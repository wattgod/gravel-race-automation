"""
Duration-Scaled Fueling Calculator.

Ported from gravel-god-nutrition (wattgod/gravel-god-nutrition).
Computes deterministic carbohydrate targets from race distance + estimated
duration. No AI mediation — pure math from questionnaire data.

Source: docs/duration-scaled-fueling-for-gravel-racing.md
Research basis: Jeukendrup (2014), van Loon et al. (2001), GSSI, Precision Fuel.
"""

from typing import Dict, Optional


# Conservative average gravel speeds (mph, including stops).
# Sorted ascending by max_distance.
SPEED_BRACKETS = [
    (50, 14),    # <= 50 miles: shorter races, higher avg pace
    (100, 12),   # 51-100 miles: endurance pace with stops
    (150, 11),   # 101-150 miles: ultra territory
    (9999, 10),  # 150+ miles: survival pace
]

# Duration-scaled carb rate ranges (g/hr).
# Key insight: intensity drops with duration, shifting fuel mix toward fat.
# GI tolerance also degrades with duration. Both reduce optimal carb rate.
# Fields: (max_hours, carb_lo, carb_hi, label, gut_training_weeks)
DURATION_BRACKETS = [
    (4,  80, 100, "High-intensity race pace", 6),
    (8,  60, 80,  "Endurance pace", 8),
    (12, 50, 70,  "Sub-threshold — fat oxidation increasing", 10),
    (16, 40, 60,  "Ultra pace — fat is primary fuel", 12),
    (99, 30, 50,  "Survival pace — GI tolerance is the limiter", 12),
]


def estimate_speed(distance_mi: int) -> int:
    """Estimate average gravel speed (mph) from distance bracket."""
    for max_dist, speed in SPEED_BRACKETS:
        if distance_mi <= max_dist:
            return speed
    return 10


def compute_fueling(distance_mi: int, duration_hours: float = 0) -> dict:
    """Compute duration-scaled fueling targets for a gravel race.

    Args:
        distance_mi: Race distance in miles.
        duration_hours: Estimated duration in hours. If 0, estimated from distance.

    Returns:
        Dict with carb_rate_lo, carb_rate_hi, hours, label, gut_training_weeks,
        carbs_total_lo, carbs_total_hi, gels_lo, gels_hi.
    """
    if duration_hours <= 0:
        avg_mph = estimate_speed(distance_mi)
        duration_hours = distance_mi / avg_mph

    # Find the matching duration bracket
    carb_lo = carb_hi = 0
    label = ""
    gut_weeks = 8
    for max_hours, lo, hi, bracket_label, gt_weeks in DURATION_BRACKETS:
        carb_lo = lo
        carb_hi = hi
        label = bracket_label
        gut_weeks = gt_weeks
        if duration_hours <= max_hours:
            break

    carbs_total_lo = int(duration_hours * carb_lo)
    carbs_total_hi = int(duration_hours * carb_hi)
    gels_lo = carbs_total_lo // 25  # 1 gel = 25g carbs
    gels_hi = carbs_total_hi // 25

    return {
        "distance_mi": distance_mi,
        "hours": round(duration_hours, 1),
        "carb_rate_lo": carb_lo,
        "carb_rate_hi": carb_hi,
        "carbs_total_lo": carbs_total_lo,
        "carbs_total_hi": carbs_total_hi,
        "gels_lo": gels_lo,
        "gels_hi": gels_hi,
        "label": label,
        "gut_training_weeks": gut_weeks,
    }


def compute_fueling_for_guide(
    race_distance,
    race_data: Dict,
    profile: Optional[Dict] = None,
) -> dict:
    """Compute fueling targets from guide inputs. No AI — pure math.

    Uses duration_estimate from race_data if available, otherwise estimates
    from distance. Returns a dict ready for the guide template.
    """
    dist = int(race_distance) if race_distance else 0
    if dist < 20:
        return compute_fueling(dist)

    # Parse duration estimate from race data (e.g. "6-10 hours")
    duration_hours = 0
    duration_est = race_data.get("duration_estimate", "") if race_data else ""
    if duration_est and "-" in str(duration_est):
        parts = str(duration_est).replace("hours", "").replace("hour", "").strip().split("-")
        try:
            duration_hours = (float(parts[0].strip()) + float(parts[1].strip())) / 2
        except (ValueError, IndexError):
            duration_hours = 0

    result = compute_fueling(dist, duration_hours)

    # Add weight-derived daily targets if profile is available
    if profile:
        weight_lbs = profile.get("demographics", {}).get("weight_lbs")
        if weight_lbs:
            try:
                weight_kg = float(weight_lbs) / 2.205
                result["weight_kg"] = round(weight_kg, 1)
                result["weight_lbs"] = float(weight_lbs)
                result["daily_carb_lo"] = round(weight_kg * 6)
                result["daily_carb_hi"] = round(weight_kg * 7)
                result["long_ride_carb_lo"] = round(weight_kg * 8)
                result["long_ride_carb_hi"] = round(weight_kg * 10)
            except (ValueError, TypeError):
                pass

    return result
