#!/usr/bin/env python3
"""
Generate Topo OG share cards for course landing pages.

Gold field (the training side of the business) with no pillar lit — courses
sit beside plans and coaching rather than being one of them. Title, price
and lesson count come from each data/courses/*/course.json.

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
import og_topo  # noqa: E402

REPO_ROOT = og_topo.REPO_ROOT
COURSES_DIR = REPO_ROOT / "data" / "courses"
OUTPUT_DIR = REPO_ROOT / "wordpress" / "output" / "course" / "assets"


def course_card_html(title: str, lessons: int, price: int, kicker: str = "SELF-PACED COURSE") -> str:
    return og_topo.pillar_card(
        pillar="plans", key=f"course-{title}", kicker=kicker, title_html=og_topo.e(title),
        size=80, width=740, line=f"{lessons} INTERACTIVE LESSONS · LIFETIME ACCESS",
        tag=("ONE-TIME", f"${price}"), active=None)


def generate_course_og(title: str, lessons: int, price: int, output_path: Path,
                       renderer, kicker: str = "SELF-PACED COURSE") -> Path:
    return renderer.render(course_card_html(title, lessons, price, kicker), output_path)


def main():
    generated = []
    total_lessons = 0
    with og_topo.Renderer() as r:
        for course_json in sorted(COURSES_DIR.glob("*/course.json")):
            with open(course_json) as f:
                course = json.load(f)
            lessons = sum(len(m["lessons"]) for m in course.get("modules", []))
            total_lessons += lessons
            og_name = course.get("og_image")
            if not og_name:
                continue
            out = generate_course_og(course["title"], lessons, course["price_usd"],
                                     OUTPUT_DIR / og_name, r)
            generated.append(out)
            print(f"  ✓ {out.relative_to(REPO_ROOT)}")

        # Academy bundle. Lesson count is summed from the courses above (the
        # old hardcoded "20" went stale); the old "SAVE 19%" kicker was dropped
        # because it no longer matched the course prices.
        out = generate_course_og("Gravel Academy 2-Pack", total_lessons, 39,
                                 OUTPUT_DIR / "course-academy-og.png", r, kicker="COURSE BUNDLE")
        generated.append(out)
        print(f"  ✓ {out.relative_to(REPO_ROOT)}")
    print(f"\n{len(generated)} OG images generated.")


if __name__ == "__main__":
    main()
