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

DOCTRINE EXCEPTION (owner: Matti, 2026-09-12): docs/email-voice-model.md
says "No broadcast ever pitches" and scripts/friend_test.py --gate enforces
it — the gate FAILS kit_pitch and kit_followup by construction (friend 1/5,
"straight-faced sales pitch"). That is the hypothesis under test, not a
copy defect. Readout 2026-10-10 on plan-funnel entry_surface=email_nurture
(arrivals → starts → checkouts → purchases) and unsubscribes per step;
either C becomes the track or it goes to weight 0 and the exception ends.

race_premise "upcoming" (kit_pitch, kit_followup: both sell a plan for the race): right before a step sends, the engine re-checks it
against the race's current published date and skips the step, with an
audit-log entry, when it no longer holds (see
sequence_engine._race_premise_failure).

DECISION (Oct 2026, pending Matti's approval of the PR that set it): on prod
data the C kit check-in path outperformed A, so C becomes the track — new
prep_kit_download enrollments go to C only (A 0 / B 0 / C 100). A and B
stay defined, unchanged, so contacts already enrolled in them finish their
track (the engine stores the variant on the enrollment row and reads that
variant's steps on every send). The doctrine exception above is therefore
standing for this sequence until Matti says otherwise.

Variant D — KIT ENDURE OFFER (Matti, 2026-11-22; copy DRAFT pending his
read, docs/specs/friend-register-copy.md): new prep_kit_download
enrollments go to D only (A 0 / B 0 / C 0 / D 100). C keeps its steps,
unchanged, for contacts already enrolled in it. D swaps C's day-7 plan
pitch for an offer to build their season in Endure (link with the race
filled in, {endure_plan_url}) and its day-11 follow-up for one question
about what worries them. The day-7 step `requires` the Endure link: with no
link for the lead (no slug or name, a discipline Endure does not build)
or a failed race premise it is skipped and the sequence moves on to day 11
on its usual schedule (sequence_engine._step_requirement_failure). Whether
the doctrine exception above covers D's day-7 offer is Matti's call with
this draft.
"""

_STEPS = [
    {"delay_days": 2, "template": "race_prep_tips", "subject": "how'd the prep kit land?"},
]

_STEPS_PILOT = [
    {"delay_days": 2, "template": "kit_checkin_pilot", "subject": "how'd the prep kit land?"},
    {"delay_days": 7, "template": "kit_pitch", "subject": "the plan, for {race_name}", "race_premise": "upcoming"},
    {"delay_days": 11, "template": "kit_followup", "subject": "week six", "race_premise": "upcoming"},
]

_STEPS_ENDURE = [
    {"delay_days": 2, "template": "kit_checkin_pilot", "subject": "how'd the prep kit land?"},
    {"delay_days": 7, "template": "kit_endure_plan", "subject": "your {race_name} plan",
     "race_premise": "upcoming", "requires": "endure_plan_url"},
    {"delay_days": 11, "template": "kit_worry", "subject": "the part that worries you"},
]

SEQUENCE = {
    "id": "nurture_v1",
    "name": "Lead Nurture",
    "description": "Prep-kit leads — kit check-in, the Endure season offer, one question (variant D, 100%; C in flight).",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {"weight": 0, "name": "Anti-funnel (retired, in-flight only)", "steps": _STEPS},
        "B": {"weight": 0, "name": "Legacy slot (same steps)", "steps": _STEPS},
        "C": {"weight": 0, "name": "Kit pitch pilot (retired, in-flight only)", "steps": _STEPS_PILOT},
        "D": {"weight": 100, "name": "Kit Endure offer", "steps": _STEPS_ENDURE},
    },
}
