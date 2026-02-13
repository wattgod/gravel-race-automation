#!/usr/bin/env python3
"""
Generate neo-brutalist landing page HTML for gravel race profiles.

Reads race data from race-data/*.json (new format) or data/*-data.json (old format),
produces self-contained HTML pages with:
  - Interactive accordion ratings (14 dimensions)
  - Sticky bottom CTA bar
  - Contextual mid-page CTA strips
  - Scroll fade-in animations
  - SportsEvent + FAQ JSON-LD structured data
  - Questionnaire-first training section

Usage:
    python generate_neo_brutalist.py unbound-200
    python generate_neo_brutalist.py unbound-200 --data-dir ../race-data
    python generate_neo_brutalist.py --all --data-dir ../race-data
    python generate_neo_brutalist.py --all --output-dir ./output
"""

import argparse
import hashlib
import html
import json
import math
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from brand_tokens import (
    BRAND_FONTS_DIR,
    COLORS,
    FONT_FILES,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
)

# ── Constants ──────────────────────────────────────────────────

COURSE_DIMS = ['logistics', 'length', 'technicality', 'elevation', 'climate', 'altitude', 'adventure']
OPINION_DIMS = ['prestige', 'race_quality', 'experience', 'community', 'field_depth', 'value', 'expenses']
ALL_DIMS = COURSE_DIMS + OPINION_DIMS

DIM_LABELS = {
    'logistics': 'Logistics',
    'length': 'Length',
    'technicality': 'Technicality',
    'elevation': 'Elevation',
    'climate': 'Climate',
    'altitude': 'Altitude',
    'adventure': 'Adventure',
    'prestige': 'Prestige',
    'race_quality': 'Race Quality',
    'experience': 'Experience',
    'community': 'Community',
    'field_depth': 'Field Depth',
    'value': 'Value',
    'expenses': 'Expenses',
}

# FAQ question templates per dimension
FAQ_TEMPLATES = {
    'climate': 'What is the climate like at {name}?',
    'logistics': 'How are the logistics for {name}?',
    'technicality': 'How technical is {name}?',
    'elevation': 'How much climbing is there at {name}?',
    'adventure': 'How adventurous is {name}?',
    'prestige': 'How prestigious is {name}?',
    'race_quality': 'What is the race quality like at {name}?',
    'experience': 'What is the race experience like at {name}?',
    'community': 'What is the community like at {name}?',
    'field_depth': 'How competitive is the field at {name}?',
    'value': 'Is {name} good value for money?',
    'expenses': 'How expensive is {name}?',
    'length': 'How long is {name}?',
    'altitude': 'What is the altitude at {name}?',
}

# Priority dimensions for FAQ schema (pick top 5 per race)
FAQ_PRIORITY = ['climate', 'logistics', 'adventure', 'prestige', 'technicality',
                'experience', 'race_quality', 'elevation', 'community', 'value']

# Month name → number mapping (shared by JSON-LD and training countdown)
MONTH_NUMBERS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

# US state names and abbreviations for country detection in JSON-LD
US_STATES = {
    'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
    'Connecticut', 'Delaware', 'Florida', 'Georgia', 'Hawaii', 'Idaho',
    'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky', 'Louisiana',
    'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
    'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada',
    'New Hampshire', 'New Jersey', 'New Mexico', 'New York',
    'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon',
    'Pennsylvania', 'Rhode Island', 'South Carolina', 'South Dakota',
    'Tennessee', 'Texas', 'Utah', 'Vermont', 'Virginia', 'Washington',
    'West Virginia', 'Wisconsin', 'Wyoming',
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY',
}

# Country name → ISO 3166-1 alpha-2 code
COUNTRY_CODES = {
    'Canada': 'CA', 'UK': 'GB', 'England': 'GB', 'Scotland': 'GB', 'Wales': 'GB',
    'Australia': 'AU', 'Queensland': 'AU', 'Victoria': 'AU',
    'South Australia': 'AU', 'New South Wales': 'AU', 'Western Australia': 'AU',
    'Italy': 'IT', 'Germany': 'DE', 'France': 'FR', 'Belgium': 'BE',
    'Belgian Ardennes': 'BE', 'Spain': 'ES', 'Switzerland': 'CH',
    'New Zealand': 'NZ', 'Colombia': 'CO', 'Chile': 'CL', 'Brazil': 'BR',
    'Argentina': 'AR', 'Sweden': 'SE', 'Austria': 'AT', 'Greece': 'GR',
    'Poland': 'PL', 'Finland': 'FI', 'Netherlands': 'NL', 'Norway': 'NO',
    'Portugal': 'PT', 'Romania': 'RO', 'South Africa': 'ZA', 'Kenya': 'KE',
    'Thailand': 'TH', 'Japan': 'JP', 'British Columbia': 'CA', 'Ontario': 'CA',
    'Southern Iceland': 'IS', 'Iceland': 'IS',
}


def detect_country(location: str) -> str:
    """Detect ISO country code from location string. Returns 'US' as default."""
    if not location or location == '--':
        return 'US'
    parts = [p.strip() for p in location.split(',')]
    # Check last part first (most specific), then second-to-last
    for part in reversed(parts):
        # Strip parentheticals: "Georgia (North Georgia mountains)" → "Georgia"
        clean = re.sub(r'\s*\(.*\)', '', part).strip()
        if clean in COUNTRY_CODES:
            return COUNTRY_CODES[clean]
        if clean in US_STATES:
            return 'US'
    return 'US'


QUESTIONNAIRE_SLUGS = {
    'unbound-200': 'unbound-200',
    'unbound-gravel-200': 'unbound-200',
    'mid-south': 'mid-south',
    'sbt-grvl': 'sbt-grvl',
    'bwr-california': 'bwr',
    'leadville-trail-100-mtb': 'leadville-100',
    'the-rift-iceland': 'rift-iceland',
    'gravel-worlds': 'gravel-worlds',
    'steamboat-gravel': 'steamboat-gravel',
}

QUESTIONNAIRE_BASE = "https://wattgod.github.io/training-plans-component/training-plan-questionnaire.html"
COACHING_URL = "https://www.wattgod.com/apply"
TRAINING_PLANS_URL = "/training-plans/"
SITE_BASE_URL = "https://gravelgodcycling.com"
GA_MEASUREMENT_ID = "G-EJJZ9T6M52"
SUBSTACK_URL = "https://gravelgodcycling.substack.com"
SUBSTACK_EMBED = "https://gravelgodcycling.substack.com/embed"
CURRENT_YEAR = str(datetime.now().year)


def build_seo_title(rd: dict) -> str:
    """Build an SEO-optimized <title> tag.

    Target format: "{Race Name} Review {Year} | {Location} | Gravel God"
    Falls back to shorter forms if title exceeds ~60 chars.
    """
    name = rd['name']
    location = rd['vitals'].get('location', '') or ''
    # Extract just state/country from full location like "Emporia, Kansas"
    loc_short = location.split(',')[-1].strip() if ',' in location else location

    # Try full format first
    full = f"{name} Review {CURRENT_YEAR} | {loc_short} | Gravel God"
    if len(full) <= 62:
        return full

    # Drop location if too long
    medium = f"{name} Review {CURRENT_YEAR} | Gravel God"
    if len(medium) <= 62:
        return medium

    # Minimal
    return f"{name} | Gravel God"


def build_seo_description(rd: dict) -> str:
    """Build an SEO-optimized meta description (120-155 chars target).

    Combines tagline + score/tier + call-to-action suffix.
    """
    tagline = rd['tagline'].rstrip('.')
    score = rd['overall_score']
    tier = rd['tier']
    tier_word = {1: 'Tier 1', 2: 'Tier 2', 3: 'Tier 3', 4: 'Tier 4'}.get(tier, f'Tier {tier}')
    suffix = f" Rated {score}/100 ({tier_word}). Course maps, ratings & full race breakdown."

    desc = f"{tagline}.{suffix}"
    if len(desc) <= 160:
        return desc

    # Truncate tagline — prefer breaking at sentence boundary
    max_tagline = 160 - len(suffix) - 1  # 1 for "."
    if max_tagline > 30:
        # Try to break at last complete sentence (period followed by space)
        candidate = tagline[:max_tagline]
        last_period = candidate.rfind('. ')
        if last_period > 30:
            truncated = candidate[:last_period]
        else:
            truncated = candidate.rsplit(' ', 1)[0].rstrip('.,;:—-')
        return f"{truncated}.{suffix}"

    # Fallback: just tagline + score
    return f"{tagline}. Rated {score}/100 ({tier_word}) by Gravel God."


# ── Phase 1: Data Adapter ─────────────────────────────────────

def normalize_race_data(data: dict) -> dict:
    """Normalize race data from new-format JSON into a consistent shape
    with all fields the generator expects. Computes derived fields if missing."""
    race = data.get('race', data)

    rating = race.get('gravel_god_rating', {})
    bor = race.get('biased_opinion_ratings', {})
    bo = race.get('biased_opinion', {})
    vitals = race.get('vitals', {})
    course = race.get('course_description', {})
    history = race.get('history', {})
    logistics = race.get('logistics', {})
    final_verdict = race.get('final_verdict', {})

    # Compute course_profile total if missing
    course_profile = sum(rating.get(d, 0) for d in COURSE_DIMS)
    opinion_total = sum(rating.get(d, 0) for d in OPINION_DIMS)

    # Build explanations dict from biased_opinion_ratings
    explanations = {}
    for dim in ALL_DIMS:
        entry = bor.get(dim, {})
        explanations[dim] = {
            'score': entry.get('score', rating.get(dim, 0)),
            'explanation': entry.get('explanation', ''),
        }

    # Extract date with year from date_specific like "2026: June 6" -> "June 6, 2026"
    date_specific = vitals.get('date_specific', '')
    short_date = date_specific
    date_match = re.search(r'(\d{4}):\s*(.+)', date_specific)
    if date_match:
        year = date_match.group(1)
        date_part = date_match.group(2).strip()
        short_date = f"{date_part}, {year}"

    # Parse entry cost from registration string, then fallback to rating explanations
    reg = vitals.get('registration', '')
    entry_cost = None
    cost_match = re.search(r'[\$€£][\d,]+(?:\s*[-–]\s*[\$€£]?[\d,]+)?', reg)
    if cost_match:
        entry_cost = cost_match.group(0)
    if not entry_cost:
        # Fallback: scan value/expenses explanations for dollar amounts
        for dim_key in ('value', 'expenses', 'logistics'):
            expl = bor.get(dim_key, {}).get('explanation', '')
            fallback_match = re.search(r'\$[\d,]+', expl)
            if fallback_match:
                entry_cost = fallback_match.group(0)
                break

    # Parse field size into short form
    field_size_raw = vitals.get('field_size', '')
    field_size_short = field_size_raw
    # Try to get just the number part
    fs_match = re.search(r'~?([\d,]+\+?)', str(field_size_raw))
    if fs_match:
        field_size_short = '~' + fs_match.group(1)

    return {
        'name': race.get('display_name') or race.get('name', 'Unknown Race'),
        'slug': race.get('slug', ''),
        'tagline': race.get('tagline', ''),
        'overall_score': rating.get('overall_score', 0),
        'tier': rating.get('tier', 4),
        'tier_label': rating.get('tier_label', f"TIER {rating.get('tier', 4)}"),
        'course_profile': course_profile,
        'opinion_total': opinion_total,
        'rating': rating,
        'explanations': explanations,
        'vitals': {
            'distance': f"{vitals.get('distance_mi', '--')} mi" if vitals.get('distance_mi') else '--',
            'elevation': f"{vitals.get('elevation_ft', '--'):,} ft".replace(',', ',') if isinstance(vitals.get('elevation_ft'), (int, float)) else str(vitals.get('elevation_ft', '--')),
            'location': vitals.get('location', '--'),
            'location_badge': vitals.get('location_badge', vitals.get('location', '--')),
            'date': short_date or vitals.get('date', '--'),
            'date_specific': date_specific,
            'field_size': field_size_short,
            'field_size_raw': field_size_raw,
            'entry_cost': entry_cost,
            'start_time': vitals.get('start_time', ''),
            'registration': reg,
            'prize_purse': vitals.get('prize_purse', ''),
            'aid_stations': vitals.get('aid_stations', ''),
            'cutoff_time': vitals.get('cutoff_time', ''),
            'terrain_types': vitals.get('terrain_types', []),
        },
        'biased_opinion': {
            'verdict': bo.get('verdict', ''),
            'summary': bo.get('summary', ''),
            'strengths': bo.get('strengths', []),
            'weaknesses': bo.get('weaknesses', []),
            'bottom_line': bo.get('bottom_line', ''),
        },
        'final_verdict': {
            'score': final_verdict.get('score', ''),
            'one_liner': final_verdict.get('one_liner', ''),
            'should_you_race': final_verdict.get('should_you_race', ''),
            'alternatives': final_verdict.get('alternatives', ''),
        },
        'course': {
            'character': course.get('character', ''),
            'suffering_zones': course.get('suffering_zones', []),
            'signature_challenge': course.get('signature_challenge', ''),
            'ridewithgps_id': course.get('ridewithgps_id'),
            'ridewithgps_name': course.get('ridewithgps_name', ''),
            'map_url': course.get('map_url', ''),
        },
        'history': {
            'founded': history.get('founded'),
            'founder': history.get('founder', ''),
            'origin_story': history.get('origin_story', ''),
            'notable_moments': history.get('notable_moments', []),
            'reputation': history.get('reputation', ''),
        },
        'logistics': {
            'airport': logistics.get('airport', ''),
            'lodging_strategy': logistics.get('lodging_strategy', ''),
            'food': logistics.get('food', ''),
            'packet_pickup': logistics.get('packet_pickup', ''),
            'parking': logistics.get('parking', ''),
            'official_site': logistics.get('official_site', ''),
        },
        'terrain': race.get('terrain', {}),
        'climate_data': race.get('climate', {}),
        'race_photos': race.get('race_photos', []),
        'citations': race.get('citations', []),
    }


def get_questionnaire_url(slug: str) -> str:
    """Return questionnaire URL for a race, with race param if supported."""
    mapped = QUESTIONNAIRE_SLUGS.get(slug)
    if mapped:
        return f"{QUESTIONNAIRE_BASE}?race={mapped}"
    return QUESTIONNAIRE_BASE


# ── Phase 2: HTML Builders ─────────────────────────────────────

def esc(text: Any) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ''


def score_bar_color(score: int) -> str:
    """Return brand-consistent bar color based on score (1-5).
    5: teal, 4: gold, 3: primary brown, 2: secondary brown, 1: tan."""
    return {
        5: COLORS['teal'],
        4: COLORS['gold'],
        3: COLORS['primary_brown'],
        2: COLORS['secondary_brown'],
        1: COLORS['tan'],
    }.get(score, COLORS['tan'])


RADAR_LABELS = {
    'logistics': 'Logistics',
    'length': 'Length',
    'technicality': 'Technical',
    'elevation': 'Elevation',
    'climate': 'Climate',
    'altitude': 'Altitude',
    'adventure': 'Adventure',
    'prestige': 'Prestige',
    'race_quality': 'Quality',
    'experience': 'Experience',
    'community': 'Community',
    'field_depth': 'Field',
    'value': 'Value',
    'expenses': 'Expenses',
}


def _radar_svg(dims: list, explanations: dict, color_fill: str, color_stroke: str,
               label: str, total: int, max_total: int, idx_offset: int = 0) -> str:
    """Generate an SVG radar chart for a set of dimensions."""
    n = len(dims)
    w, h = 440, 380
    cx, cy, r = w // 2, 180, 100
    angle_offset = -math.pi / 2  # start at top
    label_r = r + 28

    def point(angle: float, dist: float) -> tuple:
        return (cx + dist * math.cos(angle), cy + dist * math.sin(angle))

    # Grid rings (1-5)
    grid_lines = []
    for level in range(1, 6):
        frac = level / 5
        pts = ' '.join(f'{point(angle_offset + i * 2 * math.pi / n, r * frac)[0]:.1f},'
                       f'{point(angle_offset + i * 2 * math.pi / n, r * frac)[1]:.1f}'
                       for i in range(n))
        opacity = '0.3' if level < 5 else '0.5'
        grid_lines.append(f'<polygon points="{pts}" fill="none" stroke="{COLORS["secondary_brown"]}" stroke-opacity="{opacity}" stroke-width="0.5"/>')

    # Axis lines
    axis_lines = []
    for i in range(n):
        angle = angle_offset + i * 2 * math.pi / n
        x2, y2 = point(angle, r)
        axis_lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{COLORS["tan"]}" stroke-width="0.5"/>')

    # Data polygon
    scores = []
    for dim in dims:
        entry = explanations.get(dim, {})
        scores.append(entry.get('score', 0))

    data_pts = ' '.join(
        f'{point(angle_offset + i * 2 * math.pi / n, r * s / 5)[0]:.1f},'
        f'{point(angle_offset + i * 2 * math.pi / n, r * s / 5)[1]:.1f}'
        for i, s in enumerate(scores)
    )

    # Score dots — clickable, with hover ring
    dots = []
    for i, s in enumerate(scores):
        angle = angle_offset + i * 2 * math.pi / n
        dx, dy = point(angle, r * s / 5)
        dim_label = RADAR_LABELS.get(dims[i], dims[i].replace('_', ' ').title())
        # Invisible larger hit area + visible dot + hover ring
        dots.append(
            f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="12" fill="transparent" '
            f'class="gg-radar-hit" data-accordion-idx="{idx_offset + i}" '
            f'data-label="{esc(dim_label)}" data-score="{s}" style="cursor:pointer"/>'
            f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="5" fill="{color_stroke}" '
            f'stroke="{COLORS["dark_brown"]}" stroke-width="1.5" class="gg-radar-dot" pointer-events="none" opacity="0"/>'
            f'<circle cx="{dx:.1f}" cy="{dy:.1f}" r="10" fill="none" '
            f'stroke="{color_stroke}" stroke-width="1.5" opacity="0" '
            f'class="gg-radar-ring" pointer-events="none"/>'
        )

    # Labels — two lines: name + score
    labels = []
    for i, dim in enumerate(dims):
        angle = angle_offset + i * 2 * math.pi / n
        lx, ly = point(angle, label_r)
        dim_label = RADAR_LABELS.get(dim, dim.replace('_', ' ').title())
        s = scores[i]
        anchor = 'middle'
        if lx < cx - 15:
            anchor = 'end'
        elif lx > cx + 15:
            anchor = 'start'
        labels.append(
            f'<text x="{lx:.1f}" y="{ly - 5:.1f}" text-anchor="{anchor}" '
            f'dominant-baseline="central" font-size="10" font-weight="700" '
            f'fill="{COLORS["dark_brown"]}" font-family="Sometype Mono, monospace" letter-spacing="0.5">'
            f'{esc(dim_label.upper())}</text>'
            f'<text x="{lx:.1f}" y="{ly + 7:.1f}" text-anchor="{anchor}" '
            f'dominant-baseline="central" font-size="10" font-weight="700" '
            f'fill="{color_stroke}" font-family="Sometype Mono, monospace">'
            f'{s}/5</text>'
        )

    # Total in center
    center_label = (
        f'<text x="{cx}" y="{cy - 6}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="22" font-weight="700" fill="{color_stroke}" font-family="Sometype Mono, monospace">'
        f'{total}</text>'
        f'<text x="{cx}" y="{cy + 10}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="9" fill="{COLORS["secondary_brown"]}" font-family="Sometype Mono, monospace" letter-spacing="1">'
        f'/{max_total}</text>'
    )

    return f'''<div class="gg-radar-chart" data-color="{color_stroke}">
    <svg viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" class="gg-radar-svg">
      {''.join(grid_lines)}
      {''.join(axis_lines)}
      <polygon points="{data_pts}" fill="{color_fill}" class="gg-radar-polygon" fill-opacity="0" stroke="{color_stroke}" stroke-width="2.5" stroke-dasharray="1000" stroke-dashoffset="1000"/>
      {''.join(dots)}
      {''.join(labels)}
      {center_label}
      <rect class="gg-radar-tooltip-bg" x="0" y="0" width="0" height="0" fill="{COLORS['near_black']}" rx="0" opacity="0"/>
      <text class="gg-radar-tooltip-text" x="0" y="0" fill="#fff" font-size="10" font-weight="700" font-family="Sometype Mono, monospace" opacity="0"></text>
    </svg>
    <div class="gg-radar-label">{esc(label)}</div>
  </div>'''


def build_radar_charts(explanations: dict, course_total: int, opinion_total: int) -> str:
    """Build side-by-side radar charts for Course Profile and Editorial dimensions."""
    course_chart = _radar_svg(COURSE_DIMS, explanations,
                              COLORS['teal'], COLORS['teal'],
                              'Course Profile', course_total, 35, idx_offset=0)
    editorial_chart = _radar_svg(OPINION_DIMS, explanations,
                                 COLORS['gold'], COLORS['gold'],
                                 'Editorial', opinion_total, 35, idx_offset=7)
    return f'<div class="gg-radar-pair">\n{course_chart}\n{editorial_chart}\n</div>'


def build_accordion_html(dims: list, explanations: dict, idx_offset: int = 0) -> str:
    """Build accordion HTML for a list of dimension keys.
    idx_offset shifts data-idx for tile click targeting (0 for course, 7 for editorial)."""
    items = []
    for i, dim in enumerate(dims):
        entry = explanations.get(dim, {})
        score = entry.get('score', 0)
        explanation = entry.get('explanation', '')
        label = DIM_LABELS.get(dim, dim.replace('_', ' ').title())
        pct = int((score / 5) * 100) if score else 0
        has_content = bool(explanation.strip())
        bar_color = score_bar_color(score)

        trigger_class = 'gg-accordion-trigger'
        arrow = '&#x25B6;' if has_content else ''

        item = f'''<div class="gg-accordion-item" data-accordion-idx="{idx_offset + i}">
  <button class="{trigger_class}" aria-expanded="false"{' data-no-content="true"' if not has_content else ''}>
    <span class="gg-accordion-label">{esc(label)}</span>
    <span class="gg-accordion-bar-track"><span class="gg-accordion-bar-fill" style="width:{pct}%;background:{bar_color}"></span></span>
    <span class="gg-accordion-score">{score}/5</span>
    <span class="gg-accordion-arrow">{arrow}</span>
  </button>'''
        if has_content:
            item += f'''
  <div class="gg-accordion-panel">
    <div class="gg-accordion-content">{esc(explanation)}</div>
  </div>'''
        item += '\n</div>'
        items.append(item)

    return '<div class="gg-accordion">\n' + '\n'.join(items) + '\n</div>'


def build_sticky_cta(race_name: str, url: str) -> str:
    """Build sticky bottom CTA bar HTML."""
    return f'''<div class="gg-sticky-cta" id="gg-sticky-cta">
  <div class="gg-sticky-cta-inner">
    <span class="gg-sticky-cta-name">{esc(race_name)}</span>
    <div style="display:flex;align-items:center;gap:12px">
      <a href="{esc(TRAINING_PLANS_URL)}" class="gg-btn">BUILD MY PLAN &mdash; $15/WK</a>
      <button class="gg-sticky-dismiss" onclick="document.getElementById(\'gg-sticky-cta\').style.display=\'none\';try{{sessionStorage.setItem(\'gg-cta-dismissed\',\'1\')}}catch(e){{}}" aria-label="Dismiss">&times;</button>
    </div>
  </div>
</div>'''


def build_inline_js() -> str:
    """Build the inline JavaScript for all interactive features."""
    return r'''<script>
// Accordion toggle (independent mode — multiple can be open)
document.querySelectorAll('.gg-accordion-trigger').forEach(function(trigger) {
  if (trigger.dataset.noContent) return;
  trigger.addEventListener('click', function() {
    var item = trigger.closest('.gg-accordion-item');
    var expanded = item.classList.toggle('is-open');
    trigger.setAttribute('aria-expanded', expanded);
  });
});

// Race day countdown (HTML shows date for crawlers; JS replaces with day count)
(function() {
  var cd = document.querySelector('.gg-countdown');
  if (!cd) return;
  var dateStr = cd.getAttribute('data-date');
  if (!dateStr) return;
  var raceDate = new Date(dateStr + 'T00:00:00');
  var now = new Date();
  var diff = Math.ceil((raceDate - now) / (1000 * 60 * 60 * 24));
  var el = document.getElementById('gg-days-left');
  if (el && diff > 0) {
    el.textContent = diff;
    // Replace "RACE NAME" with "DAYS UNTIL RACE NAME"
    var textNodes = cd.childNodes;
    for (var i = 0; i < textNodes.length; i++) {
      if (textNodes[i].nodeType === 3 && textNodes[i].textContent.trim()) {
        textNodes[i].textContent = ' DAYS UNTIL' + textNodes[i].textContent;
        break;
      }
    }
  } else if (el && diff <= 0) {
    cd.style.display = 'none';
  }
})();

// Hero score counter animation (starts from 0, real score is in HTML for crawlers)
(function() {
  var el = document.querySelector('.gg-hero-score-number');
  if (!el) return;
  var target = parseInt(el.getAttribute('data-target'), 10);
  if (!target) return;
  el.textContent = '0';
  var duration = 1500;
  var start = null;
  function step(ts) {
    if (!start) start = ts;
    var progress = Math.min((ts - start) / duration, 1);
    var ease = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(ease * target);
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
})();

// Radar chart interactions
(function() {
  // Draw-in animation on scroll
  if ('IntersectionObserver' in window) {
    var radarObs = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-drawn');
          // Stagger dot reveal
          var dots = entry.target.querySelectorAll('.gg-radar-dot');
          dots.forEach(function(dot, i) {
            dot.style.transitionDelay = (0.8 + i * 0.08) + 's';
          });
          radarObs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.3 });
    document.querySelectorAll('.gg-radar-chart').forEach(function(chart) {
      radarObs.observe(chart);
    });
  }

  // Click + hover on data points
  document.querySelectorAll('.gg-radar-hit').forEach(function(hit) {
    var svg = hit.closest('svg');
    var ring = hit.nextElementSibling ? hit.nextElementSibling.nextElementSibling : null;
    var tooltipBg = svg.querySelector('.gg-radar-tooltip-bg');
    var tooltipText = svg.querySelector('.gg-radar-tooltip-text');

    hit.addEventListener('mouseenter', function() {
      if (ring) ring.style.opacity = '1';
      // Show tooltip
      var label = hit.getAttribute('data-label');
      var score = hit.getAttribute('data-score');
      var txt = label + ': ' + score + '/5';
      var cx = parseFloat(hit.getAttribute('cx'));
      var cy = parseFloat(hit.getAttribute('cy'));
      tooltipText.textContent = txt;
      var tLen = txt.length * 6.5 + 16;
      tooltipText.setAttribute('x', cx);
      tooltipText.setAttribute('y', cy - 22);
      tooltipText.setAttribute('text-anchor', 'middle');
      tooltipText.style.opacity = '1';
      tooltipBg.setAttribute('x', cx - tLen / 2);
      tooltipBg.setAttribute('y', cy - 34);
      tooltipBg.setAttribute('width', tLen);
      tooltipBg.setAttribute('height', 22);
      tooltipBg.style.opacity = '0.9';
    });

    hit.addEventListener('mouseleave', function() {
      if (ring) ring.style.opacity = '0';
      tooltipText.style.opacity = '0';
      tooltipBg.style.opacity = '0';
    });

    // Click → open accordion and scroll
    hit.addEventListener('click', function() {
      var idx = hit.getAttribute('data-accordion-idx');
      var target = document.querySelector('.gg-accordion-item[data-accordion-idx="' + idx + '"]');
      if (!target) return;
      if (!target.classList.contains('is-open')) {
        target.classList.add('is-open');
        var trigger = target.querySelector('.gg-accordion-trigger');
        if (trigger) trigger.setAttribute('aria-expanded', 'true');
      }
      // Brief highlight
      target.classList.add('is-highlighted');
      setTimeout(function() { target.classList.remove('is-highlighted'); }, 1500);
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  });
})();

// Stat card count-up on scroll
(function() {
  if (!('IntersectionObserver' in window)) return;
  var statObs = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (!entry.isIntersecting) return;
      var el = entry.target;
      var text = el.textContent.trim();
      var match = text.match(/^[~$]?([\d,]+)/);
      if (!match) { statObs.unobserve(el); return; }
      var prefix = text.substring(0, text.indexOf(match[1]));
      var suffix = text.substring(text.indexOf(match[1]) + match[1].length);
      var target = parseInt(match[1].replace(/,/g, ''), 10);
      if (!target || target > 100000) { statObs.unobserve(el); return; }
      var duration = 1200;
      var start = null;
      function step(ts) {
        if (!start) start = ts;
        var progress = Math.min((ts - start) / duration, 1);
        var ease = 1 - Math.pow(1 - progress, 3);
        var val = Math.round(ease * target);
        el.textContent = prefix + val.toLocaleString() + suffix;
        if (progress < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
      statObs.unobserve(el);
    });
  }, { threshold: 0.5 });
  document.querySelectorAll('.gg-stat-countable').forEach(function(el) {
    statObs.observe(el);
  });
})();

// Difficulty gauge fill animation
(function() {
  if (!('IntersectionObserver' in window)) return;
  document.querySelectorAll('.gg-difficulty-fill').forEach(function(el) {
    new IntersectionObserver(function(entries, obs) {
      if (entries[0].isIntersecting) {
        el.style.width = el.getAttribute('data-width') + '%';
        obs.unobserve(el);
      }
    }, { threshold: 0.5 }).observe(el);
  });
})();

// Staggered timeline + suffering zone reveals
(function() {
  if (!('IntersectionObserver' in window)) return;
  function staggerReveal(selector, baseDelay) {
    var items = document.querySelectorAll(selector);
    if (!items.length) return;
    var parent = items[0].closest('.gg-section');
    if (!parent) return;
    new IntersectionObserver(function(entries, obs) {
      if (entries[0].isIntersecting) {
        items.forEach(function(item, i) {
          setTimeout(function() { item.classList.add('is-visible'); }, baseDelay + i * 120);
        });
        obs.unobserve(parent);
      }
    }, { threshold: 0.2 }).observe(parent);
  }
  staggerReveal('.gg-timeline-item', 200);
  staggerReveal('.gg-suffering-zone', 100);
})();

// Sticky CTA + scroll fade-in
if ('IntersectionObserver' in window) {
  var stickyCta = document.getElementById('gg-sticky-cta');
  try { if (sessionStorage.getItem('gg-cta-dismissed')) { if (stickyCta) stickyCta.style.display = 'none'; stickyCta = null; } } catch(e) {}
  var hero = document.querySelector('.gg-hero');
  var training = document.getElementById('training');

  var heroVisible = true;
  var trainingVisible = false;

  function updateSticky() {
    if (!stickyCta) return;
    if (!heroVisible && !trainingVisible) {
      stickyCta.classList.add('is-visible');
    } else {
      stickyCta.classList.remove('is-visible');
    }
  }

  if (hero) {
    new IntersectionObserver(function(entries) {
      heroVisible = entries[0].isIntersecting;
      updateSticky();
    }).observe(hero);
  }
  if (training) {
    new IntersectionObserver(function(entries) {
      trainingVisible = entries[0].isIntersecting;
      updateSticky();
    }).observe(training);
  }

  // Scroll fade-in
  var fadeObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        fadeObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.15 });

  document.querySelectorAll('.gg-fade-section').forEach(function(el) {
    fadeObserver.observe(el);
  });

  // Back to top button
  var btt = document.getElementById('gg-back-to-top');
  if (btt && hero) {
    new IntersectionObserver(function(entries) {
      if (entries[0].isIntersecting) {
        btt.classList.remove('is-visible');
      } else {
        btt.classList.add('is-visible');
      }
    }).observe(hero);
    btt.addEventListener('click', function() {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }
}

// News ticker — multi-source (Google News + Reddit)
(function() {
  var ticker = document.getElementById('gg-news-ticker');
  var feed = document.getElementById('gg-news-feed');
  if (!ticker || !feed) return;
  var query = ticker.getAttribute('data-query');
  if (!query) return;

  function parseItem(item) {
    var title = item.title || '';
    var source = item.author || '';
    var dashIdx = title.lastIndexOf(' - ');
    if (!source && dashIdx > 0) {
      source = title.substring(dashIdx + 3).trim();
      title = title.substring(0, dashIdx).trim();
    }
    return { title: title, link: item.link, source: source, date: new Date(item.pubDate) };
  }

  // Use quoted query for exact match in Google News
  var newsUrl = 'https://api.rss2json.com/v1/api.json?rss_url=' + encodeURIComponent(
    'https://news.google.com/rss/search?q=' + encodeURIComponent('"' + query.replace(/\+/g, ' ') + '"') + '&hl=en-US&gl=US&ceid=US:en');
  var redditUrl = 'https://api.rss2json.com/v1/api.json?rss_url=' + encodeURIComponent(
    'https://www.reddit.com/search.rss?q=' + encodeURIComponent('"' + query.replace(/\+/g, ' ') + '"') + '&sort=new&t=year');

  // Build keywords from race name for relevance filtering
  var nameWords = query.replace(/\+/g, ' ').toLowerCase().split(' ').filter(function(w) { return w.length > 2; });

  // Timeout helper — abort fetch after 6 seconds
  function fetchWithTimeout(url, ms) {
    var controller = new AbortController();
    var timer = setTimeout(function() { controller.abort(); }, ms);
    return fetch(url, { signal: controller.signal })
      .then(function(r) { clearTimeout(timer); return r.json(); })
      .catch(function() { clearTimeout(timer); return { items: [] }; });
  }

  Promise.allSettled([
    fetchWithTimeout(newsUrl, 6000),
    fetchWithTimeout(redditUrl, 6000)
  ]).then(function(results) {
    var all = [];
    results.forEach(function(result) {
      if (result.status === 'fulfilled' && result.value.items) {
        result.value.items.forEach(function(item) {
          var parsed = parseItem(item);
          // Relevance filter: title must contain at least one key word from race name
          var titleLow = parsed.title.toLowerCase();
          var relevant = nameWords.some(function(w) { return titleLow.indexOf(w) !== -1; });
          if (relevant) all.push(parsed);
        });
      }
    });

    // Sort by date descending, take top 8
    all.sort(function(a, b) { return b.date - a.date; });
    all = all.slice(0, 8);

    if (all.length === 0) {
      ticker.style.display = 'none';
      return;
    }

    function buildTickerItems(items) {
      var frag = document.createDocumentFragment();
      items.forEach(function(item, i) {
        if (i > 0) {
          var sep = document.createElement('span');
          sep.className = 'gg-news-ticker-sep';
          sep.textContent = '\u25C6';
          frag.appendChild(sep);
        }
        var span = document.createElement('span');
        span.className = 'gg-news-ticker-item';
        var a = document.createElement('a');
        a.href = item.link;
        a.target = '_blank';
        a.rel = 'noopener';
        a.textContent = item.title;
        span.appendChild(a);
        if (item.source) {
          var src = document.createElement('span');
          src.className = 'gg-news-ticker-source';
          src.textContent = item.source;
          span.appendChild(src);
        }
        frag.appendChild(span);
      });
      return frag;
    }
    feed.innerHTML = '';
    feed.appendChild(buildTickerItems(all));
    ticker.style.display = '';
    // Spacer + duplicate for seamless loop
    var spacer = document.createElement('span');
    spacer.style.padding = '0 80px';
    feed.appendChild(spacer);
    feed.appendChild(buildTickerItems(all));
  });
})();

// FAQ accordion toggle
document.querySelectorAll('.gg-faq-question').forEach(function(q) {
  q.addEventListener('click', function() {
    var item = this.parentElement;
    item.classList.toggle('open');
    this.setAttribute('aria-expanded', item.classList.contains('open'));
  });
  q.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      this.click();
    }
  });
});
</script>'''


# ── Phase 3D: JSON-LD Schema ──────────────────────────────────

def build_sports_event_jsonld(rd: dict) -> dict:
    """Build SportsEvent JSON-LD from normalized race data."""
    jsonld = {
        "@context": "https://schema.org",
        "@type": "SportsEvent",
        "name": rd['name'],
        "description": rd['tagline'],
        "sport": "Gravel Cycling",
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
    }

    # Parse ISO date
    date_specific = rd['vitals'].get('date_specific', '')
    date_match = re.search(r'(\d{4}).*?(\w+)\s+(\d+)(?:-(\d+))?', date_specific)
    if date_match:
        year, month_name, day = date_match.group(1), date_match.group(2), date_match.group(3)
        end_day = date_match.group(4)
        month_num = MONTH_NUMBERS.get(month_name.lower(), "01")
        jsonld["startDate"] = f"{year}-{month_num}-{int(day):02d}"
        jsonld["endDate"] = f"{year}-{month_num}-{int(end_day):02d}" if end_day else jsonld["startDate"]

    # Location with PostalAddress — detect country from location string
    location = rd['vitals'].get('location', '')
    if location and location != '--':
        parts = [p.strip() for p in location.split(',')]
        country = detect_country(location)
        place = {"@type": "Place", "name": location}
        if len(parts) >= 2:
            place["address"] = {
                "@type": "PostalAddress",
                "addressLocality": parts[0],
                "addressRegion": parts[1] if len(parts) > 2 else parts[-1],
                "addressCountry": country,
            }
        jsonld["location"] = place

    # OG image
    jsonld["image"] = f"{SITE_BASE_URL}/og/{rd['slug']}.jpg"

    # Organizer from history.founder — skip generic stub text
    founder = rd.get('history', {}).get('founder', '')
    official_site = rd['logistics'].get('official_site', '')
    if founder and not founder.endswith('organizers') and founder != 'Unknown':
        org = {"@type": "Person", "name": founder}
        if official_site and official_site.startswith('http'):
            org["url"] = official_site
        jsonld["organizer"] = org

    # Parse price — supports $, €, £ and "NNN EUR/GBP" formats
    reg = rd['vitals'].get('registration', '')
    price_match = re.search(r'\$(\d+)', reg)
    euro_match = re.search(r'€\s*(\d+)', reg)
    gbp_match = re.search(r'£\s*(\d+)', reg)
    eur_text_match = re.search(r'(\d+)\s*EUR', reg)
    gbp_text_match = re.search(r'(\d+)\s*GBP', reg)
    if price_match or euro_match or gbp_match or eur_text_match or gbp_text_match:
        if price_match:
            price, currency = price_match.group(1), "USD"
        elif euro_match:
            price, currency = euro_match.group(1), "EUR"
        elif eur_text_match:
            price, currency = eur_text_match.group(1), "EUR"
        elif gbp_match:
            price, currency = gbp_match.group(1), "GBP"
        else:
            price, currency = gbp_text_match.group(1), "GBP"
        offer = {
            "@type": "Offer",
            "price": price,
            "priceCurrency": currency,
            "availability": "https://schema.org/LimitedAvailability",
        }
        if official_site and official_site.startswith('http'):
            offer["url"] = official_site
        if jsonld.get("startDate"):
            offer["validFrom"] = jsonld["startDate"]
        jsonld["offers"] = offer

    if rd['overall_score']:
        jsonld["review"] = {
            "@type": "Review",
            "author": {
                "@type": "Organization",
                "name": "Gravel God",
                "url": SITE_BASE_URL,
            },
            "reviewRating": {
                "@type": "Rating",
                "ratingValue": str(rd['overall_score']),
                "bestRating": "100",
                "worstRating": "0",
            },
        }

    if official_site and official_site.startswith('http'):
        jsonld["url"] = official_site

    # Performer — use organizer as the event performer
    if jsonld.get("organizer"):
        jsonld["performer"] = jsonld["organizer"]

    return jsonld


def build_faq_jsonld(rd: dict) -> Optional[dict]:
    """Build FAQPage JSON-LD from top rating explanations + verdict."""
    explanations = rd.get('explanations', {})
    name = rd['name']

    questions = []
    # Pick top 5 dimensions by FAQ_PRIORITY that have explanations
    for dim in FAQ_PRIORITY:
        if len(questions) >= 5:
            break
        entry = explanations.get(dim, {})
        expl = entry.get('explanation', '').strip()
        if not expl:
            continue
        q_template = FAQ_TEMPLATES.get(dim, f'What about {dim} at {{name}}?')
        questions.append({
            "@type": "Question",
            "name": q_template.format(name=name),
            "acceptedAnswer": {
                "@type": "Answer",
                "text": expl,
            }
        })

    # Add verdict question
    should_race = rd['final_verdict'].get('should_you_race', '').strip()
    if should_race:
        questions.append({
            "@type": "Question",
            "name": f"Should I race {name}?",
            "acceptedAnswer": {
                "@type": "Answer",
                "text": should_race,
            }
        })

    if not questions:
        return None

    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": questions,
    }


# ── Phase 3: Section Builders ─────────────────────────────────

def build_hero(rd: dict) -> str:
    """Build hero section with OG image background."""
    score = rd['overall_score']
    slug = rd['slug']
    og_style = f' style="background-image:linear-gradient(rgba(58,46,37,0.82),rgba(58,46,37,0.92)),url(/og/{esc(slug)}.jpg);background-size:cover;background-position:center"'
    official = rd['logistics'].get('official_site', '')
    site_btn = ''
    if official and official.startswith('http'):
        site_btn = f'\n  <a href="{esc(official)}" class="gg-btn gg-btn--hero-site" target="_blank" rel="noopener">OFFICIAL SITE &rarr;</a>'
    return f'''<section class="gg-hero"{og_style}>
  <span class="gg-hero-tier">{esc(rd['tier_label'])}</span>
  <h1 data-text="{esc(rd['name'])}">{esc(rd['name'])}</h1>
  <p class="gg-hero-tagline">{esc(rd['tagline'])}</p>{site_btn}
  <div class="gg-hero-score">
    <div class="gg-hero-score-number" data-target="{score}">{score}</div>
    <div class="gg-hero-score-label">/ 100</div>
  </div>
</section>'''


def build_toc() -> str:
    """Build table of contents nav."""
    links = [
        ('course', '01 Course Overview'),
        ('history', '02 Facts &amp; History'),
        ('route', '03 The Course'),
        ('ratings', '04 The Ratings'),
        ('verdict', '05 Final Verdict'),
        ('training', '06 Training'),
        ('logistics', '07 Race Logistics'),
        ('citations', '08 Sources'),
    ]
    items = '\n  '.join(f'<a href="#{href}">{label}</a>' for href, label in links)
    return f'<nav class="gg-toc" aria-label="Table of contents">\n  {items}\n</nav>'


def _extract_state(location: str) -> str:
    """Extract state/country from location string like 'Emporia, Kansas'."""
    if not location:
        return ''
    m = re.match(r'.+,\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)', location)
    return m.group(1) if m else ''


def _build_nearby_races(rd: dict, race_index: list) -> str:
    """Build 'More in [State]' contextual links for in-content SEO."""
    if not race_index:
        return ''
    location = rd['vitals'].get('location', '')
    state = _extract_state(location)
    if not state:
        return ''
    slug = rd['slug']
    # Find other races in same state, prefer higher-tier races
    nearby = []
    for r in race_index:
        if r.get('slug') == slug:
            continue
        r_loc = r.get('location', '')
        if _extract_state(r_loc) == state:
            nearby.append(r)
    if not nearby:
        return ''
    # Sort by score descending, take top 3
    nearby.sort(key=lambda r: r.get('overall_score', 0), reverse=True)
    links = []
    for r in nearby[:3]:
        links.append(f'<a href="/race/{esc(r["slug"])}/">{esc(r["name"])}</a>')
    return f'''<div class="gg-nearby-races">
        <span class="gg-nearby-label">MORE IN {esc(state.upper())}:</span> {" &middot; ".join(links)}
      </div>'''


def build_course_overview(rd: dict, race_index: list = None) -> str:
    """Build [01] Course Overview section — merged map + stat cards."""
    v = rd['vitals']

    # Map embed — prefer explicit ridewithgps_id, fall back to extracting from map_url
    map_html = ''
    rwgps_id = rd['course'].get('ridewithgps_id')
    if not rwgps_id:
        map_url = rd['course'].get('map_url', '') or ''
        m = re.search(r'ridewithgps\.com/routes/(\d+)', map_url)
        if m:
            rwgps_id = m.group(1)
    rwgps_name = rd['course'].get('ridewithgps_name', '')
    if rwgps_id:
        map_html = f'''<div class="gg-map-embed">
        <iframe src="https://ridewithgps.com/embeds?type=route&amp;id={esc(rwgps_id)}&amp;title={esc(rwgps_name)}" title="Course map for {esc(rd['name'])}" scrolling="no" allowfullscreen loading="lazy"></iframe>
      </div>'''

    # Stat cards — (value, label, countable) where countable means "animate the number"
    stats = [
        (v.get('distance', '--'), 'Distance', True),
        (v.get('elevation', '--'), 'Elevation', True),
        (v.get('location', '--'), 'Location', False),
        (v.get('date', '--'), 'Date', False),
        (v.get('field_size', '--'), 'Field Size', True),
    ]
    # Add entry cost if available
    if v.get('entry_cost'):
        stats.append((v['entry_cost'], 'Entry Cost', True))
    else:
        stats.append(('--', 'Entry Cost', False))

    cards = '\n      '.join(
        f'''<div class="gg-stat-card">
          <div class="gg-stat-value{' gg-stat-countable' if countable else ''}">{esc(val)}</div>
          <div class="gg-stat-label">{esc(label)}</div>
        </div>'''
        for val, label, countable in stats
    )

    # Difficulty gauge — based on course profile (technicality + elevation + climate + adventure)
    hard_dims = ['technicality', 'elevation', 'climate', 'adventure']
    hard_score = sum(rd['explanations'].get(d, {}).get('score', 0) for d in hard_dims)
    hard_pct = int((hard_score / 20) * 100)
    if hard_pct >= 80:
        hard_label, hard_color = 'BRUTAL', COLORS['near_black']
    elif hard_pct >= 60:
        hard_label, hard_color = 'HARD', COLORS['primary_brown']
    elif hard_pct >= 40:
        hard_label, hard_color = 'MODERATE', COLORS['gold']
    else:
        hard_label, hard_color = 'ACCESSIBLE', COLORS['teal']

    gauge_html = f'''<div class="gg-difficulty-gauge">
        <div class="gg-difficulty-header">
          <span class="gg-difficulty-title">DIFFICULTY</span>
          <span class="gg-difficulty-label">{hard_label}</span>
        </div>
        <div class="gg-difficulty-track">
          <div class="gg-difficulty-fill" data-width="{hard_pct}" style="width:0%;background:{hard_color}"></div>
        </div>
        <div class="gg-difficulty-scale">
          <span>ACCESSIBLE</span><span>MODERATE</span><span>HARD</span><span>BRUTAL</span>
        </div>
      </div>'''

    nearby_html = _build_nearby_races(rd, race_index or [])

    return f'''<section id="course" class="gg-section gg-fade-section">
    <div class="gg-section-header">
      <span class="gg-section-kicker">[01]</span>
      <h2 class="gg-section-title">Course Overview</h2>
    </div>
    <div class="gg-section-body">
      {map_html}
      <div class="gg-stat-grid">
      {cards}
      </div>
      {gauge_html}
      {nearby_html}
    </div>
  </section>'''


def build_history(rd: dict) -> str:
    """Build [02] Facts & History section."""
    h = rd['history']

    # Skip entirely if no meaningful content
    if not h.get('origin_story') and not h.get('notable_moments') and not h.get('reputation'):
        return ''

    body_parts = []

    # Origin story — suppress generic stub text (< 60 chars ending in "event." etc.)
    origin = h.get('origin_story', '').strip()
    is_stub_origin = len(origin) < 60 and origin.endswith(('event.', 'race.', 'community.'))
    if origin and not is_stub_origin:
        founded = f" Founded in {h['founded']}." if h.get('founded') else ''
        # Suppress generic "X organizers" founder text
        founder_text = h.get('founder', '')
        founder = f" By {founder_text}." if founder_text and founder_text != 'Unknown' and not founder_text.endswith('organizers') else ''
        body_parts.append(f'<div class="gg-prose"><p>{esc(origin)}{esc(founded)}{esc(founder)}</p></div>')

    # Reputation
    if h.get('reputation'):
        body_parts.append(f'<div class="gg-prose"><p><strong>Reputation:</strong> {esc(h["reputation"])}</p></div>')

    # Timeline
    moments = h.get('notable_moments', [])
    if moments:
        items = '\n        '.join(
            f'<div class="gg-timeline-item"><div class="gg-timeline-text">{esc(m)}</div></div>'
            for m in moments
        )
        body_parts.append(f'''<div class="gg-timeline">
        {items}
      </div>''')

    if not body_parts:
        return ''

    body = '\n      '.join(body_parts)

    return f'''<section id="history" class="gg-section gg-section--dark gg-fade-section">
    <div class="gg-section-header gg-section-header--teal">
      <span class="gg-section-kicker">[02]</span>
      <h2 class="gg-section-title">Facts &amp; History</h2>
    </div>
    <div class="gg-section-body">
      {body}
    </div>
  </section>'''


def build_course_route(rd: dict) -> str:
    """Build [03] The Course section — suffering zones."""
    c = rd['course']
    zones = c.get('suffering_zones', [])

    if not zones and not c.get('character') and not c.get('signature_challenge'):
        return ''

    body_parts = []

    if c.get('character'):
        body_parts.append(f'<div class="gg-prose"><p>{esc(c["character"])}</p></div>')

    if c.get('signature_challenge'):
        body_parts.append(f'<div class="gg-prose"><p><strong>Signature challenge:</strong> {esc(c["signature_challenge"])}</p></div>')

    if zones:
        zone_html = []
        for z in zones:
            zone_html.append(f'''<div class="gg-suffering-zone">
          <div class="gg-suffering-mile">
            <div class="gg-suffering-mile-num">{z.get("mile", "?")}</div>
            <div class="gg-suffering-mile-label">MILE</div>
          </div>
          <div class="gg-suffering-content">
            <div class="gg-suffering-name">{esc(z.get("label", z.get("named_section", "")))}</div>
            <div class="gg-suffering-desc">{esc(z.get("desc", ""))}</div>
          </div>
        </div>''')
        body_parts.append('\n      '.join(zone_html))

    body = '\n      '.join(body_parts)

    return f'''<section id="route" class="gg-section gg-section--accent gg-fade-section">
    <div class="gg-section-header">
      <span class="gg-section-kicker">[03]</span>
      <h2 class="gg-section-title">The Course</h2>
    </div>
    <div class="gg-section-body">
      {body}
    </div>
  </section>'''


def build_ratings(rd: dict) -> str:
    """Build [04] The Ratings section — merged course + editorial with accordions."""
    # Summary row
    summary = f'''<div class="gg-ratings-summary">
        <div class="gg-ratings-summary-card">
          <div class="gg-ratings-summary-score">{rd['course_profile']}<span class="gg-ratings-summary-max">/35</span></div>
          <div class="gg-ratings-summary-label">Course Profile</div>
        </div>
        <div class="gg-ratings-summary-card">
          <div class="gg-ratings-summary-score">{rd['opinion_total']}<span class="gg-ratings-summary-max">/35</span></div>
          <div class="gg-ratings-summary-label">Editorial</div>
        </div>
      </div>'''

    radar = build_radar_charts(rd['explanations'], rd['course_profile'], rd['opinion_total'])
    course_accordion = build_accordion_html(COURSE_DIMS, rd['explanations'], idx_offset=0)
    opinion_accordion = build_accordion_html(OPINION_DIMS, rd['explanations'], idx_offset=7)

    return f'''<section id="ratings" class="gg-section gg-section--teal-accent gg-fade-section">
    <div class="gg-section-header gg-section-header--dark">
      <span class="gg-section-kicker">[04]</span>
      <h2 class="gg-section-title">The Ratings</h2>
    </div>
    <div class="gg-section-body">
      {summary}
      {radar}
      <h3 class="gg-accordion-group-title">Course Profile</h3>
      {course_accordion}
      <h3 class="gg-accordion-group-title gg-mt-md">Editorial Assessment</h3>
      {opinion_accordion}
    </div>
  </section>'''


def build_verdict(rd: dict, race_index: list = None) -> str:
    """Build [05] Final Verdict section — Race This If / Skip This If."""
    bo = rd['biased_opinion']
    fv = rd['final_verdict']

    strengths = bo.get('strengths', [])
    weaknesses = bo.get('weaknesses', [])

    if not strengths and not weaknesses and not fv.get('should_you_race'):
        # Fallback: show summary if available
        if bo.get('summary'):
            return f'''<section id="verdict" class="gg-section gg-section--dark gg-fade-section">
    <div class="gg-section-header gg-section-header--gold">
      <span class="gg-section-kicker">[05]</span>
      <h2 class="gg-section-title">Final Verdict</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-prose"><p>{esc(bo["summary"])}</p></div>
    </div>
  </section>'''
        return ''

    # Build Race This If / Skip This If
    race_items = '\n          '.join(f'<li>{esc(s)}</li>' for s in strengths) if strengths else '<li>See the ratings above for details.</li>'
    skip_items = '\n          '.join(f'<li>{esc(w)}</li>' for w in weaknesses) if weaknesses else '<li>See the ratings above for details.</li>'

    verdict_grid = f'''<div class="gg-verdict-grid">
        <div class="gg-verdict-box gg-verdict-box--race">
          <div class="gg-verdict-box-title">Race This If</div>
          <ul class="gg-verdict-list">
          {race_items}
          </ul>
        </div>
        <div class="gg-verdict-box gg-verdict-box--skip">
          <div class="gg-verdict-box-title">Skip This If</div>
          <ul class="gg-verdict-list">
          {skip_items}
          </ul>
        </div>
      </div>'''

    bottom_line = ''
    bl_text = bo.get('bottom_line') or fv.get('should_you_race', '')
    if bl_text:
        bottom_line = f'''<div class="gg-verdict-bottom-line">
        <strong>Bottom Line:</strong> {esc(bl_text)}
      </div>'''

    # Alternatives with race links
    alt_html = ''
    if fv.get('alternatives'):
        linked = linkify_alternatives(fv['alternatives'], race_index or [])
        alt_html = f'''<div class="gg-prose gg-mt-md"><p><strong>Alternatives:</strong> {linked}</p></div>'''

    return f'''<section id="verdict" class="gg-section gg-section--dark gg-fade-section">
    <div class="gg-section-header gg-section-header--gold">
      <span class="gg-section-kicker">[05]</span>
      <h2 class="gg-section-title">Final Verdict</h2>
    </div>
    <div class="gg-section-body">
      {verdict_grid}
      {bottom_line}
      {alt_html}
    </div>
  </section>'''


def build_training(rd: dict, q_url: str) -> str:
    """Build [06] Training section — two distinct paths, countdown, clear differentiation."""
    race_name = rd['name']

    # Race date countdown — parsed from date_specific
    countdown_html = ''
    date_specific = rd['vitals'].get('date_specific', '')
    date_match = re.search(r'(\d{4}).*?(\w+)\s+(\d+)', date_specific)
    if date_match:
        year, month_name, day = date_match.groups()
        month_num = MONTH_NUMBERS.get(month_name.lower(), "01")
        iso_date = f"{year}-{month_num}-{int(day):02d}"
        # Show formatted date for no-JS/crawlers; JS replaces with day count
        display_date = f"{month_name} {int(day)}, {year}"
        countdown_html = f'<div class="gg-countdown" data-date="{iso_date}"><span class="gg-countdown-num" id="gg-days-left">{esc(display_date)}</span> {esc(race_name.upper())}</div>'

    return f'''<section id="training" class="gg-section gg-fade-section">
    <div class="gg-section-header">
      <span class="gg-section-kicker">[06]</span>
      <h2 class="gg-section-title">Training</h2>
    </div>
    <div class="gg-section-body">
      {countdown_html}
      <div class="gg-training-primary">
        <h3>Custom Training Plan</h3>
        <p class="gg-training-subtitle">Race-specific. Built for {esc(race_name)}. $15/week, capped at $199.</p>
        <ul class="gg-training-bullets">
          <li>Structured workouts pushed to your device</li>
          <li>30+ page custom training guide</li>
          <li>Heat &amp; altitude protocols</li>
          <li>Nutrition plan</li>
          <li>Strength training</li>
        </ul>
        <a href="{esc(TRAINING_PLANS_URL)}" class="gg-btn">BUILD MY PLAN &mdash; $15/WK</a>
      </div>
      <div class="gg-training-divider">
        <span class="gg-training-divider-line"></span>
        <span class="gg-training-divider-text">OR</span>
        <span class="gg-training-divider-line"></span>
      </div>
      <div class="gg-training-secondary">
        <div class="gg-training-secondary-text">
          <h4>1:1 Coaching</h4>
          <p class="gg-training-subtitle">A human in your corner. Adapts week to week.</p>
          <p>Your coach reviews every session, adjusts when life happens, and builds race-day strategy with you. Not a plan &mdash; a partnership.</p>
        </div>
        <a href="{esc(COACHING_URL)}" class="gg-btn" target="_blank" rel="noopener">APPLY</a>
      </div>
    </div>
  </section>'''


def build_logistics_section(rd: dict) -> str:
    """Build [07] Race Logistics section."""
    lg = rd['logistics']

    items_data = [
        ('Airport', lg.get('airport', '')),
        ('Lodging', lg.get('lodging_strategy', '')),
        ('Food', lg.get('food', '')),
        ('Packet Pickup', lg.get('packet_pickup', '')),
        ('Parking', lg.get('parking', '')),
    ]

    # Filter out empty items and placeholder text ("Check X website/calendars")
    items_data = [(label, val) for label, val in items_data
                  if val and not re.match(r'^Check\s', val, re.IGNORECASE)]

    if not items_data:
        return ''

    items = '\n      '.join(
        f'''<div class="gg-logistics-item">
          <div class="gg-logistics-item-label">{esc(label)}</div>
          <div class="gg-logistics-item-value">{esc(val)}</div>
        </div>'''
        for label, val in items_data
    )

    # Official site link
    official = lg.get('official_site', '')
    site_html = ''
    if official and official.startswith('http'):
        site_html = f'''<div class="gg-mt-md">
        <a href="{esc(official)}" class="gg-btn gg-btn--secondary" target="_blank" rel="noopener">OFFICIAL SITE</a>
      </div>'''

    return f'''<section id="logistics" class="gg-section gg-section--accent gg-fade-section">
    <div class="gg-section-header">
      <span class="gg-section-kicker">[07]</span>
      <h2 class="gg-section-title">Race Logistics</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-logistics-grid">
      {items}
      </div>
      {site_html}
    </div>
  </section>'''


def build_photos_section(rd: dict) -> str:
    """Build photo grid section using self-hosted AI-generated race photos.
    Returns empty string if no photos — no empty placeholder."""
    photos = rd.get('race_photos', [])
    if not photos:
        return ''

    photo_base = 'https://gravelgodcycling.com/photos'
    cards = []
    for p in photos:
        url = f"{photo_base}/{p['file']}"
        alt = esc(p.get('alt', 'Race course photo'))
        ptype = p.get('type', 'hero')
        h = 675 if ptype != 'grit' else 900
        cards.append(f'''<figure class="gg-photo-card">
          <img src="{esc(url)}" alt="{alt}" loading="lazy"
               width="1200" height="{h}">
        </figure>''')

    if not cards:
        return ''

    grid = '\n        '.join(cards)
    return f'''<section id="photos" class="gg-section gg-fade-section gg-section--accent">
    <div class="gg-section-header gg-section-header--dark">
      <span class="gg-section-kicker">[&mdash;]</span>
      <h2 class="gg-section-title">From the Field</h2>
    </div>
    <div class="gg-section-body gg-photos-body">
      <div class="gg-photos-grid">
        {grid}
      </div>
    </div>
  </section>'''


def build_news_section(rd: dict) -> str:
    """Build Latest News section — fetches Google News RSS via rss2json.com at runtime.
    Only renders for T1/T2 races (T3/T4 rarely have news, wastes API calls).
    Starts hidden to prevent layout shift — JS reveals it if headlines load."""
    tier = rd.get('tier', 4)
    if tier > 2:
        return ''
    name = rd['name']
    search_query = name.replace(' ', '+')

    return f'''<div class="gg-news-ticker gg-fade-section" id="gg-news-ticker" role="region" aria-label="Latest news" data-query="{esc(search_query)}" style="display:none">
    <div class="gg-news-ticker-label" aria-hidden="true">LATEST NEWS</div>
    <div class="gg-news-ticker-track">
      <div class="gg-news-ticker-content" id="gg-news-feed" aria-live="polite" aria-atomic="true"></div>
    </div>
  </div>'''


def build_pullquote(rd: dict) -> str:
    """Build a pull-quote block from the biased opinion summary.
    Uses summary (not bottom_line) to avoid duplicating the verdict section."""
    bo = rd['biased_opinion']
    fv = rd['final_verdict']
    # Use summary first; only use bottom_line if summary is empty AND bottom_line
    # differs from what the verdict section will show
    text = bo.get('summary', '').strip()
    if not text:
        bl = bo.get('bottom_line', '').strip()
        should_race = fv.get('should_you_race', '').strip()
        # Only use bottom_line for pullquote if it won't be shown in verdict
        if bl and bl != should_race:
            text = bl
    if not text:
        return ''

    return f'''<div class="gg-pullquote gg-fade-section">
    <blockquote class="gg-pullquote-text">&ldquo;{esc(text)}&rdquo;</blockquote>
  </div>'''


def _build_race_name_map(race_index: list) -> dict:
    """Build name → slug mapping from the full race index for linkification."""
    name_map = {}
    for r in race_index:
        slug = r.get('slug', '')
        name = r.get('name', '')
        if name and slug:
            name_map[name] = slug
    return name_map


def linkify_alternatives(alt_text: str, race_index: list) -> str:
    """Parse race names from alternatives text and link to profile pages.
    Builds name→slug mapping from the full race index (328 races)."""
    if not alt_text:
        return ''

    # Build mapping from index; include common aliases as fallback
    name_map = _build_race_name_map(race_index) if race_index else {}
    # Add well-known aliases that differ from display names
    aliases = {
        'Unbound': 'unbound-200',
        'Unbound Gravel': 'unbound-200',
        'BWR': 'bwr-california',
        'Belgian Waffle Ride': 'bwr-california',
        'Big Sugar': 'big-sugar',
        'Land Run': 'mid-south',
        'Leadville': 'leadville-trail-100-mtb',
    }
    for alias, slug in aliases.items():
        if alias not in name_map:
            name_map[alias] = slug

    result = esc(alt_text)
    # Sort by length descending to match longer names first
    for name, slug in sorted(name_map.items(), key=lambda x: len(x[0]), reverse=True):
        escaped_name = esc(name)
        if escaped_name in result:
            link = f'<a href="/race/{slug}/" class="gg-alt-link">{escaped_name}</a>'
            result = result.replace(escaped_name, link, 1)

    return result


def build_email_capture(rd: dict) -> str:
    """Build email capture section — Substack iframe embed for native subscribe flow."""
    return f'''<div class="gg-email-capture gg-fade-section">
    <div class="gg-email-capture-inner">
      <h3 class="gg-email-capture-title">SLOW, MID, 38s</h3>
      <p class="gg-email-capture-text">For cyclists with more passion than talent. Commentary on cycling training, culture and life. Free. No spam.</p>
      <iframe src="{esc(SUBSTACK_EMBED)}" title="Newsletter signup" width="100%" height="100" style="border:none; background:transparent;" frameborder="0" scrolling="no" loading="lazy"></iframe>
    </div>
  </div>'''


def build_visible_faq(rd: dict) -> str:
    """Build visible FAQ section for long-tail SEO. Uses same data as FAQ schema
    but renders as on-page content with H3 headings for search engines."""
    explanations = rd.get('explanations', {})
    name = rd['name']
    fv = rd['final_verdict']

    questions = []
    # Top FAQ dimensions
    for dim in FAQ_PRIORITY:
        if len(questions) >= 4:
            break
        entry = explanations.get(dim, {})
        expl = entry.get('explanation', '').strip()
        if not expl:
            continue
        q_template = FAQ_TEMPLATES.get(dim, f'What about {dim} at {{name}}?')
        questions.append((q_template.format(name=name), expl))

    # Verdict question
    should_race = fv.get('should_you_race', '').strip()
    if should_race:
        questions.append((f"Should I race {name}?", should_race))

    if not questions:
        return ''

    items = []
    for q, a in questions:
        items.append(f'''<div class="gg-faq-item">
        <div class="gg-faq-question" role="button" tabindex="0" aria-expanded="false">
          <h3>{esc(q)}</h3>
          <span class="gg-faq-toggle" aria-hidden="true">+</span>
        </div>
        <div class="gg-faq-answer"><p>{esc(a)}</p></div>
      </div>''')

    return f'''<section id="faq" class="gg-section gg-fade-section">
    <div class="gg-section-header">
      <span class="gg-section-kicker">[&mdash;]</span>
      <h2 class="gg-section-title">Frequently Asked Questions</h2>
    </div>
    <div class="gg-section-body">
      {''.join(items)}
    </div>
  </section>'''


def build_similar_races(rd: dict, race_index: list) -> str:
    """Build Similar Races section from the race index.
    Finds 4 races in same region or adjacent tier, excluding self."""
    if not race_index:
        return ''

    slug = rd['slug']
    tier = rd.get('tier', 4)
    score = rd.get('overall_score', 0)
    # Derive region from location
    location = rd['vitals'].get('location', '')

    # Find region by matching this slug in the index
    my_region = ''
    for r in race_index:
        if r.get('slug') == slug:
            my_region = r.get('region', '')
            break

    my_distance = rd['vitals'].get('distance_mi') or 0
    if isinstance(my_distance, str):
        try:
            my_distance = float(re.sub(r'[^\d.]', '', str(my_distance)))
        except (ValueError, TypeError):
            my_distance = 0

    candidates = []
    for r in race_index:
        if r.get('slug') == slug:
            continue
        r_region = r.get('region', '')
        r_tier = r.get('tier', 4)
        r_score = r.get('overall_score', 0)
        r_dist = r.get('distance_mi', 0) or 0
        # Score: same region = 10, same tier = 5, adjacent tier = 2, score + distance proximity
        relevance = 0
        if my_region and r_region == my_region:
            relevance += 10
        if r_tier == tier:
            relevance += 5
        elif abs(r_tier - tier) == 1:
            relevance += 2
        relevance += max(0, 10 - abs(r_score - score) / 5)
        # Distance similarity bonus (up to 5 points)
        if my_distance > 0 and r_dist > 0:
            dist_ratio = min(my_distance, r_dist) / max(my_distance, r_dist)
            relevance += dist_ratio * 5
        candidates.append((relevance, r))

    # Sort by relevance descending, take top 6
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = [c[1] for c in candidates[:6]]

    if not top:
        return ''

    cards = []
    for r in top:
        tier_num = r.get('tier', 4)
        dist = r.get('distance_mi', '')
        dist_str = f" &middot; {dist} mi" if dist else ''
        cards.append(f'''<a href="/race/{esc(r['slug'])}/" class="gg-similar-card">
        <span class="gg-similar-tier">T{tier_num}</span>
        <span class="gg-similar-name">{esc(r['name'])}</span>
        <span class="gg-similar-meta">{esc(r.get('location', ''))}{dist_str} &middot; {r.get('overall_score', 0)}/100</span>
      </a>''')

    return f'''<section class="gg-section gg-fade-section">
    <div class="gg-section-header gg-section-header--dark">
      <span class="gg-section-kicker">[&mdash;]</span>
      <h2 class="gg-section-title">Similar Races</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-similar-grid">
        {''.join(cards)}
      </div>
    </div>
  </section>'''


def build_citations_section(rd: dict) -> str:
    """Build Sources & Citations section from race.citations data."""
    citations = rd.get('citations', [])
    if not citations:
        return ''

    # Group by category
    categories = {}
    for c in citations:
        cat = c.get('category', 'other')
        categories.setdefault(cat, []).append(c)

    # Category display order and labels
    cat_order = [
        ('official', 'Official'),
        ('route', 'Route Maps'),
        ('media', 'Media & Press'),
        ('community', 'Community'),
        ('video', 'Video'),
        ('registration', 'Registration'),
        ('social', 'Social'),
        ('tracking', 'Live Tracking'),
        ('reference', 'Reference'),
        ('activity', 'Activity'),
        ('other', 'Other Sources'),
    ]

    items = []
    for cat_key, cat_label in cat_order:
        if cat_key not in categories:
            continue
        for c in categories[cat_key]:
            url = c.get('url', '')
            label = c.get('label', 'Source')
            # Truncate long URLs for display
            display_url = url.replace('https://', '').replace('http://', '')
            if len(display_url) > 60:
                display_url = display_url[:57] + '...'
            items.append(
                f'<li class="gg-citation-item">'
                f'<span class="gg-citation-cat">{esc(cat_label)}</span> '
                f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer" '
                f'class="gg-citation-link">{esc(label)}</a>'
                f'<span class="gg-citation-url">{esc(display_url)}</span>'
                f'</li>'
            )

    if not items:
        return ''

    return f'''<section class="gg-section gg-fade-section" id="citations">
    <div class="gg-section-header gg-section-header--dark">
      <span class="gg-section-kicker">[&mdash;]</span>
      <h2 class="gg-section-title">Sources &amp; Citations</h2>
    </div>
    <div class="gg-section-body">
      <p class="gg-citations-intro">Research sources used to build this race profile. Always verify details with official race sources before making travel or registration decisions.</p>
      <ol class="gg-citations-list">
        {''.join(items)}
      </ol>
    </div>
  </section>'''


def build_breadcrumb_jsonld(rd: dict, race_index: list) -> dict:
    """Build BreadcrumbList JSON-LD schema."""
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home",
             "item": SITE_BASE_URL},
            {"@type": "ListItem", "position": 2, "name": "Gravel Races",
             "item": f"{SITE_BASE_URL}/gravel-races/"},
            {"@type": "ListItem", "position": 3, "name": rd['tier_label'],
             "item": f"{SITE_BASE_URL}/race/tier-{rd['tier']}/"},
            {"@type": "ListItem", "position": 4, "name": rd['name'],
             "item": f"{SITE_BASE_URL}/race/{rd['slug']}/"},
        ]
    }


def build_webpage_jsonld(rd: dict) -> dict:
    """Build WebPage JSON-LD with speakable targeting key content sections."""
    canonical_url = f"{SITE_BASE_URL}/race/{rd['slug']}/"
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": build_seo_title(rd),
        "url": canonical_url,
        "dateModified": rd.get('_file_mtime', date.today().isoformat()),
        "isPartOf": {
            "@type": "WebSite",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "speakable": {
            "@type": "SpeakableSpecification",
            "cssSelector": [
                ".gg-hero-tagline",
                ".gg-verdict-text",
                ".gg-faq-answer",
            ],
        },
    }


def build_nav_header(rd: dict, race_index: list) -> str:
    """Build visible navigation header with breadcrumb trail."""
    return f'''<nav class="gg-site-nav">
    <div class="gg-site-nav-inner">
      <a href="{SITE_BASE_URL}/" class="gg-site-nav-brand">GRAVEL GOD</a>
      <a href="{SITE_BASE_URL}/gravel-races/" class="gg-site-nav-link">ALL RACES</a>
      <a href="{SITE_BASE_URL}/race/methodology/" class="gg-site-nav-link">HOW WE RATE</a>
    </div>
    <div class="gg-breadcrumb">
      <a href="{SITE_BASE_URL}/">Home</a>
      <span class="gg-breadcrumb-sep">&rsaquo;</span>
      <a href="{SITE_BASE_URL}/gravel-races/">Gravel Races</a>
      <span class="gg-breadcrumb-sep">&rsaquo;</span>
      <a href="{SITE_BASE_URL}/race/tier-{rd['tier']}/">{esc(rd['tier_label'])}</a>
      <span class="gg-breadcrumb-sep">&rsaquo;</span>
      <span class="gg-breadcrumb-current">{esc(rd['name'])}</span>
    </div>
  </nav>'''


def build_footer(rd: dict = None) -> str:
    """Build page footer with nav links and disclaimer."""
    updated = ''
    if rd and rd.get('_file_mtime'):
        try:
            dt = datetime.strptime(rd['_file_mtime'], '%Y-%m-%d')
            updated = f'\n    <p class="gg-footer-updated">Last updated {dt.strftime("%B %Y")}</p>'
        except ValueError:
            pass
    return f'''<div class="gg-footer">
    <nav class="gg-footer-nav">
      <a href="{SITE_BASE_URL}/gravel-races/">All Races</a>
      <a href="{SITE_BASE_URL}/race/methodology/">How We Rate</a>
      <a href="{SUBSTACK_URL}" target="_blank" rel="noopener">Newsletter</a>
    </nav>{updated}
    <p class="gg-footer-disclaimer">This content is produced independently by Gravel God and is not affiliated with, endorsed by, or officially connected to any race organizer, event, or governing body mentioned on this page. All ratings, opinions, and assessments represent the editorial views of Gravel God based on publicly available information and community research. Race details are subject to change &mdash; always verify with official race sources.</p>
  </div>'''


# ── CSS ────────────────────────────────────────────────────────

def get_page_css() -> str:
    """Return the full page CSS with brand tokens, self-hosted fonts, and editorial typography."""
    tokens = get_tokens_css()
    fonts = get_font_face_css("/race/assets/fonts")
    return f'''<style>
{fonts}

{tokens}

/* Skip link */
.gg-skip-link {{ position: absolute; top: -100px; left: 16px; background: var(--gg-color-gold); color: var(--gg-color-dark-brown); padding: 8px 16px; font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; text-decoration: none; z-index: 999; border: var(--gg-border-standard); }}
.gg-skip-link:focus {{ top: 8px; outline: 3px solid var(--gg-color-near-black); outline-offset: 2px; }}

/* Focus indicators */
.gg-neo-brutalist-page a:focus-visible, .gg-neo-brutalist-page button:focus-visible, .gg-neo-brutalist-page [role="button"]:focus-visible, .gg-neo-brutalist-page .gg-btn:focus-visible {{ outline: 3px solid var(--gg-color-gold); outline-offset: 2px; }}
.gg-neo-brutalist-page .gg-faq-question:focus-visible {{ outline: 3px solid var(--gg-color-gold); outline-offset: -3px; }}

/* Utility */
.gg-mt-md {{ margin-top: var(--gg-spacing-md); }}

/* Page wrapper */
.gg-neo-brutalist-page {{
  max-width: 960px;
  margin: 0 auto;
  padding: 0 20px;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
  line-height: 1.6;
  background: var(--gg-color-sand);
}}
.gg-neo-brutalist-page *, .gg-neo-brutalist-page *::before, .gg-neo-brutalist-page *::after {{
  border-radius: 0 !important;
  box-shadow: none !important;
  box-sizing: border-box;
}}

/* Hero */
.gg-neo-brutalist-page .gg-hero {{ background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); padding: var(--gg-spacing-3xl) var(--gg-spacing-2xl); border-bottom: var(--gg-border-double); margin-bottom: 0; position: relative; overflow: hidden; }}
.gg-neo-brutalist-page .gg-hero-tier {{ display: inline-block; background: var(--gg-color-gold); color: var(--gg-color-dark-brown); padding: var(--gg-spacing-2xs) var(--gg-spacing-sm); font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-ultra-wide); text-transform: uppercase; margin-bottom: var(--gg-spacing-md); }}
.gg-neo-brutalist-page .gg-hero h1 {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-4xl); font-weight: var(--gg-font-weight-bold); line-height: var(--gg-line-height-tight); letter-spacing: var(--gg-letter-spacing-tight); margin-bottom: 16px; color: var(--gg-color-white); position: relative; }}
.gg-neo-brutalist-page .gg-hero h1::after {{ content: attr(data-text); position: absolute; left: 3px; top: 3px; color: var(--gg-color-teal); opacity: 0.3; z-index: 0; pointer-events: none; }}
.gg-neo-brutalist-page .gg-hero-tagline {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-base); line-height: var(--gg-line-height-relaxed); color: var(--gg-color-tan); max-width: 700px; }}
.gg-neo-brutalist-page .gg-btn--hero-site {{ display: inline-block; margin-top: 16px; background: transparent; color: var(--gg-color-warm-paper); border: 2px solid var(--gg-color-warm-paper); padding: 8px 20px; font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; text-decoration: none; }}
.gg-neo-brutalist-page .gg-btn--hero-site:hover {{ background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-hero-score {{ position: absolute; top: 40px; right: 40px; text-align: center; }}
.gg-neo-brutalist-page .gg-hero-score-number {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-5xl); font-weight: var(--gg-font-weight-bold); line-height: 1; color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-hero-score-label {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: var(--gg-color-warm-brown); }}

/* TOC */
.gg-neo-brutalist-page .gg-toc {{ background: var(--gg-color-near-black); padding: 16px 20px; border: var(--gg-border-standard); border-top: none; display: flex; flex-wrap: wrap; gap: 8px 20px; margin-bottom: 32px; }}
.gg-neo-brutalist-page .gg-toc a {{ color: var(--gg-color-tan); text-decoration: none; font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; transition: color 0.2s; }}
.gg-neo-brutalist-page .gg-toc a:hover {{ color: var(--gg-color-white); }}

/* Section common */
.gg-neo-brutalist-page .gg-section {{ margin-bottom: 32px; border: var(--gg-border-standard); background: var(--gg-color-warm-paper); }}
.gg-neo-brutalist-page .gg-section-header {{ background: var(--gg-color-primary-brown); color: var(--gg-color-warm-paper); padding: 14px 20px; display: flex; align-items: center; gap: 12px; border-bottom: var(--gg-border-double); }}
.gg-neo-brutalist-page .gg-section-kicker {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: 700; letter-spacing: var(--gg-letter-spacing-ultra-wide); text-transform: uppercase; color: var(--gg-color-gold); white-space: nowrap; }}
.gg-neo-brutalist-page .gg-section-title {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); font-weight: var(--gg-font-weight-semibold); letter-spacing: var(--gg-letter-spacing-normal); color: var(--gg-color-white); margin: 0; }}
.gg-neo-brutalist-page .gg-section-body {{ padding: 24px 20px; }}

/* Section header variant: dark */
.gg-neo-brutalist-page .gg-section-header--dark {{ background: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-section-header--dark .gg-section-kicker {{ color: var(--gg-color-gold); }}

/* Section variant: accent (subtle warm bg) */
.gg-neo-brutalist-page .gg-section--accent {{ background: var(--gg-color-sand); }}

/* Section variant: dark (near-black bg, light text) */
.gg-neo-brutalist-page .gg-section--dark {{ background: var(--gg-color-near-black); }}
.gg-neo-brutalist-page .gg-section--dark .gg-section-body {{ color: var(--gg-color-tan); }}
.gg-neo-brutalist-page .gg-section--dark .gg-prose {{ color: var(--gg-color-tan); }}
.gg-neo-brutalist-page .gg-section--dark .gg-prose p {{ color: var(--gg-color-tan); }}
.gg-neo-brutalist-page .gg-section--dark .gg-prose strong {{ color: var(--gg-color-white); }}
.gg-neo-brutalist-page .gg-section--dark .gg-timeline {{ border-left-color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-section--dark .gg-timeline-text {{ color: var(--gg-color-tan); }}
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-grid {{ gap: 16px; }}
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-box--race {{ background: var(--gg-color-near-black); border-color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-box--skip {{ background: var(--gg-color-near-black); border-color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-box-title {{ color: var(--gg-color-white); }}
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-list li {{ color: var(--gg-color-tan); }}
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-bottom-line {{ background: var(--gg-color-near-black); border-color: var(--gg-color-dark-brown); color: var(--gg-color-tan); }}
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-bottom-line strong {{ color: var(--gg-color-gold); }}

/* Section variant: teal accent (teal top border) */
.gg-neo-brutalist-page .gg-section--teal-accent {{ border-top: var(--gg-border-width-heavy) solid var(--gg-color-teal); }}

/* Section header variant: teal */
.gg-neo-brutalist-page .gg-section-header--teal {{ background: var(--gg-color-teal); }}
.gg-neo-brutalist-page .gg-section-header--teal .gg-section-kicker {{ color: rgba(255,255,255,0.6); }}

/* Section header variant: gold */
.gg-neo-brutalist-page .gg-section-header--gold {{ background: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-section-header--gold .gg-section-kicker {{ color: rgba(255,255,255,0.6); }}

/* Stat cards */
.gg-neo-brutalist-page .gg-stat-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.gg-neo-brutalist-page .gg-stat-card {{ border: var(--gg-border-standard); padding: var(--gg-spacing-md); text-align: center; background: var(--gg-color-dark-brown); transition: border-color var(--gg-transition-hover); }}
.gg-neo-brutalist-page .gg-stat-card:hover {{ border-color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-stat-value {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xl); font-weight: var(--gg-font-weight-bold); color: var(--gg-color-warm-paper); line-height: var(--gg-line-height-tight); }}
.gg-neo-brutalist-page .gg-stat-label {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: var(--gg-color-gold); margin-top: var(--gg-spacing-2xs); }}

/* Difficulty gauge */
.gg-neo-brutalist-page .gg-difficulty-gauge {{ margin-top: 20px; border: var(--gg-border-standard); padding: 16px; background: var(--gg-color-warm-paper); }}
.gg-neo-brutalist-page .gg-difficulty-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
.gg-neo-brutalist-page .gg-difficulty-title {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); color: var(--gg-color-secondary-brown); }}
.gg-neo-brutalist-page .gg-difficulty-label {{ font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-difficulty-track {{ height: 12px; background: var(--gg-color-sand); border: 1px solid var(--gg-color-dark-brown); position: relative; overflow: hidden; }}
.gg-neo-brutalist-page .gg-difficulty-fill {{ height: 100%; transition: width 1.5s cubic-bezier(0.22,1,0.36,1); }}
.gg-neo-brutalist-page .gg-difficulty-scale {{ display: flex; justify-content: space-between; margin-top: 6px; font-family: var(--gg-font-data); font-size: 8px; font-weight: 700; letter-spacing: 1px; color: var(--gg-color-warm-brown); text-transform: uppercase; }}

/* Nearby races — in-content cross-links */
.gg-neo-brutalist-page .gg-nearby-races {{ margin-top: 16px; padding: 10px 16px; background: var(--gg-color-dark-brown); font-family: var(--gg-font-data); font-size: 11px; }}
.gg-neo-brutalist-page .gg-nearby-label {{ font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-nearby-races a {{ color: var(--gg-color-tan); text-decoration: none; }}
.gg-neo-brutalist-page .gg-nearby-races a:hover {{ color: var(--gg-color-white); text-decoration: underline; }}

/* Map embed */
.gg-neo-brutalist-page .gg-map-embed {{ border: var(--gg-border-subtle); margin-bottom: 16px; overflow: hidden; }}
.gg-neo-brutalist-page .gg-map-embed iframe {{ width: 100%; height: 400px; border: none; display: block; }}

/* Prose — editorial font */
.gg-neo-brutalist-page .gg-prose {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-base); line-height: var(--gg-line-height-prose); color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-prose p {{ margin-bottom: 14px; }}
.gg-neo-brutalist-page .gg-prose p:last-child {{ margin-bottom: 0; }}

/* Timeline */
.gg-neo-brutalist-page .gg-timeline {{ border-left: var(--gg-border-standard); border-left-color: var(--gg-color-gold); margin: 16px 0 0 12px; padding-left: 20px; }}
.gg-neo-brutalist-page .gg-timeline-item {{ position: relative; margin-bottom: 16px; padding-bottom: 4px; opacity: 0; transform: translateY(10px); transition: opacity 0.4s, transform 0.4s; }}
.gg-neo-brutalist-page .gg-timeline-item.is-visible {{ opacity: 1; transform: translateY(0); }}
.gg-neo-brutalist-page .gg-timeline-item::before {{ content: ''; position: absolute; left: -27px; top: 6px; width: 10px; height: 10px; background: var(--gg-color-gold); border: 2px solid var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-timeline-text {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); color: var(--gg-color-dark-brown); line-height: 1.5; }}

/* Suffering zones */
.gg-neo-brutalist-page .gg-suffering-zone {{ border: var(--gg-border-subtle); margin-bottom: 12px; display: flex; background: var(--gg-color-warm-paper); opacity: 0; transform: translateX(-30px); transition: opacity 0.5s, transform 0.5s; }}
.gg-neo-brutalist-page .gg-suffering-zone.is-visible {{ opacity: 1; transform: translateX(0); }}
.gg-neo-brutalist-page .gg-suffering-mile {{ background: var(--gg-color-teal); color: var(--gg-color-white); min-width: 80px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 12px; border-right: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-suffering-mile-num {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-xl); font-weight: 700; }}
.gg-neo-brutalist-page .gg-suffering-mile-label {{ font-family: var(--gg-font-data); font-size: 9px; letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: rgba(255,255,255,0.7); }}
.gg-neo-brutalist-page .gg-suffering-content {{ padding: 12px 16px; flex: 1; }}
.gg-neo-brutalist-page .gg-suffering-name {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }}
.gg-neo-brutalist-page .gg-suffering-desc {{ font-family: var(--gg-font-editorial); font-size: 12px; color: var(--gg-color-secondary-brown); line-height: 1.5; }}

/* Accordion */
.gg-neo-brutalist-page .gg-accordion {{ border-top: var(--gg-border-standard); }}
.gg-neo-brutalist-page .gg-accordion-group-title {{ font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: var(--gg-letter-spacing-wider); color: var(--gg-color-secondary-brown); padding: var(--gg-spacing-md) 0 var(--gg-spacing-xs) 0; }}
.gg-neo-brutalist-page .gg-accordion-item {{ border-bottom: 2px solid var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-accordion-trigger {{ display: flex; align-items: center; width: 100%; padding: 10px 0; cursor: pointer; background: none; border: none; font-family: var(--gg-font-data); font-size: 12px; text-align: left; gap: 8px; }}
.gg-neo-brutalist-page .gg-accordion-trigger:hover {{ background: var(--gg-color-warm-paper); }}
.gg-neo-brutalist-page .gg-accordion-label {{ font-family: var(--gg-font-data); width: 110px; min-width: 110px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-size: 11px; color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-accordion-bar-track {{ flex: 1; height: 8px; background: var(--gg-color-sand); position: relative; border: 1px solid var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-accordion-bar-fill {{ height: 100%; transition: width 0.3s; }}
.gg-neo-brutalist-page .gg-accordion-score {{ font-family: var(--gg-font-editorial); width: 40px; min-width: 40px; text-align: center; font-weight: var(--gg-font-weight-bold); font-size: var(--gg-font-size-sm); color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-accordion-arrow {{ width: 20px; min-width: 20px; text-align: center; font-size: var(--gg-font-size-2xs); color: var(--gg-color-warm-brown); transition: transform 0.2s; }}
.gg-neo-brutalist-page .gg-accordion-item.is-open .gg-accordion-arrow {{ transform: rotate(90deg); color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-accordion-panel {{ max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out; }}
.gg-neo-brutalist-page .gg-accordion-item.is-open .gg-accordion-panel {{ max-height: 500px; }}
.gg-neo-brutalist-page .gg-accordion-content {{ font-family: var(--gg-font-editorial); padding: 0 0 14px 122px; font-size: var(--gg-font-size-sm); line-height: var(--gg-line-height-relaxed); color: var(--gg-color-primary-brown); }}

/* Radar charts */
.gg-neo-brutalist-page .gg-radar-pair {{ display: flex; gap: 16px; margin-bottom: 24px; }}
.gg-neo-brutalist-page .gg-radar-chart {{ flex: 1; border: var(--gg-border-subtle); background: var(--gg-color-warm-paper); padding: 12px 8px 12px; text-align: center; }}
.gg-neo-brutalist-page .gg-radar-svg {{ width: 100%; height: auto; display: block; margin: 0 auto; }}
.gg-neo-brutalist-page .gg-radar-label {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: 700; text-transform: uppercase; letter-spacing: var(--gg-letter-spacing-wider); color: var(--gg-color-secondary-brown); margin-top: var(--gg-spacing-2xs); }}
.gg-neo-brutalist-page .gg-radar-chart.is-drawn .gg-radar-polygon {{ stroke-dashoffset: 0 !important; fill-opacity: 0.2; transition: stroke-dashoffset 1.2s ease-out, fill-opacity 0.8s ease-out 0.6s; }}
.gg-neo-brutalist-page .gg-radar-chart.is-drawn .gg-radar-dot {{ opacity: 1; transition: opacity 0.3s ease-out; }}
.gg-neo-brutalist-page .gg-radar-hit:hover ~ .gg-radar-ring {{ opacity: 0; }}
.gg-neo-brutalist-page .gg-radar-chart .gg-radar-ring {{ transition: opacity 0.2s; }}

/* Verdict box hover */
.gg-neo-brutalist-page .gg-verdict-box {{ transition: border-color var(--gg-transition-hover); }}
.gg-neo-brutalist-page .gg-verdict-box:hover {{ border-color: var(--gg-color-gold); }}

/* Accordion item hover highlight */
.gg-neo-brutalist-page .gg-accordion-item {{ transition: background 0.15s; }}
.gg-neo-brutalist-page .gg-accordion-item.is-highlighted {{ background: var(--gg-color-sand); }}

/* Ratings summary */
.gg-neo-brutalist-page .gg-ratings-summary {{ display: flex; gap: 16px; margin-bottom: 20px; }}
.gg-neo-brutalist-page .gg-ratings-summary-card {{ flex: 1; border: var(--gg-border-subtle); padding: 16px; text-align: center; background: var(--gg-color-warm-paper); }}
.gg-neo-brutalist-page .gg-ratings-summary-card:first-child {{ border-left: 4px solid var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-ratings-summary-card:last-child {{ border-left: 4px solid var(--gg-color-teal); }}
.gg-neo-brutalist-page .gg-ratings-summary-score {{ font-family: var(--gg-font-data); font-size: 32px; font-weight: 700; color: var(--gg-color-primary-brown); line-height: 1; }}
.gg-neo-brutalist-page .gg-ratings-summary-max {{ font-size: 14px; color: var(--gg-color-tier-3); }}
.gg-neo-brutalist-page .gg-ratings-summary-label {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: var(--gg-color-secondary-brown); margin-top: var(--gg-spacing-2xs); }}

/* Verdict */
.gg-neo-brutalist-page .gg-verdict-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.gg-neo-brutalist-page .gg-verdict-box {{ border: var(--gg-border-standard); padding: var(--gg-spacing-md); }}
.gg-neo-brutalist-page .gg-verdict-box-title {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-base); font-weight: var(--gg-font-weight-semibold); margin-bottom: var(--gg-spacing-sm); color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-verdict-box--race {{ background: var(--gg-color-sand); border-left: 4px solid var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-verdict-box--race .gg-verdict-box-title {{ color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-verdict-box--skip {{ background: var(--gg-color-warm-paper); border-left: 4px solid var(--gg-color-warm-brown); }}
.gg-neo-brutalist-page .gg-verdict-list {{ list-style: none; padding: 0; }}
.gg-neo-brutalist-page .gg-verdict-list li {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); line-height: var(--gg-line-height-relaxed); color: var(--gg-color-dark-brown); padding: 6px 0; padding-left: 24px; position: relative; }}
.gg-neo-brutalist-page .gg-verdict-list li::before {{ content: '\\2014'; position: absolute; left: 0; top: 6px; color: var(--gg-color-warm-brown); font-weight: var(--gg-font-weight-regular); }}
.gg-neo-brutalist-page .gg-verdict-box--race .gg-verdict-list li::before {{ color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-verdict-bottom-line {{ margin-top: var(--gg-spacing-md); padding: var(--gg-spacing-md); border: var(--gg-border-standard); border-top: var(--gg-border-double); background: var(--gg-color-warm-paper); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); line-height: var(--gg-line-height-relaxed); color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-verdict-bottom-line strong {{ color: var(--gg-color-gold); }}

/* Pull quote — Desert Editorial: centered, tan bg, double-rule, curly quotes */
.gg-neo-brutalist-page .gg-pullquote {{ margin: var(--gg-spacing-xl) 0; padding: var(--gg-spacing-2xl); background: var(--gg-color-tan); border-top: var(--gg-border-double); border-bottom: var(--gg-border-double); text-align: center; position: relative; }}
.gg-neo-brutalist-page .gg-pullquote-text {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); font-weight: var(--gg-font-weight-regular); font-style: italic; line-height: var(--gg-line-height-relaxed); color: var(--gg-color-dark-brown); margin: 0 0 var(--gg-spacing-sm) 0; position: relative; }}
.gg-neo-brutalist-page .gg-pullquote-text::before {{ content: '\\201c'; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-4xl); font-style: normal; color: var(--gg-color-gold); position: absolute; top: -10px; left: -20px; line-height: 1; }}
.gg-neo-brutalist-page .gg-pullquote-text::after {{ content: '\\201d'; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-4xl); font-style: normal; color: var(--gg-color-gold); position: relative; top: 10px; margin-left: 4px; line-height: 1; }}
.gg-neo-brutalist-page .gg-pullquote-attr {{ font-family: var(--gg-font-data); font-size: 11px; color: var(--gg-color-secondary-brown); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; font-style: normal; }}

/* Alternative links */
.gg-neo-brutalist-page .gg-alt-link {{ color: var(--gg-color-teal); text-decoration: underline; text-underline-offset: 2px; }}
.gg-neo-brutalist-page .gg-alt-link:hover {{ color: #14695F; }}

/* Buttons */
.gg-neo-brutalist-page .gg-btn {{ display: inline-block; padding: 10px 24px; font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); font-weight: 700; text-transform: uppercase; letter-spacing: var(--gg-letter-spacing-wider); text-decoration: none; cursor: pointer; border: var(--gg-border-standard); transition: background 0.15s, color 0.15s; }}
.gg-neo-brutalist-page .gg-btn--primary {{ background: var(--gg-color-gold); color: var(--gg-color-dark-brown); }}
.gg-neo-brutalist-page .gg-btn--primary:hover {{ background: var(--gg-color-light-gold); }}
.gg-neo-brutalist-page .gg-btn--secondary {{ background: var(--gg-color-teal); color: var(--gg-color-white); }}
.gg-neo-brutalist-page .gg-btn--secondary:hover {{ background: var(--gg-color-light-teal); }}

/* Training */
.gg-neo-brutalist-page .gg-training-primary {{ border: var(--gg-border-standard); background: var(--gg-color-primary-brown); color: var(--gg-color-white); padding: 32px; margin-bottom: 16px; }}
.gg-neo-brutalist-page .gg-training-primary h3 {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); font-weight: 700; text-transform: uppercase; letter-spacing: var(--gg-letter-spacing-wider); margin-bottom: 6px; color: var(--gg-color-white); }}
.gg-neo-brutalist-page .gg-training-primary .gg-training-subtitle {{ font-family: var(--gg-font-editorial); font-size: 12px; color: var(--gg-color-tan); margin-bottom: 20px; }}
.gg-neo-brutalist-page .gg-training-bullets {{ list-style: none; padding: 0; margin-bottom: 24px; }}
.gg-neo-brutalist-page .gg-training-bullets li {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); line-height: var(--gg-line-height-relaxed); color: var(--gg-color-tan); padding: 6px 0; padding-left: 20px; position: relative; }}
.gg-neo-brutalist-page .gg-training-bullets li::before {{ content: '\\2014'; position: absolute; left: 0; color: var(--gg-color-tan); }}
.gg-neo-brutalist-page .gg-training-primary .gg-btn {{ background: var(--gg-color-white); color: var(--gg-color-primary-brown); border-color: var(--gg-color-white); }}
.gg-neo-brutalist-page .gg-training-primary .gg-btn:hover {{ background: var(--gg-color-warm-paper); }}
.gg-neo-brutalist-page .gg-training-divider {{ display: flex; align-items: center; gap: 16px; margin: 20px 0; }}
.gg-neo-brutalist-page .gg-training-divider-line {{ flex: 1; height: 1px; background: var(--gg-color-tan); }}
.gg-neo-brutalist-page .gg-training-divider-text {{ font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; color: var(--gg-color-secondary-brown); letter-spacing: var(--gg-letter-spacing-ultra-wide); }}
.gg-neo-brutalist-page .gg-training-secondary {{ border: var(--gg-border-standard); background: var(--gg-color-near-black); padding: 28px 32px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }}
.gg-neo-brutalist-page .gg-training-secondary-text h4 {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); font-weight: 700; text-transform: uppercase; letter-spacing: var(--gg-letter-spacing-wider); margin-bottom: 6px; color: var(--gg-color-white); }}
.gg-neo-brutalist-page .gg-training-secondary-text .gg-training-subtitle {{ font-family: var(--gg-font-editorial); font-size: 12px; color: var(--gg-color-secondary-brown); margin: 0 0 8px 0; }}
.gg-neo-brutalist-page .gg-training-secondary-text p {{ font-family: var(--gg-font-editorial); font-size: 12px; color: var(--gg-color-secondary-brown); line-height: 1.5; margin: 0; }}
.gg-neo-brutalist-page .gg-training-secondary .gg-btn {{ background: transparent; color: var(--gg-color-white); border-color: var(--gg-color-white); }}
.gg-neo-brutalist-page .gg-training-secondary .gg-btn:hover {{ background: var(--gg-color-white); color: var(--gg-color-near-black); }}

/* Logistics */
.gg-neo-brutalist-page .gg-logistics-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.gg-neo-brutalist-page .gg-logistics-item {{ border: var(--gg-border-subtle); padding: 12px; background: var(--gg-color-warm-paper); }}
.gg-neo-brutalist-page .gg-logistics-item-label {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: var(--gg-color-secondary-brown); margin-bottom: var(--gg-spacing-2xs); }}
.gg-neo-brutalist-page .gg-logistics-item-value {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-sm); color: var(--gg-color-dark-brown); line-height: 1.5; }}

/* Photo grid */
.gg-neo-brutalist-page .gg-photos-body {{ padding: 0; }}
.gg-neo-brutalist-page .gg-photos-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0; }}
.gg-neo-brutalist-page .gg-photo-card {{ margin: 0; border: var(--gg-border-standard); overflow: hidden; }}
.gg-neo-brutalist-page .gg-photo-card img {{ width: 100%; height: 220px; object-fit: cover; display: block; }}
.gg-neo-brutalist-page .gg-photo-card figcaption {{ background: var(--gg-color-warm-paper); padding: var(--gg-spacing-xs) var(--gg-spacing-sm); font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); color: var(--gg-color-secondary-brown); letter-spacing: 0.5px; border-top: var(--gg-border-standard); }}
.gg-neo-brutalist-page .gg-photo-card figcaption a {{ color: var(--gg-color-primary-brown); text-decoration: none; font-weight: 700; }}
.gg-neo-brutalist-page .gg-photo-card figcaption a:hover {{ color: var(--gg-color-teal); }}

/* News ticker */
.gg-neo-brutalist-page .gg-news-ticker {{ background: var(--gg-color-near-black); border: var(--gg-border-standard); margin-bottom: 32px; display: flex; align-items: stretch; overflow: hidden; height: 48px; }}
.gg-neo-brutalist-page .gg-news-ticker-label {{ background: var(--gg-color-gold); color: var(--gg-color-near-black); font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; padding: 0 var(--gg-spacing-md); display: flex; align-items: center; white-space: nowrap; min-width: fit-content; border-right: var(--gg-border-standard); }}
.gg-neo-brutalist-page .gg-news-ticker-track {{ flex: 1; overflow: hidden; position: relative; display: flex; align-items: center; }}
.gg-neo-brutalist-page .gg-news-ticker-content {{ display: flex; align-items: center; white-space: nowrap; animation: gg-ticker-scroll 80s linear infinite; padding-left: 100%; }}
.gg-neo-brutalist-page .gg-news-ticker-content:hover {{ animation-play-state: paused; }}
.gg-neo-brutalist-page .gg-news-ticker-item {{ display: inline-flex; align-items: center; gap: 6px; padding: 0 32px; }}
.gg-neo-brutalist-page .gg-news-ticker-item a {{ color: var(--gg-color-tan); text-decoration: none; font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; letter-spacing: 0.5px; }}
.gg-neo-brutalist-page .gg-news-ticker-item a:hover {{ color: var(--gg-color-light-teal); }}
.gg-neo-brutalist-page .gg-news-ticker-source {{ color: var(--gg-color-secondary-brown); font-size: var(--gg-font-size-2xs); font-weight: 400; }}
.gg-neo-brutalist-page .gg-news-ticker-sep {{ color: var(--gg-color-teal); font-size: 8px; margin: 0 8px; }}
.gg-neo-brutalist-page .gg-news-ticker-loading {{ color: var(--gg-color-secondary-brown); font-size: 11px; letter-spacing: 1px; padding-left: 16px; }}
.gg-neo-brutalist-page .gg-news-ticker-empty {{ color: var(--gg-color-secondary-brown); font-size: 11px; letter-spacing: 1px; padding-left: 16px; }}
@keyframes gg-ticker-scroll {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-100%); }} }}

/* Sticky CTA */
.gg-sticky-cta {{ position: fixed; bottom: 0; left: 0; right: 0; z-index: 200; background: var(--gg-color-near-black); border-top: 3px solid var(--gg-color-teal); padding: 12px 24px; transform: translateY(100%); transition: transform 0.3s ease; }}
.gg-sticky-cta.is-visible {{ transform: translateY(0); }}
.gg-sticky-cta-inner {{ max-width: 960px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 16px; }}
.gg-sticky-cta-name {{ font-family: var(--gg-font-data); font-size: 13px; font-weight: 700; color: var(--gg-color-white); text-transform: uppercase; letter-spacing: 1px; }}
.gg-sticky-cta .gg-btn {{ font-family: var(--gg-font-data); background: var(--gg-color-teal); color: var(--gg-color-white); border: var(--gg-border-width-subtle) solid var(--gg-color-teal); padding: var(--gg-spacing-xs) 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: var(--gg-letter-spacing-wider); text-decoration: none; cursor: pointer; }}
.gg-sticky-cta .gg-btn:hover {{ background: #14695F; border-color: #14695F; }}
.gg-sticky-dismiss {{ background: none; border: none; color: var(--gg-color-white); font-size: 22px; cursor: pointer; opacity: 0.6; padding: 0 4px; line-height: 1; }}
.gg-sticky-dismiss:hover {{ opacity: 1; }}

/* Back to top */
.gg-back-to-top {{ position: fixed; bottom: 72px; right: 20px; z-index: 199; width: 40px; height: 40px; background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); border: 2px solid var(--gg-color-warm-paper); font-size: 18px; cursor: pointer; opacity: 0; visibility: hidden; transition: opacity 0.2s, visibility 0.2s; display: flex; align-items: center; justify-content: center; }}
.gg-back-to-top.is-visible {{ opacity: 1; visibility: visible; }}
.gg-back-to-top:hover {{ background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); }}

/* Scroll fade-in */
.gg-neo-brutalist-page .gg-fade-section {{ opacity: 0; transform: translateY(20px); transition: opacity 0.6s ease, transform 0.6s ease; }}
.gg-neo-brutalist-page .gg-fade-section.is-visible {{ opacity: 1; transform: translateY(0); }}

/* Email capture */
.gg-neo-brutalist-page .gg-email-capture {{ margin-bottom: var(--gg-spacing-xl); border: var(--gg-border-standard); background: var(--gg-color-primary-brown); padding: 0; }}
.gg-neo-brutalist-page .gg-email-capture-inner {{ padding: var(--gg-spacing-lg) var(--gg-spacing-xl); text-align: center; }}
.gg-neo-brutalist-page .gg-email-capture-title {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); font-weight: 700; letter-spacing: var(--gg-letter-spacing-ultra-wide); color: var(--gg-color-white); margin: 0 0 var(--gg-spacing-2xs) 0; }}
.gg-neo-brutalist-page .gg-email-capture-text {{ font-family: var(--gg-font-editorial); font-size: 12px; color: var(--gg-color-tan); line-height: var(--gg-line-height-relaxed); margin: 0 0 var(--gg-spacing-sm) 0; max-width: 500px; margin-left: auto; margin-right: auto; }}
.gg-neo-brutalist-page .gg-email-capture iframe {{ max-width: 480px; height: 100px; margin: 0 auto; display: block; overflow: hidden; }}

/* Countdown */
.gg-neo-brutalist-page .gg-countdown {{ border: var(--gg-border-width-standard) solid var(--gg-color-teal); background: var(--gg-color-near-black); color: var(--gg-color-white); padding: var(--gg-spacing-md); text-align: center; font-family: var(--gg-font-data); font-size: 12px; font-weight: 700; letter-spacing: var(--gg-letter-spacing-ultra-wide); margin-bottom: 20px; }}
.gg-neo-brutalist-page .gg-countdown-num {{ font-size: 32px; color: var(--gg-color-teal); display: block; line-height: 1.2; }}

/* FAQ accordion */
.gg-neo-brutalist-page .gg-faq-item {{ border-bottom: 1px solid var(--gg-color-sand); }}
.gg-neo-brutalist-page .gg-faq-item:last-child {{ border-bottom: none; }}
.gg-neo-brutalist-page .gg-faq-question {{ display: flex; align-items: center; justify-content: space-between; cursor: pointer; padding: 16px 0; gap: 12px; }}
.gg-neo-brutalist-page .gg-faq-question h3 {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); font-weight: 700; color: var(--gg-color-dark-brown); margin: 0; text-transform: none; letter-spacing: 0; }}
.gg-neo-brutalist-page .gg-faq-toggle {{ font-size: 20px; font-weight: 700; color: var(--gg-color-primary-brown); transition: transform 0.3s; flex-shrink: 0; }}
.gg-neo-brutalist-page .gg-faq-item.open .gg-faq-toggle {{ transform: rotate(45deg); }}
.gg-neo-brutalist-page .gg-faq-answer {{ max-height: 0; overflow: hidden; transition: max-height 0.3s ease; }}
.gg-neo-brutalist-page .gg-faq-answer p {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-sm); color: var(--gg-color-secondary-brown); line-height: var(--gg-line-height-prose); margin: 0; }}
.gg-neo-brutalist-page .gg-faq-item.open .gg-faq-answer {{ max-height: 500px; padding-bottom: 16px; }}

/* Similar races */
.gg-neo-brutalist-page .gg-similar-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
.gg-neo-brutalist-page .gg-similar-card {{ display: block; border: var(--gg-border-subtle); padding: 16px; background: var(--gg-color-warm-paper); text-decoration: none; color: var(--gg-color-dark-brown); transition: border-color 0.15s, background 0.15s; }}
.gg-neo-brutalist-page .gg-similar-card:hover {{ border-color: var(--gg-color-gold); background: var(--gg-color-sand); }}
.gg-neo-brutalist-page .gg-similar-tier {{ font-family: var(--gg-font-data); display: inline-block; background: var(--gg-color-gold); color: var(--gg-color-dark-brown); padding: 2px 8px; font-size: 9px; font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); margin-bottom: 6px; }}
.gg-neo-brutalist-page .gg-similar-name {{ font-family: var(--gg-font-editorial); display: block; font-size: var(--gg-font-size-base); font-weight: var(--gg-font-weight-semibold); letter-spacing: 0; margin-bottom: 4px; }}
.gg-neo-brutalist-page .gg-similar-meta {{ display: block; font-size: var(--gg-font-size-2xs); color: var(--gg-color-secondary-brown); letter-spacing: 0.5px; }}

/* Site nav */
.gg-site-nav {{ background: var(--gg-color-dark-brown); padding: 12px 20px; border-bottom: var(--gg-border-standard); }}
.gg-site-nav-inner {{ display: flex; align-items: center; gap: 24px; margin-bottom: 6px; }}
.gg-site-nav-brand {{ color: var(--gg-color-white); text-decoration: none; font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); font-weight: 700; letter-spacing: var(--gg-letter-spacing-ultra-wide); }}
.gg-site-nav-link {{ color: var(--gg-color-tan); text-decoration: none; font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; }}
.gg-site-nav-link:hover {{ color: var(--gg-color-gold); }}
.gg-breadcrumb {{ font-family: var(--gg-font-data); font-size: 11px; }}
.gg-breadcrumb a {{ color: var(--gg-color-warm-brown); text-decoration: none; }}
.gg-breadcrumb a:hover {{ color: var(--gg-color-gold); }}
.gg-breadcrumb-sep {{ color: var(--gg-color-secondary-brown); margin: 0 4px; }}
.gg-breadcrumb-current {{ color: var(--gg-color-warm-paper); }}

/* Citations */
.gg-neo-brutalist-page .gg-citations-intro {{ font-size: var(--gg-font-size-xs); color: var(--gg-color-secondary-brown); margin-bottom: var(--gg-spacing-md); line-height: var(--gg-line-height-relaxed); }}
.gg-neo-brutalist-page .gg-citations-list {{ list-style: decimal; padding-left: 24px; margin: 0; }}
.gg-neo-brutalist-page .gg-citation-item {{ font-size: var(--gg-font-size-2xs); line-height: 1.8; border-bottom: 1px solid var(--gg-color-cream); padding: 4px 0; }}
.gg-neo-brutalist-page .gg-citation-item:last-child {{ border-bottom: none; }}
.gg-neo-brutalist-page .gg-citation-cat {{ display: inline-block; background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); font-size: 9px; font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; padding: 1px 6px; margin-right: 6px; }}
.gg-neo-brutalist-page .gg-citation-link {{ color: var(--gg-color-dark-teal); text-decoration: none; font-weight: 600; }}
.gg-neo-brutalist-page .gg-citation-link:hover {{ color: var(--gg-color-teal); text-decoration: underline; }}
.gg-neo-brutalist-page .gg-citation-url {{ display: block; color: var(--gg-color-secondary-brown); font-size: 9px; word-break: break-all; }}

/* Footer */
.gg-neo-brutalist-page .gg-footer {{ background: var(--gg-color-dark-brown); color: var(--gg-color-tan); padding: 24px 20px; border-top: var(--gg-border-double); margin-bottom: 80px; font-size: 11px; text-align: center; letter-spacing: 0.5px; }}
.gg-neo-brutalist-page .gg-footer a {{ color: var(--gg-color-white); text-decoration: none; }}
.gg-neo-brutalist-page .gg-footer a:hover {{ color: var(--gg-color-gold); }}
.gg-neo-brutalist-page .gg-footer-nav {{ display: flex; justify-content: center; gap: 24px; margin-bottom: var(--gg-spacing-md); }}
.gg-neo-brutalist-page .gg-footer-nav a {{ font-family: var(--gg-font-data); font-size: 11px; font-weight: 700; letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; }}
.gg-neo-brutalist-page .gg-footer-updated {{ color: var(--gg-color-secondary-brown); font-size: var(--gg-font-size-2xs); margin: var(--gg-spacing-xs) 0 0 0; letter-spacing: 1px; text-transform: uppercase; }}
.gg-neo-brutalist-page .gg-footer-disclaimer {{ color: var(--gg-color-secondary-brown); line-height: var(--gg-line-height-relaxed); margin: var(--gg-spacing-sm) 0 0 0; font-size: var(--gg-font-size-2xs); }}

/* Responsive — tablet */
@media (max-width: 1024px) {{
  .gg-neo-brutalist-page .gg-radar-pair {{ gap: 8px; }}
  .gg-neo-brutalist-page .gg-similar-grid {{ grid-template-columns: 1fr 1fr; }}  /* 2-col on tablet */
  .gg-neo-brutalist-page .gg-stat-grid {{ grid-template-columns: repeat(3, 1fr); gap: 10px; }}
  .gg-neo-brutalist-page .gg-news-ticker {{ display: none; }}
}}

/* Responsive — mobile */
@media (max-width: 768px) {{
  .gg-neo-brutalist-page .gg-hero {{ padding: var(--gg-spacing-2xl) var(--gg-spacing-lg); }}
  .gg-neo-brutalist-page .gg-hero h1 {{ font-size: var(--gg-font-size-2xl); }}
  .gg-neo-brutalist-page .gg-hero-score {{ position: static; margin-top: var(--gg-spacing-md); text-align: left; }}
  .gg-neo-brutalist-page .gg-hero-score-number {{ font-size: var(--gg-font-size-4xl); }}
  .gg-neo-brutalist-page .gg-stat-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .gg-neo-brutalist-page .gg-verdict-grid {{ grid-template-columns: 1fr; }}
  .gg-neo-brutalist-page .gg-logistics-grid {{ grid-template-columns: 1fr; }}
  .gg-neo-brutalist-page .gg-ratings-summary {{ flex-direction: column; }}
  .gg-neo-brutalist-page .gg-radar-pair {{ flex-direction: column; }}
  .gg-neo-brutalist-page .gg-accordion-label {{ width: 80px; min-width: 80px; font-size: 10px; }}
  .gg-neo-brutalist-page .gg-accordion-content {{ padding-left: 0; }}
  .gg-neo-brutalist-page .gg-training-secondary {{ flex-direction: column; text-align: center; }}
  .gg-sticky-cta-name {{ display: none; }}
  .gg-sticky-cta .gg-btn {{ width: 100%; text-align: center; }}
  .gg-neo-brutalist-page .gg-toc {{ flex-direction: column; gap: 6px; }}
  .gg-neo-brutalist-page .gg-map-embed iframe {{ height: 250px; }}
  .gg-neo-brutalist-page .gg-pullquote {{ padding: var(--gg-spacing-lg); }}
  .gg-neo-brutalist-page .gg-pullquote-text {{ font-size: var(--gg-font-size-base); }}
  .gg-neo-brutalist-page .gg-pullquote-text::before {{ position: static; display: block; margin-bottom: -10px; }}
  .gg-neo-brutalist-page .gg-pullquote-text::after {{ display: none; }}
  .gg-neo-brutalist-page .gg-news-ticker-label {{ font-size: 9px; padding: 0 10px; letter-spacing: 1px; }}
  .gg-neo-brutalist-page .gg-email-capture iframe {{ height: 100px; }}
  .gg-neo-brutalist-page .gg-similar-grid {{ grid-template-columns: 1fr; }}
  .gg-neo-brutalist-page .gg-countdown-num {{ font-size: 24px; }}
}}

/* Responsive — small phones */
@media (max-width: 480px) {{
  .gg-neo-brutalist-page {{ padding: 0 12px; }}
  .gg-neo-brutalist-page .gg-hero {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-neo-brutalist-page .gg-hero h1 {{ font-size: var(--gg-font-size-xl); }}
  .gg-neo-brutalist-page .gg-hero-score-number {{ font-size: var(--gg-font-size-3xl); }}
  .gg-neo-brutalist-page .gg-stat-grid {{ grid-template-columns: 1fr; }}
  .gg-neo-brutalist-page .gg-section-header {{ flex-wrap: wrap; gap: 4px 12px; padding: 12px 16px; }}
  .gg-neo-brutalist-page .gg-section-kicker {{ white-space: normal; }}
  .gg-neo-brutalist-page .gg-section-body {{ padding: 16px 12px; }}
  .gg-neo-brutalist-page .gg-suffering-mile {{ min-width: 60px; padding: 8px; }}
  .gg-neo-brutalist-page .gg-suffering-mile-num {{ font-size: var(--gg-font-size-md); }}
  .gg-neo-brutalist-page .gg-suffering-content {{ padding: 8px 12px; }}
  .gg-neo-brutalist-page .gg-accordion-label {{ width: 65px; min-width: 65px; font-size: 9px; letter-spacing: 0.5px; }}
  .gg-neo-brutalist-page .gg-accordion-score {{ width: 32px; min-width: 32px; font-size: 12px; }}
  .gg-neo-brutalist-page .gg-site-nav {{ padding: 10px 12px; }}
  .gg-neo-brutalist-page .gg-breadcrumb {{ font-size: 10px; }}
  .gg-sticky-cta {{ padding: 10px 12px; }}
  .gg-back-to-top {{ bottom: 60px; right: 12px; width: 36px; height: 36px; }}
}}
</style>'''


# ── Shared Assets ─────────────────────────────────────────────


def _extract_css_content() -> str:
    """Extract raw CSS from get_page_css() (strip <style> tags)."""
    raw = get_page_css()
    return raw.replace('<style>', '').replace('</style>', '').strip()


def _extract_js_content() -> str:
    """Extract raw JS from build_inline_js() (strip <script> tags)."""
    raw = build_inline_js()
    return raw.replace('<script>', '').replace('</script>', '').strip()


def write_shared_assets(output_dir: Path) -> dict:
    """Write shared CSS/JS to external files with content hash. Returns asset info."""
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Copy self-hosted font files
    fonts_dir = assets_dir / "fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    for font_file in FONT_FILES:
        src = BRAND_FONTS_DIR / font_file
        dst = fonts_dir / font_file
        if src.exists():
            shutil.copy2(src, dst)
        else:
            print(f"  WARNING: Font file not found: {src}")
    print(f"  Copied {len(FONT_FILES)} font files to {fonts_dir}/")

    css_content = _extract_css_content()
    js_content = _extract_js_content()

    css_hash = hashlib.md5(css_content.encode()).hexdigest()[:8]
    js_hash = hashlib.md5(js_content.encode()).hexdigest()[:8]

    css_file = f"gg-styles.{css_hash}.css"
    js_file = f"gg-scripts.{js_hash}.js"

    # Clean up stale hashed assets before writing new ones
    for old in assets_dir.glob("gg-styles.*.css"):
        if old.name != css_file:
            old.unlink()
    for old in assets_dir.glob("gg-scripts.*.js"):
        if old.name != js_file:
            old.unlink()

    (assets_dir / css_file).write_text(css_content, encoding='utf-8')
    (assets_dir / js_file).write_text(js_content, encoding='utf-8')

    print(f"  Wrote {assets_dir / css_file} ({len(css_content):,} bytes)")
    print(f"  Wrote {assets_dir / js_file} ({len(js_content):,} bytes)")

    return {
        "css_tag": f'<link rel="stylesheet" href="/race/assets/{css_file}">',
        "js_tag": f'<script src="/race/assets/{js_file}"></script>',
    }


# ── Page Assembly ──────────────────────────────────────────────

def generate_page(rd: dict, race_index: list = None, external_assets: dict = None) -> str:
    """Generate complete HTML page from normalized race data.

    If external_assets is provided, references external CSS/JS files instead of inlining.
    """
    race_index = race_index or []
    q_url = get_questionnaire_url(rd['slug'])
    canonical_url = f"{SITE_BASE_URL}/race/{rd['slug']}/"

    # JSON-LD
    jsonld_parts = []
    sports_event = build_sports_event_jsonld(rd)
    jsonld_parts.append(json.dumps(sports_event, indent=2, ensure_ascii=False))
    faq = build_faq_jsonld(rd)
    if faq:
        jsonld_parts.append(json.dumps(faq, indent=2, ensure_ascii=False))
    if race_index:
        breadcrumb = build_breadcrumb_jsonld(rd, race_index)
        jsonld_parts.append(json.dumps(breadcrumb, indent=2, ensure_ascii=False))

    webpage = build_webpage_jsonld(rd)
    jsonld_parts.append(json.dumps(webpage, indent=2, ensure_ascii=False))

    jsonld_html = '\n'.join(
        f'<script type="application/ld+json">\n{j}\n</script>'
        for j in jsonld_parts
    )

    # Build sections
    nav_header = build_nav_header(rd, race_index)
    hero = build_hero(rd)
    toc = build_toc()
    course_overview = build_course_overview(rd, race_index)
    history = build_history(rd)
    pullquote = build_pullquote(rd)
    course_route = build_course_route(rd)
    photos = build_photos_section(rd)
    ratings = build_ratings(rd)
    verdict = build_verdict(rd, race_index)
    email_capture = build_email_capture(rd)
    visible_faq = build_visible_faq(rd)
    news = build_news_section(rd)
    training = build_training(rd, q_url)
    logistics_sec = build_logistics_section(rd)
    similar = build_similar_races(rd, race_index)
    citations_sec = build_citations_section(rd)
    footer = build_footer(rd)
    sticky_cta = build_sticky_cta(rd['name'], q_url)

    # Use external assets if provided, otherwise inline
    if external_assets:
        # Inline minimal critical CSS to prevent flash of white while stylesheet loads
        critical_css = '''<style>
body{margin:0;background:#ede4d8}
.gg-neo-brutalist-page{max-width:960px;margin:0 auto;padding:0 20px;font-family:'Sometype Mono',monospace;color:#3a2e25;background:#ede4d8}
.gg-neo-brutalist-page *,.gg-neo-brutalist-page *::before,.gg-neo-brutalist-page *::after{border-radius:0!important;box-shadow:none!important;box-sizing:border-box}
.gg-site-nav{background:#3a2e25;padding:12px 20px;border-bottom:3px solid #3a2e25}
.gg-hero{background:#3a2e25;color:#f5efe6;padding:64px 48px;border-bottom:4px double #3a2e25;position:relative;overflow:hidden}
</style>
  '''
        css = critical_css + external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        css = get_page_css()
        inline_js = build_inline_js()

    # Section order
    content_sections = []
    for section in [course_overview, history, pullquote, course_route, photos,
                    ratings, verdict, email_capture, news,
                    training, logistics_sec, similar, visible_faq,
                    citations_sec]:
        if section:
            content_sections.append(section)

    content = '\n\n  '.join(content_sections)

    # SEO-optimized title and description
    seo_title = build_seo_title(rd)
    seo_description = build_seo_description(rd)

    # Open Graph meta tags
    og_image_url = f"{SITE_BASE_URL}/og/{rd['slug']}.jpg"
    og_tags = f'''<meta property="og:title" content="{esc(seo_title)}">
  <meta property="og:description" content="{esc(seo_description)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{esc(og_image_url)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(seo_title)}">
  <meta name="twitter:description" content="{esc(seo_description)}">
  <meta name="twitter:image" content="{esc(og_image_url)}">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(seo_title)}</title>
  <meta name="description" content="{esc(seo_description)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='%233a2e25'/><text x='16' y='24' text-anchor='middle' font-family='serif' font-size='24' font-weight='700' fill='%23B7950B'>G</text></svg>">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  <link rel="dns-prefetch" href="https://ridewithgps.com">
  <link rel="dns-prefetch" href="https://api.rss2json.com">
  {preload}
  {og_tags}
  {jsonld_html}
  {css}
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
</head>
<body>

<a href="#course" class="gg-skip-link">Skip to content</a>
<div class="gg-neo-brutalist-page">
  {nav_header}

  {hero}

  {toc}

  {content}

  {footer}
</div>

{sticky_cta}
<button class="gg-back-to-top" id="gg-back-to-top" aria-label="Back to top">&uarr;</button>
{inline_js}

</body>
</html>'''


# ── Data Loading ───────────────────────────────────────────────

def find_data_file(slug: str, data_dirs: list) -> Optional[Path]:
    """Find a race data file by slug, searching multiple directories."""
    for d in data_dirs:
        d = Path(d)
        # New format: {slug}.json
        candidate = d / f"{slug}.json"
        if candidate.exists():
            return candidate
        # Old format: {slug}-data.json
        candidate = d / f"{slug}-data.json"
        if candidate.exists():
            return candidate
    return None


def load_race_data(filepath: Path) -> dict:
    """Load and normalize race data from a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    rd = normalize_race_data(raw)
    # Store file mtime for accurate dateModified in JSON-LD
    rd['_file_mtime'] = datetime.fromtimestamp(filepath.stat().st_mtime).strftime('%Y-%m-%d')
    return rd


def main():
    parser = argparse.ArgumentParser(
        description="Generate neo-brutalist landing page HTML for gravel race profiles."
    )
    parser.add_argument('slug', nargs='?', help='Race slug (e.g., unbound-200)')
    parser.add_argument('--all', action='store_true', help='Generate pages for all races')
    parser.add_argument('--data-dir', help='Primary data directory (default: auto-detect)')
    parser.add_argument('--output-dir', default=None, help='Output directory (default: wordpress/output/)')
    args = parser.parse_args()

    if not args.slug and not args.all:
        parser.error("Provide a race slug or use --all")

    # Resolve data directories
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    data_dirs = []
    if args.data_dir:
        data_dirs.append(Path(args.data_dir))
    data_dirs.append(project_root / 'race-data')
    data_dirs.append(project_root / 'data')

    # Output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = script_dir / 'output'
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load race index for internal linking + breadcrumbs
    index_path = project_root / 'web' / 'race-index.json'
    race_index = []
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            race_index = json.load(f)
        print(f"Loaded race index: {len(race_index)} races")

    if args.all:
        # Generate for all races in the primary data directory
        primary = None
        for d in data_dirs:
            d = Path(d)
            if d.exists() and list(d.glob('*.json')):
                primary = d
                break
        if not primary:
            print("ERROR: No data directory found with JSON files.", file=sys.stderr)
            sys.exit(1)

        files = sorted(primary.glob('*.json'))
        total = len(files)
        success = 0
        errors = []

        # Write shared CSS/JS assets
        assets = write_shared_assets(output_dir)

        for i, f in enumerate(files, 1):
            slug = f.stem.replace('-data', '')
            try:
                rd = load_race_data(f)
                page_html = generate_page(rd, race_index, external_assets=assets)
                out = output_dir / f"{slug}.html"
                out.write_text(page_html, encoding='utf-8')
                success += 1
                if i % 50 == 0 or i == total:
                    print(f"  [{i}/{total}] Generated {slug}.html")
            except Exception as e:
                errors.append((slug, str(e)))
                print(f"  ERROR: {slug}: {e}", file=sys.stderr)

        print(f"\nDone. {success}/{total} pages generated in {output_dir}/")
        if errors:
            print(f"\n{len(errors)} errors:")
            for slug, err in errors:
                print(f"  {slug}: {err}")
    else:
        # Single race
        filepath = find_data_file(args.slug, data_dirs)
        if not filepath:
            print(f"ERROR: No data file found for slug '{args.slug}'", file=sys.stderr)
            print(f"  Searched: {', '.join(str(d) for d in data_dirs)}", file=sys.stderr)
            sys.exit(1)

        rd = load_race_data(filepath)
        page_html = generate_page(rd, race_index)
        out = output_dir / f"{args.slug}.html"
        out.write_text(page_html, encoding='utf-8')
        print(f"Generated: {out}")
        print(f"  Race: {rd['name']}")
        print(f"  Tier: {rd['tier_label']} (Score: {rd['overall_score']})")
        print(f"  Sections: Course Overview, History, Course, Ratings, Verdict, FAQ, Training, Logistics, Similar Races")


if __name__ == '__main__':
    main()
