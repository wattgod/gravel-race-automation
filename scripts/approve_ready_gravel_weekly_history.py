#!/usr/bin/env python3
"""Stage every READY historical draft after one exact human approval phrase.

This command applies hash-bound approvals only. It cannot seal, publish, deploy,
or alter race data, and held entries are excluded even when they overlap the
selected year.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from approve_gravel_weekly_history import (
    APPROVAL_SCHEMA,
    STAGED_DIR,
    apply_history_decision,
    reviewed_headline_copy,
    reviewed_take_copy,
)
from render_gravel_weekly_history_review import approval_holds
from validate_gravel_weekly_history import HISTORY_DIR, load_history_entries


@dataclass(frozen=True)
class StagedHistoryApproval:
    entry_id: str
    approved: dict[str, Any]
    decision: dict[str, Any]


def approval_phrase(year: int) -> str:
    return f"approve all READY {year} entries as written"


def prepare_ready_approvals(
    entries: list[dict[str, Any]],
    *,
    year: int,
    phrase: str,
    approver: str,
    decided_at: str,
) -> list[StagedHistoryApproval]:
    expected = approval_phrase(year)
    if phrase != expected:
        raise ValueError(f"approval phrase must exactly equal: {expected}")
    ready = [
        entry
        for entry in entries
        if entry["status"] == "draft"
        and entry["activeFrom"] <= f"{year}-12-31"
        and entry["activeThrough"] >= f"{year}-01-01"
        and not approval_holds(entry)
    ]
    if not ready:
        raise ValueError(f"no READY {year} historical entries are available")

    prepared: list[StagedHistoryApproval] = []
    for draft in ready:
        approved, decision = apply_history_decision(draft, {
            "schemaVersion": APPROVAL_SCHEMA,
            "entryId": draft["entryId"],
            "reviewedDraftContentHash": draft["contentHash"],
            "decision": "approve",
            "approver": approver,
            "decidedAt": decided_at,
            "headline": reviewed_headline_copy(draft),
            "take": reviewed_take_copy(draft),
            "editSummary": (
                "Approved the displayed headline and Take as written; removed only "
                "the internal model-draft provenance warning from the staged Take."
            ),
            "reason": None,
        })
        if approved is None:  # pragma: no cover - apply_history_decision is fail-closed
            raise ValueError(f"approval unexpectedly rejected {draft['entryId']}")
        prepared.append(StagedHistoryApproval(draft["entryId"], approved, decision))
    return prepared


def stage_ready_approvals(
    prepared: list[StagedHistoryApproval], output_dir: Path = STAGED_DIR
) -> list[Path]:
    targets = [
        target
        for item in prepared
        for target in (
            output_dir / f"{item.entry_id}.approved.json",
            output_dir / f"{item.entry_id}.decision.json",
        )
    ]
    existing = [path for path in targets if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to replace staged historical approval: "
            + ", ".join(str(path) for path in existing)
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    for item in prepared:
        (output_dir / f"{item.entry_id}.approved.json").write_text(
            f"{json.dumps(item.approved, indent=2, ensure_ascii=False)}\n",
            encoding="utf-8",
        )
        (output_dir / f"{item.entry_id}.decision.json").write_text(
            f"{json.dumps(item.decision, indent=2, ensure_ascii=False)}\n",
            encoding="utf-8",
        )
    return targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--approval-phrase", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--decided-at", required=True)
    parser.add_argument("--output-dir", type=Path, default=STAGED_DIR)
    args = parser.parse_args()

    prepared = prepare_ready_approvals(
        load_history_entries(HISTORY_DIR),
        year=args.year,
        phrase=args.approval_phrase,
        approver=args.approver,
        decided_at=args.decided_at,
    )
    targets = stage_ready_approvals(prepared, args.output_dir)
    print(f"Approved but not published: {len(prepared)} READY {args.year} entries")
    for path in targets:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
