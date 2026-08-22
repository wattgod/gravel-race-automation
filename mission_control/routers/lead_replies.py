"""Mobile-friendly editor queue for lead replies and learning metrics."""

import re

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control.services.lead_nurture import (
    approve_reply_suggestion,
    dismiss_reply_suggestion,
    get_learning_metrics,
    get_reply_queue,
)


router = APIRouter(prefix="/lead-replies")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


@router.get("")
async def lead_reply_queue(request: Request):
    return templates.TemplateResponse(request, "lead_replies/index.html", {
        "request": request,
        "active_page": "lead_replies",
        "queue": get_reply_queue(),
        "metrics": get_learning_metrics(),
    })


@router.post("/{suggestion_id}/approve")
async def approve_lead_reply(
    suggestion_id: str,
    draft_text: str = Form(...),
):
    if not _UUID_RE.match(suggestion_id):
        raise HTTPException(status_code=400, detail="Invalid suggestion ID")
    result = approve_reply_suggestion(suggestion_id, draft_text)
    if not result:
        raise HTTPException(status_code=409, detail="Suggestion cannot be approved")
    return HTMLResponse(
        '<div class="gg-alert gg-alert--success">'
        '<span class="gg-alert__label">Approved</span>'
        '<span class="gg-alert__message">The Gmail relay will create an unsent draft. Nothing was sent.</span>'
        '</div>'
    )


@router.post("/{suggestion_id}/dismiss")
async def dismiss_lead_reply(suggestion_id: str):
    if not _UUID_RE.match(suggestion_id):
        raise HTTPException(status_code=400, detail="Invalid suggestion ID")
    if not dismiss_reply_suggestion(suggestion_id):
        raise HTTPException(status_code=409, detail="Suggestion cannot be dismissed")
    return HTMLResponse("")
