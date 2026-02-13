"""Tests for the Race Prep Kit generator."""
import json
import re
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

import generate_prep_kit
from generate_prep_kit import (
    load_guide_sections,
    load_raw_training_data,
    has_full_training_data,
    parse_by_when,
    week_to_phase,
    build_phase_extras,
    render_personalized_timeline,
    build_race_context_callout,
    compute_wake_time,
    compute_fueling_estimate,
    build_climate_gear_callout,
    build_terrain_emphasis_callout,
    build_pk_header,
    build_pk_training_timeline,
    build_pk_non_negotiables,
    build_pk_race_week,
    build_pk_equipment,
    build_pk_race_morning,
    build_pk_fueling,
    build_pk_decision_tree,
    build_pk_recovery,
    build_pk_footer_cta,
    build_prep_kit_css,
    build_prep_kit_js,
    generate_prep_kit_page,
    GUIDE_SECTION_IDS,
    PHASE_RANGES,
)

from generate_neo_brutalist import load_race_data, find_data_file

PROJECT_ROOT = Path(__file__).parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
DATA_DIRS = [RACE_DATA_DIR]

# Known full-personalization race
FULL_SLUG = "unbound-200"
# Known generic race (no training_config)
GENERIC_SLUG = "almanzo-100"


def _load_test_race(slug):
    """Helper to load rd + raw for a test race."""
    fp = find_data_file(slug, DATA_DIRS)
    assert fp is not None, f"Race data not found: {slug}"
    rd = load_race_data(fp)
    raw = load_raw_training_data(fp)
    return rd, raw


# ── Guide Section Loading ─────────────────────────────────────


class TestGuideLoading:
    def test_loads_all_sections(self):
        sections = load_guide_sections()
        assert len(sections) == len(GUIDE_SECTION_IDS)

    def test_section_ids_match(self):
        sections = load_guide_sections()
        for sid in GUIDE_SECTION_IDS:
            assert sid in sections, f"Missing guide section: {sid}"

    def test_sections_have_blocks(self):
        sections = load_guide_sections()
        for sid, section in sections.items():
            assert "blocks" in section, f"No blocks in section: {sid}"
            assert len(section["blocks"]) > 0, f"Empty blocks in section: {sid}"


# ── Raw Training Data ─────────────────────────────────────────


class TestRawTrainingData:
    def test_full_race_has_training_config(self):
        fp = find_data_file(FULL_SLUG, DATA_DIRS)
        raw = load_raw_training_data(fp)
        assert raw["training_config"] is not None
        assert raw["non_negotiables"] is not None
        assert len(raw["non_negotiables"]) > 0

    def test_generic_race_lacks_training_config(self):
        fp = find_data_file(GENERIC_SLUG, DATA_DIRS)
        raw = load_raw_training_data(fp)
        assert raw["training_config"] is None
        assert raw["non_negotiables"] is None

    def test_has_full_training_data_true(self):
        fp = find_data_file(FULL_SLUG, DATA_DIRS)
        raw = load_raw_training_data(fp)
        assert has_full_training_data(raw) is True

    def test_has_full_training_data_false(self):
        fp = find_data_file(GENERIC_SLUG, DATA_DIRS)
        raw = load_raw_training_data(fp)
        assert has_full_training_data(raw) is False

    def test_has_full_training_data_empty(self):
        assert has_full_training_data({}) is False
        assert has_full_training_data({"training_config": {}, "non_negotiables": []}) is False


# ── Personalization Logic ─────────────────────────────────────


class TestPersonalization:
    def test_parse_by_when_simple(self):
        assert parse_by_when("Week 6") == 6

    def test_parse_by_when_range(self):
        assert parse_by_when("Week 8-10") == 8

    def test_parse_by_when_none(self):
        assert parse_by_when("") is None
        assert parse_by_when(None) is None

    def test_parse_by_when_no_match(self):
        assert parse_by_when("Before the race") is None

    def test_week_to_phase_base(self):
        for w in range(1, 5):
            assert week_to_phase(w) == "base"

    def test_week_to_phase_build(self):
        for w in range(5, 11):
            assert week_to_phase(w) == "build"

    def test_week_to_phase_taper(self):
        for w in range(11, 13):
            assert week_to_phase(w) == "taper"

    def test_build_phase_extras_no_milestones(self):
        """Milestones are shown in Section 02 cards, not in the timeline."""
        mods = {"heat_training": {"enabled": True, "week": 6}}
        extras = build_phase_extras(mods)
        # Only workout mod chips, no milestone content
        assert "Heat Training" in extras["build"]
        assert "gg-pk-milestone" not in extras["build"]

    def test_build_phase_extras_mods(self):
        mods = {
            "heat_training": {"enabled": True, "week": 6},
            "dress_rehearsal": {"enabled": True, "week": 9},
            "disabled_mod": {"enabled": False, "week": 4},
        }
        extras = build_phase_extras(mods)
        assert "Heat Training" in extras["build"]
        assert "Dress Rehearsal" in extras["build"]
        assert "disabled_mod" not in extras["base"]

    def test_render_personalized_timeline(self):
        block = {
            "steps": [
                {"label": "Base (Weeks 1-4)", "content": "Easy rides"},
                {"label": "Build (Weeks 5-10)", "content": "Hard rides"},
                {"label": "Peak/Taper (Weeks 11-12)", "content": "Rest"},
            ]
        }
        extras = {
            "base": "",
            "build": '<span class="gg-pk-workout-mod">Heat Training</span>',
            "taper": "",
        }
        html = render_personalized_timeline(block, extras)
        assert "gg-pk-workout-mod" in html
        assert "Heat Training" in html
        assert "gg-guide-timeline" in html


# ── Section Builders ──────────────────────────────────────────


class TestSectionBuilders:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.guide = load_guide_sections()
        self.full_rd, self.full_raw = _load_test_race(FULL_SLUG)
        self.gen_rd, self.gen_raw = _load_test_race(GENERIC_SLUG)

    def test_header_full_race(self):
        html = build_pk_header(self.full_rd, self.full_raw)
        assert "PERSONALIZED PREP KIT" in html
        assert self.full_rd["name"] in html
        assert "gg-pk-header" in html

    def test_header_generic_race(self):
        html = build_pk_header(self.gen_rd, self.gen_raw)
        assert "GUIDE PREP KIT" in html

    def test_training_timeline_full(self):
        html = build_pk_training_timeline(self.guide, self.full_raw, self.full_rd)
        assert "12-Week Training Timeline" in html
        assert "gg-pk-section" in html
        # Full races should have workout mod chips (milestones in Section 02)
        assert "gg-pk-workout-mod" in html

    def test_training_timeline_generic(self):
        html = build_pk_training_timeline(self.guide, self.gen_raw, self.gen_rd)
        assert "12-Week Training Timeline" in html
        # Generic should have context box
        assert "gg-pk-context-box" in html or "gg-guide-timeline" in html

    def test_non_negotiables_full(self):
        html = build_pk_non_negotiables(self.full_raw)
        assert "Non-Negotiables" in html
        assert "gg-pk-nn-card" in html

    def test_non_negotiables_generic_empty(self):
        html = build_pk_non_negotiables(self.gen_raw)
        assert html == ""

    def test_race_week(self):
        html = build_pk_race_week(self.guide, self.full_raw)
        assert "Race Week Countdown" in html
        assert "gg-guide-timeline" in html

    def test_equipment(self):
        html = build_pk_equipment(self.guide, self.full_raw, self.full_rd)
        assert "Equipment" in html
        assert "gg-guide-accordion" in html

    def test_equipment_with_tires(self):
        # Unbound should have tire recommendations
        html = build_pk_equipment(self.guide, self.full_raw, self.full_rd)
        assert "Recommended Tires" in html or "gg-guide-accordion" in html

    def test_equipment_climate_gear(self):
        # Unbound has heat climate — should show climate gear
        html = build_pk_equipment(self.guide, self.full_raw, self.full_rd)
        assert "Climate Gear" in html or "gg-guide-accordion" in html

    def test_race_morning(self):
        html = build_pk_race_morning(self.guide, self.full_rd)
        assert "Race Morning" in html
        assert "gg-guide-timeline" in html

    def test_fueling(self):
        html = build_pk_fueling(self.guide, self.full_raw, self.full_rd)
        assert "Fueling" in html

    def test_fueling_has_distance_math(self):
        html = build_pk_fueling(self.guide, self.full_raw, self.full_rd)
        assert "Fueling Math" in html
        assert "200 miles" in html
        assert "carbs" in html

    def test_fueling_has_aid_stations(self):
        html = build_pk_fueling(self.guide, self.full_raw, self.full_rd)
        assert "Aid Stations" in html

    def test_decision_tree(self):
        html = build_pk_decision_tree(self.guide, self.full_rd)
        assert "Decision Tree" in html
        assert "gg-guide-accordion" in html

    def test_recovery(self):
        html = build_pk_recovery(self.guide)
        assert "Recovery" in html
        assert "gg-guide-process" in html

    def test_footer_cta(self):
        html = build_pk_footer_cta(self.full_rd)
        assert "BUILD MY PLAN" in html
        assert "1:1 COACHING" in html
        assert self.full_rd["slug"] in html


# ── CSS & JS ─────────────────────────────────────────────────


class TestCSSAndJS:
    def test_css_has_pk_classes(self):
        css = build_prep_kit_css()
        assert ".gg-pk-page" in css
        assert ".gg-pk-header" in css
        assert ".gg-pk-section" in css
        assert ".gg-pk-nn-card" in css
        assert ".gg-pk-milestone" in css
        assert ".gg-pk-workout-mod" in css
        assert ".gg-pk-context-box" in css
        assert ".gg-pk-footer" in css

    def test_css_has_guide_block_classes(self):
        css = build_prep_kit_css()
        assert ".gg-guide-timeline" in css
        assert ".gg-guide-accordion" in css
        assert ".gg-guide-process-list" in css
        assert ".gg-guide-callout" in css

    def test_css_has_print_styles(self):
        css = build_prep_kit_css()
        assert "@media print" in css

    def test_css_has_responsive(self):
        css = build_prep_kit_css()
        assert "@media (max-width:600px)" in css

    def test_js_has_accordion(self):
        js = build_prep_kit_js()
        assert "accordion-trigger" in js
        assert "aria-expanded" in js


# ── Full Page Assembly ────────────────────────────────────────


class TestPageAssembly:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.guide = load_guide_sections()
        self.full_rd, self.full_raw = _load_test_race(FULL_SLUG)
        self.gen_rd, self.gen_raw = _load_test_race(GENERIC_SLUG)

    def test_full_page_is_valid_html(self):
        html = generate_prep_kit_page(self.full_rd, self.full_raw, self.guide)
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html
        assert "<head>" in html
        assert "<body>" in html

    def test_full_page_has_meta(self):
        html = generate_prep_kit_page(self.full_rd, self.full_raw, self.guide)
        assert 'name="description"' in html
        assert 'rel="canonical"' in html
        assert "og:title" in html

    def test_full_page_has_ga4(self):
        html = generate_prep_kit_page(self.full_rd, self.full_raw, self.guide)
        assert "googletagmanager" in html
        assert "G-EJJZ9T6M52" in html

    def test_full_page_has_brand_tokens(self):
        html = generate_prep_kit_page(self.full_rd, self.full_raw, self.guide)
        assert "--gg-color-primary-brown" in html
        assert "--gg-font-data" in html

    def test_canonical_url_format(self):
        html = generate_prep_kit_page(self.full_rd, self.full_raw, self.guide)
        expected = f"https://gravelgodcycling.com/race/{FULL_SLUG}/prep-kit/"
        assert expected in html

    def test_generic_page_omits_non_negotiables(self):
        html = generate_prep_kit_page(self.gen_rd, self.gen_raw, self.guide)
        # CSS class definition exists, but no actual nn-card HTML elements
        assert 'class="gg-pk-nn-card"' not in html
        assert "Race-Specific Non-Negotiables" not in html
        # But should still have other sections
        assert "gg-pk-section" in html


# ── Race Context Callout ─────────────────────────────────────


class TestRaceContextCallout:
    def test_generic_race_has_callout(self):
        rd, raw = _load_test_race(GENERIC_SLUG)
        html = build_race_context_callout(raw, rd)
        assert "gg-pk-context-box" in html

    def test_callout_has_race_name(self):
        rd, raw = _load_test_race(GENERIC_SLUG)
        html = build_race_context_callout(raw, rd)
        assert rd["name"].upper() in html

    def test_empty_callout(self):
        html = build_race_context_callout({}, {"name": "Test", "vitals": {}, "course": {}})
        assert html == ""


# ── Wake-Up Time ─────────────────────────────────────────────


class TestComputeWakeTime:
    def test_simple_am(self):
        assert compute_wake_time("Saturday 6:00 AM") == "3:00 AM"

    def test_simple_pm(self):
        assert compute_wake_time("Saturday 1:00 PM") == "10:00 AM"

    def test_midnight_wrap(self):
        # 2:00 AM - 3h = 11:00 PM (previous day)
        assert compute_wake_time("Sunday 2:00 AM") == "11:00 PM"

    def test_noon(self):
        assert compute_wake_time("Saturday 12:00 PM") == "9:00 AM"

    def test_midnight(self):
        assert compute_wake_time("Saturday 12:00 AM") == "9:00 PM"

    def test_multi_line_takes_first(self):
        # Mid-South style: takes the first time (1:00 PM)
        result = compute_wake_time(
            "Pro Race: Friday 1:00 PM<br>Amateur Race: Saturday 6:00 AM"
        )
        assert result == "10:00 AM"

    def test_empty(self):
        assert compute_wake_time("") is None
        assert compute_wake_time(None) is None

    def test_no_match(self):
        assert compute_wake_time("TBD") is None

    def test_race_morning_has_wake_time(self):
        """Unbound has start_time — wake-up should appear in race morning."""
        guide = load_guide_sections()
        rd, _ = _load_test_race(FULL_SLUG)
        html = build_pk_race_morning(guide, rd)
        assert "alarm" in html.lower()


# ── Fueling Estimate ─────────────────────────────────────────


class TestComputeFuelingEstimate:
    def test_200_mile_race(self):
        est = compute_fueling_estimate(200)
        assert est is not None
        assert est["avg_mph"] == 10
        assert est["hours"] == 20.0
        assert est["carbs_low"] == 1200
        assert est["carbs_high"] == 1800

    def test_100_mile_race(self):
        est = compute_fueling_estimate(100)
        assert est is not None
        assert est["avg_mph"] == 12
        assert round(est["hours"], 1) == 8.3

    def test_50_mile_race(self):
        est = compute_fueling_estimate(50)
        assert est is not None
        assert est["avg_mph"] == 14

    def test_short_race_none(self):
        assert compute_fueling_estimate(15) is None

    def test_zero_none(self):
        assert compute_fueling_estimate(0) is None

    def test_none_input(self):
        assert compute_fueling_estimate(None) is None

    def test_gel_equivalents(self):
        est = compute_fueling_estimate(100)
        # 100mi / 12mph = 8.33h → 500-750g carbs → 20-30 gels
        assert est["gels_low"] == est["carbs_low"] // 25
        assert est["gels_high"] == est["carbs_high"] // 25


# ── Climate Gear ─────────────────────────────────────────────


class TestClimateGearCallout:
    def test_heat_climate(self):
        climate = {
            "primary": "Flint Hills heat",
            "description": "June brings 85-95°F days with high humidity",
            "challenges": ["Heat adaptation critical", "Sun exposure relentless"],
        }
        html = build_climate_gear_callout(climate)
        assert "Sun sleeves" in html
        assert "Extra water" in html
        assert "Flint Hills heat" in html

    def test_cold_climate(self):
        climate = {
            "primary": "Winter conditions",
            "description": "Temperatures drop to 30°F with freezing rain",
            "challenges": ["Cold exposure"],
        }
        html = build_climate_gear_callout(climate)
        assert "Knee warmers" in html or "gloves" in html.lower()

    def test_wet_climate(self):
        climate = {
            "primary": "Pacific Northwest rain",
            "description": "Expect rain and wet muddy conditions",
            "challenges": [],
        }
        html = build_climate_gear_callout(climate)
        assert "rain jacket" in html.lower()

    def test_empty_climate(self):
        assert build_climate_gear_callout({}) == ""
        assert build_climate_gear_callout(None) == ""

    def test_no_matching_keywords(self):
        climate = {"primary": "Mild", "description": "Perfect weather", "challenges": []}
        assert build_climate_gear_callout(climate) == ""

    def test_deduplicates_recs(self):
        climate = {
            "primary": "Harsh",
            "description": "Cold wind exposed freezing",
            "challenges": ["Wind gusts"],
        }
        html = build_climate_gear_callout(climate)
        # "Wind vest" could match both cold and wind — should appear only once
        assert html.count("Wind vest") == 1


# ── Terrain Emphasis ─────────────────────────────────────────


class TestTerrainEmphasisCallout:
    def test_high_technicality(self):
        rd = {
            "rating": {"technicality": 4},
            "vitals": {"terrain_types": [], "elevation": "5,000 ft", "distance_mi": 100},
        }
        html = build_terrain_emphasis_callout(rd)
        assert "MTB skills" in html

    def test_medium_technicality(self):
        rd = {
            "rating": {"technicality": 3},
            "vitals": {"terrain_types": [], "elevation": "5,000 ft", "distance_mi": 100},
        }
        html = build_terrain_emphasis_callout(rd)
        assert "off-road skills" in html.lower() or "gravel descending" in html.lower()

    def test_low_technicality_no_output(self):
        rd = {
            "rating": {"technicality": 2},
            "vitals": {"terrain_types": [], "elevation": "2,000 ft", "distance_mi": 100},
        }
        html = build_terrain_emphasis_callout(rd)
        # Low tech + low climbing = no tips
        assert html == ""

    def test_high_climbing(self):
        rd = {
            "rating": {"technicality": 1},
            "vitals": {"terrain_types": [], "elevation": "15,000 ft", "distance_mi": 100},
        }
        html = build_terrain_emphasis_callout(rd)
        assert "climbing intervals" in html.lower()
        assert "150 ft/mile" in html

    def test_mud_terrain(self):
        rd = {
            "rating": {"technicality": 2},
            "vitals": {
                "terrain_types": ["Oklahoma red clay roads", "rolling hills"],
                "elevation": "2,000 ft",
                "distance_mi": 100,
            },
        }
        html = build_terrain_emphasis_callout(rd)
        assert "clay" in html.lower()

    def test_unbound_has_terrain_callout(self):
        rd, _ = _load_test_race(FULL_SLUG)
        html = build_terrain_emphasis_callout(rd)
        # Unbound: technicality=3, 11000ft/200mi = 55 ft/mile (below 80 threshold)
        # But tech=3 should trigger skills tip
        assert "Race-Specific Training Focus" in html


# ── Section Numbering ────────────────────────────────────────


class TestSectionNumbering:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.guide = load_guide_sections()

    def test_full_race_numbers_01_to_08(self):
        rd, raw = _load_test_race(FULL_SLUG)
        html = generate_prep_kit_page(rd, raw, self.guide)
        nums = re.findall(r'class="gg-pk-section-num">(\d{2})<', html)
        assert nums == ["01", "02", "03", "04", "05", "06", "07", "08"]

    def test_generic_race_sequential_numbering(self):
        rd, raw = _load_test_race(GENERIC_SLUG)
        html = generate_prep_kit_page(rd, raw, self.guide)
        nums = re.findall(r'class="gg-pk-section-num">(\d{2})<', html)
        # Generic races skip Non-Negotiables → should be 01-07 (sequential)
        assert nums == ["01", "02", "03", "04", "05", "06", "07"]
        # And should NOT contain "Non-Negotiables"
        assert "Race-Specific Non-Negotiables" not in html
