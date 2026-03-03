"""Triage service — surfaces what needs attention RIGHT NOW."""

import logging
import os
from datetime import date, datetime, timedelta, timezone

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
# SYSTEM HEALTH
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
