#!/usr/bin/env python3
"""
Generate the Gravel God Coaching landing page: "Field Notes".

The page reads like the file I keep on an athlete: graph-paper ground,
Sometype Mono labels, teal margin notes, an ID card with my photo that
crossfades into the v6.7 cartoon of me doing the same thing, a "week with
me" chart built only from the real inclusions, and the prices on a paper
ledger in a dark band (tabs on phone).

Rebuilt 2026-11-15 from the "Dossier" (hero → terms → tiers → fit → faq →
final-cta) after Matti called it monotone and picked mock "Opus C, field
notes", merged with the photo card from mock "Astra B". Section order:
hero (H1 + ID card) → fit → terms (what you get) → week → how-it-works →
tiers (levels ledger + 3-question picker) → faq → final-cta.

Not built, on purpose (no stand-ins): an athlete-words proof section and a
capacity line. Both wait on real words and a real number from Matti.

Uses brand tokens exclusively: zero hardcoded hex, no border-radius, no
box-shadow, no bounce easing.

Usage:
    python generate_coaching.py
    python generate_coaching.py --output-dir ./output
"""

import argparse
import html
import shutil
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

# Images the page needs. main() copies them next to coaching.html under
# coaching-img/, and push_wordpress.sync_coaching uploads that folder to
# /coaching/img/. A missing file stops the build: no stand-in picture.
IMG_SRC_DIR = Path(__file__).parent / "assets" / "coaching"
IMG_URL_BASE = "/coaching/img"
IMAGES = {
    # Real photo: grocery aisle, felt hat, frozen pizza (from the 2023 RGG post).
    "photo": ("matti-pizza.webp", 720, 960),
    # v6.7 character (gravel-god-character rig, street outfit) in the same pose.
    "cartoon": ("matti-pizza-v67.webp", 720, 960),
    # v6.7 guide art: post-race, medal, beer, mud.
    "close": ("post-race-v67.webp", 960, 640),
}
IMG_OUTPUT_SUBDIR = "coaching-img"

# ── Constants ─────────────────────────────────────────────────

QUESTIONNAIRE_URL = f"{SITE_BASE_URL}/coaching/apply/"
CONTACT_EMAIL = "gravelgodcoaching@gmail.com"

# Tier identity: the single source for name and price. The ledger head and
# the picker result both render from this, so a price can't drift.
TIERS = (
    ("min", "Min", "$199"),
    ("mid", "Mid", "$299"),
    ("max", "Max", "$1,200"),
)
TIER_INTERVAL = "every 4 weeks"
TIER_BLURBS = {
    "min": "You train on your own and want me checking the work once a week.",
    "mid": "I read your files between sessions and change the plan the same week your life changes.",
    "max": "I read every file the day it lands. For a season built around the one race you care about most.",
}

# The ID card under my photo. Every row is a public fact, already on the site:
# Day job, Road, Team: wordpress/generate_about.py (bio + "only 2 promotions
# tho", "CAT 5 handling skills", "until it folded", third kid). Gravel: the
# about page race list and the RGG race report ("I'd won in '21 and '22",
# wordpress/posts/i-didnt-screw-up-red-granite-grinder-and-neither-do-you-2/).
# Matti's first-person bio, so no inline [n] markers (the citation rule is for
# race facts and ratings). Matti asked for the bio line verbatim and a self-deprecating
# resume that says very few have gotten farther on less talent.
ID_BIO = "I&#39;m Matti Rowe. Peddler of bikes and hot takes, and really fast clients."
ID_ROWS = (
    ("Day job", "12 years at TrainingPeaks teaching coaches and athletes. Two promotions."),
    ("Road", "Cat 1 on the NRC, with Cat 5 handling skills."),
    ("Team", "Rio Grande Elite, until it folded the year my third kid arrived."),
    ("Gravel", "Unbound 200, SBT GRVL. Won Red Granite Grinder in 2021 and 2022."),
    ("Talent", "Modest. Very few people have gotten farther on less of it."),
)

# Picker: three questions, answers 1-3, the rounded mean marks a tier.
PICKER_INTRO = "Answer three questions and I&#39;ll mark one."
PICKER_QUESTIONS = (
    ("How often should I read your files?", (
        "Once a week is plenty",
        "Between sessions",
        "The day each one lands",
    )),
    ("When your week blows up, how fast should the plan move?", (
        "At the weekly review",
        "That same week",
        "Today, on a call",
    )),
    ("What&#39;s this season built around?", (
        "One race, my own way",
        "One race, done properly",
        "Several races, one season plan",
    )),
)
PICKER_EMPTY = "Answer all three and I&#39;ll mark a level."

# Ledger rows: (label, min, mid, max). True = included, False = not,
# a string = the value for that tier.
LEDGER_GROUPS = (
    ("Every level", (
        ("Weekly training review", True, True, True),
        ("File analysis", True, True, True),
        ("Structured workouts for your trainer or head unit", True, True, True),
        ("Race-day nutrition plan", True, True, True),
        ("Custom training guide", True, True, True),
        ("TrainingPeaks Premium", True, True, True),
        ("Strategy calls", "Quarterly", "Every 4 weeks", "Every 4 weeks + on demand"),
    )),
    ("Mid and Max", (
        ("Detailed power-file analysis", False, True, True),
        ("Weekly plan adjustments", False, True, True),
        ("Direct message access", False, True, True),
        ("Blindspot detection", False, True, True),
    )),
    ("Max only", (
        ("Daily file review", False, False, True),
        ("Race-week strategy", False, False, True),
        ("Multi-race season planning", False, False, True),
        ("Priority response", False, False, True),
    )),
)


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


def _img(key: str) -> tuple:
    name, w, h = IMAGES[key]
    return f"{IMG_URL_BASE}/{name}", w, h


def _sec_head(num: str, label: str, title: str, sub: str = "") -> str:
    sub_html = f'<p>{sub}</p>' if sub else ''
    return (
        f'<div class="gg-coach-sec-head">'
        f'<p class="gg-coach-label gg-coach-sec-num">{num} / {label}</p>'
        f'<div><h2 class="gg-coach-sec-title">{title}</h2>{sub_html}</div>'
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


def build_id_card() -> str:
    photo, pw, ph = _img("photo")
    toon, tw, th = _img("cartoon")
    rows = "\n          ".join(
        f'<div><span>{label}</span>{value}</div>' for label, value in ID_ROWS
    )
    return f'''<aside class="gg-coach-id" aria-label="Who I am">
        <div class="gg-coach-id-head"><span>File: Matti Rowe</span><span>GG-01</span></div>
        <figure class="gg-coach-id-photo">
          <img class="gg-coach-id-real" src="{photo}" alt="Me in a felt hat, grinning in the grocery aisle with a frozen pizza." width="{pw}" height="{ph}">
          <img class="gg-coach-id-toon" src="{toon}" alt="" aria-hidden="true" width="{tw}" height="{th}" loading="lazy">
        </figure>
        <p class="gg-coach-id-bio">{ID_BIO}</p>
        <div class="gg-coach-id-rows">
          {rows}
        </div>
      </aside>'''


def build_hero() -> str:
    return f'''<section class="gg-coach-band gg-coach-hero" id="hero">
    <div class="gg-coach-inner gg-coach-hero-grid">
      <div>
        <div class="gg-coach-hero-file"><span>File: Coaching</span><span>One-on-one</span><span>Gravel</span></div>
        <h1>Gravel coaching for people who want to <mark>throw down</mark> but still like to <mark>get down.</mark></h1>
        <p class="gg-coach-tagline">Three levels, from a weekly look at your training to every file read the day it lands. <strong>$199 to $1,200</strong> every 4 weeks.</p>
        <div class="gg-coach-hero-actions">
          <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-hero-cta" data-cta="hero_apply">APPLY FOR COACHING &rarr;</a>
          <span class="gg-coach-fine">About 10 minutes. I reply within two business days.</span>
        </div>
      </div>
      {build_id_card()}
    </div>
  </section>'''


def build_honest_check() -> str:
    yes = (
        "You have a gravel race on the calendar and a reason to go faster at it.",
        "You&#39;ll upload your files and tell me how the week went.",
        "You&#39;ll act on feedback you didn&#39;t ask for.",
    )
    no = (
        "Your race is next week.",
        "You need injury rehab. I&#39;m not a doctor or a physio.",
        "You won&#39;t upload files or reply to my comments.",
    )
    li = lambda items: "\n            ".join(
        f'<li><span class="gg-coach-box" aria-hidden="true"></span><span>{t}</span></li>' for t in items
    )
    return f'''<section class="gg-coach-band gg-coach-band--dark gg-coach-fit" id="fit">
    <div class="gg-coach-inner">
      {_sec_head("01", "Fit check", "Check the boxes before you apply.")}
      <div class="gg-coach-fit-grid">
        <div class="gg-coach-fit-yes">
          <h3>Coaching fits if</h3>
          <ul>
            {li(yes)}
          </ul>
        </div>
        <div class="gg-coach-fit-no">
          <h3>Probably not a fit if</h3>
          <ul>
            {li(no)}
          </ul>
        </div>
      </div>
    </div>
  </section>'''


def build_terms() -> str:
    items = (
        ("I read your rides.",
         "When you bail on an interval, or your heart rate creeps up at hour four, or a long ride gets cut short, I ask about it. At Min I look once a week. At Max I look the day the file lands."),
        ("A plan for your gravel race.",
         "Structured workouts built around your race&#39;s distance, climbing and surface, on TrainingPeaks for your trainer or head unit."),
        ("Fueling for the long day.",
         "A race-day nutrition plan for the hours you&#39;ll be out there."),
        ("The week moves when your life does.",
         "When a sick kid, a work trip or a sore knee lands, tell me. At Mid and Max, the week changes that week."),
        ("Straight answers.",
         "If you&#39;re sandbagging, I&#39;ll say so. If you need the rest week, I&#39;ll say that too."),
    )
    rows = "\n        ".join(
        f'<li><p class="gg-coach-label">Item {i:02d}</p><h3>{t}</h3><p>{b}</p></li>'
        for i, (t, b) in enumerate(items, start=1)
    )
    return f'''<section class="gg-coach-band" id="terms">
    <div class="gg-coach-inner">
      {_sec_head("02", "What you get", "I read your rides and change the plan the week your life changes.")}
      <ol class="gg-coach-get">
        {rows}
      </ol>
    </div>
  </section>'''


def build_week() -> str:
    rows = (
        ("Each ride", ("off", "Read at the weekly review"), ("on", "I read your files between sessions"), ("on", "Daily file review, the day it lands")),
        ("Each week", ("on", "Weekly training review and file analysis"), ("on", "Weekly plan adjustments, detailed power-file analysis, blindspot detection"), ("on", "Everything in Mid")),
        ("Life happens", ("off", "Changes land at the weekly review"), ("on", "Message me directly; the week changes that week"), ("on", "On-demand calls, priority response")),
        None,
        ("Strategy calls", ("on", "Quarterly"), ("on", "Every 4 weeks"), ("on", "Every 4 weeks, plus on demand")),
        ("Race week", ("on", "Race-day nutrition plan"), ("on", "Race-day nutrition plan"), ("on", "Race-week strategy and nutrition plan")),
        ("The season", ("on", "Custom training guide"), ("on", "Custom training guide"), ("on", "Multi-race season planning")),
    )
    body = []
    for row in rows:
        if row is None:
            body.append('<tr class="gg-coach-cad-note"><td colspan="4"><span class="gg-coach-note">The sick kid, the work trip, the sore knee. This is the row that separates the levels.</span></td></tr>')
            continue
        when, *cells = row
        tds = "".join(
            f'<td class="gg-coach-cad-{state}" data-t="{name.upper()}">{text}</td>'
            for (key, name, _p), (state, text) in zip(TIERS, cells)
        )
        body.append(f'<tr><th scope="row">{when}</th>{tds}</tr>')
    body_html = "\n          ".join(body)
    return f'''<section class="gg-coach-band gg-coach-band--sand" id="week">
    <div class="gg-coach-inner">
      {_sec_head("03", "A week with me", "What a week with me looks like, by level.", "Same plan, same race. The difference is how often I&#39;m looking and how fast things move.")}
      <table class="gg-coach-cad">
        <thead><tr><th>When</th><th>Min</th><th>Mid</th><th>Max</th></tr></thead>
        <tbody>
          {body_html}
        </tbody>
      </table>
    </div>
  </section>'''


def build_how_it_works() -> str:
    steps = (
        ("About 10 min", "You apply.", "Questions about your riding, your race and your week."),
        ("2 business days", "You hear back from me.", "Including when coaching isn&#39;t the right fit."),
        ("If it&#39;s a fit", "Agreement, then checkout.", "A short agreement and consent, then a link for your first 4 weeks plus the $99 setup fee."),
        ("Setup", "Your first plan.", "I set you up on TrainingPeaks and build your first plan from your intake."),
        ("Every week after", "The rhythm of your level.", "Everything in the chart above, at the pace you picked."),
    )
    rows = "\n        ".join(
        f'<li><span class="gg-coach-label">{when}</span><div><h3>{t}</h3><p>{b}</p></div></li>'
        for when, t, b in steps
    )
    return f'''<section class="gg-coach-band" id="how-it-works">
    <div class="gg-coach-inner">
      {_sec_head("04", "How it works", "What happens after you click apply.")}
      <ol class="gg-coach-steps">
        {rows}
      </ol>
    </div>
  </section>'''


def build_fit_check() -> str:
    """Three-question picker. Rendered `hidden`; build_coaching_js() shows
    it, so without JS the ledger stands alone."""
    sets = []
    for qi, (text, options) in enumerate(PICKER_QUESTIONS, start=1):
        labels = "\n          ".join(
            f'<label><input type="radio" name="gg-coach-q{qi}" value="{ai}"><span>{opt}</span></label>'
            for ai, opt in enumerate(options, start=1)
        )
        sets.append(f'''<fieldset><legend>Q{qi}</legend><p>{text}</p>
          {labels}</fieldset>''')
    fieldsets = "\n        ".join(sets)
    return f'''<form class="gg-coach-picker" id="gg-coach-picker" aria-label="Three questions to pick a level" hidden>
        {fieldsets}
      </form>
      <p class="gg-coach-picker-out" id="gg-coach-picker-out" aria-live="polite" hidden>{PICKER_EMPTY}</p>'''


def _ledger_cell(key: str, value) -> str:
    if value is True:
        inner = '<span class="gg-coach-y" role="img" aria-label="Included"></span>'
    elif value is False:
        inner = '<span class="gg-coach-n" role="img" aria-label="Not included"></span>'
    else:
        inner = value
    return f'<td class="gg-coach-t-{key}">{inner}</td>'


def build_tiers() -> str:
    heads = "\n            ".join(
        f'<th class="gg-coach-t-{key}" data-tier="{key}" scope="col">'
        f'<span class="gg-coach-tname">{name} <span class="gg-coach-tpick">My pick</span></span>'
        f'<span class="gg-coach-tprice">{price}</span>'
        f'<span class="gg-coach-tper">{TIER_INTERVAL}</span>'
        f'<span class="gg-coach-tblurb">{TIER_BLURBS[key]}</span></th>'
        for key, name, price in TIERS
    )
    body = []
    for group, rows in LEDGER_GROUPS:
        body.append(f'<tr class="gg-coach-grp"><th colspan="4" scope="colgroup">{group}</th></tr>')
        for label, *vals in rows:
            cells = "".join(_ledger_cell(key, v) for (key, _n, _p), v in zip(TIERS, vals))
            body.append(f'<tr><th scope="row">{label}</th>{cells}</tr>')
    body_html = "\n            ".join(body)
    foot = "\n            ".join(
        f'<td class="gg-coach-t-{key}"><a href="{QUESTIONNAIRE_URL}?tier={key}" class="gg-coach-btn gg-coach-tier-cta" data-cta="tier_{key}">APPLY FOR {name.upper()}</a></td>'
        for key, name, _p in TIERS
    )
    tabs = "\n        ".join(
        f'<button type="button" role="tab" data-tab="{key}" aria-selected="{"true" if key == "mid" else "false"}">{name}</button>'
        for key, name, _p in TIERS
    )
    return f'''<section class="gg-coach-band gg-coach-band--brown" id="tiers">
    <div class="gg-coach-inner">
      {_sec_head("05", "Levels &amp; prices", "Pick how closely I watch.", "Every level is billed every 4 weeks and includes TrainingPeaks Premium. " + PICKER_INTRO)}
      {build_fit_check()}
      <div class="gg-coach-tabs" role="tablist" aria-label="Levels" hidden>
        {tabs}
      </div>
      <table class="gg-coach-ledger" id="gg-coach-ledger">
        <colgroup><col class="gg-coach-c0"><col><col><col></colgroup>
        <thead>
          <tr>
            <th scope="col">Level</th>
            {heads}
          </tr>
        </thead>
        <tbody>
            {body_html}
        </tbody>
        <tfoot>
          <tr><td></td>
            {foot}
          </tr>
        </tfoot>
      </table>
      <div class="gg-coach-tier-setup-fee gg-coach-fine">
        <p><strong>$99 one-time setup fee</strong> on every level. It covers intake analysis, a review of your training history and your first plan build. Any waiver is offered privately, case by case.</p>
        <p>Coaching renews every 4 weeks. Cancel before the next renewal and you keep coaching through the weeks you&#39;ve paid for. No cancellation fee.</p>
      </div>
    </div>
  </section>'''


FAQS = (
    ("What happens after I apply?",
     "You hear back from me within two business days, including when I don&#39;t think coaching is the right fit. If it is, I send a short agreement, then a checkout link."),
    ("How often will I hear from you?",
     "Every week at minimum, and more as your race gets close. Mid and Max can message me directly."),
    ("Do I need a power meter?",
     "No. Every workout has effort targets you can ride by feel. Heart rate sharpens them, and a power meter sharpens them most."),
    ("What if I miss workouts?",
     "Tell me. I&#39;d rather move the workout than have you chase it on a tired Thursday."),
    ("How many hours do I need?",
     "I build around the hours you have."),
    ("How will I know it&#39;s working?",
     "We set baselines at intake and measure against them."),
    ("What&#39;s the $99 setup fee?",
     "It covers intake analysis, training-history review, and building your first plan. It&#39;s a one-time charge on top of your first billing cycle."),
    ("Can I cancel anytime?",
     "Yes. There is no long-term commitment. Coaching renews every four weeks; cancel before the next renewal and your access continues through the paid cycle. There is no cancellation fee."),
)


def build_faq() -> str:
    items = "\n        ".join(
        f'<details class="gg-coach-faq-item"><summary><span class="gg-coach-label">Q{i:02d}</span>'
        f'<span class="gg-coach-faq-q">{q}</span></summary><p>{a}</p></details>'
        for i, (q, a) in enumerate(FAQS, start=1)
    )
    return f'''<section class="gg-coach-band gg-coach-faq" id="faq">
    <div class="gg-coach-inner">
      {_sec_head("06", "Questions", "What people ask before they apply.")}
      <div class="gg-coach-faq-list">
        {items}
      </div>
    </div>
  </section>'''


def build_application_close() -> str:
    src, w, h = _img("close")
    return f'''<section class="gg-coach-band gg-coach-close" id="final-cta">
    <div class="gg-coach-inner gg-coach-close-grid">
      <div>
        <p class="gg-coach-label">07 / Application</p>
        <h2>Start your file.</h2>
        <p class="gg-coach-final-hook">About ten minutes of questions about your riding, your race and your week. You hear back within two business days.</p>
        <a href="{QUESTIONNAIRE_URL}" class="gg-coach-btn gg-coach-btn--gold" data-cta="final_fill_intake">APPLY FOR COACHING &rarr;</a>
        <p class="gg-coach-fine gg-coach-final-contact">Email me at <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> if you have questions first.<br>$99 one-time setup. Renews every 4 weeks; cancel before the next renewal, no fee.</p>
      </div>
      <figure class="gg-coach-close-img"><img src="{src}" alt="Cartoon of me after a gravel race, muddy, with a medal and a beer, leaning on my bike." width="{w}" height="{h}" loading="lazy"></figure>
    </div>
  </section>'''


def build_footer() -> str:
    return get_mega_footer_html()


def build_mobile_sticky_cta() -> str:
    return f'''<div class="gg-coach-sticky-cta">
    <a href="{QUESTIONNAIRE_URL}" data-cta="sticky_cta">APPLY FOR COACHING &rarr;</a>
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

/* ── Ground: graph paper ─────────────────────────── */
.gg-neo-brutalist-page {
  background-color: var(--gg-color-warm-paper);
  background-image:
    repeating-linear-gradient(0deg, var(--gg-color-sand) 0 1px, transparent 1px 24px),
    repeating-linear-gradient(90deg, var(--gg-color-sand) 0 1px, transparent 1px 24px);
}
.gg-coach-band { padding: var(--gg-spacing-4xl) 0; color: var(--gg-color-dark-brown); }
.gg-coach-band--dark { background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
.gg-coach-band--brown { background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); }
.gg-coach-band--sand { background: var(--gg-color-sand); border-top: var(--gg-border-width-standard) solid var(--gg-color-dark-brown); border-bottom: var(--gg-border-width-standard) solid var(--gg-color-dark-brown); }
.gg-coach-label { font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; font-weight: var(--gg-font-weight-bold); color: var(--gg-color-secondary-brown); margin: 0; }
.gg-coach-note { font-family: var(--gg-font-editorial); font-style: italic; color: var(--gg-color-teal); font-size: var(--gg-font-size-base); }
.gg-coach-fine { font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); line-height: var(--gg-line-height-normal); }
.gg-coach-btn { display: inline-block; font-family: var(--gg-font-data); font-weight: var(--gg-font-weight-bold); font-size: var(--gg-font-size-sm); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; text-decoration: none; padding: var(--gg-spacing-md) var(--gg-spacing-lg); background: var(--gg-color-teal); color: var(--gg-color-white); border: var(--gg-border-width-standard) solid var(--gg-color-teal); transition: background var(--gg-transition-hover), color var(--gg-transition-hover), border-color var(--gg-transition-hover); }
.gg-coach-btn:hover, .gg-coach-btn:focus-visible { background: var(--gg-color-near-black); border-color: var(--gg-color-near-black); color: var(--gg-color-white); }
.gg-coach-btn--gold { background: var(--gg-color-light-gold); border-color: var(--gg-color-light-gold); color: var(--gg-color-near-black); }
.gg-coach-btn--gold:hover, .gg-coach-btn--gold:focus-visible { background: var(--gg-color-warm-paper); border-color: var(--gg-color-warm-paper); color: var(--gg-color-near-black); }

/* ── Section heads: mono label on a teal rule ────── */
.gg-coach-sec-head { display: grid; grid-template-columns: 200px 1fr; gap: var(--gg-spacing-xl); margin-bottom: var(--gg-spacing-2xl); }
.gg-coach-sec-num { padding-top: var(--gg-spacing-sm); border-top: var(--gg-border-width-heavy) solid var(--gg-color-teal); color: var(--gg-color-teal); align-self: start; }
.gg-coach-sec-title { margin: 0; font-family: var(--gg-font-editorial); font-size: clamp(30px, 3.6vw, 46px); line-height: var(--gg-line-height-tight); letter-spacing: var(--gg-letter-spacing-tight); color: var(--gg-color-near-black); }
.gg-coach-sec-head p { margin: var(--gg-spacing-sm) 0 0; max-width: 46em; }
.gg-coach-band--dark .gg-coach-sec-title, .gg-coach-band--brown .gg-coach-sec-title { color: var(--gg-color-warm-paper); }
.gg-coach-band--dark .gg-coach-sec-num { color: var(--gg-color-light-teal); border-color: var(--gg-color-light-teal); }
.gg-coach-band--brown .gg-coach-sec-num { color: var(--gg-color-light-gold); border-color: var(--gg-color-light-gold); }
.gg-coach-band--brown .gg-coach-sec-head p { color: var(--gg-color-tan); }

/* ── Hero ────────────────────────────────────────── */
.gg-coach-hero { padding: var(--gg-spacing-3xl) 0; }
.gg-coach-hero-grid { display: grid; grid-template-columns: 1fr 360px; gap: var(--gg-spacing-3xl); align-items: start; }
.gg-coach-hero-file { display: flex; gap: var(--gg-spacing-lg); margin-bottom: var(--gg-spacing-lg); flex-wrap: wrap; }
.gg-coach-hero-file span { font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; border-bottom: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); padding-bottom: 2px; }
.gg-coach-hero h1 { font-family: var(--gg-font-editorial); font-weight: var(--gg-font-weight-bold); font-size: clamp(34px, 5vw, 66px); line-height: 1.04; letter-spacing: var(--gg-letter-spacing-tight); margin: 0 0 var(--gg-spacing-lg); color: var(--gg-color-near-black); }
.gg-coach-hero h1 mark { background: linear-gradient(transparent 58%, var(--gg-color-light-gold) 58%, var(--gg-color-light-gold) 92%, transparent 92%); color: inherit; padding: 0 2px; }
.gg-coach-tagline { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); margin: 0 0 var(--gg-spacing-xl); max-width: 34em; }
.gg-coach-tagline strong { font-family: var(--gg-font-data); font-size: 0.9em; background: var(--gg-color-dark-brown); color: var(--gg-color-light-gold); padding: 1px 6px; white-space: nowrap; }
.gg-coach-hero-actions { display: flex; flex-wrap: wrap; align-items: center; gap: var(--gg-spacing-md) var(--gg-spacing-lg); }

/* ── ID card: real photo crossfades to the v6.7 me ── */
.gg-coach-id { background: var(--gg-color-white); border: var(--gg-border-width-standard) solid var(--gg-color-dark-brown); transform: rotate(1.5deg); }
.gg-coach-id-head { background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); padding: var(--gg-spacing-xs) var(--gg-spacing-md); display: flex; justify-content: space-between; font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; }
.gg-coach-id-photo { position: relative; margin: var(--gg-spacing-md); aspect-ratio: 3 / 4; border: var(--gg-border-width-standard) solid var(--gg-color-light-gold); background: var(--gg-color-sand); overflow: hidden; }
.gg-coach-id-photo img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center 20%; }
.gg-coach-id-toon { opacity: 0; animation: gg-coach-idswap 9s ease-in-out 2s infinite; }
@keyframes gg-coach-idswap { 0%, 38% { opacity: 0; } 50%, 88% { opacity: 1; } 100% { opacity: 0; } }
.gg-coach-id-bio { margin: 0 var(--gg-spacing-md) var(--gg-spacing-md); font-family: var(--gg-font-editorial); font-weight: var(--gg-font-weight-bold); font-size: var(--gg-font-size-lg); line-height: var(--gg-line-height-tight); color: var(--gg-color-near-black); }
.gg-coach-id-rows { border-top: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); }
.gg-coach-id-rows div { display: grid; grid-template-columns: 76px 1fr; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-xs) var(--gg-spacing-md); border-bottom: 1px solid var(--gg-color-tan); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-sm); line-height: 1.35; }
.gg-coach-id-rows div:last-child { border-bottom: 0; }
.gg-coach-id-rows span { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-secondary-brown); padding-top: 2px; }

/* ── Fit check ───────────────────────────────────── */
.gg-coach-fit-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--gg-spacing-2xl); }
.gg-coach-fit h3 { font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; margin: 0 0 var(--gg-spacing-md); }
.gg-coach-fit-yes h3 { color: var(--gg-color-light-teal); }
.gg-coach-fit-no h3 { color: var(--gg-color-warm-brown); }
.gg-coach-fit ul { list-style: none; margin: 0; padding: 0; }
.gg-coach-fit li { display: grid; grid-template-columns: 28px 1fr; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-md) 0; border-top: 1px solid var(--gg-color-primary-brown); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); }
.gg-coach-box { width: 20px; height: 20px; border: var(--gg-border-width-subtle) solid currentColor; margin-top: 4px; position: relative; }
.gg-coach-fit-yes .gg-coach-box { color: var(--gg-color-light-teal); }
.gg-coach-fit-yes .gg-coach-box::after { content: ""; position: absolute; left: 5px; top: 1px; width: 6px; height: 11px; border: solid var(--gg-color-light-teal); border-width: 0 3px 3px 0; transform: rotate(45deg); }
.gg-coach-fit-no .gg-coach-box { color: var(--gg-color-warm-brown); }
.gg-coach-fit-no .gg-coach-box::before, .gg-coach-fit-no .gg-coach-box::after { content: ""; position: absolute; left: 7px; top: 1px; width: 3px; height: 14px; background: var(--gg-color-warm-brown); transform: rotate(45deg); }
.gg-coach-fit-no .gg-coach-box::after { transform: rotate(-45deg); }
.gg-coach-fit-no li { color: var(--gg-color-tan); }

/* ── What you get ────────────────────────────────── */
.gg-coach-get { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--gg-spacing-lg); }
.gg-coach-get li { background: var(--gg-color-warm-paper); border: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); padding: var(--gg-spacing-lg); }
.gg-coach-get li:first-child { grid-column: 1 / -1; background: var(--gg-color-dark-brown); color: var(--gg-color-warm-paper); }
.gg-coach-get li:first-child h3 { font-size: var(--gg-font-size-3xl); color: var(--gg-color-light-gold); }
.gg-coach-get li:first-child .gg-coach-label { color: var(--gg-color-light-gold); }
.gg-coach-get li:first-child p { font-size: var(--gg-font-size-lg); }
.gg-coach-get h3 { margin: var(--gg-spacing-xs) 0 var(--gg-spacing-sm); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xl); line-height: var(--gg-line-height-tight); }
.gg-coach-get p { margin: 0; max-width: 68ch; font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-relaxed); }

/* ── A week with me ──────────────────────────────── */
.gg-coach-cad { width: 100%; border-collapse: collapse; background: var(--gg-color-warm-paper); border: var(--gg-border-width-standard) solid var(--gg-color-dark-brown); font-family: var(--gg-font-editorial); }
.gg-coach-cad th, .gg-coach-cad td { text-align: left; vertical-align: top; padding: var(--gg-spacing-md); border-bottom: 1px solid var(--gg-color-tan); }
.gg-coach-cad thead th { background: var(--gg-color-dark-brown); color: var(--gg-color-light-gold); font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; border-bottom: 0; width: 28%; }
.gg-coach-cad thead th:first-child { color: var(--gg-color-warm-paper); width: 16%; }
.gg-coach-cad tbody th { font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-near-black); border-right: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); }
.gg-coach-cad td { font-size: var(--gg-font-size-base); }
.gg-coach-cad-off { color: var(--gg-color-warm-brown); }
.gg-coach-cad-on { font-weight: var(--gg-font-weight-semibold); }
.gg-coach-cad-on::before { content: ""; display: inline-block; width: 10px; height: 10px; background: var(--gg-color-teal); margin-right: var(--gg-spacing-xs); }
.gg-coach-cad-note td { border-bottom: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); padding-top: 0; }

/* ── How it works ────────────────────────────────── */
.gg-coach-steps { list-style: none; margin: 0; padding: 0; counter-reset: gg-step; max-width: 860px; }
.gg-coach-steps li { display: grid; grid-template-columns: 64px 180px 1fr; gap: var(--gg-spacing-lg); padding: var(--gg-spacing-lg) 0; border-top: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); align-items: baseline; }
.gg-coach-steps li:last-child { border-bottom: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); }
.gg-coach-steps li::before { counter-increment: gg-step; content: "0" counter(gg-step); font-family: var(--gg-font-data); font-weight: var(--gg-font-weight-bold); font-size: var(--gg-font-size-2xl); color: var(--gg-color-teal); }
.gg-coach-steps .gg-coach-label { color: var(--gg-color-gold); }
.gg-coach-steps h3 { margin: 0 0 var(--gg-spacing-2xs); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xl); line-height: var(--gg-line-height-tight); }
.gg-coach-steps p { margin: 0; font-family: var(--gg-font-editorial); }

/* ── Levels: picker + ledger ─────────────────────── */
.gg-coach-picker { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--gg-spacing-lg); margin-bottom: var(--gg-spacing-lg); }
.gg-coach-picker[hidden], .gg-coach-picker-out[hidden] { display: none; }
.gg-coach-picker fieldset { border: var(--gg-border-width-subtle) solid var(--gg-color-secondary-brown); padding: var(--gg-spacing-md); margin: 0; min-width: 0; }
.gg-coach-picker legend { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: var(--gg-color-light-gold); padding: 0 var(--gg-spacing-xs); }
.gg-coach-picker p { margin: 0 0 var(--gg-spacing-sm); font-family: var(--gg-font-editorial); font-weight: var(--gg-font-weight-semibold); font-size: var(--gg-font-size-base); }
.gg-coach-picker label { display: flex; gap: var(--gg-spacing-sm); align-items: center; font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); padding: var(--gg-spacing-2xs) 0; cursor: pointer; color: var(--gg-color-tan); }
.gg-coach-picker input { appearance: none; -webkit-appearance: none; width: 16px; height: 16px; border: var(--gg-border-width-subtle) solid var(--gg-color-tan); margin: 0; flex: none; background: transparent; cursor: pointer; }
.gg-coach-picker input:checked { background: var(--gg-color-light-gold); border-color: var(--gg-color-light-gold); }
.gg-coach-picker input:checked + span { color: var(--gg-color-warm-paper); font-weight: var(--gg-font-weight-bold); }
.gg-coach-picker input:focus-visible { outline: var(--gg-border-width-subtle) solid var(--gg-color-light-teal); outline-offset: 2px; }
.gg-coach-picker-out { font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; color: var(--gg-color-light-gold); margin: 0 0 var(--gg-spacing-xl); min-height: 1.5em; }
.gg-coach-tabs, .gg-coach-tabs[hidden] { display: none; }
.gg-coach-ledger { width: 100%; border-collapse: collapse; background: var(--gg-color-warm-paper); color: var(--gg-color-dark-brown); border: var(--gg-border-width-heavy) solid var(--gg-color-near-black); table-layout: fixed; font-family: var(--gg-font-editorial); }
.gg-coach-ledger th, .gg-coach-ledger td { padding: var(--gg-spacing-sm) var(--gg-spacing-md); border-bottom: 1px solid var(--gg-color-tan); text-align: left; vertical-align: top; }
.gg-coach-ledger col.gg-coach-c0 { width: 31%; }
.gg-coach-ledger thead th { background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); padding: var(--gg-spacing-lg) var(--gg-spacing-md); border-bottom: 0; border-left: 1px solid var(--gg-color-primary-brown); transition: background var(--gg-transition-hover); }
.gg-coach-ledger thead th:first-child { border-left: 0; vertical-align: bottom; font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: var(--gg-color-warm-brown); }
.gg-coach-tname { display: flex; justify-content: space-between; align-items: center; font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); letter-spacing: var(--gg-letter-spacing-ultra-wide); text-transform: uppercase; font-weight: var(--gg-font-weight-bold); color: var(--gg-color-light-gold); }
.gg-coach-tpick { visibility: hidden; font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wide); background: var(--gg-color-light-teal); color: var(--gg-color-near-black); padding: 2px 6px; }
.gg-coach-tprice { display: block; font-family: var(--gg-font-data); font-weight: var(--gg-font-weight-bold); font-size: clamp(40px, 4.6vw, 60px); line-height: 1; letter-spacing: -1px; margin: var(--gg-spacing-sm) 0 var(--gg-spacing-2xs); color: var(--gg-color-warm-paper); }
.gg-coach-tper { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; color: var(--gg-color-warm-brown); font-weight: var(--gg-font-weight-regular); }
.gg-coach-tblurb { display: block; font-family: var(--gg-font-editorial); font-style: italic; font-weight: var(--gg-font-weight-regular); font-size: var(--gg-font-size-base); color: var(--gg-color-tan); margin-top: var(--gg-spacing-md); line-height: var(--gg-line-height-normal); }
.gg-coach-ledger thead th.gg-coach-is-pick { background: var(--gg-color-teal); }
.gg-coach-ledger thead th.gg-coach-is-pick .gg-coach-tpick { visibility: visible; }
.gg-coach-ledger thead th.gg-coach-is-pick .gg-coach-tname,
.gg-coach-ledger thead th.gg-coach-is-pick .gg-coach-tper,
.gg-coach-ledger thead th.gg-coach-is-pick .gg-coach-tblurb { color: var(--gg-color-white); }
.gg-coach-ledger tbody th { font-weight: var(--gg-font-weight-regular); font-size: var(--gg-font-size-base); }
.gg-coach-ledger tbody td { border-left: 1px solid var(--gg-color-tan); text-align: center; }
.gg-coach-ledger .gg-coach-grp th { font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; background: var(--gg-color-sand); color: var(--gg-color-secondary-brown); font-weight: var(--gg-font-weight-bold); }
.gg-coach-y, .gg-coach-n { display: inline-block; width: 14px; height: 14px; vertical-align: middle; }
.gg-coach-y { background: var(--gg-color-teal); }
.gg-coach-n { height: 2px; background: var(--gg-color-tan); }
.gg-coach-ledger tfoot td { border-left: 1px solid var(--gg-color-tan); padding: var(--gg-spacing-md); background: var(--gg-color-sand); }
.gg-coach-ledger tfoot td:first-child { border-left: 0; }
.gg-coach-ledger tfoot .gg-coach-btn { display: block; text-align: center; padding: var(--gg-spacing-sm) var(--gg-spacing-xs); font-size: var(--gg-font-size-xs); }
.gg-coach-tier-setup-fee { display: grid; grid-template-columns: 1fr 1fr; gap: var(--gg-spacing-xl); margin-top: var(--gg-spacing-lg); color: var(--gg-color-tan); }
.gg-coach-tier-setup-fee p { margin: 0; }
.gg-coach-tier-setup-fee strong { color: var(--gg-color-warm-paper); }

/* ── FAQ ─────────────────────────────────────────── */
.gg-coach-faq { background: var(--gg-color-warm-paper); border-top: var(--gg-border-width-standard) solid var(--gg-color-dark-brown); }
.gg-coach-faq-list { max-width: 860px; }
.gg-coach-faq-item { border-top: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); }
.gg-coach-faq-item:last-child { border-bottom: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); }
.gg-coach-faq-item summary { list-style: none; cursor: pointer; display: grid; grid-template-columns: 56px 1fr 24px; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-md) 0; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); font-weight: var(--gg-font-weight-semibold); align-items: baseline; }
.gg-coach-faq-item summary::-webkit-details-marker { display: none; }
.gg-coach-faq-item summary .gg-coach-label { color: var(--gg-color-teal); }
.gg-coach-faq-item summary::after { content: "+"; font-family: var(--gg-font-data); font-size: var(--gg-font-size-xl); color: var(--gg-color-teal); }
.gg-coach-faq-item[open] summary::after { content: "\\2212"; }
.gg-coach-faq-item summary:focus-visible { outline: var(--gg-border-width-subtle) solid var(--gg-color-teal); outline-offset: 2px; }
.gg-coach-faq-item p { margin: 0 0 var(--gg-spacing-lg) 68px; max-width: 68ch; font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-relaxed); }

/* ── Application close ───────────────────────────── */
.gg-coach-close { background: var(--gg-color-teal); color: var(--gg-color-white); }
.gg-coach-close-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--gg-spacing-3xl); align-items: center; }
.gg-coach-close .gg-coach-label { color: var(--gg-color-white); }
.gg-coach-close h2 { font-family: var(--gg-font-editorial); font-size: clamp(32px, 4vw, 52px); line-height: var(--gg-line-height-tight); margin: var(--gg-spacing-sm) 0 var(--gg-spacing-md); color: var(--gg-color-white); }
.gg-coach-final-hook { margin: 0 0 var(--gg-spacing-lg); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); }
.gg-coach-final-contact { margin-top: var(--gg-spacing-md); }
.gg-coach-final-contact a { color: var(--gg-color-white); }
.gg-coach-close-img { margin: 0; border: var(--gg-border-width-standard) solid var(--gg-color-near-black); }
.gg-coach-close-img img { display: block; width: 100%; height: auto; }

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

/* ── Reduced motion: the photo stays, no swap ────── */
@media (prefers-reduced-motion: reduce) {
  .gg-coach-id-toon { animation: none; opacity: 0; }
  .gg-coach-btn, .gg-coach-ledger thead th { transition: none; }
}

/* ── Responsive ──────────────────────────────────── */
@media (max-width: 960px) {
  .gg-coach-hero-grid { grid-template-columns: 1fr; }
  .gg-coach-id { max-width: 420px; }
  .gg-coach-picker { grid-template-columns: 1fr; }
  .gg-coach-close-grid { grid-template-columns: 1fr; }
}
@media (max-width: 768px) {
  .gg-coach-inner { padding: 0 var(--gg-spacing-md); }
  .gg-coach-band { padding: var(--gg-spacing-3xl) 0; }
  .gg-coach-hero { padding: var(--gg-spacing-lg) 0 var(--gg-spacing-2xl); }
  .gg-coach-hero-file { gap: var(--gg-spacing-sm); margin-bottom: var(--gg-spacing-md); }
  .gg-coach-hero-file span { font-size: var(--gg-font-size-2xs); }
  .gg-coach-hero h1 { font-size: 33px; margin-bottom: var(--gg-spacing-md); }
  .gg-coach-tagline { font-size: var(--gg-font-size-base); margin-bottom: var(--gg-spacing-lg); }
  .gg-coach-hero-actions .gg-coach-btn { width: 100%; text-align: center; }
  .gg-coach-id { transform: none; }
  .gg-coach-sec-head { grid-template-columns: 1fr; gap: var(--gg-spacing-sm); margin-bottom: var(--gg-spacing-xl); }
  .gg-coach-sec-num { justify-self: start; }
  .gg-coach-fit-grid { grid-template-columns: 1fr; gap: var(--gg-spacing-xl); }
  .gg-coach-fit li { font-size: var(--gg-font-size-md); }
  .gg-coach-get { grid-template-columns: 1fr; }
  .gg-coach-get li:first-child h3 { font-size: var(--gg-font-size-2xl); }
  .gg-coach-cad, .gg-coach-cad tbody, .gg-coach-cad tr, .gg-coach-cad th, .gg-coach-cad td { display: block; width: 100%; }
  .gg-coach-cad thead { display: none; }
  .gg-coach-cad tr { border-bottom: var(--gg-border-width-subtle) solid var(--gg-color-dark-brown); padding: var(--gg-spacing-sm) 0; }
  .gg-coach-cad tbody th { border-right: 0; border-bottom: 0; padding: var(--gg-spacing-xs) var(--gg-spacing-md); color: var(--gg-color-teal); }
  .gg-coach-cad td { border-bottom: 0; padding: var(--gg-spacing-2xs) var(--gg-spacing-md); display: grid; grid-template-columns: 44px 1fr; gap: var(--gg-spacing-xs); }
  .gg-coach-cad td::before, .gg-coach-cad .gg-coach-cad-on::before { content: attr(data-t); display: block; width: auto; height: auto; background: none; margin: 0; font-family: var(--gg-font-data); font-size: var(--gg-font-size-2xs); letter-spacing: var(--gg-letter-spacing-wide); color: var(--gg-color-secondary-brown); font-weight: var(--gg-font-weight-bold); padding-top: 4px; }
  .gg-coach-cad .gg-coach-cad-note td { display: block; }
  .gg-coach-cad .gg-coach-cad-note td::before { content: none; }
  .gg-coach-steps li { grid-template-columns: 44px 1fr; gap: var(--gg-spacing-2xs) var(--gg-spacing-sm); }
  .gg-coach-steps li::before { grid-row: span 2; font-size: var(--gg-font-size-xl); }
  .gg-coach-tabs:not([hidden]) { display: grid; grid-template-columns: repeat(3, 1fr); }
  .gg-coach-tabs button { font-family: var(--gg-font-data); font-size: var(--gg-font-size-sm); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; font-weight: var(--gg-font-weight-bold); padding: var(--gg-spacing-sm) 0; background: var(--gg-color-primary-brown); color: var(--gg-color-tan); border: 0; border-bottom: var(--gg-border-width-heavy) solid var(--gg-color-near-black); cursor: pointer; }
  .gg-coach-tabs button[aria-selected="true"] { background: var(--gg-color-near-black); color: var(--gg-color-light-gold); }
  .gg-coach-ledger, .gg-coach-ledger tbody { display: block; border-top: 0; }
  .gg-coach-ledger colgroup { display: none; }
  .gg-coach-ledger tbody tr { display: grid; grid-template-columns: 1fr 34%; }
  .gg-coach-ledger tbody tr.gg-coach-grp { grid-template-columns: 1fr; }
  .gg-coach-ledger tbody tr > * { display: block; }
  .gg-coach-ledger thead, .gg-coach-ledger thead tr, .gg-coach-ledger thead th, .gg-coach-ledger tfoot, .gg-coach-ledger tfoot tr, .gg-coach-ledger tfoot td { display: block; width: 100%; }
  .gg-coach-ledger tbody td { font-size: var(--gg-font-size-sm); }
  .gg-coach-ledger[data-show="min"] .gg-coach-t-mid, .gg-coach-ledger[data-show="min"] .gg-coach-t-max,
  .gg-coach-ledger[data-show="mid"] .gg-coach-t-min, .gg-coach-ledger[data-show="mid"] .gg-coach-t-max,
  .gg-coach-ledger[data-show="max"] .gg-coach-t-min, .gg-coach-ledger[data-show="max"] .gg-coach-t-mid { display: none; }
  .gg-coach-ledger thead th:first-child { display: none; }
  .gg-coach-ledger thead th { border-left: 0; }
  .gg-coach-ledger tbody th { font-size: var(--gg-font-size-sm); }
  .gg-coach-ledger tfoot td:first-child { display: none; }
  .gg-coach-ledger tfoot td { border-left: 0; }
  .gg-coach-ledger tfoot .gg-coach-btn { padding: var(--gg-spacing-md); font-size: var(--gg-font-size-sm); }
  .gg-coach-tier-setup-fee { grid-template-columns: 1fr; gap: var(--gg-spacing-sm); }
  .gg-coach-faq-item summary { grid-template-columns: 40px 1fr 20px; font-size: var(--gg-font-size-md); }
  .gg-coach-faq-item p { margin-left: 52px; }
  .gg-coach-close .gg-coach-btn { width: 100%; text-align: center; }
  /* clears the fixed sticky CTA */
  .gg-mega-footer { padding-bottom: 72px; }
}
''' + get_scroll_animation_css([]) + '\n</style>'


def build_coaching_js() -> str:
    """Interactive JS: tier tabs, picker, FAQ + scroll-depth + CTA events, sticky CTA."""
    tier_labels = {key: f"Marked: {name}, {price} every 4 weeks." for key, name, price in TIERS}
    labels_js = _safe_json_for_script(tier_labels, separators=(",", ":"))
    return '''<script>
/* Levels: phone tabs + three-question picker. The picker is rendered
   hidden and only shown here, so without JS the ledger stands alone. */
(function() {
  var ledger = document.getElementById('gg-coach-ledger');
  if (!ledger) return;
  var tabs = document.querySelectorAll('.gg-coach-tabs button');
  function show(tier) {
    ledger.setAttribute('data-show', tier);
    tabs.forEach(function(b) { b.setAttribute('aria-selected', b.getAttribute('data-tab') === tier ? 'true' : 'false'); });
  }
  tabs.forEach(function(b) { b.addEventListener('click', function() { show(b.getAttribute('data-tab')); }); });
  /* Tabs exist only with JS. Without it the phone ledger shows all three
     levels stacked, so no price or apply link is ever out of reach. */
  var tablist = document.querySelector('.gg-coach-tabs');
  if (tablist) tablist.hidden = false;
  show('mid');

  var form = document.getElementById('gg-coach-picker');
  var out = document.getElementById('gg-coach-picker-out');
  if (!form || !out) return;
  var names = { 1: 'min', 2: 'mid', 3: 'max' };
  var labels = ''' + labels_js + ''';
  var current = null;
  form.addEventListener('change', function(e) {
    if (e.target && e.target.name && typeof gtag === 'function') gtag('event', 'coaching_fitcheck_answer', { question: e.target.name.slice(-1), answer: e.target.value });
    var v = [1, 2, 3].map(function(q) { var c = form.querySelector('input[name=gg-coach-q' + q + ']:checked'); return c ? +c.value : 0; });
    if (v.indexOf(0) !== -1) return;
    var tier = names[Math.round((v[0] + v[1] + v[2]) / 3)];
    out.textContent = labels[tier];
    ledger.querySelectorAll('thead th[data-tier]').forEach(function(th) { th.classList.toggle('gg-coach-is-pick', th.getAttribute('data-tier') === tier); });
    show(tier);
    if (tier !== current && typeof gtag === 'function') gtag('event', 'coaching_fitcheck_result', { tier: tier });
    current = tier;
  });
  form.hidden = false;
  out.hidden = false;
})();

/* FAQ: log opens */
document.querySelectorAll('.gg-coach-faq-item').forEach(function(d) {
  d.addEventListener('toggle', function() {
    if (d.open && typeof gtag === 'function') gtag('event', 'coaching_faq_open', { question: d.querySelector('.gg-coach-faq-q').textContent.trim().slice(0, 60) });
  });
});

/* Scroll depth tracking */
(function() {
  if (typeof gtag !== 'function' || !('IntersectionObserver' in window)) return;
  var sections = [
    { id: 'hero', label: '0_hero' },
    { id: 'fit', label: '10_fit' },
    { id: 'terms', label: '20_terms' },
    { id: 'week', label: '35_week' },
    { id: 'how-it-works', label: '45_how' },
    { id: 'tiers', label: '60_tiers' },
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
    if (typeof gtag === 'function') gtag('event', 'cta_click', { source: 'coaching', cta_name: el.getAttribute('data-cta') });
  });
});

/* Page view event */
if (typeof gtag === 'function') gtag('event', 'coaching_page_view');

/* Mobile sticky CTA: show after scrolling past hero */
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
        "description": "One-on-one gravel coaching from Matti Rowe. Three levels, from a weekly review to every file read the day it lands.",
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
        "description": "One-on-one gravel coaching: structured workouts for your race, file review, plan changes when your week changes, and a race-day nutrition plan.",
    }
    wp_tag = f'<script type="application/ld+json">{_safe_json_for_script(webpage, separators=(",", ":"))}</script>'
    svc_tag = f'<script type="application/ld+json">{_safe_json_for_script(service, separators=(",", ":"))}</script>'
    return f'{wp_tag}\n  {svc_tag}'


# ── Assemble page ─────────────────────────────────────────────


def generate_coaching_page(external_assets: dict = None) -> str:
    canonical_url = f"{SITE_BASE_URL}/coaching/"

    sections = "\n\n  ".join((
        build_nav(),
        build_hero(),
        build_honest_check(),
        build_terms(),
        build_week(),
        build_how_it_works(),
        build_tiers(),
        build_faq(),
        build_application_close(),
        build_footer(),
        build_mobile_sticky_cta(),
    ))
    coaching_css = build_coaching_css()
    coaching_js = build_coaching_js()
    jsonld = build_jsonld()

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    meta_desc = "Gravel coaching for people who want to throw down but still like to get down. I read your rides and change the plan when your week changes. From $199 every 4 weeks."

    og_tags = f'''<meta property="og:title" content="Coaching | Gravel God">
  <meta property="og:description" content="Gravel coaching for people who want to throw down but still like to get down. From $199 every 4 weeks.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/page-coaching.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Coaching | Gravel God">
  <meta name="twitter:description" content="Gravel coaching for people who want to throw down but still like to get down. From $199 every 4 weeks.">
  <meta name="twitter:image" content="{SITE_BASE_URL}/og/page-coaching.jpg">'''

    preload = get_preload_hints()
    photo_src = _img("photo")[0]

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
  <link rel="preload" as="image" href="{photo_src}">
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
  {sections}
</div>

{inline_js}
{coaching_js}

''' + '<script>' + get_site_header_js() + '</script>' + f'''

{get_consent_banner_html()}
</body>
</html>'''


def write_coaching_images(output_dir: Path) -> Path:
    """Copy the page's images to output_dir/coaching-img/. Raises if one is
    missing: the page never ships with a stand-in picture."""
    dest = output_dir / IMG_OUTPUT_SUBDIR
    dest.mkdir(parents=True, exist_ok=True)
    for name, _w, _h in IMAGES.values():
        src = IMG_SRC_DIR / name
        if not src.is_file():
            raise FileNotFoundError(f"coaching image missing: {src}")
        shutil.copy2(src, dest / name)
    return dest


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God coaching page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)
    write_coaching_images(output_dir)

    html_content = generate_coaching_page(external_assets=assets)
    output_file = output_dir / "coaching.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
