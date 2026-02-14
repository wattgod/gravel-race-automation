"""Performance Management Chart (CTL / ATL / TSB) — 12-week training load."""
import math
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    LIGHT_GOLD, WARM_BROWN, ERROR_RED, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE,
)

BASE_WIDTH = 1600


def _generate_training_data():
    """Generate realistic 12-week CTL/ATL/TSB data."""
    weeks = list(range(1, 13))

    # CTL: slow steady rise from ~40 to ~75, with small dips for recovery weeks
    ctl = [40, 43, 47, 44, 49, 54, 58, 55, 61, 65, 62, 58]

    # ATL: volatile, spikes on hard weeks, drops on recovery
    atl = [35, 50, 55, 30, 48, 60, 65, 35, 55, 70, 45, 30]

    # TSB: CTL - ATL
    tsb = [c - a for c, a in zip(ctl, atl)]

    return weeks, ctl, atl, tsb


def render(width: int = 1600, height: int = 600) -> Image.Image:
    """Render a Performance Management Chart."""
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_label = load_font(bold=True, size=int(15 * s))
    font_sm = load_font(bold=False, size=int(13 * s))
    font_xs = load_font(bold=False, size=int(11 * s))

    pad = int(50 * s)
    weeks, ctl, atl, tsb = _generate_training_data()

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "PERFORMANCE MANAGEMENT CHART — 12 WEEKS",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Chart area
    chart_left = pad + int(60 * s)
    chart_right = width - pad - int(30 * s)
    chart_top = int(80 * s)
    chart_bottom = height - int(110 * s)
    chart_w = chart_right - chart_left
    chart_h = chart_bottom - chart_top

    # Y-axis range: -30 to 80
    y_min, y_max = -30, 80
    y_range = y_max - y_min

    def val_to_y(val):
        return chart_bottom - ((val - y_min) / y_range) * chart_h

    def week_to_x(w):
        return chart_left + ((w - 1) / 11) * chart_w

    # Y-axis labels and grid
    for val in [-20, 0, 20, 40, 60, 80]:
        y = val_to_y(val)
        draw.text((pad, y - int(7 * s)), str(val),
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)
        # Gridline
        dash_len = int(8 * s)
        gap = int(6 * s)
        x = chart_left
        while x < chart_right:
            end = min(x + dash_len, chart_right)
            color = hex_to_rgb(DARK_BROWN) if val == 0 else hex_to_rgb("#d4c5b9")
            w = max(2, int(2 * s)) if val == 0 else max(1, int(1 * s))
            draw.line([(x, y), (end, y)], fill=color, width=w)
            x = end + gap

    # X-axis labels
    for w in weeks:
        x = week_to_x(w)
        draw.text((x - int(8 * s), chart_bottom + int(8 * s)), f"W{w}",
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Axes
    draw.line([(chart_left, chart_top), (chart_left, chart_bottom)],
              fill=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))
    draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)],
              fill=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))

    # TSB shaded area (fill between zero line and TSB)
    zero_y = val_to_y(0)
    for i in range(len(weeks)):
        x = week_to_x(weeks[i])
        tsb_y = val_to_y(tsb[i])
        if tsb[i] >= 0:
            # Fresh — light teal
            draw.line([(x, zero_y), (x, tsb_y)], fill=hex_to_rgb("#d0ece9"), width=int(chart_w / 12))
        else:
            # Fatigued — light brown
            draw.line([(x, zero_y), (x, tsb_y)], fill=hex_to_rgb("#e8ddd6"), width=int(chart_w / 12))

    # CTL line (fitness) — dark teal, thick
    ctl_points = [(week_to_x(w), val_to_y(c)) for w, c in zip(weeks, ctl)]
    draw.line(ctl_points, fill=hex_to_rgb(DARK_TEAL), width=max(3, int(4 * s)))

    # ATL line (fatigue) — gold, thick
    atl_points = [(week_to_x(w), val_to_y(a)) for w, a in zip(weeks, atl)]
    draw.line(atl_points, fill=hex_to_rgb(GOLD), width=max(3, int(4 * s)))

    # TSB line (form) — primary brown, dashed-ish
    tsb_points = [(week_to_x(w), val_to_y(t)) for w, t in zip(weeks, tsb)]
    draw.line(tsb_points, fill=hex_to_rgb(PRIMARY_BROWN), width=max(2, int(3 * s)))

    # Data point squares (no circles — brand rule)
    dot_r = max(3, int(4 * s))
    for pts, color in [(ctl_points, DARK_TEAL), (atl_points, GOLD), (tsb_points, PRIMARY_BROWN)]:
        for px, py in pts:
            draw.rectangle([(px - dot_r, py - dot_r), (px + dot_r, py + dot_r)], fill=hex_to_rgb(color))

    # Legend
    legend_x = chart_left + int(20 * s)
    legend_y = chart_top + int(10 * s)
    items = [
        ("CTL (Fitness)", DARK_TEAL, "42-day avg — slow to build, slow to fade"),
        ("ATL (Fatigue)", GOLD, "7-day avg — spikes fast, recovers fast"),
        ("TSB (Form)", PRIMARY_BROWN, "CTL - ATL — positive = fresh, negative = fatigued"),
    ]
    for i, (name, color, desc) in enumerate(items):
        y = legend_y + i * int(24 * s)
        draw.rectangle([(legend_x, y + int(2 * s)),
                        (legend_x + int(24 * s), y + int(10 * s))],
                       fill=hex_to_rgb(color))
        draw.text((legend_x + int(32 * s), y - int(2 * s)), name,
                  fill=hex_to_rgb(NEAR_BLACK), font=font_label)
        draw.text((legend_x + int(220 * s), y - int(1 * s)), desc,
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Race day annotation
    race_x = week_to_x(12)
    race_tsb = val_to_y(tsb[11])
    draw.text((race_x - int(60 * s), chart_top - int(5 * s)), "RACE DAY",
              fill=hex_to_rgb(ERROR_RED), font=font_label)
    draw.line([(race_x, chart_top + int(12 * s)), (race_x, chart_bottom)],
              fill=hex_to_rgb(ERROR_RED), width=max(2, int(2 * s)))
    # TSB target annotation
    draw.text((race_x + int(10 * s), race_tsb - int(6 * s)), f"TSB: +{tsb[11]}",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_label)

    # Recovery weeks annotation
    for rw in [4, 8]:
        rx = week_to_x(rw)
        draw.text((rx - int(25 * s), chart_bottom + int(22 * s)), "REST",
                  fill=hex_to_rgb(DARK_TEAL), font=font_xs)

    return img
