"""
Tests for individual profile integrity.

Validates that every race-data/*.json file:
1. Is valid JSON with a 'race' wrapper key
2. Has filename matching race.slug (with known exceptions)
3. Contains required vital signs (name, location)
4. Has valid URL fields where present
5. Has no unintentional duplicate names
"""

import json
import re
import pytest
from pathlib import Path

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"

# Known exceptions — document why each is allowed
KNOWN_SLUG_MISMATCHES = {
    "fuego-mtb": "fuego-xl",  # Historical: renamed from Fuego XL to Fuego MTB
}

KNOWN_DUPLICATE_NAMES = set()  # Previously: FNLD GRVL, Grasshopper — resolved by removing stubs


def get_all_profiles():
    """Load all race profiles as (filename, data) tuples."""
    profiles = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
        profiles.append((f.name, f.stem, data))
    return profiles


class TestJSONValidity:
    """Every file must be valid JSON with correct structure."""

    def test_all_files_parse(self):
        """Every .json file in race-data/ must parse without error."""
        errors = []
        for f in sorted(RACE_DATA_DIR.glob("*.json")):
            try:
                json.loads(f.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"{f.name}: {e}")

        if errors:
            pytest.fail(f"JSON parse errors:\n" + "\n".join(errors))

    def test_all_have_race_wrapper(self):
        """Every profile must have a top-level 'race' key."""
        missing = []
        for fname, slug, data in get_all_profiles():
            if "race" not in data:
                missing.append(fname)

        if missing:
            pytest.fail(f"{len(missing)} profiles missing 'race' key:\n" +
                        "\n".join(f"  {f}" for f in missing))


class TestSlugConsistency:
    """Filename must match race.slug field."""

    def test_slug_matches_filename(self):
        """race.slug should equal filename (minus .json)."""
        mismatches = []
        for fname, file_slug, data in get_all_profiles():
            race = data.get("race", data)
            json_slug = race.get("slug", "")

            if file_slug != json_slug:
                # Check if this is a known exception
                if KNOWN_SLUG_MISMATCHES.get(file_slug) == json_slug:
                    continue
                mismatches.append(f"  {fname}: file={file_slug}, slug={json_slug}")

        if mismatches:
            pytest.fail(f"{len(mismatches)} slug mismatches:\n" + "\n".join(mismatches))


class TestVitalSigns:
    """Every profile must have core identifying fields."""

    def test_all_have_name(self):
        """Every profile must have a non-empty name."""
        missing = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            name = race.get("name", "")
            if not name or not str(name).strip():
                missing.append(fname)

        if missing:
            pytest.fail(f"{len(missing)} profiles with missing/empty name:\n" +
                        "\n".join(f"  {f}" for f in missing))

    def test_all_have_location(self):
        """Every profile must have a location in vitals."""
        missing = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            vitals = race.get("vitals", {})
            location = vitals.get("location", "")
            if not location or not str(location).strip():
                missing.append(fname)

        if missing:
            pytest.fail(f"{len(missing)} profiles with missing location:\n" +
                        "\n".join(f"  {f}" for f in missing))

    def test_all_have_distance_or_elevation(self):
        """Every profile should have at least distance or elevation."""
        missing = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            vitals = race.get("vitals", {})
            dist = vitals.get("distance_mi")
            elev = vitals.get("elevation_ft")
            # Accept numeric or string ranges (e.g., "48-91")
            has_dist = dist is not None and str(dist).strip() not in ("", "0", "?")
            has_elev = elev is not None and str(elev).strip() not in ("", "0", "?")
            if not has_dist and not has_elev:
                missing.append(fname)

        if missing:
            pytest.fail(f"{len(missing)} profiles with no distance or elevation:\n" +
                        "\n".join(f"  {f}" for f in missing))

    def test_all_have_date_fields(self):
        """Every profile must have date and date_specific in vitals."""
        missing = []
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            vitals = race.get("vitals", {})
            if not vitals.get("date") and not vitals.get("date_specific"):
                missing.append(fname)

        if missing:
            pytest.fail(f"{len(missing)} profiles with no date fields:\n" +
                        "\n".join(f"  {f}" for f in missing))


class TestURLValidity:
    """URL fields must be well-formed where present."""

    URL_PATTERN = re.compile(r'^https?://\S+')

    def test_url_fields_valid(self):
        """URL fields that look like URLs must be well-formed.

        Skips placeholder text like 'Check X website' — only validates
        strings that start with http or www.
        """
        url_fields = ["website", "official_site", "registration_url"]
        violations = []

        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            vitals = race.get("vitals", {})
            logistics = race.get("logistics", {})

            for section_name, section in [("vitals", vitals), ("logistics", logistics)]:
                for field in url_fields:
                    val = section.get(field, "")
                    if not val or not isinstance(val, str):
                        continue
                    val = val.strip()
                    # Only validate strings that look like URLs (start with http/www)
                    if val.startswith(("http://", "https://", "www.")):
                        if not self.URL_PATTERN.match(val):
                            violations.append(f"  {fname} {section_name}.{field}: {val!r}")

        if violations:
            pytest.fail(f"{len(violations)} malformed URLs:\n" + "\n".join(violations))


class TestDuplicateDetection:
    """No unintentional duplicate profiles."""

    def test_no_duplicate_slugs(self):
        """No two files should have the same filename/slug."""
        slugs = [f.stem for f in RACE_DATA_DIR.glob("*.json")]
        dupes = [s for s in slugs if slugs.count(s) > 1]
        if dupes:
            pytest.fail(f"Duplicate slugs: {set(dupes)}")

    def test_no_unintentional_duplicate_names(self):
        """Flag duplicate race names, allowing known exceptions."""
        name_to_files = {}
        for fname, _, data in get_all_profiles():
            race = data.get("race", data)
            name = race.get("name", "").strip().upper()
            if name:
                name_to_files.setdefault(name, []).append(fname)

        unexpected_dupes = []
        for name, files in name_to_files.items():
            if len(files) > 1:
                # Check if this is a known exception (case-insensitive)
                original_name = next(
                    (n for n in KNOWN_DUPLICATE_NAMES if n.upper() == name), None
                )
                if original_name is None:
                    unexpected_dupes.append(f"  '{name}': {files}")

        if unexpected_dupes:
            pytest.fail(f"{len(unexpected_dupes)} unexpected duplicate names:\n" +
                        "\n".join(unexpected_dupes))
