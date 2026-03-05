"""Triage service — surfaces what needs attention RIGHT NOW."""

import logging
import os
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from mission_control import supabase_client as db

logger = logging.getLogger(__name__)

# Exported constant so template and tests can reference it
STALE_DEAL_HOURS = 48


# ---------------------------------------------------------------------------
# ACTION REQUIRED — things that need Matti
# ---------------------------------------------------------------------------

def get_pending_intakes(limit: int = 20) -> list[dict]:
    """Plan requests awaiting processing."""
    try:
        return db.get_pending_plan_requests(limit=limit)
    except Exception:
        logger.exception("Failed to fetch pending intakes")
        return []


def get_unanswered_replies() -> list[dict]:
    """Inbound emails not yet acknowledged."""
    try:
        q = db._table("gg_communications").select("*, gg_athletes(name, slug)")
        q = q.eq("comm_type", "inbound").eq("status", "received")
        q = q.order("sent_at", desc=True).limit(20)
        result = q.execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to fetch unanswered replies")
        return []


def get_plans_needing_action() -> list[dict]:
    """Athletes whose plans need approval or delivery."""
    try:
        actionable = ["pipeline_complete", "audit_passed", "approved"]
        q = db._table("gg_athletes").select(
            "name, slug, email, race_name, race_date, plan_status, updated_at"
        )
        q = q.in_("plan_status", actionable)
        q = q.order("updated_at", desc=True).limit(20)
        result = q.execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to fetch plans needing action")
        return []


def get_stale_deals(stale_hours: int = STALE_DEAL_HOURS) -> list[dict]:
    """Deals in active stages with no update in stale_hours."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=stale_hours)).isoformat()
        active_stages = ["lead", "qualified", "proposal_sent"]
        q = db._table("gg_deals").select("*")
        q = q.in_("stage", active_stages).lt("updated_at", cutoff)
        q = q.order("updated_at").limit(20)
        result = q.execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to fetch stale deals")
        return []


def get_due_touchpoints() -> list[dict]:
    """Touchpoints due today or overdue."""
    try:
        return db.get_touchpoints(due_only=True, limit=20)
    except Exception:
        logger.exception("Failed to fetch due touchpoints")
        return []


# ---------------------------------------------------------------------------
# INLINE ACTIONS — approve plans, mark touchpoints sent
# ---------------------------------------------------------------------------

def approve_plan(slug: str) -> dict | None:
    """Approve a plan (pipeline_complete or audit_passed → approved).

    Returns the updated athlete dict, or None if not found/not approvable.
    """
    try:
        athlete = db.select_one("gg_athletes", match={"slug": slug})
        if not athlete:
            return None
        if athlete.get("plan_status") not in ("pipeline_complete", "audit_passed"):
            return None

        updated = db.update(
            "gg_athletes",
            {
                "plan_status": "approved",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            {"slug": slug},
        )

        db.log_action(
            "plan_approved",
            entity_type="athlete",
            entity_id=str(athlete.get("id", "")),
            details=f"Approved plan for {slug}",
        )

        return updated if updated else athlete
    except Exception:
        logger.exception("Failed to approve plan for %s", slug)
        return None


def mark_touchpoint_sent(tp_id: str) -> dict | None:
    """Mark a touchpoint as sent. Returns the touchpoint, or None if not found."""
    try:
        existing = db.select_one("gg_touchpoints", match={"id": tp_id})
        if not existing:
            return None

        db.update("gg_touchpoints", {"sent": True}, {"id": tp_id})

        db.log_action(
            "touchpoint_marked_sent",
            entity_type="touchpoint",
            entity_id=tp_id,
        )

        return existing
    except Exception:
        logger.exception("Failed to mark touchpoint %s as sent", tp_id)
        return None


# ---------------------------------------------------------------------------
# AUTOMATED — FYI
# ---------------------------------------------------------------------------

def get_recent_sends(hours: int = 24) -> list[dict]:
    """Sequence emails sent in the last N hours."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        q = db._table("gg_sequence_sends").select(
            "*, gg_sequence_enrollments(contact_email, contact_name, sequence_id)"
        )
        q = q.gte("sent_at", cutoff).order("sent_at", desc=True).limit(50)
        result = q.execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to fetch recent sends")
        return []


def get_recent_enrollments(hours: int = 24) -> list[dict]:
    """New sequence enrollments in the last N hours."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        q = db._table("gg_sequence_enrollments").select("*")
        q = q.gte("enrolled_at", cutoff).order("enrolled_at", desc=True).limit(50)
        result = q.execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to fetch recent enrollments")
        return []


def get_upcoming_races(days: int = 30) -> list[dict]:
    """Athletes with races in the next N days."""
    try:
        today = date.today().isoformat()
        future = (date.today() + timedelta(days=days)).isoformat()
        q = db._table("gg_athletes").select(
            "name, slug, race_name, race_date, tier, plan_status"
        )
        q = q.gte("race_date", today).lte("race_date", future)
        q = q.order("race_date").limit(20)
        result = q.execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to fetch upcoming races")
        return []


def get_recent_bounces(days: int = 7) -> list[dict]:
    """Bounced emails in the last N days."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q = db._table("gg_sequence_sends").select(
            "*, gg_sequence_enrollments(contact_email, contact_name, sequence_id)"
        )
        q = q.eq("status", "bounced").gte("sent_at", cutoff)
        q = q.order("sent_at", desc=True).limit(20)
        result = q.execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to fetch recent bounces")
        return []


def get_recent_unsubscribes(days: int = 7) -> list[dict]:
    """Recent unsubscribes."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        q = db._table("gg_sequence_enrollments").select(
            "contact_email, contact_name, sequence_id, completed_at"
        )
        q = q.eq("status", "unsubscribed").gte("completed_at", cutoff)
        q = q.order("completed_at", desc=True).limit(20)
        result = q.execute()
        return result.data or []
    except Exception:
        logger.exception("Failed to fetch recent unsubscribes")
        return []


# ---------------------------------------------------------------------------
# SYSTEM HEALTH — basic (fast, loads with page)
# ---------------------------------------------------------------------------

def get_system_health() -> dict:
    """Check system health indicators."""
    from mission_control.config import (
        RESEND_API_KEY,
        SUPABASE_URL,
    )
    stripe_key = os.environ.get("STRIPE_API_KEY", "") or os.environ.get("STRIPE_SECRET_KEY", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")

    # Real DB connectivity check
    db_ok = False
    db_detail = "SUPABASE_URL not set"
    if SUPABASE_URL:
        try:
            db._table("gg_athletes").select("id", count="exact").limit(1).execute()
            db_ok = True
            db_detail = "Connected"
        except Exception as e:
            db_detail = f"Connection failed: {e}"

    checks = [
        {
            "name": "Supabase",
            "status": "ok" if db_ok else "error",
            "detail": db_detail,
        },
        {
            "name": "Resend (Email)",
            "status": "ok" if RESEND_API_KEY else "error",
            "detail": "API key configured" if RESEND_API_KEY else "RESEND_API_KEY not set",
        },
        {
            "name": "Stripe",
            "status": "ok" if stripe_key else "warning",
            "detail": "API key configured" if stripe_key else "STRIPE_API_KEY not set",
        },
        {
            "name": "SMTP (Notifications)",
            "status": "ok" if smtp_pass else "warning",
            "detail": "Configured" if smtp_pass else "SMTP_PASS not set — order notifications disabled",
        },
    ]

    return {
        "checks": checks,
        "ok_count": sum(1 for c in checks if c["status"] == "ok"),
        "warning_count": sum(1 for c in checks if c["status"] == "warning"),
        "error_count": sum(1 for c in checks if c["status"] == "error"),
    }


# ---------------------------------------------------------------------------
# SYSTEM HEALTH — expanded (deep checks, lazy-loaded)
# ---------------------------------------------------------------------------

# All env vars to check
_REQUIRED_ENV_VARS = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "WEBHOOK_SECRET", "RESEND_API_KEY"]
_OPTIONAL_ENV_VARS = [
    "STRIPE_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
    "SMTP_PASS", "GA4_PROPERTY_ID", "GA4_CREDENTIALS_PATH",
    "PUBLIC_URL", "SEQUENCE_FROM_EMAIL", "REPLY_TO_EMAIL",
]


def get_expanded_health() -> dict:
    """Run all deep health checks. Returns structured results."""
    checks = []

    # Env vars
    checks.extend(_check_env_vars())

    # Supabase tables
    checks.extend(_check_supabase_tables())

    # Self-health (HTTP ping)
    checks.append(_check_self_health())

    # Resend connectivity
    checks.append(_check_resend_connectivity())

    ok = sum(1 for c in checks if c["status"] == "ok")
    warn = sum(1 for c in checks if c["status"] == "warning")
    err = sum(1 for c in checks if c["status"] == "error")

    return {"checks": checks, "ok_count": ok, "warning_count": warn, "error_count": err}


def _check_env_vars() -> list[dict]:
    """Check all known config env vars."""
    results = []
    for var in _REQUIRED_ENV_VARS:
        val = os.environ.get(var, "")
        results.append({
            "name": f"ENV: {var}",
            "status": "ok" if val else "error",
            "detail": "Set" if val else "MISSING (required)",
        })
    for var in _OPTIONAL_ENV_VARS:
        val = os.environ.get(var, "")
        results.append({
            "name": f"ENV: {var}",
            "status": "ok" if val else "warning",
            "detail": "Set" if val else "Not set (optional)",
        })
    return results


def _check_supabase_tables() -> list[dict]:
    """Verify key Supabase tables exist and have data."""
    tables = ["gg_deals", "gg_athletes", "gg_sequence_enrollments"]
    results = []
    for table_name in tables:
        try:
            result = db._table(table_name).select("id", count="exact").limit(1).execute()
            row_count = result.count if result.count is not None else len(result.data or [])
            results.append({
                "name": f"Table: {table_name}",
                "status": "ok" if row_count > 0 else "warning",
                "detail": f"{row_count} rows" if row_count > 0 else "Empty",
            })
        except Exception as e:
            results.append({
                "name": f"Table: {table_name}",
                "status": "error",
                "detail": f"Query failed: {e}",
            })
    return results


def _check_self_health() -> dict:
    """HTTP GET to PUBLIC_URL/health to verify the service is reachable."""
    from mission_control.config import PUBLIC_URL

    if not PUBLIC_URL:
        return {"name": "Self-ping", "status": "warning", "detail": "PUBLIC_URL not set"}

    try:
        import httpx
        resp = httpx.get(f"{PUBLIC_URL}/health", timeout=5.0)
        if resp.status_code == 200:
            return {"name": "Self-ping", "status": "ok", "detail": f"Reachable ({resp.status_code})"}
        return {"name": "Self-ping", "status": "warning", "detail": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"name": "Self-ping", "status": "error", "detail": f"Unreachable: {e}"}


def _check_resend_connectivity() -> dict:
    """GET https://api.resend.com/domains with API key to verify connectivity."""
    from mission_control.config import RESEND_API_KEY

    if not RESEND_API_KEY:
        return {"name": "Resend API", "status": "error", "detail": "No API key"}

    try:
        import httpx
        resp = httpx.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            timeout=5.0,
        )
        if resp.status_code == 200:
            return {"name": "Resend API", "status": "ok", "detail": "Connected"}
        return {"name": "Resend API", "status": "error", "detail": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"name": "Resend API", "status": "error", "detail": f"Connection failed: {e}"}


# ---------------------------------------------------------------------------
# TRIAGE SUMMARY
# ---------------------------------------------------------------------------

def triage_summary(
    pending_intakes: list[dict] | None = None,
    plans_needing_action: list[dict] | None = None,
) -> dict:
    """Quick counts for the triage header.

    Accepts pre-computed lists to avoid duplicate queries when the router
    has already fetched them.
    """
    try:
        pending = len(pending_intakes) if pending_intakes is not None else len(db.get_pending_plan_requests(limit=100))
        unread = db.count_unread_inbound()
        plans = len(plans_needing_action) if plans_needing_action is not None else len(get_plans_needing_action())
        due_tp = db.count_due_touchpoints()

        return {
            "action_required": pending + unread + plans + due_tp,
            "pending_intakes": pending,
            "unread_replies": unread,
            "plans_needing_action": plans,
            "due_touchpoints": due_tp,
        }
    except Exception:
        logger.exception("Failed to compute triage summary")
        return {
            "action_required": 0,
            "pending_intakes": 0,
            "unread_replies": 0,
            "plans_needing_action": 0,
            "due_touchpoints": 0,
        }


# ---------------------------------------------------------------------------
# GA4 ANALYTICS SNAPSHOT
# ---------------------------------------------------------------------------

def get_triage_ga4_summary() -> dict:
    """GA4 snapshot for triage — sessions, conversions, top source."""
    try:
        from mission_control.services.ga4 import (
            get_conversion_events,
            get_daily_sessions,
            get_traffic_sources,
        )
        daily = get_daily_sessions(days=7)
        conversions = get_conversion_events(days=7)
        sources = get_traffic_sources(days=7)

        sessions_7d = sum(d["sessions"] for d in daily) if daily else 0
        total_conversions = sum(e["count"] for e in conversions) if conversions else 0
        top_source = sources[0]["channel"] if sources else None
        top_source_sessions = sources[0]["sessions"] if sources else 0

        plan_requests = next((e["count"] for e in conversions if e["event"] == "plan_request"), 0)
        email_captures = next((e["count"] for e in conversions if e["event"] == "email_capture"), 0)

        return {
            "configured": True,
            "sessions_7d": sessions_7d,
            "total_conversions": total_conversions,
            "plan_requests": plan_requests,
            "email_captures": email_captures,
            "top_source": top_source,
            "top_source_sessions": top_source_sessions,
            "conversions": conversions,
        }
    except Exception:
        logger.exception("Failed to fetch GA4 triage summary")
        return {"configured": False}


# ---------------------------------------------------------------------------
# API COST TRACKING
# ---------------------------------------------------------------------------

API_PRICING = {
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
    "sonar-pro": {"input": 3.00, "output": 15.00},
    "sonar": {"input": 1.00, "output": 1.00},
}


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost in USD for a given model and token counts."""
    pricing = API_PRICING.get(model)
    if not pricing:
        return 0.0
    cost_in = (tokens_in / 1_000_000) * pricing["input"]
    cost_out = (tokens_out / 1_000_000) * pricing["output"]
    return round(cost_in + cost_out, 6)


def get_api_cost_summary() -> dict:
    """Get API cost summary for the triage widget.

    Returns {configured, today, week, month, total, by_model} or {configured: False}.
    """
    try:
        # Check if table exists by querying it
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        week_start = (now - timedelta(days=7)).isoformat()
        month_start = (now - timedelta(days=30)).isoformat()

        # Get all records (for small table this is fine)
        q = db._table("gg_api_usage").select("*")
        result = q.execute()
        rows = result.data or []

        if not rows:
            return {
                "configured": True,
                "today": 0.0,
                "week": 0.0,
                "month": 0.0,
                "total": 0.0,
                "by_model": {},
            }

        today_cost = 0.0
        week_cost = 0.0
        month_cost = 0.0
        total_cost = 0.0
        by_model: dict[str, float] = {}

        for row in rows:
            cost = float(row.get("cost_usd", 0))
            model = row.get("model", "unknown")
            created = row.get("created_at", "")

            total_cost += cost
            by_model[model] = by_model.get(model, 0.0) + cost

            if created >= today_start:
                today_cost += cost
            if created >= week_start:
                week_cost += cost
            if created >= month_start:
                month_cost += cost

        return {
            "configured": True,
            "today": round(today_cost, 4),
            "week": round(week_cost, 4),
            "month": round(month_cost, 4),
            "total": round(total_cost, 4),
            "by_model": {k: round(v, 4) for k, v in by_model.items()},
        }
    except Exception:
        logger.debug("gg_api_usage table not available — cost tracking disabled")
        return {"configured": False}
