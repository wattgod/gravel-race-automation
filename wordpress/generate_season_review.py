#!/usr/bin/env python3
"""
Generate the Gravel God Season Review at /coaching/season-review/.

A close-out questionnaire sent to existing athletes at the end of a season.
It looks and behaves like the coaching intake (/coaching/apply/) — same
card, progress bar, save/resume, and brand tokens — and reuses that page's
CSS so the two can't drift apart.

Shape: Jordan Peterson's Self Authoring suite, compressed for athletes —
Past (the season as chapters and turning points), Present (one strength,
one fault, the wants that fight the goal), Future (the season you want, the
season to avoid, then a goal with an if-then plan). Trait wording is
verbatim from the Present Authoring lists (Matti's Oct 2025 form).

Evidence that shaped the cuts (research brief, Sep 22 2026):
  - Only Future Authoring has outcome evidence, and independent trials are
    weaker than Peterson-linked ones. It gets the most room here.
  - Free-writing under ~15 minutes shows ~zero effect (Frattaroli 2006), so
    "the season you want" is a 15-minute write with an optional timer.
  - Naming an internal obstacle and an if-then plan (Oettingen's WOOP,
    Gollwitzer) is the best-evidenced piece; the goal and every habit carry it.
  - Two sittings beat one, so answers autosave.
Training numbers (FTP etc.) are deliberately absent — they come from data.

Habits are scored on James Clear's four laws (0-3 each) to match the Endure
goal model (endurelabs docs/specs/endure-loop-2026.md). The athlete sees
the shape of the four scores, never their sum. "Stop" habits invert.

Links can be personalised: ?name=Ada&email=ada@example.com prefills both.

Submission goes to formsubmit.co (already activated for
gravelgodcoaching@gmail.com on this site). The email carries a readable
review plus a JSON block shaped like the Endure seed manifest.

Usage:
    python generate_season_review.py
    python generate_season_review.py --output-dir ./output
"""

import argparse
from pathlib import Path

from generate_neo_brutalist import (
    SITE_BASE_URL,
    get_page_css,
    write_shared_assets,
)
from brand_tokens import get_ga4_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html, get_site_header_js
from cookie_consent import get_consent_banner_html
from generate_coaching_apply import build_apply_css

OUTPUT_DIR = Path(__file__).parent / "output"

SEASON = 2026
NEXT_SEASON = SEASON + 1

FORMSUBMIT_EMAIL = "gravelgodcoaching@gmail.com"
FORMSUBMIT_URL = f"https://formsubmit.co/ajax/{FORMSUBMIT_EMAIL}"

STORAGE_KEY = f"season_review_{SEASON}_progress"

# The four laws, in Endure's column order. Labels are what the athlete reads.
LAWS = [
    ("obvious", "Set time and place"),
    ("attractive", "Something I looked forward to"),
    ("easy", "Easy to start"),
    ("satisfying", "Showed me it was working"),
]
LAW_LEVELS = ["No", "Barely", "Mostly", "Yes"]

# Verbatim from the Self Authoring Present Authoring lists, chosen for
# what shows up in training and racing.
STRENGTHS = [
    "Do what I say I am going to do",
    "Make plans and stick to them",
    "Am very goal-oriented",
    "Have seen my tendency for hard work pay off",
    "Am always learning new things",
    "Spend time reflecting on things",
    "Am not bothered when things don't go according to plan",
    "Know how to go with the flow",
    "Can easily be spontaneous and enjoy the moment",
    "Calm down quickly when I do get upset",
    "Don't get caught up in my problems or blow things out of proportion",
    "Am rarely or never stopped from doing what I want by my fears",
    "Watch what I eat carefully",
    "Am good at identifying the risks in new situations",
    "Am comfortable alone",
    "Enjoy time in natural surroundings",
    "Make other people laugh and have fun",
]
FAULTS = [
    "Am too perfectionistic",
    "Feel that I am being unproductive if I relax",
    "Believe that I have to be flawless",
    "Seriously dislike having my routine or schedule upset",
    "Often procrastinate",
    "Frequently make excuses",
    "Have no stable daily routine for sleeping or eating",
    "Pursue too many activities at the same time",
    "May spend too much time pursuing fun and excitement",
    "Am often too optimistic",
    "Often take counterproductive or unnecessary risks",
    "Don't appear to learn as well from my mistakes as others do",
    "Compare myself unfavorably to other people",
    "Let my fears stop me from doing things I want to do",
    "Get stressed out easily",
    "Blow little things out of proportion",
    "Cannot negotiate for myself very well",
    "Would probably help me if I could be more competitive",
]

SYSTEM_AREAS = [
    ("endurance", "Endurance / late-race durability"),
    ("climbing", "Climbing"),
    ("top_end", "Top end / surges"),
    ("fueling", "Fueling & hydration"),
    ("skills", "Bike handling & skills"),
    ("strength", "Strength & mobility"),
    ("body_comp", "Body composition"),
    ("recovery", "Sleep & recovery"),
    ("consistency", "Consistency"),
    ("mental", "Head game / pacing"),
    ("other", "Something else"),
]


# ── Small builders ────────────────────────────────────────────


def _radio_row(name: str, options, required: bool = False, horizontal: bool = True) -> str:
    cls = "gg-apply-radio-group gg-apply-radio-horizontal" if horizontal else "gg-apply-radio-group"
    parts = []
    for i, opt in enumerate(options):
        value, title = opt[0], opt[1]
        desc = opt[2] if len(opt) > 2 else ""
        req = " required" if required and i == 0 else ""
        desc_html = f'<div class="gg-apply-radio-desc">{desc}</div>' if desc else ""
        parts.append(
            f'<label class="gg-apply-radio-option">'
            f'<input type="radio" name="{name}" value="{value}"{req}>'
            f'<div class="gg-apply-radio-label"><div class="gg-apply-radio-title">{title}</div>{desc_html}</div>'
            f"</label>"
        )
    return f'<div class="{cls}">' + "".join(parts) + "</div>"


def _select(name: str, options, required: bool = False) -> str:
    req = " required" if required else ""
    opts = '<option value="">Select...</option>' + "".join(
        f'<option value="{v}">{t}</option>' for v, t in options
    )
    return f'<select id="{name}" name="{name}"{req}>{opts}</select>'


def _trait_options(traits) -> str:
    esc = lambda s: s.replace("'", "&#39;")
    return '<option value="">Select...</option>' + "".join(
        f'<option value="{esc(t)}">{esc(t)}</option>' for t in traits
    ) + '<option value="other">Something else (say it below)</option>'


def _timed(minutes: int) -> str:
    return (
        f'<button type="button" class="gg-sr-timer" data-minutes="{minutes}">'
        f"Start {minutes}:00</button>"
    )


# ── Page sections ─────────────────────────────────────────────


def build_nav() -> str:
    return get_site_header_html(active="services") + f'''
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <a href="{SITE_BASE_URL}/coaching/">Coaching</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">Season Review</span>
  </div>'''


def build_header() -> str:
    return f'''<div class="gg-apply-header">
    <div class="gg-apply-badge">Season Review</div>
    <h1>Close the Books on {SEASON}</h1>
    <p>Two sittings. The season now, about 15 minutes. {NEXT_SEASON} a few days later, about 25. Everything saves as you type. Write like nobody&#39;s grading it.</p>
  </div>'''


def build_progress_bar() -> str:
    return '''<div class="gg-apply-progress">
    <div class="gg-apply-progress-bar">
      <div class="gg-apply-progress-fill" id="progress-fill"></div>
    </div>
    <div class="gg-apply-progress-text" id="progress-text">0% complete</div>
  </div>'''


def _part(label: str) -> str:
    return f'<div class="gg-sr-part">{label}</div>'


def build_section_you() -> str:
    return '''<div class="gg-apply-section-title">1. You</div>

      <div class="gg-apply-inline">
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="name">Name <span class="gg-apply-required">*</span></label>
          <input type="text" id="name" name="name" required autocomplete="name" placeholder="First Last">
        </div>
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="email">Email <span class="gg-apply-required">*</span></label>
          <input type="email" id="email" name="email" required autocomplete="email" placeholder="you@email.com">
        </div>
      </div>'''


def build_section_start() -> str:
    return '''<div class="gg-apply-section-title">2. Start Here</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="proudest">What are you most proud of this season? <span class="gg-apply-required">*</span></label>
        <textarea id="proudest" name="proudest" required rows="3" placeholder="Not the result you&#39;d post. The thing you&#39;d tell a friend at 1 a.m."></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="one_word">The season in one word</label>
        <input type="text" id="one_word" name="one_word" placeholder="e.g., Stubborn">
      </div>'''


def build_section_chapters() -> str:
    return f'''<div class="gg-apply-section-title">3. The Chapters</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="chapters">Split {SEASON} into two to four chapters. Name each, one line on what it was.</label>
        <textarea id="chapters" name="chapters" rows="4" placeholder="Winter: the first base I didn&#39;t skip&#10;Spring: sick twice, lost April&#10;Summer: the Unbound block&#10;Fall: cooked, and fine with it"></textarea>
      </div>'''


def build_section_moments() -> str:
    return '''<div class="gg-apply-section-title">4. The Moments That Mattered</div>
      <p class="gg-apply-section-sub">Up to three. Good or bad. The ones you still think about.</p>

      <div id="moments-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="moment">+ Add a moment</button>'''


def build_section_goals() -> str:
    return f'''<div class="gg-apply-section-title">5. The Goals You Set</div>
      <p class="gg-apply-section-sub">The ones you wrote down before the season, not the ones you wish you&#39;d written.</p>

      <div id="goals-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="goal">+ Add a goal</button>'''


def build_section_traits() -> str:
    return '''<div class="gg-apply-section-title">6. What Carried You, What Cost You</div>

      <div id="strengths-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="strength">+ Add a strength</button>

      <div id="faults-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="fault">+ Add a fault</button>'''


def build_section_wants() -> str:
    return '''<div class="gg-apply-section-title">7. Wants That Fight Your Goals</div>
      <p class="gg-apply-section-sub">Some of what you want gets in the way of what you want.</p>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="competing_wants">What do you enjoy that costs you training?</label>
        <textarea id="competing_wants" name="competing_wants" rows="3" placeholder="The post-ride party. Two days wrecked, twenty times a year."></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="want_to_want">What would you have to start wanting instead?</label>
        <input type="text" id="want_to_want" name="want_to_want" placeholder="e.g., Being proud of a 9 p.m. bedtime">
      </div>'''


def build_section_habits() -> str:
    return '''<div class="gg-apply-section-title">8. The Habits That Held</div>
      <p class="gg-apply-section-sub">A habit that died usually had one of these four missing. Score each one honestly.</p>

      <div id="habits-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="habit">+ Add a habit</button>'''


def build_section_life() -> str:
    return f'''<div class="gg-apply-section-title">9. Life Around the Bike</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label">Did training fit your life this season, or fight it?</label>
        {_radio_row("life_fit", [
            ("fit", "It fit"),
            ("mostly", "Mostly fit"),
            ("fought", "It fought"),
        ])}
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="life_friction">Where did it fight, and who paid for it?</label>
        <textarea id="life_friction" name="life_friction" rows="2" placeholder="Work, family, sleep, money, your body"></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="injuries_now">Anything hurting going into the off-season?</label>
        <input type="text" id="injuries_now" name="injuries_now" placeholder="Where, how long, what makes it worse">
      </div>'''


def build_section_ideal() -> str:
    return f'''<div class="gg-apply-section-title">10. The Season You Want</div>
      <p class="gg-apply-section-sub">Fifteen minutes without stopping. Don&#39;t edit.</p>

      <div class="gg-apply-group">
        <div class="gg-sr-label-row">
          <label class="gg-apply-label" for="ideal_season">It&#39;s December {NEXT_SEASON} and it went as well as it could. Who were you, what did you do, what did it feel like? <span class="gg-apply-required">*</span></label>
          {_timed(15)}
        </div>
        <textarea id="ideal_season" name="ideal_season" required rows="12" class="gg-sr-long"></textarea>
      </div>'''


def build_section_avoid() -> str:
    return f'''<div class="gg-apply-section-title">11. The Season to Avoid</div>

      <div class="gg-apply-group">
        <div class="gg-sr-label-row">
          <label class="gg-apply-label" for="avoid_season">It&#39;s December {NEXT_SEASON} and it went badly. What happened, and what was your part in it? <span class="gg-apply-required">*</span></label>
          {_timed(5)}
        </div>
        <textarea id="avoid_season" name="avoid_season" required rows="7" class="gg-sr-long"></textarea>
      </div>'''


def build_section_goal() -> str:
    return f'''<div class="gg-apply-section-title">12. The Goal</div>
      <p class="gg-apply-section-sub">Measurable, dated, and a little frightening. If it isn&#39;t, it&#39;s a wish.</p>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="outcome_goal">By the end of {NEXT_SEASON}, I will&hellip; <span class="gg-apply-required">*</span></label>
        <textarea id="outcome_goal" name="outcome_goal" required rows="2" placeholder="e.g., Finish Unbound 200 under 14 hours"></textarea>
      </div>

      <div class="gg-apply-inline">
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="outcome_measure">How we&#39;ll know <span class="gg-apply-required">*</span></label>
          <input type="text" id="outcome_measure" name="outcome_measure" required placeholder="e.g., Official finish time">
        </div>
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="outcome_date">By when</label>
          <input type="date" id="outcome_date" name="outcome_date">
        </div>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label">Say it out loud. Does it scare you?</label>
        {_radio_row("outcome_scary", [
            ("yes", "Yes"),
            ("a_bit", "A bit"),
            ("no", "No"),
        ])}
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="why_1">Why do you want it?</label>
        <input type="text" id="why_1" name="why_1">
      </div>
      <div class="gg-apply-group gg-sr-why">
        <label class="gg-apply-label" for="why_2">And why does that matter?</label>
        <input type="text" id="why_2" name="why_2">
      </div>
      <div class="gg-apply-group gg-sr-why">
        <label class="gg-apply-label" for="why_3">And why does that matter?</label>
        <input type="text" id="why_3" name="why_3">
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="inner_obstacle">What in you is most likely to stop you? <span class="gg-apply-required">*</span></label>
        <input type="text" id="inner_obstacle" name="inner_obstacle" required placeholder="Not the weather. You. e.g., I quit on long rides when I&#39;m alone">
      </div>
      <div class="gg-apply-group">
        <label class="gg-apply-label" for="obstacle_plan">When that shows up, I will&hellip; <span class="gg-apply-required">*</span></label>
        <input type="text" id="obstacle_plan" name="obstacle_plan" required placeholder="e.g., Text my riding buddy before I turn around">
      </div>'''


def build_section_systems() -> str:
    return '''<div class="gg-apply-section-title">13. What Has to Get Better</div>
      <p class="gg-apply-section-sub">Two or three things that decide the goal. Each gets a number and a date.</p>

      <div id="systems-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="system">+ Add one</button>'''


def build_section_new_habits() -> str:
    return '''<div class="gg-apply-section-title">14. Habits to Start and Stop</div>
      <p class="gg-apply-section-sub">Built so they survive a bad week.</p>

      <div id="newhabits-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="newhabit">+ Add a habit</button>'''


def build_section_calendar() -> str:
    hours = [
        ("3-5", "3&ndash;5 hrs"), ("5-7", "5&ndash;7 hrs"), ("7-10", "7&ndash;10 hrs"),
        ("10-12", "10&ndash;12 hrs"), ("12-15", "12&ndash;15 hrs"), ("15+", "15+ hrs"),
    ]
    return f'''<div class="gg-apply-section-title">15. The Calendar</div>

      <div id="races-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="race">+ Add a race</button>

      <div class="gg-apply-inline">
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="hours_next">Weekly hours you can really give {NEXT_SEASON} <span class="gg-apply-required">*</span></label>
          {_select("hours_next", hours, required=True)}
        </div>
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="break_dates">Off-season break</label>
          <input type="text" id="break_dates" name="break_dates" placeholder="e.g., Oct 12 &ndash; Oct 26">
        </div>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="life_changes">What changes in {NEXT_SEASON}?</label>
        <textarea id="life_changes" name="life_changes" rows="2" placeholder="New job, new baby, a move, known travel, a surgery date"></textarea>
      </div>'''


def build_section_me() -> str:
    return f'''<div class="gg-apply-section-title">16. Me</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="coach_keep">What should I keep doing?</label>
        <textarea id="coach_keep" name="coach_keep" rows="2"></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="coach_change">What should I change?</label>
        <textarea id="coach_change" name="coach_change" rows="2"></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label">For {NEXT_SEASON}, you want <span class="gg-apply-required">*</span></label>
        {_radio_row("next_season_plan", [
            ("coaching", "Coaching", "Weekly review, the plan moves with you"),
            ("custom_plan", "A custom plan", "Built once for your A race"),
            ("undecided", "Not sure yet", "Let&#39;s talk it through"),
        ], required=True, horizontal=False)}
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="anything_else">What haven&#39;t I asked?</label>
        <textarea id="anything_else" name="anything_else" rows="3"></textarea>
      </div>'''


def build_submit_buttons() -> str:
    return '''<div class="gg-apply-actions">
        <button type="button" class="gg-apply-save-btn" id="save-btn">Save Progress</button>
        <button type="submit" class="gg-apply-submit-btn" id="submit-btn">Submit Season Review</button>
      </div>'''


def build_footer() -> str:
    return f'''<div class="gg-apply-confidential-wrap">
    <p class="gg-apply-confidential">Your answers go to your coach only. Questions? Email {FORMSUBMIT_EMAIL}</p>
  </div>
  ''' + get_mega_footer_html()


# ── Row templates (cloned by JS) ──────────────────────────────


def _law_picker() -> str:
    """Four-law scoring block for last season's habits."""
    rows = []
    for key, label in LAWS:
        buttons = "".join(
            f'<button type="button" class="gg-sr-level" data-law="{key}" data-level="{i}">{lvl}</button>'
            for i, lvl in enumerate(LAW_LEVELS)
        )
        rows.append(
            f'<div class="gg-sr-law-row" data-law-row="{key}">'
            f'<span class="gg-sr-law-name">{label}</span>'
            f'<div class="gg-sr-levels" role="group" aria-label="{label}">{buttons}</div>'
            f"</div>"
        )
    spine = "".join(f'<span class="gg-sr-seg" data-seg="{k}"></span>' for k, _ in LAWS)
    return (
        '<div class="gg-sr-laws">'
        + "".join(rows)
        + f'<div class="gg-sr-spine" aria-hidden="true">{spine}</div>'
        + '<div class="gg-sr-missing" hidden></div>'
        + "</div>"
    )


def _head() -> str:
    return '<div class="gg-sr-entry-head"><span class="gg-sr-entry-num"></span><button type="button" class="gg-sr-remove">Remove</button></div>'


def _radio_field(field: str, options) -> str:
    return (
        '<div class="gg-apply-radio-group gg-apply-radio-horizontal">'
        + "".join(
            f'<label class="gg-apply-radio-option"><input type="radio" data-field="{field}" value="{v}">'
            f'<div class="gg-apply-radio-label"><div class="gg-apply-radio-title">{t}</div></div></label>'
            for v, t in options
        )
        + "</div>"
    )


def build_templates() -> str:
    areas = "".join(f'<option value="{v}">{t}</option>' for v, t in SYSTEM_AREAS)
    return f'''<template id="tpl-moment">
  <div class="gg-sr-entry" data-kind="moment">
    {_head()}
    <div class="gg-apply-group">
      <label class="gg-apply-label">Call it something</label>
      <input type="text" data-field="title" placeholder="e.g., The second climb at Worlds">
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">What happened</label>
      <textarea data-field="what" rows="3"></textarea>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">What part was yours, and what wasn&#39;t?</label>
      <textarea data-field="role" rows="2" placeholder="What you controlled, what you&#39;d do differently, what was luck"></textarea>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">What did it change about how you see yourself?</label>
      <textarea data-field="impact" rows="2"></textarea>
    </div>
  </div>
</template>

<template id="tpl-goal">
  <div class="gg-sr-entry" data-kind="goal">
    {_head()}
    <div class="gg-apply-group">
      <label class="gg-apply-label">Goal</label>
      <input type="text" data-field="goal" placeholder="e.g., Break 10 hours at Mid South">
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">Result</label>
      {_radio_field("result", [("hit", "Hit it"), ("close", "Close"), ("missed", "Missed"), ("dropped", "Dropped it")])}
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">What decided it</label>
      <input type="text" data-field="why" placeholder="e.g., Flatted at mile 40; fitness was there">
    </div>
  </div>
</template>

<template id="tpl-strength">
  <div class="gg-sr-entry" data-kind="strength">
    {_head()}
    <div class="gg-apply-group">
      <label class="gg-apply-label">A strength that carried you</label>
      <select data-field="trait">{_trait_options(STRENGTHS)}</select>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">When did it show up this season?</label>
      <textarea data-field="story" rows="2"></textarea>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">How do you use it more next year?</label>
      <input type="text" data-field="use">
    </div>
  </div>
</template>

<template id="tpl-fault">
  <div class="gg-sr-entry" data-kind="fault">
    {_head()}
    <div class="gg-apply-group">
      <label class="gg-apply-label">A fault that cost you</label>
      <select data-field="trait">{_trait_options(FAULTS)}</select>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">When did it cost you this season?</label>
      <textarea data-field="story" rows="2"></textarea>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">What will you do so it doesn&#39;t repeat?</label>
      <input type="text" data-field="fix">
    </div>
  </div>
</template>

<template id="tpl-habit">
  <div class="gg-sr-entry" data-kind="habit">
    {_head()}
    <div class="gg-apply-inline">
      <div class="gg-apply-group">
        <label class="gg-apply-label">Habit</label>
        <input type="text" data-field="habit" placeholder="e.g., Mobility after every ride">
      </div>
      <div class="gg-apply-group">
        <label class="gg-apply-label">Did it stick?</label>
        <select data-field="stuck">
          <option value="">Select...</option>
          <option value="most_weeks">Most weeks</option>
          <option value="on_off">On and off</option>
          <option value="died">Died by midseason</option>
          <option value="never">Never started</option>
        </select>
      </div>
    </div>
    {_law_picker()}
  </div>
</template>

<template id="tpl-system">
  <div class="gg-sr-entry" data-kind="system">
    {_head()}
    <div class="gg-apply-inline">
      <div class="gg-apply-group">
        <label class="gg-apply-label">Area</label>
        <select data-field="area"><option value="">Select...</option>{areas}</select>
      </div>
      <div class="gg-apply-group">
        <label class="gg-apply-label">In your words</label>
        <input type="text" data-field="detail" placeholder="e.g., Stop fading after hour 6">
      </div>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">What would show it&#39;s working?</label>
      <input type="text" data-field="metric" placeholder="e.g., Still riding with the group in hour 6">
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">If it hasn&#39;t moved by&hellip;</label>
      <div class="gg-sr-kill">
        <input type="date" data-field="check_by">
        <span class="gg-apply-unit">we change the approach</span>
      </div>
    </div>
  </div>
</template>

<template id="tpl-newhabit">
  <div class="gg-sr-entry" data-kind="newhabit" data-direction="do">
    {_head()}
    <div class="gg-apply-group">
      <div class="gg-apply-radio-group gg-apply-radio-horizontal gg-sr-direction">
        <label class="gg-apply-radio-option selected"><input type="radio" data-field="direction" value="do" checked><div class="gg-apply-radio-label"><div class="gg-apply-radio-title">Start</div></div></label>
        <label class="gg-apply-radio-option"><input type="radio" data-field="direction" value="reduce"><div class="gg-apply-radio-label"><div class="gg-apply-radio-title">Stop</div></div></label>
      </div>
    </div>
    <div class="gg-apply-inline">
      <div class="gg-apply-group">
        <label class="gg-apply-label">Habit</label>
        <input type="text" data-field="habit" data-ph-do="e.g., 20 min of hip mobility" data-ph-reduce="e.g., Phone in the bedroom" placeholder="e.g., 20 min of hip mobility">
      </div>
      <div class="gg-apply-group">
        <label class="gg-apply-label">Serves</label>
        <select data-field="serves" class="gg-sr-serves"><option value="">Select...</option></select>
      </div>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label" data-lbl-do="When and where" data-lbl-reduce="Make it invisible">When and where</label>
      <input type="text" data-field="obvious" data-ph-do="After I close the laptop, on the mat by the trainer" data-ph-reduce="Charger lives in the kitchen" placeholder="After I close the laptop, on the mat by the trainer">
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label" data-lbl-do="What makes it worth looking forward to" data-lbl-reduce="Make it unappealing">What makes it worth looking forward to</label>
      <input type="text" data-field="attractive" data-ph-do="Only podcast I let myself listen to" data-ph-reduce="Tell my partner; they get to call me on it" placeholder="Only podcast I let myself listen to">
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label" data-lbl-do="The smallest version that still counts" data-lbl-reduce="Make it harder to do">The smallest version that still counts</label>
      <input type="text" data-field="easy" data-ph-do="5 minutes, one stretch" data-ph-reduce="Log out of the app every night" placeholder="5 minutes, one stretch">
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label" data-lbl-do="How you&#39;ll see it working, same day" data-lbl-reduce="What you&#39;ll see instead">How you&#39;ll see it working, same day</label>
      <input type="text" data-field="satisfying" data-ph-do="Tick on the fridge calendar" data-ph-reduce="Morning HRV" placeholder="Tick on the fridge calendar">
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">If ___ gets in the way, I will ___</label>
      <input type="text" data-field="if_then" data-ph-do="If I get home after 7, I do the 5-minute version before dinner" data-ph-reduce="If I want the phone at night, I read the book on the nightstand" placeholder="If I get home after 7, I do the 5-minute version before dinner">
    </div>
  </div>
</template>

<template id="tpl-race">
  <div class="gg-sr-entry" data-kind="race">
    {_head()}
    <div class="gg-sr-race-fields">
      <div class="gg-apply-group">
        <label class="gg-apply-label">Race</label>
        <input type="text" data-field="race" placeholder="e.g., Unbound 200">
      </div>
      <div class="gg-apply-group">
        <label class="gg-apply-label">Date</label>
        <input type="date" data-field="date">
      </div>
      <div class="gg-apply-group">
        <label class="gg-apply-label">Priority</label>
        <select data-field="priority">
          <option value="">Select...</option>
          <option value="A">A &mdash; the goal</option>
          <option value="B">B &mdash; matters</option>
          <option value="C">C &mdash; training</option>
        </select>
      </div>
    </div>
  </div>
</template>'''


# ── CSS (additions on top of the intake form's CSS) ───────────


def build_season_review_css() -> str:
    return '''<style>
.gg-sr-scale .gg-apply-radio-option { min-width: 44px; flex: 1 1 0; justify-content: center; padding: var(--gg-spacing-xs); }
.gg-sr-scale .gg-apply-radio-option input { position: absolute; opacity: 0; width: 0; height: 0; }
.gg-sr-scale .gg-apply-radio-title { text-align: center; }

.gg-sr-list { display: flex; flex-direction: column; gap: var(--gg-spacing-md); }
.gg-sr-list:not(:empty) { margin-bottom: var(--gg-spacing-md); }
.gg-sr-entry {
  border: 2px solid var(--gg-color-near-black);
  background: var(--gg-color-warm-paper);
  padding: var(--gg-spacing-md);
}
.gg-sr-entry .gg-apply-group:last-child { margin-bottom: 0; }
.gg-sr-entry-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--gg-spacing-sm);
}
.gg-sr-entry-num {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
}
.gg-sr-remove {
  background: none;
  border: 2px solid var(--gg-color-near-black);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-semibold);
  padding: 2px var(--gg-spacing-xs);
  cursor: pointer;
}
.gg-sr-remove:hover { background: var(--gg-color-near-black); color: var(--gg-color-white); }
.gg-sr-add-btn {
  width: 100%;
  background: var(--gg-color-white);
  border: 2px dashed var(--gg-color-near-black);
  padding: var(--gg-spacing-sm) var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-semibold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
  cursor: pointer;
  margin-bottom: var(--gg-spacing-lg);
  transition: background-color var(--gg-transition-hover);
}
.gg-sr-add-btn:hover { background: var(--gg-color-sand); border-style: solid; }
.gg-sr-add-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.gg-sr-race-fields {
  display: grid;
  grid-template-columns: 2fr 1.3fr 1fr;
  gap: var(--gg-spacing-sm);
}
.gg-sr-race-fields .gg-apply-group { margin-bottom: 0; }

.gg-apply-form-card .gg-apply-unit-wrap input { min-width: 0; }

.gg-sr-kill { display: flex; flex-wrap: wrap; align-items: center; gap: var(--gg-spacing-sm); }
.gg-sr-kill .gg-apply-unit { white-space: normal; }
.gg-sr-kill input { max-width: 200px; }

/* Four-law scoring */
.gg-sr-laws {
  border-top: 2px solid var(--gg-color-near-black);
  padding-top: var(--gg-spacing-sm);
  margin-top: var(--gg-spacing-xs);
}
.gg-sr-law-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--gg-spacing-sm);
  padding: var(--gg-spacing-2xs) 0;
}
.gg-sr-law-name {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-semibold);
}
.gg-sr-levels { display: flex; flex-shrink: 0; }
.gg-sr-level {
  background: var(--gg-color-white);
  border: 2px solid var(--gg-color-near-black);
  margin-left: -2px;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  padding: 4px 10px;
  min-width: 62px;
  cursor: pointer;
}
.gg-sr-level:hover { background: var(--gg-color-sand); }
.gg-sr-level.on { background: var(--gg-color-teal); color: var(--gg-color-white); }
.gg-sr-level.on[data-level="0"] { background: var(--gg-color-error); }

.gg-sr-spine {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 3px;
  margin-top: var(--gg-spacing-sm);
}
.gg-sr-seg {
  height: 8px;
  border: 1px dashed var(--gg-color-secondary-brown);
  background: transparent;
}
.gg-sr-seg[data-v] { border-style: solid; border-color: var(--gg-color-near-black); }
.gg-sr-seg[data-v="0"] { background: var(--gg-color-error); }
.gg-sr-seg[data-v="1"] { background: linear-gradient(90deg, var(--gg-color-teal) 33%, var(--gg-color-sand) 33%); }
.gg-sr-seg[data-v="2"] { background: linear-gradient(90deg, var(--gg-color-teal) 66%, var(--gg-color-sand) 66%); }
.gg-sr-seg[data-v="3"] { background: var(--gg-color-teal); }
.gg-sr-missing {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-error);
  margin-top: var(--gg-spacing-2xs);
}

.gg-sr-direction { margin-bottom: 0; }
.gg-sr-entry[data-direction="reduce"] { border-left: 6px solid var(--gg-color-error); }

/* Part dividers */
.gg-sr-part {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  background: var(--gg-color-near-black);
  color: var(--gg-color-white);
  padding: var(--gg-spacing-xs) var(--gg-spacing-md);
  margin: var(--gg-spacing-2xl) 0 var(--gg-spacing-lg);
}
.gg-sr-part:first-of-type { margin-top: 0; }

/* Timed writing */
.gg-sr-label-row {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--gg-spacing-sm);
}
.gg-sr-label-row .gg-apply-label { flex: 1; }
.gg-sr-timer {
  flex-shrink: 0;
  margin-bottom: var(--gg-spacing-xs);
  background: var(--gg-color-white);
  border: 2px solid var(--gg-color-near-black);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  font-variant-numeric: tabular-nums;
  padding: 4px var(--gg-spacing-sm);
  min-width: 96px;
  cursor: pointer;
}
.gg-sr-timer:hover { background: var(--gg-color-sand); }
.gg-sr-timer.running { background: var(--gg-color-teal); color: var(--gg-color-white); }
.gg-sr-timer.done { background: var(--gg-color-near-black); color: var(--gg-color-white); }
.gg-apply-form-card textarea.gg-sr-long {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  line-height: var(--gg-line-height-relaxed);
}
.gg-sr-why { padding-left: var(--gg-spacing-lg); border-left: 2px solid var(--gg-color-tan); }

@media (max-width: 600px) {
  .gg-sr-label-row { flex-direction: column; align-items: stretch; }
  .gg-sr-timer { align-self: flex-start; }
  .gg-sr-race-fields { grid-template-columns: 1fr; }
  .gg-sr-law-row { flex-direction: column; align-items: stretch; }
  .gg-sr-levels { width: 100%; }
  .gg-sr-level { flex: 1; min-width: 0; }
  .gg-sr-scale .gg-apply-radio-horizontal { flex-direction: row; flex-wrap: wrap; }
  .gg-sr-scale .gg-apply-radio-option { flex: 1 0 17%; min-width: 0; }
}
</style>'''




# ── JavaScript ────────────────────────────────────────────────


def build_season_review_js() -> str:
    js = r'''<script>
(function() {
  "use strict";

  var STORAGE_KEY = "__STORAGE_KEY__";
  var SUBMIT_URL = "__SUBMIT_URL__";
  var SEASON = __SEASON__;
  var LAWS = ["obvious", "attractive", "easy", "satisfying"];
  var LAW_LABELS = { obvious: "set time and place", attractive: "something to look forward to", easy: "easy to start", satisfying: "a same-day payoff" };
  var KINDS = {
    moment:   { list: "moments",    limit: 3, title: "Moment" },
    goal:     { list: "goals",      limit: 5, title: "Goal" },
    strength: { list: "strengths",  limit: 2, title: "Strength" },
    fault:    { list: "faults",     limit: 2, title: "Fault" },
    habit:    { list: "habits",     limit: 5, title: "Habit" },
    system:   { list: "systems",    limit: 3, title: "Area" },
    newhabit: { list: "new_habits", limit: 6, title: "Habit" },
    race:     { list: "races",      limit: 8, title: "Race" }
  };
  /* systems first so habits can point at them */
  var ORDER = ["system", "moment", "goal", "strength", "fault", "habit", "newhabit", "race"];

  var form = document.getElementById("season-form");

  function ga4(name, params) {
    if (typeof gtag === "function") { gtag("event", name, params || {}); }
  }

  /* ── Repeating entries ───────────────────────────── */
  var rowSeq = 0;
  function container(kind) { return document.getElementById(kind + "s-container"); }

  function addEntry(kind) {
    var list = container(kind);
    if (list.children.length >= KINDS[kind].limit) { return null; }
    var node = document.getElementById("tpl-" + kind).content.firstElementChild.cloneNode(true);
    rowSeq++;
    /* radios inside a row need a row-unique name so rows don't share a group */
    node.querySelectorAll("input[type=radio]").forEach(function(r) {
      r.name = "row_" + rowSeq + "_" + r.getAttribute("data-field");
    });
    list.appendChild(node);
    renumber(kind);
    if (kind === "system" || kind === "newhabit") { refreshServes(); }
    return node;
  }

  function renumber(kind) {
    var list = container(kind);
    Array.prototype.forEach.call(list.children, function(el, i) {
      el.querySelector(".gg-sr-entry-num").textContent = KINDS[kind].title + " " + (i + 1);
      el.querySelector(".gg-sr-remove").hidden = list.children.length === 1;
    });
    var btn = document.querySelector("[data-add=\"" + kind + "\"]");
    if (btn) { btn.disabled = list.children.length >= KINDS[kind].limit; }
  }

  function areaLabel(sys) {
    var sel = sys.querySelector("[data-field=area]");
    var detail = sys.querySelector("[data-field=detail]").value.trim();
    return detail || (sel.value ? sel.options[sel.selectedIndex].text : "");
  }

  function refreshServes() {
    var systems = Array.prototype.slice.call(container("system").children);
    document.querySelectorAll(".gg-sr-serves").forEach(function(sel) {
      var current = sel.value;
      while (sel.firstChild) { sel.removeChild(sel.firstChild); }
      sel.appendChild(new Option("Select...", ""));
      systems.forEach(function(sys, i) {
        var label = areaLabel(sys);
        if (label) { sel.appendChild(new Option(label, "S" + (i + 1))); }
      });
      sel.appendChild(new Option("The goal directly", "goal"));
      sel.value = current;
    });
  }

  /* ── Four-law picker ─────────────────────────────── */
  function setLaw(laws, law, level) {
    laws.querySelectorAll(".gg-sr-level[data-law=" + law + "]").forEach(function(b) {
      b.classList.toggle("on", String(level) === b.getAttribute("data-level"));
    });
    laws.setAttribute("data-" + law, level);
    var seg = laws.querySelector("[data-seg=" + law + "]");
    if (level === "" || level === null) { seg.removeAttribute("data-v"); } else { seg.setAttribute("data-v", level); }
    var missing = LAWS.filter(function(l) { return laws.getAttribute("data-" + l) === "0"; });
    var note = laws.querySelector(".gg-sr-missing");
    if (missing.length) {
      note.textContent = "Missing: " + missing.map(function(l) { return LAW_LABELS[l]; }).join(", ");
      note.hidden = false;
    } else {
      note.hidden = true;
    }
  }

  /* ── Start / stop direction swaps the prompts ────── */
  function setDirection(entry, dir) {
    entry.setAttribute("data-direction", dir);
    entry.querySelectorAll("[data-ph-" + dir + "]").forEach(function(el) {
      el.placeholder = el.getAttribute("data-ph-" + dir);
    });
    entry.querySelectorAll("[data-lbl-" + dir + "]").forEach(function(el) {
      el.textContent = el.getAttribute("data-lbl-" + dir);
    });
  }

  /* ── Writing timers ──────────────────────────────── */
  var timers = {};
  function toggleTimer(btn) {
    var key = btn.getAttribute("data-minutes") + (btn.closest(".gg-apply-group").querySelector("textarea").id);
    var total = Number(btn.getAttribute("data-minutes")) * 60;
    if (timers[key]) {
      clearInterval(timers[key]);
      delete timers[key];
      btn.classList.remove("running", "done");
      btn.textContent = "Start " + btn.getAttribute("data-minutes") + ":00";
      return;
    }
    var left = total;
    btn.classList.add("running");
    btn.closest(".gg-apply-group").querySelector("textarea").focus();
    function paint() {
      var m = Math.floor(left / 60), s = left % 60;
      btn.textContent = m + ":" + (s < 10 ? "0" : "") + s;
    }
    paint();
    timers[key] = setInterval(function() {
      left--;
      if (left <= 0) {
        clearInterval(timers[key]);
        delete timers[key];
        btn.classList.remove("running");
        btn.classList.add("done");
        btn.textContent = "Time";
        return;
      }
      paint();
    }, 1000);
  }

  /* ── Delegated events ────────────────────────────── */
  form.addEventListener("click", function(e) {
    var t = e.target;
    var add = t.closest("[data-add]");
    if (add) { addEntry(add.getAttribute("data-add")); updateProgress(); return; }

    var timer = t.closest(".gg-sr-timer");
    if (timer) { toggleTimer(timer); return; }

    var rm = t.closest(".gg-sr-remove");
    if (rm) {
      var entry = rm.closest(".gg-sr-entry");
      var kind = entry.getAttribute("data-kind");
      entry.remove();
      renumber(kind);
      if (kind === "system") { refreshServes(); }
      queueSave();
      updateProgress();
      return;
    }

    var lvl = t.closest(".gg-sr-level");
    if (lvl) {
      var laws = lvl.closest(".gg-sr-laws");
      var law = lvl.getAttribute("data-law");
      var level = lvl.getAttribute("data-level");
      setLaw(laws, law, laws.getAttribute("data-" + law) === level ? "" : level);
      queueSave();
      return;
    }

    var opt = t.closest(".gg-apply-radio-option");
    if (opt) {
      var input = opt.querySelector("input");
      form.querySelectorAll("input[name=\"" + input.name + "\"]").forEach(function(inp) {
        inp.closest(".gg-apply-radio-option").classList.remove("selected");
      });
      input.checked = true;
      opt.classList.add("selected");
      if (input.getAttribute("data-field") === "direction") {
        setDirection(opt.closest(".gg-sr-entry"), input.value);
      }
      queueSave();
      updateProgress();
    }
  });

  function onEdit(e) {
    if (e.target.closest("[data-kind=system]")) { refreshServes(); }
    queueSave();
    updateProgress();
  }
  form.addEventListener("input", onEdit);
  form.addEventListener("change", onEdit);

  /* ── Progress ────────────────────────────────────── */
  function updateProgress() {
    var names = {};
    form.querySelectorAll("[required]").forEach(function(el) { names[el.name] = true; });
    var keys = Object.keys(names);
    var filled = keys.filter(function(n) {
      var el = form.querySelector("[name=\"" + n + "\"]");
      if (el.type === "radio") { return !!form.querySelector("input[name=\"" + n + "\"]:checked"); }
      return !!el.value.trim();
    }).length;
    var pct = keys.length ? Math.round(filled / keys.length * 100) : 0;
    document.getElementById("progress-fill").style.width = pct + "%";
    document.getElementById("progress-text").textContent = pct + "% complete";
  }

  /* ── Collect everything into one object ──────────── */
  function readEntries(kind) {
    return Array.prototype.map.call(container(kind).children, function(entry) {
      var row = {};
      entry.querySelectorAll("[data-field]").forEach(function(el) {
        var f = el.getAttribute("data-field");
        if (el.type === "radio") { if (el.checked) { row[f] = el.value; } }
        else if (el.value.trim()) { row[f] = el.value.trim(); }
      });
      var laws = entry.querySelector(".gg-sr-laws");
      if (laws) {
        row.scores = LAWS.map(function(l) {
          var v = laws.getAttribute("data-" + l);
          return v === null || v === "" ? null : Number(v);
        });
      }
      if (kind === "system") {
        var sel = entry.querySelector("[data-field=area]");
        if (sel.value) { row.area_label = sel.options[sel.selectedIndex].text; }
      }
      return row;
    }).filter(function(row) {
      /* a row that only carries its default direction, or empty scores, is empty */
      return Object.keys(row).some(function(k) {
        if (k === "scores") { return row.scores.some(function(s) { return s !== null; }); }
        if (k === "direction") { return false; }
        return true;
      });
    });
  }

  function collect() {
    var data = {};
    var fd = new FormData(form);
    fd.forEach(function(value, key) {
      if (key === "website" || /^row_\d+_/.test(key)) { return; }
      if (String(value).trim()) { data[key] = String(value).trim(); }
    });
    Object.keys(KINDS).forEach(function(kind) { data[KINDS[kind].list] = readEntries(kind); });
    return data;
  }

  /* ── Save / restore ──────────────────────────────── */
  var submitted = false;
  var saveTimer = null;
  function save(silent) {
    if (submitted) { return; }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(collect()));
      if (!silent) { showMessage("info", "Saved in this browser. Close the page and come back any time."); }
    } catch (err) {
      if (!silent) { showMessage("error", "This browser won't let me save. Keep the page open until you submit."); }
    }
  }
  function queueSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function() { save(true); }, 800);
  }

  function fillEntry(entry, row) {
    Object.keys(row).forEach(function(f) {
      if (f === "scores" || f === "area_label") { return; }
      entry.querySelectorAll("[data-field=\"" + f + "\"]").forEach(function(el) {
        if (el.type === "radio") {
          var opt = el.closest(".gg-apply-radio-option");
          el.checked = el.value === row[f];
          opt.classList.toggle("selected", el.checked);
          if (el.checked && f === "direction") { setDirection(entry, el.value); }
        } else {
          el.value = row[f];
        }
      });
    });
    var laws = entry.querySelector(".gg-sr-laws");
    if (laws && row.scores) {
      LAWS.forEach(function(l, i) { if (row.scores[i] !== null) { setLaw(laws, l, String(row.scores[i])); } });
    }
  }

  function restore() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch (err) { saved = null; }
    ORDER.forEach(function(kind) {
      var rows = saved && saved[KINDS[kind].list] && saved[KINDS[kind].list].length ? saved[KINDS[kind].list] : null;
      var n = rows ? rows.length : 1;
      for (var i = 0; i < n; i++) {
        var entry = addEntry(kind);
        if (rows && entry) { fillEntry(entry, rows[i]); }
      }
      if (kind === "system") { refreshServes(); }
    });
    /* serves options exist only after systems are filled; re-apply saved picks */
    if (saved && saved.new_habits) {
      Array.prototype.forEach.call(container("newhabit").children, function(entry, i) {
        var row = saved.new_habits[i];
        if (row && row.serves) { entry.querySelector("[data-field=serves]").value = row.serves; }
      });
    }
    if (saved) {
      Object.keys(saved).forEach(function(key) {
        if (typeof saved[key] !== "string") { return; }
        form.querySelectorAll("[name=\"" + key + "\"]").forEach(function(el) {
          if (el.type === "radio") {
            if (el.value === saved[key]) { el.checked = true; el.closest(".gg-apply-radio-option").classList.add("selected"); }
          } else { el.value = saved[key]; }
        });
      });
      showMessage("info", "Picked up where you left off.");
    }
    /* personalised links: ?name=&email= */
    var params = new URLSearchParams(window.location.search);
    ["name", "email"].forEach(function(k) {
      var el = document.getElementById(k);
      if (params.get(k) && !el.value) { el.value = params.get(k); }
    });
    updateProgress();
  }

  document.getElementById("save-btn").addEventListener("click", function() { save(false); ga4("season_review_saved", {}); });
  window.addEventListener("beforeunload", function() { save(true); });

  /* ── Format the email ────────────────────────────── */
  var LEVEL_WORDS = ["No", "Barely", "Mostly", "Yes"];
  var LAW_SHORT = ["Obvious", "Attractive", "Easy", "Satisfying"];

  function formatSubmission(d) {
    var L = [];
    function add(label, v) { if (v) { L.push("- " + label + ": " + v); } }
    function sub(label, v) { if (v) { L.push("    " + label + ": " + v); } }
    function block(title, v) { if (v) { L.push("### " + title); L.push(v); L.push(""); } }
    L.push("# Season Review " + SEASON + ": " + d.name);
    L.push("Email: " + d.email);
    L.push("Submitted: " + new Date().toISOString());
    L.push("");
    L.push("## PAST: " + SEASON);
    add("Proudest", d.proudest);
    add("One word", d.one_word);
    L.push("");
    block("Chapters", d.chapters);
    L.push("### Moments that mattered");
    d.moments.forEach(function(m, i) {
      L.push((i + 1) + ". " + (m.title || "(untitled)"));
      sub("what happened", m.what);
      sub("their part", m.role);
      sub("what it changed", m.impact);
    });
    L.push("");
    L.push("### Goals they set");
    d.goals.forEach(function(g) { L.push("- " + (g.goal || "(unnamed)") + " -> " + (g.result || "?") + (g.why ? " (" + g.why + ")" : "")); });
    L.push("");
    L.push("## PRESENT");
    d.strengths.forEach(function(s) {
      L.push("- STRENGTH: " + (s.trait || "?"));
      sub("showed up", s.story);
      sub("use more", s.use);
    });
    d.faults.forEach(function(f) {
      L.push("- FAULT: " + (f.trait || "?"));
      sub("cost them", f.story);
      sub("fix", f.fix);
    });
    add("Wants that fight the goal", d.competing_wants);
    add("Would have to start wanting", d.want_to_want);
    L.push("");
    L.push("### Habits, four-law audit");
    d.habits.forEach(function(h) {
      L.push("- " + (h.habit || "(unnamed)") + " [" + (h.stuck || "?") + "]");
      if (h.scores) {
        L.push("    " + h.scores.map(function(s, i) { return LAW_SHORT[i] + " " + (s === null ? "?" : LEVEL_WORDS[s]); }).join(" | "));
      }
    });
    L.push("");
    add("Life fit", d.life_fit);
    add("Where it fought", d.life_friction);
    add("Hurting", d.injuries_now);
    L.push("");
    L.push("## FUTURE: " + (SEASON + 1));
    block("The season they want", d.ideal_season);
    block("The season to avoid", d.avoid_season);
    L.push("### The goal");
    add("Goal", d.outcome_goal);
    add("Measured by", d.outcome_measure);
    add("By", d.outcome_date);
    add("Scares them", d.outcome_scary);
    add("Why", [d.why_1, d.why_2, d.why_3].filter(Boolean).join(" -> "));
    add("Inner obstacle", d.inner_obstacle);
    add("When it shows up", d.obstacle_plan);
    L.push("");
    L.push("### What has to get better");
    d.systems.forEach(function(s, i) {
      L.push("- S" + (i + 1) + " " + (s.area_label || "?") + (s.detail ? ": " + s.detail : ""));
      sub("evidence", s.metric);
      sub("change approach if unmoved by", s.check_by);
    });
    L.push("");
    L.push("### Habits to start and stop");
    d.new_habits.forEach(function(h) {
      var stop = h.direction === "reduce";
      L.push("- " + (stop ? "STOP " : "START ") + (h.habit || "?") + (h.serves ? " (serves " + h.serves + ")" : ""));
      sub(stop ? "invisible" : "when/where", h.obvious);
      sub(stop ? "unappealing" : "worth it", h.attractive);
      sub(stop ? "harder" : "minimum", h.easy);
      sub(stop ? "instead see" : "same-day proof", h.satisfying);
      sub("if-then", h.if_then);
    });
    L.push("");
    L.push("### Calendar");
    d.races.forEach(function(r) { L.push("- [" + (r.priority || "?") + "] " + (r.race || "?") + " " + (r.date || "")); });
    add("Hours/week", d.hours_next);
    add("Break", d.break_dates);
    add("Changes", d.life_changes);
    L.push("");
    L.push("## COACHING");
    add("Keep", d.coach_keep);
    add("Change", d.coach_change);
    add("Next season", d.next_season_plan);
    add("Not asked", d.anything_else);
    L.push("");
    L.push("## Flags");
    var flags = [];
    d.habits.forEach(function(h) {
      if (!h.scores) { return; }
      var zero = h.scores.map(function(s, i) { return s === 0 ? LAW_SHORT[i] : null; }).filter(Boolean);
      var known = h.scores.filter(function(s) { return s !== null; });
      var total = known.reduce(function(a, b) { return a + b; }, 0);
      if (zero.length) { flags.push((h.habit || "habit") + ": empty " + zero.join(", ")); }
      else if (known.length === 4 && total < 8) { flags.push((h.habit || "habit") + ": built to fail (under 8 of 12)"); }
    });
    if (d.outcome_scary === "no") { flags.push("Goal doesn't scare them: likely too small"); }
    if (!d.why_2) { flags.push("Why stops at one level"); }
    d.systems.forEach(function(s, i) {
      if (!s.metric) { flags.push("S" + (i + 1) + ": no evidence named"); }
      if (!s.check_by) { flags.push("S" + (i + 1) + ": no check date"); }
    });
    d.new_habits.forEach(function(h) { if (!h.if_then) { flags.push((h.habit || "habit") + ": no if-then"); } });
    if ((d.ideal_season || "").split(/\s+/).length < 150) { flags.push("Season-you-want write is short (" + (d.ideal_season || "").split(/\s+/).filter(Boolean).length + " words)"); }
    L.push(flags.length ? flags.map(function(f) { return "- " + f; }).join("\n") : "- none");
    L.push("");
    L.push("## Endure import (JSON)");
    L.push(JSON.stringify(toEndure(d)));
    return L.join("\n");
  }

  /* Shaped like endurelabs docs/specs/endure-loop-seed-manifest.json */
  function toEndure(d) {
    var goals = {
      "review:ROOT": {
        horizon: "season", title: d.outcome_goal || null,
        metric: { source_type: "manual", description: d.outcome_measure || null, due: d.outcome_date || null },
        why: [d.why_1, d.why_2, d.why_3].filter(Boolean),
        obstacle: d.inner_obstacle || null, obstacle_plan: d.obstacle_plan || null,
        kill_condition: null
      }
    };
    d.systems.forEach(function(s, i) {
      goals["review:S" + (i + 1)] = {
        horizon: "season", parent: "review:ROOT", area: s.area || null, title: s.detail || s.area_label || null,
        metric: { source_type: "manual", description: s.metric || null },
        kill_condition: s.check_by ? { kind: "metric_unchanged", evaluate_on: s.check_by } : null
      };
    });
    var actions = {};
    d.new_habits.forEach(function(h, i) {
      actions["review:H" + (i + 1)] = {
        direction: h.direction || "do", title: h.habit || null,
        goal: h.serves ? (h.serves === "goal" ? "review:ROOT" : "review:" + h.serves) : null,
        design: { obvious: h.obvious || null, attractive: h.attractive || null, easy: h.easy || null, satisfying: h.satisfying || null },
        if_then: h.if_then || null,
        scores: null
      };
    });
    var audit = d.habits.map(function(h) { return { title: h.habit || null, stuck: h.stuck || null, scores: h.scores || null }; });
    return { version: 2, season: SEASON, email: d.email, goals: goals, goal_actions: actions, habit_audit: audit, races: d.races };
  }

  /* ── Submit ──────────────────────────────────────── */
  form.addEventListener("submit", function(e) {
    e.preventDefault();
    var btn = document.getElementById("submit-btn");
    var d = collect();
    if (form.querySelector("[name=website]").value) { return; }
    if (!d.new_habits.length) {
      showMessage("error", "Add at least one habit to start or stop.");
      return;
    }
    btn.disabled = true;
    btn.textContent = "Submitting...";
    save(true);

    var payload = new FormData();
    payload.append("_subject", "Season Review " + SEASON + ": " + d.name);
    payload.append("_replyto", d.email);
    payload.append("_captcha", "false");
    payload.append("_template", "box");
    payload.append("name", d.name);
    payload.append("email", d.email);
    payload.append("message", formatSubmission(d));

    fetch(SUBMIT_URL, { method: "POST", body: payload, headers: { "Accept": "application/json" } })
      .then(function(r) {
        return r.json().catch(function() { return {}; }).then(function(res) {
          if (!r.ok || String(res.success) !== "true") { throw new Error(res.message || ("HTTP " + r.status)); }
        });
      })
      .then(function() {
        submitted = true;
        clearTimeout(saveTimer);
        try { localStorage.removeItem(STORAGE_KEY); } catch (err) { /* ignore */ }
        ga4("season_review_submitted", { systems: d.systems.length, habits: d.new_habits.length });
        showMessage("success", "Got it. I'll read it properly and come back with the plan for " + (SEASON + 1) + ".");
        btn.textContent = "Submitted";
      })
      .catch(function(err) {
        showMessage("error", "That didn't go through. Your answers are saved in this browser. Try again, or email __EMAIL__.");
        btn.disabled = false;
        btn.textContent = "Submit Season Review";
        ga4("season_review_error", { message: String(err.message || "unknown").slice(0, 80) });
      });
  });

  function showMessage(type, text) {
    var m = document.getElementById("message");
    m.className = "gg-apply-message " + type;
    m.textContent = text;
    m.classList.remove("hidden");
    m.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  restore();
  ga4("season_review_view", {});
})();
</script>'''
    return (
        js.replace("__STORAGE_KEY__", STORAGE_KEY)
        .replace("__SUBMIT_URL__", FORMSUBMIT_URL)
        .replace("__SEASON__", str(SEASON))
        .replace("__EMAIL__", FORMSUBMIT_EMAIL)
    )


# ── Page assembly ─────────────────────────────────────────────


def generate_season_review_page(external_assets=None) -> str:
    page_css = external_assets["css_tag"] if external_assets else get_page_css()
    title = f"Season Review {SEASON} | Gravel God"
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="robots" content="noindex, nofollow">
  <link rel="canonical" href="{SITE_BASE_URL}/coaching/season-review/">
  <meta property="og:title" content="{title}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{SITE_BASE_URL}/coaching/season-review/">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  <link rel="icon" type="image/svg+xml" href="https://gravelgodcycling.com/gg-logo.svg">
  {get_preload_hints()}
  {page_css}
  {get_ga4_head_snippet()}
  {build_apply_css()}
  {build_season_review_css()}
</head>
<body class="gg-neo-brutalist-page" style="background:var(--gg-color-warm-paper);color:var(--gg-color-near-black);font-family:var(--gg-font-data);font-size:var(--gg-font-size-sm);line-height:1.7;min-height:100vh">
  {build_nav()}
  <div class="gg-apply-container">
    {build_header()}
    {build_progress_bar()}
    <div id="message" class="gg-apply-message hidden"></div>
    <form id="season-form" class="gg-apply-form-card">
      <input type="text" name="website" class="gg-apply-honeypot" tabindex="-1" autocomplete="off">
      {_part(f"Part I &mdash; {SEASON}")}
      {build_section_you()}
      {build_section_start()}
      {build_section_chapters()}
      {build_section_moments()}
      {build_section_goals()}
      {_part("Part II &mdash; You, Now")}
      {build_section_traits()}
      {build_section_wants()}
      {build_section_habits()}
      {build_section_life()}
      {_part(f"Part III &mdash; {NEXT_SEASON}")}
      {build_section_ideal()}
      {build_section_avoid()}
      {build_section_goal()}
      {build_section_systems()}
      {build_section_new_habits()}
      {build_section_calendar()}
      {build_section_me()}
      {build_submit_buttons()}
    </form>
  </div>
  {build_templates()}
  {build_footer()}
  {build_season_review_js()}
  <script>{get_site_header_js()}</script>
  {get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate the season review page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = write_shared_assets(out_dir)

    html_content = generate_season_review_page(external_assets=assets)
    out_path = out_dir / "season-review.html"
    out_path.write_text(html_content, encoding="utf-8")
    print(f"Generated {out_path} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
