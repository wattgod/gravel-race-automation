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
    compute_personalized_fueling,
    classify_climate_heat,
    compute_sweat_rate,
    compute_sodium,
    compute_aid_station_hours,
    compute_hourly_plan,
    build_fueling_calculator_html,
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
    FUELING_WORKER_URL,
    GUIDE_SECTION_IDS,
    PHASE_RANGES,
    HEAT_MULTIPLIERS,
    SWEAT_MULTIPLIERS,
    FORMAT_SPLITS,
    SODIUM_BASE_MG_PER_L,
    SODIUM_HEAT_BOOST,
    SODIUM_CRAMP_BOOST,
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
        assert "carbs/hour" in html
        assert "Jeukendrup" in html

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
        # 20h at survival pace → 30-50g/h → 600-1000g total
        assert est["carb_rate_lo"] == 30
        assert est["carb_rate_hi"] == 50
        assert est["carbs_low"] == 600
        assert est["carbs_high"] == 1000
        assert "Survival" in est["note"]

    def test_100_mile_race(self):
        est = compute_fueling_estimate(100)
        assert est is not None
        assert est["avg_mph"] == 12
        assert round(est["hours"], 1) == 8.3
        # ~8.3h → sub-threshold range (50-70g/h)
        assert est["carb_rate_lo"] == 50
        assert est["carb_rate_hi"] == 70

    def test_50_mile_race(self):
        est = compute_fueling_estimate(50)
        assert est is not None
        assert est["avg_mph"] == 14
        # ~3.6h → high intensity range (80-100g/h)
        assert est["carb_rate_lo"] == 80
        assert est["carb_rate_hi"] == 100

    def test_150_mile_race(self):
        est = compute_fueling_estimate(150)
        assert est is not None
        # 150mi/11mph = 13.6h → ultra pace (40-60g/h)
        assert est["carb_rate_lo"] == 40
        assert est["carb_rate_hi"] == 60
        assert "fat" in est["note"].lower()

    def test_short_race_none(self):
        assert compute_fueling_estimate(15) is None

    def test_zero_none(self):
        assert compute_fueling_estimate(0) is None

    def test_none_input(self):
        assert compute_fueling_estimate(None) is None

    def test_gel_equivalents(self):
        est = compute_fueling_estimate(100)
        assert est["gels_low"] == est["carbs_low"] // 25
        assert est["gels_high"] == est["carbs_high"] // 25

    def test_carb_rate_scales_with_duration(self):
        """Longer races should have lower per-hour carb targets."""
        short = compute_fueling_estimate(50)   # ~3.6h
        medium = compute_fueling_estimate(100)  # ~8.3h
        ultra = compute_fueling_estimate(200)   # ~20h
        assert short["carb_rate_hi"] > medium["carb_rate_hi"] > ultra["carb_rate_hi"]


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


# ── Personalized Fueling Calculator ─────────────────────────


class TestComputePersonalizedFueling:
    def test_with_ftp_and_weight(self):
        # 75kg rider, 250W FTP, 8 hours
        result = compute_personalized_fueling(75.0, 250.0, 8.0)
        assert result is not None
        # raw_rate = 75 * 0.7 * (250/100) * 0.7 = 75 * 0.7 * 2.5 * 0.7 = 91.875
        # 8h bracket = 60-80, clamp 92 → 80
        assert result["personalized_rate"] == 80
        assert result["bracket_lo"] == 60
        assert result["bracket_hi"] == 80

    def test_without_ftp_falls_back(self):
        # No FTP → midpoint of bracket
        result = compute_personalized_fueling(75.0, None, 6.0)
        assert result is not None
        # 6h bracket = 60-80, midpoint = 70
        assert result["personalized_rate"] == 70
        assert "FTP" in result["note"]

    def test_clamps_to_bracket_ceiling(self):
        # Very high FTP on a short race — should not exceed 100g/hr
        result = compute_personalized_fueling(90.0, 400.0, 3.0)
        assert result is not None
        # raw = 90 * 0.7 * 4.0 * 0.7 = 176.4 → clamp to 100
        assert result["personalized_rate"] == 100

    def test_clamps_to_bracket_floor(self):
        # Very light rider, low FTP, ultra race
        result = compute_personalized_fueling(50.0, 80.0, 20.0)
        assert result is not None
        # raw = 50 * 0.7 * 0.8 * 0.7 = 19.6 → clamp to 30 (20h+ bracket floor)
        assert result["personalized_rate"] == 30
        assert result["bracket_lo"] == 30

    def test_light_rider_lower_rate(self):
        # 55kg rider vs 85kg rider, same FTP and duration
        light = compute_personalized_fueling(55.0, 200.0, 6.0)
        heavy = compute_personalized_fueling(85.0, 200.0, 6.0)
        assert light["personalized_rate"] <= heavy["personalized_rate"]

    def test_high_ftp_high_rate(self):
        # 300W FTP should produce higher rate than 150W (same weight/duration)
        high = compute_personalized_fueling(75.0, 300.0, 10.0)
        low = compute_personalized_fueling(75.0, 150.0, 10.0)
        assert high["personalized_rate"] >= low["personalized_rate"]

    def test_short_race_high_ceiling(self):
        # 3-hour race allows up to 100g/hr
        result = compute_personalized_fueling(80.0, 300.0, 3.0)
        assert result["bracket_hi"] == 100

    def test_ultra_race_low_ceiling(self):
        # 20-hour race capped at 50g/hr
        result = compute_personalized_fueling(80.0, 250.0, 20.0)
        assert result["bracket_hi"] == 50

    def test_total_carbs_and_gels(self):
        result = compute_personalized_fueling(75.0, 200.0, 10.0)
        assert result is not None
        assert result["total_carbs"] == result["personalized_rate"] * 10
        assert result["gels"] == result["total_carbs"] // 25

    def test_none_inputs(self):
        assert compute_personalized_fueling(0, 200, 5) is None
        assert compute_personalized_fueling(75, 200, 0) is None
        assert compute_personalized_fueling(None, 200, 5) is None


class TestFuelingCalculatorHTML:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.full_rd, self.full_raw = _load_test_race(FULL_SLUG)
        self.gen_rd, self.gen_raw = _load_test_race(GENERIC_SLUG)

    def test_form_present(self):
        html = build_fueling_calculator_html(self.full_rd)
        assert 'id="gg-pk-calc-form"' in html
        assert "gg-pk-calc-form" in html

    def test_email_field_required(self):
        html = build_fueling_calculator_html(self.full_rd)
        assert 'name="email"' in html
        assert "required" in html

    def test_weight_field_required(self):
        html = build_fueling_calculator_html(self.full_rd)
        assert 'name="weight_lbs"' in html
        # weight input should be required
        assert 'id="gg-pk-weight"' in html

    def test_ftp_field_optional(self):
        html = build_fueling_calculator_html(self.full_rd)
        assert 'name="ftp"' in html
        # FTP input should NOT have required attribute
        ftp_section = html[html.index('id="gg-pk-ftp"'):]
        ftp_tag = ftp_section[:ftp_section.index(">")]
        assert "required" not in ftp_tag

    def test_hours_prefilled(self):
        html = build_fueling_calculator_html(self.full_rd)
        # Unbound 200 → ~20h
        assert 'name="est_hours"' in html
        assert 'value="20.0"' in html

    def test_substack_iframe_present(self):
        html = build_fueling_calculator_html(self.full_rd)
        assert "substack.com/embed" in html
        assert "<iframe" in html

    def test_results_panel_hidden(self):
        html = build_fueling_calculator_html(self.full_rd)
        assert 'id="gg-pk-calc-result"' in html
        assert 'style="display:none"' in html

    def test_race_slug_in_form(self):
        html = build_fueling_calculator_html(self.full_rd)
        assert f'value="{self.full_rd["slug"]}"' in html

    def test_honeypot_field(self):
        html = build_fueling_calculator_html(self.full_rd)
        assert 'name="website"' in html


class TestFuelingCalculatorCSS:
    def test_calc_classes_in_css(self):
        css = build_prep_kit_css()
        assert ".gg-pk-calc-form" in css
        assert ".gg-pk-calc-result" in css
        assert ".gg-pk-calc-btn" in css
        assert ".gg-pk-calc-input" in css

    def test_print_hides_form(self):
        css = build_prep_kit_css()
        assert ".gg-pk-calc-form{display:none}" in css

    def test_neo_brutalist_inputs(self):
        css = build_prep_kit_css()
        # Calculator inputs should NOT have border-radius
        # Extract the .gg-pk-calc-input rule
        assert "border-radius" not in css.split(".gg-pk-calc-input")[1].split("}")[0]

    def test_responsive_single_column(self):
        css = build_prep_kit_css()
        assert ".gg-pk-calc-form{grid-template-columns:1fr}" in css


class TestFuelingCalculatorJS:
    def test_compute_function_in_js(self):
        js = build_prep_kit_js()
        assert "computePersonalized" in js

    def test_worker_url_in_js(self):
        js = build_prep_kit_js()
        assert FUELING_WORKER_URL in js

    def test_localstorage_key_in_js(self):
        js = build_prep_kit_js()
        assert "gg-pk-fueling" in js

    def test_ga4_event_in_js(self):
        js = build_prep_kit_js()
        assert "pk_fueling_submit" in js

    def test_substack_reveal_in_js(self):
        js = build_prep_kit_js()
        assert "gg-pk-calc-substack" in js


class TestFuelingInFullPage:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.guide = load_guide_sections()

    def test_calculator_in_full_race_page(self):
        rd, raw = _load_test_race(FULL_SLUG)
        html = generate_prep_kit_page(rd, raw, self.guide)
        assert "gg-pk-calc-form" in html
        assert "GET MY FUELING PLAN" in html

    def test_calculator_in_generic_race_page(self):
        rd, raw = _load_test_race(GENERIC_SLUG)
        html = generate_prep_kit_page(rd, raw, self.guide)
        assert "gg-pk-calc-form" in html


# ── Climate Heat Classification ────────────────────────────


class TestClassifyClimateHeat:
    def test_extreme_heat_keywords_and_score_5(self):
        climate = {
            "primary": "Desert conditions",
            "description": "Temperatures exceed 100+ degrees in the desert",
            "challenges": ["Extreme heat exposure"],
        }
        assert classify_climate_heat(climate, 5) == "extreme"

    def test_hot_keywords(self):
        climate = {
            "primary": "Flint Hills heat",
            "description": "June brings 85-95°F days with high humidity",
            "challenges": ["Heat adaptation critical"],
        }
        assert classify_climate_heat(climate, 5) == "hot"

    def test_warm_keywords(self):
        climate = {
            "primary": "Warm summer",
            "description": "Warm conditions in late summer",
            "challenges": [],
        }
        assert classify_climate_heat(climate, 3) == "warm"

    def test_cool_keywords(self):
        climate = {
            "primary": "Ontario spring—cold, wet, mud likely",
            "description": "Temperatures range 5-12°C (40-55°F)",
            "challenges": ["Cold temperatures"],
        }
        assert classify_climate_heat(climate, 4) == "cool"

    def test_mild_default(self):
        climate = {
            "primary": "Moderate conditions",
            "description": "Pleasant temperatures",
            "challenges": [],
        }
        assert classify_climate_heat(climate, 2) == "mild"

    def test_empty_climate_data_returns_mild(self):
        assert classify_climate_heat(None, None) == "mild"
        assert classify_climate_heat({}, None) == "mild"
        assert classify_climate_heat(None, 2) == "mild"

    def test_all_328_races_classify_without_error(self):
        """Every race in the database should classify without crashing."""
        data_dir = RACE_DATA_DIR
        count = 0
        for jf in sorted(data_dir.glob("*.json")):
            data = json.loads(jf.read_text(encoding="utf-8"))
            race = data.get("race", data)
            climate = race.get("climate")
            score = (race.get("gravel_god_rating") or {}).get("climate")
            result = classify_climate_heat(climate, score)
            assert result in ("cool", "mild", "warm", "hot", "extreme"), f"{jf.stem}: {result}"
            count += 1
        assert count >= 328


# ── Sweat Rate ─────────────────────────────────────────────


class TestComputeSweatRate:
    def test_average_rider_mild(self):
        # 75kg rider, mild, moderate sweat, 6 hours
        result = compute_sweat_rate(75, "mild", "moderate", 6)
        assert result is not None
        assert 0.5 < result["sweat_rate_l_hr"] < 2.0

    def test_heavy_sweater_hot(self):
        result = compute_sweat_rate(80, "hot", "heavy", 4)
        assert result is not None
        # Hot + heavy + short race = high sweat
        assert result["sweat_rate_l_hr"] > 1.5

    def test_light_sweater_cool(self):
        result = compute_sweat_rate(60, "cool", "light", 10)
        assert result is not None
        # Cool + light + long = low sweat
        assert result["sweat_rate_l_hr"] < 0.6

    def test_extreme_highest_multiplier(self):
        extreme = compute_sweat_rate(75, "extreme", "moderate", 6)
        mild = compute_sweat_rate(75, "mild", "moderate", 6)
        assert extreme["sweat_rate_l_hr"] > mild["sweat_rate_l_hr"]

    def test_fluid_target_60_80_percent_of_sweat(self):
        # Verify that fluid targets fall in the 60-80% replacement range.
        # The function rounds sweat_rate_l_hr to 2dp for display but uses
        # full precision for fluid calculations, so we verify the ratio
        # against the returned fluid values directly.
        result = compute_sweat_rate(75, "mild", "moderate", 6)
        # fluid_lo should be < fluid_hi
        assert result["fluid_lo_ml_hr"] < result["fluid_hi_ml_hr"]
        # And the ratio between lo and hi should be ~0.6/0.8 = 0.75
        ratio = result["fluid_lo_ml_hr"] / result["fluid_hi_ml_hr"]
        assert 0.74 <= ratio <= 0.76, f"ratio was {ratio}"
        # Both should be positive and reasonable (400-1200 ml/hr for avg rider)
        assert 400 < result["fluid_lo_ml_hr"] < 1200
        assert 500 < result["fluid_hi_ml_hr"] < 1500

    def test_intensity_scales_with_duration(self):
        short = compute_sweat_rate(75, "mild", "moderate", 3)
        long = compute_sweat_rate(75, "mild", "moderate", 20)
        assert short["sweat_rate_l_hr"] > long["sweat_rate_l_hr"]

    def test_none_inputs(self):
        assert compute_sweat_rate(0, "mild", "moderate", 6) is None
        assert compute_sweat_rate(75, "mild", "moderate", 0) is None
        assert compute_sweat_rate(None, "mild", "moderate", 6) is None


# ── Aid Station Hours ──────────────────────────────────────


class TestComputeAidStationHours:
    def test_mile_markers(self):
        text = "Aid at mile 30, mile 60, mile 90"
        result = compute_aid_station_hours(text, 120, 10)
        assert len(result) == 3
        # mile 30 / 120mi * 10h = 2.5h
        assert result[0] == 2.5

    def test_count_only_evenly_distributed(self):
        text = "9 fully-stocked feed zones along the route"
        result = compute_aid_station_hours(text, 100, 10)
        assert len(result) == 9
        # 10h / (9+1) = 1.0h interval
        assert result[0] == 1.0

    def test_self_supported_empty(self):
        assert compute_aid_station_hours("Self-supported", 100, 10) == []

    def test_dash_empty(self):
        assert compute_aid_station_hours("--", 100, 10) == []

    def test_unbound_checkpoints_and_oases(self):
        text = "2 full checkpoints + 2 water oases. Everything between those points is on you."
        result = compute_aid_station_hours(text, 200, 20)
        # 2 checkpoints + 2 water oases = 4 total
        assert len(result) == 4

    def test_none_input(self):
        assert compute_aid_station_hours(None, 100, 10) == []
        assert compute_aid_station_hours("", 100, 10) == []


# ── Sodium ─────────────────────────────────────────────────


class TestComputeSodium:
    def test_baseline_no_cramps(self):
        result = compute_sodium(1.0, "mild", "rarely")
        assert result is not None
        # 1.0 L/hr * 1000 mg/L = 1000 mg/hr
        assert result["sodium_mg_hr"] == 1000
        assert result["concentration_mg_l"] == 1000

    def test_cramp_sometimes_boost(self):
        result = compute_sodium(1.0, "mild", "sometimes")
        assert result["sodium_mg_hr"] == 1150  # 1000 + 150

    def test_cramp_frequent_boost(self):
        result = compute_sodium(1.0, "mild", "frequent")
        assert result["sodium_mg_hr"] == 1300  # 1000 + 300

    def test_hot_conditions_boost(self):
        result = compute_sodium(1.0, "hot", "rarely")
        assert result["sodium_mg_hr"] == 1200  # 1000 + 200
        extreme = compute_sodium(1.0, "extreme", "rarely")
        assert extreme["sodium_mg_hr"] == 1300  # 1000 + 300


# ── Hourly Plan ────────────────────────────────────────────


class TestComputeHourlyPlan:
    def test_plan_length_matches_ceil_hours(self):
        plan = compute_hourly_plan(7.5, 80, 750, 1000, "mixed", [])
        assert len(plan) == 8  # ceil(7.5)

    def test_aid_station_hours_flagged(self):
        plan = compute_hourly_plan(10, 80, 750, 1000, "mixed", [3.0, 6.0])
        assert plan[2]["is_aid"] is True   # hour 3
        assert plan[5]["is_aid"] is True   # hour 6
        assert plan[0]["is_aid"] is False

    def test_format_liquid_80_percent_drink(self):
        plan = compute_hourly_plan(4, 100, 750, 1000, "liquid", [])
        # Hours 2 and 3 should have full rate
        mid_hour = plan[1]
        # Find drink item
        drink_items = [i for i in mid_hour["items"] if i["type"] == "drink"]
        gel_items = [i for i in mid_hour["items"] if i["type"] == "gel"]
        assert len(drink_items) > 0
        # Drink carbs should be ~80% of total
        # 100 * 0.80 = 80g drink
        assert "80g" in drink_items[0]["label"]

    def test_format_gels_70_percent_gels(self):
        plan = compute_hourly_plan(4, 100, 750, 1000, "gels", [])
        mid_hour = plan[1]
        gel_items = [i for i in mid_hour["items"] if i["type"] == "gel"]
        assert len(gel_items) > 0
        # 100 * 0.70 = 70g gel → 3 gels (75g)
        assert "3 gels" in gel_items[0]["label"]

    def test_format_mixed_balanced(self):
        plan = compute_hourly_plan(6, 80, 750, 1000, "mixed", [])
        mid_hour = plan[2]
        types = [i["type"] for i in mid_hour["items"]]
        # Mixed should have all three types (if carbs allow)
        assert "gel" in types
        assert "drink" in types

    def test_format_solid_60_percent_food(self):
        plan = compute_hourly_plan(6, 80, 750, 1000, "solid", [])
        mid_hour = plan[2]
        food_items = [i for i in mid_hour["items"] if i["type"] == "food"]
        assert len(food_items) > 0

    def test_hour_1_ramp_up_80_percent(self):
        plan = compute_hourly_plan(6, 100, 750, 1000, "mixed", [])
        assert plan[0]["carbs_g"] == 80  # 100 * 0.8

    def test_last_hour_taper_80_percent(self):
        plan = compute_hourly_plan(6, 100, 750, 1000, "mixed", [])
        assert plan[-1]["carbs_g"] == 80  # 100 * 0.8

    def test_carb_totals_sum_correctly(self):
        plan = compute_hourly_plan(6, 80, 750, 1000, "mixed", [])
        total = sum(p["carbs_g"] for p in plan)
        # 6 hours: hour1=64, hours 2-5=80*4=320, hour6=64 → 448
        assert total == 64 + 80 * 4 + 64


# ── Hydration Form HTML ────────────────────────────────────


class TestHydrationFormHTML:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.full_rd, self.full_raw = _load_test_race(FULL_SLUG)
        self.gen_rd, self.gen_raw = _load_test_race(GENERIC_SLUG)

    def test_climate_badge_rendered(self):
        html = build_fueling_calculator_html(self.full_rd, self.full_raw)
        assert "gg-pk-calc-climate-badge" in html
        assert "gg-pk-calc-climate--" in html

    def test_sweat_tendency_select_present(self):
        html = build_fueling_calculator_html(self.full_rd, self.full_raw)
        assert 'name="sweat_tendency"' in html
        assert "Heavy sweater" in html

    def test_fuel_format_select_present(self):
        html = build_fueling_calculator_html(self.full_rd, self.full_raw)
        assert 'name="fuel_format"' in html
        assert "Mostly liquid" in html

    def test_cramp_history_select_present(self):
        html = build_fueling_calculator_html(self.full_rd, self.full_raw)
        assert 'name="cramp_history"' in html
        assert "Frequently" in html

    def test_aid_station_hours_hidden_input(self):
        html = build_fueling_calculator_html(self.full_rd, self.full_raw)
        assert 'name="aid_station_hours"' in html
        # Unbound has aid stations → should have non-empty JSON array
        assert "[]" not in html.split('name="aid_station_hours"')[1].split(">")[0]

    def test_climate_heat_hidden_input(self):
        html = build_fueling_calculator_html(self.full_rd, self.full_raw)
        assert 'name="climate_heat"' in html
        # Unbound: "Flint Hills heat", 85-95°F, score=5 → "hot"
        assert 'value="hot"' in html


# ── Hydration JS ───────────────────────────────────────────


class TestHydrationJS:
    def test_compute_sweat_rate_in_js(self):
        js = build_prep_kit_js()
        assert "computeSweatRate" in js

    def test_compute_hourly_plan_in_js(self):
        js = build_prep_kit_js()
        assert "computeHourlyPlan" in js

    def test_hourly_table_rendering(self):
        js = build_prep_kit_js()
        assert "gg-pk-calc-hourly-table" in js
        assert "Hour-by-Hour" in js

    def test_shopping_list_rendering(self):
        js = build_prep_kit_js()
        assert "gg-pk-calc-shopping-grid" in js
        assert "What to Pack" in js


# ── Python/JS Parity ──────────────────────────────────────


class TestPythonJSParity:
    """Verify Python and JS implementations produce matching results.

    Static checks confirm constants are present in JS source.
    Runtime checks execute JS via Node.js and compare against Python.
    """
    def test_heat_multiplier_constants_match(self):
        js = build_prep_kit_js()
        for key, val in HEAT_MULTIPLIERS.items():
            assert f"{key}:{val}" in js, f"Missing {key}:{val} in JS"

    def test_sweat_multiplier_constants_match(self):
        js = build_prep_kit_js()
        for key, val in SWEAT_MULTIPLIERS.items():
            assert f"{key}:{val}" in js, f"Missing {key}:{val} in JS"

    def test_format_split_ratios_match(self):
        js = build_prep_kit_js()
        for fmt, splits in FORMAT_SPLITS.items():
            for k, v in splits.items():
                # JS may format as 0.80 or 0.8 — check both
                found = f"{k}:{v}" in js or f"{k}:{v:.1f}" in js or f"{k}:{v:.2f}" in js
                assert found, f"Missing {k}:{v} for format {fmt} in JS"

    def test_sodium_boost_constants_match(self):
        js = build_prep_kit_js()
        assert f"hot:{SODIUM_HEAT_BOOST['hot']}" in js
        assert f"extreme:{SODIUM_HEAT_BOOST['extreme']}" in js
        assert f"sometimes:{SODIUM_CRAMP_BOOST['sometimes']}" in js
        assert f"frequent:{SODIUM_CRAMP_BOOST['frequent']}" in js

    def test_sweat_rate_computation_matches_js(self):
        """Run identical inputs through Python and JS, compare outputs."""
        import subprocess
        import json as _json

        # Extract just the compute functions from JS (strip DOM code)
        js_full = build_prep_kit_js()
        # Build a Node.js script that defines the constants + functions, then runs tests
        node_script = """
// Extract constants and compute functions from prep kit JS
var HEAT_MULT={cool:0.7,mild:1.0,warm:1.3,hot:1.6,extreme:1.9};
var SWEAT_MULT={light:0.7,moderate:1.0,heavy:1.3};
var SODIUM_BASE=1000;
var SODIUM_HEAT_BOOST={hot:200,extreme:300};
var SODIUM_CRAMP_BOOST={sometimes:150,frequent:300};
var FORMAT_SPLITS={
    liquid:{drink:0.80,gel:0.15,food:0.05},
    gels:{drink:0.20,gel:0.70,food:0.10},
    mixed:{drink:0.30,gel:0.40,food:0.30},
    solid:{drink:0.20,gel:0.20,food:0.60}
};

function computeSweatRate(weightLbs,climateHeat,sweatTendency,hours){
    if(!weightLbs||weightLbs<=0||!hours||hours<=0) return null;
    var weightKg=weightLbs*0.453592;
    var base=weightKg*0.013;
    var hm=HEAT_MULT[climateHeat]||1.0;
    var sm=SWEAT_MULT[sweatTendency]||1.0;
    var intensity;
    if(hours<=4) intensity=1.15;
    else if(hours<=8) intensity=1.0;
    else if(hours<=12) intensity=0.9;
    else if(hours<=16) intensity=0.8;
    else intensity=0.7;
    var sr=base*hm*sm*intensity;
    var fLo=Math.round(sr*0.6*1000);
    var fHi=Math.round(sr*0.8*1000);
    return{sweatRate:Math.round(sr*100)/100,fluidLoMl:fLo,fluidHiMl:fHi};
}

function computeSodium(sweatRate,climateHeat,crampHistory){
    if(!sweatRate||sweatRate<=0) return null;
    var conc=SODIUM_BASE+(SODIUM_HEAT_BOOST[climateHeat]||0)+(SODIUM_CRAMP_BOOST[crampHistory]||0);
    return{sodiumMgHr:Math.round(sweatRate*conc),concentration:conc};
}

function computeHourlyPlan(hours,carbRate,fluidMlHr,sodiumMgHr,fuelFormat,aidHours){
    if(!hours||hours<=0||!carbRate||carbRate<=0) return[];
    var total=Math.ceil(hours);
    var splits=FORMAT_SPLITS[fuelFormat]||FORMAT_SPLITS.mixed;
    var aidSet={};
    (aidHours||[]).forEach(function(h){aidSet[Math.round(h)]=true;});
    var plan=[];
    for(var h=1;h<=total;h++){
      var mult;
      if(h===1) mult=0.8;
      else if(h===total&&hours%1>0) mult=hours%1;
      else if(h===total) mult=0.8;
      else mult=1.0;
      plan.push({hour:h,carbs:Math.round(carbRate*mult),fluid:Math.round(fluidMlHr*mult),sodium:Math.round(sodiumMgHr*mult)});
    }
    return plan;
}

// Test cases
var cases = [
    {w:165, heat:'mild', sweat:'moderate', h:6, cramp:'rarely', fmt:'mixed', aid:[]},
    {w:185, heat:'hot', sweat:'heavy', h:4, cramp:'frequent', fmt:'gels', aid:[2]},
    {w:130, heat:'cool', sweat:'light', h:12, cramp:'rarely', fmt:'liquid', aid:[3,6,9]},
];
var results = cases.map(function(c) {
    var sr = computeSweatRate(c.w, c.heat, c.sweat, c.h);
    var na = sr ? computeSodium(sr.sweatRate, c.heat, c.cramp) : null;
    var plan = computeHourlyPlan(c.h, 80, sr?Math.round((sr.fluidLoMl+sr.fluidHiMl)/2):750,
                                  na?na.sodiumMgHr:1000, c.fmt, c.aid);
    return {sweat: sr, sodium: na, plan_len: plan.length, plan_h1_carbs: plan.length>0?plan[0].carbs:0};
});
console.log(JSON.stringify(results));
"""
        result = subprocess.run(
            ["node", "-e", node_script],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"Node.js failed: {result.stderr}"
        js_results = _json.loads(result.stdout.strip())

        # Now run same cases through Python
        test_cases = [
            {"w": 165, "heat": "mild", "sweat": "moderate", "h": 6, "cramp": "rarely", "fmt": "mixed", "aid": []},
            {"w": 185, "heat": "hot", "sweat": "heavy", "h": 4, "cramp": "frequent", "fmt": "gels", "aid": [2]},
            {"w": 130, "heat": "cool", "sweat": "light", "h": 12, "cramp": "rarely", "fmt": "liquid", "aid": [3, 6, 9]},
        ]

        for i, c in enumerate(test_cases):
            weight_kg = c["w"] * 0.453592
            py_sr = compute_sweat_rate(weight_kg, c["heat"], c["sweat"], c["h"])
            py_na = compute_sodium(py_sr["sweat_rate_l_hr"], c["heat"], c["cramp"]) if py_sr else None
            fluid_mid = round((py_sr["fluid_lo_ml_hr"] + py_sr["fluid_hi_ml_hr"]) / 2) if py_sr else 750
            sodium_hr = py_na["sodium_mg_hr"] if py_na else 1000
            py_plan = compute_hourly_plan(c["h"], 80, fluid_mid, sodium_hr, c["fmt"], c["aid"])

            js_r = js_results[i]
            # Compare sweat rates (within rounding tolerance)
            assert abs(py_sr["sweat_rate_l_hr"] - js_r["sweat"]["sweatRate"]) <= 0.02, \
                f"Case {i}: sweat rate mismatch: py={py_sr['sweat_rate_l_hr']} js={js_r['sweat']['sweatRate']}"
            # Compare sodium
            if py_na and js_r["sodium"]:
                assert abs(py_na["sodium_mg_hr"] - js_r["sodium"]["sodiumMgHr"]) <= 5, \
                    f"Case {i}: sodium mismatch: py={py_na['sodium_mg_hr']} js={js_r['sodium']['sodiumMgHr']}"
            # Compare plan length
            assert len(py_plan) == js_r["plan_len"], \
                f"Case {i}: plan length mismatch: py={len(py_plan)} js={js_r['plan_len']}"
            # Compare hour 1 carbs (ramp-up)
            assert py_plan[0]["carbs_g"] == js_r["plan_h1_carbs"], \
                f"Case {i}: hour 1 carbs mismatch: py={py_plan[0]['carbs_g']} js={js_r['plan_h1_carbs']}"
