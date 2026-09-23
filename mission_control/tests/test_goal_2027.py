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
                       "goal_answers": {"outcome_goal": "x" * 9000,
                                        **{f"q{i}": "y" * 900 for i in range(90)}}})
        kept = _enrollment(fake_db, "essay@example.com")["source_data"]["goal_answers"]
        assert len(kept) <= 64
        assert all(len(v) <= 4000 for v in kept.values())
        assert sum(len(v) for v in kept.values()) <= 30000

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


class TestAthleteReviewIsTransactional:
    """A coached athlete filing a review is not being marketed to. Every
    marketing guard in the engine would otherwise drop it (Fable review,
    Sep 22): they have bought a plan, they may have unsubscribed years ago,
    and they are not a new sales deal.
    """

    def test_exempt_from_the_marketing_guards(self):
        from mission_control.services.sequence_engine import _POST_PURCHASE_TRIGGERS
        assert "athlete_review" in _POST_PURCHASE_TRIGGERS

    def test_an_unsubscribed_athlete_still_gets_stored(self, client, fake_db):
        fake_db.store["gg_sequence_enrollments"].append({
            "id": "old-1", "sequence_id": "welcome_v1",
            "contact_email": "unsub@example.com", "status": "unsubscribed",
            "source": "exit_intent", "source_data": {},
        })
        resp = _post(client, {"email": "unsub@example.com", "name": "Unsubbed",
                              "source": "athlete_review", "goal_answers": ANSWERS})
        assert "athlete_review_v1" in resp.json()["enrolled"]

    def test_resubmitting_updates_the_answers(self, client, fake_db):
        first = dict(ANSWERS, outcome_goal="First answer")
        _post(client, {"email": "again@example.com", "name": "Again",
                       "source": "athlete_review", "goal_answers": first})
        token = _enrollment(fake_db, "again@example.com")["source_data"]["poster_token"]

        second = dict(ANSWERS, outcome_goal="Corrected answer")
        _post(client, {"email": "again@example.com", "name": "Again",
                       "source": "athlete_review", "goal_answers": second})
        sd = _enrollment(fake_db, "again@example.com")["source_data"]
        assert sd["goal_answers"]["outcome_goal"] == "Corrected answer"
        assert sd["poster_token"] == token, "a poster link already emailed must keep working"


class TestResubmitResendsTheResults:
    """The results screen promises a copy, so a correction must send one."""

    def _two_posts(self, client, fake_db, monkeypatch, gap_minutes=None):
        from datetime import datetime, timedelta, timezone
        import mission_control.services.sequence_engine as se
        sent = []
        monkeypatch.setattr(se, "RESEND_API_KEY", "test-key")
        monkeypatch.setattr(se, "_send_email_sync",
                            lambda to, subject, *a: (to == "fix@example.com" and sent.append(subject)) or "rs-1")
        _post(client, {"email": "fix@example.com", "name": "Fix", "source": "goal_2027",
                       "goal_answers": dict(ANSWERS, outcome_goal="First")})
        enrollment = _enrollment(fake_db, "fix@example.com")
        if gap_minutes is not None:  # the day-0 email the scheduler already sent
            fake_db.store["gg_sequence_sends"].append({
                "id": "s0", "enrollment_id": enrollment["id"], "step_index": 0,
                "template": "goal_2027_results", "subject": "x",
                "sent_at": (datetime.now(timezone.utc) - timedelta(minutes=gap_minutes)).isoformat(),
            })
        _post(client, {"email": "fix@example.com", "name": "Fix", "source": "goal_2027",
                       "goal_answers": dict(ANSWERS, outcome_goal="Second")})
        return sent

    def test_a_correction_sends_the_revised_poster(self, client, fake_db, monkeypatch):
        sent = self._two_posts(client, fake_db, monkeypatch, gap_minutes=30)
        assert sent == ["your 2027 goal, revised"]

    def test_a_quick_correction_still_gets_one(self, client, fake_db, monkeypatch):
        assert self._two_posts(client, fake_db, monkeypatch, gap_minutes=1) == ["your 2027 goal, revised"]

    def test_nothing_extra_before_the_first_email_goes(self, client, fake_db, monkeypatch):
        # the scheduled day-0 send renders the corrected answers anyway
        assert self._two_posts(client, fake_db, monkeypatch) == []

    def test_resends_are_capped(self, client, fake_db, monkeypatch):
        from datetime import datetime, timedelta, timezone
        from mission_control.services.sequence_engine import MAX_RESENDS
        _post(client, {"email": "cap@example.com", "name": "Cap", "source": "goal_2027",
                       "goal_answers": ANSWERS})
        enrollment = _enrollment(fake_db, "cap@example.com")
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        for i in range(MAX_RESENDS + 1):
            fake_db.store["gg_sequence_sends"].append({
                "id": f"c{i}", "enrollment_id": enrollment["id"], "step_index": 0,
                "template": "goal_2027_results", "subject": "x", "sent_at": old})
        import mission_control.services.sequence_engine as se
        sent = []
        monkeypatch.setattr(se, "RESEND_API_KEY", "test-key")
        monkeypatch.setattr(se, "_send_email_sync",
                            lambda to, *a: (to == "cap@example.com" and sent.append(a)) or "rs-2")
        _post(client, {"email": "cap@example.com", "name": "Cap", "source": "goal_2027",
                       "goal_answers": ANSWERS})
        assert sent == []

    def test_an_unsubscribed_lead_gets_nothing(self, client, fake_db, monkeypatch):
        import mission_control.services.sequence_engine as se
        sent = []
        monkeypatch.setattr(se, "RESEND_API_KEY", "test-key")
        monkeypatch.setattr(se, "_send_email_sync", lambda to, *a: (to == "gone@example.com" and sent.append(a)) or "rs-3")
        _post(client, {"email": "gone@example.com", "name": "Gone", "source": "goal_2027",
                       "goal_answers": ANSWERS})
        _enrollment(fake_db, "gone@example.com")["status"] = "unsubscribed"
        _post(client, {"email": "gone@example.com", "name": "Gone", "source": "goal_2027",
                       "goal_answers": ANSWERS})
        assert sent == []


class TestCapsFitTheLongestForm:
    """The athlete form has 50 answers and a 15-minute free-write."""

    def test_key_cap_clears_the_form(self):
        from mission_control.routers.webhooks import _MAX_GOAL_ANSWER_KEYS
        assert _MAX_GOAL_ANSWER_KEYS >= 56

    def test_answer_cap_fits_a_fifteen_minute_write(self):
        from mission_control.routers.webhooks import _MAX_GOAL_ANSWER_LEN
        assert _MAX_GOAL_ANSWER_LEN >= 3000
