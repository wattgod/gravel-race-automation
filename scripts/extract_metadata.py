#!/usr/bin/env python3
"""
extract_metadata.py — Extract websites, founders, and prices from research dumps.

Reads research-dumps/<slug>-raw.md (and .bak.md) files and extracts:
  - Official website URLs → logistics.official_site
  - Founder/organizer names → history.founder
  - Entry fee/price data → vitals.registration

Only fills gaps — never overwrites existing good data.

Usage:
  python scripts/extract_metadata.py --all --dry-run   # Preview all
  python scripts/extract_metadata.py --all --verbose    # Apply all
  python scripts/extract_metadata.py --websites         # Websites only
  python scripts/extract_metadata.py --founders         # Founders only
  python scripts/extract_metadata.py --prices           # Prices only
  python scripts/extract_metadata.py --slug mid-south   # Single race
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
RESEARCH_DIR = PROJECT_ROOT / "research-dumps"

# ---------------------------------------------------------------------------
# Website extraction
# ---------------------------------------------------------------------------

# Domains that are NOT official race websites
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
    "usacycling.org", "seaotterclassic.com",
    "strambecco.com",
}


def _is_official_url(url: str) -> bool:
    """Check if a URL looks like an official race website."""
    if not url.startswith("http"):
        return False
    try:
        domain = urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return False
    # Reject known non-official domains
    for d in NON_OFFICIAL_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return False
    return True


def _extract_url_from_text(text: str) -> str:
    """Extract a URL from text that may contain markdown links."""
    # Markdown link: [text](url)
    md = re.search(r'\[.*?\]\((https?://[^\s\)]+)\)', text)
    if md:
        return md.group(1).rstrip(".,;:!?")
    # Bare URL
    bare = re.search(r'(https?://[^\s\)\]\>,|]+)', text)
    if bare:
        return bare.group(1).rstrip(".,;:!?*_")
    return ""


def extract_website(dump_text: str, slug: str, verbose: bool = False) -> str:
    """Extract official website URL from research dump.

    Patterns (priority order):
    1. Markdown table: | **Official Website** | url |
    2. Inline bold: **Website:** url
    3. Plain: Website: url
    """
    # Strip bold markers for easier matching
    text = dump_text

    # Pattern 1: Markdown table row with Official Website / Website
    # Handles: | **Official Website** | https://... | or | **Website** | [text](url) |
    p1 = re.finditer(
        r'\|\s*\*?\*?(?:Official\s+)?Website\*?\*?\s*\|\s*(.+?)\s*\|',
        text, re.IGNORECASE
    )
    for m in p1:
        url = _extract_url_from_text(m.group(1))
        if url and _is_official_url(url):
            if verbose:
                print(f"  [W-P1] {slug}: {url}")
            return url

    # Pattern 2: Inline bold: **Official Website:** url or **Website:** url
    p2 = re.finditer(
        r'\*\*(?:Official\s+)?Website:?\*\*:?\s*(.+)',
        text, re.IGNORECASE
    )
    for m in p2:
        url = _extract_url_from_text(m.group(1))
        if url and _is_official_url(url):
            if verbose:
                print(f"  [W-P2] {slug}: {url}")
            return url

    # Pattern 3: Plain "Official Website:" or "Official Site:" on a line
    # Require "Official" prefix to avoid matching lodging/hotel "Website:" lines
    p3 = re.finditer(
        r'Official\s+(?:Website|Site)\s*:\s*(.+)',
        text, re.IGNORECASE
    )
    for m in p3:
        url = _extract_url_from_text(m.group(1))
        if url and _is_official_url(url):
            if verbose:
                print(f"  [W-P3] {slug}: {url}")
            return url

    # Pattern 4: Table row **Race Name** [Official] (url) — older bak format
    p4 = re.finditer(
        r'\[Official\]\s*\((https?://[^\s\)]+)\)',
        text, re.IGNORECASE
    )
    for m in p4:
        url = m.group(1).rstrip(".,;:!?")
        if _is_official_url(url):
            if verbose:
                print(f"  [W-P4] {slug}: {url}")
            return url

    return ""


# ---------------------------------------------------------------------------
# Founder extraction
# ---------------------------------------------------------------------------

# Patterns that indicate placeholder founder data
FOUNDER_PLACEHOLDERS = re.compile(
    r'^(unknown|unavailable|tbd|n/?a|not specified|not found|not available|'
    r'race\s+director|'  # bare "race director" without a name
    r'.*\borganizers?\b|.*\borganisation\b|.*\borganization\b|'
    r'.*\bseries expansion\b|'
    r'(?:local\s+)?\w+\s+cycling$'  # "USA Cycling" but not "Monuments of Cycling"
    r')',
    re.IGNORECASE,
)


def _clean_founder(raw: str) -> str:
    """Clean a founder name string.

    - Strip citation references like [1][4]
    - Strip pipe characters and markdown bold
    - Extract person name from org parenthetical: "Org (Person Name, Role)" → "Person Name"
    - Strip roles after comma: "Todd Sadow, Founder & President" → "Todd Sadow"
    - Strip leading phrases: "The race is organized by", "by"
    - Truncate at semicolons (take first entity)
    - Strip leading/trailing whitespace and punctuation
    """
    if not raw:
        return ""

    # Strip citation refs [1][4] etc.
    name = re.sub(r'\[\d+\]', '', raw).strip()

    # Strip markdown bold and pipe characters
    name = name.replace("**", "").replace("|", "").strip()

    # Strip leading list markers and narrative phrases
    name = re.sub(r'^[-•]\s*', '', name).strip()
    name = re.sub(
        r'^(?:The\s+race\s+is\s+)?(?:organized|organised|founded|created|hosted)(?:/hosted)?\s+(?:and\s+hosted\s+)?by\s+',
        '', name, flags=re.IGNORECASE
    ).strip()
    name = re.sub(
        r'^(?:accomplished\s+cyclist|professional\s+cyclist|noted\s+cyclist|cyclist)\s+',
        '', name, flags=re.IGNORECASE
    ).strip()

    # Take first entity before semicolons (multi-org lists)
    if ";" in name:
        name = name.split(";")[0].strip()

    # Truncate at common continuation phrases
    # Truncate at common continuation phrases (run iteratively)
    truncation_phrases = [
        " and his crew", " and their crew", " and her crew",
        " as part of", " eligible for", " with website",
        " on equestrian", " per rider", '" per rider',
        ", primarily the", ", also known as",
    ]
    changed = True
    while changed:
        changed = False
        for phrase in truncation_phrases:
            idx = name.lower().find(phrase.lower())
            if idx > 0:
                name = name[:idx].strip()
                changed = True
                break

    # Check for person in parenthetical: "Org (Person Name, Role)"
    paren = re.search(r'\(([A-Z][a-z]+ [A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s*(?:,.*?)?\)', name)
    if paren:
        name = paren.group(1)
    else:
        # Strip trailing role descriptions: "Todd Sadow, Founder & President"
        # But only if the part before the comma looks like a person name
        comma_parts = name.split(",", 1)
        if len(comma_parts) == 2:
            before = comma_parts[0].strip()
            after = comma_parts[1].strip().lower()
            role_words = {"founder", "president", "director", "ceo", "owner", "organizer", "creator"}
            if any(w in after for w in role_words) and re.match(r'^[A-Z][a-z]+\s+[A-Z]', before):
                name = before

    # Strip leading "by " or "By "
    name = re.sub(r'^[Bb]y\s+', '', name).strip()

    # Strip trailing punctuation and parenthetical fragments
    name = re.sub(r'\s*\([^)]*$', '', name)  # Unclosed parens: "Stefan Griebel (Boulder"
    # Strip verbose parentheticals (>30 chars, likely descriptions not names)
    name = re.sub(r'\s*\([^)]{30,}\)', '', name).strip()
    name = name.rstrip('.,;:!?"\'')  # Include quotes in trailing strip

    # Reject single-word first names (too ambiguous)
    if name and " " not in name and len(name) < 15:
        return ""

    # Reject if too long (>60 chars) — likely captured too much context
    if len(name) > 60:
        # Try to truncate at a natural break
        for sep in [",", " - ", " – "]:
            if sep in name:
                name = name.split(sep)[0].strip()
                break
        if len(name) > 60:
            return ""

    return name


def extract_founder(dump_text: str, slug: str, verbose: bool = False) -> str:
    """Extract founder/organizer name from research dump.

    Patterns (priority order):
    1. Table: | **Founder** | name | or | **Race Director/Founder** | name |
    2. Table: | **Organizer** | Org (Person Name) |
    3. Inline: **Founder:** Name
    4. Narrative: founded by **Name** or founded ... by **Name**
    5. Race director: race director **Name**
    6. Race history section: Founded ... by Name
    """
    text = dump_text

    # Pattern 1: Table row with Founder / Race Director/Founder
    p1 = re.finditer(
        r'\|\s*\*?\*?(?:Race\s+)?(?:Director/?)?Founder\*?\*?\s*\|\s*(.+?)\s*\|',
        text, re.IGNORECASE
    )
    for m in p1:
        name = _clean_founder(m.group(1))
        if name and not FOUNDER_PLACEHOLDERS.match(name):
            if verbose:
                print(f"  [F-P1] {slug}: {name}")
            return name

    # Pattern 2: Table row with Organizer — extract person if available
    p2 = re.finditer(
        r'\|\s*\*?\*?Organizer\*?\*?\s*\|\s*(.+?)\s*\|',
        text, re.IGNORECASE
    )
    for m in p2:
        raw = m.group(1).strip()
        name = _clean_founder(raw)
        if name and not FOUNDER_PLACEHOLDERS.match(name):
            if verbose:
                print(f"  [F-P2] {slug}: {name}")
            return name

    # Pattern 3: Inline bold **Founder:** Name or **Organizer:** Name
    # Requires colon or text on the same line (excludes standalone headers)
    p3 = re.finditer(
        r'\*\*(?:Founder|Organizer|Organized by|Founded by):?\*\*:?\s+(\S.+)',
        text, re.IGNORECASE
    )
    for m in p3:
        raw = m.group(1).split('.')[0]  # Take first sentence
        # Skip if it's just a table fragment or pipe-separated
        if '|' in raw:
            continue
        name = _clean_founder(raw)
        if name and not FOUNDER_PLACEHOLDERS.match(name):
            if verbose:
                print(f"  [F-P3] {slug}: {name}")
            return name

    # Pattern 4: Narrative "founded by **Name**" or "founded ... by Name"
    p4 = re.finditer(
        r'founded\s+(?:in\s+\d{4}\s+)?(?:informally\s+)?by\s+\*?\*?([A-Z][^*\n.;]{2,60})\*?\*?',
        text, re.IGNORECASE
    )
    for m in p4:
        name = _clean_founder(m.group(1))
        if name and not FOUNDER_PLACEHOLDERS.match(name):
            if verbose:
                print(f"  [F-P4] {slug}: {name}")
            return name

    # Pattern 5: "race director **Name**" or "Race Director: Name"
    p5 = re.finditer(
        r'[Rr]ace\s+[Dd]irector:?\s+\*?\*?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\*?\*?',
        text,
    )
    for m in p5:
        name = _clean_founder(m.group(1))
        if name and not FOUNDER_PLACEHOLDERS.match(name):
            if verbose:
                print(f"  [F-P5] {slug}: {name}")
            return name

    # Pattern 6: Race history section: "Founded YEAR ... by Name" within a line
    p6 = re.finditer(
        r'[Ff]ounded\s+(?:\d{4}[-–]\d{4}\s+)?by\s+([A-Z][^;\n]{2,50}?)(?:\s+(?:as|in|from|who)\b|[;.\n])',
        text,
    )
    for m in p6:
        name = _clean_founder(m.group(1))
        if name and not FOUNDER_PLACEHOLDERS.match(name):
            if verbose:
                print(f"  [F-P6] {slug}: {name}")
            return name

    # Pattern 7: "Organized by **Name**" in narrative
    p7 = re.finditer(
        r'[Oo]rganized\s+by\s+\*?\*?([A-Z][^*\n.;]{2,60})\*?\*?',
        text,
    )
    for m in p7:
        name = _clean_founder(m.group(1))
        if name and not FOUNDER_PLACEHOLDERS.match(name):
            if verbose:
                print(f"  [F-P7] {slug}: {name}")
            return name

    # Pattern 8: "Creator Name" in narrative
    p8 = re.finditer(
        r'[Cc]reator\s+\*?\*?([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\*?\*?',
        text,
    )
    for m in p8:
        name = _clean_founder(m.group(1))
        if name and not FOUNDER_PLACEHOLDERS.match(name):
            if verbose:
                print(f"  [F-P8] {slug}: {name}")
            return name

    return ""


# ---------------------------------------------------------------------------
# Price extraction
# ---------------------------------------------------------------------------

# Regex for currency amounts: $200, €100, £150, 200 EUR, 150 GBP
PRICE_RE = re.compile(
    r'(?:[\$€£]\s*\d[\d,]*(?:\s*[-–]\s*[\$€£]?\s*\d[\d,]*)?'
    r'|\d[\d,]+\s*(?:EUR|GBP|USD|CAD|AUD|SEK|NOK|DKK|CHF))',
    re.IGNORECASE,
)

# Detect FREE races
FREE_RE = re.compile(r'\bFREE\b|\$\s*0\b', re.IGNORECASE)


def extract_price(dump_text: str, slug: str, verbose: bool = False) -> str:
    """Extract entry fee / price from research dump.

    Patterns:
    1. Table: | **Entry Fee(s)** | $345 |
    2. Inline: Registration cost / entry fees: $200-$275
    3. Free detection: FREE, $0
    """
    text = dump_text

    # Pattern 1: Table row with Entry Fee / Entry Fees / Registration Fee
    p1 = re.finditer(
        r'\|\s*\*?\*?(?:Entry\s+)?(?:Fee|Fees|Registration\s+Fee)s?(?:\s*\([^)]*\))?\*?\*?\s*\|\s*(.+?)\s*\|',
        text, re.IGNORECASE
    )
    for m in p1:
        cell = m.group(1).strip()
        # Check for FREE
        if FREE_RE.search(cell):
            if verbose:
                print(f"  [P-P1] {slug}: FREE")
            return "FREE"
        # Skip cells where "Tiered pricing" is the main info and only a
        # kids/add-on price is specified (no real adult price available)
        if re.search(r'[Tt]iered\s+pricing', cell):
            # Only accept if there's a price that's not clearly a kids/add-on
            non_kid_prices = re.sub(r"[Kk]ids?'?\s*.*?[:]\s*\$\d+", "", cell)
            prices = PRICE_RE.findall(non_kid_prices)
        else:
            prices = PRICE_RE.findall(cell)
        if prices:
            result = _format_price(prices, cell)
            if verbose:
                print(f"  [P-P1] {slug}: {result}")
            return result

    # Pattern 2: Inline "Registration cost / entry fees:" or "Cost:"
    p2 = re.finditer(
        r'(?:Registration\s+cost|Entry\s+fees?|Cost)\s*[:/]\s*(.+?)(?:\n|$)',
        text, re.IGNORECASE
    )
    for m in p2:
        line = m.group(1).strip()
        if FREE_RE.search(line):
            if verbose:
                print(f"  [P-P2] {slug}: FREE")
            return "FREE"
        prices = PRICE_RE.findall(line)
        if prices:
            result = _format_price(prices, line)
            if verbose:
                print(f"  [P-P2] {slug}: {result}")
            return result

    # Pattern 3: "**Registration:**" line (older format)
    p3 = re.finditer(
        r'\*\*Registration:?\*\*:?\s*(.+)',
        text, re.IGNORECASE
    )
    for m in p3:
        line = m.group(1).strip()
        if FREE_RE.search(line):
            if verbose:
                print(f"  [P-P3] {slug}: FREE")
            return "FREE"
        prices = PRICE_RE.findall(line)
        if prices:
            result = _format_price(prices, line)
            if verbose:
                print(f"  [P-P3] {slug}: {result}")
            return result

    return ""


def _format_price(prices: list, context: str) -> str:
    """Format extracted price strings into a clean cost string.

    If there's a simple range like "$100-$200", return that.
    Otherwise return the highest price found (skip kids/add-on prices).
    """
    if not prices:
        return ""

    # Look for a range in context: $100-$200 or €100–€180
    range_match = re.search(
        r'([\$€£]\s*\d[\d,]*\s*[-–]\s*[\$€£]?\s*\d[\d,]*)',
        context
    )
    if range_match:
        return range_match.group(1).strip()

    # Parse numeric values and return the highest (main entry, not kids/add-ons)
    best_price = ""
    best_value = 0
    for p in prices:
        nums = re.findall(r'\d[\d,]*', p)
        if nums:
            val = int(nums[-1].replace(",", ""))
            if val > best_value:
                best_value = val
                best_price = p.strip()

    return best_price if best_price else prices[0].strip()


# ---------------------------------------------------------------------------
# Placeholder detection — what counts as "needs filling"
# ---------------------------------------------------------------------------

def needs_website(race: dict) -> bool:
    """Check if logistics.official_site needs filling."""
    site = race.get("logistics", {}).get("official_site", "")
    if not site:
        return True
    if site.startswith("http"):
        return False
    # Placeholder patterns: "Check ...", empty, non-URL text
    return True


def needs_founder(race: dict) -> bool:
    """Check if history.founder needs filling."""
    founder = race.get("history", {}).get("founder", "")
    if not founder:
        return True
    return bool(FOUNDER_PLACEHOLDERS.match(founder))


def needs_price(race: dict) -> bool:
    """Check if vitals.registration needs a price."""
    reg = race.get("vitals", {}).get("registration", "")
    if not reg:
        return True
    # Has currency symbol or NNN EUR/GBP pattern?
    if re.search(r'[\$€£]|\d+\s*(?:EUR|GBP|USD|CAD)', reg, re.IGNORECASE):
        return False
    # Has FREE?
    if FREE_RE.search(reg):
        return False
    return True


# ---------------------------------------------------------------------------
# Research dump loading
# ---------------------------------------------------------------------------

def load_dump(slug: str) -> str:
    """Load research dump for a slug. Try -raw.md first, fall back to .bak.md."""
    for suffix in ["-raw.md", "-raw.bak.md"]:
        path = RESEARCH_DIR / f"{slug}{suffix}"
        if path.exists():
            return path.read_text(errors="replace")
    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract metadata from research dumps")
    parser.add_argument("--websites", action="store_true", help="Extract official websites")
    parser.add_argument("--founders", action="store_true", help="Extract founder names")
    parser.add_argument("--prices", action="store_true", help="Extract entry fees")
    parser.add_argument("--all", action="store_true", help="Extract all (default if no flags)")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--slug", help="Process only this race slug")
    parser.add_argument("--verbose", action="store_true", help="Show extraction details")
    args = parser.parse_args()

    # Default to --all if no specific flags
    if not (args.websites or args.founders or args.prices):
        args.all = True
    do_websites = args.all or args.websites
    do_founders = args.all or args.founders
    do_prices = args.all or args.prices

    # Collect race files
    if args.slug:
        files = [RACE_DATA_DIR / f"{args.slug}.json"]
        if not files[0].exists():
            print(f"ERROR: {files[0]} not found")
            return 1
    else:
        files = sorted(RACE_DATA_DIR.glob("*.json"))

    # Counters
    stats = {
        "total": 0,
        "w_need": 0, "w_found": 0, "w_no_dump": 0,
        "f_need": 0, "f_found": 0, "f_no_dump": 0,
        "p_need": 0, "p_found": 0, "p_no_dump": 0,
        "files_modified": 0,
    }

    for path in files:
        slug = path.stem
        data = json.loads(path.read_text())
        race = data.get("race", data)
        stats["total"] += 1
        modified = False

        dump = None  # Lazy-load

        # --- Websites ---
        if do_websites and needs_website(race):
            stats["w_need"] += 1
            if dump is None:
                dump = load_dump(slug)
            if not dump:
                stats["w_no_dump"] += 1
            else:
                url = extract_website(dump, slug, verbose=args.verbose)
                if url:
                    stats["w_found"] += 1
                    if args.dry_run:
                        old = race.get("logistics", {}).get("official_site", "")
                        print(f"  WEBSITE {slug}: {old!r} -> {url!r}")
                    else:
                        if "logistics" not in race:
                            race["logistics"] = {}
                        race["logistics"]["official_site"] = url
                        modified = True

        # --- Founders ---
        if do_founders and needs_founder(race):
            stats["f_need"] += 1
            if dump is None:
                dump = load_dump(slug)
            if not dump:
                stats["f_no_dump"] += 1
            else:
                name = extract_founder(dump, slug, verbose=args.verbose)
                if name:
                    stats["f_found"] += 1
                    if args.dry_run:
                        old = race.get("history", {}).get("founder", "")
                        print(f"  FOUNDER {slug}: {old!r} -> {name!r}")
                    else:
                        if "history" not in race:
                            race["history"] = {}
                        race["history"]["founder"] = name
                        modified = True

        # --- Prices ---
        if do_prices and needs_price(race):
            stats["p_need"] += 1
            if dump is None:
                dump = load_dump(slug)
            if not dump:
                stats["p_no_dump"] += 1
            else:
                price = extract_price(dump, slug, verbose=args.verbose)
                if price:
                    stats["p_found"] += 1
                    if args.dry_run:
                        old = race.get("vitals", {}).get("registration", "")
                        print(f"  PRICE   {slug}: {old!r} + Cost: {price!r}")
                    else:
                        reg = race.get("vitals", {}).get("registration", "")
                        if reg:
                            # Append cost to existing text
                            race["vitals"]["registration"] = f"{reg}. Cost: {price}"
                        else:
                            race["vitals"]["registration"] = f"Online. Cost: {price}"
                        modified = True

        # Write updated JSON
        if modified and not args.dry_run:
            data["race"] = race
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            stats["files_modified"] += 1
            if args.verbose:
                print(f"  WROTE {slug}")

    # --- Summary ---
    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"\n{prefix}Summary ({stats['total']} races processed):")
    if do_websites:
        print(f"  Websites:  {stats['w_need']} needed, {stats['w_found']} found, "
              f"{stats['w_no_dump']} no dump")
    if do_founders:
        print(f"  Founders:  {stats['f_need']} needed, {stats['f_found']} found, "
              f"{stats['f_no_dump']} no dump")
    if do_prices:
        print(f"  Prices:    {stats['p_need']} needed, {stats['p_found']} found, "
              f"{stats['p_no_dump']} no dump")
    if not args.dry_run:
        print(f"  Files modified: {stats['files_modified']}")
    else:
        print("\n(Dry run — no files were modified)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
