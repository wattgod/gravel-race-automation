#!/usr/bin/env python3
"""
Automated audit of community_parser.py across all community dumps.

Runs the parser against every community dump and flags:
- Suspicious rider names (likely false positives)
- Dumps with 0 riders extracted (missing real riders?)
- Terrain features that look like section headers
- Statistics on extraction coverage

Run: python3 scripts/audit_community_parser.py
     python3 scripts/audit_community_parser.py --verbose
     python3 scripts/audit_community_parser.py --slug salty-lizard
"""

import argparse
import re
import sys
from pathlib import Path

# Add parent dir for import
sys.path.insert(0, str(Path(__file__).parent))
from community_parser import (
    extract_riders,
    extract_terrain_features,
    extract_weather,
    extract_numbers,
    parse_sections,
    build_fact_sheet,
)

RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"

# Patterns that suggest a rider name is actually a topic label
SUSPICIOUS_PATTERNS = [
    re.compile(r'\b(?:Strategy|Dynamics|Formation|Decision|Positioning)\b'),
    re.compile(r'\b(?:Delays|Crossings|Issues|Factors|Conditions)\b'),
    re.compile(r'\b(?:Details|Notes|Recommendations|Challenges|Options)\b'),
    re.compile(r'\b(?:Setup|Prep|Configuration|Selection|Assessment)\b'),
    re.compile(r'\b(?:Performance|Classification|Description|Character)\b'),
    re.compile(r'\b(?:Sections?|Points?|Profile|Overview|Analysis)\b'),
    # Names that are too short to be real (single character only)
    re.compile(r'^[A-Za-z]$'),
]

# Terrain features that look like section headers
SUSPICIOUS_TERRAIN = [
    re.compile(r'\b(?:Course|Surface|Overall|Opening|Final|Specific)\b.*\b(?:Description|Character|Conditions|Descent|Approach|Roads)\b'),
    re.compile(r'\b(?:Double|Single)\s+Track\b'),
    re.compile(r'\b(?:Elevation|Difficulty)\s+(?:Profile|Classification)\b'),
]


def audit_slug(slug, verbose=False):
    """Audit a single community dump. Returns dict of findings."""
    community_path = RESEARCH_DUMPS / f"{slug}-community.md"
    if not community_path.exists():
        return None

    text = community_path.read_text()
    sections = parse_sections(text)
    riders = extract_riders(text)

    # Count raw ** [LEVEL] ** matches for comparison
    raw_matches = re.findall(r'\*\*(.+?)\s*\[([^\]]+)\]', text)
    raw_count = len(raw_matches)

    # Check for suspicious rider names
    suspicious_riders = []
    for name in riders:
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.search(name):
                suspicious_riders.append(name)
                break

    # Check terrain features
    terrain_text = (
        sections.get("Terrain Details (Rider Perspective)", "") +
        sections.get("Terrain Details", "")
    )
    terrain = extract_terrain_features(terrain_text)
    suspicious_terrain = []
    for feature in terrain:
        for pattern in SUSPICIOUS_TERRAIN:
            if pattern.search(feature):
                suspicious_terrain.append(feature)
                break

    # Weather and numbers coverage
    weather = extract_weather(sections)
    numbers = extract_numbers(text)

    result = {
        "slug": slug,
        "file_kb": community_path.stat().st_size / 1024,
        "section_count": len([s for s in sections if s != "_header"]),
        "raw_attribution_count": raw_count,
        "rider_count": len(riders),
        "riders": list(riders.keys()),
        "suspicious_riders": suspicious_riders,
        "terrain_count": len(terrain),
        "suspicious_terrain": suspicious_terrain,
        "has_weather": bool(weather),
        "has_elevation": "elevation_mentions" in numbers,
        "has_field_size": "field_sizes" in numbers,
        "has_power": "power_data" in numbers,
    }

    if verbose:
        print(f"\n{'='*60}")
        print(f"  {slug.upper()} ({result['file_kb']:.1f}KB)")
        print(f"{'='*60}")
        print(f"  Sections: {result['section_count']}")
        print(f"  Raw attributions: {result['raw_attribution_count']}")
        print(f"  Riders extracted: {result['rider_count']}")
        if riders:
            for name, level in riders.items():
                flag = " [SUSPICIOUS]" if name in suspicious_riders else ""
                print(f"    - {name} ({level}){flag}")
        print(f"  Terrain features: {result['terrain_count']}")
        if suspicious_terrain:
            for t in suspicious_terrain:
                print(f"    [SUSPICIOUS] {t}")
        print(f"  Weather: {'Yes' if result['has_weather'] else 'No'}")
        print(f"  Elevation data: {'Yes' if result['has_elevation'] else 'No'}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Audit community parser across all dumps")
    parser.add_argument("--slug", help="Audit a specific slug")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed per-slug output")
    parser.add_argument("--suspicious-only", action="store_true", help="Only show slugs with issues")
    args = parser.parse_args()

    if args.slug:
        result = audit_slug(args.slug, verbose=True)
        if not result:
            print(f"No community dump for {args.slug}")
        return

    # Audit all dumps
    community_files = sorted(RESEARCH_DUMPS.glob("*-community.md"))
    print(f"Auditing {len(community_files)} community dumps...\n")

    results = []
    for path in community_files:
        slug = path.stem.replace("-community", "")
        result = audit_slug(slug, verbose=args.verbose)
        if result:
            results.append(result)

    # Summary statistics
    total = len(results)
    zero_riders = [r for r in results if r["rider_count"] == 0]
    has_suspicious = [r for r in results if r["suspicious_riders"]]
    has_suspicious_terrain = [r for r in results if r["suspicious_terrain"]]
    total_riders = sum(r["rider_count"] for r in results)
    total_suspicious = sum(len(r["suspicious_riders"]) for r in results)
    total_raw = sum(r["raw_attribution_count"] for r in results)

    print(f"\n{'='*60}")
    print("  AUDIT SUMMARY")
    print(f"{'='*60}")
    print(f"  Community dumps audited: {total}")
    print(f"  Total raw ** [LEVEL] ** matches: {total_raw}")
    print(f"  Total riders extracted: {total_riders}")
    print(f"  Extraction rate: {total_riders}/{total_raw} ({100*total_riders/max(total_raw,1):.1f}%)")
    print()
    print(f"  Dumps with 0 riders: {len(zero_riders)}")
    if zero_riders:
        for r in zero_riders[:10]:
            print(f"    - {r['slug']} ({r['file_kb']:.1f}KB, {r['raw_attribution_count']} raw matches)")
    print()
    print(f"  Dumps with suspicious riders: {len(has_suspicious)} ({total_suspicious} total suspicious)")
    if has_suspicious:
        if args.suspicious_only or not args.verbose:
            for r in has_suspicious:
                print(f"    - {r['slug']}: {r['suspicious_riders']}")
    print()
    print(f"  Dumps with suspicious terrain: {len(has_suspicious_terrain)}")
    if has_suspicious_terrain and not args.verbose:
        for r in has_suspicious_terrain[:10]:
            print(f"    - {r['slug']}: {r['suspicious_terrain']}")
    print()

    # Coverage stats
    has_weather = sum(1 for r in results if r["has_weather"])
    has_elevation = sum(1 for r in results if r["has_elevation"])
    has_field = sum(1 for r in results if r["has_field_size"])
    has_power = sum(1 for r in results if r["has_power"])
    print(f"  Coverage:")
    print(f"    Weather data: {has_weather}/{total} ({100*has_weather/max(total,1):.0f}%)")
    print(f"    Elevation data: {has_elevation}/{total} ({100*has_elevation/max(total,1):.0f}%)")
    print(f"    Field size data: {has_field}/{total} ({100*has_field/max(total,1):.0f}%)")
    print(f"    Power data: {has_power}/{total} ({100*has_power/max(total,1):.0f}%)")

    # Exit code: non-zero if suspicious riders found
    if total_suspicious > 0:
        print(f"\n  ** {total_suspicious} SUSPICIOUS RIDER NAMES — review and fix **")
        sys.exit(1)
    else:
        print(f"\n  All clean.")
        sys.exit(0)


if __name__ == "__main__":
    main()
