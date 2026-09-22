#!/usr/bin/env python3
"""
Generate the Gravel God Season Review at /coaching/season-review/.

A short close-out questionnaire sent to existing athletes at the end of a
season. It looks and behaves like the coaching intake (/coaching/apply/) —
same card, progress bar, save/resume, and brand tokens — and reuses that
page's CSS so the two can't drift apart.

Built to be finished: about 15 minutes, one sitting. Matti's Oct 2025
Self-Authoring Google Form (30-45 min) got zero responses, and a 60-90
minute draft of this page was cut down after two adversarial reviews (sol,
Sep 22 2026). What survived:

  - Past: the proudest moment and last season's main goal against its
    result (judged against the goal set, not the one remembered).
  - Future: one measurable goal and why, then the inner obstacle and an
    if-then plan (Oettingen's WOOP; Gollwitzer & Sheeran 2006). These have
    the strongest general evidence of anything in Self Authoring's family,
    though none of it is tested on athletes.
  - The Endure chain in its smallest form: goal -> one area -> one habit
    (start or stop, when and where, smallest version).
  - "Go deeper": optional, collapsed Self Authoring modules for athletes
    who want to spend much longer: a 15-minute "season you want" write,
    the season to avoid, the moments that shaped the year, one strength and
    one fault (verbatim Present Authoring wording), wants that fight the
    goal (Matti's 2021 thesis), a dead habit diagnosed by the four laws, and
    more whys. Matti's direction: an MVP review everyone finishes, with the
    option to go deep.

Deliberately absent: training numbers (FTP etc. come from data).

Links can be personalised: ?name=Ada&email=ada@example.com prefills both.

Submission goes to formsubmit.co (already activated for
gravelgodcoaching@gmail.com on this site). The email carries a readable
review, a few flags for the coach, and a draft JSON block in the shape of
the Endure goal tree.

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

# v2: the short form. Old long-form drafts must not restore into it.
STORAGE_KEY = f"season_review_{SEASON}_v2"

# Verbatim from the Self Authoring Present Authoring fault lists, chosen for
# what shows up in training and racing.
FAULTS = [
    "Am too perfectionistic",
    "Feel that I am being unproductive if I relax",
    "Seriously dislike having my routine or schedule upset",
    "Often procrastinate",
    "Frequently make excuses",
    "Have no stable daily routine for sleeping or eating",
    "Pursue too many activities at the same time",
    "May spend too much time pursuing fun and excitement",
    "Am often too optimistic",
    "Often take counterproductive or unnecessary risks",
    "Compare myself unfavorably to other people",
    "Let my fears stop me from doing things I want to do",
    "Get stressed out easily",
    "Cannot negotiate for myself very well",
]

AREAS = [
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

HOURS = [
    ("3-5", "3&ndash;5 hrs"), ("5-7", "5&ndash;7 hrs"), ("7-10", "7&ndash;10 hrs"),
    ("10-12", "10&ndash;12 hrs"), ("12-15", "12&ndash;15 hrs"), ("15+", "15+ hrs"),
]


# ── Small builders ────────────────────────────────────────────


def _radio_row(name: str, options, required: bool = False) -> str:
    parts = []
    for i, (value, title) in enumerate(options):
        req = " required" if required and i == 0 else ""
        parts.append(
            f'<label class="gg-apply-radio-option">'
            f'<input type="radio" name="{name}" value="{value}"{req}>'
            f'<div class="gg-apply-radio-label"><div class="gg-apply-radio-title">{title}</div></div>'
            f"</label>"
        )
    return '<div class="gg-apply-radio-group gg-apply-radio-horizontal">' + "".join(parts) + "</div>"


def _select(name: str, options, required: bool = False) -> str:
    req = " required" if required else ""
    opts = '<option value="">Select...</option>' + "".join(
        f'<option value="{v}">{t}</option>' for v, t in options
    )
    return f'<select id="{name}" name="{name}"{req}>{opts}</select>'


def _req() -> str:
    return ' <span class="gg-apply-required">*</span>'


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
    <p>About 15 minutes, with optional sections at the end if you want to go deep. It saves as you type.</p>
  </div>'''


def build_progress_bar() -> str:
    return '''<div class="gg-apply-progress">
    <div class="gg-apply-progress-bar">
      <div class="gg-apply-progress-fill" id="progress-fill"></div>
    </div>
    <div class="gg-apply-progress-text" id="progress-text">0% complete</div>
  </div>'''


def build_section_you() -> str:
    return f'''<div class="gg-apply-section-title">1. You</div>

      <div class="gg-apply-inline">
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="name">Name{_req()}</label>
          <input type="text" id="name" name="name" required autocomplete="name" placeholder="First Last">
        </div>
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="email">Email{_req()}</label>
          <input type="email" id="email" name="email" required autocomplete="email" placeholder="you@email.com">
        </div>
      </div>'''


def build_section_past() -> str:
    return f'''<div class="gg-apply-section-title">2. {SEASON}</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="proudest">What moment from {SEASON} are you proudest of? What happened, and what did you do that helped?{_req()}</label>
        <textarea id="proudest" name="proudest" required rows="4"></textarea>
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="last_goal">What was your main goal for {SEASON}?{_req()}</label>
        <input type="text" id="last_goal" name="last_goal" required placeholder="The one you set before the season">
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label">What happened?{_req()}</label>
        {_radio_row("last_goal_result", [
            ("hit", "Hit"), ("close", "Close"), ("missed", "Missed"),
            ("dropped", "Dropped"), ("none", "No clear goal"),
        ], required=True)}
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="last_goal_why">What most decided the result?{_req()}</label>
        <input type="text" id="last_goal_why" name="last_goal_why" required placeholder="e.g., Flatted at mile 40; the fitness was there">
      </div>'''


def build_section_goal() -> str:
    return f'''<div class="gg-apply-section-title">3. {NEXT_SEASON}</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="outcome_goal">By the end of {NEXT_SEASON}, I will&hellip;{_req()}</label>
        <input type="text" id="outcome_goal" name="outcome_goal" required placeholder="e.g., Finish Unbound 200 under 14 hours">
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="outcome_measure">How will we know?{_req()}</label>
        <input type="text" id="outcome_measure" name="outcome_measure" required placeholder="e.g., Official finish time">
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="outcome_why">Why does this matter to you?{_req()}</label>
        <input type="text" id="outcome_why" name="outcome_why" required>
      </div>

      <div class="gg-apply-inline">
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="a_race">Main race, if the goal has one</label>
          <input type="text" id="a_race" name="a_race" placeholder="e.g., Unbound 200">
        </div>
        <div class="gg-apply-group">
          <label class="gg-apply-label" for="a_race_date">Date</label>
          <input type="date" id="a_race_date" name="a_race_date">
        </div>
      </div>'''


def build_section_obstacle() -> str:
    return f'''<div class="gg-apply-section-title">4. What Gets in the Way</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="inner_obstacle">What in you is most likely to get in the way?{_req()}</label>
        <input type="text" id="inner_obstacle" name="inner_obstacle" required placeholder="Not the weather. You. e.g., I skip rides after a late night out">
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="obstacle_plan">If that shows up, then I will&hellip;{_req()}</label>
        <input type="text" id="obstacle_plan" name="obstacle_plan" required placeholder="e.g., Ride the short version before 9 a.m.">
      </div>'''


def build_section_habit() -> str:
    return f'''<div class="gg-apply-section-title">5. One Area, One Habit</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="area">What one area most needs to improve for this goal?{_req()}</label>
        {_select("area", AREAS, required=True)}
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label">Will you start or stop a habit?{_req()}</label>
        {_radio_row("habit_direction", [("do", "Start"), ("reduce", "Stop")], required=True)}
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="habit">What is the habit?{_req()}</label>
        <input type="text" id="habit" name="habit" required
          data-ph-do="e.g., 10 minutes of hip mobility" data-ph-reduce="e.g., Phone in the bedroom"
          placeholder="e.g., 10 minutes of hip mobility">
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="habit_when" data-lbl-do="When and where will it happen?" data-lbl-reduce="What will you change so it doesn&#39;t happen?">When and where will it happen?{_req()}</label>
        <input type="text" id="habit_when" name="habit_when" required
          data-ph-do="e.g., After I close the laptop, on the mat by the trainer" data-ph-reduce="e.g., Charger lives in the kitchen"
          placeholder="e.g., After I close the laptop, on the mat by the trainer">
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="habit_min" data-lbl-do="What is the smallest version that counts?" data-lbl-reduce="What will you do instead?">What is the smallest version that counts?{_req()}</label>
        <input type="text" id="habit_min" name="habit_min" required
          data-ph-do="e.g., One stretch" data-ph-reduce="e.g., Read the book on the nightstand"
          placeholder="e.g., One stretch">
      </div>'''


def build_section_year() -> str:
    return f'''<div class="gg-apply-section-title">6. Your Year</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="hours_next">How many hours can you honestly give most weeks?{_req()}</label>
        {_select("hours_next", HOURS, required=True)}
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="constraints">Anything that could change what you can do: work, family, health or travel?{_req()}</label>
        <input type="text" id="constraints" name="constraints" required placeholder="Write &ldquo;nothing&rdquo; if none">
      </div>'''


def build_section_me() -> str:
    return f'''<div class="gg-apply-section-title">7. Me</div>

      <div class="gg-apply-group">
        <label class="gg-apply-label">For {NEXT_SEASON}, what do you want from me?{_req()}</label>
        {_radio_row("next_season_plan", [
            ("coaching", "Coaching"),
            ("custom_plan", "A custom plan"),
            ("undecided", "Not sure"),
        ], required=True)}
      </div>

      <div class="gg-apply-group">
        <label class="gg-apply-label" for="coach_notes">What should I keep or change? Anything else?</label>
        <textarea id="coach_notes" name="coach_notes" rows="3"></textarea>
      </div>'''


STRENGTHS = [
    "Do what I say I am going to do",
    "Make plans and stick to them",
    "Am very goal-oriented",
    "Have seen my tendency for hard work pay off",
    "Am always learning new things",
    "Am not bothered when things don't go according to plan",
    "Calm down quickly when I do get upset",
    "Am rarely or never stopped from doing what I want by my fears",
    "Watch what I eat carefully",
    "Am comfortable alone",
    "Enjoy time in natural surroundings",
    "Make other people laugh and have fun",
]

# Why a habit died, one per four-law column (obvious, attractive, easy, satisfying).
DEAD_HABIT_REASONS = [
    ("dead_obvious", "No set time or place"),
    ("dead_attractive", "Nothing in it I looked forward to"),
    ("dead_easy", "Too much hassle to start"),
    ("dead_satisfying", "Couldn't see it working"),
]


def _trait_select(name: str, traits) -> str:
    esc = lambda t: t.replace("'", "&#39;")
    opts = '<option value="">Select...</option>' + "".join(
        f'<option value="{esc(t)}">{esc(t)}</option>' for t in traits
    )
    return f'<select id="{name}" name="{name}">{opts}</select>'


def _field(name: str, label: str, rows: int = 0, placeholder: str = "") -> str:
    ph = f' placeholder="{placeholder}"' if placeholder else ""
    control = (
        f'<textarea id="{name}" name="{name}" rows="{rows}"{ph}></textarea>' if rows
        else f'<input type="text" id="{name}" name="{name}"{ph}>'
    )
    return f'''<div class="gg-apply-group">
          <label class="gg-apply-label" for="{name}">{label}</label>
          {control}
        </div>'''


def _timed_field(name: str, label: str, minutes: int, rows: int) -> str:
    return f'''<div class="gg-apply-group">
          <div class="gg-sr-label-row">
            <label class="gg-apply-label" for="{name}">{label}</label>
            <button type="button" class="gg-sr-timer" data-minutes="{minutes}" data-target="{name}">Start {minutes}:00</button>
          </div>
          <textarea id="{name}" name="{name}" rows="{rows}" class="gg-sr-long"></textarea>
        </div>'''


def _module(key: str, title: str, minutes: str, body: str) -> str:
    return f'''<details class="gg-sr-deeper" data-module="{key}">
        <summary>{title} <span class="gg-apply-optional">({minutes})</span></summary>
        {body}
      </details>'''


def build_deep_modules() -> str:
    """Optional Self Authoring depth. Collapsed; the core form stands alone."""
    dead = "".join(
        f'<label class="gg-apply-checkbox-option"><input type="checkbox" name="{n}" value="yes">'
        f'<span class="gg-apply-checkbox-label">{t}</span></label>'
        for n, t in DEAD_HABIT_REASONS
    )
    modules = [
        _module("ideal", "The season you want", "15 min", _timed_field(
            "ideal_season",
            f"It&#39;s December {NEXT_SEASON} and the season went as well as it could. Who were you, what did you do, and what made it matter? Write without stopping.",
            15, 12)),
        _module("avoid", "The season to avoid", "5 min", _timed_field(
            "avoid_season",
            f"It&#39;s December {NEXT_SEASON} and it went badly. What happened, and what was your part in it?",
            5, 7)),
        _module("moments", f"The moments that shaped {SEASON}", "10 min",
            _field("moment_1", "The moment that mattered most: what happened?", 3)
            + _field("moment_1_role", "What part was yours, and what wasn&#39;t?", 2)
            + _field("moment_1_impact", "What did it change about how you see yourself?", 2)
            + _field("moment_2", "Another one, good or bad", 3)),
        _module("traits", "What carried you, what cost you", "5 min",
            f'''<div class="gg-apply-group">
          <label class="gg-apply-label" for="strength">Which of these carried you in {SEASON}?</label>
          {_trait_select("strength", STRENGTHS)}
        </div>'''
            + _field("strength_when", "When did it show up, and how do you use it more?", 2)
            + f'''<div class="gg-apply-group">
          <label class="gg-apply-label" for="fault">Which of these cost you most?</label>
          {_trait_select("fault", FAULTS)}
        </div>'''
            + _field("fault_when", "When did it cost you, and what will you do so it doesn&#39;t repeat?", 2)),
        _module("wants", "Wants that fight your goal", "3 min",
            _field("competing_wants", "What do you enjoy that costs you training?", 2, "The post-ride party. Two days wrecked, twenty times a year.")
            + _field("want_to_want", "What would you have to start wanting instead?", 0, "e.g., Being proud of a 9 p.m. bedtime")),
        _module("dead_habit", "A habit that died", "2 min",
            _field("dead_habit", f"A habit you meant to keep in {SEASON} that didn&#39;t last", 0, "e.g., Mobility after every ride")
            + f'''<div class="gg-apply-group">
          <label class="gg-apply-label">What was missing?</label>
          <div class="gg-apply-checkbox-vertical">{dead}</div>
        </div>'''),
        _module("whys", "Keep asking why", "3 min",
            _field("why_2", "You said why the goal matters. Why does that matter?")
            + _field("why_3", "And why does that matter?")),
    ]
    return (
        '<div class="gg-sr-part">Go deeper &mdash; optional, as much as you want</div>'
        + "\n      ".join(modules)
    )


def build_submit_buttons() -> str:
    return '''<div class="gg-apply-actions">
        <button type="button" class="gg-apply-save-btn" id="save-btn">Save Progress</button>
        <button type="submit" class="gg-apply-submit-btn" id="submit-btn">Submit Season Review</button>
      </div>'''


def build_footer() -> str:
    return f'''<div class="gg-apply-confidential-wrap">
    <p class="gg-apply-confidential">Your answers, including health information you choose to share, are used to coach you as described in the <a href="/privacy/">Privacy Policy</a>. They reach me by email through FormSubmit, a form service that keeps a copy for 30 days. Drafts are saved only in this browser until you submit. Questions? Email {FORMSUBMIT_EMAIL}</p>
  </div>
  ''' + get_mega_footer_html()


# ── CSS (additions on top of the intake form's CSS) ───────────


def build_season_review_css() -> str:
    return '''<style>
.gg-sr-part {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wider);
  background: var(--gg-color-near-black);
  color: var(--gg-color-white);
  padding: var(--gg-spacing-xs) var(--gg-spacing-md);
  margin: var(--gg-spacing-2xl) 0 var(--gg-spacing-md);
}
.gg-sr-deeper {
  border: 2px dashed var(--gg-color-near-black);
  padding: var(--gg-spacing-md);
  margin-bottom: var(--gg-spacing-sm);
}
.gg-sr-deeper[open] { border-style: solid; background: var(--gg-color-warm-paper); }
.gg-sr-deeper summary {
  cursor: pointer;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: var(--gg-letter-spacing-wide);
}
.gg-sr-deeper[open] summary { margin-bottom: var(--gg-spacing-lg); }
.gg-sr-deeper .gg-apply-group:last-child { margin-bottom: 0; }

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

@media (max-width: 600px) {
  .gg-sr-label-row { flex-direction: column; align-items: stretch; }
  .gg-sr-timer { align-self: flex-start; }
  .gg-apply-actions { flex-direction: column-reverse; align-items: stretch; gap: var(--gg-spacing-sm); }
  .gg-apply-save-btn { margin-right: 0; }
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

  var form = document.getElementById("season-form");

  function ga4(name, params) {
    if (typeof gtag === "function") { gtag("event", name, params || {}); }
  }

  /* ── Start / stop swaps the habit prompts ────────── */
  function setDirection(dir) {
    form.querySelectorAll("[data-ph-" + dir + "]").forEach(function(el) {
      el.placeholder = el.getAttribute("data-ph-" + dir);
    });
    form.querySelectorAll("[data-lbl-" + dir + "]").forEach(function(el) {
      var star = el.querySelector(".gg-apply-required");
      el.textContent = el.getAttribute("data-lbl-" + dir);
      if (star) { el.appendChild(document.createTextNode(" ")); el.appendChild(star); }
    });
  }

  /* ── Writing timer (end time, so it survives a backgrounded tab) ── */
  var timer = null;
  var timerBtn = null;
  function toggleTimer(btn) {
    var minutes = btn.getAttribute("data-minutes");
    if (timer && timerBtn !== btn) {
      clearInterval(timer);
      timer = null;
      timerBtn.classList.remove("running");
      timerBtn.textContent = "Start " + timerBtn.getAttribute("data-minutes") + ":00";
    }
    timerBtn = btn;
    if (timer) {
      clearInterval(timer);
      timer = null;
      btn.classList.remove("running", "done");
      btn.textContent = "Start " + minutes + ":00";
      return;
    }
    var endsAt = Date.now() + Number(minutes) * 60000;
    btn.classList.remove("done");
    btn.classList.add("running");
    document.getElementById(btn.getAttribute("data-target")).focus();
    function paint() {
      var left = Math.max(0, Math.round((endsAt - Date.now()) / 1000));
      if (left === 0) {
        clearInterval(timer);
        timer = null;
        btn.classList.remove("running");
        btn.classList.add("done");
        btn.textContent = "Time";
        return;
      }
      var m = Math.floor(left / 60), s = left % 60;
      btn.textContent = m + ":" + (s < 10 ? "0" : "") + s;
    }
    paint();
    timer = setInterval(paint, 500);
  }

  /* ── Events ──────────────────────────────────────── */
  form.addEventListener("click", function(e) {
    var t = e.target;
    var tb = t.closest(".gg-sr-timer");
    if (tb) { toggleTimer(tb); return; }

    var box = t.closest(".gg-apply-checkbox-option");
    if (box) {
      var cb = box.querySelector("input");
      if (t !== cb) { cb.checked = !cb.checked; e.preventDefault(); }
      box.classList.toggle("selected", cb.checked);
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
      if (input.name === "habit_direction") { setDirection(input.value); }
      queueSave();
      updateProgress();
    }
  });

  function onEdit() { queueSave(); updateProgress(); }
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

  /* ── Collect ─────────────────────────────────────── */
  function collect() {
    var data = {};
    new FormData(form).forEach(function(value, key) {
      if (key === "website") { return; }
      if (String(value).trim()) { data[key] = String(value).trim(); }
    });
    var area = document.getElementById("area");
    if (area.value) { data.area_label = area.options[area.selectedIndex].text; }
    return data;
  }

  /* ── Save / restore ──────────────────────────────── */
  var submitted = false;
  var saveTimer = null;
  var saveOk = true;
  var saveWarned = false;
  function save(silent) {
    if (submitted) { return; }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(collect()));
      saveOk = true;
      if (!silent) { showMessage("info", "Saved in this browser. Close the page and come back any time."); }
    } catch (err) {
      saveOk = false;
      if (!silent || !saveWarned) {
        saveWarned = true;
        showMessage("error", "This browser won't let me save. Keep the page open until you submit.");
      }
    }
  }
  function queueSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(function() { save(true); }, 800);
  }

  function restore() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch (err) { saved = null; }
    if (saved) {
      Object.keys(saved).forEach(function(key) {
        form.querySelectorAll("[name=\"" + key + "\"]").forEach(function(el) {
          if (el.type === "checkbox") {
            el.checked = saved[key] === el.value;
            el.closest(".gg-apply-checkbox-option").classList.toggle("selected", el.checked);
          } else if (el.type === "radio") {
            if (el.value === saved[key]) {
              el.checked = true;
              el.closest(".gg-apply-radio-option").classList.add("selected");
              if (el.name === "habit_direction") { setDirection(el.value); }
            }
          } else {
            el.value = saved[key];
          }
        });
      });
      form.querySelectorAll(".gg-sr-deeper").forEach(function(mod) {
        var used = Array.prototype.some.call(mod.querySelectorAll("[name]"), function(el) { return !!saved[el.name]; });
        if (used) { mod.open = true; }
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
  function formatSubmission(d) {
    var L = [];
    function add(label, v) { if (v) { L.push("- " + label + ": " + v); } }
    var stop = d.habit_direction === "reduce";
    L.push("# Season Review " + SEASON + ": " + d.name);
    L.push("Email: " + d.email);
    L.push("Submitted: " + new Date().toISOString());
    L.push("");
    L.push("## " + SEASON);
    add("Proudest", d.proudest);
    add("Main goal", d.last_goal);
    add("Result", d.last_goal_result);
    add("Decided by", d.last_goal_why);
    L.push("");
    L.push("## " + (SEASON + 1));
    add("Goal", d.outcome_goal);
    add("Measured by", d.outcome_measure);
    add("Why", d.outcome_why);
    add("Main race", [d.a_race, d.a_race_date].filter(Boolean).join(" "));
    add("Inner obstacle", d.inner_obstacle);
    add("If-then", d.obstacle_plan);
    add("Area", d.area_label);
    add(stop ? "STOP" : "START", d.habit);
    add(stop ? "What changes" : "When/where", d.habit_when);
    add(stop ? "Instead" : "Smallest version", d.habit_min);
    L.push("");
    L.push("## Their year");
    add("Hours/week", d.hours_next);
    add("Constraints", d.constraints);
    L.push("");
    L.push("## Coaching");
    add("Wants", d.next_season_plan);
    add("Keep/change/else", d.coach_notes);
    var deep = [];
    function dadd(label, v) { if (v) { deep.push("- " + label + ": " + v); } }
    if (d.ideal_season) { deep.push("### The season they want (" + d.ideal_season.split(/\s+/).filter(Boolean).length + " words)"); deep.push(d.ideal_season); }
    if (d.avoid_season) { deep.push("### The season to avoid"); deep.push(d.avoid_season); }
    dadd("Moment", d.moment_1);
    dadd("  their part", d.moment_1_role);
    dadd("  what it changed", d.moment_1_impact);
    dadd("Another moment", d.moment_2);
    dadd("Strength", d.strength);
    dadd("  when/use", d.strength_when);
    dadd("Fault", d.fault);
    dadd("  when/fix", d.fault_when);
    dadd("Wants that fight the goal", d.competing_wants);
    dadd("Would have to start wanting", d.want_to_want);
    var missing = [["dead_obvious", "set time/place"], ["dead_attractive", "something to look forward to"], ["dead_easy", "easy to start"], ["dead_satisfying", "visible payoff"]]
      .filter(function(p) { return d[p[0]]; }).map(function(p) { return p[1]; });
    if (d.dead_habit) { dadd("Habit that died", d.dead_habit + (missing.length ? " (missing: " + missing.join(", ") + ")" : "")); }
    if (d.why_2 || d.why_3) { dadd("Why, deeper", [d.outcome_why, d.why_2, d.why_3].filter(Boolean).join(" -> ")); }
    if (deep.length) {
      L.push("");
      L.push("## Went deeper");
      deep.forEach(function(x) { L.push(x); });
    }
    L.push("");
    L.push("## Flags");
    var flags = [];
    if (d.last_goal_result === "none") { flags.push("No clear goal last season"); }
    if (d.a_race && /^(3-5|5-7)$/.test(d.hours_next || "")) { flags.push("Main race on " + d.hours_next + " hrs/week: check the fit"); }
    if (d.constraints && !/^(nothing|none|no)\.?$/i.test(d.constraints)) { flags.push("Constraint: " + d.constraints); }
    L.push(flags.length ? flags.map(function(f) { return "- " + f; }).join("\n") : "- none");
    L.push("");
    L.push("## Endure draft (JSON, not import-ready: needs athlete id and frequency rules)");
    L.push(JSON.stringify(toEndure(d)));
    return L.join("\n");
  }

  /* goal -> area -> habit, in the shape of the Endure goal tree */
  function toEndure(d) {
    return {
      version: 3, season: SEASON, email: d.email,
      goals: {
        "review:ROOT": {
          horizon: "season", title: d.outcome_goal || null,
          metric: { source_type: "manual", description: d.outcome_measure || null },
          why: d.outcome_why || null,
          obstacle: d.inner_obstacle || null, obstacle_plan: d.obstacle_plan || null,
          race: d.a_race ? { name: d.a_race, date: d.a_race_date || null } : null
        },
        "review:AREA": { horizon: "season", parent: "review:ROOT", area: d.area || null, title: d.area_label || null }
      },
      goal_actions: {
        "review:H1": {
          direction: d.habit_direction || "do", title: d.habit || null, goal: "review:AREA",
          design: { obvious: d.habit_when || null, easy: d.habit_min || null },
          scores: null
        }
      }
    };
  }

  /* ── Submit ──────────────────────────────────────── */
  form.addEventListener("submit", function(e) {
    e.preventDefault();
    var btn = document.getElementById("submit-btn");
    if (btn.disabled) { return; }
    if (form.querySelector("[name=website]").value) {
      showMessage("error", "Something filled a hidden field. Clear your browser's autofill for this page and try again.");
      return;
    }
    var d = collect();
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

    var ctrl = typeof AbortController === "function" ? new AbortController() : null;
    var killer = setTimeout(function() { if (ctrl) { ctrl.abort(); } }, 25000);
    fetch(SUBMIT_URL, { method: "POST", body: payload, headers: { "Accept": "application/json" }, signal: ctrl ? ctrl.signal : undefined })
      .then(function(r) {
        return r.json().catch(function() { return {}; }).then(function(res) {
          if (!r.ok || String(res.success) !== "true") { throw new Error(res.message || ("HTTP " + r.status)); }
        });
      })
      .then(function() {
        clearTimeout(killer);
        submitted = true;
        clearTimeout(saveTimer);
        try { localStorage.removeItem(STORAGE_KEY); } catch (err) { /* ignore */ }
        ga4("season_review_submitted", { deep_modules: form.querySelectorAll(".gg-sr-deeper[open]").length });
        showMessage("success", "Got it. I'll read it properly and come back with the plan for " + (SEASON + 1) + ".");
        btn.textContent = "Submitted";
      })
      .catch(function(err) {
        clearTimeout(killer);
        showMessage("error", saveOk
          ? "That didn't go through. Your answers are saved in this browser. Try again, or email __EMAIL__."
          : "That didn't go through, and this browser can't save. Keep this page open and try again, or email __EMAIL__.");
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
      {build_section_you()}
      {build_section_past()}
      {build_section_goal()}
      {build_section_obstacle()}
      {build_section_habit()}
      {build_section_year()}
      {build_section_me()}
      {build_deep_modules()}
      {build_submit_buttons()}
    </form>
  </div>
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
