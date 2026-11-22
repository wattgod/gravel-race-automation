"""Day-0 prep-kit delivery, isolated from legacy nurture enrollments.

This is a separate sequence instead of a new nurture step: existing nurture
rows at current_step 0 are waiting for the old day-2 check-in and would
otherwise receive a newly inserted step retroactively.

Roadie Labs variant B (2026-11-22, copy DRAFT pending Matti's read):
new enrollments get the receipt that promises up to three notes, to match
road_nurture_v1 variant B. Variant A stays defined, at weight 0, for any
receipt still pending.

XC Ski Labs (2026-11-22, copy DRAFT pending Matti's read): before this an
xcskilabs prep_kit_gate lead got no email at all (lead_unrouted). XC gets
the kit link here and one check-in in xc_nurture_v1; no Endure offer.
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
    "variants": {
        "A": {"weight": 0, "name": "Delivery, one note (retired, in-flight only)", "steps": [
            {"delay_days": 0, "template": "road_prep_kit_delivery", "subject": "your {race_name} prep kit"},
        ]},
        "B": {"weight": 100, "name": "Delivery, up to three notes", "steps": [
            {"delay_days": 0, "template": "road_prep_kit_delivery_notes", "subject": "your {race_name} prep kit"},
        ]},
    },
}

XC = {
    "id": "xc_kit_delivery_v1",
    "name": "Prep-kit Delivery (XC Ski Labs)",
    "brand": "xcskilabs",
    "description": "Immediate link receipt for XC prep_kit_gate enrollments only.",
    "trigger": "prep_kit_delivery",
    "active": True,
    "variants": {"A": {"weight": 100, "name": "Delivery", "steps": [
        {"delay_days": 0, "template": "xc_prep_kit_delivery", "subject": "your {race_name} prep kit"},
    ]}},
}
