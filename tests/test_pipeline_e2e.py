"""
End-to-end pipeline integration test.

Runs Steps 1-7 with Sarah Printz's data (skips PDF, deploy, deliver).
Validates all quality gates pass through guide generation.
"""

import json
import pytest
from pathlib import Path

from pipeline.step_01_validate import validate_intake
from pipeline.step_02_profile import create_profile
from pipeline.step_03_classify import classify_athlete
from pipeline.step_04_schedule import build_schedule
from pipeline.step_05_template import select_template
from pipeline.step_06_workouts import generate_workouts, load_race_data
from pipeline.step_07_guide import generate_guide

from gates.quality_gates import (
    gate_1_intake,
    gate_2_profile,
    gate_3_classification,
    gate_4_schedule,
    gate_5_template,
    gate_6_workouts,
    gate_7_guide,
)


BASE_DIR = Path(__file__).parent.parent


@pytest.fixture
def sarah_intake():
    fixture_path = BASE_DIR / "tests" / "fixtures" / "sarah_printz.json"
    with open(fixture_path) as f:
        return json.load(f)


class TestPipelineE2E:
    """Full pipeline test with Sarah Printz data."""

    def test_step_1_validate(self, sarah_intake):
        validated = validate_intake(sarah_intake)
        gate_1_intake(validated)
        assert validated["name"] == "Sarah Printz"

    def test_step_2_profile(self, sarah_intake):
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        gate_2_profile(profile)
        assert profile["primary_race"]["name"] == "SBT GRVL"
        assert profile["primary_race"]["distance_miles"] == 100

    def test_step_3_classify(self, sarah_intake):
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        gate_3_classification(derived, profile)

        assert derived["tier"] == "finisher"
        assert derived["level"] == "intermediate"
        assert derived["race_distance_miles"] == 100

    def test_step_4_schedule(self, sarah_intake):
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        gate_4_schedule(schedule, validated)

        # Wednesday must be rest
        assert schedule["days"]["wednesday"]["session"] == "rest"
        # Saturday must be long ride
        assert schedule["days"]["saturday"]["session"] == "long_ride"

    def test_step_5_template(self, sarah_intake):
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        plan_config = select_template(derived, BASE_DIR)
        gate_5_template(plan_config, derived)

        assert plan_config["plan_duration"] == derived["plan_duration"]
        assert len(plan_config["template"]["weeks"]) == derived["plan_duration"]

    def test_step_6_workouts(self, sarah_intake, tmp_path):
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)
        gate_6_workouts(workouts_dir, derived)

        zwo_count = len(list(workouts_dir.glob("*.zwo")))
        assert zwo_count > 0
        print(f"Generated {zwo_count} ZWO files")

    def test_step_7_guide(self, sarah_intake, tmp_path):
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        guide_path = tmp_path / "guide.html"
        generate_guide(profile, derived, plan_config, schedule, guide_path, BASE_DIR)
        gate_7_guide(guide_path, validated, derived)

        html = guide_path.read_text()
        # Distance must say 100, not 142
        assert "100" in html
        # Race name present
        assert "SBT GRVL" in html
        # Methodology mentioned (tier communicated through methodology name)
        assert "traditional pyramidal" in html.lower()
        # Has altitude section (Steamboat is at 6700ft)
        assert "altitude" in html.lower() or "elevation" in html.lower()

    def test_full_pipeline_steps_1_through_7(self, sarah_intake, tmp_path):
        """Run all steps 1-7 in sequence, verify all gates pass."""
        # Step 1
        validated = validate_intake(sarah_intake)
        gate_1_intake(validated)

        # Step 2
        profile = create_profile(validated)
        gate_2_profile(profile)

        # Step 3
        derived = classify_athlete(profile)
        gate_3_classification(derived, profile)

        # Step 4
        schedule = build_schedule(profile, derived)
        gate_4_schedule(schedule, validated)

        # Step 5
        plan_config = select_template(derived, BASE_DIR)
        gate_5_template(plan_config, derived)

        # Step 6
        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)
        gate_6_workouts(workouts_dir, derived)

        # Step 7
        guide_path = tmp_path / "guide.html"
        generate_guide(profile, derived, plan_config, schedule, guide_path, BASE_DIR)
        gate_7_guide(guide_path, validated, derived)

        # Final assertions
        assert derived["tier"] == "finisher"
        assert derived["level"] == "intermediate"
        assert derived["race_distance_miles"] == 100

        zwo_count = len(list(workouts_dir.glob("*.zwo")))
        guide_size = guide_path.stat().st_size

        print(f"\n{'='*50}")
        print(f"PIPELINE E2E RESULT")
        print(f"  Tier: {derived['tier']}")
        print(f"  Level: {derived['level']}")
        print(f"  Duration: {derived['plan_duration']} weeks")
        print(f"  ZWO files: {zwo_count}")
        print(f"  Guide size: {guide_size:,} bytes")
        print(f"{'='*50}")


class TestRaceDataLoading:
    """Test distance-variant resolution."""

    def test_sbt_grvl_100_resolves_correctly(self):
        race_data = load_race_data("SBT GRVL", 100, BASE_DIR)
        assert race_data is not None
        assert race_data["distance_miles"] == 100
        assert race_data["elevation_feet"] == 8000
        assert race_data["name"] == "SBT GRVL 100"

    def test_sbt_grvl_37_resolves_correctly(self):
        race_data = load_race_data("SBT GRVL", 37, BASE_DIR)
        assert race_data is not None
        assert race_data["distance_miles"] == 37
        assert race_data["elevation_feet"] == 2800

    def test_sbt_grvl_142_resolves_correctly(self):
        race_data = load_race_data("SBT GRVL", 142, BASE_DIR)
        assert race_data is not None
        assert race_data["distance_miles"] == 142
        assert race_data["elevation_feet"] == 11000

    def test_sbt_grvl_64_resolves_correctly(self):
        race_data = load_race_data("SBT GRVL", 64, BASE_DIR)
        assert race_data is not None
        assert race_data["distance_miles"] == 64

    def test_unknown_race_returns_none(self):
        race_data = load_race_data("Nonexistent Race", 100, BASE_DIR)
        assert race_data is None

    def test_close_distance_resolves_to_nearest(self):
        """If athlete says 95 miles, should resolve to 100mi variant."""
        race_data = load_race_data("SBT GRVL", 95, BASE_DIR)
        assert race_data is not None
        assert race_data["distance_miles"] == 100


class TestTemplateExtension:
    """Template extension must not leak internal labels."""

    def test_extended_template_no_artifact_labels(self, sarah_intake):
        """When a 12-week template is extended to 20 weeks, focus text must not
        have 'Extended Base' prefix — that's an internal label."""
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        plan_config = select_template(derived, BASE_DIR)

        if plan_config["plan_duration"] <= 12:
            pytest.skip("Plan not extended — artifact test not applicable")

        weeks = plan_config["template"]["weeks"]
        for week in weeks:
            focus = week.get("focus", "")
            assert not focus.startswith("Extended Base"), (
                f"Week {week['week_number']} has internal label: '{focus}'. "
                f"Template extension should preserve original focus text."
            )
