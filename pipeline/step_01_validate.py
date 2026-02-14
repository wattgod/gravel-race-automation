"""
Step 1: Validate Intake

Validates raw questionnaire data before processing.
Adapted from athlete-profiles/athletes/scripts/validate_submission.py
"""

import re
from datetime import datetime, date
from typing import Dict, List

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
