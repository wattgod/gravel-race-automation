#!/usr/bin/env python3
"""
Compare before/after enrichment snapshots.

Shows per-criterion diffs: length, proper nouns, numbers, slop removal,
community penetration, and score preservation.

Usage:
    python scripts/enrich_diff.py --slug salty-lizard
    python scripts/enrich_diff.py --slug salty-lizard --detail
    python scripts/enrich_diff.py --all-snapshots
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Add parent dir for community_parser import
sys.path.insert(0, str(Path(__file__).parent))
from community_parser import RE_NO_EVIDENCE, RE_PROPER_NOUN, extract_proper_nouns

RACE_DATA = Path(__file__).parent.parent / "race-data"
SNAPSHOTS = Path(__file__).parent.parent / "data" / "enrichment-snapshots"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"

SCORE_COMPONENTS = [
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses'
]

RE_NUMBER = re.compile(r'\d+')


def extract_community_nouns(slug):
    """Extract proper nouns from community dump."""
    community_path = RESEARCH_DUMPS / f"{slug}-community.md"
    if not community_path.exists():
        return set()
    return extract_proper_nouns(community_path.read_text())


def count_no_evidence(text):
    """Count uncertainty/no-evidence phrases."""
    return len(RE_NO_EVIDENCE.findall(text))


def diff_criterion(key, old_entry, new_entry, community_nouns):
    """Compare one criterion between old and new."""
    old_exp = old_entry.get("explanation", "") if isinstance(old_entry, dict) else ""
    new_exp = new_entry.get("explanation", "") if isinstance(new_entry, dict) else ""
    old_score = old_entry.get("score") if isinstance(old_entry, dict) else None
    new_score = new_entry.get("score") if isinstance(new_entry, dict) else None

    old_nouns = extract_proper_nouns(old_exp)
    new_nouns = extract_proper_nouns(new_exp)
    old_numbers = len(RE_NUMBER.findall(old_exp))
    new_numbers = len(RE_NUMBER.findall(new_exp))
    old_slop = count_no_evidence(old_exp)
    new_slop = count_no_evidence(new_exp)

    # Community nouns that penetrated
    old_community = {n for n in community_nouns if n in old_exp} if community_nouns else set()
    new_community = {n for n in community_nouns if n in new_exp} if community_nouns else set()

    # Score change check
    score_changed = old_score is not None and new_score is not None and old_score != new_score

    # Classify change
    improvements = 0
    regressions = 0

    if len(new_nouns) > len(old_nouns):
        improvements += 1
    elif len(new_nouns) < len(old_nouns):
        regressions += 1

    if new_numbers > old_numbers:
        improvements += 1
    elif new_numbers < old_numbers:
        regressions += 1

    if new_slop < old_slop:
        improvements += 1
    elif new_slop > old_slop:
        regressions += 1

    if len(new_community) > len(old_community):
        improvements += 1
    elif len(new_community) < len(old_community):
        regressions += 1

    if improvements > regressions:
        status = "IMPROVED"
    elif regressions > improvements:
        status = "REGRESSED"
    else:
        status = "UNCHANGED"

    return {
        "key": key,
        "status": status,
        "score_changed": score_changed,
        "old_score": old_score,
        "new_score": new_score,
        "old_explanation": old_exp,
        "new_explanation": new_exp,
        "length_delta": len(new_exp) - len(old_exp),
        "proper_noun_delta": len(new_nouns) - len(old_nouns),
        "old_proper_nouns": old_nouns,
        "new_proper_nouns": new_nouns,
        "number_delta": new_numbers - old_numbers,
        "slop_removed": old_slop > new_slop,
        "old_slop_count": old_slop,
        "new_slop_count": new_slop,
        "community_nouns_old": old_community,
        "community_nouns_new": new_community,
        "new_community_nouns": new_community - old_community,
    }


def diff_profile(slug, detail=False):
    """Compare snapshot vs current profile for a slug."""
    snapshot_path = SNAPSHOTS / f"{slug}-pre.json"
    if not snapshot_path.exists():
        print(f"  No snapshot for {slug}")
        return None

    profile_path = RACE_DATA / f"{slug}.json"
    if not profile_path.exists():
        print(f"  No profile for {slug}")
        return None

    old_bor = json.loads(snapshot_path.read_text())
    data = json.loads(profile_path.read_text())
    race = data.get("race", data)
    new_bor = race.get("biased_opinion_ratings", {})

    community_nouns = extract_community_nouns(slug)

    results = []
    for key in SCORE_COMPONENTS:
        old_entry = old_bor.get(key, {})
        new_entry = new_bor.get(key, {})
        result = diff_criterion(key, old_entry, new_entry, community_nouns)
        results.append(result)

    # Print results
    improved = sum(1 for r in results if r["status"] == "IMPROVED")
    regressed = sum(1 for r in results if r["status"] == "REGRESSED")
    unchanged = sum(1 for r in results if r["status"] == "UNCHANGED")
    score_errors = sum(1 for r in results if r["score_changed"])
    slop_removed = sum(1 for r in results if r["slop_removed"])
    all_new_community = set()
    for r in results:
        all_new_community.update(r["new_community_nouns"])

    print(f"\n{'='*60}")
    print(f"  {slug.upper()}")
    print(f"{'='*60}")

    for r in results:
        status_icon = {"IMPROVED": "+", "REGRESSED": "-", "UNCHANGED": "="}[r["status"]]
        score_warn = " [SCORE CHANGED!]" if r["score_changed"] else ""
        print(f"  [{status_icon}] {r['key']}: {r['status']}{score_warn}")

        if detail:
            print(f"      Length: {len(r['old_explanation'])} → {len(r['new_explanation'])} ({r['length_delta']:+d})")
            print(f"      Proper nouns: {len(r['old_proper_nouns'])} → {len(r['new_proper_nouns'])} ({r['proper_noun_delta']:+d})")
            print(f"      Numbers: {r['number_delta']:+d}")
            if r["slop_removed"]:
                print(f"      Slop removed: {r['old_slop_count']} → {r['new_slop_count']}")
            if r["new_community_nouns"]:
                print(f"      + Community nouns: {', '.join(sorted(r['new_community_nouns']))}")
            if r["status"] != "UNCHANGED":
                old_preview = r["old_explanation"][:100] + "..." if len(r["old_explanation"]) > 100 else r["old_explanation"]
                new_preview = r["new_explanation"][:100] + "..." if len(r["new_explanation"]) > 100 else r["new_explanation"]
                print(f"      OLD: \"{old_preview}\"")
                print(f"      NEW: \"{new_preview}\"")
            print()

    print(f"\n  SUMMARY: {improved} improved, {unchanged} unchanged, {regressed} regressed")
    if score_errors:
        print(f"  ** {score_errors} SCORE CHANGES DETECTED (ERROR!) **")
    if slop_removed:
        print(f"  Slop phrases removed in {slop_removed} criteria")
    if all_new_community:
        print(f"  Community nouns that penetrated: {', '.join(sorted(all_new_community)[:10])}")
    print()

    return {
        "slug": slug,
        "improved": improved,
        "unchanged": unchanged,
        "regressed": regressed,
        "score_errors": score_errors,
        "slop_removed": slop_removed,
        "new_community_nouns": all_new_community,
    }


def main():
    parser = argparse.ArgumentParser(description="Compare enrichment before/after snapshots")
    parser.add_argument("--slug", help="Specific slug to diff")
    parser.add_argument("--all-snapshots", action="store_true",
                        help="Diff all available snapshots")
    parser.add_argument("--detail", action="store_true",
                        help="Show detailed per-criterion diffs")
    args = parser.parse_args()

    if not SNAPSHOTS.exists():
        print(f"No snapshots directory at {SNAPSHOTS}")
        print("Run batch_enrich.py --force first to create snapshots.")
        return

    if args.slug:
        diff_profile(args.slug, detail=args.detail)
    elif args.all_snapshots:
        snapshot_files = sorted(SNAPSHOTS.glob("*-pre.json"))
        if not snapshot_files:
            print("No snapshots found.")
            return

        all_results = []
        for f in snapshot_files:
            slug = f.stem.replace("-pre", "")
            result = diff_profile(slug, detail=args.detail)
            if result:
                all_results.append(result)

        if all_results:
            print(f"\n{'='*60}")
            print("  OVERALL SUMMARY")
            print(f"{'='*60}")
            total_improved = sum(r["improved"] for r in all_results)
            total_unchanged = sum(r["unchanged"] for r in all_results)
            total_regressed = sum(r["regressed"] for r in all_results)
            total_score_errors = sum(r["score_errors"] for r in all_results)
            total_slop = sum(r["slop_removed"] for r in all_results)
            all_community = set()
            for r in all_results:
                all_community.update(r["new_community_nouns"])

            print(f"  Profiles diffed: {len(all_results)}")
            print(f"  Criteria improved: {total_improved}")
            print(f"  Criteria unchanged: {total_unchanged}")
            print(f"  Criteria regressed: {total_regressed}")
            if total_score_errors:
                print(f"  ** SCORE ERRORS: {total_score_errors} **")
            print(f"  Slop phrases removed: {total_slop}")
            print(f"  Community nouns penetrated: {len(all_community)}")
            print()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
