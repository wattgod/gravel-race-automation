"""Tests for GET /api/season-plan/prefill/{token} — the read-only lookup
that lets /season-plan/ prefill a returning /goals/ lead's saved answers.

Covers: a valid token returns exactly the whitelisted fields, a bad/unknown
token 404s, a malformed token 404s without touching the database, no-store
caching, and rate limiting.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret-123")

from mission_control.routers import season_plan_prefill
from mission_control.routers.season_plan_prefill import router, _rate_buckets

VALID_TOKEN = "a" * 24  # matches _TOKEN_RE (16-64 url-safe chars)


def _fake_row(**source_data_overrides):
    source_data = {
        "poster_token": VALID_TOKEN,
        "goal_answers": {
            "outcome_goal": "Finish Unbound 200 under 14 hours",
            "a_race": "Unbound Gravel 200",
            "a_race_date": "2027-05-31",
            "habit": "Ride to work",
            "habit_when": "Every weekday morning",
        },
        "offer_variant": "C",
        "entry_src": "home",
        "ga4_client_id": "GA1.2.123.456",
    }
    source_data.update(source_data_overrides)
    return {
        "contact_name": "Ada Athlete",
        "contact_email": "ada@example.com",
        "source": "goal_2027",
        "source_data": source_data,
    }


def _mock_db_returning(rows):
    """Build a mock supabase_client whose _table(...).select(...).eq(...)
    .limit(...).execute().data returns `rows`, regardless of filter args —
    the fake in-memory db (conftest.py) doesn't support the source_data
    ->>'poster_token' JSON-path filter this route (and poster.py) use, so
    this route is tested against a mock at the query-result boundary."""
    chain = MagicMock()
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.limit.return_value = chain
    chain.execute.return_value = MagicMock(data=rows)
    mock_db = MagicMock()
    mock_db._table.return_value = chain
    return mock_db


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        _rate_buckets.clear()
        yield c


class TestValidToken:
    def test_returns_only_whitelisted_fields(self, client, monkeypatch):
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([_fake_row()]))
        resp = client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        assert resp.status_code == 200
        body = resp.json()
        assert body == {
            "name": "Ada Athlete",
            "email": "ada@example.com",
            "goal": "Finish Unbound 200 under 14 hours",
            "a_race_name": "Unbound Gravel 200",
            "a_race_date": "2027-05-31",
            "habits": "Ride to work, Every weekday morning",
        }
        # Nothing else in source_data leaks through.
        assert "offer_variant" not in body
        assert "entry_src" not in body
        assert "ga4_client_id" not in body
        assert "poster_token" not in body

    def test_no_store_cache_header(self, client, monkeypatch):
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([_fake_row()]))
        resp = client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        assert resp.headers.get("cache-control") == "no-store"

    def test_missing_answers_return_empty_strings_not_an_error(self, client, monkeypatch):
        row = _fake_row(goal_answers={})
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([row]))
        resp = client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["goal"] == ""
        assert body["a_race_name"] == ""
        assert body["habits"] == ""

    def test_cors_header_set_for_allowed_origin(self, client, monkeypatch):
        """sol review (BLOCKER #4): the browser calls this route
        cross-origin from gravelgodcycling.com; Mission Control has no
        blanket CORS middleware, so without an explicit
        Access-Control-Allow-Origin here the fetch response body is
        unreadable by the page's own JS."""
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([_fake_row()]))
        resp = client.get(
            f"/api/season-plan/prefill/{VALID_TOKEN}",
            headers={"Origin": "https://gravelgodcycling.com"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "https://gravelgodcycling.com"

    def test_cors_header_absent_for_unrecognized_origin(self, client, monkeypatch):
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([_fake_row()]))
        resp = client.get(
            f"/api/season-plan/prefill/{VALID_TOKEN}",
            headers={"Origin": "https://evil.example.com"},
        )
        assert "access-control-allow-origin" not in {k.lower() for k in resp.headers}

    def test_404_response_also_carries_no_store(self, client, monkeypatch):
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([]))
        resp = client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        assert resp.status_code == 404
        assert resp.headers.get("cache-control") == "no-store"


class TestBadOrUnknownToken:
    def test_unknown_token_is_404(self, client, monkeypatch):
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([]))
        resp = client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        assert resp.status_code == 404

    def test_malformed_token_is_404_without_a_db_lookup(self, client, monkeypatch):
        mock_db = _mock_db_returning([_fake_row()])
        monkeypatch.setattr(season_plan_prefill, "db", mock_db)
        resp = client.get("/api/season-plan/prefill/short")
        assert resp.status_code == 404
        mock_db._table.assert_not_called()

    def test_athlete_review_token_is_rejected(self, client, monkeypatch):
        """sol review (BLOCKER #5): webhooks.py mints the same kind of
        poster_token for athlete_review (a coached athlete's private
        season close-out) as it does for goal_2027. That token must never
        unlock this route — only a genuine goal_2027 lead's token may."""
        row = _fake_row()
        row["source"] = "athlete_review"
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([row]))
        resp = client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        assert resp.status_code == 404

    def test_db_lookup_failure_is_404_not_500(self, client, monkeypatch):
        mock_db = MagicMock()
        mock_db._table.side_effect = RuntimeError("supabase unreachable")
        monkeypatch.setattr(season_plan_prefill, "db", mock_db)
        resp = client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        assert resp.status_code == 404


class TestRateLimit:
    def test_429_after_limit(self, client, monkeypatch):
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([]))
        for _ in range(season_plan_prefill._RATE_LIMIT):
            client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        resp = client.get(f"/api/season-plan/prefill/{VALID_TOKEN}")
        assert resp.status_code == 429

    def test_429_still_carries_cors_and_no_store(self, client, monkeypatch):
        """sol review round 2 NIT: a 429 used to have neither header,
        contradicting the "every response" claim."""
        monkeypatch.setattr(season_plan_prefill, "db", _mock_db_returning([]))
        for _ in range(season_plan_prefill._RATE_LIMIT):
            client.get(f"/api/season-plan/prefill/{VALID_TOKEN}",
                      headers={"Origin": "https://gravelgodcycling.com"})
        resp = client.get(
            f"/api/season-plan/prefill/{VALID_TOKEN}",
            headers={"Origin": "https://gravelgodcycling.com"})
        assert resp.status_code == 429
        assert resp.headers.get("access-control-allow-origin") == "https://gravelgodcycling.com"
        assert resp.headers.get("cache-control") == "no-store"
