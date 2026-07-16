"""Welcome sequence — new subscriber onboarding, anti-funnel posture.

A/B test of two ENTIRELY different sequences (different subjects, topics,
register). Measure with scripts/sequence_report.py; decide manually once
each variant has meaningful volume — do not auto-shift weights at this
list size.

A "Value-first": friend-register rewrite (docs/specs/friend-register-copy.md,
Jul 16) — a single opener keyed to whatever context the capture gave us
(guide chapter / browsing trail / race page / anonymous, offseason-aware),
plus one optional day-10 follow-up. No pitch in the broadcast; replies are
the conversion engine.
B "Sober": contract welcome, race three-act structure, how scoring works,
plain-spec pitch, breathing technique. Plain declarative register.
Unchanged — stays as the A/B control.
"""

# Friend-register set (docs/specs/friend-register-copy.md) — the pitch-count
# promise machinery is gone with the removed pitch/repitch/essay steps.
_STEPS_A = [
    {"delay_days": 0, "template": "welcome_value", "subject": "getting ready for one of these?"},
    {"delay_days": 10, "template": "welcome_followup", "subject": "land on a race yet?"},
]

_STEPS_B = [
    {"delay_days": 0, "template": "sober_welcome", "subject": "what you signed up for"},
    {"delay_days": 3, "template": "sober_pacing", "subject": "how long races actually unfold"},
    {"delay_days": 5, "template": "sober_scoring", "subject": "what a 97 means"},
    {"delay_days": 7, "template": "sober_pitch", "subject": "the offer, stated plainly"},
    {"delay_days": 10, "template": "sober_repitch", "subject": "the follow-up, and then we're done"},
    {"delay_days": 17, "template": "sober_breathing", "subject": "a technique for the hard miles"},
]

SEQUENCE = {
    "id": "welcome_v1",
    "name": "Welcome Sequence",
    "description": "New subscriber onboarding — A/B of two distinct tracks: value-first (warm) vs sober (plain).",
    "trigger": "new_subscriber",
    "active": True,
    "variants": {
        "A": {"weight": 50, "name": "Value-first", "steps": _STEPS_A},
        "B": {"weight": 50, "name": "Sober", "steps": _STEPS_B},
    },
}
