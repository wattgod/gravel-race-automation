"""Win-back lifecycle trigger — the only thing that fires lead_cold_30d.

Daily job (see scheduler.py). OFF unless WIN_BACK_ENABLED is set; the same
flag activates the win_back_v1 / xc_win_back_v1 definitions, which
enroll() otherwise refuses. Each run enrolls at most WIN_BACK_DAILY_CAP
contacts (default 20): every reply lands in Matti's inbox and the reply is
the product, so the cold backlog drains over days, not in one afternoon.

A contact is a cold lead when ALL of these hold (contact level, every brand):

- no active enrollment anywhere (every sequence they were in has finished)
  and at least one finished marketing enrollment;
- the newest activity of any kind is 30+ days old: an enrollment starting
  or completing, any send (race-watch updates included), an open, a click,
  a reply attributed to a send, or a Gmail lead-conversation message in
  either direction;
- never unsubscribed, opted out, bounced, complained, or paused (a bounce
  pauses the enrollment; a manual pause is respected the same way);
- not a buyer or coached athlete: no gg_athletes row, no closed_won deal,
  no payment on their deal, no post-purchase / athlete-review / exit /
  plan-debrief enrollment;
- no Gmail conversation that is waiting on Matti or already decided
  (won / lost);
- never had a win-back (either brand) and never had a race debrief — the
  debrief already asked "did you end up racing it?", and win-back would
  ask it again.

Brand comes from the contact's newest marketing enrollment. Roadie Labs has
no win-back definition, so its cold leads are counted, not enrolled.

Premise honesty: the GG/XC templates say "a while back you were looking at
{race_name}. Did you end up racing it?". That is only true once the race
has happened, so race_name is passed only when the published date for that
race is in the past; otherwise the template's {{^race_name}} branch
("a while back you were poking around the race database") renders.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone

from mission_control import config
from mission_control import supabase_client as db
from mission_control.sequences import get_sequence, sequence_brand
from mission_control.services.race_countdown import (
    _MAX_ERRORS_PER_RUN,
    _NOT_LEAD_SOURCES,
    _fetch_dates_sync,
    audit,
    parse_race_date,
)
from mission_control.services.sequence_engine import (
    OPT_OUT_FLAG,
    _POST_PURCHASE_TRIGGERS,
    enroll,
)

logger = logging.getLogger(__name__)

COLD_DAYS = 30
WIN_BACK_TRIGGER = "lead_cold_30d"

SEQUENCE_IDS = {
    "gravelgod": "win_back_v1",
    "xcskilabs": "xc_win_back_v1",
    # roadielabs: no win-back definition (road_win_back.html exists, no def)
}

_SUPPRESSED_ENROLLMENT_STATUSES = {"unsubscribed", "paused"}
_SUPPRESSED_SEND_STATUSES = {"bounced", "complained"}
# A conversation in one of these states means a human thread is open on
# Matti's side or already settled — an automated check-in would talk over it.
_HOLD_CONVERSATION_STATUSES = {
    "needs_reply", "suggested", "approved_for_gmail", "gmail_drafted",
    "draft_conflict", "won", "lost",
}
_PAGE = 1000


def _ts(value) -> datetime | None:
    """A stored timestamp as an aware UTC datetime, or None."""
    if not value:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _norm(email) -> str:
    return str(email or "").strip().lower()


def select_cold_leads(
    enrollments: list[dict],
    sends: list[dict],
    conversations: list[dict],
    buyer_emails: set[str],
    now: datetime,
    race_dates: dict[str, dict[str, str]] | None = None,
) -> tuple[list[dict], dict]:
    """Pure selection: who is a cold lead today, newest-cold first.

    Returns (candidates, skip_counts). Each candidate is
    {email, name, brand, sequence_id, last_activity, source_data}.
    """
    race_dates = race_dates or {}
    cutoff = now - timedelta(days=COLD_DAYS)
    today = now.date()
    contacts: dict[str, dict] = {}
    by_enrollment: dict[str, str] = {}

    def contact(email: str) -> dict:
        return contacts.setdefault(email, {
            "email": None, "name": "", "active": False, "suppressed": False,
            "not_lead": False, "had_win_back": False, "had_debrief": False,
            "completed_marketing": 0, "last": None, "latest_marketing": None,
            "races": {}, "held": False,
        })

    def touch(c: dict, value) -> None:
        dt = _ts(value)
        if dt and (c["last"] is None or dt > c["last"]):
            c["last"] = dt

    for e in enrollments:
        key = _norm(e.get("contact_email"))
        if not key:
            continue
        c = contact(key)
        c["email"] = c["email"] or e.get("contact_email")
        if e.get("id"):
            by_enrollment[str(e["id"])] = key
        seq = get_sequence(e.get("sequence_id") or "") or {}
        trigger = seq.get("trigger")
        status = e.get("status")
        sd = e.get("source_data") or {}
        touch(c, e.get("enrolled_at"))
        touch(c, e.get("completed_at"))
        if status == "active":
            c["active"] = True
        if status in _SUPPRESSED_ENROLLMENT_STATUSES or sd.get(OPT_OUT_FLAG):
            c["suppressed"] = True
        if trigger in _POST_PURCHASE_TRIGGERS or e.get("source") in _NOT_LEAD_SOURCES:
            c["not_lead"] = True
            continue
        if trigger == WIN_BACK_TRIGGER or e.get("source") == "win_back":
            c["had_win_back"] = True
        if trigger == "race_debrief":
            c["had_debrief"] = True
        if not seq:
            continue  # unknown/retired sequence id: activity counted, brand not taken from it
        brand = sequence_brand(seq)
        if status == "completed":
            c["completed_marketing"] += 1
        when = _ts(e.get("enrolled_at"))
        latest = c["latest_marketing"]
        if latest is None or (when and (latest[0] is None or when >= latest[0])):
            c["latest_marketing"] = (when, brand, e.get("contact_name") or "")
        if sd.get("race_slug"):
            prev = c["races"].get(brand)
            if prev is None or (when and (prev[0] is None or when >= prev[0])):
                c["races"][brand] = (when, sd["race_slug"], sd.get("race_name") or "")

    for s in sends:
        key = by_enrollment.get(str(s.get("enrollment_id")))
        if not key:
            continue
        c = contacts[key]
        for col in ("sent_at", "opened_at", "clicked_at", "first_reply_at", "complained_at"):
            touch(c, s.get(col))
        if s.get("status") in _SUPPRESSED_SEND_STATUSES or s.get("complained_at"):
            c["suppressed"] = True

    for conv in conversations:
        key = _norm(conv.get("contact_email"))
        if key not in contacts:
            continue  # a Gmail-only contact was never enrolled: not ours to win back
        c = contacts[key]
        touch(c, conv.get("last_inbound_at"))
        touch(c, conv.get("last_outbound_at"))
        if conv.get("status") in _HOLD_CONVERSATION_STATUSES:
            c["held"] = True

    skips = {"active": 0, "suppressed": 0, "not_lead": 0, "buyer": 0,
             "had_win_back": 0, "had_debrief": 0, "conversation": 0,
             "no_finished_sequence": 0, "recent_activity": 0,
             "no_activity_record": 0, "no_sequence_for_brand": 0}
    out = []
    for key, c in contacts.items():
        reason = None
        if c["not_lead"]:
            reason = "not_lead"
        elif key in buyer_emails:
            reason = "buyer"
        elif c["suppressed"]:
            reason = "suppressed"
        elif c["active"]:
            reason = "active"
        elif c["had_win_back"]:
            reason = "had_win_back"
        elif c["had_debrief"]:
            reason = "had_debrief"
        elif c["held"]:
            reason = "conversation"
        elif not c["completed_marketing"] or not c["latest_marketing"]:
            reason = "no_finished_sequence"
        elif c["last"] is None:
            reason = "no_activity_record"
        elif c["last"] > cutoff:
            reason = "recent_activity"
        if reason:
            skips[reason] += 1
            continue
        _, brand, name = c["latest_marketing"]
        seq_id = SEQUENCE_IDS.get(brand)
        if not seq_id:
            skips["no_sequence_for_brand"] += 1
            continue
        source_data = {"brand": brand, "cold_since": c["last"].isoformat()}
        race = c["races"].get(brand)
        if race and race[2]:  # a bare slug is not a name to put in a sentence
            raw = (race_dates.get(brand) or {}).get(race[1])
            race_date = parse_race_date(raw) if raw else None
            if race_date is not None and race_date < today:
                source_data.update({"race_slug": race[1], "race_name": race[2],
                                    "race_date": race_date.isoformat()})
        out.append({"email": c["email"], "name": name, "brand": brand,
                    "sequence_id": seq_id, "last_activity": c["last"],
                    "source_data": source_data})
    # Newest-cold first: the lead most likely to remember us goes first when
    # the cap cuts a run short; the rest are still cold tomorrow.
    out.sort(key=lambda x: x["last_activity"], reverse=True)
    return out, skips


def _select_all(table: str, columns: str) -> list[dict]:
    """Every row, paged — PostgREST caps an unpaged select (1000 by default)."""
    rows: list[dict] = []
    offset = 0
    while True:
        page = db.select(table, columns=columns, order="id", limit=_PAGE, offset=offset)
        rows.extend(page)
        if len(page) < _PAGE:
            return rows
        offset += _PAGE


def _load_sync() -> tuple[list, list, list, set]:
    enrollments = _select_all(
        "gg_sequence_enrollments",
        "id,sequence_id,contact_email,contact_name,source,source_data,status,enrolled_at,completed_at")
    sends = _select_all(
        "gg_sequence_sends",
        "id,enrollment_id,status,sent_at,opened_at,clicked_at,first_reply_at,complained_at")
    conversations = _select_all(
        "gg_lead_conversations", "id,contact_email,status,last_inbound_at,last_outbound_at")
    buyers = {_norm(a.get("email")) for a in _select_all("gg_athletes", "id,email")}
    deals = _select_all("gg_deals", "id,contact_email,stage")
    paid_deals = {str(p.get("deal_id")) for p in _select_all("gg_payments", "id,deal_id")
                  if p.get("deal_id")}
    buyers |= {_norm(d.get("contact_email")) for d in deals
               if d.get("stage") == "closed_won" or str(d.get("id")) in paid_deals}
    buyers.discard("")
    return enrollments, sends, conversations, buyers


async def run_win_back(now: datetime | None = None) -> dict:
    """One win-back pass. Returns a summary dict for logging/tests."""
    summary = {"enabled": bool(config.WIN_BACK_ENABLED), "candidates": 0, "enrolled": 0,
               "with_race": 0, "capped": False, "errors": 0, "aborted": False,
               "cap": config.WIN_BACK_DAILY_CAP, "skipped": {}}
    if not config.WIN_BACK_ENABLED:
        logger.info("win-back: WIN_BACK_ENABLED is off — nothing selected or enrolled")
        return summary
    now = now or datetime.now(timezone.utc)

    try:
        enrollments, sends, conversations, buyers = await asyncio.to_thread(_load_sync)
    except Exception as e:
        # Fail closed: a missing table means a missing suppression signal.
        summary["aborted"] = True
        audit("win_back_aborted", f"could not read lead history — {e!r}")
        logger.exception("win-back: could not read lead history — run aborted")
        return summary

    try:
        race_dates = await asyncio.to_thread(_fetch_dates_sync)
    except Exception as e:  # no dates only costs the race-named opener
        logger.warning("win-back: race dates unavailable (%r) — race-free opener for all", e)
        race_dates = {}

    candidates, skips = select_cold_leads(enrollments, sends, conversations, buyers, now,
                                          race_dates)
    summary["candidates"] = len(candidates)
    summary["skipped"] = skips
    first_error: Exception | None = None

    for cand in candidates:
        if summary["enrolled"] >= config.WIN_BACK_DAILY_CAP:
            summary["capped"] = True
            break
        try:
            result = enroll(cand["email"], cand["name"], cand["sequence_id"],
                            source="win_back", source_data=cand["source_data"])
            if result:
                summary["enrolled"] += 1
                if cand["source_data"].get("race_name"):
                    summary["with_race"] += 1
                db.log_action("win_back_enrolled", "sequence", cand["sequence_id"],
                              f"{cand['email']} — cold since {cand['last_activity'].date()}")
        except Exception as e:
            summary["errors"] += 1
            if first_error is None:
                first_error = e
                logger.exception("win-back: enrolling a contact failed (first error this run)")
            if summary["errors"] >= _MAX_ERRORS_PER_RUN:
                summary["aborted"] = True
                audit("win_back_aborted", f"{summary['errors']} contacts failed — {first_error!r}")
                break

    audit("win_back_run",
          f"enrolled {summary['enrolled']} of {summary['candidates']} cold "
          f"(cap {summary['cap']}, {summary['with_race']} with race), errors {summary['errors']}")
    logger.info("win-back run: %s", summary)
    return summary
