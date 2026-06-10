"""Welcome sequence — new subscriber onboarding, anti-funnel posture.

Voice-true single track (June 2026 rewrite): assume familiarity, lead with
the work, pitch once at the end with permission to say no. Variant B is
kept (weight 0, same steps) so in-flight legacy-B enrollments keep working.
"""

_STEPS = [
    {"delay_days": 0, "template": "welcome_a", "subject": "what race are you scared of?"},
    {"delay_days": 3, "template": "fueling_mistake", "subject": "the biggest fueling mistake in gravel"},
    {"delay_days": 7, "template": "honest_ratings", "subject": "the race we gave a 36"},
    {"delay_days": 12, "template": "anti_pitch", "subject": "you probably don't need a coach"},
    # Post-pitch pure-value email — nothing for sale, keeps the relationship
    {"delay_days": 18, "template": "essay_sweet_spot", "subject": "sweet spot isn't that sweet"},
]

SEQUENCE = {
    "id": "welcome_v1",
    "name": "Welcome Sequence",
    "description": "New subscriber onboarding — one voice-true track: reply prompt, best essay, honesty flex, anti-pitch.",
    "trigger": "new_subscriber",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Anti-funnel", "steps": _STEPS},
        "B": {"weight": 0, "name": "Legacy slot (same steps)", "steps": _STEPS},
    },
}
