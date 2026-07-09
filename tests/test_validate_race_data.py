"""Tests for scripts/validate_race_data.py -- cross-source race vitals validator.

Covers the parsing/comparison logic (date extraction, None/0 normalization)
and the two conflict-detection paths (known_races.py vs race-data,
gain-vs-ASL confusion) against constructed fixtures, not the real 757-race
dataset.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.validate_race_data import (
    Report,
    _extract_dates,
    _month_num,
    _norm,
    check_internal,
    check_known_races,
)


def _write_race_json(dir_path, slug, vitals, altitude_rating=None):
    race = {"name": slug, "slug": slug, "vitals": vitals}
    if altitude_rating is not None:
        race["gravel_god_rating"] = {"altitude": altitude_rating}
    (dir_path / f"{slug}.json").write_text(json.dumps({"race": race}))


class TestNorm:
    def test_none_and_zero_are_equal(self):
        assert _norm(None) == _norm(0)

    def test_real_values_differ(self):
        assert _norm(100) != _norm(104)


class TestMonthNum:
    def test_full_name(self):
        assert _month_num("October") == 10

    def test_abbreviation(self):
        assert _month_num("Aug") == 8

    def test_unknown_word_returns_none(self):
        assert _month_num("TBD") is None


class TestExtractDates:
    def test_simple_date(self):
        year, days = _extract_dates("2026: October 17")
        assert year == 2026
        assert (10, 17) in days

    def test_range_expands_every_day(self):
        year, days = _extract_dates("2026: Aug 19-23 (Race Aug 22-23)")
        assert year == 2026
        # the actual race day (22) is covered by the "Race Aug 22-23"
        # sub-phrase even though it's not the first date mentioned
        assert (8, 22) in days
        assert (8, 19) in days

    def test_unparseable_text_returns_empty(self):
        year, days = _extract_dates("Mid-October annually")
        assert days == set()

    def test_empty_string(self):
        assert _extract_dates("") == (None, set())


class TestCheckKnownRaces:
    """Reproduces the Big Sugar 104mi (known_races.py) vs 100mi (race-data)
    conflict this validator was built to catch, plus its resolution."""

    def test_distance_mismatch_flagged(self, tmp_path):
        _write_race_json(tmp_path, "big-sugar", {
            "distance_mi": 100, "elevation_ft": 9500,
            "date_specific": "2026: October 17",
        })
        known_races = {
            "big_sugar": {"date": "2026-10-17", "name": "Big Sugar Gravel",
                          "distance_miles": 104, "elevation_ft": 9500},
        }
        report = Report()
        # Monkeypatch the slug map lookup by using the real module mapping
        # (big_sugar -> big-sugar is already registered there).
        check_known_races(report, known_races, race_data_dir=tmp_path)
        messages = [m for _, m in report.conflicts]
        assert any("DISTANCE_MISMATCH" in m for m in messages)

    def test_reconciled_data_has_no_conflict(self, tmp_path):
        """After correcting known_races.py to 100mi (matching race-data),
        no conflict should be reported."""
        _write_race_json(tmp_path, "big-sugar", {
            "distance_mi": 100, "elevation_ft": 9500,
            "date_specific": "2026: October 17",
        })
        known_races = {
            "big_sugar": {"date": "2026-10-17", "name": "Big Sugar Gravel",
                          "distance_miles": 100, "elevation_ft": 9500},
        }
        report = Report()
        check_known_races(report, known_races, race_data_dir=tmp_path)
        assert report.conflicts == []

    def test_unmapped_race_id_warns_instead_of_crashing(self, tmp_path):
        known_races = {"totally_unknown_race": {"date": "2026-01-01",
                                                  "name": "Mystery Race",
                                                  "distance_miles": 50,
                                                  "elevation_ft": 1000}}
        report = Report()
        check_known_races(report, known_races, race_data_dir=tmp_path)
        assert report.conflicts == []
        assert any("UNMAPPED" in m for _, m in report.warnings)


class TestCheckInternalGainVsAsl:
    """(c) the elevation-gain-vs-ASL confusion check -- the exact trap that
    produced the Leadville/SBT GRVL/Big Sugar altitude bug."""

    def test_asl_equal_to_gain_is_flagged(self, tmp_path):
        # A field that's IDENTICAL to the gain figure is almost certainly
        # gain copy-pasted into the ASL slot.
        _write_race_json(tmp_path, "suspect-race", {
            "distance_mi": 100, "elevation_ft": 9500,
            "start_elevation_asl_ft": 9500,
        })
        report = Report()
        check_internal(report, race_data_dir=tmp_path)
        messages = [m for _, m in report.conflicts]
        assert any("GAIN_AS_ASL_SUSPECTED" in m for m in messages)

    def test_distinct_asl_value_not_flagged(self, tmp_path):
        # Big Sugar's real shape: gain=9500, ASL=1300 -- clearly distinct.
        _write_race_json(tmp_path, "big-sugar", {
            "distance_mi": 100, "elevation_ft": 9500,
            "start_elevation_asl_ft": 1300, "avg_elevation_asl_ft": 1300,
        })
        report = Report()
        check_internal(report, race_data_dir=tmp_path)
        assert report.conflicts == []

    def test_implausible_gain_ratio_flagged(self, tmp_path):
        _write_race_json(tmp_path, "steep-race", {
            "distance_mi": 10, "elevation_ft": 5000,  # 500 ft/mi
        })
        report = Report()
        check_internal(report, race_data_dir=tmp_path)
        messages = [m for _, m in report.warnings]
        assert any("IMPLAUSIBLE_GAIN_RATIO" in m for m in messages)

    def test_missing_asl_for_mountain_race_is_aggregated_warning(self, tmp_path):
        _write_race_json(tmp_path, "high-mountain-race",
                          {"distance_mi": 100, "elevation_ft": 10000},
                          altitude_rating=5)
        report = Report()
        check_internal(report, race_data_dir=tmp_path)
        messages = [m for _, m in report.warnings]
        assert any("MISSING_ASL_FOR_MOUNTAIN_RACE" in m for m in messages)
