"""Filesystem → Supabase sync engine.

Reads athlete directories and upserts data into Supabase gg_athletes + gg_touchpoints.
Filesystem wins for intake/derived/touchpoint data.
Database wins for plan_status (once delivered), notes, NPS, referrals.
"""

import json
from pathlib import Path

import yaml

from mission_control.config import ATHLETES_DIR
from mission_control import supabase_client as db


def sync_all() -> dict:
    """Scan athletes/ directory and sync everything into Supabase.

    Returns dict with counts: {"athletes": N, "touchpoints": N, "skipped": N}.
    """
    if not ATHLETES_DIR.exists():
        return {"athletes": 0, "touchpoints": 0, "skipped": 0}

    stats = {"athletes": 0, "touchpoints": 0, "skipped": 0}

    for athlete_dir in sorted(ATHLETES_DIR.iterdir()):
        if not athlete_dir.is_dir():
            continue
        intake_path = athlete_dir / "intake.json"
        if not intake_path.exists():
            stats["skipped"] += 1
            continue

        result = _sync_athlete(athlete_dir)
        stats["athletes"] += 1
        stats["touchpoints"] += result.get("touchpoints", 0)

    return stats


def _sync_athlete(athlete_dir: Path) -> dict:
    """Sync a single athlete directory into Supabase."""
    slug = athlete_dir.name
    result = {"touchpoints": 0}

    # Read intake
    intake_path = athlete_dir / "intake.json"
    intake = json.loads(intake_path.read_text())

    name = intake.get("name", slug)
    email = intake.get("email", "")
    ftp = intake.get("ftp")
    weekly_hours = intake.get("weekly_hours", "")

    # Read derived.yaml if exists
    tier = None
    level = None
    race_name = None
    race_date = None
    plan_weeks = None
    derived_json = None

    derived_path = athlete_dir / "derived.yaml"
    if derived_path.exists():
        derived = yaml.safe_load(derived_path.read_text())
        derived_json = derived
        tier = derived.get("tier")
        level = derived.get("level")
        race_name = derived.get("race_name")
        race_date = str(derived.get("race_date", "")) or None
        plan_weeks = derived.get("plan_weeks") or derived.get("plan_duration")
    else:
        # Fall back to intake for race info
        races = intake.get("races", [])
        if races:
            race_name = races[0].get("name")
            race_date = races[0].get("date")

    # Read methodology.json if exists
    methodology_json = None
    methodology_path = athlete_dir / "methodology.json"
    if methodology_path.exists():
        methodology_json = json.loads(methodology_path.read_text())

    # Determine plan_status from filesystem artifacts
    receipt_path = athlete_dir / "receipt.json"
    plan_status = "intake_received"

    guide_path = athlete_dir / "guide.html"
    workouts_dir = athlete_dir / "workouts"

    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt.get("email_sent"):
            plan_status = "delivered"
        else:
            plan_status = "approved"
    elif guide_path.exists() or (workouts_dir.exists() and any(workouts_dir.iterdir())):
        plan_status = "pipeline_complete"
    elif derived_path.exists():
        plan_status = "pipeline_complete"

    # Check existing record — preserve DB-only fields
    existing = db.get_athlete(slug)

    # Preserve DB-wins fields if already set beyond initial states
    if existing:
        db_status = existing.get("plan_status", "")
        if db_status in ("delivered", "active", "post_race", "archived"):
            plan_status = db_status

    # Build upsert data
    athlete_data = {
        "slug": slug,
        "name": name,
        "email": email,
        "tier": tier,
        "level": level,
        "race_name": race_name,
        "race_date": race_date,
        "plan_weeks": plan_weeks,
        "plan_status": plan_status,
        "ftp": ftp,
        "weekly_hours": str(weekly_hours) if weekly_hours else None,
        "intake_json": intake,
        "derived_json": derived_json,
        "methodology_json": methodology_json,
    }

    # Preserve notes if they exist
    if existing and existing.get("notes"):
        athlete_data.pop("notes", None)

    row = db.upsert_athlete(athlete_data)
    athlete_id = row.get("id") or (existing and existing.get("id"))

    if not athlete_id:
        return result

    # Sync touchpoints
    tp_path = athlete_dir / "touchpoints.json"
    if tp_path.exists():
        result["touchpoints"] = _sync_touchpoints(athlete_id, tp_path)

    # Log delivery communication if receipt exists
    if receipt_path.exists():
        _sync_delivery_comm(athlete_id, receipt_path)

    return result


def _sync_touchpoints(athlete_id: str, tp_path: Path) -> int:
    """Sync touchpoints.json into gg_touchpoints. Returns count."""
    data = json.loads(tp_path.read_text())
    touchpoints = data.get("touchpoints", [])

    count = 0
    for tp in touchpoints:
        tp_data = {
            "athlete_id": athlete_id,
            "touchpoint_id": tp["id"],
            "category": tp.get("category", ""),
            "send_date": tp["send_date"],
            "subject": tp.get("subject", ""),
            "template": tp.get("template", tp["id"]),
            "template_data": tp.get("template_data"),
        }

        # Check if already sent in DB — don't overwrite sent status
        existing = db.select_one("gg_touchpoints", match={
            "athlete_id": athlete_id,
            "touchpoint_id": tp["id"],
        })
        if existing and existing.get("sent"):
            # Already sent — only update schedule info, not sent status
            tp_data.pop("athlete_id", None)
            tp_data.pop("touchpoint_id", None)
        else:
            # Not yet sent — include sent status from filesystem
            tp_data["sent"] = bool(tp.get("sent"))
            tp_data["sent_at"] = tp.get("sent_at")

        db.upsert_touchpoint({
            "athlete_id": athlete_id,
            "touchpoint_id": tp["id"],
            **tp_data,
        })
        count += 1

    return count


def _sync_delivery_comm(athlete_id: str, receipt_path: Path) -> None:
    """Sync receipt.json into gg_communications if delivered."""
    receipt = json.loads(receipt_path.read_text())
    if not receipt.get("email_sent"):
        return

    # Check if already logged
    existing = db.select("gg_communications", match={
        "athlete_id": athlete_id,
        "comm_type": "delivery",
    }, limit=1)
    if existing:
        return

    db.log_communication(
        athlete_id=athlete_id,
        comm_type="delivery",
        subject="Training Plan Delivery",
        recipient=receipt.get("recipient", ""),
        resend_id=receipt.get("resend_id", ""),
        status="sent",
    )
