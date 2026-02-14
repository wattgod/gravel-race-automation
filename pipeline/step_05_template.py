"""
Step 5: Select + Extend Plan Template

Selects the correct 12-week base template for tier+level,
then extends to the athlete's exact plan duration if needed.
Adapted from gravel-plans-experimental/races/generate_expanded_race_plans.py
"""

import copy
import json
import re
from pathlib import Path
from typing import Dict

# Map (tier, level) → plan template directory name
TEMPLATE_MAP = {
    ("time_crunched", "beginner"): "1. Ayahuasca Beginner (12 weeks)",
    ("time_crunched", "intermediate"): "2. Ayahuasca Intermediate (12 weeks)",
    ("time_crunched", "masters"): "3. Ayahuasca Masters (12 weeks)",
    ("finisher", "beginner"): "5. Finisher Beginner (12 weeks)",
    ("finisher", "intermediate"): "6. Finisher Intermediate (12 weeks)",
    ("finisher", "advanced"): "7. Finisher Advanced (12 weeks)",
    ("finisher", "masters"): "8. Finisher Masters (12 weeks)",
    ("compete", "intermediate"): "10. Compete Intermediate (12 weeks)",
    ("compete", "advanced"): "11. Compete Advanced (12 weeks)",
    ("compete", "masters"): "12. Compete Masters (12 weeks)",
    ("podium", "advanced"): "14. Podium Advanced (12 weeks)",
    ("podium", "advanced_goat"): "15. Podium Advanced GOAT (12 weeks)",
}

# Save My Race variants for plans <= 8 weeks
SAVE_MY_RACE_MAP = {
    "time_crunched": "4. Ayahuasca Save My Race (6 weeks)",
    "finisher": "9. Finisher Save My Race (6 weeks)",
    "compete": "13. Compete Save My Race (6 weeks)",
}

def _compute_ftp_test_weeks(plan_duration: int) -> list:
    """Compute FTP test weeks for any plan duration. Test every 6 weeks, starting W1."""
    weeks = [1]
    w = 7
    while w <= plan_duration - 2:  # don't test in taper/race week
        weeks.append(w)
        w += 6
    return weeks


def select_template(derived: Dict, base_dir: Path) -> Dict:
    """
    Select and load the plan template, extending if needed.

    Returns dict with:
        - template: the full plan template (extended if needed)
        - template_key: (tier, level) tuple
        - plan_duration: target duration
        - extended: whether template was extended
    """
    tier = derived["tier"]
    level = derived["level"]
    plan_duration = derived["plan_duration"]
    plan_weeks = derived["plan_weeks"]

    template_key = (tier, level)

    # Use Save My Race for very short plans
    if plan_weeks <= 8 and tier in SAVE_MY_RACE_MAP:
        template_dir_name = SAVE_MY_RACE_MAP[tier]
        plan_duration = 6
    elif template_key not in TEMPLATE_MAP:
        raise ValueError(
            f"No template for tier={tier}, level={level}. "
            f"Valid combos: {list(TEMPLATE_MAP.keys())}"
        )
    else:
        template_dir_name = TEMPLATE_MAP[template_key]

    # Load template
    template_path = base_dir / "plans" / template_dir_name / "template.json"
    if not template_path.exists():
        raise FileNotFoundError(
            f"Template not found: {template_path}\n"
            f"Did you copy plan templates to plans/ directory?"
        )

    with open(template_path) as f:
        template = json.load(f)

    base_weeks = len(template.get("weeks", []))
    extended = False
    recovery_cadence = derived.get("recovery_week_cadence", 4)

    # Extend if needed
    if plan_duration > base_weeks:
        template = extend_plan_template(template, plan_duration, recovery_cadence=recovery_cadence)
        extended = True

    return {
        "template": template,
        "template_key": f"{tier}_{level}",
        "template_dir": template_dir_name,
        "plan_duration": plan_duration,
        "extended": extended,
        "ftp_test_weeks": _compute_ftp_test_weeks(plan_duration),
    }


# Focus text transforms for extended weeks — avoids confusing duplicates
# like "Build Phase Begins" appearing at both W5 and W9.
_FOCUS_TRANSFORMS = {
    # Original focus → replacement for repeated cycles
    "Build Phase Begins": "Continued Development",
    "Intensity Progression": "Intensity Consolidation",
    "Peak Build Volume": "Volume Consolidation",
    "Build Easy Volume": "Continued Volume Building",
    "Peak Base Volume": "Base Consolidation",
    "G-Spot Development": "G-Spot Progression",
    "Building HIIT Tolerance": "HIIT Consolidation",
    "Peak HIIT Volume": "HIIT Maintenance",
    "Polarized Volume Building": "Continued Polarized Volume",
    "Peak Base Volume with Polarization": "Polarized Consolidation",
    "Base Volume Building": "Continued Base Volume",
    "Peak Base Volume": "Base Consolidation",
}


def _transform_extended_focus(focus: str, cycle: int) -> str:
    """Transform focus text for extended template weeks to avoid confusing duplication."""
    if cycle == 0:
        # First repeat — use mapped text if available, otherwise keep original
        return _FOCUS_TRANSFORMS.get(focus, focus)
    # Second+ repeat — add cycle indicator
    base = _FOCUS_TRANSFORMS.get(focus, focus)
    return base


def extend_plan_template(base_template: Dict, target_weeks: int, recovery_cadence: int = 4) -> Dict:
    """
    Extend a 12-week plan template to any target duration.

    Strategy: duplicate base phase patterns to fill the gap,
    then keep the original build/peak/taper progression at the end.

    recovery_cadence: 3 for masters/40+ athletes, 4 for standard.
    Controls how often recovery weeks appear across the entire plan.
    """
    extended = copy.deepcopy(base_template)
    weeks = extended.get("weeks", [])
    base_count = len(weeks)

    if target_weeks <= base_count:
        return extended

    additional = target_weeks - base_count

    # Base template structure (12 weeks):
    # W1(70% intro), W2(80%), W3(90%), W4(60% recovery),
    # W5(85%), W6(95%), W7(100%), W8(60% recovery),
    # W9-W12(peak/taper)
    #
    # For cadence=3: rearrange base block so recovery is at W3 and W6,
    # then extension pattern starts with recovery at W9 → every 3 weeks.
    # For cadence=4: keep original base block (recovery at W4, W8),
    # extension pattern puts recovery at W12, W16 → every 4 weeks.

    if base_count >= 8 and recovery_cadence == 3:
        # Rearrange base block: move recovery weeks to positions 3 and 6
        # Original: [W1, W2, W3, W4(rec), W5, W6, W7, W8(rec)]
        # Desired:  [W1, W2, W4(rec), W3, W5, W8(rec), W6, W7]
        base_block = [
            weeks[0],  # W1 intro (70%)
            weeks[1],  # W2 build (80%)
            weeks[3],  # W4 recovery → now at position 3
            weeks[2],  # W3 build (90%) → now at position 4
            weeks[4],  # W5 build (85%)
            weeks[7],  # W8 recovery → now at position 6
            weeks[5],  # W6 build (95%) → now at position 7
            weeks[6],  # W7 peak build (100%) → now at position 8
        ]
        # Extension pattern: [recovery, build, build] so W9=recovery, W12=recovery, W15=recovery
        pattern_weeks = [weeks[7], weeks[4], weeks[5]]  # W8(rec), W5(build), W6(build)
    elif base_count >= 8:
        base_block = weeks[:8]
        # Standard 4-week cycle: build, build, build, recovery
        pattern_weeks = weeks[4:8]  # weeks 5-8
    else:
        base_block = weeks[:min(8, base_count)]
        pattern_weeks = weeks[-4:]

    split_point = len(base_block)
    final_block = weeks[min(8, base_count):]  # weeks 9-12 (peak/taper)

    # Renumber base block (content was reordered, week_numbers need to match position)
    for i, week in enumerate(base_block):
        new_num = i + 1
        old_num = week["week_number"]
        week["week_number"] = new_num
        for workout in week.get("workouts", []):
            old_name = workout.get("name", "")
            workout["name"] = re.sub(r"^W\d{1,2}", f"W{new_num:02d}", old_name)
            workout["week_number"] = new_num

    # Extended base weeks are numbered starting after the base block
    new_weeks = []
    for i in range(additional):
        pattern_idx = i % len(pattern_weeks)
        new_week = copy.deepcopy(pattern_weeks[pattern_idx])
        new_week_number = split_point + 1 + i  # 9, 10, 11, 12 for a 16-week plan

        # Renumber
        new_week["week_number"] = new_week_number
        # Transform focus text for repeated cycles so it reads as continuation,
        # not a restart. E.g., "Build Phase Begins" → "Continued Development"
        original_focus = new_week.get("focus", "")
        cycle = i // len(pattern_weeks)  # 0 for first repeat, 1 for second, etc.
        new_week["focus"] = _transform_extended_focus(original_focus, cycle)

        # Slight volume progression for extended base (skip recovery weeks)
        if i < additional // 2 and new_week.get("volume_percent", 100) > 65:
            new_week["volume_percent"] = min(
                105, new_week.get("volume_percent", 100) + 3
            )

        # Renumber workouts
        for workout in new_week.get("workouts", []):
            old_name = workout.get("name", "")
            new_name = re.sub(r"^W\d{1,2}", f"W{new_week_number:02d}", old_name)
            workout["name"] = new_name
            workout["week_number"] = new_week_number

        new_weeks.append(new_week)

    # Final block starts after the extended base weeks
    final_start = split_point + additional + 1  # 13 for a 16-week plan

    # Renumber final block
    for i, week in enumerate(final_block):
        old_num = week["week_number"]
        new_num = final_start + i
        week["week_number"] = new_num
        week["focus"] = week.get("focus", "").replace(
            f"Week {old_num}", f"Week {new_num}"
        )
        for workout in week.get("workouts", []):
            old_name = workout.get("name", "")
            workout["name"] = re.sub(
                r"^W\d{1,2}", f"W{new_num:02d}", old_name
            )
            workout["week_number"] = new_num

    extended["weeks"] = base_block + new_weeks + final_block

    # Update metadata
    if "plan_metadata" in extended:
        extended["plan_metadata"]["duration_weeks"] = target_weeks

    return extended
