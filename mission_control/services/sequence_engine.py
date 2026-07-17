"""Sequence engine — enrollment, scheduling, sending, A/B assignment."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import random
import re
import urllib.parse
from datetime import datetime, timedelta, timezone

from mission_control import supabase_client as db
from mission_control.config import (
    PUBLIC_URL, RESEND_API_KEY, UNSUBSCRIBE_SECRET, WEB_TEMPLATES_DIR,
)
from mission_control.sequences import get_sequence, SEQUENCES

# Triggers that are post-purchase — should NOT be suppressed for customers
_POST_PURCHASE_TRIGGERS = {"plan_purchased"}

# Fallback plan length (weeks) for completion-relative steps when the
# enrollment's source_data carries no usable plan_weeks AND the step has no
# static delay_days fallback of its own. 12 weeks matches our most common
# tier-2 plan length. See _step_delay_days().
_DEFAULT_PLAN_WEEKS = 12

logger = logging.getLogger(__name__)


def _step_delay_days(step: dict, source_data: dict | None) -> int:
    """Resolve a step's cumulative delay-from-enrollment, in days.

    Steps normally carry a static `delay_days` — CUMULATIVE from enrollment,
    exactly as before. This function returns that value unchanged for such
    steps (full backward compatibility).

    A step may instead (additionally) carry `delay_from_completion_days: N`,
    which schedules it relative to plan *completion* rather than a fixed
    calendar day: `(plan_weeks * 7) + N` days from enrollment, where
    `plan_weeks` comes from the enrollment's `source_data`.

    Fallback order when `delay_from_completion_days` is present:
      1. `source_data["plan_weeks"]` is a valid positive number -> use it.
      2. else, if the step also has a static `delay_days` -> use that as-is
         (documented fallback; lets a step degrade gracefully to a fixed day
         when plan length isn't known yet).
      3. else -> assume _DEFAULT_PLAN_WEEKS (12) weeks.
    """
    completion_delay = step.get("delay_from_completion_days")
    if completion_delay is None:
        return step["delay_days"]

    plan_weeks = (source_data or {}).get("plan_weeks")
    try:
        plan_weeks = float(plan_weeks)
        if plan_weeks <= 0:
            raise ValueError
    except (TypeError, ValueError):
        plan_weeks = None

    if plan_weeks is not None:
        return int(plan_weeks * 7) + completion_delay
    if "delay_days" in step:
        return step["delay_days"]
    return _DEFAULT_PLAN_WEEKS * 7 + completion_delay

# Lock to prevent concurrent process_due_sends() from sending duplicate emails
_processing_lock = asyncio.Lock()


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

    # Calculate first send time (honors delay_from_completion_days if set)
    first_delay = _step_delay_days(steps[0], source_data) if steps else 0
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

    # Auto-create deal for marketing sequences (not post-purchase)
    if seq.get("trigger") not in _POST_PURCHASE_TRIGGERS:
        existing_deal = db.select_one("gg_deals", match={"contact_email": email})
        if not existing_deal:
            from mission_control.services.deals import create_deal
            sd = source_data or {}
            create_deal(
                email=email,
                name=name,
                race_name=sd.get("race_name", ""),
                race_slug=sd.get("race_slug", ""),
                source=source,
                value=249.00,
            )

    return enrollment


def _pick_variant(variants: dict) -> str:
    """Pick a variant based on weights.

    Raises ValueError if variants is empty or all weights are zero.
    """
    if not variants:
        raise ValueError("No variants defined")
    keys = list(variants.keys())
    weights = [variants[k]["weight"] for k in keys]
    if not any(w > 0 for w in weights):
        raise ValueError(f"All variant weights are zero: {keys}")
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

    Uses an async lock to prevent concurrent invocations from sending
    duplicate emails (e.g. if scheduler fires twice in quick succession).

    Returns dict with counts: {processed, sent, errors, skipped}.
    """
    if _processing_lock.locked():
        logger.info("process_due_sends already running, skipping")
        return {"processed": 0, "sent": 0, "errors": 0, "skipped": True}

    async with _processing_lock:
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
                logger.exception("Error sending step for enrollment %s", enrollment["id"])
                db.log_action(
                    "sequence_send_error",
                    "enrollment",
                    str(enrollment["id"]),
                    str(e),
                )

        return {"processed": len(enrollments), "sent": sent, "errors": errors, "skipped": False}


async def _send_next_step(enrollment: dict) -> bool:
    """Send the current step for an enrollment and advance to next."""
    seq = get_sequence(enrollment["sequence_id"])
    if not seq:
        return False

    # Customer suppression — don't send marketing emails to existing customers
    if seq.get("trigger") not in _POST_PURCHASE_TRIGGERS:
        customer = db.select_one(
            "gg_athletes",
            columns="plan_status",
            match={"email": enrollment["contact_email"]},
        )
        if customer and customer.get("plan_status") in (
            "delivered", "approved", "audit_passed",
        ):
            db.update("gg_sequence_enrollments", {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }, {"id": enrollment["id"]})
            db.log_action(
                "sequence_suppressed", "enrollment", str(enrollment["id"]),
                f"Customer suppression: {enrollment['contact_email']} "
                f"has plan_status={customer['plan_status']}",
            )
            return True

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
    brand = seq.get("brand", "gravelgod")

    # Render subject with source_data substitutions
    subject = _render_subject(step["subject"], enrollment.get("source_data") or {})

    # Render email template, inject UTM tracking, and inject unsubscribe link
    html = _render_template(step["template"], enrollment)
    html = _inject_utm_params(
        html,
        sequence_id=enrollment["sequence_id"],
        variant=enrollment["variant"],
        step_index=step_index,
        brand=brand,
    )
    html = _inject_unsubscribe(html, enrollment["contact_email"])

    # Send via Resend (in thread to avoid blocking event loop)
    if not RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set — skipping send for %s step %d",
                        enrollment["contact_email"], step_index)
        return False

    try:
        resend_id = await asyncio.to_thread(
            _send_email_sync,
            enrollment["contact_email"],
            subject,
            html,
            brand,
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
        # Schedule next send.
        # delay_days is CUMULATIVE from enrollment (day 0, 3, 7 = gaps of 3, 4).
        # Delta = next step's delay minus current step's delay.
        # min 1 day gap to prevent same-day sends from config errors.
        # _step_delay_days() also resolves delay_from_completion_days steps
        # (plan_weeks*7 + N) — see that function for fallback semantics.
        source_data = enrollment.get("source_data") or {}
        next_delay = _step_delay_days(steps[next_step], source_data)
        current_delay = _step_delay_days(step, source_data)
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
        if val is not None:
            subject = subject.replace(f"{{{key}}}", str(val))
    # race_name is not guaranteed in source_data — never leak the placeholder
    return subject.replace("{race_name}", "your race")


def _apply_conditionals(html: str, data: dict) -> str:
    """Mustache-style conditional blocks for optional personalization.

    {{#key}}...{{/key}}  kept only when data[key] is truthy
    {{^key}}...{{/key}}  kept only when data[key] is missing/empty

    Lets one template serve both known-race signups (race_profile /
    prep_kit captures carry race_name) and anonymous ones (exit_intent)
    — the friend-opener rule: talk about THEM when you know anything
    about them, and never leak an empty placeholder when you don't.

    Blocks may nest (e.g. {{^any_context}} wrapping {{^offseason}}/
    {{#offseason}} in welcome_value) — a single regex pass only resolves
    the outermost block and leaves inner tags raw inside its kept body,
    so this re-applies to a fixed point (repeats until a pass makes no
    further change) to resolve arbitrary nesting depth.
    """
    import re as _re

    def _repl(m):
        inverse, key, body = m.group(1) == "^", m.group(2), m.group(3)
        has = bool(data.get(key))
        return body if has != inverse else ""

    pattern = _re.compile(r"\{\{([#^])(\w+)\}\}(.*?)\{\{/\2\}\}", _re.S)
    prev = None
    while prev != html:
        prev = html
        html = pattern.sub(_repl, html)
    return html


def _render_template(template_name: str, enrollment: dict) -> str:
    """Render a sequence email template."""
    template_path = WEB_TEMPLATES_DIR / "emails" / "sequences" / f"{template_name}.html"

    if not template_path.exists():
        raise FileNotFoundError(f"Sequence email template '{template_name}' not found at {template_path}")

    html = template_path.read_text()

    # Replace placeholders with enrollment data
    source_data = enrollment.get("source_data") or {}
    html = _apply_conditionals(html, source_data)
    replacements = {
        "{contact_name}": enrollment.get("contact_name", ""),
        "{contact_email}": enrollment.get("contact_email", ""),
        "{first_name}": enrollment.get("contact_name", "").split()[0] if enrollment.get("contact_name") else "there",
    }
    # Add source_data replacements
    for key, val in source_data.items():
        if val is not None:
            replacements[f"{{{key}}}"] = str(val)

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    # race_name is not guaranteed in source_data — never leak the placeholder
    return html.replace("{race_name}", "your race")


def _inject_utm_params(
    html: str, sequence_id: str, variant: str, step_index: int,
    brand: str = "gravelgod",
) -> str:
    """Append UTM tracking params to all brand-site links in HTML."""
    from mission_control.config import BRAND_SEQUENCE_SENDERS

    sender = BRAND_SEQUENCE_SENDERS.get(brand, BRAND_SEQUENCE_SENDERS["gravelgod"])
    utm = urllib.parse.urlencode({
        "utm_source": sender["utm_source"],
        "utm_medium": "email",
        "utm_campaign": sequence_id,
        "utm_content": f"{variant}_{step_index}",
    })

    def _add_utm(match: re.Match) -> str:
        url = match.group(1)
        sep = "&" if "?" in url else "?"
        return f'href="{url}{sep}{utm}"'

    return re.sub(
        r'href="(https://(?:gravelgodcycling|roadielabs|xcskilabs)\.com[^"]*)"',
        _add_utm,
        html,
    )


def _send_email_sync(
    to_email: str, subject: str, html: str, brand: str = "gravelgod",
) -> str:
    """Send an email via Resend. Runs in a thread (called via asyncio.to_thread)."""
    import resend
    from mission_control.config import BRAND_SEQUENCE_SENDERS

    if not resend.api_key:
        resend.api_key = RESEND_API_KEY

    sender = BRAND_SEQUENCE_SENDERS.get(brand, BRAND_SEQUENCE_SENDERS["gravelgod"])
    result = resend.Emails.send({
        "from": f"{sender['from_name']} <{sender['from_email']}>",
        "reply_to": sender["reply_to"],
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

    # Send stats per variant — only fetch sends for this sequence's enrollments
    enrollment_ids = {e["id"] for e in enrollments}
    sends = []
    for eid in enrollment_ids:
        sends.extend(db.select("gg_sequence_sends", match={"enrollment_id": eid}))
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


def reset_enrollment(enrollment_id: str) -> bool:
    """Reset an enrollment back to step 0 and clear stale sends.

    Used to recover from sends recorded without an actual email delivery
    (e.g. RESEND_API_KEY was not set when the scheduler ran).
    """
    enrollment = db.select_one("gg_sequence_enrollments", match={"id": enrollment_id})
    if not enrollment:
        return False

    # Delete stale send records (no resend_id = never actually sent)
    stale_sends = db.select("gg_sequence_sends", match={"enrollment_id": enrollment_id})
    for send in stale_sends:
        if not send.get("resend_id"):
            db.delete("gg_sequence_sends", {"id": send["id"]})

    # Reset enrollment to step 0, active, send now
    db.update("gg_sequence_enrollments", {
        "current_step": 0,
        "status": "active",
        "completed_at": None,
        "next_send_at": datetime.now(timezone.utc).isoformat(),
    }, {"id": enrollment_id})

    db.log_action("enrollment_reset", "enrollment", enrollment_id,
                  f"Reset to step 0: {enrollment['contact_email']}")
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
