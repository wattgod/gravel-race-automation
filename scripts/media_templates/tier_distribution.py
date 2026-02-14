"""Tier distribution chart — 328 races across 4 tiers."""
from PIL import Image, ImageDraw

from .base import (
    load_font, load_editorial_font, hex_to_rgb, draw_gold_rule,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, GOLD,
    LIGHT_GOLD, WARM_PAPER, DARK_BROWN, NEAR_BLACK, WHITE, WARM_BROWN,
    TIER_3_WARM, TIER_4_WARM,
)

# Tier data: name, count, percentage, color, score_range, description
TIERS = [
    ("TIER 1", 25, 8, PRIMARY_BROWN, "80+", "Elite — the bucket list races"),
    ("TIER 2", 73, 22, SECONDARY_BROWN, "60-79", "Strong — worth traveling for"),
    ("TIER 3", 154, 47, TIER_3_WARM, "45-59", "Solid — good regional events"),
    ("TIER 4", 76, 23, TIER_4_WARM, "< 45", "Entry — local or niche"),
]


def render(width: int = 1200, height: int = 400) -> Image.Image:
    """Render the tier distribution horizontal stacked bar with breakdown."""
    s = width / 1200

    img = Image.new("RGB", (width, height), hex_to_rgb(WARM_PAPER))
    draw = ImageDraw.Draw(img)

    font_title = load_editorial_font(size=int(26 * s))
    font_label = load_font(bold=True, size=int(16 * s))
    font_num = load_font(bold=True, size=int(28 * s))
    font_sm = load_font(bold=False, size=int(13 * s))
    font_xs = load_font(bold=False, size=int(11 * s))
    font_pct = load_font(bold=True, size=int(18 * s))

    pad = int(40 * s)

    # Title — Source Serif 4 + gold rule
    draw.text((pad, int(14 * s)), "GRAVEL GOD RACE DATABASE — 328 RACES",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    rule_y = int(50 * s)
    draw_gold_rule(draw, pad, rule_y, width - pad, width=max(2, int(2 * s)))

    # Main stacked bar
    bar_top = int(68 * s)
    bar_h = int(70 * s)
    bar_left = pad
    bar_right = width - pad
    bar_w = bar_right - bar_left
    total = sum(t[1] for t in TIERS)

    x = bar_left
    for name, count, pct, color, score_range, desc in TIERS:
        seg_w = int((count / total) * bar_w)
        if name == "TIER 4":
            seg_w = bar_right - x  # fill remaining to avoid rounding gaps

        draw.rectangle([(x, bar_top), (x + seg_w, bar_top + bar_h)],
                       fill=hex_to_rgb(color), outline=hex_to_rgb(DARK_BROWN),
                       width=max(2, int(2 * s)))

        # Percentage centered in segment — white text on all warm tiers
        pct_text = f"{pct}%"
        bbox = draw.textbbox((0, 0), pct_text, font=font_pct)
        tw = bbox[2] - bbox[0]
        if seg_w > tw + int(10 * s):
            draw.text((x + (seg_w - tw) // 2, bar_top + (bar_h - int(20 * s)) // 2),
                      pct_text, fill=hex_to_rgb(WHITE), font=font_pct)

        x += seg_w

    # Tier detail rows below
    row_top = bar_top + bar_h + int(25 * s)
    row_h = int(55 * s)
    col_w = (width - pad * 2) // 4

    for i, (name, count, pct, color, score_range, desc) in enumerate(TIERS):
        cx = pad + i * col_w

        # Tier badge — white text on all warm tiers
        badge_w = int(80 * s)
        draw.rectangle([(cx, row_top), (cx + badge_w, row_top + int(26 * s))],
                       fill=hex_to_rgb(color), outline=hex_to_rgb(DARK_BROWN),
                       width=max(2, int(2 * s)))
        draw.text((cx + int(8 * s), row_top + int(4 * s)), name,
                  fill=hex_to_rgb(WHITE), font=font_sm)

        # Count
        draw.text((cx + badge_w + int(10 * s), row_top - int(2 * s)), str(count),
                  fill=hex_to_rgb(NEAR_BLACK), font=font_num)
        draw.text((cx + badge_w + int(10 * s) + len(str(count)) * int(18 * s), row_top + int(8 * s)), "races",
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

        # Score range
        draw.text((cx, row_top + int(32 * s)), f"Score: {score_range}",
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)

        # Description
        draw.text((cx, row_top + int(52 * s)), desc,
                  fill=hex_to_rgb(NEAR_BLACK), font=font_xs)

    # Bottom insight
    box_y = height - int(62 * s)
    draw.rectangle([(pad, box_y), (width - pad, height - int(18 * s))],
                   fill=hex_to_rgb(WHITE), outline=hex_to_rgb(DARK_BROWN),
                   width=max(2, int(2 * s)))
    draw.text((pad + int(16 * s), box_y + int(10 * s)),
              "Only 8% of races make Tier 1. Most races (47%) are solid Tier 3 regional events.",
              fill=hex_to_rgb(NEAR_BLACK), font=font_label)

    return img
