#!/usr/bin/env python3
"""
One-shot cleanup: remove generic homepage and suspicious Reddit citations.

Scans all race profiles and removes citations that are:
1. Generic homepage URLs (no meaningful path)
2. Reddit user profile URLs (/user/ or /u/)
3. Reddit share links (/r/.../s/...)

Reports what was removed per profile. Safe to run multiple times.

Usage:
    python scripts/clean_generic_citations.py              # Execute cleanup
    python scripts/clean_generic_citations.py --dry-run    # Preview only
    python scripts/clean_generic_citations.py --slug foo   # Single race
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"


def is_generic_homepage(url: str) -> bool:
    """Return True if URL is just a domain homepage with no specific path."""
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip('/')
        if not path:
            return True
        if re.match(r'^/[a-z]{2}$', path):
            return True
        return False
    except Exception:
        return False


def is_suspicious_reddit(url: str) -> bool:
    """Return True if Reddit URL is a user profile or share link."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ''
        if 'reddit.com' not in hostname:
            return False
        path = parsed.path.rstrip('/')
        if not path:
            return False
        if path.startswith('/user/') or path.startswith('/u/'):
            return True
        if re.search(r'/r/[a-zA-Z0-9_]+/s/[a-zA-Z0-9]+', path):
            return True
        return False
    except Exception:
        return False


MAX_CITATIONS = 20

# Priority for cap enforcement — keep higher-priority categories first
CATEGORY_PRIORITY = {
    'official': 0, 'route': 1, 'media': 2, 'community': 3,
    'video': 4, 'reference': 5, 'registration': 6,
    'tracking': 7, 'social': 8, 'activity': 9, 'other': 10,
}


def clean_profile(filepath: Path, dry_run: bool = False) -> dict:
    """Clean citations for a single profile. Returns removal report."""
    data = json.loads(filepath.read_text())
    race = data['race']
    slug = filepath.stem
    citations = race.get('citations', [])

    if not citations:
        return {'slug': slug, 'removed': [], 'remaining': 0}

    removed = []
    kept = []

    for cit in citations:
        url = cit.get('url', '')
        reason = None

        if is_generic_homepage(url):
            reason = 'generic_homepage'
        elif is_suspicious_reddit(url):
            reason = 'suspicious_reddit'

        if reason:
            removed.append({'url': url, 'reason': reason, 'label': cit.get('label', '')})
        else:
            kept.append(cit)

    # Deduplicate near-duplicates (differ only by trailing slash or fragment)
    seen_normalized = set()
    deduped = []
    for cit in kept:
        norm = cit.get('url', '').split('#')[0].rstrip('/')
        if norm in seen_normalized:
            removed.append({'url': cit['url'], 'reason': 'near_duplicate', 'label': cit.get('label', '')})
        else:
            seen_normalized.add(norm)
            deduped.append(cit)
    kept = deduped

    # Enforce cap — trim lowest-priority citations
    if len(kept) > MAX_CITATIONS:
        kept.sort(key=lambda c: CATEGORY_PRIORITY.get(c.get('category', 'other'), 99))
        over = kept[MAX_CITATIONS:]
        kept = kept[:MAX_CITATIONS]
        for cit in over:
            removed.append({'url': cit['url'], 'reason': 'cap_exceeded', 'label': cit.get('label', '')})

    changed = len(removed) > 0
    if changed and not dry_run:
        race['citations'] = kept
        data['race'] = race
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')

    return {
        'slug': slug,
        'removed': removed,
        'remaining': len(kept),
    }


def main():
    parser = argparse.ArgumentParser(description='Remove generic/suspicious citations')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    parser.add_argument('--slug', help='Process only this race slug')
    args = parser.parse_args()

    files = sorted(DATA_DIR.glob('*.json'))
    if args.slug:
        files = [DATA_DIR / f"{args.slug}.json"]
        if not files[0].exists():
            print(f"ERROR: {files[0]} not found")
            sys.exit(1)

    total_removed = 0
    profiles_affected = 0
    reason_counts = {'generic_homepage': 0, 'suspicious_reddit': 0}

    for filepath in files:
        result = clean_profile(filepath, dry_run=args.dry_run)

        if result['removed']:
            profiles_affected += 1
            total_removed += len(result['removed'])

            print(f"\n  {result['slug']} — removed {len(result['removed'])}, {result['remaining']} remaining:")
            for r in result['removed']:
                reason_counts[r['reason']] = reason_counts.get(r['reason'], 0) + 1
                print(f"    [{r['reason']}] {r['url'][:80]}")

    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"\n{prefix}Summary:")
    print(f"  Profiles scanned:    {len(files)}")
    print(f"  Profiles affected:   {profiles_affected}")
    print(f"  Citations removed:   {total_removed}")
    for reason, count in sorted(reason_counts.items()):
        print(f"    {reason}: {count}")

    if args.dry_run and total_removed > 0:
        print(f"\n  Run without --dry-run to apply changes.")


if __name__ == '__main__':
    main()
