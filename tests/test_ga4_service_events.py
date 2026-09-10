import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from mission_control.services import ga4


FUNNEL_FIXTURE = Path(__file__).parent / "fixtures" / "ga4_native_closed_funnel.json"


class Message:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class Filter(Message):
    class InListFilter(Message):
        pass


def _install_fake_ga4_types(monkeypatch):
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
    _install_fake_ga4_types(monkeypatch)

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


def test_conversion_event_report_marks_missing_client_unavailable(monkeypatch):
    monkeypatch.setattr(ga4, "_get_cached", lambda key: None)
    monkeypatch.setattr(ga4, "_get_client", lambda: None)

    assert ga4.get_conversion_event_report(days=7) == {
        "available": False,
        "events": [],
        "error": "GA4 client unavailable",
    }


def test_conversion_event_report_does_not_cache_api_failure(monkeypatch):
    _install_fake_ga4_types(monkeypatch)
    cached = []

    class Client:
        def run_report(self, request):
            raise RuntimeError("temporary GA4 failure")

    monkeypatch.setattr(ga4, "_get_cached", lambda key: None)
    monkeypatch.setattr(ga4, "_set_cached", lambda key, data: cached.append(data))
    monkeypatch.setattr(ga4, "_get_client", lambda: Client())

    assert ga4.get_conversion_event_report(days=7) == {
        "available": False,
        "events": [],
        "error": "GA4 event query failed",
    }
    assert cached == []


def test_conversion_event_report_preserves_successful_empty_cache(monkeypatch):
    monkeypatch.setattr(ga4, "_get_cached", lambda key: [])
    monkeypatch.setattr(
        ga4, "_get_client", lambda: (_ for _ in ()).throw(AssertionError("cache miss")))

    assert ga4.get_conversion_event_report(days=7) == {
        "available": True,
        "events": [],
        "error": None,
    }


def test_conversion_event_report_caches_successful_empty_response(monkeypatch):
    _install_fake_ga4_types(monkeypatch)
    cached = []

    class Client:
        def run_report(self, request):
            return SimpleNamespace(rows=[])

    monkeypatch.setattr(ga4, "_get_cached", lambda key: None)
    monkeypatch.setattr(ga4, "_set_cached", lambda key, data: cached.append((key, data)))
    monkeypatch.setattr(ga4, "_get_client", lambda: Client())

    assert ga4.get_conversion_event_report(days=7) == {
        "available": True,
        "events": [],
        "error": None,
    }
    assert cached == [("conversion_events_v2_7", [])]


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


class _TimezoneClient:
    def __init__(self, timezone_name="America/Denver"):
        self.timezone_name = timezone_name
        self.requests = []

    def run_report(self, request):
        self.requests.append(request)
        return SimpleNamespace(metadata=SimpleNamespace(time_zone=self.timezone_name))


class _HttpResponse:
    def __init__(self, body, status_code=200):
        self._body = body
        self.status_code = status_code

    def json(self):
        return copy.deepcopy(self._body)


class _FunnelSession:
    def __init__(self, body, status_code=200):
        self.body = body
        self.status_code = status_code
        self.calls = []

    def post(self, url, *, json, timeout):
        self.calls.append({"url": url, "json": json, "timeout": timeout})
        return _HttpResponse(self.body, self.status_code)


def _captured_response():
    wrapped = json.loads(FUNNEL_FIXTURE.read_text())
    response = wrapped["response"]
    return {
        "kind": response["kind"],
        "funnelTable": response["funnel_table"],
        "funnelVisualization": response["funnel_visualization"],
    }


def _install_funnel_boundaries(monkeypatch, body=None, *, status_code=200,
                               timezone_name="America/Denver"):
    client = _TimezoneClient(timezone_name)
    session = _FunnelSession(body or _captured_response(), status_code)
    writes = []
    monkeypatch.setattr(ga4, "_get_client", lambda: client)
    monkeypatch.setattr(ga4, "_get_funnel_session", lambda: session)
    monkeypatch.setattr(ga4, "_get_cached", lambda key: None)
    monkeypatch.setattr(ga4, "_set_cached", lambda key, data: writes.append((key, data)))
    monkeypatch.setattr(
        ga4, "_utc_now",
        lambda: datetime(2026, 9, 9, 5, 30, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(ga4, "GA4_PROPERTY_ID", "properties/123456")
    return client, session, writes


def test_native_funnel_parses_captured_repeated_headers_and_preserves_absence(
        monkeypatch):
    client, session, writes = _install_funnel_boundaries(monkeypatch)

    report = ga4.get_ordered_funnel_report(days=30)

    assert report["available"] is True
    assert report["period"] == {
        "start_date": "2026-08-09",
        "end_date": "2026-09-07",
        "timezone": "America/Denver",
        "complete_days": 30,
    }
    assert [step["users"] for step in report["steps"]] == [4601, 186, 10, 2, None, None]
    assert [step["present"] for step in report["steps"]] == [True] * 4 + [False] * 2
    assert report["steps"][3]["completion_rate"] == 0.0
    assert report["steps"][4]["completion_rate"] is None
    assert report["fetched_at"] == "2026-09-09T05:30:00+00:00"
    assert report["provenance"]["cache_hit"] is False
    assert report["provenance"]["method"] == "v1alpha properties.runFunnelReport"
    assert len(client.requests) == 1
    assert client.requests[0].property == "properties/123456"
    assert client.requests[0].date_ranges[0].start_date == "yesterday"
    assert client.requests[0].date_ranges[0].end_date == "yesterday"
    assert session.calls[0]["url"].endswith("/v1alpha/properties/123456:runFunnelReport")
    payload = session.calls[0]["json"]
    assert payload["dateRanges"] == [{"startDate": "2026-08-09", "endDate": "2026-09-07"}]
    assert payload["funnel"]["isOpenFunnel"] is False
    assert [step["name"] for step in payload["funnel"]["steps"]] == [
        "Race page view", "Race CTA", "Plan form start", "Training-plan checkout",
        "Plan form submit", "Training-plan purchase",
    ]
    assert "unifiedPagePathScreen" in json.dumps(payload)
    assert '"itemCategory"' in json.dumps(payload)
    assert '"training_plan"' in json.dumps(payload)
    event_names = {
        value
        for value in (
            "page_view", "cta_click", "form_start", "tp_form_start",
            "form_submit", "tp_form_submit", "begin_checkout", "purchase",
        )
        if f'"eventName": "{value}"' in json.dumps(payload)
    }
    assert event_names == {
        "page_view", "cta_click", "form_start", "tp_form_start",
        "form_submit", "tp_form_submit", "begin_checkout", "purchase",
    }
    funnel_writes = [item for item in writes if item[0].startswith("native_ordered_funnel_")]
    assert len(funnel_writes) == 1


def test_native_funnel_preserves_provider_zero_as_present(monkeypatch):
    body = _captured_response()
    table_row = {
        "dimensionValues": [{"value": "5. Plan form submit"}],
        "metricValues": [
            {"value": "0"}, {"value": "0"}, {"value": "0"}, {"value": "0"},
        ],
    }
    visual_row = {
        "dimensionValues": [{"value": "5. Plan form submit"}],
        "metricValues": [{"value": "0"}],
    }
    body["funnelTable"]["rows"].append(table_row)
    body["funnelVisualization"]["rows"].append(visual_row)
    _install_funnel_boundaries(monkeypatch, body)

    report = ga4.get_ordered_funnel_report()

    assert report["steps"][4]["present"] is True
    assert report["steps"][4]["users"] == 0
    assert report["steps"][5]["present"] is False
    assert report["steps"][5]["users"] is None


@pytest.mark.parametrize(("metric_index", "bad_value"), [
    (0, True),
    (0, 1.9),
    (0, float("inf")),
    (0, "1.9"),
    (1, True),
])
def test_native_funnel_rejects_non_schema_provider_metrics_without_caching(
        monkeypatch, metric_index, bad_value):
    body = _captured_response()
    body["funnelTable"]["rows"][0]["metricValues"][metric_index]["value"] = bad_value
    if metric_index == 0:
        body["funnelVisualization"]["rows"][0]["metricValues"][0]["value"] = bad_value
    _client, _session, writes = _install_funnel_boundaries(monkeypatch, body)

    report = ga4.get_ordered_funnel_report()

    assert report["available"] is False
    assert report["error_code"] == "UNKNOWN_RESPONSE_SHAPE"
    assert not any(key.startswith("native_ordered_funnel_") for key, _data in writes)


def test_native_funnel_rejects_unknown_shape_without_caching(monkeypatch):
    body = _captured_response()
    body["funnelTable"]["metricHeaders"][0]["name"] = "sessions"
    _client, _session, writes = _install_funnel_boundaries(monkeypatch, body)

    report = ga4.get_ordered_funnel_report()

    assert report["available"] is False
    assert report["error_code"] == "UNKNOWN_RESPONSE_SHAPE"
    assert not any(key.startswith("native_ordered_funnel_") for key, _data in writes)


def test_native_funnel_distinguishes_api_failure_from_successful_empty(monkeypatch):
    error = {"error": {"status": "PERMISSION_DENIED", "message": "denied"}}
    _client, _session, writes = _install_funnel_boundaries(
        monkeypatch, error, status_code=403)

    failed = ga4.get_ordered_funnel_report()

    assert failed["available"] is False
    assert failed["error_code"] == "PERMISSION_DENIED"
    assert not any(key.startswith("native_ordered_funnel_") for key, _data in writes)

    empty = _captured_response()
    empty["funnelTable"]["rows"] = []
    empty["funnelVisualization"]["rows"] = []
    _client, _session, writes = _install_funnel_boundaries(monkeypatch, empty)
    valid_empty = ga4.get_ordered_funnel_report()

    assert valid_empty["available"] is True
    assert all(step["present"] is False and step["users"] is None
               for step in valid_empty["steps"])
    assert len([key for key, _data in writes
                if key.startswith("native_ordered_funnel_")]) == 1


def test_native_funnel_retains_sampling_and_threshold_metadata(monkeypatch):
    body = _captured_response()
    body["funnelTable"]["metadata"] = {
        "samplingMetadatas": [{"samplesReadCount": "50", "samplingSpaceSize": "100"}],
        "subjectToThresholding": True,
    }
    _install_funnel_boundaries(monkeypatch, body)

    report = ga4.get_ordered_funnel_report()

    assert report["metadata"]["funnel_table"] == body["funnelTable"]["metadata"]


@pytest.mark.parametrize("bad_metadata", [
    {"samplingMetadatas": 7},
    {"samplingMetadatas": [{"samplesReadCount": 50,
                             "samplingSpaceSize": "100"}]},
    {"subjectToThresholding": "true"},
])
def test_native_funnel_rejects_malformed_provider_metadata_without_caching(
        monkeypatch, bad_metadata):
    body = _captured_response()
    body["funnelTable"]["metadata"] = bad_metadata
    _client, _session, writes = _install_funnel_boundaries(monkeypatch, body)

    report = ga4.get_ordered_funnel_report()

    assert report["available"] is False
    assert report["error_code"] == "UNKNOWN_RESPONSE_SHAPE"
    assert not any(key.startswith("native_ordered_funnel_") for key, _data in writes)


def test_native_funnel_cache_is_versioned_and_window_specific(monkeypatch):
    seen = []
    client = _TimezoneClient()
    monkeypatch.setattr(ga4, "_get_client", lambda: client)
    monkeypatch.setattr(
        ga4, "_get_property_reporting_timezone",
        lambda _client, _property: "America/Denver",
    )
    monkeypatch.setattr(ga4, "_get_cached", lambda key: seen.append(key) or None)
    monkeypatch.setattr(ga4, "_get_funnel_session", lambda: None)
    monkeypatch.setattr(ga4, "GA4_PROPERTY_ID", "properties/123456")

    monkeypatch.setattr(
        ga4, "_utc_now",
        lambda: datetime(2026, 9, 9, 5, 30, tzinfo=timezone.utc),
    )
    ga4.get_ordered_funnel_report(days=30)
    monkeypatch.setattr(
        ga4, "_utc_now",
        lambda: datetime(2026, 9, 9, 6, 30, tzinfo=timezone.utc),
    )
    ga4.get_ordered_funnel_report(days=30)

    assert len(seen) == 2
    assert seen[0] != seen[1]
    assert "2026-09-07" in seen[0]
    assert "2026-09-08" in seen[1]


def _valid_cached_funnel():
    return {
        "schema": "ga4_native_ordered_funnel/v1",
        "available": True,
        "fetched_at": "2026-09-09T05:30:00+00:00",
        "period": {
            "start_date": "2026-08-09", "end_date": "2026-09-07",
            "timezone": "America/Denver", "complete_days": 30,
        },
        "steps": [
            {
                **definition,
                "position": index,
                "present": False,
                "users": None,
                "completion_rate": None,
                "abandonments": None,
                "abandonment_rate": None,
            }
            for index, definition in enumerate(ga4.NATIVE_FUNNEL_STEPS, start=1)
        ],
        "metadata": {"funnel_table": {}, "funnel_visualization": {}},
        "request_contract": {
            "closed": True,
            "ordered": True,
            "directly_followed": False,
            "steps": copy.deepcopy(list(ga4.NATIVE_FUNNEL_STEPS)),
        },
        "provenance": {
            "cache_hit": False,
            "request_version": "v2",
            "property_ref": "1f5aeb67e1f0",
            "response_kind": "analyticsData#runFunnelReport",
        },
    }


def test_native_funnel_valid_cache_reports_hit_and_skips_transport(monkeypatch):
    cached = _valid_cached_funnel()
    monkeypatch.setattr(ga4, "_get_client", lambda: _TimezoneClient())
    monkeypatch.setattr(
        ga4, "_get_property_reporting_timezone",
        lambda _client, _property: "America/Denver",
    )
    monkeypatch.setattr(ga4, "_get_cached", lambda key: cached)
    monkeypatch.setattr(
        ga4, "_get_funnel_session",
        lambda: (_ for _ in ()).throw(AssertionError("cache hit used transport")),
    )
    monkeypatch.setattr(
        ga4, "_utc_now",
        lambda: datetime(2026, 9, 9, 5, 30, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(ga4, "GA4_PROPERTY_ID", "properties/123456")

    report = ga4.get_ordered_funnel_report()

    assert report["provenance"]["cache_hit"] is True
    assert cached["provenance"]["cache_hit"] is False


@pytest.mark.parametrize(("field", "bad_value"), [
    ("users", True),
    ("abandonments", True),
    ("completion_rate", True),
    ("abandonment_rate", True),
])
def test_native_funnel_rejects_cached_boolean_metrics_and_refetches(
        monkeypatch, field, bad_value):
    cached = _valid_cached_funnel()
    cached["steps"][0].update({
        "present": True,
        "users": 1,
        "completion_rate": 0.5,
        "abandonments": 1,
        "abandonment_rate": 0.5,
    })
    cached["steps"][0][field] = bad_value
    session = _FunnelSession(_captured_response())
    monkeypatch.setattr(ga4, "GA4_PROPERTY_ID", "properties/123456")
    monkeypatch.setattr(ga4, "_get_client", lambda: _TimezoneClient())
    monkeypatch.setattr(
        ga4, "_get_property_reporting_timezone",
        lambda _client, _property: "America/Denver",
    )
    monkeypatch.setattr(ga4, "_get_cached", lambda key: cached)
    monkeypatch.setattr(ga4, "_set_cached", lambda key, data: None)
    monkeypatch.setattr(ga4, "_get_funnel_session", lambda: session)
    monkeypatch.setattr(
        ga4, "_utc_now",
        lambda: datetime(2026, 9, 9, 5, 30, tzinfo=timezone.utc),
    )

    report = ga4.get_ordered_funnel_report()

    assert report["available"] is True
    assert report["provenance"]["cache_hit"] is False
    assert report["steps"][0]["users"] == 4601
    assert len(session.calls) == 1


def test_native_funnel_rejects_cached_malformed_metadata_and_refetches(monkeypatch):
    cached = _valid_cached_funnel()
    cached["metadata"]["funnel_table"] = {"samplingMetadatas": 7}
    session = _FunnelSession(_captured_response())
    monkeypatch.setattr(ga4, "GA4_PROPERTY_ID", "properties/123456")
    monkeypatch.setattr(ga4, "_get_client", lambda: _TimezoneClient())
    monkeypatch.setattr(
        ga4, "_get_property_reporting_timezone",
        lambda _client, _property: "America/Denver",
    )
    monkeypatch.setattr(ga4, "_get_cached", lambda key: cached)
    monkeypatch.setattr(ga4, "_set_cached", lambda key, data: None)
    monkeypatch.setattr(ga4, "_get_funnel_session", lambda: session)
    monkeypatch.setattr(
        ga4, "_utc_now",
        lambda: datetime(2026, 9, 9, 5, 30, tzinfo=timezone.utc),
    )

    report = ga4.get_ordered_funnel_report()

    assert report["available"] is True
    assert report["provenance"]["cache_hit"] is False
    assert report["metadata"]["funnel_table"] == {}
    assert len(session.calls) == 1


@pytest.mark.parametrize("cached", [
    {"schema": "ga4_native_ordered_funnel/v1", "available": False},
    {
        "schema": "ga4_native_ordered_funnel/v1",
        "available": True,
        "period": {
            "start_date": "2026-08-08", "end_date": "2026-09-06",
            "timezone": "America/Denver", "complete_days": 30,
        },
        "steps": [],
        "provenance": {
            "request_version": "v2", "property_ref": "1f5aeb67e1f0",
        },
    },
])
def test_native_funnel_failed_or_different_window_cache_cannot_masquerade(
        monkeypatch, cached):
    session = _FunnelSession(_captured_response())
    monkeypatch.setattr(ga4, "GA4_PROPERTY_ID", "properties/123456")
    monkeypatch.setattr(ga4, "_get_client", lambda: _TimezoneClient())
    monkeypatch.setattr(
        ga4, "_get_property_reporting_timezone",
        lambda _client, _property: "America/Denver",
    )
    monkeypatch.setattr(ga4, "_get_cached", lambda key: cached)
    monkeypatch.setattr(ga4, "_set_cached", lambda key, data: None)
    monkeypatch.setattr(ga4, "_get_funnel_session", lambda: session)
    monkeypatch.setattr(
        ga4, "_utc_now",
        lambda: datetime(2026, 9, 9, 5, 30, tzinfo=timezone.utc),
    )

    report = ga4.get_ordered_funnel_report()

    assert report["available"] is True
    assert report["period"]["end_date"] == "2026-09-07"
    assert report["provenance"]["cache_hit"] is False
    assert len(session.calls) == 1


def test_native_funnel_fails_unavailable_when_property_timezone_is_missing(
        monkeypatch):
    monkeypatch.setattr(ga4, "GA4_PROPERTY_ID", "properties/123456")
    monkeypatch.setattr(ga4, "_get_cached", lambda key: None)
    monkeypatch.setattr(ga4, "_get_client", lambda: _TimezoneClient(""))
    monkeypatch.setattr(
        ga4, "_get_funnel_session",
        lambda: (_ for _ in ()).throw(AssertionError("timezone must fail first")),
    )

    report = ga4.get_ordered_funnel_report()

    assert report["available"] is False
    assert report["error_code"] == "TIMEZONE_UNAVAILABLE"
