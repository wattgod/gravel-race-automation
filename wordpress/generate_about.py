#!/usr/bin/env python3
"""
Generate the Gravel God About page in neo-brutalist style.

Tells the platform story: what we built, who's behind it, how we coach.
Loads race count dynamically from race-index.json. Reuses CSS/style patterns
from generate_neo_brutalist.py. Styling follows the brand guide component
library (principle cards, pullquotes, double-rule borders, tabs, stat cards).

Usage:
    python generate_about.py
    python generate_about.py --output-dir ./output
"""

import argparse
import html
import json
from pathlib import Path

from generate_neo_brutalist import (
    SITE_BASE_URL,
    SUBSTACK_URL,
    get_page_css,
    build_inline_js,
    write_shared_assets,
)
from brand_tokens import get_ab_head_snippet, get_ga4_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html
from cookie_consent import get_consent_banner_html

OUTPUT_DIR = Path(__file__).parent / "output"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_INDEX_PATH = PROJECT_ROOT / "web" / "race-index.json"


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
    return get_site_header_html(active="about") + f'''
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">About</span>
  </div>'''


def build_hero(race_count: int) -> str:
    return f'''<div class="gg-hero gg-about-hero">
    <div class="gg-hero-tier" style="background:var(--gg-color-gold)">ABOUT</div>
    <h1 data-text="{race_count} Gravel Races. Scored.">{race_count} Gravel Races. Scored.</h1>
    <p class="gg-hero-tagline">I scored every gravel race in America by hand, then paired it with coaching for people who have real jobs and limited PTO.</p>
  </div>'''


def build_why_this_exists() -> str:
    return '''<div class="gg-section" id="why">
    <div class="gg-section-header">
      <span class="gg-section-kicker">01</span>
      <h2 class="gg-section-title">Why This Exists</h2>
    </div>
    <div class="gg-section-body">
      <p class="gg-about-prose">Gravel race information lives in Instagram comments, Reddit threads, and word of mouth. You either trust a race organizer&#39;s marketing copy or cold-DM strangers who&#39;ve done the event. Course profiles are scattered across Strava segments nobody maintains. Registration costs, terrain breakdowns, and field quality are mysteries until you show up.</p>
      <div class="gg-about-highlight gg-about-highlight--gold">
        <p>I thought that was stupid. So I built a database.</p>
      </div>
    </div>
  </div>'''


def build_what_we_built(race_count: int) -> str:
    return f'''<div class="gg-section" id="what">
    <div class="gg-section-header">
      <span class="gg-section-kicker">02</span>
      <h2 class="gg-section-title">What I Built</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-about-stats">
        <div class="gg-about-stat">
          <span class="gg-about-stat-number">{race_count}</span>
          <span class="gg-about-stat-label">Races Rated</span>
        </div>
        <div class="gg-about-stat">
          <span class="gg-about-stat-number">15</span>
          <span class="gg-about-stat-label">Scoring Dimensions</span>
        </div>
        <div class="gg-about-stat">
          <span class="gg-about-stat-number">199+</span>
          <span class="gg-about-stat-label">Regions</span>
        </div>
        <div class="gg-about-stat">
          <span class="gg-about-stat-number">42</span>
          <span class="gg-about-stat-label">States + Countries</span>
        </div>
      </div>

      <!-- Tabbed feature panels -->
      <div class="gg-about-tabs" data-about-tabs>
        <div class="gg-about-tabs-nav">
          <button class="gg-about-tab gg-about-tab--active" data-about-tab="profiles">Race Profiles</button>
          <button class="gg-about-tab" data-about-tab="prep">Prep Kits</button>
          <button class="gg-about-tab" data-about-tab="compare">Compare Tool</button>
        </div>
        <div class="gg-about-tab-panel gg-about-tab-panel--active" data-about-panel="profiles">
          <p>Every race scored across 15 dimensions. Course difficulty, field depth, logistics, prestige, value &mdash; the stuff that actually matters when you&#39;re deciding where to spend your registration fee and PTO days.</p>
        </div>
        <div class="gg-about-tab-panel" data-about-panel="prep">
          <p>Race-specific training guidance, pacing strategy, fueling plans, and gear recommendations. The pre-race homework you&#39;d do if you had 40 hours to research one event.</p>
        </div>
        <div class="gg-about-tab-panel" data-about-panel="compare">
          <p>Side-by-side radar charts for 2&ndash;4 races. Because &ldquo;which one should I do?&rdquo; is the most common question in gravel, and the answer is never &ldquo;whichever has the best Instagram.&rdquo;</p>
        </div>
      </div>

      <p style="margin-top:24px"><a href="{SITE_BASE_URL}/race/methodology/" class="gg-about-link" data-cta="methodology">See exactly how I score races &rarr;</a></p>
    </div>
  </div>'''


def build_who() -> str:
    return f'''<div class="gg-section" id="who">
    <div class="gg-section-header">
      <span class="gg-section-kicker">03</span>
      <h2 class="gg-section-title">Who&#39;s Behind This</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-about-bio">
        <div class="gg-about-bio-text">
          <p class="gg-about-prose">I&#39;m Matti. I&#39;ve spent 12 years at TrainingPeaks teaching coaches and athletes how to get the most out of their training. Before that I raced at the National level for Team Rio Grande &mdash; until the team folded and my third kid arrived in the same year. Turns out those two events have a way of reshuffling your priorities.</p>
          <p class="gg-about-prose">I&#39;ve coached athletes and sold training plans &mdash; mostly to people who have real jobs, real families, and a limited tolerance for training plans that assume you have nothing else going on.</p>
          <div class="gg-about-highlight">
            <p>I built Gravel God because I kept answering the same questions from my athletes: <em>Which race should I do? How hard is this one, actually? What do I need to know before I register?</em> The answers were always buried in six different places. Now they&#39;re in one.</p>
          </div>
        </div>
        <div class="gg-about-bio-sidebar">
          <img src="/about/matti-avatar.png" alt="Matti — cartoon portrait" class="gg-about-bio-avatar" width="280" height="280" loading="lazy">
          <div class="gg-about-bio-card">
            <div class="gg-about-bio-card-label">Background</div>
            <dl class="gg-about-bio-dl">
              <dt>TrainingPeaks</dt><dd>12 years (only 2 promotions tho)</dd>
              <dt>Racing</dt><dd>CAT 1 roadie (CAT 5 handling skills)</dd>
              <dt>Team</dt><dd>Rio Grande Elite (until it folded)</dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  </div>'''


def build_coaching() -> str:
    return '''<div class="gg-section" id="coaching">
    <div class="gg-section-header">
      <span class="gg-section-kicker">04</span>
      <h2 class="gg-section-title">How I Coach</h2>
    </div>
    <div class="gg-section-body">
      <div class="gg-about-pillars">
        <div class="gg-about-pillar">
          <div class="gg-about-pillar-kicker">Principle 01</div>
          <h3>Life-First</h3>
          <p>Training has to survive real life. Jobs, kids, travel, the random Tuesday emergency. If a plan only works when everything goes perfectly, it doesn&#39;t work.</p>
        </div>
        <div class="gg-about-pillar">
          <div class="gg-about-pillar-kicker">Principle 02</div>
          <h3>Fundamentals Over Hype</h3>
          <p>Base fitness, pacing, fueling, recovery. The boring stuff that actually moves the needle. No secret workouts. No magic intervals. Just the things that compound over months.</p>
        </div>
        <div class="gg-about-pillar">
          <div class="gg-about-pillar-kicker">Principle 03</div>
          <h3>Execution Over Theory</h3>
          <p>A mediocre plan you actually follow beats the perfect plan you abandon in week three. I build around consistency, not optimization theater.</p>
        </div>
      </div>
    </div>
  </div>'''


def build_ctas() -> str:
    return f'''<div class="gg-section" id="cta">
    <div class="gg-section-body">
      <div class="gg-about-ctas">
        <div class="gg-about-cta">
          <h3>Training Plans</h3>
          <p data-ab="training_price">Race-specific. Built for your target event. Less than your race hotel &mdash; $2/day.</p>
          <a href="{SITE_BASE_URL}/questionnaire/" class="gg-about-cta-btn gg-about-cta-btn--gold" data-cta="training_plans" data-ab="training_cta_btn">BUILD MY PLAN</a>
        </div>
        <div class="gg-about-cta">
          <h3>1:1 Coaching</h3>
          <p>A human in your corner. Adapts week to week.</p>
          <a href="{SITE_BASE_URL}/coaching/apply/" class="gg-about-cta-btn gg-about-cta-btn--teal" data-cta="coaching_apply">APPLY</a>
        </div>
        <div class="gg-about-cta">
          <h3>Newsletter</h3>
          <p>Slow, Mid, 38s &mdash; essays on training, meaning, and not majoring in the minors.</p>
          <a href="{SUBSTACK_URL}" target="_blank" rel="noopener" class="gg-about-cta-btn" data-cta="newsletter">SUBSCRIBE</a>
        </div>
      </div>
    </div>
  </div>'''


def build_footer() -> str:
    return get_mega_footer_html()


def build_about_css() -> str:
    """Additional CSS specific to the about page — brand guide component patterns."""
    return '''<style>
/* ── About hero — light sandwash override ────────── */
.gg-neo-brutalist-page .gg-about-hero {
  background: var(--gg-color-warm-paper);
  border-bottom: 3px double var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-about-hero h1 {
  color: var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-about-hero .gg-hero-tagline {
  color: var(--gg-color-secondary-brown);
}

/* ── About page — prose ─────────────────────────── */
.gg-neo-brutalist-page .gg-about-prose {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  margin-bottom: var(--gg-spacing-md);
  max-width: 640px;
}

/* ── Highlighted paragraph (brand guide pattern) ─── */
.gg-neo-brutalist-page .gg-about-highlight {
  border-left: 4px solid var(--gg-color-teal);
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  background: var(--gg-color-sand);
  margin: var(--gg-spacing-lg) 0;
}
.gg-neo-brutalist-page .gg-about-highlight--gold {
  border-left-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-about-highlight p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-semibold);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-dark-brown);
  margin: 0;
}

/* ── Stat cards — light sandwash ─────────────────── */
.gg-neo-brutalist-page .gg-about-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0;
  background: var(--gg-color-warm-paper);
  border: var(--gg-border-standard);
  border-top: 3px double var(--gg-color-dark-brown);
  border-bottom: 3px double var(--gg-color-dark-brown);
  margin-bottom: var(--gg-spacing-xl);
}
.gg-neo-brutalist-page .gg-about-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--gg-spacing-lg) var(--gg-spacing-sm);
  border-right: 1px solid var(--gg-color-tan);
}
.gg-neo-brutalist-page .gg-about-stat:last-child {
  border-right: none;
}
.gg-neo-brutalist-page .gg-about-stat-number {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-3xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  line-height: var(--gg-line-height-tight);
  letter-spacing: var(--gg-letter-spacing-tight);
}
.gg-neo-brutalist-page .gg-about-stat-label {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  margin-top: var(--gg-spacing-xs);
}

/* ── Tabbed features — light with gold underline ─── */
.gg-neo-brutalist-page .gg-about-tabs {
  border: var(--gg-border-standard);
  background: var(--gg-color-warm-paper);
}
.gg-neo-brutalist-page .gg-about-tabs-nav {
  display: flex;
  background: var(--gg-color-sand);
  border-bottom: 3px double var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-about-tab {
  padding: var(--gg-spacing-sm) var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  transition: border-color var(--gg-transition-hover),
              color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-about-tab:hover {
  color: var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-about-tab--active {
  color: var(--gg-color-dark-brown);
  border-bottom-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-about-tab-panel {
  display: none;
  padding: var(--gg-spacing-lg);
}
.gg-neo-brutalist-page .gg-about-tab-panel--active {
  display: block;
}
.gg-neo-brutalist-page .gg-about-tab-panel p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  margin: 0;
  max-width: 640px;
}

/* ── Bio layout with sidebar card ──────────────── */
.gg-neo-brutalist-page .gg-about-bio {
  display: grid;
  grid-template-columns: 1fr 280px;
  gap: var(--gg-spacing-xl);
  align-items: start;
}
.gg-neo-brutalist-page .gg-about-bio-avatar {
  display: block;
  width: 100%;
  max-width: 280px;
  height: auto;
  border: var(--gg-border-standard);
  background: var(--gg-color-warm-paper);
  margin-bottom: var(--gg-spacing-md);
}
.gg-neo-brutalist-page .gg-about-bio-card {
  border: var(--gg-border-standard);
  background: var(--gg-color-sand);
}
.gg-neo-brutalist-page .gg-about-bio-card-label {
  padding: var(--gg-spacing-xs) var(--gg-spacing-md);
  background: var(--gg-color-primary-brown);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-extreme);
  text-transform: uppercase;
  color: var(--gg-color-warm-paper);
  border-bottom: var(--gg-border-standard);
}
.gg-neo-brutalist-page .gg-about-bio-dl {
  padding: var(--gg-spacing-md);
}
.gg-neo-brutalist-page .gg-about-bio-dl dt {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  color: var(--gg-color-gold);
  margin-top: var(--gg-spacing-sm);
}
.gg-neo-brutalist-page .gg-about-bio-dl dt:first-child {
  margin-top: 0;
}
.gg-neo-brutalist-page .gg-about-bio-dl dd {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  margin-top: var(--gg-spacing-2xs);
}

/* ── Coaching pillars (brand guide principle-card) ── */
.gg-neo-brutalist-page .gg-about-pillars {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gg-spacing-md);
}
.gg-neo-brutalist-page .gg-about-pillar {
  border: var(--gg-border-standard);
  padding: var(--gg-spacing-lg);
  background: var(--gg-color-warm-paper);
  transition: border-color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-about-pillar:hover {
  border-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-about-pillar-kicker {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-extreme);
  text-transform: uppercase;
  color: var(--gg-color-gold);
  margin-bottom: var(--gg-spacing-sm);
}
.gg-neo-brutalist-page .gg-about-pillar h3 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-sm) 0;
  line-height: var(--gg-line-height-tight);
}
.gg-neo-brutalist-page .gg-about-pillar p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-dark-brown);
  margin: 0;
}

/* ── CTA grid ────────────────────────────────────── */
.gg-neo-brutalist-page .gg-about-ctas {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gg-spacing-lg);
}
.gg-neo-brutalist-page .gg-about-cta {
  border: var(--gg-border-standard);
  padding: var(--gg-spacing-lg);
  background: var(--gg-color-warm-paper);
  display: flex;
  flex-direction: column;
  transition: border-color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-about-cta:hover {
  border-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-about-cta h3 {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-xs) 0;
}
.gg-neo-brutalist-page .gg-about-cta p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
  flex: 1;
}
.gg-neo-brutalist-page .gg-about-cta-btn {
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
  transition: background-color var(--gg-transition-hover),
              border-color var(--gg-transition-hover),
              color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-about-cta-btn:hover {
  background-color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-dark-brown);
}
.gg-neo-brutalist-page .gg-about-cta-btn--gold {
  background: var(--gg-color-gold);
  color: var(--gg-color-warm-paper);
  border-color: var(--gg-color-gold);
}
.gg-neo-brutalist-page .gg-about-cta-btn--gold:hover {
  background-color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
}
.gg-neo-brutalist-page .gg-about-cta-btn--teal {
  background: var(--gg-color-teal);
  color: var(--gg-color-warm-paper);
  border-color: var(--gg-color-teal);
}
.gg-neo-brutalist-page .gg-about-cta-btn--teal:hover {
  background-color: var(--gg-color-dark-brown);
  border-color: var(--gg-color-dark-brown);
  color: var(--gg-color-warm-paper);
}

/* ── Methodology link ────────────────────────────── */
.gg-neo-brutalist-page .gg-about-link {
  color: var(--gg-color-teal);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-decoration: none;
  letter-spacing: var(--gg-letter-spacing-wide);
  border-bottom: 2px solid var(--gg-color-teal);
  padding-bottom: 2px;
  transition: border-color var(--gg-transition-hover),
              color var(--gg-transition-hover);
}
.gg-neo-brutalist-page .gg-about-link:hover {
  color: var(--gg-color-gold);
  border-color: var(--gg-color-gold);
}

/* ── Responsive ──────────────────────────────────── */
@media (max-width: 768px) {
  .gg-neo-brutalist-page .gg-about-stats {
    grid-template-columns: repeat(2, 1fr);
  }
  .gg-neo-brutalist-page .gg-about-stat {
    border-right: none;
    border-bottom: 1px solid var(--gg-color-tan);
  }
  .gg-neo-brutalist-page .gg-about-stat:nth-child(odd) {
    border-right: 1px solid var(--gg-color-tan);
  }
  .gg-neo-brutalist-page .gg-about-stat:nth-last-child(-n+2) {
    border-bottom: none;
  }
  .gg-neo-brutalist-page .gg-about-bio {
    grid-template-columns: 1fr;
  }
  .gg-neo-brutalist-page .gg-about-pillars {
    grid-template-columns: 1fr;
  }
  .gg-neo-brutalist-page .gg-about-ctas {
    grid-template-columns: 1fr;
  }
  .gg-neo-brutalist-page .gg-about-tabs-nav {
    flex-wrap: wrap;
  }
}
</style>'''


def build_about_js() -> str:
    """Interactive JS for about page tabs, CTA clicks and scroll depth."""
    return '''<script>
// About page tabs
document.querySelectorAll('[data-about-tabs]').forEach(function(tabs) {
  tabs.querySelectorAll('.gg-about-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
      tabs.querySelectorAll('.gg-about-tab').forEach(function(t) { t.classList.remove('gg-about-tab--active'); });
      tabs.querySelectorAll('.gg-about-tab-panel').forEach(function(p) { p.classList.remove('gg-about-tab-panel--active'); });
      tab.classList.add('gg-about-tab--active');
      var panel = tabs.querySelector('[data-about-panel="' + tab.getAttribute('data-about-tab') + '"]');
      if (panel) panel.classList.add('gg-about-tab-panel--active');
      if (typeof gtag === 'function') gtag('event', 'about_tab_click', { tab_name: tab.getAttribute('data-about-tab') });
    });
  });
});

// CTA click tracking
document.querySelectorAll('[data-cta]').forEach(function(el) {
  el.addEventListener('click', function() {
    if (typeof gtag === 'function') gtag('event', 'cta_click', { source: 'about', cta_name: el.getAttribute('data-cta') });
  });
});

// Scroll depth milestones
(function() {
  if (typeof gtag !== 'function' || !('IntersectionObserver' in window)) return;
  var sections = [
    { id: 'why', label: 'why_this_exists' },
    { id: 'what', label: 'what_i_built' },
    { id: 'who', label: 'whos_behind_this' },
    { id: 'coaching', label: 'how_i_coach' },
    { id: 'cta', label: 'cta_section' }
  ];
  sections.forEach(function(s) {
    var el = document.getElementById(s.id);
    if (!el) return;
    new IntersectionObserver(function(entries, obs) {
      if (entries[0].isIntersecting) {
        gtag('event', 'about_scroll_depth', { section: s.label });
        obs.unobserve(el);
      }
    }, { threshold: 0.3 }).observe(el);
  });
})();
</script>'''


def build_jsonld(race_count: int) -> str:
    """Build WebPage + Person JSON-LD for the about page."""
    webpage = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": "About Gravel God — Race Intelligence & Coaching for Gravel Cyclists",
        "description": f"The story behind the internet's most comprehensive gravel race database. {race_count} races scored across 15 dimensions, plus coaching that works for people with real lives.",
        "url": f"{SITE_BASE_URL}/about/",
        "isPartOf": {
            "@type": "WebSite",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
    }
    person = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": "Matti Rowe",
        "jobTitle": "Head Coach",
        "worksFor": {
            "@type": "Organization",
            "name": "Gravel God Cycling",
            "url": SITE_BASE_URL,
        },
    }
    wp_tag = f'<script type="application/ld+json">{json.dumps(webpage, separators=(",", ":"))} </script>'
    person_tag = f'<script type="application/ld+json">{json.dumps(person, separators=(",", ":"))} </script>'
    return f'{wp_tag}\n  {person_tag}'


# ── Assemble page ──────────────────────────────────────────────


def generate_about_page(external_assets: dict = None) -> str:
    race_count = load_race_count()
    canonical_url = f"{SITE_BASE_URL}/about/"

    nav = build_nav()
    hero = build_hero(race_count)
    why = build_why_this_exists()
    what = build_what_we_built(race_count)
    who = build_who()
    coaching = build_coaching()
    ctas = build_ctas()
    footer = build_footer()
    about_css = build_about_css()
    about_js = build_about_js()
    jsonld = build_jsonld(race_count)

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    meta_desc = f"The story behind the internet&#39;s most comprehensive gravel race database. {race_count} races scored across 15 dimensions, plus coaching that works for people with real lives."

    og_tags = f'''<meta property="og:title" content="About Gravel God — Race Intelligence &amp; Coaching for Gravel Cyclists">
  <meta property="og:description" content="The story behind the internet&#39;s most comprehensive gravel race database. {race_count} races scored across 15 dimensions.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="About Gravel God — Race Intelligence &amp; Coaching for Gravel Cyclists">
  <meta name="twitter:description" content="{race_count} gravel races scored across 15 dimensions. Plus coaching that works for people with real lives.">
  <meta name="twitter:image" content="{SITE_BASE_URL}/og/homepage.jpg">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>About Gravel God — Race Intelligence &amp; Coaching for Gravel Cyclists</title>
  <meta name="description" content="{meta_desc}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {about_css}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {nav}

  {hero}

  {why}

  {what}

  {who}

  {coaching}

  {ctas}

  {footer}
</div>

{inline_js}
{about_js}

{get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God about page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Reuse shared assets if they exist, otherwise write them
    assets = write_shared_assets(output_dir)

    html_content = generate_about_page(external_assets=assets)
    output_file = output_dir / "about.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
