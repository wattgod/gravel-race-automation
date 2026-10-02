#!/usr/bin/env python3
"""Generate OG share cards for non-race pages -> og/page-{name}.jpg.

A page card is the page's own badge + H1 on the 2026 brand frame — no new
copy, so the card always says what the page says. Pages without a card of
their own fall back to og/homepage.jpg (scripts/generate_homepage_og.py).

Covered today: every Season Review variant (/coaching/season-review/...).

Usage:
    python3 scripts/generate_page_og.py
"""

import html
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

import og_brand as og  # noqa: E402

OUTPUT_DIR = og.REPO_ROOT / "wordpress" / "output" / "og"


def render_page_card(kicker: str, headline: str, output_path: Path) -> Path:
    img, draw = og.new_card()
    max_w = og.W - 2 * og.MARGIN
    # One line if it holds at display size, else two — no orphaned last word.
    try:
        font, lines = og.fit_headline(draw, headline, max_w,
                                      sizes=(112, 104, 96, 88), max_lines=1)
    except og.OGCardError:
        font, lines = og.fit_headline(draw, headline, max_w,
                                      sizes=(104, 96, 88, 80, 72), max_lines=2)
    line_h = round(font.size * 1.1)
    # Kicker + headline block, centred in the space below the header rule.
    block_h = 48 + len(lines) * line_h
    y = og.HEADER_RULE_Y + (og.H - og.HEADER_RULE_Y - block_h) // 2 - 6
    og.kicker(draw, (og.MARGIN, y), [(kicker, og.GOLD)])
    y += 48
    for line in lines:
        draw.text((og.MARGIN, y), line, font=font, fill=og.DARK_BROWN)
        y += line_h
    return og.save(img, output_path)


def season_review_card(slug: str, output_dir: Path = OUTPUT_DIR) -> Path:
    """One Season Review variant's card: its badge over its H1."""
    from generate_season_review import VARIANTS, og_image_name
    variant = VARIANTS[slug]
    return render_page_card(html.unescape(variant["badge"]),
                            html.unescape(variant["h1"]),
                            output_dir / og_image_name(slug))


def season_review_cards(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    from generate_season_review import VARIANTS
    return [season_review_card(slug, output_dir) for slug in VARIANTS]


def main():
    for path in season_review_cards():
        print(f"  ✓ {path.relative_to(og.REPO_ROOT)}")


if __name__ == "__main__":
    main()
