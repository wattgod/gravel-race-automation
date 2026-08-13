"""Regression contract for the 2026 Nannup Gravel World Championships."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RATING_KEYS = (
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


def test_uci_gravel_worlds_uses_the_2026_nannup_edition() -> None:
    race = json.loads(
        (ROOT / "race-data" / "uci-gravel-worlds.json").read_text(encoding="utf-8")
    )["race"]
    vitals = race["vitals"]
    rating = race["gravel_god_rating"]
    explained = race["biased_opinion_ratings"]

    assert vitals["location"] == "Nannup, Western Australia, Australia"
    assert vitals["date_specific"].endswith("Sunday, October 11")
    assert vitals["distance_km"] == 143
    assert vitals["distance_mi"] == 88.9
    assert vitals["elevation_m"] == 3713
    assert vitals["elevation_ft"] == 12182
    assert race["course_description"]["surface_breakdown"]["overall"] == {
        "gravel": 80,
        "pavement": 20,
    }
    assert "ridewithgps_id" not in race["course_description"]

    assert all(rating[key] == explained[key]["score"] for key in RATING_KEYS)
    raw = sum(rating[key] for key in RATING_KEYS) + rating["cultural_impact"]
    assert rating["overall_score"] == round(raw / 70 * 100) == 83
    assert rating["tier"] == rating["display_tier"] == 1

    profile_text = json.dumps(race)
    for stale_fact in (
        "Rotating (2024: Heerlen, Netherlands)",
        "2025 UCI Gravel World Championships - Elite men 181",
        "Gravel (70%)",
        "8,202ft",
    ):
        assert stale_fact not in profile_text


def test_nannup_index_and_training_preview_match_the_profile() -> None:
    index = json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))
    entry = next(row for row in index if row["slug"] == "uci-gravel-worlds")
    preview = json.loads(
        (ROOT / "web" / "race-packs" / "uci-gravel-worlds.json").read_text(
            encoding="utf-8"
        )
    )

    assert entry["location"].startswith("Nannup")
    assert entry["distance_mi"] == preview["distance_mi"] == 88.9
    assert entry["elevation_ft"] == 12182
    assert entry["overall_score"] == 83
    assert preview["demands"]["climbing"] == 10

    preview_text = json.dumps(preview)
    assert "Heerlen" not in preview_text
    assert "8,202" not in preview_text
    assert "112 miles" not in preview_text
