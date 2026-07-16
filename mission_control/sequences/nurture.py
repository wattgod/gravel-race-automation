"""Nurture sequence — prep-kit / exit-intent leads, anti-funnel posture.

Friend-register rewrite (docs/specs/friend-register-copy.md, Jul 16) — a
single check-in on the prep kit they downloaded. No pitch in the
broadcast. Variant B kept (weight 0, same steps) for in-flight
legacy-B enrollments.
"""

_STEPS = [
    {"delay_days": 2, "template": "race_prep_tips", "subject": "how'd the prep kit land?"},
]

SEQUENCE = {
    "id": "nurture_v1",
    "name": "Lead Nurture",
    "description": "Prep-kit and exit-intent leads — one honest check-in on the kit.",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Anti-funnel", "steps": _STEPS},
        "B": {"weight": 0, "name": "Legacy slot (same steps)", "steps": _STEPS},
    },
}
