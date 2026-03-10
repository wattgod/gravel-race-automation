"""Athletes routes — list, detail, search, filter, approve, deliver."""

import json
import logging
import re
from datetime import date

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db

logger = logging.getLogger(__name__)

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


DELIVERABLE_STATUSES = {"pipeline_complete", "approved", "delivered"}


@router.post("/{slug}/deliver")
async def deliver_plan(request: Request, slug: str, dry_run: bool = Form(True)):
    athlete = db.get_athlete(slug)
    if not athlete:
        return HTMLResponse(
            '<span class="mc-text-error">Athlete not found</span>',
            status_code=404,
        )

    # Guard: athlete must have a valid email
    athlete_email = (athlete.get("email") or "").strip()
    if not athlete_email:
        return HTMLResponse(
            '<div class="gg-alert gg-alert--error">'
            '<span class="gg-alert__label">Error</span>'
            '<span class="gg-alert__message">Athlete has no email address on file. '
            'Update the athlete record before delivering.</span></div>',
            status_code=400,
        )

    # Guard: plan must be in a deliverable state
    plan_status = athlete.get("plan_status", "")
    if plan_status not in DELIVERABLE_STATUSES:
        return HTMLResponse(
            f'<div class="gg-alert gg-alert--error">'
            f'<span class="gg-alert__label">Error</span>'
            f'<span class="gg-alert__message">Cannot deliver — plan status is '
            f'<strong>{plan_status}</strong>. '
            f'Pipeline must complete before delivery.</span></div>',
            status_code=409,
        )

    if dry_run:
        return HTMLResponse(
            f'<div class="gg-alert gg-alert--warning mc-mb-md">'
            f'<span class="gg-alert__label">Preview</span>'
            f'<span class="gg-alert__message">Ready to deliver plan to <strong>{athlete_email}</strong>. '
            f'<form hx-post="/athletes/{slug}/deliver" hx-target="#deliver-result" hx-swap="innerHTML" style="display:inline">'
            f'<input type="hidden" name="dry_run" value="false">'
            f'<button type="submit" class="gg-btn gg-btn--primary" '
            f'style="font-size:var(--gg-font-size-2xs);padding:var(--gg-spacing-2xs) var(--gg-spacing-sm)">'
            f'Confirm Deliver</button></form></span></div>'
        )

    # Generate signed URLs for deliverable artifacts
    from mission_control.services.file_storage import get_signed_url

    DELIVERABLE_TYPES = {"guide_pdf", "guide_html", "zwo", "methodology_md"}
    SIGNED_URL_EXPIRY = 7 * 24 * 3600  # 7 days

    files = db.get_files(athlete["id"])
    deliverables = [f for f in files if f.get("file_type") in DELIVERABLE_TYPES]

    if not deliverables:
        return HTMLResponse(
            '<div class="gg-alert gg-alert--error">'
            '<span class="gg-alert__label">Error</span>'
            '<span class="gg-alert__message">No deliverable artifacts found. '
            'Run the pipeline first.</span></div>',
            status_code=404,
        )

    signed_urls = {}
    failed_files = []
    for f in deliverables:
        try:
            url = get_signed_url(f["storage_path"], expires_in=SIGNED_URL_EXPIRY)
            if url:
                signed_urls[f["file_name"]] = url
            else:
                failed_files.append(f["file_name"])
                logger.warning("Empty signed URL for %s", f["storage_path"])
        except Exception:
            failed_files.append(f["file_name"])
            logger.exception("Failed to sign URL for %s", f["storage_path"])

    if not signed_urls:
        return HTMLResponse(
            '<div class="gg-alert gg-alert--error">'
            '<span class="gg-alert__label">Error</span>'
            '<span class="gg-alert__message">Failed to generate download links. '
            'Check storage configuration.</span></div>',
            status_code=502,
        )

    # Send delivery email via Resend
    from mission_control.config import RESEND_API_KEY, RESEND_FROM_EMAIL

    athlete_name = athlete.get("name", "Athlete")
    race_name = athlete.get("race_name", "your race")
    email_subject = "Your Gravel God Training Plan"

    links_html = "".join(
        f'<li><a href="{url}">{name}</a></li>' for name, url in signed_urls.items()
    )
    email_body = (
        f"<h2>Hey {athlete_name},</h2>"
        f"<p>Your custom training plan for <strong>{race_name}</strong> is ready.</p>"
        f"<p>Download your files (links expire in 7 days):</p>"
        f"<ul>{links_html}</ul>"
        f"<p>Questions? Reply to this email and we'll get back to you.</p>"
        f"<p>— Gravel God Training</p>"
    )

    resend_id = ""
    email_sent = False
    email_error = ""

    if RESEND_API_KEY:
        try:
            import resend
            resend.api_key = RESEND_API_KEY

            result = resend.Emails.send({
                "from": f"Gravel God Training <{RESEND_FROM_EMAIL}>",
                "to": [athlete_email],
                "subject": email_subject,
                "html": email_body,
            })
            resend_id = result.get("id", "")
            email_sent = True
        except Exception as exc:
            email_error = str(exc)
            logger.exception(
                "Failed to send delivery email to %s (athlete=%s, files=%d)",
                athlete_email, slug, len(signed_urls),
            )
    else:
        logger.warning(
            "RESEND_API_KEY not set — skipping delivery email to %s. "
            "Signed URLs generated: %s",
            athlete_email,
            list(signed_urls.keys()),
        )

    # Determine delivery status: only mark as "delivered" if email was sent.
    # If email failed, mark as "delivery_failed" so operators can retry.
    # If API key is missing, mark as "delivered_no_email" (URLs are ready).
    if email_sent:
        new_status = "delivered"
    elif email_error:
        new_status = "delivery_failed"
    else:
        new_status = "delivered_no_email"

    db.update_athlete(slug, {"plan_status": new_status})

    # Build details string with all relevant context for debugging
    details_parts = [
        f"Plan delivery to {athlete_email}",
        f"status={new_status}",
        f"files_signed={len(signed_urls)}",
    ]
    if failed_files:
        details_parts.append(f"files_failed={failed_files}")
    if email_error:
        details_parts.append(f"email_error={email_error[:200]}")

    db.log_action("plan_delivered", "athlete", slug, ", ".join(details_parts))
    db.log_communication(
        athlete_id=athlete["id"],
        comm_type="delivery",
        subject=email_subject,
        recipient=athlete_email,
        resend_id=resend_id,
        status="sent" if email_sent else ("failed" if email_error else "skipped"),
    )

    # Build response with appropriate warnings
    warnings = []
    if failed_files:
        warnings.append(
            f'{len(failed_files)} file(s) could not be signed: {", ".join(failed_files)}'
        )
    if email_error:
        warnings.append(f"Email send failed: {email_error[:100]}")
    elif not RESEND_API_KEY:
        warnings.append("Email not sent — RESEND_API_KEY not configured")

    alert_class = "gg-alert--success" if email_sent and not failed_files else "gg-alert--warning"
    warning_html = "".join(
        f' <span class="mc-text-warning">({w})</span>' for w in warnings
    )

    return HTMLResponse(
        f'<div class="gg-alert {alert_class}">'
        f'<span class="gg-alert__label">{"Done" if email_sent else "Partial"}</span>'
        f'<span class="gg-alert__message">Plan delivery — {len(signed_urls)} files '
        f'signed for {athlete_email}.{warning_html} '
        f'<a href="javascript:location.reload()">Refresh page</a></span></div>'
    )
