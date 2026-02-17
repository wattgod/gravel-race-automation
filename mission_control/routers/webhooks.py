"""Webhooks — receives intake from Cloudflare Worker + automation triggers."""

import logging
import re
import time
from collections import defaultdict

from fastapi import APIRouter, Header, HTTPException, Request

from mission_control.config import WEBHOOK_SECRET
from mission_control import supabase_client as db
from mission_control.sequences import get_sequences_for_trigger
from mission_control.services.sequence_engine import enroll, record_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks")

# Basic email validation — intentionally permissive
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}$")
_MAX_NAME_LEN = 200
_MAX_SOURCE_LEN = 100

# In-memory rate limiter: {ip: [timestamp, ...]}
_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 30       # max requests per window
_RATE_WINDOW = 60      # window in seconds


def _check_rate_limit(request: Request) -> None:
    """Raise 429 if IP exceeds rate limit. Simple sliding window."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    # Prune old entries
    cutoff = now - _RATE_WINDOW
    _rate_buckets[ip] = bucket = [t for t in bucket if t > cutoff]
    if len(bucket) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


def _validate_email(email: str) -> str:
    """Validate and normalize email. Raises HTTPException on invalid."""
    email = email.strip().lower()
    if not email or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    return email


def _truncate(value: str, max_len: int) -> str:
    """Truncate string to max length."""
    return value[:max_len] if value else ""


@router.post("/intake")
async def intake_webhook(
    request: Request,
    authorization: str = Header(""),
):
    _check_rate_limit(request)
    # Verify webhook secret
    if WEBHOOK_SECRET:
        expected = f"Bearer {WEBHOOK_SECRET}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    request_id = body.get("request_id", "")

    if not request_id:
        raise HTTPException(status_code=400, detail="request_id required")

    # Look up the plan request
    plan_request = db.get_plan_request(request_id)
    if not plan_request:
        raise HTTPException(status_code=404, detail=f"Plan request {request_id} not found")

    payload = plan_request.get("payload", {})

    # Extract and validate athlete info from payload
    name = _truncate(payload.get("name", "Unknown"), _MAX_NAME_LEN)
    email = payload.get("email", "").strip().lower()

    # Generate slug
    from datetime import date
    slug_base = re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-"))
    slug = f"{slug_base}-{date.today().strftime('%Y%m%d')}"

    # Check if athlete already exists
    existing = db.get_athlete(slug)
    if existing:
        return {"status": "already_exists", "slug": slug}

    # Create athlete record
    races = payload.get("races", [])
    race_name = races[0].get("name") if races else None
    race_date = races[0].get("date") if races else None

    db.upsert_athlete({
        "slug": slug,
        "plan_request_id": request_id,
        "name": name,
        "email": email,
        "race_name": race_name,
        "race_date": race_date,
        "ftp": payload.get("ftp"),
        "weekly_hours": str(payload.get("weekly_hours", "")),
        "plan_status": "intake_received",
        "intake_json": payload,
    })

    db.log_action("intake_received", "athlete", slug,
                  f"New intake from webhook: {name} ({email})")

    return {"status": "created", "slug": slug}


@router.post("/subscriber")
async def subscriber_webhook(
    request: Request,
    authorization: str = Header(""),
):
    """Receive new subscriber from Cloudflare Worker.

    Payload: { email, name?, source, race_slug?, race_name? }
    Enrolls in appropriate sequences based on source.
    """
    _check_rate_limit(request)
    if WEBHOOK_SECRET:
        expected = f"Bearer {WEBHOOK_SECRET}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    email = _validate_email(body.get("email", ""))
    name = _truncate(body.get("name", "").strip(), _MAX_NAME_LEN)
    source = _truncate(body.get("source", "unknown"), _MAX_SOURCE_LEN)

    source_data = {}
    if body.get("race_slug"):
        source_data["race_slug"] = body["race_slug"]
    if body.get("race_name"):
        source_data["race_name"] = body["race_name"]

    # Map capture source to sequence trigger
    trigger_map = {
        "exit_intent": "new_subscriber",
        "race_profile": "new_subscriber",
        "prep_kit_gate": "prep_kit_download",
        "race_quiz": "quiz_completed",
        "quiz_shared": "quiz_completed",
        "fueling_calculator": "new_subscriber",
    }
    trigger = trigger_map.get(source, "new_subscriber")

    # Enroll in matching sequences
    enrolled = []
    for seq in get_sequences_for_trigger(trigger):
        result = enroll(email, name, seq["id"], source=source, source_data=source_data)
        if result:
            enrolled.append(seq["id"])

    # Also enroll in welcome if trigger wasn't new_subscriber
    if trigger != "new_subscriber":
        for seq in get_sequences_for_trigger("new_subscriber"):
            result = enroll(email, name, seq["id"], source=source, source_data=source_data)
            if result:
                enrolled.append(seq["id"])

    db.log_action(
        "subscriber_received", "webhook", email,
        f"Source: {source}, enrolled in: {', '.join(enrolled) or 'none (already enrolled)'}",
    )

    return {"status": "ok", "enrolled": enrolled}


@router.post("/resend")
async def resend_webhook(
    request: Request,
    authorization: str = Header(""),
):
    """Receive Resend email event webhooks (opens, clicks, bounces)."""
    _check_rate_limit(request)
    if WEBHOOK_SECRET:
        expected = f"Bearer {WEBHOOK_SECRET}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()

    event_type = body.get("type", "")
    data = body.get("data", {})

    # Resend sends email_id in data
    resend_id = data.get("email_id", "")
    if not resend_id:
        return {"status": "ignored", "reason": "no email_id"}

    if event_type in ("email.opened", "email.clicked", "email.bounced"):
        success = record_event(resend_id, event_type)
        return {"status": "recorded" if success else "not_found"}

    return {"status": "ignored", "reason": f"unhandled event: {event_type}"}


@router.post("/resend-inbound")
async def resend_inbound_webhook(
    request: Request,
    authorization: str = Header(""),
):
    """Receive inbound email replies via Resend."""
    _check_rate_limit(request)
    if WEBHOOK_SECRET:
        expected = f"Bearer {WEBHOOK_SECRET}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    data = body.get("data", {})

    from_email = data.get("from", "")
    subject = data.get("subject", "")
    text_body = data.get("text", "")

    if not from_email:
        return {"status": "ignored"}

    # Try to match to an athlete by email
    athletes = db.select("gg_athletes", match={"email": from_email}, limit=1)
    if athletes:
        athlete = athletes[0]
        db.log_communication(
            athlete_id=athlete["id"],
            comm_type="inbound",
            subject=subject,
            recipient=from_email,
            status="received",
        )
        db.log_action(
            "inbound_email", "athlete", athlete["slug"],
            f"Reply from {from_email}: {subject}",
        )
        return {"status": "recorded", "athlete_slug": athlete["slug"]}

    # Log even if no matching athlete
    db.log_action("inbound_email", "contact", from_email, f"Reply (no athlete match): {subject}")
    return {"status": "recorded", "athlete_slug": None}
