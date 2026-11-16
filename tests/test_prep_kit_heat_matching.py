"""Prep-kit heat matching is whole-word, not substring.

classify_climate_heat and the climate-gear fallback used to test heat with
`kw in text`, so "hot" fired on "photo", "sun" on "Sunday", and "90"/"100" on
any distance, elevation or wind speed. Both now go through the race demand
analyzer's whole-word _mentions_heat, plus a temperature pattern that only
counts a 90-119 reading with a degree sign or the literal "85-95" range.
This file is kept identical in road-race-automation and gravel-race-automation.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_prep_kit  # noqa: E402
import race_demand_analyzer  # noqa: E402
from generate_prep_kit import (  # noqa: E402
    _mentions_hot_climate,
    build_climate_gear_callout,
    classify_climate_heat,
)

HEAT_GEAR = "Sun sleeves"


def test_uses_the_demand_analyzer_matcher():
    assert generate_prep_kit._mentions_heat is race_demand_analyzer._mentions_heat


@pytest.mark.parametrize("text", [
    "Sunday start; photo stops at the summit",
    "Sunrise around 4am, sunset after 10pm",
    "Generally mild heathland terrain",
    "Ridge winds can exceed 90 km/h and gust to 100+ km/h",
    "The 190 km route tops out at 1,100 m, around 2,100m altitude",
    "Climbs approaching 900-950m",
])
def test_substrings_are_not_heat(text):
    assert not _mentions_hot_climate(text)


@pytest.mark.parametrize("text", [
    "Expect heat on the exposed climbs",
    "Hot afternoons in the valley",
    "Sun exposure is relentless",
    "Late-summer humidity lingers",
    "Overheating is the main risk",
    "Highs reach 95°F by noon",
    "Valley readings of 105 °F",
    "June brings 85-95 days",
])
def test_heat_words_and_anchored_temperatures_are_heat(text):
    assert _mentions_hot_climate(text)


def test_gear_callout_skips_heat_gear_on_false_positives():
    climate = {
        "primary": "Alpine spring",
        "description": "Sunday start, photo stops, 190 km at 1,100 m",
        "challenges": ["Winds to 100 km/h on the ridge"],
    }
    assert HEAT_GEAR not in build_climate_gear_callout(climate)


def test_gear_callout_keeps_heat_gear_for_real_heat():
    climate = {
        "primary": "Valley summer",
        "description": "Highs of 95°F with high humidity",
        "challenges": ["Heat on the exposed climbs"],
    }
    assert HEAT_GEAR in build_climate_gear_callout(climate)


def test_photo_is_not_hot_for_classification():
    climate = {
        "primary": "Mountain spring",
        "description": "Photo stops along the 190 km route",
        "challenges": [],
    }
    assert classify_climate_heat(climate, 4) == "warm"


def test_hot_word_still_classifies_hot():
    climate = {
        "primary": "Mountain summer",
        "description": "Hot afternoons on the climbs",
        "challenges": [],
    }
    assert classify_climate_heat(climate, 4) == "hot"


def test_degree_reading_still_classifies_hot():
    climate = {
        "primary": "Valley summer",
        "description": "Highs of 95°F",
        "challenges": [],
    }
    assert classify_climate_heat(climate, 4) == "hot"


def test_humid_adjective_still_classifies_hot():
    climate = {"primary": "", "description": "Humid afternoons", "challenges": []}
    assert classify_climate_heat(climate, 4) == "hot"
