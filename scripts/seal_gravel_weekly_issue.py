#!/usr/bin/env python3
"""Seal an approved Gravel Weekly issue as an immutable deployable snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from validate_gravel_weekly import ISSUE_DIR, compute_content_hash, validate_issue


def _timestamp(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


def seal_issue(approved_value: Any, published_at: str) -> dict[str, Any]:
    approved = validate_issue(approved_value)
    if approved["status"] != "approved":
        raise ValueError("sealing requires a status=approved issue")
    published_time = _timestamp(published_at, "publishedAt")
    approved_time = _timestamp(approved["editorialApproval"]["approvedAt"], "editorialApproval.approvedAt")
    if published_time < approved_time:
        raise ValueError("publishedAt cannot precede editorial approval")
    sealed = {
        **approved,
        "status": "published",
        "publishedAt": published_at,
        "updatedAt": published_at,
        "contentHash": "pending",
    }
    sealed["contentHash"] = compute_content_hash(sealed)
    return validate_issue(sealed)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("approved", type=Path)
    parser.add_argument("--published-at", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    approved = json.loads(args.approved.read_text(encoding="utf-8"))
    issue = seal_issue(approved, args.published_at)
    output = args.output or ISSUE_DIR / f"{issue['publicationDate']}.json"
    if output.exists() and not args.overwrite:
        raise SystemExit(f"Refusing to replace immutable issue snapshot: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{json.dumps(issue, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"Sealed deployable issue snapshot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
