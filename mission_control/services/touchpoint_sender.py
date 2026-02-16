"""Touchpoint sender — render template, send via Resend, update Supabase."""

import json
from datetime import date, datetime
from pathlib import Path

from mission_control.config import ATHLETES_DIR, RESEND_API_KEY, RESEND_FROM_EMAIL, TEMPLATES_DIR
from mission_control import supabase_client as db


def render_touchpoint(touchpoint: dict, athlete: dict) -> str:
    """Render a touchpoint email template with athlete data."""
    template_name = touchpoint["template"]
    template_path = TEMPLATES_DIR / f"{template_name}.html"

    if not template_path.exists():
        return f"<p>Template not found: {template_name}.html</p>"

    html = template_path.read_text()

    # Get intake data
    intake = athlete.get("intake_json") or {}
    if isinstance(intake, str):
        intake = json.loads(intake)

    # Build replacements
    replacements = {
        "{athlete_name}": intake.get("name", athlete.get("name", "")),
        "{race_name}": athlete.get("race_name", ""),
        "{race_date}": str(athlete.get("race_date", "")),
        "{plan_duration}": str(athlete.get("plan_weeks", "")),
    }

    # Dynamic template_data
    template_data = touchpoint.get("template_data")
    if template_data:
        if isinstance(template_data, str):
            try:
                template_data = json.loads(template_data)
            except (json.JSONDecodeError, TypeError):
                template_data = {}
        if isinstance(template_data, dict):
            for key, val in template_data.items():
                replacements[f"{{{key}}}"] = str(val)

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return html


def send_touchpoint(touchpoint_id: str, dry_run: bool = False) -> dict:
    """Send a single touchpoint email.

    Args:
        touchpoint_id: UUID of the touchpoint row.
        dry_run: If True, render but don't send.

    Returns:
        dict with keys: success, html, message, resend_id (if sent).
    """
    tp = db.select_one("gg_touchpoints", match={"id": touchpoint_id})
    if not tp:
        return {"success": False, "message": "Touchpoint not found"}

    athlete = db.get_athlete_by_id(tp["athlete_id"])
    if not athlete:
        return {"success": False, "message": "Athlete not found"}

    html = render_touchpoint(tp, athlete)

    if dry_run:
        return {"success": True, "html": html, "message": "Dry run — not sent", "dry_run": True}

    if not RESEND_API_KEY:
        return {"success": False, "html": html, "message": "RESEND_API_KEY not set — cannot send"}

    try:
        import resend
        resend.api_key = RESEND_API_KEY

        result = resend.Emails.send({
            "from": f"Gravel God <{RESEND_FROM_EMAIL}>",
            "to": [athlete["email"]],
            "subject": tp["subject"],
            "html": html,
        })

        resend_id = result.get("id", "")
        now = datetime.utcnow().isoformat()

        # Update touchpoint
        db.update_touchpoint(touchpoint_id, {
            "sent": True,
            "sent_at": now,
            "resend_id": resend_id,
        })

        # Log communication
        db.log_communication(
            athlete_id=athlete["id"],
            comm_type="touchpoint",
            subject=tp["subject"],
            recipient=athlete["email"],
            resend_id=resend_id,
        )

        # Update filesystem
        _update_filesystem_touchpoint(athlete["slug"], tp["touchpoint_id"], now)

        # Audit log
        db.log_action("touchpoint_sent", "touchpoint", str(touchpoint_id),
                       f"{tp['touchpoint_id']} to {athlete['name']}")

        return {"success": True, "html": html, "message": f"Sent to {athlete['email']}", "resend_id": resend_id}

    except Exception as e:
        return {"success": False, "html": html, "message": f"Send failed: {e}"}


def batch_send_due(dry_run: bool = False) -> dict:
    """Send all touchpoints that are due today or earlier."""
    due_count = db.count_due_touchpoints()

    if dry_run:
        return {"due": due_count, "sent": 0, "failed": 0, "dry_run": True}

    due_touchpoints = db.get_touchpoints(due_only=True)

    sent = 0
    failed = 0
    for tp in due_touchpoints:
        result = send_touchpoint(tp["id"])
        if result["success"]:
            sent += 1
        else:
            failed += 1

    return {"due": len(due_touchpoints), "sent": sent, "failed": failed, "dry_run": False}


def _update_filesystem_touchpoint(slug: str, touchpoint_id: str, sent_at: str) -> None:
    """Update touchpoints.json on disk to mark as sent."""
    tp_path = ATHLETES_DIR / slug / "touchpoints.json"
    if not tp_path.exists():
        return

    data = json.loads(tp_path.read_text())
    for tp in data.get("touchpoints", []):
        if tp["id"] == touchpoint_id:
            tp["sent"] = True
            tp["sent_at"] = sent_at
            break

    tp_path.write_text(json.dumps(data, indent=2))
