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

from brand_tokens import get_tokens_css  # noqa: E402
from validate_gravel_weekly_history import HISTORY_DIR, load_history_entries  # noqa: E402


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def paragraphs(value: str) -> str:
    return "".join(
        f"<p>{esc(block.strip())}</p>"
        for block in value.split("\n\n")
        if block.strip()
    )


def approval_holds(entry: dict[str, Any]) -> list[str]:
    holds = [name for name, verdict in entry["editorialGates"].items() if verdict != "pass"]
    publishers = {
        receipt["publisher"].strip().casefold()
        for receipt in entry["contemporaryReceipts"]
    }
    if len(publishers) < 2:
        holds.append("two-publisher corroboration")
    return holds


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


def _card(entry: dict[str, Any]) -> str:
    holds = approval_holds(entry)
    readiness = (
        '<span class="ready">READY FOR MATTI</span>'
        if not holds
        else f'<span class="hold">HOLD · {esc(", ".join(holds))}</span>'
    )
    gate_rows = "".join(
        f"<li><b>{esc(name)}</b><span>{esc(verdict.upper())}</span></li>"
        for name, verdict in entry["editorialGates"].items()
    )
    decision_instruction = (
        f'Tell Codex <q>approve {esc(entry["entryId"])}</q>, '
        '<q>reject … because …</q>, or give an edited headline/Take.'
        if not holds
        else "Resolve the named hold or reject this premise. Approval fails closed while any hold remains."
    )
    return f'''<article class="story" id="{esc(entry['entryId'])}">
      <header>
        <div class="eyebrow">{esc(entry['activeFrom'])} → {esc(entry['activeThrough'])} · SCORE {entry['editorialScore']}</div>
        <h2>{esc(entry['headline'])}</h2>
        <div class="status">{readiness}<code>{esc(entry['entryId'])}</code></div>
      </header>
      <section class="point"><h3>THE POINT</h3>{paragraphs(entry['point'])}</section>
      <div class="judgment">
        <section><h3>BEFORE</h3>{paragraphs(entry['priorJudgment'])}</section>
        <section><h3>AFTER</h3>{paragraphs(entry['changedJudgment'])}</section>
      </div>
      <section><h3>WHAT HAPPENED</h3>{paragraphs(entry['whatHappened'])}</section>
      <section class="take"><h3>THE TAKE · MODEL DRAFT</h3>{paragraphs(entry['take'])}</section>
      <div class="judgment">
        <section><h3>STAKES</h3>{paragraphs(entry['stakes'])}</section>
        <section><h3>CREDIBLE OPPOSITION</h3>{paragraphs(entry['credibleOpposition'])}</section>
      </div>
      <section><h3>UNCERTAINTY</h3>{paragraphs(entry['uncertainty'])}</section>
      <details open><summary>CONTEMPORARY RECEIPTS ({len(entry['contemporaryReceipts'])})</summary>{_receipt_list(entry['contemporaryReceipts'])}</details>
      <details><summary>LATER EVIDENCE ({len(entry['laterEvidence'])})</summary>{_receipt_list(entry['laterEvidence'])}</details>
      <details><summary>GATES &amp; RACE INTELLIGENCE</summary><ul class="gates">{gate_rows}</ul>{_impact_list(entry['raceImpacts'])}</details>
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
    drafts = [entry for entry in selected if entry["status"] == "draft"]
    ready = sum(not approval_holds(entry) for entry in drafts)
    held = len(drafts) - ready
    cards = "".join(_card(entry) for entry in drafts)
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow"><title>Gravel Weekly {year} Historical Review</title>
<style>
{get_tokens_css()}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--gg-color-sand); color: var(--gg-color-near-black); font-family: var(--gg-font-data); }}
main {{ width: min(1120px, calc(100% - 32px)); margin: 32px auto 80px; }}
.desk-head {{ border: var(--gg-border-heavy); background: var(--gg-color-gold); padding: var(--gg-spacing-lg); }}
.desk-head h1 {{ margin: 0; font-size: clamp(2.4rem, 8vw, 6rem); line-height: .85; }}
.desk-head p {{ max-width: 800px; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-lg); }}
.summary {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
.summary b, .ready, .hold {{ border: var(--gg-border-standard); padding: 6px 10px; background: var(--gg-color-warm-paper); }}
.hold {{ background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }}
.story {{ margin-top: 32px; border: var(--gg-border-heavy); background: var(--gg-color-warm-paper); }}
.story > header, .story > section, .story > div, .story > details, .story > footer {{ padding: var(--gg-spacing-lg); border-top: var(--gg-border-standard); }}
.story > header {{ border-top: 0; background: var(--gg-color-white); }}
.story h2 {{ margin: 8px 0 16px; max-width: 900px; font-family: var(--gg-font-editorial); font-size: clamp(2rem, 6vw, 4rem); line-height: .95; }}
.story h3 {{ margin: 0 0 8px; letter-spacing: var(--gg-letter-spacing-wide); }}
.story p {{ max-width: 900px; font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-relaxed); }}
.status {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }}
.judgment {{ display: grid; grid-template-columns: 1fr 1fr; padding: 0 !important; }}
.judgment section {{ padding: var(--gg-spacing-lg); }} .judgment section + section {{ border-left: var(--gg-border-standard); }}
.point {{ background: var(--gg-color-gold); }} .take {{ background: var(--gg-color-sand); }}
summary {{ cursor: pointer; font-weight: var(--gg-font-weight-black); }}
.receipts li {{ margin: 16px 0; }} blockquote {{ margin: 8px 0; font-family: var(--gg-font-editorial); }}
.gates {{ max-width: 520px; padding: 0; list-style: none; }} .gates li {{ display: flex; justify-content: space-between; border-bottom: var(--gg-border-subtle); padding: 8px 0; }}
code {{ overflow-wrap: anywhere; }} footer {{ background: var(--gg-color-near-black); color: var(--gg-color-warm-paper); }} footer code {{ color: var(--gg-color-light-gold); }}
@media (max-width: 700px) {{ .judgment {{ grid-template-columns: 1fr; }} .judgment section + section {{ border-left: 0; border-top: var(--gg-border-standard); }} main {{ width: min(100% - 16px, 1120px); margin-top: 8px; }} }}
</style></head><body><main>
  <header class="desk-head"><div class="eyebrow">PRIVATE EDITORIAL DESK · NOT PUBLIC</div><h1>{year}<br>THE SEASON<br>AS A STORY</h1>
  <p>This queue contains narrative change-points, not one required story per week. Review the point first, then the Take. Receipts from the active period are separated from evidence learned later.</p>
  <div class="summary"><b>{len(drafts)} DRAFTS</b><b>{ready} READY FOR HUMAN DECISION</b><b>{held} HELD BY EVIDENCE OR EDITORIAL GATES</b></div></header>
  {cards or '<section class="story"><header><h2>No draft historical entries for this year.</h2></header></section>'}
</main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (
        PROJECT_ROOT / "data" / "gravel-weekly" / "history-review" / f"{args.year}.html"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = load_history_entries(HISTORY_DIR)
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
