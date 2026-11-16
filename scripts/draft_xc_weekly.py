#!/usr/bin/env python3
"""Draft one XC Ski Labs Weekly issue from collected evidence and stage it.

Merges one or more evidence files from collect_xc_weekly.py, keeps the last
seven days, asks Claude to pick and summarise the week in Matti's wax-bench
voice (prompts/xc-weekly-voice.md), then runs the publication gate in
xc_weekly_issue.validate_issue. A draft that fails the gate gets one repair
attempt with the gate's findings; if it still fails, nothing is staged and
the script exits non-zero. There is no template or fallback issue.

Writes to --output-dir: issue.json, evidence.json, preview.html, review.md,
manifest.json. Nothing here sends email.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from collect_xc_weekly import merge_items  # noqa: E402
from xc_weekly_issue import (  # noqa: E402
    IssueError, assemble_issue, render_email_html, render_review_markdown, validate_issue,
)

MODEL = "claude-opus-5-5"
VOICE_PATH = PROJECT_ROOT / "prompts" / "xc-weekly-voice.md"
WINDOW_DAYS = 7

SELECTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject", "preheader", "take", "stories", "podcasts"],
    "properties": {
        "subject": {"type": "string"},
        "preheader": {"type": "string"},
        "take": {"type": "array", "items": {"type": "string"}},
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["itemId", "headline", "blurb"],
                "properties": {
                    "itemId": {"type": "string"},
                    "headline": {"type": "string"},
                    "blurb": {"type": "string"},
                },
            },
        },
        "podcasts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["itemId", "blurb"],
                "properties": {
                    "itemId": {"type": "string"},
                    "blurb": {"type": "string"},
                },
            },
        },
    },
}


def load_evidence(paths: list[Path], now: datetime) -> dict:
    """Merge evidence files and keep the items from the last WINDOW_DAYS."""
    since = now - timedelta(days=WINDOW_DAYS)
    groups, coverage = [], {}
    for path in paths:
        data = json.loads(path.read_text())
        groups.append(data["items"])
        for cov in data["coverage"]:
            prior = coverage.get(cov["id"])
            # Keep the latest run's coverage row, but remember any error seen.
            if prior is None or data["collectedAt"] >= prior["_at"]:
                coverage[cov["id"]] = {**cov, "_at": data["collectedAt"]}
    items = [i for i in merge_items(*groups)
             if since <= datetime.fromisoformat(i["published"]) <= now]
    for cov in coverage.values():
        cov["kept"] = sum(1 for i in items if i["sourceId"] == cov["id"])
        cov.pop("_at", None)
    return {"since": since.isoformat(), "collectedAt": now.isoformat(),
            "items": items, "coverage": sorted(coverage.values(), key=lambda c: (c["kind"], c["id"]))}


def evidence_prompt(evidence: dict) -> str:
    rows = [{
        "id": i["id"], "kind": i["kind"], "outlet": i["sourceName"], "lang": i["lang"],
        "published": i["published"][:16], "title": i["title"], "excerpt": i["excerpt"],
        "categories": i["categories"],
    } for i in evidence["items"]]
    return (
        f"The week runs from {evidence['since'][:10]} to {evidence['collectedAt'][:10]}. "
        f"Here are the {len(rows)} items collected from the cross-country outlets and podcasts. "
        "Pick and write the issue. Refer to items only by their id.\n\n"
        + json.dumps(rows, ensure_ascii=False, indent=1)
    )


def ask_claude(client, messages: list[dict]) -> tuple[dict, list]:
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        thinking={"type": "adaptive"},
        output_config={"effort": "high",
                       "format": {"type": "json_schema", "schema": SELECTION_SCHEMA}},
        system=VOICE_PATH.read_text(),
        messages=messages,
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined to draft this week's issue")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("the draft hit max_tokens before finishing")
    text = "".join(block.text for block in response.content if block.type == "text")
    return json.loads(text), response.content


def draft(evidence: dict, issue_number: int, issue_date: str, client=None) -> dict:
    if client is None:
        import anthropic
        client = anthropic.Anthropic()
    messages = [{"role": "user", "content": evidence_prompt(evidence)}]
    selection, content = ask_claude(client, messages)
    try:
        issue = assemble_issue(selection, evidence, issue_number, issue_date)
        return validate_issue(issue, evidence)
    except IssueError as exc:
        problems = str(exc)
    messages += [
        {"role": "assistant", "content": content},
        {"role": "user", "content": (
            "The issue failed the publication check. Fix every problem below and return "
            "the whole issue again. Do not drop the take or the citations to get around a "
            f"rule.\n\nProblems: {problems}")},
    ]
    selection, _ = ask_claude(client, messages)
    issue = assemble_issue(selection, evidence, issue_number, issue_date)
    return validate_issue(issue, evidence)


def stage(issue: dict, evidence: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    (out / "issue.json").write_text(json.dumps(issue, ensure_ascii=False, indent=2))
    (out / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    (out / "preview.html").write_text(render_email_html(issue))
    (out / "review.md").write_text(render_review_markdown(issue, evidence["coverage"]))
    manifest = {
        "issueNumber": issue["issueNumber"],
        "issueDate": issue["issueDate"],
        "contentHash": issue["contentHash"],
        "stories": len(issue["stories"]),
        "podcasts": len(issue["podcasts"]),
        "humanApprovalRequired": True,
        "autoSendAllowed": False,
        "model": MODEL,
        "stagedAt": datetime.now(timezone.utc).isoformat(),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", nargs="+", type=Path)
    parser.add_argument("--issue-number", type=int, required=True)
    parser.add_argument("--issue-date", help="YYYY-MM-DD; defaults to today (UTC)")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set; nothing drafted", file=sys.stderr)
        return 1
    now = datetime.now(timezone.utc)
    issue_date = args.issue_date or now.date().isoformat()
    evidence = load_evidence(args.evidence, now)
    news = sum(1 for i in evidence["items"] if i["kind"] == "news")
    if news < 4:
        print(f"Only {news} news items this week; not enough for an issue, nothing staged", file=sys.stderr)
        return 1
    try:
        issue = draft(evidence, args.issue_number, issue_date)
    except (IssueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"XC Weekly draft refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(stage(issue, evidence, args.output_dir)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
