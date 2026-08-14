"""Official-source contracts for the eight missing 2026 UCI gravel qualifiers."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLUGS = (
    "gravel-arteaga-mexico",
    "og-classique",
    "grand-tour-3-cime-lavaredo",
    "gravel-tour-hlinsko",
    "gravel-weekend-tukums",
    "the-wolf-dronninglund",
    "falling-leaves-lahti",
    "tartu-rattamaraton-gravel",
)
SCORE_KEYS = {
    "logistics", "length", "technicality", "elevation", "climate",
    "altitude", "adventure", "prestige", "race_quality", "experience",
    "community", "field_depth", "value", "expenses",
}


def race(slug: str) -> dict:
    return json.loads(
        (ROOT / "race-data" / f"{slug}.json").read_text(encoding="utf-8")
    )["race"]


def test_all_missing_uci_qualifiers_have_complete_rubric_scores() -> None:
    for slug in SLUGS:
        profile = race(slug)
        rating = profile["gravel_god_rating"]
        explained = profile["biased_opinion_ratings"]
        assert set(explained) == SCORE_KEYS
        assert all(explained[key]["score"] == rating[key] for key in SCORE_KEYS)
        assert all(len(explained[key]["explanation"]) >= 60 for key in SCORE_KEYS)
        raw = sum(rating[key] for key in SCORE_KEYS) + rating["cultural_impact"]
        assert rating["overall_score"] == round(raw / 70 * 100)
        assert rating["tier"] == 2


def test_objective_course_facts_match_the_official_uci_pages() -> None:
    expected = {
        "gravel-arteaga-mexico": (133, 1648, "2026-08-30"),
        "og-classique": (124, 1548, "2026-06-21"),
        "grand-tour-3-cime-lavaredo": (133, 3170, "2026-06-20"),
        "gravel-tour-hlinsko": (129, 1577, "2026-08-01"),
        "gravel-weekend-tukums": (140, None, "2026-08-08"),
        "the-wolf-dronninglund": (165, 1398, "2026-09-05"),
        "falling-leaves-lahti": (175, 1586, "2026-09-12"),
        "tartu-rattamaraton-gravel": (126, 1500, "2026-09-19"),
    }
    for slug, (distance_km, elevation_m, race_date) in expected.items():
        profile = race(slug)
        assert profile["vitals"]["distance_km"] == distance_km
        assert profile["vitals"]["elevation_m"] == elevation_m
        assert profile["source_review"]["race_date"] == race_date
        assert profile["source_review"]["reviewed_at"] == "2026-08-14"


def test_no_new_profile_projects_a_2026_course_into_an_unannounced_2027_edition() -> None:
    falling = race("falling-leaves-lahti")
    assert "September 12 (Saturday)" in falling["vitals"]["date_specific"]
    assert "no 2027 Falling Leaves date" in falling["vitals"]["date_specific"]
    assert "separately cataloged event" in falling["eligibility"]["status_note"]
    assert "must not be inferred" in falling["source_review"]["facts_scope"]

    for slug in set(SLUGS) - {"falling-leaves-lahti"}:
        assert "no organizer-confirmed 2027 date" in race(slug)["eligibility"][
            "status_note"
        ]


def test_profiles_cite_only_official_organizer_or_uci_sources() -> None:
    for slug in SLUGS:
        profile = race(slug)
        assert len(profile["citations"]) >= 3
        assert all(citation["category"] == "official" for citation in profile["citations"])
        assert all(citation["url"].startswith("https://") for citation in profile["citations"])


def test_known_official_source_conflicts_remain_explicit() -> None:
    arteaga = race("gravel-arteaga-mexico")["source_review"]["facts_scope"]
    wolf = race("the-wolf-dronninglund")["source_review"]["facts_scope"]
    assert "133/135 km" in arteaga and "1,648/2,200 m" in arteaga
    assert "does not reconcile" in wolf
