"""Tests for Step 3: Classification."""

import pytest
from pipeline.step_03_classify import classify_athlete, TIER_MAP, LEVEL_MAP


def _make_profile(weekly_hours="5-7", years_cycling="3-5 years", age=44, race_date="2026-06-28"):
    return {
        "name": "Test",
        "email": "test@example.com",
        "demographics": {"sex": "female", "age": age},
        "race_calendar": [{"name": "SBT GRVL", "date": race_date, "distance_miles": 100}],
        "primary_race": {"name": "SBT GRVL", "date": race_date, "distance_miles": 100},
        "fitness": {},
        "schedule": {"weekly_hours": weekly_hours},
        "training_history": {"years_cycling": years_cycling},
        "strength": {},
        "health": {},
    }


class TestTierDerivation:
    def test_time_crunched(self):
        derived = classify_athlete(_make_profile(weekly_hours="3-5"))
        assert derived["tier"] == "time_crunched"

    def test_finisher_low(self):
        derived = classify_athlete(_make_profile(weekly_hours="5-7"))
        assert derived["tier"] == "finisher"

    def test_finisher_high(self):
        derived = classify_athlete(_make_profile(weekly_hours="7-10"))
        assert derived["tier"] == "finisher"

    def test_compete_low(self):
        derived = classify_athlete(_make_profile(weekly_hours="10-12"))
        assert derived["tier"] == "compete"

    def test_compete_high(self):
        derived = classify_athlete(_make_profile(weekly_hours="12-15"))
        assert derived["tier"] == "compete"

    def test_podium(self):
        derived = classify_athlete(_make_profile(weekly_hours="15+"))
        assert derived["tier"] == "podium"


class TestLevelDerivation:
    def test_beginner(self):
        derived = classify_athlete(_make_profile(years_cycling="<1 year"))
        assert derived["level"] == "beginner"

    def test_intermediate(self):
        derived = classify_athlete(_make_profile(years_cycling="3-5 years"))
        assert derived["level"] == "intermediate"

    def test_advanced_downgraded_for_finisher(self):
        """Advanced + finisher tier → intermediate (goal is just finish)."""
        derived = classify_athlete(_make_profile(years_cycling="10+ years", weekly_hours="5-7"))
        assert derived["tier"] == "finisher"
        assert derived["level"] == "intermediate"

    def test_masters_override(self):
        derived = classify_athlete(_make_profile(age=55))
        assert derived["level"] == "masters"
        assert derived["is_masters"] is True


class TestPlanWeeks:
    def test_plan_duration_equals_plan_weeks(self):
        """No bucketing — plan_duration should equal plan_weeks."""
        from datetime import date, timedelta
        for weeks_out in [9, 13, 15, 18, 19, 22]:
            future_date = (date.today() + timedelta(weeks=weeks_out)).strftime("%Y-%m-%d")
            derived = classify_athlete(_make_profile(race_date=future_date))
            assert derived["plan_duration"] == derived["plan_weeks"], (
                f"plan_duration ({derived['plan_duration']}) != plan_weeks ({derived['plan_weeks']}) "
                f"for {weeks_out} weeks out. No bucketing — use every week."
            )

    def test_plan_weeks_clamped_to_range(self):
        """plan_weeks must be in [8, 24] regardless of actual time to race."""
        from datetime import date, timedelta
        # Very far out → capped at 24
        far_date = (date.today() + timedelta(weeks=50)).strftime("%Y-%m-%d")
        derived = classify_athlete(_make_profile(race_date=far_date))
        assert derived["plan_weeks"] <= 24
        assert derived["plan_duration"] <= 24


class TestPlanStartDate:
    def test_plan_start_date_present(self):
        """plan_start_date must always be in derived output."""
        derived = classify_athlete(_make_profile())
        assert "plan_start_date" in derived
        assert derived["plan_start_date"]  # not empty

    def test_plan_start_date_is_today(self):
        """plan_start_date must be the day the plan was requested — today."""
        from datetime import date, datetime
        derived = classify_athlete(_make_profile())
        start = datetime.strptime(derived["plan_start_date"], "%Y-%m-%d").date()
        assert start == date.today(), (
            f"plan_start_date should be today ({date.today()}) but got {start}. "
            f"Plan starts the day the athlete submits, not next Monday."
        )

    def test_plan_start_date_format(self):
        """plan_start_date must be YYYY-MM-DD format."""
        derived = classify_athlete(_make_profile())
        from datetime import datetime
        # Will raise ValueError if format is wrong
        datetime.strptime(derived["plan_start_date"], "%Y-%m-%d")

    def test_race_day_falls_in_final_week(self):
        """Race day must fall within the final week of the plan."""
        from datetime import date, datetime, timedelta
        for weeks_out in [9, 13, 15, 18, 19, 22]:
            future_date = (date.today() + timedelta(weeks=weeks_out)).strftime("%Y-%m-%d")
            derived = classify_athlete(_make_profile(race_date=future_date))
            start = datetime.strptime(derived["plan_start_date"], "%Y-%m-%d").date()
            race = datetime.strptime(future_date, "%Y-%m-%d").date()
            plan_end = start + timedelta(weeks=derived["plan_duration"]) - timedelta(days=1)
            last_week_start = start + timedelta(weeks=derived["plan_duration"] - 1)
            assert last_week_start <= race <= plan_end, (
                f"Race {race} not in final week ({last_week_start} to {plan_end}) "
                f"for {weeks_out} weeks out. plan_duration={derived['plan_duration']}"
            )


class TestSarahPrintz:
    """Integration test using Sarah's actual data."""

    def test_full_classification(self):
        from pipeline.step_02_profile import create_profile

        intake = {
            "name": "Sarah Printz",
            "email": "sarah_printz@yahoo.com",
            "sex": "female",
            "age": 44,
            "weight_lbs": 135,
            "height_ft": 5,
            "height_in": 10,
            "years_cycling": "3-5 years",
            "sleep": "good",
            "stress": "moderate",
            "races": [{"name": "SBT GRVL", "date": "2026-06-28", "distance_miles": 100, "priority": "A"}],
            "longest_ride": "2-4",
            "ftp": None,
            "max_hr": None,
            "weekly_hours": "5-7",
            "trainer_access": "yes-basic",
            "long_ride_days": ["saturday", "sunday"],
            "interval_days": ["tuesday", "thursday"],
            "off_days": ["wednesday"],
            "strength_current": "regular",
            "strength_include": "yes",
            "strength_equipment": "full-gym",
            "injuries": "NA",
        }

        profile = create_profile(intake)
        derived = classify_athlete(profile)

        assert derived["tier"] == "finisher"
        assert derived["level"] == "intermediate"
        assert derived["race_name"] == "SBT GRVL"
        assert derived["race_distance_miles"] == 100
        assert derived["recovery_week_cadence"] == 3, (
            f"Sarah is 44 — recovery_week_cadence should be 3, got {derived['recovery_week_cadence']}"
        )


class TestRecoveryWeekCadence:
    def test_young_athlete_gets_4_week_cadence(self):
        derived = classify_athlete(_make_profile(age=30))
        assert derived["recovery_week_cadence"] == 4

    def test_39_year_old_gets_4_week_cadence(self):
        derived = classify_athlete(_make_profile(age=39))
        assert derived["recovery_week_cadence"] == 4

    def test_40_year_old_gets_3_week_cadence(self):
        derived = classify_athlete(_make_profile(age=40))
        assert derived["recovery_week_cadence"] == 3

    def test_44_year_old_gets_3_week_cadence(self):
        derived = classify_athlete(_make_profile(age=44))
        assert derived["recovery_week_cadence"] == 3

    def test_55_year_old_gets_3_week_cadence(self):
        derived = classify_athlete(_make_profile(age=55))
        assert derived["recovery_week_cadence"] == 3
