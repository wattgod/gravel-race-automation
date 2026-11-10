"""Admin authentication middleware — Bearer token OR signed session cookie.

Fail-closed: if MISSION_CONTROL_SECRET is not set, ALL protected requests
are denied with 401. This prevents accidental exposure on misconfigured deploys.

Browser flow:
  1. GET /login  — renders login form
  2. POST /login — validates secret, sets signed ``mc_session`` cookie
  3. All dashboard requests carry the cookie automatically
  4. GET /logout  — clears cookie, redirects to /login

API/CLI flow:
  Authorization: Bearer <MISSION_CONTROL_SECRET>
"""

import hashlib
import hmac
import os
import time

from fastapi import Cookie, Header, HTTPException, Request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

#: Session cookies are valid for 24 hours
SESSION_MAX_AGE = 24 * 60 * 60

COOKIE_NAME = "mc_session"


def _get_secret() -> str:
    """Read the secret at call time so tests can patch env vars."""
    return os.environ.get("MISSION_CONTROL_SECRET", "")


def _sign(payload: str, secret: str) -> str:
    """Create an HMAC-SHA256 signature for *payload*."""
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_session_token(secret: str) -> str:
    """Build a signed session token: ``<timestamp>.<signature>``."""
    ts = str(int(time.time()))
    sig = _sign(ts, secret)
    return f"{ts}.{sig}"


def verify_session_token(token: str, secret: str) -> bool:
    """Return True if *token* is validly signed and not expired."""
    try:
        ts_str, sig = token.split(".", 1)
        ts = int(ts_str)
    except (ValueError, AttributeError):
        return False

    # Check expiry
    if time.time() - ts > SESSION_MAX_AGE:
        return False

    # Constant-time comparison
    expected = _sign(ts_str, secret)
    return hmac.compare_digest(sig, expected)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def require_admin(
    request: Request,
    authorization: str = Header(""),
) -> None:
    """FastAPI dependency — accepts Bearer header OR signed session cookie.

    Raises 401 if:
    - ``MISSION_CONTROL_SECRET`` is not set (fail closed)
    - Neither a valid Bearer header nor a valid session cookie is present
    """
    secret = _get_secret()

    if not secret:
        raise HTTPException(
            status_code=401,
            detail="MISSION_CONTROL_SECRET is not configured — all admin access denied",
        )

    # Path 1: Bearer token (API / CLI callers). Bytes compare: constant time,
    # and a non-ASCII header cannot raise.
    expected = f"Bearer {secret}"
    if hmac.compare_digest((authorization or "").encode(), expected.encode()):
        return

    # Path 2: Signed session cookie (browser callers)
    cookie_value = request.cookies.get(COOKIE_NAME, "")
    if cookie_value and verify_session_token(cookie_value, secret):
        return

    _raise_unauthenticated(request, "Invalid or missing admin credentials")


def _raise_unauthenticated(request: Request, detail: str) -> None:
    """Send a signed-out browser to /login; everyone else gets a JSON 401.

    - htmx fragment requests (``HX-Request``) get 401 + ``HX-Redirect: /login``
      so htmx swaps the whole page to the login form.
    - A plain browser ``GET`` that accepts HTML gets a 303 to ``/login``.
    - Bearer/API callers, non-GETs, and ``/api/*`` or ``/webhooks/*`` paths keep
      the JSON 401.
    """
    path = request.url.path
    if not (path.startswith("/api/") or path.startswith("/webhooks/")):
        if request.headers.get("hx-request"):
            raise HTTPException(
                status_code=401, detail=detail, headers={"HX-Redirect": "/login"},
            )
        if (
            request.method == "GET"
            and "text/html" in request.headers.get("accept", "")
            and not request.headers.get("authorization")
        ):
            raise HTTPException(
                status_code=303, detail=detail, headers={"Location": "/login"},
            )
    raise HTTPException(status_code=401, detail=detail)
