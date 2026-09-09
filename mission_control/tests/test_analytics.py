import re
from unittest.mock import patch


def _native_funnel_report(*, available=True):
    return {
        "available": available,
        "error": None if available else "GA4 native funnel query failed",
        "error_code": None if available else "PERMISSION_DENIED",
        "fetched_at": "2026-09-09T05:30:00+00:00" if available else None,
        "period": {
            "start_date": "2026-08-09", "end_date": "2026-09-07",
            "timezone": "America/Denver", "complete_days": 30,
        } if available else None,
        "steps": [
            {"position": 1, "name": "Race page view", "present": True, "users": 100,
             "completion_rate": 0.2},
            {"position": 2, "name": "Race CTA", "present": True, "users": 20,
             "completion_rate": 0.25},
            {"position": 3, "name": "Plan form start", "present": True, "users": 5,
             "completion_rate": 0.4},
            {"position": 4, "name": "Plan form submit", "present": True, "users": 2,
             "completion_rate": 0.0},
            {"position": 5, "name": "Training-plan checkout", "present": True, "users": 0,
             "completion_rate": 0.0},
            {"position": 6, "name": "Training-plan purchase", "present": False, "users": None,
             "completion_rate": None},
        ] if available else [],
        "metadata": {
            "funnel_table": {"subjectToThresholding": True},
            "funnel_visualization": {},
        } if available else {},
        "provenance": {"cache_hit": False} if available else {},
    }


def _common_analytics_patches(funnel=None):
    return (
        patch("mission_control.routers.analytics.get_top_pages", return_value=[]),
        patch("mission_control.routers.analytics.get_traffic_sources", return_value=[]),
        patch("mission_control.routers.analytics.get_daily_sessions", return_value=[]),
        patch(
            "mission_control.routers.analytics.get_conversion_event_report",
            return_value={"available": True, "events": [], "error": None},
        ),
        patch(
            "mission_control.routers.analytics.get_ordered_funnel_report",
            return_value=funnel or _native_funnel_report(),
        ),
    )


def test_analytics_page_renders_distinct_event_counts_without_combined_kpi(
        client, fake_db):
    event_totals = [
        {"event": "add_to_cart", "count": 90},
        {"event": "email_capture", "count": 7},
        {"event": "begin_checkout", "count": 4},
        {"event": "purchase", "count": 2},
        {"event": "refund", "count": 5},
    ]
    with patch("mission_control.routers.analytics.get_top_pages", return_value=[]), \
         patch("mission_control.routers.analytics.get_traffic_sources", return_value=[]), \
         patch("mission_control.routers.analytics.get_daily_sessions", return_value=[]), \
         patch("mission_control.routers.analytics.get_conversion_event_report",
               return_value={"available": True, "events": event_totals, "error": None}), \
         patch("mission_control.routers.analytics.get_ordered_funnel_report",
               return_value=_native_funnel_report()):
        response = client.get("/analytics/")

    assert response.status_code == 200
    assert "Lead and commerce event totals (30 days)" in response.text
    assert "Independent event counts; no cross-stage conversion rate." in response.text
    assert "Conversions (30d)" not in response.text
    assert re.search(r">2</div>\s*<div[^>]*>Purchase events \(30d\)</div>", response.text)
    assert re.search(r">5</div>\s*<div[^>]*>Refund events \(30d\)</div>", response.text)
    assert ">108</div>" not in response.text


def test_analytics_page_distinguishes_ga4_failure_from_verified_zero(client, fake_db):
    common = (
        patch("mission_control.routers.analytics.get_top_pages", return_value=[]),
        patch("mission_control.routers.analytics.get_traffic_sources", return_value=[]),
        patch("mission_control.routers.analytics.get_daily_sessions", return_value=[]),
    )
    with common[0], common[1], common[2], \
         patch("mission_control.services.ga4._get_cached", return_value=None), \
         patch("mission_control.services.ga4._get_client", return_value=None), \
         patch("mission_control.routers.analytics.get_ordered_funnel_report",
               return_value=_native_funnel_report(available=False)):
        failed = client.get("/analytics/")

    assert failed.status_code == 200
    assert "GA4 event data unavailable" in failed.text
    assert re.search(r">Unavailable</div>\s*<div[^>]*>Purchase events", failed.text)
    assert re.search(r">Unavailable</div>\s*<div[^>]*>Refund events", failed.text)

    with patch("mission_control.routers.analytics.get_top_pages", return_value=[]), \
         patch("mission_control.routers.analytics.get_traffic_sources", return_value=[]), \
         patch("mission_control.routers.analytics.get_daily_sessions", return_value=[]), \
         patch(
             "mission_control.routers.analytics.get_conversion_event_report",
             return_value={"available": True, "events": [], "error": None},
         ), \
         patch(
             "mission_control.routers.analytics.get_ordered_funnel_report",
             return_value=_native_funnel_report(),
         ):
        empty = client.get("/analytics/")

    assert empty.status_code == 200
    assert re.search(r">0</div>\s*<div[^>]*>Purchase events", empty.text)
    assert re.search(r">0</div>\s*<div[^>]*>Refund events", empty.text)
    assert "No lead or commerce events observed in this period." in empty.text


def test_analytics_page_renders_native_funnel_with_absent_distinct_from_zero(
        client, fake_db):
    patches = _common_analytics_patches()
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        response = client.get("/analytics/")

    assert response.status_code == 200
    assert "Ordered user funnel" in response.text
    assert "Aug 9–Sep 7, 2026" in response.text
    assert "America/Denver" in response.text
    assert "complete days" in response.text
    assert "Broad race-page CTA" in response.text
    assert "behavioral user progression" in response.text
    assert re.search(r"Training-plan checkout.*?>\s*0\s*<", response.text, re.DOTALL)
    assert re.search(r"Training-plan purchase.*?>\s*Absent\s*<", response.text, re.DOTALL)
    assert "paid customers" not in response.text.lower()
    assert "exact-plan selection" not in response.text.lower()
    assert "subject to GA4 thresholding" in response.text


def test_analytics_page_renders_native_funnel_unavailable_without_zeroes(
        client, fake_db):
    patches = _common_analytics_patches(_native_funnel_report(available=False))
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        response = client.get("/analytics/")

    assert response.status_code == 200
    assert "Ordered user funnel unavailable" in response.text
    assert "PERMISSION_DENIED" in response.text
    funnel = response.text.split("Ordered user funnel", 1)[1].split("Traffic Sources", 1)[0]
    assert ">0<" not in funnel


def test_analytics_page_defensively_ignores_malformed_funnel_metadata(
        client, fake_db):
    report = _native_funnel_report()
    report["metadata"] = {
        "funnel_table": {
            "samplingMetadatas": 7,
            "subjectToThresholding": "true",
        },
        "funnel_visualization": {},
    }
    patches = _common_analytics_patches(report)
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        response = client.get("/analytics/")

    assert response.status_code == 200
    assert "Ordered user funnel" in response.text
    assert "GA4 sampled this report" not in response.text
    assert "subject to GA4 thresholding" not in response.text
