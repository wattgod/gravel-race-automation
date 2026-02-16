"""Pipeline routes — trigger runs, view history, sync filesystem."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db
from mission_control.services.pipeline_runner import (
    get_run_status,
    trigger_audit,
    trigger_pipeline,
)
from mission_control.sync import sync_all

router = APIRouter(prefix="/pipeline")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


@router.get("/")
async def pipeline_index(request: Request):
    runs = db.get_pipeline_runs(limit=50)
    athletes = db.select("gg_athletes", columns="id, slug, name", order="name")

    return templates.TemplateResponse("pipeline/index.html", {
        "request": request,
        "active_page": "pipeline",
        "runs": runs,
        "athletes": athletes,
    })


@router.get("/{run_id}")
async def pipeline_run_detail(request: Request, run_id: str):
    run = db.get_pipeline_run(run_id)
    if not run:
        return HTMLResponse("<h1>Run not found</h1>", status_code=404)

    athlete = db.get_athlete_by_id(run["athlete_id"])

    return templates.TemplateResponse("pipeline/run_detail.html", {
        "request": request,
        "active_page": "pipeline",
        "run": run,
        "athlete": athlete,
    })


@router.post("/trigger")
async def pipeline_trigger(
    request: Request,
    athlete_id: str = Form(...),
    run_type: str = Form("draft"),
    skip_pdf: bool = Form(True),
    skip_deploy: bool = Form(True),
    skip_deliver: bool = Form(True),
):
    athlete = db.get_athlete_by_id(athlete_id)
    if not athlete:
        return HTMLResponse('<div class="gg-alert gg-alert--error"><span class="gg-alert__label">Error</span><span class="gg-alert__message">Athlete not found</span></div>')

    try:
        run_id = trigger_pipeline(
            athlete_id=athlete_id,
            slug=athlete["slug"],
            run_type=run_type,
            skip_pdf=skip_pdf,
            skip_deploy=skip_deploy,
            skip_deliver=skip_deliver,
        )
    except FileNotFoundError as e:
        return HTMLResponse(f'<div class="gg-alert gg-alert--error"><span class="gg-alert__label">Error</span><span class="gg-alert__message">{e}</span></div>')

    return HTMLResponse(
        f'<div id="run-status" hx-get="/pipeline/status/{run_id}" hx-trigger="every 2s" '
        f'hx-swap="outerHTML" class="gg-alert gg-alert--warning">'
        f'<span class="gg-alert__label">Running</span>'
        f'<span class="gg-alert__message">Pipeline running for {athlete["name"]}...</span>'
        f'</div>'
    )


@router.get("/status/{run_id}")
async def pipeline_status(run_id: str):
    run = get_run_status(run_id)
    if not run:
        return HTMLResponse('<div class="gg-alert gg-alert--error"><span class="gg-alert__label">Error</span><span class="gg-alert__message">Run not found</span></div>')

    if run["status"] == "running":
        athlete = db.get_athlete_by_id(run["athlete_id"])
        name = athlete["name"] if athlete else "Unknown"
        step = run.get("current_step", "")
        return HTMLResponse(
            f'<div id="run-status" hx-get="/pipeline/status/{run_id}" hx-trigger="every 2s" '
            f'hx-swap="outerHTML" class="gg-alert gg-alert--warning">'
            f'<span class="gg-alert__label">Running</span>'
            f'<span class="gg-alert__message">Pipeline running for {name}... Step: {step}</span>'
            f'</div>'
        )

    if run["status"] == "completed":
        duration = f'{run["duration_secs"]:.1f}s' if run.get("duration_secs") else ""
        stdout = _escape(run.get("stdout", ""))
        return HTMLResponse(
            f'<div id="run-status">'
            f'<div class="gg-alert gg-alert--success">'
            f'<span class="gg-alert__label">Done</span>'
            f'<span class="gg-alert__message">Pipeline completed in {duration}. '
            f'<a href="/pipeline/{run_id}">View details</a></span></div>'
            f'<pre class="mc-pre mc-mt-md">{stdout}</pre></div>'
        )

    # Failed
    error = _escape(run.get("error_message", ""))
    return HTMLResponse(
        f'<div id="run-status">'
        f'<div class="gg-alert gg-alert--error">'
        f'<span class="gg-alert__label">Failed</span>'
        f'<span class="gg-alert__message">Pipeline failed</span></div>'
        f'<pre class="mc-pre mc-mt-md">{error}</pre></div>'
    )


@router.post("/sync")
async def pipeline_sync(request: Request):
    stats = sync_all()
    db.log_action("filesystem_sync", "system", "",
                  f"athletes={stats['athletes']}, touchpoints={stats['touchpoints']}")
    return HTMLResponse(
        f'<div class="gg-alert gg-alert--success">'
        f'<span class="gg-alert__label">Synced</span>'
        f'<span class="gg-alert__message">Synced {stats["athletes"]} athletes, {stats["touchpoints"]} touchpoints</span></div>'
    )


@router.post("/audit")
async def pipeline_audit(
    request: Request,
    athlete_id: str = Form(...),
):
    athlete = db.get_athlete_by_id(athlete_id)
    if not athlete:
        return HTMLResponse('<div class="gg-alert gg-alert--error"><span class="gg-alert__label">Error</span><span class="gg-alert__message">Athlete not found</span></div>')

    try:
        run_id = trigger_audit(athlete_id, athlete["slug"])
    except FileNotFoundError as e:
        return HTMLResponse(f'<div class="gg-alert gg-alert--error"><span class="gg-alert__label">Error</span><span class="gg-alert__message">{e}</span></div>')

    return HTMLResponse(
        f'<div id="run-status" hx-get="/pipeline/status/{run_id}" hx-trigger="every 2s" '
        f'hx-swap="outerHTML" class="gg-alert gg-alert--warning">'
        f'<span class="gg-alert__label">Running</span>'
        f'<span class="gg-alert__message">Running audit for {athlete["name"]}...</span></div>'
    )


def _escape(text: str) -> str:
    """Escape HTML entities."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
