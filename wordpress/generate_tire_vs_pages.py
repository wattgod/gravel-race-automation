#!/usr/bin/env python3
"""
Generate tire-vs-tire comparison pages at /tire/{tire-a}-vs-{tire-b}/.

Targets high-intent search queries like "Continental Terra Speed vs Terra Trail"
with the two tires' BRR lab tests head to head, specs, race picks and FAQ.
Everything compared is measured by BRR or labelled as our call; no
hand-written tagline, strengths or weaknesses reach the page.

Usage:
    python wordpress/generate_tire_vs_pages.py
    python wordpress/generate_tire_vs_pages.py --output-dir /tmp/tire-vs-test
"""

import argparse
import html as html_mod
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import (
    SITE_BASE_URL,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
    get_ga4_head_snippet,
)
from season import season_year
from cookie_consent import get_consent_banner_html

from generate_tire_guide import load_tire_database
from generate_tire_pages import (
    RANK_MEASURES,
    _join,
    _num,
    biggest_class,
    lab_meta,
    lab_pool,
    number_sections,
    ordinal,
    rating_label,
    tests_by_class,
    tire_ranks,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "tire"
SEASON_YEAR = season_year()


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def tire_slug(tire: dict) -> str:
    return tire["id"]


# ── Head to head: both tires ranked in the BRR width class they share ──

# What leading on each lab measure means, for the verdict and the FAQ.
LEADS = {
    "rr_watts": "rolls faster",
    "puncture_tread": "resists punctures better",
    "wet_grip": "grips better in the wet",
    "weight_g": "weighs less",
}


def head_to_head(tire_a: dict, tire_b: dict):
    """Both tires' BRR ranks at one tested width, measure by measure, with the
    leader on each. The width class is the shared one holding the most tested
    tires, as tire_ranks() picks for a single tire. None unless both tires
    were tested at the same width there."""
    if not (tire_a.get("lab_tested") and tire_b.get("lab_tested")):
        return None
    shared = set(tests_by_class(tire_a)) & set(tests_by_class(tire_b))
    if not shared:
        return None
    cls = biggest_class(shared, lab_pool())
    ranks = [tire_ranks(t, cls) for t in (tire_a, tire_b)]
    if None in ranks or ranks[0]["test"]["width_mm"] != ranks[1]["test"]["width_mm"]:
        return None
    by_key = [{r["key"]: r for r in x["rows"]} for x in ranks]
    rows = []
    for key, label, _noun, unit, lower in RANK_MEASURES:
        a, b = by_key[0].get(key), by_key[1].get(key)
        if not (a or b):
            continue
        leader = None
        if a and b and a["value"] != b["value"]:
            leader = 0 if (a["value"] < b["value"]) == lower else 1
        rows.append({"key": key, "label": label, "unit": unit,
                     "cells": (a, b), "leader": leader})
    return {
        "width": ranks[0]["test"]["width_mm"],
        "class_label": ranks[0]["class_label"],
        "tests": (ranks[0]["test"], ranks[1]["test"]),
        "rows": rows,
        "pool": max(r["of"] for x in ranks for r in x["rows"]),
    }


def verdict_sentence(tire_a: dict, tire_b: dict, h2h: dict) -> str:
    """'In BRR's 40mm tests, A rolls faster and weighs less; B grips better in the wet.'"""
    names = (tire_a["name"], tire_b["name"])
    parts = []
    for i in (0, 1):
        leads = [LEADS[r["key"]] for r in h2h["rows"] if r["leader"] == i]
        if leads:
            parts.append(f"{names[i]} {_join(leads)}")
    found = "; ".join(parts) or "the two measure the same on every lab measure"
    return f"In BRR's {_num(h2h['width'], 'mm')} tests, {found}."


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

    # Publish a comparison only when it compares measured numbers that people
    # would look up: both tires BRR-tested at the same width, ranked in one
    # width class, and at least one of them picked for a race. Missing pairs
    # 301 to the first tire's page.
    by_id = {t["id"]: t for t in tire_db}

    def worth_a_page(pair):
        a, b = by_id[pair[0]], by_id[pair[1]]
        return bool((a.get("race_appearances") or b.get("race_appearances"))
                    and head_to_head(a, b))

    return sorted(p for p in pairs if worth_a_page(p))


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


def _knobs(test: dict) -> str:
    if test.get("knob_center_mm") is None and test.get("knob_edge_mm") is None:
        return "&mdash;"
    return f'{_num(test.get("knob_center_mm"))} / {_num(test.get("knob_edge_mm"), "mm")}'


def _test_link(test: dict) -> str:
    year = esc(test.get("year")) or "BRR"
    if not test.get("url"):
        return year
    return f'<a href="{esc(test["url"])}" target="_blank" rel="noopener">{year} &rarr;</a>'


def build_ranks_section(tire_a: dict, tire_b: dict, h2h: dict, verdict: str) -> str:
    """The verdict and each lab measure head to head, with both tires' ranks."""

    def cell(row, i):
        r = row["cells"][i]
        if not r:
            return "<td>&mdash;</td>"
        cls = ' class="tvs-winner-cell"' if row["leader"] == i else ""
        return (f'<td{cls}>{_num(r["value"], r["unit"])}'
                f'<span class="tvs-rank">{ordinal(r["rank"])} of {r["of"]}</span></td>')

    test_a, test_b = h2h["tests"]
    rows = "".join(f'<tr><td>{row["label"]}</td>{cell(row, 0)}{cell(row, 1)}</tr>'
                   for row in h2h["rows"])
    rows += (f'<tr><td>Measured width</td><td>{_num(test_a.get("measured_width_mm"), "mm")}</td>'
             f'<td>{_num(test_b.get("measured_width_mm"), "mm")}</td></tr>'
             f'<tr><td>Knobs center / edge</td><td>{_knobs(test_a)}</td><td>{_knobs(test_b)}</td></tr>'
             f'<tr><td>BRR test</td><td>{_test_link(test_a)}</td><td>{_test_link(test_b)}</td></tr>')
    meta = lab_meta()
    return f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">01 / HOW THEY RANK</span>
    <h2>How They Rank</h2>
    <p class="tvs-verdict">{esc(verdict)}</p>
    <table class="tvs-specs-table tvs-rank-table">
      <thead><tr><th>Lab measure</th><th>{esc(tire_a["name"])}</th><th>{esc(tire_b["name"])}</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <p class="tvs-lab-source">Ranked among the {h2h["pool"]} tires in our database BRR tested at {esc(h2h["class_label"])}. {esc(meta["protocol"])} Source: <a href="{esc(meta["source"])}" target="_blank" rel="noopener">bicyclerollingresistance.com</a>.</p>
  </div>
</section>'''


# The FAQ answers each lab measure from the numbers: (question, where measured).
FAQ_MEASURES = {
    "rr_watts": ("Is {a} or {b} faster?", "in BRR's {w} rolling resistance test"),
    "puncture_tread": ("Which is more puncture resistant, {a} or {b}?",
                       "in BRR's {w} tread puncture test"),
    "wet_grip": ("Which grips better in the wet, {a} or {b}?", "in BRR's {w} wet grip test"),
    "weight_g": ("Which is lighter, {a} or {b}?", "as weighed by BRR at {w}"),
}


def faq_pairs(tire_a: dict, tire_b: dict, h2h: dict) -> list:
    """(question, answer) pairs, every answer read off BRR's numbers or
    named as our call."""
    names = (tire_a["name"], tire_b["name"])
    width = _num(h2h["width"], "mm")
    pairs = []

    for row in h2h["rows"]:
        if None in row["cells"]:
            continue
        question, where = FAQ_MEASURES[row["key"]]
        where = where.format(w=width)
        vals = [_num(c["value"], row["unit"]) for c in row["cells"]]
        if row["leader"] is None:
            answer = f"Neither: both measured {vals[0]} {where}."
        else:
            i = row["leader"]
            answer = (f"{names[i]} {LEADS[row['key']]}: {vals[i]} against "
                      f"{vals[1 - i]} for {names[1 - i]} {where}.")
        pairs.append((question.format(a=names[0], b=names[1]), answer))

    mud = [t.get("mud_clearance") for t in (tire_a, tire_b)]
    if all(mud):
        answer = (f"Mud clearance is our call; BRR doesn't test it. We rate it "
                  f"{rating_label(mud[0])} for {names[0]} and {rating_label(mud[1])} for {names[1]}.")
        tests = h2h["tests"]
        if all(t.get(k) is not None for t in tests for k in ("knob_center_mm", "knob_edge_mm")):
            answer += (f" BRR measured knobs (center / edge) of {_knobs(tests[0])} on "
                       f"{names[0]} and {_knobs(tests[1])} on {names[1]}.")
        pairs.append((f"Which is better in mud, {names[0]} or {names[1]}?", answer))

    prices = [t.get("msrp_usd") for t in (tire_a, tire_b)]
    if all(prices):
        if prices[0] == prices[1]:
            answer = f"Neither: both list at ${prices[0]:.2f} MSRP."
        else:
            i = 0 if prices[0] < prices[1] else 1
            answer = (f"{names[i]} costs less: ${prices[i]:.2f} MSRP against "
                      f"${prices[1 - i]:.2f} for {names[1 - i]}.")
        pairs.append((f"Which costs less, {names[0]} or {names[1]}?", answer))

    return pairs


def build_faq(tire_a: dict, tire_b: dict, h2h: dict) -> tuple:
    """Build FAQ HTML and JSON-LD. Returns (html, jsonld_str)."""
    pairs = faq_pairs(tire_a, tire_b, h2h)
    faq_items = "".join(f'''<div class="tvs-faq-item">
      <h4>{esc(q)}</h4>
      <p>{esc(a)}</p>
    </div>''' for q, a in pairs)

    faq_html = f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">04 / FAQ</span>
    <h2>Frequently Asked Questions</h2>
    {faq_items}
  </div>
</section>'''

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
    # "</" would close the <script> early; "<\/" is the same JSON.
    return faq_html, json.dumps(faq_ld, indent=2).replace("</", "<\\/")


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

/* How they rank */
.tvs-verdict {
  font-family: var(--gg-font-editorial);
  font-size: 20px;
  line-height: 1.4;
  margin: 0 0 16px;
}
.tvs-rank-table td:nth-child(n+2) { white-space: nowrap; }
.tvs-rank {
  display: block;
  font-size: 11px;
  font-weight: 400;
  color: var(--gg-color-secondary-brown);
}
.tvs-lab-source {
  font-family: var(--gg-font-data);
  font-size: 12px;
  color: var(--gg-color-secondary-brown);
  margin: 8px 0 0;
}
.tvs-rank-table a { font-weight: 700; }

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
.tvs-overlap-label--a { color: var(--gg-color-primary-brown); }
.tvs-overlap-label--b { color: var(--gg-color-teal); }
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
  .tvs-specs-table th, .tvs-specs-table td { padding: 8px 10px; }
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
.tvs-review-card--a { border-top: 3px solid var(--gg-color-primary-brown); }
.tvs-review-card--b { border-top: 3px solid var(--gg-color-teal); }
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
    """What BRR doesn't measure: price and widths from the brands, and our
    calls, labelled as ours."""
    ours = " (our call)"
    pair = (tire_a, tire_b)

    def row(label, cells, classes=("", "")):
        tds = "".join(f"<td{c}>{v}</td>" for v, c in zip(cells, classes))
        return f"<tr><td>{label}</td>{tds}</tr>"

    prices = [t.get("msrp_usd") for t in pair]
    price_cls = ["", ""]
    if all(prices) and prices[0] != prices[1]:
        price_cls[0 if prices[0] < prices[1] else 1] = ' class="tvs-winner-cell"'

    rows = [
        row("MSRP", [f"${p:.2f}" if p else "&mdash;" for p in prices], price_cls),
        row("Widths", [", ".join(str(w) for w in t["widths_mm"]) + "mm" for t in pair]),
        row("Tubeless", ["Yes" if t.get("tubeless_ready") else "No" for t in pair]),
        row("Tread type" + ours, [esc(t.get("tread_type", "").title()) or "&mdash;" for t in pair]),
        row("Mud clearance" + ours, [esc(rating_label(t.get("mud_clearance", ""))) for t in pair]),
    ]

    return f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">02 / SPECS</span>
    <h2>Specs</h2>
    <table class="tvs-specs-table">
      <thead><tr><th>Spec</th><th>{esc(tire_a["name"])}</th><th>{esc(tire_b["name"])}</th></tr></thead>
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
        parts.append(f'''<div class="tvs-overlap-label tvs-overlap-label--both">BOTH PICKED ({len(overlap["both"])})</div>
    <div class="tvs-overlap-list">{chips}</div>''')

    if overlap["only_a"]:
        chips = "".join(
            f'<a href="/race/{esc(r["slug"])}/tires/" class="tvs-overlap-chip">{esc(r["name"])}</a>'
            for r in overlap["only_a"][:10]
        )
        parts.append(f'''<div class="tvs-overlap-label tvs-overlap-label--a">ONLY {esc(tire_a["name"]).upper()} ({len(overlap["only_a"])})</div>
    <div class="tvs-overlap-list">{chips}</div>''')

    if overlap["only_b"]:
        chips = "".join(
            f'<a href="/race/{esc(r["slug"])}/tires/" class="tvs-overlap-chip">{esc(r["name"])}</a>'
            for r in overlap["only_b"][:10]
        )
        parts.append(f'''<div class="tvs-overlap-label tvs-overlap-label--b">ONLY {esc(tire_b["name"]).upper()} ({len(overlap["only_b"])})</div>
    <div class="tvs-overlap-list">{chips}</div>''')

    return f'''<section class="tvs-section">
  <div class="tvs-container">
    <span class="tvs-section-num">03 / RACE PICKS</span>
    <h2>Where We Pick Them</h2>
    <div class="tvs-race-overlap">{"".join(parts)}</div>
  </div>
</section>'''


def build_email_capture() -> str:
    return '''<div class="tvs-email-capture">
    <div class="tvs-email-capture-inner">
      <div class="tvs-email-capture-badge">FREE</div>
      <h3 class="tvs-email-capture-title">GET A RACE DAY TIRE SETUP</h3>
      <p class="tvs-email-capture-text">Tire picks, pressure chart, sealant amounts, and tubeless tips &mdash; customized for any gravel race.</p>
      <form class="tvs-email-capture-form" id="tvs-email-capture-form" autocomplete="off">
        <input type="hidden" name="source" value="tire_guide">
        <input type="hidden" name="website" value="">
        <div class="tvs-email-capture-row">
          <input type="email" name="email" required placeholder="your@email.com" class="tvs-email-capture-input" aria-label="Email address">
          <button type="submit" class="tvs-email-capture-btn">SHOW TIRE SETUP</button>
        </div>
      </form>
      <div class="tvs-email-capture-success" id="tvs-email-capture-success" style="display:none">
        <p class="tvs-email-capture-check">&#10003; Tire setup unlocked!</p>
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
    var subBtn=form.querySelector('button[type=submit]');
    var errEl=document.getElementById('tvs-email-capture-err');
    if(!errEl){errEl=document.createElement('p');errEl.id='tvs-email-capture-err';errEl.className='tvs-email-capture-fine';form.parentNode.insertBefore(errEl,form.nextSibling);}
    errEl.style.display='none';
    if(subBtn) subBtn.disabled=true;
    var payload={email:email,source:form.source.value,website:form.website.value};
    /* Only claim success once the capture is actually stored. A swallowed
       error used to show the unlocked state for a lead nobody recorded. */
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:(typeof AbortSignal!=='undefined'&&AbortSignal.timeout)?AbortSignal.timeout(10000):undefined})
    .then(function(resp){
      if(!resp.ok) throw new Error('bad status');
      try{localStorage.setItem(LS_KEY,JSON.stringify({email:email,exp:Date.now()+EXPIRY_DAYS*86400000}));}catch(ex){}
      if(typeof gtag==='function') gtag('event','email_capture',{source:'tire_guide'});
      form.style.display='none';
      var success=document.getElementById('tvs-email-capture-success');
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
    h2h = head_to_head(tire_a, tire_b)
    if h2h is None:
        raise ValueError(f"{tire_a['id']} vs {tire_b['id']}: no BRR test at a shared width")
    verdict = verdict_sentence(tire_a, tire_b, h2h)
    overlap = get_race_overlap(tire_races, tire_a["id"], tire_b["id"])

    name_a = tire_a["name"]
    name_b = tire_b["name"]
    slug_a = tire_slug(tire_a)
    slug_b = tire_slug(tire_b)

    faq_html, faq_ld = build_faq(tire_a, tire_b, h2h)
    sections = number_sections("\n".join(part for part in (
        build_ranks_section(tire_a, tire_b, h2h, verdict),
        build_specs_comparison(tire_a, tire_b),
        build_race_overlap_section(tire_a, tire_b, overlap),
        faq_html,
        build_review_comparison(tire_a, tire_b),
    ) if part), prefix="tvs")
    email_capture = build_email_capture()
    inline_js = build_inline_js()

    breadcrumb_ld = build_json_ld(tire_a, tire_b)
    json_ld = f'''<script type="application/ld+json">{breadcrumb_ld}</script>
<script type="application/ld+json">{faq_ld}</script>'''

    title = f"{esc(name_a)} vs {esc(name_b)}: Which Gravel Tire Is Right? | Gravel God"
    meta_desc = verdict
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
      <a href="/">Gravel God</a> / <a href="/tire/">Tires</a> / Tire Comparison
    </div>
    <span class="tvs-badge">TIRE COMPARISON</span>
    <h1>{esc(name_a)} vs {esc(name_b)}</h1>
  </div>
</header>
<main>
{sections}
<section class="tvs-section">
  <div class="tvs-container">
    {email_capture}
  </div>
</section>
</main>
<footer class="tvs-footer-cta">
  <div class="tvs-container">
    <div class="tvs-footer-cta-inner">
      <a href="/tire/{slug_a}/" class="tvs-btn tvs-btn--primary">{esc(name_a)}</a>
      <a href="/tire/{slug_b}/" class="tvs-btn tvs-btn--outline">{esc(name_b)}</a>
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
