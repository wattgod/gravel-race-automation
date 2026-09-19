#!/usr/bin/env python3
"""Use advisory judgments to triage immune near-duplicate findings."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

try:
    from scripts import jev_client
except ImportError:  # pragma: no cover - direct script execution
    import jev_client


ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = ROOT / "race-data"
DEFAULT_OUT = ROOT / "data" / "jev" / "duplicate-report.json"
PAIR_RE = re.compile(r"'([^']+)'\s+and\s+'([^']+)'")


def _pairs(report: dict[str, Any]) -> list[tuple[str, str]]:
    pairs = []
    for finding in report.get("findings", []):
        if finding.get("code") != "duplicate-race":
            continue
        direct_a = finding.get("slug_a") or finding.get("a")
        direct_b = finding.get("slug_b") or finding.get("b")
        if direct_a and direct_b:
            pairs.append((str(direct_a), str(direct_b)))
            continue
        match = PAIR_RE.search(finding.get("detail", "") or finding.get("message", ""))
        if match:
            pairs.append(match.groups())
    return pairs


def _profile(slug: str) -> dict[str, Any]:
    race = json.loads((RACE_DATA / f"{slug}.json").read_text(encoding="utf-8")).get("race", {})
    vitals = race.get("vitals", {})
    return {
        "name": race.get("name"),
        "slug": race.get("slug", slug),
        "vitals": {
            "location": vitals.get("location"),
            "date": vitals.get("date"),
            "distance": vitals.get("distance_mi", vitals.get("distance_km")),
        },
        "history": {"founded": (race.get("history") or {}).get("founded")},
        "website": race.get("website") or vitals.get("website"),
    }


def _row(a: str, b: str) -> dict[str, Any]:
    Noul = jev_client.question_types()[2]
    response = jev_client.ask(
        {"a": _profile(a), "b": _profile(b)},
        {"same_event": Noul(instructions=(
            "Are these two profiles the same real-world event (same organizer/course "
            "lineage, possibly different year or name), rather than two distinct events?"
        ))},
    )
    probability = jev_client.probability(jev_client.noul(response, "same_event"))
    verdict = "likely_same" if probability is not None and probability >= 0.8 else (
        "likely_distinct" if probability is not None and probability <= 0.2 else "unclear"
    )
    return {
        "slug_a": a,
        "slug_b": b,
        "same_event_probability": probability,
        "verdict": verdict,
        "model": jev_client.model(response),
        "response_available": response is not None,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    pairs: list[tuple[str, str]] = []
    if args.pair:
        pairs.append(tuple(args.pair))
    else:
        report_path = ROOT / "immune" / "report.json"
        if args.regen or not report_path.exists():
            subprocess.run(
                ["python3", "scripts/immune_check.py", "--json"],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
        try:
            pairs = _pairs(json.loads(report_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pairs = []
    rows = [_row(a, b) for a, b in pairs]
    response_model = next((row.get("model") for row in rows if row.get("model")), None)
    report = jev_client.base_report(
        type("Response", (), {"model": response_model})() if response_model else None,
        available=any(row["response_available"] for row in rows),
    )
    report.update({
        "pairs_source": "synthetic_pair" if args.pair else "immune/report.json",
        "pair_parsing": (
            None if args.pair else "slugs parsed from immune finding detail messages when needed"
        ),
        "rows": rows,
        "summary": {"pairs_considered": len(pairs), "likely_same": sum(r["verdict"] == "likely_same" for r in rows)},
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regen", action="store_true")
    parser.add_argument("--pair", nargs=2, metavar=("SLUG_A", "SLUG_B"))
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    report = run(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
