"""
Sanity tests for duration-scaled nutrition calculations.

These tests exist because the old code gave Sarah Printz (135 lbs, 100-mile
SBT GRVL, ~8hr estimated duration) a flat 90g/hr recommendation. The
duration-scaled framework from gravel-god-nutrition says that's too high
for an 8-hour effort where fat oxidation is increasing and GI risk is
climbing. Correct range: 50-70g/hr.

Source of truth: gravel-god-nutrition (wattgod/gravel-god-nutrition)
Research: Jeukendrup (2014), van Loon et al. (2001), GSSI.
"""

import pytest
from pipeline.nutrition import (
    DURATION_BRACKETS,
    SPEED_BRACKETS,
    compute_fueling,
    compute_fueling_for_guide,
    estimate_speed,
)


# ── Speed estimation ────────────────────────────────────────


class TestEstimateSpeed:
    def test_short_race(self):
        assert estimate_speed(30) == 14

    def test_50_mile_boundary(self):
        assert estimate_speed(50) == 14

    def test_mid_distance(self):
        assert estimate_speed(75) == 12

    def test_100_mile_boundary(self):
        assert estimate_speed(100) == 12

    def test_ultra(self):
        assert estimate_speed(120) == 11

    def test_mega_ultra(self):
        assert estimate_speed(200) == 10

    def test_extreme(self):
        assert estimate_speed(350) == 10


# ── Core fueling calculation ────────────────────────────────


class TestComputeFueling:
    """Test the duration-scaled fueling calculator."""

    def test_sarah_printz_100mi(self):
        """Sarah: 100 miles, ~8.3hrs estimated → should NOT be 90g/hr.
        Duration bracket: 4-8hr = 60-80g/hr."""
        result = compute_fueling(100)
        assert result["hours"] == pytest.approx(8.3, abs=0.1)
        # THE critical assertion: NOT 90g/hr
        assert result["carb_rate_hi"] <= 80
        assert result["carb_rate_lo"] >= 50

    def test_sarah_with_race_duration(self):
        """Sarah's actual race data: duration_estimate '6-10 hours' → avg 8hr."""
        result = compute_fueling(100, duration_hours=8.0)
        assert result["carb_rate_lo"] == 60
        assert result["carb_rate_hi"] == 80

    def test_50_mile_race(self):
        """50 miles at 14mph = ~3.6hrs → 2-4hr bracket = 80-100g/hr."""
        result = compute_fueling(50)
        assert result["carb_rate_lo"] == 80
        assert result["carb_rate_hi"] == 100

    def test_200_mile_race(self):
        """200 miles at 10mph = 20hrs → 16+ bracket = 30-50g/hr."""
        result = compute_fueling(200)
        assert result["carb_rate_lo"] == 30
        assert result["carb_rate_hi"] == 50

    def test_142_mile_race(self):
        """142 miles at 11mph = ~12.9hrs → 12-16hr bracket = 40-60g/hr."""
        result = compute_fueling(142)
        assert result["carb_rate_lo"] == 40
        assert result["carb_rate_hi"] == 60

    def test_total_carbs_calculated(self):
        """Total carbs should be in the right ballpark (hours * rate).
        Allow +-1 for rounding (hours is rounded for display)."""
        result = compute_fueling(100)  # ~8.3hrs → 8-12hr bracket = 50-70g/hr
        expected_lo = result["hours"] * result["carb_rate_lo"]
        expected_hi = result["hours"] * result["carb_rate_hi"]
        assert abs(result["carbs_total_lo"] - expected_lo) <= 2
        assert abs(result["carbs_total_hi"] - expected_hi) <= 2

    def test_gels_calculated(self):
        """Gels = total_carbs // 25."""
        result = compute_fueling(100)
        assert result["gels_lo"] == result["carbs_total_lo"] // 25
        assert result["gels_hi"] == result["carbs_total_hi"] // 25

    def test_explicit_duration_overrides_estimate(self):
        """If duration_hours given, don't estimate from distance."""
        result = compute_fueling(100, duration_hours=3.0)
        # 3 hours → 2-4hr bracket = 80-100g/hr (not the 60-80 from distance-estimated 8.3hrs)
        assert result["carb_rate_lo"] == 80
        assert result["carb_rate_hi"] == 100
        assert result["hours"] == 3.0


# ── Sanity invariants ───────────────────────────────────────


class TestNutritionSanity:
    """Invariants that must NEVER be violated regardless of inputs."""

    def test_no_athlete_gets_above_120g_hr(self):
        """Max possible rate is 100g/hr (2-4hr bracket high end)."""
        for distance in [20, 50, 100, 150, 200, 300]:
            result = compute_fueling(distance)
            assert result["carb_rate_hi"] <= 100, (
                f"Distance {distance}mi: {result['carb_rate_hi']}g/hr exceeds physiological ceiling"
            )

    def test_no_athlete_gets_below_30g_hr(self):
        """Min possible rate is 30g/hr (16+ hr bracket low end)."""
        for distance in [20, 50, 100, 150, 200, 300]:
            result = compute_fueling(distance)
            assert result["carb_rate_lo"] >= 30, (
                f"Distance {distance}mi: {result['carb_rate_lo']}g/hr below minimum"
            )

    def test_carb_rate_decreases_with_duration(self):
        """As duration increases, carb rate should decrease or stay the same.
        This is the core insight of the duration-scaled framework."""
        prev_hi = 999
        for max_hours, lo, hi, label, gt_weeks in DURATION_BRACKETS:
            assert hi <= prev_hi, (
                f"Bracket '{label}' has higher carb rate ({hi}) than shorter bracket ({prev_hi}). "
                f"Duration-scaled fueling means LESS carbs at longer durations."
            )
            prev_hi = hi

    def test_brackets_are_complete(self):
        """Every possible duration maps to a bracket."""
        for hours in [1, 2, 4, 6, 8, 10, 12, 14, 16, 20, 30, 50]:
            result = compute_fueling(100, duration_hours=hours)
            assert result["carb_rate_lo"] > 0
            assert result["carb_rate_hi"] > result["carb_rate_lo"]
            assert result["label"]  # has a bracket label

    def test_total_carbs_positive(self):
        """Total carbs must always be positive for real distances."""
        for distance in [30, 50, 100, 200]:
            result = compute_fueling(distance)
            assert result["carbs_total_lo"] > 0
            assert result["carbs_total_hi"] > result["carbs_total_lo"]

    def test_gut_training_weeks_scale_with_duration(self):
        """Longer events need more gut training lead time."""
        short = compute_fueling(50)  # ~3.6hrs
        long = compute_fueling(200)  # ~20hrs
        assert long["gut_training_weeks"] >= short["gut_training_weeks"]


# ── Boundary conditions ─────────────────────────────────────


class TestBoundaryConditions:
    def test_exactly_4_hours(self):
        """4 hours is the boundary between 80-100 and 60-80 brackets."""
        result = compute_fueling(100, duration_hours=4.0)
        assert result["carb_rate_lo"] == 80
        assert result["carb_rate_hi"] == 100

    def test_just_over_4_hours(self):
        result = compute_fueling(100, duration_hours=4.1)
        assert result["carb_rate_lo"] == 60
        assert result["carb_rate_hi"] == 80

    def test_exactly_8_hours(self):
        result = compute_fueling(100, duration_hours=8.0)
        assert result["carb_rate_lo"] == 60
        assert result["carb_rate_hi"] == 80

    def test_just_over_8_hours(self):
        result = compute_fueling(100, duration_hours=8.1)
        assert result["carb_rate_lo"] == 50
        assert result["carb_rate_hi"] == 70

    def test_exactly_12_hours(self):
        result = compute_fueling(100, duration_hours=12.0)
        assert result["carb_rate_lo"] == 50
        assert result["carb_rate_hi"] == 70

    def test_just_over_12_hours(self):
        result = compute_fueling(100, duration_hours=12.1)
        assert result["carb_rate_lo"] == 40
        assert result["carb_rate_hi"] == 60


# ── Guide integration ───────────────────────────────────────


class TestComputeFuelingForGuide:
    """Test the guide-facing wrapper that parses race_data."""

    @pytest.fixture
    def sarah_profile(self):
        return {
            "demographics": {
                "sex": "female",
                "age": 44,
                "weight_lbs": 135,
            }
        }

    @pytest.fixture
    def sbt_grvl_100(self):
        return {
            "duration_estimate": "6-10 hours",
            "race_metadata": {
                "name": "SBT GRVL",
                "start_elevation_feet": 6732,
            },
        }

    def test_sarah_gets_duration_scaled_not_90(self, sarah_profile, sbt_grvl_100):
        """THE regression test. Sarah must NOT get 90g/hr."""
        result = compute_fueling_for_guide(100, sbt_grvl_100, sarah_profile)
        assert result["carb_rate_hi"] <= 80, (
            f"Sarah (135lb, 100mi, 6-10hr) got {result['carb_rate_hi']}g/hr. "
            f"Duration-scaled framework says max 80g/hr for this duration."
        )

    def test_sarah_weight_derived_targets(self, sarah_profile, sbt_grvl_100):
        """Sarah's daily carb targets should be based on her 61kg body weight."""
        result = compute_fueling_for_guide(100, sbt_grvl_100, sarah_profile)
        assert result["weight_kg"] == pytest.approx(61.2, abs=0.5)
        # 6g/kg * 61.2 = 367, 7g/kg * 61.2 = 428
        assert 360 <= result["daily_carb_lo"] <= 370
        assert 420 <= result["daily_carb_hi"] <= 435

    def test_duration_parsed_from_race_data(self, sarah_profile, sbt_grvl_100):
        """'6-10 hours' should parse to avg 8 hours."""
        result = compute_fueling_for_guide(100, sbt_grvl_100, sarah_profile)
        assert result["hours"] == 8.0

    def test_fallback_when_no_duration(self, sarah_profile):
        """Without duration_estimate, estimate from distance.
        100mi / 12mph = 8.33hrs → 8-12hr bracket = 50-70g/hr."""
        result = compute_fueling_for_guide(100, {}, sarah_profile)
        assert result["carb_rate_lo"] == 50
        assert result["carb_rate_hi"] == 70

    def test_no_profile(self):
        """Works without profile (no weight-derived targets)."""
        result = compute_fueling_for_guide(100, {"duration_estimate": "8-10 hours"})
        assert result["carb_rate_lo"] > 0
        assert "weight_kg" not in result

    def test_none_race_data(self, sarah_profile):
        """Handles None race_data without crashing."""
        result = compute_fueling_for_guide(100, None, sarah_profile)
        assert result["carb_rate_lo"] > 0

    def test_short_race_high_carbs(self, sarah_profile):
        """37-mile race → ~2.6hrs → 80-100g/hr."""
        race = {"duration_estimate": "2-4 hours"}
        result = compute_fueling_for_guide(37, race, sarah_profile)
        assert result["carb_rate_lo"] == 80
        assert result["carb_rate_hi"] == 100


# ── Speed bracket sanity ────────────────────────────────────


class TestSpeedBrackets:
    def test_brackets_sorted(self):
        """Speed brackets must be sorted ascending by max_distance."""
        prev = 0
        for max_dist, _ in SPEED_BRACKETS:
            assert max_dist > prev
            prev = max_dist

    def test_speed_decreases_with_distance(self):
        """Longer races are slower (includes stops, fatigue)."""
        prev_speed = 999
        for _, speed in SPEED_BRACKETS:
            assert speed <= prev_speed
            prev_speed = speed
