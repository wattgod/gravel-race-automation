import re
from unittest.mock import patch


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
               return_value={"available": True, "events": event_totals, "error": None}):
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
         patch("mission_control.services.ga4._get_client", return_value=None):
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
         ):
        empty = client.get("/analytics/")

    assert empty.status_code == 200
    assert re.search(r">0</div>\s*<div[^>]*>Purchase events", empty.text)
    assert re.search(r">0</div>\s*<div[^>]*>Refund events", empty.text)
    assert "No lead or commerce events observed in this period." in empty.text
