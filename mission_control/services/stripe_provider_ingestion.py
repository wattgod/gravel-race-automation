"""Fail-closed ingestion of the privacy-safe standalone Stripe receipt."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from mission_control.services.provider_ingestion import ProviderIngestionError

db: Any | None = None

SCHEMA = "stripe_revenue_reconciliation/v1"
PROVIDER = "stripe"
SOURCE_KIND = "reconciliation_receipt"
RECORD_KEY_KIND = "hmac_sha256_provider_id_v1"
MONTHLY_SOURCE_KIND = "stripe_reconciliation"
RECORD_KEY_RE = re.compile(r"^srk_[0-9a-f]{64}$")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
RAW_STRIPE_ID_RE = re.compile(
    r"\b(?:acct|cs|pi|cus|ch|re|po|txn|sub|in|prod|price)_[A-Za-z0-9_]+\b"
)

FORBIDDEN_KEYS = {
    "email",
    "phone",
    "address",
    "billing_details",
    "shipping",
    "payment_method",
    "payment_method_details",
    "bank_account",
    "bank_destination",
    "destination",
    "receipt_url",
    "customer_name",
    "athlete_name",
    "contact_name",
    "first_name",
    "last_name",
    "description",
    "price_nickname",
}

REQUIRED_INVOICE_LINE_FIELDS = {
    "price_record_key",
    "product_record_key",
    "merchant_product_name",
    "offer_family",
    "currency",
    "amount_cents",
    "quantity",
    "period_start_at",
    "period_end_at",
}

REQUIRED_ROW_FIELDS = {
    "products": {
        "record_key",
        "created_at",
        "name",
        "offer_family",
        "active",
        "livemode",
    },
    "prices": {
        "record_key",
        "product_record_key",
        "created_at",
        "currency",
        "unit_amount_cents",
        "recurring_interval",
        "recurring_interval_count",
        "offer_family",
        "active",
        "livemode",
    },
    "checkout_sessions": {
        "record_key",
        "payment_intent_record_key",
        "subscription_record_key",
        "customer_record_key",
        "created_at",
        "currency",
        "amount_total_cents",
        "amount_discount_cents",
        "amount_tax_cents",
        "status",
        "payment_status",
        "mode",
        "offer_family",
        "brand",
        "synthetic",
        "livemode",
    },
    "invoices": {
        "record_key",
        "subscription_record_key",
        "customer_record_key",
        "created_at",
        "currency",
        "status",
        "amount_due_cents",
        "amount_paid_cents",
        "amount_remaining_cents",
        "offer_family",
        "brand",
        "line_items",
        "line_items_complete",
        "livemode",
    },
    "charges": {
        "record_key",
        "payment_intent_record_key",
        "invoice_record_key",
        "customer_record_key",
        "balance_transaction_record_key",
        "created_at",
        "currency",
        "status",
        "paid",
        "captured",
        "disputed",
        "gross_cents",
        "refunded_cents",
        "gross_less_refunds_cents",
        "offer_family",
        "brand",
        "livemode",
    },
    "refunds": {
        "record_key",
        "charge_record_key",
        "payment_intent_record_key",
        "balance_transaction_record_key",
        "created_at",
        "currency",
        "status",
        "amount_cents",
    },
    "balance_transactions": {
        "record_key",
        "source_record_key",
        "created_at",
        "available_at",
        "currency",
        "type",
        "reporting_category",
        "status",
        "amount_cents",
        "fee_cents",
        "net_cents",
    },
    "payouts": {
        "record_key",
        "balance_transaction_record_key",
        "created_at",
        "arrival_at",
        "currency",
        "status",
        "amount_cents",
        "automatic",
    },
}

EXPECTED_2026_08_27 = {
    "period": {
        "start_date": "2025-08-27",
        "end_date_inclusive": "2026-08-27",
        "timezone": "UTC",
    },
    "raw_rows": {
        "products": 17,
        "prices": 52,
        "checkout_sessions": 1101,
        "invoices": 89,
        "charges": 121,
        "refunds": 1,
        "balance_transactions": 234,
        "payouts": 70,
    },
    "successful_charges": {
        "eur": {"count": 1, "amount_cents": 500},
        "usd": {"count": 90, "amount_cents": 226800},
    },
    "succeeded_refunds": {"usd": {"count": 1, "amount_cents": 130}},
    "paid_payouts": {"usd": {"count": 70, "amount_cents": 207132}},
    "paid_invoices": {
        "eur": {"count": 1, "amount_cents": 500},
        "usd": {"count": 82, "amount_cents": 94500},
    },
    "balance_activity_by_category": {
        "usd": {
            "charge": {
                "count": 91,
                "amount_cents": 227370,
                "fee_cents": 19416,
                "net_cents": 207954,
            },
            "fee": {
                "count": 72,
                "amount_cents": -680,
                "fee_cents": 12,
                "net_cents": -692,
            },
            "payout": {
                "count": 70,
                "amount_cents": -207132,
                "fee_cents": 0,
                "net_cents": -207132,
            },
            "refund": {
                "count": 1,
                "amount_cents": -130,
                "fee_cents": 0,
                "net_cents": -130,
            },
        },
    },
    "current_balance": {"usd": {"available_cents": 0, "pending_cents": 0}},
    "checkout_sessions": {
        "synthetic_expired_unpaid": 876,
        "non_synthetic_expired_unpaid": 217,
        "non_synthetic_paid": 8,
    },
    "offer_allocation": {
        "consulting": {"usd": {"count": 2, "amount_cents": 30000}},
        "training_plan": {"usd": {"count": 6, "amount_cents": 102300}},
        "unknown": {
            "eur": {"count": 1, "amount_cents": 500},
            "usd": {"count": 82, "amount_cents": 94500},
        },
    },
    "invoice_line_items_complete": 89,
}


@dataclass
class StripeImportBundle:
    observed_at: str
    batch: dict[str, Any]
    payments: list[dict[str, Any]]
    payouts: list[dict[str, Any]]
    balance_transactions: list[dict[str, Any]]
    monthly_controls: list[dict[str, Any]]
    controls: dict[str, Any]

    def summary(self) -> dict[str, Any]:
        return {
            "status": "VALIDATED",
            "observed_at": self.observed_at,
            "provider_account": self.batch["provider_account"],
            "source_payload_sha256": self.batch["source_payload_sha256"],
            "source_rows": self.batch["row_count"],
            "canonical_rows": {
                "gg_payments": len(self.payments),
                "gg_provider_payouts": len(self.payouts),
                "gg_provider_balance_transactions": len(self.balance_transactions),
                "gg_provider_monthly_controls": len(self.monthly_controls),
            },
            "controls": self.controls,
            "identity_boundary": (
                "Provider and customer identities are stable HMAC record keys; raw Stripe "
                "IDs and customer PII are absent. GA4 transaction IDs remain unjoined."
            ),
        }


def _record_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _payload_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(value: Any, field: str, *, allow_empty: bool = False) -> str | None:
    cleaned = str(value or "").strip()
    if not cleaned and allow_empty:
        return None
    try:
        parsed = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderIngestionError(
            f"Invalid timezone-aware timestamp for {field}"
        ) from exc
    if parsed.tzinfo is None:
        raise ProviderIngestionError(f"Timestamp must include a timezone for {field}")
    return parsed.isoformat()


def _integer(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ProviderIngestionError(f"Boolean is not an integer for {field}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ProviderIngestionError(f"Invalid integer for {field}: {value!r}") from exc


def _money_from_cents(value: Any, field: str) -> str:
    cents = _integer(value, field)
    return format((Decimal(cents) / Decimal(100)).quantize(Decimal("0.01")), "f")


def _decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ProviderIngestionError(f"Invalid decimal for {field}: {value!r}") from exc


def _assert_record_key(value: Any, field: str, *, allow_empty: bool = False) -> str:
    candidate = str(value or "")
    if allow_empty and not candidate:
        return ""
    if not RECORD_KEY_RE.fullmatch(candidate):
        raise ProviderIngestionError(f"Invalid HMAC record key for {field}")
    return candidate


def _assert_privacy_projection(value: Any, path: tuple[Any, ...] = ()) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).casefold()
            if normalized in FORBIDDEN_KEYS:
                raise ProviderIngestionError(
                    f"Forbidden PII/provider field in receipt: {'.'.join(map(str, path + (key,)))}"
                )
            if normalized == "name" and not (
                path == ("provider",)
                or len(path) >= 2
                and path[:2] == ("rows", "products")
            ):
                raise ProviderIngestionError(
                    "Only provider and merchant product names are allowed"
                )
            _assert_privacy_projection(nested, path + (key,))
        return
    if isinstance(value, list):
        for index, nested in enumerate(value):
            _assert_privacy_projection(nested, path + (index,))
        return
    if isinstance(value, str):
        if EMAIL_RE.search(value):
            raise ProviderIngestionError(
                "Email-like value is forbidden in Stripe receipt"
            )
        if path[:1] != ("privacy",) and RAW_STRIPE_ID_RE.search(value):
            raise ProviderIngestionError("Raw Stripe object ID is forbidden in receipt")


def _assert_exact_row_contract(rows: dict[str, Any]) -> None:
    if set(rows) != set(REQUIRED_ROW_FIELDS):
        raise ProviderIngestionError(
            "Stripe row collections do not match the versioned receipt contract"
        )
    for collection, required in REQUIRED_ROW_FIELDS.items():
        values = rows[collection]
        if not isinstance(values, list):
            raise ProviderIngestionError(f"rows.{collection} must be a list")
        seen: set[str] = set()
        for index, row in enumerate(values):
            if not isinstance(row, dict) or not required.issubset(row):
                raise ProviderIngestionError(
                    f"rows.{collection}[{index}] is missing required fields"
                )
            key = _assert_record_key(
                row.get("record_key"), f"{collection}[{index}].record_key"
            )
            if key in seen:
                raise ProviderIngestionError(
                    f"Duplicate record key in rows.{collection}"
                )
            seen.add(key)


def _totals(rows: Iterable[dict[str, Any]], amount_field: str) -> dict[str, Any]:
    totals: dict[str, dict[str, int]] = {}
    for row in rows:
        currency = str(row.get("currency") or "unknown").casefold()
        bucket = totals.setdefault(currency, {"count": 0, "amount_cents": 0})
        bucket["count"] += 1
        bucket["amount_cents"] += _integer(row.get(amount_field), amount_field)
    return totals


def _balance_totals(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, dict[str, dict[str, int]]] = {}
    for row in rows:
        currency = str(row.get("currency") or "unknown").casefold()
        category = str(row.get("reporting_category") or "unknown").casefold()
        bucket = totals.setdefault(currency, {}).setdefault(
            category,
            {
                "count": 0,
                "amount_cents": 0,
                "fee_cents": 0,
                "net_cents": 0,
            },
        )
        bucket["count"] += 1
        for field in ("amount_cents", "fee_cents", "net_cents"):
            bucket[field] += _integer(row.get(field), field)
    return totals


def _offer_totals(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, dict[str, dict[str, int]]] = {}
    for row in rows:
        offer = str(row.get("offer_family") or "unknown")
        currency = str(row.get("currency") or "unknown").casefold()
        bucket = totals.setdefault(offer, {}).setdefault(
            currency, {"count": 0, "amount_cents": 0}
        )
        bucket["count"] += 1
        bucket["amount_cents"] += _integer(row.get("gross_cents"), "gross_cents")
    return totals


def _checkout_controls(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    result = {
        "synthetic_expired_unpaid": 0,
        "non_synthetic_expired_unpaid": 0,
        "non_synthetic_paid": 0,
    }
    for row in rows:
        if (
            row.get("synthetic")
            and row.get("status") == "expired"
            and row.get("payment_status") == "unpaid"
        ):
            result["synthetic_expired_unpaid"] += 1
        elif (
            not row.get("synthetic")
            and row.get("status") == "expired"
            and row.get("payment_status") == "unpaid"
        ):
            result["non_synthetic_expired_unpaid"] += 1
        elif not row.get("synthetic") and row.get("payment_status") == "paid":
            result["non_synthetic_paid"] += 1
    return result


def _month(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return f"{parsed.year:04d}-{parsed.month:02d}"


def _months(period: dict[str, Any]) -> list[str]:
    start = date.fromisoformat(str(period["start_date"]))
    end = date.fromisoformat(str(period["end_date_inclusive"]))
    if start > end:
        raise ProviderIngestionError("Stripe receipt period is reversed")
    output = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        output.append(f"{year:04d}-{month:02d}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return output


def _validate_receipt(
    receipt: dict[str, Any], *, enforce_2026_08_27_controls: bool
) -> dict[str, Any]:
    if receipt.get("schema") != SCHEMA:
        raise ProviderIngestionError(
            f"Unsupported Stripe receipt schema: {receipt.get('schema')!r}"
        )
    provider = receipt.get("provider")
    privacy = receipt.get("privacy")
    rows = receipt.get("rows")
    controls = receipt.get("controls")
    period = receipt.get("period")
    if not all(
        isinstance(value, dict) for value in (provider, privacy, rows, controls, period)
    ):
        raise ProviderIngestionError("Stripe receipt is missing a required object")
    if provider.get("name") != PROVIDER:
        raise ProviderIngestionError("Receipt provider must be stripe")
    _assert_record_key(
        provider.get("account_record_key"), "provider.account_record_key"
    )
    if (
        provider.get("charges_enabled") is not True
        or provider.get("payouts_enabled") is not True
    ):
        raise ProviderIngestionError("Stripe charges and payouts must both be enabled")
    if privacy.get("projection") != "financial_and_offer_fields_only":
        raise ProviderIngestionError("Unexpected Stripe privacy projection")
    if privacy.get("record_keys") != "hmac_sha256_using_server_secret":
        raise ProviderIngestionError(
            "Stripe record keys are not the required server HMACs"
        )
    if not str(receipt.get("side_effects") or "").startswith(
        "read_only_provider_list_and_retrieve_calls"
    ):
        raise ProviderIngestionError(
            "Stripe receipt does not assert read-only provider access"
        )
    _assert_privacy_projection(receipt)
    _assert_exact_row_contract(rows)
    _timestamp(receipt.get("generated_at"), "generated_at")
    _months(period)

    for collection, values in rows.items():
        for index, row in enumerate(values):
            _timestamp(row.get("created_at"), f"{collection}[{index}].created_at")
            if "available_at" in row:
                _timestamp(
                    row.get("available_at"),
                    f"{collection}[{index}].available_at",
                    allow_empty=True,
                )
            if "arrival_at" in row:
                _timestamp(
                    row.get("arrival_at"),
                    f"{collection}[{index}].arrival_at",
                    allow_empty=True,
                )
            for field, value in row.items():
                if field.endswith("_record_key"):
                    _assert_record_key(
                        value, f"{collection}[{index}].{field}", allow_empty=True
                    )
                if field.endswith("_cents"):
                    _integer(value, f"{collection}[{index}].{field}")

    successful = [
        row
        for row in rows["charges"]
        if row["paid"] is True
        and row["captured"] is True
        and row["status"] == "succeeded"
    ]
    refunds = [row for row in rows["refunds"] if row["status"] == "succeeded"]
    payouts = [row for row in rows["payouts"] if row["status"] == "paid"]
    paid_invoices = [row for row in rows["invoices"] if row["status"] == "paid"]
    recomputed = {
        "successful_charges": _totals(successful, "gross_cents"),
        "succeeded_refunds": _totals(refunds, "amount_cents"),
        "paid_payouts": _totals(payouts, "amount_cents"),
        "paid_invoices": _totals(paid_invoices, "amount_paid_cents"),
        "balance_activity_by_category": _balance_totals(rows["balance_transactions"]),
    }
    for key, value in recomputed.items():
        if controls.get(key) != value:
            raise ProviderIngestionError(
                f"Stripe receipt control does not reconcile: {key}"
            )

    if any(not invoice["line_items_complete"] for invoice in rows["invoices"]):
        raise ProviderIngestionError("A Stripe invoice has incomplete line items")

    product_keys = {row["record_key"] for row in rows["products"]}
    price_keys = {row["record_key"] for row in rows["prices"]}
    for price in rows["prices"]:
        if (
            price["product_record_key"]
            and price["product_record_key"] not in product_keys
        ):
            raise ProviderIngestionError("Stripe price references a missing product")
    for invoice in rows["invoices"]:
        if not isinstance(invoice["line_items"], list):
            raise ProviderIngestionError("Stripe invoice line_items must be a list")
        for line in invoice["line_items"]:
            if not isinstance(line, dict) or not REQUIRED_INVOICE_LINE_FIELDS.issubset(
                line
            ):
                raise ProviderIngestionError(
                    "Stripe invoice line is missing required fields"
                )
            _assert_record_key(
                line["price_record_key"],
                "invoice.line.price_record_key",
                allow_empty=True,
            )
            _assert_record_key(
                line["product_record_key"],
                "invoice.line.product_record_key",
                allow_empty=True,
            )
            _integer(line["amount_cents"], "invoice.line.amount_cents")
            _integer(line["quantity"], "invoice.line.quantity")
            _timestamp(line["period_start_at"], "invoice.line.period_start_at")
            _timestamp(line["period_end_at"], "invoice.line.period_end_at")
            if (
                line.get("price_record_key")
                and line["price_record_key"] not in price_keys
            ):
                raise ProviderIngestionError(
                    "Stripe invoice line references a missing price"
                )
            if (
                line.get("product_record_key")
                and line["product_record_key"] not in product_keys
            ):
                raise ProviderIngestionError(
                    "Stripe invoice line references a missing product"
                )

    balance_by_key = {row["record_key"]: row for row in rows["balance_transactions"]}
    for collection, source_rows, category in (
        ("charges", successful, "charge"),
        ("refunds", refunds, "refund"),
        ("payouts", payouts, "payout"),
    ):
        for row in source_rows:
            balance = balance_by_key.get(row["balance_transaction_record_key"])
            if not balance:
                raise ProviderIngestionError(
                    f"{collection} row is missing its balance transaction"
                )
            if balance["reporting_category"] != category:
                raise ProviderIngestionError(f"{collection} balance category mismatch")
            if balance["source_record_key"] != row["record_key"]:
                raise ProviderIngestionError(
                    f"{collection} balance source HMAC does not join"
                )

    paid_session_intents = {
        row["payment_intent_record_key"]
        for row in rows["checkout_sessions"]
        if not row["synthetic"] and row["payment_status"] == "paid"
    }
    charge_intents = {row["payment_intent_record_key"] for row in successful}
    if "" in paid_session_intents or not paid_session_intents.issubset(charge_intents):
        raise ProviderIngestionError(
            "Paid Checkout Sessions do not join to successful charges"
        )

    raw_rows = {key: len(value) for key, value in rows.items()}
    derived = {
        "raw_rows": raw_rows,
        **recomputed,
        "current_balance": controls.get("current_balance"),
        "checkout_sessions": _checkout_controls(rows["checkout_sessions"]),
        "offer_allocation": _offer_totals(successful),
        "cash_loop_net_cents": {
            currency: sum(category["net_cents"] for category in categories.values())
            for currency, categories in recomputed[
                "balance_activity_by_category"
            ].items()
        },
        "canonical_payment_rows": len(successful) + len(refunds),
        "invoice_line_items_complete": len(rows["invoices"]),
    }
    if enforce_2026_08_27_controls:
        failures = []
        for key, expected in EXPECTED_2026_08_27.items():
            actual = period if key == "period" else derived.get(key)
            if actual != expected:
                failures.append(f"{key}: expected {expected!r}, got {actual!r}")
        if derived["cash_loop_net_cents"] != {"usd": 0}:
            failures.append(
                f"cash_loop_net_cents: expected {{'usd': 0}}, got {derived['cash_loop_net_cents']!r}"
            )
        if failures:
            raise ProviderIngestionError(
                "Pinned Stripe control failure: " + "; ".join(failures)
            )
    return derived


def _product_name(charge: dict[str, Any], invoices: dict[str, dict[str, Any]]) -> str:
    labels = {
        "training_plan": "Custom Training Plan",
        "consulting": "Consulting",
        "consult_addon": "Consulting add-on",
        "coaching": "Coaching",
    }
    offer = str(charge.get("offer_family") or "unknown")
    if offer in labels:
        return labels[offer]
    invoice = invoices.get(str(charge.get("invoice_record_key") or ""), {})
    names = sorted(
        {
            str(line.get("merchant_product_name") or "").strip()
            for line in invoice.get("line_items", [])
            if str(line.get("merchant_product_name") or "").strip()
        }
    )
    return names[0] if len(names) == 1 else "Unattributed Stripe charge"


def _payment_rows(
    receipt: dict[str, Any], payload_sha256: str, observed_at: str
) -> list[dict[str, Any]]:
    rows = receipt["rows"]
    balances = {row["record_key"]: row for row in rows["balance_transactions"]}
    invoices = {row["record_key"]: row for row in rows["invoices"]}
    output: list[dict[str, Any]] = []
    successful = [
        row
        for row in rows["charges"]
        if row["paid"] is True
        and row["captured"] is True
        and row["status"] == "succeeded"
    ]
    for charge in successful:
        balance = balances[charge["balance_transaction_record_key"]]
        gross = _integer(balance["amount_cents"], "balance.amount_cents")
        net = _integer(balance["net_cents"], "balance.net_cents")
        product_name = _product_name(charge, invoices)
        output.append(
            {
                "deal_id": None,
                "athlete_id": None,
                "amount": _money_from_cents(net, "balance.net_cents"),
                "source": "provider_import",
                "stripe_payment_id": None,
                "description": product_name,
                "paid_at": charge["created_at"],
                "provider": PROVIDER,
                "provider_account": receipt["provider"]["account_record_key"],
                "provider_record_key": charge["record_key"],
                "provider_record_key_kind": RECORD_KEY_KIND,
                "customer_key": charge["customer_record_key"] or None,
                "product_name": product_name,
                "status": "succeeded",
                "currency": balance["currency"],
                "gross_amount": _money_from_cents(gross, "balance.amount_cents"),
                "provider_adjustment_amount": _money_from_cents(
                    gross - net, "provider_adjustment_cents"
                ),
                "net_amount": _money_from_cents(net, "balance.net_cents"),
                "source_payload_sha256": payload_sha256,
                "source_record_sha256": _record_sha256(
                    {"charge": charge, "balance": balance}
                ),
                "evidence_grade": "A",
                "source_boundary": (
                    "PII-free provider receipt; raw Stripe IDs and bank-deposit matching are absent."
                ),
                "provider_metadata": {
                    "balance_transaction_record_key": charge[
                        "balance_transaction_record_key"
                    ],
                    "payment_intent_record_key": charge["payment_intent_record_key"]
                    or None,
                    "invoice_record_key": charge["invoice_record_key"] or None,
                    "presentment_currency": charge["currency"],
                    "presentment_gross_cents": charge["gross_cents"],
                    "presentment_refunded_cents": charge["refunded_cents"],
                    "offer_family": charge["offer_family"],
                    "brand": charge["brand"],
                    "livemode": charge["livemode"],
                    "disputed": charge["disputed"],
                    "in_operating_system_period": True,
                },
                "observed_at": observed_at,
                "updated_at": observed_at,
            }
        )
    for refund in rows["refunds"]:
        if refund["status"] != "succeeded":
            continue
        balance = balances[refund["balance_transaction_record_key"]]
        gross = _integer(balance["amount_cents"], "refund balance.amount_cents")
        net = _integer(balance["net_cents"], "refund balance.net_cents")
        output.append(
            {
                "deal_id": None,
                "athlete_id": None,
                "amount": _money_from_cents(net, "refund balance.net_cents"),
                "source": "provider_import",
                "stripe_payment_id": None,
                "description": "Stripe refund",
                "paid_at": refund["created_at"],
                "provider": PROVIDER,
                "provider_account": receipt["provider"]["account_record_key"],
                "provider_record_key": refund["record_key"],
                "provider_record_key_kind": RECORD_KEY_KIND,
                "customer_key": None,
                "product_name": "Refund",
                "status": "refunded",
                "currency": balance["currency"],
                "gross_amount": _money_from_cents(gross, "refund balance.amount_cents"),
                "provider_adjustment_amount": _money_from_cents(
                    gross - net, "refund provider_adjustment_cents"
                ),
                "net_amount": _money_from_cents(net, "refund balance.net_cents"),
                "source_payload_sha256": payload_sha256,
                "source_record_sha256": _record_sha256(
                    {"refund": refund, "balance": balance}
                ),
                "evidence_grade": "A",
                "source_boundary": (
                    "Refund is a separate negative canonical payment; its originating charge "
                    "can fall outside the bounded receipt period."
                ),
                "provider_metadata": {
                    "balance_transaction_record_key": refund[
                        "balance_transaction_record_key"
                    ],
                    "charge_record_key": refund["charge_record_key"] or None,
                    "payment_intent_record_key": refund["payment_intent_record_key"]
                    or None,
                    "presentment_currency": refund["currency"],
                    "presentment_amount_cents": refund["amount_cents"],
                    "in_operating_system_period": True,
                },
                "observed_at": observed_at,
                "updated_at": observed_at,
            }
        )
    return output


def _payout_rows(
    receipt: dict[str, Any], payload_sha256: str, observed_at: str
) -> list[dict[str, Any]]:
    output = []
    for payout in receipt["rows"]["payouts"]:
        if payout["status"] != "paid":
            continue
        arrival = _timestamp(
            payout["arrival_at"], "payout.arrival_at", allow_empty=True
        )
        output.append(
            {
                "provider": PROVIDER,
                "provider_account": receipt["provider"]["account_record_key"],
                "provider_record_key": payout["record_key"],
                "provider_record_key_kind": RECORD_KEY_KIND,
                "status": payout["status"],
                "amount": _money_from_cents(
                    payout["amount_cents"], "payout.amount_cents"
                ),
                "currency": payout["currency"],
                "provider_created_at": payout["created_at"],
                "arrival_date": arrival[:10] if arrival else None,
                "payout_type": "automatic" if payout["automatic"] else "manual",
                "payout_method": None,
                "livemode": None,
                "source_payload_sha256": payload_sha256,
                "source_record_sha256": _record_sha256(payout),
                "evidence_grade": "A",
                "source_boundary": (
                    "PII-free provider payout; bank destination and bank-deposit match are absent."
                ),
                "provider_metadata": {
                    "balance_transaction_record_key": payout[
                        "balance_transaction_record_key"
                    ],
                    "automatic": payout["automatic"],
                    "in_operating_system_period": True,
                },
                "observed_at": observed_at,
                "updated_at": observed_at,
            }
        )
    return output


def _balance_rows(
    receipt: dict[str, Any], payload_sha256: str, observed_at: str
) -> list[dict[str, Any]]:
    source_keys = {
        row["record_key"]
        for collection in ("charges", "refunds", "payouts")
        for row in receipt["rows"][collection]
    }
    output = []
    for balance in receipt["rows"]["balance_transactions"]:
        output.append(
            {
                "provider": PROVIDER,
                "provider_account": receipt["provider"]["account_record_key"],
                "provider_record_key": balance["record_key"],
                "provider_record_key_kind": RECORD_KEY_KIND,
                "source_record_key": balance["source_record_key"] or None,
                "transaction_type": balance["type"],
                "reporting_category": balance["reporting_category"],
                "status": balance["status"],
                "amount": _money_from_cents(
                    balance["amount_cents"], "balance.amount_cents"
                ),
                "fee_amount": _money_from_cents(
                    balance["fee_cents"], "balance.fee_cents"
                ),
                "net_amount": _money_from_cents(
                    balance["net_cents"], "balance.net_cents"
                ),
                "currency": balance["currency"],
                "provider_created_at": balance["created_at"],
                "available_at": _timestamp(
                    balance["available_at"], "balance.available_at", allow_empty=True
                ),
                "source_payload_sha256": payload_sha256,
                "source_record_sha256": _record_sha256(balance),
                "evidence_grade": "A",
                "source_boundary": (
                    "Settlement ledger from a PII-free provider receipt; bank matching is absent."
                ),
                "provider_metadata": {
                    "source_record_present_in_period": balance["source_record_key"]
                    in source_keys,
                    "in_operating_system_period": True,
                },
                "observed_at": observed_at,
                "updated_at": observed_at,
            }
        )
    return output


def _monthly_rows(
    receipt: dict[str, Any], payload_sha256: str, observed_at: str
) -> list[dict[str, Any]]:
    rows = receipt["rows"]
    output = []
    for month in _months(receipt["period"]):
        charges = [
            row
            for row in rows["charges"]
            if _month(row["created_at"]) == month
            and row["paid"] is True
            and row["captured"] is True
            and row["status"] == "succeeded"
        ]
        refunds = [
            row
            for row in rows["refunds"]
            if _month(row["created_at"]) == month and row["status"] == "succeeded"
        ]
        payouts = [
            row
            for row in rows["payouts"]
            if _month(row["created_at"]) == month and row["status"] == "paid"
        ]
        balance = [
            row
            for row in rows["balance_transactions"]
            if _month(row["created_at"]) == month
        ]
        sessions = [
            row
            for row in rows["checkout_sessions"]
            if _month(row["created_at"]) == month
        ]
        metrics = {
            "successful_charges": _totals(charges, "gross_cents"),
            "succeeded_refunds": _totals(refunds, "amount_cents"),
            "paid_payouts": _totals(payouts, "amount_cents"),
            "balance_activity_by_category": _balance_totals(balance),
            "checkout_sessions": _checkout_controls(sessions),
            "offer_allocation": _offer_totals(charges),
        }
        output.append(
            {
                "provider": PROVIDER,
                "provider_account": receipt["provider"]["account_record_key"],
                "source_kind": MONTHLY_SOURCE_KIND,
                "control_month": f"{month}-01",
                "metrics": metrics,
                "source_payload_sha256": payload_sha256,
                "source_record_sha256": _record_sha256(
                    {"month": month, "metrics": metrics}
                ),
                "evidence_grade": "A",
                "source_boundary": (
                    "Created-at monthly flow controls; current balance is observation-time, "
                    "and bank matching is outside the receipt."
                ),
                "observed_at": observed_at,
                "updated_at": observed_at,
            }
        )
    return output


def build_stripe_bundle(
    receipt_path: str | Path,
    *,
    enforce_2026_08_27_controls: bool = True,
) -> StripeImportBundle:
    """Load, validate, and normalize one sanitized Stripe reconciliation receipt."""
    path = Path(receipt_path).expanduser().resolve()
    if not path.is_file():
        raise ProviderIngestionError(f"Stripe receipt is missing: {path}")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProviderIngestionError("Stripe receipt is not valid UTF-8 JSON") from exc
    if not isinstance(receipt, dict):
        raise ProviderIngestionError("Stripe receipt root must be an object")
    controls = _validate_receipt(
        receipt, enforce_2026_08_27_controls=enforce_2026_08_27_controls
    )
    observed_at = str(_timestamp(receipt["generated_at"], "generated_at"))
    payload_sha256 = _payload_sha256(path)
    provider_account = receipt["provider"]["account_record_key"]
    batch = {
        "provider": PROVIDER,
        "provider_account": provider_account,
        "source_kind": SOURCE_KIND,
        "source_payload_sha256": payload_sha256,
        "upstream_source_sha256": [],
        "observed_at": observed_at,
        "row_count": sum(controls["raw_rows"].values()),
        "control_totals": controls,
        "evidence_grade": "A",
        "source_boundary": (
            "PII-safe authenticated Stripe read receipt; raw provider IDs, GA4 raw "
            "transaction IDs, fulfillment joins, and bank-deposit matching are absent."
        ),
    }
    return StripeImportBundle(
        observed_at=observed_at,
        batch=batch,
        payments=_payment_rows(receipt, payload_sha256, observed_at),
        payouts=_payout_rows(receipt, payload_sha256, observed_at),
        balance_transactions=_balance_rows(receipt, payload_sha256, observed_at),
        monthly_controls=_monthly_rows(receipt, payload_sha256, observed_at),
        controls=controls,
    )


def _database() -> Any:
    global db
    if db is None:
        from mission_control import supabase_client

        db = supabase_client
    return db


def _with_batch_id(rows: list[dict[str, Any]], batch_id: str) -> list[dict[str, Any]]:
    return [{**row, "import_batch_id": batch_id} for row in rows]


def _money_sums(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> dict[str, str]:
    return {
        field: format(
            sum((_decimal(row[field], field) for row in rows), Decimal(0)).quantize(
                Decimal("0.01")
            ),
            "f",
        )
        for field in fields
    }


def _verify_readback(
    database: Any, bundle: StripeImportBundle, batch_id: str
) -> dict[str, Any]:
    expected = {
        "gg_payments": bundle.payments,
        "gg_provider_payouts": bundle.payouts,
        "gg_provider_balance_transactions": bundle.balance_transactions,
        "gg_provider_monthly_controls": bundle.monthly_controls,
    }
    actual = {
        table: database.select(table, match={"import_batch_id": batch_id})
        for table in expected
    }
    key_field = {
        "gg_payments": "provider_record_key",
        "gg_provider_payouts": "provider_record_key",
        "gg_provider_balance_transactions": "provider_record_key",
        "gg_provider_monthly_controls": "control_month",
    }
    for table, expected_rows in expected.items():
        field = key_field[table]
        expected_keys = {row[field] for row in expected_rows}
        actual_keys = {row[field] for row in actual[table]}
        if len(actual[table]) != len(expected_rows) or actual_keys != expected_keys:
            raise ProviderIngestionError(f"Live readback key mismatch for {table}")
    return {
        "status": "VERIFIED",
        "batch_id": batch_id,
        "rows": {table: len(rows) for table, rows in actual.items()},
        "financial_sums": {
            "gg_payments": _money_sums(
                actual["gg_payments"],
                ("amount", "gross_amount", "provider_adjustment_amount", "net_amount"),
            ),
            "gg_provider_payouts": _money_sums(
                actual["gg_provider_payouts"], ("amount",)
            ),
            "gg_provider_balance_transactions": _money_sums(
                actual["gg_provider_balance_transactions"],
                ("amount", "fee_amount", "net_amount"),
            ),
        },
    }


def apply_stripe_bundle(
    bundle: StripeImportBundle, *, batch_size: int = 500
) -> dict[str, Any]:
    """Idempotently apply a prevalidated Stripe bundle and verify live readback."""
    if batch_size < 1:
        raise ProviderIngestionError("batch_size must be at least 1")
    database = _database()
    stored_batch = database.upsert(
        "gg_provider_import_batches",
        bundle.batch,
        on_conflict="provider,provider_account,source_kind,source_payload_sha256",
    )
    if not stored_batch.get("id"):
        stored_batch = (
            database.select_one(
                "gg_provider_import_batches",
                match={
                    key: bundle.batch[key]
                    for key in (
                        "provider",
                        "provider_account",
                        "source_kind",
                        "source_payload_sha256",
                    )
                },
            )
            or {}
        )
    if not stored_batch.get("id"):
        raise ProviderIngestionError(
            "Stripe import batch did not return a persistent id"
        )
    batch_id = str(stored_batch["id"])
    prepared = {
        "gg_payments": _with_batch_id(bundle.payments, batch_id),
        "gg_provider_payouts": _with_batch_id(bundle.payouts, batch_id),
        "gg_provider_balance_transactions": _with_batch_id(
            bundle.balance_transactions, batch_id
        ),
        "gg_provider_monthly_controls": _with_batch_id(
            bundle.monthly_controls, batch_id
        ),
    }
    conflicts = {
        "gg_payments": "provider,provider_account,provider_record_key",
        "gg_provider_payouts": "provider,provider_account,provider_record_key",
        "gg_provider_balance_transactions": (
            "provider,provider_account,provider_record_key"
        ),
        "gg_provider_monthly_controls": (
            "provider,provider_account,source_kind,control_month"
        ),
    }
    returned = {
        table: database.upsert_many(
            table, rows, on_conflict=conflicts[table], batch_size=batch_size
        )
        for table, rows in prepared.items()
    }
    readback = _verify_readback(database, bundle, batch_id)
    return {
        "status": "APPLIED_AND_VERIFIED",
        "batch_id": batch_id,
        "attempted_rows": {table: len(rows) for table, rows in prepared.items()},
        "returned_rows": {table: len(rows) for table, rows in returned.items()},
        "controls": bundle.controls,
        "readback": readback,
    }
