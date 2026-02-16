"""Deals service — deal CRUD + pipeline aggregation."""

from datetime import datetime, timezone

from mission_control import supabase_client as db


STAGES = ["lead", "qualified", "proposal_sent", "closed_won", "closed_lost"]


def create_deal(
    email: str,
    name: str = "",
    race_name: str = "",
    race_slug: str = "",
    source: str = "",
    value: float = 249.00,
) -> dict:
    """Create a new deal at lead stage."""
    deal = db.insert("gg_deals", {
        "contact_email": email,
        "contact_name": name,
        "race_name": race_name,
        "race_slug": race_slug,
        "source": source,
        "value": value,
        "stage": "lead",
    })

    db.log_action("deal_created", "deal", str(deal.get("id", "")),
                  f"New deal: {name} ({email}) — {race_name}")
    return deal


def move_stage(deal_id: str, new_stage: str) -> dict | None:
    """Move a deal to a new stage."""
    if new_stage not in STAGES:
        return None

    updates = {
        "stage": new_stage,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if new_stage in ("closed_won", "closed_lost"):
        updates["closed_at"] = datetime.now(timezone.utc).isoformat()

    deal = db.update("gg_deals", updates, {"id": deal_id})

    db.log_action("deal_stage_change", "deal", deal_id, f"Moved to {new_stage}")
    return deal


def get_deal(deal_id: str) -> dict | None:
    """Get a single deal by ID."""
    return db.select_one("gg_deals", match={"id": deal_id})


def get_deals(stage: str | None = None, limit: int = 100) -> list[dict]:
    """Get deals, optionally filtered by stage."""
    match = {"stage": stage} if stage else None
    return db.select("gg_deals", match=match, order="created_at", order_desc=True, limit=limit)


def pipeline_summary() -> dict:
    """Get deal count and total value by stage."""
    deals = db.select("gg_deals")
    summary = {}
    for stage in STAGES:
        stage_deals = [d for d in deals if d["stage"] == stage]
        summary[stage] = {
            "count": len(stage_deals),
            "value": sum(float(d.get("value", 0)) for d in stage_deals),
        }
    return summary


def update_deal(deal_id: str, data: dict) -> dict:
    """Update deal fields."""
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    return db.update("gg_deals", data, {"id": deal_id})


def link_athlete(deal_id: str, athlete_id: str) -> dict:
    """Link a deal to an athlete."""
    return update_deal(deal_id, {"athlete_id": athlete_id})
