"""Regression coverage for the retired Aachen and canonical Winterberg identities."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def _tombstones() -> dict[str, dict]:
    return {
        row["slug"]: row
        for row in json.loads((ROOT / "config" / "tombstones.json").read_text())["tombstones"]
    }


def test_winterberg_is_canonical_and_aachen_is_retired():
    assert (ROOT / "race-data" / "3rides-gravel-winterberg.json").exists()
    assert not (ROOT / "race-data" / "3rides-aachen.json").exists()

    race = json.loads(
        (ROOT / "race-data" / "3rides-gravel-winterberg.json").read_text()
    )["race"]
    assert race["vitals"]["date_specific"] == "2027: TBD"
    assert race["gravel_god_rating"]["overall_score"] == 70
    assert race["gravel_god_rating"]["tier"] == 2
    assert race["research_metadata"]["validation_status"].startswith("source_blocked")


def test_aachen_tombstone_and_redirect_target_winterberg():
    tombstone = _tombstones()["3rides-aachen"]
    assert tombstone["redirect"] == "/race/3rides-gravel-winterberg/"
    assert "moved its gravel event from Aachen" in tombstone["reason"]

    deployer = (ROOT / "scripts" / "push_wordpress.py").read_text()
    assert (
        "RewriteRule ^race/3rides-aachen/?$ "
        "/race/3rides-gravel-winterberg/ [R=301,L]"
    ) in deployer
    assert (
        "RewriteRule ^race/3rides-aachen/(.*)$ "
        "/race/3rides-gravel-winterberg/$1 [R=301,L]"
    ) in deployer


def test_retired_aachen_is_absent_from_active_outputs():
    index = json.loads((ROOT / "web" / "race-index.json").read_text())
    slugs = {row["slug"] for row in index}
    assert "3rides-gravel-winterberg" in slugs
    assert "3rides-aachen" not in slugs

    assert not (ROOT / "web" / "jsonld" / "3rides-aachen.jsonld").exists()
    assert not (ROOT / "web" / "race-packs" / "3rides-aachen.json").exists()

    for path in (
        ROOT / "web" / "feed" / "races.xml",
        ROOT / "web" / "sitemap.xml",
        ROOT / "web" / "gravel-race-search.html",
        ROOT / "web" / "embed" / "embed-data.json",
        ROOT / "web" / "race-dates.json",
    ):
        assert "3rides-aachen" not in path.read_text()
