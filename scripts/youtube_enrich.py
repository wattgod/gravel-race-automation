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
    tier_label = r.get("gravel_god_rating", {}).get("tier_label", "")
    tier_num = r.get("gravel_god_rating", {}).get("tier", 4)

    # Tier-aware view count guidance
    if tier_num == 1:
        view_guidance = "Prefer videos with >5,000 views for Tier 1 races"
    elif tier_num == 2:
        view_guidance = "Prefer videos with >1,000 views for Tier 2 races"
    else:
        view_guidance = "No minimum view count for Tier 3/4 races — accept any quality content"

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
TIER: {tier_label}

Below are YouTube videos found for this race. Your job:

1. SELECT the best 1-3 videos for embedding on the race profile page.

   PREFER:
   - Rider-filmed POV and vlog content (first-person race recaps, ride-alongs)
   - Course previews with specific terrain/difficulty details
   - Recent (2023-2026) over older
   - {view_guidance}

   REJECT (do NOT curate these):
   - Indoor trainer videos (TacxRLV, BKool, Rouvy, Kinomap, Zwift, "virtual ride")
   - Auto-generated compilations, slideshows, or photo montages
   - Pure promotional reels or official channel ads with no rider perspective
   - Videos shorter than 3 minutes or longer than 2 hours
   - Generic news clips or unrelated videos

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


def _log_api_usage(response, model: str, script: str) -> None:
    """Best-effort log API token usage to gg_api_usage via Supabase REST API."""
    try:
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens

        # Calculate cost
        pricing = {
            "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
            "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.00},
        }
        rates = pricing.get(model, {"input": 3.00, "output": 15.00})
        cost = (tokens_in / 1_000_000) * rates["input"] + (tokens_out / 1_000_000) * rates["output"]

        # Direct REST API call — no MC import dependency
        import urllib.request
        import json as _json

        supabase_url = os.environ.get("SUPABASE_URL", "")
        supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not supabase_url or not supabase_key:
            return

        url = f"{supabase_url}/rest/v1/gg_api_usage"
        payload = _json.dumps({
            "provider": "anthropic",
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": round(cost, 6),
            "script": script,
        }).encode()

        req = urllib.request.Request(url, data=payload, method="POST", headers={
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        })
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass  # Never break API calls if logging fails


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
            _log_api_usage(response, "claude-sonnet-4-20250514", "youtube_enrich")
            return response.content[0].text
        except anthropic.RateLimitError:
            if attempt < max_retries - 1:
                wait = retry_delay * (attempt + 1)
                print(f"  Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def call_api_vision(prompt: str, images: list[dict], max_retries: int = 3,
                     retry_delay: int = 30) -> str:
    """Call Claude API with images (multimodal). Returns text response.

    Args:
        prompt: Text prompt to send.
        images: List of image content blocks, each with type/source keys
                matching the Anthropic Messages API image format.
        max_retries: Number of retry attempts on rate limit.
        retry_delay: Base delay in seconds between retries.
    """
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Build content array: images first, then text prompt
    content = list(images) + [{"type": "text", "text": prompt}]

    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": content}]
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


def build_enrichment_with_vision(race_data: dict, research: dict) -> tuple[str, list[dict]]:
    """Build enrichment prompt with thumbnail images for Claude vision API.

    Fetches thumbnails for candidate videos and converts them to base64
    image blocks for the Anthropic vision API.

    Returns (prompt_text, image_blocks) where image_blocks is a list of
    Anthropic image content blocks. Falls back to (prompt, []) on failure.
    """
    import base64

    prompt = build_enrichment_prompt(race_data, research)
    image_blocks = []

    try:
        from youtube_thumbnail import fetch_thumbnail
    except ImportError:
        return prompt, []

    # Append vision guidance to prompt
    vision_guidance = """

THUMBNAIL QUALITY GUIDANCE (you can see the thumbnails above):
Reject videos with dark/blurry/all-text/clickbait thumbnails.
Prefer thumbnails showing cycling scenery, course conditions, or race atmosphere.
A good thumbnail strongly correlates with good video content.
"""
    prompt += vision_guidance

    for v in research.get("videos", []):
        vid_id = extract_video_id(v.get("url", ""))
        if not vid_id:
            continue
        try:
            img_bytes, _ = fetch_thumbnail(vid_id)
            if not img_bytes:
                continue
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            image_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": b64,
                },
            })
            # Add a text label for this image
            image_blocks.append({
                "type": "text",
                "text": f"[Thumbnail for Video: {v.get('title', 'Unknown')} — ID: {vid_id}]",
            })
        except Exception:
            continue  # Skip thumbnails that fail to fetch

    return prompt, image_blocks


def _parse_duration_seconds(duration_string: str) -> int:
    """Parse YouTube duration string (MM:SS or H:MM:SS) to seconds. Returns 0 on failure."""
    if not duration_string or not isinstance(duration_string, str):
        return 0
    parts = duration_string.strip().split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 1:
        return nums[0]
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0


MIN_DURATION_SEC = 180   # 3 minutes
MAX_DURATION_SEC = 7200  # 2 hours


def validate_enrichment(slug: str, enriched: dict) -> list[str]:
    """Validate the enriched youtube_data. Returns list of error strings."""
    errors = []
    videos = enriched.get("videos", [])
    quotes = enriched.get("quotes", [])
    video_ids = {v.get("video_id") for v in videos}

    for v in videos:
        vid = str(v.get("video_id", ""))
        v["video_id"] = vid  # coerce to string
        if not VIDEO_ID_RE.match(vid):
            errors.append(f"Invalid video_id: '{vid}'")
        if not v.get("curation_reason"):
            errors.append(f"Video '{vid}' missing curation_reason")
        # Duration range check
        dur = _parse_duration_seconds(v.get("duration_string", ""))
        if dur > 0 and dur < MIN_DURATION_SEC:
            errors.append(f"Video '{vid}' too short: {v.get('duration_string')} (min 3 min)")
        if dur > MAX_DURATION_SEC:
            errors.append(f"Video '{vid}' too long: {v.get('duration_string')} (max 2 hr)")

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

    if len(videos) > 5:
        errors.append(f"Too many curated videos: {len(videos)} (max 5)")
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

        # Priority: highest tier first (T1 → T4), then highest score
        tier = race.get("gravel_god_rating", {}).get("tier", 4)
        score = race.get("gravel_god_rating", {}).get("overall_score", 0)
        candidates.append((tier, -score, slug))

    candidates.sort()  # T1 first (tier=1), then highest score within tier
    return [slug for _, _, slug in candidates[:n]]


def enrich_profile(slug: str, research_file: str = None, dry_run: bool = False,
                   use_vision: bool = False) -> bool:
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

    # Build prompt (with optional vision)
    image_blocks = []
    if use_vision:
        prompt, image_blocks = build_enrichment_with_vision(race_data, research)
        if image_blocks:
            print(f"  Vision mode: {len([b for b in image_blocks if b.get('type') == 'image'])} thumbnails attached")
        else:
            print(f"  Vision mode: no thumbnails fetched, falling back to text-only")
    else:
        prompt = build_enrichment_prompt(race_data, research)

    if dry_run:
        print(f"  [DRY RUN] Would call API with {len(prompt)} char prompt")
        print(f"  [DRY RUN] Videos available: {len(research.get('videos', []))}")
        if image_blocks:
            print(f"  [DRY RUN] Vision: {len([b for b in image_blocks if b.get('type') == 'image'])} thumbnails")
        return True

    try:
        if use_vision and image_blocks:
            response = call_api_vision(prompt, image_blocks)
        else:
            response = call_api(prompt)
        enriched = parse_json_response(response)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  ERROR: Failed to parse API response: {e}")
        return False
    except Exception as e:
        print(f"  ERROR: API call failed: {e}")
        return False

    # Drop orphaned quotes that reference non-curated videos
    curated_ids = {v.get("video_id") for v in enriched.get("videos", [])}
    original_count = len(enriched.get("quotes", []))
    enriched["quotes"] = [q for q in enriched.get("quotes", []) if q.get("source_video_id", "") in curated_ids]
    dropped = original_count - len(enriched["quotes"])
    if dropped:
        print(f"  Dropped {dropped} quote(s) referencing non-curated videos")

    # Score thumbnails and drop low-quality ones (PIL optional)
    try:
        from youtube_thumbnail import score_thumbnail, get_best_thumbnail_url

        kept_videos = []
        for v in enriched.get("videos", []):
            vid = v.get("video_id", "")
            try:
                result = score_thumbnail(vid)
                v["thumbnail_score"] = result["score"]
                v["thumbnail_url"] = get_best_thumbnail_url(vid, result["has_maxres"])
                if result["is_black"]:
                    print(f"  Dropped video {vid}: black thumbnail")
                    continue
                if result["score"] < 15:
                    print(f"  Dropped video {vid}: low thumbnail score ({result['score']:.1f})")
                    continue
                kept_videos.append(v)
            except Exception as e:
                print(f"  Thumbnail scoring failed for {vid}: {e}")
                kept_videos.append(v)  # keep on scoring failure

        if len(kept_videos) < len(enriched.get("videos", [])):
            enriched["videos"] = kept_videos
            # Re-clean orphaned quotes after thumbnail drops
            curated_ids = {v.get("video_id") for v in enriched["videos"]}
            enriched["quotes"] = [q for q in enriched.get("quotes", []) if q.get("source_video_id", "") in curated_ids]
    except ImportError:
        pass  # PIL not available — skip thumbnail scoring

    # Validate
    errors = validate_enrichment(slug, enriched)
    if errors:
        print(f"  VALIDATION FAILED:")
        for err in errors:
            print(f"    - {err}")
        return False

    # Build full video records: merge curated metadata with raw research data
    # (transcripts, descriptions, tags preserved for future use)
    all_videos = []
    for raw_v in research.get("videos", []):
        vid_id = extract_video_id(raw_v.get("url", ""))
        if not vid_id:
            continue
        record = {
            "video_id": vid_id,
            "title": raw_v.get("title"),
            "channel": raw_v.get("channel"),
            "view_count": raw_v.get("view_count"),
            "upload_date": raw_v.get("upload_date"),
            "duration_string": raw_v.get("duration_string"),
            "description": raw_v.get("description", ""),
            "tags": raw_v.get("tags", []),
            "url": raw_v.get("url"),
        }
        if raw_v.get("transcript"):
            record["transcript"] = raw_v["transcript"]
        # Merge curation metadata if this video was curated
        if vid_id in curated_ids:
            for cv in enriched["videos"]:
                if cv.get("video_id") == vid_id:
                    record["curated"] = True
                    record["curation_reason"] = cv.get("curation_reason", "")
                    record["display_order"] = cv.get("display_order", 99)
                    if cv.get("thumbnail_url"):
                        record["thumbnail_url"] = cv["thumbnail_url"]
                    if cv.get("thumbnail_score") is not None:
                        record["thumbnail_score"] = cv["thumbnail_score"]
                    break
        else:
            record["curated"] = False
        all_videos.append(record)

    # Build youtube_data block — full research payload + curated quotes
    youtube_data = {
        "researched_at": date.today().isoformat(),
        "search_query": research.get("query", ""),
        "videos": all_videos,
        "quotes": enriched.get("quotes", []),
    }

    # Write to race file
    race_data["race"]["youtube_data"] = youtube_data
    path = RACE_DATA_DIR / f"{slug}.json"
    with open(path, "w") as f:
        json.dump(race_data, f, indent=2, ensure_ascii=False)

    n_curated = len([v for v in all_videos if v.get("curated")])
    n_quotes = len([q for q in youtube_data["quotes"] if q.get("curated")])
    n_transcripts = len([v for v in all_videos if v.get("transcript")])
    print(f"  SUCCESS: {n_curated} curated videos, {n_quotes} quotes, {n_transcripts} transcripts stored → {path.name}")
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
    parser.add_argument("--vision", action="store_true",
                        help="Use Claude vision API with thumbnail images for better curation")
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
        result = enrich_profile(slug, args.research_file, args.dry_run,
                               use_vision=args.vision)
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
