"""Supercompensation curve — the foundational adaptation model."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    LIGHT_GOLD, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN, ERROR_RED,
)

BASE_WIDTH = 1200


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
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_label = load_font(bold=True, size=int(16 * s))
    font_sm = load_font(bold=False, size=int(13 * s))
    font_xs = load_font(bold=False, size=int(11 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "THE SUPERCOMPENSATION CYCLE", fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    rule_y = int(48 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Chart area
    chart_left = pad + int(20 * s)
    chart_right = width - pad - int(20 * s)
    chart_w = chart_right - chart_left
    baseline_y = int(340 * s)  # fitness baseline
    chart_top = int(70 * s)

    # Baseline label
    draw.text((pad, baseline_y - int(8 * s)), "BASELINE", fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Baseline dashed line
    dash_len = int(10 * s)
    gap_len = int(6 * s)
    x = chart_left
    while x < chart_right:
        end = min(x + dash_len, chart_right)
        draw.line([(x, baseline_y), (end, baseline_y)], fill=hex_to_rgb(SECONDARY_BROWN), width=max(1, int(1 * s)))
        x = end + gap_len

    # Curve points: stress -> fatigue dip -> recovery -> supercompensation peak -> return
    # x as fraction of chart width, y as offset from baseline (negative = above)
    raw_points = [
        (0.00, 0),       # start at baseline
        (0.05, 0),       # beginning of training stress
        (0.10, 10 * s),  # slight dip
        (0.18, 60 * s),  # deep fatigue dip
        (0.22, 70 * s),  # bottom of fatigue
        (0.28, 55 * s),  # start recovering
        (0.35, 30 * s),  # recovering
        (0.42, 10 * s),  # approaching baseline
        (0.48, 0),       # back to baseline
        (0.55, -20 * s), # above baseline
        (0.62, -45 * s), # supercompensation peak
        (0.66, -50 * s), # peak
        (0.70, -45 * s), # starting to decline
        (0.76, -30 * s), # declining
        (0.82, -15 * s), # declining more
        (0.88, -5 * s),  # approaching baseline
        (0.94, 0),       # back to baseline (detraining)
        (1.00, 5 * s),   # slight decline if no new stimulus
    ]

    curve_points = [(chart_left + frac * chart_w, baseline_y + offset)
                    for frac, offset in raw_points]
    smooth = _smooth_curve(curve_points, steps=10)

    # Fill area under/above baseline with subtle color
    # Fatigue zone (below baseline = positive y offset) — light red/brown tint
    # Supercompensation zone (above baseline = negative y offset) — light teal tint
    for i in range(len(smooth) - 1):
        x1, y1 = smooth[i]
        x2, y2 = smooth[i + 1]
        mid_y = (y1 + y2) / 2
        if mid_y > baseline_y + int(5 * s):
            # Fatigue zone — subtle brown
            draw.line([(x1, baseline_y), (x1, y1)], fill=(89, 71, 60, 30), width=max(1, int(1 * s)))
        elif mid_y < baseline_y - int(5 * s):
            # Supercompensation zone — subtle teal
            draw.line([(x1, baseline_y), (x1, y1)], fill=(26, 138, 130, 30), width=max(1, int(1 * s)))

    # Draw the curve itself
    draw.line(smooth, fill=hex_to_rgb(PRIMARY_BROWN), width=max(2, int(4 * s)))

    # Phase labels and arrows
    phases = [
        (0.08, "TRAINING\nSTRESS", PRIMARY_BROWN, int(-50 * s)),
        (0.22, "FATIGUE", ERROR_RED, int(30 * s)),
        (0.40, "RECOVERY", GOLD, int(-40 * s)),
        (0.64, "SUPER-\nCOMPENSATION", DARK_TEAL, int(-70 * s)),
        (0.92, "DETRAINING", SECONDARY_BROWN, int(-30 * s)),
    ]

    for frac, label, color, y_offset in phases:
        x = chart_left + frac * chart_w
        # Find the y position on the curve at this x
        idx = int(frac * (len(smooth) - 1))
        idx = min(idx, len(smooth) - 1)
        _, curve_y = smooth[idx]

        label_y = curve_y + y_offset
        if y_offset < 0:
            label_y = min(label_y, curve_y - int(20 * s))

        draw.text((x - int(30 * s), label_y), label, fill=hex_to_rgb(color), font=font_label)

    # Annotation arrows
    # Training stress arrow (downward)
    stress_x = chart_left + 0.14 * chart_w
    draw.line([(stress_x, baseline_y - int(10 * s)), (stress_x, baseline_y + int(40 * s))],
              fill=hex_to_rgb(PRIMARY_BROWN), width=max(2, int(2 * s)))
    # Arrow head
    draw.polygon([(stress_x - int(5 * s), baseline_y + int(35 * s)),
                  (stress_x + int(5 * s), baseline_y + int(35 * s)),
                  (stress_x, baseline_y + int(45 * s))], fill=hex_to_rgb(PRIMARY_BROWN))

    # Supercompensation arrow (upward)
    sc_x = chart_left + 0.58 * chart_w
    draw.line([(sc_x, baseline_y + int(10 * s)), (sc_x, baseline_y - int(35 * s))],
              fill=hex_to_rgb(DARK_TEAL), width=max(2, int(2 * s)))
    draw.polygon([(sc_x - int(5 * s), baseline_y - int(30 * s)),
                  (sc_x + int(5 * s), baseline_y - int(30 * s)),
                  (sc_x, baseline_y - int(40 * s))], fill=hex_to_rgb(DARK_TEAL))

    # Key insight box at bottom
    box_y = height - int(110 * s)
    draw.rectangle([(pad, box_y), (width - pad, height - int(20 * s))],
                   fill=hex_to_rgb(WHITE), outline=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))
    draw.text((pad + int(16 * s), box_y + int(10 * s)),
              "KEY: Train hard enough to create fatigue, then recover long enough",
              fill=hex_to_rgb(NEAR_BLACK), font=font_label)
    draw.text((pad + int(16 * s), box_y + int(34 * s)),
              "to reach supercompensation. Apply new stress BEFORE detraining.",
              fill=hex_to_rgb(NEAR_BLACK), font=font_label)
    draw.text((pad + int(16 * s), box_y + int(62 * s)),
              "Too soon = overtraining. Too late = lost adaptation.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)

    return img
