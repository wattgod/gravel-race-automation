"""Triage service — surfaces what needs attention RIGHT NOW."""

import os
from datetime import date, datetime, timedelta, timezone

from mission_control import supabase_client as db


# ---------------------------------------------------------------------------
# ACTION REQUIRED — things that need Matti
# ---------------------------------------------------------------------------

def get_pending_intakes(limit: int = 20) -> list[dict]:
    """Plan requests awaiting processing."""
    return db.get_pending_plan_requests(limit=limit)


def get_unanswered_replies() -> list[dict]:
    """Inbound emails not yet acknowledged."""
    q = db._table("gg_communications").select("*, gg_athletes(name, slug)")
    q = q.eq("comm_type", "inbound").eq("status", "received")
    q = q.order("sent_at", desc=True).limit(20)
    result = q.execute()
    return result.data or []


def get_plans_needing_action() -> list[dict]:
    """Athletes whose plans need approval or delivery."""
    actionable = ["pipeline_complete", "audit_passed", "approved"]
    q = db._table("gg_athletes").select(
        "name, slug, email, race_name, race_date, plan_status, updated_at"
    )
    q = q.in_("plan_status", actionable)
    q = q.order("updated_at", desc=True).limit(20)
    result = q.execute()
    return result.data or []


def get_stale_deals(stale_hours: int = 48) -> list[dict]:
    """Deals in active stages with no update in stale_hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=stale_hours)).isoformat()
    active_stages = ["lead", "qualified", "proposal_sent"]
    q = db._table("gg_deals").select("*")
    q = q.in_("stage", active_stages).lt("updated_at", cutoff)
    q = q.order("updated_at").limit(20)
    result = q.execute()
    return result.data or []


def get_due_touchpoints() -> list[dict]:
    """Touchpoints due today or overdue."""
    return db.get_touchpoints(due_only=True, limit=20)


# ---------------------------------------------------------------------------
# AUTOMATED — FYI
# ---------------------------------------------------------------------------

def get_recent_sends(hours: int = 24) -> list[dict]:
    """Sequence emails sent in the last N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q = db._table("gg_sequence_sends").select(
        "*, gg_sequence_enrollments(contact_email, contact_name, sequence_id)"
    )
    q = q.gte("sent_at", cutoff).order("sent_at", desc=True).limit(50)
    result = q.execute()
    return result.data or []


def get_recent_enrollments(hours: int = 24) -> list[dict]:
    """New sequence enrollments in the last N hours."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    q = db._table("gg_sequence_enrollments").select("*")
    q = q.gte("enrolled_at", cutoff).order("enrolled_at", desc=True).limit(50)
    result = q.execute()
    return result.data or []


def get_upcoming_races(days: int = 30) -> list[dict]:
    """Athletes with races in the next N days."""
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=days)).isoformat()
    q = db._table("gg_athletes").select(
        "name, slug, race_name, race_date, tier, plan_status"
    )
    q = q.gte("race_date", today).lte("race_date", future)
    q = q.order("race_date").limit(20)
    result = q.execute()
    return result.data or []


def get_recent_bounces(days: int = 7) -> list[dict]:
    """Bounced emails in the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = db._table("gg_sequence_sends").select(
        "*, gg_sequence_enrollments(contact_email, contact_name, sequence_id)"
    )
    q = q.eq("status", "bounced").gte("sent_at", cutoff)
    q = q.order("sent_at", desc=True).limit(20)
    result = q.execute()
    return result.data or []


def get_recent_unsubscribes(days: int = 7) -> list[dict]:
    """Recent unsubscribes."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    q = db._table("gg_sequence_enrollments").select(
        "contact_email, contact_name, sequence_id, completed_at"
    )
    q = q.eq("status", "unsubscribed").gte("completed_at", cutoff)
    q = q.order("completed_at", desc=True).limit(20)
    result = q.execute()
    return result.data or []


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

    checks = [
        {
            "name": "Supabase",
            "status": "ok" if SUPABASE_URL else "error",
            "detail": "Connected" if SUPABASE_URL else "SUPABASE_URL not set",
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


def triage_summary() -> dict:
    """Quick counts for the triage header."""
    pending = len(db.get_pending_plan_requests(limit=100))
    unread = db.count_unread_inbound()
    plans = len(get_plans_needing_action())
    due_tp = db.count_due_touchpoints()

    return {
        "action_required": pending + unread + plans + due_tp,
        "pending_intakes": pending,
        "unread_replies": unread,
        "plans_needing_action": plans,
        "due_touchpoints": due_tp,
    }
