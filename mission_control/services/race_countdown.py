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
}

_CUSTOMER_STATUSES = ("delivered", "approved", "audit_passed")
_MAX_ENROLLMENTS_PER_RUN = 200

# Last-good cache so one bad fetch doesn't blank a brand for the day.
_dates_cache: dict[str, dict[str, str]] = {}


def classify_weeks(weeks_out: float) -> int | None:
    """Map weeks-to-race onto a countdown tier, or None if out of window."""
    for tier, lo, hi in _TIERS:
        if lo <= weeks_out <= hi:
            return tier
    return None


def _fetch_dates_sync() -> dict[str, dict[str, str]]:
    """Fetch each brand's race-dates.json; fall back to last-good on failure."""
    for brand, url in RACE_DATES_URLS.items():
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                _dates_cache[brand] = json.load(resp)
        except Exception as e:
            logger.warning("race-dates fetch failed for %s (%s): %s — using cache (%d entries)",
                           brand, url, e, len(_dates_cache.get(brand, {})))
    return _dates_cache


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
        if sd.get("race_slug"):
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
               "skipped_no_date": 0, "capped": False}

    dates = await asyncio.to_thread(_fetch_dates_sync)
    if not any(dates.values()):
        logger.error("race-countdown: no race dates available for any brand — aborting run")
        return summary

    enrollments = db.select(
        "gg_sequence_enrollments",
        columns="contact_email,contact_name,source_data,status",
    )
    contacts, mid_sequence = gather_candidates(enrollments)
    summary["candidates"] = len(contacts)

    for email, info in contacts.items():
        if summary["enrolled"] >= _MAX_ENROLLMENTS_PER_RUN:
            summary["capped"] = True
            logger.warning("race-countdown: enrollment cap hit (%d) — remainder deferred to next run",
                           _MAX_ENROLLMENTS_PER_RUN)
            break

        iso = (dates.get(info["brand"]) or {}).get(info["race_slug"])
        if not iso:
            summary["skipped_no_date"] += 1
            continue
        race_date = date.fromisoformat(iso)
        weeks_out = (race_date - today).days / 7
        tier = classify_weeks(weeks_out)
        if tier is None:
            summary["skipped_window"] += 1
            continue

        # Don't stack on top of an in-flight sequence (welcome/nurture pitch)
        if email in mid_sequence:
            summary["skipped_mid_sequence"] += 1
            continue

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
                "race_date": iso,
                "weeks_out": str(int(round(weeks_out))),
            },
        )
        if result:
            summary["enrolled"] += 1
            db.log_action("race_countdown_enrolled", "sequence", seq_id,
                          f"{email} — {info['race_name']} in ~{weeks_out:.1f} weeks")

    logger.info("race-countdown run: %s", summary)
    return summary
