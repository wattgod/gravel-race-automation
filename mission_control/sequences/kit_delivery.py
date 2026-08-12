"""Day-0 prep-kit delivery, isolated from legacy nurture enrollments.

This is a separate sequence instead of a new nurture step: existing nurture
rows at current_step 0 are waiting for the old day-2 check-in and would
otherwise receive a newly inserted step retroactively.
"""

GG = {
    "id": "kit_delivery_v1",
    "name": "Prep-kit Delivery (Gravel God)",
    "description": "Immediate link receipt for prep_kit_gate enrollments only.",
    "trigger": "prep_kit_delivery",
    "active": True,
    "variants": {"A": {"weight": 100, "name": "Delivery", "steps": [
        {"delay_days": 0, "template": "prep_kit_delivery", "subject": "your {race_name} prep kit"},
    ]}},
}

ROAD = {
    "id": "road_kit_delivery_v1",
    "name": "Prep-kit Delivery (Roadie Labs)",
    "brand": "roadielabs",
    "description": "Immediate link receipt for Roadie prep_kit_gate enrollments only.",
    "trigger": "prep_kit_delivery",
    "active": True,
    "variants": {"A": {"weight": 100, "name": "Delivery", "steps": [
        {"delay_days": 0, "template": "road_prep_kit_delivery", "subject": "your {race_name} prep kit"},
    ]}},
}
