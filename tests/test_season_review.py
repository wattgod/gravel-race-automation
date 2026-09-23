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


class TestAthleteVariant:
    """The version Matti sends to people he already coaches. Its questions are
    Endure's limiter interrogation (endure-loop-2026 §3), so the answers file
    into the athlete's record instead of needing to be retyped.
    """

    def test_asks_all_seven_probes(self):
        core = core_form("athlete")
        for field in ("limiter", "limiter_evidence", "vices", "skill_gaps",
                      "week_breakers", "drop_order", "pre_race_48h", "admission"):
            assert f'name="{field}"' in core, field

    def test_limiter_is_typed(self):
        # a string alone would overload Endure's limiters[]; the kind is what
        # lets it become a race_limiters row or a leaf goal
        core = core_form("athlete")
        for kind in ("fitness", "skill", "positioning", "durability", "body", "life"):
            assert f'value="{kind}"' in core

    def test_carries_a_hidden_athlete_tag(self):
        assert '<input type="hidden" id="athlete" name="athlete">' in page("athlete")

    def test_export_keeps_the_probes_verbatim(self):
        js = build_season_review_js(VARIANTS["athlete"])
        assert "interrogation" in js and "limiter_evidence" in js
        assert "asked_at" in js and "version: 1" in js

    def test_still_short_enough_to_finish(self):
        # "athlete" is the hidden tag from the link, not a question
        names = set(re.findall(r'name="([a-z_0-9]+)"', core_form("athlete"))) - {"website", "athlete"}
        names = {n for n in names if not re.fullmatch(r"why_[2-5]", n)}
        assert len(names) <= 36, sorted(names)


class TestOneVoice:
    """The lead form, the athlete form and the original are one questionnaire
    in three lengths. They share their section blocks so the tone can't drift.
    """

    @pytest.mark.parametrize("slug", ["matti", "goal_2027", "athlete"])
    def test_same_opening(self, slug):
        assert "So. 2026." in page(slug)

    @pytest.mark.parametrize("slug", ["matti", "goal_2027", "athlete"])
    def test_shared_sections_are_word_for_word(self, slug):
        core = core_form(slug)
        for line in ("The Highlight Reel", "The Blooper Reel",
                     "Your Biggest Obstacle Is You", "What Would a Fast Cyclist Do?",
                     "Not the Strava version", "Not the weather. Not work. You."):
            assert line in core, (slug, line)

    def test_lead_form_asks_no_coaching_questions(self):
        core = core_form("goal_2027")
        for field in ("hours_next", "constraints", "next_season_plan", "coach_notes"):
            assert f'name="{field}"' not in core, field

    def test_lead_form_stays_a_fifteen_minute_job(self):
        names = set(re.findall(r'name="([a-z_0-9]+)"', core_form("goal_2027"))) - {"website"}
        names = {n for n in names if not re.fullmatch(r"why_[2-5]", n)}
        assert len(names) <= 25, sorted(names)


class TestGoalsPage:
    """/goals/ — the public lead page: questionnaire, then the poster, then
    the offer beneath it (never in front of it).
    """

    def test_lives_at_its_own_url_and_is_findable(self):
        from generate_season_review import page_path, output_name
        assert page_path("goal_2027") == "/goals/"
        assert output_name("goal_2027") == "goals.html"
        assert 'content="index, follow"' in page("goal_2027")

    def test_every_other_variant_stays_hidden(self):
        for slug in ALL:
            if slug != "goal_2027":
                assert 'content="noindex, nofollow"' in page(slug), slug

    def test_results_come_before_the_offer(self):
        html = page("goal_2027")
        assert html.index('id="poster-canvas"') < html.index("data-offer-variant")

    def test_results_start_hidden(self):
        html = page("goal_2027")
        section = html[html.index('<section id="results"'):html.index("</section>")]
        assert 'hidden' in html[html.index('<section id="results"'):html.index('class="gg-sr-results-head"')]
        assert section.count("data-offer-variant") == 3
        assert section.count("<div class=\"gg-sr-offer\"") == 3

    def test_three_offer_variants_to_test(self):
        js = build_season_review_js(VARIANTS["goal_2027"])
        assert "goal_offer_view" in js and "offer_variant" in js

    def test_lead_page_does_not_use_the_email_backstop(self):
        # every backstop copy is another stranger's answers in Matti's inbox
        js = build_season_review_js(VARIANTS["goal_2027"])
        assert 'TRANSPORT = "worker"' in js

    def test_the_athlete_form_keeps_its_backstop(self):
        assert 'TRANSPORT = "both"' in build_season_review_js(VARIANTS["athlete"])

    def test_the_funnel_is_measurable(self):
        js = build_season_review_js(VARIANTS["goal_2027"])
        for event in ("goal_start", "goal_submit", "goal_results_view",
                      "goal_poster_download", "goal_offer_view", "goal_offer_click"):
            assert event in js, event

    def test_the_offer_states_the_real_terms(self):
        html = page("goal_2027")
        assert "$15 per week" in html and "$249" in html and "7 days" in html
