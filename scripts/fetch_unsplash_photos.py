#!/usr/bin/env python3
"""
Fetch Unsplash photos for gravel race profiles.

Queries Unsplash API per race, stores photo metadata in the race JSON
under an `unsplash_photos` field. Zero runtime cost — photos are rendered
statically by the page generator.

Usage:
    python scripts/fetch_unsplash_photos.py --dry-run --auto 5
    python scripts/fetch_unsplash_photos.py --auto 328
    python scripts/fetch_unsplash_photos.py --slugs unbound-200 steamboat-gravel
    python scripts/fetch_unsplash_photos.py --force --auto 10
    python scripts/fetch_unsplash_photos.py --trigger-downloads

Requires: UNSPLASH_ACCESS_KEY in .env

Rate limits (demo tier): 50 requests/hour. The script tracks remaining
requests via X-Ratelimit-Remaining headers and pauses automatically
when the budget is low.
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RACE_DATA = Path(__file__).resolve().parent.parent / "race-data"
API_BASE = "https://api.unsplash.com"
MAX_PHOTOS = 3
UTM_SOURCE = "gravel_god_cycling"
UTM_MEDIUM = "referral"

# Track rate limit state
rate_remaining = 50
rate_reset_time = 0


def get_access_key() -> str:
    key = os.environ.get("UNSPLASH_ACCESS_KEY", "")
    if not key:
        print("ERROR: UNSPLASH_ACCESS_KEY not set in .env or environment", file=sys.stderr)
        sys.exit(1)
    return key


def api_request(url: str, access_key: str, timeout: int = 15):
    """Make an authenticated Unsplash API request with rate limit handling.
    Returns parsed JSON on success, None on failure."""
    global rate_remaining, rate_reset_time

    # If we know we're out of budget, wait for reset
    if rate_remaining <= 1:
        if rate_reset_time > time.time():
            wait = int(rate_reset_time - time.time()) + 5
        else:
            wait = 3600  # fallback: wait 1 hour
        print(f"\n  ⏳ Rate limit reached. Waiting {wait}s for reset...", flush=True)
        time.sleep(wait)
        rate_remaining = 50  # assume reset happened

    req = urllib.request.Request(url, headers={
        "Authorization": f"Client-ID {access_key}",
        "Accept-Version": "v1",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Update rate limit tracking from response headers
            remaining = resp.headers.get("X-Ratelimit-Remaining")
            if remaining is not None:
                rate_remaining = int(remaining)
            reset = resp.headers.get("X-Ratelimit-Reset")
            if reset is not None:
                rate_reset_time = int(reset)
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 403:
            # Read rate limit headers from error response
            remaining = e.headers.get("X-Ratelimit-Remaining")
            if remaining is not None:
                rate_remaining = int(remaining)
            else:
                rate_remaining = 0
            reset = e.headers.get("X-Ratelimit-Reset")
            if reset is not None:
                rate_reset_time = int(reset)

            # Wait and retry
            if rate_reset_time > time.time():
                wait = int(rate_reset_time - time.time()) + 5
            else:
                wait = 3600
            print(f"\n  ⏳ Rate limit hit (403). Waiting {wait}s for reset...", flush=True)
            time.sleep(wait)
            rate_remaining = 50
            return api_request(url, access_key, timeout)
        print(f"  Unsplash API error {e.code}: {e.reason}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  Request failed: {e}", file=sys.stderr)
        return None


def search_unsplash(query: str, access_key: str, per_page: int = MAX_PHOTOS) -> list:
    """Search Unsplash for landscape-oriented photos matching query."""
    params = urllib.parse.urlencode({
        "query": query,
        "per_page": per_page,
        "orientation": "landscape",
    })
    url = f"{API_BASE}/search/photos?{params}"
    data = api_request(url, access_key)
    if data is None:
        return []
    return data.get("results", [])


def trigger_download(download_location: str, access_key: str) -> None:
    """Notify Unsplash that a photo is being used (required by API guidelines).
    Best-effort — failures don't stop the pipeline."""
    if not download_location:
        return
    api_request(download_location, access_key, timeout=10)


def extract_photo_data(result: dict) -> dict:
    """Extract the fields we store from an Unsplash search result."""
    user = result.get("user", {})
    urls = result.get("urls", {})
    return {
        "id": result["id"],
        "url_regular": urls.get("regular", ""),
        "url_small": urls.get("small", ""),
        "photographer": user.get("name", "Unknown"),
        "photographer_url": user.get("links", {}).get("html", ""),
        "description": result.get("alt_description") or result.get("description") or "",
        "download_location": result.get("links", {}).get("download_location", ""),
    }


def _clean_location_part(s: str) -> str:
    """Strip parenthetical notes and extra whitespace from a location part."""
    import re
    return re.sub(r'\(.*?\)', '', s).strip()


def build_search_queries(rd: dict) -> list[str]:
    """Build tiered search queries from race data.
    Returns list of queries to try in order, broadening progressively."""
    name = rd.get("name", "")
    location = rd.get("vitals", {}).get("location", "")

    queries = []

    # Parse location into parts, stripping parenthetical notes
    loc_parts = [_clean_location_part(p) for p in location.split(",")] if location else []
    city = loc_parts[0] if len(loc_parts) >= 1 else ""
    state = loc_parts[1] if len(loc_parts) >= 2 else ""
    country = loc_parts[2] if len(loc_parts) >= 3 else ""

    # Tier 1: race name (rarely works but worth a shot — costs 1 request)
    if name:
        queries.append(f"{name} cycling")

    # Tier 2: state/region + gravel cycling
    if state:
        queries.append(f"{state} gravel cycling")

    # Tier 3: country-level fallback (for non-US/non-obvious regions)
    if country:
        queries.append(f"{country} gravel cycling")

    # Tier 4: generic gravel + landscape for the broadest location available
    broadest = country or state or city
    if broadest:
        queries.append(f"{broadest} dirt road landscape")

    return queries


def fetch_photos_for_race(rd: dict, access_key: str, dry_run: bool = False) -> list:
    """Try each search query until we get results. Returns list of photo dicts.
    Does NOT trigger downloads — those are deferred to save rate limit budget."""
    queries = build_search_queries(rd)
    if not queries:
        print(f"  No searchable data for {rd.get('slug', '?')}")
        return []

    for query in queries:
        print(f"  Searching: \"{query}\"", end="", flush=True)
        if dry_run:
            print(" [DRY RUN — skipping API call]")
            continue

        results = search_unsplash(query, access_key)
        # Small delay between searches to be polite
        time.sleep(0.5)

        if results:
            photos = [extract_photo_data(r) for r in results]
            print(f" → {len(photos)} photo(s)")
            return photos
        else:
            print(" → 0 results")

    return []


def load_race_files(slugs: list = None, auto: int = None, force: bool = False) -> list:
    """Load race JSON files to process."""
    files = sorted(RACE_DATA.glob("*.json"))
    candidates = []

    for f in files:
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue

        race = data.get("race", {})
        slug = race.get("slug", f.stem)

        # Filter by slugs if specified
        if slugs and slug not in slugs:
            continue

        # Skip races that already have photos (unless --force)
        if not force and race.get("unsplash_photos"):
            continue

        candidates.append(f)

    # Limit by --auto
    if auto is not None:
        candidates = candidates[:auto]

    return candidates


def run_trigger_downloads(access_key: str):
    """Trigger download events for all races that have unsplash_photos
    but haven't had their downloads tracked yet. Adds a 'downloads_triggered'
    flag so we don't re-trigger."""
    files = sorted(RACE_DATA.glob("*.json"))
    pending = []

    for f in files:
        try:
            data = json.loads(f.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        race = data.get("race", {})
        photos = race.get("unsplash_photos", [])
        if photos and not race.get("downloads_triggered"):
            pending.append((f, data))

    print(f"Triggering downloads for {len(pending)} race(s)...\n")
    triggered = 0

    for f, data in pending:
        race = data["race"]
        slug = race.get("slug", f.stem)
        photos = race["unsplash_photos"]
        print(f"[{slug}] {len(photos)} photo(s)", end="", flush=True)

        for p in photos:
            trigger_download(p.get("download_location", ""), access_key)
            time.sleep(0.3)

        race["downloads_triggered"] = True
        f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        triggered += 1
        print(f" ✓ (remaining: {rate_remaining})")

    print(f"\nDone: {triggered} race(s) downloads triggered")


def main():
    parser = argparse.ArgumentParser(description="Fetch Unsplash photos for race profiles")
    parser.add_argument("--auto", type=int, help="Process up to N races without photos")
    parser.add_argument("--slugs", nargs="+", help="Process specific race slugs")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fetched without calling API")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if unsplash_photos already exists")
    parser.add_argument("--trigger-downloads", action="store_true",
                        help="Trigger Unsplash download events for already-fetched photos")
    args = parser.parse_args()

    if args.trigger_downloads:
        access_key = get_access_key()
        run_trigger_downloads(access_key)
        return

    if not args.auto and not args.slugs:
        print("ERROR: Specify --auto N or --slugs <slug> [...] or --trigger-downloads", file=sys.stderr)
        sys.exit(1)

    access_key = "" if args.dry_run else get_access_key()

    files = load_race_files(slugs=args.slugs, auto=args.auto, force=args.force)
    print(f"Processing {len(files)} race(s)...\n")

    updated = 0
    skipped = 0

    for f in files:
        data = json.loads(f.read_text())
        race = data["race"]
        slug = race.get("slug", f.stem)
        print(f"[{slug}] (budget: {rate_remaining})")

        photos = fetch_photos_for_race(race, access_key, dry_run=args.dry_run)

        if args.dry_run:
            print()
            continue

        if photos:
            race["unsplash_photos"] = photos
            f.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            updated += 1
            print(f"  ✓ Saved {len(photos)} photo(s)\n")
        else:
            skipped += 1
            print(f"  — No photos found\n")

    print(f"Done: {updated} updated, {skipped} skipped")
    if args.dry_run:
        print("(Dry run — no files modified)")


if __name__ == "__main__":
    main()
