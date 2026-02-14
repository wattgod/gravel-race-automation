"""
Step 3: Classify Athlete

Determines tier, level, plan_weeks, and plan_duration from profile.
Adapted from athlete-profiles/athletes/scripts/derive_classifications.py
"""

from datetime import datetime, timedelta, date
from typing import Dict

VALID_TIERS = ["time_crunched", "finisher", "compete", "podium"]
VALID_LEVELS = ["beginner", "intermediate", "advanced", "masters"]

# Map weekly_hours questionnaire value → tier
TIER_MAP = {
    "3-5": "time_crunched",
    "5-7": "finisher",
    "7-10": "finisher",
    "10-12": "compete",
    "12-15": "compete",
    "15+": "podium",
}

# Tier → valid weekly_hours values
TIER_HOURS = {
    "time_crunched": ["3-5"],
    "finisher": ["5-7", "7-10"],
    "compete": ["10-12", "12-15"],
    "podium": ["15+"],
}

# Map years_cycling → base level
LEVEL_MAP = {
    "<1 year": "beginner",
    "1-2 years": "beginner",
    "3-5 years": "intermediate",
    "5-10 years": "advanced",
    "10+ years": "advanced",
}


def classify_athlete(profile: Dict) -> Dict:
    """Derive tier, level, plan_weeks, and plan_duration from profile."""
    weekly_hours = profile["schedule"]["weekly_hours"]
    age = profile["demographics"].get("age")
    years_cycling = profile["training_history"].get("years_cycling", "1-2 years")

    # ── Tier derivation ──────────────────────────────────────
    tier = TIER_MAP.get(weekly_hours, "finisher")

    # Masters override: age 50+ with compete hours → compete (level will be masters)
    is_masters = age is not None and age >= 50

    # ── Level derivation ─────────────────────────────────────
    level = LEVEL_MAP.get(years_cycling, "intermediate")

    # Downgrade if goal is just to finish and level would be advanced
    primary_race = profile.get("primary_race", {})
    # For now, finisher tier implies finish goal
    if tier == "finisher" and level == "advanced":
        level = "intermediate"

    # Masters override
    if is_masters:
        level = "masters"

    # ── Plan weeks calculation ───────────────────────────────
    race_date_str = primary_race.get("date")
    if race_date_str:
        try:
            race_date = datetime.strptime(race_date_str, "%Y-%m-%d").date()
        except ValueError:
            race_date = None
    else:
        race_date = None

    if race_date:
        # Plan starts today — the day the athlete submits
        today = date.today()
        # +1 so race day falls IN the final week, not after
        weeks_to_race = (race_date - today).days // 7 + 1
        plan_weeks = min(24, max(8, weeks_to_race))
        plan_start_date = today.strftime("%Y-%m-%d")
    else:
        plan_weeks = 12
        plan_start_date = date.today().strftime("%Y-%m-%d")

    # plan_duration = plan_weeks — no bucketing, use every week the athlete has
    plan_duration = plan_weeks

    # Recovery cadence: every 3 weeks for 40+, every 4 weeks for younger
    recovery_week_cadence = 3 if (age is not None and age >= 40) else 4

    return {
        "tier": tier,
        "level": level,
        "weekly_hours": weekly_hours,
        "plan_weeks": plan_weeks,
        "plan_duration": plan_duration,
        "plan_start_date": plan_start_date,
        "is_masters": is_masters,
        "recovery_week_cadence": recovery_week_cadence,
        "race_name": primary_race.get("name"),
        "race_date": race_date_str,
        "race_distance_miles": primary_race.get("distance_miles"),
        "derived_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
