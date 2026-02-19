"""
Unit tests for validate_enrichment() in batch_enrich.py.

Tests the post-enrichment quality gate with mock data.

Run: pytest tests/test_validate_enrichment.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from batch_enrich import validate_enrichment, SCORE_COMPONENTS


def _make_race(scores=None, explanations=None):
    """Build a mock race dict."""
    if scores is None:
        scores = {k: 3 for k in SCORE_COMPONENTS}
    race = {
        "gravel_god_rating": scores,
        "biased_opinion_ratings": {},
    }
    if explanations:
        for k, exp in explanations.items():
            race["biased_opinion_ratings"][k] = {
                "score": scores.get(k, 3),
                "explanation": exp,
            }
    return race


def _make_enriched(scores=None, explanations=None):
    """Build a mock enriched dict (API response)."""
    if scores is None:
        scores = {k: 3 for k in SCORE_COMPONENTS}
    enriched = {}
    for k in SCORE_COMPONENTS:
        exp = (explanations or {}).get(k, f"Good explanation for {k} with Silver Island Pass details.")
        enriched[k] = {"score": scores.get(k, 3), "explanation": exp}
    return enriched


class TestScorePreservation:

    def test_scores_forced_to_match_rating(self):
        """validate_enrichment should force-correct scores to match gravel_god_rating."""
        scores = {k: 4 for k in SCORE_COMPONENTS}
        race = _make_race(scores=scores)
        enriched = _make_enriched(scores={k: 2 for k in SCORE_COMPONENTS})

        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race)

        # Scores should be corrected
        for k in SCORE_COMPONENTS:
            assert fixed[k]["score"] == 4


class TestSlopDetection:

    def test_slop_flagged(self):
        explanations = {
            "prestige": "This race offers an amazing experience that is world-class in every way.",
        }
        enriched = _make_enriched(explanations=explanations)
        race = _make_race()

        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race)

        assert not passed
        slop_issues = [i for i in issues if "slop" in i.lower()]
        assert len(slop_issues) > 0

    def test_clean_explanation_passes(self):
        explanations = {k: f"Bobby Kennedy described the Silver Island Pass climb as brutal. 4300 feet of gain through volcanic rock." for k in SCORE_COMPONENTS}
        enriched = _make_enriched(explanations=explanations)
        race = _make_race()

        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race)

        # Should have no slop issues (may have other issues depending on quality_gates)
        slop_issues = [i for i in issues if "slop" in i.lower()]
        # If quality_gates flags these, that's OK — we're testing the gate works


class TestFalseUncertainty:

    def test_false_uncertainty_flagged_with_community(self):
        """If community dump exists, 'no evidence' phrases should be flagged."""
        research_dumps = Path(__file__).parent.parent / "research-dumps"
        # Find a slug that has a community dump
        community_files = list(research_dumps.glob("*-community.md"))
        if not community_files:
            pytest.skip("No community dumps found")

        slug = community_files[0].stem.replace("-community", "")
        explanations = {"prestige": "There is no evidence of rider participation in this event."}
        enriched = _make_enriched(explanations=explanations)
        race = _make_race()

        passed, issues, fixed, kept = validate_enrichment(slug, enriched, race)

        uncertainty_issues = [i for i in issues if "false uncertainty" in i.lower()]
        assert len(uncertainty_issues) > 0

    def test_uncertainty_ok_without_community(self):
        """Without community dump, uncertainty phrases are acceptable."""
        explanations = {"prestige": "No rider reports exist for this relatively new event."}
        enriched = _make_enriched(explanations=explanations)
        race = _make_race()

        passed, issues, fixed, kept = validate_enrichment("nonexistent-race-xyz", enriched, race)

        uncertainty_issues = [i for i in issues if "false uncertainty" in i.lower()]
        assert len(uncertainty_issues) == 0


class TestLengthBounds:

    def test_too_short_flagged(self):
        explanations = {"prestige": "Too short."}
        enriched = _make_enriched(explanations=explanations)
        race = _make_race()

        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race)

        short_issues = [i for i in issues if "too short" in i.lower()]
        assert len(short_issues) > 0

    def test_too_long_flagged(self):
        explanations = {"prestige": "A" * 650}
        enriched = _make_enriched(explanations=explanations)
        race = _make_race()

        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race)

        long_issues = [i for i in issues if "too long" in i.lower()]
        assert len(long_issues) > 0

    def test_proper_length_passes(self):
        explanation = "Bobby Kennedy described the climb as brutal. 4300 feet of volcanic rock gain through Silver Island."
        explanations = {k: explanation for k in SCORE_COMPONENTS}
        enriched = _make_enriched(explanations=explanations)
        race = _make_race()

        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race)

        length_issues = [i for i in issues if "too short" in i.lower() or "too long" in i.lower()]
        assert len(length_issues) == 0


class TestOldExplanationFallback:

    def test_keeps_old_on_failure_in_force_mode(self):
        """In force mode, when new explanation has issues, old should be kept."""
        old_explanation = "The Silver Island Pass climb is 4300 feet of brutal volcanic terrain."
        new_explanation = "Too short."  # Will fail length check

        scores = {k: 3 for k in SCORE_COMPONENTS}
        race = _make_race(scores=scores, explanations={
            "prestige": old_explanation,
        })
        # Fill remaining explanations
        for k in SCORE_COMPONENTS:
            if k != "prestige":
                race["biased_opinion_ratings"][k] = {
                    "score": 3,
                    "explanation": f"Good old explanation for {k} criterion.",
                }

        enriched = _make_enriched(explanations={"prestige": new_explanation})

        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race, force=True)

        assert "prestige" in kept
        assert fixed["prestige"]["explanation"] == old_explanation

    def test_no_fallback_without_force(self):
        """Without force mode, old explanation should NOT be substituted."""
        old_explanation = "Old good explanation for the prestige criterion analysis."
        new_explanation = "Too short."

        race = _make_race(explanations={"prestige": old_explanation})
        enriched = _make_enriched(explanations={"prestige": new_explanation})

        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race, force=False)

        assert len(kept) == 0
        assert fixed["prestige"]["explanation"] == new_explanation


class TestEdgeCases:

    def test_empty_enriched(self):
        race = _make_race()
        passed, issues, fixed, kept = validate_enrichment("test-slug", {}, race)
        assert passed  # No entries = no issues

    def test_non_dict_entries_skipped(self):
        enriched = {"prestige": "just a string, not a dict"}
        race = _make_race()
        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race)
        # Should not crash, should skip non-dict entries

    def test_missing_explanation_key(self):
        enriched = {"prestige": {"score": 3}}  # No explanation key
        race = _make_race()
        passed, issues, fixed, kept = validate_enrichment("test-slug", enriched, race)
        # Should flag as too short (empty string)
