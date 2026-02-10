#!/usr/bin/env python3
"""
Generate Open Graph social preview images for gravel race landing pages.

Produces 1200x630 neo-brutalist styled JPEG images optimized for social sharing:
  - Dark background for feed contrast (stops the scroll)
  - Race name as dominant visual element (64px bold)
  - Tagline hook text (the curiosity-gap copy)
  - Score badge with arc progress (the numerical hook)
  - Location + stats as supporting info (truncated for clarity)
  - Strong brand bar with GRAVEL GOD identity
  - Subtle topo-line texture for visual depth
  - Optimized for thumbnail legibility (~200-400px wide in feeds)

Usage:
    python scripts/generate_og_images.py unbound-200
    python scripts/generate_og_images.py --all
    python scripts/generate_og_images.py --all --output-dir wordpress/output/og
"""

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────

W, H = 1200, 630

# Brand colors — from gravel-god-brand/tokens/tokens.json
DARK_BROWN = (58, 46, 37)     # #3a2e25
PRIMARY_BROWN = (89, 71, 60)  # #59473c
SEC_BROWN = (140, 117, 104)   # #8c7568
WARM_BROWN = (166, 142, 128)  # #A68E80
TAN = (212, 197, 185)         # #d4c5b9
SAND = (237, 228, 216)        # #ede4d8
WARM_PAPER = (245, 239, 230)  # #f5efe6
GOLD = (183, 149, 11)         # #B7950B
LIGHT_GOLD = (201, 169, 44)   # #c9a92c
TEAL = (26, 138, 130)         # #1A8A82
LIGHT_TEAL = (78, 205, 196)   # #4ECDC4
NEAR_BLACK = (26, 22, 19)     # #1a1613
WHITE = (255, 255, 255)

# Dark background palette — near-black from tokens
BG_DARK = NEAR_BLACK
BG_TEXTURE = (36, 30, 26)     # Slightly lighter for texture lines

TIER_COLORS = {
    1: PRIMARY_BROWN,
    2: SEC_BROWN,
    3: (153, 153, 153),
    4: (100, 90, 82),           # Darker for dark bg visibility
}

TIER_BADGE_TEXT = {
    1: WHITE,
    2: WHITE,
    3: NEAR_BLACK,
    4: TAN,
}

# Score accent colors
TIER_ACCENT = {
    1: GOLD,         # Gold for T1 (hero score is gold in brand guide)
    2: TEAL,
    3: LIGHT_GOLD,
    4: SEC_BROWN,
}

ALL_DIMS = ['logistics', 'length', 'technicality', 'elevation', 'climate',
            'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
            'community', 'field_depth', 'value', 'expenses']

# Brand font paths — Sometype Mono (data) + Source Serif 4 (editorial)
FONT_DIR = Path(__file__).resolve().parent.parent / "guide" / "fonts"

FONT_EDITORIAL = str(FONT_DIR / "SourceSerif4-Variable.ttf")
FONT_EDITORIAL_ITALIC = str(FONT_DIR / "SourceSerif4-Italic-Variable.ttf")
FONT_DATA = str(FONT_DIR / "SometypeMono-Regular.ttf")
FONT_DATA_BOLD = str(FONT_DIR / "SometypeMono-Bold.ttf")

# Fallback system fonts (if brand fonts missing)
FONT_PATHS = [FONT_DATA, "/System/Library/Fonts/Helvetica.ttc"]
FONT_BOLD_PATHS = [FONT_DATA_BOLD, "/System/Library/Fonts/Helvetica.ttc"]
FONT_SERIF_PATHS = [FONT_EDITORIAL, "/System/Library/Fonts/Georgia.ttf"]


def load_font(paths: list, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for p in paths:
        try:
            idx = 1 if bold and p.endswith('.ttc') else 0
            return ImageFont.truetype(p, size, index=idx)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def get_tier(score: int) -> int:
    if score >= 80: return 1
    elif score >= 60: return 2
    elif score >= 45: return 3
    return 4


def tw(draw, text, font):
    """Text width helper."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def th(draw, text, font):
    """Text height helper."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if tw(draw, test, font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def truncate(text, max_chars=40):
    """Truncate long strings with ellipsis."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars - 1].rstrip() + "\u2026"


def draw_topo_texture(draw, seed=42):
    """Draw subtle topographic-style lines for visual depth.
    Thematically perfect for gravel cycling brand."""
    rng = random.Random(seed)
    for _ in range(8):
        # Random horizontal wavy lines
        y_base = rng.randint(60, H - 100)
        points = []
        for x in range(0, W + 40, 40):
            y = y_base + rng.randint(-15, 15)
            points.append((x, y))
        if len(points) >= 2:
            draw.line(points, fill=BG_TEXTURE, width=1)


def draw_score_badge(draw, cx, cy, radius, score, tier, font_big, font_label):
    """Draw a neo-brutalist score badge: thick ring with arc progress."""
    accent = TIER_ACCENT[tier]

    # Outer ring
    ring_w = 5
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        outline=accent, width=ring_w
    )

    # Dark inner fill
    inner_r = radius - ring_w - 2
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        fill=BG_DARK
    )

    # Score arc — thicker, brighter
    arc_r = radius - 1
    arc_extent = int(360 * score / 100)
    draw.arc(
        [cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r],
        start=-90, end=-90 + arc_extent,  # Start from top
        fill=accent, width=7
    )

    # Score number — large, colored
    score_text = str(score)
    sw = tw(draw, score_text, font_big)
    sh = th(draw, score_text, font_big)
    draw.text((cx - sw // 2, cy - sh // 2 - 8), score_text, fill=accent, font=font_big)

    # "/ 100" label
    label = "/ 100"
    lw = tw(draw, label, font_label)
    draw.text((cx - lw // 2, cy + sh // 2 - 6), label, fill=WARM_BROWN, font=font_label)


def generate_og_image(race_data: dict, output_path: Path) -> Path:
    """Generate a single OG image for a race."""

    name = race_data.get('display_name') or race_data.get('name', 'Unknown Race')
    slug = race_data.get('slug', 'unknown')
    tagline = race_data.get('tagline', '')
    vitals = race_data.get('vitals', {})
    rating = race_data.get('gravel_god_rating', race_data.get('rating', {}))
    bor = race_data.get('biased_opinion_ratings', {})

    # Compute overall score
    overall_score = rating.get('overall_score')
    if not overall_score:
        total = sum(
            bor.get(d, {}).get('score', bor.get(d, 0))
            if isinstance(bor.get(d), dict) else bor.get(d, 0)
            for d in ALL_DIMS
        )
        overall_score = round(total / 70 * 100) if total > 0 else 0
    tier = get_tier(overall_score)

    location = truncate(vitals.get('location', ''), 30)
    date_specific = vitals.get('date_specific', '')
    dist_mi = vitals.get('distance_mi')
    elev_ft = vitals.get('elevation_ft')
    distance = f"{dist_mi} mi" if dist_mi else ''
    elevation = f"{elev_ft:,} ft" if isinstance(elev_ft, (int, float)) else ''

    # Parse date — short format only
    short_date = ''
    if date_specific:
        m = re.search(r'(\d{4}):\s*(\w+\s+\d+)', date_specific)
        if m:
            short_date = f"{m.group(2).strip()}, {m.group(1)}"
        else:
            # Fallback: just grab first recognizable date-like chunk
            m2 = re.search(r'(\w+\s+\d{1,2})', date_specific)
            if m2:
                short_date = m2.group(1)

    # ── Create image with dark background ─────────────────────

    img = Image.new('RGB', (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)

    # Subtle topo texture
    # Use slug hash as seed so each race gets a unique but stable pattern
    draw_topo_texture(draw, seed=hash(slug) % 10000)

    # Load fonts — editorial (Source Serif 4) for name/tagline, data (Sometype Mono) for labels
    font_name = load_font(FONT_SERIF_PATHS, 64)          # Race name — editorial serif
    font_tagline = load_font(FONT_SERIF_PATHS, 22)       # Tagline — editorial serif italic
    font_tier = load_font(FONT_BOLD_PATHS, 20, bold=True) # Tier badge — data mono bold
    font_score_big = load_font(FONT_SERIF_PATHS, 60)     # Score number — editorial serif
    font_score_label = load_font(FONT_PATHS, 18)         # Score label — data mono
    font_detail = load_font(FONT_PATHS, 22)              # Stats — data mono
    font_detail_bold = load_font(FONT_BOLD_PATHS, 22, bold=True)  # Location — data mono bold
    font_brand = load_font(FONT_BOLD_PATHS, 28, bold=True)  # Brand name — data mono bold
    font_brand_sub = load_font(FONT_PATHS, 16)           # URL — data mono

    # ── Layout ────────────────────────────────────────────────

    left_margin = 56
    brand_bar_h = 66
    top_bar_h = 5
    score_badge_r = 76
    score_cx = W - left_margin - score_badge_r - 6
    score_cy = 260

    # ── Top accent bar ────────────────────────────────────────

    draw.rectangle([0, 0, W, top_bar_h], fill=TIER_ACCENT[tier])

    # ── Brand bar (bottom) ────────────────────────────────────

    bottom_bar_y = H - brand_bar_h
    draw.rectangle([0, bottom_bar_y, W, H], fill=DARK_BROWN)

    # Brand name
    draw.text((left_margin, bottom_bar_y + 16), "GRAVEL GOD", fill=WHITE, font=font_brand)

    # Gold underline
    brand_w = tw(draw, "GRAVEL GOD", font_brand)
    draw.rectangle(
        [left_margin, bottom_bar_y + 50, left_margin + brand_w, bottom_bar_y + 53],
        fill=GOLD
    )

    # URL right-aligned
    url_text = "gravelgodcycling.com"
    uw = tw(draw, url_text, font_brand_sub)
    draw.text((W - left_margin - uw, bottom_bar_y + 26), url_text, fill=WARM_BROWN, font=font_brand_sub)

    # ── Content area ──────────────────────────────────────────

    content_top = top_bar_h + 28
    content_bottom = bottom_bar_y - 16
    content_right = score_cx - score_badge_r - 36

    # Tier badge
    badge_text = f"TIER {tier}"
    badge_bw = tw(draw, badge_text, font_tier) + 20
    badge_bh = th(draw, badge_text, font_tier) + 12
    badge_color = TIER_COLORS[tier]
    badge_txt = TIER_BADGE_TEXT[tier]

    draw.rectangle(
        [left_margin, content_top, left_margin + badge_bw, content_top + badge_bh],
        fill=badge_color, outline=TIER_ACCENT[tier], width=2
    )
    draw.text((left_margin + 10, content_top + 4), badge_text, fill=badge_txt, font=font_tier)

    # Race name — large bold, light text on dark bg. Max 2 lines.
    name_y = content_top + badge_bh + 14
    name_max_w = content_right - left_margin
    name_lines = wrap_text(draw, name.upper(), font_name, name_max_w)
    line_h = 72
    for i, line in enumerate(name_lines[:2]):
        draw.text((left_margin, name_y + i * line_h), line, fill=WARM_PAPER, font=font_name)
    name_bottom = name_y + min(len(name_lines), 2) * line_h

    # Tagline — the scroll-stopping hook. Cream on dark = high contrast.
    if tagline:
        tag_y = name_bottom + 6
        tag_max_w = content_right - left_margin
        tag_lines = wrap_text(draw, tagline, font_tagline, tag_max_w)
        for i, line in enumerate(tag_lines[:2]):
            draw.text((left_margin, tag_y + i * 28), line, fill=TAN, font=font_tagline)

    # ── Stats strip ───────────────────────────────────────────

    strip_y = content_bottom - 24
    stats = []
    if location:
        stats.append(location)
    if short_date:
        stats.append(short_date)
    if distance:
        stats.append(distance)
    if elevation:
        stats.append(elevation)

    if stats:
        # Thin separator line
        draw.rectangle([left_margin, strip_y - 10, W - left_margin, strip_y - 9], fill=SEC_BROWN)

        stat_x = left_margin
        for j, stat in enumerate(stats):
            if j > 0:
                sep = "  \u00b7  "
                draw.text((stat_x, strip_y), sep, fill=SEC_BROWN, font=font_detail)
                stat_x += tw(draw, sep, font_detail)
            f = font_detail_bold if j == 0 else font_detail
            c = TAN if j == 0 else WARM_BROWN
            draw.text((stat_x, strip_y), stat, fill=c, font=f)
            stat_x += tw(draw, stat, f)

    # ── Score badge ───────────────────────────────────────────

    draw_score_badge(draw, score_cx, score_cy, score_badge_r, overall_score, tier,
                     font_score_big, font_score_label)

    # ── Left accent stripe ────────────────────────────────────

    draw.rectangle([0, top_bar_h, 4, bottom_bar_y], fill=TIER_ACCENT[tier])

    # ── Save ──────────────────────────────────────────────────

    output_path.parent.mkdir(parents=True, exist_ok=True)
    jpeg_path = output_path.with_suffix('.jpg')
    img.save(str(jpeg_path), 'JPEG', quality=88, optimize=True)
    return jpeg_path


def main():
    parser = argparse.ArgumentParser(description='Generate OG images for gravel race profiles')
    parser.add_argument('slug', nargs='?', help='Race slug (e.g., unbound-200)')
    parser.add_argument('--all', action='store_true', help='Generate for all races')
    parser.add_argument('--data-dir', type=Path, help='Race data directory')
    parser.add_argument('--output-dir', type=Path, help='Output directory for images')
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("Provide a race slug or --all")

    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    data_dir = args.data_dir or project_root / 'race-data'
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    output_dir = args.output_dir or project_root / 'wordpress' / 'output' / 'og'

    slugs = [f.stem for f in sorted(data_dir.glob('*.json'))] if args.all else [args.slug]
    total = len(slugs)
    errors = 0

    for i, slug in enumerate(slugs, 1):
        data_file = data_dir / f"{slug}.json"
        if not data_file.exists():
            print(f"  SKIP: {slug} (no data file)")
            errors += 1
            continue
        try:
            with open(data_file) as f:
                raw = json.load(f)
            race = raw.get('race', raw)
            race.setdefault('slug', slug)
            generate_og_image(race, output_dir / f"{slug}.jpg")
            if args.all and i % 50 == 0:
                print(f"  [{i}/{total}] Generated {slug}.jpg")
        except Exception as e:
            print(f"  ERROR: {slug}: {e}")
            errors += 1

    print(f"\nDone. {total - errors}/{total} images generated in {output_dir}/")
    if errors:
        print(f"  {errors} errors")


if __name__ == '__main__':
    main()
