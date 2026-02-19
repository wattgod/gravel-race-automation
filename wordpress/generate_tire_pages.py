#!/usr/bin/env python3
"""
Generate per-tire SEO pages at /tire/{tire-slug}/.

Each page shows tire specs, race recommendations, BRR links, email capture,
and internal links to every race tire guide where the tire is recommended.

Usage:
    python wordpress/generate_tire_pages.py
    python wordpress/generate_tire_pages.py --output-dir /tmp/tire-pages
"""

import argparse
import html as html_mod
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import (
    COLORS,
    GA_MEASUREMENT_ID,
    SITE_BASE_URL,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
)

from generate_tire_guide import load_tire_database

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "tire"
CURRENT_YEAR = date.today().year


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
.tp-header-sub {
  font-family: var(--gg-font-editorial);
  font-size: 14px;
  color: var(--gg-color-warm-brown);
  font-style: italic;
  margin-top: 4px;
}
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

/* Chips */
.tp-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 8px 0 16px;
}
.tp-chip {
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 3px 10px;
  border: 2px solid var(--gg-color-tan);
}
.tp-chip--good { border-color: var(--gg-color-teal); color: var(--gg-color-teal); }
.tp-chip--warn { border-color: var(--gg-color-gold); color: var(--gg-color-gold); }
.tp-chip--bad { border-color: var(--gg-color-secondary-brown); color: var(--gg-color-secondary-brown); }

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

/* BRR links */
.tp-brr-links {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 12px 0;
}
.tp-brr-link {
  font-family: var(--gg-font-data);
  font-size: 12px;
  font-weight: 700;
  color: var(--gg-color-teal);
  border: 2px solid var(--gg-color-teal);
  padding: 6px 14px;
  text-decoration: none;
  text-transform: uppercase;
  letter-spacing: 1px;
  transition: background 0.2s;
}
.tp-brr-link:hover { background: var(--gg-color-teal); color: var(--gg-color-white); text-decoration: none; }

/* Strengths / Weaknesses */
.tp-pros-cons {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin: 16px 0;
}
@media (max-width: 480px) { .tp-pros-cons { grid-template-columns: 1fr; } }
.tp-pros h4, .tp-cons h4 {
  font-family: var(--gg-font-data);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  margin-bottom: 8px;
}
.tp-pros h4 { color: var(--gg-color-teal); }
.tp-cons h4 { color: var(--gg-color-secondary-brown); }
.tp-pros ul, .tp-cons ul { list-style: none; padding: 0; }
.tp-pros li, .tp-cons li {
  font-family: var(--gg-font-data);
  font-size: 12px;
  padding: 2px 0;
}
.tp-pros li::before { content: "+"; color: var(--gg-color-teal); font-weight: bold; margin-right: 6px; }
.tp-cons li::before { content: "-"; color: var(--gg-color-secondary-brown); font-weight: bold; margin-right: 6px; }

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

@media (max-width: 768px) {
  .tp-rev-form-row { grid-template-columns: 1fr; }
}

@media print {
  .tp-footer-cta, .tp-email-capture, .tp-rev-form-wrap { display: none; }
}
"""


# ── HTML Builders ─────────────────────────────────────────────


def build_header(tire: dict) -> str:
    widths = ", ".join(f"{w}mm" for w in tire["widths_mm"])
    msrp = f"${tire['msrp_usd']:.2f}" if tire.get("msrp_usd") else "N/A"
    return f'''<header class="tp-header">
  <div class="tp-container">
    <div class="tp-breadcrumb">
      <a href="/">Gravel God</a> / <a href="/gravel-races/">Races</a> / Tire Review
    </div>
    <span class="tp-badge">TIRE REVIEW</span>
    <span class="tp-tread-badge">{esc(tire["tread_type"].upper())} TREAD</span>
    <h1>{esc(tire["name"])} Review</h1>
    <p class="tp-header-sub">{esc(tire.get("tagline", ""))}</p>
    <div class="tp-vitals">
      <div class="tp-vital"><strong>{esc(tire["brand"])}</strong>Brand</div>
      <div class="tp-vital"><strong>{widths}</strong>Widths</div>
      <div class="tp-vital"><strong>{msrp}</strong>MSRP</div>
      <div class="tp-vital"><strong>{"Yes" if tire.get("tubeless_ready") else "No"}</strong>Tubeless</div>
    </div>
  </div>
</header>'''


def build_specs_section(tire: dict) -> str:
    rows = []
    for w in tire["widths_mm"]:
        weight = tire.get("weight_grams", {}).get(str(w), "—")
        crr_data = tire.get("crr_watts_at_29kmh") or {}
        crr = crr_data.get(str(w), "—")
        crr_str = f"{crr}W" if isinstance(crr, (int, float)) else "—"
        weight_str = f"{weight}g" if isinstance(weight, (int, float)) else "—"
        rows.append(f"<tr><td>{w}mm</td><td>{weight_str}</td><td>{crr_str}</td></tr>")

    pr_label = rating_label(tire.get("puncture_resistance", ""))
    wt_label = rating_label(tire.get("wet_traction", ""))
    mc_label = rating_label(tire.get("mud_clearance", ""))

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">01 / SPECIFICATIONS</span>
    <h2>Specs by Width</h2>
    <table class="tp-specs-table">
      <thead><tr><th>Width</th><th>Weight</th><th>CRR (29km/h)</th></tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
    <table class="tp-specs-table" style="margin-top:12px">
      <thead><tr><th>Rating</th><th>Value</th></tr></thead>
      <tbody>
        <tr><td>Puncture Resistance</td><td style="color:{rating_color(tire.get('puncture_resistance',''))}">{pr_label}</td></tr>
        <tr><td>Wet Traction</td><td style="color:{rating_color(tire.get('wet_traction',''))}">{wt_label}</td></tr>
        <tr><td>Mud Clearance</td><td style="color:{rating_color(tire.get('mud_clearance',''))}">{mc_label}</td></tr>
      </tbody>
    </table>
  </div>
</section>'''


def build_use_cases_section(tire: dict) -> str:
    rec_chips = "".join(
        f'<span class="tp-chip tp-chip--good">{esc(u)}</span>'
        for u in tire.get("recommended_use", [])
    )
    avoid_chips = "".join(
        f'<span class="tp-chip tp-chip--bad">{esc(u)}</span>'
        for u in tire.get("avoid_use", [])
    )

    pros = "".join(f"<li>{esc(s)}</li>" for s in tire.get("strengths", []))
    cons = "".join(f"<li>{esc(w)}</li>" for w in tire.get("weaknesses", []))

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">02 / BEST FOR</span>
    <h2>When to Use This Tire</h2>
    <h4 style="font-family:var(--gg-font-data);font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-teal);margin-bottom:4px">RECOMMENDED FOR</h4>
    <div class="tp-chips">{rec_chips}</div>
    <h4 style="font-family:var(--gg-font-data);font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-secondary-brown);margin-bottom:4px">AVOID IN</h4>
    <div class="tp-chips">{avoid_chips}</div>
    <div class="tp-pros-cons">
      <div class="tp-pros"><h4>Strengths</h4><ul>{pros}</ul></div>
      <div class="tp-cons"><h4>Weaknesses</h4><ul>{cons}</ul></div>
    </div>
  </div>
</section>'''


def build_race_recommendations_section(tire: dict, race_recs: list) -> str:
    if not race_recs:
        return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">03 / RACE RECOMMENDATIONS</span>
    <h2>Races Where This Tire Shines</h2>
    <p style="font-family:var(--gg-font-data);font-size:13px;color:var(--gg-color-secondary-brown)">
      No races currently recommend this tire as a primary pick. Check individual race tire guides for the latest recommendations.
    </p>
  </div>
</section>'''

    # Sort: primary rank 1 first, then other primaries, then front/rear
    def sort_key(r):
        if r["position"] == "primary":
            return (0, r["rank"])
        return (1, 0)

    sorted_recs = sorted(race_recs, key=sort_key)

    items = []
    for rec in sorted_recs:
        if rec["position"] == "primary" and rec["rank"] == 1:
            rank_class = "tp-race-rank tp-race-rank--1"
            rank_text = "#1"
        elif rec["position"] == "primary":
            rank_class = "tp-race-rank"
            rank_text = f"#{rec['rank']}"
        else:
            rank_class = "tp-race-rank tp-race-rank--fr"
            rank_text = rec["position"].upper()[:2]

        why_html = f'<div class="tp-race-why">{esc(rec["why"])}</div>' if rec.get("why") else ""
        items.append(f'''<li class="tp-race-item">
      <span class="{rank_class}">{rank_text}</span>
      <div class="tp-race-info">
        <a href="/race/{esc(rec["slug"])}/tires/" class="tp-race-name">{esc(rec["name"])}</a>
        {why_html}
      </div>
      <span class="tp-race-width">{rec["width"]}mm</span>
    </li>''')

    primary_count = sum(1 for r in race_recs if r["position"] == "primary")
    rank1_count = sum(1 for r in race_recs if r["position"] == "primary" and r["rank"] == 1)

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">03 / RACE RECOMMENDATIONS</span>
    <h2>Races Where This Tire Shines</h2>
    <p style="font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-secondary-brown);margin-bottom:16px">
      Recommended in {len(race_recs)} race tire guides &mdash; #{" "}1 pick in {rank1_count}, top 3 in {primary_count}.
    </p>
    <ul class="tp-race-list">{"".join(items)}</ul>
  </div>
</section>'''


def build_brr_section(tire: dict) -> str:
    brr = tire.get("brr_urls_by_width", {})
    if not brr:
        return ""

    links = []
    for width, url in sorted(brr.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
        links.append(f'<a href="{esc(url)}" target="_blank" rel="noopener" class="tp-brr-link">{width}mm Review &rarr;</a>')

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">04 / TEST DATA</span>
    <h2>BicycleRollingResistance.com Reviews</h2>
    <p style="font-family:var(--gg-font-data);font-size:12px;color:var(--gg-color-secondary-brown);margin-bottom:12px">
      Independent rolling resistance, puncture, and wet grip test data.
    </p>
    <div class="tp-brr-links">{"".join(links)}</div>
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
        <button type="submit" class="tp-rev-submit">SUBMIT REVIEW</button>
      </form>
      <div class="tp-rev-success" id="tp-rev-success">
        <div class="tp-rev-success-icon">&#10003;</div>
        <p class="tp-rev-success-text">Review submitted &mdash; thank you!</p>
      </div>
    </div>'''


def build_community_reviews_section(tire: dict) -> str:
    """Build community reviews section with 3 display states."""
    reviews = [r for r in tire.get("community_reviews", []) if r.get("approved")]
    total = len(reviews)
    name = tire["name"]
    form = build_tire_review_form(tire)
    threshold = 3

    # Empty state
    if total == 0:
        return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">05 / COMMUNITY REVIEWS</span>
    <h2>Community Reviews</h2>
    <p class="tp-rev-empty">No community reviews yet. Be the first to rate the {esc(name)}.</p>
    {form}
  </div>
</section>'''

    # Pending state (below threshold)
    if total < threshold:
        needed = threshold - total
        return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">05 / COMMUNITY REVIEWS</span>
    <h2>Community Reviews</h2>
    <p class="tp-rev-pending">{total} review{"s" if total != 1 else ""} so far &mdash; {needed} more needed to display the community rating.</p>
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

    # Show up to 5 most recent
    sorted_reviews = sorted(reviews, key=lambda r: r.get("submitted_at", ""), reverse=True)[:5]

    cards = []
    for r in sorted_reviews:
        r_stars = "&#9733;" * r["stars"] + "&#9734;" * (5 - r["stars"])

        meta_parts = []
        if r.get("width_ridden"):
            meta_parts.append(f'<span>{r["width_ridden"]}mm</span>')
        if r.get("pressure_psi"):
            meta_parts.append(f'<span>{r["pressure_psi"]} psi</span>')
        if r.get("conditions"):
            meta_parts.append(f'<span>{", ".join(r["conditions"])}</span>')
        if r.get("race_used_at"):
            meta_parts.append(f'<span>{esc(r["race_used_at"])}</span>')
        meta_html = "".join(meta_parts)

        text_html = f'<div class="tp-rev-card-text">{esc(r["review_text"])}</div>' if r.get("review_text") else ""

        rec_html = ""
        if r.get("would_recommend") == "yes":
            rec_html = '<div class="tp-rev-card-recommend tp-rev-card-recommend--yes">&#10003; Would recommend</div>'
        elif r.get("would_recommend") == "no":
            rec_html = '<div class="tp-rev-card-recommend tp-rev-card-recommend--no">&#10007; Would not recommend</div>'

        cards.append(f'''<div class="tp-rev-card">
      <div class="tp-rev-card-stars">{r_stars}</div>
      <div class="tp-rev-card-meta">{meta_html}</div>
      {text_html}
      {rec_html}
    </div>''')

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">05 / COMMUNITY REVIEWS</span>
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
      <div class="tp-email-capture-badge">FREE DOWNLOAD</div>
      <h3 class="tp-email-capture-title">GET A RACE DAY SETUP CARD</h3>
      <p class="tp-email-capture-text">Tire picks, pressure chart, sealant amounts, and tubeless tips &mdash; customized for any gravel race. Print it and tape it to your stem.</p>
      <form class="tp-email-capture-form" id="tp-email-capture-form" autocomplete="off">
        <input type="hidden" name="source" value="tire_guide">
        <input type="hidden" name="website" value="">
        <div class="tp-email-capture-row">
          <input type="email" name="email" required placeholder="your@email.com" class="tp-email-capture-input" aria-label="Email address">
          <button type="submit" class="tp-email-capture-btn">GET SETUP CARD</button>
        </div>
      </form>
      <div class="tp-email-capture-success" id="tp-email-capture-success" style="display:none">
        <p class="tp-email-capture-check">&#10003; Setup card unlocked!</p>
        <a href="/gravel-races/" class="tp-email-capture-link">Find Your Race &rarr;</a>
      </div>
      <p class="tp-email-capture-fine">No spam. Unsubscribe anytime.</p>
    </div>
  </div>'''


def build_internal_links_section(tire: dict, race_recs: list) -> str:
    if not race_recs:
        return ""

    links = []
    for rec in sorted(race_recs, key=lambda r: r["name"])[:20]:
        links.append(
            f'<a href="/race/{esc(rec["slug"])}/tires/" class="tp-internal-link">{esc(rec["name"])} Tires</a>'
        )

    return f'''<section class="tp-section">
  <div class="tp-container">
    <span class="tp-section-num">06 / RELATED TIRE GUIDES</span>
    <h2>Race Tire Guides Featuring This Tire</h2>
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
    try{localStorage.setItem(LS_KEY,JSON.stringify({email:email,exp:Date.now()+EXPIRY_DAYS*86400000}));}catch(ex){}
    var payload={email:email,source:form.source.value,website:form.website.value};
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(function(){});
    if(typeof gtag==='function') gtag('event','email_capture',{source:'tire_guide'});
    form.style.display='none';
    var success=document.getElementById('tp-email-capture-success');
    if(success) success.style.display='block';
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

  form.addEventListener('submit',function(e){
    e.preventDefault();
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
    fetch(WORKER_URL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}).catch(function(){});
    if(typeof gtag==='function') gtag('event','tire_review_submit',{tire_id:form.tire_id.value,stars:stars});

    form.style.display='none';
    document.getElementById('tp-rev-success').style.display='block';
  });
})();
</script>'''


def build_json_ld(tire: dict, race_recs: list) -> str:
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
            {"@type": "ListItem", "position": 2, "name": "Tire Reviews",
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
        "description": tire.get("tagline", ""),
        "url": url,
    }
    if tire.get("msrp_usd"):
        product["offers"] = {
            "@type": "Offer",
            "price": str(tire["msrp_usd"]),
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock",
        }
    # Use real community review data when 3+ reviews exist; fallback to proxy
    approved_reviews = [r for r in tire.get("community_reviews", []) if r.get("approved")]
    if len(approved_reviews) >= 3:
        avg = sum(r["stars"] for r in approved_reviews) / len(approved_reviews)
        product["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": f"{avg:.1f}",
            "bestRating": "5",
            "ratingCount": str(len(approved_reviews)),
        }
    elif rec_count > 0:
        # Proxy rating based on recommendation count until enough reviews
        rating_value = min(4.5, 3.0 + (rec_count / 50) * 1.5)
        product["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": f"{rating_value:.1f}",
            "bestRating": "5",
            "ratingCount": str(rec_count),
        }

    combined = json.dumps([breadcrumb, product], indent=2)
    return f'<script type="application/ld+json">{combined}</script>'


# ── Full Page Assembly ────────────────────────────────────────


def generate_tire_page(tire: dict, race_recs: list) -> str:
    slug = tire_slug(tire)
    name = tire["name"]

    header = build_header(tire)
    specs = build_specs_section(tire)
    use_cases = build_use_cases_section(tire)
    races = build_race_recommendations_section(tire, race_recs)
    brr = build_brr_section(tire)
    community_reviews = build_community_reviews_section(tire)
    email_capture = build_email_capture()
    internal_links = build_internal_links_section(tire, race_recs)
    footer = build_footer_cta(tire)
    inline_js = build_inline_js()
    json_ld = build_json_ld(tire, race_recs)

    title = f"{esc(name)} Review: Best Gravel Races & Setup Guide | Gravel God"
    meta_desc = f"{name} gravel tire review: specs, rolling resistance, race recommendations, and setup guide. See which races recommend this tire."
    canonical = f"{SITE_BASE_URL}/tire/{slug}/"

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
  <meta property="og:site_name" content="Gravel God">

  {preload}

  <style>
  {font_css}
  {tokens_css}
  {page_css}
  </style>

  {json_ld}

  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', '{GA_MEASUREMENT_ID}');
  </script>
</head>
<body>
{header}
<main>
{specs}
{use_cases}
{races}
{brr}
{community_reviews}
<section class="tp-section">
  <div class="tp-container">
    {email_capture}
  </div>
</section>
{internal_links}
</main>
{footer}
{inline_js}
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

    generated = 0
    for tire in tire_db:
        slug = tire_slug(tire)
        race_recs = tire_races.get(tire["id"], [])

        page_dir = output_dir / slug
        page_dir.mkdir(parents=True, exist_ok=True)

        html_content = generate_tire_page(tire, race_recs)
        out_path = page_dir / "index.html"
        out_path.write_text(html_content, encoding="utf-8")
        generated += 1

    print(f"\nDone. {generated} tire pages generated in {output_dir}/")
    total_recs = sum(len(v) for v in tire_races.values())
    print(f"  Total race recommendations found: {total_recs}")


if __name__ == "__main__":
    main()
