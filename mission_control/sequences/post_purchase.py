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
                {"delay_days": 0, "template": "purchase_welcome", "subject": "Your training plan is ready"},
                {"delay_days": 3, "template": "week1_tips", "subject": "Week 1: What to expect"},
                {"delay_days": 10, "template": "checkin_week2", "subject": "How's the first week going?"},
                {"delay_days": 21, "template": "progress_update", "subject": "3 weeks in — here's what's happening"},
                {"delay_days": 42, "template": "nps_request", "subject": "Quick question about your plan"},
            ],
        },
    },
}
