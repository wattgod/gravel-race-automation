"""Source for /articles/your-training-app-doesnt-know-your-race-exists/ on the editorial shell.

The article text is the live page's (snapshot #438, minus the Sweet Spot
tail, see below), in
your-training-app-doesnt-know-your-race-exists.body.html; this file adds the
page metadata and an "In short" (each claim restates one section and links
to it); the ladder replaces the old three-link CTA box (same lead line), and
the shell footer replaces the old bottom subscribe box (same copy).

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

from editorial_shell import ArticleMeta, Claim, EssayFigure, Picture, render_editorial_page  # noqa: E402

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


# Each claim restates its section; section indexes are 0-based h2 positions.
IN_SHORT = (
    Claim("TrainerRoad and Zwift model your fatigue, zones and missed sessions, and none of them models the race.",
          "#first-the-part-where-i-agree-with-the-robots", "See what the apps model · §01", 0),
    Claim("Races are won by the right fitness in the right shape: where the climbing lands, when the selection happens, what you can digest.",
          "#fitness-has-a-shape", "See the shape of a race · §02", 1),
    Claim("Durability is the most race-relevant quality in endurance sport, and adaptive logic sacrifices it first because it doesn&rsquo;t move short-term metrics.",
          "#a-field-guide-to-perfectly-trained-casualties", "See the Interval Assassin · §03", 2),
    Claim("If your race is flat, your schedule stable and your goal a respectable finish, a generic plan captures most of the value.",
          "#the-part-where-i-tell-you-not-to-buy-anything", "See who doesn’t need it · §04", 3),
)


# ── Gravel God memes (2026-10-09). Rendered in the dirt-craft-course repo; see
# docs/memes/README.md. WebP only (the <img> fallback is the 1x WebP); alt text
# is docs/memes ALT.txt verbatim; phones get the recomposed -m crop. Files live
# in wordpress/articles/<slug>/img/memes/. Add a meme with one FIGURES line.
def _meme(name: str, alt: str, width: int, height: int, *, phone: tuple[int, int]) -> Picture:
    return Picture.from_stem(f"img/memes/{name}", alt, width, height, ext="webp", webp=False, phone=phone)


MEME_POV_MILE_82 = _meme("pov-mile-82", "First-person view while walking a gravel bike up a steep, rocky pitch: your own forearms reach in from the bottom, one hand on the hood, one on the top tube; the bike computer reads \"COMPLIANCE 91%\". Ahead, four other riders, sweating, walk their bikes up the pitch. Caption: \"POV: you're walking the third pitch at mile 82 with a 91% compliance score.\"", 1200, 1200, phone=(660, 900))
MEME_LOOK_INSIDE = _meme("look-inside", "A book cover, \"Your training app: Adapted to you. Your fatigue · your zones · your missed Tuesdays\", with a smiling Gravel God and a \"Look inside\" arrow. Inside, the contents page ticks off your fatigue, your zones, your missed Tuesdays and your progression levels; the last line, in red: \"The race ... not modeled.\" Footer: \"None of them models the race.\"", 1600, 1000, phone=(660, 1300))
MEME_DRAKE_FIT = _meme("drake-fit", "Two-panel approve/reject meme with Gravel God. Top: eyes shut, head turned away, palm raised against \"Fitness: a number going up.\" Bottom: smiling and pointing at \"Fit: shaped like your race.\"", 1200, 1200, phone=(660, 660))
MEME_STARTER_PACK_FUELING = _meme("starter-pack-fueling", "Heading \"THE FUELING OPTIMIST STARTER PACK\". Gravel God gives a thumbs up beside a flat-lay of labelled objects: a sticky note reading \"eat when hungry\" (The fueling plan); a bike computer with an up arrow under \"FTP\" (Excellent fitness, any shape); banana peels on a white folding table (The aid station table, after the first 500 riders); a napkin reading \"8 h × 60–90 g/h = ???\" with a frowny face (Sad math at the aid station); three sealed gels (Gels, for later).", 1600, 1000, phone=(660, 1000))
MEME_UNO_DRAW_25 = _meme("uno-draw-25", "Two-panel cartoon. A card reads 'Practice your race-day fueling on every long ride, or draw 24 gels.' In the next panel Gravel God smugly holds a huge fan of 24 energy gels.", 1600, 1000, phone=(660, 1200))
MEME_PIGEON_COMPLIANCE = _meme("pigeon-compliance", "Gravel God, labelled \"YOUR TRAINING APP\", points at a green butterfly fluttering just past his finger, labelled \"91% COMPLIANCE\". Caption: \"IS THIS RACE PREP?\"", 1600, 1000, phone=(660, 825))

FIGURES = (
    EssayFigure(MEME_POV_MILE_82, after="his app trained him for a race that doesn&rsquo;t exist.</p>"),
    EssayFigure(MEME_LOOK_INSIDE, after="None of them models <em>the race</em>.</p>", width="column"),
    EssayFigure(MEME_DRAKE_FIT, after="The race does not grade on fitness. It grades on fit.</p>"),
    EssayFigure(MEME_STARTER_PACK_FUELING, after="already stripped of bananas, doing sad math.</p>", width="column"),
    EssayFigure(MEME_UNO_DRAW_25, after="That&rsquo;s what it&rsquo;s for.</p>", width="column"),
    EssayFigure(MEME_PIGEON_COMPLIANCE, after="the only question that mattered: <em>adapted to what?</em></p>", width="column"),
)


def render() -> str:
    return render_editorial_page(META, BODY_PATH.read_text(encoding="utf-8"), in_short=IN_SHORT, ladder=True,
                                 figures=FIGURES)


def main() -> None:
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(WORDPRESS.parent)}")


if __name__ == "__main__":
    main()
