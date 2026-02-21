"""Tests for video script generator.

Tests real race data across tiers, including edge cases:
- Data-sparse races (22 without strengths/weaknesses)
- The stub race (gravel-grit-n-grind)
- Races with prestige overrides (mid-south)
- to_spoken against real explanations containing years, ranges, dollars
"""

import json
import re
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
    has_sufficient_data,
    estimate_spoken_seconds,
    _parse_cost,
    _convert_numbers,
    _break_long_sentence,
    _truncate_to_sentence,
    _single_num_to_spoken,
    TIER_NAMES,
    MAX_REASONABLE_ENTRY_FEE,
)

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"

# Races chosen to cover different tiers and data completeness levels
COMPLETE_RACES = ["unbound-200", "mid-south", "steamboat-gravel", "bwr-california"]
SPARSE_RACES = ["almanzo-100", "gravel-grit-n-grind", "unbound-xl"]


def _load_test_race(slug):
    """Load a real race for testing."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        pytest.skip(f"Race data not found: {slug}")
    return load_race(slug)


# ---------------------------------------------------------------------------
# TestSpokenCadence — including real-world data regression tests
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

    # --- Year preservation (regression: years were mangled to "N thousand") ---

    def test_years_preserved_2023(self):
        result = _convert_numbers("2023 rain created peanut-butter mud")
        assert "2023" in result
        assert "thousand" not in result

    def test_years_preserved_2024(self):
        result = _convert_numbers("In 2024, the race saw record conditions")
        assert "2024" in result
        assert "thousand" not in result

    def test_years_preserved_possessive(self):
        result = _convert_numbers("900 riders rescued in 2023's mud catastrophe")
        assert "2023's" in result
        assert "thousand's" not in result

    def test_year_with_dollar_still_converts(self):
        """$2024 should still convert — it's a dollar amount, not a year."""
        result = _convert_numbers("Prize purse of $2,024")
        assert "thousand dollars" in result

    # --- Number range handling (regression: "1,200-1,400" mangled) ---

    def test_number_range_spoken(self):
        result = _convert_numbers("1,200-1,400 feet above sea level")
        assert "thousand" in result
        assert "to" in result  # Should be "1.2 thousand to 1.4 thousand"
        # Must NOT contain the raw hyphenated form
        assert "1,200-1,400" not in result

    def test_number_range_not_mangled(self):
        result = _convert_numbers("sits around 1,200-1,400 feet")
        # Should NOT produce "1.2 thousand-1.4 thousand"
        assert "thousand-" not in result

    # --- Real race explanation regression tests ---

    def test_real_explanation_unbound_altitude(self):
        """Unbound altitude explanation mentions 1,200-1,400 feet and years."""
        rd = _load_test_race("unbound-200")
        expl = rd["explanations"]["altitude"]["explanation"]
        result = to_spoken(expl)
        # Should not contain mangled years
        assert "thousand rain" not in result
        assert "thousand's" not in result

    def test_real_explanation_unbound_climate(self):
        """Unbound climate explanation references 2023."""
        rd = _load_test_race("unbound-200")
        expl = rd["explanations"]["climate"]["explanation"]
        result = to_spoken(expl)
        assert "2023" in result or "2 thousand" not in result

    def test_long_sentence_breaking(self):
        long = (
            "This is a very long sentence that has many many words "
            "and keeps going on and on, but eventually it reaches a "
            "natural break point where we can split it"
        )
        result = to_spoken(long)
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
# TestSingleNumToSpoken
# ---------------------------------------------------------------------------


class TestSingleNumToSpoken:
    def test_year_sized_number_converts(self):
        """_single_num_to_spoken does magnitude only, year check is in caller."""
        result = _single_num_to_spoken(2023)
        assert result == "2 thousand"  # Year detection is NOT in this function

    def test_small_returns_none(self):
        assert _single_num_to_spoken(500) is None
        assert _single_num_to_spoken(999) is None

    def test_thousands(self):
        assert _single_num_to_spoken(4000) == "4 thousand"
        assert _single_num_to_spoken(11000) == "11 thousand"
        assert _single_num_to_spoken(1500) == "1.5 thousand"

    def test_millions(self):
        assert _single_num_to_spoken(1000000) == "1 million"


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
# TestTruncateToSentence
# ---------------------------------------------------------------------------


class TestTruncateToSentence:
    def test_short_text_unchanged(self):
        text = "Short."
        assert _truncate_to_sentence(text, 200) == text

    def test_truncates_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence is long."
        result = _truncate_to_sentence(text, 35)
        # Should end at "Second sentence." not mid-word
        assert result.endswith(".")
        assert "Third" not in result

    def test_falls_back_to_word_boundary(self):
        text = "This is one very long sentence without any periods that just keeps going and going"
        result = _truncate_to_sentence(text, 50)
        assert result.endswith("...")
        # Should not cut mid-word
        assert not result[-4].isalpha() or result.endswith("...")

    def test_minimum_length_respected(self):
        text = "A. This is a much longer second sentence that extends past the limit."
        result = _truncate_to_sentence(text, 30)
        # Should NOT truncate to just "A." (too short — less than 1/3 of 30)
        assert len(result) > 10


# ---------------------------------------------------------------------------
# TestHookAnalysis
# ---------------------------------------------------------------------------


class TestHookAnalysis:
    def test_overrated_detection(self):
        rd = _load_test_race("monaco-gravel-race")
        hooks = analyze_hooks(rd)
        angles = [h["angle"] for h in hooks]
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
        rd = _load_test_race("bwr-san-diego")
        hooks = analyze_hooks(rd)
        angles = [h["angle"] for h in hooks]
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

    def test_sparse_race_still_gets_hooks(self):
        """Even data-sparse races should get at least the fallback hook."""
        rd = _load_test_race("almanzo-100")
        hooks = analyze_hooks(rd)
        assert len(hooks) >= 1
        assert hooks[-1]["angle"] == "tier_reveal"


# ---------------------------------------------------------------------------
# TestDataCompleteness
# ---------------------------------------------------------------------------


class TestDataCompleteness:
    """Test that has_sufficient_data correctly identifies sparse races."""

    def test_complete_race_passes_all_formats(self):
        rd = _load_test_race("unbound-200")
        for fmt in ["tier-reveal", "should-you-race", "roast", "suffering-map"]:
            ok, reason = has_sufficient_data(rd, fmt)
            assert ok, f"{fmt} failed: {reason}"

    def test_sparse_race_fails_roast(self):
        rd = _load_test_race("gravel-grit-n-grind")
        ok, reason = has_sufficient_data(rd, "roast")
        assert not ok
        assert "strengths" in reason or "verdict" in reason

    def test_sparse_race_fails_should_you_race(self):
        rd = _load_test_race("gravel-grit-n-grind")
        ok, reason = has_sufficient_data(rd, "should-you-race")
        assert not ok

    def test_sparse_race_passes_tier_reveal(self):
        """Tier reveal only needs scores, which all races have."""
        rd = _load_test_race("almanzo-100")
        ok, _ = has_sufficient_data(rd, "tier-reveal")
        assert ok

    def test_no_zones_fails_suffering_map(self):
        rd = _load_test_race("unbound-200")
        rd["course"]["suffering_zones"] = []
        ok, reason = has_sufficient_data(rd, "suffering-map")
        assert not ok
        assert "suffering" in reason


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
        for section in ["HOOK", "SETUP", "EVIDENCE", "REVEAL", "CTA", "ENGAGEMENT"]:
            assert f"## {section}" in script

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
        assert "93" in script
        assert "The Icons" in script

    def test_no_mangled_years_in_output(self):
        """Regression: years in explanations were converted to 'N thousand'."""
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        assert "2 thousand" not in script
        assert "thousand's" not in script

    def test_different_tier_race(self):
        """Test with a non-T1 race to verify tier name changes."""
        rd = _load_test_race("steamboat-gravel")
        if not rd:
            pytest.skip("steamboat-gravel not found")
        script = fmt_tier_reveal(rd)
        tier_name = TIER_NAMES.get(rd["tier"], "Grassroots")
        assert tier_name in script


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

    def test_always_shows_dimensions_even_for_similar_races(self):
        """Regression: similar races showed only 1 dimension comparison."""
        rd1 = _load_test_race("unbound-200")
        rd2 = _load_test_race("mid-south")
        script = fmt_head_to_head(rd1, rd2)
        # Count dimension comparison blocks (### headers in the breakdown)
        dim_headers = re.findall(r"^### .+$", script, re.MULTILINE)
        assert len(dim_headers) >= 3, (
            f"Expected at least 3 dimension comparisons, got {len(dim_headers)}"
        )

    def test_declares_winner(self):
        rd1 = _load_test_race("unbound-200")
        rd2 = _load_test_race("mid-south")
        script = fmt_head_to_head(rd1, rd2)
        assert "WINNER:" in script or "TIE" in script

    def test_includes_required_sections(self):
        rd1 = _load_test_race("unbound-200")
        rd2 = _load_test_race("mid-south")
        script = fmt_head_to_head(rd1, rd2)
        for section in ["HOOK", "TALE OF THE TAPE", "DIMENSION BREAKDOWN",
                        "VERDICT", "CTA", "ENGAGEMENT"]:
            assert f"## {section}" in script

    def test_handles_identical_scores(self):
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
        for section in ["HOOK", "THE COURSE", "THE SCORES", "STRENGTHS",
                        "WEAKNESSES", "LOGISTICS", "VERDICT", "ALTERNATIVES",
                        "CTA", "ENGAGEMENT"]:
            assert f"## {section}" in script

    def test_includes_duration_estimate(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        assert "5-10 min" in script

    def test_includes_all_14_dimension_labels(self):
        """Verify all 14 dimension labels appear somewhere in the script."""
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        from generate_video_scripts import DIM_LABELS
        for dim, label in DIM_LABELS.items():
            assert label in script, f"Missing dimension label: {label}"

    def test_includes_riff_markers(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        assert "[RIFF HERE" in script

    def test_word_count_in_range(self):
        """Script narration should be roughly 5-10 min worth of words."""
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        seconds = estimate_spoken_seconds(script)
        assert seconds >= 120, f"Too short: {seconds}s of narration"
        assert seconds <= 900, f"Too long: {seconds}s of narration"


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
        assert "Icon" in script

    def test_includes_lowest_scores(self):
        rd = _load_test_race("unbound-200")
        script = fmt_roast(rd)
        assert "THE NUMBERS DON'T LIE" in script
        assert "/5" in script

    def test_includes_required_sections(self):
        rd = _load_test_race("unbound-200")
        script = fmt_roast(rd)
        for section in ["HOOK", "THE BOTTOM LINE", "CTA", "ENGAGEMENT"]:
            assert f"## {section}" in script

    def test_no_placeholder_text_for_complete_race(self):
        """Complete races should never show placeholder text."""
        rd = _load_test_race("unbound-200")
        script = fmt_roast(rd)
        assert "We struggled to find highlights" not in script
        assert "every race has its issues" not in script


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
        assert "THE ICONS" in script
        assert "ELITE" in script

    def test_includes_actual_total_count(self):
        """Regression: CTA hardcoded '328' instead of using actual count."""
        races = load_all_races()
        script = fmt_data_drops(races)
        actual_count = str(len(races))
        # Count should appear in both the header and the CTA
        assert script.count(actual_count) >= 2

    def test_includes_database_header(self):
        races = load_all_races()
        script = fmt_data_drops(races)
        assert "Data Drops" in script
        assert "DATABASE:" in script

    def test_no_unreasonable_costs(self):
        """Regression: $590,000 appeared as 'most expensive entry fee'."""
        races = load_all_races()
        script = fmt_data_drops(races)
        # Extract the most expensive race's cost from the script
        cost_match = re.search(r"MOST EXPENSIVE:.*?(\$[\d,]+)", script)
        if cost_match:
            cost_val = int(cost_match.group(1).replace("$", "").replace(",", ""))
            assert cost_val <= MAX_REASONABLE_ENTRY_FEE, (
                f"Most expensive cost {cost_val} exceeds sanity cap {MAX_REASONABLE_ENTRY_FEE}"
            )


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

    def test_sanity_cap_rejects_prize_purse(self):
        """Regression: $590,000 prize purse parsed as entry fee."""
        assert _parse_cost("$590,000") is None

    def test_sanity_cap_allows_reasonable_fee(self):
        assert _parse_cost("$5,000") == 5000
        assert _parse_cost("$9,999") == 9999

    def test_sanity_cap_rejects_above_limit(self):
        assert _parse_cost("$10,001") is None
        assert _parse_cost("$100,000") is None


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
        for i in range(len(races) - 1):
            assert races[i]["tier"] <= races[i + 1]["tier"]


# ---------------------------------------------------------------------------
# TestEstimateSpokenSeconds
# ---------------------------------------------------------------------------


class TestEstimateSpokenSeconds:
    def test_counts_narration_lines(self):
        script = '"One two three four five."\n[VISUAL: Something]\n"Six seven eight."'
        seconds = estimate_spoken_seconds(script)
        # 8 words / 2.5 wps = 3.2 → 3 seconds
        assert seconds >= 2
        assert seconds <= 10

    def test_riff_markers_add_time(self):
        script = '"Word."\n[RIFF HERE — something]\n"Another."'
        seconds = estimate_spoken_seconds(script)
        # 2 words / 2.5 + 10 (riff) = ~11 seconds
        assert seconds >= 10

    def test_real_tier_reveal_duration(self):
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        seconds = estimate_spoken_seconds(script)
        assert 20 <= seconds <= 120, f"Tier reveal duration {seconds}s outside 20-120s range"

    def test_real_should_you_race_duration(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        seconds = estimate_spoken_seconds(script)
        assert 120 <= seconds <= 900, f"Should-you-race duration {seconds}s outside 120-900s range"


# ---------------------------------------------------------------------------
# TestNoMangledOutput — scan all formats for known bad patterns
# ---------------------------------------------------------------------------


class TestNoMangledOutput:
    """Regression tests: scan generated output for patterns that indicate bugs."""

    MANGLED_PATTERNS = [
        (r"\b\d+ thousand['']s\b", "year possessive mangled"),
        (r"\b\d+ thousand rain\b", "year 'rain' mangled"),
        (r"\d+\.?\d* thousand-\d+\.?\d* thousand", "number range mangled"),
    ]

    def test_tier_reveal_no_mangled(self):
        rd = _load_test_race("unbound-200")
        script = fmt_tier_reveal(rd)
        self._check_mangled(script, "tier-reveal/unbound-200")

    def test_roast_no_mangled(self):
        rd = _load_test_race("unbound-200")
        script = fmt_roast(rd)
        self._check_mangled(script, "roast/unbound-200")

    def test_should_you_race_no_mangled(self):
        rd = _load_test_race("unbound-200")
        script = fmt_should_you_race(rd)
        self._check_mangled(script, "should-you-race/unbound-200")

    def test_mid_south_no_mangled(self):
        """Test a different race to catch different data patterns."""
        rd = _load_test_race("mid-south")
        for fmt_fn, name in [(fmt_tier_reveal, "tier-reveal"),
                             (fmt_roast, "roast")]:
            script = fmt_fn(rd)
            self._check_mangled(script, f"{name}/mid-south")

    def _check_mangled(self, script, label):
        for pattern, desc in self.MANGLED_PATTERNS:
            match = re.search(pattern, script)
            assert not match, (
                f"Mangled output in {label}: {desc} — found '{match.group()}'"
            )
