#!/usr/bin/env python3
"""
Generate Race Prep Kit pages — personalized 12-week timeline + race-day checklists.

Reads structured content from guide/gravel-guide-content.json and race profiles
from race-data/*.json to produce standalone, print-friendly HTML pages.

Two personalization tiers:
  - Full (235 races): training_config + non_negotiables → milestones injected
  - Generic (93 races): guide content + race context callout

Usage:
    python wordpress/generate_prep_kit.py unbound-200
    python wordpress/generate_prep_kit.py --all
    python wordpress/generate_prep_kit.py --all --output-dir /tmp/pk
"""

import argparse
import hashlib
import html
import json
import math
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Import shared constants from the race page generator
sys.path.insert(0, str(Path(__file__).parent))
from generate_neo_brutalist import (
    SITE_BASE_URL,
    SUBSTACK_URL,
    SUBSTACK_EMBED,
    COACHING_URL,
    TRAINING_PLANS_URL,
    normalize_race_data,
    find_data_file,
    load_race_data,
)
from generate_neo_brutalist import esc  # HTML escape helper

from brand_tokens import (
    GA_MEASUREMENT_ID,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
)
from shared_footer import get_mega_footer_css, get_mega_footer_html

# Disable glossary tooltips in guide renderers (we don't need them here)
import generate_guide
generate_guide._GLOSSARY = None
from generate_guide import (
    render_timeline,
    render_accordion,
    render_process_list,
    render_callout,
    _md_inline,
)

# ── Constants ──────────────────────────────────────────────────

GUIDE_DIR = Path(__file__).parent.parent / "guide"
CONTENT_JSON = GUIDE_DIR / "gravel-guide-content.json"
OUTPUT_DIR = Path(__file__).parent / "output" / "prep-kit"
CURRENT_YEAR = str(datetime.now().year)

# Guide section IDs we extract content from
GUIDE_SECTION_IDS = [
    "ch3-phases",       # 12-week training timeline
    "ch5-race-day",     # Race-day nutrition
    "ch5-gut-training", # Gut training timeline
    "ch6-decision-tree",# In-race decision tree
    "ch7-taper",        # Race week countdown
    "ch7-equipment",    # Equipment checklist
    "ch7-morning",      # Race morning protocol
    "ch8-immediate",    # Post-race recovery
]

# Phase boundaries for milestone bucketing
PHASE_RANGES = {
    "base":  (1, 4),
    "build": (5, 10),
    "taper": (11, 12),
}


# ── Data Loading ──────────────────────────────────────────────


def load_guide_sections() -> dict:
    """Extract the 8 target sections from guide JSON by ID.

    Returns dict mapping section ID → section dict (with 'blocks' list).
    """
    content = json.loads(CONTENT_JSON.read_text(encoding="utf-8"))
    sections = {}
    for chapter in content.get("chapters", []):
        for section in chapter.get("sections", []):
            if section.get("id") in GUIDE_SECTION_IDS:
                sections[section["id"]] = section
    return sections


def load_raw_training_data(filepath: Path) -> dict:
    """Load raw race JSON and extract training-specific fields.

    Returns dict with keys: training_config, non_negotiables, guide_variables,
    race_specific, plus the full raw data under 'raw'.
    """
    data = json.loads(filepath.read_text(encoding="utf-8"))
    race = data.get("race", data)
    return {
        "training_config": race.get("training_config"),
        "non_negotiables": race.get("non_negotiables"),
        "guide_variables": race.get("guide_variables"),
        "race_specific": race.get("race_specific"),
        "climate": race.get("climate", {}),
        "course_description": race.get("course_description", {}),
        "vitals": race.get("vitals", {}),
    }


def has_full_training_data(raw: dict) -> bool:
    """True if race has training_config AND non_negotiables for full personalization."""
    tc = raw.get("training_config")
    nn = raw.get("non_negotiables")
    return bool(tc) and bool(nn) and len(nn) > 0


# ── Personalization ───────────────────────────────────────────


def parse_by_when(text: str) -> Optional[int]:
    """Extract first week number from by_when text like 'Week 6' or 'Week 8-10'.

    Returns integer week number or None if unparseable.
    """
    if not text:
        return None
    m = re.search(r'[Ww]eek\s*(\d+)', text)
    return int(m.group(1)) if m else None


def week_to_phase(week: int) -> str:
    """Map a week number to its training phase name."""
    for phase, (lo, hi) in PHASE_RANGES.items():
        if lo <= week <= hi:
            return phase
    return "build"  # Default to build if out of range


def build_phase_extras(workout_mods: dict) -> dict:
    """Build workout mod chip HTML snippets bucketed by phase.

    Milestones are NOT included here — they appear in the dedicated
    Non-Negotiables section (Section 02) to avoid repetition.

    Returns dict mapping phase name → HTML string to inject after timeline content.
    """
    phase_mods = {"base": [], "build": [], "taper": []}
    for mod_name, mod_cfg in (workout_mods or {}).items():
        if not isinstance(mod_cfg, dict) or not mod_cfg.get("enabled"):
            continue
        week_str = mod_cfg.get("week", "")
        week = parse_by_when(f"Week {week_str}") if isinstance(week_str, (int, float)) else parse_by_when(str(week_str))
        if week:
            phase = week_to_phase(week)
        else:
            phase = "build"
        label = mod_name.replace("_", " ").title()
        phase_mods[phase].append(label)

    result = {}
    for phase in ("base", "build", "taper"):
        parts = []
        for mod_label in phase_mods.get(phase, []):
            parts.append(
                f'<span class="gg-pk-workout-mod">{esc(mod_label)}</span>'
            )
        result[phase] = "\n".join(parts)
    return result


def render_personalized_timeline(block: dict, phase_extras: dict) -> str:
    """Render timeline with injected milestone/mod HTML after each phase step.

    Like render_timeline() but appends extra HTML per phase (base/build/taper)
    after the content div, avoiding the esc() that render_timeline applies.
    """
    title = esc(block.get("title", ""))
    steps = block["steps"]
    phase_names = ["base", "build", "taper"]
    steps_html = []

    for i, step in enumerate(steps):
        label = esc(step["label"])
        content = _md_inline(esc(step["content"]))
        paras = [f'<p>{p.strip()}</p>' for p in content.split('\n') if p.strip()]

        phase = phase_names[i] if i < len(phase_names) else "taper"
        extra = phase_extras.get(phase, "")

        steps_html.append(f'''<div class="gg-guide-timeline-step">
        <div class="gg-guide-timeline-marker">{i + 1}</div>
        <div class="gg-guide-timeline-content">
          <h4 class="gg-guide-timeline-label">{label}</h4>
          {''.join(paras)}
          {extra}
        </div>
      </div>''')

    title_html = f'<h3 class="gg-guide-timeline-title">{title}</h3>' if title else ''
    return f'''<div class="gg-guide-timeline">
      {title_html}
      {''.join(steps_html)}
    </div>'''


def build_race_context_callout(raw: dict, rd: dict) -> str:
    """Build context callout box for generic-tier races (no training_config).

    Pulls distance, terrain, climate, signature challenge from available data.
    """
    parts = []

    distance = rd["vitals"].get("distance", "")
    if distance and distance != "--":
        parts.append(f"<strong>Distance:</strong> {esc(distance)}")

    elevation = rd["vitals"].get("elevation", "")
    if elevation and elevation != "--":
        parts.append(f"<strong>Elevation:</strong> {esc(elevation)}")

    location = rd["vitals"].get("location", "")
    if location and location != "--":
        parts.append(f"<strong>Location:</strong> {esc(location)}")

    climate = raw.get("climate", {})
    if isinstance(climate, dict):
        conditions = climate.get("race_day_conditions", "")
        if conditions:
            parts.append(f"<strong>Conditions:</strong> {esc(conditions)}")

    course = raw.get("course_description", {})
    if isinstance(course, dict):
        sig = course.get("signature_challenge", "")
        if sig:
            parts.append(f"<strong>Signature Challenge:</strong> {esc(sig)}")

    if not parts:
        return ""

    items = "".join(f"<p>{p}</p>" for p in parts)
    return f'''<div class="gg-pk-context-box">
      <div class="gg-pk-context-label">RACE CONTEXT: {esc(rd["name"].upper())}</div>
      {items}
    </div>'''


# ── Improvement Helpers ───────────────────────────────────────


def compute_wake_time(start_time_str: str) -> Optional[str]:
    """Parse start time and subtract 3 hours for wake-up alarm.

    Handles formats like 'Saturday 6:00 AM', 'Friday 1:00 PM',
    and multi-line strings (takes first time found).
    Returns formatted time string or None.
    """
    if not start_time_str:
        return None
    m = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', start_time_str, re.IGNORECASE)
    if not m:
        return None
    hour = int(m.group(1))
    minute = int(m.group(2))
    ampm = m.group(3).upper()
    # Convert to 24h
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0
    # Subtract 3 hours
    hour = (hour - 3) % 24
    # Convert back to 12h
    if hour == 0:
        return f"12:{minute:02d} AM"
    elif hour < 12:
        return f"{hour}:{minute:02d} AM"
    elif hour == 12:
        return f"12:{minute:02d} PM"
    else:
        return f"{hour - 12}:{minute:02d} PM"


def compute_fueling_estimate(distance_mi) -> Optional[dict]:
    """Estimate fueling needs based on race distance with duration-scaled carb rates.

    Carb absorption and utilization scale with intensity and duration per
    Jeukendrup (2014), van Loon et al. (2001), and Precision Fuel & Hydration
    field data. At lower intensities (longer races), fat oxidation dominates
    and GI distress limits practical carb intake. Returns dict or None.
    """
    if not distance_mi:
        return None
    try:
        distance_mi = int(distance_mi)
    except (ValueError, TypeError):
        return None
    if distance_mi < 20:
        return None
    # Conservative average gravel speeds (including mechanicals + stops)
    if distance_mi <= 50:
        avg_mph = 14
    elif distance_mi <= 100:
        avg_mph = 12
    elif distance_mi <= 150:
        avg_mph = 11
    else:
        avg_mph = 10
    hours = distance_mi / avg_mph

    # Duration-scaled carb rates (g/hr) — based on exercise physiology:
    # Shorter/harder races: high carb oxidation, standard Jeukendrup range
    # Longer races: lower intensity shifts fuel mix toward fat oxidation,
    # GI distress prevalence climbs from ~4% (4hr) to >80% (16hr+),
    # and splanchnic blood flow drops up to 80% during prolonged exercise.
    if hours <= 4:
        # High intensity race pace — standard dual-transport recommendation
        carb_lo, carb_hi = 80, 100
        note = "High-intensity race pace"
    elif hours <= 8:
        # Endurance pace — classic Jeukendrup range holds
        carb_lo, carb_hi = 60, 80
        note = "Endurance pace"
    elif hours <= 12:
        # Sub-threshold — fat oxidation increasing, GI risk climbing
        carb_lo, carb_hi = 50, 70
        note = "Lower intensity — fat oxidation increasing"
    elif hours <= 16:
        # Ultra pace — reverse crossover point, fat is primary fuel
        carb_lo, carb_hi = 40, 60
        note = "Ultra pace — fat is your primary fuel source"
    else:
        # Survival pace — GI distress prevalence >80%, appetite suppression
        carb_lo, carb_hi = 30, 50
        note = "Survival pace — palatability and GI tolerance are the limiters"

    carbs_low = int(hours * carb_lo)
    carbs_high = int(hours * carb_hi)
    gels_low = carbs_low // 25
    gels_high = carbs_high // 25
    return {
        "hours": round(hours, 1),
        "avg_mph": avg_mph,
        "carb_rate_lo": carb_lo,
        "carb_rate_hi": carb_hi,
        "carbs_low": carbs_low,
        "carbs_high": carbs_high,
        "gels_low": gels_low,
        "gels_high": gels_high,
        "note": note,
    }


def compute_personalized_fueling(weight_kg: float, ftp: Optional[float],
                                  hours: float) -> Optional[dict]:
    """Compute personalized carb targets using power-based formula.

    Uses the IronmanHacks/Couzens model:
        base_rate = weight_kg * 0.7 * (ftp / 100) * 0.7
    Falls back to duration-scaled generic rate when FTP is not provided.
    Clamps output to duration bracket ceiling/floor.

    Returns dict with personalized_rate, total_carbs, gels, bracket, note.
    """
    if not weight_kg or weight_kg <= 0 or not hours or hours <= 0:
        return None

    # Duration bracket bounds (same brackets as compute_fueling_estimate)
    if hours <= 4:
        bracket_lo, bracket_hi = 80, 100
        bracket = "High-intensity race pace"
    elif hours <= 8:
        bracket_lo, bracket_hi = 60, 80
        bracket = "Endurance pace"
    elif hours <= 12:
        bracket_lo, bracket_hi = 50, 70
        bracket = "Lower intensity — fat oxidation increasing"
    elif hours <= 16:
        bracket_lo, bracket_hi = 40, 60
        bracket = "Ultra pace — fat is your primary fuel source"
    else:
        bracket_lo, bracket_hi = 30, 50
        bracket = "Survival pace — palatability and GI tolerance are the limiters"

    if ftp and ftp > 0:
        # Power-based formula
        raw_rate = weight_kg * 0.7 * (ftp / 100) * 0.7
        note = "Personalized from your weight and FTP"
    else:
        # No FTP — use midpoint of bracket range
        raw_rate = (bracket_lo + bracket_hi) / 2
        note = "Enter your FTP for a more precise estimate"

    # Clamp to bracket bounds
    rate = max(bracket_lo, min(bracket_hi, round(raw_rate)))
    total_carbs = int(rate * hours)
    gels = total_carbs // 25

    return {
        "personalized_rate": rate,
        "total_carbs": total_carbs,
        "gels": gels,
        "bracket": bracket,
        "bracket_lo": bracket_lo,
        "bracket_hi": bracket_hi,
        "note": note,
    }


# ── Hydration / Sodium / Hour-by-Hour Plan ───────────────────

HEAT_MULTIPLIERS = {"cool": 0.7, "mild": 1.0, "warm": 1.3, "hot": 1.6, "extreme": 1.9}
SWEAT_MULTIPLIERS = {"light": 0.7, "moderate": 1.0, "heavy": 1.3}
FORMAT_SPLITS = {
    "liquid": {"drink": 0.80, "gel": 0.15, "food": 0.05},
    "gels":   {"drink": 0.20, "gel": 0.70, "food": 0.10},
    "mixed":  {"drink": 0.30, "gel": 0.40, "food": 0.30},
    "solid":  {"drink": 0.20, "gel": 0.20, "food": 0.60},
}
SODIUM_BASE_MG_PER_L = 1000
SODIUM_HEAT_BOOST = {"hot": 200, "extreme": 300}
SODIUM_CRAMP_BOOST = {"sometimes": 150, "frequent": 300}

# Item carb constants for hourly plan
GEL_CARBS = 25      # 1 gel = 25g carbs
DRINK_CARBS_500ML = 40  # 500ml mix = 40g carbs
BAR_CARBS = 35      # 1 bar/rice cake = 35g carbs


def classify_climate_heat(climate: Optional[dict], climate_score: Optional[int]) -> str:
    """Classify race climate into cool|mild|warm|hot|extreme at build time.

    Uses keyword analysis of climate.primary + climate.description + climate.challenges,
    with gravel_god_rating.climate score as tiebreaker.
    """
    if not climate or not isinstance(climate, dict):
        # Fall back to score-only classification
        if climate_score and climate_score >= 5:
            return "hot"
        if climate_score and climate_score >= 4:
            return "warm"
        return "mild"

    primary = (climate.get("primary") or "").lower()
    desc = (climate.get("description") or "").lower()
    challenges = climate.get("challenges", [])
    challenge_text = " ".join(c.lower() for c in challenges if isinstance(c, str))
    combined = f"{primary} {desc} {challenge_text}"

    score = climate_score or 0

    # Extreme: score=5 AND desert/extreme-specific keywords
    if score >= 5 and any(kw in combined for kw in ["desert", "extreme heat", "100+", "100°", "110°"]):
        return "extreme"

    # Hot: strong heat keywords AND score >= 4, OR very strong keywords alone
    strong_heat_kw = ["heat", "hot", "humid", "85-95", "90°", "95°"]
    if score >= 4 and any(kw in combined for kw in strong_heat_kw):
        return "hot"
    if any(kw in combined for kw in ["scorching", "brutal heat", "heat stroke"]):
        return "hot"

    # Cool: cold/freeze keywords
    if any(kw in combined for kw in ["cold", "freez", "winter", "snow", "30°", "40°", "5-12"]):
        return "cool"

    # Warm: heat-adjacent keywords with moderate score, or explicit warmth
    if any(kw in combined for kw in strong_heat_kw) and score >= 3:
        return "warm"
    if any(kw in combined for kw in ["warm", "summer", "sun", "75-85", "75°", "80°"]):
        return "warm"
    if score >= 4:
        return "warm"
    if score == 3:
        return "warm"

    return "mild"


def compute_sweat_rate(weight_kg: float, climate_heat: str,
                       sweat_tendency: str, hours: float) -> Optional[dict]:
    """Estimate sweat rate and fluid targets.

    Simplified model for lead-gen calculator (not a lab test).
    Returns dict with sweat_rate_l_hr, fluid targets in ml and oz, and note.
    """
    if not weight_kg or weight_kg <= 0 or not hours or hours <= 0:
        return None

    base_sweat = weight_kg * 0.013  # ~1 L/hr for 75kg
    heat_mult = HEAT_MULTIPLIERS.get(climate_heat, 1.0)
    sweat_mult = SWEAT_MULTIPLIERS.get(sweat_tendency, 1.0)

    # Intensity factor scales with duration
    if hours <= 4:
        intensity = 1.15
    elif hours <= 8:
        intensity = 1.0
    elif hours <= 12:
        intensity = 0.9
    elif hours <= 16:
        intensity = 0.8
    else:
        intensity = 0.7

    sweat_rate = base_sweat * heat_mult * sweat_mult * intensity
    # Fluid replacement target: 60-80% of sweat rate
    fluid_lo = sweat_rate * 0.6 * 1000  # ml
    fluid_hi = sweat_rate * 0.8 * 1000  # ml

    note = ""
    if climate_heat in ("hot", "extreme"):
        note = "High heat — pre-hydrate with 500ml 2 hours before start."
    elif climate_heat == "cool":
        note = "Cool conditions — you still sweat. Don't skip hydration."

    return {
        "sweat_rate_l_hr": round(sweat_rate, 2),
        "fluid_lo_ml_hr": round(fluid_lo),
        "fluid_hi_ml_hr": round(fluid_hi),
        "fluid_lo_oz_hr": round(fluid_lo / 29.5735),
        "fluid_hi_oz_hr": round(fluid_hi / 29.5735),
        "note": note,
    }


def compute_sodium(sweat_rate_l_hr: float, climate_heat: str,
                   cramp_history: str) -> Optional[dict]:
    """Compute sodium targets from sweat rate and conditions.

    Returns dict with sodium_mg_hr, total context, salt cap count, and note.
    """
    if not sweat_rate_l_hr or sweat_rate_l_hr <= 0:
        return None

    concentration = SODIUM_BASE_MG_PER_L
    concentration += SODIUM_HEAT_BOOST.get(climate_heat, 0)
    concentration += SODIUM_CRAMP_BOOST.get(cramp_history, 0)

    sodium_mg_hr = round(sweat_rate_l_hr * concentration)

    note = ""
    if cramp_history == "frequent":
        note = "History of cramping — consider pre-loading sodium the night before."
    elif climate_heat in ("hot", "extreme"):
        note = "Hot conditions increase sodium losses significantly."

    return {
        "sodium_mg_hr": sodium_mg_hr,
        "concentration_mg_l": concentration,
        "note": note,
    }


def compute_aid_station_hours(aid_text: str, distance_mi: float,
                              est_hours: float) -> list:
    """Best-effort parser for aid station timing from free-text vitals.

    Extracts mile markers or counts, converts to approximate hour marks.
    Returns list of floats (hour marks) or empty list.
    """
    if not aid_text or not isinstance(aid_text, str):
        return []

    text = aid_text.lower()

    # Self-supported or none
    if any(kw in text for kw in ["self-supported", "self supported", "none", "unsupported"]):
        return []
    if text.strip() in ("--", "—", ""):
        return []

    if not distance_mi or distance_mi <= 0 or not est_hours or est_hours <= 0:
        return []

    pace = est_hours / distance_mi  # hours per mile

    # Try mile markers: "mile ~30", "mile 50", etc.
    mile_markers = re.findall(r'mile\s*~?(\d+)', text)
    if mile_markers:
        hours = [round(int(m) * pace, 1) for m in mile_markers]
        return sorted(set(h for h in hours if 0 < h < est_hours))

    # Count-based: "2 full checkpoints + 2 water oases" → count all numbers before aid/check/feed/water/oases
    count_matches = re.findall(r'(\d+)\s*(?:full\s+)?(?:aid|checkpoint|feed|water|oases?|rest|refuel|zone)', text)
    if count_matches:
        total = sum(int(c) for c in count_matches)
        if total > 0:
            interval = est_hours / (total + 1)
            return [round(interval * (i + 1), 1) for i in range(total)]

    # Simple count: "9 fully-stocked feed zones"
    simple = re.search(r'(\d+)\s+(?:fully[- ]stocked\s+)?(?:feed|aid|rest|refuel)', text)
    if simple:
        total = int(simple.group(1))
        if total > 0:
            interval = est_hours / (total + 1)
            return [round(interval * (i + 1), 1) for i in range(total)]

    return []


def compute_hourly_plan(hours: float, carb_rate: int, fluid_ml_hr: int,
                        sodium_mg_hr: int, fuel_format: str,
                        aid_hours: list) -> list:
    """Build hour-by-hour race plan.

    Returns list of dicts, one per hour, with carbs, fluid, sodium, items, is_aid.
    """
    if not hours or hours <= 0 or not carb_rate or carb_rate <= 0:
        return []

    total_hours = math.ceil(hours)
    splits = FORMAT_SPLITS.get(fuel_format, FORMAT_SPLITS["mixed"])
    plan = []

    # Round aid hours to nearest int for matching
    aid_set = set(round(h) for h in (aid_hours or []))

    for h in range(1, total_hours + 1):
        # Hour 1 ramp-up: 80% rate. Last hour taper: 80% rate.
        # Fractional last hour: proportional rate.
        if h == 1:
            rate_mult = 0.8
        elif h == total_hours and hours % 1 > 0:
            rate_mult = hours % 1  # Fractional hour
        elif h == total_hours:
            rate_mult = 0.8
        else:
            rate_mult = 1.0

        hour_carbs = round(carb_rate * rate_mult)
        hour_fluid = round(fluid_ml_hr * rate_mult)
        hour_sodium = round(sodium_mg_hr * rate_mult)

        # Split carbs across formats
        drink_carbs = round(hour_carbs * splits["drink"])
        gel_carbs = round(hour_carbs * splits["gel"])
        food_carbs = hour_carbs - drink_carbs - gel_carbs  # remainder to food

        items = []
        if gel_carbs > 0:
            gel_count = max(1, round(gel_carbs / GEL_CARBS))
            items.append({"type": "gel", "label": f"{gel_count} gel{'s' if gel_count > 1 else ''} ({gel_count * GEL_CARBS}g)"})
        if drink_carbs > 0:
            drink_ml = round(drink_carbs / DRINK_CARBS_500ML * 500)
            items.append({"type": "drink", "label": f"{drink_ml}ml mix ({drink_carbs}g)"})
        if food_carbs > 0:
            bar_count = max(1, round(food_carbs / BAR_CARBS))
            items.append({"type": "food", "label": f"{bar_count} bar{'s' if bar_count > 1 else ''} ({bar_count * BAR_CARBS}g)"})

        is_aid = h in aid_set

        plan.append({
            "hour": h,
            "carbs_g": hour_carbs,
            "fluid_ml": hour_fluid,
            "sodium_mg": hour_sodium,
            "items": items,
            "is_aid": is_aid,
        })

    return plan


# Worker URL for fueling lead intake
FUELING_WORKER_URL = "https://fueling-lead-intake.gravelgodcoaching.workers.dev"


def build_fueling_calculator_html(rd: dict, raw: Optional[dict] = None) -> str:
    """Build the interactive fueling calculator form HTML for Section 6.

    Generates email-gated form with hydration/sodium fields, hidden results
    panel (3 panels: numbers, hourly plan, shopping list), and Substack iframe.
    All computation is client-side JS — the form posts to a Cloudflare Worker
    in the background for lead capture only.
    """
    slug = esc(rd["slug"])
    name = esc(rd["name"])
    raw = raw or {}

    # Pre-fill estimated hours from distance
    distance_mi = rd["vitals"].get("distance_mi", 0)
    est = compute_fueling_estimate(distance_mi)
    prefill_hours = est["hours"] if est else ""

    # Pre-classify climate at build time
    climate_data = raw.get("climate", {})
    rating = rd.get("rating", {})
    climate_score = rating.get("climate")
    climate_heat = classify_climate_heat(climate_data, climate_score)

    # Climate display text
    if isinstance(climate_data, dict) and climate_data.get("primary"):
        climate_display = climate_data["primary"]
    elif climate_heat == "mild":
        climate_display = "Mild (no climate data)"
    else:
        climate_display = climate_heat.capitalize()

    # Pre-compute aid station hours
    aid_text = rd["vitals"].get("aid_stations", "")
    aid_hours = compute_aid_station_hours(aid_text, distance_mi, prefill_hours if prefill_hours else 0)
    aid_json = esc(json.dumps(aid_hours))

    return f'''<div class="gg-pk-calc-wrapper">
    <h3 class="gg-pk-subsection-title">Personalized Fueling Calculator</h3>
    <p class="gg-pk-calc-intro">Enter your details for a complete race fueling plan — carbs, hydration, sodium, and an hour-by-hour strategy.</p>
    <form class="gg-pk-calc-form" id="gg-pk-calc-form" autocomplete="off">
      <input type="hidden" name="race_slug" value="{slug}">
      <input type="hidden" name="race_name" value="{name}">
      <input type="hidden" name="est_hours" value="{prefill_hours}">
      <input type="hidden" name="climate_heat" value="{esc(climate_heat)}">
      <input type="hidden" name="aid_station_hours" value="{aid_json}">
      <input type="hidden" name="website" value="">
      <div class="gg-pk-calc-field">
        <label for="gg-pk-email">Email <span class="gg-pk-calc-req">*</span></label>
        <input type="email" id="gg-pk-email" name="email" required placeholder="you@example.com" class="gg-pk-calc-input">
      </div>
      <div class="gg-pk-calc-field">
        <label for="gg-pk-weight">Weight (lbs) <span class="gg-pk-calc-req">*</span></label>
        <input type="number" id="gg-pk-weight" name="weight_lbs" required min="80" max="400" placeholder="165" class="gg-pk-calc-input">
      </div>
      <div class="gg-pk-calc-field">
        <label for="gg-pk-height-ft">Height</label>
        <div class="gg-pk-calc-height-row">
          <select id="gg-pk-height-ft" name="height_ft" class="gg-pk-calc-select">
            <option value="">ft</option>
            <option value="4">4&#x2032;</option>
            <option value="5">5&#x2032;</option>
            <option value="6">6&#x2032;</option>
            <option value="7">7&#x2032;</option>
          </select>
          <select id="gg-pk-height-in" name="height_in" class="gg-pk-calc-select">
            <option value="">in</option>
            {"".join(f'<option value="{i}">{i}&#x2033;</option>' for i in range(12))}
          </select>
        </div>
      </div>
      <div class="gg-pk-calc-field">
        <label for="gg-pk-age">Age</label>
        <input type="number" id="gg-pk-age" name="age" min="13" max="99" placeholder="35" class="gg-pk-calc-input">
      </div>
      <div class="gg-pk-calc-field">
        <label for="gg-pk-ftp">FTP (watts) <span class="gg-pk-calc-tooltip" title="Functional Threshold Power. Leave blank if unknown.">&#9432;</span></label>
        <input type="number" id="gg-pk-ftp" name="ftp" min="50" max="500" placeholder="220" class="gg-pk-calc-input">
      </div>
      <div class="gg-pk-calc-field">
        <label for="gg-pk-hours">Target finish time (hours)</label>
        <input type="number" id="gg-pk-hours" name="target_hours" min="1" max="48" step="0.5" placeholder="{prefill_hours}" value="{prefill_hours}" class="gg-pk-calc-input">
      </div>
      <div class="gg-pk-calc-field gg-pk-calc-field--climate">
        <label>Race Climate</label>
        <div class="gg-pk-calc-climate-badge gg-pk-calc-climate--{esc(climate_heat)}">{esc(climate_display)}</div>
      </div>
      <div class="gg-pk-calc-field">
        <label for="gg-pk-sweat">Sweat tendency <span class="gg-pk-calc-tooltip" title="How much do you sweat compared to other riders?">&#9432;</span></label>
        <select id="gg-pk-sweat" name="sweat_tendency" class="gg-pk-calc-select">
          <option value="moderate">Moderate (average)</option>
          <option value="light">Light sweater</option>
          <option value="heavy">Heavy sweater</option>
        </select>
      </div>
      <div class="gg-pk-calc-field">
        <label for="gg-pk-format">Fuel preference</label>
        <select id="gg-pk-format" name="fuel_format" class="gg-pk-calc-select">
          <option value="mixed">Mixed (gels + food + drink)</option>
          <option value="liquid">Mostly liquid (drink mix)</option>
          <option value="gels">Mostly gels</option>
          <option value="solid">Mostly solid food</option>
        </select>
      </div>
      <div class="gg-pk-calc-field">
        <label for="gg-pk-cramp">Cramping history <span class="gg-pk-calc-tooltip" title="Do you experience muscle cramps during or after long rides?">&#9432;</span></label>
        <select id="gg-pk-cramp" name="cramp_history" class="gg-pk-calc-select">
          <option value="rarely">Rarely / never</option>
          <option value="sometimes">Sometimes</option>
          <option value="frequent">Frequently</option>
        </select>
      </div>
      <button type="submit" class="gg-pk-calc-btn">GET MY FUELING PLAN</button>
    </form>
    <div class="gg-pk-calc-result" id="gg-pk-calc-result" style="display:none" aria-live="polite"></div>
    <div class="gg-pk-calc-substack" id="gg-pk-calc-substack" style="display:none">
      <p class="gg-pk-calc-substack-label">Get race-day tips in your inbox</p>
      <iframe src="{esc(SUBSTACK_EMBED)}" title="Newsletter signup" width="100%" height="150" style="border:none;background:transparent" frameborder="0" scrolling="no" loading="lazy"></iframe>
    </div>
  </div>'''


def build_climate_gear_callout(climate_data: dict) -> str:
    """Build climate-adapted gear recommendations based on race conditions."""
    if not climate_data or not isinstance(climate_data, dict):
        return ""
    desc = (climate_data.get("description", "") or "").lower()
    challenges = climate_data.get("challenges", [])
    challenge_text = " ".join(c.lower() for c in challenges if isinstance(c, str))
    combined = desc + " " + challenge_text

    recs = []
    if any(kw in combined for kw in ["heat", "hot", "90", "95", "100", "sun"]):
        recs.extend([
            "Sun sleeves or arm coolers",
            "Extra water bottles or hydration vest",
            "Electrolyte supplements (extra sodium)",
            "Light-colored kit",
        ])
    if any(kw in combined for kw in ["cold", "freez", "40°", "30°", "snow", "ice"]):
        recs.extend([
            "Knee warmers or leg warmers",
            "Wind vest or thermal layer",
            "Full-finger gloves",
            "Toe covers",
        ])
    if any(kw in combined for kw in ["rain", "wet", "mud"]):
        recs.extend([
            "Lightweight rain jacket (packable)",
            "Mudguards or frame protection",
            "Extra chain lube",
            "Clear or yellow lens glasses",
        ])
    if any(kw in combined for kw in ["wind", "exposed"]):
        recs.extend(["Wind vest", "Aero positioning practice"])
    if not recs:
        return ""

    # Deduplicate — also skip if a more detailed version already exists
    # (e.g. "Wind vest" skipped when "Wind vest or thermal layer" is present)
    seen = []
    unique_recs = []
    for r in recs:
        if r not in seen and not any(r in existing for existing in seen):
            seen.append(r)
            unique_recs.append(r)

    items = "".join(f"<li>{esc(r)}</li>" for r in unique_recs)
    primary = esc(climate_data.get("primary", "Race-day conditions"))
    return f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Climate Gear ({primary}):</strong></p>
        <ul>{items}</ul>
      </div>'''


def build_terrain_emphasis_callout(rd: dict) -> str:
    """Build terrain-adapted training emphasis based on technicality and terrain."""
    rating = rd.get("rating", {})
    tech = rating.get("technicality", 0) or 0
    terrain_types = rd["vitals"].get("terrain_types", [])
    elevation = rd["vitals"].get("elevation", "")
    distance_mi = rd["vitals"].get("distance_mi", 0) or 0

    tips = []
    if tech >= 4:
        tips.append(
            "Add 1 MTB skills session per week during Build phase (weeks 5-10)"
            " \u2014 focus on line choice, loose surface cornering, and"
            " dismount/remount"
        )
    elif tech >= 3:
        tips.append(
            "Include off-road skills work every 2 weeks \u2014 practice loose"
            " gravel descending and rough surface handling"
        )

    # Check for elevation-heavy courses
    elev_ft = 0
    if elevation:
        m = re.search(r'([\d,]+)\s*ft', elevation)
        if m:
            elev_ft = int(m.group(1).replace(',', ''))
    if distance_mi > 0 and elev_ft > 0:
        ft_per_mile = elev_ft / distance_mi
        if ft_per_mile > 80:
            tips.append(
                f"Include 2 extended climbing intervals per week (20-30 min at"
                f" threshold) \u2014 this course averages {ft_per_mile:.0f}"
                f" ft/mile of climbing"
            )

    terrain_str = ", ".join(terrain_types[:3]) if terrain_types else ""
    if terrain_str and any(
        kw in terrain_str.lower() for kw in ["sand", "mud", "clay"]
    ):
        tips.append(
            f"Train on similar surfaces ({terrain_str}) at least once per week"
            f" to build specific handling confidence"
        )

    if not tips:
        return ""

    items = "".join(f"<li>{esc(t)}</li>" for t in tips)
    return f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Race-Specific Training Focus:</strong></p>
        <ul>{items}</ul>
      </div>'''


# ── Section Builders ──────────────────────────────────────────


def build_pk_header(rd: dict, raw: dict) -> str:
    """Build header with race name and vitals ribbon."""
    name = esc(rd["name"])
    vitals = rd["vitals"]

    stats = []
    if vitals.get("distance") and vitals["distance"] != "--":
        stats.append(f'<span class="gg-pk-stat"><strong>{esc(vitals["distance"])}</strong></span>')
    if vitals.get("elevation") and vitals["elevation"] != "--":
        stats.append(f'<span class="gg-pk-stat"><strong>{esc(vitals["elevation"])}</strong></span>')
    if vitals.get("date") and vitals["date"] != "--":
        stats.append(f'<span class="gg-pk-stat">{esc(vitals["date"])}</span>')
    if vitals.get("location") and vitals["location"] != "--":
        stats.append(f'<span class="gg-pk-stat">{esc(vitals["location"])}</span>')

    ribbon = f'<div class="gg-pk-vitals-ribbon">{" ".join(stats)}</div>' if stats else ""

    is_full = has_full_training_data(raw)
    tier_label = "PERSONALIZED" if is_full else "GUIDE"

    return f'''<header class="gg-pk-header">
    <div class="gg-pk-header-badge">{tier_label} PREP KIT</div>
    <h1 class="gg-pk-header-title">{name}</h1>
    <p class="gg-pk-header-subtitle">12-Week Training Timeline &bull; Race-Day Checklists &bull; Packing List</p>
    {ribbon}
  </header>'''


def build_pk_training_timeline(guide_sections: dict, raw: dict, rd: dict) -> str:
    """Build Section 1: 12-Week Training Timeline."""
    section = guide_sections.get("ch3-phases")
    if not section:
        return ""

    # Find the timeline block
    timeline_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "timeline":
            timeline_block = block
            break

    if not timeline_block:
        return ""

    if has_full_training_data(raw):
        # Full personalization: inject workout mod chips after each phase
        # (milestones are shown in the dedicated Non-Negotiables section)
        mods = (raw.get("training_config") or {}).get("workout_modifications", {})
        extras = build_phase_extras(mods)
        timeline_html = render_personalized_timeline(timeline_block, extras)
    else:
        # Generic: render standard timeline + race context callout
        timeline_html = render_timeline(timeline_block)
        context = build_race_context_callout(raw, rd)
        if context:
            timeline_html = context + timeline_html

    # Terrain-adapted training emphasis (both tiers)
    terrain_callout = build_terrain_emphasis_callout(rd)

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">01</span>
      <h2>12-Week Training Timeline</h2>
    </div>
    {terrain_callout}
    {timeline_html}
  </section>'''


def build_pk_non_negotiables(raw: dict) -> str:
    """Build Section 2: Race-Specific Non-Negotiables. Empty for generic races."""
    if not has_full_training_data(raw):
        return ""

    nn_list = raw.get("non_negotiables", [])
    if not nn_list:
        return ""

    cards = []
    for nn in nn_list:
        req = esc(nn.get("requirement", ""))
        by_when = esc(nn.get("by_when", ""))
        why = esc(nn.get("why", ""))
        cards.append(f'''<div class="gg-pk-nn-card">
        <div class="gg-pk-nn-req">{req}</div>
        <span class="gg-pk-nn-badge">{by_when}</span>
        <p class="gg-pk-nn-why">{why}</p>
      </div>''')

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">02</span>
      <h2>Race-Specific Non-Negotiables</h2>
    </div>
    <div class="gg-pk-nn-grid">
      {"".join(cards)}
    </div>
  </section>'''


def build_pk_race_week(guide_sections: dict, raw: dict) -> str:
    """Build Section 3: Race Week Countdown (7-day taper)."""
    section = guide_sections.get("ch7-taper")
    if not section:
        return ""

    timeline_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "timeline":
            timeline_block = block
            break

    if not timeline_block:
        return ""

    # Add weather callout if available
    weather_html = ""
    gv = raw.get("guide_variables", {})
    if isinstance(gv, dict):
        weather = gv.get("race_weather", "")
        if weather:
            weather_html = f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Expected Conditions:</strong> {esc(weather)}</p>
      </div>'''

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">03</span>
      <h2>Race Week Countdown</h2>
    </div>
    {weather_html}
    {render_timeline(timeline_block)}
  </section>'''


def build_pk_equipment(guide_sections: dict, raw: dict, rd: dict) -> str:
    """Build Section 4: Equipment & Packing Checklist."""
    section = guide_sections.get("ch7-equipment")
    if not section:
        return ""

    accordion_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "accordion":
            accordion_block = block
            break

    if not accordion_block:
        return ""

    # Check for race-specific tire recommendations (Unbound has mechanicals)
    tire_html = ""
    rs = raw.get("race_specific")
    if isinstance(rs, dict):
        mechs = rs.get("mechanicals", {})
        if isinstance(mechs, dict):
            tires = mechs.get("recommended_tires", [])
            if tires:
                tire_items = "".join(f"<li>{esc(t)}</li>" for t in tires)
                tire_html = f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Recommended Tires:</strong></p>
        <ul>{tire_items}</ul>
      </div>'''

    # Climate-adapted gear recommendations
    climate_html = build_climate_gear_callout(rd.get("climate_data", {}))

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">04</span>
      <h2>Equipment &amp; Packing Checklist</h2>
    </div>
    {tire_html}
    {climate_html}
    {render_accordion(accordion_block)}
  </section>'''


def build_pk_race_morning(guide_sections: dict, rd: dict) -> str:
    """Build Section 5: Race Morning Protocol."""
    section = guide_sections.get("ch7-morning")
    if not section:
        return ""

    timeline_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "timeline":
            timeline_block = block
            break

    if not timeline_block:
        return ""

    # Add start time + computed wake-up time callout
    start_html = ""
    start_time = rd["vitals"].get("start_time", "")
    if start_time:
        wake = compute_wake_time(start_time)
        wake_line = f' Set your alarm for <strong>{esc(wake)}</strong>.' if wake else ""
        start_html = f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>{esc(rd["name"])} Start Time:</strong> {esc(start_time)}.{wake_line}</p>
      </div>'''

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">05</span>
      <h2>Race Morning Protocol</h2>
    </div>
    {start_html}
    {render_timeline(timeline_block)}
  </section>'''


def build_pk_fueling(guide_sections: dict, raw: dict, rd: dict) -> str:
    """Build Section 6: Race-Day Fueling (race-day nutrition + gut training)."""
    parts = []

    # Distance-adjusted fueling estimate (duration-scaled carb rates)
    distance_mi = rd["vitals"].get("distance_mi", 0)
    estimate = compute_fueling_estimate(distance_mi)
    if estimate:
        parts.append(
            f'<div class="gg-guide-callout gg-guide-callout--highlight">'
            f'<p><strong>Your Fueling Math ({distance_mi} miles):</strong> '
            f'At ~{estimate["avg_mph"]}mph, expect ~{estimate["hours"]} hours'
            f' on course. {estimate["note"]} \u2014 target '
            f'<strong>{estimate["carb_rate_lo"]}-{estimate["carb_rate_hi"]}g'
            f' carbs/hour</strong> ({estimate["carbs_low"]}-'
            f'{estimate["carbs_high"]}g total, or '
            f'{estimate["gels_low"]}-{estimate["gels_high"]} gels).</p>'
            f'<p style="font-size:12px;color:var(--gg-color-secondary-brown)">'
            f'Carb targets scale with duration: shorter races burn more carbs'
            f' per hour at race intensity, while ultra-distance events shift'
            f' toward fat oxidation and GI tolerance becomes the limiter'
            f' (Jeukendrup 2014, van Loon et al.).</p>'
            f'</div>'
        )

    # Personalized fueling calculator (email-gated)
    parts.append(build_fueling_calculator_html(rd, raw))

    # Aid station info
    aid_info = rd["vitals"].get("aid_stations", "")
    if aid_info and aid_info != "--":
        parts.append(
            f'<div class="gg-guide-callout gg-guide-callout--highlight">'
            f'<p><strong>Aid Stations:</strong> {esc(aid_info)}</p>'
            f'</div>'
        )

    # Race-day nutrition timeline
    rd_section = guide_sections.get("ch5-race-day")
    if rd_section:
        for block in rd_section.get("blocks", []):
            if block.get("type") == "timeline":
                parts.append(render_timeline(block))
                break

    # Aggressive fueling callout if enabled
    tc = raw.get("training_config")
    if isinstance(tc, dict):
        mods = tc.get("workout_modifications", {})
        af = mods.get("aggressive_fueling", {})
        if isinstance(af, dict) and af.get("enabled"):
            settings = af.get("settings", {})
            target = settings.get("target_carbs_per_hour", "")
            if target:
                parts.append(
                    f'<div class="gg-guide-callout gg-guide-callout--highlight">'
                    f'<p><strong>Target:</strong> {esc(target)}g carbs/hour during race</p>'
                    f'</div>'
                )

    # Gut training timeline
    gt_section = guide_sections.get("ch5-gut-training")
    if gt_section:
        for block in gt_section.get("blocks", []):
            if block.get("type") == "timeline":
                parts.append(f'<h3 class="gg-pk-subsection-title">Gut Training Protocol</h3>')
                parts.append(render_timeline(block))
                break

    if not parts:
        return ""

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">06</span>
      <h2>Race-Day Fueling</h2>
    </div>
    {"".join(parts)}
  </section>'''


def build_pk_decision_tree(guide_sections: dict, rd: dict) -> str:
    """Build Section 7: In-Race Decision Tree."""
    section = guide_sections.get("ch6-decision-tree")
    if not section:
        return ""

    accordion_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "accordion":
            accordion_block = block
            break

    if not accordion_block:
        return ""

    # Add suffering zones callout if available
    zones_html = ""
    suffering = rd["course"].get("suffering_zones", [])
    if suffering:
        zone_parts = []
        for z in suffering[:5]:
            if isinstance(z, dict):
                label = z.get("label", "")
                desc = z.get("desc", "")
                mile = z.get("mile")
                prefix = f"Mile {mile}: " if mile else ""
                suffix = f" — {esc(desc)}" if desc else ""
                zone_parts.append(f"<li><strong>{esc(prefix)}{esc(label)}</strong>{suffix}</li>")
            else:
                zone_parts.append(f"<li>{esc(z)}</li>")
        zone_items = "".join(zone_parts)
        zones_html = f'''<div class="gg-guide-callout gg-guide-callout--highlight">
        <p><strong>Known Suffering Zones:</strong></p>
        <ul>{zone_items}</ul>
      </div>'''

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">07</span>
      <h2>In-Race Decision Tree</h2>
    </div>
    {zones_html}
    {render_accordion(accordion_block)}
  </section>'''


def build_pk_recovery(guide_sections: dict) -> str:
    """Build Section 8: Post-Race Recovery."""
    section = guide_sections.get("ch8-immediate")
    if not section:
        return ""

    process_block = None
    for block in section.get("blocks", []):
        if block.get("type") == "process_list":
            process_block = block
            break

    if not process_block:
        return ""

    return f'''<section class="gg-pk-section">
    <div class="gg-pk-section-header">
      <span class="gg-pk-section-num">08</span>
      <h2>Post-Race Recovery</h2>
    </div>
    {render_process_list(process_block)}
  </section>'''


def build_pk_footer_cta(rd: dict) -> str:
    """Build footer CTA linking to training plans and newsletter."""
    name = esc(rd["name"])
    slug = esc(rd["slug"])
    return f'''<footer class="gg-pk-footer">
    <div class="gg-pk-footer-inner">
      <h3>Ready to Race {name}?</h3>
      <p>This free prep kit covers the essentials. For a fully personalized plan built
         specifically for {name} — structured workouts, nutrition protocols, and race-day
         strategy — get a custom training plan.</p>
      <div class="gg-pk-footer-buttons">
        <a href="{esc(TRAINING_PLANS_URL)}" class="gg-pk-btn gg-pk-btn--primary">BUILD MY PLAN &mdash; $15/WK</a>
        <a href="{esc(COACHING_URL)}" class="gg-pk-btn gg-pk-btn--secondary">1:1 COACHING</a>
      </div>
      <p class="gg-pk-footer-back">
        <a href="/race/{slug}/">Back to {name} Race Profile</a>
      </p>
    </div>
  </footer>'''


# ── CSS ───────────────────────────────────────────────────────


def build_prep_kit_css() -> str:
    """Build complete CSS for prep kit pages."""
    return """/* ── Prep Kit Layout ── */
.gg-pk-page{max-width:800px;margin:0 auto;padding:24px 20px;background:var(--gg-color-warm-paper);color:var(--gg-color-near-black);font-family:var(--gg-font-editorial)}

/* ── Header ── */
.gg-pk-header{text-align:center;padding:32px 0 24px;border-bottom:3px solid var(--gg-color-near-black);margin-bottom:32px}
.gg-pk-header-badge{display:inline-block;font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;background:var(--gg-color-near-black);color:var(--gg-color-warm-paper);padding:4px 12px;margin-bottom:12px}
.gg-pk-header-title{font-family:var(--gg-font-data);font-size:32px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 8px;color:var(--gg-color-near-black)}
.gg-pk-header-subtitle{font-family:var(--gg-font-data);font-size:13px;color:var(--gg-color-secondary-brown);margin:0 0 16px;letter-spacing:1px}
.gg-pk-vitals-ribbon{display:flex;flex-wrap:wrap;justify-content:center;gap:16px;padding-top:16px;border-top:2px solid var(--gg-color-tan)}
.gg-pk-stat{font-family:var(--gg-font-data);font-size:13px;color:var(--gg-color-primary-brown)}

/* ── Sections ── */
.gg-pk-section{margin-bottom:40px;page-break-inside:avoid}
.gg-pk-section-header{display:flex;align-items:baseline;gap:12px;border-bottom:3px solid var(--gg-color-near-black);padding-bottom:8px;margin-bottom:20px}
.gg-pk-section-num{font-family:var(--gg-font-data);font-size:14px;font-weight:700;color:var(--gg-color-teal);letter-spacing:1px}
.gg-pk-section-header h2{font-family:var(--gg-font-data);font-size:18px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0;color:var(--gg-color-near-black)}
.gg-pk-subsection-title{font-family:var(--gg-font-data);font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:24px 0 12px;color:var(--gg-color-primary-brown)}

/* ── Non-Negotiable Cards ── */
.gg-pk-nn-grid{display:grid;gap:16px}
.gg-pk-nn-card{border:2px solid var(--gg-color-near-black);padding:16px;background:var(--gg-color-white)}
.gg-pk-nn-req{font-family:var(--gg-font-data);font-size:14px;font-weight:700;color:var(--gg-color-near-black);margin-bottom:8px}
.gg-pk-nn-badge{display:inline-block;font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;background:var(--gg-color-teal);color:var(--gg-color-white);padding:2px 8px;margin-bottom:8px}
.gg-pk-nn-why{font-size:13px;line-height:1.6;color:var(--gg-color-primary-brown);margin:0}

/* ── Milestone + Workout Mod Chips ── */
.gg-pk-milestone{border-left:4px solid var(--gg-color-teal);padding:8px 12px;margin-top:12px;background:rgba(23,128,121,0.06);font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-near-black)}
.gg-pk-milestone-badge{display:inline-block;background:var(--gg-color-teal);color:var(--gg-color-white);font-size:10px;font-weight:700;padding:2px 6px;margin-right:8px;letter-spacing:1px;text-transform:uppercase}
.gg-pk-workout-mod{display:inline-block;font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;background:var(--gg-color-gold);color:var(--gg-color-white);padding:3px 8px;margin:8px 6px 0 0}

/* ── Context Box (generic races) ── */
.gg-pk-context-box{border:2px solid var(--gg-color-near-black);padding:16px 20px;margin-bottom:20px;background:var(--gg-color-white)}
.gg-pk-context-label{font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-teal);margin-bottom:8px}
.gg-pk-context-box p{font-size:13px;line-height:1.6;margin:4px 0;color:var(--gg-color-primary-brown)}

/* ── Footer CTA ── */
.gg-pk-footer{border-top:3px solid var(--gg-color-near-black);padding:32px 0 16px;text-align:center;margin-top:40px}
.gg-pk-footer-inner h3{font-family:var(--gg-font-data);font-size:20px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px}
.gg-pk-footer-inner p{font-size:14px;line-height:1.6;color:var(--gg-color-primary-brown);max-width:560px;margin:0 auto 20px}
.gg-pk-footer-buttons{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin-bottom:24px}
.gg-pk-btn{display:inline-block;font-family:var(--gg-font-data);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:2px;padding:12px 24px;text-decoration:none;text-align:center;transition:background 0.2s,color 0.2s}
.gg-pk-btn--primary{background:var(--gg-color-near-black);color:var(--gg-color-warm-paper);border:3px solid var(--gg-color-near-black)}
.gg-pk-btn--primary:hover{background:var(--gg-color-primary-brown);border-color:var(--gg-color-primary-brown)}
.gg-pk-btn--secondary{background:transparent;color:var(--gg-color-near-black);border:3px solid var(--gg-color-near-black)}
.gg-pk-btn--secondary:hover{background:var(--gg-color-near-black);color:var(--gg-color-warm-paper)}
.gg-pk-footer-back{font-family:var(--gg-font-data);font-size:12px;margin-top:16px}
.gg-pk-footer-back a{color:var(--gg-color-teal);text-decoration:underline}

/* ── Guide block overrides (copied from guide for standalone page) ── */

/* Timeline */
.gg-guide-timeline{margin:0 0 24px;padding-left:20px}
.gg-guide-timeline-title{font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:2px;margin:0 0 16px;color:var(--gg-color-primary-brown)}
.gg-guide-timeline-step{display:flex;gap:16px;margin-bottom:20px;position:relative}
.gg-guide-timeline-step:not(:last-child)::before{content:'';position:absolute;left:15px;top:32px;bottom:-20px;width:2px;background:var(--gg-color-tan)}
.gg-guide-timeline-marker{width:32px;height:32px;min-width:32px;background:var(--gg-color-teal);color:#fff;font-size:13px;font-weight:700;display:flex;align-items:center;justify-content:center;position:relative;z-index:1}
.gg-guide-timeline-content{flex:1}
.gg-guide-timeline-label{font-size:14px;font-weight:700;margin:0 0 6px;text-transform:uppercase;letter-spacing:1px;color:var(--gg-color-near-black)}
.gg-guide-timeline-content p{font-family:var(--gg-font-editorial);font-size:13px;line-height:1.6;margin:0;color:var(--gg-color-primary-brown)}

/* Accordion */
.gg-guide-accordion-item{border:2px solid var(--gg-color-near-black);margin-bottom:8px}
.gg-guide-accordion-trigger{display:flex;justify-content:space-between;align-items:center;width:100%;padding:12px 16px;background:var(--gg-color-warm-paper);border:none;cursor:pointer;font-family:var(--gg-font-data);font-size:13px;font-weight:700;text-align:left;color:var(--gg-color-near-black)}
.gg-guide-accordion-trigger:hover{background:var(--gg-color-sand)}
.gg-guide-accordion-icon{font-size:18px;font-weight:700}
.gg-guide-accordion-trigger[aria-expanded="true"] .gg-guide-accordion-icon{transform:rotate(45deg)}
.gg-guide-accordion-body{display:none;padding:16px;border-top:2px solid var(--gg-color-near-black)}
.gg-guide-accordion-trigger[aria-expanded="true"]+.gg-guide-accordion-body{display:block}

/* Process List */
.gg-guide-process-list{margin:0 0 20px}
.gg-guide-process-item{display:flex;gap:14px;margin-bottom:16px;padding:12px;border:2px solid var(--gg-color-near-black);background:var(--gg-color-warm-paper)}
.gg-guide-process-num{width:32px;height:32px;min-width:32px;background:var(--gg-color-near-black);color:#fff;font-size:14px;font-weight:700;display:flex;align-items:center;justify-content:center}
.gg-guide-process-body{flex:1}
.gg-guide-process-label{font-weight:700;font-size:14px;color:var(--gg-color-near-black)}
.gg-guide-process-pct{display:inline-block;background:var(--gg-color-gold);color:#fff;font-size:10px;font-weight:700;padding:2px 6px;margin-left:8px;letter-spacing:1px}
.gg-guide-process-detail{font-size:13px;color:var(--gg-color-primary-brown);margin:4px 0 0;line-height:1.5}

/* Callout */
.gg-guide-callout{padding:20px 24px;margin:0 0 20px;border-left:6px solid var(--gg-color-teal);background:var(--gg-color-warm-paper)}
.gg-guide-callout--quote{border-left-color:var(--gg-color-gold);font-style:italic}
.gg-guide-callout--highlight{border-left-color:var(--gg-color-gold)}
.gg-guide-callout p{font-family:var(--gg-font-editorial);font-size:13px;line-height:1.7;margin:0 0 8px;color:var(--gg-color-near-black)}
.gg-guide-callout p:last-child{margin-bottom:0}
.gg-guide-callout ul{margin:8px 0;padding-left:20px}
.gg-guide-callout li{font-family:var(--gg-font-editorial);font-size:13px;line-height:1.6;color:var(--gg-color-near-black)}

/* ── Fueling Calculator ── */
.gg-pk-calc-wrapper{margin:24px 0 0}
.gg-pk-calc-intro{font-size:13px;line-height:1.6;color:var(--gg-color-primary-brown);margin:0 0 16px}
.gg-pk-calc-form{display:grid;grid-template-columns:1fr 1fr;gap:12px 16px;margin-bottom:20px}
.gg-pk-calc-field{display:flex;flex-direction:column;gap:4px}
.gg-pk-calc-field label{font-family:var(--gg-font-data);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--gg-color-near-black)}
.gg-pk-calc-req{color:var(--gg-color-teal)}
.gg-pk-calc-input{font-family:var(--gg-font-data);font-size:13px;padding:8px 10px;border:2px solid var(--gg-color-near-black);background:var(--gg-color-white);color:var(--gg-color-near-black);width:100%;box-sizing:border-box}
.gg-pk-calc-input:focus{outline:none;border-color:var(--gg-color-teal)}
.gg-pk-calc-select{font-family:var(--gg-font-data);font-size:13px;padding:8px 10px;border:2px solid var(--gg-color-near-black);background:var(--gg-color-white);color:var(--gg-color-near-black)}
.gg-pk-calc-height-row{display:flex;gap:8px}
.gg-pk-calc-height-row select{flex:1}
.gg-pk-calc-tooltip{cursor:help;color:var(--gg-color-secondary-brown);font-size:14px}
.gg-pk-calc-btn{grid-column:1/-1;font-family:var(--gg-font-data);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:2px;padding:12px 24px;background:var(--gg-color-primary-brown);color:var(--gg-color-warm-paper);border:3px solid var(--gg-color-near-black);cursor:pointer;transition:background 0.2s}
.gg-pk-calc-btn:hover{background:var(--gg-color-near-black)}
.gg-pk-calc-result{border-left:6px solid var(--gg-color-teal);background:var(--gg-color-warm-paper);padding:20px 24px;margin:0 0 20px}
.gg-pk-calc-result-row{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px solid var(--gg-color-tan);font-family:var(--gg-font-data);font-size:13px}
.gg-pk-calc-result-row:last-child{border-bottom:none}
.gg-pk-calc-result-label{color:var(--gg-color-primary-brown);text-transform:uppercase;letter-spacing:1px;font-size:11px}
.gg-pk-calc-result-value{font-weight:700;color:var(--gg-color-near-black)}
.gg-pk-calc-result-highlight{font-size:28px;font-weight:700;color:var(--gg-color-teal);font-family:var(--gg-font-data)}
.gg-pk-calc-result-note{font-family:var(--gg-font-editorial);font-size:12px;color:var(--gg-color-secondary-brown);margin:12px 0 0;line-height:1.5}
.gg-pk-calc-substack{margin:20px 0 0;padding:16px;border:2px solid var(--gg-color-tan);background:var(--gg-color-white)}
.gg-pk-calc-substack-label{font-family:var(--gg-font-data);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:var(--gg-color-primary-brown);margin:0 0 8px}

/* ── Climate Badge ── */
.gg-pk-calc-field--climate{grid-column:1/-1}
.gg-pk-calc-climate-badge{font-family:var(--gg-font-data);font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px;padding:10px 16px;text-align:center;border:2px solid var(--gg-color-near-black)}
.gg-pk-calc-climate--cool{background:#e8f5e9;color:#2e7d32}
.gg-pk-calc-climate--mild{background:var(--gg-color-warm-paper);color:var(--gg-color-primary-brown)}
.gg-pk-calc-climate--warm{background:#fff8e1;color:#f57f17}
.gg-pk-calc-climate--hot{background:#ffebee;color:#c62828}
.gg-pk-calc-climate--extreme{background:#2c2c2c;color:#fff}

/* ── Panel Titles ── */
.gg-pk-calc-panel-title{font-family:var(--gg-font-data);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2px;color:var(--gg-color-teal);border-bottom:2px solid var(--gg-color-teal);padding-bottom:6px;margin:24px 0 12px}

/* ── Hourly Table ── */
.gg-pk-calc-hourly-scroll{overflow-x:auto;margin:0 0 20px;-webkit-overflow-scrolling:touch}
.gg-pk-calc-hourly-table{width:100%;border-collapse:collapse;font-family:var(--gg-font-data);font-size:12px;min-width:500px}
.gg-pk-calc-hourly-table th{background:var(--gg-color-near-black);color:var(--gg-color-warm-paper);padding:8px 10px;text-align:left;text-transform:uppercase;letter-spacing:1px;font-size:10px;font-weight:700}
.gg-pk-calc-hourly-table td{padding:8px 10px;border-bottom:1px solid var(--gg-color-tan);vertical-align:top}
.gg-pk-calc-hourly-table tr:last-child td{border-bottom:2px solid var(--gg-color-near-black);font-weight:700}
.gg-pk-calc-hour-num{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;background:var(--gg-color-near-black);color:#fff;font-size:11px;font-weight:700}
.gg-pk-calc-aid-row{background:rgba(23,128,121,0.08)}
.gg-pk-calc-aid-badge{display:inline-block;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:1px;background:var(--gg-color-teal);color:#fff;padding:2px 6px;margin-left:6px;vertical-align:middle}

/* ── Fuel Chips ── */
.gg-pk-calc-item{display:inline-block;font-family:var(--gg-font-data);font-size:11px;font-weight:600;padding:3px 8px;margin:2px 4px 2px 0;border:1px solid}
.gg-pk-calc-item--gel{background:rgba(23,128,121,0.1);color:var(--gg-color-teal);border-color:var(--gg-color-teal)}
.gg-pk-calc-item--drink{background:rgba(154,126,10,0.1);color:var(--gg-color-gold);border-color:var(--gg-color-gold)}
.gg-pk-calc-item--food{background:rgba(89,71,60,0.1);color:var(--gg-color-primary-brown);border-color:var(--gg-color-primary-brown)}

/* ── Shopping List ── */
.gg-pk-calc-shopping-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:0 0 16px}
.gg-pk-calc-shopping-item{border:2px solid var(--gg-color-near-black);padding:12px 16px;background:var(--gg-color-white)}
.gg-pk-calc-shopping-qty{font-family:var(--gg-font-data);font-size:24px;font-weight:700;color:var(--gg-color-teal);display:block;margin-bottom:4px}
.gg-pk-calc-shopping-label{font-family:var(--gg-font-data);font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--gg-color-primary-brown)}
.gg-pk-calc-shopping-note{font-family:var(--gg-font-editorial);font-size:12px;color:var(--gg-color-secondary-brown);margin:8px 0 0;line-height:1.5}

/* ── Email Gate ── */
.gg-pk-gate{text-align:center;padding:48px 20px;border:3px solid var(--gg-color-near-black);background:var(--gg-color-white);margin-bottom:32px}
.gg-pk-gate-inner{max-width:440px;margin:0 auto}
.gg-pk-gate-badge{display:inline-block;font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase;background:var(--gg-color-teal);color:var(--gg-color-white);padding:4px 12px;margin-bottom:16px}
.gg-pk-gate-title{font-family:var(--gg-font-data);font-size:22px;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin:0 0 12px;color:var(--gg-color-near-black)}
.gg-pk-gate-text{font-family:var(--gg-font-editorial);font-size:14px;line-height:1.6;color:var(--gg-color-primary-brown);margin:0 0 20px}
.gg-pk-gate-form{display:flex;gap:0;max-width:400px;margin:0 auto 12px}
.gg-pk-gate-input{flex:1;font-family:var(--gg-font-data);font-size:13px;padding:12px 14px;border:3px solid var(--gg-color-near-black);border-right:none;background:var(--gg-color-warm-paper);color:var(--gg-color-near-black);min-width:0}
.gg-pk-gate-input:focus{outline:none;border-color:var(--gg-color-teal)}
.gg-pk-gate-btn{font-family:var(--gg-font-data);font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2px;padding:12px 20px;background:var(--gg-color-near-black);color:var(--gg-color-warm-paper);border:3px solid var(--gg-color-near-black);cursor:pointer;white-space:nowrap;transition:background 0.2s}
.gg-pk-gate-btn:hover{background:var(--gg-color-teal);border-color:var(--gg-color-teal)}
.gg-pk-gate-fine{font-family:var(--gg-font-data);font-size:11px;color:var(--gg-color-secondary-brown);letter-spacing:1px;margin:0}
.gg-pk-gate-preview{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:0 0 24px;text-align:left}
.gg-pk-gate-preview-item{display:flex;align-items:center;gap:10px;padding:8px 12px;background:var(--gg-color-sand);border-left:3px solid var(--gg-color-teal)}
.gg-pk-gate-preview-num{font-family:var(--gg-font-data);font-size:11px;font-weight:700;color:var(--gg-color-teal);letter-spacing:1px;min-width:20px}
.gg-pk-gate-preview-label{font-family:var(--gg-font-data);font-size:11px;letter-spacing:0.5px;color:var(--gg-color-near-black)}
@media (max-width:600px){.gg-pk-gate-form{flex-direction:column;gap:8px}.gg-pk-gate-input{border-right:3px solid var(--gg-color-near-black)}.gg-pk-gate{padding:32px 16px}.gg-pk-gate-preview{grid-template-columns:1fr}}

/* ── Print Styles ── */
@media print{
  body{background:#fff !important}
  .gg-pk-page{max-width:100%;padding:0;margin:0}
  .gg-pk-header{padding:16px 0;border-bottom:2px solid #000}
  .gg-pk-header-badge{background:#000;color:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .gg-pk-section{page-break-inside:avoid}
  .gg-pk-footer{display:none}
  .gg-mega-footer{display:none}
  .gg-guide-accordion-body{display:block !important}
  .gg-guide-accordion-trigger{pointer-events:none}
  .gg-guide-accordion-icon{display:none}
  .gg-guide-timeline-marker,.gg-guide-process-num,.gg-pk-nn-badge,.gg-pk-milestone-badge,.gg-pk-workout-mod{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  a[href]:after{content:none !important}
  .gg-pk-calc-form{display:none}
  .gg-pk-calc-substack{display:none}
  .gg-pk-calc-intro{display:none}
  .gg-pk-calc-result[style*="block"]{display:block !important}
  .gg-pk-calc-hourly-scroll{overflow:visible}
  .gg-pk-calc-hourly-table{min-width:0}
  .gg-pk-calc-shopping-grid{grid-template-columns:repeat(4,1fr)}
  .gg-pk-calc-hour-num,.gg-pk-calc-aid-badge,.gg-pk-calc-item{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}

/* ── Responsive ── */
@media (max-width:600px){
  .gg-pk-header-title{font-size:24px}
  .gg-pk-vitals-ribbon{flex-direction:column;align-items:center;gap:6px}
  .gg-pk-footer-buttons{flex-direction:column;align-items:center}
  .gg-pk-btn{width:100%;max-width:300px}
  .gg-pk-calc-form{grid-template-columns:1fr}
  .gg-pk-calc-shopping-grid{grid-template-columns:1fr}
  .gg-pk-calc-hourly-table{min-width:500px}
}
""" + get_mega_footer_css()


# ── Page Assembly ─────────────────────────────────────────────


def build_prep_kit_js() -> str:
    """JS for email gate, accordion toggle, and fueling calculator on prep kit pages."""
    return """/* ── Email Gate ── */
(function(){
  var WORKER_URL='""" + FUELING_WORKER_URL + """';
  var LS_KEY='gg-pk-fueling';
  var EXPIRY_DAYS=90;
  var gate=document.getElementById('gg-pk-gate');
  var content=document.getElementById('gg-pk-gated-content');
  var gateForm=document.getElementById('gg-pk-gate-form');
  if(!gate||!content) return;

  function unlockContent(email){
    gate.style.display='none';
    content.style.display='block';
    /* Pre-fill fueling calculator email if present */
    var calcEmail=document.getElementById('gg-pk-email');
    if(calcEmail&&email) calcEmail.value=email;
  }

  /* Check localStorage for cached email */
  try{
    var cached=JSON.parse(localStorage.getItem(LS_KEY)||'null');
    if(cached&&cached.email&&cached.exp>Date.now()){
      unlockContent(cached.email);
      return;
    }
  }catch(e){}

  /* Handle gate form submit */
  if(gateForm){
    gateForm.addEventListener('submit',function(e){
      e.preventDefault();
      var email=gateForm.email.value.trim();
      if(!email||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)){
        alert('Please enter a valid email address.');return;
      }
      /* Honeypot check */
      if(gateForm.website&&gateForm.website.value){return;}
      /* Cache email */
      try{
        localStorage.setItem(LS_KEY,JSON.stringify({email:email,exp:Date.now()+EXPIRY_DAYS*86400000}));
      }catch(ex){}
      /* Fire-and-forget POST to Worker */
      var payload={
        email:email,
        race_slug:gateForm.race_slug.value,
        race_name:gateForm.race_name.value,
        source:'prep_kit_gate',
        website:gateForm.website.value
      };
      fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(function(){});
      /* GA4 event */
      if(typeof gtag==='function'){
        gtag('event','pk_gate_unlock',{race_slug:gateForm.race_slug.value});
      }
      unlockContent(email);
    });
  }
})();

document.querySelectorAll('.gg-guide-accordion-trigger').forEach(function(btn){
  btn.addEventListener('click',function(){
    var expanded=this.getAttribute('aria-expanded')==='true';
    this.setAttribute('aria-expanded',String(!expanded));
  });
});
/* ── Fueling Calculator ── */
(function(){
  var WORKER_URL='""" + FUELING_WORKER_URL + """';
  var LS_KEY='gg-pk-fueling';
  var EXPIRY_DAYS=90;
  var form=document.getElementById('gg-pk-calc-form');
  if(!form) return;

  /* Restore cached email */
  try{
    var cached=JSON.parse(localStorage.getItem(LS_KEY)||'null');
    if(cached&&cached.email&&cached.exp>Date.now()){
      var ef=document.getElementById('gg-pk-email');
      if(ef) ef.value=cached.email;
    }
  }catch(e){}

  /* Multiplier constants — must match Python parity */
  var HEAT_MULT={cool:0.7,mild:1.0,warm:1.3,hot:1.6,extreme:1.9};
  var SWEAT_MULT={light:0.7,moderate:1.0,heavy:1.3};
  var FORMAT_SPLITS={
    liquid:{drink:0.80,gel:0.15,food:0.05},
    gels:{drink:0.20,gel:0.70,food:0.10},
    mixed:{drink:0.30,gel:0.40,food:0.30},
    solid:{drink:0.20,gel:0.20,food:0.60}
  };
  var SODIUM_BASE=1000;
  var SODIUM_HEAT_BOOST={hot:200,extreme:300};
  var SODIUM_CRAMP_BOOST={sometimes:150,frequent:300};

  function computePersonalized(weightLbs,ftp,hours){
    if(!weightLbs||weightLbs<=0||!hours||hours<=0) return null;
    var weightKg=weightLbs*0.453592;
    var bLo,bHi,bracket;
    if(hours<=4){bLo=80;bHi=100;bracket='High-intensity race pace';}
    else if(hours<=8){bLo=60;bHi=80;bracket='Endurance pace';}
    else if(hours<=12){bLo=50;bHi=70;bracket='Lower intensity';}
    else if(hours<=16){bLo=40;bHi=60;bracket='Ultra pace';}
    else{bLo=30;bHi=50;bracket='Survival pace';}
    var rawRate,note;
    if(ftp&&ftp>0){
      rawRate=weightKg*0.7*(ftp/100)*0.7;
      note='Personalized from your weight and FTP';
    }else{
      rawRate=(bLo+bHi)/2;
      note='Enter your FTP for a more precise estimate';
    }
    var rate=Math.max(bLo,Math.min(bHi,Math.round(rawRate)));
    var totalCarbs=Math.round(rate*hours);
    var gels=Math.floor(totalCarbs/25);
    return{rate:rate,totalCarbs:totalCarbs,gels:gels,bracket:bracket,bracketLo:bLo,bracketHi:bHi,note:note};
  }

  function computeSweatRate(weightLbs,climateHeat,sweatTendency,hours){
    if(!weightLbs||weightLbs<=0||!hours||hours<=0) return null;
    var weightKg=weightLbs*0.453592;
    var base=weightKg*0.013;
    var hm=HEAT_MULT[climateHeat]||1.0;
    var sm=SWEAT_MULT[sweatTendency]||1.0;
    var intensity;
    if(hours<=4) intensity=1.15;
    else if(hours<=8) intensity=1.0;
    else if(hours<=12) intensity=0.9;
    else if(hours<=16) intensity=0.8;
    else intensity=0.7;
    var sr=base*hm*sm*intensity;
    var fLo=Math.round(sr*0.6*1000);
    var fHi=Math.round(sr*0.8*1000);
    return{sweatRate:Math.round(sr*100)/100,fluidLoMl:fLo,fluidHiMl:fHi,fluidLoOz:Math.round(fLo/29.5735),fluidHiOz:Math.round(fHi/29.5735)};
  }

  function computeSodium(sweatRate,climateHeat,crampHistory){
    if(!sweatRate||sweatRate<=0) return null;
    var conc=SODIUM_BASE+(SODIUM_HEAT_BOOST[climateHeat]||0)+(SODIUM_CRAMP_BOOST[crampHistory]||0);
    return{sodiumMgHr:Math.round(sweatRate*conc),concentration:conc};
  }

  function computeHourlyPlan(hours,carbRate,fluidMlHr,sodiumMgHr,fuelFormat,aidHours){
    if(!hours||hours<=0||!carbRate||carbRate<=0) return[];
    var total=Math.ceil(hours);
    var splits=FORMAT_SPLITS[fuelFormat]||FORMAT_SPLITS.mixed;
    var aidSet={};
    (aidHours||[]).forEach(function(h){aidSet[Math.round(h)]=true;});
    var plan=[];
    for(var h=1;h<=total;h++){
      var mult;
      if(h===1) mult=0.8;
      else if(h===total&&hours%1>0) mult=hours%1;
      else if(h===total) mult=0.8;
      else mult=1.0;
      var hCarbs=Math.round(carbRate*mult);
      var hFluid=Math.round(fluidMlHr*mult);
      var hSodium=Math.round(sodiumMgHr*mult);
      var dCarbs=Math.round(hCarbs*splits.drink);
      var gCarbs=Math.round(hCarbs*splits.gel);
      var fCarbs=hCarbs-dCarbs-gCarbs;
      var items=[];
      if(gCarbs>0){var gc=Math.max(1,Math.round(gCarbs/25));items.push({type:'gel',label:gc+' gel'+(gc>1?'s':'')+' ('+(gc*25)+'g)'});}
      if(dCarbs>0){var dm=Math.round(dCarbs/40*500);items.push({type:'drink',label:dm+'ml mix ('+dCarbs+'g)'});}
      if(fCarbs>0){var bc=Math.max(1,Math.round(fCarbs/35));items.push({type:'food',label:bc+' bar'+(bc>1?'s':'')+' ('+(bc*35)+'g)'});}
      plan.push({hour:h,carbs:hCarbs,fluid:hFluid,sodium:hSodium,items:items,isAid:!!aidSet[h]});
    }
    return plan;
  }

  function renderResults(r,hydration,sodium,plan,hours){
    var panel=document.getElementById('gg-pk-calc-result');
    if(!panel) return;
    var html='';

    /* Panel 1: YOUR RACE NUMBERS */
    html+='<div class="gg-pk-calc-panel-title">Your Race Numbers</div>';
    html+='<div class="gg-pk-calc-result-row"><span class="gg-pk-calc-result-label">Carb Target</span>'+
      '<span class="gg-pk-calc-result-highlight">'+r.rate+'g/hr</span></div>';
    html+='<div class="gg-pk-calc-result-row"><span class="gg-pk-calc-result-label">Total Carbs</span>'+
      '<span class="gg-pk-calc-result-value">'+r.totalCarbs.toLocaleString()+'g</span></div>';
    if(hydration){
      html+='<div class="gg-pk-calc-result-row"><span class="gg-pk-calc-result-label">Fluid Target</span>'+
        '<span class="gg-pk-calc-result-highlight">'+hydration.fluidLoOz+'-'+hydration.fluidHiOz+' oz/hr</span></div>';
      var totalFluidL=Math.round(hydration.fluidHiMl*hours/1000*10)/10;
      html+='<div class="gg-pk-calc-result-row"><span class="gg-pk-calc-result-label">Total Fluid</span>'+
        '<span class="gg-pk-calc-result-value">~'+totalFluidL+'L</span></div>';
    }
    if(sodium){
      html+='<div class="gg-pk-calc-result-row"><span class="gg-pk-calc-result-label">Sodium Target</span>'+
        '<span class="gg-pk-calc-result-value">'+sodium.sodiumMgHr+' mg/hr</span></div>';
      var totalSodium=Math.round(sodium.sodiumMgHr*hours);
      var saltCaps=Math.ceil(totalSodium/250);
      html+='<div class="gg-pk-calc-result-row"><span class="gg-pk-calc-result-label">Salt Capsules</span>'+
        '<span class="gg-pk-calc-result-value">~'+saltCaps+' (250mg each)</span></div>';
    }
    html+='<div class="gg-pk-calc-result-row"><span class="gg-pk-calc-result-label">Duration Bracket</span>'+
      '<span class="gg-pk-calc-result-value">'+r.bracket+' ('+r.bracketLo+'-'+r.bracketHi+'g/hr)</span></div>';
    html+='<p class="gg-pk-calc-result-note">'+r.note+'. Carb targets clamped to exercise physiology brackets (Jeukendrup 2014). Start low in training and build toward race-day targets.</p>';

    /* Panel 2: HOUR-BY-HOUR RACE PLAN */
    if(plan&&plan.length>0){
      html+='<div class="gg-pk-calc-panel-title">Hour-by-Hour Race Plan</div>';
      html+='<div class="gg-pk-calc-hourly-scroll"><table class="gg-pk-calc-hourly-table">';
      html+='<thead><tr><th>Hour</th><th>Carbs</th><th>Fluid</th><th>Sodium</th><th>What to Consume</th></tr></thead><tbody>';
      var tC=0,tF=0,tS=0;
      plan.forEach(function(p){
        tC+=p.carbs;tF+=p.fluid;tS+=p.sodium;
        var cls=p.isAid?' class="gg-pk-calc-aid-row"':'';
        var itemsHtml=p.items.map(function(it){return'<span class="gg-pk-calc-item gg-pk-calc-item--'+it.type+'">'+it.label+'</span>';}).join(' ');
        var aidBadge=p.isAid?'<span class="gg-pk-calc-aid-badge">Aid Station</span>':'';
        html+='<tr'+cls+'><td><span class="gg-pk-calc-hour-num">'+p.hour+'</span></td>';
        html+='<td>'+p.carbs+'g</td><td>'+p.fluid+'ml</td><td>'+p.sodium+'mg</td>';
        html+='<td>'+itemsHtml+aidBadge+'</td></tr>';
      });
      html+='<tr><td><strong>Total</strong></td><td><strong>'+tC+'g</strong></td>';
      html+='<td><strong>'+Math.round(tF/1000*10)/10+'L</strong></td>';
      html+='<td><strong>'+Math.round(tS/1000*10)/10+'g</strong></td><td></td></tr>';
      html+='</tbody></table></div>';
    }

    /* Panel 3: WHAT TO PACK */
    if(plan&&plan.length>0){
      html+='<div class="gg-pk-calc-panel-title">What to Pack</div>';
      var totGels=0,totDrinkMl=0,totBars=0,totSaltCaps=0;
      plan.forEach(function(p){
        p.items.forEach(function(it){
          var m=it.label.match(/^(\\d+)/);
          var n=m?parseInt(m[1]):1;
          if(it.type==='gel') totGels+=n;
          else if(it.type==='drink'){var mm=it.label.match(/(\\d+)ml/);if(mm) totDrinkMl+=parseInt(mm[1]);}
          else if(it.type==='food') totBars+=n;
        });
      });
      if(sodium){totSaltCaps=Math.ceil(sodium.sodiumMgHr*hours/250);}
      html+='<div class="gg-pk-calc-shopping-grid">';
      if(totGels>0) html+='<div class="gg-pk-calc-shopping-item"><span class="gg-pk-calc-shopping-qty">'+totGels+'</span><span class="gg-pk-calc-shopping-label">Gels (25g each)</span></div>';
      if(totDrinkMl>0) html+='<div class="gg-pk-calc-shopping-item"><span class="gg-pk-calc-shopping-qty">'+Math.round(totDrinkMl/1000*10)/10+'L</span><span class="gg-pk-calc-shopping-label">Drink mix</span></div>';
      if(totSaltCaps>0) html+='<div class="gg-pk-calc-shopping-item"><span class="gg-pk-calc-shopping-qty">'+totSaltCaps+'</span><span class="gg-pk-calc-shopping-label">Salt caps (250mg)</span></div>';
      if(totBars>0) html+='<div class="gg-pk-calc-shopping-item"><span class="gg-pk-calc-shopping-qty">'+totBars+'</span><span class="gg-pk-calc-shopping-label">Bars / rice cakes</span></div>';
      html+='</div>';
      html+='<p class="gg-pk-calc-shopping-note">Pack 10-15% extra for spills and bonking insurance.</p>';
    }

    panel.innerHTML=html;
    panel.style.display='block';
  }

  form.addEventListener('submit',function(e){
    e.preventDefault();
    var email=form.email.value.trim();
    var weightLbs=parseFloat(form.weight_lbs.value);
    var ftp=form.ftp.value?parseFloat(form.ftp.value):null;
    var hours=parseFloat(form.target_hours.value)||parseFloat(form.est_hours.value)||0;
    var climateHeat=form.climate_heat.value||'mild';
    var sweatTendency=form.sweat_tendency.value||'moderate';
    var fuelFormat=form.fuel_format.value||'mixed';
    var crampHistory=form.cramp_history.value||'rarely';
    var aidHours=[];
    try{aidHours=JSON.parse(form.aid_station_hours.value||'[]');}catch(ex){}
    if(!email||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)){
      alert('Please enter a valid email address.');return;
    }
    if(!weightLbs||weightLbs<80){
      alert('Please enter your weight in lbs.');return;
    }
    if(!hours||hours<=0) hours=6;
    var result=computePersonalized(weightLbs,ftp,hours);
    if(!result){alert('Could not compute — check your inputs.');return;}
    var hydration=computeSweatRate(weightLbs,climateHeat,sweatTendency,hours);
    var sodium=hydration?computeSodium(hydration.sweatRate,climateHeat,crampHistory):null;
    var fluidMlHr=hydration?Math.round((hydration.fluidLoMl+hydration.fluidHiMl)/2):750;
    var sodiumMgHr=sodium?sodium.sodiumMgHr:1000;
    var plan=computeHourlyPlan(hours,result.rate,fluidMlHr,sodiumMgHr,fuelFormat,aidHours);
    renderResults(result,hydration,sodium,plan,hours);
    /* Show Substack iframe */
    var ss=document.getElementById('gg-pk-calc-substack');
    if(ss) ss.style.display='block';
    /* Cache email in localStorage */
    try{
      localStorage.setItem(LS_KEY,JSON.stringify({email:email,exp:Date.now()+EXPIRY_DAYS*86400000}));
    }catch(e){}
    /* Fire-and-forget POST to Worker */
    var payload={
      email:email,weight_lbs:weightLbs,race_slug:form.race_slug.value,
      race_name:form.race_name.value,
      height_ft:form.height_ft?form.height_ft.value:'',
      height_in:form.height_in?form.height_in.value:'',
      age:form.age?form.age.value:'',ftp:ftp,target_hours:hours,
      personalized_rate:result.rate,total_carbs:result.totalCarbs,
      fluid_target_ml_hr:fluidMlHr,sodium_mg_hr:sodiumMgHr,
      sweat_tendency:sweatTendency,fuel_format:fuelFormat,
      cramp_history:crampHistory,climate_heat:climateHeat,
      website:form.website.value
    };
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(function(){});
    /* GA4 event */
    if(typeof gtag==='function'){
      gtag('event','pk_fueling_submit',{race_slug:form.race_slug.value,has_ftp:ftp?'yes':'no',climate:climateHeat});
    }
  });
})();"""


def build_pk_email_gate(rd: dict) -> str:
    """Build email gate overlay that blocks content until email is provided.

    Shows section title previews with blur to give users a reason to unlock.
    """
    name = esc(rd["name"])
    slug = esc(rd["slug"])
    # Section titles users can see through the gate (teaser)
    preview_sections = [
        ("01", "12-Week Training Timeline"),
        ("02", "Non-Negotiables Checklist"),
        ("03", "Race Week Protocol"),
        ("04", "Equipment & Packing List"),
        ("05", "Race Morning Routine"),
        ("06", "Personalized Fueling Calculator"),
        ("07", "In-Race Decision Tree"),
        ("08", "Recovery Protocol"),
    ]
    preview_html = "".join(
        f'<div class="gg-pk-gate-preview-item">'
        f'<span class="gg-pk-gate-preview-num">{num}</span>'
        f'<span class="gg-pk-gate-preview-label">{label}</span>'
        f'</div>'
        for num, label in preview_sections
    )
    return f'''<div class="gg-pk-gate" id="gg-pk-gate">
    <div class="gg-pk-gate-inner">
      <div class="gg-pk-gate-badge">FREE DOWNLOAD</div>
      <h2 class="gg-pk-gate-title">Unlock Your {name} Prep Kit</h2>
      <p class="gg-pk-gate-text">12-week training timeline, race-day checklists, packing list, and a personalized fueling calculator — free, instant access.</p>
      <div class="gg-pk-gate-preview">{preview_html}</div>
      <form class="gg-pk-gate-form" id="gg-pk-gate-form" autocomplete="off">
        <input type="hidden" name="race_slug" value="{slug}">
        <input type="hidden" name="race_name" value="{name}">
        <input type="hidden" name="website" value="">
        <input type="email" id="gg-pk-gate-email" name="email" required placeholder="your@email.com" class="gg-pk-gate-input" aria-label="Email address">
        <button type="submit" class="gg-pk-gate-btn">UNLOCK PREP KIT</button>
      </form>
      <p class="gg-pk-gate-fine">No spam. Unsubscribe anytime.</p>
    </div>
  </div>'''


def build_howto_schema(name: str, slug: str, canonical: str, has_full: bool) -> str:
    """Build HowTo + BreadcrumbList JSON-LD schema for prep kit pages."""
    steps = [
        {"name": "12-Week Training Timeline", "text": "Follow a periodized Base/Build/Peak/Taper training plan calibrated to your race distance and terrain."},
        {"name": "Race Week Countdown", "text": "Execute a 7-day taper protocol: reduce volume, lock in nutrition, and finalize logistics."},
        {"name": "Equipment & Packing Checklist", "text": "Assemble race-day gear including bike setup, nutrition, repair kit, and clothing for expected conditions."},
        {"name": "Race Morning Protocol", "text": "Follow a timed pre-race morning routine from alarm to start line: eat, hydrate, warm up, check gear."},
        {"name": "Race-Day Fueling", "text": "Execute your carb-per-hour fueling plan with gut-trained nutrition strategy and aid station planning."},
        {"name": "In-Race Decision Tree", "text": "Handle race-day problems — bonking, cramping, mechanicals, weather — with pre-planned decision frameworks."},
        {"name": "Post-Race Recovery", "text": "Follow immediate and multi-day recovery protocols to minimize damage and return to training safely."},
    ]
    if has_full:
        steps.insert(1, {"name": "Race-Specific Non-Negotiables", "text": "Complete must-do training milestones specific to this race before race day."})

    howto_steps = []
    for i, step in enumerate(steps, 1):
        howto_steps.append({
            "@type": "HowToStep",
            "position": i,
            "name": step["name"],
            "text": step["text"],
        })

    schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_BASE_URL}/"},
                    {"@type": "ListItem", "position": 2, "name": "Gravel Races", "item": f"{SITE_BASE_URL}/gravel-races/"},
                    {"@type": "ListItem", "position": 3, "name": name, "item": f"{SITE_BASE_URL}/race/{slug}/"},
                    {"@type": "ListItem", "position": 4, "name": "Prep Kit", "item": canonical},
                ],
            },
            {
                "@type": "HowTo",
                "name": f"How to Prepare for {name}",
                "description": f"Free 12-week race prep kit for {name}: training timeline, checklists, fueling calculator, and race-day strategy.",
                "totalTime": "P84D",
                "step": howto_steps,
            },
        ],
    }
    return json.dumps(schema, ensure_ascii=False, indent=2)


def generate_prep_kit_page(rd: dict, raw: dict, guide_sections: dict) -> str:
    """Assemble the complete prep kit HTML page."""
    slug = rd["slug"]
    name = rd["name"]
    canonical = f"{SITE_BASE_URL}/race/{slug}/prep-kit/"

    header = build_pk_header(rd, raw)
    gate = build_pk_email_gate(rd)

    gated_sections = [
        build_pk_training_timeline(guide_sections, raw, rd),
        build_pk_non_negotiables(raw),
        build_pk_race_week(guide_sections, raw),
        build_pk_equipment(guide_sections, raw, rd),
        build_pk_race_morning(guide_sections, rd),
        build_pk_fueling(guide_sections, raw, rd),
        build_pk_decision_tree(guide_sections, rd),
        build_pk_recovery(guide_sections),
        build_pk_footer_cta(rd),
    ]

    gated_body = "\n".join(s for s in gated_sections if s)

    # Renumber sections sequentially (handles generic races skipping Section 02)
    counter = [0]
    def _renumber(m):
        counter[0] += 1
        return f'<span class="gg-pk-section-num">{counter[0]:02d}</span>'
    gated_body = re.sub(
        r'<span class="gg-pk-section-num">\d{2}</span>', _renumber, gated_body
    )

    mega_footer = get_mega_footer_html()
    body = f'''{header}
{gate}
<div class="gg-pk-gated-content" id="gg-pk-gated-content" style="display:none">
{gated_body}
</div>
{mega_footer}'''

    tokens_css = get_tokens_css()
    font_css = get_font_face_css("/race/assets/fonts")
    preload = get_preload_hints("/race/assets/fonts")
    pk_css = build_prep_kit_css()
    js = build_prep_kit_js()

    meta_desc = f"Free race prep kit for {name}: 12-week training timeline, race-day checklists, packing list, and fueling strategy."
    title = f"Free {name} Prep Kit: 12-Week Plan, Checklists & Fueling | Gravel God"
    has_full = has_full_training_data(raw)
    schema_jsonld = build_howto_schema(name, slug, canonical, has_full)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(meta_desc)}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Gravel God">
  <script type="application/ld+json">
  {schema_jsonld}
  </script>
  {preload}
  <style>
{font_css}
{tokens_css}
{pk_css}
  </style>
  <!-- GA4 -->
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
</head>
<body>
<div class="gg-pk-page">
{body}
</div>
<script>
{js}
</script>
</body>
</html>'''


# ── CLI ───────────────────────────────────────────────────────


def generate_single(slug: str, data_dirs: list, output_dir: Path,
                    guide_sections: dict) -> bool:
    """Generate prep kit for a single race. Returns True on success."""
    filepath = find_data_file(slug, data_dirs)
    if not filepath:
        print(f"  SKIP  {slug} — data file not found")
        return False

    rd = load_race_data(filepath)
    raw = load_raw_training_data(filepath)
    page_html = generate_prep_kit_page(rd, raw, guide_sections)

    out_file = output_dir / f"{slug}.html"
    out_file.write_text(page_html, encoding="utf-8")
    tier = "full" if has_full_training_data(raw) else "generic"
    print(f"  OK    {slug} ({tier})")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Generate Race Prep Kit pages for gravel race profiles."
    )
    parser.add_argument("slug", nargs="?", help="Race slug (e.g., unbound-200)")
    parser.add_argument("--all", action="store_true", help="Generate for all races")
    parser.add_argument("--data-dir", help="Primary data directory")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("Provide a race slug or use --all")

    project_root = Path(__file__).parent.parent
    data_dirs = []
    if args.data_dir:
        data_dirs.append(Path(args.data_dir))
    data_dirs.append(project_root / "race-data")

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load guide content once
    guide_sections = load_guide_sections()
    print(f"Loaded {len(guide_sections)} guide sections")

    if args.all:
        primary = None
        for d in data_dirs:
            d = Path(d)
            if d.exists() and list(d.glob("*.json")):
                primary = d
                break
        if not primary:
            print("ERROR: No race data directory found")
            return 1

        json_files = sorted(primary.glob("*.json"))
        ok_count = 0
        fail_count = 0
        full_count = 0
        generic_count = 0

        for jf in json_files:
            slug = jf.stem
            filepath = find_data_file(slug, data_dirs)
            if not filepath:
                fail_count += 1
                continue
            try:
                rd = load_race_data(filepath)
                raw = load_raw_training_data(filepath)
                page_html = generate_prep_kit_page(rd, raw, guide_sections)
                out_file = output_dir / f"{slug}.html"
                out_file.write_text(page_html, encoding="utf-8")
                ok_count += 1
                if has_full_training_data(raw):
                    full_count += 1
                else:
                    generic_count += 1
            except Exception as e:
                print(f"  FAIL  {slug}: {e}")
                fail_count += 1

        print(f"\nGenerated {ok_count} prep kits ({full_count} full, {generic_count} generic)")
        if fail_count:
            print(f"Failed: {fail_count}")
        return 1 if fail_count else 0

    else:
        success = generate_single(args.slug, data_dirs, output_dir, guide_sections)
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
