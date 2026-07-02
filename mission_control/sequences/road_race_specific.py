"""Roadie Labs race-specific sequence — post-quiz follow-up.

INACTIVE until roadielabs.com is verified in Resend — see road_welcome.py.
"""

SEQUENCE = {
    "id": "road_race_specific_v1",
    "name": "Roadie Labs Race-Specific Follow-up",
    "brand": "roadielabs",
    "description": "After quiz completion — honest match notes, what their race demands, the plain pitch.",
    "trigger": "quiz_completed",
    "active": False,
    "variants": {
        "A": {
            "weight": 100,
            "name": "Deadpan",
            "steps": [
                {"delay_days": 1, "template": "road_quiz_recap", "subject": "about your matches"},
                {"delay_days": 4, "template": "road_race_deep_dive", "subject": "what {race_name} actually demands"},
                {"delay_days": 10, "template": "road_anti_pitch", "subject": "you probably don't need a training plan"},
            ],
        },
    },
}
