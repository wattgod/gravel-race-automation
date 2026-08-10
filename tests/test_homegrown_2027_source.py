"""Regression contracts for the Homegrown Gravel Adventure 2027 refresh."""

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
        (ROOT / "race-data" / "homegrown-gravel-adventure.json").read_text(
            encoding="utf-8"
        )
    )["race"]


def test_homegrown_2027_uses_the_100_mile_event_demands():
    race = _race()
    vitals = race["vitals"]

    assert vitals["distance_mi"] == 100
    assert vitals["elevation_ft"] == 8500
    assert vitals["date_specific"].startswith("2027: February 27")
    assert vitals["start_time"] == "8:30am men; 8:45am women"
    assert race["source_review"]["race_date"] == "2027-02-27"
    assert race["eligibility"]["status"] == "active"
    assert race["logistics"]["official_site"] == "https://homegrowngravel.com/"


def test_homegrown_score_matches_the_published_rubric():
    race = _race()
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]

    assert RATING_KEYS <= rating.keys()
    assert RATING_KEYS <= explained.keys()
    assert all(explained[key]["score"] == rating[key] for key in RATING_KEYS)
    raw = sum(rating[key] for key in RATING_KEYS) + rating.get(
        "cultural_impact", 0
    )
    assert rating["overall_score"] == round(raw / 70 * 100) == 53
    assert rating["tier"] == 3
    assert rating["elevation"] == 4


def test_homegrown_does_not_claim_a_final_2027_route():
    race = _race()
    profile_text = json.dumps(race)

    assert race["course_description"]["suffering_zones"] == []
    assert "final 2027 route" in race["source_review"]["facts_scope"]
    assert "75 miles" not in profile_text
    assert "3,000 feet" not in profile_text
    assert "minimal climbing" not in profile_text


def test_homegrown_race_pack_matches_the_corrected_source():
    pack = json.loads(
        (ROOT / "web" / "race-packs" / "homegrown-gravel-adventure.json").read_text(
            encoding="utf-8"
        )
    )
    pack_text = json.dumps(pack)

    assert pack["distance_mi"] == 100
    assert pack["demands"]["climbing"] == 8
    assert pack["demands"]["heat_resilience"] == 0
    assert "8,500ft" in pack_text
    assert "75 miles" not in pack_text
    assert "3,000ft" not in pack_text


def test_homegrown_race_index_matches_the_corrected_source():
    race_index = json.loads(
        (ROOT / "web" / "race-index.json").read_text(encoding="utf-8")
    )
    indexed = next(
        race for race in race_index if race["slug"] == "homegrown-gravel-adventure"
    )

    assert indexed["year"] == 2027
    assert indexed["distance_mi"] == 100
    assert indexed["elevation_ft"] == 8500
    assert indexed["overall_score"] == 53
    assert indexed["scores"]["elevation"] == 4
