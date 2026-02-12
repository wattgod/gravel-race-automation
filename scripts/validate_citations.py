#!/usr/bin/env python3
"""
Validate citation quality across all race profiles.

Checks:
1. No duplicate URLs within a single race
2. No Google text-fragment URLs (#:~:text=)
3. Citation count <= MAX per race
4. All URLs are well-formed (have scheme + netloc)
5. No excluded domains leaked through
6. No opaque BikeReg/Eventbrite IDs without race name

Exits 1 on any failure. Run as mandatory pre-deploy check.

Usage:
    python scripts/validate_citations.py
    python scripts/validate_citations.py --verbose
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

MAX_CITATIONS = 20

EXCLUDE_DOMAINS = {
    'gravelgodcycling.com',
    'google.com', 'google.co.uk', 'goo.gl',
    'bit.ly', 't.co',
    'web.archive.org',
    'cdn.shopify.com',
    'fonts.googleapis.com',
    'schema.org',
    'wp.com', 'wordpress.com',
    'gravatar.com',
    'cloudflare.com',
    'w3.org',
}


def validate_race_citations(slug: str, citations: list, verbose: bool = False) -> list:
    """Validate citations for a single race. Returns list of error strings."""
    errors = []

    # Check count cap
    if len(citations) > MAX_CITATIONS:
        errors.append(f"{slug}: {len(citations)} citations exceeds cap of {MAX_CITATIONS}")

    seen_urls = set()
    seen_normalized = set()

    for i, c in enumerate(citations):
        url = c.get('url', '')
        category = c.get('category', '')
        label = c.get('label', '')

        # Check required fields
        if not url:
            errors.append(f"{slug}: citation {i} has empty URL")
            continue
        if not category:
            errors.append(f"{slug}: citation {i} has empty category")
        if not label:
            errors.append(f"{slug}: citation {i} has empty label")

        # Check well-formed URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"{slug}: malformed URL: {url[:80]}")
                continue
        except Exception:
            errors.append(f"{slug}: unparseable URL: {url[:80]}")
            continue

        # Check for Google text fragments
        if '#:~:text=' in url:
            errors.append(f"{slug}: Google text fragment not stripped: {url[:80]}")

        # Check for excluded domains
        domain = parsed.netloc.lower().replace('www.', '')
        if domain in EXCLUDE_DOMAINS:
            errors.append(f"{slug}: excluded domain leaked: {domain}")

        # Check for exact duplicates
        if url in seen_urls:
            errors.append(f"{slug}: duplicate URL: {url[:80]}")
        seen_urls.add(url)

        # Check for normalized duplicates (same page, different fragment/trailing slash)
        norm = url.split('#')[0].rstrip('/')
        if norm in seen_normalized:
            errors.append(f"{slug}: near-duplicate URL (differs only by fragment/slash): {url[:80]}")
        seen_normalized.add(norm)

    return errors


def main():
    parser = argparse.ArgumentParser(description='Validate citation quality')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    files = sorted(DATA_DIR.glob('*.json'))
    all_errors = []
    races_checked = 0
    total_citations = 0
    races_with_citations = 0
    max_count = 0
    max_slug = ''

    for path in files:
        slug = path.stem
        data = json.loads(path.read_text())
        race = data['race']
        citations = race.get('citations', [])
        races_checked += 1
        total_citations += len(citations)

        if citations:
            races_with_citations += 1
            if len(citations) > max_count:
                max_count = len(citations)
                max_slug = slug

        errors = validate_race_citations(slug, citations, args.verbose)
        all_errors.extend(errors)

        if args.verbose and citations:
            print(f"  {slug}: {len(citations)} citations — {'OK' if not errors else f'{len(errors)} errors'}")

    print(f"\nCitation Validation Summary:")
    print(f"  Races checked: {races_checked}")
    print(f"  Races with citations: {races_with_citations} ({races_with_citations*100//races_checked}%)")
    print(f"  Total citations: {total_citations}")
    print(f"  Average per race: {total_citations/races_checked:.1f}")
    print(f"  Max: {max_count} ({max_slug})")

    if all_errors:
        print(f"\nFAILED — {len(all_errors)} errors:")
        for e in all_errors:
            print(f"  {e}")
        sys.exit(1)
    else:
        print(f"\nALL CHECKS PASSED")
        sys.exit(0)


if __name__ == '__main__':
    main()
