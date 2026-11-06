"""Reviewed end-of-article resources. Unlisted essays get no commercial offer.

Policy is explicit: never infer an offer from incidental keywords in a body.
Keep author text and artwork outside this module unchanged.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pricing

ROOT = Path(__file__).resolve().parents[1]

# Training and planning subjects where a plan is a direct continuation.
PLAN_ARTICLES = frozenset({
    'sweet-spot-training-cycling', '5-ways-to-become-a-power-meter-clown',
    'controversial-opinion-you-dont-need-a-power-meter-to-be-fast',
    'how-do-i-know-if-im-getting-fitter',
    'how-to-achieve-your-goals-and-stop-ruining-your-dreams',
    'how-to-beat-people-20-years-younger-than-you',
    'how-to-do-workouts-the-right-way', 'how-to-not-fk-up-your-holiday-training',
    'i-opened-a-fascat-ai-coaching-email-so-you-dont-have-to',
    'no-one-cares-if-youre-bored', 'so-why-do-you-skip-weight-training',
    'what-is-hrv-and-why-should-i-care', 'you-dont-need-to-bike-to-bike-fast',
    'shit-athletes-say-ill-just-train', '2026-is-coming-part-1',
    'operation-cat-up-part-1', 'operation-cat-up-part-2', 'operation-cat-up-part-3',
    'keep-trusting-tss-blindly', 'no-my-chart-did-not-stutter',
})
COACHING_ARTICLES = frozenset({
    'how-to-manage-dopamine-to-be-a-better-cyclist',
    'maybe-stop-sandbagging-your-goals', 'it-doesnt-matter-how-you-feel',
    'the-secret-just-take-care-of-yourself',
})
RACE_ARTICLES = {
    'hacking-unbound-200-with-best-bike-split': 'unbound-200',
    'i-didnt-screw-up-unbound-200-and-you-dont-have-to-either': 'unbound-200',
    'i-screwed-up-unbound-2024-so-you-dont-have-to': 'unbound-200',
    'i-screwed-up-unbound-gravel-200-so-you-dont-have-to': 'unbound-200',
    'unbound-two-huni-mean-five-point': 'unbound-200',
    'i-didnt-screw-up-ned-gravel-and-neither-do-you': 'ned-gravel',
    'i-didnt-screw-up-red-granite-grinder-again-and-neither-do-you': 'red-granite-grinder',
    'i-didnt-screw-up-red-granite-grinder-and-neither-do-you-2': 'red-granite-grinder',
    'i-didnt-screw-up-red-granite-grinder-and-neither-do-you': 'red-granite-grinder',
    'i-didnt-screw-up-sbt-grvl-and-neither-do-you': 'steamboat-gravel',
    'i-screwed-up-sbt-grvl-so-you-dont-have-to': 'steamboat-gravel',
    'i-messed-up-big-horn-gravel-so-you-dont-have-to': 'bighorn-gravel',
    'i-screwed-up-gunni-grinder-so-you-dont-have-to': 'gunni-grinder',
    'i-screwed-up-gravel-worlds-so-you': 'gravel-worlds',
}
GUIDE_ARTICLES = {
    'how-to-hydrate-so-you-dont-die-in-your-gravel-race': (
        'Nutrition & fueling', '/guide/nutrition-fueling/'),
    'your-eating-habits-are-killing-your-performance': (
        'Nutrition & fueling', '/guide/nutrition-fueling/'),
    'how-to-win-when-youre-terrible': (
        'Race tactics', '/guide/mental-training-race-tactics/'),
}


def offer_for_slug(slug: str) -> dict | None:
    if slug in PLAN_ARTICLES:
        return {'kind':'custom_plan', 'title':'Custom training plan',
                'detail':f'{pricing.RACE_PLAN["weekly_rate_display"]}/week · paid once',
                'href':'/products/training-plans/', 'button':'See training plans'}
    if slug in COACHING_ARTICLES:
        product=pricing.PRICING['products']['coaching']
        return {'kind':'coaching', 'title':'Coaching',
                'detail':f'From {product["from_display"]} every {product["interval_weeks"]} weeks',
                'href':'/coaching/', 'button':'See coaching'}
    if slug in RACE_ARTICLES:
        race_slug=RACE_ARTICLES[slug]
        data=json.loads((ROOT/'race-data'/f'{race_slug}.json').read_text())['race']
        return {'kind':'race_guide', 'title':data['name'], 'detail':'',
                'href':f'/race/{race_slug}/', 'button':'Race guide'}
    if slug in GUIDE_ARTICLES:
        title,href=GUIDE_ARTICLES[slug]
        return {'kind':'training_guide', 'title':title, 'detail':'',
                'href':href, 'button':'Read the guide'}
    return None


def render_offer(offer: dict | None) -> str:
    if offer is None:
        return ''
    esc=lambda value:html.escape(str(value),quote=True)
    detail=f'<p class="article-offer-detail">{esc(offer["detail"])}</p>' if offer['detail'] else ''
    return f'''<aside class="article-offer" data-gg-added aria-label="Related resource">
  <div><h2 data-no-toc>{esc(offer['title'])}</h2>{detail}</div>
  <a class="btn" href="{esc(offer['href'])}" data-event="article_cta_click" data-label="{esc(offer['kind'])}" data-cta="{esc(offer['kind'])}">{esc(offer['button'])} <span aria-hidden="true">&rsaquo;</span></a>
</aside>'''
