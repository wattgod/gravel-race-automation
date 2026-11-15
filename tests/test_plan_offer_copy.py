"""No Gravel God page may show the retired one-off offer next to the plan.

Since 2026-11-13 the custom plan is billed every 4 weeks ($49.99 per block,
14-day refund of the first payment, cancel from the plan page). Copy left
over from the one-off plan ("$249", "One-time payment", "7-day refund",
"$15 a week, paid once") next to the plan would be a false promise, and so
would "/mo" or "monthly" (it bills every 4 weeks). The guard is
plan_offer.stale_offer_phrases; this file runs it over every generator and
committed page that offers the plan, and proves it catches each phrase.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from plan_offer import PLAN_PRICE_LINE, stale_offer_phrases  # noqa: E402

UNBOUND = ROOT / "race-data" / "unbound-200.json"


def _race() -> dict:
    data = json.loads(UNBOUND.read_text())
    race = data.get("race", data)
    race.setdefault("slug", "unbound-200")
    return race


# ── The guard itself ─────────────────────────────────────────


OFFER = "<p>Custom training plan: $49.99 every 4 weeks. <a>BUILD MY PLAN</a></p>"


@pytest.mark.parametrize("stale,label", [
    ("Capped at $249.", "$249"),
    ("One-time payment, no subscription.", "One-time payment"),
    ("One payment. No subscription.", "One payment"),
    ("$15 a week until your race, paid once.", "paid once"),
    ("Just $4/mo.", "/mo"),
    ("Billed monthly.", "monthly"),
    ("7-day money-back guarantee.", "7-day"),
    ("Full refund within 7 days.", "within 7 days"),
    ("$15/week, four-week minimum.", "$15 a week"),
])
def test_guard_catches_each_retired_phrase_next_to_the_offer(stale, label):
    assert label in stale_offer_phrases(OFFER + f"<p>{stale}</p>")


def test_guard_ignores_the_phrase_far_from_any_offer():
    far = "<p>" + "Gravel. " * 200 + "</p>"
    assert stale_offer_phrases(OFFER + far + "<p>My monthly long-ride diary.</p>") == []


def test_guard_ignores_scripts_and_comments():
    page = OFFER + "<script>var s='One-time payment';</script><!-- $249 -->"
    assert stale_offer_phrases(page) == []


def test_guard_allows_one_payment_per_block():
    assert stale_offer_phrases(OFFER + "<p>One payment per 4-week block.</p>") == []


# ── Generated pages ──────────────────────────────────────────


def _product_page():
    from generate_training_plans import generate_training_page
    return generate_training_page()


def _per_race_plan_page():
    from generate_training_plan_pages import generate_page, load_pack
    return generate_page(_race(), load_pack("unbound-200"))


def _race_offer_blocks():
    from generate_neo_brutalist import (build_custom_plan_offer, build_sticky_cta,
                                        build_training, load_race_data)
    rd = load_race_data(UNBOUND)
    rd.setdefault("slug", "unbound-200")
    parts = []
    for build in (lambda: build_training(rd), lambda: build_custom_plan_offer(rd),
                  lambda: build_sticky_cta(rd["name"], rd["slug"])):
        parts.append(build())
    return "\n".join(parts)


def _state_hub():
    from generate_state_hubs import build_state_page
    return build_state_page("Kansas", [], 0)


def _vs_cta():
    from generate_vs_pages import build_training_cta
    race = {"slug": "unbound-200", "name": "Unbound Gravel 200"}
    other = {"slug": "mid-south", "name": "The Mid South"}
    return build_training_cta(race, other)


def _prep_kit_footer():
    from generate_prep_kit import build_pk_footer_cta
    return build_pk_footer_cta(_race())


def _terms():
    from generate_legal_pages import get_terms_content
    return get_terms_content()


def _ladder():
    from editorial_shell import render_ladder
    return render_ladder()


def _about():
    from generate_about import generate_about_page
    return generate_about_page()


def _homepage():
    from generate_homepage import generate_homepage, load_race_index
    return generate_homepage(load_race_index())


def _season_review():
    from generate_season_review import generate_season_review_page
    return generate_season_review_page("goal_2027")


def _training_success():
    from generate_success_pages import generate_success_page
    return generate_success_page("training-plans-success")


def _guide_cta():
    from generate_guide import build_cta_training
    return build_cta_training()


PAGES = {
    "product page": _product_page,
    "per-race plan page": _per_race_plan_page,
    "race page offer blocks": _race_offer_blocks,
    "state hub": _state_hub,
    "vs page CTA": _vs_cta,
    "prep kit footer": _prep_kit_footer,
    "terms": _terms,
    "editorial ladder": _ladder,
    "about": _about,
    "homepage": _homepage,
    "season review": _season_review,
    "training plan success page": _training_success,
    "guide CTA": _guide_cta,
}


@pytest.mark.parametrize("name", sorted(PAGES))
def test_generated_page_has_no_retired_offer_copy(name):
    page = PAGES[name]()
    assert stale_offer_phrases(page) == [], name


@pytest.mark.parametrize("name", ["product page", "per-race plan page", "race page offer blocks"])
def test_main_offer_pages_state_the_price(name):
    assert PLAN_PRICE_LINE.upper() in PAGES[name]().upper()


def test_questionnaire_reference_has_no_retired_offer_copy():
    """web/training-plans-questionnaire.html is what the Elementor widget
    must be updated to (by hand) before the form JS ships."""
    page = (ROOT / "web" / "training-plans-questionnaire.html").read_text()
    assert stale_offer_phrases(page) == []
    assert PLAN_PRICE_LINE in page


# ── Committed generated pages (posts, articles) ──────────────


# Committed pages with a known, pre-existing hit that this switch does not
# own. Each needs Matti's call, not a silent rewrite.
KNOWN_LEGACY = {
    # Imported 2024 post body: an old sales table ("Unbound 200 Training
    # Plan $100 ... Coaching $175 Monthly"). Unchanged by the 2026-11-13
    # switch; listed in the PR for Matti to decide.
    "posts/hacking-unbound-200-with-best-bike-split",
}


def _committed_pages():
    for folder in ("posts", "articles"):
        for path in sorted((ROOT / "wordpress" / folder).glob("*/index.html")):
            if f"{folder}/{path.parent.name}" not in KNOWN_LEGACY:
                yield path


def test_known_legacy_pages_still_exist():
    for key in KNOWN_LEGACY:
        assert (ROOT / "wordpress" / key / "index.html").exists(), key


@pytest.mark.parametrize("path", list(_committed_pages()),
                         ids=lambda p: f"{p.parent.parent.name}/{p.parent.name}")
def test_committed_page_has_no_retired_offer_copy(path):
    assert stale_offer_phrases(path.read_text()) == []
