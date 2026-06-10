"""Nurture sequence — prep-kit / exit-intent leads, anti-funnel posture.

Voice-true single track (June 2026 rewrite). Deliberately avoids the
essay email (welcome may also be running for the same contact); uses the
honesty-flex instead. Variant B kept (weight 0, same steps) for in-flight
legacy-B enrollments.
"""

_STEPS = [
    {"delay_days": 2, "template": "race_prep_tips", "subject": "your gut needs training too"},
    {"delay_days": 6, "template": "honest_ratings", "subject": "the race we gave a 36"},
    {"delay_days": 12, "template": "anti_pitch", "subject": "you probably don't need a coach"},
]

SEQUENCE = {
    "id": "nurture_v1",
    "name": "Lead Nurture",
    "description": "Prep-kit and exit-intent leads — prep substance, honesty flex, anti-pitch.",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Anti-funnel", "steps": _STEPS},
        "B": {"weight": 0, "name": "Legacy slot (same steps)", "steps": _STEPS},
    },
}
