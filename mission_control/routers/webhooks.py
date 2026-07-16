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


async def _send_enrollment_alert(
    email: str, name: str, brand: str, source: str,
    source_data: dict, enrolled: list[str],
) -> None:
    """Email the coach when someone new enrolls, with everything needed to
    open the conversation: who, from where, and their race/chapter/trail
    context. Recipient: ENROLLMENT_ALERT_EMAIL env, default REPLY_TO_EMAIL."""
    import asyncio
    import os
    from html import escape
    from mission_control.config import REPLY_TO_EMAIL
    from mission_control.services.sequence_engine import _send_email_sync

    to = os.environ.get("ENROLLMENT_ALERT_EMAIL", REPLY_TO_EMAIL)
    context = (
        source_data.get("wb_guide") and f"guide chapter: {source_data['wb_guide']}"
        or source_data.get("wb_trail") and f"viewed: {source_data['wb_trail']}"
        or source_data.get("race_name") and f"race: {source_data['race_name']}"
        or "no context"
    )
    subject = f"new lead · {name or email} · {context} [{brand}]"
    race = source_data.get("race_name", "")
    drafter = (
        f"<p style='color:#666'>reply-drafter: <code>python3 scripts/draft_race_reply.py "
        f"\"{escape(race)}\"{' --brand road' if brand == 'roadielabs' else ''}</code></p>"
        if race else ""
    )
    html = (
        f"<p><b>{escape(name) or '(no name)'}</b> &lt;{escape(email)}&gt;</p>"
        f"<ul>"
        f"<li>brand: {escape(brand)}</li>"
        f"<li>source: {escape(source)}</li>"
        f"<li>context: {escape(context)}</li>"
        f"<li>enrolled: {escape(', '.join(enrolled))}</li>"
        f"</ul>{drafter}"
    )
    await asyncio.to_thread(_send_email_sync, to, subject, html, brand)


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

    # Brand routing (worker sends "gravelgod" | "roadielabs"; unknown → gravelgod)
    brand = str(body.get("brand", "gravelgod")).lower()
    if brand not in ("gravelgod", "roadielabs"):
        brand = "gravelgod"

    source_data = {"brand": brand}
    if body.get("race_slug"):
        source_data["race_slug"] = body["race_slug"]
    if body.get("race_name"):
        source_data["race_name"] = body["race_name"]
    # Friend-register context (docs/specs/friend-first-sequences.md §4).
    # Welcome day-0 renders exactly ONE opener branch via the wb_* keys —
    # priority: guide chapter > browsing trail > race page. Mustache blocks
    # render independently, so exclusivity MUST be enforced here, not in the
    # template. race_name itself stays in source_data regardless (countdown
    # and quiz sequences depend on it).
    _chapter = str(body.get("guide_chapter", "")).strip()[:80]
    _viewed = body.get("viewed_races")
    if _chapter:
        source_data["guide_chapter"] = _chapter
        source_data["wb_guide"] = _chapter
    elif isinstance(_viewed, list) and _viewed:
        # short human-readable list for the template: "Unbound, SBT GRVL"
        names = [str(v).strip()[:60] for v in _viewed if str(v).strip()][:5]
        if names:
            source_data["viewed_races"] = ", ".join(names)
            source_data["wb_trail"] = source_data["viewed_races"]
    elif source_data.get("race_name"):
        source_data["wb_race"] = source_data["race_name"]
    if any(source_data.get(k) for k in ("wb_guide", "wb_trail", "wb_race")):
        source_data["any_context"] = "1"
    # Seasonal sensitivity: Nov-Jan is offseason for the northern-hemisphere
    # gravel calendar; welcome's anonymous branch swaps its opener.
    from datetime import datetime, timezone
    if datetime.now(timezone.utc).month in (11, 12, 1):
        source_data["offseason"] = "1"
    # plan_weeks (sent by a purchase payload) drives completion-relative review
    # timing in post_purchase (sequence_engine._step_delay_days). Accept a
    # positive number; silently ignore junk so a bad value never blocks enrollment.
    _pw = body.get("plan_weeks")
    try:
        if _pw is not None and float(_pw) > 0:
            source_data["plan_weeks"] = int(float(_pw))
    except (TypeError, ValueError):
        pass

    # Map capture source to sequence trigger
    trigger_map = {
        "exit_intent": "new_subscriber",
        "race_profile": "new_subscriber",
        "prep_kit_gate": "prep_kit_download",
        "race_quiz": "quiz_completed",
        "quiz_shared": "quiz_completed",
        "fueling_calculator": "new_subscriber",
        "training_guide": "new_subscriber",
        # Plan purchases (Stripe / WooCommerce / own-site) -> post-purchase
        # onboarding + review flywheel. The payment webhook must POST a source in
        # this set, with brand + plan_weeks (+ race_slug). Until that POST exists
        # the post_purchase sequence never enrolls anyone. See PIECE 2 in
        # gravel-god-training-plans/docs/E01_REVIEW_FLYWHEEL.md.
        "plan_purchased": "plan_purchased",
        "plan_purchase": "plan_purchased",
        "stripe_plan": "plan_purchased",
        "woocommerce": "plan_purchased",
    }
    trigger = trigger_map.get(source, "new_subscriber")

    # Enroll in matching sequences (brand-scoped)
    enrolled = []
    for seq in get_sequences_for_trigger(trigger, brand=brand):
        result = enroll(email, name, seq["id"], source=source, source_data=source_data)
        if result:
            enrolled.append(seq["id"])

    # WS-E (friend-first spec §4.1): no double-enrollment. Quiz and prep-kit
    # leads get ONLY their source sequence — it is their opener track. The old
    # "also enroll in welcome" behavior stacked overlapping opener tracks on
    # one subscriber (verified live, Jul 2026) and made any per-track promise
    # false. Deliberately removed; do not reintroduce.

    db.log_action(
        "subscriber_received", "webhook", email,
        f"Brand: {brand}, source: {source}, enrolled in: {', '.join(enrolled) or 'none (already enrolled)'}",
    )

    # Coach alert: every NEW enrollment is a conversation opportunity (the
    # friend-register model converts in replies), so Matti hears about it
    # immediately. Loud to coach, invisible to customer — alert failure must
    # never affect the enrollment (order-killer rule).
    if enrolled:
        try:
            await _send_enrollment_alert(email, name, brand, source, source_data, enrolled)
        except Exception:
            logger.exception("enrollment alert failed (enrollment itself succeeded)")

    return {"status": "ok", "enrolled": enrolled}


def _verify_svix_signature(raw_body: bytes, headers) -> bool:
    """Verify a Svix-signed webhook (Resend's signing scheme).

    Signature = base64(HMAC-SHA256(base64decode(secret), "{id}.{ts}.{body}"))
    The svix-signature header holds space-separated "v1,<sig>" candidates.
    """
    import base64
    import hashlib
    import hmac as hmac_mod

    from mission_control.config import RESEND_WEBHOOK_SECRET

    msg_id = headers.get("svix-id", "")
    timestamp = headers.get("svix-timestamp", "")
    signatures = headers.get("svix-signature", "")
    if not (msg_id and timestamp and signatures and RESEND_WEBHOOK_SECRET):
        return False

    secret = RESEND_WEBHOOK_SECRET.removeprefix("whsec_")
    try:
        key = base64.b64decode(secret + "=" * (-len(secret) % 4))
    except Exception:
        return False
    signed = f"{msg_id}.{timestamp}.".encode() + raw_body
    expected = base64.b64encode(
        hmac_mod.new(key, signed, hashlib.sha256).digest()).decode()
    for candidate in signatures.split(" "):
        sig = candidate.split(",", 1)[-1]
        if hmac_mod.compare_digest(expected, sig):
            return True
    return False


@router.post("/resend")
async def resend_webhook(
    request: Request,
    authorization: str = Header(""),
):
    """Receive Resend email event webhooks (opens, clicks, bounces)."""
    _check_rate_limit(request)
    raw_body = await request.body()

    # Real Resend events are Svix-signed; the Bearer path remains for
    # internal callers and tests.
    svix_ok = _verify_svix_signature(raw_body, request.headers)
    bearer_ok = bool(WEBHOOK_SECRET) and authorization == f"Bearer {WEBHOOK_SECRET}"
    if WEBHOOK_SECRET and not (svix_ok or bearer_ok):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

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
