#!/usr/bin/env python3
"""Generate the Gravel God homepage OG image (1200x630) -> og/homepage.jpg.

This is also the site-wide fallback card for pages without their own image,
so it carries the brand rather than any one page's pitch. Copy and numbers
come from the homepage generator itself (kicker, H1, hero stat counters), so
the card can't drift from the page the way the Feb-2026 hardcoded one did
("328 races / 14 dimensions" long after the site said 384 / 15).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

import og_brand as og  # noqa: E402
from generate_homepage import (  # noqa: E402
    CURRENT_YEAR, compute_stats, load_race_index,
)

HEADLINE = "Every gravel race, rated."  # homepage hero H1


def generate(output_dir: Path | None = None) -> Path:
    stats = compute_stats(load_race_index())
    img, draw = og.new_card()

    y = 196
    og.kicker(draw, (og.MARGIN, y), [(f"THE {CURRENT_YEAR} RACE DATABASE", og.GOLD)])

    font, lines = og.fit_headline(draw, HEADLINE, og.W - 2 * og.MARGIN,
                                  sizes=(104, 96, 88), max_lines=1)
    y += 44
    for line in lines:
        draw.text((og.MARGIN, y), line, font=font, fill=og.DARK_BROWN)
        y += round(font.size * 1.12)

    # Hero stat counters, same three the homepage shows, same order.
    rule_y = 452
    draw.rectangle([og.MARGIN, rule_y, og.W - og.MARGIN, rule_y + 2], fill=og.DARK_BROWN)
    num_font, lab_font = og.mono(64, bold=True), og.mono(18, bold=True)
    col_w = (og.W - 2 * og.MARGIN) // 3
    for i, (num, label) in enumerate((
        (stats["race_count"], "RACES"),
        (stats["region_count"], "REGIONS"),
        (stats["dimensions"], "CRITERIA"),
    )):
        x = og.MARGIN + i * col_w
        if i:
            draw.rectangle([x - 28, rule_y + 26, x - 27, og.H - 44], fill=og.TAN)
        draw.text((x, rule_y + 24), str(num), font=num_font, fill=og.DARK_BROWN)
        og.draw_tracked(draw, (x, rule_y + 106), label, lab_font, og.SEC_BROWN, 4)

    out = (output_dir or og.REPO_ROOT / "wordpress" / "output" / "og") / "homepage.jpg"
    path = og.save(img, out)
    print(f"Generated {path} ({path.stat().st_size:,} bytes) — "
          f"{stats['race_count']} races, {stats['region_count']} regions, "
          f"{stats['dimensions']} criteria")
    return path


if __name__ == "__main__":
    generate()
