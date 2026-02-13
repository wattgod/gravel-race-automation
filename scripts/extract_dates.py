#!/usr/bin/env python3
"""
extract_dates.py — Extract specific dates from research dumps and update TBD/stale profiles.

Reads research-dumps/<slug>-raw.md files and attempts to extract 2026 (or 2025)
race dates using regex patterns. Updates race-data/<slug>.json:
  - vitals.date_specific  (e.g. "2026: July 18")
  - vitals.date           (e.g. "Mid-July annually")

Usage:
  python scripts/extract_dates.py --dry-run     # Preview changes without writing
  python scripts/extract_dates.py               # Apply changes
  python scripts/extract_dates.py --verbose      # Show extraction details
  python scripts/extract_dates.py --stale        # Also update pre-2026 dates
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
RESEARCH_DIR = PROJECT_ROOT / "research-dumps"

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
MONTH_SET = set(m.lower() for m in MONTHS)
MONTH_ABBR = {
    "jan": "January", "feb": "February", "mar": "March", "apr": "April",
    "may": "May", "jun": "June", "jul": "July", "aug": "August",
    "sep": "September", "oct": "October", "nov": "November", "dec": "December",
}

# Season mapping from month
MONTH_TO_SEASON = {
    "January": "Winter", "February": "Winter", "March": "Spring",
    "April": "Spring", "May": "Spring", "June": "Summer",
    "July": "Summer", "August": "Summer", "September": "Fall",
    "October": "Fall", "November": "Fall", "December": "Winter",
}

# Timing labels based on day of month
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


def normalize_month(text):
    """Convert month abbreviation or full name to canonical form."""
    t = text.strip().lower().rstrip(".")
    if t in MONTH_SET:
        return text.strip().title()
    if t[:3] in MONTH_ABBR:
        return MONTH_ABBR[t[:3]]
    return None


def _match_priority(text, match_start, match_end):
    """Score a date match by its surrounding context (higher = better).

    Looks at the full line plus a local window around the match to determine
    if this is the authoritative race date vs a registration deadline.
    """
    # Find the line containing the match
    line_start = text.rfind("\n", 0, match_start) + 1
    line_end = text.find("\n", match_end)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end].lower()

    # Local context: 80 chars before and after the match
    local_start = max(0, match_start - 80)
    local_end = min(len(text), match_end + 80)
    local = text[local_start:local_end].lower()

    score = 0

    # Strong positive indicators on the line
    if "race date" in line or "race dates" in line:
        score += 10
    if "scheduled for" in line:
        score += 8
    if "takes place" in line or "held on" in line:
        score += 5

    # "confirmed" is positive only if not negated near the match
    if "confirmed" in local and "unconfirmed" not in local and "not yet confirmed" not in local:
        score += 5

    # Negative: unconfirmed near this specific match
    if "unconfirmed" in local or "not yet confirmed" in local or "not confirmed" in local:
        score -= 10

    # Negative: registration deadlines, not race dates
    if "registration" in local and ("deadline" in local or "closes" in local or "opens" in local):
        score -= 5
    if "early bird" in local or "early registration" in local:
        score -= 5
    if "packet pickup" in local:
        score -= 3

    # Negative: research metadata lines (not race dates)
    if "research date" in line or "research compiled" in line or "last updated" in line:
        score -= 20
    if "data current as of" in line:
        score -= 20

    return score


def extract_date_from_dump(dump_text, slug, verbose=False):
    """
    Extract the best race date from a research dump.

    Returns (date_specific, date_general) or (None, None) if no date found.
    date_specific: e.g. "2026: July 18" or "2026: September 6-7"
    date_general: e.g. "Mid-July annually"
    """
    candidates = []  # (year, month, day, date_spec, priority)

    # Strip markdown bold markers for easier matching
    text = dump_text.replace("**", "")

    # --- Pattern 1: "Month DD, YYYY" or "Month DD-DD, YYYY" ---
    # Also handles ordinal suffixes: "June 7th, 2025"
    p1 = re.finditer(
        r'(?:(?:Sunday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday),?\s*)?'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*[-–]\s*(\d{1,2})(?:st|nd|rd|th)?)?,?\s*(\d{4})',
        text, re.IGNORECASE
    )
    for m in p1:
        month = m.group(1).title()
        day_start = int(m.group(2))
        day_end = m.group(3)
        year = int(m.group(4))
        if 2025 <= year <= 2027 and 1 <= day_start <= 31:
            if day_end:
                date_spec = f"{year}: {month} {day_start}-{day_end}"
            else:
                date_spec = f"{year}: {month} {day_start}"
            priority = _match_priority(text, m.start(), m.end())
            candidates.append((year, month, day_start, date_spec, priority))
            if verbose:
                print(f"  [P1] {slug}: {date_spec} (pri={priority}) from: ...{m.group(0)}...")

    # --- Pattern 2: "DD Month YYYY" or "DD-DD Month YYYY" (European format) ---
    p2 = re.finditer(
        r'(\d{1,2})(?:st|nd|rd|th)?(?:\s*[-–]\s*(\d{1,2})(?:st|nd|rd|th)?)?\s+'
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r',?\s*(\d{4})',
        text, re.IGNORECASE
    )
    for m in p2:
        day = int(m.group(1))
        day_end = m.group(2)
        month = m.group(3).title()
        year = int(m.group(4))
        if 2025 <= year <= 2027 and 1 <= day <= 31:
            if day_end:
                date_spec = f"{year}: {month} {day}-{day_end}"
            else:
                date_spec = f"{year}: {month} {day}"
            priority = _match_priority(text, m.start(), m.end())
            candidates.append((year, month, day, date_spec, priority))
            if verbose:
                print(f"  [P2] {slug}: {date_spec} (pri={priority}) from: ...{m.group(0)}...")

    # --- Pattern 3: "YYYY-MM-DD" ISO format ---
    p3 = re.finditer(r'(202[5-7])-(\d{2})-(\d{2})', text)
    for m in p3:
        year = int(m.group(1))
        month_num = int(m.group(2))
        day = int(m.group(3))
        if 1 <= month_num <= 12 and 1 <= day <= 31:
            month = MONTHS[month_num - 1]
            date_spec = f"{year}: {month} {day}"
            priority = _match_priority(text, m.start(), m.end())
            candidates.append((year, month, day, date_spec, priority))
            if verbose:
                print(f"  [P3] {slug}: {date_spec} (pri={priority}) from: ...{m.group(0)}...")

    # --- Pattern 4: Line-context extraction ---
    # For dates like "2026 race on Saturday, July 11" where year and date are
    # on the same line but not adjacent. Search line by line.
    if not candidates:
        for line in text.split("\n"):
            # Find year context in the line
            year_match = re.search(r'(202[5-7])', line)
            if not year_match:
                continue
            year = int(year_match.group(1))

            # Find "Month DD" pattern in the same line
            date_matches = re.finditer(
                r'(January|February|March|April|May|June|July|August|September|October|November|December)'
                r'\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*[-–]\s*(\d{1,2})(?:st|nd|rd|th)?)?',
                line, re.IGNORECASE
            )
            for dm in date_matches:
                month = dm.group(1).title()
                day_start = int(dm.group(2))
                day_end = dm.group(3)
                if 1 <= day_start <= 31:
                    if day_end:
                        date_spec = f"{year}: {month} {day_start}-{day_end}"
                    else:
                        date_spec = f"{year}: {month} {day_start}"
                    # Approximate position for priority scoring
                    line_pos = text.find(line)
                    priority = _match_priority(text, line_pos + dm.start(), line_pos + dm.end())
                    candidates.append((year, month, day_start, date_spec, priority))
                    if verbose:
                        print(f"  [P4] {slug}: {date_spec} (pri={priority}) from line: {line.strip()[:80]}")

    if not candidates:
        return None, None

    # Filter out candidates with very negative priority (research metadata, etc.)
    viable = [c for c in candidates if c[4] > -15]
    if not viable:
        return None, None

    # Sort: prefer 2026 > 2025 > 2027, then by priority (higher = better)
    year_pref = {2026: 0, 2025: 1, 2027: 2}
    viable.sort(key=lambda c: (year_pref.get(c[0], 9), -c[4]))

    # Use the best candidate
    _, month, day, date_spec, _ = viable[0]
    date_general = timing_label(month, day)

    return date_spec, date_general


def is_tbd(date_specific):
    """Check if a date_specific field is TBD."""
    if not date_specific:
        return True
    return "TBD" in str(date_specific)


def is_stale(date_specific):
    """Check if a date_specific field has a year before 2026."""
    if not date_specific:
        return False
    ds = str(date_specific).strip()
    m = re.match(r'(\d{4})', ds)
    if m:
        return int(m.group(1)) < 2026
    return False


def main():
    parser = argparse.ArgumentParser(description="Extract dates from research dumps")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without writing")
    parser.add_argument("--verbose", action="store_true", help="Show extraction details")
    parser.add_argument("--stale", action="store_true", help="Also update profiles with pre-2026 dates")
    args = parser.parse_args()

    # Find all TBD profiles
    tbd_profiles = []
    stale_profiles = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        race = data.get("race", data)
        ds = race.get("vitals", {}).get("date_specific", "")
        slug = f.stem
        if is_tbd(ds):
            tbd_profiles.append((slug, f))
        elif args.stale and is_stale(ds):
            stale_profiles.append((slug, f))

    all_profiles = tbd_profiles + stale_profiles
    print(f"Found {len(tbd_profiles)} profiles with TBD dates")
    if args.stale:
        print(f"Found {len(stale_profiles)} profiles with stale (pre-2026) dates")

    updated = 0
    updated_stale = 0
    skipped = 0
    no_dump = 0
    no_date = 0
    stale_slugs = {s for s, _ in stale_profiles}

    for slug, profile_path in all_profiles:
        dump_path = RESEARCH_DIR / f"{slug}-raw.md"
        if not dump_path.exists():
            if args.verbose:
                print(f"  SKIP {slug}: no research dump")
            no_dump += 1
            continue

        dump_text = dump_path.read_text()
        date_spec, date_general = extract_date_from_dump(dump_text, slug, verbose=args.verbose)

        if not date_spec:
            if args.verbose:
                print(f"  NO_DATE {slug}: could not extract date")
            no_date += 1
            continue

        # For stale profiles, only update if extracted year > current year
        if slug in stale_slugs:
            extracted_year = re.match(r'(\d{4})', date_spec)
            current_data = json.loads(profile_path.read_text())
            current_ds = current_data.get("race", current_data).get("vitals", {}).get("date_specific", "")
            current_year = re.match(r'(\d{4})', str(current_ds))
            if extracted_year and current_year:
                if int(extracted_year.group(1)) <= int(current_year.group(1)):
                    if args.verbose:
                        print(f"  SKIP {slug}: extracted {date_spec} not newer than {current_ds}")
                    no_date += 1
                    continue

        # Load profile and update
        data = json.loads(profile_path.read_text())
        race = data.get("race", data)
        vitals = race.get("vitals", {})
        old_ds = vitals.get("date_specific", "")
        old_date = vitals.get("date", "")

        vitals["date_specific"] = date_spec
        if date_general:
            vitals["date"] = date_general

        if args.dry_run:
            label = "STALE" if slug in stale_slugs else "TBD"
            print(f"  WOULD UPDATE [{label}] {slug}: {old_ds!r} -> {date_spec!r} | {old_date!r} -> {date_general!r}")
        else:
            profile_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            if args.verbose:
                label = "STALE" if slug in stale_slugs else "TBD"
                print(f"  UPDATED [{label}] {slug}: {date_spec}")

        updated += 1
        if slug in stale_slugs:
            updated_stale += 1

    print(f"\nResults:")
    print(f"  Updated:    {updated} ({updated - updated_stale} TBD, {updated_stale} stale)")
    print(f"  No dump:    {no_dump}")
    print(f"  No date:    {no_date}")
    print(f"  Total:      {len(all_profiles)} ({len(tbd_profiles)} TBD, {len(stale_profiles)} stale)")

    if args.dry_run:
        print("\n(Dry run — no files were modified)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
