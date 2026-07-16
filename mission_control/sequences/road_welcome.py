"""Roadie Labs welcome sequence — new subscriber onboarding.

Friend-register rewrite (docs/specs/friend-register-copy-road.md, Jul 16) —
a single opener keyed to whatever context the capture gave us (guide
chapter / browsing trail / race page / anonymous, offseason-aware), plus
one optional day-10 follow-up. No pitch in the broadcast; replies are the
conversion engine. Deadpan register retained (clinical, zero profanity,
verdict sentences allowed).

ACTIVE — roadielabs.com verified in Resend Jul 2026 (DKIM/SPF/MX via
Cloudflare one-time authorization).
"""

_STEPS = [
    {"delay_days": 0, "template": "road_welcome_value", "subject": "which race?"},
    {"delay_days": 10, "template": "road_welcome_followup", "subject": "pick a race yet?"},
]

SEQUENCE = {
    "id": "road_welcome_v1",
    "name": "Roadie Labs Welcome",
    "brand": "roadielabs",
    "description": "New Roadie Labs subscriber onboarding — deadpan opener keyed to capture context.",
    "trigger": "new_subscriber",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Deadpan", "steps": _STEPS},
    },
}
