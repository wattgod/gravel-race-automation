"""Bonk math infographic — the shock-value fueling equation."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb, apply_brand_border,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"
RED = "#c0392b"


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render the bonk math equation and gel grid."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_big = load_font(bold=True, size=48)
    font_num = load_font(bold=True, size=36)
    font_label = load_font(bold=True, size=16)
    font_sm = load_font(bold=False, size=14)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 18), "THE BONK MATH", fill=hex_to_rgb(RED), font=font_title)
    draw.line([(pad, 50), (width - pad, 50)], fill=hex_to_rgb(BLACK), width=2)

    # Equation section
    eq_y = 75

    # Equation: 8 hrs x 75 g/hr = 600g carbs
    components = [
        ("8", "HOURS", DARK_TEAL),
        ("\u00d7", None, BLACK),       # multiplication sign
        ("75", "G/HR", DARK_GOLD),
        ("=", None, BLACK),
        ("600g", "CARBS", RED),
    ]

    eq_x = pad + 30
    spacing = [140, 50, 160, 50, 180]

    for i, (val, label, color) in enumerate(components):
        draw.text((eq_x, eq_y), val, fill=hex_to_rgb(color), font=font_big)
        if label:
            draw.text((eq_x, eq_y + 55), label, fill=hex_to_rgb(SECONDARY_BROWN), font=font_label)
        eq_x += spacing[i]

    # "That's equivalent to..." text
    equiv_y = eq_y + 95
    draw.text((pad + 30, equiv_y), "THAT'S EQUIVALENT TO:",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_label)

    # Gel grid — 24 gel "packets"
    grid_y = equiv_y + 35
    gel_w = 38
    gel_h = 52
    gel_gap = 6
    cols = 12
    rows = 2
    gel_x_start = pad + 30

    for row in range(rows):
        for col in range(cols):
            x = gel_x_start + col * (gel_w + gel_gap)
            y = grid_y + row * (gel_h + gel_gap)
            # Gel packet rectangle
            color = DARK_TEAL if (row * cols + col) < 12 else DARK_GOLD
            draw.rectangle([(x, y), (x + gel_w, y + gel_h)],
                           fill=hex_to_rgb(color), outline=hex_to_rgb(BLACK), width=2)
            # Number inside
            num = str(row * cols + col + 1)
            bbox = draw.textbbox((0, 0), num, font=font_sm)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((x + (gel_w - tw) // 2, y + (gel_h - th) // 2 - 2),
                      num, fill=hex_to_rgb(WHITE), font=font_sm)

    # "24 GELS" big callout to the right
    callout_x = gel_x_start + cols * (gel_w + gel_gap) + 20
    draw.text((callout_x, grid_y + 8), "24", fill=hex_to_rgb(RED), font=font_big)
    draw.text((callout_x, grid_y + 60), "GELS", fill=hex_to_rgb(RED), font=font_label)

    # Bottom context box
    box_y = height - 120
    draw.rectangle([(pad, box_y), (width - pad, height - 20)],
                   fill=hex_to_rgb(WHITE), outline=hex_to_rgb(BLACK), width=2)
    draw.text((pad + 16, box_y + 10),
              "Or equivalent: rice cakes, chews, drink mix, real food.",
              fill=hex_to_rgb(BLACK), font=font_label)
    draw.text((pad + 16, box_y + 34),
              "You can't store enough glycogen. You MUST eat on the bike.",
              fill=hex_to_rgb(RED), font=font_label)
    draw.text((pad + 16, box_y + 62),
              "Skipping fueling isn't tough. It's a DNF waiting to happen.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)

    # Source
    draw.text((pad, height - 16), "gravelgodcycling.com", fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
