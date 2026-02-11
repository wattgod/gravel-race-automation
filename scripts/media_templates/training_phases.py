"""Training periodization timeline overlay template."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD, GOLD, OFF_WHITE, BLACK, WHITE,
)

# Phase definitions: name, weeks, color, description
PHASES = [
    ("BASE", "Weeks 1-4", DARK_TEAL, "Build aerobic engine. Z2 focus. Long rides."),
    ("BUILD", "Weeks 5-8", DARK_GOLD, "Add intensity. Threshold + VO2. Race simulation."),
    ("PEAK / TAPER", "Weeks 9-12", PRIMARY_BROWN, "Reduce volume. Maintain intensity. Sharpen."),
]


def render(width: int = 1600, height: int = 500) -> Image.Image:
    """Render a training phases timeline."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_phase = load_font(bold=True, size=20)
    font_weeks = load_font(bold=False, size=14)
    font_desc = load_font(bold=False, size=13)

    # Title
    draw.text((40, 20), "12-WEEK GRAVEL TRAINING PERIODIZATION", fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.line([(40, 54), (width - 40, 54)], fill=hex_to_rgb(BLACK), width=2)

    # Timeline
    phase_top = 80
    phase_height = 120
    margin = 40
    total_width = width - margin * 2
    phase_widths = [total_width // 3] * 3

    for i, (name, weeks, color, desc) in enumerate(PHASES):
        x = margin + sum(phase_widths[:i])
        w = phase_widths[i]

        # Phase box
        draw.rectangle([(x, phase_top), (x + w - 4, phase_top + phase_height)],
                       fill=hex_to_rgb(color), outline=hex_to_rgb(BLACK), width=2)

        # Phase name
        draw.text((x + 16, phase_top + 12), name, fill=hex_to_rgb(WHITE), font=font_phase)

        # Weeks label
        draw.text((x + 16, phase_top + 42), weeks, fill=hex_to_rgb(WHITE), font=font_weeks)

        # Description
        draw.text((x + 16, phase_top + 70), desc, fill=hex_to_rgb(WHITE), font=font_desc)

    # Volume curve (simplified) — peaks mid-base, drops through taper
    curve_top = phase_top + phase_height + 40
    draw.text((40, curve_top), "VOLUME", fill=hex_to_rgb(DARK_TEAL), font=font_weeks)
    draw.text((40, curve_top + 30), "INTENSITY", fill=hex_to_rgb(DARK_GOLD), font=font_weeks)

    # Volume line: rises, peaks, drops
    vol_y_base = curve_top + 60
    vol_points = [
        (margin, vol_y_base),
        (margin + total_width * 0.15, vol_y_base - 40),
        (margin + total_width * 0.30, vol_y_base - 60),
        (margin + total_width * 0.45, vol_y_base - 50),
        (margin + total_width * 0.60, vol_y_base - 35),
        (margin + total_width * 0.75, vol_y_base - 20),
        (margin + total_width * 0.90, vol_y_base + 10),
        (margin + total_width, vol_y_base + 20),
    ]
    draw.line(vol_points, fill=hex_to_rgb(DARK_TEAL), width=3)

    # Intensity line: low base, rises through build, drops in taper
    int_points = [
        (margin, vol_y_base + 10),
        (margin + total_width * 0.15, vol_y_base + 5),
        (margin + total_width * 0.30, vol_y_base - 5),
        (margin + total_width * 0.45, vol_y_base - 25),
        (margin + total_width * 0.60, vol_y_base - 50),
        (margin + total_width * 0.70, vol_y_base - 55),
        (margin + total_width * 0.80, vol_y_base - 40),
        (margin + total_width * 0.90, vol_y_base - 20),
        (margin + total_width, vol_y_base - 10),
    ]
    draw.line(int_points, fill=hex_to_rgb(DARK_GOLD), width=3)

    return img
