"""Deals router — sales pipeline UI."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db
from mission_control.services.deals import (
    STAGES,
    create_deal,
    get_deal,
    get_deals,
    link_athlete,
    move_stage,
    pipeline_summary,
    update_deal,
)
from mission_control.services.revenue import record_payment, revenue_vs_target

router = APIRouter(prefix="/deals")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


@router.get("/")
async def deals_index(request: Request):
    """Pipeline board — stages as columns, deals as cards."""
    summary = pipeline_summary()

    # Get deals grouped by stage
    all_deals = get_deals(limit=200)
    by_stage = {stage: [] for stage in STAGES}
    for deal in all_deals:
        stage = deal.get("stage", "lead")
        if stage in by_stage:
            by_stage[stage].append(deal)

    rev = revenue_vs_target()

    return templates.TemplateResponse("deals/index.html", {
        "request": request,
        "active_page": "deals",
        "stages": STAGES,
        "by_stage": by_stage,
        "summary": summary,
        "revenue": rev,
    })


@router.get("/new")
async def deal_new(request: Request):
    """Create deal form (inline HTMX)."""
    return HTMLResponse(f'''
    <div class="mc-card">
        <div class="mc-card__header">
            <h3 class="mc-card__title">New Deal</h3>
        </div>
        <div class="mc-card__body">
            <form hx-post="/deals" hx-target="#deal-form-area" hx-swap="innerHTML">
                <div class="mc-form-group">
                    <label class="mc-label">Email</label>
                    <input type="email" name="email" class="mc-input" required>
                </div>
                <div class="mc-form-group">
                    <label class="mc-label">Name</label>
                    <input type="text" name="name" class="mc-input">
                </div>
                <div class="mc-form-group">
                    <label class="mc-label">Race</label>
                    <input type="text" name="race_name" class="mc-input">
                </div>
                <div class="mc-form-group">
                    <label class="mc-label">Source</label>
                    <select name="source" class="mc-select">
                        <option value="quiz">Quiz</option>
                        <option value="prep_kit">Prep Kit</option>
                        <option value="exit_intent">Exit Intent</option>
                        <option value="referral">Referral</option>
                        <option value="direct">Direct</option>
                    </select>
                </div>
                <div class="mc-form-group">
                    <label class="mc-label">Value ($)</label>
                    <input type="number" name="value" class="mc-input" value="249" step="0.01">
                </div>
                <div class="mc-flex mc-gap-sm">
                    <button type="submit" class="gg-btn gg-btn--primary">Create Deal</button>
                    <a href="/deals" class="gg-btn gg-btn--ghost">Cancel</a>
                </div>
            </form>
        </div>
    </div>
    ''')


@router.post("/")
async def deal_create(
    request: Request,
    email: str = Form(...),
    name: str = Form(""),
    race_name: str = Form(""),
    source: str = Form("direct"),
    value: float = Form(249.00),
):
    """Create a new deal."""
    deal = create_deal(email, name, race_name=race_name, source=source, value=value)
    return HTMLResponse(
        '<div class="gg-alert gg-alert--success">'
        f'Deal created for {email}. <a href="/deals">Back to pipeline</a>'
        '</div>'
    )


@router.get("/{deal_id}")
async def deal_detail(request: Request, deal_id: str):
    """Deal detail page."""
    deal = get_deal(deal_id)
    if not deal:
        return HTMLResponse("<h1>Deal not found</h1>", status_code=404)

    # Get linked athlete if any
    athlete = None
    if deal.get("athlete_id"):
        athlete = db.get_athlete_by_id(deal["athlete_id"])

    # Get payments
    payments = db.select("gg_payments", match={"deal_id": deal_id}, order="paid_at", order_desc=True)

    return templates.TemplateResponse("deals/detail.html", {
        "request": request,
        "active_page": "deals",
        "deal": deal,
        "athlete": athlete,
        "payments": payments,
        "stages": STAGES,
    })


@router.post("/{deal_id}/stage")
async def deal_stage_change(
    request: Request,
    deal_id: str,
    stage: str = Form(...),
):
    """Move deal to a new stage."""
    deal = move_stage(deal_id, stage)
    if not deal:
        return HTMLResponse(
            '<div class="gg-alert gg-alert--error">Invalid stage.</div>'
        )

    # Return updated stage badge
    return HTMLResponse(
        f'<span class="gg-badge mc-deal-stage--{stage}">{stage.replace("_", " ").title()}</span>'
        f' <span class="mc-text-muted mc-text-mono" style="font-size:10px">Updated</span>'
    )


@router.post("/{deal_id}/payment")
async def deal_payment(
    request: Request,
    deal_id: str,
    amount: float = Form(...),
    source: str = Form("manual"),
    description: str = Form(""),
):
    """Record a payment for a deal."""
    payment = record_payment(deal_id, amount, source=source, description=description)

    if payment:
        return HTMLResponse(
            f'<div class="gg-alert gg-alert--success">'
            f'Payment of ${amount:.2f} recorded. <a href="/deals/{deal_id}">Refresh</a>'
            f'</div>'
        )
    return HTMLResponse(
        '<div class="gg-alert gg-alert--error">Failed to record payment.</div>'
    )


@router.post("/{deal_id}/notes")
async def deal_notes(
    request: Request,
    deal_id: str,
    notes: str = Form(""),
):
    """Update deal notes."""
    update_deal(deal_id, {"notes": notes})
    return HTMLResponse(
        '<div class="gg-alert gg-alert--success" style="font-size:12px">Notes saved.</div>'
    )
