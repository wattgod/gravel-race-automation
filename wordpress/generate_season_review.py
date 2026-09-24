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
from brand_tokens import get_favicon_head_snippet, get_ga4_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html, get_site_header_js
from cookie_consent import get_consent_banner_html
from generate_coaching_apply import build_apply_css
from season_review_variants import SEASON, VARIANTS

OUTPUT_DIR = Path(__file__).parent / "output"

FORMSUBMIT_EMAIL = "gravelgodcoaching@gmail.com"
FORMSUBMIT_URL = f"https://formsubmit.co/ajax/{FORMSUBMIT_EMAIL}"

# The Cloudflare lead worker. Variants that post here get Matti a notification
# in his inbox (FormSubmit mail is filtered to a label and skips it) and their
# answers stored against the lead, where scripts can file them.
LEAD_WORKER_URL = "https://fueling-lead-intake.gravelgodcoaching.workers.dev"
WORKER_SOURCES = {"athlete": "athlete_review", "goal_2027": "goal_2027"}


def page_path(slug: str) -> str:
    variant = VARIANTS.get(slug, {})
    if variant.get("path"):
        return variant["path"]
    return "/coaching/season-review/" + ("" if slug == "standard" else f"{slug}/")


def output_name(slug: str) -> str:
    variant = VARIANTS.get(slug, {})
    if variant.get("output"):
        return variant["output"]
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
    if kind == "hidden":
        return f'<input type="hidden" id="{name}" name="{name}">'
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
    if field["kind"] == "hidden":
        return _control(field)
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
        # data-section-n: the goal_section GA4 event (fired on real scroll,
        # never a timer — see build_season_review_js) reads this to report
        # which numbered section a visitor actually reached.
        if sec.get("numbered", True):
            n += 1
            title = f"{n}. {sec['title']}"
            # Placed before class=, not after, so the existing
            # `gg-apply-section-title">{n}. ` string match (tests, and the
            # coach's email formatter) keeps working unchanged.
            num_attr = f'data-section-n="{n}" '
        else:
            title = sec["title"]
            num_attr = ""
        fields = "".join(render_field(f, sec["title"]) for f in sec["fields"])
        sub = f'<p class="gg-apply-section-sub">{sec["sub"]}</p>' if sec.get("sub") else ""
        out.append(f'<div {num_attr}class="gg-apply-section-title">{title}</div>{sub}\n      {fields}')
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


def build_results(variant) -> str:
    """Shown after submitting: the poster first, the offer underneath it."""
    results, offer = variant.get("results"), variant.get("offer")
    if not results:
        return ""
    plans_html = "".join(
        f'<div class="gg-sr-offer-plan">'
        f'<p class="gg-sr-offer-plan-price">{plan["price"]}</p>'
        f'<a class="gg-sr-offer-cta{"" if plan["key"] == "race" else " gg-sr-offer-cta-secondary"}" '
        f'href="{plan["cta_href"]}" data-offer-cta data-plan-type="{plan["key"]}">{plan["cta"]}</a>'
        f"</div>"
        for plan in offer.get("plans", [])
    ) if offer else ""
    cards = "".join(
        f'<div class="gg-sr-offer" data-offer-variant="{v["key"]}" hidden>'
        f'<div class="gg-sr-offer-kicker">{offer["kicker"]}</div>'
        f'<h3 class="gg-sr-offer-h">{v["h"]}</h3>'
        f'<p class="gg-sr-offer-p">{v["p"]}</p>'
        f'<div class="gg-sr-offer-plans">{plans_html}</div>'
        f'<p class="gg-sr-offer-terms">{offer["terms"]}</p>'
        f'<a class="gg-sr-offer-decline" href="#" data-offer-decline>{offer["decline"]}</a>'
        f"</div>"
        for v in offer["variants"]
    ) if offer else ""
    return f'''<section id="results" class="gg-sr-results" hidden>
    <div class="gg-sr-results-head">
      <h2>{results["title"]}</h2>
      <p>{results["lead"]}</p>
    </div>
    <canvas id="poster-canvas" width="1080" height="1440" class="gg-sr-poster" aria-label="Your 2027 goal poster"></canvas>
    <a id="poster-download" class="gg-sr-download" href="#" download="2027-goal-poster.png">{results["download"]}</a>
    {cards}
  </section>'''


def build_submit_buttons(variant, btn_id: str, lead: str = "") -> str:
    lead_html = f'<p class="gg-sr-done">{lead}</p>' if lead else ""
    return f'''{lead_html}<div class="gg-apply-actions">
        <button type="button" class="gg-apply-save-btn gg-sr-save">Save Progress</button>
        <button type="submit" class="gg-apply-submit-btn gg-sr-submit" id="{btn_id}">{variant["submit"]}</button>
      </div>'''


def build_footer(variant=None) -> str:
    slug = (variant or {}).get("slug", "")
    if (variant or {}).get("transport") == "worker":
        # a stranger, not a client: say exactly what happens and nothing more
        return f'''<div class="gg-apply-confidential-wrap">
    <p class="gg-apply-confidential">Your answers are stored so I can make your poster and email it to you, and I&#39;ll send one short check-in a week later. Unsubscribe from either with the link in the email. Nothing is sold or shared; the <a href="/privacy/">Privacy Policy</a> has the detail. Your draft stays in this browser until you submit. Questions? Email {FORMSUBMIT_EMAIL}</p>
  </div>
  ''' + get_mega_footer_html()
    if slug in WORKER_SOURCES:
        route = ("They come straight to me and are stored with your file. "
                 "The email copy is sent through FormSubmit, a form service "
                 "that keeps a copy for 30 days.")
    else:
        route = ("They reach me by email through FormSubmit, a form service that "
                 "keeps a copy for 30 days.")
    return f'''<div class="gg-apply-confidential-wrap">
    <p class="gg-apply-confidential">Your answers, including health information you choose to share, are used to coach you as described in the <a href="/privacy/">Privacy Policy</a>. {route} Drafts are saved only in this browser until you submit. Questions? Email {FORMSUBMIT_EMAIL}</p>
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

/* Results: the poster first, the offer under it */
.gg-sr-results {
  /* the site header is sticky: without this the heading lands under it */
  scroll-margin-top: calc(var(--gg-header-height, 90px) + 24px);
  border: 3px solid var(--gg-color-near-black);
  background: var(--gg-color-white);
  padding: var(--gg-spacing-xl);
  margin-bottom: var(--gg-spacing-lg);
}
.gg-sr-results-head h2 {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-2xl);
  font-weight: var(--gg-font-weight-bold);
  margin: 0 0 var(--gg-spacing-xs);
}
.gg-sr-results-head p {
  font-family: var(--gg-font-editorial);
  color: var(--gg-color-secondary-brown);
  margin: 0 0 var(--gg-spacing-lg);
  max-width: 46ch;
}
.gg-sr-poster {
  display: block;
  width: 100%;
  height: auto;
  border: 3px solid var(--gg-color-near-black);
  background: var(--gg-color-near-black);
}
.gg-sr-download {
  display: block;
  text-align: center;
  margin-top: var(--gg-spacing-md);
  padding: var(--gg-spacing-md);
  background: var(--gg-color-ink, var(--gg-color-near-black));
  color: var(--gg-color-white);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  text-decoration: none;
  border: 3px solid var(--gg-color-near-black);
}
.gg-sr-download:hover { background: var(--gg-color-white); color: var(--gg-color-near-black); }
.gg-sr-offer {
  border: 3px solid var(--gg-color-near-black);
  background: var(--gg-color-warm-paper);
  padding: var(--gg-spacing-lg);
  margin-top: var(--gg-spacing-2xl);
}
.gg-sr-offer-kicker {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wider);
  text-transform: uppercase;
  color: var(--gg-color-teal);
}
.gg-sr-offer-h {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-xl);
  font-weight: var(--gg-font-weight-bold);
  line-height: 1.1;
  margin: var(--gg-spacing-xs) 0 var(--gg-spacing-sm);
}
.gg-sr-offer-p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-base);
  margin: 0 0 var(--gg-spacing-md);
}
.gg-sr-offer-terms {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  line-height: 1.6;
  color: var(--gg-color-secondary-brown);
  border-top: 2px solid var(--gg-color-tan);
  padding-top: var(--gg-spacing-sm);
  margin: 0 0 var(--gg-spacing-md);
}
.gg-sr-offer-cta {
  display: block;
  text-align: center;
  padding: var(--gg-spacing-md);
  background: var(--gg-color-teal);
  color: var(--gg-color-white);
  border: 3px solid var(--gg-color-near-black);
  font-family: var(--gg-font-data);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  text-decoration: none;
}
.gg-sr-offer-cta:hover { background: var(--gg-color-near-black); color: var(--gg-color-teal); }
.gg-sr-offer-plans {
  display: flex;
  gap: var(--gg-spacing-md);
  margin: 0 0 var(--gg-spacing-md);
}
.gg-sr-offer-plan {
  flex: 1;
}
.gg-sr-offer-plan-price {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  margin: 0 0 var(--gg-spacing-xs);
  text-align: center;
}
.gg-sr-offer-cta-secondary {
  background: var(--gg-color-warm-paper);
  color: var(--gg-color-near-black);
}
.gg-sr-offer-cta-secondary:hover { background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
.gg-sr-offer-decline {
  display: block;
  text-align: center;
  margin-top: var(--gg-spacing-sm);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  color: var(--gg-color-secondary-brown);
}

@media (max-width: 600px) {
  .gg-sr-label-row { flex-direction: column; align-items: stretch; }
  .gg-sr-timer { align-self: flex-start; }
  .gg-apply-actions { flex-direction: column-reverse; align-items: stretch; gap: var(--gg-spacing-sm); }
  .gg-apply-save-btn { margin-right: 0; }
  .gg-sr-offer-plans { flex-direction: column; }
}
</style>'''


# ── JavaScript ────────────────────────────────────────────────


def build_season_review_js(variant) -> str:
    js = r'''<script>
(function() {
  "use strict";

  var STORAGE_KEY = "__STORAGE_KEY__";
  var SUBMIT_URL = "__SUBMIT_URL__";
  var LEAD_SOURCE = "__LEAD_SOURCE__";  /* empty = email transport */
  var TRANSPORT = "__TRANSPORT__";      /* "worker" = no email backstop */
  var HAS_RESULTS = document.getElementById("results") !== null;
  var SEASON = __SEASON__;
  var VARIANT = "__VARIANT__";
  var SUCCESS = "__SUCCESS__";
  var SUCCESS_BY_EMAIL = "Got it — your answers came through by email. (My system had a wobble, so I'll file them by hand.)";
  var lastStored = false;
  var SUBMIT_LABEL = "__SUBMIT_LABEL__";

  var form = document.getElementById("season-form");

  /* Entry attribution (goals-2027-funnel-spec.md "Consent and analytics").
     The homepage poster wall and the race-page goal strip
     (generate_homepage.py, generate_neo_brutalist.py build_goal_strip) both
     link here as /goals/?src=home or /goals/?src=race&race=<slug>, firing
     goal_hero_click with { src } on the click that got the visitor here.
     Read the same two params so the rest of this page's funnel — and the
     lead itself — can be attributed to the same surface. Validated so a
     malformed value never lands in an event or a stored lead. */
  var ENTRY_SRC = (function() {
    var v = "";
    try { v = new URLSearchParams(window.location.search).get("src") || ""; } catch (e) {}
    return /^[a-z_]{1,24}$/.test(v) ? v : "";
  })();
  var RACE_SLUG = (function() {
    var v = "";
    try { v = new URLSearchParams(window.location.search).get("race") || ""; } catch (e) {}
    return /^[a-z0-9-]{1,80}$/.test(v) ? v : "";
  })();
  // Filled in from the lead-worker's response once this submission is
  // stored (see the fetch below) — the Season Plan CTA rides it into
  // /season-plan/?t=<token> so that page can read these saved answers.
  var POSTER_TOKEN = "";

  function ga4(name, params) {
    params = params || {};
    if (ENTRY_SRC) { params.src = ENTRY_SRC; }
    if (RACE_SLUG) { params.race_slug = RACE_SLUG; }
    if (typeof gtag === "function") { gtag("event", name, params); }
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

  /* Chosen before submit so it rides along with the answers — a test whose
     result lives only in analytics is a test you cannot read later. */
  var OFFER_VARIANT = (function() {
    var cards = document.querySelectorAll("[data-offer-variant]");
    if (!cards.length) { return ""; }
    return cards[Math.floor(Math.random() * cards.length)].getAttribute("data-offer-variant");
  })();

  var started = false;
  function onEdit(e) {
    if (!started) { started = true; ga4("goal_start", { variant: VARIANT }); }
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

  /* Set while restore() may still be driving a programmatic scroll (its
     own "Picked up where you left off" message smooth-scrolls into view),
     so that scroll is never mistaken for the genuine interaction that
     starts goal_section tracking. See startWatchingGoalSectionsOnce(). */
  var restoringDraft = false;

  function restore() {
    restoringDraft = true;
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
    ["name", "email", "athlete"].forEach(function(k) {
      var el = document.getElementById(k);
      if (el && params.get(k) && !el.value) { el.value = params.get(k); }
    });
    updateProgress();
    // A smooth scrollIntoView keeps firing scroll events for a few hundred
    // ms after this function returns, not just during it — clear the flag
    // once that animation has had time to finish, not synchronously.
    setTimeout(function() { restoringDraft = false; }, 800);
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

  /* The limiter interrogation, in the shape Endure stores it
     (endurelabs docs/specs/endure-loop-2026.md §3): answers verbatim. */
  var PROBES = [
    ["limiter", "Rate limiter: if we could fix exactly one thing before the A race, what wins the most time?"],
    ["limiter_evidence", "Rate limiter: what is the evidence?"],
    ["vices", "Admitted vices: what do you eat, drink or do that is costing you? What, how often, when."],
    ["skill_gaps", "Skill shortcomings: where do you lose races that fitness does not explain?"],
    ["week_breakers", "Life constraints: what breaks a training week, and how often?"],
    ["drop_order", "Drop order: when the week collapses, what goes first, second, third?"],
    ["pre_race_48h", "The 48 hours: walk me through the 48 hours before your last race."],
    ["admission", "The admission: what would you have to admit to yourself to hit this goal?"]
  ];

  function interrogation(d) {
    var asked = new Date().toISOString();
    return PROBES.filter(function(p) { return d[p[0]]; }).map(function(p) {
      return { probe: p[1], field: p[0], answer: d[p[0]], asked_at: asked, version: 1 };
    });
  }

  /* goal -> area -> habit, in the shape of the Endure goal tree */
  function toEndure(d) {
    var areaSel = document.getElementById("area");
    var probes = interrogation(d);
    var extras = {};
    if (probes.length) {
      extras.interrogation = probes;
      extras.athlete_ref = d.athlete || null;
    }
    if (d.limiter) {
      extras.limiter_evidence = [{
        v: 1, text: d.limiter, kind: d.limiter_kind || null,
        evidence: d.limiter_evidence || null, admitted_at: new Date().toISOString()
      }];
    }
    if (d.drop_order) { extras.drop_order = d.drop_order.split(/,|→|->|then/i).map(function(x) { return x.trim(); }).filter(Boolean); }
    return Object.assign(extras, {
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
    });
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

    var ctrl = typeof AbortController === "function" ? new AbortController() : null;
    var killer = setTimeout(function() { if (ctrl) { ctrl.abort(); } }, 25000);

    /* The worker is the record: it stores the answers and tells Matti. The
       email below is the backstop, so a failure on either side still lands
       the review somewhere — but we wait for both before claiming success. */
    var workerOk = Promise.resolve(false);
    if (LEAD_SOURCE) {
      var answers = {};
      Object.keys(d).forEach(function(k) {
        if (k !== "name" && k !== "email" && k !== "athlete" && typeof d[k] === "string") { answers[k] = d[k]; }
      });
      workerOk = fetch("__LEAD_WORKER_URL__", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({
          source: LEAD_SOURCE, brand: "gravelgod", email: d.email, name: d.name || "",
          athlete: d.athlete || "", goal_answers: answers, website: "",
          offer_variant: OFFER_VARIANT, race_slug: RACE_SLUG, entry_src: ENTRY_SRC
        }),
        signal: ctrl ? ctrl.signal : undefined
      }).then(function(r) {
        // Mission Control hands back this lead's poster_token so the
        // Season Plan CTA can link to /season-plan/?t=<token> and prefill
        // there — read it here. This chain must return the parse promise
        // (not fire-and-forget it) so workerOk — and therefore showResults(),
        // which builds the CTA from POSTER_TOKEN — waits for it; a sol
        // review caught the earlier version racing showResults() against
        // an unresolved r.json() and shipping the CTA with no ?t= most of
        // the time. A parse failure still resolves to r.ok, never blocking
        // success on the token.
        return r.json().then(function(body) {
          if (body && body.poster_token) { POSTER_TOKEN = body.poster_token; }
          return r.ok;
        }).catch(function() { return r.ok; });
      }).catch(function() { return false; });
    }

    var payload = new FormData();
    payload.append("_subject", "Season Review " + SEASON + " [" + VARIANT + "]: " + d.name);
    payload.append("_replyto", d.email);
    payload.append("_captcha", "false");
    payload.append("_template", "box");
    payload.append("name", d.name);
    payload.append("email", d.email);
    payload.append("message", formatSubmission(d));
    var mailOk = TRANSPORT === "worker" ? Promise.resolve(false)
      : fetch(SUBMIT_URL, { method: "POST", body: payload, headers: { "Accept": "application/json" }, signal: ctrl ? ctrl.signal : undefined })
      .then(function(r) {
        return r.json().catch(function() { return {}; }).then(function(res) {
          return r.ok && String(res.success) === "true";
        });
      }).catch(function() { return false; });

    Promise.all([workerOk, mailOk])
      .then(function(results) {
        if (!results[0] && !results[1]) { throw new Error("both transports failed"); }
        lastStored = results[0];
      })
      .then(function() {
        clearTimeout(killer);
        submitted = true;
        if (HAS_RESULTS) { showResults(d); }
        clearTimeout(saveTimer);
        // only drop the draft once it is stored somewhere that is not this browser
        if (lastStored || TRANSPORT !== "worker") {
          try { localStorage.removeItem(STORAGE_KEY); } catch (err) { /* ignore */ }
        }
        ga4("season_review_submitted", { variant: VARIANT, deep_modules: form.querySelectorAll(".gg-sr-deeper[open]").length });
        ga4("goal_submit", { variant: VARIANT });
        if (!HAS_RESULTS) { showMessage("success", lastStored ? SUCCESS : SUCCESS_BY_EMAIL); }
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

  /* ── The results screen ──────────────────────────── */
  var POSTER = { ink: "#1a1613", paper: "#f5efe6", white: "#ffffff", tan: "#d4c5b9",
                 teal: "#178079", gold: "#c9a92c", grey: "#7d695d" };

  /* The emailed poster trims to these lengths (services/goal_poster.py);
     match them so the two copies read the same. */
  function posterClean(value, limit) {
    return String(value || "").split(/\s+/).join(" ").trim().slice(0, limit);
  }

  function wrapText(ctx, text, maxWidth) {
    var words = String(text).split(/\s+/), lines = [], line = "";
    words.forEach(function(word) {
      var next = line ? line + " " + word : word;
      if (ctx.measureText(next).width <= maxWidth || !line) { line = next; }
      else { lines.push(line); line = word; }
    });
    if (line) { lines.push(line); }
    return lines;
  }

  /* Same design as the emailed poster (services/goal_poster.py): the goal
     shrinks to fit rather than running into the frame below it. */
  function drawPoster(d) {
    var canvas = document.getElementById("poster-canvas");
    var ctx = canvas.getContext("2d");
    var W = canvas.width, H = canvas.height, pad = 84, inner = W - pad * 2;
    ctx.fillStyle = POSTER.paper;
    ctx.fillRect(0, 0, W, H);
    ctx.textBaseline = "top";

    ctx.font = "700 26px 'Sometype Mono', monospace";
    ctx.fillStyle = POSTER.teal;
    ctx.fillText((SEASON + 1) + " \u00b7 GOAL FILE", pad, pad);
    ctx.fillStyle = POSTER.ink;
    ctx.textAlign = "right";
    ctx.fillText("GRAVEL GOD", W - pad, pad);
    ctx.textAlign = "left";
    ctx.font = "22px 'Sometype Mono', monospace";
    ctx.fillStyle = POSTER.grey;
    ctx.fillText("GRAVELGODCYCLING.COM", pad, H - pad - 20);

    /* Matti, Sep 23: the goal, the deepest why, the one or two daily
       habits that make the system, and the thing most likely to wreck it. */
    var habit = posterClean(d.habit, 120);
    if (habit && d.habit_when) { habit += " \u2014 " + posterClean(d.habit_when, 120); }
    var rows = [[d.habit_direction === "reduce" ? "STOPPING" : "EVERY DAY", habit],
                ["ALSO EVERY DAY", posterClean(d.habit_2, 150)],
                ["WATCH FOR", posterClean(d.inner_obstacle, 150)]]
      .filter(function(r) { return r[1]; })
      .map(function(r) {
        ctx.font = "30px 'Sometype Mono', monospace";
        return [r[0], wrapText(ctx, r[1], inner).slice(0, 2)];
      });
    var framed = rows.reduce(function(h, r) { return h + 56 + r[1].length * 38; }, 0);
    var frameTop = H - pad - 60 - framed;
    var y = frameTop;
    rows.forEach(function(row) {
      ctx.font = "700 24px 'Sometype Mono', monospace";
      ctx.fillStyle = POSTER.teal;
      ctx.fillText(row[0], pad, y);
      ctx.font = "30px 'Sometype Mono', monospace";
      ctx.fillStyle = POSTER.ink;
      row[1].forEach(function(line, i) { ctx.fillText(line, pad, y + 34 + i * 38); });
      y += 56 + row[1].length * 38;
    });

    /* The deepest why they gave: five whys exist to get past the first answer. */
    ctx.font = "italic 38px 'Source Serif 4', Georgia, serif";
    var why = posterClean([d.why_5, d.why_4, d.why_3, d.why_2, d.outcome_why]
      .filter(function(w) { return w && String(w).trim(); })[0], 200);
    var whyLines = why ? wrapText(ctx, "\u201c" + why + "\u201d", inner).slice(0, 3) : [];
    var whyHeight = whyLines.length * 50 + (whyLines.length ? 30 : 0);

    var labelY = pad + 200;
    var available = frameTop - whyHeight - labelY - 120;
    var goal = posterClean(d.outcome_goal, 180) || "[your goal]";
    if (!/[.!?]$/.test(goal)) { goal += "."; }
    var size = 104, goalLines = [];
    [104, 92, 80, 68, 58, 48].forEach(function(candidate) {
      if (goalLines.length && goalLines.length * Math.round(size * 1.06) <= available) { return; }
      size = candidate;
      ctx.font = "700 " + size + "px 'Source Serif 4', Georgia, serif";
      goalLines = wrapText(ctx, goal, inner);
    });

    ctx.font = "26px 'Sometype Mono', monospace";
    ctx.fillStyle = POSTER.grey;
    ctx.fillText("BY THE END OF " + (SEASON + 1) + ", " + (posterClean(d.name, 40) || "I").toUpperCase() + " WILL", pad, labelY);

    ctx.font = "700 " + size + "px 'Source Serif 4', Georgia, serif";
    ctx.fillStyle = POSTER.ink;
    y = labelY + 60;
    goalLines.slice(0, 6).forEach(function(line) {
      ctx.fillText(line, pad, y);
      y += Math.round(size * 1.06);
    });
    ctx.fillStyle = POSTER.teal;
    ctx.fillRect(pad, y + 24, 150, 6);

    ctx.font = "italic 38px 'Source Serif 4', Georgia, serif";
    ctx.fillStyle = POSTER.grey;
    y = frameTop - whyHeight;
    whyLines.forEach(function(line) { ctx.fillText(line, pad, y); y += 50; });
  }

  function showResults(d) {
    var results = document.getElementById("results");
    var message = document.getElementById("message");
    if (message) { message.classList.add("hidden"); }
    form.hidden = true;
    results.hidden = false;
    try { drawPoster(d); } catch (err) { /* the emailed copy is the real one */ }
    var link = document.getElementById("poster-download");
    try { link.href = document.getElementById("poster-canvas").toDataURL("image/png"); }
    catch (err) { link.hidden = true; }
    link.addEventListener("click", function() { ga4("goal_poster_download", { variant: VARIANT }); });

    var pick = results.querySelector("[data-offer-variant=\"" + OFFER_VARIANT + "\"]");
    if (pick) {
      pick.hidden = false;
      var key = OFFER_VARIANT;
      /* Carry the offer variant (and, if present, the race that sent this
         visitor to /goals/) into each plan CTA's URL so a later purchase can
         be attributed back to which offer copy and which entry point led to
         it. Race's cta_href starts as the static "?src=goals"; Season's
         starts as the bare "/season-plan/" — add params, don't replace. The
         Season CTA alone also carries ?t=<poster_token>, once the worker
         response has handed it back, so /season-plan/ can read this lead's
         saved /goals/ answers. */
      pick.querySelectorAll("[data-offer-cta]").forEach(function(cta) {
        var planType = cta.getAttribute("data-plan-type") || "race";
        try {
          var ctaUrl = new URL(cta.getAttribute("href"), window.location.href);
          ctaUrl.searchParams.set("offer_variant", key);
          if (RACE_SLUG) { ctaUrl.searchParams.set("race", RACE_SLUG); }
          // Carried as its own param, NOT written into src= — that stays
          // "goals" (the plan form's own entry-surface value for "came from
          // the goals funnel"). Losing which surface (home/race) originally
          // sent the visitor to /goals/ would otherwise attribute every
          // plan-form arrival from here the same way.
          if (ENTRY_SRC) { ctaUrl.searchParams.set("entry_src", ENTRY_SRC); }
          if (planType === "season" && POSTER_TOKEN) { ctaUrl.searchParams.set("t", POSTER_TOKEN); }
          cta.href = ctaUrl.pathname + ctaUrl.search;
        } catch (err) { /* keep the static href */ }
        ga4("goal_offer_view", { variant: VARIANT, offer_variant: key, plan_type: planType });
        cta.addEventListener("click", function() {
          ga4("goal_offer_click", { variant: VARIANT, offer_variant: key, plan_type: planType });
        });
      });
      var decline = pick.querySelector("[data-offer-decline]");
      if (decline) {
        decline.addEventListener("click", function(e) {
          e.preventDefault();
          pick.hidden = true;
          ga4("goal_offer_declined", { variant: VARIANT, offer_variant: key });
        });
      }
    }
    ga4("goal_results_view", { variant: VARIANT });
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function showMessage(type, text) {
    var m = document.getElementById("message");
    m.className = "gg-apply-message " + type;
    m.textContent = text;
    m.classList.remove("hidden");
    m.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  /* goal_section: fired once per numbered section the visitor actually
     scrolls to (a real action), never on a timer. Mirrors the walkthrough
     recorder's own section watcher (data-section-n set by render_sections).

     IntersectionObserver reports each target's CURRENT state the moment
     observe() is called — so wiring it up immediately on load would fire
     goal_section for section 1 (already on screen) before the visitor has
     done anything at all. Deferred to the first real scroll or keystroke;
     whatever is on screen at that point is then a genuine, once-per-section
     read. */
  function watchGoalSections() {
    if (typeof IntersectionObserver !== "function") { return; }
    var targets = Array.prototype.slice.call(form.querySelectorAll("[data-section-n]"));
    if (!targets.length) { return; }
    var seen = {};
    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (!entry.isIntersecting) { return; }
        var n = entry.target.getAttribute("data-section-n");
        if (!n || seen[n]) { return; }
        seen[n] = true;
        ga4("goal_section", { variant: VARIANT, number: Number(n) });
      });
    }, { threshold: 0.5 });
    targets.forEach(function(t) { observer.observe(t); });
  }

  var goalSectionsStarted = false;
  function startWatchingGoalSectionsOnce() {
    // restoringDraft: a restored draft's "Picked up where you left off"
    // message smooth-scrolls the page (showMessage -> scrollIntoView),
    // which is a plain "scroll" event with no way to tell it apart from a
    // real one. Listening for pointerdown/keydown/wheel/touchstart instead
    // sidesteps that entirely — none of those ever fire from a
    // programmatic scroll — and restoringDraft is kept as a second guard
    // in case a future signal is added that could.
    if (goalSectionsStarted || restoringDraft) { return; }
    goalSectionsStarted = true;
    watchGoalSections();
  }
  ["pointerdown", "keydown", "wheel", "touchstart"].forEach(function(evt) {
    window.addEventListener(evt, startWatchingGoalSectionsOnce, { once: true, passive: true });
  });
  restore();
  ga4("season_review_view", { variant: VARIANT });
})();
</script>'''
    js_str = lambda s: html.unescape(s).replace("\\", "\\\\").replace('"', '\\"')
    return (
        js.replace("__STORAGE_KEY__", f"season_review_{SEASON}_{variant['slug']}_v3")
        .replace("__SUBMIT_URL__", FORMSUBMIT_URL)
        .replace("__LEAD_WORKER_URL__", LEAD_WORKER_URL)
        .replace("__LEAD_SOURCE__", WORKER_SOURCES.get(variant["slug"], ""))
        .replace("__TRANSPORT__", variant.get("transport", "both"))
        .replace("__SEASON__", str(SEASON))
        .replace("__VARIANT__", variant["slug"])
        .replace("__SUCCESS__", js_str(variant["success"]))
        .replace("__SUBMIT_LABEL__", js_str(variant["submit"]))
        .replace("__EMAIL__", FORMSUBMIT_EMAIL)
    )


# ── Walkthrough mode (D19) ───────────────────────────────────
# Matti talks through the page while using it; ?walkthrough=1 turns on a
# record control that captures mic audio (MediaRecorder) plus a timeline of
# which section is on screen and which fields he touches. On stop it
# downloads a .webm and a matching .json — nothing is uploaded anywhere.
# scripts/walkthrough.py turns the pair into a per-section markdown review.
#
# Absent the flag, the IIFE below returns on its very first line: no DOM
# node is created, no listener is attached, nothing runs. The script tag
# is still present in the HTML (this generator has one output per variant,
# not two), but it is inert — confirmed by test_walkthrough.py and by the
# Playwright check in the D19 build (docs/walkthrough.md).


def build_walkthrough_js(variant) -> str:
    js = r'''<script>
(function() {
  "use strict";
  if (new URLSearchParams(window.location.search).get("walkthrough") !== "1") { return; }

  var PAGE = "__WALK_PAGE__";
  var t0 = 0, startedAt = null;
  var events = [];
  var recorder = null, chunks = [], stream = null;
  var sectionObserver = null, lastSection = null;

  function stamp() {
    var d = new Date();
    function p(n) { return String(n).padStart(2, "0"); }
    return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + "-" + p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
  }

  function log(type, extra) {
    events.push(Object.assign({ t: Math.round((performance.now() - t0) / 10) / 100, type: type }, extra || {}));
  }

  /* Field NAMES only in the timeline events themselves — the typed values
     ride along on "input" because these are his own test answers and the
     file never leaves this machine (nothing here is ever uploaded). */
  function fieldName(el) {
    if (!el) { return null; }
    var mod = el.closest && el.closest("[data-module]");
    return el.name || el.id || (mod && mod.getAttribute("data-module")) || el.tagName;
  }

  function onFocus(e) { var f = fieldName(e.target); if (f) { log("focus", { field: f }); } }
  function onInput(e) {
    var f = fieldName(e.target);
    if (!f) { return; }
    var value = e.target.type === "checkbox" || e.target.type === "radio"
      ? (e.target.checked ? "checked" : "unchecked")
      : String(e.target.value || "").slice(0, 500);
    log("input", { field: f, value: value });
  }
  function onClick(e) {
    var el = e.target.closest("button, a, input[type=checkbox], input[type=radio], .gg-apply-radio-option, .gg-apply-checkbox-option, [data-module]");
    if (!el) { return; }
    log("click", { field: fieldName(el) || el.textContent.trim().slice(0, 60) });
  }

  function watchSections() {
    var targets = Array.prototype.slice.call(document.querySelectorAll(".gg-apply-section-title, .gg-sr-deeper"));
    if (!targets.length || typeof IntersectionObserver !== "function") { return; }
    sectionObserver = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (!entry.isIntersecting) { return; }
        var isModule = entry.target.matches(".gg-sr-deeper");
        var summary = isModule ? entry.target.querySelector("summary") : null;
        var title = (isModule ? (summary && summary.textContent) : entry.target.textContent);
        title = (title || "").trim();
        if (!title || title === lastSection) { return; }
        lastSection = title;
        log("section", { section: title });
      });
    }, { threshold: 0.5 });
    targets.forEach(function(t) { sectionObserver.observe(t); });
  }

  function download(filename, blob) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function() { URL.revokeObjectURL(a.href); }, 60000);
  }

  function finish() {
    var name = "walkthrough-" + PAGE + "-" + stamp();
    var timeline = { page: PAGE, url: window.location.href, startedAt: startedAt, endedAt: new Date().toISOString(), events: events };
    /* ONE file: Chrome silently blocks a second automatic download, which
       lost the timeline on the first real walkthrough (Sep 23). */
    var audio = chunks.length ? new Blob(chunks, { type: chunks[0].type || "audio/webm" }) : null;
    if (!audio) {
      download(name + ".walk.json", new Blob([JSON.stringify({ timeline: timeline, audio: null })], { type: "application/json" }));
      return;
    }
    var reader = new FileReader();
    reader.onload = function() {
      var b64 = String(reader.result).split(",")[1] || "";
      download(name + ".walk.json", new Blob([JSON.stringify({ timeline: timeline, audio: { mime: audio.type, base64: b64 } })], { type: "application/json" }));
    };
    reader.readAsDataURL(audio);
  }

  function stopAll(btn) {
    if (recorder && recorder.state !== "inactive") { recorder.stop(); } else { finish(); }
    if (stream) { stream.getTracks().forEach(function(tr) { tr.stop(); }); }
    if (sectionObserver) { sectionObserver.disconnect(); }
    document.removeEventListener("focusin", onFocus, true);
    document.removeEventListener("input", onInput, true);
    document.removeEventListener("click", onClick, true);
    btn.textContent = "● Record walkthrough";
    btn.classList.remove("recording");
  }

  function start(btn) {
    if (typeof MediaRecorder === "undefined" || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("This browser can't record audio here (no MediaRecorder).");
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(s) {
      stream = s;
      chunks = [];
      events = [];
      startedAt = new Date().toISOString();
      t0 = performance.now();
      lastSection = null;
      try { recorder = new MediaRecorder(stream); }
      catch (err) { alert("Couldn't start the recorder: " + err.message); return; }
      recorder.ondataavailable = function(e) { if (e.data && e.data.size) { chunks.push(e.data); } };
      recorder.onstop = finish;
      recorder.start(1000);
      document.addEventListener("focusin", onFocus, true);
      document.addEventListener("input", onInput, true);
      document.addEventListener("click", onClick, true);
      watchSections();
      btn.textContent = "■ Stop walkthrough";
      btn.classList.add("recording");
    }).catch(function(err) {
      alert("Microphone access failed: " + err.message);
    });
  }

  function buildControl() {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.id = "gg-walkthrough-btn";
    btn.textContent = "● Record walkthrough";
    btn.style.cssText = "position:fixed;bottom:16px;right:16px;z-index:99999;padding:10px 14px;"
      + "background:#1a1613;color:#fff;border:2px solid #1a1613;font:700 12px/1 monospace;"
      + "letter-spacing:.05em;text-transform:uppercase;cursor:pointer;";
    btn.addEventListener("click", function() {
      if (btn.classList.contains("recording")) { stopAll(btn); } else { start(btn); }
    });
    document.body.appendChild(btn);
  }

  if (document.readyState === "loading") { document.addEventListener("DOMContentLoaded", buildControl); }
  else { buildControl(); }
})();
</script>'''
    return js.replace("__WALK_PAGE__", variant["slug"])


# ── Page assembly ─────────────────────────────────────────────


def generate_season_review_page(slug: str = "standard", external_assets=None) -> str:
    variant = VARIANTS[slug]
    page_css = external_assets["css_tag"] if external_assets else get_page_css()
    title = variant.get("title") or f"Season Review {SEASON} | Gravel God"
    description = variant.get("description", "")
    description_tags = (
        f'\n  <meta name="description" content="{description}">'
        f'\n  <meta property="og:description" content="{description}">' if description else ""
    )
    url = SITE_BASE_URL + page_path(slug)
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="robots" content="{variant.get('robots', 'noindex, nofollow')}">
  <link rel="canonical" href="{url}">
  <meta property="og:title" content="{title}">{description_tags}
  <meta property="og:type" content="website">
  <meta property="og:url" content="{url}">
  <meta property="og:image" content="{SITE_BASE_URL}/og/homepage.jpg">
  {get_favicon_head_snippet()}
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
    {build_results(variant)}
  </div>
  {build_footer(variant)}
  {build_season_review_js(variant)}
  {build_walkthrough_js(variant)}
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
