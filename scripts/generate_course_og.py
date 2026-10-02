#!/usr/bin/env python3
"""
Generate Open Graph share cards for course landing pages.

Same 2026 brand frame as every other card (scripts/og_brand.py): kicker,
course title, subtitle, lesson count, and a bordered price block. Inputs are
unchanged — title / subtitle / price / lesson count from each
data/courses/*/course.json — so this only changes how the card looks.

Reads every data/courses/*/course.json and writes the file named by its
og_image field to wordpress/output/course/assets/. Also generates the
Academy bundle image (course-academy-og.png).

Usage:
    python3 scripts/generate_course_og.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import og_brand as og  # noqa: E402

REPO_ROOT = og.REPO_ROOT
COURSES_DIR = REPO_ROOT / "data" / "courses"
OUTPUT_DIR = REPO_ROOT / "wordpress" / "output" / "course" / "assets"

PRICE_W = 220


def generate_course_og(title: str, subtitle: str, lessons: int, price: int,
                       output_path: Path, kicker: str = "SELF-PACED COURSE"):
    img, draw = og.new_card()
    left_w = og.W - 2 * og.MARGIN - PRICE_W - 56

    y = 182
    og.kicker(draw, (og.MARGIN, y), [(kicker, og.GOLD)])
    y += 46
    font, lines = og.fit_headline(draw, title, left_w,
                                  sizes=(84, 76, 68, 60), max_lines=2)
    for line in lines:
        draw.text((og.MARGIN, y), line, font=font, fill=og.DARK_BROWN)
        y += round(font.size * 1.08)

    if subtitle:
        sub_font = og.serif(32, 400)
        y += 16
        for line in og.wrap(draw, subtitle, sub_font, left_w, 2):
            draw.text((og.MARGIN, y), line, font=sub_font, fill=og.PRIMARY_BROWN)
            y += 44

    meta_y = og.H - 44 - 22
    draw.rectangle([og.MARGIN, meta_y - 26, og.MARGIN + left_w, meta_y - 24], fill=og.DARK_BROWN)
    og.draw_tracked(draw, (og.MARGIN, meta_y), f"{lessons} INTERACTIVE LESSONS · LIFETIME ACCESS",
                    og.mono(18, bold=True), og.TEAL, 3)

    # Price block — neo-brutalist: 3px border, no fill, no radius.
    bx, by = og.W - og.MARGIN - PRICE_W, 182
    bh = 176
    draw.rectangle([bx, by, bx + PRICE_W, by + bh], outline=og.DARK_BROWN, width=3)
    price_text = f"${price}"
    p_font = og.serif(88, 700)
    l, t, r, b = draw.textbbox((0, 0), price_text, font=p_font)
    draw.text((bx + (PRICE_W - (r - l)) // 2 - l, by + 28 - t), price_text,
              font=p_font, fill=og.DARK_BROWN)
    lab = "ONE-TIME"
    lab_font = og.mono(18, bold=True)
    lw = og.tracked_w(draw, lab, lab_font, 4)
    og.draw_tracked(draw, (bx + (PRICE_W - lw) // 2, by + bh - 48), lab, lab_font, og.SEC_BROWN, 4)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG", optimize=True)
    return output_path


def main():
    generated = []
    total_lessons = 0
    for course_json in sorted(COURSES_DIR.glob("*/course.json")):
        with open(course_json) as f:
            course = json.load(f)
        lessons = sum(len(m["lessons"]) for m in course.get("modules", []))
        total_lessons += lessons
        og_name = course.get("og_image")
        if not og_name:
            continue
        out = generate_course_og(
            course["title"],
            course.get("subtitle", ""),
            lessons,
            course["price_usd"],
            OUTPUT_DIR / og_name,
        )
        generated.append(out)
        print(f"  ✓ {out.relative_to(REPO_ROOT)}")

    # Academy bundle. Lesson count is summed from the courses above (the old
    # hardcoded "20" went stale); the old "SAVE 19%" kicker was dropped
    # because it no longer matched the course prices.
    out = generate_course_og(
        "Gravel Academy 2-Pack",
        "Hydration Mastery + Dirt Craft. Every lesson, every tool.",
        total_lessons, 39,
        OUTPUT_DIR / "course-academy-og.png",
        kicker="COURSE BUNDLE",
    )
    generated.append(out)
    print(f"  ✓ {out.relative_to(REPO_ROOT)}")
    print(f"\n{len(generated)} OG images generated.")


if __name__ == "__main__":
    main()
