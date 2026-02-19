#!/usr/bin/env python3
"""
Generate state/region hub pages for SEO.

Creates /race/best-gravel-races-{state-slug}/index.html for every state or
country with 3+ races. Targets queries like "best gravel races in Colorado",
"gravel races Michigan", "gravel cycling California".

Each page includes:
  - Race cards sorted by score
  - Mini SVG map with dots (US states use US outline, others show dot cluster)
  - Monthly calendar breakdown
  - Training plan CTA
  - JSON-LD (CollectionPage + BreadcrumbList + FAQPage + ItemList)

Usage:
    python wordpress/generate_state_hubs.py
    python wordpress/generate_state_hubs.py --output-dir /tmp/gg-state-test
"""

import argparse
import html as html_mod
import json
import math
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import COLORS, GA_MEASUREMENT_ID, RACER_RATING_THRESHOLD, SITE_BASE_URL, get_font_face_css, get_tokens_css
from shared_header import get_site_header_css, get_site_header_html

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURRENT_YEAR = date.today().year
MIN_RACES = 3

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}
TIER_COLORS = {
    1: COLORS["primary_brown"],
    2: COLORS["secondary_brown"],
    3: COLORS["warm_brown"],
    4: "#5e6868",
}

# US state abbreviation → full name
STATE_ABBR = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}

US_STATES = set(STATE_ABBR.values())

MONTH_ORDER = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def _slugify(name: str) -> str:
    """Convert state/country name to URL slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ── Grouping logic ───────────────────────────────────────────────

def group_races_by_state(races: list) -> dict:
    """Group races by state/country from location field."""
    state_races = defaultdict(list)
    for r in races:
        loc = r.get("location", "")
        parts = [p.strip() for p in loc.split(",")]
        if len(parts) >= 2:
            state = parts[-1]
            # Normalize abbreviations
            if state in STATE_ABBR:
                state = STATE_ABBR[state]
            state_races[state].append(r)
    # Filter to MIN_RACES+ and sort races by score
    return {
        s: sorted(rs, key=lambda x: -x.get("overall_score", 0))
        for s, rs in state_races.items()
        if len(rs) >= MIN_RACES
    }


# ── SVG map builder ─────────────────────────────────────────────

def build_dot_map_svg(races: list) -> str:
    """Simple dot map showing race locations."""
    lats = [r.get("lat", 0) for r in races if r.get("lat")]
    lngs = [r.get("lng", 0) for r in races if r.get("lng")]
    if len(lats) < 2:
        return ""

    # Compute bounding box with padding
    min_lat, max_lat = min(lats) - 1, max(lats) + 1
    min_lng, max_lng = min(lngs) - 1, max(lngs) + 1

    # Avoid zero range
    if max_lat - min_lat < 2:
        min_lat -= 1
        max_lat += 1
    if max_lng - min_lng < 2:
        min_lng -= 1
        max_lng += 1

    vw, vh = 500, 300
    padding = 40

    def project(lat, lng):
        x = padding + (lng - min_lng) / (max_lng - min_lng) * (vw - 2 * padding)
        y = padding + (max_lat - lat) / (max_lat - min_lat) * (vh - 2 * padding)
        return x, y

    parts = [f'<svg viewBox="0 0 {vw} {vh}" class="gg-state-map-svg" role="img" '
             f'aria-label="Map showing race locations">']

    # Background
    parts.append(f'  <rect width="{vw}" height="{vh}" fill="{COLORS["sand"]}" rx="0"/>')

    # Plot dots with labels
    placed_labels = []
    for r in races:
        lat = r.get("lat")
        lng = r.get("lng")
        if not lat or not lng:
            continue
        x, y = project(lat, lng)
        tier = r.get("tier", 3)
        color = TIER_COLORS.get(tier, COLORS["warm_brown"])
        radius = 7 if tier <= 2 else 5

        parts.append(f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="{color}" opacity="0.85">'
                     f'<title>{esc(r["name"])} — T{tier} ({r.get("overall_score",0)})</title></circle>')

        # Label (avoid collision)
        label = r["name"][:20]
        ly = y - 12
        for px, py in placed_labels:
            if abs(x - px) < 80 and abs(ly - py) < 12:
                ly -= 14
        placed_labels.append((x, ly))
        parts.append(f'  <text x="{x:.1f}" y="{ly:.1f}" text-anchor="middle" '
                     f'font-family="Sometype Mono,monospace" font-size="8" '
                     f'fill="{COLORS["dark_brown"]}">{esc(label)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


# ── Monthly breakdown ────────────────────────────────────────────

def build_monthly_breakdown(races: list) -> str:
    """Group races by month in a compact list."""
    by_month = defaultdict(list)
    for r in races:
        month = r.get("month", "TBD")
        by_month[month].append(r)

    if not by_month:
        return ""

    months_sorted = sorted(by_month.keys(), key=lambda m: MONTH_ORDER.get(m, 13))

    rows = []
    for month in months_sorted:
        month_races = sorted(by_month[month], key=lambda x: -x.get("overall_score", 0))
        race_links = ", ".join(
            f'<a href="/race/{esc(r["slug"])}/">{esc(r["name"][:30])}</a>'
            for r in month_races
        )
        rows.append(f'<tr><td class="gg-state-month">{esc(month)}</td>'
                     f'<td class="gg-state-month-count">{len(month_races)}</td>'
                     f'<td class="gg-state-month-races">{race_links}</td></tr>')

    return f'''<table class="gg-state-calendar">
  <thead><tr><th>Month</th><th>#</th><th>Races</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>'''


# ── Race cards ───────────────────────────────────────────────────

def build_race_cards(races: list) -> str:
    """Race card list sorted by score."""
    cards = []
    for r in races:
        score = r.get("overall_score", 0)
        tier = r.get("tier", 3)
        tier_color = TIER_COLORS.get(tier, COLORS["warm_brown"])
        slug = r.get("slug", "")
        name = r.get("name", "")
        location = r.get("location", "")
        tagline = r.get("tagline", "")
        distance = r.get("distance_mi")
        elevation = r.get("elevation_ft")
        month = r.get("month", "")

        stat_parts = []
        if distance:
            stat_parts.append(f"{distance} mi")
        if elevation:
            try:
                stat_parts.append(f"{int(elevation):,} ft")
            except (ValueError, TypeError):
                stat_parts.append(f"{elevation} ft")
        if month:
            stat_parts.append(month)
        stats = " · ".join(stat_parts)

        # Racer rating — show pct if available, otherwise CTA
        rr_pct = r.get("racer_pct")
        rr_total = r.get("racer_total", 0)
        if rr_pct is not None and rr_total >= RACER_RATING_THRESHOLD:
            racer_html = f'''<div class="gg-state-card-racer">
  <div class="gg-state-card-racer-num" style="color:{COLORS["teal"]}">{rr_pct}%</div>
  <div class="gg-state-card-racer-label">{rr_total} RATINGS</div>
</div>'''
        else:
            racer_html = f'''<div class="gg-state-card-racer gg-state-card-racer--empty">
  <div class="gg-state-card-racer-num">&mdash;</div>
  <div class="gg-state-card-racer-label">NO RATINGS</div>
</div>'''

        cards.append(f'''<a href="/race/{esc(slug)}/" class="gg-state-card">
  <div class="gg-state-card-scores">
    <div class="gg-state-card-gg">
      <div class="gg-state-card-score" style="color:{tier_color}">{score}</div>
      <div class="gg-state-card-score-label">GG</div>
    </div>
    {racer_html}
  </div>
  <div class="gg-state-card-body">
    <div class="gg-state-card-tier" style="border-color:{tier_color}">T{tier} {esc(TIER_NAMES.get(tier,""))}</div>
    <div class="gg-state-card-name">{esc(name)}</div>
    <div class="gg-state-card-location">{esc(location)}</div>
    <div class="gg-state-card-stats">{esc(stats)}</div>
  </div>
</a>''')

    return "\n".join(cards)


# ── FAQ ──────────────────────────────────────────────────────────

def build_faq(state: str, races: list) -> tuple:
    """Build FAQ HTML + JSON-LD. Returns (html, jsonld)."""
    total = len(races)
    t1 = [r for r in races if r.get("tier") == 1]
    t2 = [r for r in races if r.get("tier") == 2]
    top = races[0] if races else None

    pairs = []

    # Q1: How many gravel races are in {state}?
    pairs.append((
        f"How many gravel races are in {state}?",
        f"We track {total} gravel races in {state}, including "
        f"{len(t1)} Elite (Tier 1) and {len(t2)} Contender (Tier 2) events. "
        f"See the full list above, ranked by our 14-dimension Gravel God Rating."
    ))

    # Q2: What is the best gravel race in {state}?
    if top:
        pairs.append((
            f"What is the best gravel race in {state}?",
            f"{top['name']} is the highest-rated gravel race in {state} with a "
            f"Gravel God score of {top.get('overall_score',0)}/100. "
            f"Located in {top.get('location','')}, it takes place in {top.get('month','')}."
        ))

    # Q3: When is gravel season in {state}?
    months = sorted(set(r.get("month", "") for r in races if r.get("month")),
                    key=lambda m: MONTH_ORDER.get(m, 13))
    if months:
        pairs.append((
            f"When is gravel racing season in {state}?",
            f"Gravel races in {state} run from {months[0]} through {months[-1]}. "
            f"Peak months include {', '.join(months[1:4])}." if len(months) > 3 else
            f"Gravel races in {state} take place in {', '.join(months)}."
        ))

    # Q4: Are there beginner-friendly gravel races?
    easy = [r for r in races if r.get("scores", {}).get("technicality", 3) <= 2
            and r.get("scores", {}).get("length", 3) <= 2]
    if easy:
        names = ", ".join(r["name"] for r in easy[:3])
        pairs.append((
            f"Are there beginner-friendly gravel races in {state}?",
            f"Yes! {names} {'are' if len(easy[:3]) > 1 else 'is'} among the most accessible "
            f"gravel races in {state}, with lower technicality and shorter distances."
        ))

    # Build HTML
    details = []
    for q, a in pairs:
        details.append(
            f'<details class="gg-state-faq-item"><summary>{esc(q)}</summary>'
            f'<p>{esc(a)}</p></details>'
        )
    faq_html = f'''<section class="gg-state-faq">
  <h2>Frequently Asked Questions</h2>
  {"".join(details)}
</section>'''

    # JSON-LD
    faq_entities = [
        {
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {"@type": "Answer", "text": a},
        }
        for q, a in pairs
    ]
    faq_jsonld = json.dumps(
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faq_entities},
        ensure_ascii=False, indent=2,
    )
    return faq_html, faq_jsonld


# ── Page assembly ────────────────────────────────────────────────

def build_state_page(state: str, races: list, total_races: int) -> str:
    """Generate a complete state hub page."""
    slug = _slugify(state)
    page_slug = f"best-gravel-races-{slug}"
    canonical = f"{SITE_BASE_URL}/race/{page_slug}/"

    is_us_state = state in US_STATES
    region_type = "state" if is_us_state else "country"

    t1_count = sum(1 for r in races if r.get("tier") == 1)
    t2_count = sum(1 for r in races if r.get("tier") == 2)

    title = f"Best Gravel Races in {state} ({CURRENT_YEAR}) | Gravel God"
    description = (
        f"All {len(races)} gravel races in {state}, ranked by our 14-dimension Gravel God Rating. "
        f"{'Including ' + str(t1_count) + ' Elite and ' + str(t2_count) + ' Contender events. ' if t1_count or t2_count else ''}"
        f"Find your next gravel race in {state}."
    )

    # Build sections
    map_svg = build_dot_map_svg(races)
    cards_html = build_race_cards(races)
    calendar_html = build_monthly_breakdown(races)
    faq_html, faq_jsonld = build_faq(state, races)

    font_face = get_font_face_css()
    tokens = get_tokens_css()

    # JSON-LD
    breadcrumb_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Gravel Races", "item": f"{SITE_BASE_URL}/gravel-races/"},
            {"@type": "ListItem", "position": 3, "name": f"Best in {state}", "item": canonical},
        ],
    }, ensure_ascii=False, indent=2)

    item_list_entries = []
    for i, r in enumerate(races, 1):
        item_list_entries.append({
            "@type": "ListItem",
            "position": i,
            "name": r.get("name", ""),
            "url": f"{SITE_BASE_URL}/race/{r.get('slug', '')}/",
        })
    item_list_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": f"Best Gravel Races in {state}",
        "numberOfItems": len(races),
        "itemListOrder": "https://schema.org/ItemListOrderDescending",
        "itemListElement": item_list_entries,
    }, ensure_ascii=False, indent=2)

    # Intro text
    if t1_count:
        intro = (
            f"{state} is home to {len(races)} gravel races in our database, "
            f"including {t1_count} Elite-tier events that rank among the best in the world. "
            f"Whether you're chasing a bucket-list finish or exploring new gravel, "
            f"{state} has a race for every rider."
        )
    elif t2_count:
        intro = (
            f"With {len(races)} gravel races tracked, {state} offers a deep bench of "
            f"quality events — including {t2_count} Contender-tier races with strong reputations "
            f"and competitive fields. Here's every gravel race in {state}, ranked."
        )
    else:
        intro = (
            f"{state} has {len(races)} gravel races in our database, from grassroots events "
            f"to regional favorites. Explore the full list below, ranked by our "
            f"14-dimension Gravel God Rating."
        )

    map_section = f'''<div class="gg-state-map">{map_svg}</div>''' if map_svg else ""

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%233a2e25'/><text x='16' y='24' text-anchor='middle' font-family='serif' font-size='24' font-weight='700' fill='%239a7e0a'>G</text></svg>">
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <script type="application/ld+json">
  {breadcrumb_jsonld}
  </script>
  <script type="application/ld+json">
  {item_list_jsonld}
  </script>
  <script type="application/ld+json">
  {faq_jsonld}
  </script>
  <style>
{font_face}
{tokens}

body {{ margin: 0; background: var(--gg-color-warm-paper); }}
*, *::before, *::after {{ border-radius: 0 !important; box-shadow: none !important; }}

.gg-state-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
}}

{get_site_header_css()}

/* Breadcrumb */
.gg-state-breadcrumb {{ font-size: 11px; color: var(--gg-color-secondary-brown); padding: 12px 0; letter-spacing: 0.5px; }}
.gg-state-breadcrumb a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}
.gg-state-breadcrumb a:hover {{ color: var(--gg-color-dark-brown); }}

/* Hero */
.gg-state-hero {{
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-dark-brown);
  padding: 48px 32px;
  margin: 0 -24px;
  border-bottom: 2px solid var(--gg-color-gold);
}}
.gg-state-hero h1 {{
  font-family: var(--gg-font-editorial);
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
  margin: 0 0 12px;
  color: var(--gg-color-dark-brown);
}}
.gg-state-hero-count {{
  font-size: 13px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-state-intro {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  line-height: 1.7;
  max-width: 720px;
  padding: 24px 0;
  border-bottom: 2px solid var(--gg-color-sand);
}}

/* Section headings */
.gg-state-page h2 {{
  font-family: var(--gg-font-editorial);
  font-size: 22px;
  font-weight: 700;
  margin: 40px 0 16px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--gg-color-gold);
}}

/* Map */
.gg-state-map {{ margin: 24px 0; text-align: center; }}
.gg-state-map-svg {{ max-width: 600px; width: 100%; height: auto; }}

/* Cards — RT-style with prominent score */
.gg-state-grid {{ display: flex; flex-direction: column; gap: 0; }}
.gg-state-card {{
  display: flex;
  align-items: stretch;
  border-bottom: 1px solid var(--gg-color-tan);
  text-decoration: none;
  color: inherit;
  transition: background 0.15s, border-color 0.15s;
}}
.gg-state-card:first-child {{ border-top: 1px solid var(--gg-color-tan); }}
.gg-state-card:hover {{ background: var(--gg-color-sand); border-color: var(--gg-color-gold); }}
.gg-state-card-scores {{
  display: flex;
  align-items: stretch;
  border-right: 1px solid var(--gg-color-tan);
}}
.gg-state-card-gg, .gg-state-card-racer {{
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-width: 56px;
  padding: 12px 8px;
}}
.gg-state-card-racer {{
  border-left: 1px solid var(--gg-color-tan);
}}
.gg-state-card-racer--empty {{ opacity: 0.45; }}
.gg-state-card:hover .gg-state-card-racer--empty {{ opacity: 0.7; }}
.gg-state-card-score {{
  font-family: var(--gg-font-editorial);
  font-size: 26px;
  font-weight: 700;
  line-height: 1;
}}
.gg-state-card-score-label {{
  font-family: var(--gg-font-data);
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 2px;
  color: var(--gg-color-warm-brown);
  margin-top: 3px;
}}
.gg-state-card-racer-num {{
  font-family: var(--gg-font-editorial);
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
}}
.gg-state-card-racer-label {{
  font-family: var(--gg-font-data);
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: var(--gg-color-warm-brown);
  margin-top: 3px;
  text-transform: uppercase;
}}
.gg-state-card-body {{
  flex: 1;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}}
.gg-state-card-tier {{
  display: inline-block;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 1px 6px;
  border: 1px solid;
  margin-bottom: 4px;
}}
.gg-state-card-name {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 2px;
  color: var(--gg-color-dark-brown);
}}
.gg-state-card-location {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 0;
}}
.gg-state-card-stats {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  margin-top: 6px;
  letter-spacing: 0.5px;
}}

/* Calendar */
.gg-state-calendar {{
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
}}
.gg-state-calendar th {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid var(--gg-color-gold);
  color: var(--gg-color-secondary-brown);
}}
.gg-state-month {{
  font-weight: 700;
  font-size: 12px;
  padding: 8px 6px;
  border-bottom: 1px solid var(--gg-color-sand);
  width: 90px;
}}
.gg-state-month-count {{
  font-size: 12px;
  padding: 8px 6px;
  border-bottom: 1px solid var(--gg-color-sand);
  width: 30px;
  text-align: center;
  color: var(--gg-color-secondary-brown);
}}
.gg-state-month-races {{
  font-size: 12px;
  padding: 8px 6px;
  border-bottom: 1px solid var(--gg-color-sand);
}}
.gg-state-month-races a {{
  color: var(--gg-color-teal);
  text-decoration: none;
}}
.gg-state-month-races a:hover {{ text-decoration: underline; }}

/* FAQ */
.gg-state-faq {{ margin: 32px 0; }}
.gg-state-faq-item {{ border-bottom: 1px solid var(--gg-color-sand); padding: 12px 0; }}
.gg-state-faq-item summary {{
  font-family: var(--gg-font-editorial);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}}
.gg-state-faq-item summary:hover {{ color: var(--gg-color-teal); }}
.gg-state-faq-item p {{
  font-size: 14px;
  line-height: 1.7;
  margin: 8px 0 0;
  color: var(--gg-color-secondary-brown);
}}

/* CTA */
.gg-state-cta {{
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-dark-brown);
  padding: 32px;
  margin: 32px -24px;
  text-align: center;
  border-top: 2px solid var(--gg-color-gold);
  border-bottom: 2px solid var(--gg-color-gold);
}}
.gg-state-cta h2 {{ color: var(--gg-color-dark-brown); border-bottom-color: var(--gg-color-gold); margin-top: 0; }}
.gg-state-cta p {{ font-size: 14px; line-height: 1.6; color: var(--gg-color-secondary-brown); }}
.gg-state-cta-btn {{
  display: inline-block;
  padding: 12px 28px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  text-decoration: none;
  border: 2px solid var(--gg-color-gold);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-gold);
  margin-top: 12px;
  transition: all 0.2s;
}}
.gg-state-cta-btn:hover {{ background: var(--gg-color-light-gold); border-color: var(--gg-color-light-gold); }}

/* Footer */
.gg-state-footer {{
  padding: 24px 0;
  margin-top: 32px;
  border-top: 2px solid var(--gg-color-gold);
  text-align: center;
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-state-footer a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}
.gg-state-footer a:hover {{ color: var(--gg-color-dark-brown); }}

/* Mobile */
@media (max-width: 768px) {{
  .gg-state-hero {{ padding: 32px 20px; }}
  .gg-state-hero h1 {{ font-size: 26px; }}
  .gg-state-cta {{ padding: 24px 16px; }}
}}
@media (max-width: 480px) {{
  .gg-state-page {{ padding: 0 12px; }}
  .gg-state-hero {{ padding: 24px 12px; margin: 0 -12px; }}
  .gg-state-hero h1 {{ font-size: 22px; }}
  .gg-state-card-gg, .gg-state-card-racer {{ min-width: 42px; padding: 10px 6px; }}
  .gg-state-card-score {{ font-size: 18px; }}
  .gg-state-card-racer-num {{ font-size: 14px; }}
  .gg-state-card-body {{ padding: 10px 12px; }}
  .gg-state-card-name {{ font-size: 14px; }}
  .gg-state-cta {{ margin: 32px -12px; }}
}}
  </style>
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
</head>
<body>

<div class="gg-state-page">

  {get_site_header_html(active="races")}

  <div class="gg-state-breadcrumb">
    <a href="/">Home</a> &rsaquo; <a href="/gravel-races/">Gravel Races</a> &rsaquo; {esc(state)}
  </div>

  <section class="gg-state-hero">
    <h1>Best Gravel Races in {esc(state)}</h1>
    <div class="gg-state-hero-count">{len(races)} races &middot; Ranked by Gravel God Rating</div>
  </section>

  <p class="gg-state-intro">{esc(intro)}</p>

  {map_section}

  <h2>All {len(races)} Gravel Races in {esc(state)}</h2>
  <div class="gg-state-grid">
    {cards_html}
  </div>

  <h2>Race Calendar</h2>
  {calendar_html}

  {faq_html}

  <section class="gg-state-cta">
    <h2>Racing in {esc(state)}?</h2>
    <p>Get a personalized training plan for any {esc(state)} gravel race — tailored to your fitness, schedule, and goals.</p>
    <a href="/training-plans/" class="gg-state-cta-btn">Build My Plan</a>
    <p style="font-size:11px;color:var(--gg-color-tan);margin-top:8px">$15/week, capped at $249. Cancel anytime.</p>
  </section>

  <footer class="gg-state-footer">
    <a href="/">Gravel God</a> &middot; {total_races} races rated &middot;
    <a href="/gravel-races/">Search All</a> &middot;
    <a href="/race/methodology/">Methodology</a>
  </footer>

</div>

</body>
</html>'''


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate state/region hub pages")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "wordpress" / "output"

    index_path = PROJECT_ROOT / "web" / "race-index.json"
    if not index_path.exists():
        print("ERROR: web/race-index.json not found.", file=sys.stderr)
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        all_races = json.load(f)
    print(f"Loaded {len(all_races)} races from index")

    state_groups = group_races_by_state(all_races)
    print(f"Found {len(state_groups)} states/countries with {MIN_RACES}+ races")

    generated = 0
    for state, races in sorted(state_groups.items(), key=lambda x: -len(x[1])):
        slug = _slugify(state)
        page_slug = f"best-gravel-races-{slug}"
        page_dir = output_dir / page_slug
        page_dir.mkdir(parents=True, exist_ok=True)

        page_html = build_state_page(state, races, len(all_races))
        out_path = page_dir / "index.html"
        out_path.write_text(page_html, encoding="utf-8")
        generated += 1
        print(f"  {page_slug}/ ({len(races)} races)")

    print(f"\nDone. {generated} state hub pages generated in {output_dir}/")


if __name__ == "__main__":
    main()
