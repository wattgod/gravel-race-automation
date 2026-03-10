"""Tests for the Nutrition API endpoint — POST /api/v1/nutrition/fueling.

Covers:
- Happy path: valid request, correct calculation
- Zero/negative distance: validation error (422)
- Zero/negative weight: validation error (422)
- Boundary values: very short and very long races
- Duration estimation: distance-only vs explicit duration
- Weight-derived targets: present when weight given
- Rate limiting: 429 after threshold
- Extreme distance: capped at 1000
- Missing required fields: 422
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Env vars
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret-123")

from mission_control.routers.nutrition_api import router as nutrition_router, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """Minimal FastAPI test client with only the nutrition router."""
    app = FastAPI()
    app.include_router(nutrition_router)

    with TestClient(app) as c:
        _rate_buckets.clear()
        yield c


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestNutritionHappyPath:
    def test_basic_100mi_request(self, client):
        """100 miles with no duration -> estimated ~8.3hr -> 60-80g/hr bracket."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["distance_mi"] == 100
        assert data["hours"] > 0
        assert data["carb_rate_lo"] > 0
        assert data["carb_rate_hi"] > data["carb_rate_lo"]
        assert data["label"]

    def test_explicit_duration(self, client):
        """Explicit duration_hours overrides distance-based estimation."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "duration_hours": 3.0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hours"] == 3.0
        # 3 hours -> 0-4hr bracket -> 80-100g/hr
        assert data["carb_rate_lo"] == 80
        assert data["carb_rate_hi"] == 100

    def test_with_weight(self, client):
        """Weight enables daily carb loading targets."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "duration_hours": 8.0,
            "weight_lbs": 170,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight_lbs"] == 170
        assert data["weight_kg"] is not None
        assert data["daily_carb_lo"] is not None
        assert data["daily_carb_hi"] is not None
        assert data["long_ride_carb_lo"] is not None
        assert data["long_ride_carb_hi"] is not None
        # Weight kg should be roughly 170 / 2.205 = 77.1
        assert 76 < data["weight_kg"] < 78

    def test_duration_estimate_string(self, client):
        """Duration estimate string parses correctly."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "duration_estimate": "6-10 hours",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hours"] == 8.0  # avg of 6 and 10

    def test_total_carbs_consistent(self, client):
        """Total carbs = hours * rate (within rounding)."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "duration_hours": 6.0,
        })
        data = resp.json()
        expected_lo = int(data["hours"] * data["carb_rate_lo"])
        expected_hi = int(data["hours"] * data["carb_rate_hi"])
        assert abs(data["carbs_total_lo"] - expected_lo) <= 1
        assert abs(data["carbs_total_hi"] - expected_hi) <= 1

    def test_gels_consistent(self, client):
        """Gels = total_carbs // 25."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
        })
        data = resp.json()
        assert data["gels_lo"] == data["carbs_total_lo"] // 25
        assert data["gels_hi"] == data["carbs_total_hi"] // 25


# ---------------------------------------------------------------------------
# Input validation — distance
# ---------------------------------------------------------------------------

class TestDistanceValidation:
    def test_zero_distance_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 0,
        })
        assert resp.status_code == 422

    def test_negative_distance_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": -50,
        })
        assert resp.status_code == 422

    def test_extreme_distance_rejected(self, client):
        """Distances over 1000 miles are rejected at the API layer."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 10001,
        })
        assert resp.status_code == 422

    def test_max_allowed_distance(self, client):
        """1000 miles is the max allowed."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 1000,
        })
        assert resp.status_code == 200

    def test_missing_distance_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Input validation — weight
# ---------------------------------------------------------------------------

class TestWeightValidation:
    def test_zero_weight_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "weight_lbs": 0,
        })
        assert resp.status_code == 422

    def test_negative_weight_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "weight_lbs": -150,
        })
        assert resp.status_code == 422

    def test_extreme_weight_rejected(self, client):
        """Weight over 500 lbs is rejected."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "weight_lbs": 501,
        })
        assert resp.status_code == 422

    def test_null_weight_ok(self, client):
        """Weight is optional — null is fine."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "weight_lbs": None,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["weight_kg"] is None


# ---------------------------------------------------------------------------
# Input validation — duration
# ---------------------------------------------------------------------------

class TestDurationValidation:
    def test_zero_duration_estimates_from_distance(self, client):
        """duration_hours=0 means 'estimate from distance'."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "duration_hours": 0,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hours"] > 0

    def test_negative_duration_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "duration_hours": -5,
        })
        assert resp.status_code == 422

    def test_extreme_duration_rejected(self, client):
        """Duration over 168 hours (1 week) is rejected."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100,
            "duration_hours": 169,
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Boundary values — race lengths
# ---------------------------------------------------------------------------

class TestBoundaryRaceLengths:
    def test_1_mile_race(self, client):
        """Very short race — should still return valid fueling."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 1,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["hours"] > 0
        assert data["carb_rate_lo"] >= 30

    def test_very_long_race_500mi(self, client):
        """Ultra-endurance — carb rates should be at survival levels."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 500,
        })
        assert resp.status_code == 200
        data = resp.json()
        # 500 miles at 10mph = 50 hours -> 16+hr bracket -> 30-50g/hr
        assert data["carb_rate_lo"] == 30
        assert data["carb_rate_hi"] == 50

    def test_50_mile_race(self, client):
        """Short endurance — high carb rate bracket."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 50,
        })
        assert resp.status_code == 200
        data = resp.json()
        # 50mi / 14mph = 3.6hr -> 0-4hr bracket -> 80-100g/hr
        assert data["carb_rate_lo"] == 80
        assert data["carb_rate_hi"] == 100


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestNutritionRateLimit:
    def test_rate_limit_enforced(self, client):
        """Exceeding 60 requests/min returns 429."""
        _rate_buckets.clear()

        for i in range(60):
            resp = client.post("/api/v1/nutrition/fueling", json={"distance_mi": 100})
            assert resp.status_code == 200, f"Request {i+1} failed with {resp.status_code}"

        # 61st should be rate limited
        resp = client.post("/api/v1/nutrition/fueling", json={"distance_mi": 100})
        assert resp.status_code == 429
        assert "rate limit" in resp.json()["detail"].lower()

    def test_rate_limit_returns_429_detail(self, client):
        """429 response includes clear detail message."""
        _rate_buckets.clear()

        # Fill the bucket
        for _ in range(60):
            client.post("/api/v1/nutrition/fueling", json={"distance_mi": 50})

        resp = client.post("/api/v1/nutrition/fueling", json={"distance_mi": 50})
        assert resp.status_code == 429
        assert resp.json()["detail"] == "Rate limit exceeded"


# ---------------------------------------------------------------------------
# Missing/malformed fields
# ---------------------------------------------------------------------------

class TestMalformedInput:
    def test_string_distance_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": "fifty",
        })
        assert resp.status_code == 422

    def test_float_distance_rejected(self, client):
        """Float distance is rejected — field expects int."""
        resp = client.post("/api/v1/nutrition/fueling", json={
            "distance_mi": 100.5,
        })
        assert resp.status_code == 422

    def test_empty_body_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling", json={})
        assert resp.status_code == 422

    def test_no_body_rejected(self, client):
        resp = client.post("/api/v1/nutrition/fueling")
        assert resp.status_code == 422
