#!/usr/bin/env python3
"""Turn a Gravel Weekly review artifact into a non-publishable issue draft."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_gravel_weekly import compute_content_hash, validate_issue

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "drafts"


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


def prepare_issue(review_value: Any, publication_date: str, issue_number: int, *, now: str | None = None) -> dict[str, Any]:
    review = _record(review_value, "review")
    if review.get("schemaVersion") != "gravel-weekly-review/v1":
        raise ValueError("unsupported Gravel Weekly review schema")
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
        (candidate for candidate in candidates.values() if candidate.get("score", 0) >= 70 and candidate.get("id") in packets),
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
        })
        all_impacts.extend(impacts)
        source_urls.extend(receipt["canonicalUrl"] for receipt in receipts)

    current = next((story["candidateId"] for story in stories if story["score"] >= 85), None)
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
        "calendarWatch": [],
        "raceImpacts": _dedupe_records(all_impacts),
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
