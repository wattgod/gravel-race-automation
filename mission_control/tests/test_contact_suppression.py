"""Do-not-email list: coached athletes never get nurture or follow-ups.

Matti, Oct 23 2026: "Make sure not to message former or current athletes."
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import patch

from mission_control.sequences import SEQUENCES
from mission_control.tests.conftest import make_enrollment

ATHLETE = "rider@example.com"


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


def _suppress(fake_db, email=ATHLETE):
    fake_db.store["gg_contact_suppressions"].append(
        {"email": email, "reason": "coached_athlete", "source": "test"})


def _receipt_sequence_id():
    return next(sid for sid, seq in SEQUENCES.items()
                if seq.get("trigger") == "athlete_review" and seq.get("active"))


class TestEnroll:
    def test_listed_address_is_not_enrolled_in_nurture(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        _suppress(fake_db)
        assert enroll(ATHLETE, "Rider", "welcome_v1", source="exit_intent") is None
        assert fake_db.store["gg_sequence_enrollments"] == []

    def test_match_ignores_case_and_spaces(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        _suppress(fake_db)
        assert enroll("  Rider@Example.COM ", "Rider", "welcome_v1") is None

    def test_listed_buyer_gets_no_post_purchase_follow_ups(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        _suppress(fake_db)
        assert enroll(ATHLETE, "Rider", "post_purchase_v1", source="trainingpeaks_store") is None

    def test_receipt_for_their_own_form_still_goes(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        _suppress(fake_db)
        assert enroll(ATHLETE, "Rider", _receipt_sequence_id(), source="athlete_review") is not None

    def test_unlisted_address_enrolls(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        _suppress(fake_db)
        assert enroll("lead@example.com", "Lead", "welcome_v1") is not None


class TestSend:
    def test_enrolled_athlete_is_closed_unsent(self, fake_db):
        from mission_control.services.sequence_engine import _send_next_step

        _suppress(fake_db)
        enrollment = make_enrollment(contact_email=ATHLETE, sequence_id="welcome_v1")
        fake_db.store["gg_sequence_enrollments"].append(enrollment)
        with patch("mission_control.services.sequence_engine._send_email_sync") as send:
            assert _run(_send_next_step(enrollment)) is True
        send.assert_not_called()
        assert enrollment["status"] == "completed"
        assert fake_db.store["gg_sequence_sends"] == []
        assert any(r["action"] == "sequence_suppressed" for r in fake_db.store["gg_audit_log"])

    def test_first_step_is_never_resent_to_an_athlete(self, fake_db):
        from mission_control.services.sequence_engine import resend_first_step

        _suppress(fake_db)
        enrollment = make_enrollment(contact_email=ATHLETE, sequence_id="welcome_v1", status="completed")
        with patch("mission_control.services.sequence_engine._send_email_sync") as send:
            assert _run(resend_first_step(enrollment)) is False
        send.assert_not_called()


class TestFailsClosed:
    def test_unreadable_list_counts_as_listed(self):
        from mission_control.services.contact_suppression import is_suppressed

        with patch("mission_control.supabase_client.select_one", side_effect=RuntimeError("no table")):
            assert is_suppressed("lead@example.com") is True

    def test_unreadable_list_stops_race_watch(self):
        from mission_control.services.race_watch import run_race_watch

        intel = {"alpha": [{"date": "2026-08-08", "text": "new"}]}
        with patch("mission_control.services.race_watch._fetch_intel_sync", return_value=intel), \
                patch("mission_control.services.race_watch.load_suppressed", return_value=None), \
                patch("mission_control.services.race_watch.db.log_action"), \
                patch("mission_control.services.race_watch._send_email_sync") as send:
            summary = _run(run_race_watch(datetime(2026, 8, 13, tzinfo=timezone.utc)))
        send.assert_not_called()
        assert summary["notified"] == 0


def test_race_watch_skips_listed_watchers():
    from mission_control.services.race_watch import run_race_watch

    watcher = {"id": "1", "sequence_id": "race_watch_v1", "contact_email": "Rider@Example.com",
               "contact_name": "R", "status": "completed", "enrolled_at": "2026-08-01T12:00:00+00:00",
               "source_data": {"race_slug": "alpha", "race_name": "Alpha"}}
    intel = {"alpha": [{"date": "2026-08-08", "text": "new"}]}
    with patch("mission_control.services.race_watch._fetch_intel_sync", return_value=intel), \
            patch("mission_control.services.race_watch.load_suppressed", return_value={ATHLETE}), \
            patch("mission_control.services.race_watch.db.select", return_value=[watcher]), \
            patch("mission_control.services.race_watch._send_email_sync") as send:
        summary = _run(run_race_watch(datetime(2026, 8, 13, tzinfo=timezone.utc)))
    send.assert_not_called()
    assert summary["skipped_suppressed"] == 1
