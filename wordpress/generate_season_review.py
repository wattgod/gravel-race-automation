#!/usr/bin/env python3
"""
Generate the Gravel God Season Review at /coaching/season-review/.

A close-out questionnaire sent to existing athletes at the end of a season.
It looks and behaves like the coaching intake (/coaching/apply/) — same
card, progress bar, save/resume, and brand tokens — and reuses that page's
CSS so the two can't drift apart.

Every page is an MVP review everyone can finish (a short required core)
plus optional, collapsed "go deeper" modules drawn from Self Authoring
(Matti, Sep 22 2026: "People need an MVP review and goal-setting
questionnaire, with the options to spend much more time and go deep").
The question sets live in season_review_variants.py as data:

  standard  /coaching/season-review/          the version after three sol rounds
  claude    /coaching/season-review/claude/   warm, plain, one idea per question
  matti     /coaching/season-review/matti/    Matti's coaching voice
  five      /coaching/season-review/five/     five questions, ~5 minutes

What the research supports, and every variant keeps: judging last season
against the goal actually set, one measurable goal, and naming an inner
obstacle with an if-then plan (Oettingen's WOOP; Gollwitzer & Sheeran
2006). None of it is tested on athletes. Training numbers (FTP etc.) are
never asked; they come from data.

Links can be personalised: ?name=Ada&email=ada@example.com prefills both.

Submission goes to formsubmit.co (already activated for
gravelgodcoaching@gmail.com on this site). The email is built from the
page itself (question, then answer, in order), followed by flags for the
coach and a draft JSON block in the shape of the Endure goal tree.

Usage:
    python generate_season_review.py                 # every variant
    python generate_season_review.py --variant matti
    python generate_season_review.py --output-dir ./output
"""

import argparse
import html
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
from season_review_variants import SEASON, VARIANTS

OUTPUT_DIR = Path(__file__).parent / "output"

FORMSUBMIT_EMAIL = "gravelgodcoaching@gmail.com"
FORMSUBMIT_URL = f"https://formsubmit.co/ajax/{FORMSUBMIT_EMAIL}"


def page_path(slug: str) -> str:
    return "/coaching/season-review/" + ("" if slug == "standard" else f"{slug}/")


def output_name(slug: str) -> str:
    return "season-review.html" if slug == "standard" else f"season-review-{slug}.html"


# ── Field rendering ───────────────────────────────────────────


def _attr(value: str) -> str:
    return html.escape(value, quote=True)


def _req(field) -> str:
    return ' <span class="gg-apply-required">*</span>' if field.get("req") else ""


def _label(field, for_id: bool = True) -> str:
    if not field.get("label"):
        return ""
    swap = field.get("swap", {})
    data = "".join(
        f' data-lbl-{d}="{_attr(v["label"])}"' for d, v in swap.items() if "label" in v
    )
    target = f' for="{field["name"]}"' if for_id else ""
    return f'<label class="gg-apply-label"{target}{data}>{field["label"]}{_req(field)}</label>'


def _control(field) -> str:
    name, kind = field["name"], field["kind"]
    req = " required" if field.get("req") else ""
    ph = f' placeholder="{field["ph"]}"' if field.get("ph") else ""
    swap = field.get("swap", {})
    ph_data = "".join(f' data-ph-{d}="{_attr(v["ph"])}"' for d, v in swap.items() if "ph" in v)
    if kind in ("text", "email", "date"):
        auto = f' autocomplete="{field["auto"]}"' if field.get("auto") else ""
        return f'<input type="{kind}" id="{name}" name="{name}"{req}{ph}{ph_data}{auto}>'
    if kind == "area":
        return f'<textarea id="{name}" name="{name}" rows="{field.get("rows", 3)}"{req}{ph}></textarea>'
    if kind == "select":
        opts = '<option value="">Select...</option>' + "".join(
            f'<option value="{_attr(v)}">{t}</option>' for v, t in field["options"]
        )
        return f'<select id="{name}" name="{name}"{req}>{opts}</select>'
    if kind == "radio":
        lift = field.get("lift")
        lift_attr = (
            f' data-lift-when="{lift["when"]}" data-lift="{",".join(lift["fields"])}"' if lift else ""
        )
        opts = "".join(
            f'<label class="gg-apply-radio-option"><input type="radio" name="{name}" value="{o[0]}"'
            f'{req if i == 0 else ""}><div class="gg-apply-radio-label"><div class="gg-apply-radio-title">{o[1]}</div>'
            + (f'<div class="gg-apply-radio-desc">{o[2]}</div>' if len(o) > 2 else "")
            + "</div></label>"
            for i, o in enumerate(field["options"])
        )
        layout = "" if any(len(o) > 2 for o in field["options"]) else " gg-apply-radio-horizontal"
        return f'<div class="gg-apply-radio-group{layout}" data-radio="{name}"{lift_attr}>{opts}</div>'
    if kind == "checks":
        opts = "".join(
            f'<label class="gg-apply-checkbox-option"><input type="checkbox" name="{n}" value="yes">'
            f'<span class="gg-apply-checkbox-label">{t}</span></label>'
            for n, t in field["options"]
        )
        return f'<div class="gg-apply-checkbox-vertical">{opts}</div>'
    if kind == "timed":
        return f'<textarea id="{name}" name="{name}" rows="{field.get("rows", 10)}" class="gg-sr-long"></textarea>'
    raise ValueError(f"unknown field kind {kind!r}")


WHY_NAMES = ["outcome_why", "why_2", "why_3", "why_4", "why_5"]


def render_why_chain(field) -> str:
    """Five whys. Each box appears once the one before has an answer, and
    its question quotes that answer back (filled in by the page script)."""
    groups = []
    for i, name in enumerate(WHY_NAMES):
        label = field["label"] if i == 0 else "And why does that matter?"
        req = " required" if field.get("req") and i == 0 else ""
        star = ' <span class="gg-apply-required">*</span>' if req else ""
        hidden = " hidden" if i else ""
        groups.append(
            f'<div class="gg-apply-group gg-sr-why" data-q="{_attr(_strip_tags(html.unescape(label)))}" data-why="{i}"{hidden}>'
            f'<label class="gg-apply-label" for="{name}">{label}{star}</label>'
            f'<input type="text" id="{name}" name="{name}"{req}'
            + (f' placeholder="{field["ph"]}"' if i == 0 and field.get("ph") else "")
            + "></div>"
        )
    return f'<div class="gg-sr-whys">{"".join(groups)}</div>'


def render_field(field, context_title: str = "") -> str:
    if field["kind"] == "whychain":
        return render_why_chain(field)
    if field["kind"] == "pair":
        inner = "".join(render_field(f, context_title) for f in field["fields"])
        return f'<div class="gg-apply-inline">{inner}</div>'
    # data-q is the question as it appears in the coach's email
    q = field.get("label") or context_title
    head = _label(field, for_id=field["kind"] not in ("radio", "checks"))
    if field["kind"] == "timed":
        head = (
            f'<div class="gg-sr-label-row">{head}'
            f'<button type="button" class="gg-sr-timer" data-minutes="{field["minutes"]}" data-target="{field["name"]}">'
            f'Start {field["minutes"]}:00</button></div>'
        )
    return (
        f'<div class="gg-apply-group" data-q="{_attr(html.unescape(_strip_tags(q)))}">'
        f"{head}{_control(field)}</div>"
    )


def _strip_tags(s: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", s)


def render_sections(variant) -> str:
    out, n = [], 0
    for sec in variant["sections"]:
        if sec.get("numbered", True):
            n += 1
            title = f"{n}. {sec['title']}"
        else:
            title = sec["title"]
        fields = "".join(render_field(f, sec["title"]) for f in sec["fields"])
        sub = f'<p class="gg-apply-section-sub">{sec["sub"]}</p>' if sec.get("sub") else ""
        out.append(f'<div class="gg-apply-section-title">{title}</div>{sub}\n      {fields}')
    return "\n      ".join(out)


def render_modules(variant) -> str:
    mods = []
    for m in variant["modules"]:
        fields = "".join(render_field(f, m["title"]) for f in m["fields"])
        mods.append(
            f'<details class="gg-sr-deeper" data-module="{m["key"]}">'
            f'<summary>{m["title"]} <span class="gg-apply-optional">({m["minutes"]})</span></summary>'
            f"{fields}</details>"
        )
    return f'<div class="gg-sr-part">{variant["deep_title"]}</div>\n      ' + "\n      ".join(mods)


# ── Page pieces ───────────────────────────────────────────────


def build_nav() -> str:
    return get_site_header_html(active="services") + f'''
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <a href="{SITE_BASE_URL}/coaching/">Coaching</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">Season Review</span>
  </div>'''


def build_header(variant) -> str:
    return f'''<div class="gg-apply-header">
    <div class="gg-apply-badge">{variant["badge"]}</div>
    <h1>{variant["h1"]}</h1>
    <p>{variant["intro"]}</p>
  </div>'''


def build_progress_bar() -> str:
    return '''<div class="gg-apply-progress">
    <div class="gg-apply-progress-bar">
      <div class="gg-apply-progress-fill" id="progress-fill"></div>
    </div>
    <div class="gg-apply-progress-text" id="progress-text">0% complete</div>
  </div>'''


def build_submit_buttons(variant, btn_id: str, lead: str = "") -> str:
    lead_html = f'<p class="gg-sr-done">{lead}</p>' if lead else ""
    return f'''{lead_html}<div class="gg-apply-actions">
        <button type="button" class="gg-apply-save-btn gg-sr-save">Save Progress</button>
        <button type="submit" class="gg-apply-submit-btn gg-sr-submit" id="{btn_id}">{variant["submit"]}</button>
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
.gg-sr-done {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-secondary-brown);
  margin: var(--gg-spacing-xl) 0 0;
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
.gg-sr-why + .gg-sr-why { padding-left: var(--gg-spacing-lg); border-left: 3px solid var(--gg-color-teal); }
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


def build_season_review_js(variant) -> str:
    js = r'''<script>
(function() {
  "use strict";

  var STORAGE_KEY = "__STORAGE_KEY__";
  var SUBMIT_URL = "__SUBMIT_URL__";
  var SEASON = __SEASON__;
  var VARIANT = "__VARIANT__";
  var SUCCESS = "__SUCCESS__";
  var SUBMIT_LABEL = "__SUBMIT_LABEL__";

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
      var group = el.closest("[data-q]");
      if (group) { group.setAttribute("data-q", el.getAttribute("data-lbl-" + dir)); }
    });
  }

  /* ── Radio side effects: styling, start/stop, lifted requirements ── */
  function radioChanged(input) {
    form.querySelectorAll("input[name=\"" + input.name + "\"]").forEach(function(inp) {
      inp.closest(".gg-apply-radio-option").classList.toggle("selected", inp.checked);
    });
    if (input.name === "habit_direction") { setDirection(input.value); }
    var group = input.closest("[data-lift]");
    if (group) {
      var lifted = input.value === group.getAttribute("data-lift-when");
      group.getAttribute("data-lift").split(",").forEach(function(id) {
        var el = document.getElementById(id);
        if (!el) { return; }
        el.required = !lifted;
        var star = form.querySelector("label[for=" + id + "] .gg-apply-required");
        if (star) { star.hidden = lifted; }
      });
    }
  }

  /* ── Writing timers (end time, so they survive a backgrounded tab) ── */
  var timer = null;
  var timerBtn = null;
  function resetTimer(btn) {
    btn.classList.remove("running", "done");
    btn.textContent = "Start " + btn.getAttribute("data-minutes") + ":00";
  }
  function toggleTimer(btn) {
    if (timer) {
      clearInterval(timer);
      timer = null;
      var same = timerBtn === btn;
      resetTimer(timerBtn);
      if (same) { return; }
    }
    timerBtn = btn;
    var endsAt = Date.now() + Number(btn.getAttribute("data-minutes")) * 60000;
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
      input.checked = true;
      radioChanged(input);
      queueSave();
      updateProgress();
    }
  });

  /* five whys: reveal the next box and quote the previous answer back */
  function updateWhys() {
    var groups = form.querySelectorAll(".gg-sr-why");
    for (var i = 1; i < groups.length; i++) {
      var prev = groups[i - 1].querySelector("input").value.trim();
      var shown = !groups[i - 1].hidden && prev.length > 0;
      var own = groups[i].querySelector("input").value.trim();
      groups[i].hidden = !(shown || own);
      if (prev) {
        var quoted = prev.length > 60 ? prev.slice(0, 57).trim() + "..." : prev;
        groups[i].querySelector("label").textContent = "Why does \u201c" + quoted + "\u201d matter?";
        groups[i].setAttribute("data-q", groups[i].querySelector("label").textContent);
      }
    }
  }

  function onEdit(e) {
    if (e && e.target.type === "radio" && e.target.checked) { radioChanged(e.target); }
    if (e && e.target.closest && e.target.closest(".gg-sr-why")) { updateWhys(); }
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

  /* ── Collect ─────────────────────────────────────── */
  function collect() {
    var data = {};
    new FormData(form).forEach(function(value, key) {
      if (key === "website") { return; }
      if (String(value).trim()) { data[key] = String(value).trim(); }
    });
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
            if (el.value === saved[key]) { el.checked = true; radioChanged(el); }
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
    updateWhys();
    /* personalised links: ?name=&email= */
    var params = new URLSearchParams(window.location.search);
    ["name", "email"].forEach(function(k) {
      var el = document.getElementById(k);
      if (params.get(k) && !el.value) { el.value = params.get(k); }
    });
    updateProgress();
  }

  form.querySelectorAll(".gg-sr-save").forEach(function(b) {
    b.addEventListener("click", function() { save(false); ga4("season_review_saved", { variant: VARIANT }); });
  });
  window.addEventListener("beforeunload", function() { save(true); });

  /* ── The email: the page's own questions, in order, with answers ── */
  function answerOf(group) {
    var vals = [];
    group.querySelectorAll("input, select, textarea").forEach(function(el) {
      if (el.type === "radio" || el.type === "checkbox") {
        if (el.checked) {
          var t = el.closest("label").querySelector(".gg-apply-radio-title, .gg-apply-checkbox-label");
          vals.push((t || el.closest("label")).textContent.trim());
        }
      } else if (el.tagName === "SELECT") {
        if (el.value) { vals.push(el.options[el.selectedIndex].text); }
      } else if (el.value.trim()) {
        vals.push(el.value.trim());
      }
    });
    return vals.join(", ");
  }

  function formatSubmission(d) {
    var L = [];
    L.push("# Season Review " + SEASON + " [" + VARIANT + "]: " + d.name);
    L.push("Email: " + d.email);
    L.push("Submitted: " + new Date().toISOString());
    var heading = null, printed = null;
    form.querySelectorAll(".gg-apply-section-title, .gg-sr-deeper summary, [data-q]").forEach(function(el) {
      if (!el.hasAttribute("data-q")) { heading = el.firstChild.textContent.trim(); return; }
      if (el.closest("[data-q]") !== el) { return; }
      var a = answerOf(el);
      if (!a || el.querySelector("#name, #email")) { return; }
      if (heading !== null) { L.push(""); L.push("## " + heading); printed = heading; heading = null; }
      var q = el.getAttribute("data-q");
      if (printed && printed.replace(/^\d+\.\s*/, "") === q.replace(/^\d+\.\s*/, "")) { L.push(a); return; }
      if (a.length > 140 || a.indexOf("\n") !== -1) { L.push("### " + q); L.push(a); }
      else { L.push("- " + q + " " + a); }
    });
    L.push("");
    L.push("## Flags");
    var flags = [];
    if (d.last_goal_result === "none") { flags.push("No clear goal last season"); }
    if (d.outcome_scary === "no") { flags.push("Goal doesn't scare them"); }
    if (d.next_season_plan === "break") { flags.push("Wants a break"); }
    if (d.energy === "tired" || d.energy === "break") { flags.push("Energy: " + d.energy); }
    if (d.constraints && !/^(nothing|none|no|n\/a)\.?$/i.test(d.constraints)) { flags.push("Constraint: " + d.constraints); }
    if (!d.outcome_measure && VARIANT !== "five") { flags.push("No measure for the goal"); }
    if (d.outcome_why && !d.why_2) { flags.push("Whys stop at one level"); }
    if (d.missed_workout === "spiral" || d.missed_workout === "disappear") { flags.push("Misses a workout -> " + d.missed_workout); }
    if (d.goal_audience === "nobody") { flags.push("Nobody knows the goal yet"); }
    L.push(flags.length ? flags.map(function(f) { return "- " + f; }).join("\n") : "- none");
    L.push("");
    L.push("## Endure draft (JSON, not import-ready: needs athlete id and frequency rules)");
    L.push(JSON.stringify(toEndure(d)));
    return L.join("\n");
  }

  /* goal -> area -> habit, in the shape of the Endure goal tree */
  function toEndure(d) {
    var areaSel = document.getElementById("area");
    return {
      version: 4, variant: VARIANT, season: SEASON, email: d.email,
      goals: {
        "review:ROOT": {
          horizon: "season", title: d.outcome_goal || null,
          metric: { source_type: "manual", description: d.outcome_measure || null },
          why: [d.outcome_why, d.why_2, d.why_3, d.why_4, d.why_5].filter(Boolean),
          not_yet: d.not_yet || null,
          obstacle: d.inner_obstacle || d.obstacle_combo || null, obstacle_plan: d.obstacle_plan || null,
          race: d.a_race ? { name: d.a_race, date: d.a_race_date || null } : null
        },
        "review:AREA": d.area ? { horizon: "season", parent: "review:ROOT", area: d.area,
          title: areaSel ? areaSel.options[areaSel.selectedIndex].text : null } : null
      },
      goal_actions: d.habit ? {
        "review:H1": {
          direction: d.habit_direction || "do", title: d.habit, goal: d.area ? "review:AREA" : "review:ROOT",
          design: { obvious: d.habit_when || null, easy: d.habit_min || null }, scores: null
        }
      } : {}
    };
  }

  /* ── Submit ──────────────────────────────────────── */
  function setButtons(disabled, label) {
    form.querySelectorAll(".gg-sr-submit").forEach(function(b) { b.disabled = disabled; b.textContent = label; });
  }

  form.addEventListener("submit", function(e) {
    e.preventDefault();
    if (form.querySelector(".gg-sr-submit").disabled) { return; }
    if (form.querySelector("[name=website]").value) {
      showMessage("error", "Something filled a hidden field. Clear your browser's autofill for this page and try again.");
      return;
    }
    var d = collect();
    setButtons(true, "Submitting...");
    save(true);

    var payload = new FormData();
    payload.append("_subject", "Season Review " + SEASON + " [" + VARIANT + "]: " + d.name);
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
        ga4("season_review_submitted", { variant: VARIANT, deep_modules: form.querySelectorAll(".gg-sr-deeper[open]").length });
        showMessage("success", SUCCESS);
        setButtons(true, "Submitted");
      })
      .catch(function(err) {
        clearTimeout(killer);
        showMessage("error", saveOk
          ? "That didn't go through. Your answers are saved in this browser. Try again, or email __EMAIL__."
          : "That didn't go through, and this browser can't save. Keep this page open and try again, or email __EMAIL__.");
        setButtons(false, SUBMIT_LABEL);
        ga4("season_review_error", { variant: VARIANT, message: String(err.message || "unknown").slice(0, 80) });
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
  ga4("season_review_view", { variant: VARIANT });
})();
</script>'''
    js_str = lambda s: html.unescape(s).replace("\\", "\\\\").replace('"', '\\"')
    return (
        js.replace("__STORAGE_KEY__", f"season_review_{SEASON}_{variant['slug']}_v3")
        .replace("__SUBMIT_URL__", FORMSUBMIT_URL)
        .replace("__SEASON__", str(SEASON))
        .replace("__VARIANT__", variant["slug"])
        .replace("__SUCCESS__", js_str(variant["success"]))
        .replace("__SUBMIT_LABEL__", js_str(variant["submit"]))
        .replace("__EMAIL__", FORMSUBMIT_EMAIL)
    )


# ── Page assembly ─────────────────────────────────────────────


def generate_season_review_page(slug: str = "standard", external_assets=None) -> str:
    variant = VARIANTS[slug]
    page_css = external_assets["css_tag"] if external_assets else get_page_css()
    title = f"Season Review {SEASON} | Gravel God"
    url = SITE_BASE_URL + page_path(slug)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="robots" content="noindex, nofollow">
  <link rel="canonical" href="{url}">
  <meta property="og:title" content="{title}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{url}">
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
    {build_header(variant)}
    {build_progress_bar()}
    <div id="message" class="gg-apply-message hidden"></div>
    <form id="season-form" class="gg-apply-form-card">
      <input type="text" name="website" class="gg-apply-honeypot" tabindex="-1" autocomplete="off">
      {render_sections(variant)}
      {build_submit_buttons(variant, "submit-btn", variant["done"])}
      {render_modules(variant)}
      {build_submit_buttons(variant, "submit-btn-2")}
    </form>
  </div>
  {build_footer()}
  {build_season_review_js(variant)}
  <script>{get_site_header_js()}</script>
  {get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate the season review pages")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument("--variant", choices=sorted(VARIANTS), help="one variant (default: all)")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    assets = write_shared_assets(out_dir)

    for slug in [args.variant] if args.variant else VARIANTS:
        html_content = generate_season_review_page(slug, external_assets=assets)
        out_path = out_dir / output_name(slug)
        out_path.write_text(html_content, encoding="utf-8")
        print(f"Generated {out_path} ({len(html_content):,} bytes) -> {page_path(slug)}")


if __name__ == "__main__":
    main()
