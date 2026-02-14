"""
Step 11: Generate Automated Check-In Touchpoint Schedule

Creates touchpoints.json in the athlete directory with a schedule of
automated check-in emails throughout the training plan.

All dates are deterministic — computed from plan_start_date, race_date,
and plan structure. No AI content. Templates are pre-written HTML files.

Touchpoints are sent externally via scripts/send_touchpoint.py.
"""

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


# ── Touchpoint Definitions ───────────────────────────────────

TOUCHPOINT_TYPES = [
    {
        "id": "week_1_welcome",
        "offset_type": "plan_start",
        "offset_days": 2,
        "subject": "Your first week — here's what to focus on",
        "template": "week_1_welcome",
    },
    {
        "id": "week_2_checkin",
        "offset_type": "plan_start",
        "offset_days": 7,
        "subject": "How's week 1 going?",
        "template": "week_2_checkin",
    },
    {
        "id": "first_recovery",
        "offset_type": "first_recovery_week",
        "offset_days": 0,
        "subject": "Recovery week — trust the process",
        "template": "first_recovery",
    },
    {
        "id": "mid_plan",
        "offset_type": "midpoint",
        "offset_days": 0,
        "subject": "Halfway there — progress check",
        "template": "mid_plan",
    },
    {
        "id": "build_phase_start",
        "offset_type": "build_start",
        "offset_days": 0,
        "subject": "Intensity increases this week",
        "template": "build_phase_start",
    },
    {
        "id": "race_month",
        "offset_type": "race_date",
        "offset_days": -28,
        "subject": "Race month — the work is done",
        "template": "race_month",
    },
    {
        "id": "race_week",
        "offset_type": "race_date",
        "offset_days": -7,
        "subject": "Race week — {race_name}",
        "template": "race_week",
    },
    {
        "id": "race_day_morning",
        "offset_type": "race_date",
        "offset_days": 0,
        "subject": "Go time. You're ready.",
        "template": "race_day_morning",
    },
    {
        "id": "post_race_3_days",
        "offset_type": "race_date",
        "offset_days": 3,
        "subject": "How'd it go?",
        "template": "post_race_3_days",
    },
    {
        "id": "post_race_2_weeks",
        "offset_type": "race_date",
        "offset_days": 14,
        "subject": "What's next?",
        "template": "post_race_2_weeks",
    },
]


def generate_touchpoints(
    profile: Dict,
    derived: Dict,
    plan_config: Dict,
    athlete_dir: Path,
) -> Dict:
    """Generate touchpoints.json schedule in the athlete directory."""
    plan_start = datetime.strptime(derived["plan_start_date"], "%Y-%m-%d")
    race_date = datetime.strptime(derived["race_date"], "%Y-%m-%d")
    plan_duration = plan_config["plan_duration"]
    athlete_name = profile.get("name", "Athlete")
    athlete_email = profile.get("email", "")
    race_name = derived.get("race_name", "Your Race")

    # Find first recovery week
    weeks = plan_config.get("template", {}).get("weeks", [])
    first_recovery_week = None
    for w in weeks:
        if w.get("volume_percent", 100) <= 65:
            first_recovery_week = w.get("week_number", 3)
            break
    if first_recovery_week is None:
        first_recovery_week = 3  # fallback

    # Build phase starts at ~50% of plan
    build_start_week = int(plan_duration * 0.5) + 1
    midpoint_week = plan_duration // 2

    touchpoints = []
    for tp_def in TOUCHPOINT_TYPES:
        send_date = _compute_send_date(
            tp_def,
            plan_start=plan_start,
            race_date=race_date,
            plan_duration=plan_duration,
            first_recovery_week=first_recovery_week,
            build_start_week=build_start_week,
            midpoint_week=midpoint_week,
        )
        if send_date is None:
            continue

        subject = tp_def["subject"].format(
            race_name=race_name,
            athlete_name=athlete_name,
        )

        touchpoints.append({
            "id": tp_def["id"],
            "send_date": send_date.strftime("%Y-%m-%d"),
            "subject": subject,
            "template": tp_def["template"],
            "sent": False,
            "sent_at": None,
        })

    # Sort chronologically
    touchpoints.sort(key=lambda t: t["send_date"])

    result = {
        "athlete": athlete_name,
        "email": athlete_email,
        "race_name": race_name,
        "race_date": derived["race_date"],
        "plan_start": derived["plan_start_date"],
        "plan_duration_weeks": plan_duration,
        "touchpoints": touchpoints,
        "generated_at": datetime.now().isoformat(),
    }

    with open(athlete_dir / "touchpoints.json", "w") as f:
        json.dump(result, f, indent=2)

    return result


def _compute_send_date(
    tp_def: Dict,
    plan_start: datetime,
    race_date: datetime,
    plan_duration: int,
    first_recovery_week: int,
    build_start_week: int,
    midpoint_week: int,
) -> Optional[datetime]:
    """Compute the send date for a touchpoint based on its offset type."""
    offset_type = tp_def["offset_type"]
    offset_days = tp_def["offset_days"]

    if offset_type == "plan_start":
        return plan_start + timedelta(days=offset_days)

    elif offset_type == "race_date":
        return race_date + timedelta(days=offset_days)

    elif offset_type == "first_recovery_week":
        # Monday of the first recovery week
        return plan_start + timedelta(weeks=first_recovery_week - 1)

    elif offset_type == "midpoint":
        return plan_start + timedelta(weeks=midpoint_week - 1)

    elif offset_type == "build_start":
        return plan_start + timedelta(weeks=build_start_week - 1)

    return None
