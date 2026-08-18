#!/usr/bin/env python3
"""
Generate the Gravel God Consulting intake form at /consulting/intake/.

Fourteen questions, five minutes, save/resume via localStorage. Reads the
booking session ref and the athlete's private intake token from the URL
FRAGMENT (`#ref=...&t=...`) — never the query string, so neither value is
logged by servers or shows up in referrer headers. The token itself is only
ever emailed to the athlete in their welcome email; if it's missing (e.g.
someone lands here from the success page instead of the email), the page
still works and tells them to use the emailed link instead.

Submits `{ref, t, answers}` as JSON to the pipeline's /api/consult-intake
endpoint (token travels in the POST body, not a header or query param, to
keep the simple-CORS story intact).

Uses brand tokens exclusively — zero hardcoded hex, no border-radius, no
box-shadow, no bounce easing, no entrance animations.

Usage:
    python generate_consult_intake.py
    python generate_consult_intake.py --output-dir ./output
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
from brand_tokens import get_ab_head_snippet, get_ga4_head_snippet, get_preload_hints
from shared_footer import get_mega_footer_html
from shared_header import get_site_header_html
from cookie_consent import get_consent_banner_html
from generate_consulting import PRIVACY_SENTENCE

OUTPUT_DIR = Path(__file__).parent / "output"

CONSULT_INTAKE_API = "https://athlete-custom-training-plan-pipeline-production.up.railway.app/api/consult-intake"


def esc(text) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


# ── Page sections ─────────────────────────────────────────────


def build_nav() -> str:
    return get_site_header_html(active="services") + f'''
  <div class="gg-breadcrumb">
    <a href="{SITE_BASE_URL}/">Home</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <a href="{SITE_BASE_URL}/consulting/">Consulting</a>
    <span class="gg-breadcrumb-sep">&rsaquo;</span>
    <span class="gg-breadcrumb-current">Intake</span>
  </div>'''


def build_header() -> str:
    return '''<div class="gg-intake-header">
    <div class="gg-intake-badge">Consult Intake</div>
    <h1>Twelve Questions, Five Minutes</h1>
    <p>Answer what you can. Skip what you don&rsquo;t know &mdash; &ldquo;don&rsquo;t know&rdquo; is a fine answer for FTP and LTHR. Save and come back if you need to.</p>
  </div>
  <div class="gg-intake-token-banner" id="token-banner" style="display:none">
    Can&rsquo;t find your booking reference? Use the link in your welcome email instead &mdash; it connects your answers to your consult automatically. You can still fill this out; I&rsquo;ll match it up.
  </div>'''


def build_fields() -> str:
    return '''<div class="gg-intake-group">
      <label class="gg-intake-label" for="goal_event">Goal event</label>
      <input type="text" id="goal_event" name="goal_event" placeholder="Race or event name">
    </div>
    <div class="gg-intake-group">
      <label class="gg-intake-label" for="goal_date">Date</label>
      <input type="date" id="goal_date" name="goal_date">
    </div>
    <div class="gg-intake-inline">
      <div class="gg-intake-group">
        <label class="gg-intake-label" for="hours_typical">Typical weekly hours</label>
        <input type="text" id="hours_typical" name="hours_typical" placeholder="e.g. 8">
      </div>
      <div class="gg-intake-group">
        <label class="gg-intake-label" for="hours_max">Max weekly hours</label>
        <input type="text" id="hours_max" name="hours_max" placeholder="e.g. 12">
      </div>
    </div>
    <div class="gg-intake-group">
      <label class="gg-intake-label" for="years_training">Years training</label>
      <input type="text" id="years_training" name="years_training" placeholder="e.g. 3">
    </div>
    <div class="gg-intake-inline">
      <div class="gg-intake-group">
        <label class="gg-intake-label" for="ftp">Your threshold power (FTP), if you know it</label>
        <input type="text" id="ftp" name="ftp" placeholder="Watts, or &quot;don't know&quot;">
      </div>
      <div class="gg-intake-group">
        <label class="gg-intake-label" for="lthr">Your threshold heart rate (LTHR), if you know it</label>
        <input type="text" id="lthr" name="lthr" placeholder="BPM, or &quot;don't know&quot;">
      </div>
    </div>
    <div class="gg-intake-group">
      <label class="gg-intake-label" for="top_question">The one question you most want answered</label>
      <textarea id="top_question" name="top_question" rows="3"></textarea>
    </div>
    <div class="gg-intake-group">
      <label class="gg-intake-label" for="whats_gone_wrong">What&rsquo;s gone wrong this year</label>
      <textarea id="whats_gone_wrong" name="whats_gone_wrong" rows="3"></textarea>
    </div>
    <div class="gg-intake-group">
      <label class="gg-intake-label" for="injuries_limits">Injuries or limits</label>
      <textarea id="injuries_limits" name="injuries_limits" rows="2"></textarea>
    </div>
    <div class="gg-intake-group">
      <label class="gg-intake-label" for="tp_email">The email you sign in to TrainingPeaks with (or &quot;no TP&quot;)</label>
      <input type="text" id="tp_email" name="tp_email" placeholder="you@example.com, or &quot;no TP&quot;">
    </div>
    <div class="gg-intake-inline">
      <div class="gg-intake-group">
        <span class="gg-intake-label">Power meter?</span>
        <div class="gg-intake-radio-row">
          <label class="gg-intake-radio-option"><input type="radio" name="power_meter" value="yes"> Yes</label>
          <label class="gg-intake-radio-option"><input type="radio" name="power_meter" value="no"> No</label>
        </div>
      </div>
      <div class="gg-intake-group">
        <span class="gg-intake-label">HR strap?</span>
        <div class="gg-intake-radio-row">
          <label class="gg-intake-radio-option"><input type="radio" name="hr_strap" value="yes"> Yes</label>
          <label class="gg-intake-radio-option"><input type="radio" name="hr_strap" value="no"> No</label>
        </div>
      </div>
    </div>
    <div class="gg-intake-group">
      <label class="gg-intake-label" for="coaching_history">Coaching or plan history</label>
      <textarea id="coaching_history" name="coaching_history" rows="2"></textarea>
    </div>
    <div class="gg-intake-group">
      <label class="gg-intake-label" for="anything_else">Anything else</label>
      <textarea id="anything_else" name="anything_else" rows="2"></textarea>
    </div>'''


def build_submit_buttons() -> str:
    return '''<div class="gg-intake-buttons">
      <button type="button" id="save-btn" class="gg-intake-save-btn">Save Progress</button>
      <button type="submit" id="submit-btn" class="gg-intake-submit-btn">Submit</button>
    </div>'''


def build_success_state() -> str:
    return '''<div id="intake-success" class="gg-intake-success" style="display:none">
    <h2>Got it &mdash; I&rsquo;ll have your read done before we talk.</h2>
  </div>'''


def build_privacy() -> str:
    return f'''<p class="gg-intake-privacy">{PRIVACY_SENTENCE}</p>'''


def build_footer() -> str:
    return get_mega_footer_html()


def build_jsonld() -> str:
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Consulting Intake",
  "url": "{SITE_BASE_URL}/consulting/intake/"
}}
</script>'''


def build_intake_css() -> str:
    return '''<style>
.gg-intake-container {
  max-width: 640px;
  margin: 0 auto;
  padding: var(--gg-spacing-xl) var(--gg-spacing-xl) var(--gg-spacing-2xl);
}
.gg-intake-header {
  text-align: center;
  margin-bottom: var(--gg-spacing-lg);
}
.gg-intake-badge {
  display: inline-block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-secondary-brown);
  margin-bottom: var(--gg-spacing-sm);
}
.gg-intake-header h1 {
  font-family: var(--gg-font-editorial);
  font-size: clamp(24px, 4vw, 32px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0 0 var(--gg-spacing-sm) 0;
}
.gg-intake-header p {
  font-family: var(--gg-font-editorial);
  font-size: var(--gg-font-size-sm);
  line-height: var(--gg-line-height-prose);
  color: var(--gg-color-primary-brown);
  margin: 0;
}
.gg-intake-token-banner {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  line-height: var(--gg-line-height-normal);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-sand);
  border: 2px solid var(--gg-color-gold);
  padding: var(--gg-spacing-md);
  margin-bottom: var(--gg-spacing-lg);
}
.gg-intake-form-card {
  background: var(--gg-color-warm-paper);
  border: 3px solid var(--gg-color-dark-brown);
  padding: var(--gg-spacing-xl);
}
.gg-intake-inline {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--gg-spacing-md);
}
.gg-intake-group {
  margin-bottom: var(--gg-spacing-md);
}
.gg-intake-label {
  display: block;
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-wide);
  text-transform: uppercase;
  color: var(--gg-color-dark-brown);
  margin-bottom: var(--gg-spacing-xs);
}
.gg-intake-group input[type="text"],
.gg-intake-group input[type="date"],
.gg-intake-group textarea {
  display: block;
  width: 100%;
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-white);
  border: 2px solid var(--gg-color-dark-brown);
  box-sizing: border-box;
  resize: vertical;
}
.gg-intake-group input:focus,
.gg-intake-group textarea:focus {
  outline: none;
  border-color: var(--gg-color-gold);
}
.gg-intake-radio-row {
  display: flex;
  gap: var(--gg-spacing-md);
}
.gg-intake-radio-option {
  display: flex;
  align-items: center;
  gap: var(--gg-spacing-2xs);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-sm);
  color: var(--gg-color-primary-brown);
  cursor: pointer;
}
.gg-intake-honeypot {
  position: absolute;
  left: -9999px;
}
.gg-intake-buttons {
  display: flex;
  gap: var(--gg-spacing-md);
  margin-top: var(--gg-spacing-lg);
}
.gg-intake-submit-btn,
.gg-intake-save-btn {
  flex: 1;
  padding: var(--gg-spacing-sm) var(--gg-spacing-lg);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  font-weight: var(--gg-font-weight-bold);
  letter-spacing: var(--gg-letter-spacing-ultra-wide);
  text-transform: uppercase;
  cursor: pointer;
  border: 3px solid var(--gg-color-dark-brown);
  transition: background-color var(--gg-transition-hover), border-color var(--gg-transition-hover);
}
.gg-intake-submit-btn {
  color: var(--gg-color-dark-brown);
  background: var(--gg-color-light-gold);
}
.gg-intake-submit-btn:hover {
  background-color: var(--gg-color-gold);
  border-color: var(--gg-color-gold);
}
.gg-intake-submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.gg-intake-save-btn {
  color: var(--gg-color-primary-brown);
  background: var(--gg-color-white);
}
.gg-intake-save-btn:hover {
  background-color: var(--gg-color-sand);
}
.gg-intake-message {
  margin-top: var(--gg-spacing-md);
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-xs);
  text-align: center;
}
.gg-intake-message.info {
  color: var(--gg-color-teal);
}
.gg-intake-message.error {
  color: var(--gg-color-dark-brown);
  border: 2px solid var(--gg-color-dark-brown);
  padding: var(--gg-spacing-sm) var(--gg-spacing-md);
  background: var(--gg-color-sand);
}
.gg-intake-message.hidden {
  display: none;
}
.gg-intake-success {
  text-align: center;
  padding: var(--gg-spacing-2xl) var(--gg-spacing-xl);
  background: var(--gg-color-warm-paper);
  border: 3px solid var(--gg-color-teal);
}
.gg-intake-success h2 {
  font-family: var(--gg-font-editorial);
  font-size: clamp(22px, 4vw, 28px);
  font-weight: var(--gg-font-weight-bold);
  color: var(--gg-color-dark-brown);
  margin: 0;
}
.gg-intake-privacy {
  font-family: var(--gg-font-data);
  font-size: var(--gg-font-size-2xs);
  color: var(--gg-color-secondary-brown);
  text-align: center;
  line-height: var(--gg-line-height-normal);
  margin-top: var(--gg-spacing-xl);
}
@media (max-width: 600px) {
  .gg-intake-container { padding: var(--gg-spacing-lg) var(--gg-spacing-md) var(--gg-spacing-xl); }
  .gg-intake-form-card { padding: var(--gg-spacing-lg); }
  .gg-intake-inline { grid-template-columns: 1fr; }
  .gg-intake-buttons { flex-direction: column; }
}
</style>'''


def build_intake_js() -> str:
    return f'''<script>
(function(){{
  var API_URL = "{CONSULT_INTAKE_API}";
  var STORAGE_KEY = "consult_intake_progress";

  /* ── Parse ref/t from the URL FRAGMENT only — never the query string ── */
  function parseFragment(){{
    var hash = window.location.hash || "";
    if (hash.indexOf("#") === 0) {{ hash = hash.slice(1); }}
    var params = new URLSearchParams(hash);
    return {{ ref: params.get("ref") || "", t: params.get("t") || "" }};
  }}
  var frag = parseFragment();

  if (!frag.t) {{
    var banner = document.getElementById("token-banner");
    if (banner) {{ banner.style.display = "block"; }}
  }}

  var form = document.getElementById("intake-form");
  var msgEl = document.getElementById("intake-message");
  var submitBtn = document.getElementById("submit-btn");
  var successEl = document.getElementById("intake-success");

  function showMessage(type, text){{
    if (!msgEl) return;
    msgEl.className = "gg-intake-message " + type;
    msgEl.textContent = text;
  }}

  /* ── Save progress ── */
  var saveBtn = document.getElementById("save-btn");
  if (saveBtn) {{
    saveBtn.addEventListener("click", function(){{
      var data = {{}};
      new FormData(form).forEach(function(value, key){{
        if (key === "_honeypot") return;
        data[key] = value;
      }});
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      showMessage("info", "Progress saved. Come back anytime.");
      if (typeof gtag === "function") {{ gtag("event", "consult_intake_progress_saved", {{}}); }}
    }});
  }}

  /* ── Restore progress ── */
  function restoreProgress(){{
    var saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    try {{
      var data = JSON.parse(saved);
      Object.keys(data).forEach(function(key){{
        var elements = form.querySelectorAll('[name="' + key + '"]');
        elements.forEach(function(el){{
          if (el.type === "radio") {{ el.checked = (el.value === data[key]); }}
          else {{ el.value = data[key]; }}
        }});
      }});
    }} catch (e) {{ /* ignore corrupt localStorage */ }}
  }}

  /* ── Submit ── */
  if (form) {{
    form.addEventListener("submit", function(e){{
      e.preventDefault();
      var honeypot = form.querySelector('input[name="_honeypot"]').value;
      if (honeypot) return;

      submitBtn.disabled = true;
      submitBtn.textContent = "Submitting...";
      showMessage("info", "");

      var answers = {{}};
      new FormData(form).forEach(function(value, key){{
        if (key === "_honeypot") return;
        answers[key] = value;
      }});

      var payload = {{ ref: frag.ref, t: frag.t, answers: answers }};

      fetch(API_URL, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload)
      }}).then(function(r){{
        if (!r.ok) throw new Error("Server error (" + r.status + ")");
        return r.json();
      }}).then(function(){{
        localStorage.removeItem(STORAGE_KEY);
        if (typeof gtag === "function") {{ gtag("event", "consult_intake_submitted", {{}}); }}
        form.style.display = "none";
        if (successEl) {{ successEl.style.display = "block"; successEl.scrollIntoView({{ behavior: "smooth", block: "center" }}); }}
      }}).catch(function(err){{
        /* Keep the draft in localStorage — do NOT clear it on error */
        showMessage("error", "Something went wrong. Your answers are saved on this device — try again, or reply to your welcome email.");
        submitBtn.disabled = false;
        submitBtn.textContent = "Submit";
        if (typeof gtag === "function") {{ gtag("event", "consult_intake_error", {{ error: err.message || "unknown" }}); }}
      }});
    }});
  }}

  if (typeof gtag === "function") {{ gtag("event", "consult_intake_page_view", {{}}); }}

  restoreProgress();
}})();
</script>'''


def generate_intake_page(external_assets: dict = None) -> str:
    canonical_url = f"{SITE_BASE_URL}/consulting/intake/"

    nav = build_nav()
    header = build_header()
    fields = build_fields()
    buttons = build_submit_buttons()
    success = build_success_state()
    privacy = build_privacy()
    footer = build_footer()
    jsonld = build_jsonld()
    intake_css = build_intake_css()
    intake_js = build_intake_js()

    if external_assets:
        page_css = external_assets['css_tag']
        inline_js = external_assets['js_tag']
    else:
        page_css = get_page_css()
        inline_js = build_inline_js()

    preload = get_preload_hints()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Consulting Intake | Gravel God</title>
  <meta name="description" content="Twelve questions before your consult call — five minutes, save and come back.">
  <meta name="robots" content="noindex, follow">
  <link rel="canonical" href="{esc(canonical_url)}">
  <link rel="preconnect" href="https://www.googletagmanager.com" crossorigin>
  {preload}
  {jsonld}
  {page_css}
  {intake_css}
  {get_ga4_head_snippet()}
  {get_ab_head_snippet()}
</head>
<body>

<div class="gg-neo-brutalist-page">
  {nav}

  <div class="gg-intake-container">
    {header}
    <form id="intake-form" class="gg-intake-form-card" novalidate>
      <input type="text" name="_honeypot" class="gg-intake-honeypot" tabindex="-1" autocomplete="off">
      {fields}
      {buttons}
      <div id="intake-message" class="gg-intake-message hidden"></div>
    </form>
    {success}
    {privacy}
  </div>

  {footer}
</div>

{inline_js}
{intake_js}

{get_consent_banner_html()}
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description="Generate Gravel God consulting intake page")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    assets = write_shared_assets(output_dir)

    html_content = generate_intake_page(external_assets=assets)
    output_file = output_dir / "consult-intake.html"
    output_file.write_text(html_content, encoding="utf-8")
    print(f"Generated {output_file} ({len(html_content):,} bytes)")


if __name__ == "__main__":
    main()
