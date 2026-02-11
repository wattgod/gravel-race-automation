"""Gear essentials grid — 5 key items every gravel racer needs."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"

ITEMS = [
    {
        "name": "BIKE FRAME",
        "glyph": "[ ]",
        "spec": "Drop bars, 38mm+ clearance",
        "skip": "Carbon, aero geometry",
        "color": DARK_TEAL,
    },
    {
        "name": "TIRES",
        "glyph": "( )",
        "spec": "40-50mm tubeless",
        "skip": "Boutique brands, TPU",
        "color": PRIMARY_BROWN,
    },
    {
        "name": "HELMET",
        "glyph": "/^\\",
        "spec": "Modern MIPS certified",
        "skip": "Aero road helmets",
        "color": DARK_TEAL,
    },
    {
        "name": "REPAIR KIT",
        "glyph": "{+}",
        "spec": "Tube, plugs, CO2, tool",
        "skip": "Exotic chain lubes",
        "color": PRIMARY_BROWN,
    },
    {
        "name": "HYDRATION",
        "glyph": "|||",
        "spec": "2-3 bottles + electrolytes",
        "skip": "Hydration packs <100mi",
        "color": DARK_TEAL,
    },
]


def render(width: int = 1200, height: int = 800) -> Image.Image:
    """Render a 5-item gear essentials grid."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_subtitle = load_font(bold=False, size=13)
    font_name = load_font(bold=True, size=18)
    font_glyph = load_font(bold=True, size=36)
    font_label = load_font(bold=True, size=12)
    font_spec = load_font(bold=False, size=13)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 16), "GEAR ESSENTIALS",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + 280, 20), "What you actually need — nothing more",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_subtitle)
    draw.line([(pad, 48), (width - pad, 48)], fill=hex_to_rgb(BLACK), width=2)

    # 5 columns — top row of 3, bottom row of 2 centered
    col_gap = 16
    top_cols = 3
    bottom_cols = 2
    col_w = (width - pad * 2 - col_gap * (top_cols - 1)) // top_cols
    card_h = 310
    top_y = 66
    bottom_y = top_y + card_h + col_gap

    def draw_card(x, y, item):
        color = item["color"]

        # Card outline
        draw.rectangle([(x, y), (x + col_w, y + card_h)],
                       fill=hex_to_rgb(WHITE), outline=hex_to_rgb(BLACK), width=2)

        # Colored header strip
        strip_h = 42
        draw.rectangle([(x, y), (x + col_w, y + strip_h)],
                       fill=hex_to_rgb(color))

        # Name centered in strip
        bbox = draw.textbbox((0, 0), item["name"], font=font_name)
        tw = bbox[2] - bbox[0]
        draw.text((x + (col_w - tw) // 2, y + 10),
                  item["name"], fill=hex_to_rgb(WHITE), font=font_name)

        # Glyph centered
        glyph_y = y + strip_h + 20
        bbox = draw.textbbox((0, 0), item["glyph"], font=font_glyph)
        tw = bbox[2] - bbox[0]
        draw.text((x + (col_w - tw) // 2, glyph_y),
                  item["glyph"], fill=hex_to_rgb(color), font=font_glyph)

        # Key spec
        spec_y = glyph_y + 60
        draw.text((x + 14, spec_y), "KEY SPEC",
                  fill=hex_to_rgb(color), font=font_label)
        draw.text((x + 14, spec_y + 18), item["spec"],
                  fill=hex_to_rgb(BLACK), font=font_spec)

        # Divider
        div_y = spec_y + 48
        draw.line([(x + 14, div_y), (x + col_w - 14, div_y)],
                  fill=hex_to_rgb(MUTED_TAN), width=1)

        # Skip until later
        skip_y = div_y + 12
        draw.text((x + 14, skip_y), "SKIP UNTIL LATER",
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_label)
        draw.text((x + 14, skip_y + 18), item["skip"],
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

    # Top row: 3 cards
    for i in range(top_cols):
        cx = pad + i * (col_w + col_gap)
        draw_card(cx, top_y, ITEMS[i])

    # Bottom row: 2 cards centered
    bottom_total = bottom_cols * col_w + (bottom_cols - 1) * col_gap
    bottom_start = (width - bottom_total) // 2
    for i in range(bottom_cols):
        cx = bottom_start + i * (col_w + col_gap)
        draw_card(cx, bottom_y, ITEMS[top_cols + i])

    # Source
    draw.text((pad, height - 20), "gravelgodcycling.com",
              fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
