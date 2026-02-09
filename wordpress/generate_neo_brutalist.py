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
import html
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Optional

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

QUESTIONNAIRE_SLUGS = {
    'unbound-200': 'unbound-200',
    'unbound-gravel-200': 'unbound-200',
    'mid-south': 'mid-south',
    'sbt-grvl': 'sbt-grvl',
    'belgian-waffle-ride': 'bwr',
    'leadville-trail-100-mtb': 'leadville-100',
    'the-rift-iceland': 'rift-iceland',
    'gravel-worlds': 'gravel-worlds',
    'steamboat-gravel': 'steamboat-gravel',
}

QUESTIONNAIRE_BASE = "https://wattgod.github.io/training-plans-component/training-plan-questionnaire.html"
COACHING_URL = "https://www.wattgod.com/apply"
SITE_BASE_URL = "https://gravelgodcycling.com"
SUBSTACK_URL = "https://gravelgodcycling.substack.com"
SUBSTACK_EMBED = "https://gravelgodcycling.substack.com/embed"


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
    5: teal (#1A8A82), 4: dark gold (#B7950B), 3: primary brown (#59473c),
    2: lighter brown (#8c7568), 1: muted tan (#c4b5ab)."""
    return {5: '#1A8A82', 4: '#B7950B', 3: '#59473c', 2: '#8c7568', 1: '#c4b5ab'}.get(score, '#c4b5ab')


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
        grid_lines.append(f'<polygon points="{pts}" fill="none" stroke="#8c7568" stroke-opacity="{opacity}" stroke-width="0.5"/>')

    # Axis lines
    axis_lines = []
    for i in range(n):
        angle = angle_offset + i * 2 * math.pi / n
        x2, y2 = point(angle, r)
        axis_lines.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#c4b5ab" stroke-width="0.5"/>')

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
            f'stroke="#000" stroke-width="1.5" class="gg-radar-dot" pointer-events="none" opacity="0"/>'
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
            f'fill="#333" font-family="Sometype Mono, monospace" letter-spacing="0.5">'
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
        f'font-size="9" fill="#8c7568" font-family="Sometype Mono, monospace" letter-spacing="1">'
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
      <rect class="gg-radar-tooltip-bg" x="0" y="0" width="0" height="0" fill="#000" rx="0" opacity="0"/>
      <text class="gg-radar-tooltip-text" x="0" y="0" fill="#fff" font-size="10" font-weight="700" font-family="Sometype Mono, monospace" opacity="0"></text>
    </svg>
    <div class="gg-radar-label">{esc(label)}</div>
  </div>'''


def build_radar_charts(explanations: dict, course_total: int, opinion_total: int) -> str:
    """Build side-by-side radar charts for Course Profile and Editorial dimensions."""
    course_chart = _radar_svg(COURSE_DIMS, explanations, '#1A8A82', '#1A8A82',
                              'Course Profile', course_total, 35, idx_offset=0)
    editorial_chart = _radar_svg(OPINION_DIMS, explanations, '#B7950B', '#B7950B',
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
    <a href="{esc(url)}" class="gg-btn" target="_blank" rel="noopener">BUILD MY FREE PLAN</a>
  </div>
</div>'''


def build_inline_js() -> str:
    """Build the inline JavaScript for all interactive features."""
    return '''<script>
// Accordion toggle (independent mode — multiple can be open)
document.querySelectorAll('.gg-accordion-trigger').forEach(function(trigger) {
  if (trigger.dataset.noContent) return;
  trigger.addEventListener('click', function() {
    var item = trigger.closest('.gg-accordion-item');
    var expanded = item.classList.toggle('is-open');
    trigger.setAttribute('aria-expanded', expanded);
  });
});

// Race day countdown
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
  } else if (el && diff <= 0) {
    cd.style.display = 'none';
  }
})();

// Hero score counter animation
(function() {
  var el = document.querySelector('.gg-hero-score-number');
  if (!el) return;
  var target = parseInt(el.getAttribute('data-target'), 10);
  if (!target) return;
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

  Promise.allSettled([
    fetch(newsUrl).then(function(r) { return r.json(); }),
    fetch(redditUrl).then(function(r) { return r.json(); })
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
      feed.innerHTML = '<span class="gg-news-ticker-empty">No recent headlines.</span>';
      feed.style.animation = 'none';
      feed.style.paddingLeft = '16px';
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
    // Spacer + duplicate for seamless loop
    var spacer = document.createElement('span');
    spacer.style.padding = '0 80px';
    feed.appendChild(spacer);
    feed.appendChild(buildTickerItems(all));
  });
})();
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
    }

    # Parse ISO date
    date_specific = rd['vitals'].get('date_specific', '')
    date_match = re.search(r'(\d{4}).*?(\w+)\s+(\d+)', date_specific)
    if date_match:
        year, month_name, day = date_match.groups()
        months = {"january": "01", "february": "02", "march": "03", "april": "04",
                  "may": "05", "june": "06", "july": "07", "august": "08",
                  "september": "09", "october": "10", "november": "11", "december": "12"}
        month_num = months.get(month_name.lower(), "01")
        jsonld["startDate"] = f"{year}-{month_num}-{int(day):02d}"

    location = rd['vitals'].get('location', '')
    if location and location != '--':
        jsonld["location"] = {"@type": "Place", "name": location}

    # Parse price
    reg = rd['vitals'].get('registration', '')
    price_match = re.search(r'\$(\d+)', reg)
    if price_match:
        jsonld["offers"] = {
            "@type": "Offer",
            "price": price_match.group(1),
            "priceCurrency": "USD",
            "availability": "https://schema.org/LimitedAvailability",
        }

    if rd['overall_score']:
        jsonld["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(rd['overall_score']),
            "bestRating": "100",
            "reviewCount": "1",
            "name": "Gravel God Rating",
        }

    official_site = rd['logistics'].get('official_site', '')
    if official_site and official_site.startswith('http'):
        jsonld["url"] = official_site

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
    """Build hero section."""
    return f'''<section class="gg-hero">
  <span class="gg-hero-tier">{esc(rd['tier_label'])}</span>
  <h1 data-text="{esc(rd['name'])}">{esc(rd['name'])}</h1>
  <p class="gg-hero-tagline">{esc(rd['tagline'])}</p>
  <div class="gg-hero-score">
    <div class="gg-hero-score-number" data-target="{rd['overall_score']}">0</div>
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
    ]
    items = '\n  '.join(f'<a href="#{href}">{label}</a>' for href, label in links)
    return f'<nav class="gg-toc">\n  {items}\n</nav>'


def build_course_overview(rd: dict) -> str:
    """Build [01] Course Overview section — merged map + stat cards."""
    v = rd['vitals']

    # Map embed
    map_html = ''
    rwgps_id = rd['course'].get('ridewithgps_id')
    rwgps_name = rd['course'].get('ridewithgps_name', '')
    if rwgps_id:
        map_html = f'''<div class="gg-map-embed">
        <iframe src="https://ridewithgps.com/embeds?type=route&amp;id={esc(rwgps_id)}&amp;title={esc(rwgps_name)}" scrolling="no" allowfullscreen loading="lazy"></iframe>
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
        hard_label, hard_color = 'BRUTAL', '#000'
    elif hard_pct >= 60:
        hard_label, hard_color = 'HARD', '#59473c'
    elif hard_pct >= 40:
        hard_label, hard_color = 'MODERATE', '#B7950B'
    else:
        hard_label, hard_color = 'ACCESSIBLE', '#1A8A82'

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
    </div>
  </section>'''


def build_history(rd: dict) -> str:
    """Build [02] Facts & History section."""
    h = rd['history']

    # Skip entirely if no meaningful content
    if not h.get('origin_story') and not h.get('notable_moments') and not h.get('reputation'):
        return ''

    body_parts = []

    # Origin story
    if h.get('origin_story'):
        founded = f" Founded in {h['founded']}." if h.get('founded') else ''
        founder = f" By {h['founder']}." if h.get('founder') and h['founder'] != 'Unknown' else ''
        body_parts.append(f'<div class="gg-prose"><p>{esc(h["origin_story"])}{esc(founded)}{esc(founder)}</p></div>')

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
      <h3 class="gg-accordion-group-title" style="margin-top:20px">Editorial Assessment</h3>
      {opinion_accordion}
    </div>
  </section>'''


def build_verdict(rd: dict) -> str:
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
        linked = linkify_alternatives(fv['alternatives'], set())
        alt_html = f'''<div class="gg-prose" style="margin-top:16px"><p><strong>Alternatives:</strong> {linked}</p></div>'''

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
        months = {"january": "01", "february": "02", "march": "03", "april": "04",
                  "may": "05", "june": "06", "july": "07", "august": "08",
                  "september": "09", "october": "10", "november": "11", "december": "12"}
        month_num = months.get(month_name.lower(), "01")
        iso_date = f"{year}-{month_num}-{int(day):02d}"
        countdown_html = f'<div class="gg-countdown" data-date="{iso_date}"><span class="gg-countdown-num" id="gg-days-left">--</span> DAYS UNTIL {esc(race_name.upper())}</div>'

    return f'''<section id="training" class="gg-section gg-fade-section">
    <div class="gg-section-header">
      <span class="gg-section-kicker">[06]</span>
      <h2 class="gg-section-title">Training</h2>
    </div>
    <div class="gg-section-body">
      {countdown_html}
      <div class="gg-training-primary">
        <h3>Free Structured Plan</h3>
        <p class="gg-training-subtitle">Self-guided. Built for {esc(race_name)}. Yours in 2 minutes.</p>
        <ul class="gg-training-bullets">
          <li>Answer a quick questionnaire about your fitness and schedule</li>
          <li>Get a periodized plan calibrated to {esc(race_name)}</li>
          <li>Follow it on your own, at your pace</li>
        </ul>
        <a href="{esc(q_url)}" class="gg-btn" target="_blank" rel="noopener">BUILD MY FREE PLAN</a>
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

    # Filter out empty items
    items_data = [(label, val) for label, val in items_data if val]

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
        site_html = f'''<div style="margin-top:16px">
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


def build_instagram_section(rd: dict) -> str:
    """Build Instagram photo carousel section.
    Uses race name to generate a hashtag-based embed placeholder.
    On WordPress, this can be replaced with a Smash Balloon shortcode."""
    name = rd['name']
    slug = rd['slug']
    # Generate plausible hashtag from race name
    hashtag = re.sub(r'[^a-zA-Z0-9]', '', name)

    return f'''<section id="photos" class="gg-section gg-fade-section gg-section--accent">
    <div class="gg-section-header gg-section-header--dark">
      <span class="gg-section-kicker">[&mdash;]</span>
      <h2 class="gg-section-title">From the Field</h2>
    </div>
    <div class="gg-section-body gg-instagram-body">
      <div class="gg-instagram-carousel" id="gg-instagram-carousel" data-hashtag="{esc(hashtag)}" data-race="{esc(slug)}">
        <div class="gg-instagram-placeholder">
          <div class="gg-instagram-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#8c7568" stroke-width="1.5"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="5"/><circle cx="17.5" cy="6.5" r="1.5" fill="#8c7568" stroke="none"/></svg>
          </div>
          <p class="gg-instagram-hashtag">#{esc(hashtag)}</p>
          <p class="gg-instagram-cta-text">Race photos from the community</p>
        </div>
      </div>
      <noscript>
        <p>Follow <strong>#{esc(hashtag)}</strong> on Instagram for race photos.</p>
      </noscript>
    </div>
  </section>'''


def build_news_section(rd: dict) -> str:
    """Build Latest News section — fetches Google News RSS via rss2json.com at runtime.
    Shows up to 5 recent headlines. Graceful fallback if feed fails or returns empty."""
    name = rd['name']
    # Build search query: race name works well for Google News
    search_query = name.replace(' ', '+')

    return f'''<div class="gg-news-ticker gg-fade-section" id="gg-news-ticker" data-query="{esc(search_query)}">
    <div class="gg-news-ticker-label">LATEST NEWS</div>
    <div class="gg-news-ticker-track">
      <div class="gg-news-ticker-content" id="gg-news-feed">
        <span class="gg-news-ticker-loading">Loading headlines&hellip;</span>
      </div>
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


def linkify_alternatives(alt_text: str, all_slugs: set) -> str:
    """Parse race names from alternatives text and link to profile pages.
    Matches known race names/slugs and wraps them in anchor tags."""
    if not alt_text:
        return ''

    # Known race name → slug mapping for common mentions
    RACE_ALIASES = {
        'Unbound': 'unbound-200',
        'Unbound Gravel': 'unbound-200',
        'Mid South': 'mid-south',
        'Belgian Waffle Ride': 'belgian-waffle-ride',
        'SBT GRVL': 'sbt-grvl',
        'Gravel Worlds': 'gravel-worlds',
        'Leadville': 'leadville-trail-100-mtb',
        'Steamboat Gravel': 'steamboat-gravel',
        'BWR': 'belgian-waffle-ride',
        'Gravel Locos': 'gravel-locos',
        'The Rift': 'the-rift-iceland',
        'Migration Gravel Race': 'migration-gravel-race',
        'Crusher in the Tushar': 'crusher-in-the-tushar',
        'Big Sugar': 'big-sugar-gravel',
        'Land Run': 'mid-south',
    }

    result = esc(alt_text)
    # Sort by length descending to match longer names first
    for name, slug in sorted(RACE_ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        escaped_name = esc(name)
        if escaped_name in result:
            link = f'<a href="/race/{slug}/" class="gg-alt-link">{escaped_name}</a>'
            result = result.replace(escaped_name, link, 1)

    return result


def build_email_capture(rd: dict) -> str:
    """Build email capture section — Substack iframe embed for native subscribe flow."""
    race_name = rd['name']
    return f'''<div class="gg-email-capture gg-fade-section">
    <div class="gg-email-capture-inner">
      <h3 class="gg-email-capture-title">RACE INTEL, DELIVERED</h3>
      <p class="gg-email-capture-text">Training tips, race updates, and course strategy for {esc(race_name)} and 300+ gravel races. Free. No spam.</p>
      <iframe src="{esc(SUBSTACK_EMBED)}" width="100%" height="150" style="border:none; background:transparent;" frameborder="0" scrolling="no" loading="lazy"></iframe>
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
        <h3 class="gg-faq-question">{esc(q)}</h3>
        <p class="gg-faq-answer">{esc(a)}</p>
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

    candidates = []
    for r in race_index:
        if r.get('slug') == slug:
            continue
        r_region = r.get('region', '')
        r_tier = r.get('tier', 4)
        r_score = r.get('overall_score', 0)
        # Score: same region = 10 points, same tier = 5, adjacent tier = 2, score proximity
        relevance = 0
        if my_region and r_region == my_region:
            relevance += 10
        if r_tier == tier:
            relevance += 5
        elif abs(r_tier - tier) == 1:
            relevance += 2
        relevance += max(0, 10 - abs(r_score - score) / 5)
        candidates.append((relevance, r))

    # Sort by relevance descending, take top 4
    candidates.sort(key=lambda x: x[0], reverse=True)
    top = [c[1] for c in candidates[:4]]

    if not top:
        return ''

    cards = []
    for r in top:
        tier_num = r.get('tier', 4)
        cards.append(f'''<a href="/race/{esc(r['slug'])}/" class="gg-similar-card">
        <span class="gg-similar-tier">T{tier_num}</span>
        <span class="gg-similar-name">{esc(r['name'])}</span>
        <span class="gg-similar-meta">{esc(r.get('location', ''))} &middot; {r.get('overall_score', 0)}/100</span>
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


def build_breadcrumb_jsonld(rd: dict, race_index: list) -> dict:
    """Build BreadcrumbList JSON-LD schema."""
    # Find region from index
    region = 'Gravel Races'
    for r in race_index:
        if r.get('slug') == rd['slug']:
            region = r.get('region', 'Gravel Races')
            break

    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home",
             "item": SITE_BASE_URL},
            {"@type": "ListItem", "position": 2, "name": "Gravel Races",
             "item": f"{SITE_BASE_URL}/races/"},
            {"@type": "ListItem", "position": 3, "name": region,
             "item": f"{SITE_BASE_URL}/races/{region.lower().replace(' ', '-')}/"},
            {"@type": "ListItem", "position": 4, "name": rd['name']},
        ]
    }


def build_footer() -> str:
    """Build page footer with disclaimer."""
    return '''<div class="gg-footer">
    <p class="gg-footer-disclaimer">This content is produced independently by Gravel God and is not affiliated with, endorsed by, or officially connected to any race organizer, event, or governing body mentioned on this page. All ratings, opinions, and assessments represent the editorial views of Gravel God based on publicly available information and community research. Race details are subject to change &mdash; always verify with official race sources.</p>
  </div>'''


# ── CSS ────────────────────────────────────────────────────────

def get_page_css() -> str:
    """Return the full page CSS. Brand colors: #59473c (primary brown),
    #8c7568 (lighter brown), #1A8A82 (dark teal), #B7950B (dark gold), #c4b5ab (tan)."""
    return '''<style>

/* Page wrapper */
.gg-neo-brutalist-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 20px;
  font-family: 'Sometype Mono', monospace;
  color: #000;
  line-height: 1.6;
}
.gg-neo-brutalist-page *, .gg-neo-brutalist-page *::before, .gg-neo-brutalist-page *::after {
  border-radius: 0 !important;
  box-shadow: none !important;
  font-family: 'Sometype Mono', monospace;
  box-sizing: border-box;
}

/* Hero */
.gg-neo-brutalist-page .gg-hero { background: #59473c; color: #fff; padding: 60px 40px; border: 3px solid #000; margin-bottom: 0; position: relative; overflow: hidden; }
.gg-neo-brutalist-page .gg-hero-tier { display: inline-block; background: #000; color: #fff; padding: 4px 12px; font-size: 12px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 16px; }
.gg-neo-brutalist-page .gg-hero h1 { font-size: 42px; font-weight: 700; line-height: 1.1; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 16px; color: #fff; position: relative; }
.gg-neo-brutalist-page .gg-hero h1::after { content: attr(data-text); position: absolute; left: 3px; top: 3px; color: #1A8A82; opacity: 0.3; z-index: 0; pointer-events: none; }
.gg-neo-brutalist-page .gg-hero-tagline { font-size: 16px; line-height: 1.5; color: #d4c5b9; max-width: 700px; }
.gg-neo-brutalist-page .gg-hero-score { position: absolute; top: 40px; right: 40px; text-align: center; }
.gg-neo-brutalist-page .gg-hero-score-number { font-size: 64px; font-weight: 700; line-height: 1; color: #fff; }
.gg-neo-brutalist-page .gg-hero-score-label { font-size: 10px; letter-spacing: 2px; text-transform: uppercase; color: #d4c5b9; }

/* TOC */
.gg-neo-brutalist-page .gg-toc { background: #000; padding: 16px 20px; border: 3px solid #000; border-top: none; display: flex; flex-wrap: wrap; gap: 8px 20px; margin-bottom: 32px; }
.gg-neo-brutalist-page .gg-toc a { color: #d4c5b9; text-decoration: none; font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; transition: color 0.2s; }
.gg-neo-brutalist-page .gg-toc a:hover { color: #fff; }

/* Section common */
.gg-neo-brutalist-page .gg-section { margin-bottom: 32px; border: 3px solid #000; background: #fff; }
.gg-neo-brutalist-page .gg-section-header { background: #59473c; color: #fff; padding: 14px 20px; display: flex; align-items: center; gap: 12px; }
.gg-neo-brutalist-page .gg-section-kicker { font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #d4c5b9; white-space: nowrap; }
.gg-neo-brutalist-page .gg-section-title { font-size: 16px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #fff; margin: 0; }
.gg-neo-brutalist-page .gg-section-body { padding: 24px 20px; }

/* Section header variant: dark (black bg) */
.gg-neo-brutalist-page .gg-section-header--dark { background: #000; }
.gg-neo-brutalist-page .gg-section-header--dark .gg-section-kicker { color: #8c7568; }

/* Section variant: accent (subtle warm bg) */
.gg-neo-brutalist-page .gg-section--accent { background: #faf5f0; }

/* Section variant: dark (black bg, light text) */
.gg-neo-brutalist-page .gg-section--dark { background: #111; }
.gg-neo-brutalist-page .gg-section--dark .gg-section-body { color: #d4c5b9; }
.gg-neo-brutalist-page .gg-section--dark .gg-prose { color: #d4c5b9; }
.gg-neo-brutalist-page .gg-section--dark .gg-prose p { color: #d4c5b9; }
.gg-neo-brutalist-page .gg-section--dark .gg-prose strong { color: #fff; }
.gg-neo-brutalist-page .gg-section--dark .gg-timeline { border-left-color: #B7950B; }
.gg-neo-brutalist-page .gg-section--dark .gg-timeline-text { color: #d4c5b9; }
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-grid { gap: 16px; }
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-box--race { background: #1a1a1a; border-color: #333; }
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-box--skip { background: #1a1a1a; border-color: #333; }
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-box-title { color: #fff; }
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-list li { color: #d4c5b9; }
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-bottom-line { background: #1a1a1a; border-color: #333; color: #d4c5b9; }
.gg-neo-brutalist-page .gg-section--dark .gg-verdict-bottom-line strong { color: #B7950B; }

/* Section variant: teal accent (teal top border) */
.gg-neo-brutalist-page .gg-section--teal-accent { border-top: 4px solid #1A8A82; }

/* Section header variant: teal */
.gg-neo-brutalist-page .gg-section-header--teal { background: #1A8A82; }
.gg-neo-brutalist-page .gg-section-header--teal .gg-section-kicker { color: rgba(255,255,255,0.6); }

/* Section header variant: gold */
.gg-neo-brutalist-page .gg-section-header--gold { background: #B7950B; }
.gg-neo-brutalist-page .gg-section-header--gold .gg-section-kicker { color: rgba(255,255,255,0.6); }

/* Stat cards */
.gg-neo-brutalist-page .gg-stat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.gg-neo-brutalist-page .gg-stat-card { border: 2px solid #000; padding: 16px; text-align: center; background: #f5f0eb; position: relative; transition: transform 0.15s; }
.gg-neo-brutalist-page .gg-stat-card::after { content: ''; position: absolute; top: 5px; left: 5px; width: 100%; height: 100%; background: #000; z-index: -1; transition: top 0.15s, left 0.15s; }
.gg-neo-brutalist-page .gg-stat-card:hover { transform: translate(-2px, -2px); }
.gg-neo-brutalist-page .gg-stat-card:hover::after { top: 7px; left: 7px; }
.gg-neo-brutalist-page .gg-stat-value { font-size: 24px; font-weight: 700; color: #59473c; line-height: 1.2; }
.gg-neo-brutalist-page .gg-stat-label { font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #666; margin-top: 4px; }

/* Difficulty gauge */
.gg-neo-brutalist-page .gg-difficulty-gauge { margin-top: 20px; border: 2px solid #000; padding: 16px; background: #fff; }
.gg-neo-brutalist-page .gg-difficulty-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
.gg-neo-brutalist-page .gg-difficulty-title { font-size: 10px; font-weight: 700; letter-spacing: 2px; color: #8c7568; }
.gg-neo-brutalist-page .gg-difficulty-label { font-size: 12px; font-weight: 700; letter-spacing: 2px; color: #000; }
.gg-neo-brutalist-page .gg-difficulty-track { height: 12px; background: #e0d6cc; border: 1px solid #000; position: relative; overflow: hidden; }
.gg-neo-brutalist-page .gg-difficulty-fill { height: 100%; transition: width 1.5s cubic-bezier(0.22,1,0.36,1); }
.gg-neo-brutalist-page .gg-difficulty-scale { display: flex; justify-content: space-between; margin-top: 6px; font-size: 8px; font-weight: 700; letter-spacing: 1px; color: #c4b5ab; text-transform: uppercase; }

/* Map embed */
.gg-neo-brutalist-page .gg-map-embed { border: 2px solid #000; margin-bottom: 16px; overflow: hidden; }
.gg-neo-brutalist-page .gg-map-embed iframe { width: 100%; height: 400px; border: none; display: block; }

/* Prose */
.gg-neo-brutalist-page .gg-prose { font-size: 14px; line-height: 1.7; color: #333; }
.gg-neo-brutalist-page .gg-prose p { margin-bottom: 14px; }
.gg-neo-brutalist-page .gg-prose p:last-child { margin-bottom: 0; }

/* Timeline */
.gg-neo-brutalist-page .gg-timeline { border-left: 3px solid #B7950B; margin: 16px 0 0 12px; padding-left: 20px; }
.gg-neo-brutalist-page .gg-timeline-item { position: relative; margin-bottom: 16px; padding-bottom: 4px; opacity: 0; transform: translateY(10px); transition: opacity 0.4s, transform 0.4s; }
.gg-neo-brutalist-page .gg-timeline-item.is-visible { opacity: 1; transform: translateY(0); }
.gg-neo-brutalist-page .gg-timeline-item::before { content: ''; position: absolute; left: -27px; top: 6px; width: 10px; height: 10px; background: #B7950B; border: 2px solid #000; }
.gg-neo-brutalist-page .gg-timeline-text { font-size: 13px; color: #333; line-height: 1.5; }

/* Suffering zones */
.gg-neo-brutalist-page .gg-suffering-zone { border: 2px solid #000; margin-bottom: 12px; display: flex; background: #f5f0eb; opacity: 0; transform: translateX(-30px); transition: opacity 0.5s, transform 0.5s; }
.gg-neo-brutalist-page .gg-suffering-zone.is-visible { opacity: 1; transform: translateX(0); }
.gg-neo-brutalist-page .gg-suffering-mile { background: #1A8A82; color: #fff; min-width: 80px; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 12px; border-right: 2px solid #000; }
.gg-neo-brutalist-page .gg-suffering-mile-num { font-size: 24px; font-weight: 700; }
.gg-neo-brutalist-page .gg-suffering-mile-label { font-size: 9px; letter-spacing: 2px; text-transform: uppercase; color: rgba(255,255,255,0.7); }
.gg-neo-brutalist-page .gg-suffering-content { padding: 12px 16px; flex: 1; }
.gg-neo-brutalist-page .gg-suffering-name { font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.gg-neo-brutalist-page .gg-suffering-desc { font-size: 12px; color: #555; line-height: 1.5; }

/* Accordion */
.gg-neo-brutalist-page .gg-accordion { border-top: 2px solid #000; }
.gg-neo-brutalist-page .gg-accordion-group-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #8c7568; padding: 16px 0 8px 0; }
.gg-neo-brutalist-page .gg-accordion-item { border-bottom: 2px solid #000; }
.gg-neo-brutalist-page .gg-accordion-trigger { display: flex; align-items: center; width: 100%; padding: 10px 0; cursor: pointer; background: none; border: none; font-family: inherit; font-size: 12px; text-align: left; gap: 8px; }
.gg-neo-brutalist-page .gg-accordion-trigger:hover { background: #f5f0eb; }
.gg-neo-brutalist-page .gg-accordion-label { width: 110px; min-width: 110px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-size: 11px; color: #000; }
.gg-neo-brutalist-page .gg-accordion-bar-track { flex: 1; height: 8px; background: #e0d6cc; position: relative; }
.gg-neo-brutalist-page .gg-accordion-bar-fill { height: 100%; background: #59473c; transition: width 0.3s; }
.gg-neo-brutalist-page .gg-accordion-score { width: 40px; min-width: 40px; text-align: center; font-weight: 700; font-size: 14px; color: #59473c; }
.gg-neo-brutalist-page .gg-accordion-arrow { width: 20px; min-width: 20px; text-align: center; font-size: 12px; color: #999; transition: transform 0.2s; }
.gg-neo-brutalist-page .gg-accordion-item.is-open .gg-accordion-arrow { transform: rotate(90deg); color: #59473c; }
.gg-neo-brutalist-page .gg-accordion-panel { max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out; }
.gg-neo-brutalist-page .gg-accordion-item.is-open .gg-accordion-panel { max-height: 500px; }
.gg-neo-brutalist-page .gg-accordion-content { padding: 0 0 14px 122px; font-size: 12px; line-height: 1.6; color: #59473c; }

/* Radar charts */
.gg-neo-brutalist-page .gg-radar-pair { display: flex; gap: 16px; margin-bottom: 24px; }
.gg-neo-brutalist-page .gg-radar-chart { flex: 1; border: 2px solid #000; background: #f5f0eb; padding: 12px 8px 12px; text-align: center; }
.gg-neo-brutalist-page .gg-radar-svg { width: 100%; height: auto; display: block; margin: 0 auto; }
.gg-neo-brutalist-page .gg-radar-label { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; color: #8c7568; margin-top: 4px; }
.gg-neo-brutalist-page .gg-radar-chart.is-drawn .gg-radar-polygon { stroke-dashoffset: 0 !important; fill-opacity: 0.2; transition: stroke-dashoffset 1.2s ease-out, fill-opacity 0.8s ease-out 0.6s; }
.gg-neo-brutalist-page .gg-radar-chart.is-drawn .gg-radar-dot { opacity: 1; transition: opacity 0.3s ease-out; }
.gg-neo-brutalist-page .gg-radar-hit:hover ~ .gg-radar-ring { opacity: 0; }
.gg-neo-brutalist-page .gg-radar-chart .gg-radar-ring { transition: opacity 0.2s; }

/* Verdict box hover */
.gg-neo-brutalist-page .gg-verdict-box { transition: transform 0.2s, border-color 0.2s; }
.gg-neo-brutalist-page .gg-verdict-box:hover { transform: translateY(-3px); }

/* Accordion item hover highlight */
.gg-neo-brutalist-page .gg-accordion-item { transition: background 0.15s; }
.gg-neo-brutalist-page .gg-accordion-item.is-highlighted { background: #f5f0eb; }

/* Ratings summary */
.gg-neo-brutalist-page .gg-ratings-summary { display: flex; gap: 16px; margin-bottom: 20px; }
.gg-neo-brutalist-page .gg-ratings-summary-card { flex: 1; border: 2px solid #000; padding: 16px; text-align: center; background: #f5f0eb; }
.gg-neo-brutalist-page .gg-ratings-summary-card:first-child { border-left: 4px solid #B7950B; }
.gg-neo-brutalist-page .gg-ratings-summary-card:last-child { border-left: 4px solid #1A8A82; }
.gg-neo-brutalist-page .gg-ratings-summary-score { font-size: 32px; font-weight: 700; color: #59473c; line-height: 1; }
.gg-neo-brutalist-page .gg-ratings-summary-max { font-size: 14px; color: #999; }
.gg-neo-brutalist-page .gg-ratings-summary-label { font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #666; margin-top: 4px; }

/* Verdict */
.gg-neo-brutalist-page .gg-verdict-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.gg-neo-brutalist-page .gg-verdict-box { border: 2px solid #000; padding: 16px; }
.gg-neo-brutalist-page .gg-verdict-box-title { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; }
.gg-neo-brutalist-page .gg-verdict-box--race { background: #f0ebe5; border-left: 4px solid #B7950B; }
.gg-neo-brutalist-page .gg-verdict-box--skip { background: #faf5f0; border-left: 4px solid #c4b5ab; }
.gg-neo-brutalist-page .gg-verdict-list { list-style: none; padding: 0; }
.gg-neo-brutalist-page .gg-verdict-list li { font-size: 12px; line-height: 1.6; color: #333; padding: 6px 0; padding-left: 18px; position: relative; }
.gg-neo-brutalist-page .gg-verdict-box--race .gg-verdict-list li::before { content: ''; position: absolute; left: 0; top: 12px; width: 6px; height: 6px; background: #1A8A82; }
.gg-neo-brutalist-page .gg-verdict-box--skip .gg-verdict-list li::before { content: ''; position: absolute; left: 0; top: 12px; width: 6px; height: 6px; background: #c4b5ab; }
.gg-neo-brutalist-page .gg-verdict-bottom-line { margin-top: 16px; padding: 16px; border: 2px solid #000; background: #f5f0eb; font-size: 13px; line-height: 1.6; color: #333; }
.gg-neo-brutalist-page .gg-verdict-bottom-line strong { color: #59473c; }

/* Pull quote */
.gg-neo-brutalist-page .gg-pullquote { margin: 32px 0; padding: 32px 40px; border-left: 6px solid #1A8A82; background: #000; }
.gg-neo-brutalist-page .gg-pullquote-text { font-size: 18px; font-weight: 700; line-height: 1.5; color: #fff; margin: 0 0 12px 0; quotes: none; }
.gg-neo-brutalist-page .gg-pullquote-attr { font-size: 11px; color: #8c7568; letter-spacing: 1px; text-transform: uppercase; }

/* Alternative links */
.gg-neo-brutalist-page .gg-alt-link { color: #1A8A82; text-decoration: underline; text-underline-offset: 2px; }
.gg-neo-brutalist-page .gg-alt-link:hover { color: #14695F; }

/* Buttons */
.gg-neo-brutalist-page .gg-btn { display: inline-block; padding: 10px 24px; font-family: 'Sometype Mono', monospace; font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; text-decoration: none; cursor: pointer; border: 2px solid #000; transition: background 0.15s, color 0.15s; }
.gg-neo-brutalist-page .gg-btn--primary { background: #59473c; color: #fff; }
.gg-neo-brutalist-page .gg-btn--primary:hover { background: #3d312a; }
.gg-neo-brutalist-page .gg-btn--secondary { background: #fff; color: #000; }
.gg-neo-brutalist-page .gg-btn--secondary:hover { background: #f5f0eb; }

/* Training */
.gg-neo-brutalist-page .gg-training-primary { border: 3px solid #000; background: #59473c; color: #fff; padding: 32px; margin-bottom: 16px; }
.gg-neo-brutalist-page .gg-training-primary h3 { font-size: 20px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 6px; color: #fff; }
.gg-neo-brutalist-page .gg-training-primary .gg-training-subtitle { font-size: 12px; color: #d4c5b9; margin-bottom: 20px; }
.gg-neo-brutalist-page .gg-training-bullets { list-style: none; padding: 0; margin-bottom: 24px; }
.gg-neo-brutalist-page .gg-training-bullets li { font-size: 13px; line-height: 1.6; color: #d4c5b9; padding: 6px 0; padding-left: 20px; position: relative; }
.gg-neo-brutalist-page .gg-training-bullets li::before { content: '\\2014'; position: absolute; left: 0; color: #d4c5b9; }
.gg-neo-brutalist-page .gg-training-primary .gg-btn { background: #fff; color: #59473c; border-color: #fff; }
.gg-neo-brutalist-page .gg-training-primary .gg-btn:hover { background: #f5f0eb; }
.gg-neo-brutalist-page .gg-training-divider { display: flex; align-items: center; gap: 16px; margin: 20px 0; }
.gg-neo-brutalist-page .gg-training-divider-line { flex: 1; height: 1px; background: #c4b5ab; }
.gg-neo-brutalist-page .gg-training-divider-text { font-size: 11px; font-weight: 700; color: #8c7568; letter-spacing: 3px; }
.gg-neo-brutalist-page .gg-training-secondary { border: 3px solid #000; background: #000; padding: 28px 32px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.gg-neo-brutalist-page .gg-training-secondary-text h4 { font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 6px; color: #fff; }
.gg-neo-brutalist-page .gg-training-secondary-text .gg-training-subtitle { font-size: 12px; color: #8c7568; margin: 0 0 8px 0; }
.gg-neo-brutalist-page .gg-training-secondary-text p { font-size: 12px; color: #8c7568; line-height: 1.5; margin: 0; }
.gg-neo-brutalist-page .gg-training-secondary .gg-btn { background: transparent; color: #fff; border-color: #fff; }
.gg-neo-brutalist-page .gg-training-secondary .gg-btn:hover { background: #fff; color: #000; }

/* Logistics */
.gg-neo-brutalist-page .gg-logistics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.gg-neo-brutalist-page .gg-logistics-item { border: 2px solid #000; padding: 12px; background: #f5f0eb; }
.gg-neo-brutalist-page .gg-logistics-item-label { font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #8c7568; margin-bottom: 4px; }
.gg-neo-brutalist-page .gg-logistics-item-value { font-size: 12px; color: #333; line-height: 1.5; }

/* Instagram carousel */
.gg-neo-brutalist-page .gg-instagram-body { padding: 0; }
.gg-neo-brutalist-page .gg-instagram-carousel { min-height: 200px; display: flex; align-items: center; justify-content: center; }
.gg-neo-brutalist-page .gg-instagram-placeholder { text-align: center; padding: 40px 20px; }
.gg-neo-brutalist-page .gg-instagram-icon { margin-bottom: 12px; }
.gg-neo-brutalist-page .gg-instagram-hashtag { font-size: 16px; font-weight: 700; color: #59473c; letter-spacing: 1px; margin: 0 0 4px 0; }
.gg-neo-brutalist-page .gg-instagram-cta-text { font-size: 12px; color: #8c7568; margin: 0; }

/* News ticker */
.gg-neo-brutalist-page .gg-news-ticker { background: #000; border: 3px solid #000; margin-bottom: 32px; display: flex; align-items: stretch; overflow: hidden; height: 48px; }
.gg-neo-brutalist-page .gg-news-ticker-label { background: #B7950B; color: #000; font-size: 10px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; padding: 0 16px; display: flex; align-items: center; white-space: nowrap; min-width: fit-content; border-right: 3px solid #000; }
.gg-neo-brutalist-page .gg-news-ticker-track { flex: 1; overflow: hidden; position: relative; display: flex; align-items: center; }
.gg-neo-brutalist-page .gg-news-ticker-content { display: flex; align-items: center; white-space: nowrap; animation: gg-ticker-scroll 80s linear infinite; padding-left: 100%; }
.gg-neo-brutalist-page .gg-news-ticker-content:hover { animation-play-state: paused; }
.gg-neo-brutalist-page .gg-news-ticker-item { display: inline-flex; align-items: center; gap: 6px; padding: 0 32px; }
.gg-neo-brutalist-page .gg-news-ticker-item a { color: #d4c5b9; text-decoration: none; font-size: 12px; font-weight: 700; letter-spacing: 0.5px; }
.gg-neo-brutalist-page .gg-news-ticker-item a:hover { color: #4ECDC4; }
.gg-neo-brutalist-page .gg-news-ticker-source { color: #8c7568; font-size: 10px; font-weight: 400; }
.gg-neo-brutalist-page .gg-news-ticker-sep { color: #1A8A82; font-size: 8px; margin: 0 8px; }
.gg-neo-brutalist-page .gg-news-ticker-loading { color: #8c7568; font-size: 11px; letter-spacing: 1px; padding-left: 16px; }
.gg-neo-brutalist-page .gg-news-ticker-empty { color: #8c7568; font-size: 11px; letter-spacing: 1px; padding-left: 16px; }
@keyframes gg-ticker-scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-100%); } }

/* Sticky CTA */
.gg-sticky-cta { position: fixed; bottom: 0; left: 0; right: 0; z-index: 200; background: #000; border-top: 3px solid #1A8A82; padding: 12px 24px; transform: translateY(100%); transition: transform 0.3s ease; }
.gg-sticky-cta.is-visible { transform: translateY(0); }
.gg-sticky-cta-inner { max-width: 960px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.gg-sticky-cta-name { font-family: 'Sometype Mono', monospace; font-size: 13px; font-weight: 700; color: #fff; text-transform: uppercase; letter-spacing: 1px; }
.gg-sticky-cta .gg-btn { font-family: 'Sometype Mono', monospace; background: #1A8A82; color: #fff; border: 2px solid #1A8A82; padding: 8px 20px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 2px; text-decoration: none; cursor: pointer; }
.gg-sticky-cta .gg-btn:hover { background: #14695F; border-color: #14695F; }

/* Scroll fade-in */
.gg-neo-brutalist-page .gg-fade-section { opacity: 0; transform: translateY(20px); transition: opacity 0.6s ease, transform 0.6s ease; }
.gg-neo-brutalist-page .gg-fade-section.is-visible { opacity: 1; transform: translateY(0); }

/* Email capture */
.gg-neo-brutalist-page .gg-email-capture { margin-bottom: 32px; border: 3px solid #000; background: #59473c; padding: 0; }
.gg-neo-brutalist-page .gg-email-capture-inner { padding: 32px; text-align: center; }
.gg-neo-brutalist-page .gg-email-capture-title { font-size: 14px; font-weight: 700; letter-spacing: 3px; color: #fff; margin: 0 0 8px 0; }
.gg-neo-brutalist-page .gg-email-capture-text { font-size: 12px; color: #d4c5b9; line-height: 1.6; margin: 0 0 20px 0; max-width: 500px; margin-left: auto; margin-right: auto; }
.gg-neo-brutalist-page .gg-email-capture iframe { max-width: 480px; margin: 0 auto; display: block; }

/* Countdown */
.gg-neo-brutalist-page .gg-countdown { border: 3px solid #1A8A82; background: #000; color: #fff; padding: 16px; text-align: center; font-size: 12px; font-weight: 700; letter-spacing: 3px; margin-bottom: 20px; }
.gg-neo-brutalist-page .gg-countdown-num { font-size: 32px; color: #1A8A82; display: block; line-height: 1.2; }

/* FAQ */
.gg-neo-brutalist-page .gg-faq-item { margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #e0d6cc; }
.gg-neo-brutalist-page .gg-faq-item:last-child { border-bottom: none; margin-bottom: 0; padding-bottom: 0; }
.gg-neo-brutalist-page .gg-faq-question { font-size: 13px; font-weight: 700; color: #000; margin: 0 0 8px 0; text-transform: none; letter-spacing: 0; }
.gg-neo-brutalist-page .gg-faq-answer { font-size: 12px; color: #555; line-height: 1.7; margin: 0; }

/* Similar races */
.gg-neo-brutalist-page .gg-similar-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.gg-neo-brutalist-page .gg-similar-card { display: block; border: 2px solid #000; padding: 16px; background: #f5f0eb; text-decoration: none; color: #000; transition: transform 0.15s, background 0.15s; position: relative; }
.gg-neo-brutalist-page .gg-similar-card:hover { transform: translate(-2px, -2px); background: #fff; }
.gg-neo-brutalist-page .gg-similar-card::after { content: ''; position: absolute; top: 4px; left: 4px; width: 100%; height: 100%; background: #000; z-index: -1; transition: top 0.15s, left 0.15s; }
.gg-neo-brutalist-page .gg-similar-card:hover::after { top: 6px; left: 6px; }
.gg-neo-brutalist-page .gg-similar-tier { display: inline-block; background: #000; color: #fff; padding: 2px 8px; font-size: 9px; font-weight: 700; letter-spacing: 2px; margin-bottom: 6px; }
.gg-neo-brutalist-page .gg-similar-name { display: block; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.gg-neo-brutalist-page .gg-similar-meta { display: block; font-size: 10px; color: #8c7568; letter-spacing: 0.5px; }

/* Footer */
.gg-neo-brutalist-page .gg-footer { background: #000; color: #d4c5b9; padding: 24px 20px; border: 3px solid #000; margin-bottom: 80px; font-size: 11px; text-align: center; letter-spacing: 0.5px; }
.gg-neo-brutalist-page .gg-footer a { color: #fff; text-decoration: none; }
.gg-neo-brutalist-page .gg-footer-disclaimer { color: #8c7568; line-height: 1.6; margin: 0; font-size: 10px; }

/* Responsive */
@media (max-width: 768px) {
  .gg-neo-brutalist-page .gg-hero { padding: 40px 20px; }
  .gg-neo-brutalist-page .gg-hero h1 { font-size: 28px; }
  .gg-neo-brutalist-page .gg-hero-score { position: static; margin-top: 16px; text-align: left; }
  .gg-neo-brutalist-page .gg-hero-score-number { font-size: 48px; }
  .gg-neo-brutalist-page .gg-stat-grid { grid-template-columns: repeat(2, 1fr); }
  .gg-neo-brutalist-page .gg-verdict-grid { grid-template-columns: 1fr; }
  .gg-neo-brutalist-page .gg-logistics-grid { grid-template-columns: 1fr; }
  .gg-neo-brutalist-page .gg-ratings-summary { flex-direction: column; }
  .gg-neo-brutalist-page .gg-radar-pair { flex-direction: column; }
  .gg-neo-brutalist-page .gg-accordion-label { width: 80px; min-width: 80px; font-size: 10px; }
  .gg-neo-brutalist-page .gg-accordion-content { padding-left: 0; }
  .gg-neo-brutalist-page .gg-training-secondary { flex-direction: column; text-align: center; }
  .gg-sticky-cta-name { display: none; }
  .gg-sticky-cta .gg-btn { width: 100%; text-align: center; }
  .gg-neo-brutalist-page .gg-toc { flex-direction: column; gap: 6px; }
  .gg-neo-brutalist-page .gg-map-embed iframe { height: 250px; }
  .gg-neo-brutalist-page .gg-pullquote { padding: 24px 20px; }
  .gg-neo-brutalist-page .gg-pullquote-text { font-size: 15px; }
  .gg-neo-brutalist-page .gg-news-ticker-label { font-size: 9px; padding: 0 10px; letter-spacing: 1px; }
  .gg-neo-brutalist-page .gg-email-capture iframe { height: 120px; }
  .gg-neo-brutalist-page .gg-similar-grid { grid-template-columns: 1fr; }
  .gg-neo-brutalist-page .gg-countdown-num { font-size: 24px; }
}
</style>'''


# ── Page Assembly ──────────────────────────────────────────────

def generate_page(rd: dict, race_index: list = None) -> str:
    """Generate complete HTML page from normalized race data."""
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

    jsonld_html = '\n'.join(
        f'<script type="application/ld+json">\n{j}\n</script>'
        for j in jsonld_parts
    )

    # Build sections
    hero = build_hero(rd)
    toc = build_toc()
    course_overview = build_course_overview(rd)
    history = build_history(rd)
    pullquote = build_pullquote(rd)
    course_route = build_course_route(rd)
    instagram = build_instagram_section(rd)
    ratings = build_ratings(rd)
    verdict = build_verdict(rd)
    email_capture = build_email_capture(rd)
    visible_faq = build_visible_faq(rd)
    news = build_news_section(rd)
    training = build_training(rd, q_url)
    logistics_sec = build_logistics_section(rd)
    similar = build_similar_races(rd, race_index)
    footer = build_footer()
    sticky_cta = build_sticky_cta(rd['name'], q_url)
    inline_js = build_inline_js()
    css = get_page_css()

    # Section order
    content_sections = []
    for section in [course_overview, history, pullquote, course_route, instagram,
                    ratings, verdict, email_capture, visible_faq, news,
                    training, logistics_sec, similar]:
        if section:
            content_sections.append(section)

    content = '\n\n  '.join(content_sections)

    # Open Graph meta tags
    og_image_url = f"{SITE_BASE_URL}/og/{rd['slug']}.jpg"
    og_tags = f'''<meta property="og:title" content="{esc(rd['name'])} — Gravel God Race Profile">
  <meta property="og:description" content="{esc(rd['tagline'])}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{esc(og_image_url)}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{esc(rd['name'])} — Gravel God Race Profile">
  <meta name="twitter:description" content="{esc(rd['tagline'])}">
  <meta name="twitter:image" content="{esc(og_image_url)}">'''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(rd["name"])} — Gravel God Race Profile</title>
  <meta name="description" content="{esc(rd["tagline"])}">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Sometype+Mono:wght@400;700&display=swap">
  {og_tags}
  {jsonld_html}
  {css}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {hero}

  {toc}

  {content}

  {footer}
</div>

{sticky_cta}
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
    return normalize_race_data(raw)


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

        for i, f in enumerate(files, 1):
            slug = f.stem.replace('-data', '')
            try:
                rd = load_race_data(f)
                page_html = generate_page(rd, race_index)
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
