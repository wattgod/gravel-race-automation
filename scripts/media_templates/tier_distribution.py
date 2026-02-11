"""Tier distribution chart — 328 races across 4 tiers."""
from PIL import Image, ImageDraw

from .base import (
    load_font, hex_to_rgb,
    PRIMARY_BROWN, SECONDARY_BROWN, DARK_TEAL, TEAL, DARK_GOLD,
    GOLD, OFF_WHITE, BLACK, WHITE,
)

MUTED_TAN = "#c4b5ab"

# Tier data: name, count, percentage, color, score_range, description
TIERS = [
    ("TIER 1", 25, 8, PRIMARY_BROWN, "80+", "Elite — the bucket list races"),
    ("TIER 2", 73, 22, SECONDARY_BROWN, "60-79", "Strong — worth traveling for"),
    ("TIER 3", 154, 47, "#999999", "45-59", "Solid — good regional events"),
    ("TIER 4", 76, 23, "#cccccc", "< 45", "Entry — local or niche"),
]


def render(width: int = 1200, height: int = 400) -> Image.Image:
    """Render the tier distribution horizontal stacked bar with breakdown."""
    img = Image.new("RGB", (width, height), hex_to_rgb(OFF_WHITE))
    draw = ImageDraw.Draw(img)

    font_title = load_font(bold=True, size=22)
    font_label = load_font(bold=True, size=16)
    font_num = load_font(bold=True, size=28)
    font_sm = load_font(bold=False, size=13)
    font_xs = load_font(bold=False, size=11)
    font_pct = load_font(bold=True, size=18)

    pad = 40

    # Title
    draw.text((pad, 16), "GRAVEL GOD RACE DATABASE — 328 RACES",
              fill=hex_to_rgb(PRIMARY_BROWN), font=font_title)
    draw.line([(pad, 48), (width - pad, 48)], fill=hex_to_rgb(BLACK), width=2)

    # Main stacked bar
    bar_top = 68
    bar_h = 70
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
                       fill=hex_to_rgb(color), outline=hex_to_rgb(BLACK), width=2)

        # Percentage centered in segment
        pct_text = f"{pct}%"
        bbox = draw.textbbox((0, 0), pct_text, font=font_pct)
        tw = bbox[2] - bbox[0]
        text_color = WHITE if color in (PRIMARY_BROWN, SECONDARY_BROWN) else BLACK
        if seg_w > tw + 10:
            draw.text((x + (seg_w - tw) // 2, bar_top + (bar_h - 20) // 2),
                      pct_text, fill=hex_to_rgb(text_color), font=font_pct)

        x += seg_w

    # Tier detail rows below
    row_top = bar_top + bar_h + 25
    row_h = 55
    col_w = (width - pad * 2) // 4

    for i, (name, count, pct, color, score_range, desc) in enumerate(TIERS):
        cx = pad + i * col_w

        # Tier badge
        badge_w = 80
        draw.rectangle([(cx, row_top), (cx + badge_w, row_top + 26)],
                       fill=hex_to_rgb(color), outline=hex_to_rgb(BLACK), width=2)
        badge_text_color = WHITE if color in (PRIMARY_BROWN, SECONDARY_BROWN) else BLACK
        draw.text((cx + 8, row_top + 4), name,
                  fill=hex_to_rgb(badge_text_color), font=font_sm)

        # Count
        draw.text((cx + badge_w + 10, row_top - 2), str(count),
                  fill=hex_to_rgb(BLACK), font=font_num)
        draw.text((cx + badge_w + 10 + len(str(count)) * 18, row_top + 8), "races",
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_xs)

        # Score range
        draw.text((cx, row_top + 32), f"Score: {score_range}",
                  fill=hex_to_rgb(SECONDARY_BROWN), font=font_sm)

        # Description
        draw.text((cx, row_top + 52), desc,
                  fill=hex_to_rgb(BLACK), font=font_xs)

    # Bottom insight
    box_y = height - 62
    draw.rectangle([(pad, box_y), (width - pad, height - 18)],
                   fill=hex_to_rgb(WHITE), outline=hex_to_rgb(BLACK), width=2)
    draw.text((pad + 16, box_y + 10),
              "Only 8% of races make Tier 1. Most races (47%) are solid Tier 3 regional events.",
              fill=hex_to_rgb(BLACK), font=font_label)

    # Source
    draw.text((pad, height - 14), "gravelgodcycling.com", fill=hex_to_rgb(MUTED_TAN), font=font_xs)

    return img
