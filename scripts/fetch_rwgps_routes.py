#!/usr/bin/env python3
"""
Search Ride with GPS for race routes and populate ridewithgps_id in race profiles.

Uses the public RWGPS search API (no auth required) to find route matches
for each race, scoring candidates by name similarity, distance proximity,
and location overlap.

Usage:
    python scripts/fetch_rwgps_routes.py                    # T1+T2, interactive
    python scripts/fetch_rwgps_routes.py --all              # All tiers
    python scripts/fetch_rwgps_routes.py --tier 1           # T1 only
    python scripts/fetch_rwgps_routes.py --auto             # Auto-accept high-confidence
    python scripts/fetch_rwgps_routes.py --dry-run          # Preview without writing
    python scripts/fetch_rwgps_routes.py --race unbound-200 # Single race
    python scripts/fetch_rwgps_routes.py --verify           # Verify all existing RWGPS IDs
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
RATE_LIMIT_SECONDS = 1.0
AUTO_ACCEPT_THRESHOLD = 0.70
DISTANCE_TOLERANCE = 0.20  # 20% distance match window
METERS_PER_MILE = 1609.34

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
    """Extract city, state/region, country from location string."""
    if not location_str:
        return {}
    parts = [p.strip() for p in location_str.split(',')]
    result = {}
    if len(parts) >= 1:
        result['city'] = parts[0].lower()
    if len(parts) >= 2:
        state = parts[1].strip().lower()
        result['state'] = state
        # Normalize to abbreviation
        if state in US_STATES:
            result['state_abbrev'] = US_STATES[state]
        elif state.upper() in STATE_ABBREV_TO_FULL:
            result['state_abbrev'] = state.upper()
    if len(parts) >= 3:
        result['country'] = parts[2].strip().lower()
    return result


def search_rwgps(keywords: str, limit: int = 10) -> list:
    """Search RWGPS for routes matching keywords. Returns list of route dicts."""
    params = urllib.parse.urlencode({
        'search[keywords]': keywords,
        'search[offset]': 0,
        'search[limit]': limit,
    })
    url = f"{RWGPS_SEARCH_URL}?{params}"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'GravelGod-RouteSearch/1.0',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except Exception as e:
        print(f"  API error: {e}")
        return []

    results = data.get('results', [])
    # Filter to routes only (not trips/activities)
    # API nests data: {"type": "route", "route": {...actual fields...}}
    routes = [r['route'] for r in results if r.get('type') == 'route' and 'route' in r]
    return routes


def score_candidate(route: dict, race_name: str, race_distance_mi: float,
                    race_location: dict) -> dict:
    """Score a RWGPS route candidate against a race. Returns dict with scores."""
    route_name = route.get('name', '')

    # 1. Name similarity (0-1)
    name_score = SequenceMatcher(
        None,
        race_name.lower(),
        route_name.lower()
    ).ratio()

    # Boost if race name words appear in route name
    race_words = set(re.findall(r'\w+', race_name.lower()))
    route_words = set(re.findall(r'\w+', route_name.lower()))
    # Remove common filler words
    filler = {'the', 'a', 'an', 'of', 'in', 'at', 'and', 'or', 'gravel', 'race', 'ride'}
    race_keywords = race_words - filler
    if race_keywords:
        word_overlap = len(race_keywords & route_words) / len(race_keywords)
        name_score = max(name_score, word_overlap * 0.9)

    # 2. Distance proximity (0-1)
    distance_score = 0.0
    route_distance_mi = route.get('distance', 0) / METERS_PER_MILE
    if race_distance_mi and race_distance_mi > 0 and route_distance_mi > 0:
        ratio = min(route_distance_mi, race_distance_mi) / max(route_distance_mi, race_distance_mi)
        if ratio >= (1 - DISTANCE_TOLERANCE):
            distance_score = ratio
        else:
            # Partial credit for somewhat close distances
            distance_score = max(0, ratio * 0.5)

    # 3. Location match (0-1)
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
    composite = (name_score * 0.50) + (distance_score * 0.25) + (location_score * 0.25)

    return {
        'route_id': route['id'],
        'route_name': route_name,
        'distance_mi': round(route_distance_mi, 1),
        'elevation_ft': round(route.get('elevation_gain', 0) * 3.28084),
        'location': route.get('short_location', f"{route_locality}, {route_state}".strip(', ')),
        'unpaved_pct': route.get('unpaved_pct'),
        'name_score': round(name_score, 3),
        'distance_score': round(distance_score, 3),
        'location_score': round(location_score, 3),
        'composite': round(composite, 3),
    }


def load_race_profile(filepath: Path) -> dict:
    """Load a race profile JSON."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_race_profile(filepath: Path, data: dict):
    """Save a race profile JSON with consistent formatting."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def get_race_distance_mi(race: dict) -> float:
    """Extract primary distance in miles from race profile."""
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
    """Format a candidate for display."""
    unpaved = f", {c['unpaved_pct']}% unpaved" if c.get('unpaved_pct') else ""
    return (
        f"  [{idx}] {c['route_name']}\n"
        f"      {c['distance_mi']} mi, {c['elevation_ft']}' gain, {c['location']}{unpaved}\n"
        f"      Score: {c['composite']:.2f} "
        f"(name={c['name_score']:.2f} dist={c['distance_score']:.2f} loc={c['location_score']:.2f})\n"
        f"      https://ridewithgps.com/routes/{c['route_id']}"
    )


def write_rwgps_id(filepath: Path, route_id: int, route_name: str, dry_run: bool) -> bool:
    """Write ridewithgps_id to a race profile's course_description section."""
    data = load_race_profile(filepath)
    race = data.get('race', {})
    # Prefer course_description (standard key), fall back to course
    course_key = 'course_description' if 'course_description' in race else 'course'
    course = race.get(course_key, {})

    existing = course.get('ridewithgps_id')
    if existing and str(existing) not in ('TBD', ''):
        print(f"  Already has ridewithgps_id={existing}, skipping write")
        return False

    if dry_run:
        print(f"  [DRY RUN] Would write ridewithgps_id={route_id}")
        return True

    course['ridewithgps_id'] = str(route_id)
    course['ridewithgps_name'] = route_name
    data['race'][course_key] = course
    save_race_profile(filepath, data)
    print(f"  Wrote ridewithgps_id={route_id}")
    return True


def build_search_query(race_name: str, location: str) -> str:
    """Build a RWGPS search query from race name and location."""
    # Clean location: strip parenthetical notes and "to" destinations
    clean_loc = re.sub(r'\(.*?\)', '', location).strip()
    # For "A to B, State" locations, take the first city
    if ' to ' in clean_loc.lower():
        clean_loc = clean_loc.split(' to ')[0].strip().rstrip(',')
        # Re-append state if location had one after the last comma
        parts = [p.strip() for p in location.split(',')]
        if len(parts) >= 2:
            last_part = re.sub(r'\(.*?\)', '', parts[-1]).strip()
            if last_part:
                clean_loc = f"{clean_loc}, {last_part}"

    loc = parse_location(clean_loc)
    state = loc.get('state_abbrev', loc.get('state', ''))
    city = loc.get('city', '')
    query_parts = [race_name]
    if state:
        query_parts.append(state)
    elif city:
        query_parts.append(city)
    return ' '.join(query_parts)


def process_race(filepath: Path, auto: bool, dry_run: bool) -> str:
    """Process a single race file. Returns status string."""
    data = load_race_profile(filepath)
    race = data.get('race', {})
    # Race profiles use 'course_description' as the course key
    course = race.get('course_description', race.get('course', {}))
    slug = race.get('slug', filepath.stem)
    name = race.get('name', slug)
    location = race.get('vitals', {}).get('location', '')

    # Skip if already has a valid RWGPS ID
    existing_id = course.get('ridewithgps_id')
    if existing_id and str(existing_id) not in ('TBD', ''):
        return 'already_has_id'

    # Skip if map_url already has a RWGPS route (generator will extract it)
    map_url = course.get('map_url', '') or ''
    if re.search(r'ridewithgps\.com/routes/\d+', map_url):
        return 'has_map_url'

    distance_mi = get_race_distance_mi(data)
    race_location = parse_location(location)

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  {location} | {distance_mi} mi")
    print(f"{'='*60}")

    # Search RWGPS
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

    # Display top candidates
    for i, c in enumerate(top, 1):
        print(format_candidate(c, i))

    best = top[0]

    # Auto-accept mode
    if auto and best['composite'] >= AUTO_ACCEPT_THRESHOLD:
        print(f"\n  AUTO-ACCEPT (confidence {best['composite']:.2f} >= {AUTO_ACCEPT_THRESHOLD})")
        write_rwgps_id(filepath, best['route_id'], best['route_name'], dry_run)
        return 'matched'

    if auto and best['composite'] < AUTO_ACCEPT_THRESHOLD:
        print(f"\n  LOW CONFIDENCE ({best['composite']:.2f}), skipping in --auto mode")
        return 'low_confidence'

    # Interactive mode
    while True:
        choice = input("\n  Pick [1/2/3], (s)kip, (m)anual ID, (q)uit: ").strip().lower()
        if choice == 'q':
            return 'quit'
        if choice == 's':
            return 'skipped'
        if choice == 'm':
            manual = input("  Enter RWGPS route ID: ").strip()
            if manual.isdigit():
                route_name = input("  Route name (optional): ").strip() or name
                write_rwgps_id(filepath, int(manual), route_name, dry_run)
                return 'matched'
            print("  Invalid ID")
            continue
        if choice in ('1', '2', '3'):
            idx = int(choice) - 1
            if idx < len(top):
                c = top[idx]
                write_rwgps_id(filepath, c['route_id'], c['route_name'], dry_run)
                return 'matched'
        print("  Invalid choice")


def verify_rwgps_id(route_id: str) -> dict:
    """Verify a RWGPS route ID is valid by fetching its metadata.

    Returns dict with 'valid', 'name', 'distance_mi', 'error' keys.
    """
    url = f"https://ridewithgps.com/routes/{route_id}.json"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'GravelGod-Verify/1.0',
        'Accept': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return {
            'valid': True,
            'name': data.get('name', ''),
            'distance_mi': round(data.get('distance', 0) / METERS_PER_MILE, 1),
            'locality': data.get('locality', ''),
            'administrative_area': data.get('administrative_area', ''),
            'error': None,
        }
    except urllib.error.HTTPError as e:
        return {'valid': False, 'error': f"HTTP {e.code}"}
    except Exception as e:
        return {'valid': False, 'error': str(e)}


def run_verify(data_dir: Path, tier_filter: int = None, all_tiers: bool = False):
    """Verify all existing RWGPS IDs are valid routes."""
    files = sorted(data_dir.glob("*.json"))

    races_with_ids = []
    for fp in files:
        try:
            data = load_race_profile(fp)
        except (json.JSONDecodeError, KeyError):
            continue
        race = data.get('race', {})
        rating = race.get('gravel_god_rating', {})
        tier = rating.get('display_tier', rating.get('tier', 4))
        if tier_filter and tier != tier_filter:
            continue
        if not all_tiers and not tier_filter and tier > 2:
            continue

        course = race.get('course_description', race.get('course', {}))
        rwgps_id = course.get('ridewithgps_id')
        if not rwgps_id or str(rwgps_id) in ('TBD', ''):
            continue

        # Also check map_url for extractable RWGPS IDs
        map_url = course.get('map_url', '') or ''
        map_id = None
        m = re.search(r'ridewithgps\.com/routes/(\d+)', map_url)
        if m:
            map_id = m.group(1)

        name = race.get('name', fp.stem)
        dist = float(race.get('vitals', {}).get('distance_mi', 0) or 0)
        races_with_ids.append((fp.stem, name, str(rwgps_id), map_id, dist, tier))

    print(f"Verifying {len(races_with_ids)} RWGPS route IDs...\n")

    valid = 0
    invalid = 0
    distance_warnings = 0

    for i, (slug, name, rwgps_id, map_id, race_dist, tier) in enumerate(races_with_ids):
        result = verify_rwgps_id(rwgps_id)
        if result['valid']:
            # Check distance sanity — flag if RWGPS distance differs by >30%
            rwgps_dist = result['distance_mi']
            dist_ok = True
            if race_dist > 0 and rwgps_dist > 0:
                ratio = min(race_dist, rwgps_dist) / max(race_dist, rwgps_dist)
                if ratio < 0.70:
                    dist_ok = False
                    distance_warnings += 1

            status = "OK" if dist_ok else "DIST MISMATCH"
            icon = "+" if dist_ok else "~"
            detail = f"{result['name']} ({rwgps_dist}mi"
            if result['locality']:
                detail += f", {result['locality']}"
            if result['administrative_area']:
                detail += f", {result['administrative_area']}"
            detail += ")"
            if not dist_ok:
                detail += f" — race is {race_dist}mi"
            print(f"  [{icon}] T{tier} {slug}: {detail}")
            valid += 1
        else:
            print(f"  [!] T{tier} {slug}: INVALID — {result['error']}")
            invalid += 1

        # Also verify map_url ID if different from ridewithgps_id
        if map_id and map_id != rwgps_id:
            map_result = verify_rwgps_id(map_id)
            if not map_result['valid']:
                print(f"      map_url ID {map_id}: INVALID — {map_result['error']}")
            time.sleep(0.5)

        if i < len(races_with_ids) - 1:
            time.sleep(0.5)

    print(f"\n{'='*60}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Valid:              {valid}")
    print(f"  Invalid:            {invalid}")
    print(f"  Distance warnings:  {distance_warnings}")
    print(f"  Total checked:      {len(races_with_ids)}")

    if invalid > 0:
        print(f"\n  ⚠ {invalid} invalid route IDs need attention!")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Search RWGPS for race routes and populate ridewithgps_id"
    )
    parser.add_argument('--all', action='store_true',
                        help='Process all tiers (default: T1+T2 only)')
    parser.add_argument('--tier', type=int, choices=[1, 2, 3, 4],
                        help='Process only this tier')
    parser.add_argument('--auto', action='store_true',
                        help=f'Auto-accept matches with confidence >= {AUTO_ACCEPT_THRESHOLD}')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show matches without writing to files')
    parser.add_argument('--verify', action='store_true',
                        help='Verify all existing RWGPS IDs are valid routes')
    parser.add_argument('--race', type=str,
                        help='Process a single race by slug')
    parser.add_argument('--data-dir', type=Path, default=RACE_DATA,
                        help='Race data directory')
    args = parser.parse_args()

    data_dir = args.data_dir
    if not data_dir.exists():
        print(f"Error: data directory not found: {data_dir}")
        sys.exit(1)

    # Verify mode — check existing IDs, don't search
    if args.verify:
        run_verify(data_dir, tier_filter=args.tier, all_tiers=args.all)
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
        rating = data.get('race', {}).get('gravel_god_rating', {})
        tier = rating.get('display_tier', rating.get('tier', 4))
        if args.tier and tier != args.tier:
            continue
        if not args.all and not args.tier and not args.race and tier > 2:
            continue
        race_files.append((fp, tier))

    # Sort by tier (T1 first), then name
    race_files.sort(key=lambda x: (x[1], x[0].stem))

    total = len(race_files)
    print(f"Processing {total} races", end="")
    if args.dry_run:
        print(" [DRY RUN]", end="")
    if args.auto:
        print(" [AUTO MODE]", end="")
    print()

    stats = {
        'matched': 0, 'skipped': 0, 'no_results': 0,
        'already_has_id': 0, 'has_map_url': 0, 'low_confidence': 0,
    }

    for i, (fp, tier) in enumerate(race_files):
        result = process_race(fp, auto=args.auto, dry_run=args.dry_run)
        if result == 'quit':
            print("\nQuitting early.")
            break
        stats[result] = stats.get(result, 0) + 1
        # Rate limit between API calls
        if i < total - 1 and result not in ('already_has_id', 'has_map_url'):
            time.sleep(RATE_LIMIT_SECONDS)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"  Matched:          {stats['matched']}")
    print(f"  Already had ID:   {stats['already_has_id']}")
    print(f"  Has map_url:      {stats['has_map_url']}")
    print(f"  Skipped:          {stats['skipped']}")
    print(f"  No results:       {stats['no_results']}")
    print(f"  Low confidence:   {stats['low_confidence']}")


if __name__ == '__main__':
    main()
