"""GA4 Data API client — fetches analytics data with caching.

Caching uses Supabase (gg_ga4_cache table) when available.
When Supabase isn't configured (e.g. standalone daily_report.py),
caching is skipped and data is fetched fresh every call.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

try:
    from mission_control import supabase_client as db
except Exception:
    db = None

try:
    from mission_control.config import GA4_CREDENTIALS_PATH, GA4_PROPERTY_ID
except Exception:
    GA4_CREDENTIALS_PATH = os.environ.get("GA4_CREDENTIALS_PATH", "")
    GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "")

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 4

# Keep this list aligned with the events already emitted by the site and the
# standard commerce lifecycle. These are independently aggregated event totals;
# this service does not join them into a user, session, product, or order cohort.
CONVERSION_EVENT_NAMES = frozenset({
    "email_capture", "prep_kit_unlock", "quiz_complete", "plan_request",
    "exit_intent_capture", "fueling_calculate", "review_submit",
    "form_start", "tp_form_start", "form_submit", "tp_form_submit",
    "view_item_list", "select_item", "view_item", "add_to_wishlist",
    "add_to_cart", "remove_from_cart", "view_cart", "begin_checkout",
    "add_shipping_info", "add_payment_info", "purchase", "refund",
})


def summarize_event_totals(events: list[dict]) -> dict[str, int]:
    """Return exact operational event counts without combining unlike events."""
    counts: dict[str, int] = {}
    for event in events:
        name = str(event.get("event") or "")
        counts[name] = counts.get(name, 0) + int(event.get("count") or 0)
    return {
        "email_capture_events": counts.get("email_capture", 0),
        "plan_request_events": counts.get("plan_request", 0),
        "checkout_start_events": counts.get("begin_checkout", 0),
        "purchase_events": counts.get("purchase", 0),
        "refund_events": counts.get("refund", 0),
    }


def _get_cached(cache_key: str) -> dict | None:
    """Get cached data if fresh enough. Returns None if caching unavailable."""
    if db is None:
        return None
    try:
        row = db.select_one("gg_ga4_cache", match={"cache_key": cache_key})
        if not row:
            return None

        fetched_at = datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - fetched_at > timedelta(hours=CACHE_TTL_HOURS):
            return None

        return row["data"]
    except Exception:
        return None


def _set_cached(cache_key: str, data: dict) -> None:
    """Store data in cache. No-op if caching unavailable."""
    if db is None:
        return
    try:
        db.upsert("gg_ga4_cache", {
            "cache_key": cache_key,
            "data": data,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="cache_key")
    except Exception:
        pass


def _get_client():
    """Get GA4 Data API client."""
    if not GA4_PROPERTY_ID or not GA4_CREDENTIALS_PATH:
        return None

    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.oauth2.service_account import Credentials

        credentials = Credentials.from_service_account_file(
            GA4_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        return BetaAnalyticsDataClient(credentials=credentials)
    except Exception as e:
        logger.error("Failed to create GA4 client: %s", e)
        return None


def get_top_pages(days: int = 30, limit: int = 20) -> list[dict]:
    """Top pages by pageviews."""
    cache_key = f"top_pages_{days}_{limit}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    client = _get_client()
    if not client:
        return []

    try:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )

        request = RunReportRequest(
            property=GA4_PROPERTY_ID,
            dimensions=[Dimension(name="pagePath")],
            metrics=[Metric(name="screenPageViews"), Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            limit=limit,
            order_bys=[{"metric": {"metric_name": "screenPageViews"}, "desc": True}],
        )
        response = client.run_report(request)

        pages = []
        for row in response.rows:
            pages.append({
                "path": row.dimension_values[0].value,
                "pageviews": int(row.metric_values[0].value),
                "sessions": int(row.metric_values[1].value),
            })

        _set_cached(cache_key, pages)
        return pages

    except Exception as e:
        logger.error("GA4 top_pages error: %s", e)
        return []


def get_traffic_sources(days: int = 30) -> list[dict]:
    """Sessions by channel grouping."""
    cache_key = f"traffic_sources_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    client = _get_client()
    if not client:
        return []

    try:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )

        request = RunReportRequest(
            property=GA4_PROPERTY_ID,
            dimensions=[Dimension(name="sessionDefaultChannelGroup")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        )
        response = client.run_report(request)

        sources = []
        for row in response.rows:
            sources.append({
                "channel": row.dimension_values[0].value,
                "sessions": int(row.metric_values[0].value),
            })

        sources.sort(key=lambda x: x["sessions"], reverse=True)
        _set_cached(cache_key, sources)
        return sources

    except Exception as e:
        logger.error("GA4 traffic_sources error: %s", e)
        return []


def get_daily_sessions(days: int = 90) -> list[dict]:
    """Daily session counts for trend line."""
    cache_key = f"daily_sessions_{days}"
    cached = _get_cached(cache_key)
    if cached:
        return cached

    client = _get_client()
    if not client:
        return []

    try:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Metric,
            RunReportRequest,
        )

        request = RunReportRequest(
            property=GA4_PROPERTY_ID,
            dimensions=[Dimension(name="date")],
            metrics=[Metric(name="sessions")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            order_bys=[{"dimension": {"dimension_name": "date"}}],
        )
        response = client.run_report(request)

        daily = []
        for row in response.rows:
            date_str = row.dimension_values[0].value  # YYYYMMDD
            daily.append({
                "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}",
                "sessions": int(row.metric_values[0].value),
            })

        _set_cached(cache_key, daily)
        return daily

    except Exception as e:
        logger.error("GA4 daily_sessions error: %s", e)
        return []


def get_conversion_event_report(days: int = 30) -> dict:
    """Return event totals with an explicit GA4 availability state."""
    cache_key = f"conversion_events_v2_{days}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return {"available": True, "events": cached, "error": None}

    client = _get_client()
    if not client:
        return {
            "available": False,
            "events": [],
            "error": "GA4 client unavailable",
        }

    try:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            Metric,
            RunReportRequest,
        )

        request = RunReportRequest(
            property=GA4_PROPERTY_ID,
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
            dimension_filter=FilterExpression(filter=Filter(
                field_name="eventName",
                in_list_filter=Filter.InListFilter(
                    values=sorted(CONVERSION_EVENT_NAMES),
                ),
            )),
        )
        response = client.run_report(request)

        events = []
        for row in response.rows:
            name = row.dimension_values[0].value
            if name in CONVERSION_EVENT_NAMES:
                events.append({
                    "event": name,
                    "count": int(row.metric_values[0].value),
                })

        events.sort(key=lambda x: x["count"], reverse=True)
        _set_cached(cache_key, events)
        return {"available": True, "events": events, "error": None}

    except Exception as e:
        logger.error("GA4 conversion_events error: %s", e)
        return {
            "available": False,
            "events": [],
            "error": "GA4 event query failed",
        }


def get_conversion_events(days: int = 30) -> list[dict]:
    """Compatibility wrapper returning independent event totals as a list."""
    return get_conversion_event_report(days=days)["events"]


def refresh_cache() -> int:
    """Force refresh all cached metrics. Returns count of metrics refreshed."""
    # Delete all cached entries
    if db is not None:
        try:
            db._table("gg_ga4_cache").delete().neq("cache_key", "").execute()
        except Exception:
            pass

    # Re-fetch all
    count = 0
    if get_top_pages():
        count += 1
    if get_traffic_sources():
        count += 1
    if get_daily_sessions():
        count += 1
    if get_conversion_events():
        count += 1

    return count
