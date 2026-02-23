#!/usr/bin/env python3
"""
Generate head-to-head "vs" comparison pages for SEO.

Creates /race/{slug1}-vs-{slug2}/index.html for strategically selected race
pairs. Targets queries like "Unbound vs SBT GRVL", "BWR vs Grinduro",
"Tour Divide vs Colorado Trail Race".

Each page includes:
  - Overlaid radar chart (7 course dimensions)
  - Side-by-side vitals comparison
  - Dimension-by-dimension breakdown with dot meters
  - Verdict section with "Choose A if..." / "Choose B if..." picks
  - Training plan CTA
  - JSON-LD (ComparisonPage + BreadcrumbList + FAQPage)

Usage:
    python wordpress/generate_vs_pages.py
    python wordpress/generate_vs_pages.py --output-dir /tmp/gg-vs-test
"""

import argparse
import html as html_mod
import json
import math
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import COLORS, get_font_face_css, get_ga4_head_snippet, get_tokens_css, SITE_BASE_URL
from shared_header import get_site_header_css, get_site_header_html
from cookie_consent import get_consent_banner_html

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CURRENT_YEAR = date.today().year

# ── Constants ────────────────────────────────────────────────────
RADAR_VARS = ["length", "technicality", "elevation", "climate", "altitude", "logistics", "adventure"]
RADAR_LABELS = ["LEN", "TECH", "ELEV", "CLIM", "ALT", "LOG", "ADV"]
RADAR_FULL_LABELS = ["Length", "Technicality", "Elevation", "Climate", "Altitude", "Logistics", "Adventure"]

EDITORIAL_VARS = ["prestige", "race_quality", "experience", "community", "field_depth", "value", "expenses"]
EDITORIAL_LABELS = ["Prestige", "Race Quality", "Experience", "Community", "Field Depth", "Value", "Expenses"]

ALL_DIMS = RADAR_VARS + EDITORIAL_VARS
ALL_DIM_LABELS = RADAR_FULL_LABELS + EDITORIAL_LABELS

COMPARE_COLORS = [
    {"stroke": COLORS["primary_brown"], "fill": "rgba(89,71,60,0.18)"},
    {"stroke": COLORS["teal"], "fill": "rgba(23,128,121,0.18)"},
]

# Max pairs to generate — focus on highest-value comparisons
MAX_PAIRS = 150

TIER_NAMES = {1: "Elite", 2: "Contender", 3: "Solid", 4: "Roster"}


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def _json_str(text) -> str:
    """Escape text for safe inclusion in JSON-LD strings."""
    return json.dumps(str(text))[1:-1] if text else ""


# ── Pair selection ───────────────────────────────────────────────

def select_pairs(races: list) -> list:
    """Select high-value race pairs for vs pages.

    Strategy:
    1. T1 vs T1 same region (natural rivalries)
    2. T1 vs T1 same month (scheduling decisions)
    3. T1 vs top-T2 same region (aspiration comparisons)
    4. T2 vs T2 same region (only top 5 per region)
    """
    scored = [r for r in races if r.get("scores") and r.get("tier") in (1, 2)]
    by_region = defaultdict(list)
    by_month = defaultdict(list)

    for r in scored:
        by_region[r["region"]].append(r)
        by_month[r.get("month", "")].append(r)

    pairs = set()

    # T1 vs T1 same region
    for region_races in by_region.values():
        t1s = [r for r in region_races if r["tier"] == 1]
        for i, a in enumerate(t1s):
            for b in t1s[i + 1:]:
                pairs.add(tuple(sorted([a["slug"], b["slug"]])))

    # T1 vs T1 same month (cross-region — people choosing between)
    for month_races in by_month.values():
        t1s = [r for r in month_races if r["tier"] == 1]
        for i, a in enumerate(t1s):
            for b in t1s[i + 1:]:
                pairs.add(tuple(sorted([a["slug"], b["slug"]])))

    # T1 vs top T2 same region
    for region_races in by_region.values():
        t1s = [r for r in region_races if r["tier"] == 1]
        t2s = sorted(
            [r for r in region_races if r["tier"] == 2],
            key=lambda x: -x.get("overall_score", 0),
        )[:5]
        for a in t1s:
            for b in t2s:
                pairs.add(tuple(sorted([a["slug"], b["slug"]])))

    # T2 vs T2 same region (top 5 only, high-traffic pairs)
    for region_races in by_region.values():
        t2s = sorted(
            [r for r in region_races if r["tier"] == 2],
            key=lambda x: -x.get("overall_score", 0),
        )[:5]
        for i, a in enumerate(t2s):
            for b in t2s[i + 1:]:
                pairs.add(tuple(sorted([a["slug"], b["slug"]])))

    # Sort by combined score (highest-value pairs first) and cap
    race_map = {r["slug"]: r for r in races}
    pair_list = sorted(
        pairs,
        key=lambda p: -(
            race_map.get(p[0], {}).get("overall_score", 0)
            + race_map.get(p[1], {}).get("overall_score", 0)
        ),
    )
    return pair_list[:MAX_PAIRS]


# ── SVG builders ─────────────────────────────────────────────────

def build_radar_svg(race_a: dict, race_b: dict) -> str:
    """Overlaid 7-point radar chart for two races."""
    vw, vh = 440, 340
    cx, cy, r = 220, 160, 120
    n = len(RADAR_VARS)

    parts = [f'<svg viewBox="0 0 {vw} {vh}" class="gg-vs-radar-svg" role="img" '
             f'aria-label="Radar comparison of {esc(race_a["name"])} vs {esc(race_b["name"])}">']

    # Grid rings
    for scale in [0.2, 0.4, 0.6, 0.8, 1.0]:
        pts = []
        for i in range(n):
            angle = (2 * math.pi * i / n) - math.pi / 2
            pts.append(f"{cx + r * scale * math.cos(angle):.1f},{cy + r * scale * math.sin(angle):.1f}")
        parts.append(f'  <polygon points="{" ".join(pts)}" fill="none" stroke="{COLORS["tan"]}" stroke-width="0.8"/>')

    # Axis lines + labels
    for i in range(n):
        angle = (2 * math.pi * i / n) - math.pi / 2
        lx = cx + (r + 18) * math.cos(angle)
        ly = cy + (r + 18) * math.sin(angle)
        parts.append(f'  <line x1="{cx}" y1="{cy}" x2="{cx + r * math.cos(angle):.1f}" '
                     f'y2="{cy + r * math.sin(angle):.1f}" stroke="{COLORS["tan"]}" stroke-width="0.5"/>')
        anchor = "middle"
        if lx < cx - 10:
            anchor = "end"
        elif lx > cx + 10:
            anchor = "start"
        parts.append(f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" '
                     f'font-family="Sometype Mono,monospace" font-size="9" '
                     f'fill="{COLORS["secondary_brown"]}" dominant-baseline="middle">{RADAR_LABELS[i]}</text>')

    # Race polygons
    for idx, race in enumerate([race_a, race_b]):
        scores = race.get("scores", {})
        pts = []
        for i, var in enumerate(RADAR_VARS):
            val = scores.get(var, 1) / 5
            angle = (2 * math.pi * i / n) - math.pi / 2
            pts.append(f"{cx + r * val * math.cos(angle):.1f},{cy + r * val * math.sin(angle):.1f}")
        c = COMPARE_COLORS[idx]
        score_text = " / ".join(f"{RADAR_LABELS[i]}:{scores.get(v,0)}" for i, v in enumerate(RADAR_VARS))
        parts.append(f'  <polygon points="{" ".join(pts)}" fill="{c["fill"]}" '
                     f'stroke="{c["stroke"]}" stroke-width="2.5">'
                     f'<title>{esc(race["name"])}: {score_text}</title></polygon>')

    # Legend
    ly = vh - 30
    for idx, race in enumerate([race_a, race_b]):
        lx = 60 + idx * 220
        c = COMPARE_COLORS[idx]
        parts.append(f'  <rect x="{lx}" y="{ly}" width="14" height="14" fill="{c["stroke"]}"/>')
        parts.append(f'  <text x="{lx + 20}" y="{ly + 11}" font-family="Sometype Mono,monospace" '
                     f'font-size="11" fill="{COLORS["dark_brown"]}">{esc(race["name"][:30])}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


def build_dot_meter(score: int, color: str = COLORS["teal"]) -> str:
    """Inline SVG dot meter (1-5 scale)."""
    dots = []
    for i in range(5):
        fill = color if i < score else COLORS["sand"]
        dots.append(f'<circle cx="{7 + i * 14}" cy="6" r="5" fill="{fill}"/>')
    return f'<svg viewBox="0 0 75 12" class="gg-vs-dots">{"".join(dots)}</svg>'


def build_bars_comparison(race_a: dict, race_b: dict) -> str:
    """Distance and elevation horizontal bars comparison."""
    dist_a = race_a.get("distance_mi", 0) or 0
    dist_b = race_b.get("distance_mi", 0) or 0
    elev_a = race_a.get("elevation_ft", 0) or 0
    elev_b = race_b.get("elevation_ft", 0) or 0

    max_dist = max(dist_a, dist_b, 1)
    max_elev = max(elev_a, elev_b, 1)

    rows = []
    for label, val_a, val_b, max_val, unit in [
        ("Distance", dist_a, dist_b, max_dist, "mi"),
        ("Elevation", elev_a, elev_b, max_elev, "ft"),
    ]:
        pct_a = (val_a / max_val) * 100
        pct_b = (val_b / max_val) * 100
        fmt_a = f"{val_a:,.0f}" if val_a else "—"
        fmt_b = f"{val_b:,.0f}" if val_b else "—"

        winner_a = " gg-vs-bar-winner" if val_a > val_b else ""
        winner_b = " gg-vs-bar-winner" if val_b > val_a else ""

        rows.append(f'''<div class="gg-vs-bar-row">
  <div class="gg-vs-bar-label">{label}</div>
  <div class="gg-vs-bar-pair">
    <div class="gg-vs-bar-cell">
      <div class="gg-vs-bar{winner_a}" style="width:{pct_a:.0f}%;background:{COLORS['primary_brown']}"></div>
      <span class="gg-vs-bar-val">{fmt_a} {unit}</span>
    </div>
    <div class="gg-vs-bar-cell">
      <div class="gg-vs-bar{winner_b}" style="width:{pct_b:.0f}%;background:{COLORS['teal']}"></div>
      <span class="gg-vs-bar-val">{fmt_b} {unit}</span>
    </div>
  </div>
</div>''')

    return "\n".join(rows)


# ── Dimension breakdown table ────────────────────────────────────

def build_dimension_table(race_a: dict, race_b: dict) -> str:
    """15-dimension comparison table with dot meters."""
    scores_a = race_a.get("scores", {})
    scores_b = race_b.get("scores", {})

    rows = []
    # Course dimensions
    rows.append('<tr class="gg-vs-dim-header"><td colspan="3">COURSE PROFILE</td></tr>')
    for dim, label in zip(RADAR_VARS, RADAR_FULL_LABELS):
        sa = scores_a.get(dim, 0)
        sb = scores_b.get(dim, 0)
        hi_a = " gg-vs-dim-win" if sa > sb else ""
        hi_b = " gg-vs-dim-win" if sb > sa else ""
        rows.append(
            f'<tr>'
            f'<td class="gg-vs-dim-name">{label}</td>'
            f'<td class="gg-vs-dim-score{hi_a}">{build_dot_meter(sa, COLORS["primary_brown"])}</td>'
            f'<td class="gg-vs-dim-score{hi_b}">{build_dot_meter(sb, COLORS["teal"])}</td>'
            f'</tr>'
        )

    # Editorial dimensions
    rows.append('<tr class="gg-vs-dim-header"><td colspan="3">EDITORIAL ASSESSMENT</td></tr>')
    for dim, label in zip(EDITORIAL_VARS, EDITORIAL_LABELS):
        sa = scores_a.get(dim, 0)
        sb = scores_b.get(dim, 0)
        hi_a = " gg-vs-dim-win" if sa > sb else ""
        hi_b = " gg-vs-dim-win" if sb > sa else ""
        rows.append(
            f'<tr>'
            f'<td class="gg-vs-dim-name">{label}</td>'
            f'<td class="gg-vs-dim-score{hi_a}">{build_dot_meter(sa, COLORS["primary_brown"])}</td>'
            f'<td class="gg-vs-dim-score{hi_b}">{build_dot_meter(sb, COLORS["teal"])}</td>'
            f'</tr>'
        )

    return f'''<table class="gg-vs-dim-table">
  <thead>
    <tr>
      <th></th>
      <th class="gg-vs-dim-th-a">{esc(race_a["name"][:22])}</th>
      <th class="gg-vs-dim-th-b">{esc(race_b["name"][:22])}</th>
    </tr>
  </thead>
  <tbody>
    {"".join(rows)}
  </tbody>
</table>'''


# ── Verdict section ──────────────────────────────────────────────

def build_verdict(race_a: dict, race_b: dict, full_a: dict, full_b: dict) -> str:
    """Build the 'Choose A if...' / 'Choose B if...' verdict section."""
    scores_a = race_a.get("scores", {})
    scores_b = race_b.get("scores", {})

    # Calculate composite differences
    course_dims = RADAR_VARS
    editorial_dims = EDITORIAL_VARS

    # Determine strengths for each race
    a_wins = []
    b_wins = []
    for dim, label in zip(ALL_DIMS, ALL_DIM_LABELS):
        sa = scores_a.get(dim, 0)
        sb = scores_b.get(dim, 0)
        if sa > sb:
            a_wins.append((label, sa - sb))
        elif sb > sa:
            b_wins.append((label, sb - sa))

    a_wins.sort(key=lambda x: -x[1])
    b_wins.sort(key=lambda x: -x[1])

    # Build "Choose X if..." bullets from dimension wins
    def _choose_bullets(wins, race):
        bullets = []
        for label, diff in wins[:5]:
            dim_lower = label.lower().replace(" ", "_")
            if dim_lower == "length":
                bullets.append(f"You want a {'longer' if race == 'a' else 'longer'} race (higher distance rating)")
            elif dim_lower == "technicality":
                bullets.append(f"You prefer more technical terrain")
            elif dim_lower == "elevation":
                bullets.append(f"You want more climbing")
            elif dim_lower == "climate":
                bullets.append(f"You want more extreme weather conditions")
            elif dim_lower == "altitude":
                bullets.append(f"You thrive at high altitude")
            elif dim_lower == "logistics":
                bullets.append(f"You prefer a more remote, logistically challenging event")
            elif dim_lower == "adventure":
                bullets.append(f"You're chasing a bigger adventure factor")
            elif dim_lower == "prestige":
                bullets.append(f"Prestige and bucket-list status matter to you")
            elif dim_lower == "race_quality":
                bullets.append(f"Top-tier organization and race production are priorities")
            elif dim_lower == "experience":
                bullets.append(f"The overall rider experience is your top priority")
            elif dim_lower == "community":
                bullets.append(f"Community and post-race culture matter most")
            elif dim_lower == "field_depth":
                bullets.append(f"You want to race against a deep competitive field")
            elif dim_lower == "value":
                bullets.append(f"You want the best value for your entry fee")
            elif dim_lower == "expenses":
                bullets.append(f"You're on a tighter travel budget")
            else:
                bullets.append(f"Stronger {label.lower()}")
        return bullets

    a_bullets = _choose_bullets(a_wins, "a")
    b_bullets = _choose_bullets(b_wins, "b")

    # Add verdict one-liners from full race data
    verdict_a = ""
    verdict_b = ""
    if full_a:
        fv = full_a.get("final_verdict", {})
        verdict_a = fv.get("one_liner", "")
    if full_b:
        fv = full_b.get("final_verdict", {})
        verdict_b = fv.get("one_liner", "")

    a_lis = "\n      ".join(f"<li>{esc(b)}</li>" for b in a_bullets)
    b_lis = "\n      ".join(f"<li>{esc(b)}</li>" for b in b_bullets)

    score_a = race_a.get("overall_score", 0)
    score_b = race_b.get("overall_score", 0)

    winner_line = ""
    if score_a > score_b:
        diff = score_a - score_b
        winner_line = f'<p class="gg-vs-winner">{esc(race_a["name"])} scores {diff} points higher overall ({score_a} vs {score_b}), but the right choice depends on what you value most.</p>'
    elif score_b > score_a:
        diff = score_b - score_a
        winner_line = f'<p class="gg-vs-winner">{esc(race_b["name"])} scores {diff} points higher overall ({score_b} vs {score_a}), but the right choice depends on what you value most.</p>'
    else:
        winner_line = f'<p class="gg-vs-winner">Both races score {score_a} — it comes down to what you value most.</p>'

    verdict_a_html = f'<p class="gg-vs-verdict-quote">"{esc(verdict_a)}"</p>' if verdict_a else ""
    verdict_b_html = f'<p class="gg-vs-verdict-quote">"{esc(verdict_b)}"</p>' if verdict_b else ""

    return f'''<section class="gg-vs-verdict">
  <h2>The Verdict</h2>
  {winner_line}
  <div class="gg-vs-verdict-grid">
    <div class="gg-vs-verdict-card gg-vs-verdict-a">
      <h3>Choose {esc(race_a["name"][:22])} if...</h3>
      {verdict_a_html}
      <ul>{a_lis}</ul>
    </div>
    <div class="gg-vs-verdict-card gg-vs-verdict-b">
      <h3>Choose {esc(race_b["name"][:22])} if...</h3>
      {verdict_b_html}
      <ul>{b_lis}</ul>
    </div>
  </div>
</section>'''


# ── FAQ builder ──────────────────────────────────────────────────

def build_faq(race_a: dict, race_b: dict) -> tuple:
    """Build FAQ HTML and JSON-LD for the vs page. Returns (html, jsonld)."""
    name_a = race_a["name"]
    name_b = race_b["name"]
    score_a = race_a.get("overall_score", 0)
    score_b = race_b.get("overall_score", 0)
    scores_a = race_a.get("scores", {})
    scores_b = race_b.get("scores", {})

    pairs = []

    # Q1: Which is harder?
    difficulty_a = sum(scores_a.get(d, 0) for d in ["length", "technicality", "elevation", "climate", "altitude"]) / 5
    difficulty_b = sum(scores_b.get(d, 0) for d in ["length", "technicality", "elevation", "climate", "altitude"]) / 5
    harder = name_a if difficulty_a >= difficulty_b else name_b
    easier = name_b if difficulty_a >= difficulty_b else name_a
    pairs.append((
        f"Which is harder, {name_a} or {name_b}?",
        f"{harder} rates as the more demanding race based on our composite difficulty score "
        f"(averaging length, technicality, elevation, climate, and altitude ratings). "
        f"If you're looking for the bigger challenge, go with {harder}. "
        f"If you want a more accessible race, {easier} is the better pick."
    ))

    # Q2: Which has the better score?
    if score_a != score_b:
        higher = name_a if score_a > score_b else name_b
        h_score = max(score_a, score_b)
        l_score = min(score_a, score_b)
        pairs.append((
            f"Is {name_a} or {name_b} rated higher?",
            f"{higher} scores {h_score}/100 compared to {l_score}/100 in our 15-dimension Gravel God Rating. "
            f"The overall score reflects course profile, prestige, race quality, community, and value."
        ))
    else:
        pairs.append((
            f"Is {name_a} or {name_b} rated higher?",
            f"Both races score {score_a}/100 in our Gravel God Rating — a dead heat. "
            f"They excel in different dimensions, so the best pick depends on your priorities."
        ))

    # Q3: Which is better for beginners?
    access_a = scores_a.get("logistics", 3) + (6 - scores_a.get("technicality", 3)) + (6 - scores_a.get("length", 3))
    access_b = scores_b.get("logistics", 3) + (6 - scores_b.get("technicality", 3)) + (6 - scores_b.get("length", 3))
    beginner = name_a if access_a >= access_b else name_b
    pairs.append((
        f"Which is better for beginners, {name_a} or {name_b}?",
        f"{beginner} is generally more accessible for first-time gravel racers, "
        f"factoring in distance, technicality, and logistical ease. "
        f"Check each race's full profile for distance options and beginner-specific advice."
    ))

    # Q4: When are they held?
    month_a = race_a.get("month", "TBD")
    month_b = race_b.get("month", "TBD")
    if month_a == month_b:
        pairs.append((
            f"When are {name_a} and {name_b} held?",
            f"Both races take place in {month_a}, which means you may need to choose between them. "
            f"Check the official race websites for exact {CURRENT_YEAR} dates."
        ))
    else:
        pairs.append((
            f"When are {name_a} and {name_b} held?",
            f"{name_a} takes place in {month_a} and {name_b} in {month_b}. "
            f"If your calendar allows, you could race both in the same season."
        ))

    # Q5: Where are they located?
    loc_a = race_a.get("location", "")
    loc_b = race_b.get("location", "")
    pairs.append((
        f"Where are {name_a} and {name_b} located?",
        f"{name_a} is held in {loc_a}. {name_b} is held in {loc_b}. "
        f"Consider travel logistics, especially if you're flying in — "
        f"check our full race profiles for airport and lodging details."
    ))

    # Build HTML
    details = []
    for q, a in pairs:
        details.append(
            f'<details class="gg-vs-faq-item"><summary>{esc(q)}</summary>'
            f'<p>{esc(a)}</p></details>'
        )
    faq_html = f'''<section class="gg-vs-faq">
  <h2>Frequently Asked Questions</h2>
  {"".join(details)}
</section>'''

    # Build JSON-LD
    faq_entities = []
    for q, a in pairs:
        faq_entities.append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": a,
            },
        })
    faq_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": faq_entities,
    }, ensure_ascii=False, indent=2)

    return faq_html, faq_jsonld


# ── Training CTA ─────────────────────────────────────────────────

def build_training_cta(race_a: dict, race_b: dict) -> str:
    """Training plan CTA block."""
    return f'''<section class="gg-vs-cta">
  <h2>Still Deciding?</h2>
  <p>Get a personalized training plan for either race — tailored to your fitness, schedule, and goals.</p>
  <div class="gg-vs-cta-buttons">
    <a href="/questionnaire/?race={esc(race_a["slug"])}" class="gg-vs-cta-btn gg-vs-cta-btn-a">
      Train for {esc(race_a["name"][:25])}
    </a>
    <a href="/questionnaire/?race={esc(race_b["slug"])}" class="gg-vs-cta-btn gg-vs-cta-btn-b">
      Train for {esc(race_b["name"][:25])}
    </a>
  </div>
  <p class="gg-vs-cta-sub">$15/week, capped at $249. One-time payment.</p>
</section>'''


# ── Page assembly ────────────────────────────────────────────────

def build_vs_page(race_a: dict, race_b: dict, full_a: dict, full_b: dict) -> str:
    """Generate a complete vs comparison page."""
    name_a = race_a["name"]
    name_b = race_b["name"]
    slug_a = race_a["slug"]
    slug_b = race_b["slug"]
    score_a = race_a.get("overall_score", 0)
    score_b = race_b.get("overall_score", 0)
    tier_a = race_a.get("tier", 3)
    tier_b = race_b.get("tier", 3)

    page_slug = f"{slug_a}-vs-{slug_b}"
    canonical = f"{SITE_BASE_URL}/race/{page_slug}/"
    title = f"{name_a} vs {name_b} — Head-to-Head Comparison | Gravel God"
    description = (
        f"Detailed comparison of {name_a} ({score_a}/100) and {name_b} ({score_b}/100). "
        f"Side-by-side radar chart, 15-dimension breakdown, and verdict to help you choose."
    )

    # Build sections
    radar_svg = build_radar_svg(race_a, race_b)
    bars_html = build_bars_comparison(race_a, race_b)
    dim_table = build_dimension_table(race_a, race_b)
    verdict_html = build_verdict(race_a, race_b, full_a, full_b)
    faq_html, faq_jsonld = build_faq(race_a, race_b)
    cta_html = build_training_cta(race_a, race_b)

    # Taglines
    tagline_a = race_a.get("tagline", "")
    tagline_b = race_b.get("tagline", "")

    font_face = get_font_face_css()
    tokens = get_tokens_css()

    # Breadcrumb JSON-LD
    breadcrumb_jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Gravel Races", "item": f"{SITE_BASE_URL}/gravel-races/"},
            {"@type": "ListItem", "position": 3, "name": f"{name_a} vs {name_b}", "item": canonical},
        ],
    }, ensure_ascii=False, indent=2)

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
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <script type="application/ld+json">
  {breadcrumb_jsonld}
  </script>
  <script type="application/ld+json">
  {faq_jsonld}
  </script>
  <style>
{font_face}
{tokens}

/* ── VS Page Layout ── */
body {{ margin: 0; background: var(--gg-color-warm-paper); }}
*, *::before, *::after {{ border-radius: 0 !important; box-shadow: none !important; }}

.gg-vs-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
}}

{get_site_header_css()}

/* Breadcrumb */
.gg-vs-breadcrumb {{ font-size: 11px; color: var(--gg-color-secondary-brown); padding: 12px 0; letter-spacing: 0.5px; }}
.gg-vs-breadcrumb a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}
.gg-vs-breadcrumb a:hover {{ color: var(--gg-color-dark-brown); }}

/* Hero */
.gg-vs-hero {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  padding: 48px 32px;
  margin: 0 -24px;
  text-align: center;
}}
.gg-vs-hero h1 {{
  font-family: var(--gg-font-editorial);
  font-size: 32px;
  font-weight: 700;
  line-height: 1.2;
  margin: 0 0 24px;
}}
.gg-vs-hero-matchup {{
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 24px;
  flex-wrap: wrap;
}}
.gg-vs-hero-card {{
  text-align: center;
  flex: 1;
  min-width: 200px;
  max-width: 340px;
}}
.gg-vs-hero-score {{
  font-family: var(--gg-font-editorial);
  font-size: 48px;
  font-weight: 700;
  line-height: 1;
}}
.gg-vs-hero-name {{
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-top: 8px;
}}
.gg-vs-hero-meta {{
  font-size: 11px;
  color: var(--gg-color-tan);
  margin-top: 4px;
}}
.gg-vs-hero-tier {{
  display: inline-block;
  border: 1px solid var(--gg-color-tan);
  padding: 2px 8px;
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin-top: 6px;
}}
.gg-vs-hero-vs {{
  font-family: var(--gg-font-editorial);
  font-size: 24px;
  font-weight: 700;
  color: var(--gg-color-gold);
}}
.gg-vs-hero-tagline {{
  font-family: var(--gg-font-editorial);
  font-size: 13px;
  color: var(--gg-color-tan);
  line-height: 1.5;
  margin-top: 8px;
  max-width: 280px;
  margin-left: auto;
  margin-right: auto;
}}

/* Section headings */
.gg-vs-page h2 {{
  font-family: var(--gg-font-editorial);
  font-size: 22px;
  font-weight: 700;
  margin: 40px 0 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--gg-color-dark-brown);
}}

/* Radar */
.gg-vs-radar {{ text-align: center; margin: 32px 0; }}
.gg-vs-radar-svg {{ max-width: 500px; width: 100%; height: auto; }}

/* Bars comparison */
.gg-vs-bars {{ margin: 24px 0; }}
.gg-vs-bar-row {{ margin-bottom: 16px; }}
.gg-vs-bar-label {{
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-bottom: 6px;
  color: var(--gg-color-secondary-brown);
}}
.gg-vs-bar-pair {{ display: flex; gap: 12px; }}
.gg-vs-bar-cell {{ flex: 1; position: relative; height: 28px; background: var(--gg-color-sand); }}
.gg-vs-bar {{
  height: 100%;
  transition: width 0.8s ease;
}}
.gg-vs-bar-winner {{ opacity: 1; }}
.gg-vs-bar-val {{
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 11px;
  font-weight: 700;
  color: var(--gg-color-dark-brown);
}}

/* Dimension table */
.gg-vs-dim-table {{
  width: 100%;
  border-collapse: collapse;
  margin: 24px 0;
}}
.gg-vs-dim-table th {{
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  text-align: left;
  padding: 8px 6px;
  border-bottom: 2px solid var(--gg-color-dark-brown);
  color: var(--gg-color-secondary-brown);
}}
.gg-vs-dim-th-a {{ color: {COLORS["primary_brown"]}; }}
.gg-vs-dim-th-b {{ color: {COLORS["teal"]}; }}
.gg-vs-dim-header td {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  padding: 16px 6px 6px;
  color: var(--gg-color-secondary-brown);
  border-bottom: 1px solid var(--gg-color-tan);
}}
.gg-vs-dim-name {{
  font-size: 12px;
  padding: 8px 6px;
  border-bottom: 1px solid var(--gg-color-sand);
  width: 120px;
}}
.gg-vs-dim-score {{
  padding: 8px 6px;
  border-bottom: 1px solid var(--gg-color-sand);
}}
.gg-vs-dim-win {{ background: var(--gg-color-sand); }}
.gg-vs-dots {{ width: 75px; height: 12px; display: inline-block; vertical-align: middle; }}

/* Verdict */
.gg-vs-verdict {{ margin: 32px 0; }}
.gg-vs-winner {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  line-height: 1.6;
  color: var(--gg-color-dark-brown);
}}
.gg-vs-verdict-grid {{ display: flex; gap: 16px; margin-top: 16px; }}
.gg-vs-verdict-card {{
  flex: 1;
  padding: 20px;
  border: 2px solid var(--gg-color-dark-brown);
}}
.gg-vs-verdict-a {{ border-left: 6px solid {COLORS["primary_brown"]}; }}
.gg-vs-verdict-b {{ border-left: 6px solid {COLORS["teal"]}; }}
.gg-vs-verdict-card h3 {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  margin: 0 0 8px;
}}
.gg-vs-verdict-quote {{
  font-family: var(--gg-font-editorial);
  font-style: italic;
  font-size: 13px;
  color: var(--gg-color-secondary-brown);
  margin-bottom: 12px;
}}
.gg-vs-verdict-card ul {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.gg-vs-verdict-card li {{
  font-size: 13px;
  padding: 4px 0;
  border-bottom: 1px solid var(--gg-color-sand);
}}
.gg-vs-verdict-card li:last-child {{ border-bottom: none; }}
.gg-vs-verdict-card li::before {{
  content: "\\2713 ";
  color: var(--gg-color-teal);
  font-weight: 700;
}}

/* FAQ */
.gg-vs-faq {{ margin: 32px 0; }}
.gg-vs-faq-item {{
  border-bottom: 1px solid var(--gg-color-sand);
  padding: 12px 0;
}}
.gg-vs-faq-item summary {{
  font-family: var(--gg-font-editorial);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  color: var(--gg-color-dark-brown);
}}
.gg-vs-faq-item summary:hover {{ color: var(--gg-color-teal); }}
.gg-vs-faq-item p {{
  font-size: 14px;
  line-height: 1.7;
  margin: 8px 0 0;
  color: var(--gg-color-secondary-brown);
}}

/* CTA */
.gg-vs-cta {{
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  padding: 32px;
  margin: 32px -24px;
  text-align: center;
}}
.gg-vs-cta h2 {{
  color: var(--gg-color-warm-paper);
  border-bottom-color: var(--gg-color-gold);
  margin-top: 0;
}}
.gg-vs-cta p {{ font-size: 14px; line-height: 1.6; }}
.gg-vs-cta-buttons {{ display: flex; gap: 16px; justify-content: center; margin: 20px 0; flex-wrap: wrap; }}
.gg-vs-cta-btn {{
  display: inline-block;
  padding: 12px 24px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  text-decoration: none;
  border: 2px solid var(--gg-color-warm-paper);
  color: var(--gg-color-warm-paper);
  transition: all 0.2s;
}}
.gg-vs-cta-btn:hover {{ background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); }}
.gg-vs-cta-btn-a {{ border-color: {COLORS["warm_brown"]}; }}
.gg-vs-cta-btn-b {{ border-color: {COLORS["teal"]}; }}
.gg-vs-cta-sub {{ font-size: 11px; color: var(--gg-color-tan); margin-top: 8px; }}

/* Links to profiles */
.gg-vs-profile-links {{
  display: flex;
  gap: 12px;
  justify-content: center;
  margin: 16px 0;
}}
.gg-vs-profile-link {{
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--gg-color-teal);
  text-decoration: none;
  padding: 6px 12px;
  border: 2px solid var(--gg-color-teal);
}}
.gg-vs-profile-link:hover {{ background: var(--gg-color-teal); color: var(--gg-color-warm-paper); }}

/* Footer */
.gg-vs-footer {{
  padding: 24px 0;
  margin-top: 32px;
  border-top: 4px double var(--gg-color-dark-brown);
  text-align: center;
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-vs-footer a {{ color: var(--gg-color-secondary-brown); text-decoration: none; }}
.gg-vs-footer a:hover {{ color: var(--gg-color-dark-brown); }}

/* Mobile */
@media (max-width: 768px) {{
  .gg-vs-hero {{ padding: 32px 20px; }}
  .gg-vs-hero h1 {{ font-size: 24px; }}
  .gg-vs-hero-matchup {{ flex-direction: column; gap: 12px; }}
  .gg-vs-hero-score {{ font-size: 36px; }}
  .gg-vs-verdict-grid {{ flex-direction: column; }}
  .gg-vs-cta {{ padding: 24px 16px; margin: 32px -24px; }}
  .gg-vs-dim-table {{ font-size: 11px; }}
  .gg-vs-dots {{ width: 60px; }}
}}
@media (max-width: 480px) {{
  .gg-vs-page {{ padding: 0 12px; }}
  .gg-vs-hero {{ padding: 24px 12px; margin: 0 -12px; }}
  .gg-vs-hero h1 {{ font-size: 20px; }}
  .gg-vs-cta {{ margin: 32px -12px; }}
  .gg-vs-profile-links {{ flex-direction: column; align-items: center; }}
}}
  </style>
  {get_ga4_head_snippet()}
</head>
<body>

<div class="gg-vs-page">

  {get_site_header_html(active="races")}

  <div class="gg-vs-breadcrumb">
    <a href="/">Home</a> &rsaquo; <a href="/gravel-races/">Gravel Races</a> &rsaquo; {esc(name_a)} vs {esc(name_b)}
  </div>

  <section class="gg-vs-hero">
    <h1>{esc(name_a)} vs {esc(name_b)}</h1>
    <div class="gg-vs-hero-matchup">
      <div class="gg-vs-hero-card">
        <div class="gg-vs-hero-score" style="color:{COLORS['warm_brown']}">{score_a}</div>
        <div class="gg-vs-hero-name">{esc(name_a)}</div>
        <div class="gg-vs-hero-meta">{esc(race_a.get("location",""))} &middot; {esc(race_a.get("month",""))}</div>
        <div class="gg-vs-hero-tier">Tier {tier_a} — {esc(TIER_NAMES.get(tier_a, ""))}</div>
        <p class="gg-vs-hero-tagline">{esc(tagline_a[:120])}</p>
      </div>
      <div class="gg-vs-hero-vs">VS</div>
      <div class="gg-vs-hero-card">
        <div class="gg-vs-hero-score" style="color:{COLORS['light_teal']}">{score_b}</div>
        <div class="gg-vs-hero-name">{esc(name_b)}</div>
        <div class="gg-vs-hero-meta">{esc(race_b.get("location",""))} &middot; {esc(race_b.get("month",""))}</div>
        <div class="gg-vs-hero-tier">Tier {tier_b} — {esc(TIER_NAMES.get(tier_b, ""))}</div>
        <p class="gg-vs-hero-tagline">{esc(tagline_b[:120])}</p>
      </div>
    </div>
  </section>

  <div class="gg-vs-profile-links">
    <a href="/race/{esc(slug_a)}/" class="gg-vs-profile-link">Full {esc(name_a[:20])} Profile</a>
    <a href="/race/{esc(slug_b)}/" class="gg-vs-profile-link">Full {esc(name_b[:20])} Profile</a>
  </div>

  <h2>Course Radar Comparison</h2>
  <div class="gg-vs-radar">
    {radar_svg}
  </div>

  <h2>Distance &amp; Elevation</h2>
  <div class="gg-vs-bars">
    {bars_html}
  </div>

  <h2>14-Dimension Breakdown</h2>
  {dim_table}

  {verdict_html}

  {faq_html}

  {cta_html}

  <footer class="gg-vs-footer">
    <a href="/">Gravel God</a> &middot;
    <a href="/gravel-races/">Search All Races</a> &middot;
    <a href="/race/methodology/">Methodology</a>
  </footer>

</div>

{get_consent_banner_html()}
</body>
</html>'''


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate vs comparison pages")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: wordpress/output/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "wordpress" / "output"

    # Load race index
    index_path = PROJECT_ROOT / "web" / "race-index.json"
    if not index_path.exists():
        print("ERROR: web/race-index.json not found.", file=sys.stderr)
        sys.exit(1)

    with open(index_path, "r", encoding="utf-8") as f:
        all_races = json.load(f)
    race_map = {r["slug"]: r for r in all_races}
    print(f"Loaded {len(all_races)} races from index")

    # Load full race data for verdict/opinion content
    race_data_dir = PROJECT_ROOT / "race-data"
    full_race_data = {}
    for slug in race_map:
        path = race_data_dir / f"{slug}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                full_race_data[slug] = data.get("race", {})

    # Select pairs
    pairs = select_pairs(all_races)
    print(f"Selected {len(pairs)} vs pairs")

    generated = 0
    for slug_a, slug_b in pairs:
        race_a = race_map.get(slug_a)
        race_b = race_map.get(slug_b)
        if not race_a or not race_b:
            continue

        full_a = full_race_data.get(slug_a, {})
        full_b = full_race_data.get(slug_b, {})

        page_slug = f"{slug_a}-vs-{slug_b}"
        page_dir = output_dir / page_slug
        page_dir.mkdir(parents=True, exist_ok=True)

        page_html = build_vs_page(race_a, race_b, full_a, full_b)
        out_path = page_dir / "index.html"
        out_path.write_text(page_html, encoding="utf-8")
        generated += 1

    print(f"\nDone. {generated} vs pages generated in {output_dir}/")


if __name__ == "__main__":
    main()
