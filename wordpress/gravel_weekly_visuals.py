#!/usr/bin/env python3
"""Deterministic, rights-safe visual system for Gravel Weekly stories."""

from __future__ import annotations

import hashlib
import html
import re
from typing import Any
from urllib.parse import parse_qs, urlparse


VISUAL_SYSTEM_VERSION = "gravel-weekly-visual/v1"
YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

THEMES = (
    (
        "category",
        "CATEGORY",
        (
            "handlebar",
            "drop bar",
            "flat bar",
            "category",
            "equipment rule",
            "banned the bike",
        ),
    ),
    (
        "community",
        "HOST COMMUNITY",
        ("community", "wildfire", "fire", "town", "business", "hotel", "recovery"),
    ),
    (
        "equity",
        "COST TRANSFER",
        ("women", "woman", "gender", "female", "traffic tax", "equal"),
    ),
    (
        "safety",
        "SAFETY SYSTEM",
        ("safety", "vehicle", "crash", "traffic", "feed zone", "intersection"),
    ),
    (
        "teams",
        "TEAMWORK",
        ("team", "privateer", "teammate", "roster", "squad", "organization"),
    ),
    (
        "governance",
        "GOVERNANCE",
        ("governing", "admission", "selection", "qualifier", "policy", "series"),
    ),
    (
        "course",
        "COURSE",
        ("route", "course", "distance", "terrain", "climb", "reroute"),
    ),
)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return safe or "story"


def _seed(*values: str) -> str:
    return hashlib.sha256("\n".join(values).encode("utf-8")).hexdigest()


def _compact_context_label(value: str) -> str:
    years = re.findall(r"\b20\d{2}\b", value)
    if years:
        return years[0] if len(set(years)) == 1 else f"{years[0]}–{years[-1]}"
    compact = " ".join(value.split()).upper()
    return compact[:28].rstrip()


def classify_theme(*values: str) -> tuple[str, str]:
    scores: dict[str, int] = {}
    labels: dict[str, str] = {}
    for theme, label, keywords in THEMES:
        labels[theme] = label
        score = 0
        for index, value in enumerate(values):
            weight = 8 if index == 0 else 1
            text = value.casefold()
            score += weight * sum(min(text.count(keyword), 3) for keyword in keywords)
        scores[theme] = score
    winner = max(scores, key=scores.get)
    if scores[winner] > 0:
        return winner, labels[winner]
    return "pulse", "THE CURRENT THING"


def youtube_video_id(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").casefold()
    candidate = ""
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/", 1)[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/")):
            parts = parsed.path.strip("/").split("/")
            candidate = parts[1] if len(parts) > 1 else ""
    return candidate if YOUTUBE_ID_RE.fullmatch(candidate) else None


def timestamped_youtube_receipt(receipts: list[dict[str, Any]]) -> dict[str, Any] | None:
    for receipt in receipts:
        seconds = receipt.get("transcriptStartSeconds")
        if (
            not isinstance(seconds, (int, float))
            or isinstance(seconds, bool)
            or seconds < 0
        ):
            continue
        video_id = youtube_video_id(str(receipt.get("canonicalUrl", "")))
        if video_id:
            return {**receipt, "videoId": video_id}
    return None


def _route_path(seed: str) -> str:
    values = [int(seed[index:index + 2], 16) for index in range(0, 12, 2)]
    y_values = [38 + (value % 104) for value in values]
    points = [
        (0, y_values[0]),
        (132, y_values[1]),
        (264, y_values[2]),
        (396, y_values[3]),
        (528, y_values[4]),
        (660, y_values[5]),
    ]
    commands = [f"M {points[0][0]} {points[0][1]}"]
    for index in range(1, len(points)):
        x0, y0 = points[index - 1]
        x1, y1 = points[index]
        midpoint = (x0 + x1) // 2
        commands.append(f"C {midpoint} {y0}, {midpoint} {y1}, {x1} {y1}")
    return " ".join(commands)


def _motif(theme: str) -> str:
    motifs = {
        "category": '''<g class="gw-visual-motif" aria-hidden="true">
          <path d="M62 64h102v72H62z M84 88h58 M113 64v72" />
          <path class="gw-visual-accent" d="M164 52v96 M180 64v72" />
        </g>''',
        "community": '''<g class="gw-visual-motif" aria-hidden="true">
          <path d="M52 128V82l38-30 38 30v46 M66 128V92h48v36" />
          <path class="gw-visual-accent" d="M142 128V70l28-22 28 22v58 M152 128V82h36v46" />
        </g>''',
        "equity": '''<g class="gw-visual-motif" aria-hidden="true">
          <path d="M50 58c44 0 44 80 88 80 M50 138c44 0 44-80 88-80" />
          <path class="gw-visual-accent" d="M154 48v100 M138 66l16-18 16 18 M138 130l16 18 16-18" />
        </g>''',
        "safety": '''<g class="gw-visual-motif" aria-hidden="true">
          <path d="M52 52h116v86H52z M68 70h84v50H68z" />
          <path class="gw-visual-accent" d="M110 76v38 M91 95h38" />
        </g>''',
        "teams": '''<g class="gw-visual-motif" aria-hidden="true">
          <path d="M52 54l58 42-58 42 M110 54v84 M168 54l-58 42 58 42" />
          <circle class="gw-visual-accent" cx="110" cy="96" r="20" />
        </g>''',
        "governance": '''<g class="gw-visual-motif" aria-hidden="true">
          <path d="M58 54h108v84H58z M76 72h72v48H76z M94 54v84 M130 54v84" />
          <path class="gw-visual-accent" d="M46 42h132v108H46z" />
        </g>''',
        "course": '''<g class="gw-visual-motif" aria-hidden="true">
          <circle cx="104" cy="96" r="50" />
          <circle class="gw-visual-accent" cx="104" cy="96" r="17" />
          <path d="M104 46v100 M54 96h100 M69 61l70 70 M139 61l-70 70" />
        </g>''',
        "pulse": '''<g class="gw-visual-motif" aria-hidden="true">
          <path d="M44 98h36l14-40 26 80 18-56 14 16h38" />
          <circle class="gw-visual-accent" cx="120" cy="98" r="52" />
        </g>''',
    }
    return motifs[theme]


def render_story_visual(
    *,
    item_id: str,
    headline: str,
    body_text: str,
    receipts: list[dict[str, Any]],
    date_label: str,
    stable_hash: str | None = None,
) -> str:
    """Render one automatic visual; factual source video wins over abstract art."""
    safe_id = _safe_id(item_id)
    theme, theme_label = classify_theme(headline, body_text)
    seed = _seed(stable_hash or "", item_id, headline, body_text)
    context_label = _compact_context_label(date_label)
    video = timestamped_youtube_receipt(receipts)
    if video:
        seconds = int(video["transcriptStartSeconds"])
        source_url = f'https://www.youtube.com/watch?v={video["videoId"]}&t={seconds}s'
        timestamp = f"{seconds // 60}:{seconds % 60:02d}"
        return f'''<figure class="gw-visual gw-visual--video" data-visual-system="{VISUAL_SYSTEM_VERSION}">
          <a class="gw-video-facade" href="{esc(source_url)}" target="_blank" rel="noopener noreferrer" aria-label="Watch the timestamped source video for {esc(headline)} on YouTube at {esc(timestamp)}">
            <svg viewBox="0 0 660 190" role="img" aria-labelledby="gw-video-title-{safe_id}" focusable="false">
              <title id="gw-video-title-{safe_id}">Timestamped source video for {esc(headline)}</title>
              <rect class="gw-visual-paper" x="0" y="0" width="660" height="190" />
              <path class="gw-visual-route" d="{_route_path(seed)}" pathLength="100" />
              <rect class="gw-video-screen" x="42" y="34" width="184" height="122" />
              <path class="gw-video-play" d="M112 68l55 27-55 27z" />
              <text class="gw-visual-kicker" x="260" y="61">TIMESTAMPED SOURCE VIDEO</text>
              <text class="gw-visual-word" x="260" y="113">WATCH @ {esc(timestamp)}</text>
              <text class="gw-visual-meta" x="260" y="145">{esc(str(video['publisher']).upper())} · {esc(context_label)}</text>
            </svg>
          </a>
          <figcaption><b>VERIFIED SOURCE VIDEO</b><span>The cited passage starts at {esc(timestamp)}. Opens on YouTube.</span></figcaption>
        </figure>'''

    particles = "".join(
        f'<circle cx="{238 + (int(seed[index:index + 2], 16) % 390)}" '
        f'cy="{24 + (int(seed[index + 2:index + 4], 16) % 142)}" '
        f'r="{2 + (int(seed[index + 4:index + 6], 16) % 5)}" />'
        for index in range(0, 30, 6)
    )
    return f'''<figure class="gw-visual gw-visual--{esc(theme)}" data-visual-system="{VISUAL_SYSTEM_VERSION}">
      <svg viewBox="0 0 660 190" role="img" aria-labelledby="gw-visual-title-{safe_id}" focusable="false">
        <title id="gw-visual-title-{safe_id}">Abstract Gravel Weekly editorial graphic for {esc(headline)}. Theme: {esc(theme_label)}. Not documentary imagery.</title>
        <rect class="gw-visual-paper" x="0" y="0" width="660" height="190" />
        <path class="gw-visual-route" d="{_route_path(seed)}" pathLength="100" />
        <g class="gw-visual-gravel" aria-hidden="true">{particles}</g>
        {_motif(theme)}
        <text class="gw-visual-kicker" x="238" y="61">GRAVEL WEEKLY · {esc(context_label)}</text>
        <text class="gw-visual-word" x="238" y="120">{esc(theme_label)}</text>
        <text class="gw-visual-meta" x="238" y="151">BUILT AUTOMATICALLY · {esc(seed[:8].upper())}</text>
      </svg>
      <figcaption><b>GW ART DEPT. // AUTO</b><span>Abstract story graphic, not a news photo.</span></figcaption>
    </figure>'''


def visual_css() -> str:
    return '''
  .gw-visual { margin: 0; border-bottom: var(--gg-border-standard); background: var(--gg-color-near-black); }
  .gw-visual svg { display: block; width: 100%; height: auto; max-height: 310px; }
  .gw-visual-paper { fill: var(--gg-color-sand); }
  .gw-visual-route { fill: none; stroke: var(--gg-color-teal); stroke-width: 18; stroke-linecap: square; opacity: .9; stroke-dasharray: 10 4; }
  .gw-visual-gravel circle { fill: var(--gg-color-primary-brown); opacity: .55; }
  .gw-visual-motif { fill: none; stroke: var(--gg-color-near-black); stroke-width: 9; }
  .gw-visual-motif .gw-visual-accent { fill: none; stroke: var(--gg-color-gold); stroke-width: 13; }
  .gw-visual-kicker, .gw-visual-meta, .gw-visual-word { fill: var(--gg-color-near-black); font-family: var(--gg-font-data); font-weight: var(--gg-font-weight-black); }
  .gw-visual-kicker { font-size: 16px; letter-spacing: 2px; }
  .gw-visual-word { font-size: 40px; letter-spacing: -2px; }
  .gw-visual-meta { font-size: 12px; letter-spacing: 1px; }
  .gw-visual figcaption { display: flex; justify-content: space-between; gap: var(--gg-spacing-sm); padding: var(--gg-spacing-xs) var(--gg-spacing-sm); color: var(--gg-color-warm-paper); font-size: var(--gg-font-size-xs); letter-spacing: var(--gg-letter-spacing-wide); text-transform: uppercase; }
  .gw-video-facade { display: block; color: inherit; }
  .gw-video-facade:focus-visible { outline: var(--gg-border-gold); outline-offset: calc(var(--gg-border-width-standard) * -2); }
  .gw-video-screen { fill: var(--gg-color-near-black); stroke: var(--gg-color-gold); stroke-width: 8; }
  .gw-video-play { fill: var(--gg-color-gold); stroke: var(--gg-color-warm-paper); stroke-width: 4; }
  .gw-visual--video .gw-visual-route { stroke: var(--gg-color-primary-brown); opacity: .35; }
  @media (prefers-reduced-motion: no-preference) {
    .gw-visual-route { animation: gw-route-pulse 16s linear infinite; }
    .gw-video-facade:hover .gw-video-play { transform: translateX(5px); transform-origin: center; transition: transform 140ms linear; }
  }
  @keyframes gw-route-pulse { to { stroke-dashoffset: -100; } }
  @media (max-width: 620px) {
    .gw-visual-word { font-size: 30px; }
    .gw-visual-kicker, .gw-visual-meta { display: none; }
    .gw-visual figcaption { display: grid; }
  }
'''
