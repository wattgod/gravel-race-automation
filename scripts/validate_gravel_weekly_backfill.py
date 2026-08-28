#!/usr/bin/env python3
"""Validate the year-level accounting ledger for Gravel Weekly history backfill."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from validate_gravel_weekly import IssueValidationError, _iso, _list, _record, _text, _url
from validate_gravel_weekly_history import HISTORY_DIR, load_history_entries

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKFILL_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "backfill"
DISPOSITIONS = {
    "explicit_gap",
    "pending_review",
    "covered_by_draft",
    "held_for_evidence",
    "rejected",
    "approved",
}


def _day(value: Any, name: str) -> str:
    raw = _text(value, name, 10)
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as exc:
        raise IssueValidationError(f"{name} must be YYYY-MM-DD") from exc
    return parsed.date().isoformat()


def validate_backfill_ledger(value: Any, history_entries: list[dict[str, Any]]) -> dict[str, Any]:
    ledger = _record(value, "backfill ledger")
    if ledger.get("schemaVersion") != "gravel-weekly-backfill-ledger/v1":
        raise IssueValidationError("unsupported Gravel Weekly backfill ledger schema")
    year = ledger.get("year")
    if not isinstance(year, int) or isinstance(year, bool) or not 2000 <= year <= 2100:
        raise IssueValidationError("backfill year is invalid")
    _iso(ledger.get("asOf"), "asOf")
    _url(ledger.get("sourceLedgerIssue"), "sourceLedgerIssue")
    _url(ledger.get("sourceLedgerRun"), "sourceLedgerRun")
    _url(ledger.get("programIssue"), "programIssue")
    source_total = ledger.get("sourceCardCount")
    if not isinstance(source_total, int) or isinstance(source_total, bool) or source_total < 0:
        raise IssueValidationError("sourceCardCount is invalid")
    if ledger.get("humanApprovalRequired") is not True or ledger.get("autoPublishAllowed") is not False:
        raise IssueValidationError("backfill publication safety flags are invalid")

    histories = {entry["entryId"]: entry for entry in history_entries}
    weeks = _list(ledger.get("weeks"), "weeks", 54)
    if not weeks:
        raise IssueValidationError("backfill ledger requires weekly accounting")
    previous_end: datetime | None = None
    counted_sources = 0
    pending = 0
    for index, week_value in enumerate(weeks):
        name = f"weeks[{index}]"
        week = _record(week_value, name)
        started = datetime.strptime(_day(week.get("periodStartedAt"), f"{name}.periodStartedAt"), "%Y-%m-%d")
        ended = datetime.strptime(_day(week.get("periodEndedAt"), f"{name}.periodEndedAt"), "%Y-%m-%d")
        if (ended - started).days != 6 or started.weekday() != 5 or ended.weekday() != 4:
            raise IssueValidationError(f"{name} must be one Saturday-through-Friday window")
        if previous_end is not None and started != previous_end + timedelta(days=1):
            raise IssueValidationError("backfill weeks must be contiguous and ordered")
        previous_end = ended
        count = week.get("sourceCardCount")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise IssueValidationError(f"{name}.sourceCardCount is invalid")
        counted_sources += count
        disposition = week.get("disposition")
        if disposition not in DISPOSITIONS:
            raise IssueValidationError(f"{name}.disposition is invalid")
        entry_ids = [
            _text(entry_id_value, f"{name}.entryIds[{entry_index}]", 500)
            for entry_index, entry_id_value in enumerate(_list(week.get("entryIds"), f"{name}.entryIds", 20))
        ]
        if len(entry_ids) != len(set(entry_ids)):
            raise IssueValidationError(f"{name}.entryIds contains duplicates")
        for entry_id in entry_ids:
            entry = histories.get(entry_id)
            if entry is None:
                raise IssueValidationError(f"{name} references unknown history entry {entry_id}")
            if not any(started.date() <= datetime.fromisoformat(receipt["publishedAt"].replace("Z", "+00:00")).date() <= ended.date() for receipt in entry["contemporaryReceipts"]):
                raise IssueValidationError(f"{name} links {entry_id} without a contemporary receipt in that week")
        reason = _text(week.get("reason"), f"{name}.reason", 1_000)
        if disposition == "explicit_gap" and (count != 0 or entry_ids):
            raise IssueValidationError("explicit gaps require zero source cards and no entries")
        if disposition == "pending_review" and (count == 0 or entry_ids):
            raise IssueValidationError("pending windows require source cards and no linked entries")
        if disposition in {"covered_by_draft", "approved"} and not entry_ids:
            raise IssueValidationError(f"{disposition} windows require linked history entries")
        if disposition == "covered_by_draft" and any(histories[entry_id]["status"] != "draft" for entry_id in entry_ids):
            raise IssueValidationError("covered_by_draft windows must link only draft entries")
        if disposition == "approved" and any(histories[entry_id]["status"] not in {"approved", "published"} for entry_id in entry_ids):
            raise IssueValidationError("approved windows require approved or published entries")
        if disposition == "pending_review":
            pending += 1
        if not reason:
            raise IssueValidationError(f"{name}.reason is required")
    if counted_sources != source_total:
        raise IssueValidationError(f"weekly source-card sum {counted_sources} does not match {source_total}")
    complete = ledger.get("complete")
    if not isinstance(complete, bool) or complete != (pending == 0):
        raise IssueValidationError("complete must be true exactly when no weekly window remains pending")
    _iso(ledger.get("updatedAt"), "updatedAt")
    return ledger


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    histories = load_history_entries(HISTORY_DIR)
    paths = args.paths or sorted(BACKFILL_DIR.glob("*.json"))
    for path in paths:
        validate_backfill_ledger(json.loads(path.read_text(encoding="utf-8")), histories)
        print(f"OK {path}")
    print(f"Validated {len(paths)} Gravel Weekly backfill ledger{'s' if len(paths) != 1 else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
