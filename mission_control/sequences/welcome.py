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

# Timing per research (Jun 2026): engagement halves by ~day 12, so pitch
# at day 7 while attention is high; product named in email 1 (no ambush);
# single re-pitch at day 10; pure-value email closes at day 17.
_STEPS_A = [
    {"delay_days": 0, "template": "welcome_value", "subject": "start here"},
    {"delay_days": 3, "template": "fueling_mistake", "subject": "the aid station will save you (it will not)"},
    {"delay_days": 5, "template": "honest_ratings", "subject": "the race we gave a 36"},
    {"delay_days": 7, "template": "anti_pitch", "subject": "you probably don't need a coach"},
    {"delay_days": 10, "template": "repitch", "subject": "what happens in week six"},
    # Post-pitch pure-value email — nothing for sale, keeps the relationship
    {"delay_days": 17, "template": "essay_sweet_spot", "subject": "sweet spot isn't that sweet"},
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
