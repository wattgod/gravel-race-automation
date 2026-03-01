#!/usr/bin/env python3
"""
Batch content fill — adds missing final_verdict and course_description
sections to stub profiles using Claude API + research dumps.

Modeled on batch_enrich.py. Never overwrites existing content.

Usage:
    python scripts/batch_fill_content.py --dry-run --auto 5
    python scripts/batch_fill_content.py --auto 10
    python scripts/batch_fill_content.py --section final_verdict --auto 60
    python scripts/batch_fill_content.py --section course_description --auto 22
    python scripts/batch_fill_content.py --slugs almanzo-100 bootlegger-100

Requires: ANTHROPIC_API_KEY environment variable
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

RACE_DATA = Path(__file__).parent.parent / "race-data"
RESEARCH_DUMPS = Path(__file__).parent.parent / "research-dumps"
BRIEFS = Path(__file__).parent.parent / "briefs"
VOICE_GUIDE = Path(__file__).parent.parent / "skills" / "voice_guide.md"

SECTIONS = ["final_verdict", "course_description"]


def load_voice_guide():
    """Load Matti voice guidelines."""
    if VOICE_GUIDE.exists():
        return VOICE_GUIDE.read_text()
    return "Direct, honest, no fluff. Matti voice: peer-to-peer, specific, dark humor."


def load_research(slug):
    """Load research dump(s) or brief for a slug."""
    parts = []
    dump = RESEARCH_DUMPS / f"{slug}-raw.md"
    if dump.exists():
        parts.append(dump.read_text())
    community = RESEARCH_DUMPS / f"{slug}-community.md"
    if community.exists():
        parts.append(community.read_text())
    if parts:
        return "\n\n---\n\n".join(parts)
    brief = BRIEFS / f"{slug}-brief.md"
    if brief.exists():
        return brief.read_text()
    return None


def needs_final_verdict(race):
    """Check if profile is missing final_verdict."""
    fv = race.get("final_verdict")
    if not fv:
        return True
    if isinstance(fv, dict) and not fv.get("one_liner"):
        return True
    return False


def needs_course_description(race):
    """Check if profile is missing course_description."""
    cd = race.get("course_description")
    if not cd:
        return True
    if isinstance(cd, dict) and not cd.get("character"):
        return True
    return False


def get_fill_candidates(n, section=None, min_research_kb=3.0):
    """Get profiles needing content fill, sorted by tier/prestige.

    Args:
        n: Max candidates to return
        section: 'final_verdict', 'course_description', or None (both)
        min_research_kb: Minimum research dump size
    """
    candidates = []

    for path in sorted(RACE_DATA.glob("*.json")):
        slug = path.stem
        dump_path = RESEARCH_DUMPS / f"{slug}-raw.md"
        brief_path = BRIEFS / f"{slug}-brief.md"

        research_path = dump_path if dump_path.exists() else (brief_path if brief_path.exists() else None)
        if not research_path:
            continue
        research_kb = research_path.stat().st_size / 1024
        if research_kb < min_research_kb:
            continue

        data = json.loads(path.read_text())
        race = data.get("race", data)

        missing = []
        if section is None or section == "final_verdict":
            if needs_final_verdict(race):
                missing.append("final_verdict")
        if section is None or section == "course_description":
            if needs_course_description(race):
                missing.append("course_description")

        if not missing:
            continue

        tier = race.get("gravel_god_rating", {}).get("tier", 4)
        prestige = race.get("gravel_god_rating", {}).get("prestige", 0)
        candidates.append({
            "slug": slug,
            "tier": tier,
            "prestige": prestige,
            "research_kb": research_kb,
            "missing": missing,
        })

    # T1 first, higher prestige first, bigger research first
    candidates.sort(key=lambda r: (r["tier"], -r["prestige"], -r["research_kb"]))
    return candidates[:n]


def build_final_verdict_prompt(race, research_text, voice_guide):
    """Build prompt for generating final_verdict section."""
    name = race.get("display_name") or race.get("name", "Unknown")
    rating = race.get("gravel_god_rating", {})
    vitals = race.get("vitals", {})
    overall_score = rating.get("overall_score", 0)
    location = vitals.get("location", "Unknown")
    distance = vitals.get("distance_mi", "?")
    elevation = vitals.get("elevation_ft", "?")

    # Include existing biased_opinion if available for context
    biased_opinion = race.get("biased_opinion", "")
    if isinstance(biased_opinion, dict):
        biased_opinion = biased_opinion.get("text", "")

    return f"""You are writing the final_verdict section for a Gravel God cycling race profile.

RACE: {name}
LOCATION: {location}
DISTANCE: {distance} mi | ELEVATION: {elevation} ft
OVERALL SCORE: {overall_score} / 100
TIER: {rating.get('tier', '?')} | PRESTIGE: {rating.get('prestige', '?')}/5

EXISTING BIASED OPINION (for context, don't repeat):
{str(biased_opinion)[:1000]}

VOICE GUIDE:
{voice_guide}

RESEARCH DATA:
{research_text[:8000]}

---

Write a final_verdict for this race. This is the "bottom line" that closes the profile page.

Output ONLY valid JSON in this exact format:
{{
  "score": "{overall_score} / 100",
  "one_liner": "One punchy sentence that captures this race's essence. Think tagline, not summary.",
  "should_you_race": "2-4 sentences of real talk. Who should race this, who shouldn't, and why. Be specific about fitness level, gear, and mindset. Reference actual course features.",
  "alternatives": "2-3 sentences naming 2-3 comparable races and why someone might choose those instead. Use real race names from the gravel world."
}}

Rules:
- score must be exactly "{overall_score} / 100"
- one_liner: 1 sentence max, punchy, specific to THIS race (not generic)
- should_you_race: Direct, honest, specific. Reference real course features and conditions.
- alternatives: Name real gravel races, explain the comparison briefly
- Matti voice throughout — no corporate speak, no hype
- Use details from the research, not generic filler
- Output ONLY the JSON, no markdown, no code blocks"""


def build_course_description_prompt(race, research_text, voice_guide):
    """Build prompt for generating course_description section."""
    name = race.get("display_name") or race.get("name", "Unknown")
    vitals = race.get("vitals", {})
    location = vitals.get("location", "Unknown")
    distance = vitals.get("distance_mi", "?")
    elevation = vitals.get("elevation_ft", "?")
    terrain = vitals.get("terrain", "")

    return f"""You are writing the course_description section for a Gravel God cycling race profile.

RACE: {name}
LOCATION: {location}
DISTANCE: {distance} mi | ELEVATION: {elevation} ft
TERRAIN: {terrain}

VOICE GUIDE:
{voice_guide}

RESEARCH DATA:
{research_text[:8000]}

---

Write a course_description that tells riders what the course actually feels like to ride.

Output ONLY valid JSON in this exact format:
{{
  "character": "2-4 sentences describing the overall course personality. What makes this course unique? What's the vibe? Use specific terrain details.",
  "suffering_zones": [
    {{
      "mile": 0,
      "label": "Short name for this section (e.g. 'The Opening Salvo')",
      "desc": "1-2 sentences about what happens here. Terrain, gradient, tactical notes."
    }},
    {{
      "mile": 25,
      "label": "Another section name",
      "desc": "What riders face here."
    }},
    {{
      "mile": 50,
      "label": "Another section",
      "desc": "Description."
    }}
  ],
  "signature_challenge": "2-3 sentences about THE defining difficulty of this course. The thing everyone talks about. Be specific."
}}

Rules:
- character: specific to THIS course, not generic gravel descriptions
- suffering_zones: 3-5 entries, use actual mile markers from research when available
- suffering_zones mile values should be integers spanning the course distance ({distance} mi)
- Each suffering_zone label should be creative but informative
- signature_challenge: the ONE thing that defines this course's difficulty
- Matti voice — direct, specific, no fluff
- Use real details from research: road names, climb names, terrain types
- Do NOT include ridewithgps_id or ridewithgps_name fields
- Output ONLY the JSON, no markdown, no code blocks"""


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
                max_tokens=2000,
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


def validate_final_verdict(fv, expected_score):
    """Validate final_verdict structure."""
    if not isinstance(fv, dict):
        return False, "Not a dict"
    required = ["score", "one_liner", "should_you_race", "alternatives"]
    missing = [k for k in required if not fv.get(k)]
    if missing:
        return False, f"Missing keys: {missing}"
    # Ensure score matches
    fv["score"] = f"{expected_score} / 100"
    return True, "OK"


def validate_course_description(cd):
    """Validate course_description structure."""
    if not isinstance(cd, dict):
        return False, "Not a dict"
    if not cd.get("character"):
        return False, "Missing character"
    if not cd.get("suffering_zones") or not isinstance(cd["suffering_zones"], list):
        return False, "Missing or invalid suffering_zones"
    if len(cd["suffering_zones"]) < 2:
        return False, f"Too few suffering_zones: {len(cd['suffering_zones'])}"
    if not cd.get("signature_challenge"):
        return False, "Missing signature_challenge"
    # Validate each suffering zone has required fields
    for i, zone in enumerate(cd["suffering_zones"]):
        if not isinstance(zone, dict):
            return False, f"suffering_zones[{i}] not a dict"
        if "label" not in zone or "desc" not in zone:
            return False, f"suffering_zones[{i}] missing label or desc"
        # Ensure mile is an int
        if "mile" in zone:
            zone["mile"] = int(zone["mile"])
    return True, "OK"


def fill_profile(slug, section=None, dry_run=False):
    """Fill missing content for a single profile. Returns (success, message)."""
    profile_path = RACE_DATA / f"{slug}.json"
    if not profile_path.exists():
        return False, f"No profile: {slug}.json"

    data = json.loads(profile_path.read_text())
    race = data.get("race", data)

    # Determine what needs filling
    fill_fv = (section is None or section == "final_verdict") and needs_final_verdict(race)
    fill_cd = (section is None or section == "course_description") and needs_course_description(race)

    if not fill_fv and not fill_cd:
        return False, f"Already complete: {slug}"

    research = load_research(slug)
    if not research:
        return False, f"No research dump: {slug}"

    voice_guide = load_voice_guide()
    labels = []
    if fill_fv:
        labels.append("final_verdict")
    if fill_cd:
        labels.append("course_description")

    if dry_run:
        return True, f"Would fill: {slug} ({', '.join(labels)}, {len(research)} chars research)"

    filled = []

    # Fill final_verdict
    if fill_fv:
        try:
            prompt = build_final_verdict_prompt(race, research, voice_guide)
            response_text = call_api(prompt)
            fv = parse_json_response(response_text)
            expected_score = race.get("gravel_god_rating", {}).get("overall_score", 0)
            valid, reason = validate_final_verdict(fv, expected_score)
            if not valid:
                return False, f"Invalid final_verdict for {slug}: {reason}"
            race["final_verdict"] = fv
            filled.append("final_verdict")
        except json.JSONDecodeError as e:
            return False, f"Bad JSON (final_verdict) for {slug}: {e}"
        except Exception as e:
            return False, f"API error (final_verdict) for {slug}: {e}"

    # Small delay between API calls for same profile
    if fill_fv and fill_cd:
        time.sleep(2)

    # Fill course_description
    if fill_cd:
        try:
            prompt = build_course_description_prompt(race, research, voice_guide)
            response_text = call_api(prompt)
            cd = parse_json_response(response_text)
            valid, reason = validate_course_description(cd)
            if not valid:
                return False, f"Invalid course_description for {slug}: {reason}"
            race["course_description"] = cd
            filled.append("course_description")
        except json.JSONDecodeError as e:
            return False, f"Bad JSON (course_description) for {slug}: {e}"
        except Exception as e:
            return False, f"API error (course_description) for {slug}: {e}"

    # Write back
    if "race" in data:
        data["race"] = race
    else:
        data = race

    profile_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return True, f"Filled: {slug} ({', '.join(filled)})"


def main():
    parser = argparse.ArgumentParser(description="Batch content fill for stub profiles")
    parser.add_argument("--auto", type=int, metavar="N",
                        help="Auto-select top N candidates")
    parser.add_argument("--slugs", nargs="+", help="Specific slugs to fill")
    parser.add_argument("--section", choices=SECTIONS,
                        help="Fill only this section (default: both)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without calling API or writing files")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds between profiles (default: 3)")
    parser.add_argument("--min-research-kb", type=float, default=3.0,
                        help="Minimum research dump size in KB (default: 3.0)")
    args = parser.parse_args()

    if args.auto:
        candidates = get_fill_candidates(args.auto, section=args.section,
                                         min_research_kb=args.min_research_kb)
        slugs = [c["slug"] for c in candidates]
        section_label = args.section or "all"
        print(f"Auto-selected {len(slugs)} candidates (section: {section_label})")
        for c in candidates[:5]:
            print(f"  T{c['tier']} p{c['prestige']} {c['slug']} ({', '.join(c['missing'])})")
        if len(candidates) > 5:
            print(f"  ... and {len(candidates) - 5} more")
    elif args.slugs:
        slugs = args.slugs
    else:
        parser.print_help()
        return

    print(f"\n{'DRY RUN - ' if args.dry_run else ''}FILLING {len(slugs)} profiles\n")

    success = 0
    failed = 0
    skipped = 0

    for i, slug in enumerate(slugs, 1):
        print(f"[{i}/{len(slugs)}] {slug}...", end=" ", flush=True)
        ok, msg = fill_profile(slug, section=args.section, dry_run=args.dry_run)
        print(msg)

        if ok:
            success += 1
        elif "Already complete" in msg or "No research dump" in msg:
            skipped += 1
        else:
            failed += 1

        # Rate limiting delay between profiles
        if not args.dry_run and ok and i < len(slugs):
            time.sleep(args.delay)

    print(f"\nDone: {success} filled, {skipped} skipped, {failed} failed")


if __name__ == "__main__":
    main()
