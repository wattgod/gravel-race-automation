#!/usr/bin/env python3
"""Fail-closed validation for Gravel Weekly historical Current Thing entries."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

from validate_gravel_weekly import IssueValidationError, _impact, _iso, _list, _receipt, _record, _text
from no_ai_slop import audit_no_ai_slop

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "history"
PASSING_GATES = {"party", "point", "friend", "craft", "hostileEditor"}
DEPRECATED_HISTORICAL_RACE_IDS = {
    "gravel:big-sugar-gravel": "gravel:big-sugar",
    "gravel:gravel-locos-150": "gravel:gravel-locos",
    "gravel:rad-dirt-fest": "gravel:the-rad",
    "gravel:sbt-grvl": "gravel:steamboat-gravel",
    "gravel:uci-gravel-world-championships": "gravel:uci-gravel-worlds",
    "gravel:unbound-gravel": "gravel:unbound-200",
    "gravel:unbound-gravel-200": "gravel:unbound-200",
    "gravel:usa-cycling-gravel-national-championships": "gravel:usa-cycling-gravel-nationals",
}


def _day(value: Any, name: str) -> str:
    raw = _text(value, name, 10)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        raise IssueValidationError(f"{name} must be YYYY-MM-DD")
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as exc:
        raise IssueValidationError(f"{name} is invalid") from exc
    return raw


def canonical_history_json(entry: dict[str, Any]) -> str:
    payload = dict(entry)
    payload.pop("contentHash", None)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def compute_history_content_hash(entry: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_history_json(entry).encode("utf-8")).hexdigest()


def _published_timestamp(receipt: dict[str, Any], name: str) -> datetime:
    raw = receipt.get("publishedAt")
    if raw is None:
        raise IssueValidationError(f"{name}.publishedAt is required for historical chronology")
    result = datetime.fromisoformat(_iso(raw, f"{name}.publishedAt").replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise IssueValidationError(f"{name}.publishedAt must include a timezone")
    return result.astimezone(timezone.utc)


def validate_history_entry(value: Any, *, verify_hash: bool = True) -> dict[str, Any]:
    entry = _record(value, "history entry")
    if entry.get("schemaVersion") != "gravel-weekly-history-entry/v1":
        raise IssueValidationError("unsupported Gravel Weekly history schema")
    _text(entry.get("entryId"), "entryId", 500)
    active_from = _day(entry.get("activeFrom"), "activeFrom")
    active_through = _day(entry.get("activeThrough"), "activeThrough")
    active_from_at = datetime.combine(datetime.strptime(active_from, "%Y-%m-%d").date(), time.min, tzinfo=timezone.utc)
    active_through_at = datetime.combine(datetime.strptime(active_through, "%Y-%m-%d").date(), time.max, tzinfo=timezone.utc)
    if active_through_at < active_from_at:
        raise IssueValidationError("activeThrough must not precede activeFrom")
    if (active_through_at - active_from_at).days > 180:
        raise IssueValidationError("historical active period must not exceed 180 days")
    status = entry.get("status")
    if status not in {"draft", "approved", "published"}:
        raise IssueValidationError("history status is invalid")
    headline = _text(entry.get("headline"), "headline", 300)
    _text(entry.get("point"), "point", 1_000)
    _text(entry.get("priorJudgment"), "priorJudgment", 1_000)
    _text(entry.get("changedJudgment"), "changedJudgment", 1_000)
    _text(entry.get("stakes"), "stakes", 1_500)
    _text(entry.get("credibleOpposition"), "credibleOpposition", 1_000)
    what_happened = _text(entry.get("whatHappened"), "whatHappened", 3_000)
    take = _text(entry.get("take"), "take", 8_000)
    _text(entry.get("uncertainty"), "uncertainty", 2_000)
    score = entry.get("editorialScore")
    if not isinstance(score, int) or isinstance(score, bool) or not 85 <= score <= 100:
        raise IssueValidationError("historical Current Thing editorialScore must be 85 to 100")
    provenance = entry.get("takeProvenance")
    if provenance not in {"model_draft", "human_approved"}:
        raise IssueValidationError("takeProvenance is invalid")
    if status != "draft" and provenance != "human_approved":
        raise IssueValidationError("approved historical takes require human-approved provenance")
    if status != "draft" and re.search(r"model draft|not matti(?:’|')s approved", take, re.IGNORECASE):
        raise IssueValidationError("historical take still contains model-draft language")
    if status != "draft" and re.search(r"model draft|not matti(?:’|')s approved", headline, re.IGNORECASE):
        raise IssueValidationError("historical headline still contains model-draft language")
    if status != "draft":
        prose_gate = audit_no_ai_slop({"headline": headline, "what_happened": what_happened, "take": take})
        if prose_gate["verdict"] != "pass":
            findings = ", ".join(f"{finding['field']}:{finding['pattern']}" for finding in prose_gate["findings"])
            raise IssueValidationError(f"historical entry fails the no-ai-slop gate: {findings}")
    gates = _record(entry.get("editorialGates"), "editorialGates")
    if set(gates) != PASSING_GATES:
        raise IssueValidationError("editorialGates must contain the five historical gates")
    for gate_name, verdict in gates.items():
        if verdict not in {"pass", "hold", "fail"}:
            raise IssueValidationError(f"editorialGates.{gate_name} is invalid")
        if status != "draft" and verdict != "pass":
            raise IssueValidationError("approved historical entries require every editorial gate to pass")

    contemporary = _list(entry.get("contemporaryReceipts"), "contemporaryReceipts", 100)
    if not contemporary:
        raise IssueValidationError("contemporaryReceipts must not be empty")
    contemporary_publishers: set[str] = set()
    claim_ids: set[str] = set()
    receipt_keys: set[tuple[str, str]] = set()
    for index, receipt_value in enumerate(contemporary):
        name = f"contemporaryReceipts[{index}]"
        receipt = _receipt(receipt_value, name)
        published_at = _published_timestamp(receipt, name)
        if published_at > active_through_at:
            raise IssueValidationError(f"{name} is later evidence, not contemporary evidence")
        contemporary_publishers.add(receipt["publisher"].strip().casefold())
        claim_ids.add(receipt["claimId"])
        receipt_keys.add((receipt["claimId"], receipt["canonicalUrl"]))
    if status != "draft" and len(contemporary_publishers) < 2:
        raise IssueValidationError("approved historical entries require two contemporary publishers")

    later_evidence = _list(entry.get("laterEvidence"), "laterEvidence", 100)
    for index, receipt_value in enumerate(later_evidence):
        name = f"laterEvidence[{index}]"
        receipt = _receipt(receipt_value, name)
        if _published_timestamp(receipt, name) <= active_through_at:
            raise IssueValidationError(f"{name} must postdate the active period")
        key = (receipt["claimId"], receipt["canonicalUrl"])
        if key in receipt_keys:
            raise IssueValidationError("laterEvidence must not duplicate a contemporary receipt")
        receipt_keys.add(key)
        claim_ids.add(receipt["claimId"])

    for index, impact_value in enumerate(_list(entry.get("raceImpacts"), "raceImpacts", 100)):
        impact = _impact(impact_value, f"raceImpacts[{index}]")
        if impact["impactKind"] != "editorial_review":
            raise IssueValidationError("historical race impacts must be editorial_review")
        replacement = DEPRECATED_HISTORICAL_RACE_IDS.get(impact["raceId"])
        if replacement:
            raise IssueValidationError(
                f"raceImpacts[{index}].raceId is deprecated; use {replacement}"
            )
        missing = set(impact["claimIds"]) - claim_ids
        if missing:
            raise IssueValidationError(f"raceImpacts[{index}] references claims without historical receipts: {sorted(missing)}")
    if entry.get("humanApprovalRequired") is not True or entry.get("autoPublishAllowed") is not False:
        raise IssueValidationError("historical publication safety flags are invalid")
    approval = entry.get("editorialApproval")
    if status != "draft" and not isinstance(approval, dict):
        raise IssueValidationError(f"{status} historical entries require editorial approval")
    if isinstance(approval, dict):
        _text(approval.get("approver"), "editorialApproval.approver", 300)
        _iso(approval.get("approvedAt"), "editorialApproval.approvedAt")
    if status == "published" and entry.get("publishedAt") is None:
        raise IssueValidationError("published historical entries require publishedAt")
    if entry.get("publishedAt") is not None:
        _iso(entry["publishedAt"], "publishedAt")
    _iso(entry.get("updatedAt"), "updatedAt")
    expected = compute_history_content_hash(entry)
    if verify_hash and _text(entry.get("contentHash"), "contentHash", 64) != expected:
        raise IssueValidationError(f"contentHash mismatch: expected {expected}")
    return entry


def load_history_entries(history_dir: Path = HISTORY_DIR) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not history_dir.exists():
        return entries
    for path in sorted(history_dir.glob("*.json")):
        try:
            entries.append(validate_history_entry(json.loads(path.read_text(encoding="utf-8"))))
        except (json.JSONDecodeError, IssueValidationError) as exc:
            raise IssueValidationError(f"{path}: {exc}") from exc
    ids = [entry["entryId"] for entry in entries]
    if len(ids) != len(set(ids)):
        raise IssueValidationError("historical entry IDs must be unique")
    return sorted(entries, key=lambda entry: (entry["activeThrough"], entry["activeFrom"]), reverse=True)


def load_public_history_entries(history_dir: Path = HISTORY_DIR) -> list[dict[str, Any]]:
    """Load only history entries that have cleared the editorial publication boundary."""
    return [entry for entry in load_history_entries(history_dir) if entry["status"] in {"approved", "published"}]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    paths = args.paths or sorted(HISTORY_DIR.glob("*.json"))
    for path in paths:
        validate_history_entry(json.loads(path.read_text(encoding="utf-8")))
        print(f"OK {path}")
    print(f"Validated {len(paths)} Gravel Weekly historical entr{'y' if len(paths) == 1 else 'ies'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
