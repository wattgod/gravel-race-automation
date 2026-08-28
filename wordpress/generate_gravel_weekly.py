#!/usr/bin/env python3
"""Render Gravel Weekly's latest issue and immutable dated archive."""

from __future__ import annotations

import argparse
import html as html_mod
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from brand_tokens import get_font_face_css, get_ga4_head_snippet, get_tokens_css  # noqa: E402
from cookie_consent import get_consent_banner_html  # noqa: E402
from shared_header import get_site_header_css, get_site_header_html, get_site_header_js  # noqa: E402
from validate_gravel_weekly import load_issues, validate_issue  # noqa: E402
from validate_gravel_weekly_history import HISTORY_DIR, load_public_history_entries  # noqa: E402

ISSUE_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "issues"
OUTPUT = PROJECT_ROOT / "wordpress" / "output" / "gravel-weekly.html"
ARCHIVE_OUTPUT = PROJECT_ROOT / "wordpress" / "output" / "gravel-weekly"
LEAD_WORKER_URL = "https://fueling-lead-intake.gravelgodcoaching.workers.dev"
SITE_URL = "https://gravelgodcycling.com"


def esc(value: Any) -> str:
    if value is None:
        return ""
    return html_mod.escape(str(value), quote=True)


def safe_json_for_script(value: Any) -> str:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("<", "\\u003c")
            .replace(">", "\\u003e")
            .replace("&", "\\u0026")
            .replace("\u2028", "\\u2028")
            .replace("\u2029", "\\u2029"))


def display_date(value: str) -> str:
    return datetime.strptime(value, "%Y-%m-%d").strftime("%B %-d, %Y")


def prose(value: str) -> str:
    return "".join(
        f'<p>{esc(paragraph.strip())}</p>'
        for paragraph in value.split("\n\n") if paragraph.strip()
    )


def story_by_id(issue: dict[str, Any], story_id: str | None) -> dict[str, Any] | None:
    return next((story for story in issue["stories"] if story["candidateId"] == story_id), None)


def render_receipts(receipts: list[dict[str, Any]]) -> str:
    items = []
    for receipt in receipts:
        date_label = ""
        if receipt.get("publishedAt"):
            try:
                date_label = datetime.fromisoformat(receipt["publishedAt"].replace("Z", "+00:00")).strftime("%b %-d")
            except ValueError:
                date_label = ""
        timestamp = ""
        if receipt.get("transcriptStartSeconds") is not None:
            seconds = int(receipt["transcriptStartSeconds"])
            timestamp = f" · {seconds // 60}:{seconds % 60:02d}"
        meta = " · ".join(part for part in [receipt["publisher"], date_label] if part)
        excerpt = f'<blockquote>{esc(receipt["quoteExcerpt"])}</blockquote>' if receipt.get("quoteExcerpt") else ""
        items.append(f'''<li>
          <a href="{esc(receipt['canonicalUrl'])}" rel="noopener" target="_blank">{esc(meta or receipt['canonicalUrl'])}{esc(timestamp)}</a>
          {excerpt}
        </li>''')
    return f'<ol class="gw-receipts">{"".join(items)}</ol>'


def render_impacts(impacts: list[dict[str, Any]]) -> str:
    meaningful = [impact for impact in impacts if impact["impactKind"] != "no_change"]
    if not meaningful:
        return '<p class="gw-empty">No race-profile change proposed.</p>'
    labels = {
        "verify_field": "VERIFY",
        "propose_fact": "FACT PROPOSED",
        "editorial_review": "EDITORIAL REVIEW",
        "new_race_candidate": "NEW RACE",
    }
    items = []
    for impact in meaningful:
        _, slug = impact["raceId"].split(":", 1)
        field = f'<code>{esc(impact["fieldPath"])}</code>' if impact.get("fieldPath") else "catalog entry"
        items.append(f'''<li>
          <span class="gw-impact-label">{esc(labels.get(impact['impactKind'], impact['impactKind'].upper()))}</span>
          <a href="/race/{esc(slug)}/">{esc(slug.replace('-', ' '))}</a>
          <span>{field} · {round(float(impact['confidence']) * 100)}% evidence confidence · human review required</span>
        </li>''')
    return f'<ul class="gw-impacts">{"".join(items)}</ul>'


def render_retrospectives(retrospectives: list[dict[str, Any]], issues: list[dict[str, Any]], *, draft: bool) -> str:
    if not retrospectives:
        return ""
    issue_by_id = {issue["issueId"]: issue for issue in issues}
    verdict_labels = {
        "aged_well": "THIS AGED WELL",
        "aged_poorly": "THIS AGED POORLY",
        "still_developing": "STILL DEVELOPING",
    }
    cards = []
    for item in retrospectives:
        prior = issue_by_id.get(item["priorIssueId"])
        label = verdict_labels[item["verdict"]]
        prior_label = f"Earlier take · {item['priorIssueId']}"
        if prior:
            prior_label = f"Issue #{prior['issueNumber']:03d} · {display_date(prior['publicationDate'])}"
            prior_link = f'<a href="/gravel-weekly/{esc(prior["slug"])}/#{esc(item["priorStoryId"])}">{esc(prior_label)}</a>'
        else:
            prior_link = f"<span>{esc(prior_label)}</span>"
        assessment_label = "THE REASSESSMENT — MODEL DRAFT" if draft else "THE REASSESSMENT"
        cards.append(f'''<article class="gw-memory gw-memory--{esc(item['verdict'])}">
          <header><span class="gw-memory-verdict">{esc(label)}</span>{prior_link}<h3>{esc(item['headline'])}</h3></header>
          <div class="gw-memory-grid">
            <section><h4>WHAT CHANGED</h4>{prose(item['whatChanged'])}</section>
            <section><h4>{assessment_label}</h4>{prose(item['assessment'])}</section>
          </div>
          <details class="gw-details"><summary>RECEIPTS · {len(item['receipts'])}</summary>{render_receipts(item['receipts'])}</details>
        </article>''')
    return f'<section class="gw-retrospectives"><h2>THE RECEIPTS ON US</h2><p class="gw-retro-dek">Old takes do not disappear when the timeline moves on.</p>{"".join(cards)}</section>'


def render_story(story: dict[str, Any], *, current: bool = False, draft: bool = False) -> str:
    label = "THE CURRENT THING" if current else story["storyKind"].replace("_", " ").upper()
    take_label = "THE TAKE — MODEL DRAFT" if draft else "THE TAKE"
    return f'''<article class="gw-story{' gw-story--cover' if current else ''}" id="{esc(story['candidateId'])}">
      <header class="gw-story-head">
        <span class="gw-cover-line">{esc(label)}</span>
        <span class="gw-score">EDITORIAL SCORE {story['score']}/100</span>
        <h2>{esc(story['headline'])}</h2>
        <p class="gw-dek">{esc(story['dek'])}</p>
      </header>
      <div class="gw-story-grid">
        <section class="gw-facts" aria-labelledby="facts-{esc(story['candidateId'])}">
          <h3 id="facts-{esc(story['candidateId'])}">WHAT HAPPENED</h3>
          {prose(story['whatHappened'])}
        </section>
        <section class="gw-take" aria-labelledby="take-{esc(story['candidateId'])}">
          <h3 id="take-{esc(story['candidateId'])}">{take_label}</h3>
          {prose(story['take'])}
        </section>
      </div>
      <details class="gw-details">
        <summary>RECEIPTS · {len(story['receipts'])}</summary>
        {render_receipts(story['receipts'])}
      </details>
      <details class="gw-details">
        <summary>RACE INTELLIGENCE</summary>
        {render_impacts(story['raceImpacts'])}
      </details>
    </article>'''


def render_archive(issues: list[dict[str, Any]], active_issue_id: str) -> str:
    items = []
    for issue in issues:
        current = story_by_id(issue, issue.get("currentThingStoryId"))
        label = current["headline"] if current else issue["title"]
        deck = current["dek"] if current else "No manufactured Current Thing cleared the gate."
        take = ""
        if current:
            compact_take = " ".join(current["take"].split())
            excerpt = compact_take[:240].rstrip()
            if len(compact_take) > 240:
                excerpt += "…"
            take = f'<p class="gw-archive-take"><b>THE TAKE:</b> {esc(excerpt)}</p>'
        active = ' aria-current="page"' if issue["issueId"] == active_issue_id else ""
        items.append(f'''<li>
          <a href="/gravel-weekly/{esc(issue['slug'])}/"{active}>
            <span>ISSUE #{issue['issueNumber']:03d} · {esc(display_date(issue['publicationDate']).upper())}</span>
            <strong>{esc(label)}</strong>
            <p>{esc(deck)}</p>
            {take}
          </a>
        </li>''')
    return f'<ol class="gw-archive">{"".join(items)}</ol>' if items else '<p class="gw-empty">The archive starts with Issue #001.</p>'


def render_history_timeline(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return '''<section class="gw-history" id="season-story">
          <header class="gw-history-head"><span class="gw-label">THE PULSE OF GRAVEL</span><h2>THE SEASON AS A STORY</h2><p>The backfill is underway. Empty periods stay empty until a sourced point clears the gate.</p></header>
        </section>'''
    cards = []
    for entry in entries:
        active_label = display_date(entry["activeFrom"])
        if entry["activeThrough"] != entry["activeFrom"]:
            active_label = f'{active_label} → {display_date(entry["activeThrough"])}'
        later = ""
        if entry["laterEvidence"]:
            later = f'''<details class="gw-history-later">
              <summary>LATER EVIDENCE — NOT AVAILABLE THEN · {len(entry['laterEvidence'])}</summary>
              {render_receipts(entry['laterEvidence'])}
            </details>'''
        cards.append(f'''<!-- gravel-weekly-history-hash: {esc(entry['contentHash'])} -->
        <article class="gw-history-entry" id="{esc(entry['entryId'])}">
          <header><span class="gw-history-date">{esc(active_label.upper())}</span><span class="gw-score">EDITORIAL SCORE {entry['editorialScore']}/100</span><h3>{esc(entry['headline'])}</h3></header>
          <div class="gw-history-grid">
            <section><h4>THE POINT</h4>{prose(entry['point'])}<h4>WHAT HAPPENED</h4>{prose(entry['whatHappened'])}<h4>WHY IT MATTERED</h4>{prose(entry['stakes'])}<h4>THE FAIR OBJECTION</h4>{prose(entry['credibleOpposition'])}</section>
            <section class="gw-history-take"><h4>THE TAKE</h4>{prose(entry['take'])}</section>
          </div>
          <div class="gw-history-judgment"><b>WHAT CHANGED:</b> {esc(entry['priorJudgment'])} → {esc(entry['changedJudgment'])}</div>
          <details class="gw-details"><summary>WHAT WAS KNOWABLE THEN · {len(entry['contemporaryReceipts'])}</summary>{render_receipts(entry['contemporaryReceipts'])}</details>
          {later}
          <p class="gw-history-uncertainty"><b>UNCERTAINTY:</b> {esc(entry['uncertainty'])}</p>
        </article>''')
    return f'''<section class="gw-history" id="season-story">
      <header class="gw-history-head"><span class="gw-label">THE PULSE OF GRAVEL</span><h2>THE SEASON AS A STORY</h2><p>Only approved narrative change-points. Contemporary receipts stay separate from what we learned later.</p></header>
      <div class="gw-history-line">{"".join(cards)}</div>
    </section>'''


def json_ld(issue: dict[str, Any], canonical_url: str) -> str:
    current = story_by_id(issue, issue.get("currentThingStoryId"))
    payload = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": current["headline"] if current else issue["title"],
        "description": current["dek"] if current else issue["mastheadDeck"],
        "datePublished": issue.get("publishedAt") or issue["publicationDate"],
        "dateModified": issue["updatedAt"],
        "author": {"@type": "Person", "name": "Matti Rowe"},
        "publisher": {"@type": "Organization", "name": "Gravel God"},
        "mainEntityOfPage": canonical_url,
    }
    return safe_json_for_script(payload)


def subscribe_block() -> str:
    return f'''<section class="gw-sub" id="subscribe">
      <p class="gw-label">GET NEXT WEEK&rsquo;S ISSUE</p>
      <h2>ONE EMAIL. ONCE A WEEK.</h2>
      <p>The sport moves on quickly. Gravel Weekly keeps the receipts.</p>
      <form class="gw-sub-form" id="gw-sub-form" autocomplete="off">
        <input type="text" class="gw-hp" name="website" value="" tabindex="-1" aria-hidden="true">
        <label class="gw-sr-only" for="gw-email">Email address</label>
        <input id="gw-email" type="email" name="email" required placeholder="your@email.com" autocomplete="email">
        <button type="submit">SUBSCRIBE</button>
      </form>
      <p class="gw-sub-msg" id="gw-sub-msg" role="status" aria-live="polite"></p>
    </section>
    <script>
    (function() {{
      var form = document.getElementById('gw-sub-form');
      var msg = document.getElementById('gw-sub-msg');
      if (!form || !msg) return;
      form.addEventListener('submit', function(event) {{
        event.preventDefault();
        var button = form.querySelector('button');
        var email = form.email.value.trim();
        if (!email || !button) return;
        button.disabled = true;
        msg.textContent = 'SUBSCRIBING...';
        fetch('{LEAD_WORKER_URL}', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            email: email,
            race_slug: '',
            race_name: 'Gravel Weekly',
            source: 'gravel_weekly_subscribe',
            brand: 'gravelgod',
            website: form.website.value
          }})
        }}).then(function(response) {{
          if (!response.ok) throw new Error('Subscription rejected');
          return response.json();
        }}).then(function() {{
          msg.textContent = "YOU'RE IN. NEXT ISSUE LANDS FRIDAY.";
          form.email.value = '';
          if (typeof gtag === 'function') gtag('event', 'gravel_weekly_subscribe', {{ source: 'gravel_weekly_page' }});
        }}).catch(function() {{
          msg.textContent = 'THAT FAILED. TRY AGAIN.';
        }}).finally(function() {{
          button.disabled = false;
        }});
      }});
    }})();
    </script>'''


def page_css() -> str:
    return '''
  body { margin: 0; background: var(--gg-color-warm-paper); color: var(--gg-color-near-black); font-family: var(--gg-font-data); }
  .gw-wrap { max-width: 1040px; margin: 0 auto; padding: var(--gg-spacing-lg) var(--gg-spacing-md) var(--gg-spacing-3xl); }
  .gw-masthead { border: var(--gg-border-heavy); background: var(--gg-color-white); margin-top: var(--gg-spacing-md); }
  .gw-masthead-top { display: flex; justify-content: space-between; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-xs) var(--gg-spacing-md); border-bottom: var(--gg-border-standard); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; }
  .gw-name { margin: 0; padding: var(--gg-spacing-sm) var(--gg-spacing-md) 0; font-family: var(--gg-font-data); font-size: clamp(3.3rem, 12vw, 8.2rem); font-weight: var(--gg-font-weight-black); line-height: .78; letter-spacing: -.08em; text-transform: uppercase; }
  .gw-name span { color: var(--gg-color-teal); }
  .gw-deck { margin: var(--gg-spacing-lg) var(--gg-spacing-md) var(--gg-spacing-md); padding: var(--gg-spacing-xs) var(--gg-spacing-sm); background: var(--gg-color-gold); border: var(--gg-border-standard); font-weight: var(--gg-font-weight-bold); text-transform: uppercase; letter-spacing: var(--gg-letter-spacing-wide); transform: rotate(-1deg); width: fit-content; }
  .gw-cover-lines { display: grid; grid-template-columns: repeat(3, 1fr); border-top: var(--gg-border-standard); }
  .gw-cover-lines span { padding: var(--gg-spacing-sm); border-right: var(--gg-border-subtle); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); text-align: center; text-transform: uppercase; }
  .gw-cover-lines span:last-child { border-right: 0; }
  .gw-back { display: inline-block; margin: var(--gg-spacing-lg) 0 0; color: var(--gg-color-primary-brown); font-weight: var(--gg-font-weight-bold); }
  .gw-story { margin-top: var(--gg-spacing-xl); border: var(--gg-border-heavy); background: var(--gg-color-white); }
  .gw-story--cover { border-width: calc(var(--gg-border-width-heavy) * 2); }
  .gw-story-head { padding: var(--gg-spacing-lg); border-bottom: var(--gg-border-standard); }
  .gw-cover-line, .gw-score, .gw-label { display: inline-block; font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; }
  .gw-cover-line { margin-right: var(--gg-spacing-xs); padding: var(--gg-spacing-2xs) var(--gg-spacing-xs); background: var(--gg-color-teal); color: var(--gg-color-white); }
  .gw-score { padding: var(--gg-spacing-2xs) var(--gg-spacing-xs); border: var(--gg-border-subtle); }
  .gw-story h2 { max-width: 900px; margin: var(--gg-spacing-md) 0 var(--gg-spacing-xs); font-family: var(--gg-font-editorial); font-size: clamp(2rem, 7vw, 4.8rem); line-height: .98; letter-spacing: var(--gg-letter-spacing-tight); }
  .gw-story:not(.gw-story--cover) h2 { font-size: clamp(1.8rem, 5vw, 3.4rem); }
  .gw-dek { max-width: 760px; margin: 0; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); line-height: var(--gg-line-height-normal); }
  .gw-story-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); }
  .gw-story-grid section { padding: var(--gg-spacing-lg); }
  .gw-take { background: var(--gg-color-sand); border-left: var(--gg-border-standard); }
  .gw-story-grid h3 { margin: 0 0 var(--gg-spacing-sm); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wider); }
  .gw-story-grid p { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-relaxed); }
  .gw-take p { font-weight: var(--gg-font-weight-semibold); }
  .gw-details { border-top: var(--gg-border-standard); }
  .gw-details summary { cursor: pointer; padding: var(--gg-spacing-sm) var(--gg-spacing-lg); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-receipts, .gw-impacts { margin: 0; padding: 0 var(--gg-spacing-lg) var(--gg-spacing-lg) calc(var(--gg-spacing-lg) * 2); }
  .gw-receipts li, .gw-impacts li { margin-bottom: var(--gg-spacing-sm); line-height: var(--gg-line-height-normal); }
  .gw-receipts a, .gw-impacts a { color: var(--gg-color-primary-brown); font-weight: var(--gg-font-weight-bold); }
  .gw-receipts blockquote { margin: var(--gg-spacing-xs) 0; padding-left: var(--gg-spacing-sm); border-left: var(--gg-border-gold); font-family: var(--gg-font-editorial); }
  .gw-impact-label { display: inline-block; margin-right: var(--gg-spacing-xs); padding: var(--gg-spacing-2xs) var(--gg-spacing-xs); background: var(--gg-color-gold); border: var(--gg-border-subtle); font-weight: var(--gg-font-weight-bold); }
  .gw-utility-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--gg-spacing-lg); margin-top: var(--gg-spacing-xl); }
  .gw-utility { border: var(--gg-border-heavy); background: var(--gg-color-white); padding: var(--gg-spacing-lg); }
  .gw-utility h2 { margin-top: 0; font-size: var(--gg-font-size-xl); }
  .gw-watch { padding-left: var(--gg-spacing-lg); }
  .gw-watch li { margin-bottom: var(--gg-spacing-xs); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); }
  .gw-archive { list-style: none; margin: 0; padding: 0; border: var(--gg-border-heavy); }
  .gw-archive li { border-bottom: var(--gg-border-standard); }
  .gw-archive li:last-child { border-bottom: 0; }
  .gw-archive a { display: grid; gap: var(--gg-spacing-xs); padding: var(--gg-spacing-md); color: var(--gg-color-near-black); text-decoration: none; }
  .gw-archive span { font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-archive strong { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); }
  .gw-archive p { margin: 0; max-width: 760px; font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-normal); }
  .gw-archive .gw-archive-take { font-size: var(--gg-font-size-sm); color: var(--gg-color-secondary-brown); }
  .gw-history { margin-top: var(--gg-spacing-2xl); border: var(--gg-border-heavy); background: var(--gg-color-white); }
  .gw-history-head { padding: var(--gg-spacing-lg); border-bottom: var(--gg-border-heavy); background: var(--gg-color-gold); }
  .gw-history-head h2 { margin: var(--gg-spacing-xs) 0; font-size: clamp(2rem, 6vw, 4.4rem); line-height: .95; }
  .gw-history-head p { max-width: 760px; margin: 0; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); }
  .gw-history-line { position: relative; padding: var(--gg-spacing-lg); }
  .gw-history-line::before { content: ''; position: absolute; top: 0; bottom: 0; left: calc(var(--gg-spacing-lg) + 7px); width: var(--gg-border-width-standard); background: var(--gg-color-teal); }
  .gw-history-entry { position: relative; margin: 0 0 var(--gg-spacing-xl) var(--gg-spacing-lg); border: var(--gg-border-heavy); background: var(--gg-color-warm-paper); }
  .gw-history-entry:last-child { margin-bottom: 0; }
  .gw-history-entry::before { content: ''; position: absolute; left: calc(var(--gg-spacing-lg) * -1 - 9px); top: var(--gg-spacing-md); width: 14px; height: 14px; border: var(--gg-border-standard); background: var(--gg-color-gold); }
  .gw-history-entry > header { padding: var(--gg-spacing-md); border-bottom: var(--gg-border-standard); }
  .gw-history-date { display: inline-block; margin-right: var(--gg-spacing-xs); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-history-entry h3 { margin: var(--gg-spacing-sm) 0 0; max-width: 860px; font-family: var(--gg-font-editorial); font-size: clamp(1.7rem, 4vw, 3rem); line-height: 1; }
  .gw-history-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); }
  .gw-history-grid section { padding: var(--gg-spacing-md); }
  .gw-history-grid h4 { margin: 0 0 var(--gg-spacing-xs); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-history-grid h4:not(:first-child) { margin-top: var(--gg-spacing-md); }
  .gw-history-grid p { font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-relaxed); }
  .gw-history-take { border-left: var(--gg-border-standard); background: var(--gg-color-sand); font-weight: var(--gg-font-weight-semibold); }
  .gw-history-judgment, .gw-history-uncertainty { margin: 0; padding: var(--gg-spacing-sm) var(--gg-spacing-md); border-top: var(--gg-border-standard); font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-normal); }
  .gw-history-later { border-top: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-history-later summary { cursor: pointer; padding: var(--gg-spacing-sm) var(--gg-spacing-md); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-history-later a { color: var(--gg-color-gold); }
  .gw-retrospectives { margin-top: var(--gg-spacing-xl); padding: var(--gg-spacing-lg); border: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-retrospectives > h2 { margin: 0; font-size: clamp(2rem, 6vw, 4rem); }
  .gw-retro-dek { margin: var(--gg-spacing-xs) 0 var(--gg-spacing-lg); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); }
  .gw-memory { margin-top: var(--gg-spacing-md); border: var(--gg-border-heavy); background: var(--gg-color-white); color: var(--gg-color-near-black); }
  .gw-memory > header { padding: var(--gg-spacing-md); border-bottom: var(--gg-border-standard); }
  .gw-memory > header > a, .gw-memory > header > span:not(.gw-memory-verdict) { display: inline-block; color: var(--gg-color-primary-brown); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); }
  .gw-memory-verdict { display: inline-block; margin-right: var(--gg-spacing-xs); padding: var(--gg-spacing-2xs) var(--gg-spacing-xs); border: var(--gg-border-subtle); background: var(--gg-color-gold); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); }
  .gw-memory--aged_poorly .gw-memory-verdict { background: var(--gg-color-teal); color: var(--gg-color-white); }
  .gw-memory > header h3 { margin: var(--gg-spacing-sm) 0 0; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xl); }
  .gw-memory-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gw-memory-grid section { padding: var(--gg-spacing-md); }
  .gw-memory-grid section + section { border-left: var(--gg-border-standard); background: var(--gg-color-sand); }
  .gw-memory-grid h4 { margin: 0 0 var(--gg-spacing-xs); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-memory-grid p { font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-relaxed); }
  .gw-corrections { border: var(--gg-border-heavy); background: var(--gg-color-gold); margin-top: var(--gg-spacing-xl); padding: var(--gg-spacing-lg); }
  .gw-corrections h2 { margin-top: 0; }
  .gw-sub { margin-top: var(--gg-spacing-2xl); padding: var(--gg-spacing-xl); border: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-sub h2 { margin: var(--gg-spacing-xs) 0; font-size: clamp(1.8rem, 5vw, 3rem); }
  .gw-sub-form { display: flex; gap: var(--gg-spacing-sm); flex-wrap: wrap; margin-top: var(--gg-spacing-md); }
  .gw-sub-form input[type="email"] { flex: 1; min-width: 220px; padding: var(--gg-spacing-sm); border: var(--gg-border-heavy); font: inherit; }
  .gw-sub-form button { padding: var(--gg-spacing-sm) var(--gg-spacing-lg); border: var(--gg-border-heavy); background: var(--gg-color-gold); color: var(--gg-color-near-black); font: inherit; font-weight: var(--gg-font-weight-bold); cursor: pointer; }
  .gw-sub-form button:disabled { background: var(--gg-color-tan); cursor: wait; }
  .gw-sub-msg { min-height: 1.5em; font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); }
  .gw-hp, .gw-sr-only { position: absolute; left: -10000px; width: 1px; height: 1px; overflow: hidden; }
  .gw-empty { font-family: var(--gg-font-editorial); font-style: italic; color: var(--gg-color-secondary-brown); }
  code { font-family: var(--gg-font-data); overflow-wrap: anywhere; }
  @media (max-width: 720px) {
    .gw-cover-lines, .gw-story-grid, .gw-utility-grid, .gw-memory-grid, .gw-history-grid { grid-template-columns: 1fr; }
    .gw-cover-lines span { border-right: 0; border-bottom: var(--gg-border-subtle); }
    .gw-cover-lines span:last-child { border-bottom: 0; }
    .gw-take { border-left: 0; border-top: var(--gg-border-standard); }
    .gw-memory-grid section + section { border-left: 0; border-top: var(--gg-border-standard); }
    .gw-history-take { border-left: 0; border-top: var(--gg-border-standard); }
    .gw-story-head, .gw-story-grid section, .gw-utility, .gw-sub { padding: var(--gg-spacing-md); }
  }
'''


def build_page(issue: dict[str, Any] | None, issues: list[dict[str, Any]], *, latest: bool, history_entries: list[dict[str, Any]] | None = None) -> str:
    canonical_path = "/gravel-weekly/" if latest or issue is None else f"/gravel-weekly/{issue['slug']}/"
    canonical_url = f"{SITE_URL}{canonical_path}"
    if issue:
        is_draft = issue["status"] == "draft"
        current = story_by_id(issue, issue.get("currentThingStoryId"))
        other_stories = [story for story in issue["stories"] if story["candidateId"] != issue.get("currentThingStoryId")]
        title = f"Gravel Weekly #{issue['issueNumber']:03d} — {display_date(issue['publicationDate'])}"
        description = current["dek"] if current else issue["mastheadDeck"]
        content = (render_story(current, current=True, draft=is_draft) if current else '<p class="gw-empty">Nothing this week deserved a manufactured Current Thing.</p>')
        content += "".join(render_story(story, draft=is_draft) for story in other_stories)
        watch = "".join(f"<li>{esc(item)}</li>" for item in issue["calendarWatch"]) or '<li class="gw-empty">No calendar item cleared the gate.</li>'
        corrections = ""
        if issue["corrections"]:
            items = "".join(f'<li><strong>{esc(item["publishedAt"][:10])}</strong> — {esc(item["text"])}</li>' for item in issue["corrections"])
            corrections = f'<section class="gw-corrections"><h2>CORRECTIONS</h2><ul>{items}</ul></section>'
        issue_body = f'''{content}
        <div class="gw-utility-grid">
          <section class="gw-utility"><h2>CALENDAR WATCH</h2><ul class="gw-watch">{watch}</ul></section>
          <section class="gw-utility"><h2>RACE INTELLIGENCE</h2>{render_impacts(issue['raceImpacts'])}</section>
        </div>
        {render_retrospectives(issue['retrospectives'], issues, draft=is_draft)}
        {corrections}'''
        schema = "" if is_draft else f'<script type="application/ld+json">{json_ld(issue, canonical_url)}</script>'
        issue_number = issue["issueNumber"]
        date_label = display_date(issue["publicationDate"]).upper()
        issue_id = issue["issueId"]
        publication_label = "DRAFT — NOT PUBLISHED" if is_draft else "BY GRAVEL GOD"
    else:
        title = "Gravel Weekly — Gravel God"
        description = "The people, races, money and bad ideas moving gravel. One opinionated issue every Friday."
        issue_body = '<section class="gw-story"><div class="gw-story-head"><span class="gw-cover-line">ISSUE #001</span><h2>The first issue is being assembled.</h2><p class="gw-dek">The evidence machine is working. The opinion still requires a person.</p></div></section>'
        schema = ""
        issue_number = 1
        date_label = "FRIDAYS"
        issue_id = "none"
        publication_label = "BY GRAVEL GOD"
    back = '<a class="gw-back" href="/gravel-weekly/">← LATEST ISSUE</a>' if not latest else ""
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}">
  <link rel="canonical" href="{esc(canonical_url)}">
{get_ga4_head_snippet()}
  {schema}
  <style>
{get_tokens_css()}
{get_font_face_css()}
{get_site_header_css()}
{page_css()}
  </style>
</head>
<body>
<!-- gravel-weekly-content-hash: {esc(issue['contentHash']) if issue else 'none'} -->
{get_site_header_html()}
<main class="gw-wrap">
  {back}
  <header class="gw-masthead">
    <div class="gw-masthead-top"><span>ISSUE #{issue_number:03d}</span><span>{esc(date_label)}</span><span>{esc(publication_label)}</span></div>
    <h1 class="gw-name">GRAVEL <span>WEEKLY</span></h1>
    <p class="gw-deck">THE PEOPLE, RACES, MONEY &amp; BAD IDEAS MOVING GRAVEL</p>
    <div class="gw-cover-lines"><span>WHAT HAPPENED</span><span>WHAT IT MEANS</span><span>WHAT CHANGES</span></div>
  </header>
  {issue_body}
  {render_history_timeline(history_entries or []) if latest else ''}
  <section class="gw-utility" id="past-issues"><h2>PAST ISSUES</h2>{render_archive(issues, issue_id)}</section>
  {subscribe_block()}
</main>
<script>{get_site_header_js()}</script>
{get_consent_banner_html()}
</body>
</html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview-draft", type=Path)
    parser.add_argument("--preview-output", type=Path, default=PROJECT_ROOT / "wordpress" / "output" / "gravel-weekly-draft.html")
    args = parser.parse_args()
    if args.preview_draft:
        issue = validate_issue(json.loads(args.preview_draft.read_text(encoding="utf-8")))
        args.preview_output.parent.mkdir(parents=True, exist_ok=True)
        args.preview_output.write_text(build_page(issue, [issue], latest=True), encoding="utf-8")
        print(f"Generated draft-only preview: {args.preview_output}")
        return 0
    all_issues = load_issues(ISSUE_DIR)
    public_history_entries = load_public_history_entries(HISTORY_DIR)
    public_issues = [issue for issue in all_issues if issue["status"] in {"approved", "published"}]
    latest_issue = public_issues[0] if public_issues else None
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_page(latest_issue, public_issues, latest=True, history_entries=public_history_entries), encoding="utf-8")
    for issue in public_issues:
        target = ARCHIVE_OUTPUT / issue["slug"] / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(build_page(issue, public_issues, latest=False), encoding="utf-8")
    print(f"Generated {OUTPUT} and {len(public_issues)} dated issue page(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
