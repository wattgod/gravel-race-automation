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
  exact wording and render and the athlete says yes;
- the "Next actions" for Matti's backup alert. The worker's alert builds the
  same list (workers/fueling-lead-intake/worker.js exitNextActions); a test
  holds the two to the same output, and these labels to the form's.

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
AGE_GROUPS = ("under_18", "18_29", "30_39", "40_49", "50_59", "60_plus")

# For Matti's alert, as the form labels them.
SHARE_TIER_ALERT = {
    "full": "full name",
    "initial": "first name + last initial",
    "age_group": "first name + age group",
}
CHANNEL_LABELS = {
    "where_site": "gravelgodcycling.com",
    "where_social": "Gravel God social posts",
    "where_email": "Emails to riders thinking about coaching",
    "where_tp": "My TrainingPeaks coach profile",
}
CONNECTION_LABELS = {
    "none": "No, just coaching",
    "comped": "You coached me free or at a discount",
    "friend": "We're friends or ride together",
    "work": "We've worked together",
    "family": "We're family",
}
CHECKIN_LABELS = {
    "3m": "In about three months",
    "6m": "In about six months",
    "preseason": "Before next season",
}
NEED_LABELS = {
    "need_zones": "A summary of my zones and latest tests",
    "need_notes": "Notes for training on my own",
    "need_billing": "Confirmation that billing has stopped",
    "need_tp": "Help with my TrainingPeaks account",
}
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")

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
    # "You said I can share what you wrote" only when they wrote something.
    if share in SHARE_TIER_PLAIN and (answers.get("quote") or answers.get("not_for")):
        out["share_tier_plain"] = SHARE_TIER_PLAIN[share]
    needs = [plain for key, plain in NEEDS_PLAIN.items() if answers.get(key) == "yes"]
    if needs:
        out["needs_plain"] = _plain_list(needs)
    return out


def _checkin_month(code: str, now: datetime) -> str:
    """"Before next season" is the January after this one; the others count
    on from today. Mirrors the worker's checkinMonth."""
    months = {"3m": 3, "6m": 6}.get(code)
    if months is not None:
        total = now.year * 12 + (now.month - 1) + months
        return f"{MONTHS[total % 12]} {total // 12}"
    if code == "preseason":
        return f"January {now.year + 1}"
    return ""


def consent_actions(answers: dict, *, channel_labels: dict, connection_labels: dict,
                    roster: str) -> list[str]:
    """The "On the Record" block's actions, shared with the race debrief
    (services/plan_debrief.py): consent to share and its approval steps, the
    flags approval needs, and the talk-to-a-rider roster. Mirrors the
    worker's consentActions."""
    actions: list[str] = []
    tier = SHARE_TIER_ALERT.get(answers.get("share_as"))
    # "Can I share what you wrote above?" covers both texts.
    consented = bool(tier and (answers.get("quote") or answers.get("not_for")))
    if consented:
        channels = [label for key, label in channel_labels.items() if answers.get(key) == "yes"]
        connection = connection_labels.get(answers.get("connection"), "not answered")
        actions.append(
            f"Consent to share: {tier}; channels: {', '.join(channels) or 'none ticked'}; "
            f"connection: {connection}. Next: send the exact wording + render for approval. "
            "Ledger entry needs quote_approved_at and render_approved_at before it can render."
        )
    if answers.get("age_group") == "under_18":
        actions.append("Under 18: needs a parent's sign-off before anything renders.")
    if consented and answers.get("share_as") == "age_group" and answers.get("age_group") not in AGE_GROUPS:
        actions.append("Ask their age group at approval.")
    if consented and answers.get("connection") not in connection_labels:
        actions.append("Connection not answered: ask before approval.")
    if answers.get("reference") in ("yes", "ask"):
        actions.append(f"Add to {roster} "
                       f"({'yes' if answers['reference'] == 'yes' else 'ask first'}).")
    return actions


def next_actions(answers: dict, now: datetime | None = None) -> list[str]:
    """What Matti has to do, derived from the answers (plain text)."""
    now = now or datetime.now(timezone.utc)
    actions = consent_actions(answers, channel_labels=CHANNEL_LABELS,
                              connection_labels=CONNECTION_LABELS,
                              roster="the talk-to-an-athlete roster")
    checkin = answers.get("checkin")
    if checkin in CHECKIN_LABELS:
        actions.append(f"Check in around {_checkin_month(checkin, now)} ({CHECKIN_LABELS[checkin]}).")
    needs = [label for key, label in NEED_LABELS.items() if answers.get(key) == "yes"]
    if needs:
        actions.append(f"Asked for: {'; '.join(needs)}.")
    return actions


def consent_record(answers: dict, now: datetime | None = None, *,
                   source: str = "athlete_exit", channels: dict = CHANNELS) -> dict | None:
    """The athlete's answer to "Can I share what you wrote above?", shaped
    for the receipts ledger. None when they skipped the question. The race
    debrief (services/plan_debrief.py) builds on it with its own source and
    channel ids."""
    share = answers.get("share_as")
    if share not in IDENTITY_TIERS:
        return None
    now = now or datetime.now(timezone.utc)
    sharing = share in SHARING_TIERS
    # The question covers everything above it: the quote AND "who shouldn't
    # hire me". Both texts are kept, exactly as written; neither is approved.
    texts = {key: answers.get(key, "") if sharing else "" for key in ("quote", "not_for")}
    connection = answers.get("connection")
    reference = answers.get("reference")
    age_group = answers.get("age_group") if answers.get("age_group") in AGE_GROUPS else None
    return {
        # Form response id: one per submission; a resubmission replaces it.
        "consent_id": f"{source}:{secrets.token_hex(8)}",
        "source": source,
        "identity_tier": IDENTITY_TIERS[share],
        # One tick per asset (§5.3): each text they wrote and agreed to share.
        "assets": [key for key, text in texts.items() if text],
        "quote": texts["quote"],
        "not_for": texts["not_for"],
        "age_group": age_group,
        # §5.3: a parent signs before anything of a minor's renders.
        "needs_parent_signoff": age_group == "under_18",
        "channels": [ch for key, ch in channels.items() if sharing and answers.get(key) == "yes"],
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
