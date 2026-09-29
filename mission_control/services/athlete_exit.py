"""A leaving athlete's exit survey (/coaching/exit/, source=athlete_exit).

The answers are stored on the athlete_exit_v1 enrollment like a season
review's. This module derives the two things built from them:

- the flat keys the receipt template reads (templates read flat keys, not the
  nested answer bag): which sharing tier they chose, and what they asked for;
- a consent record in the receipts ledger's vocabulary
  (docs/specs/receipts-social-proof-2026.md §5.3, §6.2), so an athlete's "yes"
  can be filed into the private ledger without re-keying. Consent here is
  consent in principle: the ledger will not render the words until
  quote_approved_at and render_approved_at are set, after Matti sends the
  exact wording and render and the athlete says yes.

An exit is transactional, never a lead: nothing here carries race context,
and the trigger is in the engine's _POST_PURCHASE_TRIGGERS.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

# share_as -> the ledger's identity_tier. "private" ("No, keep it between us")
# is the spec's count-only tier: counted, never named or quoted.
IDENTITY_TIERS = {
    "full": "full",
    "initial": "initial",
    "age_group": "age_group",
    "private": "count_only",
}
SHARING_TIERS = ("full", "initial", "age_group")

# For the receipt: "You said I can share what you wrote, {share_tier_plain}."
SHARE_TIER_PLAIN = {
    "full": "with your full name",
    "initial": "with your first name and last initial",
    "age_group": "with your first name and age group",
}

# where_* checkbox -> ledger channel id (the spec names a site channel by its
# brand, e.g. "channel = roadie" for roadielabs.com).
CHANNELS = {
    "where_site": "gravelgod",
    "where_social": "social",
    "where_email": "email",
    "where_tp": "tp",
}

# need_* checkbox -> the receipt's plain-English list, in the athlete's terms.
NEEDS_PLAIN = {
    "need_zones": "a summary of your zones and latest tests",
    "need_notes": "notes for training on your own",
    "need_billing": "confirmation that billing has stopped",
    "need_tp": "help with your TrainingPeaks account",
}

CONNECTIONS = ("none", "comped", "friend", "work", "family")
REFERENCES = ("yes", "ask", "no")

# "It stays up for three years at most" (the consent note on the form).
CONSENT_YEARS = 3


def _plain_list(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def receipt_fields(answers: dict) -> dict:
    """Flat keys for athlete_exit_receipt.html. Absent keys make its
    {{#...}} blocks vanish, so only what they actually said shows."""
    out: dict[str, str] = {}
    share = answers.get("share_as")
    if share in SHARE_TIER_PLAIN:
        out["share_tier_plain"] = SHARE_TIER_PLAIN[share]
    needs = [plain for key, plain in NEEDS_PLAIN.items() if answers.get(key) == "yes"]
    if needs:
        out["needs_plain"] = _plain_list(needs)
    return out


def consent_record(answers: dict, now: datetime | None = None) -> dict | None:
    """The athlete's answer to "Can I share what you wrote above?", shaped
    for the receipts ledger. None when they skipped the question."""
    share = answers.get("share_as")
    if share not in IDENTITY_TIERS:
        return None
    now = now or datetime.now(timezone.utc)
    sharing = share in SHARING_TIERS
    quote = answers.get("quote", "")
    connection = answers.get("connection")
    reference = answers.get("reference")
    return {
        # Form response id: one per submission; a resubmission replaces it.
        "consent_id": f"athlete_exit:{secrets.token_hex(8)}",
        "source": "athlete_exit",
        "identity_tier": IDENTITY_TIERS[share],
        # One tick per asset (§5.3). This form only ever asks about the quote.
        "assets": ["quote"] if sharing and quote else [],
        # Exactly as written. Not approved text: approval is a later step.
        "quote": quote if sharing else "",
        "not_for": answers.get("not_for", "") if sharing else "",
        "channels": [ch for key, ch in CHANNELS.items() if sharing and answers.get(key) == "yes"],
        "material_connection": connection if connection in CONNECTIONS else None,
        "reference": reference if reference in REFERENCES else None,
        "consented_at": now.isoformat(),
        # Conservative: counted from consent, not from first publication.
        "consent_expires": (now + timedelta(days=365 * CONSENT_YEARS)).date().isoformat(),
        "quote_approved_at": None,
        "render_approved_at": None,
        "withdrawn_at": None,
    }


def exit_source_data(brand: str, answers: dict, athlete: str = "",
                     now: datetime | None = None) -> dict:
    """Everything stored on the enrollment for one exit survey. Built from
    scratch, so no lead context (race, trail, guide chapter) can ride along:
    the countdown and debrief jobs enroll anyone whose record has a race_slug."""
    source_data: dict = {"brand": brand}
    if answers:
        source_data["goal_answers"] = answers
    if athlete:
        source_data["athlete"] = athlete
    source_data.update(receipt_fields(answers))
    consent = consent_record(answers, now)
    if consent:
        source_data["consent"] = consent
    return source_data
