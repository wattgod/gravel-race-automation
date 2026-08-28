#!/usr/bin/env python3
"""Create a fail-closed assigning ledger from a historical source census."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from validate_gravel_weekly import IssueValidationError
from validate_gravel_weekly_backfill import validate_backfill_ledger


def _record(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IssueValidationError(f"{name} must be an object")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise IssueValidationError(f"{name} must be an array")
    return value


def _timestamp_day(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise IssueValidationError(f"{name} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IssueValidationError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise IssueValidationError(f"{name} must include a timezone")
    return parsed.date().isoformat()


def build_initial_backfill_ledger(
    discovery_value: Any,
    *,
    source_ledger_issue: str,
    source_ledger_run: str,
    program_issue: str,
    updated_at: str,
) -> dict[str, Any]:
    """Convert a complete discovery ledger into an all-accounted initial review ledger."""

    discovery = _record(discovery_value, "historical discovery ledger")
    if discovery.get("schemaVersion") != "gravel-weekly-historical-ledger/v1":
        raise IssueValidationError("unsupported historical discovery ledger schema")
    year = discovery.get("year")
    if not isinstance(year, int) or isinstance(year, bool):
        raise IssueValidationError("historical discovery year is invalid")

    requested = discovery.get("archiveMonthsRequested")
    succeeded = discovery.get("archiveMonthsSucceeded")
    errors = _list(discovery.get("archiveMonthErrors"), "archiveMonthErrors")
    if not isinstance(requested, int) or requested <= 0:
        raise IssueValidationError("archiveMonthsRequested is invalid")
    if succeeded != requested or errors:
        raise IssueValidationError("historical discovery ledger is incomplete")

    cards = [_record(card, f"sourceCards[{index}]") for index, card in enumerate(_list(discovery.get("sourceCards"), "sourceCards"))]
    card_ids: list[str] = []
    for index, card in enumerate(cards):
        card_id = card.get("id")
        if not isinstance(card_id, str) or not card_id:
            raise IssueValidationError(f"sourceCards[{index}].id is invalid")
        card_ids.append(card_id)
    if len(card_ids) != len(set(card_ids)):
        raise IssueValidationError("historical source card IDs must be unique")
    source_count = discovery.get("sourceCardCount")
    if source_count != len(card_ids):
        raise IssueValidationError("historical sourceCardCount does not match sourceCards")

    assigned_ids: list[str] = []
    weeks: list[dict[str, Any]] = []
    for index, week_value in enumerate(_list(discovery.get("weeks"), "weeks")):
        week = _record(week_value, f"weeks[{index}]")
        source_ids = _list(week.get("sourceCardIds"), f"weeks[{index}].sourceCardIds")
        for source_index, source_id in enumerate(source_ids):
            if not isinstance(source_id, str) or not source_id:
                raise IssueValidationError(f"weeks[{index}].sourceCardIds[{source_index}] is invalid")
            assigned_ids.append(source_id)
        count = len(source_ids)
        weeks.append({
            "periodStartedAt": _timestamp_day(week.get("periodStartedAt"), f"weeks[{index}].periodStartedAt"),
            "periodEndedAt": _timestamp_day(week.get("periodEndedAt"), f"weeks[{index}].periodEndedAt"),
            "sourceCardCount": count,
            "disposition": "explicit_gap" if count == 0 else "pending_review",
            "entryIds": [],
            "reason": (
                "Cyclingnews exposed no matching source card; preserve the quiet window."
                if count == 0
                else "Source census complete; assigning-desk research and disposition remain pending."
            ),
        })

    if len(assigned_ids) != len(set(assigned_ids)):
        raise IssueValidationError("historical source cards must not be assigned to multiple weeks")
    if set(assigned_ids) != set(card_ids):
        missing = sorted(set(card_ids) - set(assigned_ids))
        unknown = sorted(set(assigned_ids) - set(card_ids))
        raise IssueValidationError(f"weekly source-card accounting mismatch: missing={missing}, unknown={unknown}")

    result = {
        "schemaVersion": "gravel-weekly-backfill-ledger/v1",
        "year": year,
        "asOf": discovery.get("asOf"),
        "sourceLedgerIssue": source_ledger_issue,
        "sourceLedgerRun": source_ledger_run,
        "programIssue": program_issue,
        "sourceCardCount": source_count,
        "complete": not any(week["disposition"] == "pending_review" for week in weeks),
        "humanApprovalRequired": True,
        "autoPublishAllowed": False,
        "weeks": weeks,
        "updatedAt": updated_at,
    }
    return validate_backfill_ledger(result, [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--source-ledger-issue", required=True)
    parser.add_argument("--source-ledger-run", required=True)
    parser.add_argument("--program-issue", required=True)
    parser.add_argument("--updated-at", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    result = build_initial_backfill_ledger(
        json.loads(args.ledger.read_text(encoding="utf-8")),
        source_ledger_issue=args.source_ledger_issue,
        source_ledger_run=args.source_ledger_run,
        program_issue=args.program_issue,
        updated_at=args.updated_at,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {args.output} with {len(result['weeks'])} accounted windows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
