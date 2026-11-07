"""Pick'em games: one JSON per game in data/pickem/, shared by the page
generator, the race-page CTA and scripts/score_pickem.py.

A game file names its race (`race_slug`), its page `path`, the lock time
(`lock_utc`, the race start) and the rider lists. A second race is a second
JSON file; nothing here is Unbound-specific.
"""

from __future__ import annotations

import json
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

PICKEM_DIR = Path(__file__).resolve().parent.parent / "data" / "pickem"
CATEGORIES = (("women", "Elite women"), ("men", "Elite men"))
PLACES = ("1st", "2nd", "3rd")


def load_games(pickem_dir: Path = PICKEM_DIR) -> list[dict]:
    """Every game definition (files with a `game` key; leaderboards and
    results files are skipped)."""
    games = []
    for path in sorted(pickem_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("game") and data.get("race_slug"):
            data["_file"] = path
            games.append(data)
    return games


def game_for_race(slug: str, pickem_dir: Path = PICKEM_DIR) -> dict | None:
    for game in load_games(pickem_dir):
        if game["race_slug"] == slug:
            return game
    return None


def lock_time(game: dict) -> datetime:
    return datetime.strptime(game["lock_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def normalize_name(name) -> str:
    """Case-, accent- and spacing-insensitive key for a rider name."""
    if name is None:
        return ""
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.replace("ø", "o").replace("Ø", "o").replace("ł", "l").replace("Ł", "l")
    text = text.replace("'", "").replace("’", "").replace("-", " ").replace(".", " ")
    return " ".join(text.lower().split())


def rider_names(game: dict, category: str) -> list[str]:
    """Deduplicated rider names for one category, in file order."""
    seen, names = set(), []
    for group in game["riders"][category]:
        for name in group["riders"]:
            key = normalize_name(name)
            if key and key not in seen:
                seen.add(key)
                names.append(name)
    return names


def leaderboard_path(game: dict) -> Path:
    return game["_file"].with_name(game["_file"].stem + "-leaderboard.json")


def results_path(game: dict) -> Path:
    return game["_file"].with_name(game["_file"].stem + "-results.json")
