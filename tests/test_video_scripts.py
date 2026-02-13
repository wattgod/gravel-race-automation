"""Tests for video script generator."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_video_scripts import (
    to_spoken,
    analyze_hooks,
    fmt_tier_reveal,
    fmt_head_to_head,
    fmt_should_you_race,
    fmt_roast,
    fmt_suffering_map,
    fmt_data_drops,
    load_race,
    load_all_races,
    _parse_cost,
    _convert_numbers,
    _break_long_sentence,
    TIER_NAMES,
)

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"


def _load_test_race(slug):
    """Load a real race for testing."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        pytest.skip(f"Race data not found: {slug}")
    return load_race(slug)


# ---------------------------------------------------------------------------
# TestSpokenCadence
# ---------------------------------------------------------------------------


class TestSpokenCadence:
    def test_empty_input(self):
        assert to_spoken("") == ""
        assert to_spoken(None) == ""

    def test_em_dash_conversion(self):
        result = to_spoken("First part — second part")
        assert "—" not in result
        assert "." in result

    def test_en_dash_conversion(self):
        result = to_spoken("First part – second part")
        assert "–" not in result

    def test_parenthetical_removal(self):
        result = to_spoken("The race (founded in 2006) is great")
        assert "(founded in 2006)" not in result
        assert "race" in result
        assert "great" in result

    def test_number_conversion_thousands(self):
        result = _convert_numbers("The elevation is 11,000 feet")
        assert "11 thousand" in result
        assert "11,000" not in result

    def test_number_conversion_dollars(self):
        result = _convert_numbers("Entry costs $1,500")
        assert "1.5 thousand dollars" in result

    def test_number_conversion_small_number_unchanged(self):
        result = _convert_numbers("Only 200 riders")
        assert "200" in result

    def test_number_conversion_large(self):
        result = _convert_numbers("Over 1,000,000 views")
        assert "million" in result

    def test_long_sentence_breaking(self):
        long = (
            "This is a very long sentence that has many many words "
            "and keeps going on and on, but eventually it reaches a "
            "natural break point where we can split it"
        )
        result = to_spoken(long)
        # Should have been broken at ", but"
        sentences = [s.strip() for s in result.split(".") if s.strip()]
        assert len(sentences) >= 2

    def test_short_sentence_unchanged(self):
        short = "This is a short sentence."
        result = to_spoken(short)
        assert result == short

    def test_double_period_cleanup(self):
        result = to_spoken("End of sentence.. Start of next.")
        assert ".." not in result

    def test_preserves_basic_content(self):
        text = "Emporia is affordable. Hotels sell out early."
        result = to_spoken(text)
        assert "Emporia" in result
        assert "affordable" in result


# ---------------------------------------------------------------------------
# TestBreakLongSentence
# ---------------------------------------------------------------------------


class TestBreakLongSentence:
    def test_break_at_semicolon(self):
        sent = "The first half is easy; the second half will break you completely and leave you wrecked"
        result = _break_long_sentence(sent)
        assert "." in result

    def test_break_at_but(self):
        sent = "The race looks straightforward on paper, but the wind and heat and distance combine to make it brutal"
        result = _break_long_sentence(sent)
        assert "." in result

    def test_no_break_needed(self):
        sent = "Short and sweet."
        result = _break_long_sentence(sent)
        assert result == sent


# ---------------------------------------------------------------------------
# TestHookAnalysis
# ---------------------------------------------------------------------------


class TestHookAnalysis:
    def test_overrated_detection(self):
        rd = _load_test_race("unbound-200")
        hooks = analyze_hooks(rd)
        angles = [h["angle"] for h in hooks]
        # Unbound has prestige 5, expenses 2 → should trigger overrated
        assert "overrated" in angles

    def test_hidden_gem_detection(self):
        """Find a race with high adventure, low prestige."""
        races = load_all_races()
        found = False
        for rd in races:
            scores = {d: rd["explanations"][d]["score"] for d in ["adventure", "prestige"]}
            if scores["adventure"] >= 4 and scores["prestige"] <= 2:
                hooks = analyze_hooks(rd)
                angles = [h["angle"] for h in hooks]
                assert "hidden_gem" in angles
                found = True
                break
        if not found:
            pytest.skip("No hidden gem race found in dataset")

    def test_prestige_override(self):
        rd = _load_test_race("mid-south")
        hooks = analyze_hooks(rd)
        angles = [h["angle"] for h in hooks]
        # Mid South has tier_override_reason mentioning "Prestige"
        assert "prestige_override" in angles

    def test_fallback_always_present(self):
        rd = _load_test_race("unbound-200")
        hooks = analyze_hooks(rd)
        angles = [h["angle"] for h in hooks]
        assert "tier_reveal" in angles

    def test_hook_structure(self):
        rd = _load_test_race("unbound-200")
        hooks = analyze_hooks(rd)
        for hook in hooks:
            assert "angle" in hook
            assert "tension_text" in hook
            assert "engagement_question" in hook
            assert len(hook["tension_text"]) > 10
            assert hook["engagement_question"].endswith(("?", "."))


# ---------------------------------------------------------------------------
# TestTierReveal
# ---------------------------------------------------------------------------


class TestTierReveal:
    def test_generates_valid_markdown(self):
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        assert script.startswith("# FORMAT: Tier Reveal")
        assert "Unbound" in script

    def test_includes_required_sections(self):
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        assert "## HOOK" in script
        assert "## SETUP" in script
        assert "## EVIDENCE" in script
        assert "## REVEAL" in script
        assert "## CTA" in script
        assert "## ENGAGEMENT" in script

    def test_includes_riff_markers(self):
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        assert "[RIFF HERE" in script

    def test_includes_slug_in_cta(self):
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        assert "gravelgodcycling.com/race/unbound-200" in script

    def test_includes_tier_and_score(self):
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        assert "80" in script  # score
        assert "Elite" in script  # tier name

    def test_includes_visual_notes(self):
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        assert "**VISUAL NOTES:**" in script


# ---------------------------------------------------------------------------
# TestHeadToHead
# ---------------------------------------------------------------------------


class TestHeadToHead:
    def test_generates_comparison(self):
        rd1 = _load_test_race("unbound-200")
        rd2 = _load_test_race("mid-south")
        script = fmt_head_to_head(rd1, rd2)
        assert "Head-to-Head" in script
        assert "Unbound" in script
        assert "Mid South" in script

    def test_finds_dimension_differences(self):
        rd1 = _load_test_race("unbound-200")
        rd2 = _load_test_race("mid-south")
        script = fmt_head_to_head(rd1, rd2)
        # Should have at least one dimension comparison with scores
        assert "/5" in script

    def test_declares_winner(self):
        rd1 = _load_test_race("unbound-200")
        rd2 = _load_test_race("mid-south")
        script = fmt_head_to_head(rd1, rd2)
        assert "WINNER:" in script or "TIE" in script

    def test_includes_required_sections(self):
        rd1 = _load_test_race("unbound-200")
        rd2 = _load_test_race("mid-south")
        script = fmt_head_to_head(rd1, rd2)
        assert "## HOOK" in script
        assert "## TALE OF THE TAPE" in script
        assert "## DIMENSION BREAKDOWN" in script
        assert "## VERDICT" in script
        assert "## CTA" in script
        assert "## ENGAGEMENT" in script

    def test_handles_identical_scores(self):
        """If two races have the same tier and score, should declare a tie."""
        rd = _load_test_race("unbound-200")
        script = fmt_head_to_head(rd, rd)
        assert "TIE" in script or "Dead heat" in script


# ---------------------------------------------------------------------------
# TestShouldYouRace
# ---------------------------------------------------------------------------


class TestShouldYouRace:
    def test_generates_all_sections(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        assert "## HOOK" in script
        assert "## THE COURSE" in script
        assert "## THE SCORES" in script
        assert "## STRENGTHS" in script
        assert "## WEAKNESSES" in script
        assert "## LOGISTICS" in script
        assert "## VERDICT" in script
        assert "## ALTERNATIVES" in script
        assert "## CTA" in script
        assert "## ENGAGEMENT" in script

    def test_includes_duration_estimate(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        assert "5-10 min" in script

    def test_includes_all_14_dimensions(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        # Top 8 highlighted + remaining 6 listed
        assert "Top 8 Dimensions" in script
        assert "Also Scored" in script

    def test_includes_riff_markers(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        assert "[RIFF HERE" in script

    def test_includes_youtube_format(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        assert "YouTube" in script


# ---------------------------------------------------------------------------
# TestRoast
# ---------------------------------------------------------------------------


class TestRoast:
    def test_splits_strengths_weaknesses(self):
        rd = _load_test_race("unbound-200")
        script = fmt_roast(rd)
        assert "WHAT THEY TELL YOU" in script
        assert "WHAT THEY DON'T TELL YOU" in script

    def test_includes_verdict_label(self):
        rd = _load_test_race("unbound-200")
        script = fmt_roast(rd)
        # Unbound's verdict is "Icon"
        assert "Icon" in script

    def test_includes_lowest_scores(self):
        rd = _load_test_race("unbound-200")
        script = fmt_roast(rd)
        assert "THE NUMBERS DON'T LIE" in script
        # Should include the lowest-scoring dimensions
        assert "/5" in script

    def test_includes_required_sections(self):
        rd = _load_test_race("unbound-200")
        script = fmt_roast(rd)
        assert "## HOOK" in script
        assert "## THE BOTTOM LINE" in script
        assert "## CTA" in script
        assert "## ENGAGEMENT" in script


# ---------------------------------------------------------------------------
# TestSufferingMap
# ---------------------------------------------------------------------------


class TestSufferingMap:
    def test_narrates_zones(self):
        rd = _load_test_race("unbound-200")
        script = fmt_suffering_map(rd)
        assert script is not None
        assert "MILE" in script
        assert "Suffering Map" in script

    def test_skips_races_without_zones(self):
        rd = _load_test_race("unbound-200")
        # Simulate no zones
        rd["course"]["suffering_zones"] = []
        script = fmt_suffering_map(rd)
        assert script is None

    def test_includes_all_zones(self):
        rd = _load_test_race("unbound-200")
        zones = rd["course"]["suffering_zones"]
        if not zones:
            pytest.skip("No suffering zones")
        script = fmt_suffering_map(rd)
        for zone in zones:
            label = zone.get("label", zone.get("named_section", ""))
            if label:
                assert label in script

    def test_duration_scales_with_zones(self):
        rd = _load_test_race("unbound-200")
        zones = rd["course"]["suffering_zones"]
        if not zones:
            pytest.skip("No suffering zones")
        script = fmt_suffering_map(rd)
        expected_duration = max(15, min(60, len(zones) * 12))
        assert f"~{expected_duration}s" in script

    def test_includes_engagement(self):
        rd = _load_test_race("unbound-200")
        script = fmt_suffering_map(rd)
        if script:
            assert "## ENGAGEMENT" in script
            assert "mile marker" in script.lower() or "zone" in script.lower()


# ---------------------------------------------------------------------------
# TestDataDrops
# ---------------------------------------------------------------------------


class TestDataDrops:
    def test_generates_multiple_drops(self):
        races = load_all_races()
        script = fmt_data_drops(races)
        assert script.count("## DROP:") >= 5

    def test_includes_tier_stats(self):
        races = load_all_races()
        script = fmt_data_drops(races)
        assert "Elite" in script or "ELITE" in script
        assert "Contender" in script or "CONTENDER" in script

    def test_includes_total_count(self):
        races = load_all_races()
        script = fmt_data_drops(races)
        assert str(len(races)) in script

    def test_includes_database_header(self):
        races = load_all_races()
        script = fmt_data_drops(races)
        assert "Data Drops" in script
        assert "DATABASE:" in script

    def test_includes_cta(self):
        races = load_all_races()
        script = fmt_data_drops(races)
        assert "gravelgodcycling.com" in script


# ---------------------------------------------------------------------------
# TestParseCost
# ---------------------------------------------------------------------------


class TestParseCost:
    def test_parse_dollar_amount(self):
        assert _parse_cost("$345") == 345

    def test_parse_with_comma(self):
        assert _parse_cost("$1,500") == 1500

    def test_parse_none(self):
        assert _parse_cost(None) is None

    def test_parse_empty(self):
        assert _parse_cost("") is None

    def test_parse_no_dollar_sign(self):
        assert _parse_cost("345") == 345


# ---------------------------------------------------------------------------
# TestLoadRace
# ---------------------------------------------------------------------------


class TestLoadRace:
    def test_load_existing_race(self):
        rd = load_race("unbound-200")
        assert rd is not None
        assert rd["slug"] == "unbound-200"
        assert rd["overall_score"] > 0

    def test_load_nonexistent_race(self):
        rd = load_race("nonexistent-race-99999")
        assert rd is None

    def test_load_all_races_sorted(self):
        races = load_all_races()
        assert len(races) > 100
        # Should be sorted by tier first
        for i in range(len(races) - 1):
            assert races[i]["tier"] <= races[i + 1]["tier"]
