#!/usr/bin/env python3
"""Durable, rights-bounded Gravel Weekly culture cards."""

from __future__ import annotations

import html
import hashlib
import re
import textwrap
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


CULTURE_VISUAL_VERSION = "gravel-weekly-culture-visual/v1"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _timestamp_label(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f" · {seconds // 60}:{seconds % 60:02d}"


def _source_url(artifact: dict[str, Any]) -> str:
    """Make timestamped YouTube culture links land on the reviewed moment."""
    url = artifact["canonicalUrl"]
    seconds = artifact.get("timestampSeconds")
    if artifact.get("sourceKind") != "youtube" or seconds is None:
        return url
    parsed = urlsplit(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["t"] = f"{int(seconds)}s"
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return safe or "culture-artifact"


def _seed(artifact: dict[str, Any]) -> str:
    stable = "\n".join([
        str(artifact.get("artifactId", "")),
        str(artifact.get("canonicalUrl", "")),
        str(artifact.get("publishedAt", "")),
        str(artifact.get("title", "")),
    ])
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _svg_text_block(
    value: str, *, x: int, y: int, class_name: str,
    max_chars: int, max_lines: int, line_height: int,
) -> str:
    lines = textwrap.wrap(
        " ".join(value.split()),
        width=max_chars,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = f"{lines[-1][:max_chars - 1].rstrip()}…"
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if index == 0 else line_height}">{esc(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text class="{esc(class_name)}" x="{x}" y="{y}">{spans}</text>'


def _poster_marks(seed: str) -> str:
    marks: list[str] = []
    for index in range(0, 30, 6):
        x = 34 + (int(seed[index:index + 2], 16) % 568)
        y = 26 + (int(seed[index + 2:index + 4], 16) % 226)
        size = 8 + (int(seed[index + 4:index + 6], 16) % 24)
        marks.append(
            f'<rect x="{x}" y="{y}" width="{size}" height="{size}" '
            'transform="rotate(45 ' + f'{x + size // 2} {y + size // 2}' + ')" />'
        )
    return "".join(marks)


def _culture_poster(artifact: dict[str, Any], source_url: str) -> str:
    """Render local editorial artwork without copying or hotlinking source media."""
    safe_id = _safe_id(str(artifact["artifactId"]))
    seed = _seed(artifact)
    source_kind = str(artifact["sourceKind"]).upper()
    publisher = str(artifact.get("author") or artifact["publisher"])
    timestamp_seconds = artifact.get("timestampSeconds")
    is_timestamped_video = (
        artifact.get("sourceKind") == "youtube"
        and isinstance(timestamp_seconds, int)
        and not isinstance(timestamp_seconds, bool)
        and timestamp_seconds >= 0
    )
    if is_timestamped_video:
        timestamp = f"{timestamp_seconds // 60}:{timestamp_seconds % 60:02d}"
        title = (
            f"Timestamped source-video facade for {artifact['title']} at {timestamp}. "
            "No source image or video is embedded."
        )
        artwork = f'''
          <rect class="gw-culture-poster-screen" x="32" y="34" width="238" height="174" />
          <path class="gw-culture-poster-play" d="M118 78l74 43-74 43z" />
          <text class="gw-culture-poster-time" x="151" y="238" text-anchor="middle">WATCH @ {esc(timestamp)}</text>
          <text class="gw-culture-poster-kicker" x="304" y="62">TIMESTAMPED SOURCE VIDEO</text>
          {_svg_text_block(str(artifact['title']), x=304, y=103, class_name='gw-culture-poster-title', max_chars=20, max_lines=4, line_height=30)}
          <text class="gw-culture-poster-meta" x="304" y="238">{esc(publisher.upper())}</text>'''
        visual_kind = "video"
        caption_label = "SOURCE VIDEO // LOCAL FACADE"
        caption_text = f"Opens the reviewed moment at {timestamp}; no embed or thumbnail."
    else:
        topic_label = " / ".join(
            str(tag).upper() for tag in artifact.get("topicTags", [])[:3]
        ) or "CULTURE"
        title = (
            f"Abstract Gravel Weekly culture poster for {artifact['title']}. "
            "Context artwork, not a source image or documentary depiction."
        )
        artwork = f'''
          <g class="gw-culture-poster-marks" aria-hidden="true">{_poster_marks(seed)}</g>
          <rect class="gw-culture-poster-frame" x="28" y="28" width="584" height="224" />
          <text class="gw-culture-poster-kicker" x="52" y="62">FROM THE GROUP CHAT · {esc(source_kind)}</text>
          {_svg_text_block(str(artifact['title']), x=52, y=110, class_name='gw-culture-poster-title', max_chars=34, max_lines=3, line_height=34)}
          <text class="gw-culture-poster-meta" x="52" y="230">{esc(topic_label)}</text>
          <text class="gw-culture-poster-stamp" x="588" y="230" text-anchor="end">{esc(seed[:8].upper())}</text>'''
        visual_kind = "artifact"
        caption_label = "GW CULTURE DESK // AUTO"
        caption_text = "Abstract context poster; not the source image."
    return f'''<figure class="gw-culture-poster gw-culture-poster--{visual_kind}" data-culture-visual="{CULTURE_VISUAL_VERSION}">
      <a href="{esc(source_url)}" target="_blank" rel="noopener noreferrer" aria-label="Open the original {esc(source_kind)} culture source: {esc(artifact['title'])}">
        <svg viewBox="0 0 640 280" role="img" aria-labelledby="gw-culture-poster-title-{safe_id}" focusable="false">
          <title id="gw-culture-poster-title-{safe_id}">{esc(title)}</title>
          <rect class="gw-culture-poster-paper" x="0" y="0" width="640" height="280" />
          {artwork}
        </svg>
      </a>
      <figcaption><b>{caption_label}</b><span>{esc(caption_text)}</span></figcaption>
    </figure>'''


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
        source_url = _source_url(artifact)
        cards.append(f'''<article class="gw-culture-card" data-culture-artifact="{esc(artifact['artifactId'])}">
          {_culture_poster(artifact, source_url)}
          <div class="gw-culture-card-copy">
          <header><span>{esc(artifact['sourceKind'].upper())}</span><time datetime="{esc(artifact['publishedAt'])}">{esc(published)}</time></header>
          <h5>{esc(artifact['title'])}</h5>
          <p class="gw-culture-by">{esc(author)}</p>
          {excerpt}
          {review_reason}
          <a href="{esc(source_url)}" rel="noopener noreferrer" target="_blank">OPEN ORIGINAL{esc(timestamp)} →</a>
          </div>
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
  .gw-culture-card { display: flex; min-width: 0; flex-direction: column; background: var(--gg-color-warm-paper); color: var(--gg-color-near-black); }
  .gw-culture-card:only-child { grid-column: 1 / -1; }
  .gw-culture-card-copy { display: flex; flex: 1; min-width: 0; flex-direction: column; padding: var(--gg-spacing-md); }
  .gw-culture-card-copy > header { display: flex; justify-content: space-between; gap: var(--gg-spacing-sm); border: 0; padding: 0; font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-culture-card h5 { margin: var(--gg-spacing-md) 0 var(--gg-spacing-xs); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-xl); line-height: 1.05; }
  .gw-culture-by { margin: 0 0 var(--gg-spacing-sm); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-bold); text-transform: uppercase; }
  .gw-culture-card blockquote { flex: 1; margin: 0 0 var(--gg-spacing-md); padding-left: var(--gg-spacing-sm); border-left: var(--gg-border-gold); font-family: var(--gg-font-editorial); font-size: var(--gg-font-size-md); line-height: var(--gg-line-height-normal); }
  .gw-culture-card a { align-self: flex-start; color: var(--gg-color-primary-brown); font-size: var(--gg-font-size-xs); font-weight: var(--gg-font-weight-black); letter-spacing: var(--gg-letter-spacing-wide); }
  .gw-culture-reason { margin: 0 0 var(--gg-spacing-md); font-size: var(--gg-font-size-sm); line-height: var(--gg-line-height-normal); }
  .gw-culture-poster { margin: 0; border-bottom: var(--gg-border-standard); background: var(--gg-color-near-black); }
  .gw-culture-poster > a { display: block; width: 100%; color: inherit; }
  .gw-culture-poster > a:focus-visible { outline: var(--gg-border-gold); outline-offset: calc(var(--gg-border-width-standard) * -2); }
  .gw-culture-poster svg { display: block; width: 100%; height: auto; }
  .gw-culture-poster-paper { fill: var(--gg-color-sand); }
  .gw-culture-poster-frame { fill: var(--gg-color-warm-paper); stroke: var(--gg-color-near-black); stroke-width: 5; }
  .gw-culture-poster-marks { fill: var(--gg-color-teal); opacity: .72; }
  .gw-culture-poster-kicker, .gw-culture-poster-title, .gw-culture-poster-meta, .gw-culture-poster-stamp, .gw-culture-poster-time { fill: var(--gg-color-near-black); font-family: var(--gg-font-data); }
  .gw-culture-poster-kicker { font-size: 14px; font-weight: var(--gg-font-weight-black); letter-spacing: 2px; }
  .gw-culture-poster-title { font-size: 27px; font-weight: var(--gg-font-weight-black); }
  .gw-culture-poster-meta, .gw-culture-poster-stamp { font-size: 12px; font-weight: var(--gg-font-weight-black); letter-spacing: 1px; }
  .gw-culture-poster-screen { fill: var(--gg-color-near-black); stroke: var(--gg-color-teal); stroke-width: 8; }
  .gw-culture-poster-play { fill: var(--gg-color-gold); stroke: var(--gg-color-warm-paper); stroke-width: 5; }
  .gw-culture-poster-time { font-size: 17px; font-weight: var(--gg-font-weight-black); letter-spacing: 1px; }
  .gw-culture-poster figcaption { display: flex; justify-content: space-between; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-xs) var(--gg-spacing-sm); color: var(--gg-color-warm-paper); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; }
  @media (max-width: 700px) { .gw-culture-grid { grid-template-columns: 1fr; } }
  @media (max-width: 620px) {
    .gw-culture-poster-title { font-size: 23px; }
    .gw-culture-poster figcaption { display: grid; }
  }
'''
