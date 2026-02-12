#!/usr/bin/env python3
"""
Search Ride with GPS public API for race routes and populate ridewithgps_id
in race JSON profiles.

No auth required. Uses the RWGPS search endpoint to find route matches,
scoring candidates by name similarity, distance proximity, and location overlap.

Usage:
    python scripts/fetch_rwgps_routes.py                    # T1+T2 only, auto mode
    python scripts/fetch_rwgps_routes.py --all              # All tiers
    python scripts/fetch_rwgps_routes.py --tier 1           # T1 only
    python scripts/fetch_rwgps_routes.py --dry-run          # Show matches without writing
    python scripts/fetch_rwgps_routes.py --race unbound-200 # Single race
    python scripts/fetch_rwgps_routes.py --stats            # Show RWGPS coverage stats
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

RACE_DATA = Path(__file__).resolve().parent.parent / "race-data"
RWGPS_SEARCH_URL = "https://ridewithgps.com/find/search.json"
RATE_LIMIT_SECONDS = 1.1
AUTO_ACCEPT_THRESHOLD = 0.65
DISTANCE_TOLERANCE = 0.20  # 20% distance match window
METERS_PER_MILE = 1609.34
REQUEST_TIMEOUT = 10  # seconds
USER_AGENT = "GravelGodRaceDB/1.0 (gravel race RWGPS lookup)"

# Scoring weights
WEIGHT_NAME = 0.5
WEIGHT_DISTANCE = 0.3
WEIGHT_LOCATION = 0.2

# US state abbreviations for location matching
US_STATES = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN',
    'mississippi': 'MS', 'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE',
    'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
    'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC',
    'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK', 'oregon': 'OR',
    'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA',
    'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY',
}
STATE_ABBREV_TO_FULL = {v: k for k, v in US_STATES.items()}


def parse_location(location_str: str) -> dict:
    """Extract city, state/region, country from location string.

    Splits on commas and takes the last 1-2 parts as state/country.
    Returns dict with 'city', 'state', 'state_abbrev', 'country' keys
    where available.
    """
    if not location_str:
        return {}
    parts = [p.strip() for p in location_str.split(',')]
    result = {}
    if len(parts) >= 1:
        result['city'] = parts[0].lower()
    if len(parts) >= 2:
        state = parts[-1].strip().lower() if len(parts) == 2 else parts[1].strip().lower()
        result['state'] = state
        # Normalize to abbreviation
        if state in US_STATES:
            result['state_abbrev'] = US_STATES[state]
        elif state.upper() in STATE_ABBREV_TO_FULL:
            result['state_abbrev'] = state.upper()
    if len(parts) >= 3:
        result['country'] = parts[-1].strip().lower()
    return result


def search_rwgps(keywords: str, limit: int = 10) -> list:
    """Search RWGPS for routes matching keywords.

    Hits the public search API with search[keywords] and search[limit].
    Filters results client-side to type: "route" only (excludes trips).
    Returns list of route dicts.
    """
    params = urllib.parse.urlencode({
        'search[keywords]': keywords,
        'search[offset]': 0,
        'search[limit]': limit,
    })
    url = f"{RWGPS_SEARCH_URL}?{params}"
    req = urllib.request.Request(url, headers={
        'User-Agent': USER_AGENT,
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  API HTTP error: {e.code} {e.reason}")
        return []
    except urllib.error.URLError as e:
        print(f"  API connection error: {e.reason}")
        return []
    except json.JSONDecodeError as e:
        print(f"  API returned invalid JSON: {e}")
        return []
    except Exception as e:
        print(f"  API error: {e}")
        return []

    results = data.get('results', [])
    # Filter to routes only (not trips/activities)
    # API nests data: {"type": "route", "route": {...actual fields...}}
    routes = []
    for r in results:
        if r.get('type') == 'route' and 'route' in r:
            routes.append(r['route'])
    return routes


def score_candidate(route: dict, race_name: str, race_distance_mi: float,
                    race_location: dict) -> dict:
    """Score a RWGPS route candidate against a race.

    Scoring breakdown:
    - Name similarity (difflib.SequenceMatcher ratio, weight 0.5)
    - Distance proximity (within 20% is ideal, weight 0.3)
    - Location match (state/region string overlap, weight 0.2)

    Returns dict with individual scores and weighted composite.
    """
    route_name = route.get('name', '')

    # 1. Name similarity (0-1)
    name_score = SequenceMatcher(
        None,
        race_name.lower(),
        route_name.lower()
    ).ratio()

    # Boost if race name keywords appear in route name
    race_words = set(re.findall(r'\w+', race_name.lower()))
    route_words = set(re.findall(r'\w+', route_name.lower()))
    filler = {'the', 'a', 'an', 'of', 'in', 'at', 'and', 'or', 'gravel', 'race', 'ride'}
    race_keywords = race_words - filler
    if race_keywords:
        word_overlap = len(race_keywords & route_words) / len(race_keywords)
        name_score = max(name_score, word_overlap * 0.9)

    # 2. Distance proximity (0-1)
    # If distance_mi is missing or 0, skip distance scoring
    distance_score = 0.0
    route_distance_mi = route.get('distance', 0) / METERS_PER_MILE
    if race_distance_mi and race_distance_mi > 0 and route_distance_mi > 0:
        ratio = min(route_distance_mi, race_distance_mi) / max(route_distance_mi, race_distance_mi)
        if ratio >= (1 - DISTANCE_TOLERANCE):
            distance_score = ratio
        else:
            # Partial credit for somewhat close distances
            distance_score = max(0, ratio * 0.5)

    # 3. Location match (0-1) — state/region string overlap
    location_score = 0.0
    route_state = (route.get('administrative_area') or '').lower()
    route_locality = (route.get('locality') or '').lower()

    if race_location.get('state_abbrev'):
        if route_state.upper() == race_location['state_abbrev']:
            location_score = 0.8
        elif route_state == race_location.get('state', ''):
            location_score = 0.8
    elif race_location.get('state'):
        if route_state == race_location['state']:
            location_score = 0.8

    if race_location.get('city') and route_locality:
        if race_location['city'] in route_locality or route_locality in race_location['city']:
            location_score = 1.0

    # Weighted composite
    composite = (
        (name_score * WEIGHT_NAME)
        + (distance_score * WEIGHT_DISTANCE)
        + (location_score * WEIGHT_LOCATION)
    )

    return {
        'route_id': route['id'],
        'route_name': route_name,
        'distance_mi': round(route_distance_mi, 1),
        'elevation_ft': round(route.get('elevation_gain', 0) * 3.28084),
        'location': route.get('short_location', f"{route_locality}, {route_state}".strip(', ')),
        'terrain': route.get('terrain', ''),
        'name_score': round(name_score, 3),
        'distance_score': round(distance_score, 3),
        'location_score': round(location_score, 3),
        'composite': round(composite, 3),
    }


def load_race_profile(filepath: Path) -> dict:
    """Load a race profile JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_race_profile(filepath: Path, data: dict):
    """Save a race profile JSON with consistent formatting."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def get_race_distance_mi(race: dict) -> float:
    """Extract primary distance in miles from race profile.

    Checks vitals.distance_mi first, then tries to parse from distance string.
    Returns 0.0 if not found.
    """
    vitals = race.get('race', {}).get('vitals', {})
    dist = vitals.get('distance_mi')
    if dist and isinstance(dist, (int, float)):
        return float(dist)
    # Try parsing from distance string like "200 miles"
    dist_str = vitals.get('distance', '')
    if dist_str:
        m = re.search(r'([\d.]+)\s*(?:mi|mile)', str(dist_str), re.IGNORECASE)
        if m:
            return float(m.group(1))
        m = re.search(r'([\d.]+)\s*(?:km|kilo)', str(dist_str), re.IGNORECASE)
        if m:
            return float(m.group(1)) * 0.621371
    return 0.0


def format_candidate(c: dict, idx: int) -> str:
    """Format a candidate route for display."""
    terrain = f", terrain={c['terrain']}" if c.get('terrain') else ""
    return (
        f"  [{idx}] {c['route_name']}\n"
        f"      {c['distance_mi']} mi, {c['elevation_ft']}' gain, {c['location']}{terrain}\n"
        f"      Score: {c['composite']:.2f} "
        f"(name={c['name_score']:.2f} dist={c['distance_score']:.2f} loc={c['location_score']:.2f})\n"
        f"      https://ridewithgps.com/routes/{c['route_id']}"
    )


def write_rwgps_id(filepath: Path, route_id: int, route_name: str, dry_run: bool) -> bool:
    """Write ridewithgps_id and ridewithgps_name to the race JSON course_description section."""
    data = load_race_profile(filepath)
    race = data.get('race', {})
    course = race.get('course_description', {})

    existing = course.get('ridewithgps_id')
    if existing and str(existing) not in ('TBD', ''):
        print(f"  Already has ridewithgps_id={existing}, skipping write")
        return False

    if dry_run:
        print(f"  [DRY RUN] Would write ridewithgps_id={route_id}, ridewithgps_name=\"{route_name}\"")
        return True

    course['ridewithgps_id'] = str(route_id)
    course['ridewithgps_name'] = route_name
    data['race']['course_description'] = course
    save_race_profile(filepath, data)
    print(f"  Wrote ridewithgps_id={route_id}, ridewithgps_name=\"{route_name}\"")
    return True


def build_search_query(race_name: str, location: str) -> str:
    """Build a RWGPS search query from race name + state/country extracted from location.

    Extracts state/country from location by splitting on commas and taking the
    last 1-2 parts. Appends to the race name for geographic context.
    """
    if not location:
        return race_name

    parts = [p.strip() for p in location.split(',')]
    # Take last 1-2 parts as state/country context
    if len(parts) >= 2:
        geo_context = ', '.join(parts[-2:]).strip()
    elif len(parts) == 1:
        geo_context = parts[0].strip()
    else:
        geo_context = ''

    if geo_context:
        return f"{race_name} {geo_context}"
    return race_name


def process_race(filepath: Path, dry_run: bool) -> str:
    """Process a single race file: search RWGPS and auto-match.

    Returns status string: 'matched', 'already_has_id', 'no_results',
    'low_confidence', or 'error'.
    """
    try:
        data = load_race_profile(filepath)
    except json.JSONDecodeError as e:
        print(f"  JSON decode error in {filepath.name}: {e}")
        return 'error'
    except Exception as e:
        print(f"  Error loading {filepath.name}: {e}")
        return 'error'

    race = data.get('race', {})
    course = race.get('course_description', {})
    slug = race.get('slug', filepath.stem)
    name = race.get('name', slug)
    location = race.get('vitals', {}).get('location', '')

    # Skip races that already have a numeric ridewithgps_id (not "TBD")
    existing_id = course.get('ridewithgps_id')
    if existing_id and str(existing_id) not in ('TBD', ''):
        return 'already_has_id'

    distance_mi = get_race_distance_mi(data)
    race_location = parse_location(location)

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  {location} | {distance_mi} mi")
    print(f"{'='*60}")

    # Build search query from race name + state/country from location
    query = build_search_query(name, location)
    print(f"  Searching: \"{query}\"")

    routes = search_rwgps(query, limit=10)
    if not routes:
        print("  No routes found")
        return 'no_results'

    # Score candidates
    candidates = [
        score_candidate(r, name, distance_mi, race_location)
        for r in routes
    ]
    candidates.sort(key=lambda c: c['composite'], reverse=True)
    top = candidates[:3]

    # Display top candidates with matched route name and distance for verification
    for i, c in enumerate(top, 1):
        print(format_candidate(c, i))

    best = top[0]

    # Auto-accept the best match if confidence >= threshold
    if best['composite'] >= AUTO_ACCEPT_THRESHOLD:
        print(f"\n  AUTO-ACCEPT (confidence {best['composite']:.2f} >= {AUTO_ACCEPT_THRESHOLD})")
        write_rwgps_id(filepath, best['route_id'], best['route_name'], dry_run)
        return 'matched'
    else:
        print(f"\n  NO MATCH (best confidence {best['composite']:.2f} < {AUTO_ACCEPT_THRESHOLD})")
        return 'low_confidence'


def get_tier(data: dict) -> int:
    """Extract tier from a race profile dict."""
    rating = data.get('race', {}).get('gravel_god_rating', {})
    return rating.get('display_tier', rating.get('tier', 4))


def run_stats(data_dir: Path):
    """Show RWGPS coverage stats: how many races have RWGPS IDs by tier."""
    files = sorted(data_dir.glob("*.json"))

    # Collect per-tier counts
    tier_total = {1: 0, 2: 0, 3: 0, 4: 0}
    tier_has_id = {1: 0, 2: 0, 3: 0, 4: 0}
    missing_by_tier = {1: [], 2: [], 3: [], 4: []}

    for fp in files:
        try:
            data = load_race_profile(fp)
        except (json.JSONDecodeError, KeyError):
            continue

        race = data.get('race', {})
        tier = get_tier(data)
        if tier not in tier_total:
            tier = 4

        tier_total[tier] += 1

        course = race.get('course_description', {})
        rwgps_id = course.get('ridewithgps_id')
        if rwgps_id and str(rwgps_id) not in ('TBD', ''):
            tier_has_id[tier] += 1
        else:
            missing_by_tier[tier].append(race.get('name', fp.stem))

    total_all = sum(tier_total.values())
    total_with_id = sum(tier_has_id.values())

    print(f"\n{'='*60}")
    print("RWGPS COVERAGE STATS")
    print(f"{'='*60}")
    print()

    for t in (1, 2, 3, 4):
        total = tier_total[t]
        has_id = tier_has_id[t]
        pct = (has_id / total * 100) if total > 0 else 0
        bar_filled = int(pct / 5)  # 20-char bar
        bar = '#' * bar_filled + '-' * (20 - bar_filled)
        print(f"  Tier {t}: {has_id:3d} / {total:3d} ({pct:5.1f}%)  [{bar}]")

    print()
    overall_pct = (total_with_id / total_all * 100) if total_all > 0 else 0
    print(f"  Total: {total_with_id} / {total_all} ({overall_pct:.1f}%)")

    # Show missing T1/T2 races
    for t in (1, 2):
        missing = missing_by_tier[t]
        if missing:
            print(f"\n  Missing T{t} ({len(missing)}):")
            for name in sorted(missing):
                print(f"    - {name}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Search RWGPS for race routes and populate ridewithgps_id in race profiles."
    )
    parser.add_argument('--all', action='store_true',
                        help='Process all tiers (default: T1+T2 only)')
    parser.add_argument('--tier', type=int, choices=[1, 2, 3, 4],
                        help='Process only this tier')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show matches without writing to files')
    parser.add_argument('--race', type=str,
                        help='Process a single race by slug')
    parser.add_argument('--stats', action='store_true',
                        help='Show RWGPS coverage stats by tier')
    parser.add_argument('--data-dir', type=Path, default=RACE_DATA,
                        help='Race data directory (default: race-data/)')
    args = parser.parse_args()

    data_dir = args.data_dir
    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}")
        sys.exit(1)

    # Stats mode — show coverage and exit
    if args.stats:
        run_stats(data_dir)
        return

    # Collect race files to process
    if args.race:
        filepath = data_dir / f"{args.race}.json"
        if not filepath.exists():
            print(f"Error: race file not found: {filepath}")
            sys.exit(1)
        files = [filepath]
    else:
        files = sorted(data_dir.glob("*.json"))

    # Filter by tier
    race_files = []
    for fp in files:
        try:
            data = load_race_profile(fp)
        except (json.JSONDecodeError, KeyError):
            continue
        tier = get_tier(data)
        if args.tier and tier != args.tier:
            continue
        # Default: T1+T2 only (unless --all or --tier or --race specified)
        if not args.all and not args.tier and not args.race and tier > 2:
            continue
        race_files.append((fp, tier))

    # Sort by tier (T1 first), then alphabetically by slug
    race_files.sort(key=lambda x: (x[1], x[0].stem))

    total = len(race_files)
    mode_label = " [DRY RUN]" if args.dry_run else ""
    tier_label = f" T{args.tier}" if args.tier else (" all tiers" if args.all else " T1+T2")
    print(f"Processing {total} races ({tier_label}){mode_label}")

    stats = {
        'matched': 0,
        'already_has_id': 0,
        'no_results': 0,
        'low_confidence': 0,
        'error': 0,
    }

    for i, (fp, tier) in enumerate(race_files):
        result = process_race(fp, dry_run=args.dry_run)
        stats[result] = stats.get(result, 0) + 1

        # Rate limit between API calls — skip delay for races that didn't hit the API
        if i < total - 1 and result not in ('already_has_id', 'error'):
            time.sleep(RATE_LIMIT_SECONDS)

    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Matched:          {stats['matched']}")
    print(f"  Already had ID:   {stats['already_has_id']}")
    print(f"  No results:       {stats['no_results']}")
    print(f"  Low confidence:   {stats['low_confidence']}")
    if stats['error']:
        print(f"  Errors:           {stats['error']}")
    skipped = stats['already_has_id']
    failed = stats['no_results'] + stats['low_confidence']
    print(f"  ---")
    print(f"  Total processed:  {sum(stats.values())}")
    print(f"  Skipped (had ID): {skipped}")
    print(f"  Failed (no match):{failed}")


if __name__ == '__main__':
    main()
