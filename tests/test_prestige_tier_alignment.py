"""
Test for prestige/tier alignment.

Catches races where prestige scoring doesn't match tier assignment:
1. High prestige (4-5) stuck in Tier 3 with score >= 70 (likely should be T2)
2. Prestige 5 races not in Tier 1 or 2 (prestige 5 = world-class)
3. Low prestige (1-2) in Tier 1 (unlikely for truly elite events)

These are FLAGS for human review, not automatic failures.
"""

import json
import os
import pytest
from pathlib import Path

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"


def get_all_races():
    """Load all race profiles."""
    races = []
    for fname in sorted(os.listdir(RACE_DATA_DIR)):
        if not fname.endswith('.json'):
            continue
        with open(RACE_DATA_DIR / fname) as f:
            data = json.load(f)
        races.append((fname, data['race']))
    return races


class TestPrestigeTierAlignment:
    """Test that prestige scores align with tier assignments."""

    def test_high_prestige_not_stuck_in_tier3(self):
        """
        Flag: Prestige 4-5 races in Tier 3 with score >= 70.

        These races have high prestige but are stuck in Tier 3.
        If score is 70+, they likely deserve a tier override to T2.

        Acceptable if: tier_override_reason explains why it stays T3.
        """
        violations = []

        for fname, race in get_all_races():
            r = race.get('gravel_god_rating', {})
            prestige = r.get('prestige', 0)
            tier = r.get('tier', 3)
            score = r.get('overall_score', 0)
            has_override = bool(r.get('tier_override_reason'))

            # High prestige + Tier 3 + score >= 70 = suspicious
            if prestige >= 4 and tier == 3 and score >= 70:
                violations.append({
                    'file': fname,
                    'name': race.get('name'),
                    'prestige': prestige,
                    'tier': tier,
                    'score': score,
                    'has_override': has_override,
                })

        if violations:
            msg = "\n\nHIGH PRESTIGE RACES STUCK IN TIER 3 (need review):\n"
            for v in violations:
                msg += f"  - {v['name']}: prestige={v['prestige']}, tier={v['tier']}, score={v['score']}\n"
            msg += "\nFix: Either promote to Tier 2 with tier_override_reason, or lower prestige.\n"
            pytest.fail(msg)

    def test_prestige5_must_be_tier1_or_tier2(self):
        """
        Flag: Prestige 5 races must be Tier 1 or Tier 2.

        Prestige 5 = world-class event (Unbound, Leadville, World Champs).
        These should never be Tier 3.
        """
        violations = []

        for fname, race in get_all_races():
            r = race.get('gravel_god_rating', {})
            prestige = r.get('prestige', 0)
            tier = r.get('tier', 3)

            if prestige == 5 and tier == 3:
                violations.append({
                    'file': fname,
                    'name': race.get('name'),
                    'tier': tier,
                    'score': r.get('overall_score', 0),
                })

        if violations:
            msg = "\n\nPRESTIGE 5 RACES IN TIER 3 (invalid):\n"
            for v in violations:
                msg += f"  - {v['name']}: tier={v['tier']}, score={v['score']}\n"
            msg += "\nFix: Prestige 5 = world-class. Must be Tier 1 or 2.\n"
            pytest.fail(msg)

    def test_low_prestige_tier1_needs_justification(self):
        """
        Flag: Prestige 1-2 races in Tier 1.

        Tier 1 races should have high prestige (4-5).
        Low prestige + Tier 1 suggests either:
        - Prestige is underscored
        - Race doesn't belong in Tier 1
        """
        violations = []

        for fname, race in get_all_races():
            r = race.get('gravel_god_rating', {})
            prestige = r.get('prestige', 0)
            tier = r.get('tier', 3)
            has_override = bool(r.get('tier_override_reason'))

            if prestige <= 2 and tier == 1 and not has_override:
                violations.append({
                    'file': fname,
                    'name': race.get('name'),
                    'prestige': prestige,
                    'score': r.get('overall_score', 0),
                })

        if violations:
            msg = "\n\nLOW PRESTIGE RACES IN TIER 1 (suspicious):\n"
            for v in violations:
                msg += f"  - {v['name']}: prestige={v['prestige']}, score={v['score']}\n"
            msg += "\nFix: Either increase prestige or add tier_override_reason.\n"
            pytest.fail(msg)


class TestKnownMajorRaces:
    """Ensure known major races are properly tiered."""

    # Races that MUST be Tier 1 or 2 (known prestigious events)
    KNOWN_TIER1_RACES = {
        'unbound-200', 'mid-south', 'leadville-100', 'sea-otter-gravel',
        'gravel-worlds', 'crusher-in-the-tushar', 'badlands', 'the-traka',
        'strade-bianche-gran-fondo', 'uci-gravel-worlds',
    }

    KNOWN_TIER2_MINIMUM = {
        'the-rift', 'dirty-reiver', 'grinduro-california', 'grinduro-france',
        'grinduro-germany', 'vermont-overland', 'rasputitsa',
        'paris-to-ancaster', 'bwr-california', 'bwr-asheville', 'bwr-utah',
        'bwr-montana', 'bwr-cedar-city', 'sbt-grvl', 'big-sugar', 'the-rad',
        'migration-gravel-race', 'nova-eroica', 'fnld-grvl',
    }

    def test_known_tier1_races(self):
        """Known Tier 1 races must be Tier 1."""
        violations = []

        for fname, race in get_all_races():
            slug = fname.replace('.json', '')
            if slug not in self.KNOWN_TIER1_RACES:
                continue

            r = race.get('gravel_god_rating', {})
            tier = r.get('tier', 3)

            if tier != 1:
                violations.append({
                    'file': fname,
                    'name': race.get('name'),
                    'tier': tier,
                    'score': r.get('overall_score', 0),
                })

        if violations:
            msg = "\n\nKNOWN TIER 1 RACES NOT IN TIER 1:\n"
            for v in violations:
                msg += f"  - {v['name']}: tier={v['tier']}, score={v['score']}\n"
            pytest.fail(msg)

    def test_known_tier2_minimum(self):
        """Known major races must be at least Tier 2."""
        violations = []

        for fname, race in get_all_races():
            slug = fname.replace('.json', '')
            if slug not in self.KNOWN_TIER2_MINIMUM:
                continue

            r = race.get('gravel_god_rating', {})
            tier = r.get('tier', 3)

            if tier > 2:  # Tier 3 or worse
                violations.append({
                    'file': fname,
                    'name': race.get('name'),
                    'tier': tier,
                    'score': r.get('overall_score', 0),
                })

        if violations:
            msg = "\n\nKNOWN MAJOR RACES STUCK IN TIER 3:\n"
            for v in violations:
                msg += f"  - {v['name']}: tier={v['tier']}, score={v['score']}\n"
            pytest.fail(msg)
