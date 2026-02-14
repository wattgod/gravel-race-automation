#!/usr/bin/env python3
"""
Migrate series tags into constituent race JSON files.

Reads series-data/*.json and adds a "series" field to matching race-data/*.json files.
Idempotent — safe to re-run.

Usage:
    python scripts/migrate_series_tags.py
    python scripts/migrate_series_tags.py --dry-run
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERIES_DIR = PROJECT_ROOT / "series-data"
RACE_DIR = PROJECT_ROOT / "race-data"


def load_series_definitions() -> list:
    """Load all series definition files."""
    series_list = []
    for path in sorted(SERIES_DIR.glob("*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        series = data.get("series", {})
        series["_source_file"] = path.name
        series_list.append(series)
    return series_list


def validate_series(series_list: list) -> list:
    """Validate series definitions. Returns list of error strings."""
    errors = []
    seen_slugs = set()

    for s in series_list:
        name = s.get("name", "UNKNOWN")
        slug = s.get("slug", "")

        if not slug:
            errors.append(f"Series '{name}' missing slug")
            continue

        if slug in seen_slugs:
            errors.append(f"Duplicate series slug: {slug}")
        seen_slugs.add(slug)

        if not s.get("events"):
            errors.append(f"Series '{name}' has no events")

        for event in s.get("events", []):
            event_slug = event.get("slug")
            if event.get("has_profile") and event_slug:
                race_file = RACE_DIR / f"{event_slug}.json"
                if not race_file.exists():
                    errors.append(
                        f"Series '{name}' references slug '{event_slug}' "
                        f"but {race_file.name} does not exist"
                    )

    return errors


def migrate_tags(series_list: list, dry_run: bool = False) -> dict:
    """Add series tags to constituent race files.

    Returns dict with counts: tagged, skipped, already_tagged.
    """
    stats = {"tagged": 0, "skipped": 0, "already_tagged": 0, "details": []}

    for s in series_list:
        series_id = s["slug"]
        series_name = s["name"]
        series_tag = {"id": series_id, "name": series_name}

        for event in s.get("events", []):
            event_slug = event.get("slug")
            if not event_slug or not event.get("has_profile"):
                stats["skipped"] += 1
                continue

            race_file = RACE_DIR / f"{event_slug}.json"
            if not race_file.exists():
                stats["skipped"] += 1
                continue

            with open(race_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            race = data.get("race", {})
            existing = race.get("series")

            if existing == series_tag:
                stats["already_tagged"] += 1
                stats["details"].append(f"  SKIP {event_slug} (already tagged)")
                continue

            race["series"] = series_tag
            data["race"] = race

            if not dry_run:
                with open(race_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")

            stats["tagged"] += 1
            action = "WOULD TAG" if dry_run else "TAGGED"
            stats["details"].append(f"  {action} {event_slug} -> {series_name}")

    # Also tag the parent profile for series that have one
    parent_map = {
        "gravel-earth-series": "gravel-earth",
        "grasshopper-adventure-series": "grasshopper-series",
        "grinduro": "grinduro",
    }
    for s in series_list:
        series_id = s["slug"]
        parent_slug = parent_map.get(series_id)
        if not parent_slug:
            continue

        race_file = RACE_DIR / f"{parent_slug}.json"
        if not race_file.exists():
            continue

        with open(race_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        race = data.get("race", {})
        series_tag = {"id": series_id, "name": s["name"]}
        existing = race.get("series")

        if existing == series_tag:
            stats["already_tagged"] += 1
            stats["details"].append(f"  SKIP {parent_slug} (parent, already tagged)")
            continue

        race["series"] = series_tag
        data["race"] = race

        if not dry_run:
            with open(race_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

        stats["tagged"] += 1
        action = "WOULD TAG" if dry_run else "TAGGED"
        stats["details"].append(f"  {action} {parent_slug} (parent) -> {s['name']}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate series tags to race JSONs")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing files")
    args = parser.parse_args()

    if not SERIES_DIR.exists():
        print(f"ERROR: series-data/ not found at {SERIES_DIR}", file=sys.stderr)
        sys.exit(1)

    series_list = load_series_definitions()
    print(f"Loaded {len(series_list)} series definitions")

    errors = validate_series(series_list)
    if errors:
        print(f"\nValidation errors ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)

    print("Validation passed")

    mode = "DRY RUN" if args.dry_run else "MIGRATING"
    print(f"\n{mode}...")

    stats = migrate_tags(series_list, dry_run=args.dry_run)

    for detail in stats["details"]:
        print(detail)

    print(f"\nResults: {stats['tagged']} tagged, "
          f"{stats['already_tagged']} already tagged, "
          f"{stats['skipped']} skipped (no profile)")


if __name__ == "__main__":
    main()
