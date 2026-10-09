"""Source for /articles/your-training-app-doesnt-know-your-race-exists/ on the editorial shell.

The article text is the live page's, verbatim (snapshot #438), in
your-training-app-doesnt-know-your-race-exists.body.html; this file adds the
page metadata. No "In short" (the article has no summary); the ladder
replaces the old three-link CTA box (same lead line), and the shell footer
replaces the old bottom subscribe box (same copy).

KNOWN CONTENT DEFECT, carried over verbatim on purpose (Matt decides): the
live page was cloned from Sweet Spot and still carries Sweet Spot's last
four sections ("It Makes You Slow" .. "That Said, G-Spot..."), its
references list, and its Article/FAQ JSON-LD (wrong headline, keywords,
citations). Fixing it = delete those sections from the body file and rewrite
ARTICLE_LD/FAQ_LD below, then regenerate.

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

# Verbatim from the live page (see KNOWN CONTENT DEFECT above).
ARTICLE_LD = {'@context': 'https://schema.org',
 '@type': 'Article',
 'headline': "Sweet Spot Training Isn't That Sweet — The Science Says You're Wasting Time",
 'author': {'@type': 'Person', 'name': 'Matti Rowe', 'url': 'https://gravelgodcycling.com'},
 'publisher': {'@type': 'Organization', 'name': 'Gravel God', 'url': 'https://gravelgodcycling.com'},
 'datePublished': '2026-03-26',
 'dateModified': '2026-03-26',
 'description': 'Sweet Spot training is made up, makes you slower, and science hates it. The evidence for '
                'polarized training is clear.',
 'mainEntityOfPage': 'https://gravelgodcycling.com/articles/your-training-app-doesnt-know-your-race-exists/',
 'keywords': ['sweet spot training',
              'cycling training zones',
              'polarized training',
              'FTP',
              'threshold training',
              'cycling science'],
 'citation': [{'@type': 'ScholarlyArticle',
               'name': 'Autonomic recovery after exercise in trained athletes',
               'author': 'Seiler, Haugen, Kuffel',
               'datePublished': '2007'},
              {'@type': 'ScholarlyArticle',
               'name': 'Six weeks of a polarized training-intensity distribution leads to greater '
                       'physiological and performance adaptations',
               'author': 'Neal et al.',
               'datePublished': '2013'},
              {'@type': 'ScholarlyArticle',
               'name': 'Polarized training has greater impact on key endurance variables',
               'author': 'Stöggl, Sperlich',
               'datePublished': '2014'},
              {'@type': 'ScholarlyArticle',
               'name': 'Impact of training intensity distribution on performance in endurance athletes',
               'author': 'Esteve-Lanao, Foster, Seiler, Lucia',
               'datePublished': '2007'},
              {'@type': 'ScholarlyArticle',
               'name': 'Polarized vs. threshold training intensity distribution on endurance sport '
                       'performance',
               'author': 'Rosenblat et al.',
               'datePublished': '2019'},
              {'@type': 'ScholarlyArticle',
               'name': 'Which training intensity distribution intervention will produce the greatest '
                       'improvements',
               'author': 'Rosenblat, Seiler et al.',
               'datePublished': '2025'}]}

FAQ_LD = {'@context': 'https://schema.org',
 '@type': 'FAQPage',
 'mainEntity': [{'@type': 'Question',
                 'name': 'What is Sweet Spot training in cycling?',
                 'acceptedAnswer': {'@type': 'Answer',
                                    'text': 'Sweet Spot training targets 88-94% of Functional Threshold '
                                            'Power (FTP). It was coined by Frank Overton of FasCat Coaching '
                                            'around 2004, based on a hypothetical, unitless graph by '
                                            "exercise physiologist Andy Coggan that was 'only ever intended "
                                            "as conveying a concept.' It lacks rigorous scientific "
                                            'foundation.'}},
                {'@type': 'Question',
                 'name': 'Is polarized training better than Sweet Spot?',
                 'acceptedAnswer': {'@type': 'Answer',
                                    'text': 'Yes. Multiple studies show polarized training (75-90% below '
                                            'LT1, 15-20% above LT2) consistently outperforms threshold-heavy '
                                            'training. Neal et al. (2013) showed 8% peak power gains vs 3% '
                                            'for threshold. Stöggl and Sperlich (2014) found polarized '
                                            'improved VO2peak by 11.7%. The 2025 network meta-analysis by '
                                            'Rosenblat and Seiler confirmed threshold-heavy approaches '
                                            'ranked worst for competitive athletes.'}},
                {'@type': 'Question',
                 'name': 'Why does Sweet Spot training make you slower?',
                 'acceptedAnswer': {'@type': 'Answer',
                                    'text': "Sweet Spot sits in Seiler's 'black hole' of training intensity. "
                                            'Your autonomic nervous system treats it like threshold work '
                                            '(same recovery cost), it inhibits fat oxidation by locking out '
                                            "CPT1/CPT2 enzymes, and it's not intense enough to maximally "
                                            'trigger mitochondrial biogenesis. You get the recovery cost of '
                                            'hard training with the adaptive stimulus of not-that-hard '
                                            'training.'}},
                {'@type': 'Question',
                 'name': 'Do most cyclists actually train at Sweet Spot intensity?',
                 'acceptedAnswer': {'@type': 'Answer',
                                    'text': 'No. Most cyclists overestimate their FTP by 5-10%, meaning '
                                            "their 'Sweet Spot' workouts at 88-94% of inflated FTP actually "
                                            "put them at or above their true threshold. They're doing "
                                            'threshold work while thinking they found a training hack.'}}]}

META = ArticleMeta(
    slug=SLUG,
    canonical_url=URL,
    title="Your Training App Doesn't Know Your Race Exists | Gravel God",
    description=(
        "TrainerRoad and Zwift build you excellent fitness in a generic shape. Races are not generic. "
        "Where the climbing lands, when the selection happens, and what you can digest decide your day "
        "— and no algorithm reads a course profile."
    ),
    og_description="Adaptive training solved the wrong problem. Your fitness has a shape, and so does your race.",
    headline="Your Training App Doesn’t Know Your Race Exists",
    kicker="Training · Opinion",
    dek="Adaptive training solved the wrong problem. Your fitness has a shape, and so does your race.",
    date_published=date(2026, 7, 2),
    json_ld=(ARTICLE_LD, FAQ_LD),
)


def render() -> str:
    return render_editorial_page(META, BODY_PATH.read_text(encoding="utf-8"), in_short=None, ladder=True)


def main() -> None:
    OUTPUT_PATH.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH.relative_to(WORDPRESS.parent)}")


if __name__ == "__main__":
    main()
