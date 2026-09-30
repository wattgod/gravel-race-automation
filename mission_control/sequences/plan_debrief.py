"""A plan buyer's race debrief (/race-debrief/ on gravelgodcycling.com and
roadielabs.com).

One transactional receipt and nothing after it: a debrief is not a lead and
never enters nurture. The trigger is listed in the engine's
_POST_PURCHASE_TRIGGERS, so the marketing guards (customer suppression, the
unsubscribe guard, the sales deal) neither drop the receipt nor open a deal.
Brand works the way the 2027 goals sequences do: one sequence per brand, so
a Roadie rider gets Roadie's sender and footer.

Not race_debrief_* (sequences/race_debrief.py), which is the post-race email
to leads.
"""

# DRAFT COPY: Matti's read pending before deploy (receipts spec §3.7: Matti writes every ask).
# The receipts, templates/emails/sequences/plan_debrief_receipt.html and
# road_plan_debrief_receipt.html, are draft too.
GG = {
    "id": "plan_debrief_v1",
    "name": "Race Debrief (Gravel God)",
    "description": "Receipt for a plan buyer's race debrief. Never nurture.",
    "trigger": "plan_debrief",
    "active": True,
    "variants": {"A": {"weight": 100, "name": "Receipt", "steps": [
        {"delay_days": 0, "template": "plan_debrief_receipt", "subject": "got it"},
    ]}},
}

ROAD = {
    **GG,
    "id": "road_plan_debrief_v1",
    "name": "Race Debrief (Roadie Labs)",
    "brand": "roadielabs",
    "variants": {"A": {"weight": 100, "name": "Receipt", "steps": [
        {"delay_days": 0, "template": "road_plan_debrief_receipt", "subject": "got it"},
    ]}},
}
