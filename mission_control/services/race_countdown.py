"""Race-countdown lifecycle trigger — weeks-to-race enrollment job.

Daily job (see scheduler.py): joins contacts who told us their race
(enrollment source_data.race_slug) against published race dates
(web/race-dates.json per brand), and enrolls them in a countdown sequence
when their race enters a threshold window:

    16-week tier: 12 <= weeks_out <= 17   ("the honest window")
     8-week tier:  5 <= weeks_out <= 9    ("triage math")

Below 5 weeks: no email — a 3-week "plan" pitch spends trust on
low-quality sales. enroll()'s (sequence_id, contact_email) dedup makes
each tier fire at most once per contact, ever — which also acts as the
year-over-year guard. Spec: docs/specs/race-countdown-trigger.md.
"""

import asyncio
import json
import logging
import os
import re
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

from mission_control import supabase_client as db
from mission_control.config import RACE_DATES_URLS
from mission_control.services.sequence_engine import enroll

logger = logging.getLogger(__name__)

# (tier, min_weeks, max_weeks) — ranges, not equality, so the daily job
# catches contacts captured mid-window and tolerates missed runs.
_TIERS = ((16, 12.0, 17.0), (8, 5.0, 9.0))

_SEQUENCE_IDS = {
    ("gravelgod", 16): "race_countdown_16_v1",
    ("gravelgod", 8): "race_countdown_8_v1",
    ("roadielabs", 16): "road_race_countdown_16_v1",
    ("roadielabs", 8): "road_race_countdown_8_v1",
    ("xcskilabs", 16): "xc_race_countdown_16_v1",
    ("xcskilabs", 8): "xc_race_countdown_8_v1",
}

_CUSTOMER_STATUSES = ("delivered", "approved", "audit_passed")
_MAX_ENROLLMENTS_PER_RUN = 200
# A run stops after this many contacts fail: past that it is an outage, not
# a bad record, and crawling on through every contact helps nobody.
_MAX_ERRORS_PER_RUN = 10
# Not leads, whatever their stored record carries: a coached athlete's season
# review and a leaving athlete's exit survey. Intake strips race context from
# both; this also covers a record stored before it did.
_NOT_LEAD_SOURCES = frozenset({"athlete_review", "athlete_exit"})

# Last-good cache so one bad fetch doesn't blank a brand for the day.
_dates_cache: dict[str, dict[str, str]] = {}

# Last fetch error per brand (cleared on success) — surfaced in the abort
# audit entry and the startup probe so a failing fetch names its exception
# in gg_audit_log instead of only in Railway logs.
_last_errors: dict[str, str] = {}

# SiteGround (all three hosts) 403s library default UAs (Python-urllib/*,
# python-requests/*) and bot-style "Mozilla/5.0 (compatible; ...)" ones;
# without a set UA every fetch 403'd and the job aborted daily, silently,
# from the day it shipped. The browser-shaped UA below (our name on the end)
# and the JSON Accept header got 200 JSON from all three hosts, checked
# from a laptop on 2026-09-30, as did the old "GG-MissionControl/1.0". From
# Railway the fetches have been failing with 2xx non-JSON bodies, which
# looks like SiteGround's IP-based challenge rather than the UA; that is
# unconfirmed. What settles it is the failure detail below (_describe),
# which the startup probe records. RACE_DATES_USER_AGENT overrides the UA.
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36 GG-MissionControl/1.1")


def _fetch_headers() -> dict[str, str]:
    return {"User-Agent": os.environ.get("RACE_DATES_USER_AGENT") or _DEFAULT_USER_AGENT,
            "Accept": "application/json"}


def _max_per_run() -> int:
    """Countdown enrollments per run. RACE_COUNTDOWN_MAX_PER_RUN spreads a
    backlog over several days (0 pauses enrolling); read on every run."""
    try:
        return max(0, int(os.environ.get("RACE_COUNTDOWN_MAX_PER_RUN", _MAX_ENROLLMENTS_PER_RUN)))
    except ValueError:
        return _MAX_ENROLLMENTS_PER_RUN


def audit(action: str, detail: str) -> None:
    """An audit row that never takes the job down with it (the database it
    writes to may be the thing that is failing)."""
    try:
        db.log_action(action, "sequence", "", detail[:500])
    except Exception as e:
        logger.warning("audit write failed (%s): %s", action, e)


def window_closes_in(days_out: int, tier: int) -> int:
    """Days left before a race drops out of its tier's window (0 = last day)."""
    low = next(lo for t, lo, _hi in _TIERS if t == tier)
    return days_out - int(low * 7)


def classify_weeks(weeks_out: float) -> int | None:
    """Map weeks-to-race onto a countdown tier, or None if out of window."""
    for tier, lo, hi in _TIERS:
        if lo <= weeks_out <= hi:
            return tier
    return None


_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
_MONTHS.update({m[:3]: i for m, i in list(_MONTHS.items())})
_MONTHS["sept"] = 9
# "2026: January 18", "2026: March 26-28", "2026: January 31 (Skate), ...":
# the date_specific display format, which XC Ski Labs publishes as-is (GG
# and Roadie publish ISO). Year and start day are explicit, so it is
# unambiguous. "2026: Cancelled" or "2026: October TBD" are not dates.
_PREFIXED_DATE = re.compile(r"^(\d{4}):\s*([A-Za-z]+)\.?\s+(\d{1,2})\b")


def parse_race_date(value) -> date | None:
    """A published race date as a date, or None when it isn't one. Never
    raises: one bad value in a feed must not take the whole job down."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    m = _PREFIXED_DATE.match(text)
    month = _MONTHS.get(m.group(2).lower()) if m else None
    if not month:
        return None
    try:
        return date(int(m.group(1)), month, int(m.group(3)))
    except ValueError:
        return None


def warn_bad_dates(job: str, bad: list[str]) -> None:
    """One warning per run for every published date that could not be read."""
    if bad:
        logger.warning("%s: skipped %d race date(s) that are not dates: %s%s", job, len(bad),
                       "; ".join(bad[:5]), " ..." if len(bad) > 5 else "")


def _describe(status, headers, body: bytes) -> str:
    """What the host actually sent, for a fetch that didn't give us JSON: a
    bot-protection challenge and a real outage look the same otherwise."""
    ctype = (headers.get("Content-Type") if headers is not None else None) or "no content-type"
    start = body[:80].decode("utf-8", "replace").replace("\n", " ")
    return f"HTTP {status if status is not None else '?'}, {ctype}, body starts {start!r}"


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=_fetch_headers())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = getattr(resp, "status", None)
            headers = getattr(resp, "headers", None)
            body = resp.read()
    except urllib.error.HTTPError as e:
        try:
            body = e.read() or b""
        except Exception:
            body = b""
        raise ValueError(f"{e} [{_describe(e.code, e.headers, body)}]") from None
    try:
        data = json.loads(body)
    except ValueError as e:
        raise ValueError(f"{e} [{_describe(status, headers, body)}]") from None
    if not isinstance(data, dict):
        raise ValueError(f"not a JSON object [{_describe(status, headers, body)}]")
    return data


def _fetch_dates_sync() -> dict[str, dict[str, str]]:
    """Fetch each brand's race-dates.json; fall back to last-good on failure.

    Last-good lives in TWO places: this process (fast path) and gg_settings
    (survives restarts). The in-memory cache alone is nearly useless on
    Railway — every push to main redeploys, so the process is often minutes
    old when a job fires, and one flaky fetch (the hosts intermittently
    serve a non-JSON challenge page) used to mean an empty cache and an
    aborted run.
    """
    for brand, url in RACE_DATES_URLS.items():
        try:
            _dates_cache[brand] = _get_json(url)
            _last_errors.pop(brand, None)
            try:
                db.set_setting(f"race_dates_{brand}", json.dumps({
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "dates": _dates_cache[brand],
                }))
            except Exception as e:  # cache write must never break the fetch
                logger.warning("race-dates DB cache write failed for %s: %s", brand, e)
        except Exception as e:
            _last_errors[brand] = repr(e)
            if not _dates_cache.get(brand):
                _load_db_fallback(brand)
            logger.warning("race-dates fetch failed for %s (%s): %s — using cache (%d entries)",
                           brand, url, e, len(_dates_cache.get(brand, {})))
    return _dates_cache


def _load_db_fallback(brand: str) -> None:
    """Populate the in-memory cache for a brand from the gg_settings copy."""
    try:
        raw = db.get_setting(f"race_dates_{brand}")
        if not raw:
            return
        stored = json.loads(raw)
        dates = stored.get("dates") or {}
        if dates:
            _dates_cache[brand] = dates
            _last_errors[brand] += f" (using DB copy from {stored.get('fetched_at', '?')[:10]}, {len(dates)} entries)"
    except Exception as e:
        logger.warning("race-dates DB fallback failed for %s: %s", brand, e)


def probe_race_dates() -> str:
    """One fetch pass, summarized for the audit log. Called at app startup
    (see app.py lifespan) so every deploy immediately records whether the
    dates pipeline works FROM THIS ENVIRONMENT — a fetch that passes from a
    dev laptop can still fail from the host's egress."""
    dates = _fetch_dates_sync()
    parts = []
    for brand in RACE_DATES_URLS:
        if brand in _last_errors:
            parts.append(f"{brand}: FAILED {_last_errors[brand]}")
        else:
            parts.append(f"{brand}: ok ({len(dates.get(brand) or {})} entries)")
    return " | ".join(parts)


def gather_candidates(enrollments: list[dict]) -> tuple[dict, set]:
    """From enrollment rows: latest race per contact, and who is mid-sequence.

    Returns ({email: {name, brand, race_slug, race_name}}, {emails with an
    active enrollment}). Later rows win (db returns in insert order).
    """
    contacts: dict[str, dict] = {}
    mid_sequence: set[str] = set()
    for e in enrollments:
        email = e.get("contact_email")
        if not email:
            continue
        if e.get("status") == "active":
            mid_sequence.add(email)
        sd = e.get("source_data") or {}
        if sd.get("race_slug") and e.get("source") not in _NOT_LEAD_SOURCES:
            contacts[email] = {
                "name": e.get("contact_name") or "",
                "brand": sd.get("brand", "gravelgod"),
                "race_slug": sd["race_slug"],
                "race_name": sd.get("race_name") or sd["race_slug"],
            }
    return contacts, mid_sequence


async def run_race_countdown(today: date | None = None) -> dict:
    """One countdown pass. Returns a summary dict for logging/tests."""
    today = today or datetime.now(timezone.utc).date()
    summary = {"candidates": 0, "enrolled": 0, "skipped_window": 0,
               "skipped_mid_sequence": 0, "skipped_customer": 0,
               "skipped_no_date": 0, "skipped_bad_date": 0, "errors": 0,
               "capped": False, "deferred": 0, "aborted": False}
    bad_dates: list[str] = []

    dates = await asyncio.to_thread(_fetch_dates_sync)
    if not any(dates.values()):
        logger.error("race-countdown: no race dates available for any brand — aborting run")
        # Surface the abort where an operator will actually see it. This
        # exact path failed silently for weeks (403'd fetches) with the only
        # evidence buried in Railway logs.
        errors = "; ".join(f"{b}: {e}" for b, e in _last_errors.items()) or "unknown"
        db.log_action("race_countdown_aborted", "sequence", "",
                      f"no race dates available for any brand — {errors}"[:500])
        return summary

    enrollments = db.select(
        "gg_sequence_enrollments",
        columns="contact_email,contact_name,source,source_data,status",
    )
    contacts, mid_sequence = gather_candidates(enrollments)
    summary["candidates"] = len(contacts)

    # Who is in a window today, soonest-closing window first: when the cap
    # cuts a run short (a backlog after the job was down), whoever would
    # miss their window goes first, and the rest are still in it tomorrow.
    queue = []
    for email, info in contacts.items():
        raw = (dates.get(info["brand"]) or {}).get(info["race_slug"])
        if not raw:
            summary["skipped_no_date"] += 1
            continue
        race_date = parse_race_date(raw)
        if race_date is None:
            # one bad value in a feed skips that race, never the run
            summary["skipped_bad_date"] += 1
            bad_dates.append(f"{info['brand']}/{info['race_slug']}={raw!r}")
            continue
        days_out = (race_date - today).days
        tier = classify_weeks(days_out / 7)
        if tier is None:
            summary["skipped_window"] += 1
            continue

        # Don't stack on top of an in-flight sequence (welcome/nurture pitch)
        if email in mid_sequence:
            summary["skipped_mid_sequence"] += 1
            continue
        queue.append((window_closes_in(days_out, tier), email, info, race_date, tier))
    queue.sort(key=lambda item: item[0])  # stable: ties keep their order

    cap = _max_per_run()
    first_error: Exception | None = None
    for position, (_closes_in, email, info, race_date, tier) in enumerate(queue):
        if summary["enrolled"] >= cap:
            summary["capped"] = True
            summary["deferred"] = len(queue) - position
            logger.warning("race-countdown: enrollment cap hit (%d) — %d deferred to the next run",
                           cap, summary["deferred"])
            break
        weeks_out = (race_date - today).days / 7
        try:
            # Customer suppression — mirrors the engine's marketing suppression
            customer = db.select_one("gg_athletes", columns="plan_status",
                                     match={"email": email})
            if customer and customer.get("plan_status") in _CUSTOMER_STATUSES:
                summary["skipped_customer"] += 1
                continue

            seq_id = _SEQUENCE_IDS[(info["brand"], tier)]
            result = enroll(
                email, info["name"], seq_id,
                source="race_countdown",
                source_data={
                    "brand": info["brand"],
                    "race_slug": info["race_slug"],
                    "race_name": info["race_name"],
                    "race_date": race_date.isoformat(),
                    "weeks_out": str(int(round(weeks_out))),
                },
            )
            if result:
                summary["enrolled"] += 1
                db.log_action("race_countdown_enrolled", "sequence", seq_id,
                              f"{email} — {info['race_name']} in ~{weeks_out:.1f} weeks")
        except Exception as e:
            # one contact's failure is logged and skipped; the rest still go
            summary["errors"] += 1
            if first_error is None:
                first_error = e
                logger.exception("race-countdown: processing a contact failed (first error this run)")
            if summary["errors"] >= _MAX_ERRORS_PER_RUN:
                summary["aborted"] = True
                audit("race_countdown_aborted",
                      f"{summary['errors']} contacts failed — {first_error!r}")
                break

    if summary["errors"]:
        audit("race_countdown_errors",
              f"{summary['errors']} contact(s) failed, {summary['enrolled']} enrolled — {first_error!r}")
    warn_bad_dates("race-countdown", bad_dates)
    logger.info("race-countdown run: %s", summary)
    return summary
