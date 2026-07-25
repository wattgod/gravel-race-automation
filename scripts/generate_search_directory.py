#!/usr/bin/env python3
"""Regenerate the crawlable race directory inside the search widget."""

from __future__ import annotations

import argparse
import html
import json
import re
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = PROJECT_ROOT / "web" / "race-index.json"
DEFAULT_WIDGET = PROJECT_ROOT / "web" / "gravel-race-search.html"

BEGIN_MARKER = "  <!-- BEGIN GENERATED RACE DIRECTORY -->"
END_MARKER = "  <!-- END GENERATED RACE DIRECTORY -->"
LEGACY_BEGIN = (
    "  <!-- Static Race Directory — crawlable by search engines, independent of JS -->"
)
LEGACY_END = "  <!-- End Race Directory -->"

TIER_NAMES = {
    1: "The Icons",
    2: "Elite",
    3: "Solid",
    4: "Grassroots",
}
DISCIPLINE_LABELS = {
    "gravel": "gravel",
    "mtb": "MTB",
    "bikepacking": "bikepacking",
}


def _list_phrase(values: list[str]) -> str:
    if not values:
        return "cycling"
    if len(values) == 1:
        return values[0]
    if len(values) == 2:
        return f"{values[0]} and {values[1]}"
    return f"{', '.join(values[:-1])}, and {values[-1]}"


def render_directory(races: list[dict]) -> str:
    """Render an escaped, index-driven static directory block."""
    by_tier = defaultdict(list)
    series = defaultdict(list)
    disciplines = []

    for race in races:
        by_tier[int(race.get("tier", 4))].append(race)
        discipline = race.get("discipline", "gravel")
        if discipline not in disciplines:
            disciplines.append(discipline)
        if race.get("series_id"):
            series[(race["series_id"], race.get("series_name") or race["series_id"])].append(race)

    ordered_disciplines = [
        DISCIPLINE_LABELS[discipline]
        for discipline in ("gravel", "mtb", "bikepacking")
        if discipline in disciplines
    ]
    discipline_phrase = _list_phrase(ordered_disciplines)

    lines = [
        BEGIN_MARKER,
        "  <!-- Crawlable by search engines and regenerated from web/race-index.json. -->",
        '  <div class="gg-race-directory">',
        '    <h2 class="gg-directory-heading">Race Directory</h2>',
        (
            '    <p class="gg-directory-desc">Browse all '
            f"{len(races)} {html.escape(discipline_phrase)} races rated by "
            "Gravel God. Click any race for the full review with course maps, "
            "ratings, and logistics.</p>"
        ),
    ]

    for tier in (1, 2, 3, 4):
        tier_races = sorted(
            by_tier.get(tier, []),
            key=lambda race: (str(race.get("name", "")).casefold(), race["slug"]),
        )
        lines.extend(
            [
                '    <div class="gg-directory-tier">',
                (
                    f'      <h3 class="gg-directory-tier-heading tier-{tier}">'
                    f"Tier {tier} — {TIER_NAMES[tier]} ({len(tier_races)})</h3>"
                ),
                '      <div class="gg-directory-links">',
            ]
        )
        for race in tier_races:
            slug = html.escape(race["slug"], quote=True)
            name = html.escape(str(race.get("name") or race["slug"]))
            lines.append(
                f'        <a href="/race/{slug}/" '
                f'class="gg-directory-link">{name}</a>'
            )
        lines.extend(["      </div>", "    </div>"])

    if series:
        lines.extend(
            [
                '    <div class="gg-directory-tier">',
                (
                    '      <h3 class="gg-directory-tier-heading tier-series">'
                    "Race Series</h3>"
                ),
                '      <div class="gg-directory-links">',
            ]
        )
        for (series_id, series_name), members in sorted(
            series.items(), key=lambda item: item[0][1].casefold()
        ):
            escaped_id = html.escape(series_id, quote=True)
            escaped_name = html.escape(series_name)
            lines.append(
                f'        <a href="/race/series/{escaped_id}/" '
                f'class="gg-directory-link">{escaped_name} '
                f"({len(members)} events)</a>"
            )
        lines.extend(["      </div>", "    </div>"])

    lines.extend(["  </div>", END_MARKER])
    return "\n".join(lines)


def replace_directory(widget_html: str, directory_html: str) -> str:
    """Replace either the generated markers or the legacy hand-authored block."""
    if BEGIN_MARKER in widget_html and END_MARKER in widget_html:
        pattern = (
            re.escape(BEGIN_MARKER)
            + r".*?"
            + re.escape(END_MARKER)
        )
    elif LEGACY_BEGIN in widget_html and LEGACY_END in widget_html:
        pattern = re.escape(LEGACY_BEGIN) + r".*?" + re.escape(LEGACY_END)
    else:
        raise ValueError("race-directory markers not found in search widget")

    updated, replacements = re.subn(
        pattern,
        directory_html,
        widget_html,
        count=1,
        flags=re.DOTALL,
    )
    if replacements != 1:
        raise ValueError(f"expected one race-directory block, replaced {replacements}")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Regenerate the search widget's static race directory"
    )
    parser.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    parser.add_argument("--widget", type=Path, default=DEFAULT_WIDGET)
    args = parser.parse_args()

    races = json.loads(args.index.read_text(encoding="utf-8"))
    directory_html = render_directory(races)
    updated = replace_directory(
        args.widget.read_text(encoding="utf-8"),
        directory_html,
    )
    args.widget.write_text(updated, encoding="utf-8")
    print(f"Generated search directory: {len(races)} races in {args.widget}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
