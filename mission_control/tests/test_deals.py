"""Tests for deals service — CRUD, stage transitions, pipeline aggregation."""

import uuid
from datetime import datetime, timezone

import pytest

from mission_control.tests.conftest import make_deal


class TestCreateDeal:
    def test_creates_deal_at_lead_stage(self, fake_db):
        from mission_control.services.deals import create_deal

        deal = create_deal(
            email="new@example.com",
            name="New Lead",
            race_name="Unbound 200",
            source="quiz",
        )
        assert deal["contact_email"] == "new@example.com"
        assert deal["stage"] == "lead"
        assert deal["value"] == 249.00

    def test_creates_deal_with_custom_value(self, fake_db):
        from mission_control.services.deals import create_deal

        deal = create_deal(email="vip@example.com", value=499.00)
        assert deal["value"] == 499.00

    def test_logs_audit_action(self, fake_db):
        from mission_control.services.deals import create_deal

        create_deal(email="logged@example.com", name="Logged Lead")
        logs = fake_db.store["gg_audit_log"]
        assert any(log["action"] == "deal_created" for log in logs)


class TestMoveStage:
    def test_valid_stage_transition(self, fake_db):
        from mission_control.services.deals import move_stage

        deal = make_deal()
        fake_db.store["gg_deals"].append(deal)

        result = move_stage(deal["id"], "qualified")
        assert result is not None
        assert deal["stage"] == "qualified"

    def test_closed_won_sets_closed_at(self, fake_db):
        from mission_control.services.deals import move_stage

        deal = make_deal(stage="proposal_sent")
        fake_db.store["gg_deals"].append(deal)

        move_stage(deal["id"], "closed_won")
        assert deal["stage"] == "closed_won"
        assert deal["closed_at"] is not None

    def test_closed_lost_sets_closed_at(self, fake_db):
        from mission_control.services.deals import move_stage

        deal = make_deal(stage="qualified")
        fake_db.store["gg_deals"].append(deal)

        move_stage(deal["id"], "closed_lost")
        assert deal["closed_at"] is not None

    def test_invalid_stage_returns_none(self, fake_db):
        from mission_control.services.deals import move_stage

        deal = make_deal()
        fake_db.store["gg_deals"].append(deal)

        result = move_stage(deal["id"], "bogus_stage")
        assert result is None

    def test_logs_stage_change(self, fake_db):
        from mission_control.services.deals import move_stage

        deal = make_deal()
        fake_db.store["gg_deals"].append(deal)

        move_stage(deal["id"], "qualified")
        logs = fake_db.store["gg_audit_log"]
        assert any(
            log["action"] == "deal_stage_change" and "qualified" in log.get("details", "")
            for log in logs
        )


class TestPipelineSummary:
    def test_groups_by_stage(self, fake_db):
        from mission_control.services.deals import pipeline_summary

        fake_db.store["gg_deals"].extend([
            make_deal(stage="lead", value=249.00),
            make_deal(stage="lead", value=249.00, contact_email="b@test.com"),
            make_deal(stage="qualified", value=499.00, contact_email="c@test.com"),
            make_deal(stage="closed_won", value=249.00, contact_email="d@test.com"),
        ])

        summary = pipeline_summary()
        assert summary["lead"]["count"] == 2
        assert summary["lead"]["value"] == 498.00
        assert summary["qualified"]["count"] == 1
        assert summary["qualified"]["value"] == 499.00
        assert summary["closed_won"]["count"] == 1
        assert summary["proposal_sent"]["count"] == 0

    def test_empty_pipeline(self, fake_db):
        from mission_control.services.deals import pipeline_summary

        summary = pipeline_summary()
        for stage in ["lead", "qualified", "proposal_sent", "closed_won", "closed_lost"]:
            assert summary[stage]["count"] == 0
            assert summary[stage]["value"] == 0


class TestGetDeals:
    def test_filters_by_stage(self, fake_db):
        from mission_control.services.deals import get_deals

        fake_db.store["gg_deals"].extend([
            make_deal(stage="lead"),
            make_deal(stage="qualified", contact_email="q@test.com"),
        ])

        leads = get_deals(stage="lead")
        assert len(leads) == 1
        assert leads[0]["stage"] == "lead"

    def test_returns_all_without_filter(self, fake_db):
        from mission_control.services.deals import get_deals

        fake_db.store["gg_deals"].extend([
            make_deal(stage="lead"),
            make_deal(stage="qualified", contact_email="q@test.com"),
        ])

        all_deals = get_deals()
        assert len(all_deals) == 2


class TestUpdateDeal:
    def test_updates_fields(self, fake_db):
        from mission_control.services.deals import update_deal

        deal = make_deal(notes="old notes")
        fake_db.store["gg_deals"].append(deal)

        update_deal(deal["id"], {"notes": "new notes"})
        assert deal["notes"] == "new notes"
        assert deal["updated_at"] is not None


class TestLinkAthlete:
    def test_links_athlete_to_deal(self, fake_db):
        from mission_control.services.deals import link_athlete

        deal = make_deal()
        fake_db.store["gg_deals"].append(deal)
        athlete_id = str(uuid.uuid4())

        link_athlete(deal["id"], athlete_id)
        assert deal["athlete_id"] == athlete_id
