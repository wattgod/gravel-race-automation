#!/usr/bin/env python3
"""
Generate Open Graph social preview images for course landing pages.

Produces 1200x630 neo-brutalist PNGs matching the race OG image style
(scripts/generate_og_images.py): dark background, topo texture, dominant
serif title, mono data labels, price badge, GRAVEL GOD ACADEMY brand bar.

Reads every data/courses/*/course.json and writes the file named by its
og_image field to wordpress/output/course/assets/. Also generates the
Academy bundle image (course-academy-og.png).

Usage:
    python3 scripts/generate_course_og.py
"""

import json
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)

# Reuse the race OG style system — colors, fonts, texture, text helpers
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_og_images import (  # noqa: E402
    W, H, BG_DARK, WARM_PAPER, TAN, GOLD, LIGHT_TEAL, TEAL, NEAR_BLACK, WHITE,
    FONT_SERIF_PATHS, FONT_PATHS, FONT_BOLD_PATHS,
    load_font, tw, wrap_text, draw_topo_texture,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
COURSES_DIR = REPO_ROOT / "data" / "courses"
OUTPUT_DIR = REPO_ROOT / "wordpress" / "output" / "course" / "assets"


def generate_course_og(title: str, subtitle: str, lessons: int, price: int,
                       output_path: Path, kicker: str = "SELF-PACED COURSE"):
    img = Image.new("RGB", (W, H), BG_DARK)
    draw = ImageDraw.Draw(img)
    draw_topo_texture(draw, seed=hash(title) % 1000)

    font_kicker = load_font(FONT_BOLD_PATHS, 22, bold=True)
    font_title = load_font(FONT_SERIF_PATHS, 72)
    font_sub = load_font(FONT_SERIF_PATHS, 28)
    font_meta = load_font(FONT_PATHS, 22)
    font_price = load_font(FONT_BOLD_PATHS, 40, bold=True)
    font_brand = load_font(FONT_BOLD_PATHS, 24, bold=True)

    margin = 70

    # Kicker — gold mono label
    y = 80
    draw.text((margin, y), kicker, font=font_kicker, fill=GOLD)
    y += 50

    # Title — dominant serif, wrapped
    title_lines = wrap_text(draw, title, font_title, W - margin * 2 - 220)
    for line in title_lines[:3]:
        draw.text((margin, y), line, font=font_title, fill=WARM_PAPER)
        y += 84

    # Subtitle
    y += 8
    for line in wrap_text(draw, subtitle, font_sub, W - margin * 2 - 220)[:2]:
        draw.text((margin, y), line, font=font_sub, fill=TAN)
        y += 38

    # Meta row — lesson count
    y += 24
    meta = f"{lessons} INTERACTIVE LESSONS · LIFETIME ACCESS"
    draw.text((margin, y), meta, font=font_meta, fill=LIGHT_TEAL)

    # Price badge — top-right, teal block with thick border
    badge_w, badge_h = 170, 110
    bx, by = W - margin - badge_w, 80
    draw.rectangle([bx, by, bx + badge_w, by + badge_h], fill=TEAL)
    draw.rectangle([bx, by, bx + badge_w, by + badge_h], outline=NEAR_BLACK, width=4)
    price_text = f"${price}"
    px = bx + (badge_w - tw(draw, price_text, font_price)) // 2
    draw.text((px, by + 18), price_text, font=font_price, fill=WHITE)
    one_time = "ONE-TIME"
    font_small = load_font(FONT_PATHS, 16)
    ox = bx + (badge_w - tw(draw, one_time, font_small)) // 2
    draw.text((ox, by + 72), one_time, font=font_small, fill=WARM_PAPER)

    # Brand bar — bottom
    bar_h = 70
    draw.rectangle([0, H - bar_h, W, H], fill=WARM_PAPER)
    draw.text((margin, H - bar_h + 20), "GRAVEL GOD ACADEMY",
              font=font_brand, fill=NEAR_BLACK)
    url = "gravelgodcycling.com/course"
    draw.text((W - margin - tw(draw, url, font_meta), H - bar_h + 22),
              url, font=font_meta, fill=TEAL)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG", optimize=True)
    return output_path


def main():
    generated = []
    for course_json in sorted(COURSES_DIR.glob("*/course.json")):
        with open(course_json) as f:
            course = json.load(f)
        og_name = course.get("og_image")
        if not og_name:
            continue
        lessons = sum(len(m["lessons"]) for m in course.get("modules", []))
        out = generate_course_og(
            course["title"],
            course.get("subtitle", ""),
            lessons,
            course["price_usd"],
            OUTPUT_DIR / og_name,
        )
        generated.append(out)
        print(f"  ✓ {out.relative_to(REPO_ROOT)}")

    # Academy bundle
    out = generate_course_og(
        "Gravel Academy 2-Pack",
        "Hydration Mastery + Dirt Craft. Every lesson, every tool.",
        20, 39,
        OUTPUT_DIR / "course-academy-og.png",
        kicker="COURSE BUNDLE · SAVE 19%",
    )
    generated.append(out)
    print(f"  ✓ {out.relative_to(REPO_ROOT)}")
    print(f"\n{len(generated)} OG images generated.")


if __name__ == "__main__":
    main()
