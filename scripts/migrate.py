#!/usr/bin/env python3
"""
Migrate v1/v2/v3 race profiles → canonical schema.

For races that exist in multiple formats, merges data by taking the
richest content per field (longer prose, more suffering zones, real
names over generic ones).

Outputs canonical JSON to race-data/ (overwriting v1 files in place,
adding new files for races only in v2/v3).

Usage:
    python migrate.py --dry-run                  # Preview what would change
    python migrate.py                             # Execute migration
    python migrate.py --race unbound-200          # Migrate single race
    python migrate.py --diff                      # Show field-level diffs
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


# Source directories
V1_DIR = Path(__file__).parent.parent / "race-data"
V2_DIR = Path.home() / "Documents/GravelGod/project/gravel-plans-experimental/data"
V3_DIR = Path.home() / "Documents/GravelGod/project/gravel-landing-page-project/races"

# Slug normalization map (different naming conventions across sources)
SLUG_ALIASES = {
    "crusher-tushar": "crusher-in-the-tushar",
    "leadville-trail-100-mtb": "leadville-100",
    "traka-360": "the-traka",
    "belgian-waffle-ride": "bwr-california",
}

# Reverse mapping for V3 filenames (underscores, full names)
V3_SLUG_MAP = {
    "unbound_gravel_200": "unbound-200",
    "mid_south": "mid-south",
}


def load_v1(slug: str) -> Optional[dict]:
    """Load V1 race JSON from race-data/."""
    path = V1_DIR / f"{slug}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def load_v2(slug: str) -> Optional[dict]:
    """Load V2 race JSON from experimental/data/."""
    path = V2_DIR / f"{slug}-data.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def load_v3(slug: str) -> Optional[dict]:
    """Load V3/V4 race JSON from landing-page-project/races/."""
    # Try both slug formats
    for v3_slug, canonical_slug in V3_SLUG_MAP.items():
        if canonical_slug == slug:
            path = V3_DIR / f"{v3_slug}.json"
            if path.exists():
                return json.loads(path.read_text())
    # Also try direct match with underscores
    underscore_slug = slug.replace("-", "_")
    path = V3_DIR / f"{underscore_slug}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def _pick_richer(a, b, field_name: str = ""):
    """Pick the richer value between two options."""
    if a is None or a == "" or a == [] or a == {}:
        return b
    if b is None or b == "" or b == [] or b == {}:
        return a
    # For strings: pick longer
    if isinstance(a, str) and isinstance(b, str):
        return a if len(a) >= len(b) else b
    # For lists: pick longer
    if isinstance(a, list) and isinstance(b, list):
        return a if len(a) >= len(b) else b
    # For dicts: merge (a wins on conflicts)
    if isinstance(a, dict) and isinstance(b, dict):
        merged = dict(b)
        merged.update(a)
        return merged
    # Default: prefer a (first source)
    return a


def _get_score_from_v1(race: dict, var: str) -> Optional[int]:
    """Extract score from V1 nested format."""
    for section in ("course_profile", "biased_opinion_ratings"):
        entry = race.get(section, {}).get(var, {})
        if isinstance(entry, dict) and "score" in entry:
            return entry["score"]
    return None


def _get_score_from_v2(race: dict, var: str) -> Optional[int]:
    """Extract score from V2 flat format (under gravel_god_rating)."""
    rating = race.get("gravel_god_rating", {})
    val = rating.get(var)
    if isinstance(val, (int, float)):
        return int(val)
    return None


def merge_to_canonical(v1: Optional[dict], v2: Optional[dict], v3: Optional[dict], slug: str) -> dict:
    """Merge v1/v2/v3 data into canonical schema."""
    # Start with v2 as base (richest race-profile format), fall back to v1
    if v2:
        race = v2.get("race", {})
    elif v1:
        race = v1.get("race", {})
    else:
        race = {}

    # Merge vitals
    v1_race = (v1 or {}).get("race", {})
    v2_race = (v2 or {}).get("race", {})
    v3_data = v3 or {}

    vitals = _pick_richer(
        v2_race.get("vitals", {}),
        v1_race.get("vitals", {}),
    )

    # Build 14 scores — prefer v2 flat format, fall back to v1 nested
    course_vars = ["logistics", "length", "technicality", "elevation", "climate", "altitude", "adventure"]
    editorial_vars = ["prestige", "race_quality", "experience", "community", "field_depth", "value", "expenses"]

    scores = {}
    for var in course_vars + editorial_vars:
        score = _get_score_from_v2(v2_race, var) or _get_score_from_v1(v1_race, var)
        if score is not None:
            scores[var] = score

    # Get existing overall score or calculate
    existing_overall = (
        v2_race.get("gravel_god_rating", {}).get("overall_score")
        or v1_race.get("gravel_god_rating", {}).get("overall_score")
    )
    if len(scores) == 14:
        calculated = round((sum(scores.values()) / 70) * 100)
    else:
        calculated = existing_overall

    # Determine tier
    overall = existing_overall or calculated or 0
    if overall >= 80:
        tier = 1
    elif overall >= 60:
        tier = 2
    elif overall >= 45:
        tier = 3
    else:
        tier = 4

    # Check for prestige override
    prestige_score = scores.get("prestige", 0)
    tier_override = None
    if prestige_score == 5:
        if overall >= 75 and tier > 1:
            tier = 1
            tier_override = "Prestige 5 + score >= 75 — promoted to Tier 1"
        elif tier > 2:
            tier = 2
            tier_override = "Prestige 5 — promoted to Tier 2 (score < 75)"
    elif prestige_score == 4 and tier > 2:
        tier = tier - 1
        tier_override = "Prestige 4 — promoted 1 tier (not into T1)"

    # Build gravel_god_rating
    rating = {
        "overall_score": overall,
        "tier": tier,
        "tier_label": f"TIER {tier}",
        **scores,
    }

    # Preserve extra rating metadata
    for extra_key in ("course_profile", "biased_opinion", "tier_note", "score_note",
                      "tier_override_reason", "editorial_tier", "editorial_tier_label",
                      "business_tier", "business_tier_label", "display_tier", "display_tier_label"):
        for source in (v2_race.get("gravel_god_rating", {}), v1_race.get("gravel_god_rating", {})):
            if extra_key in source and extra_key not in rating:
                rating[extra_key] = source[extra_key]

    if tier_override:
        rating["tier_override_reason"] = _pick_richer(
            rating.get("tier_override_reason", ""),
            tier_override
        )

    # Merge prose sections
    canonical = {
        "race": {
            "name": v2_race.get("name") or v1_race.get("name") or slug.replace("-", " ").title(),
            "slug": slug,
            "display_name": v2_race.get("display_name") or v1_race.get("display_name") or v2_race.get("name") or v1_race.get("name", ""),
            "tagline": _pick_richer(v2_race.get("tagline"), v1_race.get("tagline")),
            "race_challenge_tagline": v2_race.get("race_challenge_tagline", ""),
            "vitals": vitals,
            "climate": _pick_richer(v2_race.get("climate", {}), v1_race.get("climate", {})),
            "terrain": _pick_richer(v2_race.get("terrain", {}), v1_race.get("terrain", {})),
            "gravel_god_rating": rating,
            "course_profile": _pick_richer(v1_race.get("course_profile", {}), v2_race.get("course_profile", {})),
            "biased_opinion_ratings": _pick_richer(v1_race.get("biased_opinion_ratings", {}), v2_race.get("biased_opinion_ratings", {})),
            "biased_opinion": _pick_richer(v2_race.get("biased_opinion", {}), v1_race.get("biased_opinion", {})),
            "black_pill": _pick_richer(v2_race.get("black_pill", {}), v1_race.get("black_pill", {})),
            "final_verdict": _pick_richer(v2_race.get("final_verdict", {}), v1_race.get("final_verdict", {})),
            "logistics": _pick_richer(v2_race.get("logistics", {}), v1_race.get("logistics", {})),
            "history": _pick_richer(v2_race.get("history", {}), v1_race.get("history", {})),
            "course_description": _pick_richer(v2_race.get("course_description", {}), v1_race.get("course_description", {})),
            # Guide / training blocks (optional)
            "guide_variables": v2_race.get("guide_variables", v1_race.get("guide_variables", {})),
            "non_negotiables": v2_race.get("non_negotiables", v1_race.get("non_negotiables", [])),
            "race_specific": v2_race.get("race_specific", v1_race.get("race_specific", {})),
            "training_implications": v2_race.get("training_implications", v1_race.get("training_implications", {})),
            # Research metadata
            "research_metadata": {
                "data_confidence": "migrated",
                "validation_status": "pending",
                "sources": ["v1", "v2"] if (v1 and v2) else (["v1"] if v1 else ["v2"]),
                "migration_notes": [],
            },
        }
    }

    # Enrich from V3 if available (training config blocks)
    if v3:
        race_out = canonical["race"]
        for key in ("workout_modifications", "masterclass_topics", "tier_overrides", "marketplace_variables"):
            if key in v3 and v3[key]:
                race_out.setdefault("training_config", {})[key] = v3[key]

        # V3 has richer non_negotiables
        v3_non_neg = v3.get("non_negotiables", [])
        if len(v3_non_neg) > len(race_out.get("non_negotiables", [])):
            race_out["non_negotiables"] = v3_non_neg

        # V3 has race_specific enrichment
        v3_specific = v3.get("race_specific", {})
        if v3_specific:
            race_out["race_specific"] = _pick_richer(v3_specific, race_out.get("race_specific", {}))

        # V3 guide_variables
        v3_gv = v3.get("guide_variables", {})
        if v3_gv:
            race_out["guide_variables"] = _pick_richer(v3_gv, race_out.get("guide_variables", {}))

        canonical["race"]["research_metadata"]["sources"].append("v3")

    # Clean up empty fields
    race_out = canonical["race"]
    for key in list(race_out.keys()):
        if race_out[key] is None or race_out[key] == "" or race_out[key] == {} or race_out[key] == []:
            if key not in ("name", "slug", "display_name", "tagline", "vitals", "gravel_god_rating", "research_metadata"):
                del race_out[key]

    return canonical


def discover_all_slugs() -> set:
    """Discover all unique race slugs across v1/v2/v3 sources."""
    slugs = set()

    # V1
    for f in V1_DIR.glob("*.json"):
        slugs.add(f.stem)

    # V2
    for f in V2_DIR.glob("*-data.json"):
        slug = f.stem.replace("-data", "")
        # Normalize aliases
        slug = SLUG_ALIASES.get(slug, slug)
        slugs.add(slug)

    # V3
    for f in V3_DIR.glob("*.json"):
        if f.stem == "race_schema_template":
            continue
        slug = V3_SLUG_MAP.get(f.stem, f.stem.replace("_", "-"))
        slugs.add(slug)

    return slugs


def get_v2_slug(canonical_slug: str) -> str:
    """Get the v2 slug for a canonical slug (reverse alias lookup)."""
    reverse_aliases = {v: k for k, v in SLUG_ALIASES.items()}
    return reverse_aliases.get(canonical_slug, canonical_slug)


def diff_report(old: dict, new: dict, slug: str) -> list:
    """Generate field-level diff between old and new JSON."""
    diffs = []

    def walk(old_obj, new_obj, path=""):
        if type(old_obj) != type(new_obj):
            diffs.append(f"  TYPE CHANGE {path}: {type(old_obj).__name__} → {type(new_obj).__name__}")
            return
        if isinstance(old_obj, dict):
            all_keys = set(list(old_obj.keys()) + list(new_obj.keys()))
            for k in sorted(all_keys):
                p = f"{path}.{k}" if path else k
                if k not in old_obj:
                    diffs.append(f"  + ADDED {p}")
                elif k not in new_obj:
                    diffs.append(f"  - REMOVED {p}")
                else:
                    walk(old_obj[k], new_obj[k], p)
        elif isinstance(old_obj, list):
            if len(old_obj) != len(new_obj):
                diffs.append(f"  ~ LENGTH {path}: {len(old_obj)} → {len(new_obj)}")
        elif isinstance(old_obj, str):
            if old_obj != new_obj:
                old_preview = old_obj[:60] + "..." if len(old_obj) > 60 else old_obj
                new_preview = new_obj[:60] + "..." if len(new_obj) > 60 else new_obj
                diffs.append(f"  ~ CHANGED {path}: \"{old_preview}\" → \"{new_preview}\"")
        elif old_obj != new_obj:
            diffs.append(f"  ~ CHANGED {path}: {old_obj} → {new_obj}")

    walk(old, new, "")
    return diffs


def migrate_race(slug: str, dry_run: bool = False, show_diff: bool = False) -> dict:
    """Migrate a single race to canonical format."""
    v2_slug = get_v2_slug(slug)

    v1 = load_v1(slug)
    v2 = load_v2(v2_slug)
    v3 = load_v3(slug)

    if not v1 and not v2 and not v3:
        return {"slug": slug, "status": "skipped", "reason": "no source data found"}

    canonical = merge_to_canonical(v1, v2, v3, slug)

    result = {
        "slug": slug,
        "sources": canonical["race"]["research_metadata"]["sources"],
        "overall_score": canonical["race"]["gravel_god_rating"]["overall_score"],
        "tier": canonical["race"]["gravel_god_rating"]["tier"],
    }

    if show_diff and v1:
        diffs = diff_report(v1, canonical, slug)
        result["diff_count"] = len(diffs)
        result["diffs"] = diffs

    if not dry_run:
        output_path = V1_DIR / f"{slug}.json"
        output_path.write_text(json.dumps(canonical, indent=2, ensure_ascii=False) + "\n")
        result["status"] = "migrated"
        result["output"] = str(output_path)
    else:
        result["status"] = "dry_run"

    return result


def main():
    parser = argparse.ArgumentParser(description="Migrate race profiles to canonical schema")
    parser.add_argument("--race", help="Migrate a single race by slug")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--diff", action="store_true", help="Show field-level diffs")
    parser.add_argument("--json-output", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    if args.race:
        result = migrate_race(args.race, dry_run=args.dry_run, show_diff=args.diff)
        if args.json_output:
            print(json.dumps(result, indent=2))
        else:
            print(f"\n{result['slug']}: {result['status']}")
            if "sources" in result:
                print(f"  Sources: {', '.join(result['sources'])}")
                print(f"  Score: {result.get('overall_score')} (Tier {result.get('tier')})")
            if "diffs" in result:
                for d in result["diffs"][:20]:
                    print(d)
                if len(result.get("diffs", [])) > 20:
                    print(f"  ... and {len(result['diffs']) - 20} more changes")
    else:
        slugs = sorted(discover_all_slugs())
        print(f"\nDiscovered {len(slugs)} unique races across all sources\n")

        results = []
        for slug in slugs:
            result = migrate_race(slug, dry_run=args.dry_run, show_diff=args.diff)
            results.append(result)

            status_icon = "✓" if result["status"] in ("migrated", "dry_run") else "✗"
            sources = ", ".join(result.get("sources", []))
            score = result.get("overall_score", "?")
            tier = result.get("tier", "?")
            print(f"  {status_icon} {slug:<40} [{sources}] → Score {score} (Tier {tier})")

            if args.diff and "diffs" in result:
                for d in result["diffs"][:5]:
                    print(f"    {d}")
                if len(result.get("diffs", [])) > 5:
                    print(f"    ... and {len(result['diffs']) - 5} more")

        if args.json_output:
            print(json.dumps(results, indent=2))

        migrated = [r for r in results if r["status"] in ("migrated", "dry_run")]
        skipped = [r for r in results if r["status"] == "skipped"]
        print(f"\n{'Would migrate' if args.dry_run else 'Migrated'}: {len(migrated)}")
        if skipped:
            print(f"Skipped: {len(skipped)} — {[r['slug'] for r in skipped]}")


if __name__ == "__main__":
    main()
