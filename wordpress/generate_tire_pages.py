#!/usr/bin/env python3
"""
Generate per-tire SEO pages at /tire/{tire-slug}/.

Each page shows BRR lab data, race recommendations, email capture,
and internal links to every race tire guide where the tire is recommended.

Usage:
    python wordpress/generate_tire_pages.py
    python wordpress/generate_tire_pages.py --output-dir /tmp/tire-pages
"""

import argparse
import html as html_mod
import json
import re
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
from season import season_year
from cookie_consent import get_consent_banner_html

from generate_tire_guide import load_tire_database

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "tire"
SEASON_YEAR = season_year()


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def _json_str(text) -> str:
    """Escape text for safe inclusion in JSON-LD strings."""
    return json.dumps(str(text))[1:-1] if text else ""


def tire_slug(tire: dict) -> str:
    """Generate URL slug from tire ID (strip trailing width suffixes)."""
    tid = tire["id"]
    # Use the ID directly — it's already a valid slug
    return tid


def rating_label(value: str) -> str:
    """Convert rating values to display labels."""
    return {
        "low": "Low", "moderate": "Moderate", "high": "High",
        "poor": "Poor", "fair": "Fair", "good": "Good",
        "none": "None",
    }.get(value, value.title() if value else "N/A")


def rating_color(value: str) -> str:
    """Return CSS color for rating value."""
    return {
        "high": COLORS["teal"], "good": COLORS["teal"],
        "moderate": COLORS["gold"], "fair": COLORS["gold"],
        "low": COLORS["secondary_brown"], "poor": COLORS["secondary_brown"],
        "none": COLORS["warm_brown"],
    }.get(value, COLORS["secondary_brown"])


# ── Data Loading ──────────────────────────────────────────────


INDEX_DIR = PROJECT_ROOT / "data" / "indexes"


def scan_race_recommendations(tire_db: list) -> dict:
    """Load tire→race associations from pre-computed index + race JSONs for why text.

    Uses data/indexes/tire-race-map.json for the tire→race list, then reads
    each referenced race JSON to get the 'why' text for display.

    Returns: {tire_id: [{"slug": ..., "name": ..., "rank": ..., "width": ..., "why": ..., "position": ...}, ...]}
    """
    tire_races = {t["id"]: [] for t in tire_db}

    # Load pre-computed index
    index_path = INDEX_DIR / "tire-race-map.json"
    if not index_path.exists():
        print("WARNING: tire-race-map.json not found — run scripts/rebuild_tire_indexes.py")
        return tire_races

    with open(index_path, "r", encoding="utf-8") as f:
        tire_race_map = json.load(f)

    # Collect all race slugs we need 'why' text from
    slugs_needed = set()
    for tid, data in tire_race_map.items():
        for entry in data.get("races", []):
            if entry.get("position") == "primary":
                slugs_needed.add(entry["slug"])

    # Batch-read 'why' text from race JSONs
    why_lookup = {}  # (slug, tire_id) → why text
    for slug in slugs_needed:
        race_path = RACE_DATA_DIR / f"{slug}.json"
        if not race_path.exists():
            continue
        try:
            rd = json.loads(race_path.read_text(encoding="utf-8"))
            race = rd.get("race", rd)
            tr = race.get("tire_recommendations", {})
            for rec in tr.get("primary", []):
                tid = rec.get("tire_id", "")
                if tid:
                    why_lookup[(slug, tid)] = rec.get("why", "")
        except (json.JSONDecodeError, OSError):
            continue

    # Build return structure
    for tid, data in tire_race_map.items():
        if tid not in tire_races:
            continue
        for entry in data.get("races", []):
            slug = entry["slug"]
            position = entry.get("position", "primary")
            why = why_lookup.get((slug, tid), "")
            if not why and position in ("front", "rear"):
                why = f"Recommended as {position} tire"
            tire_races[tid].append({
                "slug": slug,
                "name": entry.get("name", slug.replace("-", " ").title()),
                "rank": entry.get("rank", 0),
                "width": entry.get("width_mm", 40),
                "why": why,
                "position": position,
            })

    return tire_races


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

.tp-container { max-width: 820px; margin: 0 auto; padding: 0 20px; }

/* Header */
.tp-header {
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  padding: 48px 0 36px;
  border-bottom: 4px solid var(--gg-color-teal);
}
.tp-breadcrumb {
  font-family: var(--gg-font-data);
  font-size: 10px;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--gg-color-warm-brown);
  margin-bottom: 12px;
}
.tp-breadcrumb a { color: var(--gg-color-warm-brown); }
.tp-breadcrumb a:hover { color: var(--gg-color-teal); }
.tp-badge {
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
.tp-tread-badge {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  background: transparent;
  color: var(--gg-color-warm-paper);
  border: 2px solid var(--gg-color-warm-brown);
  padding: 2px 8px;
  margin-left: 8px;
}
.tp-header h1 {
  font-family: var(--gg-font-data);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: -0.5px;
  line-height: 1.2;
  margin: 8px 0;
}
@media (min-width: 640px) { .tp-header h1 { font-size: 36px; } }
.tp-vitals {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(255,255,255,0.15);
}
.tp-vital {
  font-family: var(--gg-font-data);
  font-size: 12px;
  color: var(--gg-color-tan);
}
.tp-vital strong {
  color: var(--gg-color-warm-paper);
  display: block;
  font-size: 14px;
}

/* Section styling */
.tp-section {
  padding: 40px 0;
  border-bottom: 1px solid var(--gg-color-tan);
}
.tp-section:last-of-type { border-bottom: none; }
.tp-section-num {
  font-family: var(--gg-font-data);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-teal);
  display: block;
  margin-bottom: 8px;
}
.tp-section h2 {
  font-family: var(--gg-font-data);
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.3px;
  margin-bottom: 20px;
}

/* Specs table */
.tp-specs-table {
  width: 100%;
  border-collapse: collapse;
  font-family: var(--gg-font-data);
  font-size: 13px;
  margin: 16px 0;
}
.tp-specs-table th {
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  padding: 10px 16px;
  text-align: left;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
}
.tp-specs-table td {
  padding: 10px 16px;
  border-bottom: 1px solid var(--gg-color-tan);
}
.tp-specs-table tr:nth-child(even) td { background: var(--gg-color-sand); }

/* Race list */
.tp-race-list { list-style: none; padding: 0; }
.tp-race-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--gg-color-tan);
  display: flex;
  align-items: baseline;
  gap: 12px;
}
.tp-race-item:last-child { border-bottom: none; }
.tp-race-rank {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tp-race-rank--1 { background: var(--gg-color-teal); }
.tp-race-rank--fr { background: var(--gg-color-primary-brown); font-size: 9px; }
.tp-race-info { flex: 1; }
.tp-race-name {
  font-family: var(--gg-font-data);
  font-size: 14px;
  font-weight: 700;
}
.tp-race-why {
  font-family: var(--gg-font-editorial);
  font-size: 12px;
  color: var(--gg-color-secondary-brown);
  margin-top: 2px;
}
.tp-race-width {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  background: var(--gg-color-sand);
  padding: 2px 8px;
  flex-shrink: 0;
}

/* Lab data */
.tp-table-scroll { overflow-x: auto; margin: 16px 0 0; }
.tp-table-scroll .tp-specs-table { margin: 0; }
.tp-lab-table th, .tp-lab-table td { padding: 8px 10px; white-space: nowrap; }
.tp-lab-table a { color: var(--gg-color-teal); font-weight: 700; }
.tp-lab-source {
  font-family: var(--gg-font-data);
  font-size: 12px;
  color: var(--gg-color-secondary-brown);
  margin: 8px 0 0;
}
.tp-lab-source a { color: var(--gg-color-teal); }
.tp-ratings-table { margin-top: 20px; }

/* How it ranks, where we pick it, who raced it */
.tp-verdict {
  font-family: var(--gg-font-editorial);
  font-size: 20px;
  line-height: 1.4;
  margin: 0 0 16px;
}
.tp-rank-table td:nth-child(n+2), .tp-course-table td:nth-child(2) {
  font-family: var(--gg-font-data);
  white-space: nowrap;
}
.tp-sub {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  margin: 24px 0 8px;
}
.tp-race-more { margin-top: 16px; border: 2px solid var(--gg-color-near-black); }
.tp-race-more summary {
  font-family: var(--gg-font-data);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 12px 16px;
  cursor: pointer;
}
.tp-race-more .tp-race-list { padding: 0 16px; }
.tp-podium-detail { font-size: 12px; color: var(--gg-color-secondary-brown); }

/* Email capture */
.tp-email-capture {
  border: 1px solid var(--gg-color-tan);
  border-top: 3px solid var(--gg-color-teal);
  background: var(--gg-color-white);
  padding: 0;
  margin: 16px 0;
}
.tp-email-capture-inner { padding: 24px 32px; text-align: center; }
.tp-email-capture-badge { display: inline-block; font-family: var(--gg-font-data); font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; background: var(--gg-color-teal); color: var(--gg-color-white); padding: 3px 10px; margin-bottom: 8px; }
.tp-email-capture-title { font-family: var(--gg-font-data); font-size: 14px; font-weight: 700; letter-spacing: 3px; color: var(--gg-color-near-black); margin: 0 0 4px 0; }
.tp-email-capture-text { font-family: var(--gg-font-editorial); font-size: 12px; color: var(--gg-color-secondary-brown); line-height: 1.6; margin: 0 0 16px 0; max-width: 500px; margin-left: auto; margin-right: auto; }
.tp-email-capture-row { display: flex; gap: 0; max-width: 420px; margin: 0 auto 8px; }
.tp-email-capture-input { flex: 1; font-family: var(--gg-font-data); font-size: 13px; padding: 12px 14px; border: 2px solid var(--gg-color-tan); border-right: none; background: var(--gg-color-white); color: var(--gg-color-near-black); min-width: 0; }
.tp-email-capture-input:focus { outline: none; border-color: var(--gg-color-teal); }
.tp-email-capture-btn { font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; padding: 12px 18px; background: var(--gg-color-teal); color: var(--gg-color-white); border: 2px solid var(--gg-color-teal); cursor: pointer; white-space: nowrap; transition: background 0.2s; }
.tp-email-capture-btn:hover { background: var(--gg-color-light-teal); }
.tp-email-capture-fine { font-family: var(--gg-font-data); font-size: 10px; color: var(--gg-color-warm-brown); letter-spacing: 1px; margin: 0; }
.tp-email-capture-success { padding: 8px 0; }
.tp-email-capture-check { font-family: var(--gg-font-data); font-size: 14px; font-weight: 700; color: var(--gg-color-teal); margin: 0 0 8px; }
.tp-email-capture-link { display: inline-block; font-family: var(--gg-font-data); font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: var(--gg-color-white); background: var(--gg-color-teal); padding: 10px 20px; text-decoration: none; border: 2px solid var(--gg-color-teal); transition: background 0.2s; }
.tp-email-capture-link:hover { background: var(--gg-color-light-teal); text-decoration: none; }

/* Footer CTA */
.tp-footer-cta {
  background: var(--gg-color-near-black);
  padding: 40px 0;
}
.tp-footer-cta-inner {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  justify-content: center;
}
.tp-btn {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 12px 24px;
  text-decoration: none;
  transition: all 0.2s;
}
.tp-btn--primary { background: var(--gg-color-teal); color: var(--gg-color-white); border: 2px solid var(--gg-color-teal); }
.tp-btn--primary:hover { background: transparent; color: var(--gg-color-teal); text-decoration: none; }
.tp-btn--outline { background: transparent; color: var(--gg-color-warm-paper); border: 2px solid var(--gg-color-warm-paper); }
.tp-btn--outline:hover { background: var(--gg-color-warm-paper); color: var(--gg-color-near-black); text-decoration: none; }

/* Internal links */
.tp-internal-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tp-internal-link {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  color: var(--gg-color-teal);
  padding: 4px 10px;
  border: 1px solid var(--gg-color-tan);
  text-decoration: none;
  transition: border-color 0.2s;
}
.tp-internal-link:hover { border-color: var(--gg-color-teal); text-decoration: none; }

@media (max-width: 480px) {
  .tp-email-capture-row { flex-direction: column; gap: 8px; }
  .tp-email-capture-input { border-right: 2px solid var(--gg-color-tan); }
  .tp-race-item { flex-direction: column; gap: 4px; }
}

/* Community Reviews */
.tp-rev-summary { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.tp-rev-avg { font-family: var(--gg-font-data); font-size: 28px; font-weight: 700; color: var(--gg-color-near-black); }
.tp-rev-stars-display { color: var(--gg-color-gold); font-size: 20px; letter-spacing: 2px; }
.tp-rev-count { font-family: var(--gg-font-data); font-size: 12px; color: var(--gg-color-secondary-brown); }

.tp-rev-card {
  border: 1px solid var(--gg-color-tan);
  padding: 16px 20px;
  margin-bottom: 12px;
  background: var(--gg-color-white);
}
.tp-rev-card-stars { color: var(--gg-color-gold); font-size: 14px; letter-spacing: 1px; margin-bottom: 6px; }
.tp-rev-card-meta {
  font-family: var(--gg-font-data);
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.tp-rev-card-meta span { background: var(--gg-color-sand); padding: 2px 6px; }
.tp-rev-card-text { font-family: var(--gg-font-editorial); font-size: 13px; line-height: 1.5; color: var(--gg-color-near-black); }
.tp-rev-card-recommend {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-top: 8px;
}
.tp-rev-card-recommend--yes { color: var(--gg-color-teal); }
.tp-rev-card-recommend--no { color: var(--gg-color-secondary-brown); }

.tp-rev-empty, .tp-rev-pending {
  font-family: var(--gg-font-data);
  font-size: 13px;
  color: var(--gg-color-secondary-brown);
  margin-bottom: 20px;
}

/* Review Form */
.tp-rev-form-wrap { margin-top: 24px; border-top: 1px solid var(--gg-color-tan); padding-top: 24px; }
.tp-rev-form-title {
  font-family: var(--gg-font-data);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-bottom: 16px;
}
.tp-rev-star-row { display: flex; gap: 4px; margin-bottom: 16px; }
.tp-rev-star-btn {
  background: none;
  border: none;
  font-size: 28px;
  color: var(--gg-color-tan);
  cursor: pointer;
  padding: 0 2px;
  transition: color 0.15s;
}
.tp-rev-star-btn.is-active { color: var(--gg-color-gold); }
.tp-rev-field-label {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  display: block;
  margin-bottom: 4px;
}
.tp-rev-form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}
.tp-rev-field label {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  display: block;
  margin-bottom: 4px;
}
.tp-rev-input, .tp-rev-select {
  width: 100%;
  font-family: var(--gg-font-data);
  font-size: 13px;
  padding: 10px 12px;
  border: 2px solid var(--gg-color-tan);
  background: var(--gg-color-white);
  color: var(--gg-color-near-black);
}
.tp-rev-input:focus, .tp-rev-select:focus, .tp-rev-textarea:focus {
  outline: none;
  border-color: var(--gg-color-teal);
}
.tp-rev-conditions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.tp-rev-cond-label {
  font-family: var(--gg-font-data);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
}
.tp-rev-field--full { margin-bottom: 12px; }
.tp-rev-textarea {
  width: 100%;
  font-family: var(--gg-font-data);
  font-size: 13px;
  padding: 10px 12px;
  border: 2px solid var(--gg-color-tan);
  background: var(--gg-color-white);
  color: var(--gg-color-near-black);
  resize: vertical;
}
.tp-rev-charcount {
  font-family: var(--gg-font-data);
  font-size: 10px;
  color: var(--gg-color-warm-brown);
  text-align: right;
  display: block;
  margin-top: 2px;
}
.tp-rev-submit {
  font-family: var(--gg-font-data);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 2px;
  padding: 12px 24px;
  background: var(--gg-color-teal);
  color: var(--gg-color-white);
  border: 2px solid var(--gg-color-teal);
  cursor: pointer;
  transition: background 0.2s;
  margin-top: 4px;
}
.tp-rev-submit:hover { background: var(--gg-color-light-teal); }
.tp-rev-success { display: none; padding: 16px 0; }
.tp-rev-success-icon {
  font-size: 24px;
  color: var(--gg-color-teal);
  margin-bottom: 8px;
}
.tp-rev-success-text {
  font-family: var(--gg-font-data);
  font-size: 13px;
  color: var(--gg-color-secondary-brown);
}
.tp-rev-error {
  padding: 12px 0;
}
.tp-rev-error-text {
  font-family: var(--gg-font-data);
  font-size: 13px;
  color: #c0392b;
  font-weight: 600;
}
.tp-rev-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .tp-rev-form-row { grid-template-columns: 1fr; }
}

@media print {
  .tp-footer-cta, .tp-email-capture, .tp-rev-form-wrap { display: none; }
}
"""


# ── HTML Builders ─────────────────────────────────────────────


def page_title(tire: dict) -> str:
    """We cite lab data and pick races; we don't test tires ourselves, so the
    title never says "Review"."""
    if tire.get("lab_tested"):
        return f"{tire['name']}: Rolling Resistance, Race Picks & Pressure | Gravel God"
    return f"{tire['name']}: Specs, Race Picks & Pressure | Gravel God"


def page_description(tire: dict, ranks, race_recs: list) -> str:
    """The verdict, for search results: lab ranks first, then our picks."""
    rank1, top3 = pick_counts(race_recs)
    if rank1:
        picks = f"Our #1 pick at {rank1} gravel races."
    elif top3:
        picks = f"In our top 3 at {top3} gravel races."
    else:
        picks = "Not one of our race picks yet."
    if ranks:
        return f"{tire['name']} in BRR lab tests: {rank_sentence(ranks)}. {picks}"
    return f"{tire['name']}: No lab test yet. {picks}"


def build_header(tire: dict) -> str:
    widths = ", ".join(f"{w}mm" for w in tire["widths_mm"])
    msrp_html = (f'\n      <div class="tp-vital"><strong>${tire["msrp_usd"]:.2f}</strong>MSRP</div>'
                 if tire.get("msrp_usd") else "")
    return f'''<header class="tp-header">
  <div class="tp-container">
    <div class="tp-breadcrumb">
      <a href="/">Gravel God</a> / <a href="/tire/">Tires</a> / {esc(tire["name"])}
    </div>
    <span class="tp-tread-badge">{esc(tire["tread_type"].upper())} TREAD</span>
    <h1>{esc(tire["name"])}</h1>
    <div class="tp-vitals">
      <div class="tp-vital"><strong>{esc(tire["brand"])}</strong>Brand</div>
      <div class="tp-vital"><strong>{widths}</strong>Widths</div>{msrp_html}
      <div class="tp-vital"><strong>{"Yes" if tire.get("tubeless_ready") else "No"}</strong>Tubeless</div>
    </div>
  </div>
</header>'''


LAB_SNAPSHOT = PROJECT_ROOT / "data" / "tires" / "lab" / "brr-cx-gravel.json"
_lab_meta = None


def lab_meta() -> dict:
    """Source URL and test protocol of the BRR snapshot the lab numbers come from."""
    global _lab_meta
    if _lab_meta is None:
        snap = json.loads(LAB_SNAPSHOT.read_text(encoding="utf-8"))
        _lab_meta = {"source": snap["source"], "protocol": snap["protocol"]}
    return _lab_meta


def _num(v, unit: str = "") -> str:
    """40.0 -> '40', 38.5 -> '38.5'; missing -> an em dash."""
    if v is None or v == "":
        return "&mdash;"
    return f"{float(v):g}{unit}"


def build_lab_row(t: dict) -> str:
    knobs = (f'{_num(t.get("knob_center_mm"))} / {_num(t.get("knob_edge_mm"), "mm")}'
             if t.get("knob_center_mm") is not None or t.get("knob_edge_mm") is not None
             else "&mdash;")
    rr = (f'{_num(t["rr_watts"], "W")} @ {_num(t.get("test_psi"), " psi")}'
          if t.get("rr_watts") is not None else "&mdash;")
    year = esc(t.get("year")) or "BRR"
    link = (f'<a href="{esc(t["url"])}" target="_blank" rel="noopener">{year} &rarr;</a>'
            if t.get("url") else year)
    return (f'<tr><td>{_num(t["width_mm"], "mm")}</td>'
            f'<td>{_num(t.get("measured_width_mm"), "mm")}</td>'
            f'<td>{_num(t.get("weight_g"), "g")}</td>'
            f'<td>{rr}</td>'
            f'<td>{_num(t.get("puncture_tread"))}</td>'
            f'<td>{_num(t.get("wet_grip"))}</td>'
            f'<td>{knobs}</td>'
            f'<td>{link}</td></tr>')


def build_specs_section(tire: dict) -> str:
    tested = bool(tire.get("lab_tested"))
    if tested:
        meta = lab_meta()
        rows = "".join(build_lab_row(t) for t in tire.get("brr_tests", []))
        lab_html = f'''<div class="tp-table-scroll">
    <table class="tp-specs-table tp-lab-table">
      <thead><tr><th>Width</th><th>Measured</th><th>Weight</th><th>Rolling resistance</th><th>Puncture (tread)</th><th>Wet grip</th><th>Knobs center / edge</th><th>BRR test</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    </div>
    <p class="tp-lab-source">Source: <a href="{esc(meta["source"])}" target="_blank" rel="noopener">bicyclerollingresistance.com</a>. {esc(meta["protocol"])}</p>'''
    else:
        lab_html = '<p class="tp-lab-source">Not lab-tested at race widths.</p>'

    # Puncture and wet labels are read off the lab numbers when there are any;
    # otherwise they are our call, like mud clearance and tread type.
    ours = " (our call)"
    ratings = [
        ("Puncture resistance" + ("" if tested else ours), tire.get("puncture_resistance")),
        ("Wet traction" + ("" if tested else ours), tire.get("wet_traction")),
        ("Mud clearance" + ours, tire.get("mud_clearance")),
    ]
    rating_rows = "".join(
        f'<tr><td>{label}</td><td style="color:{rating_color(value)}">{esc(rating_label(value))}</td></tr>'
        for label, value in ratings if value
    )
    if tire.get("tread_type"):
        rating_rows += f'<tr><td>Tread type{ours}</td><td>{esc(tire["tread_type"].title())}</td></tr>'

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">02 / LAB DATA</span>
    <h2>Lab Data by Width</h2>
    {lab_html}
    <table class="tp-specs-table tp-ratings-table">
      <thead><tr><th>Rating</th><th>Value</th></tr></thead>
      <tbody>{rating_rows}</tbody>
    </table>
  </div>
</section>'''


# ── How it ranks: each BRR test against every lab-tested tire ─

WIDTH_CLASSES = (  # (nominal mm, min, max, label)
    (40, 35, 42, "35–42mm"),
    (45, 43, 47, "43–47mm"),
    (50, 48, 60, "48mm and wider"),
)
RANK_MEASURES = (  # (test key, table label, sentence noun, unit, lower is better)
    ("rr_watts", "Rolling resistance", "rolling resistance", " W", True),
    ("puncture_tread", "Puncture (tread)", "puncture resistance", "", False),
    ("wet_grip", "Wet grip", "wet grip", "", False),
    ("weight_g", "Weight", "weight", " g", True),
)
_lab_pool = None


def width_class(width_mm):
    for nominal, lo, hi, _ in WIDTH_CLASSES:
        if width_mm and lo <= width_mm <= hi:
            return nominal
    return None


def tests_by_class(tire: dict) -> dict:
    """One BRR test per width class: the one nearest the class's nominal width."""
    out = {}
    for t in tire.get("brr_tests", []):
        cls = width_class(t.get("width_mm"))
        if cls and (cls not in out
                    or abs(t["width_mm"] - cls) < abs(out[cls]["width_mm"] - cls)):
            out[cls] = t
    return out


def lab_pool() -> dict:
    """tire id -> tests by width class, for every lab-tested tire in the database."""
    global _lab_pool
    if _lab_pool is None:
        _lab_pool = {t["id"]: tests_by_class(t) for t in load_tire_database()
                     if t.get("lab_tested")}
    return _lab_pool


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def tire_ranks(tire: dict):
    """Rank the tire's BRR test against every lab-tested tire in one width
    class: the class with the most tested tires (ties go wider). None when the
    tire has no lab test."""
    mine = tests_by_class(tire) if tire.get("lab_tested") else {}
    if not mine:
        return None
    pool = {**lab_pool(), tire["id"]: mine}
    cls = max(mine, key=lambda c: (sum(1 for tests in pool.values() if c in tests), c))
    test = mine[cls]
    rows = []
    for key, label, noun, unit, lower in RANK_MEASURES:
        value = test.get(key)
        if value is None:
            continue
        others = [tests[cls][key] for tid, tests in pool.items()
                  if tid != tire["id"] and cls in tests and tests[cls].get(key) is not None]
        better = sum(1 for o in others if (o < value if lower else o > value))
        rows.append({"label": label, "noun": noun, "value": value, "unit": unit,
                     "rank": better + 1, "of": len(others) + 1})
    if not rows:
        return None
    label = next(lbl for nominal, _, _, lbl in WIDTH_CLASSES if nominal == cls)
    return {"width_class": cls, "class_label": label, "test": test, "rows": rows}


def _join(words: list) -> str:
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def rank_sentence(ranks: dict) -> str:
    """'top third for wet grip; bottom third for puncture resistance'."""
    top = [r["noun"] for r in ranks["rows"] if r["rank"] <= r["of"] / 3]
    bottom = [r["noun"] for r in ranks["rows"] if r["rank"] > r["of"] * 2 / 3]
    parts = []
    if top:
        parts.append(f"top third for {_join(top)}")
    if bottom:
        parts.append(f"bottom third for {_join(bottom)}")
    return "; ".join(parts) or "middle third on every lab measure"


def build_ranks_section(ranks) -> str:
    if not ranks:
        body = '<p class="tp-verdict">No lab test yet.</p>'
    else:
        phrase = rank_sentence(ranks)
        test = ranks["test"]
        rows = "".join(
            f'<tr><td>{r["label"]}</td><td>{_num(r["value"], r["unit"])}</td>'
            f'<td>{ordinal(r["rank"])} of {r["of"]}</td></tr>'
            for r in ranks["rows"])
        pool = max(r["of"] for r in ranks["rows"])
        width = _num(test["width_mm"], "mm")
        test_link = (f'<a href="{esc(test["url"])}" target="_blank" rel="noopener">{width} test</a>'
                     if test.get("url") else f"{width} test")
        body = f'''<p class="tp-verdict">{esc(phrase[0].upper() + phrase[1:])}.</p>
    <table class="tp-specs-table tp-rank-table">
      <thead><tr><th>Lab measure</th><th>Result</th><th>Rank</th></tr></thead>
      <tbody>{rows}</tbody>
    </table>
    <p class="tp-lab-source">BRR's {test_link}, ranked among the {pool} tires in our database BRR tested at {esc(ranks["class_label"])}.</p>'''
    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">01 / HOW IT RANKS</span>
    <h2>How It Ranks</h2>
    {body}
  </div>
</section>'''


# ── Where we pick it: the race picks, summarized ──────────────

PROFILE_LABELS = (("mixed", "Mixed surface"), ("technical", "Technical"),
                  ("muddy", "Muddy"), ("wet", "Wet"), ("fast", "Fast"))
_race_meta = None


def race_meta() -> dict:
    """slug -> name, tier and surface profile for every race with tire picks."""
    global _race_meta
    if _race_meta is None:
        _race_meta = {}
        for path in RACE_DATA_DIR.glob("*.json"):
            try:
                race = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            race = race.get("race", race)
            picks = race.get("tire_recommendations") or {}
            if not picks.get("primary"):
                continue
            rating = race.get("gravel_god_rating") or {}
            _race_meta[path.stem] = {"name": race.get("name") or path.stem,
                                     "tier": rating.get("tier"),
                                     "profile": picks.get("race_surface_profile") or "mixed"}
    return _race_meta


def _race_item(rec: dict) -> str:
    if rec["position"] == "primary" and rec["rank"] == 1:
        rank_class, rank_text = "tp-race-rank tp-race-rank--1", "#1"
    elif rec["position"] == "primary":
        rank_class, rank_text = "tp-race-rank", f"#{rec['rank']}"
    else:
        rank_class, rank_text = "tp-race-rank tp-race-rank--fr", rec["position"].upper()[:2]
    why_html = f'<div class="tp-race-why">{esc(rec["why"])}</div>' if rec.get("why") else ""
    return f'''<li class="tp-race-item">
      <span class="{rank_class}">{rank_text}</span>
      <div class="tp-race-info">
        <a href="/race/{esc(rec["slug"])}/tires/" class="tp-race-name">{esc(rec["name"])}</a>
        {why_html}
      </div>
      <span class="tp-race-width">{rec["width"]}mm</span>
    </li>'''


RACE_LIST_OPEN_MAX = 12


def pick_counts(race_recs: list) -> tuple:
    """(#1 picks, top-3 picks) across the race guides."""
    primary = [r for r in race_recs if r["position"] == "primary"]
    return sum(1 for r in primary if r["rank"] == 1), len(primary)


def build_where_we_pick_section(race_recs: list) -> str:
    races = race_meta()
    rank1, top3 = pick_counts(race_recs)
    split = len(race_recs) - top3
    if rank1:
        summary = f"#1 pick at {rank1} of {len(races)} races; top 3 at {top3}."
    elif top3:
        summary = f"Top 3 at {top3} of {len(races)} races, never #1."
    else:
        summary = f"Not in our top 3 at any of the {len(races)} races."
    if split:
        summary += f" Front/rear split at {split}."

    courses = ""
    if top3:
        picked = {r["slug"] for r in race_recs if r["position"] == "primary"}
        rows = []
        for key, label in PROFILE_LABELS:
            slugs = [slug for slug, meta in races.items() if meta["profile"] == key]
            if slugs:
                rows.append(f"<tr><td>{label}</td>"
                            f"<td>{sum(1 for slug in slugs if slug in picked)} of {len(slugs)}</td></tr>")
        courses = f'''<table class="tp-specs-table tp-course-table">
      <thead><tr><th>Course</th><th>Top 3 at</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>'''

    ordered = sorted(race_recs, key=lambda r: (r["position"] != "primary", r.get("rank") or 9, r["name"]))
    if len(ordered) <= RACE_LIST_OPEN_MAX:
        lists = f'<ul class="tp-race-list">{"".join(_race_item(r) for r in ordered)}</ul>' if ordered else ""
    else:
        top_tier = [r for r in ordered if races.get(r["slug"], {}).get("tier") == 1]
        lists = (f'<h3 class="tp-sub">Tier 1 races</h3>'
                 f'<ul class="tp-race-list">{"".join(_race_item(r) for r in top_tier)}</ul>'
                 if top_tier else "")
        lists += (f'<details class="tp-race-more"><summary>All {len(ordered)} races</summary>'
                  f'<ul class="tp-race-list">{"".join(_race_item(r) for r in ordered)}</ul></details>')

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">03 / RACE PICKS</span>
    <h2>Where We Pick It</h2>
    <p class="tp-verdict">{esc(summary)}</p>
    {courses}
    {lists}
  </div>
</section>'''


# ── Who raced it: sourced podium setups ───────────────────────


def build_who_raced_section(tire: dict) -> str:
    """Podium riders on this tire, from the sourced podium file. A row counts
    only when the source names this exact tire."""
    from generate_tire_guide import load_podiums, podium_width
    races = race_meta()
    rows = []
    for slug, podium in sorted(load_podiums().items()):
        for e in podium.get("entries", []):
            if e.get("tire") != tire["name"]:
                continue
            detail = "; ".join(x for x in (podium_width(e), e.get("pressure"), e.get("note")) if x)
            source = (f'<a href="{esc(e["source_url"])}" target="_blank" rel="noopener">'
                      f'{esc(e["source_name"])}</a>')
            if e.get("source_type") in ("brand", "rider"):
                source += f' ({esc(e["source_type"])})'
            race_name = races.get(slug, {}).get("name", slug)
            rows.append(
                f'<tr><td><a href="/race/{esc(slug)}/tires/">{esc(race_name)} '
                f'{esc(podium["edition_year"])}</a><br>{esc(e["category"].title())} {esc(e["place"])}</td>'
                f'<td><strong>{esc(e["rider"])}</strong><br>'
                f'<span class="tp-podium-detail">{esc(detail)}</span></td>'
                f'<td>{source}</td></tr>')
    if not rows:
        return ""
    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">04 / PODIUMS</span>
    <h2>Who Raced It</h2>
    <div class="tp-table-scroll">
    <table class="tp-specs-table">
      <thead><tr><th>Race</th><th>Rider</th><th>Source</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    </div>
  </div>
</section>'''


def build_tire_review_form(tire: dict) -> str:
    """Build the tire review submission form."""
    tid = tire["id"]
    name = tire["name"]
    width_options = "".join(
        f'<option value="{w}">{w}mm</option>' for w in tire["widths_mm"]
    )
    return f'''<div class="tp-rev-form-wrap" id="tp-rev-form-wrap">
      <h3 class="tp-rev-form-title">RATE THE {esc(name.upper())}</h3>
      <form class="tp-rev-form" id="tp-rev-form" autocomplete="off">
        <input type="hidden" name="tire_id" value="{esc(tid)}">
        <input type="hidden" name="tire_name" value="{esc(name)}">
        <input type="hidden" name="website" value="">
        <div>
          <label class="tp-rev-field-label" id="tp-rev-star-label">Overall Rating <span style="color:var(--gg-color-teal)">*</span></label>
          <div class="tp-rev-star-row" role="radiogroup" aria-labelledby="tp-rev-star-label">
            {"".join(f'<button type="button" class="tp-rev-star-btn" data-star="{i}" role="radio" aria-checked="false" aria-label="{i} star{"s" if i>1 else ""}">&#9733;</button>' for i in range(1, 6))}
          </div>
          <input type="hidden" name="stars" id="tp-rev-stars-val" value="">
        </div>
        <div class="tp-rev-form-row">
          <div class="tp-rev-field">
            <label for="tp-rev-email">Email <span style="color:var(--gg-color-teal)">*</span></label>
            <input type="email" id="tp-rev-email" name="email" required placeholder="you@example.com" class="tp-rev-input">
          </div>
          <div class="tp-rev-field">
            <label for="tp-rev-width">Width Ridden</label>
            <select id="tp-rev-width" name="width_ridden" class="tp-rev-select">
              <option value="">Select</option>
              {width_options}
            </select>
          </div>
        </div>
        <div class="tp-rev-form-row">
          <div class="tp-rev-field">
            <label for="tp-rev-pressure">Pressure (PSI)</label>
            <input type="number" id="tp-rev-pressure" name="pressure_psi" min="15" max="60" placeholder="e.g. 28" class="tp-rev-input">
          </div>
          <div class="tp-rev-field">
            <label for="tp-rev-recommend">Would Recommend?</label>
            <select id="tp-rev-recommend" name="would_recommend" class="tp-rev-select">
              <option value="">Select</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          </div>
        </div>
        <div>
          <label class="tp-rev-field-label">Conditions Ridden</label>
          <div class="tp-rev-conditions">
            <label class="tp-rev-cond-label"><input type="checkbox" name="conditions" value="dry"> Dry</label>
            <label class="tp-rev-cond-label"><input type="checkbox" name="conditions" value="mixed"> Mixed</label>
            <label class="tp-rev-cond-label"><input type="checkbox" name="conditions" value="wet"> Wet</label>
            <label class="tp-rev-cond-label"><input type="checkbox" name="conditions" value="mud"> Mud</label>
          </div>
        </div>
        <div class="tp-rev-form-row">
          <div class="tp-rev-field">
            <label for="tp-rev-race">Race Used At</label>
            <input type="text" id="tp-rev-race" name="race_used_at" maxlength="100" placeholder="e.g. Unbound 200" class="tp-rev-input">
          </div>
        </div>
        <div class="tp-rev-field tp-rev-field--full">
          <label for="tp-rev-text">Review</label>
          <textarea id="tp-rev-text" name="review_text" maxlength="500" rows="3" class="tp-rev-textarea" placeholder="How did it perform?"></textarea>
          <span class="tp-rev-charcount" data-for="tp-rev-text">0/500</span>
        </div>
        <button type="submit" class="tp-rev-submit" id="tp-rev-submit-btn">SUBMIT REVIEW</button>
      </form>
      <div class="tp-rev-success" id="tp-rev-success">
        <div class="tp-rev-success-icon">&#10003;</div>
        <p class="tp-rev-success-text">Review submitted &mdash; thank you!</p>
      </div>
      <div class="tp-rev-error" id="tp-rev-error" style="display:none;">
        <p class="tp-rev-error-text" id="tp-rev-error-text"></p>
      </div>
    </div>'''


def _render_review_card(r: dict) -> str:
    """Render a single review card with safe escaping on all user fields."""
    # Fix #13: Clamp stars to 1-5 range to prevent rendering bugs
    stars = max(1, min(5, int(r.get("stars", 0)))) if isinstance(r.get("stars"), (int, float)) else 0
    if stars == 0:
        return ""  # Skip reviews with invalid stars
    r_stars = "&#9733;" * stars + "&#9734;" * (5 - stars)

    # Fix #12: Escape ALL user-sourced fields, not just some
    meta_parts = []
    if r.get("width_ridden"):
        meta_parts.append(f'<span>{esc(str(r["width_ridden"]))}mm</span>')
    if r.get("pressure_psi"):
        meta_parts.append(f'<span>{esc(str(r["pressure_psi"]))} psi</span>')
    if r.get("conditions") and isinstance(r["conditions"], list):
        meta_parts.append(f'<span>{esc(", ".join(str(c) for c in r["conditions"]))}</span>')
    if r.get("race_used_at"):
        meta_parts.append(f'<span>{esc(str(r["race_used_at"]))}</span>')
    meta_html = "".join(meta_parts)

    text_html = f'<div class="tp-rev-card-text">{esc(str(r["review_text"]))}</div>' if r.get("review_text") else ""

    rec_html = ""
    if r.get("would_recommend") == "yes":
        rec_html = '<div class="tp-rev-card-recommend tp-rev-card-recommend--yes">&#10003; Would recommend</div>'
    elif r.get("would_recommend") == "no":
        rec_html = '<div class="tp-rev-card-recommend tp-rev-card-recommend--no">&#10007; Would not recommend</div>'

    return f'''<div class="tp-rev-card">
      <div class="tp-rev-card-stars">{r_stars}</div>
      <div class="tp-rev-card-meta">{meta_html}</div>
      {text_html}
      {rec_html}
    </div>'''


def build_community_reviews_section(tire: dict) -> str:
    """Build community reviews section with 3 display states."""
    reviews = [r for r in tire.get("community_reviews", []) if r.get("approved")]
    # Fix #13: Filter out reviews with invalid stars before counting
    reviews = [r for r in reviews if isinstance(r.get("stars"), (int, float)) and 1 <= r["stars"] <= 5]
    total = len(reviews)
    name = tire["name"]
    form = build_tire_review_form(tire)
    threshold = 3

    # Empty state
    if total == 0:
        return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">04 / COMMUNITY REVIEWS</span>
    <h2>Community Reviews</h2>
    <p class="tp-rev-empty">No community reviews yet. Be the first to rate the {esc(name)}.</p>
    {form}
  </div>
</section>'''

    # Fix #14: Pending state now shows review cards (just no aggregate)
    sorted_reviews = sorted(reviews, key=lambda r: r.get("submitted_at", ""), reverse=True)

    if total < threshold:
        needed = threshold - total
        cards = [_render_review_card(r) for r in sorted_reviews[:5]]
        cards = [c for c in cards if c]  # filter empty (invalid stars)
        return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">04 / COMMUNITY REVIEWS</span>
    <h2>Community Reviews</h2>
    <p class="tp-rev-pending">{total} review{"s" if total != 1 else ""} so far &mdash; {needed} more needed to display the community rating.</p>
    {"".join(cards)}
    {form}
  </div>
</section>'''

    # Full display: aggregate + cards + form
    avg = sum(r["stars"] for r in reviews) / total
    full_stars = int(avg)
    half = (avg - full_stars) >= 0.5
    stars_html = "&#9733;" * full_stars
    if half:
        stars_html += "&#9733;"
        empty = 5 - full_stars - 1
    else:
        empty = 5 - full_stars
    stars_html += "&#9734;" * empty

    cards = [_render_review_card(r) for r in sorted_reviews[:5]]
    cards = [c for c in cards if c]

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">04 / COMMUNITY REVIEWS</span>
    <h2>Community Reviews</h2>
    <div class="tp-rev-summary">
      <span class="tp-rev-avg">{avg:.1f}</span>
      <span class="tp-rev-stars-display">{stars_html}</span>
      <span class="tp-rev-count">{total} review{"s" if total != 1 else ""}</span>
    </div>
    {"".join(cards)}
    {form}
  </div>
</section>'''


def build_email_capture() -> str:
    return '''<div class="tp-email-capture">
    <div class="tp-email-capture-inner">
      <div class="tp-email-capture-badge">FREE</div>
      <h3 class="tp-email-capture-title">GET A RACE DAY TIRE SETUP</h3>
      <p class="tp-email-capture-text">Tire picks, pressure chart, sealant amounts, and tubeless tips &mdash; customized for any gravel race.</p>
      <form class="tp-email-capture-form" id="tp-email-capture-form" autocomplete="off">
        <input type="hidden" name="source" value="tire_guide">
        <input type="hidden" name="website" value="">
        <div class="tp-email-capture-row">
          <input type="email" name="email" required placeholder="your@email.com" class="tp-email-capture-input" aria-label="Email address">
          <button type="submit" class="tp-email-capture-btn">SHOW TIRE SETUP</button>
        </div>
      </form>
      <div class="tp-email-capture-success" id="tp-email-capture-success" style="display:none">
        <p class="tp-email-capture-check">&#10003; Tire setup unlocked!</p>
        <a href="/gravel-races/" class="tp-email-capture-link">Find Your Race &rarr;</a>
      </div>
      <p class="tp-email-capture-fine">No spam. Unsubscribe anytime.</p>
    </div>
  </div>'''


def build_internal_links_section(tire: dict, race_recs: list,
                                comparisons: list = ()) -> str:
    """Race tire guides plus this tire's head-to-head pages.

    ``comparisons`` is a list of (vs_slug, other_tire_name). Without these
    links the /tire/{a}-vs-{b}/ pages had no inbound links at all.
    """
    if not race_recs and not comparisons:
        return ""

    links = []
    for rec in sorted(race_recs, key=lambda r: r["name"])[:20]:
        links.append(
            f'<a href="/race/{esc(rec["slug"])}/tires/" class="tp-internal-link">{esc(rec["name"])} Tires</a>'
        )
    for vs_slug, other_name in comparisons:
        links.append(
            f'<a href="/tire/{esc(vs_slug)}/" class="tp-internal-link">{esc(tire["name"])} vs {esc(other_name)}</a>'
        )

    heading = ("Race Tire Guides Featuring This Tire" if race_recs
               else "Compare This Tire")
    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">05 / RELATED TIRE GUIDES</span>
    <h2>{heading}</h2>
    <div class="tp-internal-links">{"".join(links)}</div>
  </div>
</section>'''


def build_footer_cta(tire: dict) -> str:
    return f'''<footer class="tp-footer-cta">
  <div class="tp-container">
    <div class="tp-footer-cta-inner">
      <a href="/gravel-races/" class="tp-btn tp-btn--primary">Browse All Races</a>
      <a href="/race/quiz/" class="tp-btn tp-btn--outline">Find Your Race</a>
    </div>
  </div>
</footer>'''


def build_inline_js() -> str:
    return '''<script>
(function(){
  var WORKER_URL='https://fueling-lead-intake.gravelgodcoaching.workers.dev';
  var LS_KEY='gg-pk-fueling';
  var EXPIRY_DAYS=90;
  var form=document.getElementById('tp-email-capture-form');
  if(!form) return;
  try{
    var cached=JSON.parse(localStorage.getItem(LS_KEY)||'null');
    if(cached&&cached.email&&cached.exp>Date.now()){
      form.style.display='none';
      var success=document.getElementById('tp-email-capture-success');
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
    var errEl=document.getElementById('tp-email-capture-err');
    if(!errEl){errEl=document.createElement('p');errEl.id='tp-email-capture-err';errEl.className='tp-email-capture-fine';form.parentNode.insertBefore(errEl,form.nextSibling);}
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
      var success=document.getElementById('tp-email-capture-success');
      if(success) success.style.display='block';
    })
    .catch(function(){
      errEl.textContent='That did not go through. Check your connection and try again.';
      errEl.style.display='block';
      if(subBtn) subBtn.disabled=false;
    });
  });
})();

// Tire review form
(function(){
  var WORKER_URL='https://tire-review-intake.gravelgodcoaching.workers.dev';
  var form=document.getElementById('tp-rev-form');
  if(!form) return;

  /* Star rating interaction */
  var starBtns=document.querySelectorAll('.tp-rev-star-btn');
  var starsInput=document.getElementById('tp-rev-stars-val');
  starBtns.forEach(function(btn){
    btn.addEventListener('click',function(){
      var val=parseInt(this.getAttribute('data-star'));
      starsInput.value=val;
      starBtns.forEach(function(b){
        var active=parseInt(b.getAttribute('data-star'))<=val;
        b.classList.toggle('is-active',active);
        b.setAttribute('aria-checked',active?'true':'false');
      });
    });
    btn.addEventListener('mouseenter',function(){
      var val=parseInt(this.getAttribute('data-star'));
      starBtns.forEach(function(b){
        if(parseInt(b.getAttribute('data-star'))<=val) b.style.color='var(--gg-color-gold)';
        else b.style.color='var(--gg-color-tan)';
      });
    });
    btn.addEventListener('mouseleave',function(){
      starBtns.forEach(function(b){b.style.color='';});
    });
  });

  /* Character count on textarea */
  var cc=document.querySelector('.tp-rev-charcount');
  if(cc){
    var ta=document.getElementById(cc.getAttribute('data-for'));
    if(ta){ta.addEventListener('input',function(){cc.textContent=ta.value.length+'/500';});}
  }

  /* Fix #5: Track submission state to prevent double-submit */
  var submitting=false;
  var submitBtn=document.getElementById('tp-rev-submit-btn');
  var errEl=document.getElementById('tp-rev-error');
  var errText=document.getElementById('tp-rev-error-text');

  form.addEventListener('submit',function(e){
    e.preventDefault();
    if(submitting) return;

    var stars=parseInt(starsInput.value);
    var email=form.email.value.trim();
    if(!stars||stars<1||stars>5){alert('Please select a star rating.');return;}
    if(!email||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)){alert('Please enter a valid email.');return;}
    if(form.website&&form.website.value) return;

    /* Collect conditions checkboxes */
    var conds=[];
    form.querySelectorAll('input[name="conditions"]:checked').forEach(function(cb){conds.push(cb.value);});

    var widthVal=form.width_ridden.value;
    var pressureVal=form.pressure_psi.value;
    var payload={
      tire_id:form.tire_id.value,
      tire_name:form.tire_name.value,
      email:email,
      stars:stars,
      width_ridden:widthVal?parseInt(widthVal):null,
      pressure_psi:pressureVal?parseInt(pressureVal):null,
      conditions:conds.length?conds:null,
      race_used_at:form.race_used_at.value||null,
      would_recommend:form.would_recommend.value||null,
      review_text:form.review_text.value||null,
      website:form.website.value
    };

    /* Fix #5: Disable button immediately */
    submitting=true;
    submitBtn.disabled=true;
    submitBtn.textContent='SUBMITTING...';
    errEl.style.display='none';

    /* Fix #6: Await fetch response, handle errors */
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:(typeof AbortSignal!=='undefined'&&AbortSignal.timeout)?AbortSignal.timeout(10000):undefined})
    .then(function(resp){
      return resp.json().then(function(data){return{status:resp.status,body:data};});
    })
    .then(function(result){
      if(result.status===200){
        if(typeof gtag==='function') gtag('event','tire_review_submit',{tire_id:form.tire_id.value,stars:stars});
        form.style.display='none';
        document.getElementById('tp-rev-success').style.display='block';
      } else {
        var msg=result.body.error||'Something went wrong. Please try again.';
        errText.textContent=msg;
        errEl.style.display='block';
        submitting=false;
        submitBtn.disabled=false;
        submitBtn.textContent='SUBMIT REVIEW';
      }
    })
    .catch(function(){
      errText.textContent='Network error. Please check your connection and try again.';
      errEl.style.display='block';
      submitting=false;
      submitBtn.disabled=false;
      submitBtn.textContent='SUBMIT REVIEW';
    });
  });
})();
</script>'''


def build_json_ld(tire: dict, race_recs: list, description: str = "") -> str:
    slug = tire_slug(tire)
    name = tire["name"]
    url = f"{SITE_BASE_URL}/tire/{slug}/"
    rec_count = len(race_recs)

    # BreadcrumbList
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Gravel God",
             "item": f"{SITE_BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Tires",
             "item": f"{SITE_BASE_URL}/tire/"},
            {"@type": "ListItem", "position": 3, "name": name,
             "item": url},
        ]
    }

    # Product schema
    product = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "brand": {"@type": "Brand", "name": tire["brand"]},
        "description": description,
        "url": url,
    }
    if tire.get("msrp_usd"):
        product["offers"] = {
            "@type": "Offer",
            "price": str(tire["msrp_usd"]),
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
        }
    # AggregateRating only from real approved community reviews (3+). Never
    # synthesize a rating from recommendation counts: an invented ratingValue
    # published as Product schema is a fabricated claim (scoring-and-veracity
    # SKILL: real submissions only) and misrepresents ratingCount to Google.
    approved_reviews = [r for r in tire.get("community_reviews", []) if r.get("approved")]
    if len(approved_reviews) >= 3:
        avg = sum(r["stars"] for r in approved_reviews) / len(approved_reviews)
        product["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": f"{avg:.1f}",
            "bestRating": "5",
            "ratingCount": str(len(approved_reviews)),
        }

    combined = json.dumps([breadcrumb, product], indent=2)
    return f'<script type="application/ld+json">{combined}</script>'


# ── Full Page Assembly ────────────────────────────────────────


def number_sections(html: str) -> str:
    """Renumber the "NN / LABEL" section tags in page order, so an optional
    section (Who Raced It) never leaves a gap."""
    counter = iter(range(1, 100))
    return re.sub(r'(<span class="tp-section-num">)\d{2}( / )',
                  lambda m: f"{m.group(1)}{next(counter):02d}{m.group(2)}", html)


def generate_tire_page(tire: dict, race_recs: list, comparisons: list = ()) -> str:
    slug = tire_slug(tire)
    name = tire["name"]

    ranks = tire_ranks(tire)
    title = esc(page_title(tire))
    meta_desc = page_description(tire, ranks, race_recs)

    header = build_header(tire)
    sections = [
        build_ranks_section(ranks),
        build_specs_section(tire),
        build_where_we_pick_section(race_recs),
        build_who_raced_section(tire),
    ]
    community_reviews = build_community_reviews_section(tire)
    email_capture = build_email_capture()
    internal_links = build_internal_links_section(tire, race_recs, comparisons)
    footer = build_footer_cta(tire)
    inline_js = build_inline_js()
    json_ld = build_json_ld(tire, race_recs, meta_desc)
    canonical = f"{SITE_BASE_URL}/tire/{slug}/"

    main_html = number_sections("\n".join(x for x in sections + [community_reviews, f'''<section class="tp-section">
  <div class="tp-container">
    {email_capture}
  </div>
</section>''', internal_links] if x))

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
{header}
<main>
{main_html}
</main>
{footer}
{inline_js}
{get_consent_banner_html()}
</body>
</html>'''


# ── CLI ───────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Generate per-tire SEO pages."
    )
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: wordpress/output/tire/)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load tire database
    tire_db = load_tire_database()
    print(f"Loaded {len(tire_db)} tires")

    # Scan race data for tire recommendations
    print("Scanning race data for tire recommendations...")
    tire_races = scan_race_recommendations(tire_db)

    # Head-to-head pages, paired the same way generate_tire_vs_pages.py does
    from generate_tire_vs_pages import select_tire_pairs
    tire_names = {t["id"]: t["name"] for t in tire_db}
    comparisons = {}
    for id_a, id_b in select_tire_pairs(tire_db):
        if id_a in tire_names and id_b in tire_names:
            comparisons.setdefault(id_a, []).append((f"{id_a}-vs-{id_b}", tire_names[id_b]))
            comparisons.setdefault(id_b, []).append((f"{id_a}-vs-{id_b}", tire_names[id_a]))

    generated = 0
    for tire in tire_db:
        slug = tire_slug(tire)
        race_recs = tire_races.get(tire["id"], [])

        page_dir = output_dir / slug
        page_dir.mkdir(parents=True, exist_ok=True)

        html_content = generate_tire_page(tire, race_recs, comparisons.get(tire["id"], []))
        out_path = page_dir / "index.html"
        out_path.write_text(html_content, encoding="utf-8")
        generated += 1

    from generate_tire_index import write_tire_index
    write_tire_index(output_dir, tire_db)

    print(f"\nDone. {generated} tire pages generated in {output_dir}/")
    total_recs = sum(len(v) for v in tire_races.values())
    print(f"  Total race recommendations found: {total_recs}")


if __name__ == "__main__":
    main()
