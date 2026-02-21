#!/usr/bin/env python3
"""
Generate "The State of Gravel" data insights page in neo-brutalist style.

A data journalism page (NYT/Pudding.cool style) with scroll-triggered
infographics and editorial narrative. Surfaces original research from
328 rated gravel race profiles across 14 scoring criteria.

Uses brand tokens exclusively — zero hardcoded hex, no border-radius, no
box-shadow, <rect> only (no <circle>).

Usage:
    python generate_insights.py
    python generate_insights.py --output-dir ./output
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
from pathlib import Path
from collections import defaultdict
from statistics import mean, median

from generate_neo_brutalist import (
    GA_MEASUREMENT_ID,
    SITE_BASE_URL,
    get_page_css,
    write_shared_assets,
)
from brand_tokens import get_ab_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html, get_site_header_css

OUTPUT_DIR = Path(__file__).parent / "output"
RACE_INDEX = Path(__file__).parent.parent / "web" / "race-index.json"
RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"

# 14 scoring dimensions
ALL_DIMS = [
    "logistics", "length", "technicality", "elevation", "climate",
    "altitude", "adventure", "prestige", "race_quality", "experience",
    "community", "field_depth", "value", "expenses",
]

DIM_LABELS = {
    "logistics": "Logistics", "length": "Length", "technicality": "Technicality",
    "elevation": "Elevation", "climate": "Climate", "altitude": "Altitude",
    "adventure": "Adventure", "prestige": "Prestige", "race_quality": "Race Quality",
    "experience": "Experience", "community": "Community", "field_depth": "Field Depth",
    "value": "Value", "expenses": "Expenses",
}

# US state abbreviations → tile grid positions (col, row) for cartogram
# Standard US tile grid map layout (10 cols × 8 rows approximation)
US_TILE_GRID = {
    "AK": (0, 0), "ME": (10, 0),
    "WI": (5, 1), "VT": (9, 1), "NH": (10, 1),
    "WA": (0, 2), "ID": (1, 2), "MT": (2, 2), "ND": (3, 2), "MN": (4, 2),
    "IL": (5, 2), "MI": (6, 2), "NY": (8, 2), "MA": (9, 2), "CT": (10, 2),
    "OR": (0, 3), "NV": (1, 3), "WY": (2, 3), "SD": (3, 3), "IA": (4, 3),
    "IN": (5, 3), "OH": (6, 3), "PA": (7, 3), "NJ": (8, 3), "RI": (9, 3),
    "CA": (0, 4), "UT": (1, 4), "CO": (2, 4), "NE": (3, 4), "MO": (4, 4),
    "KY": (5, 4), "WV": (6, 4), "VA": (7, 4), "MD": (8, 4), "DE": (9, 4),
    "AZ": (1, 5), "NM": (2, 5), "KS": (3, 5), "AR": (4, 5), "TN": (5, 5),
    "NC": (6, 5), "SC": (7, 5),
    "OK": (3, 6), "LA": (4, 6), "MS": (5, 6), "AL": (6, 6), "GA": (7, 6),
    "HI": (0, 7), "TX": (3, 7), "FL": (7, 7),
}

# Full set of US state abbreviations
US_STATES = sorted(US_TILE_GRID.keys())

# Month order for calendar
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


def safe_num(val, default=0):
    """Convert a value to float, handling None, strings, and 'N/A'."""
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace(",", "").strip()
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return default
    return default


def extract_price(registration_text: str) -> float | None:
    """Extract dollar amount from registration text like 'Cost: $345'."""
    if not registration_text:
        return None
    # Match patterns like $345, $4,400, $20
    matches = re.findall(r'\$[\d,]+', registration_text)
    if not matches:
        return None
    # Take last match (often is the actual cost)
    price_str = matches[-1].replace("$", "").replace(",", "")
    try:
        return float(price_str)
    except ValueError:
        return None


def extract_state(location: str) -> str | None:
    """Extract US state abbreviation from location string."""
    if not location:
        return None
    # Common state name → abbreviation mapping
    state_map = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
        "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
        "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
        "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
        "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
        "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
        "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
        "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
        "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
        "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
        "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    }
    # Try full state names first
    for name, abbr in state_map.items():
        if name in location:
            return abbr
    # Try 2-letter abbreviation at end (e.g., "Emporia, KS")
    m = re.search(r',\s*([A-Z]{2})\s*$', location)
    if m and m.group(1) in US_STATES:
        return m.group(1)
    return None


# ── Data Loading ───────────────────────────────────────────────


def load_race_index() -> list[dict]:
    """Load race-index.json."""
    with open(RACE_INDEX, encoding="utf-8") as f:
        return json.load(f)


def load_race_profile(slug: str) -> dict | None:
    """Load individual race profile JSON."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def enrich_races(races: list[dict]) -> list[dict]:
    """Enrich race index data with fields from individual profiles.

    Adds: founded, price, state, elevation_ft (if missing).
    """
    enriched = []
    for r in races:
        entry = dict(r)

        # Extract state from location
        entry["state"] = extract_state(r.get("location", ""))

        # Load profile for founding year and pricing
        profile = load_race_profile(r["slug"])
        if profile:
            race_data = profile.get("race", {})
            # Founded year
            history = race_data.get("history", {})
            founded = history.get("founded")
            if isinstance(founded, int) and 1900 <= founded <= 2026:
                entry["founded"] = founded
            else:
                entry["founded"] = None
            # Price from registration text
            vitals = race_data.get("vitals", {})
            reg = vitals.get("registration", "")
            entry["price"] = extract_price(reg)
            # Elevation if missing from index
            if not entry.get("elevation_ft"):
                entry["elevation_ft"] = safe_num(vitals.get("elevation_ft"))
        else:
            entry["founded"] = None
            entry["price"] = None

        enriched.append(entry)
    return enriched


def compute_stats(races: list[dict]) -> dict:
    """Compute aggregate statistics for the hero section."""
    total_races = len(races)
    distances = [safe_num(r.get("distance_mi")) for r in races if safe_num(r.get("distance_mi")) > 0]
    elevations = [safe_num(r.get("elevation_ft")) for r in races if safe_num(r.get("elevation_ft")) > 0]
    states_with_races = len({r["state"] for r in races if r.get("state")})
    total_distance = sum(distances)
    total_elevation = sum(elevations)
    everest_multiple = total_elevation / 29032 if total_elevation else 0
    prices = [r["price"] for r in races if r.get("price") is not None and r["price"] > 0]
    price_min = min(prices) if prices else 0
    price_max = max(prices) if prices else 0

    return {
        "total_races": total_races,
        "total_distance": round(total_distance),
        "total_elevation": round(total_elevation),
        "states_with_races": states_with_races,
        "everest_multiple": round(everest_multiple, 1),
        "price_min": int(price_min),
        "price_max": int(price_max),
        "median_price": int(median(prices)) if prices else 0,
    }


def compute_editorial_facts(races: list[dict]) -> dict:
    """Crunch data used across multiple editorial narratives.

    Returns a dict with data-driven facts for specific race references,
    provocative claims, and gravel culture voice.
    """
    # State counts + averages (US only)
    state_counts: dict[str, int] = defaultdict(int)
    state_scores: dict[str, list[float]] = defaultdict(list)
    for r in races:
        st = r.get("state")
        if st:
            state_counts[st] += 1
            state_scores[st].append(r.get("overall_score", 0))

    top_state = max(state_counts, key=lambda s: state_counts[s]) if state_counts else ""
    top_state_count = state_counts.get(top_state, 0)
    top_state_avg = mean(state_scores[top_state]) if state_scores.get(top_state) else 0

    # Quality state: highest avg score with min 3 races
    quality_candidates = {s: mean(sc) for s, sc in state_scores.items() if len(sc) >= 3}
    quality_state = max(quality_candidates, key=lambda s: quality_candidates[s]) if quality_candidates else top_state
    quality_state_avg = quality_candidates.get(quality_state, 0)
    quality_state_count = state_counts.get(quality_state, 0)

    # Cheap beat: cheap race (<$100) outscoring expensive (>$300)
    cheap_races = [(r, r["price"]) for r in races if r.get("price") and r["price"] < 100 and r.get("overall_score", 0) > 50]
    expensive_races = [(r, r["price"]) for r in races if r.get("price") and r["price"] > 300]
    cheap_beat = {}
    if cheap_races and expensive_races:
        cheap_races.sort(key=lambda x: -x[0].get("overall_score", 0))
        expensive_races.sort(key=lambda x: x[0].get("overall_score", 0))
        cr, cp = cheap_races[0]
        er, ep = expensive_races[0]
        if cr.get("overall_score", 0) > er.get("overall_score", 0):
            cheap_beat = {
                "cheap_name": cr["name"], "cheap_score": cr.get("overall_score", 0), "cheap_price": cp,
                "expensive_name": er["name"], "expensive_score": er.get("overall_score", 0), "expensive_price": ep,
            }

    # Youngest T1 race
    t1_with_year = [(r, r["founded"]) for r in races if r.get("tier") == 1 and r.get("founded")]
    t1_with_year.sort(key=lambda x: -x[1])
    youngest_t1 = {}
    if t1_with_year:
        r, yr = t1_with_year[0]
        youngest_t1 = {"name": r["name"], "founded": yr, "score": r.get("overall_score", 0)}

    # Midwest stats
    midwest = [r for r in races if r.get("region") == "Midwest"]
    midwest_count = len(midwest)
    midwest_avg = mean([r.get("overall_score", 0) for r in midwest]) if midwest else 0

    # Overrated: high prestige, lower tier than expected (p >= 4, tier >= 3)
    overrated_candidates = []
    for r in races:
        p = (r.get("scores") or {}).get("prestige", 0)
        tier = r.get("tier", 4)
        score = r.get("overall_score", 0)
        if p and p >= 3 and tier >= 3:
            overrated_candidates.append((r, p - (5 - tier), p, tier, score))
    overrated_candidates.sort(key=lambda x: (-x[1], -x[2]))
    overrated = [x[0] for x in overrated_candidates[:5]]

    # Underrated: low prestige, high score
    underrated_candidates = []
    for r in races:
        p = (r.get("scores") or {}).get("prestige", 0)
        score = r.get("overall_score", 0)
        tier = r.get("tier", 4)
        if p and p <= 2 and score >= 50:
            underrated_candidates.append((r, score - p * 10, p, score))
    underrated_candidates.sort(key=lambda x: (-x[1], -x[3]))
    underrated = [x[0] for x in underrated_candidates[:5]]

    # Pearson correlation: price vs score
    priced = [(r["price"], r.get("overall_score", 0)) for r in races if r.get("price") and r["price"] > 0]
    price_score_corr = 0.0
    if len(priced) >= 3:
        px = [p for p, _ in priced]
        sx = [s for _, s in priced]
        mean_p, mean_s = mean(px), mean(sx)
        cov = sum((p - mean_p) * (s - mean_s) for p, s in zip(px, sx))
        std_p = math.sqrt(sum((p - mean_p) ** 2 for p in px))
        std_s = math.sqrt(sum((s - mean_s) ** 2 for s in sx))
        if std_p > 0 and std_s > 0:
            price_score_corr = cov / (std_p * std_s)

    # Cheapest T1 race
    t1_priced = [(r, r["price"]) for r in races if r.get("tier") == 1 and r.get("price") and r["price"] > 0]
    t1_priced.sort(key=lambda x: x[1])
    cheapest_t1 = {}
    if t1_priced:
        r, p = t1_priced[0]
        cheapest_t1 = {"name": r["name"], "price": p, "score": r.get("overall_score", 0)}

    # Priciest T4 race
    t4_priced = [(r, r["price"]) for r in races if r.get("tier") == 4 and r.get("price") and r["price"] > 0]
    t4_priced.sort(key=lambda x: -x[1])
    priciest_t4 = {}
    if t4_priced:
        r, p = t4_priced[0]
        priciest_t4 = {"name": r["name"], "price": p, "score": r.get("overall_score", 0)}

    return {
        "top_state": top_state, "top_state_count": top_state_count, "top_state_avg": top_state_avg,
        "quality_state": quality_state, "quality_state_avg": quality_state_avg, "quality_state_count": quality_state_count,
        "cheap_beat": cheap_beat, "youngest_t1": youngest_t1,
        "midwest_count": midwest_count, "midwest_avg": midwest_avg,
        "overrated": overrated, "underrated": underrated,
        "price_score_corr": price_score_corr,
        "cheapest_t1": cheapest_t1, "priciest_t4": priciest_t4,
    }


def build_figure_wrap(chart_html: str, title: str, takeaway: str, chart_id: str) -> str:
    """Wrap a chart SVG in a figure container with title and takeaway.

    Mirrors the guide infographic pattern: gold border-bottom on title,
    teal border-left on takeaway, editorial font.
    """
    return f'''<figure class="gg-insights-figure" id="{esc(chart_id)}-figure">
  <div class="gg-insights-figure-title">{esc(title)}</div>
  {chart_html}
  <div class="gg-insights-figure-takeaway">{takeaway}</div>
</figure>'''


def build_overrated_underrated(races: list[dict], editorial_facts: dict) -> str:
    """Section: Two side-by-side card groups showing over/underrated races."""
    overrated = editorial_facts.get("overrated", [])
    underrated = editorial_facts.get("underrated", [])

    def _card(r: dict, editorial: str) -> str:
        name = r.get("name", "Unknown")
        slug = r.get("slug", "")
        tier = r.get("tier", 3)
        prestige = (r.get("scores") or {}).get("prestige", 0)
        score = r.get("overall_score", 0)
        scores = r.get("scores") or {}
        # Build dimension breakdown bars
        dim_bars = ""
        for dim in ALL_DIMS:
            val = scores.get(dim, 0)
            pct = val * 20  # 1-5 → 20-100%
            dim_bars += (
                f'          <div class="gg-ins-ou-dim">'
                f'<span class="gg-ins-ou-dim-label">{esc(DIM_LABELS[dim])}</span>'
                f'<div class="gg-ins-ou-dim-bar">'
                f'<div class="gg-ins-ou-dim-fill" data-tier="{tier}" '
                f'style="width:{pct}%"></div></div>'
                f'<span class="gg-ins-ou-dim-val">{val}/5</span></div>\n'
            )
        link_html = ""
        if slug:
            link_html = (
                f'          <a href="{SITE_BASE_URL}/race/{esc(slug)}/" '
                f'class="gg-ins-ou-link">View Full Profile &rarr;</a>\n'
            )
        return f'''      <div class="gg-insights-ou-card" tabindex="0" role="button" aria-expanded="false">
        <span class="gg-insights-ou-card-tier">Tier {tier}</span>
        <h3 class="gg-insights-ou-card-name">{esc(name)}</h3>
        <span class="gg-insights-ou-card-stats">Score: {score} &middot; Prestige: {prestige}/5</span>
        <p class="gg-insights-ou-card-editorial">{esc(editorial)}</p>
        <span class="gg-ins-ou-expand-hint">Click to see why &darr;</span>
        <div class="gg-ins-ou-detail" aria-hidden="true">
{dim_bars}{link_html}        </div>
      </div>
'''

    def _under_quip(r: dict) -> str:
        """Deadpan, data-forward quip for underrated races. Brand voice: coroner delivery."""
        s = r.get("scores") or {}
        prestige = s.get("prestige", 0)
        score = r.get("overall_score", 0)
        adventure = s.get("adventure", 0)
        tech = s.get("technicality", 0)
        elev = s.get("elevation", 0)
        value = s.get("value", 0)
        price = r.get("price") or 0
        dist = round(safe_num(r.get("distance_mi")))
        # Pick the most interesting data angle for each race
        suffering = tech + elev + s.get("altitude", 0)
        if suffering >= 13:
            return (f"Technicality {tech}/5. Elevation {elev}/5. Prestige {prestige}/5. "
                    f"The course is a sufferfest. The marketing budget is not.")
        if adventure >= 5 and dist >= 150:
            return (f"{dist} miles of adventure scored at {adventure}/5. "
                    f"Prestige: {prestige}/5. Nobody told the Instagram algorithm.")
        if price and price <= 80 and score >= 65:
            return (f"Scores {score} overall for ${price:.0f}. "
                    f"Some races charge three times that and deliver less.")
        if value >= 4 and prestige <= 2:
            return (f"Value: {value}/5. Prestige: {prestige}/5. "
                    f"The course does the talking. Just not very loudly.")
        return (f"Overall {score} across 14 dimensions. Prestige {prestige}/5. "
                f"The data sees what the hype cycle missed.")

    def _over_quip(r: dict) -> str:
        """Deadpan, data-forward quip for overrated races. Never punch down."""
        s = r.get("scores") or {}
        prestige = s.get("prestige", 0)
        score = r.get("overall_score", 0)
        tech = s.get("technicality", 0)
        adventure = s.get("adventure", 0)
        value = s.get("value", 0)
        dist = round(safe_num(r.get("distance_mi")))
        price = r.get("price") or 0
        if tech <= 2 and prestige >= 3:
            return (f"Technicality: {tech}/5. Prestige: {prestige}/5. "
                    f"The brand showed up. The course stayed home.")
        if dist <= 50:
            return (f"{dist} miles and a prestige score of {prestige}/5. "
                    f"Short races can be great. This one scores {score}.")
        if price and price >= 120 and value <= 3:
            return (f"${price:.0f} entry. Value: {value}/5. Overall: {score}. "
                    f"The gravel tax is real.")
        if adventure <= 3 and prestige >= 3:
            return (f"Adventure: {adventure}/5. Prestige: {prestige}/5. "
                    f"Name recognition and the actual ride are having different conversations.")
        return (f"Prestige {prestige}/5 writes a check the {score}-point score "
                f"quietly declines to cash.")

    under_cards = ""
    for r in underrated:
        under_cards += _card(r, _under_quip(r))

    over_cards = ""
    for r in overrated:
        over_cards += _card(r, _over_quip(r))

    return f'''<section class="gg-insights-section" id="overrated-underrated">
  <h2 class="gg-insights-section-title">Punching Above &amp; Below Their Weight</h2>
  <p class="gg-insights-narrative">Prestige and performance do not always align. We cross-referenced every race&#8217;s prestige score against its overall rating to find the biggest gaps &#8212; the races that outperform their reputation, and the ones that coast on name alone.</p>
  <div class="gg-insights-ou-grid">
    <div class="gg-insights-ou-group">
      <div class="gg-insights-ou-group-title">Punching Above Their Weight</div>
      <p class="gg-insights-ou-group-sub">These races scored well across 14 dimensions but have a prestige score of 2/5 or lower. The course delivers. The name recognition does not.</p>
{under_cards}    </div>
    <div class="gg-insights-ou-group">
      <div class="gg-insights-ou-group-title">The Prestige Premium</div>
      <p class="gg-insights-ou-group-sub">High prestige, middling scores. The registration page promises more than the course confirms.</p>
{over_cards}    </div>
  </div>
</section>'''


# ── Section Builders ───────────────────────────────────────────


def build_hero(stats: dict) -> str:
    """Section 0: Hero with animated counters."""
    counters = [
        (str(stats["total_races"]), "races analyzed"),
        (f"{stats['total_distance']:,}", "total miles"),
        (str(stats["states_with_races"]), "US states"),
        (f"{stats['everest_multiple']}x", "Everests of climbing"),
        (f"${stats['price_min']}&ndash;${stats['price_max']:,}", "price range"),
    ]
    counter_html = ""
    for value, label in counters:
        # Strip non-numeric for data-counter (keep digits and .)
        raw = re.sub(r'[^0-9.]', '', value.replace("&ndash;", "").replace(",", ""))
        counter_html += f'''      <div class="gg-insights-counter">
        <span class="gg-insights-counter-value" data-counter="{esc(raw)}">{value}</span>
        <span class="gg-insights-counter-label">{esc(label)}</span>
      </div>
'''
    return f'''<section class="gg-insights-hero" id="hero">
  <div class="gg-insights-hero-inner">
    <h1 class="gg-insights-hero-title">The State of Gravel</h1>
    <p class="gg-insights-hero-subtitle">{stats["total_races"]} gravel races. 14 scoring dimensions. {stats["states_with_races"]} states. Scroll to explore.</p>
    <p class="gg-insights-narrative">{stats["total_races"]} races, {stats["total_distance"]:,} miles, {stats['everest_multiple']}x Everests of climbing. Every race rated on 14 dimensions from logistics to prestige. Here is what the data reveals.</p>
    <div class="gg-insights-counters">
{counter_html}    </div>
  </div>
</section>'''


def build_race_data_embed(races: list[dict]) -> str:
    """Embed compact race data as JSON for client-side interactives."""
    entries = []
    for r in races:
        scores = r.get("scores") or {}
        dm = [scores.get(d, 0) for d in ALL_DIMS]
        entry = {
            "s": r.get("slug", ""),
            "n": r.get("name", ""),
            "t": r.get("tier", 4),
            "sc": r.get("overall_score", 0),
            "p": r.get("price") or 0,
            "d": round(safe_num(r.get("distance_mi"))),
            "e": round(safe_num(r.get("elevation_ft"))),
            "r": r.get("region", ""),
            "m": r.get("month", ""),
            "st": r.get("state", ""),
            "dm": dm,
            "di": r.get("discipline", "gravel"),
            "f": r.get("founded") or 0,
        }
        entries.append(entry)
    blob = json.dumps(entries, separators=(",", ":"))
    return f'<script type="application/json" id="gg-race-data">{blob}</script>'


def build_data_story(races: list[dict], editorial_facts: dict) -> str:
    """Build 4 focused data sections replacing the scrollytelling beeswarm.

    Each section: clear headline, one-liner insight, readable bar chart.
    All charts are HTML/CSS bars computed at build time — no client-side
    rendering needed, just IntersectionObserver for scroll-triggered entry.
    """
    total = len(races)

    # ── Tier Breakdown ──
    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in races:
        t = r.get("tier")
        if t in tier_counts:
            tier_counts[t] += 1
    max_tier_count = max(tier_counts.values()) or 1
    tier_labels = {1: "Tier 1", 2: "Tier 2", 3: "Tier 3", 4: "Tier 4"}
    tier_descs = {
        1: "Score &ge; 80. The real deal.",
        2: "Score 60&ndash;79. Seriously good.",
        3: "Score 45&ndash;59. Solid.",
        4: "Score &lt; 45. Developing.",
    }
    tier_bars = ""
    for t in [1, 2, 3, 4]:
        pct = round(tier_counts[t] / max_tier_count * 100)
        tier_bars += f'''        <div class="gg-ins-data-row">
          <span class="gg-ins-data-label">{tier_labels[t]}</span>
          <div class="gg-ins-data-bar">
            <div class="gg-ins-data-bar-fill" data-tier="{t}" style="width:{pct}%"></div>
          </div>
          <span class="gg-ins-data-count">{tier_counts[t]}</span>
          <span class="gg-ins-data-desc">{tier_descs[t]}</span>
        </div>\n'''

    tier_section = f'''<section id="tier-breakdown" class="gg-insights-section">
  <h2 class="gg-insights-section-title">The Gravel 1%</h2>
  <p class="gg-insights-narrative">{tier_counts[1]} of {total} races earn Tier 1. {tier_counts[3]} land in Tier 3. Scoring 80+ across 14 dimensions is hard. That is the point.</p>
  <div class="gg-ins-data-chart" data-animate="bars">
{tier_bars}  </div>
</section>'''

    # ── Regional Breakdown ──
    region_counts: dict[str, int] = defaultdict(int)
    region_scores: dict[str, list[float]] = defaultdict(list)
    for r in races:
        reg = r.get("region", "Other")
        if reg:
            region_counts[reg] += 1
            region_scores[reg].append(r.get("overall_score", 0))
    # Sort by count descending
    sorted_regions = sorted(region_counts.items(), key=lambda x: -x[1])
    max_region_count = sorted_regions[0][1] if sorted_regions else 1
    region_bars = ""
    for reg, count in sorted_regions:
        avg = round(mean(region_scores[reg])) if region_scores[reg] else 0
        pct = round(count / max_region_count * 100)
        region_bars += f'''        <div class="gg-ins-data-row">
          <span class="gg-ins-data-label">{esc(reg)}</span>
          <div class="gg-ins-data-bar">
            <div class="gg-ins-data-bar-fill gg-ins-data-bar-fill--teal" style="width:{pct}%"></div>
          </div>
          <span class="gg-ins-data-count">{count}</span>
          <span class="gg-ins-data-desc">Avg: {avg}</span>
        </div>\n'''

    qs = editorial_facts.get("quality_state", "CO")
    qs_avg = editorial_facts.get("quality_state_avg", 0)
    qs_count = editorial_facts.get("quality_state_count", 0)
    region_section = f'''<section id="geography" class="gg-insights-section gg-insights-section--alt">
  <h2 class="gg-insights-section-title">Geography Is Destiny</h2>
  <p class="gg-insights-narrative">{esc(qs)} averages {qs_avg:.0f} across {qs_count} races. Some states stack the deck. Others just stack the start line.</p>
  <div class="gg-ins-data-chart" data-animate="bars">
{region_bars}  </div>
</section>'''

    # ── Calendar ──
    month_counts = {m: 0 for m in MONTHS}
    for r in races:
        m = r.get("month", "")
        if m in month_counts:
            month_counts[m] += 1
    peak_month = max(month_counts, key=lambda m: month_counts[m])
    dead_month = min(month_counts, key=lambda m: month_counts[m])
    max_month_count = max(month_counts.values()) or 1
    month_abbr = {m: m[:3] for m in MONTHS}
    month_bars = ""
    for m in MONTHS:
        count = month_counts[m]
        pct = round(count / max_month_count * 100)
        is_peak = ' gg-ins-cal-peak' if m == peak_month else ''
        month_bars += f'''        <div class="gg-ins-cal-col{is_peak}">
          <div class="gg-ins-cal-bar-wrap">
            <div class="gg-ins-cal-bar" style="height:{pct}%"></div>
          </div>
          <span class="gg-ins-cal-count">{count}</span>
          <span class="gg-ins-cal-label">{month_abbr[m]}</span>
        </div>\n'''

    calendar_section = f'''<section id="calendar" class="gg-insights-section">
  <h2 class="gg-insights-section-title">The Calendar Crunch</h2>
  <p class="gg-insights-narrative">{esc(peak_month)}: {month_counts[peak_month]} races. {esc(dead_month)}: {month_counts[dead_month]}. Scheduling conflicts are a feature, not a bug.</p>
  <div class="gg-ins-cal-chart" data-animate="bars">
{month_bars}  </div>
</section>'''

    # ── Price Myth ──
    corr = editorial_facts.get("price_score_corr", 0.0)
    cb = editorial_facts.get("cheap_beat", {})
    cheapest_t1 = editorial_facts.get("cheapest_t1", {})
    priciest_t4 = editorial_facts.get("priciest_t4", {})

    price_detail = ""
    if cb:
        price_detail = (
            f' {esc(cb.get("cheap_name", ""))} costs '
            f'${int(cb.get("cheap_price", 0))} and outscores '
            f'{esc(cb.get("expensive_name", ""))}.'
        )

    callout_items = ""
    callout_items += f'''        <div class="gg-ins-price-stat">
          <span class="gg-ins-price-stat-value">{corr:.2f}</span>
          <span class="gg-ins-price-stat-label">Price-Score Correlation</span>
        </div>\n'''
    if cheapest_t1:
        callout_items += f'''        <div class="gg-ins-price-stat">
          <span class="gg-ins-price-stat-value">${int(cheapest_t1["price"])}</span>
          <span class="gg-ins-price-stat-label">Cheapest Tier 1 ({esc(cheapest_t1["name"])})</span>
        </div>\n'''
    if priciest_t4:
        callout_items += f'''        <div class="gg-ins-price-stat">
          <span class="gg-ins-price-stat-value">${int(priciest_t4["price"])}</span>
          <span class="gg-ins-price-stat-label">Priciest Tier 4 ({esc(priciest_t4["name"])})</span>
        </div>\n'''

    # Value outliers
    value_outliers = [
        r for r in races
        if r.get("overall_score", 0) >= 60
        and r.get("price") is not None
        and 0 < r["price"] <= 100
    ]
    value_count = len(value_outliers)
    callout_items += f'''        <div class="gg-ins-price-stat">
          <span class="gg-ins-price-stat-value">{value_count}</span>
          <span class="gg-ins-price-stat-label">Tier 2+ Races Under $100</span>
        </div>\n'''

    price_section = f'''<section id="price-myth" class="gg-insights-section gg-insights-section--alt">
  <h2 class="gg-insights-section-title">The Price Myth</h2>
  <p class="gg-insights-narrative">Registration fees predict logistics budgets, not race quality.{price_detail}</p>
  <div class="gg-ins-price-grid" data-animate="bars">
{callout_items}  </div>
</section>'''

    return f"{tier_section}\n\n{region_section}\n\n{calendar_section}\n\n{price_section}"


def build_dimension_leaderboard(races: list[dict]) -> str:
    """Section: Pick a dimension, see top 15 races as horizontal bars."""
    # Build dimension buttons
    buttons_html = ""
    for i, dim in enumerate(ALL_DIMS):
        active = ' gg-ins-dim-btn--active' if i == 0 else ''
        buttons_html += (
            f'      <button class="gg-ins-dim-btn{active}" '
            f'data-dim="{esc(dim)}">{esc(DIM_LABELS[dim])}</button>\n'
        )

    return f'''<section id="dimension-leaderboard">
  <figure class="gg-ins-figure">
    <div class="gg-ins-figure-title">Who Leads Where</div>
    <div class="gg-ins-figure-takeaway">Pick a dimension. See who scores highest across {len(races)} rated races.</div>
    <div class="gg-ins-dim-controls" role="tablist" aria-label="Select scoring dimension">
{buttons_html}    </div>
    <div class="gg-ins-dim-bars" id="dim-leaderboard" role="tabpanel" aria-live="polite">
    </div>
  </figure>
</section>'''


def build_ranking_builder(races: list[dict]) -> str:
    """Section: Custom ranking builder with weighted sliders."""
    slider_groups = [
        ("suffering", "Suffering", "technicality, elevation, altitude"),
        ("prestige", "Prestige", "prestige, field depth, race quality"),
        ("practicality", "Practicality", "logistics, climate, expenses"),
        ("adventure", "Adventure", "adventure, length"),
        ("community", "Community", "community, experience"),
        ("value", "Value", "value"),
    ]

    sliders_html = ""
    for gid, label, dims in slider_groups:
        sliders_html += f'''      <div class="gg-ins-rank-slider-group">
        <label class="gg-ins-rank-label" for="gg-ins-rank-{gid}">
          {esc(label)}
          <span class="gg-ins-rank-dims">{esc(dims)}</span>
        </label>
        <div class="gg-ins-rank-slider-row">
          <input type="range" id="gg-ins-rank-{gid}" class="gg-ins-rank-slider"
                 min="0" max="10" value="5" data-group="{esc(gid)}">
          <span class="gg-ins-rank-value" id="gg-ins-rank-{gid}-val">5</span>
        </div>
      </div>
'''

    # Initial leaderboard placeholder (populated by JS)
    entries_html = ""
    for i in range(10):
        entries_html += (
            f'      <div class="gg-ins-rank-entry" '
            f'data-rank="{i}"></div>\n'
        )

    return f'''<section id="ranking-builder" class="gg-ins-rank">
  <figure class="gg-ins-figure">
    <div class="gg-ins-figure-title">Your Gravel, Your Rules</div>
    <div class="gg-ins-figure-takeaway">Move the sliders. The ranking updates instantly.</div>
    <div class="gg-ins-rank-inner">
      <div class="gg-ins-rank-sliders">
{sliders_html}        <button id="gg-ins-rank-reset" class="gg-ins-rank-reset-btn">Reset to Gravel God Defaults</button>
      </div>
      <div id="gg-ins-rank-leaderboard" class="gg-ins-rank-leaderboard" aria-live="polite">
{entries_html}      </div>
    </div>
  </figure>
</section>'''


def build_heritage(races: list[dict], editorial_facts: dict = None) -> str:
    """Section 7: Timeline scatter of founding year vs overall score."""
    with_year = [(r, r["founded"]) for r in races if r.get("founded") and isinstance(r.get("founded"), int)]

    if not with_year:
        return ""

    years = [y for _, y in with_year]
    min_year = min(years)
    max_year = max(years)

    # Pre-2015 vs post-2018 averages
    pre_2015 = [r.get("overall_score", 0) for r, y in with_year if y < 2015]
    post_2018 = [r.get("overall_score", 0) for r, y in with_year if y >= 2018]
    pre_avg = mean(pre_2015) if pre_2015 else 0
    post_avg = mean(post_2018) if post_2018 else 0

    # SVG scatter
    chart_width = 600
    chart_height = 300
    margin = {"left": 45, "right": 20, "top": 20, "bottom": 35}
    plot_w = chart_width - margin["left"] - margin["right"]
    plot_h = chart_height - margin["top"] - margin["bottom"]

    yr_range = max(max_year - min_year, 1)

    def x_pos(year: int) -> float:
        return margin["left"] + ((year - min_year) / yr_range) * plot_w

    def y_pos(score: float) -> float:
        return margin["top"] + plot_h - (score / 100) * plot_h

    # Axis
    x_axis = f'    <line x1="{margin["left"]}" y1="{chart_height - margin["bottom"]}" x2="{chart_width - margin["right"]}" y2="{chart_height - margin["bottom"]}" style="stroke:var(--gg-color-tan);stroke-width:1;"/>\n'
    y_axis = f'    <line x1="{margin["left"]}" y1="{margin["top"]}" x2="{margin["left"]}" y2="{chart_height - margin["bottom"]}" style="stroke:var(--gg-color-tan);stroke-width:1;"/>\n'

    # Y ticks
    y_ticks = ""
    for score in range(0, 101, 20):
        yy = y_pos(score)
        y_ticks += f'    <text x="{margin["left"] - 6}" y="{yy + 3:.0f}" text-anchor="end" style="font-family:var(--gg-font-data);font-size:9px;fill:var(--gg-color-secondary-brown);">{score}</text>\n'
        y_ticks += f'    <line x1="{margin["left"]}" y1="{yy:.0f}" x2="{chart_width - margin["right"]}" y2="{yy:.0f}" style="stroke:var(--gg-color-sand);stroke-width:0.5;"/>\n'

    # X ticks
    x_ticks = ""
    step = 5 if yr_range > 20 else 2 if yr_range > 10 else 1
    yr = min_year - (min_year % step) + step
    while yr <= max_year:
        xx = x_pos(yr)
        x_ticks += f'    <text x="{xx:.0f}" y="{chart_height - margin["bottom"] + 14}" text-anchor="middle" style="font-family:var(--gg-font-data);font-size:9px;fill:var(--gg-color-secondary-brown);">{yr}</text>\n'
        yr += step

    # Dots
    dots = ""
    for r, yr in with_year:
        score = r.get("overall_score", 0)
        tier = r.get("tier", 3)
        px = x_pos(yr)
        py = y_pos(score)
        tip = f"{r['name']}: est. {yr}, score {score}"
        dots += f'    <rect x="{px - 3:.0f}" y="{py - 3:.0f}" width="6" height="6" style="fill:var(--gg-color-tier-{tier});" class="gg-insights-heritage-dot" data-name="{esc(r["name"])}" data-year="{yr}" data-tooltip="{esc(tip)}" tabindex="0"/>\n'

    # Average lines
    avg_lines = ""
    if pre_2015:
        py_pre = y_pos(pre_avg)
        avg_lines += f'    <line x1="{x_pos(min_year):.0f}" y1="{py_pre:.0f}" x2="{x_pos(2014):.0f}" y2="{py_pre:.0f}" style="stroke:var(--gg-color-teal);stroke-width:2;stroke-dasharray:6 3;"/>\n'
        avg_lines += f'    <text x="{x_pos(2014) + 4:.0f}" y="{py_pre - 4:.0f}" style="font-family:var(--gg-font-data);font-size:9px;fill:var(--gg-color-teal);">pre-2015 avg: {pre_avg:.1f}</text>\n'
    if post_2018:
        py_post = y_pos(post_avg)
        avg_lines += f'    <line x1="{x_pos(2018):.0f}" y1="{py_post:.0f}" x2="{x_pos(max_year):.0f}" y2="{py_post:.0f}" style="stroke:var(--gg-color-gold);stroke-width:2;stroke-dasharray:6 3;"/>\n'
        avg_lines += f'    <text x="{x_pos(max_year) + 4:.0f}" y="{py_post - 4:.0f}" style="font-family:var(--gg-font-data);font-size:9px;fill:var(--gg-color-gold);">post-2018 avg: {post_avg:.1f}</text>\n'

    ef = editorial_facts or {}
    yt1 = ef.get("youngest_t1", {})
    yt1_name = yt1.get("name", "")
    yt1_year = yt1.get("founded", 0)

    chart_svg = f'''  <div class="gg-insights-chart-wrap">
    <svg class="gg-insights-heritage-svg" viewBox="0 0 {chart_width} {chart_height}" role="img" aria-label="Timeline scatter plot showing founding year versus overall score for {len(with_year)} gravel races">
{x_axis}{y_axis}{y_ticks}{x_ticks}{dots}{avg_lines}
    </svg>
  </div>'''
    takeaway_text = "Heritage earns a premium, but it is not destiny"
    if yt1_name:
        takeaway_text = f"{esc(yt1_name)} (est. {yt1_year}) proves you do not need decades to reach the top"
    chart_figure = build_figure_wrap(chart_svg, "Founding Year vs. Score: Does Age Matter?", takeaway_text, "heritage-chart")

    return f'''<section class="gg-insights-section" id="heritage">
  <h2 class="gg-insights-section-title">The Heritage Premium</h2>
  <p class="gg-insights-narrative">Races founded before 2015 average {pre_avg:.1f}. Post-2018 races average {post_avg:.1f}. Heritage earns a premium &#8212; but {esc(yt1_name) if yt1_name else "several newer races"} proved you do not need decades to crack the top tier. A head start helps, but a great course, strong community, and smart logistics close the gap fast.</p>
  <p class="gg-insights-section-intro">Pre-2015 avg: {pre_avg:.1f}. Post-2018 avg: {post_avg:.1f}. Heritage matters, but execution matters more.</p>
  {chart_figure}
  <p class="gg-insights-narrative">The old guard earned its reputation, but the new guard is closing fast. Several post-2018 races have cracked Tier 1 through sheer quality of execution. In gravel, pedigree opens the door &#8212; but the course still has to deliver.</p>
</section>'''



def build_cta_block(
    heading: str,
    text: str,
    primary_href: str,
    primary_label: str,
    secondary_href: str | None = None,
    secondary_label: str | None = None,
    cta_id: str = "",
) -> str:
    """Build a reusable CTA block with optional secondary button."""
    secondary_html = ""
    if secondary_href and secondary_label:
        secondary_html = f'\n    <a href="{esc(secondary_href)}" class="gg-insights-cta-btn-secondary" data-cta="{esc(cta_id)}-secondary">{esc(secondary_label)}</a>'
    return f'''<div class="gg-insights-cta-block" id="cta-{esc(cta_id)}">
  <div class="gg-insights-cta-inner">
    <h3 class="gg-insights-cta-heading">{esc(heading)}</h3>
    <p class="gg-insights-cta-text">{esc(text)}</p>
    <div class="gg-insights-cta-buttons">
      <a href="{esc(primary_href)}" class="gg-insights-cta-btn-gold" data-cta="{esc(cta_id)}">{esc(primary_label)}</a>{secondary_html}
    </div>
  </div>
</div>'''


def build_closing(race_count: int) -> str:
    """Closing section — single CTA to explore races."""
    return f'''<section class="gg-insights-section" id="what-now">
  <h2 class="gg-insights-section-title">Now Go Race</h2>
  <p class="gg-insights-narrative">{race_count} races. 14 dimensions. The data is here. Use it.</p>
  <div class="gg-insights-closing-single">
    <a href="{SITE_BASE_URL}/races/" class="gg-insights-cta-btn-gold gg-insights-cta-btn-lg" data-cta="closing-explore">Explore All {race_count} Races</a>
  </div>
</section>'''


# ── CSS ────────────────────────────────────────────────────────


def build_insights_css() -> str:
    """Return all CSS for the insights page."""
    return f'''<style>
/* ── Insights Page ─────────────────────────────────────── */
{get_site_header_css()}

/* ── Hero ── */
.gg-insights-hero {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl) var(--gg-spacing-xl);
  background: var(--gg-color-warm-paper);
  border-bottom: 3px solid var(--gg-color-dark-brown);
}}
.gg-insights-hero-inner {{
  max-width: 960px;
  margin: 0 auto;
  text-align: center;
}}
.gg-insights-hero-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(32px, 6vw, 52px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
  line-height: 1.1;
}}
.gg-insights-hero-subtitle {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-xl) 0;
  max-width: 640px;
  margin-left: auto;
  margin-right: auto;
}}
.gg-insights-counters {{
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--gg-spacing-lg);
}}
.gg-insights-counter {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--gg-spacing-xs);
  min-width: 120px;
}}
.gg-insights-counter-value {{
  font-family: var(--gg-font-data);
  font-size: clamp(24px, 4vw, 36px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-insights-counter-label {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
}}

/* ── Sections ── */
.gg-insights-section {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  max-width: 960px;
  margin: 0 auto;
}}
.gg-insights-section--alt {{
  background: var(--gg-color-sand);
  max-width: none;
}}
.gg-insights-section--alt > * {{
  max-width: 960px;
  margin-left: auto;
  margin-right: auto;
}}
.gg-insights-section-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(24px, 4vw, 36px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-insights-section-intro {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-xl) 0;
  max-width: 640px;
}}

/* ── Chart Wrappers ── */
.gg-insights-chart-wrap {{
  width: 100%;
  overflow-x: auto;
  margin: 0 0 var(--gg-spacing-lg) 0;
}}
.gg-insights-chart-wrap svg {{
  display: block;
  max-width: 100%;
  height: auto;
}}

/* ── Editorial Narrative ── */
.gg-insights-narrative {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(15px, 2.5vw, 17px);
  line-height: 1.7;
  color: var(--gg-color-primary-brown);
  max-width: 680px;
  margin: 0 0 var(--gg-spacing-lg) 0;
}}

/* ── Figure Wrapper (legacy gg-insights- for heritage) ── */
.gg-insights-figure {{
  margin: 0 0 var(--gg-spacing-xl) 0;
}}
.gg-insights-figure-title {{
  font-family: var(--gg-font-editorial);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--gg-color-near-black);
  border-bottom: 3px solid var(--gg-color-gold);
  padding: 0 0 0.5rem 0;
  margin: 0 0 1rem 0;
}}
.gg-insights-figure-takeaway {{
  border-left: 4px solid var(--gg-color-teal);
  padding: 0.75rem 1rem;
  margin: 1.25rem 0 0 0;
  font-family: var(--gg-font-editorial);
  font-style: italic;
  font-size: 0.95rem;
  color: var(--gg-color-secondary-brown);
}}

/* ── Figure Wrapper (new gg-ins- for interactives) ── */
.gg-ins-figure {{
  margin: 0 0 var(--gg-spacing-xl) 0;
}}
.gg-ins-figure-title {{
  font-family: var(--gg-font-editorial);
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--gg-color-near-black);
  border-bottom: 3px solid var(--gg-color-gold);
  padding: 0 0 0.5rem 0;
  margin: 0 0 1rem 0;
}}
.gg-ins-figure-takeaway {{
  border-left: 4px solid var(--gg-color-teal);
  padding: 0.75rem 1rem;
  margin: 0 0 1.25rem 0;
  font-family: var(--gg-font-editorial);
  font-style: italic;
  font-size: 0.95rem;
  color: var(--gg-color-secondary-brown);
}}

/* ── Heritage ── */
/* ── CTA Blocks ── */
.gg-insights-cta-block {{
  max-width: 600px;
  margin: 0 auto;
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  text-align: center;
}}
.gg-insights-cta-inner {{
  max-width: 480px;
  margin: 0 auto;
}}
.gg-insights-cta-heading {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-insights-cta-text {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-lg) 0;
}}
.gg-insights-cta-buttons {{
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--gg-spacing-md);
}}
.gg-insights-cta-btn-gold {{
  display: inline-block;
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  text-decoration: none;
  color: var(--gg-color-warm-paper);
  background: var(--gg-color-gold);
  border: 3px solid var(--gg-color-dark-brown);
  transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover);
}}
.gg-insights-cta-btn-gold:hover {{
  background-color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-dark-brown);
}}
.gg-insights-cta-btn-gold:focus-visible {{
  outline: 3px solid var(--gg-color-teal);
  outline-offset: 2px;
}}
.gg-insights-cta-btn-secondary {{
  display: inline-block;
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  text-decoration: none;
  color: var(--gg-color-dark-brown);
  background: transparent;
  border: 3px solid var(--gg-color-dark-brown);
  transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover);
}}
.gg-insights-cta-btn-secondary:hover {{
  background-color: var(--gg-color-sand);
  border-color: var(--gg-color-teal);
}}
.gg-insights-cta-btn-secondary:focus-visible {{
  outline: 3px solid var(--gg-color-teal);
  outline-offset: 2px;
}}

/* ── Overrated / Underrated ── */
.gg-insights-ou-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-xl);
}}
.gg-insights-ou-group-title {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  font-weight: 700;
  color: var(--gg-color-dark-brown);
  border-bottom: 2px solid var(--gg-color-gold);
  padding: 0 0 var(--gg-spacing-xs) 0;
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-insights-ou-group-sub {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-secondary-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-insights-ou-card {{
  padding: var(--gg-spacing-md);
  background: var(--gg-color-warm-paper);
  border: 3px solid var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-insights-ou-card-tier {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
}}
.gg-insights-ou-card-name {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0;
}}
.gg-insights-ou-card-stats {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
}}
.gg-insights-ou-card-editorial {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  font-style: italic;
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: var(--gg-spacing-xs) 0 0 0;
}}

/* ── Closing / What Now ── */
.gg-insights-closing-single {{
  text-align: center;
  margin-top: var(--gg-spacing-xl);
}}
.gg-insights-cta-btn-lg {{
  display: inline-block;
  padding: var(--gg-spacing-md) var(--gg-spacing-2xl);
  font-size: var(--gg-font-size-md);
  letter-spacing: 3px;
}}

/* ══════════════════════════════════════════════════════════════
   DATA STORY — Horizontal Bars + Calendar + Price Stats
   ══════════════════════════════════════════════════════════════ */

/* ── Horizontal bar rows (tier + region) ── */
.gg-ins-data-chart {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-xs);
  max-width: 680px;
}}
.gg-ins-data-row {{
  display: grid;
  grid-template-columns: 64px 1fr 40px;
  gap: var(--gg-spacing-sm);
  align-items: center;
}}
.gg-ins-data-label {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  white-space: nowrap;
}}
.gg-ins-data-bar {{
  height: 24px;
  background: color-mix(in srgb, var(--gg-color-dark-brown) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--gg-color-dark-brown) 20%, transparent);
  position: relative;
  overflow: hidden;
}}
.gg-ins-data-bar-fill {{
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  transition: width 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}}
/* Bar fill widths start at 0 until parent gets .gg-in-view */
.gg-ins-data-bar-fill[data-tier="1"] {{ background: var(--gg-color-tier-1); }}
.gg-ins-data-bar-fill[data-tier="2"] {{ background: var(--gg-color-tier-2); }}
.gg-ins-data-bar-fill[data-tier="3"] {{ background: var(--gg-color-tier-3); }}
.gg-ins-data-bar-fill[data-tier="4"] {{ background: var(--gg-color-tier-4); }}
.gg-ins-data-bar-fill--teal {{ background: var(--gg-color-teal); }}
.gg-ins-data-count {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  text-align: right;
}}
.gg-ins-data-desc {{
  grid-column: 2 / -1;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  font-style: italic;
  margin-top: -4px;
  padding-bottom: var(--gg-spacing-xs);
  border-bottom: 1px solid color-mix(in srgb, var(--gg-color-dark-brown) 10%, transparent);
}}

/* ── Calendar (vertical bars) ── */
.gg-ins-cal-chart {{
  display: flex;
  align-items: flex-end;
  gap: var(--gg-spacing-xs);
  max-width: 680px;
  height: 200px;
  padding-top: var(--gg-spacing-md);
}}
.gg-ins-cal-col {{
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  height: 100%;
}}
.gg-ins-cal-bar-wrap {{
  flex: 1;
  width: 100%;
  display: flex;
  align-items: flex-end;
}}
.gg-ins-cal-bar {{
  width: 100%;
  background: var(--gg-color-teal);
  border: 1px solid var(--gg-color-dark-brown);
  transition: height 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94);
  min-height: 2px;
}}
.gg-ins-cal-peak .gg-ins-cal-bar {{
  background: var(--gg-color-gold);
}}
.gg-ins-cal-count {{
  font-family: var(--gg-font-data);
  font-size: 10px;
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
}}
.gg-ins-cal-label {{
  font-family: var(--gg-font-data);
  font-size: 10px;
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}

/* ── Price stat grid ── */
.gg-ins-price-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-md);
  max-width: 680px;
}}
.gg-ins-price-stat {{
  padding: var(--gg-spacing-md);
  background: var(--gg-color-warm-paper);
  border: 3px solid var(--gg-color-dark-brown);
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-xs);
}}
.gg-ins-price-stat-value {{
  font-family: var(--gg-font-data);
  font-size: clamp(24px, 4vw, 36px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-ins-price-stat-label {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  line-height: 1.4;
}}

/* ══════════════════════════════════════════════════════════════
   DIMENSION LEADERBOARD
   ══════════════════════════════════════════════════════════════ */
#dimension-leaderboard {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  max-width: 960px;
  margin: 0 auto;
}}
.gg-ins-dim-controls {{
  display: flex;
  flex-wrap: wrap;
  gap: var(--gg-spacing-xs);
  margin: 0 0 var(--gg-spacing-lg) 0;
}}
.gg-ins-dim-btn {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  padding: var(--gg-spacing-xs) var(--gg-spacing-sm);
  border: 2px solid var(--gg-color-dark-brown);
  background: transparent;
  color: var(--gg-color-dark-brown);
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover), color var(--gg-transition-hover);
}}
.gg-ins-dim-btn:hover {{
  border-color: var(--gg-color-teal);
}}
.gg-ins-dim-btn--active {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  border-color: var(--gg-color-dark-brown);
}}
.gg-ins-dim-btn:focus-visible {{
  outline: 3px solid var(--gg-color-teal);
  outline-offset: 2px;
}}
.gg-ins-dim-bars {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-xs);
}}
.gg-ins-dim-row {{
  display: grid;
  grid-template-columns: 24px 1fr 180px 40px 40px;
  gap: var(--gg-spacing-xs);
  align-items: center;
  padding: var(--gg-spacing-xs) 0;
  border-bottom: 1px solid color-mix(in srgb, var(--gg-color-dark-brown) 15%, transparent);
}}
.gg-ins-dim-rank {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-secondary-brown);
  text-align: right;
}}
.gg-ins-dim-name {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  text-decoration: none;
  transition: color var(--gg-transition-hover);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.gg-ins-dim-name:hover {{ color: var(--gg-color-teal); }}
.gg-ins-dim-bar {{
  height: 18px;
  background: color-mix(in srgb, var(--gg-color-dark-brown) 10%, transparent);
  position: relative;
}}
.gg-ins-dim-bar-fill {{
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  transition: width 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}}
.gg-ins-dim-bar-fill[data-tier="1"] {{ background: var(--gg-color-tier-1); }}
.gg-ins-dim-bar-fill[data-tier="2"] {{ background: var(--gg-color-tier-2); }}
.gg-ins-dim-bar-fill[data-tier="3"] {{ background: var(--gg-color-tier-3); }}
.gg-ins-dim-bar-fill[data-tier="4"] {{ background: var(--gg-color-tier-4); }}
.gg-ins-dim-score {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  text-align: center;
}}
.gg-ins-dim-tier {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  text-align: center;
}}

/* ── Expandable O/U Cards ── */
.gg-ins-ou-expand-hint {{
  display: block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-teal);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin-top: var(--gg-spacing-xs);
  cursor: pointer;
}}
.gg-insights-ou-card[aria-expanded="true"] .gg-ins-ou-expand-hint {{
  display: none;
}}
.gg-ins-ou-detail {{
  display: none;
  margin-top: var(--gg-spacing-sm);
  padding-top: var(--gg-spacing-sm);
  border-top: 1px solid color-mix(in srgb, var(--gg-color-dark-brown) 20%, transparent);
}}
.gg-insights-ou-card[aria-expanded="true"] .gg-ins-ou-detail {{
  display: block;
}}
.gg-ins-ou-dim {{
  display: grid;
  grid-template-columns: 100px 1fr 36px;
  gap: var(--gg-spacing-xs);
  align-items: center;
  margin-bottom: 4px;
}}
.gg-ins-ou-dim-label {{
  font-family: var(--gg-font-data);
  font-size: 10px;
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}}
.gg-ins-ou-dim-bar {{
  height: 12px;
  background: color-mix(in srgb, var(--gg-color-dark-brown) 10%, transparent);
  position: relative;
}}
.gg-ins-ou-dim-fill {{
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
}}
.gg-ins-ou-dim-fill[data-tier="1"] {{ background: var(--gg-color-tier-1); }}
.gg-ins-ou-dim-fill[data-tier="2"] {{ background: var(--gg-color-tier-2); }}
.gg-ins-ou-dim-fill[data-tier="3"] {{ background: var(--gg-color-tier-3); }}
.gg-ins-ou-dim-fill[data-tier="4"] {{ background: var(--gg-color-tier-4); }}
.gg-ins-ou-dim-val {{
  font-family: var(--gg-font-data);
  font-size: 10px;
  color: var(--gg-color-dark-brown);
  text-align: right;
}}
.gg-ins-ou-link {{
  display: inline-block;
  margin-top: var(--gg-spacing-sm);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-teal);
  text-decoration: none;
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  transition: color var(--gg-transition-hover);
}}
.gg-ins-ou-link:hover {{ color: var(--gg-color-dark-brown); }}
.gg-insights-ou-card {{
  cursor: pointer;
  transition: border-color var(--gg-transition-hover);
}}
.gg-insights-ou-card:hover {{ border-color: var(--gg-color-teal); }}

/* ══════════════════════════════════════════════════════════════
   RANKING BUILDER
   ══════════════════════════════════════════════════════════════ */
.gg-ins-rank {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  max-width: 960px;
  margin: 0 auto;
}}
.gg-ins-rank-inner {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-xl);
}}
.gg-ins-rank-sliders {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-md);
}}
.gg-ins-rank-slider-group {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-xs);
}}
.gg-ins-rank-label {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  display: flex;
  flex-direction: column;
  gap: 2px;
}}
.gg-ins-rank-dims {{
  font-size: var(--gg-font-size-2xs);
  font-weight: normal;
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-ins-rank-slider-row {{
  display: flex;
  align-items: center;
  gap: var(--gg-spacing-sm);
}}
.gg-ins-rank-slider {{
  flex: 1;
  -webkit-appearance: none;
  appearance: none;
  height: 4px;
  background: var(--gg-color-tan);
  border: 1px solid var(--gg-color-dark-brown);
  cursor: pointer;
}}
.gg-ins-rank-slider::-webkit-slider-thumb {{
  -webkit-appearance: none;
  appearance: none;
  width: 16px;
  height: 16px;
  background: var(--gg-color-dark-brown);
  border: 2px solid var(--gg-color-dark-brown);
  cursor: pointer;
}}
.gg-ins-rank-slider::-moz-range-thumb {{
  width: 16px;
  height: 16px;
  background: var(--gg-color-dark-brown);
  border: 2px solid var(--gg-color-dark-brown);
  cursor: pointer;
}}
.gg-ins-rank-slider:focus-visible {{
  outline: 3px solid var(--gg-color-teal);
  outline-offset: 2px;
}}
.gg-ins-rank-value {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  min-width: 24px;
  text-align: center;
}}
.gg-ins-rank-reset-btn {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  padding: var(--gg-spacing-xs) var(--gg-spacing-md);
  border: 2px solid var(--gg-color-dark-brown);
  background: transparent;
  color: var(--gg-color-dark-brown);
  cursor: pointer;
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin-top: var(--gg-spacing-sm);
  transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover);
}}
.gg-ins-rank-reset-btn:hover {{
  background-color: var(--gg-color-sand);
  border-color: var(--gg-color-teal);
}}
.gg-ins-rank-reset-btn:focus-visible {{
  outline: 3px solid var(--gg-color-teal);
  outline-offset: 2px;
}}
.gg-ins-rank-leaderboard {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-xs);
}}
.gg-ins-rank-entry {{
  display: flex;
  align-items: center;
  gap: var(--gg-spacing-sm);
  padding: var(--gg-spacing-xs) var(--gg-spacing-sm);
  border: 2px solid var(--gg-color-dark-brown);
  background: var(--gg-color-warm-paper);
  min-height: 36px;
}}
.gg-ins-rank-num {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-secondary-brown);
  min-width: 24px;
}}
.gg-ins-rank-name {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  text-decoration: none;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: color var(--gg-transition-hover);
}}
.gg-ins-rank-name:hover {{ color: var(--gg-color-teal); }}
.gg-ins-rank-bar {{
  flex: 0 0 80px;
  height: 8px;
  background: var(--gg-color-sand);
  border: 1px solid var(--gg-color-dark-brown);
}}
.gg-ins-rank-bar-fill {{
  height: 100%;
  background: var(--gg-color-teal);
  transition: width 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94);
}}
.gg-ins-rank-tier {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  padding: 2px 6px;
  border: 1px solid var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
}}
.gg-ins-rank-tier[data-tier="1"] {{ background: var(--gg-color-tier-1); }}
.gg-ins-rank-tier[data-tier="2"] {{ background: var(--gg-color-tier-2); }}
.gg-ins-rank-tier[data-tier="3"] {{ background: var(--gg-color-tier-3); }}
.gg-ins-rank-tier[data-tier="4"] {{ background: var(--gg-color-tier-4); }}

/* ── Tooltip ── */
.gg-insights-tooltip {{
  position: absolute;
  z-index: 1000;
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  border: 3px solid var(--gg-color-gold);
  padding: 8px 12px;
  font-family: var(--gg-font-data);
  font-size: 11px;
  line-height: 1.5;
  letter-spacing: 0.5px;
  max-width: 260px;
  pointer-events: none;
  display: none;
}}
.gg-insights-tooltip--visible {{
  display: block;
}}

/* ── Scroll Animations (.gg-has-js guard) ── */
.gg-has-js .gg-insights-figure {{
  visibility: hidden;
}}
.gg-has-js .gg-insights-figure.gg-in-view {{
  visibility: visible;
}}
.gg-has-js .gg-insights-ou-card {{
  transform: translateY(16px);
  transition: transform 0.4s cubic-bezier(0.25,0.46,0.45,0.94);
}}
.gg-in-view .gg-insights-ou-card {{
  transform: translateY(0);
}}

/* ── Breadcrumb ── */
.gg-insights-breadcrumb {{
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  max-width: 960px;
  margin: 0 auto;
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-insights-breadcrumb a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
  transition: color var(--gg-transition-hover);
}}
.gg-insights-breadcrumb a:hover {{ color: var(--gg-color-gold); }}
.gg-insights-breadcrumb-sep {{ margin: 0 var(--gg-spacing-xs); }}

/* ── Print ── */
@media print {{
  .gg-site-header,
  .gg-mega-footer,
  .gg-insights-breadcrumb,
  .gg-insights-cta-block {{ display: none; }}
  .gg-ins-dim-controls {{ display: none; }}
  .gg-ins-rank-sliders {{ display: none; }}
}}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {{
  .gg-ins-data-bar-fill {{ transition: none; }}
  .gg-ins-cal-bar {{ transition: none; }}
  .gg-ins-rank-bar-fill {{ transition: none; }}
  .gg-ins-dim-bar-fill {{ transition: none; }}
  .gg-insights-counter-value {{ transition: none; }}
  .gg-has-js .gg-insights-figure {{ visibility: visible; }}
  .gg-has-js .gg-insights-ou-card {{ transform: none; transition: none; }}
}}

/* ── Responsive: 900px ── */
@media (max-width: 900px) {{
  .gg-ins-rank-inner {{
    grid-template-columns: 1fr;
  }}
  .gg-insights-counters {{ gap: var(--gg-spacing-md); }}
  .gg-ins-dim-row {{ grid-template-columns: 24px 1fr 120px 36px 36px; }}
}}

/* ── Responsive: 600px ── */
@media (max-width: 600px) {{
  .gg-insights-hero {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-insights-section {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  #dimension-leaderboard {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-ins-rank {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-ins-dim-row {{ grid-template-columns: 24px 1fr 80px 32px 32px; }}
  .gg-insights-counters {{ flex-direction: column; align-items: center; }}
  .gg-insights-counter {{ min-width: auto; }}
  .gg-insights-cta-buttons {{ flex-direction: column; align-items: center; }}
  .gg-insights-ou-grid {{ grid-template-columns: 1fr; }}
  .gg-ins-ou-dim {{ grid-template-columns: 80px 1fr 32px; }}
  .gg-ins-price-grid {{ grid-template-columns: 1fr; }}
  .gg-ins-data-row {{ grid-template-columns: 56px 1fr 36px; }}
  .gg-ins-cal-chart {{ height: 150px; }}
}}

/* ── Responsive: 480px ── */
@media (max-width: 480px) {{
  .gg-insights-hero {{ padding: var(--gg-spacing-lg) var(--gg-spacing-sm); }}
  .gg-insights-section {{ padding: var(--gg-spacing-lg) var(--gg-spacing-sm); }}
  #dimension-leaderboard {{ padding: var(--gg-spacing-lg) var(--gg-spacing-sm); }}
  .gg-ins-rank {{ padding: var(--gg-spacing-lg) var(--gg-spacing-sm); }}
  .gg-ins-dim-row {{ grid-template-columns: 20px 1fr 60px 28px; }}
  .gg-ins-dim-tier {{ display: none; }}
  .gg-ins-cal-label {{ font-size: 8px; }}
  .gg-ins-cal-count {{ font-size: 8px; }}
}}
</style>'''



def build_insights_js() -> str:
    """Return all JS for the insights page — interactives + analytics."""
    return '''<script>
(function(){
  'use strict';

  /* ── .gg-has-js guard ── */
  document.documentElement.classList.add('gg-has-js');

  /* ── Reduced motion ── */
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Parse race data ── */
  var dataEl = document.getElementById('gg-race-data');
  var RACES = dataEl ? JSON.parse(dataEl.textContent) : [];

  var DIMS = ['logistics','length','technicality','elevation','climate','altitude',
    'adventure','prestige','race_quality','experience','community','field_depth','value','expenses'];

  var DIM_LABELS = {
    logistics:'Logistics', length:'Length', technicality:'Technicality',
    elevation:'Elevation', climate:'Climate', altitude:'Altitude',
    adventure:'Adventure', prestige:'Prestige', race_quality:'Race Quality',
    experience:'Experience', community:'Community', field_depth:'Field Depth',
    value:'Value', expenses:'Expenses',
    price:'Price ($)', distance_mi:'Distance (mi)', elevation_ft:'Elevation (ft)',
    overall_score:'Overall Score'
  };

  /* ══════════════════════════════════════════════════════════════
     DATA STORY — Scroll-triggered bar animations
     ══════════════════════════════════════════════════════════════ */

  /* Stash bar widths, zero them out, animate on scroll */
  var barCharts = document.querySelectorAll('[data-animate="bars"]');
  barCharts.forEach(function(chart) {
    var fills = chart.querySelectorAll('.gg-ins-data-bar-fill, .gg-ins-cal-bar');
    fills.forEach(function(fill) {
      var w = fill.style.width || '';
      var h = fill.style.height || '';
      if (w) { fill.setAttribute('data-target-w', w); fill.style.width = '0'; }
      if (h) { fill.setAttribute('data-target-h', h); fill.style.height = '0'; }
    });
  });
  if ('IntersectionObserver' in window && !reducedMotion) {
    var barObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          var fills = entry.target.querySelectorAll('[data-target-w], [data-target-h]');
          fills.forEach(function(fill) {
            var tw = fill.getAttribute('data-target-w');
            var th = fill.getAttribute('data-target-h');
            if (tw) fill.style.width = tw;
            if (th) fill.style.height = th;
          });
          barObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.2 });
    barCharts.forEach(function(chart) { barObserver.observe(chart); });
  } else {
    barCharts.forEach(function(chart) {
      var fills = chart.querySelectorAll('[data-target-w], [data-target-h]');
      fills.forEach(function(fill) {
        var tw = fill.getAttribute('data-target-w');
        var th = fill.getAttribute('data-target-h');
        if (tw) fill.style.width = tw;
        if (th) fill.style.height = th;
      });
    });
  }

  /* ══════════════════════════════════════════════════════════════
     DIMENSION LEADERBOARD
     ══════════════════════════════════════════════════════════════ */

  var dimLeaderboard = document.getElementById('dim-leaderboard');
  var dimBtns = document.querySelectorAll('.gg-ins-dim-btn');
  var SITE_URL = 'https://www.gravelgod.com';

  function getDimValue(race, dim) {
    var idx = DIMS.indexOf(dim);
    if (idx !== -1) return race.dm[idx] || 0;
    return 0;
  }

  function updateDimLeaderboard(dim) {
    if (!dimLeaderboard || !RACES.length) return;
    var scored = RACES.map(function(r, i) {
      return { idx: i, val: getDimValue(r, dim), name: r.n, slug: r.s, tier: r.t, score: r.sc };
    });
    scored.sort(function(a, b) { return b.val - a.val || b.score - a.score; });
    var top15 = scored.slice(0, 15);
    var html = '';
    top15.forEach(function(entry, i) {
      var pct = entry.val * 20;
      html += '<div class="gg-ins-dim-row">';
      html += '<span class="gg-ins-dim-rank">' + (i + 1) + '</span>';
      html += '<a class="gg-ins-dim-name" href="' + SITE_URL + '/race/' + entry.slug + '/">' + entry.name + '</a>';
      html += '<div class="gg-ins-dim-bar"><div class="gg-ins-dim-bar-fill" data-tier="' + entry.tier + '" style="width:' + pct + '%"></div></div>';
      html += '<span class="gg-ins-dim-score">' + entry.val + '/5</span>';
      html += '<span class="gg-ins-dim-tier" data-tier="' + entry.tier + '">T' + entry.tier + '</span>';
      html += '</div>';
    });
    dimLeaderboard.innerHTML = html;
    dimBtns.forEach(function(b) {
      b.classList.toggle('gg-ins-dim-btn--active', b.getAttribute('data-dim') === dim);
    });
    if (typeof gtag === 'function') {
      gtag('event', 'insights_dim_change', { dimension: dim });
    }
  }

  dimBtns.forEach(function(btn) {
    btn.addEventListener('click', function() {
      updateDimLeaderboard(btn.getAttribute('data-dim'));
    });
  });

  if (dimLeaderboard && RACES.length) updateDimLeaderboard('logistics');

  /* ══════════════════════════════════════════════════════════════
     EXPANDABLE O/U CARDS
     ══════════════════════════════════════════════════════════════ */

  document.querySelectorAll('.gg-insights-ou-card[aria-expanded]').forEach(function(card) {
    card.addEventListener('click', function() {
      var expanded = card.getAttribute('aria-expanded') === 'true';
      card.setAttribute('aria-expanded', !expanded);
      var detail = card.querySelector('.gg-ins-ou-detail');
      if (detail) detail.setAttribute('aria-hidden', expanded);
      if (typeof gtag === 'function') {
        gtag('event', 'insights_ou_expand', { race: card.querySelector('.gg-insights-ou-card-name').textContent });
      }
    });
    card.addEventListener('keydown', function(e) {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        card.click();
      }
    });
  });

  /* ══════════════════════════════════════════════════════════════
     RANKING BUILDER
     ══════════════════════════════════════════════════════════════ */

  var RANK_GROUPS = [
    { id: 'suffering', dims: ['technicality','elevation','altitude'] },
    { id: 'prestige', dims: ['prestige','field_depth','race_quality'] },
    { id: 'practicality', dims: ['logistics','climate','expenses'] },
    { id: 'adventure', dims: ['adventure','length'] },
    { id: 'community', dims: ['community','experience'] },
    { id: 'value', dims: ['value'] }
  ];

  var leaderboard = document.getElementById('gg-ins-rank-leaderboard');
  var resetBtn = document.getElementById('gg-ins-rank-reset');

  function getSliderWeights() {
    var weights = [];
    RANK_GROUPS.forEach(function(g) {
      var slider = document.getElementById('gg-ins-rank-' + g.id);
      weights.push(slider ? parseFloat(slider.value) : 5);
    });
    return weights;
  }

  function computeRanking(weights) {
    var scored = RACES.map(function(race, idx) {
      var total = 0;
      var maxPossible = 0;
      RANK_GROUPS.forEach(function(g, gi) {
        var w = weights[gi];
        g.dims.forEach(function(dim) {
          var di = DIMS.indexOf(dim);
          var val = di !== -1 ? (race.dm[di] || 0) : 0;
          total += val * w;
          maxPossible += 5 * w;
        });
      });
      var pct = maxPossible > 0 ? Math.round((total / maxPossible) * 100) : 0;
      return { idx: idx, score: pct, name: race.n, slug: race.s, tier: race.t };
    });
    scored.sort(function(a, b) { return b.score - a.score; });
    return scored.slice(0, 10);
  }

  function updateLeaderboard() {
    if (!leaderboard || !RACES.length) return;
    var weights = getSliderWeights();
    var top10 = computeRanking(weights);
    var html = '';
    top10.forEach(function(entry, i) {
      html += '<div class="gg-ins-rank-entry">';
      html += '<span class="gg-ins-rank-num">' + (i + 1) + '</span>';
      html += '<a class="gg-ins-rank-name" href="https://www.gravelgod.com/race/' + entry.slug + '/">' + entry.name + '</a>';
      html += '<div class="gg-ins-rank-bar"><div class="gg-ins-rank-bar-fill" style="width:' + entry.score + '%"></div></div>';
      html += '<span class="gg-ins-rank-tier" data-tier="' + entry.tier + '">T' + entry.tier + '</span>';
      html += '</div>';
    });
    leaderboard.innerHTML = html;
    var params = weights.join(',');
    try { history.replaceState(null, '', '?w=' + params); } catch(e) {}
    if (typeof gtag === 'function') {
      gtag('event', 'insights_rank_change', { weights: params });
    }
  }

  RANK_GROUPS.forEach(function(g) {
    var slider = document.getElementById('gg-ins-rank-' + g.id);
    var display = document.getElementById('gg-ins-rank-' + g.id + '-val');
    if (slider) {
      slider.addEventListener('input', function() {
        if (display) display.textContent = slider.value;
        updateLeaderboard();
      });
    }
  });

  if (resetBtn) {
    resetBtn.addEventListener('click', function() {
      RANK_GROUPS.forEach(function(g) {
        var slider = document.getElementById('gg-ins-rank-' + g.id);
        var display = document.getElementById('gg-ins-rank-' + g.id + '-val');
        if (slider) slider.value = '5';
        if (display) display.textContent = '5';
      });
      updateLeaderboard();
      if (typeof gtag === 'function') { gtag('event', 'insights_rank_reset'); }
    });
  }

  (function() {
    try {
      var params = new URLSearchParams(window.location.search);
      var w = params.get('w');
      if (w) {
        var parts = w.split(',');
        RANK_GROUPS.forEach(function(g, i) {
          var slider = document.getElementById('gg-ins-rank-' + g.id);
          var display = document.getElementById('gg-ins-rank-' + g.id + '-val');
          var val = parseFloat(parts[i]);
          if (!isNaN(val) && val >= 0 && val <= 10 && slider) {
            slider.value = val;
            if (display) display.textContent = val;
          }
        });
      }
    } catch(e) {}
    updateLeaderboard();
  })();

  /* ══════════════════════════════════════════════════════════════
     TOOLTIP
     ══════════════════════════════════════════════════════════════ */

  var tooltip = document.createElement('div');
  tooltip.className = 'gg-insights-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  document.body.appendChild(tooltip);

  function showTooltip(el, text) {
    tooltip.textContent = text;
    tooltip.classList.add('gg-insights-tooltip--visible');
    var rect = el.getBoundingClientRect();
    tooltip.style.left = (rect.left + window.scrollX + rect.width / 2) + 'px';
    tooltip.style.top = (rect.top + window.scrollY - tooltip.offsetHeight - 8) + 'px';
  }
  function hideTooltip() {
    tooltip.classList.remove('gg-insights-tooltip--visible');
  }

  document.addEventListener('mouseover', function(e) {
    var el = e.target.closest('[data-tooltip]');
    if (el) showTooltip(el, el.getAttribute('data-tooltip'));
  });
  document.addEventListener('mouseout', function(e) {
    if (e.target.closest('[data-tooltip]')) hideTooltip();
  });
  document.addEventListener('focusin', function(e) {
    var el = e.target.closest('[data-tooltip]');
    if (el) showTooltip(el, el.getAttribute('data-tooltip'));
  });
  document.addEventListener('focusout', function(e) {
    if (e.target.closest('[data-tooltip]')) hideTooltip();
  });

  /* ══════════════════════════════════════════════════════════════
     COUNTER ANIMATION
     ══════════════════════════════════════════════════════════════ */

  function animateCounter(el) {
    var raw = el.getAttribute('data-counter');
    if (!raw) return;
    var target = parseFloat(raw);
    if (isNaN(target) || target === 0 || reducedMotion) return;
    var isFloat = raw.indexOf('.') !== -1;
    var startTime = null;
    var duration = 1200;
    var original = el.textContent;
    function step(ts) {
      if (!startTime) startTime = ts;
      var progress = Math.min((ts - startTime) / duration, 1);
      var ease = 1 - Math.pow(1 - progress, 3);
      var current = ease * target;
      if (isFloat) {
        el.textContent = current.toFixed(1) + 'x';
      } else {
        el.textContent = Math.round(current).toLocaleString();
      }
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        el.textContent = original;
      }
    }
    requestAnimationFrame(step);
  }

  var counters = document.querySelectorAll('[data-counter]');
  if (counters.length && 'IntersectionObserver' in window) {
    var counterObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          counterObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.3 });
    counters.forEach(function(el) { counterObserver.observe(el); });
  }

  /* ── GA4: section view + scroll depth ── */
  var sectionsSeen = {};
  if ('IntersectionObserver' in window) {
    var sectionObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          var id = entry.target.id;
          if (id && !sectionsSeen[id] && typeof gtag === 'function') {
            sectionsSeen[id] = true;
            gtag('event', 'insights_section_view', { section: id });
          }
        }
      });
    }, { threshold: 0.2 });
    document.querySelectorAll('section[id]').forEach(function(s) { sectionObserver.observe(s); });
  }

  var depthMarks = [25, 50, 75, 100];
  var depthSent = {};
  window.addEventListener('scroll', function() {
    var scrollTop = window.scrollY || document.documentElement.scrollTop;
    var docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (docHeight <= 0) return;
    var pct = Math.round((scrollTop / docHeight) * 100);
    depthMarks.forEach(function(mark) {
      if (pct >= mark && !depthSent[mark]) {
        depthSent[mark] = true;
        if (typeof gtag === 'function') {
          gtag('event', 'insights_scroll_depth', { depth: mark });
        }
      }
    });
  }, { passive: true });

  /* ── Figure visibility animations ── */
  if ('IntersectionObserver' in window) {
    var figObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('gg-in-view');
          figObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15 });
    document.querySelectorAll('.gg-insights-figure').forEach(function(fig) {
      figObserver.observe(fig);
    });
  }

  /* ── CTA clicks ── */
  document.querySelectorAll('[data-cta]').forEach(function(el) {
    el.addEventListener('click', function() {
      if (typeof gtag === 'function') {
        gtag('event', 'insights_cta_click', { cta_name: el.getAttribute('data-cta') });
      }
    });
  });

  /* ── Page view ── */
  if (typeof gtag === 'function') { gtag('event', 'insights_page_view'); }
})();
</script>'''


def build_nav() -> str:
    """Build header + breadcrumb."""
    breadcrumb = f'''<div class="gg-insights-breadcrumb">
  <a href="{SITE_BASE_URL}/">Home</a>
  <span class="gg-insights-breadcrumb-sep">&rsaquo;</span>
  <a href="{SITE_BASE_URL}/articles/">Articles</a>
  <span class="gg-insights-breadcrumb-sep">&rsaquo;</span>
  <span>The State of Gravel</span>
</div>'''
    return get_site_header_html(active="articles") + breadcrumb


def build_jsonld(race_count: int = 0, state_count: int = 0) -> str:
    """Build JSON-LD structured data for the page."""
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "The State of Gravel Racing: {race_count} Races Analyzed",
  "description": "Original data analysis of {race_count} gravel races across {state_count} US states. Interactive data exploration of pricing, geography, scoring, and hidden gems in gravel cycling.",
  "author": {{
    "@type": "Organization",
    "name": "Gravel God Cycling",
    "url": "{SITE_BASE_URL}"
  }},
  "publisher": {{
    "@type": "Organization",
    "name": "Gravel God Cycling",
    "url": "{SITE_BASE_URL}"
  }},
  "datePublished": "2026-02-20",
  "url": "{SITE_BASE_URL}/insights/"
}}
</script>'''


def generate_insights_page(external_assets: dict = None) -> str:
    """Generate the complete insights page HTML."""
    canonical_url = f"{SITE_BASE_URL}/insights/"

    # Load and enrich data — gravel only (exclude bikepacking + MTB)
    all_races = load_race_index()
    all_races = enrich_races(all_races)
    races = [r for r in all_races if (r.get("discipline") or "gravel") == "gravel"]
    stats = compute_stats(races)

    # Compute editorial facts for data-driven narratives
    editorial_facts = compute_editorial_facts(races)

    # Build sections
    nav = build_nav()
    hero = build_hero(stats)
    race_data_embed = build_race_data_embed(races)
    data_story = build_data_story(races, editorial_facts)
    race_count = len(races)
    state_count = stats["states_with_races"]
    dimension_leaderboard = build_dimension_leaderboard(races)
    ranking_builder = build_ranking_builder(races)
    overrated_underrated = build_overrated_underrated(races, editorial_facts)
    closing = build_closing(race_count)
    footer = get_mega_footer_html()
    insights_css = build_insights_css()
    insights_js = build_insights_js()
    jsonld = build_jsonld(race_count=race_count, state_count=state_count)

    if external_assets:
        page_css = external_assets['css_tag']
    else:
        page_css = get_page_css()

    meta_desc = f"Original data analysis of {race_count} gravel races across {state_count} US states. Interactive data exploration of pricing, geography, scoring, and hidden gems in gravel cycling."

    og_tags = f'''<meta property="og:title" content="The State of Gravel Racing: {race_count} Races Analyzed | Gravel God">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="The State of Gravel Racing | Gravel God">
  <meta name="twitter:description" content="{esc(meta_desc)}">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>The State of Gravel Racing: {race_count} Races Analyzed | Gravel God</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {insights_css}
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
  {get_ab_head_snippet()}
</head>
<body>

<a href="#hero" class="gg-skip-link">Skip to content</a>

<div class="gg-neo-brutalist-page">
  {nav}

  {hero}

  {race_data_embed}

  {data_story}

  {dimension_leaderboard}

  {ranking_builder}

  {overrated_underrated}

  {closing}

  {footer}
</div>

{insights_js}

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God insights page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)

    html_content = generate_insights_page(external_assets=assets)
    output_file = output_dir / "insights.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
