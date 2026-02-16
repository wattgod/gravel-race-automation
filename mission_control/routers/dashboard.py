"""Dashboard route — GET /"""

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db
from mission_control.services.stats import (
    dashboard_stats,
    recent_pipeline_runs,
    tier_breakdown,
    upcoming_races,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


@router.get("/")
async def dashboard(request: Request):
    stats = dashboard_stats()
    races = upcoming_races()
    runs = recent_pipeline_runs()
    tiers = tier_breakdown()
    pending_requests = db.get_pending_plan_requests(limit=10)

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_page": "dashboard",
        "stats": stats,
        "upcoming_races": races,
        "recent_runs": runs,
        "tiers": tiers,
        "pending_requests": pending_requests,
    })
