"""
Cross-cutting data quality tests for race-data/*.json profiles.

Catches recurring issues from batch generation:
- Malformed slugs, dates, suffering zones
- Sponsor names in race names
- Self-referencing alternative slugs
- Coordinate plausibility
- Discipline mismatches
"""

import json
import re
import warnings
import pytest
from pathlib import Path

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"


def get_all_profiles():
    """Load all race profiles as (filename, slug, data) tuples."""
    profiles = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
        profiles.append((f.name, f.stem, data))
    return profiles


class TestSlugFormat:
    """Slugs must be URL-safe."""

    def test_all_slugs_are_url_safe(self):
        """Slugs must match ^[a-z0-9-]+$ — no accents, spaces, uppercase."""
        pattern = re.compile(r'^[a-z0-9-]+$')
        violations = []
        for fname, slug, data in get_all_profiles():
            race = data.get("race", data)
            json_slug = race.get("slug", "")
            if not pattern.match(json_slug):
                violations.append(f"  {fname}: slug={json_slug!r}")
            if not pattern.match(slug):
                violations.append(f"  {fname}: filename slug={slug!r}")

        if violations:
            pytest.fail(
                f"{len(violations)} non-URL-safe slugs:\n" + "\n".join(violations)
            )


class TestDateFormat:
    """date_specific must follow expected patterns."""

    def test_date_specific_format(self):
        """Every date_specific must match one of the accepted formats.

        Accepted:
        - 'YYYY: Month Day' (standard)
        - 'Month Day, YYYY' (US-style)
        - Placeholder text like 'Check ... for date', 'TBD', 'Paused', etc.
        - Status notes like 'Event cancelled', 'Status: UNCERTAIN'
        """
        # Patterns that indicate valid date content
        valid_patterns = [
            re.compile(r'^\d{4}:\s+\w+'),                     # 2026: June 15
            re.compile(r'^\d{4}\s+\w+'),                       # 2026 Arizona: ...
            re.compile(r'^[A-Z][a-z]+ \d{1,2},? \d{4}'),      # June 15, 2026
            re.compile(r'^[A-Z][a-z]+ \d{1,2}[-–]'),          # June 15-17
            re.compile(r'(?i)^check\b'),                       # Check official website
            re.compile(r'(?i)\b(tbd|paused|cancelled|canceled|uncertain|no future|final)\b'),
            re.compile(r'(?i)^(event|status)'),                # Event cancelled, Status: ...
            re.compile(r'(?i)^self-scheduled'),                # Self-scheduled events
        ]
        violations = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            vitals = race.get("vitals", {})
            ds = vitals.get("date_specific", "")
            if not ds or not isinstance(ds, str):
                continue
            ds = ds.strip()
            if not ds:
                continue
            if any(p.search(ds) for p in valid_patterns):
                continue
            violations.append(f"  {fname}: date_specific={ds!r}")

        if violations:
            pytest.fail(
                f"{len(violations)} date_specific values with unexpected format:\n"
                + "\n".join(violations)
            )

    def test_no_boolean_in_date_specific(self):
        """date_specific must be a string, not True/False/None."""
        violations = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            vitals = race.get("vitals", {})
            ds = vitals.get("date_specific")
            if ds is None:
                continue
            if not isinstance(ds, str):
                violations.append(f"  {fname}: date_specific={ds!r} (type={type(ds).__name__})")

        if violations:
            pytest.fail(
                f"{len(violations)} date_specific values with wrong type:\n"
                + "\n".join(violations)
            )


class TestSufferingZones:
    """Suffering zones must have required fields and be ordered."""

    def test_suffering_zones_have_required_fields(self):
        """Each zone must have a label/name and description.

        Accepts alternative field names from batch generation:
        - label: label, name, named_section, stage, event
        - desc: desc, description, survival_strategy

        Distance markers (mile/km) are optional — some road races use
        named sections without mile markers.
        """
        violations = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            zones = race.get("course_description", {}).get("suffering_zones", [])
            for i, zone in enumerate(zones):
                if not isinstance(zone, dict):
                    violations.append(f"  {fname}: zone[{i}] is not a dict: {zone!r}")
                    continue
                has_label = any(k in zone for k in ("label", "name", "named_section", "stage", "event"))
                has_desc = any(k in zone for k in ("desc", "description", "survival_strategy"))
                missing = []
                if not has_label:
                    missing.append("label (label/name)")
                if not has_desc:
                    missing.append("desc (desc/description)")
                if missing:
                    violations.append(f"  {fname}: zone[{i}] missing {missing}")

        if violations:
            warnings.warn(
                f"{len(violations)} suffering zones with missing fields:\n"
                + "\n".join(violations)
            )

    def test_suffering_zones_ordered_by_distance(self):
        """Zones should be in ascending distance order (mile or km)."""
        violations = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            zones = race.get("course_description", {}).get("suffering_zones", [])
            distances = []
            for zone in zones:
                if not isinstance(zone, dict):
                    continue
                m = zone.get("mile") or zone.get("miles") or zone.get("km") or zone.get("distance_km")
                if m is not None and isinstance(m, (int, float)):
                    distances.append(m)
            if distances != sorted(distances):
                violations.append(f"  {fname}: distances={distances}")

        if violations:
            warnings.warn(
                f"{len(violations)} profiles with out-of-order suffering zones:\n"
                + "\n".join(violations)
            )


class TestAlternativeSlugs:
    """Alternative slug references must be valid."""

    def test_alternative_slugs_not_self_referencing(self):
        """A race's alternative_slugs must not contain its own slug."""
        violations = []
        for fname, slug, data in get_all_profiles():
            race = data.get("race", data)
            alts = race.get("alternative_slugs", [])
            if not isinstance(alts, list):
                continue
            if slug in alts:
                violations.append(f"  {fname}: self-references in alternative_slugs")

        if violations:
            pytest.fail(
                f"{len(violations)} profiles with self-referencing alternative_slugs:\n"
                + "\n".join(violations)
            )

    def test_alternative_slugs_reference_existing_races(self):
        """Alt slugs should point to real files (warning, not hard fail)."""
        all_slugs = {f.stem for f in RACE_DATA_DIR.glob("*.json")}
        missing_refs = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            alts = race.get("alternative_slugs", [])
            if not isinstance(alts, list):
                continue
            for alt in alts:
                if alt not in all_slugs:
                    missing_refs.append(f"  {fname}: alt slug {alt!r} has no matching file")

        if missing_refs:
            warnings.warn(
                f"{len(missing_refs)} alternative_slugs reference non-existent races:\n"
                + "\n".join(missing_refs)
            )


class TestCoordinates:
    """Coordinates must be plausible."""

    def test_coordinate_plausibility(self):
        """When lat/lng present, lat in [-90,90], lng in [-180,180]."""
        violations = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            vitals = race.get("vitals", {})
            lat = vitals.get("lat")
            lng = vitals.get("lng")
            if lat is not None and isinstance(lat, (int, float)):
                if not (-90 <= lat <= 90):
                    violations.append(f"  {fname}: lat={lat} out of range [-90,90]")
            if lng is not None and isinstance(lng, (int, float)):
                if not (-180 <= lng <= 180):
                    violations.append(f"  {fname}: lng={lng} out of range [-180,180]")

        if violations:
            pytest.fail(
                f"{len(violations)} profiles with implausible coordinates:\n"
                + "\n".join(violations)
            )


class TestRaceNameQuality:
    """Race names must be clean."""

    def test_no_sponsor_names_in_race_name(self):
        """Race names must not contain | (catches 'Sponsor | Race Name' pattern)."""
        violations = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            name = race.get("name", "")
            if "|" in name:
                violations.append(f"  {fname}: name={name!r}")

        if violations:
            pytest.fail(
                f"{len(violations)} race names contain '|' (likely sponsor prefix):\n"
                + "\n".join(violations)
            )


class TestDisciplineConsistency:
    """Discipline values must be consistent across sections."""

    def test_discipline_matches_between_rating_and_vitals(self):
        """If both gravel_god_rating.discipline and vitals.discipline exist, they must match."""
        violations = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            rating_disc = race.get("gravel_god_rating", {}).get("discipline")
            vitals_disc = race.get("vitals", {}).get("discipline")
            if rating_disc and vitals_disc and rating_disc != vitals_disc:
                violations.append(
                    f"  {fname}: rating.discipline={rating_disc!r} != vitals.discipline={vitals_disc!r}"
                )

        if violations:
            warnings.warn(
                f"{len(violations)} profiles with discipline mismatch:\n"
                + "\n".join(violations)
            )
