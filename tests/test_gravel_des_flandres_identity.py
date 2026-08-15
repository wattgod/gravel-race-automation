"""Regression coverage for the invalid Gravel des Flandres identity."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_invalid_profile_is_retired_with_a_documented_tombstone():
    assert not (ROOT / "race-data" / "gravel-des-flandres.json").exists()

    tombstones = json.loads((ROOT / "config" / "tombstones.json").read_text())[
        "tombstones"
    ]
    record = next(row for row in tombstones if row["slug"] == "gravel-des-flandres")
    assert record["redirect"] == "/race/calendar/2026/"
    assert "no organizer or official event exists" in record["reason"]
    assert "Flanders Gravel Series" in record["reason"]


def test_invalid_profile_redirects_to_the_current_race_calendar():
    deployer = (ROOT / "scripts" / "push_wordpress.py").read_text()
    assert (
        "RewriteRule ^race/gravel-des-flandres/?$ "
        "/race/calendar/2026/ [R=301,L]"
    ) in deployer
    assert (
        "RewriteRule ^race/gravel-des-flandres/(.*)$ "
        "/race/calendar/2026/ [R=301,L]"
    ) in deployer


def test_retired_identity_is_absent_from_public_catalog_outputs():
    index = json.loads((ROOT / "web" / "race-index.json").read_text())
    assert "gravel-des-flandres" not in {row["slug"] for row in index}

    assert not (ROOT / "web" / "jsonld" / "gravel-des-flandres.jsonld").exists()
    assert not (ROOT / "web" / "race-packs" / "gravel-des-flandres.json").exists()

    for path in (
        ROOT / "web" / "feed" / "races.xml",
        ROOT / "web" / "sitemap.xml",
        ROOT / "web" / "gravel-race-search.html",
        ROOT / "web" / "embed" / "embed-data.json",
        ROOT / "web" / "race-dates.json",
        ROOT / "web" / "race-intel.json",
        ROOT / "web" / "llms-full.txt",
    ):
        assert "gravel-des-flandres" not in path.read_text()
