"""Source contracts for the newly discovered 2026 Toppling Goliath race."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLUG = "toppling-goliath-gravel-grinder"


def load_race() -> dict:
    return json.loads(
        (ROOT / f"race-data/{SLUG}.json").read_text(encoding="utf-8")
    )["race"]


def test_toppling_goliath_is_current_graded_and_plan_ready() -> None:
    race = load_race()
    vitals = race["vitals"]
    rating = race["gravel_god_rating"]

    assert vitals["date_specific"] == "2026: October 10"
    assert vitals["distance_mi"] == 62
    assert vitals["elevation_ft"] == 3500
    assert vitals["start_time"] == "100 km 7:30 AM; 50 km 8:00 AM"
    assert "2:00 PM" in vitals["cutoff_time"]
    assert rating["overall_score"] == 57
    assert rating["elevation"] == 2
    assert rating["tier"] == rating["display_tier"] == 3
    score_sum = sum(
        rating[key]
        for key in (
            "logistics", "length", "technicality", "elevation", "climate",
            "altitude", "adventure", "prestige", "race_quality", "experience",
            "community", "field_depth", "value", "expenses",
        )
    )
    assert round(score_sum / 70 * 100) == rating["overall_score"]
    assert race["source_review"]["reviewed_at"] == "2026-08-15"
    assert race["training_config"]["marketplace_variables"][
        "trainingpeaks_url"
    ] is None


def test_toppling_goliath_uses_first_party_facts_without_route_invention() -> None:
    race = load_race()
    citations = race["citations"]

    assert citations[0]["url"] == "https://iowagravelseries.com/goliath/"
    assert race["course_description"]["surface_breakdown"] is None
    assert race["course_description"]["ridewithgps_id"] is None
    assert "not a mile-by-mile current course narrative" in race[
        "course_description"
    ]["character"]
    assert race["youtube_data"] == {"videos": [], "quotes": []}
    assert race["photos"] == []
