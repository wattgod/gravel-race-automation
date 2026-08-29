#!/usr/bin/env python3
"""Durable, rights-bounded Gravel Weekly culture cards."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _timestamp_label(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f" · {seconds // 60}:{seconds % 60:02d}"


def render_culture_artifacts(
    artifacts: list[dict[str, Any]], *, private_review: bool = False,
    section_id: str | None = None,
) -> str:
    if not artifacts:
        return ""
    cards: list[str] = []
    for artifact in artifacts:
        published = datetime.fromisoformat(
            artifact["publishedAt"].replace("Z", "+00:00")
        ).strftime("%b %-d, %Y")
        author = artifact.get("author") or artifact["publisher"]
        excerpt = (
            f'<blockquote>{esc(artifact["excerpt"])}</blockquote>'
            if artifact.get("excerpt") else ""
        )
        review_reason = (
            f'<p class="gw-culture-reason"><b>WHY IT IS HERE:</b> '
            f'{esc(artifact["reviewReason"])}</p>'
            if private_review else ""
        )
        timestamp = _timestamp_label(artifact.get("timestampSeconds"))
        cards.append(f'''<article class="gw-culture-card" data-culture-artifact="{esc(artifact['artifactId'])}">
          <header><span>{esc(artifact['sourceKind'].upper())}</span><time datetime="{esc(artifact['publishedAt'])}">{esc(published)}</time></header>
          <h5>{esc(artifact['title'])}</h5>
          <p class="gw-culture-by">{esc(author)}</p>
          {excerpt}
          {review_reason}
          <a href="{esc(artifact['canonicalUrl'])}" rel="noopener noreferrer" target="_blank">OPEN ORIGINAL{esc(timestamp)} →</a>
        </article>''')
    mode = "PRIVATE CULTURE CHECK" if private_review else "THE SCENE REPORT"
    explanation = (
        "These are the jokes, arguments, personalities, and artifacts the desk thinks help reconstruct the moment. "
        "They are context—not proof, consensus, or a substitute for the point."
    )
    id_attribute = f' id="{esc(section_id)}"' if section_id else ""
    return f'''<section class="gw-culture"{id_attribute} aria-label="Culture artifacts">
      <header><span>{mode}</span><h4>WHAT THE GROUP CHAT WAS PASSING AROUND</h4><p>{explanation}</p></header>
      <div class="gw-culture-grid">{"".join(cards)}</div>
    </section>'''


def culture_css() -> str:
    return '''
  .gw-culture { border-top: var(--gg-border-heavy); background: var(--gg-color-teal); color: var(--gg-color-white); }
  .gw-culture > header { padding: var(--gg-spacing-md); border-bottom: var(--gg-border-standard); }
  .gw-culture > header > span { display: inline-block; padding: var(--gg-spacing-2xs) var(--gg-spacing-xs); border: var(--gg-border-subtle); background: var(--gg-color-gold); color: var(--gg-color-near-black); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-culture > header h4 { margin: var(--gg-spacing-xs) 0; font-size: clamp(1.4rem, 4vw, 2.4rem); line-height: 1; }
  .gw-culture > header p { max-width: 760px; margin: 0; font-family: var(--gg-font-editorial); line-height: var(--gg-line-height-normal); }
  .gw-culture-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--gg-border-width-standard); background: var(--gg-color-near-black); }
  .gw-culture-card { display: flex; min-width: 0; flex-direction: column; padding: var(--gg-spacing-md); background: var(--gg-color-warm-paper); color: var(--gg-color-near-black); }
  .gw-culture-card > header { display: flex; justify-content: space-between; gap: var(--gg-spacing-sm); border: 0; padding: 0; font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-culture-card h5 { margin: var(--gg-spacing-md) 0 var(--gg-spacing-xs); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xl); line-height: 1.05; }
  .gw-culture-by { margin: 0 0 var(--gg-spacing-sm); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); text-transform: uppercase; }
  .gw-culture-card blockquote { flex: 1; margin: 0 0 var(--gg-spacing-md); padding-left: var(--gg-spacing-sm); border-left: var(--gg-border-gold); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-normal); }
  .gw-culture-card a { align-self: flex-start; color: var(--gg-color-primary-brown); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-culture-reason { margin: 0 0 var(--gg-spacing-md); font-size: var(--gg-font-size-sm); line-height: var(--gg-line-height-normal); }
  @media (max-width: 700px) { .gw-culture-grid { grid-template-columns: 1fr; } }
'''
