#!/usr/bin/env python3
"""
Overnight enrichment pipeline — re-research all profiles with 3-engine search
(DDG + Google + Perplexity), then re-enrich profiles where new research added
significant new material.

Usage:
    python scripts/overnight_enrichment.py
    python scripts/overnight_enrichment.py --research-only   # skip enrichment
    python scripts/overnight_enrichment.py --enrich-only     # skip research
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = PROJECT_ROOT / "race-data"
RESEARCH_DUMPS = PROJECT_ROOT / "research-dumps"
SCRIPTS = PROJECT_ROOT / "scripts"
ENV_FILE = PROJECT_ROOT / ".env"


def load_dotenv():
    """Load .env file into os.environ so subprocesses inherit API keys."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()

# Slugs to skip entirely
SKIP_SLUGS = {"dirty-french"}  # Not a real race

# Threshold: only re-enrich if community dump grew by this fraction
GROWTH_THRESHOLD = 0.30  # 30%


def get_all_slugs():
    """Get all race slugs that have JSON profiles."""
    return sorted(p.stem for p in RACE_DATA.glob("*.json") if p.stem not in SKIP_SLUGS)


def get_dump_sizes(slugs):
    """Record current community dump sizes for comparison."""
    sizes = {}
    for slug in slugs:
        dump = RESEARCH_DUMPS / f"{slug}-community.md"
        if dump.exists():
            sizes[slug] = dump.stat().st_size
        else:
            sizes[slug] = 0
    return sizes


def run_research(slugs, batch_size=50, delay=2):
    """Re-research slugs in batches with 3-engine search."""
    total = len(slugs)
    for i in range(0, total, batch_size):
        batch = slugs[i:i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        print(f"\n{'='*60}")
        print(f"RESEARCH BATCH {batch_num}/{total_batches} ({len(batch)} races)")
        print(f"{'='*60}")

        cmd = [
            sys.executable, str(SCRIPTS / "batch_community_research.py"),
            "--slugs", *batch,
            "--force",
            "--delay", str(delay),
        ]
        result = subprocess.run(cmd, capture_output=False)
        if result.returncode != 0:
            print(f"WARNING: Research batch {batch_num} had errors")

        # Cool down between batches to avoid rate limits
        if i + batch_size < total:
            print("Cooling down 30s between batches...")
            time.sleep(30)


def run_enrichment(slugs, delay=3):
    """Re-enrich slugs with --force."""
    if not slugs:
        print("No slugs to enrich.")
        return

    print(f"\n{'='*60}")
    print(f"ENRICHING {len(slugs)} profiles")
    print(f"{'='*60}")

    cmd = [
        sys.executable, str(SCRIPTS / "batch_enrich.py"),
        "--force",
        "--slugs", *slugs,
        "--delay", str(delay),
    ]
    subprocess.run(cmd, capture_output=False)


def run_cleanup():
    """Run slop cleanup on any new kept-old fallbacks."""
    print(f"\n{'='*60}")
    print("SLOP CLEANUP")
    print(f"{'='*60}")
    cmd = [sys.executable, str(SCRIPTS / "cleanup_slop.py")]
    subprocess.run(cmd, capture_output=False)


def run_citations():
    """Add community citations to re-enriched profiles."""
    print(f"\n{'='*60}")
    print("ADDING CITATIONS")
    print(f"{'='*60}")
    cmd = [sys.executable, str(SCRIPTS / "add_community_citations.py")]
    subprocess.run(cmd, capture_output=False)


def run_tests():
    """Run the quality test suite."""
    print(f"\n{'='*60}")
    print("RUNNING QUALITY TESTS")
    print(f"{'='*60}")
    cmd = [sys.executable, "-m", "pytest",
           "tests/test_enrichment_quality.py",
           "tests/test_enrichment.py",
           "-v", "--tb=short"]
    result = subprocess.run(cmd, capture_output=False, cwd=str(PROJECT_ROOT))
    return result.returncode == 0


def fix_lowercase():
    """Fix any explanations starting with lowercase."""
    import re
    COMPONENTS = [
        'logistics', 'length', 'technicality', 'elevation', 'climate',
        'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
        'community', 'field_depth', 'value', 'expenses'
    ]
    fixed = 0
    for p in sorted(RACE_DATA.glob("*.json")):
        data = json.loads(p.read_text())
        race = data.get("race", data)
        bor = race.get("biased_opinion_ratings", {})
        changed = False
        for k in COMPONENTS:
            entry = bor.get(k)
            if not isinstance(entry, dict):
                continue
            exp = entry.get("explanation", "")
            if exp and exp[0].islower():
                entry["explanation"] = exp[0].upper() + exp[1:]
                changed = True
                fixed += 1
        if changed:
            if "race" in data:
                data["race"] = race
            p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    if fixed:
        print(f"Fixed {fixed} lowercase explanations")


def main():
    parser = argparse.ArgumentParser(description="Overnight enrichment pipeline")
    parser.add_argument("--research-only", action="store_true")
    parser.add_argument("--enrich-only", action="store_true")
    args = parser.parse_args()

    load_dotenv()
    start = time.time()
    all_slugs = get_all_slugs()
    print(f"Total profiles: {len(all_slugs)}")

    if not args.enrich_only:
        # Phase 1: Record current dump sizes
        before_sizes = get_dump_sizes(all_slugs)

        # Phase 2: Re-research ALL with 3 engines
        print(f"\nPhase 1: Re-researching {len(all_slugs)} profiles with DDG+Google+Perplexity")
        run_research(all_slugs, batch_size=40, delay=2)

        # Phase 3: Compare dump sizes, find enrichment candidates
        after_sizes = get_dump_sizes(all_slugs)
        grew = []
        for slug in all_slugs:
            old = before_sizes.get(slug, 0)
            new = after_sizes.get(slug, 0)
            if old == 0 and new > 0:
                grew.append(slug)  # Brand new dump
            elif old > 0 and new > old * (1 + GROWTH_THRESHOLD):
                grew.append(slug)  # Grew significantly

        print(f"\nPhase 1 complete: {len(grew)} profiles have significantly richer research")
        print(f"  (threshold: >{GROWTH_THRESHOLD*100:.0f}% dump growth)")

        if args.research_only:
            elapsed = time.time() - start
            print(f"\nResearch-only complete in {elapsed/60:.0f} minutes")
            return

        enrich_slugs = grew
    else:
        # Enrich all that have community dumps
        enrich_slugs = [s for s in all_slugs
                        if (RESEARCH_DUMPS / f"{s}-community.md").exists()]

    # Phase 4: Re-enrich candidates
    if enrich_slugs:
        print(f"\nPhase 2: Re-enriching {len(enrich_slugs)} profiles")
        run_enrichment(enrich_slugs, delay=3)
    else:
        print("\nNo profiles need re-enrichment (no significant research growth)")

    # Phase 5: Cleanup
    print(f"\nPhase 3: Post-enrichment cleanup")
    run_cleanup()
    fix_lowercase()
    run_citations()

    # Phase 6: Validate
    print(f"\nPhase 4: Validation")
    tests_pass = run_tests()

    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"OVERNIGHT PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"  Time: {elapsed/60:.0f} minutes ({elapsed/3600:.1f} hours)")
    print(f"  Researched: {len(all_slugs)} profiles")
    print(f"  Enriched: {len(enrich_slugs)} profiles")
    print(f"  Tests: {'ALL PASS' if tests_pass else 'SOME FAILURES'}")
    print(f"\nNext steps:")
    print(f"  python wordpress/generate_neo_brutalist.py --all")
    print(f"  python wordpress/generate_prep_kit.py --all")
    print(f"  # deploy with push_wordpress.py")


if __name__ == "__main__":
    main()
