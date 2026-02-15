"""
Quality Gates — All 10 gate assertions in one file.

Each gate function raises AssertionError if the gate fails.
The pipeline HALTS on any gate failure. No partial delivery.
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date
from pathlib import Path
from typing import Dict


# ── Gate 1: Intake Validation ────────────────────────────────

def gate_1_intake(intake: Dict):
    """Validate intake data passed validation step."""
    assert intake.get("name"), "Gate 1: Name is required"
    assert "@" in intake.get("email", ""), "Gate 1: Valid email required"
    assert intake.get("races"), "Gate 1: At least one race required"

    today = date.today()
    for i, race in enumerate(intake["races"]):
        assert race.get("name"), f"Gate 1: Race {i+1} name required"
        assert race.get("date"), f"Gate 1: Race {i+1} date required"

        # Date sanity: must be future, must have reasonable lead time
        try:
            race_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
            assert race_date > today, (
                f"Gate 1: Race {i+1} date {race['date']} is in the past"
            )
            weeks_until = (race_date - today).days / 7
            assert weeks_until >= 6, (
                f"Gate 1: Race {i+1} is only {weeks_until:.0f} weeks away "
                f"(need >= 6 weeks for a meaningful plan)"
            )
            # Day of week should be enriched by step_01
            assert race.get("race_day_of_week"), (
                f"Gate 1: Race {i+1} missing race_day_of_week enrichment"
            )
        except ValueError:
            raise AssertionError(
                f"Gate 1: Race {i+1} has unparseable date: {race['date']}"
            )

    assert intake.get("weekly_hours"), "Gate 1: weekly_hours required"


# ── Gate 2: Profile Schema ──────────────────────────────────

REQUIRED_PROFILE_SECTIONS = [
    "name",
    "email",
    "demographics",
    "race_calendar",
    "fitness",
    "schedule",
    "strength",
    "health",
]


def gate_2_profile(profile: Dict):
    """Validate profile has all required sections."""
    assert profile.get("name"), "Gate 2: Profile must have name"
    assert profile.get("race_calendar"), "Gate 2: Must have at least one race"
    assert profile.get("schedule", {}).get("weekly_hours"), "Gate 2: Must have weekly hours"

    for section in REQUIRED_PROFILE_SECTIONS:
        assert section in profile, f"Gate 2: Missing profile section: {section}"


# ── Gate 3: Classification Coherence ─────────────────────────

VALID_TIERS = ["time_crunched", "finisher", "compete", "podium"]
VALID_LEVELS = ["beginner", "intermediate", "advanced", "masters"]

TIER_VALID_HOURS = {
    "time_crunched": ["3-5"],
    "finisher": ["5-7", "7-10"],
    "compete": ["10-12", "12-15"],
    "podium": ["15+"],
}


def gate_3_classification(derived: Dict, profile: Dict):
    """Validate tier + level + weeks are coherent."""
    tier = derived["tier"]
    level = derived["level"]
    plan_weeks = derived["plan_weeks"]
    weekly_hours = derived["weekly_hours"]

    assert tier in VALID_TIERS, f"Gate 3: Invalid tier: {tier}"
    assert level in VALID_LEVELS, f"Gate 3: Invalid level: {level}"
    assert 6 <= plan_weeks <= 24, f"Gate 3: plan_weeks {plan_weeks} out of range [6, 24]"
    assert 6 <= derived["plan_duration"] <= 24, (
        f"Gate 3: plan_duration {derived['plan_duration']} out of range [6, 24]"
    )

    # Verify tier matches weekly hours
    valid_hours = TIER_VALID_HOURS.get(tier, [])
    assert weekly_hours in valid_hours, (
        f"Gate 3: Tier {tier} expects hours in {valid_hours}, got {weekly_hours}"
    )


# ── Gate 4: Schedule Sanity ──────────────────────────────────

def gate_4_schedule(schedule: Dict, intake: Dict):
    """Validate schedule has enough training days and respects off days."""
    days = schedule.get("days", {})
    training_days = [d for d, info in days.items() if info["session"] != "rest"]
    assert len(training_days) >= 3, (
        f"Gate 4: Only {len(training_days)} training days (need >= 3)"
    )

    # Verify off days are respected
    off_days = [d.lower() for d in intake.get("off_days", [])]
    for off_day in off_days:
        assert days.get(off_day, {}).get("session") == "rest", (
            f"Gate 4: {off_day} should be rest but is {days.get(off_day, {}).get('session')}"
        )

    # Must have at least one long ride day
    long_days = [d for d, info in days.items() if info["session"] == "long_ride"]
    assert long_days, "Gate 4: No long ride day in schedule"


# ── Gate 5: Template Selection ───────────────────────────────

def gate_5_template(plan_config: Dict, derived: Dict):
    """Validate template was loaded and has correct duration."""
    template = plan_config["template"]
    plan_duration = plan_config["plan_duration"]

    assert template, "Gate 5: Template is empty"
    assert "weeks" in template, "Gate 5: Template has no 'weeks' key"

    actual_weeks = len(template["weeks"])
    assert actual_weeks == plan_duration, (
        f"Gate 5: Template has {actual_weeks} weeks but plan_duration is {plan_duration}"
    )


# ── Gate 6: Workout Files ───────────────────────────────────

def gate_6_workouts(workouts_dir: Path, derived: Dict):
    """Validate ZWO files: count, valid XML, sane power targets."""
    plan_duration = derived["plan_duration"]
    zwo_files = list(workouts_dir.glob("*.zwo"))

    # Expect 7 ZWO files per week, minus up to 6 for partial first week
    # (plan may start mid-week, so W01 has fewer days)
    min_expected = plan_duration * 7 - 6
    assert len(zwo_files) >= min_expected, (
        f"Gate 6: Too few ZWO files: {len(zwo_files)} (expected >= {min_expected} for {plan_duration} weeks)"
    )

    # Verify strength workouts exist
    strength_files = [f for f in zwo_files if "Strength" in f.name or "strength" in f.name]
    assert len(strength_files) > 0, "Gate 6: No strength workout ZWO files found"

    # Verify rest/recovery day files exist
    rest_files = [f for f in zwo_files if "Rest" in f.name or "Off" in f.name or "Recovery_Day" in f.name]
    assert len(rest_files) > 0, "Gate 6: No rest/off-day ZWO files found"

    # Verify filename format: W01_1Mon_Feb02_Type.zwo (sortable, with dates)
    name_pattern = re.compile(
        r"^W\d{2}_[1-7](Mon|Tue|Wed|Thu|Fri|Sat|Sun)_[A-Z][a-z]{2}\d{2}_.+\.zwo$"
    )
    for zwo in zwo_files:
        if "Race_Day" in zwo.name:
            continue  # Race day has a different format
        assert name_pattern.match(zwo.name), (
            f"Gate 6: Bad filename format '{zwo.name}'. "
            f"Expected W{{week}}_{{daynum}}{{Day}}_{{MmmDD}}_{{Type}}.zwo "
            f"(e.g. W01_1Mon_Feb02_Strength_Base.zwo)"
        )

    for zwo in zwo_files:
        try:
            tree = ET.parse(zwo)
        except ET.ParseError as e:
            raise AssertionError(f"Gate 6: Invalid XML in {zwo.name}: {e}")

        root = tree.getroot()
        assert root.tag == "workout_file", (
            f"Gate 6: Invalid ZWO root tag '{root.tag}' in {zwo.name}"
        )

        workout = root.find("workout")
        assert workout is not None, f"Gate 6: No <workout> element in {zwo.name}"

        # Power target sanity check
        for elem in workout.iter():
            for attr in ["Power", "PowerLow", "PowerHigh", "OnPower", "OffPower"]:
                if attr in elem.attrib:
                    try:
                        power = float(elem.attrib[attr])
                    except ValueError:
                        continue
                    assert 0.3 <= power <= 2.0, (
                        f"Gate 6: Insane power target {power} in {zwo.name} ({attr})"
                    )

            # Duration must be positive
            if "Duration" in elem.attrib:
                try:
                    dur = int(elem.attrib["Duration"])
                except ValueError:
                    continue
                assert dur > 0, f"Gate 6: Zero/negative duration in {zwo.name}"


# ── Gate 7: Guide Quality ───────────────────────────────────

def gate_7_guide(guide_path: Path, intake: Dict, derived: Dict):
    """
    The most critical gate. Validates:
    - No unreplaced {{placeholders}}
    - No null/undefined/None text
    - Distance matches athlete's race
    - Race name present
    - Required sections present
    - File size sanity
    """
    assert guide_path.exists(), f"Gate 7: Guide not created at {guide_path}"

    html = guide_path.read_text(encoding="utf-8")

    # No unreplaced placeholders
    placeholder = re.search(r"\{\{.*?\}\}", html)
    assert placeholder is None, (
        f"Gate 7: Unreplaced placeholder: {placeholder.group()}"
    )

    # No null/undefined/None text (standalone, not in CSS/code)
    for bad in ["undefined", "null", "None", "NaN"]:
        matches = re.findall(rf">\s*{bad}\s*<", html, re.IGNORECASE)
        assert not matches, f"Gate 7: Found '{bad}' in guide HTML"

    # Distance matches
    race_distance = derived.get("race_distance_miles")
    if race_distance:
        assert str(int(race_distance)) in html, (
            f"Gate 7: Guide doesn't mention {race_distance}mi distance"
        )

    # Race name present
    race_name = derived.get("race_name")
    if race_name:
        assert race_name in html, f"Gate 7: Guide doesn't mention race: {race_name}"

    # Methodology mentioned (tier is communicated through methodology name, not raw label)
    tier = derived["tier"]
    methodology_names = {
        "time_crunched": "hiit-focused",
        "finisher": "traditional pyramidal",
        "compete": "polarized",
        "podium": "high-volume polarized",
    }
    meth_name = methodology_names.get(tier, tier)
    assert meth_name in html.lower(), (
        f"Gate 7: Methodology for tier '{tier}' ('{meth_name}') not mentioned in guide"
    )

    # Required sections
    for section in ["training zones", "weekly structure", "race day"]:
        assert section in html.lower(), f"Gate 7: Missing section: '{section}'"

    # Required sections (all 14)
    required_sections = [
        "race profile", "non-negotiables", "training zones",
        "how adaptation works", "weekly structure", "phase progression",
        "week-by-week overview", "workout execution", "recovery protocol",
        "equipment checklist", "nutrition strategy", "mental preparation",
        "race week", "race day",
    ]
    for section in required_sections:
        assert section in html.lower(), f"Gate 7: Missing required section: '{section}'"

    # File size sanity — guide must be substantive (50KB+ per plan spec)
    size = len(html)
    assert size > 50_000, f"Gate 7: Guide too small: {size} bytes (need > 50KB)"
    assert size < 500_000, f"Gate 7: Guide too large: {size} bytes"


# ── Gate 8: PDF Quality ──────────────────────────────────────

def gate_8_pdf(pdf_path: Path):
    """Validate PDF was created and is reasonable size."""
    assert pdf_path.exists(), f"Gate 8: PDF not created at {pdf_path}"

    size = pdf_path.stat().st_size
    assert size > 10_000, f"Gate 8: PDF too small ({size} bytes) - likely empty/corrupt"
    assert size < 20_000_000, f"Gate 8: PDF too large ({size} bytes)"


# ── Gate 9: Deployment ───────────────────────────────────────

def gate_9_deploy(guide_url: str):
    """Validate guide is accessible at the deployed URL."""
    import requests

    response = requests.get(guide_url, timeout=30)
    assert response.status_code == 200, (
        f"Gate 9: Guide URL not accessible: {response.status_code} at {guide_url}"
    )


# ── Gate 10: Delivery ───────────────────────────────────────

def gate_10_deliver(receipt: Dict, intake: Dict):
    """Validate email was sent to correct address."""
    assert receipt.get("email_sent") is True, "Gate 10: Email not sent"
    assert receipt["recipient"] == intake["email"], (
        f"Gate 10: Wrong recipient: {receipt['recipient']} != {intake['email']}"
    )
    assert receipt.get("guide_url", "").startswith("http"), (
        f"Gate 10: Invalid guide URL: {receipt.get('guide_url')}"
    )


# ── Gate 6b: Methodology Document ─────────────────────────────

def gate_6b_methodology(athlete_dir: Path):
    """Validate methodology document was generated with required sections."""
    json_path = athlete_dir / "methodology.json"
    md_path = athlete_dir / "methodology.md"

    assert json_path.exists(), f"Gate 6b: methodology.json not created at {json_path}"
    assert md_path.exists(), f"Gate 6b: methodology.md not created at {md_path}"

    with open(json_path) as f:
        doc = json.load(f)

    required_sections = [
        "athlete_summary", "why_this_plan", "template_selection",
        "periodization", "scaling", "accommodations",
        "weekly_structure", "key_workouts_per_phase", "generated_at",
    ]
    for section in required_sections:
        assert section in doc, f"Gate 6b: Missing section: {section}"

    # Athlete summary must have key fields
    summary = doc["athlete_summary"]
    for field in ["name", "tier", "level", "weekly_hours", "plan_duration_weeks"]:
        assert summary.get(field), f"Gate 6b: Missing athlete_summary.{field}"

    # Periodization must list recovery weeks
    assert "recovery_weeks" in doc["periodization"], "Gate 6b: No recovery_weeks in periodization"

    # Why this plan must not be empty
    assert len(doc["why_this_plan"]) > 20, "Gate 6b: why_this_plan is too short"

    # Markdown must be substantive
    md_size = md_path.stat().st_size
    assert md_size > 500, f"Gate 6b: methodology.md too small ({md_size} bytes)"


# ── Gate 11: Touchpoints ──────────────────────────────────────

def gate_11_touchpoints(athlete_dir: Path, derived: Dict):
    """Validate touchpoints schedule was generated correctly."""
    tp_path = athlete_dir / "touchpoints.json"
    assert tp_path.exists(), f"Gate 11: touchpoints.json not created at {tp_path}"

    with open(tp_path) as f:
        tp_data = json.load(f)

    # Must have touchpoints array — expanded lifecycle requires >= 15
    touchpoints = tp_data.get("touchpoints", [])
    assert len(touchpoints) >= 15, (
        f"Gate 11: Only {len(touchpoints)} touchpoints (expected >= 15 for full lifecycle)"
    )

    # All touchpoints must have required fields
    for tp in touchpoints:
        for field in ["id", "send_date", "subject", "template", "category", "sent"]:
            assert field in tp, f"Gate 11: Touchpoint '{tp.get('id', '?')}' missing field: {field}"

    # Must have all 6 lifecycle categories represented
    categories = {tp["category"] for tp in touchpoints}
    required_categories = {"onboarding", "training", "recovery", "race_prep", "post_race", "retention"}
    missing = required_categories - categories
    assert not missing, f"Gate 11: Missing touchpoint categories: {missing}"

    # Must have dynamic recovery week touchpoints
    recovery_tps = [tp for tp in touchpoints if tp["id"].startswith("recovery_week_")]
    assert len(recovery_tps) >= 2, (
        f"Gate 11: Only {len(recovery_tps)} recovery week touchpoints (need >= 2)"
    )

    # Must have FTP test reminder touchpoints
    ftp_tps = [tp for tp in touchpoints if tp["id"].startswith("ftp_reminder_")]
    assert len(ftp_tps) >= 1, (
        f"Gate 11: No FTP test reminder touchpoints"
    )

    # Dates must be chronological
    dates = [tp["send_date"] for tp in touchpoints]
    assert dates == sorted(dates), "Gate 11: Touchpoint dates not chronological"

    # Race week touchpoint must be ~7 days before race
    race_date = derived.get("race_date")
    if race_date:
        race_week_tps = [tp for tp in touchpoints if tp["id"] == "race_week"]
        if race_week_tps:
            race_week_date = datetime.strptime(race_week_tps[0]["send_date"], "%Y-%m-%d")
            race_dt = datetime.strptime(race_date, "%Y-%m-%d")
            diff = (race_dt - race_week_date).days
            assert 5 <= diff <= 9, (
                f"Gate 11: Race week touchpoint is {diff} days before race (expected ~7)"
            )

    # Post-race touchpoints must be after race date
    if race_date:
        for tp in touchpoints:
            if tp["id"].startswith("post_race"):
                assert tp["send_date"] > race_date, (
                    f"Gate 11: Post-race touchpoint '{tp['id']}' on {tp['send_date']} "
                    f"is not after race date {race_date}"
                )

    # Athlete metadata
    assert tp_data.get("athlete"), "Gate 11: Missing athlete name"
    assert tp_data.get("email"), "Gate 11: Missing athlete email"

    # Recovery and FTP metadata
    assert "recovery_weeks" in tp_data, "Gate 11: Missing recovery_weeks in touchpoints.json"
    assert "ftp_test_weeks" in tp_data, "Gate 11: Missing ftp_test_weeks in touchpoints.json"
