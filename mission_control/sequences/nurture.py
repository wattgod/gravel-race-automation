"""Nurture sequence — engaged lead follow-up with race content + soft pitch."""

SEQUENCE = {
    "id": "nurture_v1",
    "name": "Lead Nurture",
    "description": "For leads who downloaded a prep kit or used exit intent — race content drip with gentle conversion push.",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {
            "weight": 50,
            "name": "Content-heavy",
            "steps": [
                {"delay_days": 2, "template": "race_prep_tips", "subject": "3 things most gravel racers get wrong"},
                {"delay_days": 6, "template": "training_myth", "subject": "The base-miles myth (and what actually works)"},
                {"delay_days": 10, "template": "plan_pitch_soft", "subject": "Your race is coming — are you ready?"},
                {"delay_days": 17, "template": "social_proof", "subject": "From DNS to finish line: Mike's story"},
            ],
        },
        "B": {
            "weight": 50,
            "name": "Value-first",
            "steps": [
                {"delay_days": 2, "template": "race_prep_tips", "subject": "Your race-day checklist (from a coach)"},
                {"delay_days": 5, "template": "plan_pitch_direct", "subject": "Custom plan for your race — $249"},
                {"delay_days": 12, "template": "social_proof", "subject": "Why 90% of gravel DNFs are preventable"},
            ],
        },
    },
}
