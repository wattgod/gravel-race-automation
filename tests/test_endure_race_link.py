"""Race-page plan offer: the Endure Labs 14-day trial (Matt, 2026-11-07)."""
import json
import re
import sys
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))

import endure_offer as offer  # noqa: E402
from generate_neo_brutalist import (  # noqa: E402
    build_custom_plan_offer, generate_page, normalize_race_data,
)

ALL_SLUGS = sorted(p.stem for p in (ROOT / "race-data").glob("*.json"))
OFFER_RE = re.compile(r'<section class="gg-approved-section gg-offer" data-measure-section="custom-plan">.*?</section>', re.S)
TRIAL_LINK_RE = re.compile(r'<a class="gg-plan-cta" href="([^"]+)" data-cta="endure_trial">')


def _race(slug):
    return json.loads((ROOT / "race-data" / f"{slug}.json").read_text())["race"]


def _query(href):
    url = urlparse(unescape(href))
    assert (url.scheme, url.netloc, url.path) == ("https", "endurelabs.app", "/sign-up")
    return parse_qs(url.query)


def test_terms_live_in_one_place():
    assert (offer.TRIAL_DAYS, offer.PRICE_MONTHLY, offer.PRICE_YEARLY) == (14, "$24", "$199")
    assert offer.TRIAL_BUTTON == "START 14 DAYS FREE"
    assert offer.TRIAL_PRICE_LINE == "$24 / MONTH · $199 / YEAR"
    assert offer.TRIAL_TERMS == "Card required. Billing starts after 14 days unless you cancel."


def test_link_carries_exactly_the_params_endure_reads():
    assert offer.endure_trial_url("unbound-200") == (
        "https://endurelabs.app/sign-up?race=unbound-200&utm_source=gravel-god"
        "&utm_medium=race-page&utm_campaign=endure_trial&interval=year"
    )


def test_beta_list_and_draft_only_fields_are_gone():
    for name in ("ENDURE_PLAN_RACES", "ENDURE_PLAN_COPY", "endure_plan_url"):
        assert not hasattr(offer, name), name


@pytest.mark.parametrize("slug", ALL_SLUGS)
def test_every_race_offer_is_the_endure_trial(slug):
    html = build_custom_plan_offer(normalize_race_data({"race": _race(slug)}))
    links = TRIAL_LINK_RE.findall(html)
    assert len(links) == 1, slug
    assert _query(links[0]) == {
        "race": [slug], "utm_source": ["gravel-god"], "utm_medium": ["race-page"],
        "utm_campaign": ["endure_trial"], "interval": ["year"],
    }, slug
    assert "START 14 DAYS FREE &rarr;" in html
    assert "$24 / MONTH · $199 / YEAR" in html
    assert "Card required. Billing starts after 14 days unless you cancel." in html
    assert "/ WEEK" not in html and "$15" not in html
    assert "approved_custom_plan" not in html and "training-plans" not in html
    assert "endure_plan" not in html and "Or train in Endure" not in html


def test_slug_is_escaped():
    rd = normalize_race_data({"race": _race("unbound-200")})
    rd["slug"] = 'x"><script>alert(1)</script>&y=1'
    html = build_custom_plan_offer(rd)
    assert "<script>" not in html and 'x"' not in html
    assert _query(TRIAL_LINK_RE.findall(html)[0])["race"] == [rd["slug"]]


def test_race_name_is_escaped():
    rd = normalize_race_data({"race": _race("unbound-200")})
    rd["name"] = "<b>Bad</b> & Co"
    html = build_custom_plan_offer(rd)
    assert "<b>" not in html and "Train for &lt;b&gt;Bad&lt;/b&gt; &amp; Co" in html


def test_copy_keeps_the_unbound_variant_and_says_the_plan_adapts():
    unbound = build_custom_plan_offer(normalize_race_data({"race": _race("unbound-200")}))
    assert "200 miles of heat, wind, and rough" in unbound
    other = build_custom_plan_offer(normalize_race_data({"race": _race("mid-south")}))
    assert "A training plan for" in other and "200 miles" not in other
    for html in (unbound, other):
        assert "adjusts when your week changes" in html
        assert '<span class="gg-approved-kicker">Endure Labs</span>' in html


def test_full_page_offer_is_measured_and_tracked():
    html = generate_page(normalize_race_data({"race": _race("unbound-200")}), [])
    offers = OFFER_RE.findall(html)
    assert len(offers) == 1
    assert 'data-cta="endure_trial"' in offers[0]
    assert 'data-cta="approved_custom_plan"' not in html
    assert "endure_plan_click" not in html and "data-endure-plan" not in html
    # The generic race-page handler sends cta_click with cta_name = data-cta.
    assert "document.querySelectorAll('a[data-cta]" in html
    assert "cta_name: this.getAttribute('data-cta') || cta_type" in html
    assert "onclick" not in offers[0]


def test_offer_css_is_neo_brutalist_and_stacks_on_phones():
    src = (ROOT / "wordpress" / "generate_neo_brutalist.py").read_text()
    rules = [line for line in src.splitlines()
             if line.startswith(".gg-neo-brutalist-page .gg-offer") or line.startswith(".gg-neo-brutalist-page .gg-plan-cta")]
    assert any(".gg-offer-terms" in line for line in rules)
    for line in rules:
        body = line.split("{", 1)[-1]
        assert "border-radius" not in body and "box-shadow" not in body and "#" not in body
    assert ".gg-neo-brutalist-page .gg-offer { grid-template-columns: 1fr; }" in src
