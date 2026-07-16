"""Win-back sequence — re-engage 30-day cold leads. Currently inactive.

Friend-register rewrite (docs/specs/friend-register-copy.md, Jul 16) —
single low-pressure touch, no anti-pitch. Variant B kept (weight 0,
same steps) in case legacy-B enrollments exist when reactivated.
"""

_STEPS = [
    {"delay_days": 0, "template": "win_back_value", "subject": "did you end up racing it?"},
]

SEQUENCE = {
    "id": "win_back_v1",
    "name": "Win-Back",
    "description": "Re-engage 30-day cold leads — one honest check-in.",
    "trigger": "lead_cold_30d",
    "active": False,
    "variants": {
        "A": {"weight": 100, "name": "Anti-funnel", "steps": _STEPS},
        "B": {"weight": 0, "name": "Legacy slot (same steps)", "steps": _STEPS},
    },
}
