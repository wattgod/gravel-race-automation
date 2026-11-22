"""XC Ski Labs nurture — prep-kit leads (2026-11-22, copy DRAFT pending
Matti's read; docs/specs/friend-register-copy-xc.md).

Before this an xcskilabs prep_kit_gate lead matched no sequence and got no
email (logged lead_unrouted). One check-in on the kit, day 2, after the
day-0 receipt in xc_kit_delivery_v1. No Endure offer: Endure builds gravel,
road and mtb seasons only. No plan pitch.
"""

_STEPS = [
    {"delay_days": 2, "template": "xc_prep_checkin", "subject": "did the prep kit cover it?"},
]

SEQUENCE = {
    "id": "xc_nurture_v1",
    "name": "XC Lead Nurture",
    "brand": "xcskilabs",
    "description": "XC prep-kit leads — one check-in on the kit.",
    "trigger": "prep_kit_download",
    "active": True,
    "variants": {
        "A": {"weight": 100, "name": "Friend register", "steps": _STEPS},
    },
}
