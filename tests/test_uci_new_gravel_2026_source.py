"""Regression contracts for official UCI gravel catalog additions."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RATING_KEYS = {
    "logistics", "length", "technicality", "elevation", "climate",
    "altitude", "adventure", "prestige", "race_quality", "experience",
    "community", "field_depth", "value", "expenses",
}


def _race(slug: str) -> dict:
    return json.loads(
        (ROOT / "race-data" / f"{slug}.json").read_text(encoding="utf-8")
    )["race"]


def _assert_score_contract(race: dict, score: int, tier: int) -> None:
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]
    assert set(explained) == RATING_KEYS
    assert all(explained[key]["score"] == rating[key] for key in RATING_KEYS)
    raw = sum(rating[key] for key in RATING_KEYS) + rating.get("cultural_impact", 0)
    assert rating["overall_score"] == round(raw / 70 * 100) == score
    assert rating["tier"] == tier


def test_pyrenees_catalanes_uses_the_official_2026_course() -> None:
    race = _race("pyrenees-catalanes-gravel-tour")
    assert race["vitals"]["date_specific"] == "2026: September 26 (Saturday)"
    assert race["vitals"]["distance_km"] == 100
    assert race["vitals"]["elevation_m"] == 2286
    assert race["vitals"]["max_elevation_asl_ft"] == 6581
    assert race["eligibility"]["race_plan_eligible"] is True
    assert race["source_review"]["race_date"] == "2026-09-26"
    assert race["training_config"]["marketplace_variables"]["dark_mile"] == "55"
    _assert_score_contract(race, 67, 2)


def test_gravel_chile_keeps_first_edition_unknowns_explicit() -> None:
    race = _race("gravel-chile")
    assert race["vitals"]["date_specific"] == "2026: October 3 (Saturday)"
    assert race["vitals"]["distance_km"] == 100
    assert race["vitals"]["elevation_m"] == 665
    assert race["vitals"]["field_size"] == "Not published"
    assert race["course_description"]["surface_breakdown"]["overall"] == {
        "gravel": None, "pavement": None,
    }
    assert race["source_review"]["race_date"] == "2026-10-03"
    _assert_score_contract(race, 54, 3)


def test_gravel_of_marathon_uses_the_official_three_lap_course() -> None:
    race = _race("gravel-of-marathon")
    assert race["vitals"]["date_specific"] == "2026: November 15 (Sunday)"
    assert race["vitals"]["distance_km"] == 121
    assert race["vitals"]["elevation_m"] == 2020
    assert race["course_description"]["surface_breakdown"]["overall"] == {
        "gravel": 90, "pavement": 10,
    }
    assert "three" in race["course_description"]["character"].lower()
    assert race["source_review"]["race_date"] == "2026-11-15"
    _assert_score_contract(race, 57, 3)


def test_new_profiles_cite_only_their_official_race_or_series_sources() -> None:
    for slug in (
        "pyrenees-catalanes-gravel-tour", "gravel-chile", "gravel-of-marathon",
    ):
        race = _race(slug)
        assert all(citation["category"] == "official" for citation in race["citations"])
        assert all(citation["url"].startswith("https://") for citation in race["citations"])
        assert "Not published" in json.dumps(race["vitals"])
