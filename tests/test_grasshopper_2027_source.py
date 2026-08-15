"""Regression contracts for the organizer-confirmed 2027 Grasshopper wave."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_index import extract_region


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "low-gap-grasshopper": {
        "date": "2027-01-31",
        "distance": 59,
        "elevation": 6585,
        "surface": {"paved_pct": 5, "dirt_pct": 95},
    },
    "huffmaster-grasshopper": {
        "date": "2027-02-28",
        "distance": 90,
        "elevation": 4866,
        "surface": {"paved_pct": 54, "dirt_pct": 46},
    },
    "jackson-forest-grasshopper": {
        "date": "2027-04-10",
        "distance": 32,
        "elevation": 4138,
        "surface": {"gravel_pct": 65, "singletrack_pct": 35, "paved_pct": 0},
    },
    "ukiah-mendo-gravel-epic": {
        "date": "2027-05-23",
        "distance": 76,
        "elevation": 8420,
        "surface": {"paved_pct": 32, "dirt_pct": 68},
    },
}


def _race(slug: str) -> dict:
    return json.loads(
        (ROOT / "race-data" / f"{slug}.json").read_text(encoding="utf-8")
    )["race"]


def test_grasshopper_wave_uses_organizer_confirmed_2027_facts():
    for slug, expected in EXPECTED.items():
        race = _race(slug)
        vitals = race["vitals"]

        assert vitals["course_status"] == "verified"
        assert vitals["distance_mi"] == expected["distance"]
        assert vitals["elevation_ft"] == expected["elevation"]
        assert vitals["surface_breakdown"] == expected["surface"]
        assert race["source_review"]["race_date"] == expected["date"]
        assert race["eligibility"]["status"] == "active"
        assert race["eligibility"]["race_plan_eligible"] is True
        assert race["research_metadata"]["next_edition_status"] == "build_ready"


def test_grasshopper_wave_preserves_operational_guards():
    for slug in EXPECTED:
        race = _race(slug)
        scope = race["source_review"]["facts_scope"]
        gap = race["research_metadata"]["known_gap"]

        assert "2027" in scope
        assert "Final 2027" in gap
        assert "source_blocked" not in json.dumps(race)


def test_jackson_forest_uses_the_corrected_organizer_date():
    race = _race("jackson-forest-grasshopper")
    profile_text = json.dumps(race)

    assert race["vitals"]["date_specific"] == "2027: April 10 (Saturday)"
    assert "April 24, 2027" not in profile_text
    assert "third-party calendar" not in profile_text


def test_ukiah_is_not_misclassified_as_the_uk():
    assert extract_region("Ukiah, California") == "West"
    assert extract_region("Caspar, California") == "West"
    assert extract_region("Waukon, Iowa") == "Midwest"
    assert extract_region("Across the UK") == "Europe"
    assert extract_region("Tukums, Latvia") == "Europe"

    race_index = json.loads(
        (ROOT / "web" / "race-index.json").read_text(encoding="utf-8")
    )
    indexed = {race["slug"]: race for race in race_index}
    assert indexed["low-gap-grasshopper"]["region"] == "West"
    assert indexed["ukiah-mendo-gravel-epic"]["region"] == "West"
