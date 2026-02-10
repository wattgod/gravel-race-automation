"""Rider categories comparison grid — 4 rider types at a glance."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb, apply_brand_border,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"

# Rider categories from guide content
RIDERS = [
    {
        "name": "AYAHUASCA",
        "hours": "0-5 hrs/wk",
        "ftp": "~150W",
        "color": TEAL,
        "goal": "Finish your first race",
        "reality": "Every ride is a training ride",
        "tier_fit": "Tier 3-4 races",
    },
    {
        "name": "FINISHER",
        "hours": "5-12 hrs/wk",
        "ftp": "~200W",
        "color": DARK_TEAL,
        "goal": "Complete longer events",
        "reality": "Structured training helps a lot",
        "tier_fit": "Tier 2-3 races",
    },
    {
        "name": "COMPETITOR",
        "hours": "12-18 hrs/wk",
        "ftp": "~260W",
        "color": DARK_GOLD,
        "goal": "Top 25% finish",
        "reality": "Periodization is essential",
        "tier_fit": "Tier 1-2 races",
    },
    {
        "name": "PODIUM",
        "hours": "18-25+ hrs/wk",
        "ftp": "~320W",
        "color": PRIMARY_BROWN,
        "goal": "Race for the win",
        "reality": "Marginal gains matter",
        "tier_fit": "Tier 1 races",
    },
]


def render(width: int = 1200, height: int = 600) -> Image.Image:
    """Render the four rider categories comparison grid."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_name = load_font(bold=True, size=18)
    font_big = load_font(bold=True, size=28)
    font_label = load_font(bold=True, size=13)
    font_sm = load_font(bold=False, size=13)
    font_xs = load_font(bold=False, size=11)

    pad = 40

    # Title
    draw.text((pad, 16), "WHICH RIDER ARE YOU?",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + 370, 20), "Four training profiles for gravel racing",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)
    draw.line([(pad, 48), (width - pad, 48)], fill=hex_to_rgb(BLACK), width=2)

    # Four columns
    col_gap = 16
    total_gap = col_gap * 3
    col_w = (width - pad * 2 - total_gap) // 4
    card_top = 66

    for i, rider in enumerate(RIDERS):
        cx = pad + i * (col_w + col_gap)
        color = rider["color"]

        # Card background
        draw.rectangle([(cx, card_top), (cx + col_w, height - 38)],
                       fill=hex_to_rgb(WHITE), outline=hex_to_rgb(BLACK), width=2)

        # Colored header strip
        strip_h = 44
        draw.rectangle([(cx, card_top), (cx + col_w, card_top + strip_h)],
                       fill=hex_to_rgb(color))

        # Name centered in strip
        name = rider["name"]
        bbox = draw.textbbox((0, 0), name, font=font_name)
        tw = bbox[2] - bbox[0]
        text_color = BLACK if color in (TEAL, GOLD) else WHITE
        draw.text((cx + (col_w - tw) // 2, card_top + 10),
                  name, fill=hex_to_rgb(text_color), font=font_name)

        # Hours and FTP — big numbers
        info_y = card_top + strip_h + 16

        draw.text((cx + 14, info_y), rider["hours"],
                  fill=hex_to_rgb(color), font=font_big)
        draw.text((cx + 14, info_y + 36), rider["ftp"],
                  fill=hex_to_rgb(BLACK), font=font_label)

        # FTP bar visualization
        bar_y = info_y + 60
        bar_h = 12
        ftp_val = int(rider["ftp"].replace("~", "").replace("W", ""))
        ftp_pct = ftp_val / 350  # max ~350W for scale
        bar_full_w = col_w - 28
        bar_fill_w = int(ftp_pct * bar_full_w)

        draw.rectangle([(cx + 14, bar_y), (cx + 14 + bar_full_w, bar_y + bar_h)],
                       fill=hex_to_rgb("#e8e0d8"), outline=hex_to_rgb(BLACK), width=1)
        draw.rectangle([(cx + 14, bar_y), (cx + 14 + bar_fill_w, bar_y + bar_h)],
                       fill=hex_to_rgb(color))

        # Details
        details_y = bar_y + bar_h + 18
        detail_items = [
            ("GOAL", rider["goal"]),
            ("REALITY", rider["reality"]),
            ("RACES", rider["tier_fit"]),
        ]

        for j, (key, val) in enumerate(detail_items):
            dy = details_y + j * 42
            draw.text((cx + 14, dy), key,
                      fill=hex_to_rgb(color), font=font_label)
            draw.text((cx + 14, dy + 17), val,
                      fill=hex_to_rgb(BLACK), font=font_xs)

    # Source
    draw.text((pad, height - 16), "gravelgodcycling.com", fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
