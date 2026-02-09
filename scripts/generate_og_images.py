#!/usr/bin/env python3
"""
Generate Open Graph social preview images for gravel race landing pages.

Produces 1200x630 neo-brutalist styled images with:
  - Race name, tier badge, overall score
  - Location and date
  - Brand identity (colors, style)

Usage:
    python scripts/generate_og_images.py unbound-200
    python scripts/generate_og_images.py --all
    python scripts/generate_og_images.py --all --output-dir wordpress/output/og
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────

W, H = 1200, 630

# Brand colors
BROWN = (89, 71, 60)        # #59473c
BROWN_SEC = (140, 117, 104)  # #8c7568
DARK_TEAL = (26, 138, 130)   # #1A8A82
DARK_GOLD = (183, 149, 11)   # #B7950B
OFF_WHITE = (245, 240, 235)  # #f5f0eb
CREAM = (212, 197, 185)      # #d4c5b9
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


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """Word-wrap text to fit within max_width."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_og_image(race_data: dict, output_path: Path) -> Path:
    """Generate a single OG image for a race."""

    name = race_data.get('display_name') or race_data.get('name', 'Unknown Race')
    slug = race_data.get('slug', 'unknown')
    vitals = race_data.get('vitals', {})
    rating = race_data.get('gravel_god_rating', race_data.get('rating', {}))
    bor = race_data.get('biased_opinion_ratings', {})

    # Compute overall score from biased_opinion_ratings if not in rating
    overall_score = rating.get('overall_score')
    if not overall_score:
        all_dims = ['logistics', 'length', 'technicality', 'elevation', 'climate',
                     'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
                     'community', 'field_depth', 'value', 'expenses']
        total = sum(bor.get(d, {}).get('score', bor.get(d, 0)) if isinstance(bor.get(d), dict) else bor.get(d, 0) for d in all_dims)
        overall_score = round(total / 70 * 100) if total > 0 else 0
    tier = get_tier(overall_score)

    location = vitals.get('location', '')
    date_specific = vitals.get('date_specific', '')
    # Format distance/elevation from raw vitals
    dist_mi = vitals.get('distance_mi')
    elev_ft = vitals.get('elevation_ft')
    distance = f"{dist_mi} mi" if dist_mi else ''
    elevation = f"{elev_ft:,} ft" if isinstance(elev_ft, (int, float)) else str(elev_ft) if elev_ft else ''

    # Parse date to short format
    short_date = ''
    if date_specific:
        m = re.search(r'(\d{4}):\s*(.+)', date_specific)
        if m:
            year, date_part = m.group(1), m.group(2).strip()
            short_date = f"{date_part}, {year}"
        else:
            short_date = date_specific

    # ── Create image ──────────────────────────────────────────

    img = Image.new('RGB', (W, H), OFF_WHITE)
    draw = ImageDraw.Draw(img)

    # Load fonts
    font_name = load_font(FONT_BOLD_PATHS, 52, bold=True)
    font_tier = load_font(FONT_BOLD_PATHS, 22, bold=True)
    font_score_big = load_font(FONT_BOLD_PATHS, 80, bold=True)
    font_score_label = load_font(FONT_PATHS, 16)
    font_detail = load_font(FONT_PATHS, 24)
    font_brand = load_font(FONT_BOLD_PATHS, 20, bold=True)
    font_tagline = load_font(FONT_PATHS, 18)

    # ── Neo-brutalist frame ───────────────────────────────────

    # Outer border (3px black)
    draw.rectangle([0, 0, W - 1, H - 1], outline=BLACK, width=3)

    # Top brown bar (tier-colored)
    bar_h = 8
    draw.rectangle([3, 3, W - 4, 3 + bar_h], fill=TIER_COLORS[tier])

    # ── Left side: Race info ──────────────────────────────────

    left_margin = 60
    right_boundary = 820  # Leave room for score panel on right
    text_max_w = right_boundary - left_margin - 20

    # Tier badge
    tier_y = 50
    badge_text = f"TIER {tier}"
    badge_bbox = draw.textbbox((0, 0), badge_text, font=font_tier)
    badge_w = badge_bbox[2] - badge_bbox[0] + 24
    badge_h = badge_bbox[3] - badge_bbox[1] + 14
    badge_color = TIER_COLORS[tier]
    badge_text_color = TIER_TEXT_COLORS[tier]

    draw.rectangle([left_margin, tier_y, left_margin + badge_w, tier_y + badge_h], fill=badge_color)
    # Black border on badge
    draw.rectangle([left_margin, tier_y, left_margin + badge_w, tier_y + badge_h], outline=BLACK, width=2)
    draw.text((left_margin + 12, tier_y + 5), badge_text, fill=badge_text_color, font=font_tier)

    # Race name (wrapped)
    name_y = tier_y + badge_h + 24
    name_lines = wrap_text(draw, name.upper(), font_name, text_max_w)
    for i, line in enumerate(name_lines[:3]):  # Max 3 lines
        draw.text((left_margin, name_y + i * 62), line, fill=BLACK, font=font_name)
    name_bottom = name_y + len(name_lines[:3]) * 62

    # Location
    if location:
        loc_y = name_bottom + 16
        draw.text((left_margin, loc_y), location, fill=BROWN_SEC, font=font_detail)
    else:
        loc_y = name_bottom

    # Date
    if short_date:
        date_y = loc_y + 36
        draw.text((left_margin, date_y), short_date, fill=BROWN_SEC, font=font_detail)
    else:
        date_y = loc_y

    # Distance + Elevation stat line
    stat_parts = []
    if distance:
        stat_parts.append(distance)
    if elevation:
        stat_parts.append(elevation)
    if stat_parts:
        stat_y = date_y + 36
        stat_text = "  |  ".join(stat_parts)
        draw.text((left_margin, stat_y), stat_text, fill=BROWN, font=font_detail)

    # ── Right side: Score panel ───────────────────────────────

    panel_x = 850
    panel_w = W - panel_x - 40
    panel_y = 50
    panel_h = 200

    # Score box with thick border
    draw.rectangle(
        [panel_x, panel_y, panel_x + panel_w, panel_y + panel_h],
        fill=WHITE, outline=BLACK, width=3
    )

    # Score number centered
    score_text = str(overall_score)
    score_bbox = draw.textbbox((0, 0), score_text, font=font_score_big)
    score_w = score_bbox[2] - score_bbox[0]
    score_x = panel_x + (panel_w - score_w) // 2
    score_y = panel_y + 30

    # Color the score based on tier
    score_color = DARK_TEAL if tier <= 2 else BROWN if tier == 3 else BROWN_SEC
    draw.text((score_x, score_y), score_text, fill=score_color, font=font_score_big)

    # "OVERALL" label
    label = "OVERALL"
    label_bbox = draw.textbbox((0, 0), label, font=font_score_label)
    label_w = label_bbox[2] - label_bbox[0]
    label_x = panel_x + (panel_w - label_w) // 2
    draw.text((label_x, panel_y + panel_h - 40), label, fill=BROWN_SEC, font=font_score_label)

    # Score bar below box
    bar_y = panel_y + panel_h + 16
    bar_w = panel_w
    bar_full_h = 12

    # Background bar
    draw.rectangle([panel_x, bar_y, panel_x + bar_w, bar_y + bar_full_h], fill=CREAM)
    draw.rectangle([panel_x, bar_y, panel_x + bar_w, bar_y + bar_full_h], outline=BLACK, width=2)

    # Filled portion
    fill_w = max(2, int(bar_w * overall_score / 100))
    fill_color = DARK_TEAL if tier <= 2 else DARK_GOLD if tier == 3 else BROWN_SEC
    draw.rectangle([panel_x + 2, bar_y + 2, panel_x + fill_w - 2, bar_y + bar_full_h - 2], fill=fill_color)

    # ── Bottom bar ────────────────────────────────────────────

    bottom_bar_y = H - 60
    draw.rectangle([3, bottom_bar_y, W - 4, H - 4], fill=BROWN)

    # Brand name
    draw.text((left_margin, bottom_bar_y + 16), "GRAVEL GOD", fill=CREAM, font=font_brand)

    # Tagline right-aligned
    tagline = "RACE PROFILES  |  TRAINING PLANS  |  RACE INTEL"
    tag_bbox = draw.textbbox((0, 0), tagline, font=font_tagline)
    tag_w = tag_bbox[2] - tag_bbox[0]
    draw.text((W - 60 - tag_w, bottom_bar_y + 18), tagline, fill=CREAM, font=font_tagline)

    # ── Decorative elements (neo-brutalist) ───────────────────

    # Corner accent squares
    accent_size = 12
    draw.rectangle([W - 60, 60, W - 60 + accent_size, 60 + accent_size], fill=DARK_GOLD)
    draw.rectangle([W - 40, 60, W - 40 + accent_size, 60 + accent_size], fill=DARK_TEAL)

    # ── Save ──────────────────────────────────────────────────

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), 'PNG', optimize=True)
    return output_path


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

            out_path = output_dir / f"{slug}.png"
            generate_og_image(race, out_path)

            if args.all and i % 50 == 0:
                print(f"  [{i}/{total}] Generated {slug}.png")
        except Exception as e:
            print(f"  ERROR: {slug}: {e}")
            errors += 1

    print(f"\nDone. {total - errors}/{total} images generated in {output_dir}/")
    if errors:
        print(f"  {errors} errors")


if __name__ == '__main__':
    main()
