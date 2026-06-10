"""Tests for scripts/funnel_report.py — conversion funnel analysis.

Covers:
- Mock data output format
- Funnel stage ordering
- Drop-off calculation
- Cumulative conversion calculation
- Edge cases (zero counts, single stage)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from funnel_report import (
    COACHING_FUNNEL,
    TRAINING_PLAN_FUNNEL,
    compute_funnel_metrics,
    get_mock_data,
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
            assert isinstance(stage["count"], int)

    def test_coaching_stages_have_required_keys(self):
        _, coaching, _ = get_mock_data()
        for stage in coaching:
            assert "stage" in stage
            assert "label" in stage
            assert "count" in stage
            assert isinstance(stage["count"], int)

    def test_article_stages_have_required_keys(self):
        _, _, articles = get_mock_data()
        for stage in articles:
            assert "stage" in stage
            assert "label" in stage
            assert "count" in stage
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


class TestFunnelStageOrdering:
    """Funnel stages must be in correct sequential order."""

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

    def test_mock_data_counts_decrease_through_training_funnel(self):
        """Each stage should have fewer or equal events than the previous."""
        tp, _, _ = get_mock_data()
        for i in range(1, len(tp)):
            # Coaching scroll might be higher than CTA clicks (passive vs active),
            # but training plan funnel should monotonically decrease
            assert tp[i]["count"] <= tp[i - 1]["count"], (
                f"Stage {tp[i]['stage']} ({tp[i]['count']}) > "
                f"{tp[i - 1]['stage']} ({tp[i - 1]['count']})"
            )


# ── Drop-off calculation ───────────────────────────────────


class TestDropoffCalculation:
    """Tests for compute_funnel_metrics drop-off percentages."""

    def test_basic_dropoff(self):
        stages = [
            {"stage": "a", "label": "A", "count": 100},
            {"stage": "b", "label": "B", "count": 50},
        ]
        result = compute_funnel_metrics(stages)
        assert result[0]["dropoff_pct"] is None  # first stage has no drop-off
        assert result[1]["dropoff_pct"] == 50.0  # 50% drop from 100 to 50

    def test_zero_dropoff(self):
        stages = [
            {"stage": "a", "label": "A", "count": 100},
            {"stage": "b", "label": "B", "count": 100},
        ]
        result = compute_funnel_metrics(stages)
        assert result[1]["dropoff_pct"] == 0.0

    def test_full_dropoff(self):
        stages = [
            {"stage": "a", "label": "A", "count": 100},
            {"stage": "b", "label": "B", "count": 0},
        ]
        result = compute_funnel_metrics(stages)
        assert result[1]["dropoff_pct"] == 100.0

    def test_multi_stage_dropoff(self):
        stages = [
            {"stage": "a", "label": "A", "count": 1000},
            {"stage": "b", "label": "B", "count": 500},
            {"stage": "c", "label": "C", "count": 250},
        ]
        result = compute_funnel_metrics(stages)
        assert result[1]["dropoff_pct"] == 50.0
        assert result[2]["dropoff_pct"] == 50.0

    def test_dropoff_with_zero_previous(self):
        stages = [
            {"stage": "a", "label": "A", "count": 100},
            {"stage": "b", "label": "B", "count": 0},
            {"stage": "c", "label": "C", "count": 0},
        ]
        result = compute_funnel_metrics(stages)
        assert result[2]["dropoff_pct"] is None  # 0/0 = undefined

    def test_first_stage_dropoff_is_none(self):
        stages = [{"stage": "a", "label": "A", "count": 500}]
        result = compute_funnel_metrics(stages)
        assert result[0]["dropoff_pct"] is None


# ── Cumulative conversion ──────────────────────────────────


class TestCumulativeConversion:
    """Tests for compute_funnel_metrics cumulative conversion percentages."""

    def test_first_stage_is_100_percent(self):
        stages = [
            {"stage": "a", "label": "A", "count": 100},
            {"stage": "b", "label": "B", "count": 50},
        ]
        result = compute_funnel_metrics(stages)
        assert result[0]["cumulative_pct"] == 100.0

    def test_basic_cumulative(self):
        stages = [
            {"stage": "a", "label": "A", "count": 100},
            {"stage": "b", "label": "B", "count": 50},
        ]
        result = compute_funnel_metrics(stages)
        assert result[1]["cumulative_pct"] == 50.0

    def test_multi_stage_cumulative(self):
        stages = [
            {"stage": "a", "label": "A", "count": 1000},
            {"stage": "b", "label": "B", "count": 500},
            {"stage": "c", "label": "C", "count": 100},
        ]
        result = compute_funnel_metrics(stages)
        assert result[0]["cumulative_pct"] == 100.0
        assert result[1]["cumulative_pct"] == 50.0
        assert result[2]["cumulative_pct"] == 10.0

    def test_zero_top_of_funnel(self):
        stages = [
            {"stage": "a", "label": "A", "count": 0},
            {"stage": "b", "label": "B", "count": 0},
        ]
        result = compute_funnel_metrics(stages)
        assert result[0]["cumulative_pct"] is None
        assert result[1]["cumulative_pct"] is None

    def test_empty_stages_list(self):
        result = compute_funnel_metrics([])
        assert result == []

    def test_mock_data_cumulative_first_is_100(self):
        tp, coaching, articles = get_mock_data()
        tp = compute_funnel_metrics(tp)
        coaching = compute_funnel_metrics(coaching)
        articles = compute_funnel_metrics(articles)
        assert tp[0]["cumulative_pct"] == 100.0
        assert coaching[0]["cumulative_pct"] == 100.0
        assert articles[0]["cumulative_pct"] == 100.0

    def test_mock_data_last_stage_overall_conversion(self):
        tp, _, _ = get_mock_data()
        tp = compute_funnel_metrics(tp)
        # Last stage cumulative = purchases / page views * 100
        expected = round(tp[-1]["count"] / tp[0]["count"] * 100, 2)
        assert tp[-1]["cumulative_pct"] == expected

    def test_output_has_dropoff_and_cumulative_keys(self):
        stages = [{"stage": "x", "label": "X", "count": 42}]
        result = compute_funnel_metrics(stages)
        assert "dropoff_pct" in result[0]
        assert "cumulative_pct" in result[0]
