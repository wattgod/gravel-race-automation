#!/usr/bin/env python3
"""
Batch research prompt generator — Sprint 4/5.

Reads the flat database, identifies races needing research, and generates
per-race prompt files that can be fed into Cursor sessions.

Usage:
    python batch_research.py --tier A                     # Generate Tier A prompts
    python batch_research.py --tier A --batch-size 20     # First 20 Tier A races
    python batch_research.py --list                       # List all races by tier
    python batch_research.py --status                     # Show research coverage
"""

import argparse
import json
import re
from pathlib import Path
from typing import List


FLAT_DB = Path(__file__).parent.parent / "db" / "gravel_races_full_database.json"
RACE_DATA = Path(__file__).parent.parent / "race-data"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
RESEARCH_DUMPS_DIR = Path(__file__).parent.parent / "research-dumps"

# Research brief template (condensed for prompt generation)
RESEARCH_PROMPT_TEMPLATE = """# RACE RESEARCH TASK: {race_name}

## Seed Data (from flat database — VERIFY everything)
- **Name:** {race_name}
- **Location:** {location}
- **Distance:** {distance} miles
- **Elevation:** {elevation} ft
- **Date:** {date}
- **Website:** {website}
- **Data Quality:** {data_quality} — {verify_note}

## Research Instructions

You are researching **{race_name}** for the Gravel God Cycling race database.

### Step 1: Web Research (find 5+ distinct sources)

Search for and open at minimum:
1. Official race website — extract vitals, registration, course info
2. Reddit threads (r/gravelcycling, r/cycling) — rider experiences, race reports
3. YouTube race recaps — look for course footage and commentary
4. Forum threads (TrainerRoad, Slowtwitch) — training/equipment discussions
5. News coverage (VeloNews, CyclingTips, Escape Collective) — race results, profiles
6. RideWithGPS or Strava — route data, segment info

For each source, extract:
- Specific mile markers and named course features
- Weather data (temperatures, conditions by month/year)
- Equipment recommendations with reasons
- DNF rates and reasons
- Real rider quotes (with attribution: username, source)
- Logistics details (parking, lodging, aid stations)

### Step 2: Write Research Dump

Output a markdown research dump with these sections:

```
## OFFICIAL DATA
[Race vitals, registration, course details from official site]

## TERRAIN & COURSE
[Surface types, named climbs/features, mile-by-mile breakdown]

## WEATHER & CLIMATE
[Historical conditions, temperature ranges, wind patterns]

## REDDIT & FORUM INSIGHTS
[Real rider quotes with u/username attribution]

## SUFFERING ZONES
[Specific named sections where the race gets hard — real geographic names]

## DNF FACTORS
[What makes people quit, with data if available]

## EQUIPMENT CONSENSUS
[Tire recommendations, gear setup, what experienced riders run]

## LOGISTICS
[Airport, lodging, parking, food, packet pickup]
```

### Step 3: Quality Requirements

- Every statistic must have a source URL
- Every suffering zone must have a real geographic name (not "the hard part")
- At least 1 real rider quote with attribution
- No generic filler phrases ("amazing experience", "world-class")
- No fabricated data — if you can't find it, say "DATA NOT FOUND"

Save output to: `research-dumps/{slug}-raw.md`
"""

VERIFY_NOTES = {
    "Verified": "Seed data is verified. Use as starting point but still cross-reference.",
    "Estimated": "Seed data may be inaccurate. VERIFY all vitals against official source.",
    "Unverified": "Seed data is unreliable. Research from scratch.",
}


def load_flat_db() -> list:
    """Load the flat database. Handles {"races": [...]} wrapper."""
    raw = json.loads(FLAT_DB.read_text())
    if isinstance(raw, dict):
        return raw.get("races", [])
    return raw


def get_existing_profiles() -> set:
    """Get slugs of races that already have rich profiles."""
    return {f.stem for f in RACE_DATA.glob("*.json")}


def get_existing_research() -> set:
    """Get slugs of races that already have research dumps."""
    if not RESEARCH_DUMPS_DIR.exists():
        return set()
    slugs = set()
    for f in RESEARCH_DUMPS_DIR.glob("*-raw.md"):
        slug = f.stem.replace("-raw", "")
        slugs.add(slug)
    return slugs


def slugify(name: str) -> str:
    """Convert race name to slug."""
    slug = name.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = re.sub(r'-+', '-', slug)
    return slug


def _get(race: dict, *keys, default=""):
    """Get value from race dict, trying multiple key formats."""
    for k in keys:
        if k in race:
            return race[k]
    return default


def classify_tier(race: dict) -> str:
    """Classify race into research tier based on data quality and priority."""
    priority = _get(race, "PRIORITY_SCORE", "priority_score", default=0)
    quality = _get(race, "DATA_QUALITY", "data_quality", default="Unverified")

    if isinstance(priority, str):
        try:
            priority = float(priority)
        except ValueError:
            priority = 0

    if priority >= 7 and quality == "Verified":
        return "A"
    elif priority >= 5 or quality in ("Verified", "Estimated"):
        return "B"
    else:
        return "C"


def generate_prompt(race: dict, slug: str) -> str:
    """Generate a research prompt for a single race."""
    quality = _get(race, "DATA_QUALITY", "data_quality", default="Unverified")
    distance_raw = _get(race, "DISTANCE", "distance_miles", default="?")
    # Take first distance if multi-option (e.g., "60/34/21")
    if isinstance(distance_raw, str) and "/" in distance_raw:
        distance_raw = distance_raw.split("/")[0].strip()

    return RESEARCH_PROMPT_TEMPLATE.format(
        race_name=_get(race, "RACE_NAME", "name", default=slug),
        location=_get(race, "LOCATION", "location", default="Unknown"),
        distance=distance_raw,
        elevation=_get(race, "ELEVATION_GAIN", "elevation_feet", default="?"),
        date=_get(race, "DATE", "date", default="Unknown"),
        website=_get(race, "WEBSITE_URL", "website", default=""),
        data_quality=quality,
        verify_note=VERIFY_NOTES.get(quality, "Research from scratch."),
        slug=slug,
    )


def main():
    parser = argparse.ArgumentParser(description="Generate batch research prompts")
    parser.add_argument("--tier", choices=["A", "B", "C", "all"], help="Generate prompts for tier")
    parser.add_argument("--batch-size", type=int, default=0, help="Limit to N prompts (0 = all)")
    parser.add_argument("--list", action="store_true", help="List all races by tier")
    parser.add_argument("--status", action="store_true", help="Show research coverage")
    parser.add_argument("--output-dir", help="Custom output directory for prompts")
    args = parser.parse_args()

    db = load_flat_db()
    existing_profiles = get_existing_profiles()
    existing_research = get_existing_research()

    # Classify and organize
    tiers = {"A": [], "B": [], "C": []}
    for race in db:
        slug = slugify(_get(race, "RACE_NAME", "name", default=""))
        tier = classify_tier(race)
        race["_slug"] = slug
        race["_tier"] = tier
        race["_has_profile"] = slug in existing_profiles
        race["_has_research"] = slug in existing_research
        tiers[tier].append(race)

    if args.status:
        print("\n=== RESEARCH COVERAGE ===\n")
        print(f"Flat DB total:      {len(db)}")
        print(f"Rich profiles:      {len(existing_profiles)}")
        print(f"Research dumps:     {len(existing_research)}")
        print()
        for tier_name in ["A", "B", "C"]:
            races = tiers[tier_name]
            with_profile = sum(1 for r in races if r["_has_profile"])
            with_research = sum(1 for r in races if r["_has_research"])
            needs_work = sum(1 for r in races if not r["_has_profile"])
            print(f"Tier {tier_name}: {len(races)} races ({with_profile} profiles, {with_research} research, {needs_work} need work)")
        print()
        return

    if args.list:
        for tier_name in ["A", "B", "C"]:
            print(f"\n=== TIER {tier_name} ({len(tiers[tier_name])} races) ===\n")
            for race in sorted(tiers[tier_name], key=lambda r: _get(r, "PRIORITY_SCORE", "priority_score", default=0), reverse=True):
                status = "✓" if race["_has_profile"] else "○"
                research = "R" if race["_has_research"] else " "
                priority = _get(race, "PRIORITY_SCORE", "priority_score", default="?")
                name = _get(race, "RACE_NAME", "name", default="?")
                location = _get(race, "LOCATION", "location", default="?")
                print(f"  {status}{research} [{priority:>4}] {name:<40} {location}")
        return

    if args.tier:
        target_tiers = ["A", "B", "C"] if args.tier == "all" else [args.tier]
        output_dir = Path(args.output_dir) if args.output_dir else PROMPTS_DIR
        output_dir.mkdir(exist_ok=True)

        count = 0
        for tier_name in target_tiers:
            for race in sorted(tiers[tier_name], key=lambda r: _get(r, "PRIORITY_SCORE", "priority_score", default=0), reverse=True):
                # Skip races that already have profiles
                if race["_has_profile"]:
                    continue

                slug = race["_slug"]
                prompt = generate_prompt(race, slug)
                prompt_file = output_dir / f"{slug}-research.txt"
                prompt_file.write_text(prompt)
                count += 1
                print(f"  Generated: {prompt_file.name}")

                if args.batch_size and count >= args.batch_size:
                    break
            if args.batch_size and count >= args.batch_size:
                break

        print(f"\nGenerated {count} research prompts in {output_dir}/")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
