"""Regression contract for the 2026 Nannup Gravel World Championships."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.geocode_races import MANUAL_COORDS


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


def test_nannup_machine_readable_derivatives_cannot_regress_to_europe() -> None:
    dates = json.loads((ROOT / "web" / "race-dates.json").read_text(encoding="utf-8"))
    # The public countdown starts with the two-day championship weekend; the
    # plan itself targets the Sunday long-course categories.
    assert dates["uci-gravel-worlds"] == "2026-10-10"
    assert MANUAL_COORDS["uci-gravel-worlds"] == (-33.9784, 115.7638)

    llms = (ROOT / "web" / "llms-full.txt").read_text(encoding="utf-8")
    worlds_section = llms.split("### UCI Gravel World Championships", 1)[1].split(
        "\n### ", 1
    )[0]
    assert "83/100 | 88.9 mi | 12,182 ft | Nannup" in worlds_section

    brief = (ROOT / "briefs" / "uci-gravel-worlds-brief.md").read_text(
        encoding="utf-8"
    )
    video_briefs = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "video-briefs").glob("*/uci-gravel-worlds.json"))
    )
    current_derivatives = brief + worlds_section + video_briefs
    for stale_fact in ("Heerlen", "Grenoble", "112 mi", "8,202 ft"):
        assert stale_fact not in current_derivatives
