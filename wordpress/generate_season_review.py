#!/usr/bin/env python3
"""
Generate the Gravel God Season Review at /coaching/season-review/.

A close-out questionnaire sent to existing athletes at the end of a season.
It looks and behaves like the coaching intake (/coaching/apply/) — same
card, progress bar, save/resume, and brand tokens — and reuses that page's
CSS so the two can't drift apart.

The questions follow the Endure goal model (endurelabs
docs/specs/endure-loop-2026.md): one season outcome, the systems that
ladder up to it, and the habits that carry each system. Habits are scored
on James Clear's four laws (obvious, attractive, easy, satisfying), 0-3
each. Per the Endure ruling, the athlete sees the shape of the four scores,
never their sum. "Stop" habits invert the prompts.

Links can be personalised: ?name=Ada&email=ada@example.com prefills both.

Submission goes to formsubmit.co (already activated for
gravelgodcoaching@gmail.com on this site). The email carries a readable
review plus a JSON block shaped like the Endure seed manifest so the answers
can be loaded into Endure later without retyping.

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
    <p>About 15 minutes. What worked, what didn&#39;t, and what we build for {NEXT_SEASON}. Numbers beat adjectives.</p>
  </div>'''


def build_progress_bar() -> str:
    return '''<div class="gg-apply-progress">
    <div class="gg-apply-progress-bar">
      <div class="gg-apply-progress-fill" id="progress-fill"></div>
    </div>
    <div class="gg-apply-progress-text" id="progress-text">0% complete</div>
  </div>'''


def build_section_1_you() -> str:
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


def build_section_2_scored() -> str:
    rating = _radio_row(
        "season_rating",
        [(str(n), str(n)) for n in range(1, 11)],
        required=True,
    )
    consistency = _radio_row(
        "plan_completion",
        [
            ("under-50", "&lt; 50%"),
            ("50-70", "50&ndash;70%"),
            ("70-85", "70&ndash;85%"),
            ("85+", "85%+"),
        ],
        required=True,
    )
    return f'''<div class="gg-apply-section-title">2. The Season, Scored</div>
      <p class="gg-apply-section-sub">Before the story, the numbers.</p>

      <div class="gg-apply-group">
        <label class="gg-apply-label">Rate the season, 1&ndash;10 <span class="gg-apply-required">*</span></label>
        <div class="gg-sr-scale">{rating}</div>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label">How much of the plan did you actually do? <span class="gg-apply-required">*</span></label>
        {consistency}
      </div>

      <div class="gg-apply-inline">
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="weeks_lost">Weeks lost to illness, injury or life</label>
          <div class="gg-apply-unit-wrap">
            <input type="number" id="weeks_lost" name="weeks_lost" min="0" max="52" placeholder="0">
            <span class="gg-apply-unit">weeks</span>
          </div>
        </div>
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="ftp_now">FTP now <span class="gg-apply-optional">(if known)</span></label>
          <div class="gg-apply-unit-wrap">
            <input type="number" id="ftp_now" name="ftp_now" min="50" max="600" placeholder="250">
            <span class="gg-apply-unit">W</span>
          </div>
        </div>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="best_moment">The best moment of the season <span class="gg-apply-required">*</span></label>
        <textarea id="best_moment" name="best_moment" required rows="2" placeholder="e.g., Held the front group over the second climb at Gravel Worlds for the first time"></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="biggest_regret">The one thing you&#39;d redo <span class="gg-apply-required">*</span></label>
        <textarea id="biggest_regret" name="biggest_regret" required rows="2" placeholder="e.g., Went out too hard at mile 20 and paid for it at 80"></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="best_block">Your best stretch of training this year. What made it work?</label>
        <textarea id="best_block" name="best_block" rows="2" placeholder="e.g., May: fixed Tuesday group ride, no travel, in bed by 10"></textarea>
      </div>'''


def build_section_3_goals() -> str:
    return f'''<div class="gg-apply-section-title">3. The Goals You Set</div>
      <p class="gg-apply-section-sub">What you said you&#39;d do in {SEASON}, and what happened.</p>

      <div id="goals-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="goal">+ Add a goal</button>'''


def build_section_4_habits() -> str:
    return f'''<div class="gg-apply-section-title">4. The Habits That Held</div>
      <p class="gg-apply-section-sub">A habit that died usually had one of these four missing. Score each one honestly.</p>

      <div id="habits-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="habit">+ Add a habit</button>'''


def build_section_5_body() -> str:
    return f'''<div class="gg-apply-section-title">5. What Wore You Down</div>

      <div class="gg-apply-inline">
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="sleep_trend">Sleep, compared with a year ago</label>
          {_select("sleep_trend", [("better", "Better"), ("same", "About the same"), ("worse", "Worse")])}
        </div>
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="stress_trend">Life stress, compared with a year ago</label>
          {_select("stress_trend", [("lower", "Lower"), ("same", "About the same"), ("higher", "Higher")])}
        </div>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="injuries_now">Injuries or niggles you&#39;re carrying into the off-season</label>
        <textarea id="injuries_now" name="injuries_now" rows="2" placeholder="Where, how long, what makes it worse"></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="energy_drains">What cost you the most training this year?</label>
        <textarea id="energy_drains" name="energy_drains" rows="2" placeholder="e.g., Work travel in June, a cold every time the kids went back to school"></textarea>
      </div>'''


def build_section_6_outcome() -> str:
    return f'''<div class="gg-apply-section-title">6. {NEXT_SEASON}: The One Outcome</div>
      <p class="gg-apply-section-sub">One sentence. If it can&#39;t be measured, it&#39;s a wish.</p>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="outcome_goal">By the end of {NEXT_SEASON}, I want to&hellip; <span class="gg-apply-required">*</span></label>
        <textarea id="outcome_goal" name="outcome_goal" required rows="2" placeholder="e.g., Finish Unbound 200 in under 13 hours"></textarea>
      </div>

      <div class="gg-apply-inline">
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="outcome_measure">How we&#39;ll know <span class="gg-apply-required">*</span></label>
          <input type="text" id="outcome_measure" name="outcome_measure" required placeholder="e.g., Finish time on the official results">
        </div>
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="outcome_date">By when</label>
          <input type="date" id="outcome_date" name="outcome_date">
        </div>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="outcome_why">Why this one?</label>
        <textarea id="outcome_why" name="outcome_why" rows="2" placeholder="The reason that will still be true in February"></textarea>
      </div>'''


def build_section_7_races() -> str:
    return f'''<div class="gg-apply-section-title">7. {NEXT_SEASON}: Races</div>
      <p class="gg-apply-section-sub">A = the goal. B = matters. C = training with a number on.</p>

      <div id="races-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="race">+ Add a race</button>'''


def build_section_8_systems() -> str:
    return f'''<div class="gg-apply-section-title">8. What Has to Get Better</div>
      <p class="gg-apply-section-sub">Two or three things that decide the outcome. Each gets a number and a check date.</p>

      <div id="systems-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="system">+ Add one</button>'''


def build_section_9_new_habits() -> str:
    return f'''<div class="gg-apply-section-title">9. The Habits That Get You There</div>
      <p class="gg-apply-section-sub">Things to start and things to stop. Built so they survive a bad week.</p>

      <div id="newhabits-container" class="gg-sr-list"></div>
      <button type="button" class="gg-sr-add-btn" data-add="newhabit">+ Add a habit</button>'''


def build_section_10_year() -> str:
    hours = [
        ("3-5", "3&ndash;5 hrs"), ("5-7", "5&ndash;7 hrs"), ("7-10", "7&ndash;10 hrs"),
        ("10-12", "10&ndash;12 hrs"), ("12-15", "12&ndash;15 hrs"), ("15+", "15+ hrs"),
    ]
    return f'''<div class="gg-apply-section-title">10. The Year Ahead</div>

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
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="venues">Where you train, and minutes from door to start</label>
        <textarea id="venues" name="venues" rows="3" placeholder="Garage trainer, 2 min&#10;Local gravel loop, 10 min&#10;Gym, 20 min"></textarea>
      </div>'''


def build_section_11_coaching() -> str:
    return f'''<div class="gg-apply-section-title">11. Me</div>

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
      </div>'''


def build_section_12_other() -> str:
    return '''<div class="gg-apply-section-title">12. What Haven&#39;t I Asked?</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="anything_else">Anything else</label>
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


def _law_picker(prefix_attr: str) -> str:
    """Four-law scoring block. `prefix_attr` becomes the data-field root."""
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
        f'<div class="gg-sr-laws" data-{prefix_attr}>'
        + "".join(rows)
        + f'<div class="gg-sr-spine" aria-hidden="true">{spine}</div>'
        + '<div class="gg-sr-missing" hidden></div>'
        + "</div>"
    )


def build_templates() -> str:
    areas = "".join(f'<option value="{v}">{t}</option>' for v, t in SYSTEM_AREAS)
    return f'''<template id="tpl-goal">
  <div class="gg-sr-entry" data-kind="goal">
    <div class="gg-sr-entry-head"><span class="gg-sr-entry-num"></span><button type="button" class="gg-sr-remove">Remove</button></div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">Goal</label>
      <input type="text" data-field="goal" placeholder="e.g., Break 10 hours at Mid South">
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">Result</label>
      <div class="gg-apply-radio-group gg-apply-radio-horizontal">
        <label class="gg-apply-radio-option"><input type="radio" data-field="result" value="hit"><div class="gg-apply-radio-label"><div class="gg-apply-radio-title">Hit it</div></div></label>
        <label class="gg-apply-radio-option"><input type="radio" data-field="result" value="close"><div class="gg-apply-radio-label"><div class="gg-apply-radio-title">Close</div></div></label>
        <label class="gg-apply-radio-option"><input type="radio" data-field="result" value="missed"><div class="gg-apply-radio-label"><div class="gg-apply-radio-title">Missed</div></div></label>
        <label class="gg-apply-radio-option"><input type="radio" data-field="result" value="dropped"><div class="gg-apply-radio-label"><div class="gg-apply-radio-title">Dropped it</div></div></label>
      </div>
    </div>
    <div class="gg-apply-group">
      <label class="gg-apply-label">What decided it</label>
      <input type="text" data-field="why" placeholder="e.g., Flatted at mile 40; fitness was there">
    </div>
  </div>
</template>

<template id="tpl-habit">
  <div class="gg-sr-entry" data-kind="habit">
    <div class="gg-sr-entry-head"><span class="gg-sr-entry-num"></span><button type="button" class="gg-sr-remove">Remove</button></div>
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
    {_law_picker("laws")}
  </div>
</template>

<template id="tpl-race">
  <div class="gg-sr-entry" data-kind="race">
    <div class="gg-sr-entry-head"><span class="gg-sr-entry-num"></span><button type="button" class="gg-sr-remove">Remove</button></div>
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
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="C">C</option>
        </select>
      </div>
    </div>
  </div>
</template>

<template id="tpl-system">
  <div class="gg-sr-entry" data-kind="system">
    <div class="gg-sr-entry-head"><span class="gg-sr-entry-num"></span><button type="button" class="gg-sr-remove">Remove</button></div>
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
      <label class="gg-apply-label">The number that shows it&#39;s working</label>
      <input type="text" data-field="metric" placeholder="e.g., Power in hour 5 of a long ride within 10% of hour 1">
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
    <div class="gg-sr-entry-head"><span class="gg-sr-entry-num"></span><button type="button" class="gg-sr-remove">Remove</button></div>
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
    <div class="gg-sr-law-prompts">
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

@media (max-width: 600px) {
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
  var LIMITS = { goal: 6, habit: 6, race: 8, system: 4, newhabit: 8 };
  var START = { goal: 1, habit: 1, race: 1, system: 1, newhabit: 1 };
  var TITLES = { goal: "Goal", habit: "Habit", race: "Race", system: "Area", newhabit: "Habit" };

  var form = document.getElementById("season-form");

  function ga4(name, params) {
    if (typeof gtag === "function") { gtag("event", name, params || {}); }
  }

  /* ── Repeating entries ───────────────────────────── */
  var rowSeq = 0;
  function container(kind) { return document.getElementById(kind + "s-container"); }

  function addEntry(kind) {
    var list = container(kind);
    if (list.children.length >= LIMITS[kind]) { return null; }
    var node = document.getElementById("tpl-" + kind).content.firstElementChild.cloneNode(true);
    rowSeq++;
    /* radios inside a row need a row-unique name so rows don't share a group */
    node.querySelectorAll("input[type=radio]").forEach(function(r) {
      r.name = kind + "_" + rowSeq + "_" + r.getAttribute("data-field");
    });
    list.appendChild(node);
    renumber(kind);
    if (kind === "system" || kind === "newhabit") { refreshServes(); }
    return node;
  }

  function renumber(kind) {
    var list = container(kind);
    Array.prototype.forEach.call(list.children, function(el, i) {
      el.querySelector(".gg-sr-entry-num").textContent = TITLES[kind] + " " + (i + 1);
      el.querySelector(".gg-sr-remove").hidden = list.children.length === 1;
    });
    var btn = document.querySelector("[data-add=\"" + kind + "\"]");
    if (btn) { btn.disabled = list.children.length >= LIMITS[kind]; }
  }

  function areaLabel(sys) {
    var sel = sys.querySelector("[data-field=area]");
    var detail = sys.querySelector("[data-field=detail]").value.trim();
    var name = sel.value ? sel.options[sel.selectedIndex].text : "";
    return detail || name;
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
      sel.appendChild(new Option("The outcome directly", "outcome"));
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

  /* ── Delegated events ────────────────────────────── */
  form.addEventListener("click", function(e) {
    var t = e.target;
    var add = t.closest("[data-add]");
    if (add) { addEntry(add.getAttribute("data-add")); updateProgress(); return; }

    var rm = t.closest(".gg-sr-remove");
    if (rm) {
      var entry = rm.closest(".gg-sr-entry");
      var kind = entry.getAttribute("data-kind");
      entry.remove();
      renumber(kind);
      if (kind === "system") { refreshServes(); }
      updateProgress();
      return;
    }

    var lvl = t.closest(".gg-sr-level");
    if (lvl) {
      var laws = lvl.closest(".gg-sr-laws");
      var law = lvl.getAttribute("data-law");
      var level = lvl.getAttribute("data-level");
      setLaw(laws, law, laws.getAttribute("data-" + law) === level ? "" : level);
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
      updateProgress();
    }
  });

  form.addEventListener("input", function(e) {
    if (e.target.closest("[data-kind=system]")) { refreshServes(); }
    updateProgress();
  });
  form.addEventListener("change", function(e) {
    if (e.target.closest("[data-kind=system]")) { refreshServes(); }
    updateProgress();
  });

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
      return Object.keys(row).some(function(k) {
        return k === "scores" ? row.scores.some(function(s) { return s !== null; }) : true;
      });
    });
  }

  function collect() {
    var data = {};
    var fd = new FormData(form);
    fd.forEach(function(value, key) {
      if (key.indexOf("_") === 0 || /^(goal|habit|race|system|newhabit)_\d+_/.test(key)) { return; }
      if (String(value).trim()) { data[key] = String(value).trim(); }
    });
    data.goals = readEntries("goal");
    data.habits = readEntries("habit");
    data.races = readEntries("race");
    data.systems = readEntries("system");
    data.new_habits = readEntries("newhabit");
    return data;
  }

  /* ── Save / restore ──────────────────────────────── */
  function save(silent) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(collect()));
      if (!silent) { showMessage("info", "Saved in this browser. Close the page and come back any time."); }
    } catch (err) {
      if (!silent) { showMessage("error", "This browser won't let me save. Keep the page open until you submit."); }
    }
  }

  function fillEntry(entry, row) {
    Object.keys(row).forEach(function(f) {
      if (f === "scores" || f === "area_label") { return; }
      entry.querySelectorAll("[data-field=\"" + f + "\"]").forEach(function(el) {
        if (el.type === "radio") {
          if (el.value === row[f]) {
            el.checked = true;
            el.closest(".gg-apply-radio-option").classList.add("selected");
            if (f === "direction") { setDirection(entry, el.value); }
          }
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
    var lists = { goal: "goals", habit: "habits", race: "races", system: "systems", newhabit: "new_habits" };
    /* systems first so habits can point at them */
    ["system", "goal", "habit", "race", "newhabit"].forEach(function(kind) {
      var rows = saved && saved[lists[kind]] && saved[lists[kind]].length ? saved[lists[kind]] : null;
      var n = rows ? rows.length : START[kind];
      for (var i = 0; i < n; i++) {
        var entry = addEntry(kind);
        if (rows && entry) { fillEntry(entry, rows[i]); }
      }
      if (kind === "system") { refreshServes(); }
    });
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
  var submitted = false;
  window.addEventListener("beforeunload", function() { if (!submitted) { save(true); } });

  /* ── Format the email ────────────────────────────── */
  var LEVEL_WORDS = ["No", "Barely", "Mostly", "Yes"];
  var LAW_SHORT = ["Obvious", "Attractive", "Easy", "Satisfying"];

  function lawLine(scores) {
    return scores.map(function(s, i) { return LAW_SHORT[i] + " " + (s === null ? "?" : LEVEL_WORDS[s]); }).join(" | ");
  }

  function formatSubmission(d) {
    var L = [];
    function add(label, v) { if (v) { L.push("- " + label + ": " + v); } }
    function sub(label, v) { if (v) { L.push("    " + label + ": " + v); } }
    L.push("# Season Review " + SEASON + ": " + d.name);
    L.push("Email: " + d.email);
    L.push("Submitted: " + new Date().toISOString());
    L.push("");
    L.push("## The season, scored");
    add("Rating", d.season_rating + "/10");
    add("Plan completion", d.plan_completion);
    add("Weeks lost", d.weeks_lost);
    add("FTP now", d.ftp_now && d.ftp_now + " W");
    add("Best moment", d.best_moment);
    add("Would redo", d.biggest_regret);
    add("Best training stretch", d.best_block);
    L.push("");
    L.push("## Last season's goals");
    d.goals.forEach(function(g) { L.push("- " + (g.goal || "(unnamed)") + " -> " + (g.result || "?") + (g.why ? " (" + g.why + ")" : "")); });
    L.push("");
    L.push("## Habits, four-law audit");
    d.habits.forEach(function(h) {
      L.push("- " + (h.habit || "(unnamed)") + " [" + (h.stuck || "?") + "]");
      if (h.scores) { L.push("    " + lawLine(h.scores)); }
    });
    L.push("");
    L.push("## What wore them down");
    add("Sleep vs last year", d.sleep_trend);
    add("Stress vs last year", d.stress_trend);
    add("Injuries now", d.injuries_now);
    add("Biggest training cost", d.energy_drains);
    L.push("");
    L.push("## " + (SEASON + 1) + " outcome");
    add("Outcome", d.outcome_goal);
    add("Measured by", d.outcome_measure);
    add("By", d.outcome_date);
    add("Why", d.outcome_why);
    L.push("");
    L.push("## Races");
    d.races.forEach(function(r) { L.push("- [" + (r.priority || "?") + "] " + (r.race || "?") + " " + (r.date || "")); });
    L.push("");
    L.push("## What has to get better");
    d.systems.forEach(function(s, i) {
      L.push("- S" + (i + 1) + " " + (s.area_label || "?") + (s.detail ? ": " + s.detail : ""));
      if (s.metric) { L.push("    number: " + s.metric); }
      if (s.check_by) { L.push("    change approach if unmoved by " + s.check_by); }
    });
    L.push("");
    L.push("## New habits");
    d.new_habits.forEach(function(h) {
      var stop = h.direction === "reduce";
      L.push("- " + (stop ? "STOP " : "START ") + (h.habit || "?") + (h.serves ? " (serves " + h.serves + ")" : ""));
      sub(stop ? "invisible" : "when/where", h.obvious);
      sub(stop ? "unappealing" : "worth it", h.attractive);
      sub(stop ? "harder" : "minimum", h.easy);
      sub(stop ? "instead see" : "same-day proof", h.satisfying);
    });
    L.push("");
    L.push("## The year ahead");
    add("Hours/week", d.hours_next);
    add("Break", d.break_dates);
    add("Changes", d.life_changes);
    add("Venues", d.venues && d.venues.replace(/\n/g, "; "));
    L.push("");
    L.push("## Coaching");
    add("Keep", d.coach_keep);
    add("Change", d.coach_change);
    add("Next season", d.next_season_plan);
    add("Anything else", d.anything_else);
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
    d.systems.forEach(function(s, i) {
      if (!s.metric) { flags.push("S" + (i + 1) + ": no number"); }
      if (!s.check_by) { flags.push("S" + (i + 1) + ": no check date"); }
    });
    L.push(flags.length ? flags.map(function(f) { return "- " + f; }).join("\n") : "- none");
    L.push("");
    L.push("## Endure import (JSON)");
    L.push(JSON.stringify(toEndure(d)));
    return L.join("\n");
  }

  /* Shaped like endurelabs docs/specs/endure-loop-seed-manifest.json */
  function toEndure(d) {
    var goals = { "review:ROOT": { horizon: "season", title: d.outcome_goal || null, metric: { source_type: "manual", description: d.outcome_measure || null, due: d.outcome_date || null }, kill_condition: null } };
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
        goal: h.serves ? (h.serves === "outcome" ? "review:ROOT" : "review:" + h.serves) : null,
        design: { obvious: h.obvious || null, attractive: h.attractive || null, easy: h.easy || null, satisfying: h.satisfying || null },
        scores: null
      };
    });
    var audit = d.habits.map(function(h) { return { title: h.habit || null, stuck: h.stuck || null, scores: h.scores || null }; });
    return { version: 1, season: SEASON, email: d.email, goals: goals, goal_actions: actions, habit_audit: audit, races: d.races };
  }

  /* ── Submit ──────────────────────────────────────── */
  form.addEventListener("submit", function(e) {
    e.preventDefault();
    var btn = document.getElementById("submit-btn");
    var d = collect();
    if (form.querySelector("[name=website]").value) { return; }
    if (!d.new_habits.length || !d.systems.length) {
      showMessage("error", "Add at least one thing that has to get better and one habit for it.");
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
        try { localStorage.removeItem(STORAGE_KEY); } catch (err) { /* ignore */ }
        submitted = true;
        ga4("season_review_submitted", { systems: d.systems.length, habits: d.new_habits.length });
        showMessage("success", "Got it. I'll read it properly and come back with the plan for " + (SEASON + 1) + ".");
        btn.textContent = "Submitted";
      })
      .catch(function(err) {
        showMessage("error", "That didn't go through. Your answers are saved in this browser. Try again, or email " + "__EMAIL__" + ".");
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
      {build_section_1_you()}
      {build_section_2_scored()}
      {build_section_3_goals()}
      {build_section_4_habits()}
      {build_section_5_body()}
      {build_section_6_outcome()}
      {build_section_7_races()}
      {build_section_8_systems()}
      {build_section_9_new_habits()}
      {build_section_10_year()}
      {build_section_11_coaching()}
      {build_section_12_other()}
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
