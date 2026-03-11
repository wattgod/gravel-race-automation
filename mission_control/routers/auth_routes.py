"""Login / logout routes for browser-based Mission Control access.

GET  /login  — render login form
POST /login  — validate secret, set session cookie, redirect to /
GET  /logout — clear cookie, redirect to /login
"""

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


@router.get("/login")
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
    })


@router.post("/login")
async def login_submit(request: Request, secret: str = Form("")):
    expected = _get_secret()

    if not expected:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Server misconfigured — admin access is disabled.",
        }, status_code=503)

    if secret != expected:
        return templates.TemplateResponse("login.html", {
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
        secure=False,  # Set True in production behind HTTPS
    )
    return response


@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=COOKIE_NAME)
    return response
