"""GA4 Data API client — fetches analytics data with caching.

Caching uses Supabase (gg_ga4_cache table) when available.
When Supabase isn't configured (e.g. standalone daily_report.py),
caching is skipped and data is fetched fresh every call.
"""

from __future__ import annotations

import copy
import hashlib
import logging
import math
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
GA4_DATA_API_ROOT = "https://analyticsdata.googleapis.com"
NATIVE_FUNNEL_SCHEMA = "ga4_native_ordered_funnel/v1"
NATIVE_FUNNEL_CACHE_VERSION = "v1"
NATIVE_FUNNEL_METRICS = (
    "activeUsers",
    "funnelStepCompletionRate",
    "funnelStepAbandonments",
    "funnelStepAbandonmentRate",
)
NATIVE_FUNNEL_STEPS = (
    {"key": "race_page_view", "name": "Race page view"},
    {"key": "race_cta", "name": "Race CTA"},
    {"key": "plan_form_start", "name": "Plan form start"},
    {"key": "plan_form_submit", "name": "Plan form submit"},
    {"key": "training_plan_checkout", "name": "Training-plan checkout"},
    {"key": "training_plan_purchase", "name": "Training-plan purchase"},
)
_INTEGER_METRIC = re.compile(r"(?:0|[1-9][0-9]*)\Z")

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


def _get_funnel_session():
    """Create the REST transport needed by the alpha funnel endpoint."""
    if not GA4_PROPERTY_ID or not GA4_CREDENTIALS_PATH:
        return None

    try:
        from google.auth.transport.requests import AuthorizedSession
        from google.oauth2.service_account import Credentials

        credentials = Credentials.from_service_account_file(
            GA4_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/analytics.readonly"],
        )
        return AuthorizedSession(credentials)
    except Exception as e:
        logger.error("Failed to create GA4 funnel session: %s", e)
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _property_name() -> str | None:
    raw = str(GA4_PROPERTY_ID or "").strip()
    value = raw.removeprefix("properties/")
    if not value.isdigit():
        return None
    return f"properties/{value}"


def _property_ref(property_name: str) -> str:
    return hashlib.sha256(property_name.encode()).hexdigest()[:12]


def _valid_timezone_name(value) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        return None
    return value


def _get_property_reporting_timezone(client, property_name: str) -> str | None:
    """Read the property's IANA timezone from GA4 response metadata."""
    property_ref = _property_ref(property_name)
    cache_key = f"ga4_property_timezone_v1_{property_ref}"
    cached = _get_cached(cache_key)
    if isinstance(cached, dict):
        timezone_name = _valid_timezone_name(cached.get("timezone"))
        if timezone_name:
            return timezone_name

    try:
        from google.analytics.data_v1beta.types import (
            DateRange,
            Metric,
            RunReportRequest,
        )

        response = client.run_report(RunReportRequest(
            property=property_name,
            metrics=[Metric(name="activeUsers")],
            date_ranges=[DateRange(start_date="yesterday", end_date="yesterday")],
            limit=1,
        ))
        timezone_name = _valid_timezone_name(
            getattr(getattr(response, "metadata", None), "time_zone", None))
        if timezone_name:
            _set_cached(cache_key, {"timezone": timezone_name})
        return timezone_name
    except Exception as e:
        logger.error("GA4 property timezone query failed: %s", e)
        return None


def _funnel_event(name: str) -> dict:
    return {"funnelEventFilter": {"eventName": name}}


def _funnel_field(name: str, value: str, match_type: str) -> dict:
    return {"funnelFieldFilter": {
        "fieldName": name,
        "stringFilter": {
            "matchType": match_type,
            "value": value,
            "caseSensitive": True,
        },
    }}


def _funnel_and(*expressions: dict) -> dict:
    return {"andGroup": {"expressions": list(expressions)}}


def _funnel_or(*expressions: dict) -> dict:
    return {"orGroup": {"expressions": list(expressions)}}


def _native_funnel_request(start_date: str, end_date: str) -> dict:
    race_path = _funnel_field(
        "unifiedPagePathScreen", "/race/", "BEGINS_WITH")
    form_path = _funnel_field(
        "unifiedPagePathScreen", "/questionnaire/", "BEGINS_WITH")
    steps = (
        _funnel_and(_funnel_event("page_view"), race_path),
        _funnel_and(_funnel_event("cta_click"), race_path),
        _funnel_and(_funnel_or(
            _funnel_event("form_start"), _funnel_event("tp_form_start")),
            form_path),
        _funnel_and(_funnel_or(
            _funnel_event("form_submit"), _funnel_event("tp_form_submit")),
            form_path),
        _funnel_and(
            _funnel_event("begin_checkout"),
            _funnel_field("itemCategory", "training_plan", "EXACT")),
        _funnel_and(
            _funnel_event("purchase"),
            _funnel_field("itemCategory", "training_plan", "EXACT")),
    )
    return {
        "dateRanges": [{"startDate": start_date, "endDate": end_date}],
        "funnel": {
            "isOpenFunnel": False,
            "steps": [
                {"name": definition["name"], "filterExpression": expression}
                for definition, expression in zip(NATIVE_FUNNEL_STEPS, steps)
            ],
        },
        "returnPropertyQuota": True,
    }


def _parse_int(value) -> int:
    if type(value) is not str or _INTEGER_METRIC.fullmatch(value) is None:
        raise ValueError("invalid integer metric")
    return int(value)


def _parse_rate(value) -> float:
    if type(value) is not str:
        raise ValueError("invalid rate metric")
    parsed = float(value)
    if not math.isfinite(parsed) or parsed < 0 or parsed > 1:
        raise ValueError("rate outside [0, 1]")
    return parsed


def _valid_subreport_metadata(metadata) -> bool:
    if not isinstance(metadata, dict):
        return False
    if ("subjectToThresholding" in metadata
            and type(metadata["subjectToThresholding"]) is not bool):
        return False
    if "samplingMetadatas" not in metadata:
        return True
    samples = metadata["samplingMetadatas"]
    if not isinstance(samples, list):
        return False
    for sample in samples:
        if not isinstance(sample, dict):
            return False
        for key in ("samplesReadCount", "samplingSpaceSize"):
            value = sample.get(key)
            if type(value) is not str or _INTEGER_METRIC.fullmatch(value) is None:
                return False
    return True


def _subreport_headers(subreport: dict, expected_metrics: tuple[str, ...]) -> None:
    if not isinstance(subreport, dict):
        raise ValueError("subreport missing")
    dimensions = subreport.get("dimensionHeaders")
    if dimensions != [{"name": "funnelStepName"}]:
        raise ValueError("unexpected dimension headers")
    headers = subreport.get("metricHeaders")
    if not isinstance(headers, list):
        raise ValueError("metric headers missing")
    names = tuple(item.get("name") for item in headers if isinstance(item, dict))
    if len(names) != len(headers) or names not in {
            expected_metrics, expected_metrics + expected_metrics}:
        raise ValueError("unexpected metric headers")
    if not _valid_subreport_metadata(subreport.get("metadata", {})):
        raise ValueError("unexpected report metadata")


def _parse_funnel_rows(subreport: dict, metric_count: int) -> list[dict]:
    rows = subreport.get("rows", [])
    if not isinstance(rows, list) or len(rows) > len(NATIVE_FUNNEL_STEPS):
        raise ValueError("unexpected row count")
    parsed = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("unexpected row")
        dimensions = row.get("dimensionValues")
        metrics = row.get("metricValues")
        expected_name = f"{index + 1}. {NATIVE_FUNNEL_STEPS[index]['name']}"
        if (not isinstance(dimensions, list) or len(dimensions) != 1
                or not isinstance(dimensions[0], dict)
                or dimensions[0].get("value") != expected_name):
            raise ValueError("unexpected step row")
        if (not isinstance(metrics, list) or len(metrics) != metric_count
                or any(not isinstance(item, dict) or "value" not in item
                       for item in metrics)):
            raise ValueError("unexpected metric row")
        parsed.append({"name": expected_name, "values": [
            item["value"] for item in metrics]})
    return parsed


def _parse_native_funnel_response(body: dict) -> tuple[list[dict], dict]:
    if not isinstance(body, dict) or body.get("kind") != "analyticsData#runFunnelReport":
        raise ValueError("unexpected response kind")
    table = body.get("funnelTable")
    visualization = body.get("funnelVisualization")
    _subreport_headers(table, NATIVE_FUNNEL_METRICS)
    _subreport_headers(visualization, ("activeUsers",))
    table_rows = _parse_funnel_rows(table, 4)
    visual_rows = _parse_funnel_rows(visualization, 1)
    if len(table_rows) != len(visual_rows):
        raise ValueError("subreport row counts differ")

    steps = []
    for index, definition in enumerate(NATIVE_FUNNEL_STEPS):
        if index >= len(table_rows):
            steps.append({
                **definition,
                "position": index + 1,
                "present": False,
                "users": None,
                "completion_rate": None,
                "abandonments": None,
                "abandonment_rate": None,
            })
            continue
        table_values = table_rows[index]["values"]
        visual_values = visual_rows[index]["values"]
        users = _parse_int(table_values[0])
        if users != _parse_int(visual_values[0]):
            raise ValueError("subreport active-user values differ")
        steps.append({
            **definition,
            "position": index + 1,
            "present": True,
            "users": users,
            "completion_rate": _parse_rate(table_values[1]),
            "abandonments": _parse_int(table_values[2]),
            "abandonment_rate": _parse_rate(table_values[3]),
        })

    metadata = {
        "funnel_table": copy.deepcopy(table.get("metadata", {})),
        "funnel_visualization": copy.deepcopy(visualization.get("metadata", {})),
    }
    return steps, metadata


def _unavailable_funnel(error: str, error_code: str, *, period=None,
                        attempted_at: str | None = None, provenance=None) -> dict:
    return {
        "schema": NATIVE_FUNNEL_SCHEMA,
        "available": False,
        "error": error,
        "error_code": error_code,
        "attempted_at": attempted_at,
        "fetched_at": None,
        "period": period,
        "steps": [],
        "metadata": {},
        "provenance": provenance or {},
    }


def _valid_cached_funnel(value, period: dict, property_ref: str) -> bool:
    if not (
            isinstance(value, dict)
            and value.get("schema") == NATIVE_FUNNEL_SCHEMA
            and value.get("available") is True
            and value.get("period") == period
            and isinstance(value.get("fetched_at"), str)
            and isinstance(value.get("steps"), list)
            and len(value["steps"]) == len(NATIVE_FUNNEL_STEPS)
            and isinstance(value.get("metadata"), dict)
            and set(value["metadata"]) == {
                "funnel_table", "funnel_visualization"}
            and _valid_subreport_metadata(value["metadata"]["funnel_table"])
            and _valid_subreport_metadata(value["metadata"]["funnel_visualization"])
            and isinstance(value.get("request_contract"), dict)
            and value["request_contract"].get("closed") is True
            and value["request_contract"].get("ordered") is True
            and value["request_contract"].get("directly_followed") is False
            and value["request_contract"].get("steps") == list(NATIVE_FUNNEL_STEPS)
            and isinstance(value.get("provenance"), dict)
            and value["provenance"].get("request_version") == NATIVE_FUNNEL_CACHE_VERSION
            and value["provenance"].get("property_ref") == property_ref
            and value["provenance"].get("response_kind")
            == "analyticsData#runFunnelReport"):
        return False
    for index, (step, definition) in enumerate(
            zip(value["steps"], NATIVE_FUNNEL_STEPS), start=1):
        if (not isinstance(step, dict)
                or step.get("key") != definition["key"]
                or step.get("name") != definition["name"]
                or step.get("position") != index
                or not isinstance(step.get("present"), bool)):
            return False
        users = step.get("users")
        if step["present"]:
            if type(users) is not int or users < 0:
                return False
            if (type(step.get("completion_rate")) is not float
                    or not math.isfinite(step["completion_rate"])
                    or not 0 <= step["completion_rate"] <= 1
                    or type(step.get("abandonments")) is not int
                    or step["abandonments"] < 0
                    or type(step.get("abandonment_rate")) is not float
                    or not math.isfinite(step["abandonment_rate"])
                    or not 0 <= step["abandonment_rate"] <= 1):
                return False
        elif users is not None:
            return False
        elif any(step.get(key) is not None for key in (
                "completion_rate", "abandonments", "abandonment_rate")):
            return False
    return True


def get_ordered_funnel_report(days: int = 30) -> dict:
    """Return GA4's closed, ordered active-user funnel for complete days."""
    now = _utc_now()
    attempted_at = now.isoformat()
    if not isinstance(days, int) or isinstance(days, bool) or days < 1:
        return _unavailable_funnel(
            "Invalid funnel reporting window", "INVALID_WINDOW",
            attempted_at=attempted_at)

    property_name = _property_name()
    if property_name is None:
        return _unavailable_funnel(
            "GA4 property is unavailable", "PROPERTY_UNAVAILABLE",
            attempted_at=attempted_at)
    property_ref = _property_ref(property_name)
    provenance = {
        "provider": "Google Analytics Data API",
        "method": "v1alpha properties.runFunnelReport",
        "request_version": NATIVE_FUNNEL_CACHE_VERSION,
        "property_ref": property_ref,
        "cache_hit": False,
    }

    client = _get_client()
    if client is None:
        return _unavailable_funnel(
            "GA4 client unavailable", "CLIENT_UNAVAILABLE",
            attempted_at=attempted_at, provenance=provenance)
    timezone_name = _get_property_reporting_timezone(client, property_name)
    if timezone_name is None:
        return _unavailable_funnel(
            "GA4 property timezone unavailable", "TIMEZONE_UNAVAILABLE",
            attempted_at=attempted_at, provenance=provenance)

    local_today = now.astimezone(ZoneInfo(timezone_name)).date()
    end_date = local_today - timedelta(days=1)
    start_date = end_date - timedelta(days=days - 1)
    period = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "timezone": timezone_name,
        "complete_days": days,
    }
    cache_key = (
        f"native_ordered_funnel_{NATIVE_FUNNEL_CACHE_VERSION}_{property_ref}_"
        f"{period['start_date']}_{period['end_date']}_{timezone_name}"
    )
    cached = _get_cached(cache_key)
    if _valid_cached_funnel(cached, period, property_ref):
        result = copy.deepcopy(cached)
        result["provenance"]["cache_hit"] = True
        return result

    session = _get_funnel_session()
    if session is None:
        return _unavailable_funnel(
            "GA4 funnel client unavailable", "CLIENT_UNAVAILABLE",
            period=period, attempted_at=attempted_at, provenance=provenance)

    request_body = _native_funnel_request(
        period["start_date"], period["end_date"])
    url = f"{GA4_DATA_API_ROOT}/v1alpha/{property_name}:runFunnelReport"
    try:
        response = session.post(url, json=request_body, timeout=60)
        body = response.json()
    except Exception as e:
        logger.error("GA4 native funnel request failed: %s", e)
        return _unavailable_funnel(
            "GA4 native funnel query failed", "API_FAILURE",
            period=period, attempted_at=attempted_at, provenance=provenance)

    if response.status_code != 200:
        provider_error = body.get("error") if isinstance(body, dict) else None
        provider_status = (provider_error.get("status")
                           if isinstance(provider_error, dict) else None)
        error_code = (str(provider_status)[:80] if provider_status
                      else f"HTTP_{response.status_code}")
        return _unavailable_funnel(
            "GA4 native funnel query failed", error_code,
            period=period, attempted_at=attempted_at, provenance={
                **provenance, "http_status": response.status_code})

    try:
        steps, metadata = _parse_native_funnel_response(body)
    except (KeyError, OverflowError, TypeError, ValueError) as e:
        logger.error("GA4 native funnel response shape failed: %s", e)
        return _unavailable_funnel(
            "GA4 native funnel response shape is unsupported",
            "UNKNOWN_RESPONSE_SHAPE", period=period,
            attempted_at=attempted_at, provenance=provenance)

    result = {
        "schema": NATIVE_FUNNEL_SCHEMA,
        "available": True,
        "error": None,
        "error_code": None,
        "attempted_at": attempted_at,
        "fetched_at": attempted_at,
        "period": period,
        "steps": steps,
        "metadata": metadata,
        "request_contract": {
            "closed": True,
            "ordered": True,
            "directly_followed": False,
            "steps": copy.deepcopy(list(NATIVE_FUNNEL_STEPS)),
        },
        "provenance": {
            **provenance,
            "response_kind": body.get("kind"),
        },
    }
    _set_cached(cache_key, result)
    return result


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
    if get_ordered_funnel_report().get("available") is True:
        count += 1

    return count
