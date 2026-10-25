"""Race page elements that search engines and AI answers read first.

Covers the answer-first summary, named rater byline, one shared updated date
(byline, footer, JSON-LD, sitemap), the visible changelog and the HTML
comparison table for similar races.
"""
import html
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_neo_brutalist import (  # noqa: E402
    ANSWER_SUMMARY_MAX_WORDS,
    build_answer_summary,
    build_changelog,
    build_hero,
    build_hero_byline,
    build_similar_races,
    build_webpage_jsonld,
    generate_page,
    load_race_data,
)
from page_dates import format_display_date, race_updated_date  # noqa: E402

RACE_INDEX = json.loads((ROOT / "web" / "race-index.json").read_text())


@pytest.fixture(scope="module")
def revival():
    return load_race_data(ROOT / "race-data" / "gravel-revival.json")


def _summary_words(fragment: str) -> int:
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    return len(text.split())


def test_summary_is_40_to_60_words(revival):
    words = _summary_words(build_answer_summary(revival))
    assert 40 <= words <= ANSWER_SUMMARY_MAX_WORDS


def test_summary_states_page_facts(revival):
    text = html.unescape(build_answer_summary(revival))
    assert "68-mile gravel race in Hickman County, Tennessee" in text
    assert "3,000 feet of climbing" in text
    assert "The 2026 edition runs October 16-18." in text
    assert "Lab score: 46/100, Tier 3." in text


@pytest.mark.parametrize("slug", ["big-sugar", "unbound-200", "the-equalizer", "croatan-buck-fifty"])
def test_summary_never_exceeds_cap(slug):
    path = ROOT / "race-data" / f"{slug}.json"
    if not path.exists():
        pytest.skip(f"{slug} not in race-data")
    rd = load_race_data(path)
    assert _summary_words(build_answer_summary(rd)) <= ANSWER_SUMMARY_MAX_WORDS


def test_summary_sits_under_h1(revival):
    hero = build_hero(revival)
    assert hero.index("<h1>") < hero.index("gg-hero-byline") < hero.index("gg-hero-summary")


def test_byline_names_rater_and_date(revival):
    byline = build_hero_byline(revival)
    assert 'rel="author"' in byline and "Matti Rowe" in byline
    assert f'datetime="{revival["_updated_date"]}"' in byline
    assert 'href="#changelog"' in byline


def test_changelog_from_race_data(revival):
    section = build_changelog(revival)
    assert 'id="changelog"' in section
    assert 'datetime="2026-10-25"' in section


def test_no_changelog_section_without_entries(revival):
    rd = dict(revival, _changelog=[])
    assert build_changelog(rd) == ""
    assert "#changelog" not in build_hero_byline(rd)


def test_one_updated_date_everywhere(revival):
    page = generate_page(revival, RACE_INDEX)
    day = revival["_updated_date"]
    assert day == "2026-10-25"  # newest changelog entry wins over git/mtime
    assert f'"dateModified":"{day}"' in page
    assert f"Last updated {format_display_date(day)}" in page
    assert f'<time datetime="{day}">' in page


def test_webpage_jsonld_has_person_author(revival):
    author = build_webpage_jsonld(revival)["author"]
    assert author["@type"] == "Person" and author["name"] == "Matti Rowe"
    assert author["url"].endswith("/about/")


def test_similar_races_is_html_table_with_self_row(revival):
    section = build_similar_races(revival, RACE_INDEX)
    assert '<table class="gg-similar-table">' in section
    assert "<caption>" in section
    assert section.count("<tr") == 1 + 1 + 6  # header + this race + 6 similar
    assert "This race" in section


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
