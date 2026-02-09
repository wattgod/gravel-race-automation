#!/usr/bin/env python3
"""
Recalculate tiers for all race profiles with updated prestige rules.

Prestige override logic:
  - prestige=5 AND score >= 75 → Tier 1
  - prestige=5 AND score < 75  → Tier 2 (capped, not T1)
  - prestige=4 → promote 1 tier but NOT into Tier 1

Discipline tagging:
  - Known MTB slugs → "mtb"
  - All others → "gravel"

Usage:
    python recalculate_tiers.py --dry-run     # Preview changes
    python recalculate_tiers.py               # Apply changes
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Tuple

RACE_DATA = Path(__file__).parent.parent / "race-data"

# Tier thresholds
T1_THRESHOLD = 80
T2_THRESHOLD = 60
T3_THRESHOLD = 45

# Prestige-5 floor for T1 promotion
P5_T1_FLOOR = 75

# MTB discipline slugs
MTB_SLUGS = {"chequamegon-mtb", "fuego-mtb", "little-sugar-mtb", "leadville-100"}


def calculate_tier(overall_score: int) -> int:
    """Calculate base tier from overall score."""
    if overall_score >= T1_THRESHOLD:
        return 1
    elif overall_score >= T2_THRESHOLD:
        return 2
    elif overall_score >= T3_THRESHOLD:
        return 3
    else:
        return 4


def apply_prestige_override(tier: int, prestige: int, overall_score: int) -> Tuple[int, Optional[str]]:
    """Apply prestige override rules. Returns (new_tier, override_reason)."""
    if prestige == 5:
        if overall_score >= P5_T1_FLOOR and tier > 1:
            return 1, f"Prestige 5 + score >= {P5_T1_FLOOR} — promoted to Tier 1"
        elif overall_score < P5_T1_FLOOR and tier > 2:
            return 2, f"Prestige 5 — promoted to Tier 2 (score < {P5_T1_FLOOR})"
        elif overall_score < P5_T1_FLOOR and tier <= 2:
            # Already T2 or better by score but doesn't meet P5 T1 floor
            # If currently T1 by override but score < 75, demote to T2
            return tier, None
    elif prestige == 4:
        if tier > 2:
            return tier - 1, "Prestige 4 — promoted 1 tier (not into T1)"
        # prestige=4 does NOT promote into T1
    return tier, None


def recalculate_race(data: dict, slug: str) -> dict:
    """Recalculate tier for a single race. Returns change info."""
    race = data.get("race", {})
    rating = race.get("gravel_god_rating", {})

    overall = rating.get("overall_score", 0)
    prestige = rating.get("prestige", 0)
    old_tier = rating.get("tier", 3)
    old_override = rating.get("tier_override_reason")

    # Calculate base tier from score
    base_tier = calculate_tier(overall)

    # Apply prestige override
    new_tier, override_reason = apply_prestige_override(base_tier, prestige, overall)

    # Discipline tag
    discipline = "mtb" if slug in MTB_SLUGS else "gravel"

    # Build change record
    changed = (new_tier != old_tier) or ("discipline" not in rating)
    change = {
        "slug": slug,
        "overall_score": overall,
        "prestige": prestige,
        "old_tier": old_tier,
        "new_tier": new_tier,
        "base_tier": base_tier,
        "discipline": discipline,
        "tier_changed": new_tier != old_tier,
        "override_reason": override_reason,
        "old_override": old_override,
    }

    # Update the data
    rating["tier"] = new_tier
    rating["tier_label"] = f"TIER {new_tier}"
    rating["discipline"] = discipline

    # Sync display_tier and editorial_tier if present
    for key in ("display_tier", "editorial_tier", "business_tier"):
        if key in rating:
            rating[key] = new_tier
    for key in ("display_tier_label", "editorial_tier_label", "business_tier_label"):
        if key in rating:
            rating[key] = f"TIER {new_tier}"

    if override_reason:
        rating["tier_override_reason"] = override_reason
    elif "tier_override_reason" in rating:
        # Remove stale override reason if no override was applied
        del rating["tier_override_reason"]

    return change


def main():
    parser = argparse.ArgumentParser(description="Recalculate tiers with updated prestige rules")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    profiles = sorted(RACE_DATA.glob("*.json"))
    print(f"\nProcessing {len(profiles)} race profiles...\n")

    changes = []
    demotions = []
    promotions = []
    discipline_tags = {"gravel": 0, "mtb": 0}

    for path in profiles:
        slug = path.stem
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"  SKIP invalid JSON: {path.name}")
            continue

        change = recalculate_race(data, slug)
        changes.append(change)
        discipline_tags[change["discipline"]] += 1

        if change["tier_changed"]:
            direction = "DEMOTE" if change["new_tier"] > change["old_tier"] else "PROMOTE"
            icon = "↓" if direction == "DEMOTE" else "↑"
            print(f"  {icon} {slug:<40} T{change['old_tier']}→T{change['new_tier']}  score={change['overall_score']}  p={change['prestige']}")
            if direction == "DEMOTE":
                demotions.append(change)
            else:
                promotions.append(change)

            if not args.dry_run:
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        else:
            # Still write to add discipline tag if missing
            if not args.dry_run:
                path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    # Summary
    print(f"\n{'DRY RUN — ' if args.dry_run else ''}SUMMARY")
    print(f"  Total profiles: {len(changes)}")
    print(f"  Demotions: {len(demotions)}")
    for d in demotions:
        print(f"    {d['slug']}: T{d['old_tier']}→T{d['new_tier']} (score={d['overall_score']}, p={d['prestige']})")
    print(f"  Promotions: {len(promotions)}")
    for p in promotions:
        print(f"    {p['slug']}: T{p['old_tier']}→T{p['new_tier']} (score={p['overall_score']}, p={p['prestige']})")
    print(f"  Discipline: gravel={discipline_tags['gravel']}, mtb={discipline_tags['mtb']}")

    # Tier distribution
    tier_dist = {1: 0, 2: 0, 3: 0, 4: 0}
    for c in changes:
        tier_dist[c["new_tier"]] += 1
    print(f"  Tier distribution: T1={tier_dist[1]}, T2={tier_dist[2]}, T3={tier_dist[3]}, T4={tier_dist[4]}")


if __name__ == "__main__":
    main()
