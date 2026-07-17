"""XC Ski Labs welcome — friend-register, deadpan-warm skin.

ACTIVE — xcskilabs.com verified in Resend Jul 17 2026 (DKIM/SPF via
SiteGround DNS). Copy: docs/specs/friend-register-copy-xc.md. Season inversion:
XC offseason = Apr-Oct (webhook computes the flag per-brand).
"""

_STEPS = [
    {"delay_days": 0, "template": "xc_welcome_value", "subject": "which race?"},
    {"delay_days": 10, "template": "xc_welcome_followup", "subject": "pick a race yet?"},
]

SEQUENCE = {
    "id": "xc_welcome_v1",
    "name": "XC Welcome",
    "description": "New XC Ski Labs subscriber — context-aware friend opener.",
    "trigger": "new_subscriber",
    "brand": "xcskilabs",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Friend register", "steps": _STEPS},
    },
}
