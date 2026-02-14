"""
Step 5: Select + Extend Plan Template

Selects the correct 12-week base template for tier+level,
then extends to 16 or 20 weeks if needed.
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

# FTP test insertion weeks by plan duration
FTP_TEST_WEEKS = {
    12: [1, 7],
    16: [1, 7, 13],
    20: [1, 7, 13, 19],
}


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

    # Extend if needed
    if plan_duration > base_weeks:
        template = extend_plan_template(template, plan_duration)
        extended = True

    return {
        "template": template,
        "template_key": f"{tier}_{level}",
        "template_dir": template_dir_name,
        "plan_duration": plan_duration,
        "extended": extended,
        "ftp_test_weeks": FTP_TEST_WEEKS.get(plan_duration, [1, 7]),
    }


def extend_plan_template(base_template: Dict, target_weeks: int) -> Dict:
    """
    Extend a 12-week plan template to 16 or 20 weeks.

    Strategy: duplicate base phase patterns (weeks 5-8) to fill the gap,
    then keep the original build/peak/taper progression at the end.
    """
    extended = copy.deepcopy(base_template)
    weeks = extended.get("weeks", [])
    base_count = len(weeks)

    if target_weeks <= base_count:
        return extended

    additional = target_weeks - base_count

    # Use weeks 5-8 as the "extra base" block to repeat
    # (weeks 1-4 = intro/base, 5-8 = build, 9-12 = peak/taper)
    if base_count >= 8:
        pattern_weeks = weeks[4:8]  # weeks 5-8 (0-indexed: 4-7)
    else:
        pattern_weeks = weeks[-4:]

    # Split: first 8 weeks = base block, last N weeks = final block (build/peak/taper)
    split_point = min(8, base_count)
    base_block = weeks[:split_point]   # weeks 1-8
    final_block = weeks[split_point:]  # weeks 9-12

    # Extended base weeks are numbered starting after the base block
    new_weeks = []
    for i in range(additional):
        pattern_idx = i % len(pattern_weeks)
        new_week = copy.deepcopy(pattern_weeks[pattern_idx])
        new_week_number = split_point + 1 + i  # 9, 10, 11, 12 for a 16-week plan

        # Renumber
        new_week["week_number"] = new_week_number
        # Keep original focus text — "Extended Base" prefix is an internal
        # label that should never leak into the athlete-facing guide.
        # The focus text from the pattern week is descriptive enough.

        # Slight volume progression for extended base
        if i < additional // 2:
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
