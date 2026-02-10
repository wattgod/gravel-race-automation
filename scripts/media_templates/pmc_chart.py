"""Performance Management Chart (CTL / ATL / TSB) — 12-week training load."""
import math
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb, apply_brand_border,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"


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
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_label = load_font(bold=True, size=15)
    font_sm = load_font(bold=False, size=13)
    font_xs = load_font(bold=False, size=11)

    pad = 50
    weeks, ctl, atl, tsb = _generate_training_data()

    # Title
    draw.text((pad, 18), "PERFORMANCE MANAGEMENT CHART — 12 WEEKS", fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.line([(pad, 50), (width - pad, 50)], fill=hex_to_rgb(BLACK), width=2)

    # Chart area
    chart_left = pad + 60
    chart_right = width - pad - 30
    chart_top = 80
    chart_bottom = height - 110
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
        draw.text((pad, y - 7), str(val), fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)
        # Gridline
        dash_len = 8
        gap = 6
        x = chart_left
        while x < chart_right:
            end = min(x + dash_len, chart_right)
            color = hex_to_rgb(BLACK) if val == 0 else hex_to_rgb("#d4c5b9")
            w = 2 if val == 0 else 1
            draw.line([(x, y), (end, y)], fill=color, width=w)
            x = end + gap

    # X-axis labels
    for w in weeks:
        x = week_to_x(w)
        draw.text((x - 8, chart_bottom + 8), f"W{w}", fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Axes
    draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=hex_to_rgb(BLACK), width=2)
    draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=hex_to_rgb(BLACK), width=2)

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
    draw.line(ctl_points, fill=hex_to_rgb(DARK_TEAL), width=4)

    # ATL line (fatigue) — gold, thick
    atl_points = [(week_to_x(w), val_to_y(a)) for w, a in zip(weeks, atl)]
    draw.line(atl_points, fill=hex_to_rgb(DARK_GOLD), width=4)

    # TSB line (form) — primary brown, dashed-ish
    tsb_points = [(week_to_x(w), val_to_y(t)) for w, t in zip(weeks, tsb)]
    draw.line(tsb_points, fill=hex_to_rgb(PRIMARY_BROWN), width=3)

    # Data point dots
    for pts, color in [(ctl_points, DARK_TEAL), (atl_points, DARK_GOLD), (tsb_points, PRIMARY_BROWN)]:
        for px, py in pts:
            draw.ellipse([(px - 4, py - 4), (px + 4, py + 4)], fill=hex_to_rgb(color))

    # Legend
    legend_x = chart_left + 20
    legend_y = chart_top + 10
    items = [
        ("CTL (Fitness)", DARK_TEAL, "42-day avg — slow to build, slow to fade"),
        ("ATL (Fatigue)", DARK_GOLD, "7-day avg — spikes fast, recovers fast"),
        ("TSB (Form)", PRIMARY_BROWN, "CTL - ATL — positive = fresh, negative = fatigued"),
    ]
    for i, (name, color, desc) in enumerate(items):
        y = legend_y + i * 24
        draw.rectangle([(legend_x, y + 2), (legend_x + 24, y + 10)], fill=hex_to_rgb(color))
        draw.text((legend_x + 32, y - 2), name, fill=hex_to_rgb(BLACK), font=font_label)
        draw.text((legend_x + 220, y - 1), desc, fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Race day annotation
    race_x = week_to_x(12)
    race_tsb = val_to_y(tsb[11])
    draw.text((race_x - 60, chart_top - 5), "RACE DAY", fill=hex_to_rgb("#c0392b"), font=font_label)
    draw.line([(race_x, chart_top + 12), (race_x, chart_bottom)],
              fill=hex_to_rgb("#c0392b"), width=2)
    # TSB target annotation
    draw.text((race_x + 10, race_tsb - 6), f"TSB: +{tsb[11]}", fill=hex_to_rgb(PRIMARY_BROWN), font=font_label)

    # Recovery weeks annotation
    for rw in [4, 8]:
        rx = week_to_x(rw)
        draw.text((rx - 25, chart_bottom + 22), "REST", fill=hex_to_rgb(DARK_TEAL), font=font_xs)

    # Source
    draw.text((pad, height - 18), "gravelgodcycling.com", fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
