"""Athletes routes — list, detail, search, filter, approve, deliver."""

import json
import re
from datetime import date

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db

router = APIRouter(prefix="/athletes")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


def _sanitize_search(q: str) -> str:
    """Strip PostgREST filter metacharacters from search input."""
    return re.sub(r"[%,.()\[\]]", "", q)[:100]


@router.get("/")
async def athlete_list(
    request: Request,
    q: str = Query("", description="Search name/email/race"),
    status: str = Query("", description="Filter by plan_status"),
    tier: str = Query("", description="Filter by tier"),
    page: int = Query(1, ge=1),
):
    per_page = 25
    offset = (page - 1) * per_page

    # Build query
    query = db._table("gg_athletes").select("*", count="exact")
    if q:
        q = _sanitize_search(q)
        query = query.or_(f"name.ilike.%{q}%,email.ilike.%{q}%,race_name.ilike.%{q}%")
    if status:
        query = query.eq("plan_status", status)
    if tier:
        query = query.eq("tier", tier)

    query = query.order("created_at", desc=True).range(offset, offset + per_page - 1)
    result = query.execute()
    athletes = result.data or []
    total = result.count or 0

    context = {
        "request": request,
        "active_page": "athletes",
        "athletes": athletes,
        "total": total,
        "page": page,
        "per_page": per_page,
        "q": q,
        "status": status,
        "tier": tier,
    }

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/athlete_table.html", context)

    return templates.TemplateResponse("athletes/list.html", context)


@router.get("/{slug}")
async def athlete_detail(request: Request, slug: str):
    athlete = db.get_athlete(slug)
    if not athlete:
        return HTMLResponse("<h1>Athlete not found</h1>", status_code=404)

    athlete_id = athlete["id"]

    touchpoints = db.get_touchpoints(athlete_id=athlete_id)
    communications = db.get_communications(athlete_id)
    pipeline_runs = db.get_pipeline_runs(athlete_id=athlete_id, limit=10)
    nps_scores = db.select("gg_nps_scores", match={"athlete_id": athlete_id},
                           order="created_at", order_desc=True)
    files = db.get_files(athlete_id)

    # Parse intake and methodology
    intake = athlete.get("intake_json") or {}
    if isinstance(intake, str):
        intake = json.loads(intake)

    methodology = athlete.get("methodology_json")
    if isinstance(methodology, str):
        methodology = json.loads(methodology)

    today = date.today().isoformat()
    due_count = sum(1 for t in touchpoints if str(t.get("send_date", "")) <= today and not t.get("sent"))

    return templates.TemplateResponse("athletes/detail.html", {
        "request": request,
        "active_page": "athletes",
        "athlete": athlete,
        "touchpoints": touchpoints,
        "communications": communications,
        "pipeline_runs": pipeline_runs,
        "nps_scores": nps_scores,
        "files": files,
        "methodology": methodology,
        "intake": intake,
        "due_count": due_count,
        "today": today,
    })


@router.post("/{slug}/notes")
async def update_notes(request: Request, slug: str, notes: str = Form("")):
    db.update_athlete(slug, {"notes": notes})
    db.log_action("notes_updated", "athlete", slug, "Notes updated")

    return HTMLResponse(
        f'<div id="notes-section">'
        f'<textarea name="notes" rows="3" class="mc-textarea"'
        f' hx-post="/athletes/{slug}/notes" hx-target="#notes-section" hx-swap="outerHTML"'
        f' hx-trigger="change">{notes}</textarea>'
        f'<span class="mc-text-teal" style="font-size:var(--gg-font-size-2xs)">Saved</span></div>'
    )


@router.post("/{slug}/approve")
async def approve_plan(request: Request, slug: str):
    db.update_athlete(slug, {"plan_status": "approved"})
    db.log_action("plan_approved", "athlete", slug, f"Plan approved for {slug}")

    return HTMLResponse(
        '<span class="gg-badge mc-status--approved">APPROVED</span>'
        ' <a href="javascript:location.reload()" class="gg-btn gg-btn--secondary" '
        'style="font-size:var(--gg-font-size-2xs);padding:var(--gg-spacing-2xs) var(--gg-spacing-sm)">'
        'Refresh</a>'
    )


@router.post("/{slug}/deliver")
async def deliver_plan(request: Request, slug: str, dry_run: bool = Form(True)):
    athlete = db.get_athlete(slug)
    if not athlete:
        return HTMLResponse('<span class="mc-text-error">Athlete not found</span>')

    if dry_run:
        return HTMLResponse(
            f'<div class="gg-alert gg-alert--warning mc-mb-md">'
            f'<span class="gg-alert__label">Preview</span>'
            f'<span class="gg-alert__message">Ready to deliver plan to <strong>{athlete["email"]}</strong>. '
            f'<form hx-post="/athletes/{slug}/deliver" hx-target="#deliver-result" hx-swap="innerHTML" style="display:inline">'
            f'<input type="hidden" name="dry_run" value="">'
            f'<button type="submit" class="gg-btn gg-btn--primary" '
            f'style="font-size:var(--gg-font-size-2xs);padding:var(--gg-spacing-2xs) var(--gg-spacing-sm)">'
            f'Confirm Deliver</button></form></span></div>'
        )

    # TODO: Actual delivery logic (generate signed URLs, send email)
    db.update_athlete(slug, {"plan_status": "delivered"})
    db.log_action("plan_delivered", "athlete", slug, f"Plan delivered to {athlete['email']}")
    db.log_communication(
        athlete_id=athlete["id"],
        comm_type="delivery",
        subject="Your Gravel God Training Plan",
        recipient=athlete["email"],
    )

    return HTMLResponse(
        '<div class="gg-alert gg-alert--success">'
        '<span class="gg-alert__label">Done</span>'
        '<span class="gg-alert__message">Plan delivered successfully. '
        '<a href="javascript:location.reload()">Refresh page</a></span></div>'
    )
