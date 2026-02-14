#!/usr/bin/env python3
"""
TRIGGER INTEGRITY CHECK — Detects duplicated conditional section logic.

The conditional section triggers (altitude > 5000ft, sex == female, age >= 40)
must exist in ONE place: _conditional_triggers(). If someone duplicates this
logic in _build_section_titles() or _build_full_guide(), this script fails.

WHY THIS EXISTS: On Feb 13, 2026, the TOC builder and body builder had
different altitude trigger logic. The TOC checked 2 conditions, the body
checked 3. This caused the altitude section to appear in the body but not
in the TOC for certain race data. The test that should have caught this
used a fixture where all 3 elevation values were high, so the divergence
was invisible.

This script makes the root cause (duplicated logic) impossible to reintroduce.

Exit codes:
  0 = trigger logic is centralized in _conditional_triggers
  1 = duplicated trigger logic found
"""

import re
import sys
from pathlib import Path


# Patterns that indicate trigger logic duplication.
# If these patterns appear in any function EXCEPT _conditional_triggers,
# it means someone re-implemented the trigger logic instead of calling
# the shared function.
TRIGGER_PATTERNS = [
    # Altitude: checking elevation against 5000
    (r'>\s*5000', "altitude threshold check (> 5000)"),
    # Women: checking sex == female
    (r'sex\.lower\(\)\s*==\s*["\']female["\']', "sex == female check"),
    # Masters: checking age >= 40
    (r'int\(age\)\s*>=\s*40', "age >= 40 check"),
]


def check_trigger_isolation(guide_path: Path) -> list[str]:
    """Verify trigger logic only exists in _conditional_triggers."""
    issues = []
    source = guide_path.read_text(encoding="utf-8")
    lines = source.split("\n")

    # Find function boundaries
    functions = []
    current_func = None
    current_start = None
    indent = 0

    for i, line in enumerate(lines):
        func_match = re.match(r'^def (_\w+)\(', line)
        if func_match:
            if current_func:
                functions.append((current_func, current_start, i - 1))
            current_func = func_match.group(1)
            current_start = i

    if current_func:
        functions.append((current_func, current_start, len(lines) - 1))

    # Only check section-inclusion functions for trigger duplication.
    # _build_section_titles and _build_full_guide decide WHICH sections exist.
    # Content-rendering functions (e.g. _section_non_negotiables using > 5000
    # to show an altitude warning within a section) are legitimate.
    SECTION_INCLUSION_FUNCS = {"_build_section_titles", "_build_full_guide"}

    for func_name, start, end in functions:
        if func_name == "_conditional_triggers":
            continue  # This is the CORRECT location for trigger logic
        if func_name not in SECTION_INCLUSION_FUNCS:
            continue  # Content-rendering functions can use elevation data

        func_body = "\n".join(lines[start:end+1])

        for pattern, description in TRIGGER_PATTERNS:
            matches = re.findall(pattern, func_body)
            if matches:
                issues.append(
                    f"DUPLICATED TRIGGER LOGIC in {func_name}() (line {start+1}): "
                    f"Found {description}. "
                    f"This logic MUST only exist in _conditional_triggers(). "
                    f"Call _conditional_triggers() instead of re-checking."
                )

    # Also verify _conditional_triggers actually exists
    func_names = [f[0] for f in functions]
    if "_conditional_triggers" not in func_names:
        issues.append(
            "MISSING: _conditional_triggers() function not found. "
            "Someone deleted the single source of truth for trigger logic."
        )

    # Verify _build_section_titles calls _conditional_triggers
    for func_name, start, end in functions:
        if func_name == "_build_section_titles":
            func_body = "\n".join(lines[start:end+1])
            if "_conditional_triggers" not in func_body:
                issues.append(
                    "_build_section_titles() does not call _conditional_triggers(). "
                    "It must use the shared trigger function."
                )

    return issues


def main():
    guide_path = Path(__file__).parent.parent / "pipeline" / "step_07_guide.py"
    if not guide_path.exists():
        print("ERROR: pipeline/step_07_guide.py not found")
        sys.exit(1)

    print(f"{'='*60}")
    print("TRIGGER INTEGRITY CHECK")
    print(f"Checking: {guide_path}")
    print(f"{'='*60}")
    print()

    issues = check_trigger_isolation(guide_path)

    if not issues:
        print("TRIGGER LOGIC IS CENTRALIZED")
        print()
        print("_conditional_triggers() is the single source of truth.")
        print("No duplicated trigger logic found in other functions.")
        sys.exit(0)
    else:
        print(f"TRIGGER INTEGRITY VIOLATIONS: {len(issues)}")
        print()
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        print("FIX: Remove duplicated logic and call _conditional_triggers() instead.")
        sys.exit(1)


if __name__ == "__main__":
    main()
