"""Training periodization timeline overlay template."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD, LIGHT_GOLD,
    WARM_BROWN, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE,
)

# Phase definitions: name, weeks, color, description
PHASES = [
    ("BASE", "Weeks 1-4", DARK_TEAL, "Build aerobic engine. Z2 focus. Long rides."),
    ("BUILD", "Weeks 5-8", GOLD, "Add intensity. Threshold + VO2. Race simulation."),
    ("PEAK / TAPER", "Weeks 9-12", PRIMARY_BROWN, "Reduce volume. Maintain intensity. Sharpen."),
]

BASE_WIDTH = 1600


def render(width: int = 1600, height: int = 500) -> Image.Image:
    """Render a training phases timeline."""
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_phase = load_font(bold=True, size=int(20 * s))
    font_weeks = load_font(bold=False, size=int(14 * s))
    font_desc = load_font(bold=False, size=int(13 * s))

    margin = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((margin, int(14 * s)), "12-WEEK GRAVEL TRAINING PERIODIZATION",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    rule_y = int(50 * s)
    draw_gold_rule(draw, margin, rule_y, width - margin, width=max(2, int(2 * s)))

    # Timeline
    phase_top = int(80 * s)
    phase_height = int(120 * s)
    total_width = width - margin * 2
    phase_widths = [total_width // 3] * 3

    for i, (name, weeks, color, desc) in enumerate(PHASES):
        x = margin + sum(phase_widths[:i])
        w = phase_widths[i]

        # Phase box
        draw.rectangle([(x, phase_top), (x + w - int(4 * s), phase_top + phase_height)],
                       fill=hex_to_rgb(color), outline=hex_to_rgb(DARK_BROWN),
                       width=max(2, int(2 * s)))

        # Phase name
        draw.text((x + int(16 * s), phase_top + int(12 * s)), name,
                  fill=hex_to_rgb(WHITE), font=font_phase)

        # Weeks label
        draw.text((x + int(16 * s), phase_top + int(42 * s)), weeks,
                  fill=hex_to_rgb(WHITE), font=font_weeks)

        # Description
        draw.text((x + int(16 * s), phase_top + int(70 * s)), desc,
                  fill=hex_to_rgb(WHITE), font=font_desc)

    # Volume curve (simplified) — peaks mid-base, drops through taper
    curve_top = phase_top + phase_height + int(40 * s)
    draw.text((margin, curve_top), "VOLUME", fill=hex_to_rgb(DARK_TEAL), font=font_weeks)
    draw.text((margin, curve_top + int(30 * s)), "INTENSITY", fill=hex_to_rgb(GOLD), font=font_weeks)

    # Volume line: rises, peaks, drops
    vol_y_base = curve_top + int(60 * s)
    vol_points = [
        (margin, vol_y_base),
        (margin + total_width * 0.15, vol_y_base - int(40 * s)),
        (margin + total_width * 0.30, vol_y_base - int(60 * s)),
        (margin + total_width * 0.45, vol_y_base - int(50 * s)),
        (margin + total_width * 0.60, vol_y_base - int(35 * s)),
        (margin + total_width * 0.75, vol_y_base - int(20 * s)),
        (margin + total_width * 0.90, vol_y_base + int(10 * s)),
        (margin + total_width, vol_y_base + int(20 * s)),
    ]
    draw.line(vol_points, fill=hex_to_rgb(DARK_TEAL), width=max(3, int(3 * s)))

    # Intensity line: low base, rises through build, drops in taper
    int_points = [
        (margin, vol_y_base + int(10 * s)),
        (margin + total_width * 0.15, vol_y_base + int(5 * s)),
        (margin + total_width * 0.30, vol_y_base - int(5 * s)),
        (margin + total_width * 0.45, vol_y_base - int(25 * s)),
        (margin + total_width * 0.60, vol_y_base - int(50 * s)),
        (margin + total_width * 0.70, vol_y_base - int(55 * s)),
        (margin + total_width * 0.80, vol_y_base - int(40 * s)),
        (margin + total_width * 0.90, vol_y_base - int(20 * s)),
        (margin + total_width, vol_y_base - int(10 * s)),
    ]
    draw.line(int_points, fill=hex_to_rgb(GOLD), width=max(3, int(3 * s)))

    return img
