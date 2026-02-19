#!/usr/bin/env python3
"""
Extract and categorize citations for all race profiles.

Sources:
1. Race JSON profiles — official_site (from vitals, logistics, organizer), ridewithgps_id
2. Research dumps (research-dumps/{slug}-raw.md and .bak.md) — extract URLs
3. Known source patterns (Reddit, YouTube, TrainerRoad, etc.)

Quality controls:
- Strips Google text-fragment URLs (#:~:text=)
- Deduplicates URLs that differ only by fragment
- Filters irrelevant URLs using race name/slug relevance scoring
- Caps citations at MAX_CITATIONS per race
- Checks multiple JSON locations for official website

Writes a `citations` list into each race JSON under race.citations.

Usage:
    python scripts/extract_citations.py
    python scripts/extract_citations.py --dry-run
    python scripts/extract_citations.py --slug unbound-200
"""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse


DUMP_DIR = Path(__file__).resolve().parent.parent / "research-dumps"
DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

# Hard cap on citations per race — anything beyond this is noise
MAX_CITATIONS = 20

# URL extraction regex — captures http/https URLs, stops at whitespace, ), ], or >
URL_RE = re.compile(r'https?://[^\s\)\]\>]+')

# Trailing punctuation to strip from URLs
TRAILING_PUNCT = re.compile(r'[.,;:!?\'"]+$')

# Source categorization rules: (domain pattern, category, label)
SOURCE_RULES = [
    (r'ridewithgps\.com', 'route', 'RideWithGPS'),
    (r'reddit\.com|redd\.it', 'community', 'Reddit'),
    (r'youtube\.com|youtu\.be', 'video', 'YouTube'),
    (r'instagram\.com', 'social', 'Instagram'),
    (r'facebook\.com|fb\.com', 'social', 'Facebook'),
    (r'strava\.com', 'activity', 'Strava'),
    (r'trainerroad\.com', 'community', 'TrainerRoad'),
    (r'ridinggravel\.com', 'community', 'Riding Gravel'),
    (r'gravelcyclist\.com', 'media', 'Gravel Cyclist'),
    (r'cxmagazine\.com', 'media', 'CX Magazine'),
    (r'velonews\.com', 'media', 'VeloNews'),
    (r'velo\.outsideonline\.com', 'media', 'Velo'),
    (r'cyclingtips\.com', 'media', 'CyclingTips'),
    (r'bikeradar\.com', 'media', 'BikeRadar'),
    (r'gearjunkie\.com', 'media', 'GearJunkie'),
    (r'cyclingweekly\.com', 'media', 'Cycling Weekly'),
    (r'outsideonline\.com', 'media', 'Outside'),
    (r'bikereg\.com', 'registration', 'BikeReg'),
    (r'eventbrite\.com', 'registration', 'Eventbrite'),
    (r'wikipedia\.org', 'reference', 'Wikipedia'),
    (r'trackleaders\.com', 'tracking', 'TrackLeaders'),
    (r'dotwatcher\.cc', 'tracking', 'DotWatcher'),
]

# Domains to exclude (not useful as citations)
EXCLUDE_DOMAINS = {
    'gravelgodcycling.com',
    'google.com', 'google.co.uk', 'goo.gl', 'google.ca',
    'bit.ly', 't.co', 'tinyurl.com',
    'web.archive.org',
    'cdn.shopify.com',
    'fonts.googleapis.com', 'fonts.gstatic.com',
    'schema.org',
    'wp.com', 'wordpress.com', 'wordpress.org',
    'gravatar.com',
    'cloudflare.com', 'cdnjs.cloudflare.com',
    'w3.org',
    'amazon.com', 'amzn.to',
    'twitter.com', 'x.com',
    'maps.google.com', 'maps.app.goo.gl',
    'play.google.com',
    'apps.apple.com',
    'creativecommons.org',
    'mailto',
}

# Domains that are always relevant to gravel racing (never filter these out)
ALWAYS_RELEVANT_DOMAINS = {
    'ridewithgps.com', 'strava.com',
    'ridinggravel.com', 'gravelcyclist.com', 'cxmagazine.com',
    'velonews.com', 'cyclingtips.com', 'bikeradar.com',
    'gearjunkie.com', 'cyclingweekly.com',
    'bikereg.com', 'eventbrite.com',
    'trackleaders.com', 'dotwatcher.cc',
    'trainerroad.com',
    'wikipedia.org',
}


def clean_url(url: str) -> str:
    """Clean extracted URL — strip trailing punctuation, fragments, artifacts."""
    url = TRAILING_PUNCT.sub('', url)
    # Strip trailing ) if unmatched
    if url.count(')') > url.count('('):
        url = url.rstrip(')')
    # Strip markdown artifacts
    url = url.rstrip('*_[]')
    # Strip Google text-fragment highlights (#:~:text=...)
    if '#:~:text=' in url:
        url = url.split('#:~:text=')[0]
    return url


def normalize_url(url: str) -> str:
    """Normalize URL for deduplication — strip fragment, trailing slash, lowercase."""
    try:
        parsed = urlparse(url)
        # Normalize path: strip trailing slash (root "/" becomes "")
        path = parsed.path.rstrip('/')
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            parsed.query,
            '',  # drop fragment
        ))
        return normalized
    except Exception:
        return url.lower()


def categorize_url(url: str) -> tuple:
    """Return (category, label) for a URL based on domain patterns."""
    try:
        domain = urlparse(url).netloc.lower()
    except Exception:
        return ('other', 'Web')

    for pattern, category, label in SOURCE_RULES:
        if re.search(pattern, domain):
            return (category, label)

    return ('other', domain.replace('www.', '').split('.')[0].title())


def is_excluded(url: str) -> bool:
    """Check if URL should be excluded from citations."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
    except Exception:
        return True

    if domain in EXCLUDE_DOMAINS:
        return True

    # Exclude common non-content paths
    path = parsed.path.lower()
    if any(p in path for p in ['/wp-admin', '/wp-login', '/feed/', '/xmlrpc',
                                '/cart', '/checkout', '/my-account',
                                '/.well-known', '/favicon']):
        return True

    return False


def is_relevant_to_race(url: str, slug: str, race_name: str) -> bool:
    """Check if a URL is plausibly relevant to this specific race.

    Returns True if the URL should be kept, False if it's likely noise
    from research dump search results about other races.

    Strategy: conservative. It's better to miss a marginal citation than to
    include one about a completely different race. We require either:
    - The full slug appears in the URL
    - The domain is a known cycling media/tool site
    - The domain itself is clearly the race's website
    - Multiple distinctive (5+ char) race name words appear in the URL
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower().replace('www.', '')
        path = parsed.path.lower()
    except Exception:
        return False

    url_lower = url.lower()

    # Always-relevant cycling media/tool domains — but for registration sites
    # with opaque IDs, require the race name in the URL path
    for d in ALWAYS_RELEVANT_DOMAINS:
        if d in domain:
            # BikeReg/Eventbrite with opaque numeric IDs are NOT automatically relevant
            if d in ('bikereg.com', 'eventbrite.com'):
                # Only relevant if the path contains race-identifying text
                slug_parts = slug.split('-')
                distinctive = [w for w in slug_parts if len(w) >= 5]
                if any(w in path for w in distinctive):
                    return True
                if slug in path:
                    return True
                # Opaque ID — skip
                return False
            return True

    # Full slug match in URL (e.g., "almanzo-100" in URL)
    if slug in url_lower:
        return True

    # Domain is clearly the race's website (e.g., almanzo.com for almanzo-100)
    domain_base = domain.split('.')[0]
    slug_parts = slug.split('-')
    distinctive_slug_words = [w for w in slug_parts if len(w) >= 5]

    if len(domain_base) >= 5 and domain_base in slug:
        return True

    # Distinctive slug words in domain (e.g., "leadville" in leadvilleraceseries.com)
    for w in distinctive_slug_words:
        if w in domain:
            return True

    # Multiple distinctive words from race name appear in URL path
    # Require 5+ char words to avoid false positives on generic terms
    name_words = [w.lower() for w in race_name.split() if len(w) >= 5]
    if name_words and len(name_words) >= 2:
        matches = sum(1 for w in name_words if w in url_lower)
        if matches >= 2:
            return True
    elif name_words and len(name_words) == 1:
        # Single distinctive word — must appear in path (not just domain)
        if name_words[0] in path:
            return True

    return False


def extract_urls_from_dumps(slug: str) -> list:
    """Extract unique URLs from research dump files for a given slug."""
    urls = set()

    for suffix in ['-raw.md', '-raw.bak.md', '-community.md']:
        path = DUMP_DIR / f"{slug}{suffix}"
        if path.exists():
            content = path.read_text(errors='replace')
            found = URL_RE.findall(content)
            for url in found:
                cleaned = clean_url(url)
                if cleaned and not is_excluded(cleaned):
                    urls.add(cleaned)

    return sorted(urls)


def find_official_website(race: dict) -> str:
    """Find official website URL from multiple possible JSON locations."""
    # Check logistics.official_site
    logistics = race.get('logistics', {})
    if isinstance(logistics, dict):
        official = logistics.get('official_site', '')
        if official and official.startswith('http'):
            return official

    # Check vitals.website
    vitals = race.get('vitals', {})
    if isinstance(vitals, dict):
        website = vitals.get('website', '')
        if website and website.startswith('http'):
            return website

    # Check organizer.website
    organizer = race.get('organizer', {})
    if isinstance(organizer, dict):
        website = organizer.get('website', '')
        if website and website.startswith('http'):
            return website

    return ''


def build_citations(slug: str, race: dict) -> list:
    """Build citation list for a race from all available sources."""
    citations = []
    seen_normalized = set()  # Track normalized URLs for dedup

    race_name = race.get('display_name', '') or race.get('name', slug)

    def add_citation(url, category, label):
        """Add citation if not a duplicate (by normalized URL)."""
        norm = normalize_url(url)
        if norm in seen_normalized:
            return
        seen_normalized.add(norm)
        citations.append({
            'url': url,
            'category': category,
            'label': label,
        })

    # 1. Official website from JSON (check multiple locations)
    official = find_official_website(race)
    if official:
        add_citation(official, 'official', 'Official Website')

    # 2. RideWithGPS from course_description
    cd = race.get('course_description', {})
    if isinstance(cd, dict):
        rwgps_id = cd.get('ridewithgps_id')
        rwgps_name = cd.get('ridewithgps_name', '')
        if rwgps_id:
            url = f"https://ridewithgps.com/routes/{rwgps_id}"
            label = f"RideWithGPS: {rwgps_name}" if rwgps_name else "RideWithGPS Route"
            add_citation(url, 'route', label)

    # 3. Links from JSON (if present)
    links = race.get('links', {})
    if isinstance(links, dict):
        for key, url in links.items():
            if isinstance(url, str) and url.startswith('http'):
                category, label = categorize_url(url)
                add_citation(url, category, f"{label}: {key.replace('_', ' ').title()}")

    # 4. URLs from research dumps — with relevance filtering
    dump_urls = extract_urls_from_dumps(slug)
    for url in dump_urls:
        norm = normalize_url(url)
        if norm in seen_normalized:
            continue
        if not is_relevant_to_race(url, slug, race_name):
            continue
        category, label = categorize_url(url)
        add_citation(url, category, label)

    # 5. Cap total citations
    if len(citations) > MAX_CITATIONS:
        # Keep official + route first, then prioritize by category
        priority = {'official': 0, 'route': 1, 'media': 2, 'community': 3,
                     'video': 4, 'reference': 5, 'registration': 6,
                     'tracking': 7, 'social': 8, 'activity': 9, 'other': 10}
        citations.sort(key=lambda c: priority.get(c['category'], 99))
        citations = citations[:MAX_CITATIONS]

    return citations


def main():
    parser = argparse.ArgumentParser(description='Extract citations for race profiles')
    parser.add_argument('--dry-run', action='store_true', help='Print results without writing')
    parser.add_argument('--slug', help='Process only this race slug')
    args = parser.parse_args()

    files = sorted(DATA_DIR.glob('*.json'))
    if args.slug:
        files = [DATA_DIR / f"{args.slug}.json"]

    total = 0
    with_citations = 0
    total_citations = 0
    max_count = 0
    max_slug = ''

    for path in files:
        slug = path.stem
        data = json.loads(path.read_text())
        race = data['race']

        citations = build_citations(slug, race)
        total += 1

        if citations:
            with_citations += 1
            total_citations += len(citations)
            if len(citations) > max_count:
                max_count = len(citations)
                max_slug = slug

        if args.dry_run:
            if citations:
                print(f"{slug}: {len(citations)} citations")
                for c in citations[:5]:
                    print(f"  [{c['category']}] {c['label']}: {c['url'][:80]}")
                if len(citations) > 5:
                    print(f"  ... +{len(citations) - 5} more")
        else:
            race['citations'] = citations
            data['race'] = race
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')

    avg = total_citations / total if total else 0
    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Summary:")
    print(f"  Processed: {total} races")
    print(f"  With citations: {with_citations} ({with_citations*100//total if total else 0}%)")
    print(f"  Total citations: {total_citations}")
    print(f"  Average per race: {avg:.1f}")
    print(f"  Max citations: {max_count} ({max_slug})")
    print(f"  Cap: {MAX_CITATIONS}")


if __name__ == '__main__':
    main()
