"""Serve a lead's 2027 goal poster from their enrollment token.

The token is unguessable and stored with the answers it renders (see
webhooks.subscriber_webhook), so this route needs no auth and no signing key.
Rendered on each request; nothing is written to disk.
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from mission_control import supabase_client as db
from mission_control.services.goal_poster import render_poster

router = APIRouter()
logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


@router.get("/poster/{token}.png")
def goal_poster(token: str) -> Response:
    if not _TOKEN_RE.match(token):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        rows = (
            db._table("gg_sequence_enrollments")
            .select("contact_name,source_data")
            .eq("source_data->>poster_token", token)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception:  # noqa: BLE001 - a poster is never worth a 500
        logger.exception("poster lookup failed")
        raise HTTPException(status_code=404, detail="Not found") from None
    if not rows:
        raise HTTPException(status_code=404, detail="Not found")
    match = rows[0]

    source_data = match.get("source_data") or {}
    try:
        png = render_poster(
            source_data.get("goal_answers") or {},
            name=match.get("contact_name") or "",
        )
    except Exception:  # noqa: BLE001 - a broken poster is a 404, never a 500
        logger.exception("poster render failed")
        raise HTTPException(status_code=404, detail="Not found") from None
    return Response(
        content=png,
        media_type="image/png",
        headers={
            # The answers can change (the athlete can redo the questionnaire),
            # so let a mail client cache it for a day, not forever.
            "Cache-Control": "public, max-age=86400",
            "Content-Disposition": 'inline; filename="2027-goal-poster.png"',
        },
    )
