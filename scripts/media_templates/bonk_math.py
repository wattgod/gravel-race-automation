"""Bonk math infographic — the shock-value fueling equation."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    LIGHT_GOLD, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN, ERROR_RED,
)

BASE_WIDTH = 1200


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render the bonk math equation and gel grid."""
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_big = load_font(bold=True, size=int(48 * s))
    font_num = load_font(bold=True, size=int(36 * s))
    font_label = load_font(bold=True, size=int(16 * s))
    font_sm = load_font(bold=False, size=int(14 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "THE BONK MATH", fill=hex_to_rgb(ERROR_RED), font=font_title)
    rule_y = int(48 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Equation section
    eq_y = int(75 * s)

    # Equation: 8 hrs x 75 g/hr = 600g carbs
    components = [
        ("8", "HOURS", DARK_TEAL),
        ("\u00d7", None, NEAR_BLACK),    # multiplication sign
        ("75", "G/HR", GOLD),
        ("=", None, NEAR_BLACK),
        ("600g", "CARBS", ERROR_RED),
    ]

    eq_x = pad + int(30 * s)
    spacing = [int(140 * s), int(50 * s), int(160 * s), int(50 * s), int(180 * s)]

    for i, (val, label, color) in enumerate(components):
        draw.text((eq_x, eq_y), val, fill=hex_to_rgb(color), font=font_big)
        if label:
            draw.text((eq_x, eq_y + int(55 * s)), label, fill=hex_to_rgb(SECONDARY_BROWN), font=font_label)
        eq_x += spacing[i]

    # "That's equivalent to..." text
    equiv_y = eq_y + int(95 * s)
    draw.text((pad + int(30 * s), equiv_y), "THAT'S EQUIVALENT TO:",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_label)

    # Gel grid — 24 gel "packets"
    grid_y = equiv_y + int(35 * s)
    gel_w = int(38 * s)
    gel_h = int(52 * s)
    gel_gap = int(6 * s)
    cols = 12
    rows = 2
    gel_x_start = pad + int(30 * s)

    for row in range(rows):
        for col in range(cols):
            x = gel_x_start + col * (gel_w + gel_gap)
            y = grid_y + row * (gel_h + gel_gap)
            # Gel packet rectangle
            color = DARK_TEAL if (row * cols + col) < 12 else GOLD
            draw.rectangle([(x, y), (x + gel_w, y + gel_h)],
                           fill=hex_to_rgb(color), outline=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))
            # Number inside
            num = str(row * cols + col + 1)
            bbox = draw.textbbox((0, 0), num, font=font_sm)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((x + (gel_w - tw) // 2, y + (gel_h - th) // 2 - int(2 * s)),
                      num, fill=hex_to_rgb(WHITE), font=font_sm)

    # "24 GELS" big callout to the right
    callout_x = gel_x_start + cols * (gel_w + gel_gap) + int(20 * s)
    draw.text((callout_x, grid_y + int(8 * s)), "24", fill=hex_to_rgb(ERROR_RED), font=font_big)
    draw.text((callout_x, grid_y + int(60 * s)), "GELS", fill=hex_to_rgb(ERROR_RED), font=font_label)

    # Bottom context box
    box_y = height - int(120 * s)
    draw.rectangle([(pad, box_y), (width - pad, height - int(20 * s))],
                   fill=hex_to_rgb(WHITE), outline=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))
    draw.text((pad + int(16 * s), box_y + int(10 * s)),
              "Or equivalent: rice cakes, chews, drink mix, real food.",
              fill=hex_to_rgb(NEAR_BLACK), font=font_label)
    draw.text((pad + int(16 * s), box_y + int(34 * s)),
              "You can't store enough glycogen. You MUST eat on the bike.",
              fill=hex_to_rgb(ERROR_RED), font=font_label)
    draw.text((pad + int(16 * s), box_y + int(62 * s)),
              "Skipping fueling isn't tough. It's a DNF waiting to happen.",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)

    return img
