"""Tests for Athlete OS race lookup module."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from race_lookup import Race, RaceLookup


@pytest.fixture
def db():
    """Load the race database."""
    return RaceLookup()


# ── Basic loading ──


def test_loads_races(db):
    """Verify database loads with expected number of races."""
    assert len(db) >= 300  # Should be ~328


def test_all_races_list(db):
    """Verify all_races returns a list of Race objects."""
    races = db.all_races()
    assert isinstance(races, list)
    assert all(isinstance(r, Race) for r in races[:5])


# ── Exact lookup ──


def test_lookup_exact_slug(db):
    """Verify exact slug lookup works."""
    race = db.lookup("unbound-200")
    assert race is not None
    assert race.slug == "unbound-200"
    assert "Unbound" in race.name


def test_lookup_tier(db):
    """Verify tier is populated."""
    race = db.lookup("unbound-200")
    assert race.tier == 1


def test_lookup_score(db):
    """Verify score is populated."""
    race = db.lookup("unbound-200")
    assert race.score >= 80


def test_lookup_distance(db):
    """Verify distance is populated."""
    race = db.lookup("unbound-200")
    assert race.distance_mi > 0


def test_lookup_profile_url(db):
    """Verify profile URL is correct."""
    race = db.lookup("unbound-200")
    assert race.profile_url == "https://gravelgodcycling.com/race/unbound-200/"


def test_lookup_nonexistent(db):
    """Verify nonexistent slug returns None."""
    assert db.lookup("nonexistent-race-12345") is None


# ── Fuzzy matching ──


def test_lookup_underscore(db):
    """Verify underscore-to-hyphen normalization."""
    race = db.lookup("mid_south")
    assert race is not None
    assert race.slug == "mid-south"


def test_lookup_alias_dirty_kanza(db):
    """Verify alias for Dirty Kanza → Unbound."""
    race = db.lookup("dirty-kanza")
    assert race is not None
    assert race.slug == "unbound-200"


def test_lookup_alias_sbt(db):
    """Verify alias for SBT GRVL."""
    race = db.lookup("sbt-grvl")
    assert race is not None
    assert race.slug == "steamboat-gravel"


def test_lookup_alias_bwr(db):
    """Verify alias for BWR."""
    race = db.lookup("bwr")
    assert race is not None
    assert race.slug == "bwr-california"


# ── Training context ──


def test_training_context_keys(db):
    """Verify training_context returns expected keys."""
    race = db.lookup("unbound-200")
    ctx = race.training_context()
    expected_keys = [
        "race_slug", "race_name", "tier", "score",
        "distance_mi", "elevation_ft", "discipline",
        "terrain_notes", "strength_emphasis", "fueling_target",
        "non_negotiables", "date", "location", "profile_url",
    ]
    for key in expected_keys:
        assert key in ctx, f"Missing key: {key}"


def test_training_context_emphasis(db):
    """Verify strength emphasis is a list."""
    race = db.lookup("unbound-200")
    ctx = race.training_context()
    assert isinstance(ctx["strength_emphasis"], list)
    assert len(ctx["strength_emphasis"]) > 0


def test_training_context_fueling(db):
    """Verify fueling target for long race."""
    race = db.lookup("unbound-200")
    ctx = race.training_context()
    assert "cal/hr" in ctx["fueling_target"]


# ── Recommendations ──


def test_recommend_by_tier(db):
    """Verify tier filtering works."""
    results = db.recommend(tier=[1])
    assert len(results) > 0
    assert all(r.tier == 1 for r in results)


def test_recommend_by_distance(db):
    """Verify distance range filtering."""
    results = db.recommend(distance_range=(80, 150))
    assert len(results) > 0
    for r in results:
        assert 80 <= r.distance_mi <= 150


def test_recommend_sorted_by_score(db):
    """Verify results are sorted by score descending."""
    results = db.recommend(tier=[1, 2])
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_recommend_limit(db):
    """Verify limit works."""
    results = db.recommend(limit=5)
    assert len(results) <= 5


def test_recommend_combined(db):
    """Verify combined filters."""
    results = db.recommend(tier=[1, 2], distance_range=(100, 300))
    for r in results:
        assert r.tier in [1, 2]
        assert 100 <= r.distance_mi <= 300


# ── Race dataclass ──


def test_race_repr():
    """Verify Race repr doesn't include _raw."""
    race = Race(slug="test", name="Test Race")
    r = repr(race)
    assert "_raw" not in r
    assert "test" in r
