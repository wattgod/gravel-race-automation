"""Regression coverage for the current Rad Dirt Fest identity and course."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _race():
    return json.loads((ROOT / "race-data" / "the-rad.json").read_text())["race"]


def test_duplicate_profile_is_retired_to_the_canonical_race():
    assert not (ROOT / "race-data" / "rad-dirt-fest.json").exists()

    tombstones = json.loads((ROOT / "config" / "tombstones.json").read_text())[
        "tombstones"
    ]
    record = next(item for item in tombstones if item["slug"] == "rad-dirt-fest")
    assert record["redirect"] == "/race/the-rad/"
    assert "stale Salida race facts" in record["reason"]

    deployer = (ROOT / "scripts" / "push_wordpress.py").read_text()
    assert "RewriteRule ^race/rad-dirt-fest/?$ /race/the-rad/ [R=301,L]" in deployer
    assert "RewriteRule ^race/rad-dirt-fest/(.*)$ /race/the-rad/$1 [R=301,L]" in deployer


def test_rad_is_the_current_trinidad_long_course():
    race = _race()
    vitals = race["vitals"]

    assert race["slug"] == "the-rad"
    assert vitals["location"] == "Trinidad, Colorado"
    assert vitals["date_specific"] == "2026: September 26"
    assert vitals["distance_mi"] == 113
    assert vitals["elevation_ft"] == 10613
    assert vitals["start_time"] == "9:30 a.m. for the 110-mile course"
    assert "$190" in vitals["registration"]
    assert "$200" in vitals["registration"]


def test_rad_score_matches_dimension_sum_and_current_course_character():
    race = _race()
    rating = race["gravel_god_rating"]
    dimensions = (
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

    assert sum(rating[key] for key in dimensions) == 48
    assert rating["overall_score"] == 69
    assert rating["technicality"] == 2
    assert race["terrain"]["technical_rating"] == 2


def test_rad_discloses_the_organizer_route_elevation_conflict():
    race = _race()
    notes = race["research_metadata"]["notes"]

    assert "10,613 feet" in notes
    assert "2,522.03 meters" in notes
    assert "8,274 feet" in notes
    assert "51731077" in notes
    assert race["guide_variables"]["altitude_feet"] == 8921


def test_rad_uses_current_primary_sources():
    race = _race()
    urls = {citation["url"] for citation in race["citations"]}

    assert "https://www.theraddirt.com/info/" in urls
    assert "https://www.theraddirt.com/registration/" in urls
    assert "https://www.theraddirt.com/stubborndolores/" in urls
    assert "https://ridewithgps.com/routes/51731077" in urls
    assert race["youtube_data"]["search_query"] == "The Rad gravel race Trinidad"


def test_duplicate_is_absent_from_public_catalog_surfaces():
    index = json.loads((ROOT / "web" / "race-index.json").read_text())
    slugs = {row["slug"] for row in index}
    assert "the-rad" in slugs
    assert "rad-dirt-fest" not in slugs

    for path in (ROOT / "web" / "feed" / "races.xml", ROOT / "web" / "sitemap.xml"):
        assert "/race/rad-dirt-fest/" not in path.read_text()
