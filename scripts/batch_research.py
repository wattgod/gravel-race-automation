#!/usr/bin/env python3
"""
Batch research via Kimi K2 web search — generates research dumps
for race profiles that lack substantial research data.

Uses Moonshot AI's built-in $web_search tool to gather race details
from the web, then saves structured research dumps.

Usage:
    python scripts/batch_research.py --auto 10               # Top 10 priority races
    python scripts/batch_research.py --slugs unbound-200      # Specific races
    python scripts/batch_research.py --auto 5 --dry-run       # Preview candidates
    python scripts/batch_research.py --auto 50 --concurrency 5  # Parallel
    python scripts/batch_research.py --auto 20 --include-no-profile  # Include index-only races
    python scripts/batch_research.py --status                 # Show research coverage

Requires: MOONSHOT_API_KEY environment variable
Get key at: https://platform.moonshot.ai/console/api-keys

Pipeline:
    1. batch_research.py  (Kimi — cheap web search)  → research-dumps/{slug}-raw.md
    2. batch_enrich.py    (Claude — voice & style)    → race-data/{slug}.json enriched
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RACE_DATA = Path(__file__).parent.parent / "race-data"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"
INDEX_PATH = Path(__file__).parent.parent / "web" / "race-index.json"

# Minimum KB for a research dump to be considered "substantial"
MIN_RESEARCH_KB = 5.0

# Kimi API config
KIMI_MODEL = "kimi-k2-0905-preview"
KIMI_BASE_URL = "https://api.moonshot.ai/v1"
MAX_SEARCH_ROUNDS = 15  # Cap tool-call loops to prevent runaway


def get_research_candidates(n, include_no_profile=False, min_kb=None):
    """Find races that need research, prioritized by tier.

    Returns list of dicts with slug, name, location, tier, and
    any existing vitals to seed the research prompt.
    """
    threshold = min_kb if min_kb is not None else MIN_RESEARCH_KB
    candidates = []
    seen_slugs = set()

    # Races WITH profiles but thin/no research
    for path in sorted(RACE_DATA.glob("*.json")):
        slug = path.stem
        dump = RESEARCH_DUMPS / f"{slug}-raw.md"
        if dump.exists() and dump.stat().st_size / 1024 >= threshold:
            continue  # Already has substantial research

        data = json.loads(path.read_text())
        race = data.get("race", data)
        tier = race.get("gravel_god_rating", {}).get("display_tier",
               race.get("gravel_god_rating", {}).get("tier", 4))
        candidates.append({
            "slug": slug,
            "name": race.get("name", slug),
            "location": race.get("vitals", {}).get("location", "Unknown"),
            "distance": race.get("vitals", {}).get("distance_mi", ""),
            "elevation": race.get("vitals", {}).get("elevation_ft", ""),
            "website": race.get("logistics", {}).get("official_site", ""),
            "tier": tier,
            "has_profile": True,
        })
        seen_slugs.add(slug)

    # Races in index WITHOUT profiles (optional)
    if include_no_profile and INDEX_PATH.exists():
        index = json.loads(INDEX_PATH.read_text())
        for entry in index:
            slug = entry.get("slug", "")
            if slug in seen_slugs:
                continue
            dump = RESEARCH_DUMPS / f"{slug}-raw.md"
            if dump.exists() and dump.stat().st_size / 1024 >= threshold:
                continue
            candidates.append({
                "slug": slug,
                "name": entry.get("name", slug),
                "location": entry.get("location", "Unknown"),
                "distance": entry.get("distance_mi", ""),
                "elevation": entry.get("elevation_ft", ""),
                "website": "",
                "tier": entry.get("tier", 4),
                "has_profile": False,
            })

    # Sort: T1 first, then T2, T3, T4
    candidates.sort(key=lambda r: (r["tier"], r["slug"]))
    return candidates[:n]


def build_research_prompt(race_info):
    """Build the research prompt for Kimi web search."""
    name = race_info["name"]
    location = race_info["location"]
    distance = race_info.get("distance", "")
    elevation = race_info.get("elevation", "")
    website = race_info.get("website", "")

    seed_lines = [f"LOCATION: {location}"]
    if distance:
        seed_lines.append(f"DISTANCE: {distance} miles")
    if elevation:
        seed_lines.append(f"ELEVATION: {elevation} ft")
    if website and website.startswith("http"):
        seed_lines.append(f"WEBSITE: {website}")
    seed_info = "\n".join(seed_lines)

    return f"""Research the gravel/cycling race "{name}" thoroughly using web search.

KNOWN INFO:
{seed_info}

Search for and compile a comprehensive research dump covering ALL of the following.
Use multiple searches to find different types of information:

**OFFICIAL DATA**
- 2025 and 2026 race dates (specific month/day if available)
- Registration cost / entry fees
- Field size (number of participants)
- Distance options and elevation gain for each
- Prize purse (if any)
- Start location and time
- Aid station details, cutoff times

**TERRAIN & COURSE**
- Surface breakdown (% gravel, pavement, singletrack, dirt)
- Key course features, named climbs/sectors
- Technical difficulty level
- Elevation profile description

**CLIMATE & CONDITIONS**
- Typical weather for the race date/location
- Historical weather incidents (mud years, heat, wind)
- Altitude (starting elevation, max elevation)

**LOGISTICS**
- Nearest airport
- Lodging options and strategy
- Parking situation
- Packet pickup details

**COMMUNITY & REPUTATION**
- Race history (founded year, founder if known)
- Notable past winners / pro riders who have raced it
- Rider reviews and quotes (Reddit, forums, race reports)
- YouTube race coverage
- How the race is perceived in the gravel community

**RACE REPORTS & RIDER EXPERIENCE**
- Specific rider experiences and quotes
- "What I wish I knew" insights
- Equipment recommendations from participants
- DNF rates if available

FORMAT RULES:
- Use markdown with **bold section headers**
- Include specific numbers, dates, names — no vague generalizations
- Quote riders directly when possible (attribute the source)
- Note your sources inline (e.g. "per the official race website", "Reddit user u/xxx noted")
- If information is unavailable or uncertain, say so explicitly — do NOT fabricate
- Start the document with: # {name.upper()} - RAW RESEARCH DUMP"""


def call_kimi_with_search(prompt, api_key, max_retries=2):
    """Call Kimi API with built-in web search. Returns (text, search_rounds)."""
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=KIMI_BASE_URL,
    )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a cycling race researcher. Your job is to use web search "
                "to find detailed, factual information about gravel and cycling races. "
                "Search multiple times to build comprehensive coverage. "
                "Be specific — include real dates, numbers, names, quotes, and sources. "
                "Do not make up information. If you cannot find something, say so."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    tools = [
        {
            "type": "builtin_function",
            "function": {"name": "$web_search"},
        }
    ]

    for attempt in range(max_retries + 1):
        try:
            finish_reason = None
            rounds = 0

            while finish_reason != "stop" and rounds < MAX_SEARCH_ROUNDS:
                completion = client.chat.completions.create(
                    model=KIMI_MODEL,
                    messages=messages,
                    temperature=0.6,
                    tools=tools,
                    max_tokens=8000,
                )
                choice = completion.choices[0]
                finish_reason = choice.finish_reason
                rounds += 1

                if finish_reason == "tool_calls":
                    messages.append(choice.message)
                    for tool_call in choice.message.tool_calls:
                        tool_args = json.loads(tool_call.function.arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": tool_call.function.name,
                            "content": json.dumps(tool_args),
                        })

            return choice.message.content, rounds

        except Exception as e:
            if attempt < max_retries:
                wait = 30 * (attempt + 1)
                print(f"\n  Error: {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise


def research_race(race_info, api_key, dry_run=False):
    """Research a single race. Returns (success, message, slug)."""
    slug = race_info["slug"]
    name = race_info["name"]

    if dry_run:
        profile_tag = "" if race_info.get("has_profile") else " [no profile]"
        return True, f"Would research: {name} (T{race_info['tier']}){profile_tag}", slug

    prompt = build_research_prompt(race_info)

    try:
        result, search_rounds = call_kimi_with_search(prompt, api_key)
    except Exception as e:
        return False, f"API error: {e}", slug

    if not result or len(result.strip()) < 200:
        return False, f"Too short ({len(result or '')} chars)", slug

    # Save research dump
    RESEARCH_DUMPS.mkdir(exist_ok=True)
    dump_path = RESEARCH_DUMPS / f"{slug}-raw.md"

    # Back up existing dump if present
    if dump_path.exists():
        backup = RESEARCH_DUMPS / f"{slug}-raw.bak.md"
        backup.write_text(dump_path.read_text())

    dump_path.write_text(result)
    kb = len(result) / 1024

    return True, f"Done: {kb:.1f}KB, {search_rounds} searches", slug


def show_status():
    """Show research coverage statistics."""
    profiles = list(RACE_DATA.glob("*.json"))
    dumps = list(RESEARCH_DUMPS.glob("*-raw.md"))

    substantial = sum(1 for d in dumps if d.stat().st_size / 1024 >= MIN_RESEARCH_KB)
    stubs = len(dumps) - substantial

    # Count enrichment status
    enriched = 0
    unenriched_with_research = 0
    unenriched_no_research = 0
    for f in profiles:
        data = json.loads(f.read_text())
        race = data.get("race", data)
        bor = race.get("biased_opinion_ratings", {})
        comps = ['logistics', 'length', 'technicality', 'elevation', 'climate',
                 'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
                 'community', 'field_depth', 'value', 'expenses']
        explained = sum(1 for k in comps
                        if isinstance(bor.get(k), dict) and bor[k].get("explanation", "").strip())
        if explained >= 14:
            enriched += 1
        else:
            dump = RESEARCH_DUMPS / f"{f.stem}-raw.md"
            if dump.exists() and dump.stat().st_size / 1024 >= MIN_RESEARCH_KB:
                unenriched_with_research += 1
            else:
                unenriched_no_research += 1

    # Index-only races
    index_only = 0
    if INDEX_PATH.exists():
        profile_slugs = {f.stem for f in profiles}
        index = json.loads(INDEX_PATH.read_text())
        index_only = sum(1 for e in index if e.get("slug") not in profile_slugs)

    print("\n=== RESEARCH PIPELINE STATUS ===\n")
    print(f"Profiles:           {len(profiles)}")
    print(f"  Fully enriched:   {enriched} (14/14 explanations)")
    print(f"  Need enrichment:  {unenriched_with_research} (have research, run batch_enrich.py)")
    print(f"  Need research:    {unenriched_no_research} (run batch_research.py first)")
    print(f"\nResearch dumps:     {len(dumps)}")
    print(f"  Substantial:      {substantial} (>= {MIN_RESEARCH_KB}KB)")
    print(f"  Stubs:            {stubs} (< {MIN_RESEARCH_KB}KB)")
    print(f"\nIndex-only (no profile): {index_only}")
    print(f"\n--- Pipeline ---")
    print(f"  Step 1: batch_research.py --auto N   → fills research-dumps/")
    print(f"  Step 2: batch_enrich.py --auto N      → enriches race-data/")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Batch research via Kimi K2 web search",
        epilog="Pipeline: batch_research.py (Kimi) → batch_enrich.py (Claude)"
    )
    parser.add_argument("--auto", type=int, metavar="N",
                        help="Auto-select top N research candidates")
    parser.add_argument("--slugs", nargs="+",
                        help="Research specific slugs")
    parser.add_argument("--include-no-profile", action="store_true",
                        help="Include index-only races (no profile yet)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview candidates without calling API")
    parser.add_argument("--concurrency", type=int, default=1,
                        help="Parallel API calls (default: 1, max ~10)")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="Seconds between sequential API calls (default: 2)")
    parser.add_argument("--min-research-kb", type=float, default=MIN_RESEARCH_KB,
                        help=f"Skip races with research >= this size (default: {MIN_RESEARCH_KB})")
    parser.add_argument("--status", action="store_true",
                        help="Show research pipeline coverage")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    api_key = os.environ.get("MOONSHOT_API_KEY")
    if not api_key and not args.dry_run:
        print("Error: MOONSHOT_API_KEY environment variable not set")
        print("Get your key at: https://platform.moonshot.ai/console/api-keys")
        sys.exit(1)

    # Build candidate list
    if args.slugs:
        candidates = []
        for slug in args.slugs:
            path = RACE_DATA / f"{slug}.json"
            if path.exists():
                data = json.loads(path.read_text())
                race = data.get("race", data)
                candidates.append({
                    "slug": slug,
                    "name": race.get("name", slug),
                    "location": race.get("vitals", {}).get("location", "Unknown"),
                    "distance": race.get("vitals", {}).get("distance_mi", ""),
                    "elevation": race.get("vitals", {}).get("elevation_ft", ""),
                    "website": race.get("logistics", {}).get("official_site", ""),
                    "tier": race.get("gravel_god_rating", {}).get("tier", 4),
                    "has_profile": True,
                })
            else:
                # Check index
                entry = None
                if INDEX_PATH.exists():
                    index = json.loads(INDEX_PATH.read_text())
                    entry = next((e for e in index if e.get("slug") == slug), None)
                if entry:
                    candidates.append({
                        "slug": slug,
                        "name": entry.get("name", slug),
                        "location": entry.get("location", "Unknown"),
                        "distance": entry.get("distance_mi", ""),
                        "elevation": entry.get("elevation_ft", ""),
                        "website": "",
                        "tier": entry.get("tier", 4),
                        "has_profile": False,
                    })
                else:
                    candidates.append({
                        "slug": slug, "name": slug,
                        "location": "Unknown", "distance": "",
                        "elevation": "", "website": "",
                        "tier": 4, "has_profile": False,
                    })
    elif args.auto:
        candidates = get_research_candidates(
            args.auto,
            include_no_profile=args.include_no_profile,
            min_kb=args.min_research_kb,
        )
        print(f"Auto-selected {len(candidates)} research candidates")
    else:
        parser.print_help()
        return

    if not candidates:
        print("No candidates found needing research.")
        return

    label = "DRY RUN - " if args.dry_run else ""
    print(f"\n{label}Researching {len(candidates)} races\n")

    success = 0
    failed = 0

    if args.concurrency > 1 and not args.dry_run:
        # Parallel execution
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {
                pool.submit(research_race, c, api_key, args.dry_run): c
                for c in candidates
            }
            for i, future in enumerate(as_completed(futures), 1):
                race_info = futures[future]
                try:
                    ok, msg, slug = future.result()
                    print(f"[{i}/{len(candidates)}] {slug}... {msg}")
                    if ok:
                        success += 1
                    else:
                        failed += 1
                except Exception as e:
                    print(f"[{i}/{len(candidates)}] {race_info['slug']}... Error: {e}")
                    failed += 1
    else:
        # Sequential execution
        for i, candidate in enumerate(candidates, 1):
            print(f"[{i}/{len(candidates)}] {candidate['slug']}...", end=" ", flush=True)
            ok, msg, slug = research_race(candidate, api_key, args.dry_run)
            print(msg)

            if ok:
                success += 1
            else:
                failed += 1

            if not args.dry_run and ok and i < len(candidates):
                time.sleep(args.delay)

    print(f"\nDone: {success} researched, {failed} failed")

    if success > 0 and not args.dry_run:
        print(f"\nNext step — enrich profiles from new research:")
        print(f"  ANTHROPIC_API_KEY=... python scripts/batch_enrich.py --auto {success} --delay 3")


if __name__ == "__main__":
    main()
