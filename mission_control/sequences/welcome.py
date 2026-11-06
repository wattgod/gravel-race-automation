"""Welcome sequence — new subscriber onboarding, anti-funnel posture.

Was an A/B test of two ENTIRELY different sequences (different subjects,
topics, register). Decided manually on prod data (Oct 2026, pending Matti's
approval of the PR that set it): A outperformed the Sober control, so new
enrollments now go to A only (A 100 / B 0). B is RETIRED, not deleted —
its steps and sober_* templates stay so contacts already enrolled in B
finish the track they started (the engine stores the variant on the
enrollment row and reads that variant's steps on every send).

A "Value-first": friend-register rewrite (docs/specs/friend-register-copy.md,
Jul 16) — a single opener keyed to whatever context the capture gave us
(guide chapter / browsing trail / race page / anonymous, offseason-aware),
plus one optional day-10 follow-up. No pitch in the broadcast; replies are
the conversion engine.
B "Sober": contract welcome, race three-act structure, how scoring works,
plain-spec pitch, breathing technique. Plain declarative register.
Copy unchanged (do not edit — in-flight B enrollments still receive it);
weight 0, so no new contact is assigned B.
"""

# Friend-register set (docs/specs/friend-register-copy.md) — the pitch-count
# promise machinery is gone with the removed pitch/repitch/essay steps.
_STEPS_A = [
    {"delay_days": 0, "template": "welcome_value", "subject": "getting ready for one of these?"},
    {"delay_days": 10, "template": "welcome_followup", "subject": "land on a race yet?"},
]

_STEPS_B = [
    {"delay_days": 0, "template": "sober_welcome", "subject": "what you signed up for"},
    {"delay_days": 3, "template": "sober_pacing", "subject": "how long races actually unfold"},
    {"delay_days": 5, "template": "sober_scoring", "subject": "what a 97 means"},
    {"delay_days": 7, "template": "sober_pitch", "subject": "the offer, stated plainly"},
    {"delay_days": 10, "template": "sober_repitch", "subject": "the follow-up, and then we're done"},
    {"delay_days": 17, "template": "sober_breathing", "subject": "a technique for the hard miles"},
]

SEQUENCE = {
    "id": "welcome_v1",
    "name": "Welcome Sequence",
    "description": "New subscriber onboarding — value-first (warm) track; sober (plain) control retired at weight 0.",
    "trigger": "new_subscriber",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Value-first", "steps": _STEPS_A},
        # Retired control: weight 0 keeps it out of _pick_variant for new
        # enrollments; the entry must stay for in-flight B rows.
        "B": {"weight": 0, "name": "Sober", "steps": _STEPS_B},
    },
}
