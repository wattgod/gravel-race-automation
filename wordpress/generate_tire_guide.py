#!/usr/bin/env python3
"""
Generate Tire Guide pages — race-specific tire recommendations with pressure tables.

Reads race data from race-data/*.json and tire database from data/tires/*.json
to produce standalone HTML pages with top 3 tire picks, pressure guide, and setup strategy.

Usage:
    python wordpress/generate_tire_guide.py unbound-200
    python wordpress/generate_tire_guide.py --all
    python wordpress/generate_tire_guide.py --all --output-dir /tmp/tires
"""

import argparse
import html
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Import shared constants from the race page generator
sys.path.insert(0, str(Path(__file__).parent))
from generate_neo_brutalist import (
    SITE_BASE_URL,
    normalize_race_data,
    find_data_file,
    load_race_data,
)
from generate_neo_brutalist import esc  # HTML escape helper

from brand_tokens import (
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
    get_ab_head_snippet,
    get_ga4_head_snippet,
)
from cookie_consent import get_consent_banner_html

# ── Constants ──────────────────────────────────────────────────

TIRE_DIR = Path(__file__).parent.parent / "data" / "tires"
WEATHER_DIR = Path(__file__).parent.parent / "data" / "weather"
OUTPUT_DIR = Path(__file__).parent / "output" / "tires"
CURRENT_YEAR = str(datetime.now().year)

# Negation phrases — catch "no mud", "without mud", "minimal mud", "little to no mud"
# Longer phrases listed first so regex alternation matches them before shorter "no".
NEGATION_PATTERN = re.compile(
    r'\b(?:little\s+to\s+no|no\s+significant|absent\s+of|without|minimal|no)\s+(\w+)',
    re.IGNORECASE,
)

# Surface demand categories
SURFACE_FAST = "fast"
SURFACE_MIXED = "mixed"
SURFACE_TECHNICAL = "technical"
SURFACE_MUDDY = "muddy"
SURFACE_WET = "wet"

# ── Scoring Constants ────────────────────────────────────────
# Each constant is named for its purpose. Rationale documented inline.

# recommended_use match bonus: +10 per matching use case keyword.
# Intentionally the largest single-criterion bonus because matching the tire's
# intended use is the strongest signal.
SCORE_USE_MATCH = 10

# avoid_use penalty: -15 per matching avoid condition.
# Larger than SCORE_USE_MATCH so a single avoid outweighs a single match
# (safety > performance).
SCORE_AVOID_PENALTY = -15

# CRR normalization: best gravel tires ~25W, worst ~45W at 29km/h (BRR data).
# Score = (ceiling - crr) / 2 → range ~0 to +10.
CRR_CEILING_WATTS = 45.0

# Puncture resistance bonuses: high is critical on flint/limestone courses.
# Moderate gets partial credit. Based on BRR puncture test rankings.
SCORE_PUNCTURE_HIGH = 12
SCORE_PUNCTURE_MODERATE = 4

# Climbing weight normalization: lightest gravel tires ~280g, heaviest ~600g.
# Score = (ceiling - weight) / divisor → range ~0 to +6.
WEIGHT_CEILING_GRAMS = 600.0
WEIGHT_DIVISOR = 50.0

# Climbing ratio threshold: 80 ft/mile is roughly equivalent to a "hilly" course
# (e.g., Unbound 200 = 80 ft/mi, SBT GRVL = 75 ft/mi, BWR = 100+ ft/mi).
CLIMBING_RATIO_THRESHOLD = 80

# Wet traction bonuses: "good" from BRR wet-grip test results.
SCORE_WET_GOOD = 10
SCORE_WET_FAIR = 4

# Mud clearance bonuses: based on tread void volume.
SCORE_MUD_HIGH = 12
SCORE_MUD_MODERATE = 6
SCORE_MUD_LOW = 2

# Comfort: wider tires (>=45mm) provide more air volume for long-distance comfort.
SCORE_COMFORT_WIDE = 3
SCORE_COMFORT_DURABLE_HIGH = 4
SCORE_COMFORT_DURABLE_MOD = 2

# Terrain keyword direct match bonus.
SCORE_TERRAIN_KEYWORD = 5

# Price bonuses: all else equal, cheaper tires are better value.
# Thresholds based on typical gravel tire MSRP range ($45-$90).
SCORE_PRICE_CHEAP = 2  # <= $60
SCORE_PRICE_MID = 1    # <= $70

# Distance threshold for "needs comfort" flag.
# 100 miles is standard ultra-distance cutoff (Unbound 200, Almanzo 100).
COMFORT_DISTANCE_MI = 100

# Precipitation threshold for "needs wet" flag (percent chance).
PRECIP_WET_THRESHOLD = 40

# Precipitation threshold for SURFACE_WET classification (percent chance).
PRECIP_SURFACE_WET_THRESHOLD = 50

# ── Pressure Table Constants ─────────────────────────────────
# Base pressure for a 40mm tire at tech_rating 2 on a tubeless setup with
# 21-25mm internal width rims. Sourced from SILCA tire pressure calculator
# median for 170lb rider on gravel.
PRESSURE_BASE_PSI = 38

# Pressure adjusts -0.5 psi per mm of width above 40mm. Wider tires need
# less pressure for same casing deflection. ~0.5 psi/mm matches SILCA model.
PRESSURE_WIDTH_FACTOR = 0.5

# Pressure adjusts -1.5 psi per tech_rating above 2. Lower pressure improves
# grip on technical terrain. 1.5 psi/step keeps range reasonable (32-38 base).
PRESSURE_TECH_FACTOR = 1.5

# Absolute floor pressures: below these values, rim strikes become likely
# on gravel regardless of tire width. Based on Stan's tubeless guidelines.
PRESSURE_FLOOR_DRY = 22
PRESSURE_FLOOR_MIXED = 20
PRESSURE_FLOOR_WET = 18

# ── Width Target Constants ───────────────────────────────────
# Target width by tech_rating. Standard gravel widths: 35-50mm.
# tech 1 (smooth): 38mm — fast rolling, low rolling resistance
# tech 2 (mixed): 40mm — all-round standard gravel width
# tech 3 (technical): 42mm — extra volume for rocks/roots
# tech 4+ (extreme): 45mm — maximum grip and cushion
WIDTH_TARGETS = {1: 38, 2: 40, 3: 42, 4: 45}

# ── Sealant Constants ────────────────────────────────────────
# Sealant amounts per tire, based on manufacturer recommendations
# (Stan's, Orange Seal) for gravel tire volumes.
SEALANT_WIDE = "90-120ml"    # >= 45mm
SEALANT_MEDIUM = "60-90ml"   # >= 40mm
SEALANT_NARROW = "50-70ml"   # < 40mm

# CRR "fast rolling" threshold for why-text (W at 29km/h).
# Tires below 30W are in the top tier per BRR rankings.
CRR_FAST_THRESHOLD = 30


# ── Data Loading ──────────────────────────────────────────────


def load_tire_database() -> list:
    """Load curated tire database from per-tire JSON files in data/tires/."""
    tires = []
    for path in sorted(TIRE_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "id" in data:
                tires.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return tires


def load_weather_data(slug: str) -> dict:
    """Load weather data for a race slug."""
    weather_file = WEATHER_DIR / f"{slug}.json"
    if weather_file.exists():
        try:
            return json.loads(weather_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logging.warning("Malformed weather JSON for %s: %s", slug, e)
        except OSError as e:
            logging.warning("Could not read weather file for %s: %s", slug, e)
    return {}


# ── Terrain Parsing ──────────────────────────────────────────


def parse_terrain_text(raw_race: dict) -> tuple:
    """Extract terrain text, tech_rating, features, vitals from raw race data.

    Returns (combined_text, tech_rating, distance_mi, elevation_ft, features_list).
    Handles all edge cases: string terrain, dict surface, missing data.
    """
    terrain = raw_race.get("terrain", {})
    if not isinstance(terrain, dict):
        terrain = {"surface": str(terrain), "primary": str(terrain)}
    vitals = raw_race.get("vitals", {})
    if not isinstance(vitals, dict):
        vitals = {}

    tech_rating = terrain.get("technical_rating", 2)
    surface_val = terrain.get("surface", "")
    if isinstance(surface_val, dict):
        surface_val = " ".join(str(k) for k in surface_val.keys())
    primary_val = terrain.get("primary", "")
    if isinstance(primary_val, dict):
        primary_val = " ".join(str(k) for k in primary_val.keys())
    surface = (str(surface_val) + " " + str(primary_val)).lower()
    features_raw = terrain.get("features", [])
    if isinstance(features_raw, list):
        features = " ".join(str(f) for f in features_raw).lower()
        features_list = [str(f) for f in features_raw]
    else:
        features = str(features_raw).lower()
        features_list = [str(features_raw)] if features_raw else []
    combined = surface + " " + features

    distance_mi = vitals.get("distance_mi", 50)
    if isinstance(distance_mi, str):
        # Handle strings like "70" or "50-100"
        try:
            distance_mi = int(re.sub(r'[^\d]', '', distance_mi.split('-')[0].split(',')[0]))
        except (ValueError, IndexError):
            logging.warning("Could not parse distance_mi '%s', defaulting to 50", distance_mi)
            distance_mi = 50
    elevation_ft = vitals.get("elevation_ft", 0)
    if isinstance(elevation_ft, str):
        # Handle strings like "4,500-9,116" — take the first number
        try:
            elevation_ft = int(re.sub(r'[^\d]', '', elevation_ft.split('-')[0]))
        except (ValueError, IndexError):
            logging.warning("Could not parse elevation_ft '%s', defaulting to 0", elevation_ft)
            elevation_ft = 0
    terrain_types = vitals.get("terrain_types", [])
    if isinstance(terrain_types, list):
        combined += " " + " ".join(str(t).lower() for t in terrain_types)

    return combined, tech_rating, distance_mi, elevation_ft, features_list


def extract_negated_keywords(text: str) -> set:
    """Find keywords that are negated (e.g. 'no mud' → {'mud'})."""
    return {m.group(1).lower() for m in NEGATION_PATTERN.finditer(text)}


def keyword_present(text: str, keyword: str, negated: set) -> bool:
    """Check if keyword is present in text AND not negated."""
    return keyword in text and keyword not in negated


# ── Race Profile Builder ─────────────────────────────────────


def build_race_profile(rd: dict, raw_race: dict, weather: dict) -> dict:
    """Build a race profile with parsed terrain demands.

    Returns dict with:
      - surface_category: fast/mixed/technical/muddy/wet
      - tech_rating, distance_mi, elevation_ft
      - needs_puncture, needs_wet, needs_mud, needs_speed, needs_comfort
      - precip_pct, climbing_ratio
      - combined_text (for debugging)
    """
    combined, tech_rating, distance_mi, elevation_ft, features_list = \
        parse_terrain_text(raw_race)
    precip_pct = weather.get("precip_chance_pct", 20)
    negated = extract_negated_keywords(combined)

    # Climbing ratio: ft per mile
    climbing_ratio = elevation_ft / max(distance_mi, 1)

    # Determine surface demands
    needs_mud = keyword_present(combined, "mud", negated) or \
                keyword_present(combined, "clay", negated) or \
                keyword_present(combined, "bog", negated) or \
                keyword_present(combined, "swamp", negated)
    needs_wet = precip_pct >= PRECIP_WET_THRESHOLD or \
                keyword_present(combined, "wet", negated) or \
                keyword_present(combined, "rain", negated) or \
                keyword_present(combined, "creek", negated)
    needs_puncture = any(keyword_present(combined, kw, negated)
                         for kw in ["limestone", "flint", "sharp", "rocky", "chunk",
                                    "shred", "angular", "abrasive"])
    needs_speed = tech_rating <= 2 and not needs_mud
    needs_comfort = distance_mi >= COMFORT_DISTANCE_MI

    # Is it truly technical singletrack or just chunky/rough gravel?
    has_singletrack = any(keyword_present(combined, kw, negated)
                          for kw in ["singletrack", "switchback", "technical descent",
                                     "roots", "rock garden"])

    # Classify primary surface demand
    if needs_mud:
        surface_category = SURFACE_MUDDY
    elif needs_wet and precip_pct >= PRECIP_SURFACE_WET_THRESHOLD:
        surface_category = SURFACE_WET
    elif tech_rating >= 4:
        surface_category = SURFACE_TECHNICAL
    elif tech_rating >= 3 and has_singletrack:
        surface_category = SURFACE_TECHNICAL
    elif tech_rating <= 1 and not needs_puncture:
        surface_category = SURFACE_FAST
    else:
        surface_category = SURFACE_MIXED

    return {
        "surface_category": surface_category,
        "tech_rating": tech_rating,
        "distance_mi": distance_mi,
        "elevation_ft": elevation_ft,
        "climbing_ratio": climbing_ratio,
        "precip_pct": precip_pct,
        "needs_puncture": needs_puncture,
        "needs_wet": needs_wet,
        "needs_mud": needs_mud,
        "needs_speed": needs_speed,
        "needs_comfort": needs_comfort,
        "combined_text": combined,
        "features_list": features_list,
    }


# ── Filter-Then-Rank Scoring ─────────────────────────────────


def filter_tires(tires: list, profile: dict) -> list:
    """Filter out disqualified tires based on race profile.

    Returns list of tires that are NOT disqualified.
    """
    filtered = []
    for tire in tires:
        # Hard disqualification: race needs mud, tire has no mud clearance
        if profile["needs_mud"] and tire.get("mud_clearance") == "none":
            continue
        # Hard disqualification: race needs wet grip, tire has poor wet traction
        if profile["needs_wet"] and profile["precip_pct"] >= PRECIP_SURFACE_WET_THRESHOLD and \
           tire.get("wet_traction") == "poor":
            continue
        # MTB crossover warning: tech_rating >= 5 with file tread
        if profile["tech_rating"] >= 5 and tire.get("tread_type") == "file":
            continue
        filtered.append(tire)
    return filtered


def score_tire(tire: dict, profile: dict) -> float:
    """Score a tire against race profile using filter-then-rank criteria.

    Uses measurable data instead of subjective scoring profiles.
    """
    score = 0.0
    cat = profile["surface_category"]

    # 1. recommended_use overlap with race conditions
    rec_use = tire.get("recommended_use", [])
    avoid_use = tire.get("avoid_use", [])

    # Map surface category to use keywords
    use_keywords = {
        SURFACE_FAST: ["fast gravel", "road-to-gravel", "smooth hardpack", "dry racing"],
        SURFACE_MIXED: ["mixed gravel", "all-rounder", "variable conditions", "fast mixed"],
        SURFACE_TECHNICAL: ["technical terrain", "rocky", "loose over hard", "mixed technical"],
        SURFACE_MUDDY: ["mud", "wet", "clay", "saturated courses"],
        SURFACE_WET: ["wet", "wet technical", "mixed wet"],
    }

    # Count recommended_use matches
    target_uses = use_keywords.get(cat, use_keywords[SURFACE_MIXED])
    for use in rec_use:
        if any(kw in use.lower() for kw in [t.lower() for t in target_uses]):
            score += SCORE_USE_MATCH

    # 2. avoid_use overlap with race conditions → hard penalty
    race_conditions = []
    if profile["needs_mud"]:
        race_conditions.extend(["mud", "wet"])
    if profile["needs_wet"]:
        race_conditions.append("wet")
    if profile["needs_puncture"]:
        race_conditions.extend(["sharp rock"])
    if profile["needs_speed"]:
        race_conditions.extend(["smooth", "fast"])
    for avoid in avoid_use:
        if any(cond in avoid.lower() for cond in race_conditions):
            score += SCORE_AVOID_PENALTY

    # 3. Crr watts when speed matters (lower = better)
    crr_data = tire.get("crr_watts_at_29kmh")
    if profile["needs_speed"] and crr_data and isinstance(crr_data, dict):
        # Pick CRR for the target width (same logic as recommend_width)
        tr = profile["tech_rating"]
        target_w = 45 if tr >= 4 else (42 if tr >= 3 else (40 if tr >= 2 else 38))
        widths_avail = sorted(tire.get("widths_mm", [40]))
        closest_w = min(widths_avail, key=lambda w: abs(w - target_w))
        crr_val = crr_data.get(str(closest_w)) or next(iter(crr_data.values()), None)
        if crr_val is not None:
            # Normalize: 25W is excellent, 45W is terrible
            # Score: (45 - crr) / 2 → range ~0 to 10
            score += max(0, (CRR_CEILING_WATTS - crr_val) / 2.0)

    # 4. Puncture resistance when surface is abrasive
    if profile["needs_puncture"]:
        pr = tire.get("puncture_resistance", "moderate")
        if pr == "high":
            score += SCORE_PUNCTURE_HIGH
        elif pr == "moderate":
            score += SCORE_PUNCTURE_MODERATE

    # 5. Weight when climbing matters (elevation_ft / distance_mi ratio)
    if profile["climbing_ratio"] > CLIMBING_RATIO_THRESHOLD:
        weight_data = tire.get("weight_grams", {})
        if weight_data:
            avg_weight = sum(weight_data.values()) / len(weight_data)
            score += max(0, (WEIGHT_CEILING_GRAMS - avg_weight) / WEIGHT_DIVISOR)

    # 6. Wet traction when precip_chance > threshold
    if profile["needs_wet"]:
        wt = tire.get("wet_traction", "fair")
        if wt == "good":
            score += SCORE_WET_GOOD
        elif wt == "fair":
            score += SCORE_WET_FAIR

    # 7. Mud clearance when mud keywords present
    if profile["needs_mud"]:
        mc = tire.get("mud_clearance", "none")
        if mc == "high":
            score += SCORE_MUD_HIGH
        elif mc == "moderate":
            score += SCORE_MUD_MODERATE
        elif mc == "low":
            score += SCORE_MUD_LOW

    # 8. Distance/comfort bonus for long races
    if profile["needs_comfort"]:
        widths = tire.get("widths_mm", [40])
        max_width = max(widths)
        if max_width >= 45:
            score += SCORE_COMFORT_WIDE
        pr = tire.get("puncture_resistance", "moderate")
        if pr == "high":
            score += SCORE_COMFORT_DURABLE_HIGH
        elif pr == "moderate":
            score += SCORE_COMFORT_DURABLE_MOD

    # 9. Direct terrain keyword matches against recommended_use
    combined_text = profile.get("combined_text", "")
    terrain_keywords = ["sharp rock", "chunky", "long distance", "durability",
                        "comfort", "fast gravel", "smooth", "rocky", "loose",
                        "technical", "singletrack", "mud", "wet", "clay"]
    for kw in terrain_keywords:
        if kw in combined_text:
            for use in rec_use:
                if kw in use.lower():
                    score += SCORE_TERRAIN_KEYWORD
                    break

    # 10. Price bonus (value matters, all else equal)
    msrp = tire.get("msrp_usd", 80)
    if msrp <= 60:
        score += SCORE_PRICE_CHEAP
    elif msrp <= 70:
        score += SCORE_PRICE_MID

    return score


def recommend_width(tech_rating: int, tire: dict) -> int:
    """Recommend tire width based on technical rating and available widths."""
    # Clamp tech_rating to known range, default to widest for extreme tech
    target = WIDTH_TARGETS.get(min(tech_rating, 4), WIDTH_TARGETS[2])

    widths = sorted(tire["widths_mm"])
    closest = min(widths, key=lambda w: abs(w - target))
    return closest


def get_top_tires(tires: list, profile: dict, n: int = 3) -> list:
    """Filter, score, and return top N tires with recommended widths.

    Uses filter-then-rank approach instead of subjective dot-product.
    """
    tech_rating = profile["tech_rating"]

    # Step 1: Filter out disqualified tires
    candidates = filter_tires(tires, profile)
    if not candidates:
        logging.warning("All %d tires filtered out for surface=%s — falling back to full set",
                        len(tires), profile["surface_category"])
        candidates = tires

    # Step 2: Score and rank
    scored = []
    for tire in candidates:
        s = score_tire(tire, profile)
        w = recommend_width(tech_rating, tire)
        scored.append({
            "tire": tire,
            "score": s,
            "width": w,
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:n]


def get_front_rear_split(tires: list, profile: dict, top_picks: list) -> dict:
    """Determine front/rear split recommendation.

    - tech_rating 2-3: faster tire front, grippier rear
    - tech_rating 4+: same aggressive tire front and rear
    - tech_rating 1: same fast tire front and rear
    """
    tech_rating = profile["tech_rating"]

    if tech_rating < 2 or tech_rating >= 4:
        # Same tire front and rear
        return {"applicable": False}

    if len(top_picks) < 2:
        return {"applicable": False}

    # For mixed-terrain races (tech_rating 2-3):
    # Look for a faster tire for front, grippier for rear
    all_scored = []
    candidates = filter_tires(tires, profile)
    if not candidates:
        candidates = tires
    for tire in candidates:
        s = score_tire(tire, profile)
        w = recommend_width(tech_rating, tire)
        all_scored.append({"tire": tire, "score": s, "width": w})
    all_scored.sort(key=lambda x: x["score"], reverse=True)

    # Front: prefer faster rolling (lower Crr or file tread)
    fast_tires = [t for t in all_scored if t["tire"].get("tread_type") == "file"]
    # Rear: prefer grippier (knobby or aggressive)
    grippy_tires = [t for t in all_scored if t["tire"].get("tread_type") in ("knobby", "aggressive")]

    if not fast_tires or not grippy_tires:
        return {"applicable": False}

    front = fast_tires[0]
    rear = grippy_tires[0]

    # Don't recommend split if same tire
    if front["tire"]["id"] == rear["tire"]["id"]:
        return {"applicable": False}

    return {
        "applicable": True,
        "front": {
            "tire_id": front["tire"]["id"],
            "name": front["tire"]["name"],
            "brand": front["tire"]["brand"],
            "width_mm": front["width"],
            "msrp_usd": front["tire"].get("msrp_usd"),
        },
        "rear": {
            "tire_id": rear["tire"]["id"],
            "name": rear["tire"]["name"],
            "brand": rear["tire"]["brand"],
            "width_mm": rear["width"],
            "msrp_usd": rear["tire"].get("msrp_usd"),
        },
        "rationale": "Faster front for reduced rolling resistance on straights, "
                     "grippier rear for traction on loose climbs and corners",
    }


def generate_why_text(tire: dict, profile: dict, race_name: str) -> str:
    """Generate 'Why this tire' explanation referencing real measurable facts."""
    parts = []
    name = tire["name"]
    race_short = race_name.split(" - ")[0] if " - " in race_name else race_name

    # Reference Crr watts for recommended width
    crr_data = tire.get("crr_watts_at_29kmh")
    if crr_data and isinstance(crr_data, dict):
        tr = profile.get("tech_rating", 2)
        target_w = 45 if tr >= 4 else (42 if tr >= 3 else (40 if tr >= 2 else 38))
        widths_avail = sorted(tire.get("widths_mm", [40]))
        closest_w = min(widths_avail, key=lambda w: abs(w - target_w))
        crr_val = crr_data.get(str(closest_w)) or next(iter(crr_data.values()), None)
        if crr_val is not None:
            if crr_val <= CRR_FAST_THRESHOLD:
                parts.append(f"{crr_val}W rolling resistance (among the fastest tested)")
            elif crr_val <= CRR_FAST_THRESHOLD + 5:
                parts.append(f"{crr_val}W rolling resistance (fast for a knobby)")
            else:
                parts.append(f"{crr_val}W rolling resistance")

    # Reference price
    msrp = tire.get("msrp_usd")
    if msrp:
        parts.append(f"${msrp:.2f} MSRP")

    # Reference weight for recommended width
    weight_data = tire.get("weight_grams", {})
    if weight_data:
        # Pick weight for the target width (same logic as recommend_width)
        tr = profile.get("tech_rating", 2)
        target_w = 45 if tr >= 4 else (42 if tr >= 3 else (40 if tr >= 2 else 38))
        widths_avail = sorted(tire.get("widths_mm", [40]))
        closest_w = min(widths_avail, key=lambda w: abs(w - target_w))
        w_key = str(closest_w)
        w_val = weight_data.get(w_key) or next(iter(weight_data.values()))
        parts.append(f"{w_val}g per tire ({w_key}mm)")

    # Reference puncture resistance for sharp courses
    if profile["needs_puncture"]:
        pr = tire.get("puncture_resistance", "moderate")
        if pr == "high":
            parts.append("high puncture resistance for sharp surfaces")
        elif pr == "low":
            parts.append("low puncture protection — consider carefully for sharp surfaces")

    # Reference wet traction for wet courses
    if profile["needs_wet"]:
        wt = tire.get("wet_traction", "fair")
        if wt == "good":
            parts.append("strong wet grip")
        elif wt == "poor":
            parts.append("limited wet traction — monitor forecast")

    # Reference mud clearance for muddy courses
    if profile["needs_mud"]:
        mc = tire.get("mud_clearance", "none")
        if mc == "high":
            parts.append("excellent mud shedding")
        elif mc == "moderate":
            parts.append("decent mud clearance")

    # Build the final text
    if not parts:
        parts = [tire.get("tagline", "Solid all-round choice")]

    # Cap at 4 facts
    facts = parts[:4]

    if len(facts) >= 3:
        return f"For {esc(race_short)}: {facts[0]}, {facts[1]}, {facts[2]}. {esc(tire.get('tagline', ''))}"
    elif len(facts) == 2:
        return f"For {esc(race_short)}: {facts[0]}, {facts[1]}. {esc(tire.get('tagline', ''))}"
    else:
        return f"For {esc(race_short)}: {facts[0]}. {esc(tire.get('tagline', ''))}"


# ── Pressure Table ────────────────────────────────────────────


def compute_pressure_table(tech_rating: int, rec_width: int) -> list:
    """Compute tire pressure recommendations for 4 weight ranges x 3 conditions.

    Returns list of dicts: [{weight_range, dry, mixed, wet}, ...]
    Base pressures computed from tech_rating + recommended width.
    """
    # Base pressure: wider tires and more technical terrain = lower pressure
    base = PRESSURE_BASE_PSI
    base -= (rec_width - 40) * PRESSURE_WIDTH_FACTOR
    base -= (tech_rating - 2) * PRESSURE_TECH_FACTOR

    weight_ranges = [
        {"label": "140-160 lbs", "offset": -3},
        {"label": "160-180 lbs", "offset": 0},
        {"label": "180-200 lbs", "offset": 3},
        {"label": "200+ lbs", "offset": 6},
    ]

    rows = []
    for wr in weight_ranges:
        p = base + wr["offset"]
        rows.append({
            "weight_range": wr["label"],
            "dry": f"{max(round(p), PRESSURE_FLOOR_DRY)}-{max(round(p + 4), PRESSURE_FLOOR_DRY + 4)}",
            "mixed": f"{max(round(p - 3), PRESSURE_FLOOR_MIXED)}-{max(round(p + 1), PRESSURE_FLOOR_MIXED + 4)}",
            "wet": f"{max(round(p - 5), PRESSURE_FLOOR_WET)}-{max(round(p - 1), PRESSURE_FLOOR_WET + 4)}",
        })

    return rows


# ── Setup Strategy ────────────────────────────────────────────


def build_setup_strategy(tech_rating: int, rec_width: int, profile: dict) -> dict:
    """Build tire setup strategy recommendations."""
    needs_puncture = profile.get("needs_puncture", False)

    # Sealant amount based on width + puncture risk
    if rec_width >= 45:
        sealant = SEALANT_WIDE
    elif rec_width >= 40:
        sealant = SEALANT_MEDIUM
    else:
        sealant = SEALANT_NARROW

    if needs_puncture:
        sealant_note = "Use the higher end of the range. Sharp surfaces demand extra sealant."
    else:
        sealant_note = "Standard amount should work fine for this course."

    # Tubeless strength
    if tech_rating >= 3 or needs_puncture:
        tubeless_rec = "Strongly recommended"
        tubeless_note = "Technical terrain and sharp surfaces make tubeless essential. Self-sealing capability is critical."
    else:
        tubeless_rec = "Recommended"
        tubeless_note = "Tubeless provides better comfort and puncture protection, even on smoother courses."

    # Spare strategy
    if needs_puncture:
        spare = "Carry a tube, tire plugs, AND a tire boot. Sharp surfaces can cause cuts too large for sealant alone."
    elif tech_rating >= 3:
        spare = "Carry a tube and tire plugs. Technical terrain increases the chance of a sidewall cut."
    else:
        spare = "Carry a tube and tire plugs. Standard repair kit should handle most issues."

    return {
        "tubeless_rec": tubeless_rec,
        "tubeless_note": tubeless_note,
        "sealant": sealant,
        "sealant_note": sealant_note,
        "spare": spare,
        "break_in": "Mount tires 2-3 days before race day. Ride at least 30 minutes to seat the bead, check for sealant leaks, and verify tire pressure holds overnight.",
    }


# ── Condition Alternatives ────────────────────────────────────


def get_condition_alternatives(tires: list, profile: dict, top_picks: list) -> dict:
    """Find best wet and dry alternatives not already in top 3.

    Only show alternatives when the primary pick has a weakness in that condition.
    """
    top_ids = {p["tire"]["id"] for p in top_picks}
    tech_rating = profile["tech_rating"]

    primary_tire = top_picks[0]["tire"] if top_picks else {}
    primary_wet = primary_tire.get("wet_traction", "fair")
    primary_mud = primary_tire.get("mud_clearance", "none")
    primary_tread = primary_tire.get("tread_type", "knobby")

    # Wet alternative: only if primary has poor/fair wet traction
    wet_alt = None
    if primary_wet in ("poor", "fair"):
        best_score = -999
        for tire in tires:
            if tire["id"] in top_ids:
                continue
            if tire.get("wet_traction") != "good":
                continue
            s = score_tire(tire, profile)
            # Boost wet-focused tires
            s += 20
            if s > best_score:
                best_score = s
                wet_alt = {"tire": tire, "score": s, "width": recommend_width(tech_rating, tire)}

    # Dry alternative: only if primary is conservative (mud/aggressive tread)
    dry_alt = None
    if primary_tread in ("mud", "aggressive") or primary_mud in ("moderate", "high"):
        best_score = -999
        for tire in tires:
            if tire["id"] in top_ids:
                continue
            if tire.get("tread_type") != "file":
                continue
            s = score_tire(tire, profile)
            # Boost speed-focused tires
            crr_data = tire.get("crr_watts_at_29kmh")
            if crr_data and isinstance(crr_data, dict):
                crr_val = next(iter(crr_data.values()), None)
                if crr_val and crr_val <= 30:
                    s += 15
            if s > best_score:
                best_score = s
                dry_alt = {"tire": tire, "score": s, "width": recommend_width(tech_rating, tire)}

    return {"wet": wet_alt, "dry": dry_alt}


# ── Page CSS ──────────────────────────────────────────────────


def get_page_css() -> str:
    """Return page-specific CSS for tire guide pages."""
    return """
/* Tire Guide Page Styles */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--gg-font-editorial);
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-near-black);
  line-height: var(--gg-line-height-normal);
}
a { color: var(--gg-color-teal); text-decoration: none; }
a:hover { text-decoration: underline; }

.tg-container {
  max-width: 820px;
  margin: 0 auto;
  padding: 0 var(--gg-spacing-md);
}

/* Header */
.tg-header {
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  padding: var(--gg-spacing-2xl) 0 var(--gg-spacing-xl);
  border-bottom: var(--gg-border-width-heavy) solid var(--gg-color-teal);
}
.tg-badge {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  background: var(--gg-color-teal);
  color: var(--gg-color-white);
  padding: 3px 10px;
  margin-bottom: var(--gg-spacing-sm);
}
.tg-header h1 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xl);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-tight);
  line-height: var(--gg-line-height-tight);
  margin: var(--gg-spacing-sm) 0;
}
@media (min-width: 640px) {
  .tg-header h1 { font-size: var(--gg-font-size-3xl); }
}
.tg-header-sub {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-warm-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
}

/* Vitals ribbon */
.tg-vitals {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gg-spacing-md);
  margin-top: var(--gg-spacing-md);
  padding-top: var(--gg-spacing-md);
  border-top: 1px solid rgba(255,255,255,0.15);
}
.tg-vital {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-tan);
}
.tg-vital strong {
  color: var(--gg-color-warm-paper);
  display: block;
  font-size: var(--gg-font-size-sm);
}

/* Section styling */
.tg-section {
  padding: var(--gg-spacing-2xl) 0;
  border-bottom: var(--gg-border-subtle);
}
.tg-section:last-of-type { border-bottom: none; }
.tg-section-num {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  color: var(--gg-color-teal);
  display: block;
  margin-bottom: var(--gg-spacing-xs);
}
.tg-section h2 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-tight);
  margin-bottom: var(--gg-spacing-lg);
}

/* Surface analysis */
.tg-surface-box {
  background: var(--gg-color-sand);
  border: var(--gg-border-subtle);
  padding: var(--gg-spacing-lg);
  margin-bottom: var(--gg-spacing-md);
}
.tg-surface-box p { margin-bottom: var(--gg-spacing-sm); }
.tg-tech-badge {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  padding: 2px 8px;
  border: 2px solid var(--gg-color-primary-brown);
  margin-right: var(--gg-spacing-xs);
}
.tg-features {
  list-style: none;
  padding: 0;
  margin: var(--gg-spacing-sm) 0 0;
}
.tg-features li {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  padding: var(--gg-spacing-2xs) 0;
  border-bottom: 1px solid var(--gg-color-tan);
}
.tg-features li:last-child { border-bottom: none; }
.tg-features li::before {
  content: "\\2022";
  color: var(--gg-color-teal);
  font-weight: bold;
  margin-right: var(--gg-spacing-xs);
}
.tg-weather-note {
  background: var(--gg-color-warm-paper);
  border-left: 3px solid var(--gg-color-teal);
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  margin-top: var(--gg-spacing-md);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
}

/* Tire cards */
.tg-tire-card {
  background: var(--gg-color-white);
  border: var(--gg-border-standard);
  margin-bottom: var(--gg-spacing-lg);
  position: relative;
}
.tg-tire-rank {
  position: absolute;
  top: -1px;
  left: -1px;
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.tg-tire-rank--1 { background: var(--gg-color-teal); }
.tg-tire-rank--2 { background: var(--gg-color-primary-brown); }
.tg-tire-rank--3 { background: var(--gg-color-secondary-brown); }
.tg-tire-header {
  padding: var(--gg-spacing-lg) var(--gg-spacing-lg) var(--gg-spacing-sm);
  padding-left: 64px;
}
.tg-tire-name {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  margin: 0;
}
.tg-tire-brand {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
}
.tg-tire-width {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  background: var(--gg-color-sand);
  padding: 2px 8px;
  margin-top: var(--gg-spacing-2xs);
}
.tg-tire-body { padding: 0 var(--gg-spacing-lg) var(--gg-spacing-lg); }
.tg-tire-tagline {
  font-family: var(--gg-font-editorial);
  font-style: italic;
  color: var(--gg-color-secondary-brown);
  margin-bottom: var(--gg-spacing-sm);
}
.tg-tire-why {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
  margin-bottom: var(--gg-spacing-md);
}

/* Badges row */
.tg-badges {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gg-spacing-xs);
  margin-bottom: var(--gg-spacing-md);
}
.tg-badge-item {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  padding: 3px 8px;
  border: 2px solid var(--gg-color-tan);
}
.tg-badge-item--fast { border-color: var(--gg-color-teal); color: var(--gg-color-teal); }
.tg-badge-item--high { border-color: var(--gg-color-gold); color: var(--gg-color-gold); }

/* Strengths/weaknesses */
.tg-pros-cons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-md);
  margin-bottom: var(--gg-spacing-md);
}
@media (max-width: 480px) {
  .tg-pros-cons { grid-template-columns: 1fr; }
}
.tg-pros h4, .tg-cons h4 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  margin-bottom: var(--gg-spacing-xs);
}
.tg-pros h4 { color: var(--gg-color-teal); }
.tg-cons h4 { color: var(--gg-color-secondary-brown); }
.tg-pros ul, .tg-cons ul {
  list-style: none;
  padding: 0;
}
.tg-pros li, .tg-cons li {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  padding: 2px 0;
}
.tg-pros li::before { content: "+"; color: var(--gg-color-teal); font-weight: bold; margin-right: 6px; }
.tg-cons li::before { content: "-"; color: var(--gg-color-secondary-brown); font-weight: bold; margin-right: 6px; }

.tg-review-link {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-teal);
  border-bottom: 2px solid var(--gg-color-teal);
  padding-bottom: 2px;
}

/* Pressure table */
.tg-pressure-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  margin: var(--gg-spacing-md) 0;
}
.tg-pressure-table th {
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  text-align: left;
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
}
.tg-pressure-table td {
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  border-bottom: 1px solid var(--gg-color-tan);
}
.tg-pressure-table tr:nth-child(even) td { background: var(--gg-color-sand); }
.tg-pressure-note {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  margin-top: var(--gg-spacing-sm);
  font-style: italic;
}

/* Setup strategy */
.tg-setup-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-md);
}
@media (max-width: 640px) {
  .tg-setup-grid { grid-template-columns: 1fr; }
}
.tg-setup-item {
  background: var(--gg-color-sand);
  border: var(--gg-border-subtle);
  padding: var(--gg-spacing-md);
}
.tg-setup-item h4 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  color: var(--gg-color-teal);
  margin-bottom: var(--gg-spacing-xs);
}
.tg-setup-item p {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
}

/* Condition alternatives */
.tg-alt-card {
  background: var(--gg-color-sand);
  border: var(--gg-border-subtle);
  padding: var(--gg-spacing-md);
  margin-bottom: var(--gg-spacing-md);
}
.tg-alt-label {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  color: var(--gg-color-teal);
  margin-bottom: var(--gg-spacing-xs);
}
.tg-alt-card h4 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-bold);
  margin-bottom: var(--gg-spacing-2xs);
}
.tg-alt-card p {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
}

/* Footer CTA */
.tg-footer-cta {
  background: var(--gg-color-near-black);
  padding: var(--gg-spacing-2xl) 0;
}
.tg-footer-cta-inner {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gg-spacing-md);
  justify-content: center;
}
.tg-btn {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  padding: var(--gg-spacing-sm) var(--gg-spacing-lg);
  text-decoration: none;
  transition: var(--gg-transition-hover);
}
.tg-btn--primary {
  background: var(--gg-color-teal);
  color: var(--gg-color-white);
  border: 2px solid var(--gg-color-teal);
}
.tg-btn--primary:hover { background: transparent; color: var(--gg-color-teal); text-decoration: none; }
.tg-btn--outline {
  background: transparent;
  color: var(--gg-color-warm-paper);
  border: 2px solid var(--gg-color-warm-paper);
}
.tg-btn--outline:hover { background: var(--gg-color-warm-paper); color: var(--gg-color-near-black); text-decoration: none; }

/* Breadcrumb */
.tg-breadcrumb {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-warm-brown);
  margin-bottom: var(--gg-spacing-sm);
}
.tg-breadcrumb a { color: var(--gg-color-warm-brown); }
.tg-breadcrumb a:hover { color: var(--gg-color-teal); }

/* Email capture */
.tg-email-capture {
  border: 1px solid var(--gg-color-tan);
  border-top: 3px solid var(--gg-color-teal);
  background: var(--gg-color-white);
  padding: 0;
  margin-bottom: var(--gg-spacing-lg);
}
.tg-email-capture-inner {
  padding: var(--gg-spacing-lg) var(--gg-spacing-xl);
  text-align: center;
}
.tg-email-capture-badge {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
  background: var(--gg-color-teal);
  color: var(--gg-color-white);
  padding: 3px 10px;
  margin-bottom: var(--gg-spacing-xs);
}
.tg-email-capture-title {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: 700;
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  color: var(--gg-color-near-black);
  margin: 0 0 var(--gg-spacing-2xs) 0;
}
.tg-email-capture-text {
  font-family: var(--gg-font-editorial);
  font-size: 12px;
  color: var(--gg-color-secondary-brown);
  line-height: var(--gg-line-height-relaxed);
  margin: 0 0 var(--gg-spacing-md) 0;
  max-width: 500px;
  margin-left: auto;
  margin-right: auto;
}
.tg-email-capture-row {
  display: flex;
  gap: 0;
  max-width: 420px;
  margin: 0 auto var(--gg-spacing-xs);
}
.tg-email-capture-input {
  flex: 1;
  font-family: var(--gg-font-data);
  font-size: 13px;
  padding: 12px 14px;
  border: 2px solid var(--gg-color-tan);
  border-right: none;
  background: var(--gg-color-white);
  color: var(--gg-color-near-black);
  min-width: 0;
}
.tg-email-capture-input:focus { outline: none; border-color: var(--gg-color-teal); }
.tg-email-capture-btn {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 2px;
  padding: 12px 18px;
  background: var(--gg-color-teal);
  color: var(--gg-color-white);
  border: 2px solid var(--gg-color-teal);
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.2s;
}
.tg-email-capture-btn:hover { background: var(--gg-color-light-teal); }
.tg-email-capture-fine {
  font-family: var(--gg-font-data);
  font-size: 10px;
  color: var(--gg-color-warm-brown);
  letter-spacing: 1px;
  margin: 0;
}
.tg-email-capture-success { padding: var(--gg-spacing-sm) 0; }
.tg-email-capture-check {
  font-family: var(--gg-font-data);
  font-size: 14px;
  font-weight: 700;
  color: var(--gg-color-teal);
  margin: 0 0 var(--gg-spacing-xs);
}
.tg-email-capture-link {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: var(--gg-color-white);
  background: var(--gg-color-teal);
  padding: 10px 20px;
  text-decoration: none;
  border: 2px solid var(--gg-color-teal);
  transition: background 0.2s;
}
.tg-email-capture-link:hover { background: var(--gg-color-light-teal); text-decoration: none; }

/* Exit-intent popup */
.tg-exit-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; z-index: 9999; background: rgba(26,22,19,0.85); display: flex; align-items: center; justify-content: center; padding: 20px; animation: tg-fade-in 0.3s ease; }
.tg-exit-modal { background: var(--gg-color-warm-paper); border: 4px solid var(--gg-color-near-black); max-width: 440px; width: 100%; padding: 40px 32px; text-align: center; position: relative; animation: tg-slide-up 0.3s ease; }
.tg-exit-close { position: absolute; top: 12px; right: 16px; background: none; border: none; font-size: 28px; color: var(--gg-color-secondary-brown); cursor: pointer; line-height: 1; }
.tg-exit-close:hover { color: var(--gg-color-near-black); }
.tg-exit-badge { display: inline-block; font-family: var(--gg-font-data); font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); padding: 4px 12px; margin-bottom: 16px; }
.tg-exit-title { font-family: var(--gg-font-data); font-size: 20px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 10px; color: var(--gg-color-near-black); }
.tg-exit-text { font-family: var(--gg-font-editorial); font-size: 14px; line-height: 1.6; color: var(--gg-color-primary-brown); margin: 0 0 20px; }
.tg-exit-row { display: flex; gap: 0; }
.tg-exit-input { flex: 1; font-family: var(--gg-font-data); font-size: 13px; padding: 12px 14px; border: 3px solid var(--gg-color-near-black); border-right: none; background: var(--gg-color-white); color: var(--gg-color-near-black); min-width: 0; }
.tg-exit-input:focus { outline: none; border-color: var(--gg-color-teal); }
.tg-exit-btn { font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; padding: 12px 18px; background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); border: 3px solid var(--gg-color-near-black); cursor: pointer; white-space: nowrap; transition: background 0.2s; }
.tg-exit-btn:hover { background: var(--gg-color-teal); border-color: var(--gg-color-teal); }
.tg-exit-fine { font-family: var(--gg-font-data); font-size: 10px; color: var(--gg-color-secondary-brown); letter-spacing: 1px; margin: 10px 0 0; }
@keyframes tg-fade-in { from { opacity: 0; } to { opacity: 1; } }
@keyframes tg-slide-up { from { transform: translateY(20px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }

@media (max-width: 480px) {
  .tg-email-capture-row { flex-direction: column; gap: 8px; }
  .tg-email-capture-input { border-right: 2px solid var(--gg-color-tan); }
  .tg-exit-row { flex-direction: column; gap: 8px; }
  .tg-exit-input { border-right: 3px solid var(--gg-color-near-black); }
  .tg-exit-modal { padding: 32px 20px; }
}

/* Print styles */
@media print {
  .tg-footer-cta { display: none; }
  .tg-email-capture { display: none; }
  .tg-tire-card { break-inside: avoid; }
}
"""


# ── HTML Builders ─────────────────────────────────────────────


def build_header(rd: dict) -> str:
    """Build page header with badge, race name, and vitals ribbon."""
    v = rd["vitals"]
    terrain_types = v.get("terrain_types", [])
    surface_type = terrain_types[0] if terrain_types else "Gravel"

    return f'''<header class="tg-header">
  <div class="tg-container">
    <div class="tg-breadcrumb">
      <a href="/">Gravel God</a> / <a href="/race/{esc(rd['slug'])}/">{esc(rd['name'])}</a> / Tire Guide
    </div>
    <span class="tg-badge">TIRE GUIDE</span>
    <h1>Best Tires for {esc(rd['name'])} {CURRENT_YEAR}</h1>
    <p class="tg-header-sub">Top 3 picks + pressure guide + setup strategy</p>
    <div class="tg-vitals">
      <div class="tg-vital"><strong>{esc(v['distance'])}</strong>Distance</div>
      <div class="tg-vital"><strong>{esc(v['elevation'])}</strong>Elevation</div>
      <div class="tg-vital"><strong>{esc(v['location'])}</strong>Location</div>
      <div class="tg-vital"><strong>{esc(surface_type)}</strong>Surface</div>
    </div>
  </div>
</header>'''


def build_surface_analysis(rd: dict, raw_race: dict, weather: dict) -> str:
    """Build Section 01: Course Surface Analysis."""
    terrain = raw_race.get("terrain", {})
    if not isinstance(terrain, dict):
        terrain = {"surface": str(terrain), "primary": str(terrain)}
    tech_rating = terrain.get("technical_rating", 2)
    surface = terrain.get("surface", "")
    if isinstance(surface, dict):
        surface = ", ".join(f"{k}: {v}%" for k, v in surface.items())
    primary = terrain.get("primary", "")
    if isinstance(primary, dict):
        primary = ", ".join(str(k) for k in primary.keys())
    features = terrain.get("features", terrain.get("notable_features", []))
    if not isinstance(features, list):
        features = [str(features)] if features else []

    tech_labels = {1: "LOW", 2: "MODERATE", 3: "HIGH", 4: "VERY HIGH", 5: "EXTREME"}
    tech_label = tech_labels.get(tech_rating, "MODERATE")

    features_html = ""
    if features:
        items = "".join(f"<li>{esc(f)}</li>" for f in features)
        features_html = f'<ul class="tg-features">{items}</ul>'

    weather_html = ""
    if weather:
        precip = weather.get("precip_chance_pct", 0)
        wind = weather.get("max_wind_mph", 0)
        high = weather.get("avg_high_f", 0)
        parts = []
        if precip:
            parts.append(f"Rain probability: {precip}%")
        if wind:
            parts.append(f"Max wind: {wind} mph")
        if high:
            parts.append(f"Avg high: {high}&deg;F")
        if parts:
            weather_html = f'''<div class="tg-weather-note">
        <strong>Race Day Weather Impact:</strong> {" | ".join(parts)}
      </div>'''

    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">01 / COURSE SURFACE ANALYSIS</span>
    <h2>What Your Tires Will Face</h2>
    <div class="tg-surface-box">
      <p><strong>{esc(primary)}</strong></p>
      <p>{esc(surface)}</p>
      <p>
        <span class="tg-tech-badge">TECHNICAL: {tech_label} ({tech_rating}/5)</span>
      </p>
      {features_html}
    </div>
    {weather_html}
  </div>
</section>'''


def build_tire_cards(top_picks: list, profile: dict, race_name: str,
                     front_rear: dict = None) -> str:
    """Build Section 02: Top 3 Tire Recommendations with real data."""
    cards = []
    for i, pick in enumerate(top_picks):
        tire = pick["tire"]
        width = pick["width"]
        rank = i + 1

        why_text = generate_why_text(tire, profile, race_name)

        # Price badge — real MSRP
        msrp = tire.get("msrp_usd")
        price_label = f"${msrp:.2f}" if msrp else "N/A"

        # Crr badge — real watts
        crr_data = tire.get("crr_watts_at_29kmh")
        crr_label = "Not independently tested"
        crr_class = ""
        if crr_data and isinstance(crr_data, dict):
            crr_val = next(iter(crr_data.values()), None)
            if crr_val is not None:
                crr_label = f"{crr_val}W @ 29km/h"
                if crr_val <= 30:
                    crr_class = "tg-badge-item--fast"

        # Weight badge — real grams
        weight_data = tire.get("weight_grams", {})
        weight_label = "N/A"
        if str(width) in weight_data:
            weight_label = f"{weight_data[str(width)]}g ({width}mm)"
        elif weight_data:
            w_key = next(iter(weight_data.keys()))
            weight_label = f"{weight_data[w_key]}g ({w_key}mm)"

        # Puncture resistance badge
        pr = tire.get("puncture_resistance", "moderate")
        pr_class = "tg-badge-item--high" if pr == "high" else ""
        pr_label = f"Protection: {pr.upper()}"

        # Strengths/weaknesses
        pros = "".join(f"<li>{esc(s)}</li>" for s in tire.get("strengths", []))
        cons = "".join(f"<li>{esc(w)}</li>" for w in tire.get("weaknesses", []))

        # BRR review link
        brr_url = tire.get("brr_urls_by_width", {}).get(str(width))
        if not brr_url:
            brr_url = next(iter(tire.get("brr_urls_by_width", {}).values()), "")
        review_link = ""
        if brr_url:
            review_link = f'<a href="{esc(brr_url)}" target="_blank" rel="noopener" class="tg-review-link">Read BRR Review &rarr;</a>'

        cards.append(f'''<div class="tg-tire-card">
      <div class="tg-tire-rank tg-tire-rank--{rank}">#{rank}</div>
      <div class="tg-tire-header">
        <span class="tg-tire-brand">{esc(tire['brand'])}</span>
        <h3 class="tg-tire-name">{esc(tire['name'])}</h3>
        <span class="tg-tire-width">Recommended: {width}mm &mdash; {price_label}</span>
      </div>
      <div class="tg-tire-body">
        <p class="tg-tire-tagline">{esc(tire.get('tagline', ''))}</p>
        <p class="tg-tire-why">{why_text}</p>
        <div class="tg-badges">
          <span class="tg-badge-item {crr_class}">Crr: {esc(crr_label)}</span>
          <span class="tg-badge-item {pr_class}">{esc(pr_label)}</span>
          <span class="tg-badge-item">Weight: {esc(weight_label)}</span>
        </div>
        <div class="tg-pros-cons">
          <div class="tg-pros"><h4>Strengths</h4><ul>{pros}</ul></div>
          <div class="tg-cons"><h4>Trade-offs</h4><ul>{cons}</ul></div>
        </div>
        {review_link}
      </div>
    </div>''')

    # Front/rear split callout
    split_html = ""
    if front_rear and front_rear.get("applicable"):
        f = front_rear["front"]
        r = front_rear["rear"]
        rationale = front_rear.get("rationale", "")
        split_html = f'''<div class="tg-alt-card" style="margin-top:var(--gg-spacing-lg);border-left:3px solid var(--gg-color-teal)">
      <div class="tg-alt-label">FRONT / REAR SPLIT OPTION</div>
      <p style="font-family:var(--gg-font-data);font-size:var(--gg-font-size-sm);margin-bottom:4px">
        <strong>Front:</strong> {esc(f['name'])} ({f['width_mm']}mm) &mdash;
        <strong>Rear:</strong> {esc(r['name'])} ({r['width_mm']}mm)
      </p>
      <p style="font-family:var(--gg-font-data);font-size:var(--gg-font-size-xs);color:var(--gg-color-secondary-brown)">{esc(rationale)}</p>
    </div>'''

    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">02 / TOP 3 TIRE RECOMMENDATIONS</span>
    <h2>Best Tires for {esc(race_name)}</h2>
    {''.join(cards)}
    {split_html}
  </div>
</section>'''


def build_pressure_section(pressure_rows: list, tech_rating: int, rec_width: int,
                           raw_race: dict) -> str:
    """Build Section 03: Tire Pressure Guide."""
    terrain = raw_race.get("terrain", {})
    if not isinstance(terrain, dict):
        terrain = {"surface": str(terrain), "primary": str(terrain)}
    surface_val = terrain.get("surface", "")
    if isinstance(surface_val, dict):
        surface_val = " ".join(str(k) for k in surface_val.keys())
    primary_val = terrain.get("primary", "")
    if isinstance(primary_val, dict):
        primary_val = " ".join(str(k) for k in primary_val.keys())
    surface = (str(surface_val) + " " + str(primary_val)).lower()

    rows_html = ""
    for row in pressure_rows:
        rows_html += f'''<tr>
      <td>{esc(row['weight_range'])}</td>
      <td>{esc(row['dry'])} psi</td>
      <td>{esc(row['mixed'])} psi</td>
      <td>{esc(row['wet'])} psi</td>
    </tr>'''

    # Race-specific pressure notes
    notes = []
    if any(kw in surface for kw in ["limestone", "flint", "sharp"]):
        notes.append("Sharp surfaces: err on the higher end to prevent pinch flats and rim damage.")
    if any(kw in surface for kw in ["mud", "clay"]):
        notes.append("Mud: drop 3-5 psi below 'wet' values for maximum traction.")
    if any(kw in surface for kw in ["sand", "loose"]):
        notes.append("Loose surfaces: lower pressure increases contact patch and traction.")
    if tech_rating >= 4:
        notes.append("Technical terrain: lower pressure improves grip but increases pinch flat risk. Find your balance.")

    notes_html = ""
    if notes:
        notes_items = " ".join(notes)
        notes_html = f'<p class="tg-pressure-note">{notes_items}</p>'

    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">03 / TIRE PRESSURE GUIDE</span>
    <h2>Pressure Recommendations ({rec_width}mm)</h2>
    <table class="tg-pressure-table">
      <thead>
        <tr>
          <th>Rider Weight</th>
          <th>Dry</th>
          <th>Mixed</th>
          <th>Wet</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
    {notes_html}
    <p class="tg-pressure-note">All pressures assume tubeless setup with 21-25mm internal width rims. Wider rims allow 2-3 PSI lower. Add 5-8 psi for tubes. Pressures are starting points &mdash; fine-tune during training rides on similar surfaces.</p>
  </div>
</section>'''


def build_setup_section(strategy: dict) -> str:
    """Build Section 04: Setup Strategy."""
    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">04 / SETUP STRATEGY</span>
    <h2>Race-Day Tire Setup</h2>
    <div class="tg-setup-grid">
      <div class="tg-setup-item">
        <h4>Tubeless</h4>
        <p><strong>{esc(strategy['tubeless_rec'])}</strong></p>
        <p>{esc(strategy['tubeless_note'])}</p>
      </div>
      <div class="tg-setup-item">
        <h4>Sealant</h4>
        <p><strong>{esc(strategy['sealant'])}</strong></p>
        <p>{esc(strategy['sealant_note'])}</p>
      </div>
      <div class="tg-setup-item">
        <h4>Spare Strategy</h4>
        <p>{esc(strategy['spare'])}</p>
      </div>
      <div class="tg-setup-item">
        <h4>Pre-Race Break-In</h4>
        <p>{esc(strategy['break_in'])}</p>
      </div>
    </div>
  </div>
</section>'''


def build_alternatives_section(alts: dict) -> str:
    """Build Section 05: Condition Alternatives."""
    if not alts.get("wet") and not alts.get("dry"):
        return ""

    cards = []
    if alts.get("wet"):
        t = alts["wet"]["tire"]
        w = alts["wet"]["width"]
        msrp = t.get("msrp_usd")
        price_str = f" &mdash; ${msrp:.2f}" if msrp else ""
        brr_url = t.get("brr_urls_by_width", {}).get(str(w)) or next(iter(t.get("brr_urls_by_width", {}).values()), "")
        review = f' <a href="{esc(brr_url)}" target="_blank" rel="noopener" style="color:var(--gg-color-teal)">Review &rarr;</a>' if brr_url else ""
        cards.append(f'''<div class="tg-alt-card">
      <div class="tg-alt-label">PLAN B: WET CONDITIONS</div>
      <h4>{esc(t['name'])} ({w}mm){price_str}</h4>
      <p>{esc(t.get('tagline', ''))}{review}</p>
    </div>''')

    if alts.get("dry"):
        t = alts["dry"]["tire"]
        w = alts["dry"]["width"]
        msrp = t.get("msrp_usd")
        price_str = f" &mdash; ${msrp:.2f}" if msrp else ""
        brr_url = t.get("brr_urls_by_width", {}).get(str(w)) or next(iter(t.get("brr_urls_by_width", {}).values()), "")
        review = f' <a href="{esc(brr_url)}" target="_blank" rel="noopener" style="color:var(--gg-color-teal)">Review &rarr;</a>' if brr_url else ""
        cards.append(f'''<div class="tg-alt-card">
      <div class="tg-alt-label">PLAN B: DRY CONDITIONS</div>
      <h4>{esc(t['name'])} ({w}mm){price_str}</h4>
      <p>{esc(t.get('tagline', ''))}{review}</p>
    </div>''')

    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">05 / CONDITION ALTERNATIVES</span>
    <h2>Plan B Tires</h2>
    {''.join(cards)}
  </div>
</section>'''


def build_email_capture_section(rd: dict) -> str:
    """Build email capture CTA — Race Day Setup Card download."""
    slug = esc(rd["slug"])
    name = esc(rd["name"])
    return f'''<section class="tg-section">
  <div class="tg-container">
    <div class="tg-email-capture">
      <div class="tg-email-capture-inner">
        <div class="tg-email-capture-badge">FREE DOWNLOAD</div>
        <h3 class="tg-email-capture-title">GET YOUR RACE DAY SETUP CARD</h3>
        <p class="tg-email-capture-text">Tire picks, pressure chart, sealant amounts, and tubeless tips &mdash; customized for {name}. Print it and tape it to your stem.</p>
        <form class="tg-email-capture-form" id="tg-email-capture-form" autocomplete="off">
          <input type="hidden" name="race_slug" value="{slug}">
          <input type="hidden" name="race_name" value="{name}">
          <input type="hidden" name="source" value="tire_guide">
          <input type="hidden" name="website" value="">
          <div class="tg-email-capture-row">
            <input type="email" name="email" required placeholder="your@email.com" class="tg-email-capture-input" aria-label="Email address">
            <button type="submit" class="tg-email-capture-btn">GET SETUP CARD</button>
          </div>
        </form>
        <div class="tg-email-capture-success" id="tg-email-capture-success" style="display:none">
          <p class="tg-email-capture-check">&#10003; Setup card unlocked!</p>
          <a href="/race/{slug}/tires/" class="tg-email-capture-link">View Your Tire Guide &rarr;</a>
        </div>
        <p class="tg-email-capture-fine">No spam. Unsubscribe anytime.</p>
      </div>
    </div>
  </div>
</section>'''


def build_inline_js() -> str:
    """Build inline JavaScript for email capture form and exit-intent popup."""
    return '''<script>
/* Email capture form — tire guide setup card CTA */
(function(){
  var WORKER_URL='https://fueling-lead-intake.gravelgodcoaching.workers.dev';
  var LS_KEY='gg-pk-fueling';
  var EXPIRY_DAYS=90;
  var form=document.getElementById('tg-email-capture-form');
  if(!form) return;

  /* Check if already captured (shared SSO with race profiles) */
  try{
    var cached=JSON.parse(localStorage.getItem(LS_KEY)||'null');
    if(cached&&cached.email&&cached.exp>Date.now()){
      form.style.display='none';
      var success=document.getElementById('tg-email-capture-success');
      if(success) success.style.display='block';
      return;
    }
  }catch(e){}

  form.addEventListener('submit',function(e){
    e.preventDefault();
    var email=form.email.value.trim();
    if(!email||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)){
      alert('Please enter a valid email address.');return;
    }
    if(form.website&&form.website.value) return;
    try{
      localStorage.setItem(LS_KEY,JSON.stringify({email:email,exp:Date.now()+EXPIRY_DAYS*86400000}));
    }catch(ex){}
    var payload={
      email:email,
      race_slug:form.race_slug.value,
      race_name:form.race_name.value,
      source:form.source.value,
      website:form.website.value
    };
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(function(){});
    if(typeof gtag==='function'){
      gtag('event','email_capture',{race_slug:form.race_slug.value,source:'tire_guide'});
    }
    form.style.display='none';
    var success=document.getElementById('tg-email-capture-success');
    if(success) success.style.display='block';
  });
})();

/* Exit-intent popup */
(function(){
  var LS_KEY='gg-exit-popup-dismissed';
  var WORKER_URL='https://fueling-lead-intake.gravelgodcoaching.workers.dev';
  var DISMISS_DAYS=14;
  try{
    var cached=JSON.parse(localStorage.getItem('gg-pk-fueling')||'null');
    if(cached&&cached.email&&cached.exp>Date.now()) return;
    var dismissed=parseInt(localStorage.getItem(LS_KEY)||'0',10);
    if(dismissed&&Date.now()<dismissed) return;
  }catch(e){}

  var shown=false;
  function createPopup(){
    if(shown) return;
    shown=true;
    try{localStorage.setItem(LS_KEY,String(Date.now()+DISMISS_DAYS*86400000));}catch(e){}
    var overlay=document.createElement('div');
    overlay.className='tg-exit-overlay';
    overlay.setAttribute('role','dialog');
    overlay.setAttribute('aria-modal','true');
    overlay.setAttribute('aria-label','Email signup');
    overlay.innerHTML='<div class="tg-exit-modal">'
      +'<button class="tg-exit-close" aria-label="Close">&times;</button>'
      +'<div class="tg-exit-badge">BEFORE YOU GO</div>'
      +'<h3 class="tg-exit-title">GET A FREE SETUP CARD</h3>'
      +'<p class="tg-exit-text">Get a printable tire setup card with pressures, sealant, and race-day tips for any gravel race.</p>'
      +'<form class="tg-exit-form" id="tg-exit-form" autocomplete="off">'
      +'<input type="hidden" name="source" value="exit_intent">'
      +'<input type="hidden" name="website" value="">'
      +'<div class="tg-exit-row">'
      +'<input type="email" name="email" required placeholder="your@email.com" class="tg-exit-input" aria-label="Email">'
      +'<button type="submit" class="tg-exit-btn">SEND IT</button>'
      +'</div></form>'
      +'<p class="tg-exit-fine">No spam. Unsubscribe anytime.</p>'
      +'</div>';
    document.body.appendChild(overlay);

    function closePopup(){overlay.remove();document.removeEventListener('keydown',escHandler);}
    function escHandler(e){if(e.key==='Escape') closePopup();}
    overlay.querySelector('.tg-exit-close').addEventListener('click',closePopup);
    overlay.addEventListener('click',function(e){if(e.target===overlay) closePopup();});
    document.addEventListener('keydown',escHandler);

    var emailInput=overlay.querySelector('.tg-exit-input');
    if(emailInput) emailInput.focus();
    overlay.addEventListener('keydown',function(e){
      if(e.key!=='Tab') return;
      var focusable=overlay.querySelectorAll('button,input,[tabindex]');
      var first=focusable[0],last=focusable[focusable.length-1];
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
      else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
    });

    var exitForm=document.getElementById('tg-exit-form');
    if(exitForm){
      exitForm.addEventListener('submit',function(ev){
        ev.preventDefault();
        var email=exitForm.email.value.trim();
        if(!email||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)){
          alert('Please enter a valid email.');return;
        }
        if(exitForm.website&&exitForm.website.value) return;
        try{localStorage.setItem('gg-pk-fueling',JSON.stringify({email:email,exp:Date.now()+90*86400000}));}catch(ex){}
        var payload={email:email,source:'exit_intent',website:exitForm.website.value};
        fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(function(){});
        if(typeof gtag==='function') gtag('event','email_capture',{source:'exit_intent'});
        overlay.querySelector('.tg-exit-modal').innerHTML='<div class="tg-exit-badge" style="background:#178079">DONE</div>'
          +'<h3 class="tg-exit-title">CHECK YOUR INBOX</h3>'
          +'<p class="tg-exit-text">Browse our <a href="/gravel-races/" style="color:#178079;text-decoration:underline">race profiles</a> to find your setup card.</p>';
        setTimeout(function(){overlay.remove();},4000);
      });
    }
  }

  document.addEventListener('mouseout',function(e){
    if(!e.relatedTarget&&e.clientY<5) createPopup();
  });
  var lastScroll=0;
  var triggered=false;
  window.addEventListener('scroll',function(){
    var st=window.pageYOffset||document.documentElement.scrollTop;
    if(st>500&&lastScroll-st>200&&!triggered){
      triggered=true;
      setTimeout(createPopup,500);
    }
    lastScroll=st;
  },{passive:true});
})();
</script>'''


def build_footer_cta(rd: dict) -> str:
    """Build footer CTA section."""
    return f'''<footer class="tg-footer-cta">
  <div class="tg-container">
    <div class="tg-footer-cta-inner">
      <a href="/race/{esc(rd['slug'])}/" class="tg-btn tg-btn--primary">Race Profile</a>
      <a href="/race/{esc(rd['slug'])}/prep-kit/" class="tg-btn tg-btn--outline">Get Free Prep Kit</a>
    </div>
  </div>
</footer>'''


def build_json_ld(rd: dict, top_picks: list) -> str:
    """Build schema.org JSON-LD: BreadcrumbList + Article + ItemList."""
    slug = rd["slug"]
    name = rd["name"]
    url = f"{SITE_BASE_URL}/race/{slug}/tires/"

    # BreadcrumbList
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Gravel God",
             "item": f"{SITE_BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": name,
             "item": f"{SITE_BASE_URL}/race/{slug}/"},
            {"@type": "ListItem", "position": 3, "name": "Tire Guide",
             "item": url},
        ]
    }

    # Article
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"Best Tires for {name} {CURRENT_YEAR}: Top 3 Picks + Pressure Guide",
        "url": url,
        "author": {"@type": "Organization", "name": "Gravel God"},
        "publisher": {
            "@type": "Organization",
            "name": "Gravel God",
            "url": SITE_BASE_URL,
        },
        "datePublished": datetime.now().strftime("%Y-%m-%d"),
        "dateModified": datetime.now().strftime("%Y-%m-%d"),
    }

    # ItemList (top 3 tires)
    item_list = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Top 3 Tires for {name}",
        "numberOfItems": len(top_picks),
        "itemListElement": [],
    }
    for i, pick in enumerate(top_picks):
        tire = pick["tire"]
        width = pick["width"]
        brr_url = tire.get("brr_urls_by_width", {}).get(str(width)) or next(iter(tire.get("brr_urls_by_width", {}).values()), "")
        item = {
            "@type": "ListItem",
            "position": i + 1,
            "name": f"{tire['name']} ({width}mm)",
        }
        if brr_url:
            item["url"] = brr_url
        item_list["itemListElement"].append(item)

    combined = json.dumps([breadcrumb, article, item_list], indent=2)
    return f'<script type="application/ld+json">{combined}</script>'


# ── Full Page Assembly ────────────────────────────────────────


def generate_tire_guide_page(rd: dict, raw_race: dict, weather: dict,
                             tire_db: list) -> str:
    """Generate complete tire guide HTML page.

    Uses enriched tire_recommendations from race JSON when available,
    otherwise computes on-the-fly.
    """
    # Step 1: Build race profile
    profile = build_race_profile(rd, raw_race, weather)
    tech_rating = profile["tech_rating"]

    # Check for pre-enriched data
    enriched = raw_race.get("tire_recommendations", {})
    tire_index = {t["id"]: t for t in tire_db}

    if enriched and enriched.get("primary"):
        # Use enriched data — reconstruct top_picks from tire database
        top_picks = []
        for rec in enriched["primary"][:3]:
            tire = tire_index.get(rec.get("tire_id"))
            if tire:
                top_picks.append({
                    "tire": tire,
                    "score": 0,
                    "width": rec.get("recommended_width_mm", 40),
                })
        front_rear = enriched.get("front_rear_split", {"applicable": False})
        # Ensure front/rear split has tire details for HTML
        if front_rear.get("applicable"):
            for key in ("front", "rear"):
                entry = front_rear.get(key, {})
                tid = entry.get("tire_id")
                if tid and tid in tire_index:
                    t = tire_index[tid]
                    entry.setdefault("name", t["name"])
                    entry.setdefault("brand", t["brand"])
                    entry.setdefault("msrp_usd", t.get("msrp_usd"))
    else:
        # Step 2: Filter, score, rank — get top 3
        top_picks = get_top_tires(tire_db, profile)
        # Step 3: Front/rear split
        front_rear = get_front_rear_split(tire_db, profile, top_picks)

    if not top_picks:
        top_picks = get_top_tires(tire_db, profile)
        front_rear = get_front_rear_split(tire_db, profile, top_picks)

    # Step 4: Recommended width from #1 tire
    rec_width = top_picks[0]["width"] if top_picks else 40

    # Build page sections
    header = build_header(rd)
    surface = build_surface_analysis(rd, raw_race, weather)
    tire_cards = build_tire_cards(top_picks, profile, rd["name"], front_rear)

    pressure_rows = compute_pressure_table(tech_rating, rec_width)
    pressure = build_pressure_section(pressure_rows, tech_rating, rec_width, raw_race)

    strategy = build_setup_strategy(tech_rating, rec_width, profile)
    setup = build_setup_section(strategy)

    alts = get_condition_alternatives(tire_db, profile, top_picks)
    alternatives = build_alternatives_section(alts)

    email_capture = build_email_capture_section(rd)
    inline_js = build_inline_js()
    footer = build_footer_cta(rd)
    json_ld = build_json_ld(rd, top_picks)

    # Page title and meta
    tire_names = ", ".join(p["tire"]["name"] for p in top_picks)
    title = f"Best Tires for {esc(rd['name'])} {CURRENT_YEAR}: Top 3 Picks + Pressure Guide | Gravel God"
    meta_desc = f"Top 3 tire recommendations for {rd['name']}: {tire_names}. Pressure chart, tubeless setup guide."

    canonical = f"{SITE_BASE_URL}/race/{rd['slug']}/tires/"

    page_css = get_page_css()
    tokens_css = get_tokens_css()
    font_css = get_font_face_css()
    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{esc(meta_desc)}">
  <link rel="canonical" href="{canonical}">

  <!-- OG -->
  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Gravel God Cycling">

  <!-- Preload fonts -->
  {preload}

  <style>
  {font_css}
  {tokens_css}
  {page_css}
  </style>

  {json_ld}

  <!-- GA4 -->
  {get_ga4_head_snippet()}
</head>
<body>
{header}
<main>
{surface}
{tire_cards}
{pressure}
{setup}
{alternatives}
{email_capture}
</main>
{footer}
{inline_js}
{get_consent_banner_html()}
</body>
</html>'''


# ── CLI ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate tire guide pages for gravel race profiles."
    )
    parser.add_argument('slug', nargs='?', help='Race slug (e.g., unbound-200)')
    parser.add_argument('--all', action='store_true', help='Generate pages for all races')
    parser.add_argument('--data-dir', help='Primary data directory (default: auto-detect)')
    parser.add_argument('--output-dir', default=None, help='Output directory')
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("Provide a race slug or use --all")

    # Resolve paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    data_dirs = []
    if args.data_dir:
        data_dirs.append(Path(args.data_dir))
    data_dirs.append(project_root / 'race-data')
    data_dirs.append(project_root / 'data')

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load tire database
    tire_db = load_tire_database()
    print(f"Loaded tire database: {len(tire_db)} tires")

    if args.all:
        # Generate for all races
        primary = None
        for d in data_dirs:
            d = Path(d)
            if d.exists() and list(d.glob('*.json')):
                primary = d
                break
        if not primary:
            print("ERROR: No data directory found with JSON files.", file=sys.stderr)
            sys.exit(1)

        files = sorted(primary.glob('*.json'))
        total = len(files)
        success = 0
        errors = []

        for i, filepath in enumerate(files, 1):
            slug = filepath.stem
            try:
                raw = json.loads(filepath.read_text(encoding="utf-8"))
                rd = normalize_race_data(raw)
                rd['slug'] = rd.get('slug') or slug
                rd['_file_mtime'] = datetime.fromtimestamp(filepath.stat().st_mtime).strftime('%Y-%m-%d')
                weather = load_weather_data(slug)

                html_content = generate_tire_guide_page(rd, raw.get("race", raw), weather, tire_db)
                out_path = output_dir / f"{slug}.html"
                out_path.write_text(html_content, encoding="utf-8")
                success += 1

                if i % 50 == 0 or i == total:
                    print(f"  [{i}/{total}] {success} generated, {len(errors)} errors")
            except Exception as e:
                errors.append((slug, str(e)))

        print(f"\nDone: {success}/{total} tire guide pages generated")
        if errors:
            print(f"Errors ({len(errors)}):")
            for slug, err in errors[:10]:
                print(f"  {slug}: {err}")
    else:
        # Single race
        filepath = find_data_file(args.slug, data_dirs)
        if not filepath:
            print(f"ERROR: Race data not found for '{args.slug}'", file=sys.stderr)
            print(f"  Searched: {', '.join(str(d) for d in data_dirs)}", file=sys.stderr)
            sys.exit(1)

        raw = json.loads(filepath.read_text(encoding="utf-8"))
        rd = normalize_race_data(raw)
        rd['slug'] = rd.get('slug') or args.slug
        rd['_file_mtime'] = datetime.fromtimestamp(filepath.stat().st_mtime).strftime('%Y-%m-%d')
        weather = load_weather_data(args.slug)

        html_content = generate_tire_guide_page(rd, raw.get("race", raw), weather, tire_db)
        out_path = output_dir / f"{args.slug}.html"
        out_path.write_text(html_content, encoding="utf-8")
        print(f"Generated: {out_path}")
        print(f"  URL: {SITE_BASE_URL}/race/{args.slug}/tires/")


if __name__ == '__main__':
    main()
