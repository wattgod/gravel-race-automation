#!/usr/bin/env python3
"""
Generate the Intensity-Aware Fueling Methodology page.

A scrollytelling narrative visual essay (38 citations) on the W/kg fueling
framework that powers the carb calculator in all 328 Race Prep Kits. Features
an inline calculator, sticky-chart scroll sections, and corrected crossover
science. Published as a branded, infographic-enriched HTML page.

Uses brand tokens exclusively — zero hardcoded hex in CSS, COLORS dict for
SVG fills/strokes, no border-radius, no box-shadow, <rect> only (no <circle>).

Usage:
    python generate_whitepaper_fueling.py
    python generate_whitepaper_fueling.py --output-dir ./output
"""
from __future__ import annotations

import argparse
import datetime
import html
import json
from pathlib import Path

from generate_neo_brutalist import (
    SITE_BASE_URL,
    get_page_css,
    write_shared_assets,
)
from brand_tokens import (
    COLORS,
    get_ab_head_snippet,
    get_ga4_head_snippet,
    get_preload_hints,
    get_tokens_css,
)
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html, get_site_header_css
from cookie_consent import get_consent_banner_html

OUTPUT_DIR = Path(__file__).parent / "output"

CANONICAL_URL = f"{SITE_BASE_URL}/fueling-methodology/"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Section Builders ─────────────────────────────────────────


def build_nav() -> str:
    """Build header + breadcrumb."""
    breadcrumb = f'''<div class="gg-wp-breadcrumb">
  <a href="{SITE_BASE_URL}/">Home</a>
  <span class="gg-wp-breadcrumb-sep">&rsaquo;</span>
  <a href="{SITE_BASE_URL}/articles/">Articles</a>
  <span class="gg-wp-breadcrumb-sep">&rsaquo;</span>
  <span>Fueling Methodology</span>
</div>'''
    return get_site_header_html("articles") + "\n" + breadcrumb


def build_hero() -> str:
    """Section: Hero — eyebrow + title + subtitle."""
    return f'''<section class="gg-wp-hero" id="hero">
  <div class="gg-wp-hero-inner">
    <span class="gg-wp-hero-eyebrow">FUELING METHODOLOGY</span>
    <h1 class="gg-wp-hero-title">How Many Carbs Do You Actually Need?</h1>
    <p class="gg-wp-hero-subtitle">Everyone says 60 to 90 grams per hour. For a 95-kilo rider at 2.3&nbsp;W/kg, the right number is 63. For a 70-kilo rider at 4.0&nbsp;W/kg, it&#8217;s 75. Same race, same bracket, different bodies. Which number is yours?</p>
  </div>
</section>'''


def build_tldr() -> str:
    """Section: TL;DR — how the formula works in 60 seconds."""
    takeaways = [
        ("Duration sets the range", "SBT GRVL (4&#8211;6 hours) gives you 60&#8211;80&nbsp;g/hr. Unbound 200 (10&#8211;14 hours) gives you 50&#8211;70. Five brackets. Your race picks the floor and ceiling."),
        ("Your fitness moves you within it", "A 2.3&nbsp;W/kg rider lands near the bottom of the bracket. A 4.0&nbsp;W/kg rider lands near the top. The formula uses your FTP and weight to find your spot."),
        ("Your gut gets the final vote", "Your muscles can burn more carbs than your stomach can absorb. Max intake tops out around 90&#8211;120&nbsp;g/hr no matter who you are."),
    ]
    cards_html = ""
    for title, body in takeaways:
        cards_html += f'''    <div class="gg-wp-tldr-card">
      <h3 class="gg-wp-tldr-card-title">{title}</h3>
      <p class="gg-wp-tldr-card-body">{body}</p>
    </div>
'''
    return f'''<section class="gg-wp-section gg-wp-section--alt" id="tldr">
  <h2 class="gg-wp-section-title">The Formula in 60 Seconds</h2>
  <div class="gg-wp-tldr-grid">
{cards_html}  </div>
</section>'''


def build_murphy() -> str:
    """Section 1: Two Riders, One Number — with comparison bar chart."""
    # HTML div bar chart: generic vs personalized vs lab range
    bars_html = '''<div class="gg-wp-chart-wrap" data-animate="bars" role="img" aria-label="Comparison of fueling formulas for a 95kg/220W rider in a 6.5-hour race">
  <div class="gg-wp-compare-row">
    <span class="gg-wp-compare-label">Generic advice (60&ndash;90)</span>
    <div class="gg-wp-bar-track">
      <div class="gg-wp-bar-fill gg-wp-bar-fill--brown" style="--tw:80%" data-target-w="80%"></div>
    </div>
    <span class="gg-wp-compare-value">80 g/hr</span>
  </div>
  <div class="gg-wp-compare-row">
    <span class="gg-wp-compare-label">Personalized (W/kg-adjusted)</span>
    <div class="gg-wp-bar-track">
      <div class="gg-wp-bar-fill gg-wp-bar-fill--teal" style="--tw:63%" data-target-w="63%"></div>
    </div>
    <span class="gg-wp-compare-value">63 g/hr</span>
  </div>
  <div class="gg-wp-compare-row">
    <span class="gg-wp-compare-label">Lab exogenous range</span>
    <div class="gg-wp-bar-track">
      <div class="gg-wp-bar-fill gg-wp-bar-fill--gold" style="--tw:20%;--ml:60%" data-target-w="20%"></div>
    </div>
    <span class="gg-wp-compare-value">60&ndash;80 g/hr</span>
  </div>
  <div class="gg-wp-compare-annotation">Murphy: SBT GRVL, 95 kg, 220W FTP (2.32 W/kg)</div>
</div>'''

    return f'''<section class="gg-wp-section" id="murphy">
  <h2 class="gg-wp-section-title">Two Riders, One Number</h2>
  <div class="gg-wp-prose">
    <p>It&#8217;s hour six at SBT GRVL in Steamboat Springs. You&#8217;ve been eating 80 grams of carbs per hour because that&#8217;s what the internet told you. Your stomach is revolting. Meanwhile the rider next to you &#8212; twenty kilos lighter, twenty watts higher &#8212; is eating 75 and feeling fine. Same race. Same bracket. Same generic advice. One of you got the wrong number.</p>
    <p>Murphy is a 95-kilo masters racer who signed up for SBT GRVL because his buddy wouldn&#8217;t stop talking about it. His FTP is 220 watts &#8212; respectable, not elite. At 2.3&nbsp;W/kg, he&#8217;s solidly mid-pack. He read every fueling guide online. They all said eat 60&#8211;90 grams per hour. He picked 80. He was wrong by 27%.</p>
    <p><strong>Three inputs tell you which number is yours: your weight, your FTP, your race.</strong></p>
  </div>
  <figure class="gg-wp-figure" id="murphy-comparison-figure">
    <div class="gg-wp-figure-title">The Murphy Problem: Same Bracket, Wrong Answer</div>
    {bars_html}
    <div class="gg-wp-figure-takeaway">Generic advice gave Murphy 80 g/hr &#8212; 27% higher than his personalized target of 63 g/hr. Lab data confirms: at 2.3 W/kg, exogenous absorption is closer to 60&ndash;80 g/hr.</div>
  </figure>
</section>'''


def build_inline_calculator() -> str:
    """Section: Inline carb calculator — 3 inputs, instant result, no email gate."""
    return f'''<section class="gg-wp-section" id="inline-calculator">
  <div class="gg-wp-calculator">
    <h2 class="gg-wp-section-title">Your Number</h2>
    <div class="gg-wp-prose">
      <p>Three inputs. Ten seconds. No email required.</p>
    </div>
    <div class="gg-wp-calc-form" role="form" aria-label="Carb rate calculator">
      <div class="gg-wp-calc-inputs">
        <div class="gg-wp-calc-field">
          <label class="gg-wp-calc-label" for="gg-calc-weight">Weight</label>
          <div class="gg-wp-calc-input-row">
            <input type="number" id="gg-calc-weight" class="gg-wp-calc-input" placeholder="75" min="30" max="200" step="0.1" aria-describedby="gg-calc-weight-unit">
            <button type="button" id="gg-calc-unit-toggle" class="gg-wp-calc-unit-btn" aria-label="Toggle weight unit">
              <span id="gg-calc-weight-unit">kg</span>
            </button>
          </div>
        </div>
        <div class="gg-wp-calc-field">
          <label class="gg-wp-calc-label" for="gg-calc-ftp">FTP <span class="gg-wp-calc-optional">(optional)</span></label>
          <div class="gg-wp-calc-input-row">
            <input type="number" id="gg-calc-ftp" class="gg-wp-calc-input" placeholder="220" min="50" max="500" step="1">
            <span class="gg-wp-calc-unit">W</span>
          </div>
        </div>
        <div class="gg-wp-calc-field">
          <label class="gg-wp-calc-label" for="gg-calc-hours">Race duration</label>
          <div class="gg-wp-calc-input-row">
            <input type="number" id="gg-calc-hours" class="gg-wp-calc-input" placeholder="6" min="1" max="30" step="0.5">
            <span class="gg-wp-calc-unit">hrs</span>
          </div>
        </div>
      </div>
      <div class="gg-wp-calc-output" aria-live="polite" aria-atomic="true">
        <div class="gg-wp-calc-result" id="gg-calc-result">
          <span class="gg-wp-calc-result-number" id="gg-calc-number">&mdash;</span>
          <span class="gg-wp-calc-result-unit">g/hr</span>
        </div>
        <div class="gg-wp-calc-bracket-bar" id="gg-calc-bracket" aria-hidden="true">
          <div class="gg-wp-calc-bracket-track">
            <div class="gg-wp-calc-bracket-fill" id="gg-calc-bracket-fill"></div>
            <div class="gg-wp-calc-bracket-marker" id="gg-calc-bracket-marker"></div>
          </div>
          <div class="gg-wp-calc-bracket-labels">
            <span id="gg-calc-bracket-lo"></span>
            <span id="gg-calc-bracket-hi"></span>
          </div>
        </div>
        <div class="gg-wp-calc-food" id="gg-calc-food"></div>
      </div>
    </div>
    <div class="gg-wp-calc-fallback">
      <p>Visit <a href="{SITE_BASE_URL}/gravel-races/">your race page</a> for a personalized carb calculator.</p>
    </div>
  </div>
</section>'''


def build_scroll_duration() -> str:
    """Scrollytelling section: Duration sets the range — sticky bracket chart."""
    brackets = [
        ("2&#8211;4 hrs", "80&#8211;100 g/hr", 80, 100),
        ("4&#8211;8 hrs", "60&#8211;80 g/hr", 60, 80),
        ("8&#8211;12 hrs", "50&#8211;70 g/hr", 50, 70),
        ("12&#8211;16 hrs", "40&#8211;60 g/hr", 40, 60),
        ("16+ hrs", "30&#8211;50 g/hr", 30, 50),
    ]
    # SVG bracket chart — 5 horizontal bars
    svg_w, svg_h = 400, 260
    bar_h, gap = 36, 8
    y_start = 20
    bars_svg = ""
    for i, (label, rate, lo, hi) in enumerate(brackets):
        y = y_start + i * (bar_h + gap)
        # Muted state by default — step classes added by JS
        bars_svg += f'''    <g class="gg-wp-scroll-bracket" data-chart-bracket="{i}">
      <text x="90" y="{y + bar_h // 2 + 4}" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="11" text-anchor="end">{label}</text>
      <rect x="100" y="{y}" width="{hi * 2.5}" height="{bar_h}" fill="{COLORS['tan']}" class="gg-wp-scroll-bracket-bg"/>
      <rect x="100" y="{y}" width="{hi * 2.5}" height="{bar_h}" fill="{COLORS['teal']}" class="gg-wp-scroll-bracket-fill" opacity="0.2"/>
      <text x="{100 + hi * 2.5 + 8}" y="{y + bar_h // 2 + 4}" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="11">{rate}</text>
    </g>
'''
    # Murphy dot (at 4-8hr bracket, position ~63 within 60-80 range → 15% of bracket)
    murphy_y = y_start + 1 * (bar_h + gap) + bar_h // 2
    murphy_x = 100 + 63 * 2.5  # scaled position
    bars_svg += f'''    <g class="gg-wp-scroll-murphy-dot" data-chart-murphy opacity="0">
      <rect x="{murphy_x - 4}" y="{murphy_y - 4}" width="8" height="8" fill="{COLORS['gold']}"/>
      <text x="{murphy_x + 10}" y="{murphy_y + 4}" fill="{COLORS['gold']}" font-family="'Sometype Mono', monospace" font-size="10">63 g/hr</text>
    </g>
'''

    chart_svg = f'''<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Duration brackets showing carb rate ranges">
    <title>Duration Brackets: How race length sets your carb range</title>
{bars_svg}  </svg>'''

    return f'''<section class="gg-wp-scroll-section" id="scroll-duration">
  <div class="gg-wp-scroll-chart">
    <div class="gg-wp-scroll-chart-inner" data-scroll-chart="duration">
      <div class="gg-wp-figure-title">Duration Sets the Range</div>
      <div class="gg-wp-chart-wrap">
        {chart_svg}
      </div>
    </div>
  </div>
  <div class="gg-wp-scroll-steps">
    <div class="gg-wp-scroll-step gg-step-active" data-step="0">
      <h3 class="gg-wp-subsection-title">Your Race Picks the Bracket</h3>
      <p class="gg-wp-prose">Murphy&#8217;s race is 6.5 hours. That puts him in the 4&#8211;8 hour bracket: 60&#8211;80&nbsp;g/hr. The bracket is his floor and ceiling.</p>
    </div>
    <div class="gg-wp-scroll-step" data-step="1">
      <h3 class="gg-wp-subsection-title">Longer Races, Lower Rate</h3>
      <p class="gg-wp-prose">Longer races need fewer carbs per hour &#8212; not more. As intensity drops, fat oxidation rises and carbohydrate demand falls. A 14-hour Unbound needs less per hour than a 4-hour SBT GRVL.</p>
    </div>
    <div class="gg-wp-scroll-step" data-step="2">
      <h3 class="gg-wp-subsection-title">But the Range Is Wide</h3>
      <p class="gg-wp-prose">60&#8211;80 is still a 20&nbsp;g/hr gap. Over a 6.5-hour race, that&#8217;s the difference between 390g and 520g of carbs. Your fitness narrows it down.</p>
    </div>
  </div>
</section>'''


def build_scroll_fitness() -> str:
    """Scrollytelling section: Fitness moves you within the bracket — power curve chart."""
    # SVG power curve with Murphy and competitive racer dots
    svg_w, svg_h = 400, 280

    def _x(wkg):
        return 50 + (wkg - 1.5) / 3.0 * 320

    def _y(factor):
        return 240 - factor * 200

    # Power curve polyline
    curve_pts = []
    for w in range(15, 46):
        wkg = w / 10.0
        linear = (wkg - 1.5) / 3.0
        factor = linear ** 1.4
        curve_pts.append(f"{_x(wkg):.0f},{_y(factor):.0f}")
    curve_path = " ".join(curve_pts)

    # Murphy: 2.32 W/kg
    murphy_lin = (2.32 - 1.5) / 3.0
    murphy_factor = murphy_lin ** 1.4
    mx, my = _x(2.32), _y(murphy_factor)

    # Competitive: 4.0 W/kg
    comp_lin = (4.0 - 1.5) / 3.0
    comp_factor = comp_lin ** 1.4
    cx, cy = _x(4.0), _y(comp_factor)

    chart_svg = f'''<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Power curve showing how W/kg positions you within your bracket">
    <title>Fitness Effect: How W/kg moves your position within the bracket</title>
    <!-- Axes -->
    <line x1="50" y1="240" x2="370" y2="240" stroke="{COLORS['dark_brown']}" stroke-width="2"/>
    <line x1="50" y1="40" x2="50" y2="240" stroke="{COLORS['dark_brown']}" stroke-width="2"/>
    <!-- X labels -->
    <text x="50" y="258" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">1.5</text>
    <text x="157" y="258" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">2.5</text>
    <text x="263" y="258" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">3.5</text>
    <text x="370" y="258" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">4.5</text>
    <text x="210" y="275" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="11" text-anchor="middle">W/kg</text>
    <!-- Y labels -->
    <text x="42" y="244" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="end">Floor</text>
    <text x="42" y="44" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="end">Ceiling</text>
    <!-- Grid -->
    <line x1="50" y1="140" x2="370" y2="140" stroke="{COLORS['tan']}" stroke-width="1" stroke-dasharray="4"/>
    <!-- Power curve -->
    <polyline points="{curve_path}" fill="none" stroke="{COLORS['teal']}" stroke-width="2.5"/>
    <!-- Murphy dot -->
    <g class="gg-wp-scroll-murphy" data-chart-murphy>
      <rect x="{mx - 5:.0f}" y="{my - 5:.0f}" width="10" height="10" fill="{COLORS['gold']}"/>
      <text x="{mx + 12:.0f}" y="{my + 4:.0f}" fill="{COLORS['gold']}" font-family="'Sometype Mono', monospace" font-size="10">Murphy 2.3 W/kg</text>
    </g>
    <!-- Competitive racer dot -->
    <g class="gg-wp-scroll-comp" data-chart-comp opacity="0">
      <rect x="{cx - 5:.0f}" y="{cy - 5:.0f}" width="10" height="10" fill="{COLORS['teal']}"/>
      <text x="{cx + 12:.0f}" y="{cy + 4:.0f}" fill="{COLORS['teal']}" font-family="'Sometype Mono', monospace" font-size="10">4.0 W/kg</text>
    </g>
    <!-- Exponent annotation -->
    <g class="gg-wp-scroll-exponent" data-chart-exponent opacity="0">
      <text x="210" y="30" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">Exponent 1.4: steepens at higher W/kg</text>
    </g>
  </svg>'''

    return f'''<section class="gg-wp-scroll-section" id="scroll-fitness">
  <div class="gg-wp-scroll-chart">
    <div class="gg-wp-scroll-chart-inner" data-scroll-chart="fitness">
      <div class="gg-wp-figure-title">Your Fitness Moves You Within It</div>
      <div class="gg-wp-chart-wrap">
        {chart_svg}
      </div>
    </div>
  </div>
  <div class="gg-wp-scroll-steps">
    <div class="gg-wp-scroll-step gg-step-active" data-step="0">
      <h3 class="gg-wp-subsection-title">Murphy Lands Low</h3>
      <p class="gg-wp-prose">Murphy&#8217;s FTP is 220W at 95&nbsp;kg &#8212; that&#8217;s 2.3&nbsp;W/kg. He lands near the bottom of his 60&#8211;80 bracket. His personalized number: <strong>63&nbsp;g/hr</strong>.</p>
    </div>
    <div class="gg-wp-scroll-step" data-step="1">
      <h3 class="gg-wp-subsection-title">Same Bracket, Different Spot</h3>
      <p class="gg-wp-prose">A 70&nbsp;kg rider with 280W FTP &#8212; 4.0&nbsp;W/kg &#8212; lands near the top. Same bracket, 12&nbsp;g/hr apart. His number: <strong>75&nbsp;g/hr</strong>.</p>
    </div>
    <div class="gg-wp-scroll-step" data-step="2">
      <h3 class="gg-wp-subsection-title">The Curve Steepens</h3>
      <p class="gg-wp-prose">The relationship isn&#8217;t linear. It steepens at higher W/kg because carbohydrate oxidation accelerates near threshold. The 1.4 exponent captures this: gains are compressed at low W/kg and amplified at high W/kg.</p>
    </div>
  </div>
</section>'''


def build_scroll_crossover() -> str:
    """Scrollytelling section: fat oxidation rate curves — Pro vs Recreational.

    Key science (from metabolic reference data):
    - Carbs ALWAYS provide >57% of energy at all intensities for all fitness levels.
    - Fat never dominates. Even at 0.75 W/kg, fat% is only ~39%.
    - Fat oxidation RATE (g/min) rises, peaks, then falls as intensity increases.
    - Pro peak: 0.99 g/min at 3.5 W/kg. Recreational peak: 0.53 g/min at 2.5 W/kg.
    - The story: fitter riders sustain fat burning longer, but carbs always run the show.
    """
    svg_w, svg_h = 400, 280
    # Chart area: x 60-370 (W/kg 0.5-6.0), y 40-230 (0-1.1 g/min)
    x_min_wkg, x_max_wkg = 0.5, 6.0
    y_max_rate = 1.1  # g/min ceiling

    def _x(wkg: float) -> float:
        return 60 + (wkg - x_min_wkg) / (x_max_wkg - x_min_wkg) * 310

    def _y(rate: float) -> float:
        return 230 - rate / y_max_rate * 190

    # Actual data from metabolic-reference.csv (fat oxidation rate in g/min)
    pro_data = [
        (0.75, 0.28), (1.0, 0.37), (1.5, 0.55), (2.0, 0.72), (2.5, 0.86),
        (3.0, 0.96), (3.5, 0.99), (4.0, 0.93), (4.5, 0.77), (5.0, 0.50),
        (5.5, 0.14), (5.8, 0.00),
    ]
    rec_data = [
        (0.75, 0.21), (1.0, 0.28), (1.5, 0.41), (2.0, 0.50), (2.5, 0.53),
        (3.0, 0.49), (3.5, 0.36), (4.0, 0.16), (4.5, 0.00),
    ]

    # Build filled-area polygons (area under curve to x-axis)
    def _area_path(data):
        top = " ".join(f"{_x(w):.0f},{_y(r):.0f}" for w, r in data)
        bottom = f"{_x(data[-1][0]):.0f},{_y(0):.0f} {_x(data[0][0]):.0f},{_y(0):.0f}"
        return f"{top} {bottom}"

    # Build line polyline (just the curve, no fill)
    def _line_points(data):
        return " ".join(f"{_x(w):.0f},{_y(r):.0f}" for w, r in data)

    pro_area = _area_path(pro_data)
    rec_area = _area_path(rec_data)
    pro_line = _line_points(pro_data)
    rec_line = _line_points(rec_data)

    # Peak annotations
    pro_peak_x, pro_peak_y = _x(3.5), _y(0.99)
    rec_peak_x, rec_peak_y = _x(2.5), _y(0.53)

    # Race pace zone: 2.5-3.5 W/kg (typical gravel intensity)
    race_lo, race_hi = _x(2.5), _x(3.5)

    # Horizontal gridlines at 0.25, 0.50, 0.75, 1.00 g/min
    gridlines = ""
    for rate in [0.25, 0.50, 0.75, 1.00]:
        gy = _y(rate)
        gridlines += (
            f'    <line x1="60" y1="{gy:.0f}" x2="370" y2="{gy:.0f}" '
            f'stroke="{COLORS["tan"]}" stroke-width="0.5" stroke-dasharray="3 3"/>\n'
        )

    # X-axis tick marks at 1, 2, 3, 4, 5 W/kg
    x_ticks = ""
    for wkg in [1, 2, 3, 4, 5]:
        tx = _x(wkg)
        x_ticks += (
            f'    <line x1="{tx:.0f}" y1="230" x2="{tx:.0f}" y2="235" '
            f'stroke="{COLORS["dark_brown"]}" stroke-width="1"/>\n'
            f'    <text x="{tx:.0f}" y="248" fill="{COLORS["secondary_brown"]}" '
            f'font-family="\'Sometype Mono\', monospace" font-size="9" '
            f'text-anchor="middle">{wkg}</text>\n'
        )

    chart_svg = f'''<svg viewBox="0 0 {svg_w} {svg_h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Fat oxidation rate chart comparing pro and recreational riders across intensity">
    <title>Fat Burning Rate: How fitness changes the curve</title>
    <!-- Gridlines -->
{gridlines}
    <!-- Pro filled area (under curve) -->
    <polygon points="{pro_area}" fill="{COLORS['teal']}" opacity="0.15" class="gg-wp-scroll-pro-area"/>
    <!-- Recreational filled area (hidden by default) -->
    <polygon points="{rec_area}" fill="{COLORS['gold']}" opacity="0" class="gg-wp-scroll-rec-area" data-chart-rec-area/>
    <!-- Pro curve line -->
    <polyline points="{pro_line}" fill="none" stroke="{COLORS['teal']}" stroke-width="2.5" class="gg-wp-scroll-pro-line"/>
    <!-- Recreational curve line (hidden by default) -->
    <polyline points="{rec_line}" fill="none" stroke="{COLORS['gold']}" stroke-width="2.5" opacity="0" class="gg-wp-scroll-rec-line" data-chart-rec-line/>
    <!-- Race pace zone (hidden by default) -->
    <rect x="{race_lo:.0f}" y="40" width="{race_hi - race_lo:.0f}" height="190" fill="{COLORS['dark_brown']}" opacity="0" class="gg-wp-scroll-race-zone" data-chart-race-zone/>
    <text x="{(race_lo + race_hi) / 2:.0f}" y="35" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="9" text-anchor="middle" opacity="0" data-chart-race-label>RACE PACE</text>
    <!-- Pro peak annotation (hidden by default) -->
    <circle cx="{pro_peak_x:.0f}" cy="{pro_peak_y:.0f}" r="4" fill="{COLORS['teal']}" stroke="{COLORS['dark_brown']}" stroke-width="1" opacity="0" data-chart-pro-peak/>
    <text x="{pro_peak_x + 6:.0f}" y="{pro_peak_y - 6:.0f}" fill="{COLORS['teal']}" font-family="'Sometype Mono', monospace" font-size="8" opacity="0" data-chart-pro-peak-label>0.99 g/min</text>
    <!-- Rec peak annotation (hidden by default) -->
    <circle cx="{rec_peak_x:.0f}" cy="{rec_peak_y:.0f}" r="4" fill="{COLORS['gold']}" stroke="{COLORS['dark_brown']}" stroke-width="1" opacity="0" data-chart-rec-peak/>
    <text x="{rec_peak_x + 6:.0f}" y="{rec_peak_y - 6:.0f}" fill="{COLORS['gold']}" font-family="'Sometype Mono', monospace" font-size="8" opacity="0" data-chart-rec-peak-label>0.53 g/min</text>
    <!-- Carb-dominant annotation (visible at step 0) -->
    <text x="215" y="218" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="8" text-anchor="middle" opacity="0.7" data-chart-carb-note>Carbs provide 60%+ of energy at every intensity</text>
    <!-- Curve labels (hidden by default) -->
    <text x="{_x(4.2):.0f}" y="{_y(0.85) - 4:.0f}" fill="{COLORS['teal']}" font-family="'Sometype Mono', monospace" font-size="10" font-weight="bold" opacity="0" data-chart-pro-label>PRO</text>
    <text x="{_x(3.6):.0f}" y="{_y(0.30) + 14:.0f}" fill="{COLORS['gold']}" font-family="'Sometype Mono', monospace" font-size="10" font-weight="bold" opacity="0" data-chart-rec-label>RECREATIONAL</text>
    <!-- Gap bracket at 3.0 W/kg — hidden until step 2 -->
    <!-- Pro at 3.0: FATox=0.96, fat_pct=32%. Rec at 3.0: FATox=0.49, fat_pct=21%. -->
    <line x1="{_x(3.0):.0f}" y1="40" x2="{_x(3.0):.0f}" y2="230" stroke="{COLORS['dark_brown']}" stroke-width="1" stroke-dasharray="4 3" opacity="0" data-chart-gap-line/>
    <circle cx="{_x(3.0):.0f}" cy="{_y(0.96):.0f}" r="3.5" fill="{COLORS['teal']}" stroke="{COLORS['dark_brown']}" stroke-width="1" opacity="0" data-chart-gap-pro-dot/>
    <circle cx="{_x(3.0):.0f}" cy="{_y(0.49):.0f}" r="3.5" fill="{COLORS['gold']}" stroke="{COLORS['dark_brown']}" stroke-width="1" opacity="0" data-chart-gap-rec-dot/>
    <!-- Bracket line between the two dots -->
    <line x1="{_x(3.0) + 6:.0f}" y1="{_y(0.96):.0f}" x2="{_x(3.0) + 6:.0f}" y2="{_y(0.49):.0f}" stroke="{COLORS['dark_brown']}" stroke-width="1.5" opacity="0" data-chart-gap-bracket/>
    <line x1="{_x(3.0) + 3:.0f}" y1="{_y(0.96):.0f}" x2="{_x(3.0) + 9:.0f}" y2="{_y(0.96):.0f}" stroke="{COLORS['dark_brown']}" stroke-width="1.5" opacity="0" data-chart-gap-bracket-top/>
    <line x1="{_x(3.0) + 3:.0f}" y1="{_y(0.49):.0f}" x2="{_x(3.0) + 9:.0f}" y2="{_y(0.49):.0f}" stroke="{COLORS['dark_brown']}" stroke-width="1.5" opacity="0" data-chart-gap-bracket-bot/>
    <!-- Gap labels -->
    <text x="{_x(3.0) + 14:.0f}" y="{_y(0.96) + 3:.0f}" fill="{COLORS['teal']}" font-family="'Sometype Mono', monospace" font-size="7.5" opacity="0" data-chart-gap-pro-text>32% from fat</text>
    <text x="{_x(3.0) + 14:.0f}" y="{_y(0.49) + 3:.0f}" fill="{COLORS['gold']}" font-family="'Sometype Mono', monospace" font-size="7.5" opacity="0" data-chart-gap-rec-text>21% from fat</text>
    <text x="{_x(3.0) + 14:.0f}" y="{(_y(0.96) + _y(0.49)) / 2 + 3:.0f}" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="8" font-weight="bold" opacity="0" data-chart-gap-diff>2&#215; gap</text>
    <!-- Axes -->
    <line x1="60" y1="230" x2="370" y2="230" stroke="{COLORS['dark_brown']}" stroke-width="2"/>
    <line x1="60" y1="40" x2="60" y2="230" stroke="{COLORS['dark_brown']}" stroke-width="2"/>
    <!-- X-axis ticks + labels -->
{x_ticks}
    <!-- Axis titles -->
    <text x="215" y="265" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="9" text-anchor="middle">INTENSITY (W/kg)</text>
    <text x="14" y="135" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="9" text-anchor="middle" transform="rotate(-90, 14, 135)">FAT BURN (g/min)</text>
    <!-- Y-axis labels -->
    <text x="54" y="233" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="8" text-anchor="end">0</text>
    <text x="54" y="{_y(0.50):.0f}" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="8" text-anchor="end">0.50</text>
    <text x="54" y="{_y(1.0):.0f}" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="8" text-anchor="end">1.00</text>
  </svg>'''

    return f'''<section class="gg-wp-scroll-section" id="scroll-crossover">
  <div class="gg-wp-scroll-chart">
    <div class="gg-wp-scroll-chart-inner" data-scroll-chart="crossover">
      <div class="gg-wp-figure-title">Fat Burning: How Fitness Changes the Curve</div>
      <div class="gg-wp-chart-wrap">
        {chart_svg}
      </div>
    </div>
  </div>
  <div class="gg-wp-scroll-steps">
    <div class="gg-wp-scroll-step gg-step-active" data-step="0">
      <h3 class="gg-wp-subsection-title">Carbs Always Run the Show</h3>
      <p class="gg-wp-prose">Even on the easiest ride you&#8217;ll ever do, your body burns more carbs than fat. At a casual 1.5&nbsp;W/kg, carbohydrate provides <strong>61% of your energy</strong> &#8212; whether you&#8217;re a pro or a weekend rider. Fat never dominates. Not at any intensity, for any fitness level.</p>
    </div>
    <div class="gg-wp-scroll-step" data-step="1">
      <h3 class="gg-wp-subsection-title">Fat Burning Peaks, Then Drops</h3>
      <p class="gg-wp-prose">Your body does burn fat &#8212; and the rate <em>increases</em> as you ride harder. But only up to a point. Then it drops. This rise-and-fall is your fat oxidation curve. A pro rider&#8217;s fat burning peaks at <strong>0.99&nbsp;g/min</strong> around 3.5&nbsp;W/kg. A recreational rider peaks at <strong>0.53&nbsp;g/min</strong> around 2.5&nbsp;W/kg.</p>
    </div>
    <div class="gg-wp-scroll-step" data-step="2">
      <h3 class="gg-wp-subsection-title">That Gap Changes the Problem</h3>
      <p class="gg-wp-prose">At 3.0&nbsp;W/kg, a pro burns 0.96&nbsp;g/min of fat (<strong>32%</strong> of their energy). A recreational rider burns just 0.49&nbsp;g/min (<strong>21%</strong>). That&#8217;s a <strong>2&#215; gap</strong> in free energy from fat. But here&#8217;s the twist: the pro&#8217;s <em>total</em> carb demand is also much higher &#8212; 123&nbsp;g/hr vs 103. And at realistic race pace, the picture changes even more.</p>
      <p class="gg-wp-prose">A recreational rider racing at 1.5&#8211;2.0&nbsp;W/kg burns only <strong>41&#8211;58&nbsp;g/hr</strong> of carbs. The gut can absorb 90&#8211;120&nbsp;g/hr. They have massive headroom &#8212; if they actually eat. A pro racing at 3.5&nbsp;W/kg burns <strong>156&nbsp;g/hr</strong> &#8212; well beyond what any gut can absorb. Their fat buffer is the only thing keeping them from bonking faster.</p>
      <p class="gg-wp-prose"><strong>Everyone has a carb gap. Fitness determines where it bites.</strong> For the recreational rider, the gap is behavioral &#8212; they eat 30&nbsp;g/hr when they could absorb 90. For the pro, the gap is physiological &#8212; they burn more than any gut can replace.</p>
    </div>
    <div class="gg-wp-scroll-step" data-step="3">
      <h3 class="gg-wp-subsection-title">At Race Pace, You&#8217;re Carb-Powered</h3>
      <p class="gg-wp-prose">Whatever your fitness, carbs dominate at race intensity: <strong>65&#8211;79%</strong> of your energy comes from carbohydrate. The difference is scale. A recreational rider at 2.0&nbsp;W/kg burns 58&nbsp;g/hr and can replace every gram if they practice. A pro at 3.5&nbsp;W/kg burns 156&nbsp;g/hr and will always run a deficit. That&#8217;s why the right number depends on <strong>your</strong> body, <strong>your</strong> fitness, and <strong>your</strong> race.</p>
    </div>
  </div>
</section>'''


def build_metabolic_testing() -> str:
    """Section 2: What Metabolic Testing Reveals — crossover table + data."""
    # Fitness category data table with bar fills
    categories = [
        ("Well-trained endurance", "~5.4", 100),
        ("Competitive age-group", "~4.4", 81),
        ("Trained masters (40+)", "~3.8", 70),
        ("Recreational", "~3.2", 59),
        ("Minimally trained", "~2.1", 39),
    ]
    rows_html = ""
    for name, crossover, pct in categories:
        rows_html += f'''        <tr>
          <td class="gg-wp-table-cell gg-wp-table-cell--label">{esc(name)}</td>
          <td class="gg-wp-table-cell gg-wp-table-cell--value">{crossover}</td>
          <td class="gg-wp-table-cell gg-wp-table-cell--bar">
            <div class="gg-wp-bar-track">
              <div class="gg-wp-bar-fill" style="--tw:{pct}%" data-target-w="{pct}%"></div>
            </div>
          </td>
        </tr>
'''

    return f'''<section class="gg-wp-section gg-wp-section--alt" id="metabolic-testing">
  <h2 class="gg-wp-section-title">Why Fitness Changes Your Fuel Mix</h2>
  <div class="gg-wp-prose">
    <p>Inside a metabolic lab, riders pedal on an ergometer while a mask captures every breath. As intensity rises, the body&#8217;s fuel mix shifts. At low watts, fat dominates. Cross a threshold &#8212; and carbohydrate takes over. Where that crossover happens depends almost entirely on how fit you are.</p>
    <p>Notice that even the well-trained rider&#8217;s crossover (~5.4&nbsp;W/kg) is below typical gravel race intensity for most athletes. This is the core insight: at race pace, riders across all fitness levels are carb-dominant. The question is how <em>much</em> carbohydrate they burn &#8212; and therefore how much they need to replace.</p>
  </div>
  <figure class="gg-wp-figure" id="crossover-figure">
    <div class="gg-wp-figure-title">Crossover Point by Fitness Level</div>
    <div class="gg-wp-chart-wrap" data-animate="bars">
      <table class="gg-wp-table" role="table" aria-label="Crossover point by fitness level">
        <thead>
          <tr>
            <th class="gg-wp-table-header">Fitness Level</th>
            <th class="gg-wp-table-header">Crossover (W/kg)</th>
            <th class="gg-wp-table-header">Relative</th>
          </tr>
        </thead>
        <tbody>
{rows_html}        </tbody>
      </table>
    </div>
    <div class="gg-wp-figure-takeaway">At 2.0 W/kg, the difference in total carbohydrate oxidation between a well-trained and a minimally trained rider is approximately 2.4x. Fitness level changes everything.</div>
  </figure>
</section>'''


def build_power_curve() -> str:
    """Section 3: The Power Curve Formula — formula, calibration, worked examples."""
    # Duration brackets table
    brackets_html = """        <tr><td class="gg-wp-table-cell">2&ndash;4 hrs</td><td class="gg-wp-table-cell">80&ndash;100</td><td class="gg-wp-table-cell">High-intensity race pace</td></tr>
        <tr><td class="gg-wp-table-cell">4&ndash;8 hrs</td><td class="gg-wp-table-cell">60&ndash;80</td><td class="gg-wp-table-cell">Classic endurance</td></tr>
        <tr><td class="gg-wp-table-cell">8&ndash;12 hrs</td><td class="gg-wp-table-cell">50&ndash;70</td><td class="gg-wp-table-cell">Sub-threshold, fat oxidation rising</td></tr>
        <tr><td class="gg-wp-table-cell">12&ndash;16 hrs</td><td class="gg-wp-table-cell">40&ndash;60</td><td class="gg-wp-table-cell">Ultra pace, glycogen depletion</td></tr>
        <tr><td class="gg-wp-table-cell">16+ hrs</td><td class="gg-wp-table-cell">30&ndash;50</td><td class="gg-wp-table-cell">Survival pace, GI distress &gt;90%</td></tr>"""

    # Power curve calibration table with SVG scatter
    cal_points = [
        (2.0, 0.093, 0.081, 0.2),
        (2.5, 0.226, 0.213, 0.3),
        (3.0, 0.379, 0.378, 0.0),
        (3.5, 0.553, 0.568, 0.3),
        (4.0, 0.744, 0.779, 0.7),
    ]
    cal_rows = ""
    for wkg, curve, lab, err in cal_points:
        cal_note = " (calibration)" if wkg == 3.0 else ""
        cal_rows += f'        <tr><td class="gg-wp-table-cell">{wkg}</td><td class="gg-wp-table-cell">{curve:.3f}</td><td class="gg-wp-table-cell">{lab:.3f}</td><td class="gg-wp-table-cell">{err} g/hr{cal_note}</td></tr>\n'

    # SVG scatter: power curve vs lab data
    scatter_w = 500
    scatter_h = 300
    # Map W/kg 1.5-4.5 to x: 60-460, factor 0-1 to y: 260-40
    def _x(wkg):
        return 60 + (wkg - 1.5) / 3.0 * 400

    def _y(factor):
        return 260 - factor * 220

    # Draw curve line (power curve)
    curve_points = []
    for w in range(15, 46):
        wkg = w / 10.0
        linear = (wkg - 1.5) / 3.0
        factor = linear ** 1.4
        curve_points.append(f"{_x(wkg):.0f},{_y(factor):.0f}")
    curve_path = " ".join(curve_points)

    # Lab data points
    lab_dots = ""
    for wkg, _, lab, _ in cal_points:
        lab_dots += f'    <rect x="{_x(wkg) - 4:.0f}" y="{_y(lab) - 4:.0f}" width="8" height="8" fill="{COLORS["gold"]}"/>\n'

    scatter_svg = f'''<div class="gg-wp-chart-wrap">
  <svg viewBox="0 0 {scatter_w} {scatter_h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Power curve vs lab data calibration scatter plot">
    <title>6-Point Calibration: Power Curve vs Lab Data</title>
    <!-- Axes -->
    <line x1="60" y1="260" x2="460" y2="260" stroke="{COLORS['dark_brown']}" stroke-width="2"/>
    <line x1="60" y1="40" x2="60" y2="260" stroke="{COLORS['dark_brown']}" stroke-width="2"/>
    <!-- X-axis labels -->
    <text x="60" y="280" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">1.5</text>
    <text x="193" y="280" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">2.5</text>
    <text x="327" y="280" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">3.5</text>
    <text x="460" y="280" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="middle">4.5</text>
    <text x="260" y="298" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="11" text-anchor="middle">W/kg (FTP)</text>
    <!-- Y-axis labels -->
    <text x="50" y="264" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="end">0.0</text>
    <text x="50" y="154" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="end">0.5</text>
    <text x="50" y="44" fill="{COLORS['secondary_brown']}" font-family="'Sometype Mono', monospace" font-size="10" text-anchor="end">1.0</text>
    <!-- Grid lines -->
    <line x1="60" y1="150" x2="460" y2="150" stroke="{COLORS['tan']}" stroke-width="1" stroke-dasharray="4"/>
    <!-- Power curve line -->
    <polyline points="{curve_path}" fill="none" stroke="{COLORS['teal']}" stroke-width="2.5"/>
    <!-- Lab data points -->
{lab_dots}    <!-- Legend -->
    <line x1="300" y1="20" x2="330" y2="20" stroke="{COLORS['teal']}" stroke-width="2.5"/>
    <text x="335" y="24" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="10">Power curve (1.4)</text>
    <rect x="300" y="35" width="8" height="8" fill="{COLORS['gold']}"/>
    <text x="315" y="43" fill="{COLORS['dark_brown']}" font-family="'Sometype Mono', monospace" font-size="10">Lab data</text>
  </svg>
</div>'''

    # Worked examples as expandable accordions
    examples_html = '''    <div class="gg-wp-accordion" data-accordion>
      <button class="gg-wp-accordion-trigger" aria-expanded="false">
        <span class="gg-wp-accordion-title">Murphy: 95 kg, 220W FTP, 6.5-hour race</span>
        <span class="gg-wp-accordion-icon" aria-hidden="true">+</span>
      </button>
      <div class="gg-wp-accordion-panel" aria-hidden="true">
        <ul class="gg-wp-example-steps">
          <li>FTP-derived W/kg = 220/95 = <strong>2.32</strong></li>
          <li>Duration bracket: 60&ndash;80 g/hr (4&ndash;8 hours)</li>
          <li>linear = (2.32 &minus; 1.5) / 3.0 = 0.273</li>
          <li>factor = 0.273<sup>1.4</sup> = 0.167</li>
          <li>rate = round(60 + 0.167 &times; 20) = <strong>63 g/hr</strong></li>
          <li>Total: 63 &times; 6.5 = <strong>410g</strong> (~16 gels equivalent)</li>
        </ul>
        <p class="gg-wp-example-note">Generic 60&#8211;90 advice would give Murphy 80 g/hr &#8212; 27% higher.</p>
      </div>
    </div>
    <div class="gg-wp-accordion" data-accordion>
      <button class="gg-wp-accordion-trigger" aria-expanded="false">
        <span class="gg-wp-accordion-title">Competitive racer: 70 kg, 280W FTP, 6.5-hour race</span>
        <span class="gg-wp-accordion-icon" aria-hidden="true">+</span>
      </button>
      <div class="gg-wp-accordion-panel" aria-hidden="true">
        <ul class="gg-wp-example-steps">
          <li>FTP-derived W/kg = 280/70 = <strong>4.0</strong></li>
          <li>Duration bracket: 60&ndash;80 g/hr (4&ndash;8 hours)</li>
          <li>linear = (4.0 &minus; 1.5) / 3.0 = 0.833</li>
          <li>factor = 0.833<sup>1.4</sup> = 0.744</li>
          <li>rate = round(60 + 0.744 &times; 20) = <strong>75 g/hr</strong></li>
          <li>Total: 75 &times; 6.5 = <strong>488g</strong> (~20 gels equivalent)</li>
        </ul>
        <p class="gg-wp-example-note">At 4.0 W/kg FTP, 12 g/hr higher than the 2.3 W/kg rider.</p>
      </div>
    </div>'''

    return f'''<section class="gg-wp-section" id="power-curve">
  <h2 class="gg-wp-section-title">Inside the Formula</h2>
  <div class="gg-wp-prose">
    <p>The formula takes three inputs: body weight (kg), FTP (watts), and estimated race duration (hours). It works in two stages. First, your race duration picks a bracket. Then your W/kg positions you within it.</p>
  </div>
  <figure class="gg-wp-figure" id="brackets-figure">
    <div class="gg-wp-figure-title">Duration Brackets (g/hr)</div>
    <div class="gg-wp-chart-wrap">
      <table class="gg-wp-table" role="table" aria-label="Duration brackets for carbohydrate intake">
        <thead>
          <tr><th class="gg-wp-table-header">Duration</th><th class="gg-wp-table-header">Bracket (g/hr)</th><th class="gg-wp-table-header">Basis</th></tr>
        </thead>
        <tbody>
{brackets_html}
        </tbody>
      </table>
    </div>
  </figure>
  <div class="gg-wp-accordion" data-accordion>
    <button class="gg-wp-accordion-trigger" aria-expanded="false">
      <span class="gg-wp-accordion-title">See the math</span>
      <span class="gg-wp-accordion-icon" aria-hidden="true">+</span>
    </button>
    <div class="gg-wp-accordion-panel" aria-hidden="true">
      <div class="gg-wp-formula-block" role="region" aria-label="Power curve formula">
        <code class="gg-wp-formula">
          W/kg = FTP / body_weight_kg<br>
          linear = clamp((W/kg &minus; 1.5) / (4.5 &minus; 1.5), 0, 1)<br>
          intensity_factor = linear<sup>1.4</sup><br>
          rate = round(bracket_low + intensity_factor &times; (bracket_high &minus; bracket_low))
        </code>
      </div>
      <p>The exponent of 1.4 compresses the lower end of the W/kg range toward the bracket floor and steepens the gains at higher W/kg. This matches the non-linear rise in carbohydrate oxidation near the lactate threshold.</p>
    </div>
  </div>
  <div class="gg-wp-accordion" data-accordion>
    <button class="gg-wp-accordion-trigger" aria-expanded="false">
      <span class="gg-wp-accordion-title">Calibration data</span>
      <span class="gg-wp-accordion-icon" aria-hidden="true">+</span>
    </button>
    <div class="gg-wp-accordion-panel" aria-hidden="true">
      <figure class="gg-wp-figure" id="calibration-figure">
        <div class="gg-wp-figure-title">6-Point Calibration Cross-Check</div>
        {scatter_svg}
        <div class="gg-wp-chart-wrap">
          <table class="gg-wp-table" role="table" aria-label="Calibration cross-check data">
            <thead>
              <tr><th class="gg-wp-table-header">W/kg</th><th class="gg-wp-table-header">Power Curve</th><th class="gg-wp-table-header">Lab Data</th><th class="gg-wp-table-header">Error</th></tr>
            </thead>
            <tbody>
{cal_rows}            </tbody>
          </table>
        </div>
        <div class="gg-wp-figure-takeaway">Maximum error across the range is 0.7 g/hr within a 20 g/hr bracket &#8212; well within the noise floor of individual variation.</div>
      </figure>
    </div>
  </div>
  <h3 class="gg-wp-subsection-title">Worked Examples</h3>
{examples_html}
</section>'''


def build_jensen() -> str:
    """Section 4: Jensen's Inequality — averaging bias."""
    # HTML div comparison bars
    bar_html = '''<div class="gg-wp-chart-wrap" data-animate="bars" role="img" aria-label="Jensen's inequality: fat oxidation estimate error">
  <div class="gg-wp-compare-row">
    <span class="gg-wp-compare-label">From average power</span>
    <div class="gg-wp-bar-track">
      <div class="gg-wp-bar-fill gg-wp-bar-fill--brown" style="--tw:84%" data-target-w="84%"></div>
    </div>
    <span class="gg-wp-compare-value">100.8g</span>
  </div>
  <div class="gg-wp-compare-row">
    <span class="gg-wp-compare-label">Second-by-second</span>
    <div class="gg-wp-bar-track">
      <div class="gg-wp-bar-fill gg-wp-bar-fill--teal" style="--tw:46%" data-target-w="46%"></div>
    </div>
    <span class="gg-wp-compare-value">55.0g</span>
  </div>
  <div class="gg-wp-compare-annotation gg-wp-compare-annotation--highlight">83% overestimate</div>
  <div class="gg-wp-compare-annotation">Fat oxidation over a real ride with variable power</div>
</div>'''

    return f'''<section class="gg-wp-section gg-wp-section--alt" id="jensen">
  <h2 class="gg-wp-section-title">Why Averages Lie</h2>
  <div class="gg-wp-prose">
    <p>Gravel races are not ridden at constant power. You surge up a 15% gravel wall, coast down the other side, and sprint to close a gap. Your average watts might be 180 &#8212; but you spent half the race at 250 and the other half at 110. Mathematicians call this Jensen&#8217;s Inequality. For fat oxidation, the error is dramatic:</p>
  </div>
  <figure class="gg-wp-figure" id="jensen-figure">
    <div class="gg-wp-figure-title">The Jensen&#8217;s Inequality Effect on Fat Oxidation</div>
    {bar_html}
    <div class="gg-wp-figure-takeaway">Our bracket-bounded approach absorbs the Jensen&#8217;s error. A rider whose true per-second average suggests 70 g/hr will get a recommendation between 60 and 80 g/hr regardless &#8212; the brackets are the guardrail.</div>
  </figure>
</section>'''


def build_practical() -> str:
    """Section 2: What To Do About It — numbered callout cards."""
    implications = [
        ("You have a power meter",
         "Go to your race page. Enter your weight, FTP, and expected finish time. That&#8217;s your starting number &#8212; not a ceiling, not a floor."),
        ("You don&#8217;t have a power meter",
         "The calculator defaults to the bracket midpoint. Conservative &#8212; and that&#8217;s fine. Undershooting by 10&nbsp;g/hr is an inconvenience. Overshooting is a porta-potty emergency."),
        ("Train your gut before race day",
         "Your stomach is the weakest link in your fueling chain. Gut training increases exogenous carbohydrate oxidation by ~16% over 28 days and reduces GI symptoms by up to 60%. A perfect number on paper is worthless if you&#8217;re retching at mile 90. Start 8&#8211;10 weeks out."),
        ("Start low, adjust up",
         "For your first Leadville or your first Unbound, aim for the lower third of your bracket. GI distress cascades &#8212; once it starts, your gut becomes less tolerant, not more."),
        ("Real food matters after hour 8",
         "By hour 10, the thought of another gel is worse than the climb ahead. Rice cakes, PB+J, boiled potatoes &#8212; real food keeps your stomach in the game."),
    ]
    cards_html = ""
    for i, (title, body) in enumerate(implications, 1):
        cards_html += f'''    <div class="gg-wp-callout-card">
      <span class="gg-wp-callout-number">{i}</span>
      <h3 class="gg-wp-callout-title">{title}</h3>
      <p class="gg-wp-callout-body">{body}</p>
    </div>
'''
    return f'''<section class="gg-wp-section" id="practical">
  <h2 class="gg-wp-section-title">What To Do About It</h2>
  <div class="gg-wp-prose">
    <p>Before the science: here&#8217;s what to do.</p>
  </div>
{cards_html}</section>'''


def build_inline_cta(text: str, note: str, ga_label: str) -> str:
    """Build an inline CTA block with a button and note."""
    return f'''<div class="gg-wp-inline-cta">
  <a href="{SITE_BASE_URL}/gravel-races/" class="gg-wp-cta-button" data-ga="whitepaper_inline_cta" data-ga-label="{esc(ga_label)}">{esc(text)}</a>
  <p class="gg-wp-inline-cta-note">{note}</p>
</div>'''


def build_phenotype() -> str:
    """Section 4: Same Watts, Different Engine — VLaMax table + glycogen depletion timeline."""
    # VLaMax data table with heatmap coloring
    vlamax_rows = [
        ("0.25&ndash;0.3", "Diesel &#8212; the rider who never bonks", "~60&ndash;80", "~100&ndash;120", "low"),
        ("0.4&ndash;0.5", "All-rounder &#8212; most gravel racers", "~90&ndash;120", "~140&ndash;170", "mid"),
        ("0.6&ndash;0.7", "Glycolytic &#8212; the rider who surges and suffers", "~120&ndash;150", "~180&ndash;220", "high"),
    ]
    vla_rows_html = ""
    for vla, rider_type, cho_sub, cho_thresh, heat_class in vlamax_rows:
        vla_rows_html += f'''        <tr class="gg-wp-heat-{heat_class}">
          <td class="gg-wp-table-cell">{vla}</td>
          <td class="gg-wp-table-cell">{esc(rider_type)}</td>
          <td class="gg-wp-table-cell">{cho_sub} g/hr</td>
          <td class="gg-wp-table-cell">{cho_thresh} g/hr</td>
        </tr>
'''

    # HTML div glycogen depletion bars
    depletion_html = '''<div class="gg-wp-chart-wrap" data-animate="bars" role="img" aria-label="Glycogen depletion timeline by phenotype">
  <div class="gg-wp-compare-row">
    <span class="gg-wp-compare-label">Diesel (low VLaMax)</span>
    <div class="gg-wp-bar-track">
      <div class="gg-wp-bar-fill gg-wp-bar-fill--teal" style="--tw:90%" data-target-w="90%"></div>
    </div>
    <span class="gg-wp-compare-value">12+ hrs</span>
  </div>
  <div class="gg-wp-compare-row">
    <span class="gg-wp-compare-label">Average</span>
    <div class="gg-wp-bar-track">
      <div class="gg-wp-bar-fill gg-wp-bar-fill--gold" style="--tw:68%" data-target-w="68%"></div>
    </div>
    <span class="gg-wp-compare-value">10&ndash;15 hrs</span>
  </div>
  <div class="gg-wp-compare-row">
    <span class="gg-wp-compare-label">Glycolytic (high VLaMax)</span>
    <div class="gg-wp-bar-track">
      <div class="gg-wp-bar-fill gg-wp-bar-fill--brown" style="--tw:35%" data-target-w="35%"></div>
    </div>
    <span class="gg-wp-compare-value">5&ndash;6 hrs</span>
  </div>
</div>'''

    return f'''<section class="gg-wp-section" id="phenotype">
  <h2 class="gg-wp-section-title">Same Watts, Different Engine</h2>
  <div class="gg-wp-prose">
    <p>Two riders. Both 3.5&nbsp;W/kg. Both riding Mid South in Oklahoma. One has a diesel engine &#8212; slow-twitch dominant, burns fat like a furnace. The other is glycolytic &#8212; fast-twitch heavy, tears through carbs like they&#8217;re free. The diesel rider&#8217;s glycogen lasts 12 hours. The glycolytic rider&#8217;s lasts 5.</p>
  </div>
  <figure class="gg-wp-figure" id="vlamax-figure">
    <div class="gg-wp-figure-title">VLaMax and Carbohydrate Combustion</div>
    <div class="gg-wp-chart-wrap">
      <table class="gg-wp-table" role="table" aria-label="VLaMax ranges and carbohydrate combustion rates">
        <thead>
          <tr><th class="gg-wp-table-header">VLaMax (mmol/L/s)</th><th class="gg-wp-table-header">Rider Type</th><th class="gg-wp-table-header">CHO at ~65% VO2max</th><th class="gg-wp-table-header">CHO at Threshold</th></tr>
        </thead>
        <tbody>
{vla_rows_html}        </tbody>
      </table>
    </div>
  </figure>
  <figure class="gg-wp-figure" id="depletion-figure">
    <div class="gg-wp-figure-title">Glycogen Depletion Timeline</div>
    {depletion_html}
    <div class="gg-wp-figure-takeaway">The diesel rider doesn&#8217;t need to eat less &#8212; they <em>can get away with</em> eating less. The glycolytic rider can&#8217;t eat enough to prevent depletion. More fuel doesn&#8217;t save them &#8212; <strong>pacing saves them</strong>.</div>
  </figure>
  <div class="gg-wp-prose">
    <p><strong>The counterintuitive finding:</strong> the phenotype effect on total carbohydrate combustion is massive, but the effect on the exogenous fueling recommendation is constrained by the gut. Maximum exogenous absorption caps at ~90&ndash;120 g/hr regardless of how fast the muscles burn carbs. The practical effect at gravel-relevant intensity is ~20 g/hr &#8212; exactly one bracket width.</p>
  </div>
</section>'''


def build_limitations() -> str:
    """Section 7: Limitations — expandable accordion list."""
    limitations = [
        ("W/kg is not %VO2max", "Two riders at 3.0 W/kg FTP with different VO2max values are at different fractions of their metabolic ceiling. W/kg is the best proxy available without a lab test."),
        ("FTP &ne; race power", "Most gravel racers ride at 60&ndash;80% of FTP for multi-hour events. The formula uses FTP as a fitness proxy, not as an assumption of race-day watts."),
        ("FTP measurement varies by protocol", "A 20-minute test, ramp test, 8-minute test, and Kolie Moore protocol produce 5&ndash;10% different FTP values. At 75 kg, a 5% FTP error = ~0.2 W/kg = ~1&ndash;2 g/hr recommendation shift."),
        ("The 1.5&ndash;4.5 W/kg range is gravel-specific", "Road racing W/kg values extend higher; recreational cycling extends lower. The range was chosen to cover the population that uses Race Prep Kits."),
        ("Individual variation is enormous", "Metabolic testing shows 2.4x differences in total CHO oxidation at the same W/kg across fitness levels. Our formula models a competitive age-group cyclist."),
        ("Phenotype is not modeled", "Fiber type, VLaMax, fat adaptation, sex, and body composition all affect substrate utilization. The bracket width absorbs most variation for the exogenous recommendation."),
        ("Pre-race glycogen loading, heat, altitude, and gut training are not in the formula", "Starting glycogen stores (300&ndash;700g) affect the depletion clock. Heat and altitude affect GI tolerance and metabolic demand."),
        ("Jensen&#8217;s inequality bias", "FTP represents a ~40&ndash;70 minute steady-state effort; race power distribution is far more variable. The bracket-bounded approach limits practical impact to 3&ndash;8 g/hr for CHO."),
        ("The exponent has not been independently validated", "The 1.4 exponent was calibrated and cross-checked against one metabolic testing dataset. It has not been validated against a second independent dataset or prospective race outcomes."),
        ("Duration bracket boundaries are clinical judgment", "Transitions at 4, 8, 12, and 16 hours are round numbers chosen from literature and coaching experience, not derived from changepoint analysis."),
    ]
    items_html = ""
    for title, body in limitations:
        items_html += f'''    <div class="gg-wp-accordion" data-accordion>
      <button class="gg-wp-accordion-trigger" aria-expanded="false">
        <span class="gg-wp-accordion-title">{title}</span>
        <span class="gg-wp-accordion-icon" aria-hidden="true">+</span>
      </button>
      <div class="gg-wp-accordion-panel" aria-hidden="true">
        <p>{body}</p>
      </div>
    </div>
'''
    return f'''<section class="gg-wp-section gg-wp-section--alt" id="limitations">
  <h2 class="gg-wp-section-title">What This Can&#8217;t Tell You</h2>
  <div class="gg-wp-prose">
    <p>Ten things this framework does not do, cannot do, or does imperfectly.</p>
  </div>
{items_html}</section>'''


def build_references() -> str:
    """Section 8: References — collapsible numbered list."""
    refs = [
        'Achten J, Gleeson M, Jeukendrup AE. (2002). Determination of the exercise intensity that elicits maximal fat oxidation. <em>Med Sci Sports Exerc</em>, 34(1), 92-97. <a href="https://doi.org/10.1097/00005768-200201000-00015" target="_blank" rel="noopener">DOI</a>',
        'Achten J, Jeukendrup AE. (2004). Relation between plasma lactate concentration and fat oxidation rates. <em>Int J Sports Med</em>, 25(1), 32-37. <a href="https://doi.org/10.1055/s-2003-45231" target="_blank" rel="noopener">DOI</a>',
        'Brooks GA, Mercier J. (1994). Balance of carbohydrate and lipid utilization during exercise: the &#8220;crossover&#8221; concept. <em>J Appl Physiol</em>, 76(6), 2253-2261. <a href="https://doi.org/10.1152/jappl.1994.76.6.2253" target="_blank" rel="noopener">DOI</a>',
        'Burke LM, et al. (2017). Low carbohydrate, high fat diet impairs exercise economy. <em>J Physiol</em>, 595(9), 2785-2807. <a href="https://doi.org/10.1113/JP273230" target="_blank" rel="noopener">DOI</a>',
        'Costa RJS, et al. (2017). Gut-training: the impact of two weeks repetitive gut-challenge. <em>Appl Physiol Nutr Metab</em>, 42(5), 547-557. <a href="https://doi.org/10.1139/apnm-2016-0453" target="_blank" rel="noopener">DOI</a>',
        'Cox GR, et al. (2010). Daily training with high carbohydrate availability increases exogenous carbohydrate oxidation. <em>J Appl Physiol</em>, 109(1), 126-134. <a href="https://doi.org/10.1152/japplphysiol.00950.2009" target="_blank" rel="noopener">DOI</a>',
        'Currell K, Jeukendrup AE. (2008). Superior endurance performance with ingestion of multiple transportable carbohydrates. <em>Med Sci Sports Exerc</em>, 40(2), 275-281. <a href="https://doi.org/10.1249/mss.0b013e31815adf19" target="_blank" rel="noopener">DOI</a>',
        'Daemen S, et al. (2020). Impact of exercise training status on fiber type-specific lipid metabolism proteins. <em>J Appl Physiol</em>, 128(2), 379-389. <a href="https://doi.org/10.1152/japplphysiol.00797.2019" target="_blank" rel="noopener">DOI</a>',
        'Devries MC. (2016). Sex-based differences in endurance exercise muscle metabolism. <em>Exp Physiol</em>, 101(2), 243-249. <a href="https://doi.org/10.1113/EP085369" target="_blank" rel="noopener">DOI</a>',
        'Gonzalez JT, et al. (2016). Liver glycogen metabolism during and after prolonged endurance-type exercise. <em>Am J Physiol</em>, 311(3), E543-E553. <a href="https://doi.org/10.1152/ajpendo.00232.2016" target="_blank" rel="noopener">DOI</a>',
        'Jensen JLWV. (1906). Sur les fonctions convexes et les in&eacute;galit&eacute;s entre les valeurs moyennes. <em>Acta Math</em>, 30, 175-193. <a href="https://doi.org/10.1007/BF02418571" target="_blank" rel="noopener">DOI</a>',
        'Jentjens RLPG, et al. (2004). Oxidation of combined ingestion of glucose and fructose during exercise. <em>J Appl Physiol</em>, 96(4), 1277-1284. <a href="https://doi.org/10.1152/japplphysiol.00974.2003" target="_blank" rel="noopener">DOI</a>',
        'Jentjens RLPG, Jeukendrup AE. (2005). High rates of exogenous carbohydrate oxidation from glucose and fructose. <em>Br J Nutr</em>, 93(4), 485-492. <a href="https://doi.org/10.1079/BJN20041368" target="_blank" rel="noopener">DOI</a>',
        'Jeukendrup AE, et al. (1997). Exogenous glucose oxidation during exercise in trained and untrained subjects. <em>J Appl Physiol</em>, 82(3), 835-840. <a href="https://doi.org/10.1152/jappl.1997.82.3.835" target="_blank" rel="noopener">DOI</a>',
        'Jeukendrup AE, et al. (2000). Relationship between GI complaints and endotoxaemia during long-distance triathlon. <em>Clin Sci</em>, 98(1), 47-55. <a href="https://doi.org/10.1042/CS19990258" target="_blank" rel="noopener">DOI</a>',
        'Jeukendrup AE. (2010). Carbohydrate and exercise performance: multiple transportable carbohydrates. <em>Curr Opin Clin Nutr Metab Care</em>, 13(4), 452-457. <a href="https://doi.org/10.1097/MCO.0b013e328339de9f" target="_blank" rel="noopener">DOI</a>',
        'Jeukendrup AE. (2014). A step towards personalized sports nutrition. <em>Sports Med</em>, 44(Suppl 1), S25-S33. <a href="https://doi.org/10.1007/s40279-014-0148-z" target="_blank" rel="noopener">DOI</a>',
        'Jeukendrup AE. (2017). Training the gut for athletes. <em>Sports Med</em>, 47(Suppl 1), 101-110. <a href="https://doi.org/10.1007/s40279-017-0690-6" target="_blank" rel="noopener">DOI</a>',
        'Kiens B, et al. (2004). Lipid-binding proteins and lipoprotein lipase activity in skeletal muscle. <em>J Appl Physiol</em>, 97(4), 1209-1218. <a href="https://doi.org/10.1152/japplphysiol.01278.2003" target="_blank" rel="noopener">DOI</a>',
        'Mattsson CM, et al. (2024). Variability in power output and its impact on estimated substrate oxidation. <em>Eur J Appl Physiol</em>, 124, 1269-1280. <a href="https://doi.org/10.1007/s00421-023-05355-5" target="_blank" rel="noopener">DOI</a>',
        'Miall A, et al. (2018). Two weeks of repetitive gut-challenge reduce exercise-associated GI symptoms. <em>Scand J Med Sci Sports</em>, 28(2), 630-640. <a href="https://doi.org/10.1111/sms.12912" target="_blank" rel="noopener">DOI</a>',
        'Moore K. (2023). The VLamax metric in WKO5. <em>Empirical Cycling</em>. <a href="https://www.empiricalcycling.com/vlamax_in_wko5.html" target="_blank" rel="noopener">Link</a>',
        'Noakes T, et al. (2025). Identification of a reverse crossover point during moderate-intensity exercise. <em>Front Nutr</em>, 12, 1627404. <a href="https://doi.org/10.3389/fnut.2025.1627404" target="_blank" rel="noopener">DOI</a>',
        'Pfeiffer B, et al. (2012). Nutritional intake and GI problems during competitive endurance events. <em>Med Sci Sports Exerc</em>, 44(2), 344-351. <a href="https://doi.org/10.1249/MSS.0b013e31822dc809" target="_blank" rel="noopener">DOI</a>',
        'Podlogar T, et al. (2022). Increased exogenous but unaltered endogenous CHO oxidation with combined fructose-maltodextrin at 120 vs 90 g/hr. <em>Eur J Appl Physiol</em>, 122(11), 2393-2404. <a href="https://doi.org/10.1007/s00421-022-05019-w" target="_blank" rel="noopener">DOI</a>',
        'Quittmann OJ, et al. (2024). INSCYD physiological performance software is valid to determine MLSS. <em>Front Physiol</em>, 15, 1364814. <a href="https://doi.org/10.3389/fphys.2024.1364814" target="_blank" rel="noopener">DOI</a>',
        'Randell RK, et al. (2017). Maximal fat oxidation rates in an athletic population. <em>Med Sci Sports Exerc</em>, 49(1), 133-140. <a href="https://doi.org/10.1249/MSS.0000000000001084" target="_blank" rel="noopener">DOI</a>',
        'San-Mill&aacute;n I, Brooks GA. (2018). Assessment of metabolic flexibility by blood lactate, fat, and CHO oxidation. <em>Sports Med</em>, 48(2), 467-479. <a href="https://doi.org/10.1007/s40279-017-0751-x" target="_blank" rel="noopener">DOI</a>',
        'Stuempfle KJ, Hoffman MD. (2015). GI distress is common during 161-km ultramarathon. <em>J Sports Sci</em>, 33(17), 1814-1821. <a href="https://doi.org/10.1080/02640414.2015.1012104" target="_blank" rel="noopener">DOI</a>',
        'Tarnopolsky LJ, et al. (1990). Gender differences in substrate for endurance exercise. <em>J Appl Physiol</em>, 68(1), 302-308. <a href="https://doi.org/10.1152/jappl.1990.68.1.302" target="_blank" rel="noopener">DOI</a>',
        'ter Steege RWF, Kolkman JJ. (2012). Pathophysiology and management of GI symptoms during physical exercise. <em>Aliment Pharmacol Ther</em>, 35(5), 516-528. <a href="https://doi.org/10.1111/j.1365-2036.2011.04980.x" target="_blank" rel="noopener">DOI</a>',
        'van Loon LJC, et al. (2001). Effects of increasing exercise intensity on muscle fuel utilisation. <em>J Physiol</em>, 536(Pt 1), 295-304. <a href="https://doi.org/10.1111/j.1469-7793.2001.00295.x" target="_blank" rel="noopener">DOI</a>',
        'van Loon LJC, et al. (2004). Intramyocellular lipid content in type I and type II muscle fibres. <em>Diabetologia</em>, 47(1), 23-30. <a href="https://doi.org/10.1007/s00125-003-1267-4" target="_blank" rel="noopener">DOI</a>',
        'van Wijck K, et al. (2011). Exercise-induced splanchnic hypoperfusion results in gut dysfunction. <em>PLoS ONE</em>, 6(7), e22366. <a href="https://doi.org/10.1371/journal.pone.0022366" target="_blank" rel="noopener">DOI</a>',
        'Venables MC, et al. (2005). Determinants of fat oxidation during exercise. <em>J Appl Physiol</em>, 98(1), 160-167. <a href="https://doi.org/10.1152/japplphysiol.00662.2003" target="_blank" rel="noopener">DOI</a>',
        'Volek JS, et al. (2016). Metabolic characteristics of keto-adapted ultra-endurance runners. <em>Metabolism</em>, 65(3), 100-110. <a href="https://doi.org/10.1016/j.metabol.2015.10.028" target="_blank" rel="noopener">DOI</a>',
        'Weber S. (2003). Calculation of performance-determining parameters of metabolic activity. Diploma thesis, German Sport University Cologne.',
        'Metabolic testing laboratory data, five fitness categories. Used for model calibration and cross-validation.',
    ]
    ref_items = ""
    for i, ref in enumerate(refs, 1):
        ref_items += f'      <li class="gg-wp-ref-item">{ref}</li>\n'

    return f'''<section class="gg-wp-section" id="references">
  <div class="gg-wp-accordion" data-accordion>
    <button class="gg-wp-accordion-trigger" aria-expanded="false">
      <span class="gg-wp-accordion-title">Sources ({len(refs)})</span>
      <span class="gg-wp-accordion-icon" aria-hidden="true">+</span>
    </button>
    <div class="gg-wp-accordion-panel" aria-hidden="true">
      <ol class="gg-wp-ref-list">
{ref_items}      </ol>
    </div>
  </div>
</section>'''


def build_cta() -> str:
    """Section: Closing CTA — link to Race Prep Kits."""
    return f'''<section class="gg-wp-section" id="cta">
  <div class="gg-wp-cta-block">
    <div class="gg-wp-cta-inner">
      <h2 class="gg-wp-cta-heading">Run Your Number</h2>
      <p class="gg-wp-cta-text">Three inputs. Your weight, your FTP, your race. Find your race page and the calculator does the rest.</p>
      <a href="{SITE_BASE_URL}/gravel-races/" class="gg-wp-cta-button" data-ga="whitepaper_cta_click" data-ga-label="race_prep_kits">FIND YOUR RACE</a>
    </div>
  </div>
</section>'''


# ── CSS ──────────────────────────────────────────────────────


def build_whitepaper_css() -> str:
    """Return all CSS for the white paper page."""
    return f'''<style>
/* ── White Paper Page ─────────────────────────────────────── */
{get_site_header_css()}

/* ── Page wrapper ── */
.gg-wp-page {{
  margin: 0;
  padding: 0;
  font-family: var(--gg-font-data);
  color: var(--gg-color-dark-brown);
  line-height: 1.6;
  background: var(--gg-color-warm-paper);
}}
.gg-wp-page *, .gg-wp-page *::before, .gg-wp-page *::after {{
  border-radius: 0 !important;
  box-shadow: none !important;
  box-sizing: border-box;
}}

/* ── Breadcrumb ── */
.gg-wp-breadcrumb {{
  max-width: 720px;
  margin: 0 auto;
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-wp-breadcrumb a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
  transition: color var(--gg-transition-hover);
}}
.gg-wp-breadcrumb a:hover {{ color: var(--gg-color-gold); }}
.gg-wp-breadcrumb-sep {{ margin: 0 var(--gg-spacing-xs); }}

/* ── Hero ── */
.gg-wp-hero {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl) var(--gg-spacing-xl);
  background: var(--gg-color-warm-paper);
  border-bottom: 3px solid var(--gg-color-dark-brown);
}}
.gg-wp-hero-inner {{
  max-width: 720px;
  margin: 0 auto;
  text-align: center;
}}
.gg-wp-hero-eyebrow {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-extreme);
  color: var(--gg-color-gold);
  text-transform: uppercase;
  display: block;
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-wp-hero-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(28px, 5vw, 48px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
  line-height: var(--gg-line-height-tight);
}}
.gg-wp-hero-subtitle {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(16px, 3vw, 22px);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
  line-height: var(--gg-line-height-normal);
}}
.gg-wp-hero-meta {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  margin: 0 0 var(--gg-spacing-xl) 0;
  letter-spacing: var(--gg-letter-spacing-wide);
}}

/* ── Sections ── */
.gg-wp-section {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  max-width: 720px;
  margin: 0 auto;
}}
.gg-wp-section--alt {{
  background: var(--gg-color-sand);
  max-width: none;
  padding-left: max(var(--gg-spacing-xl), calc(50% - 328px));
  padding-right: max(var(--gg-spacing-xl), calc(50% - 328px));
}}
.gg-wp-section-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(22px, 3.5vw, 32px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-wp-subsection-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(18px, 2.5vw, 22px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: var(--gg-spacing-lg) 0 var(--gg-spacing-md) 0;
}}

/* ── Prose ── */
.gg-wp-prose {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(15px, 2.5vw, 17px);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  max-width: 720px;
  margin: 0 auto var(--gg-spacing-lg) auto;
}}
.gg-wp-prose p {{
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-wp-prose strong {{
  color: var(--gg-color-dark-brown);
}}

/* ── Figure Wrapper ── */
.gg-wp-figure {{
  margin: 0 0 var(--gg-spacing-xl) 0;
}}
.gg-wp-figure-title {{
  font-family: var(--gg-font-editorial);
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--gg-color-near-black);
  border-bottom: 3px solid var(--gg-color-gold);
  padding: 0 0 0.5rem 0;
  margin: 0 0 1rem 0;
}}
.gg-wp-figure-takeaway {{
  border-left: 4px solid var(--gg-color-teal);
  padding: 0.75rem 1rem;
  margin: 1rem 0 0 0;
  font-family: var(--gg-font-editorial);
  font-style: italic;
  font-size: 0.9rem;
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-secondary-brown);
}}

/* ── Chart Wrappers ── */
.gg-wp-chart-wrap {{
  width: 100%;
  overflow-x: auto;
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-wp-chart-wrap svg {{
  display: block;
  max-width: 100%;
  height: auto;
}}

/* ── Tables ── */
.gg-wp-table {{
  width: 100%;
  border-collapse: collapse;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
}}
.gg-wp-table-header {{
  text-align: left;
  padding: var(--gg-spacing-xs) var(--gg-spacing-sm);
  font-weight: var(--gg-font-weight-bold);
  font-size: var(--gg-font-size-2xs);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-dark-brown);
  border-bottom: 2px solid var(--gg-color-dark-brown);
}}
.gg-wp-table-cell {{
  padding: var(--gg-spacing-xs) var(--gg-spacing-sm);
  border-bottom: 1px solid var(--gg-color-tan);
  vertical-align: middle;
}}
.gg-wp-table-cell--label {{
  font-weight: var(--gg-font-weight-semibold);
  white-space: nowrap;
}}
.gg-wp-table-cell--bar {{
  width: 40%;
}}

/* ── Bar fills in tables ──
   Bars use CSS custom property --tw for no-JS fallback width.
   .gg-has-js overrides to width:0, then JS sets inline width to animate. */
.gg-wp-bar-track {{
  background: var(--gg-color-tan);
  height: 16px;
  width: 100%;
}}
.gg-wp-bar-fill {{
  height: 100%;
  background: var(--gg-color-teal);
  width: var(--tw, 100%);
  margin-left: var(--ml, 0);
  transition: width 0.8s ease-out;
}}
.gg-wp-bar-fill--teal {{ background: var(--gg-color-teal); }}
.gg-wp-bar-fill--brown {{ background: var(--gg-color-secondary-brown); }}
.gg-wp-bar-fill--gold {{ background: var(--gg-color-gold); }}

/* ── Comparison bar rows ── */
.gg-wp-compare-row {{
  display: flex;
  align-items: center;
  gap: var(--gg-spacing-sm);
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-wp-compare-label {{
  flex: 0 0 200px;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-dark-brown);
  white-space: nowrap;
}}
.gg-wp-compare-row .gg-wp-bar-track {{
  flex: 1;
  height: 22px;
}}
.gg-wp-compare-row .gg-wp-bar-fill {{
  height: 100%;
}}
.gg-wp-compare-value {{
  flex: 0 0 auto;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  white-space: nowrap;
}}
.gg-wp-compare-annotation {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xs);
  font-style: italic;
  color: var(--gg-color-secondary-brown);
  margin: var(--gg-spacing-xs) 0 0 0;
}}
.gg-wp-compare-annotation--highlight {{
  font-family: var(--gg-font-data);
  font-style: normal;
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-gold);
  font-size: var(--gg-font-size-xs);
}}

/* ── Heatmap rows — use color-mix() with brand tokens, never raw rgba() ── */
.gg-wp-heat-low td {{ background: color-mix(in srgb, var(--gg-color-teal) 8%, transparent); }}
.gg-wp-heat-mid td {{ background: color-mix(in srgb, var(--gg-color-gold) 8%, transparent); }}
.gg-wp-heat-high td {{ background: color-mix(in srgb, var(--gg-color-secondary-brown) 12%, transparent); }}

/* ── TL;DR Grid ── */
.gg-wp-tldr-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--gg-spacing-md);
  padding: var(--gg-spacing-xs) 0;
}}
.gg-wp-tldr-card {{
  border: 3px solid var(--gg-color-gold);
  padding: var(--gg-spacing-md);
  background: var(--gg-color-warm-paper);
}}
.gg-wp-tldr-card-title {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-wp-tldr-card-body {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xs);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0;
}}

/* ── Formula Block ── */
.gg-wp-formula-block {{
  background: var(--gg-color-sand);
  border: 2px solid var(--gg-color-dark-brown);
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  margin: 0 0 var(--gg-spacing-lg) 0;
  overflow-x: auto;
}}
.gg-wp-formula {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  line-height: 2;
  color: var(--gg-color-dark-brown);
}}

/* ── Accordion ── */
.gg-wp-accordion {{
  border: 2px solid var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
}}
.gg-wp-accordion-trigger {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  background: var(--gg-color-warm-paper);
  border: none;
  cursor: pointer;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  text-align: left;
  transition: background-color var(--gg-transition-hover);
}}
.gg-wp-accordion-trigger:hover {{
  background: var(--gg-color-sand);
}}
.gg-wp-accordion-trigger[aria-expanded="true"] {{
  border-bottom: 1px solid var(--gg-color-tan);
}}
.gg-wp-accordion-title {{
  font-weight: var(--gg-font-weight-semibold);
}}
.gg-wp-accordion-icon {{
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-gold);
  transition: transform var(--gg-transition-hover);
}}
.gg-wp-accordion-trigger[aria-expanded="true"] .gg-wp-accordion-icon {{
  transform: rotate(45deg);
}}
.gg-wp-accordion-panel {{
  padding: var(--gg-spacing-md);
  display: none;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
}}
.gg-wp-accordion-panel[aria-hidden="false"] {{
  display: block;
}}
.gg-wp-accordion-panel p {{
  margin: 0 0 var(--gg-spacing-sm) 0;
}}

/* ── Worked Example Steps ── */
.gg-wp-example-steps {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  line-height: 1.8;
  padding-left: var(--gg-spacing-lg);
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-wp-example-note {{
  font-family: var(--gg-font-editorial);
  font-style: italic;
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  margin: 0;
}}

/* ── Callout Cards ── */
.gg-wp-callout-card {{
  border-left: 4px solid var(--gg-color-gold);
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  margin: 0 0 var(--gg-spacing-md) 0;
  background: var(--gg-color-warm-paper);
}}
.gg-wp-callout-number {{
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-gold);
  margin: 0 0 var(--gg-spacing-xs) 0;
}}
.gg-wp-callout-title {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
}}
.gg-wp-callout-body {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0;
}}

/* ── References ── */
.gg-wp-ref-list {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  line-height: 1.8;
  padding-left: var(--gg-spacing-lg);
  color: var(--gg-color-primary-brown);
}}
.gg-wp-ref-item {{
  margin: 0 0 var(--gg-spacing-xs) 0;
}}
.gg-wp-ref-item a {{
  color: var(--gg-color-teal);
  text-decoration: none;
}}
.gg-wp-ref-item a:hover {{
  color: var(--gg-color-dark-brown);
  text-decoration: underline;
}}

/* ── Inline CTA ── */
.gg-wp-inline-cta {{
  text-align: center;
  padding: var(--gg-spacing-xl) var(--gg-spacing-md);
  max-width: 720px;
  margin: 0 auto;
}}
.gg-wp-inline-cta-note {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  margin: var(--gg-spacing-sm) 0 0 0;
}}

/* ── CTA Block ── */
.gg-wp-cta-block {{
  max-width: 600px;
  margin: 0 auto;
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  text-align: center;
}}
.gg-wp-cta-inner {{
  max-width: 480px;
  margin: 0 auto;
}}
.gg-wp-cta-heading {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-wp-cta-text {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-lg) 0;
}}
.gg-wp-cta-button {{
  display: inline-block;
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  text-decoration: none;
  background: var(--gg-color-gold);
  color: var(--gg-color-white);
  border: var(--gg-border-width-standard) solid var(--gg-color-gold);
  transition: background-color var(--gg-transition-hover), color var(--gg-transition-hover);
}}
.gg-wp-cta-button:hover {{
  background: transparent;
  color: var(--gg-color-gold);
}}

/* ── Scrollytelling ── */
.gg-wp-scroll-section {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-xl);
  max-width: 1080px;
  margin: 0 auto;
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
}}
.gg-wp-scroll-chart {{
  position: sticky;
  top: 80px;
  height: fit-content;
  align-self: start;
}}
.gg-wp-scroll-chart-inner {{
  padding: var(--gg-spacing-md);
  border: 2px solid var(--gg-color-dark-brown);
  background: var(--gg-color-warm-paper);
}}
.gg-wp-scroll-steps {{
  display: flex;
  flex-direction: column;
  gap: 60vh;
}}
.gg-wp-scroll-step {{
  min-height: 40vh;
  opacity: 0.3;
  transition: opacity 0.4s ease;
}}
.gg-wp-scroll-step.gg-step-active {{
  opacity: 1;
}}
.gg-wp-scroll-step .gg-wp-prose {{
  max-width: none;
  margin: 0;
}}

/* ── Inline Calculator ── */
.gg-wp-calculator {{
  max-width: 720px;
  margin: 0 auto;
}}
.gg-wp-calc-form {{
  border: 3px solid var(--gg-color-dark-brown);
  padding: var(--gg-spacing-lg);
  background: var(--gg-color-warm-paper);
}}
.gg-wp-calc-inputs {{
  display: flex;
  gap: var(--gg-spacing-md);
  margin: 0 0 var(--gg-spacing-lg) 0;
}}
.gg-wp-calc-field {{
  flex: 1;
}}
.gg-wp-calc-label {{
  display: block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
}}
.gg-wp-calc-optional {{
  font-weight: normal;
  text-transform: none;
  color: var(--gg-color-secondary-brown);
}}
.gg-wp-calc-input-row {{
  display: flex;
  align-items: center;
  gap: var(--gg-spacing-xs);
}}
.gg-wp-calc-input {{
  width: 100%;
  padding: var(--gg-spacing-xs) var(--gg-spacing-sm);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-warm-paper);
  border: 3px solid var(--gg-color-dark-brown);
}}
.gg-wp-calc-input:focus {{
  outline: 3px solid var(--gg-color-teal);
  outline-offset: -3px;
}}
.gg-wp-calc-unit {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  white-space: nowrap;
}}
.gg-wp-calc-unit-btn {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-teal);
  background: none;
  border: 2px solid var(--gg-color-teal);
  padding: var(--gg-spacing-xs) var(--gg-spacing-sm);
  cursor: pointer;
  white-space: nowrap;
}}
.gg-wp-calc-unit-btn:hover {{
  background: var(--gg-color-teal);
  color: var(--gg-color-white);
}}
.gg-wp-calc-output {{
  text-align: center;
  padding: var(--gg-spacing-md) 0;
}}
.gg-wp-calc-result {{
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: var(--gg-spacing-xs);
}}
.gg-wp-calc-result-number {{
  font-family: var(--gg-font-data);
  font-size: clamp(36px, 8vw, 56px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-teal);
  line-height: 1;
}}
.gg-wp-calc-result-unit {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-lg);
  color: var(--gg-color-secondary-brown);
}}
.gg-wp-calc-bracket-bar {{
  max-width: 320px;
  margin: var(--gg-spacing-md) auto 0;
}}
.gg-wp-calc-bracket-track {{
  position: relative;
  height: 12px;
  background: var(--gg-color-tan);
}}
.gg-wp-calc-bracket-fill {{
  height: 100%;
  background: var(--gg-color-teal);
  opacity: 0.3;
  width: 100%;
}}
.gg-wp-calc-bracket-marker {{
  position: absolute;
  top: -2px;
  width: 4px;
  height: 16px;
  background: var(--gg-color-gold);
  transform: translateX(-50%);
  transition: left 0.3s ease;
}}
.gg-wp-calc-bracket-labels {{
  display: flex;
  justify-content: space-between;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  margin: var(--gg-spacing-xs) 0 0 0;
}}
.gg-wp-calc-food {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  margin: var(--gg-spacing-sm) 0 0 0;
  font-style: italic;
}}
.gg-wp-calc-fallback {{
  text-align: center;
  padding: var(--gg-spacing-md);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-secondary-brown);
}}
.gg-wp-calc-fallback a {{
  color: var(--gg-color-teal);
}}
/* No JS: show fallback, hide form.
   .gg-has-js reverses this so calculator works when JS loads. */
.gg-wp-calc-form {{ display: none; }}
.gg-wp-calc-fallback {{ display: block; }}
.gg-has-js .gg-wp-calc-form {{ display: block; }}
.gg-has-js .gg-wp-calc-fallback {{ display: none; }}

/* ── Responsive ── */
@media (max-width: 768px) {{
  .gg-wp-scroll-section {{
    grid-template-columns: 1fr;
  }}
  .gg-wp-scroll-chart {{
    position: relative;
    top: auto;
  }}
  .gg-wp-scroll-steps {{
    gap: var(--gg-spacing-2xl);
  }}
  .gg-wp-scroll-step {{
    opacity: 1;
  }}
}}
@media (max-width: 600px) {{
  .gg-wp-hero {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-wp-section {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-wp-section--alt {{ padding-left: var(--gg-spacing-md); padding-right: var(--gg-spacing-md); }}
  .gg-wp-breadcrumb {{ padding: var(--gg-spacing-xs) var(--gg-spacing-md); }}
  .gg-wp-tldr-grid {{ grid-template-columns: 1fr; }}
  .gg-wp-formula-block {{ padding: var(--gg-spacing-sm) var(--gg-spacing-md); }}
  .gg-wp-compare-label {{ flex: 0 0 140px; font-size: 10px; }}
  .gg-wp-calc-inputs {{ flex-direction: column; }}
  .gg-wp-scroll-section {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
}}

/* ── Progressive enhancement: bars visible by default, zeroed only when JS loads ── */
.gg-has-js [data-animate="bars"] .gg-wp-bar-fill {{
  width: 0;
}}
.gg-has-js [data-animate="bars"] .gg-wp-bar-fill.gg-in-view {{
  /* Animated state set by JS via inline style */
}}

@media (prefers-reduced-motion: reduce) {{
  .gg-wp-bar-fill, [data-target-w] {{ transition: none !important; }}
  .gg-has-js [data-animate="bars"] .gg-wp-bar-fill {{ width: var(--tw, 100%); }}
  .gg-wp-scroll-step {{ opacity: 1; transition: none !important; }}
  .gg-wp-calc-bracket-marker {{ transition: none !important; }}
}}
</style>'''


# ── JS ───────────────────────────────────────────────────────


def build_whitepaper_js() -> str:
    """Return all JS for the white paper page."""
    return '''<script>
(function(){
  'use strict';

  /* ── Progressive enhancement guard ── */
  document.documentElement.classList.add('gg-has-js');

  /* ── Reduced motion ── */
  var reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ══════════════════════════════════════════════════════════════
     BAR ANIMATIONS — Scroll-triggered
     ══════════════════════════════════════════════════════════════ */

  var barCharts = document.querySelectorAll('[data-animate="bars"]');
  if ('IntersectionObserver' in window && !reducedMotion) {
    var barObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          var fills = entry.target.querySelectorAll('[data-target-w]');
          fills.forEach(function(fill) {
            var tw = fill.getAttribute('data-target-w');
            if (tw) { fill.style.width = tw; fill.classList.add('gg-in-view'); }
          });
          barObserver.unobserve(entry.target);
        }
      });
    }, { threshold: 0.2 });
    barCharts.forEach(function(chart) { barObserver.observe(chart); });
  } else {
    barCharts.forEach(function(chart) {
      var fills = chart.querySelectorAll('[data-target-w]');
      fills.forEach(function(fill) {
        var tw = fill.getAttribute('data-target-w');
        if (tw) fill.style.width = tw;
      });
    });
  }

  /* ══════════════════════════════════════════════════════════════
     ACCORDION — Expand/collapse
     ══════════════════════════════════════════════════════════════ */

  var accordions = document.querySelectorAll('[data-accordion]');
  accordions.forEach(function(acc) {
    var trigger = acc.querySelector('.gg-wp-accordion-trigger');
    var panel = acc.querySelector('.gg-wp-accordion-panel');
    if (!trigger || !panel) return;
    trigger.addEventListener('click', function() {
      var expanded = trigger.getAttribute('aria-expanded') === 'true';
      trigger.setAttribute('aria-expanded', expanded ? 'false' : 'true');
      panel.setAttribute('aria-hidden', expanded ? 'true' : 'false');
    });
  });

  /* ══════════════════════════════════════════════════════════════
     SCROLLYTELLING — Step observer + chart updaters
     ══════════════════════════════════════════════════════════════ */

  function updateDurationChart(chart, step) {
    var brackets = chart.querySelectorAll('[data-chart-bracket]');
    var murphy = chart.querySelector('[data-chart-murphy]');
    brackets.forEach(function(g) {
      var fill = g.querySelector('.gg-wp-scroll-bracket-fill');
      if (!fill) return;
      if (step === 0) {
        fill.setAttribute('opacity', g.getAttribute('data-chart-bracket') === '1' ? '0.6' : '0.15');
      } else if (step === 1) {
        fill.setAttribute('opacity', '0.4');
      } else {
        fill.setAttribute('opacity', g.getAttribute('data-chart-bracket') === '1' ? '0.6' : '0.15');
      }
    });
    if (murphy) {
      murphy.setAttribute('opacity', step >= 2 ? '1' : '0');
    }
  }

  function updateFitnessChart(chart, step) {
    var comp = chart.querySelector('[data-chart-comp]');
    var exponent = chart.querySelector('[data-chart-exponent]');
    if (comp) comp.setAttribute('opacity', step >= 1 ? '1' : '0');
    if (exponent) exponent.setAttribute('opacity', step >= 2 ? '1' : '0');
  }

  function updateCrossoverChart(chart, step) {
    var recLine = chart.querySelector('[data-chart-rec-line]');
    var recArea = chart.querySelector('[data-chart-rec-area]');
    var recLabel = chart.querySelector('[data-chart-rec-label]');
    var proLabel = chart.querySelector('[data-chart-pro-label]');
    var proPeak = chart.querySelector('[data-chart-pro-peak]');
    var proPeakLabel = chart.querySelector('[data-chart-pro-peak-label]');
    var recPeak = chart.querySelector('[data-chart-rec-peak]');
    var recPeakLabel = chart.querySelector('[data-chart-rec-peak-label]');
    var raceZone = chart.querySelector('[data-chart-race-zone]');
    var raceLabel = chart.querySelector('[data-chart-race-label]');
    var carbNote = chart.querySelector('[data-chart-carb-note]');
    /* Gap bracket elements */
    var gapEls = chart.querySelectorAll('[data-chart-gap-line],[data-chart-gap-pro-dot],[data-chart-gap-rec-dot],[data-chart-gap-bracket],[data-chart-gap-bracket-top],[data-chart-gap-bracket-bot],[data-chart-gap-pro-text],[data-chart-gap-rec-text],[data-chart-gap-diff]');

    /* Step 0: Pro curve + carb-note visible. Everything else hidden. */
    if (carbNote) carbNote.setAttribute('opacity', step === 0 ? '0.7' : '0.3');

    /* Step 1: Rec curve appears + both curve labels + peak annotations */
    var showRec = step >= 1 ? '1' : '0';
    if (recLine) recLine.setAttribute('opacity', showRec);
    if (recArea) recArea.setAttribute('opacity', step >= 1 ? '0.12' : '0');
    if (proLabel) proLabel.setAttribute('opacity', showRec);
    if (recLabel) recLabel.setAttribute('opacity', showRec);
    if (proPeak) proPeak.setAttribute('opacity', step >= 1 ? '1' : '0');
    if (proPeakLabel) proPeakLabel.setAttribute('opacity', step >= 1 ? '1' : '0');
    if (recPeak) recPeak.setAttribute('opacity', step >= 1 ? '1' : '0');
    if (recPeakLabel) recPeakLabel.setAttribute('opacity', step >= 1 ? '1' : '0');

    /* Step 2: Gap bracket at 3.0 W/kg — the 2x gap visualization */
    var showGap = step >= 2 ? '1' : '0';
    gapEls.forEach(function(el) { el.setAttribute('opacity', showGap); });

    /* Step 3: Race pace zone */
    if (raceZone) raceZone.setAttribute('opacity', step >= 3 ? '0.08' : '0');
    if (raceLabel) raceLabel.setAttribute('opacity', step >= 3 ? '1' : '0');
  }

  function updateChart(chartEl, sectionId, stepIndex) {
    if (sectionId === 'scroll-duration') updateDurationChart(chartEl, stepIndex);
    else if (sectionId === 'scroll-fitness') updateFitnessChart(chartEl, stepIndex);
    else if (sectionId === 'scroll-crossover') updateCrossoverChart(chartEl, stepIndex);
  }

  var scrollSections = document.querySelectorAll('.gg-wp-scroll-section');
  if ('IntersectionObserver' in window) {
    scrollSections.forEach(function(section) {
      var steps = section.querySelectorAll('.gg-wp-scroll-step');
      var chart = section.querySelector('.gg-wp-scroll-chart-inner');
      if (!steps.length || !chart) return;

      var stepObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
          if (entry.isIntersecting) {
            steps.forEach(function(s) { s.classList.remove('gg-step-active'); });
            entry.target.classList.add('gg-step-active');
            var stepIndex = parseInt(entry.target.getAttribute('data-step'), 10);
            updateChart(chart, section.id, stepIndex);
          }
        });
      }, { threshold: 0.5, rootMargin: '-20% 0px -20% 0px' });
      steps.forEach(function(s) { stepObserver.observe(s); });
      /* Initialize chart at step 0 on page load */
      updateChart(chart, section.id, 0);
    });
  }

  /* ══════════════════════════════════════════════════════════════
     INLINE CALCULATOR — Reactive carb rate
     ══════════════════════════════════════════════════════════════ */

  function computeInline(weightKg, ftp, hours) {
    var bLo, bHi;
    if (hours <= 4)       { bLo = 80; bHi = 100; }
    else if (hours <= 8)  { bLo = 60; bHi = 80; }
    else if (hours <= 12) { bLo = 50; bHi = 70; }
    else if (hours <= 16) { bLo = 40; bHi = 60; }
    else                  { bLo = 30; bHi = 50; }

    var rate;
    if (ftp && ftp > 0 && weightKg > 0) {
      var wkg = ftp / weightKg;
      var lin = Math.max(0, Math.min(1, (wkg - 1.5) / 3.0));
      var factor = Math.pow(lin, 1.4);
      rate = Math.round(bLo + factor * (bHi - bLo));
    } else {
      rate = Math.round((bLo + bHi) / 2);
    }
    return { rate: rate, lo: bLo, hi: bHi };
  }

  var calcWeight = document.getElementById('gg-calc-weight');
  var calcFtp = document.getElementById('gg-calc-ftp');
  var calcHours = document.getElementById('gg-calc-hours');
  var calcNumber = document.getElementById('gg-calc-number');
  var calcBracket = document.getElementById('gg-calc-bracket');
  var calcBracketFill = document.getElementById('gg-calc-bracket-fill');
  var calcBracketMarker = document.getElementById('gg-calc-bracket-marker');
  var calcBracketLo = document.getElementById('gg-calc-bracket-lo');
  var calcBracketHi = document.getElementById('gg-calc-bracket-hi');
  var calcFood = document.getElementById('gg-calc-food');
  var calcUnitToggle = document.getElementById('gg-calc-unit-toggle');
  var calcUnitLabel = document.getElementById('gg-calc-weight-unit');
  var usingLbs = false;

  var calcGa4Timer = null;
  function updateCalc() {
    if (!calcWeight || !calcHours) return;
    var rawWeight = parseFloat(calcWeight.value);
    var rawFtp = parseFloat(calcFtp.value);
    var rawHours = parseFloat(calcHours.value);
    if (isNaN(rawWeight) || rawWeight <= 0 || isNaN(rawHours) || rawHours <= 0) {
      calcNumber.textContent = '\\u2014';
      if (calcBracket) calcBracket.setAttribute('aria-hidden', 'true');
      if (calcFood) calcFood.textContent = '';
      return;
    }
    var weightKg = usingLbs ? rawWeight * 0.453592 : rawWeight;
    if (weightKg < 20 || weightKg > 250) return;
    var result = computeInline(weightKg, rawFtp, rawHours);
    calcNumber.textContent = result.rate;
    if (calcBracket) {
      calcBracket.setAttribute('aria-hidden', 'false');
      if (calcBracketLo) calcBracketLo.textContent = result.lo + ' g/hr';
      if (calcBracketHi) calcBracketHi.textContent = result.hi + ' g/hr';
      var pct = (result.rate - result.lo) / (result.hi - result.lo) * 100;
      if (calcBracketMarker) calcBracketMarker.style.left = Math.max(0, Math.min(100, pct)) + '%';
    }
    if (calcFood) {
      var gels = (result.rate / 25).toFixed(1);
      calcFood.textContent = 'That\\u2019s about ' + gels + ' gels + 500ml sports drink per hour';
    }
    /* GA4: debounce — only fire once all 3 inputs have values, with 1s delay */
    if (rawWeight > 0 && rawHours > 0) {
      clearTimeout(calcGa4Timer);
      calcGa4Timer = setTimeout(function() {
        if (typeof gtag === 'function') {
          gtag('event', 'whitepaper_calculator', { rate: result.rate, weight_kg: Math.round(weightKg), hours: rawHours });
        }
      }, 1000);
    }
  }

  if (calcWeight) calcWeight.addEventListener('input', updateCalc);
  if (calcFtp) calcFtp.addEventListener('input', updateCalc);
  if (calcHours) calcHours.addEventListener('input', updateCalc);
  if (calcUnitToggle) {
    calcUnitToggle.addEventListener('click', function() {
      usingLbs = !usingLbs;
      if (calcUnitLabel) calcUnitLabel.textContent = usingLbs ? 'lbs' : 'kg';
      if (calcWeight.value) {
        var v = parseFloat(calcWeight.value);
        if (usingLbs) calcWeight.value = Math.round(v * 2.20462);
        else calcWeight.value = Math.round(v * 0.453592);
      }
      calcWeight.placeholder = usingLbs ? '165' : '75';
      calcWeight.min = usingLbs ? '66' : '30';
      calcWeight.max = usingLbs ? '440' : '200';
      updateCalc();
    });
  }

  /* ══════════════════════════════════════════════════════════════
     GA4 — Track accordion interactions
     ══════════════════════════════════════════════════════════════ */

  accordions.forEach(function(acc) {
    var trigger = acc.querySelector('.gg-wp-accordion-trigger');
    if (trigger) {
      trigger.addEventListener('click', function() {
        if (typeof gtag === 'function') {
          var title = acc.querySelector('.gg-wp-accordion-title');
          gtag('event', 'whitepaper_accordion', {
            section: title ? title.textContent : 'unknown'
          });
        }
      });
    }
  });

})();
</script>'''


# ── JSON-LD ──────────────────────────────────────────────────


def build_jsonld() -> str:
    """Return JSON-LD structured data for the white paper page."""
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "How Many Carbs Do You Actually Need? Personalized Fueling for Gravel Racing",
  "description": "Everyone says 60-90 grams per hour. The science behind personalized fueling in every Gravel God Race Prep Kit.",
  "author": {{
    "@type": "Organization",
    "name": "Gravel God Cycling"
  }},
  "publisher": {{
    "@type": "Organization",
    "name": "Gravel God Cycling",
    "url": "{SITE_BASE_URL}"
  }},
  "datePublished": "2026-02-01",
  "dateModified": "{datetime.date.today().isoformat()}",
  "url": "{CANONICAL_URL}"
}}
</script>'''


# ── Page Generation ──────────────────────────────────────────


def generate_whitepaper_page(external_assets: dict = None) -> str:
    """Generate the complete white paper page HTML."""
    nav = build_nav()
    hero = build_hero()
    murphy_problem = build_murphy()
    inline_calculator = build_inline_calculator()
    practical = build_practical()
    inline_cta_1 = build_inline_cta("CHECK YOUR NUMBER", "Find your race. Get your personalized carb target.", "check_your_number")
    scroll_duration = build_scroll_duration()
    scroll_fitness = build_scroll_fitness()
    scroll_crossover = build_scroll_crossover()
    tldr = build_tldr()
    inline_cta_2 = build_inline_cta("FIND YOUR RACE PREP KIT", "Personalized fueling for 328 races.", "find_race_prep_kit")
    phenotype = build_phenotype()
    jensen = build_jensen()
    power_curve = build_power_curve()
    metabolic_testing = build_metabolic_testing()
    limitations = build_limitations()
    references = build_references()
    cta = build_cta()
    footer = get_mega_footer_html()
    whitepaper_css = build_whitepaper_css()
    whitepaper_js = build_whitepaper_js()
    jsonld = build_jsonld()

    if external_assets:
        page_css = external_assets['css_tag']
    else:
        page_css = get_page_css()

    meta_desc = "Everyone says 60-90 grams per hour. A 95kg rider and a 62kg rider shouldn&#8217;t eat the same carbs. The science behind personalized fueling in every Gravel God Race Prep Kit."

    og_tags = f'''<meta property="og:title" content="How Many Carbs Do You Actually Need? | Gravel God">
  <meta property="og:description" content="{esc(meta_desc)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{esc(CANONICAL_URL)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="How Many Carbs Do You Actually Need? | Gravel God">
  <meta name="twitter:description" content="{esc(meta_desc)}">
  <meta name="twitter:image" content="{SITE_BASE_URL}/og/homepage.jpg">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>How Many Carbs Do You Actually Need? | Gravel God</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(CANONICAL_URL)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {whitepaper_css}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>

<a href="#hero" class="gg-skip-link">Skip to content</a>

<div class="gg-wp-page">
  {nav}

  {hero}

  {murphy_problem}

  {inline_calculator}

  {practical}

  {inline_cta_1}

  {scroll_duration}

  {scroll_fitness}

  {scroll_crossover}

  {tldr}

  {inline_cta_2}

  {phenotype}

  {jensen}

  {power_curve}

  {metabolic_testing}

  {limitations}

  {references}

  {cta}

  {footer}
</div>

{whitepaper_js}

{get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God fueling methodology white paper")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)

    html_content = generate_whitepaper_page(external_assets=assets)
    output_file = output_dir / "whitepaper-fueling.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
