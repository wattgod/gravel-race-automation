"""
Schema consistency tests.

Ensures all race profiles have consistent structure and don't contain
non-canonical keys that could cause adapter failures or data loss.
"""

try:
    import pytest
    HAS_PYTEST = True
except ImportError:
    HAS_PYTEST = False
    class pytest:
        @staticmethod
        def skip(msg): raise Exception(f"SKIP: {msg}")
        @staticmethod
        def fail(msg): raise AssertionError(msg)

import json
from pathlib import Path


def get_race_data_dir():
    """Get path to race-data directory."""
    return Path(__file__).parent.parent / "race-data"


# Canonical top-level keys (within 'race' object)
CANONICAL_KEYS = {
    'name', 'slug', 'display_name', 'tagline', 'tldr',
    'vitals', 'climate', 'terrain', 'gravel_god_rating',
    'course_description', 'biased_opinion', 'biased_opinion_ratings',
    'logistics', 'history', 'quotes', 'race_specific',
    'guide_variables', 'training_implications', 'seo',
    'training_plans', 'final_verdict', 'research_metadata',
    'training_config', 'non_negotiables', 'racer_rating',
    'youtube_data',
}

# Keys that Cursor commonly adds but shouldn't
NON_CANONICAL_KEYS = {
    'community_culture', 'equipment', 'media_coverage',
    'social_media', 'registration_url', 'website',
    'race_challenge_tagline', 'course_profile', 'race_history',
}

# Required keys that every race must have
REQUIRED_KEYS = {
    'name', 'slug', 'vitals', 'gravel_god_rating',
}

# Required keys within gravel_god_rating
REQUIRED_RATING_KEYS = {
    'overall_score', 'tier', 'tier_label',
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses',
}


class TestSchemaConsistency:
    """Test that all races follow the canonical schema."""

    def test_no_non_canonical_keys(self):
        """Detect non-canonical keys that could cause data loss in adapters."""
        race_data_dir = get_race_data_dir()
        if not race_data_dir.exists():
            pytest.skip("race-data directory not found")

        violations = []

        for json_file in race_data_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                race_data = data.get('race', data)
            except (json.JSONDecodeError, IOError):
                continue

            # Check for non-canonical keys
            actual_keys = set(race_data.keys())
            bad_keys = actual_keys & NON_CANONICAL_KEYS

            if bad_keys:
                violations.append({
                    "file": json_file.name,
                    "bad_keys": sorted(bad_keys),
                })

        if violations:
            msg = f"\n\nFound {len(violations)} races with non-canonical keys:\n\n"
            for v in violations:
                msg += f"  {v['file']:40} {v['bad_keys']}\n"
            msg += "\nThese keys should be removed or renamed to canonical equivalents.\n"
            msg += "See CURSOR_WORKFLOW.md Stage 3 for canonical schema.\n"
            pytest.fail(msg)

    def test_required_keys_present(self):
        """Ensure all required keys are present."""
        race_data_dir = get_race_data_dir()
        if not race_data_dir.exists():
            pytest.skip("race-data directory not found")

        violations = []

        for json_file in race_data_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                race_data = data.get('race', data)
            except (json.JSONDecodeError, IOError):
                continue

            actual_keys = set(race_data.keys())
            missing = REQUIRED_KEYS - actual_keys

            if missing:
                violations.append({
                    "file": json_file.name,
                    "missing": sorted(missing),
                })

        if violations:
            msg = f"\n\nFound {len(violations)} races missing required keys:\n\n"
            for v in violations:
                msg += f"  {v['file']:40} missing: {v['missing']}\n"
            pytest.fail(msg)

    def test_rating_keys_complete(self):
        """Ensure gravel_god_rating has all required scoring keys."""
        race_data_dir = get_race_data_dir()
        if not race_data_dir.exists():
            pytest.skip("race-data directory not found")

        violations = []

        for json_file in race_data_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                race_data = data.get('race', data)
                rating = race_data.get('gravel_god_rating', {})
            except (json.JSONDecodeError, IOError):
                continue

            actual_keys = set(rating.keys())
            missing = REQUIRED_RATING_KEYS - actual_keys

            if missing:
                violations.append({
                    "file": json_file.name,
                    "missing": sorted(missing),
                })

        if violations:
            msg = f"\n\nFound {len(violations)} races with incomplete gravel_god_rating:\n\n"
            for v in violations:
                msg += f"  {v['file']:40} missing: {v['missing']}\n"
            pytest.fail(msg)

    def test_course_description_not_course_profile(self):
        """Catch Cursor schema drift: course_profile should be course_description."""
        race_data_dir = get_race_data_dir()
        if not race_data_dir.exists():
            pytest.skip("race-data directory not found")

        violations = []

        for json_file in race_data_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                race_data = data.get('race', data)
            except (json.JSONDecodeError, IOError):
                continue

            if 'course_profile' in race_data:
                violations.append(json_file.name)

        if violations:
            msg = f"\n\nFound {len(violations)} races using 'course_profile' instead of 'course_description':\n\n"
            for f in violations:
                msg += f"  {f}\n"
            msg += "\nRename 'course_profile' to 'course_description' (see mid-south.json for reference).\n"
            pytest.fail(msg)

    def test_history_not_race_history(self):
        """Catch Cursor schema drift: race_history should be history."""
        race_data_dir = get_race_data_dir()
        if not race_data_dir.exists():
            pytest.skip("race-data directory not found")

        violations = []

        for json_file in race_data_dir.glob("*.json"):
            try:
                data = json.loads(json_file.read_text())
                race_data = data.get('race', data)
            except (json.JSONDecodeError, IOError):
                continue

            if 'race_history' in race_data:
                violations.append(json_file.name)

        if violations:
            msg = f"\n\nFound {len(violations)} races using 'race_history' instead of 'history':\n\n"
            for f in violations:
                msg += f"  {f}\n"
            msg += "\nRename 'race_history' to 'history' (see mid-south.json for reference).\n"
            pytest.fail(msg)


if __name__ == "__main__":
    print("Running schema consistency tests...\n")

    t = TestSchemaConsistency()

    try:
        t.test_no_non_canonical_keys()
        print("✓ No non-canonical keys: PASSED")
    except AssertionError as e:
        print(f"✗ No non-canonical keys: FAILED{e}")

    try:
        t.test_required_keys_present()
        print("✓ Required keys present: PASSED")
    except AssertionError as e:
        print(f"✗ Required keys present: FAILED{e}")

    try:
        t.test_rating_keys_complete()
        print("✓ Rating keys complete: PASSED")
    except AssertionError as e:
        print(f"✗ Rating keys complete: FAILED{e}")

    try:
        t.test_course_description_not_course_profile()
        print("✓ No course_profile drift: PASSED")
    except AssertionError as e:
        print(f"✗ No course_profile drift: FAILED{e}")

    try:
        t.test_history_not_race_history()
        print("✓ No race_history drift: PASSED")
    except AssertionError as e:
        print(f"✗ No race_history drift: FAILED{e}")
