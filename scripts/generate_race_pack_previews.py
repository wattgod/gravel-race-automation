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


def _poss(name: str) -> str:
    """Return possessive form: 'Badlands' -> \"Badlands'\", 'Mid South' -> \"Mid South's\"."""
    if name.endswith('s') or name.endswith('S'):
        return f"{name}'"
    return f"{name}'s"


def generate_workout_context(race: dict, demands: dict, category: str) -> str:
    """Generate a 1-sentence race-specific context for why a workout category matters.

    Uses actual race data (distance, elevation, terrain, month, location) to produce
    genuinely race-specific text. Brand voice: specific over inspiring, numbers not
    feelings, short sentences, no LinkedIn words.
    """
    vitals = race.get('vitals') or {}
    distance = _safe_numeric(vitals, 'distance_mi', 0)
    race_name = race.get('display_name') or race.get('name', 'this race')
    location = _extract_location(race)
    terrain_primary = _extract_terrain_primary(race)
    terrain_str = terrain_primary.rstrip('.') if terrain_primary else 'mixed terrain'
    # Title-case state/country names at start of terrain strings
    _US_STATES = {'alabama','alaska','arizona','arkansas','california','colorado',
        'connecticut','delaware','florida','georgia','hawaii','idaho','illinois',
        'indiana','iowa','kansas','kentucky','louisiana','maine','maryland',
        'massachusetts','michigan','minnesota','mississippi','missouri','montana',
        'nebraska','nevada','new hampshire','new jersey','new mexico','new york',
        'north carolina','north dakota','ohio','oklahoma','oregon','pennsylvania',
        'rhode island','south carolina','south dakota','tennessee','texas','utah',
        'vermont','virginia','washington','west virginia','wisconsin','wyoming'}
    terrain_lower = terrain_str.lower()
    for state in sorted(_US_STATES, key=len, reverse=True):
        if terrain_lower.startswith(state):
            terrain_str = terrain_str[:len(state)].title() + terrain_str[len(state):]
            break
    else:
        terrain_str = terrain_str[0].lower() + terrain_str[1:] if terrain_str else terrain_str
    # Truncate terrain_str if absurdly long (some race profiles have full descriptions)
    if len(terrain_str) > 50:
        terrain_str = terrain_str[:50].rsplit(' ', 1)[0]
    elevation = _safe_numeric(vitals, 'elevation_ft', 0)
    terrain_types = vitals.get('terrain_types', []) or []
    # Title-case terrain_types entries that start with state names
    clean_terrain_types = []
    for tt in terrain_types:
        tt_lower = tt.lower()
        for state in sorted(_US_STATES, key=len, reverse=True):
            if tt_lower.startswith(state):
                tt = tt[:len(state)].title() + tt[len(state):]
                break
        clean_terrain_types.append(tt)
    terrain_types = clean_terrain_types
    elev_per_mi = round(elevation / distance) if distance > 0 else 0

    # Extract month
    date_str = vitals.get('date', '') or vitals.get('date_specific', '') or ''
    month = ''
    for m in ['January','February','March','April','May','June','July','August',
              'September','October','November','December']:
        if m in date_str:
            month = m
            break

    if category == 'Durability':
        if distance >= 150:
            return f"{int(distance)} miles. Your legs will beg to quit after 120. This trains the power output you need from mile 130 onward."
        elif distance >= 80:
            return f"At mile 60 of {int(distance)}, glycogen is gone. This workout teaches your body to produce watts on fumes."
        else:
            return f"{int(distance)} miles on {terrain_str} burns energy faster than the distance suggests. Train the fade resistance now."
    elif category == 'VO2max':
        if elevation >= 5000:
            return f"{int(elevation):,}ft of climbing means repeated surges above threshold. VO2max work is how you survive the fifth climb, not just the first."
        else:
            return f"When someone attacks on {terrain_str}, you have 10 seconds to respond or you're off the back. This builds that response."
    elif category == 'HVLI_Extended':
        if distance >= 100:
            return f"{int(distance)} miles rewards fat oxidation. This volume work shifts your fuel mix so you're still burning fat at hour 5, not bonking at hour 3."
        else:
            return f"The aerobic base that lets you ride {terrain_str} at tempo for {int(distance)} miles without cracking. No shortcuts."
    elif category == 'Race_Simulation':
        if month:
            return f"Race-pace efforts that mimic {_poss(race_name)} demands. Pacing, fueling, and tactical decisions under fatigue. Practice the race before {month}."
        else:
            return f"Race-pace efforts that mimic {_poss(race_name)} demands. Pacing, fueling, and tactical decisions under fatigue. Practice the race before race day."
    elif category == 'TT_Threshold':
        if elev_per_mi >= 50:
            return f"{elev_per_mi}ft/mi means long efforts at or near FTP on every climb. If your threshold cracks at minute 15, you'll walk the rest."
        else:
            return f"{_poss(race_name)} {terrain_str} rewards steady threshold power. Surging and recovering costs more watts than just holding."
    elif category == 'G_Spot':
        return f"88\u201392% FTP is where you'll spend the hardest sustained miles of {race_name}. Train it until it feels boring."
    elif category == 'Mixed_Climbing':
        if elevation >= 5000:
            return f"{int(elevation):,}ft of climbing on grades that change every minute. You need to switch from seated to standing without losing rhythm."
        else:
            return f"Varied gradients on {terrain_str} demand climbing versatility. Sit the shallow stuff, stand the steep stuff, switch without thinking."
    elif category == 'Over_Under':
        return f"At {race_name}, surges push you above threshold and you have to recover while still riding. Over-unders train exactly that."
    elif category == 'Gravel_Specific':
        terrain_detail = ', '.join(terrain_types[:2]) if terrain_types else terrain_str
        # Truncate absurdly long terrain descriptions
        if len(terrain_detail) > 60:
            terrain_detail = terrain_detail[:60].rsplit(' ', 1)[0]
        return f"{_poss(race_name)} {terrain_detail} forces constant power changes. Surge over the rough stuff, settle on the smooth, repeat for {int(distance)} miles."
    elif category == 'Endurance':
        if distance >= 80:
            return f"Every hard session works better with a bigger aerobic base. At {int(distance)} miles, base fitness is the difference between racing and surviving."
        else:
            return f"Base fitness for {race_name}. Without this, the hard workouts break you down instead of building you up."
    elif category == 'Critical_Power':
        return f"How long can you hold 105% FTP before you blow? At {race_name}, that number decides whether you bridge or get dropped."
    elif category == 'Anaerobic_Capacity':
        if elevation >= 3000:
            return f"Short, max efforts are unavoidable. Punchy climbs, gap closures, attacks on {terrain_str}. If you haven't trained them, you'll crack."
        else:
            return f"2-minute all-out efforts on {terrain_str}. Closing gaps, responding to attacks, sprinting for position. Train the burn."
    elif category == 'Sprint_Neuromuscular':
        return f"5-second power closes gaps and wins field sprints. At {race_name}, neuromuscular snap is a tactical tool, not just a finish-line move."
    elif category == 'Norwegian_Double':
        if distance >= 80:
            return f"Two threshold sessions per week without the recovery cost of VO2max work. For {int(distance)} miles, sustainable FTP gains matter more than peak power."
        else:
            return f"Double-threshold training builds sustained power with less fatigue. More FTP per hour of training."
    elif category == 'SFR_Muscle_Force':
        if elevation >= 3000:
            return f"Low-cadence force work for {int(elevation):,}ft of climbing. The slow, grinding ascents where you can't spin\u2014you push."
        else:
            return f"Torque for headwinds and {terrain_str}. When cadence drops below 70rpm, muscular strength keeps the watts up."
    elif category == 'Cadence_Work':
        return f"Smooth pedaling at {int(distance)} miles saves muscle. Bad technique at mile 10 is invisible. At mile 80 it's a cramp."
    elif category == 'Blended':
        if elevation >= 3000:
            return f"Endurance with intensity spikes baked in. Exactly what {int(elevation):,}ft of climbing on {terrain_str} does to your power file on race day."
        else:
            return f"Long rides with hard efforts mixed in. Simulates what {_poss(race_name)} {terrain_str} actually does to you."
    elif category == 'Tempo':
        if distance >= 80:
            return f"Tempo is {_poss(race_name)} race pace. The wattage you'll hold for {int(distance)} miles on {terrain_str}. Train it until it's automatic."
        else:
            return f"76\u201385% FTP for extended efforts. At {race_name}, tempo is the floor you'll live on. Make it feel easy."
    elif category == 'LT1_MAF':
        return f"Below LT1, you burn fat. Above it, you burn glycogen. For {int(distance)} miles, a higher LT1 means slower bonk."
    elif category == 'Recovery':
        return f"Hard training without recovery is just fatigue. These easy spins keep the adaptations coming between the real sessions."
    else:
        return f"Targeted training for {_poss(race_name)} specific demands."


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
