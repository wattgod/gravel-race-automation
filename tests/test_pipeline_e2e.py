"""
End-to-end pipeline integration test.

Runs Steps 1-7 with Sarah Printz's data (skips PDF, deploy, deliver).
Validates all quality gates pass through guide generation.
"""

import json
import pytest
from datetime import date, timedelta
from pathlib import Path

from pipeline.step_01_validate import validate_intake, cross_reference_race_date, _parse_date_specific
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


class TestRecoveryWeekCadence:
    """Recovery week placement must match athlete's age-appropriate cadence."""

    def test_3_week_cadence_for_40_plus(self, sarah_intake):
        """40+ athlete should have recovery every 3 weeks in pre-peak block."""
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        assert derived["recovery_week_cadence"] == 3

        plan_config = select_template(derived, BASE_DIR)
        weeks = plan_config["template"]["weeks"]
        plan_duration = plan_config["plan_duration"]

        # Find recovery weeks (vol <= 65%) in pre-peak block
        from pipeline.step_07_guide import _get_phase_boundaries
        phases = _get_phase_boundaries(plan_duration)
        peak_start = phases["peak"][0]

        recovery_weeks = [
            w["week_number"] for w in weeks
            if w.get("volume_percent", 100) <= 65 and w["week_number"] < peak_start
        ]

        # Recovery should be every 3 weeks: W3, W6, W9, W12, W15
        for rw in recovery_weeks:
            assert rw % 3 == 0, (
                f"Recovery at W{rw} doesn't align with 3-week cadence. "
                f"All recovery weeks: {recovery_weeks}"
            )

        # Verify gaps between recovery weeks are exactly 3
        for i in range(1, len(recovery_weeks)):
            gap = recovery_weeks[i] - recovery_weeks[i - 1]
            assert gap == 3, (
                f"Gap between recovery W{recovery_weeks[i-1]} and W{recovery_weeks[i]} is {gap}, expected 3. "
                f"All recovery weeks: {recovery_weeks}"
            )

    def test_4_week_cadence_for_under_40(self):
        """Under-40 athlete should have recovery every 4 weeks."""
        intake = {
            "name": "Young Rider", "email": "young@test.com",
            "sex": "male", "age": 30, "weight_lbs": 165, "height_ft": 5, "height_in": 11,
            "years_cycling": "3-5 years", "sleep": "good", "stress": "low",
            "races": [{"name": "SBT GRVL", "date": "2026-06-28", "distance_miles": 100, "priority": "A"}],
            "longest_ride": "2-4", "ftp": None, "max_hr": None, "weekly_hours": "5-7",
            "trainer_access": "yes-basic", "long_ride_days": ["saturday", "sunday"],
            "interval_days": ["tuesday", "thursday"], "off_days": ["wednesday"],
            "strength_current": "regular", "strength_include": "yes",
            "strength_equipment": "full-gym", "injuries": "NA",
        }
        validated = validate_intake(intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        assert derived["recovery_week_cadence"] == 4

        plan_config = select_template(derived, BASE_DIR)
        weeks = plan_config["template"]["weeks"]
        plan_duration = plan_config["plan_duration"]

        from pipeline.step_07_guide import _get_phase_boundaries
        phases = _get_phase_boundaries(plan_duration)
        peak_start = phases["peak"][0]

        recovery_weeks = [
            w["week_number"] for w in weeks
            if w.get("volume_percent", 100) <= 65 and w["week_number"] < peak_start
        ]

        # Recovery should be every 4 weeks: W4, W8, W12, W16
        for rw in recovery_weeks:
            assert rw % 4 == 0, (
                f"Recovery at W{rw} doesn't align with 4-week cadence. "
                f"All recovery weeks: {recovery_weeks}"
            )

    def test_session_count_excludes_rest(self, sarah_intake):
        """Week-by-week session count must not include rest days."""
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        plan_config = select_template(derived, BASE_DIR)
        weeks = plan_config["template"]["weeks"]

        for week in weeks:
            workouts = week.get("workouts", [])
            total = len(workouts)
            non_rest = sum(1 for w in workouts if "rest" not in w.get("name", "").lower())
            assert non_rest < total or total == 0, (
                f"W{week['week_number']} has {total} workouts and none are rest — "
                f"expected at least 1 rest day"
            )


class TestValidateLeadTime:
    """Step 1 must enforce lead time bounds on race dates."""

    def test_too_close_race_fails(self):
        """Race < 6 weeks away should be rejected."""
        close_date = (date.today() + timedelta(weeks=3)).isoformat()
        intake = {
            "name": "Test Athlete",
            "email": "test@example.com",
            "races": [{"name": "SBT GRVL", "date": close_date, "distance_miles": 100}],
            "weekly_hours": "5-7",
            "off_days": ["wednesday"],
        }
        with pytest.raises(ValueError, match="weeks away"):
            validate_intake(intake)

    def test_too_far_race_fails(self):
        """Race > 78 weeks away should be rejected."""
        far_date = (date.today() + timedelta(weeks=100)).isoformat()
        intake = {
            "name": "Test Athlete",
            "email": "test@example.com",
            "races": [{"name": "SBT GRVL", "date": far_date, "distance_miles": 100}],
            "weekly_hours": "5-7",
            "off_days": ["wednesday"],
        }
        with pytest.raises(ValueError, match="weeks away"):
            validate_intake(intake)

    def test_valid_lead_time_passes(self):
        """Race 20 weeks away should pass."""
        good_date = (date.today() + timedelta(weeks=20)).isoformat()
        intake = {
            "name": "Test Athlete",
            "email": "test@example.com",
            "races": [{"name": "SBT GRVL", "date": good_date, "distance_miles": 100}],
            "weekly_hours": "5-7",
            "off_days": ["wednesday"],
        }
        validated = validate_intake(intake)
        assert validated["races"][0]["race_day_of_week"]  # day of week enriched

    def test_day_of_week_enrichment(self):
        """Step 1 must add race_day_of_week to each race."""
        good_date = (date.today() + timedelta(weeks=20)).isoformat()
        expected_dow = (date.today() + timedelta(weeks=20)).strftime("%A")
        intake = {
            "name": "Test Athlete",
            "email": "test@example.com",
            "races": [{"name": "SBT GRVL", "date": good_date, "distance_miles": 100}],
            "weekly_hours": "5-7",
            "off_days": ["wednesday"],
        }
        validated = validate_intake(intake)
        assert validated["races"][0]["race_day_of_week"] == expected_dow


class TestParseDateSpecific:
    """Test the date_specific parser for race-data cross-reference."""

    def test_standard_date(self):
        assert _parse_date_specific("2026: June 28", 2026) == date(2026, 6, 28)

    def test_date_range(self):
        """Date ranges should parse to first day."""
        assert _parse_date_specific("2026: May 19-23", 2026) == date(2026, 5, 19)

    def test_date_with_parenthetical(self):
        assert _parse_date_specific("2026: May 17-18 (overnight)", 2026) == date(2026, 5, 17)

    def test_unparseable_returns_none(self):
        assert _parse_date_specific("Check USA Cycling for date", 2026) is None

    def test_vague_date_returns_none(self):
        assert _parse_date_specific("2026: Early September (weather dependent)", 2026) is None

    def test_single_digit_day(self):
        assert _parse_date_specific("2026: February 6", 2026) == date(2026, 2, 6)

    def test_wrong_year_still_parses(self):
        """date_specific may list previous year — parser should use the year in the string."""
        assert _parse_date_specific("2025: September 27", 2026) == date(2025, 9, 27)


class TestCrossReferenceRaceDate:
    """Cross-reference intake dates against race-data/ database."""

    def test_sbt_grvl_date_match(self):
        """SBT GRVL 2026 is June 28 — cross-ref should confirm."""
        result = cross_reference_race_date("SBT GRVL", "2026-06-28", BASE_DIR)
        assert result["matched"] is True
        assert result["date_match"] is True
        assert result["day_of_week"] == "Sunday"

    def test_sbt_grvl_wrong_date(self):
        """If intake says June 27, cross-ref should flag mismatch."""
        result = cross_reference_race_date("SBT GRVL", "2026-06-27", BASE_DIR)
        assert result["matched"] is True
        assert result["date_match"] is False
        assert result["warning"] is not None

    def test_unknown_race_not_matched(self):
        result = cross_reference_race_date("Fake Race 9000", "2026-06-28", BASE_DIR)
        assert result["matched"] is False

    def test_day_of_week_always_populated(self):
        result = cross_reference_race_date("SBT GRVL", "2026-06-28", BASE_DIR)
        assert result["day_of_week"] == "Sunday"


class TestGuideDateHelpers:
    """Unit tests for _week_to_date and _phase_date_range."""

    def test_week_to_date_week_1_is_start_date(self):
        from pipeline.step_07_guide import _week_to_date
        d = _week_to_date("2026-02-16", 1)
        assert d.strftime("%Y-%m-%d") == "2026-02-16"

    def test_week_to_date_week_2_is_one_week_later(self):
        from pipeline.step_07_guide import _week_to_date
        d = _week_to_date("2026-02-16", 2)
        assert d.strftime("%Y-%m-%d") == "2026-02-23"

    def test_week_to_date_week_18(self):
        from pipeline.step_07_guide import _week_to_date
        d = _week_to_date("2026-02-16", 18)
        assert d.strftime("%Y-%m-%d") == "2026-06-15"

    def test_phase_date_range_format(self):
        from pipeline.step_07_guide import _phase_date_range
        result = _phase_date_range("2026-02-16", 1, 8)
        # Should contain start and end dates with ndash
        assert "Feb" in result
        assert "Apr" in result
        assert "&ndash;" in result

    def test_phase_date_range_single_week(self):
        from pipeline.step_07_guide import _phase_date_range
        result = _phase_date_range("2026-02-16", 1, 1)
        # Single week: Feb 16 – Feb 22
        assert "Feb 16" in result
        assert "Feb 22" in result

    def test_phase_date_range_end_is_sunday(self):
        """Phase end date should be the Sunday of the last week."""
        from pipeline.step_07_guide import _phase_date_range, _week_to_date
        from datetime import timedelta
        result = _phase_date_range("2026-02-16", 1, 1)
        # Monday Feb 16 + 6 days = Sunday Feb 22
        end = _week_to_date("2026-02-16", 1) + timedelta(days=6)
        assert end.weekday() == 6  # Sunday
        assert end.strftime("%-d") in result


# ── Duration Scaling Tests ──────────────────────────────────

class TestDurationScaling:
    """Workout durations must scale to athlete capacity and round cleanly."""

    def test_parse_hours_range_standard(self):
        from pipeline.step_06_workouts import _parse_hours_range
        assert _parse_hours_range("5-7") == (5.0, 7.0)
        assert _parse_hours_range("10-12") == (10.0, 12.0)
        assert _parse_hours_range("3-5") == (3.0, 5.0)

    def test_parse_hours_range_plus(self):
        from pipeline.step_06_workouts import _parse_hours_range
        lo, hi = _parse_hours_range("15+")
        assert lo == 15.0
        assert hi == 20.0

    def test_parse_hours_range_empty(self):
        from pipeline.step_06_workouts import _parse_hours_range
        assert _parse_hours_range("") == (0.0, 0.0)
        assert _parse_hours_range(None) == (0.0, 0.0)

    def test_compute_scale_factor(self):
        from pipeline.step_06_workouts import _compute_duration_scale
        # 5-7h athlete on 10-12h template → 6/11 ≈ 0.545
        scale = _compute_duration_scale("5-7", "10-12")
        assert 0.54 <= scale <= 0.56

    def test_scale_never_exceeds_1(self):
        from pipeline.step_06_workouts import _compute_duration_scale
        # 10-12h athlete on 10-12h template → 1.0
        assert _compute_duration_scale("10-12", "10-12") == 1.0
        # 15+h athlete on 10-12h template → clamped to 1.0
        assert _compute_duration_scale("15+", "10-12") == 1.0

    def test_scale_never_below_0_4(self):
        from pipeline.step_06_workouts import _compute_duration_scale
        # 3-5h athlete on 15+h template → 4/17.5 = 0.23 → clamped to 0.4
        assert _compute_duration_scale("3-5", "15+") == 0.4

    def test_longest_ride_cap(self):
        from pipeline.step_06_workouts import _longest_ride_cap_seconds
        # "2-4" → 4 hours → 14400 seconds
        assert _longest_ride_cap_seconds("2-4") == 14400
        # "4-6" → 6 hours → 21600 seconds
        assert _longest_ride_cap_seconds("4-6") == 21600


class TestDurationRounding:
    """Scaled durations must round to clean 15-minute increments."""

    def test_round_to_15_min_for_long_durations(self):
        from pipeline.step_06_workouts import _round_duration
        # 66 min (3960s) → 60 min (3600s)
        assert _round_duration(3960) == 3600
        # 99 min (5940s) → 105 min (6300s)
        assert _round_duration(5940) == 6300
        # 132 min (7920s) → 135 min (8100s)
        assert _round_duration(7920) == 8100

    def test_round_to_5_min_for_short_durations(self):
        from pipeline.step_06_workouts import _round_duration
        # 8 min (480s) → 10 min (600s)
        assert _round_duration(480) == 600
        # 12 min (720s) → 10 min (600s)
        assert _round_duration(720) == 600

    def test_minimum_5_minutes(self):
        from pipeline.step_06_workouts import _round_duration
        assert _round_duration(100) == 300
        assert _round_duration(0) == 300

    def test_scale_blocks_rounds_cleanly(self):
        from pipeline.step_06_workouts import _scale_blocks
        blocks = '        <SteadyState Duration="10800" Power="0.65"/>\n'
        # 10800 * 0.55 = 5940 → rounds to 6300 (105 min)
        result = _scale_blocks(blocks, 0.55)
        assert 'Duration="6300"' in result

    def test_scale_blocks_preserves_interval_structure(self):
        from pipeline.step_06_workouts import _scale_blocks
        blocks = (
            '        <IntervalsT Repeat="5" OnDuration="240" OnPower="1.10" '
            'OffDuration="240" OffPower="0.50"/>\n'
        )
        result = _scale_blocks(blocks, 0.55)
        # OnDuration/OffDuration should NOT be scaled
        assert 'OnDuration="240"' in result
        assert 'OffDuration="240"' in result
        # Repeat should be scaled: 5 * 0.55 = 2.75 → 2
        assert 'Repeat="2"' in result

    def test_long_ride_cap_enforced(self):
        from pipeline.step_06_workouts import _scale_blocks
        # 3h steady state, cap at 2h (7200s)
        blocks = (
            '        <Warmup Duration="600" PowerLow="0.40" PowerHigh="0.60"/>\n'
            '        <SteadyState Duration="10800" Power="0.65"/>\n'
            '        <Cooldown Duration="600" PowerLow="0.60" PowerHigh="0.40"/>\n'
        )
        result = _scale_blocks(blocks, 1.0, long_ride_cap=7200)
        # Total should not exceed 7200s (2h)
        import re
        durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', result)]
        assert sum(durations) <= 7200


class TestWorkoutScalingE2E:
    """End-to-end test: scaled workouts match athlete's stated capacity."""

    def test_no_long_ride_exceeds_athlete_max(self, sarah_intake, tmp_path):
        """No long ride workout should exceed the athlete's stated longest ride."""
        import re
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        longest_ride_hours = sarah_intake.get("longest_ride", "2-4")
        _, max_hours = _parse_hours_range_for_test(longest_ride_hours)
        max_seconds = max_hours * 3600

        for f in workouts_dir.glob("*Long_Endurance*"):
            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            assert total <= max_seconds + 300, (  # 5 min grace for warmup/cooldown rounding
                f"{f.name}: {total/3600:.1f}h exceeds athlete max {max_hours}h"
            )

    def test_weekly_hours_within_athlete_range(self, sarah_intake, tmp_path):
        """Average weekly bike hours should be within athlete's stated range."""
        import re
        from collections import defaultdict
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        week_hours = defaultdict(float)
        for f in workouts_dir.glob("*.zwo"):
            if "Strength" in f.name or "Rest_Day" in f.name:
                continue
            m = re.match(r"W(\d+)", f.name)
            if not m:
                continue
            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            week_hours[int(m.group(1))] += sum(durations) / 3600

        avg_hours = sum(week_hours.values()) / len(week_hours) if week_hours else 0
        lo, hi = _parse_hours_range_for_test(sarah_intake["weekly_hours"])

        # Average should not wildly exceed stated range (allow 20% over for build weeks)
        assert avg_hours <= hi * 1.2, (
            f"Average {avg_hours:.1f}h/week exceeds athlete max {hi}h by > 20%"
        )

    def test_all_durations_are_clean_multiples(self, sarah_intake, tmp_path):
        """Every scaled duration should be a multiple of 5 min (300s)."""
        import re
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        for f in workouts_dir.glob("*.zwo"):
            if "Race_Day" in f.name or "FTP_Test" in f.name:
                continue  # race day openers and FTP test have intentional short intervals
            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            for dur in durations:
                if dur == 1:
                    continue  # rest day placeholder
                assert dur % 300 == 0, (
                    f"{f.name}: duration {dur}s ({dur/60:.0f}min) is not a multiple of 5 min"
                )


class TestNoWorkoutsBeforePlanStart:
    """CRITICAL: No workout files should exist for dates before plan_start_date."""

    def test_no_workouts_before_start_date(self, sarah_intake, tmp_path):
        """Every workout file date must be >= plan_start_date."""
        import re
        from datetime import datetime
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        plan_start = datetime.strptime(derived["plan_start_date"], "%Y-%m-%d").date()

        for f in workouts_dir.glob("*.zwo"):
            # Extract date from filename: W01_6Sat_Feb14_... → Feb14
            m = re.search(r"_([A-Z][a-z]{2})(\d{2})_", f.name)
            if not m:
                continue  # Race_Day has different format
            month_str, day_str = m.group(1), m.group(2)
            file_date = datetime.strptime(
                f"{month_str}{day_str} 2026", "%b%d %Y"
            ).date()
            assert file_date >= plan_start, (
                f"CRITICAL: {f.name} is dated {file_date} which is BEFORE "
                f"plan start {plan_start}. Athletes cannot time-travel."
            )

    def test_last_workout_aligns_with_race_date(self, sarah_intake, tmp_path):
        """Race day workout must fall on the actual race date."""
        import re
        from datetime import datetime
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        race_date = datetime.strptime(derived["race_date"], "%Y-%m-%d").date()
        race_files = list(workouts_dir.glob("*Race_Day*"))
        assert race_files, "No race day workout file found"

        # Race day file should contain the race date
        race_file = race_files[0]
        race_month = race_date.strftime("%b")
        race_day = race_date.strftime("%d")
        assert f"{race_month}{race_day}" in race_file.name, (
            f"Race day file {race_file.name} doesn't match race date {race_date}"
        )

    def test_first_workout_is_plan_start_date(self, sarah_intake, tmp_path):
        """The earliest workout file must be on the plan start date."""
        import re
        from datetime import datetime
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        plan_start = datetime.strptime(derived["plan_start_date"], "%Y-%m-%d").date()

        # Find earliest date across all workout files
        dates = []
        for f in sorted(workouts_dir.glob("*.zwo")):
            m = re.search(r"_([A-Z][a-z]{2})(\d{2})_", f.name)
            if m:
                file_date = datetime.strptime(
                    f"{m.group(1)}{m.group(2)} 2026", "%b%d %Y"
                ).date()
                dates.append(file_date)

        assert dates, "No workout files with dates found"
        earliest = min(dates)
        assert earliest == plan_start, (
            f"First workout is {earliest} but plan starts {plan_start}"
        )


class TestRaceDayDuration:
    """Race day workout must reflect actual race duration, not a placeholder."""

    def test_estimate_from_race_data(self):
        """_estimate_race_seconds uses duration_estimate from race JSON."""
        from pipeline.step_06_workouts import _estimate_race_seconds
        race_data = {"duration_estimate": "6-10 hours"}
        result = _estimate_race_seconds(race_data, "100")
        # Midpoint of 6-10 = 8 hours = 28800s
        assert result == 28800

    def test_estimate_from_distance_fallback(self):
        """Without duration_estimate, falls back to distance-based estimate."""
        from pipeline.step_06_workouts import _estimate_race_seconds
        result = _estimate_race_seconds(None, "100")
        # 100 miles / 14 mph ≈ 7.14h ≈ 25714s
        assert 25000 <= result <= 26000

    def test_estimate_default_fallback(self):
        """With no data at all, returns 4-hour default."""
        from pipeline.step_06_workouts import _estimate_race_seconds
        result = _estimate_race_seconds(None, None)
        assert result == 14400  # 4 hours

    def test_race_day_freeride_matches_estimate(self, sarah_intake, tmp_path):
        """Race day ZWO FreeRide duration must match race duration estimate."""
        import re
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        race_files = list(workouts_dir.glob("*Race_Day*"))
        assert race_files, "No race day workout"
        content = race_files[0].read_text()

        # Find FreeRide duration
        m = re.search(r'FreeRide Duration="(\d+)"', content)
        assert m, "No FreeRide block in race day workout"
        freeride_sec = int(m.group(1))

        # SBT GRVL 100mi: 6-10 hours → 8h midpoint → 28800s
        assert freeride_sec >= 3600 * 4, (
            f"Race day FreeRide is only {freeride_sec/3600:.1f}h — too short for a 100mi race"
        )
        assert freeride_sec <= 3600 * 12, (
            f"Race day FreeRide is {freeride_sec/3600:.1f}h — unreasonably long"
        )

    def test_race_day_never_one_hour(self, sarah_intake, tmp_path):
        """CRITICAL: Race day must NEVER be the old 1-hour placeholder for long races."""
        import re
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        race_files = list(workouts_dir.glob("*Race_Day*"))
        content = race_files[0].read_text()
        m = re.search(r'FreeRide Duration="(\d+)"', content)
        freeride_sec = int(m.group(1))
        assert freeride_sec != 3600, (
            "CRITICAL: Race day FreeRide is exactly 1 hour — the old hardcoded placeholder. "
            "This is a 100-mile gravel race, not a criterium."
        )


class TestLongRideFloor:
    """Long rides must never be embarrassingly short after scaling."""

    def test_scale_blocks_enforces_floor(self):
        """_scale_blocks with total_floor scales UP short rides."""
        from pipeline.step_06_workouts import _scale_blocks
        import re
        # 1h ride scaled down to 0.55x = ~33 min, but floor = 2h
        blocks = (
            '        <Warmup Duration="300" PowerLow="0.50" PowerHigh="0.65"/>\n'
            '        <SteadyState Duration="3600" Power="0.70"/>\n'
            '        <Cooldown Duration="300" PowerLow="0.70" PowerHigh="0.55"/>\n'
        )
        result = _scale_blocks(blocks, 0.55, total_floor=7200)
        durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', result)]
        total = sum(durations)
        assert total >= 7200, (
            f"Total {total}s ({total/60:.0f}min) is below 2h floor"
        )

    def test_floor_does_not_affect_short_sessions(self):
        """Floor=0 (non-long-ride sessions) should not inflate durations."""
        from pipeline.step_06_workouts import _scale_blocks
        import re
        blocks = (
            '        <Warmup Duration="300" PowerLow="0.50" PowerHigh="0.65"/>\n'
            '        <SteadyState Duration="1800" Power="0.70"/>\n'
            '        <Cooldown Duration="300" PowerLow="0.70" PowerHigh="0.55"/>\n'
        )
        result = _scale_blocks(blocks, 0.55, total_floor=0)
        durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', result)]
        total = sum(durations)
        # Should be scaled down (~1320s), not inflated
        assert total < 2400, f"Total {total}s should be scaled down, not inflated"

    def test_long_rides_above_floor_for_sarah(self, sarah_intake, tmp_path):
        """Every BUILD WEEK long ride for Sarah must be >= her floor (2h).

        Recovery weeks are exempt from the floor — the whole point is reduced volume.
        """
        import re
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        # Identify recovery and taper weeks (exempt from floor)
        weeks = plan_config["template"]["weeks"]
        plan_duration = plan_config["plan_duration"]
        recovery_week_nums = {
            w["week_number"] for w in weeks
            if w.get("volume_percent", 100) <= 65
        }
        exempt_weeks = recovery_week_nums | {plan_duration - 1, plan_duration}

        longest_ride = sarah_intake.get("longest_ride", "2-4")
        lo, _ = _parse_hours_range_for_test(longest_ride)
        floor_seconds = max(3600, lo * 3600)

        # Check Sunday long rides (day 7 = Sunday) — BUILD WEEKS ONLY
        for f in workouts_dir.glob("*7Sun*Long_Endurance*"):
            m = re.match(r"W(\d+)", f.name)
            if not m:
                continue
            week_num = int(m.group(1))
            if week_num in exempt_weeks:
                continue  # Recovery/taper weeks don't need floor

            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            assert total >= floor_seconds, (
                f"{f.name}: {total/3600:.1f}h is below the {lo}h floor — "
                f"a '{total/60:.0f}-minute long ride' is coaching malpractice"
            )


class TestQualitySessionsNotInflated:
    """Quality sessions (VO2max, threshold) must NOT be inflated by long ride floor."""

    def test_vo2max_warmup_not_inflated(self, sarah_intake, tmp_path):
        """VO2max warmup should be ~15 min, not inflated to hours by long ride floor."""
        import re
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        for f in workouts_dir.glob("*VO2max*"):
            content = f.read_text()
            warmups = re.findall(r'Warmup Duration="(\d+)"', content)
            for w in warmups:
                assert int(w) <= 1800, (
                    f"CRITICAL: {f.name} has a {int(w)/60:.0f}-min warmup. "
                    f"VO2max warmup should be ~15 min, not inflated by long ride floor."
                )

    def test_threshold_not_inflated(self, sarah_intake, tmp_path):
        """Threshold sessions should not exceed 2 hours total."""
        import re
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        for f in workouts_dir.glob("*Threshold*"):
            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            assert total <= 7200, (
                f"{f.name}: {total/3600:.1f}h total. Threshold sessions should be ≤2h, "
                f"not inflated by long ride floor."
            )

    def test_interval_sessions_reasonable_total(self, sarah_intake, tmp_path):
        """No interval/quality session should exceed 2.5 hours total."""
        import re
        validated = validate_intake(sarah_intake)
        profile = create_profile(validated)
        derived = classify_athlete(profile)
        schedule = build_schedule(profile, derived)
        plan_config = select_template(derived, BASE_DIR)

        workouts_dir = tmp_path / "workouts"
        workouts_dir.mkdir()
        generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

        quality_types = ["VO2max", "Threshold", "Intervals", "Sprints", "Tempo"]
        for f in workouts_dir.glob("*.zwo"):
            if not any(qt in f.name for qt in quality_types):
                continue
            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            assert total <= 9000, (
                f"CRITICAL: {f.name}: {total/3600:.1f}h total. Quality sessions should "
                f"never be this long — likely inflated by long ride floor."
            )


def _parse_hours_range_for_test(val: str):
    """Test helper — mirrors _parse_hours_range without importing."""
    if not val:
        return (0.0, 0.0)
    val = str(val).strip()
    if val.endswith("+"):
        lo = float(val[:-1])
        return (lo, lo + 5.0)
    if "-" in val:
        parts = val.split("-", 1)
        return (float(parts[0]), float(parts[1]))
    return (float(val), float(val))
