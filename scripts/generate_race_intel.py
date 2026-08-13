#!/usr/bin/env python3
"""Mine deterministic race-profile changes from git history."""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
DEFAULT_OUTPUT = PROJECT_ROOT / "web" / "race-intel.json"
LOOKBACK_MONTHS = 18
MAX_EVENTS_PER_RACE = 5
# Normalization/enrichment sweeps are not news; keep mass edits out of the feed.
BULK_COMMIT_FILE_LIMIT = 20


def _race(data: dict[str, Any] | None) -> dict[str, Any]:
    data = data or {}
    race = data.get("race", data)
    return race if isinstance(race, dict) else {}


def _field(data: dict[str, Any] | None, *path: str) -> Any:
    value: Any = _race(data)
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _confirmed_date_text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    match = re.search(
        r"\b(20\d{2}):\s*([A-Za-z]+\s+\d{1,2})(?:\b|st|nd|rd|th)", value
    )
    if not match:
        return None
    return f"{match.group(1)} edition: {match.group(2)} — date confirmed"


def classify_changes(
    old_dict: dict[str, Any] | None,
    new_dict: dict[str, Any],
) -> list[dict[str, str]]:
    """Classify only the v1 fields named in the product spec."""
    if old_dict is None:
        return [{"type": "added", "text": "Added to the database"}]

    events: list[dict[str, str]] = []
    old_date = _field(old_dict, "vitals", "date_specific")
    new_date = _field(new_dict, "vitals", "date_specific")
    if old_date != new_date:
        text = _confirmed_date_text(new_date)
        if text:
            events.append({"type": "date_confirmed", "text": text})

    old_tier = _field(old_dict, "gravel_god_rating", "tier")
    new_tier = _field(new_dict, "gravel_god_rating", "tier")
    if old_tier != new_tier and old_tier is not None and new_tier is not None:
        events.append({
            "type": "rerated",
            "text": f"Re-rated: Tier {old_tier} → Tier {new_tier}",
        })

    old_score = _field(old_dict, "gravel_god_rating", "overall_score")
    new_score = _field(new_dict, "gravel_god_rating", "overall_score")
    if (
        isinstance(old_score, (int, float))
        and not isinstance(old_score, bool)
        and isinstance(new_score, (int, float))
        and not isinstance(new_score, bool)
        and abs(new_score - old_score) >= 2
    ):
        events.append({
            "type": "rescored",
            "text": f"Score updated: {old_score:g} → {new_score:g}",
        })

    old_website = _field(old_dict, "website")
    new_website = _field(new_dict, "website")
    if old_website != new_website:
        events.append({"type": "site_updated", "text": "Official site link updated"})

    return events


def is_bulk_commit(race_data_files: list[str]) -> bool:
    """Return True when a commit exceeds the v1 race-data noise threshold."""
    return len(set(race_data_files)) > BULK_COMMIT_FILE_LIMIT


def _git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        check=check,
        capture_output=True,
        text=True,
    )
    return proc.stdout


def _history_rows(since_arg: str) -> list[tuple[str, str, str | None, list[str]]]:
    """Read metadata and names in one git process."""
    output = _git(
        "log", "--first-parent", f"--since={since_arg}", "--name-only",
        "--format=%x1e%H%x09%cs%x09%P", "--", "race-data",
    )
    rows = []
    for block in output.split("\x1e"):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        commit, commit_date, parents_text = lines[0].split("\t", 2)
        parents = parents_text.split()
        changed = [
            line for line in lines[1:]
            if line.startswith("race-data/") and line.endswith(".json")
        ]
        rows.append((commit, commit_date, parents[0] if parents else None, changed))
    return rows


def _json_blobs(specs: list[str]) -> dict[str, dict[str, Any] | None]:
    """Resolve historical JSON blobs in bounded cat-file batches."""
    unique_specs = list(dict.fromkeys(specs))
    result: dict[str, dict[str, Any] | None] = {}
    for start in range(0, len(unique_specs), 100):
        batch = unique_specs[start:start + 100]
        proc = subprocess.run(
            ["git", "cat-file", "--batch"],
            cwd=PROJECT_ROOT,
            input=("\n".join(batch) + "\n").encode(),
            capture_output=True,
            check=True,
        )
        stream = io.BytesIO(proc.stdout)
        for spec in batch:
            header = stream.readline().decode("utf-8", errors="replace").rstrip("\n")
            if header.endswith(" missing"):
                result[spec] = None
                continue
            parts = header.rsplit(" ", 2)
            if len(parts) != 3:
                result[spec] = None
                continue
            size = int(parts[2])
            raw = stream.read(size)
            stream.read(1)  # record newline
            try:
                value = json.loads(raw)
            except json.JSONDecodeError:
                value = None
            result[spec] = value if isinstance(value, dict) else None
    return result


def mine_history(
    *,
    since: str | None = None,
    only_slug: str | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Mine the current branch's first-parent history, newest first."""
    since_arg = since or f"{LOOKBACK_MONTHS} months ago"
    rows = _history_rows(since_arg)
    feed: dict[str, list[dict[str, str]]] = {}

    relevant_rows = []
    specs = []
    for commit, commit_date, parent, changed in rows:
        if is_bulk_commit(changed):
            continue
        filtered = [path for path in changed if not only_slug or Path(path).stem == only_slug]
        if not filtered:
            continue
        relevant_rows.append((commit, commit_date, parent, filtered))
        for path in filtered:
            specs.append(f"{commit}:{path}")
            if parent:
                specs.append(f"{parent}:{path}")
    blobs = _json_blobs(specs)

    for commit, commit_date, parent, changed in relevant_rows:
        for path in changed:
            slug = Path(path).stem
            if only_slug and slug != only_slug:
                continue
            if len(feed.get(slug, [])) >= MAX_EVENTS_PER_RACE:
                continue
            new_dict = blobs.get(f"{commit}:{path}")
            if new_dict is None:
                continue
            old_dict = blobs.get(f"{parent}:{path}") if parent else None
            for event in classify_changes(old_dict, new_dict):
                if len(feed.setdefault(slug, [])) >= MAX_EVENTS_PER_RACE:
                    break
                feed[slug].append({"date": commit_date, **event})

    return {slug: events for slug, events in sorted(feed.items()) if events}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    feed = mine_history()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Wrote {args.output} ({len(feed)} races, generated {date.today().isoformat()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
