"""XC Ski Labs win-back — friend-register. INACTIVE until Resend domain
verified AND the cold-lead trigger fires for the brand."""

_STEPS = [
    {"delay_days": 0, "template": "xc_win_back", "subject": "did you end up skiing it?"},
]

SEQUENCE = {
    "id": "xc_win_back_v1",
    "name": "XC Win-back",
    "description": "Re-engage cold XC leads with a real question.",
    "trigger": "lead_cold_30d",
    "brand": "xcskilabs",
    "active": False,
    "variants": {
        "A": {"weight": 100, "name": "Friend register", "steps": _STEPS},
    },
}
