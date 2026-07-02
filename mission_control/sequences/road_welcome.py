"""Roadie Labs welcome sequence — new subscriber onboarding.

Deadpan register: study-breakdown skeleton, verdict sentences, zero
profanity, methodological transparency instead of self-deprecation.
Single track (list too small to A/B). Timing mirrors gravel welcome
(pitch day 7, single re-pitch day 10).

INACTIVE until roadielabs.com is verified as a sending domain in Resend
(DNS records). Flip "active" after verification — enrollment is already
brand-routed, so road leads queue nothing until then.
"""

_STEPS = [
    {"delay_days": 0, "template": "road_welcome_value", "subject": "what this is"},
    {"delay_days": 3, "template": "road_fueling_math", "subject": "how many carbs does a gran fondo actually take?"},
    {"delay_days": 5, "template": "road_honest_ratings", "subject": "the race we rated 44"},
    {"delay_days": 7, "template": "road_anti_pitch", "subject": "you probably don't need a training plan"},
    {"delay_days": 10, "template": "road_repitch", "subject": "the week-six problem"},
]

SEQUENCE = {
    "id": "road_welcome_v1",
    "name": "Roadie Labs Welcome",
    "brand": "roadielabs",
    "description": "New Roadie Labs subscriber onboarding — deadpan, data-first, single pitch.",
    "trigger": "new_subscriber",
    "active": False,
    "variants": {
        "A": {"weight": 100, "name": "Deadpan", "steps": _STEPS},
    },
}
