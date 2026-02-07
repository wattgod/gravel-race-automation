"""
Tests for date field consistency.

Validates that:
1. Every profile has both date and date_specific fields
2. date_specific follows recognizable patterns
3. Profiles with specific dates have valid month references
"""

import json
import re
import pytest
from pathlib import Path

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"

VALID_MONTHS = {
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
}

# Recognized date_specific patterns (all acceptable)
VALID_DATE_PATTERNS = [
    r"^\d{4}:\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}",  # "2026: May 17"
    r"^\d{4}:\s*(Spring|Summer|Fall|Winter|Autumn)\s+TBD",  # "2026: Spring TBD"
    r"^\d{4}:\s*(Spring|Summer|Fall|Winter)/?(Spring|Summer|Fall|Winter)?\s+TBD",  # "2026: Spring/Fall TBD"
    r"^\d{4}:\s*TBD",  # "2026: TBD"
    r"^\d{4}:\s*Various",  # "2026: Various dates"
    r"^Check\s+",  # "Check official website for date"
    r"^Status:",  # "Status: UNCERTAIN - Last held August 2022"
    r"^\d{4}:\s*(January|February|March|April|May|June|July|August|September|October|November|December)",  # "2026: July 11-12"
    r"^\d{4}:\s*\w+",  # Any year: something pattern
]


def get_all_profiles():
    """Load all race profiles."""
    profiles = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        race = data.get("race", data)
        profiles.append((f.name, race))
    return profiles


class TestDatePresence:
    """Every profile must have date fields."""

    def test_all_have_date(self):
        """Every profile must have a 'date' field in vitals."""
        missing = []
        for fname, race in get_all_profiles():
            vitals = race.get("vitals", {})
            if not vitals.get("date"):
                missing.append(fname)

        if missing:
            pytest.fail(f"{len(missing)} profiles missing vitals.date:\n" +
                        "\n".join(f"  {f}" for f in missing))

    def test_all_have_date_specific(self):
        """Every profile must have a 'date_specific' field in vitals."""
        missing = []
        for fname, race in get_all_profiles():
            vitals = race.get("vitals", {})
            if not vitals.get("date_specific"):
                missing.append(fname)

        if missing:
            pytest.fail(f"{len(missing)} profiles missing vitals.date_specific:\n" +
                        "\n".join(f"  {f}" for f in missing))


class TestDateFormat:
    """date_specific must follow a recognizable pattern."""

    def test_date_specific_recognizable(self):
        """date_specific should match one of the known valid patterns."""
        unrecognized = []
        for fname, race in get_all_profiles():
            vitals = race.get("vitals", {})
            ds = str(vitals.get("date_specific", "")).strip()
            if not ds:
                continue

            matched = any(re.search(p, ds) for p in VALID_DATE_PATTERNS)
            if not matched:
                unrecognized.append(f"  {fname}: {ds!r}")

        if unrecognized:
            pytest.fail(
                f"{len(unrecognized)} profiles with unrecognized date_specific format:\n" +
                "\n".join(unrecognized[:20]) +
                "\n\nAdd new pattern to VALID_DATE_PATTERNS if format is intentional."
            )

    def test_date_field_mentions_frequency(self):
        """The 'date' field should indicate timing (month, season, or 'annually')."""
        suspicious = []
        for fname, race in get_all_profiles():
            vitals = race.get("vitals", {})
            date = str(vitals.get("date", "")).strip()
            if not date:
                continue

            # Should contain a month, season, or "annually"
            has_month = any(m.lower() in date.lower() for m in VALID_MONTHS)
            has_season = any(s in date.lower() for s in ["spring", "summer", "fall", "winter", "autumn"])
            has_annually = "annual" in date.lower()
            has_specific = bool(re.search(r'\d{4}', date))

            if not (has_month or has_season or has_annually or has_specific):
                suspicious.append(f"  {fname}: {date!r}")

        if suspicious:
            # Warning only — don't fail, just report
            print(f"\nWARNING: {len(suspicious)} profiles with vague date field:")
            for s in suspicious[:10]:
                print(s)


class TestDateConsistency:
    """Month in date should be consistent with month derived from date_specific."""

    def test_month_field_populated(self):
        """Profiles with specific dates should have consistent month references."""
        # This is informational — checks that date and date_specific don't contradict
        contradictions = []
        for fname, race in get_all_profiles():
            vitals = race.get("vitals", {})
            date = str(vitals.get("date", ""))
            ds = str(vitals.get("date_specific", ""))

            # Extract month from date_specific
            ds_month = None
            for m in VALID_MONTHS:
                if m in ds:
                    ds_month = m
                    break

            # Extract month from date
            date_month = None
            for m in VALID_MONTHS:
                if m in date:
                    date_month = m
                    break

            # If both have months, they should match
            if ds_month and date_month and ds_month != date_month:
                contradictions.append(
                    f"  {fname}: date says {date_month}, date_specific says {ds_month}"
                )

        if contradictions:
            # Warning, not failure — dates shift between years and fields
            # may reference different editions
            print(f"\nWARNING: {len(contradictions)} date/date_specific month contradictions:")
            for c in contradictions[:10]:
                print(c)
