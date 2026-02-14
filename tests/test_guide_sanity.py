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


# ── Long Ride Realism ────────────────────────────────────────

class TestLongRideRealism:
    """Long ride targets must be achievable within the athlete's weekly budget."""

    def test_no_unreachable_duration_target(self, sarah_derived, sarah_html):
        """Key workouts should never claim 70-80% of race duration when that's impossible."""
        weekly_hours = sarah_derived.get("weekly_hours", "")
        if not weekly_hours:
            pytest.skip("No weekly_hours")
        _, max_hrs = _parse_hours_range(weekly_hours)
        lr_ceiling = max_hrs * 0.4  # ~40% of weekly budget per long ride

        # If ceiling < 3hrs, the guide should NOT say "70-80% of race duration"
        if lr_ceiling < 3.0:
            assert "70-80% of race duration" not in sarah_html, (
                f"Guide claims '70-80% of race duration' but long ride ceiling is "
                f"only {lr_ceiling:.1f}hrs (weekly budget: {max_hrs}hrs). "
                f"This is an unreachable target."
            )

    def test_phase_progression_no_unreachable_target(self, sarah_derived, sarah_html):
        """Phase descriptions should not reference 60-70% of race duration when unreachable."""
        weekly_hours = sarah_derived.get("weekly_hours", "")
        if not weekly_hours:
            pytest.skip("No weekly_hours")
        _, max_hrs = _parse_hours_range(weekly_hours)
        lr_ceiling = max_hrs * 0.4

        if lr_ceiling < 3.0:
            assert "60-70% of race duration" not in sarah_html, (
                f"Phase progression claims '60-70% of race duration' but long ride "
                f"ceiling is only {lr_ceiling:.1f}hrs."
            )


# ── Race Week Table Order ────────────────────────────────────

class TestRaceWeekTableOrder:
    """Race week table must be in chronological countdown order."""

    def test_race_day_is_second_to_last_row(self, sarah_html):
        """Race day row should be near the end, not the beginning."""
        race_table = re.search(
            r'Race Week Schedule.*?</table>',
            sarah_html, re.DOTALL
        )
        if not race_table:
            pytest.skip("Race week table not found")

        rows = re.findall(r'<tr[^>]*>.*?</tr>', race_table.group(), re.DOTALL)
        # Skip header row
        data_rows = rows[1:]
        if not data_rows:
            pytest.skip("No data rows in race week table")

        # Race day should be second to last (last is recovery)
        race_day_indices = [i for i, r in enumerate(data_rows) if "RACE DAY" in r]
        assert race_day_indices, "No RACE DAY row found in table"
        assert race_day_indices[0] == len(data_rows) - 2, (
            f"RACE DAY row is at position {race_day_indices[0]} but should be at "
            f"position {len(data_rows) - 2} (second to last). "
            f"Recovery should be the final row."
        )

    def test_countdown_labels_present(self, sarah_html):
        """Race week table should have countdown labels (Day -6, Day -5, etc.)."""
        race_table = re.search(
            r'Race Week Schedule.*?</table>',
            sarah_html, re.DOTALL
        )
        if not race_table:
            pytest.skip("Race week table not found")

        table_text = race_table.group()
        assert "Day -6" in table_text, "Missing Day -6 countdown label"
        assert "Day -1" in table_text, "Missing Day -1 countdown label"
        assert "Race Day" in table_text, "Missing Race Day label"
        assert "Day +1" in table_text, "Missing Day +1 recovery label"


# ── FTP Gating ───────────────────────────────────────────────

class TestFTPGating:
    """When FTP is not provided, the guide must gate structured training behind testing."""

    def test_ftp_test_required_callout(self, sarah_profile, sarah_html):
        """If no FTP, guide must have a strong testing callout."""
        ftp = sarah_profile.get("fitness", {}).get("ftp_watts")
        if ftp:
            pytest.skip("FTP is provided — gating not needed")

        # Must contain the "BEFORE YOU START" or similar gating language
        assert "FTP TEST" in sarah_html.upper() or "FTP test" in sarah_html, (
            "Guide doesn't mention FTP test despite FTP not being provided"
        )
        assert "before" in sarah_html.lower() or "Week 1" in sarah_html, (
            "Guide doesn't frame FTP test as a prerequisite"
        )

    def test_week_1_shows_ftp_test(self, sarah_profile, sarah_html):
        """Week 1 in the week-by-week table should show FTP TEST when FTP is missing."""
        ftp = sarah_profile.get("fitness", {}).get("ftp_watts")
        if ftp:
            pytest.skip("FTP is provided")

        # Find Week 1 row (W1 or W01)
        w1_match = re.search(r'<tr>.*?<strong>W0?1</strong>.*?</tr>', sarah_html, re.DOTALL)
        if not w1_match:
            pytest.skip("Week 1 row not found")

        assert "FTP TEST" in w1_match.group().upper(), (
            "Week 1 should be marked with [FTP TEST] when FTP is not provided"
        )


# ── Template Artifact Labels ────────────────────────────────

class TestNoTemplateArtifacts:
    """Internal template labels must not leak into athlete-facing guide."""

    def test_no_extended_base_prefix(self, sarah_html):
        """'Extended Base' is an internal label from template extension — must not appear."""
        assert "Extended Base" not in sarah_html, (
            "Internal 'Extended Base' template label is leaking into the guide. "
            "Week focus text should use the original phase label, not the wrapped version."
        )

    def test_focus_text_not_duplicated(self, sarah_derived, sarah_html):
        """Extended weeks should have transformed focus text, not verbatim duplicates.

        When a 12-week template is extended, duplicated weeks should have different
        focus text from the originals (e.g., "Continued Development" not "Build Phase Begins" again).
        Recovery weeks are exempt — "Recovery & Absorption" repeating is fine.
        """
        plan_duration = sarah_derived.get("plan_duration", 12)
        if plan_duration <= 12:
            pytest.skip("Plan not extended — duplicate test not applicable")

        wbw_section = re.search(
            r'Week-by-Week Overview.*?</section>',
            sarah_html, re.DOTALL
        )
        if not wbw_section:
            pytest.skip("Week-by-week section not found")

        # Extract all focus texts from the table
        focus_matches = re.findall(
            r'<td>([^<]+)</td>\s*<td>\d+%',
            wbw_section.group()
        )
        # Clean up FTP TEST markers
        focus_texts = [re.sub(r'\s*\[FTP TEST\]', '', f).strip()
                       for f in focus_matches if f.strip()]

        # No focus text should contain internal wrapping like "Extended Base (...)"
        for focus in focus_texts:
            assert not re.match(r'^Extended\s', focus, re.IGNORECASE), (
                f"Internal template label in week focus: '{focus}'"
            )

        # Non-recovery focus texts should not appear more than once
        non_recovery = [f for f in focus_texts
                        if "recovery" not in f.lower() and "race week" not in f.lower()]
        seen = {}
        duplicates = []
        for f in non_recovery:
            if f in seen:
                duplicates.append(f)
            seen[f] = True
        assert not duplicates, (
            f"Duplicate focus text found in non-recovery weeks: {duplicates}. "
            f"Extended weeks should have transformed labels."
        )


# ── Dress Rehearsal Realism ─────────────────────────────────

class TestDressRehearsalRealism:
    """Dress rehearsal hours must be achievable within weekly budget."""

    def test_dress_rehearsal_within_budget(self, sarah_derived, sarah_html):
        """Dress rehearsal duration should not exceed what's achievable in one ride."""
        weekly_hours = sarah_derived.get("weekly_hours", "")
        if not weekly_hours:
            pytest.skip("No weekly_hours")
        _, max_hrs = _parse_hours_range(weekly_hours)

        # Find dress rehearsal hour mentions
        dr_section = re.search(
            r'DRESS REHEARSAL.*?</div>',
            sarah_html, re.DOTALL
        )
        if not dr_section:
            pytest.skip("Dress rehearsal section not found")

        content = dr_section.group()
        # Look for hour values like "5-hour" or "4-5 hours" or "(4-5 hours)"
        hour_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:-\s*\d+(?:\.\d+)?)?\s*hour', content, re.IGNORECASE)

        for h in hour_matches:
            hours_val = float(h)
            assert hours_val <= max_hrs * 0.7, (
                f"Dress rehearsal mentions {hours_val}-hour ride but weekly budget is "
                f"only {max_hrs}hrs. A single ride shouldn't exceed ~{max_hrs * 0.6:.0f} hours."
            )


# ── Calendar Date Integrity ─────────────────────────────────

class TestCalendarDateIntegrity:
    """Training calendar must contain the race date in the final week."""

    def test_last_week_contains_race_date(self, sarah_derived, sarah_html):
        """The last training week's date range must include race day."""
        race_date_str = sarah_derived.get("race_date", "")
        if not race_date_str:
            pytest.skip("No race date")

        race_date = datetime.strptime(str(race_date_str), "%Y-%m-%d")

        # Find all week date ranges in calendar
        cal_section = re.search(
            r'Your Training Calendar.*?</table>',
            sarah_html, re.DOTALL
        )
        assert cal_section, "Training calendar not found"

        # Extract the last week's date range
        date_ranges = re.findall(
            r'<td>(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})</td>',
            cal_section.group()
        )
        assert date_ranges, "No date ranges found in calendar"

        last_start_str, last_end_str = date_ranges[-1]
        last_start = datetime.strptime(last_start_str, "%Y-%m-%d")
        last_end = datetime.strptime(last_end_str, "%Y-%m-%d")

        assert last_start <= race_date <= last_end, (
            f"Race day ({race_date_str}) falls outside the last training week "
            f"({last_start_str} to {last_end_str}). "
            f"There's a {(race_date - last_end).days}-day gap."
        )

    def test_no_week_gap_in_calendar(self, sarah_html):
        """Calendar weeks should be contiguous — no missing weeks."""
        cal_section = re.search(
            r'Your Training Calendar.*?</table>',
            sarah_html, re.DOTALL
        )
        if not cal_section:
            pytest.skip("Training calendar not found")

        date_ranges = re.findall(
            r'<td>(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})</td>',
            cal_section.group()
        )
        for i in range(1, len(date_ranges)):
            prev_end = datetime.strptime(date_ranges[i-1][1], "%Y-%m-%d")
            curr_start = datetime.strptime(date_ranges[i][0], "%Y-%m-%d")
            gap = (curr_start - prev_end).days
            assert gap == 1, (
                f"Gap between week {i} and {i+1}: {gap} days "
                f"({date_ranges[i-1][1]} to {date_ranges[i][0]})"
            )


# ── Phase Label Consistency ─────────────────────────────────

class TestPhaseConsistency:
    """Phase labels must be consistent between calendar and week-by-week table."""

    def test_calendar_and_wbw_phases_match(self, sarah_html):
        """Phase labels in calendar and week-by-week must agree for each week."""
        # Extract phases from calendar
        cal_section = re.search(
            r'Your Training Calendar.*?</table>',
            sarah_html, re.DOTALL
        )
        if not cal_section:
            pytest.skip("Calendar not found")

        cal_phases = re.findall(
            r'<td>W(\d+)</td>.*?phase-indicator--(\w+)',
            cal_section.group()
        )

        # Extract phases from week-by-week
        wbw_section = re.search(
            r'Week-by-Week Overview.*?</section>',
            sarah_html, re.DOTALL
        )
        if not wbw_section:
            pytest.skip("Week-by-week not found")

        wbw_phases = re.findall(
            r'<strong>W(\d+)</strong>.*?phase-indicator--(\w+)',
            wbw_section.group()
        )

        # Build dicts for comparison
        cal_dict = {int(w): p for w, p in cal_phases}
        wbw_dict = {int(w): p for w, p in wbw_phases}

        mismatches = []
        for week in sorted(set(cal_dict.keys()) & set(wbw_dict.keys())):
            if cal_dict[week] != wbw_dict[week]:
                mismatches.append(
                    f"W{week}: calendar={cal_dict[week]}, week-by-week={wbw_dict[week]}"
                )

        assert not mismatches, (
            f"Phase labels differ between calendar and week-by-week: {mismatches}"
        )

    def test_phase_progression_matches_wbw(self, sarah_html, sarah_derived):
        """Phase progression section week ranges must match week-by-week phase labels."""
        plan_duration = sarah_derived.get("plan_duration", 12)

        # Extract phase ranges from Phase Progression section
        phase_section = re.search(
            r'Phase Progression.*?</section>',
            sarah_html, re.DOTALL
        )
        if not phase_section:
            pytest.skip("Phase progression section not found")

        # Match "WEEKS X-Y" in phase cards
        phase_ranges = re.findall(
            r'phase-indicator--(\w+).*?WEEKS\s+(\d+)-(\d+)',
            phase_section.group()
        )

        # Extract week-by-week phases
        wbw_section = re.search(
            r'Week-by-Week Overview.*?</section>',
            sarah_html, re.DOTALL
        )
        if not wbw_section:
            pytest.skip("Week-by-week not found")

        wbw_phases = re.findall(
            r'<strong>W(\d+)</strong>.*?phase-indicator--(\w+)',
            wbw_section.group()
        )
        wbw_dict = {int(w): p for w, p in wbw_phases}

        for phase_type, start, end in phase_ranges:
            for w in range(int(start), int(end) + 1):
                if w in wbw_dict:
                    # Race week overrides taper label — skip that check
                    if w == plan_duration:
                        continue
                    assert wbw_dict[w] == phase_type, (
                        f"Phase Progression says W{w} is {phase_type}, "
                        f"but week-by-week shows {wbw_dict[w]}"
                    )


# ── Long Ride Cautionary Number ─────────────────────────────

class TestLongRideCautionaryNumber:
    """Long ride section should reference realistic hours, not hardcoded values."""

    def test_no_unreachable_cautionary_hours(self, sarah_derived, sarah_html):
        """The Long Ride data card should not mention hour counts
        that exceed the athlete's long ride ceiling."""
        weekly_hours = sarah_derived.get("weekly_hours", "")
        if not weekly_hours:
            pytest.skip("No weekly_hours")
        _, max_hrs = _parse_hours_range(weekly_hours)

        # Find the Long Ride data card
        lr_section = re.search(
            r'LONG RIDE</div>.*?</div>\s*</div>',
            sarah_html, re.DOTALL
        )
        if not lr_section:
            pytest.skip("Long Ride data card not found")

        content = lr_section.group()
        # Find any hour mentions like "5 hours" or "4-5 hours"
        hour_mentions = re.findall(r'(\d+(?:\.\d+)?)\s*hour', content, re.IGNORECASE)
        for h in hour_mentions:
            assert float(h) <= max_hrs, (
                f"Long Ride card mentions {h} hours but athlete's weekly budget "
                f"is only {max_hrs}hrs. Cautionary number should reflect reality."
            )


class TestRaceDateVerification:
    """Guide must show date verification callout with day of week and cross-reference."""

    def test_guide_shows_race_day_of_week(self, sarah_html, sarah_derived):
        """Race date verification must include the day of week."""
        race_date_str = sarah_derived.get("race_date", "")
        if not race_date_str:
            pytest.skip("No race_date in derived")
        rd = datetime.strptime(race_date_str, "%Y-%m-%d")
        day_name = rd.strftime("%A")
        assert day_name in sarah_html, (
            f"Guide missing day of week '{day_name}' for race date {race_date_str}. "
            f"Athletes need to see the day to verify it's correct."
        )

    def test_guide_has_date_verification_section(self, sarah_html):
        """Guide must have a RACE DATE VERIFICATION callout."""
        assert "RACE DATE VERIFICATION" in sarah_html, (
            "Guide is missing the RACE DATE VERIFICATION callout. "
            "Every guide must triple-check the race date."
        )

    def test_guide_has_triple_check_reminder(self, sarah_html):
        """Guide must remind athlete to verify date independently."""
        assert "triple-check" in sarah_html.lower() or "triple check" in sarah_html.lower(), (
            "Guide missing triple-check reminder for race date."
        )


class TestExactDatesInGuide:
    """Phase timelines must show exact calendar dates, not just week numbers."""

    def test_gut_training_has_month_dates(self, sarah_html):
        """Gut training timeline must show month/day date ranges, not just 'Weeks 1-8'."""
        import re
        # Look for month abbreviation in gut training section
        start = sarah_html.find("Training Your Gut</h3>")
        end = sarah_html.find("Race-Day Nutrition Execution")
        assert start != -1, "Gut training section not found"
        gut_section = sarah_html[start:end] if end != -1 else sarah_html[start:start+3000]
        # Must contain month abbreviations (Feb, Mar, Apr, May, Jun)
        month_pattern = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+")
        matches = month_pattern.findall(gut_section)
        assert len(matches) >= 2, (
            f"Gut training timeline must show exact dates (e.g., 'Feb 16 – Apr 12'), "
            f"found only {len(matches)} month references. No vague 'Weeks 1-8' without dates."
        )

    def test_phase_progression_has_month_dates(self, sarah_html):
        """Phase progression cards must show month/day date ranges."""
        import re
        # Use the section heading (not the TOC link) to find the right section
        marker = "Phase Progression</h2>"
        start = sarah_html.find(marker)
        assert start != -1, "Phase Progression section heading not found"
        end = sarah_html.find("Week-by-Week Overview</h2>", start)
        phase_section = sarah_html[start:end] if end != -1 else sarah_html[start:start+5000]
        month_pattern = re.compile(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d+")
        matches = month_pattern.findall(phase_section)
        assert len(matches) >= 4, (
            f"Phase progression must show exact dates for each phase, "
            f"found only {len(matches)} month references."
        )

    def test_week_by_week_table_has_dates_column(self, sarah_html):
        """Week-by-week table must have a Dates column with Mon-Sun ranges."""
        assert ">Dates<" in sarah_html, (
            "Week-by-week table missing 'Dates' column header. "
            "Every week must show its exact calendar dates."
        )

    def test_week_by_week_table_has_date_per_row(self, sarah_html):
        """Each week row must have a date range like 'Feb 16–Feb 22'."""
        import re
        start = sarah_html.find("Week-by-Week Overview</h2>")
        end = sarah_html.find("Workout Execution</h2>", start)
        assert start != -1, "Week-by-week section not found"
        wbw_section = sarah_html[start:end] if end != -1 else sarah_html[start:start+10000]
        # Count ndash date ranges (Feb 16&ndash;Feb 22 pattern)
        date_ranges = re.findall(r"[A-Z][a-z]{2}\s+\d+&ndash;[A-Z][a-z]{2}\s+\d+", wbw_section)
        # Should have at least plan_duration date ranges (one per week row)
        assert len(date_ranges) >= 10, (
            f"Week-by-week table should have date ranges for each week, found {len(date_ranges)}"
        )


class TestGuideConsistency:
    """Guide content must be internally consistent."""

    def test_midweek_start_note_present(self, sarah_html):
        """When plan starts on non-Monday, guide must explain what to do."""
        # Sarah's plan starts Feb 14, 2026 which is a Saturday
        assert "YOUR PLAN STARTS ON A" in sarah_html, (
            "Guide should have a mid-week start callout when plan_start_date is not a Monday"
        )
        assert "Saturday" in sarah_html.split("YOUR PLAN STARTS ON A")[1][:200], (
            "Mid-week start note should mention the actual start day (Saturday)"
        )

    def test_recovery_cadence_text_matches_plan(self, sarah_html):
        """Recovery week text must say 'every 3rd' for 40+ athlete, not 'every 3rd or 4th'."""
        # Find the recovery weeks callout in phase progression
        start = sarah_html.find("RECOVERY WEEKS</div>")
        assert start != -1, "Recovery weeks callout not found"
        section = sarah_html[start:start+300]
        assert "Every 3rd week" in section, (
            f"For 44-year-old athlete, should say 'Every 3rd week', not generic '3rd or 4th'. "
            f"Found: {section[:200]}"
        )
        assert "3rd or 4th" not in section, (
            "Should NOT say '3rd or 4th' — cadence is specific to athlete's age"
        )

    def test_gut_training_table_uses_plan_phases(self, sarah_html):
        """Gut training table must use 'Plan Phase' column, not numbered gut-training weeks."""
        start = sarah_html.find("Gut Training Progression</h4>")
        assert start != -1, "Gut Training Progression section not found"
        section = sarah_html[start:start+1500]
        assert "Plan Phase" in section, (
            "Gut training table should use 'Plan Phase' as column header, "
            "not a standalone numbered-week protocol"
        )
        # Should NOT have the old "Start gut training N weeks before race day" framing
        assert "weeks before race day" not in section.lower(), (
            "Gut training table should not reference 'N weeks before race day' — "
            "it should align with plan phases"
        )

    def test_session_count_excludes_rest_days(self, sarah_html):
        """Week-by-week session count must not include rest days."""
        import re
        start = sarah_html.find("Week-by-Week Overview</h2>")
        end = sarah_html.find("Workout Execution</h2>", start)
        assert start != -1
        wbw = sarah_html[start:end] if end != -1 else sarah_html[start:start+10000]
        # The Sessions column is the last <td> in each row
        # For W1, the template has 7 workouts but 2 are rest → should show 5
        rows = re.findall(r"<tr><td><strong>W(\d+)</strong></td>.*?</tr>", wbw, re.DOTALL)
        assert len(rows) > 0, "No week rows found"
        # Check W1 specifically: should not be 7
        w1_match = re.search(r"<tr><td><strong>W1</strong></td>.*?<td>(\d+)</td></tr>", wbw, re.DOTALL)
        assert w1_match, "W1 row not found"
        session_count = int(w1_match.group(1))
        assert session_count < 7, (
            f"W1 shows {session_count} sessions but should be less than 7 "
            f"(rest days must not count as sessions)"
        )
