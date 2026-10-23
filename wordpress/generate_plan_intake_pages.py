#!/usr/bin/env python3
"""
Generate the two-step training-plan questionnaire (2026-10-23).

Pages:
  /training-plans/start/    → output/plan-start.html
      Step 1: race, race date, name, email. Quotes the price, then sends
      the customer to Stripe Checkout (POST /api/create-checkout with
      intake_flow "two_step").
  /training-plans/details/  → output/plan-details.html
      Step 2, after payment (Stripe success_url carries ?t=<token>): every
      other question from the full questionnaire, over five short pages,
      autosaved and submitted to /api/intake-details/<token>.

Both pages are noindex: one is a checkout step, the other a private link.
/questionnaire/ 302s to /training-plans/start/ (scripts/push_wordpress.py
REDIRECT_BLOCK); deploy with `push_wordpress.py --sync-plan-intake`.

The page JS lives in web/training-plans-start.js and
web/training-plans-details.js and is inlined at build time. Prices come
from pricing.py (data/pricing.json) only.

Usage:
    python generate_plan_intake_pages.py
    python generate_plan_intake_pages.py --output-dir ./output
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path

from generate_neo_brutalist import (
    SITE_BASE_URL,
    get_page_css,
    build_inline_js,
    write_shared_assets,
)
from brand_tokens import (
    get_ab_head_snippet,
    get_font_face_css,
    get_ga4_head_snippet,
    get_preload_hints,
)
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html, get_site_header_css, get_site_header_js
from cookie_consent import get_consent_banner_html
from pricing import (
    PRICE_PER_WEEK,
    RACE_PLAN_DELIVERY_HOURS,
    RACE_PLAN_REFUND_DAYS,
)

OUTPUT_DIR = Path(__file__).parent / "output"
WEB_DIR = Path(__file__).resolve().parent.parent / "web"
START_JS_PATH = WEB_DIR / "training-plans-start.js"
DETAILS_JS_PATH = WEB_DIR / "training-plans-details.js"

START_PATH = "/training-plans/start/"
DETAILS_PATH = "/training-plans/details/"
START_URL = SITE_BASE_URL + START_PATH
DETAILS_URL = SITE_BASE_URL + DETAILS_PATH


def esc(text) -> str:
    return html.escape(str(text)) if text else ""


# ── CSS (Desert Editorial: warm paper, gold hairlines, square corners) ──


def build_intake_css() -> str:
    return f"""<style>
{get_font_face_css()}
{get_site_header_css()}
.gg-pi {{
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-dark-brown);
  font-family: var(--gg-font-editorial);
  padding: var(--gg-spacing-2xl) var(--gg-spacing-md) var(--gg-spacing-3xl);
}}
.gg-pi-inner {{ max-width: 680px; margin: 0 auto; }}
.gg-pi-kicker {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  text-transform: uppercase;
  color: var(--gg-color-gold);
  border-bottom: 1px solid var(--gg-color-gold);
  display: inline-block;
  padding-bottom: var(--gg-spacing-2xs);
  margin: 0 0 var(--gg-spacing-md);
}}
.gg-pi h1 {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(30px, 6vw, 44px);
  font-weight: var(--gg-font-weight-bold);
  line-height: var(--gg-line-height-tight);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-sm);
}}
.gg-pi h2 {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs);
}}
.gg-pi-lede, .gg-pi p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-lg);
}}
.gg-pi-card {{
  border-top: 1px solid var(--gg-color-gold);
  border-bottom: 1px solid var(--gg-color-gold);
  padding: var(--gg-spacing-lg) 0;
  margin: 0 0 var(--gg-spacing-lg);
}}
.gg-pi label, .gg-pi .gg-pi-label {{
  display: block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-2xs);
}}
.gg-pi .gg-radio-option label, .gg-pi .gg-checkbox-option label {{
  display: inline;
  text-transform: none;
  letter-spacing: normal;
  font-weight: var(--gg-font-weight-regular);
  font-size: var(--gg-font-size-sm);
}}
.gg-pi .required {{ color: var(--gg-color-gold); }}
.gg-pi input[type="text"], .gg-pi input[type="email"], .gg-pi input[type="date"],
.gg-pi input[type="number"], .gg-pi select, .gg-pi textarea {{
  width: 100%;
  box-sizing: border-box;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-white);
  border: 1px solid var(--gg-color-tan);
  border-radius: 0;
  padding: var(--gg-spacing-xs) var(--gg-spacing-sm);
  min-height: 44px;
}}
.gg-pi textarea {{ min-height: 110px; resize: vertical; }}
.gg-pi input:focus, .gg-pi select:focus, .gg-pi textarea:focus {{
  outline: 2px solid var(--gg-color-gold);
  outline-offset: 0;
  border-color: var(--gg-color-gold);
}}
.gg-form-group {{ margin: 0 0 var(--gg-spacing-md); min-width: 0; }}
.gg-form-row {{ display: grid; grid-template-columns: 1fr 1fr; gap: var(--gg-spacing-md); }}
.gg-form-row.triple {{ grid-template-columns: repeat(3, 1fr); }}
.gg-form-row.quad {{ grid-template-columns: repeat(4, 1fr); }}
.gg-form-row.dual {{ grid-template-columns: 1fr 1fr; }}
.gg-height-row {{ display: flex; align-items: center; gap: var(--gg-spacing-2xs); }}
.gg-height-row input {{ min-width: 0; }}
.gg-height-row span {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); }}
.gg-radio-group, .gg-checkbox-group {{ display: flex; flex-wrap: wrap; gap: var(--gg-spacing-xs); }}
.gg-radio-option, .gg-checkbox-option {{
  display: flex; align-items: center; gap: var(--gg-spacing-2xs);
  border: 1px solid var(--gg-color-tan);
  background: var(--gg-color-white);
  padding: var(--gg-spacing-2xs) var(--gg-spacing-sm);
  min-height: 40px;
}}
.gg-pi-help {{
  display: block;
  margin-top: var(--gg-spacing-2xs);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-secondary-brown);
}}
.gg-hp-field {{ position: absolute; left: -9999px; width: 1px; height: 1px; }}
.gg-pi-btn {{
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-light-gold);
  border: 1px solid var(--gg-color-gold);
  border-radius: 0;
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  min-height: 48px;
  cursor: pointer;
  transition: background var(--gg-transition-hover);
}}
.gg-pi-btn:hover, .gg-pi-btn:focus-visible {{ background: var(--gg-color-gold); }}
.gg-pi-btn:disabled {{ cursor: wait; background: var(--gg-color-sand); }}
.gg-pi-btn-quiet {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-primary-brown);
  background: transparent;
  border: 1px solid var(--gg-color-gold);
  border-radius: 0;
  padding: var(--gg-spacing-xs) var(--gg-spacing-md);
  min-height: 44px;
  cursor: pointer;
}}
.gg-pi-btn-quiet:disabled {{ color: var(--gg-color-tan); cursor: default; }}
.gg-pi-quote {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-dark-brown);
  border-left: 3px solid var(--gg-color-gold);
  padding: var(--gg-spacing-2xs) 0 var(--gg-spacing-2xs) var(--gg-spacing-sm);
  margin: 0 0 var(--gg-spacing-sm);
}}
.gg-pi-min-note {{ font-size: var(--gg-font-size-sm); color: var(--gg-color-secondary-brown); margin: 0 0 var(--gg-spacing-md); }}
.gg-pi-terms {{ font-size: var(--gg-font-size-sm); color: var(--gg-color-secondary-brown); margin-top: var(--gg-spacing-sm); }}
.gg-pi-message {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-error);
  border: 1px solid var(--gg-color-error);
  background: var(--gg-color-white);
  padding: var(--gg-spacing-sm);
  margin: var(--gg-spacing-md) 0;
}}
.gg-pd-progress {{ margin: 0 0 var(--gg-spacing-lg); }}
.gg-pd-progress-track {{ height: 4px; background: var(--gg-color-sand); border-bottom: 1px solid var(--gg-color-gold); }}
.gg-pd-progress-fill {{ height: 4px; width: 20%; background: var(--gg-color-gold); transition: width var(--gg-transition-hover); }}
.gg-pd-progress-label {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-primary-brown);
  margin-top: var(--gg-spacing-xs);
  display: flex; justify-content: space-between; gap: var(--gg-spacing-sm);
}}
.gg-pd-page h2 {{ border-bottom: 1px solid var(--gg-color-gold); padding-bottom: var(--gg-spacing-xs); margin-bottom: var(--gg-spacing-sm); }}
.gg-pd-nav {{ display: flex; justify-content: space-between; align-items: center; gap: var(--gg-spacing-sm); margin-top: var(--gg-spacing-lg); border-top: 1px solid var(--gg-color-gold); padding-top: var(--gg-spacing-md); }}
.gg-pd-nav .gg-pi-btn {{ margin-left: auto; }}
.gg-pd-a-race {{ border: 1px solid var(--gg-color-gold); background: var(--gg-color-white); padding: var(--gg-spacing-md); margin: 0 0 var(--gg-spacing-md); }}
.gg-pd-a-race-name {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); font-weight: var(--gg-font-weight-bold); }}
.gg-pd-a-race-date {{ font-family: var(--gg-font-editorial); color: var(--gg-color-secondary-brown); margin-bottom: var(--gg-spacing-sm); }}
.gg-race-entry {{ border: 1px solid var(--gg-color-tan); background: var(--gg-color-white); padding: var(--gg-spacing-md); margin: 0 0 var(--gg-spacing-md); }}
.gg-race-entry-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--gg-spacing-sm); }}
.gg-race-number {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; }}
.gg-remove-race {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); background: none; border: none; color: var(--gg-color-secondary-brown); text-decoration: underline; cursor: pointer; min-height: 44px; }}
.gg-race-fields {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0 var(--gg-spacing-md); }}
.gg-calculated {{ font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-sm); border-left: 3px solid var(--gg-color-gold); padding-left: var(--gg-spacing-sm); }}
.gg-pd-save-status {{ font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); color: var(--gg-color-secondary-brown); }}
@media (max-width: 640px) {{
  .gg-form-row, .gg-form-row.triple, .gg-form-row.quad, .gg-form-row.dual, .gg-race-fields {{ grid-template-columns: 1fr; }}
  .gg-pi-btn {{ width: 100%; }}
}}
</style>"""


# ── Step 1 ───────────────────────────────────────────────────


def build_start_content() -> str:
    return f'''<main class="gg-pi" id="gg-plan-start">
  <div class="gg-pi-inner">
    <div class="gg-pi-kicker">Custom training plan</div>
    <h1>Your race. Your plan.</h1>
    <p class="gg-pi-lede">Four answers to start. Your race date sets the price: {esc(PRICE_PER_WEEK)} a week from now to race day.</p>

    <form id="gg-plan-start-form" class="gg-pi-card" novalidate>
      <input type="text" name="_honeypot" class="gg-hp-field" tabindex="-1" autocomplete="off" aria-hidden="true">
      <div class="gg-form-row">
        <div class="gg-form-group">
          <label for="gg-ps-race">Race <span class="required">*</span></label>
          <input type="text" id="gg-ps-race" name="race_name" required placeholder="e.g., Unbound 200" autocomplete="off">
        </div>
        <div class="gg-form-group">
          <label for="gg-ps-date">Race date <span class="required">*</span></label>
          <input type="date" id="gg-ps-date" name="race_date" required>
        </div>
      </div>
      <p class="gg-pi-quote" id="gg-ps-quote" aria-live="polite" style="display: none;"></p>
      <p class="gg-pi-min-note" id="gg-ps-min-note" style="display: none;"></p>
      <div class="gg-form-row">
        <div class="gg-form-group">
          <label for="gg-ps-name">Name <span class="required">*</span></label>
          <input type="text" id="gg-ps-name" name="name" required placeholder="Your name" autocomplete="name">
        </div>
        <div class="gg-form-group">
          <label for="gg-ps-email">Email <span class="required">*</span></label>
          <input type="email" id="gg-ps-email" name="email" required placeholder="you@email.com" autocomplete="email">
        </div>
      </div>
      <button type="submit" class="gg-pi-btn" id="gg-ps-submit">BUILD MY PLAN &rarr;</button>
      <p class="gg-pi-terms"><span id="gg-ps-terms-price">{esc(PRICE_PER_WEEK)} a week to race day</span>, paid once. No subscription. Full refund within {RACE_PLAN_REFUND_DAYS} days. Next, about 8 minutes of questions so the plan fits you. Nothing gets built until you&rsquo;re done.</p>
      <div id="gg-ps-message" class="gg-pi-message" role="alert" style="display: none;"></div>
    </form>
  </div>
</main>'''


# ── Step 2 ───────────────────────────────────────────────────
# Same input names and option values as web/training-plans-questionnaire.html
# (tests/test_plan_intake_pages.py checks), minus name, email and the A-race
# name and date, which come from step 1.

_DAYS = (("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"),
         ("thu", "Thursday"), ("fri", "Friday"), ("sat", "Saturday"), ("sun", "Sunday"))


def _day_checkboxes(name: str, prefix: str, flexible: bool) -> str:
    rows = [
        f'<div class="gg-checkbox-option"><input type="checkbox" name="{name}" id="{prefix}-{short}" value="{full}">'
        f'<label for="{prefix}-{short}">{short.capitalize()}</label></div>'
        for short, full in _DAYS
    ]
    if flexible:
        rows.append(f'<div class="gg-checkbox-option"><input type="checkbox" name="{name}" id="{prefix}-flex" value="Flexible">'
                    f'<label for="{prefix}-flex">Flexible</label></div>')
    return "\n            ".join(rows)


def _radios(name: str, prefix: str, options, required: bool) -> str:
    out = []
    for i, (value, label) in enumerate(options):
        req = " required" if required and i == 0 else ""
        rid = f"{prefix}-{i}"
        out.append(f'<div class="gg-radio-option"><input type="radio" name="{name}" id="{rid}" value="{esc(value)}"{req}>'
                   f'<label for="{rid}">{label}</label></div>')
    return "\n            ".join(out)


def build_details_form() -> str:
    page_about = '''<section class="gg-pd-page" data-title="About you">
        <h2>About you</h2>
        <p>Used for zones and recovery. Nothing here is shared.</p>
        <div class="gg-form-row quad">
          <div class="gg-form-group">
            <label>Sex <span class="required">*</span></label>
            <select name="sex" required>
              <option value="">Select</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>
          <div class="gg-form-group">
            <label>Age <span class="required">*</span></label>
            <input type="number" name="age" required min="16" max="90" placeholder="35">
          </div>
          <div class="gg-form-group">
            <label>Weight (lbs) <span class="required">*</span></label>
            <input type="number" name="weight" required min="80" max="350" placeholder="165">
          </div>
          <div class="gg-form-group">
            <label>Height <span class="required">*</span></label>
            <div class="gg-height-row">
              <input type="number" name="heightFeet" required min="4" max="7" placeholder="5" aria-label="Height, feet">
              <span>ft</span>
              <input type="number" name="heightInches" required min="0" max="11" placeholder="10" aria-label="Height, inches">
              <span>in</span>
            </div>
          </div>
        </div>

        <div class="gg-form-row dual" id="cycle-row" style="display: none;">
          <div class="gg-form-group">
            <label>Menstrual Cycle Status</label>
            <select name="cycleStatus">
              <option value="">Select</option>
              <option value="regular">Regular cycle</option>
              <option value="irregular">Irregular cycle</option>
              <option value="hormonal-bc">Hormonal birth control</option>
              <option value="iud">IUD (hormonal)</option>
              <option value="iud-copper">IUD (copper / non-hormonal)</option>
              <option value="perimenopause">Perimenopause</option>
              <option value="postmenopause">Postmenopause</option>
              <option value="prefer-not">Prefer not to say</option>
            </select>
          </div>
          <div class="gg-form-group">
            <label>Track Your Cycle?</label>
            <select name="cycleTracking">
              <option value="">Select</option>
              <option value="yes-app">Yes (app)</option>
              <option value="yes-manual">Yes (manual)</option>
              <option value="no">No</option>
            </select>
          </div>
        </div>

        <div class="gg-form-row triple">
          <div class="gg-form-group">
            <label>Years Cycling <span class="required">*</span></label>
            <select name="yearsCycling" required>
              <option value="">Select</option>
              <option value="&lt;1">&lt;1 year</option>
              <option value="1-2">1-2 years</option>
              <option value="3-5">3-5 years</option>
              <option value="5-10">5-10 years</option>
              <option value="10+">10+ years</option>
            </select>
          </div>
          <div class="gg-form-group">
            <label>Typical Sleep <span class="required">*</span></label>
            <select name="typicalSleep" required>
              <option value="">Select</option>
              <option value="excellent">Excellent (8+ hrs)</option>
              <option value="good">Good (7-8 hrs)</option>
              <option value="fair">Fair (6-7 hrs)</option>
              <option value="poor">Poor (&lt;6 hrs)</option>
            </select>
          </div>
          <div class="gg-form-group">
            <label>Life Stress Level <span class="required">*</span></label>
            <select name="stressLevel" required>
              <option value="">Select</option>
              <option value="low">Low</option>
              <option value="moderate">Moderate</option>
              <option value="high">High</option>
              <option value="very-high">Very High</option>
            </select>
          </div>
        </div>

        <div class="gg-form-row dual">
          <div class="gg-form-group">
            <label>Prior Structured Plan Experience</label>
            <select name="priorPlanExperience">
              <option value="">Select</option>
              <option value="none">Never followed a plan</option>
              <option value="generic">Used a generic/free plan</option>
              <option value="app">Used an app (TrainerRoad, Zwift, etc.)</option>
              <option value="coached">Worked with a coach</option>
              <option value="custom">Had a custom plan built before</option>
            </select>
          </div>
          <div class="gg-form-group">
            <label>Travel During Training Block?</label>
            <select name="travelDuringPlan">
              <option value="">Select</option>
              <option value="none">No significant travel</option>
              <option value="short">Short trip (2-4 days)</option>
              <option value="week">Week-long trip</option>
              <option value="multi">Multiple trips</option>
              <option value="frequent">Frequent travel (work)</option>
            </select>
          </div>
        </div>
        <div class="gg-form-group" id="travelDatesGroup" style="display: none;">
          <label>Travel Dates (if known)</label>
          <input type="text" name="travelDates" placeholder="e.g. 2026-09-03 to 2026-09-08, 2026-10-15" autocomplete="off">
          <span class="gg-pi-help">Dates or ranges (YYYY-MM-DD), comma-separated. Your plan will schedule easy shakeout days around them.</span>
        </div>
      </section>'''

    page_races = '''<section class="gg-pd-page" data-title="Races" hidden>
        <h2>Races</h2>
        <p>Your A-race is set from checkout. Add any B or C races on the way to it.</p>
        <div class="gg-pd-a-race">
          <div class="gg-pi-label">A-race (main goal)</div>
          <div class="gg-pd-a-race-name" id="gg-pd-a-name"></div>
          <div class="gg-pd-a-race-date" id="gg-pd-a-date"></div>
          <div class="gg-form-row">
            <div class="gg-form-group">
              <label>Distance</label>
              <select name="race_a_distance">
                <option value="">Select</option>
                <option value="50">~50 mi</option>
                <option value="75">~75 mi</option>
                <option value="100">~100 mi</option>
                <option value="130">~130 mi</option>
                <option value="150">~150 mi</option>
                <option value="200">200+ mi</option>
              </select>
            </div>
            <div class="gg-form-group">
              <label>Goal</label>
              <select name="race_a_goal">
                <option value="">Select</option>
                <option value="survive">Survive</option>
                <option value="finish-strong">Finish Strong</option>
                <option value="compete">Compete</option>
                <option value="podium">Podium</option>
              </select>
            </div>
          </div>
        </div>
        <div id="races-container"></div>
        <button type="button" id="add-race-btn" class="gg-pi-btn-quiet">+ Add a B or C race</button>
      </section>'''

    ride_opts = (("<2hrs", "&lt;2 hrs"), ("2-3hrs", "2-3 hrs"), ("3-4hrs", "3-4 hrs"),
                 ("4-5hrs", "4-5 hrs"), ("5-6hrs", "5-6 hrs"), ("6+hrs", "6+ hrs"))
    metric_opts = (("power", "Power"), ("hr", "Heart Rate"), ("both", "Both"), ("rpe", "Neither"))
    page_fitness = f'''<section class="gg-pd-page" data-title="Fitness" hidden>
        <h2>Fitness</h2>
        <p>Where you're starting from. No power meter? Heart rate works.</p>
        <div class="gg-form-group">
          <label>Longest ride in the past month? <span class="required">*</span></label>
          <div class="gg-radio-group">
            {_radios("recentRideDuration", "ride", ride_opts, required=True)}
          </div>
        </div>
        <div class="gg-form-group">
          <label>Do you train with power or heart rate?</label>
          <div class="gg-radio-group">
            {_radios("powerOrHr", "metric", metric_opts, required=False)}
          </div>
        </div>
        <div id="powerFields" style="display: none;">
          <div class="gg-form-group">
            <label>FTP (watts)</label>
            <input type="number" name="ftp" id="ftpInput" min="50" max="500" placeholder="e.g., 250">
          </div>
          <div id="pwCalc" class="gg-calculated" style="display: none;">
            Estimated W/kg: <span id="wkgValue">--</span> &nbsp;|&nbsp; Category: <span id="catValue">--</span>
          </div>
        </div>
        <div id="hrFields" style="display: none;">
          <div class="gg-form-row triple">
            <div class="gg-form-group">
              <label>Max HR (bpm)</label>
              <input type="number" name="maxHr" min="100" max="220" placeholder="e.g., 185">
            </div>
            <div class="gg-form-group">
              <label>Threshold HR (bpm)</label>
              <input type="number" name="lthr" min="80" max="200" placeholder="e.g., 165">
            </div>
            <div class="gg-form-group">
              <label>Resting HR (bpm)</label>
              <input type="number" name="restingHr" min="30" max="100" placeholder="e.g., 52">
            </div>
          </div>
        </div>
      </section>'''

    page_schedule = f'''<section class="gg-pd-page" data-title="Schedule" hidden>
        <h2>Schedule</h2>
        <p>When and how much you can train. The plan fits the week you have, not the one you wish you had.</p>
        <div class="gg-form-row">
          <div class="gg-form-group">
            <label>Weekly Training Hours <span class="required">*</span></label>
            <select name="weeklyHours" required>
              <option value="">Select</option>
              <option value="3-5">3-5 hours</option>
              <option value="5-7">5-7 hours</option>
              <option value="7-10">7-10 hours</option>
              <option value="10-12">10-12 hours</option>
              <option value="12-15">12-15 hours</option>
              <option value="15+">15+ hours</option>
            </select>
          </div>
          <div class="gg-form-group">
            <label>Indoor Trainer Access <span class="required">*</span></label>
            <select name="trainerType" required>
              <option value="">Select</option>
              <option value="smart">Smart Trainer</option>
              <option value="basic">Basic Trainer</option>
              <option value="outdoor">Outdoor Only</option>
            </select>
          </div>
        </div>
        <div class="gg-form-group">
          <label>Preferred Long Ride Day(s) <span class="required">*</span></label>
          <div class="gg-checkbox-group" id="longRideDays">
            {_day_checkboxes("longRideDays", "long", flexible=True)}
          </div>
        </div>
        <div class="gg-form-group">
          <label>Preferred Hard Interval Day(s) <span class="required">*</span></label>
          <div class="gg-checkbox-group" id="intervalDays">
            {_day_checkboxes("intervalDays", "int", flexible=True)}
          </div>
        </div>
        <div class="gg-form-group">
          <label>Required Off Days (if any)</label>
          <div class="gg-checkbox-group" id="daysOff">
            {_day_checkboxes("daysOff", "off", flexible=False)}
          </div>
        </div>
      </section>'''

    strength_opts = (("none", "None"), ("occasional", "Occasional"), ("1x-week", "1x/week"),
                     ("2x-week", "2x/week"), ("dedicated", "Dedicated Program"))
    page_strength = f'''<section class="gg-pd-page" data-title="Strength and notes" hidden>
        <h2>Strength and notes</h2>
        <div class="gg-form-group">
          <label>Current Strength Training <span class="required">*</span></label>
          <div class="gg-radio-group">
            {_radios("currentStrength", "str", strength_opts, required=True)}
          </div>
        </div>
        <div class="gg-form-row">
          <div class="gg-form-group">
            <label>Include Strength in Plan? <span class="required">*</span></label>
            <select name="includeStrength" required>
              <option value="">Select</option>
              <option value="yes">Yes, include it</option>
              <option value="no">No, I'll handle it separately</option>
              <option value="your-call">Your call</option>
            </select>
          </div>
          <div class="gg-form-group">
            <label>Equipment Available</label>
            <select name="strengthEquipment">
              <option value="">Select</option>
              <option value="full-gym">Full Gym</option>
              <option value="home-basic">Home - Basic (dumbbells, bands)</option>
              <option value="home-full">Home - Full Setup</option>
              <option value="bodyweight">Bodyweight Only</option>
              <option value="none">None</option>
            </select>
          </div>
        </div>
        <div class="gg-form-group">
          <label>Injuries or Limitations</label>
          <textarea name="injuries" placeholder="Any current or past injuries, physical limitations, or health considerations I should know about?"></textarea>
        </div>
        <div class="gg-form-group">
          <label>Anything Else?</label>
          <textarea name="additionalNotes" placeholder="Other context, goals, concerns, or questions..."></textarea>
        </div>
      </section>'''

    return f'''<form id="gg-training-form" novalidate>
      <input type="text" name="_honeypot" class="gg-hp-field" tabindex="-1" autocomplete="off" aria-hidden="true">
      {page_about}
      {page_races}
      {page_fitness}
      {page_schedule}
      {page_strength}
      <div id="gg-pd-message" class="gg-pi-message" role="alert" style="display: none;"></div>
      <div class="gg-pd-nav">
        <button type="button" class="gg-pi-btn-quiet" id="gg-pd-back" hidden>&larr; Back</button>
        <button type="button" class="gg-pi-btn" id="gg-pd-next">NEXT &rarr;</button>
        <button type="submit" class="gg-pi-btn" id="gg-pd-submit" data-label="SEND MY ANSWERS" hidden>SEND MY ANSWERS</button>
      </div>
    </form>'''


def build_details_content() -> str:
    return f'''<main class="gg-pi" id="gg-plan-details" data-delivery-hours="{RACE_PLAN_DELIVERY_HOURS}">
  <div class="gg-pi-inner">
    <div data-view="loading">
      <div class="gg-pi-kicker">Custom training plan</div>
      <p>Loading your questions&hellip;</p>
    </div>

    <div data-view="form" hidden>
      <div class="gg-pi-kicker">Step 2 of 2</div>
      <h1 id="gg-pd-hello">Thanks. You&rsquo;re paid up.</h1>
      <p class="gg-pi-lede"><span id="gg-pd-race-line"></span></p>
      <p id="gg-pd-paid-note" hidden>Your payment is still confirming. Start now; nothing is lost.</p>
      <p>About 8 minutes of questions so the plan fits you. Nothing gets built until you&rsquo;re done. Answers save as you go.</p>
      <div class="gg-pd-progress" id="gg-pd-progress">
        <div class="gg-pd-progress-track"><div class="gg-pd-progress-fill" id="gg-pd-progress-fill"></div></div>
        <div class="gg-pd-progress-label"><span id="gg-pd-progress-label">Step 1 of 5: About you</span><span class="gg-pd-save-status" id="gg-pd-save-status" aria-live="polite"></span></div>
      </div>
      {build_details_form()}
    </div>

    <div data-view="done" hidden>
      <div class="gg-pi-kicker">Custom training plan</div>
      <h1>Got it. Your plan is building.</h1>
      <p id="gg-pd-done-line"></p>
      <p>Questions or changes: reply to your receipt email.</p>
    </div>

    <div data-view="invalid" hidden>
      <div class="gg-pi-kicker">Custom training plan</div>
      <h1>This link isn&rsquo;t valid.</h1>
      <p>Reply to your receipt email and I&rsquo;ll send you the right one.</p>
    </div>

    <div data-view="error" hidden>
      <div class="gg-pi-kicker">Custom training plan</div>
      <h1>Your questions didn&rsquo;t load.</h1>
      <p>Refresh the page. If it happens again, reply to your receipt email.</p>
    </div>
  </div>
</main>
<noscript><p class="gg-pi-inner">This page needs JavaScript. Reply to your receipt email and I&rsquo;ll take your answers there.</p></noscript>'''


# ── Page assembly ────────────────────────────────────────────

# Runs before the GA4 snippet on the step-2 page: the link token is a
# bearer credential, so it moves to sessionStorage and leaves the address
# bar before the first page_view can record the URL. The address is only
# scrubbed once the token is safely stored.
TOKEN_SCRUB_HEAD_JS = (
    "<script>(function(){try{var u=new URL(window.location.href);"
    "var t=u.searchParams.get('t');if(!t)return;"
    "sessionStorage.setItem('gg_tp_details_token',t);"
    "if(sessionStorage.getItem('gg_tp_details_token')!==t)return;"
    "u.searchParams.delete('t');"
    "history.replaceState(null,'',u.pathname+u.search+u.hash);"
    "}catch(e){}})();</script>"
)

PAGES = {
    "start": {
        "title": "Build Your Plan | Gravel God Cycling",
        "description": "Start your custom gravel training plan: your race, your date, one price.",
        "canonical": START_PATH,
        "builder": build_start_content,
        "js_path": START_JS_PATH,
        "output_path": "plan-start.html",
    },
    "details": {
        "title": "Your Plan Details | Gravel God Cycling",
        "description": "The questions that make your training plan fit you.",
        "canonical": DETAILS_PATH,
        "builder": build_details_content,
        "js_path": DETAILS_JS_PATH,
        "output_path": "plan-details.html",
        "pre_ga4_head": TOKEN_SCRUB_HEAD_JS,
    },
}


def generate_page(page_key: str, external_assets: dict | None = None) -> str:
    page = PAGES[page_key]
    canonical_url = SITE_BASE_URL + page["canonical"]
    if external_assets:
        page_css = external_assets["css_tag"]
        inline_js = external_assets["js_tag"]
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()
    page_js = page["js_path"].read_text(encoding="utf-8")
    if "</script" in page_js.lower():
        raise ValueError(f"{page['js_path']} contains </script>; it can't be inlined")

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(page['title'])}</title>
  <meta name="description" content="{esc(page['description'])}">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <meta property="og:title" content="{esc(page['title'])}">
  <meta property="og:description" content="{esc(page['description'])}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:site_name" content="Gravel God Cycling">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {get_preload_hints()}
  {page_css}
  {build_intake_css()}
  {page.get('pre_ga4_head', '')}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>
<div class="gg-neo-brutalist-page">
  {get_site_header_html(active="products")}
  {page['builder']()}
  {get_mega_footer_html()}
</div>
{inline_js}
<script>
{page_js}
</script>
''' + '<script>' + get_site_header_js() + '</script>' + get_consent_banner_html() + '''
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate the two-step plan questionnaire pages")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR),
                        help="Output directory (default: wordpress/output)")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = write_shared_assets(output_dir)

    for key, page in PAGES.items():
        page_html = generate_page(key, external_assets=assets)
        out = output_dir / page["output_path"]
        out.write_text(page_html, encoding="utf-8")
        print(f"  Generated {out.name} ({len(page_html):,} bytes)")


if __name__ == "__main__":
    main()
