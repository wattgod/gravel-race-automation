#!/usr/bin/env python3
"""Score a pick'em game and write its public leaderboard.

    python3 scripts/score_pickem.py --entries export.json
    python3 scripts/score_pickem.py --entries export.json --game unbound-200-2027

Reads the worker export (GET /export), the official results at
data/pickem/<game file>-results.json, and writes
data/pickem/<game file>-leaderboard.json with display names only.

Results file:
    {"women": ["1st", "2nd", "3rd"], "men": ["1st", "2nd", "3rd"],
     "aliases": {"Sofía Gómez Villafañe": ["Sofia Gomez", "SGV"]}}

Points per category: 3 for the right rider in the right place, 1 for a
podium rider in the wrong place. Ties: the earlier final entry ranks higher.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))
from pickem import (  # noqa: E402
    CATEGORIES, leaderboard_path, load_games, lock_time, normalize_name, results_path,
)

EXACT_POINTS = 3
PODIUM_POINTS = 1


def _alias_map(results: dict) -> dict[str, str]:
    """normalized alias -> normalized official name."""
    mapping = {}
    for official, aliases in (results.get("aliases") or {}).items():
        for alias in aliases:
            mapping[normalize_name(alias)] = normalize_name(official)
    return mapping


def canonical(name, aliases: dict[str, str]) -> str:
    key = normalize_name(name)
    return aliases.get(key, key)


def score_entry(picks: dict, results: dict, aliases: dict[str, str] | None = None) -> int:
    aliases = aliases if aliases is not None else _alias_map(results)
    points = 0
    for cat, _label in CATEGORIES:
        official = [canonical(n, aliases) for n in results[cat]]
        for i, pick in enumerate((picks.get(cat) or [])[:3]):
            key = canonical(pick, aliases)
            if not key:
                continue
            if i < len(official) and key == official[i]:
                points += EXACT_POINTS
            elif key in official:
                points += PODIUM_POINTS
    return points


def build_leaderboard(entries: list[dict], results: dict, lock_utc: datetime | None = None) -> list[dict]:
    """Ranked rows (display names only). Entries saved after the lock are dropped."""
    aliases = _alias_map(results)
    scored = []
    for e in entries:
        submitted = e.get("submitted_at") or ""
        if lock_utc is not None and submitted:
            when = datetime.fromisoformat(submitted.replace("Z", "+00:00"))
            if when >= lock_utc:
                continue
        scored.append((score_entry(e.get("picks") or {}, results, aliases), submitted, e))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [
        {"rank": i + 1, "display_name": e.get("display_name") or "Anonymous", "points": pts}
        for i, (pts, _submitted, e) in enumerate(scored)
    ]


def unmatched_picks(entries: list[dict], results: dict) -> list[tuple[str, int]]:
    """Free-text picks that match no official podium rider, most common first,
    so near-misses ("Sofia Gomez") can be added to `aliases`."""
    aliases = _alias_map(results)
    official = {canonical(n, aliases) for cat, _ in CATEGORIES for n in results[cat]}
    counts = Counter()
    for e in entries:
        for cat, _ in CATEGORIES:
            for pick in (e.get("picks") or {}).get(cat) or []:
                if pick and canonical(pick, aliases) not in official:
                    counts[pick.strip()] += 1
    return counts.most_common(15)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--entries", required=True, help="JSON from the worker's GET /export")
    parser.add_argument("--game", default=None, help="game id (default: the only game)")
    args = parser.parse_args()

    games = load_games()
    game = next((g for g in games if g["game"] == args.game), None) if args.game else (games[0] if len(games) == 1 else None)
    if game is None:
        print(f"Pick a game with --game: {', '.join(g['game'] for g in games)}", file=sys.stderr)
        return 1

    rpath = results_path(game)
    if not rpath.exists():
        print(f"Missing results file: {rpath}", file=sys.stderr)
        return 1
    results = json.loads(rpath.read_text(encoding="utf-8"))
    for cat, _ in CATEGORIES:
        if len(results.get(cat) or []) != 3:
            print(f"Results need 3 names for {cat}", file=sys.stderr)
            return 1

    export = json.loads(Path(args.entries).read_text(encoding="utf-8"))
    entries = [e for e in export.get("entries", []) if e.get("game", game["game"]) == game["game"]]
    rows = build_leaderboard(entries, results, lock_time(game))

    out = {
        "game": game["game"],
        "scored_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "results": {cat: results[cat] for cat, _ in CATEGORIES},
        "entries": rows,
    }
    lpath = leaderboard_path(game)
    lpath.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Scored {len(rows)} entries -> {lpath}")
    for name, count in unmatched_picks(entries, results):
        print(f"  no podium match: {name!r} x{count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
