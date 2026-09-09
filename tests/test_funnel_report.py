"""Tests for scripts/funnel_report.py — conversion funnel analysis.

Covers:
- Mock data output format
- Observed stage ordering and query scope
- Independent-total measurement semantics
- Human and JSON disclosure of denominator limits
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import funnel_report
from funnel_report import (
    ARTICLE_FUNNEL,
    COACHING_FUNNEL,
    TRAINING_PLAN_FUNNEL,
    get_mock_data,
    print_report,
)


# ── Mock data format ────────────────────────────────────────


class TestMockData:
    """Tests for get_mock_data() output format."""

    def test_returns_three_lists(self):
        tp, coaching, articles = get_mock_data()
        assert isinstance(tp, list)
        assert isinstance(coaching, list)
        assert isinstance(articles, list)

    def test_training_plan_stages_have_required_keys(self):
        tp, _, _ = get_mock_data()
        for stage in tp:
            assert "stage" in stage
            assert "label" in stage
            assert "count" in stage
            assert "scope" in stage
            assert isinstance(stage["count"], int)

    def test_coaching_stages_have_required_keys(self):
        _, coaching, _ = get_mock_data()
        for stage in coaching:
            assert "stage" in stage
            assert "label" in stage
            assert "count" in stage
            assert "scope" in stage
            assert isinstance(stage["count"], int)

    def test_article_stages_have_required_keys(self):
        _, _, articles = get_mock_data()
        for stage in articles:
            assert "stage" in stage
            assert "label" in stage
            assert "count" in stage
            assert "scope" in stage
            assert isinstance(stage["count"], int)

    def test_training_plan_has_six_stages(self):
        tp, _, _ = get_mock_data()
        assert len(tp) == 6

    def test_coaching_has_three_stages(self):
        _, coaching, _ = get_mock_data()
        assert len(coaching) == 3

    def test_article_has_three_stages(self):
        _, _, articles = get_mock_data()
        assert len(articles) == 3

    def test_mock_counts_are_positive(self):
        tp, coaching, articles = get_mock_data()
        for stage in tp + coaching + articles:
            assert stage["count"] > 0


# ── Funnel stage ordering ──────────────────────────────────


class TestObservedStageOrdering:
    """Rows retain a useful journey-like reading order without claiming a cohort."""

    def test_training_plan_funnel_order(self):
        expected_stages = [
            "page_view", "cta_click", "tp_form_start",
            "tp_form_submit", "begin_checkout", "purchase",
        ]
        actual = [s["stage"] for s in TRAINING_PLAN_FUNNEL]
        assert actual == expected_stages

    def test_coaching_funnel_order(self):
        expected_stages = [
            "page_view", "coaching_cta_click", "coaching_scroll_depth",
        ]
        actual = [s["stage"] for s in COACHING_FUNNEL]
        assert actual == expected_stages

    def test_mock_data_need_not_decrease_through_training_totals(self):
        """Mock totals may rise because the rows are independent event totals."""
        tp, _, _ = get_mock_data()
        assert tp[-1]["count"] > tp[-2]["count"]

    def test_every_stage_declares_its_query_scope(self):
        for stage in TRAINING_PLAN_FUNNEL + COACHING_FUNNEL + ARTICLE_FUNNEL:
            assert stage["scope"]

    def test_race_cta_is_scoped_to_race_pages(self):
        cta = next(s for s in TRAINING_PLAN_FUNNEL if s["stage"] == "cta_click")
        assert cta["filter_field"] == "pagePath"
        assert cta["filter_prefix"] == "/race/"

    def test_form_stage_counts_both_deployed_event_generations(self):
        start = next(s for s in TRAINING_PLAN_FUNNEL if s["stage"] == "tp_form_start")
        submit = next(s for s in TRAINING_PLAN_FUNNEL if s["stage"] == "tp_form_submit")
        assert set(start["events"]) == {"form_start", "tp_form_start"}
        assert set(submit["events"]) == {"form_submit", "tp_form_submit"}


# ── Measurement semantics ──────────────────────────────────


class TestIndependentTotalSemantics:
    def test_metadata_refuses_unavailable_denominators(self):
        metadata = getattr(funnel_report, "MEASUREMENT_METADATA", {})
        assert metadata.get("kind") == "independent_event_totals"
        assert metadata.get("joined") is False
        assert metadata.get("denominator", "missing") is None

    def test_json_payload_contains_limits_and_no_cross_stage_rates(self):
        tp, coaching, articles = get_mock_data()
        build_report_payload = getattr(funnel_report, "build_report_payload", None)
        assert callable(build_report_payload)
        payload = build_report_payload(30, tp, coaching, articles)
        assert payload["measurement"] == funnel_report.MEASUREMENT_METADATA
        assert payload["schema"] == "ga4_event_totals/v2"
        for rows in (
            payload["training_plan_totals"],
            payload["coaching_totals"],
            payload["article_totals"],
        ):
            for row in rows:
                assert "dropoff_pct" not in row
                assert "cumulative_pct" not in row

    def test_query_applies_declared_scope_and_event_aliases(self, monkeypatch):
        from google.analytics import data_v1beta

        requests = []

        class Client:
            def run_report(self, request):
                requests.append(request)
                return SimpleNamespace(rows=[])

        monkeypatch.setattr(data_v1beta, "BetaAnalyticsDataClient", Client)
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", "test-sentinel")
        rows = funnel_report.get_funnel_data(
            "123", "/tmp/test-ga4.json", 30, TRAINING_PLAN_FUNNEL
        )

        assert len(requests) == len(TRAINING_PLAN_FUNNEL)
        assert [row["scope"] for row in rows] == [
            stage["scope"] for stage in TRAINING_PLAN_FUNNEL
        ]
        race_path_filter = requests[1].dimension_filter.and_group.expressions[1]
        assert race_path_filter.filter.string_filter.value == "/race/"
        form_events = requests[2].dimension_filter.and_group.expressions[0]
        assert {
            expression.filter.string_filter.value
            for expression in form_events.or_group.expressions
        } == {"form_start", "tp_form_start"}
        assert not requests[-1].dimension_filter.and_group.expressions

    def test_human_report_labels_totals_and_omits_conversion_claims(self, capsys):
        tp, coaching, articles = get_mock_data()
        print_report(tp, coaching, 30, articles)
        output = capsys.readouterr().out
        assert "INDEPENDENT GA4 EVENT TOTALS" in output
        assert "No shared session, user, product, or event order" in output
        assert "Overall conversion" not in output
        assert "Drop-off" not in output
        assert "Cumulative" not in output
