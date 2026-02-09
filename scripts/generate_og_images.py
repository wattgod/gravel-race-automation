#!/usr/bin/env python3
"""
Generate Open Graph social preview images for gravel race landing pages.

Produces 1200x630 neo-brutalist styled JPEG images optimized for social sharing:
  - Race name as dominant visual element
  - Tagline hook text (the scroll-stopping copy)
  - Score badge with tier-colored accent
  - Location + date + stats as supporting info
  - Strong brand bar with GRAVEL GOD identity
  - Optimized for thumbnail legibility (~200-400px wide in feeds)

Usage:
    python scripts/generate_og_images.py unbound-200
    python scripts/generate_og_images.py --all
    python scripts/generate_og_images.py --all --output-dir wordpress/output/og
"""

import argparse
import json
import math
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

# Brand colors
BROWN = (89, 71, 60)          # #59473c
BROWN_SEC = (140, 117, 104)   # #8c7568
DARK_TEAL = (26, 138, 130)    # #1A8A82
TEAL = (78, 205, 196)         # #4ECDC4
DARK_GOLD = (183, 149, 11)    # #B7950B
GOLD = (244, 208, 63)         # #F4D03F
OFF_WHITE = (245, 240, 235)   # #f5f0eb
CREAM = (212, 197, 185)       # #d4c5b9
MUTED_TAN = (196, 181, 171)   # #c4b5ab
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

TIER_COLORS = {
    1: BROWN,
    2: BROWN_SEC,
    3: (153, 153, 153),
    4: (204, 204, 204),
}

TIER_TEXT_COLORS = {
    1: WHITE,
    2: WHITE,
    3: BLACK,
    4: BLACK,
}

# Score accent colors (for the score circle/badge)
TIER_ACCENT = {
    1: DARK_TEAL,
    2: DARK_TEAL,
    3: DARK_GOLD,
    4: BROWN_SEC,
}

ALL_DIMS = ['logistics', 'length', 'technicality', 'elevation', 'climate',
            'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
            'community', 'field_depth', 'value', 'expenses']

# Font paths — tries system fonts, falls back to default
FONT_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

FONT_BOLD_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def load_font(paths: list, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load font from first available path, fall back to default."""
    for p in paths:
        try:
            idx = 1 if bold and p.endswith('.ttc') else 0
            return ImageFont.truetype(p, size, index=idx)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def get_tier(score: int) -> int:
    if score >= 80:
        return 1
    elif score >= 60:
        return 2
    elif score >= 45:
        return 3
    return 4


def text_width(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def text_height(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def wrap_text(draw, text, font, max_width):
    """Word-wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if text_width(draw, test, font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_score_badge(draw, cx, cy, radius, score, tier, font_big, font_label):
    """Draw a neo-brutalist score badge: thick-bordered circle with score."""
    accent = TIER_ACCENT[tier]

    # Outer black ring
    draw.ellipse(
        [cx - radius, cy - radius, cx + radius, cy + radius],
        fill=BLACK
    )
    # Inner white fill
    inner_r = radius - 4
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        fill=WHITE
    )
    # Accent arc (bottom quarter — like a progress indicator)
    arc_r = radius - 2
    # Draw colored arc proportional to score
    arc_extent = int(360 * score / 100)
    draw.arc(
        [cx - arc_r, cy - arc_r, cx + arc_r, cy + arc_r],
        start=90, end=90 + arc_extent,
        fill=accent, width=6
    )

    # Score text centered
    score_text = str(score)
    sw = text_width(draw, score_text, font_big)
    sh = text_height(draw, score_text, font_big)
    draw.text((cx - sw // 2, cy - sh // 2 - 10), score_text, fill=accent, font=font_big)

    # "/ 100" label below
    label = "/ 100"
    lw = text_width(draw, label, font_label)
    draw.text((cx - lw // 2, cy + sh // 2 - 8), label, fill=MUTED_TAN, font=font_label)


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
            if isinstance(bor.get(d), dict)
            else bor.get(d, 0)
            for d in ALL_DIMS
        )
        overall_score = round(total / 70 * 100) if total > 0 else 0
    tier = get_tier(overall_score)

    location = vitals.get('location', '')
    date_specific = vitals.get('date_specific', '')
    dist_mi = vitals.get('distance_mi')
    elev_ft = vitals.get('elevation_ft')
    distance = f"{dist_mi} mi" if dist_mi else ''
    elevation = f"{elev_ft:,} ft" if isinstance(elev_ft, (int, float)) else ''

    # Parse date
    short_date = ''
    if date_specific:
        m = re.search(r'(\d{4}):\s*(.+)', date_specific)
        if m:
            short_date = f"{m.group(2).strip()}, {m.group(1)}"
        else:
            short_date = date_specific

    # ── Create image ──────────────────────────────────────────

    img = Image.new('RGB', (W, H), OFF_WHITE)
    draw = ImageDraw.Draw(img)

    # Load fonts — larger sizes for thumbnail legibility
    font_name = load_font(FONT_BOLD_PATHS, 56, bold=True)
    font_tagline = load_font(FONT_PATHS, 22)
    font_tier = load_font(FONT_BOLD_PATHS, 18, bold=True)
    font_score_big = load_font(FONT_BOLD_PATHS, 56, bold=True)
    font_score_label = load_font(FONT_PATHS, 18)
    font_detail = load_font(FONT_PATHS, 20)
    font_detail_bold = load_font(FONT_BOLD_PATHS, 20, bold=True)
    font_brand = load_font(FONT_BOLD_PATHS, 28, bold=True)
    font_brand_sub = load_font(FONT_PATHS, 16)

    # ── Layout constants ──────────────────────────────────────

    left_margin = 56
    brand_bar_h = 70
    top_bar_h = 6
    score_badge_r = 72
    score_cx = W - left_margin - score_badge_r - 10
    score_cy = 260  # Vertically centered in content area

    # ── Neo-brutalist frame ───────────────────────────────────

    # Outer border (3px black)
    draw.rectangle([0, 0, W - 1, H - 1], outline=BLACK, width=3)

    # Top accent bar (tier-colored)
    draw.rectangle([3, 3, W - 4, 3 + top_bar_h], fill=TIER_COLORS[tier])

    # ── Brand bar (bottom) ────────────────────────────────────

    bottom_bar_y = H - brand_bar_h
    draw.rectangle([3, bottom_bar_y, W - 4, H - 4], fill=BROWN)

    # Brand name — much larger for recognition
    draw.text((left_margin, bottom_bar_y + 18), "GRAVEL GOD", fill=WHITE, font=font_brand)

    # Brand URL right-aligned
    url_text = "gravelgodcycling.com"
    uw = text_width(draw, url_text, font_brand_sub)
    draw.text((W - left_margin - uw, bottom_bar_y + 28), url_text, fill=MUTED_TAN, font=font_brand_sub)

    # Gold accent line below brand name
    brand_text_w = text_width(draw, "GRAVEL GOD", font_brand)
    draw.rectangle(
        [left_margin, bottom_bar_y + 52, left_margin + brand_text_w, bottom_bar_y + 56],
        fill=DARK_GOLD
    )

    # ── Content area ──────────────────────────────────────────

    content_top = 3 + top_bar_h + 30
    content_bottom = bottom_bar_y - 20
    content_right = score_cx - score_badge_r - 40  # Leave room for score badge

    # Tier badge
    badge_text = f"TIER {tier}"
    badge_bw = text_width(draw, badge_text, font_tier) + 20
    badge_bh = text_height(draw, badge_text, font_tier) + 12
    badge_color = TIER_COLORS[tier]
    badge_text_color = TIER_TEXT_COLORS[tier]

    draw.rectangle(
        [left_margin, content_top, left_margin + badge_bw, content_top + badge_bh],
        fill=badge_color, outline=BLACK, width=2
    )
    draw.text((left_margin + 10, content_top + 4), badge_text, fill=badge_text_color, font=font_tier)

    # Race name — bold, large, max 2 lines for thumbnail legibility
    name_y = content_top + badge_bh + 16
    name_max_w = content_right - left_margin
    name_lines = wrap_text(draw, name.upper(), font_name, name_max_w)
    line_h = 64
    for i, line in enumerate(name_lines[:2]):  # Max 2 lines
        draw.text((left_margin, name_y + i * line_h), line, fill=BLACK, font=font_name)
    name_bottom = name_y + min(len(name_lines), 2) * line_h

    # Tagline — the scroll-stopping hook (stays within left content area)
    if tagline:
        tag_y = name_bottom + 8
        tag_max_w = content_right - left_margin  # Don't overlap score badge
        tag_lines = wrap_text(draw, tagline, font_tagline, tag_max_w)
        for i, line in enumerate(tag_lines[:2]):  # Max 2 lines
            draw.text((left_margin, tag_y + i * 28), line, fill=BROWN_SEC, font=font_tagline)
        tag_bottom = tag_y + min(len(tag_lines), 2) * 28
    else:
        tag_bottom = name_bottom

    # ── Stats strip ───────────────────────────────────────────
    # Bottom of content area — location, date, distance, elevation in a clean row

    strip_y = content_bottom - 28
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
        # Draw separator line above stats
        draw.rectangle([left_margin, strip_y - 12, W - left_margin, strip_y - 10], fill=CREAM)

        # Draw stats with dot separators
        stat_x = left_margin
        for j, stat in enumerate(stats):
            if j > 0:
                # Dot separator
                draw.text((stat_x, strip_y - 2), "  \u00b7  ", fill=MUTED_TAN, font=font_detail)
                stat_x += text_width(draw, "  \u00b7  ", font_detail)
            # First stat (location) in bold
            f = font_detail_bold if j == 0 else font_detail
            c = BROWN if j == 0 else BROWN_SEC
            draw.text((stat_x, strip_y), stat, fill=c, font=f)
            stat_x += text_width(draw, stat, f)

    # ── Score badge (right side) ──────────────────────────────

    draw_score_badge(draw, score_cx, score_cy, score_badge_r, overall_score, tier,
                     font_score_big, font_score_label)

    # ── Decorative elements ───────────────────────────────────

    # Vertical accent stripe on left edge
    draw.rectangle([3, 3 + top_bar_h, 8, bottom_bar_y], fill=TIER_ACCENT[tier])

    # ── Save as optimized JPEG ────────────────────────────────

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # JPEG for smaller file size (~50-80KB vs ~200KB+ PNG)
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

    # Find project root
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent

    # Data directory
    data_dir = args.data_dir or project_root / 'race-data'
    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}")
        sys.exit(1)

    # Output directory
    output_dir = args.output_dir or project_root / 'wordpress' / 'output' / 'og'

    if args.all:
        slugs = [f.stem for f in sorted(data_dir.glob('*.json'))]
    else:
        slugs = [args.slug]

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

            out_path = output_dir / f"{slug}.png"  # Will be saved as .jpg
            generate_og_image(race, out_path)

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
