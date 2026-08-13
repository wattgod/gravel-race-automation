import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from mission_control.sequences import SEQUENCES, get_sequences_for_trigger
from mission_control.services.race_watch import pending_events, run_race_watch


def _run(coro):
    return asyncio.run(coro)


def _watch(i, *, status="completed", email=None, enrolled_at="2026-08-01T12:00:00+00:00", source_data=None):
    return {"id": str(i), "sequence_id": "race_watch_v1", "contact_email": email or f"r{i}@x.com", "contact_name": "R", "status": status, "enrolled_at": enrolled_at, "source_data": source_data or {"race_slug": "alpha", "race_name": "Alpha"}}


def test_worker_payload_contract_and_allowlist():
    root = Path(__file__).resolve().parents[2]
    worker = (root / "workers/fueling-lead-intake/worker.js").read_text()
    page = (root / "wordpress/generate_neo_brutalist.py").read_text()
    assert "'race_watch'" in worker
    for field in ("source:'race_watch'", "race_slug:form.race_slug.value", "race_name:form.race_name.value", "website:form.website.value"):
        assert field in page
    for field in ("race_slug: data.race_slug", "race_name: data.race_name", "source: source"):
        assert field in worker


def test_sequence_registration_and_confirm_step():
    seq = SEQUENCES["race_watch_v1"]
    assert get_sequences_for_trigger("race_watch") == [seq]
    steps = seq["variants"]["A"]["steps"]
    assert steps == [{"delay_days": 0, "template": "race_watch_confirm", "subject": "watching {race_name}"}]


def test_signup_baseline_never_replays_history():
    enrollment = _watch(1, enrolled_at="2026-08-10T00:00:00+00:00")
    events = [{"date": "2026-08-09", "text": "old"}, {"date": "2026-08-11", "text": "new"}]
    assert [event["text"] for event in pending_events(enrollment, events)] == ["new"]


def test_new_event_send_updates_state_and_audits():
    enrollment = _watch(1)
    intel = {"alpha": [{"date": "2026-08-08", "text": "Date confirmed"}]}
    with patch("mission_control.services.race_watch._fetch_intel_sync", return_value=intel), \
         patch("mission_control.services.race_watch.db.select", return_value=[enrollment]), \
         patch("mission_control.services.race_watch.db.update") as update, \
         patch("mission_control.services.race_watch.db.insert"), \
         patch("mission_control.services.race_watch.db.log_action") as log, \
         patch("mission_control.services.race_watch._send_email_sync", return_value="re_1") as send:
        summary = _run(run_race_watch(datetime(2026, 8, 13, tzinfo=timezone.utc)))
    assert summary["notified"] == 1
    assert send.call_args.args[1] == "Alpha: update"
    assert "2026-08-08 · Date confirmed" in send.call_args.args[2]
    assert update.call_args.args[1]["source_data"]["last_notified_event_date"] == "2026-08-08"
    assert log.call_args.args[0] == "race_watch_notified"


def test_seven_day_cap_folds_events():
    enrollment = _watch(1, source_data={"race_slug": "alpha", "race_name": "Alpha", "last_notified_event_date": "2026-08-01", "last_notified_at": "2026-08-10T15:00:00+00:00"})
    intel = {"alpha": [{"date": "2026-08-12", "text": "new"}]}
    with patch("mission_control.services.race_watch._fetch_intel_sync", return_value=intel), patch("mission_control.services.race_watch.db.select", return_value=[enrollment]), patch("mission_control.services.race_watch._send_email_sync") as send:
        summary = _run(run_race_watch(datetime(2026, 8, 13, 15, tzinfo=timezone.utc)))
    assert summary["skipped_rate_cap"] == 1
    send.assert_not_called()


def test_cap_per_run(monkeypatch):
    rows = [_watch(i) for i in range(55)]
    intel = {"alpha": [{"date": "2026-08-08", "text": "new"}]}
    with patch("mission_control.services.race_watch._fetch_intel_sync", return_value=intel), patch("mission_control.services.race_watch.db.select", return_value=rows), patch("mission_control.services.race_watch.db.update"), patch("mission_control.services.race_watch.db.insert"), patch("mission_control.services.race_watch.db.log_action"), patch("mission_control.services.race_watch._send_email_sync", return_value="re") as send:
        summary = _run(run_race_watch(datetime(2026, 8, 13, tzinfo=timezone.utc)))
    assert summary["notified"] == 50
    assert summary["capped"] is True
    assert send.call_count == 50


def test_unsubscribed_contact_skipped():
    watcher = _watch(1, email="stop@x.com")
    unsubscribe = {"sequence_id": "welcome_v1", "contact_email": "stop@x.com", "status": "unsubscribed"}
    with patch("mission_control.services.race_watch._fetch_intel_sync", return_value={"alpha": [{"date": "2026-08-08", "text": "new"}]}), patch("mission_control.services.race_watch.db.select", return_value=[watcher, unsubscribe]), patch("mission_control.services.race_watch._send_email_sync") as send:
        summary = _run(run_race_watch(datetime(2026, 8, 13, tzinfo=timezone.utc)))
    assert summary["skipped_unsubscribed"] == 1
    send.assert_not_called()


def test_abort_is_surfaced():
    with patch("mission_control.services.race_watch._fetch_intel_sync", return_value={}), patch("mission_control.services.race_watch.db.log_action") as log:
        summary = _run(run_race_watch(datetime(2026, 8, 13, tzinfo=timezone.utc)))
    assert summary["notified"] == 0
    assert log.call_args.args[0] == "race_watch_aborted"
