#!/usr/bin/env python3
"""Apply an explicit human approval packet to a Gravel Weekly draft.

This produces an approved, still non-deployable snapshot. It deliberately
cannot change factual reporting, receipts, scores, or race impacts from the
reviewed draft; only the human-owned editorial fields may change.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from validate_gravel_weekly import compute_content_hash, validate_issue
from validate_gravel_weekly_decisions import (
    DECISION_SCHEMA,
    QUIET_DECISION_SCHEMA,
    RECEIPT_SCHEMA,
    validate_decision_receipt,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPROVED_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "approved"
APPROVAL_SCHEMA = "gravel-weekly-approval/v3"
ALLOWED_APPROVAL_KEYS = {
    "schemaVersion", "issueId", "reviewedDraftContentHash", "approver",
    "approvedAt", "currentThingStoryId", "stories", "quietIssue",
}
ALLOWED_STORY_DECISION_KEYS = {
    "candidateId", "decision", "headline", "dek", "take", "editSummary", "reason",
}
ALLOWED_QUIET_DECISION_KEYS = {
    "decision", "headline", "note", "editSummary",
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
        reason = _text(item.get("reason"), f"approval.stories[{index}].reason", 2_000)
        return {"candidateId": candidate_id, "decision": decision, "reason": reason}
    return {
        "candidateId": candidate_id,
        "decision": decision,
        "headline": _text(item.get("headline"), f"approval.stories[{index}].headline", 300),
        "dek": _text(item.get("dek"), f"approval.stories[{index}].dek", 600),
        "take": _text(item.get("take"), f"approval.stories[{index}].take", 8_000),
        "editSummary": _text(item.get("editSummary"), f"approval.stories[{index}].editSummary", 2_000),
    }


def _approval_quiet_issue(value: Any) -> dict[str, Any]:
    item = _record(value, "approval.quietIssue")
    unknown = set(item) - ALLOWED_QUIET_DECISION_KEYS
    if unknown:
        raise ValueError(f"approval.quietIssue has unsupported fields: {sorted(unknown)}")
    if item.get("decision") != "approve":
        raise ValueError("approval.quietIssue.decision must be approve")
    return {
        "decision": "approve",
        "headline": _text(item.get("headline"), "approval.quietIssue.headline", 300),
        "note": _text(item.get("note"), "approval.quietIssue.note", 1_000),
        "editSummary": _text(
            item.get("editSummary"), "approval.quietIssue.editSummary", 2_000
        ),
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
    reviewed_hash = _text(
        approval.get("reviewedDraftContentHash"),
        "approval.reviewedDraftContentHash",
        64,
    )
    if not re.fullmatch(r"[0-9a-f]{64}", reviewed_hash):
        raise ValueError("approval.reviewedDraftContentHash must be a lowercase SHA-256 hash")
    if reviewed_hash != draft["contentHash"]:
        raise ValueError("approval.reviewedDraftContentHash must match the exact reviewed draft")

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
        # evidentiary, scoring, race-impact, and culture-context field remains
        # the reviewed draft.
        approved_stories.append({
            **draft_story,
            "headline": decision["headline"],
            "dek": decision["dek"],
            "take": decision["take"],
            "takeProvenance": "human_approved",
        })
    quiet_decision_raw = approval.get("quietIssue")
    if approved_stories:
        if quiet_decision_raw is not None:
            raise ValueError("approval.quietIssue cannot coexist with approved stories")
        approved_quiet_issue = None
    else:
        if quiet_decision_raw is None:
            raise ValueError(
                "an issue without approved stories requires an explicit quiet issue decision"
            )
        quiet_decision = _approval_quiet_issue(quiet_decision_raw)
        approved_quiet_issue = {
            "headline": quiet_decision["headline"],
            "note": quiet_decision["note"],
            "provenance": "human_approved",
        }

    approved_at = _text(approval.get("approvedAt"), "approval.approvedAt", 100)
    approver = _text(approval.get("approver"), "approval.approver", 300)
    current_id = approval.get("currentThingStoryId")
    if current_id is not None:
        current_id = _text(current_id, "approval.currentThingStoryId", 500)
    approved_ids = {story["candidateId"] for story in approved_stories}
    if current_id is not None and current_id not in approved_ids:
        raise ValueError("approval.currentThingStoryId must reference an approved story")
    if approved_quiet_issue is not None and current_id is not None:
        raise ValueError("a quiet issue cannot designate The Current Thing")

    all_impacts = _dedupe_records([
        impact for story in approved_stories for impact in story["raceImpacts"]
    ])
    source_index = sorted({
        receipt["canonicalUrl"] for story in approved_stories for receipt in story["receipts"]
    } | {
        artifact["canonicalUrl"] for story in approved_stories for artifact in story.get("cultureArtifacts", [])
    })
    approved = {
        **draft,
        "status": "approved",
        "stories": approved_stories,
        "quietIssue": approved_quiet_issue,
        "currentThingStoryId": current_id,
        "raceImpacts": all_impacts,
        "sourceIndex": source_index,
        "editorialApproval": {
            "approver": approver,
            "approvedAt": approved_at,
            "reviewedDraftContentHash": reviewed_hash,
        },
        "publishedAt": None,
        "updatedAt": approved_at,
        "contentHash": "pending",
    }
    approved["contentHash"] = compute_content_hash(approved)
    return validate_issue(approved)


def build_decision_receipt(draft_value: Any, approval_value: Any, approved_value: Any) -> dict[str, Any]:
    """Bind every human story decision to the exact reviewed draft and approved copy."""
    draft = validate_issue(draft_value)
    approved = validate_issue(approved_value)
    expected = approve_issue(draft, approval_value)
    if approved != expected:
        raise ValueError("approved issue does not match the supplied draft and approval packet")
    approval = _record(approval_value, "approval")
    decisions = [_approval_story(value, index) for index, value in enumerate(approval["stories"])]
    approved_by_id = {story["candidateId"]: story for story in approved["stories"]}
    draft_by_id = {story["candidateId"]: story for story in draft["stories"]}
    records: list[dict[str, Any]] = []
    for decision in decisions:
        is_approved = decision["decision"] == "approve"
        records.append({
            "schemaVersion": DECISION_SCHEMA,
            "issueId": approved["issueId"],
            "candidateId": decision["candidateId"],
            "decision": decision["decision"],
            "reason": (
                f"Approved for Gravel Weekly #{approved['issueNumber']:03d}."
                if is_approved else decision["reason"]
            ),
            "decidedBy": approval["approver"],
            "decidedAt": approval["approvedAt"],
            "suggestedCopy": draft_by_id[decision["candidateId"]]["take"] if is_approved else None,
            "approvedCopy": approved_by_id[decision["candidateId"]]["take"] if is_approved else None,
            "editSummary": decision["editSummary"] if is_approved else None,
        })
    receipt = {
        "schemaVersion": RECEIPT_SCHEMA,
        "issueId": approved["issueId"],
        "publicationDate": approved["publicationDate"],
        "reviewedDraftContentHash": draft["contentHash"],
        "decidedBy": approval["approver"],
        "decidedAt": approval["approvedAt"],
        "decisions": records,
        "quietIssueDecision": None,
    }
    if approved.get("quietIssue") is not None:
        quiet_decision = _approval_quiet_issue(approval.get("quietIssue"))
        suggested = draft.get("quietIssue")
        receipt["quietIssueDecision"] = {
            "schemaVersion": QUIET_DECISION_SCHEMA,
            "issueId": approved["issueId"],
            "decision": "approve",
            "reason": f"Approved a quiet Gravel Weekly #{approved['issueNumber']:03d}.",
            "decidedBy": approval["approver"],
            "decidedAt": approval["approvedAt"],
            "suggestedHeadline": suggested["headline"] if suggested else None,
            "suggestedNote": suggested["note"] if suggested else None,
            "approvedHeadline": approved["quietIssue"]["headline"],
            "approvedNote": approved["quietIssue"]["note"],
            "editSummary": quiet_decision["editSummary"],
        }
    return validate_decision_receipt(receipt, approved)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("approval", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--decision-receipt-output", type=Path)
    args = parser.parse_args()
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    approval = json.loads(args.approval.read_text(encoding="utf-8"))
    issue = approve_issue(draft, approval)
    output = args.output or APPROVED_DIR / f"{issue['publicationDate']}.json"
    receipt = build_decision_receipt(draft, approval, issue)
    receipt_output = args.decision_receipt_output or APPROVED_DIR / f"{issue['publicationDate']}.decisions.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{json.dumps(issue, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    receipt_output.write_text(f"{json.dumps(receipt, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"Approved but not published: {output}")
    print(f"Durable decision receipt staged: {receipt_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
