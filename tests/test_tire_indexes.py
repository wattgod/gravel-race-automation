"""Tire pages list their races from data/indexes/, not from race-data. If the
indexes fall behind the race picks, /tire/{slug}/ pages show the wrong races."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEXES = ROOT / "data" / "indexes"
FIX = "Run python3 scripts/rebuild_tire_indexes.py."


def _race_primaries():
    picks = set()
    for f in (ROOT / "race-data").glob("*.json"):
        race = json.loads(f.read_text(encoding="utf-8"))
        race = race.get("race", race)
        for p in (race.get("tire_recommendations") or {}).get("primary", []):
            picks.add((f.stem, p.get("tire_id"), p.get("rank")))
    return picks


def test_tire_race_map_matches_race_picks():
    index = json.loads((INDEXES / "tire-race-map.json").read_text(encoding="utf-8"))
    indexed = {(e["slug"], tid, e.get("rank"))
               for tid, data in index.items() for e in data.get("races", [])
               if e.get("position", "primary") == "primary"}
    picks = _race_primaries()
    missing = sorted(picks - indexed)[:5]
    extra = sorted(indexed - picks)[:5]
    assert not missing and not extra, f"{FIX} Missing: {missing} Extra: {extra}"


def test_race_tire_map_covers_every_race_with_picks():
    index = json.loads((INDEXES / "race-tire-map.json").read_text(encoding="utf-8"))
    with_picks = {slug for slug, _, _ in _race_primaries()}
    missing = sorted(with_picks - set(index))[:5]
    assert not missing, f"{FIX} Missing: {missing}"
