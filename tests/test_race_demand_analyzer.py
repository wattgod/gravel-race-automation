"""Comprehensive tests for scripts/race_demand_analyzer.py — 8-dimension demand vector."""

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure scripts/ is importable (conftest.py also does this)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from race_demand_analyzer import (
    DIMENSIONS,
    _score_altitude,
    _score_climbing,
    _score_durability,
    _score_heat_resilience,
    _score_race_specificity,
    _score_technical,
    _score_threshold,
    _score_vo2_power,
    analyze_race_demands,
    analyze_race_demands_from_file,
)

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
    base = {"distance_mi": 100, "elevation_ft": 5000}
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
    vitals=None, rating=None, climate=None, youtube_data=None, terrain=None
) -> dict:
    """Build a full race_data dict with 'race' key."""
    race = {}
    race["vitals"] = vitals or _make_vitals()
    race["gravel_god_rating"] = rating or _make_rating()
    if climate is not None:
        race["climate"] = climate
    if youtube_data is not None:
        race["youtube_data"] = youtube_data
    if terrain is not None:
        race["terrain"] = terrain
    return {"race": race}


# ── TestScoreDurability ───────────────────────────────────────────────


class TestScoreDurability:
    def test_ultra_200mi(self):
        vitals = _make_vitals(distance_mi=200)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 10

    def test_150mi(self):
        vitals = _make_vitals(distance_mi=150)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 8

    def test_100mi(self):
        vitals = _make_vitals(distance_mi=100)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 6

    def test_75mi(self):
        vitals = _make_vitals(distance_mi=75)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 4

    def test_50mi(self):
        vitals = _make_vitals(distance_mi=50)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 2

    def test_short_30mi(self):
        vitals = _make_vitals(distance_mi=30)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 1

    def test_bikepacking_boost(self):
        """100mi gravel = 6, bikepacking +2 = 8."""
        vitals = _make_vitals(distance_mi=100)
        rating = _make_rating(discipline="bikepacking")
        assert _score_durability(vitals, rating) == 8

    def test_bikepacking_cap_at_10(self):
        """200mi = 10, bikepacking +2 still capped at 10."""
        vitals = _make_vitals(distance_mi=200)
        rating = _make_rating(discipline="bikepacking")
        assert _score_durability(vitals, rating) == 10

    def test_zero_distance(self):
        vitals = _make_vitals(distance_mi=0)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 1

    def test_boundary_199mi(self):
        vitals = _make_vitals(distance_mi=199)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 8

    def test_boundary_49mi(self):
        vitals = _make_vitals(distance_mi=49)
        rating = _make_rating()
        assert _score_durability(vitals, rating) == 1


# ── TestScoreClimbing ─────────────────────────────────────────────────


class TestScoreClimbing:
    def test_high_elevation(self):
        """10000ft, score 5 -> min(10, round(7.5+2.0)) = min(10, 10) = 10."""
        vitals = _make_vitals(elevation_ft=10000)
        rating = _make_rating(elevation=5)
        assert _score_climbing(vitals, rating) == 10

    def test_moderate_elevation(self):
        """5000ft, score 3 -> min(10, round(4.5+1.0)) = min(10, round(5.5)) = min(10, 6) = 6."""
        vitals = _make_vitals(elevation_ft=5000)
        rating = _make_rating(elevation=3)
        assert _score_climbing(vitals, rating) == 6

    def test_flat(self):
        """1000ft, score 1 -> min(10, round(1.5+0.2)) = min(10, round(1.7)) = min(10, 2) = 2."""
        vitals = _make_vitals(elevation_ft=1000)
        rating = _make_rating(elevation=1)
        assert _score_climbing(vitals, rating) == 2

    def test_extreme_elevation_80k(self):
        """80000ft, score 5 -> min(10, round(7.5+16)) = min(10, 24) = 10."""
        vitals = _make_vitals(elevation_ft=80000)
        rating = _make_rating(elevation=5)
        assert _score_climbing(vitals, rating) == 10

    def test_zero_elevation(self):
        vitals = _make_vitals(elevation_ft=0)
        rating = _make_rating(elevation=0)
        assert _score_climbing(vitals, rating) == 0

    def test_mid_range(self):
        """3000ft, score 2 -> min(10, round(3.0+0.6)) = min(10, round(3.6)) = 4."""
        vitals = _make_vitals(elevation_ft=3000)
        rating = _make_rating(elevation=2)
        assert _score_climbing(vitals, rating) == 4


# ── TestScoreVo2Power ─────────────────────────────────────────────────


class TestScoreVo2Power:
    def test_elite_field(self):
        """field_depth=5, prestige=5 -> 10."""
        rating = _make_rating(field_depth=5, prestige=5)
        assert _score_vo2_power(rating) == 10

    def test_local_race(self):
        """field_depth=2, prestige=1 -> 3."""
        rating = _make_rating(field_depth=2, prestige=1)
        assert _score_vo2_power(rating) == 3

    def test_mid_tier(self):
        """field_depth=3, prestige=3 -> 6."""
        rating = _make_rating(field_depth=3, prestige=3)
        assert _score_vo2_power(rating) == 6

    def test_zero_fields(self):
        rating = _make_rating(field_depth=0, prestige=0)
        assert _score_vo2_power(rating) == 0

    def test_max_possible(self):
        """field_depth=5, prestige=5 -> 10 (capped)."""
        rating = _make_rating(field_depth=5, prestige=5)
        assert _score_vo2_power(rating) == 10


# ── TestScoreThreshold ────────────────────────────────────────────────


class TestScoreThreshold:
    def test_100mi(self):
        """100mi is in 75-150 range -> 7."""
        vitals = _make_vitals(distance_mi=100)
        rating = _make_rating(elevation=2)
        assert _score_threshold(vitals, rating) == 7

    def test_60mi(self):
        """60mi is in 50-75 range -> 5."""
        vitals = _make_vitals(distance_mi=60)
        rating = _make_rating(elevation=2)
        assert _score_threshold(vitals, rating) == 5

    def test_200mi(self):
        """200mi > 150 -> 4."""
        vitals = _make_vitals(distance_mi=200)
        rating = _make_rating(elevation=2)
        assert _score_threshold(vitals, rating) == 4

    def test_30mi(self):
        """30mi else -> 3."""
        vitals = _make_vitals(distance_mi=30)
        rating = _make_rating(elevation=2)
        assert _score_threshold(vitals, rating) == 3

    def test_climbing_boost(self):
        """100mi + elev_score 4 -> 7 + 1 = 8."""
        vitals = _make_vitals(distance_mi=100)
        rating = _make_rating(elevation=4)
        assert _score_threshold(vitals, rating) == 8

    def test_climbing_boost_at_boundary(self):
        """elev_score 3 exactly -> +1."""
        vitals = _make_vitals(distance_mi=100)
        rating = _make_rating(elevation=3)
        assert _score_threshold(vitals, rating) == 8

    def test_no_climbing_boost(self):
        """elev_score 2 -> no boost."""
        vitals = _make_vitals(distance_mi=100)
        rating = _make_rating(elevation=2)
        assert _score_threshold(vitals, rating) == 7

    def test_75mi_boundary(self):
        """75mi is in the 75-150 range -> 7."""
        vitals = _make_vitals(distance_mi=75)
        rating = _make_rating(elevation=1)
        assert _score_threshold(vitals, rating) == 7

    def test_150mi_boundary(self):
        """150mi is in the 75-150 range -> 7."""
        vitals = _make_vitals(distance_mi=150)
        rating = _make_rating(elevation=1)
        assert _score_threshold(vitals, rating) == 7

    def test_151mi(self):
        """151mi > 150 -> 4."""
        vitals = _make_vitals(distance_mi=151)
        rating = _make_rating(elevation=1)
        assert _score_threshold(vitals, rating) == 4


# ── TestScoreTechnical ────────────────────────────────────────────────


class TestScoreTechnical:
    def test_very_technical(self):
        """technicality 5 -> 10."""
        rating = _make_rating(technicality=5)
        assert _score_technical(rating) == 10

    def test_moderate(self):
        """technicality 3 -> 6."""
        rating = _make_rating(technicality=3)
        assert _score_technical(rating) == 6

    def test_smooth(self):
        """technicality 1 -> 2."""
        rating = _make_rating(technicality=1)
        assert _score_technical(rating) == 2

    def test_zero(self):
        rating = _make_rating(technicality=0)
        assert _score_technical(rating) == 0

    def test_max_cap(self):
        """technicality 5 -> 10, not 10+."""
        rating = _make_rating(technicality=5)
        assert _score_technical(rating) == 10


# ── TestScoreHeatResilience ───────────────────────────────────────────


class TestScoreHeatResilience:
    def test_hot_race(self):
        """climate=5 -> base 10, already at cap."""
        race_data = _make_race(rating=_make_rating(climate=5))
        race = race_data["race"]
        assert _score_heat_resilience(race) == 10

    def test_mild_race(self):
        """climate=2 -> base 0, no intel, no challenges -> 0."""
        race_data = _make_race(rating=_make_rating(climate=2))
        race = race_data["race"]
        assert _score_heat_resilience(race) == 0

    def test_rider_intel_boost(self):
        """climate=4 -> base 6, rider intel mentions 'heat' -> +2 = 8."""
        youtube_data = {
            "rider_intel": {
                "search_text": "The heat was brutal and riders struggled with hydration."
            }
        }
        race_data = _make_race(
            rating=_make_rating(climate=4),
            youtube_data=youtube_data,
        )
        race = race_data["race"]
        assert _score_heat_resilience(race) == 8

    def test_no_rider_intel(self):
        """climate=4 -> base 6, no rider intel -> 6."""
        race_data = _make_race(rating=_make_rating(climate=4))
        race = race_data["race"]
        assert _score_heat_resilience(race) == 6

    def test_climate_challenges_boost(self):
        """climate=4 -> base 6, challenges mention heat -> +1 = 7."""
        race_data = _make_race(
            rating=_make_rating(climate=4),
            climate={"challenges": ["Heat adaptation critical", "Wind exposure"]},
        )
        race = race_data["race"]
        assert _score_heat_resilience(race) == 7

    def test_intel_and_challenges_combined(self):
        """climate=4 -> base 6, intel +2 + challenges +1 = 9."""
        youtube_data = {
            "rider_intel": {"search_text": "Record heat and humidity levels."}
        }
        race_data = _make_race(
            rating=_make_rating(climate=4),
            youtube_data=youtube_data,
            climate={"challenges": ["Heat adaptation critical"]},
        )
        race = race_data["race"]
        assert _score_heat_resilience(race) == 9

    def test_low_climate_with_heat_challenges(self):
        """climate=2 -> base 0, but challenges mention 'Extreme heat' -> +1 = 1."""
        race_data = _make_race(
            rating=_make_rating(climate=2),
            climate={"challenges": ["Extreme heat", "Cold nights"]},
        )
        race = race_data["race"]
        assert _score_heat_resilience(race) == 1

    def test_low_climate_with_rider_intel_heat(self):
        """climate=2 -> base 0, rider intel mentions 'hot' -> +2 = 2."""
        youtube_data = {
            "rider_intel": {"search_text": "It was really hot out there."}
        }
        race_data = _make_race(
            rating=_make_rating(climate=2),
            youtube_data=youtube_data,
        )
        race = race_data["race"]
        assert _score_heat_resilience(race) == 2

    def test_empty_challenges(self):
        """Empty challenges list -> no boost."""
        race_data = _make_race(
            rating=_make_rating(climate=4),
            climate={"challenges": []},
        )
        race = race_data["race"]
        assert _score_heat_resilience(race) == 6


# ── TestScoreAltitude ─────────────────────────────────────────────────


class TestScoreAltitude:
    def test_high_altitude(self):
        """altitude_score 5 -> 10."""
        rating = _make_rating(altitude=5)
        assert _score_altitude(rating) == 10

    def test_low_altitude(self):
        """altitude_score 1 -> 2."""
        rating = _make_rating(altitude=1)
        assert _score_altitude(rating) == 2

    def test_no_altitude(self):
        """altitude_score 0 -> 0."""
        rating = _make_rating(altitude=0)
        assert _score_altitude(rating) == 0

    def test_mid_altitude(self):
        """altitude_score 3 -> 6."""
        rating = _make_rating(altitude=3)
        assert _score_altitude(rating) == 6


# ── TestScoreRaceSpecificity ──────────────────────────────────────────


class TestScoreRaceSpecificity:
    def test_tier1_prestige5(self):
        """min(10, round((5-1)*2+5)) = min(10, 13) = 10."""
        rating = _make_rating(tier=1, prestige=5)
        assert _score_race_specificity(rating) == 10

    def test_tier4_prestige1(self):
        """min(10, round((5-4)*2+1)) = min(10, 3) = 3."""
        rating = _make_rating(tier=4, prestige=1)
        assert _score_race_specificity(rating) == 3

    def test_tier2_prestige3(self):
        """min(10, round((5-2)*2+3)) = min(10, 9) = 9."""
        rating = _make_rating(tier=2, prestige=3)
        assert _score_race_specificity(rating) == 9

    def test_tier3_prestige2(self):
        """min(10, round((5-3)*2+2)) = min(10, 6) = 6."""
        rating = _make_rating(tier=3, prestige=2)
        assert _score_race_specificity(rating) == 6

    def test_tier1_prestige1(self):
        """min(10, round((5-1)*2+1)) = min(10, 9) = 9."""
        rating = _make_rating(tier=1, prestige=1)
        assert _score_race_specificity(rating) == 9


# ── TestAnalyzeRaceDemands (integration with real race JSON) ──────────


class TestAnalyzeRaceDemands:
    def test_unbound_200(self):
        data = _load_race("unbound-200")
        demands = analyze_race_demands(data)
        assert demands["durability"] == 10
        assert demands["vo2_power"] == 10
        # climate=5 -> base 10, challenges have 'Heat adaptation critical' -> +1 but already capped
        assert demands["heat_resilience"] >= 8
        assert demands["heat_resilience"] == 10

    def test_leadville_100(self):
        data = _load_race("leadville-100")
        demands = analyze_race_demands(data)
        # elevation=5, 11900ft -> min(10, round(7.5+2.38)) = 10
        assert demands["climbing"] >= 8
        assert demands["climbing"] == 10
        # altitude=5 -> 10
        assert demands["altitude"] >= 8
        assert demands["altitude"] == 10

    def test_mid_south(self):
        data = _load_race("mid-south")
        demands = analyze_race_demands(data)
        # 100mi in 75-150 -> 7, elevation=2 < 3 -> no boost -> 7
        assert demands["threshold"] == 7

    def test_atlas_mountain_race(self):
        data = _load_race("atlas-mountain-race")
        demands = analyze_race_demands(data)
        # 750mi bikepacking -> 10+2 but capped at 10
        assert demands["durability"] == 10
        # elevation=5, 80000ft -> min(10, round(7.5+16)) = 10
        assert demands["climbing"] == 10

    def test_bwr_california(self):
        data = _load_race("bwr-california")
        demands = analyze_race_demands(data)
        # field_depth=5, prestige=5 -> 10
        assert demands["vo2_power"] >= 8
        assert demands["vo2_power"] == 10
        # technicality=5 -> 10
        assert demands["technical"] == 10

    def test_unbound_full_vector(self):
        """Verify every dimension for unbound-200."""
        data = _load_race("unbound-200")
        demands = analyze_race_demands(data)
        assert demands["durability"] == 10
        assert demands["climbing"] == 7
        assert demands["vo2_power"] == 10
        assert demands["threshold"] == 5  # >150mi -> 4, elev=3 >= 3 -> +1 = 5
        assert demands["technical"] == 8  # technicality=4 -> 8
        assert demands["heat_resilience"] == 10
        assert demands["altitude"] == 2  # altitude=1 -> 2
        assert demands["race_specificity"] == 10

    def test_leadville_full_vector(self):
        """Verify every dimension for leadville-100."""
        data = _load_race("leadville-100")
        demands = analyze_race_demands(data)
        assert demands["durability"] == 6
        assert demands["climbing"] == 10
        assert demands["vo2_power"] == 10
        assert demands["threshold"] == 8  # 100mi -> 7, elev=5 >= 3 -> +1 = 8
        assert demands["technical"] == 8  # technicality=4 -> 8
        # climate=4 -> base 6, no heat keywords in challenges -> 6
        assert demands["heat_resilience"] == 6
        assert demands["altitude"] == 10
        assert demands["race_specificity"] == 10

    def test_atlas_full_vector(self):
        """Verify every dimension for atlas-mountain-race."""
        data = _load_race("atlas-mountain-race")
        demands = analyze_race_demands(data)
        assert demands["durability"] == 10
        assert demands["climbing"] == 10
        assert demands["vo2_power"] == 5  # field_depth=2, prestige=3
        assert demands["threshold"] == 5  # >150mi -> 4, elev=5 >= 3 -> +1 = 5
        assert demands["technical"] == 8  # technicality=4 -> 8
        # climate=2 < 4 -> base 0, challenges have 'Extreme heat' -> +1 = 1
        assert demands["heat_resilience"] == 1
        assert demands["altitude"] == 8  # altitude=4 -> 8
        assert demands["race_specificity"] == 9  # tier=2: (5-2)*2+3=9


# ── TestAnalyzeRaceDemandsEdgeCases ───────────────────────────────────


class TestAnalyzeRaceDemandsEdgeCases:
    def test_missing_rider_intel(self):
        """No youtube_data -> heat from climate only."""
        race_data = _make_race(
            rating=_make_rating(climate=4),
            climate={"challenges": []},
        )
        demands = analyze_race_demands(race_data)
        assert demands["heat_resilience"] == 6

    def test_missing_climate(self):
        """No climate block -> heat defaults work (no challenges boost)."""
        race_data = _make_race(rating=_make_rating(climate=4))
        demands = analyze_race_demands(race_data)
        # base=6, no climate block = no challenges boost -> 6
        assert demands["heat_resilience"] == 6

    def test_missing_vitals_fields(self):
        """Graceful with missing vitals fields."""
        race_data = {"race": {"vitals": {}, "gravel_god_rating": {}}}
        demands = analyze_race_demands(race_data)
        # distance=0 -> durability 1
        assert demands["durability"] == 1
        # All scores should be valid
        for dim in DIMENSIONS:
            assert 0 <= demands[dim] <= 10

    def test_all_zeros(self):
        """Minimal race with all zeros -> low scores."""
        race_data = _make_race(
            vitals={"distance_mi": 10, "elevation_ft": 0},
            rating={
                "tier": 4,
                "prestige": 0,
                "field_depth": 0,
                "elevation": 0,
                "altitude": 0,
                "climate": 0,
                "technicality": 0,
                "discipline": "gravel",
            },
        )
        demands = analyze_race_demands(race_data)
        assert demands["durability"] == 1
        assert demands["climbing"] == 0
        assert demands["vo2_power"] == 0
        assert demands["threshold"] == 3
        assert demands["technical"] == 0
        assert demands["heat_resilience"] == 0
        assert demands["altitude"] == 0
        assert demands["race_specificity"] == 2  # (5-4)*2+0 = 2

    def test_all_maxed(self):
        """Maximal race -> high scores."""
        youtube_data = {
            "rider_intel": {"search_text": "extreme heat and humidity throughout"}
        }
        race_data = _make_race(
            vitals={"distance_mi": 300, "elevation_ft": 50000},
            rating={
                "tier": 1,
                "prestige": 5,
                "field_depth": 5,
                "elevation": 5,
                "altitude": 5,
                "climate": 5,
                "technicality": 5,
                "discipline": "bikepacking",
            },
            youtube_data=youtube_data,
            climate={"challenges": ["Extreme heat", "High humidity"]},
        )
        demands = analyze_race_demands(race_data)
        assert demands["durability"] == 10
        assert demands["climbing"] == 10
        assert demands["vo2_power"] == 10
        assert demands["technical"] == 10
        assert demands["heat_resilience"] == 10
        assert demands["altitude"] == 10
        assert demands["race_specificity"] == 10

    def test_return_type(self):
        """All values are ints, all 0-10."""
        race_data = _make_race()
        demands = analyze_race_demands(race_data)
        for dim, value in demands.items():
            assert isinstance(value, int), f"{dim} is {type(value)}, expected int"
            assert 0 <= value <= 10, f"{dim}={value} out of range 0-10"

    def test_empty_race_data(self):
        """Completely empty dict -> graceful defaults."""
        demands = analyze_race_demands({})
        for dim in DIMENSIONS:
            assert isinstance(demands[dim], int)
            assert 0 <= demands[dim] <= 10

    def test_missing_race_key(self):
        """Dict without 'race' key -> all defaults."""
        demands = analyze_race_demands({"something_else": True})
        assert demands["durability"] == 1
        assert demands["vo2_power"] == 0

    def test_none_values_in_rating(self):
        """Rating with None values -> fallback to 0."""
        race_data = _make_race(
            rating={
                "tier": None,
                "prestige": None,
                "field_depth": None,
                "elevation": None,
                "altitude": None,
                "climate": None,
                "technicality": None,
                "discipline": None,
            }
        )
        demands = analyze_race_demands(race_data)
        for dim in DIMENSIONS:
            assert isinstance(demands[dim], int)
            assert 0 <= demands[dim] <= 10


# ── TestDemandVector ──────────────────────────────────────────────────


class TestDemandVector:
    def test_keys_present(self):
        """All 8 dimensions present in output."""
        race_data = _make_race()
        demands = analyze_race_demands(race_data)
        for dim in DIMENSIONS:
            assert dim in demands, f"Missing dimension: {dim}"

    def test_no_extra_keys(self):
        """Exactly 8 keys, no extras."""
        race_data = _make_race()
        demands = analyze_race_demands(race_data)
        assert len(demands) == 8
        assert set(demands.keys()) == set(DIMENSIONS)

    def test_all_values_in_range(self):
        """Every value is an integer 0-10."""
        race_data = _make_race()
        demands = analyze_race_demands(race_data)
        for dim, value in demands.items():
            assert isinstance(value, int), f"{dim}: expected int, got {type(value)}"
            assert 0 <= value <= 10, f"{dim}={value} not in [0, 10]"

    def test_dimensions_constant_matches_output(self):
        """DIMENSIONS list matches the keys returned by analyze_race_demands."""
        race_data = _make_race()
        demands = analyze_race_demands(race_data)
        assert list(demands.keys()) == DIMENSIONS


# ── TestAnalyzeFromFile ───────────────────────────────────────────────


class TestAnalyzeFromFile:
    def test_from_file_matches_direct(self):
        """analyze_race_demands_from_file produces same result as loading + calling."""
        path = os.path.join(RACE_DATA_DIR, "unbound-200.json")
        if not os.path.exists(path):
            pytest.skip("unbound-200.json not found")
        from_file = analyze_race_demands_from_file(path)
        with open(path) as f:
            data = json.load(f)
        direct = analyze_race_demands(data)
        assert from_file == direct

    def test_file_not_found(self):
        """Missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            analyze_race_demands_from_file("/nonexistent/path/fake-race.json")

    def test_from_file_returns_dict(self):
        """Return type is a dict."""
        path = os.path.join(RACE_DATA_DIR, "mid-south.json")
        if not os.path.exists(path):
            pytest.skip("mid-south.json not found")
        result = analyze_race_demands_from_file(path)
        assert isinstance(result, dict)
        assert len(result) == 8
