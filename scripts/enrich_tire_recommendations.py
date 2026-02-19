#!/usr/bin/env python3
"""
Enrich race JSON files with tire recommendations.

Runs the tire matching algorithm against each race and writes the results
back into the race JSON under `tire_recommendations`. This follows the
enrichment pattern from batch_enrich.py.

Usage:
    python scripts/enrich_tire_recommendations.py                    # All races
    python scripts/enrich_tire_recommendations.py --slug unbound-200 # Single race
    python scripts/enrich_tire_recommendations.py --dry-run          # Preview
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add wordpress/ to path for generator imports
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_tire_guide import (
    load_tire_database,
    load_weather_data,
    build_race_profile,
    get_top_tires,
    get_front_rear_split,
    compute_pressure_table,
    recommend_width,
)
from generate_neo_brutalist import normalize_race_data

# ── Paths ────────────────────────────────────────────────────

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"


def load_race_file(filepath: Path) -> tuple:
    """Load race JSON file, handling both flat and nested formats.

    Returns (full_data, race_dict, is_nested).
    """
    data = json.loads(filepath.read_text(encoding="utf-8"))
    if "race" in data and isinstance(data["race"], dict):
        return data, data["race"], True
    return data, data, False


def save_race_file(filepath: Path, data: dict, race: dict, is_nested: bool):
    """Save race JSON preserving original structure."""
    if is_nested:
        data["race"] = race
    else:
        data = race
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")


def build_enrichment(rd: dict, raw_race: dict, tire_db: list, slug: str) -> dict:
    """Build tire recommendation enrichment data for a race.

    Returns the tire_recommendations dict to be written into the race JSON.
    """
    weather = load_weather_data(slug)
    profile = build_race_profile(rd, raw_race, weather)
    top_picks = get_top_tires(tire_db, profile)
    front_rear = get_front_rear_split(tire_db, profile, top_picks)

    rec_width = top_picks[0]["width"] if top_picks else 40
    tech_rating = profile["tech_rating"]

    # Build primary recommendations
    primary = []
    for i, pick in enumerate(top_picks):
        tire = pick["tire"]
        width = pick["width"]
        crr_data = tire.get("crr_watts_at_29kmh")
        crr_val = None
        if crr_data and isinstance(crr_data, dict):
            # Look up CRR for the recommended width, fall back to first available
            crr_val = crr_data.get(str(width)) or next(iter(crr_data.values()), None)
        weight_data = tire.get("weight_grams", {})
        weight_val = weight_data.get(str(width))
        if not weight_val and weight_data:
            weight_val = next(iter(weight_data.values()))

        # Build concise "why" text
        why_parts = []
        if tire.get("puncture_resistance") == "high" and profile["needs_puncture"]:
            why_parts.append("high puncture protection for sharp surfaces")
        if crr_val and crr_val <= 30:
            why_parts.append(f"fast rolling at {crr_val}W")
        if tire.get("wet_traction") == "good" and profile["needs_wet"]:
            why_parts.append("excellent wet grip")
        if tire.get("mud_clearance") in ("moderate", "high") and profile["needs_mud"]:
            why_parts.append("strong mud clearance")
        if not why_parts:
            why_parts.append(tire.get("tagline", "Strong all-round pick"))

        primary.append({
            "rank": i + 1,
            "tire_id": tire["id"],
            "name": tire["name"],
            "brand": tire["brand"],
            "recommended_width_mm": width,
            "msrp_usd": tire.get("msrp_usd"),
            "weight_grams": weight_val,
            "crr_watts": crr_val,
            "why": ". ".join(why_parts[:3]),
        })

    # Build pressure table as flat dict
    pressure_rows = compute_pressure_table(tech_rating, rec_width)
    pressure_psi = {}
    for row in pressure_rows:
        weight_key = row["weight_range"].replace(" lbs", "lb").replace("-", "_").replace("+", "plus").replace(" ", "")
        pressure_psi[f"{weight_key}_dry"] = row["dry"]
        pressure_psi[f"{weight_key}_mixed"] = row["mixed"]
        pressure_psi[f"{weight_key}_wet"] = row["wet"]

    # Build front/rear split
    front_rear_data = {"applicable": False}
    if front_rear.get("applicable"):
        front_rear_data = {
            "applicable": True,
            "front": {
                "tire_id": front_rear["front"]["tire_id"],
                "name": front_rear["front"]["name"],
                "width_mm": front_rear["front"]["width_mm"],
            },
            "rear": {
                "tire_id": front_rear["rear"]["tire_id"],
                "name": front_rear["rear"]["name"],
                "width_mm": front_rear["rear"]["width_mm"],
            },
            "rationale": front_rear.get("rationale", ""),
        }

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d"),
        "primary": primary,
        "front_rear_split": front_rear_data,
        "race_surface_profile": profile["surface_category"],
        "recommended_width_mm": rec_width,
        "pressure_psi": pressure_psi,
    }


def enrich_single(slug: str, tire_db: list, dry_run: bool = False) -> tuple:
    """Enrich a single race with tire recommendations.

    Returns (success: bool, message: str).
    """
    filepath = RACE_DATA_DIR / f"{slug}.json"
    if not filepath.exists():
        return False, f"File not found: {filepath}"

    try:
        data, raw_race, is_nested = load_race_file(filepath)
        rd = normalize_race_data(data)
        rd["slug"] = rd.get("slug") or slug

        enrichment = build_enrichment(rd, raw_race, tire_db, slug)

        if dry_run:
            top = enrichment["primary"][0] if enrichment["primary"] else {}
            return True, (f"  {slug}: #{1} {top.get('name', '?')} "
                          f"{top.get('recommended_width_mm', '?')}mm "
                          f"${top.get('msrp_usd', '?')} "
                          f"({enrichment['race_surface_profile']})")

        # Write enrichment back to race JSON
        raw_race["tire_recommendations"] = enrichment
        save_race_file(filepath, data, raw_race, is_nested)
        return True, slug

    except Exception as e:
        return False, f"{slug}: {e}"


def main():
    parser = argparse.ArgumentParser(
        description="Enrich race JSON files with tire recommendations."
    )
    parser.add_argument("--slug", nargs="+", help="Specific race slug(s)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview enrichment without writing")
    parser.add_argument("--force", action="store_true",
                        help="Re-enrich even if tire_recommendations already exist")
    args = parser.parse_args()

    tire_db = load_tire_database()
    print(f"Loaded tire database: {len(tire_db)} tires")

    if args.slug:
        slugs = args.slug
    else:
        # All races
        slugs = sorted(f.stem for f in RACE_DATA_DIR.glob("*.json"))

    total = len(slugs)
    success = 0
    skipped = 0
    errors = []

    if args.dry_run:
        print(f"\n--- DRY RUN: previewing {total} races ---\n")

    for i, slug in enumerate(slugs, 1):
        # Check if already enriched (unless --force)
        if not args.force and not args.dry_run:
            filepath = RACE_DATA_DIR / f"{slug}.json"
            if filepath.exists():
                try:
                    d = json.loads(filepath.read_text(encoding="utf-8"))
                    r = d.get("race", d)
                    tr = r.get("tire_recommendations")
                    if tr and isinstance(tr, dict) and \
                       isinstance(tr.get("primary"), list) and len(tr["primary"]) > 0:
                        skipped += 1
                        continue
                except json.JSONDecodeError as e:
                    logging.warning("Malformed JSON for %s, will re-enrich: %s", slug, e)
                except OSError as e:
                    logging.warning("Could not read %s: %s", slug, e)

        ok, msg = enrich_single(slug, tire_db, dry_run=args.dry_run)
        if ok:
            success += 1
            if args.dry_run:
                print(msg)
        else:
            errors.append(msg)

        if not args.dry_run and i % 50 == 0:
            print(f"  [{i}/{total}] {success} enriched, {skipped} skipped, {len(errors)} errors")

    print(f"\nDone: {success}/{total} enriched, {skipped} skipped, {len(errors)} errors")
    if errors:
        print(f"Errors ({len(errors)}):")
        for err in errors[:10]:
            print(f"  {err}")


if __name__ == "__main__":
    main()
