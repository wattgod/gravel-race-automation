"""/coaching/exit/ in a real browser on a 390px phone.

Opens the page from a personalised link, answers every question the way an
athlete would (the 0-10 scale by keyboard only), submits with both transports
intercepted, and checks what the worker and the FormSubmit backstop received,
what the athlete saw, and that nothing threw. Skipped without Playwright.
"""
from __future__ import annotations

import html

import pytest

from tests.exit_survey_browser import has_playwright, load_submission, submit_exit_survey

pytestmark = pytest.mark.skipif(not has_playwright(), reason="playwright not installed")


@pytest.fixture(scope="module")
def run():
    return submit_exit_survey(load_submission(), width=390)


def test_zero_page_errors(run):
    assert run["errors"] == []


def test_personalised_link_prefills_identity(run):
    sub = load_submission()
    assert run["prefilled"] == {k: sub[k] for k in ("name", "email", "athlete")}


def test_worker_gets_every_answer_as_a_string(run):
    sub = load_submission()
    body = run["worker"]
    assert body["source"] == "athlete_exit"
    assert body["brand"] == "gravelgod"
    assert (body["name"], body["email"], body["athlete"]) == (sub["name"], sub["email"], sub["athlete"])
    assert body["goal_answers"] == sub["goal_answers"]
    assert all(isinstance(v, str) for v in body["goal_answers"].values())
    assert body["goal_answers"]["recommend"] == "8"
    # identity rides at the top level, never inside the answers
    assert not {"name", "email", "athlete", "consent_note"} & set(body["goal_answers"])


def test_backstop_email_is_the_exit_survey_not_a_goal_export(run):
    raw = run["formsubmit"]
    assert raw, "FormSubmit backstop never fired"
    assert "Exit survey: Test Rider A" in raw
    assert "# Exit survey: Test Rider A" in raw
    assert "How likely are you to recommend me to a rider like you? 8" in raw
    assert "Gravel God social posts" in raw  # a ticked channel, by its label
    for goal_only in ("## Flags", "Endure draft", "Season Review 2026"):
        assert goal_only not in raw, goal_only
    # the consent note is an explanation, not a question
    assert "Before anything goes up" not in raw


def test_the_athlete_sees_the_success_line(run):
    from season_review_variants import EXIT
    assert "success" in run["message_class"]
    assert run["message"] == html.unescape(EXIT["success"])


def test_no_horizontal_scroll_at_390(run):
    layout = run["layout"]
    assert layout["innerWidth"] == 390
    assert layout["scrollWidth"] <= layout["innerWidth"]


def test_scale_is_one_row_that_fits(run):
    layout = run["layout"]
    assert layout["scaleCount"] == 11
    assert len(set(layout["scaleTops"])) == 1, layout["scaleTops"]
    assert layout["scaleLeft"] >= 0 and layout["scaleRight"] <= layout["innerWidth"]
    # WCAG 2.5.8 target size: at least 24 x 24 CSS px
    assert layout["scaleMinWidth"] >= 24 and layout["scaleMinHeight"] >= 44


def test_scale_answers_to_the_keyboard(run):
    # the helper never clicks the scale: focus on 0, then ArrowRight x8
    assert run["layout"]["recommendPicked"] == "8"


def test_share_options_stack_and_fit(run):
    layout = run["layout"]
    assert len(set(layout["shareLefts"])) == 1
    assert layout["shareTops"] == sorted(layout["shareTops"])
    assert len(set(layout["shareTops"])) == 4
    assert layout["shareRight"] <= layout["innerWidth"]
