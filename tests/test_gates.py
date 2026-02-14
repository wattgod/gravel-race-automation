"""Tests for all 10 quality gates."""

import json
import pytest
from pathlib import Path

from gates.quality_gates import (
    gate_1_intake,
    gate_2_profile,
    gate_3_classification,
    gate_4_schedule,
    gate_5_template,
    gate_6_workouts,
    gate_7_guide,
    gate_8_pdf,
)


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def valid_intake():
    return {
        "name": "Test Athlete",
        "email": "test@example.com",
        "races": [{"name": "SBT GRVL", "date": "2026-06-28", "distance_miles": 100}],
        "weekly_hours": "5-7",
        "off_days": ["wednesday"],
    }


@pytest.fixture
def valid_profile():
    return {
        "name": "Test Athlete",
        "email": "test@example.com",
        "demographics": {"sex": "female", "age": 44},
        "race_calendar": [{"name": "SBT GRVL", "date": "2026-06-28", "distance_miles": 100}],
        "fitness": {"ftp_watts": None},
        "schedule": {"weekly_hours": "5-7", "off_days": ["wednesday"]},
        "training_history": {"years_cycling": "3-5 years"},
        "strength": {"include_in_plan": "yes"},
        "health": {"sleep_quality": "good"},
    }


@pytest.fixture
def valid_derived():
    return {
        "tier": "finisher",
        "level": "intermediate",
        "weekly_hours": "5-7",
        "plan_weeks": 20,
        "plan_duration": 20,
        "is_masters": False,
        "race_name": "SBT GRVL",
        "race_date": "2026-06-28",
        "race_distance_miles": 100,
    }


@pytest.fixture
def valid_schedule():
    return {
        "description": "Custom weekly structure",
        "tier": "finisher",
        "days": {
            "monday": {"session": "easy_ride", "notes": ""},
            "tuesday": {"session": "intervals", "notes": ""},
            "wednesday": {"session": "rest", "notes": "Off day"},
            "thursday": {"session": "intervals", "notes": ""},
            "friday": {"session": "strength", "notes": ""},
            "saturday": {"session": "long_ride", "notes": ""},
            "sunday": {"session": "long_ride", "notes": ""},
        },
    }


# ── Gate 1 Tests ─────────────────────────────────────────────

class TestGate1:
    def test_valid_intake_passes(self, valid_intake):
        gate_1_intake(valid_intake)  # Should not raise

    def test_missing_name_fails(self, valid_intake):
        valid_intake["name"] = ""
        with pytest.raises(AssertionError, match="Name"):
            gate_1_intake(valid_intake)

    def test_missing_email_fails(self, valid_intake):
        valid_intake["email"] = ""
        with pytest.raises(AssertionError, match="email"):
            gate_1_intake(valid_intake)

    def test_no_races_fails(self, valid_intake):
        valid_intake["races"] = []
        with pytest.raises(AssertionError, match="race"):
            gate_1_intake(valid_intake)


# ── Gate 2 Tests ─────────────────────────────────────────────

class TestGate2:
    def test_valid_profile_passes(self, valid_profile):
        gate_2_profile(valid_profile)

    def test_missing_section_fails(self, valid_profile):
        del valid_profile["demographics"]
        with pytest.raises(AssertionError, match="demographics"):
            gate_2_profile(valid_profile)

    def test_empty_race_calendar_fails(self, valid_profile):
        valid_profile["race_calendar"] = []
        with pytest.raises(AssertionError, match="race"):
            gate_2_profile(valid_profile)


# ── Gate 3 Tests ─────────────────────────────────────────────

class TestGate3:
    def test_valid_classification_passes(self, valid_derived, valid_profile):
        gate_3_classification(valid_derived, valid_profile)

    def test_invalid_tier_fails(self, valid_derived, valid_profile):
        valid_derived["tier"] = "invalid"
        with pytest.raises(AssertionError, match="tier"):
            gate_3_classification(valid_derived, valid_profile)

    def test_invalid_level_fails(self, valid_derived, valid_profile):
        valid_derived["level"] = "invalid"
        with pytest.raises(AssertionError, match="level"):
            gate_3_classification(valid_derived, valid_profile)

    def test_tier_hours_mismatch_fails(self, valid_derived, valid_profile):
        valid_derived["tier"] = "podium"
        valid_derived["weekly_hours"] = "5-7"
        with pytest.raises(AssertionError, match="hours"):
            gate_3_classification(valid_derived, valid_profile)


# ── Gate 4 Tests ─────────────────────────────────────────────

class TestGate4:
    def test_valid_schedule_passes(self, valid_schedule, valid_intake):
        gate_4_schedule(valid_schedule, valid_intake)

    def test_too_few_training_days_fails(self, valid_intake):
        bad_schedule = {
            "days": {
                "monday": {"session": "rest", "notes": ""},
                "tuesday": {"session": "rest", "notes": ""},
                "wednesday": {"session": "rest", "notes": ""},
                "thursday": {"session": "rest", "notes": ""},
                "friday": {"session": "intervals", "notes": ""},
                "saturday": {"session": "long_ride", "notes": ""},
                "sunday": {"session": "rest", "notes": ""},
            }
        }
        with pytest.raises(AssertionError, match="training days"):
            gate_4_schedule(bad_schedule, valid_intake)

    def test_off_day_not_respected_fails(self, valid_schedule, valid_intake):
        valid_schedule["days"]["wednesday"]["session"] = "intervals"
        with pytest.raises(AssertionError, match="wednesday"):
            gate_4_schedule(valid_schedule, valid_intake)

    def test_no_long_ride_fails(self, valid_intake):
        bad_schedule = {
            "days": {
                "monday": {"session": "easy_ride", "notes": ""},
                "tuesday": {"session": "intervals", "notes": ""},
                "wednesday": {"session": "rest", "notes": ""},
                "thursday": {"session": "intervals", "notes": ""},
                "friday": {"session": "easy_ride", "notes": ""},
                "saturday": {"session": "easy_ride", "notes": ""},
                "sunday": {"session": "easy_ride", "notes": ""},
            }
        }
        with pytest.raises(AssertionError, match="long ride"):
            gate_4_schedule(bad_schedule, valid_intake)


# ── Gate 5 Tests ─────────────────────────────────────────────

class TestGate5:
    def test_valid_template_passes(self, valid_derived):
        plan_config = {
            "template": {"weeks": [{"week_number": i} for i in range(1, 21)]},
            "plan_duration": 20,
        }
        gate_5_template(plan_config, valid_derived)

    def test_wrong_week_count_fails(self, valid_derived):
        plan_config = {
            "template": {"weeks": [{"week_number": i} for i in range(1, 13)]},
            "plan_duration": 20,
        }
        with pytest.raises(AssertionError, match="12 weeks"):
            gate_5_template(plan_config, valid_derived)


# ── Gate 6 Tests ─────────────────────────────────────────────

class TestGate6:
    ZWO_VALID = (
        '<?xml version="1.0"?>\n'
        "<workout_file>\n"
        "  <workout>\n"
        '    <SteadyState Duration="600" Power="0.65"/>\n'
        "  </workout>\n"
        "</workout_file>"
    )

    def _populate_workouts(self, tmp_path, derived, extra_files=None):
        """Create realistic workout files: 7 per week with strength + rest."""
        plan_duration = derived["plan_duration"]
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for w in range(1, plan_duration + 1):
            for d in days:
                if d == "Wed":
                    name = f"W{w:02d}_{d}_Rest_Day.zwo"
                elif d == "Fri":
                    name = f"W{w:02d}_{d}_Strength_Base.zwo"
                else:
                    name = f"W{w:02d}_{d}_workout.zwo"
                (tmp_path / name).write_text(self.ZWO_VALID)
        if extra_files:
            for ef in extra_files:
                (tmp_path / ef).write_text(self.ZWO_VALID)

    def test_valid_zwo_passes(self, tmp_path, valid_derived):
        self._populate_workouts(tmp_path, valid_derived)
        gate_6_workouts(tmp_path, valid_derived)

    def test_insane_power_fails(self, tmp_path, valid_derived):
        self._populate_workouts(tmp_path, valid_derived)
        # Overwrite one file with bad power
        (tmp_path / "W01_Mon_workout.zwo").write_text(
            '<?xml version="1.0"?>\n'
            "<workout_file>\n"
            "  <workout>\n"
            '    <SteadyState Duration="600" Power="5.0"/>\n'
            "  </workout>\n"
            "</workout_file>"
        )
        with pytest.raises(AssertionError, match="power target"):
            gate_6_workouts(tmp_path, valid_derived)

    def test_too_few_files_fails(self, tmp_path, valid_derived):
        for i in range(5):
            (tmp_path / f"W{i:02d}_workout.zwo").write_text(self.ZWO_VALID)
        with pytest.raises(AssertionError, match="Too few"):
            gate_6_workouts(tmp_path, valid_derived)

    def test_no_strength_files_fails(self, tmp_path, valid_derived):
        """Gate 6 requires strength workout files exist."""
        plan_duration = valid_derived["plan_duration"]
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for w in range(1, plan_duration + 1):
            for d in days:
                if d == "Wed":
                    name = f"W{w:02d}_{d}_Rest_Day.zwo"
                else:
                    name = f"W{w:02d}_{d}_workout.zwo"
                (tmp_path / name).write_text(self.ZWO_VALID)
        with pytest.raises(AssertionError, match="strength"):
            gate_6_workouts(tmp_path, valid_derived)

    def test_no_rest_files_fails(self, tmp_path, valid_derived):
        """Gate 6 requires rest/off-day ZWO files exist."""
        plan_duration = valid_derived["plan_duration"]
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for w in range(1, plan_duration + 1):
            for d in days:
                if d == "Fri":
                    name = f"W{w:02d}_{d}_Strength_Base.zwo"
                else:
                    name = f"W{w:02d}_{d}_workout.zwo"
                (tmp_path / name).write_text(self.ZWO_VALID)
        with pytest.raises(AssertionError, match="rest"):
            gate_6_workouts(tmp_path, valid_derived)


# ── Gate 7 Tests ─────────────────────────────────────────────

class TestGate7:
    """Gate 7 tests: 50KB minimum, all 14 sections, no placeholders, no nulls."""

    # All 14 required sections
    REQUIRED_SECTIONS = [
        "race profile", "non-negotiables", "training zones",
        "how adaptation works", "weekly structure", "phase progression",
        "week-by-week overview", "workout execution", "recovery protocol",
        "equipment checklist", "nutrition strategy", "mental preparation",
        "race week", "race day",
    ]

    def _build_valid_guide(self, size_target=55_000):
        """Build a valid guide HTML that passes all Gate 7 checks."""
        sections = "\n".join(
            f"<h2>{s.title()}</h2><p>Detailed content for {s} section.</p>"
            for s in self.REQUIRED_SECTIONS
        )
        base = (
            "<html><body>"
            "<h1>SBT GRVL 100mi Training Guide</h1>"
            f"{sections}"
            "<p>traditional pyramidal plan</p>"
        )
        # Pad to reach size target with realistic content
        padding_needed = size_target - len(base) - 20
        if padding_needed > 0:
            base += "<p>" + ("Training content. " * (padding_needed // 18)) + "</p>"
        base += "</body></html>"
        return base

    def _write_guide(self, path, content):
        path.write_text(content, encoding="utf-8")

    def test_valid_guide_passes(self, tmp_path, valid_intake, valid_derived):
        guide = tmp_path / "guide.html"
        self._write_guide(guide, self._build_valid_guide())
        gate_7_guide(guide, valid_intake, valid_derived)

    def test_guide_too_small_fails(self, tmp_path, valid_intake, valid_derived):
        """Gate 7 requires 50KB+ — no weakening allowed."""
        guide = tmp_path / "guide.html"
        sections = "\n".join(
            f"<h2>{s.title()}</h2><p>Content.</p>"
            for s in self.REQUIRED_SECTIONS
        )
        html = (
            "<html><body>"
            "<h1>SBT GRVL 100mi Training Guide</h1>"
            f"{sections}"
            "<p>traditional pyramidal</p>"
            "</body></html>"
        )
        self._write_guide(guide, html)
        with pytest.raises(AssertionError, match="too small"):
            gate_7_guide(guide, valid_intake, valid_derived)

    def test_missing_section_fails(self, tmp_path, valid_intake, valid_derived):
        """Every one of the 14 required sections must be present."""
        guide = tmp_path / "guide.html"
        # Build with only 3 sections — missing the other 11
        html = (
            "<html><body>"
            "<h1>SBT GRVL 100mi Training Guide</h1>"
            "<h2>Training Zones</h2><p>Content.</p>"
            "<h2>Weekly Structure</h2><p>Content.</p>"
            "<h2>Race Day</h2><p>Content.</p>"
            "<p>traditional pyramidal</p>"
            + ("x" * 55000)
            + "</body></html>"
        )
        self._write_guide(guide, html)
        with pytest.raises(AssertionError, match="Missing required section"):
            gate_7_guide(guide, valid_intake, valid_derived)

    def test_unreplaced_placeholder_fails(self, tmp_path, valid_intake, valid_derived):
        guide = tmp_path / "guide.html"
        html = self._build_valid_guide().replace(
            "SBT GRVL 100mi", "SBT GRVL 100mi {{athlete_name}}"
        )
        self._write_guide(guide, html)
        with pytest.raises(AssertionError, match="placeholder"):
            gate_7_guide(guide, valid_intake, valid_derived)

    def test_null_text_fails(self, tmp_path, valid_intake, valid_derived):
        guide = tmp_path / "guide.html"
        html = self._build_valid_guide().replace(
            "</body>", "<p> None </p></body>"
        )
        self._write_guide(guide, html)
        with pytest.raises(AssertionError, match="None"):
            gate_7_guide(guide, valid_intake, valid_derived)

    def test_missing_distance_fails(self, tmp_path, valid_intake, valid_derived):
        """Guide must mention the race distance."""
        guide = tmp_path / "guide.html"
        html = self._build_valid_guide().replace("100", "XXX")
        self._write_guide(guide, html)
        with pytest.raises(AssertionError, match="distance"):
            gate_7_guide(guide, valid_intake, valid_derived)

    def test_missing_race_name_fails(self, tmp_path, valid_intake, valid_derived):
        """Guide must mention the race name."""
        guide = tmp_path / "guide.html"
        html = self._build_valid_guide().replace("SBT GRVL", "SOME RACE")
        self._write_guide(guide, html)
        with pytest.raises(AssertionError, match="race"):
            gate_7_guide(guide, valid_intake, valid_derived)


# ── Gate 8 Tests ─────────────────────────────────────────────

class TestGate8:
    def test_missing_pdf_fails(self, tmp_path):
        with pytest.raises(AssertionError, match="not created"):
            gate_8_pdf(tmp_path / "missing.pdf")

    def test_tiny_pdf_fails(self, tmp_path):
        pdf = tmp_path / "guide.pdf"
        pdf.write_bytes(b"tiny")
        with pytest.raises(AssertionError, match="too small"):
            gate_8_pdf(pdf)
