#!/usr/bin/env python3
"""
Rebuild tire indexes from per-tire JSON files and race data.

Produces three index files in data/indexes/:
  - tire-race-map.json: tire_id → list of races where recommended
  - race-tire-map.json: race_slug → list of tire recommendations
  - tire-category-map.json: category → list of tire_ids

Also updates each per-tire JSON's `race_appearances` and `comparable_tires`
fields in place.

Usage:
    python scripts/rebuild_tire_indexes.py
    python scripts/rebuild_tire_indexes.py --dry-run
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIRE_DIR = PROJECT_ROOT / "data" / "tires"
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
INDEX_DIR = PROJECT_ROOT / "data" / "indexes"


def load_all_tires() -> list:
    """Load all per-tire JSON files."""
    tires = []
    for path in sorted(TIRE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "id" in data:
                tires.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return tires


def scan_race_tire_links() -> tuple:
    """Scan all race JSONs for tire_recommendations.

    Returns:
        tire_race_map: {tire_id: [{slug, name, rank, width_mm, position, surface}]}
        race_tire_map: {race_slug: [{tire_id, name, rank, width_mm, position}]}
    """
    tire_race_map = defaultdict(list)
    race_tire_map = defaultdict(list)

    for path in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        race = data.get("race", data)
        slug = race.get("slug") or path.stem
        name = race.get("name", slug)
        tr = race.get("tire_recommendations")
        if not tr or not isinstance(tr, dict):
            continue

        surface = tr.get("race_surface_profile", "mixed")

        # Primary recommendations
        for pick in tr.get("primary", []):
            tire_id = pick.get("tire_id", "")
            if not tire_id:
                continue
            rank = pick.get("rank", 0)
            width = pick.get("recommended_width_mm", 0)
            entry = {
                "slug": slug,
                "name": name,
                "rank": rank,
                "width_mm": width,
                "position": "primary",
                "surface": surface,
            }
            tire_race_map[tire_id].append(entry)
            race_tire_map[slug].append({
                "tire_id": tire_id,
                "name": pick.get("name", ""),
                "rank": rank,
                "width_mm": width,
                "position": "primary",
            })

        # Front/rear split
        frs = tr.get("front_rear_split", {})
        if frs.get("applicable"):
            for pos in ("front", "rear"):
                split = frs.get(pos, {})
                tire_id = split.get("tire_id", "")
                if not tire_id:
                    continue
                width = split.get("width_mm", 0)
                entry = {
                    "slug": slug,
                    "name": name,
                    "rank": 0,
                    "width_mm": width,
                    "position": pos,
                    "surface": surface,
                }
                # Avoid duplicates — tire may already be in primary
                existing_ids = [e["slug"] for e in tire_race_map[tire_id]
                                if e["position"] == pos]
                if slug not in existing_ids:
                    tire_race_map[tire_id].append(entry)

    return dict(tire_race_map), dict(race_tire_map)


def build_category_map(tires: list) -> dict:
    """Build category → tire_id mappings for browsing/SEO.

    Categories:
      - By tread type: file-tread, knobby, aggressive, mud
      - By use case: all-rounder, fast-gravel, technical, wet-conditions,
                     budget (under $65), long-distance, comfort
      - By brand: continental, schwalbe, pirelli, etc.
    """
    categories = defaultdict(list)

    for tire in tires:
        tid = tire["id"]
        status = tire.get("status", "active")
        if status != "active":
            continue

        # By tread type
        tread = tire.get("tread_type", "")
        if tread:
            categories[f"tread-{tread}"].append(tid)

        # By brand
        brand = tire.get("brand", "").lower().replace(" ", "-")
        if brand:
            categories[f"brand-{brand}"].append(tid)

        # By use case (from recommended_use keywords)
        uses = tire.get("recommended_use", [])
        use_str = " ".join(u.lower() for u in uses)

        if any(k in use_str for k in ["all-rounder", "mixed gravel", "variable"]):
            categories["use-all-rounder"].append(tid)
        if any(k in use_str for k in ["fast gravel", "road-to-gravel", "smooth hardpack", "dry racing"]):
            categories["use-fast-gravel"].append(tid)
        if any(k in use_str for k in ["technical", "rocky", "roots", "loose over hard"]):
            categories["use-technical"].append(tid)
        if any(k in use_str for k in ["wet", "mud", "clay", "saturated"]):
            categories["use-wet-mud"].append(tid)
        if any(k in use_str for k in ["long distance", "durability", "comfort"]):
            categories["use-endurance"].append(tid)
        if any(k in use_str for k in ["budget", "value"]):
            categories["use-budget"].append(tid)

        # By price tier
        msrp = tire.get("msrp_usd", 0)
        if msrp and msrp < 65:
            categories["price-under-65"].append(tid)
        elif msrp and msrp < 80:
            categories["price-65-80"].append(tid)
        else:
            categories["price-80-plus"].append(tid)

    return dict(categories)


def find_comparable_tires(tires: list) -> dict:
    """For each tire, find comparable alternatives.

    Comparable = same tread_type OR overlapping recommended_use keywords.
    Returns: {tire_id: [comparable_tire_ids]}
    """
    comparables = {}
    tire_map = {t["id"]: t for t in tires}

    for tire in tires:
        tid = tire["id"]
        tread = tire.get("tread_type", "")
        uses = set(tire.get("recommended_use", []))
        candidates = []

        for other in tires:
            if other["id"] == tid:
                continue
            # Same tread type = comparable
            if other.get("tread_type") == tread:
                candidates.append(other["id"])
                continue
            # Overlapping use cases (3+ shared keywords)
            other_uses = set(other.get("recommended_use", []))
            if len(uses & other_uses) >= 2:
                candidates.append(other["id"])

        comparables[tid] = candidates

    return comparables


def rebuild(dry_run: bool = False) -> None:
    tires = load_all_tires()
    print(f"Loaded {len(tires)} tires from {TIRE_DIR}")

    tire_race_map, race_tire_map = scan_race_tire_links()
    category_map = build_category_map(tires)
    comparables = find_comparable_tires(tires)

    # Stats
    total_links = sum(len(v) for v in tire_race_map.values())
    races_with_tires = len(race_tire_map)
    print(f"Found {total_links} tire→race links across {races_with_tires} races")
    print(f"Built {len(category_map)} categories")

    # Build summary tire-race-map (with stats)
    tire_race_summary = {}
    for tid, appearances in tire_race_map.items():
        primary = [a for a in appearances if a["position"] == "primary"]
        ranks = [a["rank"] for a in primary if a["rank"] > 0]
        widths = [a["width_mm"] for a in appearances if a["width_mm"] > 0]
        tire_race_summary[tid] = {
            "total_appearances": len(appearances),
            "primary_picks": len(primary),
            "front_rear_picks": len(appearances) - len(primary),
            "avg_rank": round(sum(ranks) / len(ranks), 1) if ranks else 0,
            "most_common_width": max(set(widths), key=widths.count) if widths else 0,
            "races": appearances,
        }

    if dry_run:
        print("\n[dry-run] Would write:")
        print(f"  data/indexes/tire-race-map.json ({len(tire_race_summary)} tires)")
        print(f"  data/indexes/race-tire-map.json ({len(race_tire_map)} races)")
        print(f"  data/indexes/tire-category-map.json ({len(category_map)} categories)")
        print(f"  + Update race_appearances in {len(tires)} per-tire files")
        return

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    # Write tire-race-map.json
    trm_path = INDEX_DIR / "tire-race-map.json"
    with open(trm_path, "w", encoding="utf-8") as f:
        json.dump(tire_race_summary, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {trm_path} ({len(tire_race_summary)} tires)")

    # Write race-tire-map.json
    rtm_path = INDEX_DIR / "race-tire-map.json"
    with open(rtm_path, "w", encoding="utf-8") as f:
        json.dump(race_tire_map, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {rtm_path} ({len(race_tire_map)} races)")

    # Write tire-category-map.json
    tcm_path = INDEX_DIR / "tire-category-map.json"
    with open(tcm_path, "w", encoding="utf-8") as f:
        json.dump(category_map, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {tcm_path} ({len(category_map)} categories)")

    # Update each per-tire JSON with race_appearances and comparable_tires
    updated = 0
    for tire in tires:
        tid = tire["id"]
        tire_path = TIRE_DIR / f"{tid}.json"
        if not tire_path.exists():
            continue

        data = json.loads(tire_path.read_text(encoding="utf-8"))

        # Build compact race_appearances (slug → context)
        appearances = {}
        for entry in tire_race_map.get(tid, []):
            slug = entry["slug"]
            if slug not in appearances:
                appearances[slug] = {
                    "rank": entry["rank"],
                    "width_mm": entry["width_mm"],
                    "position": entry["position"],
                    "surface": entry["surface"],
                }
            elif entry["position"] in ("front", "rear"):
                appearances[slug]["position"] = entry["position"]

        data["race_appearances"] = appearances
        data["comparable_tires"] = comparables.get(tid, [])

        with open(tire_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        updated += 1

    print(f"Updated race_appearances + comparable_tires in {updated} tire files")

    # Print top tires by appearance count
    print("\nTop 10 tires by race appearances:")
    sorted_tires = sorted(tire_race_summary.items(),
                          key=lambda x: x[1]["total_appearances"], reverse=True)
    for tid, stats in sorted_tires[:10]:
        print(f"  {tid}: {stats['total_appearances']} appearances "
              f"(avg rank {stats['avg_rank']}, "
              f"common width {stats['most_common_width']}mm)")


def main():
    parser = argparse.ArgumentParser(description="Rebuild tire indexes")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    rebuild(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
