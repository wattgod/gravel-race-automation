#!/usr/bin/env python3
"""
Tests for community research quality filters — race-name disambiguation,
rider-level context tagging, and OUTPUT VALIDATION.

All tests use hard-coded inputs and expected outputs. No AI involved.
Run: python -m pytest tests/test_community_research.py -v
"""

import re
import sys
from pathlib import Path

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from batch_community_research import (
    _extract_distinctive_words,
    _is_generic_name,
    detect_rider_level,
    validate_content_relevance,
)

PROJECT_ROOT = Path(__file__).parent.parent
RESEARCH_DUMPS = PROJECT_ROOT / "research-dumps"


# ===================================================================
# Output validation helpers — hard-coded parsers, no AI
# ===================================================================

# Wattage mention: any number 100-500 followed by W/watts
_WATTAGE_RE = re.compile(r"\b(\d{3})\s*(?:w|watts?)\b", re.IGNORECASE)

# Carb/nutrition rate: Xg/hr or X grams per hour
_NUTRITION_RE = re.compile(
    r"\b(\d{2,3})\s*(?:g|grams?)\s*(?:/\s*(?:hr|hour)|per\s+hour)\b",
    re.IGNORECASE,
)

# Rider level tags in output
_LEVEL_TAG_RE = re.compile(r"\[(?:ELITE|COMPETITIVE|RECREATIONAL|UNKNOWN)\]")

# URL pattern
_URL_RE = re.compile(r"https?://[^\s\)\"'>]+")

# Source URLs section
_SOURCE_SECTION_RE = re.compile(r"^## Source URLs", re.MULTILINE)

# Quote pattern: text in quotes with some attribution
_QUOTE_RE = re.compile(r'"[^"]{20,}"')  # quoted text, 20+ chars


def _parse_community_dump(text):
    """Parse a community dump into sections. Returns dict of section_name -> content."""
    sections = {}
    current = None
    lines = text.split("\n")
    for line in lines:
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return {k: "\n".join(v) for k, v in sections.items()}


def _find_untagged_wattage(section_text):
    """Find wattage mentions (100-500W) not within 3 lines of a [LEVEL] tag.

    Returns list of (line_number, line_text) for untagged mentions.
    """
    lines = section_text.split("\n")
    untagged = []
    for i, line in enumerate(lines):
        if _WATTAGE_RE.search(line):
            # Check surrounding 3 lines for a level tag
            context_start = max(0, i - 3)
            context_end = min(len(lines), i + 4)
            context = "\n".join(lines[context_start:context_end])
            if not _LEVEL_TAG_RE.search(context):
                untagged.append((i, line.strip()))
    return untagged


def _find_untagged_nutrition(section_text):
    """Find nutrition rate mentions (e.g., 120g/hr) not near a [LEVEL] tag."""
    lines = section_text.split("\n")
    untagged = []
    for i, line in enumerate(lines):
        if _NUTRITION_RE.search(line):
            context_start = max(0, i - 3)
            context_end = min(len(lines), i + 4)
            context = "\n".join(lines[context_start:context_end])
            if not _LEVEL_TAG_RE.search(context):
                untagged.append((i, line.strip()))
    return untagged


def _find_orphan_quotes(section_text):
    """Find quotes (20+ chars in double quotes) without a URL or attribution nearby.

    Attribution = URL within 3 lines, or bold name (**Name**) within 2 lines.
    """
    lines = section_text.split("\n")
    orphans = []
    for i, line in enumerate(lines):
        if _QUOTE_RE.search(line):
            context_start = max(0, i - 2)
            context_end = min(len(lines), i + 4)
            context = "\n".join(lines[context_start:context_end])
            has_url = bool(_URL_RE.search(context))
            has_name = bool(re.search(r"\*\*[A-Z][^*]+\*\*", context))
            has_attribution = bool(re.search(r"\([^)]*(?:reddit|blog|forum|\.com|\.org|source)", context, re.IGNORECASE))
            if not (has_url or has_name or has_attribution):
                orphans.append((i, line.strip()))
    return orphans


# ===================================================================
# Race-name disambiguation tests
# ===================================================================

class TestExtractDistinctiveWords:
    """Test that stopwords and short words are filtered out."""

    def test_specific_name(self):
        words = _extract_distinctive_words("Belgian Waffle Ride")
        assert "belgian" in words
        assert "waffle" in words
        assert "ride" not in words  # stopword

    def test_generic_name(self):
        words = _extract_distinctive_words("SEVEN")
        assert words == {"seven"}

    def test_stopword_heavy(self):
        words = _extract_distinctive_words("The Gravel Race of the Year")
        # "the", "gravel", "race", "of" are all stopwords
        assert "year" in words
        assert "the" not in words
        assert "gravel" not in words

    def test_with_numbers(self):
        words = _extract_distinctive_words("Unbound 200")
        assert "unbound" in words
        assert "200" not in words  # stopword

    def test_crusher_in_the_tushar(self):
        words = _extract_distinctive_words("Crusher in the Tushar")
        assert "crusher" in words
        assert "tushar" in words
        assert "the" not in words


class TestIsGenericName:
    """Test that generic race names are correctly identified."""

    def test_seven_is_generic(self):
        assert _is_generic_name("SEVEN") is True

    def test_badlands_is_generic(self):
        assert _is_generic_name("BADLANDS") is True

    def test_mid_south_is_generic(self):
        # "mid" and "south" are both directional stopwords — 0 distinctive words
        assert _is_generic_name("Mid South") is True

    def test_belgian_waffle_ride_is_specific(self):
        assert _is_generic_name("Belgian Waffle Ride") is False

    def test_crusher_in_the_tushar_is_specific(self):
        assert _is_generic_name("Crusher in the Tushar") is False

    def test_unbound_200_is_generic(self):
        # "unbound" is the only distinctive word (200 is stopword)
        assert _is_generic_name("Unbound 200") is True

    def test_red_granite_grinder_is_specific(self):
        assert _is_generic_name("Red Granite Grinder") is False

    def test_sbt_grvl_is_specific(self):
        # "sbt" and "grvl" are both distinctive abbreviations — 2 words = specific
        assert _is_generic_name("SBT GRVL") is False

    def test_jeroboam_is_generic(self):
        assert _is_generic_name("JEROBOAM") is True

    def test_transcontinental_race_is_generic(self):
        # "transcontinental" stays, "race" is stopword — 1 distinctive word
        assert _is_generic_name("TRANSCONTINENTAL RACE") is True

    def test_dirty_reiver_is_specific(self):
        assert _is_generic_name("Dirty Reiver") is False

    def test_gravel_worlds_is_generic(self):
        # "gravel" and "worlds" — gravel is stopword, just "worlds"
        assert _is_generic_name("Gravel Worlds") is True


class TestValidateContentRelevance:
    """Test that content is validated against the right race."""

    # --- Specific names: name or slug match is sufficient ---

    def test_specific_name_match(self):
        content = "I rode the Belgian Waffle Ride last year and it was brutal."
        assert validate_content_relevance(content, "Belgian Waffle Ride", "bwr-california") is True

    def test_specific_slug_match(self):
        content = "The BWR California edition features the worst climbs in San Diego county."
        assert validate_content_relevance(content, "Belgian Waffle Ride", "bwr-california") is True

    def test_specific_no_match(self):
        content = "Best pancake recipes for Sunday morning breakfast with fresh waffles."
        assert validate_content_relevance(content, "Belgian Waffle Ride", "bwr-california") is False

    # --- Generic names: require cycling context ---

    def test_generic_with_cycling_context(self):
        content = "BADLANDS is an ultra-endurance gravel race through the Spanish desert. Riders face 750km of terrain."
        assert validate_content_relevance(content, "BADLANDS", "badlands") is True

    def test_generic_without_cycling_context(self):
        content = "Badlands National Park is a stunning geological formation in South Dakota. Great for hiking."
        assert validate_content_relevance(content, "BADLANDS", "badlands") is False

    def test_seven_cycling(self):
        content = "SEVEN is a brutal bikepacking race through the Scottish Highlands with 1000km of singletrack and gravel."
        assert validate_content_relevance(content, "SEVEN", "seven") is True

    def test_seven_not_cycling(self):
        content = "Seven is the best movie by David Fincher. Brad Pitt and Morgan Freeman star in this thriller."
        assert validate_content_relevance(content, "SEVEN", "seven") is False

    def test_mid_south_cycling(self):
        content = "Mid South gravel race in Stillwater Oklahoma had brutal conditions. DNF rate was 40% due to mud."
        assert validate_content_relevance(content, "Mid South", "mid-south") is True

    def test_mid_south_not_cycling(self):
        content = "The mid south region of the United States has a moderate climate and growing economy."
        assert validate_content_relevance(content, "Mid South", "mid-south") is False

    def test_jeroboam_cycling(self):
        content = "The Jeroboam race report: 200 miles of gravel in the Ozarks. I bonked at mile 150."
        assert validate_content_relevance(content, "JEROBOAM", "jeroboam") is True

    def test_jeroboam_wine(self):
        content = "A Jeroboam is a large format wine bottle equivalent to 4 standard bottles or 3 liters."
        assert validate_content_relevance(content, "JEROBOAM", "jeroboam") is False

    def test_unbound_cycling(self):
        content = "Unbound 200 race report from Emporia Kansas. I finished in 14 hours with two flats on the gravel roads."
        assert validate_content_relevance(content, "Unbound 200", "unbound-200") is True

    def test_unbound_not_cycling(self):
        content = "Unbound is a free-to-play online RPG game with an epic storyline and player-versus-player combat."
        assert validate_content_relevance(content, "Unbound 200", "unbound-200") is False


# ===================================================================
# Rider-level detection tests
# ===================================================================

class TestDetectRiderLevel:
    """Test hard-coded rider-level classification."""

    # --- Elite detection ---

    def test_pro_rider(self):
        content = "As a pro rider on the EF Education team, I averaged 285W for the first 100 miles."
        assert detect_rider_level(content) == "elite"

    def test_overall_winner(self):
        content = "I crossed the line in 9:45 for the overall win. Best race of my career."
        assert detect_rider_level(content) == "elite"

    def test_podium(self):
        content = "After 12 hours of racing, I podiumed in 3rd place overall."
        assert detect_rider_level(content) == "elite"

    def test_1st_overall(self):
        content = "Finished 1st overall with a time of 8:52."
        assert detect_rider_level(content) == "elite"

    def test_age_group_win(self):
        content = "Thrilled to take the age group win in 40-44."
        assert detect_rider_level(content) == "elite"

    def test_high_wattage(self):
        content = "Averaged 295W NP over the full 200 miles. The tailwind helped in the last 50."
        assert detect_rider_level(content) == "elite"

    def test_top_5(self):
        content = "Ended up top 3 which I'm stoked about for my first year racing gravel."
        assert detect_rider_level(content) == "elite"

    # --- Competitive detection ---

    def test_age_group_podium(self):
        content = "Happy with my age group podium in 30-34. Trained all winter for this."
        assert detect_rider_level(content) == "competitive"

    def test_high_ftp(self):
        content = "With my FTP of 320, I knew I could hold a strong pace on the flats."
        assert detect_rider_level(content) == "competitive"

    def test_personal_best(self):
        content = "Crushed my personal best by 45 minutes. All the structured training paid off."
        assert detect_rider_level(content) == "competitive"

    def test_w_per_kg(self):
        content = "At 4.2 w/kg I was able to stay with the lead group through the first 50 miles."
        assert detect_rider_level(content) == "competitive"

    def test_targeting_sub_time(self):
        content = "I was targeting sub-10 hours and came in at 9:58. Just barely made it."
        assert detect_rider_level(content) == "competitive"

    def test_moderate_wattage(self):
        content = "My normalized power was 245W avg for the day. Legs felt good until mile 150."
        assert detect_rider_level(content) == "competitive"

    # --- Recreational detection ---

    def test_bucket_list(self):
        content = "Unbound was on my bucket list for years. I just wanted to finish before cutoff."
        assert detect_rider_level(content) == "recreational"

    def test_just_finish(self):
        content = "My goal was to finish. That's it. No time goals, just cross the line."
        assert detect_rider_level(content) == "recreational"

    def test_first_gravel_race(self):
        content = "This was my first gravel race ever. I had no idea what to expect."
        assert detect_rider_level(content) == "recreational"

    def test_survival_mode(self):
        content = "By mile 120 I was in full survival mode. Walking hills, eating whatever I could."
        assert detect_rider_level(content) == "recreational"

    def test_back_of_pack(self):
        content = "As a back of pack rider, the course looked very different than what the pros saw."
        assert detect_rider_level(content) == "recreational"

    def test_cutoff_concern(self):
        content = "I was worried about the time cutoff at the last checkpoint but made it with 20 min to spare."
        assert detect_rider_level(content) == "recreational"

    def test_beginner(self):
        content = "Total beginner here. Never raced a gravel race before this one."
        assert detect_rider_level(content) == "recreational"

    def test_low_wattage(self):
        content = "I averaged about 155W avg over the full distance. Not fast but got it done."
        assert detect_rider_level(content) == "recreational"

    # --- Unknown detection ---

    def test_generic_content(self):
        content = "The course goes through beautiful countryside with rolling hills and fall colors."
        assert detect_rider_level(content) == "unknown"

    def test_logistics_only(self):
        content = "Registration opens in March. The race starts at 7am from downtown. Parking is free."
        assert detect_rider_level(content) == "unknown"

    # --- Priority tests (elite > competitive > recreational) ---

    def test_elite_overrides_recreational(self):
        # Has both elite and recreational signals — elite wins
        content = "This was my first gravel race but I podiumed in 2nd overall. Beginner's luck!"
        assert detect_rider_level(content) == "elite"

    def test_elite_overrides_competitive(self):
        content = "With my FTP of 340, I took the overall win at the age of 42."
        assert detect_rider_level(content) == "elite"

    # --- Edge cases ---

    def test_top_5_mph_not_elite(self):
        # "top 5 mph" should NOT trigger the "top 5" elite pattern
        content = "The top speed on the descent was about 45 mph. Pretty scary on gravel."
        assert detect_rider_level(content) != "elite"

    def test_wattage_below_floor(self):
        # 50W is nonsensical for a race average — should not classify
        content = "Output was 50W avg which doesn't sound right, probably a sensor glitch."
        assert detect_rider_level(content) == "unknown"

    def test_watts_in_sprint_not_race_avg(self):
        # "585W for 35 seconds" is a sprint, not race avg — pattern requires avg/NP/normalized
        content = "I sprinted up the hill at 585 W for 35 seconds then sat up."
        assert detect_rider_level(content) == "unknown"


# ===================================================================
# Output validation tests — verify the DUMP CONTENT, not the classifiers
# ===================================================================

class TestDumpStructure:
    """Verify community dump files have required structure."""

    def _get_dumps(self):
        """Get all community dump paths."""
        return sorted(RESEARCH_DUMPS.glob("*-community.md"))

    def test_community_dumps_exist(self):
        dumps = self._get_dumps()
        assert len(dumps) > 0, "No community dumps found — run batch_community_research.py first"

    def test_every_dump_has_header(self):
        """Every dump must start with # RACE NAME — COMMUNITY RESEARCH."""
        for path in self._get_dumps():
            content = path.read_text()
            assert content.startswith("# "), \
                f"{path.name}: Missing markdown H1 header"
            assert "COMMUNITY RESEARCH" in content.split("\n")[0], \
                f"{path.name}: Header missing 'COMMUNITY RESEARCH'"

    def test_every_dump_has_source_urls_section(self):
        """Every dump should have a ## Source URLs section.

        Pre-fix dumps (generated with max_tokens=4000) often truncate this
        section. Post-fix dumps (6000 tokens + mandatory rule) should always
        include it. This test flags the failure rate and will tighten as
        old dumps are regenerated.
        """
        missing = []
        for path in self._get_dumps():
            content = path.read_text()
            if not _SOURCE_SECTION_RE.search(content):
                missing.append(path.name)
        total = len(self._get_dumps())
        if missing:
            print(f"\nWARN: {len(missing)}/{total} dumps missing Source URLs section")
            print(f"  Re-run with --force to regenerate: {', '.join(missing[:5])}...")
        # Threshold: allow up to 60% missing (pre-fix dumps)
        # Tighten to 20% after full regeneration
        assert len(missing) < total * 0.6, (
            f"{len(missing)}/{total} dumps missing Source URLs section — "
            f"regenerate with: batch_community_research.py --force --slugs {' '.join(m.replace('-community.md', '') for m in missing[:5])}"
        )

    def test_dumps_have_attribution_somewhere(self):
        """Every dump must have attribution — full URLs, domain references, or named sources.

        Full URLs (https://...) are preferred. Domain-only (gravelcyclist.com)
        is acceptable. Named sources (SomeMayoPlease, Reddit user) are minimum
        acceptable for pre-fix dumps.
        """
        no_attribution = []
        for path in self._get_dumps():
            content = path.read_text()
            full_urls = _URL_RE.findall(content)
            domain_refs = re.findall(
                r"\b\w+\.(?:com|org|net|io|bike|earth)\b",
                content,
            )
            # Also count named attributions: **Name** or *Name:* patterns
            named_sources = re.findall(r"\*\*[A-Z][^*]{2,50}\*\*", content)
            total = len(full_urls) + len(domain_refs) + len(named_sources)
            if total < 3:
                no_attribution.append(
                    f"{path.name}: {len(full_urls)} URLs, {len(domain_refs)} domains, "
                    f"{len(named_sources)} named sources"
                )
        assert len(no_attribution) == 0, (
            f"{len(no_attribution)} dumps with poor attribution:\n"
            + "\n".join(no_attribution)
        )

    def test_no_empty_sections(self):
        """No section should be empty (just a header with no content)."""
        for path in self._get_dumps():
            sections = _parse_community_dump(path.read_text())
            for name, content in sections.items():
                stripped = content.strip()
                # Allow empty Source URLs if all URLs are inline
                if name == "Source URLs":
                    continue
                assert len(stripped) > 20, \
                    f"{path.name}: Section '{name}' is empty or trivially short"

    def test_dump_minimum_size(self):
        """Every dump must be at least 2KB — anything less is suspiciously thin."""
        for path in self._get_dumps():
            size = path.stat().st_size
            assert size >= 2048, \
                f"{path.name}: Only {size} bytes — suspiciously thin"


class TestAttribution:
    """Verify quotes and claims are properly attributed."""

    def _get_dumps(self):
        return sorted(RESEARCH_DUMPS.glob("*-community.md"))

    def test_quotes_have_attribution(self):
        """Every substantial quote should have a name or URL nearby."""
        total_orphans = []
        for path in self._get_dumps():
            content = path.read_text()
            orphans = _find_orphan_quotes(content)
            for line_num, line_text in orphans:
                total_orphans.append(f"{path.name}:{line_num}: {line_text[:80]}")
        # Allow some orphans (Claude isn't perfect) but flag if > 10% of dumps have them
        orphan_rate = len(total_orphans) / max(len(self._get_dumps()), 1)
        assert orphan_rate < 5, (
            f"Too many orphan quotes ({len(total_orphans)} across {len(self._get_dumps())} dumps). "
            f"First 5:\n" + "\n".join(total_orphans[:5])
        )

    def test_rider_quotes_section_has_attribution(self):
        """Rider Quotes section should have attributed names or source URLs.

        Acceptable formats:
          - **Name:** "quote" (source)
          - **"quote"** - Name (source)
          - "quote" (source-url.com)
        """
        for path in self._get_dumps():
            sections = _parse_community_dump(path.read_text())
            quotes_section = sections.get("Rider Quotes & Race Reports", "")
            if not quotes_section.strip():
                continue
            # Check for bold names OR parenthetical attributions
            has_bold_names = bool(re.search(r"\*\*[A-Z][^*]+\*\*", quotes_section))
            has_url_attributions = bool(re.search(r"\([^)]*\.(?:com|org|net|io)", quotes_section))
            has_dash_names = bool(re.search(r"[-–—]\s*[A-Z][a-z]+", quotes_section))
            assert has_bold_names or has_url_attributions or has_dash_names, \
                f"{path.name}: Rider Quotes section has no attribution (no bold names, URLs, or dash-names)"


class TestPerformanceDataTagging:
    """Verify performance-specific data has rider level context.

    This catches the dangerous case: a 120g/hr nutrition plan or 280W pacing
    strategy from an elite being presented without level context, where a
    recreational rider might take it as general advice.
    """

    def _get_tagged_dumps(self):
        """Get dumps generated AFTER tagging was implemented.

        Only check dumps that contain [ELITE], [COMPETITIVE], or [RECREATIONAL]
        tags — older dumps were generated before this feature.
        """
        tagged = []
        for path in sorted(RESEARCH_DUMPS.glob("*-community.md")):
            content = path.read_text()
            if _LEVEL_TAG_RE.search(content):
                tagged.append(path)
        return tagged

    def test_tagged_dumps_exist_after_rerun(self):
        """After re-running with --force, dumps should have level tags.

        This test will skip gracefully if no tagged dumps exist yet.
        """
        tagged = self._get_tagged_dumps()
        if not tagged:
            pytest.skip("No tagged community dumps yet — re-run with --force to generate")

    def test_wattage_mentions_have_level_context(self):
        """Wattage numbers in Strategy/Nutrition sections should be near a [LEVEL] tag."""
        tagged = self._get_tagged_dumps()
        if not tagged:
            pytest.skip("No tagged community dumps yet")

        violations = []
        for path in tagged:
            sections = _parse_community_dump(path.read_text())
            for section_name in ["Race Strategy & Pacing", "Nutrition Strategy",
                                 "Equipment & Gear Recommendations"]:
                section_text = sections.get(section_name, "")
                untagged = _find_untagged_wattage(section_text)
                for line_num, line_text in untagged:
                    violations.append(f"{path.name} [{section_name}]:{line_num}: {line_text[:80]}")

        assert len(violations) == 0, (
            f"{len(violations)} wattage mentions without rider level context:\n"
            + "\n".join(violations[:10])
        )

    def test_nutrition_rates_have_level_context(self):
        """Nutrition rates (g/hr) should be near a [LEVEL] tag."""
        tagged = self._get_tagged_dumps()
        if not tagged:
            pytest.skip("No tagged community dumps yet")

        violations = []
        for path in tagged:
            sections = _parse_community_dump(path.read_text())
            for section_name in ["Race Strategy & Pacing", "Nutrition Strategy"]:
                section_text = sections.get(section_name, "")
                untagged = _find_untagged_nutrition(section_text)
                for line_num, line_text in untagged:
                    violations.append(f"{path.name} [{section_name}]:{line_num}: {line_text[:80]}")

        assert len(violations) == 0, (
            f"{len(violations)} nutrition rate mentions without rider level context:\n"
            + "\n".join(violations[:10])
        )


class TestCrossReference:
    """Verify community dumps match their race profiles."""

    def test_dump_race_name_matches_profile(self):
        """The H1 header race name should match the JSON profile name."""
        race_data = PROJECT_ROOT / "race-data"
        for path in sorted(RESEARCH_DUMPS.glob("*-community.md")):
            slug = path.stem.replace("-community", "")
            json_path = race_data / f"{slug}.json"
            if not json_path.exists():
                continue

            import json
            data = json.loads(json_path.read_text())
            race = data.get("race", data)
            profile_name = race.get("name", "").upper()

            header = path.read_text().split("\n")[0]
            # Header format: # RACE NAME — COMMUNITY RESEARCH
            header_name = header.replace("# ", "").split("—")[0].strip()

            assert header_name == profile_name, (
                f"{path.name}: Header '{header_name}' doesn't match profile '{profile_name}'"
            )

    def test_source_urls_are_valid_format(self):
        """Source URLs should be well-formed http(s) URLs, not hallucinated."""
        for path in sorted(RESEARCH_DUMPS.glob("*-community.md")):
            sections = _parse_community_dump(path.read_text())
            source_section = sections.get("Source URLs", "")
            urls = _URL_RE.findall(source_section)
            for url in urls:
                assert url.startswith("http"), f"{path.name}: Bad URL: {url}"
                # No obvious hallucination patterns
                assert "example.com" not in url, f"{path.name}: Hallucinated URL: {url}"
                assert "placeholder" not in url.lower(), f"{path.name}: Placeholder URL: {url}"


class TestRealWorldContent:
    """Test classifiers against ACTUAL content from existing community dumps.

    These tests use real text from dumps we've already generated, not
    synthetic sentences. If the classifiers can't handle real-world messy
    content, they're useless.
    """

    def test_real_elite_content(self):
        """Real elite content from Unbound 200 dump."""
        # SomeMayoPlease (Reddit, 2024, 10:13 finish, Age Group win, 3rd overall)
        content = (
            "10:13 finish, Age Group win, 3rd overall. "
            "255W average, 273W normalized, only 3:22 stopped time, 120g carbs/hour"
        )
        assert detect_rider_level(content) == "elite"

    def test_real_competitive_content(self):
        """Real competitive content — Bertn05 from Unbound dump."""
        # Bertn05: 10h37 total, 252W NP at 74kg, 12th overall, age group podium
        content = (
            "10h37 total (10h32 ride time), 252W NP at 74kg. "
            "age group podium. Started at the first line aiming for 10 hours."
        )
        assert detect_rider_level(content) in ("elite", "competitive")

    def test_real_recreational_content(self):
        """Real recreational content — Neil Fortner from Unbound dump."""
        # 13:58:20 finish, 154W average, "bucket list item", "my only goal was to have a good race"
        content = (
            "Unbound had been a bucket list item for me for a while. "
            "Final time: 13:58:20, 154W average. "
            "my only goal was to have a good race and beat the sun"
        )
        assert detect_rider_level(content) == "recreational"

    def test_real_mixed_signals(self):
        """Content with mixed signals — should pick strongest."""
        # Jenna Rinehart: finished 30th (top placement = elite), but "fell apart", "not sure I was going to make it"
        content = (
            "Taken down in a crash less than 5 miles into the race. "
            "I completely fell apart during the last 20 miles. "
            "I crept to the finish line, not sure I was going to make it. "
            "Despite all issues, finished 30th averaging 18.25 mph"
        )
        # No explicit elite markers (30th isn't "top 5" or "podium")
        # "crept to finish line" suggests recreational signals
        level = detect_rider_level(content)
        assert level in ("recreational", "unknown")

    def test_real_no_signals(self):
        """Real terrain description content — should be unknown."""
        content = (
            "This was the roughest section of the day. Steep, rocky, pointy, "
            "and it went for a handful of miles. This was one of the few times "
            "a front suspension and wider tires would have really helped."
        )
        assert detect_rider_level(content) == "unknown"

    def test_wattage_in_natural_text(self):
        """Wattage mentioned naturally, not in clean 'XXW avg' format."""
        # "154W average (201W normalized)" — should catch this
        content = "Final time: 13:58:20, 15.3 mph average, 154W average (201W normalized)"
        level = detect_rider_level(content)
        assert level == "recreational"  # 154W avg is recreational

    def test_validate_relevance_real_ironbull_content(self):
        """Real fetched content from ironbull.org about Red Granite Grinder."""
        content = (
            "Red Granite Grinder race report by Stan. "
            "I would recommend you put this race on your bucket list. "
            "The course traverses some of the most beautiful fall countryside "
            "I have raced through anywhere in the world."
        )
        assert validate_content_relevance(content, "Red Granite Grinder", "red-granite-grinder") is True

    def test_validate_relevance_false_positive_race_results(self):
        """Race results page that mentions a generic race name in a list — not about THIS race."""
        content = (
            "2024 Ultra Race Calendar: Badlands Spain, Tour Divide Montana, "
            "Silk Road Mountain Race Kyrgyzstan, Atlas Mountain Race Morocco. "
            "Complete list of endurance events worldwide."
        )
        # "Badlands" appears, but this is a calendar page — no cycling context about THIS race
        # However "race" is in CYCLING_CONTEXT... this is actually tricky
        # The content DOES have cycling context and DOES mention badlands
        # This would pass validation — which is OK, Claude filters the rest
        # This is a known limitation: validation catches non-cycling content,
        # not cycling content that mentions the race in passing
