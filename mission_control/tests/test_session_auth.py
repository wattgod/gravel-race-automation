"""Tests for cookie-based session authentication.

Verifies:
- Login page renders at /login without auth
- POST /login with correct secret sets session cookie and redirects
- POST /login with wrong secret returns 401 with error
- POST /login with no secret configured returns 503
- Session cookie grants access to protected routes (no Bearer header needed)
- Expired session cookies are rejected
- Invalid/tampered session cookies are rejected
- Logout clears the cookie and redirects to /login
- Bearer token auth still works alongside cookies
"""

import os
import sys
import time
import types
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Env vars before MC imports
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret-123")
os.environ.setdefault("RESEND_API_KEY", "")
os.environ.setdefault("MISSION_CONTROL_SECRET", "test-secret-for-tests")

# Pre-mock supabase
if "supabase" not in sys.modules or not hasattr(sys.modules["supabase"], "Client"):
    _fake_supabase = types.ModuleType("supabase")
    _fake_supabase.Client = MagicMock
    _fake_supabase.create_client = MagicMock()
    sys.modules["supabase"] = _fake_supabase

import mission_control.supabase_client  # noqa: E402

ADMIN_SECRET = "test-secret-for-tests"


@contextmanager
def _make_client(env_overrides: dict | None = None):
    """Build a fresh TestClient with optional env var overrides."""
    env = {
        "SUPABASE_URL": "https://fake.supabase.co",
        "SUPABASE_SERVICE_KEY": "fake-key",
        "WEBHOOK_SECRET": "test-secret-123",
        "RESEND_API_KEY": "",
        "MISSION_CONTROL_SECRET": ADMIN_SECRET,
    }
    if env_overrides:
        env.update(env_overrides)

    with patch.dict(os.environ, env, clear=False):
        import importlib
        import mission_control.config
        importlib.reload(mission_control.config)
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

            with TestClient(app, follow_redirects=False, raise_server_exceptions=False) as c:
                yield c


# ---------------------------------------------------------------------------
# Login page
# ---------------------------------------------------------------------------

class TestLoginPage:
    def test_login_page_renders_without_auth(self):
        with _make_client() as client:
            resp = client.get("/login")
            assert resp.status_code == 200
            assert "Admin Secret" in resp.text

    def test_login_correct_secret_sets_cookie_and_redirects(self):
        with _make_client() as client:
            resp = client.post("/login", data={"secret": ADMIN_SECRET})
            assert resp.status_code == 303
            assert resp.headers.get("location") == "/"
            # Cookie should be set
            assert "mc_session" in resp.cookies

    def test_login_wrong_secret_returns_401(self):
        with _make_client() as client:
            resp = client.post("/login", data={"secret": "wrong"})
            assert resp.status_code == 401
            assert "Invalid credentials" in resp.text

    def test_login_no_secret_configured_returns_503(self):
        with _make_client({"MISSION_CONTROL_SECRET": ""}) as client:
            resp = client.post("/login", data={"secret": "anything"})
            assert resp.status_code == 503
            assert "misconfigured" in resp.text.lower()


# ---------------------------------------------------------------------------
# Cookie-based access to protected routes
# ---------------------------------------------------------------------------

class TestCookieAuth:
    def test_session_cookie_grants_access(self):
        """After login, the session cookie should grant access to dashboard."""
        with _make_client() as client:
            # Login first
            login_resp = client.post("/login", data={"secret": ADMIN_SECRET})
            session_cookie = login_resp.cookies.get("mc_session")
            assert session_cookie

            # Access protected route with cookie (no Bearer header)
            client.cookies.set("mc_session", session_cookie)
            # Use follow_redirects since TestClient was created with follow_redirects=False
            resp = client.get("/athletes/")
            # Should pass auth — may return 200 or 500 (no DB) but NOT 401
            assert resp.status_code != 401, (
                f"Cookie auth should pass, got {resp.status_code}: {resp.text[:200]}"
            )

    def test_invalid_cookie_rejected(self):
        with _make_client() as client:
            client.cookies.set("mc_session", "garbage.invalid")
            resp = client.get("/athletes/")
            assert resp.status_code == 401

    def test_tampered_cookie_rejected(self):
        with _make_client() as client:
            # Valid timestamp but wrong signature
            ts = str(int(time.time()))
            client.cookies.set("mc_session", f"{ts}.aaaaaabbbbbbcccccc")
            resp = client.get("/athletes/")
            assert resp.status_code == 401

    def test_expired_cookie_rejected(self):
        """Cookie older than 24h should be rejected."""
        from mission_control.middleware.auth import _sign, SESSION_MAX_AGE

        with _make_client() as client:
            # Create a token from 25 hours ago
            old_ts = str(int(time.time()) - SESSION_MAX_AGE - 3600)
            sig = _sign(old_ts, ADMIN_SECRET)
            client.cookies.set("mc_session", f"{old_ts}.{sig}")
            resp = client.get("/athletes/")
            assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_redirects_to_login(self):
        with _make_client() as client:
            resp = client.get("/logout")
            assert resp.status_code == 303
            assert resp.headers.get("location") == "/login"

    def test_logout_clears_cookie(self):
        with _make_client() as client:
            # Login first
            login_resp = client.post("/login", data={"secret": ADMIN_SECRET})
            assert "mc_session" in login_resp.cookies

            # Logout
            resp = client.get("/logout")
            # The cookie should be deleted (max-age=0 or set to empty)
            cookie_header = resp.headers.get("set-cookie", "")
            assert "mc_session" in cookie_header


# ---------------------------------------------------------------------------
# Bearer still works
# ---------------------------------------------------------------------------

class TestBearerStillWorks:
    def test_bearer_token_passes_auth(self):
        with _make_client() as client:
            resp = client.get(
                "/athletes/",
                headers={"Authorization": f"Bearer {ADMIN_SECRET}"},
            )
            assert resp.status_code != 401


# ---------------------------------------------------------------------------
# Hardening: constant-time compares, secure cookie, failed-login limit,
# signed-out browser redirect
# ---------------------------------------------------------------------------

class TestLoginHardening:
    def test_non_ascii_password_is_rejected_not_crashing(self):
        with _make_client() as client:
            resp = client.post("/login", data={"secret": "pässwörd-ü"})
            assert resp.status_code == 401

    def test_non_ascii_bearer_is_rejected_not_crashing(self):
        with _make_client() as client:
            resp = client.get(
                "/sequences/",
                headers={"Authorization": "Bearer p\xe4ss".encode("latin-1")},
            )
            assert resp.status_code == 401

    def test_cookie_secure_on_railway(self, monkeypatch):
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        with _make_client() as client:
            resp = client.post("/login", data={"secret": ADMIN_SECRET})
            assert resp.status_code == 303
            assert "secure" in resp.headers["set-cookie"].lower()

    def test_cookie_secure_with_railway_public_domain(self, monkeypatch):
        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        monkeypatch.setenv("RAILWAY_PUBLIC_DOMAIN", "example.up.railway.app")
        with _make_client() as client:
            resp = client.post("/login", data={"secret": ADMIN_SECRET})
            assert "secure" in resp.headers["set-cookie"].lower()

    def test_cookie_not_secure_locally(self, monkeypatch):
        monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
        monkeypatch.delenv("RAILWAY_PUBLIC_DOMAIN", raising=False)
        with _make_client() as client:
            resp = client.post("/login", data={"secret": ADMIN_SECRET})
            assert "secure" not in resp.headers["set-cookie"].lower()

    def test_ten_failures_lock_the_form(self):
        with _make_client() as client:
            for _ in range(10):
                assert client.post("/login", data={"secret": "wrong"}).status_code == 401
            # Locked: even the right password answers 429 until the window clears.
            assert client.post("/login", data={"secret": "wrong"}).status_code == 429
            assert client.post("/login", data={"secret": ADMIN_SECRET}).status_code == 429

    def test_successful_logins_are_not_counted(self):
        with _make_client() as client:
            for _ in range(9):
                client.post("/login", data={"secret": "wrong"})
            for _ in range(5):
                assert client.post("/login", data={"secret": ADMIN_SECRET}).status_code == 303
            assert client.post("/login", data={"secret": "wrong"}).status_code == 401
            assert client.post("/login", data={"secret": "wrong"}).status_code == 429

    def test_lock_clears_after_the_window(self, monkeypatch):
        import mission_control.routers.auth_routes as ar

        clock = [1000.0]
        monkeypatch.setattr(ar.time, "monotonic", lambda: clock[0])
        with _make_client() as client:
            for _ in range(10):
                client.post("/login", data={"secret": "wrong"})
            assert client.post("/login", data={"secret": ADMIN_SECRET}).status_code == 429
            clock[0] += 10 * 60 + 1
            assert client.post("/login", data={"secret": ADMIN_SECRET}).status_code == 303


class TestSignedOutBrowserRedirect:
    HTML = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}

    def test_browser_get_redirects_to_login(self):
        with _make_client() as client:
            resp = client.get("/sequences/", headers=self.HTML)
            assert resp.status_code == 303
            assert resp.headers["location"] == "/login"

    def test_htmx_request_gets_401_with_hx_redirect(self):
        with _make_client() as client:
            resp = client.get("/sequences/", headers={**self.HTML, "HX-Request": "true"})
            assert resp.status_code == 401
            assert resp.headers["hx-redirect"] == "/login"

    def test_non_html_get_keeps_json_401(self):
        with _make_client() as client:
            resp = client.get("/sequences/", headers={"Accept": "application/json"})
            assert resp.status_code == 401
            assert resp.json()["detail"]

    def test_post_keeps_json_401(self):
        with _make_client() as client:
            resp = client.post("/sequences/process-now", headers=self.HTML)
            assert resp.status_code == 401

    def test_bearer_caller_keeps_json_401(self):
        with _make_client() as client:
            resp = client.get(
                "/sequences/",
                headers={**self.HTML, "Authorization": "Bearer wrong"},
            )
            assert resp.status_code == 401

    def test_webhooks_keep_json_401(self):
        with _make_client() as client:
            resp = client.get("/webhooks/gmail-sync/candidates", headers=self.HTML)
            assert resp.status_code == 401

    def test_public_routes_unchanged(self):
        with _make_client() as client:
            assert client.get("/login", headers=self.HTML).status_code == 200
            assert client.get("/unsubscribe", headers=self.HTML).status_code == 200
