"""Contracts for the newly cataloged La Épica Gravel Grinder 2027 race."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_neo_brutalist import generate_page, load_race_data


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
        (ROOT / "race-data" / "la-epica-gravel-grinder.json").read_text(
            encoding="utf-8"
        )
    )["race"]


def test_la_epica_uses_only_confirmed_2027_stage_facts() -> None:
    race = _race()
    vitals = race["vitals"]

    assert race["display_name"] == "La Épica Gravel Grinder"
    assert vitals["date"] == "March 26-28, 2027"
    assert vitals["distance_mi"] == 175.2
    assert vitals["elevation_ft"] is None
    assert vitals["gain_display"] == "Not published for 2027"
    assert "Saturday: 170 km queen stage" in vitals["route_options"]
    assert "eight laps of 14 km" in vitals["route_options"][2]
    assert "$165" in vitals["registration"]
    assert race["eligibility"]["race_plan_eligible"] is True


def test_la_epica_is_graded_and_score_locked() -> None:
    race = _race()
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]

    assert all(explained[key]["score"] == rating[key] for key in RATING_KEYS)
    assert rating["overall_score"] == round(
        sum(rating[key] for key in RATING_KEYS) / 70 * 100
    ) == 59
    assert rating["tier"] == rating["display_tier"] == 3
    assert rating["discipline"] == "gravel"


def test_la_epica_plan_clearance_models_the_stage_weekend() -> None:
    clearance = _race()["training_plan_clearance"]

    assert clearance["status"] == "build_ready"
    assert clearance["race_date"] == "2027-03-27"
    assert clearance["event_window"] == "2027-03-26/2027-03-28"
    assert clearance["ladder"] == "FULL-7"
    assert clearance["variation"] == "All-Rounder"
    assert clearance["blockers"] == []
    assert "optional Friday criterium" in clearance["guard"]
    assert "Do not claim a 2027 elevation total" in clearance["guard"]


def test_la_epica_index_and_page_are_generated() -> None:
    index = json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))
    row = next(row for row in index if row["slug"] == "la-epica-gravel-grinder")

    assert row["name"] == "La Épica Gravel Grinder"
    assert row["overall_score"] == 59
    assert row["distance_mi"] == 175.2

    race_data = load_race_data(ROOT / "race-data" / "la-epica-gravel-grinder.json")
    html = generate_page(race_data, index)

    assert "La Épica Gravel Grinder" in html
    assert "170 km" in html
    assert "Not published for 2027" in html
    assert '"@type":"SportsEvent"' in html
    assert "questionnaire/?race=la-epica-gravel-grinder" in html
