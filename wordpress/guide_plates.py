#!/usr/bin/env python3
"""Inline SVG survey plates for guide chapter heroes."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any


RACE_INDEX_PATH = Path(__file__).parent.parent / "web" / "race-index.json"


def _esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _race_rows(data: dict | None) -> list[dict]:
    races = (data or {}).get("race_index")
    if isinstance(races, dict):
        return list(races.values())
    if isinstance(races, list):
        return races
    try:
        loaded = json.loads(RACE_INDEX_PATH.read_text(encoding="utf-8"))
    except OSError:
        return []
    return loaded if isinstance(loaded, list) else []


def _tier_distribution(data: dict | None) -> tuple[int, dict[int, int]]:
    rows = _race_rows(data)
    counts = Counter()
    for race in rows:
        try:
            tier = int(race.get("tier"))
        except (TypeError, ValueError):
            continue
        if 1 <= tier <= 4:
            counts[tier] += 1
    return len(rows), {tier: counts.get(tier, 0) for tier in range(1, 5)}


def _tier_bars(data: dict | None) -> str:
    total, counts = _tier_distribution(data)
    max_count = max(counts.values()) if counts else 1
    label = f"{total} RACES, RANKED"
    rows = [f'<text class="gg-plate-label gg-plate-label-strong" x="610" y="148">{_esc(label)}</text>']
    y = 184
    for tier in range(1, 5):
        count = counts[tier]
        width = 260 * (count / max_count) if max_count else 0
        rows.append(
            f'<text class="gg-plate-label" x="610" y="{y + 7}">T{tier}</text>'
            f'<rect class="gg-plate-bar-track" x="652" y="{y - 8}" width="276" height="16"></rect>'
            f'<rect class="gg-plate-bar-fill gg-plate-tier-{tier}" x="652" y="{y - 8}" width="{width:.1f}" height="16"></rect>'
            f'<text class="gg-plate-label" x="946" y="{y + 7}">{count}</text>'
        )
        y += 38
    return "\n".join(rows)


def _motif(chapter_number: int, data: dict | None) -> str:
    motifs = {
        1: '''
<path class="gg-plate-line gg-plate-line-soft" d="M584 306 C628 270 654 338 696 290 S760 248 800 288 866 342 934 278"></path>
<path class="gg-plate-line" d="M604 360 C646 326 686 372 724 336 S802 296 842 332 894 382 962 322"></path>
<path class="gg-plate-line gg-plate-line-soft" d="M628 414 C682 386 716 422 762 394 S842 356 906 404"></path>
''',
        2: _tier_bars(data),
        3: '''
<line class="gg-plate-line" x1="610" y1="300" x2="950" y2="300"></line>
<rect class="gg-plate-zone gg-plate-zone-1" x="610" y="264" width="68" height="72"></rect>
<rect class="gg-plate-zone gg-plate-zone-2" x="678" y="264" width="68" height="72"></rect>
<rect class="gg-plate-zone gg-plate-zone-3" x="746" y="264" width="68" height="72"></rect>
<rect class="gg-plate-zone gg-plate-zone-4" x="814" y="264" width="68" height="72"></rect>
<rect class="gg-plate-zone gg-plate-zone-5" x="882" y="264" width="68" height="72"></rect>
<text class="gg-plate-label" x="630" y="358">Z1</text><text class="gg-plate-label" x="698" y="358">Z2</text><text class="gg-plate-label" x="766" y="358">Z3</text><text class="gg-plate-label" x="834" y="358">Z4</text><text class="gg-plate-label" x="902" y="358">Z5</text>
''',
        4: '''
<rect class="gg-plate-signal gg-plate-signal-red" x="628" y="252" width="84" height="84"></rect>
<rect class="gg-plate-signal gg-plate-signal-gold" x="748" y="252" width="84" height="84"></rect>
<rect class="gg-plate-signal gg-plate-signal-teal" x="868" y="252" width="84" height="84"></rect>
<path class="gg-plate-check" d="M650 294 l14 14 l28 -32"></path>
<path class="gg-plate-check" d="M770 294 l14 14 l28 -32"></path>
<path class="gg-plate-check" d="M890 294 l14 14 l28 -32"></path>
''',
        5: '''
<line class="gg-plate-line" x1="610" y1="302" x2="952" y2="302"></line>
<line class="gg-plate-line" x1="650" y1="270" x2="650" y2="334"></line>
<line class="gg-plate-line" x1="780" y1="270" x2="780" y2="334"></line>
<line class="gg-plate-line" x1="910" y1="270" x2="910" y2="334"></line>
<text class="gg-plate-label gg-plate-label-strong" x="622" y="358">30g/hr</text>
<text class="gg-plate-label gg-plate-label-strong" x="752" y="358">60g/hr</text>
<text class="gg-plate-label gg-plate-label-strong" x="882" y="358">90g/hr</text>
''',
        6: '''
<path class="gg-plate-line" d="M610 356 C660 252 710 252 760 330 S850 430 944 250"></path>
<rect class="gg-plate-dot" x="645" y="283" width="10" height="10"></rect>
<rect class="gg-plate-dot" x="755" y="325" width="10" height="10"></rect>
<rect class="gg-plate-dot" x="887" y="295" width="10" height="10"></rect>
<text class="gg-plate-label" x="626" y="246">CALM</text>
<text class="gg-plate-label" x="730" y="380">DIP</text>
<text class="gg-plate-label" x="850" y="256">COMMIT</text>
''',
        7: '''
<line class="gg-plate-line" x1="612" y1="304" x2="952" y2="304"></line>
<line class="gg-plate-line" x1="632" y1="270" x2="632" y2="338"></line>
<line class="gg-plate-line" x1="732" y1="270" x2="732" y2="338"></line>
<line class="gg-plate-line" x1="832" y1="270" x2="832" y2="338"></line>
<line class="gg-plate-line" x1="932" y1="270" x2="932" y2="338"></line>
<text class="gg-plate-label" x="612" y="362">-7D</text><text class="gg-plate-label" x="712" y="362">-3D</text><text class="gg-plate-label" x="812" y="362">-1D</text><text class="gg-plate-label" x="912" y="362">RACE</text>
''',
        8: '''
<path class="gg-plate-line gg-plate-line-soft" d="M610 294 C686 290 708 418 768 396 S826 250 944 244"></path>
<path class="gg-plate-line" d="M610 338 C680 338 716 338 758 338 S860 338 952 338"></path>
<rect class="gg-plate-dot" x="753" y="333" width="10" height="10"></rect>
<rect class="gg-plate-dot" x="881" y="253" width="10" height="10"></rect>
<text class="gg-plate-label" x="716" y="420">RECOVER</text>
<text class="gg-plate-label" x="834" y="232">ADAPT</text>
''',
    }
    return motifs.get(chapter_number, motifs[1])


def render_chapter_plate(chapter_number: int, data: dict | None) -> str:
    """Return the inline SVG survey plate for a guide chapter hero."""
    variant = "dark" if chapter_number in {2, 4, 6, 8} else "light"
    return f'''<svg class="gg-guide-plate gg-guide-plate--{variant}" viewBox="0 0 1000 520" role="img" aria-label="Chapter {chapter_number} survey plate" focusable="false" xmlns="http://www.w3.org/2000/svg">
  <style>
    .gg-guide-plate .gg-plate-bg{{fill:var(--gg-color-warm-paper)}}
    .gg-guide-plate .gg-plate-rule,.gg-guide-plate .gg-plate-line,.gg-guide-plate .gg-plate-check{{fill:none;stroke:var(--gg-color-primary-brown);stroke-width:2;stroke-linecap:square;stroke-linejoin:miter}}
    .gg-guide-plate .gg-plate-rule-soft,.gg-guide-plate .gg-plate-line-soft{{stroke:var(--gg-color-secondary-brown);opacity:.42}}
    .gg-guide-plate .gg-plate-numeral{{font-family:var(--gg-font-editorial);font-size:360px;font-weight:700;fill:var(--gg-color-tan);opacity:.24}}
    .gg-guide-plate .gg-plate-label{{font-family:var(--gg-font-data);font-size:16px;font-weight:700;letter-spacing:2px;fill:var(--gg-color-primary-brown)}}
    .gg-guide-plate .gg-plate-label-strong{{fill:var(--gg-color-dark-brown)}}
    .gg-guide-plate .gg-plate-dot,.gg-guide-plate .gg-plate-bar-fill,.gg-guide-plate .gg-plate-zone,.gg-guide-plate .gg-plate-signal{{fill:var(--gg-color-teal)}}
    .gg-guide-plate .gg-plate-bar-track{{fill:var(--gg-color-sand)}}
    .gg-guide-plate .gg-plate-tier-1,.gg-guide-plate .gg-plate-signal-red{{fill:var(--gg-color-primary-brown)}}
    .gg-guide-plate .gg-plate-tier-2,.gg-guide-plate .gg-plate-signal-gold{{fill:var(--gg-color-gold)}}
    .gg-guide-plate .gg-plate-tier-3{{fill:var(--gg-color-teal)}}
    .gg-guide-plate .gg-plate-tier-4{{fill:var(--gg-color-secondary-brown)}}
    .gg-guide-plate .gg-plate-zone-1{{opacity:.24}}.gg-guide-plate .gg-plate-zone-2{{opacity:.36}}.gg-guide-plate .gg-plate-zone-3{{opacity:.48}}.gg-guide-plate .gg-plate-zone-4{{opacity:.62}}.gg-guide-plate .gg-plate-zone-5{{opacity:.78}}
    .gg-guide-plate--dark .gg-plate-bg{{fill:var(--gg-color-dark-brown)}}
    .gg-guide-plate--dark .gg-plate-rule,.gg-guide-plate--dark .gg-plate-line,.gg-guide-plate--dark .gg-plate-check{{stroke:var(--gg-color-tan)}}
    .gg-guide-plate--dark .gg-plate-rule-soft,.gg-guide-plate--dark .gg-plate-line-soft{{stroke:var(--gg-color-warm-brown);opacity:.42}}
    .gg-guide-plate--dark .gg-plate-numeral{{fill:var(--gg-color-primary-brown);opacity:.46}}
    .gg-guide-plate--dark .gg-plate-label{{fill:var(--gg-color-sand)}}
    .gg-guide-plate--dark .gg-plate-label-strong{{fill:var(--gg-color-white)}}
    .gg-guide-plate--dark .gg-plate-bar-track{{fill:var(--gg-color-primary-brown)}}
    .gg-guide-plate--dark .gg-plate-check{{stroke:var(--gg-color-white);stroke-width:4}}
  </style>
  <rect class="gg-plate-bg" x="0" y="0" width="1000" height="520"></rect>
  <path class="gg-plate-rule gg-plate-rule-soft" d="M40 48 H960 M40 472 H960 M500 72 V448"></path>
  <path class="gg-plate-rule" d="M560 112 H960 M560 430 H960"></path>
  <text class="gg-plate-numeral" x="694" y="382">{chapter_number}</text>
  {_motif(chapter_number, data)}
</svg>'''
