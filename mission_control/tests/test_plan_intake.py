"""A skier's custom-plan questionnaire (xcskilabs.com/questionnaire/, source=plan_intake).

It is a lead (race context stays), but nothing automated goes to the skier:
Matti replies personally. So nothing is enrolled, and that is by design, not
an [UNROUTED] miss. The whole submission is stored in gg_audit_log
(plan_intake_received) before anything else, and Matti gets an inbox-visible
alert with every answer. If either the store or the alert fails, the request
fails, so the worker answers 503 and the page keeps the draft.
"""
from __future__ import annotations

import json

import pytest

from mission_control.routers import webhooks as wh

EMAIL = "skier@example.com"
ANSWERS = {
    "target_race": "American Birkebeiner",
    "race_date": "February 27, 2027",
    "race_distance": "50km",
    "technique": "classic",
    "weekly_hours": "8",
    "injuries": "Test answer: left <knee>",
    "plan_workarounds": "Test answer: night shifts",
    "email": EMAIL,
    "name": "Test Skier",
}


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    import mission_control.services.sequence_engine as se
    monkeypatch.setattr(se, "_send_email_sync", lambda *a, **k: "rs-test")


def _post(client, body):
    return client.post("/webhooks/subscriber", json=body,
                       headers={"Authorization": "Bearer test-secret-123"})


def _body(**extra):
    body = {"email": EMAIL, "name": "Test Skier", "source": "plan_intake", "brand": "xcskilabs",
            "race_slug": "american-birkebeiner", "race_name": "American Birkebeiner",
            "goal_answers": dict(ANSWERS)}
    body.update(extra)
    return body


def _capture_sends(monkeypatch):
    import mission_control.services.sequence_engine as se
    sent = []
    monkeypatch.setattr(se, "_send_email_sync",
                        lambda to, subject, html, brand="gravelgod", *a: sent.append(
                            {"to": to, "subject": subject, "html": html, "brand": brand}) or "rs-1")
    return sent


def _audit(fake_db, action):
    return [r for r in fake_db.store.get("gg_audit_log", []) if r.get("action") == action]


class TestPlanIntake:
    def test_it_is_a_lead_and_an_answer_source(self):
        assert "plan_intake" in wh._ANSWER_SOURCES
        assert "plan_intake" not in wh._NOT_LEAD_SOURCES
        assert "plan_intake" in wh._NO_SEQUENCE_SOURCES

    def test_answers_and_race_context_are_stored(self, client, fake_db, monkeypatch):
        _capture_sends(monkeypatch)
        resp = _post(client, _body())
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "enrolled": []}
        rows = _audit(fake_db, "plan_intake_received")
        assert len(rows) == 1 and rows[0]["entity_id"] == EMAIL
        stored = json.loads(rows[0]["details"])
        assert stored["brand"] == "xcskilabs" and stored["name"] == "Test Skier"
        assert stored["source_data"]["goal_answers"] == ANSWERS
        assert stored["source_data"]["race_slug"] == "american-birkebeiner"
        assert stored["source_data"]["race_name"] == "American Birkebeiner"

    def test_nothing_is_enrolled_and_it_is_not_unrouted(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _body())
        assert fake_db.store.get("gg_sequence_enrollments", []) == []
        assert _audit(fake_db, "lead_unrouted") == []
        assert _audit(fake_db, "subscriber_received") == []
        assert not any("[UNROUTED]" in s["subject"] for s in sent)

    def test_never_falls_through_to_the_xc_welcome(self, client, fake_db, monkeypatch):
        # new_subscriber is the default trigger; xc_welcome_v1 listens on it.
        _capture_sends(monkeypatch)
        _post(client, _body())
        assert not any(e.get("sequence_id") == "xc_welcome_v1"
                       for e in fake_db.store.get("gg_sequence_enrollments", []))

    def test_matti_gets_one_inbox_visible_alert_with_every_answer(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _body())
        assert [(s["subject"], s["brand"]) for s in sent] == [
            ("[XC] Plan questionnaire filed · Test Skier", "xcskilabs")]
        assert not sent[0]["subject"].lower().startswith("new lead")
        html = sent[0]["html"]
        for key in ANSWERS:
            assert f">{key}</td>" in html, key
        assert "Test answer: left &lt;knee&gt;" in html
        assert "<knee>" not in html
        assert "American Birkebeiner" in html
        assert "Reply personally" in html

    def test_no_name_uses_the_email_in_the_subject(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _body(name=""))
        assert sent[0]["subject"] == f"[XC] Plan questionnaire filed · {EMAIL}"

    def test_answers_are_capped(self, client, fake_db, monkeypatch):
        _capture_sends(monkeypatch)
        answers = {f"field_{i}": "x" * 5000 for i in range(80)}
        answers["Bad-Key"] = "dropped"
        _post(client, _body(goal_answers=answers))
        kept = json.loads(_audit(fake_db, "plan_intake_received")[0]["details"])["source_data"]["goal_answers"]
        assert "Bad-Key" not in kept
        assert all(len(v) <= wh._MAX_GOAL_ANSWER_LEN for v in kept.values())
        assert sum(len(v) for v in kept.values()) <= wh._MAX_GOAL_ANSWERS_TOTAL

    def test_a_resubmission_is_stored_and_alerted_again(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, _body())
        _post(client, _body())
        assert len(_audit(fake_db, "plan_intake_received")) == 2
        assert len(sent) == 2

    def test_a_failed_alert_fails_the_request_but_keeps_the_answers(self, client, fake_db, monkeypatch):
        import mission_control.services.sequence_engine as se

        def boom(*a, **k):
            raise RuntimeError("resend down")
        monkeypatch.setattr(se, "_send_email_sync", boom)
        resp = _post(client, _body())
        assert resp.status_code == 502
        assert len(_audit(fake_db, "plan_intake_received")) == 1
        assert len(_audit(fake_db, "plan_intake_alert_failed")) == 1

    def test_a_failed_store_fails_the_request_and_sends_nothing(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        real = wh.db.log_action

        def failing(action, *a, **k):
            if action == "plan_intake_received":
                raise RuntimeError("db down")
            return real(action, *a, **k)
        monkeypatch.setattr(wh.db, "log_action", failing)
        with pytest.raises(RuntimeError, match="db down"):
            _post(client, _body())
        assert sent == []

    def test_other_sources_still_route_and_alert_as_before(self, client, fake_db, monkeypatch):
        sent = _capture_sends(monkeypatch)
        _post(client, {"email": "guide@example.com", "name": "Guide", "source": "training_guide",
                       "brand": "xcskilabs"})
        assert _audit(fake_db, "plan_intake_received") == []
        assert any(e["sequence_id"] == "xc_welcome_v1"
                   for e in fake_db.store.get("gg_sequence_enrollments", []))
        assert sent and sent[0]["subject"].startswith("new lead ·")


class TestPlanIntakeBrandRequired:
    """plan_intake must name a supported brand: no gravelgod default.

    A skier's questionnaire filed as Gravel God would be stored under the
    wrong brand and reach Matti as a [GG] alert. Other sources keep the
    gravelgod default for now (known follow-up)."""

    @pytest.mark.parametrize("brand", [None, "", "nordicgod", ["xcskilabs"], 7])
    def test_missing_or_unknown_brand_is_a_400_and_nothing_happens(
            self, client, fake_db, monkeypatch, brand):
        sent = _capture_sends(monkeypatch)
        body = _body(brand=brand)
        if brand is None:
            del body["brand"]
        resp = _post(client, body)
        assert resp.status_code == 400
        assert resp.json() == {"detail": "Unknown brand"}
        assert _audit(fake_db, "plan_intake_received") == []
        assert fake_db.store.get("gg_audit_log", []) == []
        assert sent == []

    @pytest.mark.parametrize("brand", ["xcskilabs", "XCSkiLabs", "roadielabs", "gravelgod"])
    def test_every_supported_brand_is_accepted(self, client, fake_db, monkeypatch, brand):
        _capture_sends(monkeypatch)
        resp = _post(client, _body(brand=brand))
        assert resp.status_code == 200
        stored = json.loads(_audit(fake_db, "plan_intake_received")[0]["details"])
        assert stored["brand"] == brand.lower()

    @pytest.mark.parametrize("source", ["training_guide", "exit_intent", "race_quiz", "goal_2027"])
    @pytest.mark.parametrize("brand", [None, "", "nordicgod", ["gravelgod"]])
    def test_every_source_refuses_a_missing_or_unknown_brand(self, client, fake_db, monkeypatch,
                                                             source, brand):
        sends = _capture_sends(monkeypatch)
        body = {"email": "guide@example.com", "name": "Guide", "source": source, "brand": brand}
        resp = _post(client, body)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Unknown brand"
        assert not fake_db.store.get("gg_sequence_enrollments")
        assert not fake_db.store.get("gg_audit_log")
        assert sends == []

    def test_no_gravelgod_default_left_in_brand_routing(self):
        import inspect
        import mission_control.routers.webhooks as wh
        src = inspect.getsource(wh.subscriber_webhook)
        assert 'raw_brand or "gravelgod"' not in src
        assert 'brand = "gravelgod"' not in src
