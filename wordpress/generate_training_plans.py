#!/usr/bin/env python3
"""
Generate the Gravel God Training Plans landing page in neo-brutalist style.

Port of web/training-plans.html (WordPress paste-in) into the generator system.
Full shared header/footer, brand tokens, JSON-LD, and GA4 tracking.

Uses brand tokens exclusively — zero hardcoded hex, no border-radius, no
box-shadow, no opacity transitions, no bounce easing.

Usage:
    python generate_training_plans.py
    python generate_training_plans.py --output-dir ./output
"""
from __future__ import annotations

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
from shared_header import get_site_header_html, get_site_header_css
from cookie_consent import get_consent_banner_html

OUTPUT_DIR = Path(__file__).parent / "output"

# ── Constants ─────────────────────────────────────────────────

QUESTIONNAIRE_URL = f"{SITE_BASE_URL}/questionnaire/"
TRAINING_PLANS_URL = f"{SITE_BASE_URL}/products/training-plans/"
PRICE_PER_WEEK = "$15"
PRICE_CAP = "$249"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Section builders ──────────────────────────────────────────


def build_nav() -> str:
    breadcrumb = f'''<div class="gg-breadcrumb">
  <a href="{SITE_BASE_URL}/">Home</a>
  <span class="gg-breadcrumb-sep">&rsaquo;</span>
  <span class="gg-breadcrumb-current">Training Plans</span>
</div>'''
    return get_site_header_html(active="products") + breadcrumb


def build_hero() -> str:
    return f'''<section class="gg-tp-hero" id="hero">
  <h1 class="gg-tp-hero-title">Your Race. Your Hours. Your Plan.</h1>
  <p class="gg-tp-hero-sub">Most training plans assume you&rsquo;re average. A parent with 5 hours a week needs fundamentally different training than someone with 15. This isn&rsquo;t a template with your name on it. It&rsquo;s a plan built from your schedule, your fitness, your race, and the specific demands of the course you&rsquo;re lining up for.</p>
  <div class="gg-tp-hero-cta">
    <a href="{QUESTIONNAIRE_URL}" class="gg-tp-btn" data-cta="hero_build">Build My Plan</a>
    <a href="#how-it-works" class="gg-tp-btn gg-tp-btn-secondary" data-cta="hero_how">See How It Works</a>
  </div>
  <div class="gg-tp-hero-bar">
    <div class="gg-tp-hero-bar-item"><strong>Same Day</strong><span>Delivery</span></div>
    <div class="gg-tp-hero-bar-item"><strong>Matched</strong><span>Methodology</span></div>
    <div class="gg-tp-hero-bar-item"><strong>$2/day</strong><span>Less Than a Tube</span></div>
    <div class="gg-tp-hero-bar-item"><strong>5 min</strong><span>To Start</span></div>
  </div>
</section>'''


DELIVERABLES = [
    (
        "01",
        "Structured Workouts on Your Device",
        "Every workout drops directly into TrainingPeaks, Zwift, Wahoo, "
        "or any platform that reads .zwo files. Power targets, cadence "
        "prescriptions (high RPM for efficiency, low RPM for gravel grinding), "
        "riding position cues (drops, hoods, standing), and durability efforts "
        "that simulate late-race fatigue. These dimensions change the stimulus "
        "even at identical power zones &mdash; because racing isn&rsquo;t just about "
        "watts. Open your app. The workout is there. Start pedaling.",
    ),
    (
        "02",
        "30+ Page Custom Training Guide",
        "Your power zones. Your fueling protocol. Your race-week countdown. "
        "Phase-by-phase breakdown of what you&rsquo;re building and why. If your race "
        "is in the database: suffering zones, terrain breakdown, altitude warnings, "
        "and the harsh reality of what the course demands. Not marketing. Data.",
    ),
    (
        "03",
        "Heat &amp; Altitude Training Protocols",
        "Racing at 6,700ft? In Kansas in June? The plan includes acclimatization "
        "protocols calibrated to your race conditions. Heat adaptation timelines. "
        "Altitude adjustment strategies. The stuff that separates finishing from "
        "finishing well.",
    ),
    (
        "04",
        "Race-Optimized Nutrition Plan",
        "Fueling protocol matched to your race distance and conditions. Calorie "
        "targets per hour. Hydration schedule. Race-morning meal timing. What to "
        "eat, when, and how much. Built from the course profile, not a generic "
        "calculator.",
    ),
    (
        "05",
        "Custom Strength Training",
        "Cycling-specific. Not CrossFit. Exercises that transfer to the bike, "
        "scaled to your strength experience &mdash; whether you&rsquo;ve never touched a "
        "barbell or you&rsquo;ve been lifting for years. Matched to whatever equipment "
        "you have. Phases from general strength into race-specific power. "
        "Stops when the taper starts.",
    ),
]

SAMPLE_WEEK_BLOCKS = [
    {
        "cls": "rest",
        "label": "Rest",
        "detail": "Active recovery or full rest. Strategic &mdash; not lazy. Your body adapts during rest, not during intervals.",
    },
    {
        "cls": "intervals",
        "label": "VO2max<br>Intervals<br>1hr",
        "detail": "4x4min @ 108-120% FTP / RPE 9. Cadence: 100-110rpm, seated on the hoods. Full recovery between efforts. Power targets, cadence, and position cues built into the .zwo file.",
        "structure": '[{"z":"z2","w":12,"h":45,"l":"WU 10m"},{"z":"z5","w":8,"h":85,"l":"4m"},{"z":"z1","w":6,"h":30,"l":"4m"},{"z":"z5","w":8,"h":88,"l":"4m"},{"z":"z1","w":6,"h":30,"l":"4m"},{"z":"z5","w":8,"h":90,"l":"4m"},{"z":"z1","w":6,"h":30,"l":"4m"},{"z":"z5","w":8,"h":92,"l":"4m"},{"z":"z2","w":10,"h":40,"l":"CD 8m"}]',
        "meta": "108-120% FTP | 100-110rpm | Hoods, seated",
    },
    {
        "cls": "endurance",
        "label": "Easy<br>Spin<br>45min",
        "detail": "Zone 2 spin. 55-75% FTP / RPE 3-4. Recovery between hard days. Nasal breathing pace.",
        "structure": '[{"z":"z2","w":100,"h":48,"l":"Z2 45m"}]',
        "meta": "55-75% FTP | 85-95rpm | Hoods",
    },
    {
        "cls": "intervals",
        "label": "G-Spot<br>1.5hr",
        "detail": "2x20min @ 88-94% FTP / RPE 7. The workhorse session. Builds sustained power you&rsquo;ll need at mile 60+. Cadence: 85-95rpm seated on the hoods. Position and cadence cues baked into the .zwo file.",
        "structure": '[{"z":"z2","w":12,"h":45,"l":"WU 10m"},{"z":"z3","w":6,"h":58,"l":"5m"},{"z":"z4","w":22,"h":72,"l":"20m"},{"z":"z2","w":6,"h":40,"l":"5m"},{"z":"z4","w":22,"h":74,"l":"20m"},{"z":"z3","w":6,"h":55,"l":"5m"},{"z":"z2","w":10,"h":40,"l":"CD"}]',
        "meta": "88-94% FTP | 85-95rpm | Hoods, seated",
    },
    {
        "cls": "strength",
        "label": "Strength<br>45min",
        "detail": "Cycling-specific. Bulgarian split squats, hip hinge work, single-leg stability. Scaled to your equipment and experience level. 40-50min.",
    },
    {
        "cls": "long-ride",
        "label": "Long<br>Ride<br>3hr",
        "detail": "Endurance ride with late-ride race-pace efforts &mdash; durability work. 2.5hrs zone 2, then 2x10min at threshold in the drops at 55rpm. Practices holding power on tired legs in an aero position at low cadence &mdash; exactly what gravel racing demands. Fueling targets included.",
        "structure": '[{"z":"z2","w":40,"h":48,"l":"Z2 2.5hrs"},{"z":"z3","w":5,"h":58,"l":""},{"z":"z4","w":10,"h":72,"l":"10m @FTP"},{"z":"z2","w":5,"h":40,"l":"5m"},{"z":"z4","w":10,"h":74,"l":"10m @FTP"},{"z":"z2","w":8,"h":40,"l":"CD"}]',
        "meta": "88-100% FTP (late ride) | 55rpm | Drops",
    },
    {
        "cls": "rest",
        "label": "Rest",
        "detail": "Full rest before the next training week. Sleep well. Eat well. The plan respects that you have a life outside of cycling.",
    },
]

REALITY_CHECKS = [
    "You downloaded a 12-week plan from the internet. It assumed you had 15 hours a week and zero injuries. How'd that go?",
    "Your buddy's training plan worked great. For your buddy. You're not your buddy.",
    "A 50-year-old with 5 hours needs fundamentally different training than a 28-year-old with 15. Different hours demand different science.",
    "You know what a generic plan does at mile 80 of Unbound? Nothing. Because it doesn't know you're at Unbound.",
    "Every training plan is a bet. Most plans are betting you're a 25-year-old with unlimited time and perfect recovery. Are you?",
    "The plan said 'tempo ride, 2 hours.' You had 45 minutes before school pickup. So you skipped it. Then you skipped Tuesday too.",
    "Your FTP is 230. Your plan was written for someone with an FTP of 300. You've been training in the wrong zones for 8 weeks.",
    "You have a smart trainer collecting dust. You have a race in 16 weeks. You have no plan. You have excuses. Pick one to fix.",
    "Nutrition plan: 'eat 60g carbs per hour.' At what elevation? In what heat? For what distance? Details matter. Vague advice kills races.",
    "Your strength training is whatever YouTube recommended this week. Your left hip flexor has an opinion about that.",
    "Rest days aren't lazy. They're where adaptation happens. Your plan should know which ones are strategic and which ones are panic.",
    "You're training for a 100-mile gravel race with a plan designed for 40km road crits. The specificity isn't there.",
    "Three hours a week can build you for a gravel century. But not with a plan that wastes two of them on junk miles.",
    "You told your last plan about your bad knee. It gave you plyometrics in week 3.",
    "Heat kills more gravel races than fitness. If your plan doesn't have an acclimatization protocol, it's not a plan. It's a wish.",
    "You tapered for 3 weeks because 'that's what the article said.' You lost fitness. Race day felt flat. Taper length is individual.",
    "Your race starts at 7,000 feet. Your plan was written at sea level. That's a different sport and nobody told you.",
    "Training without power zones is like cooking without measurements. You can do it. It's just worse.",
    "You finished your last race. You also bonked at mile 60, walked two climbs, and questioned your life choices. 'Finished' is a low bar.",
    "Somewhere right now, someone is doing their third 'base phase' of the year because they keep restarting the same generic plan.",
    "Your plan says 'G-Spot, 2 hours.' At what cadence? In what position? After how much fatigue? Those dimensions change the workout entirely. Most plans don't even know they exist.",
    "Mile 80 of your race, you'll be grinding at 55rpm in the drops on tired legs. Your training plan should have prepared you for that exact scenario. Did it?",
]


def _build_sample_week() -> str:
    """Build the interactive sample week grid."""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    day_cells = "\n".join(
        f'        <div class="gg-tp-sample-day">{d}</div>' for d in days
    )
    block_cells = ""
    for b in SAMPLE_WEEK_BLOCKS:
        data_detail = f' data-detail="{esc(b["detail"])}"'
        data_structure = ""
        data_meta = ""
        if "structure" in b:
            data_structure = f" data-structure='{b['structure']}'"
        if "meta" in b:
            data_meta = f' data-meta="{esc(b["meta"])}"'
        block_cells += f'        <div class="gg-tp-sample-block {b["cls"]}"{data_detail}{data_structure}{data_meta}>{b["label"]}</div>\n'

    return f'''<div class="gg-tp-sample-week">
      <div class="gg-tp-sample-week-label">Sample Build Week (8 hrs/wk athlete) <span class="gg-tp-sample-hint">&mdash; click a session for details</span></div>
      <div class="gg-tp-sample-grid">
{day_cells}
{block_cells}      </div>
      <div class="gg-tp-sample-detail" id="gg-tp-sample-detail" style="display:none;"></div>
    </div>'''


def build_what_you_get() -> str:
    rows = ""
    for num, title, desc in DELIVERABLES:
        rows += f'''<div class="gg-tp-deliverable-row">
        <div class="gg-tp-deliverable-num">{num}</div>
        <div class="gg-tp-deliverable-content">
          <h3>{title}</h3>
          <p>{desc}</p>
        </div>
      </div>
'''
    sample_week = _build_sample_week()
    return f'''<section class="gg-tp-section" id="what-you-get">
  <div class="gg-tp-section-label">What You Get</div>
  <h2>Five Things. All Custom. Zero Filler.</h2>
  <div class="gg-tp-deliverables">
    {rows}
  </div>
  {sample_week}
</section>'''


def build_how_it_works() -> str:
    process_cards = [
        ("01", "Questionnaire", "5 min form"),
        ("02", "TrainingPeaks", "Connect account"),
        ("03", "Plan Built", "Matched to you"),
        ("04", "You Train", "Same day delivery"),
    ]
    cards_html = ""
    for num, title, desc in process_cards:
        cards_html += f'''<div class="gg-tp-process-step">
        <div class="gg-tp-process-num">{num}</div>
        <h4>{esc(title)}</h4>
        <p>{esc(desc)}</p>
      </div>
'''
    steps = [
        ("01", "Fill Out the Questionnaire",
         "Your race. Your hours. Your fitness. Your constraints. Injuries. Goals. The stuff most plans never ask about. Five minutes. Be honest &mdash; the plan is only as good as the data."),
        ("02", "Connect on TrainingPeaks",
         "Attach to my TrainingPeaks Coach Account. This is how the plan gets to your calendar. Free TrainingPeaks account works fine."),
        ("03", "I Build Your Plan",
         "Your intake hits the methodology engine. The training approach gets selected based on your profile. Polarized for the time-crunched. Pyramidal for the balanced. Block for the serious. Matched to your availability and ability."),
        ("04", "Plan Drops Into Your Calendar",
         "I push the plan directly into your TrainingPeaks calendar. Every workout. Every phase. Open your app &mdash; it&rsquo;s there. Syncs to Zwift, Wahoo, Garmin. You start training. Delivered same day."),
    ]
    steps_html = ""
    for num, title, desc in steps:
        steps_html += f'''<div class="gg-tp-step">
        <div class="gg-tp-step-num">{num}</div>
        <div>
          <h3>{title}</h3>
          <p>{desc}</p>
        </div>
      </div>
'''
    return f'''<section class="gg-tp-section gg-tp-section-alt" id="how-it-works">
  <div class="gg-tp-section-label">How It Works</div>
  <h2>Four Steps. You Start Training Today.</h2>
  <div class="gg-tp-process">
    {cards_html}
  </div>
  <div class="gg-tp-steps">
    {steps_html}
  </div>
</section>'''


def build_rotating_quote() -> str:
    first_quote = esc(REALITY_CHECKS[0])
    return f'''<section class="gg-tp-pullquote" id="gg-tp-rotating-quote">
  <span class="gg-tp-reality-label">Reality Check</span>
  <p id="gg-tp-quote-text">{first_quote}</p>
</section>'''


def build_honest_check() -> str:
    buy_items = [
        "You have a race on the calendar and you&rsquo;re done winging it",
        "You have 3-15 hours a week and need every session to count",
        "You want structure that respects your actual life",
        "You can follow a plan without someone texting you every morning",
        "You&rsquo;re tired of generic plans that assume you&rsquo;re 25 with 20 hours",
    ]
    dont_items = [
        "You want ongoing coaching with weekly adjustments",
        "You don&rsquo;t have a target event",
        "Your race is in 3 weeks &mdash; not enough time to build anything real",
        "You need daily accountability to do the work",
        "You just want someone to tell you you&rsquo;re doing great",
    ]
    buy_li = "\n".join(f"          <li>{i}</li>" for i in buy_items)
    dont_li = "\n".join(f"          <li>{i}</li>" for i in dont_items)
    return f'''<section class="gg-tp-section gg-tp-section-alt" id="honest-check">
  <div class="gg-tp-section-label">Honest Check</div>
  <h2>This Isn&rsquo;t For Everyone. Good.</h2>
  <div class="gg-tp-audience-grid">
    <div class="gg-tp-audience-col">
      <h3>Buy This If:</h3>
      <ul class="gg-tp-audience-list gg-tp-for-list">
{buy_li}
      </ul>
    </div>
    <div class="gg-tp-audience-col gg-tp-not-for">
      <h3>Don&rsquo;t Buy This If:</h3>
      <ul class="gg-tp-audience-list gg-tp-not-list">
{dont_li}
      </ul>
    </div>
  </div>
</section>'''


def build_testimonials() -> str:
    testimonials = [
        (
            "I finished Mid-South 45 minutes faster than last year. The plan accounted for my 6-hour work weeks and bad left knee. Nothing else I tried did that.",
            "Jason R.", "Mid-South 2025",
        ),
        (
            "First gravel century. The fueling plan alone saved me. I watched people bonk at mile 60 while I was eating exactly what my plan said to eat.",
            "Sarah M.", "Unbound 100 2025",
        ),
        (
            "I have 5 hours a week and two kids. Every session in this plan mattered. No junk miles. Finished Big Sugar strong for the first time ever.",
            "Mark D.", "Big Sugar 2025",
        ),
    ]
    cards = ""
    for quote, name, event in testimonials:
        cards += f'''<div class="gg-tp-testimonial">
        <p>&ldquo;{esc(quote)}&rdquo;</p>
        <cite>&mdash; {esc(name)} &middot; {esc(event)}</cite>
      </div>
'''
    return f'''<section class="gg-tp-section" id="testimonials">
  <div class="gg-tp-section-label">Athletes</div>
  <h2>Don&rsquo;t Take My Word For It.</h2>
  <div class="gg-tp-testimonials">
    {cards}
  </div>
</section>'''


def build_pricing() -> str:
    return f'''<section class="gg-tp-section" id="pricing">
  <div class="gg-tp-section-label">Pricing</div>
  <h2>{PRICE_PER_WEEK} Per Week. One Payment. No Subscription.</h2>
  <div class="gg-tp-pricing-wrap">
    <div class="gg-tp-pricing-card">
      <div class="gg-tp-pricing-header">Custom Training Plan</div>
      <div class="gg-tp-price">{PRICE_PER_WEEK}<span> / week of training</span></div>
      <ul class="gg-tp-pricing-list">
        <li>Computed from your race date &mdash; pay for exactly what you need</li>
        <li>6-week plan = $90. 12-week plan = $180. 16-week plan = $240</li>
        <li>Capped at {PRICE_CAP} no matter how long the plan</li>
        <li>Structured .zwo workouts for Zwift/TrainingPeaks/Wahoo</li>
        <li>30+ page custom training guide</li>
        <li>Race-optimized fueling plan</li>
        <li>Custom strength program</li>
        <li>Heat &amp; altitude protocols</li>
        <li>Same-day delivery</li>
      </ul>
      <div class="gg-tp-pricing-cta">
        <a href="{QUESTIONNAIRE_URL}" class="gg-tp-btn" data-cta="pricing_build">Build My Plan</a>
      </div>
      <p class="gg-tp-pricing-note">Your entry fee was $175. Your hotel is $200. Your plan is $2/day. Don&rsquo;t show up without one.</p>
    </div>
  </div>
  <div class="gg-tp-guarantee">
    <p><strong>7-Day Money-Back Guarantee.</strong> If the plan doesn&rsquo;t meet your expectations, email me within 7 days for a full refund. No questions. No hoops.</p>
  </div>
</section>'''


FAQ_ITEMS = [
    (
        "Do I need a power meter?",
        "Not required. Every workout includes RPE targets so you can train by feel. But a power meter is strongly recommended &mdash; watt targets remove guesswork entirely. Heart rate works as a middle ground.",
    ),
    (
        "What if I don&rsquo;t know my FTP?",
        "Mark it unknown. Week 1 includes an FTP test protocol. Once you have the number, every zone recalibrates.",
    ),
    (
        "How are workouts delivered?",
        ".zwo files. Load directly into Zwift, TrainingPeaks, or anything that reads the format. Each file has power targets, cadence cues, and coaching text built in. Your guide is a web page &mdash; bookmark it.",
    ),
    (
        "How is the price calculated?",
        f"{PRICE_PER_WEEK} per week of training, computed from your race date. A 6-week plan is $90. A 12-week plan is $180. Anything over 16 weeks caps at {PRICE_CAP}. You pay for exactly what you need &mdash; no more.",
    ),
    (
        "Is this coaching?",
        "No. This is a plan, not a relationship. You get the full plan up front and execute it yourself. No weekly check-ins.",
    ),
    (
        "What if my race isn&rsquo;t in the database?",
        "The training still works. You won&rsquo;t get race-specific intel (suffering zones, terrain breakdown), but the workouts, phases, and structure are identical.",
    ),
]


def build_faq() -> str:
    faq_html = ""
    for q, a in FAQ_ITEMS:
        faq_html += f'''<div class="gg-tp-faq-item">
        <button class="gg-tp-faq-q" aria-expanded="false">{q}<span class="gg-tp-faq-toggle">+</span></button>
        <div class="gg-tp-faq-a"><p>{a}</p></div>
      </div>
'''
    return f'''<section class="gg-tp-section gg-tp-section-alt" id="faq">
  <div class="gg-tp-section-label">Questions</div>
  <h2>FAQ</h2>
  <div class="gg-tp-faq-list">
    {faq_html}
  </div>
</section>'''


def build_mobile_sticky() -> str:
    return f'''<div class="gg-tp-sticky-cta" id="gg-tp-sticky-cta">
  <a href="{QUESTIONNAIRE_URL}" data-cta="sticky_mobile">Build My Plan &mdash; $2/day</a>
</div>'''


def build_footer() -> str:
    return get_mega_footer_html()


# ── CSS ───────────────────────────────────────────────────────


def build_training_css() -> str:
    return f'''<style>
/* ── Training Plans Page ──────────────────────────────────── */
{get_site_header_css()}

/* ── Breadcrumb ── */
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

/* ── Layout ── */
.gg-tp-section {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  max-width: 900px;
  margin: 0 auto;
  border-bottom: var(--gg-border-standard);
}}
.gg-tp-section:last-of-type {{ border-bottom: none; }}
.gg-tp-section-alt {{
  background: var(--gg-color-sand);
  max-width: none;
  border-bottom-color: var(--gg-color-primary-brown);
}}
.gg-tp-section-alt > * {{
  max-width: 900px;
  margin-left: auto;
  margin-right: auto;
}}
.gg-tp-section-label {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  color: var(--gg-color-primary-brown);
  margin-bottom: var(--gg-spacing-sm);
  border-bottom: var(--gg-border-subtle);
  border-bottom-color: var(--gg-color-primary-brown);
  display: inline-block;
  padding-bottom: var(--gg-spacing-2xs);
}}
.gg-tp-section h2 {{
  font-family: var(--gg-font-data);
  font-size: clamp(24px, 5vw, 36px);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  line-height: var(--gg-line-height-tight);
  color: var(--gg-color-near-black);
  margin: 0 0 var(--gg-spacing-lg) 0;
}}

/* ── Buttons ── */
.gg-tp-btn {{
  display: inline-block;
  background: var(--gg-color-near-black);
  color: var(--gg-color-white);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  padding: var(--gg-spacing-sm) var(--gg-spacing-xl);
  border: var(--gg-border-standard);
  border-color: var(--gg-color-near-black);
  cursor: pointer;
  text-decoration: none;
  transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover);
}}
.gg-tp-btn:hover {{
  background-color: var(--gg-color-primary-brown);
  border-color: var(--gg-color-primary-brown);
  color: var(--gg-color-white);
}}
.gg-tp-btn-secondary {{
  background: transparent;
  color: var(--gg-color-near-black);
}}
.gg-tp-btn-secondary:hover {{
  background-color: var(--gg-color-sand);
  color: var(--gg-color-near-black);
}}

/* ── Hero ── */
.gg-tp-hero {{
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl) var(--gg-spacing-xl);
  max-width: 900px;
  margin: 0 auto;
  border-bottom: var(--gg-border-standard);
}}
.gg-tp-hero-title {{
  font-family: var(--gg-font-data);
  font-size: clamp(28px, 5vw, 42px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-near-black);
  margin: 0 0 var(--gg-spacing-lg) 0;
  max-width: 700px;
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  line-height: var(--gg-line-height-tight);
}}
.gg-tp-hero-sub {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  color: var(--gg-color-primary-brown);
  max-width: 600px;
  line-height: var(--gg-line-height-prose);
  margin: 0 0 var(--gg-spacing-xl) 0;
}}
.gg-tp-hero-cta {{
  display: flex;
  gap: var(--gg-spacing-md);
  flex-wrap: wrap;
  margin-bottom: var(--gg-spacing-xl);
}}
.gg-tp-hero-bar {{
  display: flex;
  gap: 0;
  border: var(--gg-border-standard);
  max-width: 550px;
}}
.gg-tp-hero-bar-item {{
  flex: 1;
  text-align: center;
  padding: var(--gg-spacing-sm) var(--gg-spacing-xs);
  border-right: var(--gg-border-standard);
}}
.gg-tp-hero-bar-item:last-child {{ border-right: none; }}
.gg-tp-hero-bar-item strong {{
  display: block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-lg);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-near-black);
}}
.gg-tp-hero-bar-item span {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  color: var(--gg-color-primary-brown);
  font-weight: var(--gg-font-weight-semibold);
}}

/* ── What You Get — Deliverables ── */
.gg-tp-deliverables {{
  display: flex;
  flex-direction: column;
  gap: 0;
  margin-top: var(--gg-spacing-lg);
  border: var(--gg-border-standard);
}}
.gg-tp-deliverable-row {{
  display: grid;
  grid-template-columns: 60px 1fr;
  border-bottom: var(--gg-border-standard);
}}
.gg-tp-deliverable-row:last-child {{ border-bottom: none; }}
.gg-tp-deliverable-num {{
  background: var(--gg-color-near-black);
  color: var(--gg-color-sand);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-bold);
  border-right: var(--gg-border-standard);
}}
.gg-tp-deliverable-content {{
  padding: var(--gg-spacing-lg);
}}
.gg-tp-deliverable-content h3 {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin: 0 0 var(--gg-spacing-xs) 0;
  color: var(--gg-color-near-black);
}}
.gg-tp-deliverable-content p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-primary-brown);
  margin: 0;
  line-height: var(--gg-line-height-prose);
}}
.gg-tp-deliverable-row:nth-child(odd) .gg-tp-deliverable-content {{
  background: var(--gg-color-white);
}}
.gg-tp-deliverable-row:nth-child(even) .gg-tp-deliverable-content {{
  background: var(--gg-color-sand);
}}

/* ── Sample Week ── */
.gg-tp-sample-week {{
  margin-top: var(--gg-spacing-xl);
  border: var(--gg-border-standard);
  background: var(--gg-color-sand);
  padding: var(--gg-spacing-lg);
}}
.gg-tp-sample-week-label {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  color: var(--gg-color-primary-brown);
  margin-bottom: var(--gg-spacing-sm);
}}
.gg-tp-sample-hint {{
  color: var(--gg-color-secondary-brown);
  font-weight: var(--gg-font-weight-regular);
}}
.gg-tp-sample-grid {{
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}}
.gg-tp-sample-day {{
  text-align: center;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  font-weight: var(--gg-font-weight-bold);
  padding: var(--gg-spacing-xs) var(--gg-spacing-2xs);
  color: var(--gg-color-primary-brown);
}}
.gg-tp-sample-block {{
  text-align: center;
  padding: var(--gg-spacing-xs) var(--gg-spacing-2xs);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-semibold);
  border: var(--gg-border-subtle);
  min-height: 3.5rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
  line-height: 1.4;
  cursor: pointer;
}}
.gg-tp-sample-block.rest {{
  background: var(--gg-color-white);
  color: var(--gg-color-secondary-brown);
  border-color: var(--gg-color-tan);
}}
.gg-tp-sample-block.endurance {{
  background: var(--gg-color-white);
  color: var(--gg-color-near-black);
}}
.gg-tp-sample-block.intervals {{
  background: var(--gg-color-near-black);
  color: var(--gg-color-sand);
}}
.gg-tp-sample-block.strength {{
  background: var(--gg-color-primary-brown);
  color: var(--gg-color-sand);
}}
.gg-tp-sample-block.long-ride {{
  background: var(--gg-color-near-black);
  color: var(--gg-color-teal);
}}
.gg-tp-sample-block[data-detail] {{
  transition: border-color var(--gg-transition-hover);
}}
.gg-tp-sample-block[data-detail]:hover {{
  border-color: var(--gg-color-primary-brown);
}}
.gg-tp-sample-block[data-detail].active {{
  border-color: var(--gg-color-gold);
  border-width: var(--gg-border-width-standard);
}}
.gg-tp-sample-detail {{
  margin-top: var(--gg-spacing-sm);
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  background: var(--gg-color-white);
  border: var(--gg-border-subtle);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-relaxed);
  color: var(--gg-color-near-black);
}}

/* ── Workout Visualization (zone colors via CSS, not inline hex) ── */
.gg-tp-workout-viz {{
  display: flex;
  align-items: flex-end;
  gap: 1px;
  margin-bottom: var(--gg-spacing-sm);
  min-height: 60px;
}}
.gg-tp-viz-block {{
  display: flex;
  align-items: flex-end;
  justify-content: center;
  border: var(--gg-border-subtle);
  font-family: var(--gg-font-data);
  font-size: 9px;
  font-weight: var(--gg-font-weight-semibold);
  overflow: hidden;
}}
.gg-tp-viz-z1 {{ background: color-mix(in srgb, var(--gg-color-near-black) 8%, var(--gg-color-white)); color: var(--gg-color-near-black); }}
.gg-tp-viz-z2 {{ background: var(--gg-color-sand); border-color: var(--gg-color-primary-brown); color: var(--gg-color-near-black); }}
.gg-tp-viz-z3 {{ background: var(--gg-color-tan); color: var(--gg-color-near-black); }}
.gg-tp-viz-z4 {{ background: var(--gg-color-primary-brown); color: var(--gg-color-sand); }}
.gg-tp-viz-z5 {{ background: var(--gg-color-near-black); color: var(--gg-color-sand); }}
.gg-tp-viz-z6 {{ background: var(--gg-color-near-black); color: var(--gg-color-sand); }}
.gg-tp-viz-label {{
  padding: 2px;
  text-align: center;
  word-break: break-all;
}}
.gg-tp-viz-meta {{
  display: flex;
  gap: var(--gg-spacing-md);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin-top: var(--gg-spacing-xs);
}}

/* ── How It Works — Process Cards ── */
.gg-tp-process {{
  display: flex;
  gap: var(--gg-spacing-md);
  margin-top: var(--gg-spacing-lg);
}}
.gg-tp-process-step {{
  flex: 1;
  padding: var(--gg-spacing-lg) var(--gg-spacing-md);
  text-align: center;
  border: var(--gg-border-standard);
  background: var(--gg-color-white);
  transition: border-color var(--gg-transition-hover);
}}
.gg-tp-process-step:hover {{
  border-color: var(--gg-color-gold);
}}
.gg-tp-process-step:nth-child(even) {{
  background: var(--gg-color-near-black);
  color: var(--gg-color-sand);
}}
.gg-tp-process-step:nth-child(even) h4 {{ color: var(--gg-color-sand); }}
.gg-tp-process-step:nth-child(even) p {{ color: var(--gg-color-warm-brown); }}
.gg-tp-process-step:nth-child(even) .gg-tp-process-num {{ color: var(--gg-color-sand); }}
.gg-tp-process-num {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
  margin-bottom: var(--gg-spacing-xs);
}}
.gg-tp-process-step h4 {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin: 0 0 var(--gg-spacing-2xs) 0;
  color: var(--gg-color-near-black);
}}
.gg-tp-process-step p {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  line-height: 1.4;
  margin: 0;
}}

/* ── How It Works — Detail Steps ── */
.gg-tp-steps {{
  margin-top: var(--gg-spacing-lg);
}}
.gg-tp-step {{
  display: grid;
  grid-template-columns: 40px 1fr;
  gap: var(--gg-spacing-md);
  padding: var(--gg-spacing-md) 0;
  border-bottom: 1px solid var(--gg-color-tan);
  align-items: start;
}}
.gg-tp-step:last-child {{ border-bottom: none; }}
.gg-tp-step-num {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
  text-align: right;
  padding-top: 2px;
}}
.gg-tp-step h3 {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin: 0 0 var(--gg-spacing-2xs) 0;
  color: var(--gg-color-near-black);
}}
.gg-tp-step p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-primary-brown);
  margin: 0;
  line-height: var(--gg-line-height-prose);
}}

/* ── Pullquote / Rotating Reality Check ── */
.gg-tp-pullquote {{
  padding: var(--gg-spacing-xl);
  background: var(--gg-color-near-black);
  min-height: 5rem;
  border-top: var(--gg-border-standard);
  border-top-color: var(--gg-color-primary-brown);
  border-bottom: var(--gg-border-standard);
  border-bottom-color: var(--gg-color-primary-brown);
}}
.gg-tp-pullquote p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-semibold);
  color: var(--gg-color-sand);
  margin: 0;
  line-height: var(--gg-line-height-prose);
  max-width: 750px;
}}
.gg-tp-reality-label {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  color: var(--gg-color-primary-brown);
  margin-bottom: var(--gg-spacing-sm);
  display: block;
}}

/* ── Honest Check (Audience) ── */
.gg-tp-audience-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-lg);
  margin-top: var(--gg-spacing-lg);
}}
.gg-tp-audience-col h3 {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  margin-bottom: var(--gg-spacing-sm);
  color: var(--gg-color-primary-brown);
}}
.gg-tp-not-for h3 {{ color: var(--gg-color-secondary-brown); }}
.gg-tp-audience-list {{
  list-style: none;
  padding: 0;
  margin: 0;
}}
.gg-tp-audience-list li {{
  padding: var(--gg-spacing-xs) 0;
  padding-left: var(--gg-spacing-lg);
  position: relative;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-near-black);
  border-bottom: 1px solid var(--gg-color-tan);
  line-height: var(--gg-line-height-normal);
}}
.gg-tp-audience-list li:last-child {{ border-bottom: none; }}
.gg-tp-audience-list li::before {{
  position: absolute;
  left: 0;
  font-family: var(--gg-font-data);
  font-weight: var(--gg-font-weight-bold);
}}
.gg-tp-for-list li::before {{ content: ">"; color: var(--gg-color-primary-brown); }}
.gg-tp-not-list li::before {{ content: "x"; color: var(--gg-color-secondary-brown); }}

/* ── Testimonials ── */
.gg-tp-testimonials {{
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gg-spacing-md);
  margin-top: var(--gg-spacing-lg);
}}
.gg-tp-testimonial {{
  border: var(--gg-border-standard);
  padding: var(--gg-spacing-lg);
  background: var(--gg-color-white);
}}
.gg-tp-testimonial:nth-child(even) {{ background: var(--gg-color-sand); }}
.gg-tp-testimonial p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  font-style: italic;
  color: var(--gg-color-near-black);
  line-height: var(--gg-line-height-prose);
  margin: 0 0 var(--gg-spacing-sm) 0;
}}
.gg-tp-testimonial cite {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-style: normal;
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  display: block;
}}

/* ── Pricing ── */
.gg-tp-pricing-wrap {{
  max-width: 500px;
  margin-top: var(--gg-spacing-lg);
}}
.gg-tp-pricing-card {{
  border: var(--gg-border-standard);
  overflow: hidden;
}}
.gg-tp-pricing-header {{
  background: var(--gg-color-near-black);
  color: var(--gg-color-sand);
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
}}
.gg-tp-price {{
  font-family: var(--gg-font-data);
  font-size: clamp(32px, 6vw, 42px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-near-black);
  padding: var(--gg-spacing-md) var(--gg-spacing-lg) 0;
}}
.gg-tp-price span {{
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-regular);
  color: var(--gg-color-primary-brown);
}}
.gg-tp-pricing-list {{
  list-style: none;
  padding: 0;
  margin: var(--gg-spacing-sm) 0 0;
}}
.gg-tp-pricing-list li {{
  padding: var(--gg-spacing-xs) var(--gg-spacing-lg);
  padding-left: calc(var(--gg-spacing-lg) + var(--gg-spacing-lg));
  position: relative;
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-near-black);
  border-top: 1px solid var(--gg-color-tan);
  line-height: var(--gg-line-height-normal);
}}
.gg-tp-pricing-list li::before {{
  content: ">";
  position: absolute;
  left: var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-primary-brown);
}}
.gg-tp-pricing-cta {{
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
}}
.gg-tp-pricing-cta .gg-tp-btn {{
  width: 100%;
  text-align: center;
}}
.gg-tp-pricing-note {{
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-primary-brown);
  text-align: center;
  padding: 0 var(--gg-spacing-lg) var(--gg-spacing-md);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  margin: 0;
}}

/* ── Guarantee ── */
.gg-tp-guarantee {{
  margin-top: var(--gg-spacing-lg);
  padding: var(--gg-spacing-lg);
  border: var(--gg-border-standard);
  border-color: var(--gg-color-primary-brown);
  background: var(--gg-color-sand);
  text-align: center;
}}
.gg-tp-guarantee p {{
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-near-black);
  margin: 0;
  line-height: var(--gg-line-height-prose);
}}
.gg-tp-guarantee strong {{
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
}}

/* ── FAQ ── */
.gg-tp-faq-list {{
  margin-top: 0;
}}
.gg-tp-faq-item {{
  border: var(--gg-border-subtle);
  background: var(--gg-color-warm-paper);
  margin-bottom: var(--gg-spacing-xs);
}}
.gg-tp-faq-q {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding: var(--gg-spacing-md) var(--gg-spacing-lg);
  cursor: pointer;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  color: var(--gg-color-near-black);
  background: none;
  border: none;
  text-align: left;
}}
.gg-tp-faq-q:hover {{ color: var(--gg-color-primary-brown); }}
.gg-tp-faq-toggle {{
  font-size: var(--gg-font-size-md);
  font-weight: var(--gg-font-weight-bold);
  line-height: 1;
  color: var(--gg-color-near-black);
  flex-shrink: 0;
  margin-left: var(--gg-spacing-md);
}}
.gg-tp-faq-a {{
  max-height: 0;
  overflow: hidden;
  transition: max-height var(--gg-transition-hover);
  padding: 0 var(--gg-spacing-lg);
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
}}
.gg-tp-faq-item.open .gg-tp-faq-a {{
  max-height: 500px;
  padding-bottom: var(--gg-spacing-md);
}}
.gg-tp-faq-a p {{
  margin: 0;
}}

/* ── Mobile Sticky CTA ── */
.gg-tp-sticky-cta {{
  display: none;
}}
@media (max-width: 768px) {{
  .gg-tp-sticky-cta {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 999;
    background: var(--gg-color-near-black);
    padding: var(--gg-spacing-sm) var(--gg-spacing-md);
    text-align: center;
    border-top: var(--gg-border-standard);
    border-top-color: var(--gg-color-primary-brown);
    visibility: hidden;
    pointer-events: none;
  }}
  .gg-tp-sticky-cta.is-visible {{
    visibility: visible;
    pointer-events: auto;
  }}
  .gg-tp-sticky-cta a {{
    display: block;
    color: var(--gg-color-sand);
    font-family: var(--gg-font-data);
    font-size: var(--gg-font-size-sm);
    font-weight: var(--gg-font-weight-bold);
    text-transform: uppercase;
    letter-spacing: var(--gg-letter-spacing-wider);
    text-decoration: none;
    padding: var(--gg-spacing-2xs) 0;
  }}
}}

/* ── Responsive ── */
@media (max-width: 768px) {{
  .gg-tp-hero {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-tp-hero-title {{ font-size: clamp(22px, 6vw, 28px); }}
  .gg-tp-hero-bar {{ flex-wrap: wrap; }}
  .gg-tp-hero-bar-item {{
    flex: 1 1 48%;
    border-bottom: var(--gg-border-standard);
  }}
  .gg-tp-hero-bar-item:nth-last-child(-n+2) {{ border-bottom: none; }}
  .gg-tp-section {{ padding: var(--gg-spacing-xl) var(--gg-spacing-md); }}
  .gg-tp-section h2 {{ font-size: clamp(20px, 5vw, 28px); }}
  .gg-tp-sample-grid {{ grid-template-columns: repeat(4, 1fr); }}
  .gg-tp-testimonials {{ grid-template-columns: 1fr; }}
  .gg-tp-audience-grid {{ grid-template-columns: 1fr; }}
  .gg-tp-process {{ flex-direction: column; gap: var(--gg-spacing-sm); }}
  .gg-neo-brutalist-page {{ padding-bottom: var(--gg-spacing-2xl); }}
}}
</style>'''


# ── JavaScript ────────────────────────────────────────────────


def build_training_js() -> str:
    # Serialize quotes as JSON for safe embedding
    quotes_json = json.dumps(REALITY_CHECKS)
    return f'''<script>
(function(){{
  /* GA4 analytics helper */
  function track(event, params) {{
    if (typeof gtag === 'function') {{
      gtag('event', event, params || {{}});
    }} else if (window.dataLayer) {{
      var obj = {{ event: event }};
      if (params) {{ for (var k in params) obj[k] = params[k]; }}
      window.dataLayer.push(obj);
    }}
  }}

  track('tp_page_view', {{ page: 'landing' }});

  /* ── Scroll Depth Tracking ── */
  (function() {{
    var depths = {{}};
    var tick = null;
    window.addEventListener('scroll', function() {{
      if (tick) return;
      tick = requestAnimationFrame(function() {{
        tick = null;
        var scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        var docHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
        if (docHeight <= 0) return;
        var pct = Math.round((scrollTop / docHeight) * 100);
        [25, 50, 75, 100].forEach(function(d) {{
          if (pct >= d && !depths[d]) {{
            depths[d] = true;
            track('tp_scroll_depth', {{ depth: d, page: 'landing' }});
          }}
        }});
      }});
    }});
  }})();

  /* ── CTA Click Attribution ── */
  document.querySelectorAll('[data-cta]').forEach(function(el) {{
    el.addEventListener('click', function() {{
      track('tp_cta_click', {{ cta_name: el.getAttribute('data-cta'), text: el.textContent.trim().substring(0, 40) }});
    }});
  }});

  /* ── FAQ Accordion ── */
  document.querySelectorAll('.gg-tp-faq-q').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      var item = btn.parentElement;
      var wasOpen = item.classList.contains('open');
      document.querySelectorAll('.gg-tp-faq-item').forEach(function(el) {{
        el.classList.remove('open');
        el.querySelector('.gg-tp-faq-q').setAttribute('aria-expanded', 'false');
      }});
      if (!wasOpen) {{
        item.classList.add('open');
        btn.setAttribute('aria-expanded', 'true');
        track('tp_faq_open', {{ question: btn.childNodes[0].textContent.trim().substring(0, 60) }});
      }}
    }});
  }});

  /* ── Smooth scroll for #how-it-works ── */
  var howLink = document.querySelector('[data-cta="hero_how"]');
  if (howLink) {{
    howLink.addEventListener('click', function(e) {{
      e.preventDefault();
      var target = document.getElementById('how-it-works');
      if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }});
  }}

  /* ── Rotating Reality Checks ── */
  var realityChecks = {quotes_json};
  var quoteEl = document.getElementById('gg-tp-quote-text');
  if (quoteEl) {{
    /* Fisher-Yates shuffle */
    for (var qi = realityChecks.length - 1; qi > 0; qi--) {{
      var qj = Math.floor(Math.random() * (qi + 1));
      var tmp = realityChecks[qi];
      realityChecks[qi] = realityChecks[qj];
      realityChecks[qj] = tmp;
    }}
    var quoteIndex = 0;
    quoteEl.textContent = realityChecks[0];
    setInterval(function() {{
      quoteEl.style.visibility = 'hidden';
      setTimeout(function() {{
        quoteIndex = (quoteIndex + 1) % realityChecks.length;
        quoteEl.textContent = realityChecks[quoteIndex];
        quoteEl.style.visibility = 'visible';
      }}, 200);
    }}, 8000);
  }}

  /* ── Sample Week Clickable Blocks ── */
  var sampleDetail = document.getElementById('gg-tp-sample-detail');

  function buildWorkoutViz(structureJSON, meta) {{
    var blocks = JSON.parse(structureJSON);
    var vizHTML = '<div class="gg-tp-workout-viz">';
    blocks.forEach(function(b) {{
      var heightPx = Math.round(b.h * 0.95);
      vizHTML += '<div class="gg-tp-viz-block gg-tp-viz-' + b.z + '" style="flex-basis:' + b.w + '%;height:' + heightPx + 'px;">';
      if (b.l) vizHTML += '<span class="gg-tp-viz-label">' + b.l + '</span>';
      vizHTML += '</div>';
    }});
    vizHTML += '</div>';
    if (meta) {{
      var parts = meta.split(' | ');
      vizHTML += '<div class="gg-tp-viz-meta">';
      parts.forEach(function(p) {{ vizHTML += '<span>' + p + '</span>'; }});
      vizHTML += '</div>';
    }}
    return vizHTML;
  }}

  document.querySelectorAll('.gg-tp-sample-block[data-detail]').forEach(function(block) {{
    block.addEventListener('click', function() {{
      var wasActive = this.classList.contains('active');
      document.querySelectorAll('.gg-tp-sample-block').forEach(function(b) {{
        b.classList.remove('active');
      }});
      if (wasActive) {{
        sampleDetail.style.display = 'none';
      }} else {{
        this.classList.add('active');
        var html = '';
        if (this.dataset.structure) {{
          html += buildWorkoutViz(this.dataset.structure, this.dataset.meta || '');
        }}
        html += '<div>' + this.dataset.detail + '</div>';
        sampleDetail.innerHTML = html;
        sampleDetail.style.display = 'block';
        track('tp_sample_week_click', {{
          workout: this.textContent.trim().replace(/\\s+/g, ' ').substring(0, 30)
        }});
      }}
    }});
  }});

  /* ── Mobile Sticky CTA (visibility-based, scroll-triggered) ── */
  var stickyCta = document.getElementById('gg-tp-sticky-cta');
  var heroSection = document.getElementById('hero');
  if (stickyCta && heroSection) {{
    var stickyShown = false;
    window.addEventListener('scroll', function() {{
      var heroBottom = heroSection.getBoundingClientRect().bottom;
      if (heroBottom < 0 && !stickyShown) {{
        stickyCta.classList.add('is-visible');
        stickyCta.style.display = 'block';
        stickyShown = true;
      }} else if (heroBottom >= 0 && stickyShown) {{
        stickyCta.classList.remove('is-visible');
        stickyShown = false;
      }}
    }});
  }}
}})();
</script>'''


# ── JSON-LD ───────────────────────────────────────────────────


def build_jsonld() -> str:
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Custom Gravel Training Plan",
  "description": "Race-specific training plan built from your schedule, fitness, and target event. Includes structured workouts, training guide, nutrition plan, strength program, and heat/altitude protocols.",
  "brand": {{
    "@type": "Organization",
    "name": "Gravel God Cycling",
    "url": "{SITE_BASE_URL}"
  }},
  "offers": {{
    "@type": "AggregateOffer",
    "lowPrice": "60",
    "highPrice": "{PRICE_CAP.replace('$', '')}",
    "priceCurrency": "USD",
    "offerCount": "14",
    "availability": "https://schema.org/InStock"
  }},
  "url": "{TRAINING_PLANS_URL}"
}}
</script>'''


# ── Page assembly ─────────────────────────────────────────────


def generate_training_page(external_assets: dict = None) -> str:
    canonical_url = TRAINING_PLANS_URL

    nav = build_nav()
    hero = build_hero()
    what = build_what_you_get()
    how = build_how_it_works()
    quote = build_rotating_quote()
    honest = build_honest_check()
    testimonials = build_testimonials()
    pricing = build_pricing()
    faq = build_faq()
    sticky = build_mobile_sticky()
    footer = build_footer()
    training_css = build_training_css()
    training_js = build_training_js()
    jsonld = build_jsonld()

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    meta_desc = (
        "Gravel training plans built for your goal race. 16-week periodized "
        "programs with race-specific prep. Data-driven. From $15/week."
    )

    og_tags = f'''<meta property="og:title" content="Custom Training Plans | Gravel God">
  <meta property="og:description" content="Race-specific training plans. $15/week, capped at $249. Structured workouts, nutrition, strength, and race protocols.">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{esc(canonical_url)}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta property="og:site_name" content="Gravel God Cycling">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Custom Training Plans | Gravel God">
  <meta name="twitter:description" content="Race-specific training plans. $15/week, capped at $249.">
  <meta name="twitter:image" content="{SITE_BASE_URL}/og/homepage.jpg">'''

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Gravel Training Plans | Gravel God</title>
  <meta name="description" content="{esc(meta_desc)}">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {og_tags}
  {jsonld}
  {page_css}
  {training_css}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {nav}

  {hero}

  {what}

  {how}

  {quote}

  {honest}

  {testimonials}

  {pricing}

  {faq}

  {footer}
</div>

{sticky}
{inline_js}
{training_js}

{get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God training plans page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    tp_dir = output_dir / "training-plans"
    tp_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)

    html_content = generate_training_page(external_assets=assets)
    output_file = tp_dir / "index.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
