#!/usr/bin/env python3
"""
Generate tire-vs-tire comparison pages at /tire/{tire-a}-vs-{tire-b}/.

Targets high-intent search queries like "Continental Terra Speed vs Terra Trail"
with radar chart, specs comparison, race recommendation overlap, verdict, and FAQ.

Usage:
    python wordpress/generate_tire_vs_pages.py
    python wordpress/generate_tire_vs_pages.py --output-dir /tmp/tire-vs-test
"""

import argparse
import html as html_mod
import json
import math
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import (
    COLORS,
    SITE_BASE_URL,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
    get_ga4_head_snippet,
)
from cookie_consent import get_consent_banner_html

from generate_tire_guide import load_tire_database

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "tire"
CURRENT_YEAR = date.today().year

# Radar chart dimensions for tire comparison
RADAR_VARS = [
    "rolling_resistance", "puncture_resistance", "wet_traction",
    "mud_clearance", "weight", "durability", "versatility",
]
RADAR_LABELS = ["CRR", "PUNCT", "WET", "MUD", "WEIGHT", "DUR", "VERS"]

COMPARE_COLORS = [
    {"stroke": COLORS["primary_brown"], "fill": "rgba(89,71,60,0.18)"},
    {"stroke": COLORS["teal"], "fill": "rgba(23,128,121,0.18)"},
]


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def _json_str(text) -> str:
    return json.dumps(str(text))[1:-1] if text else ""


def tire_slug(tire: dict) -> str:
    return tire["id"]


# ── Scoring ───────────────────────────────────────────────────


def _rating_to_num(value: str) -> int:
    """Convert qualitative ratings to 1-5 numeric scale."""
    return {
        "high": 5, "good": 5,
        "moderate": 3, "fair": 3,
        "low": 1, "poor": 1,
        "none": 0,
    }.get(value, 2)


def compute_tire_scores(tire: dict) -> dict:
    """Compute 7-dimension radar scores (1-5 scale) for a tire."""
    # Rolling resistance: lower watts = higher score.
    # Best ~27W, worst ~42W among gravel tires
    crr_data = tire.get("crr_watts_at_29kmh") or {}
    crr_vals = [v for v in crr_data.values() if isinstance(v, (int, float))]
    if crr_vals:
        avg_crr = sum(crr_vals) / len(crr_vals)
        crr_score = max(1, min(5, round(5 - (avg_crr - 27) / 3)))
    else:
        crr_score = 3

    # Puncture, wet, mud from qualitative ratings
    punct = _rating_to_num(tire.get("puncture_resistance", ""))
    wet = _rating_to_num(tire.get("wet_traction", ""))
    mud = _rating_to_num(tire.get("mud_clearance", ""))

    # Weight: lighter = higher score. Lightest ~310g, heaviest ~620g at 40mm
    weight_data = tire.get("weight_grams", {})
    weight_vals = [v for v in weight_data.values() if isinstance(v, (int, float))]
    if weight_vals:
        avg_weight = sum(weight_vals) / len(weight_vals)
        weight_score = max(1, min(5, round(5 - (avg_weight - 310) / 70)))
    else:
        weight_score = 3

    # Durability: derived from puncture + tread type
    dur_base = punct
    if tire.get("tread_type") in ("knobby", "aggressive", "mud"):
        dur_base = min(5, dur_base + 1)
    durability = max(1, min(5, dur_base))

    # Versatility: count of recommended_use keywords, scaled to 1-5
    uses = len(tire.get("recommended_use", []))
    versatility = max(1, min(5, round(uses / 1.5)))

    return {
        "rolling_resistance": crr_score,
        "puncture_resistance": punct,
        "wet_traction": wet,
        "mud_clearance": mud,
        "weight": weight_score,
        "durability": durability,
        "versatility": versatility,
    }


# ── Pair Selection ────────────────────────────────────────────


def select_tire_pairs(tire_db: list) -> list:
    """Select high-value tire comparison pairs.

    Strategy:
    1. Same-brand variants (e.g., Terra Speed vs Terra Trail)
    2. Same-category competitors (all file treads, all knobby, etc.)
    3. Cross-category natural matchups (fast vs all-rounder)
    """
    pairs = set()
    tires_by_brand = {}
    tires_by_tread = {}

    for t in tire_db:
        brand = t["brand"]
        tread = t["tread_type"]
        tires_by_brand.setdefault(brand, []).append(t)
        tires_by_tread.setdefault(tread, []).append(t)

    # 1. Same-brand pairs (most natural comparisons)
    for brand, tires in tires_by_brand.items():
        if len(tires) < 2:
            continue
        for i, a in enumerate(tires):
            for b in tires[i + 1:]:
                pairs.add(tuple(sorted([a["id"], b["id"]])))

    # 2. Same-tread-type competitors (top matchups within category)
    for tread, tires in tires_by_tread.items():
        if len(tires) < 2:
            continue
        for i, a in enumerate(tires):
            for b in tires[i + 1:]:
                if a["brand"] != b["brand"]:  # Skip same-brand (already covered)
                    pairs.add(tuple(sorted([a["id"], b["id"]])))

    # 3. Cross-category: file vs knobby (common upgrade/downgrade decision)
    file_tires = tires_by_tread.get("file", [])
    knobby_tires = tires_by_tread.get("knobby", [])
    for a in file_tires[:4]:  # Top 4 file treads
        for b in knobby_tires[:4]:  # Top 4 knobby
            pairs.add(tuple(sorted([a["id"], b["id"]])))

    return sorted(pairs)


# ── SVG Builder ───────────────────────────────────────────────


def build_radar_svg(tire_a: dict, tire_b: dict, scores_a: dict, scores_b: dict) -> str:
    """Overlaid 7-point radar chart for two tires."""
    vw, vh = 440, 340
    cx, cy, r = 220, 160, 120
    n = len(RADAR_VARS)

    parts = [f'<svg viewBox="0 0 {vw} {vh}" class="tvs-radar-svg" role="img" '
             f'aria-label="Radar comparison of {esc(tire_a["name"])} vs {esc(tire_b["name"])}">']

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

    # Tire polygons
    for idx, (tire, scores) in enumerate([(tire_a, scores_a), (tire_b, scores_b)]):
        pts = []
        for i, var in enumerate(RADAR_VARS):
            val = scores.get(var, 1) / 5
            angle = (2 * math.pi * i / n) - math.pi / 2
            pts.append(f"{cx + r * val * math.cos(angle):.1f},{cy + r * val * math.sin(angle):.1f}")
        c = COMPARE_COLORS[idx]
        parts.append(f'  <polygon points="{" ".join(pts)}" fill="{c["fill"]}" '
                     f'stroke="{c["stroke"]}" stroke-width="2.5">'
                     f'<title>{esc(tire["name"])}</title></polygon>')

    # Legend
    ly = vh - 30
    for idx, tire in enumerate([tire_a, tire_b]):
        lx = 60 + idx * 220
        c = COMPARE_COLORS[idx]
        parts.append(f'  <rect x="{lx}" y="{ly}" width="14" height="14" fill="{c["stroke"]}"/>')
        parts.append(f'  <text x="{lx + 20}" y="{ly + 11}" font-family="Sometype Mono,monospace" '
                     f'font-size="11" fill="{COLORS["dark_brown"]}">{esc(tire["name"][:30])}</text>')

    parts.append("</svg>")
    return "\n".join(parts)


# ── Race Overlap ──────────────────────────────────────────────


def get_race_overlap(tire_races: dict, id_a: str, id_b: str) -> dict:
    """Find races where both, only A, or only B tires are recommended."""
    races_a = {r["slug"]: r for r in tire_races.get(id_a, [])}
    races_b = {r["slug"]: r for r in tire_races.get(id_b, [])}

    both = []
    only_a = []
    only_b = []

    for slug in sorted(set(races_a) | set(races_b)):
        if slug in races_a and slug in races_b:
            both.append(races_a[slug])
        elif slug in races_a:
            only_a.append(races_a[slug])
        else:
            only_b.append(races_b[slug])

    return {"both": both, "only_a": only_a, "only_b": only_b}


# ── HTML Builders ─────────────────────────────────────────────


def build_verdict(tire_a: dict, tire_b: dict, scores_a: dict, scores_b: dict) -> str:
    """Build 'Choose A if...' / 'Choose B if...' verdict."""
    a_bullets = []
    b_bullets = []

    dim_advice = {
        "rolling_resistance": ("You prioritize speed and low rolling resistance", "You prioritize speed and low rolling resistance"),
        "puncture_resistance": ("Flat protection is critical for your course", "Flat protection is critical for your course"),
        "wet_traction": ("You expect wet or slick conditions", "You expect wet or slick conditions"),
        "mud_clearance": ("Mud is likely on your course", "Mud is likely on your course"),
        "weight": ("You want the lightest possible setup", "You want the lightest possible setup"),
        "durability": ("Durability and longevity matter most", "Durability and longevity matter most"),
        "versatility": ("You need one tire for many different conditions", "You need one tire for many different conditions"),
    }

    for var in RADAR_VARS:
        sa = scores_a.get(var, 0)
        sb = scores_b.get(var, 0)
        advice = dim_advice.get(var, ("", ""))
        if sa > sb and advice[0]:
            a_bullets.append(advice[0])
        elif sb > sa and advice[1]:
            b_bullets.append(advice[1])

    # Add tread-type specific advice
    if tire_a.get("tread_type") != tire_b.get("tread_type"):
        tread_a = tire_a.get("tread_type", "")
        tread_b = tire_b.get("tread_type", "")
        if tread_a == "file":
            a_bullets.append("Your course is primarily smooth hardpack or pavement")
        elif tread_a in ("aggressive", "mud"):
            a_bullets.append("Your course has technical, loose, or muddy sections")
        if tread_b == "file":
            b_bullets.append("Your course is primarily smooth hardpack or pavement")
        elif tread_b in ("aggressive", "mud"):
            b_bullets.append("Your course has technical, loose, or muddy sections")

    # Price comparison
    price_a = tire_a.get("msrp_usd", 0)
    price_b = tire_b.get("msrp_usd", 0)
    if price_a and price_b and abs(price_a - price_b) > 5:
        if price_a < price_b:
            a_bullets.append(f"Budget matters (${price_a:.0f} vs ${price_b:.0f})")
        else:
            b_bullets.append(f"Budget matters (${price_b:.0f} vs ${price_a:.0f})")

    a_lis = "\n      ".join(f"<li>{esc(b)}</li>" for b in a_bullets[:5])
    b_lis = "\n      ".join(f"<li>{esc(b)}</li>" for b in b_bullets[:5])

    total_a = sum(scores_a.values())
    total_b = sum(scores_b.values())

    if total_a > total_b:
        winner_line = f'<p class="tvs-winner">{esc(tire_a["name"])} scores higher in our composite rating, but the best choice depends on your specific race conditions.</p>'
    elif total_b > total_a:
        winner_line = f'<p class="tvs-winner">{esc(tire_b["name"])} scores higher in our composite rating, but the best choice depends on your specific race conditions.</p>'
    else:
        winner_line = '<p class="tvs-winner">Both tires score equally in our composite rating — your race conditions should decide.</p>'

    return f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">04 / VERDICT</span>
    <h2>The Verdict</h2>
    {winner_line}
    <div class="tvs-verdict-grid">
      <div class="tvs-verdict-card tvs-verdict-a">
        <h3>Choose {esc(tire_a["name"][:25])} if...</h3>
        <ul>{a_lis}</ul>
      </div>
      <div class="tvs-verdict-card tvs-verdict-b">
        <h3>Choose {esc(tire_b["name"][:25])} if...</h3>
        <ul>{b_lis}</ul>
      </div>
    </div>
  </div>
</section>'''


def build_faq(tire_a: dict, tire_b: dict, scores_a: dict, scores_b: dict) -> tuple:
    """Build FAQ HTML and JSON-LD. Returns (html, jsonld_str)."""
    name_a = tire_a["name"]
    name_b = tire_b["name"]

    pairs = []

    # Q1: Which is faster?
    crr_a = scores_a.get("rolling_resistance", 0)
    crr_b = scores_b.get("rolling_resistance", 0)
    faster = name_a if crr_a >= crr_b else name_b
    pairs.append((
        f"Is {name_a} or {name_b} faster?",
        f"{faster} has lower rolling resistance based on BicycleRollingResistance.com test data. "
        f"On smooth hardpack, this translates to measurable watts saved. However, on loose or "
        f"technical terrain, grip often matters more than pure rolling speed."
    ))

    # Q2: Which has better puncture protection?
    punct_a = scores_a.get("puncture_resistance", 0)
    punct_b = scores_b.get("puncture_resistance", 0)
    tougher = name_a if punct_a >= punct_b else name_b
    pairs.append((
        f"Which tire is more puncture resistant, {name_a} or {name_b}?",
        f"{tougher} offers better puncture protection. For courses with sharp flint, "
        f"limestone, or goathead thorns, puncture resistance should be weighted heavily "
        f"in your tire decision."
    ))

    # Q3: Which is better for mud?
    mud_a = scores_a.get("mud_clearance", 0)
    mud_b = scores_b.get("mud_clearance", 0)
    if mud_a == mud_b and mud_a == 0:
        pairs.append((
            f"Can I use {name_a} or {name_b} in mud?",
            f"Neither tire is designed for muddy conditions. Both lack the open tread pattern "
            f"needed for mud clearance. If mud is expected, consider a dedicated mud tire "
            f"like the Schwalbe G-One Ultrabite."
        ))
    else:
        muddier = name_a if mud_a >= mud_b else name_b
        pairs.append((
            f"Which is better in mud, {name_a} or {name_b}?",
            f"{muddier} handles mud better thanks to its tread design and mud clearance. "
            f"For races with predicted rain or notorious mud sections, this difference matters."
        ))

    # Q4: Which is lighter?
    weight_a = scores_a.get("weight", 0)
    weight_b = scores_b.get("weight", 0)
    lighter = name_a if weight_a >= weight_b else name_b
    pairs.append((
        f"Which is lighter, {name_a} or {name_b}?",
        f"{lighter} is the lighter tire. Weight savings help most on climbs — "
        f"roughly 1 second per kilometer of climbing per 100g saved at race effort."
    ))

    # Q5: Price comparison
    price_a = tire_a.get("msrp_usd", 0)
    price_b = tire_b.get("msrp_usd", 0)
    if price_a and price_b:
        cheaper = name_a if price_a <= price_b else name_b
        pairs.append((
            f"Which is a better value, {name_a} or {name_b}?",
            f"At ${min(price_a, price_b):.2f} vs ${max(price_a, price_b):.2f} MSRP, "
            f"{cheaper} is the more budget-friendly option. Factor in expected tire life "
            f"and your race calendar when evaluating total cost of ownership."
        ))

    # Build FAQ HTML
    faq_items = []
    for q, a in pairs:
        faq_items.append(f'''<div class="tvs-faq-item">
      <h4>{esc(q)}</h4>
      <p>{esc(a)}</p>
    </div>''')

    faq_html = f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">05 / FAQ</span>
    <h2>Frequently Asked Questions</h2>
    {"".join(faq_items)}
  </div>
</section>'''

    # Build FAQ JSON-LD
    faq_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": a},
            }
            for q, a in pairs
        ],
    }

    return faq_html, json.dumps(faq_ld, indent=2)


# ── Review Comparison ─────────────────────────────────────────


def compute_review_aggregate(tire: dict) -> dict:
    """Compute review aggregate stats for a tire.

    Returns dict with count, avg, distribution, top_conditions, recommend_pct.
    Only counts approved reviews with valid stars 1-5.
    """
    reviews = [
        r for r in tire.get("community_reviews", [])
        if r.get("approved") and isinstance(r.get("stars"), (int, float))
        and 1 <= r["stars"] <= 5
    ]
    if not reviews:
        return {"count": 0, "avg": 0, "distribution": {}, "top_conditions": [], "recommend_pct": 0}

    stars_list = [int(r["stars"]) for r in reviews]
    avg = sum(stars_list) / len(stars_list)

    distribution = {}
    for s in range(1, 6):
        distribution[s] = stars_list.count(s)

    # Top conditions by frequency
    cond_counts = {}
    for r in reviews:
        for c in (r.get("conditions") or []):
            if isinstance(c, str):
                cond_counts[c] = cond_counts.get(c, 0) + 1
    top_conditions = sorted(cond_counts, key=cond_counts.get, reverse=True)[:3]

    # Recommend percentage
    rec_reviews = [r for r in reviews if r.get("would_recommend") in ("yes", "no")]
    if rec_reviews:
        yes_count = sum(1 for r in rec_reviews if r["would_recommend"] == "yes")
        recommend_pct = round(100 * yes_count / len(rec_reviews))
    else:
        recommend_pct = 0

    return {
        "count": len(reviews),
        "avg": avg,
        "distribution": distribution,
        "top_conditions": top_conditions,
        "recommend_pct": recommend_pct,
    }


def build_review_comparison(tire_a: dict, tire_b: dict) -> str:
    """Build review comparison section for VS pages.

    Three display states:
    - Both have 3+ reviews: side-by-side cards
    - One has reviews: show reviewed tire + CTA for other
    - Neither has reviews: return empty string
    """
    agg_a = compute_review_aggregate(tire_a)
    agg_b = compute_review_aggregate(tire_b)

    has_a = agg_a["count"] >= 3
    has_b = agg_b["count"] >= 3

    if not has_a and not has_b:
        # Neither has enough reviews — skip section entirely
        if agg_a["count"] == 0 and agg_b["count"] == 0:
            return ""
        # One or both have <3 reviews — still skip the comparison
        if agg_a["count"] < 3 and agg_b["count"] < 3:
            return ""

    slug_a = tire_slug(tire_a)
    slug_b = tire_slug(tire_b)
    name_a = esc(tire_a["name"])
    name_b = esc(tire_b["name"])

    def _star_html(avg):
        full = int(avg)
        half = (avg - full) >= 0.5
        stars = "&#9733;" * full
        if half:
            stars += "&#9733;"
            empty = 5 - full - 1
        else:
            empty = 5 - full
        stars += "&#9734;" * max(0, empty)
        return stars

    def _review_card(tire, agg, css_class):
        name = esc(tire["name"])
        slug = tire_slug(tire)
        stars_html = _star_html(agg["avg"])
        conditions_html = ""
        if agg["top_conditions"]:
            tags = ", ".join(c.title() for c in agg["top_conditions"])
            conditions_html = f'<div class="tvs-review-conditions">Top conditions: {esc(tags)}</div>'
        rec_html = ""
        if agg["recommend_pct"] > 0:
            rec_html = f'<div class="tvs-review-recommend">{agg["recommend_pct"]}% would recommend</div>'
        return f'''<div class="tvs-review-card {css_class}">
        <h3 class="tvs-review-card-name">{name}</h3>
        <div class="tvs-review-card-avg">{agg["avg"]:.1f}</div>
        <div class="tvs-review-card-stars">{stars_html}</div>
        <div class="tvs-review-card-count">{agg["count"]} review{"s" if agg["count"] != 1 else ""}</div>
        {conditions_html}
        {rec_html}
        <a href="/tire/{slug}/" class="tvs-review-card-link">Read all reviews &rarr;</a>
      </div>'''

    def _cta_card(tire, css_class):
        name = esc(tire["name"])
        slug = tire_slug(tire)
        return f'''<div class="tvs-review-card {css_class} tvs-review-card--empty">
        <h3 class="tvs-review-card-name">{name}</h3>
        <div class="tvs-review-card-none">No community reviews yet.</div>
        <a href="/tire/{slug}/" class="tvs-review-card-link">Be the first to review &rarr;</a>
      </div>'''

    # Build cards
    if has_a and has_b:
        card_a = _review_card(tire_a, agg_a, "tvs-review-card--a")
        card_b = _review_card(tire_b, agg_b, "tvs-review-card--b")
    elif has_a:
        card_a = _review_card(tire_a, agg_a, "tvs-review-card--a")
        card_b = _cta_card(tire_b, "tvs-review-card--b")
    else:
        card_a = _cta_card(tire_a, "tvs-review-card--a")
        card_b = _review_card(tire_b, agg_b, "tvs-review-card--b")

    return f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">06 / COMMUNITY REVIEWS</span>
    <h2>What Riders Say</h2>
    <div class="tvs-review-grid">
      {card_a}
      {card_b}
    </div>
  </div>
</section>'''


# ── CSS ───────────────────────────────────────────────────────


def get_page_css() -> str:
    return """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: var(--gg-font-editorial);
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-near-black);
  line-height: 1.6;
}
a { color: var(--gg-color-teal); text-decoration: none; }
a:hover { text-decoration: underline; }

.tvs-container { max-width: 820px; margin: 0 auto; padding: 0 20px; }

/* Header */
.tvs-header {
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  padding: 48px 0 36px;
  border-bottom: 4px solid var(--gg-color-teal);
}
.tvs-breadcrumb {
  font-family: var(--gg-font-data);
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--gg-color-warm-brown);
  margin-bottom: 12px;
}
.tvs-breadcrumb a { color: var(--gg-color-warm-brown); }
.tvs-breadcrumb a:hover { color: var(--gg-color-teal); }
.tvs-badge {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  background: var(--gg-color-teal);
  color: var(--gg-color-white);
  padding: 3px 10px;
  margin-bottom: 12px;
}
.tvs-header h1 {
  font-family: var(--gg-font-data);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.3px;
  line-height: 1.2;
  margin: 8px 0;
}
@media (min-width: 640px) { .tvs-header h1 { font-size: 32px; } }
.tvs-header-sub {
  font-family: var(--gg-font-editorial);
  font-size: 14px;
  color: var(--gg-color-warm-brown);
  font-style: italic;
}

/* Section styling */
.tvs-section {
  padding: 40px 0;
  border-bottom: 1px solid var(--gg-color-tan);
}
.tvs-section:last-of-type { border-bottom: none; }
.tvs-section-num {
  font-family: var(--gg-font-data);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-teal);
  display: block;
  margin-bottom: 8px;
}
.tvs-section h2 {
  font-family: var(--gg-font-data);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 20px;
}

/* Radar chart */
.tvs-radar-svg { width: 100%; max-width: 440px; height: auto; margin: 0 auto; display: block; }

/* Specs comparison table */
.tvs-specs-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--gg-font-data);
  font-size: 13px;
  margin: 16px 0;
}
.tvs-specs-table th {
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  padding: 10px 16px;
  text-align: left;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}
.tvs-specs-table td {
  padding: 10px 16px;
  border-bottom: 1px solid var(--gg-color-tan);
}
.tvs-specs-table tr:nth-child(even) td { background: var(--gg-color-sand); }
.tvs-specs-table .tvs-winner-cell { color: var(--gg-color-teal); font-weight: 700; }

/* Race overlap */
.tvs-race-overlap { margin: 16px 0; }
.tvs-overlap-label {
  font-family: var(--gg-font-data);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.tvs-overlap-label--both { color: var(--gg-color-teal); }
.tvs-overlap-label--a { color: """ + COLORS["primary_brown"] + """; }
.tvs-overlap-label--b { color: """ + COLORS["teal"] + """; }
.tvs-overlap-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}
.tvs-overlap-chip {
  font-family: var(--gg-font-data);
  font-size: 11px;
  padding: 3px 8px;
  border: 1px solid var(--gg-color-tan);
  text-decoration: none;
  color: var(--gg-color-near-black);
}
.tvs-overlap-chip:hover { border-color: var(--gg-color-teal); text-decoration: none; }

/* Verdict */
.tvs-winner {
  font-family: var(--gg-font-editorial);
  font-size: 14px;
  color: var(--gg-color-secondary-brown);
  margin-bottom: 20px;
  font-style: italic;
}
.tvs-verdict-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 640px) { .tvs-verdict-grid { grid-template-columns: 1fr; } }
.tvs-verdict-card {
  background: var(--gg-color-white);
  border: 2px solid var(--gg-color-tan);
  padding: 20px;
}
.tvs-verdict-a { border-top: 3px solid """ + COLORS["primary_brown"] + """; }
.tvs-verdict-b { border-top: 3px solid """ + COLORS["teal"] + """; }
.tvs-verdict-card h3 {
  font-family: var(--gg-font-data);
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 12px;
}
.tvs-verdict-card ul { list-style: none; padding: 0; }
.tvs-verdict-card li {
  font-family: var(--gg-font-data);
  font-size: 12px;
  padding: 3px 0;
}
.tvs-verdict-card li::before { content: "\\2192"; margin-right: 8px; color: var(--gg-color-teal); }

/* FAQ */
.tvs-faq-item {
  padding: 16px 0;
  border-bottom: 1px solid var(--gg-color-tan);
}
.tvs-faq-item:last-child { border-bottom: none; }
.tvs-faq-item h4 {
  font-family: var(--gg-font-data);
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 6px;
}
.tvs-faq-item p {
  font-family: var(--gg-font-editorial);
  font-size: 13px;
  color: var(--gg-color-secondary-brown);
  line-height: 1.6;
}

/* Email capture */
.tvs-email-capture {
  border: 1px solid var(--gg-color-tan);
  border-top: 3px solid var(--gg-color-teal);
  background: var(--gg-color-white);
  margin: 16px 0;
}
.tvs-email-capture-inner { padding: 24px 32px; text-align: center; }
.tvs-email-capture-badge { display: inline-block; font-family: var(--gg-font-data); font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; background: var(--gg-color-teal); color: var(--gg-color-white); padding: 3px 10px; margin-bottom: 8px; }
.tvs-email-capture-title { font-family: var(--gg-font-data); font-size: 14px; font-weight: 700; letter-spacing: 3px; color: var(--gg-color-near-black); margin: 0 0 4px 0; }
.tvs-email-capture-text { font-family: var(--gg-font-editorial); font-size: 12px; color: var(--gg-color-secondary-brown); line-height: 1.6; margin: 0 0 16px 0; max-width: 500px; margin-left: auto; margin-right: auto; }
.tvs-email-capture-row { display: flex; gap: 0; max-width: 420px; margin: 0 auto 8px; }
.tvs-email-capture-input { flex: 1; font-family: var(--gg-font-data); font-size: 13px; padding: 12px 14px; border: 2px solid var(--gg-color-tan); border-right: none; background: var(--gg-color-white); color: var(--gg-color-near-black); min-width: 0; }
.tvs-email-capture-input:focus { outline: none; border-color: var(--gg-color-teal); }
.tvs-email-capture-btn { font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; padding: 12px 18px; background: var(--gg-color-teal); color: var(--gg-color-white); border: 2px solid var(--gg-color-teal); cursor: pointer; white-space: nowrap; transition: background 0.2s; }
.tvs-email-capture-btn:hover { background: var(--gg-color-light-teal); }
.tvs-email-capture-fine { font-family: var(--gg-font-data); font-size: 10px; color: var(--gg-color-warm-brown); letter-spacing: 1px; margin: 0; }
.tvs-email-capture-success { padding: 8px 0; }
.tvs-email-capture-check { font-family: var(--gg-font-data); font-size: 14px; font-weight: 700; color: var(--gg-color-teal); margin: 0 0 8px; }
.tvs-email-capture-link { display: inline-block; font-family: var(--gg-font-data); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: var(--gg-color-white); background: var(--gg-color-teal); padding: 10px 20px; text-decoration: none; border: 2px solid var(--gg-color-teal); transition: background 0.2s; }
.tvs-email-capture-link:hover { background: var(--gg-color-light-teal); text-decoration: none; }

/* Footer */
.tvs-footer-cta {
  background: var(--gg-color-near-black);
  padding: 40px 0;
}
.tvs-footer-cta-inner { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; }
.tvs-btn {
  display: inline-block; font-family: var(--gg-font-data); font-size: 13px; font-weight: 700;
  letter-spacing: 1.5px; text-transform: uppercase; padding: 12px 24px;
  text-decoration: none; transition: all 0.2s;
}
.tvs-btn--primary { background: var(--gg-color-teal); color: var(--gg-color-white); border: 2px solid var(--gg-color-teal); }
.tvs-btn--primary:hover { background: transparent; color: var(--gg-color-teal); text-decoration: none; }
.tvs-btn--outline { background: transparent; color: var(--gg-color-warm-paper); border: 2px solid var(--gg-color-warm-paper); }
.tvs-btn--outline:hover { background: var(--gg-color-warm-paper); color: var(--gg-color-near-black); text-decoration: none; }

@media (max-width: 480px) {
  .tvs-email-capture-row { flex-direction: column; gap: 8px; }
  .tvs-email-capture-input { border-right: 2px solid var(--gg-color-tan); }
}
/* Review comparison */
.tvs-review-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 640px) { .tvs-review-grid { grid-template-columns: 1fr; } }
.tvs-review-card {
  background: var(--gg-color-white);
  border: 2px solid var(--gg-color-tan);
  padding: 24px;
  text-align: center;
}
.tvs-review-card--a { border-top: 3px solid """ + COLORS["primary_brown"] + """; }
.tvs-review-card--b { border-top: 3px solid """ + COLORS["teal"] + """; }
.tvs-review-card-name {
  font-family: var(--gg-font-data);
  font-size: 14px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 12px;
}
.tvs-review-card-avg {
  font-family: var(--gg-font-data);
  font-size: 36px;
  font-weight: 700;
  color: var(--gg-color-near-black);
  line-height: 1;
  margin-bottom: 4px;
}
.tvs-review-card-stars {
  font-size: 18px;
  color: var(--gg-color-teal);
  margin-bottom: 8px;
}
.tvs-review-card-count {
  font-family: var(--gg-font-data);
  font-size: 12px;
  color: var(--gg-color-secondary-brown);
  margin-bottom: 8px;
}
.tvs-review-conditions {
  font-family: var(--gg-font-data);
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  margin-bottom: 6px;
}
.tvs-review-recommend {
  font-family: var(--gg-font-data);
  font-size: 12px;
  font-weight: 700;
  color: var(--gg-color-teal);
  margin-bottom: 8px;
}
.tvs-review-card-none {
  font-family: var(--gg-font-editorial);
  font-size: 13px;
  color: var(--gg-color-secondary-brown);
  font-style: italic;
  margin-bottom: 16px;
  padding: 24px 0;
}
.tvs-review-card-link {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  color: var(--gg-color-teal);
  margin-top: 8px;
}

@media print { .tvs-footer-cta, .tvs-email-capture { display: none; } }
"""


# ── Page Assembly ─────────────────────────────────────────────


def build_specs_comparison(tire_a: dict, tire_b: dict) -> str:
    """Side-by-side specs table."""
    rows = []

    def _compare_row(label, val_a, val_b, lower_wins=False):
        """Build a table row, highlighting the winner."""
        cls_a = cls_b = ""
        try:
            na, nb = float(val_a.replace("g", "").replace("W", "").replace("$", "")), float(val_b.replace("g", "").replace("W", "").replace("$", ""))
            if lower_wins:
                if na < nb: cls_a = ' class="tvs-winner-cell"'
                elif nb < na: cls_b = ' class="tvs-winner-cell"'
            else:
                if na > nb: cls_a = ' class="tvs-winner-cell"'
                elif nb > na: cls_b = ' class="tvs-winner-cell"'
        except (ValueError, AttributeError):
            pass
        return f"<tr><td>{label}</td><td{cls_a}>{val_a}</td><td{cls_b}>{val_b}</td></tr>"

    # Price
    pa = f"${tire_a['msrp_usd']:.2f}" if tire_a.get("msrp_usd") else "N/A"
    pb = f"${tire_b['msrp_usd']:.2f}" if tire_b.get("msrp_usd") else "N/A"
    rows.append(_compare_row("MSRP", pa, pb, lower_wins=True))

    # Widths
    wa = ", ".join(f"{w}" for w in tire_a["widths_mm"])
    wb = ", ".join(f"{w}" for w in tire_b["widths_mm"])
    rows.append(f"<tr><td>Widths (mm)</td><td>{wa}</td><td>{wb}</td></tr>")

    # Weight at common width
    common_widths = set(str(w) for w in tire_a["widths_mm"]) & set(str(w) for w in tire_b["widths_mm"])
    if common_widths:
        cw = sorted(common_widths)[len(common_widths) // 2]  # Pick middle width
        wa_g = tire_a.get("weight_grams", {}).get(cw, "—")
        wb_g = tire_b.get("weight_grams", {}).get(cw, "—")
        wa_s = f"{wa_g}g" if isinstance(wa_g, (int, float)) else "—"
        wb_s = f"{wb_g}g" if isinstance(wb_g, (int, float)) else "—"
        rows.append(_compare_row(f"Weight ({cw}mm)", wa_s, wb_s, lower_wins=True))

    # CRR
    crr_a = tire_a.get("crr_watts_at_29kmh") or {}
    crr_b = tire_b.get("crr_watts_at_29kmh") or {}
    crr_va = next((v for v in crr_a.values() if isinstance(v, (int, float))), None)
    crr_vb = next((v for v in crr_b.values() if isinstance(v, (int, float))), None)
    ca_s = f"{crr_va}W" if crr_va else "—"
    cb_s = f"{crr_vb}W" if crr_vb else "—"
    rows.append(_compare_row("CRR (29km/h)", ca_s, cb_s, lower_wins=True))

    # Qualitative ratings
    def _rating_label(v):
        return {"high": "High", "good": "Good", "moderate": "Moderate", "fair": "Fair",
                "low": "Low", "poor": "Poor", "none": "None"}.get(v, "N/A")

    rows.append(f"<tr><td>Tread Type</td><td>{esc(tire_a.get('tread_type', '').title())}</td><td>{esc(tire_b.get('tread_type', '').title())}</td></tr>")
    rows.append(f"<tr><td>Puncture</td><td>{_rating_label(tire_a.get('puncture_resistance', ''))}</td><td>{_rating_label(tire_b.get('puncture_resistance', ''))}</td></tr>")
    rows.append(f"<tr><td>Wet Traction</td><td>{_rating_label(tire_a.get('wet_traction', ''))}</td><td>{_rating_label(tire_b.get('wet_traction', ''))}</td></tr>")
    rows.append(f"<tr><td>Mud Clearance</td><td>{_rating_label(tire_a.get('mud_clearance', ''))}</td><td>{_rating_label(tire_b.get('mud_clearance', ''))}</td></tr>")

    return f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">02 / SPECS COMPARISON</span>
    <h2>Head-to-Head Specs</h2>
    <table class="tvs-specs-table">
      <thead><tr><th>Spec</th><th>{esc(tire_a["name"][:25])}</th><th>{esc(tire_b["name"][:25])}</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</section>'''


def build_race_overlap_section(tire_a: dict, tire_b: dict, overlap: dict) -> str:
    if not overlap["both"] and not overlap["only_a"] and not overlap["only_b"]:
        return ""

    parts = []

    if overlap["both"]:
        chips = "".join(
            f'<a href="/race/{esc(r["slug"])}/tires/" class="tvs-overlap-chip">{esc(r["name"])}</a>'
            for r in overlap["both"][:15]
        )
        parts.append(f'''<div class="tvs-overlap-label tvs-overlap-label--both">BOTH RECOMMENDED ({len(overlap["both"])})</div>
    <div class="tvs-overlap-list">{chips}</div>''')

    if overlap["only_a"]:
        chips = "".join(
            f'<a href="/race/{esc(r["slug"])}/tires/" class="tvs-overlap-chip">{esc(r["name"])}</a>'
            for r in overlap["only_a"][:10]
        )
        parts.append(f'''<div class="tvs-overlap-label tvs-overlap-label--a">ONLY {esc(tire_a["name"][:20]).upper()} ({len(overlap["only_a"])})</div>
    <div class="tvs-overlap-list">{chips}</div>''')

    if overlap["only_b"]:
        chips = "".join(
            f'<a href="/race/{esc(r["slug"])}/tires/" class="tvs-overlap-chip">{esc(r["name"])}</a>'
            for r in overlap["only_b"][:10]
        )
        parts.append(f'''<div class="tvs-overlap-label tvs-overlap-label--b">ONLY {esc(tire_b["name"][:20]).upper()} ({len(overlap["only_b"])})</div>
    <div class="tvs-overlap-list">{chips}</div>''')

    return f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">03 / RACE RECOMMENDATIONS</span>
    <h2>Where Each Tire Is Recommended</h2>
    <div class="tvs-race-overlap">{"".join(parts)}</div>
  </div>
</section>'''


def build_email_capture() -> str:
    return '''<div class="tvs-email-capture">
    <div class="tvs-email-capture-inner">
      <div class="tvs-email-capture-badge">FREE DOWNLOAD</div>
      <h3 class="tvs-email-capture-title">GET A RACE DAY SETUP CARD</h3>
      <p class="tvs-email-capture-text">Tire picks, pressure chart, sealant amounts, and tubeless tips &mdash; customized for any gravel race.</p>
      <form class="tvs-email-capture-form" id="tvs-email-capture-form" autocomplete="off">
        <input type="hidden" name="source" value="tire_guide">
        <input type="hidden" name="website" value="">
        <div class="tvs-email-capture-row">
          <input type="email" name="email" required placeholder="your@email.com" class="tvs-email-capture-input" aria-label="Email address">
          <button type="submit" class="tvs-email-capture-btn">GET SETUP CARD</button>
        </div>
      </form>
      <div class="tvs-email-capture-success" id="tvs-email-capture-success" style="display:none">
        <p class="tvs-email-capture-check">&#10003; Setup card unlocked!</p>
        <a href="/gravel-races/" class="tvs-email-capture-link">Find Your Race &rarr;</a>
      </div>
      <p class="tvs-email-capture-fine">No spam. Unsubscribe anytime.</p>
    </div>
  </div>'''


def build_inline_js() -> str:
    return '''<script>
(function(){
  var WORKER_URL='https://fueling-lead-intake.gravelgodcoaching.workers.dev';
  var LS_KEY='gg-pk-fueling';
  var EXPIRY_DAYS=90;
  var form=document.getElementById('tvs-email-capture-form');
  if(!form) return;
  try{
    var cached=JSON.parse(localStorage.getItem(LS_KEY)||'null');
    if(cached&&cached.email&&cached.exp>Date.now()){
      form.style.display='none';
      var success=document.getElementById('tvs-email-capture-success');
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
    try{localStorage.setItem(LS_KEY,JSON.stringify({email:email,exp:Date.now()+EXPIRY_DAYS*86400000}));}catch(ex){}
    var payload={email:email,source:form.source.value,website:form.website.value};
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(function(){});
    if(typeof gtag==='function') gtag('event','email_capture',{source:'tire_guide'});
    form.style.display='none';
    var success=document.getElementById('tvs-email-capture-success');
    if(success) success.style.display='block';
  });
})();
</script>'''


def build_json_ld(tire_a: dict, tire_b: dict) -> str:
    slug_a = tire_slug(tire_a)
    slug_b = tire_slug(tire_b)
    url = f"{SITE_BASE_URL}/tire/{slug_a}-vs-{slug_b}/"

    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Gravel God",
             "item": f"{SITE_BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Tire Comparisons",
             "item": f"{SITE_BASE_URL}/tire/"},
            {"@type": "ListItem", "position": 3,
             "name": f"{tire_a['name']} vs {tire_b['name']}",
             "item": url},
        ]
    }
    return json.dumps(breadcrumb, indent=2)


def generate_vs_page(tire_a: dict, tire_b: dict, tire_races: dict) -> str:
    scores_a = compute_tire_scores(tire_a)
    scores_b = compute_tire_scores(tire_b)
    overlap = get_race_overlap(tire_races, tire_a["id"], tire_b["id"])

    name_a = tire_a["name"]
    name_b = tire_b["name"]
    slug_a = tire_slug(tire_a)
    slug_b = tire_slug(tire_b)

    radar = build_radar_svg(tire_a, tire_b, scores_a, scores_b)
    specs = build_specs_comparison(tire_a, tire_b)
    race_overlap = build_race_overlap_section(tire_a, tire_b, overlap)
    verdict = build_verdict(tire_a, tire_b, scores_a, scores_b)
    faq_html, faq_ld = build_faq(tire_a, tire_b, scores_a, scores_b)
    review_comparison = build_review_comparison(tire_a, tire_b)
    email_capture = build_email_capture()
    inline_js = build_inline_js()

    breadcrumb_ld = build_json_ld(tire_a, tire_b)
    json_ld = f'''<script type="application/ld+json">{breadcrumb_ld}</script>
<script type="application/ld+json">{faq_ld}</script>'''

    title = f"{esc(name_a)} vs {esc(name_b)}: Which Gravel Tire Is Right? | Gravel God"
    meta_desc = f"{name_a} vs {name_b} comparison: rolling resistance, puncture protection, weight, race recommendations, and verdict."
    canonical = f"{SITE_BASE_URL}/tire/{slug_a}-vs-{slug_b}/"

    tokens_css = get_tokens_css()
    font_css = get_font_face_css(font_path_prefix="/race/assets/fonts")
    preload = get_preload_hints()
    page_css = get_page_css()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{esc(meta_desc)}">
  <link rel="canonical" href="{canonical}">

  <meta property="og:title" content="{title}">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:type" content="article">
  <meta property="og:site_name" content="Gravel God Cycling">

  {preload}

  <style>
  {font_css}
  {tokens_css}
  {page_css}
  </style>

  {json_ld}

  {get_ga4_head_snippet()}
</head>
<body>
<header class="tvs-header">
  <div class="tvs-container">
    <div class="tvs-breadcrumb">
      <a href="/">Gravel God</a> / <a href="/gravel-races/">Races</a> / Tire Comparison
    </div>
    <span class="tvs-badge">TIRE COMPARISON</span>
    <h1>{esc(name_a)} vs {esc(name_b)}</h1>
    <p class="tvs-header-sub">Which gravel tire is right for your next race?</p>
  </div>
</header>
<main>
<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">01 / RADAR COMPARISON</span>
    <h2>Performance Profile</h2>
    {radar}
  </div>
</section>
{specs}
{race_overlap}
{verdict}
{faq_html}
{review_comparison}
<section class="tvs-section">
  <div class="tvs-container">
    {email_capture}
  </div>
</section>
</main>
<footer class="tvs-footer-cta">
  <div class="tvs-container">
    <div class="tvs-footer-cta-inner">
      <a href="/tire/{slug_a}/" class="tvs-btn tvs-btn--primary">{esc(name_a[:20])} Review</a>
      <a href="/tire/{slug_b}/" class="tvs-btn tvs-btn--outline">{esc(name_b[:20])} Review</a>
    </div>
  </div>
</footer>
{inline_js}
{get_consent_banner_html()}
</body>
</html>'''


# ── CLI ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate tire-vs-tire comparison pages."
    )
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: wordpress/output/tire/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load tire database
    tire_db = load_tire_database()
    tire_map = {t["id"]: t for t in tire_db}
    print(f"Loaded {len(tire_db)} tires")

    # Scan race data for tire recommendations
    from generate_tire_pages import scan_race_recommendations
    print("Scanning race data for tire recommendations...")
    tire_races = scan_race_recommendations(tire_db)

    # Select pairs
    pairs = select_tire_pairs(tire_db)
    print(f"Selected {len(pairs)} tire comparison pairs")

    generated = 0
    for id_a, id_b in pairs:
        tire_a = tire_map.get(id_a)
        tire_b = tire_map.get(id_b)
        if not tire_a or not tire_b:
            continue

        page_slug = f"{id_a}-vs-{id_b}"
        page_dir = output_dir / page_slug
        page_dir.mkdir(parents=True, exist_ok=True)

        html_content = generate_vs_page(tire_a, tire_b, tire_races)
        out_path = page_dir / "index.html"
        out_path.write_text(html_content, encoding="utf-8")
        generated += 1

    print(f"\nDone. {generated} tire vs pages generated in {output_dir}/")


if __name__ == "__main__":
    main()
