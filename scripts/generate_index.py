#!/usr/bin/env python3
"""
Generate race index JSON for the searchable database page.

Reads all canonical race JSONs + flat database → produces race-index.json
with the data needed for client-side filtering and display.

Also generates JSON-LD structured data for each race with a profile.

Usage:
    python generate_index.py                    # Generate race-index.json
    python generate_index.py --with-jsonld      # Also generate JSON-LD per race
    python generate_index.py --stats            # Show coverage statistics
"""

import argparse
import json
import re
from pathlib import Path
from typing import Optional


RACE_DATA = Path(__file__).parent.parent / "race-data"
FLAT_DB = Path(__file__).parent.parent / "gravel_races_full_database.json"
OUTPUT_DIR = Path(__file__).parent.parent / "web"


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)
    return slug


def extract_region(location: str) -> str:
    """Extract broad region from location string."""
    if not location:
        return "Unknown"

    location_lower = location.lower()

    # International
    country_map = {
        "iceland": "Europe", "uk": "Europe", "england": "Europe",
        "scotland": "Europe", "spain": "Europe", "italy": "Europe",
        "france": "Europe", "belgium": "Europe", "australia": "Oceania",
        "new zealand": "Oceania", "canada": "North America",
        "south africa": "Africa", "mexico": "North America",
    }
    for country, region in country_map.items():
        if country in location_lower:
            return region

    # US regions
    us_regions = {
        "West": ["california", "oregon", "washington", "colorado", "utah",
                 "montana", "wyoming", "idaho", "nevada", "arizona", "new mexico"],
        "Midwest": ["kansas", "nebraska", "iowa", "illinois", "indiana", "ohio",
                    "michigan", "wisconsin", "minnesota", "missouri", "oklahoma"],
        "South": ["texas", "arkansas", "louisiana", "mississippi", "alabama",
                 "georgia", "florida", "tennessee", "kentucky", "north carolina",
                 "south carolina", "virginia", "west virginia"],
        "Northeast": ["new york", "pennsylvania", "connecticut", "massachusetts",
                     "vermont", "new hampshire", "maine", "maryland", "new jersey",
                     "delaware", "rhode island"],
    }
    for region, states in us_regions.items():
        if any(s in location_lower for s in states):
            return region

    return "Other"


def extract_month(date_str: str) -> Optional[str]:
    """Extract month from date string."""
    if not date_str:
        return None
    months = ["january", "february", "march", "april", "may", "june",
              "july", "august", "september", "october", "november", "december"]
    date_lower = date_str.lower()
    for month in months:
        if month[:3] in date_lower:
            return month.capitalize()
    return None


def build_index_entry_from_profile(slug: str, data: dict) -> dict:
    """Build index entry from a canonical race JSON."""
    race = data.get("race", {})
    vitals = race.get("vitals", {})
    rating = race.get("gravel_god_rating", {})
    location = vitals.get("location", "")

    # Extract 14 scores
    course_vars = ["logistics", "length", "technicality", "elevation", "climate", "altitude", "adventure"]
    editorial_vars = ["prestige", "race_quality", "experience", "community", "field_depth", "value", "expenses"]
    scores = {}
    for var in course_vars + editorial_vars:
        val = rating.get(var)
        if isinstance(val, (int, float)):
            scores[var] = int(val)

    return {
        "name": race.get("display_name") or race.get("name", slug),
        "slug": slug,
        "location": location,
        "region": extract_region(location),
        "month": extract_month(vitals.get("date", "")),
        "distance_mi": vitals.get("distance_mi"),
        "elevation_ft": vitals.get("elevation_ft"),
        "tier": rating.get("tier", 3),
        "overall_score": rating.get("overall_score"),
        "scores": scores,
        "tagline": race.get("tagline", ""),
        "has_profile": True,
        "profile_url": f"/{slug}-race-guide/",
        "has_rwgps": bool(race.get("course_description", {}).get("ridewithgps_id")),
    }


def build_index_entry_from_flat(race: dict) -> dict:
    """Build index entry from flat database record.

    Handles UPPER_CASE keys from the flat DB format.
    """
    name = race.get("RACE_NAME", race.get("name", ""))
    slug = slugify(name)
    location = race.get("LOCATION", race.get("location", ""))
    date_str = race.get("DATE", race.get("date", ""))

    # Parse distance from strings like "60/34/21" — take first (longest)
    distance_raw = race.get("DISTANCE", race.get("distance_miles", ""))
    distance = None
    if isinstance(distance_raw, (int, float)):
        distance = int(distance_raw)
    elif isinstance(distance_raw, str) and distance_raw:
        first = distance_raw.split("/")[0].strip()
        try:
            distance = int(re.sub(r'[^\d]', '', first))
        except ValueError:
            pass

    # Parse elevation
    elev_raw = race.get("ELEVATION_GAIN", race.get("elevation_feet", ""))
    elevation = None
    if isinstance(elev_raw, (int, float)):
        elevation = int(elev_raw)
    elif isinstance(elev_raw, str) and elev_raw:
        try:
            elevation = int(re.sub(r'[^\d]', '', elev_raw))
        except ValueError:
            pass

    return {
        "name": name,
        "slug": slug,
        "location": location,
        "region": extract_region(location),
        "month": extract_month(date_str),
        "distance_mi": distance,
        "elevation_ft": elevation,
        "tier": 3,  # Default for unresearched
        "overall_score": None,
        "scores": {},
        "tagline": "",
        "has_profile": False,
        "profile_url": None,
        "has_rwgps": False,
    }


def generate_jsonld(entry: dict, profile_data: dict = None) -> dict:
    """Generate JSON-LD Event structured data for Google Rich Results."""
    race = (profile_data or {}).get("race", {})
    vitals = race.get("vitals", {})

    # Parse date for structured data
    date_specific = vitals.get("date_specific", "")
    # Try to extract ISO date from strings like "2026: June 6"
    iso_date = None
    date_match = re.search(r'(\d{4}).*?(\w+)\s+(\d+)', date_specific)
    if date_match:
        year, month_name, day = date_match.groups()
        months = {"january": "01", "february": "02", "march": "03", "april": "04",
                  "may": "05", "june": "06", "july": "07", "august": "08",
                  "september": "09", "october": "10", "november": "11", "december": "12"}
        month_num = months.get(month_name.lower(), "01")
        iso_date = f"{year}-{month_num}-{int(day):02d}"

    # Parse price from registration string
    price = None
    reg = vitals.get("registration", "")
    price_match = re.search(r'\$(\d+)', reg)
    if price_match:
        price = price_match.group(1)

    jsonld = {
        "@context": "https://schema.org",
        "@type": "SportsEvent",
        "name": entry["name"],
        "description": entry.get("tagline", ""),
        "sport": "Gravel Cycling",
    }

    if iso_date:
        jsonld["startDate"] = iso_date

    if entry.get("location"):
        jsonld["location"] = {
            "@type": "Place",
            "name": entry["location"],
        }

    if price:
        jsonld["offers"] = {
            "@type": "Offer",
            "price": price,
            "priceCurrency": "USD",
            "availability": "https://schema.org/LimitedAvailability",
        }

    # Add aggregate rating if we have scores
    if entry.get("overall_score"):
        jsonld["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": str(entry["overall_score"]),
            "bestRating": "100",
            "ratingCount": "14",
            "name": "Gravel God Rating",
        }

    official_site = race.get("logistics", {}).get("official_site", "")
    if official_site:
        jsonld["url"] = official_site

    return jsonld


def main():
    parser = argparse.ArgumentParser(description="Generate race index for search page")
    parser.add_argument("--with-jsonld", action="store_true", help="Also generate JSON-LD per race")
    parser.add_argument("--stats", action="store_true", help="Show coverage statistics")
    parser.add_argument("--output", help="Output file (default: web/race-index.json)")
    args = parser.parse_args()

    # Load all canonical profiles
    profiles = {}
    for f in sorted(RACE_DATA.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            profiles[f.stem] = data
        except json.JSONDecodeError:
            print(f"  ⚠ Skipping invalid JSON: {f.name}")

    # Load flat DB for races without profiles
    flat_raw = json.loads(FLAT_DB.read_text()) if FLAT_DB.exists() else []
    # Handle both {"races": [...]} and [...] formats
    if isinstance(flat_raw, dict):
        flat_db = flat_raw.get("races", [])
    else:
        flat_db = flat_raw

    # Build index
    index = []
    seen_slugs = set()

    # First: add all profiled races
    for slug, data in profiles.items():
        entry = build_index_entry_from_profile(slug, data)
        index.append(entry)
        seen_slugs.add(slug)

    # Then: add flat DB races that don't have profiles
    for race in flat_db:
        slug = slugify(race.get("RACE_NAME", race.get("name", "")))
        if slug and slug not in seen_slugs:
            entry = build_index_entry_from_flat(race)
            index.append(entry)
            seen_slugs.add(slug)

    # Sort by tier (ascending) then overall_score (descending)
    index.sort(key=lambda x: (x["tier"], -(x["overall_score"] or 0)))

    if args.stats:
        print(f"\n=== RACE INDEX STATS ===\n")
        print(f"Total races:     {len(index)}")
        with_profile = sum(1 for e in index if e["has_profile"])
        print(f"With profile:    {with_profile}")
        print(f"Without profile: {len(index) - with_profile}")
        print()
        # By tier
        for t in [1, 2, 3]:
            tier_races = [e for e in index if e["tier"] == t]
            print(f"Tier {t}: {len(tier_races)} races")
        # By region
        print()
        regions = {}
        for e in index:
            r = e.get("region", "Unknown")
            regions[r] = regions.get(r, 0) + 1
        for r, count in sorted(regions.items(), key=lambda x: -x[1]):
            print(f"  {r}: {count}")
        return

    # Write index
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = Path(args.output) if args.output else OUTPUT_DIR / "race-index.json"
    output_file.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print(f"✓ Generated {output_file} ({len(index)} races)")

    # Generate JSON-LD if requested
    if args.with_jsonld:
        jsonld_dir = OUTPUT_DIR / "jsonld"
        jsonld_dir.mkdir(exist_ok=True)
        count = 0
        for entry in index:
            if entry["has_profile"]:
                profile_data = profiles.get(entry["slug"])
                jsonld = generate_jsonld(entry, profile_data)
                jsonld_file = jsonld_dir / f"{entry['slug']}.jsonld"
                jsonld_file.write_text(json.dumps(jsonld, indent=2) + "\n")
                count += 1
        print(f"✓ Generated {count} JSON-LD files in {jsonld_dir}/")


if __name__ == "__main__":
    main()
