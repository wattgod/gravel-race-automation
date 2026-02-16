#!/usr/bin/env python3
"""
Generate series hub landing pages for SEO.

Creates one page per series at /race/series/{slug}/index.html with
hero, overview, history, format, event calendar, infographics,
decision matrix, FAQ, and JSON-LD.

Usage:
    python wordpress/generate_series_hubs.py
    python wordpress/generate_series_hubs.py --output-dir /tmp/gg-test
"""

import argparse
import html as html_mod
import json
import math
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import COLORS, GA_MEASUREMENT_ID, RACER_RATING_THRESHOLD, get_font_face_css, get_tokens_css

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERIES_DIR = PROJECT_ROOT / "series-data"
SITE_BASE_URL = "https://gravelgodcycling.com"

# Month order for sorting events chronologically
MONTH_ORDER = {
    "January": 1, "February": 2, "March": 3, "April": 4,
    "May": 5, "June": 6, "July": 7, "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
    "TBD": 99,
}

# Radar chart dimensions (7-point heptagon)
RADAR_DIMS = ["logistics", "length", "technicality", "elevation", "climate", "altitude", "adventure"]
RADAR_LABELS = ["Logistics", "Length", "Technicality", "Elevation", "Climate", "Altitude", "Adventure"]

# Colors for overlaid radar polygons (cycling for multiple events)
POLYGON_COLORS = [
    COLORS["teal"],        # #178079
    COLORS["gold"],        # #9a7e0a
    COLORS["light_teal"],  # #4ECDC4
    COLORS["light_gold"],  # #c9a92c
    COLORS["warm_brown"],  # #A68E80
]

# Decision matrix criteria: (label, extractor function)
MATRIX_CRITERIA = [
    ("Difficulty", "difficulty"),
    ("Technicality", "technicality"),
    ("Budget-Friendliness", "budget"),
    ("Accessibility", "accessibility"),
    ("Climate Challenge", "climate"),
    ("Field Competitiveness", "field"),
]

# Dynamic year — never hardcode "2026" in output
CURRENT_YEAR = date.today().year

# Display/truncation limits (named to prevent magic numbers)
MAX_EVENT_NAMES_IN_FAQ = 12
MAX_COST_ITEMS_IN_FAQ = 5
MAX_TERRAIN_TYPES_IN_FAQ = 10
TIMELINE_DESC_MAX_LEN = 65
MATRIX_NAME_MAX_LEN = 16
BAR_CHART_NAME_MAX_LEN = 22
MAP_LABEL_NAME_MAX_LEN = 18

# Simplified US outline coordinates [lng, lat] tracing continental border clockwise
US_OUTLINE_COORDS = [
    (-124.5, 48.4), (-123.0, 48.5), (-117.0, 49.0), (-110.0, 49.0),
    (-104.0, 49.0), (-97.0, 49.0), (-95.0, 49.3),
    (-89.5, 47.8), (-84.5, 46.5), (-82.5, 41.7),
    (-79.0, 43.0), (-75.0, 44.5), (-71.0, 44.0), (-67.0, 45.0),
    (-70.0, 42.0), (-71.0, 41.5), (-73.5, 40.5), (-74.0, 40.5),
    (-74.5, 39.0), (-75.5, 38.5),
    (-76.0, 37.0), (-75.5, 35.5),
    (-77.0, 34.5), (-79.0, 33.0), (-80.5, 32.0),
    (-81.0, 31.0), (-81.5, 30.5), (-80.5, 25.3),
    (-82.0, 24.8), (-82.5, 27.5), (-84.0, 30.0),
    (-87.5, 30.3), (-89.5, 30.0), (-90.0, 29.0), (-93.0, 29.5),
    (-97.0, 26.0),
    (-100.0, 29.0), (-103.0, 29.0), (-106.5, 31.8), (-111.0, 31.5),
    (-114.5, 32.5),
    (-117.0, 32.5), (-118.5, 34.0), (-120.5, 34.5), (-122.0, 37.0),
    (-123.0, 38.5), (-124.0, 40.5), (-124.5, 42.0), (-124.0, 46.0),
    (-124.5, 48.4),
]


# ── Helper functions ──────────────────────────────────────────


def _avg_scores(race_data: dict, keys: list) -> float:
    """Average gravel_god_rating scores for the given keys."""
    ratings = race_data.get("gravel_god_rating", {})
    vals = [ratings.get(k, 0) for k in keys]
    valid = [v for v in vals if v > 0]
    return round(sum(valid) / len(valid), 1) if valid else 0


def _extract_criterion(race_data: dict, criterion_key: str) -> float:
    """Extract a decision-matrix criterion score from race data."""
    ratings = race_data.get("gravel_god_rating", {})
    if criterion_key == "difficulty":
        return _avg_scores(race_data, ["length", "technicality", "elevation", "altitude"])
    elif criterion_key == "technicality":
        return ratings.get("technicality", 0)
    elif criterion_key == "budget":
        exp = ratings.get("expenses", 3)
        return max(1, 6 - exp)
    elif criterion_key == "accessibility":
        return ratings.get("logistics", 0)
    elif criterion_key == "climate":
        return ratings.get("climate", 0)
    elif criterion_key == "field":
        return ratings.get("field_depth", 0)
    return 0


def _heptagon_point(cx, cy, radius, index, total=7):
    """Get (x, y) for the i-th vertex of a regular polygon starting from top."""
    angle = -math.pi / 2 + index * 2 * math.pi / total
    return (cx + radius * math.cos(angle), cy + radius * math.sin(angle))


def _project_coords(lat, lng, bounds, vw=700, vh=400):
    """Project lat/lng to SVG coordinates using equirectangular projection."""
    lng_min, lng_max, lat_min, lat_max = bounds
    if lng_max == lng_min or lat_max == lat_min:
        return (vw / 2, vh / 2)
    x = (lng - lng_min) / (lng_max - lng_min) * vw
    y = (lat_max - lat) / (lat_max - lat_min) * vh
    return (round(x, 1), round(y, 1))


def _dot_meter_svg(value, max_val=5):
    """Build inline SVG with filled/empty dots for a 1-5 score."""
    val = int(round(value)) if value else 0
    val = max(0, min(max_val, val))
    circles = []
    for i in range(max_val):
        cx = 5 + i * 10
        fill = COLORS["teal"] if i < val else COLORS["sand"]
        circles.append(f'<circle cx="{cx}" cy="6" r="4" fill="{fill}"/>')
    return (
        f'<svg viewBox="0 0 50 12" width="50" height="12" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" '
        f'aria-label="{val} out of {max_val}">{"".join(circles)}</svg>'
    )


def _us_outline_path(bounds):
    """Build SVG path d-string from US_OUTLINE_COORDS."""
    parts = []
    for i, (lng, lat) in enumerate(US_OUTLINE_COORDS):
        x, y = _project_coords(lat, lng, bounds)
        cmd = "M" if i == 0 else "L"
        parts.append(f"{cmd}{x},{y}")
    parts.append("Z")
    return " ".join(parts)


def esc(text) -> str:
    return html_mod.escape(str(text)) if text else ""


def _json_str(text) -> str:
    """Escape a string for safe embedding inside a JSON string literal.

    Unlike esc() (HTML escaping), this handles backslashes, quotes, and
    control characters the way JSON requires. Use this inside JSON-LD
    <script> blocks — never use esc() there.
    """
    if not text:
        return ""
    # json.dumps wraps in quotes; strip them since our template already has quotes
    return json.dumps(str(text))[1:-1]


def _svg_text_esc(text) -> str:
    """Escape text for SVG <text> elements.

    Only escapes XML-required characters (<, >, &). Does NOT escape quotes
    or apostrophes, which are safe inside SVG text content and would render
    as literal &#x27; entities otherwise.
    """
    if not text:
        return ""
    s = str(text)
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    return s


# ── Data loading ──────────────────────────────────────────────


def load_race_index() -> dict:
    """Load race index and return dict keyed by slug."""
    index_path = PROJECT_ROOT / "web" / "race-index.json"
    if not index_path.exists():
        return {}
    with open(index_path, "r", encoding="utf-8") as f:
        races = json.load(f)
    return {r["slug"]: r for r in races if r.get("slug")}


def load_full_race_data(slugs: list) -> dict:
    """Load full race-data JSON for profiled event slugs."""
    result = {}
    for slug in slugs:
        path = PROJECT_ROOT / "race-data" / f"{slug}.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                result[slug] = json.load(f).get("race", {})
    return result


# ── Section builders ──────────────────────────────────────────


def build_event_card(event: dict, race_lookup: dict) -> str:
    """Build an event card for the calendar section."""
    name = event.get("name", "")
    slug = event.get("slug")
    location = event.get("location", "")
    month = event.get("month", "TBD")
    has_profile = event.get("has_profile", False)

    # Pull tier + scores from index if available
    tier_badge = ""
    score_html = ""
    racer_html = ""
    if slug and slug in race_lookup:
        race = race_lookup[slug]
        tier = race.get("tier", 0)
        score = race.get("overall_score", 0)
        if tier:
            tier_badge = f'<span class="gg-series-event-tier gg-tier-{tier}">T{tier}</span>'
        if score:
            score_html = f'<span class="gg-series-event-score">{score}<small class="gg-series-score-label">GG</small></span>'
        # Racer rating
        rr_pct = race.get("racer_pct")
        rr_total = race.get("racer_total", 0)
        if rr_pct is not None and rr_total >= RACER_RATING_THRESHOLD:
            racer_html = f'<span class="gg-series-event-racer">{rr_pct}%<small class="gg-series-score-label">RACER</small></span>'
        else:
            racer_html = '<span class="gg-series-event-racer gg-series-event-racer--empty">&mdash;<small class="gg-series-score-label">RATE</small></span>'

    if has_profile and slug:
        name_html = f'<a href="/race/{esc(slug)}/" class="gg-series-event-name">{esc(name)}</a>'
        link_icon = ' <span class="gg-series-event-link">&#8599;</span>'
    else:
        name_html = f'<span class="gg-series-event-name">{esc(name)}</span>'
        link_icon = ""

    return f'''<div class="gg-series-event-card">
      <div class="gg-series-event-month">{esc(month)}</div>
      {name_html}{link_icon}
      <div class="gg-series-event-location">{esc(location)}</div>
      <div class="gg-series-event-badges">{tier_badge}{score_html}{racer_html}</div>
    </div>'''


def build_collapsible_section(title: str, content: str, section_id: str) -> str:
    """Build a collapsible content section."""
    if not content:
        return ""
    # Split into paragraphs
    paragraphs = content.strip().split("\n\n") if "\n\n" in content else [content]
    p_html = "\n".join(f"<p>{esc(p.strip())}</p>" for p in paragraphs if p.strip())
    return f'''<details class="gg-series-section" open>
    <summary class="gg-series-section-title">{esc(title)}</summary>
    <div class="gg-series-section-body">
      {p_html}
    </div>
  </details>'''


def build_series_radar_svg(series: dict, race_data: dict) -> str:
    """Build overlaid 7-point radar chart comparing course dimensions across events."""
    events = series.get("events", [])
    profiled = []
    for e in events:
        slug = e.get("slug")
        if slug and e.get("has_profile") and slug in race_data:
            rd = race_data[slug]
            if rd.get("gravel_god_rating"):
                profiled.append((e, rd))

    if len(profiled) < 2:
        return ""

    cx, cy, radius = 250, 200, 130

    # Concentric heptagonal grid rings
    grid_lines = []
    for pct in [0.2, 0.4, 0.6, 0.8, 1.0]:
        r = radius * pct
        pts = " ".join(
            f"{_heptagon_point(cx, cy, r, i)[0]:.1f},{_heptagon_point(cx, cy, r, i)[1]:.1f}"
            for i in range(7)
        )
        opacity = "0.3" if pct < 1.0 else "0.5"
        grid_lines.append(
            f'    <polygon points="{pts}" fill="none" stroke="{COLORS["tan"]}" '
            f'stroke-width="1" opacity="{opacity}"/>'
        )

    # Axis lines from center to each vertex
    for i in range(7):
        px, py = _heptagon_point(cx, cy, radius, i)
        grid_lines.append(
            f'    <line x1="{cx}" y1="{cy}" x2="{px:.1f}" y2="{py:.1f}" '
            f'stroke="{COLORS["tan"]}" stroke-width="1" opacity="0.3"/>'
        )

    # Axis labels
    for i, label in enumerate(RADAR_LABELS):
        px, py = _heptagon_point(cx, cy, radius + 20, i)
        anchor = "middle"
        if px < cx - 10:
            anchor = "end"
        elif px > cx + 10:
            anchor = "start"
        grid_lines.append(
            f'    <text x="{px:.1f}" y="{py:.1f}" font-size="9" '
            f'fill="{COLORS["secondary_brown"]}" text-anchor="{anchor}" '
            f'dominant-baseline="middle" '
            f"font-family=\"'Sometype Mono', monospace\">{label}</text>"
        )

    # Event polygons with draw animation
    polygons = []
    legend_items = []
    for idx, (event, rd) in enumerate(profiled):
        color = POLYGON_COLORS[idx % len(POLYGON_COLORS)]
        rating = rd.get("gravel_god_rating", {})
        points = []
        for i, dim in enumerate(RADAR_DIMS):
            val = rating.get(dim, 0)
            r = (val / 5.0) * radius
            px, py = _heptagon_point(cx, cy, r, i)
            points.append((px, py))

        pts_str = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)

        # Calculate perimeter for stroke-dasharray animation
        perimeter = 0
        for j in range(len(points)):
            x1, y1 = points[j]
            x2, y2 = points[(j + 1) % len(points)]
            perimeter += math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

        delay = idx * 0.15
        # Build tooltip: event name + dimension scores
        scores_str = ", ".join(f"{RADAR_LABELS[i]}: {rating.get(dim, 0)}" for i, dim in enumerate(RADAR_DIMS))
        event_name = event.get("name", "")
        polygons.append(
            f'    <polygon points="{pts_str}" fill="{color}" fill-opacity="0.12" '
            f'stroke="{color}" stroke-width="2" data-radar-idx="{idx}" '
            f'style="stroke-dasharray:{perimeter:.0f};stroke-dashoffset:{perimeter:.0f};'
            f'animation:gg-radar-draw 1s ease {delay:.2f}s forwards">'
            f'<title>{_svg_text_esc(event_name)}: {_svg_text_esc(scores_str)}</title>'
            f'</polygon>'
        )
        legend_items.append((color, event_name, idx))

    grid_svg = "\n".join(grid_lines)
    poly_svg = "\n".join(polygons)

    # Legend as HTML (wraps naturally unlike SVG text)
    legend_html = []
    for color, name, idx in legend_items:
        legend_html.append(
            f'<span class="gg-series-radar-legend-item" data-radar-idx="{idx}">'
            f'<span class="gg-series-radar-legend-swatch" style="background:{color}"></span>'
            f'{esc(name)}</span>'
        )
    legend = "\n      ".join(legend_html)

    return f'''<div class="gg-series-radar">
    <svg viewBox="0 0 500 380" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Difficulty comparison radar chart">
{grid_svg}
{poly_svg}
    </svg>
    <div class="gg-series-radar-legend">
      {legend}
    </div>
  </div>'''


def _bar_smart_label(event_name: str, series_name: str) -> str:
    """Strip shared series prefix from event name for bar chart labels."""
    prefix_candidates = [series_name, series_name.upper(), series_name.split()[0]]
    for prefix in prefix_candidates:
        if event_name.upper().startswith(prefix.upper()) and len(event_name) > len(prefix) + 1:
            suffix = event_name[len(prefix):].strip(" -–—:")
            if suffix:
                return suffix
    return event_name


def build_distance_elevation_svg(series: dict, race_data: dict) -> str:
    """Build horizontal dual-bar chart comparing distance and elevation."""
    events = series.get("events", [])
    profiled = []
    for e in events:
        slug = e.get("slug")
        if slug and e.get("has_profile") and slug in race_data:
            rd = race_data[slug]
            vitals = rd.get("vitals", {})
            dist = vitals.get("distance_mi", 0)
            elev = vitals.get("elevation_ft", 0)
            if dist or elev:
                profiled.append((e, dist, elev))

    if len(profiled) < 2:
        return ""

    # Sort by distance descending
    profiled.sort(key=lambda x: x[1], reverse=True)

    max_dist = max(p[1] for p in profiled) or 1
    max_elev = max(p[2] for p in profiled) or 1

    label_width = 160
    bar_area = 350
    value_width = 80
    row_height = 44
    svg_height = len(profiled) * row_height + 30  # padding for header
    svg_width = 600

    rows = []
    # Header labels
    rows.append(
        f'  <text x="{label_width}" y="14" font-size="9" '
        f'fill="{COLORS["secondary_brown"]}" '
        f"font-family=\"'Sometype Mono', monospace\" letter-spacing=\"1\">DISTANCE (MI)</text>"
    )
    rows.append(
        f'  <text x="{label_width}" y="24" font-size="9" '
        f'fill="{COLORS["gold"]}" '
        f"font-family=\"'Sometype Mono', monospace\" letter-spacing=\"1\">ELEVATION (FT)</text>"
    )

    series_name = series.get("display_name") or series.get("name", "")
    for i, (event, dist, elev) in enumerate(profiled):
        y_base = 36 + i * row_height
        name = event.get("name", "")
        # Strip series prefix for readability, then truncate if still too long
        short_name = _bar_smart_label(name, series_name)
        display_name = short_name if len(short_name) <= BAR_CHART_NAME_MAX_LEN else short_name[:BAR_CHART_NAME_MAX_LEN - 2] + "..."

        # Event name label
        rows.append(
            f'  <text x="0" y="{y_base + 12}" font-size="10" font-weight="700" '
            f'fill="{COLORS["dark_brown"]}" '
            f"font-family=\"'Sometype Mono', monospace\">{esc(display_name)}</text>"
        )

        # Distance bar (teal)
        dist_w = (dist / max_dist) * bar_area if max_dist else 0
        delay_d = i * 0.08
        rows.append(
            f'  <rect x="{label_width}" y="{y_base + 2}" width="{dist_w:.1f}" height="14" '
            f'fill="{COLORS["teal"]}" style="transform-origin:{label_width}px 0;'
            f'animation:gg-bar-grow 0.6s ease {delay_d:.2f}s both"/>'
        )
        rows.append(
            f'  <text x="{label_width + dist_w + 6:.1f}" y="{y_base + 13}" font-size="10" '
            f'fill="{COLORS["dark_brown"]}" '
            f"font-family=\"'Sometype Mono', monospace\">{dist} mi</text>"
        )

        # Elevation bar (gold)
        elev_w = (elev / max_elev) * bar_area if max_elev else 0
        delay_e = i * 0.08 + 0.04
        rows.append(
            f'  <rect x="{label_width}" y="{y_base + 20}" width="{elev_w:.1f}" height="14" '
            f'fill="{COLORS["gold"]}" style="transform-origin:{label_width}px 0;'
            f'animation:gg-bar-grow 0.6s ease {delay_e:.2f}s both"/>'
        )
        rows.append(
            f'  <text x="{label_width + elev_w + 6:.1f}" y="{y_base + 31}" font-size="10" '
            f'fill="{COLORS["dark_brown"]}" '
            f"font-family=\"'Sometype Mono', monospace\">{elev:,} ft</text>"
        )

    content = "\n".join(rows)
    return f'''<div class="gg-series-bars">
    <svg viewBox="0 0 {svg_width} {svg_height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Distance and elevation comparison">
{content}
    </svg>
  </div>'''


def build_geographic_map_svg(series: dict, race_data: dict, race_lookup: dict) -> str:
    """Build inline SVG map showing event locations as labeled dots."""
    events = series.get("events", [])
    located = []
    for e in events:
        slug = e.get("slug")
        lat, lng = None, None

        # Try full race data first
        if slug and slug in race_data:
            vitals = race_data[slug].get("vitals", {})
            lat = vitals.get("lat")
            lng = vitals.get("lng")

        # Fallback to race index
        if (lat is None or lng is None) and slug and slug in race_lookup:
            idx_entry = race_lookup[slug]
            lat = idx_entry.get("lat")
            lng = idx_entry.get("lng")

        if lat is not None and lng is not None:
            located.append((e, lat, lng))

    if len(located) < 2:
        return ""

    # Determine if all events are within continental US
    us_bounds = (-130, -60, 22, 52)
    all_us = all(
        us_bounds[0] <= lng <= us_bounds[1] and us_bounds[2] <= lat <= us_bounds[3]
        for _, lat, lng in located
    )

    vw, vh = 700, 400

    if all_us:
        bounds = us_bounds
        outline_path = _us_outline_path(bounds)
        outline_svg = (
            f'  <path d="{outline_path}" fill="none" stroke="{COLORS["tan"]}" '
            f'stroke-width="1.5" opacity="0.6"/>'
        )
    else:
        # Compute bounding box with padding for international events
        all_lngs = [lng for _, _, lng in located]
        all_lats = [lat for _, lat, _ in located]
        pad_lng = max(10, (max(all_lngs) - min(all_lngs)) * 0.15)
        pad_lat = max(5, (max(all_lats) - min(all_lats)) * 0.15)
        bounds = (
            min(all_lngs) - pad_lng, max(all_lngs) + pad_lng,
            min(all_lats) - pad_lat, max(all_lats) + pad_lat,
        )
        # Simple grid lines instead of outline
        grid = []
        for frac in [0.25, 0.5, 0.75]:
            gx = frac * vw
            gy = frac * vh
            grid.append(
                f'  <line x1="{gx:.0f}" y1="0" x2="{gx:.0f}" y2="{vh}" '
                f'stroke="{COLORS["sand"]}" stroke-width="1" opacity="0.5"/>'
            )
            grid.append(
                f'  <line x1="0" y1="{gy:.0f}" x2="{vw}" y2="{gy:.0f}" '
                f'stroke="{COLORS["sand"]}" stroke-width="1" opacity="0.5"/>'
            )
        outline_svg = "\n".join(grid)

    # Sort by month for connecting lines
    sorted_located = sorted(
        located, key=lambda x: MONTH_ORDER.get(x[0].get("month", "TBD"), 99)
    )

    # Connecting dashed lines in calendar order
    lines = []
    for j in range(len(sorted_located) - 1):
        _, lat1, lng1 = sorted_located[j]
        _, lat2, lng2 = sorted_located[j + 1]
        x1, y1 = _project_coords(lat1, lng1, bounds, vw, vh)
        x2, y2 = _project_coords(lat2, lng2, bounds, vw, vh)
        lines.append(
            f'  <line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{COLORS["tan"]}" stroke-width="1" stroke-dasharray="4,4" opacity="0.5"/>'
        )
    lines_svg = "\n".join(lines)

    # Build smart labels: strip common series prefix to show distinguishing location
    series_name = series.get("display_name") or series.get("name", "")
    # Common prefixes to strip (e.g., "Belgian Waffle Ride", "GRINDURO", "Life Time")
    prefix_candidates = [series_name, series_name.upper(), series_name.split()[0]]

    def _smart_label(event_name: str, event_location: str) -> str:
        """Extract the distinguishing part of an event name within a series.

        Falls back to location if the name is identical to the series name
        (e.g., "Belgian Waffle Ride" → use "California" from location).
        """
        for prefix in prefix_candidates:
            if event_name.upper().startswith(prefix.upper()) and len(event_name) > len(prefix) + 1:
                suffix = event_name[len(prefix):].strip(" -–—:")
                if suffix and suffix.lower() not in series_name.lower():
                    return suffix
        # If event name IS the series name, use location (city or state)
        if event_location:
            # Use the most specific part: "San Diego, California" → "San Diego"
            loc_parts = [p.strip() for p in event_location.split(",")]
            return loc_parts[0] if loc_parts else event_location
        # Final fallback: truncated name
        return event_name if len(event_name) <= MAP_LABEL_NAME_MAX_LEN else event_name[:MAP_LABEL_NAME_MAX_LEN - 2] + "..."

    # Event dots and labels with collision avoidance for BOTH dots and labels
    placed_dots = []   # list of (x, y) for placed dots
    placed_labels = []  # list of (x, y) for placed labels

    dots = []
    for e, lat, lng in sorted_located:
        x, y = _project_coords(lat, lng, bounds, vw, vh)
        name = e.get("name", "")
        location = e.get("location", "")
        label = _smart_label(name, location)

        # Offset dot if another event occupies the same spot
        dot_x, dot_y = x, y
        for px, py in placed_dots:
            if abs(dot_x - px) < 8 and abs(dot_y - py) < 8:
                dot_x = px + 12
                dot_y = py - 8
        placed_dots.append((dot_x, dot_y))

        dots.append(
            f'  <circle cx="{dot_x}" cy="{dot_y}" r="6" fill="{COLORS["teal"]}" '
            f'stroke="{COLORS["warm_paper"]}" stroke-width="2">'
            f'<title>{_svg_text_esc(name)}</title></circle>'
        )
        # Position label to avoid overlap with dot and other labels
        label_x = dot_x + 10
        anchor = "start"
        if dot_x > vw - 150:
            label_x = dot_x - 10
            anchor = "end"

        # Offset y if another label is too close
        label_y = dot_y + 4
        for px, py in placed_labels:
            if abs(label_x - px) < 100 and abs(label_y - py) < 14:
                label_y = py + 14  # push down
        placed_labels.append((label_x, label_y))

        dots.append(
            f'  <text x="{label_x}" y="{label_y}" font-size="9" '
            f'fill="{COLORS["dark_brown"]}" text-anchor="{anchor}" '
            f"font-family=\"'Sometype Mono', monospace\">{_svg_text_esc(label)}</text>"
        )
    dots_svg = "\n".join(dots)

    return f'''<div class="gg-series-map">
    <div class="gg-series-map-title">Event Locations</div>
    <svg viewBox="0 0 {vw} {vh}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Geographic map of event locations">
{outline_svg}
{lines_svg}
{dots_svg}
    </svg>
  </div>'''


TIMELINE_MAX_ENTRIES = 12

# Patterns that indicate weather/climate data, not real milestones.
# ALL lowercase — compared against desc.lower().
_WEATHER_PATTERNS = [
    "°f", "°c",                          # temperature units
    "hot,", "warm,", "cold,", "cool,",   # temp descriptors with comma
    "variable,", "dry,", "humid",        # climate descriptors
    "sunny,", "sunny ", "rain on ",      # precipitation
    "snowing", "freezing", "muddy",      # severe weather
    "perfect conditions",                 # euphemism for weather report
]

# Regex for bare temperature ranges like "(55-65°F)" or "(18-28°C)"
_TEMP_RANGE_RE = re.compile(r"\d+-\d+°[fc]", re.IGNORECASE)

# Entries under this length that match weather patterns are pure weather reports.
# Longer entries that mention weather in context of a real event (course shortened,
# DNF rate, etc.) are kept.
_WEATHER_MAX_LEN = 50


def _is_weather_entry(desc: str) -> bool:
    """Detect weather/climate strings masquerading as notable moments.

    Short entries (<50 chars) matching weather patterns are filtered.
    Longer entries keep weather as context for substantive milestones
    (e.g., 'course shortened due to freezing temps').
    """
    lower = desc.lower()
    has_weather = any(pat in lower for pat in _WEATHER_PATTERNS)
    has_temp_range = bool(_TEMP_RANGE_RE.search(lower))
    if not has_weather and not has_temp_range:
        return False
    # Short entries with weather = pure weather report
    if len(desc) < _WEATHER_MAX_LEN:
        return True
    # Long entries: only filter if it's JUST a temperature range with no substance
    # e.g., "Variable, some heat (15-30°C)" is short but padded
    stripped = _TEMP_RANGE_RE.sub("", lower).strip(" ,()")
    if len(stripped) < 20:
        return True
    return False


def _is_redundant_founded(desc: str, year_int: int, existing_entries: set) -> bool:
    """Detect redundant 'Founded—' entries when we already have a founding/established entry for the same year."""
    lower = desc.lower()
    if "founded" not in lower:
        return False
    # If any existing entry for the same year describes founding/establishment, this is redundant
    for existing_year, existing_desc in existing_entries:
        if existing_year == year_int and ("established" in existing_desc.lower() or "founded" in existing_desc.lower()):
            return True
    return False


def _parse_year(val) -> int:
    """Parse a year value, stripping ~ prefix for approximate dates."""
    s = str(val).strip().lstrip("~").lstrip("c.")
    try:
        return int(s)
    except ValueError:
        return 0


def build_series_timeline_svg(series: dict, race_data: dict) -> str:
    """Build vertical timeline SVG showing founding, event additions, and milestones.

    Filters out weather data, redundant entries, and caps at TIMELINE_MAX_ENTRIES
    to keep the visual focused on actual milestones.
    """
    events_list = series.get("events", [])
    series_founded = series.get("founded")

    # Collect timeline entries: (year_int, display_year, description, type, priority)
    # priority: 0=founding, 1=event established, 2=milestone
    entries = []

    # Series founding
    if series_founded:
        year_int = _parse_year(series_founded)
        if year_int:
            series_name = series.get("display_name") or series.get("name", "")
            entries.append((year_int, str(series_founded), f"{series_name} series founded", "founding", 0))

    # Individual event founding dates and notable moments
    for e in events_list:
        slug = e.get("slug")
        if slug and slug in race_data:
            rd = race_data[slug]
            hist = rd.get("history", {})

            # Event founding
            event_founded = hist.get("founded")
            if event_founded:
                year_int = _parse_year(event_founded)
                series_year = _parse_year(series_founded) if series_founded else 0
                if year_int and year_int != series_year:
                    display_year = str(event_founded) if "~" not in str(event_founded) else f"~{year_int}"
                    entries.append((year_int, display_year, f"{e.get('name', '')} established", "event", 1))

            # Notable moments
            moments = hist.get("notable_moments", [])
            for moment in moments:
                if ": " in str(moment):
                    parts = str(moment).split(": ", 1)
                    try:
                        year_int = int(parts[0])
                        desc = parts[1]
                        # Skip weather data
                        if _is_weather_entry(desc):
                            continue
                        entries.append((year_int, str(parts[0]), desc, "milestone", 2))
                    except ValueError:
                        pass

    if not entries:
        return ""

    # Sort by year, then priority (founding first, then events, then milestones)
    entries.sort(key=lambda x: (x[0], x[4]))

    # Deduplicate
    seen = set()
    unique = []
    existing_entries = set()
    for year_int, display_year, desc, etype, priority in entries:
        key = f"{year_int}:{desc}"
        if key in seen:
            continue
        # Skip redundant "Founded—" entries
        if _is_redundant_founded(desc, year_int, existing_entries):
            continue
        seen.add(key)
        existing_entries.add((year_int, desc))
        unique.append((year_int, display_year, desc, etype, priority))

    # Cap at max entries — keep all founding/event entries, trim milestones if needed
    if len(unique) > TIMELINE_MAX_ENTRIES:
        important = [e for e in unique if e[4] <= 1]  # founding + events
        milestones = [e for e in unique if e[4] == 2]
        remaining = TIMELINE_MAX_ENTRIES - len(important)
        if remaining > 0:
            unique = important + milestones[:remaining]
        else:
            unique = important[:TIMELINE_MAX_ENTRIES]
        # Re-sort after trimming
        unique.sort(key=lambda x: (x[0], x[4]))

    if len(unique) < 2:
        return ""

    # SVG dimensions
    line_x = 100
    row_height = 40
    svg_height = len(unique) * row_height + 40
    svg_width = 600

    elements = []
    # Central vertical line
    elements.append(
        f'  <line x1="{line_x}" y1="20" x2="{line_x}" y2="{svg_height - 20}" '
        f'stroke="{COLORS["tan"]}" stroke-width="2"/>'
    )

    for i, (year_int, display_year, desc, etype, priority) in enumerate(unique):
        y = 30 + i * row_height
        # Dot size and color based on type
        if etype == "founding":
            r, fill = 10, COLORS["teal"]
        elif etype == "event":
            r, fill = 7, COLORS["teal"]
        else:
            r, fill = 6, COLORS["gold"]

        elements.append(
            f'  <circle cx="{line_x}" cy="{y}" r="{r}" fill="{fill}" '
            f'stroke="{COLORS["warm_paper"]}" stroke-width="2"/>'
        )
        # Year label (left)
        elements.append(
            f'  <text x="{line_x - 18}" y="{y + 4}" font-size="11" font-weight="700" '
            f'fill="{COLORS["dark_brown"]}" text-anchor="end" '
            f"font-family=\"'Sometype Mono', monospace\">{_svg_text_esc(display_year)}</text>"
        )
        # Description (right) — truncate long descriptions, store full for tooltip
        is_truncated = len(desc) > TIMELINE_DESC_MAX_LEN
        display_desc = desc if not is_truncated else desc[:TIMELINE_DESC_MAX_LEN - 2] + "..."
        full_attr = f' data-full-desc="{esc(desc)}"' if is_truncated else ""
        elements.append(
            f'  <text x="{line_x + 18}" y="{y + 4}" font-size="10" '
            f'fill="{COLORS["secondary_brown"]}" class="gg-tl-desc"{full_attr} '
            f"font-family=\"'Sometype Mono', monospace\">{_svg_text_esc(display_desc)}</text>"
        )

    content = "\n".join(elements)
    return f'''<div class="gg-series-timeline">
    <svg viewBox="0 0 {svg_width} {svg_height}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Series timeline">
{content}
    </svg>
  </div>'''


def build_decision_matrix(series: dict, race_data: dict) -> str:
    """Build HTML comparison table with inline SVG dot-meters."""
    events = series.get("events", [])
    profiled = []
    for e in events:
        slug = e.get("slug")
        if slug and e.get("has_profile") and slug in race_data:
            rd = race_data[slug]
            if rd.get("gravel_god_rating"):
                profiled.append((e, rd))

    if len(profiled) < 2:
        return ""

    # Column headers (event names linking to profiles)
    header_cells = ['<th>Criteria</th>']
    for e, _ in profiled:
        slug = e.get("slug", "")
        name = e.get("name", "")
        short = name if len(name) <= MATRIX_NAME_MAX_LEN else name[:MATRIX_NAME_MAX_LEN - 2] + "..."
        if slug:
            header_cells.append(f'<th><a href="/race/{esc(slug)}/">{esc(short)}</a></th>')
        else:
            header_cells.append(f'<th>{esc(short)}</th>')
    header_row = "<tr>" + "".join(header_cells) + "</tr>"

    # Data rows
    data_rows = []
    scores_by_criterion = {}
    for label, criterion_key in MATRIX_CRITERIA:
        cells = [f'<td>{esc(label)}</td>']
        row_scores = []
        for e, rd in profiled:
            score = _extract_criterion(rd, criterion_key)
            row_scores.append((e.get("name", ""), score))
            dots = _dot_meter_svg(score)
            cells.append(f'<td class="gg-series-matrix-dot">{dots}</td>')
        data_rows.append("<tr>" + "".join(cells) + "</tr>")
        scores_by_criterion[label] = row_scores

    rows_html = "\n        ".join(data_rows)

    # "BEST FOR" editorial picks — with tie handling
    def _pick_best(scores, highest=True):
        """Return name(s) for best/worst score, or None if too many tie (>50%)."""
        if not scores:
            return None
        target = max(scores, key=lambda x: x[1])[1] if highest else min(scores, key=lambda x: x[1])[1]
        winners = [name for name, score in scores if score == target]
        # If more than half the events tie, the pick is meaningless
        if len(winners) > len(scores) / 2:
            return None
        return " &amp; ".join(esc(w) for w in winners)

    picks = []
    diff_scores = scores_by_criterion.get("Difficulty", [])
    if diff_scores:
        hardest = _pick_best(diff_scores, highest=True)
        if hardest:
            picks.append(f"<strong>Hardest challenge:</strong> {hardest}")
        easiest = _pick_best(diff_scores, highest=False)
        if easiest:
            picks.append(f"<strong>First-timers:</strong> {easiest}")
    budget_scores = scores_by_criterion.get("Budget-Friendliness", [])
    if budget_scores:
        best_val = _pick_best(budget_scores, highest=True)
        if best_val:
            picks.append(f"<strong>Best value:</strong> {best_val}")
    tech_scores = scores_by_criterion.get("Technicality", [])
    if tech_scores:
        most_tech = _pick_best(tech_scores, highest=True)
        if most_tech:
            picks.append(f"<strong>Most technical:</strong> {most_tech}")

    picks_html = ""
    if picks:
        picks_list = " &middot; ".join(picks)
        picks_html = f'<div class="gg-series-matrix-picks">{picks_list}</div>'

    return f'''<div class="gg-series-matrix">
    <div class="gg-series-matrix-title">Decision Matrix</div>
    <table>
      <thead>{header_row}</thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
    {picks_html}
  </div>'''


def _build_faq_pairs(series: dict, race_data: dict) -> list:
    """Build all FAQ question-answer pairs for a series.

    Single source of truth for FAQ content — used by both HTML and JSON-LD builders.
    Returns list of (question, answer) tuples.
    """
    name = series.get("display_name") or series.get("name", "")
    events = series.get("events", [])
    slug = series.get("slug", "")
    year = CURRENT_YEAR

    qa_pairs = []

    # Q1: How many events?
    event_count = len(events)
    event_names = [e.get("name", "") for e in events]
    names_list = ", ".join(event_names[:MAX_EVENT_NAMES_IN_FAQ])
    if len(event_names) > MAX_EVENT_NAMES_IN_FAQ:
        names_list += f", and {len(event_names) - MAX_EVENT_NAMES_IN_FAQ} more"
    qa_pairs.append((
        f"How many {name} events are there in {year}?",
        f"The {name} features {event_count} events in {year}: {names_list}."
    ))

    # Q2: Which event is hardest?
    profiled_with_diff = []
    for e in events:
        e_slug = e.get("slug")
        if e_slug and e_slug in race_data:
            rd = race_data[e_slug]
            diff = _avg_scores(rd, ["length", "technicality", "elevation", "altitude"])
            if diff > 0:
                vitals = rd.get("vitals", {})
                dist = vitals.get("distance_mi", 0)
                elev = vitals.get("elevation_ft", 0)
                profiled_with_diff.append((e.get("name", ""), diff, dist, elev))
    if profiled_with_diff:
        hardest = max(profiled_with_diff, key=lambda x: x[1])
        stats = ""
        if hardest[2]:
            stats += f" at {hardest[2]} miles"
        if hardest[3]:
            stats += f" and {hardest[3]:,} feet of climbing"
        qa_pairs.append((
            f"Which {name} event is the hardest?",
            f"{hardest[0]} is the most challenging event in the series with a difficulty "
            f"rating of {hardest[1]}/5{stats}."
        ))

    # Q3: Schedule
    sorted_events = sorted(events, key=lambda e: MONTH_ORDER.get(e.get("month", "TBD"), 99))
    schedule_parts = []
    for e in sorted_events:
        month = e.get("month", "TBD")
        loc = e.get("location", "")
        schedule_parts.append(f"{e.get('name', '')} ({month}, {loc})" if loc else f"{e.get('name', '')} ({month})")
    schedule_text = "; ".join(schedule_parts)
    qa_pairs.append((
        f"What is the {name} {year} schedule?",
        f"The {name} {year} calendar includes: {schedule_text}."
    ))

    # Q4: Cost — readable prose, not raw data dump
    cost_entries = []
    for e in events:
        e_slug = e.get("slug")
        if e_slug and e_slug in race_data:
            rd = race_data[e_slug]
            reg = rd.get("vitals", {}).get("registration", "")
            if reg:
                cost_entries.append((e.get("name", ""), reg))
    if cost_entries:
        shown = cost_entries[:MAX_COST_ITEMS_IN_FAQ]
        parts = [f"{n} ({cost})" for n, cost in shown]
        cost_text = f"Registration costs vary across the {name}. "
        cost_text += ", ".join(parts[:-1]) + f", and {parts[-1]}" if len(parts) > 1 else parts[0]
        cost_text += "."
        if len(cost_entries) > MAX_COST_ITEMS_IN_FAQ:
            cost_text += f" The remaining {len(cost_entries) - MAX_COST_ITEMS_IN_FAQ} events have similar price ranges."
        qa_pairs.append((
            f"How much does it cost to enter {name} races?",
            cost_text
        ))

    # Q5: Terrain types — extract clean keywords only, never raw paragraph strings
    _terrain_kw_list = [
        "gravel", "dirt", "pavement", "paved", "singletrack", "single-track",
        "sand", "rock", "mud", "fire road", "doubletrack", "double-track",
        "mixed", "water crossing", "mountain", "high desert",
    ]
    _terrain_normalize = {
        "single-track": "singletrack",
        "double-track": "doubletrack",
        "paved": "pavement",
    }
    terrain_keywords = set()
    tech_ratings = []
    for e in events:
        e_slug = e.get("slug")
        if e_slug and e_slug in race_data:
            rd = race_data[e_slug]
            # Scan both terrain_types list AND surface string for keywords
            text_sources = rd.get("vitals", {}).get("terrain_types", [])
            surface = rd.get("terrain", {}).get("surface", "")
            if surface:
                text_sources.append(surface)
            for raw in text_sources:
                raw_lower = str(raw).lower()
                for kw in _terrain_kw_list:
                    if kw in raw_lower:
                        clean = _terrain_normalize.get(kw, kw)
                        terrain_keywords.add(clean)
            tech = rd.get("terrain", {}).get("technical_rating")
            if tech:
                tech_ratings.append(tech)
    if terrain_keywords:
        sorted_terrain = sorted(terrain_keywords)[:MAX_TERRAIN_TYPES_IN_FAQ]
        terrain_list = ", ".join(sorted_terrain)
        answer = f"The {name} features diverse terrain including {terrain_list}."
        if tech_ratings:
            avg_tech = sum(tech_ratings) / len(tech_ratings)
            answer += f" Technical ratings across events range from {min(tech_ratings)}/5 to {max(tech_ratings)}/5 (average {avg_tech:.1f}/5)."
        qa_pairs.append((
            f"What terrain types are in {name} races?",
            answer
        ))

    # Q6: LTGP-specific points question
    if slug == "life-time-grand-prix":
        fmt = series.get("format_overview", "")
        if fmt:
            qa_pairs.append((
                "How does the Life Time Grand Prix points system work?",
                fmt
            ))

    return qa_pairs


def build_series_faq(series: dict, race_data: dict, race_lookup: dict) -> str:
    """Build FAQ section with expandable Q&A."""
    qa_pairs = _build_faq_pairs(series, race_data)
    if not qa_pairs:
        return ""

    items = []
    for question, answer in qa_pairs:
        items.append(
            f'<details>\n'
            f'      <summary>{esc(question)}</summary>\n'
            f'      <div class="gg-series-faq-answer">{esc(answer)}</div>\n'
            f'    </details>'
        )
    items_html = "\n    ".join(items)

    return f'''<div class="gg-series-faq">
    <div class="gg-series-faq-title">Frequently Asked Questions</div>
    {items_html}
  </div>'''


def build_faq_jsonld(series: dict, race_data: dict, race_lookup: dict) -> str:
    """Build FAQPage JSON-LD for structured data.

    Uses the same _build_faq_pairs() as the HTML FAQ — guaranteed to have
    identical questions. All pairs are included (not a subset).
    """
    qa_pairs = _build_faq_pairs(series, race_data)
    if not qa_pairs:
        return ""

    faq_entries = []
    for q, a in qa_pairs:
        entry = {
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": a
            }
        }
        faq_entries.append(json.dumps(entry, ensure_ascii=False))

    entries_json = ",\n      ".join(faq_entries)

    return f'''<script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": [
      {entries_json}
    ]
  }}
  </script>'''


# ── Page assembly ─────────────────────────────────────────────


def build_hub_page(series: dict, race_lookup: dict, race_data: dict) -> str:
    """Generate a full series hub page."""
    name = series.get("display_name") or series.get("name", "")
    slug = series.get("slug", "")
    tagline = series.get("tagline", "")
    founded = series.get("founded", "")
    organizer = series.get("organizer", "")
    website = series.get("website", "")
    description = series.get("description", "")
    history = series.get("history", "")
    format_overview = series.get("format_overview", "")
    events = series.get("events", [])
    key_stats = series.get("key_stats", {})

    total_events = key_stats.get("total_events", len(events))
    countries = key_stats.get("countries", 1)

    # Sort events by month
    sorted_events = sorted(events, key=lambda e: MONTH_ORDER.get(e.get("month", "TBD"), 99))

    # Build event cards
    cards_html = []
    for event in sorted_events:
        cards_html.append(build_event_card(event, race_lookup))
    cards = "\n    ".join(cards_html)

    # Build JSON-LD: SportsOrganization + ItemList
    item_list_entries = []
    for i, event in enumerate(sorted_events, 1):
        event_slug = event.get("slug")
        event_url = f"{SITE_BASE_URL}/race/{event_slug}/" if event_slug and event.get("has_profile") else ""
        entry = {
            "@type": "ListItem",
            "position": i,
            "name": event.get("name", ""),
        }
        if event_url:
            entry["url"] = event_url
        item_list_entries.append(json.dumps(entry, ensure_ascii=False))
    item_list_json = ",\n      ".join(item_list_entries)

    canonical = f"{SITE_BASE_URL}/race/series/{slug}/"
    page_title = f"{name} — All Events & Series Guide | Gravel God"
    meta_desc = tagline if tagline else f"Complete guide to the {name} race series."

    # Stats line for hero
    country_text = f"{countries} {'country' if countries == 1 else 'countries'}"
    stats_parts = [f"{total_events} events", country_text]
    if founded:
        stats_parts.append(f"Est. {founded}")
    stats_line = " &middot; ".join(stats_parts)

    # Website button
    site_btn = ""
    if website:
        site_btn = f'\n    <a href="{esc(website)}" class="gg-btn gg-btn--series-site" target="_blank" rel="noopener">OFFICIAL SITE &rarr;</a>'

    # Existing sections
    overview_section = build_collapsible_section("Overview", description, "overview")
    format_section = build_collapsible_section("Format", format_overview, "format")

    # New infographic sections
    radar_svg = build_series_radar_svg(series, race_data)
    bars_svg = build_distance_elevation_svg(series, race_data)
    timeline_svg = build_series_timeline_svg(series, race_data)
    map_svg = build_geographic_map_svg(series, race_data, race_lookup)
    matrix_html = build_decision_matrix(series, race_data)
    faq_html = build_series_faq(series, race_data, race_lookup)
    faq_jsonld = build_faq_jsonld(series, race_data, race_lookup)

    # "Series At A Glance" wrapper for radar + bars
    # Count profiled events for subtitle when showing partial data
    profiled_count = sum(
        1 for e in events
        if e.get("slug") and e.get("has_profile") and e.get("slug") in race_data
        and race_data[e["slug"]].get("gravel_god_rating")
    )
    at_a_glance = ""
    if radar_svg or bars_svg:
        subtitle = ""
        if profiled_count < total_events:
            subtitle = (
                f'<div class="gg-series-at-a-glance-subtitle">'
                f'{profiled_count} of {total_events} events profiled</div>'
            )
        at_a_glance = f'''<div class="gg-series-at-a-glance">
    <div class="gg-series-at-a-glance-title">SERIES AT A GLANCE</div>
    {subtitle}
    {radar_svg}
    {bars_svg}
  </div>'''

    # History section with timeline SVG inside (above prose text)
    history_section = ""
    if history:
        paragraphs = history.strip().split("\n\n") if "\n\n" in history else [history]
        p_html = "\n".join(f"<p>{esc(p.strip())}</p>" for p in paragraphs if p.strip())
        history_section = f'''<details class="gg-series-section" open>
    <summary class="gg-series-section-title">History</summary>
    <div class="gg-series-section-body">
      {timeline_svg}
      {p_html}
    </div>
  </details>'''

    font_face = get_font_face_css()
    tokens = get_tokens_css()

    teal = COLORS["teal"]

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(page_title)}</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical)}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%233a2e25'/><text x='16' y='24' text-anchor='middle' font-family='serif' font-size='24' font-weight='700' fill='%239a7e0a'>G</text></svg>">
  <meta property="og:title" content="{esc(page_title)}">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical)}">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "SportsOrganization",
    "name": "{_json_str(name)}",
    "description": "{_json_str(meta_desc)}",
    "url": "{_json_str(canonical)}",
    "sport": "Cycling",
    "foundingDate": "{founded}"
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
      {{
        "@type": "ListItem",
        "position": 1,
        "name": "Home",
        "item": "{SITE_BASE_URL}/"
      }},
      {{
        "@type": "ListItem",
        "position": 2,
        "name": "Gravel Races",
        "item": "{SITE_BASE_URL}/gravel-races/"
      }},
      {{
        "@type": "ListItem",
        "position": 3,
        "name": "Series",
        "item": "{SITE_BASE_URL}/race/series/"
      }},
      {{
        "@type": "ListItem",
        "position": 4,
        "name": "{_json_str(name)}",
        "item": "{_json_str(canonical)}"
      }}
    ]
  }}
  </script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "{_json_str(name)} Events",
    "numberOfItems": {len(events)},
    "itemListElement": [
      {item_list_json}
    ]
  }}
  </script>
  {faq_jsonld}
  <style>
{font_face}
{tokens}

.gg-series-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 24px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-warm-paper);
  min-height: 100vh;
}}
.gg-series-page *, .gg-series-page *::before, .gg-series-page *::after {{
  border-radius: 0 !important;
  box-shadow: none !important;
}}

/* Site header */
.gg-site-header {{
  padding: 16px 24px;
  border-bottom: 2px solid var(--gg-color-gold);
}}
.gg-site-header-inner {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 960px;
  margin: 0 auto;
}}
.gg-site-header-logo img {{
  display: block;
  height: 50px;
  width: auto;
}}
.gg-site-header-nav {{
  display: flex;
  gap: 28px;
}}
.gg-site-header-nav a {{
  color: var(--gg-color-dark-brown);
  text-decoration: none;
  font-family: 'Sometype Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
}}
.gg-site-header-nav a:hover {{
  color: var(--gg-color-gold);
}}

/* Breadcrumb */
.gg-series-breadcrumb {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  padding: 12px 0;
  letter-spacing: 0.5px;
}}
.gg-series-breadcrumb a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
}}
.gg-series-breadcrumb a:hover {{
  color: var(--gg-color-dark-brown);
}}

/* Hero */
.gg-series-hero {{
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-dark-brown);
  padding: 48px 32px;
  margin: 0 -24px;
  border-bottom: 2px solid var(--gg-color-gold);
}}
.gg-series-hero-badge {{
  display: inline-block;
  background: transparent;
  color: {teal};
  padding: 4px 12px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  border: 2px solid {teal};
  margin-bottom: 16px;
}}
.gg-series-hero-founded {{
  display: inline-block;
  margin-left: 12px;
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
}}
.gg-series-hero h1 {{
  font-family: var(--gg-font-editorial);
  font-size: 36px;
  font-weight: 700;
  line-height: 1.1;
  margin: 0 0 12px 0;
}}
.gg-series-hero-stats {{
  font-size: 13px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 12px;
}}
.gg-series-hero-tagline {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  line-height: 1.5;
  color: var(--gg-color-secondary-brown);
  max-width: 720px;
  margin-bottom: 16px;
}}
.gg-btn--series-site {{
  display: inline-block;
  padding: 8px 20px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  text-decoration: none;
  color: var(--gg-color-primary-brown);
  border: 1px solid var(--gg-color-primary-brown);
  transition: background 0.15s, color 0.15s;
}}
.gg-btn--series-site:hover {{
  background: var(--gg-color-gold);
  color: var(--gg-color-warm-paper);
  border-color: var(--gg-color-gold);
}}

/* Collapsible sections */
.gg-series-section {{
  border-bottom: 2px solid var(--gg-color-sand);
  padding: 0;
}}
.gg-series-section-title {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  padding: 16px 0;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.gg-series-section-title::after {{
  content: "\\25BC";
  font-size: 9px;
  transition: transform 0.2s;
}}
.gg-series-section[open] .gg-series-section-title::after {{
  transform: rotate(180deg);
}}
.gg-series-section-title::-webkit-details-marker {{
  display: none;
}}
.gg-series-section-body {{
  padding: 0 0 20px 0;
}}
.gg-series-section-body p {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  line-height: 1.7;
  color: var(--gg-color-dark-brown);
  max-width: 720px;
  margin: 0 0 16px 0;
}}
.gg-series-section-body p:last-child {{
  margin-bottom: 0;
}}

/* Series At A Glance */
.gg-series-at-a-glance {{
  padding: 16px 0 24px;
  border-bottom: 2px solid var(--gg-color-sand);
}}
.gg-series-at-a-glance-title {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  padding: 16px 0;
  border-bottom: 1px solid var(--gg-color-gold);
  margin-bottom: 4px;
}}
.gg-series-at-a-glance-subtitle {{
  font-family: var(--gg-font-data);
  font-size: 10px;
  color: var(--gg-color-warm-brown);
  letter-spacing: 0.5px;
  margin-bottom: 12px;
  font-style: italic;
}}

/* Radar chart */
.gg-series-radar {{
  margin: 16px 0;
}}
.gg-series-radar svg {{
  max-width: 500px;
  width: 100%;
  height: auto;
}}
.gg-series-radar-legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  padding: 12px 0;
}}
.gg-series-radar-legend-item {{
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
  letter-spacing: 0.5px;
}}
.gg-series-radar-legend-swatch {{
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}}

/* Bar chart */
.gg-series-bars {{
  margin: 16px 0;
  overflow-x: auto;
}}
.gg-series-bars svg {{
  max-width: 600px;
  width: 100%;
  height: auto;
}}

/* Geographic map */
.gg-series-map {{
  padding: 16px 0 24px;
  border-bottom: 2px solid var(--gg-color-sand);
}}
.gg-series-map-title {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  margin-bottom: 12px;
}}
.gg-series-map svg {{
  max-width: 700px;
  width: 100%;
  height: auto;
}}

/* Timeline */
.gg-series-timeline {{
  margin: 0 0 20px;
  overflow-x: auto;
}}
.gg-series-timeline svg {{
  max-width: 600px;
  width: 100%;
  height: auto;
}}

/* Decision matrix */
.gg-series-matrix {{
  padding: 24px 0;
  border-bottom: 2px solid var(--gg-color-sand);
  overflow-x: auto;
}}
.gg-series-matrix-title {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  margin-bottom: 16px;
}}
.gg-series-matrix table {{
  width: 100%;
  border-collapse: collapse;
  font-family: var(--gg-font-data);
  font-size: 11px;
}}
.gg-series-matrix th {{
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 8px 6px;
  border-bottom: 1px solid var(--gg-color-gold);
  text-align: left;
  color: var(--gg-color-dark-brown);
  white-space: nowrap;
}}
.gg-series-matrix th a {{
  color: var(--gg-color-dark-brown);
  text-decoration: none;
}}
.gg-series-matrix th a:hover {{
  color: var(--gg-color-gold);
}}
.gg-series-matrix td {{
  padding: 8px 6px;
  border-bottom: 1px solid var(--gg-color-sand);
  vertical-align: middle;
}}
.gg-series-matrix td:first-child {{
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  white-space: nowrap;
}}
.gg-series-matrix-dot svg {{
  vertical-align: middle;
}}
.gg-series-matrix-picks {{
  margin-top: 16px;
  font-family: var(--gg-font-data);
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 0.5px;
  line-height: 1.8;
}}
.gg-series-matrix-picks strong {{
  color: var(--gg-color-dark-brown);
  text-transform: uppercase;
  letter-spacing: 1px;
}}

/* FAQ */
.gg-series-faq {{
  padding: 24px 0;
}}
.gg-series-faq-title {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  padding-bottom: 16px;
  border-bottom: 1px solid var(--gg-color-gold);
}}
.gg-series-faq details {{
  border-bottom: 1px solid var(--gg-color-sand);
}}
.gg-series-faq summary {{
  font-family: var(--gg-font-editorial);
  font-size: 16px;
  font-weight: 700;
  color: var(--gg-color-dark-brown);
  padding: 14px 0;
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}}
.gg-series-faq summary::after {{
  content: "+";
  font-family: var(--gg-font-data);
  font-size: 16px;
  font-weight: 700;
  color: var(--gg-color-secondary-brown);
  transition: transform 0.2s;
}}
.gg-series-faq details[open] summary::after {{
  content: "\\2212";
}}
.gg-series-faq summary::-webkit-details-marker {{
  display: none;
}}
.gg-series-faq-answer {{
  padding: 0 0 16px;
  font-family: var(--gg-font-editorial);
  font-size: 15px;
  line-height: 1.7;
  color: var(--gg-color-dark-brown);
  max-width: 720px;
}}

/* Radar interactivity */
.gg-series-radar polygon[data-radar-idx] {{
  cursor: pointer;
  transition: fill-opacity 0.2s, stroke-width 0.2s;
}}
.gg-series-radar.gg-radar-hover polygon[data-radar-idx] {{
  fill-opacity: 0.03;
  stroke-width: 1;
}}
.gg-series-radar.gg-radar-hover polygon[data-radar-idx].gg-radar-active {{
  fill-opacity: 0.35;
  stroke-width: 3;
}}
.gg-series-radar-legend-item {{
  cursor: pointer;
  transition: opacity 0.2s;
}}
.gg-series-radar.gg-radar-hover .gg-series-radar-legend-item {{
  opacity: 0.35;
}}
.gg-series-radar.gg-radar-hover .gg-series-radar-legend-item.gg-radar-active {{
  opacity: 1;
}}

/* Matrix column highlight */
.gg-series-matrix td.gg-col-highlight,
.gg-series-matrix th.gg-col-highlight {{
  background: var(--gg-color-sand);
}}

/* Timeline tooltip */
.gg-series-timeline-tip {{
  position: absolute;
  background: var(--gg-color-primary-brown);
  color: var(--gg-color-warm-paper);
  font-family: var(--gg-font-data);
  font-size: 11px;
  padding: 6px 10px;
  max-width: 340px;
  pointer-events: none;
  z-index: 10;
  line-height: 1.4;
  opacity: 0;
  transition: opacity 0.15s;
}}
.gg-series-timeline-tip.gg-visible {{
  opacity: 1;
}}

/* Animations */
@keyframes gg-radar-draw {{
  to {{ stroke-dashoffset: 0; }}
}}
@keyframes gg-bar-grow {{
  from {{ transform: scaleX(0); }}
  to {{ transform: scaleX(1); }}
}}

/* Event calendar */
.gg-series-calendar-title {{
  font-family: var(--gg-font-data);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  padding: 24px 0 16px;
  border-bottom: 1px solid var(--gg-color-gold);
}}
.gg-series-calendar {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 0;
}}
.gg-series-event-card {{
  padding: 16px;
  border-bottom: 2px solid var(--gg-color-sand);
  border-right: 2px solid var(--gg-color-sand);
  transition: background 0.15s;
}}
.gg-series-event-card:hover {{
  background: var(--gg-color-sand);
}}
.gg-series-event-month {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 2px;
  text-transform: uppercase;
  color: {teal};
  margin-bottom: 6px;
}}
.gg-series-event-name {{
  font-family: var(--gg-font-editorial);
  font-size: 15px;
  font-weight: 700;
  color: var(--gg-color-dark-brown);
  text-decoration: none;
  display: block;
  margin-bottom: 4px;
}}
a.gg-series-event-name:hover {{
  color: var(--gg-color-gold);
}}
.gg-series-event-link {{
  font-size: 12px;
  color: var(--gg-color-gold);
}}
.gg-series-event-location {{
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}}
.gg-series-event-badges {{
  display: flex;
  gap: 6px;
  align-items: center;
}}
.gg-series-event-tier {{
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 2px 6px;
  border: 1px solid var(--gg-color-secondary-brown);
  color: var(--gg-color-secondary-brown);
}}
.gg-tier-1 {{
  color: var(--gg-color-gold);
  border-color: var(--gg-color-gold);
}}
.gg-tier-2 {{
  color: var(--gg-color-teal);
  border-color: var(--gg-color-teal);
}}
.gg-tier-3 {{
  color: var(--gg-color-secondary-brown);
  border-color: var(--gg-color-secondary-brown);
}}
.gg-series-event-score {{
  font-family: var(--gg-font-editorial);
  font-size: 14px;
  font-weight: 700;
  color: var(--gg-color-dark-brown);
}}
.gg-series-score-label {{
  font-family: var(--gg-font-data);
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 1.5px;
  color: var(--gg-color-warm-brown);
  margin-left: 3px;
}}
.gg-series-event-racer {{
  font-family: var(--gg-font-editorial);
  font-size: 14px;
  font-weight: 700;
  color: var(--gg-color-teal);
  margin-left: 8px;
}}
.gg-series-event-racer--empty {{ opacity: 0.4; color: var(--gg-color-warm-brown); }}

/* Footer */
.gg-series-footer {{
  padding: 24px 0;
  margin-top: 32px;
  border-top: 2px solid var(--gg-color-gold);
  text-align: center;
  font-size: 11px;
  color: var(--gg-color-secondary-brown);
  letter-spacing: 1px;
  text-transform: uppercase;
}}
.gg-series-footer a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
}}
.gg-series-footer a:hover {{
  color: var(--gg-color-dark-brown);
}}

/* Mobile */
@media (max-width: 768px) {{
  .gg-series-hero {{ padding: 32px 20px; }}
  .gg-series-hero h1 {{ font-size: 28px; }}
  .gg-site-header-nav {{ gap: 12px; }}
  .gg-site-header-nav a {{ font-size: 10px; letter-spacing: 1.5px; }}
  .gg-series-calendar {{ grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); }}
  .gg-series-matrix table {{ font-size: 10px; }}
  .gg-series-matrix th, .gg-series-matrix td {{ padding: 6px 4px; }}
  /* Sticky first column for matrix on mobile */
  .gg-series-matrix td:first-child,
  .gg-series-matrix th:first-child {{
    position: sticky;
    left: 0;
    background: var(--gg-color-warm-paper);
    z-index: 1;
  }}
  /* Scroll hint — fade on right edge */
  .gg-series-matrix {{
    position: relative;
  }}
  .gg-series-matrix::after {{
    content: "";
    position: absolute;
    top: 0;
    right: 0;
    width: 24px;
    height: 100%;
    background: linear-gradient(to right, transparent, var(--gg-color-warm-paper));
    pointer-events: none;
  }}
}}
@media (max-width: 480px) {{
  .gg-series-page {{ padding: 0 12px; }}
  .gg-series-hero {{ padding: 24px 12px; margin: 0 -12px; }}
  .gg-series-hero h1 {{ font-size: 22px; }}
  .gg-series-calendar {{ grid-template-columns: 1fr; }}
  .gg-series-event-card {{ border-right: none; }}
  .gg-site-header {{ padding: 12px 16px; }}
  .gg-site-header-inner {{ flex-wrap: wrap; justify-content: center; gap: 10px; }}
  .gg-site-header-logo img {{ height: 40px; }}
  .gg-site-header-nav {{ flex-wrap: wrap; justify-content: center; gap: 8px; }}
  .gg-series-radar-legend {{ gap: 6px 10px; }}
  .gg-series-matrix-picks {{ font-size: 10px; }}
}}
  </style>
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
</head>
<body style="margin:0;background:var(--gg-color-warm-paper)">

<div class="gg-series-page">

  <header class="gg-site-header">
    <div class="gg-site-header-inner">
      <a href="/" class="gg-site-header-logo">
        <img src="https://gravelgodcycling.com/wp-content/uploads/2021/09/cropped-Gravel-God-logo.png" alt="Gravel God" width="50" height="50">
      </a>
      <nav class="gg-site-header-nav">
        <a href="/gravel-races/">RACES</a>
        <a href="/coaching/">COACHING</a>
        <a href="/articles/">ARTICLES</a>
        <a href="/about/">ABOUT</a>
      </nav>
    </div>
  </header>

  <div class="gg-series-breadcrumb">
    <a href="/">Home</a> &rsaquo;
    <a href="/gravel-races/">Gravel Races</a> &rsaquo;
    <a href="/race/series/">Series</a> &rsaquo;
    <span>{esc(name)}</span>
  </div>

  <section class="gg-series-hero">
    <span class="gg-series-hero-badge">SERIES</span>
    {"<span class='gg-series-hero-founded'>Founded: " + str(founded) + "</span>" if founded else ""}
    <h1>{esc(name)}</h1>
    <div class="gg-series-hero-stats">{stats_line}</div>
    <p class="gg-series-hero-tagline">{esc(tagline)}</p>{site_btn}
  </section>

  {overview_section}

  {at_a_glance}

  {history_section}

  {format_section}

  {map_svg}

  <div class="gg-series-calendar-title">{CURRENT_YEAR} Event Calendar</div>
  <div class="gg-series-calendar">
    {cards}
  </div>

  {matrix_html}

  {faq_html}

  <footer class="gg-series-footer">
    <a href="/">Gravel God</a> &middot;
    <a href="/gravel-races/">Search All Races</a> &middot;
    <a href="/race/methodology/">Methodology</a>
  </footer>

</div>

<script>
(function() {{
  'use strict';

  /* ── Radar: hover/click legend to highlight polygon ── */
  var radar = document.querySelector('.gg-series-radar');
  if (radar) {{
    var legendItems = radar.querySelectorAll('[data-radar-idx]');
    var polygons = radar.querySelectorAll('polygon[data-radar-idx]');
    var pinned = null;

    function highlightRadar(idx) {{
      radar.classList.add('gg-radar-hover');
      legendItems.forEach(function(el) {{
        el.classList.toggle('gg-radar-active', el.getAttribute('data-radar-idx') === String(idx));
      }});
      polygons.forEach(function(el) {{
        el.classList.toggle('gg-radar-active', el.getAttribute('data-radar-idx') === String(idx));
      }});
    }}

    function clearRadar() {{
      if (pinned !== null) return;
      radar.classList.remove('gg-radar-hover');
      legendItems.forEach(function(el) {{ el.classList.remove('gg-radar-active'); }});
      polygons.forEach(function(el) {{ el.classList.remove('gg-radar-active'); }});
    }}

    legendItems.forEach(function(item) {{
      item.addEventListener('mouseenter', function() {{
        if (pinned === null) highlightRadar(this.getAttribute('data-radar-idx'));
      }});
      item.addEventListener('mouseleave', clearRadar);
      item.addEventListener('click', function(e) {{
        e.preventDefault();
        var idx = this.getAttribute('data-radar-idx');
        if (pinned === idx) {{
          pinned = null;
          clearRadar();
        }} else {{
          pinned = idx;
          highlightRadar(idx);
        }}
      }});
    }});

    polygons.forEach(function(poly) {{
      poly.addEventListener('mouseenter', function() {{
        if (pinned === null) highlightRadar(this.getAttribute('data-radar-idx'));
      }});
      poly.addEventListener('mouseleave', clearRadar);
      poly.addEventListener('click', function(e) {{
        var idx = this.getAttribute('data-radar-idx');
        if (pinned === idx) {{
          pinned = null;
          clearRadar();
        }} else {{
          pinned = idx;
          highlightRadar(idx);
        }}
      }});
    }});
  }}

  /* ── Matrix: column highlight on hover ── */
  var matrix = document.querySelector('.gg-series-matrix table');
  if (matrix) {{
    var cells = matrix.querySelectorAll('th, td');
    cells.forEach(function(cell) {{
      cell.addEventListener('mouseenter', function() {{
        var colIdx = Array.prototype.indexOf.call(this.parentNode.children, this);
        matrix.querySelectorAll('th, td').forEach(function(c) {{
          var cIdx = Array.prototype.indexOf.call(c.parentNode.children, c);
          c.classList.toggle('gg-col-highlight', cIdx === colIdx && colIdx > 0);
        }});
      }});
      cell.addEventListener('mouseleave', function() {{
        matrix.querySelectorAll('.gg-col-highlight').forEach(function(c) {{
          c.classList.remove('gg-col-highlight');
        }});
      }});
    }});
  }}

  /* ── Timeline: tooltip for truncated descriptions ── */
  var timeline = document.querySelector('.gg-series-timeline');
  if (timeline) {{
    var tip = document.createElement('div');
    tip.className = 'gg-series-timeline-tip';
    timeline.style.position = 'relative';
    timeline.appendChild(tip);

    var tlTexts = timeline.querySelectorAll('.gg-tl-desc[data-full-desc]');
    tlTexts.forEach(function(el) {{
      el.style.cursor = 'pointer';
      el.addEventListener('mouseenter', function(e) {{
        tip.textContent = this.getAttribute('data-full-desc');
        tip.classList.add('gg-visible');
        var rect = this.getBoundingClientRect();
        var parentRect = timeline.getBoundingClientRect();
        tip.style.left = (rect.left - parentRect.left) + 'px';
        tip.style.top = (rect.bottom - parentRect.top + 6) + 'px';
      }});
      el.addEventListener('mouseleave', function() {{
        tip.classList.remove('gg-visible');
      }});
    }});
  }}
}})();
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate series hub landing pages")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory (default: wordpress/output/race/series/)")
    args = parser.parse_args()

    output_base = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / "wordpress" / "output" / "race" / "series"
    output_base.mkdir(parents=True, exist_ok=True)

    if not SERIES_DIR.exists():
        print("ERROR: series-data/ not found. Create series definitions first.", file=sys.stderr)
        sys.exit(1)

    # Load race index for enriching event cards
    race_lookup = load_race_index()
    if race_lookup:
        print(f"Loaded {len(race_lookup)} races from index")
    else:
        print("WARN: No race index found. Event cards will lack tier/score data.")

    series_files = sorted(SERIES_DIR.glob("*.json"))
    if not series_files:
        print("ERROR: No series JSON files found in series-data/", file=sys.stderr)
        sys.exit(1)

    # Collect all profiled event slugs across all series for bulk loading
    all_profiled_slugs = []
    all_series_data = []
    for path in series_files:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        series = data.get("series", {})
        if not series.get("slug"):
            print(f"  SKIP {path.name} (no slug)")
            continue
        all_series_data.append(series)
        for event in series.get("events", []):
            if event.get("has_profile") and event.get("slug"):
                all_profiled_slugs.append(event["slug"])

    # Load full race data for all profiled events
    race_data = load_full_race_data(all_profiled_slugs)
    if race_data:
        print(f"Loaded {len(race_data)} full race profiles for enrichment")

    for series in all_series_data:
        slug = series["slug"]
        hub_dir = output_base / slug
        hub_dir.mkdir(parents=True, exist_ok=True)

        page_html = build_hub_page(series, race_lookup, race_data)
        out_path = hub_dir / "index.html"
        out_path.write_text(page_html, encoding="utf-8")

        event_count = len(series.get("events", []))
        print(f"  Generated series/{slug}/index.html ({event_count} events)")

    print(f"\nDone. {len(all_series_data)} series hub pages in {output_base}/")


if __name__ == "__main__":
    main()
