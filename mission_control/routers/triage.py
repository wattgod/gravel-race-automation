"""Triage route — command center with inline actions and OOB stat refresh."""

import logging
import re
import time
from collections import defaultdict

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control import supabase_client as db
from mission_control.config import WEB_TEMPLATES_DIR
from mission_control.services.deals import move_stage
from mission_control.services.triage import (
    STALE_DEAL_HOURS,
    get_api_cost_summary,
    get_expanded_health,
    get_pending_intakes,
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


def _render_stats_html() -> str:
    """Render the stat cards partial as an HTML string."""
    summary = triage_summary()
    env = templates.env
    tmpl = env.get_template("partials/triage_stats.html")
    return tmpl.render(summary=summary)


def _oob_response(primary_html: str = "") -> HTMLResponse:
    """Return primary HTML + OOB stat card update."""
    oob = _render_stats_html()
    return HTMLResponse(
        primary_html
        + f'<div id="triage-stats" class="gg-stat-grid mc-mb-lg" '
        f'hx-get="/triage/stats" hx-trigger="every 300s" hx-swap="innerHTML" '
        f'hx-swap-oob="true">{oob}</div>'
    )


# ---------------------------------------------------------------------------
# GET /triage — main page
# ---------------------------------------------------------------------------

@router.get("/triage")
async def triage(request: Request):
    load_error = False
    try:
        # Action required
        pending_intakes = get_pending_intakes()
        unanswered_replies = get_unanswered_replies()
        stale_deals = get_stale_deals()

        # Automated FYI
        recent_sends = get_recent_sends()
        recent_enrollments = get_recent_enrollments()
        upcoming_races = get_upcoming_races()
        recent_bounces = get_recent_bounces()
        recent_unsubscribes = get_recent_unsubscribes()

        # System health
        health = get_system_health()
        summary = triage_summary(pending_intakes=pending_intakes)

        # GA4
        ga4 = get_triage_ga4_summary()

        # API costs
        api_costs = get_api_cost_summary()

    except Exception:
        logger.exception("Triage page failed to load data")
        load_error = True
        pending_intakes = []
        unanswered_replies = []
        stale_deals = []
        recent_sends = []
        recent_enrollments = []
        upcoming_races = []
        recent_bounces = []
        recent_unsubscribes = []
        health = {"checks": [], "ok_count": 0, "warning_count": 0, "error_count": 0}
        summary = {
            "action_required": 0, "pending_intakes": 0,
            "unread_replies": 0,
        }
        ga4 = {"configured": False}
        api_costs = {"configured": False}

    # First-run detection: all sections empty and no load error
    is_first_run = (
        not load_error
        and not pending_intakes
        and not unanswered_replies
        and not stale_deals
        and not recent_sends
        and not recent_enrollments
        and not upcoming_races
        and not recent_bounces
        and not recent_unsubscribes
    )

    return templates.TemplateResponse(request, "triage.html", {
        "request": request,
        "active_page": "triage",
        "load_error": load_error,
        "is_first_run": is_first_run,
        "stale_hours": STALE_DEAL_HOURS,
        # Action required
        "pending_intakes": pending_intakes,
        "unanswered_replies": unanswered_replies,
        "stale_deals": stale_deals,
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
        # API costs
        "api_costs": api_costs,
    })


# ---------------------------------------------------------------------------
# GET /triage/stats — HTML fragment for stat cards (used by htmx polling + OOB)
# ---------------------------------------------------------------------------

@router.get("/triage/stats")
async def triage_stats():
    """Return stat card HTML fragment for htmx polling."""
    return HTMLResponse(_render_stats_html())


# ---------------------------------------------------------------------------
# POST /triage/ack/{comm_id} — acknowledge inbound reply
# ---------------------------------------------------------------------------

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

    return _oob_response("")


# ---------------------------------------------------------------------------
# POST /triage/deals/{deal_id}/stage — change deal stage from triage
# ---------------------------------------------------------------------------

@router.post("/triage/deals/{deal_id}/stage")
async def change_deal_stage(deal_id: str, request: Request, stage: str = Form(...)):
    """Move a deal to a new stage from the triage page."""
    _check_rate_limit(request)

    # UUID validation
    if not _UUID_RE.match(deal_id):
        raise HTTPException(status_code=400, detail="Invalid deal ID format")

    # Existence check
    existing = db.select_one("gg_deals", match={"id": deal_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Deal not found")

    # Move stage (validates stage name internally)
    result = move_stage(deal_id, stage)
    if result is None:
        raise HTTPException(status_code=400, detail="Invalid stage")

    # If closed, remove row. If still active, return updated row.
    if stage in ("closed_won", "closed_lost"):
        return _oob_response("")

    # Return updated row HTML
    row_html = (
        f'<tr>'
        f'<td><a href="/deals/{deal_id}" class="mc-text-teal">'
        f'{_esc(result.get("contact_name") or result.get("contact_email", "—"))}</a></td>'
        f'<td>{_esc(result.get("race_name") or "—")}</td>'
        f'<td><span class="gg-badge mc-deal-stage--{_esc(stage)}">'
        f'{_esc(stage.replace("_", " "))}</span></td>'
        f'<td class="gg-table__num">${float(result.get("value", 0)):.0f}</td>'
        f'<td class="mc-text-muted">'
        f'{(result.get("updated_at") or "—")[:10]}</td>'
        f'<td class="triage-action-group">'
        f'<button class="gg-btn gg-btn--ghost triage-btn-sm" '
        f'hx-post="/triage/deals/{deal_id}/stage" '
        f'hx-vals=\'{{"stage":"qualified"}}\' '
        f'hx-target="closest tr" hx-swap="outerHTML" '
        f'hx-confirm="Move to Qualified?">Qualify</button>'
        f'<button class="gg-btn gg-btn--ghost triage-btn-sm triage-btn-danger" '
        f'hx-post="/triage/deals/{deal_id}/stage" '
        f'hx-vals=\'{{"stage":"closed_lost"}}\' '
        f'hx-target="closest tr" hx-swap="outerHTML" '
        f'hx-confirm="Close as Lost?">Close</button>'
        f'</td>'
        f'</tr>'
    )
    return _oob_response(row_html)


# ---------------------------------------------------------------------------
# GET /triage/health/deep — expanded health checks (lazy-loaded)
# ---------------------------------------------------------------------------

@router.get("/triage/health/deep")
async def deep_health():
    """Run expanded health checks and return HTML fragment."""
    health = get_expanded_health()
    env = templates.env
    tmpl = env.get_template("partials/triage_health_detail.html")
    html = tmpl.render(health=health)
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _esc(val: str) -> str:
    """HTML-escape a string to prevent XSS."""
    return (
        str(val)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )
