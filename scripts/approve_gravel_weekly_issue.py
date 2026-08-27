#!/usr/bin/env python3
"""Apply an explicit human approval packet to a Gravel Weekly draft.

This produces an approved, still non-deployable snapshot. It deliberately
cannot change factual reporting, receipts, scores, or race impacts from the
reviewed draft; only the human-owned editorial fields may change.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_gravel_weekly import compute_content_hash, validate_issue

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPROVED_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "approved"
APPROVAL_SCHEMA = "gravel-weekly-approval/v1"
ALLOWED_APPROVAL_KEYS = {
    "schemaVersion", "issueId", "approver", "approvedAt", "currentThingStoryId", "stories",
}
ALLOWED_STORY_DECISION_KEYS = {
    "candidateId", "decision", "headline", "dek", "take", "editSummary", "reason",
}


def _record(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _text(value: Any, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    if len(value) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    return value.strip()


def _approval_story(value: Any, index: int) -> dict[str, Any]:
    item = _record(value, f"approval.stories[{index}]")
    unknown = set(item) - ALLOWED_STORY_DECISION_KEYS
    if unknown:
        raise ValueError(f"approval.stories[{index}] has unsupported fields: {sorted(unknown)}")
    candidate_id = _text(item.get("candidateId"), f"approval.stories[{index}].candidateId", 500)
    decision = item.get("decision")
    if decision not in {"approve", "reject"}:
        raise ValueError(f"approval.stories[{index}].decision must be approve or reject")
    if decision == "reject":
        _text(item.get("reason"), f"approval.stories[{index}].reason", 2_000)
        return {"candidateId": candidate_id, "decision": decision}
    return {
        "candidateId": candidate_id,
        "decision": decision,
        "headline": _text(item.get("headline"), f"approval.stories[{index}].headline", 300),
        "dek": _text(item.get("dek"), f"approval.stories[{index}].dek", 600),
        "take": _text(item.get("take"), f"approval.stories[{index}].take", 8_000),
        "editSummary": _text(item.get("editSummary"), f"approval.stories[{index}].editSummary", 2_000),
    }


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        key = json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        if key not in seen:
            result.append(record)
            seen.add(key)
    return result


def approve_issue(draft_value: Any, approval_value: Any) -> dict[str, Any]:
    draft = validate_issue(draft_value)
    if draft["status"] != "draft":
        raise ValueError("approval requires a status=draft issue")
    approval = _record(approval_value, "approval")
    unknown = set(approval) - ALLOWED_APPROVAL_KEYS
    if unknown:
        raise ValueError(f"approval has unsupported fields: {sorted(unknown)}")
    if approval.get("schemaVersion") != APPROVAL_SCHEMA:
        raise ValueError("unsupported Gravel Weekly approval schema")
    if approval.get("issueId") != draft["issueId"]:
        raise ValueError("approval.issueId must match the draft issueId")

    decisions_raw = approval.get("stories")
    if not isinstance(decisions_raw, list):
        raise ValueError("approval.stories must be a list")
    decisions = [_approval_story(value, index) for index, value in enumerate(decisions_raw)]
    decision_ids = [item["candidateId"] for item in decisions]
    if len(decision_ids) != len(set(decision_ids)):
        raise ValueError("approval story candidate IDs must be unique")
    draft_ids = [story["candidateId"] for story in draft["stories"]]
    if set(decision_ids) != set(draft_ids):
        missing = sorted(set(draft_ids) - set(decision_ids))
        extra = sorted(set(decision_ids) - set(draft_ids))
        raise ValueError(f"approval must decide every reviewed story exactly once; missing={missing}, extra={extra}")

    decisions_by_id = {item["candidateId"]: item for item in decisions}
    approved_stories: list[dict[str, Any]] = []
    for draft_story in draft["stories"]:
        decision = decisions_by_id[draft_story["candidateId"]]
        if decision["decision"] == "reject":
            continue
        # Only these three fields come from the human approval. Every factual,
        # evidentiary, scoring, and race-impact field remains the reviewed draft.
        approved_stories.append({
            **draft_story,
            "headline": decision["headline"],
            "dek": decision["dek"],
            "take": decision["take"],
            "takeProvenance": "human_approved",
        })
    if not approved_stories:
        raise ValueError("an approved issue must contain at least one approved story")

    approved_at = _text(approval.get("approvedAt"), "approval.approvedAt", 100)
    approver = _text(approval.get("approver"), "approval.approver", 300)
    current_id = approval.get("currentThingStoryId")
    if current_id is not None:
        current_id = _text(current_id, "approval.currentThingStoryId", 500)
    approved_ids = {story["candidateId"] for story in approved_stories}
    if current_id is not None and current_id not in approved_ids:
        raise ValueError("approval.currentThingStoryId must reference an approved story")

    all_impacts = _dedupe_records([
        impact for story in approved_stories for impact in story["raceImpacts"]
    ])
    source_index = sorted({
        receipt["canonicalUrl"] for story in approved_stories for receipt in story["receipts"]
    })
    approved = {
        **draft,
        "status": "approved",
        "stories": approved_stories,
        "currentThingStoryId": current_id,
        "raceImpacts": all_impacts,
        "sourceIndex": source_index,
        "editorialApproval": {"approver": approver, "approvedAt": approved_at},
        "publishedAt": None,
        "updatedAt": approved_at,
        "contentHash": "pending",
    }
    approved["contentHash"] = compute_content_hash(approved)
    return validate_issue(approved)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("approval", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    approval = json.loads(args.approval.read_text(encoding="utf-8"))
    issue = approve_issue(draft, approval)
    output = args.output or APPROVED_DIR / f"{issue['publicationDate']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{json.dumps(issue, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"Approved but not published: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
