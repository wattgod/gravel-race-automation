"""Post-purchase sequence — onboarding + value reinforcement after buying a plan."""

SEQUENCE = {
    "id": "post_purchase_v1",
    "name": "Post-Purchase Onboarding",
    "description": "After plan purchase — onboarding flow, value reinforcement, NPS request.",
    "trigger": "plan_purchased",
    "active": True,
    "variants": {
        "A": {
            "weight": 100,
            "name": "Standard",
            "steps": [
                {"delay_days": 0, "template": "purchase_welcome", "subject": "your plan is being built (here's the deal)"},
                {"delay_days": 3, "template": "week1_tips", "subject": "week 1: do less than you want to"},
                {"delay_days": 10, "template": "checkin_week2", "subject": "two weeks in — three questions"},
                {"delay_days": 21, "template": "progress_update", "subject": "welcome to the boring middle"},
                {"delay_days": 42, "template": "nps_request", "subject": "one number, honestly"},
            ],
        },
    },
}
