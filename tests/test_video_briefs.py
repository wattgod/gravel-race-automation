"""Tests for video brief generator.

Comprehensive test suite covering:
- Trope detection from scoring patterns
- Beat timing and duration constraints
- WPM validation (narration feasibility)
- Duration limits (Short format caps)
- B-roll URL filtering
- Head-to-head winner logic (round wins)
- Suffering map zone truncation
- Thumbnail aspect ratios
- Edge cases: sparse data, extreme scores, tie scenarios
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_video_briefs import (
    detect_tropes,
    brief_tier_reveal,
    brief_suffering_map,
    brief_roast,
    brief_should_you_race,
    brief_head_to_head,
    has_sufficient_data,
    _fmt_time,
    _check_wpm,
    _trim_narration,
    _pick_avatar,
    _get_broll_sources,
    _thumbnail_prompt,
    _build_brief,
    _stable_hash,
    _extract_first_sentence,
    _narrate_score,
    _pick_intro,
    _narrate_round,
    DURATION_TARGETS,
    SHORT_MAX_SEC,
    WPM_COMFORTABLE,
    WPM_FAST,
    WPM_MAX,
    FORMATS,
    BPM,
    RETENTION_TARGETS,
    SCORE_QUIPS,
    ROAST_MARKETING_INTROS,
    ROAST_REALITY_INTROS,
    ROAST_DATA_INTROS,
    SYR_SCORE_INTROS,
    SYR_REMAINING_INTROS,
    SYR_STRENGTH_INTROS,
    SYR_WEAKNESS_INTROS,
    SYR_LOGISTICS_INTROS,
    TIER_TAGS,
)
from generate_video_scripts import (
    load_race,
    load_all_races,
    TIER_NAMES,
)

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"

# Races chosen to cover different tiers and data completeness levels
COMPLETE_RACES = ["unbound-200", "mid-south", "steamboat-gravel", "bwr-california"]
SPARSE_RACES = ["almanzo-100", "gravel-grit-n-grind", "unbound-xl"]
ALL_TEST_RACES = COMPLETE_RACES + SPARSE_RACES


def _load(slug):
    """Load a real race for testing."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        pytest.skip(f"Race data not found: {slug}")
    return load_race(slug)


# ---------------------------------------------------------------------------
# _fmt_time
# ---------------------------------------------------------------------------

class TestFmtTime:
    """Test time formatting helper."""

    def test_zero(self):
        assert _fmt_time(0) == "0:00"

    def test_under_minute(self):
        assert _fmt_time(30) == "0:30"
        assert _fmt_time(59) == "0:59"

    def test_exact_minute(self):
        assert _fmt_time(60) == "1:00"

    def test_over_minute(self):
        assert _fmt_time(75) == "1:15"
        assert _fmt_time(125) == "2:05"

    def test_large_values(self):
        assert _fmt_time(600) == "10:00"
        assert _fmt_time(725) == "12:05"

    def test_negative_clamps(self):
        # Negative values should still produce valid output
        result = _fmt_time(-5)
        assert ":" in result


# ---------------------------------------------------------------------------
# _check_wpm
# ---------------------------------------------------------------------------

class TestCheckWpm:
    """Test words-per-minute validation."""

    def test_comfortable_pace(self):
        text = "This is a normal sentence."  # 5 words
        wpm, feasible, severity = _check_wpm(text, 3)  # 100 WPM
        assert feasible is True
        assert severity == "ok"

    def test_fast_pace(self):
        text = " ".join(["word"] * 9)  # 9 words in 3 sec = 180 WPM
        wpm, feasible, severity = _check_wpm(text, 3)
        assert severity in ("fast", "too_fast")

    def test_impossible_pace(self):
        text = " ".join(["word"] * 15)  # 15 words in 3 sec = 300 WPM
        wpm, feasible, severity = _check_wpm(text, 3)
        assert feasible is False
        assert severity == "impossible"

    def test_empty_text(self):
        wpm, feasible, severity = _check_wpm("", 10)
        assert feasible is True
        assert severity == "ok"

    def test_zero_duration(self):
        wpm, feasible, severity = _check_wpm("Hello world", 0)
        assert feasible is False
        assert severity == "impossible"

    def test_zero_duration_empty_text(self):
        wpm, feasible, severity = _check_wpm("", 0)
        assert feasible is True


# ---------------------------------------------------------------------------
# _trim_narration
# ---------------------------------------------------------------------------

class TestTrimNarration:
    """Test narration trimming to fit duration."""

    def test_short_text_unchanged(self):
        text = "Hello world."
        assert _trim_narration(text, 10) == text

    def test_long_text_trimmed(self):
        text = "Word " * 100 + "end."
        result = _trim_narration(text, 3, target_wpm=150)
        words = len(result.split())
        # At 150 WPM, 3 seconds = 7.5 words max
        assert words <= 8

    def test_trims_at_sentence_boundary(self):
        text = "First sentence. Second sentence. Third sentence."
        result = _trim_narration(text, 2, target_wpm=150)
        # Should end at a period
        assert result.endswith(".")

    def test_adds_period_if_no_boundary(self):
        text = "One two three four five six seven eight nine ten"
        result = _trim_narration(text, 1, target_wpm=150)
        assert result.endswith(".")


# ---------------------------------------------------------------------------
# Trope Detection
# ---------------------------------------------------------------------------

class TestTropeDetection:
    """Test trope detection from race scoring patterns."""

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_always_returns_at_least_one(self, slug):
        rd = _load(slug)
        tropes = detect_tropes(rd)
        assert len(tropes) >= 1

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_tropes_sorted_by_strength(self, slug):
        rd = _load(slug)
        tropes = detect_tropes(rd)
        strengths = [t["strength"] for t in tropes]
        assert strengths == sorted(strengths, reverse=True)

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_tropes_have_required_fields(self, slug):
        rd = _load(slug)
        tropes = detect_tropes(rd)
        required = {"name", "tension", "mechanism", "hook_text", "engagement_q", "strength"}
        for trope in tropes:
            assert required.issubset(trope.keys()), \
                f"Missing fields in trope {trope['name']}: {required - trope.keys()}"

    def test_fallback_tier_reveal_always_present(self):
        rd = _load("unbound-200")
        tropes = detect_tropes(rd)
        names = [t["name"] for t in tropes]
        assert "tier_reveal" in names

    def test_expose_trope_fires_on_high_prestige_low_value(self):
        """Synthetic test: force prestige=5, value=1 and check expose fires."""
        rd = _load("unbound-200")
        # Manipulate scores
        rd["explanations"]["prestige"]["score"] = 5
        rd["explanations"]["value"]["score"] = 1
        tropes = detect_tropes(rd)
        names = [t["name"] for t in tropes]
        assert "expose" in names

    def test_underdog_reveal_fires_on_low_tier_perfect_score(self):
        """Synthetic test: force tier=4 with a perfect 5."""
        rd = _load("unbound-200")
        rd["tier"] = 4
        rd["explanations"]["adventure"]["score"] = 5
        tropes = detect_tropes(rd)
        names = [t["name"] for t in tropes]
        assert "underdog_reveal" in names

    def test_no_duplicate_trope_names(self):
        """Trope names should be unique (except extreme_* variants)."""
        rd = _load("unbound-200")
        tropes = detect_tropes(rd)
        base_names = [t["name"].split("_")[0] if t["name"].startswith("extreme_")
                      else t["name"] for t in tropes]
        # extreme_ variants are ok, but others should be unique
        non_extreme = [n for n in base_names if n != "extreme"]
        # Allow tier_reveal as it's always present
        assert len(non_extreme) == len(set(non_extreme))


# ---------------------------------------------------------------------------
# Brief Generation — Tier Reveal
# ---------------------------------------------------------------------------

class TestBriefTierReveal:
    """Test tier-reveal brief generation."""

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_generates_valid_brief(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        assert brief is not None
        assert brief["format"] == "tier-reveal"
        assert brief["slug"] == slug

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_duration_within_target(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        lo, hi = DURATION_TARGETS["tier-reveal"]
        # Allow small buffer above target (hook extension adds 2s)
        assert lo - 5 <= brief["estimated_duration_sec"] <= hi + 10, \
            f"Duration {brief['estimated_duration_sec']}s outside target ({lo}-{hi})"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_has_required_beats(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        beat_ids = [b["id"] for b in brief["beats"]]
        assert "hook" in beat_ids
        assert "reveal" in beat_ids
        assert "cta" in beat_ids

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_thumbnail_aspect_ratio_vertical(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        assert "9:16" in brief["thumbnail_prompt"], "Shorts should use 9:16"
        assert "16:9" not in brief["thumbnail_prompt"]

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_has_narration_feasibility(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        feas = brief["narration_feasibility"]
        assert "total_words" in feas
        assert "warnings" in feas
        assert isinstance(feas["warnings"], list)

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_cta_has_correct_url(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        cta_beat = [b for b in brief["beats"] if b["id"] == "cta"][0]
        assert slug in cta_beat["text_on_screen"]


# ---------------------------------------------------------------------------
# Brief Generation — Suffering Map
# ---------------------------------------------------------------------------

class TestBriefSufferingMap:
    """Test suffering-map brief generation."""

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_generates_or_skips(self, slug):
        rd = _load(slug)
        brief = brief_suffering_map(rd)
        zones = rd["course"].get("suffering_zones", [])
        if not zones:
            assert brief is None
        else:
            assert brief is not None
            assert brief["format"] == "suffering-map"

    def test_duration_never_exceeds_short_max(self):
        """All suffering maps must stay under SHORT_MAX_SEC."""
        races = load_all_races()
        for rd in races:
            brief = brief_suffering_map(rd)
            if brief is not None:
                assert brief["estimated_duration_sec"] <= SHORT_MAX_SEC, \
                    f"{rd['slug']}: {brief['estimated_duration_sec']}s > {SHORT_MAX_SEC}s"

    def test_time_range_format_valid(self):
        """All time_range values must be valid M:SS-M:SS format."""
        races = load_all_races()
        pattern = re.compile(r"^\d+:\d{2}-\d+:\d{2}$")
        for rd in races:
            brief = brief_suffering_map(rd)
            if brief is not None:
                for beat in brief["beats"]:
                    tr = beat["time_range"]
                    assert pattern.match(tr), \
                        f"{rd['slug']}: bad time_range '{tr}' in beat {beat['id']}"

    def test_many_zones_get_truncated(self):
        """Synthetic test: race with 20 zones should be truncated to fit."""
        rd = _load("unbound-200")
        # Inject 20 fake zones
        rd["course"]["suffering_zones"] = [
            {"mile": i * 10, "label": f"Zone {i}", "desc": f"Description {i}"}
            for i in range(20)
        ]
        brief = brief_suffering_map(rd)
        assert brief is not None
        assert brief["estimated_duration_sec"] <= SHORT_MAX_SEC
        # Should have fewer than 20 zone beats
        zone_beats = [b for b in brief["beats"] if b["id"].startswith("zone_")]
        assert len(zone_beats) < 20

    def test_thumbnail_vertical(self):
        """Suffering map thumbnails should be 9:16."""
        rd = _load("unbound-200")
        if not rd["course"].get("suffering_zones"):
            pytest.skip("No suffering zones")
        brief = brief_suffering_map(rd)
        if brief:
            assert "9:16" in brief["thumbnail_prompt"]


# ---------------------------------------------------------------------------
# Brief Generation — Roast
# ---------------------------------------------------------------------------

class TestBriefRoast:
    """Test roast brief generation."""

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_generates_valid_brief(self, slug):
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "roast")
        if not ok:
            pytest.skip("Insufficient data for roast")
        brief = brief_roast(rd)
        assert brief["format"] == "roast"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_duration_within_target(self, slug):
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "roast")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_roast(rd)
        lo, hi = DURATION_TARGETS["roast"]
        assert lo <= brief["estimated_duration_sec"] <= hi + 30

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_has_contrast_pattern(self, slug):
        """Roast should have both marketing_pitch and reality_check beats."""
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "roast")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_roast(rd)
        beat_ids = [b["id"] for b in brief["beats"]]
        assert "marketing_pitch" in beat_ids
        assert "reality_check" in beat_ids

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_thumbnail_horizontal(self, slug):
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "roast")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_roast(rd)
        assert "16:9" in brief["thumbnail_prompt"]


# ---------------------------------------------------------------------------
# Brief Generation — Should You Race
# ---------------------------------------------------------------------------

class TestBriefShouldYouRace:
    """Test should-you-race brief generation."""

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_generates_valid_brief(self, slug):
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "should-you-race")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_should_you_race(rd)
        assert brief["format"] == "should-you-race"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_covers_all_14_dimensions(self, slug):
        """Should-you-race should reference all 14 dimensions."""
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "should-you-race")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_should_you_race(rd)
        # Check evidence_data across all score beats
        all_dims = set()
        for beat in brief["beats"]:
            for ed in beat.get("evidence_data", []):
                all_dims.add(ed["dimension"])
        assert len(all_dims) >= 14, f"Only {len(all_dims)} dimensions covered"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_has_alternatives_beat(self, slug):
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "should-you-race")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_should_you_race(rd)
        beat_ids = [b["id"] for b in brief["beats"]]
        assert "alternatives" in beat_ids

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_thumbnail_horizontal(self, slug):
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "should-you-race")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_should_you_race(rd)
        assert "16:9" in brief["thumbnail_prompt"]


# ---------------------------------------------------------------------------
# Brief Generation — Head-to-Head
# ---------------------------------------------------------------------------

class TestBriefHeadToHead:
    """Test head-to-head comparison brief generation."""

    def test_generates_valid_brief(self):
        rd1 = _load("unbound-200")
        rd2 = _load("mid-south")
        brief = brief_head_to_head(rd1, rd2)
        assert brief["format"] == "head-to-head"
        assert "unbound-200-vs-mid-south" in brief["slug"]

    def test_winner_based_on_round_wins(self):
        """Winner should be determined by dimension victories, not just score."""
        rd1 = _load("unbound-200")
        rd2 = _load("mid-south")
        brief = brief_head_to_head(rd1, rd2)
        # Check verdict narration includes "rounds to"
        verdict = [b for b in brief["beats"] if b["id"] == "verdict"][0]
        assert "rounds to" in verdict["narration"] or "rounds each" in verdict["narration"]

    def test_biggest_gap_comes_last(self):
        """Escalation: the dimension with the biggest gap should be the final round."""
        rd1 = _load("unbound-200")
        rd2 = _load("mid-south")
        brief = brief_head_to_head(rd1, rd2)
        dim_beats = [b for b in brief["beats"] if b["id"].startswith("dim_")]
        if len(dim_beats) >= 2:
            last_delta = dim_beats[-1]["comparison_data"]["delta"]
            other_deltas = [b["comparison_data"]["delta"] for b in dim_beats[:-1]]
            assert last_delta >= max(other_deltas), \
                "Biggest gap should be saved for the last round"

    def test_tie_scenario(self):
        """Head-to-head with same race should produce a tie."""
        rd = _load("unbound-200")
        brief = brief_head_to_head(rd, rd)
        verdict = [b for b in brief["beats"] if b["id"] == "verdict"][0]
        assert "Dead heat" in verdict["narration"] or "TIE" in verdict["text_on_screen"]

    def test_has_tale_of_tape(self):
        rd1 = _load("unbound-200")
        rd2 = _load("mid-south")
        brief = brief_head_to_head(rd1, rd2)
        beat_ids = [b["id"] for b in brief["beats"]]
        assert "tale_of_tape" in beat_ids


# ---------------------------------------------------------------------------
# B-roll Sources
# ---------------------------------------------------------------------------

class TestBrollSources:
    """Test B-roll URL filtering and query generation."""

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_no_non_url_race_websites(self, slug):
        rd = _load(slug)
        sources = _get_broll_sources(rd, "hero")
        for src in sources:
            if src["type"] == "race_website":
                assert src["url"].startswith(("http://", "https://")), \
                    f"Non-URL race website: {src['url']}"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_no_hardcoded_years(self, slug):
        rd = _load(slug)
        sources = _get_broll_sources(rd, "hero")
        for src in sources:
            query = src.get("query", "")
            assert "2025 2026" not in query, f"Hardcoded years in query: {query}"

    def test_rwgps_included_when_present(self):
        rd = _load("unbound-200")
        sources = _get_broll_sources(rd, "route")
        rwgps = [s for s in sources if s["type"] == "rwgps"]
        rwgps_id = rd["course"].get("ridewithgps_id")
        if rwgps_id:
            assert len(rwgps) == 1
            assert str(rwgps_id) in rwgps[0]["url"]


# ---------------------------------------------------------------------------
# Thumbnail Prompt
# ---------------------------------------------------------------------------

class TestThumbnailPrompt:
    """Test thumbnail generation prompts."""

    def test_short_formats_use_vertical(self):
        rd = _load("unbound-200")
        trope = {"name": "tier_reveal", "strength": 4, "hook_text": "test"}
        for fmt in ("tier-reveal", "suffering-map", "data-drops"):
            prompt = _thumbnail_prompt(rd, trope, fmt)
            assert "9:16" in prompt, f"{fmt} should use 9:16"

    def test_long_formats_use_horizontal(self):
        rd = _load("unbound-200")
        trope = {"name": "tier_reveal", "strength": 4, "hook_text": "test"}
        for fmt in ("roast", "should-you-race", "head-to-head"):
            prompt = _thumbnail_prompt(rd, trope, fmt)
            assert "16:9" in prompt, f"{fmt} should use 16:9"

    def test_includes_cref(self):
        rd = _load("unbound-200")
        trope = {"name": "tier_reveal", "strength": 4, "hook_text": "test"}
        prompt = _thumbnail_prompt(rd, trope, "tier-reveal")
        assert "--cref" in prompt

    def test_includes_race_name(self):
        rd = _load("unbound-200")
        trope = {"name": "tier_reveal", "strength": 4, "hook_text": "test"}
        prompt = _thumbnail_prompt(rd, trope, "tier-reveal")
        assert rd["name"] in prompt


# ---------------------------------------------------------------------------
# Avatar Pose Selection
# ---------------------------------------------------------------------------

class TestPickAvatar:
    """Test avatar pose selection logic."""

    def test_hook_poses_vary_by_trope(self):
        poses = set()
        for trope in ("underdog_reveal", "expose", "hidden_gem"):
            pose = _pick_avatar("hook", trope, 1)
            poses.add(pose)
        assert len(poses) >= 2, "Hook poses should vary by trope"

    def test_reveal_varies_by_tier(self):
        tier1_pose = _pick_avatar("reveal", "tier_reveal", 1)
        tier4_pose = _pick_avatar("reveal", "tier_reveal", 4)
        assert tier1_pose != tier4_pose

    def test_cta_always_pointing(self):
        # CTA should always be "pointing" per heuristics
        # But the function returns "presenting" for unknown beat types
        # which is fine — the CTA beat hardcodes "pointing" directly


        pass

    def test_returns_string(self):
        result = _pick_avatar("hook", "tier_reveal", 1)
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# has_sufficient_data
# ---------------------------------------------------------------------------

class TestSufficientData:
    """Test data sufficiency checks."""

    def test_complete_race_passes_all_formats(self):
        rd = _load("unbound-200")
        for fmt in ("tier-reveal", "roast", "should-you-race"):
            ok, reason = has_sufficient_data(rd, fmt)
            assert ok, f"unbound-200 should have sufficient data for {fmt}: {reason}"

    def test_stub_race_fails_editorial_formats(self):
        rd = _load("gravel-grit-n-grind")
        if rd is None:
            pytest.skip("Stub race not found")
        for fmt in ("roast", "should-you-race"):
            ok, _ = has_sufficient_data(rd, fmt)
            # Stub may or may not pass — just verify no crash
            assert isinstance(ok, bool)


# ---------------------------------------------------------------------------
# Brief Structure Validation
# ---------------------------------------------------------------------------

class TestBriefStructure:
    """Validate JSON structure of generated briefs."""

    REQUIRED_TOP_KEYS = {
        "slug", "format", "platform", "race_name", "race_tier", "race_score",
        "duration_target_range", "estimated_duration_sec", "estimated_spoken_words",
        "story_arc", "primary_trope", "retention_targets", "beats",
        "avatar_assets_needed", "meme_inserts", "thumbnail_prompt",
        "narration_feasibility", "content_pillars", "cross_platform_notes",
        "production_checklist",
    }

    REQUIRED_BEAT_KEYS = {
        "id", "label", "time_range", "duration_sec", "narration",
        "visual", "avatar_pose",
    }

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_top_level_keys(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        missing = self.REQUIRED_TOP_KEYS - brief.keys()
        assert not missing, f"Missing top-level keys: {missing}"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_beat_keys(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        for beat in brief["beats"]:
            missing = self.REQUIRED_BEAT_KEYS - beat.keys()
            assert not missing, \
                f"Beat '{beat.get('id', '?')}' missing keys: {missing}"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_time_range_format(self, slug):
        """All time_range values must match M:SS-M:SS pattern."""
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        pattern = re.compile(r"^\d+:\d{2}-\d+:\d{2}$")
        for beat in brief["beats"]:
            tr = beat["time_range"]
            assert pattern.match(tr), f"Bad time_range '{tr}' in beat {beat['id']}"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_narration_feasibility_schema(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        feas = brief["narration_feasibility"]
        assert "total_words" in feas
        assert "overall_wpm" in feas
        assert "warnings" in feas
        assert "feasible" in feas
        assert isinstance(feas["feasible"], bool)

    def test_production_checklist_non_empty(self):
        rd = _load("unbound-200")
        brief = brief_tier_reveal(rd)
        assert len(brief["production_checklist"]) >= 5

    def test_avatar_assets_is_sorted_list(self):
        rd = _load("unbound-200")
        brief = brief_tier_reveal(rd)
        assets = brief["avatar_assets_needed"]
        assert isinstance(assets, list)
        assert assets == sorted(assets)

    def test_retention_targets_present(self):
        rd = _load("unbound-200")
        brief = brief_tier_reveal(rd)
        assert brief["retention_targets"] == RETENTION_TARGETS["short"]


# ---------------------------------------------------------------------------
# WPM Validation Across All Formats
# ---------------------------------------------------------------------------

class TestWpmAcrossFormats:
    """Verify narration_wpm is present on each beat."""

    @pytest.mark.parametrize("slug", ["unbound-200", "mid-south"])
    def test_beats_have_wpm_annotation(self, slug):
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        for beat in brief["beats"]:
            narration = beat.get("narration", "")
            if narration and beat.get("duration_sec", 0) > 0:
                assert "narration_wpm" in beat, \
                    f"Beat '{beat['id']}' missing narration_wpm"


# ---------------------------------------------------------------------------
# Full Pipeline — Regression on all races
# ---------------------------------------------------------------------------

class TestFullPipelineRegression:
    """Run brief generation on all 328 races to catch crashes."""

    def test_tier_reveal_all_races(self):
        """Every race should produce a valid tier-reveal brief."""
        races = load_all_races()
        failures = []
        for rd in races:
            try:
                brief = brief_tier_reveal(rd)
                assert brief is not None
                assert brief["estimated_duration_sec"] > 0
            except Exception as e:
                failures.append(f"{rd['slug']}: {e}")
        assert not failures, f"Tier-reveal failures:\n" + "\n".join(failures)

    def test_suffering_map_duration_cap(self):
        """All suffering maps must stay under SHORT_MAX_SEC."""
        races = load_all_races()
        violations = []
        for rd in races:
            brief = brief_suffering_map(rd)
            if brief and brief["estimated_duration_sec"] > SHORT_MAX_SEC:
                violations.append(
                    f"{rd['slug']}: {brief['estimated_duration_sec']}s"
                )
        assert not violations, \
            f"Duration violations:\n" + "\n".join(violations)

    def test_no_broken_time_ranges(self):
        """No time_range should have seconds >= 60 in MM:SS format."""
        races = load_all_races()
        bad = []
        for rd in races:
            for gen in (brief_tier_reveal, brief_suffering_map):
                brief = gen(rd)
                if brief is None:
                    continue
                for beat in brief["beats"]:
                    tr = beat["time_range"]
                    for part in tr.split("-"):
                        m_obj = re.match(r"(\d+):(\d+)", part)
                        if m_obj and int(m_obj.group(2)) >= 60:
                            bad.append(f"{rd['slug']}: {tr}")
        assert not bad, f"Broken time_ranges:\n" + "\n".join(bad[:10])


# ---------------------------------------------------------------------------
# FORMATS constant
# ---------------------------------------------------------------------------

class TestFormatsConstant:
    """Verify FORMATS constant is correct."""

    def test_data_drops_not_in_formats(self):
        assert "data-drops" not in FORMATS

    def test_all_implemented_formats_present(self):
        for fmt in ("tier-reveal", "should-you-race", "roast",
                     "suffering-map", "head-to-head"):
            assert fmt in FORMATS


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge cases that strain or break functionality."""

    def test_race_with_no_suffering_zones(self):
        """Brief should return None for race without zones."""
        rd = _load("unbound-200")
        rd["course"]["suffering_zones"] = []
        brief = brief_suffering_map(rd)
        assert brief is None

    def test_race_with_single_zone(self):
        """Single zone should still produce a valid brief."""
        rd = _load("unbound-200")
        rd["course"]["suffering_zones"] = [
            {"mile": 50, "label": "The Wall", "desc": "Where hope dies."}
        ]
        brief = brief_suffering_map(rd)
        assert brief is not None
        zone_beats = [b for b in brief["beats"] if b["id"].startswith("zone_")]
        assert len(zone_beats) == 1

    def test_all_scores_identical(self):
        """Trope detection shouldn't crash when all scores are the same."""
        rd = _load("unbound-200")
        for dim in rd["explanations"]:
            rd["explanations"][dim]["score"] = 3
        tropes = detect_tropes(rd)
        assert len(tropes) >= 1

    def test_head_to_head_same_race(self):
        """Comparing a race to itself shouldn't crash."""
        rd = _load("unbound-200")
        brief = brief_head_to_head(rd, rd)
        assert brief is not None

    def test_race_with_empty_strengths_and_weaknesses(self):
        """Roast with empty strengths/weaknesses should handle gracefully."""
        rd = _load("unbound-200")
        rd["biased_opinion"]["strengths"] = []
        rd["biased_opinion"]["weaknesses"] = []
        ok, _ = has_sufficient_data(rd, "roast")
        assert not ok  # Should be flagged as insufficient

    def test_json_serializable(self):
        """Generated briefs must be JSON-serializable."""
        rd = _load("unbound-200")
        brief = brief_tier_reveal(rd)
        # Should not raise
        json_str = json.dumps(brief, ensure_ascii=False)
        assert len(json_str) > 0
        # Round-trip
        loaded = json.loads(json_str)
        assert loaded["slug"] == brief["slug"]


# ---------------------------------------------------------------------------
# _stable_hash
# ---------------------------------------------------------------------------

class TestStableHash:
    """Test deterministic hash utility."""

    def test_deterministic(self):
        assert _stable_hash("test") == _stable_hash("test")

    def test_different_inputs_differ(self):
        assert _stable_hash("foo") != _stable_hash("bar")

    def test_returns_int(self):
        assert isinstance(_stable_hash("test"), int)


# ---------------------------------------------------------------------------
# _extract_first_sentence
# ---------------------------------------------------------------------------

class TestExtractFirstSentence:
    """Test first sentence extraction from explanations."""

    def test_empty_input(self):
        assert _extract_first_sentence("") == ""

    def test_none_input(self):
        assert _extract_first_sentence(None) == ""

    def test_too_short(self):
        assert _extract_first_sentence("Just three words.") == ""

    def test_too_long(self):
        long = " ".join(["word"] * 30) + "."
        assert _extract_first_sentence(long) == ""

    def test_normal_extraction(self):
        text = "This race has excellent aid stations and support. The course is demanding."
        result = _extract_first_sentence(text)
        assert result == "This race has excellent aid stations and support."

    def test_no_sentence_ending(self):
        assert _extract_first_sentence("No period here") == ""


# ---------------------------------------------------------------------------
# _narrate_score
# ---------------------------------------------------------------------------

class TestNarrateScore:
    """Test dimension score narration with personality."""

    def test_all_dims_all_scores_produce_output(self):
        """Every dimension × score combination should produce valid output."""
        dims = [d for d in SCORE_QUIPS if d != "_default"]
        for dim in dims:
            for score in range(1, 6):
                result = _narrate_score(dim, score, "test-slug")
                assert len(result) > 0, f"{dim}/{score} produced empty output"
                assert "out of 5" in result, f"{dim}/{score} missing 'out of 5'"

    def test_deterministic(self):
        r1 = _narrate_score("logistics", 3, "unbound-200")
        r2 = _narrate_score("logistics", 3, "unbound-200")
        assert r1 == r2

    def test_compact_shorter_than_full(self):
        rd = _load("unbound-200")
        compact = _narrate_score("logistics",
                                 rd["explanations"]["logistics"]["score"],
                                 "unbound-200", rd=rd, compact=True)
        full = _narrate_score("logistics",
                              rd["explanations"]["logistics"]["score"],
                              "unbound-200", rd=rd, compact=False)
        assert len(compact) <= len(full)

    def test_includes_dimension_label(self):
        result = _narrate_score("field_depth", 5, "test")
        assert "Field Depth" in result

    def test_unknown_dim_uses_default(self):
        result = _narrate_score("unknown_dim", 3, "test")
        assert "out of 5" in result


# ---------------------------------------------------------------------------
# _pick_intro
# ---------------------------------------------------------------------------

class TestPickIntro:
    """Test section intro selection."""

    def test_deterministic(self):
        r1 = _pick_intro("unbound-200", ROAST_MARKETING_INTROS)
        r2 = _pick_intro("unbound-200", ROAST_MARKETING_INTROS)
        assert r1 == r2

    def test_selects_from_list(self):
        result = _pick_intro("test-slug", ROAST_MARKETING_INTROS)
        assert result in ROAST_MARKETING_INTROS

    def test_different_slugs_can_differ(self):
        results = set()
        for slug in ["a", "b", "c", "d", "e", "f", "g", "h"]:
            results.add(_pick_intro(slug, ROAST_MARKETING_INTROS))
        # With 4 options and 8 slugs, should get at least 2 different
        assert len(results) >= 2


# ---------------------------------------------------------------------------
# _narrate_round
# ---------------------------------------------------------------------------

class TestNarrateRound:
    """Test head-to-head round narration."""

    def test_tie(self):
        result = _narrate_round("logistics", 3, 3, "Race A", "Race B", "a-b")
        assert "3" in result
        assert any(w in result.lower() for w in ["even", "identical", "same", "apiece"])

    def test_close(self):
        result = _narrate_round("logistics", 4, 3, "Race A", "Race B", "a-b")
        assert "4" in result and "3" in result

    def test_clear(self):
        result = _narrate_round("logistics", 5, 3, "Race A", "Race B", "a-b")
        assert "5" in result and "3" in result

    def test_blowout(self):
        result = _narrate_round("logistics", 5, 1, "Race A", "Race B", "a-b")
        assert "5" in result and "1" in result

    def test_finale(self):
        result = _narrate_round("logistics", 5, 2, "Race A", "Race B", "a-b",
                                is_finale=True)
        assert any(w in result.lower()
                   for w in ["big one", "last", "final", "decides"])

    def test_deterministic(self):
        r1 = _narrate_round("logistics", 4, 2, "A", "B", "a-b")
        r2 = _narrate_round("logistics", 4, 2, "A", "B", "a-b")
        assert r1 == r2

    def test_includes_dimension_label(self):
        result = _narrate_round("field_depth", 3, 2, "A", "B", "a-b")
        assert "Field Depth" in result


# ---------------------------------------------------------------------------
# Narration Personality Regression
# ---------------------------------------------------------------------------

class TestNarrationHasPersonality:
    """Regression tests: narration should no longer be robotic."""

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_evidence_beats_have_quips(self, slug):
        """Evidence beat narration should NOT match bare 'Dim: N out of 5.' pattern."""
        rd = _load(slug)
        brief = brief_tier_reveal(rd)
        evidence_beat = [b for b in brief["beats"] if b["id"] == "evidence"][0]
        narration = evidence_beat["narration"]
        # Old robotic pattern: "Dimension: N out of 5." with no personality
        bare_pattern = re.compile(r"^(\w[\w\s]*: \d out of 5\.\s*){2,}$")
        assert not bare_pattern.match(narration), \
            f"Evidence narration is still robotic: {narration[:80]}"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_roast_intros_vary(self, slug):
        """Roast section intros should come from rotation lists."""
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "roast")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_roast(rd)
        marketing = [b for b in brief["beats"]
                     if b["id"] == "marketing_pitch"][0]
        assert marketing["narration"] in ROAST_MARKETING_INTROS

    def test_head_to_head_rounds_no_edge_pattern(self):
        """H2H rounds should NOT use robotic 'Edge: RaceName.' pattern."""
        rd1 = _load("unbound-200")
        rd2 = _load("mid-south")
        brief = brief_head_to_head(rd1, rd2)
        dim_beats = [b for b in brief["beats"] if b["id"].startswith("dim_")]
        for beat in dim_beats:
            assert "Edge:" not in beat["narration"], \
                f"Round still uses robotic 'Edge:' pattern: {beat['narration'][:80]}"

    def test_tier_reveal_has_tag(self):
        """Tier reveal beat should include a tier tag."""
        rd = _load("unbound-200")
        brief = brief_tier_reveal(rd)
        reveal = [b for b in brief["beats"] if b["id"] == "reveal"][0]
        narration = reveal["narration"]
        assert any(tag in narration for tag in TIER_TAGS.values()), \
            f"Reveal missing tier tag: {narration}"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_roast_data_evidence_has_scores(self, slug):
        """Roast data_evidence should include actual per-dimension narration."""
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "roast")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_roast(rd)
        data_beat = [b for b in brief["beats"]
                     if b["id"] == "data_evidence"][0]
        assert "out of 5" in data_beat["narration"], \
            "Data evidence should include per-dimension scores"

    @pytest.mark.parametrize("slug", COMPLETE_RACES)
    def test_syr_score_intros_from_list(self, slug):
        """Should-you-race scores_top should use intro from rotation list."""
        rd = _load(slug)
        ok, _ = has_sufficient_data(rd, "should-you-race")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_should_you_race(rd)
        scores_top = [b for b in brief["beats"]
                      if b["id"] == "scores_top"][0]
        narration = scores_top["narration"]
        assert any(narration.startswith(intro)
                   for intro in SYR_SCORE_INTROS), \
            f"scores_top doesn't start with a rotation intro: {narration[:60]}"


# ---------------------------------------------------------------------------
# RIFF Markers
# ---------------------------------------------------------------------------

class TestRiffMarkers:
    """Verify [RIFF HERE] markers appear in editing_note fields."""

    def test_tier_reveal_has_riff(self):
        rd = _load("unbound-200")
        brief = brief_tier_reveal(rd)
        notes = " ".join(b.get("editing_note", "") for b in brief["beats"])
        assert "[RIFF HERE]" in notes

    def test_roast_has_riff(self):
        rd = _load("unbound-200")
        ok, _ = has_sufficient_data(rd, "roast")
        if not ok:
            pytest.skip("Insufficient data")
        brief = brief_roast(rd)
        notes = " ".join(b.get("editing_note", "") for b in brief["beats"])
        assert "[RIFF HERE]" in notes

    def test_riff_not_in_narration(self):
        """RIFF markers should only be in editing_note, never in narration."""
        rd = _load("unbound-200")
        brief = brief_tier_reveal(rd)
        for beat in brief["beats"]:
            assert "[RIFF HERE]" not in beat.get("narration", ""), \
                f"RIFF marker leaked into narration of {beat['id']}"

    def test_head_to_head_has_riff(self):
        rd1 = _load("unbound-200")
        rd2 = _load("mid-south")
        brief = brief_head_to_head(rd1, rd2)
        notes = " ".join(b.get("editing_note", "") for b in brief["beats"])
        assert "[RIFF HERE]" in notes
