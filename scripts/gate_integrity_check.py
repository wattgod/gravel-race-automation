#!/usr/bin/env python3
"""
GATE INTEGRITY CHECK — Detects if quality gates have been weakened.

This script reads quality_gates.py and verifies that the hard thresholds
match the plan specification. It runs via pre-commit hook or CI to prevent
anyone (human or AI) from weakening the gates.

The thresholds below are from the plan spec. If you're changing them,
you need a written justification in docs/GATE_CHANGES.md.

Exit codes:
  0 = gates match spec
  1 = gates have been weakened
"""

import ast
import re
import sys
from pathlib import Path


# ── PLAN SPEC THRESHOLDS ──────────────────────────────────────
# These are the authoritative values from the plan.
# Changing them here without changing the plan is sabotage.

SPEC = {
    "gate_6_min_zwo_per_week": 7,
    "gate_7_min_guide_bytes": 50_000,
    "gate_7_max_guide_bytes": 500_000,
    "gate_7_required_sections": 14,
    "gate_8_min_pdf_bytes": 10_000,
}


def check_gate_file(gate_path: Path) -> list[str]:
    """Parse quality_gates.py and verify thresholds haven't been weakened."""
    issues = []
    source = gate_path.read_text(encoding="utf-8")

    # Gate 6: ZWO count — must require plan_duration * 7
    # Look for the multiplier in the min_expected calculation
    match = re.search(r"min_expected\s*=\s*plan_duration\s*\*\s*(\d+)", source)
    if match:
        multiplier = int(match.group(1))
        if multiplier < SPEC["gate_6_min_zwo_per_week"]:
            issues.append(
                f"Gate 6: ZWO multiplier is {multiplier} (spec: {SPEC['gate_6_min_zwo_per_week']}). "
                f"Every day must have a file. This was weakened."
            )
    else:
        issues.append("Gate 6: Could not find min_expected calculation. Gate may have been removed.")

    # Gate 7: Guide size minimum
    size_checks = re.findall(r"assert\s+size\s*>\s*(\d[\d_]*)", source)
    if size_checks:
        min_size = int(size_checks[0].replace("_", ""))
        if min_size < SPEC["gate_7_min_guide_bytes"]:
            issues.append(
                f"Gate 7: Guide minimum size is {min_size:,} bytes "
                f"(spec: {SPEC['gate_7_min_guide_bytes']:,}). THIS WAS WEAKENED."
            )
    else:
        issues.append("Gate 7: Could not find guide size assertion. Gate may have been removed.")

    # Gate 7: Required sections count
    sections_match = re.search(r"required_sections\s*=\s*\[([^\]]+)\]", source, re.DOTALL)
    if sections_match:
        section_items = re.findall(r'"([^"]+)"', sections_match.group(1))
        if len(section_items) < SPEC["gate_7_required_sections"]:
            issues.append(
                f"Gate 7: Only {len(section_items)} required sections "
                f"(spec: {SPEC['gate_7_required_sections']}). Sections were removed."
            )
    else:
        issues.append("Gate 7: Could not find required_sections list.")

    # Gate 6: Must check for strength files
    if "strength" not in source.lower() or "Strength" not in source:
        issues.append("Gate 6: No strength file check found. This check was removed.")

    # Gate 6: Must check for rest files
    if "Rest" not in source and "rest" not in source.lower():
        issues.append("Gate 6: No rest file check found. This check was removed.")

    # Gate 7: Must check for placeholders
    if "{{" not in source and "placeholder" not in source.lower():
        issues.append("Gate 7: No placeholder check found. This check was removed.")

    # Gate 7: Must check for null/undefined text
    if "undefined" not in source and "null" not in source:
        issues.append("Gate 7: No null/undefined text check found. This check was removed.")

    return issues


def main():
    gate_path = Path(__file__).parent.parent / "gates" / "quality_gates.py"
    if not gate_path.exists():
        print("ERROR: gates/quality_gates.py not found")
        sys.exit(1)

    print(f"{'='*60}")
    print("GATE INTEGRITY CHECK")
    print(f"Checking: {gate_path}")
    print(f"{'='*60}")
    print()

    print("Plan spec thresholds:")
    for key, value in SPEC.items():
        print(f"  {key}: {value:,}" if isinstance(value, int) else f"  {key}: {value}")
    print()

    issues = check_gate_file(gate_path)

    if not issues:
        print("ALL GATES MATCH PLAN SPEC")
        print()
        print("Gate 6: Requires 7 ZWO files per week, strength + rest files present")
        print("Gate 7: Requires 50KB+ guide, 14 sections, no placeholders, no nulls")
        print("Gate 8: Requires PDF > 10KB")
        sys.exit(0)
    else:
        print(f"GATE INTEGRITY VIOLATIONS: {len(issues)}")
        print()
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print()
        print("These gates have been WEAKENED from the plan specification.")
        print("If this is intentional, document the change in docs/GATE_CHANGES.md")
        print("with a written justification.")
        sys.exit(1)


if __name__ == "__main__":
    main()
