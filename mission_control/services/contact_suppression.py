"""Do-not-email list: current and former coached athletes.

Matti, Oct 23 2026: "Make sure not to message former or current athletes."

gg_contact_suppressions holds one row per address. Every marketing and
follow-up path checks it before it enrolls or sends: enroll(),
_send_next_step(), resend_first_step() and the race-watch notifier. The only
exemption is a receipt for a form the person just filed themselves (a season
review, an exit survey, a plan debrief), because that is an answer, not
outreach.

The check fails closed: if the list can't be read, the send is skipped and the
error is logged. A missed lead email costs a day; an athlete getting a sales
email costs trust.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

TABLE = "gg_contact_suppressions"


def normalise(email: str | None) -> str:
    return (email or "").strip().lower()


def is_suppressed(email: str | None) -> bool:
    """True when the address is on the do-not-email list, or the list can't be read."""
    from mission_control import supabase_client as db

    address = normalise(email)
    if not address:
        return False
    try:
        return db.select_one(TABLE, columns="email", match={"email": address}) is not None
    except Exception:
        logger.exception("do-not-email list unreadable; treating %s as suppressed", address)
        return True


def load_suppressed() -> set[str] | None:
    """The whole list, for batch jobs. None when it can't be read, and the
    caller then sends nothing."""
    from mission_control import supabase_client as db

    try:
        rows = db.select(TABLE, columns="email")
    except Exception:
        logger.exception("do-not-email list unreadable")
        return None
    return {normalise(r.get("email")) for r in rows if r.get("email")}
