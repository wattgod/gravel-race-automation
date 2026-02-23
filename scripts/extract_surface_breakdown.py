#!/usr/bin/env python3
"""
Extract surface composition breakdowns from research dumps.

Finds patterns like:
  "86% gravel/12% paved/2% trail"
  "85% gravel, 10% pavement, 5% singletrack"
  "Surface breakdown: 90% gravel roads, 10% dirt"

Writes structured surface_breakdown into course_description for each race.
Never overwrites existing surface_breakdown data.

Usage:
    python scripts/extract_surface_breakdown.py              # All races
    python scripts/extract_surface_breakdown.py --dry-run    # Preview only
    python scripts/extract_surface_breakdown.py --slug foo   # Single race
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"
DUMP_DIR = PROJECT_ROOT / "research-dumps"

# Patterns to find surface breakdowns
# Matches: "86% gravel/12% paved/2% trail" or "85% gravel, 10% pavement"
SURFACE_LINE_RE = re.compile(
    r'(\d{1,3})\s*%\s*'
    r'(gravel|paved?(?:ment)?|dirt|single\s*track|double\s*track|trail|road|asphalt|tarmac|sand|mud|off-?road)'
    r'(?:\s*(?:roads?|surface|terrain|sections?))?\s*'
    r'[,/&]\s*'
    r'(\d{1,3})\s*%\s*'
    r'(gravel|paved?(?:ment)?|dirt|single\s*track|double\s*track|trail|road|asphalt|tarmac|sand|mud|off-?road)'
    r'(?:\s*(?:roads?|surface|terrain|sections?))?',
    re.I,
)

# Also catch a third segment if present
SURFACE_THREE_RE = re.compile(
    r'(\d{1,3})\s*%\s*'
    r'(gravel|paved?(?:ment)?|dirt|single\s*track|double\s*track|trail|road|asphalt|tarmac|sand|mud|off-?road)'
    r'(?:\s*(?:roads?|surface|terrain|sections?))?\s*'
    r'[,/&]\s*'
    r'(\d{1,3})\s*%\s*'
    r'(gravel|paved?(?:ment)?|dirt|single\s*track|double\s*track|trail|road|asphalt|tarmac|sand|mud|off-?road)'
    r'(?:\s*(?:roads?|surface|terrain|sections?))?\s*'
    r'[,/&]\s*'
    r'(\d{1,3})\s*%\s*'
    r'(gravel|paved?(?:ment)?|dirt|single\s*track|double\s*track|trail|road|asphalt|tarmac|sand|mud|off-?road)',
    re.I,
)

# Distance label patterns before surface data
DISTANCE_LABEL_RE = re.compile(
    r'(\d+)\s*(?:mi(?:le)?|km|k)\s*(?:route|course|option)?[:\s]*',
    re.I,
)


def normalize_surface(name):
    """Normalize surface type name."""
    name = name.lower().strip()
    if name.startswith("pave") or name == "asphalt" or name == "tarmac" or name == "road":
        return "pavement"
    if "single" in name:
        return "singletrack"
    if "double" in name:
        return "doubletrack"
    return name


def extract_surfaces(content):
    """Extract surface breakdown from content. Returns dict or None."""
    # Try to find distance-specific breakdowns first
    breakdowns = {}

    lines = content.split("\n")
    for i, line in enumerate(lines):
        # Check for distance label + surface data on same line or next line
        dist_match = DISTANCE_LABEL_RE.search(line)
        search_text = line
        if dist_match and i + 1 < len(lines):
            search_text = line + " " + lines[i + 1]

        # Try 3-segment match first
        m3 = SURFACE_THREE_RE.search(search_text)
        if m3:
            surfaces = {
                normalize_surface(m3.group(2)): int(m3.group(1)),
                normalize_surface(m3.group(4)): int(m3.group(3)),
                normalize_surface(m3.group(6)): int(m3.group(5)),
            }
            total = sum(surfaces.values())
            if 90 <= total <= 110:  # Sanity check
                if dist_match:
                    label = f"{dist_match.group(1)}mi"
                    breakdowns[label] = surfaces
                else:
                    breakdowns["overall"] = surfaces
                continue

        # Try 2-segment match
        m2 = SURFACE_LINE_RE.search(search_text)
        if m2:
            surfaces = {
                normalize_surface(m2.group(2)): int(m2.group(1)),
                normalize_surface(m2.group(4)): int(m2.group(3)),
            }
            total = sum(surfaces.values())
            if 50 <= total <= 110:  # More lenient for 2-segment
                if dist_match:
                    label = f"{dist_match.group(1)}mi"
                    breakdowns[label] = surfaces
                elif "overall" not in breakdowns:
                    breakdowns["overall"] = surfaces

    if not breakdowns:
        # Try one more pass on full content without line breaks
        m3 = SURFACE_THREE_RE.search(content)
        if m3:
            surfaces = {
                normalize_surface(m3.group(2)): int(m3.group(1)),
                normalize_surface(m3.group(4)): int(m3.group(3)),
                normalize_surface(m3.group(6)): int(m3.group(5)),
            }
            if 90 <= sum(surfaces.values()) <= 110:
                return {"overall": surfaces}

        m2 = SURFACE_LINE_RE.search(content)
        if m2:
            surfaces = {
                normalize_surface(m2.group(2)): int(m2.group(1)),
                normalize_surface(m2.group(4)): int(m2.group(3)),
            }
            if 50 <= sum(surfaces.values()) <= 110:
                return {"overall": surfaces}

    return breakdowns if breakdowns else None


def process_profile(filepath, dry_run=False):
    """Extract surface breakdown for one profile."""
    slug = filepath.stem
    content = ""
    for suffix in ["-raw.md", "-raw.bak.md", "-community.md"]:
        path = DUMP_DIR / f"{slug}{suffix}"
        if path.exists():
            content += "\n" + path.read_text(errors="replace")

    if not content.strip():
        return {"slug": slug, "status": "no_dump"}

    data = json.loads(filepath.read_text())
    race = data["race"]
    course = race.get("course_description", {})

    # Don't overwrite existing
    if course.get("surface_breakdown"):
        return {"slug": slug, "status": "already_has"}

    breakdown = extract_surfaces(content)
    if not breakdown:
        return {"slug": slug, "status": "no_match"}

    if not dry_run:
        course["surface_breakdown"] = breakdown
        race["course_description"] = course
        data["race"] = race
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return {"slug": slug, "status": "filled", "data": breakdown}


def main():
    parser = argparse.ArgumentParser(description="Extract surface composition from dumps")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--slug", help="Single race")
    args = parser.parse_args()

    files = sorted(DATA_DIR.glob("*.json"))
    if args.slug:
        files = [DATA_DIR / f"{args.slug}.json"]

    stats = {"filled": 0, "already_has": 0, "no_match": 0, "no_dump": 0}

    for fp in files:
        result = process_profile(fp, dry_run=args.dry_run)
        stats[result["status"]] = stats.get(result["status"], 0) + 1

        if result["status"] == "filled":
            print(f"  {result['slug']}: {result['data']}")

    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"\n{prefix}Surface Breakdown Extraction:")
    print(f"  Profiles:    {len(files)}")
    print(f"  Filled:      {stats['filled']}")
    print(f"  Already had: {stats['already_has']}")
    print(f"  No match:    {stats['no_match']}")
    print(f"  No dump:     {stats['no_dump']}")


if __name__ == "__main__":
    main()
