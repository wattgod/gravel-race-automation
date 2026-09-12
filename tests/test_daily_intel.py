"""Unit tests for the pure Morning Intel report functions."""
from __future__ import annotations

from copy import deepcopy
import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from scripts.daily_intel import (
    INTERPRET_PROMPT,
    combine_report,
    compute_constraint,
    detect_tracking_regression,
    measurement_epochs_for_report,
    measurement_epochs_in_window,
    render_report,
)


def _ga4(sessions=20, cta=2):
    return {
        "ok": True,
        "sessions": sessions,
        "sessions_7d_avg": 18.5,
        "funnel": {
            "cta_click": cta,
            "form_start": 2,
            "form_submit": 1,
            "begin_checkout": 0,
            "purchase": 0,
        },
        "top_pages": [{"path": "/race/test/", "views": 7}],
        "channel_mix": {"Organic Search": 12, "Direct": 8},
        "top_landing": [{"path": "/race/test/", "sessions": 5}],
    }


@pytest.fixture
def collected():
    return {
        "date": "2026-07-20",
        "ga4": {
            "gravelgod": _ga4(),
            "roadielabs": _ga4(sessions=3, cta=0),
        },
        "checkout": {
            "gravelgod": {"ok": True},
            "roadielabs": {"ok": True},
        },
        "mission_control": {
            "ok": True,
            "leads_by_brand": {"gravelgod": 2, "roadielabs": 1},
            "hot_leads_14d": [{
                "name": "Ada Rider",
                "email": "ada@example.com",
                "race": "Test Gravel",
                "sequence": "welcome_v1",
                "step": 2,
                "opens": 3,
                "clicks": 1,
            }],
            "errors_24h": [],
        },
        "commerce_ledger": {
            "ok": True,
            "failed_orders": [],
            "orders": [],
            "recoveries": [],
            "questionnaire_starts": 0,
        },
        "constraint": {
            "ok": True,
            "assessment": "data_insufficient",
            "reason": "independent event totals do not establish a causal bottleneck",
            "sessions_28d": 1061,
            "event_totals_28d": {
                "cta_click": 43,
                "form_start": 20,
                "form_submit": 10,
                "begin_checkout": 3,
                "purchase": 2,
                "refund": 4,
            },
        },
        "social": {"ok": True, "accounts_live": False},
        "workflows": {"ok": True, "latest": {"regression-tests.yml": "success"}},
        "report_issues": [],
    }


def test_render_report_has_deterministic_sections_and_readable_funnel(collected):
    report = render_report(collected)

    assert report.startswith("## NUMBERS")
    assert "cta 2; form_start 2; submit 1; checkout 0; purchase 0; refund 0" in report
    assert "{'cta_click'" not in report
    assert "## TRAFFIC" in report
    assert "Gravel God top pages" in report
    assert "Roadie Labs:** 3 sessions; near-zero traffic" in report
    assert "## ORDER PROCESSING (LOCAL RECORDS)" in report
    assert "no processing attempts, cart recoveries, or questionnaire starts" in report
    assert "causal bottleneck: data insufficient" in report
    assert "sessions 1061; cta 43; form_start 20; submit 10; checkout 3; purchase 2; refund 4" in report
    assert "CTA→submit" not in report
    assert "Ada Rider <ada@example.com> — Test Gravel; welcome_v1 step 2" in report
    assert "## SOCIAL" not in report
    assert "###" not in report
    assert report.endswith("- nothing broken.")


def test_measurement_window_fully_after_epoch_has_no_annotation(collected):
    collected["date"] = "2026-09-25"
    collected["measurement_epochs"] = measurement_epochs_for_report(collected["date"])

    report = render_report(collected)

    assert collected["measurement_epochs"] == []
    assert "measurement regime change" not in report


def test_measurement_window_straddle_is_annotated_and_serializable(collected):
    import json

    collected["date"] = "2026-07-29"
    collected["measurement_epochs"] = measurement_epochs_for_report(collected["date"])

    report = render_report(collected)
    snapshot = json.loads(json.dumps({**collected, "report": report}))

    warning = (
        "⚠ measurement regime change 2026-07-26 — comparison not like-for-like"
    )
    assert report.count(warning) == 2
    assert "(28d sessions and independent event totals)." in report
    assert snapshot["measurement_epochs"] == [{
        "date": "2026-07-26",
        "scope": "sessions",
        "label": (
            "consent geo-gate deployed (f52d2722): non-EEA analytics default granted; "
            "sessions before this date captured only opted-in visitors and are not comparable"
        ),
    }]
    assert warning in snapshot["report"]
    assert "analytics collection changes, not demand changes" in INTERPRET_PROMPT
    assert "Do not infer conversion rates or a causal bottleneck" in INTERPRET_PROMPT


def test_compute_constraint_refuses_rates_for_nonmonotonic_event_totals():
    result = compute_constraint({
        "ok": True,
        "sessions_28d": 500,
        "funnel_28d": {
            "cta_click": 4,
            "form_start": 3,
            "form_submit": 1,
            "begin_checkout": 1,
            "purchase": 2,
            "refund": 7,
        },
    })

    assert result == {
        "ok": True,
        "assessment": "data_insufficient",
        "reason": "independent event totals do not establish a causal bottleneck",
        "sessions_28d": 500,
        "event_totals_28d": {
            "cta_click": 4,
            "form_start": 3,
            "form_submit": 1,
            "begin_checkout": 1,
            "purchase": 2,
            "refund": 7,
        },
    }
    assert not any(key.endswith("_pct") for key in result)
    assert "binding_constraint" not in result


def test_collect_ga4_filters_both_event_queries_before_limit(monkeypatch):
    from scripts import daily_intel

    class Message:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class Filter(Message):
        class InListFilter(Message):
            pass

        class StringFilter(Message):
            class MatchType:
                BEGINS_WITH = "BEGINS_WITH"

    def row(name, count):
        return SimpleNamespace(
            dimension_values=[SimpleNamespace(value=name)],
            metric_values=[SimpleNamespace(value=str(count))],
        )

    class Client:
        def __init__(self):
            self.event_requests = []

        def run_realtime_report(self, request):
            return SimpleNamespace(rows=[SimpleNamespace(metric_values=[SimpleNamespace(value="2")])])

        def run_report(self, request):
            dimensions = [item.name for item in request.dimensions]
            if dimensions == ["dateHour"]:
                # Hourly rows stop at 03:00 — GA4 still processing yesterday.
                return SimpleNamespace(rows=[
                    SimpleNamespace(dimension_values=[SimpleNamespace(value=f"20260910{h:02d}")],
                                    metric_values=[SimpleNamespace(value="3")])
                    for h in range(0, 4)])
            if dimensions == ["eventName"]:
                self.event_requests.append(request)
                dim_filter = getattr(request, "dimension_filter", None)
                if dim_filter is None:
                    return SimpleNamespace(rows=[row(f"unrelated_{i}", 1) for i in range(100)])
                if getattr(dim_filter, "and_group", None) is not None:
                    # Legacy Enhanced-Measurement pair, questionnaire-scoped.
                    return SimpleNamespace(rows=[row("form_submit", 3)])
                return SimpleNamespace(rows=[row("purchase", 2), row("refund", 7),
                                             row("tp_form_submit", 1)])
            return SimpleNamespace(rows=[])

    client = Client()
    fake_api = ModuleType("google.analytics.data_v1beta")
    fake_api.BetaAnalyticsDataClient = lambda: client
    fake_types = ModuleType("google.analytics.data_v1beta.types")
    for name, value in {
        "DateRange": Message,
        "Dimension": Message,
        "Filter": Filter,
        "FilterExpression": Message,
        "FilterExpressionList": Message,
        "Metric": Message,
        "RunReportRequest": Message,
        "RunRealtimeReportRequest": Message,
    }.items():
        setattr(fake_types, name, value)
    monkeypatch.setitem(sys.modules, "google.analytics.data_v1beta", fake_api)
    monkeypatch.setitem(sys.modules, "google.analytics.data_v1beta.types", fake_types)
    monkeypatch.setenv(daily_intel.BRANDS["gravelgod"]["property_env"], "123")

    result = daily_intel.collect_ga4("gravelgod")

    assert result["funnel"]["purchase"] == 2
    assert result["funnel"]["refund"] == 7
    assert result["funnel"]["form_submit"] == 4  # 1 tp_form_submit + 3 scoped legacy
    assert result["yesterday_last_hour"] == 3
    assert result["yesterday_provisional"] is True
    assert result["realtime_active_users"] == 2  # tag live → late processing likely
    assert result["hourly_error"] is None
    assert result["funnel_28d"]["purchase"] == 2
    assert result["funnel_28d"]["refund"] == 7
    assert result["funnel_28d"]["form_submit"] == 4
    # Two windows (yesterday, 28d) x two filtered queries each.
    assert len(client.event_requests) == 4
    custom = [r for r in client.event_requests
              if getattr(r.dimension_filter, "and_group", None) is None]
    legacy = [r for r in client.event_requests
              if getattr(r.dimension_filter, "and_group", None) is not None]
    assert len(custom) == 2 and len(legacy) == 2
    expected_custom = set(daily_intel.FUNNEL_EVENTS) - set(daily_intel.LEGACY_FORM_EVENTS)
    for request in custom:
        event_filter = request.dimension_filter.filter
        assert event_filter.field_name == "eventName"
        assert set(event_filter.in_list_filter.values) == expected_custom
    for request in legacy:
        name_expr, path_expr = request.dimension_filter.and_group.expressions
        assert name_expr.filter.field_name == "eventName"
        assert set(name_expr.filter.in_list_filter.values) == set(daily_intel.LEGACY_FORM_EVENTS)
        assert path_expr.filter.field_name == "pagePath"
        assert path_expr.filter.string_filter.value == daily_intel.LEGACY_FORM_PATH_PREFIX
        assert path_expr.filter.string_filter.match_type == "BEGINS_WITH"


def test_load_trend_keeps_events_distinct_from_processing_records(tmp_path, monkeypatch):
    from scripts import daily_intel

    snapshot = {
        "ga4": {
            "gravelgod": {
                "ok": True,
                "sessions": 10,
                "funnel": {"purchase": 9, "refund": 4},
            },
            "roadielabs": {
                "ok": True,
                "sessions": 5,
                "funnel": {"purchase": 2, "refund": 1},
            },
            "xcski": {
                "ok": True,
                "sessions": 0,
                "funnel": {"purchase": 0, "refund": 0},
            },
        },
        "commerce_ledger": {
            "ok": True,
            "orders": [
                {"id": "cs_test_same", "success": True},
                {"id": "cs_test_same", "success": True},
            ],
            "failed_orders": [],
        },
        "mission_control": {
            "new_orders_24h_UNRELIABLE": "use ga4 purchase counts",
        },
    }
    (tmp_path / "2026-09-07.json").write_text(json.dumps(snapshot))
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", tmp_path)

    [trend] = daily_intel.load_trend()

    assert trend["purchase_events"] == 11
    assert trend["refund_events"] == 5
    assert trend["order_processing_records"] == 2
    assert "provider_orders" not in trend
    assert "orders" not in trend
    assert trend["gravelgod"]["purchase_events"] == 9
    assert trend["gravelgod"]["refund_events"] == 4
    assert "purchases" not in trend["gravelgod"]
    assert "GA4 purchase and refund counts are behavioral events, not orders" in daily_intel.INTERPRET_PROMPT
    assert "may contain retries, duplicate attempts, failures, or synthetic traffic" in daily_intel.INTERPRET_PROMPT
    assert "does not establish payment or customer fulfillment" in daily_intel.INTERPRET_PROMPT


@pytest.mark.parametrize(
    "unavailable_brand",
    [None, {"ok": False, "funnel": {"purchase": 0, "refund": 0}}],
)
def test_load_trend_keeps_aggregate_unknown_for_missing_or_failed_brand(
        tmp_path, monkeypatch, unavailable_brand):
    from scripts import daily_intel

    ga4 = {
        "gravelgod": {
            "ok": True,
            "sessions": 10,
            "funnel": {"purchase": 2, "refund": 1},
        },
        "roadielabs": {
            "ok": True,
            "sessions": 5,
            "funnel": {"purchase": 0, "refund": 0},
        },
    }
    if unavailable_brand is not None:
        ga4["xcski"] = unavailable_brand
    (tmp_path / "2026-09-05.json").write_text(json.dumps({"ga4": ga4}))
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", tmp_path)

    [trend] = daily_intel.load_trend()

    assert trend["purchase_events"] is None
    assert trend["refund_events"] is None
    assert trend["xcski"]["purchase_events"] is None


def test_load_trend_keeps_refunds_unknown_before_refund_epoch(tmp_path, monkeypatch):
    from scripts import daily_intel

    ga4 = {
        brand: {"ok": True, "funnel": {"purchase": 0}}
        for brand in daily_intel.BRANDS
    }
    (tmp_path / "2026-06-30.json").write_text(json.dumps({"ga4": ga4}))
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", tmp_path)

    [trend] = daily_intel.load_trend()

    assert trend["purchase_events"] == 0
    assert trend["refund_events"] is None
    assert all(trend[brand]["refund_events"] is None for brand in daily_intel.BRANDS)


def test_load_trend_preserves_true_complete_zero(tmp_path, monkeypatch):
    from scripts import daily_intel

    ga4 = {
        brand: {"ok": True, "funnel": {"purchase": 0, "refund": 0}}
        for brand in daily_intel.BRANDS
    }
    (tmp_path / "2026-09-06.json").write_text(json.dumps({"ga4": ga4}))
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", tmp_path)

    [trend] = daily_intel.load_trend()

    assert trend["purchase_events"] == 0
    assert trend["refund_events"] == 0


def test_empty_epoch_list_preserves_report_behavior(collected):
    baseline = render_report(deepcopy(collected))
    collected["measurement_epochs"] = []

    assert render_report(collected) == baseline
    assert measurement_epochs_in_window(
        "2026-07-01", "2026-07-31", epochs=[]) == []


def test_render_report_failed_orders_are_first_and_broken_is_complete(collected):
    failed_record = {
        "name": "Failed Rider",
        "email": "failed@example.com",
        "product_type": "training_plan",
        "success": False,
        "error": "delivery timeout",
    }
    collected["commerce_ledger"].update({
        "failed_orders": [failed_record],
        "orders": [
            failed_record,
            {
                "name": "Paid Rider",
                "email": "paid@example.com",
                "product_type": "training_plan",
                "success": True,
            },
        ],
        "recoveries": [{"email": "cart@example.com", "product": "training_plan"}],
        "questionnaire_starts": 2,
    })
    collected["checkout"]["roadielabs"] = {"ok": False, "error": "checkout=500"}
    collected["mission_control"]["errors_24h"] = [
        {"action": "sequence_send_error", "details": "Resend 500"},
    ]
    collected["workflows"]["latest"]["link-check.yml"] = "failure"
    collected["report_issues"] = ["possible tracking regression"]

    report = render_report(collected)
    commerce = report.split("## ORDER PROCESSING (LOCAL RECORDS)\n", 1)[1].split(
        "\n\n## CONSTRAINT", 1)[0]

    assert commerce.index("**PROCESSING FAILURE:**") < commerce.index(
        "- processing record: Paid Rider")
    assert "processing FAILED: delivery timeout" in commerce
    assert "processing succeeded" in commerce
    assert "fulfilled" not in commerce
    assert "cart recovery: cart@example.com" in commerce
    assert "questionnaire starts: 2" in commerce
    assert "checkout Roadie Labs FAIL: checkout=500" in report
    assert "Mission Control sequence_send_error: Resend 500" in report
    assert "workflow link-check.yml: failure" in report
    assert "possible tracking regression" in report


def test_render_report_includes_social_only_when_accounts_are_live(collected):
    collected["social"] = {
        "ok": True,
        "accounts_live": True,
        "queued_today": 1,
        "queued_yesterday": 2,
        "posts": [{"brand": "gravelgod", "race": "Test Gravel", "kind": "preview"}],
    }

    report = render_report(collected)

    assert "## SOCIAL" in report
    assert "queued: 1 today; 2 yesterday" in report
    assert "gravelgod: Test Gravel — preview" in report


def test_detect_tracking_regression_after_three_qualifying_days():
    today = {"ga4": {"gravelgod": _ga4(sessions=27, cta=0)}}
    priors = [
        {"ga4": {"gravelgod": _ga4(sessions=24, cta=0)}},
        {"ga4": {"gravelgod": _ga4(sessions=31, cta=0)}},
    ]

    warning = detect_tracking_regression(today, priors)

    assert warning == (
        "possible GA4 event-tracking regression: 27 sessions but "
        "0 cta_click for 3+ consecutive days"
    )


def test_detect_tracking_regression_requires_explicit_cta_counts():
    today = {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}}
    priors = [
        {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}},
        {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}},
    ]
    del priors[1]["ga4"]["gravelgod"]["funnel"]["cta_click"]

    assert detect_tracking_regression(today, priors) is None


@pytest.mark.parametrize(
    ("today_sessions", "today_cta", "prior_index", "prior_change"),
    [
        (14, 0, None, None),
        (20, 1, None, None),
        (20, 0, 0, {"sessions": 14}),
        (20, 0, 1, {"cta_click": 1}),
        (20, 0, 0, {"ok": False}),
    ],
)
def test_detect_tracking_regression_guard_conditions(
        today_sessions, today_cta, prior_index, prior_change):
    today = {"ga4": {"gravelgod": _ga4(sessions=today_sessions, cta=today_cta)}}
    priors = [
        {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}},
        {"ga4": {"gravelgod": _ga4(sessions=20, cta=0)}},
    ]
    if prior_index is not None:
        g = priors[prior_index]["ga4"]["gravelgod"]
        for key, value in prior_change.items():
            if key == "cta_click":
                g["funnel"][key] = value
            else:
                g[key] = value

    assert detect_tracking_regression(today, priors) is None


def test_combine_report_keeps_deterministic_core_between_narration(collected):
    core = render_report(deepcopy(collected))
    narration = "## TOP LINE\n- 20 sessions.\n\n## DO TODAY\n- nothing — let it run"

    report = combine_report(narration, core)

    assert report.index("## TOP LINE") < report.index("## NUMBERS")
    assert report.index("## BROKEN") < report.index("## DO TODAY")


# ── Delivery-guard tests (email must always send) ───────────────────────

def test_safe_render_survives_shape_drift(collected):
    from scripts import daily_intel
    bad = deepcopy(collected)
    bad["commerce_ledger"] = {"ok": True, "orders": ["not-a-dict"]}
    out = daily_intel.safe_render(bad)
    assert "## BROKEN" in out
    assert "report rendering crashed" in out


def test_collect_checkout_gated_brand_is_not_broken(monkeypatch):
    from scripts import daily_intel

    def fake_http(url, data=None, headers=None, timeout=25):
        if url.endswith("/health"):
            return 200, "ok"
        return 400, '{"error": "XC Ski Labs does not support training-plan generation yet"}'

    monkeypatch.setattr(daily_intel, "_http", fake_http)
    out = daily_intel.collect_checkout("xcski")
    assert out["plans_gated"] is True
    assert out["error"] == ""


def test_collect_checkout_real_400_still_fails(monkeypatch):
    from scripts import daily_intel

    def fake_http(url, data=None, headers=None, timeout=25):
        if url.endswith("/health"):
            return 200, "ok"
        return 400, '{"error": "Valid email is required"}'

    monkeypatch.setattr(daily_intel, "_http", fake_http)
    out = daily_intel.collect_checkout("gravelgod")
    assert out["ok"] is False
    assert "checkout=400" in out["error"]


def test_load_prior_snapshots_skips_non_dict(tmp_path, monkeypatch):
    from scripts import daily_intel
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-07-19.json").write_text("[]")
    assert daily_intel.load_prior_snapshots("2026-07-20") == []


def test_no_llm_does_not_extend_failure_streak(tmp_path, monkeypatch):
    from scripts import daily_intel
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", tmp_path)
    (tmp_path / "2026-07-19.json").write_text('{"interpretation_ok": null}')
    (tmp_path / "2026-07-18.json").write_text('{"interpretation_ok": false}')
    assert daily_intel.interpretation_failure_streak("2026-07-20") == 1


def test_main_sends_email_even_when_everything_downstream_breaks(
        tmp_path, monkeypatch, capsys):
    """Collectors return drifted shapes, interpretation raises, snapshots are
    unwritable — send_email must still be called."""
    from scripts import daily_intel

    def boom(*a, **k):
        raise RuntimeError("boom")

    for name in ("collect_ga4", "collect_checkout", "collect_mission_control",
                 "collect_commerce_ledger", "collect_social", "collect_workflows"):
        monkeypatch.setattr(daily_intel, name, boom)
    monkeypatch.setattr(daily_intel, "render_report", boom)
    monkeypatch.setattr(daily_intel, "interpret", boom)
    monkeypatch.setattr(daily_intel, "load_trend", lambda: [])
    # unwritable snapshot dir: a path whose parent is a file
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    monkeypatch.setattr(daily_intel, "SNAPSHOT_DIR", blocker / "nope")

    sent = {}
    monkeypatch.setattr(daily_intel, "send_email",
                        lambda subject, report: sent.update(
                            subject=subject, report=report) or "msg_test")
    monkeypatch.setattr("sys.argv", ["daily_intel.py"])

    assert daily_intel.main() == 0
    assert "INTERPRETATION BROKEN" in sent["subject"]
    assert "snapshot write failed" in sent["report"]


def test_collect_mission_control_reads_newest_rows_past_the_1000_row_cap(monkeypatch):
    """Regression: gg_sequence_sends crossed 1000 rows on 2026-08-26 and the
    collector — which sorted ascending and capped at 1000 — stopped seeing
    any send in the 24h window, reporting "0 emails sent" for eight days
    while the scheduler was sending daily. Every capped select must page
    newest-first so the recent windows are always inside the page."""
    import sys
    import types
    from datetime import datetime, timedelta, timezone

    from scripts import daily_intel

    now = datetime.now(timezone.utc)
    iso = lambda dt: dt.isoformat()  # noqa: E731 — PostgREST returns ISO 8601 strings

    old_sends = [
        {"id": f"s-old-{i}", "enrollment_id": "e-old", "template": "old",
         "status": "sent", "sent_at": iso(now - timedelta(days=200, minutes=-i)),
         "opened_at": None, "clicked_at": None}
        for i in range(1100)
    ]
    new_sends = [
        {"id": "s-new-1", "enrollment_id": "e-new", "template": "prep_kit_delivery",
         "status": "clicked", "sent_at": iso(now - timedelta(hours=3)),
         "opened_at": iso(now - timedelta(hours=2)),
         "clicked_at": iso(now - timedelta(hours=1))},
        {"id": "s-new-2", "enrollment_id": "e-new", "template": "welcome_value",
         "status": "sent", "sent_at": iso(now - timedelta(hours=2)),
         "opened_at": None, "clicked_at": None},
        {"id": "s-new-3", "enrollment_id": "e-old", "template": "sober_repitch",
         "status": "sent", "sent_at": iso(now - timedelta(minutes=30)),
         "opened_at": None, "clicked_at": None},
    ]
    enrollments = [
        {"id": "e-old", "contact_email": "old@example.com", "contact_name": "Old",
         "sequence_id": "nurture_v1", "current_step": 3, "status": "completed",
         "enrolled_at": iso(now - timedelta(days=100)), "source": "kit",
         "source_data": {"brand": "gravelgod", "race_name": "Unbound"}},
        {"id": "e-new", "contact_email": "new@example.com", "contact_name": "New",
         "sequence_id": "kit_delivery_v1", "current_step": 1, "status": "completed",
         "enrolled_at": iso(now - timedelta(hours=4)), "source": "kit",
         "source_data": {"brand": "gravelgod", "race_name": "The Rift"}},
        {"id": "e-new-2", "contact_email": "new2@example.com", "contact_name": "",
         "sequence_id": "road_kit_delivery_v1", "current_step": 0, "status": "active",
         "enrolled_at": iso(now - timedelta(hours=1)), "source": "kit",
         "source_data": {"brand": "roadielabs", "race_name": "Haute Route"}},
    ]
    tables = {"gg_sequence_sends": old_sends + new_sends,
              "gg_sequence_enrollments": enrollments}

    fake = types.ModuleType("mission_control.supabase_client")

    def select(table, columns="*", match=None, order=None, order_desc=False,
               limit=None, offset=None):
        # Mirrors PostgREST: sort by `order` (ascending unless order_desc),
        # then cap at `limit`. Ascending + limit=1000 returns the OLDEST page.
        rows = list(tables[table])
        for k, v in (match or {}).items():
            rows = [r for r in rows if r.get(k) == v]
        if order:
            rows.sort(key=lambda r: r.get(order) or "", reverse=order_desc)
        if limit:
            rows = rows[:limit]
        return [dict(r) for r in rows]

    fake.select = select
    fake.get_audit_log = lambda limit=50: []
    monkeypatch.setitem(sys.modules, "mission_control.supabase_client", fake)
    import mission_control
    monkeypatch.setattr(mission_control, "supabase_client", fake, raising=False)

    out = daily_intel.collect_mission_control()

    assert out["emails_sent_24h"] == 3
    assert out["opens_24h"] == 1
    assert out["clicks_24h"] == 1
    assert out["new_leads_24h"] == 2
    assert out["leads_by_brand"] == {"gravelgod": 1, "roadielabs": 1}
    assert "new_orders_24h_UNRELIABLE" not in out
    hot = {lead["email"]: lead for lead in out["hot_leads_14d"]}
    assert set(hot) == {"new@example.com", "new2@example.com"}
    assert hot["new@example.com"]["opens"] == 1
    assert hot["new@example.com"]["clicks"] == 1
    assert hot["new@example.com"]["race"] == "The Rift"


def test_render_marks_provisional_sessions_and_separates_lag_from_outage(collected):
    from scripts import daily_intel
    g = collected["ga4"]["gravelgod"]
    g["yesterday_provisional"] = True
    g["yesterday_last_hour"] = 3
    g["realtime_active_users"] = 2
    report = daily_intel.render_report(collected)
    assert "PROVISIONAL" in report and "end at 03:00" in report
    assert "tag is live (2 active users" in report
    g["realtime_active_users"] = 0
    assert "realtime shows 0 active users" in daily_intel.render_report(collected)
    g["realtime_active_users"] = None
    assert "completeness unknown" in daily_intel.render_report(collected)
    g["yesterday_provisional"] = False
    assert "PROVISIONAL" not in daily_intel.render_report(collected)


def test_render_shows_revision_of_yesterdays_provisional_figure(collected):
    from scripts import daily_intel
    collected["ga4_revisions"] = {"gravelgod": {"date": "2026-09-10", "reported": 6, "now": 121}}
    report = daily_intel.render_report(collected)
    assert "2026-09-10 revised to 121 (reported 6 yesterday)" in report


def test_compute_ga4_revisions_only_when_the_figure_moved():
    from scripts import daily_intel
    collected = {"ga4": {"gravelgod": {"ok": True, "sessions_d2": 121, "sessions_d2_date": "2026-09-10"},
                         "roadielabs": {"ok": True, "sessions_d2": 5, "sessions_d2_date": "2026-09-10"}}}
    prior = [{"ga4": {"gravelgod": {"ok": True, "sessions": 6}, "roadielabs": {"ok": True, "sessions": 5}}}]
    rev = daily_intel.compute_ga4_revisions(collected, prior)
    assert rev == {"gravelgod": {"date": "2026-09-10", "reported": 6, "now": 121}}
    assert daily_intel.compute_ga4_revisions(collected, []) == {}


def test_interpret_prompt_forbids_narrating_provisional_as_a_drop():
    from scripts import daily_intel
    assert "marked PROVISIONAL" in daily_intel.INTERPRET_PROMPT
    assert "do not compare it to the 7-day average or call it a drop" in daily_intel.INTERPRET_PROMPT
    assert "realtime shows 0 active users" in daily_intel.INTERPRET_PROMPT


def test_summarize_workflow_runs_reports_newest_any_trigger_and_last_green():
    from scripts import daily_intel
    runs = [
        {"conclusion": "failure", "updatedAt": "2026-09-08T12:29:08Z", "event": "schedule"},
        {"conclusion": "success", "updatedAt": "2026-09-11T17:00:00Z", "event": "workflow_dispatch"},
    ]
    s = daily_intel.summarize_workflow_runs(runs)
    assert s["conclusion"] == "failure" and s["event"] == "schedule"
    assert s["last_success_at"] == "2026-09-11T17:00:00Z"
    assert s["last_success_event"] == "workflow_dispatch"
    assert daily_intel.summarize_workflow_runs([]) == {"conclusion": "never-run"}


def test_render_workflow_failure_names_age_and_last_green(collected):
    from scripts import daily_intel
    collected["workflows"] = {"ok": True, "latest": {"link-check.yml": "failure"},
                              "runs": {"link-check.yml": {"conclusion": "failure", "event": "schedule",
                                                          "age_hours": 72.0,
                                                          "last_success_at": "2026-09-11T17:00:00Z",
                                                          "last_success_event": "workflow_dispatch"}}}
    report = daily_intel.render_report(collected)
    assert "workflow link-check.yml: failure (schedule 72h ago; last green 2026-09-11 via workflow_dispatch)" in report


def test_render_since_yesterday_and_review_queue(collected):
    from scripts import daily_intel
    collected["since_yesterday"] = {
        "ok": True,
        "merged_prs": [{"repo": "gravel-race-automation", "number": 350, "title": "fix(intel): guard"}],
        "closed_issues": [{"repo": "gravel-race-automation", "number": 41, "title": "font 404"}],
        "review_queue": [{"repo": "gravel-race-automation", "number": 351, "title": "exec: score",
                          "agent": "nightly-executor", "draft": True, "age_days": 2.5}],
        "runs_24h": {"gravel-race-automation/Link Check": {"success": 1, "failure": 0, "other": 0}},
    }
    report = daily_intel.render_report(collected)
    assert "merged gravel-race-automation#350" in report
    assert "closed gravel-race-automation#41" in report
    assert "#351 (nightly-executor, draft, 2.5d)" in report
    assert "Link Check 1✓/0✗" in report


def test_render_leads_shows_movement_only(collected):
    from scripts import daily_intel
    collected["mission_control"]["hot_leads_14d"] = [
        {"email": "a@x.com", "name": "A", "race": "R1", "sequence": "kit_delivery_v1", "step": 1, "opens": 0, "clicks": 0},
        {"email": "b@x.com", "name": "B", "race": "R2", "sequence": "welcome_v1", "step": 3, "opens": 0, "clicks": 0},
        {"email": "c@x.com", "name": "C", "race": "R3", "sequence": "kit_delivery_v1", "step": 1, "opens": 1, "clicks": 1},
    ]
    report = daily_intel.render_report(collected)
    assert "MOVED" in report and "c@x.com" in report or "C" in report
    assert "STALLED" in report
    assert "1 fresh lead(s) at step 1 with no signal yet" in report
    assert "a@x.com" not in report


def test_plan_funnel_renders_when_available(collected):
    from scripts import daily_intel
    collected["ga4"]["gravelgod"]["plan_funnel"] = {
        "available": True, "error": None,
        "yesterday": {"race_offer_seen_users": 40, "plan_cta_users": 2, "cta_unlabelled_users": 0,
                      "questionnaire_users_by_surface": {"race_profile": 2}, "questionnaire_users": 3,
                      "form_start_users": 1, "form_submit_users": 0, "checkout_users": 0, "plan_purchase_users": 0},
        "28d": {"race_offer_seen_users": 700, "plan_cta_users": 19, "cta_unlabelled_users": 0,
                "questionnaire_users_by_surface": {"race_profile": 15, "product_page": 4}, "questionnaire_users": 30,
                "form_start_users": 7, "form_submit_users": 2, "checkout_users": 2, "plan_purchase_users": 1},
    }
    report = daily_intel.render_report(collected)
    assert "offer seen 700 → plan CTA 19 → questionnaire 30 (race_profile 15, product_page 4)" in report
    c = daily_intel.compute_constraint(collected["ga4"]["gravelgod"])
    assert c["assessment"] == "plan_funnel" and c["plan_funnel_28d"]["form_submit_users"] == 2


def test_mark_new_agents_and_seo_adjudication_render(collected):
    from scripts import daily_intel
    marked = daily_intel._mark_new_agents(
        [{"user_agent": "OldBot", "count": 5}, {"user_agent": "NewBot", "count": 2}],
        [{"user_agent": "OldBot", "count": 4}])
    assert [(m["user_agent"], m["new_this_week"]) for m in marked] == [("OldBot", False), ("NewBot", True)]
    assert "marked PROVISIONAL" in daily_intel.INTERPRET_PROMPT
    assert "REVIEW QUEUE" in daily_intel.INTERPRET_PROMPT
