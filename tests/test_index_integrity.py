"""
Tests for race-index.json integrity.

Validates that:
1. race-index.json is valid JSON array
2. Every race-data/*.json profile appears in the index with has_profile=true
3. Index entries with has_profile=true have matching race-data files
4. No duplicate slugs in the index
5. Index fields are consistent with profile data
"""

import json
import pytest
from pathlib import Path

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"
INDEX_PATH = Path(__file__).parent.parent / "web" / "race-index.json"


def load_index():
    """Load race-index.json."""
    if not INDEX_PATH.exists():
        pytest.skip("race-index.json not found")
    return json.loads(INDEX_PATH.read_text())


class TestIndexStructure:
    """Index must be valid and well-formed."""

    def test_index_parses(self):
        """race-index.json must be valid JSON."""
        data = load_index()
        assert isinstance(data, list), "Index must be a JSON array"

    def test_index_not_empty(self):
        """Index must contain races."""
        data = load_index()
        assert len(data) > 100, f"Index has only {len(data)} entries"

    def test_index_entries_have_required_fields(self):
        """Every index entry must have name, slug, tier."""
        data = load_index()
        violations = []
        for i, entry in enumerate(data):
            for field in ["name", "slug", "tier"]:
                if field not in entry:
                    violations.append(f"  Entry {i}: missing '{field}'")

        if violations:
            pytest.fail(f"{len(violations)} entries missing required fields:\n" +
                        "\n".join(violations[:20]))

    def test_no_duplicate_slugs_in_index(self):
        """No two index entries should have the same slug."""
        data = load_index()
        slugs = [e.get("slug", "") for e in data]
        seen = set()
        dupes = set()
        for s in slugs:
            if s in seen:
                dupes.add(s)
            seen.add(s)

        if dupes:
            pytest.fail(f"Duplicate slugs in index: {dupes}")


class TestIndexSync:
    """Index must stay in sync with race-data/ files."""

    def test_all_profiles_in_index(self):
        """Every race-data/*.json file must appear in the index."""
        data = load_index()
        index_slugs = {e["slug"] for e in data if "slug" in e}
        profile_slugs = {f.stem for f in RACE_DATA_DIR.glob("*.json")}

        missing = profile_slugs - index_slugs
        if missing:
            pytest.fail(
                f"{len(missing)} profiles not in index:\n" +
                "\n".join(f"  {s}" for s in sorted(missing))
            )

    def test_profiled_entries_have_flag(self):
        """Index entries for existing profiles must have has_profile=true."""
        data = load_index()
        profile_slugs = {f.stem for f in RACE_DATA_DIR.glob("*.json")}

        wrong_flag = []
        for entry in data:
            slug = entry.get("slug", "")
            if slug in profile_slugs and not entry.get("has_profile"):
                wrong_flag.append(slug)

        if wrong_flag:
            pytest.fail(
                f"{len(wrong_flag)} profiles exist but index says has_profile=false:\n" +
                "\n".join(f"  {s}" for s in sorted(wrong_flag))
            )

    def test_no_phantom_profiles(self):
        """Index entries with has_profile=true must have actual files."""
        data = load_index()
        profile_slugs = {f.stem for f in RACE_DATA_DIR.glob("*.json")}

        phantoms = []
        for entry in data:
            if entry.get("has_profile") and entry.get("slug") not in profile_slugs:
                phantoms.append(entry["slug"])

        if phantoms:
            pytest.fail(
                f"{len(phantoms)} index entries claim has_profile but no file exists:\n" +
                "\n".join(f"  {s}" for s in sorted(phantoms))
            )


class TestIndexDataConsistency:
    """Index data should match profile data."""

    def test_tier_matches_profile(self):
        """Index tier should match profile's gravel_god_rating.tier."""
        data = load_index()
        index_by_slug = {e["slug"]: e for e in data if "slug" in e}

        mismatches = []
        for f in sorted(RACE_DATA_DIR.glob("*.json")):
            slug = f.stem
            if slug not in index_by_slug:
                continue

            profile = json.loads(f.read_text())
            race = profile.get("race", profile)
            rating = race.get("gravel_god_rating", {})
            profile_tier = rating.get("display_tier", rating.get("tier", 0))
            index_tier = index_by_slug[slug].get("tier", 0)

            if profile_tier and index_tier and profile_tier != index_tier:
                mismatches.append(f"  {slug}: profile T{profile_tier} vs index T{index_tier}")

        if mismatches:
            pytest.fail(
                f"{len(mismatches)} tier mismatches between profile and index:\n" +
                "\n".join(mismatches[:20]) +
                "\n\nFix: Run `python scripts/generate_index.py --with-jsonld`"
            )

    def test_score_matches_profile(self):
        """Index overall_score should match profile's gravel_god_rating.overall_score."""
        data = load_index()
        index_by_slug = {e["slug"]: e for e in data if "slug" in e}

        mismatches = []
        for f in sorted(RACE_DATA_DIR.glob("*.json")):
            slug = f.stem
            if slug not in index_by_slug:
                continue

            profile = json.loads(f.read_text())
            race = profile.get("race", profile)
            rating = race.get("gravel_god_rating", {})
            profile_score = rating.get("overall_score", 0)
            index_score = index_by_slug[slug].get("overall_score", 0)

            if profile_score and index_score and profile_score != index_score:
                mismatches.append(
                    f"  {slug}: profile={profile_score} vs index={index_score}"
                )

        if mismatches:
            pytest.fail(
                f"{len(mismatches)} score mismatches between profile and index:\n" +
                "\n".join(mismatches[:20]) +
                "\n\nFix: Run `python scripts/generate_index.py --with-jsonld`"
            )

    def test_discipline_field_present(self):
        """Every index entry must have a discipline field."""
        data = load_index()
        missing = [e["slug"] for e in data if "discipline" not in e]
        if missing:
            pytest.fail(
                f"{len(missing)} entries missing 'discipline' field:\n" +
                "\n".join(f"  {s}" for s in sorted(missing)[:20])
            )

    def test_discipline_values_valid(self):
        """Discipline must be one of: gravel, mtb, bikepacking."""
        data = load_index()
        valid = {"gravel", "mtb", "bikepacking"}
        invalid = [(e["slug"], e.get("discipline")) for e in data
                   if e.get("discipline") not in valid]
        if invalid:
            pytest.fail(
                f"{len(invalid)} entries with invalid discipline:\n" +
                "\n".join(f"  {s}: {d}" for s, d in invalid[:20])
            )

    def test_discipline_matches_profile(self):
        """Index discipline should match profile's gravel_god_rating.discipline."""
        data = load_index()
        index_by_slug = {e["slug"]: e for e in data if "slug" in e}

        mismatches = []
        for f in sorted(RACE_DATA_DIR.glob("*.json")):
            slug = f.stem
            if slug not in index_by_slug:
                continue

            profile = json.loads(f.read_text())
            race = profile.get("race", profile)
            rating = race.get("gravel_god_rating", {})
            profile_disc = rating.get("discipline", "gravel")
            index_disc = index_by_slug[slug].get("discipline", "gravel")

            if profile_disc != index_disc:
                mismatches.append(
                    f"  {slug}: profile={profile_disc} vs index={index_disc}"
                )

        if mismatches:
            pytest.fail(
                f"{len(mismatches)} discipline mismatches between profile and index:\n" +
                "\n".join(mismatches[:20]) +
                "\n\nFix: Run `python scripts/generate_index.py --with-jsonld`"
            )

    def test_bikepacking_races_tagged(self):
        """Known bikepacking races must NOT be tagged as gravel."""
        data = load_index()
        index_by_slug = {e["slug"]: e for e in data if "slug" in e}

        bikepacking_slugs = [
            "tour-divide", "trans-am-bike-race", "transcontinental-race",
            "atlas-mountain-race", "colorado-trail-race", "badlands",
            "torino-nice-rally",
        ]
        wrong = []
        for slug in bikepacking_slugs:
            entry = index_by_slug.get(slug)
            if entry and entry.get("discipline") != "bikepacking":
                wrong.append(f"  {slug}: discipline={entry.get('discipline')}")

        if wrong:
            pytest.fail(
                f"{len(wrong)} bikepacking races mis-tagged:\n" +
                "\n".join(wrong)
            )
