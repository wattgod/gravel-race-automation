"""Regression coverage for the duplicate Font-Romeu race identity."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DUPLICATE = "66-south-pyrenees"
CANONICAL = "pyrenees-catalanes-gravel-tour"


def test_only_canonical_profile_is_active():
    assert (ROOT / "race-data" / f"{CANONICAL}.json").exists()
    assert not (ROOT / "race-data" / f"{DUPLICATE}.json").exists()


def test_duplicate_is_tombstoned_to_the_canonical_race():
    tombstones = json.loads(
        (ROOT / "config" / "tombstones.json").read_text(encoding="utf-8")
    )["tombstones"]
    record = next(item for item in tombstones if item["slug"] == DUPLICATE)

    assert record["redirect"] == f"/race/{CANONICAL}/"
    assert "same September 26, 2026 Font-Romeu" in record["reason"]


def test_duplicate_has_root_and_subpath_redirects():
    deployer = (ROOT / "scripts" / "push_wordpress.py").read_text(
        encoding="utf-8"
    )

    assert (
        "RewriteRule ^race/66-south-pyrenees/?$ "
        "/race/pyrenees-catalanes-gravel-tour/ [R=301,L]"
    ) in deployer
    assert (
        "RewriteRule ^race/66-south-pyrenees/(.*)$ "
        "/race/pyrenees-catalanes-gravel-tour/$1 [R=301,L]"
    ) in deployer


def test_duplicate_is_absent_from_public_catalog_surfaces():
    index = json.loads((ROOT / "web" / "race-index.json").read_text())
    slugs = {row["slug"] for row in index}
    assert CANONICAL in slugs
    assert DUPLICATE not in slugs

    dates = json.loads((ROOT / "web" / "race-dates.json").read_text())
    assert DUPLICATE not in dates

    for path in (ROOT / "web" / "feed" / "races.xml", ROOT / "web" / "sitemap.xml"):
        assert f"/race/{DUPLICATE}/" not in path.read_text()
