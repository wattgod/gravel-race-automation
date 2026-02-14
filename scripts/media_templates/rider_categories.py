"""Rider categories comparison grid — 4 rider types at a glance."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    LIGHT_GOLD, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN, SAND,
)

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
        "color": GOLD,
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
    s = width / 1200  # scale factor for resolution independence
    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_name = load_font(bold=True, size=int(18 * s))
    font_big = load_font(bold=True, size=int(28 * s))
    font_label = load_font(bold=True, size=int(13 * s))
    font_sm = load_font(bold=False, size=int(13 * s))
    font_xs = load_font(bold=False, size=int(11 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "WHICH RIDER ARE YOU?",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.text((pad + int(370 * s), int(22 * s)), "Four training profiles for gravel racing",
              fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Four columns
    col_gap = int(16 * s)
    total_gap = col_gap * 3
    col_w = (width - pad * 2 - total_gap) // 4
    card_top = int(66 * s)

    for i, rider in enumerate(RIDERS):
        cx = pad + i * (col_w + col_gap)
        color = rider["color"]

        # Card background
        draw.rectangle([(cx, card_top), (cx + col_w, height - int(38 * s))],
                       fill=hex_to_rgb(WHITE), outline=hex_to_rgb(DARK_BROWN), width=max(2, int(2 * s)))

        # Colored header strip
        strip_h = int(44 * s)
        draw.rectangle([(cx, card_top), (cx + col_w, card_top + strip_h)],
                       fill=hex_to_rgb(color))

        # Name centered in strip
        name = rider["name"]
        bbox = draw.textbbox((0, 0), name, font=font_name)
        tw = bbox[2] - bbox[0]
        text_color = NEAR_BLACK if color in (TEAL, LIGHT_GOLD, GOLD) else WHITE
        draw.text((cx + (col_w - tw) // 2, card_top + int(10 * s)),
                  name, fill=hex_to_rgb(text_color), font=font_name)

        # Hours and FTP — big numbers
        info_y = card_top + strip_h + int(16 * s)

        draw.text((cx + int(14 * s), info_y), rider["hours"],
                  fill=hex_to_rgb(color), font=font_big)
        draw.text((cx + int(14 * s), info_y + int(36 * s)), rider["ftp"],
                  fill=hex_to_rgb(NEAR_BLACK), font=font_label)

        # FTP bar visualization
        bar_y = info_y + int(60 * s)
        bar_h = int(12 * s)
        ftp_val = int(rider["ftp"].replace("~", "").replace("W", ""))
        ftp_pct = ftp_val / 350  # max ~350W for scale
        bar_full_w = col_w - int(28 * s)
        bar_fill_w = int(ftp_pct * bar_full_w)

        draw.rectangle([(cx + int(14 * s), bar_y), (cx + int(14 * s) + bar_full_w, bar_y + bar_h)],
                       fill=hex_to_rgb(SAND), outline=hex_to_rgb(DARK_BROWN), width=1)
        draw.rectangle([(cx + int(14 * s), bar_y), (cx + int(14 * s) + bar_fill_w, bar_y + bar_h)],
                       fill=hex_to_rgb(color))

        # Details
        details_y = bar_y + bar_h + int(18 * s)
        detail_items = [
            ("GOAL", rider["goal"]),
            ("REALITY", rider["reality"]),
            ("RACES", rider["tier_fit"]),
        ]

        for j, (key, val) in enumerate(detail_items):
            dy = details_y + j * int(42 * s)
            draw.text((cx + int(14 * s), dy), key,
                      fill=hex_to_rgb(color), font=font_label)
            draw.text((cx + int(14 * s), dy + int(17 * s)), val,
                      fill=hex_to_rgb(NEAR_BLACK), font=font_xs)

    return img
