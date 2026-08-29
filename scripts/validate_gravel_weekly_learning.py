#!/usr/bin/env python3
"""Validate human-authored Gravel Weekly learning source records."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gravel_weekly_race_impacts import race_impact_hash, race_impact_id
from validate_gravel_weekly import ISSUE_DIR, IssueValidationError, _record, _text, _url, validate_issue

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEARNING_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "learning"
SCHEMA_VERSION = "gravel-weekly-learning-source/v1"
OUTER_KEYS = {
    "schemaVersion", "kind", "issueDate", "issueContentHash", "candidateId",
    "recordedBy", "recordedAt", "raceImpactDecision", "missedStory",
}
RACE_DECISION_KEYS = {
    "impactId", "reviewedImpactHash", "outcome", "reason", "decidedAt",
    "implementationUrl", "regressionTest",
}
MISSED_STORY_KEYS = {
    "failureKey", "headline", "whyImportant", "sourceUrl", "publishedAt",
    "discoveredAt",
}


def _exact_keys(value: dict[str, Any], expected: set[str], name: str) -> None:
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown or missing:
        raise IssueValidationError(
            f"{name} fields are invalid; missing={sorted(missing)}, extra={sorted(unknown)}"
        )


def _timestamp(value: Any, name: str) -> str:
    raw = _text(value, name, 100)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IssueValidationError(f"{name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise IssueValidationError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _nullable_text(value: Any, name: str, maximum: int) -> str | None:
    return None if value is None else _text(value, name, maximum)


def _linked_issue(source: dict[str, Any], issue_value: Any | None) -> dict[str, Any] | None:
    issue_date = source.get("issueDate")
    issue_hash = source.get("issueContentHash")
    if (issue_date is None) != (issue_hash is None):
        raise IssueValidationError("issueDate and issueContentHash must be paired")
    if issue_date is None:
        if issue_value is not None:
            raise IssueValidationError("an unlinked learning source cannot receive an issue")
        return None
    if not isinstance(issue_date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", issue_date):
        raise IssueValidationError("issueDate must be YYYY-MM-DD")
    issue = validate_issue(issue_value)
    if issue["status"] != "published":
        raise IssueValidationError("learning sources may link only to a published issue")
    if issue["publicationDate"] != issue_date:
        raise IssueValidationError("issueDate does not match the linked issue")
    if issue["contentHash"] != issue_hash:
        raise IssueValidationError("issueContentHash does not match the linked issue")
    return issue


def impact_with_evidence(issue: dict[str, Any], impact_id_value: str) -> tuple[dict[str, Any], list[str]]:
    matches = [impact for impact in issue["raceImpacts"] if race_impact_id(impact) == impact_id_value]
    if len(matches) != 1:
        raise IssueValidationError("raceImpactDecision.impactId must identify exactly one issue impact")
    impact = matches[0]
    if impact["impactKind"] == "no_change":
        raise IssueValidationError("no_change context cannot receive a race-impact disposition")
    receipts = {
        receipt["claimId"]: receipt["canonicalUrl"]
        for story in issue["stories"] for receipt in story["receipts"]
    }
    return impact, list(dict.fromkeys(receipts[claim_id] for claim_id in impact["claimIds"]))


def validate_learning_source(value: Any, issue_value: Any | None = None) -> dict[str, Any]:
    source = _record(value, "learning source")
    _exact_keys(source, OUTER_KEYS, "learning source")
    if source.get("schemaVersion") != SCHEMA_VERSION:
        raise IssueValidationError("unsupported Gravel Weekly learning source schema")
    kind = source.get("kind")
    if kind not in {"race_impact_decision", "missed_story"}:
        raise IssueValidationError("learning source kind is invalid")
    issue = _linked_issue(source, issue_value)
    candidate_id = _nullable_text(source.get("candidateId"), "candidateId", 500)
    _text(source.get("recordedBy"), "recordedBy", 300)
    recorded_at = _timestamp(source.get("recordedAt"), "recordedAt")

    if kind == "race_impact_decision":
        if issue is None or candidate_id is None:
            raise IssueValidationError("race-impact decisions require a linked issue and candidateId")
        if source.get("missedStory") is not None:
            raise IssueValidationError("race-impact decisions cannot carry missedStory")
        decision = _record(source.get("raceImpactDecision"), "raceImpactDecision")
        _exact_keys(decision, RACE_DECISION_KEYS, "raceImpactDecision")
        impact_id_value = _text(decision.get("impactId"), "raceImpactDecision.impactId", 12)
        if not re.fullmatch(r"[a-f0-9]{12}", impact_id_value):
            raise IssueValidationError("raceImpactDecision.impactId must be 12 lowercase hexadecimal characters")
        impact, _ = impact_with_evidence(issue, impact_id_value)
        full_hash = _text(decision.get("reviewedImpactHash"), "raceImpactDecision.reviewedImpactHash", 64)
        if full_hash != race_impact_hash(impact):
            raise IssueValidationError("raceImpactDecision.reviewedImpactHash does not match the issue impact")
        story = next((item for item in issue["stories"] if item["candidateId"] == candidate_id), None)
        if story is None or not any(race_impact_id(item) == impact_id_value for item in story["raceImpacts"]):
            raise IssueValidationError("candidateId does not own the reviewed impact")
        outcome = decision.get("outcome")
        if outcome not in {"accepted", "rejected", "superseded"}:
            raise IssueValidationError("raceImpactDecision.outcome is invalid")
        _text(decision.get("reason"), "raceImpactDecision.reason", 2_000)
        if _timestamp(decision.get("decidedAt"), "raceImpactDecision.decidedAt") != recorded_at:
            raise IssueValidationError("raceImpactDecision.decidedAt must equal recordedAt")
        implementation_url = decision.get("implementationUrl")
        regression_test = decision.get("regressionTest")
        if outcome == "accepted":
            _url(implementation_url, "raceImpactDecision.implementationUrl")
            _text(regression_test, "raceImpactDecision.regressionTest", 500)
        elif implementation_url is not None or regression_test is not None:
            raise IssueValidationError("only accepted race impacts may carry implementation proof")
    else:
        if source.get("raceImpactDecision") is not None:
            raise IssueValidationError("missed stories cannot carry raceImpactDecision")
        if issue is not None and candidate_id is not None and not any(
            story["candidateId"] == candidate_id for story in issue["stories"]
        ):
            raise IssueValidationError("candidateId does not resolve in the linked issue")
        missed = _record(source.get("missedStory"), "missedStory")
        _exact_keys(missed, MISSED_STORY_KEYS, "missedStory")
        failure_key = _text(missed.get("failureKey"), "missedStory.failureKey", 100)
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,99}", failure_key):
            raise IssueValidationError("missedStory.failureKey must be a lowercase slug")
        _text(missed.get("headline"), "missedStory.headline", 500)
        _text(missed.get("whyImportant"), "missedStory.whyImportant", 2_000)
        _url(missed.get("sourceUrl"), "missedStory.sourceUrl")
        published_at = _timestamp(missed.get("publishedAt"), "missedStory.publishedAt")
        discovered_at = _timestamp(missed.get("discoveredAt"), "missedStory.discoveredAt")
        if datetime.fromisoformat(discovered_at.replace("Z", "+00:00")) <= datetime.fromisoformat(published_at.replace("Z", "+00:00")):
            raise IssueValidationError("missedStory.discoveredAt must be after publishedAt")
        if datetime.fromisoformat(recorded_at.replace("Z", "+00:00")) < datetime.fromisoformat(discovered_at.replace("Z", "+00:00")):
            raise IssueValidationError("recordedAt cannot predate missedStory.discoveredAt")
    return source


def load_linked_issue(source: dict[str, Any]) -> dict[str, Any] | None:
    issue_date = source.get("issueDate")
    if issue_date is None:
        return None
    path = ISSUE_DIR / f"{issue_date}.json"
    if not path.exists():
        raise IssueValidationError(f"linked issue not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_learning_sources(learning_dir: Path = LEARNING_DIR) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    identities: set[tuple[str, ...]] = set()
    for path in sorted(learning_dir.glob("*.json")):
        try:
            source = json.loads(path.read_text(encoding="utf-8"))
            validated = validate_learning_source(source, load_linked_issue(source))
        except (json.JSONDecodeError, IssueValidationError) as exc:
            raise IssueValidationError(f"{path}: {exc}") from exc
        if validated["kind"] == "race_impact_decision":
            identity = (
                "race_impact_decision", validated["issueDate"],
                validated["raceImpactDecision"]["impactId"],
            )
        else:
            identity = (
                "missed_story", validated["missedStory"]["failureKey"],
                validated["missedStory"]["sourceUrl"],
                validated["missedStory"]["publishedAt"],
            )
        if identity in identities:
            raise IssueValidationError(f"duplicate Gravel Weekly learning source identity: {identity}")
        identities.add(identity)
        sources.append(validated)
    return sources


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    if not args.paths:
        sources = load_learning_sources()
        print(f"Validated {len(sources)} Gravel Weekly learning source(s)")
        return 0
    paths = args.paths
    for path in paths:
        source = json.loads(path.read_text(encoding="utf-8"))
        validate_learning_source(source, load_linked_issue(source))
        print(f"OK {path}")
    print(f"Validated {len(paths)} Gravel Weekly learning source(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
