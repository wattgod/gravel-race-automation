#!/usr/bin/env python3
"""
scrape_official_sites.py — Scrape official race websites and extract structured data.

Uses Scrapling for tiered fetching (fast HTTP → Cloudflare bypass) and Claude Sonnet
for structured extraction. Cached HTML avoids re-fetching; re-runs are free.

Usage:
  python scripts/scrape_official_sites.py --dry-run              # Preview targets
  python scripts/scrape_official_sites.py --tier 1 --tier 2      # T1+T2 only
  python scripts/scrape_official_sites.py --slug unbound-200      # Single race
  python scripts/scrape_official_sites.py --stale-only            # Only stale-dated races
  python scripts/scrape_official_sites.py --no-claude             # Scrape only, skip extraction
  python scripts/scrape_official_sites.py --force                 # Ignore cache, re-scrape
  python scripts/scrape_official_sites.py --delay 5.0             # Rate limit (default: 3.0s)

Output: data/scrape-extracts/{slug}.json per race.

Requires: scrapling[fetchers], ANTHROPIC_API_KEY (unless --no-claude)
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Allow running from project root or scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scrape_utils import (
    fetch_url,
    get_cached,
    set_cached,
    extract_race_facts_via_claude,
    load_official_sites,
    save_extract,
    load_extract,
    RACE_DATA_DIR,
)


def _load_existing_vitals(slug: str) -> dict:
    """Load existing vitals from race JSON for comparison in extraction prompt."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        race = data.get("race", data)
        vitals = race.get("vitals", {})
        return {
            "distance_mi": vitals.get("distance_mi"),
            "elevation_ft": vitals.get("elevation_ft"),
            "date_specific": vitals.get("date_specific"),
            "location": vitals.get("location"),
            "field_size": vitals.get("field_size"),
            "start_time": vitals.get("start_time"),
        }
    except (json.JSONDecodeError, OSError):
        return {}


def scrape_race(slug: str, url: str, name: str, *,
                force: bool = False, no_claude: bool = False,
                verbose: bool = False) -> dict:
    """Scrape a single race's official site and optionally extract data.

    Returns dict with keys: slug, url, status, fetcher, extracted, error.
    """
    result = {"slug": slug, "url": url, "status": None, "fetcher": None,
              "extracted": None, "error": None}

    # Check cache first
    if not force:
        cached = get_cached(url)
        if cached and cached.get("html"):
            if verbose:
                print(f"  CACHE HIT ({cached['fetcher']})")
            result["status"] = cached["status"]
            result["fetcher"] = f"cached:{cached['fetcher']}"
            html = cached["html"]
        elif cached and not cached.get("html"):
            # Previously failed fetch — skip unless forced
            if verbose:
                print(f"  CACHE HIT (previous failure: {cached['fetcher']})")
            result["status"] = cached["status"]
            result["fetcher"] = f"cached:{cached['fetcher']}"
            result["error"] = "previous_failure"
            return result
        else:
            cached = None
    else:
        cached = None

    # Fetch if not cached
    if not cached:
        if verbose:
            print(f"  FETCHING {url}")
        html, status, fetcher = fetch_url(url)
        result["status"] = status
        result["fetcher"] = fetcher

        # Cache the result (even failures, to avoid re-trying)
        set_cached(url, html, status, fetcher)

        if not html:
            result["error"] = fetcher
            return result
    else:
        html = cached["html"]

    if verbose:
        print(f"  HTML: {len(html)} chars, status={result['status']}")

    # Extract structured data via Claude
    if not no_claude:
        existing = _load_existing_vitals(slug)
        if verbose:
            print(f"  EXTRACTING via Claude...")
        extracted = extract_race_facts_via_claude(html, name, existing)
        result["extracted"] = extracted

        if extracted and "error" not in extracted:
            save_extract(slug, extracted)
            if verbose:
                print(f"  SAVED extract: {json.dumps(extracted, indent=2)[:200]}")
        elif verbose:
            print(f"  EXTRACTION FAILED: {extracted.get('error', 'unknown')}")

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Scrape official race websites and extract structured data"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview targets without scraping")
    parser.add_argument("--tier", type=int, action="append", dest="tiers",
                        help="Only process races of this tier (repeatable)")
    parser.add_argument("--slug", help="Process single race by slug")
    parser.add_argument("--stale-only", action="store_true",
                        help="Only process races with stale (pre-2026) dates")
    parser.add_argument("--no-claude", action="store_true",
                        help="Scrape HTML only, skip Claude extraction")
    parser.add_argument("--force", action="store_true",
                        help="Ignore cache, re-scrape all")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed progress")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Delay between races in seconds (default: 3.0)")
    args = parser.parse_args()

    tier_filters = set(args.tiers) if args.tiers else None
    sites = load_official_sites(
        tier_filters=tier_filters,
        slug_filter=args.slug,
        stale_only=args.stale_only,
    )

    if not sites:
        print("No races found matching filters.")
        return 0

    stale_label = " (stale dates only)" if args.stale_only else ""
    tier_label = f" (tiers {sorted(tier_filters)})" if tier_filters else ""
    print(f"Found {len(sites)} races with official URLs{tier_label}{stale_label}")

    if args.dry_run:
        print()
        for slug, info in sorted(sites.items()):
            existing = load_extract(slug)
            cached = get_cached(info["url"])
            cache_status = "cached" if cached and cached.get("html") else "not cached"
            extract_status = "extracted" if existing else "no extract"
            print(f"  T{info['tier']} {slug}: {info['url'][:60]} [{cache_status}, {extract_status}]")
        print(f"\n(Dry run — no fetching or extraction performed)")
        return 0

    print()
    stats = {"success": 0, "cached": 0, "failed": 0, "extracted": 0}

    for i, (slug, info) in enumerate(sorted(sites.items())):
        print(f"[{i+1}/{len(sites)}] T{info['tier']} {slug}")

        result = scrape_race(
            slug, info["url"], info["name"],
            force=args.force, no_claude=args.no_claude,
            verbose=args.verbose,
        )

        if result["error"]:
            stats["failed"] += 1
            print(f"  FAILED: {result['error']}")
        elif result["fetcher"] and result["fetcher"].startswith("cached:"):
            stats["cached"] += 1
            print(f"  OK (cached, status={result['status']})")
        else:
            stats["success"] += 1
            print(f"  OK ({result['fetcher']}, status={result['status']})")

        if result["extracted"] and "error" not in result.get("extracted", {}):
            stats["extracted"] += 1

        # Rate limiting between races (skip for cached)
        if i < len(sites) - 1 and not (result["fetcher"] or "").startswith("cached:"):
            time.sleep(args.delay)

    print()
    print(f"Results:")
    print(f"  Fetched:   {stats['success']}")
    print(f"  Cached:    {stats['cached']}")
    print(f"  Failed:    {stats['failed']}")
    print(f"  Extracted: {stats['extracted']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
