"""
Tests for recovery week handling, methodology document, and touchpoint scheduling.

Recovery weeks must:
- Be detected from template volume_percent (≤65%)
- Have reduced volume (no long ride floor inflation)
- Have rides ≤90 minutes
- Use lighter strength sessions
- Not lose long ride floor on build weeks (regression check)

Methodology document must be generated for every athlete with all required sections.

Touchpoint schedule must have correct dates and chronological ordering.
"""

import json
import re
import pytest
from datetime import date, datetime, timedelta
from pathlib import Path

from pipeline.step_01_validate import validate_intake
from pipeline.step_02_profile import create_profile
from pipeline.step_03_classify import classify_athlete
from pipeline.step_04_schedule import build_schedule
from pipeline.step_05_template import select_template
from pipeline.step_06_workouts import generate_workouts
from pipeline.step_06b_methodology import generate_methodology
from pipeline.step_11_touchpoints import generate_touchpoints

from gates.quality_gates import gate_6b_methodology, gate_11_touchpoints


BASE_DIR = Path(__file__).parent.parent


@pytest.fixture
def sarah_intake():
    fixture_path = BASE_DIR / "tests" / "fixtures" / "sarah_printz.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.fixture
def sarah_full_pipeline(sarah_intake, tmp_path):
    """Run the full pipeline for Sarah and return all artifacts."""
    validated = validate_intake(sarah_intake)
    profile = create_profile(validated)
    derived = classify_athlete(profile)
    schedule = build_schedule(profile, derived)
    plan_config = select_template(derived, BASE_DIR)

    workouts_dir = tmp_path / "workouts"
    workouts_dir.mkdir()
    generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

    return {
        "validated": validated,
        "profile": profile,
        "derived": derived,
        "schedule": schedule,
        "plan_config": plan_config,
        "workouts_dir": workouts_dir,
        "athlete_dir": tmp_path,
    }


@pytest.fixture
def mike_intake():
    """Mike Wallace — 61yo masters finisher with knee restrictions."""
    return {
        "name": "Mike Wallace",
        "email": "iowariders@yahoo.com",
        "sex": "male",
        "age": 61,
        "weight_lbs": None,
        "height_ft": None,
        "height_in": None,
        "years_cycling": "10+",
        "sleep": "good",
        "stress": "moderate",
        "races": [{"name": "Gravel Century Goal", "date": "2026-07-04", "distance_miles": 100, "priority": "A"}],
        "longest_ride": "4-6",
        "ftp": None,
        "max_hr": None,
        "weekly_hours": "7-10",
        "trainer_access": "yes-basic",
        "long_ride_days": ["saturday", "sunday"],
        "interval_days": ["tuesday", "thursday"],
        "off_days": ["wednesday", "friday"],
        "strength_current": "regular",
        "strength_include": "yes",
        "strength_equipment": "full-gym",
        "injuries": "Chondromalacia patella (left knee) — can spin but limited with standing, stomping, or heavy axial loading. Hip resurfacing 2020.",
    }


@pytest.fixture
def mike_full_pipeline(mike_intake, tmp_path):
    """Run the full pipeline for Mike and return all artifacts."""
    validated = validate_intake(mike_intake)
    profile = create_profile(validated)
    derived = classify_athlete(profile)
    schedule = build_schedule(profile, derived)
    plan_config = select_template(derived, BASE_DIR)

    workouts_dir = tmp_path / "workouts"
    workouts_dir.mkdir()
    generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

    return {
        "validated": validated,
        "profile": profile,
        "derived": derived,
        "schedule": schedule,
        "plan_config": plan_config,
        "workouts_dir": workouts_dir,
        "athlete_dir": tmp_path,
    }


# ── Recovery Week Detection ──────────────────────────────────

class TestRecoveryWeekDetection:
    """Recovery weeks must be identified from template volume_percent."""

    def test_recovery_weeks_have_reduced_volume(self, sarah_full_pipeline):
        """Recovery week rides should be scaled down — no 4-hour recovery rides."""
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        plan_config = sarah_full_pipeline["plan_config"]
        weeks = plan_config["template"]["weeks"]

        recovery_week_nums = {
            w["week_number"] for w in weeks
            if w.get("volume_percent", 100) <= 65
        }
        assert recovery_week_nums, "No recovery weeks found in template"

        # Check rides on recovery weeks
        for f in workouts_dir.glob("*.zwo"):
            m = re.match(r"W(\d+)", f.name)
            if not m:
                continue
            week_num = int(m.group(1))
            if week_num not in recovery_week_nums:
                continue
            if any(skip in f.name for skip in ("Rest_Day", "Strength", "FTP_Test", "Race_Day")):
                continue

            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            # Recovery week rides should be under 90 minutes (5400s)
            assert total <= 5400, (
                f"CRITICAL: {f.name} on recovery week {week_num} is "
                f"{total/60:.0f}min — recovery rides must be ≤90 min"
            )

    def test_no_long_ride_floor_on_recovery_weeks(self, sarah_full_pipeline):
        """Long ride floor must NOT apply during recovery weeks."""
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        plan_config = sarah_full_pipeline["plan_config"]
        weeks = plan_config["template"]["weeks"]

        recovery_week_nums = {
            w["week_number"] for w in weeks
            if w.get("volume_percent", 100) <= 65
        }

        for f in workouts_dir.glob("*.zwo"):
            m = re.match(r"W(\d+)", f.name)
            if not m:
                continue
            week_num = int(m.group(1))
            if week_num not in recovery_week_nums:
                continue
            if "Long_Endurance" in f.name:
                pytest.fail(
                    f"CRITICAL: {f.name} — recovery week should NOT have "
                    f"'Long_Endurance' rides. Floor is inflating recovery weeks."
                )

    def test_recovery_rides_under_90_minutes(self, mike_full_pipeline):
        """No ride on a recovery week should exceed 90 minutes — even for Mike (4-6h athlete)."""
        workouts_dir = mike_full_pipeline["workouts_dir"]
        plan_config = mike_full_pipeline["plan_config"]
        weeks = plan_config["template"]["weeks"]

        recovery_week_nums = {
            w["week_number"] for w in weeks
            if w.get("volume_percent", 100) <= 65
        }

        for f in workouts_dir.glob("*.zwo"):
            m = re.match(r"W(\d+)", f.name)
            if not m:
                continue
            week_num = int(m.group(1))
            if week_num not in recovery_week_nums:
                continue
            if any(skip in f.name for skip in ("Rest_Day", "Strength", "FTP_Test", "Race_Day")):
                continue

            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            assert total <= 5400, (
                f"CRITICAL: {f.name} on recovery week {week_num} is "
                f"{total/60:.0f}min — this is Mike's recovery week, not a build ride"
            )

    def test_recovery_week_cadence_masters(self, sarah_full_pipeline):
        """Masters athletes (40+) get recovery every 3 weeks."""
        derived = sarah_full_pipeline["derived"]
        assert derived["recovery_week_cadence"] == 3

    def test_recovery_strength_is_lighter(self, sarah_full_pipeline):
        """Recovery week strength is mobility-focused, ≤30 min."""
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        plan_config = sarah_full_pipeline["plan_config"]
        weeks = plan_config["template"]["weeks"]

        recovery_week_nums = {
            w["week_number"] for w in weeks
            if w.get("volume_percent", 100) <= 65
        }

        for f in workouts_dir.glob("*Strength*Recovery*"):
            m = re.match(r"W(\d+)", f.name)
            if not m:
                continue
            week_num = int(m.group(1))
            if week_num not in recovery_week_nums:
                continue

            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            # Recovery strength: 30 min = 1800s
            assert total <= 1800, (
                f"{f.name} on recovery week: {total/60:.0f}min strength. "
                f"Recovery strength should be ≤30 min."
            )

    def test_build_weeks_still_have_floor(self, sarah_full_pipeline):
        """Build week long rides must still respect the floor (no regression)."""
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        plan_config = sarah_full_pipeline["plan_config"]
        weeks = plan_config["template"]["weeks"]

        recovery_week_nums = {
            w["week_number"] for w in weeks
            if w.get("volume_percent", 100) <= 65
        }
        # Taper weeks also don't need floor check
        plan_duration = plan_config["plan_duration"]
        non_floor_weeks = recovery_week_nums | {plan_duration - 1, plan_duration}

        sarah_floor_seconds = 2 * 3600  # Sarah: longest_ride "2-4" → floor = 2h

        for f in workouts_dir.glob("*Long_Endurance*"):
            m = re.match(r"W(\d+)", f.name)
            if not m:
                continue
            week_num = int(m.group(1))
            if week_num in non_floor_weeks:
                continue

            content = f.read_text()
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            assert total >= sarah_floor_seconds, (
                f"{f.name} on build week {week_num}: {total/3600:.1f}h is below "
                f"the 2h floor — regression in build week floor enforcement"
            )


# ── Methodology Document ─────────────────────────────────────

class TestMethodologyDocument:
    """Internal methodology doc must be generated for every athlete."""

    def test_methodology_json_created(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]
        schedule = sarah_full_pipeline["schedule"]

        generate_methodology(profile, derived, plan_config, schedule, athlete_dir)

        assert (athlete_dir / "methodology.json").exists()
        assert (athlete_dir / "methodology.md").exists()

    def test_methodology_contains_required_sections(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]
        schedule = sarah_full_pipeline["schedule"]

        doc = generate_methodology(profile, derived, plan_config, schedule, athlete_dir)

        required = [
            "athlete_summary", "why_this_plan", "template_selection",
            "periodization", "scaling", "accommodations",
            "weekly_structure", "key_workouts_per_phase", "generated_at",
        ]
        for section in required:
            assert section in doc, f"Missing methodology section: {section}"

    def test_rationale_is_deterministic(self, sarah_full_pipeline):
        """Running methodology generation twice produces identical output."""
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]
        schedule = sarah_full_pipeline["schedule"]

        doc1 = generate_methodology(profile, derived, plan_config, schedule, athlete_dir)
        doc2 = generate_methodology(profile, derived, plan_config, schedule, athlete_dir)

        # Everything except generated_at should be identical
        for key in doc1:
            if key == "generated_at":
                continue
            assert doc1[key] == doc2[key], f"Non-deterministic section: {key}"

    def test_recovery_weeks_listed(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]
        schedule = sarah_full_pipeline["schedule"]

        doc = generate_methodology(profile, derived, plan_config, schedule, athlete_dir)
        recovery_weeks = doc["periodization"]["recovery_weeks"]
        assert len(recovery_weeks) >= 2, f"Only {len(recovery_weeks)} recovery weeks listed"

    def test_methodology_gate_passes(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]
        schedule = sarah_full_pipeline["schedule"]

        generate_methodology(profile, derived, plan_config, schedule, athlete_dir)
        gate_6b_methodology(athlete_dir)  # Should not raise


# ── Touchpoints ──────────────────────────────────────────────

class TestTouchpoints:
    """Automated check-in schedule must be generated."""

    def test_touchpoints_json_created(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]

        result = generate_touchpoints(profile, derived, plan_config, athlete_dir)
        assert (athlete_dir / "touchpoints.json").exists()

    def test_all_touchpoint_types_present(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]

        result = generate_touchpoints(profile, derived, plan_config, athlete_dir)
        tp_ids = {tp["id"] for tp in result["touchpoints"]}

        expected_ids = {
            "week_1_welcome", "week_2_checkin", "first_recovery",
            "mid_plan", "build_phase_start", "race_month",
            "race_week", "race_day_morning", "post_race_3_days",
            "post_race_2_weeks",
        }
        assert expected_ids == tp_ids, (
            f"Missing: {expected_ids - tp_ids}, Extra: {tp_ids - expected_ids}"
        )

    def test_dates_are_chronological(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]

        result = generate_touchpoints(profile, derived, plan_config, athlete_dir)
        dates = [tp["send_date"] for tp in result["touchpoints"]]
        assert dates == sorted(dates), f"Dates not chronological: {dates}"

    def test_race_week_touchpoint_is_7_days_before(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]

        result = generate_touchpoints(profile, derived, plan_config, athlete_dir)
        race_date = datetime.strptime(derived["race_date"], "%Y-%m-%d")

        race_week_tp = [tp for tp in result["touchpoints"] if tp["id"] == "race_week"][0]
        race_week_date = datetime.strptime(race_week_tp["send_date"], "%Y-%m-%d")
        diff = (race_date - race_week_date).days
        assert diff == 7, f"Race week touchpoint is {diff} days before race, expected 7"

    def test_post_race_touchpoints_after_race_date(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]

        result = generate_touchpoints(profile, derived, plan_config, athlete_dir)
        race_date = derived["race_date"]

        for tp in result["touchpoints"]:
            if tp["id"].startswith("post_race"):
                assert tp["send_date"] > race_date, (
                    f"Post-race '{tp['id']}' on {tp['send_date']} is before race {race_date}"
                )

    def test_touchpoints_gate_passes(self, sarah_full_pipeline):
        athlete_dir = sarah_full_pipeline["athlete_dir"]
        profile = sarah_full_pipeline["profile"]
        derived = sarah_full_pipeline["derived"]
        plan_config = sarah_full_pipeline["plan_config"]

        generate_touchpoints(profile, derived, plan_config, athlete_dir)
        gate_11_touchpoints(athlete_dir, derived)  # Should not raise


# ── Exercise Library URLs ─────────────────────────────────────

class TestExerciseLibraryURLs:
    """Strength workouts must include exercise demo URLs."""

    def test_base_strength_has_urls(self, sarah_full_pipeline):
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        base_strength = list(workouts_dir.glob("*Strength_Base*"))
        assert base_strength, "No base strength workouts found"

        content = base_strength[0].read_text()
        assert "youtube.com" in content, "Base strength workout missing exercise URLs"

    def test_build_strength_has_urls(self, sarah_full_pipeline):
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        build_strength = list(workouts_dir.glob("*Strength_Build*"))
        assert build_strength, "No build strength workouts found"

        content = build_strength[0].read_text()
        assert "youtube.com" in content, "Build strength workout missing exercise URLs"

    def test_knee_restriction_flagged(self, mike_full_pipeline):
        """Mike has chondromalacia — strength workouts should have knee warning."""
        workouts_dir = mike_full_pipeline["workouts_dir"]
        strength_files = list(workouts_dir.glob("*Strength_B*"))
        assert strength_files, "No strength workouts for Mike"

        content = strength_files[0].read_text()
        assert "KNEE RESTRICTION" in content or "MODIFY" in content, (
            "Mike has chondromalacia but strength workout has no knee restriction note"
        )
