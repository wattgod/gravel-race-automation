"""Regression contracts for the organizer-confirmed Dirty Deluxe 2027 refresh."""

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
        (
            ROOT
            / "race-data"
            / "standard-deluxe-dirt-road-century.json"
        ).read_text(encoding="utf-8")
    )["race"]


def test_dirty_deluxe_uses_the_confirmed_2027_event_facts() -> None:
    race = _race()
    vitals = race["vitals"]

    assert race["display_name"] == "Dirty Deluxe Dirt Road Century"
    assert vitals["date"] == "May 22, 2027"
    assert vitals["distance_mi"] == 100
    assert vitals["elevation_ft"] is None
    assert vitals["gain_display"] == "Not published"
    assert vitals["location"] == "Opelika, Alabama"
    assert vitals["field_size"] == "350 riders total across all distances"
    assert vitals["start_time"].startswith("7:00 AM for the 100-mile race")
    assert "$85" in vitals["registration"]
    assert race["source_review"]["race_date"] == "2027-05-22"
    assert race["eligibility"]["status"] == "active"
    assert race["eligibility"]["source"] == "https://www.bikereg.com/77006"


def test_dirty_deluxe_is_build_ready_with_a_final_route_guard() -> None:
    race = _race()
    clearance = race["training_plan_clearance"]

    assert clearance["status"] == "build_ready"
    assert clearance["race_date"] == "2027-05-22"
    assert clearance["ladder"] == "FULL-7"
    assert clearance["variation"] == "All-Rounder"
    assert clearance["blockers"] == []
    assert "Do not claim an elevation total" in clearance["guard"]
    assert "Historical Waverly reports are context only" in clearance["guard"]


def test_dirty_deluxe_does_not_promote_the_old_route_to_2027() -> None:
    race = _race()
    youtube = race["youtube_data"]

    assert race["course_description"]["suffering_zones"] == []
    assert race["guide_variables"]["race_elevation"] == "Not yet published"
    assert "final 2027 route" in race["source_review"]["facts_scope"].lower()
    assert not any(video.get("curated") for video in youtube["videos"])
    assert not any(quote.get("curated") for quote in youtube["quotes"])
    assert youtube["rider_intel"]["key_challenges"] == []
    assert youtube["rider_intel"]["race_day_tips"] == []
    assert all(
        photo["credit"].startswith("Historical Waverly edition")
        for photo in race["photos"]
    )
    assert "4,000" not in json.dumps(
        {
            "vitals": race["vitals"],
            "terrain": race["terrain"],
            "course_description": race["course_description"],
            "guide_variables": race["guide_variables"],
            "marketplace_variables": race["training_config"][
                "marketplace_variables"
            ],
        }
    )


def test_dirty_deluxe_score_remains_rubric_locked() -> None:
    race = _race()
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]

    assert all(explained[key]["score"] == rating[key] for key in RATING_KEYS)
    assert rating["overall_score"] == round(
        sum(rating[key] for key in RATING_KEYS) / 70 * 100
    ) == 49
    assert rating["tier"] == 3
