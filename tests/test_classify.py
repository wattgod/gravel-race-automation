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
    def test_long_plan_gets_20_weeks(self):
        """Race far in the future should get 20-week plan."""
        from datetime import date, timedelta
        far_date = (date.today() + timedelta(weeks=22)).strftime("%Y-%m-%d")
        derived = classify_athlete(_make_profile(race_date=far_date))
        assert derived["plan_duration"] == 20

    def test_medium_plan_gets_16_weeks(self):
        """Race ~16 weeks out should get 16-week plan."""
        from datetime import date, timedelta
        med_date = (date.today() + timedelta(weeks=16)).strftime("%Y-%m-%d")
        derived = classify_athlete(_make_profile(race_date=med_date))
        assert derived["plan_duration"] == 16

    def test_short_plan_gets_12_weeks(self):
        """Race in 10 weeks → 12-week template."""
        from datetime import date, timedelta
        short_date = (date.today() + timedelta(weeks=10)).strftime("%Y-%m-%d")
        derived = classify_athlete(_make_profile(race_date=short_date))
        assert derived["plan_duration"] == 12


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
