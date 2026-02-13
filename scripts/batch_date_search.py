#!/usr/bin/env python3
"""
batch_date_search.py — Web-search for 2026 dates for races with stale (pre-2026) dates.

Searches DuckDuckGo for each stale race's 2026 date, parses results for date
patterns, and opportunistically captures official website URLs.

Usage:
  python scripts/batch_date_search.py --dry-run              # Preview all
  python scripts/batch_date_search.py --tier 1 --tier 2      # T1+T2 only
  python scripts/batch_date_search.py --slug jeroboam        # Single race
  python scripts/batch_date_search.py --verbose               # Show search details
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from ddgs import DDGS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_ABBR = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April",
    "may": "May", "jun": "June", "jul": "July", "aug": "August",
    "sep": "September", "oct": "October", "nov": "November", "dec": "December",
}
# Match both full and abbreviated month names
MONTH_PATTERN = "|".join(MONTHS) + "|" + "|".join(
    f"{a}(?:\\.)?" for a in ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
)


def normalize_month(text):
    """Convert month name/abbreviation to canonical full name."""
    t = text.strip().rstrip(".").lower()
    if t in {m.lower() for m in MONTHS}:
        return text.strip().rstrip(".").title()
    if t[:3] in MONTH_ABBR:
        return MONTH_ABBR[t[:3]]
    return None


def timing_label(month, day):
    """Generate a timing label like 'Mid-July annually'."""
    if day <= 10:
        prefix = "Early"
    elif day <= 20:
        prefix = "Mid-"
    else:
        prefix = "Late"
    if prefix == "Mid-":
        return f"Mid-{month} annually"
    return f"{prefix} {month} annually"


# ---------------------------------------------------------------------------
# Website extraction from search results
# ---------------------------------------------------------------------------

NON_OFFICIAL_DOMAINS = {
    "bikereg.com", "eventbrite.com", "google.com", "google.co.uk",
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "reddit.com", "redd.it",
    "strava.com", "ridewithgps.com", "trainerroad.com",
    "velonews.com", "cyclingtips.com", "bikeradar.com",
    "gravelcyclist.com", "cxmagazine.com", "gearjunkie.com",
    "cyclingweekly.com", "outsideonline.com", "velo.outsideonline.com",
    "wikipedia.org", "en.wikipedia.org",
    "trackleaders.com", "dotwatcher.cc",
    "ridinggravel.com", "gravelgodcycling.com",
    "bit.ly", "t.co", "tinyurl.com", "goo.gl",
    "amazon.com", "amzn.to", "wordpress.com", "wordpress.org",
    "maps.google.com", "maps.app.goo.gl",
    "web.archive.org", "schema.org", "w3.org",
    "granfondoguide.com", "bikepacking.com",
    "usacycling.org",
    "duckduckgo.com",
    # Aggregator / calendar sites (not the race's own site)
    "findarace.com", "battistrada.com", "en.3bikes.fr",
    "firstcycling.com", "procyclingstats.com",
    "ahotu.com", "cycloworld.cc", "strambecco.com",
    "dirtyfreehub.org", "gravelup.earth",
    # Government / unrelated
    "iowadot.gov", "wyo.gov",
}


def is_official_url(url):
    """Check if a URL looks like an official race website."""
    if not url or not url.startswith("http"):
        return False
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return False
    for d in NON_OFFICIAL_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return False
    return True


def needs_website(race):
    """Check if logistics.official_site needs filling."""
    site = race.get("logistics", {}).get("official_site", "")
    if not site:
        return True
    if site.startswith("http"):
        return False
    return True


# ---------------------------------------------------------------------------
# Date parsing from search result snippets
# ---------------------------------------------------------------------------

def extract_date_from_text(text):
    """Extract a 2026 date from search result text.

    Returns (date_specific, month, day) or (None, None, None).
    """
    candidates = []

    # Pattern 1: "Month DD, 2026" or "Month DD-DD, 2026"
    p1 = re.finditer(
        rf'({MONTH_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?'
        r'(?:\s*[-–]\s*(\d{1,2})(?:st|nd|rd|th)?)?,?\s*2026',
        text, re.IGNORECASE
    )
    for m in p1:
        month = normalize_month(m.group(1))
        if not month:
            continue
        day = int(m.group(2))
        day_end = m.group(3)
        if 1 <= day <= 31:
            if day_end:
                candidates.append((month, day, int(day_end), m.start()))
            else:
                candidates.append((month, day, None, m.start()))

    # Pattern 2: "DD Month 2026" or "DD-DD Month 2026" (European format)
    p2 = re.finditer(
        rf'(\d{{1,2}})(?:st|nd|rd|th)?\s*[-–]?\s*(?:(\d{{1,2}})(?:st|nd|rd|th)?\s+)?'
        rf'({MONTH_PATTERN}),?\s*2026',
        text, re.IGNORECASE
    )
    for m in p2:
        day = int(m.group(1))
        day_end = m.group(2)
        month = normalize_month(m.group(3))
        if not month:
            continue
        if 1 <= day <= 31:
            if day_end:
                candidates.append((month, day, int(day_end), m.start()))
            else:
                candidates.append((month, day, None, m.start()))

    # Pattern 3: "2026-MM-DD" ISO format
    p3 = re.finditer(r'2026-(\d{2})-(\d{2})', text)
    for m in p3:
        month_num = int(m.group(1))
        day = int(m.group(2))
        if 1 <= month_num <= 12 and 1 <= day <= 31:
            month = MONTHS[month_num - 1]
            candidates.append((month, day, None, m.start()))

    # Pattern 4: "May 29 - May 31, 2026" cross-day range with month repeated
    p4 = re.finditer(
        rf'({MONTH_PATTERN})\s+(\d{{1,2}})\s*[-–]\s*(?:{MONTH_PATTERN})\s+(\d{{1,2}}),?\s*2026',
        text, re.IGNORECASE
    )
    for m in p4:
        month = normalize_month(m.group(1))
        if not month:
            continue
        day = int(m.group(2))
        day_end = int(m.group(3))
        if 1 <= day <= 31:
            candidates.append((month, day, day_end, m.start()))

    if not candidates:
        return None, None, None

    # Take the first candidate (search results are relevance-ordered)
    month, day, day_end, _ = candidates[0]
    if day_end:
        date_spec = f"2026: {month} {day}-{day_end}"
    else:
        date_spec = f"2026: {month} {day}"

    return date_spec, month, day


def build_search_queries(race, slug):
    """Build search queries for a race's 2026 date (primary + fallback)."""
    display_name = race.get("display_name", race.get("name", ""))
    location = race.get("vitals", {}).get("location", "")

    queries = []

    # Primary: race name + 2026 + gravel/cycling context
    queries.append(f'{display_name} 2026 gravel race date')

    # Fallback 1: quoted name + 2026
    queries.append(f'"{display_name}" 2026')

    # Fallback 2: with location context
    if location:
        parts = [p.strip() for p in location.split(",")]
        loc_suffix = parts[-1].strip() if parts else ""
        if loc_suffix:
            queries.append(f'{display_name} 2026 cycling {loc_suffix}')

    return queries


# ---------------------------------------------------------------------------
# Search with retry
# ---------------------------------------------------------------------------

def ddgs_search(query, max_results=8, retries=2):
    """Search DuckDuckGo with retry for transient TLS errors."""
    for attempt in range(retries + 1):
        try:
            return list(DDGS().text(query, max_results=max_results))
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
                continue
            raise


def _result_mentions_race(result, display_name, slug):
    """Check if a search result actually mentions this race."""
    text = f"{result.get('title', '')} {result.get('body', '')}".lower()
    name_lower = display_name.lower()

    # Direct name match
    if name_lower in text:
        return True

    # Slug-based match (e.g. "almanzo" in text for "almanzo-100")
    slug_words = [w for w in slug.split("-") if len(w) > 3]
    if slug_words and all(w in text for w in slug_words):
        return True

    # Match on significant words from display name (skip short words)
    name_words = [w.lower() for w in display_name.split() if len(w) > 3]
    if name_words and all(w in text for w in name_words):
        return True

    return False


def search_race_date(race, slug, verbose=False):
    """Search for a race's 2026 date and official website.

    Returns (date_specific, date_general, website_url).
    """
    display_name = race.get("display_name", race.get("name", ""))
    queries = build_search_queries(race, slug)
    all_results = []
    date_spec = None
    month = None
    day = None

    for qi, query in enumerate(queries):
        if verbose:
            print(f"  SEARCH[{qi+1}]: {query}")

        try:
            results = ddgs_search(query, max_results=8)
        except Exception as e:
            if verbose:
                print(f"  ERROR: Search failed for {slug}: {e}")
            continue

        if not results:
            if verbose:
                print(f"  NO RESULTS")
            continue

        if verbose:
            for i, r in enumerate(results[:3]):
                mentions = _result_mentions_race(r, display_name, slug)
                marker = "✓" if mentions else " "
                print(f"    [{i+1}]{marker} {r.get('title', '')[:80]}")
                print(f"        {r.get('body', '')[:120]}")
                print(f"        {r.get('href', '')}")

        all_results.extend(results)

        # Only extract dates from results that actually mention this race
        relevant_text = ""
        for r in all_results:
            if _result_mentions_race(r, display_name, slug):
                relevant_text += f" {r.get('title', '')} {r.get('body', '')}"

        if relevant_text.strip():
            date_spec, month, day = extract_date_from_text(relevant_text)

        if date_spec:
            break

        if qi < len(queries) - 1:
            time.sleep(1)

    date_general = None
    date_month = month  # preserve for caller
    if date_spec and month and day:
        date_general = timing_label(month, day)

    # Look for official website URL in results
    website = None
    if needs_website(race) and all_results:
        slug_parts = slug.replace("-", " ").split()

        for r in all_results:
            if not _result_mentions_race(r, display_name, slug):
                continue

            url = r.get("href", "")
            if not is_official_url(url):
                continue

            try:
                domain = urlparse(url).netloc.lower().replace("www.", "")
            except Exception:
                continue

            title = r.get("title", "").lower()

            # Strong signal: domain contains slug parts or race name words
            # Require length >= 5 to avoid false matches (e.g. "zero" in "zeromobiles")
            name_words = [w for w in display_name.lower().split() if len(w) >= 5]
            domain_match = any(part in domain for part in slug_parts if len(part) >= 5)
            title_match = any(w in title for w in name_words)

            if domain_match:
                website = url
                if verbose:
                    print(f"  WEBSITE: {website}")
                break

            path = urlparse(url).path.lower()
            if (path == "/" or path == "") and title_match:
                website = url
                if verbose:
                    print(f"  WEBSITE (likely): {website}")
                break

    return date_spec, date_general, date_month, website


def _month_num(month_name):
    """Convert month name to 1-12 number."""
    try:
        return MONTHS.index(month_name) + 1
    except ValueError:
        return None


def _month_distance(m1, m2):
    """Minimum circular distance between two months (0-6)."""
    if m1 is None or m2 is None:
        return 0
    diff = abs(m1 - m2)
    return min(diff, 12 - diff)


def _extract_month_from_date_specific(ds):
    """Extract month number from a date_specific string like '2025: July 10'."""
    if not ds:
        return None
    for i, m in enumerate(MONTHS):
        if m in str(ds):
            return i + 1
    return None


def load_stale_races(tier_filters=None, slug_filter=None):
    """Load races with stale (pre-2026) dates."""
    stale = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        slug = f.stem
        if slug_filter and slug != slug_filter:
            continue

        data = json.loads(f.read_text())
        race = data.get("race", data)
        ds = race.get("vitals", {}).get("date_specific", "")

        if not ds:
            continue
        m = re.match(r"(\d{4})", str(ds))
        if not m or int(m.group(1)) >= 2026:
            continue

        tier = race.get("gravel_god_rating", {}).get("tier") or \
               race.get("gravel_god_rating", {}).get("display_tier")

        if tier_filters and tier not in tier_filters:
            continue

        stale.append((slug, f, data, tier))

    return stale


def main():
    parser = argparse.ArgumentParser(
        description="Web-search for 2026 dates for stale races"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing")
    parser.add_argument("--tier", type=int, action="append", dest="tiers",
                        help="Only process races of this tier (repeatable)")
    parser.add_argument("--slug", help="Process single race by slug")
    parser.add_argument("--verbose", action="store_true",
                        help="Show search details")
    parser.add_argument("--delay", type=float, default=2.5,
                        help="Delay between races in seconds (default: 2.5)")
    args = parser.parse_args()

    tier_filters = set(args.tiers) if args.tiers else None
    stale = load_stale_races(tier_filters=tier_filters, slug_filter=args.slug)

    if not stale:
        print("No stale races found matching filters.")
        return 0

    tier_label = f" (tiers {sorted(tier_filters)})" if tier_filters else ""
    print(f"Found {len(stale)} stale races{tier_label}")
    print()

    date_found = 0
    date_not_found = 0
    website_found = 0

    for i, (slug, path, data, tier) in enumerate(stale):
        race = data.get("race", data)
        old_ds = race.get("vitals", {}).get("date_specific", "")
        display_name = race.get("display_name", slug)

        print(f"[{i+1}/{len(stale)}] T{tier} {slug} (current: {old_ds})")

        date_spec, date_general, month, website = search_race_date(
            race, slug, verbose=args.verbose
        )

        if date_spec:
            # Sanity check: reject dates that shift more than 2 months
            old_month = _extract_month_from_date_specific(old_ds)
            new_month = _month_num(month) if month else None
            shift = _month_distance(old_month, new_month)

            if shift > 2:
                print(f"  REJECTED date: {old_ds!r} -> {date_spec!r} (month shift={shift}, likely wrong)")
                date_spec = None
                date_general = None
                date_not_found += 1
            else:
                date_found += 1
                old_date = race.get("vitals", {}).get("date", "")

                if args.dry_run:
                    print(f"  WOULD UPDATE date: {old_ds!r} -> {date_spec!r}")
                    print(f"                     {old_date!r} -> {date_general!r}")
                else:
                    race["vitals"]["date_specific"] = date_spec
                    if date_general:
                        race["vitals"]["date"] = date_general
        else:
            date_not_found += 1
            print(f"  NO 2026 DATE FOUND")

        if website:
            website_found += 1
            old_site = race.get("logistics", {}).get("official_site", "")
            if args.dry_run:
                print(f"  WOULD UPDATE website: {old_site!r} -> {website!r}")
            else:
                if "logistics" not in race:
                    race["logistics"] = {}
                race["logistics"]["official_site"] = website

        # Write updated JSON
        if not args.dry_run and (date_spec or website):
            data["race"] = race
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

        # Rate limiting between races
        if i < len(stale) - 1:
            time.sleep(args.delay)

    print()
    print(f"Results:")
    print(f"  Dates found:    {date_found}/{len(stale)}")
    print(f"  Dates missing:  {date_not_found}/{len(stale)}")
    print(f"  Websites found: {website_found}")

    if args.dry_run:
        print("\n(Dry run — no files were modified)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
