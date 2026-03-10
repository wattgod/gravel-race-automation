"""Tests for plan delivery endpoint — /athletes/{slug}/deliver.

Covers:
- Happy path: full artifact set, email sends, status updated
- No artifacts: clear error returned
- Partial signed URL failures: delivers what exists with warning
- Re-delivery: idempotent (delivered status allows re-delivery)
- Email failure: plan marked delivery_failed, not delivered
- No RESEND_API_KEY: graceful degradation, marked delivered_no_email
- No email address on athlete: 400 error
- Plan not in deliverable state: 409 error
- Athlete not found: 404 error
"""

import os
import sys
import types
from unittest.mock import patch, MagicMock

import pytest

# Env vars before MC imports
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret-123")
os.environ.setdefault("RESEND_API_KEY", "")
os.environ.setdefault("MISSION_CONTROL_SECRET", "test-secret-for-tests")

ADMIN_HEADERS = {"Authorization": f"Bearer {os.environ['MISSION_CONTROL_SECRET']}"}

# Pre-mock supabase
if "supabase" not in sys.modules or not hasattr(sys.modules["supabase"], "Client"):
    _fake_supabase = types.ModuleType("supabase")
    _fake_supabase.Client = MagicMock
    _fake_supabase.create_client = MagicMock()
    sys.modules["supabase"] = _fake_supabase

import mission_control.supabase_client  # noqa: E402

from mission_control.tests.conftest import make_athlete  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_athlete():
    return make_athlete(
        slug="test-athlete",
        email="test@example.com",
        plan_status="pipeline_complete",
    )


@pytest.fixture
def fake_files():
    return [
        {"file_type": "guide_pdf", "storage_path": "test-athlete/guide.pdf", "file_name": "guide.pdf"},
        {"file_type": "guide_html", "storage_path": "test-athlete/guide.html", "file_name": "guide.html"},
        {"file_type": "zwo", "storage_path": "test-athlete/workouts/W01.zwo", "file_name": "W01.zwo"},
        {"file_type": "methodology_md", "storage_path": "test-athlete/methodology.md", "file_name": "methodology.md"},
        {"file_type": "intake", "storage_path": "test-athlete/intake.json", "file_name": "intake.json"},  # non-deliverable
    ]


def _make_client():
    """Build a test client with mocked DB and no lifespan (no scheduler)."""
    from contextlib import asynccontextmanager
    from fastapi.testclient import TestClient

    with patch("mission_control.app.lifespan") as mock_lifespan:
        @asynccontextmanager
        async def noop_lifespan(app):
            yield

        mock_lifespan.side_effect = noop_lifespan

        from mission_control.app import create_app
        app = create_app()
        app.router.lifespan_context = noop_lifespan
        return TestClient(app)


@pytest.fixture
def deliver_client(fake_athlete, fake_files):
    """Client with mocked DB returning a deliverable athlete and files."""
    with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
        with patch("mission_control.supabase_client.get_athlete", return_value=fake_athlete) as mock_get:
            with patch("mission_control.supabase_client.get_files", return_value=fake_files) as mock_files:
                with patch("mission_control.supabase_client.update_athlete") as mock_update:
                    with patch("mission_control.supabase_client.log_action") as mock_log:
                        with patch("mission_control.supabase_client.log_communication") as mock_comm:
                            client = _make_client()
                            with client:
                                yield {
                                    "client": client,
                                    "mock_get": mock_get,
                                    "mock_files": mock_files,
                                    "mock_update": mock_update,
                                    "mock_log": mock_log,
                                    "mock_comm": mock_comm,
                                    "athlete": fake_athlete,
                                }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestDeliverHappyPath:
    def test_dry_run_returns_preview(self, deliver_client):
        """Default dry_run=True returns a confirmation prompt."""
        c = deliver_client["client"]
        resp = c.post("/athletes/test-athlete/deliver", data={"dry_run": "true"}, headers=ADMIN_HEADERS)
        assert resp.status_code == 200
        assert "Preview" in resp.text
        assert "Confirm Deliver" in resp.text

    def test_full_delivery_with_email(self, deliver_client):
        """Full delivery: signed URLs generated, email sent, status=delivered."""
        c = deliver_client["client"]

        fake_resend = MagicMock()
        fake_resend.Emails.send.return_value = {"id": "resend-123"}

        with patch("mission_control.services.file_storage.get_signed_url", return_value="https://signed.url/file"):
            with patch.dict(os.environ, {"RESEND_API_KEY": "re_test_key"}):
                with patch("mission_control.config.RESEND_API_KEY", "re_test_key"):
                    with patch.dict(sys.modules, {"resend": fake_resend}):
                        resp = c.post("/athletes/test-athlete/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert "Done" in resp.text
        assert "4 files" in resp.text  # 4 deliverables (pdf, html, zwo, md)

        # Status updated to delivered
        deliver_client["mock_update"].assert_called()
        call_args = deliver_client["mock_update"].call_args
        assert call_args[0][1]["plan_status"] == "delivered"

        # Communication logged as sent
        deliver_client["mock_comm"].assert_called_once()
        comm_args = deliver_client["mock_comm"].call_args
        assert comm_args[1]["status"] == "sent"


# ---------------------------------------------------------------------------
# No artifacts
# ---------------------------------------------------------------------------

class TestDeliverNoArtifacts:
    def test_no_artifacts_returns_error(self, fake_athlete):
        """Athlete with no deliverable files gets a clear error."""
        with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
            with patch("mission_control.supabase_client.get_athlete", return_value=fake_athlete):
                with patch("mission_control.supabase_client.get_files", return_value=[]):
                    client = _make_client()
                    with client:
                        resp = client.post("/athletes/test-athlete/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 404
        assert "No deliverable artifacts" in resp.text


# ---------------------------------------------------------------------------
# Partial signed URL failures
# ---------------------------------------------------------------------------

class TestDeliverPartialURLFailure:
    def test_partial_url_failure_delivers_with_warning(self, deliver_client):
        """If some URLs fail to sign, deliver what we have with a warning."""
        c = deliver_client["client"]
        call_count = 0

        def flaky_sign(path, expires_in=3600):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Storage timeout")
            return f"https://signed.url/{call_count}"

        with patch("mission_control.services.file_storage.get_signed_url", side_effect=flaky_sign):
            with patch("mission_control.config.RESEND_API_KEY", ""):
                resp = c.post("/athletes/test-athlete/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert "3 files" in resp.text  # 3 of 4 succeeded
        assert "could not be signed" in resp.text


# ---------------------------------------------------------------------------
# Re-delivery
# ---------------------------------------------------------------------------

class TestRedelivery:
    def test_redelivery_allowed(self):
        """Already-delivered plans can be re-delivered (idempotent)."""
        athlete = make_athlete(slug="re-test", email="re@test.com", plan_status="delivered")
        files = [
            {"file_type": "guide_pdf", "storage_path": "re-test/guide.pdf", "file_name": "guide.pdf"},
        ]

        with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
            with patch("mission_control.supabase_client.get_athlete", return_value=athlete):
                with patch("mission_control.supabase_client.get_files", return_value=files):
                    with patch("mission_control.supabase_client.update_athlete"):
                        with patch("mission_control.supabase_client.log_action"):
                            with patch("mission_control.supabase_client.log_communication"):
                                with patch("mission_control.services.file_storage.get_signed_url", return_value="https://url"):
                                    with patch("mission_control.config.RESEND_API_KEY", ""):
                                        client = _make_client()
                                        with client:
                                            resp = client.post("/athletes/re-test/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert "1 files" in resp.text


# ---------------------------------------------------------------------------
# Email failure
# ---------------------------------------------------------------------------

class TestDeliverEmailFailure:
    def test_email_failure_marks_delivery_failed(self, deliver_client):
        """If email send throws, plan status should be delivery_failed, not delivered."""
        c = deliver_client["client"]

        fake_resend = MagicMock()
        fake_resend.Emails.send.side_effect = RuntimeError("SMTP timeout")

        with patch("mission_control.services.file_storage.get_signed_url", return_value="https://signed.url/file"):
            with patch("mission_control.config.RESEND_API_KEY", "re_test_key"):
                with patch.dict(sys.modules, {"resend": fake_resend}):
                    resp = c.post("/athletes/test-athlete/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert "Email send failed" in resp.text

        # Status should be delivery_failed
        call_args = deliver_client["mock_update"].call_args
        assert call_args[0][1]["plan_status"] == "delivery_failed"

        # Communication logged as failed
        comm_args = deliver_client["mock_comm"].call_args
        assert comm_args[1]["status"] == "failed"


# ---------------------------------------------------------------------------
# No RESEND_API_KEY
# ---------------------------------------------------------------------------

class TestDeliverNoApiKey:
    def test_no_api_key_graceful_degradation(self, deliver_client):
        """Without RESEND_API_KEY, URLs are generated but email is skipped."""
        c = deliver_client["client"]

        with patch("mission_control.services.file_storage.get_signed_url", return_value="https://signed.url/file"):
            with patch("mission_control.config.RESEND_API_KEY", ""):
                resp = c.post("/athletes/test-athlete/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 200
        assert "RESEND_API_KEY" in resp.text

        # Status = delivered_no_email (not delivered)
        call_args = deliver_client["mock_update"].call_args
        assert call_args[0][1]["plan_status"] == "delivered_no_email"


# ---------------------------------------------------------------------------
# No email address
# ---------------------------------------------------------------------------

class TestDeliverNoEmail:
    def test_no_email_returns_400(self):
        """Athlete with no email address gets a clear error."""
        athlete = make_athlete(slug="no-email", email="", plan_status="pipeline_complete")

        with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
            with patch("mission_control.supabase_client.get_athlete", return_value=athlete):
                client = _make_client()
                with client:
                    resp = client.post("/athletes/no-email/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 400
        assert "no email" in resp.text.lower()

    def test_none_email_returns_400(self):
        """Athlete with None email gets a clear error."""
        athlete = make_athlete(slug="null-email", email=None, plan_status="pipeline_complete")

        with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
            with patch("mission_control.supabase_client.get_athlete", return_value=athlete):
                client = _make_client()
                with client:
                    resp = client.post("/athletes/null-email/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Plan not in deliverable state
# ---------------------------------------------------------------------------

class TestDeliverWrongStatus:
    @pytest.mark.parametrize("status", [
        "intake_received", "pipeline_running", "draft", "cancelled",
    ])
    def test_non_deliverable_status_returns_409(self, status):
        """Plans that haven't completed pipeline cannot be delivered."""
        athlete = make_athlete(slug="wrong-status", email="ws@test.com", plan_status=status)

        with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
            with patch("mission_control.supabase_client.get_athlete", return_value=athlete):
                client = _make_client()
                with client:
                    resp = client.post("/athletes/wrong-status/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 409
        assert "Cannot deliver" in resp.text

    @pytest.mark.parametrize("status", [
        "pipeline_complete", "approved", "delivered",
    ])
    def test_deliverable_statuses_allowed(self, status):
        """Pipeline complete, approved, and delivered states allow delivery."""
        athlete = make_athlete(slug="ok-status", email="ok@test.com", plan_status=status)
        files = [
            {"file_type": "guide_pdf", "storage_path": "ok-status/guide.pdf", "file_name": "guide.pdf"},
        ]

        with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
            with patch("mission_control.supabase_client.get_athlete", return_value=athlete):
                with patch("mission_control.supabase_client.get_files", return_value=files):
                    with patch("mission_control.supabase_client.update_athlete"):
                        with patch("mission_control.supabase_client.log_action"):
                            with patch("mission_control.supabase_client.log_communication"):
                                with patch("mission_control.services.file_storage.get_signed_url", return_value="https://url"):
                                    with patch("mission_control.config.RESEND_API_KEY", ""):
                                        client = _make_client()
                                        with client:
                                            resp = client.post("/athletes/ok-status/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Athlete not found
# ---------------------------------------------------------------------------

class TestDeliverAthleteNotFound:
    def test_missing_athlete_returns_404(self):
        with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
            with patch("mission_control.supabase_client.get_athlete", return_value=None):
                client = _make_client()
                with client:
                    resp = client.post("/athletes/ghost/deliver", data={"dry_run": "false"}, headers=ADMIN_HEADERS)

        assert resp.status_code == 404
        assert "not found" in resp.text.lower()
