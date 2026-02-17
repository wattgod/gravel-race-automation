"""Tests for the sequence engine — enrollment, A/B assignment, sending, events."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from mission_control.tests.conftest import make_enrollment


class TestPickVariant:
    """Variant selection weighted random."""

    def test_respects_weights(self, fake_db):
        from mission_control.services.sequence_engine import _pick_variant

        variants = {
            "A": {"weight": 100, "steps": []},
            "B": {"weight": 0, "steps": []},
        }
        # With weight 0 on B, should always pick A
        for _ in range(20):
            assert _pick_variant(variants) == "A"

    def test_single_variant(self, fake_db):
        from mission_control.services.sequence_engine import _pick_variant

        variants = {"ONLY": {"weight": 50, "steps": []}}
        assert _pick_variant(variants) == "ONLY"

    def test_all_zero_weights_raises(self, fake_db):
        from mission_control.services.sequence_engine import _pick_variant

        variants = {
            "A": {"weight": 0, "steps": []},
            "B": {"weight": 0, "steps": []},
        }
        with pytest.raises(ValueError, match="All variant weights are zero"):
            _pick_variant(variants)

    def test_empty_variants_raises(self, fake_db):
        from mission_control.services.sequence_engine import _pick_variant

        with pytest.raises(ValueError, match="No variants defined"):
            _pick_variant({})


class TestEnroll:
    """Enrollment logic — deduplication, variant assignment, scheduling."""

    def test_enrolls_new_contact(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        result = enroll(
            email="new@example.com",
            name="New User",
            sequence_id="welcome_v1",
            source="exit_intent",
        )
        assert result is not None
        assert result["contact_email"] == "new@example.com"
        assert result["sequence_id"] == "welcome_v1"
        assert result["status"] == "active"
        assert result["variant"] in ("A", "B")

    def test_rejects_duplicate_enrollment(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        first = enroll("dupe@example.com", "Dupe", "welcome_v1")
        assert first is not None

        second = enroll("dupe@example.com", "Dupe", "welcome_v1")
        assert second is None

    def test_rejects_inactive_sequence(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        # Patch to make a sequence appear inactive
        with patch("mission_control.services.sequence_engine.get_sequence") as mock_get:
            mock_get.return_value = {"id": "test", "active": False, "variants": {}}
            result = enroll("test@example.com", "Test", "test")
            assert result is None

    def test_rejects_nonexistent_sequence(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        result = enroll("test@example.com", "Test", "nonexistent_v99")
        assert result is None

    def test_sets_next_send_at(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        result = enroll("timing@example.com", "Timing Test", "welcome_v1")
        assert result is not None
        assert result["next_send_at"] is not None

    def test_logs_audit_action(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        enroll("audit@example.com", "Audit Test", "welcome_v1")

        logs = fake_db.store["gg_audit_log"]
        assert any(
            log["action"] == "sequence_enrolled" and "audit@example.com" in log.get("details", "")
            for log in logs
        )

    def test_stores_source_data(self, fake_db):
        from mission_control.services.sequence_engine import enroll

        result = enroll(
            "data@example.com", "Data Test", "welcome_v1",
            source="quiz",
            source_data={"race_slug": "unbound-gravel-200", "race_name": "Unbound 200"},
        )
        assert result["source_data"]["race_slug"] == "unbound-gravel-200"


class TestRenderSubject:
    def test_replaces_placeholders(self, fake_db):
        from mission_control.services.sequence_engine import _render_subject

        result = _render_subject(
            "Your race: {race_name} is coming up",
            {"race_name": "SBT GRVL", "race_slug": "sbt-grvl"},
        )
        assert result == "Your race: SBT GRVL is coming up"

    def test_no_placeholders_unchanged(self, fake_db):
        from mission_control.services.sequence_engine import _render_subject

        result = _render_subject("Welcome to Gravel God", {})
        assert result == "Welcome to Gravel God"


class TestRenderTemplate:
    def test_renders_existing_template(self, fake_db):
        from mission_control.services.sequence_engine import _render_template

        html = _render_template("welcome_a", {
            "contact_name": "Sarah Johnson",
            "contact_email": "sarah@example.com",
            "source_data": {"race_name": "Unbound 200"},
        })
        assert "Sarah" in html  # {first_name} replaced
        assert "Gravel God" in html  # template content present
        assert "{first_name}" not in html  # placeholder replaced

    def test_raises_on_missing_template(self, fake_db):
        from mission_control.services.sequence_engine import _render_template

        with pytest.raises(FileNotFoundError, match="nonexistent_template"):
            _render_template("nonexistent_template", {"contact_name": "", "source_data": {}})

    def test_handles_empty_name(self, fake_db):
        from mission_control.services.sequence_engine import _render_template

        html = _render_template("welcome_a", {
            "contact_name": "",
            "contact_email": "anon@example.com",
            "source_data": {},
        })
        assert isinstance(html, str)
        assert len(html) > 100


class TestRecordEvent:
    def test_records_open_event(self, fake_db):
        from mission_control.services.sequence_engine import record_event

        enrollment = make_enrollment()
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        send = {
            "id": str(uuid.uuid4()),
            "enrollment_id": enrollment["id"],
            "resend_id": "resend-abc-123",
            "step_index": 0,
            "template": "welcome_a",
            "subject": "Welcome",
            "status": "sent",
            "opened_at": None,
            "clicked_at": None,
        }
        fake_db.store["gg_sequence_sends"].append(send)

        result = record_event("resend-abc-123", "email.opened")
        assert result is True
        assert send["status"] == "opened"
        assert send["opened_at"] is not None

    def test_records_click_event(self, fake_db):
        from mission_control.services.sequence_engine import record_event

        enrollment = make_enrollment()
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        send = {
            "id": str(uuid.uuid4()),
            "enrollment_id": enrollment["id"],
            "resend_id": "resend-click-456",
            "step_index": 0,
            "template": "welcome_a",
            "subject": "Welcome",
            "status": "sent",
            "opened_at": None,
            "clicked_at": None,
        }
        fake_db.store["gg_sequence_sends"].append(send)

        result = record_event("resend-click-456", "email.clicked")
        assert result is True
        assert send["status"] == "clicked"

    def test_bounce_pauses_enrollment(self, fake_db):
        from mission_control.services.sequence_engine import record_event

        enrollment = make_enrollment(status="active")
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        send = {
            "id": str(uuid.uuid4()),
            "enrollment_id": enrollment["id"],
            "resend_id": "resend-bounce-789",
            "step_index": 0,
            "template": "welcome_a",
            "subject": "Welcome",
            "status": "sent",
            "opened_at": None,
            "clicked_at": None,
        }
        fake_db.store["gg_sequence_sends"].append(send)

        result = record_event("resend-bounce-789", "email.bounced")
        assert result is True
        assert enrollment["status"] == "paused"

    def test_unknown_resend_id_returns_false(self, fake_db):
        from mission_control.services.sequence_engine import record_event

        result = record_event("nonexistent-id", "email.opened")
        assert result is False

    def test_does_not_overwrite_existing_open(self, fake_db):
        from mission_control.services.sequence_engine import record_event

        enrollment = make_enrollment()
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        original_time = "2026-02-15T10:00:00+00:00"
        send = {
            "id": str(uuid.uuid4()),
            "enrollment_id": enrollment["id"],
            "resend_id": "resend-double-open",
            "step_index": 0,
            "template": "welcome_a",
            "subject": "Welcome",
            "status": "opened",
            "opened_at": original_time,
            "clicked_at": None,
        }
        fake_db.store["gg_sequence_sends"].append(send)

        result = record_event("resend-double-open", "email.opened")
        # Should return False because opened_at already set
        assert result is False
        assert send["opened_at"] == original_time


class TestPauseResume:
    def test_pause_active_enrollment(self, fake_db):
        from mission_control.services.sequence_engine import pause_enrollment

        enrollment = make_enrollment(status="active")
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        result = pause_enrollment(enrollment["id"])
        assert result is True
        assert enrollment["status"] == "paused"

    def test_pause_non_active_returns_false(self, fake_db):
        from mission_control.services.sequence_engine import pause_enrollment

        enrollment = make_enrollment(status="completed")
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        result = pause_enrollment(enrollment["id"])
        assert result is False

    def test_resume_paused_enrollment(self, fake_db):
        from mission_control.services.sequence_engine import resume_enrollment

        enrollment = make_enrollment(status="paused", current_step=1)
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        result = resume_enrollment(enrollment["id"])
        assert result is True
        assert enrollment["status"] == "active"
        assert enrollment["next_send_at"] is not None

    def test_resume_non_paused_returns_false(self, fake_db):
        from mission_control.services.sequence_engine import resume_enrollment

        enrollment = make_enrollment(status="active")
        fake_db.store["gg_sequence_enrollments"].append(enrollment)

        result = resume_enrollment(enrollment["id"])
        assert result is False


class TestUnsubscribe:
    def test_unsubscribes_all_active(self, fake_db):
        from mission_control.services.sequence_engine import unsubscribe

        email = "unsub@example.com"
        e1 = make_enrollment(contact_email=email, status="active", sequence_id="welcome_v1")
        e2 = make_enrollment(contact_email=email, status="active", sequence_id="nurture_v1")
        e3 = make_enrollment(contact_email=email, status="completed", sequence_id="win_back_v1")

        fake_db.store["gg_sequence_enrollments"].extend([e1, e2, e3])

        count = unsubscribe(email)
        assert count == 2
        assert e1["status"] == "unsubscribed"
        assert e2["status"] == "unsubscribed"
        assert e3["status"] == "completed"  # unchanged

    def test_unsubscribe_no_enrollments(self, fake_db):
        from mission_control.services.sequence_engine import unsubscribe

        count = unsubscribe("nobody@example.com")
        assert count == 0


class TestUnsubscribeTokens:
    """HMAC-based unsubscribe token generation and verification."""

    def test_generate_token_deterministic(self, fake_db):
        from mission_control.services.sequence_engine import generate_unsubscribe_token

        t1 = generate_unsubscribe_token("test@example.com")
        t2 = generate_unsubscribe_token("test@example.com")
        assert t1 == t2

    def test_different_emails_different_tokens(self, fake_db):
        from mission_control.services.sequence_engine import generate_unsubscribe_token

        t1 = generate_unsubscribe_token("a@example.com")
        t2 = generate_unsubscribe_token("b@example.com")
        assert t1 != t2

    def test_verify_valid_token(self, fake_db):
        from mission_control.services.sequence_engine import (
            generate_unsubscribe_token, verify_unsubscribe_token,
        )

        email = "valid@example.com"
        token = generate_unsubscribe_token(email)
        assert verify_unsubscribe_token(email, token) is True

    def test_verify_invalid_token(self, fake_db):
        from mission_control.services.sequence_engine import verify_unsubscribe_token

        assert verify_unsubscribe_token("test@example.com", "bogus-token") is False

    def test_case_insensitive_email(self, fake_db):
        from mission_control.services.sequence_engine import (
            generate_unsubscribe_token, verify_unsubscribe_token,
        )

        token = generate_unsubscribe_token("Test@Example.COM")
        assert verify_unsubscribe_token("test@example.com", token) is True

    def test_build_unsubscribe_url(self, fake_db):
        from mission_control.services.sequence_engine import build_unsubscribe_url

        url = build_unsubscribe_url("test@example.com")
        assert "/unsubscribe?" in url
        assert "email=test%40example.com" in url
        assert "token=" in url


class TestInjectUnsubscribe:
    def test_injects_before_body_close(self, fake_db):
        from mission_control.services.sequence_engine import _inject_unsubscribe

        html = "<html><body><p>Hello</p></body></html>"
        result = _inject_unsubscribe(html, "test@example.com")
        assert "Unsubscribe" in result
        assert result.index("Unsubscribe") < result.index("</body>")

    def test_link_contains_email_and_token(self, fake_db):
        from mission_control.services.sequence_engine import _inject_unsubscribe

        html = "<html><body><p>Hello</p></body></html>"
        result = _inject_unsubscribe(html, "test@example.com")
        assert "test%40example.com" in result
        assert "token=" in result


class TestProcessingLock:
    """process_due_sends() uses async lock to prevent duplicates."""

    def test_lock_exists(self, fake_db):
        import asyncio
        from mission_control.services.sequence_engine import _processing_lock
        assert isinstance(_processing_lock, asyncio.Lock)

    def test_skips_when_locked(self, fake_db):
        import asyncio
        from mission_control.services.sequence_engine import process_due_sends, _processing_lock

        async def run():
            # Acquire lock first
            async with _processing_lock:
                result = await process_due_sends()
            return result

        result = asyncio.new_event_loop().run_until_complete(run())
        assert result["skipped"] is True
        assert result["processed"] == 0


class TestGetSequenceStats:
    def test_stats_with_enrollments(self, fake_db):
        from mission_control.services.sequence_engine import get_sequence_stats

        # Create enrollments
        e1 = make_enrollment(variant="A", status="completed")
        e2 = make_enrollment(variant="A", status="active",
                             contact_email="e2@test.com")
        e3 = make_enrollment(variant="B", status="completed",
                             contact_email="e3@test.com")

        fake_db.store["gg_sequence_enrollments"].extend([e1, e2, e3])

        # Create sends
        fake_db.store["gg_sequence_sends"].extend([
            {"id": str(uuid.uuid4()), "enrollment_id": e1["id"],
             "step_index": 0, "template": "welcome_a", "subject": "Hi",
             "opened_at": "2026-01-01T00:00:00Z", "clicked_at": None},
            {"id": str(uuid.uuid4()), "enrollment_id": e3["id"],
             "step_index": 0, "template": "welcome_b", "subject": "Hi",
             "opened_at": "2026-01-01T00:00:00Z", "clicked_at": "2026-01-01T01:00:00Z"},
        ])

        stats = get_sequence_stats("welcome_v1")
        assert stats["total"] == 3
        assert stats["completed"] == 2
        assert stats["active"] == 1
        assert "A" in stats["variants"]
        assert "B" in stats["variants"]
        assert stats["variants"]["A"]["total"] == 2
        assert stats["variants"]["B"]["total"] == 1

    def test_stats_empty_sequence(self, fake_db):
        from mission_control.services.sequence_engine import get_sequence_stats

        stats = get_sequence_stats("welcome_v1")
        assert stats["total"] == 0
        assert stats["completion_rate"] == 0
