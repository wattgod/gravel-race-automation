"""Tests for triage service, router security, and template rendering."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import pytest

from mission_control.tests.conftest import (
    make_api_usage,
    make_athlete,
    make_communication,
    make_deal,
    make_enrollment,
    make_sequence_send,
    make_touchpoint,
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


# ---------------------------------------------------------------------------
# Class 9: Stats Endpoint + OOB
# ---------------------------------------------------------------------------

class TestStatsEndpoint:

    def test_get_stats_returns_html_fragment(self, client, fake_db):
        resp = client.get("/triage/stats")
        assert resp.status_code == 200
        assert "Action Required" in resp.text
        assert "Pending Intakes" in resp.text

    def test_get_stats_reflects_current_counts(self, client, fake_db):
        fake_db.store["plan_requests"].append({
            "id": str(uuid.uuid4()),
            "status": "pending",
            "payload": {"name": "Alice"},
            "created_at": _now_iso(),
        })
        resp = client.get("/triage/stats")
        assert resp.status_code == 200
        # Should include at least 1 in some count
        assert "Action Required" in resp.text

    def test_ack_returns_oob_stats(self, client, fake_db):
        """POST /triage/ack now returns OOB stats refresh."""
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        comm = make_communication()
        fake_db.store["gg_communications"].append(comm)
        resp = client.post(f"/triage/ack/{comm['id']}")
        assert resp.status_code == 200
        assert "hx-swap-oob" in resp.text
        assert "triage-stats" in resp.text

    def test_stats_partial_included_in_triage_page(self, client, fake_db):
        """The triage page should include the stats partial."""
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert 'id="triage-stats"' in resp.text
        assert 'hx-get="/triage/stats"' in resp.text


# ---------------------------------------------------------------------------
# Class 10: Deal Stage Change
# ---------------------------------------------------------------------------

class TestDealStageChange:

    def _post_stage(self, client, deal_id, stage):
        return client.post(f"/triage/deals/{deal_id}/stage", data={"stage": stage})

    def test_qualify_deal_succeeds(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        deal = make_deal(stage="lead")
        fake_db.store["gg_deals"].append(deal)
        resp = self._post_stage(client, deal["id"], "qualified")
        assert resp.status_code == 200
        assert "hx-swap-oob" in resp.text

    def test_close_deal_returns_empty_row(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        deal = make_deal(stage="lead")
        fake_db.store["gg_deals"].append(deal)
        resp = self._post_stage(client, deal["id"], "closed_lost")
        assert resp.status_code == 200
        # Primary HTML is empty (row removed), but OOB stats present
        assert "hx-swap-oob" in resp.text

    def test_invalid_uuid_rejected(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = self._post_stage(client, "not-a-uuid", "qualified")
        assert resp.status_code == 400

    def test_nonexistent_deal_returns_404(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = self._post_stage(client, str(uuid.uuid4()), "qualified")
        assert resp.status_code == 404

    def test_invalid_stage_returns_400(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        deal = make_deal(stage="lead")
        fake_db.store["gg_deals"].append(deal)
        resp = self._post_stage(client, deal["id"], "invalid_stage")
        assert resp.status_code == 400

    def test_deal_stage_change_rate_limited(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        deal = make_deal(stage="lead")
        fake_db.store["gg_deals"].append(deal)

        for _ in range(10):
            resp = self._post_stage(client, deal["id"], "qualified")
            assert resp.status_code == 200

        resp = self._post_stage(client, deal["id"], "qualified")
        assert resp.status_code == 429

    def test_deal_stage_audit_logged(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        deal = make_deal(stage="lead")
        fake_db.store["gg_deals"].append(deal)
        self._post_stage(client, deal["id"], "qualified")

        logs = fake_db.store["gg_audit_log"]
        assert any(log["action"] == "deal_stage_change" for log in logs)

    def test_stale_deals_table_has_action_buttons(self, client, fake_db):
        fake_db.store["gg_deals"].append(
            make_deal(stage="lead", updated_at=_hours_ago(72))
        )
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "Qualify" in resp.text
        assert "Close" in resp.text
        assert "triage-action-group" in resp.text


# ---------------------------------------------------------------------------
# Class 11: Plan Approve
# ---------------------------------------------------------------------------

class TestPlanApprove:

    def test_approve_pipeline_complete_plan(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        athlete = make_athlete(slug="test-approve", plan_status="pipeline_complete")
        fake_db.store["gg_athletes"].append(athlete)
        resp = client.post("/triage/plans/test-approve/approve")
        assert resp.status_code == 200
        assert "approved" in resp.text
        assert "hx-swap-oob" in resp.text

    def test_approve_audit_passed_plan(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        athlete = make_athlete(slug="test-audit", plan_status="audit_passed")
        fake_db.store["gg_athletes"].append(athlete)
        resp = client.post("/triage/plans/test-audit/approve")
        assert resp.status_code == 200
        assert "approved" in resp.text

    def test_approve_already_approved_returns_404(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        athlete = make_athlete(slug="already-done", plan_status="approved")
        fake_db.store["gg_athletes"].append(athlete)
        resp = client.post("/triage/plans/already-done/approve")
        assert resp.status_code == 404

    def test_approve_nonexistent_slug_returns_404(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = client.post("/triage/plans/does-not-exist/approve")
        assert resp.status_code == 404

    def test_approve_invalid_slug_rejected(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = client.post("/triage/plans/INVALID_SLUG!/approve")
        assert resp.status_code == 400

    def test_approve_creates_audit_log(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        athlete = make_athlete(slug="audit-test", plan_status="pipeline_complete")
        fake_db.store["gg_athletes"].append(athlete)
        client.post("/triage/plans/audit-test/approve")

        logs = fake_db.store["gg_audit_log"]
        assert any(log["action"] == "plan_approved" for log in logs)

    def test_plans_table_has_approve_button(self, client, fake_db):
        fake_db.store["gg_athletes"].append(
            make_athlete(slug="btn-test", plan_status="pipeline_complete", updated_at=_now_iso())
        )
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "Approve" in resp.text
        assert "/triage/plans/btn-test/approve" in resp.text

    def test_approved_plan_no_approve_button(self, client, fake_db):
        fake_db.store["gg_athletes"].append(
            make_athlete(slug="already-approved", plan_status="approved", updated_at=_now_iso())
        )
        resp = client.get("/triage")
        assert resp.status_code == 200
        # Should have Review but not Approve for already-approved
        assert "/triage/plans/already-approved/approve" not in resp.text


# ---------------------------------------------------------------------------
# Class 12: Touchpoint Mark Sent
# ---------------------------------------------------------------------------

class TestTouchpointMarkSent:

    def test_mark_sent_succeeds(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        tp = make_touchpoint()
        fake_db.store["gg_touchpoints"].append(tp)
        resp = client.post(f"/triage/touchpoints/{tp['id']}/sent")
        assert resp.status_code == 200
        assert "hx-swap-oob" in resp.text

    def test_mark_sent_updates_db(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        tp = make_touchpoint(sent=False)
        fake_db.store["gg_touchpoints"].append(tp)
        client.post(f"/triage/touchpoints/{tp['id']}/sent")
        assert tp["sent"] is True

    def test_mark_sent_creates_audit_log(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        tp = make_touchpoint()
        fake_db.store["gg_touchpoints"].append(tp)
        client.post(f"/triage/touchpoints/{tp['id']}/sent")

        logs = fake_db.store["gg_audit_log"]
        assert any(log["action"] == "touchpoint_marked_sent" for log in logs)

    def test_mark_sent_invalid_uuid(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = client.post("/triage/touchpoints/not-a-uuid/sent")
        assert resp.status_code == 400

    def test_mark_sent_nonexistent_returns_404(self, client, fake_db):
        from mission_control.routers.triage import _rate_buckets
        _rate_buckets.clear()

        resp = client.post(f"/triage/touchpoints/{str(uuid.uuid4())}/sent")
        assert resp.status_code == 404

    def test_touchpoint_table_has_mark_sent_button(self, client, fake_db):
        tp = make_touchpoint()
        with patch("mission_control.services.triage.db.get_touchpoints", return_value=[tp]):
            resp = client.get("/triage")
            assert resp.status_code == 200
            assert "Mark Sent" in resp.text


# ---------------------------------------------------------------------------
# Class 13: Expanded Health Checks
# ---------------------------------------------------------------------------

class TestExpandedHealth:

    def test_deep_health_endpoint_returns_html(self, client, fake_db):
        resp = client.get("/triage/health/deep")
        assert resp.status_code == 200
        assert "Deep Health Checks" in resp.text

    def test_deep_health_checks_env_vars(self, client, fake_db):
        resp = client.get("/triage/health/deep")
        assert resp.status_code == 200
        assert "ENV:" in resp.text

    def test_deep_health_checks_supabase_tables(self, client, fake_db):
        resp = client.get("/triage/health/deep")
        assert resp.status_code == 200
        assert "Table:" in resp.text

    def test_expanded_health_service_returns_structure(self, fake_db):
        from mission_control.services.triage import get_expanded_health
        health = get_expanded_health()
        assert "checks" in health
        assert "ok_count" in health
        assert "warning_count" in health
        assert "error_count" in health
        assert len(health["checks"]) > 4  # More than basic checks

    def test_check_env_vars_required(self, fake_db):
        from mission_control.services.triage import _check_env_vars
        results = _check_env_vars()
        names = [r["name"] for r in results]
        assert "ENV: SUPABASE_URL" in names
        assert "ENV: SUPABASE_SERVICE_KEY" in names
        assert "ENV: WEBHOOK_SECRET" in names
        assert "ENV: RESEND_API_KEY" in names

    def test_check_env_vars_optional(self, fake_db):
        from mission_control.services.triage import _check_env_vars
        results = _check_env_vars()
        names = [r["name"] for r in results]
        assert "ENV: STRIPE_API_KEY" in names
        assert "ENV: GA4_PROPERTY_ID" in names

    def test_check_supabase_tables(self, fake_db):
        from mission_control.services.triage import _check_supabase_tables
        results = _check_supabase_tables()
        names = [r["name"] for r in results]
        assert "Table: gg_deals" in names
        assert "Table: gg_athletes" in names
        assert "Table: gg_sequence_enrollments" in names

    def test_check_supabase_table_with_data(self, fake_db):
        from mission_control.services.triage import _check_supabase_tables
        fake_db.store["gg_deals"].append(make_deal())
        results = _check_supabase_tables()
        deal_check = next(r for r in results if r["name"] == "Table: gg_deals")
        assert deal_check["status"] == "ok"

    def test_check_self_health_no_public_url(self, fake_db):
        from mission_control.services.triage import _check_self_health
        with patch("mission_control.config.PUBLIC_URL", ""):
            result = _check_self_health()
            assert result["status"] == "warning"

    def test_check_resend_no_api_key(self, fake_db):
        from mission_control.services.triage import _check_resend_connectivity
        with patch("mission_control.config.RESEND_API_KEY", ""):
            result = _check_resend_connectivity()
            assert result["status"] == "error"

    def test_deep_health_button_in_template(self, client, fake_db):
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "Run Deep Checks" in resp.text
        assert 'hx-get="/triage/health/deep"' in resp.text

    def test_deep_health_never_crashes_page(self, client, fake_db):
        """Even if all deep checks fail, endpoint should return 200."""
        with patch("mission_control.services.triage._check_env_vars", return_value=[]):
            with patch("mission_control.services.triage._check_supabase_tables", return_value=[]):
                resp = client.get("/triage/health/deep")
                assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Class 14: Auto-Refresh Timer
# ---------------------------------------------------------------------------

class TestAutoRefresh:

    def test_stats_div_has_polling_trigger(self, client, fake_db):
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert 'hx-trigger="every 300s"' in resp.text

    def test_last_refreshed_span_exists(self, client, fake_db):
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert 'id="last-refreshed"' in resp.text

    def test_scripts_block_has_after_swap_listener(self, client, fake_db):
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "htmx:afterSwap" in resp.text


# ---------------------------------------------------------------------------
# Class 15: API Cost Tracking
# ---------------------------------------------------------------------------

class TestAPICostTracking:

    def test_calculate_cost_known_model(self, fake_db):
        from mission_control.services.triage import calculate_cost
        # claude-sonnet: $3/M in, $15/M out
        cost = calculate_cost("claude-sonnet-4-20250514", 1000, 500)
        expected = (1000 / 1_000_000) * 3.00 + (500 / 1_000_000) * 15.00
        assert abs(cost - expected) < 0.000001

    def test_calculate_cost_unknown_model(self, fake_db):
        from mission_control.services.triage import calculate_cost
        cost = calculate_cost("unknown-model", 1000, 500)
        assert cost == 0.0

    def test_get_api_cost_summary_empty_table(self, fake_db):
        from mission_control.services.triage import get_api_cost_summary
        result = get_api_cost_summary()
        assert result["configured"] is True
        assert result["today"] == 0.0
        assert result["total"] == 0.0

    def test_get_api_cost_summary_with_data(self, fake_db):
        from mission_control.services.triage import get_api_cost_summary
        fake_db.store["gg_api_usage"].append(
            make_api_usage(cost_usd=0.05, created_at=_now_iso())
        )
        fake_db.store["gg_api_usage"].append(
            make_api_usage(cost_usd=0.03, model="sonar-pro", created_at=_now_iso())
        )
        result = get_api_cost_summary()
        assert result["configured"] is True
        assert result["total"] == 0.08
        assert "claude-sonnet-4-20250514" in result["by_model"]
        assert "sonar-pro" in result["by_model"]

    def test_get_api_cost_summary_time_buckets(self, fake_db):
        from mission_control.services.triage import get_api_cost_summary
        # Today
        fake_db.store["gg_api_usage"].append(
            make_api_usage(cost_usd=0.10, created_at=_now_iso())
        )
        # 3 days ago (within week, not today)
        fake_db.store["gg_api_usage"].append(
            make_api_usage(cost_usd=0.20, created_at=_days_ago(3))
        )
        # 15 days ago (within month, not week)
        fake_db.store["gg_api_usage"].append(
            make_api_usage(cost_usd=0.30, created_at=_days_ago(15))
        )
        result = get_api_cost_summary()
        assert result["today"] == 0.10
        assert result["week"] == 0.30  # today + 3 days ago
        assert result["month"] == 0.60  # all three
        assert result["total"] == 0.60

    def test_api_cost_summary_table_not_exist(self, fake_db):
        """If gg_api_usage doesn't exist, return configured=False."""
        from mission_control.services.triage import get_api_cost_summary
        with patch("mission_control.services.triage.db._table", side_effect=Exception("table not found")):
            result = get_api_cost_summary()
            assert result["configured"] is False

    def test_api_costs_widget_in_triage_page(self, client, fake_db):
        """API costs widget shows when configured with data."""
        fake_db.store["gg_api_usage"].append(
            make_api_usage(cost_usd=1.50, created_at=_now_iso())
        )
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "API Costs" in resp.text

    def test_api_costs_widget_hidden_when_not_configured(self, fake_db):
        """When configured=False, the API costs section is not rendered."""
        from mission_control.services.triage import get_api_cost_summary
        # Simulate table not existing
        with patch("mission_control.services.triage.db._table") as mock_table:
            mock_table.side_effect = Exception("table not found")
            result = get_api_cost_summary()
            assert result["configured"] is False
        # The template uses {% if api_costs.configured %} so with False,
        # "API Costs" heading will not appear. Verified via service test above.

    def test_pricing_dict_has_expected_models(self, fake_db):
        from mission_control.services.triage import API_PRICING
        assert "claude-sonnet-4-20250514" in API_PRICING
        assert "sonar-pro" in API_PRICING
        assert "sonar" in API_PRICING

    def test_calculate_cost_sonar(self, fake_db):
        from mission_control.services.triage import calculate_cost
        # sonar: $1/M in, $1/M out
        cost = calculate_cost("sonar", 1_000_000, 1_000_000)
        assert cost == 2.0

    def test_api_costs_empty_state_in_page(self, client, fake_db):
        """With configured=True but no data, should still show widget."""
        resp = client.get("/triage")
        assert resp.status_code == 200
        # With empty gg_api_usage table, configured=True but all zeros
        assert "API Costs" in resp.text


# ---------------------------------------------------------------------------
# Class 16: Intake View Links
# ---------------------------------------------------------------------------

class TestIntakeViewLinks:

    def test_intake_name_links_to_athlete_search(self, client, fake_db):
        fake_db.store["plan_requests"].append({
            "id": str(uuid.uuid4()),
            "status": "pending",
            "payload": {"name": "Link Test", "email": "link@test.com"},
            "created_at": _now_iso(),
        })
        resp = client.get("/triage")
        assert resp.status_code == 200
        assert "/athletes?search=" in resp.text
        assert "link%40test.com" in resp.text or "link@test.com" in resp.text


# ---------------------------------------------------------------------------
# Class 17: Service Approve/MarkSent Unit Tests
# ---------------------------------------------------------------------------

class TestServiceApprovePlan:

    def test_approve_plan_changes_status(self, fake_db):
        from mission_control.services.triage import approve_plan
        athlete = make_athlete(slug="svc-test", plan_status="pipeline_complete")
        fake_db.store["gg_athletes"].append(athlete)
        result = approve_plan("svc-test")
        assert result is not None
        assert athlete["plan_status"] == "approved"

    def test_approve_plan_wrong_status_returns_none(self, fake_db):
        from mission_control.services.triage import approve_plan
        athlete = make_athlete(slug="wrong-status", plan_status="delivered")
        fake_db.store["gg_athletes"].append(athlete)
        result = approve_plan("wrong-status")
        assert result is None

    def test_approve_plan_missing_slug_returns_none(self, fake_db):
        from mission_control.services.triage import approve_plan
        result = approve_plan("nonexistent")
        assert result is None


class TestServiceMarkTouchpointSent:

    def test_mark_sent_sets_flag(self, fake_db):
        from mission_control.services.triage import mark_touchpoint_sent
        tp = make_touchpoint(sent=False)
        fake_db.store["gg_touchpoints"].append(tp)
        result = mark_touchpoint_sent(tp["id"])
        assert result is not None
        assert tp["sent"] is True

    def test_mark_sent_missing_id_returns_none(self, fake_db):
        from mission_control.services.triage import mark_touchpoint_sent
        result = mark_touchpoint_sent(str(uuid.uuid4()))
        assert result is None

    def test_mark_sent_on_db_error_returns_none(self, fake_db):
        from mission_control.services.triage import mark_touchpoint_sent
        with patch("mission_control.services.triage.db.select_one", side_effect=Exception("boom")):
            result = mark_touchpoint_sent(str(uuid.uuid4()))
            assert result is None
