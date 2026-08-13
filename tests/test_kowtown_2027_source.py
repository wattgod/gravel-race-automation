"""Regression coverage for organizer-confirmed KowTown 2027 facts."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _race() -> dict:
    return json.loads(
        (ROOT / "race-data" / "kowtown-gravel.json").read_text(encoding="utf-8")
    )["race"]


def test_kowtown_uses_the_organizer_confirmed_2027_flagship() -> None:
    race = _race()
    vitals = race["vitals"]

    assert vitals["date_specific"] == "2027: June 12 (Saturday)"
    assert vitals["distance_mi"] == 88
    assert vitals["elevation_ft"] is None
    assert vitals["course_status"] == "verified"
    assert race["source_review"]["race_date"] == "2027-06-12"
    assert race["eligibility"]["status"] == "active"
    assert race["logistics"]["official_site"] == "https://www.kowtowngravel.com/"


def test_kowtown_does_not_promote_the_2026_map_to_2027() -> None:
    race = _race()
    scope = race["source_review"]["facts_scope"]

    assert race["course_description"]["suffering_zones"] == []
    assert "not carried forward as a final 2027 GPX" in scope
    assert race["guide_variables"]["race_elevation"] == "not yet published for 2027"
    assert race["training_config"]["marketplace_variables"]["dark_mile"] is None


def test_kowtown_score_remains_rubric_locked() -> None:
    race = _race()
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]
    keys = {
        "logistics", "length", "technicality", "elevation", "climate",
        "altitude", "adventure", "prestige", "race_quality", "experience",
        "community", "field_depth", "value", "expenses",
    }

    assert all(explained[key]["score"] == rating[key] for key in keys)
    assert rating["overall_score"] == round(sum(rating[key] for key in keys) / 70 * 100) == 47
    assert rating["tier"] == 3
