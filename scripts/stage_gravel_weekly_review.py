#!/usr/bin/env python3
"""Stage one trusted control-plane review as a private Gravel Weekly draft."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from prepare_gravel_weekly_issue import prepare_issue
from validate_gravel_weekly import ISSUE_DIR, load_issues

SOURCE_REPOSITORY = "wattgod/race-intelligence-control-plane"
ACCEPTED_SOURCE_WORKFLOWS = {
    ".github/workflows/race-intelligence.yml": (
        "Race intelligence review",
        "race-intelligence-{run_id}",
    ),
    ".github/workflows/gravel-weekly-editorial-replay.yml": (
        "Gravel Weekly fast editorial replay",
        "gravel-weekly-editorial-{run_id}",
    ),
}


def _record(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def _utc(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def validate_source_run(value: Any) -> dict[str, Any]:
    """Accept only successful main-branch runs from the two editorial workflows."""
    run = _record(value, "source run")
    repository = _record(run.get("repository"), "source run.repository")
    if repository.get("full_name") != SOURCE_REPOSITORY:
        raise ValueError("source run repository is not trusted")
    run_id = run.get("id")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        raise ValueError("source run id must be a positive integer")
    if run.get("head_branch") != "main" or run.get("conclusion") != "success":
        raise ValueError("source workflow must be a successful main-branch run")
    if run.get("event") not in {"schedule", "workflow_dispatch"}:
        raise ValueError("source workflow event is not accepted")
    head_sha = run.get("head_sha")
    if not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise ValueError("source run head SHA is invalid")
    raw_path = run.get("path")
    if not isinstance(raw_path, str):
        raise ValueError("source workflow path is missing")
    workflow_path = raw_path.split("@", 1)[0]
    accepted = ACCEPTED_SOURCE_WORKFLOWS.get(workflow_path)
    if accepted is None:
        raise ValueError("source workflow is not an accepted Gravel Weekly producer")
    expected_name, artifact_template = accepted
    if run.get("name") != expected_name:
        raise ValueError("source workflow name does not match its trusted path")
    html_url = run.get("html_url")
    expected_url = f"https://github.com/{SOURCE_REPOSITORY}/actions/runs/{run_id}"
    if html_url != expected_url:
        raise ValueError("source run URL is invalid")
    return {
        "repository": SOURCE_REPOSITORY,
        "runId": run_id,
        "workflow": expected_name,
        "workflowPath": workflow_path,
        "artifactName": artifact_template.format(run_id=run_id),
        "headSha": head_sha,
        "event": run["event"],
        "createdAt": _utc(run.get("created_at"), "source run.created_at").isoformat().replace("+00:00", "Z"),
        "htmlUrl": html_url,
    }


def derive_weekly_identity(
    review_value: Any,
    *,
    issue_dir: Path = ISSUE_DIR,
) -> tuple[str, int]:
    """Bind the draft date and serial number to the locked Friday window."""
    review = _record(review_value, "review")
    started = _utc(review.get("windowStartedAt"), "review.windowStartedAt")
    ended = _utc(review.get("windowEndedAt"), "review.windowEndedAt")
    if ended - started != timedelta(days=7):
        raise ValueError("Gravel Weekly staging requires an exact seven-day window")
    if ended.weekday() != 4 or (ended.hour, ended.minute, ended.second, ended.microsecond) != (15, 30, 0, 0):
        raise ValueError("Gravel Weekly staging requires the locked Friday 15:30 UTC close")
    publication_date = ended.date().isoformat()
    issues = load_issues(issue_dir)
    if any(issue["publicationDate"] == publication_date for issue in issues):
        raise ValueError(
            f"a canonical Gravel Weekly snapshot already exists for {publication_date}; "
            "a replay cannot replace publication history"
        )
    issue_number = max((issue["issueNumber"] for issue in issues), default=0) + 1
    return publication_date, issue_number


def stage_review(
    review_value: Any,
    source_run_value: Any,
    *,
    issue_dir: Path = ISSUE_DIR,
    now: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    source = validate_source_run(source_run_value)
    publication_date, issue_number = derive_weekly_identity(
        review_value,
        issue_dir=issue_dir,
    )
    issue = prepare_issue(
        review_value,
        publication_date,
        issue_number,
        now=now,
    )
    review = _record(review_value, "review")
    review_run_id = review.get("runId")
    if not isinstance(review_run_id, str) or not review_run_id.strip():
        raise ValueError("review.runId is required for the staging receipt")
    manifest = {
        "schemaVersion": "gravel-weekly-stage/v1",
        "source": source,
        "reviewRunId": review_run_id,
        "publicationDate": publication_date,
        "issueId": issue["issueId"],
        "issueNumber": issue_number,
        "draftContentHash": issue["contentHash"],
        "storyCount": len(issue["stories"]),
        "currentThingStoryId": issue["currentThingStoryId"],
        "sourceCoverageStatus": issue["sourceCoverage"]["status"],
        "status": "draft",
        "humanApprovalRequired": True,
        "autoPublishAllowed": False,
    }
    return issue, manifest


def render_stage_summary(issue: dict[str, Any], manifest: dict[str, Any]) -> str:
    source = manifest["source"]
    current = next(
        (story for story in issue["stories"] if story["candidateId"] == issue["currentThingStoryId"]),
        None,
    )
    if current is None:
        decision = "**QUIET ISSUE CANDIDATE.** No story cleared every publication gate."
        next_action = (
            f"Review the private preview, then explicitly choose `APPROVE QUIET #{issue['issueNumber']:03d}` "
            "or `WAIT`."
        )
    else:
        decision = f"**CURRENT THING CANDIDATE:** {current['headline']} ({current['score']}/100)."
        next_action = (
            "Review the private preview, then approve, edit, reject, or hold the exact hash-bound copy."
        )
    return "\n".join([
        f"<!-- gravel-weekly-draft-date: {issue['publicationDate']} -->",
        f"<!-- gravel-weekly-draft-hash: {issue['contentHash']} -->",
        f"# Gravel Weekly #{issue['issueNumber']:03d} private draft",
        "",
        "> **DRAFT — NOT MATTI-APPROVED, PUBLISHED, EMAILED, OR AUTHORIZED TO ALTER RACE DATA.**",
        "",
        decision,
        "",
        f"- Publication window: `{issue['publicationDate']}`",
        f"- Draft hash: `{issue['contentHash']}`",
        f"- Stories staged: {len(issue['stories'])}",
        f"- Source coverage: `{issue['sourceCoverage']['status']}`",
        f"- Trusted producer: [{source['workflow']} run {source['runId']}]({source['htmlUrl']})",
        f"- Producer commit: `{source['headSha']}`",
        "",
        next_action,
        "Approval remains a separate immutable decision. Publication remains a second separate instruction.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("review", type=Path)
    parser.add_argument("--source-run", required=True, type=Path)
    parser.add_argument("--issue-dir", type=Path, default=ISSUE_DIR)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    review = json.loads(args.review.read_text(encoding="utf-8"))
    source_run = json.loads(args.source_run.read_text(encoding="utf-8"))
    issue, manifest = stage_review(review, source_run, issue_dir=args.issue_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    draft_path = args.output_dir / "draft.json"
    manifest_path = args.output_dir / "manifest.json"
    summary_path = args.output_dir / "review-summary.md"
    draft_path.write_text(f"{json.dumps(issue, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    manifest_path.write_text(f"{json.dumps(manifest, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    summary_path.write_text(render_stage_summary(issue, manifest), encoding="utf-8")
    print(json.dumps({
        "draft": str(draft_path),
        "manifest": str(manifest_path),
        "summary": str(summary_path),
        "publicationDate": issue["publicationDate"],
        "issueNumber": issue["issueNumber"],
        "contentHash": issue["contentHash"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
