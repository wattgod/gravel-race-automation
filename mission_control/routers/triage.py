"""Triage route — GET /triage (command center), POST /triage/ack."""

import logging
import re
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control import supabase_client as db
from mission_control.config import WEB_TEMPLATES_DIR
from mission_control.services.triage import (
    STALE_DEAL_HOURS,
    get_due_touchpoints,
    get_pending_intakes,
    get_plans_needing_action,
    get_recent_bounces,
    get_recent_enrollments,
    get_recent_sends,
    get_recent_unsubscribes,
    get_stale_deals,
    get_system_health,
    get_triage_ga4_summary,
    get_unanswered_replies,
    get_upcoming_races,
    triage_summary,
)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))

# UUID validation
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Rate limiting (same pattern as webhooks.py)
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 10
_RATE_WINDOW = 60


def _check_rate_limit(request: Request) -> None:
    """Raise 429 if IP exceeds rate limit. Simple sliding window."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    cutoff = now - _RATE_WINDOW
    _rate_buckets[ip] = bucket = [t for t in bucket if t > cutoff]
    if len(bucket) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


@router.get("/triage")
async def triage(request: Request):
    load_error = False
    try:
        # Action required
        pending_intakes = get_pending_intakes()
        unanswered_replies = get_unanswered_replies()
        plans = get_plans_needing_action()
        stale_deals = get_stale_deals()
        due_touchpoints = get_due_touchpoints()

        # Automated FYI
        recent_sends = get_recent_sends()
        recent_enrollments = get_recent_enrollments()
        upcoming_races = get_upcoming_races()
        recent_bounces = get_recent_bounces()
        recent_unsubscribes = get_recent_unsubscribes()

        # System health
        health = get_system_health()
        summary = triage_summary(
            pending_intakes=pending_intakes,
            plans_needing_action=plans,
        )

        # GA4
        ga4 = get_triage_ga4_summary()

    except Exception:
        logger.exception("Triage page failed to load data")
        load_error = True
        pending_intakes = []
        unanswered_replies = []
        plans = []
        stale_deals = []
        due_touchpoints = []
        recent_sends = []
        recent_enrollments = []
        upcoming_races = []
        recent_bounces = []
        recent_unsubscribes = []
        health = {"checks": [], "ok_count": 0, "warning_count": 0, "error_count": 0}
        summary = {
            "action_required": 0, "pending_intakes": 0,
            "unread_replies": 0, "plans_needing_action": 0,
            "due_touchpoints": 0,
        }
        ga4 = {"configured": False}

    # First-run detection: all sections empty and no load error
    is_first_run = (
        not load_error
        and not pending_intakes
        and not unanswered_replies
        and not plans
        and not stale_deals
        and not due_touchpoints
        and not recent_sends
        and not recent_enrollments
        and not upcoming_races
        and not recent_bounces
        and not recent_unsubscribes
    )

    return templates.TemplateResponse("triage.html", {
        "request": request,
        "active_page": "triage",
        "load_error": load_error,
        "is_first_run": is_first_run,
        "stale_hours": STALE_DEAL_HOURS,
        # Action required
        "pending_intakes": pending_intakes,
        "unanswered_replies": unanswered_replies,
        "plans_needing_action": plans,
        "stale_deals": stale_deals,
        "due_touchpoints": due_touchpoints,
        # Automated FYI
        "recent_sends": recent_sends,
        "recent_enrollments": recent_enrollments,
        "upcoming_races": upcoming_races,
        "recent_bounces": recent_bounces,
        "recent_unsubscribes": recent_unsubscribes,
        # System health
        "health": health,
        "summary": summary,
        # GA4
        "ga4": ga4,
    })


@router.post("/triage/ack/{comm_id}")
async def ack_reply(comm_id: str, request: Request):
    """Acknowledge an inbound reply — removes the row via htmx."""
    # Rate limit
    _check_rate_limit(request)

    # UUID format validation
    if not _UUID_RE.match(comm_id):
        raise HTTPException(status_code=400, detail="Invalid communication ID format")

    # Existence check
    existing = db.select_one("gg_communications", match={"id": comm_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Communication not found")

    # Update
    try:
        db.update("gg_communications", {"status": "acknowledged"}, {"id": comm_id})
    except Exception:
        logger.exception("Failed to acknowledge communication %s", comm_id)
        raise HTTPException(status_code=500, detail="Failed to update communication")

    # Audit log
    try:
        db.log_action(
            "reply_acknowledged",
            entity_type="communication",
            entity_id=comm_id,
        )
    except Exception:
        logger.warning("Failed to write audit log for ack %s", comm_id)

    return HTMLResponse("")
