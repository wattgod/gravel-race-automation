"""
Step 1: Validate Intake

Validates raw questionnaire data before processing.
Adapted from athlete-profiles/athletes/scripts/validate_submission.py
"""

import json
import re
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Lead time bounds
MIN_LEAD_WEEKS = 6    # Can't build a meaningful plan in less than 6 weeks
MAX_LEAD_WEEKS = 78   # 1.5 years out — beyond this, date is likely wrong

VALID_HOURS = ["3-5", "5-7", "7-10", "10-12", "12-15", "15+"]

DISPOSABLE_EMAIL_PROVIDERS = [
    "10minutemail.com",
    "guerrillamail.com",
    "tempmail.com",
    "mailinator.com",
    "throwaway.email",
    "getnada.com",
    "mohmal.com",
    "fakeinbox.com",
    "trashmail.com",
    "maildrop.cc",
]


def validate_intake(intake: Dict) -> Dict:
    """
    Validate intake data. Returns the intake dict (possibly normalized)
    or raises ValueError with all validation errors.
    """
    errors: List[str] = []

    # Required fields
    if not intake.get("name"):
        errors.append("Name is required")

    # Email
    email = intake.get("email", "")
    if not email:
        errors.append("Email is required")
    elif not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
        errors.append(f"Invalid email format: {email}")
    elif email.split("@")[1].lower() in DISPOSABLE_EMAIL_PROVIDERS:
        errors.append("Disposable email providers are not allowed")

    # Races
    races = intake.get("races", [])
    if not races:
        errors.append("At least one race is required")
    else:
        today = date.today()
        for i, race in enumerate(races):
            if not race.get("name"):
                errors.append(f"Race {i+1}: name is required")
            if not race.get("date"):
                errors.append(f"Race {i+1}: date is required")
            else:
                try:
                    race_date = datetime.strptime(race["date"], "%Y-%m-%d").date()
                    if race_date <= today:
                        errors.append(
                            f"Race {i+1}: date {race['date']} is in the past"
                        )
                    else:
                        # Lead time validation
                        weeks_until = (race_date - today).days / 7
                        if weeks_until < MIN_LEAD_WEEKS:
                            errors.append(
                                f"Race {i+1}: date {race['date']} is only "
                                f"{weeks_until:.0f} weeks away (minimum {MIN_LEAD_WEEKS} weeks "
                                f"needed to build a meaningful plan)"
                            )
                        elif weeks_until > MAX_LEAD_WEEKS:
                            errors.append(
                                f"Race {i+1}: date {race['date']} is "
                                f"{weeks_until:.0f} weeks away — please verify this date "
                                f"(max {MAX_LEAD_WEEKS} weeks)"
                            )
                        # Enrich with day of week
                        race["race_day_of_week"] = race_date.strftime("%A")
                except ValueError:
                    errors.append(
                        f"Race {i+1}: invalid date format '{race['date']}' (use YYYY-MM-DD)"
                    )
            if not race.get("distance_miles"):
                errors.append(f"Race {i+1}: distance_miles is required")

    # Weekly hours
    weekly_hours = intake.get("weekly_hours", "")
    if not weekly_hours:
        errors.append("weekly_hours is required")
    elif weekly_hours not in VALID_HOURS:
        errors.append(f"Invalid weekly_hours: '{weekly_hours}' (valid: {VALID_HOURS})")

    # Age
    age = intake.get("age")
    if age is not None:
        if not isinstance(age, int) or age < 16 or age > 85:
            errors.append(f"Age must be between 16 and 85, got: {age}")

    # Honeypot check
    if intake.get("_honeypot"):
        errors.append("Bot detected (honeypot field filled)")

    if errors:
        raise ValueError("Intake validation failed:\n  - " + "\n  - ".join(errors))

    # Normalize: ensure off_days is a list
    if "off_days" not in intake:
        intake["off_days"] = []
    if isinstance(intake["off_days"], str):
        intake["off_days"] = [intake["off_days"]]

    # Normalize: ensure long_ride_days / interval_days are lists
    for field in ["long_ride_days", "interval_days"]:
        if field not in intake:
            intake[field] = []
        if isinstance(intake[field], str):
            intake[field] = [intake[field]]

    return intake


def cross_reference_race_date(
    race_name: str, race_date_str: str, base_dir: Path
) -> Dict:
    """
    Cross-reference an intake race date against the race-data/ database.

    Returns dict with:
        - matched: bool — whether a matching race was found
        - race_data_file: str — filename if matched
        - date_specific: str — raw date_specific value from race data
        - parsed_date: str — parsed YYYY-MM-DD if possible, else None
        - date_match: bool — whether the dates match
        - warning: str — human-readable warning if dates don't match
        - day_of_week: str — day of week for the intake date
    """
    result = {
        "matched": False,
        "race_data_file": None,
        "date_specific": None,
        "parsed_date": None,
        "date_match": None,
        "warning": None,
        "day_of_week": None,
    }

    # Parse intake date
    try:
        rd = datetime.strptime(race_date_str, "%Y-%m-%d").date()
        result["day_of_week"] = rd.strftime("%A")
    except ValueError:
        result["warning"] = f"Cannot parse intake date: {race_date_str}"
        return result

    # Search race-data/ directory for matching race name
    race_data_dir = base_dir / "race-data"
    if not race_data_dir.exists():
        return result

    name_lower = race_name.lower().strip()
    for json_file in sorted(race_data_dir.glob("*.json")):
        try:
            with open(json_file) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        # Check both top-level and nested structures
        race_obj = data.get("race", data)
        file_name = race_obj.get("name", "") or race_obj.get("display_name", "")
        if file_name.lower().strip() != name_lower:
            continue

        # Found a match
        result["matched"] = True
        result["race_data_file"] = json_file.name

        vitals = race_obj.get("vitals", {})
        date_specific = vitals.get("date_specific", "")
        result["date_specific"] = date_specific

        if not date_specific:
            break

        # Try to parse date_specific (format: "YYYY: Month Day" or "YYYY: Month Day-Day")
        parsed = _parse_date_specific(date_specific, rd.year)
        if parsed:
            result["parsed_date"] = parsed.isoformat()
            result["date_match"] = (parsed == rd)
            if not result["date_match"]:
                result["warning"] = (
                    f"Date mismatch: intake says {race_date_str} "
                    f"({result['day_of_week']}), but race database says "
                    f"\"{date_specific}\" → {parsed.isoformat()} "
                    f"({parsed.strftime('%A')}). Please verify."
                )
        break

    return result


def _parse_date_specific(date_specific: str, target_year: int) -> Optional[date]:
    """
    Parse a date_specific string like "2026: June 28" into a date object.

    Handles:
        - "2026: June 28" → date(2026, 6, 28)
        - "2026: May 19-23" → date(2026, 5, 19) (first day of range)
        - "2026: February 6-15" → date(2026, 2, 6)
        - Returns None for unparseable strings like "Check USA Cycling for date"
    """
    # Extract "YYYY: rest" pattern
    m = re.match(r"(\d{4}):\s*(.+)", date_specific.strip())
    if not m:
        return None

    year_str, date_part = m.group(1), m.group(2).strip()
    year = int(year_str)

    # Strip trailing range (e.g., "June 28-30" → "June 28", "May 6-15" → "May 6")
    date_part = re.sub(r"-\d+.*$", "", date_part).strip()

    # Strip parenthetical notes like "(overnight)"
    date_part = re.sub(r"\(.*?\)", "", date_part).strip()

    # Strip qualifiers like "Early", "Late", "Mid"
    date_part = re.sub(r"^(Early|Late|Mid)\s+", "", date_part, flags=re.IGNORECASE).strip()

    # Try parsing "Month Day"
    for fmt in ["%B %d", "%b %d"]:
        try:
            parsed = datetime.strptime(date_part, fmt).date()
            return parsed.replace(year=year)
        except ValueError:
            continue

    return None
