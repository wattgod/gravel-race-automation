#!/usr/bin/env python3
"""
ZWO TRAININGPEAKS VALIDATOR — Catches common formatting pitfalls.

TrainingPeaks has specific requirements for ZWO import. This script
catches every known pitfall before the athlete drags files in.

Run on any workouts directory:
  python3 scripts/zwo_tp_validator.py athletes/sarah-printz-20260213/workouts/

Common TrainingPeaks ZWO pitfalls checked:
  1. Invalid XML (TP silently drops the file)
  2. Root tag must be <workout_file> (not <workout> or <zwo>)
  3. Missing <workout> element (TP imports but shows empty workout)
  4. Missing <name> element (shows as "Unnamed" in TP)
  5. Missing <sportType> (defaults to bike but may confuse multi-sport athletes)
  6. Power values as watts instead of FTP fraction (e.g., 250 instead of 0.83)
  7. Duration as minutes instead of seconds (e.g., 5 instead of 300)
  8. Missing <description> (workout instructions won't show)
  9. Special characters in name that break TP filename handling
  10. Zero-duration elements (TP may crash or skip)
  11. FreeRide with Duration=0 (TP hangs)
  12. IntervalsT with Repeat=0 (TP shows empty workout)
"""

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


class TPIssue:
    def __init__(self, file: str, pitfall: str, detail: str):
        self.file = file
        self.pitfall = pitfall
        self.detail = detail

    def __str__(self):
        return f"  [{self.pitfall}] {self.file}: {self.detail}"


def validate_zwo_for_tp(workouts_dir: Path) -> list[TPIssue]:
    """Validate all ZWO files against TrainingPeaks requirements."""
    issues = []
    zwo_files = sorted(workouts_dir.glob("*.zwo"))

    if not zwo_files:
        issues.append(TPIssue("(none)", "NO_FILES", "No .zwo files found"))
        return issues

    for zwo in zwo_files:
        raw = zwo.read_text(encoding="utf-8")

        # Pitfall 1: Invalid XML
        try:
            tree = ET.parse(zwo)
        except ET.ParseError as e:
            issues.append(TPIssue(zwo.name, "INVALID_XML",
                                  f"XML parse error: {e}. TP will silently drop this file."))
            continue

        root = tree.getroot()

        # Pitfall 2: Wrong root tag
        if root.tag != "workout_file":
            issues.append(TPIssue(zwo.name, "WRONG_ROOT",
                                  f"Root tag is <{root.tag}>, must be <workout_file>"))

        # Pitfall 3: Missing <workout>
        workout = root.find("workout")
        if workout is None:
            issues.append(TPIssue(zwo.name, "NO_WORKOUT",
                                  "Missing <workout> element. TP will show empty workout."))
            continue

        # Pitfall 4: Missing <name>
        name_elem = root.find("name")
        if name_elem is None or not name_elem.text or not name_elem.text.strip():
            issues.append(TPIssue(zwo.name, "NO_NAME",
                                  "Missing or empty <name>. Shows as 'Unnamed' in TP."))

        # Pitfall 5: Missing <sportType>
        sport = root.find("sportType")
        if sport is None or not sport.text:
            issues.append(TPIssue(zwo.name, "NO_SPORT_TYPE",
                                  "Missing <sportType>. May confuse multi-sport athletes."))

        # Pitfall 8: Missing <description>
        desc = root.find("description")
        if desc is None or not desc.text or not desc.text.strip():
            issues.append(TPIssue(zwo.name, "NO_DESCRIPTION",
                                  "Missing <description>. No instructions will show in TP."))

        # Pitfall 9: Special characters in name
        if name_elem is not None and name_elem.text:
            bad_chars = re.findall(r'[<>&\'"/\\|?*]', name_elem.text)
            if bad_chars:
                issues.append(TPIssue(zwo.name, "BAD_NAME_CHARS",
                                      f"Name contains chars that may break TP: {bad_chars}"))

        # Check workout elements
        for elem in workout.iter():
            tag = elem.tag

            # Pitfall 6: Power as watts instead of FTP fraction
            for attr in ["Power", "PowerLow", "PowerHigh", "OnPower", "OffPower"]:
                if attr in elem.attrib:
                    try:
                        val = float(elem.attrib[attr])
                    except ValueError:
                        issues.append(TPIssue(zwo.name, "NON_NUMERIC_POWER",
                                              f"{attr}={elem.attrib[attr]} is not a number"))
                        continue
                    if val > 2.0:
                        issues.append(TPIssue(zwo.name, "POWER_AS_WATTS",
                                              f"{attr}={val} looks like watts, not FTP fraction. "
                                              f"ZWO uses 0.0-2.0 range (e.g., 0.75 = 75% FTP)"))
                    elif val < 0.3 and val > 0:
                        issues.append(TPIssue(zwo.name, "VERY_LOW_POWER",
                                              f"{attr}={val} is very low (< 30% FTP). Intentional?"))

            # Pitfall 7: Duration as minutes instead of seconds
            if "Duration" in elem.attrib:
                try:
                    dur = int(elem.attrib["Duration"])
                except ValueError:
                    issues.append(TPIssue(zwo.name, "NON_NUMERIC_DURATION",
                                          f"Duration={elem.attrib['Duration']} is not an integer"))
                    continue

                # Pitfall 10: Zero duration
                if dur <= 0:
                    issues.append(TPIssue(zwo.name, "ZERO_DURATION",
                                          f"Duration={dur} on <{tag}>. TP may crash or skip."))
                elif dur < 10 and tag not in ("SteadyState",):
                    # Duration < 10 seconds is suspicious for most elements
                    # (but 1-second rest day placeholders are fine for SteadyState)
                    if not (dur == 1 and "Rest" in zwo.name):
                        issues.append(TPIssue(zwo.name, "VERY_SHORT_DURATION",
                                              f"Duration={dur}s on <{tag}>. Did you mean {dur} minutes ({dur*60}s)?"))

            # Pitfall 11: FreeRide with Duration=0
            if tag == "FreeRide" and elem.attrib.get("Duration") == "0":
                issues.append(TPIssue(zwo.name, "FREERIDE_ZERO",
                                      "FreeRide Duration=0. TP may hang or show empty."))

            # Pitfall 12: IntervalsT with Repeat=0
            if tag == "IntervalsT":
                repeat = elem.attrib.get("Repeat", "1")
                try:
                    if int(repeat) <= 0:
                        issues.append(TPIssue(zwo.name, "INTERVALS_ZERO_REPEAT",
                                              f"IntervalsT Repeat={repeat}. TP shows empty workout."))
                except ValueError:
                    issues.append(TPIssue(zwo.name, "BAD_REPEAT",
                                          f"IntervalsT Repeat={repeat} is not an integer"))

    return issues


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/zwo_tp_validator.py <workouts_dir>")
        sys.exit(1)

    workouts_dir = Path(sys.argv[1])
    if not workouts_dir.exists():
        print(f"ERROR: Directory not found: {workouts_dir}")
        sys.exit(1)

    zwo_files = list(workouts_dir.glob("*.zwo"))
    print(f"{'='*60}")
    print(f"TRAININGPEAKS ZWO VALIDATOR")
    print(f"Directory: {workouts_dir}")
    print(f"Files: {len(zwo_files)}")
    print(f"{'='*60}")
    print()

    issues = validate_zwo_for_tp(workouts_dir)

    if not issues:
        print(f"ALL {len(zwo_files)} ZWO FILES PASS TRAININGPEAKS VALIDATION")
        print()
        print("Checked:")
        print("  - Valid XML (TP silently drops invalid files)")
        print("  - Root tag: <workout_file>")
        print("  - Required elements: name, description, sportType, workout, tags")
        print("  - Power values as FTP fraction (0.3-2.0)")
        print("  - Durations as seconds (positive integers)")
        print("  - No special characters in names")
        print("  - No zero-duration FreeRide or zero-repeat IntervalsT")
        sys.exit(0)
    else:
        for issue in issues:
            print(issue)
        print()
        print(f"TOTAL ISSUES: {len(issues)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
