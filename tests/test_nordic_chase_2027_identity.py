"""Regression coverage for the two distinct Nordic Chase gravel races."""

from __future__ import annotations

import json
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wordpress"))

from generate_neo_brutalist import generate_page, load_race_data


ROOT = Path(__file__).resolve().parents[1]
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
RACES = {
    "nordic-chase-gravel": {
        "name": "Nordic Chase Copenhagen to Oslo Gravel",
        "location": "Copenhagen, Denmark to Oslo, Norway",
        "distance_mi": 497,
        "elevation_ft": 23622,
        "score": 66,
        "date_window": "2027 event window: August 13-19",
        "official_page": "https://nordicchase.com/cph-osl-gravel",
    },
    "nordic-chase-berlin-copenhagen-gravel": {
        "name": "Nordic Chase Berlin to Copenhagen Gravel",
        "location": "Berlin, Germany to Copenhagen, Denmark",
        "distance_mi": 454,
        "elevation_ft": 13123,
        "score": 66,
        "date_window": "2027 event window: July 31-August 5",
        "official_page": "https://nordicchase.com/ber-cph-gravel",
    },
}


def _race(slug: str) -> dict:
    return json.loads(
        (ROOT / "race-data" / f"{slug}.json").read_text(encoding="utf-8")
    )["race"]


def test_nordic_chase_gravel_routes_are_distinct_and_graded() -> None:
    for slug, expected in RACES.items():
        race = _race(slug)
        vitals = race["vitals"]
        rating = race["gravel_god_rating"]

        assert race["name"] == expected["name"]
        assert vitals["location"] == expected["location"]
        assert vitals["distance_mi"] == expected["distance_mi"]
        assert vitals["elevation_ft"] == expected["elevation_ft"]
        assert vitals["date_specific"].startswith("TBD —")
        assert expected["date_window"] in vitals["date_specific"]
        assert race["logistics"]["official_site"] == expected["official_page"]
        assert rating["overall_score"] == expected["score"]
        assert round(sum(rating[key] for key in COMPONENTS) / 70 * 100) == expected["score"]
        assert rating["tier"] == rating["display_tier"] == 2
        assert rating["discipline"] == "gravel"
        assert rating["elevation"] == 5
        assert rating["expenses"] == 2


def test_nordic_chase_2027_plans_stay_source_blocked() -> None:
    for slug in RACES:
        race = _race(slug)
        metadata = race["research_metadata"]

        assert race["eligibility"]["status"] == "active"
        assert race["eligibility"]["race_plan_eligible"] is True
        assert race["vitals"]["course_status"] == "source_blocked"
        assert race["vitals"]["course_status_label"] == (
            "2027 GRAND DEPART PENDING"
        )
        assert metadata["validation_status"] == "source_blocked_for_2027_plan"
        assert metadata["next_edition_status"] == (
            "waiting_for_exact_grand_depart_and_final_route"
        )
        assert "Do not clone, date, or publish" in metadata["known_gap"]
        assert "exact grand depart pending" in race["vitals"]["date_specific"]


def test_generated_index_contains_both_nordic_chase_gravel_races() -> None:
    index = json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))
    rows = {row["slug"]: row for row in index if row["slug"] in RACES}

    assert set(rows) == set(RACES)
    for slug, expected in RACES.items():
        row = rows[slug]
        assert row["name"] == expected["name"]
        assert row["location"] == expected["location"]
        assert row["distance_mi"] == expected["distance_mi"]
        assert row["elevation_ft"] == expected["elevation_ft"]
        assert row["overall_score"] == expected["score"]


def test_source_blocked_pages_do_not_publish_a_false_race_day_or_plan_cta() -> None:
    index = json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))

    for slug in RACES:
        race_data = load_race_data(ROOT / "race-data" / f"{slug}.json")
        html = generate_page(race_data, index)

        assert "exact grand depart pending" in html
        assert '"@type":"SportsEvent"' not in html
        assert "data-race-date=" not in html
        assert f"questionnaire/?race={slug}" not in html
