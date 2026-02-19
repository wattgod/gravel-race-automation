#!/usr/bin/env python3
"""
Generate the Gravel God Coaching landing page in neo-brutalist style.

Consolidates both service tiers (Custom Training Plans + 1:1 Coaching) into
a single conversion-optimized page at /coaching/. Replaces the old WordPress/
Elementor page and the non-brand-compliant /training-plans/ page.

Uses brand tokens exclusively — zero hardcoded hex, no border-radius, no
box-shadow, no bounce easing, no entrance animations.

Usage:
    python generate_coaching.py
    python generate_coaching.py --output-dir ./output
"""

import argparse
import html
import json
from pathlib import Path

from generate_neo_brutalist import (
    GA_MEASUREMENT_ID,
    SITE_BASE_URL,
    get_page_css,
    build_inline_js,
    write_shared_assets,
)
from brand_tokens import get_ab_head_snippet, get_preload_hints
from generate_about import _testimonial_data

OUTPUT_DIR = Path(__file__).parent / "output"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_INDEX_PATH = PROJECT_ROOT / "web" / "race-index.json"

# ── Constants ─────────────────────────────────────────────────

PRICE_PER_WEEK = 15
PRICE_CAP = 249
QUESTIONNAIRE_URL = f"{SITE_BASE_URL}/coaching/apply/"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


def load_race_count() -> int:
    """Load the race count from race-index.json."""
    if RACE_INDEX_PATH.exists():
        data = json.loads(RACE_INDEX_PATH.read_text(encoding="utf-8"))
        return len(data)
    return 328  # fallback


# ── Page sections ─────────────────────────────────────────────


def build_nav() -> str:
    return f'''<header class="gg-site-header">
    <div class="gg-site-header-inner">
      <a href="{SITE_BASE_URL}/" class="gg-site-header-logo">
        <img src="https://gravelgodcycling.com/wp-content/uploads/2021/09/cropped-Gravel-God-logo.png" alt="Gravel God" width="50" height="50">
      </a>
      <nav class="gg-site-header-nav">
        <a href="{SITE_BASE_URL}/gravel-races/">RACES</a>
        <a href="{SITE_BASE_URL}/coaching/" aria-current="page">COACHING</a>
        <a href="{SITE_BASE_URL}/articles/">ARTICLES</a>
        <a href="{SITE_BASE_URL}/about/">ABOUT</a>
      </nav>
    </div>
  </header>
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">Coaching</span>
  </div>'''


def build_hero(race_count: int) -> str:
    return f'''<div class="gg-hero gg-coach-hero" id="hero">
    <div class="gg-hero-tier" style="background:var(--gg-color-gold)">COACHING</div>
    <h1>Stop Guessing. Start Training.</h1>
    <p class="gg-hero-tagline">Race-specific training plans built from your schedule, your fitness, and the actual demands of your course. Or apply for 1:1 coaching if you want a human in your corner.</p>
    <div class="gg-coach-hero-cta">
      <a href="#tiers" class="gg-coach-btn gg-coach-btn--gold" data-cta="hero_see_options">SEE OPTIONS</a>
      <a href="#pricing" class="gg-coach-btn gg-coach-btn--secondary" data-cta="hero_pricing">VIEW PRICING</a>
    </div>
    <div class="gg-coach-stat-bar">
      <div class="gg-coach-stat-item">
        <strong>{race_count}</strong>
        <span>Races in Database</span>
      </div>
      <div class="gg-coach-stat-item">
        <strong>$2/day</strong>
        <span>Average Cost</span>
      </div>
      <div class="gg-coach-stat-item">
        <strong>Same Day</strong>
        <span>Delivery</span>
      </div>
      <div class="gg-coach-stat-item">
        <strong>1,000+</strong>
        <span>Plans Delivered</span>
      </div>
    </div>
  </div>'''


def build_problem() -> str:
    return '''<div class="gg-section" id="problem">
    <div class="gg-section-header">
      <span class="gg-section-kicker">01</span>
      <h2 class="gg-section-title">The Problem</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-quotes">
        <blockquote class="gg-coach-quote">
          <p>You downloaded a 12-week plan from the internet. It assumed you had 15 hours a week and zero injuries. How&#39;d that go?</p>
        </blockquote>
        <blockquote class="gg-coach-quote">
          <p>Your entry fee was $175. Your hotel is $200. Your flight was $350. And you showed up with a free plan you found on Reddit.</p>
        </blockquote>
        <blockquote class="gg-coach-quote">
          <p>You bonked at mile 80 because your fueling plan was &ldquo;eat when hungry.&rdquo; Your pacing strategy was &ldquo;go hard and hope.&rdquo;</p>
        </blockquote>
      </div>
    </div>
  </div>'''


def build_service_tiers() -> str:
    return f'''<div class="gg-section" id="tiers">
    <div class="gg-section-header">
      <span class="gg-section-kicker">02</span>
      <h2 class="gg-section-title">Choose Your Level</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-tiers">
        <div class="gg-coach-tier-card">
          <div class="gg-coach-tier-header">FREE</div>
          <h3>Race Prep Kit</h3>
          <p class="gg-coach-tier-desc">Race-specific intel: course breakdown, pacing zones, fueling plan, gear checklist. Free for every race in the database.</p>
          <ul class="gg-coach-tier-list">
            <li>Course terrain breakdown</li>
            <li>Pacing strategy by segment</li>
            <li>Hydration &amp; sodium calculator</li>
            <li>Hour-by-hour fueling plan</li>
            <li>Gear checklist</li>
          </ul>
          <a href="{SITE_BASE_URL}/gravel-races/" class="gg-coach-btn" data-cta="tier_prep_kit">BROWSE RACES</a>
        </div>
        <div class="gg-coach-tier-card gg-coach-tier-card--featured">
          <div class="gg-coach-tier-header gg-coach-tier-header--gold">MOST POPULAR</div>
          <h3>Custom Training Plan</h3>
          <p class="gg-coach-tier-desc">Built from your schedule, fitness, and race. Structured workouts on your device. Same-day delivery. ${PRICE_PER_WEEK}/week, capped at ${PRICE_CAP}.</p>
          <ul class="gg-coach-tier-list">
            <li>Everything in Prep Kit</li>
            <li>Structured .zwo workouts</li>
            <li>30+ page custom guide</li>
            <li>Race-optimized nutrition plan</li>
            <li>Heat &amp; altitude protocols</li>
            <li>Custom strength program</li>
            <li>7-day refund guarantee</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="tier_custom_plan">BUILD MY PLAN</a>
        </div>
        <div class="gg-coach-tier-card">
          <div class="gg-coach-tier-header">APPLICATION</div>
          <h3>1:1 Coaching</h3>
          <p class="gg-coach-tier-desc">A human in your corner. Weekly adjustments based on your life, your data, and how you&#39;re actually responding to training. Limited spots.</p>
          <ul class="gg-coach-tier-list">
            <li>Everything in Custom Plan</li>
            <li>Weekly plan adjustments</li>
            <li>Direct message access</li>
            <li>Race-week strategy calls</li>
            <li>Blindspot detection</li>
            <li>Multi-race season planning</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--teal" data-cta="tier_coaching_apply">APPLY</a>
        </div>
      </div>
    </div>
  </div>'''


def build_deliverables() -> str:
    return f'''<div class="gg-section" id="deliverables">
    <div class="gg-section-header">
      <span class="gg-section-kicker">03</span>
      <h2 class="gg-section-title">What You Get</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-deliverables">
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">01</div>
          <div class="gg-coach-deliverable-content">
            <h3>Structured Workouts on Your Device</h3>
            <p>Every workout drops directly into TrainingPeaks, Zwift, Wahoo, or any platform that reads .zwo files. Power targets, cadence prescriptions, riding position cues, and durability efforts that simulate late-race fatigue.</p>
          </div>
        </div>
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">02</div>
          <div class="gg-coach-deliverable-content">
            <h3>30+ Page Custom Training Guide</h3>
            <p>Your power zones. Your fueling protocol. Your race-week countdown. Phase-by-phase breakdown of what you&#39;re building and why. If your race is in the database: suffering zones, terrain breakdown, altitude warnings.</p>
          </div>
        </div>
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">03</div>
          <div class="gg-coach-deliverable-content">
            <h3>Heat &amp; Altitude Training Protocols</h3>
            <p>Racing at 6,700ft? In Kansas in June? The plan includes acclimatization protocols calibrated to your race conditions. Heat adaptation timelines. Altitude adjustment strategies.</p>
          </div>
        </div>
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">04</div>
          <div class="gg-coach-deliverable-content">
            <h3>Race-Optimized Nutrition Plan</h3>
            <p>Fueling protocol matched to your race distance and conditions. Calorie targets per hour. Hydration schedule. Race-morning meal timing. Built from the course profile, not a generic calculator.</p>
          </div>
        </div>
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">05</div>
          <div class="gg-coach-deliverable-content">
            <h3>Custom Strength Training</h3>
            <p>Cycling-specific. Not CrossFit. Exercises that transfer to the bike, scaled to your strength experience. Phases from general strength into race-specific power. Stops when the taper starts.</p>
          </div>
        </div>
      </div>

      <div class="gg-coach-sample-week">
        <div class="gg-coach-sample-label">SAMPLE BUILD WEEK (8 HRS/WK ATHLETE) &mdash; CLICK A SESSION FOR DETAILS</div>
        <div class="gg-coach-sample-grid">
          <div class="gg-coach-sample-day">Mon</div>
          <div class="gg-coach-sample-day">Tue</div>
          <div class="gg-coach-sample-day">Wed</div>
          <div class="gg-coach-sample-day">Thu</div>
          <div class="gg-coach-sample-day">Fri</div>
          <div class="gg-coach-sample-day">Sat</div>
          <div class="gg-coach-sample-day">Sun</div>
          <div class="gg-coach-sample-block gg-coach-block--rest" data-detail="Active recovery or full rest. Strategic &mdash; not lazy. Your body adapts during rest, not during intervals.">Rest</div>
          <div class="gg-coach-sample-block gg-coach-block--intervals" data-detail="4x4min @ 108-120% FTP / RPE 9. Cadence: 100-110rpm, seated on the hoods. Full recovery between efforts. Power targets and cadence cues built into the .zwo file.">VO2max<br>Intervals<br>1hr</div>
          <div class="gg-coach-sample-block gg-coach-block--endurance" data-detail="Zone 2 spin. 55-75% FTP / RPE 3-4. Recovery between hard days. Nasal breathing pace.">Easy<br>Spin<br>45min</div>
          <div class="gg-coach-sample-block gg-coach-block--intervals" data-detail="2x20min @ 88-94% FTP / RPE 7. The workhorse session. Builds sustained power you&#39;ll need at mile 60+. Cadence: 85-95rpm seated on the hoods.">G-Spot<br>1.5hr</div>
          <div class="gg-coach-sample-block gg-coach-block--strength" data-detail="Cycling-specific. Bulgarian split squats, hip hinge work, single-leg stability. Scaled to your equipment and experience level. 40-50min.">Strength<br>45min</div>
          <div class="gg-coach-sample-block gg-coach-block--long" data-detail="Endurance ride with late-ride race-pace efforts &mdash; durability work. 2.5hrs zone 2, then 2x10min at threshold in the drops at 55rpm. Practices holding power on tired legs.">Long<br>Ride<br>3hr</div>
          <div class="gg-coach-sample-block gg-coach-block--rest" data-detail="Full rest before the next training week. Sleep well. Eat well. The plan respects that you have a life outside of cycling.">Rest</div>
        </div>
        <div class="gg-coach-sample-detail" id="gg-coach-sample-detail" style="display:none"></div>
      </div>
    </div>
  </div>'''


def build_how_it_works() -> str:
    return f'''<div class="gg-section" id="how-it-works">
    <div class="gg-section-header">
      <span class="gg-section-kicker">04</span>
      <h2 class="gg-section-title">How It Works</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-steps">
        <div class="gg-coach-step">
          <div class="gg-coach-step-num">01</div>
          <div class="gg-coach-step-body">
            <h3>Tell Me About Your Race</h3>
            <p>Fill out the questionnaire. Your race. Your hours. Your fitness. Your constraints. Five minutes. Be honest &mdash; the plan is only as good as the data.</p>
          </div>
        </div>
        <div class="gg-coach-step">
          <div class="gg-coach-step-num">02</div>
          <div class="gg-coach-step-body">
            <h3>I Build Your Plan</h3>
            <p>Your intake hits the methodology engine. Training approach selected based on your profile. Polarized for time-crunched. Pyramidal for balanced. Block for serious. Matched to your availability and ability.</p>
          </div>
        </div>
        <div class="gg-coach-step">
          <div class="gg-coach-step-num">03</div>
          <div class="gg-coach-step-body">
            <h3>Open Your App. Start Training.</h3>
            <p>The plan drops directly into your TrainingPeaks calendar. Every workout. Every phase. Syncs to Zwift, Wahoo, Garmin. Delivered same day.</p>
          </div>
        </div>
      </div>
      <div style="margin-top:var(--gg-spacing-lg)">
        <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="how_it_works_cta">BUILD MY PLAN</a>
      </div>
    </div>
  </div>'''


def build_testimonials() -> str:
    testimonials = _testimonial_data()
    cards = []
    for name, quote, meta in testimonials:
        cards.append(
            f'<blockquote class="gg-coach-testimonial">'
            f'<p>{esc(quote)}</p>'
            f'<footer><strong>{esc(name)}</strong>'
            f'<span class="gg-coach-testimonial-meta">{meta}</span>'
            f'</footer></blockquote>'
        )
    inner = "\n        ".join(cards)
    return f'''<div class="gg-section" id="results">
    <div class="gg-section-header">
      <span class="gg-section-kicker">05</span>
      <h2 class="gg-section-title">Athlete Results</h2>
    </div>
    <div class="gg-section-body" style="position:relative">
      <div class="gg-coach-carousel" id="gg-coach-carousel">
        <div class="gg-coach-carousel-track">
        {inner}
        </div>
      </div>
      <div class="gg-coach-carousel-nav">
        <button class="gg-coach-carousel-btn" id="gg-coach-prev" aria-label="Previous testimonials">&larr;</button>
        <span class="gg-coach-carousel-count" id="gg-coach-count"></span>
        <button class="gg-coach-carousel-btn" id="gg-coach-next" aria-label="Next testimonials">&rarr;</button>
      </div>
    </div>
  </div>'''


def build_honest_check() -> str:
    return '''<div class="gg-section" id="honest-check">
    <div class="gg-section-header">
      <span class="gg-section-kicker">06</span>
      <h2 class="gg-section-title">Honest Check</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-audience">
        <div class="gg-coach-audience-col">
          <h3 class="gg-coach-audience-heading gg-coach-audience-heading--yes">Buy This If:</h3>
          <ul class="gg-coach-audience-list gg-coach-list--yes">
            <li>You have a race on the calendar and you&#39;re done winging it</li>
            <li>You have 3&ndash;15 hours a week and need every session to count</li>
            <li>You want structure that respects your actual life</li>
            <li>You can follow a plan without someone texting you every morning</li>
            <li>You&#39;re tired of generic plans that assume you&#39;re 25 with 20 hours</li>
          </ul>
        </div>
        <div class="gg-coach-audience-col">
          <h3 class="gg-coach-audience-heading gg-coach-audience-heading--no">Don&#39;t Buy This If:</h3>
          <ul class="gg-coach-audience-list gg-coach-list--no">
            <li>You don&#39;t have a target event</li>
            <li>Your race is in 3 weeks &mdash; not enough time to build anything real</li>
            <li>You need daily accountability to do the work</li>
            <li>You just want someone to tell you you&#39;re doing great</li>
          </ul>
        </div>
      </div>
    </div>
  </div>'''


def build_pricing() -> str:
    return f'''<div class="gg-section" id="pricing">
    <div class="gg-section-header">
      <span class="gg-section-kicker">07</span>
      <h2 class="gg-section-title">Pricing</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-pricing-card">
        <div class="gg-coach-pricing-header">CUSTOM TRAINING PLAN</div>
        <div class="gg-coach-pricing-price">${PRICE_PER_WEEK}<span> / week of training</span></div>
        <ul class="gg-coach-pricing-list">
          <li>Computed from your race date &mdash; pay for exactly what you need</li>
          <li>6-week plan = $90. 12-week plan = $180. 16-week plan = $240</li>
          <li>Capped at ${PRICE_CAP} no matter how long the plan</li>
          <li>Structured .zwo workouts for Zwift/TrainingPeaks/Wahoo</li>
          <li>30+ page custom training guide</li>
          <li>Race-optimized fueling plan</li>
          <li>Custom strength program</li>
          <li>Heat &amp; altitude protocols</li>
          <li>Same-day delivery</li>
        </ul>
        <div class="gg-coach-pricing-cta">
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="pricing_cta">BUILD MY PLAN</a>
        </div>
        <p class="gg-coach-pricing-anchor">That&#39;s $2/day. Your entry fee was $175. Your hotel is $200. Your flight was $350. Don&#39;t show up without a plan.</p>
        <p class="gg-coach-pricing-guarantee">Full refund within 7 days. No questions.</p>
      </div>
    </div>
  </div>'''


def build_faq() -> str:
    faqs = [
        (
            "Do I need a power meter?",
            "Not required. Every workout includes RPE targets so you can train by feel. But a power meter is strongly recommended &mdash; watt targets remove guesswork entirely. Heart rate works as a middle ground.",
        ),
        (
            "What if I don&#39;t know my FTP?",
            "Mark it unknown. Week 1 includes an FTP test protocol. Once you have the number, every zone recalibrates.",
        ),
        (
            "How are workouts delivered?",
            ".zwo files. Load directly into Zwift, TrainingPeaks, or anything that reads the format. Each file has power targets, cadence cues, and coaching text built in. Your guide is a web page &mdash; bookmark it.",
        ),
        (
            "How is the price calculated?",
            f"${PRICE_PER_WEEK} per week of training, computed from your race date. A 6-week plan is $90. A 12-week plan is $180. Anything over 16 weeks caps at ${PRICE_CAP}. You pay for exactly what you need &mdash; no more.",
        ),
        (
            "Is this coaching?",
            "The Custom Plan is a plan, not a relationship. You get the full plan up front and execute it yourself. If you want weekly adjustments and direct access, apply for 1:1 coaching.",
        ),
        (
            "What if my race isn&#39;t in the database?",
            "The training still works. You won&#39;t get race-specific intel (suffering zones, terrain breakdown), but the workouts, phases, and structure are identical.",
        ),
    ]

    items = []
    for q, a in faqs:
        items.append(
            f'<div class="gg-coach-faq-item">'
            f'<div class="gg-coach-faq-q" role="button" tabindex="0" aria-expanded="false">'
            f'{q}'
            f'<span class="gg-coach-faq-toggle" aria-hidden="true">+</span>'
            f'</div>'
            f'<div class="gg-coach-faq-a"><p>{a}</p></div>'
            f'</div>'
        )
    inner = "\n      ".join(items)
    return f'''<div class="gg-section" id="faq">
    <div class="gg-section-header">
      <span class="gg-section-kicker">08</span>
      <h2 class="gg-section-title">FAQ</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-faq-list">
      {inner}
      </div>
    </div>
  </div>'''


def build_final_cta() -> str:
    return f'''<div class="gg-section" id="final-cta">
    <div class="gg-section-body">
      <div class="gg-coach-final-cta">
        <p class="gg-coach-final-hook">You&#39;ve already paid for the race. Don&#39;t waste it.</p>
        <p class="gg-coach-final-sub">Your entry fee, your hotel, your travel, your PTO &mdash; that money is spent. The only variable left is how you show up.</p>
        <div class="gg-coach-final-buttons">
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="final_build_plan">BUILD MY PLAN</a>
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--teal" data-cta="final_apply_coaching">APPLY FOR 1:1 COACHING</a>
        </div>
      </div>
    </div>
  </div>'''


def build_footer() -> str:
    return '''<div class="gg-footer">
    <p class="gg-footer-disclaimer">Gravel God Cycling is an independent editorial and coaching platform. It is not affiliated with, endorsed by, or officially connected to any race organizer, event, or governing body. All ratings represent editorial views based on publicly available information and community research.</p>
  </div>'''


def build_mobile_sticky_cta() -> str:
    return f'''<div class="gg-coach-sticky-cta">
    <a href="{QUESTIONNAIRE_URL}" data-cta="sticky_cta">BUILD MY PLAN &mdash; $2/day</a>
  </div>'''


# ── CSS ───────────────────────────────────────────────────────


def build_coaching_css() -> str:
    """Coaching-page-specific CSS. All gg-coach-* prefix. Brand tokens only."""
    return '''<style>
/* ── Coach hero — light sandwash override ────────── */
.gg-neo-brutalist-page .gg-coach-hero {
  background: var(--gg-color-warm-paper);
  border-bottom: 3px double var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-coach-hero h1 {
  color: var(--gg-color-dark-brown);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-4xl);
  line-height: var(--gg-line-height-tight);
}
.gg-neo-brutalist-page .gg-coach-hero .gg-hero-tagline {
  color: var(--gg-color-secondary-brown);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  line-height: var(--gg-line-height-relaxed);
  max-width: 640px;
}
.gg-neo-brutalist-page .gg-coach-hero-cta {
  display: flex;
  gap: var(--gg-spacing-md);
  margin-top: var(--gg-spacing-lg);
  flex-wrap: wrap;
}

/* ── Stat bar ────────────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-stat-bar {
  display: flex;
  gap: 0;
  border: var(--gg-border-standard);
  border-top: 3px double var(--gg-color-dark-brown);
  border-bottom: 3px double var(--gg-color-dark-brown);
  margin-top: var(--gg-spacing-xl);
  background: var(--gg-color-warm-paper);
  max-width: 600px;
}
.gg-neo-brutalist-page .gg-coach-stat-item {
  flex: 1;
  text-align: center;
  padding: var(--gg-spacing-md) var(--gg-spacing-sm);
  border-right: 1px solid var(--gg-color-tan);
}
.gg-neo-brutalist-page .gg-coach-stat-item:last-child {
  border-right: none;
}
.gg-neo-brutalist-page .gg-coach-stat-item strong {
  display: block;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  line-height: var(--gg-line-height-tight);
}
.gg-neo-brutalist-page .gg-coach-stat-item span {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  color: var(--gg-color-secondary-brown);
}

/* ── Buttons (shared) ────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-btn {
  display: inline-block;
  background: var(--gg-color-primary-brown);
  color: var(--gg-color-warm-paper);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  padding: var(--gg-spacing-sm) var(--gg-spacing-lg);
  border: 3px solid var(--gg-color-primary-brown);
  text-decoration: none;
  text-align: center;
  cursor: pointer;
  transition: background-color var(--gg-transition-hover),
              border-color var(--gg-transition-hover),
              color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-coach-btn:hover {
  background-color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-coach-btn--gold {
  background: var(--gg-color-gold);
  color: var(--gg-color-warm-paper);
  border-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-btn--gold:hover {
  background-color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
}
.gg-neo-brutalist-page .gg-coach-btn--teal {
  background: var(--gg-color-teal);
  color: var(--gg-color-warm-paper);
  border-color: var(--gg-color-teal);
}
.gg-neo-brutalist-page .gg-coach-btn--teal:hover {
  background-color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
}
.gg-neo-brutalist-page .gg-coach-btn--secondary {
  background: transparent;
  color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-coach-btn--secondary:hover {
  background-color: var(--gg-color-sand);
}

/* ── Problem quotes ──────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-quotes {
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-md);
}
.gg-neo-brutalist-page .gg-coach-quote {
  border-left: 4px solid var(--gg-color-gold);
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  background: var(--gg-color-sand);
  margin: 0;
}
.gg-neo-brutalist-page .gg-coach-quote p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  font-weight: var(--gg-font-weight-semibold);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-dark-brown);
  margin: 0;
}

/* ── Service tiers ───────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-tiers {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gg-spacing-md);
}
.gg-neo-brutalist-page .gg-coach-tier-card {
  border: var(--gg-border-standard);
  padding: var(--gg-spacing-lg);
  background: var(--gg-color-warm-paper);
  display: flex;
  flex-direction: column;
  transition: border-color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-coach-tier-card:hover {
  border-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-tier-card--featured {
  border-top: 4px solid var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-tier-header {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-extreme);
  color: var(--gg-color-secondary-brown);
  margin-bottom: var(--gg-spacing-sm);
}
.gg-neo-brutalist-page .gg-coach-tier-header--gold {
  color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-tier-card h3 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
  line-height: var(--gg-line-height-tight);
}
.gg-neo-brutalist-page .gg-coach-tier-desc {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-dark-brown);
  margin-bottom: var(--gg-spacing-md);
}
.gg-neo-brutalist-page .gg-coach-tier-list {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--gg-spacing-lg) 0;
  flex: 1;
}
.gg-neo-brutalist-page .gg-coach-tier-list li {
  padding: var(--gg-spacing-xs) 0;
  padding-left: var(--gg-spacing-lg);
  position: relative;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-dark-brown);
  border-bottom: 1px solid var(--gg-color-tan);
  line-height: var(--gg-line-height-normal);
}
.gg-neo-brutalist-page .gg-coach-tier-list li:last-child {
  border-bottom: none;
}
.gg-neo-brutalist-page .gg-coach-tier-list li::before {
  content: ">";
  position: absolute;
  left: 0;
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-gold);
}

/* ── Deliverables ────────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-deliverables {
  border: var(--gg-border-standard);
}
.gg-neo-brutalist-page .gg-coach-deliverable {
  display: grid;
  grid-template-columns: 60px 1fr;
  border-bottom: var(--gg-border-standard);
}
.gg-neo-brutalist-page .gg-coach-deliverable:last-child {
  border-bottom: none;
}
.gg-neo-brutalist-page .gg-coach-deliverable-num {
  background: var(--gg-color-near-black);
  color: var(--gg-color-sand);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-bold);
  border-right: var(--gg-border-standard);
}
.gg-neo-brutalist-page .gg-coach-deliverable-content {
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  background: var(--gg-color-warm-paper);
}
.gg-neo-brutalist-page .gg-coach-deliverable:nth-child(even) .gg-coach-deliverable-content {
  background: var(--gg-color-sand);
}
.gg-neo-brutalist-page .gg-coach-deliverable-content h3 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
}
.gg-neo-brutalist-page .gg-coach-deliverable-content p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  margin: 0;
}

/* ── Sample week grid ────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-sample-week {
  margin-top: var(--gg-spacing-xl);
  border: var(--gg-border-standard);
  background: var(--gg-color-sand);
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
}
.gg-neo-brutalist-page .gg-coach-sample-label {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  color: var(--gg-color-secondary-brown);
  margin-bottom: var(--gg-spacing-sm);
}
.gg-neo-brutalist-page .gg-coach-sample-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}
.gg-neo-brutalist-page .gg-coach-sample-day {
  text-align: center;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  font-weight: var(--gg-font-weight-bold);
  padding: var(--gg-spacing-xs) var(--gg-spacing-2xs);
  color: var(--gg-color-secondary-brown);
}
.gg-neo-brutalist-page .gg-coach-sample-block {
  text-align: center;
  padding: var(--gg-spacing-sm) var(--gg-spacing-2xs);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-semibold);
  border: 2px solid var(--gg-color-near-black);
  min-height: 70px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  line-height: var(--gg-line-height-normal);
  cursor: pointer;
  transition: border-color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-coach-sample-block:hover {
  border-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-sample-block.gg-coach-active {
  border-color: var(--gg-color-gold);
  border-width: 3px;
}
.gg-neo-brutalist-page .gg-coach-block--rest {
  background: var(--gg-color-white);
  color: var(--gg-color-secondary-brown);
  border-color: var(--gg-color-tan);
}
.gg-neo-brutalist-page .gg-coach-block--endurance {
  background: var(--gg-color-white);
  color: var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-coach-block--intervals {
  background: var(--gg-color-near-black);
  color: var(--gg-color-sand);
}
.gg-neo-brutalist-page .gg-coach-block--strength {
  background: var(--gg-color-primary-brown);
  color: var(--gg-color-sand);
}
.gg-neo-brutalist-page .gg-coach-block--long {
  background: var(--gg-color-near-black);
  color: var(--gg-color-teal);
}
.gg-neo-brutalist-page .gg-coach-sample-detail {
  margin-top: var(--gg-spacing-sm);
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  background: var(--gg-color-white);
  border: 2px solid var(--gg-color-near-black);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-dark-brown);
}

/* ── How it works steps ──────────────────────────── */
.gg-neo-brutalist-page .gg-coach-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.gg-neo-brutalist-page .gg-coach-step {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: var(--gg-spacing-md);
  padding: var(--gg-spacing-md) 0;
  border-bottom: 1px solid var(--gg-color-tan);
}
.gg-neo-brutalist-page .gg-coach-step:last-child {
  border-bottom: none;
}
.gg-neo-brutalist-page .gg-coach-step-num {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-secondary-brown);
  text-align: right;
  padding-top: 2px;
}
.gg-neo-brutalist-page .gg-coach-step-body h3 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
}
.gg-neo-brutalist-page .gg-coach-step-body p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  margin: 0;
}

/* ── Testimonial carousel ────────────────────────── */
.gg-neo-brutalist-page .gg-coach-carousel {
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.gg-neo-brutalist-page .gg-coach-carousel::-webkit-scrollbar {
  display: none;
}
.gg-neo-brutalist-page .gg-coach-carousel-track {
  display: flex;
  gap: var(--gg-spacing-md);
}
.gg-neo-brutalist-page .gg-coach-testimonial {
  flex: 0 0 calc(50% - 8px);
  scroll-snap-align: start;
  background: var(--gg-color-warm-paper);
  border: var(--gg-border-standard);
  padding: var(--gg-spacing-lg) var(--gg-spacing-lg) var(--gg-spacing-md);
  margin: 0;
  position: relative;
  min-height: 200px;
  display: flex;
  flex-direction: column;
}
.gg-neo-brutalist-page .gg-coach-testimonial p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  font-style: italic;
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
  flex: 1;
}
.gg-neo-brutalist-page .gg-coach-testimonial footer {
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-2xs);
  border-top: 1px solid var(--gg-color-tan);
  padding-top: var(--gg-spacing-sm);
}
.gg-neo-brutalist-page .gg-coach-testimonial footer strong {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}
.gg-neo-brutalist-page .gg-coach-testimonial-meta {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}
.gg-neo-brutalist-page .gg-coach-carousel-nav {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--gg-spacing-md);
  margin-top: var(--gg-spacing-md);
}
.gg-neo-brutalist-page .gg-coach-carousel-btn {
  background: var(--gg-color-sand);
  border: var(--gg-border-standard);
  width: 40px;
  height: 40px;
  font-size: 18px;
  line-height: 1;
  color: var(--gg-color-dark-brown);
  cursor: pointer;
  transition: background-color var(--gg-transition-hover),
              border-color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-coach-carousel-btn:hover {
  background-color: var(--gg-color-warm-paper);
  border-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-carousel-count {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  min-width: 80px;
  text-align: center;
}

/* ── Honest check (audience) ─────────────────────── */
.gg-neo-brutalist-page .gg-coach-audience {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-xl);
}
.gg-neo-brutalist-page .gg-coach-audience-heading {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  margin: 0 0 var(--gg-spacing-md) 0;
}
.gg-neo-brutalist-page .gg-coach-audience-heading--yes {
  color: var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-coach-audience-heading--no {
  color: var(--gg-color-secondary-brown);
}
.gg-neo-brutalist-page .gg-coach-audience-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.gg-neo-brutalist-page .gg-coach-audience-list li {
  padding: var(--gg-spacing-sm) 0;
  padding-left: var(--gg-spacing-lg);
  position: relative;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  border-bottom: 1px solid var(--gg-color-tan);
  line-height: var(--gg-line-height-normal);
}
.gg-neo-brutalist-page .gg-coach-audience-list li:last-child {
  border-bottom: none;
}
.gg-neo-brutalist-page .gg-coach-audience-list li::before {
  position: absolute;
  left: 0;
  font-weight: var(--gg-font-weight-bold);
  font-family: var(--gg-font-data);
}
.gg-neo-brutalist-page .gg-coach-list--yes li::before {
  content: ">";
  color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-list--no li::before {
  content: "x";
  color: var(--gg-color-secondary-brown);
}

/* ── Pricing card ────────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-pricing-card {
  border: var(--gg-border-standard);
  max-width: 500px;
  background: var(--gg-color-warm-paper);
}
.gg-neo-brutalist-page .gg-coach-pricing-header {
  background: var(--gg-color-near-black);
  color: var(--gg-color-sand);
  padding: var(--gg-spacing-sm) var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
}
.gg-neo-brutalist-page .gg-coach-pricing-price {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-4xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  padding: var(--gg-spacing-md) var(--gg-spacing-lg) 0;
}
.gg-neo-brutalist-page .gg-coach-pricing-price span {
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-regular);
  color: var(--gg-color-secondary-brown);
}
.gg-neo-brutalist-page .gg-coach-pricing-list {
  list-style: none;
  padding: 0;
  margin: var(--gg-spacing-sm) 0 0;
}
.gg-neo-brutalist-page .gg-coach-pricing-list li {
  padding: var(--gg-spacing-xs) var(--gg-spacing-lg);
  padding-left: calc(var(--gg-spacing-lg) + var(--gg-spacing-md));
  position: relative;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-dark-brown);
  border-top: 1px solid var(--gg-color-tan);
  line-height: var(--gg-line-height-normal);
}
.gg-neo-brutalist-page .gg-coach-pricing-list li::before {
  content: ">";
  position: absolute;
  left: var(--gg-spacing-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-pricing-cta {
  padding: var(--gg-spacing-md) var(--gg-spacing-lg) var(--gg-spacing-sm);
}
.gg-neo-brutalist-page .gg-coach-pricing-cta .gg-coach-btn {
  width: 100%;
  text-align: center;
}
.gg-neo-brutalist-page .gg-coach-pricing-anchor {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  text-align: center;
  padding: 0 var(--gg-spacing-lg) var(--gg-spacing-xs);
  margin: 0;
}
.gg-neo-brutalist-page .gg-coach-pricing-guarantee {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-teal);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  text-align: center;
  padding: 0 var(--gg-spacing-lg) var(--gg-spacing-md);
  margin: 0;
}

/* ── FAQ accordion ───────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-faq-list {
  max-width: 640px;
}
.gg-neo-brutalist-page .gg-coach-faq-item {
  border-bottom: 1px solid var(--gg-color-tan);
}
.gg-neo-brutalist-page .gg-coach-faq-item:first-child {
  border-top: 1px solid var(--gg-color-tan);
}
.gg-neo-brutalist-page .gg-coach-faq-q {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--gg-spacing-sm) 0;
  cursor: pointer;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-dark-brown);
  user-select: none;
  transition: color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-coach-faq-q:hover {
  color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-faq-toggle {
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-bold);
  line-height: 1;
  color: var(--gg-color-dark-brown);
  transition: color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-coach-faq-item.gg-coach-faq-open .gg-coach-faq-toggle {
  color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-coach-faq-a {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease;
}
.gg-neo-brutalist-page .gg-coach-faq-item.gg-coach-faq-open .gg-coach-faq-a {
  max-height: 500px;
  padding-bottom: var(--gg-spacing-sm);
}
.gg-neo-brutalist-page .gg-coach-faq-a p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  line-height: var(--gg-line-height-relaxed);
  margin: 0;
}

/* ── Final CTA ───────────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-final-cta {
  text-align: center;
  padding: var(--gg-spacing-xl) 0;
  border-top: 3px double var(--gg-color-dark-brown);
  border-bottom: 3px double var(--gg-color-dark-brown);
  background: var(--gg-color-sand);
  margin: 0 calc(-1 * var(--gg-spacing-lg));
  padding-left: var(--gg-spacing-lg);
  padding-right: var(--gg-spacing-lg);
}
.gg-neo-brutalist-page .gg-coach-final-hook {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-sm) 0;
  line-height: var(--gg-line-height-tight);
}
.gg-neo-brutalist-page .gg-coach-final-sub {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  color: var(--gg-color-secondary-brown);
  line-height: var(--gg-line-height-relaxed);
  margin: 0 0 var(--gg-spacing-lg) 0;
  max-width: 560px;
  margin-left: auto;
  margin-right: auto;
}
.gg-neo-brutalist-page .gg-coach-final-buttons {
  display: flex;
  gap: var(--gg-spacing-md);
  justify-content: center;
  flex-wrap: wrap;
}

/* ── Mobile sticky CTA ───────────────────────────── */
.gg-neo-brutalist-page .gg-coach-sticky-cta {
  display: none;
}
@media (max-width: 768px) {
  .gg-neo-brutalist-page .gg-coach-sticky-cta {
    display: block;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 999;
    background: var(--gg-color-near-black);
    padding: var(--gg-spacing-sm) var(--gg-spacing-md);
    text-align: center;
    border-top: 3px solid var(--gg-color-gold);
  }
  .gg-neo-brutalist-page .gg-coach-sticky-cta a {
    display: block;
    color: var(--gg-color-sand);
    font-family: var(--gg-font-data);
    font-size: var(--gg-font-size-xs);
    font-weight: var(--gg-font-weight-bold);
    text-transform: uppercase;
    letter-spacing: var(--gg-letter-spacing-wider);
    text-decoration: none;
    padding: var(--gg-spacing-2xs) 0;
  }
}

/* ── Responsive ──────────────────────────────────── */
@media (max-width: 768px) {
  .gg-neo-brutalist-page .gg-coach-hero h1 {
    font-size: var(--gg-font-size-2xl);
  }
  .gg-neo-brutalist-page .gg-coach-stat-bar {
    flex-wrap: wrap;
  }
  .gg-neo-brutalist-page .gg-coach-stat-item {
    flex: 1 1 48%;
    border-bottom: 1px solid var(--gg-color-tan);
  }
  .gg-neo-brutalist-page .gg-coach-stat-item:nth-last-child(-n+2) {
    border-bottom: none;
  }
  .gg-neo-brutalist-page .gg-coach-tiers {
    grid-template-columns: 1fr;
  }
  .gg-neo-brutalist-page .gg-coach-audience {
    grid-template-columns: 1fr;
  }
  .gg-neo-brutalist-page .gg-coach-sample-grid {
    grid-template-columns: repeat(4, 1fr);
  }
  .gg-neo-brutalist-page .gg-coach-testimonial {
    flex: 0 0 calc(100% - 16px);
  }
  .gg-neo-brutalist-page .gg-coach-final-hook {
    font-size: var(--gg-font-size-xl);
  }
  .gg-neo-brutalist-page {
    padding-bottom: 60px;
  }
}
</style>'''


# ── JS ────────────────────────────────────────────────────────


def build_coaching_js() -> str:
    """Interactive JS for coaching page — FAQ, carousel, sample week, GA4 events."""
    return '''<script>
/* FAQ accordion — single-open behavior */
(function() {
  var items = document.querySelectorAll('.gg-coach-faq-item');
  items.forEach(function(item) {
    var q = item.querySelector('.gg-coach-faq-q');
    if (!q) return;
    function toggle() {
      var wasOpen = item.classList.contains('gg-coach-faq-open');
      items.forEach(function(i) { i.classList.remove('gg-coach-faq-open'); });
      if (!wasOpen) {
        item.classList.add('gg-coach-faq-open');
        q.setAttribute('aria-expanded', 'true');
        if (typeof gtag === 'function') gtag('event', 'coaching_faq_open', { question: q.textContent.trim().slice(0, 60) });
      } else {
        q.setAttribute('aria-expanded', 'false');
      }
    }
    q.addEventListener('click', toggle);
    q.addEventListener('keydown', function(e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });
  });
})();

/* Testimonial carousel */
(function() {
  var carousel = document.getElementById('gg-coach-carousel');
  var prev = document.getElementById('gg-coach-prev');
  var next = document.getElementById('gg-coach-next');
  var counter = document.getElementById('gg-coach-count');
  if (!carousel || !prev || !next) return;
  var cards = carousel.querySelectorAll('.gg-coach-testimonial');
  var total = cards.length;
  var perPage = window.innerWidth <= 768 ? 1 : 2;

  function getPage() {
    var scrollLeft = carousel.scrollLeft;
    var cardWidth = cards[0].offsetWidth + 16;
    return Math.round(scrollLeft / (cardWidth * perPage));
  }
  function totalPages() { return Math.ceil(total / perPage); }
  function updateCounter() {
    if (counter) counter.textContent = (getPage() + 1) + ' / ' + totalPages();
  }
  function scrollToPage(page) {
    var cardWidth = cards[0].offsetWidth + 16;
    carousel.scrollTo({ left: page * perPage * cardWidth, behavior: 'smooth' });
  }
  prev.addEventListener('click', function() {
    var page = getPage();
    scrollToPage(page > 0 ? page - 1 : totalPages() - 1);
  });
  next.addEventListener('click', function() {
    var page = getPage();
    scrollToPage(page < totalPages() - 1 ? page + 1 : 0);
  });
  carousel.addEventListener('scroll', updateCounter);
  window.addEventListener('resize', function() {
    perPage = window.innerWidth <= 768 ? 1 : 2;
    updateCounter();
  });
  updateCounter();

  var autoTimer = null;
  var paused = false;
  function autoAdvance() {
    if (paused) return;
    var page = getPage();
    scrollToPage(page < totalPages() - 1 ? page + 1 : 0);
  }
  function startAuto() { autoTimer = setInterval(autoAdvance, 6000); }
  function stopAuto() { clearInterval(autoTimer); }
  carousel.addEventListener('mouseenter', function() { paused = true; });
  carousel.addEventListener('mouseleave', function() { paused = false; });
  prev.addEventListener('click', function() { stopAuto(); startAuto(); });
  next.addEventListener('click', function() { stopAuto(); startAuto(); });
  startAuto();
})();

/* Sample week click-to-reveal */
(function() {
  var blocks = document.querySelectorAll('.gg-coach-sample-block[data-detail]');
  var detail = document.getElementById('gg-coach-sample-detail');
  if (!detail) return;
  blocks.forEach(function(block) {
    block.addEventListener('click', function() {
      var wasActive = block.classList.contains('gg-coach-active');
      blocks.forEach(function(b) { b.classList.remove('gg-coach-active'); });
      if (wasActive) {
        detail.style.display = 'none';
        detail.textContent = '';
      } else {
        block.classList.add('gg-coach-active');
        detail.textContent = block.getAttribute('data-detail');
        detail.style.display = 'block';
        if (typeof gtag === 'function') gtag('event', 'coaching_sample_week_click', { session: block.textContent.trim().replace(/\\n/g, ' ') });
      }
    });
  });
})();

/* Scroll depth tracking */
(function() {
  if (typeof gtag !== 'function' || !('IntersectionObserver' in window)) return;
  var sections = [
    { id: 'hero', label: '0_hero' },
    { id: 'problem', label: '25_problem' },
    { id: 'deliverables', label: '50_deliverables' },
    { id: 'results', label: '75_results' },
    { id: 'final-cta', label: '100_final_cta' }
  ];
  sections.forEach(function(s) {
    var el = document.getElementById(s.id);
    if (!el) return;
    new IntersectionObserver(function(entries, obs) {
      if (entries[0].isIntersecting) {
        gtag('event', 'coaching_scroll_depth', { section: s.label });
        obs.unobserve(el);
      }
    }, { threshold: 0.3 }).observe(el);
  });
})();

/* CTA click attribution */
document.querySelectorAll('[data-cta]').forEach(function(el) {
  el.addEventListener('click', function() {
    if (typeof gtag === 'function') gtag('event', 'coaching_cta_click', { cta_name: el.getAttribute('data-cta') });
  });
});

/* Page view event */
if (typeof gtag === 'function') gtag('event', 'coaching_page_view');

/* Smooth scroll for anchor links */
document.querySelectorAll('a[href^="#"]').forEach(function(a) {
  a.addEventListener('click', function(e) {
    var target = document.getElementById(a.getAttribute('href').slice(1));
    if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
});
</script>'''


# ── JSON-LD ───────────────────────────────────────────────────


def build_jsonld(race_count: int) -> str:
    webpage = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "Gravel Race Training Plans & Coaching | Gravel God",
        "description": f"Race-specific training plans built from your schedule, fitness, and course demands. {race_count} gravel races in the database. $15/week, capped at $249.",
        "url": f"{SITE_BASE_URL}/coaching/",
        "isPartOf": {
            "@type": "WebSite",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
    }
    service = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": "Custom Gravel Race Training Plan",
        "provider": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "description": "Race-specific training plans with structured workouts, nutrition planning, and race-day strategy. Built from your schedule, fitness level, and target event.",
        "offers": {
            "@type": "Offer",
            "price": str(PRICE_PER_WEEK),
            "priceCurrency": "USD",
            "priceSpecification": {
                "@type": "UnitPriceSpecification",
                "price": str(PRICE_PER_WEEK),
                "priceCurrency": "USD",
                "unitText": "week",
            },
        },
    }
    wp_tag = f'<script type="application/ld+json">{json.dumps(webpage, separators=(",", ":"))}</script>'
    svc_tag = f'<script type="application/ld+json">{json.dumps(service, separators=(",", ":"))}</script>'
    return f'{wp_tag}\n  {svc_tag}'


# ── Assemble page ─────────────────────────────────────────────


def generate_coaching_page(external_assets: dict = None) -> str:
    race_count = load_race_count()
    canonical_url = f"{SITE_BASE_URL}/coaching/"

    nav = build_nav()
    hero = build_hero(race_count)
    problem = build_problem()
    tiers = build_service_tiers()
    deliverables = build_deliverables()
    how = build_how_it_works()
    testimonials = build_testimonials()
    honest = build_honest_check()
    pricing = build_pricing()
    faq = build_faq()
    final_cta = build_final_cta()
    footer = build_footer()
    sticky = build_mobile_sticky_cta()
    coaching_css = build_coaching_css()
    coaching_js = build_coaching_js()
    jsonld = build_jsonld(race_count)

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    meta_desc = f"Race-specific training plans built from your schedule, fitness, and course demands. {race_count} gravel races in the database. ${PRICE_PER_WEEK}/week, capped at ${PRICE_CAP}."

    og_tags = f'''<meta property="og:title" content="Gravel Race Training Plans &amp; Coaching | Gravel God">
  <meta property="og:description" content="Race-specific training plans built from your schedule, fitness, and course demands. {race_count} gravel races. ${PRICE_PER_WEEK}/week.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="Gravel Race Training Plans &amp; Coaching | Gravel God">
  <meta name="twitter:description" content="Race-specific training plans. {race_count} gravel races. ${PRICE_PER_WEEK}/week, capped at ${PRICE_CAP}.">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gravel Race Training Plans &amp; Coaching | Gravel God</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {coaching_css}
  <script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_MEASUREMENT_ID}');</script>
  {get_ab_head_snippet()}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {nav}

  {hero}

  {problem}

  {tiers}

  {deliverables}

  {how}

  {testimonials}

  {honest}

  {pricing}

  {faq}

  {final_cta}

  {footer}

  {sticky}
</div>

{inline_js}
{coaching_js}

</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God coaching page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)

    html_content = generate_coaching_page(external_assets=assets)
    output_file = output_dir / "coaching.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
