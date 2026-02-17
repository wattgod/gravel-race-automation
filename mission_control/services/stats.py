"""Dashboard aggregation queries — Supabase."""

from datetime import date

from mission_control import supabase_client as db


def dashboard_stats() -> dict:
    """Return stats for the main dashboard."""
    total_athletes = db.count("gg_athletes")
    # Count specific statuses
    active_statuses = ["intake_received", "pipeline_running", "pipeline_complete", "audit_passed", "approved"]
    active_count = 0
    for s in active_statuses:
        active_count += db.count("gg_athletes", {"plan_status": s})

    delivered = db.count("gg_athletes", {"plan_status": "delivered"})
    due_touchpoints = db.count_due_touchpoints()

    all_tp = db.count("gg_touchpoints")
    sent_tp = db.count("gg_touchpoints", {"sent": True})

    nps_data = db.get_nps_distribution()

    referral_count = db.count("gg_referrals")

    return {
        "total_athletes": total_athletes,
        "active_plans": active_count,
        "delivered": delivered,
        "due_touchpoints": due_touchpoints,
        "total_touchpoints": all_tp,
        "sent_touchpoints": sent_tp,
        "nps_avg": nps_data["average"] if nps_data["total"] > 0 else None,
        "nps_count": nps_data["total"],
        "nps_score": nps_data["nps"],
        "referral_count": referral_count,
    }


def upcoming_races(limit: int = 10) -> list[dict]:
    """Return athletes with upcoming races, sorted by race_date."""
    today = date.today().isoformat()
    q = db._table("gg_athletes").select("name, slug, race_name, race_date, tier, level, plan_status")
    q = q.gte("race_date", today).order("race_date").limit(limit)
    result = q.execute()
    return result.data or []


def recent_pipeline_runs(limit: int = 10) -> list[dict]:
    """Return recent pipeline runs with athlete name."""
    return db.get_pipeline_runs(limit=limit)


def tier_breakdown() -> list[dict]:
    """Count athletes per tier."""
    athletes = db.select("gg_athletes", columns="tier")
    counts = {}
    for a in athletes:
        t = a.get("tier") or "unknown"
        counts[t] = counts.get(t, 0) + 1
    return [{"tier": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]


def level_breakdown() -> list[dict]:
    """Count athletes per level."""
    athletes = db.select("gg_athletes", columns="level")
    counts = {}
    for a in athletes:
        lvl = a.get("level") or "unknown"
        counts[lvl] = counts.get(lvl, 0) + 1
    return [{"level": k, "count": v} for k, v in sorted(counts.items(), key=lambda x: -x[1])]
