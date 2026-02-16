#!/usr/bin/env python3
"""
Inline SVG/HTML infographic renderers for the Gravel God Training Guide.

16 renderers producing interactive, progressively-enhanced infographics:
- Flip cards (data-interactive="flip")
- Accordion panels (data-interactive="accordion")
- Expandable timelines (data-interactive="timeline")
- Traffic-light cycling (data-interactive="traffic-light")
- Radar morph charts (data-interactive="radar-morph")
- Digit rollers (data-interactive="digit-roller")
- Line draw animations (data-animate="line")
- Bar/shimmer animations (data-animate="bar")
- Pyramid stagger (data-animate="pyramid")
- Fade stagger (data-animate="fade-stagger")
- Heatmap grids with proximity glow

All interactivity is via data-* attributes — JS handlers in generate_guide.py.
Static fallback works without JS (.gg-has-js guard).

Hero photos (ch1-hero through ch8-hero) remain as <img> tags.
All colors use CSS custom properties via var(--gg-color-*).
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
                 asset_id: str = "", alt: str = "",
                 title: str = "", takeaway: str = "") -> str:
    """Wrap content in a <figure> with optional title bar, takeaway, caption, and aria-label."""
    cls = "gg-infographic"
    if layout and layout != "inline":
        cls += f" gg-infographic--{layout}"
    aid = f' data-asset-id="{_esc(asset_id)}"' if asset_id else ""
    aria = f' aria-label="{_esc(alt)}"' if alt else ""
    role = ' role="figure"' if alt else ""
    title_html = (
        f'<div class="gg-infographic-title">{_esc(title)}</div>'
        if title else ""
    )
    takeaway_html = (
        f'<div class="gg-infographic-takeaway">{_esc(takeaway)}</div>'
        if takeaway else ""
    )
    cap = (
        f'<figcaption class="gg-infographic-caption">{_esc(caption)}</figcaption>'
        if caption else ""
    )
    return f'<figure class="{cls}"{aid}{role}{aria}>{title_html}{inner}{takeaway_html}{cap}</figure>'


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
    """5-item gear essentials grid as flip cards (front: icon+title, back: details+tip).

    Uses data-interactive="flip" for click-to-flip progressive enhancement.
    """
    items = [
        ("frame", "Bike Frame", "Your foundation. Gravel-specific geometry, tire clearance, and mounting points.",
         "Look for 45mm+ tire clearance and multiple bottle mounts"),
        ("tires", "Tires", "The single biggest performance variable. 40-50mm for most courses.",
         "Run 38-42mm for fast courses, 45-50mm for chunky terrain"),
        ("helmet", "Helmet", "Non-negotiable safety. MIPS preferred. Ventilation matters for long days.",
         "MIPS or WaveCel for rotational impact protection"),
        ("repair", "Repair Kit", "Tubes/plugs, multi-tool, CO2. Practice repairs before race day.",
         "Carry both a tube and plugs \u2014 plugs fail on sidewall cuts"),
        ("hydration", "Hydration", "Bottles or pack. Know your course's water availability.",
         "Two bottles minimum; pack for courses with 30+ mile gaps between aid"),
    ]

    cards = []
    for key, card_title, desc, tip in items:
        icon_fn = _GEAR_ICONS.get(key, _icon_frame)
        cards.append(
            f'<div class="gg-infographic-card" data-interactive="flip" tabindex="0"'
            f' aria-label="Flip to see {_esc(card_title)} details">'
            # Front face — icon + title
            f'<div class="gg-infographic-card-front">'
            f'<div class="gg-infographic-card-icon">{icon_fn()}</div>'
            f'<div class="gg-infographic-card-title">{_esc(card_title)}</div>'
            f'<div class="gg-infographic-flip-hint">Tap to flip</div>'
            f'</div>'
            # Back face — description + tip
            f'<div class="gg-infographic-card-back">'
            f'<div class="gg-infographic-card-title">{_esc(card_title)}</div>'
            f'<div class="gg-infographic-card-desc">{_esc(desc)}</div>'
            f'<div class="gg-infographic-card-tip">{_esc(tip)}</div>'
            f'</div>'
            f'</div>'
        )

    inner = f'<div class="gg-infographic-gear-grid">{"".join(cards)}</div>'
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Essential Gear for Race Day",
        takeaway="Get these five categories dialed in training \u2014 never debut new gear on race day.",
    )


def render_rider_categories(block: dict) -> str:
    """4-column rider category grid as flip cards (front: summary, back: details).

    Uses data-interactive="flip" for click-to-flip progressive enhancement.
    """
    riders = [
        {
            "name": "Ayahuasca",
            "hours": "3-5 hrs/wk",
            "ftp_range": "100-160W",
            "ftp_pct": 25,
            "goal": "Finish upright",
            "reality": "Survival mode",
            "tier": "T4",
            "detail": "First-timers and casual riders. Focus on completing the distance, "
                      "not competing. Build slowly with 3-4 rides per week.",
        },
        {
            "name": "Finisher",
            "hours": "5-8 hrs/wk",
            "ftp_range": "160-220W",
            "ftp_pct": 50,
            "goal": "Finish strong",
            "reality": "Solid mid-pack",
            "tier": "T3-T4",
            "detail": "The biggest category. Consistent training pays off \u2014 "
                      "structured intervals 2x/week plus one long ride builds real fitness.",
        },
        {
            "name": "Competitor",
            "hours": "8-12 hrs/wk",
            "ftp_range": "220-280W",
            "ftp_pct": 75,
            "goal": "Top 25%",
            "reality": "Age group podium",
            "tier": "T2-T3",
            "detail": "Serious athletes balancing training with life. Periodized plans, "
                      "race-specific prep, and dialed nutrition separate you from finishers.",
        },
        {
            "name": "Podium",
            "hours": "12-20 hrs/wk",
            "ftp_range": "280-400W",
            "ftp_pct": 100,
            "goal": "Win or podium",
            "reality": "Elite-level prep",
            "tier": "T1",
            "detail": "Full commitment. Double days, altitude camps, race recon. "
                      "Every marginal gain matters when the field is this deep.",
        },
    ]

    highlight_colors = {
        "Ayahuasca": "var(--gg-color-secondary-brown)",
        "Finisher": "var(--gg-color-teal)",
        "Competitor": "var(--gg-color-gold)",
        "Podium": "var(--gg-color-primary-brown)",
    }

    cards = []
    for r in riders:
        bar_w = r["ftp_pct"]
        accent = highlight_colors.get(r["name"], "var(--gg-color-teal)")
        cards.append(
            f'<div class="gg-infographic-card" data-interactive="flip" tabindex="0"'
            f' aria-label="Flip to see {_esc(r["name"])} details">'
            # Front face — summary
            f'<div class="gg-infographic-card-front">'
            f'<div class="gg-infographic-rider-name">{_esc(r["name"])}</div>'
            f'<div class="gg-infographic-rider-hours">{_esc(r["hours"])}</div>'
            f'<div class="gg-infographic-rider-bar-wrap">'
            f'<div class="gg-infographic-rider-bar" style="width:{bar_w}%;background:{accent}"></div>'
            f'</div>'
            f'<div class="gg-infographic-rider-ftp">{_esc(r["ftp_range"])}</div>'
            f'<div class="gg-infographic-flip-hint">Tap to flip</div>'
            f'</div>'
            # Back face — details
            f'<div class="gg-infographic-card-back"'
            f' style="border-top:4px solid {accent}">'
            f'<div class="gg-infographic-rider-name">{_esc(r["name"])}</div>'
            f'<div class="gg-infographic-rider-meta">'
            f'<span>Goal: {_esc(r["goal"])}</span>'
            f'<span>Reality: {_esc(r["reality"])}</span>'
            f'<span>Races: {_esc(r["tier"])}</span>'
            f'</div>'
            f'<div class="gg-infographic-card-detail">{_esc(r["detail"])}</div>'
            f'</div>'
            f'</div>'
        )

    inner = f'<div class="gg-infographic-rider-grid">{"".join(cards)}</div>'
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Four Rider Archetypes",
        takeaway="Most riders are Finishers \u2014 and that\u2019s the right goal for your first gravel race.",
    )


def render_race_week_countdown(block: dict) -> str:
    """7-day race week countdown as expandable timeline nodes.

    Uses data-interactive="timeline" for click-to-expand detail panels.
    Static fallback shows all days with notes visible.
    """
    days = [
        ("MON", "Easy spin", "30-45 min Z2. Legs loose, nothing hard.",
         ["Spin 30-45 minutes in Zone 2", "Focus on smooth pedaling, no intensity",
          "Hydrate well \u2014 start pre-loading electrolytes"], False),
        ("TUE", "Openers", "3x1 min Z4 surges in a Z2 ride. Wake up legs.",
         ["Warm up 15 min Z2", "3\u00d71 min at Zone 4 with 3 min recovery",
          "Cool down 10 min. Legs should feel snappy, not tired."], False),
        ("WED", "Rest day", "Off the bike. Walk, stretch, hydrate.",
         ["Completely off the bike", "Light walk or stretching only",
          "Focus on sleep quality \u2014 aim for 8+ hours"], False),
        ("THU", "Shakeout", "20-30 min easy spin. Bike check.",
         ["20-30 min very easy spin", "Check tire pressure, brakes, shifting",
          "Lube chain, charge computer and lights"], False),
        ("FRI", "Rest + prep", "Lay out gear. Charge devices. Sleep early.",
         ["Lay out ALL race gear \u2014 kit, nutrition, tools",
          "Charge every device: GPS, phone, lights",
          "Bed by 9 PM. Pre-race sleep matters more than race-night sleep."], False),
        ("SAT", "Travel day", "Drive to venue. Packet pickup. Course preview.",
         ["Drive to venue, check into lodging",
          "Packet pickup and gear check",
          "Short course preview ride if possible (30 min max)"], False),
        ("SUN", "RACE DAY", "Execute the plan. Trust the training.",
         ["Wake 3 hours before start, eat 600-800 cal breakfast",
          "Arrive 90 min early for setup and warm-up",
          "Execute your pacing plan. Trust the training. Enjoy the ride."], True),
    ]

    nodes = []
    for i, (abbr, task, note, details, is_race_day) in enumerate(days):
        cls = "gg-infographic-timeline-node"
        if is_race_day:
            cls += " gg-infographic-timeline-node--highlight"
        detail_items = "".join(f"<li>{_esc(d)}</li>" for d in details)
        nodes.append(
            f'<div class="{cls}" tabindex="0" role="button"'
            f' aria-expanded="false" style="--delay:{i * 80}ms">'
            # Node marker + summary (always visible)
            f'<div class="gg-infographic-timeline-marker"></div>'
            f'<div class="gg-infographic-timeline-summary">'
            f'<div class="gg-infographic-day-abbr">{_esc(abbr)}</div>'
            f'<div class="gg-infographic-day-task">{_esc(task)}</div>'
            f'</div>'
            # Detail panel (expanded on click)
            f'<div class="gg-infographic-timeline-detail">'
            f'<ul class="gg-infographic-timeline-list">{detail_items}</ul>'
            f'</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-infographic-timeline" data-interactive="timeline"'
        f' data-animate="fade-stagger">{"".join(nodes)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Race Week: Seven Days Out",
        takeaway="Race week is about rest and logistics, not fitness. The hay is in the barn.",
    )


def render_traffic_light(block: dict) -> str:
    """Green/Yellow/Red autoregulation system — click-to-cycle states.

    Uses data-interactive="traffic-light" with data-state for JS cycling.
    Static fallback shows all three states expanded.
    """
    signals = [
        {
            "state": "go",
            "color": "var(--gg-color-teal)",
            "label": "GREEN \u2014 Go",
            "criteria": "Slept 7+ hrs, resting HR normal, motivation high, no soreness",
            "action": "Execute as planned. Full intensity.",
        },
        {
            "state": "caution",
            "color": "var(--gg-color-gold)",
            "label": "YELLOW \u2014 Caution",
            "criteria": "Slept 5-7 hrs, slightly elevated HR, moderate fatigue",
            "action": "Reduce intensity 5-10%. Shorten intervals. Monitor feel.",
        },
        {
            "state": "stop",
            "color": "var(--gg-color-error)",
            "label": "RED \u2014 Stop",
            "criteria": "Slept <5 hrs, elevated HR, illness symptoms, sharp pain",
            "action": "Rest or Z1 only. Recovery is training. Come back tomorrow.",
        },
    ]

    rows = []
    for s in signals:
        rows.append(
            f'<div class="gg-infographic-signal-row" data-state="{s["state"]}"'
            f' tabindex="0" role="button"'
            f' aria-label="{_esc(s["label"])}: {_esc(s["criteria"])}">'
            f'<div class="gg-infographic-signal-indicator"'
            f' style="background:{s["color"]}"></div>'
            f'<div class="gg-infographic-signal-body">'
            f'<div class="gg-infographic-signal-label">{_esc(s["label"])}</div>'
            f'<div class="gg-infographic-signal-criteria">{_esc(s["criteria"])}</div>'
            f'<div class="gg-infographic-signal-action">{_esc(s["action"])}</div>'
            f'</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-infographic-traffic-light"'
        f' data-interactive="traffic-light" data-state="go">'
        f'<div class="gg-infographic-traffic-light__prompt">'
        f'Click a signal to see your training prescription'
        f'</div>'
        f'{"".join(rows)}'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Go / Caution / No-Go Framework",
        takeaway="If you\u2019re in the red zone on two or more criteria, DNS is the smart play.",
    )


def _mini_sparkline(points_str: str, color: str) -> str:
    """Render a mini SVG sparkline curve for act panels (effort/energy profile)."""
    return (
        f'<svg viewBox="0 0 120 40" style="width:100%;height:40px;display:block" aria-hidden="true">'
        f'<path d="{points_str}" fill="none"'
        f' stroke="{color}" stroke-width="2" stroke-linecap="square"/>'
        f'</svg>'
    )


def render_three_acts(block: dict) -> str:
    """Three-act race structure as accordion panels with mini sparklines.

    Uses data-interactive="accordion" for click-to-expand.
    Static fallback shows all panels with strategies visible.
    """
    acts = [
        {
            "num": "ACT 1",
            "title": "Restraint",
            "range": "0-40%",
            "sparkline": "M 0,30 Q 30,28 60,25 Q 90,22 120,20",
            "strategies": [
                "Hold 10% below target power",
                "Ignore early surges",
                "Settle into rhythm",
                "Bank nothing \u2014 save everything",
            ],
        },
        {
            "num": "ACT 2",
            "title": "Resilience",
            "range": "40-75%",
            "sparkline": "M 0,20 Q 30,15 60,18 Q 90,22 120,15",
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
            "sparkline": "M 0,25 Q 30,30 60,20 Q 90,10 120,5",
            "strategies": [
                "Unlock remaining reserves",
                "Shorten mental horizon: 10 min at a time",
                "Draw on training memories",
                "This is what you came for",
            ],
        },
    ]

    act_colors = [
        "var(--gg-color-teal)",
        "var(--gg-color-gold)",
        "var(--gg-color-primary-brown)",
    ]
    panels = []
    for i, act in enumerate(acts):
        items = "".join(f"<li>{_esc(s)}</li>" for s in act["strategies"])
        sparkline = _mini_sparkline(act["sparkline"], act_colors[i])
        panels.append(
            f'<div class="gg-infographic-act-panel" tabindex="0" role="button"'
            f' aria-expanded="false">'
            # Header (always visible, clickable)
            f'<div class="gg-infographic-act-header">'
            f'<div class="gg-infographic-act-num">{_esc(act["num"])}</div>'
            f'<div class="gg-infographic-act-title"'
            f' style="border-bottom-color:{act_colors[i]}">{_esc(act["title"])}</div>'
            f'<div class="gg-infographic-act-range">{_esc(act["range"])}</div>'
            f'<div class="gg-infographic-act-sparkline">{sparkline}</div>'
            f'</div>'
            # Body (expanded on click)
            f'<div class="gg-infographic-act-body">'
            f'<ul class="gg-infographic-act-list">{items}</ul>'
            f'</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-infographic-three-acts"'
        f' data-interactive="accordion">{"".join(panels)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Three Acts of Every Gravel Race",
        takeaway="Restraint early, resilience in the middle, resolve at the end. Violate the order and you\u2019ll bonk.",
    )


def render_bonk_math(block: dict) -> str:
    """Bonk math with digit roller for the 600g total + waterfall gel grid.

    Uses data-interactive="digit-roller" for the animated total and
    data-animate="bar" for the staggered waterfall gel visualization.
    """
    # Digit roller for 600 — 3 digit columns (6, 0, 0)
    def _digit_strip() -> str:
        digits = "".join(
            f'<span class="gg-infographic-bonk-digit-val">{d}</span>'
            for d in range(10)
        )
        return f'<div class="gg-infographic-bonk-digit-strip">{digits}</div>'

    roller = (
        '<div class="gg-infographic-bonk-roller" data-interactive="digit-roller"'
        ' data-values="600" data-unit="g">'
        '<div class="gg-infographic-bonk-equation"'
        ' data-tooltip="75g/hr is the target for trained gut absorption. Build up to this in training." tabindex="0">'
        '<span class="gg-infographic-bonk-num">8</span>'
        '<span class="gg-infographic-bonk-op">&times;</span>'
        '<span class="gg-infographic-bonk-num">75g</span>'
        '<span class="gg-infographic-bonk-op">=</span>'
        '<span class="gg-infographic-bonk-total">'
        f'<span class="gg-infographic-bonk-digit">{_digit_strip()}</span>'
        f'<span class="gg-infographic-bonk-digit">{_digit_strip()}</span>'
        f'<span class="gg-infographic-bonk-digit">{_digit_strip()}</span>'
        '<span class="gg-infographic-bonk-unit">g</span>'
        '</span>'
        '</div>'
        '<div class="gg-infographic-bonk-subtitle">'
        '8 hours &times; 75g carbs/hr = 600g total carbohydrate</div>'
        '</div>'
    )

    # 24 gel rectangles as waterfall bars with stagger
    gels = ""
    for i in range(24):
        gels += (
            f'<div class="gg-infographic-bonk-gel"'
            f' style="--delay:{i * 40}ms"></div>'
        )

    gel_grid = (
        f'<div class="gg-infographic-bonk-grid" data-animate="bar">{gels}</div>'
        f'<div class="gg-infographic-bonk-label">= 24 gels (or equivalent)</div>'
    )

    inner = f'<div class="gg-infographic-bonk-math">{roller}{gel_grid}</div>'
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Math Behind the Bonk",
        takeaway="Your body stores ~2,000 calories of glycogen. An 8-hour race burns ~4,000+. Do the math.",
    )


# ══════════════════════════════════════════════════════════════
# Phase 3: SVG Charts (10 renderers)
# ══════════════════════════════════════════════════════════════


def render_zone_spectrum(block: dict) -> str:
    """7 horizontal bars Z1-Z7 as HTML shimmer bars with stagger delays.

    Uses data-animate="bar" with shimmer ::before pseudo-element.
    Converted from SVG to HTML bars for shimmer CSS support.
    """
    zones = [
        ("Z1", "Active Recovery", "\u226455%", "var(--gg-color-light-teal)", 28,
         "Easy spinning, <55% FTP. Promotes blood flow and recovery."),
        ("Z2", "Endurance", "55-75%", "var(--gg-color-teal)", 38,
         "55-75% FTP. The foundation of all gravel training."),
        ("Z3", "Tempo", "76-90%", "var(--gg-color-gold)", 45,
         "76-90% FTP. Comfortably hard \u2014 the sweet spot for long rides."),
        ("Z4", "Threshold", "91-105%", "var(--gg-color-light-gold)", 53,
         "91-105% FTP. Race pace for short-course gravel events."),
        ("Z5", "VO2max", "106-120%", "var(--gg-color-warm-brown)", 60,
         "106-120% FTP. Hard intervals that build top-end power."),
        ("Z6", "Anaerobic", "121-150%", "var(--gg-color-secondary-brown)", 75,
         "121-150% FTP. Short punchy efforts for climbs and surges."),
        ("Z7", "Neuromuscular", "Max", "var(--gg-color-primary-brown)", 100,
         "Max effort sprints. Rarely needed in gravel racing."),
    ]

    rows = []
    for i, (zone_num, zone_name, pct_range, color, bar_pct, tip) in enumerate(zones):
        delay = i * 100
        rows.append(
            f'<div class="gg-bar-chart__row" style="--delay:{delay}ms">'
            f'<div class="gg-bar-chart__label">'
            f'<span class="gg-infographic-zone-num">{_esc(zone_num)}</span>'
            f' {_esc(zone_name)}</div>'
            f'<div class="gg-bar-chart__track">'
            f'<div class="gg-bar-chart__fill" style="--w:{bar_pct}%;background:{color}"'
            f' data-tooltip="{_esc(tip)}" tabindex="0">'
            f'<span class="gg-bar-chart__value">{_esc(pct_range)}</span>'
            f'</div>'
            f'</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-bar-chart" data-animate="bar">'
        f'<div class="gg-bar-chart__body">{"".join(rows)}</div>'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Seven Training Zones",
        takeaway="Gravel racing lives in Zones 2\u20134. Build your base there before chasing intensity.",
    )


def render_hierarchy_pyramid(block: dict) -> str:
    """5-layer performance hierarchy as narrowing HTML bars (pyramid, bottom-to-top).

    Uses data-animate="pyramid" with stagger delays for bottom-up reveal.
    Widest bar (Fitness) at bottom, narrowest (Equipment) at top.
    """
    # Ordered top-to-bottom visually (narrowest first)
    layers = [
        ("Equipment", "0.5%", 15,
         "Marginal gains: lighter wheels, aero bars. Matters least.",
         "var(--gg-color-tan)", "var(--gg-color-primary-brown)"),
        ("Bike Handling", "1.5%", 30,
         "Cornering, descending, loose-surface skills save minutes.",
         "var(--gg-color-sand)", "var(--gg-color-primary-brown)"),
        ("Nutrition", "8%", 50,
         "Proper fueling prevents bonking \u2014 worth 30+ min in long races.",
         "var(--gg-color-warm-brown)", "var(--gg-color-warm-paper)"),
        ("Pacing", "20%", 75,
         "Even pacing beats heroic surges. Discipline > talent.",
         "var(--gg-color-secondary-brown)", "var(--gg-color-warm-paper)"),
        ("Fitness", "70%", 100,
         "+50W FTP = ~2mph faster. Train more, spend less.",
         "var(--gg-color-primary-brown)", "var(--gg-color-warm-paper)"),
    ]

    n = len(layers)
    bars = []
    for i, (label, pct, width, tip, bg, text_color) in enumerate(layers):
        # Stagger delay: bottom-up (reverse index)
        delay = (n - 1 - i) * 120
        bars.append(
            f'<div class="gg-infographic-pyramid-bar"'
            f' style="--w:{width}%;--delay:{delay}ms;background:{bg}"'
            f' data-tooltip="{_esc(tip)}" tabindex="0">'
            f'<div class="gg-infographic-pyramid-label"'
            f' style="color:{text_color}">{_esc(label)}</div>'
            f'<div class="gg-infographic-pyramid-pct"'
            f' style="color:{text_color}">{_esc(pct)}</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-infographic-pyramid" data-animate="pyramid">'
        f'{"".join(bars)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Hierarchy of Speed: What Actually Makes You Faster",
        takeaway="Aero gains are sexy but fitness is 80% of the equation. Train more, spend less.",
    )


def render_tier_distribution(block: dict) -> str:
    """Tier distribution as pyramid with narrowing bars (T4 widest, T1 narrowest).

    Uses data-animate="pyramid" with bottom-to-top stagger.
    Visual hierarchy: T1 at top (narrow, prestigious), T4 at bottom (wide, many races).
    """
    # Ordered top-to-bottom: T1 (fewest) → T4 (most)
    tiers = [
        ("T1", 25, 8, "var(--gg-color-primary-brown)", "var(--gg-color-warm-paper)",
         "Unbound, BWR, Leadville \u2014 the bucket-list events"),
        ("T2", 73, 22, "var(--gg-color-secondary-brown)", "var(--gg-color-warm-paper)",
         "SBT GRVL, Gravel Worlds, Mid South \u2014 strong fields, great courses"),
        ("T3", 154, 47, "var(--gg-color-tier-3)", "var(--gg-color-warm-paper)",
         "Regional favorites with solid organization and community"),
        ("T4", 76, 23, "var(--gg-color-tier-4)", "var(--gg-color-warm-paper)",
         "Local or niche events \u2014 great entry points for beginners"),
    ]

    total = sum(t[1] for t in tiers)
    n = len(tiers)
    bars = []
    # Width proportional to count, scaled so T3 (largest) = 100%
    max_count = max(t[1] for t in tiers)
    for i, (label, count, pct, bg, text_color, tip) in enumerate(tiers):
        width_pct = int((count / max_count) * 100)
        delay = (n - 1 - i) * 150
        bars.append(
            f'<div class="gg-infographic-pyramid-bar"'
            f' style="--w:{width_pct}%;--delay:{delay}ms;background:{bg}"'
            f' data-tooltip="{_esc(tip)}" tabindex="0">'
            f'<div class="gg-infographic-pyramid-label"'
            f' style="color:{text_color}">'
            f'{_esc(label)}: {count} races</div>'
            f'<div class="gg-infographic-pyramid-pct"'
            f' style="color:{text_color}">{pct}%</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-infographic-pyramid" data-animate="pyramid">'
        f'{"".join(bars)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="How We Tier 328 Gravel Races",
        takeaway="Only 8% earn Tier 1. If your target race is T1, respect it with T1 preparation.",
    )


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
        ("BASE", 0, 5, "color-mix(in srgb, var(--gg-color-teal) 12%, transparent)",
         "Weeks 1-5: Long Z2 rides, build aerobic engine. 3-5 rides/week."),
        ("BUILD", 5, 9, "color-mix(in srgb, var(--gg-color-gold) 12%, transparent)",
         "Weeks 6-9: Add intervals, tempo, and race-specificity."),
        ("PEAK / TAPER", 9, 12, "color-mix(in srgb, var(--gg-color-primary-brown) 12%, transparent)",
         "Weeks 10-12: Reduce volume 40%, maintain intensity, rest up."),
    ]

    week_w = chart_w / 12
    for idx, (label, start, end, fill, tip) in enumerate(phases):
        x = margin_l + start * week_w
        w = (end - start) * week_w
        # Phase box with grow animation
        svg.append(_svg_rect(
            x, chart_top, w, chart_h, fill=fill,
            stroke="var(--gg-color-tan)", stroke_width=1,
            extra=f'data-animate="bar" data-target-width="{w}"'
                  f' data-tooltip="{_esc(tip)}" tabindex="0"'
        ))
        # Phase label with fade-in after bar grows
        delay_ms = 800 + idx * 200
        svg.append(
            f'<g class="gg-line-chart__annotation" style="--delay:{delay_ms}ms">'
        )
        svg.append(_svg_text(
            x + w / 2, chart_top + 30, label,
            font_size=18, fill="var(--gg-color-primary-brown)",
            anchor="middle", weight="700",
            family="var(--gg-font-editorial)"
        ))
        svg.append("</g>")

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
        extra='stroke-linecap="round" data-animate="line"'
              ' class="gg-line-chart__path"'
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
        extra='stroke-linecap="round" stroke-dasharray="8 4" data-animate="line"'
              ' class="gg-line-chart__path gg-line-chart__path--secondary"'
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
    return _figure_wrap(
        "".join(svg), block.get("caption", ""), block.get("layout", "full-width"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Periodization: Building Fitness in Three Phases",
        takeaway="Base \u2192 Build \u2192 Peak. Skip base and your peak will have no foundation.",
    )


def render_execution_gap(block: dict) -> str:
    """Execution gap as heatmap grid: planned vs actual intensity over intervals.

    Uses HTML grid layout with intensity classes, proximity glow, and data-tooltip.
    Two rows (Plan vs Actual) x N intervals, color-coded by deviation.
    """
    # Interval data: (label, planned%, actual%)
    intervals = [
        ("Int 1", 85, 95),
        ("Int 2", 85, 78),
        ("Int 3", 85, 55),
        ("Int 4", 85, 84),
        ("Int 5", 85, 83),
        ("Int 6", 85, 85),
    ]

    def _intensity_class(planned: int, actual: int) -> str:
        """Map deviation to intensity level 0-5 for heatmap coloring."""
        diff = abs(actual - planned)
        if diff <= 2:
            return "5"  # perfect
        elif diff <= 5:
            return "4"
        elif diff <= 10:
            return "3"
        elif diff <= 15:
            return "2"
        elif diff <= 25:
            return "1"
        return "0"  # severe deviation

    # Build grid: header row + plan row + actual row
    cells = []

    # Header row
    cells.append('<div class="gg-heatmap__cell gg-heatmap__cell--header"></div>')
    for label, _p, _a in intervals:
        cells.append(
            f'<div class="gg-heatmap__cell gg-heatmap__cell--header">'
            f'{_esc(label)}</div>'
        )

    # Plan row
    cells.append(
        '<div class="gg-heatmap__cell gg-heatmap__cell--row-label">PLAN</div>'
    )
    for label, planned, _actual in intervals:
        cells.append(
            f'<div class="gg-heatmap__cell" data-v="5"'
            f' data-tooltip="{_esc(label)}: Target {planned}% FTP" tabindex="0">'
            f'{planned}%</div>'
        )

    # Actual row (chasing watts)
    cells.append(
        '<div class="gg-heatmap__cell gg-heatmap__cell--row-label">ACTUAL</div>'
    )
    for label, planned, actual in intervals:
        level = _intensity_class(planned, actual)
        diff = actual - planned
        diff_label = f"+{diff}" if diff > 0 else str(diff)
        deviation = "on target" if abs(diff) <= 2 else f"{diff_label}% deviation"
        cells.append(
            f'<div class="gg-heatmap__cell" data-v="{level}"'
            f' data-tooltip="{_esc(label)}: {actual}% FTP ({deviation})" tabindex="0">'
            f'{actual}%</div>'
        )

    n_cols = len(intervals) + 1  # +1 for row label
    inner = (
        f'<div class="gg-heatmap" data-animate="fade-stagger"'
        f' style="--cols:{n_cols}">'
        f'{"".join(cells)}</div>'
        f'<div class="gg-infographic-execution-summary">'
        f'<div class="gg-infographic-execution-bad">'
        f'<span class="gg-infographic-execution-label">Chasing Watts</span>'
        f'<span class="gg-infographic-execution-detail">'
        f'Int 1-3: starts hot (95%), fades to 55%</span></div>'
        f'<div class="gg-infographic-execution-good">'
        f'<span class="gg-infographic-execution-label">Consistent Execution</span>'
        f'<span class="gg-infographic-execution-detail">'
        f'Int 4-6: holds 83-85% \u2014 all within 2% of target</span></div>'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Execution Gap: Plan vs. Reality",
        takeaway="Consistency beats heroism. Four steady efforts outperform three big ones with a crash.",
    )


def render_fueling_timeline(block: dict) -> str:
    """Race-day fueling as horizontal timeline with staggered node fade-in.

    Uses HTML timeline pattern with data-animate="fade-stagger".
    Each node fades in sequentially to show the fueling progression.
    """
    markers = [
        ("T-3 hrs", "Pre-race meal",
         "600-800 cal, low fiber, familiar foods",
         "Oatmeal + banana + honey is the classic. Eat what you practiced."),
        ("T-30 min", "Top off",
         "Gel or drink, 30-50g carbs",
         "One gel or half a bottle of drink mix. Nothing new, nothing heavy."),
        ("Start", "Race begins",
         "Start fueling at min 15-20, not later",
         "Set a timer. By the time you feel hungry, you are already behind."),
        ("Every 20 min", "Steady intake",
         "75g carbs/hr from gels, chews, drink mix",
         "Mix sources: gels + chews + liquid. Trained gut absorbs 90-120g/hr."),
        ("Ongoing", "Hydration",
         "500-750ml/hr, sodium 500-1000mg/hr",
         "Adjust for heat. Clear urine = good. Dark = drink more. Cramping = more sodium."),
    ]

    nodes = []
    for i, (time_label, mk_title, summary, detail) in enumerate(markers):
        nodes.append(
            f'<div class="gg-infographic-timeline-node" style="--delay:{i * 150}ms"'
            f' data-tooltip="{_esc(detail)}" tabindex="0">'
            f'<div class="gg-infographic-timeline-marker"></div>'
            f'<div class="gg-infographic-timeline-summary">'
            f'<div class="gg-infographic-timeline-time">{_esc(time_label)}</div>'
            f'<div class="gg-infographic-timeline-title">{_esc(mk_title)}</div>'
            f'<div class="gg-infographic-timeline-desc">{_esc(summary)}</div>'
            f'</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-infographic-timeline gg-infographic-timeline--horizontal"'
        f' data-animate="fade-stagger">{"".join(nodes)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Race Day Fueling: Hour by Hour",
        takeaway="Start eating at minute 30, not when you\u2019re hungry. By then it\u2019s too late.",
    )


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
    """Radar chart showing scoring dimensions as SVG polygon.

    Uses data-interactive="radar-morph" for toggling between race profiles.
    14 axes arranged radially. Polygon scales in on scroll.
    Falls back to static polygon without JS.
    """
    import math

    rating = _load_unbound_rating()

    dim_tips = {
        "Logistics": "Travel complexity, registration difficulty, permit requirements",
        "Length": "Total race distance \u2014 longer races score higher",
        "Technicality": "Surface difficulty, navigation challenges, technical terrain",
        "Elevation": "Total climbing relative to distance",
        "Climate": "Heat, cold, wind, altitude exposure risks",
        "Altitude": "Maximum elevation and time spent above 5,000ft",
        "Adventure": "Remoteness, scenery, exploration factor",
        "Prestige": "Historical significance, brand recognition, media coverage",
        "Race Quality": "Organization, course marking, aid station quality",
        "Experience": "Overall rider experience, post-race atmosphere",
        "Community": "Local engagement, volunteer quality, spectator support",
        "Field Depth": "Pro presence, competitive depth, field size",
        "Value": "Registration cost relative to what you get",
        "Expenses": "Total trip cost: travel, lodging, gear requirements",
    }
    dim_keys = [
        ("Logistics", "logistics"), ("Length", "length"),
        ("Technicality", "technicality"), ("Elevation", "elevation"),
        ("Climate", "climate"), ("Altitude", "altitude"),
        ("Adventure", "adventure"), ("Prestige", "prestige"),
        ("Race Quality", "race_quality"), ("Experience", "experience"),
        ("Community", "community"), ("Field Depth", "field_depth"),
        ("Value", "value"), ("Expenses", "expenses"),
    ]

    n = len(dim_keys)
    vb_size = 800
    cx, cy = vb_size / 2, vb_size / 2
    max_r = 300  # max radius for score 5
    label_r = max_r + 40  # where labels sit

    svg = [_svg_open(vb_size, vb_size, "gg-infographic-svg")]

    # Grid rings at each score level (1-5)
    for level in range(1, 6):
        r = (level / 5) * max_r
        ring_pts = []
        for i in range(n):
            angle = (2 * math.pi * i / n) - math.pi / 2
            px = cx + r * math.cos(angle)
            py = cy + r * math.sin(angle)
            ring_pts.append(f"{px:.1f},{py:.1f}")
        ring_pts.append(ring_pts[0])  # close
        svg.append(
            f'<polyline points="{" ".join(ring_pts)}" fill="none"'
            f' stroke="var(--gg-color-tan)" stroke-width="1"/>'
        )

    # Axis lines from center to each vertex
    for i in range(n):
        angle = (2 * math.pi * i / n) - math.pi / 2
        ex = cx + max_r * math.cos(angle)
        ey = cy + max_r * math.sin(angle)
        svg.append(_svg_line(cx, cy, ex, ey,
                             stroke="var(--gg-color-sand)", stroke_width=1))

    # Data polygon — Unbound 200 scores
    data_pts = []
    for i, (label, key) in enumerate(dim_keys):
        score = rating.get(key, 0)
        r = (score / 5) * max_r
        angle = (2 * math.pi * i / n) - math.pi / 2
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        data_pts.append(f"{px:.1f},{py:.1f}")

    # Data polygon as JSON for morph animation
    data_json = ",".join(str(rating.get(k, 0)) for _, k in dim_keys)
    svg.append(
        f'<polygon points="{" ".join(data_pts)}"'
        f' fill="color-mix(in srgb, var(--gg-color-teal) 20%, transparent)"'
        f' stroke="var(--gg-color-teal)" stroke-width="2.5"'
        f' stroke-linejoin="miter"'
        f' class="gg-radar-chart__polygon"'
        f' data-scores="{data_json}"/>'
    )

    # Vertex markers (rect only) + tooltips
    for i, (label, key) in enumerate(dim_keys):
        score = rating.get(key, 0)
        r = (score / 5) * max_r
        angle = (2 * math.pi * i / n) - math.pi / 2
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        tip = dim_tips.get(label, "")
        svg.append(_svg_rect(
            px - 4, py - 4, 8, 8,
            fill="var(--gg-color-teal)",
            stroke="var(--gg-color-dark-brown)", stroke_width=1,
            extra=f'class="gg-line-chart__marker"'
                  f' data-tooltip="{_esc(label)}: {score}/5 \u2014 {_esc(tip)}" tabindex="0"'
        ))

    # Axis labels
    for i, (label, _key) in enumerate(dim_keys):
        angle = (2 * math.pi * i / n) - math.pi / 2
        lx = cx + label_r * math.cos(angle)
        ly = cy + label_r * math.sin(angle)
        # Determine text-anchor based on position
        if abs(math.cos(angle)) < 0.15:
            anchor = "middle"
        elif math.cos(angle) > 0:
            anchor = "start"
        else:
            anchor = "end"
        svg.append(_svg_text(
            lx, ly + 5, label,
            font_size=12, fill="var(--gg-color-primary-brown)",
            anchor=anchor, weight="600",
            family="var(--gg-font-data)"
        ))

    svg.append(_svg_close())

    # Morph toggle buttons (race comparison)
    toggle_html = (
        '<div class="gg-radar-chart__toggles">'
        '<button class="gg-radar-chart__toggle is-active" data-race="unbound-200"'
        ' data-scores="' + data_json + '">Unbound 200</button>'
        '<button class="gg-radar-chart__toggle" data-race="mid-south-100"'
        ' data-scores="3,4,3,2,4,1,3,4,5,5,5,4,4,3">Mid South</button>'
        '<button class="gg-radar-chart__toggle" data-race="leadville-100"'
        ' data-scores="4,5,4,5,4,5,5,5,4,5,4,4,3,2">Leadville</button>'
        '</div>'
    )

    inner = (
        f'<div class="gg-radar-chart" data-interactive="radar-morph">'
        f'{toggle_html}{"".join(svg)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Inside the Rating: 14 Scoring Dimensions",
        takeaway="No single score tells the whole story. A race can be Tier 3 overall but Tier 1 on course difficulty.",
    )


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

    # Main curve with line-draw animation
    svg.append(_svg_path(
        _cubic_bezier_path(points),
        stroke="var(--gg-color-primary-brown)", stroke_width=3,
        extra='stroke-linecap="round" data-animate="line"'
              ' class="gg-line-chart__path"'
    ))

    # Key point markers (rect only — no circles per brand rule)
    key_pts = [(0.20, -120, "Nadir"), (0.55, 70, "Peak")]
    for frac, offset, mk_label in key_pts:
        mx = margin_l + frac * chart_w
        my = baseline_y - offset
        svg.append(_svg_rect(
            mx - 4, my - 4, 8, 8,
            fill="var(--gg-color-primary-brown)",
            stroke="var(--gg-color-warm-paper)", stroke_width=2,
            extra='class="gg-line-chart__marker"'
        ))

    # Phase labels with tooltips + fade-stagger animation
    phase_labels = [
        (0.12, -140, "Training\nStress", "var(--gg-color-error)",
         "The workout itself \u2014 muscle fiber damage and glycogen depletion"),
        (0.22, -150, "Fatigue", "var(--gg-color-error)",
         "Performance dips below baseline as body repairs damage"),
        (0.35, 10, "Recovery", "var(--gg-color-gold)",
         "Repair and adaptation \u2014 sleep, nutrition, and easy days"),
        (0.55, 95, "Supercompensation", "var(--gg-color-teal)",
         "The window where fitness exceeds previous baseline \u2014 train again here"),
        (0.80, 25, "Detraining", "var(--gg-color-secondary-brown)",
         "Wait too long and you lose the adaptation gains"),
    ]

    for idx, (frac, y_off, label, color, tip) in enumerate(phase_labels):
        x = margin_l + frac * chart_w
        y = baseline_y - y_off
        # Annotation group with stagger delay for fade-in
        delay_ms = 2500 + idx * 300  # start after line draw completes
        svg.append(f'<g class="gg-line-chart__annotation" style="--delay:{delay_ms}ms">')
        lines = label.split("\n")
        for j, line in enumerate(lines):
            extra_attr = ""
            if j == 0:
                extra_attr = f'data-tooltip="{_esc(tip)}" tabindex="0"'
            svg.append(_svg_text(
                x, y + j * 18, line,
                font_size=14, fill=color,
                anchor="middle", weight="700",
                family="var(--gg-font-editorial)",
                extra=extra_attr
            ))
        svg.append("</g>")

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
    return _figure_wrap(
        "".join(svg), block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Supercompensation: Why Rest Makes You Faster",
        takeaway="You don\u2019t get faster during the workout \u2014 you get faster during recovery.",
    )


def render_pmc_chart(block: dict) -> str:
    """Performance Management Chart: 3 Bezier curves (CTL/ATL/TSB) over 12 weeks.

    Dual line draw with stagger delay. Cross-reveal marker where CTL > ATL (taper).
    Uses gg-line-chart classes for draw animation.
    """
    vb_w, vb_h = 1600, 600
    margin_l, margin_r = 80, 60
    chart_top = 60
    chart_bot = 480
    chart_w = vb_w - margin_l - margin_r
    chart_h = chart_bot - chart_top

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Y-axis labels + grid
    for val, label in [(0, "0"), (50, "50"), (100, "100")]:
        y = chart_bot - (val / 100) * chart_h
        svg.append(_svg_text(
            margin_l - 10, y + 4, label,
            font_size=12, fill="var(--gg-color-secondary-brown)",
            anchor="end", family="var(--gg-font-data)"
        ))
        svg.append(_svg_line(margin_l, y, margin_l + chart_w, y,
                             stroke="var(--gg-color-tan)", stroke_width=1,
                             extra='stroke-dasharray="4 4" class="gg-line-chart__grid"'))

    zero_y = chart_bot - (50 / 100) * chart_h

    # CTL (Fitness) — primary line
    ctl_vals = [25, 30, 36, 43, 50, 57, 63, 70, 75, 78, 72, 65]
    ctl_points = [
        (margin_l + (i + 0.5) * (chart_w / 12), chart_bot - (v / 100) * chart_h)
        for i, v in enumerate(ctl_vals)
    ]
    svg.append(_svg_path(
        _cubic_bezier_path(ctl_points),
        stroke="var(--gg-color-teal)", stroke_width=3,
        extra='stroke-linecap="round" data-animate="line"'
              ' class="gg-line-chart__path"'
    ))

    # ATL (Fatigue) — secondary line with stagger delay
    atl_vals = [30, 45, 55, 50, 65, 70, 60, 80, 75, 50, 35, 25]
    atl_points = [
        (margin_l + (i + 0.5) * (chart_w / 12), chart_bot - (v / 100) * chart_h)
        for i, v in enumerate(atl_vals)
    ]
    svg.append(_svg_path(
        _cubic_bezier_path(atl_points),
        stroke="var(--gg-color-error)", stroke_width=3,
        extra='stroke-linecap="round" stroke-dasharray="8 4" data-animate="line"'
              ' class="gg-line-chart__path gg-line-chart__path--secondary"'
    ))

    # TSB (Form) — third line with further stagger
    tsb_vals = [-5, -15, -19, -7, -15, -13, 3, -10, 0, 28, 37, 40]
    tsb_points = [
        (margin_l + (i + 0.5) * (chart_w / 12), zero_y - (v / 50) * (chart_h / 2))
        for i, v in enumerate(tsb_vals)
    ]
    svg.append(_svg_path(
        _cubic_bezier_path(tsb_points),
        stroke="var(--gg-color-gold)", stroke_width=3,
        extra='stroke-linecap="round" data-animate="line"'
              ' class="gg-line-chart__path gg-line-chart__path--gold"'
    ))

    # Cross-reveal marker: week 10 where CTL > ATL (taper starts working)
    cross_week = 9  # 0-indexed, week 10
    cross_x = margin_l + (cross_week + 0.5) * (chart_w / 12)
    cross_ctl_y = chart_bot - (ctl_vals[cross_week] / 100) * chart_h
    cross_atl_y = chart_bot - (atl_vals[cross_week] / 100) * chart_h
    cross_mid_y = (cross_ctl_y + cross_atl_y) / 2
    svg.append(
        f'<g class="gg-line-chart__annotation" style="--delay:3000ms">'
    )
    svg.append(_svg_rect(
        cross_x - 5, cross_mid_y - 5, 10, 10,
        fill="var(--gg-color-gold)",
        stroke="var(--gg-color-near-black)", stroke_width=2,
        extra='data-tooltip="Week 10: CTL exceeds ATL \u2014 you\'re fresh and fit. Race week." tabindex="0"'
    ))
    svg.append(_svg_text(
        cross_x, cross_mid_y - 16, "RACE READY",
        font_size=12, fill="var(--gg-color-gold)",
        anchor="middle", weight="700",
        family="var(--gg-font-data)"
    ))
    svg.append("</g>")

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
        ("var(--gg-color-teal)", "CTL (Fitness)", "",
         "Chronic Training Load \u2014 your long-term fitness trend"),
        ("var(--gg-color-error)", "ATL (Fatigue)", 'stroke-dasharray="8 4"',
         "Acute Training Load \u2014 recent fatigue from hard training"),
        ("var(--gg-color-gold)", "TSB (Form)", "",
         "Training Stress Balance \u2014 positive = fresh, negative = fatigued"),
    ]
    leg_x = margin_l
    for color, label, dash, tip in items:
        svg.append(_svg_line(leg_x, leg_y, leg_x + 30, leg_y,
                             stroke=color, stroke_width=3,
                             extra=dash))
        svg.append(_svg_text(
            leg_x + 40, leg_y + 5, label,
            font_size=14, fill="var(--gg-color-primary-brown)",
            family="var(--gg-font-data)",
            extra=f'data-tooltip="{_esc(tip)}" tabindex="0"'
        ))
        leg_x += 220

    svg.append(_svg_close())
    return _figure_wrap(
        "".join(svg), block.get("caption", ""), block.get("layout", "full-width"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Performance Management Chart: Fitness, Fatigue, Form",
        takeaway="CTL is your fitness. ATL is your fatigue. TSB is the gap \u2014 go positive before race day.",
    )


def render_psych_phases(block: dict) -> str:
    """Psychological phases mood curve with 5 background bands + Bezier mood line
    and expandable accordion panels below.

    Uses data-interactive="accordion" for phase detail panels.
    SVG curve retains data-animate="line".
    """
    vb_w, vb_h = 1200, 600
    margin_l, margin_r = 60, 60
    chart_top = 60
    chart_bot = 500
    chart_w = vb_w - margin_l - margin_r
    chart_h = chart_bot - chart_top

    # 5 psychological phases
    phases = [
        ("Honeymoon", 0.0, 0.20, "color-mix(in srgb, var(--gg-color-teal) 10%, transparent)",
         "Adrenaline and excitement carry you. Danger: going out too fast.",
         "var(--gg-color-teal)",
         ["Adrenaline masks fatigue \u2014 heart rate is 10-15 bpm above target",
          "Biggest mistake: going out at 110% because it feels easy",
          "Strategy: set a hard ceiling on power/pace for the first 30 minutes"]),
        ("Shattering", 0.20, 0.40, "color-mix(in srgb, var(--gg-color-gold) 10%, transparent)",
         "Reality hits. Fatigue and doubt creep in. Stay process-focused.",
         "var(--gg-color-gold)",
         ["The adrenaline wears off and true fatigue reveals itself",
          "Doubt whispers: 'Why did I sign up for this?'",
          "Strategy: focus on the next aid station, not the finish line"]),
        ("Dark Patch", 0.40, 0.60, "color-mix(in srgb, var(--gg-color-error) 10%, transparent)",
         "The low point. Mantras, small goals, and fuel get you through.",
         "var(--gg-color-error)",
         ["Glycogen depletion + cumulative fatigue = mental low point",
          "This is where races are lost \u2014 most DNFs happen here",
          "Strategy: mantras, 10-min mental chunks, force calories in"]),
        ("Second Wind", 0.60, 0.80, "color-mix(in srgb, var(--gg-color-teal) 10%, transparent)",
         "Energy returns. The body adapts and endorphins kick in.",
         "var(--gg-color-teal)",
         ["Endorphins finally arrive, fat oxidation stabilizes",
          "Mental clarity returns \u2014 you remember why you love this",
          "Strategy: ride the wave, increase effort slightly if legs respond"]),
        ("Final Push", 0.80, 1.00, "color-mix(in srgb, var(--gg-color-gold) 10%, transparent)",
         "The finish is close. Draw on everything you trained for.",
         "var(--gg-color-gold)",
         ["The finish is tangible \u2014 pain tolerance increases when the end is near",
          "Crowd energy and course familiarity (if you pre-rode) carry you",
          "Strategy: empty the tank, leave nothing for the parking lot"]),
    ]

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Background bands
    for label, start, end, fill, tip, _accent, _details in phases:
        x = margin_l + start * chart_w
        w = (end - start) * chart_w
        svg.append(_svg_rect(
            x, chart_top, w, chart_h, fill=fill,
            extra=f'data-tooltip="{_esc(tip)}" tabindex="0"'
        ))
        svg.append(_svg_text(
            x + w / 2, chart_top + 25, label,
            font_size=15, fill="var(--gg-color-primary-brown)",
            anchor="middle", weight="700",
            family="var(--gg-font-editorial)"
        ))

    # Mood curve points (0=worst, 1=best)
    mood_pts = [
        (0.00, 0.70), (0.05, 0.85), (0.10, 0.90), (0.15, 0.80),
        (0.20, 0.65), (0.25, 0.50), (0.30, 0.35), (0.35, 0.25),
        (0.40, 0.20), (0.45, 0.12), (0.50, 0.08), (0.55, 0.15),
        (0.60, 0.30), (0.65, 0.50), (0.70, 0.65), (0.75, 0.72),
        (0.80, 0.68), (0.85, 0.60), (0.90, 0.70), (0.95, 0.85),
        (1.00, 0.95),
    ]

    points = [
        (margin_l + frac * chart_w, chart_bot - mood * chart_h)
        for frac, mood in mood_pts
    ]

    svg.append(_svg_path(
        _cubic_bezier_path(points),
        stroke="var(--gg-color-primary-brown)", stroke_width=3,
        extra='stroke-linecap="round" data-animate="line"'
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

    # Accordion panels below the chart
    panels = []
    for label, _start, _end, _fill, _tip, accent, details in phases:
        detail_items = "".join(f"<li>{_esc(d)}</li>" for d in details)
        panels.append(
            f'<div class="gg-infographic-act-panel" tabindex="0" role="button"'
            f' aria-expanded="false">'
            f'<div class="gg-infographic-act-header">'
            f'<div class="gg-infographic-act-title"'
            f' style="border-bottom-color:{accent}">{_esc(label)}</div>'
            f'</div>'
            f'<div class="gg-infographic-act-body">'
            f'<ul class="gg-infographic-act-list">{detail_items}</ul>'
            f'</div>'
            f'</div>'
        )

    accordion = (
        f'<div class="gg-infographic-psych-accordion"'
        f' data-interactive="accordion">{"".join(panels)}</div>'
    )

    inner = f'<div class="gg-infographic-psych-phases">{"".join(svg)}{accordion}</div>'
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Mental Arc: Excitement to Emptiness to Resolve",
        takeaway="The low point at mile 60 isn\u2019t a sign you\u2019re failing \u2014 it\u2019s a phase everyone passes through.",
    )


# ══════════════════════════════════════════════════════════════
# Phase 3: New Renderers (14 additional)
# ══════════════════════════════════════════════════════════════


def render_gear_weight(block: dict) -> str:
    """Interactive gear weight budget — toggle items to see total weight impact.

    Uses data-interactive="gear-toggle" with live stacked-bar total.
    """
    items = [
        ("Frame", "Gravel bike frame", 8.5, True,
         "Carbon: 7.5-8.5 kg, Alloy: 9-10.5 kg, Steel: 10-12 kg"),
        ("Wheels", "Wheelset", 1.8, True,
         "Carbon: 1.3-1.6 kg, Alloy: 1.7-2.1 kg. Biggest speed gain per gram."),
        ("Tires", "40-50mm gravel tires", 0.7, True,
         "Lighter tires roll faster but puncture more. Run tubeless always."),
        ("Hydration", "2 bottles + cage", 1.5, True,
         "2 bottles = 1.5 kg water + cage. Pack adds 0.5 kg but carries more."),
        ("Repair Kit", "Tubes, plugs, CO2, tool", 0.5, True,
         "Minimum: tube, plugs, CO2, multi-tool, tire lever = 0.5 kg"),
        ("Nutrition", "8hr race fuel", 0.8, True,
         "24 gels = ~0.8 kg. Don\u2019t cut fuel to save weight \u2014 bonking costs more."),
        ("Electronics", "GPS, lights, sensors", 0.3, True,
         "GPS head unit + sensors. Lights for early-morning starts."),
        ("Aero Bars", "Clip-on extensions", 0.4, False,
         "Legal at most gravel events. Saves watts on flat/wind sections."),
    ]

    total_on = sum(w for _, _, w, on, _ in items if on)
    item_html = []
    for name, desc, weight, default_on, tip in items:
        cls = "is-active" if default_on else "is-inactive"
        item_html.append(
            f'<div class="gg-gear-toggle__item {cls}"'
            f' data-weight="{weight}" tabindex="0" role="button"'
            f' aria-pressed="{"true" if default_on else "false"}"'
            f' data-tooltip="{_esc(tip)}">'
            f'<div class="gg-gear-toggle__name">{_esc(name)}</div>'
            f'<div class="gg-gear-toggle__desc">{_esc(desc)}</div>'
            f'<div class="gg-gear-toggle__weight">{weight:.1f} kg</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-gear-toggle" data-interactive="gear-toggle">'
        f'<div class="gg-gear-toggle__grid">{"".join(item_html)}</div>'
        f'<div class="gg-gear-toggle__total">'
        f'<span class="gg-gear-toggle__total-label">Total Weight</span>'
        f'<span class="gg-gear-toggle__total-value"'
        f' data-target="{total_on:.1f}">{total_on:.1f} kg</span>'
        f'</div>'
        f'<div class="gg-gear-toggle__bar">'
        f'<div class="gg-gear-toggle__bar-fill"'
        f' style="--w:{int(total_on / 16 * 100)}%"></div>'
        f'</div>'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Gear Weight Budget: Where Every Gram Goes",
        takeaway="The bike is 60% of total weight. Wheels and tires are the best bang-for-gram upgrades.",
    )


def render_course_profile(block: dict) -> str:
    """SVG elevation profile with gradient-colored segments.

    Uses data-animate="line" for the profile draw.
    Segments colored by gradient steepness.
    """
    # Elevation data points: (mile, elevation_ft, gradient%)
    profile_pts = [
        (0, 1200, 0), (5, 1350, 3), (10, 1800, 9), (15, 2200, 8),
        (20, 1900, -6), (25, 1600, -6), (30, 1700, 2), (35, 2400, 14),
        (40, 2800, 8), (45, 2500, -6), (50, 2100, -8), (55, 1800, -6),
        (60, 1400, -8), (65, 1500, 2), (70, 1800, 6), (75, 2000, 4),
        (80, 1600, -8), (85, 1300, -6), (90, 1200, -2), (95, 1250, 1),
        (100, 1200, -1),
    ]

    vb_w, vb_h = 1400, 500
    margin_l, margin_r = 80, 40
    chart_top = 40
    chart_bot = 420
    chart_w = vb_w - margin_l - margin_r
    chart_h = chart_bot - chart_top

    min_elev = min(e for _, e, _ in profile_pts)
    max_elev = max(e for _, e, _ in profile_pts)
    max_mile = profile_pts[-1][0]

    def _to_xy(mile, elev):
        x = margin_l + (mile / max_mile) * chart_w
        y = chart_bot - ((elev - min_elev) / (max_elev - min_elev)) * chart_h
        return x, y

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Grid lines
    for elev_mark in range(1200, 3200, 400):
        if min_elev <= elev_mark <= max_elev + 200:
            _, y = _to_xy(0, elev_mark)
            svg.append(_svg_line(margin_l, y, margin_l + chart_w, y,
                                 stroke="var(--gg-color-sand)", stroke_width=1,
                                 extra='stroke-dasharray="4 4"'))
            svg.append(_svg_text(
                margin_l - 8, y + 4, f"{elev_mark}ft",
                font_size=11, fill="var(--gg-color-secondary-brown)",
                anchor="end", family="var(--gg-font-data)"
            ))

    # Area fill under profile
    points = [_to_xy(m, e) for m, e, _ in profile_pts]
    area_d = f"M {points[0][0]:.1f},{chart_bot}"
    for px, py in points:
        area_d += f" L {px:.1f},{py:.1f}"
    area_d += f" L {points[-1][0]:.1f},{chart_bot} Z"
    svg.append(_svg_path(
        area_d, fill="color-mix(in srgb, var(--gg-color-teal) 15%, transparent)",
        stroke_width=0
    ))

    # Profile line segments colored by gradient
    for i in range(len(profile_pts) - 1):
        m1, e1, g1 = profile_pts[i]
        m2, e2, g2 = profile_pts[i + 1]
        x1, y1 = _to_xy(m1, e1)
        x2, y2 = _to_xy(m2, e2)
        grad = abs(g2)
        if grad >= 10:
            color = "var(--gg-color-error)"
        elif grad >= 6:
            color = "var(--gg-color-gold)"
        elif grad >= 3:
            color = "var(--gg-color-teal)"
        else:
            color = "var(--gg-color-secondary-brown)"
        tip = f"Mile {m1}-{m2}: {g2:+d}% grade, {e1}-{e2}ft"
        svg.append(_svg_line(
            x1, y1, x2, y2, stroke=color, stroke_width=3,
            extra=f'stroke-linecap="square" data-tooltip="{_esc(tip)}" tabindex="0"'
        ))

    # Mile labels
    for mile_mark in range(0, max_mile + 1, 20):
        x, _ = _to_xy(mile_mark, min_elev)
        svg.append(_svg_text(
            x, chart_bot + 25, f"Mi {mile_mark}",
            font_size=11, fill="var(--gg-color-secondary-brown)",
            anchor="middle", family="var(--gg-font-data)"
        ))

    # Legend
    leg_y = chart_bot + 55
    legend_items = [
        ("var(--gg-color-secondary-brown)", "Flat (<3%)"),
        ("var(--gg-color-teal)", "Moderate (3-6%)"),
        ("var(--gg-color-gold)", "Steep (6-10%)"),
        ("var(--gg-color-error)", "Brutal (10%+)"),
    ]
    leg_x = margin_l
    for color, label in legend_items:
        svg.append(_svg_line(leg_x, leg_y, leg_x + 24, leg_y,
                             stroke=color, stroke_width=3))
        svg.append(_svg_text(
            leg_x + 32, leg_y + 4, label,
            font_size=12, fill="var(--gg-color-primary-brown)",
            family="var(--gg-font-data)"
        ))
        leg_x += 160

    svg.append(_svg_close())
    inner = f'<div data-animate="profile">{"".join(svg)}</div>'
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "full-width"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Reading the Course Profile: Gradient by Segment",
        takeaway="Red segments demand conservation. Save matches for gold. Recover on green and gray.",
    )


def render_field_scatter(block: dict) -> str:
    """SVG scatter plot: field size vs median finish time for T1-T4 races.

    Uses data-animate="scatter" for staggered dot fade-in.
    Rect markers only (no circles per brand rule).
    """
    # Sample data: (name, field_size, median_hrs, tier)
    races = [
        ("Unbound 200", 4000, 12.5, "T1"), ("BWR", 1200, 7.5, "T1"),
        ("Leadville", 2500, 10.0, "T1"), ("SBT GRVL", 3500, 6.0, "T1"),
        ("Mid South", 3000, 5.5, "T2"), ("Gravel Worlds", 800, 11.0, "T2"),
        ("Steamboat", 2000, 7.0, "T2"), ("The Rift", 600, 8.5, "T2"),
        ("Rooted VT", 500, 6.5, "T3"), ("Grasshopper", 300, 5.0, "T3"),
        ("Rule of 3", 400, 8.0, "T3"), ("Ochoco", 200, 9.0, "T3"),
        ("Local Gravel", 100, 4.0, "T4"), ("County Gravel", 150, 5.5, "T4"),
        ("Backroads 50", 80, 3.5, "T4"), ("Farm Gravel", 120, 4.5, "T4"),
    ]

    tier_colors = {
        "T1": "var(--gg-color-primary-brown)",
        "T2": "var(--gg-color-secondary-brown)",
        "T3": "var(--gg-color-tier-3)",
        "T4": "var(--gg-color-tier-4)",
    }

    vb_w, vb_h = 1200, 600
    margin_l, margin_r = 100, 60
    chart_top = 40
    chart_bot = 480
    chart_w = vb_w - margin_l - margin_r
    chart_h = chart_bot - chart_top
    max_field = 4500
    max_hrs = 14

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Grid
    for hrs in range(0, max_hrs + 1, 2):
        y = chart_bot - (hrs / max_hrs) * chart_h
        svg.append(_svg_line(margin_l, y, margin_l + chart_w, y,
                             stroke="var(--gg-color-sand)", stroke_width=1,
                             extra='stroke-dasharray="4 4"'))
        svg.append(_svg_text(
            margin_l - 8, y + 4, f"{hrs}h",
            font_size=11, fill="var(--gg-color-secondary-brown)",
            anchor="end", family="var(--gg-font-data)"
        ))

    for field in range(0, max_field + 1, 1000):
        x = margin_l + (field / max_field) * chart_w
        svg.append(_svg_line(x, chart_top, x, chart_bot,
                             stroke="var(--gg-color-sand)", stroke_width=1,
                             extra='stroke-dasharray="4 4"'))
        svg.append(_svg_text(
            x, chart_bot + 25, f"{field}",
            font_size=11, fill="var(--gg-color-secondary-brown)",
            anchor="middle", family="var(--gg-font-data)"
        ))

    # Axis labels
    svg.append(_svg_text(
        vb_w / 2, chart_bot + 50, "FIELD SIZE",
        font_size=13, fill="var(--gg-color-secondary-brown)",
        anchor="middle", weight="700", family="var(--gg-font-data)"
    ))
    svg.append(_svg_text(
        20, vb_h / 2, "MEDIAN FINISH (HRS)",
        font_size=13, fill="var(--gg-color-secondary-brown)",
        anchor="middle", weight="700", family="var(--gg-font-data)",
        extra='transform="rotate(-90,20,' + str(int(vb_h / 2)) + ')"'
    ))

    # Data points (rect markers — no circles)
    for i, (name, field, hrs, tier) in enumerate(races):
        x = margin_l + (field / max_field) * chart_w
        y = chart_bot - (hrs / max_hrs) * chart_h
        color = tier_colors.get(tier, "var(--gg-color-secondary-brown)")
        svg.append(_svg_rect(
            x - 5, y - 5, 10, 10,
            fill=color, stroke="var(--gg-color-near-black)", stroke_width=1,
            extra=f'class="gg-line-chart__marker" style="--delay:{i * 60}ms"'
                  f' data-tooltip="{_esc(name)} ({tier}): {field} riders, {hrs}h median" tabindex="0"'
        ))

    # Legend
    leg_y = chart_bot + 75
    leg_x = margin_l
    for tier, color in tier_colors.items():
        svg.append(_svg_rect(leg_x, leg_y - 6, 12, 12, fill=color,
                             stroke="var(--gg-color-near-black)", stroke_width=1))
        svg.append(_svg_text(
            leg_x + 18, leg_y + 4, tier,
            font_size=12, fill="var(--gg-color-primary-brown)",
            weight="600", family="var(--gg-font-data)"
        ))
        leg_x += 80

    svg.append(_svg_close())
    inner = f'<div data-animate="scatter">{"".join(svg)}</div>'
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Field Size vs. Race Duration: What You\u2019re Getting Into",
        takeaway="T1 races combine massive fields with brutal distances. T4 events are intimate and accessible.",
    )


def render_race_table(block: dict) -> str:
    """Sortable race comparison table with column-header click sorting.

    Uses data-interactive="sortable-table" for JS-driven column sort.
    """
    headers = ["Race", "Tier", "Distance", "Elevation", "Score", "Field"]
    rows = [
        ["Unbound 200", "T1", "200 mi", "11,000 ft", "94", "4,000"],
        ["Belgian Waffle Ride", "T1", "137 mi", "10,800 ft", "92", "1,200"],
        ["Leadville 100", "T1", "100 mi", "12,600 ft", "90", "2,500"],
        ["SBT GRVL", "T1", "141 mi", "9,400 ft", "88", "3,500"],
        ["Mid South 100", "T2", "100 mi", "4,800 ft", "78", "3,000"],
        ["Gravel Worlds", "T2", "150 mi", "8,200 ft", "76", "800"],
        ["Steamboat Gravel", "T2", "140 mi", "8,800 ft", "72", "2,000"],
        ["Rooted Vermont", "T3", "90 mi", "7,500 ft", "62", "500"],
        ["Grasshopper", "T3", "65 mi", "6,200 ft", "55", "300"],
        ["Rule of Three", "T3", "120 mi", "6,800 ft", "52", "400"],
    ]

    th_html = "".join(
        f'<th class="gg-sortable-table__th" data-col="{i}"'
        f' tabindex="0" role="button" aria-sort="none">{_esc(h)}</th>'
        for i, h in enumerate(headers)
    )

    tr_html = []
    for row in rows:
        cells = "".join(f'<td class="gg-sortable-table__td">{_esc(c)}</td>' for c in row)
        tr_html.append(f'<tr class="gg-sortable-table__tr">{cells}</tr>')

    inner = (
        f'<div class="gg-sortable-table" data-interactive="sortable-table">'
        f'<table class="gg-sortable-table__table">'
        f'<thead><tr>{th_html}</tr></thead>'
        f'<tbody>{"".join(tr_html)}</tbody>'
        f'</table>'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Race Comparison: Sorting the Field",
        takeaway="Sort by any column to find races that match your goals, fitness, and ambition.",
    )


# ══════════════════════════════════════════════════════════════
# Phase 3: Ch3 Renderers (Training)
# ══════════════════════════════════════════════════════════════


def render_power_duration(block: dict) -> str:
    """Power-duration curve showing sustainable power vs time.

    SVG line chart with zone bands in background.
    Uses data-animate="line" for curve draw.
    """
    import math

    vb_w, vb_h = 1400, 500
    margin_l, margin_r = 100, 40
    chart_top = 40
    chart_bot = 420
    chart_w = vb_w - margin_l - margin_r
    chart_h = chart_bot - chart_top

    # Power-duration data: (seconds, watts) — typical 250W FTP rider
    pd_pts = [
        (5, 900), (10, 750), (30, 500), (60, 380),
        (120, 310), (300, 270), (600, 255), (1200, 250),
        (1800, 245), (3600, 235), (7200, 220), (14400, 195),
        (28800, 170),
    ]

    max_secs = 28800  # 8 hours
    max_watts = 1000

    def _to_x(secs):
        # Log scale for time
        return margin_l + (math.log10(max(secs, 1)) / math.log10(max_secs)) * chart_w

    def _to_y(watts):
        return chart_bot - (watts / max_watts) * chart_h

    svg = [_svg_open(vb_w, vb_h, "gg-infographic-svg")]

    # Zone bands (horizontal)
    zone_bands = [
        ("Z2 Endurance", 138, 188, "color-mix(in srgb, var(--gg-color-teal) 8%, transparent)"),
        ("Z3 Tempo", 188, 225, "color-mix(in srgb, var(--gg-color-gold) 8%, transparent)"),
        ("Z4 Threshold", 225, 263, "color-mix(in srgb, var(--gg-color-primary-brown) 8%, transparent)"),
    ]
    for label, lo, hi, fill in zone_bands:
        y_top = _to_y(hi)
        y_bot = _to_y(lo)
        svg.append(_svg_rect(
            margin_l, y_top, chart_w, y_bot - y_top, fill=fill
        ))
        svg.append(_svg_text(
            margin_l + chart_w - 8, (y_top + y_bot) / 2 + 4, label,
            font_size=11, fill="var(--gg-color-secondary-brown)",
            anchor="end", family="var(--gg-font-data)"
        ))

    # Grid
    for watts in range(0, max_watts + 1, 200):
        y = _to_y(watts)
        svg.append(_svg_line(margin_l, y, margin_l + chart_w, y,
                             stroke="var(--gg-color-sand)", stroke_width=1,
                             extra='stroke-dasharray="4 4"'))
        svg.append(_svg_text(
            margin_l - 8, y + 4, f"{watts}W",
            font_size=11, fill="var(--gg-color-secondary-brown)",
            anchor="end", family="var(--gg-font-data)"
        ))

    time_marks = [(60, "1m"), (300, "5m"), (1200, "20m"), (3600, "1h"), (14400, "4h"), (28800, "8h")]
    for secs, label in time_marks:
        x = _to_x(secs)
        svg.append(_svg_text(
            x, chart_bot + 25, label,
            font_size=11, fill="var(--gg-color-secondary-brown)",
            anchor="middle", family="var(--gg-font-data)"
        ))

    # Power-duration curve
    points = [(_to_x(s), _to_y(w)) for s, w in pd_pts]
    svg.append(_svg_path(
        _cubic_bezier_path(points),
        stroke="var(--gg-color-teal)", stroke_width=3,
        extra='stroke-linecap="round" data-animate="line"'
              ' class="gg-line-chart__path"'
    ))

    # Key markers
    key_pts = [
        (60, 380, "1-min Power", "Punch power for steep climbs and surges"),
        (1200, 250, "FTP (20min)", "Your sustainable race-pace power"),
        (14400, 195, "4hr Power", "Long-race power \u2014 typically 78% of FTP"),
    ]
    for secs, watts, label, tip in key_pts:
        x, y = _to_x(secs), _to_y(watts)
        svg.append(_svg_rect(
            x - 4, y - 4, 8, 8,
            fill="var(--gg-color-teal)",
            stroke="var(--gg-color-dark-brown)", stroke_width=2,
            extra=f'class="gg-line-chart__marker"'
                  f' data-tooltip="{_esc(label)}: {watts}W \u2014 {_esc(tip)}" tabindex="0"'
        ))

    svg.append(_svg_close())
    return _figure_wrap(
        "".join(svg), block.get("caption", ""), block.get("layout", "full-width"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Your Power-Duration Curve: What You Can Sustain",
        takeaway="Gravel racing is a 4-8 hour effort. Your 20-minute power matters less than your 4-hour power.",
    )


def render_gantt_season(block: dict) -> str:
    """12-month training season Gantt chart.

    Horizontal bars per phase across months.
    Uses data-animate="gantt" with stagger.
    """
    phases = [
        ("Off-Season", 0, 1.5, "var(--gg-color-secondary-brown)",
         "Nov-mid Dec: Active recovery, cross-training, mental reset"),
        ("Base 1", 1.5, 4, "var(--gg-color-teal)",
         "Mid Dec-Mar: Aerobic foundation, long Z2 rides, consistency"),
        ("Base 2", 4, 6, "color-mix(in srgb, var(--gg-color-teal) 75%, var(--gg-color-gold))",
         "Apr-May: Add tempo work, longer rides, race-surface training"),
        ("Build", 6, 8.5, "var(--gg-color-gold)",
         "Jun-mid Aug: Intervals, race simulation, peak training load"),
        ("Race Season", 8.5, 10.5, "var(--gg-color-primary-brown)",
         "Mid Aug-Oct: A-race taper, B-race maintenance, peak performance"),
        ("Transition", 10.5, 12, "var(--gg-color-tan)",
         "Nov: Deload, reflect, plan next year. Ride for fun."),
    ]

    months = ["Nov", "Dec", "Jan", "Feb", "Mar", "Apr",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    rows = []
    for i, (label, start, end, color, tip) in enumerate(phases):
        start_pct = (start / 12) * 100
        span_pct = ((end - start) / 12) * 100
        delay = i * 120
        rows.append(
            f'<div class="gg-gantt-chart__row" style="--delay:{delay}ms">'
            f'<div class="gg-gantt-chart__label">{_esc(label)}</div>'
            f'<div class="gg-gantt-chart__track">'
            f'<div class="gg-gantt-chart__bar"'
            f' style="--start:{start_pct:.1f}%;--span:{span_pct:.1f}%;background:{color}"'
            f' data-tooltip="{_esc(tip)}" tabindex="0"></div>'
            f'</div>'
            f'</div>'
        )

    # Month headers
    month_headers = "".join(
        f'<div class="gg-gantt-chart__month">{m}</div>' for m in months
    )

    inner = (
        f'<div class="gg-gantt-chart" data-animate="gantt">'
        f'<div class="gg-gantt-chart__months">'
        f'<div class="gg-gantt-chart__month-spacer"></div>{month_headers}</div>'
        f'{"".join(rows)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "full-width"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="The Annual Training Calendar: 12 Months at a Glance",
        takeaway="Build backwards from your A-race. Every month has a purpose \u2014 even the off-season.",
    )


def render_before_after(block: dict) -> str:
    """Before/after comparison: untrained vs trained athlete stats.

    Uses data-interactive="before-after" with drag clip-path divider.
    """
    comparisons = [
        ("FTP", "180W", "250W", "39% increase"),
        ("4hr Power", "140W", "195W", "Sustained race power"),
        ("Recovery HR", "95 bpm", "68 bpm", "Faster bounce-back"),
        ("Time to Exhaustion", "3.5 hrs", "7+ hrs", "Double the endurance"),
        ("Body Comp", "22% BF", "15% BF", "Power-to-weight gains"),
        ("Race Finish", "Bottom 25%", "Top 35%", "Mid-pack competitive"),
    ]

    before_items = []
    after_items = []
    for metric, before, after, note in comparisons:
        before_items.append(
            f'<div class="gg-before-after__row">'
            f'<div class="gg-before-after__metric">{_esc(metric)}</div>'
            f'<div class="gg-before-after__value">{_esc(before)}</div>'
            f'</div>'
        )
        after_items.append(
            f'<div class="gg-before-after__row">'
            f'<div class="gg-before-after__metric">{_esc(metric)}</div>'
            f'<div class="gg-before-after__value">{_esc(after)}</div>'
            f'<div class="gg-before-after__note">{_esc(note)}</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-before-after" data-interactive="before-after">'
        f'<div class="gg-before-after__panel gg-before-after__panel--before">'
        f'<div class="gg-before-after__label">BEFORE</div>'
        f'<div class="gg-before-after__subtitle">Untrained / 3 months</div>'
        f'{"".join(before_items)}</div>'
        f'<div class="gg-before-after__divider">'
        f'<div class="gg-before-after__handle" tabindex="0"'
        f' role="slider" aria-label="Drag to compare before and after"'
        f' aria-valuemin="0" aria-valuemax="100" aria-valuenow="50"></div>'
        f'</div>'
        f'<div class="gg-before-after__panel gg-before-after__panel--after">'
        f'<div class="gg-before-after__label">AFTER</div>'
        f'<div class="gg-before-after__subtitle">12 months structured training</div>'
        f'{"".join(after_items)}</div>'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="12 Months of Structured Training: Before vs. After",
        takeaway="Consistent training transforms everything. A year of focused work can move you up two tiers.",
    )


# ══════════════════════════════════════════════════════════════
# Phase 3: Ch4-Ch5 Renderers (Recovery & Nutrition)
# ══════════════════════════════════════════════════════════════


def render_recovery_dash(block: dict) -> str:
    """Recovery dashboard: Sleep/HRV/Soreness gauges in a 3-up grid.

    Uses data-animate="stroke" for gauge fill animation.
    Square gauges (rect perimeter, not circles).
    """
    gauges = [
        ("Sleep Quality", 7.2, 10, "hrs avg",
         "var(--gg-color-teal)",
         "7+ hours correlates with 15-20% better recovery scores"),
        ("HRV Score", 65, 100, "ms rMSSD",
         "var(--gg-color-gold)",
         "Higher HRV = better parasympathetic recovery. Track trends, not single readings."),
        ("Muscle Readiness", 3, 5, "/5 soreness",
         "var(--gg-color-primary-brown)",
         "Self-rated 1-5. Below 3 = modify workout. Below 2 = rest day."),
    ]

    gauge_html = []
    for label, value, max_val, unit, color, tip in gauges:
        pct = int((value / max_val) * 100)
        # Square gauge: rect perimeter = 4 * side. We use a 120x120 rect.
        side = 120
        perim = 4 * side
        filled = (pct / 100) * perim
        gauge_html.append(
            f'<div class="gg-gauge" data-animate="stroke"'
            f' data-tooltip="{_esc(tip)}" tabindex="0">'
            f'<svg viewBox="0 0 140 140" style="width:100%;height:auto;display:block"'
            f' aria-hidden="true">'
            f'<rect x="10" y="10" width="{side}" height="{side}"'
            f' fill="none" stroke="var(--gg-color-sand)" stroke-width="8"/>'
            f'<rect x="10" y="10" width="{side}" height="{side}"'
            f' fill="none" stroke="{color}" stroke-width="8"'
            f' stroke-dasharray="{perim}" stroke-dashoffset="{perim - filled}"'
            f' class="gg-gauge__fill"'
            f' style="--gauge-perimeter:{perim};--gauge-target:{filled}"/>'
            f'</svg>'
            f'<div class="gg-gauge__value">{value}</div>'
            f'<div class="gg-gauge__unit">{_esc(unit)}</div>'
            f'<div class="gg-gauge__label">{_esc(label)}</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-gauge-grid" data-animate="counter">'
        f'{"".join(gauge_html)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Recovery Dashboard: Three Metrics That Matter",
        takeaway="Track sleep, HRV, and subjective soreness. Two out of three in the red? Take a rest day.",
    )


def render_sleep_debt(block: dict) -> str:
    """Weekly sleep debt accumulator — 7-day bars + deficit/surplus + counter.

    Uses data-animate="counter" for the debt total.
    """
    days = [
        ("Mon", 6.5, 8.0), ("Tue", 5.5, 8.0), ("Wed", 8.5, 8.0),
        ("Thu", 6.0, 8.0), ("Fri", 7.0, 8.0), ("Sat", 9.0, 8.0),
        ("Sun", 6.5, 8.0),
    ]

    total_debt = sum(need - actual for _, actual, need in days if actual < need)
    total_surplus = sum(actual - need for _, actual, need in days if actual > need)
    net_debt = total_debt - total_surplus

    day_html = []
    for abbr, actual, need in days:
        cls = "gg-sleep-tracker__day"
        if actual < need:
            cls += " gg-sleep-tracker__day--deficit"
        else:
            cls += " gg-sleep-tracker__day--surplus"
        diff = actual - need
        tip = f"{abbr}: {actual}h slept, {need:.0f}h needed ({diff:+.1f}h)"
        day_html.append(
            f'<div class="{cls}" data-tooltip="{_esc(tip)}" tabindex="0">'
            f'<div class="gg-sleep-tracker__day-name">{_esc(abbr)}</div>'
            f'<div class="gg-sleep-tracker__day-hrs">{actual}</div>'
            f'<div class="gg-sleep-tracker__day-unit">hrs</div>'
            f'<div class="gg-sleep-tracker__day-need">need {need:.0f}</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-sleep-tracker" data-animate="counter">'
        f'<div class="gg-sleep-tracker__header">'
        f'<div class="gg-sleep-tracker__title">Race Week Sleep Debt</div>'
        f'</div>'
        f'<div class="gg-sleep-tracker__body">'
        f'<div class="gg-sleep-tracker__grid">{"".join(day_html)}</div>'
        f'<div class="gg-sleep-tracker__debt">'
        f'<span class="gg-sleep-tracker__debt-label">Weekly Debt</span>'
        f'<span class="gg-sleep-tracker__debt-num"'
        f' data-target="{net_debt:.0f}">{net_debt:.0f}</span>'
        f'<span class="gg-sleep-tracker__debt-unit">hours</span>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Sleep Debt: The Hidden Performance Killer",
        takeaway="7 hours of debt in race week costs you 10-15% power output. Bank sleep early.",
    )


def render_hydration_calc(block: dict) -> str:
    """Slider-based hydration calculator.

    Uses data-interactive="range-calculator" for live output.
    Inputs: duration, temp, intensity. Output: fluid + sodium needs.
    """
    inner = (
        '<div class="gg-range-calculator" data-interactive="range-calculator"'
        ' data-formula="hydration">'
        '<div class="gg-range-calculator__inputs">'
        # Duration slider
        '<div class="gg-range-calculator__field">'
        '<label class="gg-range-calculator__label">Race Duration</label>'
        '<input type="range" class="gg-range-calculator__slider"'
        ' data-input="duration" min="2" max="12" value="6" step="0.5"'
        ' aria-label="Race duration in hours"/>'
        '<output class="gg-range-calculator__value">6 hrs</output>'
        '</div>'
        # Temperature slider
        '<div class="gg-range-calculator__field">'
        '<label class="gg-range-calculator__label">Temperature</label>'
        '<input type="range" class="gg-range-calculator__slider"'
        ' data-input="temp" min="50" max="110" value="80" step="5"'
        ' aria-label="Temperature in Fahrenheit"/>'
        '<output class="gg-range-calculator__value">80\u00b0F</output>'
        '</div>'
        # Intensity slider
        '<div class="gg-range-calculator__field">'
        '<label class="gg-range-calculator__label">Intensity</label>'
        '<input type="range" class="gg-range-calculator__slider"'
        ' data-input="intensity" min="1" max="5" value="3" step="1"'
        ' aria-label="Effort intensity 1-5"/>'
        '<output class="gg-range-calculator__value">3 / 5</output>'
        '</div>'
        '</div>'
        # Outputs
        '<div class="gg-range-calculator__outputs">'
        '<div class="gg-range-calculator__result">'
        '<div class="gg-range-calculator__result-label">Total Fluid</div>'
        '<div class="gg-range-calculator__result-value" data-output="fluid">3,750 ml</div>'
        '</div>'
        '<div class="gg-range-calculator__result">'
        '<div class="gg-range-calculator__result-label">Sodium</div>'
        '<div class="gg-range-calculator__result-value" data-output="sodium">4,500 mg</div>'
        '</div>'
        '<div class="gg-range-calculator__result">'
        '<div class="gg-range-calculator__result-label">Bottles/hr</div>'
        '<div class="gg-range-calculator__result-value" data-output="bottles">~1.3</div>'
        '</div>'
        '</div>'
        '</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Hydration Calculator: Dial In Your Fluid Plan",
        takeaway="Adjust for your race. Hot weather + long duration = dramatically more fluid and sodium.",
    )


def render_glycogen_gauge(block: dict) -> str:
    """Dual depletion gauges: with vs without nutrition.

    Square SVG gauges showing glycogen percentage remaining.
    Uses data-animate="stroke" for depletion animation.
    """
    scenarios = [
        ("Without Fueling", [
            ("Start", 100, "var(--gg-color-teal)"),
            ("Hour 2", 65, "var(--gg-color-gold)"),
            ("Hour 4", 25, "var(--gg-color-error)"),
            ("Hour 6", 5, "var(--gg-color-error)"),
        ], "Glycogen depleted by hour 4. Bonk inevitable."),
        ("With 75g/hr Fueling", [
            ("Start", 100, "var(--gg-color-teal)"),
            ("Hour 2", 80, "var(--gg-color-teal)"),
            ("Hour 4", 55, "var(--gg-color-gold)"),
            ("Hour 6", 35, "var(--gg-color-gold)"),
        ], "Steady depletion but manageable. Finish strong."),
    ]

    panels = []
    for title_text, checkpoints, summary in scenarios:
        gauges = []
        for label, pct, color in checkpoints:
            side = 80
            perim = 4 * side
            filled = (pct / 100) * perim
            tip = f"{label}: {pct}% glycogen remaining"
            gauges.append(
                f'<div class="gg-gauge gg-gauge--sm" data-animate="stroke"'
                f' data-tooltip="{_esc(tip)}" tabindex="0">'
                f'<svg viewBox="0 0 100 100" style="width:100%;height:auto;display:block"'
                f' aria-hidden="true">'
                f'<rect x="10" y="10" width="{side}" height="{side}"'
                f' fill="none" stroke="var(--gg-color-sand)" stroke-width="6"/>'
                f'<rect x="10" y="10" width="{side}" height="{side}"'
                f' fill="none" stroke="{color}" stroke-width="6"'
                f' stroke-dasharray="{perim}" stroke-dashoffset="{perim - filled}"'
                f' class="gg-gauge__fill"'
                f' style="--gauge-perimeter:{perim};--gauge-target:{filled}"/>'
                f'</svg>'
                f'<div class="gg-gauge__value">{pct}%</div>'
                f'<div class="gg-gauge__label">{_esc(label)}</div>'
                f'</div>'
            )
        panels.append(
            f'<div class="gg-infographic-glycogen-panel">'
            f'<div class="gg-infographic-glycogen-title">{_esc(title_text)}</div>'
            f'<div class="gg-infographic-glycogen-gauges">{"".join(gauges)}</div>'
            f'<div class="gg-infographic-glycogen-summary">{_esc(summary)}</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-infographic-glycogen-compare">'
        f'{"".join(panels)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Glycogen Depletion: Fed vs. Unfed",
        takeaway="Without fueling, you hit empty by hour 4. With 75g/hr, you finish with reserves.",
    )


def render_macro_split(block: dict) -> str:
    """Carb/protein/fat progress bars for daily training nutrition.

    Uses data-animate="progress" with shimmer fills.
    """
    macros = [
        ("Carbohydrates", "55-65%", 60, "var(--gg-color-gold)",
         "Primary fuel source. 6-10g/kg body weight on training days."),
        ("Protein", "15-20%", 18, "var(--gg-color-teal)",
         "Muscle repair and adaptation. 1.6-2.2g/kg. Spread across meals."),
        ("Fat", "20-30%", 22, "var(--gg-color-secondary-brown)",
         "Essential for hormones and long-effort fat oxidation."),
    ]

    rows = []
    for i, (name, range_text, pct, color, tip) in enumerate(macros):
        rows.append(
            f'<div class="gg-bar-chart__row" style="--delay:{i * 150}ms">'
            f'<div class="gg-bar-chart__label">{_esc(name)}</div>'
            f'<div class="gg-bar-chart__track">'
            f'<div class="gg-bar-chart__fill" style="--w:{pct}%;background:{color}"'
            f' data-tooltip="{_esc(tip)}" tabindex="0">'
            f'<span class="gg-bar-chart__value">{_esc(range_text)}</span>'
            f'</div>'
            f'</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-bar-chart" data-animate="bar">'
        f'<div class="gg-bar-chart__body">{"".join(rows)}</div>'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Daily Macro Split for Endurance Athletes",
        takeaway="Carbs are king for gravel. Don\u2019t fear them \u2014 they\u2019re your primary fuel.",
    )


def render_calorie_burn(block: dict) -> str:
    """Hourly calorie burn waterfall chart for an 8-hour race.

    Uses data-animate="bar" with growing columns from bottom.
    """
    # (hour, calories_burned, cumulative)
    hours = [
        ("Hr 1", 700, 700), ("Hr 2", 650, 1350), ("Hr 3", 600, 1950),
        ("Hr 4", 580, 2530), ("Hr 5", 550, 3080), ("Hr 6", 520, 3600),
        ("Hr 7", 500, 4100), ("Hr 8", 480, 4580),
    ]

    max_cal = 750  # max single-hour burn for scaling
    rows = []
    for i, (label, cal, cumul) in enumerate(hours):
        pct = int((cal / max_cal) * 100)
        tip = f"{label}: {cal} cal burned, {cumul} cumulative"
        rows.append(
            f'<div class="gg-waterfall-chart__col" style="--delay:{i * 100}ms"'
            f' data-tooltip="{_esc(tip)}" tabindex="0">'
            f'<div class="gg-waterfall-chart__bar"'
            f' style="--h:{pct}%"></div>'
            f'<div class="gg-waterfall-chart__value">{cal}</div>'
            f'<div class="gg-waterfall-chart__label">{_esc(label)}</div>'
            f'</div>'
        )

    inner = (
        f'<div class="gg-waterfall-chart" data-animate="bar">'
        f'<div class="gg-waterfall-chart__grid">{"".join(rows)}</div>'
        f'<div class="gg-waterfall-chart__total">'
        f'<span class="gg-waterfall-chart__total-label">Total</span>'
        f'<span class="gg-waterfall-chart__total-value"'
        f' data-target="4580">4,580 cal</span>'
        f'</div>'
        f'</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Calorie Burn by Hour: The Energy Deficit",
        takeaway="You burn 4,500+ calories but can only absorb ~2,400 from food. The deficit is inevitable \u2014 manage it.",
    )


# ══════════════════════════════════════════════════════════════
# Phase 3: Ch7 Renderers (Race Week)
# ══════════════════════════════════════════════════════════════


def render_weather_matrix(block: dict) -> str:
    """Wind x temperature performance impact matrix (5x5 heatmap grid).

    Uses data-animate="fade-stagger" with intensity classes and data-tooltip.
    """
    temps = ["<50\u00b0F", "50-60\u00b0F", "60-75\u00b0F", "75-90\u00b0F", ">90\u00b0F"]
    winds = ["Calm", "5-10 mph", "10-15 mph", "15-20 mph", "20+ mph"]

    # Impact matrix: 0=optimal, 1=minor, 2=moderate, 3=significant, 4=severe, 5=dangerous
    # [temp_idx][wind_idx]
    matrix = [
        [3, 3, 4, 5, 5],  # <50
        [1, 2, 3, 4, 4],  # 50-60
        [0, 0, 1, 2, 3],  # 60-75 (ideal)
        [1, 2, 2, 3, 4],  # 75-90
        [3, 4, 4, 5, 5],  # >90
    ]

    tips = [
        ["Cold + calm: manageable with layers", "Cold + light wind: wind chill factor",
         "Cold + moderate wind: significant chill, numbness risk",
         "Cold + strong wind: hypothermia risk, avoid if possible",
         "Cold + extreme wind: dangerous conditions"],
        ["Cool + calm: dress warmly at start", "Cool + light wind: arm warmers may suffice",
         "Cool + moderate wind: headwind sections drain energy",
         "Cool + strong wind: major energy tax on exposed sections",
         "Cool + extreme wind: crosswinds dangerous on descents"],
        ["Ideal + calm: optimal racing conditions", "Ideal + light wind: near-perfect",
         "Ideal + moderate wind: minor impact, draft when possible",
         "Ideal + strong wind: moderate energy cost, plan for headwinds",
         "Ideal + extreme wind: significant impact despite good temp"],
        ["Warm + calm: hydration critical", "Warm + light wind: some cooling effect",
         "Warm + moderate wind: hot wind = worse than calm",
         "Warm + strong wind: dehydration risk accelerates",
         "Warm + extreme wind: severe conditions, reduce pace 15%"],
        ["Hot + calm: dangerous heat stress", "Hot + any wind: false cooling, dehydration critical",
         "Hot + moderate wind: heat illness risk high",
         "Hot + strong wind: extreme conditions, DNS consideration",
         "Hot + extreme wind: do not race"],
    ]

    cells = []
    # Header row
    cells.append('<div class="gg-heatmap__cell gg-heatmap__cell--header"></div>')
    for wind in winds:
        cells.append(
            f'<div class="gg-heatmap__cell gg-heatmap__cell--header">{_esc(wind)}</div>'
        )

    # Data rows
    for t_idx, temp in enumerate(temps):
        cells.append(
            f'<div class="gg-heatmap__cell gg-heatmap__cell--row-label">{_esc(temp)}</div>'
        )
        for w_idx, wind in enumerate(winds):
            level = matrix[t_idx][w_idx]
            tip = tips[t_idx][w_idx]
            cells.append(
                f'<div class="gg-heatmap__cell" data-v="{level}"'
                f' data-tooltip="{_esc(tip)}" tabindex="0">'
                f'{level}</div>'
            )

    n_cols = len(winds) + 1
    inner = (
        f'<div class="gg-heatmap" data-animate="fade-stagger"'
        f' style="--cols:{n_cols}">'
        f'{"".join(cells)}</div>'
    )
    return _figure_wrap(
        inner, block.get("caption", ""), block.get("layout", "inline"),
        block.get("asset_id", ""), block.get("alt", ""),
        title="Weather Impact Matrix: Wind \u00d7 Temperature",
        takeaway="60-75\u00b0F with light wind is the sweet spot. Anything beyond that costs watts.",
    )


# ══════════════════════════════════════════════════════════════
# Dispatch Map
# ══════════════════════════════════════════════════════════════


INFOGRAPHIC_RENDERERS = {
    "ch1-gear-essentials": render_gear_grid,
    "ch1-rider-grid": render_rider_categories,
    "ch1-hierarchy-of-speed": render_hierarchy_pyramid,
    "ch1-gear-weight": render_gear_weight,
    "ch2-scoring-dimensions": render_scoring_dimensions,
    "ch2-tier-distribution": render_tier_distribution,
    "ch2-course-profile": render_course_profile,
    "ch2-field-scatter": render_field_scatter,
    "ch2-race-table": render_race_table,
    "ch3-supercompensation": render_supercompensation,
    "ch3-zone-spectrum": render_zone_spectrum,
    "ch3-pmc-chart": render_pmc_chart,
    "ch3-training-phases": render_training_phases,
    "ch3-power-duration": render_power_duration,
    "ch3-gantt-season": render_gantt_season,
    "ch3-before-after": render_before_after,
    "ch4-execution-gap": render_execution_gap,
    "ch4-traffic-light": render_traffic_light,
    "ch4-recovery-dash": render_recovery_dash,
    "ch4-sleep-debt": render_sleep_debt,
    "ch5-fueling-timeline": render_fueling_timeline,
    "ch5-bonk-math": render_bonk_math,
    "ch5-hydration-calc": render_hydration_calc,
    "ch5-glycogen-gauge": render_glycogen_gauge,
    "ch5-macro-split": render_macro_split,
    "ch5-calorie-burn": render_calorie_burn,
    "ch6-three-acts": render_three_acts,
    "ch6-psych-phases": render_psych_phases,
    "ch7-race-week-countdown": render_race_week_countdown,
    "ch7-weather-matrix": render_weather_matrix,
}
