"""Regression contracts for the De Ronde and Gravel n Granite 2027 refresh."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RATING_KEYS = {
    "logistics",
    "length",
    "technicality",
    "elevation",
    "climate",
    "altitude",
    "adventure",
    "prestige",
    "race_quality",
    "experience",
    "community",
    "field_depth",
    "value",
    "expenses",
}


def _race(slug: str) -> dict:
    return json.loads(
        (ROOT / "race-data" / f"{slug}.json").read_text(encoding="utf-8")
    )["race"]


def _assert_score_contract(race: dict, expected_score: int, expected_tier: int) -> None:
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]

    assert all(explained[key]["score"] == rating[key] for key in RATING_KEYS)
    raw = sum(rating[key] for key in RATING_KEYS) + rating.get("cultural_impact", 0)
    assert rating["overall_score"] == round(raw / 70 * 100) == expected_score
    assert rating["tier"] == expected_tier


def test_de_ronde_uses_the_confirmed_2027_date_and_current_long_course() -> None:
    race = _race("de-ronde-van-grampian")
    vitals = race["vitals"]

    assert vitals["date_specific"] == "2027: August 7 (Saturday)"
    assert vitals["distance_mi"] == 52
    assert vitals["elevation_ft"] == 3123
    assert vitals["aid_stations"] == (
        "One aid station at approximately mile 33 on the long course"
    )
    assert race["source_review"]["race_date"] == "2027-08-07"
    assert race["eligibility"]["status"] == "active"
    assert race["course_description"]["official_route_url"].endswith(
        "3255687889976907442"
    )
    assert race["course_description"]["ridewithgps_name"].startswith("Historical")
    _assert_score_contract(race, 43, 4)


def test_de_ronde_labels_the_course_year_boundary() -> None:
    race = _race("de-ronde-van-grampian")
    scope = race["source_review"]["facts_scope"]

    assert "remains labeled 2026" in scope
    assert "not represented as a final 2027 GPX" in scope
    assert race["vitals"]["start_time"] == "Not published for 2027"


def test_gravel_n_granite_uses_only_published_2027_core_facts() -> None:
    race = _race("gravel-and-granite")
    vitals = race["vitals"]

    assert race["name"] == "Gravel n Granite"
    assert vitals["date_specific"].startswith("2027: March 6")
    assert vitals["distance_mi"] == 56.5
    assert vitals["elevation_ft"] is None
    assert vitals["start_time"] == "Not published for 2027"
    assert race["source_review"]["race_date"] == "2027-03-06"
    assert race["eligibility"]["status"] == "active"
    assert race["guide_variables"]["race_elevation"] == (
        "not yet published for 2027"
    )
    assert race["course_description"]["suffering_zones"] == []
    _assert_score_contract(race, 41, 4)


def test_gravel_n_granite_removes_misattributed_wisconsin_claims() -> None:
    race = _race("gravel-and-granite")
    trust_surface = json.dumps(
        {
            "vitals": race["vitals"],
            "terrain": race["terrain"],
            "course_description": race["course_description"],
            "guide_variables": race["guide_variables"],
            "biased_opinion_ratings": race["biased_opinion_ratings"],
            "citations": race["citations"],
        }
    )

    assert "Wausau" not in trust_surface
    assert "ironbull" not in trust_surface.lower()
    assert "4,500" not in trust_surface
    assert "65 miles" not in trust_surface
    assert "March 5-7, 2027" in trust_surface
