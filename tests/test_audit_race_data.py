"""Regression tests for race-data audit helpers."""

from scripts.audit_race_data import detect_region


def test_us_state_wins_over_bare_south_america_region():
    assert detect_region("Patagonia, Arizona") == "us"


def test_patagonia_without_us_state_remains_south_america():
    assert detect_region("Patagonia, Chile") == "s_america"
    assert detect_region("Bariloche, Patagonia") == "s_america"


def test_us_state_wins_over_bare_europe_region():
    assert detect_region("Wales, Wisconsin") == "us"
