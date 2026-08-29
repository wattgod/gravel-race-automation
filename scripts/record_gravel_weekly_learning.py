#!/usr/bin/env python3
"""Mirror validated Gravel Weekly learning records into the control plane."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from validate_gravel_weekly import PROJECT_ROOT, validate_issue
from validate_gravel_weekly_learning import (
    impact_with_evidence,
    load_linked_issue,
    validate_learning_source,
)

DEFAULT_ENDPOINT = "https://race-intelligence-control-plane.vercel.app/api/editorial-learning-receipt"
DEFAULT_REPOSITORY = "wattgod/gravel-race-automation"


def _source_commit(value: str | None) -> str:
    commit = value or os.environ.get("GITHUB_SHA")
    if not commit:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT, text=True
        ).strip()
    commit = commit.lower()
    if not re.fullmatch(r"[a-f0-9]{40,64}", commit):
        raise ValueError("source commit must be a full hexadecimal Git commit")
    return commit


def _repository_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("issue path must be inside the source repository") from exc


def build_correction_receipts(
    issue: dict[str, Any],
    *,
    source_repository: str,
    source_path: str,
    source_commit: str,
    source_content_hash: str,
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for correction in issue["corrections"]:
        learning = correction["learning"]
        receipts.append({
            "schemaVersion": "editorial-learning-receipt/v1",
            "kind": "correction",
            "issueId": issue["issueId"],
            "candidateId": correction["storyId"],
            "sourceRepository": source_repository,
            "sourcePath": source_path,
            "sourceCommit": source_commit,
            "sourceContentHash": source_content_hash,
            "recordedBy": learning["recordedBy"],
            "recordedAt": correction["publishedAt"],
            "correction": {
                "failureKey": learning["failureKey"],
                "publishedAt": correction["publishedAt"],
                "originalClaim": learning["originalClaim"],
                "correctedClaim": learning["correctedClaim"],
                "severity": learning["severity"],
                "evidenceUrls": learning["evidenceUrls"],
            },
        })
    return receipts


def build_source_receipt(
    source: dict[str, Any],
    *,
    issue: dict[str, Any] | None,
    source_repository: str,
    source_path: str,
    source_commit: str,
    source_content_hash: str,
) -> dict[str, Any]:
    common = {
        "schemaVersion": "editorial-learning-receipt/v1",
        "kind": source["kind"],
        "issueId": issue["issueId"] if issue else None,
        "candidateId": source["candidateId"],
        "sourceRepository": source_repository,
        "sourcePath": source_path,
        "sourceCommit": source_commit,
        "sourceContentHash": source_content_hash,
        "recordedBy": source["recordedBy"],
        "recordedAt": source["recordedAt"],
    }
    if source["kind"] == "missed_story":
        return {**common, "missedStory": source["missedStory"]}

    decision = source["raceImpactDecision"]
    if issue is None:
        raise ValueError("race-impact decisions require a linked issue")
    impact, evidence_urls = impact_with_evidence(issue, decision["impactId"])
    if decision["implementationUrl"] is not None:
        evidence_urls = list(dict.fromkeys([*evidence_urls, decision["implementationUrl"]]))
    vertical, race_slug = impact["raceId"].split(":", 1)
    return {
        **common,
        "raceImpactDecision": {
            "impactId": decision["impactId"],
            "vertical": vertical,
            "raceSlug": race_slug,
            "fieldPath": impact["fieldPath"] or "catalog",
            "outcome": decision["outcome"],
            "reason": decision["reason"],
            "decidedAt": decision["decidedAt"],
            "evidenceUrls": evidence_urls,
            "implementationUrl": decision["implementationUrl"],
            "regressionTest": decision["regressionTest"],
        },
    }


def post_receipts(receipts: list[dict[str, Any]], endpoint: str, secret: str) -> list[dict[str, Any]]:
    responses: list[dict[str, Any]] = []
    for receipt in receipts:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(receipt, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1_000]
            raise RuntimeError(f"control-plane learning receipt rejected with HTTP {exc.code}: {detail}") from exc
        if not isinstance(payload, dict) or payload.get("accepted") is not True:
            raise RuntimeError("control plane did not acknowledge the learning receipt")
        responses.append(payload)
    return responses


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("issue", nargs="?", type=Path)
    parser.add_argument("--learning-source", action="append", default=[], type=Path)
    parser.add_argument("--endpoint", default=os.environ.get("CONTROL_PLANE_EDITORIAL_LEARNING_URL", DEFAULT_ENDPOINT))
    parser.add_argument("--source-repository", default=DEFAULT_REPOSITORY)
    parser.add_argument("--source-commit")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.issue is None and not args.learning_source:
        parser.error("provide an issue or at least one --learning-source")
    commit = _source_commit(args.source_commit)
    receipts: list[dict[str, Any]] = []
    if args.issue is not None:
        source_bytes = args.issue.read_bytes()
        issue = validate_issue(json.loads(source_bytes.decode("utf-8")))
        if issue["status"] != "published":
            raise SystemExit("learning receipts require a published issue snapshot")
        receipts.extend(build_correction_receipts(
            issue,
            source_repository=args.source_repository,
            source_path=_repository_relative(args.issue),
            source_commit=commit,
            source_content_hash=hashlib.sha256(source_bytes).hexdigest(),
        ))
    for learning_path in args.learning_source:
        learning_bytes = learning_path.read_bytes()
        source = json.loads(learning_bytes.decode("utf-8"))
        issue_value = load_linked_issue(source)
        validated = validate_learning_source(source, issue_value)
        linked_issue = validate_issue(issue_value) if issue_value is not None else None
        receipts.append(build_source_receipt(
            validated,
            issue=linked_issue,
            source_repository=args.source_repository,
            source_path=_repository_relative(learning_path),
            source_commit=commit,
            source_content_hash=hashlib.sha256(learning_bytes).hexdigest(),
        ))
    if args.dry_run:
        print(json.dumps(receipts, ensure_ascii=False, indent=2))
        return 0
    if not receipts:
        print("Recorded 0 Gravel Weekly learning receipt(s)")
        return 0
    secret = os.environ.get("CONTROL_PLANE_INGEST_SECRET")
    if not secret:
        raise SystemExit("CONTROL_PLANE_INGEST_SECRET is required")
    responses = post_receipts(receipts, args.endpoint, secret)
    recorded = sum(response.get("recorded") is True for response in responses)
    replayed = len(responses) - recorded
    print(f"Recorded {recorded} Gravel Weekly learning receipt(s); {replayed} idempotent replay(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
