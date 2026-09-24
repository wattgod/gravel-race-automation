"""Read-only prefill for /season-plan/ from a /goals/ lead's saved answers.

The /goals/ page's Season Plan CTA links to /season-plan/?t=<poster_token> —
the same unguessable token webhooks.subscriber_webhook mints for the goal
poster image (see routers/poster.py). This route hands back ONLY the
fields /season-plan/ prefills: name, email, the stated goal, the A-race
name/date, and daily habits. No auth beyond the token itself (unguessable,
24 url-safe bytes — same trust model as the poster route), rate-limited,
and never cached by an intermediary (the answers can change).
"""
from __future__ import annotations

import re
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from mission_control import supabase_client as db

router = APIRouter()

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}\Z")

# The browser calls this route cross-origin, from gravelgodcycling.com /
# roadielabs.com — Mission Control has no CORS middleware anywhere (a sol
# review confirmed every other public route here, races_api/nutrition_api/
# poster, is either called server-side or embedded as an <img src>, neither
# of which needs it). Without an explicit Access-Control-Allow-Origin on
# THIS response, the browser fetch in web/season-plan-form.js would get a
# response the page is never allowed to read. Scoped to this route only,
# not a blanket CORSMiddleware — same allowlist the lead-intake worker uses.
_ALLOWED_ORIGINS = {
    "https://gravelgodcycling.com", "https://www.gravelgodcycling.com",
    "https://roadielabs.com", "https://www.roadielabs.com",
}


def _base_headers(request: Request) -> dict:
    # sol NIT: the answers can change, and a 404 today (an athlete redoing
    # /goals/, a not-yet-processed submission) can become a 200 minutes
    # later — no-store belongs on every response, not just the success path.
    headers = {"Cache-Control": "no-store"}
    origin = request.headers.get("origin", "")
    if origin in _ALLOWED_ORIGINS:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Vary"] = "Origin"
    return headers

# ---------------------------------------------------------------------------
# Rate limiting (same in-memory pattern as nutrition_api.py / races_api.py)
# ---------------------------------------------------------------------------
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 30
_RATE_WINDOW = 60
_MAX_TRACKED_IPS = 10_000
_last_cleanup = 0.0


def _check_rate_limit(request: Request) -> None:
    global _last_cleanup
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    if now - _last_cleanup > _RATE_WINDOW * 2:
        _last_cleanup = now
        cutoff = now - _RATE_WINDOW
        stale = [k for k, v in _rate_buckets.items() if not v or v[-1] < cutoff]
        for k in stale:
            del _rate_buckets[k]
    if ip not in _rate_buckets and len(_rate_buckets) >= _MAX_TRACKED_IPS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket = _rate_buckets[ip]
    cutoff = now - _RATE_WINDOW
    _rate_buckets[ip] = bucket = [t for t in bucket if t > cutoff]
    if len(bucket) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


@router.get("/api/season-plan/prefill/{token}")
def season_plan_prefill(token: str, request: Request) -> JSONResponse:
    cors = _base_headers(request)
    _check_rate_limit(request)

    if not _TOKEN_RE.match(token):
        raise HTTPException(status_code=404, detail="Not found", headers=cors)

    try:
        rows = (
            db._table("gg_sequence_enrollments")
            .select("contact_name,contact_email,source,source_data")
            .eq("source_data->>poster_token", token)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001 - never leak a lookup failure as a 500
        raise HTTPException(status_code=404, detail="Not found", headers=cors) from None
    if not rows:
        raise HTTPException(status_code=404, detail="Not found", headers=cors)
    match = rows[0]

    # sol review: a poster_token is minted for BOTH goal_2027 and
    # athlete_review (webhooks.py). athlete_review is a coached athlete's
    # private season-close-out — its token must never unlock a *different*
    # record type here. Only a goal_2027 lead's token prefills this form.
    if match.get("source") != "goal_2027":
        raise HTTPException(status_code=404, detail="Not found", headers=cors)

    source_data = match.get("source_data") or {}
    answers = source_data.get("goal_answers") or {}

    # ONLY the fields /season-plan/ prefills, using the /goals/
    # questionnaire's own field names (season_review_variants.py: "a_race",
    # "a_race_date", "outcome_goal", "habit"/"habit_when"). Nothing else in
    # source_data (offer_variant, entry_src, GA4 ids, the rest of
    # goal_answers) is returned — this route exists to fill a form, not to
    # dump a lead record to whoever holds the link.
    habit_bits = [str(answers.get("habit", "")).strip(), str(answers.get("habit_when", "")).strip()]
    body = {
        "name": (match.get("contact_name") or "")[:120],
        "email": (match.get("contact_email") or "")[:254],
        "goal": str(answers.get("outcome_goal", ""))[:600],
        "a_race_name": str(answers.get("a_race", ""))[:200],
        "a_race_date": str(answers.get("a_race_date", ""))[:20],
        "habits": ", ".join(b for b in habit_bits if b)[:600],
    }

    return JSONResponse(content=body, headers=cors)
