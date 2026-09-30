"""/race-debrief/ in a real browser on a 390px phone.

Opens the page the way a plan's note links to it (?plan= for a marketplace
plan, ?ref= for a custom one, or nothing), answers every question the way a
rider would (the 0-10 scale by keyboard only), submits with the worker
intercepted, and checks what the worker received, what GA4 was told, what the
rider saw and that nothing threw. Skipped without Playwright.
"""
from __future__ import annotations

import html
import json

import pytest

from tests.race_debrief_browser import has_playwright, load_submission, run_debrief

pytestmark = pytest.mark.skipif(not has_playwright(), reason="playwright not installed")

NOTE_LINK = "?plan=123456&utm_source=trainingpeaks&utm_medium=plan_note#top"


@pytest.fixture(scope="module")
def run():
    return run_debrief(NOTE_LINK)


def _named(events, name):
    return [params for n, params in events if n == name]


def test_zero_page_errors(run):
    assert run["errors"] == []


def test_the_plan_comes_from_the_address_and_stays_there(run):
    assert run["hidden"] == {"plan": "123456", "ref": ""}
    # not personal: kept for GA4's per-plan note clicks, utm and hash untouched
    assert run["href"].endswith("/race-debrief/" + NOTE_LINK)


def test_worker_gets_every_answer_and_the_plan_top_level(run):
    sub = load_submission()
    body = run["worker"]
    assert body["source"] == "plan_debrief" and body["brand"] == "gravelgod"
    assert (body["name"], body["email"]) == (sub["name"], sub["email"])
    assert body["plan"] == "123456" and "ref" not in body
    assert body["goal_answers"] == sub["goal_answers"]
    assert all(isinstance(v, str) for v in body["goal_answers"].values())
    assert body["goal_answers"]["recommend"] == "9"
    assert not {"name", "email", "athlete", "plan", "ref", "consent_note"} & set(body["goal_answers"])


def test_no_formsubmit_copy(run):
    assert run["formsubmit"] is False


def test_the_rider_sees_the_success_line(run):
    from season_review_variants import RACE_DEBRIEF
    assert "success" in run["message_class"]
    assert run["message"] == html.unescape(RACE_DEBRIEF["success"])


def test_the_rating_line_links_this_plans_tp_page(run):
    rating = run["rating"]
    assert rating["hidden"] is False and rating["visible"] is True
    assert rating["href"] == "https://www.trainingpeaks.com/training-plans/cycling/tp-123456"
    assert rating["text"] == "If you have a minute, rate the plan on TrainingPeaks, whatever score you'd give it."


def test_ga4_start_and_submit_with_presence_not_values(run):
    assert _named(run["events_before"], "debrief_start") == []  # nothing before a real edit
    starts, submits = _named(run["events"], "debrief_start"), _named(run["events"], "debrief_submit")
    assert len(starts) == 1 and len(submits) == 1
    for params in starts + submits:
        assert params["has_plan"] == "yes" and params["has_ref"] == "no"
        assert params["variant"] == "race_debrief"
    assert "123456" not in json.dumps(run["events"])
    # never counted in the goals funnel
    assert _named(run["events"], "goal_start") == [] and _named(run["events"], "goal_submit") == []


def test_typing_stops_at_the_stored_length(run):
    assert run["capped_len"] == 4000


def test_no_horizontal_scroll_at_390(run):
    layout = run["layout"]
    assert layout["innerWidth"] == 390
    assert layout["scrollWidth"] <= layout["innerWidth"]


def test_scale_is_one_row_that_fits_and_answers_to_the_keyboard(run):
    layout = run["layout"]
    assert layout["scaleCount"] == 11 and len(set(layout["scaleTops"])) == 1
    assert layout["scaleLeft"] >= 0 and layout["scaleRight"] <= layout["innerWidth"]
    assert layout["scaleMinWidth"] >= 24 and layout["scaleMinHeight"] >= 44
    assert layout["recommendPicked"] == "9"


def test_a_custom_plan_ref_is_sent_and_gets_no_rating_line():
    seen = run_debrief("?ref=test-ref-0001", answers={"raced": "finished"})
    assert seen["errors"] == []
    assert seen["worker"]["ref"] == "test-ref-0001" and "plan" not in seen["worker"]
    assert seen["worker"]["goal_answers"] == {"raced": "finished"}
    assert seen["rating"]["hidden"] is True
    start = _named(seen["events"], "debrief_start")[0]
    assert (start["has_plan"], start["has_ref"]) == ("no", "yes")
    assert "test-ref-0001" not in json.dumps(seen["events"])


def test_no_params_means_no_plan_and_no_rating_line():
    seen = run_debrief("", answers={"raced": "dns"})
    assert seen["errors"] == []
    assert "plan" not in seen["worker"] and "ref" not in seen["worker"]
    assert seen["rating"]["hidden"] is True
    assert _named(seen["events"], "debrief_submit")[0]["has_plan"] == "no"


@pytest.mark.parametrize("query", ["?plan=12ab34&ref=bad", "?plan=1234567890123&ref=has%20space1",
                                   "?plan=%20123456&ref=test-ref-0001%0A"])
def test_malformed_params_are_never_sent(query):
    seen = run_debrief(query, answers={"raced": "later"})
    assert seen["errors"] == []
    assert seen["hidden"] == {"plan": "", "ref": ""}
    assert "plan" not in seen["worker"] and "ref" not in seen["worker"]
    assert seen["rating"]["hidden"] is True


def test_a_failed_store_shows_the_error_and_no_rating_line():
    seen = run_debrief(NOTE_LINK, answers={"raced": "finished"}, worker_status=503)
    assert "error" in seen["message_class"]
    assert seen["rating"]["hidden"] is True
    assert _named(seen["events"], "debrief_submit") == []


class TestADraftNeverCarriesAnotherPlan:
    """Devin on #421: a draft saved from one plan's link must not attribute a
    later debrief, opened from another plan's link, to the first plan."""

    def test_a_custom_plan_link_drops_the_drafts_marketplace_plan(self):
        from tests.race_debrief_browser import resume_from
        seen = resume_from("?plan=123456", "?ref=test-ref-0001")
        assert seen["errors"] == []
        assert seen["first"] == {"plan": "123456", "ref": ""}
        assert seen["second"] == {"plan": "", "ref": "test-ref-0001"}
        assert seen["restored_email"] == load_submission()["email"]  # the draft itself still resumes
        assert seen["worker"]["ref"] == "test-ref-0001" and "plan" not in seen["worker"]
        assert seen["rating"]["hidden"] is True

    def test_another_plans_link_replaces_the_plan(self):
        from tests.race_debrief_browser import resume_from
        seen = resume_from("?plan=123456", "?plan=654321")
        assert seen["second"] == {"plan": "654321", "ref": ""}
        assert seen["worker"]["plan"] == "654321"
        assert seen["rating"]["href"].endswith("/tp-654321")

    def test_a_malformed_plan_in_the_new_link_still_clears_the_old_one(self):
        from tests.race_debrief_browser import resume_from
        seen = resume_from("?plan=123456", "?plan=12ab34")
        assert seen["second"] == {"plan": "", "ref": ""}
        assert "plan" not in seen["worker"] and "ref" not in seen["worker"]

    def test_a_bare_address_resumes_the_drafts_plan(self):
        from tests.race_debrief_browser import resume_from
        seen = resume_from("?plan=123456", "")
        assert seen["second"] == {"plan": "123456", "ref": ""}
        assert seen["worker"]["plan"] == "123456"
