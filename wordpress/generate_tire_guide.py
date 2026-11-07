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
from season import season_year
from cookie_consent import get_consent_banner_html

# ── Constants ──────────────────────────────────────────────────

TIRE_DIR = Path(__file__).parent.parent / "data" / "tires"
WEATHER_DIR = Path(__file__).parent.parent / "data" / "weather"
OUTPUT_DIR = Path(__file__).parent / "output" / "tires"
SEASON_YEAR = str(season_year())

# Negation phrases — catch "no mud", "without mud", "minimal mud", "little to no mud"
# Longer phrases listed first so regex alternation matches them before shorter "no".
NEGATION_PATTERN = re.compile(
    r'\b(?:little\s+to\s+no|no\s+significant|absent\s+of|without|minimal|no)\s+(\w+)',
    re.IGNORECASE,
)

# Course-text signals, matched on word boundaries. A bare substring test read
# "rain" inside "terrain" (nearly every race came out wet) and "bog" inside
# "sandy sections bog down wheels" (a sand race came out muddy).
MUD_TERMS = re.compile(r"\b(?:mud|muddy|mudd\w+|boggy|bogs|peanut[- ]butter)\b")
CLAY_TERMS = re.compile(r"\bclay\b")
WET_TERMS = re.compile(
    r"\b(?:wet|rain|rainy|rains|raining|rainfall|puddles?|standing water)\b")
PUNCTURE_TERMS = re.compile(
    r"\b(?:limestone|flint|sharp|rocky(?!\s+mountain)|chunk\w*|shred\w*"
    r"|angular|abrasive)\b")
SINGLETRACK_TERMS = re.compile(
    r"\b(?:singletrack|single-track|switchbacks?|technical descents?|roots"
    r"|rock gardens?)\b")

# A hedge near a mention makes it a maybe, not the course: "occasional
# sand/mud", "mud when wet", "spring mud potential", "creek crossings in wet
# years". Hedges count within HEDGE_WINDOW words either side, same clause.
HEDGE_WORDS = frozenset({
    "occasional", "occasionally", "some", "sometimes", "potential",
    "potentially", "possible", "possibly", "may", "might", "can", "could",
    "if", "when", "after", "risk", "chance", "rare", "rarely", "years",
    "spots", "patches", "isolated", "forecast", "following",
})
NEGATION_WORDS = frozenset({"no", "not", "unlike", "without", "minimal", "zero",
                            "never", "absent"})
HEDGE_WINDOW = 5
CLAUSE_SPLIT = re.compile(r"[.;!?|—]")
WORD = re.compile(r"[a-z0-9'-]+")

# Surface demand categories
SURFACE_FAST = "fast"
SURFACE_MIXED = "mixed"
SURFACE_TECHNICAL = "technical"
SURFACE_MUDDY = "muddy"
SURFACE_WET = "wet"

# ── Course Cost (lower wins) ─────────────────────────────────
# Every candidate gets a cost in watts: its measured rolling resistance at the
# pick width (BRR drum, data/tires/lab/) plus a watt price on whatever this
# course punishes. "We'll pay 3 W for 20 more puncture points on flint" is the
# kind of trade a fast rider makes on purpose; these constants make it
# explicit. Only tires with a BRR test at a race width are candidates.

# Puncture: watts per point below PUNCTURE_REF (BRR tread puncture score).
PUNCTURE_REF = 56
PUNCTURE_W_SHARP = 0.2      # sharp rock in the course text: 20 pts = 4 W
PUNCTURE_W_LONG = 0.12      # 100+ miles: a flat costs more than a watt
PUNCTURE_W_BASE = 0.08      # any gravel race: 20 pts = 1.6 W

# Wet grip: watts per point below WET_REF (BRR wet grip, hard surface).
WET_REF = 85
WET_W = 0.08                # 30 pts = 2.4 W, only when the course is wet

# Shoulder knobs for loose corners: watts per mm below KNOB_EDGE_REF.
KNOB_EDGE_REF = 3.0
KNOB_EDGE_W_ROUGH = 1.5     # tech rating 3
KNOB_EDGE_W_TECH = 2.5      # tech rating 4+, or singletrack in the text

# Center knobs for mud: watts per mm below MUD_KNOB_REF.
MUD_KNOB_REF = 2.5
MUD_KNOB_W = 3.0            # mud is the course
MUD_KNOB_W_RISK = 1.5       # mud is a maybe ("occasional mud", clay)

# Width below the course target, per mm (rough gravel rewards volume).
WIDTH_SHORT_W = 0.4
# Pick width has no BRR test of its own; the nearest tested width stands in.
UNTESTED_WIDTH_W = 1.0

# Distance threshold for "needs comfort" flag.
# 100 miles is standard ultra-distance cutoff (Unbound 200, Almanzo 100).
COMFORT_DISTANCE_MI = 100

# Precipitation threshold for the "needs wet" grip weighting (share of
# race-month days with any rain). Never sets the surface category.
PRECIP_WET_THRESHOLD = 40

# ── Width Targets ────────────────────────────────────────────
# What 2026 gravel races are won on: 45-50mm (Unbound 2026 XL won on a 50mm
# G-One RX Pro; Unbound 2025 on a 50mm front / 45mm rear). On BRR's drum a
# 50mm tire at its lower test pressure rolls within ~3 W of the 40mm version
# of the same model, and often faster; on rough ground the volume wins.
WIDTH_TARGETS = {1: 40, 2: 45, 3: 50, 4: 50}

# ── Pressure Model ───────────────────────────────────────────
# Front psi = PRESSURE_A[category] * (system_lb / 180) ** PRESSURE_WEIGHT_EXP
#             * exp(PRESSURE_W1 * ln(w/45) + PRESSURE_W2 * ln(w/45) ** 2)
# rear = front * PRESSURE_REAR. Category is SILCA's gravel scale (1 smooth
# hardpack .. 4 rough), from the tech rating. Fitted by least squares to
# SILCA's public calculator (gravel 47/53 weight split, high-performance
# tubeless casing, 17.5 mph) for 130-230 lb riders, 38-53mm tires: within
# 0.5 psi everywhere. tests/test_tire_pressure_model.py holds the check points.
PRESSURE_A = {1: 33.46, 2: 30.46, 3: 27.13, 4: 24.92}
PRESSURE_WEIGHT_EXP = 0.2069
PRESSURE_W1 = -1.7609
PRESSURE_W2 = -0.6952
PRESSURE_REAR = 1.0461
BIKE_AND_KIT_LB = 25
RIDER_WEIGHTS_LB = (130, 150, 170, 190, 210, 230)

# ── Setup sources ────────────────────────────────────────────
# Sealant per 700c tire, Stan's Original / Race Day chart (fetched 2026-11-06).
STANS_SEALANT_URL = "https://stans.com/pages/how-much-sealant"
STANS_SEALANT_ML = {40: 60, 45: 80, 50: 95}
# Both Stan's and Schwalbe: sealant stays active 2-7 months.
SCHWALBE_TUBELESS_URL = "https://www.schwalbe.com/en/technology-faq/tubeless/"
# Gravel inserts listed on the makers' own pages: (name, url, grams, widths).
INSERTS = (
    ("Vittoria Air-Liner Light Gravel", "https://vittoria.com/products/air-liner-light-gravel",
     45, (42, 50)),
    ("Tannus Armour Tubeless", "https://tannus.com/products/armour-tubeless",
     150, (33, 47)),
)
LONG_RACE_MI = 150

# BRR tread puncture score worth naming as a reason.
PUNCTURE_MODERATE_PTS = 40

# Fast-rolling threshold for why lines (W, BRR low pressure). About the
# fastest third of the gravel tires BRR has tested.
CRR_FAST_THRESHOLD = 17.0


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
    if tech_rating is None:
        # Explicit null means the organizer has not published enough course
        # detail to score technicality. Keep downstream matching robust with
        # the same neutral internal default used for a missing rating.
        tech_rating = 2
    surface_val = terrain.get("surface", "")
    if isinstance(surface_val, dict):
        surface_val = " ".join(str(k) for k in surface_val.keys())
    primary_val = terrain.get("primary", "")
    if isinstance(primary_val, dict):
        primary_val = " ".join(str(k) for k in primary_val.keys())
    # Fields and list items join with ". " so each stays its own clause for
    # the hedge check (a hedge in one feature must not soften the next).
    surface = (str(surface_val) + ". " + str(primary_val)).lower()
    features_raw = terrain.get("features", [])
    if isinstance(features_raw, list):
        features = ". ".join(str(f) for f in features_raw).lower()
        features_list = [str(f) for f in features_raw]
    else:
        features = str(features_raw).lower()
        features_list = [str(features_raw)] if features_raw else []
    combined = surface + ". " + features

    distance_mi = vitals.get("distance_mi", 50)
    if distance_mi is None:
        distance_mi = 50
    if isinstance(distance_mi, str):
        # Handle strings like "70" or "50-100"
        try:
            distance_mi = int(re.sub(r'[^\d]', '', distance_mi.split('-')[0].split(',')[0]))
        except (ValueError, IndexError):
            logging.warning("Could not parse distance_mi '%s', defaulting to 50", distance_mi)
            distance_mi = 50
    elevation_ft = vitals.get("elevation_ft", 0)
    if elevation_ft is None:
        elevation_ft = 0
    if isinstance(elevation_ft, str):
        # Handle strings like "4,500-9,116" — take the first number
        try:
            elevation_ft = int(re.sub(r'[^\d]', '', elevation_ft.split('-')[0]))
        except (ValueError, IndexError):
            logging.warning("Could not parse elevation_ft '%s', defaulting to 0", elevation_ft)
            elevation_ft = 0
    terrain_types = vitals.get("terrain_types", [])
    if isinstance(terrain_types, list):
        combined += ". " + ". ".join(str(t).lower() for t in terrain_types)

    return combined, tech_rating, distance_mi, elevation_ft, features_list


def extract_negated_keywords(text: str) -> set:
    """Find keywords that are negated (e.g. 'no mud' → {'mud'})."""
    return {m.group(1).lower() for m in NEGATION_PATTERN.finditer(text)}


def keyword_present(text: str, keyword: str, negated: set) -> bool:
    """Check if keyword starts a word in text AND is not negated."""
    return (keyword not in negated
            and re.search(r"\b" + re.escape(keyword), text) is not None)


def count_mentions(text: str, pattern: re.Pattern) -> tuple:
    """Count (firm, hedged) mentions of pattern in text, skipping negated ones.

    A mention is hedged when a HEDGE_WORDS word sits within HEDGE_WINDOW words
    of it in the same clause, negated when a NEGATION_WORDS word sits in the
    three words before it.
    """
    firm = hedged = 0
    for clause in CLAUSE_SPLIT.split(text.lower()):
        for m in pattern.finditer(clause):
            before = WORD.findall(clause[:m.start()])
            after = WORD.findall(clause[m.end():])[:HEDGE_WINDOW]
            if NEGATION_WORDS & set(before[-3:]):
                continue
            if HEDGE_WORDS & set(before[-HEDGE_WINDOW:] + after):
                hedged += 1
            else:
                firm += 1
    return firm, hedged


# ── Race Profile Builder ─────────────────────────────────────


def build_race_profile(rd: dict, raw_race: dict, weather: dict) -> dict:
    """Build a race profile with parsed terrain demands.

    Returns dict with:
      - surface_category: fast/mixed/technical/muddy/wet
      - tech_rating, distance_mi, elevation_ft
      - needs_puncture, needs_wet, needs_mud, mud_risk, needs_speed,
        needs_comfort
      - precip_pct, climbing_ratio
      - combined_text (for debugging)

    The surface category comes from the course text alone. Weather (an
    optional data/weather/{slug}.json, share of race-month days with any
    rain) only adds wet-grip weighting: "it rained on 55% of August days in
    Leadville" is not a wet course, and those files are not in the repo, so
    letting them pick the category made picks unreproducible.
    """
    combined, tech_rating, distance_mi, elevation_ft, features_list = \
        parse_terrain_text(raw_race)
    precip_pct = weather.get("precip_chance_pct", 20)

    # Climbing ratio: ft per mile
    climbing_ratio = elevation_ft / max(distance_mi, 1)

    # Determine surface demands. Firm mud ("infamous mud sectors") makes the
    # course muddy; hedged mud ("occasional sand/mud") or any clay is a risk
    # that favors mud clearance without forcing mud tires.
    mud_firm, mud_hedged = count_mentions(combined, MUD_TERMS)
    clay_firm, clay_hedged = count_mentions(combined, CLAY_TERMS)
    wet_firm, wet_hedged = count_mentions(combined, WET_TERMS)
    needs_mud = mud_firm > 0
    mud_risk = not needs_mud and (mud_hedged + clay_firm + clay_hedged) > 0
    wet_surface = wet_firm > 0
    needs_wet = (wet_surface or wet_hedged > 0 or needs_mud or mud_risk
                 or precip_pct >= PRECIP_WET_THRESHOLD)
    needs_puncture = sum(count_mentions(combined, PUNCTURE_TERMS)) > 0
    needs_speed = tech_rating <= 2 and not needs_mud
    needs_comfort = distance_mi >= COMFORT_DISTANCE_MI

    # Is it truly technical singletrack or just chunky/rough gravel?
    has_singletrack = sum(count_mentions(combined, SINGLETRACK_TERMS)) > 0

    # Classify primary surface demand
    if needs_mud:
        surface_category = SURFACE_MUDDY
    elif wet_surface:
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
        "mud_risk": mud_risk,
        "needs_speed": needs_speed,
        "needs_comfort": needs_comfort,
        "combined_text": combined,
        "features_list": features_list,
        # Sourced width floor carried in the tire block so re-runs keep it.
        "min_width_mm": (raw_race.get("tire_recommendations") or {}).get("min_width_mm"),
    }


# ── Filter, Then Rank by Course Cost ─────────────────────────


def is_technical(profile: dict) -> bool:
    return profile["surface_category"] == SURFACE_TECHNICAL or profile["tech_rating"] >= 4


def target_width(profile: dict) -> int:
    """Course width target, raised to any sourced organizer floor."""
    target = WIDTH_TARGETS.get(min(max(profile["tech_rating"], 1), 4), WIDTH_TARGETS[2])
    return max(target, profile.get("min_width_mm") or 0)


def filter_tires(tires: list, profile: dict) -> list:
    """Tires that can be picked for this course.

    Only tires BRR has tested at a race width are candidates: every pick
    carries measured numbers or it isn't a pick.
    """
    filtered = []
    for tire in tires:
        if not tire.get("lab_tested"):
            continue
        # Mud is the course: a tire needs real mud clearance
        if profile["needs_mud"] and tire.get("mud_clearance") not in ("moderate", "high"):
            continue
        # The course itself is wet: no tire that grips poorly on wet ground
        if profile["surface_category"] == SURFACE_WET and \
           tire.get("wet_traction") == "poor":
            continue
        # Technical courses (tech 4+, or rough with singletrack): no file treads
        if is_technical(profile) and tire.get("tread_type") == "file":
            continue
        # Sourced width floor (organizer guidance): tire must come that wide
        if not offers_min_width(tire, profile):
            continue
        filtered.append(tire)
    return filtered


def lab_test(tire: dict, width: int):
    """BRR test for this width, else the nearest tested width (newest first)."""
    tests = tire.get("brr_tests") or []
    if not tests:
        return None
    return min(tests, key=lambda t: (abs(t["width_mm"] - width), -t["year"]))


def puncture_weight(profile: dict) -> float:
    if profile["needs_puncture"]:
        return PUNCTURE_W_SHARP
    if profile["needs_comfort"]:
        return PUNCTURE_W_LONG
    return PUNCTURE_W_BASE


def course_cost(tire: dict, width: int, profile: dict) -> dict:
    """Watts this tire costs on this course at this width (lower is better).

    Returns {"total": float, "parts": {name: watts}} so pages and tests can
    show exactly why a tire ranks where it does.
    """
    test = lab_test(tire, width)
    if test is None:
        return {"total": float("inf"), "parts": {}, "test": None}
    parts = {"rolling": test["rr_watts"]}
    parts["puncture"] = puncture_weight(profile) * max(0.0, PUNCTURE_REF - test["puncture_tread"])
    if profile["needs_wet"]:
        parts["wet"] = WET_W * max(0.0, WET_REF - test["wet_grip"])
    if is_technical(profile):
        parts["corners"] = KNOB_EDGE_W_TECH * max(0.0, KNOB_EDGE_REF - test["knob_edge_mm"])
    elif profile["tech_rating"] >= 3:
        parts["corners"] = KNOB_EDGE_W_ROUGH * max(0.0, KNOB_EDGE_REF - test["knob_edge_mm"])
    if profile["needs_mud"] or profile.get("mud_risk"):
        w = MUD_KNOB_W if profile["needs_mud"] else MUD_KNOB_W_RISK
        parts["mud"] = w * max(0.0, MUD_KNOB_REF - test["knob_center_mm"])
    short = target_width(profile) - width
    if short > 0 and profile["tech_rating"] >= 2:
        parts["width"] = WIDTH_SHORT_W * short
    if test["width_mm"] != width:
        parts["untested_width"] = UNTESTED_WIDTH_W
    return {"total": round(sum(parts.values()), 2),
            "parts": {k: round(v, 2) for k, v in parts.items() if v},
            "test": test}


def score_tire(tire: dict, profile: dict) -> float:
    """Higher is better: minus the course cost at the recommended width."""
    width = recommend_width(profile["tech_rating"], tire, profile.get("min_width_mm"))
    return -course_cost(tire, width, profile)["total"]


def recommend_width(tech_rating: int, tire: dict, min_width: int = None) -> int:
    """The offered width nearest the course target, never below a sourced floor.

    Ties go to the wider size: on gravel the extra volume is the safer miss.
    """
    target = WIDTH_TARGETS.get(min(max(tech_rating, 1), 4), WIDTH_TARGETS[2])
    widths = sorted(tire["widths_mm"])
    if min_width:
        target = max(target, min_width)
        widths = [w for w in widths if w >= min_width] or widths
    return min(widths, key=lambda w: (abs(w - target), -w))


def offers_min_width(tire: dict, profile: dict) -> bool:
    """True when the tire comes at least as wide as the course's sourced floor."""
    floor = profile.get("min_width_mm")
    return not floor or max(tire.get("widths_mm") or [0]) >= floor


def rank_tires(tires: list, profile: dict) -> list:
    """Every candidate with its width and cost, cheapest first."""
    candidates = filter_tires(tires, profile)
    if not candidates:
        logging.warning("All %d tires filtered out for surface=%s — falling back to lab-tested set",
                        len(tires), profile["surface_category"])
        candidates = [t for t in tires if t.get("lab_tested")]
    ranked = []
    for tire in candidates:
        w = recommend_width(profile["tech_rating"], tire, profile.get("min_width_mm"))
        cost = course_cost(tire, w, profile)
        ranked.append({"tire": tire, "width": w, "cost": cost,
                       "score": -cost["total"]})
    ranked.sort(key=lambda x: (x["cost"]["total"], x["tire"]["id"]))
    return ranked


def is_file_tread(tire: dict) -> bool:
    return tire.get("tread_type") == "file"


def get_top_tires(tires: list, profile: dict, n: int = 3) -> list:
    """The two cheapest tires on course cost, plus the cheapest with the other
    tread (file vs knobs) when the first two share one, so every course gets
    a real alternative instead of three versions of one answer."""
    ranked = rank_tires(tires, profile)
    picks = ranked[:max(n - 1, 0)]
    rest = ranked[len(picks):]
    if len(picks) == n - 1 and len({is_file_tread(p["tire"]) for p in picks}) == 1:
        other = next((r for r in rest if is_file_tread(r["tire"]) != is_file_tread(picks[0]["tire"])), None)
        if other:
            return picks + [other]
    return picks + rest[:n - len(picks)]


def has_shoulder_grip(tire: dict, width: int) -> bool:
    test = lab_test(tire, width)
    return bool(test) and test["knob_center_mm"] >= 1.2 and test["knob_edge_mm"] >= 2.1


def get_front_rear_split(tires: list, profile: dict, top_picks: list) -> dict:
    """Fast front, grippier rear on mixed and rough courses (tech 2-3).

    The rear carries 53% of the weight on a gravel bike (SILCA's split) and
    does the climbing and braking traction work, so it gets the knobs; the
    front gets the faster file tread.
    """
    tech_rating = profile["tech_rating"]
    if tech_rating < 2 or tech_rating >= 4 or len(top_picks) < 2:
        return {"applicable": False}

    ranked = rank_tires(tires, profile)
    fronts = [r for r in ranked if r["tire"].get("tread_type") == "file"]
    rears = [r for r in ranked if r["tire"].get("tread_type") in ("knobby", "aggressive")
             and has_shoulder_grip(r["tire"], r["width"])]
    if not fronts or not rears:
        return {"applicable": False}
    front, rear = fronts[0], rears[0]
    if front["tire"]["id"] == rear["tire"]["id"]:
        return {"applicable": False}

    def side(r):
        t = r["tire"]
        return {"tire_id": t["id"], "name": t["name"], "brand": t["brand"],
                "width_mm": r["width"], "msrp_usd": t.get("msrp_usd")}

    rear_test = lab_test(rear["tire"], rear["width"])
    elev = profile.get("elevation_ft") or 0
    climbing = f" on {elev:,.0f} ft of climbing" if elev >= 1000 else ""
    loose = " and in the mud" if profile.get("needs_mud") or profile.get("mud_risk") else ""
    return {
        "applicable": True,
        "front": side(front),
        "rear": side(rear),
        "rationale": (f"The rear carries 53% of the weight and does the traction "
                      f"work{climbing}{loose}, so it gets the "
                      f"{rear_test['knob_center_mm']:g}mm center knobs; the front "
                      f"rolls the faster file tread."),
    }


def sharp_term(profile: dict) -> str:
    """What the course text says is sharp: "flint", "limestone", else "sharp rock"."""
    text = profile.get("combined_text", "")
    for noun in ("flint", "limestone", "shale", "chert"):
        if re.search(rf"\b{noun}\b", text):
            return noun
    return "sharp rock"


def pick_reasons(tire: dict, width: int, profile: dict) -> str:
    """Why this tire fits this course, in measured numbers. Strengths only."""
    test = lab_test(tire, width)
    if test is None:
        return "No lab data at this width."
    if test["width_mm"] == width:
        out = [f"Rolls {test['rr_watts']:g} W at {width}mm on BRR's drum"]
    else:
        out = [f"BRR tested the {test['width_mm']}mm: {test['rr_watts']:g} W"]
    if profile["needs_puncture"] and test["puncture_tread"] >= PUNCTURE_MODERATE_PTS:
        out.append(f"Puncture score {test['puncture_tread']:g} for the {sharp_term(profile)}")
    if (profile["needs_mud"] or profile.get("mud_risk")) and test["knob_center_mm"] >= 1.5:
        out.append(f"{test['knob_center_mm']:g}mm center knobs for mud")
    elif (is_technical(profile) or profile["tech_rating"] >= 3) and test["knob_edge_mm"] >= 2.3:
        out.append(f"{test['knob_edge_mm']:g}mm shoulder knobs for loose corners")
    if profile["needs_wet"] and test["wet_grip"] >= 75:
        out.append(f"Wet grip {test['wet_grip']:g}")
    return ". ".join(out[:3]) + "."


def generate_why_text(tire: dict, profile: dict, race_name: str) -> str:
    """'Why this tire' line for the race tire guide."""
    width = recommend_width(profile["tech_rating"], tire, profile.get("min_width_mm"))
    return esc(pick_reasons(tire, width, profile))


# ── Pressure Table ────────────────────────────────────────────


def gravel_category(tech_rating: int) -> int:
    """SILCA's gravel category (1 smooth hardpack .. 4 rough) from tech rating."""
    return min(max(tech_rating or 2, 1), 4)


def pressure_psi(rider_lb: float, width_mm: float, category: int) -> tuple:
    """(front, rear) psi, tubeless race casing. See PRESSURE_A."""
    system = rider_lb + BIKE_AND_KIT_LB
    lw = math.log(width_mm / 45)
    front = (PRESSURE_A[category] * (system / 180) ** PRESSURE_WEIGHT_EXP
             * math.exp(PRESSURE_W1 * lw + PRESSURE_W2 * lw ** 2))
    return front, front * PRESSURE_REAR


def pressure_widths(rec_width: int) -> list:
    """The course width plus one size either side, inside 38-55mm."""
    return [w for w in (rec_width - 5, rec_width, rec_width + 5) if 38 <= w <= 55]


def compute_pressure_table(tech_rating: int, rec_width: int) -> list:
    """Front/rear psi by rider weight (rows) and tire width (columns).

    Returns [{"rider_lb": 150, "cells": {45: (25, 26), ...}}, ...], whole psi.
    """
    cat = gravel_category(tech_rating)
    widths = pressure_widths(rec_width)
    rows = []
    for rider in RIDER_WEIGHTS_LB:
        cells = {}
        for w in widths:
            f, r = pressure_psi(rider, w, cat)
            cells[w] = (round(f), round(r))
        rows.append({"rider_lb": rider, "cells": cells})
    return rows


# ── Setup Strategy ────────────────────────────────────────────


def sealant_ml(width_mm: int) -> int:
    """Stan's per-tire volume for the nearest charted width (ties go wider)."""
    nearest = min(STANS_SEALANT_ML, key=lambda w: (abs(w - width_mm), -w))
    return STANS_SEALANT_ML[nearest]


def build_setup_strategy(tech_rating: int, rec_width: int, profile: dict) -> dict:
    """Sealant, inserts and spares for this course at its width.

    Returns {"items": [{"title", "lead", "body"}], "sources": [(label, url)]}.
    Volumes, refresh intervals and insert claims come from the makers' pages
    above; whether a course needs inserts or a boot is our call from the
    course text (sharp rock) and tech rating.
    """
    sharp = profile.get("needs_puncture", False)
    technical = is_technical(profile)
    ml = sealant_ml(rec_width)
    sources = [("Stan's sealant chart", STANS_SEALANT_URL),
               ("Schwalbe tubeless FAQ", SCHWALBE_TUBELESS_URL)]
    items = [{
        "title": "Sealant",
        "lead": f"{ml} ml per tire",
        "body": (f"Stan's volume for a {rec_width}mm tire. Stan's and Schwalbe say "
                 "sealant lasts 2 to 7 months, so refill if yours is older than 2."),
    }]

    if sharp or technical:
        fits = [i for i in INSERTS if i[3][0] <= rec_width <= i[3][1]]
        why = (f"the {sharp_term(profile)}" if sharp else "the technical sections")
        named = " or ".join(f"{name} ({grams} g)" for name, _, grams, _ in fits)
        body = (f"An insert protects the rim from {why} at these pressures and "
                f"lets you ride out a flat.")
        if named:
            body += f" At {rec_width}mm: {named}."
        if any(name.startswith("Tannus") for name, *_ in fits):
            body += " Tannus says to run 0.1 to 0.5 bar (1.5 to 7 psi) less with its insert."
        items.append({"title": "Inserts", "lead": "Run them", "body": body})
        sources += [(name, url) for name, url, _, _ in fits]
    else:
        items.append({"title": "Inserts", "lead": "Skip them",
                      "body": "No sharp rock or technical sections in the course notes."})

    long_race = (profile.get("distance_mi") or 0) >= LONG_RACE_MI
    kit = ["plugs", "two tubes" if long_race else "a tube"]
    if sharp:
        kit.append("a boot for sidewall cuts")
    kit.append("CO2 plus a mini pump" if long_race else "CO2")
    items.append({"title": "Spares",
                  "lead": f"{kit[0].capitalize()}, " + ", ".join(kit[1:-1]) + f" and {kit[-1]}",
                  "body": ""})
    return {"items": items, "sources": sources}


# ── Condition Alternatives ────────────────────────────────────


def get_condition_alternatives(tires: list, profile: dict, top_picks: list) -> dict:
    """Plan B tires for a wet day and a dry day, not already in the top 3.

    Each is the cheapest tire on the same course cost with the day's
    conditions switched on (wet) or off (dry, file treads only).
    """
    top_ids = {p["tire"]["id"] for p in top_picks}
    primary = top_picks[0]["tire"] if top_picks else {}

    def best(day_profile, keep):
        for r in rank_tires(tires, day_profile):
            if r["tire"]["id"] not in top_ids and keep(r["tire"]):
                return r
        return None

    wet_alt = None
    if primary.get("wet_traction") != "good":
        wet_alt = best({**profile, "needs_wet": True},
                       lambda t: t.get("wet_traction") == "good")
    dry_alt = None
    if primary.get("tread_type") != "file":
        dry_alt = best({**profile, "needs_wet": False, "needs_mud": False,
                        "mud_risk": False},
                       lambda t: t.get("tread_type") == "file")
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--gg-spacing-md);
}

.tg-surface-box p,
.tg-tire-why,
.tg-tire-cost,
.tg-pressure-note,
.tg-setup-item p,
.tg-alt-card p {
  max-width: 68ch;
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
.tg-tire-link {
  color: inherit;
  text-decoration: underline;
  text-decoration-thickness: 2px;
  text-underline-offset: 3px;
}
.tg-tire-link:hover {
  color: var(--gg-color-teal);
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
.tg-tire-cost {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
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
.tg-podium-title {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  margin-top: var(--gg-spacing-lg);
}
.tg-podium-table td { vertical-align: top; }
.tg-podium-detail { font-size: var(--gg-font-size-xs); color: var(--gg-color-secondary-brown); }
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
  grid-template-columns: repeat(3, 1fr);
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

@media (max-width: 480px) {
  .tg-email-capture-row { flex-direction: column; gap: 8px; }
  .tg-email-capture-input { border-right: 2px solid var(--gg-color-tan); }
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
    <h1>Best Tires for {esc(rd['name'])} {SEASON_YEAR}</h1>
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


def tire_link(tire_id, name: str) -> str:
    """Tire name linked to its /tire/{id}/ page (every database tire has one)."""
    if not tire_id:
        return esc(name)
    return f'<a href="/tire/{esc(tire_id)}/" class="tg-tire-link">{esc(name)}</a>'


PODIUM_PATH = Path(__file__).resolve().parent.parent / "data" / "tires" / "podium" / "setups.json"


def load_podiums() -> dict:
    """slug -> {"edition_year", "results_url", "entries"} from the sourced file."""
    try:
        return json.loads(PODIUM_PATH.read_text(encoding="utf-8"))["races"]
    except (OSError, KeyError, json.JSONDecodeError):
        return {}


def podium_width(entry: dict) -> str:
    f, r = entry.get("front_width_mm"), entry.get("rear_width_mm")
    if not f and not r:
        return "width not given"
    if f == r or not r or not f:
        return f"{f or r}mm"
    return f"{f}mm front, {r}mm rear"


def build_podium_block(podium: dict, tire_db: list) -> str:
    """What the podium rode, each row linked to its source. Tire names link to
    our page only when the source's name matches a database tire exactly."""
    if not podium or not podium.get("entries"):
        return ""
    ids = {t["name"]: t["id"] for t in tire_db}
    rows = []
    for e in podium["entries"]:
        detail = "; ".join(x for x in (podium_width(e), e.get("pressure"), e.get("note")) if x)
        source = (f'<a href="{esc(e["source_url"])}" target="_blank" rel="noopener">'
                  f'{esc(e["source_name"])}</a>')
        if e["source_type"] == "brand":
            source += " (brand)"
        elif e["source_type"] == "rider":
            source += " (rider)"
        rows.append(
            f'<tr><td>{esc(e["category"].title())} {esc(e["place"])}<br>'
            f'<strong>{esc(e["rider"])}</strong></td>'
            f'<td>{tire_link(ids.get(e["tire"]), e["tire"])}<br>'
            f'<span class="tg-podium-detail">{esc(detail)}</span></td>'
            f'<td>{source}</td></tr>')
    return f'''<h3 class="tg-podium-title">What the {esc(podium["edition_year"])} Podium Ran</h3>
    <table class="tg-pressure-table tg-podium-table">
      <thead><tr><th>Rider</th><th>Tire</th><th>Source</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>'''


def build_tire_cards(top_picks: list, profile: dict, race_name: str,
                     front_rear: dict = None, podium_html: str = "") -> str:
    """Build Section 02: Top 3 Tire Recommendations with real data."""
    cards = []
    for i, pick in enumerate(top_picks):
        tire = pick["tire"]
        width = pick["width"]
        rank = i + 1

        why_text = generate_why_text(tire, profile, race_name)
        cost = pick.get("cost") or course_cost(tire, width, profile)
        test = cost["test"]

        msrp = tire.get("msrp_usd")
        price_label = f" &mdash; ${msrp:.2f}" if msrp else ""

        badges = []
        if test:
            fast = " tg-badge-item--fast" if test["rr_watts"] <= CRR_FAST_THRESHOLD else ""
            badges.append((f"{test['rr_watts']:g} W @ {test['test_psi']} psi", fast))
            tough = " tg-badge-item--high" if test["puncture_tread"] >= 45 else ""
            badges.append((f"Puncture {test['puncture_tread']:g}", tough))
            badges.append((f"Wet grip {test['wet_grip']:g}", ""))
            if test["weight_g"]:
                badges.append((f"{test['weight_g']:g} g", ""))
        badges_html = "".join(f'<span class="tg-badge-item{c}">{esc(t)}</span>' for t, c in badges)
        parts = ", ".join(f"{k.replace('_', ' ')} {v:g}" for k, v in cost["parts"].items())
        cost_line = f"Course cost {cost['total']:g} W: {parts}" if test else ""

        review_link = ""
        if test:
            review_link = (f'<a href="{esc(test["url"])}" target="_blank" rel="noopener" '
                           f'class="tg-review-link">BRR test, {test["width_mm"]}mm ({test["year"]}) &rarr;</a>')

        cards.append(f'''<div class="tg-tire-card">
      <div class="tg-tire-rank tg-tire-rank--{rank}">#{rank}</div>
      <div class="tg-tire-header">
        <span class="tg-tire-brand">{esc(tire['brand'])}</span>
        <h3 class="tg-tire-name">{tire_link(tire['id'], tire['name'])}</h3>
        <span class="tg-tire-width">{width}mm{price_label}</span>
      </div>
      <div class="tg-tire-body">
        <p class="tg-tire-why">{why_text}</p>
        <div class="tg-badges">{badges_html}</div>
        <p class="tg-tire-cost">{esc(cost_line)}</p>
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
        <strong>Front:</strong> {tire_link(f.get('tire_id'), f['name'])} ({f['width_mm']}mm) &mdash;
        <strong>Rear:</strong> {tire_link(r.get('tire_id'), r['name'])} ({r['width_mm']}mm)
      </p>
      <p style="font-family:var(--gg-font-data);font-size:var(--gg-font-size-xs);color:var(--gg-color-secondary-brown)">{esc(rationale)}</p>
    </div>'''

    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">02 / TOP 3 TIRE RECOMMENDATIONS</span>
    <h2>Best Tires for {esc(race_name)}</h2>
    {''.join(cards)}
    {split_html}
    {podium_html}
    <p class="tg-pressure-note"><a href="/tire/#method">How we pick</a></p>
  </div>
</section>'''


def build_pressure_section(pressure_rows: list, tech_rating: int, rec_width: int,
                           raw_race: dict) -> str:
    """Section 03: front / rear psi by rider weight and tire width."""
    widths = list(pressure_rows[0]["cells"]) if pressure_rows else [rec_width]
    head = "".join(f"<th>{w}mm</th>" for w in widths)
    rows_html = "".join(
        "<tr><td>{} lb</td>{}</tr>".format(
            row["rider_lb"],
            "".join(f"<td>{f} / {r}</td>" for f, r in (row["cells"][w] for w in widths)))
        for row in pressure_rows)
    cat = gravel_category(tech_rating)
    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">03 / TIRE PRESSURE GUIDE</span>
    <h2>Front / Rear Pressure (psi)</h2>
    <table class="tg-pressure-table">
      <thead><tr><th>Rider</th>{head}</tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p class="tg-pressure-note">Tubeless race casing, {BIKE_AND_KIT_LB} lb of bike and kit, SILCA gravel category {cat}. Use the column for the width your tire measures on your rims. Our model is fitted to <a href="https://silca.cc/pages/pro-tire-pressure-calculator" target="_blank" rel="noopener">SILCA's calculator</a> and lands within 0.5 psi of it.</p>
  </div>
</section>'''


def build_setup_section(strategy: dict) -> str:
    """Section 04: sealant, inserts and spares, with the makers' pages linked."""
    items = "\n      ".join(
        '<div class="tg-setup-item"><h4>{}</h4><p><strong>{}</strong></p>{}</div>'.format(
            esc(i["title"]), esc(i["lead"]),
            f"<p>{esc(i['body'])}</p>" if i["body"] else "")
        for i in strategy["items"])
    sources = ", ".join(
        f'<a href="{esc(url)}" target="_blank" rel="noopener">{esc(label)}</a>'
        for label, url in strategy["sources"])
    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">04 / SETUP STRATEGY</span>
    <h2>Race-Day Tire Setup</h2>
    <div class="tg-setup-grid">
      {items}
    </div>
    <p class="tg-pressure-note">Sources: {sources}.</p>
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
        test = lab_test(t, w)
        reason = (f"{test['rr_watts']:g} W at {test['width_mm']}mm, wet grip {test['wet_grip']:g}, "
                  f"puncture {test['puncture_tread']:g} (BRR).") if test else ""
        cards.append(f'''<div class="tg-alt-card">
      <div class="tg-alt-label">PLAN B: WET CONDITIONS</div>
      <h4>{tire_link(t['id'], t['name'])} ({w}mm){price_str}</h4>
      <p>{esc(reason)}</p>
    </div>''')

    if alts.get("dry"):
        t = alts["dry"]["tire"]
        w = alts["dry"]["width"]
        msrp = t.get("msrp_usd")
        price_str = f" &mdash; ${msrp:.2f}" if msrp else ""
        test = lab_test(t, w)
        reason = (f"{test['rr_watts']:g} W at {test['width_mm']}mm, wet grip {test['wet_grip']:g}, "
                  f"puncture {test['puncture_tread']:g} (BRR).") if test else ""
        cards.append(f'''<div class="tg-alt-card">
      <div class="tg-alt-label">PLAN B: DRY CONDITIONS</div>
      <h4>{tire_link(t['id'], t['name'])} ({w}mm){price_str}</h4>
      <p>{esc(reason)}</p>
    </div>''')

    return f'''<section class="tg-section">
  <div class="tg-container">
    <span class="tg-section-num">05 / CONDITION ALTERNATIVES</span>
    <h2>Plan B Tires</h2>
    {''.join(cards)}
  </div>
</section>'''


def build_email_capture_section(rd: dict) -> str:
    """Build email capture CTA — unlocks the race-day tire setup guide."""
    slug = esc(rd["slug"])
    name = esc(rd["name"])
    return f'''<section class="tg-section">
  <div class="tg-container">
    <div class="tg-email-capture">
      <div class="tg-email-capture-inner">
        <div class="tg-email-capture-badge">FREE</div>
        <h3 class="tg-email-capture-title">GET YOUR RACE DAY TIRE SETUP</h3>
        <p class="tg-email-capture-text">Tire picks, pressure chart, sealant amounts, and tubeless tips &mdash; customized for {name}.</p>
        <form class="tg-email-capture-form" id="tg-email-capture-form" autocomplete="off">
          <input type="hidden" name="race_slug" value="{slug}">
          <input type="hidden" name="race_name" value="{name}">
          <input type="hidden" name="source" value="tire_guide">
          <input type="hidden" name="website" value="">
          <div class="tg-email-capture-row">
            <input type="email" name="email" required placeholder="your@email.com" class="tg-email-capture-input" aria-label="Email address">
            <button type="submit" class="tg-email-capture-btn">SHOW TIRE SETUP</button>
          </div>
        </form>
        <div class="tg-email-capture-success" id="tg-email-capture-success" style="display:none">
          <p class="tg-email-capture-check">&#10003; You're on the list.</p>
        </div>
        <p class="tg-email-capture-fine">No spam. Unsubscribe anytime.</p>
      </div>
    </div>
  </div>
</section>'''


def build_inline_js() -> str:
    """Build inline JavaScript for email capture form and exit-intent popup."""
    return '''<script>
document.querySelectorAll('a[href*="/prep-kit/"]').forEach(function(el){
  el.addEventListener('click',function(){
    if(typeof gtag==='function'){
      gtag('event','cta_click',{source:'guide',cta_name:'tire_guide_prep_kit'});
    }
  });
});

/* Email capture form — tire setup CTA */
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
    var subBtn=form.querySelector('button[type=submit]');
    var errEl=document.getElementById('tg-email-capture-err');
    if(!errEl){errEl=document.createElement('p');errEl.id='tg-email-capture-err';errEl.className='tg-email-capture-fine';form.parentNode.insertBefore(errEl,form.nextSibling);}
    errEl.style.display='none';
    if(subBtn) subBtn.disabled=true;
    var payload={
      email:email,
      race_slug:form.race_slug.value,
      race_name:form.race_name.value,
      source:form.source.value,
      website:form.website.value
    };
    /* Only claim success once the capture is actually stored. A swallowed
       error used to show the unlocked state for a lead nobody recorded. */
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:(typeof AbortSignal!=='undefined'&&AbortSignal.timeout)?AbortSignal.timeout(10000):undefined})
    .then(function(resp){
      if(!resp.ok) throw new Error('bad status');
      try{
        localStorage.setItem(LS_KEY,JSON.stringify({email:email,exp:Date.now()+EXPIRY_DAYS*86400000}));
      }catch(ex){}
      if(typeof gtag==='function'){
        gtag('event','email_capture',{race_slug:form.race_slug.value,source:'tire_guide'});
      }
      form.style.display='none';
      var success=document.getElementById('tg-email-capture-success');
      if(success) success.style.display='block';
    })
    .catch(function(){
      errEl.textContent='That did not go through. Check your connection and try again.';
      errEl.style.display='block';
      if(subBtn) subBtn.disabled=false;
    });
  });
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
        "headline": f"Best Tires for {name} {SEASON_YEAR}: Top 3 Picks + Pressure Guide",
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

    # Step 4: The course width (stored picks carry it; a sourced floor wins)
    rec_width = enriched.get("recommended_width_mm") or target_width(profile)

    # Build page sections
    header = build_header(rd)
    surface = build_surface_analysis(rd, raw_race, weather)
    podium_html = build_podium_block(load_podiums().get(rd["slug"]), tire_db)
    tire_cards = build_tire_cards(top_picks, profile, rd["name"], front_rear, podium_html)

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
    title = f"Best Tires for {esc(rd['name'])} {SEASON_YEAR}: Top 3 Picks + Pressure Guide | Gravel God"
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

# SITE-SYNC S3 (docs/specs/SITE_SYNC_SPEC.md): fabricated race pages removed
# 2026-07, 301-redirected to state/region best-of hubs. profiles DELETED 2026-07-22
# (research-dumps + git history are the audit trail); tombstones are canonical
# in config/tombstones.json and must never regenerate a page.
REMOVED_FABRICATED_SLUGS = frozenset(
    t["slug"] for t in __import__("json").loads(
        (Path(__file__).resolve().parent.parent / "config" / "tombstones.json")
        .read_text())["tombstones"])


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

        # Only races with actual tire recommendations get a guide page — the
        # sitemap, race-page links, and prep-kit/hub crosslinks all key off
        # tire_recommendations.primary. Generating without this filter would
        # resurrect the ~217 stale pages removed 2026-07-22.
        def _has_tire_recs(f: Path) -> bool:
            try:
                r = json.loads(f.read_text(encoding="utf-8")).get("race", {})
            except (OSError, json.JSONDecodeError):
                return False
            return bool((r.get("tire_recommendations") or {}).get("primary"))

        files = [f for f in sorted(primary.glob('*.json'))
                 if f.stem not in REMOVED_FABRICATED_SLUGS and _has_tire_recs(f)]
        active_slugs = {f.stem for f in files}
        stale_outputs = [
            path for path in output_dir.glob("*.html")
            if path.stem not in active_slugs
        ]
        for path in stale_outputs:
            path.unlink()
        if stale_outputs:
            print(f"Pruned {len(stale_outputs)} stale tire guide pages")

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
