#!/usr/bin/env python3
"""Validate a hash-bound human decision for one historical narrative entry."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from validate_gravel_weekly_history import validate_history_entry

DECISION_SCHEMA = "gravel-weekly-history-decision/v1"
DECISION_KEYS = {
    "schemaVersion",
    "entryId",
    "reviewedDraftContentHash",
    "decision",
    "reason",
    "decidedBy",
    "decidedAt",
    "suggestedHeadline",
    "approvedHeadline",
    "suggestedTake",
    "approvedTake",
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


def _optional_text(value: Any, name: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _text(value, name, maximum)


def _timestamp(value: Any, name: str) -> str:
    raw = _text(value, name, 100)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return raw


def validate_history_decision(value: Any, approved_value: Any | None = None) -> dict[str, Any]:
    """Validate a decision and, for approvals, bind it to the staged entry."""
    decision = _record(value, "historical decision")
    unknown = set(decision) - DECISION_KEYS
    missing = DECISION_KEYS - set(decision)
    if unknown or missing:
        raise ValueError(
            f"historical decision fields mismatch; missing={sorted(missing)}, extra={sorted(unknown)}"
        )
    if decision.get("schemaVersion") != DECISION_SCHEMA:
        raise ValueError("unsupported Gravel Weekly historical decision schema")
    _text(decision.get("entryId"), "entryId", 500)
    reviewed_hash = _text(decision.get("reviewedDraftContentHash"), "reviewedDraftContentHash", 64)
    if not re.fullmatch(r"[0-9a-f]{64}", reviewed_hash):
        raise ValueError("reviewedDraftContentHash must be a SHA-256 hex digest")
    verdict = decision.get("decision")
    if verdict not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    _text(decision.get("reason"), "reason", 2_000)
    _text(decision.get("decidedBy"), "decidedBy", 300)
    _timestamp(decision.get("decidedAt"), "decidedAt")
    _text(decision.get("suggestedHeadline"), "suggestedHeadline", 300)
    _text(decision.get("suggestedTake"), "suggestedTake", 8_000)

    approved_headline = _optional_text(decision.get("approvedHeadline"), "approvedHeadline", 300)
    approved_take = _optional_text(decision.get("approvedTake"), "approvedTake", 8_000)
    edit_summary = _optional_text(decision.get("editSummary"), "editSummary", 2_000)
    if verdict == "approve" and not all((approved_headline, approved_take, edit_summary)):
        raise ValueError("approved historical decisions require approved copy and an edit summary")
    if verdict == "reject" and any((approved_headline, approved_take, edit_summary)):
        raise ValueError("rejected historical decisions cannot carry approved copy")

    if approved_value is not None:
        approved = validate_history_entry(approved_value)
        if verdict != "approve":
            raise ValueError("a staged approved entry requires an approve decision")
        if approved["status"] not in {"approved", "published"}:
            raise ValueError("decision binding requires an approved or published history entry")
        if decision["entryId"] != approved["entryId"]:
            raise ValueError("historical decision entryId does not match the approved entry")
        if approved_headline != approved["headline"]:
            raise ValueError("approved headline does not match the approved entry")
        if approved_take != approved["take"]:
            raise ValueError("approved take does not match the approved entry")
        approval = approved["editorialApproval"]
        if decision["decidedBy"] != approval["approver"] or decision["decidedAt"] != approval["approvedAt"]:
            raise ValueError("historical decision identity does not match editorial approval")
    return decision
