"""Hierarchy of speed pyramid — 5 layers showing what actually matters."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    WARM_BROWN, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE,
)

# Layers from top (narrowest) to bottom (widest)
LAYERS = [
    {"label": "EQUIPMENT", "pct": "0.5%", "color": TEAL},
    {"label": "BIKE HANDLING", "pct": "1.5%", "color": SECONDARY_BROWN},
    {"label": "NUTRITION", "pct": "8%", "color": GOLD},
    {"label": "PACING", "pct": "20%", "color": DARK_TEAL},
    {"label": "ENGINE / FITNESS", "pct": "70%", "color": PRIMARY_BROWN},
]

BASE_WIDTH = 1200


def render(width: int = 1200, height: int = 800) -> Image.Image:
    """Render a pyramid with 5 performance layers."""
    s = width / BASE_WIDTH

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_subtitle = load_font(bold=False, size=int(13 * s))
    font_layer = load_font(bold=True, size=int(18 * s))
    font_pct = load_font(bold=True, size=int(24 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "THE HIERARCHY OF SPEED",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + int(400 * s), int(22 * s)), "What actually determines your result",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Pyramid geometry — tighter top padding
    n = len(LAYERS)
    pyramid_top = int(62 * s)
    pyramid_bottom = height - int(30 * s)
    total_h = pyramid_bottom - pyramid_top
    layer_gap = int(4 * s)
    layer_h = (total_h - layer_gap * (n - 1)) // n

    # Pyramid narrows from bottom to top
    max_width = width - pad * 2 - int(40 * s)
    min_width = int(180 * s)

    for i, layer in enumerate(LAYERS):
        # i=0 is top (narrowest), i=4 is bottom (widest)
        frac = i / (n - 1) if n > 1 else 1
        bar_w = int(min_width + frac * (max_width - min_width))
        y = pyramid_top + i * (layer_h + layer_gap)
        x = (width - bar_w) // 2

        color = layer["color"]
        text_color = WHITE

        # Trapezoid shape — wider at bottom of each layer
        top_indent = int(10 * s) if i > 0 else 0
        points = [
            (x + top_indent, y),
            (x + bar_w - top_indent, y),
            (x + bar_w, y + layer_h),
            (x, y + layer_h),
        ]
        draw.polygon(points, fill=hex_to_rgb(color), outline=hex_to_rgb(DARK_BROWN))

        # Layer label — centered
        label = layer["label"]
        bbox = draw.textbbox((0, 0), label, font=font_layer)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        text_y = y + (layer_h - th) // 2 - int(8 * s)
        draw.text(((width - tw) // 2, text_y),
                  label, fill=hex_to_rgb(text_color), font=font_layer)

        # Percentage — right of center
        pct = layer["pct"]
        bbox_p = draw.textbbox((0, 0), pct, font=font_pct)
        pw = bbox_p[2] - bbox_p[0]
        pct_x = (width + tw) // 2 + int(16 * s)
        # If it would overflow the bar, put it to the right of the bar
        if pct_x + pw > x + bar_w - int(10 * s):
            pct_x = x + bar_w + int(12 * s)
        draw.text((pct_x, text_y - int(2 * s)),
                  pct, fill=hex_to_rgb(text_color if pct_x < x + bar_w else NEAR_BLACK), font=font_pct)

    return img
