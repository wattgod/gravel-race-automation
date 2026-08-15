"""Regression contract for the corrected 2027 Bootlegger cycling identity."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLUG = "bootlegger-100"


def _race() -> dict:
    return json.loads(
        (ROOT / "race-data" / f"{SLUG}.json").read_text(encoding="utf-8")
    )["race"]


def test_bootlegger_uses_the_official_2027_cycling_event():
    race = _race()
    vitals = race["vitals"]

    assert race["display_name"] == "The Bootlegger"
    assert vitals["date_specific"] == "2027: April 17 (Saturday)"
    assert vitals["last_confirmed_date"] == "2027-04-17"
    assert vitals["distance_mi"] == 85
    assert vitals["elevation_ft"] == 7250
    assert vitals["location"] == "Lenoir, North Carolina"
    assert race["logistics"]["official_site"] == (
        "https://www.pisgahproductions.com/events/bootlegger-100/"
    )


def test_bootlegger_is_graded_and_plan_ready():
    race = _race()
    rating = race["gravel_god_rating"]

    assert rating["overall_score"] == 71
    assert rating["tier"] == 2
    assert rating["length"] == 3
    assert rating["elevation"] == 4
    assert race["eligibility"]["status"] == "active"
    assert race["eligibility"]["race_plan_eligible"] is True
    assert race["research_metadata"]["next_edition_status"] == "build_ready"
    assert race["source_review"]["race_date"] == "2027-04-17"


def test_bootlegger_rejects_the_old_running_identity_and_current_course_drift():
    race = _race()
    current_copy = json.dumps(
        {
            "tagline": race["tagline"],
            "vitals": race["vitals"],
            "climate": race["climate"],
            "terrain": race["terrain"],
            "biased_opinion": race["biased_opinion"],
            "logistics": race["logistics"],
            "course_description": race["course_description"],
            "final_verdict": race["final_verdict"],
        }
    )

    for stale in (
        "Dahlonega",
        "North Georgia",
        "100 miles",
        "10,000",
        "bootlegger100.com",
    ):
        assert stale not in current_copy
    assert race["youtube_data"]["videos"] == []
    assert race["photos"] == []


def test_bootlegger_index_uses_corrected_date_location_and_grade():
    race_index = json.loads((ROOT / "web/race-index.json").read_text(encoding="utf-8"))
    indexed = {race["slug"]: race for race in race_index}[SLUG]

    assert indexed["year"] == 2027
    assert indexed["month"] == "April"
    assert indexed["location"] == "Lenoir, North Carolina"
    assert indexed["overall_score"] == 71
    assert indexed["tier"] == 2
