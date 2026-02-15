"""
Step 11: Generate Full-Lifecycle Touchpoint Schedule

Creates touchpoints.json in the athlete directory with a comprehensive
schedule of automated check-in emails covering the entire customer lifecycle:

  Onboarding   → account connection, week 1 welcome, week 2 check-in
  Training     → FTP test reminders, mid-plan check, build phase start
  Recovery     → reminder for EVERY recovery week (not just the first)
  Race Prep    → equipment check, taper start, race month/week/eve/morning
  Post-Race    → debrief, NPS survey, referral ask, what's next
  Retention    → 3-month re-engagement

All dates are deterministic — computed from plan_start_date, race_date,
recovery_weeks, and ftp_test_weeks. No AI content. Templates are pre-written.

Touchpoints are sent externally via scripts/send_touchpoint.py.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional


# ── Categories ──────────────────────────────────────────────

CATEGORIES = {
    "onboarding": "First 2 weeks — getting started",
    "training": "Ongoing training guidance",
    "recovery": "Recovery week reminders",
    "race_prep": "Race preparation (final 6 weeks)",
    "post_race": "Post-race follow-up",
    "retention": "Long-term re-engagement",
}


# ── Static Touchpoint Definitions ────────────────────────────
# These are always generated for every athlete. Dynamic touchpoints
# (recovery weeks, FTP tests) are added programmatically below.

STATIC_TOUCHPOINTS = [
    # ── Onboarding ──
    {
        "id": "account_connect",
        "offset_type": "plan_start",
        "offset_days": 0,
        "subject": "Connect your training accounts",
        "template": "account_connect",
        "category": "onboarding",
    },
    {
        "id": "week_1_welcome",
        "offset_type": "plan_start",
        "offset_days": 2,
        "subject": "Your first week — here's what to focus on",
        "template": "week_1_welcome",
        "category": "onboarding",
    },
    {
        "id": "week_2_checkin",
        "offset_type": "plan_start",
        "offset_days": 7,
        "subject": "How's week 1 going?",
        "template": "week_2_checkin",
        "category": "onboarding",
    },
    # ── Training ──
    {
        "id": "mid_plan",
        "offset_type": "midpoint",
        "offset_days": 0,
        "subject": "Halfway there — progress check",
        "template": "mid_plan",
        "category": "training",
    },
    {
        "id": "build_phase_start",
        "offset_type": "build_start",
        "offset_days": 0,
        "subject": "Intensity increases this week",
        "template": "build_phase_start",
        "category": "training",
    },
    # ── Race Prep ──
    {
        "id": "equipment_check",
        "offset_type": "race_date",
        "offset_days": -42,
        "subject": "Equipment check — 6 weeks to go",
        "template": "equipment_check",
        "category": "race_prep",
    },
    {
        "id": "race_month",
        "offset_type": "race_date",
        "offset_days": -28,
        "subject": "Race month — the work is done",
        "template": "race_month",
        "category": "race_prep",
    },
    {
        "id": "taper_start",
        "offset_type": "race_date",
        "offset_days": -14,
        "subject": "Taper begins — trust your fitness",
        "template": "taper_start",
        "category": "race_prep",
    },
    {
        "id": "race_week",
        "offset_type": "race_date",
        "offset_days": -7,
        "subject": "Race week — {race_name}",
        "template": "race_week",
        "category": "race_prep",
    },
    {
        "id": "race_day_eve",
        "offset_type": "race_date",
        "offset_days": -1,
        "subject": "Tomorrow is the day — {race_name}",
        "template": "race_day_eve",
        "category": "race_prep",
    },
    {
        "id": "race_day_morning",
        "offset_type": "race_date",
        "offset_days": 0,
        "subject": "Go time. You're ready.",
        "template": "race_day_morning",
        "category": "race_prep",
    },
    # ── Post-Race ──
    {
        "id": "post_race_3_days",
        "offset_type": "race_date",
        "offset_days": 3,
        "subject": "How'd it go?",
        "template": "post_race_3_days",
        "category": "post_race",
    },
    {
        "id": "post_race_nps",
        "offset_type": "race_date",
        "offset_days": 7,
        "subject": "Quick question about your training plan",
        "template": "post_race_nps",
        "category": "post_race",
    },
    {
        "id": "post_race_2_weeks",
        "offset_type": "race_date",
        "offset_days": 14,
        "subject": "What's next?",
        "template": "post_race_2_weeks",
        "category": "post_race",
    },
    # ── Retention ──
    {
        "id": "post_race_referral",
        "offset_type": "race_date",
        "offset_days": 10,
        "subject": "Know someone training for gravel?",
        "template": "post_race_referral",
        "category": "retention",
    },
    {
        "id": "post_race_3_months",
        "offset_type": "race_date",
        "offset_days": 90,
        "subject": "It's been 3 months — time to ride again?",
        "template": "post_race_3_months",
        "category": "retention",
    },
]


def _find_recovery_weeks(weeks: list, plan_duration: int) -> List[int]:
    """Identify recovery week numbers from template weeks.

    Recovery = volume_percent <= 65 AND not in taper/race phase.
    Also catches cadence-enforced recovery weeks by focus text.
    """
    recovery = []
    for w in weeks:
        wn = w["week_number"]
        focus = w.get("focus", "").lower()
        vol = w.get("volume_percent", 100)

        # Explicit recovery in focus text
        if "recovery" in focus:
            recovery.append(wn)
            continue

        # Low volume but NOT taper/race
        if (
            vol <= 65
            and wn <= plan_duration - 4
            and "taper" not in focus
            and "race" not in focus
        ):
            recovery.append(wn)

    return sorted(recovery)


def _generate_recovery_touchpoints(
    recovery_weeks: List[int],
    plan_start: datetime,
) -> List[Dict]:
    """Generate a touchpoint for each recovery week."""
    touchpoints = []
    for i, wn in enumerate(recovery_weeks):
        recovery_num = i + 1
        total = len(recovery_weeks)

        tp = {
            "id": f"recovery_week_{wn}",
            "send_date": (plan_start + timedelta(weeks=wn - 1)).strftime("%Y-%m-%d"),
            "subject": f"Recovery week {recovery_num} of {total} — trust the process",
            "template": "first_recovery" if i == 0 else "recovery_week",
            "category": "recovery",
            "template_data": {
                "week_number": wn,
                "recovery_number": recovery_num,
                "total_recovery_weeks": total,
            },
            "sent": False,
            "sent_at": None,
        }
        touchpoints.append(tp)

    return touchpoints


def _generate_ftp_touchpoints(
    ftp_test_weeks: List[int],
    plan_start: datetime,
) -> List[Dict]:
    """Generate an FTP test reminder for each test week (sent Friday before)."""
    touchpoints = []
    for i, wn in enumerate(ftp_test_weeks):
        # Send on Friday before the test week (2 days before Monday)
        test_week_monday = plan_start + timedelta(weeks=wn - 1)
        send_date = test_week_monday - timedelta(days=2)

        # Don't send FTP reminder before the plan starts
        if send_date < plan_start:
            send_date = plan_start

        tp = {
            "id": f"ftp_reminder_{wn}",
            "send_date": send_date.strftime("%Y-%m-%d"),
            "subject": f"FTP test this week — week {wn}",
            "template": "ftp_reminder",
            "category": "training",
            "template_data": {
                "week_number": wn,
                "test_number": i + 1,
                "total_tests": len(ftp_test_weeks),
            },
            "sent": False,
            "sent_at": None,
        }
        touchpoints.append(tp)

    return touchpoints


def generate_touchpoints(
    profile: Dict,
    derived: Dict,
    plan_config: Dict,
    athlete_dir: Path,
) -> Dict:
    """Generate touchpoints.json schedule in the athlete directory.

    Produces a comprehensive lifecycle touchpoint schedule:
    - Static touchpoints (onboarding, training, race prep, post-race, retention)
    - Dynamic recovery week reminders for ALL recovery weeks
    - Dynamic FTP test reminders for all scheduled FTP tests
    """
    plan_start = datetime.strptime(derived["plan_start_date"], "%Y-%m-%d")
    race_date = datetime.strptime(derived["race_date"], "%Y-%m-%d")
    plan_duration = plan_config["plan_duration"]
    athlete_name = profile.get("name", "Athlete")
    athlete_email = profile.get("email", "")
    race_name = derived.get("race_name", "Your Race")

    # Extract recovery weeks from template
    weeks = plan_config.get("template", {}).get("weeks", [])
    recovery_weeks = _find_recovery_weeks(weeks, plan_duration)

    # FTP test weeks from step 5
    ftp_test_weeks = plan_config.get("ftp_test_weeks", [1])

    # Build phase starts at ~50% of plan
    build_start_week = int(plan_duration * 0.5) + 1
    midpoint_week = plan_duration // 2

    touchpoints = []

    # ── Static touchpoints ──
    for tp_def in STATIC_TOUCHPOINTS:
        send_date = _compute_send_date(
            tp_def,
            plan_start=plan_start,
            race_date=race_date,
            plan_duration=plan_duration,
            build_start_week=build_start_week,
            midpoint_week=midpoint_week,
        )
        if send_date is None:
            continue

        # Skip if date is before plan start (e.g., equipment_check for short plans)
        if send_date < plan_start - timedelta(days=1):
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
            "category": tp_def["category"],
            "sent": False,
            "sent_at": None,
        })

    # ── Dynamic: Recovery week reminders ──
    touchpoints.extend(
        _generate_recovery_touchpoints(recovery_weeks, plan_start)
    )

    # ── Dynamic: FTP test reminders ──
    touchpoints.extend(
        _generate_ftp_touchpoints(ftp_test_weeks, plan_start)
    )

    # Sort chronologically, break ties by category priority
    category_order = {
        "onboarding": 0, "training": 1, "recovery": 2,
        "race_prep": 3, "post_race": 4, "retention": 5,
    }
    touchpoints.sort(key=lambda t: (
        t["send_date"],
        category_order.get(t.get("category", ""), 9),
    ))

    result = {
        "athlete": athlete_name,
        "email": athlete_email,
        "race_name": race_name,
        "race_date": derived["race_date"],
        "plan_start": derived["plan_start_date"],
        "plan_duration_weeks": plan_duration,
        "recovery_weeks": recovery_weeks,
        "ftp_test_weeks": ftp_test_weeks,
        "touchpoints": touchpoints,
        "categories": CATEGORIES,
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
    build_start_week: int,
    midpoint_week: int,
) -> Optional[datetime]:
    """Compute the send date for a static touchpoint based on its offset type."""
    offset_type = tp_def["offset_type"]
    offset_days = tp_def["offset_days"]

    if offset_type == "plan_start":
        return plan_start + timedelta(days=offset_days)

    elif offset_type == "race_date":
        return race_date + timedelta(days=offset_days)

    elif offset_type == "midpoint":
        return plan_start + timedelta(weeks=midpoint_week - 1)

    elif offset_type == "build_start":
        return plan_start + timedelta(weeks=build_start_week - 1)

    return None
