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
