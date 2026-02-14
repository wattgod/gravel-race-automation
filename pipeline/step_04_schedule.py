"""
Step 4: Build Weekly Schedule

Maps questionnaire schedule fields to a weekly training structure.
Adapted from athlete-profiles/athletes/scripts/build_weekly_structure.py
"""

from typing import Dict

ALL_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def build_schedule(profile: Dict, derived: Dict) -> Dict:
    """
    Build weekly training structure from profile schedule preferences.

    Uses the questionnaire checkbox fields:
    - long_ride_days → long ride sessions
    - interval_days → interval/key sessions
    - off_days → rest days
    - remaining → easy/recovery rides
    - strength days: 1-2 non-key days if strength_include == "yes"
    """
    schedule = profile["schedule"]
    long_ride_days = [d.lower() for d in schedule.get("long_ride_days", [])]
    interval_days = [d.lower() for d in schedule.get("interval_days", [])]
    off_days = [d.lower() for d in schedule.get("off_days", [])]

    include_strength = profile["strength"].get("include_in_plan") == "yes"
    tier = derived["tier"]

    week = {}

    for day in ALL_DAYS:
        if day in off_days:
            week[day] = {"session": "rest", "notes": "Off day (athlete-specified)"}
        elif day in long_ride_days:
            week[day] = {"session": "long_ride", "notes": "Long ride day"}
        elif day in interval_days:
            week[day] = {"session": "intervals", "notes": "Interval / key session"}
        else:
            week[day] = {"session": "easy_ride", "notes": "Easy / recovery ride"}

    # Assign strength days (pick 1-2 from easy_ride days, not key days)
    if include_strength:
        strength_candidates = [
            d for d in ALL_DAYS
            if week[d]["session"] == "easy_ride"
        ]
        # Prefer non-adjacent-to-interval days for recovery
        strength_count = 2 if tier in ["time_crunched", "finisher"] else 1
        assigned = 0
        for day in strength_candidates:
            if assigned >= strength_count:
                break
            # Avoid the day before an interval day
            day_idx = ALL_DAYS.index(day)
            next_day = ALL_DAYS[(day_idx + 1) % 7]
            if next_day in interval_days:
                continue
            week[day]["session"] = "strength"
            week[day]["notes"] = "Strength session"
            assigned += 1

        # If we couldn't avoid adjacent days, just assign anyway
        if assigned < strength_count:
            for day in strength_candidates:
                if assigned >= strength_count:
                    break
                if week[day]["session"] == "easy_ride":
                    week[day]["session"] = "strength"
                    week[day]["notes"] = "Strength session"
                    assigned += 1

    return {
        "description": f"Custom weekly structure for {tier} tier",
        "tier": tier,
        "days": week,
    }
