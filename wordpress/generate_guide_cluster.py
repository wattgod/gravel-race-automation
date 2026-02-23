#!/usr/bin/env python3
"""
Generate the Gravel God Training Guide as a topic cluster (hub-and-spoke).

Splits the monolithic guide into 9 pages:
  - 1 pillar page (/guide/) with chapter overview and navigation
  - 8 chapter pages (/guide/{chapter-slug}/) with full content

Reuses all block renderers from generate_guide.py and all infographic
renderers from guide_infographics.py. Follows the same output pattern
as generate_prep_kit.py — writes {slug}/index.html per page.

Usage:
    python wordpress/generate_guide_cluster.py
    python wordpress/generate_guide_cluster.py --inline
    python wordpress/generate_guide_cluster.py --output-dir /tmp/guide
"""

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Import shared constants
sys.path.insert(0, str(Path(__file__).parent))
from generate_neo_brutalist import (
    SITE_BASE_URL,
    SUBSTACK_EMBED,
    SUBSTACK_URL,
    COACHING_URL,
    TRAINING_PLANS_URL,
)

from guide_infographics import INFOGRAPHIC_RENDERERS
from shared_header import get_site_header_css, get_site_header_html
from shared_footer import get_mega_footer_css, get_mega_footer_html
from cookie_consent import get_consent_banner_html
from brand_tokens import (
    get_ga4_head_snippet,
    get_tokens_css,
    get_font_face_css,
    get_preload_hints,
)

# Reuse ALL block renderers + helpers from existing guide generator
import generate_guide
generate_guide._GLOSSARY = None  # Will be set during generation
from generate_guide import (
    BLOCK_RENDERERS,
    render_block,
    build_guide_css,
    build_guide_js,
    build_rider_selector,
    build_cta_newsletter,
    build_cta_training,
    build_cta_coaching,
    build_cta_finale,
    CTA_BUILDERS,
    esc,
    _md_inline,
    _safe_json_for_script,
)


# ── Constants ──────────────────────────────────────────────────

GUIDE_DIR = Path(__file__).parent.parent / "guide"
CONTENT_JSON = GUIDE_DIR / "gravel-guide-content.json"
OUTPUT_DIR = Path(__file__).parent / "output" / "guide"

# Chapter URL slugs — maps chapter id to URL slug
# (chapter ids in JSON already match desired URL slugs)

# Chapters 1-3 are free, 4-8 are gated
FREE_CHAPTERS = {1, 2, 3}
GATED_CHAPTERS = {4, 5, 6, 7, 8}

# SEO keyword targets per chapter
CHAPTER_META = {
    "what-is-gravel-racing": {
        "title_suffix": "What Is Gravel Racing? — Beginner's Guide",
        "description": "Everything you need to know about gravel racing: gear, rider categories, and what to expect. Free chapter from the Gravel God Training Guide.",
    },
    "race-selection": {
        "title_suffix": "How to Choose a Gravel Race — Selection Guide",
        "description": "How to choose the right gravel race: 14-dimension scoring system, tier rankings, and what to look for. Free chapter from the Gravel God Training Guide.",
    },
    "training-fundamentals": {
        "title_suffix": "Gravel Race Training Fundamentals",
        "description": "Training fundamentals for gravel racing: periodization, zone training, and building your base. Free chapter from the Gravel God Training Guide.",
    },
    "workout-execution": {
        "title_suffix": "Gravel Workout Execution — Interval Training Guide",
        "description": "How to execute gravel-specific workouts: intervals, endurance rides, and structured training for race performance.",
    },
    "nutrition-fueling": {
        "title_suffix": "Gravel Race Nutrition & Fueling Strategy",
        "description": "Complete gravel race nutrition guide: daily fueling, race-day calories, hydration strategy, and how to avoid bonking.",
    },
    "mental-training-race-tactics": {
        "title_suffix": "Mental Training & Race Tactics for Gravel",
        "description": "Mental training and race tactics for gravel racing: pacing strategy, decision-making under fatigue, and competitive mindset.",
    },
    "race-week": {
        "title_suffix": "Race Week Protocol — Gravel Race Preparation",
        "description": "Race week protocol for gravel racing: taper schedule, equipment checks, nutrition loading, and race morning routine.",
    },
    "post-race": {
        "title_suffix": "Post-Race Recovery & What's Next",
        "description": "Post-race recovery guide: immediate recovery, training restart timeline, and planning your next gravel race.",
    },
}

# Date published for schema
DATE_PUBLISHED = "2025-06-01"


# ── Content Loading ────────────────────────────────────────────


def load_content() -> dict:
    """Load and return guide content JSON."""
    return json.loads(CONTENT_JSON.read_text(encoding="utf-8"))


# ── Pillar Page Builders ───────────────────────────────────────


def build_pillar_hero(content: dict) -> str:
    """Build the hero section for the pillar page."""
    title = esc(content["title"])
    subtitle = esc(content["subtitle"])
    return f'''<div class="gg-hero">
    <div class="gg-hero-tier" style="background:var(--gg-color-teal)">FREE GUIDE</div>
    <h1>{title}</h1>
    <p class="gg-hero-tagline">{subtitle}</p>
  </div>'''


def _estimate_read_time(chapter: dict) -> int:
    """Estimate reading time in minutes based on block content length."""
    total_chars = 0
    for section in chapter.get("sections", []):
        for block in section.get("blocks", []):
            if block.get("type") == "prose":
                total_chars += len(block.get("content", ""))
            elif block.get("type") == "callout":
                total_chars += len(block.get("content", ""))
            elif block.get("type") == "tabs":
                for tab in block.get("tabs", []):
                    total_chars += len(tab.get("content", ""))
    # ~200 words/min, ~5 chars/word, plus time for infographics/interactive
    words = total_chars / 5
    minutes = words / 200
    # Add 1 min per infographic/interactive block
    for section in chapter.get("sections", []):
        for block in section.get("blocks", []):
            if block.get("type") in ("image", "calculator", "knowledge_check",
                                      "scenario", "flashcard", "zone_visualizer"):
                minutes += 1
    return max(3, round(minutes))


def build_chapter_grid(chapters: list) -> str:
    """Build the 8-card chapter grid for the pillar page."""
    cards = []
    for ch in chapters:
        num = ch["number"]
        ch_id = ch["id"]
        title = esc(ch["title"])
        subtitle = esc(ch.get("subtitle", ""))
        gated = ch.get("gated", False)
        read_time = _estimate_read_time(ch)

        lock_icon = '<span class="gg-cluster-card-lock" aria-hidden="true">&#128274;</span>' if gated else ''
        lock_class = ' gg-cluster-card--locked' if gated else ''
        badge = '<span class="gg-cluster-card-badge">FREE</span>' if not gated else '<span class="gg-cluster-card-badge gg-cluster-card-badge--locked">SUBSCRIBER</span>'

        desc_text = subtitle if subtitle else title
        colors = ['var(--gg-color-primary-brown)', 'var(--gg-color-dark-brown)',
                  'var(--gg-color-teal)', 'var(--gg-color-primary-brown)',
                  'var(--gg-color-dark-brown)', 'var(--gg-color-teal)',
                  'var(--gg-color-primary-brown)', 'var(--gg-color-dark-brown)']
        bg = colors[(num - 1) % len(colors)]

        cards.append(f'''<a href="/guide/{esc(ch_id)}/" class="gg-cluster-card{lock_class}" data-chapter="{num}">
      <div class="gg-cluster-card-header" style="background:{bg}">
        <span class="gg-cluster-card-num">CHAPTER {num:02d}</span>
        {lock_icon}
      </div>
      <div class="gg-cluster-card-body">
        <h3 class="gg-cluster-card-title">{title}</h3>
        <p class="gg-cluster-card-desc">{desc_text}</p>
        <div class="gg-cluster-card-meta">
          {badge}
          <span class="gg-cluster-card-time">{read_time} min read</span>
        </div>
      </div>
    </a>''')

    # Add configurator card as a full-width "bonus" card
    cfg_card = f'''<a href="/guide/race-prep-configurator/" class="gg-cluster-card gg-cluster-card--configurator" data-configurator="true" style="grid-column:1/-1">
      <div class="gg-cluster-card-header" style="background:var(--gg-color-teal)">
        <span class="gg-cluster-card-num">INTERACTIVE TOOL</span>
      </div>
      <div class="gg-cluster-card-body">
        <h3 class="gg-cluster-card-title">Race Prep Configurator</h3>
        <p class="gg-cluster-card-desc">Select your race, rider type, and timeline. Get a personalized prep plan covering training, nutrition, hydration, gear, and mental preparation.</p>
        <div class="gg-cluster-card-meta">
          <span class="gg-cluster-card-badge gg-cluster-card-badge--locked">SUBSCRIBER</span>
          <span class="gg-cluster-card-time">Interactive</span>
        </div>
      </div>
    </a>'''

    return f'''<div class="gg-cluster-grid" id="gg-cluster-grid">
    {"".join(cards)}
    {cfg_card}
  </div>'''


def build_pillar_cta_section() -> str:
    """Build the CTA section interspersed in the pillar page."""
    return f'''{build_cta_newsletter()}
  {build_cta_training()}
  {build_cta_coaching()}'''


def build_pillar_jsonld(content: dict) -> str:
    """Build Course + BreadcrumbList JSON-LD for the pillar page."""
    canonical = f"{SITE_BASE_URL}/guide/"
    try:
        mtime = CONTENT_JSON.stat().st_mtime
        date_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        date_modified = datetime.now().strftime("%Y-%m-%d")
    og_image = f"{SITE_BASE_URL}/wp-content/uploads/gravel-god-og.png"

    course = {
        "@context": "https://schema.org",
        "@type": "Course",
        "name": content["title"],
        "description": content["meta_description"],
        "url": canonical,
        "provider": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "hasCourseInstance": {
            "@type": "CourseInstance",
            "courseMode": "online",
        },
        "courseWorkload": "PT4H",
        "isAccessibleForFree": True,
        "datePublished": DATE_PUBLISHED,
        "dateModified": date_modified,
        "image": og_image,
    }

    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": SITE_BASE_URL,
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Training Guide",
                "item": canonical,
            },
        ],
    }

    return (
        f'<script type="application/ld+json">{_safe_json_for_script(course, separators=(",", ":"))}</script>\n'
        f'<script type="application/ld+json">{_safe_json_for_script(breadcrumb, separators=(",", ":"))}</script>'
    )


# ── Chapter Page Builders ──────────────────────────────────────


def build_chapter_breadcrumb(chapter: dict) -> str:
    """Build 3-item breadcrumb: Home > Training Guide > Chapter Title."""
    title = esc(chapter["title"])
    return f'''<div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <a href="/guide/">Training Guide</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">{title}</span>
  </div>'''


def build_chapter_hero(chapter: dict) -> str:
    """Build the hero section for a chapter page."""
    num = chapter["number"]
    title = esc(chapter["title"])
    subtitle = esc(chapter.get("subtitle", ""))
    subtitle_html = f'<p class="gg-guide-chapter-subtitle">{subtitle}</p>' if subtitle else ''

    colors = ['#59473c', '#000', '#178079', '#59473c', '#000', '#178079', '#59473c', '#000']
    bg = colors[(num - 1) % len(colors)]

    hero_image_id = chapter.get("hero_image")
    if hero_image_id:
        hero_style = f"background:url(/guide/media/{esc(hero_image_id)}-1x.webp) center/cover no-repeat;background-color:{bg}"
    else:
        hero_style = f"background:{bg}"

    return f'''<div class="gg-guide-chapter-hero" style="{hero_style}">
      <span class="gg-guide-chapter-num">CHAPTER {num:02d}</span>
      <h2 class="gg-guide-chapter-title">{title}</h2>
      {subtitle_html}
    </div>'''


def build_chapter_content(chapter: dict) -> str:
    """Build the content body for a chapter page (all sections + blocks)."""
    sections_html = []
    for section in chapter["sections"]:
        sec_title = section.get("title", "")
        sec_title_html = f'<h3 class="gg-guide-section-title">{esc(sec_title)}</h3>' if sec_title else ''
        block_parts = []
        for b in section["blocks"]:
            rendered = render_block(b)
            block_parts.append(rendered)
        blocks_html = '\n'.join(block_parts)
        sections_html.append(f'''<div class="gg-guide-section" id="{esc(section["id"])}">
        {sec_title_html}
        {blocks_html}
      </div>''')

    return f'''<div class="gg-guide-chapter-body">
      {"".join(sections_html)}
    </div>'''


def build_chapter_progress(chapter: dict, chapters: list) -> str:
    """Build a progress indicator showing current chapter position."""
    num = chapter["number"]
    total = len(chapters)
    pct = round((num / total) * 100)
    return f'''<div class="gg-cluster-progress">
    <div class="gg-cluster-progress-label">Chapter {num} of {total}</div>
    <div class="gg-cluster-progress-bar" role="progressbar"
         aria-valuenow="{pct}" aria-valuemin="0" aria-valuemax="100"
         aria-label="Chapter {num} of {total}">
      <div class="gg-cluster-progress-fill" style="width:{pct}%"></div>
    </div>
  </div>'''


def build_prev_next_nav(chapter: dict, chapters: list) -> str:
    """Build prev/next chapter navigation at bottom of chapter page."""
    num = chapter["number"]
    prev_ch = None
    next_ch = None
    for ch in chapters:
        if ch["number"] == num - 1:
            prev_ch = ch
        if ch["number"] == num + 1:
            next_ch = ch

    parts = []

    if prev_ch:
        prev_title = esc(prev_ch["title"])
        prev_slug = esc(prev_ch["id"])
        parts.append(
            f'<a href="/guide/{prev_slug}/" class="gg-cluster-nav-prev">'
            f'<span class="gg-cluster-nav-dir">&larr; PREVIOUS</span>'
            f'<span class="gg-cluster-nav-title">Ch {prev_ch["number"]}: {prev_title}</span>'
            f'</a>'
        )
    else:
        parts.append('<div class="gg-cluster-nav-spacer"></div>')

    if next_ch:
        next_title = esc(next_ch["title"])
        next_slug = esc(next_ch["id"])
        lock = ''
        if next_ch.get("gated"):
            lock = ' <span class="gg-cluster-nav-lock" aria-hidden="true">&#128274;</span>'
        parts.append(
            f'<a href="/guide/{next_slug}/" class="gg-cluster-nav-next">'
            f'<span class="gg-cluster-nav-dir">NEXT &rarr;{lock}</span>'
            f'<span class="gg-cluster-nav-title">Ch {next_ch["number"]}: {next_title}</span>'
            f'</a>'
        )
    else:
        parts.append('<div class="gg-cluster-nav-spacer"></div>')

    return f'''<nav class="gg-cluster-nav" aria-label="Chapter navigation">
    {"".join(parts)}
  </nav>'''


def build_chapter_gate(chapter: dict) -> str:
    """Build the gate overlay for gated chapter pages."""
    title = esc(chapter["title"])
    return f'''<div class="gg-guide-gate gg-cluster-gate" id="gg-guide-gate">
    <div class="gg-guide-gate-inner">
      <span class="gg-guide-gate-kicker">THIS CHAPTER IS LOCKED</span>
      <h2>Unlock {title}</h2>
      <p>Subscribe to the Gravel God newsletter to unlock all premium chapters instantly. Covers workout execution, nutrition, mental training, race week protocol, and post-race recovery.</p>
      <form action="https://formsubmit.co/gravelgodcoaching@gmail.com" method="POST" class="gg-cluster-gate-form" id="gg-cluster-gate-form">
        <input type="hidden" name="_subject" value="Guide Unlock: {title}">
        <input type="hidden" name="_template" value="table">
        <input type="hidden" name="_captcha" value="false">
        <input type="hidden" name="_next" value="{SITE_BASE_URL}/guide/{esc(chapter['id'])}/?unlocked=1">
        <input type="email" name="email" placeholder="your@email.com" required class="gg-cluster-gate-email" aria-label="Email address">
        <button type="submit" class="gg-guide-btn gg-guide-btn--primary">UNLOCK FREE</button>
      </form>
      <button class="gg-guide-gate-bypass" id="gg-guide-gate-bypass">I already subscribed &mdash; unlock</button>
    </div>
  </div>'''


def build_chapter_jsonld(chapter: dict, content: dict) -> str:
    """Build Article + BreadcrumbList JSON-LD for a chapter page."""
    ch_id = chapter["id"]
    canonical = f"{SITE_BASE_URL}/guide/{ch_id}/"
    try:
        mtime = CONTENT_JSON.stat().st_mtime
        date_modified = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    except OSError:
        date_modified = datetime.now().strftime("%Y-%m-%d")
    og_image = f"{SITE_BASE_URL}/wp-content/uploads/gravel-god-og.png"

    meta = CHAPTER_META.get(ch_id, {})
    description = meta.get("description", content.get("meta_description", ""))

    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": f"Chapter {chapter['number']}: {chapter['title']}",
        "description": description,
        "url": canonical,
        "datePublished": DATE_PUBLISHED,
        "dateModified": date_modified,
        "image": og_image,
        "author": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "publisher": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "isPartOf": {
            "@type": "Course",
            "name": content["title"],
            "url": f"{SITE_BASE_URL}/guide/",
        },
    }

    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": 1,
                "name": "Home",
                "item": SITE_BASE_URL,
            },
            {
                "@type": "ListItem",
                "position": 2,
                "name": "Training Guide",
                "item": f"{SITE_BASE_URL}/guide/",
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": chapter["title"],
                "item": canonical,
            },
        ],
    }

    # HowTo for chapters with step-like content
    howto_steps = []
    for section in chapter.get("sections", []):
        sec_title = section.get("title")
        if sec_title:
            howto_steps.append({
                "@type": "HowToStep",
                "name": sec_title,
                "url": f"{canonical}#{section['id']}",
            })

    parts = [
        f'<script type="application/ld+json">{_safe_json_for_script(article, separators=(",", ":"))}</script>',
        f'<script type="application/ld+json">{_safe_json_for_script(breadcrumb, separators=(",", ":"))}</script>',
    ]

    if howto_steps:
        howto = {
            "@context": "https://schema.org",
            "@type": "HowTo",
            "name": f"Chapter {chapter['number']}: {chapter['title']}",
            "step": howto_steps,
        }
        parts.append(f'<script type="application/ld+json">{_safe_json_for_script(howto, separators=(",", ":"))}</script>')

    return '\n'.join(parts)


# ── Cluster-Specific CSS ──────────────────────────────────────


def build_cluster_css() -> str:
    """Return CSS additions for the cluster layout (pillar grid, nav, gate form)."""
    return '''
/* ── Cluster Chapter Grid ── */
.gg-cluster-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:0;margin:0 0 40px}
.gg-cluster-card{text-decoration:none;color:inherit;border:3px solid var(--gg-color-dark-brown);display:flex;flex-direction:column;transition:border-color 0.2s}
.gg-cluster-card:hover{border-color:var(--gg-color-gold)}
.gg-cluster-card+.gg-cluster-card{margin-top:-3px}
.gg-cluster-card:nth-child(odd){border-right:none}
.gg-cluster-card:nth-child(n+3){margin-top:-3px}
.gg-cluster-card-header{padding:16px 20px;display:flex;justify-content:space-between;align-items:center}
.gg-cluster-card-num{font-family:var(--gg-font-data);font-size:10px;font-weight:700;letter-spacing:3px;color:rgba(255,255,255,0.85)}
.gg-cluster-card-lock{font-size:12px;opacity:0.6}
.gg-cluster-card-body{padding:16px 20px;flex:1;display:flex;flex-direction:column}
.gg-cluster-card-title{font-family:var(--gg-font-editorial);font-size:16px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--gg-color-primary-brown);margin:0 0 6px}
.gg-cluster-card-desc{font-family:var(--gg-font-editorial);font-size:12px;color:var(--gg-color-secondary-brown);line-height:1.5;margin:0 0 auto;flex:1}
.gg-cluster-card-meta{display:flex;justify-content:space-between;align-items:center;margin-top:12px}
.gg-cluster-card-badge{font-family:var(--gg-font-data);font-size:9px;font-weight:700;letter-spacing:2px;color:var(--gg-color-teal);text-transform:uppercase}
.gg-cluster-card-badge--locked{color:var(--gg-color-secondary-brown)}
.gg-cluster-card-time{font-family:var(--gg-font-data);font-size:10px;color:var(--gg-color-secondary-brown)}

/* ── Cluster Progress ── */
.gg-cluster-progress{padding:12px 24px;background:var(--gg-color-sand);display:flex;align-items:center;gap:12px}
.gg-cluster-progress-label{font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:1px;color:var(--gg-color-secondary-brown);white-space:nowrap}
.gg-cluster-progress-bar{flex:1;height:6px;background:var(--gg-color-tan)}
.gg-cluster-progress-fill{height:100%;background:var(--gg-color-teal)}

/* ── Cluster Prev/Next Nav ── */
.gg-cluster-nav{display:grid;grid-template-columns:1fr 1fr;gap:0;margin:40px 0 0;border-top:4px double var(--gg-color-dark-brown)}
.gg-cluster-nav-prev,.gg-cluster-nav-next{display:flex;flex-direction:column;gap:4px;padding:20px 24px;text-decoration:none;color:inherit;border:3px solid var(--gg-color-dark-brown);border-top:none;transition:background 0.2s}
.gg-cluster-nav-prev{border-right:none}
.gg-cluster-nav-prev:hover,.gg-cluster-nav-next:hover{background:var(--gg-color-sand)}
.gg-cluster-nav-next{text-align:right}
.gg-cluster-nav-dir{font-family:var(--gg-font-data);font-size:10px;font-weight:700;letter-spacing:2px;color:var(--gg-color-secondary-brown)}
.gg-cluster-nav-title{font-family:var(--gg-font-editorial);font-size:14px;font-weight:700;color:var(--gg-color-primary-brown)}
.gg-cluster-nav-lock{font-size:10px;opacity:0.5}
.gg-cluster-nav-spacer{border:3px solid var(--gg-color-dark-brown);border-top:none}

/* ── Gate Form (formsubmit.co) ── */
.gg-cluster-gate-form{display:flex;gap:0;max-width:500px;margin:16px auto 0}
.gg-cluster-gate-email{flex:1;padding:12px 16px;border:3px solid var(--gg-color-dark-brown);font-family:var(--gg-font-data);font-size:13px;background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown)}
.gg-cluster-gate-email::placeholder{color:var(--gg-color-secondary-brown)}
.gg-cluster-gate-form .gg-guide-btn{border-left:none}

/* ── Cluster Gating (per-page) ── */
.gg-cluster-gated-content{display:none}
.gg-guide-unlocked .gg-cluster-gated-content{display:block}
.gg-guide-unlocked .gg-cluster-gate{display:none}

/* ── Responsive ── */
@media(max-width:768px){
.gg-cluster-grid{grid-template-columns:1fr}
.gg-cluster-card:nth-child(odd){border-right:3px solid var(--gg-color-dark-brown)}
.gg-cluster-nav{grid-template-columns:1fr}
.gg-cluster-nav-prev{border-right:3px solid var(--gg-color-dark-brown);border-bottom:none}
.gg-cluster-nav-next{text-align:left}
.gg-cluster-gate-form{flex-direction:column}
.gg-cluster-gate-form .gg-guide-btn{border-left:3px solid var(--gg-color-dark-brown)}
}
'''


# ── Cluster JS ─────────────────────────────────────────────────


def build_cluster_js() -> str:
    """Return JS additions for the cluster layout (gate form, unlock persistence)."""
    return '''
/* ── Guide Cluster Unlock ── */
(function(){
"use strict";
var STORAGE_KEY="gg_guide_unlocked";
function track(n,p){if(typeof gtag==="function")gtag("event",n,Object.assign({transport_type:"beacon"},p||{}));}
function isUnlocked(){try{return localStorage.getItem(STORAGE_KEY)==="1";}catch(e){return false;}}
function unlock(method){
try{localStorage.setItem(STORAGE_KEY,"1");}catch(e){}
document.documentElement.classList.add("gg-guide-unlocked");
var gatedContent=document.querySelector(".gg-cluster-gated-content");
if(gatedContent)gatedContent.style.display="block";
var gate=document.getElementById("gg-guide-gate");
if(gate)gate.style.display="none";
track("guide_gate_unlock",{method:method||"unknown"});
}

/* Check URL param for post-form-submit unlock */
if(new URLSearchParams(window.location.search).get("unlocked")==="1")unlock("email_form");

/* Check localStorage */
if(isUnlocked()){
document.documentElement.classList.add("gg-guide-unlocked");
}

/* Bypass button */
var bypassBtn=document.getElementById("gg-guide-gate-bypass");
if(bypassBtn)bypassBtn.addEventListener("click",function(){unlock("manual_bypass");});

/* Form intercept — set localStorage before formsubmit.co redirect */
var gateForm=document.getElementById("gg-cluster-gate-form");
if(gateForm){
gateForm.addEventListener("submit",function(){
try{localStorage.setItem(STORAGE_KEY,"1");}catch(e){}
track("guide_gate_unlock",{method:"email_form"});
});
}
})();
'''


# ── Page Assembly ──────────────────────────────────────────────


def build_head(title: str, description: str, canonical: str,
               css_html: str, jsonld: str, content: dict,
               prev_url: str = None, next_url: str = None) -> str:
    """Build the <head> section for any cluster page."""
    og_image = f"{SITE_BASE_URL}/wp-content/uploads/gravel-god-og.png"

    prev_link = f'\n  <link rel="prev" href="{esc(prev_url)}">' if prev_url else ''
    next_link = f'\n  <link rel="next" href="{esc(next_url)}">' if next_url else ''

    return f'''<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} — Gravel God Cycling</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical)}">
  {get_preload_hints()}
  {get_ga4_head_snippet()}
  <meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(description)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(canonical)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(description)}">
  <meta name="twitter:image" content="{esc(og_image)}">
  {jsonld}{prev_link}{next_link}
  <style>
{get_tokens_css()}
{get_font_face_css()}
{get_site_header_css()}
{get_mega_footer_css()}
/* Base reset */
.gg-neo-brutalist-page {{
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  font-family: var(--gg-font-data);
  background: var(--gg-color-sand);
  color: var(--gg-color-dark-brown);
  line-height: 1.7;
}}
.gg-neo-brutalist-page *, .gg-neo-brutalist-page *::before, .gg-neo-brutalist-page *::after {{
  border-radius: 0 !important;
  box-shadow: none !important;
  box-sizing: border-box;
}}
.gg-breadcrumb {{ padding: 8px 24px; font-size: 11px; background: var(--gg-color-sand); }}
.gg-breadcrumb a {{ color: var(--gg-color-warm-brown); text-decoration: none; }}
.gg-breadcrumb a:hover {{ color: var(--gg-color-gold); }}
.gg-breadcrumb-sep {{ color: var(--gg-color-secondary-brown); margin: 0 6px; }}
.gg-breadcrumb-current {{ color: var(--gg-color-dark-brown); }}
/* Hero */
.gg-hero {{ background: var(--gg-color-primary-brown); color: var(--gg-color-white); padding: 60px 40px; border: 3px solid var(--gg-color-dark-brown); border-top: none; border-bottom: 4px double rgba(255,255,255,0.15); margin-bottom: 0; }}
.gg-hero-tier {{ display: inline-block; background: var(--gg-color-dark-brown); color: var(--gg-color-white); padding: 4px 12px; font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 16px; }}
.gg-hero h1 {{ font-family: var(--gg-font-editorial); font-size: 42px; font-weight: 700; line-height: 1.1; text-transform: uppercase; letter-spacing: -0.5px; margin-bottom: 16px; color: var(--gg-color-white); }}
.gg-hero-tagline {{ font-size: 14px; line-height: 1.6; color: var(--gg-color-tan); max-width: 700px; }}
@media(max-width:768px){{
  .gg-hero {{ padding: 40px 20px; }}
  .gg-hero h1 {{ font-size: 26px; }}
  .gg-breadcrumb {{ font-size: 10px; }}
}}
  </style>
  {css_html}
</head>'''


def generate_pillar_page(content: dict, guide_css: str, guide_js: str,
                         cluster_css: str, cluster_js: str, inline: bool) -> str:
    """Generate the pillar page HTML."""
    canonical = f"{SITE_BASE_URL}/guide/"

    if inline:
        css_html = f'<style>{guide_css}\n{cluster_css}</style>'
        js_html = f'<script>{guide_js}\n{cluster_js}</script>'
    else:
        css_html = f'<style>{guide_css}\n{cluster_css}</style>'
        js_html = f'<script>{guide_js}\n{cluster_js}</script>'

    nav = get_site_header_html(active="products")
    breadcrumb = f'''<div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">Training Guide</span>
  </div>'''

    hero = build_pillar_hero(content)
    rider_selector = build_rider_selector(content)
    chapter_grid = build_chapter_grid(content["chapters"])
    ctas = build_pillar_cta_section()
    finale = build_cta_finale()
    jsonld = build_pillar_jsonld(content)
    footer = get_mega_footer_html()

    head = build_head(
        title=content["title"],
        description=content["meta_description"],
        canonical=canonical,
        css_html=css_html,
        jsonld=jsonld,
        content=content,
    )

    return f'''<!DOCTYPE html>
<html lang="en">
{head}
<body>

<div class="gg-neo-brutalist-page" id="gg-guide-page">
  {nav}

  {breadcrumb}

  {hero}

  {rider_selector}

  {chapter_grid}

  {ctas}

  {finale}
</div>

{footer}

{js_html}

{get_consent_banner_html()}
</body>
</html>'''


def generate_chapter_page(chapter: dict, chapters: list, content: dict,
                          guide_css: str, guide_js: str,
                          cluster_css: str, cluster_js: str, inline: bool) -> str:
    """Generate a single chapter page HTML."""
    ch_id = chapter["id"]
    canonical = f"{SITE_BASE_URL}/guide/{ch_id}/"
    num = chapter["number"]

    meta = CHAPTER_META.get(ch_id, {})
    title = meta.get("title_suffix", f"Chapter {num}: {chapter['title']}")
    description = meta.get("description", content.get("meta_description", ""))

    if inline:
        css_html = f'<style>{guide_css}\n{cluster_css}</style>'
        js_html = f'<script>{guide_js}\n{cluster_js}</script>'
    else:
        css_html = f'<style>{guide_css}\n{cluster_css}</style>'
        js_html = f'<script>{guide_js}\n{cluster_js}</script>'

    # Prev/next URLs
    prev_url = None
    next_url = None
    for ch in chapters:
        if ch["number"] == num - 1:
            prev_url = f"{SITE_BASE_URL}/guide/{ch['id']}/"
        if ch["number"] == num + 1:
            next_url = f"{SITE_BASE_URL}/guide/{ch['id']}/"

    nav = get_site_header_html(active="products")
    breadcrumb = build_chapter_breadcrumb(chapter)
    progress = build_chapter_progress(chapter, chapters)
    hero = build_chapter_hero(chapter)
    rider_selector = build_rider_selector(content)
    chapter_content = build_chapter_content(chapter)
    prev_next = build_prev_next_nav(chapter, chapters)
    jsonld = build_chapter_jsonld(chapter, content)
    footer = get_mega_footer_html()

    head = build_head(
        title=title,
        description=description,
        canonical=canonical,
        css_html=css_html,
        jsonld=jsonld,
        content=content,
        prev_url=prev_url,
        next_url=next_url,
    )

    # Gated chapters wrap content behind gate
    is_gated = chapter.get("gated", False)
    if is_gated:
        gate_html = build_chapter_gate(chapter)
        body_content = f'''
  {gate_html}
  <div class="gg-cluster-gated-content">
    {chapter_content}

    {prev_next}
  </div>'''
    else:
        body_content = f'''
    {chapter_content}

    {prev_next}'''

    # CTA after chapter
    cta_html = ''
    cta_type = chapter.get("cta_after")
    if cta_type and cta_type != "gate" and cta_type in CTA_BUILDERS:
        cta_html = CTA_BUILDERS[cta_type]()
    elif cta_type == "finale":
        cta_html = build_cta_finale()

    return f'''<!DOCTYPE html>
<html lang="en">
{head}
<body>

<div class="gg-neo-brutalist-page" id="gg-guide-page">
  {nav}

  {breadcrumb}

  {progress}

  <div class="gg-guide-chapter" data-chapter="{num}">
    {hero}

    {rider_selector}

    {body_content}
  </div>

  {cta_html}
</div>

{footer}

{js_html}

{get_consent_banner_html()}
</body>
</html>'''


# ── Configurator Page ─────────────────────────────────────────


def _race_count() -> int:
    """Return the number of races in the race index."""
    idx = generate_guide._RACE_INDEX
    if idx:
        return len(idx)
    return len(generate_guide.load_race_index())


def build_configurator_race_data() -> str:
    """Build slimmed race data as inline JS variable for the configurator."""
    race_index = generate_guide._RACE_INDEX or generate_guide.load_race_index()
    slim = []
    for slug, r in sorted(race_index.items()):
        slim.append({
            "n": r["name"],
            "s": slug,
            "d": r.get("distance_mi", 0),
            "e": r.get("elevation_ft", 0),
            "t": r.get("tier", 0),
            "m": r.get("month", ""),
            "cl": r.get("scores", {}).get("climate", 0),
            "te": r.get("scores", {}).get("technicality", 0),
            "ad": r.get("scores", {}).get("adventure", 0),
            "pr": r.get("scores", {}).get("prestige", 0),
            "u": r.get("profile_url", f"/race/{slug}/"),
        })
    return f'var GG_RACES={_safe_json_for_script(slim, ensure_ascii=False, separators=(",",":"))};'


def build_configurator_body() -> str:
    """Build the configurator form and output HTML."""
    count = _race_count()
    return f'''
  <div class="gg-configurator" id="gg-configurator">
    <div class="gg-configurator__form">
      <div class="gg-configurator__step">
        <label class="gg-configurator__label" for="gg-cfg-race">1. SELECT YOUR RACE</label>
        <div class="gg-configurator__search-wrap">
          <input type="text" id="gg-cfg-race-search" class="gg-configurator__search"
                 placeholder="Search {count} races..." autocomplete="off"
                 aria-label="Search races">
          <select id="gg-cfg-race" class="gg-configurator__select" aria-label="Select your race">
            <option value="">Choose a race...</option>
          </select>
        </div>
      </div>

      <div class="gg-configurator__step">
        <span class="gg-configurator__label">2. YOUR RIDER TYPE</span>
        <div class="gg-configurator__riders" id="gg-cfg-riders" role="radiogroup" aria-label="Select rider type">
          <button class="gg-configurator__rider-btn" data-rider="ayahuasca" role="radio" aria-checked="false">
            <span class="gg-configurator__rider-name">Ayahuasca</span>
            <span class="gg-configurator__rider-hours">0-5 hrs/wk</span>
          </button>
          <button class="gg-configurator__rider-btn gg-configurator__rider-btn--active" data-rider="finisher" role="radio" aria-checked="true">
            <span class="gg-configurator__rider-name">Finisher</span>
            <span class="gg-configurator__rider-hours">5-8 hrs/wk</span>
          </button>
          <button class="gg-configurator__rider-btn" data-rider="competitor" role="radio" aria-checked="false">
            <span class="gg-configurator__rider-name">Competitor</span>
            <span class="gg-configurator__rider-hours">8-12 hrs/wk</span>
          </button>
          <button class="gg-configurator__rider-btn" data-rider="podium" role="radio" aria-checked="false">
            <span class="gg-configurator__rider-name">Podium</span>
            <span class="gg-configurator__rider-hours">12+ hrs/wk</span>
          </button>
        </div>
      </div>

      <div class="gg-configurator__step">
        <label class="gg-configurator__label" for="gg-cfg-date">3. RACE DATE</label>
        <input type="date" id="gg-cfg-date" class="gg-configurator__date" aria-label="Race date">
      </div>

      <button class="gg-configurator__generate" id="gg-cfg-generate">GENERATE PREP PLAN</button>
    </div>

    <div class="gg-configurator__output" id="gg-cfg-output" style="display:none">
      <div class="gg-configurator__output-header">
        <span class="gg-configurator__output-kicker">YOUR PERSONALIZED PREP PLAN</span>
        <h2 class="gg-configurator__output-race" id="gg-cfg-out-race"></h2>
        <div class="gg-configurator__output-meta" id="gg-cfg-out-meta"></div>
      </div>

      <div class="gg-configurator__cards">
        <div class="gg-configurator__card" id="gg-cfg-card-training">
          <div class="gg-configurator__card-header">TRAINING</div>
          <div class="gg-configurator__card-body" id="gg-cfg-out-training"></div>
        </div>
        <div class="gg-configurator__card" id="gg-cfg-card-nutrition">
          <div class="gg-configurator__card-header">NUTRITION</div>
          <div class="gg-configurator__card-body" id="gg-cfg-out-nutrition"></div>
        </div>
        <div class="gg-configurator__card" id="gg-cfg-card-hydration">
          <div class="gg-configurator__card-header">HYDRATION</div>
          <div class="gg-configurator__card-body" id="gg-cfg-out-hydration"></div>
        </div>
        <div class="gg-configurator__card" id="gg-cfg-card-gear">
          <div class="gg-configurator__card-header">GEAR</div>
          <div class="gg-configurator__card-body" id="gg-cfg-out-gear"></div>
        </div>
        <div class="gg-configurator__card" id="gg-cfg-card-mental">
          <div class="gg-configurator__card-header">MENTAL PREP</div>
          <div class="gg-configurator__card-body" id="gg-cfg-out-mental"></div>
        </div>
      </div>

      <div class="gg-configurator__link" id="gg-cfg-out-link"></div>
    </div>
  </div>'''


def build_configurator_css() -> str:
    """Return CSS for the configurator page."""
    return '''
/* ── Configurator ── */
.gg-configurator{max-width:720px;margin:0 auto 40px;padding:0 16px}
.gg-configurator__form{display:flex;flex-direction:column;gap:24px}
.gg-configurator__step{display:flex;flex-direction:column;gap:8px}
.gg-configurator__label{font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:2px;color:var(--gg-color-secondary-brown)}
.gg-configurator__search-wrap{display:flex;flex-direction:column;gap:8px}
.gg-configurator__search,.gg-configurator__select,.gg-configurator__date{padding:12px 16px;border:3px solid var(--gg-color-dark-brown);font-family:var(--gg-font-data);font-size:13px;background:var(--gg-color-warm-paper);color:var(--gg-color-dark-brown);width:100%;box-sizing:border-box}
.gg-configurator__search::placeholder{color:var(--gg-color-secondary-brown)}
.gg-configurator__riders{display:grid;grid-template-columns:repeat(4,1fr);gap:0}
.gg-configurator__rider-btn{padding:12px 8px;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-warm-paper);cursor:pointer;text-align:center;display:flex;flex-direction:column;gap:2px;transition:background 0.15s}
.gg-configurator__rider-btn+.gg-configurator__rider-btn{border-left:none}
.gg-configurator__rider-btn:hover{background:var(--gg-color-sand)}
.gg-configurator__rider-btn--active{background:var(--gg-color-dark-brown);color:var(--gg-color-warm-paper)}
.gg-configurator__rider-btn--active .gg-configurator__rider-name{color:var(--gg-color-warm-paper)}
.gg-configurator__rider-btn--active .gg-configurator__rider-hours{color:var(--gg-color-tan)}
.gg-configurator__rider-name{font-family:var(--gg-font-data);font-size:11px;font-weight:700;letter-spacing:1px;color:var(--gg-color-primary-brown)}
.gg-configurator__rider-hours{font-family:var(--gg-font-data);font-size:9px;color:var(--gg-color-secondary-brown)}
.gg-configurator__generate{padding:14px 24px;border:3px solid var(--gg-color-dark-brown);background:var(--gg-color-teal);color:var(--gg-color-warm-paper);font-family:var(--gg-font-data);font-size:13px;font-weight:700;letter-spacing:2px;cursor:pointer;transition:background 0.15s;margin-top:8px}
.gg-configurator__generate:hover{background:var(--gg-color-primary-brown)}

/* Output */
.gg-configurator__output{margin-top:32px;border:3px solid var(--gg-color-dark-brown)}
.gg-configurator__output-header{background:var(--gg-color-dark-brown);padding:20px 24px;color:var(--gg-color-warm-paper)}
.gg-configurator__output-kicker{font-family:var(--gg-font-data);font-size:10px;letter-spacing:3px;color:var(--gg-color-teal)}
.gg-configurator__output-race{font-family:var(--gg-font-editorial);font-size:24px;font-weight:700;margin:8px 0 4px;color:var(--gg-color-warm-paper)}
.gg-configurator__output-meta{font-family:var(--gg-font-data);font-size:11px;color:var(--gg-color-tan)}
.gg-configurator__cards{display:grid;grid-template-columns:1fr 1fr;gap:0}
.gg-configurator__card{border-bottom:2px solid var(--gg-color-tan);border-right:2px solid var(--gg-color-tan)}
.gg-configurator__card:nth-child(even){border-right:none}
.gg-configurator__card:last-child,.gg-configurator__card:nth-last-child(2):nth-child(odd){border-bottom:none}
.gg-configurator__card-header{padding:10px 16px;background:var(--gg-color-sand);font-family:var(--gg-font-data);font-size:10px;font-weight:700;letter-spacing:2px;color:var(--gg-color-secondary-brown);border-bottom:1px solid var(--gg-color-tan)}
.gg-configurator__card-body{padding:16px;font-family:var(--gg-font-editorial);font-size:14px;color:var(--gg-color-primary-brown);line-height:1.6}
.gg-configurator__card-body strong{font-family:var(--gg-font-data);font-size:12px;display:block;margin-bottom:4px;color:var(--gg-color-teal)}
.gg-configurator__link{padding:16px 24px;text-align:center;background:var(--gg-color-sand);border-top:2px solid var(--gg-color-tan)}
.gg-configurator__link a{color:var(--gg-color-teal);font-family:var(--gg-font-data);font-size:12px;font-weight:700;letter-spacing:1px}

@media print{
.gg-configurator__form{display:none}
.gg-configurator__output{border:1px solid #333}
}
@media(max-width:768px){
.gg-configurator__riders{grid-template-columns:repeat(2,1fr)}
.gg-configurator__rider-btn+.gg-configurator__rider-btn{border-left:3px solid var(--gg-color-dark-brown)}
.gg-configurator__rider-btn:nth-child(n+3){border-top:none}
.gg-configurator__cards{grid-template-columns:1fr}
.gg-configurator__card{border-right:none}
.gg-configurator__output-race{font-size:20px}
}
'''


def build_configurator_js() -> str:
    """Return JS for the configurator page interactivity."""
    return '''
/* ── Race Prep Configurator ── */
(function(){
"use strict";
if(typeof GG_RACES==="undefined")return;
function track(n,p){if(typeof gtag==="function")gtag("event",n,Object.assign({transport_type:"beacon"},p||{}));}
function escHtml(s){var d=document.createElement("div");d.textContent=s;return d.innerHTML;}
function $(id){return document.getElementById(id);}

var raceSelect=$("gg-cfg-race");
var raceSearch=$("gg-cfg-race-search");
var dateInput=$("gg-cfg-date");
var generateBtn=$("gg-cfg-generate");
var output=$("gg-cfg-output");
var riderBtns=document.querySelectorAll(".gg-configurator__rider-btn");
if(!raceSelect||!generateBtn||!output)return;

/* Populate race dropdown */
var allOpts=[];
GG_RACES.forEach(function(r){
var opt=document.createElement("option");
opt.value=r.s;
opt.textContent=r.n+" (T"+r.t+", "+r.d+" mi)";
opt.setAttribute("data-name",r.n.toLowerCase());
raceSelect.appendChild(opt);
allOpts.push(opt);
});

/* Search filter — remove/re-add options for Safari compat (display:none on <option> is non-standard) */
if(raceSearch){
var placeholder=raceSelect.querySelector("option:first-child");
raceSearch.addEventListener("input",function(){
var q=raceSearch.value.toLowerCase();
while(raceSelect.options.length>1)raceSelect.removeChild(raceSelect.lastChild);
allOpts.forEach(function(o){
if(!q||(o.getAttribute("data-name")||"").indexOf(q)>=0)raceSelect.appendChild(o);
});
});
}

/* Rider type buttons */
var validRiders=["ayahuasca","finisher","competitor","podium"];
var selectedRider="finisher";
function setActiveRider(rider){
if(validRiders.indexOf(rider)<0)return;
selectedRider=rider;
riderBtns.forEach(function(b){
var m=b.getAttribute("data-rider")===rider;
b.classList.toggle("gg-configurator__rider-btn--active",m);
b.setAttribute("aria-checked",m?"true":"false");
});
try{localStorage.setItem("gg_guide_rider_type",rider);}catch(e){}
}
riderBtns.forEach(function(btn){
btn.addEventListener("click",function(){setActiveRider(btn.getAttribute("data-rider"));});
});

/* Arrow key navigation for ARIA radiogroup */
var ridersContainer=$("gg-cfg-riders");
if(ridersContainer){
ridersContainer.addEventListener("keydown",function(e){
var btns=Array.prototype.slice.call(riderBtns);
var idx=btns.indexOf(document.activeElement);
if(idx<0)return;
if(e.key==="ArrowRight"||e.key==="ArrowDown"){e.preventDefault();var next=btns[(idx+1)%btns.length];next.focus();setActiveRider(next.getAttribute("data-rider"));}
else if(e.key==="ArrowLeft"||e.key==="ArrowUp"){e.preventDefault();var prev=btns[(idx-1+btns.length)%btns.length];prev.focus();setActiveRider(prev.getAttribute("data-rider"));}
});
}

/* Restore rider type from guide selector */
try{var saved=localStorage.getItem("gg_guide_rider_type");if(saved&&validRiders.indexOf(saved)>=0){setActiveRider(saved);}}catch(e){}

/* Generate plan */
generateBtn.addEventListener("click",function(){
var slug=raceSelect.value;
if(!slug){raceSelect.focus();return;}
var race=GG_RACES.find(function(r){return r.s===slug;});
if(!race)return;

var weeksOut=0;
if(dateInput&&dateInput.value){
var raceDate=new Date(dateInput.value);
var now=new Date();
weeksOut=Math.max(0,Math.round((raceDate-now)/(7*24*60*60*1000)));
}

/* Header */
var outRace=$("gg-cfg-out-race");
var outMeta=$("gg-cfg-out-meta");
if(outRace)outRace.textContent=race.n;
var elev=typeof race.e==="number"?race.e.toLocaleString():String(race.e||0);
var metaParts=["Tier "+race.t,race.d+" miles",elev+"ft elevation"];
if(weeksOut>0)metaParts.push(weeksOut+" weeks out");
if(outMeta)outMeta.textContent=metaParts.join(" \\u00b7 ");

/* Training */
var trainingHtml="";
var phases={ayahuasca:{base:0.5,build:0.3,peak:0.2},finisher:{base:0.4,build:0.35,peak:0.25},competitor:{base:0.35,build:0.35,peak:0.3},podium:{base:0.3,build:0.35,peak:0.35}};
var ph=phases[selectedRider]||phases.finisher;
if(weeksOut>=12){
var bw=Math.round(weeksOut*ph.base),buw=Math.round(weeksOut*ph.build),pw=Math.max(1,weeksOut-bw-buw);
trainingHtml="<strong>Phase Plan ("+weeksOut+" weeks)</strong>Base: "+bw+" weeks \\u2022 Build: "+buw+" weeks \\u2022 Peak/Taper: "+pw+" weeks";
}else if(weeksOut>=4){
trainingHtml="<strong>Compressed Plan ("+weeksOut+" weeks)</strong>Focus on race-specific intensity. Skip extended base phase. Maintain volume, sharpen fitness.";
}else if(weeksOut>0){
trainingHtml="<strong>Taper Mode ("+weeksOut+" weeks)</strong>Reduce volume "+({ayahuasca:"30%",finisher:"40%",competitor:"50%",podium:"60%"}[selectedRider]||"40%")+". Keep 1-2 short openers at race pace.";
}else{
trainingHtml="<strong>Training Recommendation</strong>Set your race date above for a phased training plan tailored to your timeline.";
}
var outTraining=$("gg-cfg-out-training");
if(outTraining)outTraining.innerHTML=trainingHtml;

/* Nutrition */
var carbLo={ayahuasca:30,finisher:40,competitor:60,podium:80};
var carbHi={ayahuasca:40,finisher:60,competitor:90,podium:120};
var lo=carbLo[selectedRider]||40,hi=carbHi[selectedRider]||60;
var estHours=Math.max(1,Math.round(race.d/16+0.5));
if(race.d<=0)estHours=0;
var nutHtml="<strong>Target Fueling</strong>"+lo+"\\u2013"+hi+"g/hr for ~"+estHours+" hours";
nutHtml+="<br><strong>Est. Total Carbs</strong>"+Math.round(lo*estHours)+"\\u2013"+Math.round(hi*estHours)+"g";
var outNutrition=$("gg-cfg-out-nutrition");
if(outNutrition)outNutrition.innerHTML=nutHtml;

/* Hydration */
var climateLabels=["N/A","Mild","Moderate","Variable","Challenging","Extreme"];
var fluidLo={0:500,1:500,2:500,3:600,4:700,5:800};
var fluidHi={0:700,1:700,2:700,3:800,4:1000,5:1200};
var cl=race.cl||0;
var hydHtml="<strong>Climate: "+climateLabels[cl>0?cl:0]+" ("+(cl||"N/A")+"/5)</strong>";
var flo=fluidLo[cl]||500,fhi=fluidHi[cl]||700;
hydHtml+="Target "+flo+"\\u2013"+fhi+"ml/hr with electrolytes";
hydHtml+="<br><strong>Est. Total</strong>"+Math.round(estHours*flo/1000*10)/10+"\\u2013"+Math.round(estHours*fhi/1000*10)/10+"L";
var outHydration=$("gg-cfg-out-hydration");
if(outHydration)outHydration.innerHTML=hydHtml;

/* Gear */
var techLabels=["N/A","Road-ready","Smooth gravel","Mixed surfaces","Technical terrain","Extreme terrain"];
var tireRecs={0:"38-42mm all-purpose",1:"32-38mm slick",2:"38-42mm semi-slick",3:"40-45mm mixed tread",4:"42-50mm aggressive tread",5:"45-50mm+ knobby"};
var te=race.te||0;
var gearHtml="<strong>Terrain: "+techLabels[te>0?te:0]+" ("+(te||"N/A")+"/5)</strong>";
gearHtml+="Tire rec: "+(tireRecs[te]||tireRecs[0]);
if(te>=4)gearHtml+="<br>Consider: dropper post, frame bags, extra spares";
if(race.d>150)gearHtml+="<br>Ultra distance: frame/saddle bags, lighting, emergency blanket";
var outGear=$("gg-cfg-out-gear");
if(outGear)outGear.innerHTML=gearHtml;

/* Mental */
var mentalHtml="";
if(race.pr>=4){
mentalHtml="<strong>High Prestige Event ("+race.pr+"/5)</strong>Big stage, big field. Pre-visualize key sections. Have a tactical plan and a backup plan.";
}else{
mentalHtml="<strong>Adventure Score: "+(race.ad||0)+"/5</strong>";
}
if(race.ad>=4)mentalHtml+="<br>Epic adventure race. Focus on the experience, not just the clock. Set process goals alongside time goals.";
if(race.d>200)mentalHtml+="<br><strong>Ultra Mindset</strong>Break into segments. Have mantras for each phase. Plan sleep strategy if overnight.";
else if(race.d>100)mentalHtml+="<br>Long day in the saddle. Negative-split your effort. Save mental energy for the final third.";
else mentalHtml+="<br>Short and sharp. Start controlled, finish strong.";
var outMental=$("gg-cfg-out-mental");
if(outMental)outMental.innerHTML=mentalHtml;

/* Prep kit link — use DOM API instead of innerHTML to prevent XSS from race names */
var outLink=$("gg-cfg-out-link");
if(outLink){
outLink.textContent="";
var a=document.createElement("a");
a.href=race.u;
a.textContent="View full race profile for "+race.n+" \\u2192";
outLink.appendChild(a);
}

output.style.display="block";
output.scrollIntoView({behavior:"smooth",block:"start"});
track("configurator_plan_generated",{race:slug,rider:selectedRider,weeks:weeksOut});
});

raceSelect.addEventListener("change",function(){
track("configurator_race_selected",{race:raceSelect.value});
});
})();
'''


def build_configurator_jsonld() -> str:
    """Build JSON-LD for the configurator page."""
    canonical = f"{SITE_BASE_URL}/guide/race-prep-configurator/"
    og_image = f"{SITE_BASE_URL}/wp-content/uploads/gravel-god-og.png"

    article = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": "Gravel Race Prep Configurator",
        "description": "Generate a personalized race preparation plan based on your target race, rider type, and timeline.",
        "url": canonical,
        "applicationCategory": "SportsApplication",
        "operatingSystem": "Web",
        "provider": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "image": og_image,
    }

    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home",
             "item": f"{SITE_BASE_URL}/"},
            {"@type": "ListItem", "position": 2, "name": "Training Guide",
             "item": f"{SITE_BASE_URL}/guide/"},
            {"@type": "ListItem", "position": 3, "name": "Race Prep Configurator",
             "item": canonical},
        ]
    }

    return (f'<script type="application/ld+json">{_safe_json_for_script(article, ensure_ascii=False)}</script>\n'
            f'<script type="application/ld+json">{_safe_json_for_script(breadcrumb, ensure_ascii=False)}</script>')


def generate_configurator_page(content: dict, guide_css: str, guide_js: str,
                                cluster_css: str, cluster_js: str, inline: bool) -> str:
    """Generate the race prep configurator page HTML."""
    canonical = f"{SITE_BASE_URL}/guide/race-prep-configurator/"
    cfg_css = build_configurator_css()
    cfg_js = build_configurator_js()
    race_data_js = build_configurator_race_data()

    css_html = f'<style>{guide_css}\n{cluster_css}\n{cfg_css}</style>'
    js_html = f'<script>{race_data_js}</script>\n<script>{guide_js}\n{cluster_js}\n{cfg_js}</script>'

    nav = get_site_header_html(active="products")
    breadcrumb = f'''<div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <a href="{SITE_BASE_URL}/guide/">Training Guide</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">Race Prep Configurator</span>
  </div>'''

    hero = f'''<div class="gg-hero" style="text-align:center;padding:40px 24px 24px">
    <h1 style="font-family:var(--gg-font-editorial);font-size:28px;font-weight:700;color:var(--gg-color-primary-brown);margin:0 0 8px">Race Prep Configurator</h1>
    <p style="font-family:var(--gg-font-editorial);font-size:16px;color:var(--gg-color-secondary-brown);margin:0;max-width:560px;display:inline-block">Select your race, rider type, and timeline. Get a personalized preparation plan covering training, nutrition, hydration, gear, and mental prep.</p>
  </div>'''

    body_html = build_configurator_body()
    gate_html = build_chapter_gate({"title": "Race Prep Configurator", "id": "race-prep-configurator"})
    jsonld = build_configurator_jsonld()
    footer = get_mega_footer_html()

    head = build_head(
        title="Race Prep Configurator — Gravel God Training Guide",
        description=f"Generate a personalized gravel race preparation plan. Select your target race from {_race_count()} scored events, set your rider type and timeline, and get tailored training, nutrition, and gear recommendations.",
        canonical=canonical,
        css_html=css_html,
        jsonld=jsonld,
        content=content,
    )

    return f'''<!DOCTYPE html>
<html lang="en">
{head}
<body>

<div class="gg-neo-brutalist-page" id="gg-guide-page">
  {nav}

  {breadcrumb}

  {hero}

  {gate_html}
  <div class="gg-cluster-gated-content">
    {body_html}
  </div>
</div>

{footer}

{js_html}

{get_consent_banner_html()}
</body>
</html>'''


# ── Main ───────────────────────────────────────────────────────


def generate_cluster(output_dir: Path = None, inline: bool = False):
    """Generate all 10 pages of the guide cluster (pillar + 8 chapters + configurator)."""
    if output_dir is None:
        output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    content = load_content()
    chapters = content["chapters"]
    print(f"Loaded {len(chapters)} chapters from {CONTENT_JSON}")

    # Activate glossary for tooltip resolution
    generate_guide._GLOSSARY = content.get("glossary")
    # Load race index for race-connected block renderers
    generate_guide._RACE_INDEX = generate_guide.load_race_index()

    # Build CSS/JS once
    guide_css = build_guide_css()
    guide_js = build_guide_js()
    cluster_css = build_cluster_css()
    cluster_js = build_cluster_js()

    # 1. Generate pillar page
    pillar_dir = output_dir
    pillar_dir.mkdir(parents=True, exist_ok=True)
    pillar_html = generate_pillar_page(content, guide_css, guide_js,
                                        cluster_css, cluster_js, inline)
    pillar_file = pillar_dir / "index.html"
    pillar_file.write_text(pillar_html, encoding="utf-8")
    print(f"  Pillar: {pillar_file} ({len(pillar_html):,} bytes)")

    # 2. Generate each chapter page
    for chapter in chapters:
        ch_slug = chapter["id"]
        ch_dir = output_dir / ch_slug
        ch_dir.mkdir(parents=True, exist_ok=True)
        ch_html = generate_chapter_page(chapter, chapters, content,
                                         guide_css, guide_js,
                                         cluster_css, cluster_js, inline)
        ch_file = ch_dir / "index.html"
        ch_file.write_text(ch_html, encoding="utf-8")
        gated_label = " (gated)" if chapter.get("gated") else " (free)"
        print(f"  Ch {chapter['number']}: {ch_file} ({len(ch_html):,} bytes){gated_label}")

    # 3. Generate configurator page
    cfg_dir = output_dir / "race-prep-configurator"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_html = generate_configurator_page(content, guide_css, guide_js,
                                           cluster_css, cluster_js, inline)
    cfg_file = cfg_dir / "index.html"
    cfg_file.write_text(cfg_html, encoding="utf-8")
    print(f"  Configurator: {cfg_file} ({len(cfg_html):,} bytes) (gated)")

    print(f"\nGenerated {2 + len(chapters)} pages in {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Gravel God Training Guide as topic cluster"
    )
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR),
                        help="Output directory (default: wordpress/output/guide)")
    parser.add_argument("--inline", action="store_true",
                        help="Inline CSS/JS for local preview")
    args = parser.parse_args()

    generate_cluster(
        output_dir=Path(args.output_dir),
        inline=args.inline,
    )


if __name__ == "__main__":
    main()
