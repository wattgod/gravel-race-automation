"""Tests for decision-grade provider revenue ingestion."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from mission_control import supabase_client
from mission_control.services import provider_ingestion as ingestion


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _fixture_dir(tmp_path: Path, *, duplicate_payment: bool = False) -> Path:
    upstream = "a" * 64
    payment = {
        "source_row": "1",
        "customer_key": "C001",
        "purchase_date": "2026-08-27",
        "status": "succeeded",
        "athlete_charged_usd": "299.00",
        "amount_received_usd": "290.03",
        "fee_refund_delta_usd": "8.97",
        "product": "Coaching Premium 2024",
        "in_operating_system_period": "true",
        "source_file_sha256": upstream,
        "evidence_grade": "A",
        "boundary": "Provider row has no exported payment transaction ID",
    }
    payments = [payment]
    if duplicate_payment:
        payments.append({**payment, "source_row": "2"})
    _write(tmp_path / ingestion.FILES["coaching_payments"], payments)
    _write(tmp_path / ingestion.FILES["coaching_payouts"], [{
        "source_row": "1",
        "payout_key": "P001",
        "provider_id_sha256": "b" * 64,
        "created_utc": "2026-08-27T00:40:00+00:00",
        "arrival_date_utc": "2026-08-27",
        "amount_usd": "290.03",
        "currency": "usd",
        "livemode": "true",
        "status": "paid",
        "type": "bank_account",
        "method": "standard",
        "in_operating_system_period": "true",
        "source_file_sha256": "c" * 64,
        "evidence_grade": "A",
        "boundary": "Bank destination omitted",
    }])
    _write(tmp_path / ingestion.FILES["coaching_customers"], [{
        "customer_key": "C001",
        "first_success_date": "2026-08-27",
        "last_success_date": "2026-08-27",
        "current_status": "paid",
        "current_product": "Coaching Premium 2024",
        "current_last_payment_date": "2026-08-27",
        "current_next_payment_date": "2026-09-27",
        "payment_rows": "1",
        "succeeded_rows": "1",
        "refunded_rows": "0",
        "lifetime_athlete_charged_usd": "299.00",
        "lifetime_amount_received_usd": "290.03",
        "period_athlete_charged_usd": "299.00",
        "period_amount_received_usd": "290.03",
        "confirmed_cancel_events": "0",
        "latest_confirmed_cancel_date": "",
        "pause_events": "0",
        "latest_pause_date": "",
        "successful_payments_after_latest_cancel": "0",
        "lifecycle_class": "new_active_logo",
        "evidence_grade": "A/B",
        "boundary": "Snapshot-local customer key",
    }])
    _write(tmp_path / ingestion.FILES["coaching_monthly"], [{
        "month": "2026-08",
        "payment_rows": "1",
        "succeeded_rows": "1",
        "refunded_rows": "0",
        "distinct_paying_customers": "1",
        "new_logo_starts": "1",
        "inferred_reactivations_or_migrations": "0",
        "confirmed_terminal_churns": "0",
        "athlete_charged_usd": "299.00",
        "amount_received_usd": "290.03",
        "evidence_grade": "A/B",
        "boundary": "No churn denominator",
    }])
    _write(tmp_path / ingestion.FILES["marketplace_monthly"], [{
        "sale_month": "2026-08",
        "sale_notice_count": "1",
        "gross_list_price_usd": "100.00",
        "author_share_rate": "0.70",
        "expected_author_royalty_usd": "70.00",
        "paypal_payout_date": "",
        "paypal_payout_usd": "0.00",
        "settled_variance_usd": "",
        "pending_royalty_usd": "70.00",
        "settlement_status": "pending",
        "paypal_message_sha256": "",
        "evidence_grade": "B",
        "boundary": "Aggregate only",
    }])
    return tmp_path


def test_build_bundle_preserves_financial_and_identity_boundaries(tmp_path):
    bundle = ingestion.build_trainingpeaks_bundle(
        _fixture_dir(tmp_path),
        observed_at="2026-08-27T18:00:00+00:00",
        enforce_2026_08_27_controls=False,
    )

    payment = bundle.payments[0]
    assert payment["amount"] == "290.03"
    assert payment["gross_amount"] == "299.00"
    assert payment["provider_adjustment_amount"] == "8.97"
    assert payment["provider_record_key_kind"] == "synthetic_normalized_fingerprint_v1"
    assert payment["stripe_payment_id"] is None
    assert set(payment) >= {"source_payload_sha256", "source_record_sha256", "evidence_grade"}

    payout = bundle.payouts[0]
    assert payout["provider_metadata"] == {
        "in_operating_system_period": True,
        "source_row": 1,
    }

    customer = bundle.customer_snapshots[0]
    assert customer["customer_key"] == "C001"
    assert customer["customer_key_kind"] == "snapshot_local"
    assert not ({"name", "email", "provider_customer_id"} & set(customer))
    assert bundle.summary()["canonical_rows"] == {
        "gg_payments": 1,
        "gg_provider_payouts": 1,
        "gg_provider_customer_snapshots": 1,
        "gg_provider_monthly_controls": 2,
    }


def test_identical_payment_rows_receive_distinct_deterministic_keys(tmp_path):
    source = _fixture_dir(tmp_path, duplicate_payment=True)
    first = ingestion.build_trainingpeaks_bundle(
        source, observed_at="2026-08-27T18:00:00+00:00", enforce_2026_08_27_controls=False
    )
    second = ingestion.build_trainingpeaks_bundle(
        source, observed_at="2026-08-27T19:00:00+00:00", enforce_2026_08_27_controls=False
    )
    first_keys = [row["provider_record_key"] for row in first.payments]
    second_keys = [row["provider_record_key"] for row in second.payments]
    assert len(set(first_keys)) == 2
    assert first_keys == second_keys


def test_pinned_control_profile_fails_closed_on_fixture(tmp_path):
    with pytest.raises(ingestion.ProviderIngestionError, match="payment_rows"):
        ingestion.build_trainingpeaks_bundle(_fixture_dir(tmp_path))


def test_payment_adjustment_must_reconcile(tmp_path):
    source = _fixture_dir(tmp_path)
    path = source / ingestion.FILES["coaching_payments"]
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["fee_refund_delta_usd"] = "0.00"
    _write(path, rows)

    with pytest.raises(ingestion.ProviderIngestionError, match="gross-minus-net"):
        ingestion.build_trainingpeaks_bundle(
            source, enforce_2026_08_27_controls=False
        )


def test_pii_bearing_columns_fail_closed(tmp_path):
    source = _fixture_dir(tmp_path)
    path = source / ingestion.FILES["coaching_customers"]
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["email"] = "forbidden@example.com"
    _write(path, rows)

    with pytest.raises(ingestion.ProviderIngestionError, match="PII-bearing"):
        ingestion.build_trainingpeaks_bundle(
            source, enforce_2026_08_27_controls=False
        )


def test_observation_timestamp_requires_timezone(tmp_path):
    with pytest.raises(ingestion.ProviderIngestionError, match="timezone"):
        ingestion.build_trainingpeaks_bundle(
            _fixture_dir(tmp_path),
            observed_at="2026-08-27T18:00:00",
            enforce_2026_08_27_controls=False,
        )


def test_apply_bundle_uses_idempotent_conflict_keys(tmp_path, monkeypatch):
    bundle = ingestion.build_trainingpeaks_bundle(
        _fixture_dir(tmp_path),
        observed_at="2026-08-27T18:00:00+00:00",
        enforce_2026_08_27_controls=False,
    )
    calls: list[tuple[str, str, int]] = []

    class FakeDb:
        @staticmethod
        def upsert(table, row, on_conflict=""):
            calls.append((table, on_conflict, 1))
            return {**row, "id": f"batch-{len(calls)}"}

        @staticmethod
        def select_one(*_args, **_kwargs):
            raise AssertionError("upsert returned an id")

        @staticmethod
        def upsert_many(table, rows, on_conflict="", batch_size=500):
            calls.append((table, on_conflict, len(rows)))
            assert all("import_batch_id" in row for row in rows)
            return rows

    monkeypatch.setattr(ingestion, "db", FakeDb)
    receipt = ingestion.apply_bundle(bundle, batch_size=2)
    assert receipt["status"] == "APPLIED"
    assert receipt["attempted_rows"]["gg_payments"] == 1
    assert ("gg_payments", "provider,provider_account,provider_record_key", 1) in calls
    assert (
        "gg_provider_monthly_controls",
        "provider,provider_account,source_kind,control_month",
        2,
    ) in calls


def test_upsert_many_uses_bounded_batches_and_conflict_key(monkeypatch):
    calls: list[tuple[str, list[dict], str | None]] = []

    class Result:
        def __init__(self, data):
            self.data = data

    class Query:
        def __init__(self, table):
            self.table = table
            self.rows = []
            self.conflict = None

        def upsert(self, rows, on_conflict=None):
            self.rows = rows
            self.conflict = on_conflict
            return self

        def execute(self):
            calls.append((self.table, self.rows, self.conflict))
            return Result(self.rows)

    monkeypatch.setattr(supabase_client, "_table", Query)
    rows = [{"id": value} for value in range(5)]
    stored = supabase_client.upsert_many(
        "gg_payments", rows, on_conflict="provider,provider_record_key", batch_size=2
    )

    assert [len(batch) for _, batch, _ in calls] == [2, 2, 1]
    assert all(conflict == "provider,provider_record_key" for _, _, conflict in calls)
    assert stored == rows


def test_upsert_many_rejects_invalid_batch_size():
    with pytest.raises(ValueError, match="at least 1"):
        supabase_client.upsert_many("gg_payments", [{}], batch_size=0)
