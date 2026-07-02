"""Roadie Labs nurture sequence — prep-kit / lead-magnet leads.

Deadpan register. Shares road_anti_pitch/road_repitch with the welcome
sequence (same posture: one pitch, one follow-up, done).

ACTIVE — roadielabs.com verified in Resend Jul 2026.
"""

_STEPS = [
    {"delay_days": 2, "template": "road_prep_variables", "subject": "three variables that decide your fondo"},
    {"delay_days": 5, "template": "road_race_week", "subject": "race week: mostly don'ts"},
    {"delay_days": 8, "template": "road_anti_pitch", "subject": "you probably don't need a training plan"},
    {"delay_days": 11, "template": "road_repitch", "subject": "the week-six problem"},
]

SEQUENCE = {
    "id": "road_nurture_v1",
    "name": "Roadie Labs Lead Nurture",
    "brand": "roadielabs",
    "description": "Prep-kit and lead-magnet leads — prep substance, then the plain pitch.",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Deadpan", "steps": _STEPS},
    },
}
