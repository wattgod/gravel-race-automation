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
from gravel_weekly_visuals import render_story_visual, visual_css  # noqa: E402
from gravel_weekly_culture import culture_css, render_culture_artifacts  # noqa: E402
from shared_header import get_site_header_css, get_site_header_html, get_site_header_js  # noqa: E402
from validate_gravel_weekly import load_public_issues, validate_issue  # noqa: E402
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


def meaningful_impacts(impacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [impact for impact in impacts if impact["impactKind"] != "no_change"]


def render_issue_contents(issue: dict[str, Any]) -> str:
    """Render an evidence-aware issue map without inventing empty departments."""
    current = story_by_id(issue, issue.get("currentThingStoryId"))
    if current is None:
        quiet = issue.get("quietIssue")
        if quiet is None:
            return ""
        return f'''<nav class="gw-contents" aria-label="In this issue">
      <header><span>IN THIS ISSUE</span><p>A deliberate short issue. No filler.</p></header>
      <ol><li><a href="#quiet-week"><span>1</span><b>THE QUIET WEEK</b><small>{esc(quiet['headline'])}</small></a></li></ol>
    </nav>'''
    story_id = current["candidateId"]
    chapters: list[tuple[str, str, str]] = [
        (f"#{story_id}", "THE CURRENT THING", current["headline"]),
    ]
    if current.get("cast"):
        chapters.append((f"#cast-{story_id}", "THE CAST", "The sourced roles in the story"))
    chapters.append((f"#record-{story_id}", "THE RECORD", "The verified account"))
    take_description = (
        "The model draft awaiting approval"
        if issue["status"] == "draft"
        else "The approved judgment"
    )
    chapters.append((f"#take-{story_id}", "THE TAKE", take_description))
    if current.get("fieldNotes"):
        chapters.append((f"#field-notes-{story_id}", "FIELD NOTES", "Specific details from the evidence"))
    if current.get("cultureArtifacts"):
        chapters.append((f"#scene-{story_id}", "THE SCENE REPORT", "What the culture sample adds"))
    if meaningful_impacts(current["raceImpacts"]):
        chapters.append((f"#changes-{story_id}", "WHAT THIS CHANGES", "Controlled race intelligence"))
    other_stories = [
        story for story in issue["stories"]
        if story["candidateId"] != issue.get("currentThingStoryId")
    ]
    if other_stories:
        noun = "story" if len(other_stories) == 1 else "stories"
        chapters.append((
            f"#{other_stories[0]['candidateId']}",
            "ALSO THIS WEEK",
            f"{len(other_stories)} more {noun} that cleared the gate",
        ))
    if issue["retrospectives"]:
        chapters.append(("#memory", "MEMORY", "Earlier takes meet later evidence"))
    if issue["corrections"]:
        chapters.append(("#corrections", "CORRECTIONS", "The permanent record"))
    items = "".join(
        f'''<li><a href="{esc(target)}"><span>{index}</span><b>{esc(label)}</b><small>{esc(description)}</small></a></li>'''
        for index, (target, label, description) in enumerate(chapters, start=1)
    )
    return f'''<nav class="gw-contents" aria-label="In this issue">
      <header><span>IN THIS ISSUE</span><p>The record, the scene, the Take, and the receipts.</p></header>
      <ol>{items}</ol>
    </nav>'''


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


def render_quiet_issue(quiet: dict[str, Any], *, draft: bool) -> str:
    label = "QUIET ISSUE — MODEL DRAFT" if draft else "THE QUIET WEEK"
    return f'''<section class="gw-quiet" id="quiet-week">
      <span>{esc(label)}</span>
      <h2>{esc(quiet['headline'])}</h2>
      {prose(quiet['note'])}
    </section>'''


def render_source_coverage_receipt(coverage: dict[str, Any]) -> str:
    latest = coverage["latestSourceHealth"]
    scoped = coverage.get("schemaVersion") == "gravel-weekly-source-coverage/v2"
    lane_labels = (
        (("GRAVEL OFFICIAL RACE/RESULTS" if scoped else "OFFICIAL RACE/RESULTS"), latest["officialObservation"]),
        (("GRAVEL NEWS/BLOGS/FORUMS" if scoped else "PUBLIC NEWS/BLOGS/FORUMS"), latest["publicDiscovery"]),
        (("GRAVEL SOCIAL/CULTURE APIS" if scoped else "SOCIAL/CULTURE APIS"), latest["officialSocial"]),
    )
    lanes = "".join(
        f'''<li><b>{esc(label)}</b><span>{health['succeeded']}/{health['attempted']} succeeded{f" · {health['failed']} failed" if health['failed'] else ""}</span></li>'''
        for label, health in lane_labels
    )
    sources = "".join(
        f'''<li><b>{esc(source['publisher'])}</b><span>{esc(source['connector'])} · {esc(source['latestStatus'])} · {source['parsedItems']} parsed · {source['emittedItems']} new</span></li>'''
        for source in coverage["discoverySources"]
    )
    visible_errors = coverage["sourceErrors"][-20:]
    hidden_error_count = len(coverage["sourceErrors"]) - len(visible_errors)
    error_notice = (
        f"<p>Showing the 20 most recent of {len(coverage['sourceErrors'])}; the complete receipt remains bound to this issue.</p>"
        if hidden_error_count else ""
    )
    errors = "".join(f"<li>{esc(error)}</li>" for error in visible_errors)
    error_block = (
        f'''<details><summary>MOST RECENT COLLECTION GAPS ({len(coverage['sourceErrors'])} TOTAL)</summary>{error_notice}<ul>{errors}</ul></details>'''
        if errors else ""
    )
    warnings = coverage.get("infrastructureWarnings", [])
    visible_warnings = warnings[-20:]
    warning_notice = (
        f"<p>Showing the 20 most recent of {len(warnings)}; these did not change the gravel coverage verdict.</p>"
        if len(warnings) > len(visible_warnings) else ""
    )
    warning_items = "".join(f"<li>{esc(warning)}</li>" for warning in visible_warnings)
    warning_block = (
        f'''<details><summary>OTHER VERTICAL / INFRASTRUCTURE WARNINGS ({len(warnings)} TOTAL)</summary>{warning_notice}<ul>{warning_items}</ul></details>'''
        if warning_items else ""
    )
    scope_note = (
        " The verdict is scoped to configured gravel sources; other-vertical failures remain visible below but cannot make gravel coverage partial."
        if scoped else ""
    )
    return f'''<aside class="gw-coverage" id="source-coverage">
      <span>PRIVATE COLLECTION RECEIPT — NOT PUBLIC COPY</span>
      <h2>{esc(coverage['status'].upper())} COVERAGE</h2>
      <p>{coverage['runCount']} collection run{'s' if coverage['runCount'] != 1 else ''}{f"; {coverage['scopedRunCount']} carried vertical-scoped health" if scoped else ""}; latest completed {esc(coverage['latestSweepCompletedAt'])}. {"A partial receipt keeps every gravel-relevant gap visible for the human quiet-issue decision." if coverage['status'] == 'partial' else "Complete means every configured gravel lane and named source reported successfully; it does not claim sources outside the registry were watched."}{esc(scope_note)}</p>
      <ul class="gw-coverage-lanes">{lanes}</ul>
      <details><summary>SOURCES ATTEMPTED ({len(coverage['discoverySources'])})</summary><ul>{sources}</ul></details>
      {error_block}
      {warning_block}
    </aside>'''


def render_claim_markers(
    claim_ids: list[str], receipts: list[dict[str, Any]]
) -> str:
    receipt_by_claim = {
        receipt["claimId"]: (index, receipt)
        for index, receipt in enumerate(receipts, start=1)
    }
    markers = []
    for claim_id in claim_ids:
        item = receipt_by_claim.get(claim_id)
        if item is None:
            continue
        index, receipt = item
        markers.append(
            f'<a href="{esc(receipt["canonicalUrl"])}" rel="noopener" '
            f'target="_blank" aria-label="Source {index}: {esc(receipt["publisher"])}">'
            f'[{index}]</a>'
        )
    return f'<sup class="gw-claim-markers">{"".join(markers)}</sup>'


def render_cast(
    cast: list[dict[str, Any]], receipts: list[dict[str, Any]], story_id: str
) -> str:
    if not cast:
        return ""
    cards = "".join(
        f'''<article><span>{index:02d}</span><h4>{esc(member['name'])}</h4><p>{esc(member['role'])}{render_claim_markers(member['claimIds'], receipts)}</p></article>'''
        for index, member in enumerate(cast, start=1)
    )
    return f'''<section class="gw-cast" id="cast-{esc(story_id)}" aria-labelledby="cast-label-{esc(story_id)}">
      <header><span>THE CAST</span><h3 id="cast-label-{esc(story_id)}">WHO IS ACTUALLY IN THIS STORY</h3><p>Only sourced roles. No inferred motives or synthetic character sketches.</p></header>
      <div>{cards}</div>
    </section>'''


def render_field_notes(
    notes: list[dict[str, Any]], receipts: list[dict[str, Any]], story_id: str
) -> str:
    if not notes:
        return ""
    items = "".join(
        f'<li><span>{index:02d}</span><p>{esc(note["text"])}{render_claim_markers(note["claimIds"], receipts)}</p></li>'
        for index, note in enumerate(notes, start=1)
    )
    return f'''<section class="gw-field-notes" id="field-notes-{esc(story_id)}" aria-labelledby="field-notes-label-{esc(story_id)}">
      <header><span>FIELD NOTES</span><h3 id="field-notes-label-{esc(story_id)}">THE DETAILS THAT MAKE THE SCENE LEGIBLE</h3></header>
      <ol>{items}</ol>
    </section>'''


def render_impacts(impacts: list[dict[str, Any]]) -> str:
    meaningful = meaningful_impacts(impacts)
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
    return f'<section class="gw-retrospectives" id="memory"><h2>THE RECEIPTS ON US</h2><p class="gw-retro-dek">Old takes do not disappear when the timeline moves on.</p>{"".join(cards)}</section>'


def render_story(
    story: dict[str, Any], *, current: bool = False, draft: bool = False,
    date_label: str | None = None,
) -> str:
    label = "THE CURRENT THING" if current else story["storyKind"].replace("_", " ").upper()
    take_label = "THE TAKE — MODEL DRAFT" if draft else "THE TAKE"
    visual = render_story_visual(
        item_id=story["candidateId"],
        headline=story["headline"],
        body_text=" ".join([story["dek"], story["whatHappened"], story["take"]]),
        receipts=story["receipts"],
        date_label=date_label or story["storyKind"].replace("_", " "),
        story_poster=current,
    )
    return f'''<article class="gw-story{' gw-story--cover' if current else ''}" id="{esc(story['candidateId'])}">
      <header class="gw-story-head">
        <span class="gw-cover-line">{esc(label)}</span>
        <span class="gw-score">EDITORIAL SCORE {story['score']}/100</span>
        <h2>{esc(story['headline'])}</h2>
        <p class="gw-dek">{esc(story['dek'])}</p>
      </header>
      {visual}
      {render_cast(story.get('cast', []), story['receipts'], story['candidateId'])}
      <div class="gw-story-grid">
        <section class="gw-facts" id="record-{esc(story['candidateId'])}" aria-labelledby="record-label-{esc(story['candidateId'])}">
          <h3 id="record-label-{esc(story['candidateId'])}">THE RECORD</h3>
          {prose(story['whatHappened'])}
        </section>
        <section class="gw-take" id="take-{esc(story['candidateId'])}" aria-labelledby="take-label-{esc(story['candidateId'])}">
          <h3 id="take-label-{esc(story['candidateId'])}">{take_label}</h3>
          {prose(story['take'])}
        </section>
      </div>
      {render_field_notes(story.get('fieldNotes', []), story['receipts'], story['candidateId'])}
      {render_culture_artifacts(story.get('cultureArtifacts', []), private_review=draft, section_id=f"scene-{story['candidateId']}")}
      <details class="gw-details">
        <summary>RECEIPTS · {len(story['receipts'])}</summary>
        {render_receipts(story['receipts'])}
      </details>
      <details class="gw-details" id="changes-{esc(story['candidateId'])}">
        <summary>WHAT THIS CHANGES</summary>
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


def _issue_preview(issue: dict[str, Any]) -> tuple[str, str]:
    current = story_by_id(issue, issue.get("currentThingStoryId"))
    if current:
        return current["headline"], current["dek"]
    quiet = issue.get("quietIssue")
    if quiet:
        return quiet["headline"], quiet["note"]
    return issue["title"], "No manufactured Current Thing cleared the gate."


def render_issue_neighbors(issue: dict[str, Any], issues: list[dict[str, Any]]) -> str:
    """Keep dated issues visibly connected to the publication's chronology."""
    ordered = sorted(
        issues,
        key=lambda candidate: (candidate["publicationDate"], candidate["issueNumber"]),
    )
    active_index = next(
        (index for index, candidate in enumerate(ordered)
         if candidate["issueId"] == issue["issueId"]),
        None,
    )
    if active_index is None or len(ordered) < 2:
        return ""

    older = ordered[active_index - 1] if active_index > 0 else None
    newer = ordered[active_index + 1] if active_index + 1 < len(ordered) else None

    def link(candidate: dict[str, Any] | None, *, direction: str) -> str:
        if candidate is None:
            return '<span class="gw-neighbor-empty" aria-hidden="true"></span>'
        headline, deck = _issue_preview(candidate)
        excerpt = " ".join(deck.split())
        if len(excerpt) > 150:
            excerpt = f"{excerpt[:150].rstrip()}…"
        relation = "prev" if direction == "OLDER ISSUE" else "next"
        arrow = "←" if relation == "prev" else "→"
        direction_label = (
            f"{arrow} {direction}" if relation == "prev" else f"{direction} {arrow}"
        )
        return f'''<a class="gw-neighbor gw-neighbor--{relation}" href="/gravel-weekly/{esc(candidate['slug'])}/" rel="{relation}">
          <span>{esc(direction_label)}</span>
          <strong>#{candidate['issueNumber']:03d} · {esc(display_date(candidate['publicationDate']).upper())}</strong>
          <b>{esc(headline)}</b>
          <small>{esc(excerpt)}</small>
        </a>'''

    return f'''<nav class="gw-issue-neighbors" aria-label="Adjacent Gravel Weekly issues">
      {link(older, direction="OLDER ISSUE")}
      <p><span>YOU ARE HERE</span><b>ISSUE {active_index + 1} OF {len(ordered)}</b></p>
      {link(newer, direction="NEWER ISSUE")}
    </nav>'''


def _history_race_ids(entry: dict[str, Any]) -> set[str]:
    return {
        str(impact["raceId"])
        for impact in entry.get("raceImpacts", [])
        if impact.get("raceId")
    }


def _race_arc_name(race_id: str) -> str:
    _, slug = race_id.split(":", 1)
    return slug.replace("-", " ").upper()


def render_history_arc_navigation(
    entry: dict[str, Any], entries: list[dict[str, Any]]
) -> str:
    """Expose reviewed change-points sharing a race record, never inferred affinity."""
    race_ids = _history_race_ids(entry)
    if not race_ids:
        return ""
    related = sorted(
        (
            candidate
            for candidate in entries
            if race_ids & _history_race_ids(candidate)
        ),
        key=lambda candidate: (
            candidate["activeFrom"],
            candidate["activeThrough"],
            candidate["entryId"],
        ),
    )
    if len(related) < 2:
        return ""
    active_index = next(
        index
        for index, candidate in enumerate(related)
        if candidate["entryId"] == entry["entryId"]
    )
    start = max(0, active_index - 2)
    end = min(len(related), start + 5)
    start = max(0, end - 5)
    visible = related[start:end]
    shared_ids = sorted(
        race_id
        for race_id in race_ids
        if any(
            candidate["entryId"] != entry["entryId"]
            and race_id in _history_race_ids(candidate)
            for candidate in related
        )
    )
    arc_name = " + ".join(_race_arc_name(race_id) for race_id in shared_ids[:2])
    if len(shared_ids) > 2:
        arc_name += " + MORE"
    label_id = f'arc-label-{entry["entryId"]}'
    cards = []
    for candidate in visible:
        date = display_date(candidate["activeFrom"]).upper()
        body = f'''<span>{esc(date)}</span><b>{esc(candidate['headline'])}</b>'''
        if candidate["entryId"] == entry["entryId"]:
            cards.append(
                f'<li><span class="gw-story-arc-current" aria-current="location">'
                f'<em>YOU ARE HERE</em>{body}</span></li>'
            )
        else:
            cards.append(
                f'<li><a href="#{esc(candidate["entryId"])}">{body}</a></li>'
            )
    return f'''<nav class="gw-story-arc" aria-labelledby="{esc(label_id)}">
      <header><span>MORE FROM THIS RACE&rsquo;S STORY</span><h4 id="{esc(label_id)}">{esc(arc_name)} THROUGH TIME</h4><p>Reviewed change-points sharing the same race record. Chronological, never engagement-ranked.</p></header>
      <ol>{"".join(cards)}</ol>
    </nav>'''


def render_history_timeline(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return '''<section class="gw-history" id="season-story">
          <header class="gw-history-head"><span class="gw-label">THE PULSE OF GRAVEL</span><h2>THE SEASON AS A STORY</h2><p>The backfill is underway. Empty periods stay empty until a sourced point clears the gate.</p></header>
        </section>'''
    year_groups: dict[str, list[str]] = {}
    for entry in entries:
        year = entry["activeFrom"][:4]
        active_label = display_date(entry["activeFrom"])
        if entry["activeThrough"] != entry["activeFrom"]:
            active_label = f'{active_label} → {display_date(entry["activeThrough"])}'
        later = ""
        if entry["laterEvidence"]:
            later = f'''<details class="gw-history-later">
              <summary>LATER EVIDENCE — NOT AVAILABLE THEN · {len(entry['laterEvidence'])}</summary>
              {render_receipts(entry['laterEvidence'])}
            </details>'''
        visual = render_story_visual(
            item_id=entry["entryId"],
            headline=entry["headline"],
            body_text=" ".join([
                entry["point"],
                entry["whatHappened"],
                entry["stakes"],
                entry["take"],
            ]),
            receipts=entry["contemporaryReceipts"],
            date_label=active_label,
            stable_hash=entry["contentHash"],
            prior_judgment=entry["priorJudgment"],
            changed_judgment=entry["changedJudgment"],
            point=entry["point"],
        )
        card = f'''<!-- gravel-weekly-history-hash: {esc(entry['contentHash'])} -->
        <article class="gw-history-entry" id="{esc(entry['entryId'])}">
          <header><span class="gw-history-date">{esc(active_label.upper())}</span><span class="gw-score">EDITORIAL SCORE {entry['editorialScore']}/100</span><h3>{esc(entry['headline'])}</h3></header>
          {visual}
          <div class="gw-history-grid">
            <section><h4>THE POINT</h4>{prose(entry['point'])}<h4>THE RECORD</h4>{prose(entry['whatHappened'])}<h4>WHY IT MATTERED</h4>{prose(entry['stakes'])}<h4>THE FAIR OBJECTION</h4>{prose(entry['credibleOpposition'])}</section>
            <section class="gw-history-take"><h4>THE TAKE</h4>{prose(entry['take'])}</section>
          </div>
          <div class="gw-history-judgment"><b>WHAT CHANGED:</b> {esc(entry['priorJudgment'])} → {esc(entry['changedJudgment'])}</div>
          {render_history_arc_navigation(entry, entries)}
          <details class="gw-details"><summary>WHAT WAS KNOWABLE THEN · {len(entry['contemporaryReceipts'])}</summary>{render_receipts(entry['contemporaryReceipts'])}</details>
          {render_culture_artifacts(entry.get('cultureArtifacts', []))}
          {later}
          <p class="gw-history-uncertainty"><b>UNCERTAINTY:</b> {esc(entry['uncertainty'])}</p>
        </article>'''
        year_groups.setdefault(year, []).append(card)
    year_links = "".join(
        f'<li><a href="#gravel-year-{esc(year)}"><b>{esc(year)}</b><span>{len(cards)} change-point{"s" if len(cards) != 1 else ""}</span></a></li>'
        for year, cards in year_groups.items()
    )
    years = "".join(
        f'''<section class="gw-history-year" id="gravel-year-{esc(year)}" aria-label="Gravel in {esc(year)}">
          <header><span>YEAR IN THE STORY</span><strong>{esc(year)}</strong><p>{len(cards)} approved change-point{"s" if len(cards) != 1 else ""}</p></header>
          {"".join(cards)}
          <a class="gw-history-return" href="#gravel-history-years">BACK TO YEARS ↑</a>
        </section>'''
        for year, cards in year_groups.items()
    )
    return f'''<section class="gw-history" id="season-story">
      <header class="gw-history-head"><span class="gw-label">THE PULSE OF GRAVEL</span><h2>THE SEASON AS A STORY</h2><p>Only approved narrative change-points. Contemporary receipts stay separate from what we learned later.</p></header>
      <nav class="gw-history-years" id="gravel-history-years" aria-label="Jump to a year in gravel history"><span>JUMP TO YEAR</span><ol>{year_links}</ol></nav>
      <div class="gw-history-line">{years}</div>
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
  .gw-issue-neighbors { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); margin-top: var(--gg-spacing-md); border: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-neighbor { display: grid; align-content: start; gap: var(--gg-spacing-2xs); min-width: 0; padding: var(--gg-spacing-sm) var(--gg-spacing-md); color: inherit; text-decoration: none; }
  .gw-neighbor--prev { border-right: var(--gg-border-subtle); }
  .gw-neighbor--next { border-left: var(--gg-border-subtle); text-align: right; }
  .gw-neighbor > span, .gw-issue-neighbors > p span { color: var(--gg-color-gold); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wider); }
  .gw-neighbor > strong { font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-neighbor > b { overflow-wrap: anywhere; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-tight); }
  .gw-neighbor > small { color: var(--gg-color-tan); font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-normal); }
  .gw-neighbor:hover, .gw-neighbor:focus-visible { background: var(--gg-color-teal); outline: var(--gg-border-gold); outline-offset: calc(var(--gg-border-width-standard) * -1); }
  .gw-issue-neighbors > p { display: grid; place-content: center; gap: var(--gg-spacing-2xs); margin: 0; padding: var(--gg-spacing-sm) var(--gg-spacing-md); text-align: center; }
  .gw-issue-neighbors > p b { font-size: var(--gg-font-size-xs); white-space: nowrap; }
  .gw-contents { margin-top: var(--gg-spacing-xl); border: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-contents > header { display: flex; justify-content: space-between; gap: var(--gg-spacing-md); align-items: baseline; padding: var(--gg-spacing-sm) var(--gg-spacing-md); border-bottom: var(--gg-border-standard); }
  .gw-contents > header span { font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wider); }
  .gw-contents > header p { margin: 0; font-family: var(--gg-font-editorial); }
  .gw-contents ol { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); margin: 0; padding: 0; list-style: none; }
  .gw-contents li { min-width: 0; border-right: var(--gg-border-subtle); border-bottom: var(--gg-border-subtle); }
  .gw-contents a { display: grid; grid-template-columns: auto 1fr; gap: 0 var(--gg-spacing-xs); min-height: 100%; padding: var(--gg-spacing-sm); color: inherit; text-decoration: none; }
  .gw-contents a:hover, .gw-contents a:focus-visible { background: var(--gg-color-teal); outline: var(--gg-border-gold); outline-offset: calc(var(--gg-border-width-standard) * -1); }
  .gw-contents a > span { grid-row: 1 / span 2; color: var(--gg-color-gold); font-size: var(--gg-font-size-xl); font-weight: var(--gg-font-weight-black); line-height: .9; }
  .gw-contents b { font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-contents small { margin-top: var(--gg-spacing-2xs); color: var(--gg-color-tan); font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-tight); }
  .gw-story { margin-top: var(--gg-spacing-xl); border: var(--gg-border-heavy); background: var(--gg-color-white); }
  .gw-story--cover { border-width: calc(var(--gg-border-width-heavy) * 2); }
  .gw-story-head { padding: var(--gg-spacing-lg); border-bottom: var(--gg-border-standard); }
  .gw-cover-line, .gw-score, .gw-label { display: inline-block; font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wider); text-transform: uppercase; }
  .gw-cover-line { margin-right: var(--gg-spacing-xs); padding: var(--gg-spacing-2xs) var(--gg-spacing-xs); background: var(--gg-color-teal); color: var(--gg-color-white); }
  .gw-score { padding: var(--gg-spacing-2xs) var(--gg-spacing-xs); border: var(--gg-border-subtle); }
  .gw-story h2 { max-width: 900px; margin: var(--gg-spacing-md) 0 var(--gg-spacing-xs); font-family: var(--gg-font-editorial); font-size: clamp(2rem, 7vw, 4.8rem); line-height: .98; letter-spacing: var(--gg-letter-spacing-tight); }
  .gw-story:not(.gw-story--cover) h2 { font-size: clamp(1.8rem, 5vw, 3.4rem); }
  .gw-dek { max-width: 760px; margin: 0; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); line-height: var(--gg-line-height-normal); }
  .gw-cast { border-bottom: var(--gg-border-standard); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-cast > header, .gw-field-notes > header { padding: var(--gg-spacing-md); border-bottom: var(--gg-border-standard); }
  .gw-cast > header > span, .gw-field-notes > header > span { font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wider); }
  .gw-cast h3, .gw-field-notes h3 { margin: var(--gg-spacing-xs) 0 0; font-size: clamp(1.3rem, 4vw, 2.2rem); line-height: 1; }
  .gw-cast > header p { max-width: 760px; margin: var(--gg-spacing-xs) 0 0; font-family: var(--gg-font-editorial); }
  .gw-cast > div { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }
  .gw-cast article { display: grid; grid-template-columns: auto 1fr; gap: 0 var(--gg-spacing-sm); padding: var(--gg-spacing-md); border-right: var(--gg-border-subtle); border-bottom: var(--gg-border-subtle); }
  .gw-cast article > span { grid-row: 1 / span 2; color: var(--gg-color-gold); font-size: var(--gg-font-size-2xl); font-weight: var(--gg-font-weight-black); line-height: .9; }
  .gw-cast h4 { margin: 0; font-size: var(--gg-font-size-md); }
  .gw-cast article p { margin: var(--gg-spacing-2xs) 0 0; font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-normal); }
  .gw-story-grid { display: grid; grid-template-columns: minmax(0, 2fr) minmax(260px, 1fr); }
  .gw-story-grid section { padding: var(--gg-spacing-lg); }
  .gw-take { background: var(--gg-color-sand); border-left: var(--gg-border-standard); }
  .gw-story-grid h3 { margin: 0 0 var(--gg-spacing-sm); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wider); }
  .gw-story-grid p { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-relaxed); }
  .gw-take p { font-weight: var(--gg-font-weight-semibold); }
  .gw-field-notes { border-top: var(--gg-border-heavy); background: var(--gg-color-gold); }
  .gw-field-notes ol { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); margin: 0; padding: 0; list-style: none; }
  .gw-field-notes li { display: grid; grid-template-columns: auto 1fr; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-md); border-right: var(--gg-border-subtle); border-bottom: var(--gg-border-subtle); }
  .gw-field-notes li > span { font-size: var(--gg-font-size-2xl); font-weight: var(--gg-font-weight-black); line-height: .9; }
  .gw-field-notes li p { margin: 0; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-normal); }
  .gw-claim-markers { display: inline-flex; gap: var(--gg-spacing-2xs); margin-left: var(--gg-spacing-2xs); font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); vertical-align: super; }
  .gw-claim-markers a { color: inherit; font-weight: var(--gg-font-weight-black); }
  .gw-claim-markers a:focus-visible { outline: var(--gg-border-gold); outline-offset: var(--gg-spacing-2xs); }
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
  .gw-history { margin-top: var(--gg-spacing-2xl); border: var(--gg-border-heavy); background: var(--gg-color-white); scroll-margin-top: calc(var(--gg-header-height, 80px) + var(--gg-spacing-md)); }
  .gw-history-head { padding: var(--gg-spacing-lg); border-bottom: var(--gg-border-heavy); background: var(--gg-color-gold); }
  .gw-history-head h2 { margin: var(--gg-spacing-xs) 0; font-size: clamp(2rem, 6vw, 4.4rem); line-height: .95; }
  .gw-history-head p { max-width: 760px; margin: 0; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); }
  .gw-history-years { border-bottom: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-history-years > span { display: block; padding: var(--gg-spacing-xs) var(--gg-spacing-md); border-bottom: var(--gg-border-subtle); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wider); }
  .gw-history-years ol { display: flex; margin: 0; padding: 0; overflow-x: auto; list-style: none; scroll-snap-type: x proximity; }
  .gw-history-years li { flex: 1 0 150px; border-right: var(--gg-border-subtle); scroll-snap-align: start; }
  .gw-history-years a { display: grid; gap: var(--gg-spacing-2xs); min-height: 100%; padding: var(--gg-spacing-sm) var(--gg-spacing-md); color: inherit; text-decoration: none; }
  .gw-history-years a:hover, .gw-history-years a:focus-visible { background: var(--gg-color-teal); outline: var(--gg-border-gold); outline-offset: calc(var(--gg-border-width-standard) * -1); }
  .gw-history-years b { color: var(--gg-color-gold); font-size: var(--gg-font-size-2xl); line-height: .9; }
  .gw-history-years a span { color: var(--gg-color-tan); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); }
  .gw-history-line { position: relative; padding: var(--gg-spacing-lg); }
  .gw-history-line::before { content: ''; position: absolute; top: 0; bottom: 0; left: calc(var(--gg-spacing-lg) + 7px); width: var(--gg-border-width-standard); background: var(--gg-color-teal); }
  .gw-history-year { position: relative; scroll-margin-top: calc(var(--gg-header-height, 80px) + var(--gg-spacing-md)); }
  .gw-history-year + .gw-history-year { margin-top: var(--gg-spacing-2xl); }
  .gw-history-year > header { display: grid; grid-template-columns: auto 1fr; gap: 0 var(--gg-spacing-sm); margin: 0 0 var(--gg-spacing-md) var(--gg-spacing-lg); padding: var(--gg-spacing-sm) var(--gg-spacing-md); border: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-history-year > header span { grid-column: 1 / -1; font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wider); }
  .gw-history-year > header strong { color: var(--gg-color-gold); font-size: clamp(2.8rem, 8vw, 5rem); line-height: .8; }
  .gw-history-year > header p { align-self: end; margin: 0; color: var(--gg-color-tan); font-family: var(--gg-font-editorial); }
  .gw-history-entry { position: relative; margin: 0 0 var(--gg-spacing-xl) var(--gg-spacing-lg); border: var(--gg-border-heavy); background: var(--gg-color-warm-paper); }
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
  .gw-story-arc { border-top: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-story-arc > header { display: grid; grid-template-columns: minmax(0, 1fr) minmax(260px, .75fr); gap: var(--gg-spacing-2xs) var(--gg-spacing-lg); padding: var(--gg-spacing-sm) var(--gg-spacing-md); border-bottom: var(--gg-border-subtle); }
  .gw-story-arc > header > span { grid-column: 1 / -1; color: var(--gg-color-gold); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wider); }
  .gw-story-arc h4 { margin: 0; font-size: var(--gg-font-size-md); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-story-arc > header p { margin: 0; color: var(--gg-color-tan); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xs); }
  .gw-story-arc ol { display: flex; margin: 0; padding: 0; overflow-x: auto; list-style: none; scroll-snap-type: x proximity; }
  .gw-story-arc li { flex: 1 1 180px; min-width: 180px; border-right: var(--gg-border-subtle); scroll-snap-align: start; }
  .gw-story-arc a, .gw-story-arc-current { display: grid; align-content: start; gap: var(--gg-spacing-2xs); min-height: 100%; padding: var(--gg-spacing-sm) var(--gg-spacing-md); color: inherit; text-decoration: none; }
  .gw-story-arc a:hover, .gw-story-arc a:focus-visible { background: var(--gg-color-teal); outline: var(--gg-border-gold); outline-offset: calc(var(--gg-border-width-standard) * -1); }
  .gw-story-arc-current { background: var(--gg-color-gold); color: var(--gg-color-near-black); }
  .gw-story-arc-current em { font-size: var(--gg-font-size-xs); font-style: normal; font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-story-arc li span:not(.gw-story-arc-current) { color: var(--gg-color-tan); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-story-arc-current > span { color: var(--gg-color-near-black); }
  .gw-story-arc b { font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-sm); line-height: var(--gg-line-height-tight); }
  .gw-history-later { border-top: var(--gg-border-heavy); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }
  .gw-history-later summary { cursor: pointer; padding: var(--gg-spacing-sm) var(--gg-spacing-md); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-history-later a { color: var(--gg-color-gold); }
  .gw-history-return { display: block; width: fit-content; margin: calc(var(--gg-spacing-xl) * -1) 0 0 auto; padding: var(--gg-spacing-xs) var(--gg-spacing-sm); border: var(--gg-border-standard); background: var(--gg-color-white); color: var(--gg-color-near-black); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); text-decoration: none; }
  .gw-history-return:hover, .gw-history-return:focus-visible { background: var(--gg-color-gold); outline: var(--gg-border-standard); outline-offset: var(--gg-spacing-2xs); }
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
  .gw-quiet { scroll-margin-top: 7rem; margin-top: var(--gg-spacing-xl); padding: clamp(1.5rem, 5vw, 4rem); border: var(--gg-border-heavy); background: var(--gg-color-gold); color: var(--gg-color-near-black); }
  .gw-quiet > span { display: inline-block; font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-quiet h2 { max-width: 15ch; margin: var(--gg-spacing-sm) 0; font-family: var(--gg-font-editorial); font-size: clamp(2.25rem, 8vw, 5.5rem); line-height: .95; }
  .gw-quiet p { max-width: 48rem; margin: 0; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); line-height: var(--gg-line-height-relaxed); }
  .gw-coverage { margin-top: var(--gg-spacing-lg); padding: var(--gg-spacing-lg); border: var(--gg-border-heavy); background: var(--gg-color-warm-paper); }
  .gw-coverage > span { font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-coverage h2 { margin: var(--gg-spacing-xs) 0; font-size: clamp(1.5rem, 4vw, 2.5rem); }
  .gw-coverage p { max-width: 56rem; font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-relaxed); }
  .gw-coverage ul { margin: var(--gg-spacing-sm) 0; padding: 0; list-style: none; }
  .gw-coverage li { display: flex; justify-content: space-between; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-xs) 0; border-bottom: var(--gg-border-subtle); }
  .gw-coverage li span { text-align: right; }
  .gw-coverage details { margin-top: var(--gg-spacing-md); border-top: var(--gg-border-standard); padding-top: var(--gg-spacing-sm); }
  .gw-coverage summary { cursor: pointer; font-weight: var(--gg-font-weight-black); }
  code { font-family: var(--gg-font-data); overflow-wrap: anywhere; }
  @media (max-width: 720px) {
    .gw-issue-neighbors { grid-template-columns: 1fr; }
    .gw-neighbor--prev, .gw-neighbor--next, .gw-issue-neighbors > p { border: 0; border-bottom: var(--gg-border-subtle); text-align: left; }
    .gw-neighbor--next { border-bottom: 0; }
    .gw-neighbor-empty { display: none; }
    .gw-issue-neighbors > p { place-content: start; }
    .gw-contents > header { display: grid; }
    .gw-contents ol { display: flex; overflow-x: auto; scroll-snap-type: x proximity; }
    .gw-contents li { flex: 0 0 min(78vw, 260px); scroll-snap-align: start; }
    .gw-cover-lines, .gw-story-grid, .gw-utility-grid, .gw-memory-grid, .gw-history-grid { grid-template-columns: 1fr; }
    .gw-cover-lines span { border-right: 0; border-bottom: var(--gg-border-subtle); }
    .gw-cover-lines span:last-child { border-bottom: 0; }
    .gw-take { border-left: 0; border-top: var(--gg-border-standard); }
    .gw-memory-grid section + section { border-left: 0; border-top: var(--gg-border-standard); }
    .gw-history-take { border-left: 0; border-top: var(--gg-border-standard); }
    .gw-story-arc > header { grid-template-columns: 1fr; }
    .gw-story-arc li { flex: 0 0 min(76vw, 240px); min-width: 0; }
    .gw-story-head, .gw-story-grid section, .gw-utility, .gw-sub { padding: var(--gg-spacing-md); }
    .gw-coverage li { display: block; }
    .gw-coverage li span { display: block; margin-top: var(--gg-spacing-2xs); text-align: left; }
  }
''' + culture_css()


def build_page(issue: dict[str, Any] | None, issues: list[dict[str, Any]], *, latest: bool, history_entries: list[dict[str, Any]] | None = None) -> str:
    canonical_path = "/gravel-weekly/" if latest or issue is None else f"/gravel-weekly/{issue['slug']}/"
    canonical_url = f"{SITE_URL}{canonical_path}"
    if issue:
        is_draft = issue["status"] == "draft"
        current = story_by_id(issue, issue.get("currentThingStoryId"))
        other_stories = [story for story in issue["stories"] if story["candidateId"] != issue.get("currentThingStoryId")]
        title = f"Gravel Weekly #{issue['issueNumber']:03d} — {display_date(issue['publicationDate'])}"
        description = current["dek"] if current else issue["mastheadDeck"]
        quiet = issue.get("quietIssue")
        content = (
            render_story(
                current,
                current=True,
                draft=is_draft,
                date_label=display_date(issue["publicationDate"]),
            )
            if current else render_quiet_issue(quiet, draft=is_draft)
        )
        content += "".join(
            render_story(
                story,
                draft=is_draft,
                date_label=display_date(issue["publicationDate"]),
            )
            for story in other_stories
        )
        watch = "".join(f"<li>{esc(item)}</li>" for item in issue["calendarWatch"]) or '<li class="gw-empty">No calendar item cleared the gate.</li>'
        corrections = ""
        if issue["corrections"]:
            items = "".join(f'<li><strong>{esc(item["publishedAt"][:10])}</strong> — {esc(item["text"])}</li>' for item in issue["corrections"])
            corrections = f'<section class="gw-corrections" id="corrections"><h2>CORRECTIONS</h2><ul>{items}</ul></section>'
        utility = ""
        if issue["calendarWatch"] or issue["raceImpacts"]:
            utility = f'''<div class="gw-utility-grid">
          <section class="gw-utility"><h2>CALENDAR WATCH</h2><ul class="gw-watch">{watch}</ul></section>
          <section class="gw-utility"><h2>WHAT THIS CHANGES</h2>{render_impacts(issue['raceImpacts'])}</section>
        </div>'''
        issue_body = f'''{render_issue_contents(issue)}
        {content}
        {render_source_coverage_receipt(issue['sourceCoverage']) if is_draft and issue.get('sourceCoverage') else ''}
        {utility}
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
    neighbors = render_issue_neighbors(issue, issues) if issue and not latest else ""
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
{visual_css()}
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
    <div class="gw-cover-lines"><span>THE RECORD</span><span>THE SCENE</span><span>THE TAKE</span></div>
  </header>
  {neighbors}
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
    public_history_entries = load_public_history_entries(HISTORY_DIR)
    public_issues = load_public_issues(ISSUE_DIR)
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
