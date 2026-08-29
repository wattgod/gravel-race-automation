#!/usr/bin/env python3
"""Render a private, read-only editorial desk for historical narrative drafts."""

from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

from brand_tokens import get_font_face_css, get_tokens_css  # noqa: E402
from gravel_weekly_visuals import render_story_visual, visual_css  # noqa: E402
from gravel_weekly_culture import culture_css, render_culture_artifacts  # noqa: E402
from no_ai_slop import audit_no_ai_slop  # noqa: E402
from approve_gravel_weekly_history import (  # noqa: E402
    reviewed_headline_copy,
    reviewed_take_copy,
)
from validate_gravel_weekly_history import HISTORY_DIR, load_history_entries  # noqa: E402


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def paragraphs(value: str) -> str:
    return "".join(
        f"<p>{esc(block.strip())}</p>"
        for block in value.split("\n\n")
        if block.strip()
    )


def prose_gate(entry: dict[str, Any]) -> dict[str, object]:
    return audit_no_ai_slop({
        "headline": entry["headline"],
        "what_happened": entry["whatHappened"],
        "take": entry["take"],
    })


def approval_holds(
    entry: dict[str, Any], gate: dict[str, object] | None = None
) -> list[str]:
    holds = [name for name, verdict in entry["editorialGates"].items() if verdict != "pass"]
    publishers = {
        receipt["publisher"].strip().casefold()
        for receipt in entry["contemporaryReceipts"]
    }
    if len(publishers) < 2:
        holds.append("two-publisher corroboration")
    if (gate or prose_gate(entry))["verdict"] != "pass":
        holds.append("no-AI-slop prose gate")
    return holds


def review_priority(entry: dict[str, Any]) -> tuple[int, int, str, str]:
    """Put publishable decisions before research debt without hiding either."""
    return (
        1 if approval_holds(entry) else 0,
        -entry["editorialScore"],
        entry["activeFrom"],
        entry["entryId"],
    )


def review_years(entries: list[dict[str, Any]]) -> list[int]:
    years: set[int] = set()
    for entry in entries:
        if entry["status"] != "draft":
            continue
        first = int(entry["activeFrom"][:4])
        last = int(entry["activeThrough"][:4])
        years.update(range(first, last + 1))
    return sorted(years, reverse=True)


def _receipt_list(receipts: list[dict[str, Any]]) -> str:
    if not receipts:
        return '<p class="empty">None.</p>'
    rows = []
    for receipt in receipts:
        published = datetime.fromisoformat(receipt["publishedAt"].replace("Z", "+00:00"))
        rows.append(
            '<li><a href="{url}" rel="noopener" target="_blank">{publisher} · {date}</a>'
            '<blockquote>{excerpt}</blockquote><code>{claim}</code></li>'.format(
                url=esc(receipt["canonicalUrl"]),
                publisher=esc(receipt["publisher"]),
                date=published.strftime("%b %-d, %Y"),
                excerpt=esc(receipt["quoteExcerpt"]),
                claim=esc(receipt["claimId"]),
            )
        )
    return f'<ol class="receipts">{"".join(rows)}</ol>'


def _impact_list(impacts: list[dict[str, Any]]) -> str:
    if not impacts:
        return '<p class="empty">No race-profile implication proposed.</p>'
    return '<ul class="impacts">{}</ul>'.format(
        "".join(
            "<li><b>{race}</b> · {field} · editorial review only · no auto-fix</li>".format(
                race=esc(impact["raceId"]),
                field=esc(impact.get("fieldPath") or "unspecified field"),
            )
            for impact in impacts
        )
    )


def _story_contents(entry: dict[str, Any]) -> str:
    """Map a long review card without manufacturing unavailable departments."""
    entry_id = entry["entryId"]
    chapters = [
        (f"#{entry_id}-point", "THE POINT"),
        (f"#{entry_id}-record", "THE RECORD"),
        (f"#{entry_id}-take", "THE TAKE"),
        (f"#{entry_id}-opposition", "THE OTHER SIDE"),
        (f"#{entry_id}-receipts", "THE RECEIPTS"),
    ]
    if entry.get("cultureArtifacts"):
        chapters.append((f"#{entry_id}-scene", "THE SCENE REPORT"))
    chapters.append((f"#{entry_id}-changes", "WHAT THIS CHANGES"))
    items = "".join(
        f'<li><a href="{esc(target)}"><span>{index:02d}</span>{esc(label)}</a></li>'
        for index, (target, label) in enumerate(chapters, start=1)
    )
    return f'<nav class="story-contents" aria-label="Sections in {esc(reviewed_headline_copy(entry))}"><ol>{items}</ol></nav>'


def _card(entry: dict[str, Any]) -> str:
    gate = prose_gate(entry)
    holds = approval_holds(entry, gate)
    readiness = (
        '<span class="ready">READY FOR MATTI</span>'
        if not holds
        else f'<span class="hold">HOLD · {esc(", ".join(holds))}</span>'
    )
    gate_notes = entry.get("editorialGateNotes") or {}
    gate_rows = "".join(
        '<li class="gate-{verdict}"><div><b>{name}</b><span>{verdict_label}</span></div>{note}</li>'.format(
            verdict=esc(verdict),
            name=esc(name),
            verdict_label=esc(verdict.upper()),
            note=(
                f'<p><b>WHY {esc(verdict.upper())}:</b> {esc(gate_notes[name])}</p>'
                if name in gate_notes else ""
            ),
        )
        for name, verdict in entry["editorialGates"].items()
    )
    prose_findings = gate["findings"]
    prose_finding_rows = (
        "".join(
            "<li><b>{field} · {pattern}</b><span>{excerpt}</span></li>".format(
                field=esc(finding["field"]),
                pattern=esc(finding["pattern"]),
                excerpt=esc(finding["excerpt"]),
            )
            for finding in prose_findings
        )
        if prose_findings
        else '<li><b>PASS</b><span>No deterministic findings.</span></li>'
    )
    prose_summary = (
        f'NO-AI-SLOP PROSE GATE · {esc(str(gate["verdict"]).upper())}'
    )
    decision_instruction = (
        f'Tell Codex <q>approve {esc(entry["entryId"])}</q>, '
        '<q>reject … because …</q>, or give an edited headline/Take.'
        if not holds
        else "Resolve the named hold or reject this premise. Approval fails closed while any hold remains."
    )
    visual = render_story_visual(
        item_id=entry["entryId"],
        headline=reviewed_headline_copy(entry),
        body_text=" ".join([
            entry["point"],
            entry["whatHappened"],
            entry["stakes"],
            reviewed_take_copy(entry),
        ]),
        receipts=entry["contemporaryReceipts"],
        date_label=f"{entry['activeFrom']} → {entry['activeThrough']}",
        stable_hash=entry["contentHash"],
        prior_judgment=entry["priorJudgment"],
        changed_judgment=entry["changedJudgment"],
        point=entry["point"],
    )
    return f'''<article class="story" id="{esc(entry['entryId'])}">
      <header>
        <div class="eyebrow">{esc(entry['activeFrom'])} → {esc(entry['activeThrough'])} · SCORE {entry['editorialScore']}</div>
        <h2>{esc(reviewed_headline_copy(entry))}</h2>
        <div class="status">{readiness}<code>{esc(entry['entryId'])}</code></div>
      </header>
      {visual}
      {_story_contents(entry)}
      <section class="point" id="{esc(entry['entryId'])}-point"><h3>THE POINT</h3>{paragraphs(entry['point'])}</section>
      <div class="judgment">
        <section><h3>BEFORE</h3>{paragraphs(entry['priorJudgment'])}</section>
        <section><h3>AFTER</h3>{paragraphs(entry['changedJudgment'])}</section>
      </div>
      <section id="{esc(entry['entryId'])}-record"><h3>THE RECORD</h3>{paragraphs(entry['whatHappened'])}</section>
      <section class="take" id="{esc(entry['entryId'])}-take"><h3>THE TAKE · MODEL DRAFT</h3>{paragraphs(reviewed_take_copy(entry))}</section>
      <div class="judgment">
        <section><h3>STAKES</h3>{paragraphs(entry['stakes'])}</section>
        <section id="{esc(entry['entryId'])}-opposition"><h3>THE OTHER SIDE</h3>{paragraphs(entry['credibleOpposition'])}</section>
      </div>
      <section><h3>UNCERTAINTY</h3>{paragraphs(entry['uncertainty'])}</section>
      <details open id="{esc(entry['entryId'])}-receipts"><summary>CONTEMPORARY RECEIPTS ({len(entry['contemporaryReceipts'])})</summary>{_receipt_list(entry['contemporaryReceipts'])}</details>
      {render_culture_artifacts(entry.get('cultureArtifacts', []), private_review=True, section_id=f"{entry['entryId']}-scene")}
      <details><summary>LATER EVIDENCE ({len(entry['laterEvidence'])})</summary>{_receipt_list(entry['laterEvidence'])}</details>
      <details open><summary>{prose_summary}</summary><p>Checked against <a href="{esc(gate['sourceUrl'])}" rel="noopener" target="_blank">petergyang/no-ai-slop</a> at <code>{esc(str(gate['sourceRevision'])[:8])}</code>. This is a prose-pattern gate, not an AI-authorship detector.</p><ul class="prose-findings">{prose_finding_rows}</ul></details>
      <details id="{esc(entry['entryId'])}-changes"><summary>WHAT THIS CHANGES · GATES &amp; RACE INTELLIGENCE</summary><ul class="gates">{gate_rows}</ul>{_impact_list(entry['raceImpacts'])}</details>
      <footer>
        <p><b>DECIDE:</b> {decision_instruction} Any decision binds to this exact draft hash and still does not publish.</p>
        <code>{esc(entry['contentHash'])}</code>
      </footer>
    </article>'''


def render_history_review(entries: list[dict[str, Any]], year: int) -> str:
    selected = [
        entry for entry in entries
        if entry["activeFrom"] <= f"{year}-12-31" and entry["activeThrough"] >= f"{year}-01-01"
    ]
    drafts = sorted(
        (entry for entry in selected if entry["status"] == "draft"),
        key=review_priority,
    )
    ready_entries = [entry for entry in drafts if not approval_holds(entry)]
    held_entries = [entry for entry in drafts if approval_holds(entry)]
    ready_entry_ids = {entry["entryId"] for entry in ready_entries}
    ready = len(ready_entries)
    held = len(held_entries)
    queue = "".join(
        '<li><a href="#{entry_id}"><span>{status}</span><b>{headline}</b>'
        '<code>{content_hash}</code></a></li>'.format(
            entry_id=esc(entry["entryId"]),
            status="READY" if entry["entryId"] in ready_entry_ids else "HOLD",
            headline=esc(reviewed_headline_copy(entry)),
            content_hash=esc(entry["contentHash"][:12]),
        )
        for entry in drafts
    )
    ready_ids = ", ".join(entry["entryId"] for entry in ready_entries)
    bulk_instruction = (
        f'<p class="bulk"><b>ONE-LINE APPROVAL:</b> If—and only if—you agree with every READY headline and Take, reply '
        f'<q>approve all READY {year} entries as written</q>. That instruction is limited to: <code>{esc(ready_ids)}</code>. '
        "HOLD entries remain excluded and cannot be rescued by bulk approval.</p>"
        if ready_entries
        else '<p class="bulk"><b>NO BULK APPROVAL AVAILABLE.</b> Every draft is held.</p>'
    )
    cards = "".join(_card(entry) for entry in drafts)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Gravel Weekly {year} Historical Review</title>
<style>
{get_tokens_css()}
{get_font_face_css()}
{visual_css()}
{culture_css()}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--gg-color-sand); color: var(--gg-color-near-black); font-family: var(--gg-font-data); }}
main {{ width: min(1120px, calc(100% - 32px)); margin: 32px auto 80px; }}
.desk-back {{ display: inline-block; margin-bottom: var(--gg-spacing-sm); color: inherit; font-weight: var(--gg-font-weight-black); }}
.desk-head {{ border: var(--gg-border-heavy); background: var(--gg-color-gold); padding: var(--gg-spacing-lg); }}
.desk-head h1 {{ margin: 0; font-size: clamp(2.4rem, 8vw, 6rem); line-height: .85; }}
.desk-head p {{ max-width: 800px; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); }}
.summary {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
.summary b, .ready, .hold {{ border: var(--gg-border-standard); padding: 6px 10px; background: var(--gg-color-warm-paper); }}
.hold {{ background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }}
.bulk {{ max-width: none !important; margin: 20px 0 0; border: var(--gg-border-standard); background: var(--gg-color-warm-paper); padding: var(--gg-spacing-md); }}
.bulk q {{ font-weight: var(--gg-font-weight-black); }}
.decision-queue {{ margin-top: 20px; border: var(--gg-border-standard); background: var(--gg-color-white); }}
.decision-queue h2 {{ margin: 0; padding: 10px 12px; border-bottom: var(--gg-border-standard); }}
.decision-queue ol {{ margin: 0; padding: 0; list-style: none; }}
.decision-queue li + li {{ border-top: var(--gg-border-subtle); }}
.decision-queue a {{ display: grid; grid-template-columns: 64px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 12px; color: inherit; text-decoration: none; }}
.decision-queue a:hover, .decision-queue a:focus-visible {{ background: var(--gg-color-sand); }}
.decision-queue span {{ font-weight: var(--gg-font-weight-black); }}
.story {{ margin-top: 32px; border: var(--gg-border-heavy); background: var(--gg-color-warm-paper); }}
.story > header, .story > section, .story > div, .story > details, .story > footer {{ padding: var(--gg-spacing-lg); border-top: var(--gg-border-standard); }}
.story > header {{ border-top: 0; background: var(--gg-color-white); }}
.story h2 {{ margin: 8px 0 16px; max-width: 900px; font-family: var(--gg-font-editorial); font-size: clamp(2rem, 6vw, 4rem); line-height: .95; }}
.story-contents {{ padding: 0 !important; background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }}
.story-contents ol {{ display: flex; margin: 0; padding: 0; overflow-x: auto; list-style: none; scroll-snap-type: x proximity; }}
.story-contents li {{ flex: 1 0 150px; border-right: var(--gg-border-subtle); scroll-snap-align: start; }}
.story-contents a {{ display: grid; grid-template-columns: auto 1fr; gap: var(--gg-spacing-xs); align-items: center; min-height: 100%; padding: var(--gg-spacing-sm); color: inherit; font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); text-decoration: none; }}
.story-contents a:hover, .story-contents a:focus-visible {{ background: var(--gg-color-teal); outline: var(--gg-border-gold); outline-offset: calc(var(--gg-border-width-standard) * -1); }}
.story-contents span {{ color: var(--gg-color-gold); font-size: var(--gg-font-size-xl); line-height: .9; }}
.story h3 {{ margin: 0 0 8px; letter-spacing: var(--gg-letter-spacing-wide); }}
.story p {{ max-width: 900px; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-relaxed); }}
.status {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
.judgment {{ display: grid; grid-template-columns: 1fr 1fr; padding: 0 !important; }}
.judgment section {{ padding: var(--gg-spacing-lg); }} .judgment section + section {{ border-left: var(--gg-border-standard); }}
.point {{ background: var(--gg-color-gold); }} .take {{ background: var(--gg-color-sand); }}
summary {{ cursor: pointer; font-weight: var(--gg-font-weight-black); }}
.receipts li {{ margin: 16px 0; }} blockquote {{ margin: 8px 0; font-family: var(--gg-font-editorial); }}
.gates {{ max-width: 760px; padding: 0; list-style: none; }}
.gates li {{ border-bottom: var(--gg-border-subtle); padding: 8px 0; }}
.gates li > div {{ display: flex; justify-content: space-between; gap: var(--gg-spacing-md); }}
.gates li > p {{ margin: var(--gg-spacing-xs) 0 0; padding: var(--gg-spacing-sm); border-left: var(--gg-border-gold); background: var(--gg-color-sand); font-size: var(--gg-font-size-sm); }}
.gates .gate-hold > div span, .gates .gate-fail > div span {{ font-weight: var(--gg-font-weight-black); }}
code {{ overflow-wrap: anywhere; }} footer {{ background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }} footer code {{ color: var(--gg-color-light-gold); }}
@media (max-width: 700px) {{ .judgment {{ grid-template-columns: 1fr; }} .judgment section + section {{ border-left: 0; border-top: var(--gg-border-standard); }} .decision-queue a {{ grid-template-columns: 56px minmax(0, 1fr); }} .decision-queue code {{ grid-column: 2; }} main {{ width: min(100% - 16px, 1120px); margin-top: 8px; }} }}
</style></head><body><main>
  <a class="desk-back" href="index.html">← ALL YEARS</a>
  <header class="desk-head"><div class="eyebrow">PRIVATE EDITORIAL DESK · NOT PUBLIC</div><h1>{year}<br>THE SEASON<br>AS A STORY</h1>
  <p>This queue contains narrative change-points, not one required story per week. Review the point first, then the Take. Receipts from the active period are separated from evidence learned later.</p>
  <div class="summary"><b>{len(drafts)} DRAFTS</b><b>{ready} READY FOR HUMAN DECISION</b><b>{held} HELD BY EVIDENCE, EDITORIAL, OR PROSE GATES</b></div>
  {bulk_instruction}
  <nav class="decision-queue" aria-label="Historical story decision queue"><h2>DECISION QUEUE</h2><ol>{queue}</ol></nav></header>
  {cards or '<section class="story"><header><h2>No draft historical entries for this year.</h2></header></section>'}
</main></body></html>'''


def render_history_review_index(entries: list[dict[str, Any]]) -> str:
    """Render one private map of the full newest-to-oldest decision queue."""
    rows = []
    total_ready = 0
    total_held = 0
    years = review_years(entries)
    for year in years:
        drafts = sorted(
            (
                entry for entry in entries
                if entry["status"] == "draft"
                and entry["activeFrom"] <= f"{year}-12-31"
                and entry["activeThrough"] >= f"{year}-01-01"
            ),
            key=review_priority,
        )
        ready = [entry for entry in drafts if not approval_holds(entry)]
        held = [entry for entry in drafts if approval_holds(entry)]
        total_ready += len(ready)
        total_held += len(held)
        highlights = "".join(
            '<li><span>{score}</span><b>{headline}</b></li>'.format(
                score=entry["editorialScore"],
                headline=esc(reviewed_headline_copy(entry)),
            )
            for entry in ready[:3]
        ) or '<li class="empty">No entry clears every gate yet.</li>'
        rows.append(f'''<article class="year-card">
          <a href="{year}.html" aria-label="Review Gravel Weekly historical drafts for {year}">
            <header><span>REVIEW YEAR</span><h2>{year}</h2></header>
            <div class="counts"><b>{len(ready)} READY</b><b>{len(held)} HOLD</b></div>
            <ol>{highlights}</ol>
            <footer>OPEN {year} DESK →</footer>
          </a>
        </article>''')
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Gravel Weekly Historical Review Desk</title>
<style>
{get_tokens_css()}
{get_font_face_css()}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--gg-color-sand); color: var(--gg-color-near-black); font-family: var(--gg-font-data); }}
main {{ width: min(1120px, calc(100% - 32px)); margin: 32px auto 80px; }}
.desk-head {{ border: var(--gg-border-heavy); background: var(--gg-color-gold); padding: var(--gg-spacing-lg); }}
.desk-head h1 {{ max-width: 900px; margin: var(--gg-spacing-xs) 0; font-size: clamp(2.5rem, 9vw, 6.5rem); line-height: .84; }}
.desk-head p {{ max-width: 820px; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); line-height: var(--gg-line-height-normal); }}
.summary {{ display: flex; flex-wrap: wrap; gap: var(--gg-spacing-xs); margin-top: var(--gg-spacing-md); }}
.summary b {{ border: var(--gg-border-standard); padding: var(--gg-spacing-xs) var(--gg-spacing-sm); background: var(--gg-color-warm-paper); }}
.years {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--gg-spacing-md); margin-top: var(--gg-spacing-lg); }}
.year-card {{ border: var(--gg-border-heavy); background: var(--gg-color-white); }}
.year-card a {{ display: flex; min-height: 100%; flex-direction: column; color: inherit; text-decoration: none; }}
.year-card a:hover, .year-card a:focus-visible {{ background: var(--gg-color-warm-paper); outline: var(--gg-border-gold); outline-offset: 3px; }}
.year-card header {{ padding: var(--gg-spacing-md); border-bottom: var(--gg-border-standard); }}
.year-card header span {{ font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); letter-spacing: var(--gg-letter-spacing-wide); }}
.year-card h2 {{ margin: 0; font-size: clamp(3.2rem, 8vw, 5rem); line-height: .9; }}
.counts {{ display: grid; grid-template-columns: 1fr 1fr; border-bottom: var(--gg-border-standard); }}
.counts b {{ padding: var(--gg-spacing-xs); text-align: center; }}
.counts b + b {{ border-left: var(--gg-border-standard); background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }}
.year-card ol {{ flex: 1; margin: 0; padding: var(--gg-spacing-md) var(--gg-spacing-md) var(--gg-spacing-md) calc(var(--gg-spacing-xl) + var(--gg-spacing-xs)); }}
.year-card li {{ margin-bottom: var(--gg-spacing-sm); font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-normal); }}
.year-card li span {{ display: inline-block; margin-right: var(--gg-spacing-xs); font-family: var(--gg-font-data); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); }}
.year-card footer {{ padding: var(--gg-spacing-sm) var(--gg-spacing-md); border-top: var(--gg-border-standard); background: var(--gg-color-teal); color: var(--gg-color-white); font-weight: var(--gg-font-weight-black); }}
.empty {{ font-style: italic; }}
@media (max-width: 860px) {{ .years {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
@media (max-width: 580px) {{ .years {{ grid-template-columns: 1fr; }} main {{ width: min(100% - 16px, 1120px); margin-top: 8px; }} }}
</style></head><body><main>
  <header class="desk-head"><div>PRIVATE EDITORIAL DESK · NOT PUBLIC</div><h1>THE WHOLE<br>GRAVEL STORY</h1>
  <p>Start with 2026, then work backward. Inside each year, entries that clear every evidence, editorial, hostile-editor, and prose gate come first. HOLD entries remain visible research debt; this index cannot approve, seal, publish, or edit anything.</p>
  <div class="summary"><b>{len(years)} YEARS</b><b>{total_ready} READY FOR HUMAN DECISION</b><b>{total_held} HELD</b></div></header>
  <section class="years" aria-label="Historical review years">{"".join(rows)}</section>
</main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--year", type=int)
    mode.add_argument("--all", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "gravel-weekly" / "history-review",
    )
    args = parser.parse_args()
    entries = load_history_entries(HISTORY_DIR)
    if args.all:
        if args.output is not None:
            parser.error("--output cannot be combined with --all; use --output-dir")
        args.output_dir.mkdir(parents=True, exist_ok=True)
        years = review_years(entries)
        for year in years:
            target = args.output_dir / f"{year}.html"
            target.write_text(render_history_review(entries, year), encoding="utf-8")
        index = args.output_dir / "index.html"
        index.write_text(render_history_review_index(entries), encoding="utf-8")
        print(f"Rendered {len(years)} private yearly desks plus index: {index}")
        return 0

    output = args.output or args.output_dir / f"{args.year}.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_history_review(entries, args.year), encoding="utf-8")
    selected = [
        entry for entry in entries
        if entry["activeFrom"] <= f"{args.year}-12-31"
        and entry["activeThrough"] >= f"{args.year}-01-01"
        and entry["status"] == "draft"
    ]
    print(f"Rendered {len(selected)} private historical drafts: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
