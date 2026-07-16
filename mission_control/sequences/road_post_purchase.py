"""Roadie Labs post-purchase sequence — onboarding after buying a road plan.

NOTE: plan_purchased enrollments must pass brand="roadielabs" at the
enrollment call site for road buyers to land here (the subscriber webhook
is brand-routed; verify the purchase-trigger path also carries brand).

ACTIVE — roadielabs.com verified in Resend Jul 2026.
"""

SEQUENCE = {
    "id": "road_post_purchase_v1",
    "name": "Roadie Labs Post-Purchase Onboarding",
    "brand": "roadielabs",
    "description": "After road plan purchase — onboarding, calibration check-ins, NPS.",
    "trigger": "plan_purchased",
    "active": True,
    "variants": {
        "A": {
            "weight": 100,
            "name": "Deadpan",
            "steps": [
                {"delay_days": 0, "template": "road_purchase_welcome", "subject": "questionnaire received"},
                {"delay_days": 3, "template": "road_week1", "subject": "how did the first rides feel?"},
                {"delay_days": 10, "template": "road_checkin_week2", "subject": "two weeks in"},
                {"delay_days": 21, "template": "road_progress_update", "subject": "the middle weeks"},
                {"delay_days": 42, "template": "road_nps_request", "subject": "did {race_name} happen?"},
            ],
        },
    },
}
