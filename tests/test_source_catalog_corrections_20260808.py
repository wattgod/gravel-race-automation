"""Regression contracts for the August 8 authoritative race corrections."""

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


def _index_entry(slug: str) -> dict:
    index = json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))
    return next(row for row in index if row["slug"] == slug)


def _assert_score_contract(race: dict) -> None:
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]
    assert RATING_KEYS <= rating.keys()
    assert RATING_KEYS <= explained.keys()
    assert all(explained[key]["score"] == rating[key] for key in RATING_KEYS)
    raw = sum(rating[key] for key in RATING_KEYS) + rating.get("cultural_impact", 0)
    assert rating["overall_score"] == round(raw / 70 * 100)


def test_gralloch_is_the_2027_race_not_the_separate_ultra():
    race = _race("the-gralloch")
    vitals = race["vitals"]

    assert race["name"] == "The Gralloch"
    assert vitals["date_specific"] == "2027: May 15"
    assert vitals["distance_km"] == 111
    assert vitals["elevation_m"] == 1761
    assert vitals["location"].startswith("Gatehouse of Fleet")
    assert race["gravel_god_rating"]["overall_score"] == 71
    assert "200 km" not in race["biased_opinion"]["summary"]
    _assert_score_contract(race)

    index = _index_entry("the-gralloch")
    assert index["month"] == "May"
    assert index["year"] == 2027
    assert index["distance_mi"] == 69.0
    assert index["overall_score"] == 71


def test_bikingman_profile_is_the_555_gravel_format():
    race = _race("bikingman-corsica")
    vitals = race["vitals"]

    assert race["name"] == "555 Corsica by BikingMan"
    assert vitals["date_specific"] == "2027: May 27"
    assert vitals["distance_km"] == 500
    assert vitals["elevation_m"] == 10000
    assert vitals["cutoff_time"] == "60 hours"
    assert race["gravel_god_rating"]["discipline"] == "bikepacking"
    assert race["gravel_god_rating"]["overall_score"] == 70
    _assert_score_contract(race)

    index = _index_entry("bikingman-corsica")
    assert index["month"] == "May"
    assert index["year"] == 2027
    assert index["distance_mi"] == 310.7
    assert index["overall_score"] == 70


def test_del_fuego_profile_is_the_2027_hain_flagship():
    race = _race("gravel-del-fuego")
    vitals = race["vitals"]

    assert race["name"] == "Del Fuego Race"
    assert vitals["date_specific"] == "2027: April 10"
    assert vitals["distance_km"] == 1050
    assert vitals["elevation_m"] == 8157
    assert vitals["cutoff_time"] == "5.7 days"
    assert vitals["location"].startswith("Puerto Natales to Caleta María")
    assert race["gravel_god_rating"]["discipline"] == "gravel"
    assert race["gravel_god_rating"]["overall_score"] == 70
    assert "Baqueanos" in race["biased_opinion"]["summary"]
    assert "Milodón" in race["biased_opinion"]["summary"]
    _assert_score_contract(race)

    index = _index_entry("gravel-del-fuego")
    assert index["month"] == "April"
    assert index["year"] == 2027
    assert index["distance_mi"] == 652.4
    assert index["overall_score"] == 70


def test_gravel_roubaix_profile_is_the_titusville_roughneck_race():
    race = _race("gravel-roubaix")
    vitals = race["vitals"]

    assert race["name"] == "Roughneck Gravel Roubaix"
    assert vitals["location"].startswith("Titusville")
    assert vitals["distance_mi"] == 101.9
    assert vitals["elevation_ft"] == 9985
    assert "next edition pending" in vitals["date_specific"]
    assert race["course_description"]["ridewithgps_id"] == "53075138"
    assert race["logistics"]["official_site"].startswith(
        "https://www.oilvalleyendurance.com/"
    )
    assert race["gravel_god_rating"]["overall_score"] == 67
    _assert_score_contract(race)

    profile_text = json.dumps(race)
    assert "Palmerton" not in profile_text
    assert "Sager Road" not in profile_text
    assert "Wissahickon" not in profile_text

    index = _index_entry("gravel-roubaix")
    assert index["name"] == "Roughneck Gravel Roubaix"
    assert index["distance_mi"] == 101.9
    assert index["overall_score"] == 67
