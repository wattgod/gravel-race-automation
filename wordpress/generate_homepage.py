#!/usr/bin/env python3
"""
Generate the Gravel God homepage.

Four things, in order (homepage cut, Nov 2026):
  1. The 2027 goals poster wall (owner-ruled hero, goals-2027-funnel D5).
  2. The race database band: search, the numbers once, the top-rated races.
  3. One band of four doors with the character art: Handbook, Surge Check,
     a training plan, coaching.
  4. The shared footer (it carries the newsletter sign-up).

Usage:
    python generate_homepage.py
    python generate_homepage.py --output-dir ./output
"""

import argparse
import html
import json
import re
from datetime import date
from pathlib import Path

# Import shared constants from the race page generator
from generate_neo_brutalist import (
    SITE_BASE_URL,
    TRAINING_PLANS_URL,
)
from brand_tokens import (
    get_ab_head_snippet,
    get_favicon_head_snippet,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
    get_ga4_head_snippet,
)
from cookie_consent import get_consent_banner_html
from shared_footer import get_mega_footer_css, get_mega_footer_html
from shared_header import get_site_header_css, get_site_header_html, get_site_header_js

OUTPUT_DIR = Path(__file__).parent / "output"
RACE_INDEX_PATH = Path(__file__).parent.parent / "web" / "race-index.json"
RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"

CURRENT_YEAR = date.today().year

# All 15 scored criteria in race.gravel_god_rating (course + editorial dims,
# plus the cultural_impact bonus dimension). Copy that states a criteria
# count (stats["dimensions"], meta descriptions, JSON-LD) reads len() of
# this list rather than hardcoding a number.
RATING_DIMS = [
    "logistics", "length", "technicality", "elevation", "climate",
    "altitude", "adventure", "prestige", "race_quality", "experience",
    "community", "field_depth", "value", "expenses", "cultural_impact",
]

# Series umbrella slugs — not individual races, never ranked on their own.
SERIES_UMBRELLA_SLUGS = {"grasshopper-series", "grinduro", "gravel-earth"}

TOP_RATED_COUNT = 5

RANKINGS_URL = f"{SITE_BASE_URL}/race/power-rankings-{CURRENT_YEAR}/"
GOAL_LEAD_URL = f"{SITE_BASE_URL}/goals/"

# The four doors. Art is the Handbook's v6 character scenes (guide/art/),
# already served from /guide/media/ by push_wordpress.py --sync-guide.
# Each entry: (key, title, button label, href, art slug, GA label)
DOORS = [
    ("handbook", "Gravel Handbook", "READ IT FREE", f"{SITE_BASE_URL}/guide/",
     "02-race-selection", "door_handbook"),
    ("surge", "Surge Check", "CHECK A RIDE", f"{SITE_BASE_URL}/surge-check/",
     "04-workout-execution", "door_surge_check"),
    ("plan", "Custom Training Plan", "BUILD MY PLAN", TRAINING_PLANS_URL,
     "03-training-fundamentals", "door_plan"),
    ("coaching", "Coaching", "GET ME IN YOUR CORNER", f"{SITE_BASE_URL}/coaching/",
     "08-post-race", "door_coaching"),
]


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Data loading ─────────────────────────────────────────────


def load_race_index(index_path: Path = None) -> list:
    """Load race-index.json and return list of race dicts."""
    path = index_path or RACE_INDEX_PATH
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compute_stats(race_index: list) -> dict:
    """Compute homepage statistics from the race index."""
    race_count = len(race_index)
    t1_count = sum(1 for r in race_index if r.get("tier") == 1)
    t2_count = sum(1 for r in race_index if r.get("tier") == 2)
    regions = set()
    for r in race_index:
        loc = r.get("location", "")
        if loc:
            parts = [p.strip() for p in loc.split(",")]
            if parts:
                regions.add(parts[-1])
    return {
        "race_count": race_count,
        "dimensions": len(RATING_DIMS),
        "t1_count": t1_count,
        "t2_count": t2_count,
        "region_count": len(regions),
    }


def _profile_discipline(slug: str, race_data_dir: Path = None) -> str | None:
    """vitals.discipline from the race profile, if it says one.

    race-index.json takes discipline from gravel_god_rating only, so ~50
    road and bikepacking profiles that state theirs in vitals are indexed
    as gravel. Checked here so "Top rated" never lists a road race.
    """
    path = (race_data_dir or RACE_DATA_DIR) / f"{slug}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    race = data.get("race", data)
    return (race.get("vitals") or {}).get("discipline")


def get_top_rated(race_index: list, limit: int = TOP_RATED_COUNT,
                  race_data_dir: Path = None) -> list:
    """Highest-scoring gravel races, series umbrellas excluded."""
    ranked = sorted(race_index, key=lambda r: r.get("overall_score", 0), reverse=True)
    top = []
    for r in ranked:
        slug = r.get("slug", "")
        if (r.get("discipline") or "gravel") != "gravel" or slug in SERIES_UMBRELLA_SLUGS:
            continue
        if (_profile_discipline(slug, race_data_dir) or "gravel") != "gravel":
            continue
        top.append(r)
        if len(top) == limit:
            break
    return top


# ── Section builders ─────────────────────────────────────────


def build_nav() -> str:
    return get_site_header_html()


def build_top_bar() -> str:
    return '<div class="gg-hp-top-bar" aria-hidden="true"></div>'


def build_goal_hero() -> str:
    """The 2027 goals poster wall — homepage hero, layout D1 (owner-ruled,
    goals-2027-funnel-spec.md D5).

    Left: three SAMPLE goal posters at once (middle large, two angled
    behind), drawn on <canvas> in the PAPER style (same layout as
    drawPoster() in generate_season_review.py, warm-paper background,
    near-black ink text). The artwork rotates on page load or on click of
    the poster wall only — never on a timer (see build_homepage_js()).
    Right: a fixed headline and button; neither ever changes with the
    artwork. No subtitle under the headline (house no-descriptive-copy rule).
    """
    posters = ""
    for i in range(3):
        posters += (
            f'\n        <div class="gg-hp-poster gg-hp-poster--{i}">'
            f'<canvas id="gg-goal-poster-{i}" width="1080" height="1440" '
            f'class="gg-hp-poster-canvas" aria-hidden="true"></canvas></div>'
        )

    return f'''<section class="gg-hp-goal-hero" id="main">
    <div class="gg-hp-goal-hero-inner">
      <button type="button" class="gg-hp-poster-wall" id="gg-poster-wall" aria-label="Show different sample 2027 goal posters">{posters}
      </button>
      <div class="gg-hp-goal-content">
        <p class="gg-hp-hero-kicker">2027 GOALS</p>
        <h2 class="gg-hp-goal-title">It&rsquo;s dreaming season. Most of it stays a dream.</h2>
        <a href="{GOAL_LEAD_URL}?src=home" class="gg-hp-btn-primary gg-hp-goal-cta" data-ga="goal_hero_click" data-ga-label="home">MAKE MINE</a>
      </div>
    </div>
  </section>'''


def build_top_rated(race_index: list) -> str:
    """The top-rated gravel races: rank, name, where, score."""
    rows = ""
    for idx, race in enumerate(get_top_rated(race_index), 1):
        name = esc(race.get("name", ""))
        slug = esc(race.get("slug", ""))
        location = esc(race.get("location", ""))
        score = race.get("overall_score", 0)
        rows += f'''
        <li>
          <a href="{SITE_BASE_URL}/race/{slug}/" class="gg-hp-top-row" data-ga="ranking_click" data-ga-label="{name}">
            <span class="gg-hp-top-rank" aria-hidden="true">{idx:02d}</span>
            <span class="gg-hp-top-name">{name}<span class="gg-hp-top-where">{location}</span></span>
            <span class="gg-hp-top-score" aria-label="Score {score}">{score}</span>
          </a>
        </li>'''
    return f'''<div class="gg-hp-top">
        <h2 class="gg-hp-top-head">TOP RATED</h2>
        <ol class="gg-hp-top-list">{rows}
        </ol>
        <a href="{esc(RANKINGS_URL)}" class="gg-hp-top-more" data-ga="view_all_races" data-ga-label="rankings">FULL RANKINGS &rarr;</a>
      </div>'''


def build_hero(stats: dict, race_index: list) -> str:
    """The race database band: headline, search, the numbers once, top rated."""
    race_count = stats["race_count"]
    region_count = stats["region_count"]
    dimensions = stats["dimensions"]

    return f'''<section class="gg-hp-hero" id="race-database">
    <div class="gg-hp-hero-inner">
      <div class="gg-hp-hero-content">
        <p class="gg-hp-hero-kicker">THE {CURRENT_YEAR} RACE DATABASE</p>
        <h1 id="hero-title">Every gravel race, rated.</h1>
        <form class="gg-hp-hero-search" action="{SITE_BASE_URL}/gravel-races/" method="get" role="search">
          <input type="text" name="q" class="gg-hp-hero-search-input" placeholder="Search races, locations, or what riders say..." aria-label="Search races" autocomplete="off">
          <button type="submit" class="gg-hp-hero-search-btn" aria-label="Search">&#8594;</button>
        </form>
        <div class="gg-hp-hero-chips">
          <a href="{SITE_BASE_URL}/gravel-races/?discipline=gravel" class="gg-hp-chip" data-ga="hero_chip_click" data-ga-label="gravel">Gravel</a>
          <a href="{SITE_BASE_URL}/gravel-races/?discipline=bikepacking" class="gg-hp-chip" data-ga="hero_chip_click" data-ga-label="bikepacking">Bikepacking</a>
          <a href="{SITE_BASE_URL}/gravel-races/?discipline=mtb" class="gg-hp-chip" data-ga="hero_chip_click" data-ga-label="mtb">MTB</a>
          <a href="{SITE_BASE_URL}/gravel-races/?tier=1" class="gg-hp-chip gg-hp-chip--gold" data-ga="hero_chip_click" data-ga-label="tier1">Tier 1</a>
          <a href="{SITE_BASE_URL}/race/methodology/" class="gg-hp-chip" data-ga="hero_secondary_click">How We Rate</a>
        </div>
        <dl class="gg-hp-hero-stats">
          <div class="gg-hp-hero-stat"><dt>Races</dt><dd>{race_count}</dd></div>
          <div class="gg-hp-hero-stat"><dt>Regions</dt><dd>{region_count}</dd></div>
          <div class="gg-hp-hero-stat"><dt>Criteria</dt><dd>{dimensions}</dd></div>
        </dl>
      </div>
      {build_top_rated(race_index)}
    </div>
  </section>'''


def _door_art(slug: str) -> str:
    base = f"/guide/media/gg-art-{slug}"
    return (f'<img class="gg-hp-door-art" src="{base}-1x.webp" '
            f'srcset="{base}-1x.webp 960w, {base}-2x.webp 1920w" '
            f'sizes="(max-width: 600px) 100vw, (max-width: 1100px) 50vw, 25vw" '
            f'width="960" height="640" alt="" loading="lazy" decoding="async">')


def build_doors() -> str:
    """One band, four doors, each a character scene plus one button.

    The plan door keeps the two live A/B targets (web/ab/experiments.json):
    data-ab="training_price" on the price line and data-ab="training_cta_btn"
    on its button; the experiment script swaps their text at runtime.
    """
    cells = ""
    for key, title, label, href, art, ga in DOORS:
        price = ""
        ab_btn = ""
        if key == "plan":
            price = '\n        <p class="gg-hp-door-price" data-ab="training_price">$15 a week.</p>'
            ab_btn = ' data-ab="training_cta_btn"'
        event = "cta_click" if key in ("plan", "coaching") else "door_click"
        cells += f'''
      <article class="gg-hp-door gg-hp-door--{key}">
        {_door_art(art)}
        <h3 class="gg-hp-door-title">{title}</h3>{price}
        <a href="{esc(href)}" class="gg-hp-door-btn"{ab_btn} data-ga="{event}" data-ga-label="{ga}">{label}&nbsp;&rarr;</a>
      </article>'''
    return f'''<section class="gg-hp-doors" id="start" aria-labelledby="doors-title">
    <h2 class="gg-hp-doors-head" id="doors-title">SHOW UP READY</h2>
    <div class="gg-hp-doors-grid">{cells}
    </div>
  </section>'''


def build_footer() -> str:
    return get_mega_footer_html()


# ── CSS ──────────────────────────────────────────────────────


def build_homepage_css() -> str:
    font_face = get_font_face_css()
    tokens = get_tokens_css()
    mega_footer_css = get_mega_footer_css()
    return '<style>\n/* ── Self-hosted fonts ──────────────────────────────────── */\n' + font_face + '\n\n' + tokens + '\n\n' + '''/* ── Reset & base ────────────────────────────────────────── */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body { overflow-x: clip; max-width: 100vw; }
body { font-family: var(--gg-font-editorial); color: var(--gg-color-dark-brown); line-height: 1.75; background: var(--gg-color-sand); margin: 0; }
a { text-decoration: none; color: var(--gg-color-teal); }

/* ── Page container ──────────────────────────────────────── */
.gg-hp-page { margin: 0; padding: 0; overflow-x: clip; }

/* ── Gold top bar ── */
.gg-hp-top-bar { height: 4px; background: var(--gg-color-gold); }

''' + get_site_header_css() + '''

/* ── Shared type + buttons ───────────────────────────────── */
.gg-hp-hero-kicker { font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; color: var(--gg-color-gold); text-transform: uppercase; letter-spacing: 3px; margin-bottom: 16px; }
.gg-hp-btn-primary { display: inline-block; padding: 12px 28px; background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; border: 2px solid var(--gg-color-dark-brown); text-decoration: none; transition: background-color .3s, color .3s; }
.gg-hp-btn-primary:hover { background: var(--gg-color-gold); color: var(--gg-color-near-black); border-color: var(--gg-color-gold); }

/* ── Goal poster wall hero (2027 goals funnel, D1 — owner-ruled) ───────── */
.gg-hp-goal-hero { background: var(--gg-color-warm-paper); padding: 64px 48px; border-bottom: 3px solid var(--gg-color-dark-brown); }
.gg-hp-goal-hero-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1fr 1fr; gap: 64px; align-items: center; }
.gg-hp-poster-wall { position: relative; display: block; width: 100%; height: 420px; background: none; border: none; padding: 0; margin: 0; cursor: pointer; -webkit-tap-highlight-color: transparent; }
.gg-hp-poster { position: absolute; top: 50%; left: 50%; width: 220px; border: 3px solid var(--gg-color-dark-brown); background: var(--gg-color-warm-paper); }
.gg-hp-poster-canvas { display: block; width: 100%; height: auto; }
.gg-hp-poster--0 { transform: translate(-50%, -50%) translateX(-88px) rotate(-8deg); z-index: 1; }
.gg-hp-poster--1 { width: 260px; transform: translate(-50%, -50%) rotate(0deg); z-index: 3; }
.gg-hp-poster--2 { transform: translate(-50%, -50%) translateX(88px) rotate(8deg); z-index: 2; }
.gg-hp-goal-content { text-align: left; }
.gg-hp-goal-title { font-family: var(--gg-font-editorial); font-size: 40px; font-weight: 900; line-height: 1.1; color: var(--gg-color-near-black); margin: 0 0 24px; }
.gg-hp-goal-cta { font-size: 13px; padding: 16px 36px; }

/* ── Race database band ──────────────────────────────────── */
.gg-hp-hero { background: var(--gg-color-sand); padding: 64px 48px; border-bottom: 3px solid var(--gg-color-dark-brown); }
.gg-hp-hero-inner { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: 1.1fr 1fr; gap: 64px; align-items: start; }
.gg-hp-hero h1 { font-family: var(--gg-font-editorial); font-size: 48px; font-weight: 900; line-height: 1.05; margin-bottom: 24px; color: var(--gg-color-near-black); }
.gg-hp-hero-search { display: flex; margin-bottom: 16px; border: 3px solid var(--gg-color-dark-brown); background: var(--gg-color-white); }
.gg-hp-hero-search-input { flex: 1; min-width: 0; padding: 14px 16px; font-family: var(--gg-font-data); font-size: 14px; border: none; background: transparent; color: var(--gg-color-dark-brown); outline: none; }
.gg-hp-hero-search-input::placeholder { color: var(--gg-color-secondary-brown); }
.gg-hp-hero-search-btn { padding: 12px 20px; background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); border: none; font-size: 18px; cursor: pointer; transition: background-color 0.2s; font-family: var(--gg-font-data); }
.gg-hp-hero-search-btn:hover { background: var(--gg-color-gold); }
.gg-hp-hero-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 32px; }
.gg-hp-chip { display: inline-block; padding: 6px 14px; font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; color: var(--gg-color-dark-brown); border: 1px solid var(--gg-color-secondary-brown); transition: border-color 0.2s, color 0.2s; }
.gg-hp-chip:hover { border-color: var(--gg-color-gold); color: var(--gg-color-gold); }
.gg-hp-chip--gold { border-color: var(--gg-color-gold); color: var(--gg-color-gold); }
.gg-hp-hero-stats { display: flex; gap: 0; border-top: 3px solid var(--gg-color-dark-brown); }
.gg-hp-hero-stat { flex: 1; display: flex; flex-direction: column-reverse; padding: 16px 0 0; border-right: 1px solid var(--gg-color-tan); padding-left: 16px; }
.gg-hp-hero-stat:first-child { padding-left: 0; }
.gg-hp-hero-stat:last-child { border-right: none; }
.gg-hp-hero-stat dd { font-family: var(--gg-font-editorial); font-size: 40px; font-weight: 900; color: var(--gg-color-near-black); line-height: 1; }
.gg-hp-hero-stat dt { font-family: var(--gg-font-data); font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: var(--gg-color-secondary-brown); margin-top: 6px; }

/* ── Top rated ── */
.gg-hp-top { background: var(--gg-color-warm-paper); border: 3px solid var(--gg-color-dark-brown); }
.gg-hp-top-head { font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; letter-spacing: 3px; color: var(--gg-color-warm-paper); background: var(--gg-color-dark-brown); padding: 12px 20px; margin: 0; }
.gg-hp-top-list { list-style: none; margin: 0; padding: 0; }
.gg-hp-top-row { display: grid; grid-template-columns: 40px 1fr auto; gap: 12px; align-items: center; padding: 14px 20px; border-bottom: 1px solid var(--gg-color-tan); color: var(--gg-color-dark-brown); transition: background-color .2s; }
.gg-hp-top-row:hover { background: var(--gg-color-sand); }
.gg-hp-top-row:hover .gg-hp-top-name { color: var(--gg-color-teal); }
.gg-hp-top-rank { font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; color: var(--gg-color-gold); }
.gg-hp-top-name { font-family: var(--gg-font-editorial); font-size: 19px; font-weight: 700; line-height: 1.2; min-width: 0; }
.gg-hp-top-where { display: block; font-family: var(--gg-font-data); font-size: 10px; font-weight: 400; letter-spacing: 1px; text-transform: uppercase; color: var(--gg-color-secondary-brown); margin-top: 2px; }
.gg-hp-top-score { font-family: var(--gg-font-data); font-size: 22px; font-weight: 700; color: var(--gg-color-near-black); }
.gg-hp-top-more { display: block; padding: 14px 20px; font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: 2px; color: var(--gg-color-dark-brown); }
.gg-hp-top-more:hover { color: var(--gg-color-teal); }

/* ── Four doors ──────────────────────────────────────────── */
.gg-hp-doors { background: var(--gg-color-warm-paper); padding: 56px 48px 64px; border-bottom: 3px solid var(--gg-color-dark-brown); }
.gg-hp-doors-head { max-width: 1200px; margin: 0 auto 24px; font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; letter-spacing: 3px; color: var(--gg-color-gold); }
.gg-hp-doors-grid { max-width: 1200px; margin: 0 auto; display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; }
.gg-hp-door { display: flex; flex-direction: column; background: var(--gg-color-white); border: 3px solid var(--gg-color-dark-brown); transition: border-color .2s; }
.gg-hp-door:hover { border-color: var(--gg-color-teal); }
.gg-hp-door-art { display: block; width: 100%; height: auto; aspect-ratio: 3 / 2; object-fit: cover; border-bottom: 3px solid var(--gg-color-dark-brown); }
.gg-hp-door-title { font-family: var(--gg-font-editorial); font-size: 22px; font-weight: 900; line-height: 1.15; color: var(--gg-color-near-black); padding: 18px 18px 0; margin-bottom: 18px; }
.gg-hp-door-price { font-family: var(--gg-font-data); font-size: 12px; line-height: 1.5; color: var(--gg-color-secondary-brown); padding: 0 18px; margin: -12px 0 18px; }
.gg-hp-door-btn { margin: auto 18px 18px; display: block; text-align: center; padding: 12px 10px; background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; border: 2px solid var(--gg-color-dark-brown); transition: background-color .2s, color .2s; }
.gg-hp-door-btn:hover { background: var(--gg-color-gold); border-color: var(--gg-color-gold); color: var(--gg-color-near-black); }
.gg-hp-door--plan .gg-hp-door-btn { background: var(--gg-color-teal); border-color: var(--gg-color-teal); }

/* ── Skip link ───────────────────────────────────────────── */
.gg-hp-skip { position: absolute; left: -9999px; top: auto; width: 1px; height: 1px; overflow: hidden; font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; letter-spacing: 2px; padding: 12px 24px; background: var(--gg-color-gold); color: var(--gg-color-dark-brown); z-index: 100; }
.gg-hp-skip:focus { position: fixed; top: 0; left: 0; width: auto; height: auto; }

/* ── Wide desktop: 1440px+ ── */
@media (min-width: 1440px) {
  .gg-hp-hero-inner, .gg-hp-goal-hero-inner, .gg-hp-doors-head, .gg-hp-doors-grid { max-width: 1440px; }
  /* The poster canvases are drawn at 1080x1440px, so they display larger here without blur. */
  .gg-hp-poster-wall { height: 520px; }
  .gg-hp-poster { width: 300px; }
  .gg-hp-poster--0 { transform: translate(-50%, -50%) translateX(-120px) rotate(-8deg); }
  .gg-hp-poster--1 { width: 360px; }
  .gg-hp-poster--2 { transform: translate(-50%, -50%) translateX(120px) rotate(8deg); }
  .gg-hp-goal-title { font-size: 52px; }
  .gg-hp-goal-cta { font-size: 15px; padding: 20px 44px; }
  .gg-hp-hero h1 { font-size: 60px; }
}

/* ── Responsive: 1100px ── */
@media (max-width: 1100px) {
  .gg-hp-doors-grid { grid-template-columns: repeat(2, 1fr); }
}

/* ── Responsive: 900px ── */
@media (max-width: 900px) {
  .gg-hp-hero-inner, .gg-hp-goal-hero-inner { grid-template-columns: 1fr; gap: 40px; }
}

/* ── Responsive: 600px ── */
@media (max-width: 600px) {
  .gg-hp-goal-hero { padding: 36px 16px; }
  .gg-hp-poster-wall { height: 320px; }
  .gg-hp-poster { width: 160px; }
  .gg-hp-poster--1 { width: 190px; }
  .gg-hp-poster--0 { transform: translate(-50%, -50%) translateX(-60px) rotate(-8deg); }
  .gg-hp-poster--2 { transform: translate(-50%, -50%) translateX(60px) rotate(8deg); }
  .gg-hp-goal-title { font-size: 26px; }
  .gg-hp-goal-cta { width: 100%; text-align: center; }
  .gg-hp-hero { padding: 36px 16px; }
  .gg-hp-hero h1 { font-size: 32px; }
  .gg-hp-hero-search-input { font-size: 13px; padding: 12px; }
  .gg-hp-chip { padding: 5px 10px; font-size: 10px; }
  .gg-hp-hero-stat dd { font-size: 30px; }
  .gg-hp-top-row { padding: 12px 14px; grid-template-columns: 30px 1fr auto; }
  .gg-hp-top-name { font-size: 17px; }
  .gg-hp-doors { padding: 40px 16px 48px; }
  .gg-hp-doors-grid { grid-template-columns: 1fr; gap: 20px; }
}

/* ── Print ── */
@media print { .gg-hp-top-bar { display: none; } }

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) { .gg-hp-door, .gg-hp-door-btn, .gg-hp-top-row { transition: none; } }
''' + mega_footer_css + '''
</style>'''


# ── JavaScript ───────────────────────────────────────────────


def build_homepage_js() -> str:
    header_js = get_site_header_js()
    return '<script>\n' + header_js + '''
(function() {
'use strict';

// GA4 event tracking
document.querySelectorAll('[data-ga]').forEach(function(el) {
  el.addEventListener('click', function() {
    var event_name = el.getAttribute('data-ga');
    var label = el.getAttribute('data-ga-label') || '';
    if (typeof gtag === 'function') {
      var params = event_name === 'cta_click'
        ? { source: 'homepage', cta_name: label }
        : event_name === 'goal_hero_click'
        ? { src: label }
        : { event_label: label };
      gtag('event', event_name, params);
    }
  });
});

// Goal poster wall (2027 goals funnel hero, layout D1) — three SAMPLE
// posters, paper style, artwork changes on load or click only, never on a
// timer. Headline and MAKE MINE button never change (goals-2027-funnel D5).
(function() {
  var wall = document.getElementById('gg-poster-wall');
  if (!wall) return;
  var canvases = [
    document.getElementById('gg-goal-poster-0'),
    document.getElementById('gg-goal-poster-1'),
    document.getElementById('gg-goal-poster-2')
  ];
  if (canvases.indexOf(null) !== -1) return;

  // Fields match the athlete-facing questionnaire (season_review_variants.py):
  // habit + habit_when ("when and where"), an optional second habit, and
  // inner_obstacle ("not the weather, you" — the thing in them that gets in
  // the way). Invented examples, no named athletes, no invented statistics.
  var SAMPLES = [
    { goal: "Finish Unbound 200 under 14 hours.", why: "Because bailing at mile 40 stopped being funny.",
      habit: "One structured interval session", habit_when: "Tuesday mornings before the house wakes up",
      inner_obstacle: "I let a bad night's sleep talk me out of the hard days" },
    { goal: "Podium my age group at Mid South.", why: "Because I stood at the start line undertrained twice and swore never again.",
      habit: "Two hours of zone 2", habit_when: "Every Sunday, rain or shine",
      habit_2: "Strength work — Tuesday and Thursday evenings",
      inner_obstacle: "I skip the easy days because they don't feel like progress" },
    { goal: "Finish SBT GRVL without walking a single hill.", why: "Because the Stove Prairie climb humbled me and I haven't forgotten it.",
      habit: "Hill repeats", habit_when: "Every other Thursday after work",
      inner_obstacle: "I talk myself into the easier route when the legs feel heavy" },
    { goal: "Go sub-11 hours at Leadville 100.", why: "Because sub-11 has been the plan for three years running.",
      habit: "Strength work", habit_when: "Twice a week, no shortcuts",
      inner_obstacle: "I trade the gym for extra sleep more than I'd admit" },
    { goal: "Finish my first gravel century.", why: "Because someday never shows up on a training calendar.",
      habit: "A real structured ride", habit_when: "Every Saturday morning",
      inner_obstacle: "I let one missed week turn into three" }
  ];
  var GOAL_YEAR = new Date().getFullYear() + 1;
  var PAPER = { paper: "#f5efe6", ink: "#1a1613", teal: "#178079", gold: "#9a7e0a", grey: "#7d695d" };
  var MONO = "'Sometype Mono', monospace";
  var SERIF = "'Source Serif 4', Georgia, serif";

  function wrapText(ctx, text, maxWidth) {
    var words = String(text).split(/\\s+/), lines = [], line = "";
    words.forEach(function(word) {
      var next = line ? line + " " + word : word;
      if (ctx.measureText(next).width <= maxWidth || !line) { line = next; }
      else { lines.push(line); line = word; }
    });
    if (line) { lines.push(line); }
    return lines;
  }

  // Same layout as drawPoster() in generate_season_review.py, paper
  // themed. Every card gets a SAMPLE stamp — invented examples, never a
  // named athlete (goals-2027-funnel D5).
  function drawSamplePoster(canvas, sample) {
    var ctx = canvas.getContext('2d');
    if (!ctx) return;
    var W = canvas.width, H = canvas.height, pad = 84, inner = W - pad * 2;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = PAPER.paper;
    ctx.fillRect(0, 0, W, H);
    ctx.textBaseline = "top";

    ctx.font = "700 26px " + MONO;
    ctx.fillStyle = PAPER.gold;
    ctx.fillText(GOAL_YEAR + " GOAL FILE", pad, pad);
    ctx.fillStyle = PAPER.grey;
    ctx.textAlign = "right";
    ctx.fillText("GRAVEL GOD", W - pad, pad);
    ctx.textAlign = "left";
    ctx.font = "22px " + MONO;
    ctx.fillStyle = PAPER.grey;
    ctx.fillText("SAMPLE / GRAVELGODCYCLING.COM", pad, H - pad - 20);

    // Bottom block: the daily habit(s) and the thing most likely to wreck
    // it, anchored above the footer.
    var habit = sample.habit;
    if (habit && sample.habit_when) { habit += " — " + sample.habit_when; }
    var rows = [["EVERY DAY", habit],
                ["ALSO EVERY DAY", sample.habit_2 || ""],
                ["WATCH FOR", sample.inner_obstacle]]
      .filter(function(r) { return r[1]; })
      .map(function(r) {
        ctx.font = "30px " + MONO;
        return [r[0], wrapText(ctx, r[1], inner).slice(0, 2)];
      });
    var framed = rows.reduce(function(h, r) { return h + 56 + r[1].length * 38; }, 0);
    var frameTop = H - pad - 60 - framed;
    var y = frameTop;
    rows.forEach(function(row) {
      ctx.font = "700 24px " + MONO;
      ctx.fillStyle = PAPER.teal;
      ctx.fillText(row[0], pad, y);
      ctx.font = "30px " + MONO;
      ctx.fillStyle = PAPER.ink;
      row[1].forEach(function(line, i) { ctx.fillText(line, pad, y + 34 + i * 38); });
      y += 56 + row[1].length * 38;
    });

    // The deepest-sounding why, directly above the frame.
    ctx.font = "italic 38px " + SERIF;
    var whyLines = wrapText(ctx, '"' + sample.why + '"', inner).slice(0, 3);
    var whyHeight = whyLines.length * 50 + (whyLines.length ? 30 : 0);

    var labelY = pad + 200;
    var available = frameTop - whyHeight - labelY - 120;
    var goal = sample.goal;
    var size = 104, goalLines = [];
    [104, 92, 80, 68, 58, 48].forEach(function(candidate) {
      if (goalLines.length && goalLines.length * Math.round(size * 1.06) <= available) { return; }
      size = candidate;
      ctx.font = "700 " + size + "px " + SERIF;
      goalLines = wrapText(ctx, goal, inner);
    });

    ctx.font = "26px " + MONO;
    ctx.fillStyle = PAPER.grey;
    ctx.fillText("BY THE END OF " + GOAL_YEAR + ", I WILL", pad, labelY);

    ctx.font = "700 " + size + "px " + SERIF;
    ctx.fillStyle = PAPER.ink;
    y = labelY + 60;
    goalLines.slice(0, 6).forEach(function(line) { ctx.fillText(line, pad, y); y += Math.round(size * 1.06); });
    ctx.fillStyle = PAPER.teal;
    ctx.fillRect(pad, y + 24, 150, 6);

    ctx.font = "italic 38px " + SERIF;
    ctx.fillStyle = PAPER.grey;
    y = frameTop - whyHeight;
    whyLines.forEach(function(line) { ctx.fillText(line, pad, y); y += 50; });

    // Diagonal SAMPLE stamp — invented examples, never a real rider's poster.
    ctx.save();
    ctx.translate(W - 210, 210);
    ctx.rotate(-Math.PI / 10);
    ctx.font = "900 46px " + MONO;
    ctx.fillStyle = "rgba(192, 57, 43, 0.55)";
    ctx.strokeStyle = "rgba(192, 57, 43, 0.55)";
    ctx.lineWidth = 4;
    ctx.textAlign = "center";
    ctx.strokeRect(-140, -34, 280, 68);
    ctx.fillText("SAMPLE", 0, -14);
    ctx.restore();
  }

  function pick3(startIndex) {
    var order = [];
    for (var i = 0; i < 3; i++) { order.push(SAMPLES[(startIndex + i) % SAMPLES.length]); }
    return order;
  }

  // Random on load (never a timer); advance by 3 on click so the trio
  // always changes together.
  var cursor = Math.floor(Math.random() * SAMPLES.length);
  function render() {
    var picks = pick3(cursor);
    canvases.forEach(function(c, i) { drawSamplePoster(c, picks[i]); });
  }
  render();

  wall.addEventListener('click', function() {
    cursor = (cursor + 3) % SAMPLES.length;
    render();
  });
})();
})();
</script>'''


# ── JSON-LD ──────────────────────────────────────────────────


def build_jsonld(stats: dict) -> str:
    org = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Gravel God Cycling",
        "url": SITE_BASE_URL,
        "description": f"The definitive gravel race database. Honest ratings across {stats['dimensions']} criteria.",
    }
    website = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Gravel God Cycling",
        "url": SITE_BASE_URL,
        "potentialAction": {
            "@type": "SearchAction",
            "target": f"{SITE_BASE_URL}/gravel-races/?q={{search_term_string}}",
            "query-input": "required name=search_term_string",
        },
    }
    parts = [
        f'<script type="application/ld+json">{json.dumps(org, separators=(",",":"))}</script>',
        f'<script type="application/ld+json">{json.dumps(website, separators=(",",":"))}</script>',
    ]
    return "\n  ".join(parts)


# ── Page assembler ───────────────────────────────────────────


def generate_homepage(race_index: list) -> str:
    stats = compute_stats(race_index)
    canonical_url = f"{SITE_BASE_URL}/"
    # Round down to nearest 10 for title stability as the catalog changes.
    # (Was nearest 50 — with 384 races that rounded to a stale-looking "350+",
    # a 34-race/9% undercount. Nearest 10 stays accurate to within single
    # digits while still not flapping on every single new race added.)
    stable_count = (stats['race_count'] // 10) * 10
    title = f"{stable_count}+ Gravel, MTB & Ultra Races Rated for {CURRENT_YEAR} | Gravel God"
    meta_desc = (
        f"Find your next off-road cycling event. {stats['race_count']} races "
        f"worldwide, rated on {stats['dimensions']} criteria. Training plans and race intel."
    )

    top_bar = build_top_bar()
    nav = build_nav()
    goal_hero = build_goal_hero()
    hero = build_hero(stats, race_index)
    doors = build_doors()
    footer = build_footer()
    # Omit standalone source comments from the shipped CSS. Keep declarations,
    # strings, inline comments, and all page content unchanged.
    css = re.sub(r"(?m)^[ \t]*/\*(?:(?!\*/)[^\n])*\*/[ \t]*(?:\n|$)", "", build_homepage_css())
    js = build_homepage_js()
    jsonld = build_jsonld(stats)

    og_image = f"{SITE_BASE_URL}/og/homepage.jpg"
    og_tags = f'''<meta property="og:title" content="{esc(title)}">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{esc(og_image)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(title)}">
  <meta name="twitter:description" content="{esc(meta_desc)}">
  <meta name="twitter:image" content="{esc(og_image)}">'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  {get_favicon_head_snippet()}
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="alternate" type="application/rss+xml" title="Gravel God Race Database" href="https://gravelgodcycling.com/feed/races.xml">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {get_preload_hints()}
  {og_tags}
  {jsonld}
  {css}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>

<a href="#main" class="gg-hp-skip">Skip to content</a>
<div class="gg-hp-page">
  {top_bar}

  {nav}

  {goal_hero}

  {hero}

  {doors}

  {footer}
</div>

{js}

{get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God homepage")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument("--index-file", default=str(RACE_INDEX_PATH),
                        help="Path to race-index.json")
    # Kept so existing callers (preflight, CI, docs) still work; the page no
    # longer fetches anything over the network.
    parser.add_argument("--offline", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    race_index = load_race_index(Path(args.index_file))
    html_content = generate_homepage(race_index)

    output_file = output_dir / "homepage.html"
    output_file.write_text(html_content, encoding="utf-8")

    stats = compute_stats(race_index)
    print(f"Generated {output_file} ({len(html_content):,} bytes)")
    print(f"  {stats['race_count']} races, {stats['t1_count']} T1, {stats['t2_count']} T2, {stats['region_count']} regions, {stats['dimensions']} dimensions")


if __name__ == "__main__":
    main()
