#!/usr/bin/env python3
"""Add comparative anchoring to biased_opinion_ratings explanations.

For each criterion, rank all 328 races by score. Then append a brief
comparison to a well-known race at the same score level, making abstract
scores concrete. E.g., "Comparable technicality to Belgian Waffle Ride."

Zero API cost — pure data transformation.
"""

import json
import pathlib
import re
import sys

RACE_DATA = pathlib.Path(__file__).parent.parent / "race-data"

# Criteria that benefit from comparison (skip subjective ones like 'value', 'experience')
COMPARABLE_CRITERIA = [
    "technicality", "elevation", "altitude", "length",
    "field_depth", "expenses", "climate",
]

# Well-known anchor races — manually curated T1/T2 races people recognize
# {criterion: {score: [(slug, display_name), ...]}}
# We'll populate this from data, but prefer these well-known names
PREFERRED_ANCHORS = {
    "mid-south", "unbound-gravel", "belgian-waffle-ride", "steamboat-gravel",
    "big-sugar-gravel", "sbt-grvl", "the-rift", "badlands", "atlas-mountain-race",
    "dirty-kanza",  # old name people know
    "gravel-worlds", "leadville-100", "land-run-100",
    "rule-of-three", "gravel-locos", "grinduro", "almanzo-100",
    "bwr-san-diego", "belgian-waffle-ride-san-diego",
    "crusher-in-the-tushar", "lost-and-found-gravel",
    "iowa-wind-and-rock", "rebecca-private-idaho",
    "dirty-30",
}


def load_all_races():
    """Load all race data, return dict of slug -> race data."""
    races = {}
    for f in sorted(RACE_DATA.glob("*.json")):
        d = json.loads(f.read_text())
        race = d.get("race", d)
        races[f.stem] = {
            "file": f,
            "raw": d,
            "race": race,
            "name": race.get("display_name", race.get("name", f.stem)),
            "tier": race.get("gravel_god_rating", {}).get("tier", 4),
            "bor": race.get("biased_opinion_ratings", {}),
        }
    return races


def build_anchor_map(races: dict) -> dict:
    """For each criterion+score, pick the best anchor race.

    Prefers T1/T2 races from PREFERRED_ANCHORS set.
    Returns {criterion: {score: (slug, display_name)}}
    """
    anchors = {}
    for criterion in COMPARABLE_CRITERIA:
        by_score = {}  # score -> list of (slug, name, tier, is_preferred)
        for slug, r in races.items():
            entry = r["bor"].get(criterion, {})
            if not isinstance(entry, dict):
                continue
            score = entry.get("score", 0)
            if score < 1:
                continue
            by_score.setdefault(score, []).append({
                "slug": slug,
                "name": r["name"],
                "tier": r["tier"],
                "preferred": slug in PREFERRED_ANCHORS,
            })

        anchors[criterion] = {}
        for score, candidates in by_score.items():
            # Sort: preferred first, then by tier (lower = more well-known)
            candidates.sort(key=lambda c: (not c["preferred"], c["tier"]))
            best = candidates[0]
            # Also pick a runner-up for variety
            runner_up = candidates[1] if len(candidates) > 1 else None
            anchors[criterion][score] = {
                "primary": (best["slug"], best["name"]),
                "secondary": (runner_up["slug"], runner_up["name"]) if runner_up else None,
            }

    return anchors


def already_has_comparison(explanation: str, all_race_names: set) -> bool:
    """Check if the explanation already mentions another race by name."""
    # Quick check: does it mention any known race name?
    for name in all_race_names:
        if len(name) > 8 and name in explanation:
            return True
    return False


def build_comparison_phrase(criterion: str, score: int, anchor_name: str) -> str:
    """Build a natural comparison phrase."""
    templates = {
        "technicality": {
            1: f"Smoother riding than {anchor_name}.",
            2: f"Less technical than {anchor_name}.",
            3: f"Similar technical demands to {anchor_name}.",
            4: f"More technical than most — comparable to {anchor_name}.",
            5: f"Among the most technical in gravel, on par with {anchor_name}.",
        },
        "elevation": {
            1: f"Flatter profile than {anchor_name}.",
            2: f"Less climbing than {anchor_name}.",
            3: f"Similar elevation profile to {anchor_name}.",
            4: f"More climbing than {anchor_name} at the same score.",
            5: f"Among the hilliest in gravel, comparable to {anchor_name}.",
        },
        "altitude": {
            1: f"Lower altitude than {anchor_name} — no thin-air concerns.",
            2: f"Modest altitude compared to {anchor_name}.",
            3: f"Similar altitude considerations to {anchor_name}.",
            4: f"Higher altitude racing, comparable to {anchor_name}.",
            5: f"Among the highest-altitude events in gravel, on par with {anchor_name}.",
        },
        "length": {
            1: f"Shorter than {anchor_name}.",
            2: f"More compact than {anchor_name}.",
            3: f"Similar distance to {anchor_name}.",
            4: f"Longer than {anchor_name}.",
            5: f"Among the longest in gravel, comparable to {anchor_name}.",
        },
        "field_depth": {
            1: f"Thinner field than {anchor_name}.",
            2: f"Less competitive depth than {anchor_name}.",
            3: f"Similar competitive depth to {anchor_name}.",
            4: f"Deeper field than most — comparable to {anchor_name}.",
            5: f"Elite-level competition, on par with {anchor_name}.",
        },
        "expenses": {
            1: f"More expensive than {anchor_name}.",
            2: f"Higher total cost than {anchor_name}.",
            3: f"Similar expense level to {anchor_name}.",
            4: f"More affordable than {anchor_name}.",
            5: f"Among the best value in gravel, cheaper than {anchor_name}.",
        },
        "climate": {
            1: f"Harsher conditions than {anchor_name}.",
            2: f"More weather exposure than {anchor_name}.",
            3: f"Similar climate challenges to {anchor_name}.",
            4: f"Milder conditions than {anchor_name}.",
            5: f"Among the most weather-friendly events, easier than {anchor_name}.",
        },
    }
    return templates.get(criterion, {}).get(score, f"Comparable to {anchor_name}.")


def main():
    dry_run = "--dry-run" in sys.argv

    races = load_all_races()
    anchors = build_anchor_map(races)
    all_race_names = {r["name"] for r in races.values()}

    total_injected = 0
    changes_by_criterion = {}

    for slug, r in sorted(races.items()):
        modified = False
        bor = r["bor"]

        for criterion in COMPARABLE_CRITERIA:
            entry = bor.get(criterion, {})
            if not isinstance(entry, dict):
                continue
            explanation = entry.get("explanation", "")
            if not explanation:
                continue

            score = entry.get("score", 0)
            if score < 1:
                continue

            # Skip if explanation already references another race
            if already_has_comparison(explanation, all_race_names):
                continue

            # Get anchor for this criterion+score
            score_anchors = anchors.get(criterion, {}).get(score)
            if not score_anchors:
                continue

            # Don't compare a race to itself
            anchor_slug, anchor_name = score_anchors["primary"]
            if anchor_slug == slug:
                if score_anchors["secondary"]:
                    anchor_slug, anchor_name = score_anchors["secondary"]
                else:
                    continue

            # Build comparison and append
            comparison = build_comparison_phrase(criterion, score, anchor_name)

            # Append to end of explanation
            new_explanation = f"{explanation.rstrip()} {comparison}"

            # Don't exceed 700 chars
            if len(new_explanation) > 700:
                continue

            if dry_run:
                print(f"  {slug}.{criterion} (score={score}):")
                print(f"    ADDED: {comparison}")
                print()
                if total_injected > 20:
                    # Just show sample in dry run
                    pass
            else:
                entry["explanation"] = new_explanation
                modified = True

            total_injected += 1
            changes_by_criterion[criterion] = changes_by_criterion.get(criterion, 0) + 1

        if modified and not dry_run:
            r["file"].write_text(json.dumps(r["raw"], indent=2, ensure_ascii=False) + "\n")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Added comparisons to {total_injected} explanations")
    for c, n in sorted(changes_by_criterion.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")


if __name__ == "__main__":
    main()
