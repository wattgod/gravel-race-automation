#!/usr/bin/env python3
"""Render an immutable, issue-specific review queue from a published issue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_gravel_weekly import validate_issue
from gravel_weekly_race_impacts import race_impact_id


def _inline_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("`", "\\u0060")


def render_review(issue_value: Any) -> tuple[str, int]:
    issue = validate_issue(issue_value)
    if issue["status"] != "published":
        raise ValueError("race-impact handoff requires a published issue snapshot")

    receipts_by_claim: dict[str, dict[str, Any]] = {}
    for story in issue["stories"]:
        for receipt in story["receipts"]:
            receipts_by_claim[receipt["claimId"]] = receipt

    actionable = [impact for impact in issue["raceImpacts"] if impact["impactKind"] != "no_change"]
    lines = [
        f"<!-- meaningful-race-impact-count: {len(actionable)} -->",
        f"# Gravel Weekly #{issue['issueNumber']:03d} race-impact review",
        "",
        f"Published issue: https://gravelgodcycling.com/gravel-weekly/{issue['slug']}/",
        f"Issue ID: `{issue['issueId']}` · content hash: `{issue['contentHash']}`",
        "",
        "> Controlled review only. This artifact does not authorize or perform a source-repository edit.",
        "> Confirm the evidence against the current owning profile, then use a normal branch, regression test, and pull request.",
        "",
    ]
    if not actionable:
        lines.extend(["No actionable race-profile change was proposed in this issue.", ""])
        return "\n".join(lines), 0

    for impact in actionable:
        impact_id = race_impact_id(impact)
        lines.extend([
            f"## {impact['impactKind'].upper()} · {impact['raceId']} · `{impact['fieldPath'] or 'catalog'}`",
            "",
            f"Impact ID: `{impact_id}` · evidence confidence: {round(float(impact['confidence']) * 100)}% · owner: `{impact['owner']}`",
            "",
            f"Current value: `{_inline_json(impact.get('currentValue'))}`",
            "",
            f"Proposed value: `{_inline_json(impact.get('proposedValue'))}`",
            "",
            "### Evidence",
            "",
        ])
        for claim_id in impact["claimIds"]:
            receipt = receipts_by_claim[claim_id]
            published = f" · {receipt['publishedAt'][:10]}" if receipt.get("publishedAt") else ""
            timestamp = ""
            if receipt.get("transcriptStartSeconds") is not None:
                seconds = int(receipt["transcriptStartSeconds"])
                timestamp = f" · {seconds // 60}:{seconds % 60:02d}"
            lines.append(f"- `{claim_id}` · [{receipt['publisher']}]({receipt['canonicalUrl']}){published}{timestamp}")
        lines.extend([
            "",
            "### Human disposition",
            "",
            "- [ ] Confirm current profile value and source freshness",
            "- [ ] Accept as an objective change / route for subjective editorial review / reject with reason",
            "- [ ] Add a failing regression fixture before any accepted change",
            "- [ ] Apply through the owning repository's normal pull-request path",
            "",
        ])
    return "\n".join(lines), len(actionable)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("issue", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    review, count = render_review(json.loads(args.issue.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f"{review.rstrip()}\n", encoding="utf-8")
    print(f"Rendered {count} actionable race impact(s): {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
