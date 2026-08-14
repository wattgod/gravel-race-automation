"""Regression coverage for the current Nedbank Gravel Burn identity and grade."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = (
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
)


def _race() -> dict:
    return json.loads((ROOT / "race-data" / "gravel-burn.json").read_text())["race"]


def test_gravel_burn_is_the_great_karoo_stage_race():
    race = _race()
    vitals = race["vitals"]

    assert vitals["date_specific"] == "2027: October 24-30"
    assert vitals["distance_mi"] == 466
    assert vitals["elevation_ft"] == 27887
    assert "Great Karoo" in vitals["location"]
    assert "Mpumalanga" not in json.dumps(race)
    assert race["history"]["founded"] == "2025"
    assert race["logistics"]["official_site"] == "https://gravel-burn.com/"


def test_gravel_burn_grade_is_synchronized_and_rubric_derived():
    race = _race()
    bare = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]

    assert bare["overall_score"] == 74
    assert bare["tier"] == 2
    assert race["final_verdict"]["score"] == "74 / 100"
    assert all(bare[key] == explained[key]["score"] for key in COMPONENTS)
    assert round(sum(bare[key] for key in COMPONENTS) / 70 * 100) == 74


def test_gravel_burn_2027_route_uncertainty_is_explicit():
    race = _race()
    rendered = json.dumps(race)

    assert "exact stage route is still pending" in rendered
    assert "final 2027 rider guide governs" in rendered
    assert race["research_metadata"]["validation_status"] == "official-source-verified"
    assert "https://gravel-burn.com/entry-info/" in race["research_metadata"]["sources"]


def test_gravel_burn_training_shape_preserves_all_seven_stages():
    race = _race()
    stage = race["training_config"]["workout_modifications"]["stage_block"]

    assert stage["enabled"] is True
    assert stage["stages"] == 7
    assert stage["dates"] == [f"2027-10-{day:02d}" for day in range(24, 31)]
    assert race["training_config"]["marketplace_variables"]["dark_mile"] == "Stage 5"
