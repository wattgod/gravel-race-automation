#!/usr/bin/env python3
"""Validate the durable human-decision receipt paired with a Gravel Weekly issue."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

try:
    from validate_gravel_weekly import validate_issue
except ModuleNotFoundError:  # Imported as scripts.validate_gravel_weekly_decisions.
    from scripts.validate_gravel_weekly import validate_issue

RECEIPT_SCHEMA = "gravel-weekly-decision-receipt/v2"
DECISION_SCHEMA = "editorial-decision/v1"
QUIET_DECISION_SCHEMA = "editorial-quiet-decision/v1"
OUTER_KEYS = {
    "schemaVersion", "issueId", "publicationDate", "reviewedDraftContentHash",
    "decidedBy", "decidedAt", "decisions", "quietIssueDecision",
}
DECISION_KEYS = {
    "schemaVersion", "issueId", "candidateId", "decision", "reason",
    "decidedBy", "decidedAt", "suggestedCopy", "approvedCopy", "editSummary",
}
QUIET_DECISION_KEYS = {
    "schemaVersion", "issueId", "decision", "reason", "decidedBy", "decidedAt",
    "suggestedHeadline", "suggestedNote", "approvedHeadline", "approvedNote",
    "editSummary",
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


def _iso(value: Any, name: str) -> str:
    text = _text(value, name, 100)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return text


def validate_decision_receipt(value: Any, issue_value: Any) -> dict[str, Any]:
    """Fail closed unless the receipt exactly describes the approved issue copy."""
    issue = validate_issue(issue_value)
    if issue["status"] not in {"approved", "published"}:
        raise ValueError("decision receipts require an approved or published issue")
    receipt = _record(value, "decision receipt")
    unknown = set(receipt) - OUTER_KEYS
    if unknown:
        raise ValueError(f"decision receipt has unsupported fields: {sorted(unknown)}")
    if receipt.get("schemaVersion") != RECEIPT_SCHEMA:
        raise ValueError("unsupported Gravel Weekly decision receipt schema")
    if receipt.get("issueId") != issue["issueId"]:
        raise ValueError("decision receipt issueId does not match issue")
    if receipt.get("publicationDate") != issue["publicationDate"]:
        raise ValueError("decision receipt publicationDate does not match issue")
    draft_hash = _text(receipt.get("reviewedDraftContentHash"), "reviewedDraftContentHash", 64)
    if not re.fullmatch(r"[0-9a-f]{64}", draft_hash):
        raise ValueError("reviewedDraftContentHash must be a lowercase SHA-256 hash")
    decided_by = _text(receipt.get("decidedBy"), "decidedBy", 300)
    decided_at = _iso(receipt.get("decidedAt"), "decidedAt")
    approval = issue["editorialApproval"]
    if decided_by != approval["approver"] or decided_at != approval["approvedAt"]:
        raise ValueError("decision receipt identity and time must match editorial approval")
    if draft_hash != approval["reviewedDraftContentHash"]:
        raise ValueError("decision receipt reviewed draft hash must match editorial approval")

    raw_decisions = receipt.get("decisions")
    if not isinstance(raw_decisions, list):
        raise ValueError("decision receipt decisions must be a list")
    decisions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_value in enumerate(raw_decisions):
        raw = _record(raw_value, f"decisions[{index}]")
        extra = set(raw) - DECISION_KEYS
        if extra:
            raise ValueError(f"decisions[{index}] has unsupported fields: {sorted(extra)}")
        if raw.get("schemaVersion") != DECISION_SCHEMA:
            raise ValueError(f"decisions[{index}] has unsupported schema")
        if raw.get("issueId") != issue["issueId"]:
            raise ValueError(f"decisions[{index}].issueId does not match issue")
        candidate_id = _text(raw.get("candidateId"), f"decisions[{index}].candidateId", 500)
        if candidate_id in seen:
            raise ValueError("decision receipt candidate IDs must be unique")
        seen.add(candidate_id)
        decision = raw.get("decision")
        if decision not in {"approve", "reject"}:
            raise ValueError(f"decisions[{index}].decision must be approve or reject")
        reason = _text(raw.get("reason"), f"decisions[{index}].reason", 2_000)
        if raw.get("decidedBy") != decided_by or raw.get("decidedAt") != decided_at:
            raise ValueError(f"decisions[{index}] identity and time must match receipt")
        approved_copy = raw.get("approvedCopy")
        suggested_copy = raw.get("suggestedCopy")
        edit_summary = raw.get("editSummary")
        if decision == "approve":
            suggested_copy = _text(suggested_copy, f"decisions[{index}].suggestedCopy", 8_000)
            approved_copy = _text(approved_copy, f"decisions[{index}].approvedCopy", 8_000)
            edit_summary = _text(edit_summary, f"decisions[{index}].editSummary", 2_000)
        elif suggested_copy is not None or approved_copy is not None or edit_summary is not None:
            raise ValueError(f"decisions[{index}] rejected decisions cannot carry approved copy")
        decisions.append({
            "schemaVersion": DECISION_SCHEMA,
            "issueId": issue["issueId"],
            "candidateId": candidate_id,
            "decision": decision,
            "reason": reason,
            "decidedBy": decided_by,
            "decidedAt": decided_at,
            "suggestedCopy": suggested_copy,
            "approvedCopy": approved_copy,
            "editSummary": edit_summary,
        })

    approved_by_id = {
        decision["candidateId"]: decision
        for decision in decisions if decision["decision"] == "approve"
    }
    issue_stories = {story["candidateId"]: story for story in issue["stories"]}
    if set(approved_by_id) != set(issue_stories):
        raise ValueError("approved receipt decisions must exactly match issue stories")
    for candidate_id, story in issue_stories.items():
        if approved_by_id[candidate_id]["approvedCopy"] != story["take"]:
            raise ValueError(f"approved copy does not match issue story {candidate_id}")

    quiet_issue = issue.get("quietIssue")
    quiet_raw = receipt.get("quietIssueDecision")
    quiet_decision = None
    if quiet_issue is None:
        if quiet_raw is not None:
            raise ValueError("quietIssueDecision cannot exist for an issue with stories")
        if not decisions:
            raise ValueError("a story issue requires at least one editorial decision")
    else:
        quiet = _record(quiet_raw, "quietIssueDecision")
        extra = set(quiet) - QUIET_DECISION_KEYS
        missing = QUIET_DECISION_KEYS - set(quiet)
        if extra or missing:
            raise ValueError(
                "quietIssueDecision fields are invalid; "
                f"missing={sorted(missing)}, extra={sorted(extra)}"
            )
        if quiet.get("schemaVersion") != QUIET_DECISION_SCHEMA:
            raise ValueError("quietIssueDecision has unsupported schema")
        if quiet.get("issueId") != issue["issueId"]:
            raise ValueError("quietIssueDecision issueId does not match issue")
        if quiet.get("decision") != "approve":
            raise ValueError("quietIssueDecision must approve the quiet issue")
        if quiet.get("decidedBy") != decided_by or quiet.get("decidedAt") != decided_at:
            raise ValueError("quietIssueDecision identity and time must match receipt")
        reason = _text(quiet.get("reason"), "quietIssueDecision.reason", 2_000)
        suggested_headline = quiet.get("suggestedHeadline")
        suggested_note = quiet.get("suggestedNote")
        if (suggested_headline is None) != (suggested_note is None):
            raise ValueError("quietIssueDecision suggested copy must be paired")
        if suggested_headline is not None:
            suggested_headline = _text(
                suggested_headline, "quietIssueDecision.suggestedHeadline", 300
            )
            suggested_note = _text(
                suggested_note, "quietIssueDecision.suggestedNote", 1_000
            )
        approved_headline = _text(
            quiet.get("approvedHeadline"), "quietIssueDecision.approvedHeadline", 300
        )
        approved_note = _text(
            quiet.get("approvedNote"), "quietIssueDecision.approvedNote", 1_000
        )
        edit_summary = _text(
            quiet.get("editSummary"), "quietIssueDecision.editSummary", 2_000
        )
        if (
            approved_headline != quiet_issue["headline"]
            or approved_note != quiet_issue["note"]
        ):
            raise ValueError("quiet issue approved copy does not match the issue")
        quiet_decision = {
            "schemaVersion": QUIET_DECISION_SCHEMA,
            "issueId": issue["issueId"],
            "decision": "approve",
            "reason": reason,
            "decidedBy": decided_by,
            "decidedAt": decided_at,
            "suggestedHeadline": suggested_headline,
            "suggestedNote": suggested_note,
            "approvedHeadline": approved_headline,
            "approvedNote": approved_note,
            "editSummary": edit_summary,
        }

    return {
        "schemaVersion": RECEIPT_SCHEMA,
        "issueId": issue["issueId"],
        "publicationDate": issue["publicationDate"],
        "reviewedDraftContentHash": draft_hash,
        "decidedBy": decided_by,
        "decidedAt": decided_at,
        "decisions": decisions,
        "quietIssueDecision": quiet_decision,
    }
