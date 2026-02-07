#!/usr/bin/env python3
"""
Profile triage — identifies enrichment priorities.

Scores each profile on content richness and flags gaps:
  - Date specificity (TBD vs real dates)
  - Content depth (biased_opinion explanations, key_features, etc.)
  - Research coverage (has research dump, brief)
  - Boilerplate detection (generic filler phrases)

Usage:
    python scripts/triage_profiles.py                    # Full report
    python scripts/triage_profiles.py --dates            # Date gaps only
    python scripts/triage_profiles.py --thin             # Thinnest profiles only
    python scripts/triage_profiles.py --csv              # Export CSV for spreadsheet
    python scripts/triage_profiles.py --enrich-queue N   # Top N enrichment candidates
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

RACE_DATA = Path(__file__).parent.parent / "race-data"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"
BRIEFS = Path(__file__).parent.parent / "briefs"

# Boilerplate phrases that indicate template/generic content
BOILERPLATE = [
    "challenging terrain",
    "beautiful scenery",
    "unforgettable experience",
    "amazing experience",
    "world-class event",
    "truly unique",
    "one of a kind",
    "must-do event",
    "bucket list",
]

SCORE_COMPONENTS = [
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses'
]


def load_profile(path):
    """Load a race profile, handling race wrapper."""
    data = json.loads(path.read_text())
    return data.get("race", data)


def get_research_slugs():
    """Get sets of slugs that have research dumps and briefs."""
    dumps = set()
    if RESEARCH_DUMPS.exists():
        for f in RESEARCH_DUMPS.glob("*-raw.md"):
            dumps.add(f.stem.replace("-raw", ""))
    briefs = set()
    if BRIEFS.exists():
        for f in BRIEFS.glob("*-brief.md"):
            briefs.add(f.stem.replace("-brief", ""))
    return dumps, briefs


def classify_date(race):
    """Classify date specificity. Returns (category, date_str)."""
    vitals = race.get("vitals", {})
    date = vitals.get("date", "")
    date_specific = vitals.get("date_specific", "")

    if not date and not date_specific:
        return "missing", ""

    # Check date_specific for real dates
    ds = str(date_specific)
    if "TBD" in ds.upper():
        return "tbd", ds
    if re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}', ds):
        return "specific", ds
    if re.search(r'\d{4}:\s*\w+\s+\d', ds):
        return "specific", ds

    # Fall back to date field
    d = str(date)
    if re.search(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}', d):
        return "specific", d
    if any(c.isdigit() for c in d):
        return "partial", d

    return "generic", d


def detect_boilerplate(race):
    """Count boilerplate phrases in profile text."""
    text = json.dumps(race).lower()
    return sum(1 for phrase in BOILERPLATE if phrase in text)


def score_profile(race, slug, dump_slugs, brief_slugs):
    """Score a profile's enrichment level (0-10). Higher = richer."""
    score = 0
    flags = []

    # Rich biased_opinion_ratings with explanations (+3)
    bor = race.get("biased_opinion_ratings", {})
    if bor and isinstance(bor, dict):
        explained = sum(1 for v in bor.values() if isinstance(v, dict) and v.get("explanation"))
        if explained >= 7:
            score += 3
        elif explained >= 1:
            score += 1
            flags.append(f"partial_opinions({explained}/14)")
    else:
        flags.append("no_opinions")

    # key_features section (+2)
    if race.get("key_features"):
        score += 2
    else:
        flags.append("no_key_features")

    # Course description with substance (+1)
    cd = race.get("course_description", "")
    if isinstance(cd, dict):
        char = cd.get("character", "")
        zones = cd.get("suffering_zones", [])
        if len(str(char)) > 50 and len(zones) >= 2:
            score += 1
    elif isinstance(cd, str) and len(cd) > 100:
        score += 1

    # Has research dump (+1)
    if slug in dump_slugs:
        score += 1
    else:
        flags.append("no_research_dump")

    # Has brief (+1)
    if slug in brief_slugs:
        score += 1
    else:
        flags.append("no_brief")

    # Date specificity (+1)
    date_cat, _ = classify_date(race)
    if date_cat == "specific":
        score += 1
    else:
        flags.append(f"date_{date_cat}")

    # Boilerplate penalty (-1)
    bp = detect_boilerplate(race)
    if bp >= 2:
        score -= 1
        flags.append(f"boilerplate({bp})")

    return score, flags


def triage_all():
    """Score all profiles and return sorted results."""
    dump_slugs, brief_slugs = get_research_slugs()
    results = []

    for path in sorted(RACE_DATA.glob("*.json")):
        race = load_profile(path)
        slug = path.stem
        rating = race.get("gravel_god_rating", {})
        tier = rating.get("tier", rating.get("display_tier", 4))
        overall = rating.get("overall_score", 0)
        prestige = rating.get("prestige", 0)

        enrichment_score, flags = score_profile(race, slug, dump_slugs, brief_slugs)
        date_cat, date_str = classify_date(race)

        results.append({
            "slug": slug,
            "name": race.get("name", slug),
            "tier": tier,
            "overall_score": overall,
            "prestige": prestige,
            "enrichment_score": enrichment_score,
            "date_category": date_cat,
            "date_value": date_str,
            "has_dump": slug in dump_slugs,
            "has_brief": slug in brief_slugs,
            "flags": flags,
            "file_size_kb": round(path.stat().st_size / 1024, 1),
        })

    return results


def enrichment_priority(result):
    """Priority score: high-tier + low-enrichment = high priority."""
    tier_weight = {1: 40, 2: 30, 3: 15, 4: 5}
    prestige_weight = result["prestige"] * 3
    inverse_enrichment = (10 - result["enrichment_score"]) * 5
    return tier_weight.get(result["tier"], 5) + prestige_weight + inverse_enrichment


def print_report(results):
    """Print full triage report."""
    from collections import Counter

    print("\n" + "=" * 70)
    print("PROFILE TRIAGE REPORT")
    print("=" * 70)

    print(f"\nTotal profiles: {len(results)}")

    # Enrichment score distribution
    edist = Counter(r["enrichment_score"] for r in results)
    print("\nEnrichment Score Distribution:")
    for s in sorted(edist.keys()):
        bar = "#" * edist[s]
        print(f"  Score {s:2d}: {edist[s]:3d} {bar}")

    # Date distribution
    ddist = Counter(r["date_category"] for r in results)
    print("\nDate Specificity:")
    for cat in ["specific", "partial", "generic", "tbd", "missing"]:
        if cat in ddist:
            print(f"  {cat:10s}: {ddist[cat]:3d}")

    # Tier breakdown by enrichment
    print("\nEnrichment by Tier:")
    for tier in [1, 2, 3, 4]:
        tier_results = [r for r in results if r["tier"] == tier]
        if not tier_results:
            continue
        avg = sum(r["enrichment_score"] for r in tier_results) / len(tier_results)
        rich = sum(1 for r in tier_results if r["enrichment_score"] >= 4)
        thin = sum(1 for r in tier_results if r["enrichment_score"] <= 1)
        print(f"  T{tier}: {len(tier_results):3d} profiles, avg enrichment {avg:.1f}, {rich} rich, {thin} thin")

    # Top enrichment candidates
    ranked = sorted(results, key=enrichment_priority, reverse=True)
    print("\nTop 20 Enrichment Priorities (high tier + low content):")
    for r in ranked[:20]:
        flag_str = ", ".join(r["flags"][:3]) if r["flags"] else "ok"
        print(f"  T{r['tier']} [{r['enrichment_score']}/10] {r['name']:40s} p={r['prestige']} | {flag_str}")


def print_dates(results):
    """Print date gap report."""
    print("\n" + "=" * 70)
    print("DATE GAPS REPORT")
    print("=" * 70)

    tbd = [r for r in results if r["date_category"] == "tbd"]
    generic = [r for r in results if r["date_category"] == "generic"]
    missing = [r for r in results if r["date_category"] == "missing"]

    print(f"\nTBD dates: {len(tbd)}")
    print(f"Generic dates: {len(generic)}")
    print(f"Missing dates: {len(missing)}")

    print(f"\nTBD dates — Tier 1-2 (fix first):")
    for r in sorted(tbd, key=lambda x: x["tier"]):
        if r["tier"] <= 2:
            print(f"  T{r['tier']} {r['name']:40s} {r['date_value']}")

    print(f"\nTBD dates — Tier 3 ({len([r for r in tbd if r['tier'] == 3])}):")
    for r in sorted(tbd, key=lambda x: x["prestige"], reverse=True):
        if r["tier"] == 3:
            print(f"  T{r['tier']} p={r['prestige']} {r['name']:40s} {r['date_value']}")


def print_thin(results):
    """Print thin profile report."""
    print("\n" + "=" * 70)
    print("THIN PROFILES (enrichment score 0-1)")
    print("=" * 70)

    thin = [r for r in results if r["enrichment_score"] <= 1]
    thin.sort(key=enrichment_priority, reverse=True)

    print(f"\nTotal thin: {len(thin)}")
    print(f"  With research dump:    {sum(1 for r in thin if r['has_dump'])}")
    print(f"  Without research dump: {sum(1 for r in thin if not r['has_dump'])}")

    print(f"\nThin profiles with research dumps (can enrich from existing data):")
    enrichable = [r for r in thin if r["has_dump"]]
    for r in enrichable[:30]:
        print(f"  T{r['tier']} {r['name']:40s} flags: {', '.join(r['flags'][:3])}")

    print(f"\nThin profiles WITHOUT research dumps — Tier 1-2 (need research first):")
    for r in thin:
        if not r["has_dump"] and r["tier"] <= 2:
            print(f"  T{r['tier']} {r['name']:40s} {r['file_size_kb']:.0f}KB")


def export_csv(results, outpath):
    """Export results to CSV."""
    with open(outpath, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["slug", "name", "tier", "overall_score", "prestige",
                     "enrichment_score", "priority", "date_category",
                     "has_dump", "has_brief", "flags", "file_size_kb"])
        for r in sorted(results, key=enrichment_priority, reverse=True):
            w.writerow([
                r["slug"], r["name"], r["tier"], r["overall_score"],
                r["prestige"], r["enrichment_score"], enrichment_priority(r),
                r["date_category"], r["has_dump"], r["has_brief"],
                "|".join(r["flags"]), r["file_size_kb"],
            ])
    print(f"Exported {len(results)} profiles to {outpath}")


def print_enrich_queue(results, n):
    """Print top N enrichment candidates with actionable info."""
    ranked = sorted(results, key=enrichment_priority, reverse=True)

    # Split into two queues: has research dump (can enrich now) vs needs research first
    can_enrich = [r for r in ranked if r["has_dump"] and r["enrichment_score"] <= 2]
    needs_research = [r for r in ranked if not r["has_dump"] and r["enrichment_score"] <= 2]

    print("\n" + "=" * 70)
    print(f"ENRICHMENT QUEUE (top {n})")
    print("=" * 70)

    print(f"\n--- CAN ENRICH NOW (have research dumps) — {len(can_enrich)} total ---\n")
    for r in can_enrich[:n]:
        print(f"  T{r['tier']} [{r['enrichment_score']}/10] {r['slug']}")

    print(f"\n--- NEED RESEARCH FIRST (no dump) — {len(needs_research)} total ---\n")
    for r in needs_research[:n]:
        print(f"  T{r['tier']} [{r['enrichment_score']}/10] {r['slug']}")


def main():
    parser = argparse.ArgumentParser(description="Profile triage and enrichment priority")
    parser.add_argument("--dates", action="store_true", help="Date gaps report only")
    parser.add_argument("--thin", action="store_true", help="Thin profiles only")
    parser.add_argument("--csv", type=str, metavar="FILE", help="Export to CSV")
    parser.add_argument("--enrich-queue", type=int, metavar="N", help="Top N enrichment candidates")
    args = parser.parse_args()

    results = triage_all()

    if args.dates:
        print_dates(results)
    elif args.thin:
        print_thin(results)
    elif args.csv:
        export_csv(results, args.csv)
    elif args.enrich_queue:
        print_enrich_queue(results, args.enrich_queue)
    else:
        print_report(results)


if __name__ == "__main__":
    main()
