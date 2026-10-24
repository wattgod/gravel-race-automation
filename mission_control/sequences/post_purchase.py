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
                # A TrainingPeaks store buyer (source "trainingpeaks_store",
                # services/tp_store_sales.py) has the plan the moment they pay,
                # so "got your questionnaire ... inside 24 hours" is false for
                # them, and they pick their own start date in TP, so later steps
                # can't assume the plan began at purchase (or that there's a
                # race: base plans have none). sequence_engine._resolve_step
                # swaps template + subject; timing stays shared.
                {"delay_days": 0, "template": "purchase_welcome", "subject": "got your questionnaire",
                 "source_overrides": {
                     "trainingpeaks_store": {
                         "template": "tp_purchase_welcome",
                         "subject": "did the plan land on your calendar?",
                     },
                 }},
                {"delay_days": 3, "template": "week1_tips", "subject": "how did the first rides feel?",
                 "source_overrides": {
                     "trainingpeaks_store": {
                         "template": "tp_week1_check",
                         "subject": "started yet?",
                     },
                 }},
                {"delay_days": 10, "template": "checkin_week2", "subject": "two weeks in — quick check",
                 "source_overrides": {
                     "trainingpeaks_store": {
                         "template": "tp_checkin",
                         "subject": "is the schedule surviving your week?",
                     },
                 }},
                {"delay_days": 21, "template": "progress_update", "subject": "the boring middle",
                 "source_overrides": {
                     "trainingpeaks_store": {
                         "template": "tp_progress",
                         "subject": "the easy weeks",
                     },
                 }},
                # Fires ~3 days after plan completion (length-aware), so it lands
                # alongside TP's own post-plan review prompt instead of mid-plan
                # for longer builds. delay_days=42 is the fallback used only when
                # source_data.plan_weeks isn't available (see sequence_engine's
                # _step_delay_days — DORMANT until the plan_purchased enrollment
                # path supplies plan_weeks; see webhooks.py trigger_map gap).
                # race_premise "passed": skipped at send time, audit-logged,
                # unless the race has happened (_race_premise_failure).
                {"delay_from_completion_days": 3, "delay_days": 42, "template": "nps_request", "subject": "did {race_name} happen?", "race_premise": "passed",
                 "source_overrides": {
                     "trainingpeaks_store": {
                         "template": "tp_nps",
                         "subject": "how's the plan treating you?",
                         # tp_nps makes no race claim; base plans have no race.
                         "race_premise": None,
                     },
                 }},
            ],
        },
    },
}
