"""Roadie Labs nurture sequence — prep-kit / lead-magnet leads.

Friend-register rewrite (docs/specs/friend-register-copy-road.md, Jul 16) —
a single check-in on the prep notes they downloaded. No pitch in the
broadcast. Deadpan register retained.

ACTIVE — roadielabs.com verified in Resend Jul 2026.

Variant B — KIT ENDURE OFFER (Matti, 2026-11-22; copy DRAFT pending his
read): new enrollments go to B only (A 0 / B 100). A keeps its one step,
unchanged, for contacts already enrolled in it (the engine reads the
variant stored on the enrollment row). B appends, after the same day-2
check-in, a day-7 offer to build their season in Endure ({endure_plan_url},
race filled in) and a day-11 question. The day-7 step `requires` the
Endure link and declares race_premise "upcoming": with no link or a failed
premise it is skipped and the sequence moves on to day 11 on its usual
schedule. Its day-0 receipt (road_kit_delivery_v1 variant B) promises up to
three notes to match.
"""

_STEPS = [
    {"delay_days": 2, "template": "road_prep_variables", "subject": "did the prep notes cover it?"},
]

_STEPS_ENDURE = [
    {"delay_days": 2, "template": "road_prep_variables", "subject": "did the prep notes cover it?"},
    {"delay_days": 7, "template": "road_kit_endure_plan", "subject": "your {race_name} plan",
     "race_premise": "upcoming", "requires": "endure_plan_url"},
    {"delay_days": 11, "template": "road_kit_worry", "subject": "the part that worries you"},
]

SEQUENCE = {
    "id": "road_nurture_v1",
    "name": "Roadie Labs Lead Nurture",
    "brand": "roadielabs",
    "description": "Prep-kit leads — check-in, the Endure season offer, one question (B 100%; A in flight).",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {"weight": 0, "name": "Deadpan (retired, in-flight only)", "steps": _STEPS},
        "B": {"weight": 100, "name": "Kit Endure offer", "steps": _STEPS_ENDURE},
    },
}
