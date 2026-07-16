"""Roadie Labs nurture sequence — prep-kit / lead-magnet leads.

Friend-register rewrite (docs/specs/friend-register-copy-road.md, Jul 16) —
a single check-in on the prep notes they downloaded. No pitch in the
broadcast. Deadpan register retained.

ACTIVE — roadielabs.com verified in Resend Jul 2026.
"""

_STEPS = [
    {"delay_days": 2, "template": "road_prep_variables", "subject": "did the prep notes cover it?"},
]

SEQUENCE = {
    "id": "road_nurture_v1",
    "name": "Roadie Labs Lead Nurture",
    "brand": "roadielabs",
    "description": "Prep-kit and lead-magnet leads — one honest check-in on the notes.",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Deadpan", "steps": _STEPS},
    },
}
