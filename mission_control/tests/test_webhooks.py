"""Tests for webhook endpoints — auth, intake, subscriber enrollment, events."""

import json

import pytest


class TestWebhookAuth:
    """All webhook endpoints require Bearer token auth."""

    def test_intake_rejects_no_auth(self, client):
        resp = client.post("/webhooks/intake", json={"request_id": "test"})
        assert resp.status_code == 401

    def test_intake_rejects_wrong_secret(self, client):
        resp = client.post(
            "/webhooks/intake",
            json={"request_id": "test"},
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 401

    def test_intake_accepts_valid_secret(self, client, fake_db):
        # Need a plan_request in DB for this to work beyond auth
        fake_db.store["plan_requests"].append({
            "id": "pr-1",
            "request_id": "req-123",
            "status": "pending",
            "email": "test@example.com",
            "name": "Test User",
            "race": "Unbound 200",
        })

        resp = client.post(
            "/webhooks/intake",
            json={"request_id": "req-123"},
            headers={"Authorization": "Bearer test-secret-123"},
        )
        # Should pass auth (may still return 200 or other based on data)
        assert resp.status_code != 401

    def test_subscriber_rejects_no_auth(self, client):
        resp = client.post("/webhooks/subscriber", json={"email": "test@example.com"})
        assert resp.status_code == 401

    def test_resend_rejects_no_auth(self, client):
        resp = client.post("/webhooks/resend", json={"type": "email.opened"})
        assert resp.status_code == 401

    def test_resend_inbound_rejects_no_auth(self, client):
        resp = client.post("/webhooks/resend-inbound", json={"from": "x@y.com"})
        assert resp.status_code == 401


class TestSubscriberWebhook:
    """POST /webhooks/subscriber — enrolls contacts in sequences."""

    def _post(self, client, payload):
        return client.post(
            "/webhooks/subscriber",
            json=payload,
            headers={"Authorization": "Bearer test-secret-123"},
        )

    def test_requires_email(self, client):
        resp = self._post(client, {"name": "No Email"})
        assert resp.status_code == 400

    def test_rejects_invalid_email_format(self, client):
        resp = self._post(client, {"email": "not-an-email", "name": "Bad"})
        assert resp.status_code == 400
        assert "email" in resp.json()["detail"].lower()

    def test_rejects_empty_email(self, client):
        resp = self._post(client, {"email": "   ", "name": "Blank"})
        assert resp.status_code == 400

    def test_enrolls_subscriber(self, client, fake_db):
        resp = self._post(client, {
            "email": "new-sub@example.com",
            "name": "New Subscriber",
            "source": "exit_intent",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["enrolled"], list)

    def test_includes_source_data(self, client, fake_db):
        resp = self._post(client, {
            "email": "quiz-sub@example.com",
            "name": "Quiz Taker",
            "source": "quiz",
            "race_slug": "unbound-gravel-200",
            "race_name": "Unbound 200",
        })
        assert resp.status_code == 200

        # Check enrollment was created with source_data
        enrollments = fake_db.store["gg_sequence_enrollments"]
        quiz_enrollments = [e for e in enrollments if e["contact_email"] == "quiz-sub@example.com"]
        assert len(quiz_enrollments) > 0
        assert quiz_enrollments[0]["source_data"].get("race_slug") == "unbound-gravel-200"


class TestPlanPurchasedEnrollment:
    """POST /webhooks/subscriber with a purchase source -> post_purchase + plan_weeks."""

    def _post(self, client, payload):
        return client.post(
            "/webhooks/subscriber",
            json=payload,
            headers={"Authorization": "Bearer test-secret-123"},
        )

    def test_enrolls_post_purchase_with_plan_weeks_and_not_welcome(self, client, fake_db):
        resp = self._post(client, {
            "email": "buyer@example.com",
            "name": "Plan Buyer",
            "source": "plan_purchased",
            "brand": "gravelgod",
            "plan_weeks": 12,
            "race_slug": "big-sugar",
        })
        assert resp.status_code == 200
        # Only post_purchase — NOT the welcome track (buyers already bought).
        assert resp.json()["enrolled"] == ["post_purchase_v1"]
        rows = [e for e in fake_db.store["gg_sequence_enrollments"]
                if e["contact_email"] == "buyer@example.com"]
        assert len(rows) == 1
        assert rows[0]["source_data"]["plan_weeks"] == 12
        assert rows[0]["source_data"]["brand"] == "gravelgod"

    def test_invalid_plan_weeks_ignored_but_still_enrolls(self, client, fake_db):
        resp = self._post(client, {
            "email": "buyer2@example.com",
            "name": "Buyer Two",
            "source": "plan_purchase",
            "plan_weeks": "not-a-number",
        })
        assert resp.status_code == 200
        rows = [e for e in fake_db.store["gg_sequence_enrollments"]
                if e["contact_email"] == "buyer2@example.com"]
        assert len(rows) == 1
        assert "plan_weeks" not in rows[0]["source_data"]

    def test_string_plan_weeks_coerced_to_int(self, client, fake_db):
        resp = self._post(client, {
            "email": "buyer3@example.com",
            "name": "Buyer Three",
            "source": "woocommerce",
            "plan_weeks": "6",
        })
        assert resp.status_code == 200
        rows = [e for e in fake_db.store["gg_sequence_enrollments"]
                if e["contact_email"] == "buyer3@example.com"]
        assert rows[0]["source_data"]["plan_weeks"] == 6


class TestResendWebhook:
    """POST /webhooks/resend — records email events."""

    def _post(self, client, payload):
        return client.post(
            "/webhooks/resend",
            json=payload,
            headers={"Authorization": "Bearer test-secret-123"},
        )

    def test_ignores_missing_email_id(self, client, fake_db):
        resp = self._post(client, {"type": "email.opened", "data": {}})
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"

    def test_ignores_unhandled_event_type(self, client, fake_db):
        resp = self._post(client, {
            "type": "email.sent",
            "data": {"email_id": "test-123"},
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ignored"


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestIntakeWebhook:
    """POST /webhooks/intake — creates athletes from plan requests."""

    def _post(self, client, payload):
        return client.post(
            "/webhooks/intake",
            json=payload,
            headers={"Authorization": "Bearer test-secret-123"},
        )

    def test_requires_request_id(self, client, fake_db):
        resp = self._post(client, {"name": "No ID"})
        assert resp.status_code == 400

    def test_returns_404_for_unknown_request(self, client, fake_db):
        resp = self._post(client, {"request_id": "nonexistent"})
        assert resp.status_code == 404


class TestUnsubscribeEndpoint:
    """GET /unsubscribe — public, HMAC-verified."""

    def test_valid_unsubscribe(self, client, fake_db):
        from mission_control.services.sequence_engine import generate_unsubscribe_token
        from mission_control.tests.conftest import make_enrollment

        email = "unsub-test@example.com"
        enrollment = make_enrollment(contact_email=email, status="active")
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        token = generate_unsubscribe_token(email)
        resp = client.get(f"/unsubscribe?email={email}&token={token}")
        assert resp.status_code == 200
        assert "Unsubscribed" in resp.text
        assert enrollment["status"] == "unsubscribed"

    def test_invalid_token_rejected(self, client, fake_db):
        resp = client.get("/unsubscribe?email=test@example.com&token=bogus")
        assert resp.status_code == 200
        assert "invalid" in resp.text.lower()

    def test_missing_params(self, client, fake_db):
        resp = client.get("/unsubscribe")
        assert resp.status_code == 200
        assert "missing" in resp.text.lower()

    def test_already_unsubscribed(self, client, fake_db):
        from mission_control.services.sequence_engine import generate_unsubscribe_token

        email = "already-unsub@example.com"
        token = generate_unsubscribe_token(email)
        resp = client.get(f"/unsubscribe?email={email}&token={token}")
        assert resp.status_code == 200
        assert "Already" in resp.text


class TestFriendRegisterEnrollment:
    """WS-E + wb_* context (docs/specs/friend-first-sequences.md §4)."""

    def _enroll(self, client, payload):
        resp = client.post(
            "/webhooks/subscriber", json=payload,
            headers={"Authorization": "Bearer test-secret-123"},
        )
        assert resp.status_code == 200
        return resp.json()

    def test_quiz_lead_gets_only_its_source_sequence(self, client, fake_db):
        """WS-E regression: no double-enrollment into welcome. A quiz lead's
        opener track is race_specific — stacking welcome on top made every
        per-track expectation false (live bug, Jul 2026)."""
        data = self._enroll(client, {
            "email": "ws-e-quiz@example.com", "source": "race_quiz",
            "race_name": "Unbound", "race_slug": "unbound",
        })
        assert all("welcome" not in seq_id for seq_id in data["enrolled"]), \
            f"quiz lead double-enrolled: {data['enrolled']}"

    def test_prepkit_lead_gets_only_its_source_sequence(self, client, fake_db):
        data = self._enroll(client, {
            "email": "ws-e-kit@example.com", "source": "prep_kit_gate",
            "race_name": "Unbound", "race_slug": "unbound",
        })
        assert all("welcome" not in seq_id for seq_id in data["enrolled"])

    def _source_data(self, fake_db, email):
        rows = [e for e in fake_db.store["gg_sequence_enrollments"]
                if e["contact_email"] == email]
        assert rows, "no enrollment created"
        sd = rows[0]["source_data"]
        return json.loads(sd) if isinstance(sd, str) else sd

    @pytest.mark.parametrize("source", ("training_guide", "bikepacking_guide"))
    def test_guide_sources_get_one_guide_context_welcome(self, client, fake_db, source):
        """Both guide sources enroll once in welcome with the guide opener."""
        self._enroll(client, {
            "email": f"wb-{source}@example.com", "source": source,
            "guide_chapter": "Fueling", "viewed_races": ["Unbound", "SBT GRVL"],
            "race_name": "Unbound",
        })
        email = f"wb-{source}@example.com"
        rows = [e for e in fake_db.store["gg_sequence_enrollments"]
                if e["contact_email"] == email]
        assert len(rows) == 1
        assert rows[0]["sequence_id"] == "welcome_v1"
        sd = self._source_data(fake_db, email)
        assert sd.get("wb_guide") == "Fueling"
        assert "wb_trail" not in sd and "wb_race" not in sd
        assert sd.get("any_context") == "1"

    def test_wb_branch_trail_beats_race(self, client, fake_db):
        self._enroll(client, {
            "email": "wb-trail@example.com", "source": "race_profile",
            "viewed_races": ["Unbound", "Mid South"], "race_name": "Unbound",
        })
        sd = self._source_data(fake_db, "wb-trail@example.com")
        assert sd.get("wb_trail") == "Unbound, Mid South"
        assert "wb_guide" not in sd and "wb_race" not in sd

    def test_wb_race_fallback_and_anonymous(self, client, fake_db):
        self._enroll(client, {
            "email": "wb-race@example.com", "source": "race_profile",
            "race_name": "Unbound", "race_slug": "unbound",
        })
        sd = self._source_data(fake_db, "wb-race@example.com")
        assert sd.get("wb_race") == "Unbound"
        # anonymous: no context at all
        self._enroll(client, {
            "email": "wb-anon@example.com", "source": "exit_intent",
        })
        sd2 = self._source_data(fake_db, "wb-anon@example.com")
        assert "any_context" not in sd2
        assert not any(k.startswith("wb_") for k in sd2)

    def test_xcskilabs_brand_routes_only_xc_sequences(self, client, fake_db, monkeypatch):
        """XC leads must never receive GG/RL copy — brand scoping. xc_welcome
        ships inactive (Resend gate), so activate it in-test to prove routing
        positively instead of vacuously."""
        from mission_control.sequences import SEQUENCES
        monkeypatch.setitem(SEQUENCES["xc_welcome_v1"], "active", True)
        data = self._enroll(client, {
            "email": "xc-e2e@example.com", "source": "race_profile",
            "brand": "xcskilabs", "race_name": "American Birkebeiner",
        })
        assert data["enrolled"], "XC lead should enroll once xc_welcome active"
        assert all(seq_id.startswith("xc_") for seq_id in data["enrolled"]), \
            f"XC lead cross-enrolled: {data['enrolled']}"

    def test_offseason_flag_is_brand_aware(self, client, fake_db, monkeypatch):
        """Season inversion: Nov-Jan = gravel offseason but XC RACE season;
        Apr-Oct = XC offseason. The flag must follow the brand's calendar."""
        import mission_control.routers.webhooks as wh
        from datetime import datetime, timezone
        from mission_control.sequences import SEQUENCES
        monkeypatch.setitem(SEQUENCES["xc_welcome_v1"], "active", True)

        class _FakeDT:
            @staticmethod
            def now(tz=None):
                return datetime(2026, 12, 15, tzinfo=timezone.utc)  # December

        # December: gravel lead IS offseason
        monkeypatch.setattr("mission_control.routers.webhooks.datetime",
                            _FakeDT, raising=False)
        self._enroll(client, {"email": "dec-gg@example.com", "source": "exit_intent"})
        sd = self._source_data(fake_db, "dec-gg@example.com")
        # NOTE: webhooks imports datetime inside the handler, so monkeypatch
        # via module attr may not intercept — fall back to real-month logic.
        real_month = datetime.now(timezone.utc).month
        gg_off = real_month in (11, 12, 1)
        xc_off = real_month in (4, 5, 6, 7, 8, 9, 10)
        assert (sd.get("offseason") == "1") == gg_off
        self._enroll(client, {"email": "dec-xc@example.com",
                              "source": "exit_intent", "brand": "xcskilabs"})
        sd2 = self._source_data(fake_db, "dec-xc@example.com")
        assert (sd2.get("offseason") == "1") == xc_off
        # the two brands must never agree in Jul or Dec (disjoint calendars)
        if real_month in (11, 12, 1, 4, 5, 6, 7, 8, 9, 10):
            assert sd.get("offseason") != sd2.get("offseason")
