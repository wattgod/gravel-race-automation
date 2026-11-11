"""Login / logout routes for browser-based Mission Control access.

GET  /login  — render login form
POST /login  — validate secret, set session cookie, redirect to /
GET  /logout — clear cookie, redirect to /login
"""

import hmac
import os
import threading
import time
from collections import deque

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from mission_control.config import WEB_TEMPLATES_DIR
from mission_control.middleware.auth import (
    COOKIE_NAME,
    SESSION_MAX_AGE,
    _get_secret,
    create_session_token,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(WEB_TEMPLATES_DIR))

# Failed-login limit. Global, not per address: behind Railway's proxy every
# request carries the proxy's address. After this many failures inside the
# window, POST /login answers 429 until the oldest failure ages out. Anyone
# can therefore lock the form for up to 10 minutes; Bearer access still works.
_MAX_FAILED_LOGINS = 10
_FAILED_LOGIN_WINDOW_S = 10 * 60
_failed_logins: deque[float] = deque()
_failed_logins_lock = threading.Lock()


def _login_locked(now: float) -> bool:
    with _failed_logins_lock:
        while _failed_logins and now - _failed_logins[0] >= _FAILED_LOGIN_WINDOW_S:
            _failed_logins.popleft()
        return len(_failed_logins) >= _MAX_FAILED_LOGINS


def _record_failed_login(now: float) -> None:
    with _failed_logins_lock:
        _failed_logins.append(now)


def _cookie_secure() -> bool:
    """HTTPS-only cookie on Railway; plain cookie for local dev over http."""
    return bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PUBLIC_DOMAIN"))


@router.get("/login")
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(request, "login.html", {
        "request": request,
        "error": error,
    })


@router.post("/login")
async def login_submit(request: Request, secret: str = Form("")):
    expected = _get_secret()

    if not expected:
        return templates.TemplateResponse(request, "login.html", {
            "request": request,
            "error": "Server misconfigured — admin access is disabled.",
        }, status_code=503)

    now = time.monotonic()
    if _login_locked(now):
        return templates.TemplateResponse(request, "login.html", {
            "request": request,
            "error": "Too many failed attempts. Try again in a few minutes.",
        }, status_code=429)

    # Bytes compare: constant time, and non-ASCII input cannot raise.
    if not hmac.compare_digest(secret.encode(), expected.encode()):
        _record_failed_login(now)
        return templates.TemplateResponse(request, "login.html", {
            "request": request,
            "error": "Invalid credentials.",
        }, status_code=401)

    # Success — set signed cookie and redirect to dashboard
    token = create_session_token(expected)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=COOKIE_NAME)
    return response
