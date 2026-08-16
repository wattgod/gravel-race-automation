"""Current-source contracts for Birkebeinerrittet Sykkel 2027."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "race-data" / "birkebeinerrittet-road.json"
DIMENSIONS = (
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


def _race() -> dict:
    return json.loads(PROFILE.read_text(encoding="utf-8"))["race"]


def test_birkebeinerrittet_uses_the_official_2027_identity() -> None:
    race = _race()
    vitals = race["vitals"]

    assert race["slug"] == "birkebeinerrittet-road"
    assert vitals["date_specific"] == "2027: August 28"
    assert vitals["distance_mi"] == 52.2
    assert vitals["elevation_ft"] == 3986
    assert vitals["discipline"] == "mtb"
    assert race["eligibility"]["race_plan_eligible"] is True
    assert race["source_review"]["race_date"] == "2027-08-28"


def test_birkebeinerrittet_course_uses_current_organizer_landmarks() -> None:
    race = _race()
    text = json.dumps(race, ensure_ascii=False)
    labels = {
        zone["label"] for zone in race["course_description"]["suffering_zones"]
    }

    assert labels == {
        "Djuposet",
        "Rosinbakkene to Storåsen",
        "Final Descent to Lillehammer",
    }
    for fact in (
        "84-kilometer",
        "1,200–1,300 meters",
        "955 meters",
        "Håkons Hall",
        "Ballettbakken",
        "at least 2 kilograms",
    ):
        assert fact in text
    assert "Raudfjellet" not in text
    assert "Midtfjellet" not in text
    assert "Lillehammer (490m)" not in text


def test_birkebeinerrittet_does_not_promote_2026_operations_to_2027() -> None:
    race = _race()
    review = race["source_review"]["facts_scope"]
    guard = race["training_plan_clearance"]["guard"]

    assert "still publishes 2026 operations" in review
    for unknown in (
        "Exact 2027 waves",
        "aid service",
        "cutoffs",
        "fees",
        "transport times",
        "rules",
        "route revision",
    ):
        assert unknown in review
    assert "final 2027" in guard
    assert "posted fee and traffic plan are for 2026" in race["logistics"]["parking"]


def test_birkebeinerrittet_grade_matches_the_published_rubric() -> None:
    race = _race()
    rating = race["gravel_god_rating"]
    opinion = race["biased_opinion_ratings"]

    assert rating["length"] == 2
    assert rating["logistics"] == 3
    assert rating["value"] == 3
    assert rating["expenses"] == 2
    base = sum(rating[key] for key in DIMENSIONS)
    assert base == 44
    assert rating["cultural_impact"] == 2
    assert round((base + 2) / 70 * 100) == rating["overall_score"] == 66
    assert race["vitals"]["overall_score"] == 66
    assert rating["tier"] == race["vitals"]["tier"] == 2
    for key in DIMENSIONS:
        assert opinion[key]["score"] == rating[key]
    assert opinion["cultural_impact"]["score"] == 2


def test_birkebeinerrittet_clearance_preserves_the_full_ladder() -> None:
    clearance = _race()["training_plan_clearance"]

    assert clearance["status"] == "build_ready"
    assert clearance["race_date"] == "2027-08-28"
    assert clearance["ladder"] == "FULL-7"
    assert clearance["variation"] == "All-Rounder"
    assert clearance["blockers"] == []


def test_birkebeinerrittet_citations_are_current_primary_sources() -> None:
    urls = {row["url"] for row in _race()["citations"]}

    assert urls == {
        "https://birken.no/en/all-races",
        "https://birken.no/en/cycling/birkebeinerrittet-84-km",
        "https://birken.no/en/undersider-sykkel/track-description-birkebeinerrittet",
        "https://birken.no/en/about-birken/the-birkebeiner-history/history-birkebeinerrittet",
    }
