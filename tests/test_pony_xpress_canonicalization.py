"""Regression coverage for the Pony Xpress 160K identity correction."""

from __future__ import annotations

import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_index


ROOT = Path(__file__).resolve().parent.parent
DUPLICATE = "pony-xpress-gravel-160"
CANONICAL = "pony-xpress"


def test_only_canonical_profile_is_active():
    assert (ROOT / "race-data" / f"{CANONICAL}.json").exists()
    assert not (ROOT / "race-data" / f"{DUPLICATE}.json").exists()


def test_duplicate_is_tombstoned_to_canonical_race():
    tombstones = json.loads(
        (ROOT / "config" / "tombstones.json").read_text()
    )["tombstones"]
    record = next(item for item in tombstones if item["slug"] == DUPLICATE)

    assert record["redirect"] == f"/race/{CANONICAL}/"
    assert "160K" in record["reason"]
    assert "160-mile" in record["reason"]


def test_duplicate_has_root_and_subpath_redirects():
    deployer = (ROOT / "scripts" / "push_wordpress.py").read_text()

    assert (
        "RewriteRule ^race/pony-xpress-gravel-160/?$ "
        "/race/pony-xpress/ [R=301,L]"
    ) in deployer
    assert (
        "RewriteRule ^race/pony-xpress-gravel-160/(.*)$ "
        "/race/pony-xpress/$1 [R=301,L]"
    ) in deployer


def test_duplicate_is_absent_from_generated_catalog_surfaces():
    index = json.loads((ROOT / "web" / "race-index.json").read_text())
    assert CANONICAL in {item["slug"] for item in index}
    assert DUPLICATE not in {item["slug"] for item in index}

    dates = json.loads((ROOT / "web" / "race-dates.json").read_text())
    assert DUPLICATE not in dates

    for path in (ROOT / "web" / "feed" / "races.xml", ROOT / "web" / "sitemap.xml"):
        assert f"/race/{DUPLICATE}/" not in path.read_text()


def test_flat_database_cannot_resurrect_tombstoned_duplicate():
    assert DUPLICATE in generate_index.TOMBSTONED_SLUGS

    flat_database = json.loads(
        (ROOT / "db" / "gravel_races_full_database.json").read_text()
    )
    rows = flat_database.get("races", flat_database)
    assert DUPLICATE in {
        generate_index.slugify(row.get("RACE_NAME", row.get("name", "")))
        for row in rows
    }
