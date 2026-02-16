"""Email template preview with real or sample data from Supabase."""

import json
from pathlib import Path

from mission_control.config import TEMPLATES_DIR
from mission_control import supabase_client as db


def list_templates() -> list[dict]:
    """List all email templates in templates/emails/."""
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates

    for f in sorted(TEMPLATES_DIR.iterdir()):
        if f.suffix == ".html":
            name = f.stem
            category = _categorize_template(name)
            templates.append({
                "name": name,
                "filename": f.name,
                "category": category,
                "path": str(f),
            })

    return templates


def preview_template(template_name: str, athlete_slug: str | None = None) -> dict:
    """Preview a template rendered with real or sample athlete data."""
    template_path = TEMPLATES_DIR / f"{template_name}.html"
    if not template_path.exists():
        return {"html": f"<p>Template not found: {template_name}.html</p>",
                "template_name": template_name, "athlete_name": "N/A"}

    html = template_path.read_text()

    # Get athlete data
    athlete = None
    if athlete_slug:
        athlete = db.get_athlete(athlete_slug)
    if not athlete:
        athletes = db.select("gg_athletes", columns="*", limit=1)
        athlete = athletes[0] if athletes else None

    if athlete:
        intake = athlete.get("intake_json") or {}
        if isinstance(intake, str):
            intake = json.loads(intake)

        replacements = {
            "{athlete_name}": intake.get("name", athlete.get("name", "Sample Athlete")),
            "{race_name}": athlete.get("race_name", "Sample Race"),
            "{race_date}": str(athlete.get("race_date", "2026-07-04")),
            "{plan_duration}": str(athlete.get("plan_weeks", 12)),
            "{week_number}": "4",
        }
        athlete_name = athlete["name"]
    else:
        replacements = {
            "{athlete_name}": "Sample Athlete",
            "{race_name}": "Sample Race",
            "{race_date}": "2026-07-04",
            "{plan_duration}": "12",
            "{week_number}": "4",
        }
        athlete_name = "Sample Data"

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    return {"html": html, "template_name": template_name, "athlete_name": athlete_name}


def _categorize_template(name: str) -> str:
    """Categorize template by name pattern."""
    if name.startswith("post_race"):
        return "post_race"
    if name.startswith("race_") or name in ("taper_start", "equipment_check"):
        return "race_prep"
    if name in ("account_connect", "week_1_welcome", "week_2_checkin"):
        return "onboarding"
    if name in ("recovery_week", "first_recovery"):
        return "recovery"
    if name in ("mid_plan", "build_phase_start", "ftp_reminder"):
        return "training"
    return "retention"
