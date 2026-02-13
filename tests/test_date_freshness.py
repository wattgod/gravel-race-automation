"""Tests for data freshness audit script."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from audit_date_freshness import (
    check_content_gaps,
    check_missing_fields,
    check_price_freshness,
    check_stale_dates,
    classify_severity,
    load_race_data,
    parse_year_from_date,
)


# ── parse_year_from_date ──


def test_parse_year_standard():
    assert parse_year_from_date("2026: June 6") == 2026


def test_parse_year_with_range():
    assert parse_year_from_date("2026: October 3-4") == 2026


def test_parse_year_none():
    assert parse_year_from_date(None) is None
    assert parse_year_from_date("") is None


def test_parse_year_no_year():
    assert parse_year_from_date("TBD") is None


def test_parse_year_old():
    assert parse_year_from_date("2023: October 14") == 2023


# ── check_stale_dates ──


def test_stale_dates_tbd():
    race = {"vitals": {"date_specific": "TBD"}}
    issues = check_stale_dates(race)
    assert any("TBD" in i for i in issues)


def test_stale_dates_check_official():
    race = {"vitals": {"date_specific": "Check official website"}}
    issues = check_stale_dates(race)
    assert len(issues) > 0


def test_stale_dates_no_date():
    race = {"vitals": {}}
    issues = check_stale_dates(race)
    assert any("No date" in i for i in issues)


def test_stale_dates_old_year():
    race = {"vitals": {"date_specific": "2023: October 14"}}
    issues = check_stale_dates(race)
    assert any("Stale" in i for i in issues)


def test_stale_dates_current_year():
    race = {"vitals": {"date_specific": "2026: June 6"}}
    issues = check_stale_dates(race)
    assert len(issues) == 0


# ── check_missing_fields ──


def test_missing_no_website():
    race = {"vitals": {}, "logistics": {}, "history": {}, "organizer": {}, "citations": []}
    issues = check_missing_fields(race)
    assert any("website" in i.lower() for i in issues)


def test_missing_has_website():
    race = {
        "vitals": {},
        "logistics": {"official_site": "https://example.com"},
        "history": {"founder": "John"},
        "organizer": {},
        "citations": ["a", "b", "c"],
    }
    issues = check_missing_fields(race)
    assert not any("website" in i.lower() for i in issues)
    assert not any("founder" in i.lower() for i in issues)


def test_missing_few_citations():
    race = {"vitals": {}, "logistics": {"official_site": "https://x.com"},
            "history": {"founder": "Jane"}, "organizer": {}, "citations": ["a"]}
    issues = check_missing_fields(race)
    assert any("citation" in i.lower() for i in issues)


# ── check_content_gaps ──


def test_content_gaps_empty():
    race = {"course_description": {}, "final_verdict": {}, "non_negotiables": []}
    issues = check_content_gaps(race)
    assert len(issues) >= 3  # character, non_negotiables, should_you_race


def test_content_gaps_filled():
    race = {
        "course_description": {"character": "Rolling gravel roads"},
        "final_verdict": {"should_you_race": "Yes, if you like suffering"},
        "non_negotiables": ["Heat training", "Long rides"],
        "tagline": "The OG gravel race",
    }
    issues = check_content_gaps(race)
    assert len(issues) == 0


# ── check_price_freshness ──


def test_price_stale_year():
    race = {"vitals": {"registration": "$150-200 (2023 pricing)"}}
    issues = check_price_freshness(race)
    assert any("2023" in i for i in issues)


def test_price_current_year():
    race = {"vitals": {"registration": "$150-200 (2026 pricing)"}}
    issues = check_price_freshness(race)
    assert len(issues) == 0


# ── classify_severity ──


def test_classify_critical():
    all_issues = {
        "date": ["TBD date: TBD"],
        "missing": [],
        "content": ["No course_description.character", "No non_negotiables", "No final_verdict.should_you_race"],
    }
    assert classify_severity({}, all_issues) == "critical"


def test_classify_stale():
    all_issues = {
        "date": ["Stale date (3yr old): 2023: October 14"],
        "missing": [],
        "content": [],
    }
    assert classify_severity({}, all_issues) == "stale"


def test_classify_gap():
    all_issues = {
        "date": [],
        "missing": ["No official website URL"],
        "content": [],
    }
    assert classify_severity({}, all_issues) == "gap"


def test_classify_none():
    all_issues = {"date": [], "missing": [], "content": []}
    assert classify_severity({}, all_issues) is None


# ── load_race_data ──


def test_load_race_data_returns_list():
    """Verify load_race_data returns a non-empty list."""
    races = load_race_data()
    assert isinstance(races, list)
    assert len(races) > 0


def test_load_race_data_has_slug():
    """Verify each race has _slug field."""
    races = load_race_data()
    for race in races[:5]:
        assert "_slug" in race
