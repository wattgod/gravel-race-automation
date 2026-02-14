"""
Step 6: Generate ZWO Workout Files

Generates TrainingPeaks-compatible ZWO XML files from the plan template.
Every day of every week gets a ZWO file — including rest days, strength days,
and recovery days. This ensures drag-and-drop into TrainingPeaks is complete.

File naming convention: W{week:02d}_{daynum}{Day}_{MmmDD}_{Type}.zwo
  e.g. W01_1Mon_Feb02_Strength_Base.zwo
  - Sorts chronologically: by week, then day number (1=Mon..7=Sun)
  - Date in filename for easy drag-and-drop to TrainingPeaks calendar

Adapted from gravel-plans-experimental/races/generation_modules/zwo_generator.py
"""

import json
import re
import html as html_lib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# ── ZWO Template ─────────────────────────────────────────────

ZWO_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<workout_file>
    <author>Gravel God Training</author>
    <name>{name}</name>
    <description>{description}</description>
    <sportType>{sport_type}</sportType>
    <tags>
        <tag name="ENDURE"/>
    </tags>
    <workout>
{blocks}    </workout>
</workout_file>"""

# ── Day mapping ──────────────────────────────────────────────

DAY_ORDER = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAY_ABBREV = {"monday": "Mon", "tuesday": "Tue", "wednesday": "Wed",
              "thursday": "Thu", "friday": "Fri", "saturday": "Sat", "sunday": "Sun"}
DAY_NUM = {"monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4,
           "friday": 5, "saturday": 6, "sunday": 7}

# ── FTP Test Workout ─────────────────────────────────────────

FTP_TEST_BLOCKS = """        <Warmup Duration="720" PowerLow="0.40" PowerHigh="0.65"/>
        <SteadyState Duration="300" Power="0.75"/>
        <SteadyState Duration="300" Power="0.50"/>
        <SteadyState Duration="300" Power="1.10"/>
        <SteadyState Duration="300" Power="0.50"/>
        <FreeRide Duration="1200" FlatRoad="1"/>
        <Cooldown Duration="600" PowerLow="0.55" PowerHigh="0.40"/>
"""

FTP_TEST_DESCRIPTION = """FTP TEST PROTOCOL

WARM-UP (12 min):
Progressive warmup from Zone 1 to Zone 2.

MAIN SET:
1. 5 min @ RPE 6/10 (moderate effort)
2. 5 min @ RPE 2 (easy recovery)
3. 5 min ALL OUT (RPE 8-10). Go as hard as you can sustain.
4. 5 min @ RPE 2 (easy recovery)
5. 20 min ALL OUT. Start conservatively at RPE 8 — 20 minutes is LONG. This sets your FTP.

COOL-DOWN (10 min):
Easy spin Z1-Z2.

PURPOSE:
Accurate FTP = accurate training zones for the next 6 weeks.
Formula: FTP = 20-min average power x 0.95

Do this test when fresh (not after a hard week). You want unbroken flat or slight uphill terrain."""

# ── Strength Workout Templates ───────────────────────────────

STRENGTH_WORKOUTS = {
    "base": {
        "name": "Cycling Strength - Foundation",
        "description": """CYCLING-SPECIFIC STRENGTH SESSION (45-60 min)

WARM-UP (10 min):
- 5 min light cardio (jog, jump rope, or spin)
- Dynamic stretches: leg swings, hip circles, arm circles

MAIN SET (30-40 min):
Perform 3 sets of each exercise. Rest 60-90 sec between sets.

1. GOBLET SQUAT: 3x12 reps — Full depth, weight at chest. Builds quad and glute strength for climbing.
2. SINGLE-LEG ROMANIAN DEADLIFT: 3x10 each leg — Slow and controlled. Builds hamstring strength and balance.
3. BULGARIAN SPLIT SQUAT: 3x10 each leg — Rear foot elevated. The single most cycling-specific strength exercise.
4. PLANK: 3x45 sec — Tight core, flat back. Core stability prevents power leaks on the bike.
5. SIDE PLANK: 3x30 sec each side — Lateral stability for rough terrain.
6. GLUTE BRIDGE: 3x15 reps — Squeeze at top. Activates glutes that sitting all day shuts down.
7. CALF RAISES: 3x20 reps — Single leg if possible. Ankle stability for gravel.

COOL-DOWN (5 min):
- Quad stretch, hamstring stretch, hip flexor stretch
- Hold each 30 seconds

NOTES:
- Weight should be challenging but form must be perfect
- If form breaks down, reduce weight
- Do NOT go to failure — save energy for the bike""",
        "blocks": """        <SteadyState Duration="600" Power="0.45"/>
        <FreeRide Duration="2400" FlatRoad="1"/>
        <SteadyState Duration="300" Power="0.40"/>
""",
    },
    "build": {
        "name": "Cycling Strength - Build Phase",
        "description": """CYCLING-SPECIFIC STRENGTH SESSION - BUILD PHASE (45-60 min)

Build phase shifts to heavier loads, lower reps. Maintain power on the bike.

WARM-UP (10 min):
- 5 min light cardio
- Dynamic stretches + activation: banded walks, clamshells

MAIN SET (30-40 min):
Perform 3-4 sets of each. Rest 90-120 sec between sets.

1. BARBELL OR HEAVY GOBLET SQUAT: 4x6 reps — Heavy. Full depth. Build maximum force production.
2. SINGLE-LEG DEADLIFT: 3x8 each leg — Add weight. Posterior chain strength for sustained power.
3. STEP-UPS: 3x8 each leg — Use a box at knee height. Mimics pedal stroke force production.
4. PALLOF PRESS: 3x12 each side — Anti-rotation core work. Resists the rotational forces of pedaling.
5. FARMER'S CARRY: 3x40m — Heavy dumbbells. Total body stability and grip endurance.
6. SINGLE-LEG GLUTE BRIDGE: 3x12 each leg — Addresses left/right imbalances.

COOL-DOWN (5 min):
- Stretch quads, hamstrings, hip flexors, calves
- Foam roll IT band and quads

NOTES:
- Heavier loads, fewer reps than base phase
- Priority is force production, not endurance
- If legs are trashed from bike training, reduce load 20% but keep the session""",
        "blocks": """        <SteadyState Duration="600" Power="0.45"/>
        <FreeRide Duration="2700" FlatRoad="1"/>
        <SteadyState Duration="300" Power="0.40"/>
""",
    },
}

# ── Rest Day Workout ─────────────────────────────────────────

REST_DAY_DESCRIPTION = """REST DAY

Complete rest from structured training. Your body adapts during recovery, not during workouts.

WHAT TO DO:
- Sleep 8+ hours
- Walk for 20-30 min if you feel restless
- Foam roll or light stretching (10 min max)
- Eat well — recovery meals need protein and carbs
- Hydrate — water and electrolytes

WHAT NOT TO DO:
- Do NOT ride "just a little bit"
- Do NOT do "active recovery" unless prescribed
- Do NOT feel guilty. Rest IS training.

Trust the process. The fitness gains from your hard sessions this week
are being consolidated right now while you rest."""

# ── Recovery Ride Template ───────────────────────────────────

RECOVERY_RIDE_BLOCKS = """        <Warmup Duration="300" PowerLow="0.35" PowerHigh="0.50"/>
        <SteadyState Duration="1800" Power="0.50"/>
        <Cooldown Duration="300" PowerLow="0.50" PowerHigh="0.35"/>
"""

RECOVERY_RIDE_DESCRIPTION = """EASY RECOVERY RIDE (40 min)

Zone 1-2 ONLY. This is active recovery, not training.

If your legs feel heavy, that's fine. Spin easy. If you catch yourself
pushing into Zone 3, shift to an easier gear.

The purpose of this ride is blood flow for recovery. NOT fitness.
If you make this hard, you're stealing recovery from yesterday's hard session
and compromising tomorrow's training."""


def generate_workouts(
    plan_config: Dict,
    profile: Dict,
    derived: Dict,
    schedule: Dict,
    workouts_dir: Path,
    base_dir: Path,
):
    """
    Generate ZWO files for every day of every week.
    Every day gets a file — training days, strength days, and rest days.
    """
    template = plan_config["template"]
    plan_duration = plan_config["plan_duration"]
    ftp_test_weeks = plan_config.get("ftp_test_weeks", [1, 7])
    race_name = derived.get("race_name")
    race_distance = derived.get("race_distance_miles")

    # Load race data for modifications
    race_data = load_race_data(race_name, race_distance, base_dir) if race_name else None

    # Calculate start date (next Monday from today)
    race_date_str = derived.get("race_date")
    start_date = _calculate_start_date(race_date_str, plan_duration)

    # Get weekly schedule
    days_schedule = schedule.get("days", {})

    weeks = template.get("weeks", [])

    for week_idx in range(plan_duration):
        week_num = week_idx + 1
        week_data = weeks[week_idx] if week_idx < len(weeks) else {}
        template_workouts = week_data.get("workouts", [])

        # Determine training phase for strength workout selection
        phase = "base" if week_num <= plan_duration * 0.5 else "build"

        # Is this an FTP test week?
        is_ftp_week = week_num in ftp_test_weeks

        for day_idx, day_name in enumerate(DAY_ORDER):
            day_abbrev = DAY_ABBREV[day_name]
            day_date = start_date + timedelta(weeks=week_idx, days=day_idx)
            date_str = day_date.strftime("%Y-%m-%d")
            day_schedule = days_schedule.get(day_name, {"session": "rest"})
            session_type = day_schedule["session"]

            # Find matching template workout for this day
            template_workout = _find_template_workout(template_workouts, day_abbrev, day_name)

            if session_type == "rest":
                _write_rest_day(workouts_dir, week_num, day_abbrev, date_str)

            elif session_type == "strength":
                _write_strength_workout(workouts_dir, week_num, day_abbrev, date_str, phase)

            elif session_type == "intervals" and is_ftp_week and day_name == _first_interval_day(days_schedule):
                # FTP test replaces the first interval session of FTP test weeks
                _write_ftp_test(workouts_dir, week_num, day_abbrev, date_str)

            elif template_workout:
                # Use the template workout with race modifications
                _write_template_workout(
                    workouts_dir, week_num, day_abbrev, date_str,
                    template_workout, race_data, week_num, plan_duration
                )

            else:
                # Generate appropriate default workout for session type
                _write_default_workout(
                    workouts_dir, week_num, day_abbrev, date_str,
                    session_type, race_data, week_num, plan_duration
                )

    # Generate race day workout as final file
    _write_race_day_workout(workouts_dir, plan_duration, race_data, race_name, race_distance, race_date_str)


def _calculate_start_date(race_date_str: Optional[str], plan_duration: int):
    """Calculate plan start date (Monday) working back from race date."""
    if race_date_str:
        try:
            race_date = datetime.strptime(race_date_str, "%Y-%m-%d")
            # Work backwards from race date
            start = race_date - timedelta(weeks=plan_duration)
            # Align to Monday
            days_to_monday = start.weekday()
            start = start - timedelta(days=days_to_monday)
            return start
        except ValueError:
            pass

    # Fallback: next Monday from today
    today = datetime.now()
    days_until_monday = (7 - today.weekday()) % 7
    if days_until_monday == 0:
        days_until_monday = 7
    return today + timedelta(days=days_until_monday)


def _first_interval_day(days_schedule: Dict) -> str:
    """Find the first interval day in the week."""
    for day in DAY_ORDER:
        if days_schedule.get(day, {}).get("session") == "intervals":
            return day
    return "tuesday"


def _find_template_workout(workouts: List[Dict], day_abbrev: str, day_name: str) -> Optional[Dict]:
    """Find the template workout matching this day."""
    for w in workouts:
        name = w.get("name", "")
        if day_abbrev in name or day_name.title() in name:
            return w
    return None


def _write_zwo(workouts_dir: Path, filename: str, name: str, description: str,
               blocks: str, sport_type: str = "bike"):
    """Write a ZWO file with proper XML formatting."""
    safe_desc = html_lib.escape(description)
    safe_name = html_lib.escape(name)

    # Ensure blocks are properly indented
    if blocks and not blocks.strip().startswith("<"):
        pass
    if not blocks or not blocks.strip():
        blocks = RECOVERY_RIDE_BLOCKS

    content = ZWO_TEMPLATE.format(
        name=safe_name,
        description=safe_desc,
        blocks=blocks,
        sport_type=sport_type,
    )
    (workouts_dir / filename).write_text(content, encoding="utf-8")


def _write_rest_day(workouts_dir: Path, week_num: int, day_abbrev: str, date_str: str):
    """Write a rest day ZWO file — yes, rest days get files for TrainingPeaks."""
    prefix = _file_prefix(week_num, day_abbrev, date_str)
    filename = f"{prefix}_Rest_Day.zwo"
    blocks = '        <SteadyState Duration="1" Power="0.40"/>\n'
    _write_zwo(workouts_dir, filename,
               f"W{week_num:02d} {day_abbrev} - Rest Day ({date_str})",
               REST_DAY_DESCRIPTION, blocks)


def _write_strength_workout(workouts_dir: Path, week_num: int, day_abbrev: str,
                            date_str: str, phase: str):
    """Write a strength training ZWO file."""
    template = STRENGTH_WORKOUTS.get(phase, STRENGTH_WORKOUTS["base"])
    prefix = _file_prefix(week_num, day_abbrev, date_str)
    filename = f"{prefix}_Strength_{phase.title()}.zwo"
    _write_zwo(workouts_dir, filename,
               f"W{week_num:02d} {day_abbrev} - {template['name']} ({date_str})",
               template["description"], template["blocks"])


def _write_ftp_test(workouts_dir: Path, week_num: int, day_abbrev: str, date_str: str):
    """Write an FTP test workout ZWO file."""
    prefix = _file_prefix(week_num, day_abbrev, date_str)
    filename = f"{prefix}_FTP_Test.zwo"
    _write_zwo(workouts_dir, filename,
               f"W{week_num:02d} {day_abbrev} - FTP Test ({date_str})",
               FTP_TEST_DESCRIPTION, FTP_TEST_BLOCKS)


def _write_template_workout(workouts_dir: Path, week_num: int, day_abbrev: str,
                            date_str: str, workout: Dict, race_data: Optional[Dict],
                            current_week: int, total_weeks: int):
    """Write a workout from the plan template."""
    name = workout.get("name", f"W{week_num:02d}_{day_abbrev}_Workout")
    description = workout.get("description", "")
    blocks = workout.get("blocks", "")

    # Apply race-specific modifications
    if race_data:
        description = _apply_race_mods(description, race_data, current_week, total_weeks)

    # Build standardized filename
    workout_type = _detect_workout_type(name)
    prefix = _file_prefix(week_num, day_abbrev, date_str)
    filename = f"{prefix}_{_sanitize_filename(workout_type)}.zwo"

    _write_zwo(workouts_dir, filename,
               f"W{week_num:02d} {day_abbrev} - {workout_type} ({date_str})",
               description, blocks)


def _write_default_workout(workouts_dir: Path, week_num: int, day_abbrev: str,
                           date_str: str, session_type: str, race_data: Optional[Dict],
                           current_week: int, total_weeks: int):
    """Write a default workout when no template workout exists for this day."""
    prefix = _file_prefix(week_num, day_abbrev, date_str)

    if session_type == "long_ride":
        name = f"W{week_num:02d} {day_abbrev} - Long Endurance Ride ({date_str})"
        description = (
            "LONG ENDURANCE RIDE\n\n"
            "Zone 2 steady effort. This is the backbone of your gravel preparation.\n"
            "Build duration progressively each week.\n\n"
            "- Stay in Zone 2 (conversational pace)\n"
            "- Practice race nutrition every 30 minutes\n"
            "- Include some gravel/dirt if possible\n"
            "- Focus on comfortable position for long hours"
        )
        blocks = (
            '        <Warmup Duration="600" PowerLow="0.40" PowerHigh="0.60"/>\n'
            '        <SteadyState Duration="7200" Power="0.65"/>\n'
            '        <Cooldown Duration="600" PowerLow="0.60" PowerHigh="0.40"/>\n'
        )
        filename = f"{prefix}_Long_Endurance.zwo"

    elif session_type == "intervals":
        name = f"W{week_num:02d} {day_abbrev} - Interval Session ({date_str})"
        description = (
            "INTERVAL SESSION\n\n"
            "Hard effort intervals with full recovery.\n"
            "- Complete all intervals at target power\n"
            "- If form breaks down, stop the set\n"
            "- Full recovery between intervals (Zone 1)"
        )
        blocks = (
            '        <Warmup Duration="900" PowerLow="0.40" PowerHigh="0.70"/>\n'
            '        <IntervalsT Repeat="5" OnDuration="240" OnPower="1.10" '
            'OffDuration="240" OffPower="0.50"/>\n'
            '        <Cooldown Duration="600" PowerLow="0.60" PowerHigh="0.40"/>\n'
        )
        filename = f"{prefix}_Intervals.zwo"

    else:  # easy_ride or other
        name = f"W{week_num:02d} {day_abbrev} - Easy Recovery Ride ({date_str})"
        description = RECOVERY_RIDE_DESCRIPTION
        blocks = RECOVERY_RIDE_BLOCKS
        filename = f"{prefix}_Easy_Recovery.zwo"

    if race_data:
        description = _apply_race_mods(description, race_data, current_week, total_weeks)

    _write_zwo(workouts_dir, filename, name, description, blocks)


def _write_race_day_workout(workouts_dir: Path, plan_duration: int,
                            race_data: Optional[Dict], race_name: str,
                            race_distance, race_date_str: Optional[str] = None):
    """Write the race day execution workout as final ZWO."""
    date_label_internal = race_date_str if race_date_str else "Race Day"
    name = f"W{plan_duration:02d} Race Day - {race_name or 'Race'} {race_distance}mi ({date_label_internal})"
    description = (
        f"RACE DAY: {race_name} {race_distance}mi\n\n"
        "PRE-RACE:\n"
        "- 10-15 min easy warmup\n"
        "- 2x30 sec openers at race pace\n"
        "- 5 min easy spin\n\n"
        "RACE EXECUTION:\n"
        "- First 25%: Hold back, 5% below target effort\n"
        "- Middle 50%: Settle into target effort, fuel every 20-30 min\n"
        "- Final 25%: Empty the tank if legs allow\n\n"
        "FUELING:\n"
        "- Set 20-minute timer for nutrition\n"
        "- 60-80g carbs/hour (adjust for duration — see Nutrition Strategy)\n"
        "- Hydrate 500-750ml/hour\n\n"
        "REMEMBER:\n"
        "Start slower than you think. The race doesn't start until the last third."
    )
    blocks = (
        '        <Warmup Duration="600" PowerLow="0.40" PowerHigh="0.60"/>\n'
        '        <SteadyState Duration="60" Power="0.90"/>\n'
        '        <SteadyState Duration="60" Power="0.50"/>\n'
        '        <SteadyState Duration="60" Power="0.90"/>\n'
        '        <SteadyState Duration="300" Power="0.50"/>\n'
        '        <FreeRide Duration="3600" FlatRoad="0"/>\n'
    )
    race_date_label = _date_label(race_date_str) if race_date_str else "RaceDay"
    filename = f"W{plan_duration:02d}_{race_date_label}_Race_Day.zwo"
    _write_zwo(workouts_dir, filename, name, description, blocks)


# ── Helpers ──────────────────────────────────────────────────

def load_race_data(race_name: str, distance_miles: Optional[int], base_dir: Path) -> Optional[Dict]:
    """Load race JSON and resolve to correct distance variant."""
    slug = _slugify(race_name)
    race_path = base_dir / "races" / f"{slug}.json"
    if not race_path.exists():
        return None

    with open(race_path) as f:
        race_json = json.load(f)

    if "distance_variants" in race_json and distance_miles:
        variants = race_json["distance_variants"]
        best = min(variants, key=lambda v: abs(v["distance_miles"] - distance_miles))
        resolved = {**race_json, **best}
        resolved.pop("distance_variants", None)
        return resolved

    return race_json


def _apply_race_mods(description: str, race_data: Dict, week_num: int, total_weeks: int) -> str:
    mods = race_data.get("workout_modifications", {})
    extras = []

    altitude = mods.get("altitude_training", {})
    if altitude.get("enabled") and week_num <= total_weeks // 2:
        extras.append(f"\nALTITUDE NOTE: {altitude.get('note', '')}")

    heat = mods.get("heat_training", {})
    if heat.get("enabled") and total_weeks - week_num <= 6:
        extras.append(f"\nHEAT NOTE: {heat.get('note', '')}")

    if extras:
        description += "\n" + "\n".join(extras)
    return description


def _detect_workout_type(name: str) -> str:
    """Detect workout type from template name for standardized filename."""
    upper = name.upper()
    if "REST" in upper or "OFF" in upper:
        return "Rest_Day"
    if "FTP" in upper or "TEST" in upper:
        return "FTP_Test"
    if "LONG" in upper or "ENDURANCE" in upper:
        return "Long_Endurance"
    if "VO2" in upper or "HARD SESSION" in upper:
        return "VO2max_Intervals"
    if "THRESHOLD" in upper or "SWEET SPOT" in upper or "G-SPOT" in upper:
        return "Threshold"
    if "TEMPO" in upper:
        return "Tempo"
    if "SPRINT" in upper or "STOMP" in upper:
        return "Sprints"
    if "RECOVERY" in upper or "EASY" in upper or "SPIN" in upper:
        return "Easy_Recovery"
    if "POLARIZED" in upper and "HARD" in upper:
        return "Polarized_Hard"
    if "RACE" in upper and "SIM" in upper:
        return "Race_Simulation"
    # Fallback: clean up the original name
    return _sanitize_filename(name.split("-")[-1].strip() if "-" in name else name)


def _date_label(date_str: str) -> str:
    """Convert '2026-02-14' to 'Feb14' for filenames."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b%d")
    except (ValueError, TypeError):
        return ""


def _file_prefix(week_num: int, day_abbrev: str, date_str: str) -> str:
    """Build sortable filename prefix: W01_1Mon_Feb02.

    Sorts chronologically: by week, then day number (1=Mon..7=Sun), then date.
    """
    # Reverse lookup day number from abbreviation
    abbrev_to_num = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4,
                     "Fri": 5, "Sat": 6, "Sun": 7}
    day_num = abbrev_to_num.get(day_abbrev, 0)
    date = _date_label(date_str)
    return f"W{week_num:02d}_{day_num}{day_abbrev}_{date}"


def _sanitize_filename(name: str) -> str:
    safe = re.sub(r"[^\w\s-]", "", name)
    safe = re.sub(r"\s+", "_", safe.strip())
    safe = re.sub(r"_+", "_", safe)
    return safe[:80]


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
