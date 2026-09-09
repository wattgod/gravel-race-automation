import sys
from types import ModuleType, SimpleNamespace

from mission_control.services import ga4


def test_conversion_event_allowlist_includes_commerce_lifecycle():
    assert {
        "view_item",
        "add_to_cart",
        "begin_checkout",
        "add_payment_info",
        "purchase",
        "refund",
    } <= getattr(ga4, "CONVERSION_EVENT_NAMES", set())


def test_conversion_event_allowlist_keeps_both_deployed_form_generations():
    assert {
        "form_start",
        "tp_form_start",
        "form_submit",
        "tp_form_submit",
    } <= getattr(ga4, "CONVERSION_EVENT_NAMES", set())


def test_conversion_cache_key_changes_with_expanded_event_contract(monkeypatch):
    seen = []
    monkeypatch.setattr(ga4, "_get_cached", lambda key: seen.append(key) or None)
    monkeypatch.setattr(ga4, "_get_client", lambda: None)

    assert ga4.get_conversion_events(days=14) == []
    assert seen == ["conversion_events_v2_14"]


def test_conversion_query_filters_and_returns_commerce_events(monkeypatch):
    class Message:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Filter(Message):
        class InListFilter(Message):
            pass

    fake_types = ModuleType("google.analytics.data_v1beta.types")
    for name, value in {
        "DateRange": Message,
        "Dimension": Message,
        "Filter": Filter,
        "FilterExpression": Message,
        "Metric": Message,
        "RunReportRequest": Message,
    }.items():
        setattr(fake_types, name, value)
    monkeypatch.setitem(sys.modules, "google.analytics.data_v1beta.types", fake_types)

    def row(name, count):
        return SimpleNamespace(
            dimension_values=[SimpleNamespace(value=name)],
            metric_values=[SimpleNamespace(value=str(count))],
        )

    class Client:
        request = None

        def run_report(self, request):
            self.request = request
            return SimpleNamespace(rows=[
                row("email_capture", 3),
                row("purchase", 2),
                row("refund", 1),
            ])

    client = Client()
    monkeypatch.setattr(ga4, "_get_cached", lambda key: None)
    monkeypatch.setattr(ga4, "_set_cached", lambda key, data: None)
    monkeypatch.setattr(ga4, "_get_client", lambda: client)

    assert ga4.get_conversion_events(days=7) == [
        {"event": "email_capture", "count": 3},
        {"event": "purchase", "count": 2},
        {"event": "refund", "count": 1},
    ]
    event_filter = client.request.dimension_filter.filter
    assert event_filter.field_name == "eventName"
    assert set(event_filter.in_list_filter.values) == ga4.CONVERSION_EVENT_NAMES


def test_event_summary_keeps_refunds_out_of_purchase_and_lead_counts():
    events = [
        {"event": "email_capture", "count": 7},
        {"event": "plan_request", "count": 3},
        {"event": "begin_checkout", "count": 4},
        {"event": "purchase", "count": 2},
        {"event": "refund", "count": 5},
        {"event": "add_to_cart", "count": 90},
    ]

    assert ga4.summarize_event_totals(events) == {
        "email_capture_events": 7,
        "plan_request_events": 3,
        "checkout_start_events": 4,
        "purchase_events": 2,
        "refund_events": 5,
    }
