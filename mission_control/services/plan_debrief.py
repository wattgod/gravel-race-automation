"""A plan buyer's race debrief (/race-debrief/ on gravelgodcycling.com and
roadielabs.com, source=plan_debrief).

The sibling of the exit survey (services/athlete_exit.py), and built on its
helpers: the answers are stored on a plan_debrief_v1 / road_plan_debrief_v1
enrollment, and this module derives

- the flat keys the receipt reads (templates read flat keys, not the nested
  answer bag);
- a consent record in the receipts ledger's vocabulary
  (docs/specs/receipts-social-proof-2026.md §5.3, §6.2): the exit survey's,
  plus which product it is about (tp_plan | custom_plan | unknown) and the
  plan_id or ref from the link in the plan's notes;
- the "Next actions" for Matti's backup alert. The worker's alert builds the
  same list (workers/fueling-lead-intake/worker.js debriefNextActions); a
  test holds the two to the same output.

A debrief is transactional, never a lead: nothing here carries race context,
and the trigger is in the engine's _POST_PURCHASE_TRIGGERS.
"""
from __future__ import annotations

import re
from datetime import datetime

from mission_control.services.athlete_exit import (
    SHARE_TIER_PLAIN,
    consent_actions,
    consent_record as _exit_consent_record,
)

# ?plan= (a TP planId) and ?ref= (a custom plan). The whole value must match:
# the page, the worker and this module all check (season_review_variants.py
# PLAN_ID_PATTERN / PLAN_REF_PATTERN).
PLAN_ID_RE = re.compile(r"[0-9]{1,12}")
PLAN_REF_RE = re.compile(r"[A-Za-z0-9_-]{8,32}")

# where_* checkbox -> ledger channel id. The site channel is named by its
# brand (spec §6.2: "channel = roadie" for roadielabs.com).
CHANNELS = {
    "gravelgod": {"where_site": "gravelgod", "where_social": "social", "where_email": "email", "where_tp": "tp"},
    "roadielabs": {"where_site": "roadie", "where_social": "social", "where_email": "email", "where_tp": "tp"},
}
# For Matti's alert, as each brand's form labels them.
CHANNEL_LABELS = {
    "gravelgod": {
        "where_site": "gravelgodcycling.com",
        "where_social": "Gravel God social posts",
        "where_email": "Emails to riders choosing a plan",
        "where_tp": "The plan's TrainingPeaks page",
    },
    "roadielabs": {
        "where_site": "roadielabs.com",
        "where_social": "Roadie Labs social posts",
        "where_email": "Emails to riders choosing a plan",
        "where_tp": "The plan's TrainingPeaks page",
    },
}
CONNECTION_LABELS = {
    "none": "No, only the plan",
    "comped": "You gave me the plan free or at a discount",
    "friend": "We're friends or ride together",
    "work": "We've worked together",
    "family": "We're family",
}
BRAND_TAGS = {"gravelgod": "GG", "roadielabs": "RL", "xcskilabs": "XC"}

# A second debrief from the same address for a different plan replaces the
# live record like an exit resubmission, and the one before is kept here.
MAX_EARLIER = 5


def clean_plan(plan) -> str:
    """The planId, or "" unless it is a string that matches whole (no
    trimming, no coercion: the worker's test is the same)."""
    return plan if isinstance(plan, str) and PLAN_ID_RE.fullmatch(plan) else ""


def clean_ref(ref) -> str:
    return ref if isinstance(ref, str) and PLAN_REF_RE.fullmatch(ref) else ""


def _brand(brand: str) -> str:
    return brand if brand in CHANNELS else "gravelgod"


def product(plan: str, ref: str) -> str:
    """The ledger's product (spec §6.2)."""
    if plan:
        return "tp_plan"
    if ref:
        return "custom_plan"
    return "unknown"


def plan_label(plan: str, ref: str) -> str:
    """"plan 658461", "custom plan" or "plan unknown" (the worker's
    debriefPlanLabel)."""
    if plan:
        return f"plan {plan}"
    if ref:
        return "custom plan"
    return "plan unknown"


def brand_tag(brand: str) -> str:
    return BRAND_TAGS.get(brand, "GG")


def _roster(plan: str, ref: str) -> str:
    if plan:
        return f"the talk-to-a-rider roster for plan {plan}"
    if ref:
        return "the talk-to-a-rider roster for custom plans"
    return "the talk-to-a-rider roster"


def next_actions(answers: dict, plan: str = "", ref: str = "", brand: str = "gravelgod") -> list[str]:
    """What Matti has to do, derived from the answers (plain text)."""
    actions = consent_actions(answers, channel_labels=CHANNEL_LABELS[_brand(brand)],
                              connection_labels=CONNECTION_LABELS, roster=_roster(plan, ref))
    race = answers.get("next_race") or ""
    next_race = f" Next race: {race}{'' if race[-1:] in ('.', '!', '?') else '.'}" if race else ""
    want = answers.get("next_want")
    if want == "coaching":
        actions.append(f"Wants coaching: reply personally.{next_race}")
    elif want == "custom":
        actions.append(f"Wants a plan built around them: reply personally.{next_race}")
    elif want == "another_plan":
        actions.append(f"Asked for another plan.{next_race}")
    return actions


def receipt_fields(answers: dict) -> dict:
    """Flat keys for the receipt. The sharing paragraph shows only when they
    said yes AND wrote something to share; absent keys make its {{#...}}
    block vanish."""
    share = answers.get("share_as")
    if share in SHARE_TIER_PLAIN and (answers.get("quote") or answers.get("not_for")):
        return {"share_tier_plain": SHARE_TIER_PLAIN[share]}
    return {}


def consent_record(answers: dict, plan: str = "", ref: str = "", brand: str = "gravelgod",
                   now: datetime | None = None) -> dict | None:
    """The exit survey's consent record, plus the product it is about."""
    record = _exit_consent_record(answers, now, source="plan_debrief", channels=CHANNELS[_brand(brand)])
    if record is None:
        return None
    record.update({"product": product(plan, ref), "plan_id": plan or None, "ref": ref or None})
    return record


def debrief_source_data(brand: str, answers: dict, plan: str = "", ref: str = "",
                        now: datetime | None = None) -> dict:
    """Everything stored on the enrollment for one debrief. Built from
    scratch, so no lead context (race, trail, guide chapter) can ride along:
    the countdown and debrief jobs enroll anyone whose record has a race_slug."""
    plan, ref = clean_plan(plan), clean_ref(ref)
    source_data: dict = {"brand": brand, "product": product(plan, ref)}
    if plan:
        source_data["plan_id"] = plan
    if ref:
        source_data["ref"] = ref
    if answers:
        source_data["goal_answers"] = answers
    source_data.update(receipt_fields(answers))
    consent = consent_record(answers, plan, ref, brand, now)
    if consent:
        source_data["consent"] = consent
    return source_data


def replace_record(previous: dict, current: dict) -> dict:
    """A resubmission replaces the record, as an exit's does, so a sharing
    tier or consent they took back does not linger. The same plan is a
    correction. A different plan is a second debrief: the one before is kept
    under `earlier` (newest first, at most MAX_EARLIER), consent and all."""
    out = dict(current)
    earlier = list(previous.get("earlier") or [])
    same_plan = (previous.get("plan_id"), previous.get("ref")) == (current.get("plan_id"), current.get("ref"))
    if previous.get("goal_answers") and not same_plan:
        earlier.insert(0, {k: v for k, v in previous.items() if k != "earlier"})
    if earlier:
        out["earlier"] = earlier[:MAX_EARLIER]
    return out

