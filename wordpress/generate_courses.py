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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from generate_guide import render_block, build_guide_css
from brand_tokens import get_font_face_css, get_ga4_head_snippet, get_preload_hints, get_tokens_css
from shared_footer import get_mega_footer_html, get_mega_footer_css
from shared_header import get_site_header_html, get_site_header_css
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
.gg-course-page{{max-width:100%;overflow-x:hidden}}
.gg-course-wrap{{max-width:780px;margin:0 auto;padding:0 24px}}

/* ── Landing: Hero ── */
.gg-course-hero{{background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-sand,#ede4d8);padding:80px 24px 60px;text-align:center}}
.gg-course-hero-inner{{max-width:680px;margin:0 auto}}
.gg-course-hero-badge{{display:inline-block;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:2px;text-transform:uppercase;border:1px solid var(--gg-color-teal,#1A8A82);color:var(--gg-color-teal,#1A8A82);padding:4px 14px;border-radius:2px;margin-bottom:20px}}
.gg-course-hero h1{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:clamp(2rem,5vw,3.2rem);line-height:1.15;margin:0 0 16px;color:var(--gg-color-sand,#ede4d8)}}
.gg-course-hero-subtitle{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.25rem;color:var(--gg-color-warm-brown,#A68E80);margin:0 0 32px}}
.gg-course-hero-price{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:1.5rem;color:var(--gg-color-teal,#1A8A82);margin:0 0 24px}}
.gg-course-hero-cta{{display:inline-block;background:var(--gg-color-teal,#1A8A82);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;letter-spacing:1.5px;text-transform:uppercase;padding:14px 40px;border:none;border-radius:2px;text-decoration:none;cursor:pointer;transition:background .2s}}
.gg-course-hero-cta:hover{{background:#178079}}

/* ── Landing: Description ── */
.gg-course-desc{{padding:48px 0;font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.1rem;line-height:1.7;color:var(--gg-color-dark-brown,#3a2e25)}}

/* ── Landing: What You'll Learn ── */
.gg-course-learn{{padding:40px 0;border-top:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-learn h2{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#8c7568);margin:0 0 24px}}
.gg-course-learn ul{{list-style:none;padding:0;margin:0}}
.gg-course-learn li{{position:relative;padding:8px 0 8px 28px;font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1rem;color:var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-learn li::before{{content:'\\2713';position:absolute;left:0;color:var(--gg-color-teal,#1A8A82);font-weight:700}}

/* ── Landing: Module Outline ── */
.gg-course-outline{{padding:40px 0;border-top:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-outline h2{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#8c7568);margin:0 0 24px}}
.gg-course-module{{margin-bottom:24px}}
.gg-course-module-title{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-primary-brown,#59473c);margin:0 0 12px;padding-bottom:8px;border-bottom:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-module-lessons{{list-style:none;padding:0;margin:0}}
.gg-course-module-lessons li{{padding:8px 0;font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);color:var(--gg-color-dark-brown,#3a2e25);display:flex;align-items:center;gap:8px}}
.gg-course-module-lessons li .gg-course-lesson-num{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#8c7568);min-width:24px}}

/* ── Landing: Instructor ── */
.gg-course-instructor{{padding:40px 0;border-top:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-course-instructor h2{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#8c7568);margin:0 0 16px}}
.gg-course-instructor-name{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.25rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 4px}}
.gg-course-instructor-title{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#8c7568);margin:0 0 12px}}
.gg-course-instructor-bio{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1rem;line-height:1.6;color:var(--gg-color-primary-brown,#59473c)}}

/* ── Landing: Bottom CTA ── */
.gg-course-bottom-cta{{background:var(--gg-color-warm-paper,#f5efe6);padding:48px 24px;text-align:center;margin-top:40px;border-top:2px solid var(--gg-color-teal,#1A8A82)}}
.gg-course-bottom-cta h2{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.5rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 12px}}
.gg-course-bottom-cta p{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);color:var(--gg-color-primary-brown,#59473c);margin:0 0 24px}}

/* ── Lesson: Purchase Gate ── */
.gg-course-gate{{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(58,46,37,.95);z-index:9000;display:flex;align-items:center;justify-content:center;padding:24px}}
.gg-course-gate-inner{{background:var(--gg-color-warm-paper,#f5efe6);max-width:480px;width:100%;padding:48px 36px;border-radius:4px;text-align:center}}
.gg-course-gate-badge{{display:inline-block;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:2px;text-transform:uppercase;border:1px solid var(--gg-color-teal,#1A8A82);color:var(--gg-color-teal,#1A8A82);padding:3px 12px;border-radius:2px;margin-bottom:16px}}
.gg-course-gate h2{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.5rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 12px}}
.gg-course-gate p{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);color:var(--gg-color-primary-brown,#59473c);margin:0 0 20px;font-size:.95rem}}
.gg-course-gate-cta{{display:inline-block;background:var(--gg-color-teal,#1A8A82);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1.5px;text-transform:uppercase;padding:12px 32px;border:none;border-radius:2px;text-decoration:none;cursor:pointer;margin-bottom:16px}}
.gg-course-gate-cta:hover{{background:#178079}}
.gg-course-gate-divider{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#8c7568);margin:16px 0}}
.gg-course-gate-form{{display:flex;flex-direction:column;gap:10px;margin-top:12px}}
.gg-course-gate-form input[type=email]{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;padding:10px 14px;border:1px solid var(--gg-color-tan,#d4c5b9);border-radius:2px;background:#fff}}
.gg-course-gate-form button{{background:var(--gg-color-primary-brown,#59473c);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:1.5px;text-transform:uppercase;padding:10px 24px;border:none;border-radius:2px;cursor:pointer}}
.gg-course-gate-form button:hover{{background:var(--gg-color-dark-brown,#3a2e25)}}
.gg-course-gate-fine{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;color:var(--gg-color-secondary-brown,#8c7568);margin-top:12px}}
.gg-course-gate-error{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-error,#c0392b);margin-top:8px;display:none}}

/* ── Lesson: Content ── */
.gg-course-lesson{{display:none}}
.gg-course-lesson.gg-course-unlocked{{display:block}}
.gg-course-lesson-header{{background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-sand,#ede4d8);padding:48px 24px 36px;position:relative}}
.gg-course-lesson-header-inner{{max-width:780px;margin:0 auto}}
.gg-course-lesson-breadcrumb{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#8c7568);margin-bottom:16px}}
.gg-course-lesson-breadcrumb a{{color:var(--gg-color-warm-brown,#A68E80);text-decoration:none}}
.gg-course-lesson-breadcrumb a:hover{{text-decoration:underline}}
.gg-course-lesson-num{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-teal,#1A8A82);margin-bottom:8px}}
.gg-course-lesson-header h1{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:clamp(1.5rem,4vw,2.2rem);color:var(--gg-color-sand,#ede4d8);margin:0}}

/* ── Lesson: Body ── */
.gg-course-lesson-body{{padding:40px 0 60px}}
.gg-course-lesson-body>div{{margin-bottom:32px}}

/* ── Lesson: Progress Sidebar ── */
.gg-course-progress{{background:var(--gg-color-warm-paper,#f5efe6);border:1px solid var(--gg-color-tan,#d4c5b9);border-radius:4px;padding:24px;margin-bottom:40px}}
.gg-course-progress h3{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-secondary-brown,#8c7568);margin:0 0 16px}}
.gg-course-progress-bar-wrap{{background:var(--gg-color-tan,#d4c5b9);height:6px;border-radius:3px;margin-bottom:16px;overflow:hidden}}
.gg-course-progress-bar{{height:100%;background:var(--gg-color-teal,#1A8A82);width:0%;transition:width .3s ease}}
.gg-course-progress-list{{list-style:none;padding:0;margin:0}}
.gg-course-progress-list li{{padding:6px 0;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-primary-brown,#59473c);display:flex;align-items:center;gap:8px}}
.gg-course-progress-list li a{{color:var(--gg-color-primary-brown,#59473c);text-decoration:none}}
.gg-course-progress-list li a:hover{{text-decoration:underline}}
.gg-course-progress-list li .gg-check{{color:var(--gg-color-teal,#1A8A82)}}
.gg-course-progress-list li.gg-current{{font-weight:700;color:var(--gg-color-dark-brown,#3a2e25)}}

/* ── Gamification: Streak Badge ── */
.gg-streak-badge{{position:absolute;top:24px;right:24px;display:flex;align-items:center;gap:6px;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;color:var(--gg-color-sand,#ede4d8);padding:6px 14px;border:1px solid rgba(237,228,216,.2);border-radius:20px;opacity:0;transition:opacity .3s ease}}
.gg-streak-badge.gg-streak-active{{opacity:1;border-color:var(--gg-color-teal,#1A8A82)}}
.gg-streak-badge.gg-streak-active .gg-streak-fire{{animation:gg-pulse 2s ease-in-out infinite}}
.gg-streak-badge.gg-streak-none{{opacity:.5}}
@keyframes gg-pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.2)}}}}

/* ── Gamification: XP Bar in Progress Sidebar ── */
.gg-xp-section{{margin-top:16px;padding-top:16px;border-top:1px solid var(--gg-color-tan,#d4c5b9)}}
.gg-xp-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.gg-xp-level{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gg-color-teal,#1A8A82)}}
.gg-xp-count{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;color:var(--gg-color-secondary-brown,#8c7568)}}
.gg-xp-bar-wrap{{background:var(--gg-color-tan,#d4c5b9);height:4px;border-radius:2px;overflow:hidden}}
.gg-xp-bar{{height:100%;background:var(--gg-color-teal,#1A8A82);width:0%;transition:width .5s ease}}
.gg-xp-streak-row{{display:flex;justify-content:space-between;align-items:center;margin-top:8px}}
.gg-xp-streak-label{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;color:var(--gg-color-secondary-brown,#8c7568)}}

/* ── Gamification: Completion Ring ── */
.gg-completion-ring{{display:flex;align-items:center;gap:12px;margin-bottom:12px}}
.gg-ring-svg{{width:48px;height:48px;transform:rotate(-90deg)}}
.gg-ring-bg{{fill:none;stroke:var(--gg-color-tan,#d4c5b9);stroke-width:4}}
.gg-ring-fill{{fill:none;stroke:var(--gg-color-teal,#1A8A82);stroke-width:4;stroke-linecap:round;transition:stroke-dashoffset .5s ease}}
.gg-ring-pct{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;font-weight:700;color:var(--gg-color-dark-brown,#3a2e25)}}
.gg-ring-label{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:10px;color:var(--gg-color-secondary-brown,#8c7568);text-transform:uppercase;letter-spacing:1px}}

/* ── Gamification: XP Toast ── */
.gg-xp-toast{{position:fixed;bottom:24px;right:24px;background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-teal,#1A8A82);font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;font-weight:700;padding:12px 20px;border-radius:4px;border:1px solid var(--gg-color-teal,#1A8A82);z-index:8000;transform:translateY(100px);opacity:0;transition:transform .3s ease,opacity .3s ease;pointer-events:none}}
.gg-xp-toast.gg-xp-toast-show{{transform:translateY(0);opacity:1}}

/* ── Gamification: Level-Up Overlay ── */
.gg-levelup-overlay{{position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(58,46,37,.9);z-index:9500;display:none;align-items:center;justify-content:center;padding:24px}}
.gg-levelup-overlay.gg-levelup-show{{display:flex}}
.gg-levelup-card{{background:var(--gg-color-warm-paper,#f5efe6);max-width:400px;width:100%;padding:48px 36px;border-radius:4px;text-align:center;position:relative;overflow:hidden}}
.gg-levelup-badge{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:2px;text-transform:uppercase;color:var(--gg-color-teal,#1A8A82);margin-bottom:12px}}
.gg-levelup-title{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.8rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 8px}}
.gg-levelup-name{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:14px;color:var(--gg-color-teal,#1A8A82);letter-spacing:2px;text-transform:uppercase;margin:0 0 24px}}
.gg-levelup-btn{{display:inline-block;background:var(--gg-color-teal,#1A8A82);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1.5px;text-transform:uppercase;padding:12px 32px;border:none;border-radius:2px;cursor:pointer}}
.gg-levelup-btn:hover{{background:#178079}}

/* ── Gamification: Confetti ── */
.gg-confetti{{position:absolute;width:8px;height:8px;top:-10px;animation:gg-confetti-fall 1.5s ease-out forwards}}
@keyframes gg-confetti-fall{{0%{{opacity:1;transform:translateY(0) rotate(0deg)}}100%{{opacity:0;transform:translateY(350px) rotate(720deg)}}}}

/* ── Gamification: Module Complete Card ── */
.gg-module-complete{{background:var(--gg-color-warm-paper,#f5efe6);border:2px solid var(--gg-color-teal,#1A8A82);border-radius:4px;padding:24px;margin-bottom:24px;text-align:center;display:none}}
.gg-module-complete.gg-module-complete-show{{display:block}}
.gg-module-complete-badge{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;letter-spacing:1.5px;text-transform:uppercase;color:var(--gg-color-teal,#1A8A82);margin-bottom:8px}}
.gg-module-complete-title{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.1rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 16px}}
.gg-module-complete-progress{{background:var(--gg-color-tan,#d4c5b9);height:4px;border-radius:2px;overflow:hidden;max-width:200px;margin:0 auto}}
.gg-module-complete-progress-bar{{height:100%;background:var(--gg-color-teal,#1A8A82);transition:width .5s ease}}

/* ── PWA Install Banner ── */
.gg-pwa-banner{{position:fixed;bottom:0;left:0;right:0;background:var(--gg-color-dark-brown,#3a2e25);color:var(--gg-color-sand,#ede4d8);padding:16px 24px;display:none;align-items:center;justify-content:space-between;z-index:7000;border-top:2px solid var(--gg-color-teal,#1A8A82)}}
.gg-pwa-banner.gg-pwa-banner-show{{display:flex}}
.gg-pwa-banner-text{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px}}
.gg-pwa-banner-install{{background:var(--gg-color-teal,#1A8A82);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:11px;letter-spacing:1.5px;text-transform:uppercase;padding:8px 20px;border:none;border-radius:2px;cursor:pointer}}
.gg-pwa-banner-dismiss{{background:none;border:none;color:var(--gg-color-secondary-brown,#8c7568);font-size:18px;cursor:pointer;padding:4px 8px}}

/* ── Lesson: Navigation ── */
.gg-course-nav{{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:32px 0;border-top:1px solid var(--gg-color-tan,#d4c5b9);margin-top:40px}}
.gg-course-nav a{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1px;text-transform:uppercase;color:var(--gg-color-teal,#1A8A82);text-decoration:none;padding:10px 20px;border:1px solid var(--gg-color-teal,#1A8A82);border-radius:2px}}
.gg-course-nav a:hover{{background:var(--gg-color-teal,#1A8A82);color:#fff}}
.gg-course-nav-spacer{{flex:1}}

/* ── Lesson: Mark Complete ── */
.gg-course-complete-btn{{display:block;width:100%;background:var(--gg-color-teal,#1A8A82);color:#fff;font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:13px;letter-spacing:1.5px;text-transform:uppercase;padding:14px;border:none;border-radius:2px;cursor:pointer;margin-top:24px;transition:background .2s}}
.gg-course-complete-btn:hover{{background:#178079}}
.gg-course-complete-btn.gg-completed{{background:var(--gg-color-secondary-brown,#8c7568);cursor:default}}

/* ── Course Index ── */
.gg-course-index{{padding:80px 24px 60px}}
.gg-course-index-inner{{max-width:960px;margin:0 auto}}
.gg-course-index h1{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:clamp(2rem,4vw,2.8rem);color:var(--gg-color-dark-brown,#3a2e25);text-align:center;margin:0 0 12px}}
.gg-course-index-subtitle{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);color:var(--gg-color-primary-brown,#59473c);text-align:center;margin:0 0 48px;font-size:1.1rem}}
.gg-course-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:24px}}
.gg-course-card{{background:var(--gg-color-warm-paper,#f5efe6);border:1px solid var(--gg-color-tan,#d4c5b9);border-radius:4px;padding:32px 24px;text-decoration:none;color:inherit;transition:border-color .2s,box-shadow .2s}}
.gg-course-card:hover{{border-color:var(--gg-color-teal,#1A8A82);box-shadow:0 2px 12px rgba(26,138,130,.1)}}
.gg-course-card-title{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:1.25rem;color:var(--gg-color-dark-brown,#3a2e25);margin:0 0 8px}}
.gg-course-card-subtitle{{font-family:var(--gg-font-editorial,'Source Serif 4',Georgia,serif);font-size:.9rem;color:var(--gg-color-primary-brown,#59473c);margin:0 0 16px}}
.gg-course-card-meta{{font-family:var(--gg-font-data,'Sometype Mono',monospace);font-size:12px;color:var(--gg-color-secondary-brown,#8c7568);display:flex;gap:16px}}

/* ── Responsive ── */
@media(max-width:600px){{
  .gg-course-hero{{padding:60px 20px 40px}}
  .gg-course-gate-inner{{padding:32px 24px}}
  .gg-course-nav{{flex-direction:column}}
  .gg-course-nav a{{text-align:center;width:100%}}
  .gg-streak-badge{{top:12px;right:12px;font-size:11px;padding:4px 10px}}
  .gg-xp-toast{{bottom:12px;right:12px;font-size:12px}}
}}

/* ── PWA Standalone Mode ── */
@media(display-mode:standalone){{
  .gg-site-header{{padding-top:env(safe-area-inset-top,0)}}
  .gg-pwa-banner{{display:none!important}}
}}
"""


# ── JavaScript ───────────────────────────────────────────────


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
    var colors=['#1A8A82','#d4c5b9','#59473c','#A68E80','#ede4d8'];
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
          if(d.xp_events){{
            d.xp_events.forEach(function(evt){{
              if(evt.type==='module_complete'){{
                var mc=document.getElementById('gg-module-complete');
                if(mc) mc.classList.add('gg-module-complete-show');
              }}
            }});
          }}

          if(typeof gtag==='function'){{gtag('event','lesson_complete',{{course_id:COURSE_ID,lesson_id:lessonId}});}}
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

  /* Accordion */
  document.querySelectorAll('.gg-guide-accordion-trigger').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var expanded=btn.getAttribute('aria-expanded')==='true';
      btn.setAttribute('aria-expanded',String(!expanded));
      var body=btn.nextElementSibling;
      body.style.display=expanded?'none':'block';
      btn.querySelector('.gg-guide-accordion-icon').textContent=expanded?'+':'\\u2212';
    }});
  }});
  /* Tabs */
  document.querySelectorAll('.gg-guide-tab-bar').forEach(function(bar){{
    bar.querySelectorAll('.gg-guide-tab').forEach(function(tab){{
      tab.addEventListener('click',function(){{
        bar.querySelectorAll('.gg-guide-tab').forEach(function(t){{t.classList.remove('gg-guide-tab--active');t.setAttribute('aria-selected','false')}});
        tab.classList.add('gg-guide-tab--active');tab.setAttribute('aria-selected','true');
        var group=bar.closest('.gg-guide-tabs');
        group.querySelectorAll('.gg-guide-tab-panel').forEach(function(p){{p.style.display='none'}});
        document.getElementById(tab.getAttribute('data-tab')).style.display='block';
      }});
    }});
  }});
  /* Knowledge Check with XP integration */
  document.querySelectorAll('.gg-guide-kc-option').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var kc=btn.closest('.gg-guide-knowledge-check');
      var questionHash=kc?kc.getAttribute('data-question-hash'):'';
      var isCorrect=btn.getAttribute('data-correct')==='true';
      var selectedIndex=parseInt(btn.getAttribute('data-index')||'0',10);

      kc.querySelectorAll('.gg-guide-kc-option').forEach(function(b){{
        b.style.opacity=b.getAttribute('data-correct')==='true'?'1':'0.4';
        b.style.borderColor=b.getAttribute('data-correct')==='true'?'var(--gg-color-teal,#1A8A82)':'var(--gg-color-error,#c0392b)';
        b.disabled=true;
      }});
      kc.querySelector('.gg-guide-kc-explanation').style.display='block';

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
  /* Flashcard */
  document.querySelectorAll('.gg-guide-flashcard').forEach(function(card){{
    card.addEventListener('click',function(){{card.classList.toggle('gg-guide-flashcard--flipped')}});
    card.addEventListener('keydown',function(e){{if(e.key==='Enter'||e.key===' '){{e.preventDefault();card.classList.toggle('gg-guide-flashcard--flipped')}}}});
  }});
  /* Scenario */
  document.querySelectorAll('.gg-guide-scenario-option').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var scenario=btn.closest('.gg-guide-scenario');
      scenario.querySelectorAll('.gg-guide-scenario-option').forEach(function(b){{
        b.querySelector('.gg-guide-scenario-option-result').style.display='block';
        if(b.getAttribute('data-best')==='true') b.style.borderColor='var(--gg-color-teal,#1A8A82)';
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
"""


# ── Page Builders ────────────────────────────────────────────


def build_landing_page(course: dict) -> str:
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

    # Module outline
    modules_html = []
    lesson_num = 0
    for module in course["modules"]:
        lessons_html = []
        for lesson in module["lessons"]:
            lesson_num += 1
            lessons_html.append(
                f'<li><span class="gg-course-lesson-num">{lesson_num:02d}</span> {esc(lesson["title"])}</li>'
            )
        modules_html.append(f'''<div class="gg-course-module">
          <div class="gg-course-module-title">{esc(module["title"])}</div>
          <ul class="gg-course-module-lessons">{"".join(lessons_html)}</ul>
        </div>''')

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
  <meta property="og:title" content="{title} | Gravel God Cycling">
  <meta property="og:description" content="{meta_desc}">
  <meta property="og:type" content="product">
  <meta property="og:url" content="{canonical}">
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
    {"".join(modules_html)}
  </div>

  {instructor_html}
</div>

<div class="gg-course-bottom-cta">
  <h2>Ready to master hydration?</h2>
  <p>8 interactive lessons. Science-backed strategies. Lifetime access.</p>
  <a href="{stripe_link}" class="gg-course-hero-cta">ENROLL FOR ${price}</a>
</div>

{mega_footer}
</div>
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

    # Render blocks
    blocks_html = "\n".join(render_block(block) for block in lesson.get("blocks", []))

    # Progress sidebar — list all lessons with completion status
    progress_items = []
    for idx, (mod, les) in enumerate(flat_lessons):
        current = " gg-current" if les["id"] == lesson_id else ""
        link = f'{SITE_BASE_URL}/course/{slug}/lesson/{les["id"]}/'
        progress_items.append(
            f'<li class="{current}" data-lesson-id="{esc(les["id"])}">'
            f'<span class="gg-check"></span>'
            f'<a href="{link}">{idx + 1:02d}. {esc(les["title"])}</a></li>'
        )

    # Prev/Next navigation
    prev_html = ""
    next_html = ""
    if lesson_idx > 0:
        prev_lesson = flat_lessons[lesson_idx - 1][1]
        prev_url = f'{SITE_BASE_URL}/course/{slug}/lesson/{prev_lesson["id"]}/'
        prev_html = f'<a href="{prev_url}">&larr; Previous</a>'
    if lesson_idx < total - 1:
        next_lesson = flat_lessons[lesson_idx + 1][1]
        next_url = f'{SITE_BASE_URL}/course/{slug}/lesson/{next_lesson["id"]}/'
        next_html = f'<a href="{next_url}">Next &rarr;</a>'

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
<div class="gg-course-lesson" id="gg-course-lesson">
  <div class="gg-course-lesson-header">
    <div class="gg-course-lesson-header-inner">
      <div class="gg-course-lesson-breadcrumb">
        <a href="{SITE_BASE_URL}/course/{slug}/">{course_title}</a>
        <span>&rsaquo;</span>
        <span>{esc(module["title"])}</span>
      </div>
      <div class="gg-course-lesson-num">LESSON {lesson_idx + 1:02d} OF {total:02d}</div>
      <h1>{lesson_title}</h1>
    </div>
    <!-- Streak Badge -->
    <div class="gg-streak-badge gg-streak-none" id="gg-streak-badge">
      <span class="gg-streak-fire">&#128293;</span>
      <span class="gg-streak-count">No streak</span>
    </div>
  </div>

  <div class="gg-course-wrap">
    <!-- Module Complete Card (hidden until triggered) -->
    <div class="gg-module-complete" id="gg-module-complete">
      <div class="gg-module-complete-badge">+25 XP MODULE BONUS</div>
      <div class="gg-module-complete-title">Module Complete: {esc(module["title"])}</div>
    </div>

    <div class="gg-course-progress">
      <h3>YOUR PROGRESS</h3>

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
      <ul class="gg-course-progress-list">
        {"".join(progress_items)}
      </ul>

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

    <div class="gg-course-lesson-body">
      {blocks_html}
    </div>

    <button class="gg-course-complete-btn" id="gg-course-complete-btn" data-lesson-id="{esc(lesson_id)}">
      MARK AS COMPLETE
    </button>

    <div class="gg-course-nav">
      {prev_html}
      <span class="gg-course-nav-spacer"></span>
      {next_html}
    </div>
  </div>

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
      background: #1A8A82;
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


def generate_course(course_dir: Path, output_dir: Path) -> int:
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
    landing_html = build_landing_page(course)
    (landing_dir / "index.html").write_text(landing_html, encoding="utf-8")
    print(f"  {slug}/index.html (landing page)")

    # Lesson pages
    for idx, (module, lesson) in enumerate(flat_lessons):
        lesson_dir = landing_dir / "lesson" / lesson["id"]
        lesson_dir.mkdir(parents=True, exist_ok=True)
        lesson_html = build_lesson_page(course, module, lesson, idx, total, flat_lessons)
        (lesson_dir / "index.html").write_text(lesson_html, encoding="utf-8")
        print(f"  {slug}/lesson/{lesson['id']}/index.html")

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

        count = generate_course(course_dir, output_dir)
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
            count = generate_course(course_dir, output_dir)
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
