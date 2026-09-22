"""2027 goal questionnaire plumbing (docs/specs/goals-2027-funnel-spec.md).

The lead's answers are the deliverable — they render the poster and give the
coach the read — so unlike every other capture source this one carries a body
through the worker and this router. These tests pin that it arrives, that it
is capped, and that the poster route only answers to the token it issued.
"""

import pytest

from mission_control.sequences import get_sequences_for_trigger
from mission_control.services.goal_poster import render_poster

ANSWERS = {
    "outcome_goal": "Finish Unbound 200 under 14 hours",
    "outcome_why": "To prove a dad with a job still can",
    "inner_obstacle": "I skip rides after a late night out",
    "obstacle_plan": "Ride the short version before 9 a.m.",
    "habit": "Phone sleeps in the kitchen",
    "habit_when": "Charger lives by the toaster",
}


def _post(client, body):
    return client.post(
        "/webhooks/subscriber",
        json=body,
        headers={"Authorization": "Bearer test-secret-123"},
    )


def _enrollment(fake_db, email):
    rows = [e for e in fake_db.store["gg_sequence_enrollments"]
            if e["contact_email"] == email]
    assert rows, "no enrollment written"
    return rows[0]


class TestSequence:
    def test_goal_2027_trigger_has_a_sequence(self):
        ids = [s["id"] for s in get_sequences_for_trigger("goal_2027", "gravelgod")]
        assert "goal_2027_v1" in ids

    def test_road_gets_its_own(self):
        ids = [s["id"] for s in get_sequences_for_trigger("goal_2027", "roadielabs")]
        assert ids == ["road_goal_2027_v1"]

    def test_results_email_is_first_and_same_day(self):
        seq = get_sequences_for_trigger("goal_2027", "gravelgod")[0]
        first = seq["variants"]["A"]["steps"][0]
        assert first["template"] == "goal_2027_results"
        assert first["delay_days"] == 0


class TestWebhook:
    def test_answers_reach_the_enrollment(self, client, fake_db):
        resp = _post(client, {
            "email": "goal@example.com", "name": "Ada Rider",
            "source": "goal_2027", "goal_answers": ANSWERS, "offer_variant": "B",
        })
        assert resp.status_code == 200
        assert "goal_2027_v1" in resp.json()["enrolled"]
        sd = _enrollment(fake_db, "goal@example.com")["source_data"]
        assert sd["goal_answers"]["outcome_goal"] == ANSWERS["outcome_goal"]
        assert sd["offer_variant"] == "B"

    def test_poster_token_and_url_are_issued(self, client, fake_db):
        _post(client, {"email": "token@example.com", "source": "goal_2027",
                       "goal_answers": ANSWERS})
        sd = _enrollment(fake_db, "token@example.com")["source_data"]
        assert len(sd["poster_token"]) >= 16
        # url only when Mission Control knows its own address
        assert "poster_url" not in sd or sd["poster_token"] in sd["poster_url"]

    def test_template_keys_are_flattened(self, client, fake_db):
        _post(client, {"email": "flat@example.com", "source": "goal_2027",
                       "goal_answers": ANSWERS})
        sd = _enrollment(fake_db, "flat@example.com")["source_data"]
        assert sd["goal_line"] == ANSWERS["outcome_goal"]
        assert sd["inner_obstacle"] == ANSWERS["inner_obstacle"]

    def test_junk_answers_are_dropped(self, client, fake_db):
        _post(client, {"email": "junk@example.com", "source": "goal_2027",
                       "goal_answers": {
                           "outcome_goal": "Fine",
                           "Bad Key!": "dropped",
                           "nested": {"no": "objects"},
                           "empty": "   ",
                       }})
        kept = _enrollment(fake_db, "junk@example.com")["source_data"]["goal_answers"]
        assert set(kept) == {"outcome_goal"}

    def test_an_essay_cannot_blow_up_the_row(self, client, fake_db):
        _post(client, {"email": "essay@example.com", "source": "goal_2027",
                       "goal_answers": {"outcome_goal": "x" * 5000,
                                        **{f"q{i}": "y" * 400 for i in range(60)}}})
        kept = _enrollment(fake_db, "essay@example.com")["source_data"]["goal_answers"]
        assert len(kept) <= 45
        assert all(len(v) <= 1200 for v in kept.values())
        assert sum(len(v) for v in kept.values()) <= 12000

    def test_other_sources_carry_no_answers(self, client, fake_db):
        _post(client, {"email": "other@example.com", "source": "race_profile",
                       "goal_answers": ANSWERS})
        sd = _enrollment(fake_db, "other@example.com")["source_data"]
        assert "goal_answers" not in sd and "poster_token" not in sd

    def test_bad_variant_is_ignored(self, client, fake_db):
        _post(client, {"email": "variant@example.com", "source": "goal_2027",
                       "goal_answers": ANSWERS, "offer_variant": "Z"})
        assert "offer_variant" not in _enrollment(fake_db, "variant@example.com")["source_data"]


class TestPosterRoute:
    def test_malformed_token_is_a_404(self, client):
        assert client.get("/poster/not a token.png").status_code == 404

    def test_unknown_token_is_a_404(self, client):
        assert client.get("/poster/" + "z" * 32 + ".png").status_code == 404


class TestPosterImage:
    def test_renders_a_png(self):
        png = render_poster(ANSWERS, name="Ada Rider")
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
        assert len(png) > 5000

    def test_empty_answers_still_render(self):
        assert render_poster({}, name="")[:8] == b"\x89PNG\r\n\x1a\n"

    def test_long_goal_does_not_crash(self):
        assert render_poster({"outcome_goal": "word " * 200})[:4] == b"\x89PNG"
