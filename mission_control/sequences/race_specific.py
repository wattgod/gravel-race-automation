"""Race-specific sequence — post-quiz targeted content for matched races."""

SEQUENCE = {
    "id": "race_specific_v1",
    "name": "Race-Specific Follow-up",
    "description": "After quiz completion — targeted content for their top matched races + training plan pitch.",
    "trigger": "quiz_completed",
    "active": True,
    "variants": {
        "A": {
            "weight": 100,
            "name": "Standard",
            "steps": [
                {"delay_days": 1, "template": "quiz_results_recap", "subject": "Your top race matches (and what they demand)"},
                {"delay_days": 4, "template": "race_deep_dive", "subject": "Inside {race_name}: what you need to know"},
                {"delay_days": 8, "template": "plan_pitch_soft", "subject": "Train specifically for {race_name}"},
                {"delay_days": 14, "template": "plan_pitch_direct", "subject": "Your {race_name} plan — ready in 48 hours"},
            ],
        },
    },
}
