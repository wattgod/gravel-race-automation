#!/usr/bin/env python3
"""Render a controlled race-impact queue from published historical entries."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from validate_gravel_weekly_history import HISTORY_DIR, load_history_entries
from validate_gravel_weekly_history_decisions import validate_history_decision

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DECISION_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "history-decisions"


def history_set_hash(entries: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        f"{entry['entryId']}:{entry['contentHash']}"
        for entry in sorted(entries, key=lambda item: item["entryId"])
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def render_history_race_impact_review(
    entries: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
    *,
    year: int,
) -> tuple[str, int, str]:
    selected = [
        entry
        for entry in entries
        if entry["status"] == "published"
        and entry["activeFrom"] <= f"{year}-12-31"
        and entry["activeThrough"] >= f"{year}-01-01"
    ]
    if not selected:
        raise ValueError(f"no published {year} historical entries are available")
    for entry in selected:
        decision = decisions.get(entry["entryId"])
        if decision is None:
            raise ValueError(f"historical decision missing for {entry['entryId']}")
        validate_history_decision(decision, entry)

    set_hash = history_set_hash(selected)
    impacts = [
        (entry, impact)
        for entry in selected
        for impact in entry["raceImpacts"]
    ]
    lines = [
        f"<!-- meaningful-history-race-impact-count: {len(impacts)} -->",
        f"<!-- gravel-weekly-history-set-hash: {set_hash} -->",
        f"# Gravel Weekly {year} historical race-impact review",
        "",
        f"Published timeline: https://gravelgodcycling.com/gravel-weekly/#season-story",
        f"History set hash: `{set_hash}` · entries: {len(selected)}",
        "",
        "> Controlled review only. Publishing a historical narrative does not authorize or perform a race-profile edit.",
        "> Confirm each claim against the current canonical profile, then use a normal branch, regression test, and pull request.",
        "",
    ]
    if not impacts:
        lines.extend(["No historical race-profile implication was proposed.", ""])
        return "\n".join(lines), 0, set_hash

    for entry, impact in impacts:
        receipts = {
            receipt["claimId"]: receipt
            for receipt in entry["contemporaryReceipts"] + entry["laterEvidence"]
        }
        encoded = json.dumps(impact, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        impact_id = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:12]
        lines.extend([
            f"## {impact['raceId']} · `{impact['fieldPath'] or 'catalog'}`",
            "",
            f"Story: [{entry['headline']}](https://gravelgodcycling.com/gravel-weekly/#{entry['entryId']})",
            f"Entry: `{entry['entryId']}` · history hash: `{entry['contentHash']}`",
            f"Impact ID: `{impact_id}` · evidence confidence: {round(float(impact['confidence']) * 100)}% · owner: `{impact['owner']}`",
            "",
            "### Evidence",
            "",
        ])
        for claim_id in impact["claimIds"]:
            receipt = receipts[claim_id]
            published = f" · {receipt['publishedAt'][:10]}" if receipt.get("publishedAt") else ""
            timestamp = ""
            if receipt.get("transcriptStartSeconds") is not None:
                seconds = int(receipt["transcriptStartSeconds"])
                timestamp = f" · {seconds // 60}:{seconds % 60:02d}"
            lines.append(
                f"- `{claim_id}` · [{receipt['publisher']}]({receipt['canonicalUrl']}){published}{timestamp}"
            )
        lines.extend([
            "",
            "### Human disposition",
            "",
            "- [ ] Confirm the current canonical profile and source freshness",
            "- [ ] Decide whether the narrative belongs in `race.history`; reject or revise with a reason if not",
            "- [ ] Add a failing regression fixture before any accepted change",
            "- [ ] Apply only through the owning repository's normal pull-request path",
            "",
        ])
    return "\n".join(lines), len(impacts), set_hash


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--history-dir", type=Path, default=HISTORY_DIR)
    parser.add_argument("--decision-dir", type=Path, default=DECISION_DIR)
    args = parser.parse_args()

    entries = load_history_entries(args.history_dir)
    decisions: dict[str, dict[str, Any]] = {}
    if args.decision_dir.exists():
        for path in sorted(args.decision_dir.glob("*.json")):
            decision = json.loads(path.read_text(encoding="utf-8"))
            entry_id = decision.get("entryId")
            if isinstance(entry_id, str):
                decisions[entry_id] = decision
    try:
        review, count, set_hash = render_history_race_impact_review(
            entries, decisions, year=args.year
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(f"{review.rstrip()}\n", encoding="utf-8")
    print(f"Rendered {count} controlled historical race impact(s); set hash {set_hash}: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
