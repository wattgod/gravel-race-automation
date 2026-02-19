#!/usr/bin/env python3
"""Targeted rewrite of remaining generic explanations using Claude API.

Finds explanations that lack proper nouns, numbers, or quotes and rewrites
them using available data (community dump, vitals, race details).

Usage:
    python scripts/generic_killer.py              # Rewrite all generics
    python scripts/generic_killer.py --dry-run    # Preview what would be rewritten
    python scripts/generic_killer.py --limit 5    # Only do 5
"""

import json
import os
import pathlib
import re
import sys
import time

RACE_DATA = pathlib.Path(__file__).parent.parent / "race-data"
RESEARCH_DIR = pathlib.Path(__file__).parent.parent / "research-dumps"


def load_dotenv():
    """Load .env file into os.environ."""
    env_file = pathlib.Path(__file__).parent.parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ[key.strip()] = value.strip()


def is_generic(explanation: str) -> bool:
    """Check if an explanation is generic (no proper nouns, numbers, quotes, or places)."""
    has_name = bool(re.search(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', explanation))
    has_number = bool(re.search(r'\d+', explanation))
    has_quote = bool(re.search(r'["\u201c\u201d][^"\u201c\u201d]{10,}["\u201c\u201d]', explanation))
    has_place = bool(re.search(r'(?:in|at|near|from|through)\s+[A-Z][a-z]{2,}', explanation))
    return not has_name and not has_number and not has_quote and not has_place


def find_generics() -> list[dict]:
    """Find all generic explanations across all race profiles."""
    generics = []
    for f in sorted(RACE_DATA.glob("*.json")):
        d = json.loads(f.read_text())
        race = d.get("race", d)
        bor = race.get("biased_opinion_ratings", {})
        for criterion, entry in bor.items():
            if not isinstance(entry, dict):
                continue
            exp = entry.get("explanation", "")
            if exp and is_generic(exp):
                generics.append({
                    "file": f,
                    "slug": f.stem,
                    "criterion": criterion,
                    "explanation": exp,
                    "score": entry.get("score", 0),
                })
    return generics


def build_prompt(slug: str, criterion: str, current_explanation: str,
                 score: int, race_data: dict) -> str:
    """Build a focused rewrite prompt."""
    vitals = race_data.get("vitals", {})
    name = race_data.get("display_name", race_data.get("name", slug))
    location = vitals.get("location", "")
    distance = vitals.get("distance_mi", "")
    elevation = vitals.get("elevation_ft", "")

    # Load community dump for context
    dump_file = RESEARCH_DIR / f"{slug}-community.md"
    community_context = ""
    if dump_file.exists():
        text = dump_file.read_text()
        # Take first 2000 chars of community dump for context
        community_context = text[:2000]

    return f"""Rewrite this race criterion explanation to be more specific and concrete.

RACE: {name}
LOCATION: {location}
DISTANCE: {distance} miles
ELEVATION: {elevation} ft
CRITERION: {criterion}
SCORE: {score}/5
CURRENT EXPLANATION: {current_explanation}

COMMUNITY DATA (use specific details from this):
{community_context}

RULES:
1. Keep the same score perspective (if score is low, keep the critical tone; if high, keep the positive tone)
2. Must include at least ONE of: a specific place name, a number/statistic, or a rider quote from the community data
3. Keep it 100-400 characters
4. Keep the opinionated, honest voice — no marketing fluff
5. Do NOT change the score
6. Return ONLY the rewritten explanation text, nothing else
7. Do NOT start with the race name"""


def rewrite_with_claude(prompt: str) -> str | None:
    """Call Claude API to rewrite an explanation."""
    import urllib.request

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return None

    body = json.dumps({
        "model": "claude-sonnet-4-5-20250929",
        "max_tokens": 300,
        "messages": [{"role": "user", "content": prompt}],
    })

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body.encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            return result["content"][0]["text"].strip()
    except Exception as e:
        print(f"  API error: {e}")
        return None


def main():
    load_dotenv()

    dry_run = "--dry-run" in sys.argv
    limit = None
    if "--limit" in sys.argv:
        idx = sys.argv.index("--limit")
        limit = int(sys.argv[idx + 1])

    generics = find_generics()
    print(f"Found {len(generics)} generic explanations")

    if limit:
        generics = generics[:limit]
        print(f"Processing {limit} (--limit)")

    if dry_run:
        for g in generics:
            print(f"  {g['slug']}.{g['criterion']} (score={g['score']}): {g['explanation'][:100]}...")
        print(f"\n[DRY RUN] Would rewrite {len(generics)} explanations")
        return

    # Group by file for efficient I/O
    by_file = {}
    for g in generics:
        by_file.setdefault(str(g["file"]), []).append(g)

    total_rewritten = 0
    total_failed = 0

    for file_path, file_generics in sorted(by_file.items()):
        f = pathlib.Path(file_path)
        d = json.loads(f.read_text())
        race = d.get("race", d)
        bor = race.get("biased_opinion_ratings", {})
        modified = False

        for g in file_generics:
            criterion = g["criterion"]
            prompt = build_prompt(g["slug"], criterion, g["explanation"],
                                  g["score"], race)

            new_text = rewrite_with_claude(prompt)
            if new_text:
                # Validate: must not be generic anymore
                if is_generic(new_text):
                    print(f"  {g['slug']}.{criterion}: rewrite still generic, skipping")
                    total_failed += 1
                    continue

                # Validate length
                if len(new_text) < 50 or len(new_text) > 600:
                    print(f"  {g['slug']}.{criterion}: rewrite bad length ({len(new_text)}), skipping")
                    total_failed += 1
                    continue

                bor[criterion]["explanation"] = new_text
                modified = True
                total_rewritten += 1
                print(f"  [{total_rewritten}] {g['slug']}.{criterion} ✓")
            else:
                total_failed += 1

            # Rate limit: ~50 req/min for Sonnet
            time.sleep(1.5)

        if modified:
            f.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")

    print(f"\nRewritten: {total_rewritten}, Failed: {total_failed}")


if __name__ == "__main__":
    main()
