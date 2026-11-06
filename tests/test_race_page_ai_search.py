"""Invisible race page fixes that search engines and AI answers read.

Covers one shared updated date (footer, JSON-LD, sitemap) and the Person
author in the WebPage JSON-LD. None of this changes how the page looks.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_neo_brutalist import (  # noqa: E402
    build_hero,
    build_webpage_jsonld,
    generate_page,
    load_race_data,
)
from page_dates import race_updated_date  # noqa: E402

RACE_INDEX = json.loads((ROOT / "web" / "race-index.json").read_text())


@pytest.fixture(scope="module")
def revival():
    return load_race_data(ROOT / "race-data" / "gravel-revival.json")


def test_one_updated_date_everywhere(revival):
    page = generate_page(revival, RACE_INDEX)
    day = revival["_updated_date"]
    assert day == "2026-10-25"  # newest changelog entry wins over git/mtime
    assert f'"dateModified":"{day}"' in page
    assert "Last updated October 2026" in page


def test_webpage_jsonld_has_person_author(revival):
    author = build_webpage_jsonld(revival)["author"]
    assert author["@type"] == "Person" and author["name"] == "Matti Rowe"
    assert author["url"].endswith("/about/")


def test_hero_has_no_new_visible_elements(revival):
    hero = build_hero(revival)
    assert "gg-hero-summary" not in hero
    assert "gg-hero-byline" not in hero
    assert 'id="changelog"' not in generate_page(revival, RACE_INDEX)


def test_updated_date_resolution_order(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")
    assert race_updated_date({"updated": "2026-01-02", "changelog": [
        {"date": "2026-03-04", "change": "x"}]}, f) == "2026-01-02"
    assert race_updated_date({"changelog": [
        {"date": "2026-03-04", "change": "a"}, {"date": "2026-05-06", "change": "b"}]}, f) == "2026-05-06"
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", race_updated_date({}, f))
    assert race_updated_date({"updated": "not a date"}, f) != "not a date"


def test_sitemap_uses_page_date(tmp_path):
    from generate_sitemap import generate_sitemap

    out = tmp_path / "web" / "sitemap.xml"
    out.parent.mkdir()
    index = [r for r in RACE_INDEX if r["slug"] == "gravel-revival"]
    generate_sitemap(index, out, data_dir=ROOT / "race-data")
    xml = out.read_text()
    entry = xml[xml.index("/race/gravel-revival/</loc>"):]
    assert "<lastmod>2026-10-25</lastmod>" in entry[:200]
