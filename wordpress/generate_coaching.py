#!/usr/bin/env python3
"""
Generate the Gravel God Coaching landing page.

Consolidates both service tiers (Custom Training Plans + 1:1 Coaching) into
a single page at /coaching/. Full-bleed band layout: section backgrounds span
the viewport, content sits in a 1200px measure, prose capped at a readable
width. Register is understated — the page asserts, it doesn't perform.

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
    SITE_BASE_URL,
    get_page_css,
    build_inline_js,
    write_shared_assets,
)
from brand_tokens import get_ab_head_snippet, get_ga4_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html, get_site_header_js
from cookie_consent import get_consent_banner_html
from generate_about import _testimonial_data
from scroll_animations import get_scroll_animation_css, get_scroll_animation_js

OUTPUT_DIR = Path(__file__).parent / "output"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Constants ─────────────────────────────────────────────────

QUESTIONNAIRE_URL = f"{SITE_BASE_URL}/coaching/apply/"

# Curated for the coaching page: concrete result, concrete constraint,
# concrete rider. The full set stays on /about/.
FEATURED_TESTIMONIAL_NAMES = ("Sarah K.", "Marcus W.", "Kara D.")


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


def _sec_head(num: str, title: str) -> str:
    return (
        f'<div class="gg-coach-sec-head">'
        f'<span class="gg-coach-sec-num">{num}</span>'
        f'<h2 class="gg-coach-sec-title">{title}</h2>'
        f'</div>'
    )


# ── Page sections ─────────────────────────────────────────────


def build_nav() -> str:
    return get_site_header_html(active="services") + f'''
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">Coaching</span>
  </div>'''


def build_hero() -> str:
    return f'''<section class="gg-coach-band gg-coach-hero" id="hero">
    <div class="gg-coach-inner">
      <p class="gg-coach-kicker">Coaching</p>
      <h1>Fitness is common. Preparation is rare.</h1>
      <p class="gg-coach-tagline">You can get fit on your own. The hard part is matching the training to the course, the calendar, and the rest of your life. That&#39;s the work I do.</p>
      <div class="gg-coach-hero-cta">
        <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn" data-cta="hero_apply">Apply</a>
        <a href="#how-it-works" class="gg-coach-btn gg-coach-btn--secondary" data-cta="hero_how_it_works">How it works</a>
      </div>
      <p class="gg-coach-stat-line">757 courses analyzed. One coach.</p>
    </div>
  </section>'''


def build_problem() -> str:
    return f'''<section class="gg-coach-band" id="problem">
    <div class="gg-coach-inner">
      {_sec_head("01", "The gap")}
      <div class="gg-coach-prose">
        <p>Most athletes who come to me are already fit. They train ten or twelve hours a week, read more about training than most coaches write, and still fade at the same point in the same kind of race. That isn&#39;t a fitness problem. It&#39;s a planning problem &mdash; the training never quite matched the course, the calendar, or the job.</p>
        <p>An app can make you fitter. It can&#39;t study your race&#39;s course profile, cross it with your data, and tell you which climb will end your day if your pacing doesn&#39;t change by week eleven. That&#39;s what I do.</p>
      </div>
    </div>
  </section>'''


def build_deliverables() -> str:
    items = [
        (
            "Every file, read by a person",
            "I look at your ride data, not a dashboard summary of it. Software flags a number. I notice the interval you bailed on and ask why.",
        ),
        (
            "A plan that moves when your life does",
            "Sick kid, work trip, tender knee &mdash; the week adjusts that week, not after three missed targets teach an algorithm what I&#39;d have seen on Tuesday.",
        ),
        (
            "Honest feedback",
            "Sometimes that&#39;s &ldquo;you&#39;re sandbagging.&rdquo; Sometimes it&#39;s &ldquo;you need a rest week, and you won&#39;t take one unless it&#39;s on the calendar.&rdquo;",
        ),
        (
            "Race strategy from course data",
            "I&#39;ve analyzed 757 gravel courses &mdash; terrain, altitude, where races actually break apart. Your race-day plan is built from that record, not from a template.",
        ),
    ]
    cards = "\n        ".join(
        f'<div class="gg-coach-deliverable"><h3>{t}</h3><p>{d}</p></div>'
        for t, d in items
    )
    return f'''<section class="gg-coach-band" id="deliverables">
    <div class="gg-coach-inner">
      {_sec_head("02", "What you get")}
      <div class="gg-coach-deliverables" data-animate="fade-stagger">
        {cards}
      </div>
    </div>
  </section>'''


def build_how_it_works() -> str:
    steps = [
        (
            "Fill out the intake",
            "Twelve sections: your race, your hours, your history, your constraints. Honest answers make a better plan.",
        ),
        (
            "I build your first block",
            "I study your intake against the demands of your race and build the opening four weeks. You&#39;ll hear from me within 48 hours &mdash; including if I don&#39;t think coaching is what you need.",
        ),
        (
            "We train",
            "Weekly review, adjustments as they&#39;re needed, direct access when something comes up.",
        ),
        (
            "We sharpen toward race day",
            "Every four weeks we reassess. Fitness moves, schedules shrink, plans follow.",
        ),
    ]
    rows = "\n        ".join(
        f'<div class="gg-coach-step">'
        f'<div class="gg-coach-step-num">{i:02d}</div>'
        f'<div class="gg-coach-step-body"><h3>{t}</h3><p>{d}</p></div>'
        f'</div>'
        for i, (t, d) in enumerate(steps, start=1)
    )
    return f'''<section class="gg-coach-band" id="how-it-works">
    <div class="gg-coach-inner">
      {_sec_head("03", "How it works")}
      <div class="gg-coach-steps" data-animate="fade-stagger">
        {rows}
      </div>
      <div class="gg-coach-band-cta">
        <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn" data-cta="how_it_works_cta">Start the intake</a>
      </div>
    </div>
  </section>'''


def build_service_tiers() -> str:
    return f'''<section class="gg-coach-band gg-coach-band--sand" id="tiers">
    <div class="gg-coach-inner">
      {_sec_head("04", "Same coach. Three levels of involvement.")}
      <div class="gg-coach-tiers" data-animate="fade-stagger">
        <div class="gg-coach-tier-card">
          <h3>Min</h3>
          <div class="gg-coach-tier-header">$199<span class="gg-coach-tier-interval">/4 WK</span></div>
          <p class="gg-coach-tier-desc">The plan, plus a weekly check of your training. For athletes who execute on their own and want the thinking done right.</p>
          <ul class="gg-coach-tier-list">
            <li>Weekly training review</li>
            <li>File analysis</li>
            <li>Quarterly strategy calls</li>
            <li>Structured workouts for your trainer or head unit</li>
            <li>Race-day nutrition plan</li>
            <li>Custom training guide</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}?tier=min" class="gg-coach-btn gg-coach-btn--secondary" data-cta="tier_min">Get started</a>
        </div>
        <div class="gg-coach-tier-card gg-coach-tier-card--featured">
          <h3>Mid</h3>
          <div class="gg-coach-tier-header">$299<span class="gg-coach-tier-interval">/4 WK</span></div>
          <p class="gg-coach-tier-desc">The plan, watched. Someone reads the data between sessions and adjusts the same week life changes. Most athletes belong here.</p>
          <ul class="gg-coach-tier-list">
            <li>Everything in Min</li>
            <li>Detailed power-file analysis</li>
            <li>Every-4-week strategy calls</li>
            <li>Weekly plan adjustments</li>
            <li>Direct message access</li>
            <li>Blindspot detection</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}?tier=mid" class="gg-coach-btn" data-cta="tier_mid">Get started</a>
        </div>
        <div class="gg-coach-tier-card">
          <h3>Max</h3>
          <div class="gg-coach-tier-header">$1,200<span class="gg-coach-tier-interval">/4 WK</span></div>
          <p class="gg-coach-tier-desc">Everything, daily. For the race where you want nothing left to chance.</p>
          <ul class="gg-coach-tier-list">
            <li>Everything in Mid</li>
            <li>Daily file review</li>
            <li>On-demand calls</li>
            <li>Race-week strategy</li>
            <li>Multi-race season planning</li>
            <li>Priority response</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}?tier=max" class="gg-coach-btn gg-coach-btn--secondary" data-cta="tier_max">Get started</a>
        </div>
      </div>
      <p class="gg-coach-tier-disclaimer">Coaching doesn&#39;t fix skipped workouts or feedback you don&#39;t act on. If this isn&#39;t a fit, I&#39;ll tell you within 24 hours.</p>
      <p class="gg-coach-tier-setup-fee">All tiers include a one-time $99 setup fee: intake analysis, training-history review, and your first plan build.</p>
    </div>
  </section>'''


def build_testimonials() -> str:
    by_name = {name: (name, quote, meta) for name, quote, meta in _testimonial_data()}
    featured = [by_name[n] for n in FEATURED_TESTIMONIAL_NAMES if n in by_name]
    if len(featured) < 3:
        featured = _testimonial_data()[:3]
    cards = "\n        ".join(
        f'<blockquote class="gg-coach-testimonial">'
        f'<p>{esc(quote)}</p>'
        f'<footer><strong>{esc(name)}</strong>'
        f'<span class="gg-coach-testimonial-meta">{meta}</span>'
        f'</footer></blockquote>'
        for name, quote, meta in featured
    )
    return f'''<section class="gg-coach-band" id="results">
    <div class="gg-coach-inner">
      {_sec_head("05", "What athletes say")}
      <div class="gg-coach-testimonials">
        {cards}
      </div>
      <p class="gg-coach-testimonials-more"><a href="{SITE_BASE_URL}/about/">More, from fifty athletes &rarr;</a></p>
    </div>
  </section>'''


def build_honest_check() -> str:
    return f'''<section class="gg-coach-band" id="honest-check">
    <div class="gg-coach-inner">
      {_sec_head("06", "A fit, or not")}
      <div class="gg-coach-audience">
        <div class="gg-coach-audience-col">
          <h3 class="gg-coach-audience-heading gg-coach-audience-heading--yes">Coaching is for you if:</h3>
          <ul class="gg-coach-audience-list gg-coach-list--yes">
            <li>You&#39;ll do the training when the thinking is done right</li>
            <li>You have a race and a reason</li>
            <li>You&#39;re ready to be honest about your habits</li>
            <li>You want a plan smarter than the one you&#39;d build alone</li>
          </ul>
        </div>
        <div class="gg-coach-audience-col">
          <h3 class="gg-coach-audience-heading gg-coach-audience-heading--no">It isn&#39;t:</h3>
          <ul class="gg-coach-audience-list gg-coach-list--no">
            <li>Accountability texts when you skip a Tuesday</li>
            <li>Validation dressed up as feedback</li>
            <li>A rescue for a race that&#39;s next week</li>
            <li>A substitute for doing the work</li>
          </ul>
        </div>
      </div>
    </div>
  </section>'''


def build_faq() -> str:
    faqs = [
        (
            "What&#39;s the difference between a plan and coaching?",
            "A plan is a document. Coaching is the relationship that changes the document when your life changes.",
        ),
        (
            "How often will I hear from you?",
            "Weekly at minimum, more near your race. You can message me anytime.",
        ),
        (
            "Do I need a power meter?",
            "Not required &mdash; every workout carries effort-based targets you can train by feel. A power meter removes the guesswork; heart rate sits in between.",
        ),
        (
            "What if I miss workouts?",
            "Life happens. I adjust. The plan serves you, not the other way around.",
        ),
        (
            "How do I know if coaching is working?",
            "We set baselines at intake and measure against them. You&#39;ll know.",
        ),
        (
            "What&#39;s the time commitment?",
            "The training you&#39;re already doing, but smarter. I&#39;m not adding hours &mdash; I&#39;m making the ones you have count.",
        ),
        (
            "What&#39;s the $99 setup fee?",
            "It covers intake analysis, training-history review, and building your first plan. It&#39;s a one-time charge on top of your first billing cycle.",
        ),
        (
            "Can I cancel anytime?",
            "Yes. No contracts, no cancellation fees. Your coaching access continues through the end of your current 4-week cycle.",
        ),
    ]

    items = []
    for idx, (q, a) in enumerate(faqs):
        ans_id = f'gg-coach-faq-ans-{idx}'
        items.append(
            f'<div class="gg-coach-faq-item">'
            f'<div class="gg-coach-faq-q" role="button" tabindex="0" aria-expanded="false" aria-controls="{ans_id}">'
            f'{q}'
            f'<span class="gg-coach-faq-toggle" aria-hidden="true">+</span>'
            f'</div>'
            f'<div class="gg-coach-faq-a" id="{ans_id}" role="region"><p>{a}</p></div>'
            f'</div>'
        )
    inner = "\n      ".join(items)
    return f'''<section class="gg-coach-band" id="faq">
    <div class="gg-coach-inner">
      {_sec_head("07", "FAQ")}
      <div class="gg-coach-faq-list">
      {inner}
      </div>
    </div>
  </section>'''


def build_final_cta() -> str:
    return f'''<section class="gg-coach-band gg-coach-band--dark" id="final-cta">
    <div class="gg-coach-inner">
      <div class="gg-coach-final-cta">
        <p class="gg-coach-final-hook">If you have a race and a reason, start with the intake.</p>
        <p class="gg-coach-final-sub">It takes about ten minutes, and I read every one myself. You&#39;ll hear from me within 48 hours &mdash; including if I don&#39;t think coaching is what you need.</p>
        <div class="gg-coach-final-buttons">
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--light" data-cta="final_fill_intake">Start the intake</a>
        </div>
        <p class="gg-coach-final-contact">Questions first? <a href="mailto:matt@gravelgodcycling.com">matt@gravelgodcycling.com</a> &mdash; I answer myself, usually within a day.</p>
      </div>
    </div>
  </section>'''


def build_footer() -> str:
    return get_mega_footer_html()


def build_mobile_sticky_cta() -> str:
    return f'''<div class="gg-coach-sticky-cta">
    <a href="{QUESTIONNAIRE_URL}" data-cta="sticky_cta">Apply for coaching</a>
  </div>'''


# ── CSS ───────────────────────────────────────────────────────


def build_coaching_css() -> str:
    """Coaching-page-specific CSS. All gg-coach-* prefix. Brand tokens only."""
    return '''<style>
/* ── Skip link ──────────────────────────────────── */
.gg-coach-skip-link {
  position: absolute;
  left: -9999px;
  top: 0;
  z-index: 1001;
  padding: var(--gg-spacing-xs) var(--gg-spacing-md);
  background: var(--gg-color-near-black);
  color: var(--gg-color-warm-paper);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  text-decoration: none;
}
.gg-coach-skip-link:focus {
  left: 0;
}

/* ── Full-bleed layout override ──────────────────
   The shared container caps every neo-brutalist page at 960px.
   Here the container goes full-width; each band paints the whole
   viewport and constrains its own content to the 1200px measure. */
.gg-neo-brutalist-page {
  max-width: none;
  padding: 0;
}
.gg-coach-inner {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 var(--gg-spacing-lg);
}
.gg-neo-brutalist-page .gg-site-header {
  padding-left: var(--gg-spacing-lg);
  padding-right: var(--gg-spacing-lg);
}
.gg-neo-brutalist-page .gg-site-header-inner {
  max-width: 1200px;
}
.gg-neo-brutalist-page .gg-breadcrumb {
  max-width: 1200px;
  margin: 0 auto;
  padding-left: var(--gg-spacing-lg);
  padding-right: var(--gg-spacing-lg);
  background: transparent;
  border: none;
}
.gg-neo-brutalist-page .gg-mega-footer-grid,
.gg-neo-brutalist-page .gg-mega-footer-legal,
.gg-neo-brutalist-page .gg-mega-footer-disclaimer {
  max-width: 1200px;
}
.gg-neo-brutalist-page .gg-mega-footer {
  margin-top: 0;
}

/* ── Bands ───────────────────────────────────────── */
.gg-coach-band {
  padding: var(--gg-spacing-2xl) 0;
}
.gg-coach-band--sand {
  background: var(--gg-color-sand);
  border-top: 1px solid var(--gg-color-tan);
  border-bottom: 1px solid var(--gg-color-tan);
}
.gg-coach-band--dark {
  background: var(--gg-color-dark-brown);
}
.gg-coach-band-cta {
  margin-top: var(--gg-spacing-lg);
}

/* ── Section heads — quiet numeral, serif title ──── */
.gg-coach-sec-head {
  display: flex;
  align-items: baseline;
  gap: var(--gg-spacing-md);
  border-bottom: 1px solid var(--gg-color-tan);
  padding-bottom: var(--gg-spacing-sm);
  margin-bottom: var(--gg-spacing-xl);
}
.gg-coach-sec-num {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wider);
}
.gg-coach-sec-title {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-dark-brown);
  margin: 0;
  line-height: var(--gg-line-height-tight);
}

/* ── Hero ────────────────────────────────────────── */
.gg-coach-hero {
  padding-top: var(--gg-spacing-2xl);
  padding-bottom: var(--gg-spacing-2xl);
  border-bottom: 1px solid var(--gg-color-tan);
}
.gg-coach-kicker {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-extreme);
  color: var(--gg-color-secondary-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
}
.gg-coach-hero h1 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-4xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  line-height: var(--gg-line-height-tight);
  margin: 0;
  max-width: 18ch;
}
.gg-coach-tagline {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-secondary-brown);
  max-width: 56ch;
  margin: var(--gg-spacing-lg) 0 0 0;
}
.gg-coach-hero-cta {
  display: flex;
  gap: var(--gg-spacing-md);
  margin-top: var(--gg-spacing-xl);
  flex-wrap: wrap;
}
.gg-coach-stat-line {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  color: var(--gg-color-secondary-brown);
  margin: var(--gg-spacing-xl) 0 0 0;
}

/* ── Buttons ─────────────────────────────────────── */
.gg-coach-btn {
  display: inline-block;
  background: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  padding: var(--gg-spacing-sm) var(--gg-spacing-lg);
  border: 2px solid var(--gg-color-dark-brown);
  text-decoration: none;
  text-align: center;
  cursor: pointer;
  transition: background-color var(--gg-transition-hover),
              border-color var(--gg-transition-hover),
              color var(--gg-transition-hover);
}
.gg-coach-btn:hover {
  background-color: var(--gg-color-near-black);
  border-color: var(--gg-color-near-black);
}
.gg-coach-btn--secondary {
  background: transparent;
  color: var(--gg-color-dark-brown);
}
.gg-coach-btn--secondary:hover {
  background-color: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
}
.gg-coach-btn--light {
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-warm-paper);
}
.gg-coach-btn--light:hover {
  background-color: var(--gg-color-sand);
  border-color: var(--gg-color-sand);
  color: var(--gg-color-dark-brown);
}

/* ── Prose ───────────────────────────────────────── */
.gg-coach-prose p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  max-width: 68ch;
  margin: 0 0 var(--gg-spacing-md) 0;
}
.gg-coach-prose p:last-child {
  margin-bottom: 0;
}

/* ── Deliverables — 2×2, sentence-case serif heads ── */
.gg-coach-deliverables {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-xl) var(--gg-spacing-2xl);
}
.gg-coach-deliverable h3 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
  line-height: var(--gg-line-height-tight);
}
.gg-coach-deliverable p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-secondary-brown);
  margin: 0;
  max-width: 52ch;
}

/* ── How it works steps ──────────────────────────── */
.gg-coach-steps {
  display: flex;
  flex-direction: column;
  gap: 0;
  max-width: 720px;
}
.gg-coach-step {
  display: grid;
  grid-template-columns: 48px 1fr;
  gap: var(--gg-spacing-md);
  padding: var(--gg-spacing-md) 0;
  border-bottom: 1px solid var(--gg-color-tan);
}
.gg-coach-step:last-child {
  border-bottom: none;
}
.gg-coach-step-num {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  text-align: right;
  padding-top: 4px;
  letter-spacing: var(--gg-letter-spacing-wide);
}
.gg-coach-step-body h3 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-2xs) 0;
}
.gg-coach-step-body p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-secondary-brown);
  margin: 0;
  max-width: 60ch;
}

/* ── Service tiers ───────────────────────────────── */
.gg-coach-tiers {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gg-spacing-md);
}
.gg-coach-tier-card {
  border: 1px solid var(--gg-color-tan);
  padding: var(--gg-spacing-lg);
  background: var(--gg-color-warm-paper);
  display: flex;
  flex-direction: column;
}
.gg-coach-tier-card--featured {
  border-top: 3px solid var(--gg-color-gold);
}
.gg-coach-tier-card h3 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-2xs) 0;
  line-height: var(--gg-line-height-tight);
}
.gg-coach-tier-header {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-secondary-brown);
  margin-bottom: var(--gg-spacing-sm);
}
.gg-coach-tier-interval {
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-regular);
  letter-spacing: var(--gg-letter-spacing-normal);
}
.gg-coach-tier-desc {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
}
.gg-coach-tier-list {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--gg-spacing-lg) 0;
  flex: 1;
}
.gg-coach-tier-list li {
  padding: var(--gg-spacing-xs) 0;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-dark-brown);
  border-bottom: 1px solid var(--gg-color-tan);
  line-height: var(--gg-line-height-normal);
}
.gg-coach-tier-list li:last-child {
  border-bottom: none;
}
.gg-coach-tier-disclaimer {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-secondary-brown);
  line-height: var(--gg-line-height-relaxed);
  margin-top: var(--gg-spacing-lg);
  max-width: 68ch;
  margin-bottom: 0;
}
.gg-coach-tier-setup-fee {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-secondary-brown);
  line-height: var(--gg-line-height-relaxed);
  margin-top: var(--gg-spacing-xs);
  max-width: 68ch;
  margin-bottom: 0;
}

/* ── Testimonials — static, curated ──────────────── */
.gg-coach-testimonials {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gg-spacing-md);
}
.gg-coach-testimonial {
  background: var(--gg-color-warm-paper);
  border: 1px solid var(--gg-color-tan);
  padding: var(--gg-spacing-lg);
  margin: 0;
  display: flex;
  flex-direction: column;
}
.gg-coach-testimonial p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  font-style: italic;
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
  flex: 1;
}
.gg-coach-testimonial footer {
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-2xs);
  border-top: 1px solid var(--gg-color-tan);
  padding-top: var(--gg-spacing-sm);
}
.gg-coach-testimonial footer strong {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}
.gg-coach-testimonial-meta {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}
.gg-coach-testimonials-more {
  margin: var(--gg-spacing-md) 0 0 0;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
}
.gg-coach-testimonials-more a {
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
  border-bottom: 1px solid var(--gg-color-tan);
  transition: color var(--gg-transition-hover),
              border-color var(--gg-transition-hover);
}
.gg-coach-testimonials-more a:hover {
  color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-gold);
}

/* ── A fit, or not ───────────────────────────────── */
.gg-coach-audience {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-2xl);
  max-width: 960px;
}
.gg-coach-audience-heading {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  font-weight: var(--gg-font-weight-semibold);
  margin: 0 0 var(--gg-spacing-md) 0;
}
.gg-coach-audience-heading--yes {
  color: var(--gg-color-dark-brown);
}
.gg-coach-audience-heading--no {
  color: var(--gg-color-secondary-brown);
}
.gg-coach-audience-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.gg-coach-audience-list li {
  padding: var(--gg-spacing-sm) 0;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  border-bottom: 1px solid var(--gg-color-tan);
  line-height: var(--gg-line-height-normal);
}
.gg-coach-audience-list li:last-child {
  border-bottom: none;
}
.gg-coach-list--no li {
  color: var(--gg-color-secondary-brown);
}

/* ── FAQ accordion ───────────────────────────────── */
.gg-coach-faq-list {
  max-width: 720px;
}
.gg-coach-faq-item {
  border-bottom: 1px solid var(--gg-color-tan);
}
.gg-coach-faq-item:first-child {
  border-top: 1px solid var(--gg-color-tan);
}
.gg-coach-faq-q {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--gg-spacing-md);
  padding: var(--gg-spacing-sm) 0;
  cursor: pointer;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-dark-brown);
  user-select: none;
  transition: color var(--gg-transition-hover);
}
.gg-coach-faq-q:hover {
  color: var(--gg-color-secondary-brown);
}
.gg-coach-faq-toggle {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-regular);
  line-height: 1;
  color: var(--gg-color-secondary-brown);
  transition: color var(--gg-transition-hover);
}
.gg-coach-faq-item.gg-coach-faq-open .gg-coach-faq-toggle {
  color: var(--gg-color-dark-brown);
}
.gg-coach-faq-a {
  max-height: 0;
  overflow: hidden;
  transition: max-height var(--gg-transition-hover);
}
.gg-coach-faq-item.gg-coach-faq-open .gg-coach-faq-a {
  max-height: 500px;
  padding-bottom: var(--gg-spacing-sm);
}
.gg-coach-faq-a p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-secondary-brown);
  line-height: var(--gg-line-height-relaxed);
  margin: 0;
  max-width: 60ch;
}

/* ── Final CTA — dark band ───────────────────────── */
.gg-coach-final-cta {
  text-align: center;
  padding: var(--gg-spacing-xl) 0;
}
.gg-coach-final-hook {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xl);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-warm-paper);
  margin: 0 0 var(--gg-spacing-sm) 0;
  line-height: var(--gg-line-height-tight);
}
.gg-coach-final-sub {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  color: var(--gg-color-tan);
  line-height: var(--gg-line-height-relaxed);
  margin: 0 auto var(--gg-spacing-lg);
  max-width: 56ch;
}
.gg-coach-final-buttons {
  display: flex;
  gap: var(--gg-spacing-md);
  justify-content: center;
  flex-wrap: wrap;
}
.gg-coach-final-contact {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-tan);
  margin-top: var(--gg-spacing-lg);
  text-align: center;
}
.gg-coach-final-contact a {
  color: var(--gg-color-warm-paper);
}

/* ── Mobile sticky CTA ───────────────────────────── */
.gg-coach-sticky-cta {
  display: none;
}
@media (max-width: 768px) {
  .gg-coach-sticky-cta {
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
    visibility: hidden;
    pointer-events: none;
  }
  .gg-coach-sticky-cta.gg-coach-sticky-visible {
    visibility: visible;
    pointer-events: auto;
  }
  .gg-coach-sticky-cta a {
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

/* ── Reduced motion ─────────────────────────────── */
@media (prefers-reduced-motion: reduce) {
  .gg-coach-faq-a {
    transition: none;
  }
}

/* ── Responsive ──────────────────────────────────── */
@media (max-width: 768px) {
  .gg-coach-inner {
    padding: 0 var(--gg-spacing-md);
  }
  .gg-coach-band {
    padding: var(--gg-spacing-xl) 0;
  }
  .gg-coach-hero h1 {
    font-size: var(--gg-font-size-2xl);
  }
  .gg-coach-deliverables {
    grid-template-columns: 1fr;
    gap: var(--gg-spacing-lg);
  }
  .gg-coach-tiers {
    grid-template-columns: 1fr;
  }
  .gg-coach-testimonials {
    grid-template-columns: 1fr;
  }
  .gg-coach-audience {
    grid-template-columns: 1fr;
    gap: var(--gg-spacing-lg);
  }
  .gg-coach-final-hook {
    font-size: var(--gg-font-size-xl);
  }
  .gg-neo-brutalist-page {
    padding-bottom: 60px;
  }
}
''' + get_scroll_animation_css(["fade-stagger"]) + '\n</style>'


# ── JS ────────────────────────────────────────────────────────


def build_coaching_js() -> str:
    """Interactive JS for coaching page — FAQ, scroll depth, GA4 events."""
    return '''<script>
/* FAQ accordion — single-open behavior */
(function() {
  var items = document.querySelectorAll('.gg-coach-faq-item');
  items.forEach(function(item) {
    var q = item.querySelector('.gg-coach-faq-q');
    if (!q) return;
    function toggle() {
      var wasOpen = item.classList.contains('gg-coach-faq-open');
      items.forEach(function(i) { i.classList.remove('gg-coach-faq-open'); var iq = i.querySelector('.gg-coach-faq-q'); if (iq) iq.setAttribute('aria-expanded', 'false'); });
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

/* Scroll depth tracking */
(function() {
  if (typeof gtag !== 'function' || !('IntersectionObserver' in window)) return;
  var sections = [
    { id: 'hero', label: '0_hero' },
    { id: 'problem', label: '12_problem' },
    { id: 'deliverables', label: '25_deliverables' },
    { id: 'how-it-works', label: '37_how_it_works' },
    { id: 'tiers', label: '50_tiers' },
    { id: 'results', label: '62_results' },
    { id: 'honest-check', label: '75_honest_check' },
    { id: 'faq', label: '87_faq' },
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

/* Mobile sticky CTA — show after scrolling past hero */
(function() {
  var sticky = document.querySelector('.gg-coach-sticky-cta');
  var hero = document.getElementById('hero');
  if (!sticky || !hero || !('IntersectionObserver' in window)) return;
  new IntersectionObserver(function(entries) {
    if (entries[0].isIntersecting) {
      sticky.classList.remove('gg-coach-sticky-visible');
    } else {
      sticky.classList.add('gg-coach-sticky-visible');
    }
  }, { threshold: 0 }).observe(hero);
})();
''' + get_scroll_animation_js() + '\n</script>'


# ── JSON-LD ───────────────────────────────────────────────────


def build_jsonld() -> str:
    webpage = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "Coaching | Gravel God",
        "description": "Gravel race coaching from the coach behind 757 course profiles. Three tiers of involvement, built around your race and your schedule.",
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
        "description": "Gravel race coaching: three tiers of involvement from weekly review to daily high-touch support. Built around your race, your schedule, and your training history.",
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
    deliverables = build_deliverables()
    how = build_how_it_works()
    tiers = build_service_tiers()
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

    meta_desc = "Gravel race coaching built on 757 analyzed courses. A human coach, a plan that adjusts weekly, and honest feedback. From $199 every 4 weeks."

    og_tags = f'''<meta property="og:title" content="Coaching | Gravel God">
  <meta property="og:description" content="Coaching built around your race, your hours, and your life. From the coach behind 757 course profiles.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Coaching | Gravel God">
  <meta name="twitter:description" content="Coaching built around your race, your hours, and your life. From the coach behind 757 course profiles.">
  <meta name="twitter:image" content="{SITE_BASE_URL}/og/homepage.jpg">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gravel Cycling Coaching | Gravel God</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {coaching_css}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>

<a href="#hero" class="gg-coach-skip-link">Skip to content</a>
<div class="gg-neo-brutalist-page">
  {nav}

  {hero}

  {problem}

  {deliverables}

  {how}

  {tiers}

  {testimonials}

  {honest}

  {faq}

  {final_cta}

  {footer}

  {sticky}
</div>

{inline_js}
{coaching_js}

''' + '<script>' + get_site_header_js() + '</script>' + f'''

{get_consent_banner_html()}
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
