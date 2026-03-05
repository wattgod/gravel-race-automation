"""Tests for fact_check_profiles.py — comparison tolerances, classifications, auto-fix."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from fact_check_profiles import (
    compare_distance,
    compare_elevation,
    compare_date,
    compare_race,
    auto_fix_race,
    _safe_numeric,
    _extract_month_num,
    _month_distance,
    generate_html_report,
)


# ---------------------------------------------------------------------------
# Safe numeric coercion
# ---------------------------------------------------------------------------

class TestSafeNumeric:
    def test_int(self):
        assert _safe_numeric(200) == 200.0

    def test_float(self):
        assert _safe_numeric(200.5) == 200.5

    def test_string(self):
        assert _safe_numeric("200") == 200.0

    def test_comma_string(self):
        assert _safe_numeric("11,000") == 11000.0

    def test_range_string(self):
        assert _safe_numeric("4,500-9,116") == 4500.0

    def test_none(self):
        assert _safe_numeric(None) is None

    def test_invalid(self):
        assert _safe_numeric("unknown") is None


# ---------------------------------------------------------------------------
# Distance comparison
# ---------------------------------------------------------------------------

class TestCompareDistance:
    def test_exact_match(self):
        cls, _ = compare_distance(200, 200)
        assert cls == "CONFIRM"

    def test_within_5_percent(self):
        """200 vs 208 = 4% diff, within 5% tolerance."""
        cls, _ = compare_distance(200, 208)
        assert cls == "CONFIRM"

    def test_within_2mi_for_small_race(self):
        """20mi race: 5% = 1mi, but minimum tolerance is 2mi."""
        cls, _ = compare_distance(20, 21.5)
        assert cls == "CONFIRM"

    def test_outside_tolerance(self):
        """200 vs 230 = 15% diff, outside 5% tolerance."""
        cls, _ = compare_distance(200, 230)
        assert cls == "MISMATCH"

    def test_enrichable_when_empty(self):
        cls, _ = compare_distance(None, 200)
        assert cls == "ENRICHABLE"

    def test_enrichable_when_zero(self):
        cls, _ = compare_distance(0, 200)
        assert cls == "ENRICHABLE"

    def test_no_scraped_data(self):
        cls, _ = compare_distance(200, None)
        assert cls is None

    def test_detail_includes_values(self):
        _, detail = compare_distance(200, 195)
        assert "200" in detail
        assert "195" in detail


# ---------------------------------------------------------------------------
# Elevation comparison
# ---------------------------------------------------------------------------

class TestCompareElevation:
    def test_exact_match(self):
        cls, _ = compare_elevation(11000, 11000)
        assert cls == "CONFIRM"

    def test_within_15_percent(self):
        """11000 vs 12500 = 13.6% diff, within 15%."""
        cls, _ = compare_elevation(11000, 12500)
        assert cls == "CONFIRM"

    def test_within_500ft_for_small(self):
        """2000ft race: 15% = 300ft, but minimum tolerance is 500ft."""
        cls, _ = compare_elevation(2000, 2400)
        assert cls == "CONFIRM"

    def test_outside_tolerance(self):
        """11000 vs 15000 = 36% diff, outside 15%."""
        cls, _ = compare_elevation(11000, 15000)
        assert cls == "MISMATCH"

    def test_enrichable_when_empty(self):
        cls, _ = compare_elevation(None, 5000)
        assert cls == "ENRICHABLE"

    def test_no_scraped_data(self):
        cls, _ = compare_elevation(11000, None)
        assert cls is None

    def test_string_values(self):
        """String values like '11,000' are handled."""
        cls, _ = compare_elevation("11,000", "11500")
        assert cls == "CONFIRM"


# ---------------------------------------------------------------------------
# Date comparison
# ---------------------------------------------------------------------------

class TestCompareDate:
    def test_stale_to_2026(self):
        """Pre-2026 profile date + 2026 scraped = STALE_DATE."""
        cls, _ = compare_date("2025: July 10", "2026-07-12")
        assert cls == "STALE_DATE"

    def test_both_2026_matching(self):
        """Both 2026 and same month = CONFIRM."""
        cls, _ = compare_date("2026: June 6", "2026-06-07")
        assert cls == "CONFIRM"

    def test_both_2026_mismatch(self):
        """Both 2026 but 3+ month shift = MISMATCH."""
        cls, _ = compare_date("2026: June 6", "2026-10-15")
        assert cls == "MISMATCH"

    def test_no_scraped_date(self):
        cls, _ = compare_date("2025: July 10", None)
        assert cls is None

    def test_enrichable_empty_profile(self):
        cls, _ = compare_date("", "2026-06-06")
        assert cls == "ENRICHABLE"

    def test_enrichable_none_profile(self):
        cls, _ = compare_date(None, "2026-06-06")
        assert cls == "ENRICHABLE"

    def test_adjacent_months_confirm(self):
        """1-month shift counts as CONFIRM."""
        cls, _ = compare_date("2026: June 6", "June 30, 2026")
        assert cls == "CONFIRM"


# ---------------------------------------------------------------------------
# Month extraction / distance
# ---------------------------------------------------------------------------

class TestMonthHelpers:
    def test_extract_month_from_date_specific(self):
        assert _extract_month_num("2026: June 6") == 6

    def test_extract_month_from_iso(self):
        assert _extract_month_num("2026-07-12") == 7

    def test_extract_month_none(self):
        assert _extract_month_num(None) is None

    def test_extract_month_empty(self):
        assert _extract_month_num("") is None

    def test_month_distance_same(self):
        assert _month_distance(6, 6) == 0

    def test_month_distance_adjacent(self):
        assert _month_distance(6, 7) == 1

    def test_month_distance_wrap(self):
        """December to January = 1 month."""
        assert _month_distance(12, 1) == 1

    def test_month_distance_none(self):
        assert _month_distance(None, 6) == 0


# ---------------------------------------------------------------------------
# Auto-fix
# ---------------------------------------------------------------------------

class TestAutoFix:
    def _make_race_file(self, tmp_path, slug, vitals):
        """Create a minimal race JSON for testing."""
        race_dir = tmp_path / "race-data"
        race_dir.mkdir(exist_ok=True)
        data = {"race": {"vitals": vitals, "gravel_god_rating": {"tier": 1}}}
        path = race_dir / f"{slug}.json"
        path.write_text(json.dumps(data, indent=2))
        return path

    def test_fixes_stale_date(self, tmp_path, monkeypatch):
        """Stale date is updated when month shift ≤ 2."""
        path = self._make_race_file(tmp_path, "test-race",
                                     {"date_specific": "2025: July 10"})
        monkeypatch.setattr("fact_check_profiles.RACE_DATA_DIR", tmp_path / "race-data")

        comparison = {
            "slug": "test-race",
            "fields": {
                "date_specific": {
                    "classification": "STALE_DATE",
                    "detail": "...",
                    "profile": "2025: July 10",
                    "scraped": "2026-07-12",
                }
            },
            "summary": "STALE_DATE",
        }

        fixes = auto_fix_race("test-race", comparison)
        assert len(fixes) == 1
        assert "2026-07-12" in fixes[0]

        # Verify file was updated
        updated = json.loads(path.read_text())
        assert updated["race"]["vitals"]["date_specific"] == "2026-07-12"

    def test_rejects_large_month_shift(self, tmp_path, monkeypatch):
        """Date fix is skipped when month shift > 2."""
        self._make_race_file(tmp_path, "test-race",
                             {"date_specific": "2025: July 10"})
        monkeypatch.setattr("fact_check_profiles.RACE_DATA_DIR", tmp_path / "race-data")

        comparison = {
            "slug": "test-race",
            "fields": {
                "date_specific": {
                    "classification": "STALE_DATE",
                    "detail": "...",
                    "profile": "2025: July 10",
                    "scraped": "2026-01-15",  # 6-month shift
                }
            },
            "summary": "STALE_DATE",
        }

        fixes = auto_fix_race("test-race", comparison)
        assert any("SKIPPED" in f for f in fixes)

    def test_never_fixes_mismatch(self, tmp_path, monkeypatch):
        """MISMATCH fields are never auto-fixed."""
        self._make_race_file(tmp_path, "test-race",
                             {"distance_mi": 200})
        monkeypatch.setattr("fact_check_profiles.RACE_DATA_DIR", tmp_path / "race-data")

        comparison = {
            "slug": "test-race",
            "fields": {
                "distance_mi": {
                    "classification": "MISMATCH",
                    "detail": "...",
                    "profile": 200,
                    "scraped": 300,
                }
            },
            "summary": "MISMATCH",
        }

        fixes = auto_fix_race("test-race", comparison)
        assert len(fixes) == 0

    def test_enriches_empty_field(self, tmp_path, monkeypatch):
        """Empty enrichable field is filled."""
        path = self._make_race_file(tmp_path, "test-race", {})
        monkeypatch.setattr("fact_check_profiles.RACE_DATA_DIR", tmp_path / "race-data")

        comparison = {
            "slug": "test-race",
            "fields": {
                "field_size": {
                    "classification": "ENRICHABLE",
                    "detail": "...",
                    "profile": None,
                    "scraped": "~500 riders",
                }
            },
            "summary": "ENRICHABLE",
        }

        fixes = auto_fix_race("test-race", comparison)
        assert len(fixes) == 1

        updated = json.loads(path.read_text())
        assert updated["race"]["vitals"]["field_size"] == "~500 riders"

    def test_dry_run_no_write(self, tmp_path, monkeypatch):
        """Dry run reports fixes but doesn't write."""
        path = self._make_race_file(tmp_path, "test-race",
                                     {"date_specific": "2025: July 10"})
        monkeypatch.setattr("fact_check_profiles.RACE_DATA_DIR", tmp_path / "race-data")
        original = path.read_text()

        comparison = {
            "slug": "test-race",
            "fields": {
                "date_specific": {
                    "classification": "STALE_DATE",
                    "detail": "...",
                    "profile": "2025: July 10",
                    "scraped": "2026-07-12",
                }
            },
            "summary": "STALE_DATE",
        }

        fixes = auto_fix_race("test-race", comparison, dry_run=True)
        assert len(fixes) == 1
        assert path.read_text() == original  # File unchanged


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

class TestReport:
    def test_html_report_structure(self):
        """HTML report contains expected elements."""
        results = [
            {"slug": "race-a", "summary": "MISMATCH",
             "fields": {"distance_mi": {"classification": "MISMATCH", "detail": "profile=200, scraped=300"}}},
            {"slug": "race-b", "summary": "CONFIRM",
             "fields": {"distance_mi": {"classification": "CONFIRM", "detail": "profile=200, scraped=200"}}},
        ]
        html = generate_html_report(results)
        assert "race-a" in html
        assert "race-b" in html
        assert "MISMATCH" in html
        assert "CONFIRM" in html
        assert "<table>" in html

    def test_empty_results(self):
        """Empty results produce valid HTML."""
        html = generate_html_report([])
        assert "<table>" in html
        assert "Total: 0" in html
