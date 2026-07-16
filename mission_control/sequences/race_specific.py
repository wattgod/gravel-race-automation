"""Race-specific sequence — post-quiz follow-up, anti-funnel posture.

Friend-register rewrite (docs/specs/friend-register-copy.md, Jul 16) — the
day-10 anti_pitch step is gone; no pitch in the broadcast.
"""

SEQUENCE = {
    "id": "race_specific_v1",
    "name": "Race-Specific Follow-up",
    "description": "After quiz completion — honest match notes, what their race demands.",
    "trigger": "quiz_completed",
    "active": True,
    "variants": {
        "A": {
            "weight": 100,
            "name": "Anti-funnel",
            "steps": [
                {"delay_days": 1, "template": "quiz_results_recap", "subject": "which one are you actually considering?"},
                {"delay_days": 4, "template": "race_deep_dive", "subject": "where do races usually get you?"},
            ],
        },
    },
}
