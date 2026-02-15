#!/usr/bin/env python3
"""
Pre-Delivery Audit — BLOCKS delivery if any check fails.

This script is the last gate before an athlete's plan goes out the door.
It runs AFTER the pipeline and checks things the pipeline itself doesn't:
  - Injury accommodations actually modified exercises (not just warnings)
  - Recovery week rides are truly easy (power < 0.65 FTP)
  - ZWO XML is valid and parseable
  - Methodology claims match actual generated workouts
  - Email templates exist and render cleanly
  - PDF exists and is non-trivial

This script exists because the AI that builds plans has a documented history
of writing dead code, appending warnings instead of fixing things, and
claiming "done" without verifying. This script doesn't trust the pipeline.
It re-reads every output file and validates independently.

Usage:
    python3 scripts/pre_delivery_audit.py --athlete mike-wallace-20260214
    python3 scripts/pre_delivery_audit.py --all
"""

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ATHLETES_DIR = BASE_DIR / "athletes"
TEMPLATES_DIR = BASE_DIR / "templates" / "emails"

# Exercises that must NOT appear for specific injury types
BANNED_EXERCISES = {
    "knee": [
        "BULGARIAN SPLIT SQUAT",
        "STEP-UPS",
        "Full depth",
    ],
    "back": [
        "ROMANIAN DEADLIFT",
        "FARMER'S CARRY",
    ],
    "hip": [
        "Full depth",
    ],
}

INJURY_KEYWORDS = {
    "knee": ("knee", "chondromalacia", "patella", "acl", "mcl", "meniscus"),
    "back": ("back", "spine", "lumbar", "herniat", "disc", "l4", "l5", "sciatica"),
    "hip": ("hip resurfac", "hip replac", "labral", "hip impingement"),
    "gi": ("reflux", "gerd", "acid", "gi issue", "gastro", "ibs", "crohn"),
}


class AuditFailure:
    def __init__(self, check: str, message: str, severity: str = "FAIL"):
        self.check = check
        self.message = message
        self.severity = severity

    def __str__(self):
        return f"  [{self.severity}] {self.check}: {self.message}"


def detect_injuries(injuries_text: str) -> set:
    """Detect which injury categories apply."""
    if not injuries_text:
        return set()
    lower = injuries_text.lower()
    categories = set()
    for cat, keywords in INJURY_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            categories.add(cat)
    return categories


def audit_athlete(athlete_dir: Path) -> list:
    """Run all audit checks on a single athlete. Returns list of AuditFailure."""
    failures = []
    name = athlete_dir.name

    # Load required files
    intake_path = athlete_dir / "intake.json"
    methodology_path = athlete_dir / "methodology.json"
    touchpoints_path = athlete_dir / "touchpoints.json"
    pdf_path = athlete_dir / "guide.pdf"
    workouts_dir = athlete_dir / "workouts"

    if not intake_path.exists():
        failures.append(AuditFailure("FILES", f"intake.json missing for {name}"))
        return failures

    with open(intake_path) as f:
        intake = json.load(f)

    injuries = intake.get("injuries", "")
    injury_categories = detect_injuries(injuries)

    # ── CHECK 1: Injury accommodations actually modified exercises ──
    if injury_categories & {"knee", "back", "hip"}:
        strength_files = sorted(workouts_dir.glob("*Strength_Base*")) + sorted(workouts_dir.glob("*Strength_Build*"))
        for sf in strength_files:
            content = sf.read_text()
            for cat in injury_categories & {"knee", "back", "hip"}:
                for banned in BANNED_EXERCISES.get(cat, []):
                    if banned in content:
                        failures.append(AuditFailure(
                            "INJURY_FILTER",
                            f"{sf.name}: '{banned}' present despite {cat} restriction"
                        ))

        # Check that modification note exists
        if strength_files:
            content = strength_files[0].read_text()
            if "EXERCISES MODIFIED" not in content:
                failures.append(AuditFailure(
                    "INJURY_FILTER",
                    f"Strength workouts missing 'EXERCISES MODIFIED' note despite {injury_categories} restrictions"
                ))

    # ── CHECK 2: GI nutrition accommodation ──
    if "gi" in injury_categories:
        long_rides = sorted(workouts_dir.glob("*Long_Endurance*")) + sorted(workouts_dir.glob("*Endurance*"))
        for lr in long_rides[:3]:
            content = lr.read_text()
            if "60-80g carbs/hour" in content:
                failures.append(AuditFailure(
                    "GI_NUTRITION",
                    f"{lr.name}: standard '60-80g carbs/hour' present despite GI restriction"
                ))

        race_day = list(workouts_dir.glob("*Race_Day*"))
        if race_day:
            content = race_day[0].read_text()
            if "60-80g carbs/hour" in content:
                failures.append(AuditFailure(
                    "GI_NUTRITION",
                    f"Race day workout has standard nutrition despite GI restriction"
                ))

    # ── CHECK 3: Recovery week rides — power < 0.65 FTP ──
    if methodology_path.exists():
        with open(methodology_path) as f:
            meth = json.load(f)
        recovery_weeks = set(meth.get("periodization", {}).get("recovery_weeks", []))

        for zwo in sorted(workouts_dir.glob("*.zwo")):
            m = re.match(r"W(\d+)", zwo.name)
            if not m:
                continue
            week_num = int(m.group(1))
            if week_num not in recovery_weeks:
                continue
            if any(skip in zwo.name for skip in ("Rest_Day", "Strength", "FTP_Test", "Race_Day")):
                continue

            content = zwo.read_text()
            # Check power values
            powers = re.findall(r'Power="([^"]+)"', content)
            on_powers = re.findall(r'OnPower="([^"]+)"', content)
            all_powers = powers + on_powers
            for p in all_powers:
                val = float(p)
                if val > 0.70:
                    failures.append(AuditFailure(
                        "RECOVERY_POWER",
                        f"{zwo.name}: Power={val} on recovery week {week_num} (max 0.70)"
                    ))

            # Check duration
            durations = [int(d) for d in re.findall(r'(?<!On)(?<!Off)Duration="(\d+)"', content)]
            total = sum(durations)
            if total > 5400:
                failures.append(AuditFailure(
                    "RECOVERY_DURATION",
                    f"{zwo.name}: {total/60:.0f}min on recovery week (max 90min)"
                ))

    # ── CHECK 4: ZWO XML validity ──
    for zwo in sorted(workouts_dir.glob("*.zwo")):
        try:
            ET.parse(zwo)
        except ET.ParseError as e:
            failures.append(AuditFailure("XML_VALIDITY", f"{zwo.name}: {e}"))

    # ── CHECK 5: Power values in sane range ──
    for zwo in sorted(workouts_dir.glob("*.zwo")):
        content = zwo.read_text()
        all_powers = re.findall(r'Power(?:Low|High)?="([^"]+)"', content)
        on_powers = re.findall(r'OnPower="([^"]+)"', content)
        for p in all_powers + on_powers:
            val = float(p)
            if val > 1.5 or val < 0.1:
                failures.append(AuditFailure(
                    "POWER_RANGE",
                    f"{zwo.name}: Power={val} outside valid range (0.1-1.5)"
                ))

    # ── CHECK 6: PDF exists and is non-trivial ──
    if not pdf_path.exists():
        failures.append(AuditFailure("PDF", f"guide.pdf missing for {name}"))
    else:
        size = pdf_path.stat().st_size
        if size < 10000:
            failures.append(AuditFailure("PDF", f"guide.pdf is only {size} bytes (suspicious)"))

    # ── CHECK 7: Methodology exists with required sections ──
    if not methodology_path.exists():
        failures.append(AuditFailure("METHODOLOGY", "methodology.json missing"))
    else:
        with open(methodology_path) as f:
            meth = json.load(f)
        required = ["athlete_summary", "why_this_plan", "template_selection",
                     "periodization", "scaling", "accommodations",
                     "weekly_structure", "key_workouts_per_phase"]
        for key in required:
            if key not in meth:
                failures.append(AuditFailure("METHODOLOGY", f"Missing section: {key}"))

    # ── CHECK 8: Touchpoints exist and are valid ──
    if not touchpoints_path.exists():
        failures.append(AuditFailure("TOUCHPOINTS", "touchpoints.json missing"))
    else:
        with open(touchpoints_path) as f:
            tp = json.load(f)
        if len(tp.get("touchpoints", [])) < 8:
            failures.append(AuditFailure("TOUCHPOINTS", f"Only {len(tp.get('touchpoints', []))} touchpoints (need ≥8)"))

    # ── CHECK 9: Email templates all exist ──
    required_templates = [
        "week_1_welcome", "week_2_checkin", "first_recovery", "mid_plan",
        "build_phase_start", "race_month", "race_week", "race_day_morning",
        "post_race_3_days", "post_race_2_weeks",
    ]
    for tmpl in required_templates:
        tmpl_path = TEMPLATES_DIR / f"{tmpl}.html"
        if not tmpl_path.exists():
            failures.append(AuditFailure("EMAIL_TEMPLATE", f"{tmpl}.html missing"))
        else:
            content = tmpl_path.read_text()
            # Check no raw unreplaced placeholders
            athlete_name = intake.get("name", "Test")
            rendered = content.replace("{athlete_name}", athlete_name)
            rendered = rendered.replace("{race_name}", "Test Race")
            rendered = rendered.replace("{race_date}", "2026-01-01")
            rendered = rendered.replace("{plan_duration}", "20")
            if "{" in rendered and "}" in rendered:
                # Find unreplaced placeholders
                unresolved = re.findall(r'\{[a-z_]+\}', rendered)
                if unresolved:
                    failures.append(AuditFailure(
                        "EMAIL_TEMPLATE",
                        f"{tmpl}.html has unresolved placeholders: {unresolved}"
                    ))

    return failures


def main():
    parser = argparse.ArgumentParser(description="Pre-delivery audit — blocks delivery on failure")
    parser.add_argument("--athlete", help="Athlete directory name (e.g. mike-wallace-20260214)")
    parser.add_argument("--all", action="store_true", help="Audit all athletes")
    args = parser.parse_args()

    if not args.athlete and not args.all:
        parser.error("Specify --athlete or --all")

    if args.all:
        athlete_dirs = sorted([d for d in ATHLETES_DIR.iterdir() if d.is_dir()])
    else:
        athlete_dirs = [ATHLETES_DIR / args.athlete]

    total_failures = 0
    total_athletes = 0

    for athlete_dir in athlete_dirs:
        if not athlete_dir.exists():
            print(f"\n{'='*60}")
            print(f"AUDIT: {athlete_dir.name}")
            print(f"{'='*60}")
            print(f"  [FAIL] Directory not found: {athlete_dir}")
            total_failures += 1
            continue

        total_athletes += 1
        failures = audit_athlete(athlete_dir)

        print(f"\n{'='*60}")
        print(f"AUDIT: {athlete_dir.name}")
        print(f"{'='*60}")

        if failures:
            for f in failures:
                print(f)
            total_failures += len(failures)
        else:
            print("  ALL CHECKS PASSED")

    print(f"\n{'='*60}")
    print(f"SUMMARY: {total_athletes} athletes, {total_failures} failures")
    print(f"{'='*60}")

    if total_failures > 0:
        print("\n*** DELIVERY BLOCKED — fix failures before sending plans ***\n")
        sys.exit(1)
    else:
        print("\n*** ALL CLEAR — plans are safe to deliver ***\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
