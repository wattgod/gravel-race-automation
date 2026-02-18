#!/usr/bin/env python3
"""
Add community source URLs to race profile citations.

Scans community dumps for source URLs and merges them into each race's
citations array. Deduplicates by URL — safe to run multiple times.

Usage:
    python scripts/add_community_citations.py              # All races with community dumps
    python scripts/add_community_citations.py --slugs mid-south salty-lizard
    python scripts/add_community_citations.py --dry-run    # Preview without writing
"""

import argparse
import json
import sys
from pathlib import Path

RACE_DATA = Path(__file__).parent.parent / "race-data"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"

sys.path.insert(0, str(Path(__file__).parent))
from community_parser import extract_source_urls


def add_citations_for_slug(slug, dry_run=False):
    """Add community citations to a single race profile.

    Returns (added_count, message).
    """
    profile_path = RACE_DATA / f"{slug}.json"
    community_path = RESEARCH_DUMPS / f"{slug}-community.md"

    if not profile_path.exists():
        return 0, f"No profile: {slug}"
    if not community_path.exists():
        return 0, f"No community dump: {slug}"

    community_text = community_path.read_text()
    new_citations = extract_source_urls(community_text)

    if not new_citations:
        return 0, f"No URLs found in community dump: {slug}"

    data = json.loads(profile_path.read_text())
    race = data.get("race", data)

    existing = race.get("citations", [])
    existing_urls = {c.get("url") for c in existing}

    added = []
    for cite in new_citations:
        if cite["url"] not in existing_urls:
            added.append(cite)
            existing_urls.add(cite["url"])

    if not added:
        return 0, f"All {len(new_citations)} URLs already cited: {slug}"

    race["citations"] = existing + added

    if not dry_run:
        if "race" in data:
            data["race"] = race
        profile_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return len(added), f"+{len(added)} citations (total {len(existing) + len(added)}): {slug}"


def main():
    parser = argparse.ArgumentParser(description="Add community citations to race profiles")
    parser.add_argument("--slugs", nargs="+", help="Specific slugs to process")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    if args.slugs:
        slugs = args.slugs
    else:
        # All races with community dumps
        slugs = sorted(
            p.stem.replace("-community", "")
            for p in RESEARCH_DUMPS.glob("*-community.md")
        )

    total_added = 0
    processed = 0

    for slug in slugs:
        count, msg = add_citations_for_slug(slug, dry_run=args.dry_run)
        if count > 0:
            print(f"  {msg}")
            total_added += count
            processed += 1
        elif "already cited" not in msg and "No URLs" not in msg:
            print(f"  {msg}")

    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"\n{prefix}{processed} profiles updated, {total_added} citations added ({len(slugs)} checked)")


if __name__ == "__main__":
    main()
