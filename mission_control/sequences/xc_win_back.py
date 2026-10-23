"""XC Ski Labs win-back — friend-register.

ACTIVE ONLY WHEN WIN_BACK_ENABLED is set (default off) — same flag and same
daily job (mission_control/services/win_back.py) as the Gravel God win-back.
xcskilabs.com is verified in Resend (see xc_welcome.py)."""

from mission_control.config import WIN_BACK_ENABLED

_STEPS = [
    {"delay_days": 0, "template": "xc_win_back", "subject": "did you end up skiing it?"},
]

SEQUENCE = {
    "id": "xc_win_back_v1",
    "name": "XC Win-back",
    "description": "Re-engage cold XC leads with a real question.",
    "trigger": "lead_cold_30d",
    "brand": "xcskilabs",
    "active": WIN_BACK_ENABLED,
    "variants": {
        "A": {"weight": 100, "name": "Friend register", "steps": _STEPS},
    },
}
