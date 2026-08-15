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
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))


RACE_DATA = Path(__file__).parent.parent / "race-data"
FLAT_DB = Path(__file__).parent.parent / "db" / "gravel_races_full_database.json"
OUTPUT_DIR = Path(__file__).parent.parent / "web"
ROAD_MIGRATION_MAP = (
    Path(__file__).parent.parent / "docs" / "specs" / "road-migration-map.json"
)

# SITE-SYNC S3 (docs/specs/SITE_SYNC_SPEC.md): fabricated race pages removed
# 2026-07, 301-redirected to state/region best-of hubs. profiles DELETED 2026-07-22
# (research-dumps + git history are the audit trail); tombstones are canonical
# in config/tombstones.json and must never resurface in the index/sitemap/search.
TOMBSTONED_SLUGS = frozenset(
    t["slug"] for t in __import__("json").loads(
        (Path(__file__).resolve().parent.parent / "config" / "tombstones.json")
        .read_text())["tombstones"])


# Relative contribution of each physical criterion to overall difficulty.
# Distance and climbing dominate what makes a day hard; surface adds real
# cost; weather and altitude are meaningful but secondary for most races.
_DIFFICULTY_WEIGHTS = {
    "length": 0.30,
    "elevation": 0.30,
    "technicality": 0.20,
    "climate": 0.10,
    "altitude": 0.10,
}


def _difficulty_composite(scores: dict) -> float | None:
    """Weighted 1-5 difficulty from the physical criteria.

    ALL five must be scored. Renormalising over whichever happen to be present
    lets a race with only length and elevation reach 5.0 and take full "brutal"
    credit while three dimensions are unknown — a confident number built on
    missing data. Return None instead and let the quiz apply its own neutral
    default. Every currently profiled race carries all five, so this costs
    nothing today and stops a partial profile from lying later.
    """
    if any(not isinstance(scores.get(k), (int, float)) for k in _DIFFICULTY_WEIGHTS):
        return None
    return round(sum(scores[k] * w for k, w in _DIFFICULTY_WEIGHTS.items()), 2)


def _load_migrated_road_slugs() -> frozenset[str]:
    """Return GG source slugs removed by the approved road migration.

    This also prevents two legacy flat-database rows from resurfacing as
    unprofiled gravel races after their canonical road JSONs are archived.
    """
    if not ROAD_MIGRATION_MAP.exists():
        return frozenset()
    migration_map = json.loads(ROAD_MIGRATION_MAP.read_text(encoding="utf-8"))
    return frozenset(
        entry["gg"]["slug"]
        for entry in migration_map.get("entries", [])
        if entry.get("action") in {"redirect", "hub_redirect"}
    )


MIGRATED_ROAD_SLUGS = _load_migrated_road_slugs()


def load_profiles(data_dir: Path = RACE_DATA) -> dict[str, dict]:
    """Load active canonical profiles from race-data/ only (non-recursive)."""
    profiles = {}
    for path in sorted(Path(data_dir).glob("*.json")):
        if path.stem in TOMBSTONED_SLUGS | MIGRATED_ROAD_SLUGS:
            continue
        try:
            profiles[path.stem] = json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"  ⚠ Skipping invalid JSON: {path.name}")
    return profiles


def discipline_sport(discipline: str) -> str:
    """Map catalog discipline values to Schema.org SportsEvent sport labels."""
    return {
        "mtb": "Mountain Biking",
        "bikepacking": "Bikepacking",
        "gravel": "Gravel Cycling",
    }.get(discipline or "gravel", "Gravel Cycling")


def slugify(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)
    return slug


def normalize_slug(slug: str) -> str:
    """Normalize slug for fuzzy matching - removes common suffixes/prefixes."""
    s = slug.lower().strip()
    # Remove common suffixes
    for suffix in ['-gravel', '-gravel-race', '-race', '-grinder', '-fondo', '-100', '-200']:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
    # Remove common prefixes
    for prefix in ['the-']:
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s


def find_matching_profile(name: str, profiles: dict, seen_slugs: set) -> Optional[str]:
    """Try to find a matching profile using fuzzy slug matching."""
    # Exact match first
    slug = slugify(name)
    if slug in seen_slugs:
        return slug

    # Try normalized match
    normalized = normalize_slug(slug)
    for profile_slug in profiles.keys():
        if normalize_slug(profile_slug) == normalized:
            return profile_slug

    # Try common variations
    variations = [
        slug + '-gravel',
        slug + '-gravel-race',
        'the-' + slug,
        slug.replace('-gravel', ''),
        slug.replace('-race', ''),
    ]
    for var in variations:
        if var in seen_slugs:
            return var

    return None


def extract_region(location: str) -> str:
    """Extract broad region from location string."""
    if not location:
        return "Unknown"

    location_lower = location.lower()

    # International
    country_map = {
        # Europe
        "iceland": "Europe", "uk": "Europe", "england": "Europe",
        "scotland": "Europe", "wales": "Europe", "spain": "Europe",
        "italy": "Europe", "france": "Europe", "belgium": "Europe",
        "germany": "Europe", "netherlands": "Europe", "switzerland": "Europe",
        "austria": "Europe", "portugal": "Europe", "poland": "Europe",
        "czech republic": "Europe", "romania": "Europe", "slovenia": "Europe",
        "croatia": "Europe", "greece": "Europe", "denmark": "Europe",
        "norway": "Europe", "finland": "Europe", "sweden": "Europe",
        "latvia": "Europe", "luxembourg": "Europe", "monaco": "Europe",
        "ardennes": "Europe",
        "flanders": "Europe", "eifel": "Europe", "drenthe": "Europe",
        "sardinia": "Europe", "tuscany": "Europe", "veneto": "Europe",
        "catalonia": "Europe", "andalusia": "Europe", "vosges": "Europe",
        "pyrénées": "Europe", "pyrenees": "Europe", "nürburgring": "Europe",
        "europe": "Europe", "french": "Europe", "alps": "Europe",
        "global": "North America",  # Multi-location series default to NA
        # Oceania
        "australia": "Oceania", "new zealand": "Oceania",
        "queensland": "Oceania", "victoria": "Oceania", "tasmania": "Oceania",
        "new south wales": "Oceania", "western australia": "Oceania",
        "south australia": "Oceania",
        # North America
        "canada": "North America", "mexico": "North America",
        "ontario": "North America", "british columbia": "North America",
        "alberta": "North America",
        # South America
        "colombia": "South America", "argentina": "South America",
        "chile": "South America", "brazil": "South America",
        "patagonia": "South America",
        # Africa
        "south africa": "Africa", "morocco": "Africa", "kenya": "Africa",
        # Asia
        "japan": "Asia", "thailand": "Asia",
    }
    for country, region in country_map.items():
        is_short_code = len(country) <= 3 and country.isalpha()
        matches = (
            re.search(rf"(?<![a-z]){re.escape(country)}(?![a-z])", location_lower)
            if is_short_code
            else country in location_lower
        )
        if matches:
            return region

    # US regions — full state names
    us_regions = {
        "West": ["california", "oregon", "washington", "colorado", "utah",
                 "montana", "wyoming", "idaho", "nevada", "arizona", "new mexico",
                 "alaska", "hawaii"],
        "Midwest": ["kansas", "nebraska", "iowa", "illinois", "indiana", "ohio",
                    "michigan", "wisconsin", "minnesota", "missouri", "oklahoma"],
        "South": ["texas", "arkansas", "louisiana", "mississippi", "alabama",
                 "georgia", "florida", "tennessee", "kentucky", "north carolina",
                 "south carolina", "virginia", "west virginia"],
        "Northeast": ["new york", "pennsylvania", "connecticut", "massachusetts",
                     "vermont", "new hampshire", "maine", "maryland", "new jersey",
                     "delaware", "rhode island", "district of columbia", "d.c."],
    }
    for region, states in us_regions.items():
        if any(s in location_lower for s in states):
            return region

    # US state abbreviations — match ", XX" or "XX/" patterns to avoid false positives
    us_abbrev = {
        "West": ["CA", "OR", "WA", "CO", "UT", "MT", "WY", "ID", "NV", "AZ", "NM",
                 "AK", "HI"],
        "Midwest": ["KS", "NE", "IA", "IL", "IN", "OH", "MI", "WI", "MN", "MO", "OK"],
        "South": ["TX", "AR", "LA", "MS", "AL", "GA", "FL", "TN", "KY", "NC", "SC",
                  "VA", "WV"],
        "Northeast": ["NY", "PA", "CT", "MA", "VT", "NH", "ME", "MD", "NJ", "DE",
                      "RI", "DC"],
    }
    for region, abbrevs in us_abbrev.items():
        for abbr in abbrevs:
            if re.search(r'(?:,\s*|/\s*)' + abbr + r'(?:\s|$|/)', location):
                return region

    return "Other"


def extract_month(date_str: str) -> Optional[str]:
    """Extract month from date string.

    Handles exact months, season names, and numeric dates.
    Seasons map to their midpoint month.
    """
    if not date_str:
        return None
    months = ["january", "february", "march", "april", "may", "june",
              "july", "august", "september", "october", "november", "december"]
    date_lower = date_str.lower()
    for month in months:
        if month[:3] in date_lower:
            return month.capitalize()
    # Season approximations (midpoint month)
    seasons = {"spring": "April", "summer": "July", "fall": "October",
               "autumn": "October", "winter": "January"}
    for season, month in seasons.items():
        if season in date_lower:
            return month
    return None


def extract_year(vitals: dict) -> Optional[int]:
    """Extract the event year from date_specific (e.g. "2026: June 6") or date."""
    for field in ("date_specific", "date"):
        m = re.search(r"(20\d{2})", str(vitals.get(field, "") or ""))
        if m:
            return int(m.group(1))
    return None


def build_index_entry_from_profile(slug: str, data: dict) -> dict:
    """Build index entry from a canonical race JSON."""
    race = data.get("race", {})
    vitals = race.get("vitals", {})
    rating = race.get("gravel_god_rating", {})
    location = vitals.get("location", "")

    # Extract 14 base scores + cultural_impact bonus
    course_vars = ["logistics", "length", "technicality", "elevation", "climate", "altitude", "adventure"]
    editorial_vars = ["prestige", "race_quality", "experience", "community", "field_depth", "value", "expenses"]
    bonus_vars = ["cultural_impact"]
    scores = {}
    for var in course_vars + editorial_vars + bonus_vars:
        val = rating.get(var)
        if isinstance(val, (int, float)):
            scores[var] = int(val)

    # How hard the day is, 1-5, from the physical criteria only. The race
    # quiz asks "How hard do you want it?" and weights the answer higher than
    # any other question, but the field it read (difficulty_composite) was
    # never produced by anything — so every race scored 2.5 and the two
    # hardest answers matched nothing at all.
    #
    # Physical demand only: prestige, value and logistics say nothing about
    # how much the race hurts. Weights sum to 1.0 so the result stays on the
    # same 1-5 scale as its inputs.
    difficulty = _difficulty_composite(scores)


    entry = {
        "name": race.get("display_name") or race.get("name", slug),
        "slug": slug,
        "location": location,
        "region": extract_region(location),
        "month": extract_month(vitals.get("date", "")),
        "year": extract_year(vitals),
        "distance_mi": vitals.get("distance_mi"),
        "elevation_ft": vitals.get("elevation_ft"),
        "tier": rating.get("tier", 3),
        "overall_score": rating.get("overall_score"),
        "scores": scores,
        "difficulty_composite": difficulty,
        "tagline": race.get("tagline", ""),
        "has_profile": True,
        "profile_url": f"/race/{slug}/",
        "discipline": rating.get("discipline", "gravel"),
        "has_tire_guide": bool(race.get("tire_recommendations", {}).get("primary")),
    }

    # Include coordinates if available
    if vitals.get("lat") is not None and vitals.get("lng") is not None:
        entry["lat"] = vitals["lat"]
        entry["lng"] = vitals["lng"]

    # Include RWGPS route ID if available
    course = race.get("course_description", {})
    rwgps_id = course.get("ridewithgps_id")
    if rwgps_id and str(rwgps_id).strip() and str(rwgps_id).strip().lower() != "tbd":
        entry["rwgps_id"] = str(rwgps_id).strip()

    # Include racer rating fields if any ratings exist
    racer_rating = race.get("racer_rating", {})
    total = racer_rating.get("total_ratings", 0)
    if total >= 3 and racer_rating.get("would_race_again_pct") is not None:
        entry["racer_pct"] = racer_rating["would_race_again_pct"]
        entry["racer_count"] = total
    elif total > 0:
        entry["racer_pct"] = None
        entry["racer_count"] = total

    # Include series fields if race belongs to a series
    series = race.get("series", {})
    if series.get("id"):
        entry["series_id"] = series["id"]
        entry["series_name"] = series.get("name", "")

    # Include transcript search text from rider_intel or fallback to curated quotes
    yt = race.get("youtube_data") or {}
    rider_intel = yt.get("rider_intel", {})
    search_text = rider_intel.get("search_text", "")
    if not search_text:
        # Fallback: concatenate curated quote text
        curated_quotes = [q.get("text", "") for q in yt.get("quotes", []) if q.get("curated")]
        search_text = " ".join(curated_quotes)
    if search_text:
        entry["st"] = search_text

    # Thumbnail: primary photo URL for search UI visual previews
    photos = race.get("photos", [])
    for p in photos:
        if p.get("primary") and p.get("url") and not p.get("gif"):
            entry["thumb"] = p["url"]
            break

    return entry


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
        "year": None,
        "distance_mi": distance,
        "elevation_ft": elevation,
        "tier": int(race.get("TIER", 3)) if str(race.get("TIER", "3")).isdigit() else 3,
        "overall_score": None,
        "scores": {},
        "tagline": "",
        "has_profile": False,
        "profile_url": None,
        "has_rwgps": False,
        "discipline": "gravel",
        "has_tire_guide": False,
    }


def generate_jsonld(entry: dict, profile_data: dict = None) -> dict:
    """Generate JSON-LD Event structured data for Google Rich Results."""
    race = (profile_data or {}).get("race", {})
    vitals = race.get("vitals", {})

    # Parse date for structured data
    # Source-blocked profiles retain the last confirmed date as research
    # evidence. It is historical, not a scheduled next edition, so never
    # publish it as the structured event date.
    date_specific = (
        ""
        if vitals.get("course_status") == "source_blocked"
        else vitals.get("date_specific", "")
    )
    # Only accept the canonical year-first date form.  Status prose can contain
    # several years and unrelated numbers (for example, "Cancelled for 2026 ...
    # no 2027 date") and must never be promoted to a fabricated event date.
    iso_date = None
    month_names = (
        "January|February|March|April|May|June|July|August|September|October|"
        "November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
    )
    weekdays = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
    date_match = re.match(
        rf'^\s*(\d{{4}}):\s*(?:(?:{weekdays}),?\s+)?'
        rf'({month_names})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b',
        date_specific,
        flags=re.IGNORECASE,
    )
    if date_match:
        year, month_name, day = date_match.groups()
        months = {"january": "01", "february": "02", "march": "03", "april": "04",
                  "may": "05", "june": "06", "july": "07", "august": "08",
                  "september": "09", "october": "10", "november": "11", "december": "12",
                  "jan": "01", "feb": "02", "mar": "03", "apr": "04",
                  "jun": "06", "jul": "07", "aug": "08", "sep": "09",
                  "sept": "09", "oct": "10", "nov": "11", "dec": "12"}
        month_num = months[month_name.lower()]
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
        "sport": discipline_sport(entry.get("discipline", "gravel")),
    }

    if iso_date:
        jsonld["startDate"] = iso_date

    break_note = race.get("taking_a_break") or {}
    status_text = f'{date_specific} {break_note.get("label", "")}'.lower()
    if "cancel" in status_text:
        jsonld["eventStatus"] = "https://schema.org/EventCancelled"
    elif break_note:
        jsonld["eventStatus"] = "https://schema.org/EventPostponed"

    if entry.get("location"):
        loc = entry["location"]
        parts = [p.strip() for p in loc.split(",")]
        place = {"@type": "Place", "name": loc}
        if len(parts) >= 2:
            place["address"] = {
                "@type": "PostalAddress",
                "addressLocality": parts[0],
                "addressRegion": parts[1] if len(parts) > 2 else parts[-1],
            }
        else:
            place["address"] = {
                "@type": "PostalAddress",
                "addressLocality": parts[0],
            }
        jsonld["location"] = place

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
    if official_site and official_site.startswith("http"):
        jsonld["url"] = official_site

    # Organizer from history.founder — skip generic placeholders
    founder = race.get("history", {}).get("founder", "")
    if founder and not founder.endswith("organizers") and founder != "Unknown":
        org = {"@type": "Person", "name": founder}
        if official_site and official_site.startswith("http"):
            org["url"] = official_site
        jsonld["organizer"] = org

    return jsonld


def main():
    parser = argparse.ArgumentParser(description="Generate race index for search page")
    parser.add_argument("--with-jsonld", action="store_true", help="Also generate JSON-LD per race")
    parser.add_argument("--stats", action="store_true", help="Show coverage statistics")
    parser.add_argument("--output", help="Output file (default: web/race-index.json)")
    args = parser.parse_args()

    # Load all canonical profiles
    profiles = load_profiles()

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
    # Use fuzzy matching to avoid duplicates
    for race in flat_db:
        name = race.get("RACE_NAME", race.get("name", ""))
        slug = slugify(name)

        # The flat database is an older discovery source. Without applying the
        # same tombstone boundary here, deleting an invalid canonical profile
        # merely resurrects it as an unprofiled catalog row.
        if slug in TOMBSTONED_SLUGS | MIGRATED_ROAD_SLUGS:
            continue

        # Try to find a matching profile with fuzzy matching
        matched = find_matching_profile(name, profiles, seen_slugs)
        if matched:
            # Already have this race, skip
            continue

        if slug and slug not in seen_slugs:
            entry = build_index_entry_from_flat(race)
            index.append(entry)
            seen_slugs.add(slug)

    # Sort by tier (ascending) then overall_score (descending)
    index.sort(key=lambda x: (x["tier"], -(x["overall_score"] or 0)))

    # Write index
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = Path(args.output) if args.output else OUTPUT_DIR / "race-index.json"
    output_file.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print(f"✓ Generated {output_file} ({len(index)} races)")

    # Generate JSON-LD if requested
    if args.with_jsonld:
        jsonld_dir = OUTPUT_DIR / "jsonld"
        jsonld_dir.mkdir(exist_ok=True)
        expected_jsonld_names = {
            f"{entry['slug']}.jsonld"
            for entry in index
            if entry["has_profile"]
        }
        for stale_path in jsonld_dir.glob("*.jsonld"):
            if stale_path.name not in expected_jsonld_names:
                stale_path.unlink()
        count = 0
        for entry in index:
            if entry["has_profile"]:
                profile_data = profiles.get(entry["slug"])
                jsonld = generate_jsonld(entry, profile_data)
                jsonld_file = jsonld_dir / f"{entry['slug']}.jsonld"
                jsonld_file.write_text(json.dumps(jsonld, indent=2) + "\n")
                count += 1
        print(f"✓ Generated {count} JSON-LD files in {jsonld_dir}/")

    # Show stats if requested
    if args.stats:
        print(f"\n=== RACE INDEX STATS ===\n")
        print(f"Total races:     {len(index)}")
        with_profile = sum(1 for e in index if e["has_profile"])
        print(f"With profile:    {with_profile}")
        print(f"Without profile: {len(index) - with_profile}")
        print()
        for t in [1, 2, 3, 4]:
            tier_races = [e for e in index if e["tier"] == t]
            print(f"Tier {t}: {len(tier_races)} races")
        print()
        regions = {}
        for e in index:
            r = e.get("region", "Unknown")
            regions[r] = regions.get(r, 0) + 1
        for r, count in sorted(regions.items(), key=lambda x: -x[1]):
            print(f"  {r}: {count}")


if __name__ == "__main__":
    main()
