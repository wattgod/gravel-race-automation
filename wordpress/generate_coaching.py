#!/usr/bin/env python3
"""
Generate the Gravel God Coaching landing page — "The Dossier".

Clinical prestige register: terms-of-work framing, deadpan verdict voice,
strict monochrome, luxury through precision (whitespace + hairlines) rather
than cards/shadows/borders. Full-bleed band layout: section backgrounds span
the viewport, content sits in a 1200px measure, prose capped at a readable
width.

Rebuilt 2026-07-18 from the original "band sequence" layout (hero → problem
→ deliverables → how-it-works → tiers → testimonials → honest-check → faq →
final-cta) into the Dossier structure (hero → terms → tiers → fit → faq →
final-cta), matching the Roadie Labs sibling-brand rebuild
(road-race-automation/wordpress/generate_coaching.py). Owner-approved copy
and structure.

Uses brand tokens exclusively — zero hardcoded hex, no border-radius, no
box-shadow, no bounce easing, no entrance animations — the Dossier is a
still document.

Usage:
    python generate_coaching.py
    python generate_coaching.py --output-dir ./output
"""

import argparse
import html
from pathlib import Path

from generate_neo_brutalist import (
    SITE_BASE_URL,
    get_page_css,
    build_inline_js,
    write_shared_assets,
    _safe_json_for_script,
)
from brand_tokens import get_ab_head_snippet, get_ga4_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html, get_site_header_js
from cookie_consent import get_consent_banner_html
from scroll_animations import get_scroll_animation_css, get_scroll_animation_js

OUTPUT_DIR = Path(__file__).parent / "output"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Constants ─────────────────────────────────────────────────

QUESTIONNAIRE_URL = f"{SITE_BASE_URL}/coaching/apply/"


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


# SANCTIONED EXCEPTION to the anti-defensive-messaging rule (see
# .claude/skills/brand-and-trust/SKILL.md, "Never defensive messaging" —
# phrases naming what something ISN'T are normally banned because they
# plant doubt nobody had). The sub-line below ("Not an AI, not a
# dashboard, not a coach who reads you like a spreadsheet") is an
# explicit, owner-approved exception. It is carried over verbatim from
# the Roadie Labs /coaching/ hero
# (road-race-automation/wordpress/generate_coaching.py, build_hero()) —
# Roadie Labs shipped this line 2026-07-18 as the precedent-setting
# instance of this exception, under the same brand-and-trust
# anti-defensive-messaging rule that governs both sites. This is
# gravel adopting an already-owner-sanctioned pattern from the sibling
# brand, not a fabricated in-repo precedent — no equivalent footnote
# existed anywhere in gravel-race-automation before this rebuild
# (checked including HTML-entity/curly-apostrophe variants and
# generated output).
def build_hero() -> str:
    return f'''<section class="gg-coach-band gg-coach-hero" id="hero">
    <div class="gg-coach-inner">
      <h1>You could be better than you think. That is not encouragement &mdash; it&#39;s an observation about people who train alone.</h1>
      <p class="gg-coach-tagline">The fix is a human in your corner. Not an AI, not a dashboard, not a coach who reads you like a spreadsheet. The terms are below.</p>
      <a href="{QUESTIONNAIRE_URL}" class="gg-coach-hero-cta" data-cta="hero_apply">GET ME IN YOUR CORNER &rarr;</a>
    </div>
  </section>'''


def build_terms() -> str:
    clauses = [
        (
            "01",
            "Every file, read by a person",
            "Software flags a number. I notice the interval you bailed on and ask why.",
        ),
        (
            "02",
            "The patterns you can&#39;t see",
            "You can know everything about training and still train wrong. Knowledge isn&#39;t the limiter &mdash; application is. Every athlete is their own worst blindspot: too fresh to rest, too stubborn to taper, too close to their own data to see the shape of it. Seeing it is the job.",
        ),
        (
            "03",
            "The plan moves when your life does",
            "Sick kid, work trip, tender knee &mdash; the week adjusts that week, not after three missed targets teach an algorithm what a person would have seen on Tuesday.",
        ),
        (
            "04",
            "The truth, on schedule",
            "&ldquo;You&#39;re sandbagging&rdquo; and &ldquo;take the rest week&rdquo; are both part of the service.",
        ),
        (
            "05",
            "Involvement is the only variable",
            "Same coach, same standards. The difference is how often I&#39;m looking.",
        ),
    ]
    rows = "\n        ".join(
        f'<div class="gg-coach-term">'
        f'<div class="gg-coach-term-num">{num}</div>'
        f'<div class="gg-coach-term-body"><h3>{title}</h3><p>{body}</p></div>'
        f'</div>'
        for num, title, body in clauses
    )
    return f'''<section class="gg-coach-band gg-coach-terms" id="terms">
    <div class="gg-coach-inner">
      <div class="gg-coach-terms-list">
        {rows}
      </div>
    </div>
  </section>'''


def build_tiers() -> str:
    return f'''<section class="gg-coach-band gg-coach-tiers-section" id="tiers">
    <div class="gg-coach-inner">
      <div class="gg-coach-tiers">
        <div class="gg-coach-tier-col">
          <div class="gg-coach-tier-name">Min</div>
          <div class="gg-coach-tier-price">$199<span class="gg-coach-tier-interval">/ 4 WEEKS</span></div>
          <p class="gg-coach-tier-desc">The plan, plus a weekly check of your training. For athletes who execute on their own and want the thinking done right.</p>
          <ul class="gg-coach-tier-list">
            <li>Weekly training review</li>
            <li>File analysis</li>
            <li>Quarterly strategy calls</li>
            <li>Structured workouts for your trainer or head unit</li>
            <li>Race-day nutrition plan</li>
            <li>Custom training guide</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}?tier=min" class="gg-coach-tier-cta" data-cta="tier_min">GET STARTED</a>
        </div>
        <div class="gg-coach-tier-col">
          <div class="gg-coach-tier-name">Mid</div>
          <div class="gg-coach-tier-price">$299<span class="gg-coach-tier-interval">/ 4 WEEKS</span></div>
          <p class="gg-coach-tier-desc">The plan, watched. Someone reads the data between sessions and adjusts the same week life changes. Most athletes belong here.</p>
          <ul class="gg-coach-tier-list">
            <li>Everything in Min</li>
            <li>Detailed power-file analysis</li>
            <li>Every-4-week strategy calls</li>
            <li>Weekly plan adjustments</li>
            <li>Direct message access</li>
            <li>Blindspot detection</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}?tier=mid" class="gg-coach-tier-cta" data-cta="tier_mid">GET STARTED</a>
        </div>
        <div class="gg-coach-tier-col">
          <div class="gg-coach-tier-name">Max</div>
          <div class="gg-coach-tier-price">$1,200<span class="gg-coach-tier-interval">/ 4 WEEKS</span></div>
          <p class="gg-coach-tier-desc">Everything, daily. For the race where you want nothing left to chance.</p>
          <ul class="gg-coach-tier-list">
            <li>Everything in Mid</li>
            <li>Daily file review</li>
            <li>On-demand calls</li>
            <li>Race-week strategy</li>
            <li>Multi-race season planning</li>
            <li>Priority response</li>
          </ul>
          <a href="{QUESTIONNAIRE_URL}?tier=max" class="gg-coach-tier-cta" data-cta="tier_max">GET STARTED</a>
        </div>
      </div>
      <p class="gg-coach-tier-disclaimer">Coaching doesn&#39;t fix skipped workouts or feedback you don&#39;t act on. If this isn&#39;t a fit, I&#39;ll tell you within 24 hours.</p>
      <p class="gg-coach-tier-setup-fee">All tiers include a one-time $99 setup fee: intake analysis, training-history review, and your first plan build.</p>
    </div>
  </section>'''


def build_honest_check() -> str:
    return f'''<section class="gg-coach-band" id="fit">
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


def build_application_close() -> str:
    return f'''<section class="gg-coach-band gg-coach-band--dark" id="final-cta">
    <div class="gg-coach-inner">
      <div class="gg-coach-final-cta">
        <p class="gg-coach-final-kicker">APPLICATION</p>
        <p class="gg-coach-final-hook">Ten minutes of honest answers. I read every one myself. You&#39;ll hear from me within 48 hours &mdash; including if I don&#39;t think coaching is what you need.</p>
        <a href="{QUESTIONNAIRE_URL}" class="gg-coach-final-cta-link" data-cta="final_fill_intake">GET ME IN YOUR CORNER &rarr;</a>
        <p class="gg-coach-final-contact">Questions first? <a href="mailto:matt@gravelgodcycling.com">matt@gravelgodcycling.com</a> &mdash; I answer myself, usually within a day.</p>
      </div>
    </div>
  </section>'''


def build_footer() -> str:
    return get_mega_footer_html()


def build_mobile_sticky_cta() -> str:
    return f'''<div class="gg-coach-sticky-cta">
    <a href="{QUESTIONNAIRE_URL}" data-cta="sticky_cta">GET ME IN YOUR CORNER &rarr;</a>
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
/* Hairline (1px) separators are used throughout this page — terms
   clauses, tier columns, list rows, FAQ items. That is an
   owner-approved exception to the sitewide 2-3px brutalist border
   rule, scoped to these gg-coach-* rules only: the Dossier's clinical
   register earns its structure through precision (whitespace +
   hairlines), not heavy borders. */
.gg-coach-band {
  padding: var(--gg-spacing-2xl) 0;
}
.gg-coach-band--dark {
  background: var(--gg-color-dark-brown);
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

/* ── Hero — deadpan headline, corner CTA ─────────── */
.gg-coach-hero {
  padding-top: var(--gg-spacing-2xl);
  padding-bottom: var(--gg-spacing-2xl);
  border-bottom: 1px solid var(--gg-color-dark-brown);
}
.gg-coach-hero h1 {
  font-family: var(--gg-font-editorial);
  font-size: clamp(30px, 4.6vw, 44px);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-dark-brown);
  line-height: var(--gg-line-height-tight);
  margin: 0;
  max-width: 24ch;
}
.gg-coach-tagline {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-secondary-brown);
  max-width: 52ch;
  margin: var(--gg-spacing-lg) 0 0 0;
}
.gg-coach-hero-cta {
  display: inline-block;
  text-decoration: none;
  margin-top: var(--gg-spacing-xl);
  border: 1px solid var(--gg-color-dark-brown);
  padding: 15px 30px;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-dark-brown);
}

/* ── Terms — numbered clauses ─────────────────────── */
.gg-coach-terms {
  padding-bottom: 0;
}
.gg-coach-term {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: var(--gg-spacing-lg);
  padding: var(--gg-spacing-lg) 0;
  border-bottom: 1px solid var(--gg-color-tan);
}
.gg-coach-term:last-child {
  border-bottom: none;
}
.gg-coach-term-num {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
  padding-top: 4px;
}
.gg-coach-term-body h3 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
  line-height: var(--gg-line-height-tight);
}
.gg-coach-term-body p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  margin: 0;
  max-width: 60ch;
}

/* ── Tiers — quiet columns, no cards ──────────────── */
.gg-coach-tiers-section {
  padding-top: 0;
}
.gg-coach-tiers {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0;
  border-top: 1px solid var(--gg-color-dark-brown);
}
.gg-coach-tier-col {
  padding: var(--gg-spacing-xl) var(--gg-spacing-lg);
  border-right: 1px solid var(--gg-color-tan);
}
.gg-coach-tier-col:first-child {
  padding-left: 0;
}
.gg-coach-tier-col:last-child {
  border-right: none;
  padding-right: 0;
}
.gg-coach-tier-name {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  color: var(--gg-color-secondary-brown);
}
.gg-coach-tier-price {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xl);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-dark-brown);
  margin: var(--gg-spacing-sm) 0 0 0;
}
.gg-coach-tier-interval {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-regular);
  letter-spacing: var(--gg-letter-spacing-normal);
  color: var(--gg-color-secondary-brown);
  margin-left: var(--gg-spacing-2xs);
}
.gg-coach-tier-desc {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-dark-brown);
  margin: var(--gg-spacing-md) 0 var(--gg-spacing-lg) 0;
}
.gg-coach-tier-list {
  list-style: none;
  padding: 0;
  margin: 0 0 var(--gg-spacing-lg) 0;
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
.gg-coach-tier-cta {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-dark-brown);
  text-decoration: none;
  border-bottom: 1px solid var(--gg-color-dark-brown);
  padding-bottom: 2px;
  transition: color var(--gg-transition-hover),
              border-color var(--gg-transition-hover);
}
.gg-coach-tier-cta:hover {
  color: var(--gg-color-secondary-brown);
  border-color: var(--gg-color-secondary-brown);
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

/* ── Application close — dark band ────────────────── */
.gg-coach-final-cta {
  padding: var(--gg-spacing-xl) 0;
  text-align: left;
}
.gg-coach-final-kicker {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  margin: 0 0 var(--gg-spacing-lg) 0;
}
.gg-coach-final-hook {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xl);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-warm-paper);
  margin: 0 0 var(--gg-spacing-xl) 0;
  max-width: 26em;
}
.gg-coach-final-cta-link {
  display: inline-block;
  border: 1px solid var(--gg-color-warm-paper);
  padding: var(--gg-spacing-sm) var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-warm-paper);
  text-decoration: none;
  transition: background-color var(--gg-transition-hover),
              color var(--gg-transition-hover);
}
.gg-coach-final-cta-link:hover {
  background-color: var(--gg-color-warm-paper);
  color: var(--gg-color-dark-brown);
}
.gg-coach-final-contact {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-tan);
  margin-top: var(--gg-spacing-lg);
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
    border-top: 3px solid var(--gg-color-dark-brown);
    visibility: hidden;
    pointer-events: none;
  }
  .gg-coach-sticky-cta.gg-coach-sticky-visible {
    visibility: visible;
    pointer-events: auto;
  }
  .gg-coach-sticky-cta a {
    display: block;
    color: var(--gg-color-tan);
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
  .gg-coach-term {
    grid-template-columns: 1fr;
    gap: var(--gg-spacing-xs);
  }
  .gg-coach-term-num {
    padding-top: 0;
  }
  .gg-coach-tiers {
    grid-template-columns: 1fr;
  }
  .gg-coach-tier-col {
    border-right: none;
    border-bottom: 1px solid var(--gg-color-tan);
    padding: var(--gg-spacing-lg) 0;
  }
  .gg-coach-tier-col:first-child {
    padding-top: 0;
  }
  .gg-coach-tier-col:last-child {
    border-bottom: none;
    padding-bottom: 0;
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
''' + get_scroll_animation_css([]) + '\n</style>'


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
    { id: 'terms', label: '15_terms' },
    { id: 'tiers', label: '35_tiers' },
    { id: 'fit', label: '55_fit' },
    { id: 'faq', label: '85_faq' },
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
    wp_tag = f'<script type="application/ld+json">{_safe_json_for_script(webpage, separators=(",", ":"))}</script>'
    svc_tag = f'<script type="application/ld+json">{_safe_json_for_script(service, separators=(",", ":"))}</script>'
    return f'{wp_tag}\n  {svc_tag}'


# ── Assemble page ─────────────────────────────────────────────


def generate_coaching_page(external_assets: dict = None) -> str:
    canonical_url = f"{SITE_BASE_URL}/coaching/"

    nav = build_nav()
    hero = build_hero()
    terms = build_terms()
    tiers = build_tiers()
    honest = build_honest_check()
    faq = build_faq()
    final_cta = build_application_close()
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

  {terms}

  {tiers}

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
