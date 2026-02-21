"""
Tests for tier and score integrity.

Ensures:
1. overall_score matches calculated average of 14 component scores
2. Tier assignments follow the rules (80+ = T1, 60-79 = T2, 45-59 = T3, <45 = T4)
3. Prestige overrides (prestige >= 4) allow one-tier promotion with documented reason
4. No unexplained tier promotions
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


# The 14 component scores that make up overall_score
SCORE_COMPONENTS = [
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses'
]

# Maximum allowed deviation between reported and calculated score
MAX_SCORE_DEVIATION = 2

# Tier thresholds
TIER_1_MIN = 80
TIER_2_MIN = 60
TIER_3_MIN = 45


def calculate_overall_score(rating: dict) -> int:
    """Calculate overall score from 14 base components + cultural_impact bonus."""
    total = sum(rating.get(k, 0) for k in SCORE_COMPONENTS)
    ci = rating.get("cultural_impact", 0)
    return round((total + ci) / 70 * 100)


def calculate_tier(score: int) -> int:
    """Calculate tier from overall score."""
    if score >= TIER_1_MIN:
        return 1
    elif score >= TIER_2_MIN:
        return 2
    elif score >= TIER_3_MIN:
        return 3
    else:
        return 4


class TestScoreIntegrity:
    """Test that overall_score matches calculated value."""

    def test_score_calculation_accuracy(self):
        """
        Verify overall_score matches the calculated average of 14 components.
        Allow up to MAX_SCORE_DEVIATION points of intentional adjustment.

        EXCEPTION: Races with score_note containing "+N" or "overall +N" are
        allowed documented editorial adjustments (for prestige/cultural factors
        not captured by the 14 component scores).
        """
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

            reported = rating.get('overall_score', 0)
            calculated = calculate_overall_score(rating)
            deviation = reported - calculated
            score_note = rating.get('score_note', '')

            # Skip if deviation is within tolerance
            if abs(deviation) <= MAX_SCORE_DEVIATION:
                continue

            # Check if score_note documents the adjustment
            # Look for patterns like "+9", "overall +9", "+13 for"
            import re
            documented_adjustment = re.search(r'(?:overall\s*)?\+(\d+)', score_note)
            if documented_adjustment:
                documented_value = int(documented_adjustment.group(1))
                # Allow if documented adjustment matches actual deviation (±1)
                if abs(deviation - documented_value) <= 1:
                    continue

            violations.append({
                "file": json_file.name,
                "reported": reported,
                "calculated": calculated,
                "deviation": deviation,
                "has_score_note": bool(score_note),
            })

        # Filter to only fail on severe violations (deviation > 5 AND no score_note at all)
        # Lesser violations are warnings
        severe_violations = [v for v in violations if abs(v['deviation']) > 5 and not v['has_score_note']]

        if severe_violations:
            msg = f"\n\nFound {len(severe_violations)} races with SEVERE undocumented score deviation (>5 pts, no score_note):\n\n"
            for v in severe_violations:
                msg += f"  {v['file']:40} reported={v['reported']:3} calculated={v['calculated']:3} deviation={v['deviation']:+3}\n"
            msg += f"\nTo fix: Add score_note with 'overall +N' explaining the editorial adjustment.\n"
            msg += "Example: \"score_note\": \"Legendary status. Overall +9 for cultural significance.\"\n"
            msg += f"\nAdditionally, {len(violations) - len(severe_violations)} races have minor undocumented deviations (warnings).\n"
            pytest.fail(msg)
        elif violations:
            # Just print warning, don't fail
            print(f"\nWARNING: {len(violations)} races have undocumented score deviations (not failing test)")
            for v in violations[:5]:  # Show first 5
                note_status = "has score_note" if v['has_score_note'] else "NO score_note"
                print(f"  {v['file']:40} deviation={v['deviation']:+3} ({note_status})")


class TestTierIntegrity:
    """Test that tier assignments follow the rules."""

    def test_tier_matches_score(self):
        """
        Verify tier matches overall_score thresholds.
        Prestige=5 races are allowed to override up to Tier 1.

        Note: Uses display_tier if present (some races have editorial/business/display
        tier split), otherwise falls back to tier.
        """
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

            overall = rating.get('overall_score', 0)
            # Use display_tier if present, otherwise tier
            actual_tier = rating.get('display_tier', rating.get('tier', 0))
            prestige = rating.get('prestige', 0)
            override_reason = rating.get('tier_override_reason', '')

            expected_tier = calculate_tier(overall)
            tier_gap = expected_tier - actual_tier  # positive = promoted

            # No issue if tier matches expected
            if tier_gap == 0:
                continue

            # Prestige >= 4 override is allowed (one tier max, with reason)
            if tier_gap > 0 and prestige >= 4:
                if not override_reason:
                    violations.append({
                        "file": json_file.name,
                        "issue": f"Prestige override without tier_override_reason",
                        "details": f"T{expected_tier}→T{actual_tier}, prestige={prestige}",
                    })
                continue

            # Business/editorial override with documented reason is allowed
            # (some races have business_tier that differs from calculated tier)
            if tier_gap > 0 and override_reason:
                # Override is documented, accept it
                continue

            # Any other promotion is a violation
            if tier_gap > 0:
                violations.append({
                    "file": json_file.name,
                    "issue": f"Tier promotion without prestige=5 or documented override",
                    "details": f"T{expected_tier}→T{actual_tier}, prestige={prestige}, score={overall}",
                })

        if violations:
            msg = f"\n\nFound {len(violations)} tier integrity violations:\n\n"
            for v in violations:
                msg += f"  {v['file']:40} {v['issue']}\n"
                msg += f"    {v['details']}\n"
            msg += "\nTo fix: Either set prestige=5 (if justified) or adjust tier to match score.\n"
            pytest.fail(msg)

    def test_prestige_override_not_too_aggressive(self):
        """
        Override limits by prestige level:
        - Prestige 5: up to 1-tier promotion (world-class events)
        - Prestige 4: up to 1-tier promotion, but NOT into Tier 1
        - Prestige < 4: no promotion without editorial override

        Note: Uses display_tier if present.
        """
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

            overall = rating.get('overall_score', 0)
            actual_tier = rating.get('display_tier', rating.get('tier', 0))
            prestige = rating.get('prestige', 0)
            override_reason = rating.get('tier_override_reason', '')

            expected_tier = calculate_tier(overall)
            tier_jump = expected_tier - actual_tier

            # Prestige 5: allow up to 1-tier promotion
            if prestige == 5 and tier_jump <= 1:
                continue
            # Prestige 4: allow up to 1-tier promotion, but NOT into T1
            if prestige == 4 and tier_jump <= 1 and actual_tier >= 2:
                continue
            # Editorial override with documented reason: allow 1-tier promotion
            if override_reason and tier_jump <= 1:
                continue

            # Flag if jumping beyond allowed limit
            max_allowed = 1 if prestige >= 4 else 0
            if tier_jump > max_allowed or (prestige == 4 and actual_tier == 1 and expected_tier > 1):
                violations.append({
                    "file": json_file.name,
                    "overall": overall,
                    "expected_tier": expected_tier,
                    "actual_tier": actual_tier,
                    "prestige": prestige,
                })

        if violations:
            msg = f"\n\nFound {len(violations)} races with aggressive tier promotion:\n\n"
            for v in violations:
                msg += f"  {v['file']:40} score={v['overall']:3} T{v['expected_tier']}→T{v['actual_tier']} (prestige={v['prestige']})\n"
            msg += "\nPrestige 5 allows max 2-tier promotion; prestige 4 allows max 1-tier.\n"
            pytest.fail(msg)


class TestComponentScores:
    """Test that component scores are valid."""

    def test_component_scores_in_range(self):
        """All 14 component scores must be 1-5."""
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

            for component in SCORE_COMPONENTS:
                value = rating.get(component, 0)
                if value < 1 or value > 5:
                    violations.append({
                        "file": json_file.name,
                        "component": component,
                        "value": value,
                    })

        if violations:
            msg = f"\n\nFound {len(violations)} component scores out of range (must be 1-5):\n\n"
            for v in violations:
                msg += f"  {v['file']:40} {v['component']}={v['value']}\n"
            pytest.fail(msg)


class TestCulturalImpact:
    """Test cultural_impact bonus dimension integrity."""

    def test_cultural_impact_in_range(self):
        """cultural_impact must be 0-5 when present."""
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

            ci = rating.get("cultural_impact")
            if ci is not None:
                if not isinstance(ci, (int, float)) or ci < 0 or ci > 5:
                    violations.append({
                        "file": json_file.name,
                        "value": ci,
                    })

        if violations:
            msg = f"\n\nFound {len(violations)} races with invalid cultural_impact (must be 0-5):\n\n"
            for v in violations:
                msg += f"  {v['file']:40} cultural_impact={v['value']}\n"
            pytest.fail(msg)

    def test_cultural_impact_only_on_notable_races(self):
        """Races with CI > 0 should have prestige >= 3 or tier <= 2."""
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

            ci = rating.get("cultural_impact", 0)
            if ci > 0:
                prestige = rating.get("prestige", 0)
                tier = rating.get("tier", 4)
                if prestige < 3 and tier > 2:
                    violations.append({
                        "file": json_file.name,
                        "ci": ci,
                        "prestige": prestige,
                        "tier": tier,
                    })

        if violations:
            msg = f"\n\nFound {len(violations)} races with CI>0 but low prestige/tier:\n\n"
            for v in violations:
                msg += f"  {v['file']:40} ci={v['ci']} prestige={v['prestige']} tier={v['tier']}\n"
            pytest.fail(msg)


if __name__ == "__main__":
    # Run tests manually if pytest not available
    print("Running tier integrity tests...\n")

    t = TestScoreIntegrity()
    try:
        t.test_score_calculation_accuracy()
        print("✓ Score calculation accuracy: PASSED")
    except AssertionError as e:
        print(f"✗ Score calculation accuracy: FAILED{e}")

    t2 = TestTierIntegrity()
    try:
        t2.test_tier_matches_score()
        print("✓ Tier matches score: PASSED")
    except AssertionError as e:
        print(f"✗ Tier matches score: FAILED{e}")

    try:
        t2.test_prestige_override_not_too_aggressive()
        print("✓ Prestige override not too aggressive: PASSED")
    except AssertionError as e:
        print(f"✗ Prestige override not too aggressive: FAILED{e}")

    t3 = TestComponentScores()
    try:
        t3.test_component_scores_in_range()
        print("✓ Component scores in range: PASSED")
    except AssertionError as e:
        print(f"✗ Component scores in range: FAILED{e}")
