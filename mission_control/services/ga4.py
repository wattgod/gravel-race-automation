"""GA4 Data API client — fetches analytics data with caching."""

import json
import logging
from datetime import datetime, timedelta, timezone

from mission_control import supabase_client as db
from mission_control.config import GA4_CREDENTIALS_PATH, GA4_PROPERTY_ID

logger = logging.getLogger(__name__)

CACHE_TTL_HOURS = 4


def _get_cached(cache_key: str) -> dict | None:
    """Get cached data if fresh enough."""
    row = db.select_one("gg_ga4_cache", match={"cache_key": cache_key})
    if not row:
        return None

    fetched_at = datetime.fromisoformat(row["fetched_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) - fetched_at > timedelta(hours=CACHE_TTL_HOURS):
        return None

    return row["data"]


def _set_cached(cache_key: str, data: dict) -> None:
    """Store data in cache."""
    db.upsert("gg_ga4_cache", {
        "cache_key": cache_key,
        "data": data,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }, on_conflict="cache_key")


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


def get_conversion_events(days: int = 30) -> list[dict]:
    """Key conversion events: email captures, plan requests, quiz completions."""
    cache_key = f"conversion_events_{days}"
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
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
            date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
        )
        response = client.run_report(request)

        # Filter to conversion-relevant events
        conversion_events = {
            "email_capture", "prep_kit_unlock", "quiz_complete",
            "plan_request", "exit_intent_capture", "fueling_calculate",
            "review_submit",
        }

        events = []
        for row in response.rows:
            name = row.dimension_values[0].value
            if name in conversion_events:
                events.append({
                    "event": name,
                    "count": int(row.metric_values[0].value),
                })

        events.sort(key=lambda x: x["count"], reverse=True)
        _set_cached(cache_key, events)
        return events

    except Exception as e:
        logger.error("GA4 conversion_events error: %s", e)
        return []


def refresh_cache() -> int:
    """Force refresh all cached metrics. Returns count of metrics refreshed."""
    # Delete all cached entries
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
