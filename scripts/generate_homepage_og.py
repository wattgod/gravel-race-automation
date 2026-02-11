#!/usr/bin/env python3
"""Generate a custom OG image for the Gravel God homepage (1200x630)."""

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)

import random

# ── Dimensions & colors ──────────────────────────────────────
W, H = 1200, 630

NEAR_BLACK = (26, 22, 19)
BG_TEXTURE = (36, 30, 26)
PRIMARY_BROWN = (89, 71, 60)
GOLD = (183, 149, 11)
TEAL = (26, 138, 130)
WARM_PAPER = (245, 239, 230)
TAN = (212, 197, 185)
WHITE = (255, 255, 255)
SEC_BROWN = (140, 117, 104)

# ── Fonts ────────────────────────────────────────────────────
FONT_DIR = Path(__file__).resolve().parent.parent / "guide" / "fonts"
FONT_DATA_BOLD = str(FONT_DIR / "SometypeMono-Bold.ttf")
FONT_DATA = str(FONT_DIR / "SometypeMono-Regular.ttf")
FONT_EDITORIAL = str(FONT_DIR / "SourceSerif4-Variable.ttf")


def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return ImageFont.load_default()


def tw(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def draw_topo_texture(draw, seed=99):
    rng = random.Random(seed)
    for _ in range(8):
        y_base = rng.randint(60, H - 100)
        points = []
        for x in range(0, W + 40, 40):
            y = y_base + rng.randint(-15, 15)
            points.append((x, y))
        if len(points) >= 2:
            draw.line(points, fill=BG_TEXTURE, width=1)


def generate():
    img = Image.new("RGB", (W, H), NEAR_BLACK)
    draw = ImageDraw.Draw(img)

    # Topo texture
    draw_topo_texture(draw)

    # Gold accent bar at top
    draw.rectangle([0, 0, W, 6], fill=GOLD)

    # Brand bar at bottom
    bar_y = H - 56
    draw.rectangle([0, bar_y, W, H], fill=PRIMARY_BROWN)
    draw.rectangle([0, bar_y, W, bar_y + 3], fill=GOLD)

    brand_font = load_font(FONT_DATA_BOLD, 14)
    brand_text = "GRAVELGODCYCLING.COM"
    bw = tw(draw, brand_text, brand_font)
    draw.text((W - bw - 40, bar_y + 20), brand_text, fill=TAN, font=brand_font)

    # "G" brand mark in bottom bar
    g_font = load_font(FONT_DATA_BOLD, 28)
    draw.rectangle([30, bar_y + 12, 62, bar_y + 44], fill=GOLD)
    draw.text((37, bar_y + 12), "G", fill=NEAR_BLACK, font=g_font)

    # Tagline in bottom bar
    tag_font = load_font(FONT_DATA, 11)
    draw.text((76, bar_y + 22), "THE DEFINITIVE GRAVEL RACE DATABASE",
              fill=SEC_BROWN, font=tag_font)

    # ── Main content ──

    # "328 RACES RATED" badge
    badge_font = load_font(FONT_DATA_BOLD, 13)
    badge_text = "328 RACES RATED"
    bw = tw(draw, badge_text, badge_font)
    badge_x, badge_y = 60, 60
    draw.rectangle([badge_x - 2, badge_y - 2, badge_x + bw + 16, badge_y + 24],
                   outline=GOLD, width=2)
    draw.text((badge_x + 8, badge_y + 3), badge_text, fill=GOLD, font=badge_font)

    # Main headline
    headline_font = load_font(FONT_EDITORIAL, 52)
    headline_y = 110
    draw.text((60, headline_y), "Every Gravel Race.", fill=WHITE, font=headline_font)
    draw.text((60, headline_y + 62), "Rated. Ranked.", fill=WHITE, font=headline_font)

    # Subheadline
    sub_font = load_font(FONT_DATA, 16)
    sub_y = headline_y + 150
    draw.text((60, sub_y),
              "14 dimensions. 0 sponsors. Just honest ratings.",
              fill=TAN, font=sub_font)

    # ── Right side: stat blocks ──
    stat_font_num = load_font(FONT_DATA_BOLD, 48)
    stat_font_label = load_font(FONT_DATA, 10)

    stats = [
        ("328", "RACES", GOLD),
        ("14", "DIMENSIONS", TEAL),
        ("25", "TIER 1", WHITE),
        ("0", "SPONSORS", GOLD),
    ]

    stat_x = 780
    stat_y_start = 100
    stat_gap = 120

    for i, (num, label, color) in enumerate(stats):
        sx = stat_x + (i % 2) * 180
        sy = stat_y_start + (i // 2) * stat_gap
        draw.text((sx, sy), num, fill=color, font=stat_font_num)
        draw.text((sx, sy + 54), label, fill=SEC_BROWN, font=stat_font_label)

    # Divider line between left/right
    draw.line([(740, 50), (740, bar_y - 20)], fill=PRIMARY_BROWN, width=2)

    # ── Save ──
    output_dir = Path(__file__).resolve().parent.parent / "wordpress" / "output" / "og"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "homepage.jpg"
    img.save(output_path, "JPEG", quality=90)
    print(f"Generated {output_path} ({output_path.stat().st_size:,} bytes)")
    return output_path


if __name__ == "__main__":
    generate()
