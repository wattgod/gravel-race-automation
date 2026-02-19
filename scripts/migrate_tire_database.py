#!/usr/bin/env python3
"""
One-time migration: split data/tires/tire-database.json (flat array) into
individual per-tire JSON files at data/tires/{tire-id}.json.

Adds new fields for the V3 tire system:
  - status: "active" | "discontinued" | "upcoming"
  - race_appearances: {} (populated by rebuild_tire_indexes.py)
  - community_reviews: [] (populated by tire review Worker)
  - comparable_tires: [] (populated by rebuild_tire_indexes.py)
  - versions: [] (manual — model year changes)
  - last_enriched: null (set by enrich_tire_recommendations.py)

Usage:
    python scripts/migrate_tire_database.py              # dry run
    python scripts/migrate_tire_database.py --execute    # write files
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIRE_DB_PATH = PROJECT_ROOT / "data" / "tires" / "tire-database.json"
TIRE_DIR = PROJECT_ROOT / "data" / "tires"


def migrate(execute: bool = False) -> None:
    if not TIRE_DB_PATH.exists():
        print(f"ERROR: {TIRE_DB_PATH} not found")
        return

    with open(TIRE_DB_PATH, "r", encoding="utf-8") as f:
        tires = json.load(f)

    if not isinstance(tires, list):
        print("ERROR: tire-database.json is not a JSON array — already migrated?")
        return

    print(f"Found {len(tires)} tires in flat database")

    for tire in tires:
        tire_id = tire["id"]

        # Add V3 fields (existing fields stay at root level)
        tire.setdefault("status", "active")
        tire.setdefault("race_appearances", {})
        tire.setdefault("community_reviews", [])
        tire.setdefault("comparable_tires", [])
        tire.setdefault("versions", [])
        tire.setdefault("last_enriched", None)

        out_path = TIRE_DIR / f"{tire_id}.json"
        if execute:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(tire, f, indent=2, ensure_ascii=False)
                f.write("\n")
            print(f"  WROTE {out_path.name}")
        else:
            print(f"  [dry-run] Would write {out_path.name}")

    if execute:
        # Back up the original flat file
        backup = TIRE_DB_PATH.with_suffix(".json.bak")
        shutil.move(str(TIRE_DB_PATH), str(backup))
        print(f"\nBacked up original to {backup.name}")
        print(f"Migration complete: {len(tires)} per-tire files written")
    else:
        print(f"\nDry run complete. Use --execute to write files.")


def main():
    parser = argparse.ArgumentParser(description="Migrate flat tire DB to per-tire files")
    parser.add_argument("--execute", action="store_true", help="Actually write files (default: dry run)")
    args = parser.parse_args()
    migrate(execute=args.execute)


if __name__ == "__main__":
    main()
