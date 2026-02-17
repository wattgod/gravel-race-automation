"""Sequence engine — enrollment, scheduling, sending, A/B assignment."""

import asyncio
import hashlib
import hmac
import random
import urllib.parse
from datetime import datetime, timedelta, timezone

from mission_control import supabase_client as db
from mission_control.config import (
    PUBLIC_URL, RESEND_API_KEY, UNSUBSCRIBE_SECRET, WEB_TEMPLATES_DIR,
)
from mission_control.sequences import get_sequence, SEQUENCES


def enroll(
    email: str,
    name: str,
    sequence_id: str,
    source: str = "",
    source_data: dict | None = None,
) -> dict | None:
    """Enroll a contact in a sequence. Assigns variant by weight.

    Returns the enrollment record, or None if already enrolled or sequence not found.
    """
    seq = get_sequence(sequence_id)
    if not seq or not seq.get("active"):
        return None

    # Check for existing enrollment
    existing = db.select_one(
        "gg_sequence_enrollments",
        match={"sequence_id": sequence_id, "contact_email": email},
    )
    if existing:
        return None

    # Assign variant by weight
    variant = _pick_variant(seq["variants"])
    steps = seq["variants"][variant]["steps"]

    # Calculate first send time
    first_delay = steps[0]["delay_days"] if steps else 0
    now = datetime.now(timezone.utc)
    next_send = now + timedelta(days=first_delay)

    enrollment = db.insert("gg_sequence_enrollments", {
        "sequence_id": sequence_id,
        "variant": variant,
        "contact_email": email,
        "contact_name": name,
        "source": source,
        "source_data": source_data or {},
        "current_step": 0,
        "status": "active",
        "next_send_at": next_send.isoformat(),
    })

    db.log_action(
        "sequence_enrolled",
        "sequence",
        sequence_id,
        f"{email} enrolled in {seq['name']} variant {variant}",
    )

    return enrollment


def _pick_variant(variants: dict) -> str:
    """Pick a variant based on weights."""
    keys = list(variants.keys())
    weights = [variants[k]["weight"] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def generate_unsubscribe_token(email: str) -> str:
    """Generate an HMAC token for unsubscribe URL verification."""
    secret = (UNSUBSCRIBE_SECRET or "fallback-dev-secret").encode()
    return hmac.new(secret, email.lower().encode(), hashlib.sha256).hexdigest()[:32]


def verify_unsubscribe_token(email: str, token: str) -> bool:
    """Verify an unsubscribe token is valid for the given email."""
    expected = generate_unsubscribe_token(email)
    return hmac.compare_digest(expected, token)


def build_unsubscribe_url(email: str) -> str:
    """Build the full unsubscribe URL for an email address."""
    token = generate_unsubscribe_token(email)
    params = urllib.parse.urlencode({"email": email, "token": token})
    return f"{PUBLIC_URL}/unsubscribe?{params}"


async def process_due_sends() -> dict:
    """Process all enrollments with due sends. Called by scheduler.

    Returns dict with counts: {processed, sent, errors}.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Query enrollments where status=active and next_send_at <= now
    q = db._table("gg_sequence_enrollments").select("*")
    q = q.eq("status", "active").lte("next_send_at", now)
    result = q.execute()
    enrollments = result.data or []

    sent = 0
    errors = 0

    for enrollment in enrollments:
        try:
            success = await _send_next_step(enrollment)
            if success:
                sent += 1
            else:
                errors += 1
        except Exception as e:
            errors += 1
            db.log_action(
                "sequence_send_error",
                "enrollment",
                str(enrollment["id"]),
                str(e),
            )

    return {"processed": len(enrollments), "sent": sent, "errors": errors}


async def _send_next_step(enrollment: dict) -> bool:
    """Send the current step for an enrollment and advance to next."""
    seq = get_sequence(enrollment["sequence_id"])
    if not seq:
        return False

    variant_key = enrollment["variant"]
    variant = seq["variants"].get(variant_key)
    if not variant:
        return False

    steps = variant["steps"]
    step_index = enrollment["current_step"]

    if step_index >= len(steps):
        # Sequence complete
        db.update("gg_sequence_enrollments", {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }, {"id": enrollment["id"]})
        return True

    step = steps[step_index]

    # Render subject with source_data substitutions
    subject = _render_subject(step["subject"], enrollment.get("source_data") or {})

    # Render email template and inject unsubscribe link
    html = _render_template(step["template"], enrollment)
    html = _inject_unsubscribe(html, enrollment["contact_email"])

    # Send via Resend (in thread to avoid blocking event loop)
    resend_id = ""
    if RESEND_API_KEY:
        try:
            resend_id = await asyncio.to_thread(
                _send_email_sync,
                enrollment["contact_email"],
                subject,
                html,
            )
        except Exception as e:
            db.log_action(
                "sequence_send_error",
                "enrollment",
                str(enrollment["id"]),
                f"Resend error on step {step_index}: {e}",
            )
            return False

    # Record send
    db.insert("gg_sequence_sends", {
        "enrollment_id": enrollment["id"],
        "step_index": step_index,
        "template": step["template"],
        "subject": subject,
        "resend_id": resend_id,
        "status": "sent",
    })

    # Advance to next step
    next_step = step_index + 1
    now = datetime.now(timezone.utc)

    if next_step >= len(steps):
        # Sequence complete after this send
        db.update("gg_sequence_enrollments", {
            "current_step": next_step,
            "status": "completed",
            "completed_at": now.isoformat(),
            "next_send_at": None,
        }, {"id": enrollment["id"]})
    else:
        # Schedule next send
        next_delay = steps[next_step]["delay_days"]
        current_delay = step["delay_days"]
        delta_days = next_delay - current_delay
        next_send = now + timedelta(days=max(delta_days, 1))

        db.update("gg_sequence_enrollments", {
            "current_step": next_step,
            "next_send_at": next_send.isoformat(),
        }, {"id": enrollment["id"]})

    return True


def _render_subject(subject: str, source_data: dict) -> str:
    """Replace {placeholders} in subject with source_data values."""
    for key, val in source_data.items():
        subject = subject.replace(f"{{{key}}}", str(val))
    return subject


def _render_template(template_name: str, enrollment: dict) -> str:
    """Render a sequence email template."""
    template_path = WEB_TEMPLATES_DIR / "emails" / "sequences" / f"{template_name}.html"

    if not template_path.exists():
        raise FileNotFoundError(f"Sequence email template '{template_name}' not found at {template_path}")

    html = template_path.read_text()

    # Replace placeholders with enrollment data
    source_data = enrollment.get("source_data") or {}
    replacements = {
        "{contact_name}": enrollment.get("contact_name", ""),
        "{contact_email}": enrollment.get("contact_email", ""),
        "{first_name}": enrollment.get("contact_name", "").split()[0] if enrollment.get("contact_name") else "",
    }
    # Add source_data replacements
    for key, val in source_data.items():
        replacements[f"{{{key}}}"] = str(val)

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return html


def _send_email_sync(to_email: str, subject: str, html: str) -> str:
    """Send an email via Resend. Runs in a thread (called via asyncio.to_thread)."""
    import resend
    resend.api_key = RESEND_API_KEY

    from mission_control.config import SEQUENCE_FROM_EMAIL, SEQUENCE_FROM_NAME
    result = resend.Emails.send({
        "from": f"{SEQUENCE_FROM_NAME} <{SEQUENCE_FROM_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html,
    })
    return result.get("id", "")


def _inject_unsubscribe(html: str, email: str) -> str:
    """Inject unsubscribe link into email HTML before closing </body> or at end."""
    unsub_url = build_unsubscribe_url(email)
    unsub_block = (
        '<div style="text-align:center;padding:16px 32px;font-family:\'Courier New\',monospace;'
        'font-size:11px;color:#8c7568;border-top:1px solid #d4c5b9">'
        f'<a href="{unsub_url}" style="color:#8c7568;text-decoration:underline">'
        'Unsubscribe</a> from future emails'
        '</div>'
    )

    if '</body>' in html:
        html = html.replace('</body>', f'{unsub_block}</body>')
    elif '</html>' in html:
        html = html.replace('</html>', f'{unsub_block}</html>')
    else:
        html += unsub_block

    return html


def record_event(resend_id: str, event_type: str) -> bool:
    """Record an email event (open, click, bounce) from Resend webhook."""
    send = db.select_one("gg_sequence_sends", match={"resend_id": resend_id})
    if not send:
        return False

    now = datetime.now(timezone.utc).isoformat()
    updates = {}

    if event_type == "email.opened" and not send.get("opened_at"):
        updates["opened_at"] = now
        updates["status"] = "opened"
    elif event_type == "email.clicked" and not send.get("clicked_at"):
        updates["clicked_at"] = now
        updates["status"] = "clicked"
    elif event_type == "email.bounced":
        updates["status"] = "bounced"
        # Pause enrollment on bounce
        enrollment = db.select_one(
            "gg_sequence_enrollments", match={"id": send["enrollment_id"]}
        )
        if enrollment:
            db.update("gg_sequence_enrollments", {"status": "paused"}, {"id": enrollment["id"]})

    if updates:
        db.update("gg_sequence_sends", updates, {"id": send["id"]})
        return True

    return False


def get_sequence_stats(sequence_id: str) -> dict:
    """Get aggregate stats for a sequence."""
    enrollments = db.select("gg_sequence_enrollments", match={"sequence_id": sequence_id})

    total = len(enrollments)
    active = sum(1 for e in enrollments if e["status"] == "active")
    completed = sum(1 for e in enrollments if e["status"] == "completed")
    paused = sum(1 for e in enrollments if e["status"] == "paused")

    # Per-variant stats
    variant_stats = {}
    for e in enrollments:
        v = e["variant"]
        if v not in variant_stats:
            variant_stats[v] = {"total": 0, "completed": 0, "active": 0}
        variant_stats[v]["total"] += 1
        if e["status"] == "completed":
            variant_stats[v]["completed"] += 1
        elif e["status"] == "active":
            variant_stats[v]["active"] += 1

    # Send stats per variant
    sends = db.select("gg_sequence_sends")
    enrollment_map = {e["id"]: e for e in enrollments}

    for v in variant_stats:
        v_sends = [
            s for s in sends
            if s["enrollment_id"] in enrollment_map
            and enrollment_map[s["enrollment_id"]]["variant"] == v
        ]
        total_sends = len(v_sends)
        opens = sum(1 for s in v_sends if s.get("opened_at"))
        clicks = sum(1 for s in v_sends if s.get("clicked_at"))
        variant_stats[v]["sends"] = total_sends
        variant_stats[v]["opens"] = opens
        variant_stats[v]["clicks"] = clicks
        variant_stats[v]["open_rate"] = round(opens / total_sends * 100, 1) if total_sends else 0
        variant_stats[v]["click_rate"] = round(clicks / total_sends * 100, 1) if total_sends else 0

    return {
        "total": total,
        "active": active,
        "completed": completed,
        "paused": paused,
        "completion_rate": round(completed / total * 100, 1) if total else 0,
        "variants": variant_stats,
    }


def pause_enrollment(enrollment_id: str) -> bool:
    """Pause an active enrollment."""
    enrollment = db.select_one("gg_sequence_enrollments", match={"id": enrollment_id})
    if not enrollment or enrollment["status"] != "active":
        return False
    db.update("gg_sequence_enrollments", {"status": "paused"}, {"id": enrollment_id})
    db.log_action("sequence_paused", "enrollment", enrollment_id)
    return True


def resume_enrollment(enrollment_id: str) -> bool:
    """Resume a paused enrollment."""
    enrollment = db.select_one("gg_sequence_enrollments", match={"id": enrollment_id})
    if not enrollment or enrollment["status"] != "paused":
        return False

    # Recalculate next_send_at based on current step
    seq = get_sequence(enrollment["sequence_id"])
    if not seq:
        return False

    variant = seq["variants"].get(enrollment["variant"])
    if not variant:
        return False

    steps = variant["steps"]
    step_index = enrollment["current_step"]

    if step_index < len(steps):
        next_send = datetime.now(timezone.utc) + timedelta(hours=1)
        db.update("gg_sequence_enrollments", {
            "status": "active",
            "next_send_at": next_send.isoformat(),
        }, {"id": enrollment_id})
    else:
        db.update("gg_sequence_enrollments", {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }, {"id": enrollment_id})

    db.log_action("sequence_resumed", "enrollment", enrollment_id)
    return True


def unsubscribe(email: str) -> int:
    """Pause all active enrollments for an email. Returns count paused."""
    enrollments = db.select(
        "gg_sequence_enrollments",
        match={"contact_email": email},
    )
    count = 0
    for e in enrollments:
        if e["status"] == "active":
            db.update("gg_sequence_enrollments", {"status": "unsubscribed"}, {"id": e["id"]})
            count += 1

    if count:
        db.log_action("sequence_unsubscribed", "contact", email, f"Paused {count} enrollments")

    return count
