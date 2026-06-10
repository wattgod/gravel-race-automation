"""Welcome sequence — new subscriber onboarding, anti-funnel posture.

A/B test of two ENTIRELY different sequences (different subjects, topics,
register). Measure with scripts/sequence_report.py; decide manually once
each variant has meaningful volume — do not auto-shift weights at this
list size.

A "Value-first": gift welcome, fueling math, honesty flex, anti-pitch,
post-pitch essay. Matti's warm register.
B "Sober": contract welcome, race three-act structure, how scoring works,
plain-spec pitch, breathing technique. Plain declarative register.
"""

_STEPS_A = [
    {"delay_days": 0, "template": "welcome_value", "subject": "start here"},
    {"delay_days": 3, "template": "fueling_mistake", "subject": "the biggest fueling mistake in gravel"},
    {"delay_days": 7, "template": "honest_ratings", "subject": "the race we gave a 36"},
    {"delay_days": 12, "template": "anti_pitch", "subject": "you probably don't need a coach"},
    # Post-pitch pure-value email — nothing for sale, keeps the relationship
    {"delay_days": 18, "template": "essay_sweet_spot", "subject": "sweet spot isn't that sweet"},
]

_STEPS_B = [
    {"delay_days": 0, "template": "sober_welcome", "subject": "what you signed up for"},
    {"delay_days": 3, "template": "sober_pacing", "subject": "how long races actually unfold"},
    {"delay_days": 7, "template": "sober_scoring", "subject": "what a 97 means"},
    {"delay_days": 12, "template": "sober_pitch", "subject": "the offer, stated plainly"},
    {"delay_days": 18, "template": "sober_breathing", "subject": "a technique for the hard miles"},
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
