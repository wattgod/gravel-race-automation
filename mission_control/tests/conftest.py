"""Shared fixtures for Mission Control tests.

Provides:
- mock_db: patches supabase_client with an in-memory fake
- test_client: async httpx client wired to the FastAPI app
- sample data factories for athletes, deals, enrollments
"""

import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

# Set env vars before any MC imports
os.environ.setdefault("SUPABASE_URL", "https://fake.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "fake-key")
os.environ.setdefault("WEBHOOK_SECRET", "test-secret-123")
os.environ.setdefault("RESEND_API_KEY", "")


# ---------------------------------------------------------------------------
# In-memory fake Supabase
# ---------------------------------------------------------------------------

class FakeQueryResult:
    def __init__(self, data=None, count=None):
        self.data = data or []
        self.count = count


class FakeQueryBuilder:
    """Mimics the supabase-py query builder chain."""

    def __init__(self, store, table_name):
        self._store = store
        self._table = table_name
        self._filters = []
        self._order_col = None
        self._order_desc = False
        self._limit_val = None
        self._range_start = None
        self._range_end = None
        self._columns = "*"
        self._count_mode = None
        self._upsert_data = None
        self._upsert_conflict = None
        self._update_data = None
        self._delete_mode = False
        self._insert_data = None

    def select(self, columns="*", count=None):
        self._columns = columns
        self._count_mode = count
        return self

    def insert(self, data):
        self._insert_data = data
        return self

    def upsert(self, data, on_conflict=None):
        self._upsert_data = data
        self._upsert_conflict = on_conflict
        return self

    def update(self, data):
        self._update_data = data
        return self

    def delete(self):
        self._delete_mode = True
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def neq(self, col, val):
        self._filters.append(("neq", col, val))
        return self

    def gte(self, col, val):
        self._filters.append(("gte", col, val))
        return self

    def lte(self, col, val):
        self._filters.append(("lte", col, val))
        return self

    def lt(self, col, val):
        self._filters.append(("lt", col, val))
        return self

    def or_(self, expr):
        # Simplified: don't filter, return all (search tests handle this separately)
        return self

    def order(self, col, desc=False):
        self._order_col = col
        self._order_desc = desc
        return self

    def limit(self, n):
        self._limit_val = n
        return self

    def range(self, start, end):
        self._range_start = start
        self._range_end = end
        return self

    def _match(self, row):
        for op, col, val in self._filters:
            row_val = row.get(col)
            if op == "eq" and row_val != val:
                return False
            if op == "neq" and row_val == val:
                return False
            if op == "gte" and (row_val is None or str(row_val) < str(val)):
                return False
            if op == "lte" and (row_val is None or str(row_val) > str(val)):
                return False
            if op == "lt" and (row_val is None or str(row_val) >= str(val)):
                return False
        return True

    def execute(self):
        table = self._store[self._table]

        if self._insert_data is not None:
            row = dict(self._insert_data)
            if "id" not in row:
                row["id"] = str(uuid.uuid4())
            table.append(row)
            return FakeQueryResult(data=[row])

        if self._upsert_data is not None:
            row = dict(self._upsert_data)
            if "id" not in row:
                row["id"] = str(uuid.uuid4())
            if self._upsert_conflict:
                conflict_cols = [c.strip() for c in self._upsert_conflict.split(",")]
                existing_idx = None
                for i, existing in enumerate(table):
                    if all(existing.get(c) == row.get(c) for c in conflict_cols):
                        existing_idx = i
                        break
                if existing_idx is not None:
                    table[existing_idx].update(row)
                    return FakeQueryResult(data=[table[existing_idx]])
            table.append(row)
            return FakeQueryResult(data=[row])

        if self._update_data is not None:
            updated = []
            for row in table:
                if self._match(row):
                    row.update(self._update_data)
                    updated.append(row)
            return FakeQueryResult(data=updated)

        if self._delete_mode:
            before = len(table)
            remaining = [r for r in table if not self._match(r)]
            removed = [r for r in table if self._match(r)]
            table.clear()
            table.extend(remaining)
            return FakeQueryResult(data=removed)

        # SELECT
        rows = [r for r in table if self._match(r)]

        if self._order_col:
            rows.sort(
                key=lambda r: r.get(self._order_col, ""),
                reverse=self._order_desc,
            )

        total = len(rows)

        if self._range_start is not None:
            rows = rows[self._range_start:self._range_end + 1]
        elif self._limit_val is not None:
            rows = rows[:self._limit_val]

        return FakeQueryResult(
            data=rows,
            count=total if self._count_mode else None,
        )


class FakeDB:
    """In-memory store keyed by table name."""

    def __init__(self):
        self.store = defaultdict(list)

    def table(self, name):
        return FakeQueryBuilder(self.store, name)

    def clear(self):
        self.store.clear()


@pytest.fixture
def fake_db():
    """Provides a clean in-memory DB and patches supabase_client._table."""
    db = FakeDB()

    def fake_table(name):
        return FakeQueryBuilder(db.store, name)

    with patch("mission_control.supabase_client._table", side_effect=fake_table):
        with patch("mission_control.supabase_client.get_client", return_value=MagicMock()):
            yield db


@pytest.fixture
def client(fake_db):
    """Sync test client for FastAPI app with mocked DB."""
    # Patch scheduler to avoid APScheduler import issues
    with patch("mission_control.app.lifespan") as mock_lifespan:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def noop_lifespan(app):
            yield

        mock_lifespan.side_effect = noop_lifespan

        # Re-import to get patched version
        from mission_control.app import create_app
        from fastapi.testclient import TestClient

        app = create_app()
        # Override lifespan
        app.router.lifespan_context = noop_lifespan

        with TestClient(app) as c:
            yield c


# ---------------------------------------------------------------------------
# Data factories
# ---------------------------------------------------------------------------

def make_athlete(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "slug": "test-athlete",
        "name": "Test Athlete",
        "email": "test@example.com",
        "race_name": "Unbound Gravel 200",
        "race_date": "2026-06-06",
        "tier": "tier-2",
        "level": "compete",
        "plan_status": "intake_received",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "notes": "",
        "intake_json": "{}",
        "methodology_json": "{}",
        "derived_json": "{}",
    }
    defaults.update(overrides)
    return defaults


def make_deal(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "contact_email": "lead@example.com",
        "contact_name": "Jane Lead",
        "race_name": "SBT GRVL",
        "race_slug": "sbt-grvl",
        "source": "quiz",
        "value": 249.00,
        "stage": "lead",
        "notes": "",
        "athlete_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "closed_at": None,
    }
    defaults.update(overrides)
    return defaults


def make_enrollment(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "sequence_id": "welcome_v1",
        "variant": "A",
        "contact_email": "subscriber@example.com",
        "contact_name": "Test Subscriber",
        "source": "exit_intent",
        "source_data": {},
        "current_step": 0,
        "status": "active",
        "enrolled_at": datetime.now(timezone.utc).isoformat(),
        "next_send_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
    }
    defaults.update(overrides)
    return defaults


def make_payment(**overrides):
    defaults = {
        "id": str(uuid.uuid4()),
        "deal_id": str(uuid.uuid4()),
        "athlete_id": None,
        "amount": 249.00,
        "source": "manual",
        "stripe_payment_id": "",
        "description": "Training plan",
        "paid_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    defaults.update(overrides)
    return defaults
