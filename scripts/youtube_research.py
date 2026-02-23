#!/usr/bin/env python3
"""
youtube_research.py — YouTube research tool for gravel race profiles.

Uses yt-dlp to search YouTube for race content and extract:
  - Video metadata (title, channel, views, upload date)
  - Full descriptions (often contain dates, distances, terrain details)
  - Auto-generated transcripts (rider recaps, course descriptions)

Usage:
  # Search a single race by slug
  python scripts/youtube_research.py --slug almanzo-100

  # Search multiple races
  python scripts/youtube_research.py --slug almanzo-100 migration-gravel-race

  # Search all races with stale dates
  python scripts/youtube_research.py --stale-dates

  # Search all races, save results
  python scripts/youtube_research.py --all --output youtube-research-results/

  # Control search depth
  python scripts/youtube_research.py --slug almanzo-100 --max-results 5 --transcript
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RACE_DATA_DIR = Path(__file__).parent.parent / "race-data"
DEFAULT_MAX_RESULTS = 3


def search_youtube(query: str, max_results: int = DEFAULT_MAX_RESULTS, full_metadata: bool = True) -> list[dict]:
    """Search YouTube and return video metadata as dicts."""
    cmd = [
        "yt-dlp",
        f"ytsearch{max_results}:{query}",
        "--dump-json",
        "--no-download",
    ]
    if not full_metadata:
        cmd.append("--flat-playlist")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        print(f"  [TIMEOUT] Search timed out for: {query}", file=sys.stderr)
        return []

    videos = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        try:
            videos.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return videos


def get_transcript(video_url: str) -> str | None:
    """Download auto-generated subtitles and return cleaned transcript text."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--skip-download",
            "--sub-format", "vtt",
            "-o", f"{tmpdir}/%(id)s",
            video_url,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return None

        # Find the .vtt file
        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            return None

        text = vtt_files[0].read_text()

    # Clean VTT → plain text (deduplicated lines)
    lines = []
    seen = set()
    for line in text.split("\n"):
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or re.match(r"^\d+$", line):
            continue
        if line.startswith("Kind:") or line.startswith("Language:"):
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        if clean and clean not in seen:
            seen.add(clean)
            lines.append(clean)

    return "\n".join(lines) if lines else None


def extract_video_summary(video: dict, include_transcript: bool = False) -> dict:
    """Extract the useful fields from a yt-dlp video metadata dict."""
    summary = {
        "title": video.get("title"),
        "channel": video.get("channel"),
        "upload_date": video.get("upload_date"),
        "duration_string": video.get("duration_string"),
        "view_count": video.get("view_count"),
        "like_count": video.get("like_count"),
        "description": video.get("description", ""),
        "tags": video.get("tags", []),
        "url": video.get("webpage_url") or video.get("url"),
    }

    if include_transcript and summary["url"]:
        transcript = get_transcript(summary["url"])
        if transcript:
            summary["transcript"] = transcript

    return summary


def load_race(slug: str) -> dict | None:
    """Load a race profile JSON by slug."""
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        print(f"  [WARN] Race file not found: {path}", file=sys.stderr)
        return None
    with open(path) as f:
        return json.load(f)


def build_search_query(race: dict) -> str:
    """Build a YouTube search query from race data."""
    r = race.get("race", {})
    name = r.get("name") or r.get("display_name", "")
    location = r.get("vitals", {}).get("location", "")

    # Try to include the year for freshness
    query = f"{name} gravel race"
    if location:
        query += f" {location.split(',')[0]}"  # Just the city/region
    return query


def research_race(slug: str, max_results: int = DEFAULT_MAX_RESULTS,
                  include_transcript: bool = False) -> dict:
    """Run YouTube research for a single race."""
    race = load_race(slug)
    if not race:
        return {"slug": slug, "error": "Race file not found"}

    r = race.get("race", {})
    query = build_search_query(race)

    print(f"\n{'='*60}")
    print(f"Race: {r.get('display_name', r.get('name', slug))}")
    print(f"Query: {query}")
    print(f"{'='*60}")

    videos = search_youtube(query, max_results=max_results)
    print(f"  Found {len(videos)} videos")

    results = []
    for i, v in enumerate(videos):
        summary = extract_video_summary(v, include_transcript=include_transcript)
        results.append(summary)
        print(f"\n  [{i+1}] {summary['title']}")
        print(f"      Channel: {summary['channel']} | Views: {summary['view_count']} | Date: {summary['upload_date']}")
        if summary['description']:
            desc_preview = summary['description'][:200].replace('\n', ' ')
            print(f"      Desc: {desc_preview}...")
        if summary.get('transcript'):
            print(f"      Transcript: {len(summary['transcript'])} chars")

    return {
        "slug": slug,
        "race_name": r.get("display_name", r.get("name")),
        "query": query,
        "video_count": len(results),
        "videos": results,
    }


def get_stale_date_slugs() -> list[str]:
    """Find races with stale/missing dates."""
    slugs = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        with open(f) as fh:
            data = json.load(fh)
        r = data.get("race", {})
        vitals = r.get("vitals", {})
        date_specific = vitals.get("date_specific", "")
        # Flag if no specific date, or date mentions 2025 (stale), or TBD
        if not date_specific or "2025" in str(date_specific) or "TBD" in str(date_specific):
            slugs.append(f.stem)
    return slugs


def main():
    parser = argparse.ArgumentParser(description="YouTube research for gravel race profiles")
    parser.add_argument("--slug", nargs="+", help="Race slug(s) to research")
    parser.add_argument("--stale-dates", action="store_true", help="Research all races with stale/missing dates")
    parser.add_argument("--all", action="store_true", help="Research all races")
    parser.add_argument("--max-results", type=int, default=DEFAULT_MAX_RESULTS, help="Max YouTube results per race")
    parser.add_argument("--transcript", action="store_true", help="Also download auto-generated transcripts")
    parser.add_argument("--output", type=str, help="Output directory for results JSON files")
    args = parser.parse_args()

    if not args.slug and not args.stale_dates and not args.all:
        parser.print_help()
        sys.exit(1)

    # Collect slugs
    if args.slug:
        slugs = args.slug
    elif args.stale_dates:
        slugs = get_stale_date_slugs()
        print(f"Found {len(slugs)} races with stale/missing dates")
    elif args.all:
        slugs = [f.stem for f in sorted(RACE_DATA_DIR.glob("*.json"))]
        print(f"Researching all {len(slugs)} races")

    # Output dir
    output_dir = None
    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Run research
    all_results = []
    for slug in slugs:
        result = research_race(slug, max_results=args.max_results, include_transcript=args.transcript)
        all_results.append(result)

        if output_dir:
            out_path = output_dir / f"{slug}.json"
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)

    # Summary
    total_videos = sum(r.get("video_count", 0) for r in all_results)
    print(f"\n{'='*60}")
    print(f"SUMMARY: {len(all_results)} races searched, {total_videos} videos found")
    if output_dir:
        print(f"Results saved to: {output_dir}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
