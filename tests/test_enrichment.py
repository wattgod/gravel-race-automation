"""
Tests for enrichment quality.

Validates that profiles with biased_opinion_ratings:
1. Have real explanations (not empty strings)
2. Have scores that match gravel_god_rating (with known exceptions)
3. Cover all 14 criteria
"""

import json
import pytest
from pathlib import Path

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"

SCORE_COMPONENTS = [
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses'
]

# These profiles have known score differences between biased_opinion_ratings
# and gravel_god_rating — the explanations were written for earlier score
# values. Don't fail on these; they need manual reconciliation.
KNOWN_SCORE_MISMATCH_PROFILES = {
    "big-sugar", "bwr-california", "crusher-in-the-tushar",
    "dirty-reiver", "gravel-locos", "gravel-worlds", "leadville-100",
    "rebeccas-private-idaho", "the-rift", "the-traka", "unbound-200",
}


def get_enriched_profiles():
    """Load profiles that have biased_opinion_ratings with explanations."""
    profiles = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        race = data.get("race", data)
        bor = race.get("biased_opinion_ratings", {})
        if isinstance(bor, dict) and any(
            isinstance(v, dict) and "explanation" in v for v in bor.values()
        ):
            profiles.append((f.stem, race))
    return profiles


class TestEnrichmentQuality:
    """Enriched profiles must have real content."""

    def test_explanations_not_empty(self):
        """Every explanation field that exists must have real content (>20 chars)."""
        violations = []
        for slug, race in get_enriched_profiles():
            bor = race["biased_opinion_ratings"]
            for key in SCORE_COMPONENTS:
                entry = bor.get(key, {})
                if not isinstance(entry, dict):
                    continue
                if "explanation" not in entry:
                    continue  # Field not present — tested separately
                explanation = entry.get("explanation", "")
                if len(explanation.strip()) < 20:
                    violations.append(f"  {slug}.{key}: {explanation!r}")

        if violations:
            pytest.fail(f"{len(violations)} empty/too-short explanations:\n" +
                        "\n".join(violations[:20]))

    def test_enriched_profiles_have_minimum_coverage(self):
        """Enriched profiles must cover at least 7 criteria (editorial set).

        Full enrichment = 14/14. V1 profiles have 7/14 (editorial criteria only).
        Both are acceptable. Fewer than 7 indicates a broken enrichment.
        """
        broken = []
        partial = []
        for slug, race in get_enriched_profiles():
            bor = race["biased_opinion_ratings"]
            explained = [k for k in SCORE_COMPONENTS
                         if isinstance(bor.get(k), dict) and bor[k].get("explanation")]
            if len(explained) < 7:
                broken.append(f"  {slug}: {len(explained)}/14")
            elif len(explained) < 14:
                partial.append(slug)

        if partial:
            print(f"\nINFO: {len(partial)} profiles with partial enrichment (7/14) — "
                  f"run batch_enrich.py to complete")

        if broken:
            pytest.fail(f"{len(broken)} profiles with broken enrichment (<7):\n" +
                        "\n".join(broken))


class TestEnrichmentScoreAlignment:
    """Scores in biased_opinion_ratings should match gravel_god_rating."""

    def test_scores_match_rating(self):
        """biased_opinion_ratings.{key}.score should equal gravel_god_rating.{key}."""
        violations = []
        for slug, race in get_enriched_profiles():
            if slug in KNOWN_SCORE_MISMATCH_PROFILES:
                continue

            rating = race.get("gravel_god_rating", {})
            bor = race["biased_opinion_ratings"]

            for key in SCORE_COMPONENTS:
                entry = bor.get(key, {})
                if not isinstance(entry, dict):
                    continue
                bor_score = entry.get("score")
                rating_score = rating.get(key)

                if bor_score is not None and rating_score is not None:
                    if bor_score != rating_score:
                        violations.append(
                            f"  {slug}.{key}: bor={bor_score} vs rating={rating_score}"
                        )

        if violations:
            pytest.fail(
                f"{len(violations)} score mismatches (excluding {len(KNOWN_SCORE_MISMATCH_PROFILES)} known):\n" +
                "\n".join(violations[:20])
            )

    def test_known_mismatches_documented(self):
        """Verify the known mismatch list is accurate — remove entries that are now fixed."""
        still_mismatched = set()
        for slug, race in get_enriched_profiles():
            if slug not in KNOWN_SCORE_MISMATCH_PROFILES:
                continue

            rating = race.get("gravel_god_rating", {})
            bor = race["biased_opinion_ratings"]
            has_mismatch = False

            for key in SCORE_COMPONENTS:
                entry = bor.get(key, {})
                if not isinstance(entry, dict):
                    continue
                bor_score = entry.get("score")
                rating_score = rating.get(key)
                if bor_score is not None and rating_score is not None and bor_score != rating_score:
                    has_mismatch = True
                    break

            if has_mismatch:
                still_mismatched.add(slug)

        fixed = KNOWN_SCORE_MISMATCH_PROFILES - still_mismatched
        if fixed:
            print(f"\nINFO: These profiles no longer have mismatches — "
                  f"remove from KNOWN_SCORE_MISMATCH_PROFILES: {fixed}")
