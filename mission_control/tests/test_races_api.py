"""Tests for the Races API endpoints.

Uses a minimal FastAPI app with only the races_api router to avoid
importing the full Mission Control stack (supabase, apscheduler, etc.)
which may not be installed in local dev environments.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Env vars (not needed for races API, but prevent import-time errors if
# anything transitively reads config)
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret-123")

from mission_control.services.race_data import RaceDB
from mission_control.routers.races_api import router as races_router

# ---------------------------------------------------------------------------
# Sample race data for tests
# ---------------------------------------------------------------------------

SAMPLE_INDEX = [
    {
        "name": "Unbound 200",
        "slug": "unbound-200",
        "location": "Emporia, Kansas",
        "region": "Midwest",
        "month": "June",
        "distance_mi": 200,
        "elevation_ft": 11000,
        "tier": 1,
        "overall_score": 80,
        "scores": {"prestige": 5, "length": 5, "technicality": 3, "elevation": 3},
        "tagline": "The Super Bowl of gravel.",
        "has_profile": True,
        "profile_url": "/race/unbound-200/",
        "discipline": "gravel",
        "lat": 38.404,
        "lng": -96.18,
    },
    {
        "name": "SBT GRVL",
        "slug": "steamboat-gravel",
        "location": "Steamboat Springs, Colorado",
        "region": "West",
        "month": "August",
        "distance_mi": 141,
        "elevation_ft": 9500,
        "tier": 1,
        "overall_score": 79,
        "scores": {"prestige": 4, "length": 4, "technicality": 3, "elevation": 4},
        "tagline": "Craft gravel in the Colorado Rockies.",
        "has_profile": True,
        "profile_url": "/race/steamboat-gravel/",
        "discipline": "gravel",
        "lat": 40.485,
        "lng": -106.83,
    },
    {
        "name": "Leadville 100",
        "slug": "leadville-100",
        "location": "Leadville, Colorado",
        "region": "West",
        "month": "August",
        "distance_mi": 100,
        "elevation_ft": 12000,
        "tier": 1,
        "overall_score": 84,
        "scores": {"prestige": 5, "length": 4, "technicality": 4, "elevation": 5},
        "tagline": "The race across the sky.",
        "has_profile": True,
        "profile_url": "/race/leadville-100/",
        "discipline": "mtb",
        "lat": 39.243,
        "lng": -106.293,
    },
    {
        "name": "Small Town Gravel",
        "slug": "small-town-gravel",
        "location": "Small Town, Iowa",
        "region": "Midwest",
        "month": "May",
        "distance_mi": 50,
        "elevation_ft": 2000,
        "tier": 4,
        "overall_score": 35,
        "scores": {"prestige": 1, "length": 2, "technicality": 1, "elevation": 1},
        "tagline": "A friendly small town ride.",
        "has_profile": True,
        "profile_url": "/race/small-town-gravel/",
        "discipline": "gravel",
        "lat": 41.5,
        "lng": -93.0,
    },
]

SAMPLE_PROFILE_UNBOUND = {
    "race": {
        "name": "Unbound 200",
        "slug": "unbound-200",
        "tagline": "The Super Bowl of gravel.",
        "vitals": {
            "distance_mi": 200,
            "elevation_ft": 11000,
            "location": "Emporia, Kansas",
            "date": "Early June annually",
            "date_specific": "2026: June 6",
            "region": "Midwest",
            "month": "June",
        },
        "gravel_god_rating": {
            "overall_score": 80,
            "tier": 1,
            "discipline": "gravel",
            "prestige": 5,
            "length": 5,
            "technicality": 3,
            "elevation": 3,
            "climate": 5,
            "altitude": 1,
            "adventure": 5,
            "race_quality": 5,
            "experience": 5,
            "community": 5,
            "field_depth": 5,
            "value": 3,
            "expenses": 2,
        },
        "course_description": {
            "character": "Relentless rollers through Flint Hills limestone.",
        },
        "terrain": {
            "primary": "Rolling gravel",
            "surface": "Chunky limestone",
        },
        "non_negotiables": [
            "Heat adaptation training",
            "Tire durability testing",
        ],
        "final_verdict": {
            "one_liner": "The race that defines gravel.",
        },
        "citations": [
            {"url": "https://example.com/unbound", "title": "Unbound Gravel"},
        ],
    }
}

SAMPLE_PROFILE_SBT = {
    "race": {
        "name": "SBT GRVL",
        "slug": "steamboat-gravel",
        "tagline": "Craft gravel in the Colorado Rockies.",
        "vitals": {
            "distance_mi": 141,
            "elevation_ft": 9500,
            "location": "Steamboat Springs, Colorado",
            "date": "August annually",
            "region": "West",
            "month": "August",
        },
        "gravel_god_rating": {
            "overall_score": 79,
            "tier": 1,
            "discipline": "gravel",
            "prestige": 4,
            "length": 4,
            "technicality": 3,
            "elevation": 4,
        },
        "course_description": {"character": "Mountain gravel at altitude."},
        "non_negotiables": ["Altitude acclimatization"],
    }
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def race_db():
    """Create a RaceDB preloaded with sample data (no disk I/O)."""
    db = RaceDB()
    db._index = list(SAMPLE_INDEX)
    db._profiles = {
        "unbound-200": SAMPLE_PROFILE_UNBOUND,
        "steamboat-gravel": SAMPLE_PROFILE_SBT,
        "leadville-100": {"race": SAMPLE_INDEX[2]},
        "small-town-gravel": {"race": SAMPLE_INDEX[3]},
    }
    db._loaded = True
    return db


@pytest.fixture
def client(race_db):
    """Minimal FastAPI TestClient with only the races API router."""
    app = FastAPI(
        title="Test Races API",
        docs_url="/api/v1/docs",
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    app.include_router(races_router)

    with patch("mission_control.routers.races_api.get_race_db", return_value=race_db):
        with TestClient(app) as c:
            # Clear rate limit buckets between tests
            from mission_control.routers.races_api import _rate_buckets
            _rate_buckets.clear()
            yield c


# ---------------------------------------------------------------------------
# GET /api/v1/races — list, filter, search, sort, paginate
# ---------------------------------------------------------------------------

class TestListRaces:
    def test_list_all(self, client):
        resp = client.get("/api/v1/races")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 4
        assert len(data["results"]) == 4

    def test_default_sort_by_score(self, client):
        resp = client.get("/api/v1/races")
        data = resp.json()
        scores = [r["overall_score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_sort_by_name(self, client):
        resp = client.get("/api/v1/races?sort=name")
        data = resp.json()
        names = [r["name"] for r in data["results"]]
        assert names == sorted(names, key=str.lower)

    def test_sort_by_distance(self, client):
        resp = client.get("/api/v1/races?sort=distance")
        data = resp.json()
        distances = [r["distance_mi"] for r in data["results"]]
        assert distances == sorted(distances, reverse=True)

    def test_filter_by_tier(self, client):
        resp = client.get("/api/v1/races?tier=1")
        data = resp.json()
        assert data["count"] == 3
        assert all(r["tier"] == 1 for r in data["results"])

    def test_filter_by_multiple_tiers(self, client):
        resp = client.get("/api/v1/races?tier=1&tier=4")
        data = resp.json()
        assert data["count"] == 4

    def test_filter_by_region(self, client):
        resp = client.get("/api/v1/races?region=Midwest")
        data = resp.json()
        assert data["count"] == 2
        assert all("Midwest" == r["region"] for r in data["results"])

    def test_filter_by_region_case_insensitive(self, client):
        resp = client.get("/api/v1/races?region=midwest")
        data = resp.json()
        assert data["count"] == 2

    def test_filter_by_discipline(self, client):
        resp = client.get("/api/v1/races?discipline=mtb")
        data = resp.json()
        assert data["count"] == 1
        assert data["results"][0]["slug"] == "leadville-100"

    def test_filter_by_month(self, client):
        resp = client.get("/api/v1/races?month=August")
        data = resp.json()
        assert data["count"] == 2

    def test_filter_by_distance_range(self, client):
        resp = client.get("/api/v1/races?distance_min=100&distance_max=200")
        data = resp.json()
        assert data["count"] == 3
        for r in data["results"]:
            assert 100 <= r["distance_mi"] <= 200

    def test_text_search(self, client):
        resp = client.get("/api/v1/races?q=super+bowl")
        data = resp.json()
        assert data["count"] == 1
        assert data["results"][0]["slug"] == "unbound-200"

    def test_text_search_by_location(self, client):
        resp = client.get("/api/v1/races?q=colorado")
        data = resp.json()
        assert data["count"] == 2

    def test_pagination(self, client):
        resp = client.get("/api/v1/races?limit=2&offset=0")
        data = resp.json()
        assert data["count"] == 4
        assert len(data["results"]) == 2
        assert data["next"] == "/api/v1/races?offset=2&limit=2"

    def test_pagination_last_page(self, client):
        resp = client.get("/api/v1/races?limit=2&offset=2")
        data = resp.json()
        assert len(data["results"]) == 2
        assert data["next"] is None

    def test_combined_filters(self, client):
        resp = client.get("/api/v1/races?tier=1&region=West&month=August")
        data = resp.json()
        assert data["count"] == 2

    def test_empty_result(self, client):
        resp = client.get("/api/v1/races?tier=3")
        data = resp.json()
        assert data["count"] == 0
        assert data["results"] == []


# ---------------------------------------------------------------------------
# GET /api/v1/races/recommend
# ---------------------------------------------------------------------------

class TestRecommend:
    def test_basic_recommend(self, client):
        resp = client.get("/api/v1/races/recommend")
        data = resp.json()
        assert data["count"] == 4
        # Should be sorted by score descending
        scores = [r["overall_score"] for r in data["results"]]
        assert scores == sorted(scores, reverse=True)

    def test_recommend_with_filters(self, client):
        resp = client.get("/api/v1/races/recommend?tier=1&distance_min=100")
        data = resp.json()
        assert data["count"] == 3
        assert all(r["tier"] == 1 for r in data["results"])

    def test_recommend_limit(self, client):
        resp = client.get("/api/v1/races/recommend?limit=2")
        data = resp.json()
        assert data["count"] == 2

    def test_recommend_by_month(self, client):
        resp = client.get("/api/v1/races/recommend?month=June")
        data = resp.json()
        assert data["count"] == 1
        assert data["results"][0]["slug"] == "unbound-200"


# ---------------------------------------------------------------------------
# GET /api/v1/races/{slug}
# ---------------------------------------------------------------------------

class TestGetRace:
    def test_get_existing_race(self, client):
        resp = client.get("/api/v1/races/unbound-200")
        assert resp.status_code == 200
        data = resp.json()
        assert data["race"]["name"] == "Unbound 200"
        assert data["race"]["slug"] == "unbound-200"

    def test_get_race_full_profile(self, client):
        resp = client.get("/api/v1/races/unbound-200")
        data = resp.json()
        race = data["race"]
        assert "vitals" in race
        assert "gravel_god_rating" in race
        assert "non_negotiables" in race
        assert "citations" in race

    def test_404_for_missing_race(self, client):
        resp = client.get("/api/v1/races/nonexistent-race-xyz")
        assert resp.status_code == 404

    def test_fuzzy_alias_dirty_kanza(self, client):
        resp = client.get("/api/v1/races/dirty-kanza")
        assert resp.status_code == 200
        data = resp.json()
        assert data["_canonical_slug"] == "unbound-200"
        assert data["_resolved_from"] == "dirty-kanza"

    def test_fuzzy_alias_sbt_grvl(self, client):
        resp = client.get("/api/v1/races/sbt-grvl")
        assert resp.status_code == 200
        data = resp.json()
        assert data["_canonical_slug"] == "steamboat-gravel"

    def test_fuzzy_alias_leadville(self, client):
        resp = client.get("/api/v1/races/leadville")
        assert resp.status_code == 200
        data = resp.json()
        assert data["_canonical_slug"] == "leadville-100"

    def test_direct_slug_no_resolved_field(self, client):
        resp = client.get("/api/v1/races/unbound-200")
        data = resp.json()
        assert "_resolved_from" not in data
        assert "_canonical_slug" not in data


# ---------------------------------------------------------------------------
# GET /api/v1/races/{slug}/training
# ---------------------------------------------------------------------------

class TestTrainingContext:
    def test_training_context(self, client):
        resp = client.get("/api/v1/races/unbound-200/training")
        assert resp.status_code == 200
        data = resp.json()
        assert data["race_slug"] == "unbound-200"
        assert data["race_name"] == "Unbound 200"
        assert data["distance_mi"] == 200
        assert data["elevation_ft"] == 11000
        assert data["tier"] == 1
        assert isinstance(data["strength_emphasis"], list)
        assert isinstance(data["fueling_target"], str)
        assert isinstance(data["non_negotiables"], list)

    def test_training_context_fueling(self, client):
        resp = client.get("/api/v1/races/unbound-200/training")
        data = resp.json()
        # 200 miles -> highest fueling bracket
        assert "300-400" in data["fueling_target"]

    def test_training_context_non_negotiables(self, client):
        resp = client.get("/api/v1/races/unbound-200/training")
        data = resp.json()
        assert "Heat adaptation training" in data["non_negotiables"]

    def test_training_context_404(self, client):
        resp = client.get("/api/v1/races/nonexistent-race/training")
        assert resp.status_code == 404

    def test_training_context_alias(self, client):
        resp = client.get("/api/v1/races/dirty-kanza/training")
        assert resp.status_code == 200
        data = resp.json()
        assert data["race_slug"] == "unbound-200"

    def test_training_context_profile_url(self, client):
        resp = client.get("/api/v1/races/unbound-200/training")
        data = resp.json()
        assert data["profile_url"] == "https://gravelgodcycling.com/race/unbound-200/"


# ---------------------------------------------------------------------------
# GET /.well-known/ai-plugin.json
# ---------------------------------------------------------------------------

class TestAIPlugin:
    def test_ai_plugin_manifest(self, client):
        resp = client.get("/.well-known/ai-plugin.json")
        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "v1"
        assert data["name_for_model"] == "gravel_god_races"
        assert data["auth"]["type"] == "none"
        assert "openapi.json" in data["api"]["url"]

    def test_ai_plugin_description(self, client):
        resp = client.get("/.well-known/ai-plugin.json")
        data = resp.json()
        assert "328" in data["description_for_model"]
        assert "/api/v1/races" in data["description_for_model"]


# ---------------------------------------------------------------------------
# OpenAPI docs
# ---------------------------------------------------------------------------

class TestOpenAPIDocs:
    def test_openapi_json_accessible(self, client):
        resp = client.get("/api/v1/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "paths" in data
        assert "/api/v1/races" in data["paths"]

    def test_openapi_has_race_endpoints(self, client):
        resp = client.get("/api/v1/openapi.json")
        data = resp.json()
        paths = list(data["paths"].keys())
        assert "/api/v1/races" in paths
        assert "/api/v1/races/recommend" in paths
        assert "/api/v1/races/{slug}" in paths
        assert "/api/v1/races/{slug}/training" in paths

    def test_swagger_ui_accessible(self, client):
        resp = client.get("/api/v1/docs")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_list_rate_limit(self, client):
        """Verify 429 after exceeding list rate limit."""
        from mission_control.routers.races_api import _rate_buckets
        _rate_buckets.clear()

        # Send 60 requests (at the limit)
        for _ in range(60):
            resp = client.get("/api/v1/races")
            assert resp.status_code == 200

        # 61st should be rate-limited
        resp = client.get("/api/v1/races")
        assert resp.status_code == 429

    def test_detail_rate_limit_higher(self, client):
        """Detail endpoints have a higher limit (120/min)."""
        from mission_control.routers.races_api import _rate_buckets
        _rate_buckets.clear()

        # Send 61 requests — should all pass (detail limit is 120)
        for _ in range(61):
            resp = client.get("/api/v1/races/unbound-200")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# RaceDB service unit tests
# ---------------------------------------------------------------------------

class TestRaceDBService:
    def test_resolve_slug_exact(self, race_db):
        assert race_db.resolve_slug("unbound-200") == "unbound-200"

    def test_resolve_slug_alias(self, race_db):
        assert race_db.resolve_slug("dirty-kanza") == "unbound-200"

    def test_resolve_slug_normalized(self, race_db):
        assert race_db.resolve_slug("Unbound_200") == "unbound-200"

    def test_resolve_slug_none(self, race_db):
        assert race_db.resolve_slug("totally-fake-race") is None

    def test_get_profile_exact(self, race_db):
        p = race_db.get_profile("unbound-200")
        assert p is not None
        assert p["race"]["name"] == "Unbound 200"

    def test_get_profile_alias(self, race_db):
        p = race_db.get_profile("dirty-kanza")
        assert p is not None
        assert p["race"]["slug"] == "unbound-200"

    def test_training_context(self, race_db):
        ctx = race_db.training_context("unbound-200")
        assert ctx is not None
        assert ctx["distance_mi"] == 200
        assert ctx["tier"] == 1

    def test_training_context_missing(self, race_db):
        assert race_db.training_context("nonexistent") is None

    def test_index_property(self, race_db):
        assert len(race_db.index) == 4

    def test_load_idempotent(self, race_db):
        """Calling load() again should be a no-op."""
        race_db.load()
        assert len(race_db.index) == 4
