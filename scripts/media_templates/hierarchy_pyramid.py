"""Hierarchy of speed pyramid — 5 layers showing what actually matters."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"

# Layers from top (narrowest) to bottom (widest)
LAYERS = [
    {"label": "EQUIPMENT", "pct": "0.5%", "color": TEAL},
    {"label": "BIKE HANDLING", "pct": "1.5%", "color": SECONDARY_BROWN},
    {"label": "NUTRITION", "pct": "8%", "color": DARK_GOLD},
    {"label": "PACING", "pct": "20%", "color": DARK_TEAL},
    {"label": "ENGINE / FITNESS", "pct": "70%", "color": PRIMARY_BROWN},
]


def render(width: int = 1200, height: int = 800) -> Image.Image:
    """Render a pyramid with 5 performance layers."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_subtitle = load_font(bold=False, size=13)
    font_layer = load_font(bold=True, size=18)
    font_pct = load_font(bold=True, size=24)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 16), "THE HIERARCHY OF SPEED",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + 380, 20), "What actually determines your result",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    draw.line([(pad, 48), (width - pad, 48)], fill=hex_to_rgb(BLACK), width=2)

    # Pyramid geometry
    n = len(LAYERS)
    pyramid_top = 80
    pyramid_bottom = height - 60
    total_h = pyramid_bottom - pyramid_top
    layer_gap = 4
    layer_h = (total_h - layer_gap * (n - 1)) // n

    # Pyramid narrows from bottom to top
    max_width = width - pad * 2 - 40
    min_width = 180

    for i, layer in enumerate(LAYERS):
        # i=0 is top (narrowest), i=4 is bottom (widest)
        frac = i / (n - 1) if n > 1 else 1
        bar_w = int(min_width + frac * (max_width - min_width))
        y = pyramid_top + i * (layer_h + layer_gap)
        x = (width - bar_w) // 2

        color = layer["color"]
        text_color = BLACK if color in (TEAL,) else WHITE

        # Trapezoid shape — wider at bottom of each layer
        top_indent = 10 if i > 0 else 0
        points = [
            (x + top_indent, y),
            (x + bar_w - top_indent, y),
            (x + bar_w, y + layer_h),
            (x, y + layer_h),
        ]
        draw.polygon(points, fill=hex_to_rgb(color), outline=hex_to_rgb(BLACK))

        # Layer label — centered
        label = layer["label"]
        bbox = draw.textbbox((0, 0), label, font=font_layer)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        text_y = y + (layer_h - th) // 2 - 8
        draw.text(((width - tw) // 2, text_y),
                  label, fill=hex_to_rgb(text_color), font=font_layer)

        # Percentage — right of center
        pct = layer["pct"]
        bbox_p = draw.textbbox((0, 0), pct, font=font_pct)
        pw = bbox_p[2] - bbox_p[0]
        pct_x = (width + tw) // 2 + 16
        # If it would overflow the bar, put it to the right of the bar
        if pct_x + pw > x + bar_w - 10:
            pct_x = x + bar_w + 12
        draw.text((pct_x, text_y - 2),
                  pct, fill=hex_to_rgb(text_color if pct_x < x + bar_w else BLACK), font=font_pct)

    # Source
    draw.text((pad, height - 20), "gravelgodcycling.com",
              fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
