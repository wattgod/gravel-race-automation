#!/usr/bin/env python3
"""Validate generated video scripts for quality and completeness.

Checks:
- Required sections present for each format
- Narration word count within duration range
- No mangled numbers (years converted, number-ranges with "thousand")
- No empty sections (placeholder text from missing data)
- CTA includes correct slug
- RIFF markers present

Usage:
    python scripts/validate_video_scripts.py                    # validate all in video-scripts/
    python scripts/validate_video_scripts.py --dir video-scripts/tier-reveal
    python scripts/validate_video_scripts.py --strict           # exit 1 on any warning
"""

import argparse
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Required sections per format
REQUIRED_SECTIONS = {
    "tier-reveal": ["HOOK", "SETUP", "EVIDENCE", "REVEAL", "CTA", "ENGAGEMENT"],
    "head-to-head": ["HOOK", "TALE OF THE TAPE", "DIMENSION BREAKDOWN", "VERDICT", "CTA", "ENGAGEMENT"],
    "should-you-race": ["HOOK", "THE COURSE", "THE SCORES", "STRENGTHS", "WEAKNESSES", "LOGISTICS", "VERDICT", "ALTERNATIVES", "CTA", "ENGAGEMENT"],
    "roast": ["HOOK", "WHAT THEY TELL YOU", "WHAT THEY DON'T TELL YOU", "THE NUMBERS DON'T LIE", "THE BOTTOM LINE", "CTA", "ENGAGEMENT"],
    "suffering-map": ["HOOK", "THE SUFFERING ZONES", "CTA", "ENGAGEMENT"],
    "data-drops": ["DROP:"],
}

# Spoken word count ranges (narration only) for format durations
# Based on 2.5 words/second + riff allowance
WORD_COUNT_RANGES = {
    "tier-reveal": (40, 250),       # 30-90s
    "head-to-head": (150, 600),     # 2-3 min
    "should-you-race": (500, 2000), # 5-10 min
    "roast": (150, 700),            # 2-4 min
    "suffering-map": (20, 200),     # 15-60s
    "data-drops": (100, 800),       # multiple 15-30s drops
}

# Patterns that indicate mangled output
MANGLED_PATTERNS = [
    (r"\b\d+ thousand['']s\b", "year converted to 'N thousand's'"),
    (r"\b\d+ thousand rain\b", "year converted to 'N thousand rain'"),
    (r"\b\d+\.?\d* thousand-\d+\.?\d* thousand\b", "number range mangled to 'N thousand-N thousand'"),
    (r"We struggled to find highlights", "placeholder text from empty strengths"),
    (r"Look, every race has its issues", "placeholder text from empty weaknesses"),
    (r"No specific strengths listed", "placeholder text from empty strengths"),
    (r"No specific weaknesses listed", "placeholder text from empty weaknesses"),
]


def count_narration_words(text):
    """Count words in quoted narration lines only."""
    count = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith('"') and stripped.endswith('"'):
            count += len(stripped.split())
        elif stripped.startswith('- "') and stripped.endswith('"'):
            count += len(stripped.split())
    return count


def detect_format(filepath):
    """Detect the script format from its directory or content."""
    parent = filepath.parent.name
    if parent in REQUIRED_SECTIONS:
        return parent
    # Try to detect from content
    text = filepath.read_text()
    if "# FORMAT: Tier Reveal" in text:
        return "tier-reveal"
    if "# FORMAT: Head-to-Head" in text:
        return "head-to-head"
    if "# FORMAT: Should You Race" in text:
        return "should-you-race"
    if "# FORMAT: Race Roast" in text:
        return "roast"
    if "# FORMAT: Suffering Map" in text:
        return "suffering-map"
    if "# FORMAT: Data Drops" in text:
        return "data-drops"
    return None


def validate_script(filepath):
    """Validate a single script file. Returns list of (level, message) tuples."""
    issues = []
    text = filepath.read_text()
    fmt = detect_format(filepath)
    slug = filepath.stem

    if not fmt:
        issues.append(("ERROR", "Could not detect format"))
        return issues

    # Check required sections
    required = REQUIRED_SECTIONS.get(fmt, [])
    for section in required:
        if f"## {section}" not in text and section not in text:
            issues.append(("ERROR", f"Missing required section: {section}"))

    # Check narration word count
    word_count = count_narration_words(text)
    if fmt in WORD_COUNT_RANGES:
        lo, hi = WORD_COUNT_RANGES[fmt]
        if word_count < lo:
            issues.append(("WARNING", f"Narration too short: {word_count} words (expected {lo}-{hi})"))
        elif word_count > hi:
            issues.append(("WARNING", f"Narration too long: {word_count} words (expected {lo}-{hi})"))

    # Check for mangled patterns
    for pattern, description in MANGLED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append(("ERROR", f"Mangled output: {description}"))

    # Check RIFF markers present (except data-drops)
    if fmt != "data-drops" and "[RIFF HERE" not in text:
        issues.append(("WARNING", f"No [RIFF HERE] markers — script may be too rigid"))

    # Check CTA includes slug (except data-drops and head-to-head)
    if fmt not in ("data-drops", "head-to-head"):
        if f"gravelgodcycling.com/race/{slug}" not in text:
            issues.append(("WARNING", f"CTA missing race URL for {slug}"))

    # Check for empty narration lines
    empty_narration = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped == '""':
            empty_narration += 1
    if empty_narration:
        issues.append(("WARNING", f"{empty_narration} empty narration lines"))

    return issues


def main():
    parser = argparse.ArgumentParser(description="Validate generated video scripts")
    parser.add_argument("--dir", default=str(PROJECT_ROOT / "video-scripts"),
                        help="Directory to validate")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any warning (not just errors)")
    args = parser.parse_args()

    scripts_dir = Path(args.dir)
    if not scripts_dir.exists():
        print(f"ERROR: Directory not found: {scripts_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(scripts_dir.rglob("*.md"))
    if not files:
        print(f"No .md files found in {scripts_dir}")
        sys.exit(1)

    total_errors = 0
    total_warnings = 0
    total_ok = 0

    for filepath in files:
        issues = validate_script(filepath)
        errors = [i for i in issues if i[0] == "ERROR"]
        warnings = [i for i in issues if i[0] == "WARNING"]

        if errors or warnings:
            rel = filepath.relative_to(scripts_dir)
            for level, msg in issues:
                icon = "X" if level == "ERROR" else "!"
                print(f"  [{icon}] {rel}: {msg}")
            total_errors += len(errors)
            total_warnings += len(warnings)
        else:
            total_ok += 1

    print(f"\n{len(files)} scripts checked: {total_ok} OK, "
          f"{total_errors} errors, {total_warnings} warnings")

    if total_errors > 0:
        sys.exit(1)
    if args.strict and total_warnings > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
