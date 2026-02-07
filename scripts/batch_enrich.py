#!/usr/bin/env python3
"""
Batch profile enrichment — adds biased_opinion_ratings explanations
to thin profiles using existing research dumps.

Reads existing profile + research dump, calls Claude API to generate
per-criterion explanations in Matti voice, merges result back.

Usage:
    python scripts/batch_enrich.py --auto 10        # Enrich top 10 priority
    python scripts/batch_enrich.py --slugs unbound-200 mid-south  # Specific races
    python scripts/batch_enrich.py --dry-run --auto 5  # Preview without writing
    python scripts/batch_enrich.py --auto 50 --delay 5 # Batch with 5s delay

Requires: ANTHROPIC_API_KEY environment variable
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

RACE_DATA = Path(__file__).parent.parent / "race-data"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"
BRIEFS = Path(__file__).parent.parent / "briefs"
VOICE_GUIDE = Path(__file__).parent.parent / "skills" / "voice_guide.md"

SCORE_COMPONENTS = [
    'logistics', 'length', 'technicality', 'elevation', 'climate',
    'altitude', 'adventure', 'prestige', 'race_quality', 'experience',
    'community', 'field_depth', 'value', 'expenses'
]

# Add parent dir for triage import
sys.path.insert(0, str(Path(__file__).parent))


def load_voice_guide():
    """Load Matti voice guidelines."""
    if VOICE_GUIDE.exists():
        return VOICE_GUIDE.read_text()
    return "Direct, honest, no fluff. Matti voice: peer-to-peer, specific, dark humor."


def get_enrichment_candidates(n, min_research_kb=5.0):
    """Get top N enrichment candidates.

    Finds profiles that:
    1. Have a substantial research dump (>5KB by default)
    2. Need biased_opinion_ratings enrichment (<7 explanations)

    Sorted by tier (T1 first) then research dump size.
    """
    candidates = []

    for path in sorted(RACE_DATA.glob("*.json")):
        slug = path.stem
        dump_path = RESEARCH_DUMPS / f"{slug}-raw.md"
        if not dump_path.exists():
            continue
        dump_kb = dump_path.stat().st_size / 1024
        if dump_kb < min_research_kb:
            continue

        data = json.loads(path.read_text())
        race = data.get("race", data)
        if not needs_enrichment(race):
            continue

        tier = race.get("gravel_god_rating", {}).get("tier", 4)
        prestige = race.get("gravel_god_rating", {}).get("prestige", 0)
        candidates.append({
            "slug": slug,
            "tier": tier,
            "prestige": prestige,
            "research_kb": dump_kb,
        })

    # T1 first, then T2, etc. Within tier, bigger research = better.
    candidates.sort(key=lambda r: (-r["tier"], -r["research_kb"]))
    candidates.sort(key=lambda r: r["tier"])
    return [r["slug"] for r in candidates[:n]]


def load_research(slug):
    """Load research dump or brief for a slug."""
    dump = RESEARCH_DUMPS / f"{slug}-raw.md"
    if dump.exists():
        return dump.read_text()
    brief = BRIEFS / f"{slug}-brief.md"
    if brief.exists():
        return brief.read_text()
    return None


def needs_enrichment(race):
    """Check if profile needs biased_opinion_ratings enrichment."""
    bor = race.get("biased_opinion_ratings", {})
    if not bor or not isinstance(bor, dict):
        return True
    # Check if any entry has a real explanation
    explained = sum(1 for v in bor.values()
                    if isinstance(v, dict) and v.get("explanation", "").strip())
    return explained < 7


def build_enrichment_prompt(race, research_text, voice_guide):
    """Build the API prompt for enrichment."""
    name = race.get("name", "Unknown")
    rating = race.get("gravel_god_rating", {})
    scores = {k: rating.get(k, 3) for k in SCORE_COMPONENTS}
    location = race.get("vitals", {}).get("location", "Unknown")
    distance = race.get("vitals", {}).get("distance_mi", "?")
    elevation = race.get("vitals", {}).get("elevation_ft", "?")

    scores_block = "\n".join(f"  - {k}: {v}/5" for k, v in scores.items())

    return f"""You are writing biased_opinion_ratings for the Gravel God cycling race database.

RACE: {name}
LOCATION: {location}
DISTANCE: {distance} mi | ELEVATION: {elevation} ft

EXISTING SCORES (1-5 each):
{scores_block}

VOICE GUIDE (write in this voice):
{voice_guide[:800]}

RESEARCH DATA:
{research_text[:8000]}

---

For EACH of the 14 scoring criteria below, write a 2-4 sentence explanation justifying the score. Use specific details from the research — real place names, real numbers, real rider quotes. No generic filler.

Output ONLY valid JSON in this exact format:
{{
  "prestige": {{
    "score": {scores.get('prestige', 3)},
    "explanation": "..."
  }},
  "race_quality": {{
    "score": {scores.get('race_quality', 3)},
    "explanation": "..."
  }},
  "experience": {{
    "score": {scores.get('experience', 3)},
    "explanation": "..."
  }},
  "community": {{
    "score": {scores.get('community', 3)},
    "explanation": "..."
  }},
  "field_depth": {{
    "score": {scores.get('field_depth', 3)},
    "explanation": "..."
  }},
  "value": {{
    "score": {scores.get('value', 3)},
    "explanation": "..."
  }},
  "expenses": {{
    "score": {scores.get('expenses', 3)},
    "explanation": "..."
  }},
  "length": {{
    "score": {scores.get('length', 3)},
    "explanation": "..."
  }},
  "technicality": {{
    "score": {scores.get('technicality', 3)},
    "explanation": "..."
  }},
  "elevation": {{
    "score": {scores.get('elevation', 3)},
    "explanation": "..."
  }},
  "climate": {{
    "score": {scores.get('climate', 3)},
    "explanation": "..."
  }},
  "altitude": {{
    "score": {scores.get('altitude', 3)},
    "explanation": "..."
  }},
  "logistics": {{
    "score": {scores.get('logistics', 3)},
    "explanation": "..."
  }},
  "adventure": {{
    "score": {scores.get('adventure', 3)},
    "explanation": "..."
  }}
}}

Rules:
- Keep the existing scores — don't change them
- Each explanation: 2-4 sentences, specific, Matti voice
- Reference specific course features, weather data, logistics details from research
- No generic filler ("amazing experience", "world-class")
- If research lacks detail for a criterion, say what you know honestly
- Output ONLY the JSON object, no markdown, no code blocks"""


def call_api(prompt, max_retries=3, retry_delay=30):
    """Call Claude API with retry logic."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt < max_retries - 1:
                wait = retry_delay * (attempt + 1)
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def parse_json_response(text):
    """Parse JSON from API response, handling code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def enrich_profile(slug, dry_run=False):
    """Enrich a single profile. Returns (success, message)."""
    profile_path = RACE_DATA / f"{slug}.json"
    if not profile_path.exists():
        return False, f"No profile: {slug}.json"

    data = json.loads(profile_path.read_text())
    race = data.get("race", data)

    if not needs_enrichment(race):
        return False, f"Already enriched: {slug}"

    research = load_research(slug)
    if not research:
        return False, f"No research dump: {slug}"

    voice_guide = load_voice_guide()
    prompt = build_enrichment_prompt(race, research, voice_guide)

    if dry_run:
        return True, f"Would enrich: {slug} ({len(research)} chars research)"

    try:
        response_text = call_api(prompt)
        enriched = parse_json_response(response_text)
    except json.JSONDecodeError as e:
        return False, f"Bad JSON from API: {e}"
    except Exception as e:
        return False, f"API error: {e}"

    # Validate response has expected structure
    if not isinstance(enriched, dict):
        return False, f"API returned non-dict: {type(enriched)}"

    valid_keys = set(SCORE_COMPONENTS)
    response_keys = set(enriched.keys())
    if not response_keys.intersection(valid_keys):
        return False, f"API response has no valid keys: {response_keys}"

    # Merge: set biased_opinion_ratings, preserving scores from gravel_god_rating
    rating = race.get("gravel_god_rating", {})
    for key in SCORE_COMPONENTS:
        if key in enriched and isinstance(enriched[key], dict):
            # Keep the existing score from gravel_god_rating
            enriched[key]["score"] = rating.get(key, enriched[key].get("score", 3))

    race["biased_opinion_ratings"] = enriched

    # Write back
    if "race" in data:
        data["race"] = race
    else:
        data = race

    profile_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    explained = sum(1 for v in enriched.values()
                    if isinstance(v, dict) and v.get("explanation", "").strip())
    return True, f"Enriched: {slug} ({explained}/14 explanations)"


def main():
    parser = argparse.ArgumentParser(description="Batch profile enrichment")
    parser.add_argument("--auto", type=int, metavar="N",
                        help="Auto-select top N enrichment candidates")
    parser.add_argument("--slugs", nargs="+", help="Specific slugs to enrich")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without calling API or writing files")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds between API calls (default: 3)")
    args = parser.parse_args()

    if args.auto:
        slugs = get_enrichment_candidates(args.auto)
        print(f"Auto-selected {len(slugs)} candidates")
    elif args.slugs:
        slugs = args.slugs
    else:
        parser.print_help()
        return

    print(f"\n{'DRY RUN - ' if args.dry_run else ''}Enriching {len(slugs)} profiles\n")

    success = 0
    failed = 0
    skipped = 0

    for i, slug in enumerate(slugs, 1):
        print(f"[{i}/{len(slugs)}] {slug}...", end=" ", flush=True)
        ok, msg = enrich_profile(slug, dry_run=args.dry_run)
        print(msg)

        if ok:
            success += 1
        elif "Already enriched" in msg or "No research dump" in msg:
            skipped += 1
        else:
            failed += 1

        # Rate limiting delay between API calls
        if not args.dry_run and ok and i < len(slugs):
            time.sleep(args.delay)

    print(f"\nDone: {success} enriched, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
