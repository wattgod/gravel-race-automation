#!/usr/bin/env python3
"""Seal a staged historical approval as an immutable public snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from validate_gravel_weekly_history import (
    HISTORY_DIR,
    compute_history_content_hash,
    validate_history_entry,
)
from validate_gravel_weekly_history_decisions import validate_history_decision

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DECISION_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "history-decisions"


def _timestamp(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


def seal_history_entry(approved_value: Any, published_at: str) -> dict[str, Any]:
    approved = validate_history_entry(approved_value)
    if approved["status"] != "approved":
        raise ValueError("historical sealing requires a status=approved entry")
    published_time = _timestamp(published_at, "publishedAt")
    approved_time = _timestamp(
        approved["editorialApproval"]["approvedAt"], "editorialApproval.approvedAt"
    )
    if published_time < approved_time:
        raise ValueError("publishedAt cannot precede historical editorial approval")
    sealed = {
        **approved,
        "status": "published",
        "publishedAt": published_at,
        "updatedAt": published_at,
        "contentHash": "pending",
    }
    sealed["contentHash"] = compute_history_content_hash(sealed)
    return validate_history_entry(sealed)


def _find_reviewed_draft(entry_id: str) -> Path:
    matches: list[Path] = []
    for path in sorted(HISTORY_DIR.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if value.get("entryId") == entry_id:
            matches.append(path)
    if len(matches) != 1:
        raise SystemExit(
            f"Expected exactly one canonical draft for {entry_id}; found {len(matches)}"
        )
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("approved", type=Path)
    parser.add_argument("--published-at", required=True)
    parser.add_argument("--decision", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--decision-output", type=Path)
    args = parser.parse_args()
    approved = json.loads(args.approved.read_text(encoding="utf-8"))
    sealed = seal_history_entry(approved, args.published_at)
    decision_input = args.decision or args.approved.with_name(
        f"{sealed['entryId']}.decision.json"
    )
    if not decision_input.exists():
        raise SystemExit(f"Historical decision not found: {decision_input}")
    decision = validate_history_decision(
        json.loads(decision_input.read_text(encoding="utf-8")), sealed
    )
    output = args.output or _find_reviewed_draft(sealed["entryId"])
    decision_output = args.decision_output or DECISION_DIR / f"{sealed['entryId']}.json"

    if output.exists():
        current = validate_history_entry(json.loads(output.read_text(encoding="utf-8")))
        if current["status"] != "draft":
            raise SystemExit(f"Refusing to replace non-draft historical snapshot: {output}")
        if current["entryId"] != sealed["entryId"]:
            raise SystemExit(f"Refusing to replace a different historical entry: {output}")
        if current["contentHash"] != decision["reviewedDraftContentHash"]:
            raise SystemExit("Canonical historical draft changed after review; approval is stale")
        if current["headline"] != decision["suggestedHeadline"] or current["take"] != decision["suggestedTake"]:
            raise SystemExit("Historical decision does not preserve the exact reviewed draft copy")
    if decision_output.exists():
        raise SystemExit(f"Refusing to replace immutable historical decision: {decision_output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    decision_output.parent.mkdir(parents=True, exist_ok=True)
    decision_output.write_text(f"{json.dumps(decision, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    output.write_text(f"{json.dumps(sealed, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"Sealed published historical snapshot: {output}")
    print(f"Sealed immutable historical decision: {decision_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
