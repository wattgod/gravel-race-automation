"""
Garmin device step limit for generated ZWO workouts.

Garmin head units play only the first 50 steps of a structured workout and
silently drop the rest (verified 2026-09-29 from recorded files: 61 flat steps
recorded exactly 50 laps and ended mid-set; workouts stored with repeat blocks
played in full). Device steps = every leaf once plus one marker per repeat
group, so an <IntervalsT> costs 3 steps whatever its Repeat count.

These tests guard:
- the step-counting rule
- step 6 refusing to write any workout that needs more than 50 steps
- scripts/zwo_tp_validator.py failing any file over 50 steps
- every template in the catalogue staying under the limit
"""

import contextlib
import io
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import pytest

from pipeline.step_05_template import SAVE_MY_RACE_MAP, TEMPLATE_MAP, select_template
from pipeline.step_06_workouts import (
    GARMIN_MAX_DEVICE_STEPS,
    DeviceStepLimitError,
    _write_zwo,
    device_step_count,
    device_steps_for_blocks,
    generate_workouts,
)

import zwo_tp_validator

BASE_DIR = Path(__file__).parent.parent
PLAN_START = date(2027, 1, 4)  # a Monday


# ── fixtures ─────────────────────────────────────────────────


def _steady(duration, power):
    return f'    <SteadyState Duration="{duration}" Power="{power}"/>\n'


WARMUP = '    <Warmup Duration="600" PowerLow="0.45" PowerHigh="0.70"/>\n'
COOLDOWN = '    <Cooldown Duration="600" PowerLow="0.60" PowerHigh="0.40"/>\n'

# A warm-up plus 30 bare on/off pairs: 61 flat steps, the shape of the
# workout that recorded exactly 50 laps and ended mid-set.
FLAT_61 = WARMUP + (_steady(30, "1.20") + _steady(30, "0.50")) * 30

# The same session stored as a repeat block: 1 + 3 + 1 = 5 device steps.
GROUPED_5 = (WARMUP
             + '    <IntervalsT Repeat="30" OnDuration="30" OnPower="1.20" '
               'OffDuration="30" OffPower="0.50"/>\n'
             + COOLDOWN)


def _one_week_plan(blocks: str, name: str):
    """A one-week synthetic plan with a single template workout on Tuesday."""
    plan_config = {
        "template": {
            "plan_metadata": {"target_hours": "6-8"},
            "weeks": [{
                "week_number": 1,
                "volume_percent": 100,
                "focus": "Base",
                "workouts": [{"name": name, "description": "Test session.", "blocks": blocks}],
            }],
        },
        "plan_duration": 1,
        "ftp_test_weeks": [],
    }
    profile = {"fitness": {}, "health": {}}
    derived = {
        "weekly_hours": "6-8",  # equals template hours → no duration scaling
        "race_name": None,
        "race_distance_miles": 100,
        "race_date": (PLAN_START + timedelta(days=6)).isoformat(),
        "plan_start_date": PLAN_START.isoformat(),
    }
    schedule = {"days": {d: {"session": "rest"} for d in
                         ("monday", "wednesday", "thursday", "friday", "saturday", "sunday")}}
    schedule["days"]["tuesday"] = {"session": "intervals"}
    return plan_config, profile, derived, schedule


def _generate(tmp_path, plan):
    out = tmp_path / "workouts"
    out.mkdir()
    with contextlib.redirect_stdout(io.StringIO()):
        generate_workouts(*plan, out, BASE_DIR)
    return out


def _write_raw_zwo(path: Path, blocks: str):
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<workout_file>\n'
        "    <author>Test</author>\n    <name>W01 2Tue Jan05 - Test</name>\n"
        "    <description>Test workout.</description>\n    <sportType>bike</sportType>\n"
        f"    <workout>\n{blocks}    </workout>\n</workout_file>",
        encoding="utf-8",
    )


def _step_issues(workouts_dir: Path):
    return [i for i in zwo_tp_validator.validate_zwo_for_tp(workouts_dir)
            if i.pitfall == "DEVICE_STEP_LIMIT"]


# ── the counting rule ────────────────────────────────────────


class TestDeviceStepCount:

    def test_limit_is_fifty(self):
        assert GARMIN_MAX_DEVICE_STEPS == 50

    def test_intervals_t_costs_three_whatever_the_repeat(self):
        for repeat in (1, 2, 30, 200):
            blocks = (f'<IntervalsT Repeat="{repeat}" OnDuration="30" OnPower="1.20" '
                      f'OffDuration="30" OffPower="0.50"/>')
            assert device_steps_for_blocks(blocks) == 3

    def test_every_other_element_costs_one(self):
        blocks = (WARMUP + _steady(300, "0.75")
                  + '    <Ramp Duration="300" PowerLow="0.6" PowerHigh="0.9"/>\n'
                  + '    <FreeRide Duration="600" FlatRoad="1"/>\n' + COOLDOWN)
        assert device_steps_for_blocks(blocks) == 5

    def test_flat_set_costs_one_per_element_and_grouped_set_does_not(self):
        assert device_steps_for_blocks(FLAT_61) == 61
        assert device_steps_for_blocks(GROUPED_5) == 5

    def test_validator_uses_the_generator_rule(self):
        assert zwo_tp_validator.device_step_count is device_step_count
        assert zwo_tp_validator.GARMIN_MAX_DEVICE_STEPS == GARMIN_MAX_DEVICE_STEPS


# ── generator guard ──────────────────────────────────────────


class TestGeneratorStepCap:

    def test_61_step_workout_fails_generation(self, tmp_path):
        """Regression: a 61-flat-step workout must never be written."""
        plan = _one_week_plan(FLAT_61, name="W01 Tue - Threshold 30/30s")
        with pytest.raises(DeviceStepLimitError) as exc:
            _generate(tmp_path, plan)
        msg = str(exc.value)
        assert "W01_2Tue_Jan05_Threshold.zwo" in msg  # names the file
        assert "61 device steps" in msg
        assert "50" in msg
        assert not list((tmp_path / "workouts").glob("*Threshold*.zwo")), \
            "a refused workout must not be left on disk"

    def test_same_session_as_intervals_t_is_written(self, tmp_path):
        plan = _one_week_plan(GROUPED_5, name="W01 Tue - Threshold 30/30s")
        out = _generate(tmp_path, plan)
        (zwo,) = list(out.glob("*Threshold*.zwo"))
        assert device_step_count(ET.parse(zwo).getroot().find("workout")) == 5
        assert not _step_issues(out)

    def test_direct_write_refuses_over_limit(self, tmp_path):
        with pytest.raises(DeviceStepLimitError, match=r"W09_2Tue_Mar02_Flat\.zwo: .*61 device steps"):
            _write_zwo(tmp_path, "W09_2Tue_Mar02_Flat.zwo", "n", "d", FLAT_61)
        assert not (tmp_path / "W09_2Tue_Mar02_Flat.zwo").exists()

    def test_exactly_fifty_steps_is_allowed(self, tmp_path):
        fifty = "".join(_steady(60, f"{0.50 + i * 0.01:.2f}") for i in range(50))
        _write_zwo(tmp_path, "W01_2Tue_Jan05_Fifty.zwo", "n", "d", fifty)
        assert (tmp_path / "W01_2Tue_Jan05_Fifty.zwo").exists()

    def test_fifty_one_steps_is_refused(self, tmp_path):
        fifty_one = "".join(_steady(60, f"{0.50 + i * 0.01:.2f}") for i in range(51))
        with pytest.raises(DeviceStepLimitError, match="51 device steps"):
            _write_zwo(tmp_path, "W01_2Tue_Jan05_FiftyOne.zwo", "n", "d", fifty_one)


# ── validator ────────────────────────────────────────────────


class TestValidatorStepCap:

    def test_over_limit_file_fails_with_name_and_count(self, tmp_path):
        _write_raw_zwo(tmp_path / "W01_2Tue_Jan05_Flat_Set.zwo", FLAT_61)
        issues = _step_issues(tmp_path)
        assert len(issues) == 1
        assert issues[0].file == "W01_2Tue_Jan05_Flat_Set.zwo"
        assert "FAIL" in issues[0].detail
        assert "W01_2Tue_Jan05_Flat_Set.zwo" in issues[0].detail
        assert "61 device steps" in issues[0].detail

    def test_intervals_t_version_passes(self, tmp_path):
        _write_raw_zwo(tmp_path / "W01_2Tue_Jan05_Grouped.zwo", GROUPED_5)
        assert not _step_issues(tmp_path)

    def test_cli_exits_nonzero_and_names_file(self, tmp_path):
        _write_raw_zwo(tmp_path / "W01_2Tue_Jan05_Flat_Set.zwo", FLAT_61)
        result = subprocess.run(
            [sys.executable, str(BASE_DIR / "scripts" / "zwo_tp_validator.py"), str(tmp_path)],
            capture_output=True, text=True, cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "DEVICE_STEP_LIMIT" in result.stdout
        assert "W01_2Tue_Jan05_Flat_Set.zwo needs 61 device steps" in result.stdout


# ── whole catalogue ──────────────────────────────────────────


def _catalogue():
    for tier, level in TEMPLATE_MAP:
        yield tier, level, 24  # longest plan: every extension week
    for tier in SAVE_MY_RACE_MAP:
        level = next(lv for t, lv in TEMPLATE_MAP if t == tier)
        yield tier, level, 8   # ≤ 8 weeks selects the Save My Race template


@pytest.mark.parametrize("tier,level,plan_weeks", list(_catalogue()))
def test_catalogue_stays_under_device_step_limit(tmp_path, tier, level, plan_weeks):
    derived = {"tier": tier, "level": level, "plan_weeks": plan_weeks,
               "plan_duration": plan_weeks, "recovery_week_cadence": 4}
    plan_config = select_template(derived, BASE_DIR)
    duration = plan_config["plan_duration"]
    derived.update({
        "plan_duration": duration,
        "race_name": None,
        "race_distance_miles": 100,
        "weekly_hours": plan_config["template"].get("plan_metadata", {}).get("target_hours", ""),
        "race_date": (PLAN_START + timedelta(weeks=duration) - timedelta(days=1)).isoformat(),
        "plan_start_date": PLAN_START.isoformat(),
    })
    # Riding every day so each template workout reaches the generator.
    sessions = ["easy_ride", "intervals", "intervals", "intervals",
                "easy_ride", "long_ride", "long_ride"]
    schedule = {"days": {d: {"session": s} for d, s in zip(
        ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"),
        sessions)}}
    profile = {"fitness": {}, "health": {}}
    out = _generate(tmp_path, (plan_config, profile, derived, schedule))

    files = list(out.glob("*.zwo"))
    assert files
    for f in files:
        wk = ET.parse(f).getroot().find("workout")
        assert device_step_count(wk) <= GARMIN_MAX_DEVICE_STEPS, f.name
    assert not _step_issues(out)
