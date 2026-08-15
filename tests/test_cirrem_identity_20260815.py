"""Regression coverage for the CIRREM Iowa identity correction."""

from __future__ import annotations

import json
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from race_demand_analyzer import analyze_race_demands
from generate_neo_brutalist import (
    generate_page as generate_race_page,
    load_race_data,
)
from generate_training_plan_pages import (
    generate_page as generate_training_plan_page,
    load_pack,
)


ROOT = Path(__file__).resolve().parent.parent
COMPONENTS = (
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


def _race() -> dict:
    return json.loads((ROOT / "race-data" / "cirrem.json").read_text())["race"]


def test_cirrem_is_the_cumming_iowa_winter_race():
    race = _race()

    assert race["vitals"]["location"] == "Cumming, Iowa"
    assert race["vitals"]["county"] == "Madison County"
    assert race["vitals"]["distance_mi"] == 62
    assert race["vitals"]["elevation_ft"] is None
    assert race["vitals"]["date_specific"] == "2026: February 28"
    assert race["vitals"]["course_status"] == "source_blocked"
    assert race["eligibility"]["status"] == "active"
    assert "not announced a 2027 date" in race["eligibility"]["status_note"]
    assert race["research_metadata"]["research_strength"]["scored_at"] == "2026-08-15"


def test_cirrem_score_uses_all_fourteen_dimensions():
    rating = _race()["gravel_god_rating"]
    raw = sum(rating[key] for key in COMPONENTS)

    assert raw == 39
    assert rating["overall_score"] == round(raw / 70 * 100) == 56
    assert rating["climate"] == 5
    assert rating["tier"] == 3


def test_cirrem_profile_has_no_illinois_or_unrelated_video_contamination():
    race = _race()
    user_facing = {key: value for key, value in race.items() if key != "research_metadata"}
    serialized = json.dumps(user_facing)

    assert "Roubaix, Illinois" not in serialized
    assert "Barry Roubaix" not in serialized
    assert "Unbound Gravel 200" not in serialized
    assert race["youtube_data"] == {"videos": [], "quotes": []}


def test_cirrem_extreme_cold_does_not_become_heat_training():
    demands = analyze_race_demands({"race": _race()})

    assert demands["heat_resilience"] == 0


def test_cirrem_generated_catalog_and_page_use_corrected_identity():
    index = json.loads((ROOT / "web" / "race-index.json").read_text())
    row = next(item for item in index if item["slug"] == "cirrem")
    rd = load_race_data(ROOT / "race-data" / "cirrem.json")
    html = generate_race_page(rd, index)

    assert row["location"] == "Cumming, Iowa"
    assert row["distance_mi"] == 62
    assert row["elevation_ft"] is None
    assert row["overall_score"] == 56
    assert "Cumming, Iowa" in html
    assert "Roubaix, Illinois" not in html
    assert '"startDate":"2026-02-28"' not in html
    assert "calendar.google.com/calendar/render" not in html
    assert 'data-date="2026-02-28"' not in html

    plan_html = generate_training_plan_page(_race(), load_pack("cirrem"))
    assert "NEXT DATE NOT ANNOUNCED" in plan_html
    assert 'data-race-date="2026-02-28"' not in plan_html
    assert "2026: February 28" not in plan_html
    assert "questionnaire/?race=cirrem" not in plan_html

    rss = (ROOT / "web" / "feed" / "races.xml").read_text()
    cirrem_item = rss.split("<title>CIRREM", 1)[1].split("</item>", 1)[0]
    assert "No 2027 date announced; last held February 28, 2026" in cirrem_item
    assert "Location: Cumming, Iowa" in cirrem_item

    standalone_jsonld = json.loads(
        (ROOT / "web" / "jsonld" / "cirrem.jsonld").read_text()
    )
    assert "startDate" not in standalone_jsonld
