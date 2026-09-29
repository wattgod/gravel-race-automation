"""A coached athlete's exit survey (/coaching/exit/).

One transactional receipt and nothing after it: a leaving athlete is not a
lead and never enters nurture. The trigger is listed in the engine's
_POST_PURCHASE_TRIGGERS, so the marketing guards (customer suppression, the
unsubscribe guard, the sales deal) neither drop the receipt nor open a deal.
"""

# DRAFT COPY: Matti's read pending before deploy (receipts spec §3.7: Matti writes every ask).
# The receipt, templates/emails/sequences/athlete_exit_receipt.html, and the
# plain-English strings it fills in (services/athlete_exit.py) are draft too.
SEQUENCE = {
    "id": "athlete_exit_v1",
    "name": "Athlete Exit Survey (Gravel God)",
    "description": "Receipt for a leaving athlete's exit survey. Never nurture.",
    "trigger": "athlete_exit",
    "active": True,
    "variants": {"A": {"weight": 100, "name": "Receipt", "steps": [
        {"delay_days": 0, "template": "athlete_exit_receipt", "subject": "got it"},
    ]}},
}
