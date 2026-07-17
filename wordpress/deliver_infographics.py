#!/usr/bin/env python3
"""
Inline SVG/HTML infographic renderers for the Deliver course
(sport psychology for endurance athletes).

8 renderers producing clean, self-contained SVG diagrams:
- Yerkes-Dodson inverted U curve
- Identity Tree (self-concept layers)
- Flow Channel (Csikszentmihalyi)
- Attention Matrix (Nideffer 2x2)
- Bandura's Four Sources of Self-Efficacy
- SDT Three Needs (Deci & Ryan)
- Grit Stack (5-layer execution protocol)
- 4 C's of Mental Toughness (Clough)

Design system: "Clean Pro"
  - Background: #ffffff
  - Headlines: #1a1a1a
  - Body text: #4a4a4a
  - Muted: #767676
  - Accent: #4ECDC4
  - Font: Inter
  - Border-radius: 4px
"""

import html as _html

# ── Design Tokens ──────────────────────────────────────────

_HEADLINE = "#1a1a1a"
_BODY = "#4a4a4a"
_MUTED = "#767676"
_ACCENT = "#4ECDC4"
_ACCENT_LIGHT = "#e0f7f5"
_BG = "#ffffff"
_BORDER = "#e0e0e0"
_FONT = "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
_RADIUS = "4px"


# ── Helpers ────────────────────────────────────────────────

def _esc(text) -> str:
    """HTML-escape a string."""
    return _html.escape(str(text)) if text else ""


def _figure_wrap(svg_html: str, block: dict) -> str:
    """Wrap SVG content in a <figure> with caption and accessibility."""
    alt = block.get("alt", "")
    caption = block.get("caption", "")
    asset_id = block.get("asset_id", "")

    aria = f' aria-label="{_esc(alt)}"' if alt else ""
    aid = f' data-asset-id="{_esc(asset_id)}"' if asset_id else ""

    cap_html = ""
    if caption:
        cap_html = (
            f'<figcaption style="font-family:{_FONT};font-size:14px;'
            f'color:{_MUTED};margin-top:12px;line-height:1.5;'
            f'text-align:center;max-width:600px;margin-left:auto;'
            f'margin-right:auto">{_esc(caption)}</figcaption>'
        )

    return (
        f'<figure role="figure"{aria}{aid} style="margin:32px auto;'
        f'padding:0;max-width:700px;text-align:center">'
        f'{svg_html}{cap_html}</figure>'
    )


def _svg_open(width: int, height: int) -> str:
    """Open an SVG tag with viewBox for fluid scaling."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {width} {height}" '
        f'role="img" aria-hidden="true" '
        f'style="width:100%;max-width:{width}px;height:auto;display:block;'
        f'margin:0 auto;background:{_BG}">'
    )


def _svg_close() -> str:
    return "</svg>"


# ── 1. Yerkes-Dodson ──────────────────────────────────────

def render_yerkes_dodson(block: dict) -> str:
    """Inverted U curve: arousal vs performance."""
    w, h = 660, 400
    ml, mr, mt, mb = 70, 40, 40, 70
    cw = w - ml - mr
    ch = h - mt - mb

    svg = [_svg_open(w, h)]

    # Background
    svg.append(f'<rect width="{w}" height="{h}" fill="{_BG}"/>')

    # Axes
    svg.append(
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ch}" '
        f'stroke="{_BORDER}" stroke-width="2"/>'
    )
    svg.append(
        f'<line x1="{ml}" y1="{mt + ch}" x2="{ml + cw}" y2="{mt + ch}" '
        f'stroke="{_BORDER}" stroke-width="2"/>'
    )

    # Axis labels
    svg.append(
        f'<text x="{ml + cw // 2}" y="{h - 12}" '
        f'text-anchor="middle" font-family="{_FONT}" '
        f'font-size="14" fill="{_BODY}" font-weight="600">Arousal</text>'
    )
    svg.append(
        f'<text x="16" y="{mt + ch // 2}" '
        f'text-anchor="middle" font-family="{_FONT}" '
        f'font-size="14" fill="{_BODY}" font-weight="600" '
        f'transform="rotate(-90,16,{mt + ch // 2})">Performance</text>'
    )

    # Inverted U curve using cubic bezier
    # Map across the chart area
    x0 = ml + 10
    x1 = ml + cw - 10
    y_base = mt + ch - 20  # low performance
    y_peak = mt + 30       # high performance
    mid_x = ml + cw // 2

    curve_path = (
        f'M {x0},{y_base} '
        f'C {x0 + cw * 0.15},{y_base - 20} '
        f'{mid_x - cw * 0.15},{y_peak} '
        f'{mid_x},{y_peak} '
        f'C {mid_x + cw * 0.15},{y_peak} '
        f'{x1 - cw * 0.15},{y_base - 20} '
        f'{x1},{y_base}'
    )

    # Fill under curve (subtle)
    svg.append(
        f'<path d="{curve_path} L {x1},{mt + ch} L {x0},{mt + ch} Z" '
        f'fill="{_ACCENT_LIGHT}" opacity="0.5"/>'
    )

    # Curve stroke
    svg.append(
        f'<path d="{curve_path}" '
        f'fill="none" stroke="{_ACCENT}" stroke-width="3" '
        f'stroke-linecap="round"/>'
    )

    # Peak marker
    svg.append(
        f'<circle cx="{mid_x}" cy="{y_peak}" r="5" fill="{_ACCENT}"/>'
    )

    # Zone labels
    zones = [
        (ml + cw * 0.15, y_base - 50, "Low Arousal", "(Boredom)"),
        (mid_x, y_peak - 24, "Optimal Zone", "(Peak)"),
        (ml + cw * 0.85, y_base - 50, "High Arousal", "(Anxiety)"),
    ]
    for zx, zy, label, sub in zones:
        svg.append(
            f'<text x="{zx}" y="{zy}" text-anchor="middle" '
            f'font-family="{_FONT}" font-size="13" '
            f'fill="{_HEADLINE}" font-weight="600">{_esc(label)}</text>'
        )
        svg.append(
            f'<text x="{zx}" y="{zy + 16}" text-anchor="middle" '
            f'font-family="{_FONT}" font-size="11" '
            f'fill="{_MUTED}">{_esc(sub)}</text>'
        )

    # Axis tick labels
    svg.append(
        f'<text x="{ml + 10}" y="{mt + ch + 20}" '
        f'font-family="{_FONT}" font-size="11" fill="{_MUTED}">Low</text>'
    )
    svg.append(
        f'<text x="{ml + cw - 10}" y="{mt + ch + 20}" '
        f'text-anchor="end" font-family="{_FONT}" font-size="11" '
        f'fill="{_MUTED}">High</text>'
    )
    svg.append(
        f'<text x="{ml - 8}" y="{mt + ch - 10}" text-anchor="end" '
        f'font-family="{_FONT}" font-size="11" fill="{_MUTED}">Low</text>'
    )
    svg.append(
        f'<text x="{ml - 8}" y="{mt + 10}" text-anchor="end" '
        f'font-family="{_FONT}" font-size="11" fill="{_MUTED}">High</text>'
    )

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block)


# ── 2. Identity Tree ──────────────────────────────────────

def render_identity_tree(block: dict) -> str:
    """Tree metaphor: roots, trunk, branches, leaves."""
    w, h = 660, 520
    cx = w // 2

    svg = [_svg_open(w, h)]
    svg.append(f'<rect width="{w}" height="{h}" fill="{_BG}"/>')

    # Ground line
    ground_y = 340
    svg.append(
        f'<line x1="100" y1="{ground_y}" x2="560" y2="{ground_y}" '
        f'stroke="{_BORDER}" stroke-width="2" stroke-dasharray="6 3"/>'
    )

    # Roots (below ground)
    root_paths = [
        f'M {cx},{ground_y} C {cx - 40},{ground_y + 40} {cx - 100},{ground_y + 60} {cx - 130},{ground_y + 90}',
        f'M {cx},{ground_y} C {cx + 10},{ground_y + 50} {cx - 30},{ground_y + 80} {cx - 20},{ground_y + 100}',
        f'M {cx},{ground_y} C {cx + 40},{ground_y + 40} {cx + 100},{ground_y + 60} {cx + 130},{ground_y + 90}',
        f'M {cx},{ground_y} C {cx - 10},{ground_y + 50} {cx + 30},{ground_y + 80} {cx + 20},{ground_y + 100}',
    ]
    for rp in root_paths:
        svg.append(
            f'<path d="{rp}" fill="none" stroke="#8B7355" '
            f'stroke-width="3" stroke-linecap="round" opacity="0.6"/>'
        )

    # Trunk
    trunk_w = 40
    trunk_top = 200
    svg.append(
        f'<rect x="{cx - trunk_w // 2}" y="{trunk_top}" '
        f'width="{trunk_w}" height="{ground_y - trunk_top}" '
        f'fill="#8B7355" rx="{_RADIUS}"/>'
    )

    # Branches (left and right)
    branch_paths = [
        f'M {cx},{trunk_top + 40} C {cx - 30},{trunk_top + 20} {cx - 80},{trunk_top - 10} {cx - 120},{trunk_top - 20}',
        f'M {cx},{trunk_top + 40} C {cx + 30},{trunk_top + 20} {cx + 80},{trunk_top - 10} {cx + 120},{trunk_top - 20}',
        f'M {cx},{trunk_top + 80} C {cx - 40},{trunk_top + 50} {cx - 100},{trunk_top + 30} {cx - 140},{trunk_top + 20}',
        f'M {cx},{trunk_top + 80} C {cx + 40},{trunk_top + 50} {cx + 100},{trunk_top + 30} {cx + 140},{trunk_top + 20}',
    ]
    for bp in branch_paths:
        svg.append(
            f'<path d="{bp}" fill="none" stroke="#8B7355" '
            f'stroke-width="3" stroke-linecap="round"/>'
        )

    # Canopy (leaves) — a cluster of circles
    leaf_positions = [
        (cx, trunk_top - 50, 55),
        (cx - 70, trunk_top - 20, 45),
        (cx + 70, trunk_top - 20, 45),
        (cx - 110, trunk_top + 10, 35),
        (cx + 110, trunk_top + 10, 35),
        (cx - 40, trunk_top - 40, 40),
        (cx + 40, trunk_top - 40, 40),
    ]
    for lx, ly, lr in leaf_positions:
        svg.append(
            f'<circle cx="{lx}" cy="{ly}" r="{lr}" '
            f'fill="{_ACCENT}" opacity="0.25"/>'
        )

    # Labels with connector lines
    layers = [
        ("Self-Efficacy", "(Situational beliefs)", cx, trunk_top - 70, 510, trunk_top - 60),
        ("Self-Esteem", "(Domain-specific)", cx - 120, trunk_top + 0, 510, trunk_top + 10),
        ("Self-Worth", "(Fundamental value)", cx, trunk_top + 80, 510, trunk_top + 80 + 50),
        ("Self-Concept", "(Core identity — roots)", cx, ground_y + 60, 510, ground_y + 60),
    ]

    for label, sub, _lx, _ly, label_x, label_y in layers:
        # Label on right side
        svg.append(
            f'<text x="{label_x}" y="{label_y}" text-anchor="start" '
            f'font-family="{_FONT}" font-size="14" '
            f'fill="{_HEADLINE}" font-weight="600">{_esc(label)}</text>'
        )
        svg.append(
            f'<text x="{label_x}" y="{label_y + 16}" text-anchor="start" '
            f'font-family="{_FONT}" font-size="11" '
            f'fill="{_MUTED}">{_esc(sub)}</text>'
        )

    # Left-side labels for the tree parts
    tree_parts = [
        ("Leaves", 100, trunk_top - 50),
        ("Branches", 80, trunk_top + 10),
        ("Trunk", 100, trunk_top + 80),
        ("Roots", 100, ground_y + 60),
    ]
    for part, px, py in tree_parts:
        svg.append(
            f'<text x="{px}" y="{py}" text-anchor="end" '
            f'font-family="{_FONT}" font-size="13" '
            f'fill="{_ACCENT}" font-weight="600">{_esc(part)}</text>'
        )

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block)


# ── 3. Flow Channel ───────────────────────────────────────

def render_flow_channel(block: dict) -> str:
    """Csikszentmihalyi's flow channel: challenge vs perceived skill."""
    w, h = 660, 520
    ml, mr, mt, mb = 80, 50, 50, 70
    cw = w - ml - mr
    ch = h - mt - mb

    svg = [_svg_open(w, h)]
    svg.append(f'<rect width="{w}" height="{h}" fill="{_BG}"/>')

    # Axes
    svg.append(
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt + ch}" '
        f'stroke="{_BORDER}" stroke-width="2"/>'
    )
    svg.append(
        f'<line x1="{ml}" y1="{mt + ch}" x2="{ml + cw}" y2="{mt + ch}" '
        f'stroke="{_BORDER}" stroke-width="2"/>'
    )

    # Axis labels
    svg.append(
        f'<text x="{ml + cw // 2}" y="{h - 12}" '
        f'text-anchor="middle" font-family="{_FONT}" '
        f'font-size="14" fill="{_BODY}" font-weight="600">Perceived Skill</text>'
    )
    svg.append(
        f'<text x="18" y="{mt + ch // 2}" '
        f'text-anchor="middle" font-family="{_FONT}" '
        f'font-size="14" fill="{_BODY}" font-weight="600" '
        f'transform="rotate(-90,18,{mt + ch // 2})">Challenge</text>'
    )

    # Low/High labels
    svg.append(
        f'<text x="{ml + 10}" y="{mt + ch + 20}" '
        f'font-family="{_FONT}" font-size="11" fill="{_MUTED}">Low</text>'
    )
    svg.append(
        f'<text x="{ml + cw - 10}" y="{mt + ch + 20}" text-anchor="end" '
        f'font-family="{_FONT}" font-size="11" fill="{_MUTED}">High</text>'
    )
    svg.append(
        f'<text x="{ml - 8}" y="{mt + ch - 5}" text-anchor="end" '
        f'font-family="{_FONT}" font-size="11" fill="{_MUTED}">Low</text>'
    )
    svg.append(
        f'<text x="{ml - 8}" y="{mt + 10}" text-anchor="end" '
        f'font-family="{_FONT}" font-size="11" fill="{_MUTED}">High</text>'
    )

    # Flow channel — diagonal band from bottom-left to top-right
    band_w = 70  # half-width of the band perpendicular to diagonal
    # The channel runs from (ml, mt+ch) to (ml+cw, mt)
    # Offset perpendicular to that diagonal
    import math
    diag_angle = math.atan2(ch, cw)
    dx = band_w * math.sin(diag_angle)
    dy = band_w * math.cos(diag_angle)

    # Flow band polygon
    x0, y0 = ml + 10, mt + ch - 10
    x1, y1 = ml + cw - 10, mt + 10
    svg.append(
        f'<polygon points="'
        f'{x0 - dx},{y0 - dy} '
        f'{x1 - dx},{y1 - dy} '
        f'{x1 + dx},{y1 + dy} '
        f'{x0 + dx},{y0 + dy}" '
        f'fill="{_ACCENT}" opacity="0.15"/>'
    )

    # Flow channel center line
    svg.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" '
        f'stroke="{_ACCENT}" stroke-width="2.5" stroke-dasharray="8 4"/>'
    )

    # Zone labels
    # Anxiety zone — upper-left area (high challenge, low skill)
    anxiety_x = ml + cw * 0.25
    anxiety_y = mt + ch * 0.22
    svg.append(
        f'<text x="{anxiety_x}" y="{anxiety_y}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="18" '
        f'fill="{_HEADLINE}" font-weight="700">Anxiety</text>'
    )
    svg.append(
        f'<text x="{anxiety_x}" y="{anxiety_y + 18}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" '
        f'fill="{_MUTED}">Challenge exceeds skill</text>'
    )

    # Flow label — center of diagonal
    flow_x = ml + cw * 0.5
    flow_y = mt + ch * 0.5
    svg.append(
        f'<text x="{flow_x}" y="{flow_y - 6}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="18" '
        f'fill="{_ACCENT}" font-weight="700">Flow</text>'
    )
    svg.append(
        f'<text x="{flow_x}" y="{flow_y + 12}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" '
        f'fill="{_BODY}">Challenge matches skill</text>'
    )

    # Boredom zone — lower-right area (low challenge, high skill)
    boredom_x = ml + cw * 0.75
    boredom_y = mt + ch * 0.78
    svg.append(
        f'<text x="{boredom_x}" y="{boredom_y}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="18" '
        f'fill="{_HEADLINE}" font-weight="700">Boredom</text>'
    )
    svg.append(
        f'<text x="{boredom_x}" y="{boredom_y + 18}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" '
        f'fill="{_MUTED}">Skill exceeds challenge</text>'
    )

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block)


# ── 4. Attention Matrix ───────────────────────────────────

def render_attention_matrix(block: dict) -> str:
    """Nideffer's 2x2 attention model: Broad/Narrow x Internal/External."""
    w, h = 660, 500
    svg = [_svg_open(w, h)]
    svg.append(f'<rect width="{w}" height="{h}" fill="{_BG}"/>')

    # Grid dimensions
    gx, gy = 130, 90
    gw, gh = 400, 340
    cell_w = gw // 2
    cell_h = gh // 2

    quadrants = [
        # (col, row, title, example, fill_opacity)
        (0, 0, "Broad-External", "Reading the peloton,\nscanning terrain ahead", 0.08),
        (1, 0, "Broad-Internal", "Analyzing race strategy,\nassessing overall body state", 0.12),
        (0, 1, "Narrow-External", "Watching the wheel ahead,\nfocusing on a line choice", 0.12),
        (1, 1, "Narrow-Internal", "Monitoring cadence,\ncontrolling breathing", 0.08),
    ]

    for col, row, title, example, opacity in quadrants:
        qx = gx + col * cell_w
        qy = gy + row * cell_h

        # Cell background
        svg.append(
            f'<rect x="{qx}" y="{qy}" width="{cell_w}" height="{cell_h}" '
            f'fill="{_ACCENT}" opacity="{opacity}" rx="{_RADIUS}"/>'
        )
        # Cell border
        svg.append(
            f'<rect x="{qx}" y="{qy}" width="{cell_w}" height="{cell_h}" '
            f'fill="none" stroke="{_BORDER}" stroke-width="1.5" rx="{_RADIUS}"/>'
        )

        # Title
        svg.append(
            f'<text x="{qx + cell_w // 2}" y="{qy + 36}" '
            f'text-anchor="middle" font-family="{_FONT}" '
            f'font-size="14" fill="{_HEADLINE}" font-weight="700">'
            f'{_esc(title)}</text>'
        )

        # Example lines
        lines = example.split("\n")
        for i, line in enumerate(lines):
            svg.append(
                f'<text x="{qx + cell_w // 2}" y="{qy + 62 + i * 18}" '
                f'text-anchor="middle" font-family="{_FONT}" '
                f'font-size="12" fill="{_BODY}">{_esc(line)}</text>'
            )

    # Axis labels
    # Top: External / Internal
    svg.append(
        f'<text x="{gx + cell_w // 2}" y="{gy - 16}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="13" fill="{_ACCENT}" '
        f'font-weight="600">External</text>'
    )
    svg.append(
        f'<text x="{gx + cell_w + cell_w // 2}" y="{gy - 16}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="13" fill="{_ACCENT}" '
        f'font-weight="600">Internal</text>'
    )

    # Left: Broad / Narrow
    svg.append(
        f'<text x="{gx - 16}" y="{gy + cell_h // 2}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="13" fill="{_ACCENT}" '
        f'font-weight="600" transform="rotate(-90,{gx - 16},{gy + cell_h // 2})">'
        f'Broad</text>'
    )
    svg.append(
        f'<text x="{gx - 16}" y="{gy + cell_h + cell_h // 2}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="13" fill="{_ACCENT}" '
        f'font-weight="600" transform="rotate(-90,{gx - 16},{gy + cell_h + cell_h // 2})">'
        f'Narrow</text>'
    )

    # Title
    svg.append(
        f'<text x="{w // 2}" y="36" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="16" '
        f'fill="{_HEADLINE}" font-weight="700">'
        f"Nideffer's Attention Model</text>"
    )

    # Footer note
    svg.append(
        f'<text x="{w // 2}" y="{h - 20}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" fill="{_MUTED}">'
        f'Each quadrant is useful. The skill is switching between them on demand.</text>'
    )

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block)


# ── 5. Bandura's Four Sources ─────────────────────────────

def render_bandura_four_sources(block: dict) -> str:
    """Four sources of self-efficacy as a ranked pyramid."""
    w, h = 660, 440
    svg = [_svg_open(w, h)]
    svg.append(f'<rect width="{w}" height="{h}" fill="{_BG}"/>')

    # Title
    svg.append(
        f'<text x="{w // 2}" y="36" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="16" '
        f'fill="{_HEADLINE}" font-weight="700">'
        f'Sources of Self-Efficacy</text>'
    )
    svg.append(
        f'<text x="{w // 2}" y="54" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" fill="{_MUTED}">'
        f'Ranked by impact (Bandura, 1977)</text>'
    )

    # Pyramid layers — widest at bottom (strongest source), narrowest at top
    layers = [
        ("Past Performance", "The gold standard \u2014 you did it before", 1.0),
        ("Vicarious Experience", "Watching someone like you succeed", 0.78),
        ("Verbal Persuasion", "Coaching, encouragement, self-talk", 0.56),
        ("Physiological State", "Heart rate, breathing, butterflies", 0.38),
    ]

    py_top = 80
    py_bot = 400
    layer_h = (py_bot - py_top) / len(layers)
    cx = w // 2
    max_half_w = 260

    for i, (label, desc, width_frac) in enumerate(layers):
        # Pyramid: bottom layer is widest
        idx = len(layers) - 1 - i  # reverse so index 0 = top
        y = py_top + idx * layer_h
        half_w_top = max_half_w * layers[idx]["width_frac"] if isinstance(layers[idx], dict) else max_half_w * (1.0 - idx * 0.20)
        half_w_bot = max_half_w * (1.0 - idx * 0.20)

        # Actually, let's keep it simpler — stacked horizontal bars
        # widest at bottom
        bar_y = py_top + i * layer_h
        bar_half_w = max_half_w * width_frac
        bar_h = layer_h - 8

        # Opacity gradient: strongest = most saturated
        opacity = 0.12 + (1.0 - i * 0.22) * 0.20

        svg.append(
            f'<rect x="{cx - bar_half_w}" y="{bar_y}" '
            f'width="{bar_half_w * 2}" height="{bar_h}" '
            f'fill="{_ACCENT}" opacity="{opacity:.2f}" '
            f'rx="{_RADIUS}" stroke="{_ACCENT}" stroke-width="1.5"/>'
        )

        # Rank number
        svg.append(
            f'<text x="{cx - bar_half_w + 16}" y="{bar_y + bar_h // 2 + 5}" '
            f'font-family="{_FONT}" font-size="20" '
            f'fill="{_ACCENT}" font-weight="700">{i + 1}</text>'
        )

        # Label
        svg.append(
            f'<text x="{cx}" y="{bar_y + bar_h // 2 - 2}" '
            f'text-anchor="middle" font-family="{_FONT}" '
            f'font-size="15" fill="{_HEADLINE}" font-weight="600">'
            f'{_esc(label)}</text>'
        )
        # Description
        svg.append(
            f'<text x="{cx}" y="{bar_y + bar_h // 2 + 16}" '
            f'text-anchor="middle" font-family="{_FONT}" '
            f'font-size="12" fill="{_BODY}">{_esc(desc)}</text>'
        )

    # Impact arrow on the left
    arrow_x = cx - max_half_w - 40
    svg.append(
        f'<line x1="{arrow_x}" y1="{py_bot - 20}" '
        f'x2="{arrow_x}" y2="{py_top + 20}" '
        f'stroke="{_MUTED}" stroke-width="1.5" marker-end="url(#arrowUp)"/>'
    )
    svg.append(
        f'<defs><marker id="arrowUp" viewBox="0 0 10 10" refX="5" refY="0" '
        f'markerWidth="6" markerHeight="6" orient="auto">'
        f'<path d="M0,10 L5,0 L10,10" fill="{_MUTED}"/></marker></defs>'
    )
    svg.append(
        f'<text x="{arrow_x}" y="{py_top + py_bot // 2 + 60}" '
        f'text-anchor="middle" font-family="{_FONT}" font-size="11" '
        f'fill="{_MUTED}" font-weight="600" '
        f'transform="rotate(-90,{arrow_x},{(py_top + py_bot) // 2})">'
        f'Increasing Impact</text>'
    )

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block)


# ── 6. SDT Three Needs ────────────────────────────────────

def render_sdt_three_needs(block: dict) -> str:
    """Self-Determination Theory: Autonomy, Competence, Relatedness."""
    w, h = 660, 440
    svg = [_svg_open(w, h)]
    svg.append(f'<rect width="{w}" height="{h}" fill="{_BG}"/>')

    # Title
    svg.append(
        f'<text x="{w // 2}" y="36" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="16" '
        f'fill="{_HEADLINE}" font-weight="700">'
        f'Self-Determination Theory</text>'
    )
    svg.append(
        f'<text x="{w // 2}" y="54" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" fill="{_MUTED}">'
        f'Three Basic Psychological Needs (Deci &amp; Ryan)</text>'
    )

    # Three overlapping circles in a Venn-like arrangement
    cx = w // 2
    cy = 230
    r = 110
    spread = 85  # distance from center to each circle center

    import math
    needs = [
        (-120, "Autonomy", "I chose this plan"),
        (0, "Competence", "I'm getting better"),
        (120, "Relatedness", "I'm not alone in this"),
    ]

    # Draw circles
    for angle_deg, label, desc in needs:
        angle_rad = math.radians(angle_deg - 90)  # -90 so first is at top
        nx = cx + spread * math.cos(angle_rad)
        ny = cy + spread * math.sin(angle_rad)

        # Circle fill
        svg.append(
            f'<circle cx="{nx:.0f}" cy="{ny:.0f}" r="{r}" '
            f'fill="{_ACCENT}" opacity="0.1" '
            f'stroke="{_ACCENT}" stroke-width="2"/>'
        )

    # Labels (drawn after circles so they're on top)
    label_offsets = [
        (-120, -30),  # Autonomy — pushed up from center
        (0, 0),       # Competence — pushed down-right
        (120, 0),     # Relatedness — pushed down-left
    ]

    for (angle_deg, label, desc), (_, extra_y) in zip(needs, label_offsets):
        angle_rad = math.radians(angle_deg - 90)
        # Push label further out from center
        label_dist = spread + 20
        nx = cx + label_dist * math.cos(angle_rad)
        ny = cy + label_dist * math.sin(angle_rad) + extra_y

        svg.append(
            f'<text x="{nx:.0f}" y="{ny:.0f}" text-anchor="middle" '
            f'font-family="{_FONT}" font-size="16" '
            f'fill="{_HEADLINE}" font-weight="700">{_esc(label)}</text>'
        )
        svg.append(
            f'<text x="{nx:.0f}" y="{ny + 18:.0f}" text-anchor="middle" '
            f'font-family="{_FONT}" font-size="12" '
            f'fill="{_BODY}">{_esc(desc)}</text>'
        )

    # Center label — where all three overlap
    svg.append(
        f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="13" '
        f'fill="{_ACCENT}" font-weight="700">Intrinsic</text>'
    )
    svg.append(
        f'<text x="{cx}" y="{cy + 19}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="13" '
        f'fill="{_ACCENT}" font-weight="700">Motivation</text>'
    )

    # Footer
    svg.append(
        f'<text x="{cx}" y="{h - 20}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" fill="{_MUTED}">'
        f'When all three needs are met, motivation is self-sustaining.</text>'
    )

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block)


# ── 7. Grit Stack ─────────────────────────────────────────

def render_grit_stack(block: dict) -> str:
    """Five execution layers stacked bottom to top."""
    w, h = 660, 460
    svg = [_svg_open(w, h)]
    svg.append(f'<rect width="{w}" height="{h}" fill="{_BG}"/>')

    # Title
    svg.append(
        f'<text x="{w // 2}" y="36" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="16" '
        f'fill="{_HEADLINE}" font-weight="700">'
        f'The Grit Stack</text>'
    )
    svg.append(
        f'<text x="{w // 2}" y="54" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" fill="{_MUTED}">'
        f'Five steps. In order. Every time.</text>'
    )

    layers = [
        ("5", "Segment", "Break the remaining distance into chunks"),
        ("4", "Execute", "Do the next right thing \u2014 nothing more"),
        ("3", "Reframe", "Pain is data, not danger"),
        ("2", "Detach", "Step outside the moment \u2014 observe, don't react"),
        ("1", "Breathe", "4-count in, 6-count out \u2014 reset the nervous system"),
    ]

    cx = w // 2
    stack_top = 80
    stack_bot = 430
    layer_count = len(layers)
    layer_h = (stack_bot - stack_top) / layer_count
    max_w = 500

    for i, (num, label, desc) in enumerate(layers):
        y = stack_top + i * layer_h
        bar_h = layer_h - 6

        # Graduated accent opacity — top layer is strongest
        opacity = 0.30 - i * 0.04

        svg.append(
            f'<rect x="{cx - max_w // 2}" y="{y}" '
            f'width="{max_w}" height="{bar_h}" '
            f'fill="{_ACCENT}" opacity="{opacity:.2f}" '
            f'rx="{_RADIUS}" stroke="{_ACCENT}" stroke-width="1.5"/>'
        )

        # Step number
        svg.append(
            f'<text x="{cx - max_w // 2 + 24}" y="{y + bar_h // 2 + 6}" '
            f'text-anchor="middle" font-family="{_FONT}" '
            f'font-size="22" fill="{_ACCENT}" font-weight="700">{num}</text>'
        )

        # Label
        svg.append(
            f'<text x="{cx - max_w // 2 + 55}" y="{y + bar_h // 2 - 2}" '
            f'font-family="{_FONT}" font-size="16" '
            f'fill="{_HEADLINE}" font-weight="700">{_esc(label)}</text>'
        )

        # Description
        svg.append(
            f'<text x="{cx - max_w // 2 + 55}" y="{y + bar_h // 2 + 16}" '
            f'font-family="{_FONT}" font-size="12" '
            f'fill="{_BODY}">{_esc(desc)}</text>'
        )

    # Upward arrow on the right
    arrow_x = cx + max_w // 2 + 30
    svg.append(
        f'<line x1="{arrow_x}" y1="{stack_bot - 10}" '
        f'x2="{arrow_x}" y2="{stack_top + 10}" '
        f'stroke="{_MUTED}" stroke-width="1.5" '
        f'marker-end="url(#gritArrow)"/>'
    )
    svg.append(
        f'<defs><marker id="gritArrow" viewBox="0 0 10 10" refX="5" refY="0" '
        f'markerWidth="6" markerHeight="6" orient="auto">'
        f'<path d="M0,10 L5,0 L10,10" fill="{_MUTED}"/></marker></defs>'
    )
    svg.append(
        f'<text x="{arrow_x}" y="{(stack_top + stack_bot) // 2}" '
        f'text-anchor="middle" font-family="{_FONT}" font-size="11" '
        f'fill="{_MUTED}" font-weight="600" '
        f'transform="rotate(-90,{arrow_x},{(stack_top + stack_bot) // 2})">'
        f'Execution Order</text>'
    )

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block)


# ── 8. 4 C's of Mental Toughness ─────────────────────────

def render_4cs_mental_toughness(block: dict) -> str:
    """Clough's 4 C's: Control, Commitment, Challenge, Confidence — diamond layout."""
    w, h = 660, 500
    svg = [_svg_open(w, h)]
    svg.append(f'<rect width="{w}" height="{h}" fill="{_BG}"/>')

    cx, cy = w // 2, 260
    spread = 130  # distance from center to each node

    # Four nodes in diamond/compass layout
    nodes = [
        (cx, cy - spread, "Control", "Life control &\nemotional control"),          # top
        (cx + spread + 30, cy, "Commitment", "Goal-setting &\nachievement drive"),  # right
        (cx, cy + spread, "Challenge", "Risk orientation &\nlearning from setbacks"),  # bottom
        (cx - spread - 30, cy, "Confidence", "Self-belief &\ninterpersonal confidence"),  # left
    ]

    # Connection lines from center to each node
    for nx, ny, _label, _desc in nodes:
        svg.append(
            f'<line x1="{cx}" y1="{cy}" x2="{nx}" y2="{ny}" '
            f'stroke="{_BORDER}" stroke-width="1.5"/>'
        )

    # Diamond outline connecting the four nodes
    pts = " ".join(f"{nx},{ny}" for nx, ny, _, _ in nodes)
    svg.append(
        f'<polygon points="{pts}" fill="none" '
        f'stroke="{_ACCENT}" stroke-width="1.5" opacity="0.4"/>'
    )

    # Center hub
    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="36" '
        f'fill="{_ACCENT}" opacity="0.15" '
        f'stroke="{_ACCENT}" stroke-width="2"/>'
    )
    svg.append(
        f'<text x="{cx}" y="{cy - 4}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" '
        f'fill="{_ACCENT}" font-weight="700">Self-</text>'
    )
    svg.append(
        f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" '
        f'fill="{_ACCENT}" font-weight="700">Belief</text>'
    )

    # Node circles and labels
    for nx, ny, label, desc in nodes:
        svg.append(
            f'<circle cx="{nx}" cy="{ny}" r="8" '
            f'fill="{_ACCENT}"/>'
        )

        # Position label based on location relative to center
        if ny < cy:  # top
            ty = ny - 22
        elif ny > cy:  # bottom
            ty = ny + 30
        else:
            ty = ny - 22

        svg.append(
            f'<text x="{nx}" y="{ty}" text-anchor="middle" '
            f'font-family="{_FONT}" font-size="16" '
            f'fill="{_HEADLINE}" font-weight="700">{_esc(label)}</text>'
        )

        # Description lines
        desc_lines = desc.split("\n")
        for j, dl in enumerate(desc_lines):
            dy = ty + 16 + j * 15
            # For bottom node, push desc further down
            if ny > cy:
                dy = ty + 16 + j * 15
            svg.append(
                f'<text x="{nx}" y="{dy}" text-anchor="middle" '
                f'font-family="{_FONT}" font-size="11" '
                f'fill="{_BODY}">{_esc(dl)}</text>'
            )

    # Title
    svg.append(
        f'<text x="{cx}" y="36" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="16" '
        f'fill="{_HEADLINE}" font-weight="700">'
        f"The 4 C's of Mental Toughness</text>"
    )
    svg.append(
        f'<text x="{cx}" y="54" text-anchor="middle" '
        f'font-family="{_FONT}" font-size="12" fill="{_MUTED}">'
        f'Clough &amp; Strycharczyk (2012)</text>'
    )

    svg.append(_svg_close())
    return _figure_wrap("".join(svg), block)


# ══════════════════════════════════════════════════════════════
# Public API — map asset_id → render function
# ══════════════════════════════════════════════════════════════

DELIVER_INFOGRAPHIC_RENDERERS = {
    "yerkes-dodson": render_yerkes_dodson,
    "identity-tree": render_identity_tree,
    "flow-channel": render_flow_channel,
    "attention-matrix": render_attention_matrix,
    "bandura-four-sources": render_bandura_four_sources,
    "sdt-three-needs": render_sdt_three_needs,
    "grit-stack": render_grit_stack,
    "4cs-mental-toughness": render_4cs_mental_toughness,
}
