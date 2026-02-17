"""Touchpoints routes — global view, category tabs, send, batch send."""

from datetime import date

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db
from mission_control.services.touchpoint_sender import (
    batch_send_due,
    render_touchpoint,
    send_touchpoint,
)

router = APIRouter(prefix="/touchpoints")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))

CATEGORIES = ["all", "onboarding", "training", "recovery", "race_prep", "post_race", "retention"]


@router.get("/")
async def touchpoint_list(
    request: Request,
    category: str = Query("all"),
    show: str = Query("all"),
):
    today = date.today().isoformat()

    # Build Supabase query
    q = db._table("gg_touchpoints").select("*, gg_athletes(name, slug, email)")

    if category != "all":
        q = q.eq("category", category)
    if show == "due":
        q = q.lte("send_date", today).eq("sent", False)
    elif show == "sent":
        q = q.eq("sent", True)

    q = q.order("send_date").limit(200)
    result = q.execute()
    touchpoints = result.data or []

    due_count = db.count_due_touchpoints()

    # Category counts — single query instead of 6 separate DB calls
    all_cats = db.select("gg_touchpoints", columns="category")
    cat_counts = {cat: 0 for cat in CATEGORIES[1:]}
    for row in all_cats:
        c = row.get("category", "")
        if c in cat_counts:
            cat_counts[c] += 1
    cat_counts["all"] = sum(cat_counts.values())

    context = {
        "request": request,
        "active_page": "touchpoints",
        "touchpoints": touchpoints,
        "categories": CATEGORIES,
        "cat_counts": cat_counts,
        "active_category": category,
        "active_show": show,
        "due_count": due_count,
        "today": today,
    }

    if request.headers.get("HX-Request") and request.headers.get("HX-Target") == "touchpoint-body":
        return templates.TemplateResponse("partials/touchpoint_table.html", context)

    return templates.TemplateResponse("touchpoints/index.html", context)


@router.post("/send")
async def touchpoint_send(
    request: Request,
    touchpoint_id: str = Form(...),
    dry_run: bool = Form(True),
):
    result = send_touchpoint(touchpoint_id, dry_run=dry_run)

    if result.get("dry_run"):
        tp = db.select_one("gg_touchpoints", match={"id": touchpoint_id})
        athlete = db.get_athlete_by_id(tp["athlete_id"]) if tp else None

        return HTMLResponse(
            f'<tr id="tp-{touchpoint_id}">'
            f'<td colspan="6" class="mc-card__body">'
            f'<div class="gg-alert gg-alert--warning">'
            f'<span class="gg-alert__label">Preview</span>'
            f'<span class="gg-alert__message">{tp["subject"] if tp else ""} — To: {athlete["email"] if athlete else ""}</span>'
            f'</div>'
            f'<div style="background:var(--gg-color-white);padding:var(--gg-spacing-md);border:var(--gg-border-standard);max-height:250px;overflow:auto">{result.get("html", "")}</div>'
            f'<div class="mc-flex mc-gap-sm mc-mt-md">'
            f'<form hx-post="/touchpoints/send" hx-target="#tp-{touchpoint_id}" hx-swap="outerHTML">'
            f'<input type="hidden" name="touchpoint_id" value="{touchpoint_id}">'
            f'<input type="hidden" name="dry_run" value="">'
            f'<button type="submit" class="gg-btn gg-btn--secondary">Confirm Send</button>'
            f'</form>'
            f'<button onclick="location.reload()" class="gg-btn gg-btn--default">Cancel</button>'
            f'</div></td></tr>'
        )

    if result["success"]:
        return HTMLResponse(
            f'<tr id="tp-{touchpoint_id}">'
            f'<td colspan="6" style="padding:var(--gg-spacing-sm)">'
            f'<span class="mc-text-teal">Sent successfully — {result.get("message", "")}</span>'
            f'</td></tr>'
        )

    return HTMLResponse(
        f'<tr id="tp-{touchpoint_id}">'
        f'<td colspan="6" style="padding:var(--gg-spacing-sm)">'
        f'<span class="mc-text-error">Failed: {result.get("message", "Unknown error")}</span>'
        f'</td></tr>'
    )


@router.post("/batch-send")
async def touchpoint_batch_send(
    request: Request,
    dry_run: bool = Form(True),
):
    result = batch_send_due(dry_run=dry_run)

    if result.get("dry_run"):
        return HTMLResponse(
            f'<div class="gg-alert gg-alert--warning">'
            f'<span class="gg-alert__label">Preview</span>'
            f'<span class="gg-alert__message">{result["due"]} touchpoints due. Dry run — no emails sent. '
            f'<form hx-post="/touchpoints/batch-send" hx-target="#batch-result" hx-swap="innerHTML" style="display:inline">'
            f'<input type="hidden" name="dry_run" value="">'
            f'<button type="submit" class="gg-btn gg-btn--secondary" '
            f'style="font-size:var(--gg-font-size-2xs);padding:var(--gg-spacing-2xs) var(--gg-spacing-sm)">'
            f'Send All {result["due"]}</button>'
            f'</form></span></div>'
        )

    return HTMLResponse(
        f'<div class="gg-alert gg-alert--success">'
        f'<span class="gg-alert__label">Done</span>'
        f'<span class="gg-alert__message">Batch complete: {result["sent"]} sent, {result["failed"]} failed</span></div>'
    )
