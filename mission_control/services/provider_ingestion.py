"""Idempotent ingestion of reconciled provider revenue evidence.

The TrainingPeaks coaching export does not expose a payment transaction ID.
Those rows therefore use a labeled synthetic fingerprint over normalized source
facts plus a duplicate ordinal. Marketplace royalty rows remain aggregate
monthly controls; they are never promoted to purchaser-level transactions.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# Deliberately lazy-loaded by ``_database``.  Validation and dry-run must not
# require the Supabase SDK or credentials; only an explicit apply does.
db: Any | None = None


FILES = {
    "coaching_payments": "gravel-god-trainingpeaks-coaching-provider-ledger.csv",
    "coaching_payouts": "gravel-god-trainingpeaks-coaching-payout-ledger.csv",
    "coaching_customers": "gravel-god-trainingpeaks-coaching-customer-lifecycle.csv",
    "coaching_monthly": "gravel-god-trainingpeaks-coaching-lifecycle-monthly.csv",
    "marketplace_monthly": "gravel-god-trainingpeaks-marketplace-royalty-reconciliation.csv",
}

REQUIRED_COLUMNS = {
    "coaching_payments": {
        "source_row", "customer_key", "purchase_date", "status",
        "athlete_charged_usd", "amount_received_usd", "fee_refund_delta_usd",
        "product", "in_operating_system_period", "source_file_sha256",
        "evidence_grade", "boundary",
    },
    "coaching_payouts": {
        "source_row", "payout_key", "provider_id_sha256", "created_utc",
        "arrival_date_utc", "amount_usd", "currency", "livemode", "status",
        "type", "method", "in_operating_system_period", "source_file_sha256",
        "evidence_grade", "boundary",
    },
    "coaching_customers": {
        "customer_key", "first_success_date", "last_success_date",
        "current_status", "current_product", "current_last_payment_date",
        "current_next_payment_date", "payment_rows", "succeeded_rows",
        "refunded_rows", "lifetime_athlete_charged_usd",
        "lifetime_amount_received_usd", "period_athlete_charged_usd",
        "period_amount_received_usd", "confirmed_cancel_events",
        "latest_confirmed_cancel_date", "pause_events", "latest_pause_date",
        "successful_payments_after_latest_cancel", "lifecycle_class",
        "evidence_grade", "boundary",
    },
    "coaching_monthly": {
        "month", "payment_rows", "succeeded_rows", "refunded_rows",
        "distinct_paying_customers", "new_logo_starts",
        "inferred_reactivations_or_migrations", "confirmed_terminal_churns",
        "athlete_charged_usd", "amount_received_usd", "evidence_grade",
        "boundary",
    },
    "marketplace_monthly": {
        "sale_month", "sale_notice_count", "gross_list_price_usd",
        "author_share_rate", "expected_author_royalty_usd", "paypal_payout_date",
        "paypal_payout_usd", "settled_variance_usd", "pending_royalty_usd",
        "settlement_status", "paypal_message_sha256", "evidence_grade",
        "boundary",
    },
}

FORBIDDEN_PII_COLUMNS = {
    "name", "email", "contact_name", "contact_email", "customer_name",
    "customer_email", "athlete_name", "athlete_email", "provider_customer_id",
    "bank_destination", "bank_account_number", "routing_number",
}

EXPECTED_2026_08_27 = {
    "payment_rows": 553,
    "period_payment_rows": 213,
    "period_succeeded_rows": 209,
    "period_refunded_rows": 4,
    "period_gross": Decimal("47765.60"),
    "period_net": Decimal("45694.95"),
    "payout_rows": 351,
    "period_paid_payouts": 132,
    "period_payout_amount": Decimal("45404.92"),
    "customer_rows": 36,
    "paid_customers": 17,
    "paused_customers": 8,
    "canceled_customers": 11,
    "new_logo_starts": 6,
    "inferred_reactivations": 5,
    "confirmed_terminal_churns": 5,
    "marketplace_sale_notices": 17,
    "marketplace_gross": Decimal("1342.00"),
    "marketplace_author_share": Decimal("939.40"),
    "marketplace_paid": Decimal("793.80"),
    "marketplace_pending": Decimal("145.60"),
    "customer_payment_rows_total": 553,
    "customer_period_gross": Decimal("47765.60"),
    "customer_period_net": Decimal("45694.95"),
    "monthly_period_payment_rows": 213,
    "monthly_period_succeeded_rows": 209,
    "monthly_period_refunded_rows": 4,
    "monthly_period_gross": Decimal("47765.60"),
    "monthly_period_net": Decimal("45694.95"),
    "payout_reconciliation_gap": Decimal("290.03"),
    "marketplace_settlement_gap": Decimal("0.00"),
}


class ProviderIngestionError(RuntimeError):
    """Raised when source files fail closed-loop validation."""


@dataclass
class ImportBundle:
    observed_at: str
    batches: dict[str, dict[str, Any]]
    payments: list[dict[str, Any]]
    payouts: list[dict[str, Any]]
    customer_snapshots: list[dict[str, Any]]
    monthly_controls: list[dict[str, Any]]
    controls: dict[str, Any]

    def summary(self) -> dict[str, Any]:
        return {
            "status": "VALIDATED",
            "observed_at": self.observed_at,
            "batches": {key: value["row_count"] for key, value in self.batches.items()},
            "canonical_rows": {
                "gg_payments": len(self.payments),
                "gg_provider_payouts": len(self.payouts),
                "gg_provider_customer_snapshots": len(self.customer_snapshots),
                "gg_provider_monthly_controls": len(self.monthly_controls),
            },
            "controls": self.controls,
            "identity_boundary": (
                "TrainingPeaks customer keys are snapshot-local; payment keys are labeled "
                "synthetic fingerprints because the export has no transaction ID."
            ),
        }


def _read_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise ProviderIngestionError(f"Required provider file is missing: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(required_columns - columns)
        if missing:
            raise ProviderIngestionError(
                f"Required columns are missing from {path.name}: {', '.join(missing)}"
            )
        forbidden = sorted(columns & FORBIDDEN_PII_COLUMNS)
        if forbidden:
            raise ProviderIngestionError(
                f"PII-bearing columns are forbidden in {path.name}: {', '.join(forbidden)}"
            )
        return list(reader)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_sha256(row: dict[str, Any]) -> str:
    encoded = json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _decimal(value: str | None, field: str) -> Decimal:
    try:
        return Decimal(str(value or "0"))
    except InvalidOperation as exc:
        raise ProviderIngestionError(f"Invalid decimal for {field}: {value!r}") from exc


def _money(value: Decimal | str | None) -> str:
    amount = value if isinstance(value, Decimal) else _decimal(value, "money")
    return format(amount.quantize(Decimal("0.01")), "f")


def _observed_at(value: str | None) -> str:
    if not value:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderIngestionError(f"Invalid observed_at timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ProviderIngestionError("observed_at must include a timezone offset")
    return parsed.isoformat()


def _integer(value: str | None, field: str) -> int:
    try:
        return int(str(value or "0"))
    except ValueError as exc:
        raise ProviderIngestionError(f"Invalid integer for {field}: {value!r}") from exc


def _boolean(value: str | None) -> bool:
    normalized = str(value or "").strip().casefold()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no", ""}:
        return False
    raise ProviderIngestionError(f"Invalid boolean value: {value!r}")


def _date_or_none(value: str | None) -> str | None:
    cleaned = str(value or "").strip()
    return cleaned or None


def _assert_unique(
    rows: list[dict[str, str]], field: str, label: str, *, skip_total: bool = False
) -> None:
    values = [
        row[field]
        for row in rows
        if not (skip_total and row[field].startswith("TOTAL"))
    ]
    duplicates = sorted(value for value, count in Counter(values).items() if count > 1)
    if duplicates:
        raise ProviderIngestionError(
            f"Duplicate {field} values in {label}: {', '.join(duplicates[:5])}"
        )


def _batch(
    *,
    provider_account: str,
    source_kind: str,
    path: Path,
    rows: list[dict[str, str]],
    observed_at: str,
    control_totals: dict[str, Any],
    evidence_grade: str,
    boundary: str,
) -> dict[str, Any]:
    upstream = sorted({
        row.get("source_file_sha256", "")
        for row in rows
        if row.get("source_file_sha256")
    })
    if any(not _is_sha256(digest) for digest in upstream):
        raise ProviderIngestionError(f"Invalid upstream SHA-256 in {path.name}")
    return {
        "provider": "trainingpeaks",
        "provider_account": provider_account,
        "source_kind": source_kind,
        "source_payload_sha256": _sha256_file(path),
        "upstream_source_sha256": upstream,
        "observed_at": observed_at,
        "row_count": len(rows),
        "control_totals": control_totals,
        "evidence_grade": evidence_grade,
        "source_boundary": boundary,
    }


def _payment_rows(
    rows: list[dict[str, str]], payload_sha256: str, observed_at: str
) -> list[dict[str, Any]]:
    occurrences: Counter[str] = Counter()
    output: list[dict[str, Any]] = []
    for source in rows:
        signature_fields = {
            "customer_key": source["customer_key"],
            "purchase_date": source["purchase_date"],
            "status": source["status"],
            "athlete_charged_usd": _money(source["athlete_charged_usd"]),
            "amount_received_usd": _money(source["amount_received_usd"]),
            "product": source["product"],
        }
        signature = json.dumps(signature_fields, sort_keys=True, separators=(",", ":"))
        occurrences[signature] += 1
        fingerprint = hashlib.sha256(
            f"trainingpeaks:coaching:{signature}:duplicate={occurrences[signature]}".encode("utf-8")
        ).hexdigest()
        gross = _decimal(source["athlete_charged_usd"], "athlete_charged_usd")
        net = _decimal(source["amount_received_usd"], "amount_received_usd")
        reported_adjustment = _decimal(
            source["fee_refund_delta_usd"], "fee_refund_delta_usd"
        )
        if gross - net != reported_adjustment:
            raise ProviderIngestionError(
                "Payment row gross-minus-net does not match fee_refund_delta_usd: "
                f"source_row={source['source_row']}"
            )
        output.append({
            "_batch_key": "coaching_payments",
            "deal_id": None,
            "athlete_id": None,
            "amount": _money(net),
            "source": "provider_import",
            "stripe_payment_id": None,
            "description": source["product"],
            "paid_at": source["purchase_date"],
            "provider": "trainingpeaks",
            "provider_account": "coaching",
            "provider_record_key": fingerprint,
            "provider_record_key_kind": "synthetic_normalized_fingerprint_v1",
            "customer_key": source["customer_key"],
            "product_name": source["product"],
            "status": source["status"],
            "currency": "usd",
            "gross_amount": _money(gross),
            "provider_adjustment_amount": _money(gross - net),
            "net_amount": _money(net),
            "source_payload_sha256": payload_sha256,
            "source_record_sha256": _record_sha256(source),
            "evidence_grade": source["evidence_grade"],
            "source_boundary": source["boundary"],
            "provider_metadata": {
                "in_operating_system_period": _boolean(source["in_operating_system_period"]),
                "source_row": _integer(source["source_row"], "source_row"),
            },
            "observed_at": observed_at,
            "updated_at": observed_at,
        })
    return output


def _payout_rows(
    rows: list[dict[str, str]], payload_sha256: str, observed_at: str
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in rows:
        provider_key = source["provider_id_sha256"].strip()
        if not _is_sha256(provider_key):
            raise ProviderIngestionError("TrainingPeaks payout row is missing provider_id_sha256")
        output.append({
            "_batch_key": "coaching_payouts",
            "provider": "trainingpeaks",
            "provider_account": "coaching",
            "provider_record_key": provider_key,
            "provider_record_key_kind": "provider_id_sha256",
            "status": source["status"],
            "amount": _money(source["amount_usd"]),
            "currency": source["currency"].casefold(),
            "provider_created_at": _date_or_none(source["created_utc"]),
            "arrival_date": _date_or_none(source["arrival_date_utc"]),
            "payout_type": source["type"],
            "payout_method": source["method"],
            "livemode": _boolean(source["livemode"]),
            "source_payload_sha256": payload_sha256,
            "source_record_sha256": _record_sha256(source),
            "evidence_grade": source["evidence_grade"],
            "source_boundary": source["boundary"],
            "provider_metadata": {
                "in_operating_system_period": _boolean(source["in_operating_system_period"]),
                "source_row": _integer(source["source_row"], "source_row"),
            },
            "observed_at": observed_at,
            "updated_at": observed_at,
        })
    return output


def _customer_rows(
    rows: list[dict[str, str]], payload_sha256: str, observed_at: str
) -> list[dict[str, Any]]:
    money_map = {
        "lifetime_gross_amount": "lifetime_athlete_charged_usd",
        "lifetime_net_amount": "lifetime_amount_received_usd",
        "period_gross_amount": "period_athlete_charged_usd",
        "period_net_amount": "period_amount_received_usd",
    }
    integer_map = {
        "payment_rows": "payment_rows",
        "succeeded_rows": "succeeded_rows",
        "refunded_rows": "refunded_rows",
        "confirmed_cancel_events": "confirmed_cancel_events",
        "pause_events": "pause_events",
        "successes_after_latest_cancel": "successful_payments_after_latest_cancel",
    }
    output: list[dict[str, Any]] = []
    for source in rows:
        row: dict[str, Any] = {
            "_batch_key": "coaching_customers",
            "provider": "trainingpeaks",
            "provider_account": "coaching",
            "snapshot_sha256": payload_sha256,
            "customer_key": source["customer_key"],
            "customer_key_kind": "snapshot_local",
            "first_success_date": _date_or_none(source["first_success_date"]),
            "last_success_date": _date_or_none(source["last_success_date"]),
            "current_status": source["current_status"],
            "current_product": source["current_product"],
            "current_last_payment_date": _date_or_none(source["current_last_payment_date"]),
            "current_next_payment_date": _date_or_none(source["current_next_payment_date"]),
            "latest_confirmed_cancel_date": _date_or_none(source["latest_confirmed_cancel_date"]),
            "latest_pause_date": _date_or_none(source["latest_pause_date"]),
            "lifecycle_class": source["lifecycle_class"],
            "source_record_sha256": _record_sha256(source),
            "evidence_grade": source["evidence_grade"],
            "source_boundary": source["boundary"],
            "observed_at": observed_at,
        }
        for target, source_name in money_map.items():
            row[target] = _money(source[source_name])
        for target, source_name in integer_map.items():
            row[target] = _integer(source[source_name], source_name)
        output.append(row)
    return output


def _monthly_rows(
    rows: list[dict[str, str]],
    *,
    batch_key: str,
    provider_account: str,
    source_kind: str,
    payload_sha256: str,
    observed_at: str,
    month_field: str,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in rows:
        month = source[month_field]
        if not month or month.startswith("TOTAL"):
            continue
        metrics = {
            key: value
            for key, value in source.items()
            if key not in {month_field, "evidence_grade", "boundary"}
        }
        output.append({
            "_batch_key": batch_key,
            "provider": "trainingpeaks",
            "provider_account": provider_account,
            "source_kind": source_kind,
            "control_month": f"{month}-01",
            "metrics": metrics,
            "source_payload_sha256": payload_sha256,
            "source_record_sha256": _record_sha256(source),
            "evidence_grade": source["evidence_grade"],
            "source_boundary": source["boundary"],
            "observed_at": observed_at,
            "updated_at": observed_at,
        })
    return output


def _controls(
    payments: list[dict[str, str]],
    payouts: list[dict[str, str]],
    customers: list[dict[str, str]],
    lifecycle_monthly: list[dict[str, str]],
    marketplace_monthly: list[dict[str, str]],
) -> dict[str, Any]:
    period_payments = [
        row for row in payments if _boolean(row["in_operating_system_period"])
    ]
    period_payouts = [
        row for row in payouts
        if _boolean(row["in_operating_system_period"]) and row["status"] == "paid"
    ]
    lifecycle_detail = [
        row for row in lifecycle_monthly if not row["month"].startswith("TOTAL")
    ]
    marketplace_detail = [
        row for row in marketplace_monthly
        if not row["sale_month"].startswith("TOTAL")
    ]

    period_gross = sum(
        (_decimal(row["athlete_charged_usd"], "athlete_charged_usd")
         for row in period_payments),
        Decimal("0"),
    )
    period_net = sum(
        (_decimal(row["amount_received_usd"], "amount_received_usd")
         for row in period_payments),
        Decimal("0"),
    )
    period_payout_amount = sum(
        (_decimal(row["amount_usd"], "amount_usd") for row in period_payouts),
        Decimal("0"),
    )
    marketplace_author_share = sum(
        (_decimal(row["expected_author_royalty_usd"], "expected_author_royalty_usd")
         for row in marketplace_detail),
        Decimal("0"),
    )
    marketplace_paid = sum(
        (_decimal(row["paypal_payout_usd"], "paypal_payout_usd")
         for row in marketplace_detail),
        Decimal("0"),
    )
    marketplace_pending = sum(
        (_decimal(row["pending_royalty_usd"], "pending_royalty_usd")
         for row in marketplace_detail),
        Decimal("0"),
    )
    return {
        "payment_rows": len(payments),
        "period_payment_rows": len(period_payments),
        "period_succeeded_rows": sum(row["status"] == "succeeded" for row in period_payments),
        "period_refunded_rows": sum(row["status"] == "refunded" for row in period_payments),
        "period_gross": period_gross,
        "period_net": period_net,
        "payout_rows": len(payouts),
        "period_paid_payouts": len(period_payouts),
        "period_payout_amount": period_payout_amount,
        "customer_rows": len(customers),
        "paid_customers": sum(row["current_status"] == "paid" for row in customers),
        "paused_customers": sum(row["current_status"] == "paused" for row in customers),
        "canceled_customers": sum(row["current_status"] == "canceled" for row in customers),
        "new_logo_starts": sum(
            _integer(row["new_logo_starts"], "new_logo_starts")
            for row in lifecycle_detail
        ),
        "inferred_reactivations": sum(
            _integer(
                row["inferred_reactivations_or_migrations"],
                "inferred_reactivations_or_migrations",
            )
            for row in lifecycle_detail
        ),
        "confirmed_terminal_churns": sum(
            _integer(row["confirmed_terminal_churns"], "confirmed_terminal_churns")
            for row in lifecycle_detail
        ),
        "marketplace_sale_notices": sum(
            _integer(row["sale_notice_count"], "sale_notice_count")
            for row in marketplace_detail
        ),
        "marketplace_gross": sum(
            (_decimal(row["gross_list_price_usd"], "gross_list_price_usd")
             for row in marketplace_detail),
            Decimal("0"),
        ),
        "marketplace_author_share": marketplace_author_share,
        "marketplace_paid": marketplace_paid,
        "marketplace_pending": marketplace_pending,
        "customer_payment_rows_total": sum(
            _integer(row["payment_rows"], "payment_rows") for row in customers
        ),
        "customer_period_gross": sum(
            (_decimal(row["period_athlete_charged_usd"], "period_athlete_charged_usd")
             for row in customers),
            Decimal("0"),
        ),
        "customer_period_net": sum(
            (_decimal(row["period_amount_received_usd"], "period_amount_received_usd")
             for row in customers),
            Decimal("0"),
        ),
        "monthly_period_payment_rows": sum(
            _integer(row["payment_rows"], "payment_rows") for row in lifecycle_detail
        ),
        "monthly_period_succeeded_rows": sum(
            _integer(row["succeeded_rows"], "succeeded_rows")
            for row in lifecycle_detail
        ),
        "monthly_period_refunded_rows": sum(
            _integer(row["refunded_rows"], "refunded_rows")
            for row in lifecycle_detail
        ),
        "monthly_period_gross": sum(
            (_decimal(row["athlete_charged_usd"], "athlete_charged_usd")
             for row in lifecycle_detail),
            Decimal("0"),
        ),
        "monthly_period_net": sum(
            (_decimal(row["amount_received_usd"], "amount_received_usd")
             for row in lifecycle_detail),
            Decimal("0"),
        ),
        "payout_reconciliation_gap": period_net - period_payout_amount,
        "marketplace_settlement_gap": (
            marketplace_author_share - marketplace_paid - marketplace_pending
        ),
    }


def _json_safe_controls(controls: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _money(value) if isinstance(value, Decimal) else value
        for key, value in controls.items()
    }


def _validate_expected(controls: dict[str, Any]) -> None:
    failures = []
    for key, expected in EXPECTED_2026_08_27.items():
        actual = controls.get(key)
        if actual != expected:
            failures.append(f"{key}: expected {expected}, got {actual}")
    if failures:
        raise ProviderIngestionError("Provider control failure: " + "; ".join(failures))


def build_trainingpeaks_bundle(
    input_dir: str | Path,
    *,
    observed_at: str | None = None,
    enforce_2026_08_27_controls: bool = True,
) -> ImportBundle:
    """Parse, validate, and normalize the reconciled Gravel God provider files."""
    root = Path(input_dir).expanduser().resolve()
    paths = {key: root / filename for key, filename in FILES.items()}
    source_rows = {
        key: _read_csv(path, REQUIRED_COLUMNS[key])
        for key, path in paths.items()
    }
    _assert_unique(
        source_rows["coaching_payments"], "source_row", "coaching payment ledger"
    )
    _assert_unique(
        source_rows["coaching_payouts"], "source_row", "coaching payout ledger"
    )
    _assert_unique(
        source_rows["coaching_payouts"],
        "provider_id_sha256",
        "coaching payout ledger",
    )
    _assert_unique(
        source_rows["coaching_customers"],
        "customer_key",
        "coaching customer snapshot",
    )
    _assert_unique(
        source_rows["coaching_monthly"],
        "month",
        "coaching monthly controls",
        skip_total=True,
    )
    _assert_unique(
        source_rows["marketplace_monthly"],
        "sale_month",
        "marketplace monthly controls",
        skip_total=True,
    )
    observed = _observed_at(observed_at)
    controls = _controls(
        source_rows["coaching_payments"],
        source_rows["coaching_payouts"],
        source_rows["coaching_customers"],
        source_rows["coaching_monthly"],
        source_rows["marketplace_monthly"],
    )
    if enforce_2026_08_27_controls:
        _validate_expected(controls)
    safe_controls = _json_safe_controls(controls)

    batches = {
        "coaching_payments": _batch(
            provider_account="coaching",
            source_kind="payment_ledger",
            path=paths["coaching_payments"],
            rows=source_rows["coaching_payments"],
            observed_at=observed,
            control_totals={
                key: safe_controls[key]
                for key in (
                    "payment_rows", "period_payment_rows", "period_succeeded_rows",
                    "period_refunded_rows", "period_gross", "period_net",
                )
            },
            evidence_grade="A",
            boundary=(
                "Provider export has no payment transaction ID; deterministic "
                "keys are labeled synthetic."
            ),
        ),
        "coaching_payouts": _batch(
            provider_account="coaching",
            source_kind="payout_ledger",
            path=paths["coaching_payouts"],
            rows=source_rows["coaching_payouts"],
            observed_at=observed,
            control_totals={
                key: safe_controls[key]
                for key in ("payout_rows", "period_paid_payouts", "period_payout_amount")
            },
            evidence_grade="A",
            boundary=(
                "Provider payout IDs are retained only as SHA-256; bank deposits "
                "remain unmatched."
            ),
        ),
        "coaching_customers": _batch(
            provider_account="coaching",
            source_kind="customer_lifecycle_snapshot",
            path=paths["coaching_customers"],
            rows=source_rows["coaching_customers"],
            observed_at=observed,
            control_totals={
                key: safe_controls[key]
                for key in (
                    "customer_rows", "paid_customers", "paused_customers",
                    "canceled_customers",
                )
            },
            evidence_grade="A/B",
            boundary=(
                "Customer keys are snapshot-local; six historical churn dates "
                "and churn denominators remain incomplete."
            ),
        ),
        "coaching_monthly": _batch(
            provider_account="coaching",
            source_kind="lifecycle_monthly_controls",
            path=paths["coaching_monthly"],
            rows=source_rows["coaching_monthly"],
            observed_at=observed,
            control_totals={
                key: safe_controls[key]
                for key in (
                    "new_logo_starts", "inferred_reactivations",
                    "confirmed_terminal_churns",
                )
            },
            evidence_grade="A/B",
            boundary=(
                "Monthly payment activity and dated lifecycle counts; no "
                "month-start denominator or churn rate."
            ),
        ),
        "marketplace_monthly": _batch(
            provider_account="marketplace",
            source_kind="royalty_monthly_controls",
            path=paths["marketplace_monthly"],
            rows=source_rows["marketplace_monthly"],
            observed_at=observed,
            control_totals={
                key: safe_controls[key]
                for key in (
                    "marketplace_sale_notices", "marketplace_gross", "marketplace_author_share",
                    "marketplace_paid", "marketplace_pending",
                )
            },
            evidence_grade="A/B",
            boundary=(
                "Aggregate monthly royalties only; purchaser-level marketplace "
                "transactions are unavailable."
            ),
        ),
    }

    payments = _payment_rows(
        source_rows["coaching_payments"],
        batches["coaching_payments"]["source_payload_sha256"],
        observed,
    )
    payouts = _payout_rows(
        source_rows["coaching_payouts"],
        batches["coaching_payouts"]["source_payload_sha256"],
        observed,
    )
    customers = _customer_rows(
        source_rows["coaching_customers"],
        batches["coaching_customers"]["source_payload_sha256"],
        observed,
    )
    monthly = _monthly_rows(
        source_rows["coaching_monthly"],
        batch_key="coaching_monthly",
        provider_account="coaching",
        source_kind="lifecycle",
        payload_sha256=batches["coaching_monthly"]["source_payload_sha256"],
        observed_at=observed,
        month_field="month",
    )
    monthly.extend(_monthly_rows(
        source_rows["marketplace_monthly"],
        batch_key="marketplace_monthly",
        provider_account="marketplace",
        source_kind="royalty",
        payload_sha256=batches["marketplace_monthly"]["source_payload_sha256"],
        observed_at=observed,
        month_field="sale_month",
    ))
    return ImportBundle(observed, batches, payments, payouts, customers, monthly, safe_controls)


def _attach_batch_ids(
    rows: list[dict[str, Any]], batch_ids: dict[str, str]
) -> list[dict[str, Any]]:
    prepared = []
    for source in rows:
        row = dict(source)
        key = row.pop("_batch_key")
        row["import_batch_id"] = batch_ids[key]
        prepared.append(row)
    return prepared


def _database() -> Any:
    """Return the write client only when apply mode actually needs it."""
    global db
    if db is None:
        from mission_control import supabase_client

        db = supabase_client
    return db


def apply_bundle(bundle: ImportBundle, *, batch_size: int = 500) -> dict[str, Any]:
    """Idempotently write a prevalidated bundle to the migrated Mission Control schema."""
    database = _database()
    batch_ids: dict[str, str] = {}
    for key, batch in bundle.batches.items():
        stored = database.upsert(
            "gg_provider_import_batches",
            batch,
            on_conflict="provider,provider_account,source_kind,source_payload_sha256",
        )
        if not stored.get("id"):
            stored = database.select_one(
                "gg_provider_import_batches",
                match={
                    "provider": batch["provider"],
                    "provider_account": batch["provider_account"],
                    "source_kind": batch["source_kind"],
                    "source_payload_sha256": batch["source_payload_sha256"],
                },
            ) or {}
        if not stored.get("id"):
            raise ProviderIngestionError(f"Import batch {key} did not return a persistent id")
        batch_ids[key] = str(stored["id"])

    payments = _attach_batch_ids(bundle.payments, batch_ids)
    payouts = _attach_batch_ids(bundle.payouts, batch_ids)
    customers = _attach_batch_ids(bundle.customer_snapshots, batch_ids)
    monthly = _attach_batch_ids(bundle.monthly_controls, batch_ids)
    stored = {
        "gg_payments": database.upsert_many(
            "gg_payments", payments,
            on_conflict="provider,provider_account,provider_record_key",
            batch_size=batch_size,
        ),
        "gg_provider_payouts": database.upsert_many(
            "gg_provider_payouts", payouts,
            on_conflict="provider,provider_account,provider_record_key",
            batch_size=batch_size,
        ),
        "gg_provider_customer_snapshots": database.upsert_many(
            "gg_provider_customer_snapshots", customers,
            on_conflict="provider,provider_account,snapshot_sha256,customer_key",
            batch_size=batch_size,
        ),
        "gg_provider_monthly_controls": database.upsert_many(
            "gg_provider_monthly_controls", monthly,
            on_conflict="provider,provider_account,source_kind,control_month",
            batch_size=batch_size,
        ),
    }
    return {
        "status": "APPLIED",
        "batch_ids": batch_ids,
        "attempted_rows": {
            "gg_payments": len(payments),
            "gg_provider_payouts": len(payouts),
            "gg_provider_customer_snapshots": len(customers),
            "gg_provider_monthly_controls": len(monthly),
        },
        "returned_rows": {table: len(rows) for table, rows in stored.items()},
        "controls": bundle.controls,
    }
