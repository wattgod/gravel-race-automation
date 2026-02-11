"""Psychological phases mood curve — the emotional journey of a long gravel race."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"
RED = "#c0392b"

# Phases: name, start%, end%, color, mood_description
PHASES = [
    ("HONEYMOON", 0, 30, DARK_TEAL, "Fresh legs, high energy, adrenaline flowing"),
    ("SHATTERING", 30, 50, DARK_GOLD, "Reality hits. Pace feels unsustainable."),
    ("DARK PATCH", 50, 75, RED, "Lowest point. Everything hurts. Want to quit."),
    ("SECOND WIND", 75, 88, GOLD, "Breakthrough. Pain recedes. Rhythm returns."),
    ("FINAL PUSH", 88, 100, PRIMARY_BROWN, "Finish line energy. Empty the tank."),
]


def _smooth_curve(points, steps=6):
    """Linear interpolation for smoother curves."""
    result = []
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        for s in range(steps):
            t = s / steps
            result.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    result.append(points[-1])
    return result


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render the psychological phases mood curve."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_label = load_font(bold=True, size=14)
    font_sm = load_font(bold=False, size=12)
    font_xs = load_font(bold=False, size=11)
    font_phase = load_font(bold=True, size=13)

    pad = 40

    # Title
    draw.text((pad, 18), "THE PSYCHOLOGICAL PHASES OF A LONG RACE",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.line([(pad, 50), (width - pad, 50)], fill=hex_to_rgb(BLACK), width=2)

    # Chart area
    chart_left = pad + 50
    chart_right = width - pad - 20
    chart_top = 80
    chart_bottom = height - 130
    chart_w = chart_right - chart_left
    chart_h = chart_bottom - chart_top

    def pct_to_x(pct):
        return chart_left + (pct / 100) * chart_w

    def mood_to_y(mood):
        """Mood 0-100 maps to chart area. Higher mood = higher on chart."""
        return chart_bottom - (mood / 100) * chart_h

    # Y-axis label
    draw.text((pad - 5, chart_top - 5), "HIGH", fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)
    draw.text((pad - 2, chart_bottom - 10), "LOW", fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Y-axis decorative text
    y_mid = (chart_top + chart_bottom) // 2
    # Rotated text not easily supported, use horizontal
    draw.text((pad - 10, y_mid - 5), "MOOD", fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # X-axis labels (race progress)
    for pct in [0, 25, 50, 75, 100]:
        x = pct_to_x(pct)
        draw.text((x - 10, chart_bottom + 6), f"{pct}%", fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Axes
    draw.line([(chart_left, chart_top), (chart_left, chart_bottom)], fill=hex_to_rgb(BLACK), width=2)
    draw.line([(chart_left, chart_bottom), (chart_right, chart_bottom)], fill=hex_to_rgb(BLACK), width=2)

    # Phase background bands
    for name, start_pct, end_pct, color, _ in PHASES:
        x1 = pct_to_x(start_pct)
        x2 = pct_to_x(end_pct)
        # Very subtle colored band
        rgb = hex_to_rgb(color)
        band_color = (rgb[0], rgb[1], rgb[2])
        # Draw as semi-transparent by mixing with background
        mix = 0.08
        bg = hex_to_rgb(OFF_WHITE)
        blended = tuple(int(bg[i] * (1 - mix) + band_color[i] * mix) for i in range(3))
        draw.rectangle([(x1, chart_top), (x2, chart_bottom)], fill=blended)
        # Phase boundary line
        if start_pct > 0:
            draw.line([(x1, chart_top), (x1, chart_bottom)],
                      fill=hex_to_rgb(MUTED_TAN), width=1)

    # Mood curve points (pct, mood 0-100)
    mood_points = [
        (0, 70),    # Start — excited, nervous
        (5, 80),    # Adrenaline spike
        (15, 85),   # Honeymoon peak
        (25, 75),   # Settling in
        (30, 65),   # Honeymoon fading
        (35, 50),   # Shattering begins
        (40, 40),   # Reality hits
        (45, 30),   # Grinding
        (50, 25),   # Entering Dark Patch
        (55, 18),   # Deep low
        (60, 15),   # Bottom
        (65, 12),   # Absolute bottom
        (70, 18),   # Starting to climb
        (75, 30),   # Second Wind beginning
        (80, 50),   # Breaking through
        (85, 60),   # Rhythm found
        (88, 55),   # Slight dip before final push
        (92, 65),   # Finish line energy
        (96, 75),   # Sprint mode
        (100, 85),  # Euphoria at finish
    ]

    curve_pts = [(pct_to_x(p), mood_to_y(m)) for p, m in mood_points]
    smooth = _smooth_curve(curve_pts, steps=6)

    # Draw the curve
    draw.line(smooth, fill=hex_to_rgb(PRIMARY_BROWN), width=4)

    # Phase labels (below chart)
    label_y = chart_bottom + 24
    for name, start_pct, end_pct, color, desc in PHASES:
        mid_pct = (start_pct + end_pct) / 2
        x = pct_to_x(mid_pct)
        # Phase name
        bbox = draw.textbbox((0, 0), name, font=font_phase)
        tw = bbox[2] - bbox[0]
        draw.text((x - tw // 2, label_y), name, fill=hex_to_rgb(color), font=font_phase)
        # Description
        bbox2 = draw.textbbox((0, 0), desc, font=font_xs)
        tw2 = bbox2[2] - bbox2[0]
        # Truncate if too wide for the phase band
        band_w = pct_to_x(end_pct) - pct_to_x(start_pct)
        draw.text((x - min(tw2, band_w) // 2, label_y + 18), desc,
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Key annotation: "DARK PATCH" callout
    dp_x = pct_to_x(62)
    dp_y = mood_to_y(12)
    draw.text((dp_x + 10, dp_y - 20), "Everyone hits this.",
              fill=hex_to_rgb(RED), font=font_label)
    draw.text((dp_x + 10, dp_y), "It's normal. It passes.",
              fill=hex_to_rgb(RED), font=font_sm)

    # Source
    draw.text((pad, height - 18), "gravelgodcycling.com", fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
