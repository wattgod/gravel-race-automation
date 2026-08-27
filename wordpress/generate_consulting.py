#!/usr/bin/env python3
"""
Generate the Gravel God Consulting landing page in neo-brutalist style.

A brief, conversion-focused page for one-time 60-minute consulting calls.
Sultanic 8-beat copy (v2, docs/consulting-copy-v2.md): the read you can't
give yourself, delivered before the call — not a race-selection grab bag.

Uses brand tokens exclusively — zero hardcoded hex, no border-radius, no
box-shadow, no bounce easing, no entrance animations.

Usage:
    python generate_consulting.py
    python generate_consulting.py --output-dir ./output
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
    GA_MEASUREMENT_ID,
    get_ab_head_snippet,
    get_ga4_head_snippet,
    get_preload_hints,
)
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html, get_site_header_css
from cookie_consent import get_consent_banner_html

OUTPUT_DIR = Path(__file__).parent / "output"

# ── Constants ─────────────────────────────────────────────────

CONSULTING_PRICE_INT = 150
CONSULTING_PRICE = f"${CONSULTING_PRICE_INT}"
CONSULTING_DURATION = "60 minutes"
ADDON_PRICE_INT = 100
ADDON_PRICE = f"${ADDON_PRICE_INT}"
BOOKING_URL = "https://calendar.app.google/E282ZtBJAFBXYdYJ6"
RACE_COUNT = "750+"
PRIVACY_SENTENCE = (
    "Your answers and training data are used only to prepare your consult "
    "and any plan you buy; they aren&rsquo;t shared or sold and are deleted "
    "on request."
)
COACHING_URL = f"{SITE_BASE_URL}/coaching/"
QUIET_CLAUSE = (
    f'If the consult turns into &ldquo;I want this every week&rdquo; '
    f'&mdash; that&rsquo;s <a href="{COACHING_URL}">coaching</a>.'
)


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Page sections ─────────────────────────────────────────────


def build_nav() -> str:
    breadcrumb = f'''<div class="gg-breadcrumb">
  <a href="{SITE_BASE_URL}/">Home</a>
  <span class="gg-breadcrumb-sep">&rsaquo;</span>
  <span class="gg-breadcrumb-current">Consulting</span>
</div>'''
    return get_site_header_html(active="services") + breadcrumb


def build_hero() -> str:
    return f'''<section class="gg-consult-hero" id="hero">
  <div class="gg-consult-hero-inner">
    <h1 class="gg-consult-hero-title">The read you can&rsquo;t give yourself.</h1>
    <p class="gg-consult-hero-subtitle">Sixty minutes with a coach who has already been through your last six months of riding &mdash; the files, not the summary &mdash; and a written plan of action within 48 hours.</p>
    <div class="gg-consult-hero-price">
      <span class="gg-consult-price-tag">{CONSULTING_PRICE}</span>
      <span class="gg-consult-price-detail">{CONSULTING_DURATION} &middot; your training reviewed before we talk</span>
    </div>
    <form id="checkout" class="gg-consult-form" novalidate>
      <div class="gg-consult-form-row">
        <label class="gg-consult-form-label" for="consult-name">Name</label>
        <input type="text" id="consult-name" name="name" required aria-required="true" placeholder="Your name" autocomplete="name">
      </div>
      <div class="gg-consult-form-row">
        <label class="gg-consult-form-label" for="consult-email">Email</label>
        <input type="email" id="consult-email" name="email" required aria-required="true" placeholder="you@example.com" autocomplete="email">
      </div>
      <div class="gg-consult-form-row gg-consult-form-checkbox-row">
        <label class="gg-consult-checkbox-label" for="consult-addon">
          <input type="checkbox" id="consult-addon" name="plan_addon">
          <span>Add a custom 12-week plan built from the consult (+{ADDON_PRICE})</span>
        </label>
      </div>
      <input type="text" name="_honeypot" style="display:none" tabindex="-1" autocomplete="off">
      <button type="submit" class="gg-consult-form-submit gg-consult-btn-gold" data-cta="hero_book">Book the consult &mdash; {CONSULTING_PRICE}</button>
      <div class="gg-consult-form-message" role="alert" aria-live="polite" style="display:none"></div>
    </form>
  </div>
</section>'''


def build_two_futures() -> str:
    return f'''<section class="gg-consult-section gg-consult-section--alt" id="two-futures">
  <h2 class="gg-consult-section-title">Two futures</h2>
  <div class="gg-consult-prose">
    <p>Two ways to spend the next twelve weeks.</p>
    <p>In one, you keep doing what got you here &mdash; the plan off a forum, the intervals you like, the long ride you always do &mdash; and hope it adds up by race day.</p>
    <p>In the other, someone who reads training files for a living has already seen what your last six months actually were, and tells you the one thing that would change the most.</p>
    <p class="gg-consult-prose-emphasis">Same bike. Same hours. Different twelve weeks.</p>
  </div>
</section>'''


def _strip_glyph(kind: str) -> str:
    """Return the inline SVG markup for one how-it-works frame glyph.
    Decorative only — styled entirely via CSS classes (no var() in SVG attrs)."""
    if kind == "calendar":
        return '''<rect class="gg-consult-strip-glyph-shape" x="-16" y="-14" width="32" height="26"></rect>
      <line class="gg-consult-strip-glyph-shape" x1="-16" y1="-6" x2="16" y2="-6"></line>
      <line class="gg-consult-strip-glyph-shape" x1="-9" y1="-18" x2="-9" y2="-10"></line>
      <line class="gg-consult-strip-glyph-shape" x1="9" y1="-18" x2="9" y2="-10"></line>'''
    if kind == "link":
        return '''<circle class="gg-consult-strip-glyph-shape" cx="-7" cy="-7" r="10"></circle>
      <circle class="gg-consult-strip-glyph-shape" cx="7" cy="7" r="10"></circle>'''
    if kind == "form":
        return '''<rect class="gg-consult-strip-glyph-shape" x="-14" y="-18" width="28" height="36"></rect>
      <line class="gg-consult-strip-glyph-shape" x1="-8" y1="-9" x2="8" y2="-9"></line>
      <line class="gg-consult-strip-glyph-shape" x1="-8" y1="1" x2="8" y2="1"></line>
      <line class="gg-consult-strip-glyph-shape" x1="-8" y1="11" x2="3" y2="11"></line>'''
    if kind == "magnifier":
        return '''<polyline class="gg-consult-strip-glyph-shape" points="-18,10 -8,-6 2,6 12,-10 18,2"></polyline>
      <circle class="gg-consult-strip-glyph-shape gg-consult-strip-glyph-lens" cx="4" cy="-4" r="11"></circle>
      <line class="gg-consult-strip-glyph-shape" x1="12" y1="4" x2="20" y2="12"></line>'''
    if kind == "document":
        return '''<path class="gg-consult-strip-glyph-shape" d="M -12 -18 H 6 L 14 -10 V 18 H -12 Z"></path>
      <path class="gg-consult-strip-glyph-shape" d="M 6 -18 V -10 H 14"></path>
      <line class="gg-consult-strip-glyph-shape" x1="-6" y1="-2" x2="8" y2="-2"></line>
      <line class="gg-consult-strip-glyph-shape" x1="-6" y1="6" x2="8" y2="6"></line>'''
    return ""


def build_how_it_works() -> str:
    frames = [
        ("calendar", "Book.", "Thirty seconds. You get a welcome email with three links.", False),
        ("link", "Connect your TrainingPeaks.", "One click, sign in, tap Accept &mdash; I can now see your rides. No TrainingPeaks? Send me your files or a Strava link instead.", False),
        ("form", "Answer twelve questions.", "Your goal event, your hours, the one thing you most want answered. Five minutes.", False),
        ("magnifier", "Your read arrives &mdash; before we talk.", "I go through how you have actually been riding, not how you meant to. Then we get on a call and skip the basics.", True),
        ("document", "Sixty minutes, then a written plan of action within 48 hours.", "Specific. Referenced to your own data. Yours to keep.", False),
    ]
    xs = [90, 270, 450, 630, 810]

    svg_frames = ""
    for (kind, _title, _desc, emphasis), x in zip(frames, xs):
        frame_class = "gg-consult-strip-frame gg-consult-strip-frame--emphasis" if emphasis else "gg-consult-strip-frame"
        svg_frames += f'''<g class="{frame_class}" transform="translate({x},50)">
      <circle class="gg-consult-strip-disc" r="26"></circle>
      {_strip_glyph(kind)}
    </g>
    '''

    captions = ""
    for _kind, title, desc, emphasis in frames:
        cap_class = "gg-consult-strip-caption gg-consult-strip-caption--emphasis" if emphasis else "gg-consult-strip-caption"
        captions += f'''<div class="{cap_class}">
      <strong>{title}</strong> {desc}
    </div>
    '''

    return f'''<section class="gg-consult-section" id="how-it-works">
  <h2 class="gg-consult-section-title">How it works</h2>
  <div class="gg-consult-strip">
    <svg class="gg-consult-strip-svg" viewBox="0 0 900 100" aria-hidden="true" focusable="false">
      <line class="gg-consult-strip-rail" x1="50" y1="50" x2="850" y2="50"></line>
      {svg_frames}
    </svg>
    <div class="gg-consult-strip-captions">
      {captions}
    </div>
  </div>
</section>'''


def build_what_i_look_at() -> str:
    items = [
        "<strong>How much of your hard riding was actually hard.</strong> Long sustained efforts and short surges look the same in a weekly total. They train very different things. I separate them.",
        "<strong>Whether your fitness is climbing, flat, or quietly sliding</strong> &mdash; and how the last three months compare to the same stretch last year.",
        "<strong>Whether your long rides are getting easier deep in</strong>, or whether the last hour still costs you more than the first.",
        "<strong>When you last tested yourself, and whether the numbers your zones are built on are still true.</strong> Most people&rsquo;s aren&rsquo;t.",
        "<strong>Where your training doesn&rsquo;t match the event you&rsquo;re training for.</strong>",
    ]
    list_items = "\n".join(f'      <li>{item}</li>' for item in items)
    return f'''<section class="gg-consult-section gg-consult-section--alt" id="look">
  <h2 class="gg-consult-section-title">What I actually look at</h2>
  <ul class="gg-consult-look-list">
{list_items}
  </ul>
  <p class="gg-consult-look-note">You&rsquo;ll get the answers in plain English, with the numbers behind them if you want them.</p>
</section>'''


def build_what_we_cover() -> str:
    topics = [
        "Race selection",
        "Season planning",
        "How your week should be built",
        "Fuelling",
        "Bike and gear choices",
        "Race-day execution",
        "What to do about the thing that keeps going wrong",
    ]
    items = " &middot; ".join(topics)
    return f'''<section class="gg-consult-section" id="cover">
  <h2 class="gg-consult-section-title">What we can cover</h2>
  <p class="gg-consult-cover-list">{items}</p>
  <p class="gg-consult-cover-note">Not sure your question fits? It probably does. Book it and ask.</p>
</section>'''


def build_plan_addon() -> str:
    return f'''<section class="gg-consult-section gg-consult-section--alt" id="plan">
  <h2 class="gg-consult-section-title">The plan, if you want it (+{ADDON_PRICE})</h2>
  <div class="gg-consult-prose">
    <p>Most people leave the call knowing what to change. Some want it built.</p>
    <p><strong>Custom plan add-on &mdash; {ADDON_PRICE}.</strong> A twelve-week plan built from your consult and your data &mdash; not a template with your name on it &mdash; loaded onto your TrainingPeaks calendar within a week of the call, with one round of adjustments in the first fortnight.</p>
    <p>The honest limits: one goal event, up to twelve weeks. If your race is further out, we build the last twelve before it (or the next twelve &mdash; your call). Longer than that is coaching, and I&rsquo;ll say so. Available for seven days after the call; after that it&rsquo;s the store price.</p>
  </div>
</section>'''


def build_who() -> str:
    return f'''<section class="gg-consult-section" id="who">
  <h2 class="gg-consult-section-title">Who you&rsquo;ll talk to</h2>
  <div class="gg-consult-bio-text">
    <p>I&rsquo;m Matti. Twelve years at TrainingPeaks, 100+ athletes coached, 1,000+ training plans sold. I&rsquo;ve raced at the national level and blown up at mile 80 enough times to know what bad pacing actually costs.</p>
    <p>I built a database of {RACE_COUNT} gravel races &mdash; terrain, climbing, altitude, how they tend to be won and lost. When you ask &ldquo;which race should I do?&rdquo; or &ldquo;how do I fuel for this one?&rdquo;, the answer comes from that, not from vibes.</p>
  </div>
</section>'''


def build_fit() -> str:
    return f'''<section class="gg-consult-section gg-consult-section--alt" id="fit">
  <h2 class="gg-consult-section-title">Is this for you?</h2>
  <div class="gg-consult-fit-grid">
    <div class="gg-consult-fit-col gg-consult-fit-for">
      <h3 class="gg-consult-fit-title">For you if</h3>
      <p>you have a goal event and real questions &middot; you&rsquo;ll connect your TrainingPeaks or send files &middot; you want an answer, not reassurance.</p>
    </div>
    <div class="gg-consult-fit-col gg-consult-fit-not">
      <h3 class="gg-consult-fit-title">Not for you if</h3>
      <p>you want a pep talk &middot; you want to be told the plan you&rsquo;re on is fine. (It might be. I&rsquo;ll say so &mdash; and I&rsquo;ll say what isn&rsquo;t.)</p>
    </div>
  </div>
</section>'''


def build_faq() -> str:
    faqs = [
        (
            "What happens after I pay?",
            "A welcome email with three links: pick your time, answer the twelve questions, connect your TrainingPeaks. Do all three and I&rsquo;ll have your read done before we talk.",
        ),
        (
            "I don&rsquo;t use TrainingPeaks.",
            "Reply to the welcome email with a Strava link or your last three months of ride files. Same read, one extra step.",
        ),
        (
            "Do I have to share data?",
            "No &mdash; the call is still worth it. But the read is what makes this different from every other hour you could buy.",
        ),
        (
            "What if I need more than one session?",
            "Book another. Each one stands alone &mdash; no packages, no subscriptions.",
        ),
        (
            "Can I add the plan later?",
            f"Yes, for seven days after the call. The offer is in your plan-of-action email.",
        ),
        (
            "What happens to my data?",
            PRIVACY_SENTENCE,
        ),
    ]
    faq_html = ""
    for q, a in faqs:
        faq_html += f'''<div class="gg-consult-faq-item">
      <button class="gg-consult-faq-q" aria-expanded="false">{q}</button>
      <div class="gg-consult-faq-a">{a}</div>
    </div>
'''
    return f'''<section class="gg-consult-section" id="faq">
  <h2 class="gg-consult-section-title">Questions</h2>
  <div class="gg-consult-faqs">
    {faq_html}
  </div>
</section>'''


def build_close() -> str:
    return f'''<section class="gg-consult-cta" id="close">
  <div class="gg-consult-cta-inner">
    <h2 class="gg-consult-cta-title">Less than a race entry. More useful than the forum.</h2>
    <p class="gg-consult-cta-context">You already know what it feels like to start a race unsure the training was right. Sixty minutes to trade that for knowing.</p>
    <p class="gg-consult-cta-desc">{CONSULTING_PRICE} &middot; {CONSULTING_DURATION} &middot; written plan of action included</p>
    <a href="#checkout" class="gg-consult-btn-gold" data-cta="final_book">Book the consult &mdash; {CONSULTING_PRICE}</a>
    <p class="gg-consult-cta-quiet">{QUIET_CLAUSE}</p>
  </div>
</section>'''


def build_footer() -> str:
    return get_mega_footer_html()


def build_consulting_css() -> str:
    return f'''<style>
/* ── Consulting Page ────────────────────────────────────── */
{get_site_header_css()}

.gg-consult-hero {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl) var(--gg-spacing-xl);
  background: var(--gg-color-warm-paper);
  border-bottom: 3px solid var(--gg-color-dark-brown);
}}
.gg-consult-hero-inner {{
  max-width: 640px;
  margin: 0 auto;
  text-align: center;
}}
.gg-consult-hero-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(28px, 5vw, 42px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
  line-height: 1.15;
}}
.gg-consult-hero-subtitle {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-lg) 0;
}}
.gg-consult-hero-price {{
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--gg-spacing-xs);
  margin-bottom: var(--gg-spacing-lg);
}}
.gg-consult-price-tag {{
  font-family: var(--gg-font-data);
  font-size: 36px;
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-consult-price-detail {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
}}

/* ── Buttons ── */
.gg-consult-btn-gold {{
  display: inline-block;
  padding: var(--gg-spacing-sm) var(--gg-spacing-2xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  text-transform: uppercase;
  text-decoration: none;
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-light-gold);
  border: 3px solid var(--gg-color-dark-brown);
  transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover);
}}
.gg-consult-btn-gold:hover {{
  background-color: var(--gg-color-gold);
  border-color: var(--gg-color-gold);
}}

/* ── Sections ── */
.gg-consult-section {{
  padding: var(--gg-spacing-xl) var(--gg-spacing-xl);
  max-width: 720px;
  margin: 0 auto;
}}
.gg-consult-section--alt {{
  background: var(--gg-color-sand);
}}
.gg-consult-section--alt {{
  max-width: none;
}}
.gg-consult-section--alt > * {{
  max-width: 720px;
  margin-left: auto;
  margin-right: auto;
}}
.gg-consult-section-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(22px, 4vw, 30px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-lg) 0;
  text-align: center;
}}

/* ── Prose (Two futures / Plan add-on) ── */
.gg-consult-prose p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-consult-prose p:last-child {{ margin-bottom: 0; }}
.gg-consult-prose-emphasis {{
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown) !important;
}}

/* ── How It Works strip ── */
.gg-consult-strip {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-lg);
}}
.gg-consult-strip-svg {{
  width: 100%;
  height: auto;
  display: block;
}}
.gg-consult-strip-rail {{
  stroke: var(--gg-color-secondary-brown);
  stroke-width: 2;
}}
.gg-consult-strip-disc {{
  fill: var(--gg-color-warm-paper);
  stroke: var(--gg-color-dark-brown);
  stroke-width: 2;
}}
.gg-consult-strip-glyph-shape {{
  fill: none;
  stroke: var(--gg-color-dark-brown);
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}}
.gg-consult-strip-glyph-lens {{
  fill: var(--gg-color-warm-paper);
}}
.gg-consult-strip-frame--emphasis .gg-consult-strip-disc {{
  fill: var(--gg-color-light-gold);
  stroke-width: 3;
}}
.gg-consult-strip-frame--emphasis .gg-consult-strip-glyph-shape {{
  stroke-width: 3;
}}
.gg-consult-strip-captions {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--gg-spacing-sm);
}}
.gg-consult-strip-caption {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xs);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  text-align: center;
}}
.gg-consult-strip-caption strong {{
  display: block;
  color: var(--gg-color-dark-brown);
  margin-bottom: var(--gg-spacing-2xs);
}}
.gg-consult-strip-caption--emphasis strong {{
  color: var(--gg-color-gold);
}}

/* ── What I Actually Look At ── */
.gg-consult-look-list {{
  list-style: none;
  padding: 0;
  margin: 0 0 var(--gg-spacing-lg) 0;
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-md);
}}
.gg-consult-look-list li {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  padding-left: var(--gg-spacing-md);
  border-left: 3px solid var(--gg-color-gold);
}}
.gg-consult-look-note {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  text-align: center;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin: 0;
}}

/* ── What We Cover ── */
.gg-consult-cover-list {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-dark-brown);
  text-align: center;
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-consult-cover-note {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  text-align: center;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin: 0;
}}

/* ── FAQ ── */
.gg-consult-faqs {{
  display: flex;
  flex-direction: column;
  gap: var(--gg-spacing-sm);
}}
.gg-consult-faq-item {{
  border: 2px solid var(--gg-color-dark-brown);
  background: var(--gg-color-warm-paper);
}}
.gg-consult-faq-q {{
  display: block;
  width: 100%;
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-consult-faq-a {{
  max-height: 0;
  overflow: hidden;
  transition: max-height var(--gg-transition-hover);
  padding: 0 var(--gg-spacing-lg);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
}}
.gg-consult-faq-item.open .gg-consult-faq-a {{
  max-height: 300px;
  padding-bottom: var(--gg-spacing-md);
}}

/* ── Is This For You ── */
.gg-consult-fit-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-md);
}}
.gg-consult-fit-col {{
  padding: var(--gg-spacing-lg);
  background: var(--gg-color-warm-paper);
  border-left: 3px solid var(--gg-color-secondary-brown);
}}
.gg-consult-fit-for {{
  border-left-color: var(--gg-color-teal);
}}
.gg-consult-fit-not {{
  border-left-color: var(--gg-color-warm-brown);
}}
.gg-consult-fit-title {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-dark-brown);
  text-transform: uppercase;
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-consult-fit-col p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0;
}}

/* ── Close ── */
.gg-consult-cta {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  text-align: center;
  background: var(--gg-color-dark-brown);
}}
.gg-consult-cta-inner {{
  max-width: 640px;
  margin: 0 auto;
}}
.gg-consult-cta-title {{
  font-family: var(--gg-font-editorial);
  font-size: clamp(22px, 4vw, 30px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-white);
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-consult-cta-context {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-tan);
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-consult-cta-desc {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-tan);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  margin: 0 0 var(--gg-spacing-lg) 0;
}}
.gg-consult-cta-quiet {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-tan);
  margin: var(--gg-spacing-lg) 0 0 0;
}}
.gg-consult-cta-quiet a {{
  color: var(--gg-color-light-gold);
  transition: color var(--gg-transition-hover);
}}
.gg-consult-cta-quiet a:hover {{
  color: var(--gg-color-white);
}}

/* ── Breadcrumb (shared pattern) ── */
.gg-breadcrumb {{
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  max-width: 960px;
  margin: 0 auto;
  letter-spacing: var(--gg-letter-spacing-wide);
}}
.gg-breadcrumb a {{
  color: var(--gg-color-secondary-brown);
  text-decoration: none;
  transition: color var(--gg-transition-hover);
}}
.gg-breadcrumb a:hover {{ color: var(--gg-color-gold); }}
.gg-breadcrumb-sep {{ margin: 0 var(--gg-spacing-xs); }}

/* ── Checkout Form ── */
.gg-consult-form {{
  max-width: 480px;
  margin: var(--gg-spacing-lg) auto 0;
  text-align: left;
}}
.gg-consult-form-row {{
  margin-bottom: var(--gg-spacing-md);
}}
.gg-consult-form-label {{
  display: block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-dark-brown);
  margin-bottom: var(--gg-spacing-xs);
}}
.gg-consult-form input[type="text"],
.gg-consult-form input[type="email"] {{
  display: block;
  width: 100%;
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-white);
  border: 2px solid var(--gg-color-dark-brown);
  box-sizing: border-box;
}}
.gg-consult-form input[type="text"]:focus,
.gg-consult-form input[type="email"]:focus {{
  outline: none;
  border-color: var(--gg-color-gold);
}}
.gg-consult-form-checkbox-row {{
  display: flex;
}}
.gg-consult-checkbox-label {{
  display: flex;
  align-items: flex-start;
  gap: var(--gg-spacing-xs);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-primary-brown);
  cursor: pointer;
}}
.gg-consult-checkbox-label input[type="checkbox"] {{
  margin-top: 2px;
  flex-shrink: 0;
}}
.gg-consult-form-submit {{
  width: 100%;
  cursor: pointer;
  margin-top: var(--gg-spacing-sm);
}}
.gg-consult-form-submit:disabled {{
  opacity: 0.6;
  cursor: not-allowed;
}}
.gg-consult-form-message {{
  margin-top: var(--gg-spacing-sm);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
  text-align: center;
}}
.gg-consult-form-message.error {{
  color: var(--gg-color-dark-brown);
  border: 2px solid var(--gg-color-dark-brown);
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  background: var(--gg-color-warm-paper);
}}

/* ── Bio ── */
.gg-consult-bio-text {{
  max-width: 640px;
  margin: 0 auto;
}}
.gg-consult-bio-text p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0 0 var(--gg-spacing-md) 0;
}}
.gg-consult-bio-text p:last-child {{
  margin-bottom: 0;
}}

/* ── Responsive ── */
@media (max-width: 768px) {{
  .gg-consult-fit-grid {{ grid-template-columns: 1fr; }}
  .gg-consult-strip-captions {{ grid-template-columns: 1fr; }}
  .gg-consult-hero {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-consult-section {{ padding: var(--gg-spacing-lg) var(--gg-spacing-md); }}
  .gg-consult-cta {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
}}
</style>'''


def build_consulting_js() -> str:
    return f'''<script>
(function(){{
  /* FAQ accordion */
  document.querySelectorAll('.gg-consult-faq-q').forEach(function(btn){{
    btn.addEventListener('click',function(){{
      var item=btn.parentElement;
      var isOpen=item.classList.contains('open');
      document.querySelectorAll('.gg-consult-faq-item').forEach(function(el){{el.classList.remove('open');el.querySelector('.gg-consult-faq-q').setAttribute('aria-expanded','false')}});
      if(!isOpen){{item.classList.add('open');btn.setAttribute('aria-expanded','true')}}
      if(typeof gtag==='function'){{gtag('event','consulting_faq_open',{{'question':btn.textContent.slice(0,60)}})}}
    }});
  }});
  /* CTA click tracking */
  document.querySelectorAll('[data-cta]').forEach(function(el){{
    el.addEventListener('click',function(){{
      if(typeof gtag==='function'){{gtag('event','cta_click',{{source:'consulting',cta_name:el.getAttribute('data-cta')}})}}
    }});
  }});
  /* Scroll depth */
  if('IntersectionObserver' in window){{
    var fired={{}};
    var map={{'hero':'0_hero','two-futures':'12_two_futures','how-it-works':'25_how_it_works','look':'37_look','cover':'50_cover','plan':'62_plan','who':'75_who','fit':'87_fit','faq':'93_faq','close':'100_close'}};
    var obs=new IntersectionObserver(function(entries){{
      entries.forEach(function(e){{
        if(e.isIntersecting&&!fired[e.target.id]){{
          fired[e.target.id]=true;
          if(typeof gtag==='function'){{gtag('event','consulting_scroll_depth',{{'section':map[e.target.id]||e.target.id}})}}
        }}
      }});
    }},{{'threshold':0.3}});
    Object.keys(map).forEach(function(id){{var el=document.getElementById(id);if(el)obs.observe(el)}});
  }}
  /* Page view */
  if(typeof gtag==='function'){{gtag('event','consulting_page_view')}}

  /* Consent-aware GA4 identity handoff for the verified webhook purchase. */
  var GA_ATTRIBUTION_TIMEOUT_MS=500;
  function analyticsConsentGranted(){{
    if(/(^|; )gg_consent=declined/.test(document.cookie))return false;
    if(/(^|; )gg_consent=accepted/.test(document.cookie))return true;
    return window.ggConsentRequiresOptIn===false;
  }}
  function findGaMeasurementId(){{
    return '{GA_MEASUREMENT_ID}';
  }}
  function readGtagValue(measurementId,field){{
    return new Promise(function(resolve){{
      var settled=false;
      var timer=setTimeout(function(){{if(!settled){{settled=true;resolve('')}}}},GA_ATTRIBUTION_TIMEOUT_MS);
      try{{
        gtag('get',measurementId,field,function(value){{
          if(settled)return;settled=true;clearTimeout(timer);resolve(String(value||''));
        }});
      }}catch(error){{clearTimeout(timer);settled=true;resolve('')}}
    }});
  }}
  function getGa4Attribution(){{
    if(!analyticsConsentGranted()||typeof gtag!=='function')return Promise.resolve({{analytics_consent:'denied'}});
    var measurementId=findGaMeasurementId();
    if(!measurementId)return Promise.resolve({{analytics_consent:'granted'}});
    return Promise.all([
      readGtagValue(measurementId,'client_id'),
      readGtagValue(measurementId,'session_id')
    ]).then(function(values){{
      var attribution={{analytics_consent:'granted'}};
      if(/^\\d+\\.\\d+$/.test(values[0]))attribution.ga4_client_id=values[0];
      if(/^\\d+$/.test(values[1]))attribution.ga4_session_id=values[1];
      return attribution;
    }});
  }}

  /* ── Checkout form ── */
  var CHECKOUT_API='https://athlete-custom-training-plan-pipeline-production.up.railway.app/api/create-consulting-checkout';
  var CHECKOUT_PRICE={CONSULTING_PRICE_INT};
  var CHECKOUT_BTN_LABEL='Book the consult — ${CONSULTING_PRICE_INT}';
  var checkoutForm=document.getElementById('checkout');
  var checkoutMsg=checkoutForm?checkoutForm.querySelector('.gg-consult-form-message'):null;
  var checkoutBtn=checkoutForm?checkoutForm.querySelector('.gg-consult-form-submit'):null;
  var checkoutSubmitting=false;

  function showCheckoutError(msg){{
    checkoutMsg.className='gg-consult-form-message error';
    checkoutMsg.textContent=msg;
    checkoutMsg.style.display='block';
    checkoutBtn.disabled=false;
    checkoutBtn.textContent=CHECKOUT_BTN_LABEL;
    checkoutSubmitting=false;
    if(typeof gtag==='function'){{gtag('event','consulting_checkout_error',{{error:msg}})}}
  }}

  if(checkoutForm){{
    checkoutForm.addEventListener('submit',function(e){{
      e.preventDefault();
      if(checkoutSubmitting)return;
      var nameVal=checkoutForm.querySelector('input[name="name"]').value.trim();
      var emailVal=checkoutForm.querySelector('input[name="email"]').value.trim();
      var honeypot=checkoutForm.querySelector('input[name="_honeypot"]').value;
      var addonInput=checkoutForm.querySelector('input[name="plan_addon"]');
      var planAddon=addonInput?addonInput.checked:false;
      if(honeypot)return;
      if(!nameVal||!emailVal){{
        showCheckoutError('Please fill in your name and email.');
        return;
      }}
      if(!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(emailVal)){{
        showCheckoutError('Please enter a valid email address.');
        return;
      }}
      checkoutSubmitting=true;
      checkoutBtn.disabled=true;
      checkoutBtn.textContent='Preparing checkout...';
      checkoutMsg.style.display='none';

      if(typeof gtag==='function'){{gtag('event','begin_checkout',{{currency:'USD',value:planAddon?CHECKOUT_PRICE+{ADDON_PRICE_INT}:CHECKOUT_PRICE,items:[{{item_name:'Consulting Session'}}],plan_addon:planAddon}})}}

      var checkoutPayload={{name:nameVal,email:emailVal,hours:1,plan_addon:planAddon}};
      getGa4Attribution().then(function(attribution){{
        checkoutPayload.analytics_consent=attribution.analytics_consent||'denied';
        if(attribution.ga4_client_id)checkoutPayload.ga4_client_id=attribution.ga4_client_id;
        if(attribution.ga4_session_id)checkoutPayload.ga4_session_id=attribution.ga4_session_id;
        return fetch(CHECKOUT_API,{{
          method:'POST',
          headers:{{'Content-Type':'application/json'}},
          body:JSON.stringify(checkoutPayload)
        }});
      }})
      .then(function(r){{
        if(!r.ok)throw new Error('Server error ('+r.status+'). Please try again.');
        return r.json();
      }})
      .then(function(result){{
        if(result.checkout_url){{
          window.location.href=result.checkout_url;
        }}else{{
          throw new Error(result.error||'Failed to create checkout session');
        }}
      }})
      .catch(function(err){{
        showCheckoutError(err.message||'Something went wrong. Please try again.');
      }});
    }});
  }}

  /* Smooth scroll for #checkout links */
  document.querySelectorAll('a[href="#checkout"]').forEach(function(link){{
    link.addEventListener('click',function(e){{
      e.preventDefault();
      var target=document.getElementById('checkout');
      if(target){{target.scrollIntoView({{behavior:'smooth',block:'center'}});target.querySelector('input[name="name"]').focus()}}
    }});
  }});
}})();
</script>'''


def build_jsonld() -> str:
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Service",
  "name": "Gravel Race Consulting",
  "provider": {{
    "@type": "Organization",
    "name": "Gravel God Cycling",
    "url": "{SITE_BASE_URL}"
  }},
  "description": "One-on-one gravel training consulting: a coach's read of your last six months of riding, plus a written plan of action.",
  "offers": {{
    "@type": "Offer",
    "price": "{CONSULTING_PRICE_INT}",
    "priceCurrency": "USD",
    "description": "60-minute 1-on-1 video consultation with written plan of action"
  }},
  "url": "{SITE_BASE_URL}/consulting/"
}}
</script>'''


def generate_consulting_page(external_assets: dict = None) -> str:
    canonical_url = f"{SITE_BASE_URL}/consulting/"

    nav = build_nav()
    hero = build_hero()
    two_futures = build_two_futures()
    how = build_how_it_works()
    look = build_what_i_look_at()
    cover = build_what_we_cover()
    plan = build_plan_addon()
    who = build_who()
    fit = build_fit()
    faq = build_faq()
    close = build_close()
    footer = build_footer()
    consulting_css = build_consulting_css()
    consulting_js = build_consulting_js()
    jsonld = build_jsonld()

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    meta_desc = f"Sixty minutes with a coach who has already read your last six months of training. {CONSULTING_PRICE} with a written plan of action within 48 hours."

    og_tags = f'''<meta property="og:title" content="Consulting | Gravel God">
  <meta property="og:description" content="The read you can't give yourself. Sixty minutes, your training reviewed before we talk, a written plan of action after.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Consulting | Gravel God">
  <meta name="twitter:description" content="The read you can't give yourself. Sixty minutes, your training reviewed before we talk, a written plan of action after.">
  <meta name="twitter:image" content="{SITE_BASE_URL}/og/homepage.jpg">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Consulting | Gravel God</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {consulting_css}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {nav}

  {hero}

  {two_futures}

  {how}

  {look}

  {cover}

  {plan}

  {who}

  {fit}

  {faq}

  {close}

  {footer}
</div>

{inline_js}
{consulting_js}

{get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God consulting page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)

    html_content = generate_consulting_page(external_assets=assets)
    output_file = output_dir / "consulting.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
