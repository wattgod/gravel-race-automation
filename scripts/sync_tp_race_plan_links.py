#!/usr/bin/env python3
"""Sync published Gravel God race-plan links from the TP plan database."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = PROJECT_ROOT.parent / "gravel-god-training-plans" / "db" / "plans.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "tp-race-plan-links.json"
TIER_ORDER = {
    "Finisher": 0,
    "Time-Crunched": 1,
    "Compete": 2,
    "Masters 50+": 3,
    "Save My Race": 4,
}


def load_rows(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("plans", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SystemExit(f"{path} does not contain a plan list")
    return rows


def build_links(rows: list[dict]) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for plan in rows:
        slug = plan.get("race_slug")
        url = plan.get("marketplace_url")
        if (
            plan.get("discipline") != "gravel"
            or plan.get("status") != "published"
            or not slug
            or not url
        ):
            continue
        result.setdefault(slug, []).append(
            {
                "planId": plan["planId"],
                "tier": plan["tier"],
                "weeks": plan["length_wk"],
                "price": plan["price"],
                "url": url,
            }
        )

    for plans in result.values():
        plans.sort(
            key=lambda plan: (
                TIER_ORDER.get(plan["tier"], 99),
                -int(plan["weeks"]),
                int(plan["planId"]),
            )
        )
    return dict(sorted(result.items()))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    links = build_links(load_rows(args.source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(links, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"synced {sum(len(plans) for plans in links.values())} published plans "
        f"across {len(links)} Gravel God races to {args.output}"
    )


if __name__ == "__main__":
    main()
