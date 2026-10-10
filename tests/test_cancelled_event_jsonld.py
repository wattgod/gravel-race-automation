"""Cancelled races emit SportsEvent JSON-LD with eventStatus EventCancelled.

Google's Event structured-data guidelines require name, startDate and
location, and say a cancelled event keeps its original startDate. A cancelled
race's date_specific is status prose, so the original date comes from
data/cancelled-editions.json.
"""

import copy
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))

import generate_neo_brutalist as gnb  # noqa: E402
from generate_neo_brutalist import (  # noqa: E402
    build_sports_event_jsonld,
    generate_page,
    load_race_data,
)

CANCELLED = "https://schema.org/EventCancelled"
EDITIONS = json.loads((ROOT / "data" / "cancelled-editions.json").read_text(encoding="utf-8"))


def _cancelled_slugs():
    slugs = []
    for path in sorted((ROOT / "race-data").glob("*.json")):
        race = json.loads(path.read_text(encoding="utf-8")).get("race", {})
        if (race.get("eligibility") or {}).get("status") == "cancelled":
            slugs.append(path.stem)
    return slugs


CANCELLED_SLUGS = _cancelled_slugs()


def _page_jsonld(html):
    return [
        json.loads(m)
        for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    ]


def test_known_cancelled_races_are_detected():
    assert {"gravel-fever", "gravel-unravel-why-not-chee"} <= set(CANCELLED_SLUGS)


@pytest.mark.parametrize("slug", CANCELLED_SLUGS)
def test_every_cancelled_race_has_a_sourced_original_date(slug):
    entry = EDITIONS.get(slug)
    assert entry, f"{slug} is cancelled but has no entry in data/cancelled-editions.json"
    start = date.fromisoformat(entry["start_date"])
    end = date.fromisoformat(entry["end_date"])
    assert end >= start
    assert entry["source"].startswith("https://")
    assert entry["evidence"].strip()
    date.fromisoformat(entry["verified"])


@pytest.mark.parametrize("slug", CANCELLED_SLUGS)
def test_cancelled_race_page_emits_valid_cancelled_sports_event(slug):
    rd = load_race_data(ROOT / "race-data" / f"{slug}.json")
    events = [j for j in _page_jsonld(generate_page(rd)) if j.get("@type") == "SportsEvent"]
    assert len(events) == 1, f"{slug}: expected exactly one SportsEvent"
    ev = events[0]

    assert ev["eventStatus"] == CANCELLED
    # Google required properties
    assert ev["name"]
    assert ev["startDate"] == EDITIONS[slug]["start_date"]
    assert ev["endDate"] == EDITIONS[slug]["end_date"]
    assert ev["location"]["@type"] == "Place"
    assert ev["location"]["address"]["@type"] == "PostalAddress"
    assert ev["location"]["address"]["addressCountry"]
    # Recommended properties stay present
    assert ev["description"]
    assert ev["image"]
    assert ev["eventAttendanceMode"] == "https://schema.org/OfflineEventAttendanceMode"
    # Nothing to sell for a cancelled edition
    assert "offers" not in ev


def test_cancelled_status_wins_over_taking_a_break():
    rd = load_race_data(ROOT / "race-data" / "gravel-medellin.json")
    assert rd.get("taking_a_break")
    ev = build_sports_event_jsonld(rd)
    assert ev["eventStatus"] == CANCELLED


def test_cancelled_race_with_price_text_gets_no_offer():
    rd = load_race_data(ROOT / "race-data" / "gravel-unravel-why-not-chee.json")
    assert "$" in rd["vitals"]["registration"]
    assert "offers" not in build_sports_event_jsonld(rd)


def test_cancelled_race_without_original_date_omits_event():
    rd = copy.deepcopy(load_race_data(ROOT / "race-data" / "gravel-fever.json"))
    rd["slug"] = "not-in-cancelled-editions"
    assert build_sports_event_jsonld(rd) is None


def test_invalid_original_date_omits_event(monkeypatch):
    monkeypatch.setattr(
        gnb, "_cancelled_editions_cache",
        {"gravel-fever": {"start_date": "2026-13-40", "end_date": "2026-10-25"}},
    )
    rd = load_race_data(ROOT / "race-data" / "gravel-fever.json")
    assert build_sports_event_jsonld(rd) is None


def test_non_cancelled_race_is_unchanged():
    rd = load_race_data(ROOT / "race-data" / "unbound-200.json")
    assert (rd.get("eligibility") or {}).get("status") != "cancelled"
    ev = build_sports_event_jsonld(rd)
    assert ev["eventStatus"] == "https://schema.org/EventScheduled"
    start, _ = gnb.parse_event_dates(rd["vitals"]["date_specific"])
    assert ev["startDate"] == start
