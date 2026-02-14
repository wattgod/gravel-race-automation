#!/usr/bin/env python3
"""
NEW PLAN — One command to go from SendGrid email to finished plan.

Usage:
  python3 new_plan.py --id tp-sbt-grvl-sarah-printz-mlju8jn9   # Full pipeline (PDF + deploy + email)
  python3 new_plan.py --id tp-sbt-grvl-sarah-printz-mlju8jn9 --draft  # Review first, deliver later
  python3 new_plan.py                                            # Interactive mode (manual entry)

Default: runs ALL 10 steps (validate → profile → classify → schedule → template → workouts →
         guide → PDF → deploy → deliver). Opens guide in browser AND emails athlete.

--draft: skips PDF/deploy/deliver so you can review the guide first. Then run:
         python3 run_pipeline.py athletes/<slug>/intake.json

Requires .env file with SUPABASE_URL and SUPABASE_SERVICE_KEY for --id mode.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).parent


def load_env():
    """Load .env file from project root."""
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip())


def fetch_from_supabase(request_id: str) -> dict:
    """Fetch a plan request from Supabase by request_id."""
    import urllib.request
    import urllib.error

    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not service_key:
        print("  ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
        print(f"  Create {BASE_DIR / '.env'} with:")
        print(f"    SUPABASE_URL=https://your-project.supabase.co")
        print(f"    SUPABASE_SERVICE_KEY=eyJ...")
        sys.exit(1)

    url = f"{supabase_url}/rest/v1/plan_requests?request_id=eq.{request_id}&select=payload"
    req = urllib.request.Request(url, headers={
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  ERROR: Supabase returned {e.code}: {e.read().decode()}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"  ERROR: Cannot reach Supabase: {e}")
        sys.exit(1)

    if not data:
        print(f"  ERROR: No submission found for ID: {request_id}")
        print(f"  Check that:")
        print(f"    1. The ID is correct (copy from the email subject)")
        print(f"    2. The Cloudflare Worker has SUPABASE_URL and SUPABASE_SERVICE_KEY configured")
        print(f"    3. The plan_requests migration has been applied")
        sys.exit(1)

    return data[0]["payload"]


def payload_to_intake(payload: dict) -> dict:
    """Convert the Cloudflare Worker's trainingRequest format to pipeline intake format."""
    athlete = payload.get("athlete", {})
    race = payload.get("race", {})
    fitness = payload.get("fitness", {})
    schedule = payload.get("schedule", {})
    strength = payload.get("strength", {})
    notes = payload.get("notes", {})

    # Parse distance — worker stores as string like "100mi"
    distance_raw = race.get("distance", "")
    if isinstance(distance_raw, str):
        distance = int("".join(c for c in distance_raw if c.isdigit()) or "0")
    else:
        distance = int(distance_raw) if distance_raw else 0

    return {
        "name": athlete.get("name"),
        "email": athlete.get("email"),
        "sex": athlete.get("sex"),
        "age": athlete.get("age"),
        "height_ft": athlete.get("height_ft"),
        "height_in": athlete.get("height_in"),
        "weight_lbs": athlete.get("weight_lbs"),
        "years_cycling": athlete.get("years_cycling"),
        "sleep": athlete.get("sleep_quality"),
        "stress": athlete.get("stress_level"),
        "races": [{
            "name": race.get("name"),
            "date": race.get("date"),
            "distance_miles": distance,
            "priority": "A",
            "goal": race.get("goal", "finish"),
        }],
        "longest_ride": fitness.get("longest_recent_ride"),
        "ftp": fitness.get("ftp"),
        "max_hr": fitness.get("hr_max"),
        "lthr": fitness.get("hr_threshold"),
        "resting_hr": fitness.get("hr_resting"),
        "weekly_hours": schedule.get("hours_per_week"),
        "trainer_access": schedule.get("trainer_access"),
        "long_ride_days": schedule.get("long_ride_days", []),
        "interval_days": schedule.get("interval_days", []),
        "off_days": schedule.get("off_days", []),
        "strength_current": strength.get("current"),
        "strength_include": strength.get("want_in_plan"),
        "strength_equipment": strength.get("equipment"),
        "injuries": notes.get("injuries") or "NA",
        "anything_else": notes.get("additional") or "",
    }


def prompt(label: str, default: str = "", required: bool = True) -> str:
    """Prompt for a value. Shows default in brackets."""
    if default:
        raw = input(f"  {label} [{default}]: ").strip()
        return raw if raw else default
    else:
        while True:
            raw = input(f"  {label}: ").strip()
            if raw or not required:
                return raw
            print(f"    ^ Required field")


def prompt_choice(label: str, options: list[str], default: str = "") -> str:
    """Prompt with valid options shown."""
    opts_str = " / ".join(options)
    if default:
        raw = input(f"  {label} ({opts_str}) [{default}]: ").strip().lower()
        return raw if raw else default
    else:
        while True:
            raw = input(f"  {label} ({opts_str}): ").strip().lower()
            if raw in [o.lower() for o in options]:
                return raw
            print(f"    ^ Must be one of: {opts_str}")


def prompt_days(label: str) -> list[str]:
    """Prompt for day names (comma-separated)."""
    valid = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    abbrev = {"mon": "monday", "tue": "tuesday", "wed": "wednesday", "thu": "thursday",
              "fri": "friday", "sat": "saturday", "sun": "sunday"}
    while True:
        raw = input(f"  {label} (comma-separated, e.g. saturday,sunday): ").strip().lower()
        if not raw:
            return []
        days = []
        for d in raw.replace(" ", "").split(","):
            d = d.strip()
            resolved = abbrev.get(d[:3], d)
            if resolved in valid:
                days.append(resolved)
            else:
                print(f"    ^ Unknown day: '{d}'. Use full names or 3-letter abbreviations.")
                days = []
                break
        if days:
            return days


def prompt_int(label: str, default: str = "") -> int | None:
    """Prompt for an integer. Returns None if blank."""
    if default:
        raw = input(f"  {label} [{default}]: ").strip()
        raw = raw if raw else default
    else:
        raw = input(f"  {label} (or blank): ").strip()
    if not raw or raw.lower() in ("na", "n/a", "none", "-", "—"):
        return None
    try:
        return int(raw)
    except ValueError:
        print(f"    ^ Not a number, skipping")
        return None


def interactive_intake() -> dict:
    """Prompt for all fields interactively (manual entry from SendGrid email)."""
    print()
    print("=" * 60)
    print("  NEW TRAINING PLAN — Interactive Mode")
    print("  Read the SendGrid email and fill in the fields below.")
    print("=" * 60)
    print()

    # ── ATHLETE ────────────────────────────────────────────────
    print("ATHLETE")
    name = prompt("Name")
    email = prompt("Email")
    sex = prompt_choice("Sex", ["male", "female"])
    age = prompt_int("Age")
    height_raw = prompt("Height (e.g. 5'10 or 5-10)")
    weight_raw = prompt("Weight in lbs (e.g. 135)")
    experience = prompt("Experience / Years cycling (e.g. 3-5 years)", default="3-5 years")
    sleep = prompt_choice("Sleep", ["poor", "fair", "good", "excellent"], default="good")
    stress = prompt_choice("Stress", ["low", "moderate", "high", "very_high"], default="moderate")
    print()

    # Parse height
    height_ft, height_in = 5, 10
    if height_raw:
        parts = height_raw.replace("'", "-").replace('"', '').replace("ft", "").replace("in", "").split("-")
        try:
            height_ft = int(parts[0].strip())
            height_in = int(parts[1].strip()) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            pass

    # Parse weight
    weight_lbs = 150
    try:
        weight_lbs = int(weight_raw.replace("lbs", "").replace("lb", "").strip())
    except ValueError:
        pass

    # ── RACE ───────────────────────────────────────────────────
    print("RACE")
    race_name = prompt("Race name (e.g. SBT GRVL)")
    race_date = prompt("Race date (YYYY-MM-DD, e.g. 2026-06-28)")
    race_distance = prompt_int("Distance in miles (e.g. 100)")
    goal = prompt_choice("Goal", ["finish", "compete", "podium"], default="finish")
    print()

    # ── FITNESS ────────────────────────────────────────────────
    print("FITNESS")
    longest_ride = prompt("Longest ride in last 4 weeks (e.g. 2-4)", default="2-4")
    ftp = prompt_int("FTP watts", default="")
    max_hr = prompt_int("Max HR", default="")
    lthr = prompt_int("LTHR", default="")
    resting_hr = prompt_int("Resting HR", default="")
    print()

    # ── SCHEDULE ───────────────────────────────────────────────
    print("SCHEDULE")
    weekly_hours = prompt_choice("Hours/Week", ["3-5", "5-7", "7-10", "10-12", "12-15", "15+"])
    trainer = prompt_choice("Trainer access", ["no", "yes-basic", "yes-smart"], default="yes-basic")
    long_ride_days = prompt_days("Long ride days")
    interval_days = prompt_days("Interval days")
    off_days = prompt_days("Off days")
    print()

    # ── STRENGTH ───────────────────────────────────────────────
    print("STRENGTH")
    strength_current = prompt_choice("Current practice", ["none", "occasional", "regular"], default="none")
    strength_include = prompt_choice("Include in plan", ["yes", "no"], default="yes")
    strength_equipment = prompt_choice("Equipment", ["none", "bands-only", "basic-home", "full-gym"], default="none")
    print()

    # ── INJURIES ───────────────────────────────────────────────
    print("INJURIES/LIMITATIONS")
    injuries = prompt("Injuries or limitations", default="NA", required=False)
    print()

    return {
        "name": name,
        "email": email,
        "sex": sex,
        "age": age,
        "height_ft": height_ft,
        "height_in": height_in,
        "weight_lbs": weight_lbs,
        "years_cycling": experience,
        "sleep": sleep,
        "stress": stress,
        "races": [{
            "name": race_name,
            "date": race_date,
            "distance_miles": race_distance,
            "priority": "A",
            "goal": goal,
        }],
        "longest_ride": longest_ride,
        "ftp": ftp,
        "max_hr": max_hr,
        "lthr": lthr,
        "resting_hr": resting_hr,
        "weekly_hours": weekly_hours,
        "trainer_access": trainer,
        "long_ride_days": long_ride_days,
        "interval_days": interval_days,
        "off_days": off_days,
        "strength_current": strength_current,
        "strength_include": strength_include,
        "strength_equipment": strength_equipment,
        "injuries": injuries,
        "anything_else": "",
    }


def run_pipeline(intake: dict, draft: bool = False):
    """Save intake, run pipeline, validate, open guide.

    Args:
        draft: If True, skip PDF/deploy/deliver (review mode).
               If False (default), run all 10 steps end-to-end.
    """
    name = intake["name"]
    race = intake["races"][0]
    race_name = race["name"]
    race_distance = race["distance_miles"]
    race_date = race["date"]
    weekly_hours = intake["weekly_hours"]
    goal = race.get("goal", "finish")

    # ── CONFIRM ────────────────────────────────────────────────
    print("=" * 60)
    print(f"  {name} | {race_name} {race_distance}mi | {race_date}")
    print(f"  {weekly_hours} hrs/wk | Goal: {goal}")
    print("=" * 60)
    confirm = input("\n  Generate plan? (y/n) [y]: ").strip().lower()
    if confirm and confirm != "y":
        print("Aborted.")
        sys.exit(0)

    # ── SAVE INTAKE ────────────────────────────────────────────
    slug = name.lower().replace(" ", "-")
    date_str = datetime.now().strftime("%Y%m%d")
    athlete_id = f"{slug}-{date_str}"
    athlete_dir = BASE_DIR / "athletes" / athlete_id
    athlete_dir.mkdir(parents=True, exist_ok=True)

    intake_path = athlete_dir / "intake.json"
    with open(intake_path, "w") as f:
        json.dump(intake, f, indent=2)
    print(f"\n  Saved: {intake_path}")

    # ── RUN PIPELINE ───────────────────────────────────────────
    cmd = [sys.executable, str(BASE_DIR / "run_pipeline.py"), str(intake_path)]
    if draft:
        cmd.extend(["--skip-pdf", "--skip-deploy", "--skip-deliver"])
        print(f"\n  Running pipeline (draft mode — skipping PDF/deploy/deliver)...\n")
    else:
        print(f"\n  Running full pipeline (PDF + deploy + deliver)...\n")
    result = subprocess.run(cmd, cwd=str(BASE_DIR))
    if result.returncode != 0:
        print("\n  PIPELINE FAILED. Check errors above.")
        sys.exit(1)

    # ── VALIDATE ───────────────────────────────────────────────
    print(f"\n  Validating output...\n")
    val_result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "validate_pipeline_output.py"), str(athlete_dir)],
        cwd=str(BASE_DIR),
    )

    tp_result = subprocess.run(
        [sys.executable, str(BASE_DIR / "scripts" / "zwo_tp_validator.py"), str(athlete_dir / "workouts")],
        cwd=str(BASE_DIR),
    )

    # ── OPEN GUIDE ─────────────────────────────────────────────
    guide_path = athlete_dir / "guide.html"
    if guide_path.exists():
        print(f"\n  Opening guide in browser...")
        subprocess.run(["open", str(guide_path)])

    # ── SUMMARY ────────────────────────────────────────────────
    workouts_dir = athlete_dir / "workouts"
    zwo_count = len(list(workouts_dir.glob("*.zwo"))) if workouts_dir.exists() else 0
    guide_size = guide_path.stat().st_size if guide_path.exists() else 0

    print(f"\n{'='*60}")
    print(f"  DONE")
    print(f"  Athlete: {name}")
    print(f"  Race:    {race_name} {race_distance}mi")
    print(f"  Plan:    {athlete_dir}")
    print(f"  Guide:   {guide_size:,} bytes")
    print(f"  Workouts: {zwo_count} ZWO files")
    print(f"")
    print(f"  Guide:    {guide_path}")
    print(f"  Workouts: {workouts_dir}")
    print(f"{'='*60}")

    if val_result.returncode != 0 or tp_result.returncode != 0:
        print("\n  WARNING: Validation issues detected. Check output above.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a training plan from questionnaire data.",
        epilog="Without --id: interactive mode (type data from SendGrid email).\n"
               "With --id: pulls data from Supabase (zero typing).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--id",
        dest="request_id",
        help="Plan request ID from the email subject (e.g. tp-sbt-grvl-sarah-printz-mlju8jn9)",
    )
    parser.add_argument(
        "--draft",
        action="store_true",
        help="Draft mode: skip PDF/deploy/deliver (review guide before sending)",
    )
    args = parser.parse_args()

    if args.request_id:
        # ── SUPABASE MODE (zero typing) ──────────────────────────
        print()
        print("=" * 60)
        print("  NEW TRAINING PLAN — Supabase Mode")
        print(f"  Pulling: {args.request_id}")
        print("=" * 60)
        print()

        load_env()
        payload = fetch_from_supabase(args.request_id)
        intake = payload_to_intake(payload)

        print(f"  Athlete: {intake['name']}")
        print(f"  Email:   {intake['email']}")
        print(f"  Race:    {intake['races'][0]['name']} {intake['races'][0]['distance_miles']}mi")
        print(f"  Date:    {intake['races'][0]['date']}")
        print(f"  Hours:   {intake['weekly_hours']}")
        print()
    else:
        # ── INTERACTIVE MODE (manual entry) ──────────────────────
        intake = interactive_intake()

    run_pipeline(intake, draft=args.draft)


if __name__ == "__main__":
    main()
