"""
Step 2: Create Profile

Converts 7-section questionnaire data into a structured profile dict.
Adapted from athlete-profiles/athletes/scripts/create_profile_from_form.py
"""

from typing import Dict, Any, Optional


REQUIRED_SECTIONS = [
    "name",
    "email",
    "demographics",
    "race_calendar",
    "fitness",
    "schedule",
    "strength",
    "health",
]


def create_profile(intake: Dict) -> Dict:
    """
    Convert validated intake data to a structured athlete profile.
    Maps the 7-section questionnaire fields to a normalized profile.
    """
    # Primary race (first A-priority or first race)
    races = intake.get("races", [])
    primary_race = None
    for r in races:
        if r.get("priority", "A") == "A":
            primary_race = r
            break
    if not primary_race and races:
        primary_race = races[0]

    profile = {
        "name": intake["name"],
        "email": intake["email"],
        # Section 2: Demographics
        "demographics": {
            "sex": intake.get("sex"),
            "age": intake.get("age"),
            "weight_lbs": _safe_float(intake.get("weight_lbs")),
            "height_ft": _safe_int(intake.get("height_ft")),
            "height_in": _safe_int(intake.get("height_in")),
            "menstrual_status": intake.get("menstrual_status"),
            "track_cycle": intake.get("track_cycle"),
        },
        # Section 3: Race calendar
        "race_calendar": [
            {
                "name": r["name"],
                "date": r["date"],
                "distance_miles": r.get("distance_miles"),
                "priority": r.get("priority", "A"),
            }
            for r in races
        ],
        "primary_race": {
            "name": primary_race["name"] if primary_race else None,
            "date": primary_race["date"] if primary_race else None,
            "distance_miles": primary_race.get("distance_miles") if primary_race else None,
        },
        # Section 4: Fitness
        "fitness": {
            "longest_ride_hours": intake.get("longest_ride"),
            "training_modality": intake.get("training_modality"),
            "ftp_watts": _safe_int(intake.get("ftp")),
            "max_hr": _safe_int(intake.get("max_hr")),
            "lthr": _safe_int(intake.get("lthr")),
            "resting_hr": _safe_int(intake.get("resting_hr")),
        },
        # Section 5: Schedule
        "schedule": {
            "weekly_hours": intake.get("weekly_hours"),
            "long_ride_days": intake.get("long_ride_days", []),
            "interval_days": intake.get("interval_days", []),
            "off_days": intake.get("off_days", []),
            "travel_during_block": intake.get("travel"),
        },
        # Section 2 continued: Training history
        "training_history": {
            "years_cycling": intake.get("years_cycling"),
            "prior_plan_experience": intake.get("prior_plan_experience"),
        },
        # Section 6: Strength
        "strength": {
            "current_practice": intake.get("strength_current"),
            "include_in_plan": intake.get("strength_include"),
            "equipment": intake.get("strength_equipment"),
        },
        # Section 7: Health / injuries
        "health": {
            "sleep_quality": intake.get("sleep"),
            "stress_level": intake.get("stress"),
            "injuries_limitations": intake.get("injuries"),
        },
        # Equipment
        "equipment": {
            "trainer_type": intake.get("trainer_access"),
        },
        # Notes
        "notes": {
            "anything_else": intake.get("anything_else"),
        },
    }

    return profile


def _safe_int(val: Any) -> Optional[int]:
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
