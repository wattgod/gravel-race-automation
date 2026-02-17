"""Supabase connection and query helpers for all gg_* tables."""

import re
import threading
from datetime import date, datetime, timezone
from typing import Any

from supabase import Client, create_client

from mission_control.config import SUPABASE_SERVICE_KEY, SUPABASE_URL

_client: Client | None = None
_client_lock = threading.Lock()


def get_client() -> Client:
    """Return the Supabase client singleton (thread-safe)."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                    raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
                _client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _client


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _table(name: str):
    """Return a table query builder."""
    return get_client().table(name)


def insert(table: str, data: dict) -> dict:
    """Insert a row and return it."""
    result = _table(table).insert(data).execute()
    return result.data[0] if result.data else {}


def upsert(table: str, data: dict, on_conflict: str = "") -> dict:
    """Upsert a row and return it."""
    if on_conflict:
        q = _table(table).upsert(data, on_conflict=on_conflict)
    else:
        q = _table(table).upsert(data)
    result = q.execute()
    return result.data[0] if result.data else {}


def update(table: str, data: dict, match: dict) -> dict:
    """Update rows matching conditions."""
    q = _table(table).update(data)
    for k, v in match.items():
        q = q.eq(k, v)
    result = q.execute()
    return result.data[0] if result.data else {}


def delete(table: str, match: dict) -> list:
    """Delete rows matching conditions."""
    q = _table(table).delete()
    for k, v in match.items():
        q = q.eq(k, v)
    result = q.execute()
    return result.data


def select(table: str, columns: str = "*", match: dict | None = None,
           order: str | None = None, order_desc: bool = False,
           limit: int | None = None, offset: int | None = None) -> list[dict]:
    """Select rows with optional filtering, ordering, and pagination."""
    q = _table(table).select(columns)
    if match:
        for k, v in match.items():
            q = q.eq(k, v)
    if order:
        q = q.order(order, desc=order_desc)
    if limit:
        q = q.limit(limit)
    if offset:
        q = q.range(offset, offset + (limit or 100) - 1)
    result = q.execute()
    return result.data or []


def select_one(table: str, columns: str = "*", match: dict | None = None) -> dict | None:
    """Select a single row."""
    rows = select(table, columns, match, limit=1)
    return rows[0] if rows else None


def count(table: str, match: dict | None = None) -> int:
    """Count rows matching conditions."""
    q = _table(table).select("*", count="exact")
    if match:
        for k, v in match.items():
            q = q.eq(k, v)
    result = q.execute()
    return result.count or 0


# ---------------------------------------------------------------------------
# Athletes
# ---------------------------------------------------------------------------

def get_athletes(status: str | None = None, search: str | None = None,
                 order: str = "created_at", limit: int = 50, offset: int = 0) -> list[dict]:
    """Get athletes with optional status filter and search."""
    q = _table("gg_athletes").select("*")
    if status:
        q = q.eq("plan_status", status)
    if search:
        safe = re.sub(r"[%,.()\[\]]", "", search)[:100]
        q = q.or_(f"name.ilike.%{safe}%,email.ilike.%{safe}%,race_name.ilike.%{safe}%")
    q = q.order(order, desc=True).range(offset, offset + limit - 1)
    result = q.execute()
    return result.data or []


def get_athlete(slug: str) -> dict | None:
    """Get a single athlete by slug."""
    return select_one("gg_athletes", match={"slug": slug})


def get_athlete_by_id(athlete_id: str) -> dict | None:
    """Get a single athlete by UUID."""
    return select_one("gg_athletes", match={"id": athlete_id})


def upsert_athlete(data: dict) -> dict:
    """Upsert an athlete by slug."""
    return upsert("gg_athletes", data, on_conflict="slug")


def update_athlete(slug: str, data: dict) -> dict:
    """Update an athlete by slug."""
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    return update("gg_athletes", data, {"slug": slug})


def count_athletes(status: str | None = None) -> int:
    """Count athletes with optional status filter."""
    match = {"plan_status": status} if status else None
    return count("gg_athletes", match)


# ---------------------------------------------------------------------------
# Pipeline Runs
# ---------------------------------------------------------------------------

def create_pipeline_run(athlete_id: str, run_type: str = "draft",
                        skip_pdf: bool = True, skip_deploy: bool = True,
                        skip_deliver: bool = True) -> dict:
    """Create a new pipeline run."""
    return insert("gg_pipeline_runs", {
        "athlete_id": athlete_id,
        "run_type": run_type,
        "status": "pending",
        "skip_pdf": skip_pdf,
        "skip_deploy": skip_deploy,
        "skip_deliver": skip_deliver,
    })


def update_pipeline_run(run_id: str, data: dict) -> dict:
    """Update a pipeline run."""
    return update("gg_pipeline_runs", data, {"id": run_id})


def get_pipeline_run(run_id: str) -> dict | None:
    """Get a pipeline run by ID."""
    return select_one("gg_pipeline_runs", match={"id": run_id})


def get_pipeline_runs(athlete_id: str | None = None, limit: int = 20) -> list[dict]:
    """Get recent pipeline runs, optionally for a specific athlete."""
    q = _table("gg_pipeline_runs").select("*, gg_athletes(name, slug)")
    if athlete_id:
        q = q.eq("athlete_id", athlete_id)
    q = q.order("started_at", desc=True).limit(limit)
    result = q.execute()
    return result.data or []


# ---------------------------------------------------------------------------
# Touchpoints
# ---------------------------------------------------------------------------

def get_touchpoints(athlete_id: str | None = None, category: str | None = None,
                    due_only: bool = False, limit: int = 200) -> list[dict]:
    """Get touchpoints with optional filters."""
    q = _table("gg_touchpoints").select("*, gg_athletes(name, slug, email)")
    if athlete_id:
        q = q.eq("athlete_id", athlete_id)
    if category:
        q = q.eq("category", category)
    if due_only:
        today = date.today().isoformat()
        q = q.lte("send_date", today).eq("sent", False)
    q = q.order("send_date").limit(limit)
    result = q.execute()
    return result.data or []


def upsert_touchpoint(data: dict) -> dict:
    """Upsert a touchpoint by (athlete_id, touchpoint_id)."""
    return upsert("gg_touchpoints", data, on_conflict="athlete_id,touchpoint_id")


def update_touchpoint(touchpoint_id: str, data: dict) -> dict:
    """Update a touchpoint by UUID."""
    return update("gg_touchpoints", data, {"id": touchpoint_id})


def count_due_touchpoints() -> int:
    """Count touchpoints due today or earlier that haven't been sent."""
    today = date.today().isoformat()
    q = _table("gg_touchpoints").select("*", count="exact").lte("send_date", today).eq("sent", False)
    result = q.execute()
    return result.count or 0


# ---------------------------------------------------------------------------
# Communications
# ---------------------------------------------------------------------------

def log_communication(athlete_id: str, comm_type: str, subject: str = "",
                      recipient: str = "", resend_id: str = "", status: str = "sent") -> dict:
    """Log an email send."""
    return insert("gg_communications", {
        "athlete_id": athlete_id,
        "comm_type": comm_type,
        "subject": subject,
        "recipient": recipient,
        "resend_id": resend_id,
        "status": status,
    })


def get_communications(athlete_id: str, limit: int = 50) -> list[dict]:
    """Get communications for an athlete."""
    return select("gg_communications", match={"athlete_id": athlete_id},
                  order="sent_at", order_desc=True, limit=limit)


# ---------------------------------------------------------------------------
# NPS Scores
# ---------------------------------------------------------------------------

def record_nps(athlete_id: str, score: int, comment: str = "", race_name: str = "") -> dict:
    """Record an NPS score."""
    return insert("gg_nps_scores", {
        "athlete_id": athlete_id,
        "score": score,
        "comment": comment,
        "race_name": race_name,
    })


def get_nps_scores(limit: int = 100) -> list[dict]:
    """Get all NPS scores."""
    return select("gg_nps_scores", columns="*, gg_athletes(name, slug)",
                  order="created_at", order_desc=True, limit=limit)


def get_nps_distribution() -> dict:
    """Get NPS score distribution (0-10)."""
    scores = select("gg_nps_scores", columns="score")
    dist = {i: 0 for i in range(11)}
    for s in scores:
        dist[s["score"]] = dist.get(s["score"], 0) + 1
    total = len(scores)
    if total == 0:
        return {"distribution": dist, "average": 0, "total": 0, "promoters": 0, "detractors": 0, "nps": 0}
    promoters = sum(1 for s in scores if s["score"] >= 9)
    detractors = sum(1 for s in scores if s["score"] <= 6)
    nps = round((promoters - detractors) / total * 100)
    avg = round(sum(s["score"] for s in scores) / total, 1)
    return {"distribution": dist, "average": avg, "total": total,
            "promoters": promoters, "detractors": detractors, "nps": nps}


# ---------------------------------------------------------------------------
# Referrals
# ---------------------------------------------------------------------------

def record_referral(referrer_id: str, referred_name: str, referred_email: str) -> dict:
    """Record a referral."""
    return insert("gg_referrals", {
        "referrer_id": referrer_id,
        "referred_name": referred_name,
        "referred_email": referred_email,
    })


def get_referrals(limit: int = 100) -> list[dict]:
    """Get all referrals."""
    return select("gg_referrals", columns="*, gg_athletes!referrer_id(name, slug)",
                  order="created_at", order_desc=True, limit=limit)


# ---------------------------------------------------------------------------
# Files
# ---------------------------------------------------------------------------

def record_file(athlete_id: str, file_type: str, storage_path: str,
                file_name: str, size_bytes: int = 0) -> dict:
    """Record a file upload."""
    return insert("gg_files", {
        "athlete_id": athlete_id,
        "file_type": file_type,
        "storage_path": storage_path,
        "file_name": file_name,
        "size_bytes": size_bytes,
    })


def get_files(athlete_id: str) -> list[dict]:
    """Get files for an athlete."""
    return select("gg_files", match={"athlete_id": athlete_id}, order="created_at")


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

def log_action(action: str, entity_type: str = "", entity_id: str = "", details: str = "") -> dict:
    """Log an operator action."""
    return insert("gg_audit_log", {
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": details,
    })


def get_audit_log(limit: int = 50) -> list[dict]:
    """Get recent audit log entries."""
    return select("gg_audit_log", order="created_at", order_desc=True, limit=limit)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def get_setting(key: str, default: str = "") -> str:
    """Get a setting value."""
    row = select_one("gg_settings", match={"key": key})
    return row["value"] if row else default


def set_setting(key: str, value: str) -> dict:
    """Set a setting value."""
    return upsert("gg_settings", {"key": key, "value": value}, on_conflict="key")


# ---------------------------------------------------------------------------
# Plan Requests (existing table)
# ---------------------------------------------------------------------------

def get_pending_plan_requests(limit: int = 20) -> list[dict]:
    """Get pending plan requests that haven't been processed yet."""
    return select("plan_requests", match={"status": "pending"},
                  order="created_at", order_desc=True, limit=limit)


def get_plan_request(request_id: str) -> dict | None:
    """Get a plan request by request_id."""
    return select_one("plan_requests", match={"request_id": request_id})


# ---------------------------------------------------------------------------
# Unread Communications (v2)
# ---------------------------------------------------------------------------

def count_unread_inbound() -> int:
    """Count inbound communications not yet acknowledged."""
    q = _table("gg_communications").select("*", count="exact")
    q = q.eq("comm_type", "inbound").eq("status", "received")
    result = q.execute()
    return result.count or 0
