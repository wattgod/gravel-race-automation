"""Tests for privacy-safe, idempotent Stripe provider ingestion."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mission_control.services import stripe_provider_ingestion as ingestion


def _key(character: str) -> str:
    return "srk_" + character * 64


def _receipt() -> dict:
    charge_key = _key("1")
    refund_key = _key("2")
    payout_key = _key("3")
    charge_balance_key = _key("4")
    refund_balance_key = _key("5")
    payout_balance_key = _key("6")
    product_key = _key("7")
    price_key = _key("8")
    intent_key = _key("9")
    account_key = _key("a")
    customer_key = _key("b")
    session_key = _key("c")
    invoice_key = _key("d")
    subscription_key = _key("e")
    created = "2026-08-27T18:00:00+00:00"
    rows = {
        "products": [
            {
                "record_key": product_key,
                "created_at": created,
                "name": "Custom Training Plan",
                "offer_family": "training_plan",
                "active": True,
                "livemode": True,
            }
        ],
        "prices": [
            {
                "record_key": price_key,
                "product_record_key": product_key,
                "created_at": created,
                "currency": "usd",
                "unit_amount_cents": 10000,
                "recurring_interval": "",
                "recurring_interval_count": 0,
                "offer_family": "training_plan",
                "active": True,
                "livemode": True,
            }
        ],
        "checkout_sessions": [
            {
                "record_key": session_key,
                "payment_intent_record_key": intent_key,
                "subscription_record_key": "",
                "customer_record_key": customer_key,
                "created_at": created,
                "currency": "usd",
                "amount_total_cents": 10000,
                "amount_discount_cents": 0,
                "amount_tax_cents": 0,
                "status": "complete",
                "payment_status": "paid",
                "mode": "payment",
                "offer_family": "training_plan",
                "brand": "gravelgod",
                "synthetic": False,
                "livemode": True,
            }
        ],
        "invoices": [
            {
                "record_key": invoice_key,
                "subscription_record_key": subscription_key,
                "customer_record_key": customer_key,
                "created_at": created,
                "currency": "usd",
                "status": "paid",
                "amount_due_cents": 10000,
                "amount_paid_cents": 10000,
                "amount_remaining_cents": 0,
                "offer_family": "training_plan",
                "brand": "gravelgod",
                "line_items": [
                    {
                        "price_record_key": price_key,
                        "product_record_key": product_key,
                        "merchant_product_name": "Custom Training Plan",
                        "offer_family": "training_plan",
                        "currency": "usd",
                        "amount_cents": 10000,
                        "quantity": 1,
                        "period_start_at": created,
                        "period_end_at": created,
                    }
                ],
                "line_items_complete": True,
                "livemode": True,
            }
        ],
        "charges": [
            {
                "record_key": charge_key,
                "payment_intent_record_key": intent_key,
                "invoice_record_key": invoice_key,
                "customer_record_key": customer_key,
                "balance_transaction_record_key": charge_balance_key,
                "created_at": created,
                "currency": "usd",
                "status": "succeeded",
                "paid": True,
                "captured": True,
                "disputed": False,
                "gross_cents": 10000,
                "refunded_cents": 1000,
                "gross_less_refunds_cents": 9000,
                "offer_family": "training_plan",
                "brand": "gravelgod",
                "livemode": True,
            }
        ],
        "refunds": [
            {
                "record_key": refund_key,
                "charge_record_key": charge_key,
                "payment_intent_record_key": intent_key,
                "balance_transaction_record_key": refund_balance_key,
                "created_at": created,
                "currency": "usd",
                "status": "succeeded",
                "amount_cents": 1000,
            }
        ],
        "balance_transactions": [
            {
                "record_key": charge_balance_key,
                "source_record_key": charge_key,
                "created_at": created,
                "available_at": created,
                "currency": "usd",
                "type": "charge",
                "reporting_category": "charge",
                "status": "available",
                "amount_cents": 10000,
                "fee_cents": 300,
                "net_cents": 9700,
            },
            {
                "record_key": refund_balance_key,
                "source_record_key": refund_key,
                "created_at": created,
                "available_at": created,
                "currency": "usd",
                "type": "refund",
                "reporting_category": "refund",
                "status": "available",
                "amount_cents": -1000,
                "fee_cents": 0,
                "net_cents": -1000,
            },
            {
                "record_key": payout_balance_key,
                "source_record_key": payout_key,
                "created_at": created,
                "available_at": created,
                "currency": "usd",
                "type": "payout",
                "reporting_category": "payout",
                "status": "available",
                "amount_cents": -8700,
                "fee_cents": 0,
                "net_cents": -8700,
            },
        ],
        "payouts": [
            {
                "record_key": payout_key,
                "balance_transaction_record_key": payout_balance_key,
                "created_at": created,
                "arrival_at": created,
                "currency": "usd",
                "status": "paid",
                "amount_cents": 8700,
                "automatic": True,
            }
        ],
    }
    successful = rows["charges"]
    refunds = rows["refunds"]
    payouts = rows["payouts"]
    invoices = rows["invoices"]
    return {
        "schema": ingestion.SCHEMA,
        "generated_at": created,
        "period": {
            "start_date": "2026-08-27",
            "end_date_inclusive": "2026-08-27",
            "timezone": "UTC",
        },
        "provider": {
            "name": "stripe",
            "account_record_key": account_key,
            "charges_enabled": True,
            "payouts_enabled": True,
        },
        "privacy": {
            "projection": "financial_and_offer_fields_only",
            "record_keys": "hmac_sha256_using_server_secret",
            "included_merchant_fields": ["product_name"],
            "excluded": ["provider_ids", "names", "emails", "phones", "addresses"],
        },
        "controls": {
            "successful_charges": ingestion._totals(successful, "gross_cents"),
            "succeeded_refunds": ingestion._totals(refunds, "amount_cents"),
            "paid_payouts": ingestion._totals(payouts, "amount_cents"),
            "paid_invoices": ingestion._totals(invoices, "amount_paid_cents"),
            "balance_activity_by_category": ingestion._balance_totals(
                rows["balance_transactions"]
            ),
            "current_balance": {"usd": {"available_cents": 0, "pending_cents": 0}},
        },
        "rows": rows,
        "boundaries": ["Bank matching is outside this receipt."],
        "side_effects": "read_only_provider_list_and_retrieve_calls; no mutation",
    }


def _write(tmp_path: Path, receipt: dict | None = None) -> Path:
    path = tmp_path / "stripe-reconciliation.json"
    path.write_text(json.dumps(receipt or _receipt(), sort_keys=True), encoding="utf-8")
    return path


def test_build_bundle_preserves_settlement_and_privacy_boundaries(tmp_path):
    bundle = ingestion.build_stripe_bundle(
        _write(tmp_path), enforce_2026_08_27_controls=False
    )
    assert bundle.batch["provider_account"].startswith("srk_")
    assert bundle.batch["row_count"] == 10
    assert len(bundle.payments) == 2
    charge, refund = bundle.payments
    assert charge["gross_amount"] == "100.00"
    assert charge["provider_adjustment_amount"] == "3.00"
    assert charge["net_amount"] == "97.00"
    assert charge["product_name"] == "Custom Training Plan"
    assert refund["amount"] == "-10.00"
    assert refund["status"] == "refunded"
    assert len(bundle.payouts) == 1
    assert len(bundle.balance_transactions) == 3
    assert len(bundle.monthly_controls) == 1
    assert bundle.summary()["canonical_rows"] == {
        "gg_payments": 2,
        "gg_provider_payouts": 1,
        "gg_provider_balance_transactions": 3,
        "gg_provider_monthly_controls": 1,
    }


def test_balance_source_hmac_must_join(tmp_path):
    receipt = _receipt()
    receipt["rows"]["balance_transactions"][0]["source_record_key"] = _key("f")
    with pytest.raises(
        ingestion.ProviderIngestionError, match="source HMAC does not join"
    ):
        ingestion.build_stripe_bundle(
            _write(tmp_path, receipt), enforce_2026_08_27_controls=False
        )


def test_recomputed_controls_fail_closed(tmp_path):
    receipt = _receipt()
    receipt["controls"]["successful_charges"]["usd"]["amount_cents"] = 1
    with pytest.raises(ingestion.ProviderIngestionError, match="does not reconcile"):
        ingestion.build_stripe_bundle(
            _write(tmp_path, receipt), enforce_2026_08_27_controls=False
        )


def test_pii_and_raw_provider_ids_fail_closed(tmp_path):
    for field, value in (("email", "private@example.com"), ("note", "ch_private")):
        receipt = _receipt()
        receipt["rows"]["charges"][0][field] = value
        with pytest.raises(ingestion.ProviderIngestionError):
            ingestion.build_stripe_bundle(
                _write(tmp_path, receipt), enforce_2026_08_27_controls=False
            )


def test_pinned_controls_reject_fixture(tmp_path):
    with pytest.raises(ingestion.ProviderIngestionError, match="Pinned Stripe control"):
        ingestion.build_stripe_bundle(_write(tmp_path))


def test_apply_is_idempotent_and_readback_verified(tmp_path, monkeypatch):
    bundle = ingestion.build_stripe_bundle(
        _write(tmp_path), enforce_2026_08_27_controls=False
    )
    tables: dict[str, list[dict]] = {}
    calls: list[tuple[str, str, int]] = []

    class FakeDb:
        @staticmethod
        def upsert(table, row, on_conflict=""):
            calls.append((table, on_conflict, 1))
            return {**row, "id": "batch-1"}

        @staticmethod
        def select_one(*_args, **_kwargs):
            raise AssertionError("upsert returned an id")

        @staticmethod
        def upsert_many(table, rows, on_conflict="", batch_size=500):
            calls.append((table, on_conflict, len(rows)))
            tables[table] = copy.deepcopy(rows)
            return rows

        @staticmethod
        def select(table, match=None):
            return [
                row
                for row in tables.get(table, [])
                if not match
                or all(row.get(key) == value for key, value in match.items())
            ]

    monkeypatch.setattr(ingestion, "db", FakeDb)
    first = ingestion.apply_stripe_bundle(bundle, batch_size=2)
    second = ingestion.apply_stripe_bundle(bundle, batch_size=2)
    assert first["status"] == second["status"] == "APPLIED_AND_VERIFIED"
    assert first["readback"]["rows"] == {
        "gg_payments": 2,
        "gg_provider_payouts": 1,
        "gg_provider_balance_transactions": 3,
        "gg_provider_monthly_controls": 1,
    }
    assert (
        "gg_provider_balance_transactions",
        "provider,provider_account,provider_record_key",
        3,
    ) in calls
