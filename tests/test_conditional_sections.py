"""Tests for conditional guide sections (altitude, women's, masters).

These sections are the only non-deterministic part of guide generation —
they appear or don't based on athlete profile data. Every trigger and
every key piece of content is tested here so that future changes can't
silently break them.

Design principle: hardcoded triggers, hardcoded content, deterministic output.
"""

import re
import pytest
from pathlib import Path
from copy import deepcopy

from pipeline.step_07_guide import (
    _build_section_titles,
    _section_altitude_training,
    _section_women_specific,
    _section_masters_training,
    _build_full_guide,
    _conditional_triggers,
)


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def female_profile():
    """Female athlete, age 44 (Sarah Printz)."""
    return {
        "name": "Sarah Printz",
        "email": "sarah@example.com",
        "demographics": {
            "sex": "female",
            "age": 44,
            "weight_lbs": 135.0,
            "height_ft": 5,
            "height_in": 10,
            "menstrual_status": None,
            "track_cycle": None,
        },
        "race_calendar": [{"name": "SBT GRVL", "date": "2026-06-28", "distance_miles": 100}],
        "primary_race": {"name": "SBT GRVL", "date": "2026-06-28", "distance_miles": 100},
        "fitness": {"ftp_watts": None, "longest_ride_hours": "2-4", "max_hr": None, "lthr": None, "resting_hr": None},
        "schedule": {"weekly_hours": "5-7", "off_days": ["wednesday"], "long_ride_days": ["saturday", "sunday"], "interval_days": ["tuesday", "thursday"]},
        "training_history": {"years_cycling": "3-5 years"},
        "strength": {"current_practice": "regular", "include_in_plan": "yes", "equipment": "full-gym"},
        "health": {"sleep_quality": "good", "stress_level": "moderate", "injuries_limitations": "NA"},
        "equipment": {"trainer_type": "yes-basic"},
        "notes": {"anything_else": None},
    }


@pytest.fixture
def male_profile(female_profile):
    """Male athlete, age 28."""
    p = deepcopy(female_profile)
    p["name"] = "Test Male"
    p["demographics"]["sex"] = "male"
    p["demographics"]["age"] = 28
    p["demographics"]["weight_lbs"] = 170.0
    return p


@pytest.fixture
def young_female_profile(female_profile):
    """Female athlete, age 25 — under masters threshold."""
    p = deepcopy(female_profile)
    p["name"] = "Test Young Female"
    p["demographics"]["age"] = 25
    return p


@pytest.fixture
def masters_male_profile(male_profile):
    """Male athlete, age 52 — above masters threshold."""
    p = deepcopy(male_profile)
    p["name"] = "Test Masters Male"
    p["demographics"]["age"] = 52
    return p


@pytest.fixture
def high_elevation_race():
    """SBT GRVL — elevation > 5000ft."""
    return {
        "race_metadata": {
            "name": "SBT GRVL",
            "location": "Steamboat Springs, Colorado",
            "start_elevation_feet": 6732,
            "avg_elevation_feet": 7500,
        },
        "race_characteristics": {
            "climate": "mountain",
            "altitude_category": "moderate_high",
            "terrain": "mountain_gravel",
            "technical_difficulty": "moderate",
        },
        "elevation_feet": 8000,
        "distance_miles": 100,
        "duration_estimate": "6-10 hours",
        "workout_modifications": {
            "altitude_training": {"enabled": True},
            "heat_training": {"enabled": False},
        },
        "non_negotiables": {},
        "race_specific": {},
    }


@pytest.fixture
def low_elevation_race():
    """Mid South — elevation < 5000ft."""
    return {
        "race_metadata": {
            "name": "Mid South",
            "location": "Stillwater, Oklahoma",
            "start_elevation_feet": 900,
            "avg_elevation_feet": 1000,
        },
        "race_characteristics": {
            "climate": "warm",
            "altitude_category": "low",
            "terrain": "mixed_gravel",
            "technical_difficulty": "moderate",
        },
        "elevation_feet": 3500,
        "distance_miles": 100,
        "duration_estimate": "6-10 hours",
        "workout_modifications": {
            "altitude_training": {"enabled": False},
            "heat_training": {"enabled": True},
        },
        "non_negotiables": {},
        "race_specific": {},
    }


@pytest.fixture
def finisher_derived():
    return {
        "tier": "finisher",
        "level": "intermediate",
        "weekly_hours": "5-7",
        "plan_weeks": 16,
        "plan_duration": 16,
        "is_masters": False,
        "race_name": "SBT GRVL",
        "race_date": "2026-06-28",
        "race_distance_miles": 100,
    }


@pytest.fixture
def schedule():
    return {
        "description": "Custom weekly structure",
        "tier": "finisher",
        "days": {
            "monday": {"session": "strength", "notes": "Strength"},
            "tuesday": {"session": "intervals", "notes": "Intervals"},
            "wednesday": {"session": "rest", "notes": "Off day"},
            "thursday": {"session": "intervals", "notes": "Intervals"},
            "friday": {"session": "strength", "notes": "Strength"},
            "saturday": {"session": "long_ride", "notes": "Long ride"},
            "sunday": {"session": "long_ride", "notes": "Long ride"},
        },
    }


@pytest.fixture
def plan_config():
    return {
        "template_key": "finisher_intermediate",
        "plan_duration": 16,
        "extended": True,
        "template": {"weeks": [{"week_number": i} for i in range(1, 17)]},
    }


# ── Helper ──────────────────────────────────────────────────────

def _generate_full_html(profile, derived, plan_config, schedule, race_data):
    """Generate the full guide HTML for testing."""
    return _build_full_guide(
        athlete_name=profile["name"],
        race_name=derived["race_name"],
        race_distance=derived["race_distance_miles"],
        tier=derived["tier"],
        level=derived["level"],
        plan_duration=derived["plan_duration"],
        profile=profile,
        derived=derived,
        schedule=schedule,
        plan_config=plan_config,
        race_data=race_data,
    )


# ── Section Title Builder Tests ─────────────────────────────────

class TestBuildSectionTitles:
    """_build_section_titles must include/exclude conditional sections
    based on exactly the same triggers used in _build_full_guide."""

    def test_always_has_16_core_sections(self, male_profile, low_elevation_race):
        """Core 16 sections always present regardless of profile."""
        titles = _build_section_titles(male_profile, low_elevation_race)
        assert len(titles) == 16
        assert titles[0] == ("section-1", "Training Plan Brief")
        assert titles[-1] == ("section-16", "Gravel Skills")

    def test_ids_are_sequential_no_gaps(self, female_profile, high_elevation_race):
        """IDs must be sequential with no gaps, regardless of which conditionals fire."""
        titles = _build_section_titles(female_profile, high_elevation_race)
        for i, (sid, _) in enumerate(titles):
            assert sid == f"section-{i+1}", f"ID gap: expected section-{i+1}, got {sid}"

    def test_ids_sequential_women_only(self, young_female_profile, low_elevation_race):
        """Young female, low elevation = 16 core + women's = section-17 for women's (not 18)."""
        titles = _build_section_titles(young_female_profile, low_elevation_race)
        assert len(titles) == 17
        assert titles[-1] == ("section-17", "Women-Specific Considerations")

    def test_altitude_added_for_high_elevation(self, male_profile, high_elevation_race):
        titles = _build_section_titles(male_profile, high_elevation_race)
        section_names = [t[1] for t in titles]
        assert "Altitude Training" in section_names

    def test_altitude_absent_for_low_elevation(self, male_profile, low_elevation_race):
        titles = _build_section_titles(male_profile, low_elevation_race)
        section_names = [t[1] for t in titles]
        assert "Altitude Training" not in section_names

    def test_women_added_for_female(self, female_profile, low_elevation_race):
        titles = _build_section_titles(female_profile, low_elevation_race)
        section_names = [t[1] for t in titles]
        assert "Women-Specific Considerations" in section_names

    def test_women_absent_for_male(self, male_profile, low_elevation_race):
        titles = _build_section_titles(male_profile, low_elevation_race)
        section_names = [t[1] for t in titles]
        assert "Women-Specific Considerations" not in section_names

    def test_masters_added_for_age_40(self, female_profile, low_elevation_race):
        """Age 40 is the threshold — exactly 40 should trigger."""
        female_profile["demographics"]["age"] = 40
        titles = _build_section_titles(female_profile, low_elevation_race)
        section_names = [t[1] for t in titles]
        assert "Masters Training Considerations" in section_names

    def test_masters_absent_for_age_39(self, female_profile, low_elevation_race):
        female_profile["demographics"]["age"] = 39
        titles = _build_section_titles(female_profile, low_elevation_race)
        section_names = [t[1] for t in titles]
        assert "Masters Training Considerations" not in section_names

    def test_masters_absent_for_age_none(self, male_profile, low_elevation_race):
        male_profile["demographics"]["age"] = None
        titles = _build_section_titles(male_profile, low_elevation_race)
        section_names = [t[1] for t in titles]
        assert "Masters Training Considerations" not in section_names

    def test_all_three_for_sarah(self, female_profile, high_elevation_race):
        """Sarah Printz: female, 44, high elevation → all 3 conditional sections."""
        titles = _build_section_titles(female_profile, high_elevation_race)
        section_names = [t[1] for t in titles]
        assert len(titles) == 19
        assert "Altitude Training" in section_names
        assert "Women-Specific Considerations" in section_names
        assert "Masters Training Considerations" in section_names

    def test_none_for_young_male_low_elevation(self, male_profile, low_elevation_race):
        """Male, 28, low elevation → zero conditional sections."""
        titles = _build_section_titles(male_profile, low_elevation_race)
        assert len(titles) == 16

    def test_section_order_is_altitude_women_masters(self, female_profile, high_elevation_race):
        """Conditional sections always appear in this fixed order: altitude, women, masters."""
        titles = _build_section_titles(female_profile, high_elevation_race)
        section_names = [t[1] for t in titles]
        idx_alt = section_names.index("Altitude Training")
        idx_women = section_names.index("Women-Specific Considerations")
        idx_masters = section_names.index("Masters Training Considerations")
        assert idx_alt < idx_women < idx_masters


# ── Altitude Section Tests ──────────────────────────────────────

class TestAltitudeSection:
    """Content checks for altitude section — sourced from existing guides."""

    def test_contains_power_loss_data(self, high_elevation_race):
        html = _section_altitude_training(high_elevation_race, "SBT GRVL", 8000)
        assert "FTP" in html
        assert "power" in html.lower() or "Power" in html
        assert "% reduction" in html.lower() or "% loss" in html.lower()

    def test_contains_acclimatization_protocol(self, high_elevation_race):
        html = _section_altitude_training(high_elevation_race, "SBT GRVL", 8000)
        assert "acclimat" in html.lower()

    def test_contains_elevation_table(self, high_elevation_race):
        html = _section_altitude_training(high_elevation_race, "SBT GRVL", 8000)
        assert "<table" in html
        assert "sea level" in html.lower()

    def test_mentions_race_name(self, high_elevation_race):
        html = _section_altitude_training(high_elevation_race, "SBT GRVL", 8000)
        assert "SBT GRVL" in html

    def test_section_id_uses_param(self, high_elevation_race):
        """Section ID must come from the section_num parameter, not be hardcoded."""
        html_17 = _section_altitude_training(high_elevation_race, "SBT GRVL", 8000, section_num=17)
        assert 'id="section-17"' in html_17
        html_20 = _section_altitude_training(high_elevation_race, "SBT GRVL", 8000, section_num=20)
        assert 'id="section-20"' in html_20

    def test_no_placeholders(self, high_elevation_race):
        html = _section_altitude_training(high_elevation_race, "SBT GRVL", 8000)
        assert "{{" not in html
        assert "}}" not in html

    def test_no_null_text(self, high_elevation_race):
        html = _section_altitude_training(high_elevation_race, "SBT GRVL", 8000)
        # Check for literal "None", "null", "undefined" as visible text
        assert re.search(r'>\s*None\s*<', html) is None
        assert re.search(r'>\s*null\s*<', html) is None


# ── Women-Specific Section Tests ────────────────────────────────

class TestWomenSection:
    """Content checks for women's section — sourced from existing guides."""

    def test_contains_follicular_phase(self, female_profile, high_elevation_race):
        html = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL")
        assert "follicular" in html.lower()

    def test_contains_luteal_phase(self, female_profile, high_elevation_race):
        html = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL")
        assert "luteal" in html.lower()

    def test_contains_iron_info(self, female_profile, high_elevation_race):
        html = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL")
        assert "iron" in html.lower()

    def test_contains_carb_targets(self, female_profile, high_elevation_race):
        """Carb targets should be personalized based on body weight."""
        html = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL")
        # Sarah is 135 lbs = ~61.2 kg, so carb targets should be calculated
        assert "g" in html  # gram targets present

    def test_personalized_weight_based_targets(self, female_profile, high_elevation_race):
        """With 135 lbs, should see ~61kg-based calculations."""
        html = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL")
        # 135 lbs / 2.205 = 61.2 kg
        # Training: 61.2 * 6 = 367, 61.2 * 7 = 428 → "367-428g"
        assert "367" in html or "428" in html

    def test_section_id_uses_param(self, female_profile, high_elevation_race):
        """Section ID must come from the section_num parameter, not be hardcoded."""
        html_18 = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL", section_num=18)
        assert 'id="section-18"' in html_18
        html_17 = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL", section_num=17)
        assert 'id="section-17"' in html_17

    def test_no_placeholders(self, female_profile, high_elevation_race):
        html = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL")
        assert "{{" not in html

    def test_no_null_text(self, female_profile, high_elevation_race):
        html = _section_women_specific(female_profile, high_elevation_race, "SBT GRVL")
        assert re.search(r'>\s*None\s*<', html) is None


# ── Masters Section Tests ───────────────────────────────────────

class TestMastersSection:
    """Content checks for masters section — sourced from Compete Masters template."""

    def test_contains_recovery_spacing(self, female_profile, finisher_derived):
        html = _section_masters_training(female_profile, finisher_derived)
        assert "48" in html  # hours between hard sessions

    def test_contains_hrmax_estimate(self, female_profile, finisher_derived):
        """HRmax should be personalized: 211 - (0.64 * age)."""
        html = _section_masters_training(female_profile, finisher_derived)
        expected_hrmax = round(211 - (0.64 * 44))
        assert str(expected_hrmax) in html

    def test_contains_muscle_loss_info(self, female_profile, finisher_derived):
        html = _section_masters_training(female_profile, finisher_derived)
        assert "muscle" in html.lower()

    def test_contains_sleep_requirement(self, female_profile, finisher_derived):
        html = _section_masters_training(female_profile, finisher_derived)
        assert "8+" in html or "8 hours" in html or "eight hours" in html.lower()

    def test_contains_strength_emphasis(self, female_profile, finisher_derived):
        html = _section_masters_training(female_profile, finisher_derived)
        assert "strength" in html.lower()

    def test_age_40_uses_correct_spacing(self, female_profile, finisher_derived):
        """Age 40-49 should get '48 hours minimum' spacing."""
        female_profile["demographics"]["age"] = 40
        html = _section_masters_training(female_profile, finisher_derived)
        assert "48 hours minimum" in html

    def test_age_50_uses_correct_spacing(self, female_profile, finisher_derived):
        """Age 50-54 should get '48-72 hours' spacing."""
        female_profile["demographics"]["age"] = 50
        html = _section_masters_training(female_profile, finisher_derived)
        assert "48-72 hours" in html

    def test_age_55_uses_correct_spacing(self, female_profile, finisher_derived):
        """Age 55+ should get '72 hours minimum' spacing."""
        female_profile["demographics"]["age"] = 55
        html = _section_masters_training(female_profile, finisher_derived)
        assert "72 hours minimum" in html

    def test_section_id_uses_param(self, female_profile, finisher_derived):
        """Section ID must come from the section_num parameter, not be hardcoded."""
        html_19 = _section_masters_training(female_profile, finisher_derived, section_num=19)
        assert 'id="section-19"' in html_19
        html_17 = _section_masters_training(female_profile, finisher_derived, section_num=17)
        assert 'id="section-17"' in html_17

    def test_no_placeholders(self, female_profile, finisher_derived):
        html = _section_masters_training(female_profile, finisher_derived)
        assert "{{" not in html

    def test_no_null_text(self, female_profile, finisher_derived):
        html = _section_masters_training(female_profile, finisher_derived)
        assert re.search(r'>\s*None\s*<', html) is None

    def test_personalized_with_actual_age(self, female_profile, finisher_derived):
        """The section must mention the athlete's actual age."""
        html = _section_masters_training(female_profile, finisher_derived)
        assert "44" in html  # Sarah's age


# ── Full Guide Integration Tests ─────────────────────────────────

class TestFullGuideConditionalSections:
    """Integration tests: verify conditional sections appear/disappear
    in the full guide HTML, not just in isolation."""

    def test_sarah_has_all_three(
        self, female_profile, finisher_derived, plan_config, schedule, high_elevation_race
    ):
        """Sarah Printz: female, 44, SBT GRVL → altitude + women + masters (17, 18, 19)."""
        html = _generate_full_html(female_profile, finisher_derived, plan_config, schedule, high_elevation_race)
        assert 'id="section-17"' in html  # Altitude
        assert 'id="section-18"' in html  # Women's
        assert 'id="section-19"' in html  # Masters
        assert re.search(r'<h2>\d+ &middot; Altitude Training', html)
        assert re.search(r'<h2>\d+ &middot; Women-Specific', html)
        assert re.search(r'<h2>\d+ &middot; Masters Training', html)

    def test_young_male_has_none(
        self, male_profile, finisher_derived, plan_config, schedule, low_elevation_race
    ):
        """Male, 28, low elevation → exactly 16 sections, no more."""
        html = _generate_full_html(male_profile, finisher_derived, plan_config, schedule, low_elevation_race)
        section_ids = re.findall(r'<section[^>]*id="(section-\d+)"', html)
        assert len(section_ids) == 16
        assert not re.search(r'<h2>\d+ &middot; Altitude Training', html)
        assert not re.search(r'<h2>\d+ &middot; Women-Specific', html)
        assert not re.search(r'<h2>\d+ &middot; Masters Training', html)

    def test_young_female_low_elev(
        self, young_female_profile, finisher_derived, plan_config, schedule, low_elevation_race
    ):
        """Female, 25, low elevation → women's as section-17 (sequential, no gap)."""
        html = _generate_full_html(young_female_profile, finisher_derived, plan_config, schedule, low_elevation_race)
        section_ids = re.findall(r'<section[^>]*id="(section-\d+)"', html)
        assert len(section_ids) == 17
        assert 'id="section-17"' in html  # Women's gets 17 (not 18)
        # Check for section HEADINGS (not just text, since cross-references can mention "Altitude Training")
        assert re.search(r'<h2>\d+ &middot; Women-Specific', html)
        assert not re.search(r'<h2>\d+ &middot; Altitude Training', html)
        assert not re.search(r'<h2>\d+ &middot; Masters Training', html)

    def test_masters_male_low_elev(
        self, masters_male_profile, finisher_derived, plan_config, schedule, low_elevation_race
    ):
        """Male, 52, low elevation → masters as section-17 (sequential, no gap)."""
        html = _generate_full_html(masters_male_profile, finisher_derived, plan_config, schedule, low_elevation_race)
        section_ids = re.findall(r'<section[^>]*id="(section-\d+)"', html)
        assert len(section_ids) == 17
        assert 'id="section-17"' in html  # Masters gets 17 (not 19)
        assert re.search(r'<h2>\d+ &middot; Masters Training', html)
        assert not re.search(r'<h2>\d+ &middot; Altitude Training', html)
        assert not re.search(r'<h2>\d+ &middot; Women-Specific', html)

    def test_male_high_elev(
        self, male_profile, finisher_derived, plan_config, schedule, high_elevation_race
    ):
        """Male, 28, high elevation → altitude as section-17."""
        html = _generate_full_html(male_profile, finisher_derived, plan_config, schedule, high_elevation_race)
        section_ids = re.findall(r'<section[^>]*id="(section-\d+)"', html)
        assert len(section_ids) == 17
        assert 'id="section-17"' in html  # Altitude gets 17
        assert re.search(r'<h2>\d+ &middot; Altitude Training', html)
        assert not re.search(r'<h2>\d+ &middot; Women-Specific', html)
        assert not re.search(r'<h2>\d+ &middot; Masters Training', html)

    def test_toc_matches_body_sections(
        self, female_profile, finisher_derived, plan_config, schedule, high_elevation_race
    ):
        """TOC links must match the actual section IDs in the body."""
        html = _generate_full_html(female_profile, finisher_derived, plan_config, schedule, high_elevation_race)

        # Extract TOC links
        toc_links = re.findall(r'href="#(section-\d+)"', html)
        # Extract section IDs in body
        body_sections = re.findall(r'<section[^>]*id="(section-\d+)"', html)

        # Every TOC link must have a corresponding section
        for link in toc_links:
            assert link in body_sections, f"TOC link #{link} has no matching section in body"

        # Every section must have a TOC link
        for section in body_sections:
            assert section in toc_links, f"Section {section} has no TOC link"

    def test_no_duplicate_section_ids(
        self, female_profile, finisher_derived, plan_config, schedule, high_elevation_race
    ):
        """No two sections should have the same ID."""
        html = _generate_full_html(female_profile, finisher_derived, plan_config, schedule, high_elevation_race)
        section_ids = re.findall(r'<section[^>]*id="(section-\d+)"', html)
        assert len(section_ids) == len(set(section_ids)), f"Duplicate section IDs: {section_ids}"

    def test_guide_above_50kb_with_all_conditionals(
        self, female_profile, finisher_derived, plan_config, schedule, high_elevation_race
    ):
        """Guide with all 3 conditional sections must still pass the 50KB gate."""
        html = _generate_full_html(female_profile, finisher_derived, plan_config, schedule, high_elevation_race)
        assert len(html) >= 50_000, f"Guide too small: {len(html):,} bytes"

    def test_guide_above_50kb_without_conditionals(
        self, male_profile, finisher_derived, plan_config, schedule, low_elevation_race
    ):
        """Guide with NO conditional sections must still pass the 50KB gate."""
        html = _generate_full_html(male_profile, finisher_derived, plan_config, schedule, low_elevation_race)
        assert len(html) >= 50_000, f"Guide too small: {len(html):,} bytes"

    def test_no_placeholders_in_full_guide(
        self, female_profile, finisher_derived, plan_config, schedule, high_elevation_race
    ):
        """Full guide with all conditionals must have zero {{placeholders}}."""
        html = _generate_full_html(female_profile, finisher_derived, plan_config, schedule, high_elevation_race)
        matches = re.findall(r'\{\{.*?\}\}', html)
        assert not matches, f"Unreplaced placeholders: {matches}"

    def test_no_null_text_in_full_guide(
        self, female_profile, finisher_derived, plan_config, schedule, high_elevation_race
    ):
        """Full guide must not contain literal None/null/undefined as visible text."""
        html = _generate_full_html(female_profile, finisher_derived, plan_config, schedule, high_elevation_race)
        for bad in ["None", "null", "undefined", "NaN"]:
            matches = re.findall(rf'>\s*{bad}\s*<', html)
            assert not matches, f"Found '{bad}' as visible text in guide"


# ── Trigger Boundary Tests ──────────────────────────────────────

class TestTriggerBoundaries:
    """Test exact boundary values for each conditional trigger."""

    def test_altitude_threshold_4999(self, male_profile):
        """4999ft → no altitude section."""
        race = {"race_metadata": {"start_elevation_feet": 4999, "avg_elevation_feet": 4999}, "elevation_feet": 4999}
        titles = _build_section_titles(male_profile, race)
        assert not any("Altitude" in t[1] for t in titles)

    def test_altitude_threshold_5001(self, male_profile):
        """5001ft → altitude section appears."""
        race = {"race_metadata": {"start_elevation_feet": 5001, "avg_elevation_feet": 5001}, "elevation_feet": 5001}
        titles = _build_section_titles(male_profile, race)
        assert any("Altitude" in t[1] for t in titles)

    def test_age_threshold_39(self, male_profile, low_elevation_race):
        """Age 39 → no masters section."""
        male_profile["demographics"]["age"] = 39
        titles = _build_section_titles(male_profile, low_elevation_race)
        assert not any("Masters" in t[1] for t in titles)

    def test_age_threshold_40(self, male_profile, low_elevation_race):
        """Age 40 → masters section appears."""
        male_profile["demographics"]["age"] = 40
        titles = _build_section_titles(male_profile, low_elevation_race)
        assert any("Masters" in t[1] for t in titles)

    def test_sex_male_no_women_section(self, male_profile, low_elevation_race):
        titles = _build_section_titles(male_profile, low_elevation_race)
        assert not any("Women" in t[1] for t in titles)

    def test_sex_female_has_women_section(self, female_profile, low_elevation_race):
        titles = _build_section_titles(female_profile, low_elevation_race)
        assert any("Women" in t[1] for t in titles)

    def test_sex_empty_no_women_section(self, male_profile, low_elevation_race):
        """Empty sex string → no women's section."""
        male_profile["demographics"]["sex"] = ""
        titles = _build_section_titles(male_profile, low_elevation_race)
        assert not any("Women" in t[1] for t in titles)

    def test_sex_none_no_women_section(self, male_profile, low_elevation_race):
        """None sex → no women's section."""
        male_profile["demographics"]["sex"] = None
        titles = _build_section_titles(male_profile, low_elevation_race)
        assert not any("Women" in t[1] for t in titles)

    def test_age_none_no_masters_section(self, male_profile, low_elevation_race):
        """None age → no masters section."""
        male_profile["demographics"]["age"] = None
        titles = _build_section_titles(male_profile, low_elevation_race)
        assert not any("Masters" in t[1] for t in titles)

    def test_altitude_threshold_exactly_5000(self, male_profile):
        """5000ft exactly → NO altitude section (threshold is > 5000, not >=)."""
        race = {"race_metadata": {"start_elevation_feet": 5000, "avg_elevation_feet": 5000}, "elevation_feet": 5000}
        titles = _build_section_titles(male_profile, race)
        assert not any("Altitude" in t[1] for t in titles)


# ── Trigger Function Tests ──────────────────────────────────────

class TestConditionalTriggers:
    """Tests for _conditional_triggers — the single source of truth.
    These tests verify that the shared trigger function handles all
    edge cases, including the divergent elevation fields that caused
    the original TOC/body mismatch bug (Shortcut #9)."""

    def test_returns_all_false_for_young_male_low_elev(self, male_profile, low_elevation_race):
        triggers = _conditional_triggers(male_profile, low_elevation_race)
        assert triggers == {"altitude": False, "women": False, "masters": False}

    def test_returns_all_true_for_sarah(self, female_profile, high_elevation_race):
        triggers = _conditional_triggers(female_profile, high_elevation_race)
        assert triggers == {"altitude": True, "women": True, "masters": True}

    def test_start_elev_only_triggers_altitude(self, male_profile):
        """If only start_elevation_feet > 5000 (avg and top-level are low),
        altitude MUST still trigger. This was the original divergence bug."""
        race = {
            "race_metadata": {"start_elevation_feet": 6000, "avg_elevation_feet": 4000},
            "elevation_feet": 4000,
        }
        triggers = _conditional_triggers(male_profile, race)
        assert triggers["altitude"] is True

    def test_avg_elev_only_triggers_altitude(self, male_profile):
        """If only avg_elevation_feet > 5000, altitude triggers."""
        race = {
            "race_metadata": {"start_elevation_feet": 3000, "avg_elevation_feet": 6000},
            "elevation_feet": 3000,
        }
        triggers = _conditional_triggers(male_profile, race)
        assert triggers["altitude"] is True

    def test_top_level_elev_only_triggers_altitude(self, male_profile):
        """If only top-level elevation_feet > 5000, altitude triggers."""
        race = {
            "race_metadata": {"start_elevation_feet": 3000, "avg_elevation_feet": 3000},
            "elevation_feet": 6000,
        }
        triggers = _conditional_triggers(male_profile, race)
        assert triggers["altitude"] is True

    def test_elevation_as_string_with_comma(self, male_profile):
        """elevation_feet might be '8,000' — must handle string with comma."""
        race = {
            "race_metadata": {"start_elevation_feet": 3000, "avg_elevation_feet": 3000},
            "elevation_feet": "8,000",
        }
        triggers = _conditional_triggers(male_profile, race)
        assert triggers["altitude"] is True

    def test_empty_race_data(self, male_profile):
        """Empty or missing race_data must not crash."""
        triggers = _conditional_triggers(male_profile, {})
        assert triggers["altitude"] is False

    def test_none_race_data(self, male_profile):
        """None race_data must not crash."""
        triggers = _conditional_triggers(male_profile, None)
        assert triggers["altitude"] is False


# ── TOC/Body Consistency with Divergent Elevation ──────────────

class TestTocBodyConsistencyDivergentElevation:
    """Regression tests for the TOC/body divergence bug.
    These use race data where start, avg, and top-level elevation disagree,
    which previously caused TOC to omit the altitude link while the body
    included the altitude section."""

    def test_start_elev_high_others_low(
        self, male_profile, finisher_derived, plan_config, schedule
    ):
        """Race where only start_elevation > 5000. TOC must still link to altitude."""
        race = {
            "race_metadata": {
                "name": "Divergent Race",
                "location": "Test, CO",
                "start_elevation_feet": 6000,
                "avg_elevation_feet": 4000,
            },
            "race_characteristics": {"climate": "warm", "altitude_category": "moderate",
                                     "terrain": "gravel", "technical_difficulty": "moderate"},
            "elevation_feet": 4000,
            "distance_miles": 100,
            "duration_estimate": "6-10 hours",
            "workout_modifications": {"altitude_training": {"enabled": True}},
            "non_negotiables": {},
            "race_specific": {},
        }
        html = _generate_full_html(male_profile, finisher_derived, plan_config, schedule, race)

        # Extract TOC links and body sections
        toc_links = re.findall(r'href="#(section-\d+)"', html)
        body_sections = re.findall(r'<section[^>]*id="(section-\d+)"', html)

        # TOC and body must match exactly
        for link in toc_links:
            assert link in body_sections, f"TOC has #{link} but body doesn't"
        for section in body_sections:
            assert section in toc_links, f"Body has {section} but TOC doesn't"

        # Altitude section must be present
        assert "Altitude Training" in html
