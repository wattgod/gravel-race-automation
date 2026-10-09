"""Source for /articles/your-training-app-doesnt-know-your-race-exists/ on the editorial shell.

The article text is the live page's (snapshot #438, minus the Sweet Spot
tail, see below), in
your-training-app-doesnt-know-your-race-exists.body.html; this file adds the
page metadata. No "In short" (the article has no summary); the ladder
replaces the old three-link CTA box (same lead line), and the shell footer
replaces the old bottom subscribe box (same copy).

The live page was cloned from Sweet Spot and carried Sweet Spot's last four
sections, its references and its Article/FAQ JSON-LD. Matt approved removing
them (2026-10-08): the essay now ends after "The Start Line Doesn't Care
About Your Compliance Score", and the JSON-LD below describes this article.

Regenerate after editing the body, the shell or data/pricing.json:

    python3 wordpress/article_sources/your_training_app_doesnt_know_your_race_exists.py

tests/test_editorial_shell.py fails if the committed index.html is stale.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORDPRESS = HERE.parent
if str(WORDPRESS) not in sys.path:
    sys.path.insert(0, str(WORDPRESS))

from editorial_shell import ArticleMeta, render_editorial_page  # noqa: E402

SLUG = "your-training-app-doesnt-know-your-race-exists"
URL = f"https://gravelgodcycling.com/articles/{SLUG}/"
BODY_PATH = HERE / f"{SLUG}.body.html"
OUTPUT_PATH = WORDPRESS / "articles" / SLUG / "index.html"

DESCRIPTION = (
    "TrainerRoad and Zwift build you excellent fitness in a generic shape. Races are not generic. "
    "Where the climbing lands, when the selection happens, and what you can digest decide your day "
    "— and no algorithm reads a course profile."
)
OG_DESCRIPTION = "Adaptive training solved the wrong problem. Your fitness has a shape, and so does your race."

ARTICLE_LD = {
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "Your Training App Doesn't Know Your Race Exists",
    "author": {"@type": "Person", "name": "Matti Rowe", "url": "https://gravelgodcycling.com"},
    "publisher": {"@type": "Organization", "name": "Gravel God", "url": "https://gravelgodcycling.com"},
    "datePublished": "2026-07-02",
    "dateModified": "2026-10-08",
    "description": OG_DESCRIPTION,
    "mainEntityOfPage": URL,
}

META = ArticleMeta(
    slug=SLUG,
    canonical_url=URL,
    title="Your Training App Doesn't Know Your Race Exists | Gravel God",
    description=DESCRIPTION,
    og_description=OG_DESCRIPTION,
    headline="Your Training App Doesn’t Know Your Race Exists",
    kicker="Training · Opinion",
    dek="Adaptive training solved the wrong problem. Your fitness has a shape, and so does your race.",
    date_published=date(2026, 7, 2),
    json_ld=(ARTICLE_LD,),
)


def render() -> str:
    return render_editorial_page(META, BODY_PATH.read_text(encoding="utf-8"), in_short=None, ladder=True)


def main() -> None:
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(WORDPRESS.parent)}")


if __name__ == "__main__":
    main()
