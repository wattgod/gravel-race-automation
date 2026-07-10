#!/usr/bin/env python3
"""
Generate Gravel God Course pages.

Reads structured course content from data/courses/{slug}/course.json and produces:
  1. Course index page:    /course/index.html
  2. Course landing pages: /course/{slug}/index.html  (ungated sales page)
  3. Lesson pages:         /course/{slug}/lesson/{lesson-id}/index.html  (gated)

Reuses block renderers from generate_guide.py for lesson content.
Follows the same patterns as generate_prep_kit.py for gate logic.

Usage:
    python wordpress/generate_courses.py
    python wordpress/generate_courses.py --course gravel-hydration-mastery
    python wordpress/generate_courses.py --dry-run
"""

import argparse
import html
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_guide import render_block, build_guide_css, set_lesson_context
from brand_tokens import get_font_face_css, get_ga4_head_snippet, get_preload_hints, get_tokens_css
from shared_footer import get_mega_footer_html, get_mega_footer_css
from shared_header import get_site_header_html, get_site_header_css, get_site_header_js
from cookie_consent import get_consent_banner_html

SITE_BASE_URL = "https://gravelgodcycling.com"
WORKER_URL = "https://course-access.gravelgodcoaching.workers.dev"

PROJECT_ROOT = Path(__file__).parent.parent
COURSES_DATA_DIR = PROJECT_ROOT / "data" / "courses"
OUTPUT_DIR = Path(__file__).parent / "output" / "course"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Data Loading ─────────────────────────────────────────────


def load_course(course_dir: Path) -> dict:
    """Load course.json and all referenced lesson files.

    Returns the course dict with each lesson's 'blocks' loaded inline.
    """
    course_json = course_dir / "course.json"
    if not course_json.exists():
        print(f"  SKIP: {course_dir.name} — no course.json")
        return None

    course = json.loads(course_json.read_text(encoding="utf-8"))

    if course.get("status") != "active":
        print(f"  SKIP: {course['id']} — status={course.get('status', 'missing')}")
        return None

    # Load each lesson file
    total_lessons = 0
    for module in course["modules"]:
        for lesson in module["lessons"]:
            lesson_path = course_dir / lesson["file"]
            if not lesson_path.exists():
                print(f"  WARNING: Lesson file not found: {lesson_path}")
                lesson["blocks"] = []
                continue
            lesson_data = json.loads(lesson_path.read_text(encoding="utf-8"))
            lesson["blocks"] = lesson_data.get("blocks", [])
            lesson["title"] = lesson_data.get("title", lesson["title"])
            lesson["est_minutes"] = estimate_lesson_minutes(lesson)
            lesson["drill_minutes"] = lesson_drill_minutes(lesson)
            total_lessons += 1

    course["total_lessons"] = total_lessons
    return course


def load_all_courses() -> list:
    """Load all active courses from data/courses/."""
    courses = []
    if not COURSES_DATA_DIR.exists():
        print(f"No courses directory found: {COURSES_DATA_DIR}")
        return courses

    for course_dir in sorted(COURSES_DATA_DIR.iterdir()):
        if not course_dir.is_dir():
            continue
        course = load_course(course_dir)
        if course:
            courses.append(course)

    return courses


# ── Duration estimates ───────────────────────────────────────

# Interactive blocks add ~1 min each on top of reading time.
INTERACTIVE_BLOCK_TYPES = {
    "knowledge_check", "quiz", "calculator", "drill", "flashcard", "scenario",
    "labeled_graphic", "sorting_activity",
}

# Keys that hold identifiers/config, not reader-facing text.
_WORDCOUNT_SKIP_KEYS = {
    "type", "src", "asset_id", "calculator_id", "id", "layout", "style",
    "level", "correct", "best", "slug", "context", "color", "rider_type",
    "poster", "transform",
}


def _iter_blocks_recursive(blocks):
    """Yield every block, including blocks nested in accordion items."""
    for block in blocks:
        yield block
        if block.get("type") == "accordion":
            for item in block.get("items", []):
                yield from _iter_blocks_recursive(item.get("blocks", []))


def _count_words(value, key=None) -> int:
    """Recursively count words in reader-facing string fields."""
    if key in _WORDCOUNT_SKIP_KEYS:
        return 0
    if isinstance(value, str):
        return len(value.split())
    if isinstance(value, list):
        return sum(_count_words(v) for v in value)
    if isinstance(value, dict):
        return sum(_count_words(v, k) for k, v in value.items())
    return 0


def estimate_lesson_minutes(lesson: dict) -> int:
    """Estimate lesson time: ceil(words/200) reading + 1 min per
    interactive block (knowledge_check, quiz, calculator, drill,
    flashcard, scenario). Drill field time is tracked separately —
    see lesson_drill_minutes()."""
    blocks = lesson.get("blocks", [])
    words = sum(_count_words(b) for b in blocks)
    interactive = sum(
        1 for b in _iter_blocks_recursive(blocks)
        if b.get("type") in INTERACTIVE_BLOCK_TYPES
    )
    return max(1, math.ceil(words / 200) + interactive)


def lesson_drill_minutes(lesson: dict) -> int:
    """Sum of drill time_minutes — field exercise time, shown separately."""
    total = 0
    for b in _iter_blocks_recursive(lesson.get("blocks", [])):
        if b.get("type") == "drill":
            try:
                total += int(b.get("time_minutes") or 0)
            except (TypeError, ValueError):
                pass
    return total


def format_course_total_time(course: dict) -> str:
    """Human total: '~2.5 hours of lessons + field drills'."""
    total_min = sum(
        les.get("est_minutes", 0)
        for mod in course["modules"] for les in mod["lessons"]
    )
    drill_min = sum(
        les.get("drill_minutes", 0)
        for mod in course["modules"] for les in mod["lessons"]
    )
    if total_min >= 60:
        hours = round(total_min / 30) / 2  # nearest half hour
        hours_str = f"{hours:g}"
        time_str = f"~{hours_str} hour{'s' if hours != 1 else ''} of lessons"
    else:
        time_str = f"~{total_min} minutes of lessons"
    if drill_min > 0:
        time_str += " + field drills"
    return time_str


# ── Flat lesson list helper ──────────────────────────────────


def get_flat_lessons(course: dict) -> list:
    """Return a flat ordered list of (module, lesson) tuples."""
    flat = []
    for module in course["modules"]:
        for lesson in module["lessons"]:
            flat.append((module, lesson))
    return flat


# ── CSS ──────────────────────────────────────────────────────


def build_course_css() -> str:
    """Return all course-specific CSS, including guide block CSS and gamification."""
    guide_css = build_guide_css()
    return f"""{guide_css}

/* ── Course Layout ── */
/* overflow-x:clip (not hidden) — hidden creates a scroll container that
   breaks position:sticky on the lesson sidebar */
.gg-course-page{{max-width:100%;overflow-x:clip}}
.gg-course-wrap{{max-width:780px;margin:0 auto;padding:0 24px}}

/* ── Landing: Hero ── */
.gg-course-hero{{background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-sand,#ede4d8);padding:80px 24px 60px;text-align:center}}
.gg-course-hero-inner{{max-width:680px;margin:0 auto}}
.gg-course-hero-badge{{display:inline-block;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:2px;text-transform:uppercase;border:1px solid var(--gg-color-teal,#178079);color:var(--gg-color-teal,#178079);padding:4px 14px;border-radius:2px;margin-bottom:20px}}
.gg-course-hero h1{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:clamp(2rem,5vw,3.2rem);line-height:1.15;margin:0 0 16px;color:var(--gg-color-sand,#ede4d8)}}
.gg-course-hero-subtitle{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.25rem;color:var(--gg-color-warm-brown,#A68E80);margin:0 0 32px}}
.gg-course-hero-price{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:1.5rem;color:var(--gg-color-teal,#178079);margin:0 0 24px}}
.gg-course-hero-cta{{display:inline-block;background:var(--gg-color-teal,#178079);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;letter-spacing:1.5px;text-transform:uppercase;padding:14px 40px;border:none;border-radius:2px;text-decoration:none;cursor:pointer;transition:background .2s}}
.gg-course-hero-cta:hover{{background:#178079}}

/* ── Landing: Description ── */
.gg-course-desc{{padding:48px 0;font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.1rem;line-height:1.7;color:var(--gg-color-dark-brown,#3a2e25)}}

/* ── Landing: What You'll Learn ── */
.gg-course-learn{{padding:40px 0;border-top:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-learn h2{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#7d695d);margin:0 0 24px}}
.gg-course-learn ul{{list-style:none;padding:0;margin:0}}
.gg-course-learn li{{position:relative;padding:8px 0 8px 28px;font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1rem;color:var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-learn li::before{{content:'\\2713';position:absolute;left:0;color:var(--gg-color-teal,#178079);font-weight:700}}

/* ── Landing: Module Outline ── */
.gg-course-outline{{padding:40px 0;border-top:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-outline h2{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#7d695d);margin:0 0 24px}}
.gg-course-module{{margin-bottom:24px}}
.gg-course-module-title{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-primary-brown,#59473c);margin:0 0 12px;padding-bottom:8px;border-bottom:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-module-lessons{{list-style:none;padding:0;margin:0}}
.gg-course-module-lessons li{{padding:8px 0;font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);color:var(--gg-color-dark-brown,#3a2e25);display:flex;align-items:center;gap:8px}}
.gg-course-module-lessons li .gg-course-lesson-num{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#7d695d);min-width:24px}}

/* ── Landing: Instructor ── */
.gg-course-instructor{{padding:40px 0;border-top:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-instructor h2{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#7d695d);margin:0 0 16px}}
.gg-course-instructor-name{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.25rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 4px}}
.gg-course-instructor-title{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#7d695d);margin:0 0 12px}}
.gg-course-instructor-bio{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1rem;line-height:1.6;color:var(--gg-color-primary-brown,#59473c)}}

/* ── Landing: Bottom CTA ── */
.gg-course-bottom-cta{{background:var(--gg-color-warm-paper,#f5efe6);padding:48px 24px;text-align:center;margin-top:40px;border-top:2px solid var(--gg-color-teal,#178079)}}
.gg-course-bottom-cta h2{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.5rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 12px}}
.gg-course-bottom-cta p{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);color:var(--gg-color-primary-brown,#59473c);margin:0 0 24px}}

/* ── Lesson: Purchase Gate ── */
.gg-course-gate{{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(58,46,37,.95);z-index:9000;display:flex;align-items:center;justify-content:center;padding:24px}}
.gg-course-gate-inner{{background:var(--gg-color-warm-paper,#f5efe6);max-width:480px;width:100%;padding:48px 36px;border-radius:4px;text-align:center}}
.gg-course-gate-badge{{display:inline-block;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:2px;text-transform:uppercase;border:1px solid var(--gg-color-teal,#178079);color:var(--gg-color-teal,#178079);padding:3px 12px;border-radius:2px;margin-bottom:16px}}
.gg-course-gate h2{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.5rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 12px}}
.gg-course-gate p{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);color:var(--gg-color-primary-brown,#59473c);margin:0 0 20px;font-size:.95rem}}
.gg-course-gate-cta{{display:inline-block;background:var(--gg-color-teal,#178079);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1.5px;text-transform:uppercase;padding:12px 32px;border:none;border-radius:2px;text-decoration:none;cursor:pointer;margin-bottom:16px}}
.gg-course-gate-cta:hover{{background:#178079}}
.gg-course-gate-divider{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#7d695d);margin:16px 0}}
.gg-course-gate-form{{display:flex;flex-direction:column;gap:10px;margin-top:12px}}
.gg-course-gate-form input[type=email]{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;padding:10px 14px;border:1px solid var(--gg-color-tan,#d4c5b9);border-radius:2px;background:#fff}}
.gg-course-gate-form button{{background:var(--gg-color-primary-brown,#59473c);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:1.5px;text-transform:uppercase;padding:10px 24px;border:none;border-radius:2px;cursor:pointer}}
.gg-course-gate-form button:hover{{background:var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-gate-fine{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;color:var(--gg-color-secondary-brown,#7d695d);margin-top:12px}}
.gg-course-gate-error{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-error,#c0392b);margin-top:8px;display:none}}

/* ── Lesson: Content ── */
.gg-course-lesson{{display:none}}
.gg-course-lesson.gg-course-unlocked{{display:block}}
.gg-course-lesson-header{{background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-sand,#ede4d8);padding:40px 24px 32px;position:relative}}
.gg-course-lesson-header-inner{{max-width:1280px;margin:0 auto;padding:0}}
.gg-course-lesson-breadcrumb{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#7d695d);margin-bottom:16px}}
.gg-course-lesson-breadcrumb a{{color:var(--gg-color-warm-brown,#A68E80);text-decoration:none}}
.gg-course-lesson-breadcrumb a:hover{{text-decoration:underline}}
.gg-course-lesson-num{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-teal,#178079);margin-bottom:8px}}
.gg-course-lesson-mins{{color:var(--gg-color-warm-brown,#A68E80);letter-spacing:1px}}
.gg-course-lesson-header h1{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:clamp(1.5rem,4vw,2.2rem);color:var(--gg-color-sand,#ede4d8);margin:0}}

/* ── Lesson: Two-Column Player Layout ── */
.gg-course-layout{{position:relative}}
.gg-course-main{{min-width:0}}
.gg-course-main-inner{{max-width:760px;margin:0 auto;padding:0 24px}}

/* Sidebar (desktop: sticky column / mobile: off-canvas drawer) */
.gg-course-sidebar{{background:var(--gg-color-warm-paper,#f5efe6)}}
.gg-course-sidebar-inner{{padding:24px}}
.gg-course-sidebar-title{{display:block;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--gg-color-dark-brown,#3a2e25);text-decoration:none;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-sidebar-title:hover{{color:var(--gg-color-teal,#178079)}}
.gg-course-sidebar-module{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#7d695d);margin:20px 0 6px;padding-bottom:4px;border-bottom:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-progress-bar-wrap{{background:var(--gg-color-tan,#d4c5b9);height:6px;margin-bottom:8px;overflow:hidden}}
.gg-course-progress-bar{{height:100%;background:var(--gg-color-teal,#178079);width:0%}}
.gg-course-progress-list{{list-style:none;padding:0;margin:0}}
.gg-course-progress-list li{{padding:6px 0;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-primary-brown,#59473c);display:flex;align-items:baseline;gap:8px}}
.gg-course-progress-list li a{{color:var(--gg-color-primary-brown,#59473c);text-decoration:none;flex:1;min-width:0}}
.gg-course-progress-list li a:hover{{text-decoration:underline}}
.gg-course-progress-list li .gg-check{{color:var(--gg-color-teal,#178079);min-width:14px;display:inline-block}}
.gg-course-progress-list li.gg-current{{font-weight:700;color:var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-progress-list li.gg-current a{{color:var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-progress-list li.gg-current{{border-left:3px solid var(--gg-color-teal,#178079);padding-left:8px;margin-left:-11px}}
.gg-lesson-mins{{font-size:10px;color:var(--gg-color-secondary-brown,#7d695d);white-space:nowrap}}

/* Outline bar (mobile only, pinned below lesson header) */
.gg-course-outline-bar{{display:none;position:sticky;top:var(--gg-header-height,56px);z-index:600;background:var(--gg-color-warm-paper,#f5efe6);border-bottom:2px solid var(--gg-color-dark-brown,#3a2e25);align-items:center;justify-content:space-between;padding:0 16px}}
.gg-course-outline-toggle{{background:none;border:none;cursor:pointer;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--gg-color-dark-brown,#3a2e25);padding:12px 0;display:flex;align-items:center;gap:8px}}
.gg-course-outline-toggle:hover{{color:var(--gg-color-teal,#178079)}}
.gg-course-outline-bar-pct{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;font-weight:700;color:var(--gg-color-teal,#178079)}}

/* Floating compact progress chip (mobile) */
.gg-course-chip{{display:none;position:fixed;bottom:20px;left:16px;z-index:7500;background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-sand,#ede4d8);border:2px solid var(--gg-color-teal,#178079);font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;font-weight:700;padding:8px 14px;cursor:pointer;align-items:center;gap:6px}}
.gg-course-chip .gg-course-chip-pct{{color:var(--gg-color-teal,#178079)}}
/* Lift the chip clear of the PWA install banner when it's showing */
body:has(.gg-pwa-banner-show) .gg-course-chip{{bottom:96px}}

/* Drawer scrim (mobile) */
.gg-course-scrim{{display:none;position:fixed;inset:0;background:rgba(58,46,37,.6);z-index:8400}}
.gg-course-scrim.gg-course-scrim-show{{display:block}}

@media(min-width:1024px){{
  .gg-course-layout{{display:flex;align-items:flex-start;max-width:1280px;margin:0 auto;padding:0 24px;gap:40px}}
  .gg-course-sidebar{{width:300px;min-width:300px;position:sticky;top:var(--gg-header-height,64px);max-height:calc(100vh - var(--gg-header-height,64px));overflow-y:auto;border-right:2px solid var(--gg-color-dark-brown,#3a2e25);background:transparent}}
  .gg-course-sidebar-inner{{padding:32px 24px 32px 0}}
  .gg-course-main{{flex:1}}
  .gg-course-main-inner{{padding:0}}
  .gg-course-scrim{{display:none!important}}
}}
@media(max-width:1023px){{
  .gg-course-outline-bar{{display:flex}}
  .gg-course-chip{{display:flex}}
  .gg-course-sidebar{{position:fixed;top:0;left:0;bottom:0;width:min(320px,86vw);z-index:8500;border-right:3px solid var(--gg-color-dark-brown,#3a2e25);overflow-y:auto;transform:translateX(-105%);visibility:hidden}}
  .gg-course-sidebar.gg-course-sidebar-open{{transform:translateX(0);visibility:visible}}
}}
@media(max-width:1023px) and (prefers-reduced-motion:no-preference){{
  .gg-course-sidebar{{transition:transform .25s ease-out,visibility .25s ease-out}}
}}

/* ── Lesson: Body ── */
.gg-course-lesson-body{{padding:8px 0 24px}}
.gg-course-lesson-body>div,.gg-course-lesson-body>figure{{margin-bottom:30px}}
.gg-course-lesson-body p{{font-size:17px;line-height:1.7}}
.gg-course-lesson-body .gg-guide-list{{font-size:16px;line-height:1.7}}

/* ── Gamification: Streak Badge ── */
.gg-streak-badge{{position:absolute;top:24px;right:24px;display:flex;align-items:center;gap:6px;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;color:var(--gg-color-sand,#ede4d8);padding:6px 14px;border:1px solid rgba(237,228,216,.2);border-radius:20px;opacity:0;transition:opacity .3s ease}}
.gg-streak-badge.gg-streak-active{{opacity:1;border-color:var(--gg-color-teal,#178079)}}
.gg-streak-badge.gg-streak-none{{opacity:.5}}
@media(prefers-reduced-motion:no-preference){{
  .gg-streak-badge.gg-streak-active .gg-streak-fire{{animation:gg-pulse 2s ease-in-out infinite}}
  @keyframes gg-pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.2)}}}}
}}

/* ── Gamification: XP Bar in Progress Sidebar ── */
.gg-xp-section{{margin-top:16px;padding-top:16px;border-top:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-xp-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.gg-xp-level{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gg-color-teal,#178079)}}
.gg-xp-count{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;color:var(--gg-color-secondary-brown,#7d695d)}}
.gg-xp-bar-wrap{{background:var(--gg-color-tan,#d4c5b9);height:4px;border-radius:2px;overflow:hidden}}
.gg-xp-bar{{height:100%;background:var(--gg-color-teal,#178079);width:0%;transition:width .5s ease}}
.gg-xp-streak-row{{display:flex;justify-content:space-between;align-items:center;margin-top:8px}}
.gg-xp-streak-label{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;color:var(--gg-color-secondary-brown,#7d695d)}}

/* ── Gamification: Completion Ring ── */
.gg-completion-ring{{display:flex;align-items:center;gap:12px;margin-bottom:12px}}
.gg-ring-svg{{width:48px;height:48px;transform:rotate(-90deg)}}
.gg-ring-bg{{fill:none;stroke:var(--gg-color-tan,#d4c5b9);stroke-width:4}}
.gg-ring-fill{{fill:none;stroke:var(--gg-color-teal,#178079);stroke-width:4;stroke-linecap:round;transition:stroke-dashoffset .5s ease}}
.gg-ring-pct{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;font-weight:700;color:var(--gg-color-dark-brown,#3a2e25)}}
.gg-ring-label{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:10px;color:var(--gg-color-secondary-brown,#7d695d);text-transform:uppercase;letter-spacing:1px}}

/* ── Gamification: XP Toast ── */
.gg-xp-toast{{position:fixed;bottom:24px;right:24px;background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-teal,#178079);font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;font-weight:700;padding:12px 20px;border-radius:4px;border:1px solid var(--gg-color-teal,#178079);z-index:8000;transform:translateY(100px);opacity:0;transition:transform .3s ease,opacity .3s ease;pointer-events:none}}
.gg-xp-toast.gg-xp-toast-show{{transform:translateY(0);opacity:1}}

/* ── Gamification: Level-Up Overlay ── */
.gg-levelup-overlay{{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(58,46,37,.9);z-index:9500;display:none;align-items:center;justify-content:center;padding:24px}}
.gg-levelup-overlay.gg-levelup-show{{display:flex}}
.gg-levelup-card{{background:var(--gg-color-warm-paper,#f5efe6);max-width:400px;width:100%;padding:48px 36px;border-radius:4px;text-align:center;position:relative;overflow:hidden}}
.gg-levelup-badge{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-teal,#178079);margin-bottom:12px}}
.gg-levelup-title{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.8rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 8px}}
.gg-levelup-name{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;color:var(--gg-color-teal,#178079);letter-spacing:2px;text-transform:uppercase;margin:0 0 24px}}
.gg-levelup-btn{{display:inline-block;background:var(--gg-color-teal,#178079);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1.5px;text-transform:uppercase;padding:12px 32px;border:none;border-radius:2px;cursor:pointer}}
.gg-levelup-btn:hover{{background:#178079}}

/* ── Gamification: Confetti ── */
.gg-confetti{{position:absolute;width:8px;height:8px;top:-10px;opacity:0}}
@media(prefers-reduced-motion:no-preference){{
  .gg-confetti{{animation:gg-confetti-fall 1.5s ease-out forwards;opacity:1}}
  @keyframes gg-confetti-fall{{0%{{opacity:1;transform:translateY(0) rotate(0deg)}}100%{{opacity:0;transform:translateY(350px) rotate(720deg)}}}}
}}

/* ── Gamification: Module Complete Card ── */
.gg-module-complete{{background:var(--gg-color-warm-paper,#f5efe6);border:2px solid var(--gg-color-teal,#178079);border-radius:4px;padding:24px;margin-bottom:24px;text-align:center;display:none}}
.gg-module-complete.gg-module-complete-show{{display:block}}
.gg-module-complete-badge{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gg-color-teal,#178079);margin-bottom:8px}}
.gg-module-complete-title{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.1rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 16px}}
.gg-module-complete-progress{{background:var(--gg-color-tan,#d4c5b9);height:4px;border-radius:2px;overflow:hidden;max-width:200px;margin:0 auto}}
.gg-module-complete-progress-bar{{height:100%;background:var(--gg-color-teal,#178079);transition:width .5s ease}}

/* ── PWA Install Banner ── */
.gg-pwa-banner{{position:fixed;bottom:0;left:0;right:0;background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-sand,#ede4d8);padding:16px 24px;display:none;align-items:center;justify-content:space-between;z-index:7000;border-top:2px solid var(--gg-color-teal,#178079)}}
.gg-pwa-banner.gg-pwa-banner-show{{display:flex}}
.gg-pwa-banner-text{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px}}
.gg-pwa-banner-install{{background:var(--gg-color-teal,#178079);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:1.5px;text-transform:uppercase;padding:8px 20px;border:none;border-radius:2px;cursor:pointer}}
.gg-pwa-banner-dismiss{{background:none;border:none;color:var(--gg-color-secondary-brown,#7d695d);font-size:18px;cursor:pointer;padding:4px 8px}}

/* ── Lesson: Prev/Next Navigation (titles on buttons, top + bottom) ── */
.gg-course-nav{{display:flex;justify-content:space-between;align-items:stretch;gap:16px;padding:20px 0}}
.gg-course-nav--top{{border-bottom:2px solid var(--gg-color-dark-brown,#3a2e25);margin-bottom:8px}}
.gg-course-nav--bottom{{border-top:2px solid var(--gg-color-dark-brown,#3a2e25);margin-top:32px}}
.gg-course-nav-btn{{display:flex;flex-direction:column;gap:4px;max-width:48%;text-decoration:none;padding:10px 16px;border:2px solid var(--gg-color-dark-brown,#3a2e25);background:var(--gg-color-warm-paper,#f5efe6)}}
.gg-course-nav-btn:hover{{border-color:var(--gg-color-teal,#178079)}}
.gg-course-nav-btn:hover .gg-course-nav-dir{{color:var(--gg-color-teal,#178079)}}
.gg-course-nav-next{{text-align:right;margin-left:auto}}
.gg-course-nav-dir{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#7d695d)}}
.gg-course-nav-title{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:14px;color:var(--gg-color-dark-brown,#3a2e25);overflow:hidden;text-overflow:ellipsis;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}}
.gg-course-nav-spacer{{flex:1}}

/* ── Lesson: Mark Complete ── */
.gg-course-complete-btn{{display:block;width:100%;background:var(--gg-color-teal,#178079);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1.5px;text-transform:uppercase;padding:14px;border:2px solid var(--gg-color-dark-brown,#3a2e25);cursor:pointer;margin-top:24px}}
.gg-course-complete-btn:hover{{background:var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-complete-btn.gg-completed{{background:var(--gg-color-secondary-brown,#7d695d);cursor:default}}

/* ── Entrance animations (progressive enhancement — pitfall 11) ──
   Blocks are VISIBLE by default. Initial hidden state applies only after
   JS adds .gg-anim-ready to <body>, and only when motion is allowed. */
@media(prefers-reduced-motion:no-preference){{
  body.gg-anim-ready .gg-course-anim{{opacity:0;transform:translateY(12px)}}
  body.gg-anim-ready .gg-course-anim.gg-anim-in{{opacity:1;transform:translateY(0);transition:opacity .35s ease-out,transform .35s ease-out}}
}}

/* ── Knowledge check / quiz feedback polish ── */
.gg-kc-opt-dim{{opacity:.45}}
.gg-kc-opt-correct{{border-color:var(--gg-color-teal,#178079)!important;border-width:3px!important}}
.gg-kc-opt-wrong{{border-color:var(--gg-color-error,#c0392b)!important}}
.gg-guide-kc-explanation{{overflow:hidden}}
@media(prefers-reduced-motion:no-preference){{
  .gg-kc-reveal{{animation:gg-kc-reveal .3s ease-out}}
  @keyframes gg-kc-reveal{{from{{opacity:0;max-height:0}}to{{opacity:1;max-height:600px}}}}
  .gg-kc-flash{{animation:gg-kc-flash .6s ease-out}}
  @keyframes gg-kc-flash{{0%{{background:var(--gg-color-teal,#178079);color:#fff}}100%{{background:var(--gg-color-warm-paper,#f5efe6)}}}}
  .gg-kc-shake{{animation:gg-kc-shake .35s ease-in-out}}
  @keyframes gg-kc-shake{{0%,100%{{transform:translateX(0)}}25%{{transform:translateX(-6px)}}75%{{transform:translateX(6px)}}}}
}}

/* ── Accordion icon rotate ── */
@media(prefers-reduced-motion:no-preference){{
  .gg-guide-accordion-icon{{transition:transform .2s ease-out}}
}}

/* ── Tabs crossfade ── */
@media(prefers-reduced-motion:no-preference){{
  .gg-tab-fade{{animation:gg-tab-fade .25s ease-out}}
  @keyframes gg-tab-fade{{from{{opacity:0}}to{{opacity:1}}}}
}}

/* ── Image lightbox ── */
.gg-course-zoomable{{cursor:zoom-in}}
.gg-course-lightbox{{display:none;position:fixed;inset:0;background:rgba(26,22,19,.94);z-index:9600;align-items:center;justify-content:center;padding:32px}}
.gg-course-lightbox.gg-course-lightbox-open{{display:flex}}
.gg-course-lightbox-img{{max-width:100%;max-height:100%;border:3px solid var(--gg-color-sand,#ede4d8);cursor:zoom-out}}
.gg-course-lightbox-close{{position:absolute;top:16px;right:16px;background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-sand,#ede4d8);border:2px solid var(--gg-color-sand,#ede4d8);font-size:24px;line-height:1;width:44px;height:44px;cursor:pointer;font-family:var(--gg-font-data,'Sometype Mono',monospace)}}
.gg-course-lightbox-close:hover{{color:var(--gg-color-teal,#178079);border-color:var(--gg-color-teal,#178079)}}

/* ── Process (named tool) paced stepper ── */
.gg-tool-rail{{display:flex;gap:4px;margin:12px 0 4px}}
.gg-tool-rail-dot{{flex:1;height:4px;background:var(--gg-color-tan,#d4c5b9)}}
.gg-tool-rail-dot--on{{background:var(--gg-color-teal,#178079)}}
.gg-tool-ctrl{{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 0 2px}}
.gg-tool-ctrl-btn{{background:var(--gg-color-warm-paper,#f5efe6);border:2px solid var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-dark-brown,#3a2e25);font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;padding:8px 14px;cursor:pointer}}
.gg-tool-ctrl-btn:hover{{border-color:var(--gg-color-teal,#178079);color:var(--gg-color-teal,#178079)}}
.gg-tool-ctrl-btn:disabled{{opacity:.35;cursor:default}}
.gg-tool-ctrl-count{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:1px;color:var(--gg-color-secondary-brown,#7d695d)}}
@media(min-width:1024px){{
  .gg-tool-paced .gg-guide-tool-step.gg-step-active{{border-left:3px solid var(--gg-color-teal,#178079)}}
}}
@media(max-width:1023px){{
  .gg-tool-paced .gg-guide-tool-step{{display:none}}
  .gg-tool-paced .gg-guide-tool-step.gg-step-active{{display:flex}}
}}

/* ── Flashcard flip-hint affordance (hidden after first interaction) ── */
.gg-guide-flashcard::after{{content:'\\21BB FLIP';position:absolute;bottom:6px;right:8px;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:9px;font-weight:700;letter-spacing:1px;color:var(--gg-color-teal,#178079);pointer-events:none;z-index:1}}
.gg-fc-touched .gg-guide-flashcard::after{{content:none}}

/* ── Landing: curriculum durations, locks, total time ── */
.gg-course-outline-total{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:1px;color:var(--gg-color-teal,#178079);margin:-12px 0 24px}}
.gg-course-module-lessons li .gg-course-lesson-mins-landing{{margin-left:auto;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;color:var(--gg-color-secondary-brown,#7d695d);white-space:nowrap}}
.gg-course-lesson-lock{{font-size:11px;opacity:.55}}

/* ── Landing: bundle cross-sell strip ── */
.gg-course-bundle{{border:3px solid var(--gg-color-dark-brown,#3a2e25);background:var(--gg-color-warm-paper,#f5efe6);padding:24px;margin:40px 0 0;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:16px}}
.gg-course-bundle-kicker{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-teal,#178079);margin:0 0 6px}}
.gg-course-bundle-copy{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 12px}}
.gg-course-bundle-copy a{{color:var(--gg-color-teal,#178079);text-decoration:underline}}
.gg-course-bundle-copy a:hover{{color:var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-bundle-cta{{display:inline-block;background:var(--gg-color-dark-brown,#3a2e25);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:1.5px;text-transform:uppercase;padding:12px 24px;border:2px solid var(--gg-color-dark-brown,#3a2e25);text-decoration:none;white-space:nowrap}}
.gg-course-bundle-cta:hover{{background:var(--gg-color-teal,#178079);border-color:var(--gg-color-teal,#178079)}}

/* ── Course Index ── */
.gg-course-index{{padding:80px 24px 60px}}
.gg-course-index-inner{{max-width:960px;margin:0 auto}}
.gg-course-index h1{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:clamp(2rem,4vw,2.8rem);color:var(--gg-color-dark-brown,#3a2e25);text-align:center;margin:0 0 12px}}
.gg-course-index-subtitle{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);color:var(--gg-color-primary-brown,#59473c);text-align:center;margin:0 0 48px;font-size:1.1rem}}
.gg-course-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px}}
.gg-course-card{{background:var(--gg-color-warm-paper,#f5efe6);border:1px solid var(--gg-color-tan,#d4c5b9);border-radius:4px;padding:32px 24px;text-decoration:none;color:inherit;transition:border-color .2s,box-shadow .2s}}
.gg-course-card:hover{{border-color:var(--gg-color-teal,#178079);box-shadow:0 2px 12px rgba(26,138,130,.1)}}
.gg-course-card-title{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.25rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 8px}}
.gg-course-card-subtitle{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:.9rem;color:var(--gg-color-primary-brown,#59473c);margin:0 0 16px}}
.gg-course-card-meta{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#7d695d);display:flex;gap:16px}}

/* ── Responsive ── */
@media(max-width:600px){{
  .gg-course-hero{{padding:60px 20px 40px}}
  .gg-course-gate-inner{{padding:32px 24px}}
  .gg-course-nav-btn{{max-width:100%}}
  .gg-course-nav--top .gg-course-nav-title{{display:none}}
  .gg-streak-badge{{position:static;margin-top:12px;display:inline-flex}}
  .gg-xp-toast{{bottom:12px;right:12px;font-size:12px}}
}}

/* ── PWA Standalone Mode ── */
@media(display-mode:standalone){{
  .gg-site-header{{padding-top:env(safe-area-inset-top,0)}}
  .gg-pwa-banner{{display:none!important}}
}}
"""


# ── JavaScript ───────────────────────────────────────────────

# Calculator compute module for course lesson pages. Plain string (not an
# f-string) so JS braces don't need doubling. Appended to build_course_js().
# Every calculator_id used in data/courses/*/lessons/*.json must have a
# dispatch branch here — tests/test_course_blocks.py enforces this.
_COURSE_CALC_JS = """
/* ── Course Calculators ── */
(function(){
  function num(calc,id){
    var el=calc.querySelector('#gg-calc-'+id);
    if(!el||el.value==='')return null;
    var v=parseFloat(el.value);
    return isNaN(v)?null:v;
  }
  function sel(calc,id){
    var el=calc.querySelector('#gg-calc-'+id);
    return el?el.value:null;
  }
  function markErr(calc,id){
    var el=calc.querySelector('#gg-calc-'+id);
    if(el)el.classList.add('gg-guide-calc-input--error');
  }
  function clearErrors(calc){
    calc.querySelectorAll('.gg-guide-calc-input--error').forEach(function(el){el.classList.remove('gg-guide-calc-input--error');});
    var errEl=calc.querySelector('.gg-guide-calc-error');
    if(errEl){errEl.style.display='none';errEl.textContent='';}
  }
  function showError(calc,msg){
    var errEl=calc.querySelector('.gg-guide-calc-error');
    if(errEl){errEl.textContent=msg;errEl.style.display='block';}
  }
  function setOut(calc,id,t){
    var el=calc.querySelector('#gg-calc-out-'+id);
    if(el)el.textContent=t;
  }
  function showOutput(calc){
    var out=calc.querySelector('.gg-guide-calc-output');
    if(out)out.style.display='block';
  }
  /* fields: [[id,min,max],...] — returns {id:value} or null (marks errors) */
  function requireAll(calc,fields){
    var vals={},ok=true;
    fields.forEach(function(f){
      var v=num(calc,f[0]);
      if(v===null||v<f[1]||v>f[2]){markErr(calc,f[0]);ok=false;}
      vals[f[0]]=v;
    });
    return ok?vals:null;
  }

  /* Lesson: Sweat Rate Science.
     sweat_rate_oz = ((pre - post) * 16 + fluid_consumed) / ride_duration */
  function computeSweatRate(calc){
    var v=requireAll(calc,[['pre_weight',80,400],['post_weight',80,400],['fluid_consumed',0,200],['ride_duration',0.5,8]]);
    if(!v){showError(calc,'Fill in all fields with valid numbers.');return;}
    var rate=((v.pre_weight-v.post_weight)*16+v.fluid_consumed)/v.ride_duration;
    if(rate<=0){showError(calc,'That math gives a zero or negative sweat rate \\u2014 post-ride weight should normally be lower than pre-ride. Double-check your numbers.');return;}
    setOut(calc,'sweat_rate_oz',(Math.round(rate*10)/10)+' oz/hr');
    setOut(calc,'sweat_rate_liters',(rate*0.0295735).toFixed(2)+' L/hr');
    showOutput(calc);
  }

  /* Lesson: Building Your Hydration Plan.
     Temp multiplier on sweat rate (~15-20% per 10\\u00B0F above 70\\u00B0F per the
     lesson), 75% replacement target (lesson teaches 70-80%), 24 oz bottles. */
  function computeHydrationPlan(calc){
    var v=requireAll(calc,[['sweat_rate_oz',12,80],['race_duration',1,24],['aid_station_interval',0.5,8]]);
    if(!v){showError(calc,'Fill in all fields with valid numbers.');return;}
    var mult={cool:0.8,mild:1.0,warm:1.15,hot:1.3}[sel(calc,'temperature')]||1.0;
    var adjusted=v.sweat_rate_oz*mult;
    var perHour=adjusted*0.75;
    var total=perHour*v.race_duration;
    var bottles=Math.max(1,Math.ceil(perHour*v.aid_station_interval/24));
    var refills=Math.max(0,Math.ceil(total/(bottles*24))-1);
    setOut(calc,'total_fluid_oz',Math.round(total)+' oz');
    setOut(calc,'fluid_per_hour',Math.round(perHour)+' oz/hr');
    setOut(calc,'bottles_needed',bottles+(bottles===1?' bottle':' bottles'));
    setOut(calc,'refill_count',refills+(refills===1?' refill':' refills'));
    showOutput(calc);
  }

  /* Dirt Craft L03: pressure window baseline.
     base = weight*0.18, tire/rim volume adjustment, surface modifier,
     front = base - 2, rear = base + 1, window = \\u00B13 PSI. */
  function computePressureBaseline(calc){
    var v=requireAll(calc,[['rider_weight',100,300]]);
    if(!v){showError(calc,'Enter your total rider weight (100-300 lbs).');return;}
    var tw=parseFloat(sel(calc,'tire_width'))||42;
    var rw=parseFloat(sel(calc,'rim_width'))||23;
    var mod={hardpack:3,loose_over_hard:-2,chunky:-3,sand_mud:-5,mixed:0}[sel(calc,'surface_type')]||0;
    var base=v.rider_weight*0.18+(40-tw)*0.3+(23-rw)*0.25+mod;
    var frontRec=Math.max(15,Math.round(base-2));
    var rearRec=Math.max(16,Math.round(base+1));
    setOut(calc,'front_recommended',frontRec+' PSI');
    setOut(calc,'front_min',(frontRec-3)+' PSI');
    setOut(calc,'front_max',(frontRec+3)+' PSI');
    setOut(calc,'rear_recommended',rearRec+' PSI');
    setOut(calc,'rear_min',(rearRec-3)+' PSI');
    setOut(calc,'rear_max',(rearRec+3)+' PSI');
    showOutput(calc);
  }

  /* Dirt Craft L06: corner speed.
     v_max = sqrt(mu * g * radius), recommended = 85% of max. */
  function computeCornerSpeed(calc){
    var v=requireAll(calc,[['radius',2,200],['tire_width',28,60],['lean_angle',5,40]]);
    if(!v){showError(calc,'Fill in all fields with valid numbers.');return;}
    var mu={dry_hardpack:0.55,wet_hardpack:0.35,loose_gravel:0.30,wet_loose:0.20,sand:0.15,mud:0.10}[sel(calc,'surface_type')]||0.30;
    var vmax=Math.sqrt(mu*9.81*v.radius)*2.23694;
    var rec=vmax*0.85;
    var leanFrac=Math.tan(v.lean_angle*Math.PI/180)/mu;
    var used=Math.max(0.7225,leanFrac);
    var reserve=Math.round((1-used)*100);
    var tm=reserve>0?('~'+reserve+'% of available grip in reserve'):'NONE \\u2014 that lean angle exceeds available grip on this surface. Slow down or stand the bike up.';
    setOut(calc,'max_speed_mph',vmax.toFixed(1)+' mph');
    setOut(calc,'recommended_speed_mph',rec.toFixed(1)+' mph');
    setOut(calc,'traction_margin',tm);
    showOutput(calc);
  }

  /* Dirt Craft L07: gearing check.
     Fatigued power = 65% FTP. Speed from power vs gravity + ~15%
     rolling/drivetrain losses. Cadence from speed, gear ratio, wheel
     circumference. Verdict thresholds: 65+ comfortable, 55-65 warning,
     <55 undergeared. race_slug input is notes-only and ignored. */
  function computeGearingCheck(calc){
    var v=requireAll(calc,[['ftp',80,500],['rider_bike_mass',50,160],['chainring',28,54],['largest_cog',25,52],['max_gradient',3,30],['wheel_diameter',650,750]]);
    if(!v){showError(calc,'Fill in all numeric fields. The race field is optional \\u2014 gradient comes from the Max Gradient input.');return;}
    var fp=v.ftp*0.65;
    var speedMs=fp/(1.15*v.rider_bike_mass*9.81*(v.max_gradient/100));
    var ratio=v.chainring/v.largest_cog;
    var circ=Math.PI*v.wheel_diameter/1000;
    var cadence=speedMs/(ratio*circ)*60;
    var torque=fp*60/(2*Math.PI*cadence);
    var verdict;
    if(cadence>=65)verdict='ADEQUATE \\u2014 cadence stays above 65 RPM at fatigued power on the max gradient.';
    else if(cadence>=55)verdict='MARGINAL \\u2014 55-65 RPM warning zone. Rideable, but you have no reserve when the surface gets loose.';
    else verdict='UNDERGEARED \\u2014 you\\u2019ll grind below 55 RPM, risking traction loss and walk-offs. Consider a bigger cog or smaller chainring.';
    setOut(calc,'easiest_gear_ratio',ratio.toFixed(2));
    setOut(calc,'fatigued_power',Math.round(fp)+' W');
    setOut(calc,'speed_at_max_gradient',(speedMs*2.23694).toFixed(1)+' mph');
    setOut(calc,'cadence_at_max_gradient',Math.round(cadence)+' RPM');
    setOut(calc,'torque_per_stroke',Math.round(torque)+' Nm');
    setOut(calc,'adequacy_verdict',verdict);
    showOutput(calc);
  }

  /* Dirt Craft L08: race tire pressure window.
     Silca-style base from rider weight + tire width, front 2-3 PSI below
     rear, wet -2 to -4 PSI, altitude -1 PSI per 3,000 ft, floors by tire
     type. race_slug input is notes-only and ignored. */
  function computeTirePressureWindow(calc){
    var v=requireAll(calc,[['rider_weight',90,350],['tire_width',28,55],['surface_loose_pct',0,100],['altitude_ft',0,14000]]);
    if(!v){showError(calc,'Fill in all numeric fields. The race field is optional \\u2014 course data comes from the manual inputs.');return;}
    var surface=sel(calc,'surface_primary')||'mixed';
    var mod={'hardpack':3,'loose-over-hard':-2,'mixed':0,'sand/mud':-5,'washboard':-3}[surface]||0;
    var base=v.rider_weight*0.18+(40-v.tire_width)*0.3+mod-(v.surface_loose_pct/100)*2;
    var altAdj=-Math.floor(v.altitude_ft/3000);
    var frontDry=Math.max(15,Math.round(base-2+altAdj));
    var rearDry=Math.max(16,Math.round(base+1+altAdj));
    var weather=sel(calc,'expected_weather')||'dry';
    var wetDelta={dry:0,chance_of_rain:-1,wet:-2,mud_likely:-4}[weather]||0;
    setOut(calc,'front_pressure_dry',frontDry+' PSI');
    setOut(calc,'rear_pressure_dry',rearDry+' PSI');
    if(wetDelta===0){
      setOut(calc,'front_pressure_wet','No change (dry forecast)');
      setOut(calc,'rear_pressure_wet','No change (dry forecast)');
    }else{
      setOut(calc,'front_pressure_wet',(frontDry+wetDelta)+' PSI ('+wetDelta+')');
      setOut(calc,'rear_pressure_wet',(rearDry+wetDelta)+' PSI ('+wetDelta+')');
    }
    setOut(calc,'altitude_note',altAdj<0?(altAdj+' PSI applied (\\u22121 PSI per 3,000 ft of altitude)'):'No altitude adjustment below 3,000 ft');
    var tireType=sel(calc,'tire_type')||'tubeless';
    var floor=frontDry-4;
    if(tireType==='tubeless_with_insert')floor=frontDry-8;
    else if(tireType==='tubed')floor=frontDry+1;
    setOut(calc,'pressure_floor',Math.max(12,floor)+' PSI \\u2014 below this you risk '+(tireType==='tubed'?'pinch flats':'rim strikes and burping'));
    setOut(calc,'surface_breakdown',surface+', ~'+Math.round(v.surface_loose_pct)+'% loose (manual entry)');
    var riskNote={dry:'Dry forecast \\u2014 no wet adjustment applied.',chance_of_rain:'Rain possible \\u2014 \\u22121 PSI hedge applied to wet numbers.',wet:'Wet course \\u2014 \\u22122 PSI applied for the wet numbers.',mud_likely:'Mud likely \\u2014 \\u22124 PSI applied for the wet numbers.'}[weather]||'';
    setOut(calc,'climate_risk_note',riskNote);
    showOutput(calc);
  }

  document.querySelectorAll('.gg-guide-calculator').forEach(function(calc){
    var calcType=calc.getAttribute('data-calc-type');
    var btn=calc.querySelector('.gg-guide-calc-btn');
    if(!btn)return;
    btn.addEventListener('click',function(){
      clearErrors(calc);
      if(calcType==='gravel-hydration-mastery-sweat-rate')computeSweatRate(calc);
      else if(calcType==='gravel-hydration-mastery-race-plan')computeHydrationPlan(calc);
      else if(calcType==='dirt-craft-pressure-baseline')computePressureBaseline(calc);
      else if(calcType==='dirt-craft-corner-speed')computeCornerSpeed(calc);
      else if(calcType==='dirt-craft-gearing-check')computeGearingCheck(calc);
      else if(calcType==='dirt-craft-tire-pressure')computeTirePressureWindow(calc);
      else return;
      if(typeof gtag==='function'){gtag('event','course_calculator_use',{calc_type:calcType});}
    });
  });
})();
"""


# Lesson-player UX module (Rise-style). Plain string (not an f-string) so JS
# braces don't need doubling. Appended to build_course_js().
_COURSE_PLAYER_JS = """
/* ── Course Player UX (outline drawer, entrance animations, lightbox, stepper) ── */
(function(){
  var REDUCED=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var lessonEl=document.getElementById('gg-course-lesson');
  var COURSE_ID=lessonEl?(lessonEl.getAttribute('data-course-id')||''):'';

  /* ── Outline drawer (mobile/tablet off-canvas sidebar) ── */
  (function(){
    var sidebar=document.getElementById('gg-course-sidebar');
    var toggle=document.getElementById('gg-course-outline-toggle');
    var scrim=document.getElementById('gg-course-scrim');
    var chip=document.getElementById('gg-course-chip');
    if(!sidebar) return;
    function isOpen(){return sidebar.classList.contains('gg-course-sidebar-open');}
    function openDrawer(){
      sidebar.classList.add('gg-course-sidebar-open');
      if(scrim) scrim.classList.add('gg-course-scrim-show');
      if(toggle) toggle.setAttribute('aria-expanded','true');
      /* Manual user interaction — never fired on timers/scroll */
      if(typeof gtag==='function'){gtag('event','course_outline_open',{course_id:COURSE_ID});}
    }
    function closeDrawer(){
      sidebar.classList.remove('gg-course-sidebar-open');
      if(scrim) scrim.classList.remove('gg-course-scrim-show');
      if(toggle) toggle.setAttribute('aria-expanded','false');
    }
    if(toggle) toggle.addEventListener('click',function(){isOpen()?closeDrawer():openDrawer();});
    if(chip) chip.addEventListener('click',function(){isOpen()?closeDrawer():openDrawer();});
    if(scrim) scrim.addEventListener('click',closeDrawer);
    document.addEventListener('keydown',function(e){if(e.key==='Escape'&&isOpen()) closeDrawer();});
  })();

  /* ── Entrance animations — NON-TEXT blocks only, progressive enhancement.
     Blocks are visible by default; hidden state only applies once JS adds
     .gg-anim-ready to <body> (and only under prefers-reduced-motion:
     no-preference in the CSS). Prose is never targeted. ── */
  (function(){
    if(REDUCED) return;
    if(!('IntersectionObserver' in window)) return;
    var NON_TEXT_BLOCKS=['.gg-guide-img','.gg-guide-hero-stat','.gg-guide-blackbox',
      '.gg-guide-callout','.gg-guide-drill','.gg-guide-tool','.gg-guide-process-list',
      '.gg-guide-calculator','.gg-guide-knowledge-check','.gg-guide-sensation',
      '.gg-guide-commitment','.gg-guide-recovery','.gg-guide-scenario',
      '.gg-guide-flashcard-deck','.gg-guide-zone-viz','.gg-guide-table-wrap',
      '.gg-guide-timeline','.gg-guide-labeled-graphic','.gg-guide-sorting'];
    var sel=NON_TEXT_BLOCKS.map(function(s){return '.gg-course-lesson-body '+s;}).join(',');
    var targets=document.querySelectorAll(sel);
    if(!targets.length) return;
    targets.forEach(function(el){el.classList.add('gg-course-anim');});
    document.body.classList.add('gg-anim-ready');
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(en){
        if(en.isIntersecting){en.target.classList.add('gg-anim-in');io.unobserve(en.target);}
      });
    },{threshold:0.15});
    targets.forEach(function(el){io.observe(el);});
  })();

  /* ── Image lightbox — content images only, no external lib ── */
  (function(){
    var imgs=document.querySelectorAll('.gg-course-lesson-body .gg-guide-img img.gg-guide-img-el');
    if(!imgs.length) return;
    var overlay=null,lbImg=null,closeBtn=null,lastFocus=null;
    function build(){
      overlay=document.createElement('div');
      overlay.className='gg-course-lightbox';
      overlay.setAttribute('role','dialog');
      overlay.setAttribute('aria-modal','true');
      overlay.setAttribute('aria-label','Image viewer');
      lbImg=document.createElement('img');
      lbImg.className='gg-course-lightbox-img';
      overlay.appendChild(lbImg);
      closeBtn=document.createElement('button');
      closeBtn.className='gg-course-lightbox-close';
      closeBtn.setAttribute('aria-label','Close image viewer');
      closeBtn.textContent='\\u00d7';
      overlay.appendChild(closeBtn);
      closeBtn.addEventListener('click',closeBox);
      overlay.addEventListener('click',function(e){
        if(e.target===overlay||e.target===lbImg) closeBox();
      });
      document.addEventListener('keydown',function(e){
        if(e.key==='Escape'&&overlay.classList.contains('gg-course-lightbox-open')) closeBox();
      });
      document.body.appendChild(overlay);
    }
    function openBox(el){
      if(!overlay) build();
      lbImg.src=el.currentSrc||el.src;
      lbImg.alt=el.getAttribute('alt')||'';
      overlay.classList.add('gg-course-lightbox-open');
      lastFocus=el;
      closeBtn.focus();
      /* Manual user interaction — never fired on timers/scroll */
      if(typeof gtag==='function'){gtag('event','course_lightbox_open',{course_id:COURSE_ID});}
    }
    function closeBox(){
      overlay.classList.remove('gg-course-lightbox-open');
      if(lastFocus) lastFocus.focus();
    }
    imgs.forEach(function(el){
      el.classList.add('gg-course-zoomable');
      el.setAttribute('tabindex','0');
      el.setAttribute('role','button');
      var alt=el.getAttribute('alt')||'';
      el.setAttribute('aria-label','Zoom image'+(alt?': '+alt:''));
      el.addEventListener('click',function(){openBox(el);});
      el.addEventListener('keydown',function(e){
        if(e.key==='Enter'||e.key===' '){e.preventDefault();openBox(el);}
      });
    });
  })();

  /* ── Process (named tool) paced stepper — stacked fallback if JS off.
     Desktop: step rail + active highlight. Mobile: one-at-a-time carousel
     with swipe + prev/next. ── */
  (function(){
    var tools=document.querySelectorAll('.gg-course-lesson-body .gg-guide-tool');
    tools.forEach(function(tool){
      var steps=Array.prototype.slice.call(tool.querySelectorAll('.gg-guide-tool-step'));
      if(steps.length<2) return;
      tool.classList.add('gg-tool-paced');
      var idx=0;
      var stepsWrap=tool.querySelector('.gg-guide-tool-steps');
      var rail=document.createElement('div');
      rail.className='gg-tool-rail';
      rail.setAttribute('aria-hidden','true');
      var dots=steps.map(function(){
        var d=document.createElement('span');
        d.className='gg-tool-rail-dot';
        rail.appendChild(d);
        return d;
      });
      var ctrl=document.createElement('div');
      ctrl.className='gg-tool-ctrl';
      var prev=document.createElement('button');
      prev.type='button';prev.className='gg-tool-ctrl-btn';
      prev.textContent='\\u2190 PREV';
      prev.setAttribute('aria-label','Previous step');
      var count=document.createElement('span');
      count.className='gg-tool-ctrl-count';
      count.setAttribute('aria-live','polite');
      var next=document.createElement('button');
      next.type='button';next.className='gg-tool-ctrl-btn';
      next.textContent='NEXT \\u2192';
      next.setAttribute('aria-label','Next step');
      ctrl.appendChild(prev);ctrl.appendChild(count);ctrl.appendChild(next);
      if(stepsWrap){tool.insertBefore(rail,stepsWrap);}
      tool.appendChild(ctrl);
      function render(){
        steps.forEach(function(s,i){s.classList.toggle('gg-step-active',i===idx);});
        dots.forEach(function(d,i){d.classList.toggle('gg-tool-rail-dot--on',i<=idx);});
        count.textContent='STEP '+(idx+1)+' / '+steps.length;
        prev.disabled=(idx===0);
        next.disabled=(idx===steps.length-1);
        /* Reaching the final step completes the stepper (continue gates) */
        if(idx===steps.length-1&&!tool.ggStepperDone){
          tool.ggStepperDone=true;
          tool.dispatchEvent(new CustomEvent('gg-block-complete',{bubbles:true}));
        }
      }
      prev.addEventListener('click',function(){if(idx>0){idx--;render();}});
      next.addEventListener('click',function(){if(idx<steps.length-1){idx++;render();}});
      var x0=null;
      if(stepsWrap){
        stepsWrap.addEventListener('touchstart',function(e){x0=e.touches[0].clientX;},{passive:true});
        stepsWrap.addEventListener('touchend',function(e){
          if(x0===null) return;
          var dx=e.changedTouches[0].clientX-x0;
          x0=null;
          if(Math.abs(dx)<40) return;
          if(dx<0&&idx<steps.length-1){idx++;render();}
          else if(dx>0&&idx>0){idx--;render();}
        },{passive:true});
      }
      render();
    });
  })();
})();
"""


# Rise-style blocks v2: labeled graphic hotspots, sorting activity, continue
# gates, fill-in-the-blank + matching knowledge checks. Plain string (not an
# f-string) so JS braces don't need doubling; __WORKER_URL__ / __COURSE_ID__
# placeholders are substituted in build_course_js().
_COURSE_BLOCKS_V2_JS = """
/* ── Rise Blocks v2 (labeled graphic, sorting, continue gate, FIB/matching KC) ── */
(function(){
  var WORKER_URL='__WORKER_URL__';
  var COURSE_ID='__COURSE_ID__';
  var LS_KEY='gg-course-'+COURSE_ID;
  var REDUCED=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function getAnswered(){
    try{return JSON.parse(localStorage.getItem('gg-kc-answered')||'{}');}catch(e){return {};}
  }
  function setAnswered(map){
    try{localStorage.setItem('gg-kc-answered',JSON.stringify(map));}catch(e){}
  }
  function showToast(text){
    var toast=document.getElementById('gg-xp-toast');
    if(!toast){
      toast=document.createElement('div');
      toast.id='gg-xp-toast';
      toast.className='gg-xp-toast';
      document.body.appendChild(toast);
    }
    toast.textContent=text;
    toast.classList.add('gg-xp-toast-show');
    setTimeout(function(){toast.classList.remove('gg-xp-toast-show');},3000);
  }
  /* Award XP exactly once per activity hash — same gg-kc-answered guard the
     multiple-choice knowledge checks use, so revisits never re-award. */
  function awardXP(hash){
    if(!hash) return;
    var answered=getAnswered();
    if(answered[hash]) return;
    answered[hash]={correct:true,at:new Date().toISOString()};
    setAnswered(answered);
    try{
      var c=JSON.parse(localStorage.getItem(LS_KEY)||'{}');
      var email=c.email;
      if(!email) return;
      var completeBtn=document.getElementById('gg-course-complete-btn');
      var lessonId=completeBtn?completeBtn.getAttribute('data-lesson-id'):'unknown';
      fetch(WORKER_URL+'/kc',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        email:email,course_id:COURSE_ID,lesson_id:lessonId,
        question_hash:hash,selected_index:0,correct:true
      })}).then(function(r){return r.json()}).then(function(d){
        if(d.xp_awarded>0) showToast('+'+d.xp_awarded+' XP');
      }).catch(function(){});
    }catch(e){}
  }
  function blockComplete(el){
    el.dispatchEvent(new CustomEvent('gg-block-complete',{bubbles:true}));
  }
  function revealExplanation(kc){
    var ex=kc.querySelector('.gg-guide-kc-explanation');
    if(ex){ex.style.display='block';ex.classList.add('gg-kc-reveal');}
  }

  /* ── Labeled graphic (hotspot) — markers shown + fallback list hidden
     only once JS adds .gg-lg-ready. Popovers are built with createElement
     + textContent, never markup injection. One open at a time; ESC and
     outside-click close; focus moves into the popover and returns. ── */
  document.querySelectorAll('.gg-guide-labeled-graphic').forEach(function(fig){
    var stage=fig.querySelector('.gg-guide-lg-stage');
    if(!stage) return;
    var markers=stage.querySelectorAll('.gg-guide-lg-marker');
    if(!markers.length) return;
    fig.classList.add('gg-lg-ready');
    var pop=null,openMarker=null;
    function close(focusBack){
      if(!pop) return;
      pop.remove();pop=null;
      if(openMarker){
        openMarker.setAttribute('aria-expanded','false');
        if(focusBack) openMarker.focus();
        openMarker=null;
      }
    }
    function open(btn){
      close(false);
      var idx=btn.getAttribute('data-lg-index');
      var item=fig.querySelector('.gg-guide-lg-item[data-lg-index="'+idx+'"]');
      if(!item) return;
      pop=document.createElement('div');
      pop.className='gg-guide-lg-popover';
      pop.setAttribute('role','dialog');
      pop.setAttribute('tabindex','-1');
      var titleEl=item.querySelector('.gg-guide-lg-item-title');
      var contentEl=item.querySelector('.gg-guide-lg-item-content');
      var detailEl=item.querySelector('.gg-guide-lg-item-detail');
      var h=document.createElement('div');
      h.className='gg-guide-lg-pop-title';
      h.textContent=titleEl?titleEl.textContent:'';
      pop.appendChild(h);
      pop.setAttribute('aria-label',h.textContent);
      var p=document.createElement('p');
      p.className='gg-guide-lg-pop-body';
      p.textContent=contentEl?contentEl.textContent:'';
      pop.appendChild(p);
      if(detailEl){
        var p2=document.createElement('p');
        p2.className='gg-guide-lg-pop-detail';
        p2.textContent=detailEl.textContent;
        pop.appendChild(p2);
      }
      var x=document.createElement('button');
      x.type='button';
      x.className='gg-guide-lg-pop-close';
      x.setAttribute('aria-label','Close');
      x.textContent='\\u00d7';
      x.addEventListener('click',function(){close(true);});
      pop.appendChild(x);
      /* Flip placement by marker quadrant so the card stays in view */
      var mx=parseFloat(btn.style.left)||50;
      var my=parseFloat(btn.style.top)||50;
      if(mx>50){pop.style.right=Math.min(96,100-mx+3)+'%';}
      else{pop.style.left=Math.min(96,mx+3)+'%';}
      if(my>55){pop.style.bottom=Math.min(96,100-my+4)+'%';}
      else{pop.style.top=Math.min(96,my+4)+'%';}
      stage.appendChild(pop);
      /* Post-placement clamp: if the card spills past the image edges,
         flip it above the marker or pin it inside the stage */
      if(pop.offsetTop+pop.offsetHeight>stage.clientHeight){
        pop.style.top='';
        pop.style.bottom=Math.max(2,Math.min(96,100-my+4))+'%';
      }
      if(pop.offsetTop<0){pop.style.bottom='';pop.style.top='2%';}
      if(pop.offsetLeft<0){pop.style.right='';pop.style.left='2%';}
      else if(pop.offsetLeft+pop.offsetWidth>stage.clientWidth){pop.style.left='';pop.style.right='2%';}
      if(pop.offsetTop+pop.offsetHeight>stage.clientHeight){
        pop.style.boxSizing='border-box';
        pop.style.maxHeight=Math.max(80,stage.clientHeight-pop.offsetTop-4)+'px';
      }
      btn.setAttribute('aria-expanded','true');
      openMarker=btn;
      pop.focus();
    }
    markers.forEach(function(btn){
      btn.addEventListener('click',function(e){
        e.stopPropagation();
        if(openMarker===btn) close(true);
        else open(btn);
      });
    });
    document.addEventListener('click',function(e){
      if(pop&&!pop.contains(e.target)) close(false);
    });
    document.addEventListener('keydown',function(e){
      if(e.key==='Escape'&&pop) close(true);
    });
  });

  /* ── Sorting activity — tap-to-sort card stack ── */
  document.querySelectorAll('.gg-guide-sorting').forEach(function(root){
    var cards=Array.prototype.slice.call(root.querySelectorAll('.gg-guide-sorting-card'));
    var cats=Array.prototype.slice.call(root.querySelectorAll('.gg-guide-sorting-cat'));
    var progress=root.querySelector('.gg-guide-sorting-progress');
    var doneEl=root.querySelector('.gg-guide-sorting-done');
    var hash=root.getAttribute('data-sorting-hash');
    if(!cards.length||!cats.length) return;
    root.classList.add('gg-sorting-ready');
    var counts={},idx=0,total=cards.length,busy=false;
    function setProgress(){
      if(progress) progress.textContent=Math.min(idx,total)+' / '+total+' sorted';
    }
    function showCard(i){
      cards.forEach(function(c,j){c.classList.toggle('gg-sorting-current',j===i);});
    }
    function finish(fresh){
      root.classList.add('gg-sorting-complete');
      showCard(-1);
      if(progress) progress.textContent='';
      if(doneEl){
        doneEl.hidden=false;
        doneEl.textContent=total+' / '+total+' sorted \\u2014 nice work.';
      }
      cats.forEach(function(b){b.disabled=true;});
      if(fresh) awardXP(hash);
      blockComplete(root);
    }
    var answered=getAnswered();
    if(hash&&answered[hash]){
      idx=total;setProgress();finish(false);return;
    }
    showCard(0);setProgress();
    cats.forEach(function(btn){
      btn.addEventListener('click',function(){
        if(busy||idx>=total) return;
        var card=cards[idx];
        var want=card.getAttribute('data-category');
        var got=btn.getAttribute('data-category');
        if(got===want){
          busy=true;
          counts[got]=(counts[got]||0)+1;
          btn.classList.add('gg-sorting-cat-hit');
          /* Teal check flash; the card flies to its pile (reduced motion:
             static teal confirm, no fly) */
          card.classList.add(REDUCED?'gg-sorting-correct':'gg-sorting-fly');
          setTimeout(function(){
            btn.classList.remove('gg-sorting-cat-hit');
            card.classList.remove('gg-sorting-correct','gg-sorting-fly');
            var cEl=btn.querySelector('.gg-guide-sorting-cat-count');
            if(cEl) cEl.textContent=String(counts[got]);
            idx++;setProgress();
            if(idx>=total) finish(true);
            else showCard(idx);
            busy=false;
          },REDUCED?120:450);
        }else{
          /* Wrong: red border flash always; shake only when motion is OK */
          card.classList.add('gg-sorting-wrong');
          if(!REDUCED) card.classList.add('gg-sorting-shake');
          setTimeout(function(){
            card.classList.remove('gg-sorting-wrong','gg-sorting-shake');
          },600);
        }
      });
    });
  });

  /* ── Knowledge check: fill-in-the-blank ── */
  document.querySelectorAll('.gg-guide-kc--fill-blank').forEach(function(kc){
    var wrap=kc.querySelector('.gg-guide-kc-fib');
    var input=kc.querySelector('.gg-guide-kc-fib-input');
    var btn=kc.querySelector('.gg-guide-kc-fib-check');
    var status=kc.querySelector('.gg-guide-kc-fib-status');
    if(!wrap||!input||!btn) return;
    var accept=[];
    try{accept=JSON.parse(wrap.getAttribute('data-accept')||'[]');}catch(e){}
    var caseSensitive=wrap.getAttribute('data-case-sensitive')==='true';
    var hash=kc.getAttribute('data-question-hash');
    function lock(){
      kc.classList.add('gg-kc-done');
      input.disabled=true;btn.disabled=true;
      input.classList.add('gg-kc-fib-correct');
      revealExplanation(kc);
    }
    var answered=getAnswered();
    if(hash&&answered[hash]){lock();blockComplete(kc);return;}
    function check(){
      if(kc.classList.contains('gg-kc-done')) return;
      var v=input.value.trim();
      if(!v) return;
      var ok=accept.some(function(a){
        a=String(a).trim();
        return caseSensitive?v===a:v.toLowerCase()===a.toLowerCase();
      });
      if(ok){
        lock();
        if(status) status.textContent='Correct.';
        awardXP(hash);
        blockComplete(kc);
      }else{
        input.classList.add('gg-kc-fib-wrong');
        if(!REDUCED) input.classList.add('gg-kc-shake');
        if(status) status.textContent='Not quite \\u2014 try again.';
        setTimeout(function(){
          input.classList.remove('gg-kc-fib-wrong','gg-kc-shake');
        },600);
      }
    }
    btn.addEventListener('click',check);
    input.addEventListener('keydown',function(e){
      if(e.key==='Enter'){e.preventDefault();check();}
    });
  });

  /* ── Knowledge check: matching (tap-to-pair) ── */
  document.querySelectorAll('.gg-guide-kc--matching').forEach(function(kc){
    var lefts=Array.prototype.slice.call(kc.querySelectorAll('.gg-guide-kc-match-left'));
    var rights=Array.prototype.slice.call(kc.querySelectorAll('.gg-guide-kc-match-right'));
    if(!lefts.length||!rights.length) return;
    var hash=kc.getAttribute('data-question-hash');
    var selected=null,locked=0,total=lefts.length;
    function lockAll(){
      lefts.concat(rights).forEach(function(b){
        b.classList.add('gg-kc-match-locked');b.disabled=true;
      });
      kc.classList.add('gg-kc-done');
      revealExplanation(kc);
    }
    var answered=getAnswered();
    if(hash&&answered[hash]){lockAll();blockComplete(kc);return;}
    lefts.forEach(function(b){
      b.addEventListener('click',function(){
        if(b.classList.contains('gg-kc-match-locked')) return;
        lefts.forEach(function(o){o.classList.remove('gg-kc-match-selected');});
        b.classList.add('gg-kc-match-selected');
        selected=b;
      });
    });
    rights.forEach(function(b){
      b.addEventListener('click',function(){
        if(!selected||b.classList.contains('gg-kc-match-locked')) return;
        var sel=selected;
        if(b.getAttribute('data-match')===sel.getAttribute('data-pair')){
          sel.classList.remove('gg-kc-match-selected');
          [sel,b].forEach(function(o){
            o.classList.add('gg-kc-match-locked');
            if(!REDUCED) o.classList.add('gg-kc-flash');
            o.disabled=true;
          });
          selected=null;
          locked++;
          if(locked>=total){
            kc.classList.add('gg-kc-done');
            revealExplanation(kc);
            awardXP(hash);
            blockComplete(kc);
          }
        }else{
          [sel,b].forEach(function(o){
            o.classList.add('gg-kc-match-wrong');
            if(!REDUCED) o.classList.add('gg-kc-shake');
          });
          setTimeout(function(){
            [sel,b].forEach(function(o){
              o.classList.remove('gg-kc-match-wrong','gg-kc-shake');
            });
          },600);
        }
      });
    });
  });

  /* ── Continue gates — progressive enhancement: content after a gate is
     only wrapped/hidden HERE, after JS runs. With JS off, nothing is
     hidden. Passed gates persist in the course localStorage state. ── */
  (function(){
    var body=document.querySelector('.gg-course-lesson-body');
    if(!body) return;
    var gates=Array.prototype.slice.call(body.querySelectorAll('.gg-guide-continue-gate'));
    if(!gates.length) return;
    /* Gateable = interactive blocks with a completion signal. Never plain
       buttons, callouts, or commitments (Rise's rule). */
    var GATEABLE='.gg-guide-knowledge-check,.gg-guide-sorting,.gg-guide-accordion-item,.gg-guide-tool.gg-tool-paced';
    function loadState(){
      try{return JSON.parse(localStorage.getItem(LS_KEY)||'{}');}catch(e){return {};}
    }
    function gatePassed(h){
      var c=loadState();
      return !!(c.gates&&c.gates[h]);
    }
    function persistGate(h){
      try{
        var c=loadState();
        c.gates=c.gates||{};
        c.gates[h]=true;
        localStorage.setItem(LS_KEY,JSON.stringify(c));
      }catch(e){}
    }
    /* Seed completion state for activities answered on a previous visit */
    var answered=getAnswered();
    body.querySelectorAll('.gg-guide-knowledge-check').forEach(function(el){
      var h=el.getAttribute('data-question-hash');
      if(h&&answered[h]) el.ggBlockDone=true;
    });
    body.querySelectorAll('.gg-guide-sorting').forEach(function(el){
      var h=el.getAttribute('data-sorting-hash');
      if(h&&answered[h]) el.ggBlockDone=true;
    });
    /* Requirements per gate, computed BEFORE wrapping moves any nodes.
       block_above = nearest preceding gateable block; all_above = every
       gateable block since the previous gate. */
    var ordered=Array.prototype.slice.call(body.querySelectorAll(GATEABLE+',.gg-guide-continue-gate'));
    gates.forEach(function(gate){
      var pos=ordered.indexOf(gate);
      var req=[];
      for(var i=pos-1;i>=0;i--){
        var el=ordered[i];
        if(el.classList.contains('gg-guide-continue-gate')) break;
        req.push(el);
      }
      var mode=gate.getAttribute('data-gate-mode')||'none';
      if(mode==='none') gate.ggGateReq=[];
      else if(mode==='block_above') gate.ggGateReq=req.length?[req[0]]:[];
      else gate.ggGateReq=req;
    });
    /* Wrap + hide everything after each unpassed gate */
    gates.forEach(function(gate){
      var h=gate.getAttribute('data-gate-hash');
      if(gatePassed(h)){gate.classList.add('gg-gate-passed');return;}
      var wrap=document.createElement('div');
      wrap.className='gg-gate-wrap gg-gate-closed';
      wrap.setAttribute('aria-hidden','true');
      var n=gate.nextElementSibling;
      while(n){
        var next=n.nextElementSibling;
        wrap.appendChild(n);
        n=next;
      }
      gate.parentNode.appendChild(wrap);
      gate.ggGateWrap=wrap;
    });
    function satisfied(gate){
      var req=gate.ggGateReq||[];
      for(var i=0;i<req.length;i++){
        if(!req[i].ggBlockDone) return false;
      }
      return true;
    }
    function refresh(){
      gates.forEach(function(gate){
        if(!gate.ggGateWrap) return;
        var btn=gate.querySelector('.gg-guide-continue-btn');
        var hint=gate.querySelector('.gg-guide-continue-hint');
        var ok=satisfied(gate);
        if(btn) btn.disabled=!ok;
        if(hint){
          if(ok) hint.hidden=true;
          else{
            hint.hidden=false;
            var req=gate.ggGateReq||[];
            var isKC=req.length===1&&req[0].classList.contains('gg-guide-knowledge-check');
            hint.textContent=isKC?'Answer the check above to continue':'Complete the activities above to continue';
          }
        }
      });
    }
    function openGate(gate){
      var wrap=gate.ggGateWrap;
      if(!wrap) return;
      persistGate(gate.getAttribute('data-gate-hash'));
      gate.classList.add('gg-gate-passed');
      wrap.removeAttribute('aria-hidden');
      if(REDUCED){
        wrap.classList.remove('gg-gate-closed');
      }else{
        wrap.style.maxHeight='0px';
        wrap.classList.remove('gg-gate-closed');
        wrap.classList.add('gg-gate-opening');
        requestAnimationFrame(function(){
          wrap.style.maxHeight=wrap.scrollHeight+'px';
          setTimeout(function(){
            wrap.style.maxHeight='';
            wrap.classList.remove('gg-gate-opening');
          },480);
        });
      }
      gate.ggGateWrap=null;
      refresh();
    }
    document.addEventListener('gg-block-complete',function(e){
      if(e.target&&e.target.nodeType===1) e.target.ggBlockDone=true;
      refresh();
    });
    gates.forEach(function(gate){
      var btn=gate.querySelector('.gg-guide-continue-btn');
      if(!btn) return;
      btn.addEventListener('click',function(){
        if(btn.disabled||!satisfied(gate)) return;
        openGate(gate);
        /* Manual user interaction — never fired on timers/scroll */
        if(typeof gtag==='function'){gtag('event','course_gate_continue',{course_id:COURSE_ID});}
      });
    });
    refresh();
  })();
})();
"""


def build_course_js(course: dict, module_lesson_map: dict = None) -> str:
    """Return course client-side JS for gate logic, progress tracking,
    gamification (XP, streaks, levels), and interactive blocks."""
    slug = course["id"]
    total = course["total_lessons"]
    # Build module lesson map JSON for module completion detection
    mlm_json = json.dumps(module_lesson_map or {})
    return f"""/* ── Course Gate + Progress + Gamification ── */
(function(){{
  var WORKER_URL='{WORKER_URL}';
  var COURSE_ID='{esc(slug)}';
  var TOTAL_LESSONS={total};
  var LS_KEY='gg-course-'+COURSE_ID;
  var EXPIRY_DAYS=365;
  var MODULE_LESSONS={mlm_json};

  var LEVELS=[
    {{level:1,xp:0,name:'Gravel Curious'}},
    {{level:2,xp:50,name:'Dirt Dabbler'}},
    {{level:3,xp:150,name:'Gravel Grinder'}},
    {{level:4,xp:300,name:'Dust Demon'}},
    {{level:5,xp:500,name:'Gravel God'}}
  ];

  function getLevelInfo(xp){{
    var current=LEVELS[0];
    for(var i=0;i<LEVELS.length;i++){{if(xp>=LEVELS[i].xp)current=LEVELS[i];}}
    var next=null;
    for(var j=0;j<LEVELS.length;j++){{if(LEVELS[j].level===current.level+1){{next=LEVELS[j];break;}}}}
    return{{level:current.level,name:current.name,xpToNext:next?next.xp-xp:0,nextXP:next?next.xp:null,nextName:next?next.name:null}};
  }}

  var gate=document.getElementById('gg-course-gate');
  var lesson=document.getElementById('gg-course-lesson');
  if(!gate||!lesson) return;

  var courseState={{email:null,totalXP:0,currentStreak:0,level:-1,levelName:'Gravel Curious',completedLessons:[]}};

  /* ── XP Toast ── */
  var toastQueue=[];
  var toastActive=false;

  function showXPToast(text){{
    toastQueue.push(text);
    if(!toastActive) processToastQueue();
  }}

  function processToastQueue(){{
    if(!toastQueue.length){{toastActive=false;return;}}
    toastActive=true;
    var text=toastQueue.shift();
    var toast=document.getElementById('gg-xp-toast');
    if(!toast){{
      toast=document.createElement('div');
      toast.id='gg-xp-toast';
      toast.className='gg-xp-toast';
      document.body.appendChild(toast);
    }}
    toast.textContent=text;
    toast.classList.add('gg-xp-toast-show');
    setTimeout(function(){{
      toast.classList.remove('gg-xp-toast-show');
      setTimeout(processToastQueue,300);
    }},3000);
  }}

  /* ── Level-Up Overlay ── */
  function showLevelUp(level,name){{
    var overlay=document.getElementById('gg-levelup-overlay');
    if(!overlay) return;
    overlay.querySelector('.gg-levelup-title').textContent='Level '+level;
    overlay.querySelector('.gg-levelup-name').textContent=name;
    overlay.classList.add('gg-levelup-show');
    spawnConfetti(overlay.querySelector('.gg-levelup-card'));
  }}

  function spawnConfetti(container){{
    var colors=['#178079','#d4c5b9','#59473c','#A68E80','#ede4d8'];
    for(var i=0;i<30;i++){{
      var c=document.createElement('div');
      c.className='gg-confetti';
      c.style.left=Math.random()*100+'%';
      c.style.background=colors[Math.floor(Math.random()*colors.length)];
      c.style.animationDelay=Math.random()*0.5+'s';
      c.style.borderRadius=Math.random()>0.5?'50%':'0';
      container.appendChild(c);
      setTimeout(function(el){{el.remove()}},2000,c);
    }}
  }}

  /* ── Streak Badge ── */
  function updateStreakBadge(streak){{
    var badge=document.getElementById('gg-streak-badge');
    if(!badge) return;
    var countEl=badge.querySelector('.gg-streak-count');
    if(streak>0){{
      badge.classList.add('gg-streak-active');
      badge.classList.remove('gg-streak-none');
      if(countEl) countEl.textContent=streak+' day'+(streak===1?'':'s');
    }}else{{
      badge.classList.remove('gg-streak-active');
      badge.classList.add('gg-streak-none');
      if(countEl) countEl.textContent='No streak';
    }}
  }}

  /* ── XP + Level UI Updates ── */
  function updateGamificationUI(totalXP,streak,levelInfo){{
    courseState.totalXP=totalXP;
    courseState.currentStreak=streak;
    courseState.level=levelInfo?levelInfo.level:getLevelInfo(totalXP).level;
    courseState.levelName=levelInfo?levelInfo.name:getLevelInfo(totalXP).name;

    var info=levelInfo||getLevelInfo(totalXP);
    var levelEl=document.getElementById('gg-xp-level');
    if(levelEl) levelEl.textContent='LVL '+info.level+' — '+info.name;

    var countEl=document.getElementById('gg-xp-count');
    if(countEl) countEl.textContent=totalXP+' XP';

    var bar=document.getElementById('gg-xp-bar');
    if(bar&&info.nextXP){{
      var prevXP=LEVELS[info.level-1]?LEVELS[info.level-1].xp:0;
      var pct=Math.min(100,Math.round(((totalXP-prevXP)/(info.nextXP-prevXP))*100));
      bar.style.width=pct+'%';
    }}else if(bar){{
      bar.style.width='100%';
    }}

    var streakEl=document.getElementById('gg-xp-streak-val');
    if(streakEl) streakEl.textContent=streak>0?streak+' day'+(streak===1?'':'s'):'—';

    updateStreakBadge(streak);
  }}

  function updateCompletionRing(completed,total){{
    var pct=total>0?Math.round((completed/total)*100):0;
    var pctEl=document.getElementById('gg-ring-pct');
    if(pctEl) pctEl.textContent=pct+'%';
    var chipEl=document.getElementById('gg-course-chip-pct');
    if(chipEl) chipEl.textContent=pct+'%';
    var barPctEl=document.getElementById('gg-course-outline-pct');
    if(barPctEl) barPctEl.textContent=pct+'%';
    var circle=document.getElementById('gg-ring-circle');
    if(circle){{
      var r=20;var circ=2*Math.PI*r;
      circle.style.strokeDasharray=circ;
      circle.style.strokeDashoffset=circ-(circ*pct/100);
    }}
  }}

  /* ── Unlock Content ── */
  function unlockContent(email){{
    courseState.email=email;
    gate.style.display='none';
    lesson.classList.add('gg-course-unlocked');
    try{{localStorage.setItem(LS_KEY,JSON.stringify({{email:email,exp:Date.now()+EXPIRY_DAYS*86400000}}));}}catch(e){{}}
    loadProgress(email);
    fetchStats(email);
    if(typeof gtag==='function'){{gtag('event','course_unlock',{{course_id:COURSE_ID}});}}
  }}

  function showGateError(msg){{
    var errEl=document.getElementById('gg-course-gate-error');
    if(errEl){{errEl.textContent=msg;errEl.style.display='block';}}
  }}

  /* ── Fetch Stats ── */
  function fetchStats(email){{
    fetch(WORKER_URL+'/stats',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:email,course_id:COURSE_ID}})}}
    ).then(function(r){{return r.json()}}).then(function(d){{
      if(d.total_xp!==undefined){{
        updateGamificationUI(d.total_xp,d.current_streak,d.level);
      }}
    }}).catch(function(){{}});
  }}

  /* ── Load Progress ── */
  function loadProgress(email){{
    fetch(WORKER_URL+'/progress',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:email,course_id:COURSE_ID,action:'get',total_lessons:TOTAL_LESSONS}})}}
    ).then(function(r){{return r.json()}}).then(function(d){{
      if(d.completed_lessons){{
        courseState.completedLessons=d.completed_lessons;
        updateProgressUI(d.completed_lessons);
        updateCompletionRing(d.completed_lessons.length,TOTAL_LESSONS);
        try{{var c=JSON.parse(localStorage.getItem(LS_KEY)||'{{}}');c.completed=d.completed_lessons;localStorage.setItem(LS_KEY,JSON.stringify(c));}}catch(e){{}}
      }}
      if(d.total_xp!==undefined){{
        updateGamificationUI(d.total_xp,d.current_streak,d.level);
      }}
    }}).catch(function(){{}});
  }}

  function updateProgressUI(completedList){{
    var items=document.querySelectorAll('.gg-course-progress-list li');
    var count=0;
    items.forEach(function(li){{
      var lid=li.getAttribute('data-lesson-id');
      if(completedList.indexOf(lid)!==-1){{
        li.querySelector('.gg-check').textContent='\\u2713';
        count++;
      }}
    }});
    var pct=TOTAL_LESSONS>0?Math.round((count/TOTAL_LESSONS)*100):0;
    var bar=document.querySelector('.gg-course-progress-bar');
    if(bar) bar.style.width=pct+'%';

    var btn=document.getElementById('gg-course-complete-btn');
    var currentId=btn?btn.getAttribute('data-lesson-id'):'';
    if(btn&&completedList.indexOf(currentId)!==-1){{
      btn.textContent='\\u2713 COMPLETED';
      btn.classList.add('gg-completed');
      btn.disabled=true;
    }}
  }}

  /* ── Check localStorage cache ── */
  try{{
    var cached=JSON.parse(localStorage.getItem(LS_KEY)||'null');
    if(cached&&cached.email&&cached.exp>Date.now()){{
      unlockContent(cached.email);
      return;
    }}
  }}catch(e){{}}

  /* ── Check URL for ?purchase=success ── */
  var params=new URLSearchParams(window.location.search);
  if(params.get('purchase')==='success'){{
    document.getElementById('gg-course-gate-verify').style.display='block';
    document.getElementById('gg-course-gate-buy').style.display='none';
  }}

  /* ── Verify form submission ── */
  var verifyForm=document.getElementById('gg-course-verify-form');
  if(verifyForm){{
    verifyForm.addEventListener('submit',function(e){{
      e.preventDefault();
      var email=verifyForm.email.value.trim().toLowerCase();
      if(!email||!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)){{showGateError('Please enter a valid email.');return;}}
      if(verifyForm.website&&verifyForm.website.value){{return;}}
      var btn=verifyForm.querySelector('button');
      btn.textContent='VERIFYING...';btn.disabled=true;
      fetch(WORKER_URL+'/verify',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email:email,course_id:COURSE_ID,website:verifyForm.website.value}})}}
      ).then(function(r){{return r.json()}}).then(function(d){{
        if(d.has_access){{unlockContent(email);}}
        else{{showGateError('No purchase found for this email. Please use the email you checked out with.');btn.textContent='VERIFY PURCHASE';btn.disabled=false;}}
      }}).catch(function(){{showGateError('Verification failed. Please try again.');btn.textContent='VERIFY PURCHASE';btn.disabled=false;}});
    }});
  }}

  /* ── Mark Complete button ── */
  var completeBtn=document.getElementById('gg-course-complete-btn');
  if(completeBtn){{
    completeBtn.addEventListener('click',function(){{
      if(completeBtn.classList.contains('gg-completed')) return;
      var lessonId=completeBtn.getAttribute('data-lesson-id');
      try{{
        var c=JSON.parse(localStorage.getItem(LS_KEY)||'{{}}');
        var email=c.email;
        if(!email) return;

        /* Find which module this lesson belongs to */
        var moduleLessonIds=null;
        for(var mKey in MODULE_LESSONS){{
          if(MODULE_LESSONS[mKey].indexOf(lessonId)!==-1){{
            moduleLessonIds=MODULE_LESSONS[mKey];
            break;
          }}
        }}

        completeBtn.textContent='SAVING...';completeBtn.disabled=true;
        var payload={{email:email,course_id:COURSE_ID,lesson_id:lessonId,action:'complete',total_lessons:TOTAL_LESSONS}};
        if(moduleLessonIds) payload.module_lesson_ids=moduleLessonIds;

        var prevLevel=courseState.level;

        fetch(WORKER_URL+'/progress',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(payload)}}
        ).then(function(r){{return r.json()}}).then(function(d){{
          completeBtn.textContent='\\u2713 COMPLETED';
          completeBtn.classList.add('gg-completed');
          if(d.completed_lessons){{
            courseState.completedLessons=d.completed_lessons;
            updateProgressUI(d.completed_lessons);
            updateCompletionRing(d.completed_lessons.length,TOTAL_LESSONS);
          }}

          /* XP toasts */
          if(d.xp_events){{
            d.xp_events.forEach(function(evt){{
              if(evt.type==='lesson_complete') showXPToast('+'+evt.xp+' XP — Lesson Complete');
              else if(evt.type==='module_complete') showXPToast('+'+evt.xp+' XP — Module Bonus!');
              else if(evt.type==='course_complete') showXPToast('+'+evt.xp+' XP — Course Complete!');
            }});
          }}

          if(d.total_xp!==undefined){{
            updateGamificationUI(d.total_xp,d.current_streak,d.level);
            /* Check for level up — only if stats were already loaded (prevLevel > 0) */
            var newLevel=d.level?d.level.level:getLevelInfo(d.total_xp).level;
            var newName=d.level?d.level.name:getLevelInfo(d.total_xp).name;
            if(prevLevel>0&&newLevel>prevLevel) showLevelUp(newLevel,newName);
          }}

          /* Module complete card */
          var moduleCompleted=false;
          if(d.xp_events){{
            d.xp_events.forEach(function(evt){{
              if(evt.type==='module_complete'){{
                moduleCompleted=true;
                var mc=document.getElementById('gg-module-complete');
                if(mc) mc.classList.add('gg-module-complete-show');
              }}
            }});
          }}

          if(typeof gtag==='function'){{gtag('event','course_lesson_complete',{{course_id:COURSE_ID,lesson_id:lessonId}});}}

          /* Rise-style continue flow: brief completed state, then auto-advance.
             Skip when a level-up overlay or module-complete card needs attention. */
          var nextUrl=completeBtn.getAttribute('data-next-url');
          if(nextUrl){{
            setTimeout(function(){{
              var lu=document.getElementById('gg-levelup-overlay');
              if(lu&&lu.classList.contains('gg-levelup-show')) return;
              if(moduleCompleted) return;
              window.location.href=nextUrl;
            }},1600);
          }}
        }}).catch(function(){{completeBtn.textContent='MARK AS COMPLETE';completeBtn.disabled=false;}});
      }}catch(e){{}}
    }});
  }}

  /* ── Level-up dismiss ── */
  var levelUpBtn=document.getElementById('gg-levelup-btn');
  if(levelUpBtn){{
    levelUpBtn.addEventListener('click',function(){{
      document.getElementById('gg-levelup-overlay').classList.remove('gg-levelup-show');
    }});
  }}
}})();

/* ── Interactive Blocks (accordion, tabs, knowledge check with XP, flashcard, scenario) ── */
(function(){{
  var WORKER_URL='{WORKER_URL}';
  var COURSE_ID='{esc(slug)}';
  var LS_KEY='gg-course-'+COURSE_ID;

  var REDUCED_MOTION=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Accordion — one-open-at-a-time per group, animated height */
  function setAccordion(btn,open){{
    var body=btn.nextElementSibling;
    var icon=btn.querySelector('.gg-guide-accordion-icon');
    btn.setAttribute('aria-expanded',String(open));
    if(icon) icon.textContent=open?'\\u2212':'+';
    if(REDUCED_MOTION){{body.style.display=open?'block':'none';return;}}
    if(open){{
      body.style.display='block';
      body.style.overflow='hidden';
      body.style.maxHeight='0px';
      requestAnimationFrame(function(){{
        body.style.transition='max-height .25s ease-out';
        body.style.maxHeight=body.scrollHeight+'px';
        setTimeout(function(){{body.style.maxHeight='';body.style.overflow='';body.style.transition='';}},280);
      }});
    }}else{{
      body.style.overflow='hidden';
      body.style.maxHeight=body.scrollHeight+'px';
      requestAnimationFrame(function(){{
        body.style.transition='max-height .25s ease-out';
        body.style.maxHeight='0px';
        setTimeout(function(){{body.style.display='none';body.style.maxHeight='';body.style.overflow='';body.style.transition='';}},280);
      }});
    }}
  }}
  document.querySelectorAll('.gg-guide-accordion-trigger').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var expanded=btn.getAttribute('aria-expanded')==='true';
      if(!expanded){{
        /* Close any open sibling items in the same accordion run */
        var item=btn.closest('.gg-guide-accordion-item');
        function closeIfAccordion(node){{
          if(node&&node.classList&&node.classList.contains('gg-guide-accordion-item')){{
            var t=node.querySelector('.gg-guide-accordion-trigger');
            if(t&&t!==btn&&t.getAttribute('aria-expanded')==='true') setAccordion(t,false);
            return true;
          }}
          return false;
        }}
        var n=item.previousElementSibling;
        while(n&&closeIfAccordion(n)) n=n.previousElementSibling;
        n=item.nextElementSibling;
        while(n&&closeIfAccordion(n)) n=n.nextElementSibling;
        /* Opening an accordion counts as completing it (continue gates) */
        item.dispatchEvent(new CustomEvent('gg-block-complete',{{bubbles:true}}));
      }}
      setAccordion(btn,!expanded);
    }});
  }});
  /* Tabs — ARIA tabs pattern with Left/Right arrow keys + crossfade */
  document.querySelectorAll('.gg-guide-tab-bar').forEach(function(bar){{
    var tabs=Array.prototype.slice.call(bar.querySelectorAll('.gg-guide-tab'));
    function activate(tab,focus){{
      tabs.forEach(function(t){{
        t.classList.remove('gg-guide-tab--active');
        t.setAttribute('aria-selected','false');
        t.setAttribute('tabindex','-1');
      }});
      tab.classList.add('gg-guide-tab--active');
      tab.setAttribute('aria-selected','true');
      tab.setAttribute('tabindex','0');
      if(focus) tab.focus();
      var group=bar.closest('.gg-guide-tabs');
      group.querySelectorAll('.gg-guide-tab-panel').forEach(function(p){{p.style.display='none';p.classList.remove('gg-tab-fade');}});
      var panel=document.getElementById(tab.getAttribute('data-tab'));
      if(panel){{panel.style.display='block';panel.classList.add('gg-tab-fade');}}
    }}
    tabs.forEach(function(tab,i){{
      tab.setAttribute('tabindex',tab.classList.contains('gg-guide-tab--active')?'0':'-1');
      tab.addEventListener('click',function(){{activate(tab,false);}});
      tab.addEventListener('keydown',function(e){{
        var dir=e.key==='ArrowRight'?1:(e.key==='ArrowLeft'?-1:0);
        if(!dir) return;
        e.preventDefault();
        activate(tabs[(i+dir+tabs.length)%tabs.length],true);
      }});
    }});
  }});
  /* Knowledge Check with per-choice feedback + XP integration */
  document.querySelectorAll('.gg-guide-kc-option').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var kc=btn.closest('.gg-guide-knowledge-check');
      if(kc.classList.contains('gg-kc-done')) return;
      kc.classList.add('gg-kc-done');
      /* Notify continue gates (and any listener) that this block is done */
      kc.dispatchEvent(new CustomEvent('gg-block-complete',{{bubbles:true}}));
      var questionHash=kc?kc.getAttribute('data-question-hash'):'';
      var isCorrect=btn.getAttribute('data-correct')==='true';
      var selectedIndex=parseInt(btn.getAttribute('data-index')||'0',10);

      kc.querySelectorAll('.gg-guide-kc-option').forEach(function(b){{
        var corr=b.getAttribute('data-correct')==='true';
        b.classList.add(corr?'gg-kc-opt-correct':'gg-kc-opt-dim');
        b.disabled=true;
      }});
      if(isCorrect){{btn.classList.add('gg-kc-flash');}}
      else{{btn.classList.add('gg-kc-shake');btn.classList.add('gg-kc-opt-wrong');btn.classList.remove('gg-kc-opt-dim');}}
      var ex=kc.querySelector('.gg-guide-kc-explanation');
      if(ex){{
        var fb=ex.querySelector('.gg-guide-kc-feedback[data-feedback-index="'+selectedIndex+'"]');
        var def=ex.querySelector('.gg-guide-kc-explanation-default');
        if(fb){{fb.style.display='block';if(def) def.style.display='none';}}
        ex.style.display='block';
        ex.classList.add('gg-kc-reveal');
      }}

      /* Send KC answer to worker for XP */
      if(questionHash){{
        var kcAnswered=JSON.parse(localStorage.getItem('gg-kc-answered')||'{{}}');
        if(kcAnswered[questionHash]) return; /* Already answered */

        try{{
          var c=JSON.parse(localStorage.getItem(LS_KEY)||'{{}}');
          var email=c.email;
          if(!email) return;

          /* Get lesson_id from the page */
          var completeBtn=document.getElementById('gg-course-complete-btn');
          var lessonId=completeBtn?completeBtn.getAttribute('data-lesson-id'):'unknown';

          fetch(WORKER_URL+'/kc',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{
            email:email,course_id:COURSE_ID,lesson_id:lessonId,
            question_hash:questionHash,selected_index:selectedIndex,correct:isCorrect
          }})}}).then(function(r){{return r.json()}}).then(function(d){{
            if(d.xp_awarded>0){{
              /* Show XP toast via global function */
              var toast=document.getElementById('gg-xp-toast');
              if(!toast){{
                toast=document.createElement('div');
                toast.id='gg-xp-toast';
                toast.className='gg-xp-toast';
                document.body.appendChild(toast);
              }}
              toast.textContent='+'+d.xp_awarded+' XP';
              toast.classList.add('gg-xp-toast-show');
              setTimeout(function(){{toast.classList.remove('gg-xp-toast-show')}},3000);
            }}
            /* Mark as answered locally */
            kcAnswered[questionHash]={{correct:isCorrect,at:new Date().toISOString()}};
            localStorage.setItem('gg-kc-answered',JSON.stringify(kcAnswered));
          }}).catch(function(){{}});
        }}catch(e){{}}
      }}
    }});
  }});
  /* Flashcard — flip-hint affordance hides after first interaction in a deck */
  document.querySelectorAll('.gg-guide-flashcard').forEach(function(card){{
    function flip(){{
      card.classList.toggle('gg-guide-flashcard--flipped');
      var deck=card.closest('.gg-guide-flashcard-deck');
      if(deck) deck.classList.add('gg-fc-touched');
    }}
    card.addEventListener('click',flip);
    card.addEventListener('keydown',function(e){{if(e.key==='Enter'||e.key===' '){{e.preventDefault();flip();}}}});
  }});
  /* Scenario */
  document.querySelectorAll('.gg-guide-scenario-option').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var scenario=btn.closest('.gg-guide-scenario');
      scenario.querySelectorAll('.gg-guide-scenario-option').forEach(function(b){{
        b.querySelector('.gg-guide-scenario-option-result').style.display='block';
        if(b.getAttribute('data-best')==='true') b.style.borderColor='var(--gg-color-teal,#178079)';
        else b.style.opacity='0.6';
        b.disabled=true;
      }});
    }});
  }});
}})();

/* ── PWA Install Banner ── */
(function(){{
  var deferredPrompt=null;
  window.addEventListener('beforeinstallprompt',function(e){{
    e.preventDefault();
    deferredPrompt=e;
    /* Show on 2nd visit */
    var visits=parseInt(localStorage.getItem('gg-pwa-visits')||'0',10)+1;
    localStorage.setItem('gg-pwa-visits',String(visits));
    if(visits>=2&&!localStorage.getItem('gg-pwa-dismissed')){{
      var banner=document.getElementById('gg-pwa-banner');
      if(banner) banner.classList.add('gg-pwa-banner-show');
    }}
  }});
  var installBtn=document.getElementById('gg-pwa-install-btn');
  if(installBtn){{
    installBtn.addEventListener('click',function(){{
      if(deferredPrompt){{
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then(function(){{
          deferredPrompt=null;
          var banner=document.getElementById('gg-pwa-banner');
          if(banner) banner.classList.remove('gg-pwa-banner-show');
        }});
      }}
    }});
  }}
  var dismissBtn=document.getElementById('gg-pwa-dismiss-btn');
  if(dismissBtn){{
    dismissBtn.addEventListener('click',function(){{
      localStorage.setItem('gg-pwa-dismissed','1');
      var banner=document.getElementById('gg-pwa-banner');
      if(banner) banner.classList.remove('gg-pwa-banner-show');
    }});
  }}
}})();

/* ── Service Worker Registration ── */
if('serviceWorker' in navigator){{
  navigator.serviceWorker.register('/course/sw.js').catch(function(){{}});
}}
""" + _COURSE_CALC_JS + _COURSE_PLAYER_JS + _COURSE_BLOCKS_V2_JS.replace(
        "__WORKER_URL__", WORKER_URL).replace("__COURSE_ID__", esc(slug))


# ── Page Builders ────────────────────────────────────────────


def build_og_meta(course: dict, og_title: str, og_desc: str, og_url: str,
                  og_type: str = "website") -> str:
    """Open Graph + Twitter card meta tags. og_image files live at
    /course/assets/{og_image} (wordpress/output/course/assets/)."""
    parts = [
        f'<meta property="og:title" content="{esc(og_title)}">',
        f'<meta property="og:description" content="{esc(og_desc)}">',
        f'<meta property="og:type" content="{esc(og_type)}">',
        f'<meta property="og:url" content="{esc(og_url)}">',
    ]
    og_image = course.get("og_image")
    if og_image:
        img_url = f"{SITE_BASE_URL}/course/assets/{og_image}"
        parts.append(f'<meta property="og:image" content="{esc(img_url)}">')
        parts.append('<meta name="twitter:card" content="summary_large_image">')
        parts.append(f'<meta name="twitter:image" content="{esc(img_url)}">')
    else:
        parts.append('<meta name="twitter:card" content="summary">')
    parts.append(f'<meta name="twitter:title" content="{esc(og_title)}">')
    parts.append(f'<meta name="twitter:description" content="{esc(og_desc)}">')
    return "\n  ".join(parts)


def get_bundle_payment_link() -> str:
    """Return the Academy bundle Stripe payment link from the manifest
    written by scripts/create_course_products.py, or "" if absent."""
    manifest_path = Path(__file__).resolve().parent.parent / "data" / "stripe-course-products.json"
    if not manifest_path.exists():
        return ""
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError):
        return ""
    for link in manifest.get("payment_links", []):
        if link.get("bundle") and link.get("url", "").startswith("https://buy.stripe.com/"):
            return link["url"]
    return ""


def build_bundle_strip(course: dict, all_courses: list) -> str:
    """Cross-sell strip pointing at the other course(s). CTA goes straight
    to the bundle Stripe payment link when one exists in the manifest,
    otherwise falls back to the /course/ index."""
    others = [c for c in (all_courses or []) if c["id"] != course["id"]]
    if not others:
        return ""
    bundle_link = get_bundle_payment_link()
    if len(others) == 1:
        other = others[0]
        copy = (f'Pair <strong>{esc(course["title"])}</strong> with '
                f'<a href="{SITE_BASE_URL}/course/{esc(other["id"])}/">'
                f'{esc(other["title"])}</a> &mdash; get both courses for $39 '
                f'at bundle checkout.')
    else:
        copy = (f'{esc(course["title"])} is one of {len(others) + 1} Gravel God '
                f'courses &mdash; bundle pricing available at checkout.')
    if bundle_link:
        cta = (f'<a href="{esc(bundle_link)}" class="gg-course-bundle-cta" '
               f'data-bundle-cta="1">GET THE 2-PACK &mdash; $39</a>')
    else:
        cta = f'<a href="{SITE_BASE_URL}/course/" class="gg-course-bundle-cta">VIEW ALL COURSES</a>'
    return f'''<div class="gg-course-bundle">
      <div>
        <p class="gg-course-bundle-kicker">BUNDLE &amp; SAVE</p>
        <p class="gg-course-bundle-copy">{copy}</p>
      </div>
      {cta}
    </div>'''


def build_landing_page(course: dict, all_courses: list = None) -> str:
    """Build the ungated course landing/sales page."""
    slug = course["id"]
    title = esc(course["title"])
    subtitle = esc(course["subtitle"])
    description = esc(course["description"])
    price = course["price_usd"]
    stripe_link = esc(course["stripe_payment_link"])
    canonical = f"{SITE_BASE_URL}/course/{slug}/"
    meta_desc = esc(course.get("meta_description", description))

    # What you'll learn
    learn_items = "\n".join(
        f'<li>{esc(item)}</li>' for item in course.get("what_youll_learn", [])
    )

    # Full curriculum — every module + lesson, with duration + lock icons
    modules_html = []
    lesson_num = 0
    for module in course["modules"]:
        lessons_html = []
        for lesson in module["lessons"]:
            lesson_num += 1
            est = lesson.get("est_minutes") or estimate_lesson_minutes(lesson)
            lessons_html.append(
                f'<li><span class="gg-course-lesson-num">{lesson_num:02d}</span> '
                f'<span class="gg-course-lesson-lock" aria-label="Locked until enrollment">&#128274;</span> '
                f'{esc(lesson["title"])} '
                f'<span class="gg-course-lesson-mins-landing">~{est} MIN</span></li>'
            )
        modules_html.append(f'''<div class="gg-course-module">
          <div class="gg-course-module-title">{esc(module["title"])}</div>
          <ul class="gg-course-module-lessons">{"".join(lessons_html)}</ul>
        </div>''')

    total_time_str = esc(format_course_total_time(course))
    bundle_html = build_bundle_strip(course, all_courses)

    # Instructor
    instructor = course.get("instructor", {})
    instructor_html = ""
    if instructor:
        instructor_html = f'''<div class="gg-course-instructor">
          <h2>YOUR INSTRUCTOR</h2>
          <div class="gg-course-instructor-name">{esc(instructor.get("name", ""))}</div>
          <div class="gg-course-instructor-title">{esc(instructor.get("title", ""))}</div>
          <p class="gg-course-instructor-bio">{esc(instructor.get("bio", ""))}</p>
        </div>'''

    header = get_site_header_html(active="products")
    mega_footer = get_mega_footer_html()

    tokens_css = get_tokens_css()
    font_css = get_font_face_css("/race/assets/fonts")
    preload = get_preload_hints("/race/assets/fonts")
    header_css = get_site_header_css()
    footer_css = get_mega_footer_css()
    course_css = build_course_css()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | Gravel God Cycling</title>
  <meta name="description" content="{meta_desc}">
  <link rel="canonical" href="{canonical}">
  {build_og_meta(course, f'{course["title"]} | Gravel God Cycling', course.get("meta_description", course["description"]), canonical, og_type="product")}
  <meta property="product:price:amount" content="{price}">
  <meta property="product:price:currency" content="USD">
  {preload}
  <style>
{font_css}
{tokens_css}
{header_css}
{course_css}
{footer_css}
  </style>
  {get_ga4_head_snippet()}
</head>
<body>
<div class="gg-course-page">
{header}

<div class="gg-course-hero">
  <div class="gg-course-hero-inner">
    <div class="gg-course-hero-badge">SELF-PACED COURSE</div>
    <h1>{title}</h1>
    <p class="gg-course-hero-subtitle">{subtitle}</p>
    <div class="gg-course-hero-price">${price}</div>
    <a href="{stripe_link}" class="gg-course-hero-cta">ENROLL NOW</a>
  </div>
</div>

<div class="gg-course-wrap">
  <div class="gg-course-desc">
    <p>{description}</p>
  </div>

  <div class="gg-course-learn">
    <h2>WHAT YOU&rsquo;LL LEARN</h2>
    <ul>{learn_items}</ul>
  </div>

  <div class="gg-course-outline">
    <h2>COURSE OUTLINE &mdash; {course["total_lessons"]} LESSONS</h2>
    <p class="gg-course-outline-total">{total_time_str}</p>
    {"".join(modules_html)}
  </div>

  {instructor_html}

  {bundle_html}
</div>

<div class="gg-course-bottom-cta">
  <h2>Ready to start?</h2>
  <p>{course["total_lessons"]} interactive lessons. {total_time_str.capitalize()}. Lifetime access.</p>
  <a href="{stripe_link}" class="gg-course-hero-cta">ENROLL FOR ${price}</a>
</div>

{mega_footer}
</div>
<script>
{get_site_header_js()}
</script>
{get_consent_banner_html()}
</body>
</html>'''


def build_module_lesson_map(course: dict) -> dict:
    """Build a dict of module_title -> [lesson_ids] for module completion detection."""
    module_map = {}
    for module in course["modules"]:
        lesson_ids = [les["id"] for les in module["lessons"]]
        module_map[module["title"]] = lesson_ids
    return module_map


def build_lesson_page(course: dict, module: dict, lesson: dict,
                      lesson_idx: int, total: int,
                      flat_lessons: list) -> str:
    """Build a gated lesson page with gamification UI."""
    slug = course["id"]
    lesson_id = lesson["id"]
    lesson_title = esc(lesson["title"])
    course_title = esc(course["title"])
    canonical = f"{SITE_BASE_URL}/course/{slug}/lesson/{lesson_id}/"
    stripe_link = esc(course["stripe_payment_link"])
    price = course["price_usd"]

    # Build module lesson map for JS
    module_lesson_map = build_module_lesson_map(course)

    # Render blocks — set the lesson context first so renderers that need a
    # deterministic per-lesson seed (matching shuffle, gate hashes) are stable.
    set_lesson_context(lesson_id)
    blocks_html = "\n".join(render_block(block) for block in lesson.get("blocks", []))

    # Duration estimates for the header
    est_minutes = lesson.get("est_minutes") or estimate_lesson_minutes(lesson)
    drill_minutes = lesson.get("drill_minutes", lesson_drill_minutes(lesson))
    duration_html = f'<span class="gg-course-lesson-mins">~{est_minutes} MIN</span>'
    if drill_minutes > 0:
        duration_html += (f' <span class="gg-course-lesson-mins">+ ~{drill_minutes} MIN '
                          f'FIELD DRILLS</span>')

    # Sidebar outline — lessons grouped by MODULE, with checkmarks + durations
    outline_sections = []
    flat_idx = 0
    for mod in course["modules"]:
        items = []
        for les in mod["lessons"]:
            flat_idx += 1
            is_current = les["id"] == lesson_id
            current_cls = "gg-current" if is_current else ""
            aria_current = ' aria-current="page"' if is_current else ""
            link = f'{SITE_BASE_URL}/course/{slug}/lesson/{les["id"]}/'
            les_est = les.get("est_minutes") or estimate_lesson_minutes(les)
            items.append(
                f'<li class="{current_cls}" data-lesson-id="{esc(les["id"])}">'
                f'<span class="gg-check"></span>'
                f'<a href="{link}"{aria_current}>'
                f'{flat_idx:02d}. {esc(les["title"])}</a>'
                f'<span class="gg-lesson-mins">~{les_est} MIN</span></li>'
            )
        outline_sections.append(
            f'<div class="gg-course-sidebar-module">{esc(mod["title"])}</div>'
            f'<ul class="gg-course-progress-list">{"".join(items)}</ul>'
        )
    outline_html = "".join(outline_sections)

    # Prev/Next navigation — lesson titles on the buttons (Rise convention)
    next_url = ""
    prev_html = '<span class="gg-course-nav-spacer"></span>'
    next_html = ""
    if lesson_idx > 0:
        prev_lesson = flat_lessons[lesson_idx - 1][1]
        prev_url = f'{SITE_BASE_URL}/course/{slug}/lesson/{prev_lesson["id"]}/'
        prev_html = (
            f'<a href="{prev_url}" class="gg-course-nav-btn gg-course-nav-prev" rel="prev">'
            f'<span class="gg-course-nav-dir">&larr; PREVIOUS</span>'
            f'<span class="gg-course-nav-title">{esc(prev_lesson["title"])}</span></a>'
        )
    if lesson_idx < total - 1:
        next_lesson = flat_lessons[lesson_idx + 1][1]
        next_url = f'{SITE_BASE_URL}/course/{slug}/lesson/{next_lesson["id"]}/'
        next_html = (
            f'<a href="{next_url}" class="gg-course-nav-btn gg-course-nav-next" rel="next">'
            f'<span class="gg-course-nav-dir">NEXT &rarr;</span>'
            f'<span class="gg-course-nav-title">{esc(next_lesson["title"])}</span></a>'
        )

    def nav_block(position: str) -> str:
        return (f'<nav class="gg-course-nav gg-course-nav--{position}" '
                f'aria-label="Lesson navigation">{prev_html}{next_html}</nav>')

    header = get_site_header_html(active="products")
    mega_footer = get_mega_footer_html()

    tokens_css = get_tokens_css()
    font_css = get_font_face_css("/race/assets/fonts")
    preload = get_preload_hints("/race/assets/fonts")
    header_css = get_site_header_css()
    footer_css = get_mega_footer_css()
    course_css = build_course_css()
    course_js = build_course_js(course, module_lesson_map)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{lesson_title} | {course_title} | Gravel God</title>
  <meta name="description" content="{lesson_title} — Lesson {lesson_idx + 1} of {total} in {course_title}">
  <link rel="canonical" href="{canonical}">
  {build_og_meta(course, f'{lesson["title"]} | {course["title"]}', f'Lesson {lesson_idx + 1} of {total} in {course["title"]} — Gravel God Cycling.', canonical)}
  <meta name="robots" content="noindex">
  <link rel="manifest" href="/course/manifest.json">
  <meta name="theme-color" content="#178079">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  {preload}
  <style>
{font_css}
{tokens_css}
{header_css}
{course_css}
{footer_css}
  </style>
  {get_ga4_head_snippet()}
</head>
<body>
<div class="gg-course-page">
{header}

<!-- Purchase Gate -->
<div class="gg-course-gate" id="gg-course-gate">
  <div class="gg-course-gate-inner">
    <div id="gg-course-gate-buy">
      <div class="gg-course-gate-badge">PREMIUM COURSE</div>
      <h2>{course_title}</h2>
      <p>This lesson is part of a paid course. Enroll to get lifetime access to all {total} lessons.</p>
      <a href="{stripe_link}" class="gg-course-gate-cta">ENROLL FOR ${price}</a>
    </div>
    <div id="gg-course-gate-verify" style="display:none">
      <div class="gg-course-gate-badge">WELCOME BACK</div>
      <h2>Verify Your Purchase</h2>
      <p>Enter the email you used at checkout to access your course.</p>
    </div>
    <div class="gg-course-gate-divider">Already purchased?</div>
    <form class="gg-course-gate-form" id="gg-course-verify-form" autocomplete="off">
      <input type="hidden" name="website" value="">
      <input type="email" name="email" required placeholder="your@email.com">
      <button type="submit">VERIFY PURCHASE</button>
    </form>
    <div class="gg-course-gate-error" id="gg-course-gate-error"></div>
    <p class="gg-course-gate-fine">Use the email address from your Stripe checkout.</p>
  </div>
</div>

<!-- Lesson Content (hidden until unlocked) -->
<div class="gg-course-lesson" id="gg-course-lesson" data-course-id="{esc(slug)}">
  <div class="gg-course-lesson-header">
    <div class="gg-course-lesson-header-inner">
      <div class="gg-course-lesson-breadcrumb">
        <a href="{SITE_BASE_URL}/course/{slug}/">{course_title}</a>
        <span>&rsaquo;</span>
        <span>{esc(module["title"])}</span>
      </div>
      <div class="gg-course-lesson-num">LESSON {lesson_idx + 1:02d} OF {total:02d} &middot; {duration_html}</div>
      <h1>{lesson_title}</h1>
    </div>
    <!-- Streak Badge -->
    <div class="gg-streak-badge gg-streak-none" id="gg-streak-badge">
      <span class="gg-streak-fire">&#128293;</span>
      <span class="gg-streak-count">No streak</span>
    </div>
  </div>

  <!-- Mobile outline bar (pinned below the lesson header) -->
  <div class="gg-course-outline-bar">
    <button class="gg-course-outline-toggle" id="gg-course-outline-toggle"
            aria-expanded="false" aria-controls="gg-course-sidebar">
      <span aria-hidden="true">&#9776;</span> COURSE OUTLINE
    </button>
    <span class="gg-course-outline-bar-pct" id="gg-course-outline-pct">0%</span>
  </div>

  <div class="gg-course-layout">
    <!-- Sidebar: sticky outline on desktop, off-canvas drawer on mobile -->
    <aside class="gg-course-sidebar" id="gg-course-sidebar" aria-label="Course outline">
      <div class="gg-course-sidebar-inner">
        <a class="gg-course-sidebar-title" href="{SITE_BASE_URL}/course/{slug}/">{course_title}</a>

        <!-- Completion Ring -->
        <div class="gg-completion-ring">
          <svg class="gg-ring-svg" viewBox="0 0 48 48">
            <circle class="gg-ring-bg" cx="24" cy="24" r="20"/>
            <circle class="gg-ring-fill" id="gg-ring-circle" cx="24" cy="24" r="20"
                    stroke-dasharray="125.66" stroke-dashoffset="125.66"/>
          </svg>
          <div>
            <div class="gg-ring-pct" id="gg-ring-pct">0%</div>
            <div class="gg-ring-label">Complete</div>
          </div>
        </div>

        <div class="gg-course-progress-bar-wrap">
          <div class="gg-course-progress-bar"></div>
        </div>

        <nav class="gg-course-outline-nav" aria-label="Lessons by module">
          {outline_html}
        </nav>

        <!-- XP + Level Section -->
        <div class="gg-xp-section">
          <div class="gg-xp-header">
            <span class="gg-xp-level" id="gg-xp-level">LVL 1 — Gravel Curious</span>
            <span class="gg-xp-count" id="gg-xp-count">0 XP</span>
          </div>
          <div class="gg-xp-bar-wrap">
            <div class="gg-xp-bar" id="gg-xp-bar"></div>
          </div>
          <div class="gg-xp-streak-row">
            <span class="gg-xp-streak-label">Streak</span>
            <span class="gg-xp-streak-label" id="gg-xp-streak-val">&mdash;</span>
          </div>
        </div>
      </div>
    </aside>
    <div class="gg-course-scrim" id="gg-course-scrim"></div>

    <main class="gg-course-main">
      <div class="gg-course-main-inner">
        {nav_block("top")}

        <!-- Module Complete Card (hidden until triggered) -->
        <div class="gg-module-complete" id="gg-module-complete">
          <div class="gg-module-complete-badge">+25 XP MODULE BONUS</div>
          <div class="gg-module-complete-title">Module Complete: {esc(module["title"])}</div>
        </div>

        <div class="gg-course-lesson-body">
          {blocks_html}
        </div>

        <button class="gg-course-complete-btn" id="gg-course-complete-btn"
                data-lesson-id="{esc(lesson_id)}" data-next-url="{next_url}">
          MARK AS COMPLETE
        </button>

        {nav_block("bottom")}
      </div>
    </main>
  </div>

  <!-- Floating compact progress chip (mobile) -->
  <button class="gg-course-chip" id="gg-course-chip" aria-label="Course progress — open outline">
    <span class="gg-course-chip-pct" id="gg-course-chip-pct">0%</span>
    <span>DONE</span>
  </button>

  {mega_footer}
</div>

<!-- Level-Up Overlay -->
<div class="gg-levelup-overlay" id="gg-levelup-overlay">
  <div class="gg-levelup-card">
    <div class="gg-levelup-badge">LEVEL UP</div>
    <div class="gg-levelup-title">Level 2</div>
    <div class="gg-levelup-name">Dirt Dabbler</div>
    <button class="gg-levelup-btn" id="gg-levelup-btn">CONTINUE</button>
  </div>
</div>

<!-- PWA Install Banner -->
<div class="gg-pwa-banner" id="gg-pwa-banner">
  <span class="gg-pwa-banner-text">Install Gravel God Courses for offline access</span>
  <div>
    <button class="gg-pwa-banner-install" id="gg-pwa-install-btn">ADD TO HOME SCREEN</button>
    <button class="gg-pwa-banner-dismiss" id="gg-pwa-dismiss-btn">&times;</button>
  </div>
</div>

</div>
<script>
{get_site_header_js()}
</script>
<script>
{course_js}
</script>
{get_consent_banner_html()}
</body>
</html>'''


def build_course_index(courses: list) -> str:
    """Build the /course/ index page listing all courses."""
    cards_html = []
    for course in courses:
        slug = course["id"]
        title = esc(course["title"])
        subtitle = esc(course["subtitle"])
        price = course["price_usd"]
        total = course["total_lessons"]
        cards_html.append(f'''<a href="{SITE_BASE_URL}/course/{slug}/" class="gg-course-card">
          <div class="gg-course-card-title">{title}</div>
          <div class="gg-course-card-subtitle">{subtitle}</div>
          <div class="gg-course-card-meta">
            <span>${price}</span>
            <span>{total} lessons</span>
          </div>
        </a>''')

    header = get_site_header_html(active="products")
    mega_footer = get_mega_footer_html()
    tokens_css = get_tokens_css()
    font_css = get_font_face_css("/race/assets/fonts")
    preload = get_preload_hints("/race/assets/fonts")
    header_css = get_site_header_css()
    footer_css = get_mega_footer_css()
    course_css = build_course_css()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Courses | Gravel God Cycling</title>
  <meta name="description" content="Self-paced courses on hydration, nutrition, sports psychology, and strength for gravel racers.">
  <link rel="canonical" href="{SITE_BASE_URL}/course/">
  {preload}
  <style>
{font_css}
{tokens_css}
{header_css}
{course_css}
{footer_css}
  </style>
  {get_ga4_head_snippet()}
</head>
<body>
<div class="gg-course-page">
{header}
<div class="gg-course-index">
  <div class="gg-course-index-inner">
    <h1>Gravel God Courses</h1>
    <p class="gg-course-index-subtitle">Science-backed, self-paced courses built for gravel racers.</p>
    <div class="gg-course-grid">
      {"".join(cards_html)}
    </div>
  </div>
</div>
{mega_footer}
</div>
<script>
{get_site_header_js()}
</script>
{get_consent_banner_html()}
</body>
</html>'''


# ── PWA Files ─────────────────────────────────────────────────


def build_manifest_json() -> str:
    """Return the PWA manifest.json content."""
    return json.dumps({
        "name": "Gravel God Courses",
        "short_name": "GG Courses",
        "start_url": "/course/",
        "display": "standalone",
        "background_color": "#1a1612",
        "theme_color": "#178079",
        "icons": [
            {"src": "/course/icons/icon-192.svg", "sizes": "192x192", "type": "image/svg+xml"},
            {"src": "/course/icons/icon-512.svg", "sizes": "512x512", "type": "image/svg+xml"}
        ]
    }, indent=2)


def build_service_worker() -> str:
    """Return the service worker JS for offline support and caching."""
    return """/* Gravel God Courses — Service Worker */
const CACHE_NAME = 'gg-courses-v1';
const OFFLINE_URL = '/course/offline.html';
const API_PATHS = ['/verify', '/progress', '/kc', '/stats', '/leaderboard'];

// Install: cache offline fallback page
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll([OFFLINE_URL]))
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch strategy
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // API calls: network-first, queue offline submissions for replay
  if (API_PATHS.some(p => url.pathname.endsWith(p))) {
    event.respondWith(
      fetch(event.request.clone()).catch(async () => {
        // For POST requests, queue for background sync
        if (event.request.method === 'POST') {
          const body = await event.request.clone().text();
          await queueOfflineRequest(url.pathname, body);
          return new Response(JSON.stringify({
            queued: true,
            message: 'Saved offline — will sync when reconnected'
          }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' }
          });
        }
        return new Response(JSON.stringify({ error: 'Offline' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' }
        });
      })
    );
    return;
  }

  // HTML/CSS/fonts: cache-first with stale-while-revalidate
  if (event.request.method === 'GET') {
    event.respondWith(
      caches.match(event.request).then(cached => {
        const networkFetch = fetch(event.request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => {
          // Return offline page for navigation requests
          if (event.request.mode === 'navigate') {
            return caches.match(OFFLINE_URL);
          }
          return cached;
        });

        return cached || networkFetch;
      })
    );
  }
});

// Background sync: replay queued requests
self.addEventListener('sync', event => {
  if (event.tag === 'gg-course-sync') {
    event.waitUntil(replayOfflineRequests());
  }
});

// IndexedDB helpers for offline queue
function openDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('gg-course-offline', 1);
    req.onupgradeneeded = () => {
      req.result.createObjectStore('queue', { autoIncrement: true });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function queueOfflineRequest(path, body) {
  const db = await openDB();
  const tx = db.transaction('queue', 'readwrite');
  tx.objectStore('queue').add({ path, body, timestamp: Date.now() });
  await new Promise((resolve, reject) => {
    tx.oncomplete = resolve;
    tx.onerror = () => reject(tx.error);
  });
  // Register for background sync
  if (self.registration && self.registration.sync) {
    await self.registration.sync.register('gg-course-sync');
  }
}

async function replayOfflineRequests() {
  const db = await openDB();
  const tx = db.transaction('queue', 'readwrite');
  const store = tx.objectStore('queue');
  const allKeys = await new Promise(resolve => {
    const req = store.getAllKeys();
    req.onsuccess = () => resolve(req.result);
  });
  const allValues = await new Promise(resolve => {
    const req = store.getAll();
    req.onsuccess = () => resolve(req.result);
  });

  for (let i = 0; i < allValues.length; i++) {
    const item = allValues[i];
    try {
      const workerBase = 'https://course-access.gravelgodcoaching.workers.dev';
      await fetch(workerBase + item.path, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Origin': 'https://gravelgodcycling.com'
        },
        body: item.body
      });
      store.delete(allKeys[i]);
    } catch (e) {
      // Will retry on next sync
    }
  }
}
"""


def build_offline_page() -> str:
    """Return the offline fallback HTML page."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Offline | Gravel God Courses</title>
  <style>
    body {
      font-family: Georgia, serif;
      background: #1a1612;
      color: #ede4d8;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
      padding: 24px;
    }
    .offline-card {
      text-align: center;
      max-width: 400px;
    }
    .offline-card h1 {
      font-size: 1.5rem;
      margin: 0 0 16px;
    }
    .offline-card p {
      color: #A68E80;
      line-height: 1.6;
      margin: 0 0 24px;
    }
    .offline-card .icon {
      font-size: 48px;
      margin-bottom: 16px;
    }
    .offline-retry {
      display: inline-block;
      background: #178079;
      color: #fff;
      font-family: monospace;
      font-size: 12px;
      letter-spacing: 1.5px;
      text-transform: uppercase;
      padding: 12px 32px;
      border: none;
      border-radius: 2px;
      cursor: pointer;
      text-decoration: none;
    }
  </style>
</head>
<body>
  <div class="offline-card">
    <div class="icon">&#9889;</div>
    <h1>You're offline</h1>
    <p>Your progress will sync automatically when you reconnect. Any lessons or knowledge checks you complete offline will be saved.</p>
    <button class="offline-retry" onclick="window.location.reload()">TRY AGAIN</button>
  </div>
</body>
</html>"""


def generate_pwa_files(output_dir: Path):
    """Generate manifest.json, sw.js, offline.html, and placeholder icons."""
    # manifest.json
    (output_dir / "manifest.json").write_text(build_manifest_json(), encoding="utf-8")
    print("  course/manifest.json")

    # Service worker
    (output_dir / "sw.js").write_text(build_service_worker(), encoding="utf-8")
    print("  course/sw.js")

    # Offline fallback
    (output_dir / "offline.html").write_text(build_offline_page(), encoding="utf-8")
    print("  course/offline.html")

    # Placeholder icon directory
    icons_dir = output_dir / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)

    # Generate minimal SVG-based placeholder PNGs
    # (User should replace with real icons)
    for size in [192, 512]:
        icon_path = icons_dir / f"icon-{size}.png"
        if not icon_path.exists():
            # Create a minimal 1x1 PNG as placeholder
            # Real icons should be provided by the user
            svg_placeholder = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}"><rect fill="#178079" width="{size}" height="{size}"/><text x="50%" y="50%" text-anchor="middle" dy=".35em" fill="#fff" font-family="monospace" font-size="{size//4}">GG</text></svg>'
            (icons_dir / f"icon-{size}.svg").write_text(svg_placeholder, encoding="utf-8")
            print(f"  course/icons/icon-{size}.svg (placeholder — replace with PNG)")


# ── Generator ────────────────────────────────────────────────


def generate_course(course_dir: Path, output_dir: Path,
                    all_courses: list = None) -> int:
    """Generate all pages for a single course. Returns lesson count."""
    course = load_course(course_dir)
    if not course:
        return 0

    slug = course["id"]
    flat_lessons = get_flat_lessons(course)
    total = len(flat_lessons)

    # Landing page
    landing_dir = output_dir / slug
    landing_dir.mkdir(parents=True, exist_ok=True)
    landing_html = build_landing_page(course, all_courses=all_courses)
    (landing_dir / "index.html").write_text(landing_html, encoding="utf-8")
    print(f"  {slug}/index.html (landing page)")

    # Lesson pages
    for idx, (module, lesson) in enumerate(flat_lessons):
        lesson_dir = landing_dir / "lesson" / lesson["id"]
        lesson_dir.mkdir(parents=True, exist_ok=True)
        lesson_html = build_lesson_page(course, module, lesson, idx, total, flat_lessons)
        (lesson_dir / "index.html").write_text(lesson_html, encoding="utf-8")
        print(f"  {slug}/lesson/{lesson['id']}/index.html")

    # Course-local image assets (data/courses/{slug}/assets/ → /course/{slug}/assets/)
    assets_src = course_dir / "assets"
    if assets_src.is_dir():
        assets_out = landing_dir / "assets"
        assets_out.mkdir(parents=True, exist_ok=True)
        copied = 0
        for asset in sorted(assets_src.iterdir()):
            if asset.is_file() and not asset.name.startswith("."):
                (assets_out / asset.name).write_bytes(asset.read_bytes())
                copied += 1
        print(f"  {slug}/assets/ ({copied} files)")

    return total


def main():
    parser = argparse.ArgumentParser(
        description="Generate Gravel God Course pages."
    )
    parser.add_argument(
        "--course", default=None,
        help="Generate a single course by slug (e.g., gravel-hydration-mastery)"
    )
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR),
        help=f"Output directory (default: {OUTPUT_DIR})"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing files"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    if args.course:
        course_dir = COURSES_DATA_DIR / args.course
        if not course_dir.exists():
            print(f"ERROR: Course directory not found: {course_dir}")
            return 1

        if args.dry_run:
            course = load_course(course_dir)
            if course:
                flat = get_flat_lessons(course)
                print(f"Would generate: 1 landing + {len(flat)} lessons for {course['id']}")
            return 0

        all_courses = load_all_courses()  # for the bundle cross-sell strip
        count = generate_course(course_dir, output_dir, all_courses=all_courses)
        if count == 0:
            print("No lessons generated.")
            return 1
        print(f"\nGenerated 1 landing page + {count} lesson pages for {args.course}")
    else:
        courses = load_all_courses()
        if not courses:
            print("No active courses found.")
            return 1

        if args.dry_run:
            for c in courses:
                flat = get_flat_lessons(c)
                print(f"Would generate: 1 landing + {len(flat)} lessons for {c['id']}")
            print(f"\nWould also generate course index page.")
            return 0

        total_lessons = 0
        for course in courses:
            course_dir = COURSES_DATA_DIR / course["id"]
            count = generate_course(course_dir, output_dir, all_courses=courses)
            total_lessons += count

        # Course index page
        index_html = build_course_index(courses)
        (output_dir / "index.html").write_text(index_html, encoding="utf-8")
        print(f"  course/index.html (course index)")

        # PWA files
        generate_pwa_files(output_dir)

        print(f"\nGenerated {len(courses)} course(s), {total_lessons} lesson pages + index + PWA files")

    return 0


if __name__ == "__main__":
    sys.exit(main())
