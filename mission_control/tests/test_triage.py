"""Tests for triage service, router security, and template rendering."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from mission_control.tests.conftest import (
    make_athlete,
    make_communication,
    make_deal,
    make_enrollment,
    make_sequence_send,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _hours_ago(h):
    return (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()


def _days_ago(d):
    return (datetime.now(timezone.utc) - timedelta(days=d)).isoformat()


# ---------------------------------------------------------------------------
# Class 1: Service Happy Path
# ---------------------------------------------------------------------------

class TestTriageServiceHappyPath:

    def test_get_pending_intakes_returns_pending_requests(self, fake_db):
        from mission_control.services.triage import get_pending_intakes

        fake_db.store["plan_requests"].append({
            "id": str(uuid.uuid4()),
            "status": "pending",
            "payload": {"name": "Alice"},
            "created_at": _now_iso(),
        })
        fake_db.store["plan_requests"].append({
            "id": str(uuid.uuid4()),
            "status": "processed",
            "payload": {"name": "Bob"},
            "created_at": _now_iso(),
        })
        result = get_pending_intakes()
        assert len(result) == 1
        assert result[0]["payload"]["name"] == "Alice"

    def test_get_unanswered_replies_returns_inbound_received(self, fake_db):
        from mission_control.services.triage import get_unanswered_replies

        fake_db.store["gg_communications"].append(
            make_communication(comm_type="inbound", status="received")
        )
        fake_db.store["gg_communications"].append(
            make_communication(comm_type="inbound", status="acknowledged")
        )
        fake_db.store["gg_communications"].append(
            make_communication(comm_type="outbound", status="received")
        )
        result = get_unanswered_replies()
        assert len(result) == 1
        assert result[0]["status"] == "received"
        assert result[0]["comm_type"] == "inbound"

    def test_get_plans_needing_action_filters_actionable_statuses(self, fake_db):
        from mission_control.services.triage import get_plans_needing_action

        for status in ["pipeline_complete", "audit_passed", "approved", "delivered", "intake_received"]:
            fake_db.store["gg_athletes"].append(
                make_athlete(plan_status=status, updated_at=_now_iso())
            )
        result = get_plans_needing_action()
        statuses = {a["plan_status"] for a in result}
        assert statuses == {"pipeline_complete", "audit_passed", "approved"}
        assert len(result) == 3

    def test_get_stale_deals_returns_old_active_deals(self, fake_db):
        from mission_control.services.triage import get_stale_deals

        # Stale: updated 72h ago, active stage
        fake_db.store["gg_deals"].append(
            make_deal(stage="lead", updated_at=_hours_ago(72))
        )
        # Fresh: updated 1h ago, active stage
        fake_db.store["gg_deals"].append(
            make_deal(stage="qualified", updated_at=_hours_ago(1))
        )
        # Stale but closed: should NOT appear
        fake_db.store["gg_deals"].append(
            make_deal(stage="closed_won", updated_at=_hours_ago(72))
        )
        result = get_stale_deals()
        assert len(result) == 1
        assert result[0]["stage"] == "lead"

    def test_get_due_touchpoints_delegates_to_db(self, fake_db):
        from mission_control.services.triage import get_due_touchpoints

        with patch("mission_control.services.triage.db.get_touchpoints", return_value=[{"id": "tp1"}]) as mock_tp:
            result = get_due_touchpoints()
            mock_tp.assert_called_once_with(due_only=True, limit=20)
            assert result == [{"id": "tp1"}]

    def test_get_recent_sends_filters_by_cutoff(self, fake_db):
        from mission_control.services.triage import get_recent_sends

        # Recent send (1h ago)
        fake_db.store["gg_sequence_sends"].append(
            make_sequence_send(sent_at=_hours_ago(1))
        )
        # Old send (48h ago)
        fake_db.store["gg_sequence_sends"].append(
            make_sequence_send(sent_at=_hours_ago(48))
        )
        result = get_recent_sends(hours=24)
        assert len(result) == 1

    def test_get_recent_enrollments_filters_by_cutoff(self, fake_db):
        from mission_control.services.triage import get_recent_enrollments

        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(enrolled_at=_hours_ago(2))
        )
        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(enrolled_at=_hours_ago(48))
        )
        result = get_recent_enrollments(hours=24)
        assert len(result) == 1

    def test_get_upcoming_races_filters_by_date_range(self, fake_db):
        from mission_control.services.triage import get_upcoming_races
        from datetime import date

        today = date.today()
        in_range = (today + timedelta(days=10)).isoformat()
        out_of_range = (today + timedelta(days=60)).isoformat()
        past = (today - timedelta(days=5)).isoformat()

        fake_db.store["gg_athletes"].append(make_athlete(race_date=in_range))
        fake_db.store["gg_athletes"].append(make_athlete(race_date=out_of_range))
        fake_db.store["gg_athletes"].append(make_athlete(race_date=past))

        result = get_upcoming_races(days=30)
        assert len(result) == 1
        assert result[0]["race_date"] == in_range

    def test_get_recent_bounces_filters_bounced_status(self, fake_db):
        from mission_control.services.triage import get_recent_bounces

        fake_db.store["gg_sequence_sends"].append(
            make_sequence_send(status="bounced", sent_at=_hours_ago(12))
        )
        fake_db.store["gg_sequence_sends"].append(
            make_sequence_send(status="sent", sent_at=_hours_ago(12))
        )
        result = get_recent_bounces(days=7)
        assert len(result) == 1
        assert result[0]["status"] == "bounced"

    def test_get_recent_unsubscribes_filters_correctly(self, fake_db):
        from mission_control.services.triage import get_recent_unsubscribes

        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(status="unsubscribed", completed_at=_hours_ago(12))
        )
        fake_db.store["gg_sequence_enrollments"].append(
            make_enrollment(status="active", completed_at=_hours_ago(12))
        )
        result = get_recent_unsubscribes(days=7)
        assert len(result) == 1
        assert result[0]["status"] == "unsubscribed"

    def test_get_system_health_returns_check_structure(self, fake_db):
        from mission_control.services.triage import get_system_health

        health = get_system_health()
        assert "checks" in health
        assert "ok_count" in health
        assert "warning_count" in health
        assert "error_count" in health
        assert isinstance(health["checks"], list)
        assert len(health["checks"]) == 4
        names = {c["name"] for c in health["checks"]}
        assert "Supabase" in names
        assert "Resend (Email)" in names


# ---------------------------------------------------------------------------
# Class 2: Service Error Paths
# ---------------------------------------------------------------------------

class TestTriageServiceErrorPaths:

    def test_get_pending_intakes_returns_empty_on_db_error(self, fake_db):
        from mission_control.services.triage import get_pending_intakes

        with patch("mission_control.services.triage.db.get_pending_plan_requests", side_effect=Exception("boom")):
            result = get_pending_intakes()
            assert result == []

    def test_get_unanswered_replies_returns_empty_on_db_error(self, fake_db):
        from mission_control.services.triage import get_unanswered_replies

        with patch("mission_control.services.triage.db._table", side_effect=Exception("boom")):
            result = get_unanswered_replies()
            assert result == []

    def test_get_stale_deals_returns_empty_on_db_error(self, fake_db):
        from mission_control.services.triage import get_stale_deals

        with patch("mission_control.services.triage.db._table", side_effect=Exception("boom")):
            result = get_stale_deals()
            assert result == []

    def test_triage_summary_returns_zeros_on_db_error(self, fake_db):
        from mission_control.services.triage import triage_summary

        with patch("mission_control.services.triage.db.get_pending_plan_requests", side_effect=Exception("boom")):
            result = triage_summary()
            assert result["action_required"] == 0
            assert result["pending_intakes"] == 0
            assert result["unread_replies"] == 0


# ---------------------------------------------------------------------------
# Class 3: Summary Optimization
# ---------------------------------------------------------------------------

class TestTriageSummaryOptimization:

    def test_summary_uses_precomputed_intakes(self, fake_db):
        from mission_control.services.triage import triage_summary

        precomputed = [{"id": "1"}, {"id": "2"}]
        with patch("mission_control.services.triage.db.get_pending_plan_requests") as mock_db:
            result = triage_summary(pending_intakes=precomputed)
            mock_db.assert_not_called()
            assert result["pending_intakes"] == 2

    def test_summary_uses_precomputed_plans(self, fake_db):
        from mission_control.services.triage import triage_summary

        precomputed = [{"id": "p1"}]
        with patch("mission_control.services.triage.db._table") as mock_table:
            # We still need count_unread_inbound and count_due_touchpoints to work
            mock_builder = MagicMock()
            mock_builder.select.return_value = mock_builder
            mock_builder.eq.return_value = mock_builder
            mock_builder.lte.return_value = mock_builder
            mock_builder.execute.return_value = MagicMock(count=0)
            mock_table.return_value = mock_builder

            result = triage_summary(plans_needing_action=precomputed)
            assert result["plans_needing_action"] == 1
            # _table should only be called for count queries, not for get_plans_needing_action
            for call in mock_table.call_args_list:
                assert call[0][0] != "gg_athletes" or "plan_status" not in str(call)

    def test_summary_falls_back_to_db_when_no_precomputed_values(self, fake_db):
        from mission_control.services.triage import triage_summary

        # With empty DB, everything should be 0
        result = triage_summary()
        assert result["pending_intakes"] == 0
        assert result["plans_needing_action"] == 0


# ---------------------------------------------------------------------------
# Class 4: Route GET
# ---------------------------------------------------------------------------

class TestTriageRouteGET:

    def test_triage_page_loads_with_empty_data(self, client):
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "Triage" in resp.text

    def test_triage_page_shows_pending_intakes(self, client, fake_db):
        fake_db.store["plan_requests"].append({
            "id": str(uuid.uuid4()),
            "status": "pending",
            "payload": {"name": "Test Intake", "email": "t@t.com"},
            "created_at": _now_iso(),
        })
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "New Intakes" in resp.text

    def test_triage_page_shows_action_required_count(self, client, fake_db):
        fake_db.store["plan_requests"].append({
            "id": str(uuid.uuid4()),
            "status": "pending",
            "payload": {},
            "created_at": _now_iso(),
        })
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "Action Required" in resp.text

    def test_triage_page_shows_stale_deals(self, client, fake_db):
        fake_db.store["gg_deals"].append(
            make_deal(stage="lead", updated_at=_hours_ago(72))
        )
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "Stale Deals" in resp.text

    def test_triage_page_shows_system_health(self, client):
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "System Health" in resp.text

    def test_triage_page_degrades_gracefully_on_total_failure(self, client):
        with patch("mission_control.routers.triage.get_pending_intakes", side_effect=Exception("total failure")):
            resp = client.get("/triage")
            assert resp.status_code == 200
            assert "Connection Issue" in resp.text


# ---------------------------------------------------------------------------
# Class 5: Ack Security
# ---------------------------------------------------------------------------

class TestTriageAckSecurity:

    def _post_ack(self, client, comm_id):
        return client.post(f"/triage/ack/{comm_id}")

    def test_ack_valid_uuid_succeeds(self, client, fake_db):
        comm = make_communication()
        fake_db.store["gg_communications"].append(comm)
        resp = self._post_ack(client, comm["id"])
        assert resp.status_code == 200

    def test_ack_creates_audit_log(self, client, fake_db):
        comm = make_communication()
        fake_db.store["gg_communications"].append(comm)
        self._post_ack(client, comm["id"])
        logs = fake_db.store["gg_audit_log"]
        assert any(log["action"] == "reply_acknowledged" for log in logs)

    def test_ack_updates_status_to_acknowledged(self, client, fake_db):
        comm = make_communication(status="received")
        fake_db.store["gg_communications"].append(comm)
        self._post_ack(client, comm["id"])
        assert comm["status"] == "acknowledged"

    def test_ack_rejects_non_uuid_format(self, client, fake_db):
        resp = self._post_ack(client, "not-a-uuid")
        assert resp.status_code == 400

    def test_ack_rejects_sql_injection_attempt(self, client, fake_db):
        resp = self._post_ack(client, "'; DROP TABLE gg_communications; --")
        assert resp.status_code == 400

    def test_ack_returns_404_for_nonexistent_comm(self, client, fake_db):
        valid_uuid = str(uuid.uuid4())
        resp = self._post_ack(client, valid_uuid)
        assert resp.status_code == 404

    def test_ack_rate_limited(self, client, fake_db):
        # Clear rate buckets from prior tests
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        comm = make_communication()
        fake_db.store["gg_communications"].append(comm)

        # First 10 should succeed
        for _ in range(10):
            resp = self._post_ack(client, comm["id"])
            assert resp.status_code == 200

        # 11th should be rate-limited
        resp = self._post_ack(client, comm["id"])
        assert resp.status_code == 429

    def test_ack_handles_db_error_on_update(self, client, fake_db):
        comm = make_communication()
        fake_db.store["gg_communications"].append(comm)

        with patch("mission_control.routers.triage.db.update", side_effect=Exception("DB down")):
            # Clear rate buckets
            from mission_control.routers.triage import _rate_buckets
            _rate_buckets.clear()

            resp = self._post_ack(client, comm["id"])
            assert resp.status_code == 500


# ---------------------------------------------------------------------------
# Class 6: Ack Edge Cases
# ---------------------------------------------------------------------------

class TestTriageAckEdgeCases:

    def test_ack_with_uppercase_uuid(self, client, fake_db):
        comm = make_communication()
        fake_db.store["gg_communications"].append(comm)
        upper_id = comm["id"].upper()
        # We need to match by the original ID, so store with upper too
        comm_upper = make_communication(id=upper_id)
        fake_db.store["gg_communications"].append(comm_upper)

        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = client.post(f"/triage/ack/{upper_id}")
        assert resp.status_code == 200

    def test_ack_idempotent(self, client, fake_db):
        comm = make_communication(status="received")
        fake_db.store["gg_communications"].append(comm)

        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp1 = client.post(f"/triage/ack/{comm['id']}")
        assert resp1.status_code == 200

        resp2 = client.post(f"/triage/ack/{comm['id']}")
        assert resp2.status_code == 200
        assert comm["status"] == "acknowledged"

    def test_ack_with_already_acknowledged(self, client, fake_db):
        comm = make_communication(status="acknowledged")
        fake_db.store["gg_communications"].append(comm)

        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = client.post(f"/triage/ack/{comm['id']}")
        assert resp.status_code == 200
        assert comm["status"] == "acknowledged"


# ---------------------------------------------------------------------------
# Class 7: Template Rendering
# ---------------------------------------------------------------------------

class TestTriageTemplateRendering:

    def test_null_join_in_recent_sends_renders_safely(self, client, fake_db):
        """Sends with no enrollment join should render '—' not crash."""
        fake_db.store["gg_sequence_sends"].append(
            make_sequence_send(
                sent_at=_hours_ago(1),
                gg_sequence_enrollments=None,
            )
        )
        resp = client.get("/triage")
        assert resp.status_code == 200

    def test_null_join_in_bounces_renders_safely(self, client, fake_db):
        """Bounced sends with no enrollment join should render '—'."""
        fake_db.store["gg_sequence_sends"].append(
            make_sequence_send(
                status="bounced",
                sent_at=_hours_ago(1),
                gg_sequence_enrollments=None,
            )
        )
        resp = client.get("/triage")
        assert resp.status_code == 200

    def test_empty_state_renders_for_new_install(self, client, fake_db):
        """With no data at all, should show onboarding banner."""
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "Welcome to Mission Control" in resp.text


# ---------------------------------------------------------------------------
# Class 8: GA4 Integration
# ---------------------------------------------------------------------------

class TestTriageGA4Integration:

    def test_ga4_summary_when_not_configured(self, fake_db):
        from mission_control.services.triage import get_triage_ga4_summary

        # Simulate GA4 module not being importable
        with patch.dict("sys.modules", {"mission_control.services.ga4": None}):
            result = get_triage_ga4_summary()
            assert result["configured"] is False

    def test_ga4_summary_with_data(self, fake_db):
        from mission_control.services.triage import get_triage_ga4_summary

        mock_daily = [{"date": "2026-03-01", "sessions": 100}, {"date": "2026-03-02", "sessions": 150}]
        mock_conversions = [
            {"event": "email_capture", "count": 10},
            {"event": "plan_request", "count": 3},
            {"event": "quiz_complete", "count": 5},
        ]
        mock_sources = [{"channel": "organic / search", "sessions": 200}]

        with patch("mission_control.services.ga4.get_daily_sessions", return_value=mock_daily), \
             patch("mission_control.services.ga4.get_conversion_events", return_value=mock_conversions), \
             patch("mission_control.services.ga4.get_traffic_sources", return_value=mock_sources):
            result = get_triage_ga4_summary()
            assert result["configured"] is True
            assert result["sessions_7d"] == 250
            assert result["total_conversions"] == 18
            assert result["plan_requests"] == 3
            assert result["email_captures"] == 10
            assert result["top_source"] == "organic / search"

    def test_triage_page_shows_ga4_section(self, client, fake_db):
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "Site Analytics" in resp.text
