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

    def test_knee_exercises_actually_swapped(self, mike_full_pipeline):
        """Mike has chondromalacia — dangerous exercises must be REPLACED, not just warned about."""
        workouts_dir = mike_full_pipeline["workouts_dir"]
        # Check base phase strength (has Bulgarian Split Squat in unmodified version)
        base_strength = sorted(workouts_dir.glob("*Strength_Base*"))
        assert base_strength, "No base strength workouts for Mike"

        content = base_strength[0].read_text()
        # Bulgarian Split Squat should be GONE — replaced with Wall Sit
        assert "BULGARIAN SPLIT SQUAT" not in content, (
            "Mike has chondromalacia but Bulgarian Split Squat was NOT replaced"
        )
        assert "WALL SIT" in content, (
            "Mike has chondromalacia but Wall Sit substitute is missing"
        )
        # Should have modification note
        assert "EXERCISES MODIFIED" in content, (
            "Mike's strength workout missing modification note"
        )

    def test_knee_build_phase_no_heavy_squat(self, mike_full_pipeline):
        """Mike must NOT get 'Heavy. Full depth.' squat in build phase."""
        workouts_dir = mike_full_pipeline["workouts_dir"]
        build_strength = sorted(workouts_dir.glob("*Strength_Build*"))
        assert build_strength, "No build strength workouts for Mike"

        content = build_strength[0].read_text()
        assert "Full depth" not in content, (
            "Mike has chondromalacia but build phase still says 'Full depth'"
        )
        assert "STEP-UPS" not in content, (
            "Mike has chondromalacia but Step-Ups were NOT replaced"
        )

    def test_hip_exercises_swapped_for_mike(self, mike_full_pipeline):
        """Mike has hip resurfacing — hip-stress exercises must be replaced."""
        workouts_dir = mike_full_pipeline["workouts_dir"]
        base_strength = sorted(workouts_dir.glob("*Strength_Base*"))
        assert base_strength, "No base strength workouts for Mike"

        content = base_strength[0].read_text()
        # Hip resurfacing: "Full depth" goblet squat should become limited depth
        assert "Full depth" not in content, (
            "Mike has hip resurfacing but 'Full depth' was not removed from goblet squat"
        )


# ── Fixtures for Back + GI Injury Testing ─────────────────────

@pytest.fixture
def benjy_intake():
    """Benjy Duke — 38yo intermediate with herniated L4/L5 discs."""
    return {
        "name": "Benjy Duke",
        "email": "benjyduke@gmail.com",
        "sex": "male",
        "age": 38,
        "weight_lbs": None,
        "height_ft": None,
        "height_in": None,
        "years_cycling": "3-5",
        "sleep": "good",
        "stress": "moderate",
        "races": [{"name": "SBT GRVL", "date": "2026-06-28", "distance_miles": 75, "priority": "A"}],
        "longest_ride": "1-2",
        "ftp": 180,
        "max_hr": None,
        "weekly_hours": "3-5",
        "trainer_access": "yes-basic",
        "long_ride_days": ["saturday", "sunday"],
        "interval_days": ["tuesday", "thursday"],
        "off_days": ["monday", "friday"],
        "strength_current": "bodyweight",
        "strength_include": "yes",
        "strength_equipment": "bodyweight",
        "injuries": "Herniated L4/L5 discs in 2019. Recovered through extensive PT and routine stretching. Back occasionally tightens up.",
    }


@pytest.fixture
def benjy_full_pipeline(benjy_intake, tmp_path):
    """Run the full pipeline for Benjy and return all artifacts."""
    validated = validate_intake(benjy_intake)
    profile = create_profile(validated)
    derived = classify_athlete(profile)
    schedule = build_schedule(profile, derived)
    plan_config = select_template(derived, BASE_DIR)

    workouts_dir = tmp_path / "workouts"
    workouts_dir.mkdir()
    generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

    return {
        "workouts_dir": workouts_dir,
        "athlete_dir": tmp_path,
        "profile": profile,
        "derived": derived,
    }


@pytest.fixture
def burk_intake():
    """Burk Knowlton — 34yo intermediate with acid reflux/GI issues."""
    return {
        "name": "Burk Knowlton",
        "email": "bknowlton91@gmail.com",
        "sex": "male",
        "age": 34,
        "weight_lbs": None,
        "height_ft": None,
        "height_in": None,
        "years_cycling": "3-5",
        "sleep": "fair",
        "stress": "high",
        "races": [{"name": "SBT GRVL", "date": "2026-06-28", "distance_miles": 73, "priority": "A"}],
        "longest_ride": "1-2",
        "ftp": None,
        "max_hr": None,
        "weekly_hours": "3-5",
        "trainer_access": "yes-basic",
        "long_ride_days": ["sunday"],
        "interval_days": ["thursday", "saturday"],
        "off_days": ["monday", "friday"],
        "strength_current": "dumbbells",
        "strength_include": "yes",
        "strength_equipment": "dumbbells-kettlebells",
        "injuries": "Acid reflux and associated GI issue — managed with strict diet (no caffeine). Much improved but still recovering. On Pepcid.",
    }


@pytest.fixture
def burk_full_pipeline(burk_intake, tmp_path):
    """Run the full pipeline for Burk and return all artifacts."""
    validated = validate_intake(burk_intake)
    profile = create_profile(validated)
    derived = classify_athlete(profile)
    schedule = build_schedule(profile, derived)
    plan_config = select_template(derived, BASE_DIR)

    workouts_dir = tmp_path / "workouts"
    workouts_dir.mkdir()
    generate_workouts(plan_config, profile, derived, schedule, workouts_dir, BASE_DIR)

    return {
        "workouts_dir": workouts_dir,
        "athlete_dir": tmp_path,
        "profile": profile,
        "derived": derived,
    }


# ── Back Injury Tests ──────────────────────────────────────────

class TestBackInjuryAccommodation:
    """Benjy has herniated L4/L5 — back-stress exercises must be replaced."""

    def test_romanian_deadlift_replaced(self, benjy_full_pipeline):
        """Romanian Deadlift is a spine-loading hinge — must be swapped for L4/L5."""
        workouts_dir = benjy_full_pipeline["workouts_dir"]
        base_strength = sorted(workouts_dir.glob("*Strength_Base*"))
        assert base_strength, "No base strength workouts for Benjy"

        content = base_strength[0].read_text()
        assert "ROMANIAN DEADLIFT" not in content, (
            "Benjy has herniated L4/L5 but Romanian Deadlift was NOT replaced"
        )
        assert "BIRD DOG" in content, (
            "Benjy has herniated L4/L5 but Bird Dog substitute is missing"
        )

    def test_build_phase_no_heavy_axial_loading(self, benjy_full_pipeline):
        """Build phase must not prescribe heavy barbell squats for back-injured athlete."""
        workouts_dir = benjy_full_pipeline["workouts_dir"]
        build_strength = sorted(workouts_dir.glob("*Strength_Build*"))
        assert build_strength, "No build strength workouts for Benjy"

        content = build_strength[0].read_text()
        assert "BARBELL" not in content, (
            "Benjy has herniated L4/L5 but BARBELL exercise still present"
        )
        assert "FARMER" not in content, (
            "Benjy has herniated L4/L5 but Farmer's Carry (spinal compression) still present"
        )

    def test_modification_note_present(self, benjy_full_pipeline):
        """Must have explicit note about which exercises were modified."""
        workouts_dir = benjy_full_pipeline["workouts_dir"]
        base_strength = sorted(workouts_dir.glob("*Strength_Base*"))
        content = base_strength[0].read_text()
        assert "EXERCISES MODIFIED" in content, (
            "Benjy's strength workout missing modification note"
        )
        assert "back" in content.lower() or "spine" in content.lower(), (
            "Modification note doesn't mention back/spine accommodation"
        )


# ── GI Accommodation Tests ─────────────────────────────────────

class TestGIAccommodation:
    """Burk has acid reflux — nutrition guidance must be modified."""

    def test_long_ride_nutrition_gi_safe(self, burk_full_pipeline):
        """Long rides must NOT recommend standard 60-80g carbs/hour for GI athlete."""
        workouts_dir = burk_full_pipeline["workouts_dir"]
        long_rides = sorted(workouts_dir.glob("*Long_Endurance*"))
        if not long_rides:
            long_rides = sorted(workouts_dir.glob("*Endurance*"))
        assert long_rides, "No endurance rides found for Burk"

        content = long_rides[0].read_text()
        # Standard 60-80g recommendation must be replaced
        assert "60-80g carbs/hour" not in content, (
            "Burk has acid reflux but got standard 60-80g carbs/hour recommendation"
        )

    def test_gi_accommodation_note_present(self, burk_full_pipeline):
        """Long rides must have GI accommodation note."""
        workouts_dir = burk_full_pipeline["workouts_dir"]
        long_rides = sorted(workouts_dir.glob("*Long_Endurance*"))
        if not long_rides:
            long_rides = sorted(workouts_dir.glob("*Endurance*"))
        assert long_rides, "No endurance rides found"

        content = long_rides[0].read_text()
        assert "GI ACCOMMODATION" in content, (
            "Burk has acid reflux but long ride is missing GI accommodation note"
        )

    def test_no_caffeine_recommendation(self, burk_full_pipeline):
        """Must explicitly warn against caffeine for this athlete."""
        workouts_dir = burk_full_pipeline["workouts_dir"]
        long_rides = sorted(workouts_dir.glob("*Long_Endurance*"))
        if not long_rides:
            long_rides = sorted(workouts_dir.glob("*Endurance*"))
        assert long_rides, "No endurance rides found"

        content = long_rides[0].read_text()
        assert "caffeine" in content.lower(), (
            "Burk's intake says 'no caffeine' but workouts don't mention it"
        )

    def test_race_day_gi_safe_nutrition(self, burk_full_pipeline):
        """Race day workout must have GI-safe nutrition, not standard advice."""
        workouts_dir = burk_full_pipeline["workouts_dir"]
        race_day = list(workouts_dir.glob("*Race_Day*"))
        assert race_day, "No race day workout for Burk"

        content = race_day[0].read_text()
        assert "60-80g carbs/hour" not in content, (
            "Burk's race day still has standard 60-80g recommendation despite acid reflux"
        )


# ── ZWO Structural Validation ──────────────────────────────────

class TestZWOStructuralValidity:
    """Every ZWO file must be valid XML with sane power/duration values."""

    def test_all_zwos_parse_as_xml(self, sarah_full_pipeline):
        """Every ZWO must be parseable XML."""
        import xml.etree.ElementTree as ET
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        for f in sorted(workouts_dir.glob("*.zwo")):
            try:
                ET.parse(f)
            except ET.ParseError as e:
                pytest.fail(f"{f.name} is not valid XML: {e}")

    def test_power_values_in_range(self, sarah_full_pipeline):
        """Power values must be FTP fractions (0.2 - 1.5), never absolute watts."""
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        for f in sorted(workouts_dir.glob("*.zwo")):
            content = f.read_text()
            powers = re.findall(r'Power(?:Low|High)?="([^"]+)"', content)
            for p in powers:
                val = float(p)
                assert 0.1 <= val <= 1.5, (
                    f"{f.name} has Power={val} — must be 0.1-1.5 FTP fraction"
                )

    def test_no_zero_duration_blocks(self, sarah_full_pipeline):
        """No workout block should have Duration=0."""
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        for f in sorted(workouts_dir.glob("*.zwo")):
            if "Rest_Day" in f.name:
                continue
            content = f.read_text()
            durations = re.findall(r'Duration="(\d+)"', content)
            for d in durations:
                assert int(d) > 0, f"{f.name} has Duration=0"

    def test_recovery_rides_zone2_power(self, mike_full_pipeline):
        """Recovery week rides must be Zone 1-2 power (< 0.65 FTP)."""
        workouts_dir = mike_full_pipeline["workouts_dir"]
        plan_config = mike_full_pipeline["plan_config"] if "plan_config" in mike_full_pipeline else None
        for f in sorted(workouts_dir.glob("*Easy_Recovery*")):
            content = f.read_text()
            powers = re.findall(r'Power="([^"]+)"', content)
            for p in powers:
                val = float(p)
                assert val <= 0.65, (
                    f"{f.name} has Power={val} — recovery rides must be ≤0.65 FTP"
                )

    def test_warmup_present_in_interval_workouts(self, sarah_full_pipeline):
        """Interval workouts must have a warmup block."""
        workouts_dir = sarah_full_pipeline["workouts_dir"]
        interval_files = [f for f in workouts_dir.glob("*.zwo")
                         if any(kw in f.name for kw in ("Interval", "VO2", "Threshold", "Sweet_Spot"))]
        for f in interval_files[:5]:  # Check first 5
            content = f.read_text()
            assert "<Warmup" in content, f"{f.name} is an interval workout with no warmup"
