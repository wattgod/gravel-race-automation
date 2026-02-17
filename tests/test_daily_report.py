"""Tests for scripts/daily_report.py — daily report email system."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.daily_report import (
    collect_ab_status,
    collect_blog_stats,
    collect_data_quality,
    collect_race_stats,
    collect_seo_health,
    generate_commentary,
    render_html,
)


# ── Race Stats ─────────────────────────────────────────────────────


class TestCollectRaceStats:
    def test_tier_counts(self):
        result = collect_race_stats()
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["total"] == 328
        tiers = result["tier_counts"]
        assert "T1" in tiers
        assert "T2" in tiers
        assert "T3" in tiers
        assert "T4" in tiers
        assert sum(tiers.values()) == 328

    def test_upcoming_count(self):
        result = collect_race_stats()
        assert result["upcoming_count"] >= 0
        assert len(result["upcoming_races"]) <= 5


# ── Blog Stats ─────────────────────────────────────────────────────


class TestCollectBlogStats:
    def test_categories(self):
        result = collect_blog_stats()
        if result["total"] > 0:
            assert isinstance(result["categories"], dict)
            assert sum(result["categories"].values()) == result["total"]

    def test_recent_count(self):
        result = collect_blog_stats()
        assert result["recent_count"] >= 0


# ── Data Quality ───────────────────────────────────────────────────


class TestCollectDataQuality:
    def test_stale_date_detection(self):
        result = collect_data_quality()
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["total_profiles"] == 328
        assert result["stale_dates"] >= 0
        assert result["quality_score"] >= 0
        assert result["quality_score"] <= 100

    def test_stub_detection(self):
        result = collect_data_quality()
        assert result["stubs"] >= 0
        assert result["stubs"] <= result["total_profiles"]


# ── A/B Status ─────────────────────────────────────────────────────


class TestCollectAbStatus:
    def test_experiment_parsing(self):
        result = collect_ab_status()
        assert "error" not in result, f"Unexpected error: {result.get('error')}"
        assert result["active_count"] >= 0
        for exp in result["experiments"]:
            assert "id" in exp
            assert "days_running" in exp
            assert exp["days_running"] >= 0
            assert "variants" in exp


# ── SEO Health ─────────────────────────────────────────────────────


class TestCollectSeoHealth:
    def test_sitemap_entries(self):
        result = collect_seo_health()
        assert "error" not in result
        assert result["sitemap_entries"] >= 0


# ── Commentary Engine ──────────────────────────────────────────────


class TestCommentary:
    def test_traffic_up(self):
        data = {
            "ga4": {"configured": True, "sessions_pct_change": 25.0},
            "revenue": {"configured": False},
            "data_quality": {},
            "ab_status": {"experiments": []},
            "athletes": {"configured": False},
        }
        result = generate_commentary(data)
        assert any("up" in b.lower() for b in result)

    def test_traffic_down(self):
        data = {
            "ga4": {"configured": True, "sessions_pct_change": -20.0},
            "revenue": {"configured": False},
            "data_quality": {},
            "ab_status": {"experiments": []},
            "athletes": {"configured": False},
        }
        result = generate_commentary(data)
        assert any("down" in b.lower() for b in result)

    def test_all_clear(self):
        data = {
            "ga4": {"configured": False},
            "revenue": {"configured": False},
            "data_quality": {},
            "ab_status": {"experiments": []},
            "athletes": {"configured": False},
        }
        result = generate_commentary(data)
        assert len(result) >= 1
        assert "steady state" in result[0].lower()

    def test_ab_maturity_warning(self):
        data = {
            "ga4": {"configured": False},
            "revenue": {"configured": False},
            "data_quality": {},
            "ab_status": {
                "experiments": [
                    {"id": "test_exp", "days_running": 15},
                ],
            },
            "athletes": {"configured": False},
        }
        result = generate_commentary(data)
        assert any("test_exp" in b for b in result)
        assert any("evaluating" in b.lower() for b in result)

    def test_revenue_pacing(self):
        data = {
            "ga4": {"configured": False},
            "revenue": {
                "configured": True,
                "target": 10000,
                "pct_of_target": 10.0,
            },
            "data_quality": {},
            "ab_status": {"experiments": []},
            "athletes": {"configured": False},
        }
        # On day 15, expected ~50%. Actual 10% = behind pace.
        with patch("scripts.daily_report.CURRENT_DATE", date(2026, 2, 15)):
            result = generate_commentary(data)
            assert any("behind" in b.lower() for b in result)


# ── Quality Trend Detection ────────────────────────────────────────


class TestQualityTrend:
    def test_improving(self, tmp_path):
        """When stale_dates decrease vs yesterday, commentary notes improvement."""
        yesterday = date.today() - timedelta(days=1)
        reports_dir = tmp_path / "reports" / "daily"
        reports_dir.mkdir(parents=True)
        yesterday_json = reports_dir / f"{yesterday.isoformat()}.json"
        yesterday_json.write_text(json.dumps({
            "data_quality": {"stale_dates": 50},
        }))

        data = {
            "ga4": {"configured": False},
            "revenue": {"configured": False},
            "data_quality": {"stale_dates": 40},
            "ab_status": {"experiments": []},
            "athletes": {"configured": False},
        }

        with patch("scripts.daily_report.REPORTS_DIR", reports_dir):
            result = generate_commentary(data)
            assert any("improving" in b.lower() for b in result)

    def test_degrading(self, tmp_path):
        """When stale_dates increase vs yesterday, commentary notes degradation."""
        yesterday = date.today() - timedelta(days=1)
        reports_dir = tmp_path / "reports" / "daily"
        reports_dir.mkdir(parents=True)
        yesterday_json = reports_dir / f"{yesterday.isoformat()}.json"
        yesterday_json.write_text(json.dumps({
            "data_quality": {"stale_dates": 40},
        }))

        data = {
            "ga4": {"configured": False},
            "revenue": {"configured": False},
            "data_quality": {"stale_dates": 50},
            "ab_status": {"experiments": []},
            "athletes": {"configured": False},
        }

        with patch("scripts.daily_report.REPORTS_DIR", reports_dir):
            result = generate_commentary(data)
            assert any("degrading" in b.lower() for b in result)

    def test_stable(self, tmp_path):
        """No change = no quality trend commentary."""
        yesterday = date.today() - timedelta(days=1)
        reports_dir = tmp_path / "reports" / "daily"
        reports_dir.mkdir(parents=True)
        yesterday_json = reports_dir / f"{yesterday.isoformat()}.json"
        yesterday_json.write_text(json.dumps({
            "data_quality": {"stale_dates": 40},
        }))

        data = {
            "ga4": {"configured": False},
            "revenue": {"configured": False},
            "data_quality": {"stale_dates": 40},
            "ab_status": {"experiments": []},
            "athletes": {"configured": False},
        }

        with patch("scripts.daily_report.REPORTS_DIR", reports_dir):
            result = generate_commentary(data)
            assert not any("improving" in b.lower() or "degrading" in b.lower() for b in result)


# ── HTML Rendering ─────────────────────────────────────────────────


class TestRenderHtml:
    def test_no_ga4_renders_not_configured(self):
        data = {
            "race_stats": {"total": 328, "tier_counts": {"T1": 25, "T2": 73, "T3": 154, "T4": 76}, "upcoming_count": 10, "upcoming_races": []},
            "blog_stats": {"total": 50, "categories": {"preview": 30, "recap": 20}, "recent_count": 0},
            "data_quality": {"total_profiles": 328, "stale_dates": 39, "missing_dates": 7, "stubs": 1, "missing_coords": 5, "quality_score": 85},
            "ab_status": {"active_count": 2, "experiments": [{"id": "test_a", "days_running": 3, "variants": 3, "traffic": 1.0}]},
            "seo_health": {"sitemap_entries": 4, "prep_kits": 328, "race_pages": 328},
            "ga4": {"configured": False},
            "revenue": {"configured": False},
            "athletes": {"configured": False},
            "commentary": ["No notable trends today. Steady state."],
        }
        html = render_html(data)
        assert "Not configured" in html
        assert "GRAVEL GOD" in html
        assert "Daily Report" in html

    def test_full_render_with_mock_data(self):
        data = {
            "race_stats": {"total": 328, "tier_counts": {"T1": 25, "T2": 73, "T3": 154, "T4": 76}, "upcoming_count": 5, "upcoming_races": [{"name": "Unbound 200", "slug": "unbound-200", "tier": 1}]},
            "blog_stats": {"total": 60, "categories": {"preview": 40, "recap": 20}, "recent_count": 2, "recent": []},
            "data_quality": {"total_profiles": 328, "stale_dates": 39, "missing_dates": 7, "stubs": 1, "missing_coords": 5, "quality_score": 85},
            "ab_status": {"active_count": 1, "experiments": [{"id": "homepage_hero_tagline", "days_running": 5, "variants": 3, "traffic": 1.0}]},
            "seo_health": {"sitemap_entries": 4, "prep_kits": 328, "race_pages": 328},
            "ga4": {"configured": True, "sessions_7d": 1200, "sessions_prev_7d": 1000, "sessions_pct_change": 20.0, "top_pages": [{"path": "/gravel-races/", "pageviews": 500}], "sources": [{"channel": "Organic Search", "sessions": 600}], "conversions": []},
            "revenue": {"configured": True, "mtd_revenue": 5000, "target": 10395, "pct_of_target": 48.1, "remaining": 5395, "plans_sold": 3, "pipeline_value": 2000, "month": "February 2026"},
            "athletes": {"configured": True, "total": 25, "active_plans": 5, "delivered": 18, "due_touchpoints": 2, "nps_score": 72, "nps_count": 15},
            "commentary": ["Sessions up 20.0% week-over-week.", "2 athlete touchpoint(s) due today."],
        }
        html = render_html(data)
        # All sections present
        assert "GA4 Analytics" in html
        assert "Revenue" in html
        assert "Athletes" in html
        assert "Race Database" in html
        assert "Blog Content" in html
        assert "Data Quality" in html
        assert "A/B Experiments" in html
        assert "Quick Links" in html
        # No "Not configured" when all sections have data
        assert "Not configured" not in html
        # Brand elements
        assert "#3a2e25" in html
        assert "#B7950B" in html
        assert "Georgia" in html

    def test_html_no_border_radius(self):
        """Neo-brutalist brand: no border-radius anywhere."""
        data = {
            "race_stats": {"total": 0, "tier_counts": {}, "upcoming_count": 0, "upcoming_races": []},
            "blog_stats": {"total": 0, "categories": {}, "recent_count": 0},
            "data_quality": {"error": "test"},
            "ab_status": {"active_count": 0, "experiments": []},
            "seo_health": {"sitemap_entries": 0, "prep_kits": 0, "race_pages": 0},
            "ga4": {"configured": False},
            "revenue": {"configured": False},
            "athletes": {"configured": False},
            "commentary": ["Steady state."],
        }
        html = render_html(data)
        assert "border-radius" not in html
        assert "box-shadow" not in html
