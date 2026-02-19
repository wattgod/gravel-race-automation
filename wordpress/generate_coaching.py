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

# ── Constants ─────────────────────────────────────────────────

QUESTIONNAIRE_URL = f"{SITE_BASE_URL}/coaching/apply/"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


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


def build_hero() -> str:
    return f'''<div class="gg-hero gg-coach-hero" id="hero">
    <div class="gg-hero-tier" style="background:var(--gg-color-gold)">COACHING</div>
    <h1>An Algorithm Isn&#39;t a Person.</h1>
    <p class="gg-hero-tagline">Coaching is a relationship. Someone who knows your history, reads your data, and adjusts when life gets in the way. That&#39;s what this is.</p>
    <div class="gg-coach-hero-cta">
      <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="hero_apply">APPLY NOW</a>
      <a href="#how-it-works" class="gg-coach-btn gg-coach-btn--secondary" data-cta="hero_how_it_works">SEE HOW IT WORKS</a>
    </div>
    <p class="gg-coach-stat-line">Juniors. Pros. Masters. If you can pedal, I can help.</p>
  </div>'''


def build_problem() -> str:
    return '''<div class="gg-section" id="problem">
    <div class="gg-section-header">
      <span class="gg-section-kicker">01</span>
      <h2 class="gg-section-title">The Limits of Going It Alone</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-quotes">
        <blockquote class="gg-coach-quote">
          <p>You&#39;ve been training by feel for years. Sometimes it works. Mostly you blow up at mile 80 and can&#39;t figure out why.</p>
        </blockquote>
        <blockquote class="gg-coach-quote">
          <p>You downloaded a plan from an app. It didn&#39;t know about your hip flexor, your newborn, or that your work calls run past 6 on Tuesdays.</p>
        </blockquote>
        <blockquote class="gg-coach-quote">
          <p>You know more about cycling than most people. But knowing and executing are different skills. A coach closes that gap.</p>
        </blockquote>
      </div>
    </div>
  </div>'''


def build_service_tiers() -> str:
    return f'''<div class="gg-section" id="tiers">
    <div class="gg-section-header">
      <span class="gg-section-kicker">02</span>
      <h2 class="gg-section-title">Same Coach. Same Standards. Different Involvement.</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-tiers">
        <div class="gg-coach-tier-card">
          <div class="gg-coach-tier-header">$199/MO</div>
          <h3>Min</h3>
          <p class="gg-coach-tier-cadence">Weekly review &middot; Light analysis &middot; Quarterly calls</p>
          <p class="gg-coach-tier-desc">For experienced athletes who execute without hand-holding.</p>
          <ul class="gg-coach-tier-list">
            <li>Weekly training review</li>
            <li>Light file analysis</li>
            <li>Quarterly strategy calls</li>
            <li>Structured .zwo workouts</li>
            <li>Race-optimized nutrition plan</li>
            <li>Custom training guide</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="tier_min">GET STARTED</a>
        </div>
        <div class="gg-coach-tier-card gg-coach-tier-card--featured">
          <div class="gg-coach-tier-header gg-coach-tier-header--gold">$299/MO</div>
          <h3>Mid</h3>
          <p class="gg-coach-tier-cadence">Weekly review &middot; Thorough analysis &middot; Monthly calls</p>
          <p class="gg-coach-tier-desc">For serious athletes who want clear feedback + weekly adjustments.</p>
          <ul class="gg-coach-tier-list">
            <li>Everything in Min</li>
            <li>Thorough file analysis (WKO)</li>
            <li>Monthly strategy calls</li>
            <li>Weekly plan adjustments</li>
            <li>Direct message access</li>
            <li>Blindspot detection</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="tier_mid">GET STARTED</a>
        </div>
        <div class="gg-coach-tier-card">
          <div class="gg-coach-tier-header">$1,200/MO</div>
          <h3>Max</h3>
          <p class="gg-coach-tier-cadence">Daily review &middot; Extensive support &middot; On-demand calls</p>
          <p class="gg-coach-tier-desc">For athletes who want immediate feedback + high-touch support.</p>
          <ul class="gg-coach-tier-list">
            <li>Everything in Mid</li>
            <li>Daily file review</li>
            <li>On-demand calls</li>
            <li>Race-week strategy</li>
            <li>Multi-race season planning</li>
            <li>Priority response</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="tier_max">GET STARTED</a>
        </div>
      </div>
      <p class="gg-coach-tier-disclaimer">If you skip workouts, underfuel, or ignore feedback, no tier fixes that. I&#39;ll tell you within 24 hours if it&#39;s not a fit.</p>
    </div>
  </div>'''


def build_deliverables() -> str:
    return '''<div class="gg-section" id="deliverables">
    <div class="gg-section-header">
      <span class="gg-section-kicker">03</span>
      <h2 class="gg-section-title">What Coaching Looks Like</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-coach-deliverables">
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">01</div>
          <div class="gg-coach-deliverable-content">
            <h3>I Read Your File. Not a Summary of It.</h3>
            <p>A person looks at your ride data, not a dashboard. I see the interval you bailed on and ask why. Software flags a number. I flag a pattern.</p>
          </div>
        </div>
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">02</div>
          <div class="gg-coach-deliverable-content">
            <h3>Your Plan Changes When Your Life Does</h3>
            <p>Kid got sick. Work trip. Tweaked your knee. I adjust the plan that week &mdash; not after you fail to hit targets for three weeks and an algorithm notices.</p>
          </div>
        </div>
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">03</div>
          <div class="gg-coach-deliverable-content">
            <h3>Honest Feedback You Can&#39;t Get From a Prompt</h3>
            <p>You don&#39;t need a motivational paragraph generated in 2 seconds. You need someone who knows you well enough to say &#34;you&#39;re sandbagging&#34; or &#34;you need a rest week and you won&#39;t take one.&#34;</p>
          </div>
        </div>
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">04</div>
          <div class="gg-coach-deliverable-content">
            <h3>I Know What It Feels Like</h3>
            <p>I&#39;ve blown up at mile 80. I&#39;ve overtrained into a hole. I&#39;ve raced sick because I was too stubborn to DNS. That context doesn&#39;t come from a training model &mdash; it comes from years on the bike.</p>
          </div>
        </div>
        <div class="gg-coach-deliverable">
          <div class="gg-coach-deliverable-num">05</div>
          <div class="gg-coach-deliverable-content">
            <h3>Race Strategy From Someone Who&#39;s Studied the Course</h3>
            <p>328 races in the database. Suffering zones, terrain breakdowns, altitude warnings, segment-by-segment pacing. Your race-day plan isn&#39;t a guess &mdash; it&#39;s built from data.</p>
          </div>
        </div>
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
            <h3>Fill Out the Intake</h3>
            <p>12-section questionnaire. Your race. Your hours. Your history. Your constraints. Be honest &mdash; the more I know, the better this works.</p>
          </div>
        </div>
        <div class="gg-coach-step">
          <div class="gg-coach-step-num">02</div>
          <div class="gg-coach-step-body">
            <h3>We Align on a Plan</h3>
            <p>I review your intake, identify blindspots, and build your first training block. You&#39;ll hear from me within 48 hours.</p>
          </div>
        </div>
        <div class="gg-coach-step">
          <div class="gg-coach-step-num">03</div>
          <div class="gg-coach-step-body">
            <h3>We Train Together</h3>
            <p>Weekly check-ins. Plan adjustments. Direct access when something comes up. This isn&#39;t set-and-forget.</p>
          </div>
        </div>
      </div>
      <div style="margin-top:var(--gg-spacing-lg)">
        <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="how_it_works_cta">START THE CONVERSATION</a>
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
      <h2 class="gg-section-title">What Athletes Say</h2>

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
          <h3 class="gg-coach-audience-heading gg-coach-audience-heading--yes">Coaching Is For You If:</h3>
          <ul class="gg-coach-audience-list gg-coach-list--yes">
            <li>You want someone invested in your outcome</li>
            <li>You&#39;re tired of guessing</li>
            <li>You&#39;ll do the work if someone shows you what to do</li>
            <li>You have a race and a reason</li>
            <li>You&#39;re ready to be honest about your habits</li>
          </ul>
        </div>
        <div class="gg-coach-audience-col">
          <h3 class="gg-coach-audience-heading gg-coach-audience-heading--no">Coaching Isn&#39;t For You If:</h3>
          <ul class="gg-coach-audience-list gg-coach-list--no">
            <li>You just want a file and don&#39;t want to talk to anyone</li>
            <li>You&#39;re not willing to change anything</li>
            <li>Your race is next week</li>
            <li>You want validation, not honesty</li>
          </ul>
        </div>
      </div>
    </div>
  </div>'''


def build_faq() -> str:
    faqs = [
        (
            "What&#39;s the difference between a plan and coaching?",
            "A plan is a document. Coaching is a relationship. The plan changes when your life changes.",
        ),
        (
            "How often will I hear from you?",
            "Weekly minimum. More during race week. You can message me anytime.",
        ),
        (
            "Do I need a power meter?",
            "Not required. Every workout includes RPE targets so you can train by feel. But a power meter is strongly recommended &mdash; watt targets remove guesswork entirely. Heart rate works as a middle ground.",
        ),
        (
            "What if I miss workouts?",
            "Life happens. I adjust. The plan serves you, not the other way around.",
        ),
        (
            "How do I know if coaching is working?",
            "We set baselines at intake. We track progress against them. You&#39;ll know.",
        ),
        (
            "What&#39;s the time commitment?",
            "The training you&#39;re already doing, but smarter. I&#39;m not adding hours &mdash; I&#39;m making the ones you have count.",
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
      <span class="gg-section-kicker">07</span>
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
        <p class="gg-coach-final-hook">You already know how to suffer. Let me show you how to suffer smarter.</p>
        <p class="gg-coach-final-sub">The intake takes 10 minutes. I&#39;ll review it within 48 hours. No commitment until we both agree it&#39;s a fit.</p>
        <div class="gg-coach-final-buttons">
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="final_fill_intake">FILL OUT THE INTAKE</a>
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
    <a href="{QUESTIONNAIRE_URL}" data-cta="sticky_cta">APPLY FOR COACHING</a>
  </div>'''


# ── CSS ───────────────────────────────────────────────────────


def build_coaching_css() -> str:
    """Coaching-page-specific CSS. All gg-coach-* prefix. Brand tokens only."""
    return '''<style>
/* ── Coach hero — light sandwash override ────────── */
.gg-neo-brutalist-page .gg-coach-hero {
  background: var(--gg-color-warm-paper);
  border-bottom: 3px double var(--gg-color-dark-brown);
  flex-direction: column;
  align-items: flex-start;
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

/* ── Stat line ───────────────────────────────────── */
.gg-neo-brutalist-page .gg-coach-stat-line {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  color: var(--gg-color-secondary-brown);
  margin-top: var(--gg-spacing-lg);
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
.gg-neo-brutalist-page .gg-coach-tier-cadence {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
  margin-bottom: var(--gg-spacing-sm);
}
.gg-neo-brutalist-page .gg-coach-tier-disclaimer {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  font-style: italic;
  color: var(--gg-color-secondary-brown);
  line-height: var(--gg-line-height-relaxed);
  margin-top: var(--gg-spacing-lg);
  max-width: 640px;
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
  .gg-neo-brutalist-page .gg-coach-tiers {
    grid-template-columns: 1fr;
  }
  .gg-neo-brutalist-page .gg-coach-audience {
    grid-template-columns: 1fr;
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


def build_jsonld() -> str:
    webpage = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "Coaching | Gravel God",
        "description": "Gravel race coaching built around your schedule, your data, and your life. Three tiers: Min, Mid, and Max.",
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
        "name": "Gravel Race Coaching",
        "provider": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
        "description": "Gravel race coaching: three tiers of involvement from weekly review to daily high-touch support. Built around your schedule, fitness, and target event.",
    }
    wp_tag = f'<script type="application/ld+json">{json.dumps(webpage, separators=(",", ":"))}</script>'
    svc_tag = f'<script type="application/ld+json">{json.dumps(service, separators=(",", ":"))}</script>'
    return f'{wp_tag}\n  {svc_tag}'


# ── Assemble page ─────────────────────────────────────────────


def generate_coaching_page(external_assets: dict = None) -> str:
    canonical_url = f"{SITE_BASE_URL}/coaching/"

    nav = build_nav()
    hero = build_hero()
    problem = build_problem()
    tiers = build_service_tiers()
    deliverables = build_deliverables()
    how = build_how_it_works()
    testimonials = build_testimonials()
    honest = build_honest_check()
    faq = build_faq()
    final_cta = build_final_cta()
    footer = build_footer()
    sticky = build_mobile_sticky_cta()
    coaching_css = build_coaching_css()
    coaching_js = build_coaching_js()
    jsonld = build_jsonld()

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    meta_desc = "Gravel race coaching built around your schedule, your data, and your life. Three tiers of involvement — from weekly review to daily high-touch support."

    og_tags = f'''<meta property="og:title" content="Coaching | Gravel God">
  <meta property="og:description" content="Gravel race coaching built around your schedule, your data, and your life. Three tiers of involvement.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary">
  <meta name="twitter:title" content="Coaching | Gravel God">
  <meta name="twitter:description" content="Gravel race coaching built around your schedule, your data, and your life. Three tiers of involvement.">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Coaching | Gravel God</title>
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
