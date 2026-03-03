"""Triage route — GET /triage (command center)."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control import supabase_client as db
from mission_control.config import WEB_TEMPLATES_DIR
from mission_control.services.triage import (
    get_due_touchpoints,
    get_pending_intakes,
    get_plans_needing_action,
    get_recent_bounces,
    get_recent_enrollments,
    get_recent_sends,
    get_recent_unsubscribes,
    get_stale_deals,
    get_system_health,
    get_unanswered_replies,
    get_upcoming_races,
    triage_summary,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


@router.get("/triage")
async def triage(request: Request):
    # Action required
    pending_intakes = get_pending_intakes()
    unanswered_replies = get_unanswered_replies()
    plans_needing_action = get_plans_needing_action()
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
    summary = triage_summary()

    return templates.TemplateResponse("triage.html", {
        "request": request,
        "active_page": "triage",
        # Action required
        "pending_intakes": pending_intakes,
        "unanswered_replies": unanswered_replies,
        "plans_needing_action": plans_needing_action,
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
    })


@router.post("/triage/ack/{comm_id}")
async def ack_reply(comm_id: str):
    """Acknowledge an inbound reply — removes the row via htmx."""
    db.update("gg_communications", {"status": "acknowledged"}, {"id": comm_id})
    return HTMLResponse("")
