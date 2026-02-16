"""Email templates browser — list all, preview with athlete data."""

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control import supabase_client as db
from mission_control.services.email_preview import list_templates, preview_template

router = APIRouter(prefix="/templates")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


@router.get("/")
async def templates_index(request: Request):
    email_templates = list_templates()
    athletes = db.select("gg_athletes", columns="slug, name", order="name")

    # Group by category
    by_category = {}
    for t in email_templates:
        cat = t["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(t)

    return templates.TemplateResponse("templates_page/index.html", {
        "request": request,
        "active_page": "templates",
        "email_templates": email_templates,
        "by_category": by_category,
        "athletes": athletes,
    })


@router.get("/preview")
async def template_preview(
    request: Request,
    template_name: str = Query(...),
    athlete_slug: str = Query(""),
):
    result = preview_template(template_name, athlete_slug or None)

    if request.headers.get("HX-Request"):
        return HTMLResponse(
            f'<div style="padding:var(--gg-spacing-sm) var(--gg-spacing-md);border-bottom:var(--gg-border-standard);background:var(--gg-color-sand)">'
            f'<span class="mc-text-mono" style="font-size:var(--gg-font-size-2xs)">'
            f'Template: <strong>{result["template_name"]}</strong> &middot; '
            f'Athlete: <strong>{result["athlete_name"]}</strong></span></div>'
            f'<div style="padding:var(--gg-spacing-md);background:var(--gg-color-white);overflow:auto;max-height:600px">{result["html"]}</div>'
        )

    athletes = db.select("gg_athletes", columns="slug, name", order="name")
    return templates.TemplateResponse("templates_page/preview.html", {
        "request": request,
        "active_page": "templates",
        "result": result,
        "athletes": athletes,
        "template_name": template_name,
        "athlete_slug": athlete_slug,
    })
