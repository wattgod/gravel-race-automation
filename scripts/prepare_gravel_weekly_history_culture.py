#!/usr/bin/env python3
"""Attach bounded culture-sweep candidates to a private historical draft proposal."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Any

from validate_gravel_weekly import IssueValidationError, _iso, _list, _record, _text, _url
from validate_gravel_weekly_history import (
    compute_history_content_hash,
    validate_history_entry,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROPOSAL_DIR = PROJECT_ROOT / "data" / "gravel-weekly" / "history-culture-proposals"
GENERIC_TOPIC_WORDS = {
    "argument", "arguments", "bike", "culture", "cycling", "drama", "gravel",
    "joke", "jokes", "meme", "memes", "race", "racing", "scene",
}


def _tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    return {word[:-1] if len(word) > 4 and word.endswith("s") else word for word in words}


def _entry_tokens(entry: dict[str, Any]) -> set[str]:
    return _tokens(" ".join(str(entry[field]) for field in (
        "entryId", "headline", "point", "priorJudgment", "changedJudgment", "stakes",
        "credibleOpposition", "whatHappened", "take",
    )))


def _topic_matches(values: list[str], entry_tokens: set[str]) -> bool:
    for value in values:
        raw = _tokens(value.replace("lifetime", "life time"))
        distinctive = raw - GENERIC_TOPIC_WORDS
        if distinctive and distinctive <= entry_tokens:
            return True
    return False


def _in_active_period(entry: dict[str, Any], published_at: str) -> bool:
    published = datetime.fromisoformat(_iso(published_at, "culture publishedAt").replace("Z", "+00:00")).astimezone(timezone.utc)
    start = datetime.combine(datetime.strptime(entry["activeFrom"], "%Y-%m-%d").date(), time.min, tzinfo=timezone.utc)
    end = datetime.combine(datetime.strptime(entry["activeThrough"], "%Y-%m-%d").date(), time.max, tzinfo=timezone.utc)
    return start <= published <= end


def _x_artifact(candidate_value: Any, entry: dict[str, Any], recurring_topics: set[str], min_attention: float) -> tuple[float, dict[str, Any]] | None:
    candidate = _record(candidate_value, "historical X candidate")
    if candidate.get("platform") != "x" or candidate.get("purpose") != "culture_sensor" or candidate.get("canProveClaim") is not False:
        raise IssueValidationError("historical X candidate violates its culture-only boundary")
    attention = candidate.get("attentionScore")
    if not isinstance(attention, (int, float)) or isinstance(attention, bool) or not 0 <= attention <= 100:
        raise IssueValidationError("historical X candidate attentionScore is invalid")
    if attention < min_attention or not _in_active_period(entry, candidate.get("publishedAt")):
        return None
    query_ids = [_text(value, "historical X candidate queryId", 64) for value in _list(candidate.get("queryIds"), "historical X candidate queryIds", 20)]
    query_labels = [_text(value, "historical X candidate queryLabel", 100) for value in _list(candidate.get("queryLabels"), "historical X candidate queryLabels", 20)]
    if not query_ids or not _topic_matches([*query_ids, *query_labels], _entry_tokens(entry)):
        return None
    handle = _text(candidate.get("authorHandle"), "historical X candidate authorHandle", 100)
    excerpt = _text(candidate.get("excerpt"), "historical X candidate excerpt", 280)
    source_url = _url(candidate.get("canonicalUrl"), "historical X candidate canonicalUrl")
    publisher = candidate.get("authorName") or f"@{handle}"
    matched_labels = ", ".join(query_labels or query_ids)
    recurring = sorted(set(query_ids) & recurring_topics)
    recurrence = f" It also recurred across {', '.join(recurring)} source tags." if recurring else ""
    artifact = {
        "artifactId": _text(candidate.get("id"), "historical X candidate id", 500),
        "sourceKind": "x",
        "publisher": _text(publisher, "historical X candidate publisher", 300),
        "author": f"@{handle}",
        "canonicalUrl": source_url,
        "publishedAt": _iso(candidate.get("publishedAt"), "historical X candidate publishedAt"),
        "title": f"@{handle} during {entry['activeFrom']} → {entry['activeThrough']}",
        "excerpt": excerpt,
        "timestampSeconds": None,
        "topicTags": sorted(set(query_ids)),
        "reviewReason": f"Matched this story through {matched_labels}; attention {attention:g}/100 within the bounded annual sample.{recurrence} Engagement located the artifact but did not judge its truth or publication value.",
        "collectionMethod": "official_api",
        "rightsPolicy": "short_excerpt_and_canonical_link",
        "purpose": "culture_sensor",
        "canProveClaim": False,
        "canEstablishConsensus": False,
    }
    score = float(attention) + (15 if recurring else 0)
    return score, artifact


def _supplement_artifact(value: Any, entry: dict[str, Any], recurring_topics: set[str]) -> tuple[float, dict[str, Any]] | None:
    source = _record(value, "historical culture supplement")
    if source.get("purpose") != "culture_sensor" or source.get("canProveClaim") is not False:
        raise IssueValidationError("historical supplement violates its culture-only boundary")
    if not _in_active_period(entry, source.get("publishedAt")):
        return None
    topics = [_text(item, "historical supplement topic", 64) for item in _list(source.get("topicTags"), "historical supplement topicTags", 10)]
    if not topics or not _topic_matches(topics, _entry_tokens(entry)):
        return None
    method = _text(source.get("collectionMethod"), "historical supplement collectionMethod", 100)
    excerpt = source.get("excerpt")
    if excerpt is not None:
        excerpt = _text(excerpt, "historical supplement excerpt", 280)
    timestamp = source.get("timestampSeconds")
    if timestamp is not None and (not isinstance(timestamp, int) or isinstance(timestamp, bool) or timestamp < 0):
        raise IssueValidationError("historical supplement timestampSeconds is invalid")
    recurring = sorted(set(topics) & recurring_topics)
    recurrence = f" It also recurred across {', '.join(recurring)} source tags." if recurring else ""
    rights = "timestamped_short_excerpt" if method == "authorized_caption" else (
        "short_excerpt_and_canonical_link" if excerpt else "metadata_only"
    )
    artifact = {
        "artifactId": _text(source.get("id"), "historical supplement id", 500),
        "sourceKind": _text(source.get("sourceKind"), "historical supplement sourceKind", 100),
        "publisher": _text(source.get("publisher"), "historical supplement publisher", 300),
        "author": source.get("author"),
        "canonicalUrl": _url(source.get("canonicalUrl"), "historical supplement canonicalUrl"),
        "publishedAt": _iso(source.get("publishedAt"), "historical supplement publishedAt"),
        "title": _text(source.get("title"), "historical supplement title", 500),
        "excerpt": excerpt,
        "timestampSeconds": timestamp,
        "topicTags": sorted(set(topics)),
        "reviewReason": _text(source.get("reviewReason"), "historical supplement reviewReason", 1_000) + recurrence,
        "collectionMethod": method,
        "rightsPolicy": rights,
        "purpose": "culture_sensor",
        "canProveClaim": False,
        "canEstablishConsensus": False,
    }
    score = 85.0 + (15 if recurring else 0)
    return score, artifact


def prepare_history_culture_proposal(
    entry_value: Any,
    sweep_value: Any,
    *,
    max_artifacts: int = 4,
    per_source_cap: int = 2,
    min_attention: float = 70,
) -> dict[str, Any]:
    entry = validate_history_entry(entry_value)
    if entry["status"] != "draft":
        raise ValueError("historical culture proposals require a status=draft entry")
    if not 1 <= max_artifacts <= 6:
        raise ValueError("max_artifacts must be between 1 and 6")
    if not 1 <= per_source_cap <= max_artifacts:
        raise ValueError("per_source_cap must be between 1 and max_artifacts")
    if not 0 <= min_attention <= 100:
        raise ValueError("min_attention must be between 0 and 100")
    sweep = _record(sweep_value, "historical culture sweep")
    if sweep.get("schemaVersion") != "historical-culture-sweep/v1":
        raise IssueValidationError("unsupported historical culture sweep schema")
    if sweep.get("canProveClaim") is not False or sweep.get("canEstablishConsensus") is not False or sweep.get("humanApprovalRequired") is not True or sweep.get("autoPublishAllowed") is not False:
        raise IssueValidationError("historical culture sweep safety boundary is invalid")
    entry_years = set(range(int(entry["activeFrom"][:4]), int(entry["activeThrough"][:4]) + 1))
    if sweep.get("year") not in entry_years:
        raise IssueValidationError("historical culture sweep year does not overlap the entry")
    recurring_topics = {
        _text(pattern.get("topicTag"), "cross-source topicTag", 64)
        for pattern in (_record(value, "cross-source pattern") for value in _list(sweep.get("crossSourcePatterns", []), "crossSourcePatterns", 100))
    }
    ranked: list[tuple[float, dict[str, Any]]] = []
    for candidate in _list(sweep.get("candidates"), "historical culture candidates", 100):
        converted = _x_artifact(candidate, entry, recurring_topics, min_attention)
        if converted:
            ranked.append(converted)
    for artifact in _list(sweep.get("supplementalArtifacts", []), "historical culture supplements", 100):
        converted = _supplement_artifact(artifact, entry, recurring_topics)
        if converted:
            ranked.append(converted)
    ranked.sort(key=lambda item: (-item[0], item[1]["publishedAt"], item[1]["artifactId"]))
    selected: list[dict[str, Any]] = []
    source_counts: dict[str, int] = {}
    urls: set[str] = set()
    for _, artifact in ranked:
        source = artifact["sourceKind"]
        if source_counts.get(source, 0) >= per_source_cap or artifact["canonicalUrl"] in urls:
            continue
        selected.append(artifact)
        source_counts[source] = source_counts.get(source, 0) + 1
        urls.add(artifact["canonicalUrl"])
        if len(selected) >= max_artifacts:
            break
    proposal = {
        **entry,
        "cultureArtifacts": selected,
        "contentHash": "pending",
    }
    proposal["contentHash"] = compute_history_content_hash(proposal)
    return validate_history_entry(proposal)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("entry", type=Path)
    parser.add_argument("sweep", type=Path)
    parser.add_argument("--max-artifacts", type=int, default=4)
    parser.add_argument("--per-source-cap", type=int, default=2)
    parser.add_argument("--min-attention", type=float, default=70)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--in-place", action="store_true")
    args = parser.parse_args()
    if args.in_place and args.output is not None:
        parser.error("--in-place cannot be combined with --output")
    entry = json.loads(args.entry.read_text(encoding="utf-8"))
    sweep = json.loads(args.sweep.read_text(encoding="utf-8"))
    proposal = prepare_history_culture_proposal(
        entry, sweep,
        max_artifacts=args.max_artifacts,
        per_source_cap=args.per_source_cap,
        min_attention=args.min_attention,
    )
    output = args.entry if args.in_place else (
        args.output or PROPOSAL_DIR / f"{proposal['entryId']}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{json.dumps(proposal, indent=2, ensure_ascii=False)}\n", encoding="utf-8")
    print(f"Prepared {len(proposal['cultureArtifacts'])} hash-bound culture artifacts: {output}")
    if not args.in_place:
        print("Proposal only; the canonical draft and publication state were not changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
