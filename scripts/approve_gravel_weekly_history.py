#!/usr/bin/env python3
"""Apply one explicit, hash-bound human decision to a historical draft.

Approval stages human-owned headline and Take copy outside the public history
directory. Rejection writes only a durable local decision. Neither path can
publish an entry.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from validate_gravel_weekly_history import compute_history_content_hash, validate_history_entry
from validate_gravel_weekly_history_decisions import DECISION_SCHEMA, validate_history_decision

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGED_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "history-staged"
APPROVAL_SCHEMA = "gravel-weekly-history-approval/v1"
APPROVAL_KEYS = {
    "schemaVersion",
    "entryId",
    "reviewedDraftContentHash",
    "decision",
    "approver",
    "decidedAt",
    "headline",
    "take",
    "editSummary",
    "reason",
}
MODEL_DRAFT_PREFIX = re.compile(
    r"^\s*Model draft, not Matti(?:’|')s approved view:\s*",
    re.IGNORECASE,
)
MODEL_DRAFT_HEADLINE_PREFIX = re.compile(r"^\s*MODEL DRAFT:\s*", re.IGNORECASE)


def reviewed_headline_copy(draft_value: Any) -> str:
    """Return the headline shown to Matti, without an internal draft label."""
    draft = _record(draft_value, "historical draft")
    headline = _text(draft.get("headline"), "draft.headline", 300)
    reviewed = MODEL_DRAFT_HEADLINE_PREFIX.sub("", headline, count=1).strip()
    if not reviewed:
        raise ValueError("draft.headline contains no reviewable copy after its draft label")
    return reviewed


def reviewed_take_copy(draft_value: Any) -> str:
    """Return the Take shown to Matti, without an internal provenance warning."""
    draft = _record(draft_value, "historical draft")
    take = _text(draft.get("take"), "draft.take", 8_000)
    reviewed = MODEL_DRAFT_PREFIX.sub("", take, count=1).strip()
    if not reviewed:
        raise ValueError("draft.take contains no reviewable copy after its provenance warning")
    return reviewed


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


def apply_history_decision(
    draft_value: Any, approval_value: Any
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return a non-public approved entry, if any, and its decision receipt."""
    draft = validate_history_entry(draft_value)
    if draft["status"] != "draft":
        raise ValueError("historical approval requires a status=draft entry")
    approval = _record(approval_value, "historical approval")
    unknown = set(approval) - APPROVAL_KEYS
    if unknown:
        raise ValueError(f"historical approval has unsupported fields: {sorted(unknown)}")
    if approval.get("schemaVersion") != APPROVAL_SCHEMA:
        raise ValueError("unsupported Gravel Weekly historical approval schema")
    if approval.get("entryId") != draft["entryId"]:
        raise ValueError("approval.entryId must match the historical draft")
    if approval.get("reviewedDraftContentHash") != draft["contentHash"]:
        raise ValueError("approval.reviewedDraftContentHash must match the exact reviewed draft")
    verdict = approval.get("decision")
    if verdict not in {"approve", "reject"}:
        raise ValueError("approval.decision must be approve or reject")
    approver = _text(approval.get("approver"), "approval.approver", 300)
    decided_at = _text(approval.get("decidedAt"), "approval.decidedAt", 100)

    if verdict == "reject":
        reason = _text(approval.get("reason"), "approval.reason", 2_000)
        for field in ("headline", "take", "editSummary"):
            if approval.get(field) is not None:
                raise ValueError(f"rejected historical approval cannot set {field}")
        approved = None
        approved_headline = None
        approved_take = None
        edit_summary = None
    else:
        if approval.get("reason") is not None:
            raise ValueError("approved historical approval cannot set reason")
        approved_headline = _text(approval.get("headline"), "approval.headline", 300)
        approved_take = _text(approval.get("take"), "approval.take", 8_000)
        edit_summary = _text(approval.get("editSummary"), "approval.editSummary", 2_000)
        reason = "Approved for the Gravel Weekly historical timeline."
        approved = {
            **draft,
            "status": "approved",
            "headline": approved_headline,
            "take": approved_take,
            "takeProvenance": "human_approved",
            "editorialApproval": {"approver": approver, "approvedAt": decided_at},
            "publishedAt": None,
            "updatedAt": decided_at,
            "contentHash": "pending",
        }
        approved["contentHash"] = compute_history_content_hash(approved)
        approved = validate_history_entry(approved)

    receipt = {
        "schemaVersion": DECISION_SCHEMA,
        "entryId": draft["entryId"],
        "reviewedDraftContentHash": draft["contentHash"],
        "decision": verdict,
        "reason": reason,
        "decidedBy": approver,
        "decidedAt": decided_at,
        "suggestedHeadline": draft["headline"],
        "approvedHeadline": approved_headline,
        "suggestedTake": draft["take"],
        "approvedTake": approved_take,
        "editSummary": edit_summary,
    }
    return approved, validate_history_decision(receipt, approved)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("draft", type=Path)
    parser.add_argument("approval", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--decision-output", type=Path)
    args = parser.parse_args()
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    approval = json.loads(args.approval.read_text(encoding="utf-8"))
    approved, receipt = apply_history_decision(draft, approval)
    entry_id = receipt["entryId"]
    decision_output = args.decision_output or STAGED_DIR / f"{entry_id}.decision.json"
    decision_output.parent.mkdir(parents=True, exist_ok=True)
    decision_output.write_text(f"{json.dumps(receipt, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    if approved is None:
        print(f"Rejected and recorded without publication: {decision_output}")
        return 0
    output = args.output or STAGED_DIR / f"{entry_id}.approved.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{json.dumps(approved, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"Approved but not published: {output}")
    print(f"Hash-bound decision staged: {decision_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
