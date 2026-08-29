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

from validate_gravel_weekly import IssueValidationError, _impact, _iso, _list, _receipt, _record, _text, _url
from no_ai_slop import audit_no_ai_slop

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "history"
PASSING_GATES = {"party", "point", "friend", "craft", "hostileEditor"}
CULTURE_SOURCE_KINDS = {"bluesky", "x", "instagram", "youtube", "forum", "blog", "newsletter", "podcast"}
CULTURE_COLLECTION_METHODS = {
    "official_api", "authorized_caption", "rss", "sitemap",
    "public_metadata", "user_authorized",
}
CULTURE_RIGHTS_POLICIES = {
    "metadata_only", "short_excerpt_and_canonical_link",
    "timestamped_short_excerpt",
}
CULTURE_ARTIFACT_KEYS = {
    "artifactId", "sourceKind", "publisher", "author", "canonicalUrl",
    "publishedAt", "title", "excerpt", "timestampSeconds", "topicTags",
    "reviewReason", "collectionMethod", "rightsPolicy", "purpose",
    "canProveClaim", "canEstablishConsensus",
}
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


def _culture_artifact(value: Any, name: str) -> dict[str, Any]:
    artifact = _record(value, name)
    unknown = set(artifact) - CULTURE_ARTIFACT_KEYS
    if unknown:
        raise IssueValidationError(f"{name} has unsupported fields: {sorted(unknown)}")
    _text(artifact.get("artifactId"), f"{name}.artifactId", 500)
    if artifact.get("sourceKind") not in CULTURE_SOURCE_KINDS:
        raise IssueValidationError(f"{name}.sourceKind is invalid")
    _text(artifact.get("publisher"), f"{name}.publisher", 300)
    if artifact.get("author") is not None:
        _text(artifact["author"], f"{name}.author", 300)
    _url(artifact.get("canonicalUrl"), f"{name}.canonicalUrl")
    _iso(artifact.get("publishedAt"), f"{name}.publishedAt")
    _text(artifact.get("title"), f"{name}.title", 500)
    if artifact.get("excerpt") is not None:
        _text(artifact["excerpt"], f"{name}.excerpt", 280)
    timestamp = artifact.get("timestampSeconds")
    if timestamp is not None and (
        not isinstance(timestamp, int) or isinstance(timestamp, bool)
        or timestamp < 0 or timestamp > 86_400
    ):
        raise IssueValidationError(f"{name}.timestampSeconds is invalid")
    if artifact.get("collectionMethod") == "authorized_caption" and timestamp is None:
        raise IssueValidationError(f"{name}.timestampSeconds is required for an authorized caption")
    topics = _list(artifact.get("topicTags"), f"{name}.topicTags", 10)
    if not topics:
        raise IssueValidationError(f"{name}.topicTags must not be empty")
    for index, topic in enumerate(topics):
        raw = _text(topic, f"{name}.topicTags[{index}]", 64)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]+", raw):
            raise IssueValidationError(f"{name}.topicTags[{index}] is invalid")
    if len(topics) != len(set(topics)):
        raise IssueValidationError(f"{name}.topicTags must be unique")
    _text(artifact.get("reviewReason"), f"{name}.reviewReason", 1_000)
    if artifact.get("collectionMethod") not in CULTURE_COLLECTION_METHODS:
        raise IssueValidationError(f"{name}.collectionMethod is invalid")
    if artifact.get("rightsPolicy") not in CULTURE_RIGHTS_POLICIES:
        raise IssueValidationError(f"{name}.rightsPolicy is invalid")
    if artifact.get("purpose") != "culture_sensor":
        raise IssueValidationError(f"{name}.purpose must be culture_sensor")
    if artifact.get("canProveClaim") is not False:
        raise IssueValidationError(f"{name}.canProveClaim must be false")
    if artifact.get("canEstablishConsensus") is not False:
        raise IssueValidationError(f"{name}.canEstablishConsensus must be false")
    return artifact


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
    non_passing_gates = {
        gate_name for gate_name, verdict in gates.items() if verdict != "pass"
    }
    gate_notes_value = entry.get("editorialGateNotes")
    if non_passing_gates:
        if not isinstance(gate_notes_value, dict):
            raise IssueValidationError(
                "editorialGateNotes must contain exactly the non-passing editorial gates"
            )
        gate_notes = _record(gate_notes_value, "editorialGateNotes")
        if set(gate_notes) != non_passing_gates:
            raise IssueValidationError(
                "editorialGateNotes must contain exactly the non-passing editorial gates"
            )
        for gate_name, note in gate_notes.items():
            _text(note, f"editorialGateNotes.{gate_name}", 1_000)
    elif gate_notes_value is not None:
        gate_notes = _record(gate_notes_value, "editorialGateNotes")
        if gate_notes:
            raise IssueValidationError(
                "editorialGateNotes must be empty when every editorial gate passes"
            )

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

    culture_artifacts = _list(entry.get("cultureArtifacts", []), "cultureArtifacts", 6)
    culture_ids: set[str] = set()
    culture_urls: set[str] = set()
    for index, artifact_value in enumerate(culture_artifacts):
        name = f"cultureArtifacts[{index}]"
        artifact = _culture_artifact(artifact_value, name)
        published_at = datetime.fromisoformat(
            _iso(artifact["publishedAt"], f"{name}.publishedAt").replace("Z", "+00:00")
        ).astimezone(timezone.utc)
        if not active_from_at <= published_at <= active_through_at:
            raise IssueValidationError(f"{name} must be dated inside the historical active period")
        if artifact["artifactId"] in culture_ids or artifact["canonicalUrl"] in culture_urls:
            raise IssueValidationError("cultureArtifacts must have unique IDs and canonical URLs")
        culture_ids.add(artifact["artifactId"])
        culture_urls.add(artifact["canonicalUrl"])

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
    return [entry for entry in load_history_entries(history_dir) if entry["status"] == "published"]


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
