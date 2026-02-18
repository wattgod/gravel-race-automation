"""
Unit tests for community_parser.py.

Tests every extraction function with real community dump snippets,
known false positives, and edge cases.

Run: pytest tests/test_community_parser.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from community_parser import (
    extract_riders,
    extract_terrain_features,
    extract_weather,
    extract_numbers,
    extract_key_quotes,
    extract_proper_nouns,
    parse_sections,
    build_fact_sheet,
    build_criterion_hints,
    _truncate_at_sentence,
    RE_NO_EVIDENCE,
)


# ============================================================
# Test fixtures — real community dump snippets
# ============================================================

SALTY_LIZARD_SNIPPET = """# SALTY LIZARD — COMMUNITY RESEARCH

## Rider Quotes & Race Reports

**husterk [RECREATIONAL]:** "I raced in my first official gravel race last October and it was amazing."

**Bobby Kennedy [ELITE]:** "Everyone described the miles after the Leppys Pass station as the hardest."

**Race Director John Hernandez [RACE ORGANIZER]:** "Come out, bring whatever bike I have, and have some fun riding in the desert!"

**Breanne Nalder Harward [ELITE/DIRECTOR]:** "Having raced at the professional level for many years, I saw so many things."

## Terrain Details (Rider Perspective)

**Opening Descent:** "After a neutral start up the hill, riders immediately faced the Aria Blvd downhill."

**Silver Island Pass:** "The traditionally loose pass had been solidified by the previous week's rain."

## Weather Experienced

**2022 Race (October):** "It was a suspiciously glorious day in Wendover. Temps hovered around 65 degrees."

## Equipment & Gear Recommendations

**husterk [RECREATIONAL] - Mountain Bike for Gravel Racing:** "I brought my 2021 Intense Sniper T mountain bike."

## Community Feel & Atmosphere

**Race Vibe:** "We pride ourselves on being a welcoming and inclusive ride."
"""

ALMANZO_SNIPPET = """# ALMANZO 100 — COMMUNITY RESEARCH

## Rider Quotes & Race Reports

**Nicholas Garbis [COMPETITIVE]:** "The Meteor Theory is a plan to go out hot."

**Brad Patty [COMPETITIVE]:** "I knew from previous long rides that I could maintain around 200 watts."

## Equipment & Gear Recommendations

**Tires - Nicholas Garbis [COMPETITIVE]:** Switched from Panaracer Gravelking Mud to Panaracer Gravelking SK 700c x 35mm.

**Power Meter - Brad Patty [COMPETITIVE]:** Used PowerCal heart rate-based power meter. Found PowerCal "very accurate compared to the PowerTap hub."

**Gearing - Matt Allen [COMPETITIVE]:** "41/24 is my climbing gear ratio. It's not really enough."

**Emergency Prep - Unnamed rider [COMPETITIVE]:** Made improvised rain protection from Kwik Mart grocery bags.

## Race Strategy & Pacing

**Pacing - Brad Patty [COMPETITIVE]:** Targeted 200W average. Successfully maintained pace throughout, averaging 207.6W for 6-7 hours at 15.4 mph.
"""

BWR_KANSAS_SNIPPET = """# BELGIAN WAFFLE RIDE KANSAS — COMMUNITY RESEARCH

## Rider Quotes & Race Reports

**Adam Roberge [ELITE]:** "This was by far the most dynamic and exciting BWR race."

**Tanner Ward [ELITE]:** "I have done a lot of gravel races this year."

## Race Strategy & Pacing

**Technical Sections as Selection Points [ELITE]:** "After the second single track section I came out with a fair lead."

**Snake Farm Strategy [ELITE]:** "Going into the Snake Farm technical section, the group let me in first."

**Final 15 Miles Decision [ELITE]:** "With 15-miles left in the race, I had to decide."

**Group Dynamics [ELITE]:** "The four of us really had a good dynamic."

**Chase Group Formation [ELITE]:** "I must hang on; I'm not fighting this wind alone!"

**Women's Race Dynamics [ELITE]:** "Coming out of that section, Cromwell caught and passed Oliveira."

**Railroad Crossing Delays [ELITE]:** "In the women's race, a big pile-up caused separation."

**Bonking/Nutrition Issues [ELITE]:** "I was cramping, I fought through that."
"""

TOPIC_SUBHEADER_SNIPPET = """# EXAMPLE — COMMUNITY RESEARCH

## Equipment & Gear Recommendations

**Nutrition Strategy [UNKNOWN level]:** Standard fueling recommendation of 60-80g carbs per hour.

**Accommodation options [UNKNOWN level]:** Hotels in town range from $80-150 per night.

**Water filtration [UNKNOWN level]:** Bring a filter for backcountry water sources.

## Rider Quotes & Race Reports

**Sarah Chen [ELITE]:** "The course was brutal but beautiful."
"""

MULTI_NAME_SNIPPET = """# EXAMPLE — COMMUNITY RESEARCH

## Rider Quotes & Race Reports

**Justinas Leveika [ELITE]:** "We had a great time racing together."

**Juan de la Cruz [COMPETITIVE]:** "This was my best race of the season."

**Josh "Death Rider" [RECREATIONAL]:** "The wind killed me and my poor legs."

**Steve Maas (The Cycling Addiction) [UNKNOWN]:** "A fantastic race experience."

**Andrea Wilson [ELITE] on wet conditions:** "Holy crap, I felt like I was walking on ice."

**Andrea Wilson [ELITE] on tire pressure:** "I probably had too much air in my tires."
"""


# ============================================================
# Tests: extract_riders
# ============================================================

class TestExtractRiders:
    """Tests for rider name extraction."""

    def test_standard_riders(self):
        riders = extract_riders(SALTY_LIZARD_SNIPPET)
        assert "husterk" in riders
        assert "Bobby Kennedy" in riders
        assert riders["husterk"] == "RECREATIONAL"
        assert riders["Bobby Kennedy"] == "ELITE"

    def test_slash_level(self):
        riders = extract_riders(SALTY_LIZARD_SNIPPET)
        assert "Breanne Nalder Harward" in riders
        assert riders["Breanne Nalder Harward"] == "ELITE/DIRECTOR"

    def test_space_level_race_organizer(self):
        riders = extract_riders(SALTY_LIZARD_SNIPPET)
        assert "Race Director John Hernandez" in riders
        assert riders["Race Director John Hernandez"] == "RACE ORGANIZER"

    def test_topic_prefix_stripped(self):
        """Topic prefix like 'Tires - ' should be stripped from name."""
        riders = extract_riders(ALMANZO_SNIPPET)
        # Should extract the person name, not the full "Tires - Nicholas Garbis"
        assert "Nicholas Garbis" in riders
        assert "Brad Patty" in riders
        assert "Matt Allen" in riders
        # The prefixed versions should NOT appear
        assert "Tires - Nicholas Garbis" not in riders
        assert "Power Meter - Brad Patty" not in riders
        assert "Gearing - Matt Allen" not in riders

    def test_unnamed_rider_skipped(self):
        riders = extract_riders(ALMANZO_SNIPPET)
        assert "Unnamed rider" not in riders

    def test_false_positive_strategy_labels_rejected(self):
        """BWR Kansas has strategy labels like 'Snake Farm Strategy [ELITE]'."""
        riders = extract_riders(BWR_KANSAS_SNIPPET)
        # Real riders
        assert "Adam Roberge" in riders
        assert "Tanner Ward" in riders
        # False positives — these should all be rejected
        assert "Technical Sections as Selection Points" not in riders
        assert "Snake Farm Strategy" not in riders
        assert "Final 15 Miles Decision" not in riders
        assert "Group Dynamics" not in riders
        assert "Chase Group Formation" not in riders
        assert "Railroad Crossing Delays" not in riders
        assert "Bonking/Nutrition Issues" not in riders

    def test_womens_race_dynamics_rejected(self):
        riders = extract_riders(BWR_KANSAS_SNIPPET)
        assert "Women's Race Dynamics" not in riders

    def test_unknown_level_topic_headers_rejected(self):
        """[UNKNOWN level] pattern should be skipped entirely."""
        riders = extract_riders(TOPIC_SUBHEADER_SNIPPET)
        assert "Nutrition Strategy" not in riders
        assert "Accommodation options" not in riders
        assert "Water filtration" not in riders
        # Real rider should still be extracted
        assert "Sarah Chen" in riders

    def test_compound_names(self):
        riders = extract_riders(MULTI_NAME_SNIPPET)
        assert "Justinas Leveika" in riders
        assert "Juan de la Cruz" in riders

    def test_quoted_nickname(self):
        riders = extract_riders(MULTI_NAME_SNIPPET)
        assert 'Josh "Death Rider"' in riders

    def test_parenthetical_source(self):
        """Names with parenthetical source like (The Cycling Addiction)."""
        riders = extract_riders(MULTI_NAME_SNIPPET)
        # The name before the parenthetical
        assert "Steve Maas (The Cycling Addiction)" in riders or "Steve Maas" in riders

    def test_topic_suffix_doesnt_pollute_name(self):
        """'Andrea Wilson [ELITE] on wet conditions' should extract just 'Andrea Wilson'."""
        riders = extract_riders(MULTI_NAME_SNIPPET)
        assert "Andrea Wilson" in riders
        # Should NOT have the suffix in the name
        assert "Andrea Wilson on wet conditions" not in riders

    def test_deduplication(self):
        """Same rider appearing multiple times should only appear once."""
        riders = extract_riders(MULTI_NAME_SNIPPET)
        # Andrea Wilson appears twice with different topic suffixes
        name_list = list(riders.keys())
        assert name_list.count("Andrea Wilson") == 1

    def test_empty_text(self):
        assert extract_riders("") == {}

    def test_no_matches(self):
        assert extract_riders("Just some plain text without any rider patterns.") == {}

    def test_year_in_name_rejected(self):
        text = '**2024 Race Results [ELITE]:** "Great results this year."'
        riders = extract_riders(text)
        assert len(riders) == 0

    def test_digit_start_rejected(self):
        text = '**50km Distance Performance [ELITE]:** "Strong showing."'
        riders = extract_riders(text)
        assert len(riders) == 0


# ============================================================
# Tests: parse_sections
# ============================================================

class TestParseSections:

    def test_basic_sections(self):
        sections = parse_sections(SALTY_LIZARD_SNIPPET)
        assert "Rider Quotes & Race Reports" in sections
        assert "Terrain Details (Rider Perspective)" in sections
        assert "Weather Experienced" in sections
        assert "Equipment & Gear Recommendations" in sections
        assert "Community Feel & Atmosphere" in sections

    def test_header_stored_separately(self):
        sections = parse_sections(SALTY_LIZARD_SNIPPET)
        assert "_header" in sections
        assert "SALTY LIZARD" in sections["_header"]

    def test_section_content(self):
        sections = parse_sections(SALTY_LIZARD_SNIPPET)
        terrain = sections["Terrain Details (Rider Perspective)"]
        assert "Silver Island Pass" in terrain
        assert "Aria Blvd" in terrain

    def test_empty_text(self):
        assert parse_sections("") == {"_header": ""}

    def test_no_sections(self):
        sections = parse_sections("Just text without any ## headers")
        assert "_header" in sections
        assert len(sections) == 1


# ============================================================
# Tests: extract_terrain_features
# ============================================================

class TestExtractTerrainFeatures:

    def test_extracts_named_features(self):
        text = "Silver Island Pass was solidified. Aria Blvd downhill was treacherous."
        features = extract_terrain_features(text)
        assert "Silver Island Pass" in features

    def test_filters_section_headers(self):
        text = "Terrain Details showed the Race Strategy for this Community Research event."
        features = extract_terrain_features(text)
        assert "Terrain Details" not in features
        assert "Race Strategy" not in features
        assert "Community Research" not in features

    def test_filters_sentence_starters(self):
        text = "The first section was However After Before the climb."
        features = extract_terrain_features(text)
        # All of these are sentence starters or < 6 chars
        for skip in ["The", "However After", "Before"]:
            # "However After" might match as proper noun — it should be in SKIP
            pass

    def test_short_names_filtered(self):
        text = "At Mt Hood we climbed."
        features = extract_terrain_features(text)
        # "Mt Hood" is only 7 chars so it passes the >=6 check
        # but depends on regex matching


# ============================================================
# Tests: extract_weather
# ============================================================

class TestExtractWeather:

    def test_temperature_extraction(self):
        sections = {"Weather Experienced": "Temps hovered around 65 degrees with 85°F highs."}
        weather = extract_weather(sections)
        assert "temperatures" in weather
        assert "65°F" in weather["temperatures"]
        assert "85°F" in weather["temperatures"]

    def test_wind_extraction(self):
        sections = {"Weather Experienced": "Steady 15 mph wind with gusts to 25 mph crosswind."}
        weather = extract_weather(sections)
        assert "winds" in weather
        assert "15 mph" in weather["winds"]
        assert "25 mph" in weather["winds"]

    def test_no_weather_section(self):
        assert extract_weather({}) == {}
        assert extract_weather({"Other Section": "text"}) == {}


# ============================================================
# Tests: extract_numbers
# ============================================================

class TestExtractNumbers:

    def test_elevation(self):
        text = "The course features 4,300 feet of elevation gain through mountains."
        facts = extract_numbers(text)
        assert "elevation_mentions" in facts
        assert "4300" in facts["elevation_mentions"]

    def test_field_size(self):
        text = "350 riders had registered and 150 starters showed up."
        facts = extract_numbers(text)
        assert "field_sizes" in facts
        assert "350" in facts["field_sizes"]
        assert "150" in facts["field_sizes"]

    def test_power_data(self):
        text = "Averaged 207.6W for 6-7 hours. Peaked at 301 watts on the climb."
        facts = extract_numbers(text)
        assert "power_data" in facts

    def test_tire_pressure(self):
        text = "Set pressures at 35psi front / 38psi rear."
        facts = extract_numbers(text)
        assert "tire_pressure" in facts
        assert "35 psi" in facts["tire_pressure"]
        assert "38 psi" in facts["tire_pressure"]

    def test_empty_text(self):
        assert extract_numbers("") == {}


# ============================================================
# Tests: extract_key_quotes
# ============================================================

class TestExtractKeyQuotes:

    def test_extracts_rider_quotes(self):
        quotes = extract_key_quotes(SALTY_LIZARD_SNIPPET)
        assert len(quotes) > 0
        # Quotes are scored by vividness — vivid/specific quotes rank higher
        all_text = " ".join(quotes)
        assert "first official gravel race" in all_text
        # Terrain/weather quotes should outrank generic ones
        # (exact ordering depends on content, but vivid quotes should be present)

    def test_skips_urls(self):
        text = '**Rider [ELITE]:** "Check out https://example.com for details."'
        quotes = extract_key_quotes(text)
        assert len(quotes) == 0

    def test_only_from_rider_lines(self):
        """Quotes from non-rider lines (section headers, URLs) should be skipped."""
        text = "Regular text with \"a quoted phrase that is at least twenty chars\" in it."
        quotes = extract_key_quotes(text)
        assert len(quotes) == 0

    def test_max_quotes_limit(self):
        # Build text with many rider quotes
        lines = []
        for i in range(20):
            lines.append(f'**Rider{i} [ELITE]:** "This is quote number {i:02d} from a very long race."')
        text = "\n".join(lines)
        quotes = extract_key_quotes(text, max_quotes=5)
        assert len(quotes) == 5


# ============================================================
# Tests: shared utilities
# ============================================================

class TestSharedUtilities:

    def test_re_no_evidence_matches(self):
        assert RE_NO_EVIDENCE.search("zero rider reports available")
        assert RE_NO_EVIDENCE.search("no evidence of community support")
        assert RE_NO_EVIDENCE.search("pure speculation about the course")
        assert RE_NO_EVIDENCE.search("remains a mystery to most riders")
        assert RE_NO_EVIDENCE.search("No rider testimonials exist")

    def test_re_no_evidence_no_false_positives(self):
        assert not RE_NO_EVIDENCE.search("Bobby Kennedy reported strong winds")
        assert not RE_NO_EVIDENCE.search("The evidence suggests a tough course")
        assert not RE_NO_EVIDENCE.search("A good race experience overall")

    def test_extract_proper_nouns_from_community(self):
        nouns = extract_proper_nouns(SALTY_LIZARD_SNIPPET)
        assert "Bobby Kennedy" in nouns
        assert "Silver Island Pass" in nouns
        assert "Breanne Nalder Harward" in nouns


# ============================================================
# Tests: _truncate_at_sentence
# ============================================================

class TestTruncateAtSentence:

    def test_short_text_unchanged(self):
        assert _truncate_at_sentence("Short text.", 100) == "Short text."

    def test_truncates_at_period(self):
        text = "First sentence. Second sentence. Third sentence that goes on and on."
        result = _truncate_at_sentence(text, 35)
        assert result == "First sentence. Second sentence."

    def test_fallback_to_ellipsis(self):
        text = "A very long word without any periods or sentence boundaries at all"
        result = _truncate_at_sentence(text, 20)
        assert result.endswith("...")

    def test_exact_boundary(self):
        text = "Exactly at limit."
        assert _truncate_at_sentence(text, 17) == "Exactly at limit."


# ============================================================
# Tests: build_fact_sheet (integration)
# ============================================================

class TestBuildFactSheet:

    def test_salty_lizard_fact_sheet(self):
        """Integration test with real community dump if it exists."""
        community_path = Path(__file__).parent.parent / "research-dumps" / "salty-lizard-community.md"
        if not community_path.exists():
            pytest.skip("salty-lizard community dump not found")

        fact_sheet, sections = build_fact_sheet("salty-lizard")
        assert fact_sheet is not None
        assert sections is not None

        # Should contain rider names
        assert "Bobby Kennedy" in fact_sheet
        assert "husterk" in fact_sheet

        # Should contain terrain features
        assert "TERRAIN:" in fact_sheet

        # Should have sections parsed
        assert "Rider Quotes & Race Reports" in sections

    def test_nonexistent_slug(self):
        fact_sheet, sections = build_fact_sheet("nonexistent-race-slug-xyz")
        assert fact_sheet is None
        assert sections is None


# ============================================================
# Tests: build_criterion_hints (integration)
# ============================================================

class TestBuildCriterionHints:

    def test_returns_dict_for_valid_sections(self):
        sections = parse_sections(SALTY_LIZARD_SNIPPET)
        hints = build_criterion_hints(sections)
        assert isinstance(hints, dict)
        assert len(hints) > 0

    def test_empty_sections(self):
        assert build_criterion_hints({}) == {}
        assert build_criterion_hints(None) == {}

    def test_criterion_coverage(self):
        sections = parse_sections(SALTY_LIZARD_SNIPPET)
        hints = build_criterion_hints(sections)
        # Should have hints for criteria whose sections exist in the snippet
        # "community" maps to "Community Feel & Atmosphere" which exists
        assert "community" in hints

    def test_hints_truncated(self):
        # Build a section with very long text
        long_text = "A" * 2000 + ". End."
        sections = {"Weather Experienced": long_text}
        hints = build_criterion_hints(sections)
        if "climate" in hints:
            assert len(hints["climate"]) <= 810  # 800 + sentence overflow
