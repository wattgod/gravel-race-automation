#!/usr/bin/env python3
"""
youtube_enrich.py — Transform raw YouTube research into curated youtube_data.

Takes raw youtube_research.py output (or searches inline) and uses Claude API to:
  - Curate videos: select the best 3 from raw results
  - Extract quotes: pull specific, experiential quotes from transcripts
  - Assign display orders and categories

Follows batch_enrich.py patterns (load -> prompt -> validate -> write).

Usage:
    # Enrich a single race from existing research output
    python scripts/youtube_enrich.py --slug migration-gravel-race

    # Enrich from a saved research file
    python scripts/youtube_enrich.py --slug migration-gravel-race --research-file youtube-research-results/migration-gravel-race.json

    # Preview without writing
    python scripts/youtube_enrich.py --slug migration-gravel-race --dry-run

    # Batch enrich top N races by priority
    python scripts/youtube_enrich.py --auto 50 --dry-run
    python scripts/youtube_enrich.py --auto 50

Requires: ANTHROPIC_API_KEY environment variable
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"
RESEARCH_DIR = Path(__file__).resolve().parent.parent / "youtube-research-results"

VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
QUOTE_CATEGORIES = {"race_atmosphere", "course_difficulty", "community", "logistics", "training", "generic"}


def load_race(slug: str) -> dict | None:
    """Load a race profile JSON by slug."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def load_research(slug: str, research_file: str = None) -> dict | None:
    """Load research results for a race."""
    if research_file:
        path = Path(research_file)
    else:
        path = RESEARCH_DIR / f"{slug}.json"

    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def extract_video_id(url: str) -> str:
    """Extract 11-char video ID from various YouTube URL formats."""
    patterns = [
        r'(?:v=|/v/|youtu\.be/)([A-Za-z0-9_-]{11})',
        r'(?:embed/)([A-Za-z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url or '')
        if m:
            return m.group(1)
    return ''


def build_enrichment_prompt(race_data: dict, research: dict) -> str:
    """Build the Claude prompt for YouTube curation + quote extraction."""
    r = race_data.get("race", {})
    name = r.get("display_name") or r.get("name", "Unknown")
    location = r.get("vitals", {}).get("location", "")
    tier = r.get("gravel_god_rating", {}).get("tier_label", "")

    videos_text = ""
    for i, v in enumerate(research.get("videos", [])):
        vid_id = extract_video_id(v.get("url", ""))
        transcript_excerpt = ""
        if v.get("transcript"):
            transcript_excerpt = v["transcript"][:3000]

        videos_text += f"""
--- Video {i+1} ---
Title: {v.get('title', 'N/A')}
Channel: {v.get('channel', 'N/A')}
Views: {v.get('view_count', 'N/A')}
Upload date: {v.get('upload_date', 'N/A')}
Duration: {v.get('duration_string', 'N/A')}
Video ID: {vid_id}
URL: {v.get('url', 'N/A')}
Description excerpt: {(v.get('description', '') or '')[:500]}
{"Transcript excerpt: " + transcript_excerpt if transcript_excerpt else "No transcript available."}
"""

    return f"""You are a gravel cycling content curator for Gravel God Cycling.

RACE: {name}
LOCATION: {location}
TIER: {tier}

Below are YouTube videos found for this race. Your job:

1. SELECT the best 1-3 videos for embedding on the race profile page. Prefer:
   - First-person race recaps and ride-alongs (>1K views)
   - Course previews with specific terrain/difficulty details
   - Recent (2023-2025) over older
   - Good production quality channels
   - REJECT generic news clips, pure promotional content, or unrelated videos

2. EXTRACT 1-3 specific, experiential quotes from the transcripts (if available).
   - Quotes should be vivid, specific to THIS race (not generic "great race" fluff)
   - Focus on course conditions, race atmosphere, key challenges, memorable moments
   - Each quote must reference a source_video_id from the videos you selected
   - 1-3 sentences each, suitable for a blockquote

Return ONLY valid JSON in this exact format:
{{
  "videos": [
    {{
      "video_id": "11-char-id",
      "title": "Video title",
      "channel": "Channel name",
      "view_count": 12345,
      "upload_date": "YYYYMMDD",
      "duration_string": "MM:SS",
      "curated": true,
      "curation_reason": "Why this video was selected (1 sentence)",
      "display_order": 1
    }}
  ],
  "quotes": [
    {{
      "text": "The exact quote text, cleaned up from transcript.",
      "source_video_id": "11-char-id",
      "source_channel": "Channel name",
      "source_view_count": 12345,
      "category": "race_atmosphere",
      "curated": true
    }}
  ]
}}

Category options: race_atmosphere, course_difficulty, community, logistics, training, generic

If no videos are worth curating, return {{"videos": [], "quotes": []}}.

VIDEOS:
{videos_text}
"""


def call_api(prompt: str, max_retries: int = 3, retry_delay: int = 30) -> str:
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


def parse_json_response(text: str) -> dict:
    """Parse JSON from API response, handling code blocks."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def validate_enrichment(slug: str, enriched: dict) -> list[str]:
    """Validate the enriched youtube_data. Returns list of error strings."""
    errors = []
    videos = enriched.get("videos", [])
    quotes = enriched.get("quotes", [])
    video_ids = {v.get("video_id") for v in videos}

    for v in videos:
        vid = v.get("video_id", "")
        if not VIDEO_ID_RE.match(vid):
            errors.append(f"Invalid video_id: '{vid}'")
        if not v.get("curation_reason"):
            errors.append(f"Video '{vid}' missing curation_reason")

    for q in quotes:
        src = q.get("source_video_id", "")
        if src not in video_ids:
            errors.append(f"Quote references unknown video_id: '{src}'")
        cat = q.get("category", "")
        if cat not in QUOTE_CATEGORIES:
            errors.append(f"Quote has invalid category: '{cat}'")

    orders = [v.get("display_order") for v in videos if "display_order" in v]
    if len(orders) != len(set(orders)):
        errors.append(f"Duplicate display_order values: {orders}")

    if len(videos) > 3:
        errors.append(f"Too many videos: {len(videos)} (max 3)")
    if len(quotes) > 6:
        errors.append(f"Too many quotes: {len(quotes)} (max 6)")

    return errors


def get_enrichment_candidates(n: int) -> list[str]:
    """Find races that don't yet have youtube_data, prioritizing thinnest profiles."""
    candidates = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            race = data.get("race", {})
        except (json.JSONDecodeError, IOError):
            continue

        if "youtube_data" in race:
            continue

        slug = f.stem
        # Check if research exists
        research_path = RESEARCH_DIR / f"{slug}.json"
        if not research_path.exists():
            continue

        # Priority: lower tier races (thinner content) first
        tier = race.get("gravel_god_rating", {}).get("tier", 4)
        score = race.get("gravel_god_rating", {}).get("overall_score", 0)
        candidates.append((tier, -score, slug))

    candidates.sort()  # Lower tier first, then lower score
    return [slug for _, _, slug in candidates[:n]]


def enrich_profile(slug: str, research_file: str = None, dry_run: bool = False) -> bool:
    """Enrich a single race profile with youtube_data. Returns True on success."""
    race_data = load_race(slug)
    if not race_data:
        print(f"  SKIP {slug}: race file not found")
        return False

    if race_data.get("race", {}).get("youtube_data"):
        print(f"  SKIP {slug}: already has youtube_data")
        return False

    research = load_research(slug, research_file)
    if not research:
        print(f"  SKIP {slug}: no research data found")
        return False

    if not research.get("videos"):
        print(f"  SKIP {slug}: no videos in research")
        return False

    print(f"\n  Enriching: {slug}")
    print(f"  Videos found: {research.get('video_count', len(research.get('videos', [])))}")

    prompt = build_enrichment_prompt(race_data, research)

    if dry_run:
        print(f"  [DRY RUN] Would call API with {len(prompt)} char prompt")
        print(f"  [DRY RUN] Videos available: {len(research.get('videos', []))}")
        return True

    try:
        response = call_api(prompt)
        enriched = parse_json_response(response)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  ERROR: Failed to parse API response: {e}")
        return False
    except Exception as e:
        print(f"  ERROR: API call failed: {e}")
        return False

    # Validate
    errors = validate_enrichment(slug, enriched)
    if errors:
        print(f"  VALIDATION FAILED:")
        for err in errors:
            print(f"    - {err}")
        return False

    # Build youtube_data block
    youtube_data = {
        "researched_at": date.today().isoformat(),
        "videos": enriched.get("videos", []),
        "quotes": enriched.get("quotes", []),
    }

    # Write to race file
    race_data["race"]["youtube_data"] = youtube_data
    path = RACE_DATA_DIR / f"{slug}.json"
    with open(path, "w") as f:
        json.dump(race_data, f, indent=2, ensure_ascii=False)

    n_videos = len([v for v in youtube_data["videos"] if v.get("curated")])
    n_quotes = len([q for q in youtube_data["quotes"] if q.get("curated")])
    print(f"  SUCCESS: {n_videos} videos, {n_quotes} quotes written to {path.name}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Enrich race profiles with curated YouTube data."
    )
    parser.add_argument("--slug", nargs="+", help="Race slug(s) to enrich")
    parser.add_argument("--auto", type=int, metavar="N",
                        help="Auto-enrich top N priority races with research data")
    parser.add_argument("--research-file", help="Path to research JSON file (for --slug)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview what would be enriched without calling API")
    parser.add_argument("--delay", type=int, default=3,
                        help="Seconds between API calls (default: 3)")
    args = parser.parse_args()

    if not args.slug and not args.auto:
        parser.error("Provide --slug or --auto")

    slugs = []
    if args.slug:
        slugs = args.slug
    elif args.auto:
        slugs = get_enrichment_candidates(args.auto)
        if not slugs:
            print("No enrichment candidates found (no research data or all already enriched).")
            return 0
        print(f"Found {len(slugs)} enrichment candidates")

    success = 0
    failed = 0
    skipped = 0

    for i, slug in enumerate(slugs):
        if i > 0 and not args.dry_run:
            time.sleep(args.delay)
        result = enrich_profile(slug, args.research_file, args.dry_run)
        if result:
            success += 1
        else:
            # Check if it was a skip or failure
            race = load_race(slug)
            if race and race.get("race", {}).get("youtube_data"):
                skipped += 1
            else:
                failed += 1

    print(f"\n{'='*40}")
    print(f"YouTube enrichment complete:")
    print(f"  Success: {success}")
    print(f"  Skipped: {skipped}")
    print(f"  Failed:  {failed}")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
