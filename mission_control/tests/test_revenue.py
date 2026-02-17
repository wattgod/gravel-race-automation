"""Tests for revenue service — payments, monthly tracking, targets."""

import uuid
from datetime import datetime, timezone

import pytest

from mission_control.tests.conftest import make_deal, make_payment


class TestRecordPayment:
    def test_records_payment_for_existing_deal(self, fake_db):
        from mission_control.services.revenue import record_payment

        deal = make_deal()
        fake_db.store["gg_deals"].append(deal)

        payment = record_payment(deal["id"], amount=249.00, source="manual")
        assert payment["amount"] == 249.00
        assert payment["deal_id"] == deal["id"]
        assert payment["source"] == "manual"

    def test_returns_empty_for_nonexistent_deal(self, fake_db):
        from mission_control.services.revenue import record_payment

        result = record_payment("nonexistent-id", amount=100.00)
        assert result == {}

    def test_logs_audit_action(self, fake_db):
        from mission_control.services.revenue import record_payment

        deal = make_deal()
        fake_db.store["gg_deals"].append(deal)

        record_payment(deal["id"], amount=249.00)
        logs = fake_db.store["gg_audit_log"]
        assert any(log["action"] == "payment_recorded" for log in logs)


class TestMonthlyRevenue:
    def test_sums_payments_in_month(self, fake_db):
        from mission_control.services.revenue import monthly_revenue

        fake_db.store["gg_payments"].extend([
            make_payment(amount=249.00, paid_at="2026-02-05T10:00:00Z"),
            make_payment(amount=249.00, paid_at="2026-02-15T10:00:00Z"),
            make_payment(amount=499.00, paid_at="2026-01-20T10:00:00Z"),  # wrong month
        ])

        result = monthly_revenue(2026, 2)
        assert result == 498.00

    def test_returns_zero_for_empty_month(self, fake_db):
        from mission_control.services.revenue import monthly_revenue

        result = monthly_revenue(2026, 3)
        assert result == 0.0

    def test_december_boundary(self, fake_db):
        from mission_control.services.revenue import monthly_revenue

        fake_db.store["gg_payments"].extend([
            make_payment(amount=100.00, paid_at="2025-12-15T10:00:00Z"),
            make_payment(amount=200.00, paid_at="2026-01-01T00:00:00Z"),  # next year
        ])

        result = monthly_revenue(2025, 12)
        assert result == 100.00


class TestRevenueVsTarget:
    def test_calculates_percentage(self, fake_db):
        from mission_control.services.revenue import revenue_vs_target

        # Add payment for current month
        now = datetime.now(timezone.utc)
        paid_at = now.isoformat()
        fake_db.store["gg_payments"].append(
            make_payment(amount=5000.00, paid_at=paid_at)
        )

        result = revenue_vs_target(target=10000.0)
        assert result["actual"] == 5000.00
        assert result["target"] == 10000.0
        assert result["pct"] == 50.0
        assert result["remaining"] == 5000.0

    def test_zero_target_no_division_error(self, fake_db):
        from mission_control.services.revenue import revenue_vs_target

        result = revenue_vs_target(target=0)
        assert result["pct"] == 0


class TestMonthlyTrend:
    def test_returns_correct_number_of_months(self, fake_db):
        from mission_control.services.revenue import monthly_trend

        trend = monthly_trend(months=6)
        assert len(trend) == 6

    def test_months_are_ordered_chronologically(self, fake_db):
        from mission_control.services.revenue import monthly_trend

        trend = monthly_trend(months=3)
        months = [t["month"] for t in trend]
        assert months == sorted(months)


class TestPlansSoldThisMonth:
    def test_counts_closed_won_deals(self, fake_db):
        from mission_control.services.revenue import plans_sold_this_month

        now = datetime.now(timezone.utc)
        this_month = f"{now.year}-{now.month:02d}-10T10:00:00Z"

        fake_db.store["gg_deals"].extend([
            make_deal(stage="closed_won", closed_at=this_month),
            make_deal(stage="closed_won", closed_at=this_month, contact_email="b@t.com"),
            make_deal(stage="lead", contact_email="c@t.com"),  # not closed
        ])

        count = plans_sold_this_month()
        assert count == 2

    def test_zero_when_no_sales(self, fake_db):
        from mission_control.services.revenue import plans_sold_this_month

        assert plans_sold_this_month() == 0


class TestTotalOpenPipelineValue:
    def test_sums_non_closed_deals(self, fake_db):
        from mission_control.services.revenue import total_open_pipeline_value

        fake_db.store["gg_deals"].extend([
            make_deal(stage="lead", value=249.00),
            make_deal(stage="qualified", value=499.00, contact_email="b@t.com"),
            make_deal(stage="closed_won", value=249.00, contact_email="c@t.com"),
            make_deal(stage="closed_lost", value=249.00, contact_email="d@t.com"),
        ])

        total = total_open_pipeline_value()
        assert total == 748.00  # lead + qualified only
