"""Tests for the Gravel God MCP Server.

Tests all 6 tools and 2 resources against real race data,
plus edge case tests for every v2 bug fix.
"""

import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import mcp_server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_db():
    """Reset the singleton so each test gets a fresh DB."""
    mcp_server._db = None
    yield
    mcp_server._db = None


@pytest.fixture
def db():
    return mcp_server.get_db()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

class TestDataLoading:
    def test_index_loads(self, db):
        assert len(db.index) >= 328

    def test_index_entry_has_required_fields(self, db):
        entry = db.index[0]
        for field in ("name", "slug", "tier", "overall_score"):
            assert field in entry, f"Missing field: {field}"

    def test_profile_lazy_loads(self, db):
        assert len(db._profiles) == 0
        profile = db.get_profile("unbound-200")
        assert profile is not None
        assert "unbound-200" in db._profiles

    def test_missing_profile_returns_none(self, db):
        assert db.get_profile("nonexistent-race-xyz") is None


# ---------------------------------------------------------------------------
# Slug resolution
# ---------------------------------------------------------------------------

class TestSlugResolution:
    def test_exact_match(self, db):
        assert db.resolve_slug("unbound-200") == "unbound-200"

    def test_underscore_normalization(self, db):
        assert db.resolve_slug("unbound_200") == "unbound-200"

    def test_alias_dirty_kanza(self, db):
        assert db.resolve_slug("dirty-kanza") == "unbound-200"

    def test_alias_sbt_grvl(self, db):
        assert db.resolve_slug("sbt-grvl") == "steamboat-gravel"

    def test_alias_bwr(self, db):
        assert db.resolve_slug("bwr") == "bwr-california"

    def test_alias_leadville(self, db):
        assert db.resolve_slug("leadville") == "leadville-100"

    def test_substring_match(self, db):
        result = db.resolve_slug("mid-south")
        assert result == "mid-south"

    def test_nonexistent_returns_none(self, db):
        assert db.resolve_slug("nonexistent-race-xyz") is None

    def test_space_normalization(self, db):
        """Real users type spaces: 'unbound 200' should resolve."""
        result = db.resolve_slug("unbound 200")
        assert result == "unbound-200"

    def test_uppercase_normalization(self, db):
        """Real users type UPPERCASE: 'UNBOUND-200' should resolve."""
        result = db.resolve_slug("UNBOUND-200")
        assert result == "unbound-200"

    def test_mixed_case_space_normalization(self, db):
        """'Unbound 200' with mixed case and space."""
        result = db.resolve_slug("Unbound 200")
        assert result == "unbound-200"

    def test_alias_dirty_kanza_underscore(self, db):
        """dirty_kanza (underscore) should also resolve via alias."""
        result = db.resolve_slug("dirty_kanza")
        assert result == "unbound-200"

    def test_leading_trailing_whitespace(self, db):
        """Whitespace around slug should be stripped."""
        result = db.resolve_slug("  unbound-200  ")
        assert result == "unbound-200"


# ---------------------------------------------------------------------------
# search_races tool (v2: returns {"count": N, "results": [...]})
# ---------------------------------------------------------------------------

class TestSearchRaces:
    def test_returns_dict_with_count_and_results(self):
        resp = mcp_server.search_races()
        assert isinstance(resp, dict)
        assert "count" in resp
        assert "results" in resp
        assert isinstance(resp["results"], list)

    def test_no_filters_returns_up_to_limit(self):
        resp = mcp_server.search_races()
        assert len(resp["results"]) == 20  # default limit
        assert resp["count"] >= 328  # total matching

    def test_tier_filter(self):
        resp = mcp_server.search_races(tier=1, limit=100)
        results = resp["results"]
        assert all(r["tier"] == 1 for r in results)
        assert len(results) > 0

    def test_region_filter(self):
        resp = mcp_server.search_races(region="Pacific Northwest", limit=100)
        results = resp["results"]
        assert all(r["region"] == "Pacific Northwest" for r in results)

    def test_month_filter(self):
        resp = mcp_server.search_races(month="June", limit=100)
        results = resp["results"]
        assert all(r["month"] == "June" for r in results)

    def test_discipline_filter(self):
        resp = mcp_server.search_races(discipline="bikepacking", limit=100)
        results = resp["results"]
        assert all(r.get("discipline", "gravel") == "bikepacking" for r in results)

    def test_distance_range(self):
        resp = mcp_server.search_races(distance_min=100, distance_max=200, limit=100)
        for r in resp["results"]:
            d = r.get("distance_mi") or 0
            assert 100 <= d <= 200

    def test_text_search_name(self):
        resp = mcp_server.search_races(query="unbound")
        assert any("Unbound" in r["name"] for r in resp["results"])

    def test_text_search_location(self):
        resp = mcp_server.search_races(query="kansas")
        assert resp["count"] > 0

    def test_combined_filters(self):
        resp = mcp_server.search_races(tier=1, month="June", limit=100)
        assert all(r["tier"] == 1 and r["month"] == "June" for r in resp["results"])

    def test_results_sorted_by_score_desc(self):
        resp = mcp_server.search_races(limit=50)
        scores = [r.get("overall_score", 0) for r in resp["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_limit_capped_at_100(self):
        resp = mcp_server.search_races(limit=500)
        assert len(resp["results"]) <= 100

    def test_limit_minimum_1(self):
        resp = mcp_server.search_races(limit=0)
        assert len(resp["results"]) == 1

    def test_no_results_returns_empty(self):
        resp = mcp_server.search_races(query="zzzznonexistentracexxxx")
        assert resp["count"] == 0
        assert resp["results"] == []

    def test_count_reflects_total_not_page(self):
        resp = mcp_server.search_races(tier=1, limit=3)
        assert resp["count"] >= len(resp["results"])
        assert len(resp["results"]) <= 3

    def test_case_insensitive_text_search(self):
        """'UNBOUND' should match 'Unbound 200'."""
        resp = mcp_server.search_races(query="UNBOUND")
        assert any("Unbound" in r["name"] for r in resp["results"])

    def test_transcript_search(self):
        """The 'st' field in the index enables transcript search."""
        # At least one race has rider intel with transcript text
        resp = mcp_server.search_races(query="wind", limit=50)
        # 'wind' appears in many race descriptions/transcripts
        assert resp["count"] > 0

    def test_trivial_single_char_query(self):
        """Query='a' matches many races — should not crash or return weird results."""
        resp = mcp_server.search_races(query="a", limit=10)
        assert isinstance(resp["results"], list)
        assert resp["count"] > 0
        # Results should still be sorted by score
        scores = [r.get("overall_score", 0) for r in resp["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_case_insensitive_month_is_valid(self):
        """'JUNE' should be accepted (no warning) because we lowercase before check."""
        resp = mcp_server.search_races(month="JUNE", limit=5)
        assert "warnings" not in resp
        assert all(r["month"] == "June" for r in resp["results"])

    def test_case_insensitive_discipline_is_valid(self):
        """'GRAVEL' should be accepted."""
        resp = mcp_server.search_races(discipline="GRAVEL", limit=5)
        assert "warnings" not in resp

    def test_all_filters_combined(self):
        """All filters at once should AND correctly, not crash."""
        resp = mcp_server.search_races(
            query="race", tier=2, region="Midwest", month="June",
            distance_min=50, distance_max=200, discipline="gravel", limit=10,
        )
        # May return 0 results but must not crash
        assert isinstance(resp["results"], list)
        for r in resp["results"]:
            assert r["tier"] == 2
            assert r["region"] == "Midwest"


# ---------------------------------------------------------------------------
# get_race tool
# ---------------------------------------------------------------------------

class TestGetRace:
    def test_valid_slug(self):
        result = mcp_server.get_race("unbound-200")
        assert "race" in result
        assert result["race"]["name"] == "Unbound 200"

    def test_alias_resolution(self):
        result = mcp_server.get_race("dirty-kanza")
        assert "race" in result
        assert result["race"]["slug"] == "unbound-200"
        assert result["_resolved_from"] == "dirty-kanza"
        assert result["_canonical_slug"] == "unbound-200"

    def test_stripped_fields(self):
        result = mcp_server.get_race("unbound-200")
        race = result.get("race", {})
        for key in mcp_server._STRIP_KEYS:
            assert key not in race, f"Should strip {key}"

    def test_has_vitals(self):
        result = mcp_server.get_race("unbound-200")
        vitals = result["race"]["vitals"]
        assert vitals["distance_mi"] == 200
        assert vitals["elevation_ft"] == 11000

    def test_has_gravel_god_rating(self):
        result = mcp_server.get_race("unbound-200")
        rating = result["race"]["gravel_god_rating"]
        assert rating["tier"] == 1
        assert rating["overall_score"] >= 80

    def test_not_found(self):
        result = mcp_server.get_race("nonexistent-race-xyz")
        assert "error" in result

    def test_empty_slug_returns_error(self):
        result = mcp_server.get_race("")
        assert "error" in result

    def test_whitespace_slug_returns_error(self):
        result = mcp_server.get_race("   ")
        assert "error" in result


# ---------------------------------------------------------------------------
# compare_races tool
# ---------------------------------------------------------------------------

class TestCompareRaces:
    def test_two_races(self):
        result = mcp_server.compare_races(["unbound-200", "mid-south"])
        assert "races" in result
        assert len(result["races"]) == 2
        assert "dimensions" in result
        assert len(result["dimensions"]) == 14

    def test_four_races(self):
        result = mcp_server.compare_races([
            "unbound-200", "mid-south", "steamboat-gravel", "bwr-california"
        ])
        assert len(result["races"]) == 4

    def test_too_few(self):
        result = mcp_server.compare_races(["unbound-200"])
        assert "error" in result

    def test_empty_list(self):
        result = mcp_server.compare_races([])
        assert "error" in result

    def test_too_many(self):
        result = mcp_server.compare_races(["a", "b", "c", "d", "e"])
        assert "error" in result

    def test_not_found_race(self):
        result = mcp_server.compare_races(["unbound-200", "nonexistent-xyz"])
        assert "error" in result

    def test_has_dimension_scores(self):
        result = mcp_server.compare_races(["unbound-200", "mid-south"])
        race = result["races"][0]
        assert "logistics" in race
        assert "prestige" in race
        assert isinstance(race["logistics"], (int, float, type(None)))

    def test_has_vitals(self):
        result = mcp_server.compare_races(["unbound-200", "mid-south"])
        race = result["races"][0]
        assert "distance_mi" in race
        assert "elevation_ft" in race
        assert "location" in race


# ---------------------------------------------------------------------------
# get_training_context tool
# ---------------------------------------------------------------------------

class TestGetTrainingContext:
    def test_valid_race(self):
        ctx = mcp_server.get_training_context("unbound-200")
        assert ctx["race_name"] == "Unbound 200"
        assert ctx["distance_mi"] == 200
        assert ctx["elevation_ft"] == 11000
        assert ctx["tier"] == 1

    def test_has_emphasis(self):
        ctx = mcp_server.get_training_context("unbound-200")
        assert isinstance(ctx["strength_emphasis"], list)
        assert len(ctx["strength_emphasis"]) > 0

    def test_has_fueling(self):
        ctx = mcp_server.get_training_context("unbound-200")
        assert "cal/hr" in ctx["fueling_target"]

    def test_has_non_negotiables(self):
        ctx = mcp_server.get_training_context("unbound-200")
        assert isinstance(ctx["non_negotiables"], list)

    def test_has_profile_url(self):
        ctx = mcp_server.get_training_context("unbound-200")
        assert ctx["profile_url"].startswith("https://")

    def test_not_found(self):
        ctx = mcp_server.get_training_context("nonexistent-xyz")
        assert "error" in ctx

    def test_fueling_tiers(self):
        # Short race
        short = mcp_server.get_training_context("rock-cobbler")
        if "error" not in short:
            if (short.get("distance_mi") or 0) < 50:
                assert "150-250" in short["fueling_target"]

    def test_empty_slug_returns_error(self):
        ctx = mcp_server.get_training_context("")
        assert "error" in ctx


# ---------------------------------------------------------------------------
# find_similar_races tool (v2: entries include match_reasons)
# ---------------------------------------------------------------------------

class TestFindSimilarRaces:
    def test_returns_similar(self):
        result = mcp_server.find_similar_races("unbound-200")
        assert "reference" in result
        assert "similar" in result
        assert result["reference"]["slug"] == "unbound-200"
        assert len(result["similar"]) > 0

    def test_default_limit(self):
        result = mcp_server.find_similar_races("unbound-200")
        assert len(result["similar"]) <= 5

    def test_custom_limit(self):
        result = mcp_server.find_similar_races("unbound-200", limit=3)
        assert len(result["similar"]) <= 3

    def test_sorted_by_match_score(self):
        result = mcp_server.find_similar_races("unbound-200", limit=10)
        scores = [r["match_score"] for r in result["similar"]]
        assert scores == sorted(scores, reverse=True)

    def test_reference_excluded(self):
        result = mcp_server.find_similar_races("unbound-200", limit=100)
        slugs = [r["slug"] for r in result["similar"]]
        assert "unbound-200" not in slugs

    def test_match_score_fields(self):
        result = mcp_server.find_similar_races("unbound-200")
        if result["similar"]:
            r = result["similar"][0]
            assert "match_score" in r
            assert "slug" in r
            assert "name" in r

    def test_not_found(self):
        result = mcp_server.find_similar_races("nonexistent-xyz")
        assert "error" in result

    def test_match_reasons_present(self):
        """v2: each similar race must include match_reasons list."""
        result = mcp_server.find_similar_races("unbound-200")
        for r in result["similar"]:
            assert "match_reasons" in r
            assert isinstance(r["match_reasons"], list)
            assert len(r["match_reasons"]) > 0

    def test_match_reasons_are_meaningful_strings(self):
        """match_reasons should contain known descriptive strings."""
        valid_reasons = {"same tier", "same region", "same discipline",
                         "similar distance", "similar elevation", "same month"}
        result = mcp_server.find_similar_races("unbound-200", limit=20)
        for r in result["similar"]:
            for reason in r["match_reasons"]:
                assert reason in valid_reasons, f"Unknown reason: {reason}"

    def test_empty_slug_returns_error(self):
        result = mcp_server.find_similar_races("")
        assert "error" in result

    def test_limit_zero_returns_one(self):
        """limit=0 should be clamped to 1."""
        result = mcp_server.find_similar_races("unbound-200", limit=0)
        assert len(result["similar"]) >= 1

    def test_limit_capped_at_20(self):
        """limit=999 should be clamped to 20."""
        result = mcp_server.find_similar_races("unbound-200", limit=999)
        assert len(result["similar"]) <= 20


# ---------------------------------------------------------------------------
# get_race_calendar tool (v2: returns {"count": N, "results": [...]})
# ---------------------------------------------------------------------------

class TestGetRaceCalendar:
    def test_returns_dict_with_count_and_results(self):
        resp = mcp_server.get_race_calendar(month="June")
        assert isinstance(resp, dict)
        assert "count" in resp
        assert "results" in resp

    def test_month_filter(self):
        resp = mcp_server.get_race_calendar(month="June")
        assert all(r["month"] == "June" for r in resp["results"])

    def test_region_filter(self):
        resp = mcp_server.get_race_calendar(region="Pacific Northwest")
        assert all(r["region"] == "Pacific Northwest" for r in resp["results"])

    def test_combined(self):
        resp = mcp_server.get_race_calendar(month="June", region="Midwest")
        for r in resp["results"]:
            assert r["month"] == "June"
            assert r["region"] == "Midwest"

    def test_sorted_by_tier_then_score(self):
        resp = mcp_server.get_race_calendar(month="June", limit=50)
        results = resp["results"]
        for i in range(len(results) - 1):
            a, b = results[i], results[i + 1]
            if a["tier"] == b["tier"]:
                assert (a.get("overall_score") or 0) >= (b.get("overall_score") or 0)
            else:
                assert a["tier"] <= b["tier"]

    def test_no_filters_returns_all(self):
        resp = mcp_server.get_race_calendar(limit=100)
        assert len(resp["results"]) == 100  # capped at limit
        assert resp["count"] >= 328

    def test_limit_works(self):
        resp = mcp_server.get_race_calendar(month="June", limit=3)
        assert len(resp["results"]) <= 3

    def test_count_reflects_total_matching(self):
        resp = mcp_server.get_race_calendar(month="June")
        assert resp["count"] >= len(resp["results"])

    def test_default_limit_is_20(self):
        """No limit param should default to 20 results."""
        resp = mcp_server.get_race_calendar(month="June")
        assert len(resp["results"]) <= 20


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

class TestResources:
    def test_race_index_resource(self):
        result = mcp_server.race_index()
        assert isinstance(result, list)
        assert len(result) >= 328

    def test_race_profile_resource(self):
        result = mcp_server.race_profile("unbound-200")
        assert isinstance(result, dict)
        assert "race" in result
        # Resource returns FULL unabridged profile (not trimmed)
        race = result.get("race", {})
        # biased_opinion_ratings should still be present in resource
        assert "biased_opinion_ratings" in race

    def test_race_profile_not_found(self):
        result = mcp_server.race_profile("nonexistent-xyz")
        assert "error" in result


# ---------------------------------------------------------------------------
# Trimmed profile logic
# ---------------------------------------------------------------------------

class TestTrimmedProfile:
    def test_strips_internal_fields(self):
        db = mcp_server.get_db()
        trimmed = db.get_trimmed_profile("unbound-200")
        race = trimmed["race"]
        assert "biased_opinion_ratings" not in race
        assert "training_config" not in race
        assert "guide_variables" not in race
        assert "research_metadata" not in race
        assert "unsplash_photos" not in race

    def test_keeps_public_fields(self):
        db = mcp_server.get_db()
        trimmed = db.get_trimmed_profile("unbound-200")
        race = trimmed["race"]
        assert "vitals" in race
        assert "gravel_god_rating" in race
        assert "course_description" in race
        assert "final_verdict" in race
        assert "citations" in race


# ---------------------------------------------------------------------------
# CRITICAL BUG FIX: Mutation detection (deepcopy)
# ---------------------------------------------------------------------------

class TestMutationSafety:
    """get_trimmed_profile and race_profile resource must NOT mutate cached data."""

    def test_get_trimmed_profile_does_not_mutate_cache(self):
        """CRITICAL: get_trimmed_profile must deep-copy, not mutate the cached profile."""
        db = mcp_server.get_db()

        # Load the full profile into cache
        full = db.get_profile("unbound-200")
        assert full is not None
        race_keys_before = set(full.get("race", full).keys())

        # Now get a trimmed version (this used to mutate the cache)
        trimmed = db.get_trimmed_profile("unbound-200")
        trimmed_race = trimmed.get("race", trimmed)
        for key in mcp_server._STRIP_KEYS:
            assert key not in trimmed_race

        # Verify the cached profile was NOT mutated
        full_after = db.get_profile("unbound-200")
        race_keys_after = set(full_after.get("race", full_after).keys())
        assert race_keys_before == race_keys_after, \
            f"Cache was mutated! Lost keys: {race_keys_before - race_keys_after}"

    def test_get_trimmed_profile_returns_independent_copy(self):
        """Two calls should return independent objects."""
        db = mcp_server.get_db()
        a = db.get_trimmed_profile("unbound-200")
        b = db.get_trimmed_profile("unbound-200")
        assert a is not b
        # Mutating one should not affect the other
        a["_test_key"] = "mutated"
        assert "_test_key" not in b

    def test_resource_profile_does_not_mutate_cache(self):
        """race://{slug} resource returns deep copy, not cached reference."""
        db = mcp_server.get_db()
        # Pre-load cache
        db.get_profile("unbound-200")

        result = mcp_server.race_profile("unbound-200")
        result["_injected_key"] = True

        # Cache should be unaffected
        cached = db.get_profile("unbound-200")
        assert "_injected_key" not in cached

    def test_trimming_strips_then_cache_still_has_keys(self):
        """Repeated trim+full cycles must never lose cached keys."""
        db = mcp_server.get_db()
        for _ in range(3):
            trimmed = db.get_trimmed_profile("unbound-200")
            full = db.get_profile("unbound-200")
            race = full.get("race", full)
            # biased_opinion_ratings should always be present in full
            assert "biased_opinion_ratings" in race


# ---------------------------------------------------------------------------
# CRITICAL BUG FIX: Ambiguous substring matching
# ---------------------------------------------------------------------------

class TestAmbiguousSlugMatching:
    """Substring matching must only resolve when exactly ONE slug matches."""

    def test_ambiguous_substring_returns_none(self, db):
        """A substring matching multiple slugs must return None (not a random pick)."""
        # 'gravel' appears in many slugs -- must NOT match any
        result = db.resolve_slug("gravel")
        assert result is None, \
            f"Ambiguous substring 'gravel' should return None, got {result}"

    def test_unique_substring_resolves(self, db):
        """A substring matching exactly one slug should resolve."""
        # 'unbound-200' is a unique slug
        result = db.resolve_slug("unbound-200")
        assert result == "unbound-200"

    def test_deterministic_resolution(self, db):
        """Same input must always resolve to the same output (no set randomness)."""
        results = set()
        for _ in range(10):
            r = db.resolve_slug("mid-south")
            results.add(r)
        assert len(results) == 1, f"Non-deterministic resolution: {results}"


# ---------------------------------------------------------------------------
# CRITICAL BUG FIX: Path traversal defense
# ---------------------------------------------------------------------------

class TestPathTraversal:
    """Slug-based file loading must reject path traversal attempts."""

    def test_validate_slug_rejects_double_dot(self):
        assert mcp_server._validate_slug("../../etc/passwd") is False

    def test_validate_slug_rejects_forward_slash(self):
        assert mcp_server._validate_slug("foo/bar") is False

    def test_validate_slug_rejects_backslash(self):
        assert mcp_server._validate_slug("foo\\bar") is False

    def test_validate_slug_rejects_null_byte(self):
        assert mcp_server._validate_slug("foo\x00bar") is False

    def test_validate_slug_rejects_empty(self):
        assert mcp_server._validate_slug("") is False

    def test_validate_slug_accepts_valid(self):
        assert mcp_server._validate_slug("unbound-200") is True

    def test_load_profile_rejects_traversal(self, db):
        """_load_profile must not load files outside race-data/."""
        result = db._load_profile("../../etc/passwd")
        assert result is None

    def test_get_race_tool_traversal_safe(self):
        """get_race tool must reject traversal slugs."""
        result = mcp_server.get_race("../../../etc/passwd")
        assert "error" in result


# ---------------------------------------------------------------------------
# HIGH BUG FIX: Input validation and warnings
# ---------------------------------------------------------------------------

class TestInputValidation:
    """Invalid parameters should return warnings, not silently ignore."""

    def test_invalid_tier_warning(self):
        resp = mcp_server.search_races(tier=99)
        assert "warnings" in resp
        assert any("tier" in w.lower() for w in resp["warnings"])

    def test_invalid_month_warning(self):
        resp = mcp_server.search_races(month="NotAMonth")
        assert "warnings" in resp
        assert any("month" in w.lower() for w in resp["warnings"])

    def test_invalid_discipline_warning(self):
        resp = mcp_server.search_races(discipline="triathlon")
        assert "warnings" in resp
        assert any("discipline" in w.lower() for w in resp["warnings"])

    def test_invalid_region_warning(self):
        resp = mcp_server.search_races(region="Middle Earth")
        assert "warnings" in resp
        assert any("region" in w.lower() for w in resp["warnings"])

    def test_valid_params_no_warnings(self):
        resp = mcp_server.search_races(tier=1, month="June", discipline="gravel")
        assert "warnings" not in resp

    def test_calendar_invalid_month_warning(self):
        resp = mcp_server.get_race_calendar(month="NotAMonth")
        assert "warnings" in resp
        assert any("month" in w.lower() for w in resp["warnings"])

    def test_calendar_invalid_region_warning(self):
        resp = mcp_server.get_race_calendar(region="Narnia")
        assert "warnings" in resp
        assert any("region" in w.lower() for w in resp["warnings"])


# ---------------------------------------------------------------------------
# Helper function edge cases
# ---------------------------------------------------------------------------

class TestHelpers:
    """Edge cases for _num, _safe_str, _validate_slug."""

    def test_num_none(self):
        assert mcp_server._num(None) == 0

    def test_num_int(self):
        assert mcp_server._num(5) == 5.0

    def test_num_float(self):
        assert mcp_server._num(3.14) == 3.14

    def test_num_string(self):
        assert mcp_server._num("11,000") == 11000.0

    def test_num_garbage(self):
        assert mcp_server._num("N/A") == 0

    def test_num_zero(self):
        assert mcp_server._num(0) == 0.0

    def test_safe_str_none(self):
        assert mcp_server._safe_str(None) == ""

    def test_safe_str_zero(self):
        """CRITICAL: _safe_str(0) must return '0', not ''."""
        assert mcp_server._safe_str(0) == "0"

    def test_safe_str_false(self):
        assert mcp_server._safe_str(False) == "False"

    def test_safe_str_empty(self):
        assert mcp_server._safe_str("") == ""

    def test_safe_str_normal(self):
        assert mcp_server._safe_str("hello") == "hello"

    def test_num_negative(self):
        assert mcp_server._num(-5) == -5.0

    def test_num_empty_string(self):
        assert mcp_server._num("") == 0

    def test_num_list(self):
        """_num with non-scalar should return 0, not crash."""
        assert mcp_server._num([1, 2, 3]) == 0

    def test_num_bool(self):
        """bool is a subclass of int in Python. _num(True) = 1.0."""
        assert mcp_server._num(True) == 1.0
        assert mcp_server._num(False) == 0.0

    def test_num_very_large(self):
        assert mcp_server._num(999999999) == 999999999.0

    def test_safe_str_numeric(self):
        assert mcp_server._safe_str(42) == "42"
        assert mcp_server._safe_str(3.14) == "3.14"


# ---------------------------------------------------------------------------
# Startup / corrupt data handling
# ---------------------------------------------------------------------------

class TestCorruptDataHandling:
    """DB should handle corrupt or missing data gracefully."""

    def test_missing_index_file(self, tmp_path):
        """DB with no index file should have empty index."""
        db = mcp_server.RaceDB(
            index_path=tmp_path / "nonexistent.json",
            data_dir=tmp_path / "data",
        )
        assert db.index == []

    def test_corrupt_index_file(self, tmp_path):
        """DB with corrupt JSON index should have empty index."""
        bad_file = tmp_path / "corrupt.json"
        bad_file.write_text("{{{invalid json")
        db = mcp_server.RaceDB(index_path=bad_file, data_dir=tmp_path)
        assert db.index == []

    def test_corrupt_profile_file(self, tmp_path):
        """Corrupt individual profile JSON should return None."""
        index_file = tmp_path / "index.json"
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        # Write a valid index with one entry
        index_file.write_text(json.dumps([{"slug": "test-race", "name": "Test"}]))
        # Write corrupt profile
        (data_dir / "test-race.json").write_text("{{{bad")

        db = mcp_server.RaceDB(index_path=index_file, data_dir=data_dir)
        assert db.get_profile("test-race") is None

    def test_empty_index_file(self, tmp_path):
        """Empty but valid JSON array."""
        index_file = tmp_path / "empty.json"
        index_file.write_text("[]")
        db = mcp_server.RaceDB(index_path=index_file, data_dir=tmp_path)
        assert db.index == []
        assert len(db._slug_set) == 0


# ---------------------------------------------------------------------------
# VALID_MONTHS and VALID_DISCIPLINES constants
# ---------------------------------------------------------------------------

class TestValidConstants:
    def test_valid_months_has_12(self):
        assert len(mcp_server.VALID_MONTHS) == 12

    def test_valid_months_all_lowercase(self):
        for m in mcp_server.VALID_MONTHS:
            assert m == m.lower()

    def test_valid_disciplines(self):
        assert mcp_server.VALID_DISCIPLINES == {"gravel", "mtb", "bikepacking"}


# ---------------------------------------------------------------------------
# Synthetic data tests (isolated from real data, test logic not content)
# ---------------------------------------------------------------------------

class TestSyntheticDB:
    """Tests using controlled synthetic data via tmp_path, so logic is tested
    independently of real race files. No silent dependency on unbound-200.json."""

    @pytest.fixture
    def synthetic_db(self, tmp_path):
        """Build a tiny DB with 3 synthetic races."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()

        races = [
            {
                "slug": "alpha-race", "name": "Alpha Race", "tier": 1,
                "overall_score": 90, "distance_mi": 200, "elevation_ft": 10000,
                "location": "Denver, CO", "region": "Mountain West",
                "month": "June", "discipline": "gravel",
                "scores": {"logistics": 4, "prestige": 5},
            },
            {
                "slug": "beta-race", "name": "Beta Race", "tier": 2,
                "overall_score": 70, "distance_mi": 100, "elevation_ft": 5000,
                "location": "Portland, OR", "region": "Pacific Northwest",
                "month": "June", "discipline": "gravel",
                "scores": {"logistics": 3, "prestige": 3},
            },
            {
                "slug": "gamma-race", "name": "Gamma Race", "tier": 3,
                "overall_score": 50, "distance_mi": 50, "elevation_ft": 2000,
                "location": "Austin, TX", "region": "South Central",
                "month": "October", "discipline": "mtb",
                "scores": {"logistics": 2, "prestige": 2},
            },
        ]

        index_file = tmp_path / "index.json"
        index_file.write_text(json.dumps(races))

        # Write profile for alpha-race only (beta/gamma have no profile files)
        profile = {
            "race": {
                "name": "Alpha Race", "slug": "alpha-race", "tagline": "The alpha",
                "vitals": {"distance_mi": 200, "elevation_ft": 10000, "location": "Denver, CO"},
                "gravel_god_rating": {
                    "tier": 1, "overall_score": 90, "discipline": "gravel",
                    "logistics": 4, "prestige": 5, "elevation": 4,
                    "technicality": 3, "length": 5,
                },
                "course_description": {"character": "Brutal and beautiful"},
                "final_verdict": {"one_liner": "Go do it"},
                "non_negotiables": [{"requirement": "Train hard", "by_when": "May", "why": "It's hard"}],
                "biased_opinion_ratings": {"prestige": {"score": 5, "explanation": "Top tier"}},
                "training_config": {"heat_training": True},
                "citations": [{"url": "https://example.com", "label": "Source", "category": "official"}],
            }
        }
        (data_dir / "alpha-race.json").write_text(json.dumps(profile))

        return mcp_server.RaceDB(index_path=index_file, data_dir=data_dir)

    def test_search_tier_filter(self, synthetic_db):
        # Manually call the search logic through the DB
        assert len(synthetic_db.index) == 3
        t1 = [r for r in synthetic_db.index if r["tier"] == 1]
        assert len(t1) == 1
        assert t1[0]["slug"] == "alpha-race"

    def test_resolve_slug_exact(self, synthetic_db):
        assert synthetic_db.resolve_slug("alpha-race") == "alpha-race"

    def test_resolve_slug_not_found(self, synthetic_db):
        assert synthetic_db.resolve_slug("nonexistent") is None

    def test_get_profile_loads(self, synthetic_db):
        profile = synthetic_db.get_profile("alpha-race")
        assert profile is not None
        assert profile["race"]["name"] == "Alpha Race"

    def test_get_profile_missing_file(self, synthetic_db):
        """beta-race is in the index but has no profile file — must return None, not crash."""
        profile = synthetic_db.get_profile("beta-race")
        assert profile is None

    def test_trimmed_profile_deepcopy(self, synthetic_db):
        """Trimmed profile must not mutate cache, even with synthetic data."""
        full = synthetic_db.get_profile("alpha-race")
        assert "biased_opinion_ratings" in full["race"]

        trimmed = synthetic_db.get_trimmed_profile("alpha-race")
        assert "biased_opinion_ratings" not in trimmed["race"]

        # Cache still intact
        full_after = synthetic_db.get_profile("alpha-race")
        assert "biased_opinion_ratings" in full_after["race"]

    def test_training_context(self, synthetic_db):
        ctx = synthetic_db.training_context("alpha-race")
        assert ctx is not None
        assert ctx["race_name"] == "Alpha Race"
        assert ctx["distance_mi"] == 200
        assert "endurance" in ctx["strength_emphasis"]  # length >= 4

    def test_training_context_missing_profile(self, synthetic_db):
        ctx = synthetic_db.training_context("beta-race")
        assert ctx is None


# ---------------------------------------------------------------------------
# Silent failure detection
# ---------------------------------------------------------------------------

class TestSilentFailures:
    """Detect cases where the system returns plausible-looking but wrong results
    instead of errors. These are the bugs you don't find until production."""

    def test_search_with_invalid_tier_still_filters(self):
        """Tier=99 should warn AND return 0 results (not silently return all)."""
        resp = mcp_server.search_races(tier=99)
        assert resp["count"] == 0, \
            f"tier=99 should match 0 races, but matched {resp['count']}"

    def test_search_with_invalid_month_still_filters(self):
        """Invalid month should warn AND return 0 results."""
        resp = mcp_server.search_races(month="Smarch")
        assert resp["count"] == 0, \
            f"month='Smarch' should match 0 races, but matched {resp['count']}"

    def test_calendar_with_invalid_month_still_filters(self):
        resp = mcp_server.get_race_calendar(month="Smarch")
        assert resp["count"] == 0

    def test_every_index_entry_has_slug(self):
        """If any index entry is missing 'slug', many tools silently break."""
        db = mcp_server.get_db()
        for i, entry in enumerate(db.index):
            assert "slug" in entry, f"Index entry {i} missing 'slug': {entry}"

    def test_slug_set_matches_index(self):
        """_slug_set must be in sync with _index."""
        db = mcp_server.get_db()
        index_slugs = {r["slug"] for r in db.index}
        assert db._slug_set == index_slugs

    def test_regions_set_populated(self):
        """regions property should be non-empty for the real database."""
        db = mcp_server.get_db()
        assert len(db.regions) > 5, f"Only {len(db.regions)} regions found"

    def test_all_tiers_represented(self):
        """All 4 tiers should exist in the database."""
        db = mcp_server.get_db()
        tiers = {r.get("tier") for r in db.index}
        assert tiers == {1, 2, 3, 4}, f"Missing tiers: {tiers}"

    def test_no_none_slugs_in_index(self):
        """A None slug would silently break substring matching."""
        db = mcp_server.get_db()
        for entry in db.index:
            assert entry["slug"] is not None
            assert isinstance(entry["slug"], str)
            assert len(entry["slug"]) > 0
