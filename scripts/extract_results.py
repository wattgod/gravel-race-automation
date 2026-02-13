#!/usr/bin/env python3
"""
extract_results.py — Extract race results from research dumps.

Reads research-dumps/<slug>-raw.md files and extracts:
  - Winners (male/female) → results.years.YYYY.winner_male/female
  - Winning times → results.years.YYYY.winning_time_male/female
  - Conditions → results.years.YYYY.conditions
  - Field size → results.years.YYYY.field_size_actual
  - DNF rate → results.years.YYYY.dnf_rate_pct
  - Key takeaways → results.years.YYYY.key_takeaways

Only fills gaps — never overwrites existing data.

Usage:
  python scripts/extract_results.py --all --dry-run     # Preview all
  python scripts/extract_results.py --all               # Apply all
  python scripts/extract_results.py --slug unbound-200   # Single race
  python scripts/extract_results.py --year 2024          # Specific year
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
RESEARCH_DIR = PROJECT_ROOT / "research-dumps"


def load_dump(slug):
    """Load research dump text for a slug."""
    for suffix in ["-raw.md", "-raw.bak.md"]:
        path = RESEARCH_DIR / f"{slug}{suffix}"
        if path.exists():
            return path.read_text(errors="replace")
    return ""


def _find_year_blocks(dump, year):
    """Find line blocks in dump that reference the given year.

    Returns list of (line_index, block_text) tuples where block_text
    is the year-containing line plus up to 5 following lines.

    Blocks are prioritized:
    1. Lines where the year appears as a label (e.g. "*2024:*" or "**2024 Winners:**")
    2. Lines where the year appears in text but with a person name nearby
    3. All other mentions
    """
    year_str = str(year)
    lines = dump.split("\n")

    # Year-as-label patterns: the year starts or leads the line as a heading
    year_label_re = re.compile(
        rf'^\s*[\*•\-\t]*\s*\*?{year_str}\*?\s*[:(\*]'
    )
    # Has a person name (Firstname Lastname in bold or after "Men:/Women:")
    person_re = re.compile(
        r'\*\*[A-Z][a-z]+ [A-Z][a-z]+|[-•]\s*(?:Men|Women)[\'s]*\s*(?:Pro\s*)?:\s*[A-Z]'
    )

    priority_0 = []  # year as label
    priority_1 = []  # year + person name
    priority_2 = []  # year mentioned

    for i, line in enumerate(lines):
        if year_str not in line:
            continue
        block = "\n".join(lines[i:i + 6])

        if year_label_re.search(line):
            priority_0.append((i, block))
        elif person_re.search(block):
            priority_1.append((i, block))
        else:
            priority_2.append((i, block))

    return priority_0 + priority_1 + priority_2


def _gender_matches(text, gender):
    """Check if text contains gender markers for the given gender.

    Returns True if gender markers found for the requested gender.
    For 'male', also returns True if no female markers are present
    (male is the default/first-listed).
    """
    male_markers = [r"men'?s?(?:\s+pro)?", r"\bmale\b", r"\boverall\b"]
    female_markers = [r"women'?s?(?:\s+pro)?", r"\bfemale\b"]

    text_lower = text.lower()
    if gender == "female":
        return any(re.search(m, text_lower) for m in female_markers)
    else:
        # Male matches if: explicit male marker, OR no female marker
        has_female = any(re.search(m, text_lower) for m in female_markers)
        has_male = any(re.search(m, text_lower) for m in male_markers)
        return has_male or not has_female


def extract_winner(dump, slug, gender, year):
    """Extract race winner name from dump text.

    Handles multiple real-world formats:
    1. Unbound style: *YYYY:* **Name** (bold inline names)
    2. BWR style: - Men: Name (time) under **YYYY Winners:**
    3. Grinduro style: - Men's Pro: Name under **YYYY (location):**

    Args:
        gender: 'male' or 'female'
    """
    if not dump:
        return ""

    year_str = str(year)
    blocks = _find_year_blocks(dump, year)

    for _, block in blocks:
        block_lines = block.split("\n")

        # Format 2/3: "- Men: Name" or "- Women: Name" list items
        for line in block_lines:
            # Match: "- Men: Name" / "- Men's Pro: Name" / "- Women: Name (team)"
            list_match = re.match(
                r'\s*[-•]\s*(Men\'?s?(?:\s+Pro)?|Women\'?s?(?:\s+Pro)?)\s*:\s*'
                r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)',
                line
            )
            if list_match:
                label = list_match.group(1).lower()
                name = list_match.group(2).strip()
                # Strip trailing parenthetical (team names, times)
                name = re.sub(r'\s*\(.*$', '', name).strip()
                # Strip trailing " -" or " –" (dash separators)
                name = re.sub(r'\s*[-–].*$', '', name).strip()

                if gender == "female" and re.search(r"women", label):
                    return name
                elif gender == "male" and re.search(r"men", label) and "women" not in label:
                    return name

        # Format 1: Bold names **Name** with gender context
        # Require mixed case (not ALL CAPS — those are section headers)
        name_pattern = r'\*\*([A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\*\*'
        for line in block_lines:
            names_with_pos = list(re.finditer(name_pattern, line))
            for m in names_with_pos:
                name = m.group(1)
                # Use text BEFORE this name for gender context (not full line)
                before = line[:m.start()].lower()
                # Also check a small window after (for "won women" after name)
                after = line[m.end():m.end() + 50].lower()

                if gender == "female":
                    # Need female marker before OR immediately after
                    has_female = any(re.search(p, before[-80:] + " " + after)
                                     for p in [r"women'?s?", r"\bfemale\b"])
                    if has_female:
                        return name
                else:
                    # Male: accept if no female marker before this name
                    has_female_before = any(re.search(p, before[-60:])
                                            for p in [r"women'?s?", r"\bfemale\b"])
                    if not has_female_before:
                        return name

    return ""


def extract_winning_time(dump, slug, gender, year):
    """Extract winning time in HH:MM:SS or H:MM:SS format.

    Handles:
    1. Bold time in text: **8:34:39**
    2. Parenthetical: Name (5:48:32)
    3. Dash-separated: Name - 41:43.65
    4. Inline: Name in 8:34:39
    """
    if not dump:
        return ""

    time_pattern = r'(\d{1,2}:\d{2}[:.]\d{2})'
    blocks = _find_year_blocks(dump, year)

    for _, block in blocks:
        block_lines = block.split("\n")

        # Check list-format lines first: "- Men: Name (time)" or "- Men: Name - time"
        for line in block_lines:
            list_match = re.match(
                r'\s*[-•]\s*(Men\'?s?(?:\s+Pro)?|Women\'?s?(?:\s+Pro)?)\s*:',
                line
            )
            if list_match:
                label = list_match.group(1).lower()
                time_match = re.search(time_pattern, line)
                if not time_match:
                    continue

                time_val = time_match.group(1)
                if gender == "female" and re.search(r"women", label):
                    return time_val
                elif gender == "male" and re.search(r"men", label) and "women" not in label:
                    return time_val

        # Check inline bold times: **Name** in **8:34:39**
        times_in_block = list(re.finditer(time_pattern, block))
        for tm in times_in_block:
            time_val = tm.group(1)
            before_text = block[:tm.start()].lower()
            # Check gender context within 100 chars before time
            context = before_text[-100:]

            if _gender_matches(context, gender):
                if gender == "male":
                    # Verify no female marker immediately before
                    nearby = before_text[-60:]
                    if any(re.search(m, nearby)
                           for m in [r"women'?s?", r"\bfemale\b"]):
                        continue
                return time_val

    return ""


def extract_conditions(dump, slug, year):
    """Extract race conditions/weather from dump text."""
    if not dump:
        return ""

    year_str = str(year)
    weather_keywords = [
        "mud", "rain", "hot", "cold", "wind", "dry", "wet", "heat",
        "snow", "dust", "cool", "warm", "ideal", "brutal", "conditions",
        "weather", "temperature", "humidity",
    ]

    lines = dump.split("\n")
    for i, line in enumerate(lines):
        if year_str not in line:
            continue
        search_block = "\n".join(lines[i:i+3]).lower()
        matches = [kw for kw in weather_keywords if kw in search_block]
        if len(matches) >= 2:
            # Extract the relevant sentence
            sentences = re.split(r'[.!]', lines[i])
            for sent in sentences:
                if any(kw in sent.lower() for kw in weather_keywords):
                    clean = sent.strip().strip("*").strip()
                    if len(clean) > 10:
                        return clean[:200]

    return ""


def extract_field_size_actual(dump, slug, year):
    """Extract actual field size/participation count."""
    if not dump:
        return None

    year_str = str(year)
    # Patterns: ~4,000 riders, 4000+ participants, field of 3,200
    patterns = [
        rf'{year_str}.*?(?:~|about|approximately|nearly)?\s*([\d,]+)\+?\s*(?:riders|participants|starters|racers)',
        rf'(?:~|about|approximately|nearly)?\s*([\d,]+)\+?\s*(?:riders|participants|starters|racers).*?{year_str}',
        rf'field\s+(?:size|of)\s*(?:~|about)?\s*([\d,]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, dump, re.IGNORECASE)
        if match:
            num_str = match.group(1).replace(",", "")
            try:
                val = int(num_str)
                if 10 <= val <= 50000:  # Sanity check
                    return val
            except ValueError:
                continue

    return None


def extract_dnf_rate(dump, slug, year):
    """Extract DNF rate as percentage."""
    if not dump:
        return None

    year_str = str(year)
    # Patterns: 20% DNF, DNF rate of 20%, barely 50% finish
    # Search line by line near year reference
    lines = dump.split("\n")
    for i, line in enumerate(lines):
        if year_str not in line:
            continue
        search_block = "\n".join(lines[i:i + 3])

        # NN% DNF
        m = re.search(r'(\d{1,2})%\s*(?:DNF|did not finish|dropout)', search_block, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 80:
                return val

        # DNF rate of NN%
        m = re.search(r'DNF\s+rate\s+(?:of\s+)?(\d{1,2})%', search_block, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= 80:
                return val

        # finish rate NN% (convert to DNF)
        m = re.search(r'finish\s+rate.*?(\d{2,3})%', search_block, re.IGNORECASE)
        if m:
            val = 100 - int(m.group(1))
            if 1 <= val <= 80:
                return val

    return None


def extract_key_takeaways(dump, slug, year):
    """Extract notable highlights/takeaways (max 5)."""
    if not dump:
        return []

    year_str = str(year)
    takeaways = []

    # Look for lines near year with notable markers
    notable_patterns = [
        r'(?:new|broke|record|first|largest|biggest|closest|fastest|historic)',
        r'(?:course record|field ever|sprint finish|debut)',
    ]

    lines = dump.split("\n")
    for i, line in enumerate(lines):
        if year_str not in line:
            continue
        # Check this line and nearby for notable phrases
        search_block = "\n".join(lines[max(0, i-1):i+3])
        for pattern in notable_patterns:
            if re.search(pattern, search_block, re.IGNORECASE):
                # Extract the sentence containing the notable phrase
                for sent in re.split(r'[.!]', line):
                    sent = sent.strip().strip("*").strip("•").strip("-").strip()
                    if re.search(pattern, sent, re.IGNORECASE) and len(sent) > 15:
                        # Clean up markdown
                        clean = re.sub(r'\*+', '', sent).strip()
                        clean = re.sub(r'\[.*?\]\(.*?\)', '', clean).strip()
                        if clean and clean not in takeaways:
                            takeaways.append(clean[:150])
                            break

    return takeaways[:5]


def extract_results_for_race(slug, year, verbose=False):
    """Extract all results data for a single race+year."""
    dump = load_dump(slug)
    if not dump:
        if verbose:
            print(f"  SKIP  {slug}: no research dump")
        return None

    year_str = str(year)
    if year_str not in dump:
        if verbose:
            print(f"  SKIP  {slug}: year {year} not mentioned in dump")
        return None

    results = {}

    winner_m = extract_winner(dump, slug, "male", year)
    if winner_m:
        results["winner_male"] = winner_m
    winner_f = extract_winner(dump, slug, "female", year)
    if winner_f:
        results["winner_female"] = winner_f

    time_m = extract_winning_time(dump, slug, "male", year)
    if time_m:
        results["winning_time_male"] = time_m
    time_f = extract_winning_time(dump, slug, "female", year)
    if time_f:
        results["winning_time_female"] = time_f

    conditions = extract_conditions(dump, slug, year)
    if conditions:
        results["conditions"] = conditions

    field_size = extract_field_size_actual(dump, slug, year)
    if field_size is not None:
        results["field_size_actual"] = field_size

    dnf = extract_dnf_rate(dump, slug, year)
    if dnf is not None:
        results["dnf_rate_pct"] = dnf

    takeaways = extract_key_takeaways(dump, slug, year)
    if takeaways:
        results["key_takeaways"] = takeaways

    return results if results else None


def apply_results(slug, year, results, dry_run=False):
    """Write extracted results to race JSON, gap-fill only."""
    json_path = RACE_DATA_DIR / f"{slug}.json"
    if not json_path.exists():
        return False

    data = json.loads(json_path.read_text())
    race = data.get("race", data)
    year_str = str(year)

    # Ensure results structure exists
    if "results" not in race:
        race["results"] = {"years": {}, "latest_year": ""}
    if "years" not in race["results"]:
        race["results"]["years"] = {}
    if year_str not in race["results"]["years"]:
        race["results"]["years"][year_str] = {}

    existing = race["results"]["years"][year_str]
    applied = 0

    for key, val in results.items():
        if key not in existing or not existing[key]:
            if dry_run:
                print(f"    {key}: {val}")
            else:
                existing[key] = val
            applied += 1

    if applied > 0:
        # Update latest_year
        all_years = sorted(race["results"]["years"].keys(), reverse=True)
        race["results"]["latest_year"] = all_years[0]

        if not dry_run:
            json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return applied > 0


def main():
    parser = argparse.ArgumentParser(description="Extract race results from research dumps")
    parser.add_argument("--slug", help="Extract results for a single race")
    parser.add_argument("--year", type=int, default=2024,
                        help="Year to extract results for (default: 2024)")
    parser.add_argument("--all", action="store_true",
                        help="Process all races with research dumps")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without writing")
    parser.add_argument("--verbose", action="store_true",
                        help="Show detailed output")
    args = parser.parse_args()

    if args.slug:
        results = extract_results_for_race(args.slug, args.year, verbose=True)
        if results:
            print(f"\n  {args.slug} ({args.year}):")
            for k, v in results.items():
                print(f"    {k}: {v}")
            if not args.dry_run:
                if apply_results(args.slug, args.year, results):
                    print(f"  APPLIED to {args.slug}.json")
                else:
                    print(f"  NO NEW DATA for {args.slug}.json")
        else:
            print(f"  No results found for {args.slug} ({args.year})")
        return

    if args.all:
        slugs = sorted(f.stem for f in RACE_DATA_DIR.glob("*.json"))
        updated = 0
        found = 0

        for slug in slugs:
            results = extract_results_for_race(slug, args.year, verbose=args.verbose)
            if results:
                found += 1
                if args.dry_run:
                    print(f"\n  {slug} ({args.year}):")
                    for k, v in results.items():
                        print(f"    {k}: {v}")
                else:
                    if apply_results(slug, args.year, results):
                        print(f"  OK    {slug}")
                        updated += 1

        print(f"\nFound results for {found} races.")
        if not args.dry_run:
            print(f"Updated {updated} race JSONs.")
        return

    parser.error("Provide --slug NAME or --all")


if __name__ == "__main__":
    main()
