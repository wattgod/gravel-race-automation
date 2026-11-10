"""Health checks: /health (Railway's deploy gate) and /health/jobs (heartbeat).

The test client stubs the lifespan, so the job timer never runs here; the
scheduler check and start-up state are injected through mission_control.app.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx
import pytest

import mission_control.app as app_mod

ALL_SETTINGS = {
    "SUPABASE_URL": "https://fake.supabase.co",
    "SUPABASE_SERVICE_KEY": "fake-key",
    "RESEND_API_KEY": "test-resend-key",
    "WEBHOOK_SECRET": "test-secret-123",
    "MISSION_CONTROL_SECRET": "test-secret-for-tests",
}


@pytest.fixture
def healthy(monkeypatch):
    for k, v in ALL_SETTINGS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(app_mod, "_scheduler_running", lambda: True)


@pytest.fixture
def job_health(monkeypatch):
    state = {"started": None, "first_start": False, "last_good_tick": None, "last_run": None}
    monkeypatch.setattr(app_mod, "_job_health", state)
    return state


class TestHealth:
    def test_ok_when_timer_running_and_settings_present(self, client, healthy):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_503_when_timer_not_running(self, client, healthy, monkeypatch):
        monkeypatch.setattr(app_mod, "_scheduler_running", lambda: False)
        resp = client.get("/health")
        assert resp.status_code == 503
        assert "scheduler not running" in resp.json()["failed"]

    @pytest.mark.parametrize("name", sorted(ALL_SETTINGS))
    def test_503_names_the_missing_setting_never_values(self, client, healthy, monkeypatch, name):
        monkeypatch.setenv(name, "")
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["failed"] == [f"missing setting: {name}"]
        for value in ALL_SETTINGS.values():
            assert value not in resp.text

    def test_whitespace_counts_as_missing(self, client, healthy, monkeypatch):
        monkeypatch.setenv("RESEND_API_KEY", "   ")
        assert client.get("/health").status_code == 503

    def test_optional_secrets_not_required(self, client, healthy, monkeypatch):
        monkeypatch.delenv("UNSUBSCRIBE_SECRET", raising=False)
        monkeypatch.delenv("RESEND_WEBHOOK_SECRET", raising=False)
        assert client.get("/health").status_code == 200

    def test_fake_scheduler_module_is_not_mistaken_for_running(self):
        """The conftest stub is a MagicMock; only a real True counts."""
        import sys
        from unittest.mock import MagicMock
        mod = sys.modules.get("mission_control.scheduler")
        if mod is not None and isinstance(getattr(mod, "scheduler", None), MagicMock):
            assert app_mod._scheduler_running() is False


class TestRecordTick:
    def test_ordinary_tick_is_good(self, job_health):
        app_mod.record_sequence_tick({"processed": 3, "sent": 2, "errors": 1, "skipped": False})
        assert job_health["last_good_tick"] is not None
        assert job_health["last_run"] == {"processed": 3, "sent": 2, "errors": 1}

    def test_empty_tick_is_good(self, job_health):
        app_mod.record_sequence_tick({"processed": 0, "sent": 0, "errors": 0, "skipped": False})
        assert job_health["last_good_tick"] is not None

    def test_skipped_tick_is_not_good(self, job_health):
        app_mod.record_sequence_tick({"processed": 0, "sent": 0, "errors": 0, "skipped": True})
        assert job_health["last_good_tick"] is None

    def test_every_send_failed_is_not_good(self, job_health):
        app_mod.record_sequence_tick({"processed": 4, "sent": 0, "errors": 4, "skipped": False})
        assert job_health["last_good_tick"] is None
        assert job_health["last_run"] == {"processed": 4, "sent": 0, "errors": 4}


class TestJobsHealth:
    def test_fresh_tick_is_ok(self, client, job_health):
        now = datetime.now(timezone.utc)
        job_health["started"] = now - timedelta(hours=5)
        job_health["last_good_tick"] = now - timedelta(minutes=20)
        job_health["last_run"] = {"processed": 1, "sent": 1, "errors": 0}
        resp = client.get("/health/jobs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert set(body) == {"last_good_tick_utc", "started_utc", "last_run", "ok"}
        assert body["last_run"] == {"processed": 1, "sent": 1, "errors": 0}

    def test_stale_tick_is_503(self, client, job_health):
        now = datetime.now(timezone.utc)
        job_health["started"] = now - timedelta(hours=5)
        job_health["last_good_tick"] = now - timedelta(minutes=46)
        resp = client.get("/health/jobs")
        assert resp.status_code == 503
        assert resp.json()["ok"] is False

    def test_fresh_first_start_is_ok_before_any_tick(self, client, job_health):
        job_health["started"] = datetime.now(timezone.utc) - timedelta(minutes=10)
        job_health["first_start"] = True
        assert client.get("/health/jobs").status_code == 200

    def test_crash_loop_start_is_503_before_any_tick(self, client, job_health):
        job_health["started"] = datetime.now(timezone.utc) - timedelta(minutes=10)
        job_health["first_start"] = False
        assert client.get("/health/jobs").status_code == 503

    def test_old_start_without_tick_is_503(self, client, job_health):
        job_health["started"] = datetime.now(timezone.utc) - timedelta(minutes=50)
        job_health["first_start"] = True
        assert client.get("/health/jobs").status_code == 503

    def test_public_no_auth_needed(self, client, job_health):
        job_health["started"] = datetime.now(timezone.utc)
        job_health["first_start"] = True
        resp = client.get("/health/jobs", headers={"Authorization": ""})
        assert resp.status_code == 200


class TestRecordServerStart:
    def test_first_start_when_no_previous(self, fake_db, job_health):
        now = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        assert app_mod.record_server_start(now) is True
        from mission_control import supabase_client as db
        assert db.get_setting(app_mod.LAST_START_SETTING) == now.isoformat()

    def test_restart_within_two_hours_is_not_first(self, fake_db, job_health):
        t0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        app_mod.record_server_start(t0)
        assert app_mod.record_server_start(t0 + timedelta(minutes=30)) is False
        assert job_health["first_start"] is False

    def test_restart_after_two_hours_is_first(self, fake_db, job_health):
        t0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        app_mod.record_server_start(t0)
        assert app_mod.record_server_start(t0 + timedelta(hours=2, minutes=1)) is True

    def test_database_failure_is_not_first(self, monkeypatch, job_health):
        from mission_control import supabase_client as db

        def boom(*a, **k):
            raise RuntimeError("db down")

        monkeypatch.setattr(db, "get_setting", boom)
        monkeypatch.setattr(db, "set_setting", boom)
        assert app_mod.record_server_start() is False


class TestLogging:
    def test_database_urls_with_emails_are_not_logged(self):
        """httpx logs every request URL at INFO; lookups put emails in it."""
        root = logging.getLogger()
        names = [None, *app_mod._QUIET_LOGGERS]
        saved = {n: logging.getLogger(n).level for n in names}
        records: list[logging.LogRecord] = []

        class Grab(logging.Handler):
            def emit(self, record):
                records.append(record)

        grab = Grab(level=logging.DEBUG)
        root.addHandler(grab)
        transport = httpx.MockTransport(lambda req: httpx.Response(200, json=[]))
        url = "https://fake.supabase.co/rest/v1/gg_contacts?email=eq.someone%40example.com"
        try:
            # Control: without the quiet levels httpx does log the URL.
            logging.getLogger("httpx").setLevel(logging.INFO)
            root.setLevel(logging.INFO)
            with httpx.Client(transport=transport) as c:
                c.get(url)
            assert any("example.com" in r.getMessage() for r in records)

            records.clear()
            app_mod.configure_logging()
            with httpx.Client(transport=transport) as c:
                c.get(url)
            assert not any(
                "example.com" in r.getMessage() or "@" in r.getMessage() for r in records
            )
            for name in app_mod._QUIET_LOGGERS:
                assert logging.getLogger(name).level == logging.WARNING
            assert root.level == logging.INFO
        finally:
            root.removeHandler(grab)
            for n, lvl in saved.items():
                logging.getLogger(n).setLevel(lvl)


class TestLifespan:
    def test_scheduler_start_failure_logs_error_and_health_is_503(
        self, fake_db, monkeypatch, caplog,
    ):
        import asyncio
        import sys
        import types

        class _Broken:
            running = False

            def start(self):
                raise RuntimeError("no event loop")

            def shutdown(self, wait=False):
                pass

        fake_mod = types.ModuleType("mission_control.scheduler")
        fake_mod.scheduler = _Broken()
        monkeypatch.setitem(sys.modules, "mission_control.scheduler", fake_mod)
        monkeypatch.setattr(
            "mission_control.services.race_countdown.probe_race_dates", lambda: "skipped",
        )

        async def run():
            async with app_mod.lifespan(None):
                await asyncio.sleep(0)

        with caplog.at_level(logging.INFO, logger="mission_control.app"):
            asyncio.run(run())
        assert any(
            r.levelno == logging.ERROR and "Scheduler failed to start" in r.getMessage()
            for r in caplog.records
        )
        assert "scheduler not running" in app_mod.health_problems()
