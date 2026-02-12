#!/usr/bin/env python3
"""
Geocode all race locations using Nominatim (OpenStreetMap).

Adds lat/lng coordinates to each race profile's vitals section.
Uses free Nominatim API — rate limited to 1 request/second per policy.

Usage:
    python scripts/geocode_races.py                # Geocode races missing coords
    python scripts/geocode_races.py --all          # Re-geocode all races
    python scripts/geocode_races.py --dry-run      # Preview without writing
    python scripts/geocode_races.py --race unbound-200  # Single race
    python scripts/geocode_races.py --stats        # Show coverage stats
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

RACE_DATA = Path(__file__).resolve().parent.parent / "race-data"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "GravelGodRaceDB/1.0 (gravel race geocoding)"

# Manual overrides for locations that Nominatim can't resolve or gets wrong
MANUAL_COORDS = {
    # Multi-location / global series — use HQ or primary location
    "gravel-earth": (41.9794, 2.8214),                  # Girona, Spain (HQ)
    "grinduro": (38.4324, -120.0356),                  # Quincy, CA (flagship)
    "transcontinental-race": (48.2082, 16.3738),       # Vienna (common start)
    "uci-gravel-worlds": (45.2083, 5.7148),            # Grenoble, France (2025)
    "uci-gravel-suisse": (46.3188, 6.9746),            # Aigle, Switzerland
    "uci-gravel-dustman": (50.6292, 3.0573),           # Lille, France
    # Vague locations
    "grasshopper-adventure-series": (38.2975, -122.2869),  # Fairfax, CA
    "nordic-chase-gravel-edition": (55.6761, 12.5683),     # Copenhagen
    "haute-route-gravel": (45.1885, 5.7245),               # Grenoble, France (primary venue)
}


def geocode_location(location: str, slug: str) -> tuple:
    """Geocode a location string via Nominatim. Returns (lat, lng) or (None, None)."""
    if slug in MANUAL_COORDS:
        return MANUAL_COORDS[slug]

    if not location:
        return None, None

    # Clean up location strings for better geocoding
    query = location
    # Remove parenthetical notes like "(Sandhills Global Event Center)"
    query = re.sub(r'\(.*?\)', '', query).strip()
    # Remove "HQ:" prefixes
    query = re.sub(r'^(?:Global,?\s*)?HQ:\s*', '', query).strip()
    # Remove common noise words
    query = re.sub(r'\b(?:area|region|near|outside)\b', '', query, flags=re.IGNORECASE).strip()
    # Clean up extra commas/spaces
    query = re.sub(r',\s*,', ',', query).strip(', ')

    if not query:
        return None, None

    params = urllib.parse.urlencode({
        'q': query,
        'format': 'json',
        'limit': 1,
        'addressdetails': 0,
    })
    url = f"{NOMINATIM_URL}?{params}"

    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"  ⚠ Geocoding failed for '{query}': {e}")

    # Fallback: try just the last part (state/country)
    parts = query.split(',')
    if len(parts) > 1:
        fallback = parts[-1].strip()
        params = urllib.parse.urlencode({
            'q': fallback,
            'format': 'json',
            'limit': 1,
        })
        url = f"{NOMINATIM_URL}?{params}"
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        try:
            time.sleep(1)  # Rate limit
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if data:
                    return float(data[0]['lat']), float(data[0]['lon'])
        except Exception:
            pass

    return None, None


def main():
    parser = argparse.ArgumentParser(description="Geocode race locations")
    parser.add_argument("--all", action="store_true", help="Re-geocode all races (default: only missing)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--race", help="Geocode a single race by slug")
    parser.add_argument("--stats", action="store_true", help="Show coverage stats only")
    args = parser.parse_args()

    # Load all profiles
    profiles = []
    for f in sorted(RACE_DATA.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            profiles.append((f, data))
        except json.JSONDecodeError:
            print(f"  ⚠ Skipping invalid JSON: {f.name}")

    if args.stats:
        has_coords = sum(1 for _, d in profiles
                        if d.get("race", {}).get("vitals", {}).get("lat") is not None)
        print(f"Geocoded: {has_coords}/{len(profiles)} ({has_coords*100//len(profiles)}%)")
        missing = [(f.stem, d.get("race", {}).get("vitals", {}).get("location", ""))
                   for f, d in profiles
                   if d.get("race", {}).get("vitals", {}).get("lat") is None]
        if missing:
            print(f"\nMissing ({len(missing)}):")
            for slug, loc in missing:
                print(f"  {slug}: {loc}")
        return

    # Filter to target races
    if args.race:
        profiles = [(f, d) for f, d in profiles if f.stem == args.race]
        if not profiles:
            print(f"Race '{args.race}' not found")
            sys.exit(1)

    geocoded = 0
    skipped = 0
    failed = 0

    for filepath, data in profiles:
        slug = filepath.stem
        race = data.get("race", {})
        vitals = race.get("vitals", {})
        location = vitals.get("location", "")

        # Skip if already has coords (unless --all)
        if not args.all and vitals.get("lat") is not None:
            skipped += 1
            continue

        lat, lng = geocode_location(location, slug)

        if lat is not None:
            vitals["lat"] = round(lat, 4)
            vitals["lng"] = round(lng, 4)
            geocoded += 1

            if args.dry_run:
                print(f"  ✓ {slug}: {location} → ({lat:.4f}, {lng:.4f})")
            else:
                filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                print(f"  ✓ {slug}: ({lat:.4f}, {lng:.4f})")
        else:
            failed += 1
            print(f"  ✗ {slug}: Could not geocode '{location}'")

        # Rate limit: 1 request per second (Nominatim policy)
        time.sleep(1.1)

    print(f"\nDone. Geocoded: {geocoded}, Skipped: {skipped}, Failed: {failed}")


if __name__ == "__main__":
    main()
