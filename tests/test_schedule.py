"""Tests for Step 4: Build Schedule."""

import pytest
from pipeline.step_04_schedule import build_schedule


def _make_profile_and_derived(
    long_ride_days=None,
    interval_days=None,
    off_days=None,
    include_strength="yes",
    tier="finisher",
):
    profile = {
        "schedule": {
            "weekly_hours": "5-7",
            "long_ride_days": long_ride_days or ["saturday"],
            "interval_days": interval_days or ["tuesday", "thursday"],
            "off_days": off_days or ["wednesday"],
        },
        "strength": {"include_in_plan": include_strength},
    }
    derived = {"tier": tier}
    return profile, derived


class TestBuildSchedule:
    def test_off_days_respected(self):
        profile, derived = _make_profile_and_derived(off_days=["wednesday", "friday"])
        schedule = build_schedule(profile, derived)
        assert schedule["days"]["wednesday"]["session"] == "rest"
        assert schedule["days"]["friday"]["session"] == "rest"

    def test_long_ride_days_assigned(self):
        profile, derived = _make_profile_and_derived(long_ride_days=["saturday", "sunday"])
        schedule = build_schedule(profile, derived)
        assert schedule["days"]["saturday"]["session"] == "long_ride"
        assert schedule["days"]["sunday"]["session"] == "long_ride"

    def test_interval_days_assigned(self):
        profile, derived = _make_profile_and_derived()
        schedule = build_schedule(profile, derived)
        assert schedule["days"]["tuesday"]["session"] == "intervals"
        assert schedule["days"]["thursday"]["session"] == "intervals"

    def test_minimum_training_days(self):
        profile, derived = _make_profile_and_derived()
        schedule = build_schedule(profile, derived)
        training = [d for d, v in schedule["days"].items() if v["session"] != "rest"]
        assert len(training) >= 3

    def test_strength_assigned_when_included(self):
        profile, derived = _make_profile_and_derived(include_strength="yes")
        schedule = build_schedule(profile, derived)
        strength_days = [d for d, v in schedule["days"].items() if v["session"] == "strength"]
        assert len(strength_days) >= 1

    def test_no_strength_when_excluded(self):
        profile, derived = _make_profile_and_derived(include_strength="no")
        schedule = build_schedule(profile, derived)
        strength_days = [d for d, v in schedule["days"].items() if v["session"] == "strength"]
        assert len(strength_days) == 0

    def test_sarah_printz_schedule(self):
        """Integration test with Sarah's actual preferences."""
        profile = {
            "schedule": {
                "weekly_hours": "5-7",
                "long_ride_days": ["saturday", "sunday"],
                "interval_days": ["tuesday", "thursday"],
                "off_days": ["wednesday"],
            },
            "strength": {"include_in_plan": "yes"},
        }
        derived = {"tier": "finisher"}

        schedule = build_schedule(profile, derived)
        days = schedule["days"]

        # Off day respected
        assert days["wednesday"]["session"] == "rest"
        # Long rides
        assert days["saturday"]["session"] == "long_ride"
        assert days["sunday"]["session"] == "long_ride"
        # Intervals
        assert days["tuesday"]["session"] == "intervals"
        assert days["thursday"]["session"] == "intervals"
