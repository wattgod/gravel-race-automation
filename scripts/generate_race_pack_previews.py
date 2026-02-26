#!/usr/bin/env python3
"""Generate race-specific training pack preview JSON for race page CTAs.

Sprint 6 of the race-to-archetype mapping system.

For each race:
    1. Load race JSON from race-data/
    2. Run demand analyzer to get 8-dimension demand vector
    3. Score archetype categories (inline weight matrix, same logic as
       coaching pipeline's race_category_scorer.py)
    4. Select top 3-5 categories with scores
    5. Name the top archetypes that would be in the pack
    6. Write preview JSON to web/race-packs/{slug}.json

Usage:
    python3 scripts/generate_race_pack_previews.py --slug unbound-200
    python3 scripts/generate_race_pack_previews.py --all
    python3 scripts/generate_race_pack_previews.py --tier 1
"""

import argparse
import json
import os
import sys
from datetime import date

# Ensure scripts/ is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from race_demand_analyzer import analyze_race_demands

# =============================================================================
# DEMAND-TO-CATEGORY WEIGHT MATRIX (same as coaching pipeline)
# =============================================================================
# Each demand dimension maps to categories it activates, with a weight
# multiplier reflecting how strongly that demand dimension should pull
# workouts from that category.
#
# Weights:
#   3.0 = primary match (this is THE category for that demand)
#   2.0-2.5 = strong secondary match
#   1.0-1.5 = supporting contribution
# =============================================================================

DEMAND_TO_CATEGORY_WEIGHTS = {
    'durability': {
        'Durability': 3.0,
        'HVLI_Extended': 2.5,
        'Endurance': 2.0,
        'Blended': 1.5,
        'Tempo': 1.0,
    },
    'climbing': {
        'Mixed_Climbing': 3.0,
        'Over_Under': 2.5,
        'SFR_Muscle_Force': 2.0,
        'TT_Threshold': 1.5,
        'G_Spot': 1.0,
    },
    'vo2_power': {
        'VO2max': 3.0,
        'Anaerobic_Capacity': 2.0,
        'Critical_Power': 1.5,
        'Sprint_Neuromuscular': 1.0,
    },
    'threshold': {
        'TT_Threshold': 3.0,
        'G_Spot': 2.5,
        'Norwegian_Double': 2.0,
        'Over_Under': 1.5,
        'Tempo': 1.0,
    },
    'technical': {
        'Gravel_Specific': 3.0,
        'Cadence_Work': 2.0,
        'Critical_Power': 2.0,
        'Race_Simulation': 1.5,
        'Anaerobic_Capacity': 1.0,
    },
    'heat_resilience': {
        'Durability': 2.0,
        'Endurance': 1.5,
        'HVLI_Extended': 1.0,
    },
    'altitude': {
        'VO2max': 2.5,
        'Endurance': 1.5,
        'LT1_MAF': 1.0,
    },
    'race_specificity': {
        'Race_Simulation': 3.0,
        'Gravel_Specific': 2.0,
        'Durability': 1.5,
        'Blended': 1.0,
    },
}

# =============================================================================
# SAMPLE ARCHETYPES PER CATEGORY
# =============================================================================
# Top 2-3 archetype names per category, used for preview display.
# Hardcoded here since we can't import from the coaching pipeline repo.
# =============================================================================

CATEGORY_SAMPLE_ARCHETYPES = {
    'Durability': ['Tired VO2max', 'Double Day Simulation', 'Progressive Fatigue'],
    'VO2max': ['5x3 VO2 Classic', 'Descending VO2 Pyramid', 'Norwegian 4x8'],
    'HVLI_Extended': ['HVLI Extended Z2', 'Multi-Hour Z2', 'Back-to-Back Long'],
    'Race_Simulation': ['Breakaway Simulation', 'Variable Pace Chaos', 'Sector Simulation'],
    'TT_Threshold': ['Single Sustained Threshold', 'Threshold Ramps', 'Descending Threshold'],
    'G_Spot': ['G-Spot Standard', 'G-Spot Extended', 'Criss-Cross'],
    'Mixed_Climbing': ['Seated/Standing Climbs', 'Variable Grade Simulation'],
    'Over_Under': ['Classic Over-Unders', 'Ladder Over-Unders'],
    'Gravel_Specific': ['Surge and Settle', 'Terrain Microbursts'],
    'Endurance': ['Pre-Race Openers', 'Terrain Simulation Z2'],
    'Critical_Power': ['Above CP Repeats', 'W-Prime Depletion'],
    'Anaerobic_Capacity': ['2min Killers', '90sec Repeats'],
    'Sprint_Neuromuscular': ['Attack Repeats', 'Sprint Buildups'],
    'Norwegian_Double': ['Norwegian 4x8 Classic', 'Double Threshold'],
    'SFR_Muscle_Force': ['SFR Low Cadence', 'Force Repeats'],
    'Cadence_Work': ['High Cadence Drills', 'Cadence Pyramids'],
    'Blended': ['Z2 + VO2 Combo', 'Endurance with Spikes'],
    'Tempo': ['Tempo Blocks', 'Extended Tempo'],
    'LT1_MAF': ['MAF Capped Ride', 'LT1 Assessment'],
    'Recovery': ['Easy Spin', 'Active Recovery'],
}

# Default number of top categories to include in a race pack preview
TOP_N_DEFAULT = 5
# Minimum number of top categories
TOP_N_MIN = 3


# =============================================================================
# CATEGORY SCORING (same logic as coaching pipeline race_category_scorer.py)
# =============================================================================


def calculate_category_scores(demands: dict) -> dict:
    """Score each archetype category for a race's demands.

    Args:
        demands: Dict with 8 dimensions, each 0-10.
                 Missing dimensions are treated as 0.
                 Values outside 0-10 are clamped.

    Returns:
        Dict mapping category name to normalized score 0-100, sorted descending.
    """
    category_scores = {}
    for demand_dim, demand_score in demands.items():
        if demand_dim not in DEMAND_TO_CATEGORY_WEIGHTS:
            continue
        # Clamp to 0-10
        clamped = max(0, min(10, demand_score))
        weights = DEMAND_TO_CATEGORY_WEIGHTS[demand_dim]
        for category, weight in weights.items():
            if category not in category_scores:
                category_scores[category] = 0.0
            category_scores[category] += clamped * weight

    # Normalize to 0-100
    if not category_scores:
        return {}
    max_score = max(category_scores.values())
    if max_score == 0:
        return {cat: 0 for cat in category_scores}
    for cat in category_scores:
        category_scores[cat] = round((category_scores[cat] / max_score) * 100)

    return dict(sorted(category_scores.items(), key=lambda x: -x[1]))


def get_top_categories(demands: dict, n: int = TOP_N_DEFAULT) -> list:
    """Get top N scored categories with their sample archetypes.

    Args:
        demands: Dict with 8 dimensions, each 0-10.
        n: Number of top categories to return.

    Returns:
        List of dicts with 'category', 'score', and 'workouts' keys.
    """
    scores = calculate_category_scores(demands)
    top = []
    for cat, score in list(scores.items())[:n]:
        workouts = CATEGORY_SAMPLE_ARCHETYPES.get(cat, [])
        top.append({
            'category': cat,
            'score': score,
            'workouts': workouts,
        })
    return top


# =============================================================================
# PACK SUMMARY GENERATION
# =============================================================================


def _safe_numeric(d: dict, key: str, default=0) -> float:
    """Safely retrieve a numeric value, coercing range strings.

    For range strings like '4,500-9,116', takes the first number.
    Strips commas.
    """
    val = d.get(key)
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace(",", "")
        parts = s.split("-")
        return float(parts[0].strip())
    except (ValueError, IndexError):
        return default


def _extract_terrain_primary(race: dict) -> str:
    """Extract primary terrain description from race data.

    Falls back gracefully if terrain data is missing.
    """
    terrain = race.get("terrain", {})
    primary = terrain.get("primary", "")
    if primary:
        return primary

    # Fallback: use terrain_types from vitals
    vitals = race.get("vitals", {})
    terrain_types = vitals.get("terrain_types", [])
    if terrain_types:
        return terrain_types[0]

    return "mixed terrain"


def _extract_location(race: dict) -> str:
    """Extract location from race data, with graceful fallback."""
    vitals = race.get("vitals", {})
    location = vitals.get("location", "")
    if location:
        return location
    return "the course"


def generate_pack_summary(race: dict, top_categories: list) -> str:
    """Generate a 1-sentence pack summary.

    Format:
        "This 10-workout pack focuses on {top1}, {top2}, and {top3}
         to prepare you for {distance} miles of {terrain} in {location}."
    """
    vitals = race.get("vitals", {})
    distance = _safe_numeric(vitals, "distance_mi", 0)
    terrain_primary = _extract_terrain_primary(race)
    location = _extract_location(race)

    # Get category names for top 3
    cat_names = [tc['category'].replace('_', ' ') for tc in top_categories[:3]]

    if len(cat_names) >= 3:
        focus_str = f"{cat_names[0]}, {cat_names[1]}, and {cat_names[2]}"
    elif len(cat_names) == 2:
        focus_str = f"{cat_names[0]} and {cat_names[1]}"
    elif len(cat_names) == 1:
        focus_str = cat_names[0]
    else:
        focus_str = "targeted training"

    # Distance formatting
    if distance >= 1:
        dist_str = f"{int(distance)} miles"
    else:
        dist_str = "the full distance"

    # Terrain: lowercase, strip trailing period
    terrain_str = terrain_primary.rstrip(".").lower() if terrain_primary else "mixed terrain"

    return (
        f"This 10-workout pack focuses on {focus_str} "
        f"to prepare you for {dist_str} of {terrain_str} in {location}."
    )


# =============================================================================
# PREVIEW GENERATION
# =============================================================================


def generate_preview(race_data: dict) -> dict:
    """Generate a complete preview dict for one race.

    Args:
        race_data: Full JSON dict with 'race' key at top level.

    Returns:
        Preview dict with slug, race_name, demands, top_categories,
        pack_summary, and generated_at.
    """
    race = race_data.get("race", {})
    slug = race.get("slug", "unknown")
    race_name = race.get("display_name") or race.get("name", slug)

    # 1. Demand analysis
    demands = analyze_race_demands(race_data)

    # 2. Top categories with archetypes
    top_categories = get_top_categories(demands)

    # 3. Pack summary
    pack_summary = generate_pack_summary(race, top_categories)

    return {
        "slug": slug,
        "race_name": race_name,
        "demands": demands,
        "top_categories": top_categories,
        "pack_summary": pack_summary,
        "generated_at": date.today().isoformat(),
    }


def generate_preview_from_file(path: str) -> dict:
    """Load a race JSON file and generate its preview.

    Args:
        path: Path to a race JSON file.

    Returns:
        Preview dict.
    """
    with open(path) as f:
        data = json.load(f)
    return generate_preview(data)


def write_preview(preview: dict, output_dir: str) -> str:
    """Write a preview dict to a JSON file.

    Args:
        preview: Preview dict to write.
        output_dir: Directory to write to.

    Returns:
        Path to the written file.
    """
    os.makedirs(output_dir, exist_ok=True)
    slug = preview["slug"]
    path = os.path.join(output_dir, f"{slug}.json")
    with open(path, "w") as f:
        json.dump(preview, f, indent=2)
    return path


# =============================================================================
# DIRECTORY HELPERS
# =============================================================================


def _race_data_dir() -> str:
    """Return the path to the race-data directory."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "race-data",
    )


def _output_dir() -> str:
    """Return the path to the web/race-packs output directory."""
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web",
        "race-packs",
    )


def _get_race_tier(path: str) -> int:
    """Read a race JSON and return its tier (1-4), defaulting to 4."""
    try:
        with open(path) as f:
            data = json.load(f)
        race = data.get("race", {})
        rating = race.get("gravel_god_rating", {})
        return rating.get("tier", rating.get("display_tier", 4))
    except Exception:
        return 4


# =============================================================================
# CLI
# =============================================================================


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate race-specific training pack preview JSON."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="Race slug (e.g., unbound-200)")
    group.add_argument(
        "--all", action="store_true", help="Generate previews for all races"
    )
    group.add_argument(
        "--tier", type=int, choices=[1, 2, 3, 4],
        help="Generate previews for a specific tier only"
    )

    args = parser.parse_args()
    race_dir = _race_data_dir()
    out_dir = _output_dir()

    if args.slug:
        path = os.path.join(race_dir, f"{args.slug}.json")
        if not os.path.exists(path):
            print(f"Error: {path} not found", file=sys.stderr)
            sys.exit(1)
        preview = generate_preview_from_file(path)
        written = write_preview(preview, out_dir)
        print(f"Wrote {written}")
        _print_preview_summary(preview)

    elif args.all or args.tier:
        json_files = sorted(f for f in os.listdir(race_dir) if f.endswith(".json"))
        generated = 0
        errors = 0
        for filename in json_files:
            path = os.path.join(race_dir, filename)

            # Tier filter
            if args.tier:
                tier = _get_race_tier(path)
                if tier != args.tier:
                    continue

            try:
                preview = generate_preview_from_file(path)
                write_preview(preview, out_dir)
                generated += 1
            except Exception as e:
                slug = filename.replace(".json", "")
                print(f"ERROR: {slug}: {e}", file=sys.stderr)
                errors += 1

        print(f"\nGenerated {generated} previews to {out_dir}/")
        if errors:
            print(f"Errors: {errors}", file=sys.stderr)


def _print_preview_summary(preview: dict) -> None:
    """Print a human-readable summary of a preview."""
    print(f"\n{'=' * 60}")
    print(f"  {preview['race_name']}")
    print(f"{'=' * 60}")
    print(f"\n  Demand Vector:")
    for dim, score in preview["demands"].items():
        bar = "#" * score + "." * (10 - score)
        print(f"    {dim:<20s} [{bar}] {score}/10")

    print(f"\n  Top Categories:")
    for tc in preview["top_categories"]:
        workouts_str = ", ".join(tc["workouts"][:2])
        print(f"    {tc['score']:3d}  {tc['category']:<25s}  ({workouts_str})")

    print(f"\n  Summary: {preview['pack_summary']}")
    print()


if __name__ == "__main__":
    main()
