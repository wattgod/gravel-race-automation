"""Per-race SEO overrides (race.seo.title / race.seo.description).

Overrides write {year} and {score} instead of literal values: five overrides
still said "2026" in November 2026, months after those editions ran.
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
    build_seo_description,
    build_seo_title,
    normalize_race_data,
)

OVERRIDES = {
    path.stem: data["race"]["seo"]
    for path in sorted((ROOT / "race-data").glob("*.json"))
    for data in [json.loads(path.read_text())]
    if data.get("race", {}).get("seo")
}
EDITION_YEAR = re.compile(r"\b20[2-3]\d\b")


def _race(date_specific, seo, score=80, tagline="A race."):
    return normalize_race_data({"race": {
        "name": "Test Race", "slug": "test-race", "tagline": tagline,
        "seo": seo,
        "vitals": {"location": "Emporia, Kansas", "date_specific": date_specific},
        "gravel_god_rating": {"overall_score": score, "tier": 1},
    }})


@pytest.mark.parametrize("slug", sorted(OVERRIDES))
def test_override_has_no_literal_edition_year(slug):
    for field, text in OVERRIDES[slug].items():
        assert not EDITION_YEAR.search(text or ""), (
            f"{slug}: seo.{field} names a year; write {{year}} so it follows "
            f"the next edition: {text!r}")


@pytest.mark.parametrize("slug", sorted(OVERRIDES))
def test_override_renders_within_limits(slug):
    rd = normalize_race_data(json.loads((ROOT / "race-data" / f"{slug}.json").read_text()))
    for text in (build_seo_title(rd), build_seo_description(rd)):
        assert "{" not in text and "}" not in text


def test_year_is_the_next_edition(monkeypatch):
    monkeypatch.setenv("GG_TODAY", "2026-11-05")
    rd = _race("2027: June 4", {"title": "Test Race {year}: Course"})
    assert build_seo_title(rd) == "Test Race 2027: Course"


def test_past_edition_uses_the_estimated_year(monkeypatch):
    monkeypatch.setenv("GG_TODAY", "2026-11-05")
    rd = _race("2026: September 19", {"title": "Test Race {year}: Course"})
    assert build_seo_title(rd) == "Test Race 2027: Course"


def test_unknown_year_drops_the_token(monkeypatch):
    monkeypatch.setenv("GG_TODAY", "2026-11-05")
    rd = _race("Check official website", {
        "title": "Test Race {year}: Course",
        "description": "Test Race {year} in Emporia: 100 miles. Our {score}/100.",
    })
    assert build_seo_title(rd) == "Test Race: Course"
    assert build_seo_description(rd) == "Test Race in Emporia: 100 miles. Our 80/100."


def test_truncated_description_never_ends_on_a_preposition():
    tagline = "The original race: 107 miles across 30 road and unroad sectors from Del Mar"
    desc = build_seo_description(_race("2027: May 1", {}, tagline=tagline))
    head = desc.split(" Rated ")[0]
    assert not re.search(r"\b(from|across|through|by|into)\.$", head), head
