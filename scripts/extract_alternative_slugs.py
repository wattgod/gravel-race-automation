#!/usr/bin/env python3
"""
Extract alternative race slugs from final_verdict.alternatives text.

Parses race names from the alternatives text and maps them to slugs,
writing `final_verdict.alternative_slugs` into each profile for
structured cross-referencing.

Usage:
    python scripts/extract_alternative_slugs.py             # All races
    python scripts/extract_alternative_slugs.py --dry-run   # Preview
    python scripts/extract_alternative_slugs.py --slug foo  # Single
"""

import argparse
import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

# Well-known aliases
ALIASES = {
    'unbound': 'unbound-200',
    'unbound gravel': 'unbound-200',
    'unbound 200': 'unbound-200',
    'unbound 100': 'unbound-100',
    'unbound xl': 'unbound-xl',
    'bwr': 'bwr-california',
    'belgian waffle ride': 'bwr-california',
    'big sugar': 'big-sugar',
    'land run': 'mid-south',
    'mid south': 'mid-south',
    'the mid south': 'mid-south',
    'dirty kanza': 'unbound-200',
    'leadville': 'leadville-100',
    'leadville 100': 'leadville-100',
    'sbt grvl': 'sbt-grvl',
    'tour divide': 'tour-divide',
    'gravel worlds': 'garmin-gravel-worlds',
    'barry-roubaix': 'barry-roubaix',
    'crusher in the tushar': 'crusher-in-the-tushar',
}


def build_name_map():
    """Build display_name -> slug mapping from all race profiles."""
    name_map = {}
    for fp in DATA_DIR.glob("*.json"):
        try:
            data = json.loads(fp.read_text())
            race = data["race"]
            slug = fp.stem
            display = race.get("display_name", race.get("name", ""))
            if display:
                name_map[display.lower()] = slug
                # Also add name without common suffixes
                for suffix in [" 100", " 200", " XL", " MTB"]:
                    if display.endswith(suffix):
                        name_map[display[:-len(suffix)].lower()] = slug
        except Exception:
            continue

    # Add aliases
    for alias, slug in ALIASES.items():
        name_map[alias.lower()] = slug

    return name_map


def extract_slugs(alt_text, name_map, own_slug):
    """Extract race slugs mentioned in alternatives text."""
    if not alt_text:
        return []

    text_lower = alt_text.lower()
    found = set()

    # Sort by name length descending (match longest first)
    for name, slug in sorted(name_map.items(), key=lambda x: len(x[0]), reverse=True):
        if name in text_lower and slug != own_slug:
            found.add(slug)
            # Remove matched text to avoid substring matches
            text_lower = text_lower.replace(name, "", 1)

    return sorted(found)


def main():
    parser = argparse.ArgumentParser(description="Extract alternative race slugs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--slug", help="Single race")
    args = parser.parse_args()

    name_map = build_name_map()

    files = sorted(DATA_DIR.glob("*.json"))
    if args.slug:
        files = [DATA_DIR / f"{args.slug}.json"]

    total = 0
    with_alts = 0
    total_links = 0

    for fp in files:
        data = json.loads(fp.read_text())
        race = data["race"]
        slug = fp.stem
        fv = race.get("final_verdict", {})
        alt_text = fv.get("alternatives", "")

        slugs = extract_slugs(alt_text, name_map, slug)
        total += 1

        if slugs:
            with_alts += 1
            total_links += len(slugs)

            if not args.dry_run:
                fv["alternative_slugs"] = slugs
                race["final_verdict"] = fv
                data["race"] = race
                fp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

            print(f"  {slug}: {slugs}")

    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"\n{prefix}Alternative Slugs Extraction:")
    print(f"  Profiles:        {total}")
    print(f"  With alternatives: {with_alts}")
    print(f"  Total links:     {total_links}")
    print(f"  Avg per profile: {total_links / max(with_alts, 1):.1f}")


if __name__ == "__main__":
    main()
