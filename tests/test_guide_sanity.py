"""
Deterministic sanity checks for generated guides.

These tests validate that guide output matches questionnaire data.
No AI dependency — pure assertions against generated HTML.

Run against any athlete directory:
    pytest tests/test_guide_sanity.py -v

Each check catches a class of bug that previously shipped:
- Race day mismatch (guide said Saturday, race was Sunday)
- Hours exceeding stated availability (10-12hr weeks for 5-7hr athlete)
- Tier labels leaking into output (removed per design decision)
- Recovery nutrition not personalized (generic 30g vs body-weight calc)
- Stale "sweet spot" zone naming (should be "G Spot")
- Duration-scaled fueling regression (90g/hr for 8-hour effort)
"""

import re
from datetime import datetime
from pathlib import Path

import pytest
import yaml
import json


BASE_DIR = Path(__file__).parent.parent


def _load_athlete(athlete_dir: Path):
    """Load all athlete data files."""
    with open(athlete_dir / "profile.yaml") as f:
        profile = yaml.safe_load(f)
    with open(athlete_dir / "derived.yaml") as f:
        derived = yaml.safe_load(f)
    with open(athlete_dir / "plan_config.yaml") as f:
        plan_config = yaml.safe_load(f)
    with open(athlete_dir / "weekly_structure.yaml") as f:
        schedule = yaml.safe_load(f)
    guide_path = athlete_dir / "guide.html"
    html = guide_path.read_text(encoding="utf-8") if guide_path.exists() else ""
    return profile, derived, plan_config, schedule, html


def _parse_hours_range(hours_str: str):
    """Parse '5-7' into (lo, hi) floats."""
    if not hours_str:
        return (0, 0)
    s = str(hours_str).replace("hrs", "").replace("hr", "").replace("+", "").strip()
    if "-" in s:
        parts = s.split("-")
        try:
            return (float(parts[0].strip()), float(parts[1].strip()))
        except (ValueError, IndexError):
            return (0, 0)
    try:
        v = float(s)
        return (v, v)
    except ValueError:
        return (0, 0)


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def sarah():
    """Load Sarah Printz's generated data."""
    athlete_dir = BASE_DIR / "athletes" / "sarah-printz-20260213"
    if not athlete_dir.exists():
        pytest.skip("Sarah Printz athlete directory not found")
    return _load_athlete(athlete_dir)


@pytest.fixture
def sarah_profile(sarah):
    return sarah[0]


@pytest.fixture
def sarah_derived(sarah):
    return sarah[1]


@pytest.fixture
def sarah_html(sarah):
    if not sarah[4]:
        pytest.skip("Guide HTML not generated")
    return sarah[4]


# ── Race Day Checks ──────────────────────────────────────────

class TestRaceDayCorrectness:
    """Race day in guide must match actual race date from questionnaire."""

    def test_race_day_matches_actual_date(self, sarah_derived, sarah_html):
        """If race is on Sunday, guide must show Sunday as race day."""
        race_date_str = sarah_derived.get("race_date", "")
        if not race_date_str:
            pytest.skip("No race date in derived data")
        race_date = datetime.strptime(str(race_date_str), "%Y-%m-%d")
        expected_day = race_date.strftime("%A")

        # Find the RACE DAY row in race week section
        match = re.search(
            r'RACE DAY:.*?<strong>(\w+day)</strong>',
            sarah_html
        )
        # Alternative: find the race-day-row near "RACE DAY:"
        race_section = re.search(
            r'Race Week Schedule.*?</table>',
            sarah_html, re.DOTALL
        )
        assert race_section, "Race Week Schedule section not found"

        race_day_match = re.search(
            r'RACE DAY:.*',
            race_section.group()
        )
        assert race_day_match, "RACE DAY row not found in Race Week section"
        assert expected_day in race_section.group(), (
            f"Race is on {expected_day} ({race_date_str}) but Race Week Schedule "
            f"doesn't show {expected_day} as race day"
        )

    def test_training_calendar_shows_correct_day(self, sarah_derived, sarah_html):
        """Training calendar should mention the actual race day."""
        race_date_str = sarah_derived.get("race_date", "")
        if not race_date_str:
            pytest.skip("No race date in derived data")
        race_date = datetime.strptime(str(race_date_str), "%Y-%m-%d")
        expected_day = race_date.strftime("%A")

        # The training calendar section mentions the race day
        cal_match = re.search(
            rf'Race day is.*?{expected_day}',
            sarah_html
        )
        assert cal_match, (
            f"Training calendar doesn't mention race day as {expected_day}"
        )


# ── Hours Budget Checks ──────────────────────────────────────

class TestHoursBudget:
    """Weekly hours in guide must not exceed stated availability."""

    def test_week_by_week_hours_within_budget(self, sarah_derived, sarah_html):
        """No week's hours should exceed stated weekly_hours max."""
        weekly_hours = sarah_derived.get("weekly_hours", "")
        if not weekly_hours:
            pytest.skip("No weekly_hours in derived data")
        _, max_hrs = _parse_hours_range(weekly_hours)

        # Extract all hours from week-by-week table
        # Pattern matches the hours column: <td>4.1-5</td>
        wbw_section = re.search(
            r'Week-by-Week Overview.*?</section>',
            sarah_html, re.DOTALL
        )
        if not wbw_section:
            pytest.skip("Week-by-week section not found or empty")

        hours_matches = re.findall(
            r'<td>(\d+\.?\d*(?:-\d+\.?\d*)?)</td>\s*<td>\d+</td></tr>',
            wbw_section.group()
        )

        violations = []
        for h in hours_matches:
            parts = h.split("-")
            try:
                hi = float(parts[-1])
                if hi > max_hrs + 0.5:  # small tolerance for rounding
                    violations.append(f"{h} hrs (max allowed: {max_hrs})")
            except ValueError:
                continue

        assert not violations, (
            f"Week hours exceed stated {weekly_hours} hrs/week availability: "
            f"{violations}"
        )

    def test_long_ride_duration_reasonable(self, sarah_derived, sarah_html):
        """Long ride duration shouldn't exceed half of weekly hours."""
        weekly_hours = sarah_derived.get("weekly_hours", "")
        if not weekly_hours:
            pytest.skip("No weekly_hours")
        _, max_hrs = _parse_hours_range(weekly_hours)

        lr_matches = re.findall(r'Long Ride</td><td>([^<]+)</td>', sarah_html)
        for lr in lr_matches:
            parts = lr.replace("hours", "").replace("hour", "").strip().split("-")
            try:
                hi = float(parts[-1])
                assert hi <= max_hrs * 0.7, (
                    f"Long ride {lr} exceeds 70% of weekly budget ({max_hrs}hrs)"
                )
            except ValueError:
                continue


# ── Tier Label Checks ─────────────────────────────────────────

class TestNoTierLabels:
    """Tier labels should not appear in guide output (removed by design)."""

    TIER_NAMES = ["finisher", "time_crunched", "time crunched", "compete", "podium"]

    def test_no_tier_in_headers(self, sarah_html):
        """Tier names must not appear in guide headers."""
        headers = re.findall(r'<h[1-4][^>]*>(.*?)</h[1-4]>', sarah_html, re.DOTALL)
        for header in headers:
            header_lower = header.lower()
            for tier in self.TIER_NAMES:
                assert tier not in header_lower, (
                    f"Tier label '{tier}' found in header: {header[:80]}"
                )

    def test_no_tier_badge(self, sarah_html):
        """No tier badge/tag markup in guide."""
        assert "guide-meta-tag--gold" not in sarah_html, "Dead gold badge CSS found"
        for tier in self.TIER_NAMES:
            # Check for "FINISHER INTERMEDIATE" style badges
            badge_pattern = rf'{tier}\s+(beginner|intermediate|advanced|masters)'
            matches = re.findall(badge_pattern, sarah_html, re.IGNORECASE)
            assert not matches, (
                f"Tier badge found: '{tier} {matches[0]}'"
            )

    def test_methodology_present(self, sarah_html):
        """Methodology name should be present (replaces tier label)."""
        methodology_names = [
            "HIIT-Focused", "Traditional Pyramidal", "Polarized", "High-Volume Polarized"
        ]
        found = any(m.lower() in sarah_html.lower() for m in methodology_names)
        assert found, "No methodology name found in guide"


# ── Nutrition Sanity ──────────────────────────────────────────

class TestNutritionSanity:
    """Nutrition numbers must be personalized and research-correct."""

    def test_no_flat_90g_hr_recommendation(self, sarah_html, sarah_derived):
        """No athlete doing 6+ hour race should get 90g/hr as a RECOMMENDATION.

        '90g' may appear in educational context (e.g., explaining why it's wrong,
        or discussing SGLT1 transporter limits). The check targets actual rate
        recommendations in fueling tables or personalized targets.
        """
        race_dist = sarah_derived.get("race_distance_miles", 0)
        if race_dist < 100:
            pytest.skip("Only applies to 100+ mile races")

        # Check personalized fueling section for "YOUR" or recommendation patterns
        # Look for table rows or bold recommendations with 90g/hr
        bad_patterns = [
            r'<td>\s*90\s*</td>',                    # 90 in a table cell (fueling table)
            r'target.*?90\s*g',                        # "target: 90g"
            r'recommend.*?90\s*g/hr',                  # "recommended 90g/hr"
            r'your.*?fueling.*?90\s*g',                # "your fueling: 90g"
        ]
        for pattern in bad_patterns:
            match = re.search(pattern, sarah_html, re.IGNORECASE)
            assert not match, (
                f"Found 90g/hr recommendation pattern for 100+ mile race: "
                f"'{match.group()}'. Duration-scaled framework says max 80g/hr for 6+ hour efforts."
            )

    def test_recovery_personalized(self, sarah_html, sarah_profile):
        """Recovery nutrition should use body weight, not generic numbers."""
        weight_lbs = sarah_profile.get("demographics", {}).get("weight_lbs")
        if not weight_lbs:
            pytest.skip("No weight in profile")

        weight_kg = float(weight_lbs) / 2.205

        # Should have personalized protein (0.4g/kg)
        expected_protein = round(weight_kg * 0.4)
        # Match the full data-card content after POST-RIDE header
        recovery_section = re.search(
            r'IMMEDIATELY POST-RIDE.*?</ul>',
            sarah_html, re.DOTALL
        )
        assert recovery_section, "Recovery POST-RIDE section not found"
        content = recovery_section.group()
        assert str(expected_protein) in content, (
            f"Recovery should show ~{expected_protein}g protein (0.4g/kg * {weight_kg:.0f}kg), "
            f"not generic 30g. Section content: {content[:200]}"
        )

    def test_daily_macros_present(self, sarah_html, sarah_profile):
        """Guide should include personalized daily macro targets."""
        weight_lbs = sarah_profile.get("demographics", {}).get("weight_lbs")
        if not weight_lbs:
            pytest.skip("No weight in profile")
        weight_kg = float(weight_lbs) / 2.205

        # Check for weight-derived carb targets (6-7g/kg)
        expected_daily_lo = round(weight_kg * 6)
        expected_daily_hi = round(weight_kg * 7)
        assert str(expected_daily_lo) in sarah_html or str(expected_daily_lo + 1) in sarah_html, (
            f"Daily carb target ~{expected_daily_lo}g not found in guide"
        )


# ── Zone Naming ───────────────────────────────────────────────

class TestZoneNaming:
    """Zone names must use current naming convention."""

    def test_no_sweet_spot_zone(self, sarah_html):
        """'Sweet Spot' as a zone name was renamed to 'G Spot'."""
        # "sweet spot" in tire pressure context is OK, but not as a training zone
        zone_contexts = re.findall(r'(?:zone|Zone|ZONE)[^<]*sweet\s*spot', sarah_html, re.IGNORECASE)
        assert not zone_contexts, (
            f"'Sweet Spot' zone name found — should be 'G Spot': {zone_contexts}"
        )

    def test_g_spot_zone_present(self, sarah_html):
        """G Spot zone should be present in zone tables."""
        assert "G Spot" in sarah_html, "G Spot zone not found in guide"

    def test_gs_zone_code_present(self, sarah_html):
        """GS zone code should appear in zone tables."""
        assert ">GS<" in sarah_html or "\"GS\"" in sarah_html or ">GS " in sarah_html, (
            "GS zone code not found in guide"
        )


# ── Schedule Consistency ──────────────────────────────────────

class TestScheduleConsistency:
    """Schedule in guide must match questionnaire data."""

    def test_off_days_respected(self, sarah_profile, sarah_html):
        """Days marked as off in questionnaire should show as rest."""
        off_days = sarah_profile.get("schedule", {}).get("off_days", [])
        for day in off_days:
            # Find the day in the weekly structure table
            pattern = rf'<strong>{day.title()}</strong></td>\s*<td>Rest</td>'
            assert re.search(pattern, sarah_html, re.IGNORECASE), (
                f"Off day '{day}' is not shown as rest in weekly structure"
            )


# ── Generic Sanity ────────────────────────────────────────────

class TestGuideSanityGeneric:
    """Invariants that must hold for ANY generated guide."""

    def test_no_placeholders(self, sarah_html):
        """No template placeholders should remain."""
        placeholders = re.findall(r'\{\{[^}]+\}\}', sarah_html)
        assert not placeholders, f"Template placeholders found: {placeholders}"

    def test_no_none_text(self, sarah_html):
        """No Python None should leak into output."""
        # Check for " None " as standalone word (not in legitimate words like "None of")
        nones = re.findall(r'>\s*None\s*<', sarah_html)
        assert not nones, f"Python None leaked into guide output"

    def test_no_nan_text(self, sarah_html):
        """No NaN values should leak into output."""
        nans = re.findall(r'>\s*NaN\s*<', sarah_html)
        assert not nans, f"NaN leaked into guide output"

    def test_all_required_sections_present(self, sarah_html):
        """All required sections must be present."""
        from pipeline.step_07_guide import REQUIRED_SECTIONS
        html_lower = sarah_html.lower()
        missing = [s for s in REQUIRED_SECTIONS if s not in html_lower]
        assert not missing, f"Missing required sections: {missing}"

    def test_guide_minimum_size(self, sarah_html):
        """Guide must be at least 50KB (real guide, not stub)."""
        assert len(sarah_html) >= 50_000, (
            f"Guide is only {len(sarah_html)} bytes — minimum is 50KB"
        )

    def test_race_name_present(self, sarah_derived, sarah_html):
        """Race name from questionnaire must appear in guide."""
        race_name = sarah_derived.get("race_name", "")
        if race_name:
            assert race_name in sarah_html, f"Race name '{race_name}' not in guide"

    def test_race_distance_present(self, sarah_derived, sarah_html):
        """Race distance from questionnaire must appear in guide."""
        race_dist = sarah_derived.get("race_distance_miles", 0)
        if race_dist:
            assert str(race_dist) in sarah_html, (
                f"Race distance {race_dist} not in guide"
            )

    def test_athlete_name_present(self, sarah_profile, sarah_html):
        """Athlete name must appear in guide."""
        name = sarah_profile.get("name", "")
        if name:
            assert name in sarah_html, f"Athlete name '{name}' not in guide"


# ── Cross-Section Consistency ─────────────────────────────────

class TestCrossSectionConsistency:
    """Values that appear in multiple sections must be consistent."""

    def test_ftp_consistent(self, sarah_profile, sarah_html):
        """FTP value should be consistent across all mentions."""
        ftp = sarah_profile.get("fitness", {}).get("ftp_watts")
        if not ftp:
            pytest.skip("No FTP in profile")

        # Find all FTP mentions with numbers
        ftp_mentions = re.findall(r'(\d+)\s*[Ww](?:atts)?', sarah_html)
        ftp_vals = [int(m) for m in ftp_mentions if abs(int(m) - ftp) < 50]
        # All should be the same value
        if ftp_vals:
            assert all(v == ftp_vals[0] for v in ftp_vals), (
                f"Inconsistent FTP values found: {set(ftp_vals)}"
            )

    def test_weekly_hours_consistent(self, sarah_derived, sarah_html):
        """Weekly hours should be consistent between sections."""
        weekly_hours = sarah_derived.get("weekly_hours", "")
        if not weekly_hours:
            pytest.skip("No weekly_hours")
        # The hours value should appear in the guide
        assert weekly_hours in sarah_html, (
            f"Stated weekly hours '{weekly_hours}' not found in guide"
        )
