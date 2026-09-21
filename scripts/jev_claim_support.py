#!/usr/bin/env python3
"""Flag factual claims in race explanations that lack dump support."""

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
RESEARCH = ROOT / "research-dumps"
DEFAULT_OUT = ROOT / "data" / "jev" / "claim-support-report.json"
SUPERLATIVES = re.compile(r"\b(most|only|first|largest|toughest|hardest|best|worst)\b", re.I)


def split_sentences(text: str) -> list[str]:
    value = text or ""
    boundaries = [
        match.start()
        for match in re.finditer(r"[.!?]", value)
        if not (
            match.group() == "."
            and match.start() > 0
            and match.start() + 1 < len(value)
            and value[match.start() - 1].isdigit()
            and value[match.start() + 1].isdigit()
        )
    ]
    start = 0
    sentences: list[str] = []
    for boundary in boundaries:
        sentence = value[start:boundary].strip()
        if sentence:
            sentences.append(sentence)
        start = boundary + 1
    tail = value[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences


def should_check(sentence: str) -> bool:
    return bool(re.search(r"\d|%", sentence) or SUPERLATIVES.search(sentence) or
                re.search(r"\b[A-Z][a-z]{2,}\b", sentence))


def selected_sentences(data: dict[str, Any]) -> list[str]:
    race = data.get("race", {})
    opinions = race.get("biased_opinion_ratings") or {}
    texts = [
        opinion.get("explanation", "")
        for opinion in opinions.values()
        if isinstance(opinion, dict)
    ]
    biased = race.get("biased_opinion")
    if isinstance(biased, str):
        texts.append(biased)
    result: list[str] = []
    for text in texts:
        for sentence in split_sentences(text):
            if should_check(sentence) and sentence not in result:
                result.append(sentence)
                if len(result) >= 20:
                    return result
    return result


def audit_profile(slug: str, data: dict[str, Any], dump: str) -> list[dict[str, Any]]:
    sentences = selected_sentences(data)
    rows: list[dict[str, Any]] = []
    Noul = jev_client.question_types()[2]
    for start in range(0, len(sentences), 10):
        batch = sentences[start : start + 10]
        response = jev_client.ask(
            {"dump": dump[:12000], "sentences": {f"s_{i}": value for i, value in enumerate(batch)}},
            {
                f"s_{i}": Noul(
                    instructions=(
                        "Does the research dump contain evidence that supports this "
                        "sentence's factual content (not tone)?"
                    )
                )
                for i in range(len(batch))
            },
        )
        for index, sentence in enumerate(batch):
            probability = jev_client.probability(jev_client.noul(response, f"s_{index}"))
            flag = None if probability is None else "unsupported" if probability < 0.35 else "weak" if probability < 0.6 else None
            rows.append({
                "slug": slug,
                "sentence": sentence,
                "support": probability,
                "flag": flag,
                "model": jev_client.model(response),
                "response_available": response is not None,
            })
    return rows


def run(args: argparse.Namespace) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    no_dump = 0
    profiles = sorted(RACE_DATA.glob("*.json"))
    if args.slug:
        profiles = [RACE_DATA / f"{args.slug}.json"]
    if args.limit:
        profiles = profiles[: args.limit]
    for path in profiles:
        dump_path = RESEARCH / f"{path.stem}-raw.md"
        if not dump_path.exists():
            no_dump += 1
            continue
        rows.extend(audit_profile(path.stem, json.loads(path.read_text(encoding="utf-8")), dump_path.read_text(encoding="utf-8")))
    response_model = next((row.get("model") for row in rows if row.get("model")), None)
    report = jev_client.base_report(
        type("Response", (), {"model": response_model})() if response_model else None,
        available=any(row["response_available"] for row in rows),
    )
    report.update({
        "rows": rows,
        "summary": {
            "profiles_considered": len(profiles),
            "no_dump": no_dump,
            "unsupported": sum(row["flag"] == "unsupported" for row in rows),
            "weak": sum(row["flag"] == "weak" for row in rows),
        },
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug")
    parser.add_argument("--limit", type=int)
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
