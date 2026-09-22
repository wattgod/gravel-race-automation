"""Tests for the season review page generator."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_season_review import (  # noqa: E402
    FORMSUBMIT_URL,
    build_season_review_js,
    generate_season_review_page,
)
from season_review_variants import VARIANTS  # noqa: E402
import pytest  # noqa: E402

ALL = sorted(VARIANTS)


def page(slug: str = "standard") -> str:
    return generate_season_review_page(slug)


def core_form(slug: str = "standard") -> str:
    html = page(slug)
    start = html.index('<form id="season-form"')
    return html[start:html.index('<div class="gg-sr-part">', start)]


def test_has_ga4_and_header_js():
    html = page()
    assert "gtag" in html
    assert "gg-site-header" in html or "hamburger" in html.lower()


def test_noindex():
    assert 'name="robots" content="noindex, nofollow"' in page()


def test_honeypot_present():
    assert 'name="website" class="gg-apply-honeypot"' in page()


def test_submits_to_formsubmit_ajax_with_timeout():
    js = build_season_review_js(VARIANTS["standard"])
    assert FORMSUBMIT_URL.startswith("https://formsubmit.co/ajax/")
    assert FORMSUBMIT_URL in js
    assert "AbortController" in js


@pytest.mark.parametrize("slug", ALL)
def test_no_placeholders_left(slug):
    assert not re.search(r"__[A-Z_]+__", build_season_review_js(VARIANTS[slug]))


def test_no_innerhtml_in_js():
    assert "innerHTML" not in build_season_review_js(VARIANTS["standard"])


@pytest.mark.parametrize("slug", ALL)
def test_every_variant_is_mvp_plus_optional_depth(slug):
    html = page(slug)
    deep = html[html.index('<div class="gg-sr-part">'):html.index("</form>")]
    assert deep.count('<details class="gg-sr-deeper"') >= 3
    assert "<details open" not in deep and " required" not in deep
    assert html.count('class="gg-apply-submit-btn gg-sr-submit"') == 2


@pytest.mark.parametrize("slug", ALL)
def test_section_numbers_never_repeat(slug):
    nums = re.findall(r'gg-apply-section-title">(\d+)\. ', page(slug))
    assert len(nums) == len(set(nums)), nums


@pytest.mark.parametrize("slug", ALL)
def test_every_variant_asks_obstacle_and_goal(slug):
    core = core_form(slug)
    assert 'name="outcome_goal"' in core
    assert 'name="inner_obstacle"' in core or 'name="obstacle_combo"' in core


def test_no_inline_handlers():
    assert not re.search(r"\son(click|submit|change|input)=", page())


def test_core_is_seven_sections():
    core = core_form()
    for n in range(1, 8):
        assert f'gg-apply-section-title">{n}. ' in core
    assert 'gg-apply-section-title">8. ' not in core


def test_core_stays_short():
    # MVP review: sol's cut targets ~15 minutes. Guard against creep.
    # why_2..why_5 stay hidden until the athlete answers the why before them
    names = set(re.findall(r'name="([a-z_0-9]+)"', core_form())) - {"website"}
    names = {n for n in names if not re.fullmatch(r"why_[2-5]", n)}
    assert len(names) <= 23, sorted(names)


def test_deep_modules_are_optional_and_collapsed():
    html = page()
    deep = html[html.index('<div class="gg-sr-part">'):html.index("</form>")]
    assert deep.count('<details class="gg-sr-deeper"') >= 6
    assert "<details open" not in deep
    assert " required" not in deep


def test_ideal_future_write_is_fifteen_minutes_when_chosen():
    assert 'data-minutes="15" data-target="ideal_season"' in page()


@pytest.mark.parametrize("slug", ALL)
def test_no_training_metrics_asked(slug):
    # Matti: FTP and similar numbers come from data, not the athlete.
    html = page(slug).lower()
    form = html[html.index('<form id="season-form"'):html.index("</form>")]
    for term in ('name="ftp', 'w/kg', 'name="weight', 'plan_completion'):
        assert term not in form


def test_goal_carries_if_then_plan():
    core = core_form()
    assert 'name="inner_obstacle"' in core and 'name="obstacle_plan"' in core


def test_privacy_footer_discloses_form_relay():
    html = page()
    assert "FormSubmit" in html and "/privacy/" in html


@pytest.mark.parametrize("slug", ["standard", "claude", "matti"])
def test_goal_has_five_whys_and_why_not_yet_in_core(slug):
    core = core_form(slug)
    for n in ("outcome_why", "why_2", "why_3", "why_4", "why_5", "not_yet"):
        assert f'name="{n}"' in core
