#!/usr/bin/env python3
"""Flag rubric drift between Gravel God explanations and assigned scores."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from scripts import jev_client
except ImportError:  # pragma: no cover - direct script execution
    import jev_client


ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = ROOT / "race-data"
RUBRIC = ROOT / "docs" / "GRAVEL_GOD_SCORING_SYSTEM.md"
DEFAULT_OUT = ROOT / "data" / "jev" / "rating-audit-report.json"


def _key(header: str) -> str:
    return re.sub(r"\s+", "_", re.sub(r"[^a-zA-Z0-9 ]", "", header).strip().lower())


def parse_rubric(path: Path = RUBRIC) -> dict[str, list[str]]:
    text = path.read_text(encoding="utf-8")
    tables: dict[str, list[str]] = {}
    current: str | None = None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## Course Profile"):
            current = "course"
        elif line.startswith("## Editorial"):
            current = "editorial"
        if current and line.startswith("|") and index + 1 < len(lines):
            headers = [part.strip() for part in line.strip("|").split("|")]
            if len(headers) != 6 or headers[0] != "Dimension":
                continue
            next_line = lines[index + 1]
            if not next_line.startswith("|"):
                continue
            for row in lines[index + 2 :]:
                if not row.startswith("|"):
                    break
                cells = [part.strip() for part in row.strip("|").split("|")]
                if len(cells) != 6:
                    continue
                dimension = re.sub(r"\*+", "", cells[0]).strip()
                if dimension:
                    tables[_key(dimension)] = cells[1:6]
    if len(tables) != 14 or any(len(levels) != 5 for levels in tables.values()):
        raise ValueError(f"expected 14 rubric dimensions with five levels, found {len(tables)}")
    return tables


def _date_key(slug: str, profile: dict[str, Any]) -> tuple[int, str, str]:
    metadata = profile.get("race", {}).get("research_metadata", {}) or {}
    date = metadata.get("date") or metadata.get("researched_at") or metadata.get("updated_at") or ""
    return (0, str(date), slug) if date else (1, "", slug)


def _profiles(args: argparse.Namespace) -> list[tuple[str, dict[str, Any]]]:
    paths = sorted(RACE_DATA.glob("*.json"))
    profiles = [(path.stem, json.loads(path.read_text(encoding="utf-8"))) for path in paths]
    profiles.sort(key=lambda item: _date_key(item[0], item[1]))
    if args.slug:
        profiles = [item for item in profiles if item[0] == args.slug]
    if args.tier is not None:
        profiles = [
            item for item in profiles
            if item[1].get("race", {}).get("gravel_god_rating", {}).get("tier") == args.tier
        ]
    if args.limit is not None:
        profiles = profiles[: args.limit]
    return profiles


def _score_value(answer: Any, levels: list[str]) -> int | None:
    raw = getattr(answer, "score", answer) if answer is not None else None
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
        if 1 <= value <= 5:
            return int(round(value))
    except (TypeError, ValueError):
        pass
    if isinstance(raw, str):
        folded = raw.casefold().strip()
        for index, level in enumerate(levels, 1):
            if folded == level.casefold().strip():
                return index
    return None


def audit_profile(slug: str, data: dict[str, Any], rubric: dict[str, list[str]]) -> list[dict[str, Any]]:
    race = data.get("race", {})
    opinions = race.get("biased_opinion_ratings") or {}
    if not opinions:
        return []
    rating = race.get("gravel_god_rating") or {}
    dimensions = {
        dimension: opinion.get("explanation")
        for dimension, opinion in opinions.items()
        if dimension in rubric and isinstance(opinion, dict) and opinion.get("explanation")
    }
    if not dimensions:
        return []
    state = {
        "name": race.get("name"),
        "vitals": race.get("vitals", {}),
        "climate": str(race.get("climate", ""))[:1500],
        "terrain": str(race.get("terrain", ""))[:1500],
        "explanations": {dimension: text for dimension, text in dimensions.items()},
    }
    Choice, Score, Noul = jev_client.question_types()
    del Choice, Noul
    response = jev_client.ask(
        state,
        {
            f"score_{dimension}": Score(
                instructions=(
                    "Using only the verified vitals and this explanation, which rubric "
                    f"level fits the {dimension} of this race?"
                ),
                criteria=rubric[dimension],
            )
            for dimension in dimensions
        },
    )
    rows: list[dict[str, Any]] = []
    for dimension, explanation in dimensions.items():
        assigned = rating.get(dimension)
        answer = jev_client.score(response, f"score_{dimension}")
        jev_level = _score_value(answer, rubric[dimension])
        conf = jev_client.confidence(answer)
        delta = abs(jev_level - assigned) if jev_level is not None and isinstance(assigned, (int, float)) else None
        severity = None
        if delta is not None and conf is not None:
            if delta >= 2 and conf >= 0.6:
                severity = "high"
            elif delta == 1 and conf >= 0.8:
                severity = "low"
        mismatch = (
            isinstance(opinions.get(dimension), dict)
            and opinions[dimension].get("score") != assigned
        )
        rows.append({
            "slug": slug,
            "dimension": dimension,
            "assigned": assigned,
            "jev_level": jev_level,
            "confidence": conf,
            "probabilities": jev_client.probabilities(answer),
            "severity": severity,
            "explanation_mismatch": mismatch,
            "explanation": explanation,
            "model": jev_client.model(response),
            "response_available": response is not None,
        })
    return rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    rubric = parse_rubric()
    rows: list[dict[str, Any]] = []
    skipped = 0
    for slug, data in _profiles(args):
        if not data.get("race", {}).get("biased_opinion_ratings"):
            skipped += 1
            continue
        rows.extend(audit_profile(slug, data, rubric))
    response_model = next((row.get("model") for row in rows if row.get("model")), None)
    report = jev_client.base_report(
        type("Response", (), {"model": response_model})() if response_model else None,
        available=any(row["response_available"] for row in rows),
    )
    report.update({
        "rows": rows,
        "summary": {
            "profiles_considered": len(_profiles(args)),
            "profiles_skipped_no_opinions": skipped,
            "high": sum(row["severity"] == "high" for row in rows),
            "low": sum(row["severity"] == "low" for row in rows),
            "explanation_mismatch": sum(row["explanation_mismatch"] for row in rows),
        },
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug")
    parser.add_argument("--tier", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = run(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if args.strict and report["summary"]["high"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
