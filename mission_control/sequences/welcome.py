"""Welcome sequence — new subscriber onboarding."""

SEQUENCE = {
    "id": "welcome_v1",
    "name": "Welcome Sequence",
    "description": "New subscriber onboarding — introduce GG, share race content, soft CTA for training plan.",
    "trigger": "new_subscriber",
    "active": True,
    "variants": {
        "A": {
            "weight": 50,
            "name": "Editorial (slow build)",
            "steps": [
                {"delay_days": 0, "template": "welcome_a", "subject": "Welcome to Gravel God"},
                {"delay_days": 3, "template": "top_races", "subject": "The 10 races defining 2026"},
                {"delay_days": 7, "template": "plan_pitch_soft", "subject": "What if you showed up race-ready?"},
                {"delay_days": 14, "template": "social_proof", "subject": "How Sarah PR'd SBT by 40 minutes"},
            ],
        },
        "B": {
            "weight": 50,
            "name": "Direct (faster cadence)",
            "steps": [
                {"delay_days": 0, "template": "welcome_b", "subject": "You're in. Here's what's next."},
                {"delay_days": 2, "template": "top_races", "subject": "The races everyone's talking about"},
                {"delay_days": 5, "template": "plan_pitch_direct", "subject": "Custom Training Plan: $249, built for your race"},
            ],
        },
    },
}
