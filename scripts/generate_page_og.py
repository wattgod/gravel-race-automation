#!/usr/bin/env python3
"""Generate Topo OG cards for non-race pages -> og/page-{name}.jpg.

Each card uses the page's own kicker/H1 and prices from their source of
truth (pricing.py, generate_coaching.TIERS), so the card says what the page
says. Pages without a card of their own fall back to og/homepage.jpg.

    page-training-plans.jpg      /products/training-plans/      (plans pillar)
    page-coaching.jpg            /coaching/, /coaching/apply/   (coaching pillar)
    page-season-review*.jpg      every Season Review variant    (coaching pillar)

Usage:
    python3 scripts/generate_page_og.py
"""

import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

import og_topo  # noqa: E402

OUTPUT_DIR = og_topo.OG_OUTPUT_DIR
TRAINING_PLANS_OG = "page-training-plans.jpg"
COACHING_OG = "page-coaching.jpg"

_MINUTE_WORDS = {"five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30}
_MINUTES = re.compile(r"\b(\d+|twenty-five|fifteen|twenty|thirty|five|ten)\s+minutes\b", re.I)


def minutes_from_intro(intro: str) -> int | None:
    """'About twenty-five minutes. ...' -> 25; None when the intro gives no time."""
    m = _MINUTES.search(html.unescape(intro or ""))
    if not m:
        return None
    word = m.group(1).lower()
    return int(word) if word.isdigit() else _MINUTE_WORDS[word]


def training_plans_card_html() -> str:
    from pricing import PRICE_CAP, PRICE_PER_WEEK
    return og_topo.pillar_card(
        pillar="plans", key="training-plans", kicker="CUSTOM TRAINING PLANS",
        title_html="Your Race.<br>Your Hours.<br>Your Plan.", size=80, lines=3,
        line=f"ONE PAYMENT · CAPPED AT {PRICE_CAP}", tag=("PER WEEK", PRICE_PER_WEEK))


def coaching_card_html() -> str:
    from generate_coaching import TIERS
    return og_topo.pillar_card(
        pillar="coaching", key="coaching", kicker="COACHING",
        title_html="You could be better than you think.", size=84, width=720,
        line="A HUMAN IN YOUR CORNER", tag=("PER 4 WEEKS", TIERS[0][2], "from"))


def season_review_card_html(slug: str) -> str:
    from generate_season_review import VARIANTS
    v = VARIANTS[slug]
    mins = minutes_from_intro(v.get("intro", ""))
    return og_topo.pillar_card(
        pillar="coaching", key=f"season-review-{slug}",
        kicker=html.unescape(v["badge"]), title_html=og_topo.e(html.unescape(v["h1"])), size=104,
        line=v.get("og_line"), serif_line=True,
        tag=("MINUTES", str(mins)) if mins else None)


def season_review_card(slug: str, output_dir: Path = OUTPUT_DIR, renderer=None) -> Path:
    from generate_season_review import og_image_name
    return _render(season_review_card_html(slug), output_dir / og_image_name(slug), renderer)


def _render(card_html: str, out: Path, renderer=None) -> Path:
    if renderer is not None:
        return renderer.render(card_html, out)
    with og_topo.Renderer() as r:
        return r.render(card_html, out)


def generate_all(output_dir: Path = OUTPUT_DIR) -> list[Path]:
    from generate_season_review import VARIANTS
    out = []
    with og_topo.Renderer() as r:
        out.append(r.render(training_plans_card_html(), output_dir / TRAINING_PLANS_OG))
        out.append(r.render(coaching_card_html(), output_dir / COACHING_OG))
        for slug in VARIANTS:
            out.append(season_review_card(slug, output_dir, r))
    return out


def main():
    for path in generate_all():
        print(f"  ✓ {path.relative_to(og_topo.REPO_ROOT)}")


if __name__ == "__main__":
    main()
