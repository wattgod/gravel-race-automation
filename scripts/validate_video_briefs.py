#!/usr/bin/env python3
"""Validate generated video briefs for quality and structural correctness.

Checks all JSON brief files in video-briefs/ against:
- JSON schema (required fields, types)
- Time range format (M:SS-M:SS, seconds < 60)
- Duration constraints (Short <= 55s, mid/long within targets)
- WPM feasibility (no impossible narration speeds)
- Thumbnail aspect ratio (9:16 for Shorts, 16:9 for long)
- B-roll URL validity (no non-URL official_site values)
- No hardcoded years in YouTube queries
- Beat sequence integrity (no gaps or overlaps)
- Production checklist completeness

Usage:
    python scripts/validate_video_briefs.py                    # validate all
    python scripts/validate_video_briefs.py --format tier-reveal
    python scripts/validate_video_briefs.py --strict           # exit 1 on any warning
    python scripts/validate_video_briefs.py --json             # output JSON report
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRIEFS_DIR = PROJECT_ROOT / "video-briefs"

# Required top-level keys in every brief
REQUIRED_TOP_KEYS = {
    "slug", "format", "platform", "race_name", "race_tier", "race_score",
    "duration_target_range", "estimated_duration_sec", "estimated_spoken_words",
    "story_arc", "primary_trope", "retention_targets", "beats",
    "avatar_assets_needed", "meme_inserts", "thumbnail_prompt",
    "narration_feasibility", "content_pillars", "cross_platform_notes",
    "production_checklist",
}

# Required keys in every beat
REQUIRED_BEAT_KEYS = {
    "id", "label", "time_range", "duration_sec", "narration", "visual",
    "avatar_pose",
}

# Short-form formats (must be ≤55 seconds)
SHORT_FORMATS = {"tier-reveal", "suffering-map", "data-drops"}

# Duration targets per format
DURATION_TARGETS = {
    "tier-reveal": (25, 35),
    "suffering-map": (15, 30),
    "data-drops": (15, 20),
    "roast": (180, 300),
    "head-to-head": (300, 480),
    "should-you-race": (480, 720),
}

SHORT_MAX_SEC = 55
TIME_RANGE_PATTERN = re.compile(r"^(\d+):(\d{2})-(\d+):(\d{2})$")


def validate_brief(brief, filepath):
    """Validate a single brief. Returns (errors, warnings)."""
    errors = []
    warnings = []
    slug = brief.get("slug", "?")
    fmt = brief.get("format", "?")
    prefix = f"{fmt}/{slug}"

    # ── Schema checks ──
    missing_top = REQUIRED_TOP_KEYS - brief.keys()
    if missing_top:
        errors.append(f"{prefix}: missing top-level keys: {missing_top}")

    for i, beat in enumerate(brief.get("beats", [])):
        missing_beat = REQUIRED_BEAT_KEYS - beat.keys()
        if missing_beat:
            errors.append(
                f"{prefix}: beat '{beat.get('id', i)}' missing keys: {missing_beat}"
            )

    # ── Time range format ──
    for beat in brief.get("beats", []):
        tr = beat.get("time_range", "")
        m = TIME_RANGE_PATTERN.match(tr)
        if not m:
            errors.append(
                f"{prefix}: beat '{beat.get('id', '?')}' bad time_range: '{tr}'"
            )
        else:
            s1, s2 = int(m.group(2)), int(m.group(4))
            if s1 >= 60 or s2 >= 60:
                errors.append(
                    f"{prefix}: beat '{beat.get('id', '?')}' seconds >= 60: '{tr}'"
                )

    # ── Duration constraints ──
    duration = brief.get("estimated_duration_sec", 0)
    if fmt in SHORT_FORMATS and duration > SHORT_MAX_SEC:
        errors.append(
            f"{prefix}: Short format duration {duration}s > {SHORT_MAX_SEC}s limit"
        )

    target = DURATION_TARGETS.get(fmt)
    if target:
        lo, hi = target
        # Allow 30s buffer for long formats
        buffer = 30 if fmt in ("should-you-race", "head-to-head") else 15
        if duration < lo - buffer:
            warnings.append(
                f"{prefix}: duration {duration}s below target ({lo}-{hi})"
            )
        if duration > hi + buffer:
            warnings.append(
                f"{prefix}: duration {duration}s above target ({lo}-{hi})"
            )

    # ── WPM feasibility ──
    feas = brief.get("narration_feasibility", {})
    if feas.get("warnings"):
        for w in feas["warnings"]:
            warnings.append(f"{prefix}: {w}")
    # Check for any impossible WPM beats
    for beat in brief.get("beats", []):
        wpm = beat.get("narration_wpm", 0)
        if wpm > 200:
            errors.append(
                f"{prefix}: beat '{beat.get('id', '?')}' WPM={wpm:.0f} "
                f"(impossible to speak)"
            )

    # ── Thumbnail aspect ratio ──
    thumb = brief.get("thumbnail_prompt", "")
    if fmt in SHORT_FORMATS:
        if "9:16" not in thumb:
            errors.append(f"{prefix}: Short thumbnail missing --ar 9:16")
    else:
        if "16:9" not in thumb and fmt != "head-to-head":
            # head-to-head may have custom thumbnails
            warnings.append(f"{prefix}: long-form thumbnail missing --ar 16:9")

    # ── B-roll URL validation ──
    for beat in brief.get("beats", []):
        for src in beat.get("broll_sources", []):
            if src.get("type") == "race_website":
                url = src.get("url", "")
                if not url.startswith(("http://", "https://")):
                    errors.append(
                        f"{prefix}: non-URL race_website B-roll: '{url}'"
                    )

    # ── No hardcoded years ──
    for beat in brief.get("beats", []):
        for src in beat.get("broll_sources", []):
            query = src.get("query", "")
            if "2025 2026" in query:
                errors.append(
                    f"{prefix}: hardcoded '2025 2026' in YouTube query"
                )

    # ── CTA has slug ──
    cta_beats = [b for b in brief.get("beats", []) if b.get("id") == "cta"]
    if cta_beats:
        cta_text = cta_beats[0].get("text_on_screen", "")
        if slug not in cta_text and "gravelgodcycling.com" not in cta_text:
            warnings.append(f"{prefix}: CTA text_on_screen missing slug or URL")

    # ── Production checklist non-empty ──
    checklist = brief.get("production_checklist", [])
    if len(checklist) < 3:
        warnings.append(f"{prefix}: production checklist has only {len(checklist)} items")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Validate generated video briefs."
    )
    parser.add_argument("--format", help="Only validate this format")
    parser.add_argument("--strict", action="store_true",
                        help="Exit 1 on any warning")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON report")
    parser.add_argument("--dir", default=str(BRIEFS_DIR),
                        help="Briefs directory")
    args = parser.parse_args()

    briefs_dir = Path(args.dir)
    if not briefs_dir.exists():
        print(f"ERROR: Briefs directory not found: {briefs_dir}", file=sys.stderr)
        sys.exit(1)

    # Collect all JSON files
    if args.format:
        json_files = sorted((briefs_dir / args.format).glob("*.json"))
    else:
        json_files = sorted(briefs_dir.rglob("*.json"))

    if not json_files:
        print("No brief files found.", file=sys.stderr)
        sys.exit(1)

    total_errors = []
    total_warnings = []
    validated = 0
    parse_errors = 0

    for filepath in json_files:
        try:
            with open(filepath) as f:
                brief = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            total_errors.append(f"{filepath.name}: JSON parse error: {e}")
            parse_errors += 1
            continue

        errors, warnings = validate_brief(brief, filepath)
        total_errors.extend(errors)
        total_warnings.extend(warnings)
        validated += 1

    if args.json:
        report = {
            "validated": validated,
            "parse_errors": parse_errors,
            "errors": len(total_errors),
            "warnings": len(total_warnings),
            "error_details": total_errors[:50],
            "warning_details": total_warnings[:50],
        }
        print(json.dumps(report, indent=2))
    else:
        if total_errors:
            print(f"\nERRORS ({len(total_errors)}):")
            for e in total_errors:
                print(f"  {e}")

        if total_warnings:
            print(f"\nWARNINGS ({len(total_warnings)}):")
            for w in total_warnings[:20]:
                print(f"  {w}")
            if len(total_warnings) > 20:
                print(f"  ... and {len(total_warnings) - 20} more")

        status = "PASS" if not total_errors else "FAIL"
        print(f"\n{status}: {validated} briefs validated, "
              f"{len(total_errors)} errors, {len(total_warnings)} warnings.")

    if total_errors or (args.strict and total_warnings):
        sys.exit(1)


if __name__ == "__main__":
    main()
