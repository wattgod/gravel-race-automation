#!/usr/bin/env python3
"""
Extract logistics data from existing research dumps WITHOUT API calls.

Targets fields with highest extraction confidence:
- start_time — regex for time patterns (e.g., "8:16am", "7:00 AM")
- prize_purse — regex for "$" + "prize" keywords
- camping — keyword extraction for campground names + costs
- parking — address patterns near "parking" keywords

Mode: Conservative. Only fills if high-confidence match. Never overwrites
existing non-placeholder data. Logs what it filled and couldn't find.

Usage:
    python scripts/extract_logistics.py               # All races
    python scripts/extract_logistics.py --dry-run      # Preview only
    python scripts/extract_logistics.py --slug foo     # Single race
    python scripts/extract_logistics.py --stats        # Show statistics only
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"
DUMP_DIR = PROJECT_ROOT / "research-dumps"

# Placeholder patterns — these indicate the field needs filling
PLACEHOLDER_PATTERNS = [
    re.compile(r"check\s+(the\s+)?official\s+(website|site|page)", re.I),
    re.compile(r"check\s+.*website", re.I),
    re.compile(r"^(morning|afternoon|evening)\s+start$", re.I),
    re.compile(r"^multiple\s+aid\s+stations?$", re.I),
    re.compile(r"^varies$", re.I),
    re.compile(r"^at\s+start/?finish$", re.I),
    re.compile(r"^day\s+before\s+(typically|usually|often)?\s*$", re.I),
    re.compile(r"^(tbd|tba|n/?a|unknown|not\s+available|not\s+specified)$", re.I),
    re.compile(r"^online\.?\s*cost:\s*~", re.I),
    re.compile(r"has\s+(good|full|standard|basic)\s+(lodging|dining|food|camping)\s+options", re.I),
    re.compile(r"^(modest|various)\s+prizes?$", re.I),
    re.compile(r"generally\s+mild\s+conditions", re.I),
    re.compile(r"^none$", re.I),
]


def is_placeholder(text: str) -> bool:
    """Return True if text matches a known placeholder pattern."""
    if not text or not isinstance(text, str):
        return True
    text = text.strip()
    if not text:
        return True
    for pat in PLACEHOLDER_PATTERNS:
        if pat.search(text):
            return True
    return False


def read_dumps(slug: str) -> str:
    """Read all research dump files for a slug into one string."""
    content = ""
    for suffix in ["-raw.md", "-raw.bak.md", "-community.md"]:
        path = DUMP_DIR / f"{slug}{suffix}"
        if path.exists():
            content += "\n" + path.read_text(errors="replace")
    return content


# ── Extractors ────────────────────────────────────────────────────────

# Time patterns: "8:16am CDT", "7:00 AM", "6:30 a.m.", "starts at 8:00"
TIME_RE = re.compile(
    r'(?:start(?:s|ing)?\s+(?:at\s+)?|start\s+time[:\s]+|begins?\s+(?:at\s+)?)'
    r'(\d{1,2}:\d{2}\s*(?:am|pm|a\.m\.|p\.m\.)\s*(?:[A-Z]{2,4})?)',
    re.I,
)

# Standalone time with context: "8:16am CDT" near "start" within 200 chars
TIME_STANDALONE_RE = re.compile(
    r'(\d{1,2}:\d{2}\s*(?:am|pm|a\.m\.|p\.m\.)\s*(?:[A-Z]{2,4})?)',
    re.I,
)

# Prize purse: "$X,XXX prize purse", "prize purse of $X", "$X,XXX in prizes"
PRIZE_RE = re.compile(
    r'(?:prize\s+purse\s+(?:of\s+)?\$[\d,]+(?:\.\d{2})?'
    r'|\$[\d,]+(?:\.\d{2})?\s+(?:in\s+)?prize(?:s|\s+purse)'
    r'|purse[:\s]+\$[\d,]+(?:\.\d{2})?)',
    re.I,
)
PRIZE_AMOUNT_RE = re.compile(r'\$([\d,]+(?:\.\d{2})?)')

# Camping: "camping at X", "campground", "$XX/site", "non-electric sites"
CAMPING_RE = re.compile(
    r'(?:camp(?:ing|ground|site)s?\s+(?:at\s+|available\s+(?:at\s+)?)?'
    r'|onsite\s+camping)'
    r'([^.;]{10,120})',
    re.I,
)
CAMPING_COST_RE = re.compile(r'\$\d+(?:\.\d{2})?\s*/?\s*(?:site|night|person|tent)', re.I)

# Parking: "parking at X", "park at X", address patterns
PARKING_RE = re.compile(
    r'(?:parking\s+(?:at\s+|is\s+(?:at\s+)?|available\s+(?:at\s+)?)|park\s+at\s+)'
    r'([^.;]{10,120})',
    re.I,
)


def extract_start_time(content: str) :
    """Extract start time from dump content."""
    # Direct match: "starts at 8:16am"
    m = TIME_RE.search(content)
    if m:
        return m.group(1).strip()

    # Look for time near "start" keyword
    start_positions = [m.start() for m in re.finditer(r'\bstart\b', content, re.I)]
    for pos in start_positions:
        window = content[max(0, pos - 50):pos + 200]
        tm = TIME_STANDALONE_RE.search(window)
        if tm:
            return tm.group(1).strip()

    return None


def extract_prize_purse(content: str) :
    """Extract prize purse amount from dump content."""
    m = PRIZE_RE.search(content)
    if m:
        amounts = PRIZE_AMOUNT_RE.findall(m.group())
        if amounts:
            return f"${amounts[0]} prize purse"
    return None


def extract_camping(content: str) :
    """Extract camping info from dump content."""
    m = CAMPING_RE.search(content)
    if m:
        info = m.group(0).strip()
        # Limit to one sentence
        info = re.split(r'[.;]', info)[0].strip()
        if len(info) > 20:
            return info
    # Also look for cost pattern
    cost = CAMPING_COST_RE.search(content)
    if cost:
        # Get surrounding context
        start = max(0, cost.start() - 100)
        end = min(len(content), cost.end() + 100)
        context = content[start:end]
        # Extract one sentence containing the cost
        sentences = re.split(r'[.\n]', context)
        for s in sentences:
            if cost.group() in s and len(s.strip()) > 15:
                return s.strip()
    return None


def extract_parking(content: str) :
    """Extract parking info from dump content."""
    m = PARKING_RE.search(content)
    if m:
        info = m.group(0).strip()
        info = re.split(r'[.;]', info)[0].strip()
        if len(info) > 15:
            return info
    return None


# ── Main Logic ────────────────────────────────────────────────────────

EXTRACTORS = {
    "start_time": ("vitals", extract_start_time),
    "prize_purse": ("vitals", extract_prize_purse),
    "camping": ("logistics", extract_camping),
    "parking": ("logistics", extract_parking),
}


def process_profile(filepath: Path, dry_run: bool = False) -> dict:
    """Process a single race profile. Returns report dict."""
    slug = filepath.stem
    content = read_dumps(slug)

    if not content.strip():
        return {"slug": slug, "no_dump": True, "filled": {}, "skipped": {}}

    data = json.loads(filepath.read_text())
    race = data["race"]
    filled = {}
    skipped = {}

    for field, (section, extractor) in EXTRACTORS.items():
        section_data = race.get(section, {})
        if not isinstance(section_data, dict):
            continue

        current = section_data.get(field, "")

        # Don't overwrite existing non-placeholder data
        if not is_placeholder(str(current)):
            skipped[field] = "already_filled"
            continue

        extracted = extractor(content)
        if extracted:
            filled[field] = extracted
            section_data[field] = extracted
            race[section] = section_data
        else:
            skipped[field] = "no_match"

    if filled and not dry_run:
        data["race"] = race
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return {"slug": slug, "no_dump": False, "filled": filled, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description="Extract logistics from research dumps")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--slug", help="Process only this race slug")
    parser.add_argument("--stats", action="store_true", help="Show statistics only")
    args = parser.parse_args()

    files = sorted(DATA_DIR.glob("*.json"))
    if args.slug:
        files = [DATA_DIR / f"{args.slug}.json"]
        if not files[0].exists():
            print(f"ERROR: {files[0]} not found")
            sys.exit(1)

    results = []
    for fp in files:
        result = process_profile(fp, dry_run=args.dry_run)
        results.append(result)

        if not args.stats and result["filled"]:
            print(f"\n  {result['slug']}:")
            for field, value in result["filled"].items():
                print(f"    + {field}: {value[:80]}")

    # Statistics
    total = len(results)
    with_dumps = sum(1 for r in results if not r["no_dump"])
    no_dumps = total - with_dumps

    field_stats = {}
    for field in EXTRACTORS:
        filled = sum(1 for r in results if field in r["filled"])
        already = sum(1 for r in results if r["skipped"].get(field) == "already_filled")
        no_match = sum(1 for r in results if r["skipped"].get(field) == "no_match")
        field_stats[field] = {"filled": filled, "already": already, "no_match": no_match}

    total_filled = sum(len(r["filled"]) for r in results)

    prefix = "DRY RUN — " if args.dry_run else ""
    print(f"\n{prefix}Logistics Extraction Summary:")
    print(f"  Profiles scanned:  {total}")
    print(f"  With research dumps: {with_dumps}")
    print(f"  No dumps:          {no_dumps}")
    print(f"  Total fields filled: {total_filled}")
    print()
    print(f"  {'Field':<15s} {'Filled':>7s} {'Already':>8s} {'No Match':>9s}")
    print(f"  {'-'*15} {'-'*7} {'-'*8} {'-'*9}")
    for field, stats in field_stats.items():
        print(f"  {field:<15s} {stats['filled']:>7d} {stats['already']:>8d} {stats['no_match']:>9d}")

    if args.dry_run and total_filled > 0:
        print(f"\n  Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
