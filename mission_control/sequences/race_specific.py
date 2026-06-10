"""Race-specific sequence — post-quiz follow-up, anti-funnel posture."""

SEQUENCE = {
    "id": "race_specific_v1",
    "name": "Race-Specific Follow-up",
    "description": "After quiz completion — honest match notes, what their race demands, anti-pitch.",
    "trigger": "quiz_completed",
    "active": True,
    "variants": {
        "A": {
            "weight": 100,
            "name": "Anti-funnel",
            "steps": [
                {"delay_days": 1, "template": "quiz_results_recap", "subject": "about your race matches"},
                {"delay_days": 4, "template": "race_deep_dive", "subject": "what {race_name} actually demands"},
                {"delay_days": 10, "template": "anti_pitch", "subject": "you probably don't need a coach"},
            ],
        },
    },
}
