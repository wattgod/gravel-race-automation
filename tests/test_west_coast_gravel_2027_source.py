"""Regression contracts for the West Coast Gravel 2027 source refresh."""

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


def _race() -> dict:
    return json.loads(
        (ROOT / "race-data" / "west-coast-gravel.json").read_text(
            encoding="utf-8"
        )
    )["race"]


def test_west_coast_gravel_uses_organizer_confirmed_2027_facts():
    race = _race()
    vitals = race["vitals"]

    assert vitals["distance_mi"] == 53
    assert vitals["elevation_ft"] == 6690
    assert vitals["date_specific"] == "2027: April 25 (Sunday)"
    assert race["source_review"]["race_date"] == "2027-04-25"
    assert race["eligibility"]["status"] == "active"
    assert race["logistics"]["official_site"] == (
        "https://www.mudslingerevents.com/west-coast-gravel"
    )


def test_west_coast_gravel_score_matches_the_published_rubric():
    race = _race()
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]

    assert RATING_KEYS <= rating.keys()
    assert RATING_KEYS <= explained.keys()
    assert all(explained[key]["score"] == rating[key] for key in RATING_KEYS)
    raw = sum(rating[key] for key in RATING_KEYS)
    assert rating["overall_score"] == round(raw / 70 * 100) == 44
    assert rating["tier"] == 4
    assert rating["elevation"] == 4


def test_west_coast_gravel_training_inputs_match_sunday_demands():
    race = _race()
    guide = race["guide_variables"]
    config = race["training_config"]

    assert guide["race_date"] == "April 25, 2027"
    assert guide["race_distance"] == "53 miles"
    assert guide["race_elevation"] == "approximately 6,690 feet"
    assert config["workout_modifications"]["dress_rehearsal"]["day"] == "Sunday"
    assert config["marketplace_variables"]["distance"] == "53"


def test_west_coast_gravel_race_index_matches_the_corrected_source():
    race_index = json.loads(
        (ROOT / "web" / "race-index.json").read_text(encoding="utf-8")
    )
    indexed = next(
        race for race in race_index if race["slug"] == "west-coast-gravel"
    )

    assert indexed["year"] == 2027
    assert indexed["distance_mi"] == 53
    assert indexed["elevation_ft"] == 6690
    assert indexed["overall_score"] == 44
    assert indexed["scores"]["elevation"] == 4
