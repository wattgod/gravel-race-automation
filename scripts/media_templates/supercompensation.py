"""Supercompensation curve — the foundational adaptation model."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

# Muted tan for captions/annotations
MUTED_TAN = "#c4b5ab"


def _smooth_curve(points, steps=4):
    """Simple linear interpolation between points for smoother curves."""
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
    """Render the supercompensation adaptation cycle curve."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_label = load_font(bold=True, size=16)
    font_sm = load_font(bold=False, size=13)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 20), "THE SUPERCOMPENSATION CYCLE", fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.line([(pad, 54), (width - pad, 54)], fill=hex_to_rgb(BLACK), width=2)

    # Chart area
    chart_left = pad + 20
    chart_right = width - pad - 20
    chart_w = chart_right - chart_left
    baseline_y = 340  # fitness baseline
    chart_top = 100

    # Baseline label
    draw.text((pad, baseline_y - 8), "BASELINE", fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Baseline dashed line
    dash_len = 10
    gap_len = 6
    x = chart_left
    while x < chart_right:
        end = min(x + dash_len, chart_right)
        draw.line([(x, baseline_y), (end, baseline_y)], fill=hex_to_rgb(SECONDARY_BROWN), width=1)
        x = end + gap_len

    # Curve points: stress -> fatigue dip -> recovery -> supercompensation peak -> return
    # x as fraction of chart width, y as offset from baseline (negative = above)
    raw_points = [
        (0.00, 0),       # start at baseline
        (0.05, 0),       # beginning of training stress
        (0.10, 10),      # slight dip
        (0.18, 60),      # deep fatigue dip
        (0.22, 70),      # bottom of fatigue
        (0.28, 55),      # start recovering
        (0.35, 30),      # recovering
        (0.42, 10),      # approaching baseline
        (0.48, 0),       # back to baseline
        (0.55, -20),     # above baseline
        (0.62, -45),     # supercompensation peak
        (0.66, -50),     # peak
        (0.70, -45),     # starting to decline
        (0.76, -30),     # declining
        (0.82, -15),     # declining more
        (0.88, -5),      # approaching baseline
        (0.94, 0),       # back to baseline (detraining)
        (1.00, 5),       # slight decline if no new stimulus
    ]

    curve_points = [(chart_left + frac * chart_w, baseline_y + offset)
                    for frac, offset in raw_points]
    smooth = _smooth_curve(curve_points, steps=6)

    # Fill area under/above baseline with subtle color
    # Fatigue zone (below baseline = positive y offset) — light red/brown tint
    # Supercompensation zone (above baseline = negative y offset) — light teal tint
    for i in range(len(smooth) - 1):
        x1, y1 = smooth[i]
        x2, y2 = smooth[i + 1]
        mid_y = (y1 + y2) / 2
        if mid_y > baseline_y + 5:
            # Fatigue zone — subtle brown
            draw.line([(x1, baseline_y), (x1, y1)], fill=(89, 71, 60, 30), width=1)
        elif mid_y < baseline_y - 5:
            # Supercompensation zone — subtle teal
            draw.line([(x1, baseline_y), (x1, y1)], fill=(26, 138, 130, 30), width=1)

    # Draw the curve itself
    draw.line(smooth, fill=hex_to_rgb(PRIMARY_BROWN), width=4)

    # Phase labels and arrows
    phases = [
        (0.08, "TRAINING\nSTRESS", PRIMARY_BROWN, -50),
        (0.22, "FATIGUE", "#c0392b", 30),
        (0.40, "RECOVERY", DARK_GOLD, -40),
        (0.64, "SUPER-\nCOMPENSATION", DARK_TEAL, -70),
        (0.92, "DETRAINING", SECONDARY_BROWN, -30),
    ]

    for frac, label, color, y_offset in phases:
        x = chart_left + frac * chart_w
        # Find the y position on the curve at this x
        idx = int(frac * (len(smooth) - 1))
        idx = min(idx, len(smooth) - 1)
        _, curve_y = smooth[idx]

        label_y = curve_y + y_offset
        if y_offset < 0:
            label_y = min(label_y, curve_y - 20)

        draw.text((x - 30, label_y), label, fill=hex_to_rgb(color), font=font_label)

    # Annotation arrows
    # Training stress arrow (downward)
    stress_x = chart_left + 0.14 * chart_w
    draw.line([(stress_x, baseline_y - 10), (stress_x, baseline_y + 40)],
              fill=hex_to_rgb(PRIMARY_BROWN), width=2)
    # Arrow head
    draw.polygon([(stress_x - 5, baseline_y + 35), (stress_x + 5, baseline_y + 35),
                  (stress_x, baseline_y + 45)], fill=hex_to_rgb(PRIMARY_BROWN))

    # Supercompensation arrow (upward)
    sc_x = chart_left + 0.58 * chart_w
    draw.line([(sc_x, baseline_y + 10), (sc_x, baseline_y - 35)],
              fill=hex_to_rgb(DARK_TEAL), width=2)
    draw.polygon([(sc_x - 5, baseline_y - 30), (sc_x + 5, baseline_y - 30),
                  (sc_x, baseline_y - 40)], fill=hex_to_rgb(DARK_TEAL))

    # Key insight box at bottom
    box_y = height - 110
    draw.rectangle([(pad, box_y), (width - pad, height - 20)],
                   fill=hex_to_rgb(WHITE), outline=hex_to_rgb(BLACK), width=2)
    draw.text((pad + 16, box_y + 10),
              "KEY: Train hard enough to create fatigue, then recover long enough",
              fill=hex_to_rgb(BLACK), font=font_label)
    draw.text((pad + 16, box_y + 34),
              "to reach supercompensation. Apply new stress BEFORE detraining.",
              fill=hex_to_rgb(BLACK), font=font_label)
    draw.text((pad + 16, box_y + 62),
              "Too soon = overtraining. Too late = lost adaptation.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)

    # Source
    draw.text((pad, height - 16), "gravelgodcycling.com", fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
