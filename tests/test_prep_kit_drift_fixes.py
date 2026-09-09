"""Regression contracts for the seven reviewed prep-kit drift cases."""

import json
import math
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_neo_brutalist import normalize_race_data  # noqa: E402
from generate_prep_kit import (  # noqa: E402
    build_fueling_calculator_html,
    build_pk_fueling,
    build_pk_header,
    build_terrain_emphasis_callout,
    classify_climate_heat,
    compute_fueling_estimate,
    load_guide_sections,
)


REVIEWED_SLUGS = (
    "gravel-bogota",
    "r3g3",
    "the-insayner",
    "west-coast-slugger",
    "trans-sylvania-epic",
    "bootlegger-100",
    "nordic-chase-gravel",
)


def _load(slug: str) -> tuple[dict, dict]:
    top = json.loads((ROOT / "race-data" / f"{slug}.json").read_text())
    return top["race"], normalize_race_data(top)


@pytest.mark.parametrize(
    ("slug", "expected"),
    (
        ("gravel-bogota", "August 2, 2026 (completed; next edition not announced)"),
        ("r3g3", "May 30, 2026 (completed; next edition not announced)"),
        ("the-insayner", "June 13, 2026 (completed; next edition not announced)"),
        ("west-coast-slugger", "May 17, 2026 (completed; next edition not announced)"),
    ),
)
def test_source_blocked_completed_context_survives_display_projection(slug, expected):
    raw, rd = _load(slug)

    assert rd["vitals"]["date"] == expected
    assert rd["vitals"]["date_specific"] == ""
    assert expected in build_pk_header(rd, raw)


def test_source_blocked_without_explicit_context_does_not_promote_a_stale_date():
    top = {
        "race": {
            "slug": "blocked-example",
            "vitals": {
                "date": "May 1, 2025",
                "date_specific": "",
                "course_status": "source_blocked",
            },
        }
    }

    rd = normalize_race_data(top)

    assert rd["vitals"]["date_specific"] == ""
    assert rd["vitals"]["date"] == "--"


def test_trans_sylvania_status_year_stays_with_its_own_clause():
    raw, rd = _load("trans-sylvania-epic")

    assert rd["vitals"]["date"] == "May 21-23, 2026; 2027 not announced"
    assert rd["vitals"]["date"] in build_pk_header(rd, raw)


def test_climate_classification_requires_heat_evidence_and_keeps_hot_positive():
    bootlegger, bootlegger_rd = _load("bootlegger-100")
    nordic, nordic_rd = _load("nordic-chase-gravel")
    unbound, unbound_rd = _load("unbound-200")

    assert classify_climate_heat(
        bootlegger["climate"], bootlegger_rd["rating"]["climate"]
    ) == "cool"
    assert classify_climate_heat(
        nordic["climate"], nordic_rd["rating"]["climate"]
    ) == "cool"
    assert classify_climate_heat(
        unbound["climate"], unbound_rd["rating"]["climate"]
    ) in {"hot", "extreme"}


@pytest.mark.parametrize("slug", ("alentejo-gravel", "safari-gravel-race"))
def test_warm_or_heat_evidence_outweighs_a_cool_morning(slug):
    raw, rd = _load(slug)

    assert classify_climate_heat(
        raw["climate"], rd["rating"]["climate"]
    ) == "warm"


@pytest.mark.parametrize("slug", REVIEWED_SLUGS)
def test_all_reviewed_profiles_render_their_evidence_without_heat_default(slug):
    raw, rd = _load(slug)
    header = build_pk_header(rd, raw)
    calculator = build_fueling_calculator_html(rd, raw)
    training = build_terrain_emphasis_callout(rd, raw)
    fueling = build_pk_fueling(load_guide_sections(), raw, rd)

    assert rd["name"] in header
    assert 'id="gg-pk-hours"' in calculator

    if slug in {"bootlegger-100", "nordic-chase-gravel"}:
        assert "Start heat adaptation" not in training
        assert "heat and humidity increase fluid and sodium demands" not in fueling
        assert "cool, wet, or windy conditions" in fueling


def test_nordic_valid_estimate_fits_input_without_changing_estimate():
    raw, rd = _load("nordic-chase-gravel")

    estimate = compute_fueling_estimate(497)
    calculator = build_fueling_calculator_html(rd, raw)
    input_tag = re.search(r'<input type="number" id="gg-pk-hours"[^>]+>', calculator)

    assert input_tag
    value = float(re.search(r'value="([0-9.]+)"', input_tag.group()).group(1))
    minimum = float(re.search(r'min="([0-9.]+)"', input_tag.group()).group(1))
    maximum = float(re.search(r'max="([0-9.]+)"', input_tag.group()).group(1))
    step = float(re.search(r'step="([0-9.]+)"', input_tag.group()).group(1))
    assert estimate["hours"] == 49.7
    assert (estimate["carb_rate_lo"], estimate["carb_rate_hi"]) == (30, 50)
    assert value == 49.7
    assert maximum >= value
    assert math.isclose((value - minimum) / step, round((value - minimum) / step))
    assert rd["vitals"]["date"] == (
        "2027: August 13-19 event window; exact grand depart pending"
    )
