#!/usr/bin/env python3
"""
Apply cultural_impact bonus dimension to race profiles.

Sets the cultural_impact field (0-5) in gravel_god_rating for notable races.
Also applies approved dimension adjustments for specific races.

Usage:
    python scripts/apply_cultural_impact.py --dry-run   # Preview changes
    python scripts/apply_cultural_impact.py              # Apply changes
"""

import argparse
import json
from pathlib import Path

RACE_DATA = Path(__file__).parent.parent / "race-data"

# ── Cultural Impact Assignments ──────────────────────────────
#
# CI=5: Global Icon — defines gravel cycling, 2000+ riders, massive media
# CI=4: Major International — 1000+ riders, significant international draw
# CI=3: Notable National — nationally recognized, growing media
# CI=2: Established Regional — quality event, dedicated following
# CI=1: Emerging — building reputation
# CI=0: Default — no bonus (most T3/T4 races)

CI_ASSIGNMENTS = {
    # CI=5 — Global Icons
    "unbound-200": 5,
    "the-traka": 5,
    "uci-gravel-worlds": 5,
    "mid-south": 5,
    "unbound-xl": 5,

    # CI=4 — Major International
    "bwr-california": 4,
    "big-sugar": 4,
    "steamboat-gravel": 4,
    "gravel-worlds": 4,
    "dirty-reiver": 4,
    "strade-bianche-gran-fondo": 4,
    "sea-otter-gravel": 4,
    "unbound-100": 4,
    "gravel-earth": 4,

    # CI=3 — Notable National
    "bwr-cedar-city": 3,
    "gravel-locos": 3,
    "migration-gravel-race": 3,
    "the-rift": 3,
    "rule-of-three": 3,
    "pisgah-monster-cross": 3,

    # CI=2 — Established Regional
    "crusher-in-the-tushar": 2,
}

# ── Dimension Adjustments ────────────────────────────────────
# (slug, field, old_value, new_value, reason)

DIMENSION_ADJUSTMENTS = [
    ("unbound-200", "technicality", 3, 4, "Flint Hills limestone is genuinely technical"),
    ("unbound-200", "expenses", 2, 4, "Emporia is accessible and affordable vs coastal events"),
    ("unbound-200", "value", 3, 4, "Premium production matches premium price"),
]


def apply_changes(dry_run=False):
    """Apply CI assignments and dimension adjustments."""
    ci_applied = 0
    ci_skipped = 0
    dim_applied = 0

    # Apply CI assignments
    for slug, ci_value in sorted(CI_ASSIGNMENTS.items()):
        path = RACE_DATA / f"{slug}.json"
        if not path.exists():
            print(f"  SKIP (not found): {slug}")
            ci_skipped += 1
            continue

        data = json.loads(path.read_text())
        race = data.get("race", {})
        rating = race.get("gravel_god_rating", {})
        old_ci = rating.get("cultural_impact")

        if old_ci == ci_value:
            continue

        rating["cultural_impact"] = ci_value
        ci_applied += 1

        label = f"  CI={ci_value}: {slug}"
        if old_ci is not None:
            label += f" (was {old_ci})"
        print(label)

        if not dry_run:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # Apply dimension adjustments
    for slug, field, old_val, new_val, reason in DIMENSION_ADJUSTMENTS:
        path = RACE_DATA / f"{slug}.json"
        if not path.exists():
            print(f"  SKIP dim adj (not found): {slug}")
            continue

        data = json.loads(path.read_text())
        race = data.get("race", {})
        rating = race.get("gravel_god_rating", {})
        current = rating.get(field)

        if current == new_val:
            print(f"  DIM {slug}.{field} already {new_val}")
            continue

        if current != old_val:
            print(f"  WARN {slug}.{field}={current}, expected {old_val} — forcing to {new_val}")

        rating[field] = new_val
        # Also update biased_opinion_ratings to stay in sync
        bor = race.get("biased_opinion_ratings", {})
        if field in bor and isinstance(bor[field], dict):
            bor[field]["score"] = new_val
        dim_applied += 1
        print(f"  DIM {slug}.{field}: {current}→{new_val} ({reason})")

        if not dry_run:
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # Summary
    prefix = "DRY RUN — " if dry_run else ""
    print(f"\n{prefix}SUMMARY")
    print(f"  CI assignments applied: {ci_applied}")
    print(f"  CI slugs not found: {ci_skipped}")
    print(f"  Dimension adjustments: {dim_applied}")


def main():
    parser = argparse.ArgumentParser(description="Apply cultural impact scores to race profiles")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Applying cultural impact scores...\n")
    apply_changes(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
