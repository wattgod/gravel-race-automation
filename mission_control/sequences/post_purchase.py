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
                {"delay_days": 0, "template": "purchase_welcome", "subject": "got your questionnaire"},
                {"delay_days": 3, "template": "week1_tips", "subject": "how did the first rides feel?"},
                {"delay_days": 10, "template": "checkin_week2", "subject": "two weeks in — quick check"},
                {"delay_days": 21, "template": "progress_update", "subject": "the boring middle"},
                # Fires ~3 days after plan completion (length-aware), so it lands
                # alongside TP's own post-plan review prompt instead of mid-plan
                # for longer builds. delay_days=42 is the fallback used only when
                # source_data.plan_weeks isn't available (see sequence_engine's
                # _step_delay_days — DORMANT until the plan_purchased enrollment
                # path supplies plan_weeks; see webhooks.py trigger_map gap).
                {"delay_from_completion_days": 3, "delay_days": 42, "template": "nps_request", "subject": "did {race_name} happen?"},
            ],
        },
    },
}
