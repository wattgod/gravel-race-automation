#!/usr/bin/env python3
"""
youtube_extract_intel.py — Extract structured rider intelligence from YouTube transcripts.

Second enrichment pass using Claude API. Reads existing youtube_data.videos[].transcript
from race JSON files (no research files needed). Writes youtube_data.rider_intel block.

Extracts per race:
  - Key Challenges: Named course sections riders discuss most (2-4)
  - Terrain Notes: Surface condition descriptions (1-3)
  - Gear Mentions: Tire widths, bike types, equipment advice (1-2)
  - Race Day Tips: Pacing, nutrition, logistics intel (1-3)
  - Additional Quotes: Fill underrepresented categories (1-3)
  - Search Text: ~150-word factual summary for search indexing

Follows youtube_enrich.py patterns (same CLI, retry logic, validate-before-write).

Usage:
    # Extract intel for a single race
    python scripts/youtube_extract_intel.py --slug unbound-gravel

    # Preview without API calls
    python scripts/youtube_extract_intel.py --slug unbound-gravel --dry-run

    # Batch extract top N priority races
    python scripts/youtube_extract_intel.py --auto 50
    python scripts/youtube_extract_intel.py --auto 50 --dry-run

    # Force re-extraction for races that already have rider_intel
    python scripts/youtube_extract_intel.py --slug unbound-gravel --force

Requires: ANTHROPIC_API_KEY environment variable
"""

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

# Import shared utilities — single source of truth
from youtube_enrich import call_api, parse_json_response, QUOTE_CATEGORIES
from youtube_validate import validate_rider_intel

RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"


def load_race(slug: str) -> dict | None:
    """Load a race profile JSON by slug."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def get_transcripts(race_data: dict) -> list[dict]:
    """Get top 3 transcripts from youtube_data, sorted by view count descending.

    Returns list of dicts with video_id, channel, view_count, transcript (capped at 4K chars).
    """
    yt = race_data.get("race", {}).get("youtube_data", {})
    videos = yt.get("videos", [])

    with_transcript = [
        v for v in videos
        if v.get("transcript") and len(v["transcript"].strip()) > 50
    ]

    # Sort by view count descending — most-watched videos have richest intel
    with_transcript.sort(key=lambda v: v.get("view_count", 0), reverse=True)

    result = []
    for v in with_transcript[:3]:
        result.append({
            "video_id": v["video_id"],
            "channel": v.get("channel", "Unknown"),
            "view_count": v.get("view_count", 0),
            "transcript": v["transcript"][:4000],
        })
    return result


def build_intel_prompt(race_data: dict, transcripts: list[dict]) -> str:
    """Build the Claude prompt for rider intel extraction."""
    r = race_data.get("race", {})
    name = r.get("display_name") or r.get("name", "Unknown")
    location = r.get("vitals", {}).get("location", "")
    tier = r.get("gravel_god_rating", {}).get("tier_label", "")
    distance = r.get("vitals", {}).get("distance_mi", "")
    elevation = r.get("vitals", {}).get("elevation_ft", "")

    # Existing quote categories for gap analysis
    existing_quotes = r.get("youtube_data", {}).get("quotes", [])
    existing_cats = [q.get("category", "") for q in existing_quotes if q.get("curated")]

    transcripts_text = ""
    for t in transcripts:
        transcripts_text += f"""
--- Transcript from {t['channel']} ({t['view_count']:,} views) [video_id: {t['video_id']}] ---
{t['transcript']}
"""

    return f"""You are a gravel cycling analyst for Gravel God Cycling. Extract actionable rider intelligence from YouTube race video transcripts.

RACE: {name}
LOCATION: {location}
TIER: {tier}
DISTANCE: {distance} mi
ELEVATION: {elevation} ft

EXISTING QUOTE CATEGORIES: {', '.join(existing_cats) if existing_cats else 'none'}

Below are transcripts from race videos. Extract structured intelligence riders would want to know before racing.

Rules:
- Only include information that appears in the transcripts — do NOT invent or speculate
- Attribute claims to specific video_ids using source_video_ids arrays
- For key_challenges: use named sections riders actually mention (intersections, climbs, road names)
- For terrain_notes: describe what the surface FEELS like, not just what it is
- For gear_mentions: only include specific advice (tire widths, bike types) — skip vague mentions
- For race_day_tips: focus on actionable pacing, nutrition, or logistics intel
- For additional_quotes: extract 1-3 vivid quotes that fill UNDERREPRESENTED categories (logistics, training, community) — NOT course_difficulty or atmosphere unless those are the only options
- For search_text: write a ~150-word factual summary of what riders say about this race. Include course features, conditions, key challenges, and atmosphere. This is used for search indexing — be specific and factual, not promotional.
- All text fields must be plain text — no HTML, no markdown

Return ONLY valid JSON in this exact format:
{{
  "key_challenges": [
    {{"name": "Section Name", "mile_marker": "45", "description": "What riders say about this section.", "source_video_ids": ["video_id_1"]}}
  ],
  "terrain_notes": [
    {{"text": "Description of surface conditions from rider perspective.", "source_video_ids": ["video_id_1"]}}
  ],
  "gear_mentions": [
    {{"text": "Specific gear advice from riders.", "source_video_ids": ["video_id_1"]}}
  ],
  "race_day_tips": [
    {{"text": "Actionable race day advice.", "source_video_ids": ["video_id_1"]}}
  ],
  "additional_quotes": [
    {{"text": "Vivid quote filling an underrepresented category.", "source_video_id": "video_id_1", "source_channel": "Channel Name", "source_view_count": 12000, "category": "logistics", "curated": true}}
  ],
  "search_text": "150-word factual summary of what riders say about this race..."
}}

If a category has no extractable content, use an empty array [].
mile_marker is optional — only include if riders mention a specific mile/km.

TRANSCRIPTS:
{transcripts_text}
"""


def normalize_intel(intel: dict) -> dict:
    """Normalize extracted intel: coerce types before validation.

    LLMs return ints where we expect strings, strings where we expect lists.
    This must run before validate_intel().
    """
    for field in ("key_challenges", "terrain_notes", "gear_mentions", "race_day_tips"):
        items = intel.get(field, [])
        if not isinstance(items, list):
            intel[field] = []
            continue
        for item in items:
            # source_video_ids: coerce string → [string], non-list → []
            vids = item.get("source_video_ids", [])
            if isinstance(vids, str):
                item["source_video_ids"] = [vids] if vids else []
            elif not isinstance(vids, list):
                item["source_video_ids"] = []
            # mile_marker: coerce to string (int 0 must become "0", not falsy)
            if "mile_marker" in item:
                mm = item["mile_marker"]
                item["mile_marker"] = str(mm) if mm is not None else ""

    quotes = intel.get("additional_quotes", [])
    if not isinstance(quotes, list):
        intel["additional_quotes"] = []
    for q in intel.get("additional_quotes", []):
        vid = q.get("source_video_id")
        if vid is not None and not isinstance(vid, str):
            q["source_video_id"] = str(vid)

    st = intel.get("search_text")
    if st is not None and not isinstance(st, str):
        intel["search_text"] = str(st)

    return intel


    # validate_rider_intel imported from youtube_validate.py — single source of truth


def get_intel_candidates(n: int, force: bool = False) -> list[str]:
    """Find races that have transcripts but no rider_intel yet.

    Prioritizes by tier (T1 first) then score (highest first).
    """
    candidates = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            race = data.get("race", {})
        except (json.JSONDecodeError, IOError):
            continue

        yt = race.get("youtube_data", {})
        if not yt:
            continue

        # Skip if already has rider_intel (unless force)
        if yt.get("rider_intel") and not force:
            continue

        # Must have at least one transcript
        has_transcript = any(
            v.get("transcript") and len(v["transcript"].strip()) > 50
            for v in yt.get("videos", [])
        )
        if not has_transcript:
            continue

        slug = f.stem
        tier = race.get("gravel_god_rating", {}).get("tier", 4)
        score = race.get("gravel_god_rating", {}).get("overall_score", 0)
        candidates.append((tier, -score, slug))

    candidates.sort()  # T1 first, then highest score within tier
    return [slug for _, _, slug in candidates[:n]]


def extract_intel(slug: str, dry_run: bool = False, force: bool = False) -> bool:
    """Extract rider intel for a single race. Returns True on success."""
    race_data = load_race(slug)
    if not race_data:
        print(f"  SKIP {slug}: race file not found")
        return False

    yt = race_data.get("race", {}).get("youtube_data", {})
    if not yt:
        print(f"  SKIP {slug}: no youtube_data")
        return False

    if yt.get("rider_intel") and not force:
        print(f"  SKIP {slug}: already has rider_intel (use --force to re-extract)")
        return False

    transcripts = get_transcripts(race_data)
    if not transcripts:
        print(f"  SKIP {slug}: no transcripts available")
        return False

    print(f"\n  Extracting intel: {slug}")
    print(f"  Transcripts: {len(transcripts)} (top by views)")
    total_chars = sum(len(t["transcript"]) for t in transcripts)
    print(f"  Total transcript chars: {total_chars:,}")

    prompt = build_intel_prompt(race_data, transcripts)

    if dry_run:
        print(f"  [DRY RUN] Would call API with {len(prompt):,} char prompt")
        return True

    try:
        response = call_api(prompt)
        intel = parse_json_response(response)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  ERROR: Failed to parse API response: {e}")
        return False
    except Exception as e:
        print(f"  ERROR: API call failed: {e}")
        return False

    # Normalize types before validation (LLM may return int for string, string for list)
    intel = normalize_intel(intel)

    # Collect valid video IDs for cross-reference validation
    valid_video_ids = {v.get("video_id") for v in yt.get("videos", [])}

    # Validate (single source: youtube_validate.validate_rider_intel)
    errors = validate_rider_intel(slug, intel, valid_video_ids)
    if errors:
        print(f"  VALIDATION FAILED:")
        for err in errors:
            print(f"    - {err}")
        return False

    # Build rider_intel block
    rider_intel = {
        "extracted_at": date.today().isoformat(),
        "key_challenges": intel.get("key_challenges", []),
        "terrain_notes": intel.get("terrain_notes", []),
        "gear_mentions": intel.get("gear_mentions", []),
        "race_day_tips": intel.get("race_day_tips", []),
        "additional_quotes": intel.get("additional_quotes", []),
        "search_text": intel.get("search_text", ""),
    }

    # Write to race file
    race_data["race"]["youtube_data"]["rider_intel"] = rider_intel
    path = RACE_DATA_DIR / f"{slug}.json"
    with open(path, "w") as f:
        json.dump(race_data, f, indent=2, ensure_ascii=False)

    n_challenges = len(rider_intel["key_challenges"])
    n_tips = len(rider_intel["race_day_tips"])
    n_quotes = len(rider_intel["additional_quotes"])
    st_words = len(rider_intel["search_text"].split())
    print(f"  SUCCESS: {n_challenges} challenges, {n_tips} tips, {n_quotes} new quotes, {st_words}-word search text → {path.name}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Extract rider intelligence from YouTube transcripts."
    )
    parser.add_argument("--slug", nargs="+", help="Race slug(s) to extract")
    parser.add_argument("--auto", type=int, metavar="N",
                        help="Auto-extract top N priority races with transcripts")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without calling API")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds between API calls (default: 3)")
    parser.add_argument("--force", action="store_true",
                        help="Re-extract even if rider_intel already exists")
    args = parser.parse_args()

    if not args.slug and not args.auto:
        parser.error("Provide --slug or --auto")

    slugs = []
    if args.slug:
        slugs = args.slug
    elif args.auto:
        slugs = get_intel_candidates(args.auto, force=args.force)
        if not slugs:
            print("No extraction candidates found (no transcripts or all already extracted).")
            return 0
        print(f"Found {len(slugs)} extraction candidates")

    success = 0
    failed = 0
    skipped = 0

    for i, slug in enumerate(slugs):
        if i > 0 and not args.dry_run:
            time.sleep(args.delay)
        result = extract_intel(slug, args.dry_run, args.force)
        if result:
            success += 1
        else:
            # Check if it was a skip or failure
            race = load_race(slug)
            yt = (race or {}).get("race", {}).get("youtube_data", {})
            if yt.get("rider_intel") and not args.force:
                skipped += 1
            else:
                failed += 1

    print(f"\n{'='*40}")
    print(f"Rider intel extraction complete:")
    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed:  {failed}")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
