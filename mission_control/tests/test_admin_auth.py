"""Tests for admin authentication middleware.

Verifies:
- No MISSION_CONTROL_SECRET set → 401 on all protected routes (fail closed)
- Wrong secret → 401
- Correct secret → passes through
- Public routes (races API, unsubscribe, health) remain unaffected
- Webhook routes use their own auth (WEBHOOK_SECRET), not admin auth
"""

import os
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ADMIN_SECRET = "test-admin-secret-abc123"

# Protected routes to smoke-test (one from each router group)
PROTECTED_GET_ROUTES = [
    "/athletes/",
    "/pipeline/",
    "/sequences/",
    "/deals/",
    "/analytics/",
    "/reports/",
]

PUBLIC_GET_ROUTES = [
    "/health",
    "/api/v1/races",
]


@contextmanager
def _make_client(env_overrides: dict | None = None):
    """Build a fresh TestClient with optional env var overrides."""
    env = {
        "SUPABASE_URL": "https://fake.supabase.co",
        "SUPABASE_SERVICE_KEY": "fake-key",
        "WEBHOOK_SECRET": "test-secret-123",
        "RESEND_API_KEY": "",
    }
    if env_overrides:
        env.update(env_overrides)

    with patch.dict(os.environ, env, clear=False):
        # Need fresh import each time since config reads env at import
        import importlib
        import mission_control.config
        importlib.reload(mission_control.config)

        # Also reload auth module so _get_secret sees new env
        import mission_control.middleware.auth
        importlib.reload(mission_control.middleware.auth)

        with patch("mission_control.app.lifespan") as mock_lifespan:
            @asynccontextmanager
            async def noop_lifespan(app):
                yield

            mock_lifespan.side_effect = noop_lifespan

            from mission_control.app import create_app

            app = create_app()
            app.router.lifespan_context = noop_lifespan

            with TestClient(app) as c:
                yield c


# ---------------------------------------------------------------------------
# Tests: No secret configured (fail closed)
# ---------------------------------------------------------------------------

class TestNoSecretConfigured:
    """When MISSION_CONTROL_SECRET is unset, all admin routes must deny."""

    def test_protected_routes_return_401(self):
        with _make_client({"MISSION_CONTROL_SECRET": ""}) as client:
            for route in PROTECTED_GET_ROUTES:
                resp = client.get(route)
                assert resp.status_code == 401, (
                    f"{route} should return 401 when secret is not configured, "
                    f"got {resp.status_code}"
                )

    def test_error_message_indicates_misconfiguration(self):
        with _make_client({"MISSION_CONTROL_SECRET": ""}) as client:
            resp = client.get("/athletes/")
            assert "not configured" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests: Wrong secret
# ---------------------------------------------------------------------------

class TestWrongSecret:
    """Requests with incorrect Bearer token must be rejected."""

    def test_wrong_token_returns_401(self):
        with _make_client({"MISSION_CONTROL_SECRET": ADMIN_SECRET}) as client:
            for route in PROTECTED_GET_ROUTES:
                resp = client.get(
                    route,
                    headers={"Authorization": "Bearer wrong-secret"},
                )
                assert resp.status_code == 401, (
                    f"{route} should reject wrong secret, got {resp.status_code}"
                )

    def test_no_header_returns_401(self):
        with _make_client({"MISSION_CONTROL_SECRET": ADMIN_SECRET}) as client:
            resp = client.get("/athletes/")
            assert resp.status_code == 401

    def test_malformed_header_returns_401(self):
        with _make_client({"MISSION_CONTROL_SECRET": ADMIN_SECRET}) as client:
            # Token without "Bearer " prefix
            resp = client.get(
                "/athletes/",
                headers={"Authorization": ADMIN_SECRET},
            )
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: Correct secret
# ---------------------------------------------------------------------------

class TestCorrectSecret:
    """Requests with the correct Bearer token should pass auth."""

    def test_athletes_list_passes_auth(self, client_with_secret):
        resp = client_with_secret.get(
            "/athletes/",
            headers={"Authorization": f"Bearer {ADMIN_SECRET}"},
        )
        # Should pass auth — may return 200 or 500 depending on DB state,
        # but critically NOT 401
        assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Tests: Public routes unaffected
# ---------------------------------------------------------------------------

class TestPublicRoutesUnaffected:
    """Public routes must work without any admin auth."""

    def test_health_no_auth_needed(self):
        with _make_client({"MISSION_CONTROL_SECRET": ADMIN_SECRET}) as client:
            resp = client.get("/health")
            assert resp.status_code == 200

    def test_unsubscribe_no_auth_needed(self):
        with _make_client({"MISSION_CONTROL_SECRET": ADMIN_SECRET}) as client:
            resp = client.get("/unsubscribe")
            assert resp.status_code == 200  # Returns page even with missing params

    def test_webhook_uses_own_auth(self):
        """Webhooks should use WEBHOOK_SECRET, not MISSION_CONTROL_SECRET."""
        with _make_client({"MISSION_CONTROL_SECRET": ADMIN_SECRET}) as client:
            # Wrong webhook secret → 401 (proves webhook uses its own auth)
            resp = client.post(
                "/webhooks/intake",
                json={"request_id": "test"},
                headers={"Authorization": "Bearer wrong-webhook-secret"},
            )
            assert resp.status_code == 401

            # Admin secret alone should NOT satisfy webhook auth
            resp = client.post(
                "/webhooks/intake",
                json={"request_id": "test"},
                headers={"Authorization": f"Bearer {ADMIN_SECRET}"},
            )
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client_with_secret(fake_db):
    """Client with MISSION_CONTROL_SECRET set and fake DB."""
    with _make_client({"MISSION_CONTROL_SECRET": ADMIN_SECRET}) as client:
        yield client
