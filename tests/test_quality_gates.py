"""Test the quality gate functions."""

import pytest
import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from quality_gates import (
    check_slop_phrases,
    check_matti_voice,
    check_specificity,
    check_length_sanity,
    check_required_sections,
    check_source_citations,
    run_all_quality_checks
)


class TestSlopDetection:
    def test_catches_generic_filler(self):
        content = "It's worth noting that this race is truly remarkable."
        result = check_slop_phrases(content)
        assert not result["passed"]
        assert result["slop_count"] >= 2
    
    def test_passes_clean_content(self):
        content = "The race covers 200 miles. Mile 80 is where people break. DNF rate hits 30%."
        result = check_slop_phrases(content)
        assert result["passed"]
    
    def test_catches_ai_enthusiasm(self):
        content = "This amazing opportunity offers a world-class experience."
        result = check_slop_phrases(content)
        assert not result["passed"]
        assert "amazing opportunity" in [s["phrase"] for s in result["slop_found"]]
    
    def test_catches_hedge_words(self):
        content = "It seems like perhaps you might want to consider maybe training more."
        result = check_slop_phrases(content)
        assert not result["passed"]


class TestMattiVoice:
    def test_passes_direct_content(self):
        content = "Your FTP doesn't matter at mile 150. The truth is you'll bonk if you ignore reality. 30% DNF rate. Actually brutal."
        result = check_matti_voice(content)
        assert result["passed"]
        assert result["voice_score"] >= 40
    
    def test_fails_generic_content(self):
        content = "The event offers participants an opportunity to challenge themselves in a supportive environment."
        result = check_matti_voice(content)
        assert result["voice_score"] < 40


class TestSpecificity:
    def test_passes_specific_content(self):
        content = """
        Mile 80-95 is where Unbound breaks people. In 2023, temps hit 103°F.
        u/graveldude42 said "I bonked at mile 130, should have eaten more."
        DNF rate was 35%. https://reddit.com/r/gravelcycling/xyz
        """
        result = check_specificity(content)
        assert result["passed"]
        assert result["details"]["mile_markers"] >= 1
        assert result["details"]["reddit_usernames"] >= 1
    
    def test_fails_vague_content(self):
        content = "The race is challenging with difficult terrain and variable weather conditions throughout."
        result = check_specificity(content)
        assert not result["passed"]


class TestRequiredSections:
    def test_research_has_all_sections(self, sample_research_content):
        result = check_required_sections(sample_research_content, "research")
        assert result["passed"]
    
    def test_research_missing_sections(self):
        content = """
        ## OFFICIAL DATA
        stuff
        ## TERRAIN
        stuff
        """
        result = check_required_sections(content, "research")
        assert not result["passed"]
        assert "WEATHER" in result["missing_sections"]


class TestCitations:
    def test_passes_with_sources(self):
        content = """
        According to https://reddit.com/r/gravelcycling/abc the race is hard.
        TrainerRoad forum https://trainerroad.com/forum/xyz confirms this.
        See also https://unboundgravel.com for official info.
        More at https://youtube.com/watch?v=123
        And https://velonews.com/article
        """
        result = check_source_citations(content)
        assert result["passed"]
        assert result["breakdown"]["reddit"] >= 1
    
    def test_fails_without_sources(self):
        content = "The race is really hard. People say it's brutal. Trust me."
        result = check_source_citations(content)
        assert not result["passed"]


class TestIntegration:
    def test_good_research_passes_all(self, sample_research_content):
        result = run_all_quality_checks(sample_research_content, "research")
        # Should pass most checks
        assert result["checks"]["sections"]["passed"]
        assert result["checks"]["slop"]["passed"]
    
    def test_slop_content_fails(self, slop_content):
        result = run_all_quality_checks(slop_content, "brief")
        assert not result["checks"]["slop"]["passed"]
        assert "slop" in result["critical_failures"]


class TestGoldenFiles:
    """Compare outputs against known-good reference files."""
    
    def test_research_matches_golden(self):
        # This would compare structure/quality against a validated reference
        golden_path = Path(__file__).parent / "golden" / "unbound-200-raw.md"
        if golden_path.exists():
            content = golden_path.read_text()
            result = run_all_quality_checks(content, "research")
            # Golden file should pass all checks
            assert result["overall_passed"] or len(result["critical_failures"]) == 0
        else:
            pytest.skip("Golden file not found")

