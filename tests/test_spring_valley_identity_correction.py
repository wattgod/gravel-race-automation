"""Regression coverage for the Almanzo/Spring Valley and Rasputitsa identities."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _tombstones():
    return {
        row["slug"]: row
        for row in json.loads((ROOT / "config" / "tombstones.json").read_text())["tombstones"]
    }


def test_retired_and_duplicate_profiles_are_not_active():
    assert not (ROOT / "race-data" / "almanzo-100.json").exists()
    assert not (ROOT / "race-data" / "rasputitsa-spring-classic.json").exists()
    assert (ROOT / "race-data" / "spring-valley-100.json").exists()
    assert (ROOT / "race-data" / "rasputitsa.json").exists()


def test_tombstones_route_to_the_current_canonical_pages():
    tombstones = _tombstones()
    assert tombstones["almanzo-100"]["redirect"] == "/race/spring-valley-100/"
    assert "last ran in Spring Valley in 2018" in tombstones["almanzo-100"]["reason"]
    assert tombstones["rasputitsa-spring-classic"]["redirect"] == "/race/rasputitsa/"
    assert "duplicate historical name" in tombstones["rasputitsa-spring-classic"]["reason"]


def test_spring_valley_current_identity_and_route_are_verified():
    race = json.loads((ROOT / "race-data" / "spring-valley-100.json").read_text())["race"]
    assert race["display_name"] == "Spring Valley Wilder 100"
    assert race["vitals"]["distance_mi"] == 102
    assert race["vitals"]["elevation_ft"] == 5174
    assert race["vitals"]["registration"] == "Online via BikeReg. 2026 price: $35"
    assert race["course_description"]["ridewithgps_id"] == "54987672"
    assert race["gravel_god_rating"]["overall_score"] == 47
    # 47 >= 45 with prestige 1 is Tier 3 by score alone (#68).
    assert race["gravel_god_rating"]["tier"] == 3
    assert race["gravel_god_rating"]["display_tier"] == 3


def test_legacy_urls_have_root_and_subpath_redirects():
    deployer = (ROOT / "scripts" / "push_wordpress.py").read_text()
    for old, new in (
        ("almanzo-100", "spring-valley-100"),
        ("rasputitsa-spring-classic", "rasputitsa"),
    ):
        assert f"RewriteRule ^race/{old}/?$ /race/{new}/ [R=301,L]" in deployer
        assert f"RewriteRule ^race/{old}/(.*)$ /race/{new}/$1 [R=301,L]" in deployer


def test_legacy_slugs_are_absent_from_public_catalog_outputs():
    index = json.loads((ROOT / "web" / "race-index.json").read_text())
    slugs = {row["slug"] for row in index}
    assert "spring-valley-100" in slugs
    assert "rasputitsa" in slugs
    assert "almanzo-100" not in slugs
    assert "rasputitsa-spring-classic" not in slugs

    for path in (ROOT / "web" / "feed" / "races.xml", ROOT / "web" / "sitemap.xml"):
        text = path.read_text()
        assert "/race/almanzo-100/" not in text
        assert "/race/rasputitsa-spring-classic/" not in text
