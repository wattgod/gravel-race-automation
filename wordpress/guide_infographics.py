#!/usr/bin/env python3
"""
Inline SVG/HTML infographic renderers for the Gravel God Training Guide.

Replaces 16 Pillow-generated raster infographics with server-rendered
inline SVG (charts/curves) and HTML/CSS (cards/grids). Hero photos
(ch1-hero through ch8-hero) remain as <img> tags — this module only
handles the infographic asset_ids.

All colors use CSS custom properties via var(--gg-color-*) so they
inherit from the :root block in the guide CSS.

No JavaScript. Pure static SVG/HTML.
"""

import html as _html
import json
from pathlib import Path

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"

# Module-level cache for race data loaded by renderers
_SCORING_CACHE = {}  # populated lazily by _load_unbound_rating()


def _esc(text) -> str:
    """HTML-escape a string."""
    return _html.escape(str(text)) if text else ""


# ── SVG Helpers ─────────────────────────────────────────────


def _svg_open(width: int, height: int, cls: str = "") -> str:
    """Open an SVG tag with viewBox for fluid scaling."""
    c = f' class="{cls}"' if cls else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}"'
        f'{c} role="img" aria-hidden="true"'
        f' style="width:100%;height:auto;display:block">'
    )


def _svg_close() -> str:
    return "</svg>"


def _svg_rect(x, y, w, h, fill="", stroke="", stroke_width=0, rx=0, extra="") -> str:
    """Render an SVG <rect>. rx=0 enforced (brand: no border-radius)."""
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}"']
    if fill:
        parts.append(f' fill="{fill}"')
    if stroke:
        parts.append(f' stroke="{stroke}" stroke-width="{stroke_width}"')
    if extra:
        parts.append(f" {extra}")
    parts.append("/>")
    return "".join(parts)


def _svg_text(x, y, text, font_size=14, fill="", anchor="start",
              weight="", family="", extra="") -> str:
    """Render an SVG <text> element.

    font-family is set via style="" attribute (not presentation attribute)
    so that CSS custom properties like var(--gg-font-data) can resolve.
    """
    parts = [f'<text x="{x}" y="{y}" font-size="{font_size}"']
    if fill:
        parts.append(f' fill="{fill}"')
    if anchor != "start":
        parts.append(f' text-anchor="{anchor}"')
    if weight:
        parts.append(f' font-weight="{weight}"')
    if family:
        # Use style attribute — presentation attributes can't resolve var()
        parts.append(f' style="font-family:{family}"')
    if extra:
        parts.append(f" {extra}")
    parts.append(f">{_esc(text)}</text>")
    return "".join(parts)


def _svg_line(x1, y1, x2, y2, stroke="", stroke_width=2, extra="") -> str:
    parts = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}"']
    if stroke:
        parts.append(f' stroke="{stroke}"')
    parts.append(f' stroke-width="{stroke_width}"')
    if extra:
        parts.append(f" {extra}")
    parts.append("/>")
    return "".join(parts)


def _svg_path(d: str, stroke="", stroke_width=2, fill="none", extra="") -> str:
    parts = [f'<path d="{d}"']
    if stroke:
        parts.append(f' stroke="{stroke}"')
    parts.append(f' stroke-width="{stroke_width}" fill="{fill}"')
    if extra:
        parts.append(f" {extra}")
    parts.append("/>")
    return "".join(parts)


# ── Smooth Curve Helper ─────────────────────────────────────


def _cubic_bezier_path(points: list[tuple[float, float]], closed: bool = False) -> str:
    """Convert a list of (x, y) points to a smooth SVG path using
    Catmull-Rom to cubic Bezier conversion.

    Returns an SVG path d-string like "M x0,y0 C cp1x,cp1y cp2x,cp2y x1,y1 ..."
    """
    if len(points) < 2:
        return ""
    if len(points) == 2:
        return f"M {points[0][0]},{points[0][1]} L {points[1][0]},{points[1][1]}"

    tension = 0.3  # controls curve tightness (0=straight, 0.5=very curvy)
    segments = []
    n = len(points)

    for i in range(n - 1):
        p0 = points[max(i - 1, 0)]
        p1 = points[i]
        p2 = points[min(i + 1, n - 1)]
        p3 = points[min(i + 2, n - 1)]

        # Control point 1: tangent at p1
        cp1x = p1[0] + (p2[0] - p0[0]) * tension
        cp1y = p1[1] + (p2[1] - p0[1]) * tension

        # Control point 2: tangent at p2
        cp2x = p2[0] - (p3[0] - p1[0]) * tension
        cp2y = p2[1] - (p3[1] - p1[1]) * tension

        if i == 0:
            segments.append(f"M {p1[0]:.1f},{p1[1]:.1f}")
        segments.append(
            f"C {cp1x:.1f},{cp1y:.1f} {cp2x:.1f},{cp2y:.1f} {p2[0]:.1f},{p2[1]:.1f}"
        )

    return " ".join(segments)


# ── Figure Wrapper ──────────────────────────────────────────


def _figure_wrap(inner: str, caption: str, layout: str = "inline",
                 asset_id: str = "", alt: str = "") -> str:
    """Wrap content in a <figure> with optional <figcaption> and aria-label."""
    cls = "gg-infographic"
    if layout and layout != "inline":
        cls += f" gg-infographic--{layout}"
    aid = f' data-asset-id="{_esc(asset_id)}"' if asset_id else ""
    aria = f' aria-label="{_esc(alt)}"' if alt else ""
    role = ' role="figure"' if alt else ""
    cap = (
        f'<figcaption class="gg-infographic-caption">{_esc(caption)}</figcaption>'
        if caption else ""
    )
    return f'<figure class="{cls}"{aid}{role}{aria}>{inner}{cap}</figure>'


# ── Shared SVG Micro-Icons (for gear grid cards) ────────────


def _icon_frame() -> str:
    """Minimal bike frame icon — triangle shape."""
    return (
        '<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">'
        '<path d="M8,32 L20,8 L32,32 Z" fill="none" '
        'stroke="var(--gg-color-primary-brown)" stroke-width="2.5"/>'
        '</svg>'
    )


def _icon_tire() -> str:
    """Tire icon — nested squares."""
    return (
        '<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">'
        '<rect x="4" y="4" width="32" height="32" fill="none" '
        'stroke="var(--gg-color-primary-brown)" stroke-width="2.5"/>'
        '<rect x="12" y="12" width="16" height="16" fill="none" '
        'stroke="var(--gg-color-secondary-brown)" stroke-width="2"/>'
        '</svg>'
    )


def _icon_helmet() -> str:
    """Helmet icon — dome shape using path."""
    return (
        '<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">'
        '<path d="M6,28 L6,16 Q6,4 20,4 Q34,4 34,16 L34,28 Z" fill="none" '
        'stroke="var(--gg-color-primary-brown)" stroke-width="2.5"/>'
        '<line x1="6" y1="28" x2="34" y2="28" '
        'stroke="var(--gg-color-gold)" stroke-width="2"/>'
        '</svg>'
    )


def _icon_repair() -> str:
    """Repair kit icon — wrench/cross shape."""
    return (
        '<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">'
        '<rect x="17" y="4" width="6" height="32" fill="none" '
        'stroke="var(--gg-color-primary-brown)" stroke-width="2.5"/>'
        '<rect x="4" y="17" width="32" height="6" fill="none" '
        'stroke="var(--gg-color-primary-brown)" stroke-width="2.5"/>'
        '</svg>'
    )


def _icon_hydration() -> str:
    """Hydration icon — bottle shape."""
    return (
        '<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">'
        '<rect x="12" y="2" width="16" height="6" fill="none" '
        'stroke="var(--gg-color-primary-brown)" stroke-width="2"/>'
        '<path d="M10,8 L10,36 L30,36 L30,8 Z" fill="none" '
        'stroke="var(--gg-color-primary-brown)" stroke-width="2.5"/>'
        '<line x1="10" y1="20" x2="30" y2="20" '
        'stroke="var(--gg-color-teal)" stroke-width="2"/>'
        '</svg>'
    )


_GEAR_ICONS = {
    "frame": _icon_frame,
    "tires": _icon_tire,
    "helmet": _icon_helmet,
    "repair": _icon_repair,
    "hydration": _icon_hydration,
}


# ══════════════════════════════════════════════════════════════
# Phase 2: Card/Grid Layouts (HTML/CSS — 6 renderers)
# ══════════════════════════════════════════════════════════════


def render_gear_grid(block: dict) -> str:
    """5-item gear essentials grid with inline SVG icons."""
    items = [
        ("frame", "Bike Frame", "Your foundation. Gravel-specific geometry, tire clearance, and mounting points."),
        ("tires", "Tires", "The single biggest performance variable. 40-50mm for most courses."),
        ("helmet", "Helmet", "Non-negotiable safety. MIPS preferred. Ventilation matters for long days."),
        ("repair", "Repair Kit", "Tubes/plugs, multi-tool, CO2. Practice repairs before race day."),
        ("hydration", "Hydration", "Bottles or pack. Know your course's water availability."),
    ]

    cards = []
    for key, title, desc in items:
        icon_fn = _GEAR_ICONS.get(key, _icon_frame)
        cards.append(
            f'<div class="gg-infographic-card">'
            f'<div class="gg-infographic-card-icon">{icon_fn()}</div>'
            f'<div class="gg-infographic-card-title">{_esc(title)}</div>'
            f'<div class="gg-infographic-card-desc">{_esc(desc)}</div>'
            f'</div>'
        )

    inner = f'<div class="gg-infographic-gear-grid">{"".join(cards)}</div>'
    return _figure_wrap(inner, block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_rider_categories(block: dict) -> str:
    """4-column rider category grid (Ayahuasca/Finisher/Competitor/Podium)."""
    riders = [
        {
            "name": "Ayahuasca",
            "hours": "3-5 hrs/wk",
            "ftp_range": "100-160W",
            "ftp_pct": 25,
            "goal": "Finish upright",
            "reality": "Survival mode",
            "tier": "T4",
        },
        {
            "name": "Finisher",
            "hours": "5-8 hrs/wk",
            "ftp_range": "160-220W",
            "ftp_pct": 50,
            "goal": "Finish strong",
            "reality": "Solid mid-pack",
            "tier": "T3-T4",
        },
        {
            "name": "Competitor",
            "hours": "8-12 hrs/wk",
            "ftp_range": "220-280W",
            "ftp_pct": 75,
            "goal": "Top 25%",
            "reality": "Age group podium",
            "tier": "T2-T3",
        },
        {
            "name": "Podium",
            "hours": "12-20 hrs/wk",
            "ftp_range": "280-400W",
            "ftp_pct": 100,
            "goal": "Win or podium",
            "reality": "Elite-level prep",
            "tier": "T1",
        },
    ]

    cards = []
    for r in riders:
        bar_w = r["ftp_pct"]
        cards.append(
            f'<div class="gg-infographic-rider-card">'
            f'<div class="gg-infographic-rider-name">{_esc(r["name"])}</div>'
            f'<div class="gg-infographic-rider-hours">{_esc(r["hours"])}</div>'
            f'<div class="gg-infographic-rider-bar-wrap">'
            f'<div class="gg-infographic-rider-bar" style="width:{bar_w}%"></div>'
            f'</div>'
            f'<div class="gg-infographic-rider-ftp">{_esc(r["ftp_range"])}</div>'
            f'<div class="gg-infographic-rider-meta">'
            f'<span>Goal: {_esc(r["goal"])}</span>'
            f'<span>Reality: {_esc(r["reality"])}</span>'
            f'<span>Races: {_esc(r["tier"])}</span>'
            f'</div>'
            f'</div>'
        )

    inner = f'<div class="gg-infographic-rider-grid">{"".join(cards)}</div>'
    return _figure_wrap(inner, block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_race_week_countdown(block: dict) -> str:
    """7-column race week countdown grid (Mon-Sun)."""
    days = [
        ("MON", "Easy spin", "30-45 min Z2. Legs loose, nothing hard.", False),
        ("TUE", "Openers", "3x1 min Z4 surges in a Z2 ride. Wake up legs.", False),
        ("WED", "Rest day", "Off the bike. Walk, stretch, hydrate.", False),
        ("THU", "Shakeout", "20-30 min easy spin. Bike check.", False),
        ("FRI", "Rest + prep", "Lay out gear. Charge devices. Sleep early.", False),
        ("SAT", "Travel day", "Drive to venue. Packet pickup. Course preview.", False),
        ("SUN", "RACE DAY", "Execute the plan. Trust the training.", True),
    ]

    cards = []
    for abbr, task, note, is_race_day in days:
        cls = "gg-infographic-day-card"
        if is_race_day:
            cls += " gg-infographic-day-card--race"
        cards.append(
            f'<div class="{cls}">'
            f'<div class="gg-infographic-day-abbr">{_esc(abbr)}</div>'
            f'<div class="gg-infographic-day-task">{_esc(task)}</div>'
            f'<div class="gg-infographic-day-note">{_esc(note)}</div>'
            f'</div>'
        )

    inner = f'<div class="gg-infographic-week-grid">{"".join(cards)}</div>'
    return _figure_wrap(inner, block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_traffic_light(block: dict) -> str:
    """Green/Yellow/Red autoregulation system — 3 stacked rows."""
    signals = [
        {
            "color": "var(--gg-color-teal)",
            "label": "GREEN",
            "criteria": "Slept 7+ hrs, resting HR normal, motivation high, no soreness",
            "action": "Execute as planned. Full intensity.",
        },
        {
            "color": "var(--gg-color-gold)",
            "label": "YELLOW",
            "criteria": "Slept 5-7 hrs, slightly elevated HR, moderate fatigue",
            "action": "Reduce intensity 5-10%. Shorten intervals. Monitor feel.",
        },
        {
            "color": "var(--gg-color-error)",
            "label": "RED",
            "criteria": "Slept <5 hrs, elevated HR, illness symptoms, sharp pain",
            "action": "Rest or Z1 only. Recovery is training. Come back tomorrow.",
        },
    ]

    rows = []
    for s in signals:
        rows.append(
            f'<div class="gg-infographic-signal-row">'
            f'<div class="gg-infographic-signal-indicator" style="background:{s["color"]}"></div>'
            f'<div class="gg-infographic-signal-body">'
            f'<div class="gg-infographic-signal-label">{_esc(s["label"])}</div>'
            f'<div class="gg-infographic-signal-criteria">{_esc(s["criteria"])}</div>'
            f'<div class="gg-infographic-signal-action">{_esc(s["action"])}</div>'
            f'</div>'
            f'</div>'
        )

    inner = f'<div class="gg-infographic-traffic-light">{"".join(rows)}</div>'
    return _figure_wrap(inner, block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_three_acts(block: dict) -> str:
    """Three-act race structure: Restraint / Resilience / Resolve."""
    acts = [
        {
            "num": "ACT 1",
            "title": "Restraint",
            "range": "0-40%",
            "strategies": [
                "Hold 10% below target power",
                "Ignore early surges",
                "Settle into rhythm",
                "Bank nothing — save everything",
            ],
        },
        {
            "num": "ACT 2",
            "title": "Resilience",
            "range": "40-75%",
            "strategies": [
                "Commit to target effort",
                "Process-focus: next aid, next climb",
                "Fuel relentlessly on schedule",
                "Acknowledge pain, don't chase it",
            ],
        },
        {
            "num": "ACT 3",
            "title": "Resolve",
            "range": "75-100%",
            "strategies": [
                "Unlock remaining reserves",
                "Shorten mental horizon: 10 min at a time",
                "Draw on training memories",
                "This is what you came for",
            ],
        },
    ]

    panels = []
    for act in acts:
        items = "".join(f"<li>{_esc(s)}</li>" for s in act["strategies"])
        panels.append(
            f'<div class="gg-infographic-act-panel">'
            f'<div class="gg-infographic-act-num">{_esc(act["num"])}</div>'
            f'<div class="gg-infographic-act-title">{_esc(act["title"])}</div>'
            f'<div class="gg-infographic-act-range">{_esc(act["range"])}</div>'
            f'<ul class="gg-infographic-act-list">{items}</ul>'
            f'</div>'
        )

    inner = f'<div class="gg-infographic-three-acts">{"".join(panels)}</div>'
    return _figure_wrap(inner, block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_bonk_math(block: dict) -> str:
    """Bonk math equation + gel rectangle grid."""
    # Big equation typography
    equation = (
        '<div class="gg-infographic-bonk-equation">'
        '<span class="gg-infographic-bonk-num">8</span>'
        '<span class="gg-infographic-bonk-op">&times;</span>'
        '<span class="gg-infographic-bonk-num">75g</span>'
        '<span class="gg-infographic-bonk-op">=</span>'
        '<span class="gg-infographic-bonk-total">600g</span>'
        '</div>'
        '<div class="gg-infographic-bonk-subtitle">8 hours &times; 75g carbs/hr = 600g total carbohydrate</div>'
    )

    # 24 gel rectangles in a 12x2 grid
    gels = ""
    for i in range(24):
        gels += '<div class="gg-infographic-bonk-gel"></div>'

    gel_grid = (
        f'<div class="gg-infographic-bonk-grid">{gels}</div>'
        f'<div class="gg-infographic-bonk-label">= 24 gels (or equivalent)</div>'
    )

    inner = f'<div class="gg-infographic-bonk-math">{equation}{gel_grid}</div>'
    return _figure_wrap(inner, block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


# ══════════════════════════════════════════════════════════════
# Phase 3: SVG Charts (10 renderers)
# ══════════════════════════════════════════════════════════════


def render_zone_spectrum(block: dict) -> str:
    """7 horizontal bars Z1-Z7 with zone labels and percentages."""
    zones = [
        ("Z1 Active Recovery", 55, "var(--gg-color-light-teal)"),
        ("Z2 Endurance", 75, "var(--gg-color-teal)"),
        ("Z3 Tempo", 90, "var(--gg-color-gold)"),
        ("Z4 Threshold", 105, "var(--gg-color-light-gold)"),
        ("Z5 VO2max", 120, "var(--gg-color-warm-brown)"),
        ("Z6 Anaerobic", 150, "var(--gg-color-secondary-brown)"),
        ("Z7 Neuromuscular", 200, "var(--gg-color-primary-brown)"),
    ]

    vb_w, vb_h = 1200, 600
    bar_h = 52
    gap = 22
    left_margin = 320
    right_margin = 100
    top_margin = 40
    max_pct = 200  # Z7 is the max
    bar_area = vb_w - left_margin - right_margin

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    for i, (label, pct, color) in enumerate(zones):
        y = top_margin + i * (bar_h + gap)
        bar_w = (pct / max_pct) * bar_area

        # Zone label
        svg.append(_svg_text(
            left_margin - 16, y + bar_h / 2 + 5, label,
            font_size=16, fill="var(--gg-color-primary-brown)",
            anchor="end", weight="700",
            family="var(--gg-font-data)"
        ))
        # Bar
        svg.append(_svg_rect(left_margin, y, bar_w, bar_h, fill=color))
        # Percentage label
        svg.append(_svg_text(
            left_margin + bar_w + 12, y + bar_h / 2 + 5,
            f"{pct}%",
            font_size=15, fill="var(--gg-color-secondary-brown)",
            weight="700", family="var(--gg-font-data)"
        ))

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_hierarchy_pyramid(block: dict) -> str:
    """5-layer performance hierarchy pyramid (trapezoids widening bottom-up)."""
    layers = [
        ("Equipment", "0.5%", 0.15),
        ("Bike Handling", "1.5%", 0.30),
        ("Nutrition", "8%", 0.50),
        ("Pacing", "20%", 0.75),
        ("Fitness", "70%", 1.0),
    ]

    vb_w, vb_h = 1200, 700
    top_margin = 40
    layer_h = 110
    gap = 12
    max_width = 1000
    center_x = vb_w / 2

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    for i, (label, pct, width_frac) in enumerate(layers):
        y = top_margin + i * (layer_h + gap)
        w = max_width * width_frac
        x = center_x - w / 2

        # Gradient fill from light to primary brown based on layer
        fills = [
            "var(--gg-color-tan)",
            "var(--gg-color-sand)",
            "var(--gg-color-warm-brown)",
            "var(--gg-color-secondary-brown)",
            "var(--gg-color-primary-brown)",
        ]
        text_fills = [
            "var(--gg-color-primary-brown)",
            "var(--gg-color-primary-brown)",
            "var(--gg-color-warm-paper)",
            "var(--gg-color-warm-paper)",
            "var(--gg-color-warm-paper)",
        ]

        svg.append(_svg_rect(x, y, w, layer_h, fill=fills[i],
                             stroke="var(--gg-color-near-black)", stroke_width=2))
        # Label
        svg.append(_svg_text(
            center_x, y + layer_h / 2 - 8, label,
            font_size=22, fill=text_fills[i],
            anchor="middle", weight="700",
            family="var(--gg-font-editorial)"
        ))
        # Percentage
        svg.append(_svg_text(
            center_x, y + layer_h / 2 + 20, pct,
            font_size=18, fill=text_fills[i],
            anchor="middle", weight="400",
            family="var(--gg-font-data)"
        ))

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_tier_distribution(block: dict) -> str:
    """Stacked horizontal bar showing T1-T4 distribution + detail rows."""
    tiers = [
        ("T1", 25, 8, "var(--gg-color-primary-brown)"),
        ("T2", 73, 22, "var(--gg-color-secondary-brown)"),
        ("T3", 154, 47, "var(--gg-color-tier-3)"),
        ("T4", 76, 23, "var(--gg-color-tier-4)"),
    ]

    vb_w, vb_h = 1200, 400
    bar_y = 60
    bar_h = 80
    bar_margin = 60
    bar_width = vb_w - 2 * bar_margin
    total = sum(t[1] for t in tiers)

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Title
    svg.append(_svg_text(
        vb_w / 2, 35, "328 Gravel Races Across 4 Tiers",
        font_size=22, fill="var(--gg-color-primary-brown)",
        anchor="middle", weight="700",
        family="var(--gg-font-editorial)"
    ))

    # Stacked bar
    x_offset = bar_margin
    for label, count, pct, color in tiers:
        seg_w = (count / total) * bar_width
        svg.append(_svg_rect(x_offset, bar_y, seg_w, bar_h, fill=color,
                             stroke="var(--gg-color-near-black)", stroke_width=2))
        # Label inside bar
        if seg_w > 60:
            svg.append(_svg_text(
                x_offset + seg_w / 2, bar_y + bar_h / 2 + 6, label,
                font_size=20, fill="var(--gg-color-warm-paper)",
                anchor="middle", weight="700",
                family="var(--gg-font-data)"
            ))
        x_offset += seg_w

    # Detail rows below bar
    detail_y = bar_y + bar_h + 50
    x_offset = bar_margin
    for label, count, pct, color in tiers:
        seg_w = (count / total) * bar_width

        # Color swatch
        svg.append(_svg_rect(x_offset, detail_y, 20, 20, fill=color,
                             stroke="var(--gg-color-near-black)", stroke_width=1))
        # Label + count + pct
        svg.append(_svg_text(
            x_offset + 30, detail_y + 15,
            f"{label}: {count} races ({pct}%)",
            font_size=16, fill="var(--gg-color-primary-brown)",
            weight="600", family="var(--gg-font-data)"
        ))

        detail_y += 40

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_training_phases(block: dict) -> str:
    """12-week training periodization: 3 phase boxes + volume/intensity Bezier curves."""
    vb_w, vb_h = 1600, 500
    margin_l, margin_r = 80, 60
    chart_top = 80
    chart_bot = 420
    chart_w = vb_w - margin_l - margin_r
    chart_h = chart_bot - chart_top

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Phase boxes (background bands)
    phases = [
        ("BASE", 0, 5, "color-mix(in srgb, var(--gg-color-teal) 12%, transparent)"),
        ("BUILD", 5, 9, "color-mix(in srgb, var(--gg-color-gold) 12%, transparent)"),
        ("PEAK / TAPER", 9, 12, "color-mix(in srgb, var(--gg-color-primary-brown) 12%, transparent)"),
    ]

    week_w = chart_w / 12
    for label, start, end, fill in phases:
        x = margin_l + start * week_w
        w = (end - start) * week_w
        svg.append(_svg_rect(x, chart_top, w, chart_h, fill=fill,
                             stroke="var(--gg-color-tan)", stroke_width=1))
        svg.append(_svg_text(
            x + w / 2, chart_top + 30, label,
            font_size=18, fill="var(--gg-color-primary-brown)",
            anchor="middle", weight="700",
            family="var(--gg-font-editorial)"
        ))

    # Week labels along bottom
    for wk in range(12):
        x = margin_l + (wk + 0.5) * week_w
        svg.append(_svg_text(
            x, chart_bot + 30, f"W{wk + 1}",
            font_size=12, fill="var(--gg-color-secondary-brown)",
            anchor="middle", family="var(--gg-font-data)"
        ))

    # Volume curve (builds in Base, peaks mid-Build, tapers)
    vol_pts = [
        (0, 0.30), (1, 0.40), (2, 0.55), (3, 0.65), (4, 0.75),
        (5, 0.85), (6, 0.90), (7, 0.80), (8, 0.65),
        (9, 0.50), (10, 0.35), (11, 0.25),
    ]
    vol_points = [
        (margin_l + (wk + 0.5) * week_w, chart_bot - v * chart_h)
        for wk, v in vol_pts
    ]
    svg.append(_svg_path(
        _cubic_bezier_path(vol_points),
        stroke="var(--gg-color-teal)", stroke_width=3,
        extra='stroke-linecap="round"'
    ))

    # Intensity curve (low in Base, ramps in Build, peaks early Peak)
    int_pts = [
        (0, 0.15), (1, 0.18), (2, 0.20), (3, 0.25), (4, 0.30),
        (5, 0.45), (6, 0.60), (7, 0.75), (8, 0.85),
        (9, 0.80), (10, 0.50), (11, 0.30),
    ]
    int_points = [
        (margin_l + (wk + 0.5) * week_w, chart_bot - v * chart_h)
        for wk, v in int_pts
    ]
    svg.append(_svg_path(
        _cubic_bezier_path(int_points),
        stroke="var(--gg-color-gold)", stroke_width=3,
        extra='stroke-linecap="round" stroke-dasharray="8 4"'
    ))

    # Legend
    leg_y = chart_bot + 60
    svg.append(_svg_line(margin_l, leg_y, margin_l + 30, leg_y,
                         stroke="var(--gg-color-teal)", stroke_width=3))
    svg.append(_svg_text(
        margin_l + 40, leg_y + 5, "Volume",
        font_size=14, fill="var(--gg-color-primary-brown)",
        family="var(--gg-font-data)"
    ))
    svg.append(_svg_line(margin_l + 140, leg_y, margin_l + 170, leg_y,
                         stroke="var(--gg-color-gold)", stroke_width=3,
                         extra='stroke-dasharray="8 4"'))
    svg.append(_svg_text(
        margin_l + 180, leg_y + 5, "Intensity",
        font_size=14, fill="var(--gg-color-primary-brown)",
        family="var(--gg-font-data)"
    ))

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "full-width"), block.get("asset_id", ""), block.get("alt", ""))


def render_execution_gap(block: dict) -> str:
    """Side-by-side comparison: fading intervals vs consistent execution."""
    vb_w, vb_h = 1200, 600
    mid_x = vb_w / 2
    margin = 40
    bar_w = 70
    gap = 20

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Divider line
    svg.append(_svg_line(mid_x, 20, mid_x, vb_h - 20,
                         stroke="var(--gg-color-tan)", stroke_width=2,
                         extra='stroke-dasharray="6 4"'))

    # Left side: BAD — fading intervals
    svg.append(_svg_text(
        mid_x / 2, 45, "CHASING WATTS",
        font_size=20, fill="var(--gg-color-error)",
        anchor="middle", weight="700",
        family="var(--gg-font-editorial)"
    ))

    bad_bars = [0.95, 0.78, 0.55]  # Fading power
    target_h = 350
    base_y = 480
    bad_x_start = margin + 80

    # Target line (left)
    target_y = base_y - 0.85 * target_h
    svg.append(_svg_line(bad_x_start - 10, target_y,
                         bad_x_start + len(bad_bars) * (bar_w + gap), target_y,
                         stroke="var(--gg-color-gold)", stroke_width=2,
                         extra='stroke-dasharray="6 3"'))
    svg.append(_svg_text(
        bad_x_start - 16, target_y - 6, "TARGET",
        font_size=10, fill="var(--gg-color-gold)",
        anchor="end", weight="700",
        family="var(--gg-font-data)"
    ))

    # Fading bars use color-mix to blend error color with warm-paper (no opacity)
    bad_fills = [
        "var(--gg-color-error)",
        "color-mix(in srgb, var(--gg-color-error) 75%, var(--gg-color-warm-paper))",
        "color-mix(in srgb, var(--gg-color-error) 50%, var(--gg-color-warm-paper))",
    ]
    for i, pct in enumerate(bad_bars):
        x = bad_x_start + i * (bar_w + gap)
        h = pct * target_h
        y = base_y - h
        svg.append(_svg_rect(x, y, bar_w, h,
                             fill=bad_fills[i],
                             stroke="var(--gg-color-near-black)", stroke_width=2))
        svg.append(_svg_text(
            x + bar_w / 2, base_y + 25, f"Int {i + 1}",
            font_size=13, fill="var(--gg-color-secondary-brown)",
            anchor="middle", family="var(--gg-font-data)"
        ))
        svg.append(_svg_text(
            x + bar_w / 2, y - 10, f"{int(pct * 100)}%",
            font_size=14, fill="var(--gg-color-primary-brown)",
            anchor="middle", weight="700",
            family="var(--gg-font-data)"
        ))

    # Right side: GOOD — consistent execution
    svg.append(_svg_text(
        mid_x + (vb_w - mid_x) / 2, 45, "CONSISTENT EXECUTION",
        font_size=20, fill="var(--gg-color-teal)",
        anchor="middle", weight="700",
        family="var(--gg-font-editorial)"
    ))

    good_bars = [0.84, 0.83, 0.85, 0.84]
    good_x_start = mid_x + 80

    # Target line (right)
    svg.append(_svg_line(good_x_start - 10, target_y,
                         good_x_start + len(good_bars) * (bar_w + gap), target_y,
                         stroke="var(--gg-color-gold)", stroke_width=2,
                         extra='stroke-dasharray="6 3"'))

    for i, pct in enumerate(good_bars):
        x = good_x_start + i * (bar_w + gap)
        h = pct * target_h
        y = base_y - h
        svg.append(_svg_rect(x, y, bar_w, h,
                             fill="var(--gg-color-teal)",
                             stroke="var(--gg-color-near-black)", stroke_width=2))
        svg.append(_svg_text(
            x + bar_w / 2, base_y + 25, f"Int {i + 1}",
            font_size=13, fill="var(--gg-color-secondary-brown)",
            anchor="middle", family="var(--gg-font-data)"
        ))
        svg.append(_svg_text(
            x + bar_w / 2, y - 10, f"{int(pct * 100)}%",
            font_size=14, fill="var(--gg-color-primary-brown)",
            anchor="middle", weight="700",
            family="var(--gg-font-data)"
        ))

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_fueling_timeline(block: dict) -> str:
    """Horizontal timeline showing race-day fueling milestones."""
    vb_w, vb_h = 1200, 500
    margin_l, margin_r = 80, 80
    timeline_y = 200
    bar_h = 12

    markers = [
        ("T-3 hrs", 0.0, "Pre-race meal", "600-800 cal, low fiber, familiar foods"),
        ("T-30 min", 0.20, "Top off", "Gel or drink, 30-50g carbs"),
        ("Start", 0.30, "Race begins", "Start fueling at min 15-20, not later"),
        ("Every 20 min", 0.55, "Steady intake", "75g carbs/hr from gels, chews, drink mix"),
        ("Ongoing", 0.85, "Hydration", "500-750ml/hr, sodium 500-1000mg/hr"),
    ]

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    line_w = vb_w - margin_l - margin_r

    # Timeline bar
    svg.append(_svg_rect(margin_l, timeline_y, line_w, bar_h,
                         fill="var(--gg-color-tan)"))

    for i, (time_label, pos, title, detail) in enumerate(markers):
        x = margin_l + pos * line_w

        # Marker tick
        svg.append(_svg_rect(x - 3, timeline_y - 8, 6, bar_h + 16,
                             fill="var(--gg-color-primary-brown)"))

        # Alternate callout boxes above/below
        if i % 2 == 0:
            # Above
            box_y = timeline_y - 120
            svg.append(_svg_line(x, timeline_y - 8, x, box_y + 70,
                                 stroke="var(--gg-color-tan)", stroke_width=1))
        else:
            # Below
            box_y = timeline_y + bar_h + 40
            svg.append(_svg_line(x, timeline_y + bar_h + 8, x, box_y,
                                 stroke="var(--gg-color-tan)", stroke_width=1))

        # Time label
        svg.append(_svg_text(
            x, box_y, time_label,
            font_size=14, fill="var(--gg-color-gold)",
            anchor="middle", weight="700",
            family="var(--gg-font-data)"
        ))
        # Title
        svg.append(_svg_text(
            x, box_y + 22, title,
            font_size=15, fill="var(--gg-color-primary-brown)",
            anchor="middle", weight="700",
            family="var(--gg-font-editorial)"
        ))
        # Detail
        svg.append(_svg_text(
            x, box_y + 42, detail,
            font_size=12, fill="var(--gg-color-secondary-brown)",
            anchor="middle", family="var(--gg-font-data)"
        ))

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def _load_unbound_rating() -> dict:
    """Load and cache Unbound 200 scoring data. Called once, cached at module level."""
    if "unbound" not in _SCORING_CACHE:
        ub_path = RACE_DATA_DIR / "unbound-200.json"
        if ub_path.exists():
            ub_data = json.loads(ub_path.read_text(encoding="utf-8"))
            _SCORING_CACHE["unbound"] = ub_data["race"]["gravel_god_rating"]
        else:
            _SCORING_CACHE["unbound"] = {
                "logistics": 4, "length": 5, "technicality": 3, "elevation": 3,
                "climate": 5, "altitude": 1, "adventure": 5, "prestige": 5,
                "race_quality": 5, "experience": 5, "community": 5,
                "field_depth": 5, "value": 3, "expenses": 2,
            }
    return _SCORING_CACHE["unbound"]


def render_scoring_dimensions(block: dict) -> str:
    """14 horizontal bars (7+7 in 2 columns) showing scoring dimensions.
    Uses cached Unbound 200 data for example scores."""
    rating = _load_unbound_rating()

    dimensions = [
        ("Logistics", rating.get("logistics", 0)),
        ("Length", rating.get("length", 0)),
        ("Technicality", rating.get("technicality", 0)),
        ("Elevation", rating.get("elevation", 0)),
        ("Climate", rating.get("climate", 0)),
        ("Altitude", rating.get("altitude", 0)),
        ("Adventure", rating.get("adventure", 0)),
        ("Prestige", rating.get("prestige", 0)),
        ("Race Quality", rating.get("race_quality", 0)),
        ("Experience", rating.get("experience", 0)),
        ("Community", rating.get("community", 0)),
        ("Field Depth", rating.get("field_depth", 0)),
        ("Value", rating.get("value", 0)),
        ("Expenses", rating.get("expenses", 0)),
    ]

    vb_w, vb_h = 1200, 800
    col_w = 520
    bar_h = 28
    gap = 18
    max_bar_w = 250
    left_col_x = 60
    right_col_x = vb_w / 2 + 40
    top_margin = 60

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Title
    svg.append(_svg_text(
        vb_w / 2, 35, "Unbound Gravel 200 — Scoring Dimensions",
        font_size=22, fill="var(--gg-color-primary-brown)",
        anchor="middle", weight="700",
        family="var(--gg-font-editorial)"
    ))

    for i, (label, score) in enumerate(dimensions):
        col = 0 if i < 7 else 1
        row = i if col == 0 else i - 7
        x_base = left_col_x if col == 0 else right_col_x
        y = top_margin + row * (bar_h + gap)
        bar_w = (score / 5) * max_bar_w

        # Choose color based on score
        if score >= 4:
            fill = "var(--gg-color-teal)"
        elif score >= 3:
            fill = "var(--gg-color-gold)"
        else:
            fill = "var(--gg-color-secondary-brown)"

        # Label
        svg.append(_svg_text(
            x_base, y + bar_h / 2 + 5, label,
            font_size=14, fill="var(--gg-color-primary-brown)",
            weight="600", family="var(--gg-font-data)"
        ))
        # Bar
        bar_x = x_base + 150
        svg.append(_svg_rect(bar_x, y, bar_w, bar_h, fill=fill,
                             stroke="var(--gg-color-near-black)", stroke_width=1))
        # Score label
        svg.append(_svg_text(
            bar_x + bar_w + 12, y + bar_h / 2 + 5, f"{score}/5",
            font_size=14, fill="var(--gg-color-primary-brown)",
            weight="700", family="var(--gg-font-data)"
        ))

    # Divider line between columns
    svg.append(_svg_line(vb_w / 2, top_margin - 10, vb_w / 2, top_margin + 7 * (bar_h + gap) - gap,
                         stroke="var(--gg-color-tan)", stroke_width=1))

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_supercompensation(block: dict) -> str:
    """Supercompensation curve: stress → fatigue → recovery → adaptation overshoot."""
    vb_w, vb_h = 1200, 600
    margin_l, margin_r = 80, 60
    chart_top = 60
    chart_bot = 500
    chart_w = vb_w - margin_l - margin_r

    # Baseline
    baseline_y = chart_bot - 200

    # Curve points: (x_frac, y_offset from baseline)
    # Negative = below baseline (fatigue), positive = above (supercompensation)
    curve_pts = [
        (0.00, 0),      # start at baseline
        (0.05, 5),      # slight rise during training stimulus
        (0.10, -10),    # training stress begins
        (0.15, -80),    # deep fatigue
        (0.20, -120),   # nadir
        (0.25, -100),   # recovery begins
        (0.30, -60),
        (0.35, -20),
        (0.40, 0),      # back to baseline
        (0.45, 30),     # supercompensation begins
        (0.50, 55),
        (0.55, 70),     # peak supercompensation
        (0.60, 65),
        (0.65, 50),
        (0.70, 30),     # detraining begins
        (0.75, 15),
        (0.80, 5),
        (0.85, 0),      # return to baseline
        (0.90, -5),
        (0.95, -8),
        (1.00, -10),
    ]

    points = [
        (margin_l + frac * chart_w, baseline_y - offset)
        for frac, offset in curve_pts
    ]

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Baseline
    svg.append(_svg_line(margin_l, baseline_y, margin_l + chart_w, baseline_y,
                         stroke="var(--gg-color-tan)", stroke_width=2,
                         extra='stroke-dasharray="8 4"'))
    svg.append(_svg_text(
        margin_l - 10, baseline_y + 5, "Baseline",
        font_size=12, fill="var(--gg-color-secondary-brown)",
        anchor="end", family="var(--gg-font-data)"
    ))

    # Main curve
    svg.append(_svg_path(
        _cubic_bezier_path(points),
        stroke="var(--gg-color-primary-brown)", stroke_width=3,
        extra='stroke-linecap="round"'
    ))

    # Phase labels
    phase_labels = [
        (0.12, -140, "Training\nStress", "var(--gg-color-error)"),
        (0.22, -150, "Fatigue", "var(--gg-color-error)"),
        (0.35, 10, "Recovery", "var(--gg-color-gold)"),
        (0.55, 95, "Supercompensation", "var(--gg-color-teal)"),
        (0.80, 25, "Detraining", "var(--gg-color-secondary-brown)"),
    ]

    for frac, y_off, label, color in phase_labels:
        x = margin_l + frac * chart_w
        y = baseline_y - y_off
        # Split multi-line labels
        lines = label.split("\n")
        for j, line in enumerate(lines):
            svg.append(_svg_text(
                x, y + j * 18, line,
                font_size=14, fill=color,
                anchor="middle", weight="700",
                family="var(--gg-font-editorial)"
            ))

    # Insight box at bottom
    svg.append(_svg_rect(margin_l, chart_bot + 20, chart_w, 50,
                         fill="color-mix(in srgb, var(--gg-color-gold) 8%, transparent)",
                         stroke="var(--gg-color-gold)", stroke_width=2))
    svg.append(_svg_text(
        vb_w / 2, chart_bot + 50,
        "Train hard enough to trigger adaptation, then rest long enough to realize it.",
        font_size=14, fill="var(--gg-color-primary-brown)",
        anchor="middle", weight="600",
        family="var(--gg-font-editorial)"
    ))

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


def render_pmc_chart(block: dict) -> str:
    """Performance Management Chart: 3 Bezier curves (CTL/ATL/TSB) over 12 weeks."""
    vb_w, vb_h = 1600, 600
    margin_l, margin_r = 80, 60
    chart_top = 60
    chart_bot = 480
    chart_w = vb_w - margin_l - margin_r
    chart_h = chart_bot - chart_top

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Y-axis labels
    for val, label in [(0, "0"), (50, "50"), (100, "100")]:
        y = chart_bot - (val / 100) * chart_h
        svg.append(_svg_text(
            margin_l - 10, y + 4, label,
            font_size=12, fill="var(--gg-color-secondary-brown)",
            anchor="end", family="var(--gg-font-data)"
        ))
        svg.append(_svg_line(margin_l, y, margin_l + chart_w, y,
                             stroke="var(--gg-color-tan)", stroke_width=1,
                             extra='stroke-dasharray="4 4"'))

    # Zero line for TSB
    zero_y = chart_bot - (50 / 100) * chart_h  # TSB zero = visual midpoint

    # CTL (Fitness) — steady ramp up, slight taper
    ctl_vals = [25, 30, 36, 43, 50, 57, 63, 70, 75, 78, 72, 65]
    ctl_points = [
        (margin_l + (i + 0.5) * (chart_w / 12), chart_bot - (v / 100) * chart_h)
        for i, v in enumerate(ctl_vals)
    ]
    svg.append(_svg_path(
        _cubic_bezier_path(ctl_points),
        stroke="var(--gg-color-teal)", stroke_width=3,
        extra='stroke-linecap="round"'
    ))

    # ATL (Fatigue) — spiky, follows training load
    atl_vals = [30, 45, 55, 50, 65, 70, 60, 80, 75, 50, 35, 25]
    atl_points = [
        (margin_l + (i + 0.5) * (chart_w / 12), chart_bot - (v / 100) * chart_h)
        for i, v in enumerate(atl_vals)
    ]
    svg.append(_svg_path(
        _cubic_bezier_path(atl_points),
        stroke="var(--gg-color-error)", stroke_width=3,
        extra='stroke-linecap="round" stroke-dasharray="8 4"'
    ))

    # TSB (Form) — CTL - ATL, shifted to visual range
    tsb_vals = [-5, -15, -19, -7, -15, -13, 3, -10, 0, 28, 37, 40]
    tsb_points = [
        (margin_l + (i + 0.5) * (chart_w / 12), zero_y - (v / 50) * (chart_h / 2))
        for i, v in enumerate(tsb_vals)
    ]
    svg.append(_svg_path(
        _cubic_bezier_path(tsb_points),
        stroke="var(--gg-color-gold)", stroke_width=3,
        extra='stroke-linecap="round"'
    ))

    # Week labels
    for wk in range(12):
        x = margin_l + (wk + 0.5) * (chart_w / 12)
        svg.append(_svg_text(
            x, chart_bot + 25, f"W{wk + 1}",
            font_size=12, fill="var(--gg-color-secondary-brown)",
            anchor="middle", family="var(--gg-font-data)"
        ))

    # Legend
    leg_y = chart_bot + 55
    items = [
        ("var(--gg-color-teal)", "CTL (Fitness)", ""),
        ("var(--gg-color-error)", "ATL (Fatigue)", 'stroke-dasharray="8 4"'),
        ("var(--gg-color-gold)", "TSB (Form)", ""),
    ]
    leg_x = margin_l
    for color, label, dash in items:
        svg.append(_svg_line(leg_x, leg_y, leg_x + 30, leg_y,
                             stroke=color, stroke_width=3,
                             extra=dash))
        svg.append(_svg_text(
            leg_x + 40, leg_y + 5, label,
            font_size=14, fill="var(--gg-color-primary-brown)",
            family="var(--gg-font-data)"
        ))
        leg_x += 220

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "full-width"), block.get("asset_id", ""), block.get("alt", ""))


def render_psych_phases(block: dict) -> str:
    """Psychological phases mood curve with 5 background bands + Bezier mood line."""
    vb_w, vb_h = 1200, 600
    margin_l, margin_r = 60, 60
    chart_top = 60
    chart_bot = 500
    chart_w = vb_w - margin_l - margin_r
    chart_h = chart_bot - chart_top

    # 5 psychological phases with background bands
    phases = [
        ("Honeymoon", 0.0, 0.20, "color-mix(in srgb, var(--gg-color-teal) 10%, transparent)"),
        ("Shattering", 0.20, 0.40, "color-mix(in srgb, var(--gg-color-gold) 10%, transparent)"),
        ("Dark Patch", 0.40, 0.60, "color-mix(in srgb, var(--gg-color-error) 10%, transparent)"),
        ("Second Wind", 0.60, 0.80, "color-mix(in srgb, var(--gg-color-teal) 10%, transparent)"),
        ("Final Push", 0.80, 1.00, "color-mix(in srgb, var(--gg-color-gold) 10%, transparent)"),
    ]

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Background bands
    for label, start, end, fill in phases:
        x = margin_l + start * chart_w
        w = (end - start) * chart_w
        svg.append(_svg_rect(x, chart_top, w, chart_h, fill=fill))
        svg.append(_svg_text(
            x + w / 2, chart_top + 25, label,
            font_size=15, fill="var(--gg-color-primary-brown)",
            anchor="middle", weight="700",
            family="var(--gg-font-editorial)"
        ))

    # Mood curve points (0=worst, 1=best)
    mood_pts = [
        (0.00, 0.70),   # start excited
        (0.05, 0.85),   # honeymoon peak
        (0.10, 0.90),   # high energy
        (0.15, 0.80),   # settling
        (0.20, 0.65),   # reality hits
        (0.25, 0.50),   # shattering begins
        (0.30, 0.35),
        (0.35, 0.25),
        (0.40, 0.20),   # entering dark patch
        (0.45, 0.12),
        (0.50, 0.08),   # nadir
        (0.55, 0.15),   # glimmer
        (0.60, 0.30),   # second wind starts
        (0.65, 0.50),
        (0.70, 0.65),
        (0.75, 0.72),
        (0.80, 0.68),   # final push
        (0.85, 0.60),
        (0.90, 0.70),
        (0.95, 0.85),
        (1.00, 0.95),   # finish line euphoria
    ]

    points = [
        (margin_l + frac * chart_w, chart_bot - mood * chart_h)
        for frac, mood in mood_pts
    ]

    svg.append(_svg_path(
        _cubic_bezier_path(points),
        stroke="var(--gg-color-primary-brown)", stroke_width=3,
        extra='stroke-linecap="round"'
    ))

    # Y-axis labels
    svg.append(_svg_text(
        margin_l - 8, chart_top + 15, "HIGH",
        font_size=11, fill="var(--gg-color-secondary-brown)",
        anchor="end", weight="700",
        family="var(--gg-font-data)"
    ))
    svg.append(_svg_text(
        margin_l - 8, chart_bot - 5, "LOW",
        font_size=11, fill="var(--gg-color-secondary-brown)",
        anchor="end", weight="700",
        family="var(--gg-font-data)"
    ))

    # X-axis label
    svg.append(_svg_text(
        vb_w / 2, chart_bot + 35, "RACE PROGRESS",
        font_size=13, fill="var(--gg-color-secondary-brown)",
        anchor="middle", weight="700",
        family="var(--gg-font-data)",
        extra='letter-spacing="3"'
    ))

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block.get("caption", ""), block.get("layout", "inline"), block.get("asset_id", ""), block.get("alt", ""))


# ══════════════════════════════════════════════════════════════
# Dispatch Map
# ══════════════════════════════════════════════════════════════


INFOGRAPHIC_RENDERERS = {
    "ch1-gear-essentials": render_gear_grid,
    "ch1-rider-grid": render_rider_categories,
    "ch1-hierarchy-of-speed": render_hierarchy_pyramid,
    "ch2-scoring-dimensions": render_scoring_dimensions,
    "ch2-tier-distribution": render_tier_distribution,
    "ch3-supercompensation": render_supercompensation,
    "ch3-zone-spectrum": render_zone_spectrum,
    "ch3-pmc-chart": render_pmc_chart,
    "ch3-training-phases": render_training_phases,
    "ch4-execution-gap": render_execution_gap,
    "ch4-traffic-light": render_traffic_light,
    "ch5-fueling-timeline": render_fueling_timeline,
    "ch5-bonk-math": render_bonk_math,
    "ch6-three-acts": render_three_acts,
    "ch6-psych-phases": render_psych_phases,
    "ch7-race-week-countdown": render_race_week_countdown,
}
