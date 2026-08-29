#!/usr/bin/env python3
"""Turn a Gravel Weekly review artifact into a non-publishable issue draft."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from no_ai_slop import audit_no_ai_slop
from validate_gravel_weekly import compute_content_hash, validate_issue

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "drafts"
COMEDY_MECHANICS = {
    "incongruity", "misdirection", "escalation", "specificity", "rule_of_three",
    "self_deprecation", "analogy", "callback", "straight_for_sensitivity",
}


def _record(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _first_sentence(value: str, maximum: int = 420) -> str:
    compact = " ".join(value.split())
    stop = compact.find(". ")
    sentence = compact[: stop + 1] if stop >= 0 else compact
    return sentence[:maximum].rstrip()


def _dedupe_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        key = json.dumps(record, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        unique[key] = record
    return list(unique.values())


def _passes_editorial_gate(packet: dict[str, Any]) -> bool:
    """Fail closed unless party, point, friend, and story/comedy gates are explicit."""
    gate = packet.get("editorialGate")
    if not isinstance(gate, dict) or gate.get("decision") != "pass":
        return False
    party = gate.get("partyTest")
    point = gate.get("pointTest")
    friend = gate.get("friendTest")
    arc = gate.get("storyArc")
    comedy = gate.get("comedy")
    if not all(isinstance(item, dict) for item in (party, point, friend, arc, comedy)):
        return False
    if (
        party.get("verdict") != "pass"
        or point.get("verdict") != "pass"
        or friend.get("verdict") != "pass"
        or friend.get("killReason") != "none"
    ):
        return False
    required_text = (
        party.get("rationale"), point.get("point"),
        *(friend.get(key) for key in ("repeatableLine", "nonObviousPayoff", "changedUnderstanding", "socialCost")),
        *(arc.get(key) for key in ("hook", "stakes", "tension", "turn", "landing")),
        *(comedy.get(key) for key in ("setup", "turn", "tag", "rhetoricalLicense", "factualBoundary")),
    )
    if not all(isinstance(value, str) and value.strip() for value in required_text):
        return False
    mechanics = comedy.get("mechanics")
    return (
        isinstance(mechanics, list)
        and 1 <= len(mechanics) <= 3
        and len(set(mechanics)) == len(mechanics)
        and all(mechanic in COMEDY_MECHANICS for mechanic in mechanics)
    )


def _passes_prose_gate(packet: dict[str, Any]) -> bool:
    """Recompute the exact publishable copy and reject missing, failed, or stale gates."""
    suggested = packet.get("suggestedTake")
    if not isinstance(suggested, dict) or suggested.get("label") != "model_draft":
        return False
    fields = {
        "headline": packet.get("suggestedHeadline"),
        "dek": packet.get("suggestedDek"),
        "what_happened": packet.get("whatHappened"),
        "take": suggested.get("copy"),
    }
    if not all(isinstance(value, str) and value.strip() for value in fields.values()):
        return False
    expected = audit_no_ai_slop(fields)
    supplied = packet.get("proseGate")
    return bool(
        isinstance(supplied, dict)
        and supplied.get("schemaVersion") == expected["schemaVersion"]
        and supplied.get("sourceUrl") == expected["sourceUrl"]
        and supplied.get("sourceRevision") == expected["sourceRevision"]
        and supplied.get("checkedTextHash") == expected["checkedTextHash"]
        and supplied.get("verdict") == "pass"
        and supplied.get("findings") == []
        and supplied.get("humanApprovalRequired") is True
        and supplied.get("autoPublishAllowed") is False
        and expected["verdict"] == "pass"
    )


def _culture_artifacts(packet: dict[str, Any], candidate_id: str) -> list[dict[str, Any]]:
    culture_read = packet.get("cultureRead")
    if culture_read is None:
        return []
    culture_read = _record(culture_read, f"packet {candidate_id} cultureRead")
    artifacts = culture_read.get("artifacts", [])
    if not isinstance(artifacts, list) or len(artifacts) > 6:
        raise ValueError(f"packet {candidate_id} cultureRead.artifacts must contain at most 6 items")
    if artifacts and culture_read.get("relevance") != "direct":
        raise ValueError(f"packet {candidate_id} culture artifacts require direct relevance")
    source_urls = culture_read.get("sourceUrls", [])
    if not isinstance(source_urls, list) or any(not isinstance(url, str) for url in source_urls):
        raise ValueError(f"packet {candidate_id} cultureRead.sourceUrls is invalid")
    copied: list[dict[str, Any]] = []
    for index, artifact in enumerate(artifacts):
        item = _record(artifact, f"packet {candidate_id} cultureRead.artifacts[{index}]")
        if item.get("canonicalUrl") not in source_urls:
            raise ValueError(f"packet {candidate_id} culture artifact is outside the bounded panel")
        copied.append(dict(item))
    return copied


def _scene_items(
    packet: dict[str, Any], candidate_id: str, key: str, maximum: int
) -> list[dict[str, Any]]:
    value = packet.get(key, [])
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(
            f"packet {candidate_id} {key} must contain at most {maximum} items"
        )
    return [
        dict(_record(item, f"packet {candidate_id} {key}[{index}]"))
        for index, item in enumerate(value)
    ]


def prepare_issue(review_value: Any, publication_date: str, issue_number: int, *, now: str | None = None) -> dict[str, Any]:
    review = _record(review_value, "review")
    if review.get("schemaVersion") != "gravel-weekly-review/v1":
        raise ValueError("unsupported Gravel Weekly review schema")
    model_errors = review.get("modelErrors", [])
    if not isinstance(model_errors, list) or any(
        not isinstance(error, str) or not error.strip() for error in model_errors
    ):
        raise ValueError("review.modelErrors must be an array of non-empty strings")
    fallback_candidates = [
        packet.get("candidateId", "unknown")
        for packet in review.get("packets", [])
        if isinstance(packet, dict)
        and packet.get("generatorModel") == "deterministic-fallback"
    ]
    if model_errors or fallback_candidates:
        details = []
        if model_errors:
            details.append(f"{len(model_errors)} model error(s)")
        if fallback_candidates:
            details.append(
                "deterministic fallback for " + ", ".join(map(str, fallback_candidates))
            )
        raise ValueError(
            "cannot prepare a Gravel Weekly issue from an incomplete editorial review: "
            + "; ".join(details)
            + ". Replay the same locked window after restoring model evaluation."
        )
    if issue_number < 1:
        raise ValueError("issue_number must be positive")
    datetime.strptime(publication_date, "%Y-%m-%d")
    generated_at = now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    candidates = {
        item["id"]: item
        for item in review.get("candidates", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    packets = {
        item["candidateId"]: item
        for item in review.get("packets", [])
        if isinstance(item, dict) and isinstance(item.get("candidateId"), str)
    }
    ranked = sorted(
        (
            candidate for candidate in candidates.values()
            if candidate.get("score", 0) >= 70
            and candidate.get("id") in packets
            and _passes_editorial_gate(packets[candidate["id"]])
            and _passes_prose_gate(packets[candidate["id"]])
        ),
        key=lambda candidate: (-candidate["score"], candidate["id"]),
    )
    stories: list[dict[str, Any]] = []
    all_impacts: list[dict[str, Any]] = []
    source_urls: list[str] = []
    for candidate in ranked:
        packet = packets[candidate["id"]]
        suggested = _record(packet.get("suggestedTake"), f"packet {candidate['id']} suggestedTake")
        copy = suggested.get("copy")
        if suggested.get("label") != "model_draft" or not isinstance(copy, str) or not copy.strip():
            raise ValueError(f"packet {candidate['id']} lacks a labeled model draft")
        impacts = packet.get("raceImpacts", [])
        receipts = packet.get("receipts", [])
        if not isinstance(impacts, list) or not isinstance(receipts, list):
            raise ValueError(f"packet {candidate['id']} has invalid impacts or receipts")
        culture_artifacts = _culture_artifacts(packet, candidate["id"])
        cast = _scene_items(packet, candidate["id"], "cast", 8)
        field_notes = _scene_items(packet, candidate["id"], "fieldNotes", 6)
        stories.append({
            "candidateId": candidate["id"],
            "headline": packet.get("suggestedHeadline") or candidate["headline"],
            "dek": packet.get("suggestedDek") or _first_sentence(packet["whatHappened"]),
            "storyKind": candidate["storyKind"],
            "score": candidate["score"],
            "whatHappened": packet["whatHappened"],
            "take": copy,
            "takeProvenance": "model_draft",
            "receipts": receipts,
            "raceImpacts": impacts,
            "cultureArtifacts": culture_artifacts,
            "cast": cast,
            "fieldNotes": field_notes,
        })
        all_impacts.extend(impacts)
        source_urls.extend(receipt["canonicalUrl"] for receipt in receipts)
        source_urls.extend(artifact["canonicalUrl"] for artifact in culture_artifacts)

    current = next((story["candidateId"] for story in stories if story["score"] >= 85), None)
    quiet_issue = None if stories else {
        "headline": "Nothing cleared the gate this week.",
        "note": (
            "The Friday deadline does not turn an update into a story. "
            "Gravel Weekly will be back when there is a point worth making."
        ),
        "provenance": "model_draft",
    }
    issue = {
        "schemaVersion": "gravel-weekly-issue/v1",
        "issueId": f"gravel-weekly-{issue_number:03d}",
        "issueNumber": issue_number,
        "publicationDate": publication_date,
        "status": "draft",
        "slug": publication_date,
        "title": f"Gravel Weekly — {datetime.strptime(publication_date, '%Y-%m-%d').strftime('%B %-d, %Y')}",
        "mastheadDeck": "The people, races, money and bad ideas moving gravel.",
        "currentThingStoryId": current,
        "stories": stories,
        "quietIssue": quiet_issue,
        "calendarWatch": [],
        "raceImpacts": _dedupe_records(all_impacts),
        "retrospectives": [],
        "corrections": [],
        "sourceIndex": sorted(set(source_urls)),
        "editorialApproval": None,
        "publishedAt": None,
        "updatedAt": generated_at,
        "contentHash": "pending",
    }
    issue["contentHash"] = compute_content_hash(issue)
    return validate_issue(issue)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review", type=Path)
    parser.add_argument("--publication-date", required=True)
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    issue = prepare_issue(json.loads(args.review.read_text(encoding="utf-8")), args.publication_date, args.issue_number)
    output = args.output or DRAFT_DIR / f"{args.publication_date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{json.dumps(issue, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"Prepared non-publishable draft: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
