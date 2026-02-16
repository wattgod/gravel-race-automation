"""Reports routes — NPS, referrals, plan stats, audit log."""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db
from mission_control.services.stats import level_breakdown, tier_breakdown

router = APIRouter(prefix="/reports")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


@router.get("/")
async def reports_index(request: Request):
    # NPS data
    nps_data = db.get_nps_distribution()
    nps_scores = db.get_nps_scores(limit=50)

    # Referrals
    referrals = db.get_referrals(limit=50)
    referral_stats = {
        "total": len(referrals),
        "pending": sum(1 for r in referrals if r.get("status") == "pending"),
        "contacted": sum(1 for r in referrals if r.get("status") == "contacted"),
        "converted": sum(1 for r in referrals if r.get("status") == "converted"),
    }

    # Plan stats
    tiers = tier_breakdown()
    levels = level_breakdown()

    # Status breakdown
    athletes = db.select("gg_athletes", columns="plan_status")
    status_counts = {}
    for a in athletes:
        s = a.get("plan_status") or "unknown"
        status_counts[s] = status_counts.get(s, 0) + 1
    statuses = [{"plan_status": k, "count": v} for k, v in sorted(status_counts.items(), key=lambda x: -x[1])]

    # Audit log
    audit_log = db.get_audit_log(limit=50)

    # Athletes list for forms
    all_athletes = db.select("gg_athletes", columns="id, slug, name", order="name")

    return templates.TemplateResponse("reports/index.html", {
        "request": request,
        "active_page": "reports",
        "nps_data": nps_data,
        "nps_scores": nps_scores,
        "referrals": referrals,
        "referral_stats": referral_stats,
        "tiers": tiers,
        "levels": levels,
        "statuses": statuses,
        "audit_log": audit_log,
        "athletes": all_athletes,
    })


@router.post("/nps")
async def record_nps(
    request: Request,
    athlete_id: str = Form(...),
    score: int = Form(..., ge=0, le=10),
    comment: str = Form(""),
):
    athlete = db.get_athlete_by_id(athlete_id)
    if not athlete:
        return HTMLResponse('<span class="mc-text-error">Athlete not found</span>')

    db.record_nps(athlete_id, score, comment, athlete.get("race_name", ""))
    db.log_action("nps_recorded", "athlete", str(athlete_id),
                  f"score={score} for {athlete['name']}")

    return HTMLResponse(
        f'<span class="mc-text-teal">NPS {score} recorded for {athlete["name"]}</span>'
    )


@router.post("/referral")
async def record_referral(
    request: Request,
    referrer_id: str = Form(...),
    referred_name: str = Form(...),
    referred_email: str = Form(...),
):
    athlete = db.get_athlete_by_id(referrer_id)
    if not athlete:
        return HTMLResponse('<span class="mc-text-error">Referrer not found</span>')

    db.record_referral(referrer_id, referred_name, referred_email)
    db.log_action("referral_recorded", "referral", str(referrer_id),
                  f"{athlete['name']} referred {referred_name}")

    return HTMLResponse(
        f'<span class="mc-text-teal">Referral recorded: {referred_name} from {athlete["name"]}</span>'
    )
