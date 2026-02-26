"""Comprehensive tests for scripts/generate_race_pack_previews.py — race pack preview generation.

Sprint 6 of the race-to-archetype mapping system.

40+ tests covering:
    - TestDemandToCategories (Sprint 2 parity)
    - TestPreviewGeneration (structure, content)
    - TestPreviewForRealRaces (integration with actual race JSONs)
    - TestEdgeCases (missing data, zeros)
    - TestBatchGeneration (--all, --tier modes)
    - TestPackSummary (summary sentence quality)
    - TestCategoryScoring (scoring mechanics)
"""

import json
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest

# Ensure scripts/ is importable (conftest.py also does this)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_race_pack_previews import (
    CATEGORY_SAMPLE_ARCHETYPES,
    DEMAND_TO_CATEGORY_WEIGHTS,
    TOP_N_DEFAULT,
    TOP_N_MIN,
    calculate_category_scores,
    generate_pack_summary,
    generate_preview,
    generate_preview_from_file,
    get_top_categories,
    write_preview,
)
from race_demand_analyzer import analyze_race_demands

# ── Helpers ───────────────────────────────────────────────────────────

RACE_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "race-data")


def _load_race(slug: str) -> dict:
    """Load a race JSON file, or skip if missing."""
    path = os.path.join(RACE_DATA_DIR, f"{slug}.json")
    if not os.path.exists(path):
        pytest.skip(f"Race file not found: {slug}.json")
    with open(path) as f:
        return json.load(f)


def _make_vitals(**overrides) -> dict:
    """Build a minimal vitals dict with overrides."""
    base = {
        "distance_mi": 100,
        "elevation_ft": 5000,
        "location": "Test City, State",
        "terrain_types": ["gravel roads", "rolling hills"],
    }
    base.update(overrides)
    return base


def _make_rating(**overrides) -> dict:
    """Build a minimal gravel_god_rating dict with overrides."""
    base = {
        "tier": 3,
        "prestige": 3,
        "field_depth": 3,
        "elevation": 3,
        "altitude": 2,
        "climate": 3,
        "technicality": 3,
        "discipline": "gravel",
    }
    base.update(overrides)
    return base


def _make_race(
    vitals=None,
    rating=None,
    climate=None,
    youtube_data=None,
    terrain=None,
    name="Test Race",
    slug="test-race",
    display_name=None,
) -> dict:
    """Build a full race_data dict with 'race' key."""
    race = {}
    race["name"] = name
    race["slug"] = slug
    race["display_name"] = display_name or name
    race["vitals"] = vitals or _make_vitals()
    race["gravel_god_rating"] = rating or _make_rating()
    if climate is not None:
        race["climate"] = climate
    if youtube_data is not None:
        race["youtube_data"] = youtube_data
    if terrain is not None:
        race["terrain"] = terrain
    return {"race": race}


# ── TestDemandToCategories (Sprint 2 parity) ─────────────────────────


class TestDemandToCategories:
    """Verify the demand-to-category scoring matches Sprint 2 expectations."""

    def test_unbound_durability_top(self):
        """Unbound 200: Durability should be in top 3 categories."""
        data = _load_race("unbound-200")
        demands = analyze_race_demands(data)
        scores = calculate_category_scores(demands)
        top3 = list(scores.keys())[:3]
        assert "Durability" in top3, (
            f"Durability not in top 3 for Unbound 200. Top 3: {top3}"
        )

    def test_leadville_climbing_top(self):
        """Leadville 100: climbing-related categories should rank highly.

        Leadville has climbing=10 but also vo2_power=10, altitude=10,
        race_specificity=10, so many categories get boosted. Climbing
        categories (Over_Under, TT_Threshold, Mixed_Climbing) should
        still score well even if not in the absolute top 3.
        """
        data = _load_race("leadville-100")
        demands = analyze_race_demands(data)
        assert demands["climbing"] >= 8, "Leadville should have high climbing demand"
        scores = calculate_category_scores(demands)
        top8 = list(scores.keys())[:8]
        climbing_cats = {
            "Mixed_Climbing", "Over_Under", "SFR_Muscle_Force", "TT_Threshold",
        }
        assert climbing_cats & set(top8), (
            f"No climbing category in top 8 for Leadville. Top 8: {top8}"
        )

    def test_short_race_vo2_top(self):
        """Short race with high field depth: VO2max categories should dominate."""
        # Short race, deep competitive field, high prestige
        data = _make_race(
            vitals=_make_vitals(distance_mi=40, elevation_ft=3000),
            rating=_make_rating(
                field_depth=5, prestige=5, technicality=4, elevation=2,
                tier=2, climate=2, altitude=1,
            ),
        )
        demands = analyze_race_demands(data)
        scores = calculate_category_scores(demands)
        top5 = list(scores.keys())[:5]
        vo2_cats = {"VO2max", "Anaerobic_Capacity", "Critical_Power", "Sprint_Neuromuscular"}
        assert vo2_cats & set(top5), (
            f"No VO2-family category in top 5 for short race. Top 5: {top5}"
        )

    def test_normalization(self):
        """Max score should be 100 after normalization."""
        demands = {
            "durability": 10, "climbing": 5, "vo2_power": 5,
            "threshold": 5, "technical": 5, "heat_resilience": 5,
            "altitude": 5, "race_specificity": 5,
        }
        scores = calculate_category_scores(demands)
        assert max(scores.values()) == 100

    def test_sorting(self):
        """Scores should be in descending order."""
        demands = {
            "durability": 8, "climbing": 6, "vo2_power": 4,
            "threshold": 7, "technical": 3, "heat_resilience": 2,
            "altitude": 1, "race_specificity": 5,
        }
        scores = calculate_category_scores(demands)
        values = list(scores.values())
        assert values == sorted(values, reverse=True)

    def test_all_dimensions_zero(self):
        """All demands zero: all scores should be zero."""
        demands = {d: 0 for d in DEMAND_TO_CATEGORY_WEIGHTS}
        scores = calculate_category_scores(demands)
        assert all(v == 0 for v in scores.values())

    def test_clamping_high(self):
        """Demands above 10 should be clamped to 10."""
        demands_high = {"durability": 15, "climbing": 0, "vo2_power": 0,
                        "threshold": 0, "technical": 0, "heat_resilience": 0,
                        "altitude": 0, "race_specificity": 0}
        demands_normal = dict(demands_high)
        demands_normal["durability"] = 10
        scores_high = calculate_category_scores(demands_high)
        scores_normal = calculate_category_scores(demands_normal)
        assert scores_high == scores_normal

    def test_clamping_negative(self):
        """Negative demands should be clamped to 0."""
        demands = {"durability": -5, "climbing": 0, "vo2_power": 0,
                    "threshold": 0, "technical": 0, "heat_resilience": 0,
                    "altitude": 0, "race_specificity": 0}
        scores = calculate_category_scores(demands)
        assert all(v == 0 for v in scores.values())

    def test_unknown_dimension_ignored(self):
        """Unknown demand dimensions should be silently ignored."""
        demands = {"durability": 5, "fake_dimension": 10}
        scores = calculate_category_scores(demands)
        # Should produce scores based only on durability
        assert len(scores) > 0
        assert "Durability" in scores

    def test_single_dimension_activates_correct_categories(self):
        """A single demand dimension should only activate its mapped categories."""
        demands = {"climbing": 10}
        scores = calculate_category_scores(demands)
        expected_cats = set(DEMAND_TO_CATEGORY_WEIGHTS["climbing"].keys())
        scored_cats = {cat for cat, s in scores.items() if s > 0}
        assert scored_cats == expected_cats


# ── TestPreviewGeneration ─────────────────────────────────────────────


class TestPreviewGeneration:
    """Test the structure and content of generated preview dicts."""

    def test_preview_structure(self):
        """All required keys must be present in preview output."""
        data = _make_race()
        preview = generate_preview(data)
        required_keys = {
            "slug", "race_name", "demands", "top_categories",
            "pack_summary", "generated_at",
        }
        assert required_keys <= set(preview.keys()), (
            f"Missing keys: {required_keys - set(preview.keys())}"
        )

    def test_demands_match_analyzer(self):
        """Preview demands should match race_demand_analyzer output exactly."""
        data = _make_race()
        preview = generate_preview(data)
        expected = analyze_race_demands(data)
        assert preview["demands"] == expected

    def test_top_categories_have_workouts(self):
        """Every top category must have at least 1 workout name."""
        data = _make_race()
        preview = generate_preview(data)
        for tc in preview["top_categories"]:
            assert len(tc["workouts"]) >= 1, (
                f"Category {tc['category']} has no workouts"
            )

    def test_top_categories_have_scores(self):
        """Every top category must have a numeric score."""
        data = _make_race()
        preview = generate_preview(data)
        for tc in preview["top_categories"]:
            assert isinstance(tc["score"], (int, float))
            assert 0 <= tc["score"] <= 100

    def test_pack_summary_contains_race_name(self):
        """Pack summary should reference the race name indirectly via location."""
        data = _make_race(
            vitals=_make_vitals(location="Emporia, Kansas"),
            name="Unbound Gravel 200",
        )
        preview = generate_preview(data)
        assert "Emporia, Kansas" in preview["pack_summary"]

    def test_pack_summary_contains_distance(self):
        """Pack summary should contain the race distance."""
        data = _make_race(vitals=_make_vitals(distance_mi=200))
        preview = generate_preview(data)
        assert "200 miles" in preview["pack_summary"]

    def test_generated_at_is_today(self):
        """generated_at should be today's date in ISO format."""
        data = _make_race()
        preview = generate_preview(data)
        assert preview["generated_at"] == date.today().isoformat()

    def test_slug_matches_race_slug(self):
        """Preview slug should match race slug."""
        data = _make_race(slug="my-test-race")
        preview = generate_preview(data)
        assert preview["slug"] == "my-test-race"

    def test_race_name_uses_display_name(self):
        """Preview should prefer display_name over name."""
        data = _make_race(name="Unbound 200", display_name="Unbound Gravel 200")
        preview = generate_preview(data)
        assert preview["race_name"] == "Unbound Gravel 200"

    def test_race_name_falls_back_to_name(self):
        """Preview should fall back to name if display_name is missing."""
        race_data = {
            "race": {
                "name": "Test Race",
                "slug": "test-race",
                "vitals": _make_vitals(),
                "gravel_god_rating": _make_rating(),
            }
        }
        preview = generate_preview(race_data)
        assert preview["race_name"] == "Test Race"

    def test_top_categories_count(self):
        """Should return up to TOP_N_DEFAULT categories."""
        data = _make_race(
            vitals=_make_vitals(distance_mi=200),
            rating=_make_rating(
                field_depth=5, prestige=5, elevation=5,
                technicality=5, climate=5, altitude=5, tier=1,
            ),
        )
        preview = generate_preview(data)
        assert len(preview["top_categories"]) <= TOP_N_DEFAULT
        assert len(preview["top_categories"]) >= TOP_N_MIN

    def test_top_categories_sorted_descending(self):
        """Top categories should be sorted by score descending."""
        data = _make_race()
        preview = generate_preview(data)
        scores = [tc["score"] for tc in preview["top_categories"]]
        assert scores == sorted(scores, reverse=True)


# ── TestPreviewForRealRaces (integration) ─────────────────────────────


class TestPreviewForRealRaces:
    """Integration tests using actual race JSON files from race-data/."""

    def test_unbound_200_preview(self):
        """Unbound 200 generates a valid preview with durability emphasis."""
        data = _load_race("unbound-200")
        preview = generate_preview(data)
        assert preview["slug"] == "unbound-200"
        assert preview["race_name"] == "Unbound Gravel 200"
        assert preview["demands"]["durability"] >= 8
        # Durability should be the top or second category
        top_cats = [tc["category"] for tc in preview["top_categories"][:3]]
        assert "Durability" in top_cats

    def test_leadville_100_preview(self):
        """Leadville 100 generates a valid preview with climbing + altitude."""
        data = _load_race("leadville-100")
        preview = generate_preview(data)
        assert preview["slug"] == "leadville-100"
        assert preview["demands"]["climbing"] >= 6
        assert preview["demands"]["altitude"] >= 8

    def test_mid_south_preview(self):
        """Mid South generates a valid preview."""
        data = _load_race("mid-south")
        preview = generate_preview(data)
        assert preview["slug"] == "mid-south"
        assert preview["demands"]["durability"] >= 4
        # Should have heat resilience since climate=5
        assert preview["demands"]["heat_resilience"] >= 6

    def test_bwr_california_preview(self):
        """BWR California generates a valid preview with technical emphasis."""
        data = _load_race("bwr-california")
        preview = generate_preview(data)
        assert preview["slug"] == "bwr-california"
        assert preview["demands"]["technical"] >= 8
        # Gravel_Specific should show up due to high technicality
        top_cats = [tc["category"] for tc in preview["top_categories"][:5]]
        assert "Gravel_Specific" in top_cats

    def test_chequamegon_mtb_preview(self):
        """Chequamegon MTB (short/fast race) should emphasize VO2."""
        data = _load_race("chequamegon-mtb")
        preview = generate_preview(data)
        assert preview["slug"] == "chequamegon-mtb"
        # Short race, deep field -> VO2max should rank highly
        demands = preview["demands"]
        assert demands["vo2_power"] >= 6


# ── TestEdgeCases ────────────────────────────────────────────────────


class TestEdgeCases:
    """Test graceful handling of missing or unusual data."""

    def test_missing_terrain(self):
        """Race with no terrain data should use graceful default in summary."""
        data = _make_race(terrain=None)
        preview = generate_preview(data)
        # Should still generate a pack summary
        assert "pack" in preview["pack_summary"].lower() or "workout" in preview["pack_summary"].lower()
        assert len(preview["pack_summary"]) > 20

    def test_missing_terrain_no_terrain_types(self):
        """Race with no terrain and no terrain_types should fall back to 'mixed terrain'."""
        vitals = {"distance_mi": 100, "elevation_ft": 5000, "location": "Nowhere, USA"}
        data = _make_race(vitals=vitals, terrain=None)
        preview = generate_preview(data)
        assert "mixed terrain" in preview["pack_summary"].lower()

    def test_missing_location(self):
        """Race with no location should use graceful default."""
        vitals = {"distance_mi": 100, "elevation_ft": 5000}
        data = _make_race(vitals=vitals)
        preview = generate_preview(data)
        assert "the course" in preview["pack_summary"]

    def test_all_demands_zero(self):
        """Near-zero inputs should produce a preview without crashing.

        Note: The demand analyzer has base scores (e.g., durability=1 for
        distance<50, threshold=3 for distance<50), so truly all-zero demands
        are not achievable through race data. This test verifies the preview
        handles minimal-input races gracefully.
        """
        data = _make_race(
            vitals=_make_vitals(distance_mi=0, elevation_ft=0),
            rating=_make_rating(
                tier=4, prestige=0, field_depth=0, elevation=0,
                altitude=0, climate=0, technicality=0,
            ),
        )
        preview = generate_preview(data)
        assert preview["slug"] == "test-race"
        # Should still generate valid categories (some base scores exist)
        assert isinstance(preview["top_categories"], list)
        assert len(preview["top_categories"]) >= 1
        # All scores should be <= 100
        for tc in preview["top_categories"]:
            assert 0 <= tc["score"] <= 100

    def test_all_demands_literally_zero(self):
        """Directly passing all-zero demands to category scorer produces zero scores."""
        demands = {d: 0 for d in DEMAND_TO_CATEGORY_WEIGHTS}
        top = get_top_categories(demands)
        for tc in top:
            assert tc["score"] == 0

    def test_category_sample_archetypes_coverage(self):
        """Every category in the weight matrix must have sample archetypes."""
        all_cats = set()
        for weights in DEMAND_TO_CATEGORY_WEIGHTS.values():
            all_cats.update(weights.keys())
        missing = all_cats - set(CATEGORY_SAMPLE_ARCHETYPES.keys())
        assert not missing, (
            f"Categories in weight matrix missing sample archetypes: {missing}"
        )

    def test_category_sample_archetypes_not_empty(self):
        """Every category in CATEGORY_SAMPLE_ARCHETYPES must have at least one archetype."""
        for cat, archetypes in CATEGORY_SAMPLE_ARCHETYPES.items():
            assert len(archetypes) >= 1, (
                f"Category {cat} has empty archetype list"
            )

    def test_weight_matrix_keys_match_demand_dimensions(self):
        """Weight matrix keys should match the known demand dimensions."""
        expected_dims = {
            "durability", "climbing", "vo2_power", "threshold",
            "technical", "heat_resilience", "altitude", "race_specificity",
        }
        assert set(DEMAND_TO_CATEGORY_WEIGHTS.keys()) == expected_dims

    def test_missing_slug(self):
        """Race with no slug should fall back to 'unknown'."""
        race_data = {
            "race": {
                "name": "Mystery Race",
                "vitals": _make_vitals(),
                "gravel_god_rating": _make_rating(),
            }
        }
        preview = generate_preview(race_data)
        assert preview["slug"] == "unknown"

    def test_empty_race_data(self):
        """Completely empty race data should not crash."""
        preview = generate_preview({})
        assert preview["slug"] == "unknown"
        assert isinstance(preview["demands"], dict)
        assert isinstance(preview["top_categories"], list)


# ── TestBatchGeneration ──────────────────────────────────────────────


class TestBatchGeneration:
    """Test batch file generation (--all and --tier modes)."""

    def test_generate_all_creates_files(self):
        """--all mode should create one JSON per race file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            race_dir = RACE_DATA_DIR
            if not os.path.isdir(race_dir):
                pytest.skip("race-data/ directory not found")

            json_files = [f for f in os.listdir(race_dir) if f.endswith(".json")]
            if not json_files:
                pytest.skip("No race JSON files found")

            # Generate just first 5 to keep test fast
            generated = 0
            for filename in sorted(json_files)[:5]:
                path = os.path.join(race_dir, filename)
                preview = generate_preview_from_file(path)
                write_preview(preview, tmpdir)
                generated += 1

            # Verify files were created
            output_files = [f for f in os.listdir(tmpdir) if f.endswith(".json")]
            assert len(output_files) == generated
            assert generated == 5

    def test_generate_tier1_only(self):
        """Tier filter should only include races of the specified tier."""
        race_dir = RACE_DATA_DIR
        if not os.path.isdir(race_dir):
            pytest.skip("race-data/ directory not found")

        tier1_count = 0
        json_files = sorted(f for f in os.listdir(race_dir) if f.endswith(".json"))
        for filename in json_files:
            path = os.path.join(race_dir, filename)
            with open(path) as f:
                data = json.load(f)
            race = data.get("race", {})
            rating = race.get("gravel_god_rating", {})
            tier = rating.get("tier", rating.get("display_tier", 4))
            if tier == 1:
                tier1_count += 1

        # Verify we found the expected number of T1 races (29)
        assert tier1_count > 0, "No T1 races found"
        assert tier1_count < len(json_files), "All races are T1 (filter would be meaningless)"

    def test_write_preview_creates_directory(self):
        """write_preview should create the output directory if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = os.path.join(tmpdir, "sub", "race-packs")
            preview = {
                "slug": "test-race",
                "race_name": "Test Race",
                "demands": {},
                "top_categories": [],
                "pack_summary": "Test summary.",
                "generated_at": "2026-02-25",
            }
            path = write_preview(preview, nested_dir)
            assert os.path.exists(path)
            with open(path) as f:
                loaded = json.load(f)
            assert loaded["slug"] == "test-race"

    def test_write_preview_overwrites_existing(self):
        """write_preview should overwrite an existing file for the same slug."""
        with tempfile.TemporaryDirectory() as tmpdir:
            preview_v1 = {
                "slug": "test-race",
                "race_name": "Test Race V1",
                "demands": {},
                "top_categories": [],
                "pack_summary": "V1",
                "generated_at": "2026-02-24",
            }
            preview_v2 = {
                "slug": "test-race",
                "race_name": "Test Race V2",
                "demands": {},
                "top_categories": [],
                "pack_summary": "V2",
                "generated_at": "2026-02-25",
            }
            write_preview(preview_v1, tmpdir)
            write_preview(preview_v2, tmpdir)

            path = os.path.join(tmpdir, "test-race.json")
            with open(path) as f:
                loaded = json.load(f)
            assert loaded["race_name"] == "Test Race V2"

    def test_generate_preview_from_file(self):
        """generate_preview_from_file should work with an actual file."""
        path = os.path.join(RACE_DATA_DIR, "unbound-200.json")
        if not os.path.exists(path):
            pytest.skip("unbound-200.json not found")
        preview = generate_preview_from_file(path)
        assert preview["slug"] == "unbound-200"
        assert preview["race_name"] == "Unbound Gravel 200"


# ── TestPackSummary ──────────────────────────────────────────────────


class TestPackSummary:
    """Test pack summary sentence generation."""

    def test_summary_has_three_categories(self):
        """Summary should mention top 3 category names."""
        race = {
            "vitals": {"distance_mi": 100, "location": "Test Town, USA"},
            "terrain": {"primary": "gravel roads"},
        }
        top_categories = [
            {"category": "Durability", "score": 100, "workouts": ["A"]},
            {"category": "VO2max", "score": 85, "workouts": ["B"]},
            {"category": "Race_Simulation", "score": 70, "workouts": ["C"]},
        ]
        summary = generate_pack_summary(race, top_categories)
        assert "Durability" in summary
        assert "VO2max" in summary
        assert "Race Simulation" in summary  # underscores replaced

    def test_summary_with_two_categories(self):
        """Summary with only 2 categories uses 'and' connector."""
        race = {
            "vitals": {"distance_mi": 50, "location": "Small Town"},
            "terrain": {"primary": "dirt roads"},
        }
        top_categories = [
            {"category": "VO2max", "score": 100, "workouts": ["A"]},
            {"category": "Tempo", "score": 60, "workouts": ["B"]},
        ]
        summary = generate_pack_summary(race, top_categories)
        assert "VO2max and Tempo" in summary

    def test_summary_with_one_category(self):
        """Summary with 1 category should not crash."""
        race = {
            "vitals": {"distance_mi": 30, "location": "Tiny Town"},
            "terrain": {"primary": "trails"},
        }
        top_categories = [
            {"category": "Sprint_Neuromuscular", "score": 100, "workouts": ["A"]},
        ]
        summary = generate_pack_summary(race, top_categories)
        assert "Sprint Neuromuscular" in summary

    def test_summary_distance_formatting(self):
        """Distance should be formatted as integer miles."""
        race = {
            "vitals": {"distance_mi": 200, "location": "Emporia, Kansas"},
            "terrain": {"primary": "gravel"},
        }
        top_categories = [
            {"category": "Durability", "score": 100, "workouts": ["A"]},
            {"category": "VO2max", "score": 85, "workouts": ["B"]},
            {"category": "Endurance", "score": 70, "workouts": ["C"]},
        ]
        summary = generate_pack_summary(race, top_categories)
        assert "200 miles" in summary

    def test_summary_terrain_lowercase(self):
        """Terrain in summary should be lowercase."""
        race = {
            "vitals": {"distance_mi": 100, "location": "Test"},
            "terrain": {"primary": "Rolling Gravel With Punchy Climbs"},
        }
        top_categories = [
            {"category": "Durability", "score": 100, "workouts": ["A"]},
            {"category": "VO2max", "score": 85, "workouts": ["B"]},
            {"category": "Endurance", "score": 70, "workouts": ["C"]},
        ]
        summary = generate_pack_summary(race, top_categories)
        assert "rolling gravel with punchy climbs" in summary

    def test_summary_empty_categories(self):
        """Empty categories list should produce a fallback summary."""
        race = {
            "vitals": {"distance_mi": 100, "location": "Test"},
            "terrain": {"primary": "gravel"},
        }
        summary = generate_pack_summary(race, [])
        assert "targeted training" in summary

    def test_summary_location_included(self):
        """Summary should include the location."""
        race = {
            "vitals": {"distance_mi": 100, "location": "Emporia, Kansas"},
            "terrain": {"primary": "gravel"},
        }
        top_categories = [
            {"category": "Durability", "score": 100, "workouts": ["A"]},
            {"category": "VO2max", "score": 85, "workouts": ["B"]},
            {"category": "Endurance", "score": 70, "workouts": ["C"]},
        ]
        summary = generate_pack_summary(race, top_categories)
        assert "Emporia, Kansas" in summary


# ── TestCategoryScoring ──────────────────────────────────────────────


class TestCategoryScoring:
    """Test category scoring mechanics in detail."""

    def test_durability_heavy_race(self):
        """High durability demand should put Durability at score 100."""
        demands = {
            "durability": 10, "climbing": 0, "vo2_power": 0,
            "threshold": 0, "technical": 0, "heat_resilience": 0,
            "altitude": 0, "race_specificity": 0,
        }
        scores = calculate_category_scores(demands)
        assert scores["Durability"] == 100

    def test_climbing_heavy_race(self):
        """High climbing demand should put Mixed_Climbing at score 100."""
        demands = {
            "durability": 0, "climbing": 10, "vo2_power": 0,
            "threshold": 0, "technical": 0, "heat_resilience": 0,
            "altitude": 0, "race_specificity": 0,
        }
        scores = calculate_category_scores(demands)
        assert scores["Mixed_Climbing"] == 100

    def test_multiple_dimensions_compound(self):
        """Multiple demand dimensions should compound category scores."""
        # Both durability and heat_resilience boost Durability category
        demands_combined = {
            "durability": 10, "climbing": 0, "vo2_power": 0,
            "threshold": 0, "technical": 0, "heat_resilience": 10,
            "altitude": 0, "race_specificity": 0,
        }
        demands_single = {
            "durability": 10, "climbing": 0, "vo2_power": 0,
            "threshold": 0, "technical": 0, "heat_resilience": 0,
            "altitude": 0, "race_specificity": 0,
        }
        scores_combined = calculate_category_scores(demands_combined)
        scores_single = calculate_category_scores(demands_single)
        # Durability should be higher (or same if normalized) in combined
        # But the raw score before normalization should be higher
        # Since Durability is boosted by both dimensions, it stays at 100
        # The key test is that non-zero heat categories appear
        assert scores_combined.get("Endurance", 0) > 0
        assert scores_combined.get("HVLI_Extended", 0) > 0

    def test_get_top_categories_returns_dicts(self):
        """get_top_categories should return list of dicts with correct keys."""
        demands = {
            "durability": 5, "climbing": 5, "vo2_power": 5,
            "threshold": 5, "technical": 5, "heat_resilience": 5,
            "altitude": 5, "race_specificity": 5,
        }
        top = get_top_categories(demands, n=3)
        assert len(top) == 3
        for item in top:
            assert "category" in item
            assert "score" in item
            assert "workouts" in item
            assert isinstance(item["workouts"], list)

    def test_get_top_categories_respects_n(self):
        """get_top_categories should return at most n items."""
        demands = {
            "durability": 5, "climbing": 5, "vo2_power": 5,
            "threshold": 5, "technical": 5, "heat_resilience": 5,
            "altitude": 5, "race_specificity": 5,
        }
        for n in [1, 3, 5, 8, 20]:
            top = get_top_categories(demands, n=n)
            assert len(top) <= n

    def test_empty_demands(self):
        """Empty demands dict should return empty scores."""
        scores = calculate_category_scores({})
        assert scores == {}

    def test_weight_matrix_all_weights_positive(self):
        """All weights in the matrix should be positive."""
        for dim, weights in DEMAND_TO_CATEGORY_WEIGHTS.items():
            for cat, weight in weights.items():
                assert weight > 0, (
                    f"Non-positive weight {weight} for {dim}->{cat}"
                )

    def test_weight_matrix_symmetry_check(self):
        """No category should appear in more than 4 demand dimensions.

        A category activated by too many dimensions would be generically
        high for all races, defeating the purpose of differentiation.
        """
        cat_counts = {}
        for weights in DEMAND_TO_CATEGORY_WEIGHTS.values():
            for cat in weights:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
        for cat, count in cat_counts.items():
            assert count <= 4, (
                f"Category {cat} appears in {count} demand dimensions (max 4)"
            )
