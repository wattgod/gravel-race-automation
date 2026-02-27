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

# Default number of top categories to include in a race pack preview.
# Must be high enough that ultra-distance races still get 5 eligible workouts
# after filtering (up to 7 categories can be filtered for ultra: VO2max,
# Race_Simulation, Gravel_Specific, Critical_Power, Anaerobic, Sprint, Norwegian).
TOP_N_DEFAULT = 12
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
    terrain = race.get("terrain") or {}
    if isinstance(terrain, str):
        return terrain
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


def generate_race_overlay(race: dict, demands: dict) -> dict:
    """Generate race-specific preparation notes from race data and demands.

    Uses actual race climate, terrain, and vitals data to produce genuinely
    race-specific text (not generic templates with name swapped in).

    Returns dict with keys: heat, nutrition, altitude, terrain (each str or absent).
    """
    vitals = race.get('vitals') or {}
    distance = _safe_numeric(vitals, 'distance_mi', 0)
    race_name = race.get('display_name') or race.get('name', 'this race')
    location = _extract_location(race)
    terrain_primary = _extract_terrain_primary(race)

    # Extract month from date string
    date_str = vitals.get('date', '') or vitals.get('date_specific', '') or ''
    month = ''
    for m in ['January','February','March','April','May','June','July','August',
              'September','October','November','December']:
        if m in date_str:
            month = m
            break

    # Climate data
    climate = race.get('climate') or {}
    climate_desc = ''
    if isinstance(climate, dict):
        climate_desc = climate.get('description', '')
    challenges = []
    if isinstance(climate, dict):
        challenges = climate.get('challenges', []) or []

    # Elevation
    elevation = _safe_numeric(vitals, 'elevation_ft', 0)

    # Terrain types for specificity
    terrain_types = vitals.get('terrain_types', []) or []
    terrain_detail = ', '.join(terrain_types[:3]).lower() if terrain_types else ''

    overlay = {}

    # ── Heat ──
    heat_score = demands.get('heat_resilience', 0)
    if heat_score >= 8:
        # Use actual climate data
        climate_line = ''
        if month and location != 'the course':
            climate_line = f"{month} in {location}"
            if climate_desc:
                climate_line += f" — {climate_desc.rstrip('.')}"
            climate_line += '. '
        elif climate_desc:
            climate_line = f"{climate_desc.rstrip('.')}. "

        challenge_line = ''
        heat_challenges = [c for c in challenges if any(w in c.lower() for w in ['heat', 'hot', 'sun', 'humid', 'hydra'])]
        if heat_challenges:
            challenge_line = ' Race-day realities: ' + '; '.join(c.rstrip('.') for c in heat_challenges[:2]) + '.'

        overlay['heat'] = (
            f"{climate_line}"
            f"Begin heat acclimatization 10\u201314 days before {race_name} \u2014 "
            f"20\u201330min sauna sessions or midday rides in full kit. "
            f"Pre-load sodium 48 hours out. "
            f"Target 500\u2013750ml/hr with electrolytes on race day.{challenge_line}"
        )
    elif heat_score >= 5:
        climate_line = ''
        if month and location != 'the course':
            climate_line = f"{month} in {location} can bring heat. "
        overlay['heat'] = (
            f"{climate_line}"
            f"Complete 3\u20134 heat exposure sessions in the final 2 weeks before {race_name}. "
            f"Increase sodium intake 48 hours before race day."
        )

    # ── Nutrition ──
    if distance >= 150:
        overlay['nutrition'] = (
            f"Ultra-distance fueling for {int(distance)} miles: 80\u2013100g carbs/hour from mile 1 \u2014 "
            f"don\u2019t wait until you\u2019re hungry. "
            f"Practice your exact race-day nutrition in every long training ride. "
            f"Carry backup calories. "
            f"{int(distance)} miles burns 8,000\u201312,000+ calories \u2014 you cannot replace them all, but you must try."
        )
    elif distance >= 80:
        overlay['nutrition'] = (
            f"Target 60\u201380g carbs/hour for {race_name}\u2019s {int(distance)} miles. "
            f"Start fueling within the first 30 minutes \u2014 early fueling prevents late-race collapse. "
            f"Bonking at mile 60 is a nutrition failure, not a fitness failure."
        )
    elif distance >= 40:
        overlay['nutrition'] = (
            f"Target 40\u201360g carbs/hour for {race_name}\u2019s {int(distance)} miles. "
            f"Front-load calories in the first half. One bottle per hour minimum, more in heat."
        )
    else:
        overlay['nutrition'] = (
            "Standard hydration and fueling. One bottle per hour minimum. "
            "Gel or bar every 45 minutes at race intensity."
        )

    # ── Altitude ──
    alt_score = demands.get('altitude', 0)
    if alt_score >= 7:
        elev_line = ''
        if elevation >= 1000:
            elev_line = f"with {int(elevation):,}ft of climbing, much of it above 8,000ft"
        alt_challenges = [c for c in challenges if any(w in c.lower() for w in ['altitude', 'elevation', 'feet', 'summit', 'thin air'])]
        challenge_line = ''
        if alt_challenges:
            challenge_line = ' ' + '; '.join(c.rstrip('.') for c in alt_challenges[:2]) + '.'

        overlay['altitude'] = (
            f"{race_name} {elev_line + ' ' if elev_line else ''}"
            f"demands altitude preparation. "
            f"Arrive 5\u20137 days early for acclimatization. "
            f"Expect 5\u201315% power reduction at altitude. "
            f"Increase iron intake 4 weeks out. "
            f"Hydrate aggressively \u2014 altitude increases fluid loss by 20\u201340%.{challenge_line}"
        )
    elif alt_score >= 4:
        overlay['altitude'] = (
            f"Moderate altitude at {race_name}. "
            f"Arrive 2\u20133 days early. Reduce intensity expectations by 5\u201310%. "
            f"Hydrate aggressively."
        )

    # ── Terrain ──
    tech_score = demands.get('technical', 0)
    terrain_str = terrain_primary.rstrip('.').lower() if terrain_primary else 'mixed terrain'

    if tech_score >= 7:
        detail_line = ''
        if terrain_detail:
            detail_line = f" Expect: {terrain_detail}."

        overlay['terrain'] = (
            f"Highly technical terrain at {race_name} demands practice on similar surfaces. "
            f"Ride {terrain_str} at race-day cadence weekly.{detail_line} "
            f"Practice cornering, descending, and power delivery on unstable surfaces. "
            f"Dial in tire pressure before race week \u2014 "
            f"5 PSI wrong costs you 15+ minutes over {int(distance) if distance >= 1 else 'the full'} miles."
        )
    elif tech_score >= 4:
        overlay['terrain'] = (
            f"Mixed terrain at {race_name} requires surface adaptability. "
            f"Include weekly rides on {terrain_str} to build confidence."
            + (f" Expect: {terrain_detail}." if terrain_detail else "")
        )

    return overlay


def generate_workout_context(race: dict, demands: dict, category: str) -> str:
    """Generate a 1-sentence race-specific context for why a workout category matters.

    Uses actual race data (distance, elevation, terrain, month, location) to produce
    genuinely race-specific text that varies across races.
    """
    vitals = race.get('vitals') or {}
    distance = _safe_numeric(vitals, 'distance_mi', 0)
    race_name = race.get('display_name') or race.get('name', 'this race')
    location = _extract_location(race)
    terrain_primary = _extract_terrain_primary(race)
    terrain_str = terrain_primary.rstrip('.').lower() if terrain_primary else 'mixed terrain'
    elevation = _safe_numeric(vitals, 'elevation_ft', 0)
    terrain_types = vitals.get('terrain_types', []) or []

    # Extract month
    date_str = vitals.get('date', '') or vitals.get('date_specific', '') or ''
    month = ''
    for m in ['January','February','March','April','May','June','July','August',
              'September','October','November','December']:
        if m in date_str:
            month = m
            break

    dist_str = f"{int(distance)}-mile" if distance >= 1 else "full"

    if category == 'Durability':
        if distance >= 150:
            return f"{race_name}\u2019s {dist_str} distance demands power production deep into fatigue \u2014 the defining challenge of ultra-distance gravel."
        elif distance >= 80:
            return f"At {int(distance)} miles, {race_name} punishes athletes who haven\u2019t trained their body to produce power when glycogen runs low."
        else:
            return f"{race_name}\u2019s {terrain_str} drains energy reserves faster than the distance suggests \u2014 durability training bridges the gap."
    elif category == 'VO2max':
        return f"{race_name}\u2019s {terrain_str} and competitive field demand explosive aerobic capacity \u2014 the ability to respond to surges without blowing up."
    elif category == 'HVLI_Extended':
        if distance >= 100:
            return f"At {int(distance)} miles, {race_name} rewards a massive aerobic engine. This volume work builds the fat-oxidation capacity that keeps you moving when glycogen runs low."
        else:
            return f"High-volume endurance builds the aerobic base that makes {race_name}\u2019s race-day efforts sustainable rather than destructive."
    elif category == 'Race_Simulation':
        return f"Racing {race_name} isn\u2019t just fitness \u2014 it\u2019s pacing, fueling, and executing when conditions deteriorate. This workout practices the race itself."
    elif category == 'TT_Threshold':
        return f"{race_name} rewards athletes who can hold sustained power without blowing up \u2014 threshold is the engine that drives everything above Zone 2."
    elif category == 'G_Spot':
        return f"The G-Spot zone (88\u201392% FTP) is where you\u2019ll spend the hardest sustained miles of {race_name}. Make this intensity feel like home."
    elif category == 'Mixed_Climbing':
        if elevation >= 5000:
            return f"{race_name}\u2019s {int(elevation):,}ft of climbing demands seated and standing versatility \u2014 the ability to change climbing style as gradient and fatigue dictate."
        else:
            return f"The varied gradients at {race_name} reward climbing adaptability \u2014 knowing when to sit, when to stand, and when to switch."
    elif category == 'Over_Under':
        return f"Over-unders train the lactate clearance you\u2019ll need at {race_name} when surges push you above threshold and you have to recover while still riding hard."
    elif category == 'Gravel_Specific':
        terrain_detail = ', '.join(terrain_types[:2]).lower() if terrain_types else terrain_str
        return f"{race_name}\u2019s {terrain_detail} demands rapid power changes \u2014 surge over obstacles, settle on smoother sections, repeat for hours."
    elif category == 'Endurance':
        return f"Every session at {race_name} intensity builds on this aerobic foundation \u2014 the endurance base is the soil everything else grows in."
    elif category == 'Critical_Power':
        return f"Critical power determines how long you can sustain above-threshold efforts at {race_name} \u2014 a higher CP means more time in the red before failure."
    elif category == 'Anaerobic_Capacity':
        return f"Short, violent efforts are unavoidable at {race_name} \u2014 climbs demanding 2-minute maximal efforts, surges to close gaps, attacks on {terrain_str}."
    elif category == 'Sprint_Neuromuscular':
        return f"Neuromuscular power closes gaps and wins field sprints at {race_name}. The ability to produce massive short-burst power is a tactical weapon."
    elif category == 'Norwegian_Double':
        return f"The Norwegian double-threshold method builds the sustained power base for {race_name} \u2014 massive training stimulus without the recovery cost of VO2max work."
    elif category == 'SFR_Muscle_Force':
        if elevation >= 3000:
            return f"Low-cadence force work builds the muscular strength for {race_name}\u2019s {int(elevation):,}ft of climbing \u2014 especially the grinding, low-speed ascents."
        else:
            return f"Muscular force work builds the torque for headwinds and {terrain_str} at {race_name} \u2014 when you can\u2019t spin, you grind."
    elif category == 'Cadence_Work':
        return f"Cadence efficiency makes every pedal stroke at {race_name} count \u2014 smooth technique reduces muscular fatigue over long distances."
    elif category == 'Blended':
        return f"Blended sessions combine endurance with intensity spikes \u2014 exactly what {race_name}\u2019s {terrain_str} delivers on race day."
    elif category == 'Tempo':
        return f"Tempo is the race-day intensity of {race_name}. Harder than Z2, easier than threshold \u2014 the pace you\u2019ll hold for hours on {terrain_str}."
    elif category == 'LT1_MAF':
        return f"Aerobic development below LT1 builds the fat-burning engine for {race_name}\u2019s endurance demands \u2014 the foundation everything else rides on."
    elif category == 'Recovery':
        return f"Strategic recovery enables the hard work. At {race_name}\u2019s training intensity, active recovery rides prevent overtraining."
    else:
        return f"Targeted training for {race_name}\u2019s specific demands."


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

    # 2b. Add race-specific context per category
    for tc in top_categories:
        tc['workout_context'] = generate_workout_context(race, demands, tc['category'])

    # 3. Pack summary
    pack_summary = generate_pack_summary(race, top_categories)

    # 4. Race-specific overlay
    race_overlay = generate_race_overlay(race, demands)

    # 5. Distance for eligibility filtering in page generator
    vitals = race.get("vitals") or {}
    distance_mi = _safe_numeric(vitals, "distance_mi", 0)

    return {
        "slug": slug,
        "race_name": race_name,
        "distance_mi": distance_mi,
        "demands": demands,
        "top_categories": top_categories,
        "race_overlay": race_overlay,
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
