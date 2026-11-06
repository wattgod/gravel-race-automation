"""Build-time check that a race page doesn't contradict itself.

Search engines and AI answers drop or distrust pages whose facts disagree
("68 miles" in the tiles, "75 miles" in the workouts). The 2026-10 audit of
/race/gravel-revival/ found exactly that, plus rider reports copied in from a
different event. This module catches the mechanical contradictions:

  * distance: race-data `vitals.distance_mi` vs `guide_variables.race_distance`
    and vs the workout pack in web/race-packs/{slug}.json (built from vitals
    at generation time, so it goes stale when vitals change);
  * edition: more than one "Nth annual" in the page's own narrative text.

It can't tell that a quote belongs to another race; that still needs a human.
tests/test_fact_consistency.py runs it over every profile and ratchets
against config/fact-consistency-baseline.json, so no new contradiction ships.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_PACKS_DIR = PROJECT_ROOT / "web" / "race-packs"
DISTANCE_TOLERANCE = 0.05

_MILES = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(?:mi\b|miles?\b)", re.I)
_ORDINAL_ANNUAL = re.compile(r"\b(\d{1,3})(?:st|nd|rd|th)[\s-]+annual\b", re.I)


def _miles(text) -> Optional[float]:
    if not isinstance(text, str):
        return None
    match = _MILES.search(text)
    return float(match.group(1).replace(",", "")) if match else None


def _differs(a: float, b: float) -> bool:
    return abs(a - b) / max(a, b) > DISTANCE_TOLERANCE


def _narrative_text(race: dict) -> str:
    """Prose the page renders as its own claims (not source titles/URLs)."""
    parts = []
    for entry in (race.get("biased_opinion_ratings") or {}).values():
        if isinstance(entry, dict):
            parts.append(str(entry.get("explanation") or ""))
    for key in ("biased_opinion", "final_verdict", "history", "course_description"):
        value = race.get(key)
        parts.append(json.dumps(value, ensure_ascii=False) if value else "")
    parts.append(str(race.get("tagline") or ""))
    return "\n".join(parts)


def check_race(race: dict, slug: str, packs_dir: Path = RACE_PACKS_DIR) -> list[str]:
    """Return human-readable contradictions for one race profile."""
    issues = []
    distance = (race.get("vitals") or {}).get("distance_mi")
    if isinstance(distance, (int, float)) and distance > 0:
        guide = _miles((race.get("guide_variables") or {}).get("race_distance"))
        if guide and _differs(distance, guide):
            issues.append(
                f"distance: vitals say {distance:g} mi, guide_variables.race_distance "
                f"says {guide:g} mi"
            )
        pack_file = packs_dir / f"{slug}.json"
        if pack_file.exists():
            try:
                pack_distance = json.loads(pack_file.read_text(encoding="utf-8")).get("distance_mi")
            except (json.JSONDecodeError, OSError):
                pack_distance = None
            if isinstance(pack_distance, (int, float)) and pack_distance > 0 \
                    and _differs(distance, pack_distance):
                issues.append(
                    f"distance: vitals say {distance:g} mi, workout pack says "
                    f"{pack_distance:g} mi (regenerate: python scripts/"
                    f"generate_race_pack_previews.py --slug {slug})"
                )

    editions = sorted({int(n) for n in _ORDINAL_ANNUAL.findall(_narrative_text(race))})
    if len(editions) > 1:
        issues.append(
            "edition: narrative names more than one 'Nth annual' edition: "
            + ", ".join(str(n) for n in editions)
        )
    return issues


def check_all(race_data_dir: Path = PROJECT_ROOT / "race-data",
              packs_dir: Path = RACE_PACKS_DIR) -> dict[str, list[str]]:
    """{slug: [issues]} for every profile with at least one contradiction."""
    found = {}
    for path in sorted(Path(race_data_dir).glob("*.json")):
        try:
            race = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        issues = check_race(race.get("race", race), path.stem, packs_dir)
        if issues:
            found[path.stem] = issues
    return found


if __name__ == "__main__":
    results = check_all()
    for slug, issues in results.items():
        for issue in issues:
            print(f"{slug}: {issue}")
    print(f"\n{len(results)} profiles with contradictions")
