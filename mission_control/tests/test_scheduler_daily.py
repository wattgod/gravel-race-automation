"""Daily jobs: three slots a day, at most one completed run per UTC day.

conftest's ``client`` fixture may already have put a stub module at
``mission_control.scheduler``; the fixture below loads the real one for each
test and puts back whatever was there, so the result does not depend on
which tests ran first.
"""

import asyncio
import importlib
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

import mission_control


@pytest.fixture
def sched(fake_db):
    saved_mod = sys.modules.pop("mission_control.scheduler", None)
    saved_attr = getattr(mission_control, "scheduler", None)
    try:
        mod = importlib.import_module("mission_control.scheduler")
        yield mod
    finally:
        if saved_mod is not None:
            sys.modules["mission_control.scheduler"] = saved_mod
        else:
            sys.modules.pop("mission_control.scheduler", None)
        if saved_attr is not None:
            mission_control.scheduler = saved_attr


class _FrozenDatetime(datetime):
    frozen = datetime(2026, 11, 10, 14, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.frozen


def _run(coro):
    return asyncio.run(coro)


def _markers(fake_db):
    return [r for r in fake_db.store["gg_audit_log"] if r["action"] == "daily_job_done"]


class TestDailyJobOncePerDay:
    def test_second_same_day_call_does_nothing_even_with_backlog(self, sched, fake_db, monkeypatch):
        monkeypatch.setattr(sched, "datetime", _FrozenDatetime)
        calls = []

        async def runner():
            calls.append(1)
            # A capped run: work is left over, but today's volume is spent.
            return {"enrolled": 5, "capped": True, "deferred": 40, "aborted": False}

        assert _run(sched._run_daily("race_countdown", runner)) is True
        assert _run(sched._run_daily("race_countdown", runner)) is False
        assert _run(sched._run_daily("race_countdown", runner)) is False
        assert len(calls) == 1
        assert [m["entity_id"] for m in _markers(fake_db)] == ["race_countdown:2026-11-10"]

    def test_raising_run_leaves_no_marker_and_next_slot_retries(self, sched, fake_db, monkeypatch):
        monkeypatch.setattr(sched, "datetime", _FrozenDatetime)
        calls = []

        async def boom():
            calls.append("boom")
            raise RuntimeError("race data fetch failed")

        async def ok():
            calls.append("ok")
            return {"aborted": False}

        assert _run(sched._run_daily("race_watch", boom)) is False
        assert _markers(fake_db) == []
        assert _run(sched._run_daily("race_watch", ok)) is True
        assert calls == ["boom", "ok"]
        assert len(_markers(fake_db)) == 1

    def test_aborted_summary_leaves_no_marker(self, sched, fake_db, monkeypatch):
        monkeypatch.setattr(sched, "datetime", _FrozenDatetime)

        async def aborted():
            return {"enrolled": 0, "aborted": True}

        assert _run(sched._run_daily("race_debrief", aborted)) is False
        assert _markers(fake_db) == []

    def test_next_utc_day_runs_again(self, sched, fake_db, monkeypatch):
        monkeypatch.setattr(sched, "datetime", _FrozenDatetime)
        calls = []

        async def runner():
            calls.append(1)
            return {"aborted": False}

        assert _run(sched._run_daily("win_back", runner)) is True
        monkeypatch.setattr(
            _FrozenDatetime, "frozen", datetime(2026, 11, 11, 15, 30, tzinfo=timezone.utc),
        )
        assert _run(sched._run_daily("win_back", runner)) is True
        assert len(calls) == 2
        assert sorted(m["entity_id"] for m in _markers(fake_db)) == [
            "win_back:2026-11-10", "win_back:2026-11-11",
        ]

    def test_jobs_have_separate_markers(self, sched, fake_db, monkeypatch):
        monkeypatch.setattr(sched, "datetime", _FrozenDatetime)

        async def runner():
            return {}

        assert _run(sched._run_daily("race_countdown", runner)) is True
        assert _run(sched._run_daily("race_debrief", runner)) is True

    def test_unreadable_marker_skips_the_slot(self, sched, fake_db, monkeypatch):
        calls = []

        async def runner():
            calls.append(1)
            return {}

        with patch.object(sched.db, "select", side_effect=RuntimeError("db down")):
            assert _run(sched._run_daily("race_countdown", runner)) is False
        assert calls == []


class TestSlots:
    def test_each_daily_job_has_three_slots_in_the_same_order(self, sched):
        def fields(job_id):
            job = sched.scheduler.get_job(job_id)
            return {f.name: str(f) for f in job.trigger.fields}

        expected = {
            "race_countdown": ("14,17,20", "0"),
            "race_debrief": ("14,17,20", "30"),
            "race_watch": ("15,18,21", "0"),
            "win_back": ("15,18,21", "30"),
        }
        for job_id, (hours, minute) in expected.items():
            f = fields(job_id)
            assert f["hour"] == hours, job_id
            assert f["minute"] == minute, job_id

    def test_job_wrappers_go_through_the_once_a_day_guard(self, sched, monkeypatch):
        seen = []

        async def fake_run_daily(job, runner):
            seen.append(job)
            return True

        monkeypatch.setattr(sched, "_run_daily", fake_run_daily)
        for fn in (sched.race_countdown, sched.race_debrief, sched.race_watch, sched.win_back):
            _run(fn())
        assert seen == ["race_countdown", "race_debrief", "race_watch", "win_back"]


class TestSequenceTickRecorded:
    def test_process_sequences_records_the_tick(self, sched, monkeypatch):
        import mission_control.app as app_mod

        state = {"started": None, "first_start": False, "last_good_tick": None, "last_run": None}
        monkeypatch.setattr(app_mod, "_job_health", state)

        async def fake_sends():
            return {"processed": 2, "sent": 2, "errors": 0, "skipped": False}

        monkeypatch.setattr(sched, "process_due_sends", fake_sends)
        _run(sched.process_sequences())
        assert state["last_good_tick"] is not None
        assert state["last_run"] == {"processed": 2, "sent": 2, "errors": 0}
