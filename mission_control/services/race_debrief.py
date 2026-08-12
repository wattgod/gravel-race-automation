"""Race-debrief lifecycle trigger — post-race how'd-it-go enrollment job.

Daily job (see scheduler.py): joins contacts who told us their race
(enrollment source_data.race_slug) against published race dates and
enrolls them in a one-email debrief once the race has passed:

    3 <= days_since <= 180

The 3-day floor lets the dust settle; the 180-day ceiling keeps the
premise honest ("back in May" still reads as a friend remembering, a year
later it doesn't). enroll()'s (sequence_id, contact_email) dedup makes the
debrief fire at most once per contact, ever.

The daily cap is deliberately small: every reply lands in Matti's inbox
and the reply IS the product (draft_race_reply.py). Enrolling the whole
backlog in one day would produce a week of replies in an afternoon.
"""

import asyncio
import logging
from datetime import date, datetime, timezone

from mission_control import supabase_client as db
from mission_control.services.race_countdown import (
    _fetch_dates_sync,
    _last_errors as _rc_errors,
    gather_candidates,
)
from mission_control.services.sequence_engine import enroll

logger = logging.getLogger(__name__)

_MIN_DAYS_SINCE = 3
_MAX_DAYS_SINCE = 180

_SEQUENCE_IDS = {
    "gravelgod": "race_debrief_v1",
    "roadielabs": "road_race_debrief_v1",
    "xcskilabs": "xc_race_debrief_v1",
}

_CUSTOMER_STATUSES = ("delivered", "approved", "audit_passed")
_MAX_ENROLLMENTS_PER_RUN = 12


def when_phrase(days_since: int, race_date: date) -> str:
    """Human phrase for how long ago the race was — computed here so the
    template never has to do date math."""
    if days_since <= 10:
        return "the other weekend"
    if days_since <= 45:
        return "a few weeks back"
    return f"back in {race_date.strftime('%B')}"


async def run_race_debrief(today: date | None = None) -> dict:
    """One debrief pass. Returns a summary dict for logging/tests."""
    today = today or datetime.now(timezone.utc).date()
    summary = {"candidates": 0, "enrolled": 0, "enrolled_inferred": 0,
               "skipped_window": 0, "skipped_mid_sequence": 0,
               "skipped_customer": 0, "skipped_no_date": 0,
               "skipped_no_sequence": 0, "capped": False}

    dates = await asyncio.to_thread(_fetch_dates_sync)
    if not any(dates.values()):
        logger.error("race-debrief: no race dates available for any brand — aborting run")
        errors = "; ".join(f"{b}: {e}" for b, e in _rc_errors.items()) or "unknown"
        db.log_action("race_debrief_aborted", "sequence", "",
                      f"no race dates available for any brand — {errors}"[:500])
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
            logger.info("race-debrief: daily cap hit (%d) — remainder deferred to next run",
                        _MAX_ENROLLMENTS_PER_RUN)
            break

        seq_id = _SEQUENCE_IDS.get(info["brand"])
        if not seq_id:
            summary["skipped_no_sequence"] += 1
            continue

        iso = (dates.get(info["brand"]) or {}).get(info["race_slug"])
        if not iso:
            summary["skipped_no_date"] += 1
            continue
        race_date = date.fromisoformat(iso)
        days_since = (today - race_date).days
        inferred = False
        if days_since < _MIN_DAYS_SINCE:
            # Catalog updates roll a past race's date forward to the next
            # edition, which would silently exempt its leads from a debrief
            # forever. Infer the previous edition one year back; the 3-180
            # window on the inferred date naturally excludes races that are
            # simply upcoming (a race N weeks out infers to ~52-N weeks ago,
            # outside the window until the race is ~6 months away).
            try:
                prev_edition = race_date.replace(year=race_date.year - 1)
            except ValueError:  # Feb 29 → Feb 28 of the prior year
                prev_edition = race_date.replace(year=race_date.year - 1, day=28)
            days_since = (today - prev_edition).days
            inferred = True
        if not (_MIN_DAYS_SINCE <= days_since <= _MAX_DAYS_SINCE):
            summary["skipped_window"] += 1
            continue

        # Don't land a debrief mid-welcome/nurture
        if email in mid_sequence:
            summary["skipped_mid_sequence"] += 1
            continue

        # Customer suppression — customers debrief through post-purchase
        # (nps_request already asks "did the race happen?")
        customer = db.select_one("gg_athletes", columns="plan_status",
                                 match={"email": email})
        if customer and customer.get("plan_status") in _CUSTOMER_STATUSES:
            summary["skipped_customer"] += 1
            continue

        result = enroll(
            email, info["name"], seq_id,
            source="race_debrief",
            source_data={
                "brand": info["brand"],
                "race_slug": info["race_slug"],
                "race_name": info["race_name"],
                "race_date": iso,
                # An inferred edition date can be off by a week or two, so
                # the phrase must not name a month — "this season" stays
                # honest at any offset.
                "when_phrase": "this season" if inferred
                               else when_phrase(days_since, race_date),
                **({"date_inferred": "true"} if inferred else {}),
            },
        )
        if result:
            summary["enrolled"] += 1
            if inferred:
                summary["enrolled_inferred"] += 1
            db.log_action("race_debrief_enrolled", "sequence", seq_id,
                          f"{email} — {info['race_name']} was {days_since}d ago"
                          + (" (inferred previous edition)" if inferred else ""))

    logger.info("race-debrief run: %s", summary)
    return summary
