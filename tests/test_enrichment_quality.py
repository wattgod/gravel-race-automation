"""
Re-enrichment validation suite.

Catches slop, regressions, and quality issues in biased_opinion_ratings
explanations. All checks are hard-coded regex — no AI.

Run: pytest tests/test_enrichment_quality.py -v
"""

import json
import re
import sys
from pathlib import Path

import pytest

# Import shared utilities from scripts/
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from quality_gates import check_slop_phrases
from community_parser import extract_proper_nouns, RE_NO_EVIDENCE

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"

SCORE_COMPONENTS = [
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses'
]


def get_enriched_profiles():
    """Load profiles that have biased_opinion_ratings with explanations."""
    profiles = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        race = data.get("race", data)
        bor = race.get("biased_opinion_ratings", {})
        if isinstance(bor, dict) and any(
            isinstance(v, dict) and v.get("explanation", "").strip()
            for v in bor.values()
        ):
            profiles.append((f.stem, race))
    return profiles


# ============================================================
# Test Classes
# ============================================================


class TestSlopPerExplanation:
    """Every individual explanation must be slop-free."""

    # Legitimate uses that are not slop in context
    KNOWN_EXCEPTIONS = {
        ("reliance-deep-woods", "race_quality", "legitimate"),  # "keep it legitimate"
        ("spotted-horse-ultra", "experience", "essential"),  # "the essential hurt" (poetic)
        ("trans-am-bike-race", "field_depth", "world-class"),  # with specific stat (14 days)
        ("uci-gravel-worlds", "logistics", "essential"),  # "Early booking essential" (practical)
    }

    def test_no_slop_in_explanations(self):
        violations = []
        for slug, race in get_enriched_profiles():
            bor = race.get("biased_opinion_ratings", {})
            for key in SCORE_COMPONENTS:
                entry = bor.get(key)
                if not isinstance(entry, dict):
                    continue
                explanation = entry.get("explanation", "")
                if not explanation.strip():
                    continue

                result = check_slop_phrases(explanation)
                if not result["passed"]:
                    for slop in result["slop_found"]:
                        phrase = slop["phrase"]
                        if (slug, key, phrase) in self.KNOWN_EXCEPTIONS:
                            continue
                        violations.append(
                            f"  {slug}.{key}: \"{phrase}\" in \"{slop['context']}\""
                        )

        if violations:
            pytest.fail(
                f"{len(violations)} slop phrases found in explanations:\n" +
                "\n".join(violations[:30])
            )


class TestExplanationSpecificity:
    """Each explanation should contain specific details, not vague filler."""

    # Regex for specificity markers
    RE_NUMBER = re.compile(r'\d+')
    # Multi-word proper nouns (e.g. "Flint Hills", "Bobby Kennedy")
    RE_PROPER_NOUN = re.compile(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+')
    # Single-word proper noun mid-sentence (e.g. "in Belgium", "near Flanders")
    RE_SINGLE_PROPER = re.compile(r'(?<=[a-z.,;:]\s)[A-Z][a-z]{2,}')
    RE_QUOTED = re.compile(r'["\u201c\u201d\'].*?["\u201c\u201d\']')

    KNOWN_EXCEPTIONS = {
        "dirty-french",  # NYC restaurant, not a race
    }

    def test_explanations_have_specifics(self):
        """At least 10/14 explanations per profile must contain a number,
        proper noun, or quoted phrase."""
        weak_profiles = []
        for slug, race in get_enriched_profiles():
            if slug in self.KNOWN_EXCEPTIONS:
                continue
            bor = race.get("biased_opinion_ratings", {})
            specific_count = 0
            total = 0

            for key in SCORE_COMPONENTS:
                entry = bor.get(key)
                if not isinstance(entry, dict):
                    continue
                explanation = entry.get("explanation", "")
                if not explanation.strip():
                    continue
                total += 1

                has_number = bool(self.RE_NUMBER.search(explanation))
                has_proper = bool(self.RE_PROPER_NOUN.search(explanation))
                has_single_proper = bool(self.RE_SINGLE_PROPER.search(explanation))
                has_quote = bool(self.RE_QUOTED.search(explanation))

                if has_number or has_proper or has_single_proper or has_quote:
                    specific_count += 1

            if total >= 14 and specific_count < 10:
                weak_profiles.append(
                    f"  {slug}: {specific_count}/{total} specific"
                )

        if weak_profiles:
            pytest.fail(
                f"{len(weak_profiles)} profiles with <10/14 specific explanations:\n" +
                "\n".join(weak_profiles[:20])
            )


class TestScorePreservation:
    """biased_opinion_ratings scores must exactly match gravel_god_rating."""

    def test_scores_match(self):
        violations = []
        for slug, race in get_enriched_profiles():
            rating = race.get("gravel_god_rating", {})
            bor = race.get("biased_opinion_ratings", {})

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
                f"{len(violations)} score mismatches:\n" +
                "\n".join(violations[:20])
            )


class TestCommunityPenetration:
    """Profiles with community dumps should reference community-sourced proper nouns."""

    MIN_COMMUNITY_NOUNS = 2

    # Races where community penetration is inherently limited
    KNOWN_EXCEPTIONS = {
        "dirty-french",  # NYC restaurant, not a race — data is bogus
        "la-dromoise-gravel",  # Small French race, minimal English community content
        "6-hours-of-syllamo",  # Community dump has no relevant content (0.8KB)
        "lake-country-gravel",  # One vague mention, no proper nouns (1.3KB)
        "scratch-ankle-gravel",  # All search results were MIT Scratch, not the race (1.9KB)
        "wild-gravel",  # No sources about the race found (0.9KB)
        "rose-city-rampage",  # Cancelled race, only promoter quotes (1.8KB)
        "salida-76",  # Limited dump, 1 proper noun found but threshold is 2
    }

    def test_community_nouns_in_explanations(self):
        """At least 2 unique proper nouns from community dump should appear
        in the combined explanations."""
        weak = []
        for slug, race in get_enriched_profiles():
            if slug in self.KNOWN_EXCEPTIONS:
                continue
            community_path = RESEARCH_DUMPS / f"{slug}-community.md"
            if not community_path.exists():
                continue

            community_text = community_path.read_text()
            community_nouns = extract_proper_nouns(community_text)
            if len(community_nouns) < self.MIN_COMMUNITY_NOUNS:
                continue  # Not enough nouns to test against

            # Combine all explanations
            bor = race.get("biased_opinion_ratings", {})
            all_explanations = " ".join(
                entry.get("explanation", "")
                for entry in bor.values()
                if isinstance(entry, dict)
            )

            # Check how many community nouns appear
            found = {noun for noun in community_nouns if noun in all_explanations}

            if len(found) < self.MIN_COMMUNITY_NOUNS:
                weak.append(
                    f"  {slug}: {len(found)}/{len(community_nouns)} community nouns "
                    f"(found: {sorted(found)[:5]})"
                )

        if weak:
            pytest.fail(
                f"{len(weak)} profiles with poor community penetration (<{self.MIN_COMMUNITY_NOUNS} nouns):\n" +
                "\n".join(weak[:30])
            )


class TestCrossRaceDuplication:
    """No two different profiles should share identical explanation text."""

    MIN_LENGTH = 50  # Only flag dupes longer than 50 chars

    def test_no_duplicate_explanations(self):
        seen = {}  # explanation text → (slug, key)
        dupes = []

        for slug, race in get_enriched_profiles():
            bor = race.get("biased_opinion_ratings", {})
            for key in SCORE_COMPONENTS:
                entry = bor.get(key)
                if not isinstance(entry, dict):
                    continue
                explanation = entry.get("explanation", "").strip()
                if len(explanation) < self.MIN_LENGTH:
                    continue

                if explanation in seen:
                    other_slug, other_key = seen[explanation]
                    if other_slug != slug:
                        dupes.append(
                            f"  {slug}.{key} == {other_slug}.{other_key}: "
                            f"\"{explanation[:80]}...\""
                        )
                else:
                    seen[explanation] = (slug, key)

        if dupes:
            pytest.fail(
                f"{len(dupes)} cross-race duplicate explanations:\n" +
                "\n".join(dupes[:20])
            )


class TestHonestUncertainty:
    """Explanations shouldn't claim "no evidence" when community data exists."""

    def test_no_false_uncertainty(self):
        """Races WITH community dumps shouldn't use "no evidence" phrases."""
        violations = []
        for slug, race in get_enriched_profiles():
            community_path = RESEARCH_DUMPS / f"{slug}-community.md"
            if not community_path.exists():
                continue  # No community dump — uncertainty phrases are OK

            bor = race.get("biased_opinion_ratings", {})
            for key in SCORE_COMPONENTS:
                entry = bor.get(key)
                if not isinstance(entry, dict):
                    continue
                explanation = entry.get("explanation", "")
                matches = RE_NO_EVIDENCE.findall(explanation)
                if matches:
                    violations.append(
                        f"  {slug}.{key}: \"{matches[0]}\" — but community dump exists "
                        f"({community_path.stat().st_size / 1024:.1f}KB)"
                    )

        if violations:
            pytest.fail(
                f"{len(violations)} false uncertainty claims (community data exists):\n" +
                "\n".join(violations[:30])
            )


class TestExplanationLength:
    """Each explanation should be 50-800 characters."""

    MIN_LENGTH = 50
    MAX_LENGTH = 800

    def test_explanation_length_bounds(self):
        violations = []
        for slug, race in get_enriched_profiles():
            bor = race.get("biased_opinion_ratings", {})
            for key in SCORE_COMPONENTS:
                entry = bor.get(key)
                if not isinstance(entry, dict):
                    continue
                explanation = entry.get("explanation", "")
                length = len(explanation)

                if length < self.MIN_LENGTH:
                    violations.append(
                        f"  {slug}.{key}: too short ({length} chars)"
                    )
                elif length > self.MAX_LENGTH:
                    violations.append(
                        f"  {slug}.{key}: too long ({length} chars)"
                    )

        if violations:
            pytest.fail(
                f"{len(violations)} explanations outside 50-600 char bounds:\n" +
                "\n".join(violations[:30])
            )


class TestGenericTerrainNames:
    """Flag explanations that use fabricated section names instead of real terrain."""

    FAKE_TERRAIN_NAMES = [
        "The First Push",
        "The Final Challenge",
        "Early Desert",
        "Late Desert",
        "Midpoint",
        "The Grind",
        "The Final Push",
        "The Opening Miles",
        "The Closing Miles",
        "The Middle Section",
        "The Back Half",
        "The Front Half",
    ]

    def _build_pattern(self):
        escaped = [re.escape(name) for name in self.FAKE_TERRAIN_NAMES]
        return re.compile(r'\b(?:' + '|'.join(escaped) + r')\b', re.IGNORECASE)

    def test_no_fake_terrain_names(self):
        pattern = self._build_pattern()
        violations = []
        for slug, race in get_enriched_profiles():
            bor = race.get("biased_opinion_ratings", {})
            for key in SCORE_COMPONENTS:
                entry = bor.get(key)
                if not isinstance(entry, dict):
                    continue
                explanation = entry.get("explanation", "")
                matches = pattern.findall(explanation)
                if matches:
                    violations.append(
                        f"  {slug}.{key}: fake terrain \"{matches[0]}\""
                    )

        if violations:
            pytest.fail(
                f"{len(violations)} fabricated terrain names found:\n" +
                "\n".join(violations[:30])
            )
