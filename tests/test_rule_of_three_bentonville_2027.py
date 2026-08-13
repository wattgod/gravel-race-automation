"""Regression contract for the real Bentonville Rule of Three identity."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_rule_of_three_is_bentonville_not_a_fabricated_kansas_ultra() -> None:
    race = json.loads(
        (ROOT / "race-data" / "rule-of-three.json").read_text(encoding="utf-8")
    )["race"]
    vitals = race["vitals"]
    rating = race["gravel_god_rating"]

    assert vitals["location"] == "Bentonville, Arkansas"
    assert vitals["date_specific"].startswith("2027: May 15 (Saturday")
    assert vitals["distance_mi"] == 115
    assert vitals["elevation_ft"] is None
    assert rating["overall_score"] == 76
    assert rating["tier"] == rating["display_tier"] == 2

    raw = sum(
        rating[key]
        for key in (
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
    ) + rating["cultural_impact"]
    assert round(raw / 70 * 100) == rating["overall_score"]

    profile = json.dumps(race)
    for stale_fact in (
        "Emporia",
        "Kansas",
        "Unbound roads",
        "300 miles",
        "15,000 ft",
        "ruleofthreegravel.com",
    ):
        assert stale_fact not in profile


def test_rule_of_three_keeps_next_edition_route_uncertainty_explicit() -> None:
    race = json.loads(
        (ROOT / "race-data" / "rule-of-three.json").read_text(encoding="utf-8")
    )["race"]

    assert race["research_metadata"]["validation_status"] == (
        "source_blocked_for_plan_until_2027_route_release"
    )
    assert "new course every year" in race["terrain"]["surface"]
    assert "2027 route is not yet published" in race["course_description"]["character"]
    assert all(
        "pending" in option
        for option in race["vitals"]["route_options"]
    )

    dates = json.loads((ROOT / "web" / "race-dates.json").read_text(encoding="utf-8"))
    assert dates["rule-of-three"] == "2027-05-15"
