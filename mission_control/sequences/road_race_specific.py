"""Roadie Labs race-specific sequence — post-quiz follow-up.

Friend-register rewrite (docs/specs/friend-register-copy-road.md, Jul 16) —
the day-10 anti_pitch step is gone; no pitch in the broadcast.

ACTIVE — roadielabs.com verified in Resend Jul 2026.
"""

SEQUENCE = {
    "id": "road_race_specific_v1",
    "name": "Roadie Labs Race-Specific Follow-up",
    "brand": "roadielabs",
    "description": "After quiz completion — honest match notes, what their race demands.",
    "trigger": "quiz_completed",
    "active": True,
    "variants": {
        "A": {
            "weight": 100,
            "name": "Deadpan",
            "steps": [
                {"delay_days": 1, "template": "road_quiz_recap", "subject": "which ones made the shortlist?"},
                {"delay_days": 4, "template": "road_race_deep_dive", "subject": "where do long races get you?"},
            ],
        },
    },
}
