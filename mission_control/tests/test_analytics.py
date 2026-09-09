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
         patch("mission_control.routers.analytics.get_conversion_events",
               return_value=event_totals):
        response = client.get("/analytics/")

    assert response.status_code == 200
    assert "Lead and commerce event totals (30 days)" in response.text
    assert "Independent event counts; no cross-stage conversion rate." in response.text
    assert "Conversions (30d)" not in response.text
    assert re.search(r">2</div>\s*<div[^>]*>Purchase events \(30d\)</div>", response.text)
    assert re.search(r">5</div>\s*<div[^>]*>Refund events \(30d\)</div>", response.text)
    assert ">108</div>" not in response.text
