"""Win-back sequence — re-engage 30-day cold leads.

Friend-register rewrite (docs/specs/friend-register-copy.md, Jul 16) —
single low-pressure touch, no anti-pitch. Variant B kept (weight 0,
same steps) in case legacy-B enrollments exist when reactivated.

ACTIVE ONLY WHEN WIN_BACK_ENABLED is set (default off). Nothing enrolls
here from a webhook: the only thing that fires lead_cold_30d is the daily
job in mission_control/services/win_back.py, gated by the same flag.
"""

from mission_control.config import WIN_BACK_ENABLED

_STEPS = [
    {"delay_days": 0, "template": "win_back_value", "subject": "did you end up racing it?"},
]

SEQUENCE = {
    "id": "win_back_v1",
    "name": "Win-Back",
    "description": "Re-engage 30-day cold leads — one honest check-in.",
    "trigger": "lead_cold_30d",
    "active": WIN_BACK_ENABLED,
    "variants": {
        "A": {"weight": 100, "name": "Anti-funnel", "steps": _STEPS},
        "B": {"weight": 0, "name": "Legacy slot (same steps)", "steps": _STEPS},
    },
}
