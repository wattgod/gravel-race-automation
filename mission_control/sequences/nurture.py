"""Nurture sequence — prep-kit / exit-intent leads.

Friend-register rewrite (docs/specs/friend-register-copy.md, Jul 16) — a
single check-in on the prep kit they downloaded. No pitch in the broadcast
(variant A). Variant B kept (weight 0, same steps) for in-flight legacy-B
enrollments.

Variant C — KIT PITCH PILOT (Matti, 2026-09-12): fresh prep-kit leads only
(race_name + race_slug guaranteed by the worker). A/B against A at 50/50.
One check-in that promises exactly one plan note and one follow-up, the
race-specific pitch at day 7, the follow-up at day 11, then done. Its
templates are its own (kit_*) so the shared anti_pitch/repitch promises
are never inherited. Steps are only ever APPENDED to C; A's list is not
touched (legacy current_step semantics, see webhooks.py).
"""

_STEPS = [
    {"delay_days": 2, "template": "race_prep_tips", "subject": "how'd the prep kit land?"},
]

_STEPS_PILOT = [
    {"delay_days": 2, "template": "kit_checkin_pilot", "subject": "how'd the {race_name} prep kit land?"},
    {"delay_days": 7, "template": "kit_pitch", "subject": "the plan, for {race_name}"},
    {"delay_days": 11, "template": "kit_followup", "subject": "week six"},
]

SEQUENCE = {
    "id": "nurture_v1",
    "name": "Lead Nurture",
    "description": "Prep-kit and exit-intent leads — one honest check-in on the kit; pilot arm adds one race-specific pitch + one follow-up.",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {"weight": 50, "name": "Anti-funnel", "steps": _STEPS},
        "B": {"weight": 0, "name": "Legacy slot (same steps)", "steps": _STEPS},
        "C": {"weight": 50, "name": "Kit pitch pilot", "steps": _STEPS_PILOT},
    },
}
