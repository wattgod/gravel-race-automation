#!/usr/bin/env python3
"""
PIPELINE OUTPUT VALIDATOR — Anti-shortcut enforcement.

This script runs INDEPENDENTLY of the pipeline. It reads the output directory
and verifies everything meets spec. It cannot be weakened by the same AI
that generates the output.

Run after any pipeline execution:
  python3 scripts/validate_pipeline_output.py athletes/sarah-printz-20260213

Exit codes:
  0 = all checks pass
  1 = one or more checks failed

This script is the final defense against shortcuts. If the pipeline passes
its own gates but this script fails, it means the gates were weakened.
"""

import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


class ValidationError:
    def __init__(self, severity: str, check: str, message: str):
        self.severity = severity
        self.check = check
        self.message = message

    def __str__(self):
        return f"[{self.severity}] {self.check}: {self.message}"


def validate_output(athlete_dir: Path) -> list[ValidationError]:
    """Run all validation checks on pipeline output directory."""
    errors: list[ValidationError] = []

    # ── CHECK 1: Required files exist ──────────────────────────
    required_files = [
        "intake.json",
        "profile.yaml",
        "derived.yaml",
        "weekly_structure.yaml",
        "plan_config.yaml",
        "guide.html",
    ]
    for f in required_files:
        if not (athlete_dir / f).exists():
            errors.append(ValidationError("CRITICAL", "FILE_EXISTS", f"Missing: {f}"))

    workouts_dir = athlete_dir / "workouts"
    if not workouts_dir.exists():
        errors.append(ValidationError("CRITICAL", "FILE_EXISTS", "Missing: workouts/ directory"))
        return errors  # Can't check workouts if dir doesn't exist

    # ── CHECK 2: Guide quality (independent of Gate 7) ─────────
    guide_path = athlete_dir / "guide.html"
    if guide_path.exists():
        html = guide_path.read_text(encoding="utf-8")
        guide_size = len(html)

        # HARD MINIMUM: 50KB. This number comes from the plan spec.
        # If you're reading this to change it: DON'T. The plan says 50KB.
        # The guide is the product. 50KB is already generous.
        if guide_size < 50_000:
            errors.append(ValidationError(
                "CRITICAL", "GUIDE_SIZE",
                f"Guide is {guide_size:,} bytes. MINIMUM is 50,000 bytes. "
                f"This threshold is from the plan spec and must not be lowered."
            ))

        if guide_size > 500_000:
            errors.append(ValidationError("HIGH", "GUIDE_SIZE", f"Guide is {guide_size:,} bytes (too large)"))

        # Placeholder check
        placeholders = re.findall(r"\{\{.*?\}\}", html)
        if placeholders:
            errors.append(ValidationError("CRITICAL", "GUIDE_PLACEHOLDERS",
                                          f"Unreplaced: {placeholders[:5]}"))

        # Null/undefined text
        for bad in ["undefined", "null", "None", "NaN"]:
            matches = re.findall(rf">\s*{bad}\s*<", html, re.IGNORECASE)
            if matches:
                errors.append(ValidationError("CRITICAL", "GUIDE_NULLS", f"Found '{bad}' in guide HTML"))

        # Required sections — ALL 14
        required_sections = [
            "race profile", "non-negotiables", "training zones",
            "how adaptation works", "weekly structure", "phase progression",
            "week-by-week overview", "workout execution", "recovery protocol",
            "equipment checklist", "nutrition strategy", "mental preparation",
            "race week", "race day",
        ]
        html_lower = html.lower()
        for section in required_sections:
            if section not in html_lower:
                errors.append(ValidationError("CRITICAL", "GUIDE_SECTIONS",
                                              f"Missing section: '{section}'"))

    # ── CHECK 2b: Guide section ID integrity ─────────────────────
    if guide_path.exists():
        html = guide_path.read_text(encoding="utf-8")

        # Section IDs must be sequential with no gaps
        section_ids = re.findall(r'<section[^>]*id="section-(\d+)"', html)
        if section_ids:
            nums = [int(x) for x in section_ids]
            expected = list(range(1, len(nums) + 1))
            if nums != expected:
                errors.append(ValidationError(
                    "HIGH", "GUIDE_SECTION_IDS",
                    f"Section IDs have gaps. Found: {nums}, expected: {expected}"
                ))

        # TOC links must match body section IDs
        toc_links = re.findall(r'href="#(section-\d+)"', html)
        body_sections = re.findall(r'<section[^>]*id="(section-\d+)"', html)
        for link in toc_links:
            if link not in body_sections:
                errors.append(ValidationError(
                    "CRITICAL", "GUIDE_TOC_BODY_MISMATCH",
                    f"TOC links to #{link} but no matching section in body"
                ))
        for section in body_sections:
            if section not in toc_links:
                errors.append(ValidationError(
                    "CRITICAL", "GUIDE_TOC_BODY_MISMATCH",
                    f"Section {section} exists in body but has no TOC link"
                ))

    # ── CHECK 3: Derived data coherence ────────────────────────
    derived_path = athlete_dir / "derived.yaml"
    if derived_path.exists():
        import yaml
        with open(derived_path) as f:
            derived = yaml.safe_load(f)

        plan_duration = derived.get("plan_duration")
        tier = derived.get("tier")
        race_name = derived.get("race_name")
        race_distance = derived.get("race_distance_miles")

        if plan_duration not in [6, 12, 16, 20]:
            errors.append(ValidationError("CRITICAL", "DERIVED_DURATION",
                                          f"Invalid plan_duration: {plan_duration}"))

        if tier not in ["time_crunched", "finisher", "compete", "podium"]:
            errors.append(ValidationError("CRITICAL", "DERIVED_TIER",
                                          f"Invalid tier: {tier}"))

        # Guide mentions correct distance
        if guide_path.exists() and race_distance:
            html = guide_path.read_text(encoding="utf-8")
            if str(int(race_distance)) not in html:
                errors.append(ValidationError("CRITICAL", "GUIDE_DISTANCE",
                                              f"Guide doesn't mention {race_distance}mi"))

        if guide_path.exists() and race_name:
            html = guide_path.read_text(encoding="utf-8")
            if race_name not in html:
                errors.append(ValidationError("CRITICAL", "GUIDE_RACE_NAME",
                                              f"Guide doesn't mention '{race_name}'"))

    # ── CHECK 4: ZWO file count ────────────────────────────────
    zwo_files = list(workouts_dir.glob("*.zwo"))
    if derived_path.exists():
        import yaml
        with open(derived_path) as f:
            derived = yaml.safe_load(f)
        plan_duration = derived.get("plan_duration", 12)

        # HARD MINIMUM: 7 files per week (every day gets a ZWO)
        min_expected = plan_duration * 7
        if len(zwo_files) < min_expected:
            errors.append(ValidationError(
                "CRITICAL", "ZWO_COUNT",
                f"Only {len(zwo_files)} ZWO files. Need >= {min_expected} "
                f"({plan_duration} weeks x 7 days). Every day gets a file."
            ))

    # ── CHECK 5: ZWO XML validity + TrainingPeaks compliance ──
    for zwo in zwo_files:
        try:
            tree = ET.parse(zwo)
        except ET.ParseError as e:
            errors.append(ValidationError("CRITICAL", "ZWO_XML", f"Invalid XML: {zwo.name}: {e}"))
            continue

        root = tree.getroot()
        if root.tag != "workout_file":
            errors.append(ValidationError("CRITICAL", "ZWO_ROOT", f"Wrong root tag in {zwo.name}"))

        # Required elements for TrainingPeaks
        for elem_name in ["name", "description", "sportType", "workout", "tags"]:
            if root.find(elem_name) is None:
                errors.append(ValidationError("HIGH", "ZWO_STRUCTURE",
                                              f"Missing <{elem_name}> in {zwo.name}"))

        # Workout name must contain a date (YYYY-MM-DD) or "Race Day"
        name_elem = root.find("name")
        if name_elem is not None and name_elem.text:
            name_text = name_elem.text
            has_date = bool(re.search(r"\d{4}-\d{2}-\d{2}", name_text))
            is_race_day = "race day" in name_text.lower()
            if not has_date and not is_race_day:
                errors.append(ValidationError("HIGH", "ZWO_DATE_IN_NAME",
                                              f"No date in name: {zwo.name} -> '{name_text}'"))

        # Power target sanity
        workout = root.find("workout")
        if workout is not None:
            for elem in workout.iter():
                for attr in ["Power", "PowerLow", "PowerHigh", "OnPower", "OffPower"]:
                    if attr in elem.attrib:
                        try:
                            power = float(elem.attrib[attr])
                        except ValueError:
                            errors.append(ValidationError("CRITICAL", "ZWO_POWER",
                                                          f"Non-numeric power in {zwo.name}"))
                            continue
                        if power < 0.3 or power > 2.0:
                            errors.append(ValidationError("CRITICAL", "ZWO_POWER",
                                                          f"Insane power {power} in {zwo.name}"))

                if "Duration" in elem.attrib:
                    try:
                        dur = int(elem.attrib["Duration"])
                        if dur <= 0:
                            errors.append(ValidationError("CRITICAL", "ZWO_DURATION",
                                                          f"Bad duration {dur} in {zwo.name}"))
                    except ValueError:
                        errors.append(ValidationError("CRITICAL", "ZWO_DURATION",
                                                      f"Non-numeric duration in {zwo.name}"))

    # ── CHECK 6: Strength workouts exist ───────────────────────
    strength_files = [f for f in zwo_files if "Strength" in f.name or "strength" in f.name]
    if not strength_files:
        errors.append(ValidationError("CRITICAL", "ZWO_STRENGTH", "No strength ZWO files found"))

    # ── CHECK 7: Rest day files exist ──────────────────────────
    rest_files = [f for f in zwo_files if "Rest" in f.name or "Off" in f.name]
    if not rest_files:
        errors.append(ValidationError("CRITICAL", "ZWO_REST", "No rest day ZWO files found"))

    # ── CHECK 8: FTP test files exist ──────────────────────────
    ftp_files = [f for f in zwo_files if "FTP" in f.name or "ftp" in f.name]
    if not ftp_files:
        errors.append(ValidationError("HIGH", "ZWO_FTP", "No FTP test ZWO files found"))

    # ── CHECK 9: Race day workout exists ───────────────────────
    race_day_files = [f for f in zwo_files if "Race_Day" in f.name or "race_day" in f.name]
    if not race_day_files:
        errors.append(ValidationError("HIGH", "ZWO_RACE_DAY", "No race day ZWO file found"))

    return errors


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/validate_pipeline_output.py <athlete_dir>")
        print("Example: python3 scripts/validate_pipeline_output.py athletes/sarah-printz-20260213")
        sys.exit(1)

    athlete_dir = Path(sys.argv[1])
    if not athlete_dir.exists():
        print(f"ERROR: Directory not found: {athlete_dir}")
        sys.exit(1)

    print(f"{'='*60}")
    print(f"PIPELINE OUTPUT VALIDATOR")
    print(f"Directory: {athlete_dir}")
    print(f"{'='*60}")
    print()

    errors = validate_output(athlete_dir)

    if not errors:
        print("ALL CHECKS PASSED")
        print()
        print("This output meets the plan specification:")
        print("  - Guide: 50KB+, 14 sections, no placeholders, no nulls")
        print("  - ZWO files: 7/week, valid XML, sane power, dates in names")
        print("  - Strength, rest, FTP test, and race day files present")
        print("  - Race name and distance verified in guide")
        sys.exit(0)
    else:
        critical = [e for e in errors if e.severity == "CRITICAL"]
        high = [e for e in errors if e.severity == "HIGH"]
        medium = [e for e in errors if e.severity == "MEDIUM"]

        if critical:
            print(f"CRITICAL FAILURES: {len(critical)}")
            for e in critical:
                print(f"  {e}")
            print()

        if high:
            print(f"HIGH PRIORITY ISSUES: {len(high)}")
            for e in high:
                print(f"  {e}")
            print()

        if medium:
            print(f"MEDIUM ISSUES: {len(medium)}")
            for e in medium:
                print(f"  {e}")
            print()

        print(f"TOTAL ISSUES: {len(errors)} ({len(critical)} critical, {len(high)} high, {len(medium)} medium)")
        sys.exit(1)


if __name__ == "__main__":
    main()
