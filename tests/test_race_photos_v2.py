"""Tests for scripts/generate_race_photos_v2.py — photo pipeline utilities."""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from generate_race_photos_v2 import (
    _parse_month,
    _join_natural,
    haversine_km,
    bearing_between,
    sample_route_points,
    encode_polyline,
    downsample_coords,
    build_landscape_prompt,
    select_hero,
    update_race_json,
    MONTH_SEASONS,
    MONTH_LIGHT,
    OUTPUT_DIR,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"


# ── Utility Tests ──────────────────────────────────────────────


class TestParseMonth:
    def test_january(self):
        assert _parse_month("2026: January 15") == 1

    def test_june(self):
        assert _parse_month("2026: June 6") == 6

    def test_december(self):
        assert _parse_month("2025: December 1-3") == 12

    def test_case_insensitive(self):
        assert _parse_month("MARCH 2026") == 3

    def test_none_input(self):
        assert _parse_month(None) is None

    def test_empty_string(self):
        assert _parse_month("") is None

    def test_no_month(self):
        assert _parse_month("TBD") is None

    def test_all_months_covered(self):
        months = ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November", "December"]
        for i, name in enumerate(months, 1):
            assert _parse_month(f"2026: {name} 1") == i


class TestJoinNatural:
    def test_empty(self):
        assert _join_natural([]) == ""

    def test_single(self):
        assert _join_natural(["gravel"]) == "gravel"

    def test_two(self):
        assert _join_natural(["gravel", "dirt"]) == "gravel and dirt"

    def test_three(self):
        assert _join_natural(["gravel", "dirt", "mud"]) == "gravel, dirt and mud"


# ── Geo Calculation Tests ──────────────────────────────────────


class TestHaversineKm:
    def test_same_point_is_zero(self):
        assert haversine_km(38.5, -96.0, 38.5, -96.0) == 0.0

    def test_known_distance(self):
        # Emporia, KS to Wichita, KS — approximately 110 km
        d = haversine_km(38.404, -96.182, 37.687, -97.330)
        assert 115 < d < 135

    def test_short_distance(self):
        # Two points ~1 km apart (approx 0.009 degrees latitude)
        d = haversine_km(38.0, -96.0, 38.009, -96.0)
        assert 0.8 < d < 1.2

    def test_symmetry(self):
        d1 = haversine_km(38.0, -96.0, 39.0, -95.0)
        d2 = haversine_km(39.0, -95.0, 38.0, -96.0)
        assert abs(d1 - d2) < 0.001


class TestBearingBetween:
    def test_due_north(self):
        b = bearing_between(38.0, -96.0, 39.0, -96.0)
        assert abs(b - 0) < 1 or abs(b - 360) < 1

    def test_due_east(self):
        b = bearing_between(38.0, -96.0, 38.0, -95.0)
        assert 89 < b < 91

    def test_due_south(self):
        b = bearing_between(39.0, -96.0, 38.0, -96.0)
        assert 179 < b < 181

    def test_due_west(self):
        b = bearing_between(38.0, -95.0, 38.0, -96.0)
        assert 269 < b < 271

    def test_range_0_to_360(self):
        # Bearing should always be 0-360
        for lat_offset in [-1, -0.5, 0.5, 1]:
            for lng_offset in [-1, -0.5, 0.5, 1]:
                b = bearing_between(38.0, -96.0, 38.0 + lat_offset, -96.0 + lng_offset)
                assert 0 <= b < 360


# ── Route Sampling Tests ──────────────────────────────────────


class TestSampleRoutePoints:
    def test_empty_input(self):
        assert sample_route_points([]) == []

    def test_too_few_points(self):
        assert sample_route_points([(38.0, -96.0), (38.1, -96.0)]) == []

    def test_short_route(self):
        # Route shorter than min_spacing_km
        coords = [(38.0, -96.0), (38.001, -96.0), (38.002, -96.0)]
        result = sample_route_points(coords, n=5, min_spacing_km=5)
        assert result == []

    def test_returns_tuples_of_three(self):
        # Generate a straight-line route ~100km
        coords = [(38.0 + i * 0.01, -96.0) for i in range(1000)]
        result = sample_route_points(coords, n=5, min_spacing_km=1)
        for pt in result:
            assert len(pt) == 3  # (lat, lng, heading)

    def test_headings_are_valid(self):
        coords = [(38.0 + i * 0.01, -96.0) for i in range(1000)]
        result = sample_route_points(coords, n=5, min_spacing_km=1)
        for lat, lng, heading in result:
            assert 0 <= heading < 360

    def test_minimum_spacing_enforced(self):
        coords = [(38.0 + i * 0.01, -96.0) for i in range(500)]
        result = sample_route_points(coords, n=10, min_spacing_km=5)
        # Check all pairs are at least min_spacing apart
        for i in range(len(result) - 1):
            d = haversine_km(result[i][0], result[i][1],
                             result[i + 1][0], result[i + 1][1])
            assert d >= 4.9  # small tolerance

    def test_skips_first_last_5_percent(self):
        # 100 points: should skip first 5 and last 5
        coords = [(38.0 + i * 0.01, -96.0) for i in range(100)]
        result = sample_route_points(coords, n=3, min_spacing_km=0.5)
        if result:
            # First sampled point should not be at (38.0, -96.0) (the very start)
            assert result[0][0] > 38.04  # at least past the 5% mark


# ── Polyline Encoding Tests ───────────────────────────────────


class TestEncodePolyline:
    def test_google_reference(self):
        # Google's documented example
        coords = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
        result = encode_polyline(coords)
        assert result == "_p~iF~ps|U_ulLnnqC_mqNvxq`@"

    def test_empty_input(self):
        assert encode_polyline([]) == ""

    def test_single_point(self):
        result = encode_polyline([(0.0, 0.0)])
        assert len(result) > 0

    def test_roundtrip_decodable(self):
        # Encoding should produce valid characters (all ASCII 63-126)
        coords = [(38.404, -96.182), (37.687, -97.330)]
        result = encode_polyline(coords)
        for char in result:
            assert 63 <= ord(char) <= 126


class TestDownsampleCoords:
    def test_short_list_unchanged(self):
        coords = [(i, i) for i in range(10)]
        result = downsample_coords(coords, max_points=100)
        assert result == coords

    def test_exact_max_unchanged(self):
        coords = [(i, i) for i in range(100)]
        result = downsample_coords(coords, max_points=100)
        assert len(result) == 100

    def test_downsampled_length(self):
        coords = [(i, i) for i in range(1000)]
        result = downsample_coords(coords, max_points=50)
        assert len(result) == 50

    def test_preserves_first_last(self):
        coords = [(i, i) for i in range(1000)]
        result = downsample_coords(coords, max_points=50)
        assert result[0] == coords[0]
        assert result[-1] == coords[-1]


# ── Landscape Prompt Tests ─────────────────────────────────────


class TestBuildLandscapePrompt:
    def _make_race(self, **overrides):
        race = {
            "name": "Test Race",
            "vitals": {
                "location": "Emporia, Kansas",
                "date_specific": "2026: June 6",
                "terrain_types": ["rolling gravel", "sharp limestone"],
            },
            "terrain": {
                "primary": "Rolling gravel with punchy climbs",
                "surface": "Chunky limestone",
                "features": ["Sustained rollers", "Creek crossings"],
            },
            "climate": {
                "primary": "Heat",
                "description": "June brings 85-95F days with high humidity.",
            },
            "course_description": {
                "character": "Relentless",
            },
        }
        race.update(overrides)
        return race

    def test_contains_location(self):
        prompt = build_landscape_prompt(self._make_race())
        assert "Emporia, Kansas" in prompt

    def test_contains_terrain(self):
        prompt = build_landscape_prompt(self._make_race())
        assert "rolling gravel" in prompt.lower() or "sharp limestone" in prompt.lower()

    def test_contains_season(self):
        prompt = build_landscape_prompt(self._make_race())
        assert "Summer" in prompt or "summer" in prompt

    def test_no_people_instruction(self):
        prompt = build_landscape_prompt(self._make_race())
        assert "No people" in prompt
        assert "no cyclists" in prompt

    def test_no_watermark_instruction(self):
        prompt = build_landscape_prompt(self._make_race())
        assert "no watermarks" in prompt

    def test_handles_dict_terrain_primary(self):
        race = self._make_race(
            terrain={"primary": {"type": "alpine gravel"}, "features": []},
            vitals={"location": "Alps", "date_specific": "2026: June 6", "terrain_types": []},
        )
        prompt = build_landscape_prompt(race)
        assert "alpine gravel" in prompt

    def test_handles_string_terrain(self):
        race = self._make_race(
            terrain="rough gravel roads",
            vitals={"location": "Outback", "date_specific": "2026: June 6", "terrain_types": []},
        )
        prompt = build_landscape_prompt(race)
        assert "rough gravel roads" in prompt

    def test_handles_missing_fields(self):
        race = {"name": "Minimal", "vitals": {}, "terrain": {}, "climate": {}}
        prompt = build_landscape_prompt(race)
        assert "empty gravel road" in prompt.lower()
        assert len(prompt) > 50

    def test_winter_season(self):
        race = self._make_race()
        race["vitals"]["date_specific"] = "2026: January 15"
        prompt = build_landscape_prompt(race)
        assert "Winter" in prompt or "winter" in prompt

    def test_climate_snippet_included(self):
        prompt = build_landscape_prompt(self._make_race())
        assert "85-95F" in prompt or "humidity" in prompt


# ── Hero Selection Tests ───────────────────────────────────────


class TestSelectHero:
    def test_street_view_preferred(self):
        photos = [
            {"type": "landscape", "file": "test-landscape.jpg", "alt": "x", "credit": "AI", "primary": False},
            {"type": "street-1", "file": "test-street-1.jpg", "alt": "x", "credit": "SV", "primary": False},
        ]
        with patch.object(Path, "exists", return_value=True):
            with patch("shutil.copy2"):
                result = select_hero("test", photos)
        hero = next(p for p in result if p["type"] == "hero")
        assert hero["primary"] is True
        assert hero["credit"] == "SV"

    def test_landscape_fallback(self):
        photos = [
            {"type": "landscape", "file": "test-landscape.jpg", "alt": "x", "credit": "AI", "primary": False},
            {"type": "map", "file": "test-map.jpg", "alt": "x", "credit": "GM", "primary": False},
        ]
        with patch.object(Path, "exists", return_value=True):
            with patch("shutil.copy2"):
                result = select_hero("test", photos)
        hero = next(p for p in result if p["type"] == "hero")
        assert hero["credit"] == "AI"

    def test_map_last_resort(self):
        photos = [
            {"type": "map", "file": "test-map.jpg", "alt": "x", "credit": "GM", "primary": False},
        ]
        with patch.object(Path, "exists", return_value=True):
            with patch("shutil.copy2"):
                result = select_hero("test", photos)
        hero = next(p for p in result if p["type"] == "hero")
        assert hero["credit"] == "GM"

    def test_empty_photos(self):
        result = select_hero("test", [])
        assert result == []

    def test_others_not_primary(self):
        photos = [
            {"type": "street-1", "file": "test-street-1.jpg", "alt": "x", "credit": "SV", "primary": False},
            {"type": "landscape", "file": "test-landscape.jpg", "alt": "x", "credit": "AI", "primary": False},
        ]
        with patch.object(Path, "exists", return_value=True):
            with patch("shutil.copy2"):
                result = select_hero("test", photos)
        non_hero = [p for p in result if p["type"] != "hero"]
        for p in non_hero:
            assert p["primary"] is False


# ── JSON Update Tests ──────────────────────────────────────────


class TestUpdateRaceJson:
    def test_writes_photos_to_race_key(self, tmp_path):
        # Create a minimal race JSON
        data = {"race": {"name": "Test", "slug": "test"}}
        data_file = tmp_path / "test.json"
        data_file.write_text(json.dumps(data))

        photos = [
            {"type": "hero", "file": "test-hero.jpg", "url": "/race-photos/test/test-hero.jpg",
             "alt": "Test", "credit": "AI", "primary": True},
        ]

        with patch("generate_race_photos_v2.DATA_DIR", tmp_path):
            update_race_json("test", photos)

        result = json.loads(data_file.read_text())
        assert "photos" in result["race"]
        assert len(result["race"]["photos"]) == 1
        assert result["race"]["photos"][0]["primary"] is True

    def test_preserves_existing_data(self, tmp_path):
        data = {"race": {"name": "Test", "slug": "test", "vitals": {"location": "Kansas"}}}
        data_file = tmp_path / "test.json"
        data_file.write_text(json.dumps(data))

        with patch("generate_race_photos_v2.DATA_DIR", tmp_path):
            update_race_json("test", [{"type": "hero"}])

        result = json.loads(data_file.read_text())
        assert result["race"]["vitals"]["location"] == "Kansas"

    def test_skips_missing_file(self, tmp_path):
        with patch("generate_race_photos_v2.DATA_DIR", tmp_path):
            # Should not raise
            update_race_json("nonexistent", [])


# ── Month/Season Constants Tests ──────────────────────────────


class TestConstants:
    def test_month_seasons_complete(self):
        for m in range(1, 13):
            assert m in MONTH_SEASONS

    def test_month_light_complete(self):
        for m in range(1, 13):
            assert m in MONTH_LIGHT


# ── Integration Tests with Real Race Data ─────────────────────


class TestRealRaceData:
    """Tests using actual race JSON files to validate prompt generation."""

    @pytest.fixture
    def unbound(self):
        data_file = DATA_DIR / "unbound-200.json"
        if not data_file.exists():
            pytest.skip("unbound-200.json not found")
        with open(data_file) as f:
            return json.load(f)["race"]

    @pytest.fixture
    def mid_south(self):
        data_file = DATA_DIR / "mid-south.json"
        if not data_file.exists():
            pytest.skip("mid-south.json not found")
        with open(data_file) as f:
            return json.load(f)["race"]

    def test_unbound_prompt_quality(self, unbound):
        prompt = build_landscape_prompt(unbound)
        assert "Kansas" in prompt
        assert "No people" in prompt
        assert len(prompt) > 200

    def test_mid_south_prompt_quality(self, mid_south):
        prompt = build_landscape_prompt(mid_south)
        assert "Oklahoma" in prompt
        assert "No people" in prompt

    def test_all_races_produce_valid_prompts(self):
        """Every race JSON should produce a non-empty landscape prompt."""
        for data_file in sorted(DATA_DIR.glob("*.json")):
            with open(data_file) as f:
                data = json.load(f)
            race = data.get("race", data)
            prompt = build_landscape_prompt(race)
            assert len(prompt) > 100, f"{data_file.stem}: prompt too short ({len(prompt)} chars)"
            assert "No people" in prompt, f"{data_file.stem}: missing 'No people' instruction"
            assert "no watermarks" in prompt, f"{data_file.stem}: missing 'no watermarks' instruction"

    def test_rwgps_coverage_count(self):
        """Verify RWGPS route coverage matches expected ~216/328."""
        rwgps_count = 0
        total = 0
        for data_file in sorted(DATA_DIR.glob("*.json")):
            total += 1
            with open(data_file) as f:
                data = json.load(f)
            race = data.get("race", data)
            course = race.get("course_description", {})
            if isinstance(course, dict) and course.get("ridewithgps_id"):
                rwgps_count += 1
        assert total == 328, f"Expected 328 races, got {total}"
        assert rwgps_count >= 210, f"Expected >=210 RWGPS routes, got {rwgps_count}"
