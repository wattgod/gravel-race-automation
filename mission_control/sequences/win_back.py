"""Win-back sequence — re-engage 30-day cold leads."""

SEQUENCE = {
    "id": "win_back_v1",
    "name": "Win-Back",
    "description": "Re-engage leads who haven't converted after 30 days — final value push.",
    "trigger": "lead_cold_30d",
    "active": False,
    "variants": {
        "A": {
            "weight": 50,
            "name": "Urgency",
            "steps": [
                {"delay_days": 0, "template": "win_back_urgency", "subject": "Your race is getting closer"},
                {"delay_days": 5, "template": "plan_pitch_direct", "subject": "Last chance: custom plan for {race_name}"},
            ],
        },
        "B": {
            "weight": 50,
            "name": "Value recap",
            "steps": [
                {"delay_days": 0, "template": "win_back_value", "subject": "Still thinking about {race_name}?"},
                {"delay_days": 7, "template": "social_proof", "subject": "What other riders are saying"},
            ],
        },
    },
}
