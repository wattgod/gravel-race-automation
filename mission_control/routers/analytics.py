"""Analytics router — GA4 dashboard."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control.services.ga4 import (
    get_conversion_event_report,
    get_daily_sessions,
    get_top_pages,
    get_traffic_sources,
    refresh_cache,
    summarize_event_totals,
)

router = APIRouter(prefix="/analytics")
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))


@router.get("/")
async def analytics_index(request: Request):
    """GA4 analytics dashboard."""
    top_pages = get_top_pages(days=30, limit=20)
    sources = get_traffic_sources(days=30)
    daily = get_daily_sessions(days=90)
    event_report = get_conversion_event_report(days=30)
    event_totals = event_report["events"]

    # Calculate totals
    total_sessions = sum(d["sessions"] for d in daily) if daily else 0
    total_pageviews = sum(p["pageviews"] for p in top_pages) if top_pages else 0
    event_summary = summarize_event_totals(event_totals)

    return templates.TemplateResponse(request, "analytics/index.html", {
        "request": request,
        "active_page": "analytics",
        "top_pages": top_pages,
        "sources": sources,
        "daily": daily,
        "event_totals": event_totals,
        "event_summary": event_summary,
        "event_data_available": event_report["available"],
        "event_error": event_report["error"],
        "total_sessions": total_sessions,
        "total_pageviews": total_pageviews,
    })


@router.post("/refresh")
async def analytics_refresh(request: Request):
    """Force refresh GA4 cache."""
    count = refresh_cache()
    return HTMLResponse(
        f'<div class="gg-alert gg-alert--success">Refreshed {count} metrics from GA4.</div>'
    )
