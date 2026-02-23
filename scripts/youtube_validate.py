#!/usr/bin/env python3
"""
Validate youtube_data quality across all race profiles.

Checks:
1. Video IDs are valid format (11-char alphanumeric + hyphen/underscore)
2. Quote text contains no HTML/script injection
3. Every quote references a valid video_id in the same race's videos array
4. Display orders are unique per race
5. Curated videos have curation_reason
6. researched_at is a valid YYYY-MM-DD date

Exits 1 on any failure. Run as pre-deploy check.

Usage:
    python scripts/youtube_validate.py
    python scripts/youtube_validate.py --verbose
"""

import argparse
import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
HTML_RE = re.compile(r'<[a-z][^>]*>', re.IGNORECASE)


def validate_race(fname: str, yt_data: dict, verbose: bool = False) -> list[str]:
    """Validate youtube_data for a single race. Returns list of error strings."""
    errors = []
    videos = yt_data.get("videos", [])
    quotes = yt_data.get("quotes", [])
    video_ids = {v.get("video_id") for v in videos}

    # 1. Video ID format
    for v in videos:
        vid = v.get("video_id", "")
        if not VIDEO_ID_RE.match(vid):
            errors.append(f"{fname}: invalid video_id '{vid}'")

    # 2. Quote text: no HTML
    for q in quotes:
        text = q.get("text", "")
        if HTML_RE.search(text):
            errors.append(f"{fname}: quote contains HTML: '{text[:60]}...'")

    # 3. Quote references valid video_id
    for q in quotes:
        src = q.get("source_video_id", "")
        if src and src not in video_ids:
            errors.append(f"{fname}: quote references unknown video_id '{src}'")

    # 4. Unique display orders
    orders = [v["display_order"] for v in videos if "display_order" in v]
    if len(orders) != len(set(orders)):
        errors.append(f"{fname}: duplicate display_order values: {orders}")

    # 5. Curated videos have curation_reason
    for v in videos:
        if v.get("curated") and not v.get("curation_reason"):
            errors.append(f"{fname}: curated video '{v.get('video_id')}' missing curation_reason")

    # 6. researched_at date format
    ra = yt_data.get("researched_at", "")
    if ra and not DATE_RE.match(ra):
        errors.append(f"{fname}: invalid researched_at date '{ra}'")

    if verbose and not errors:
        n_videos = len([v for v in videos if v.get("curated")])
        n_quotes = len([q for q in quotes if q.get("curated")])
        print(f"  {fname}: {n_videos} curated videos, {n_quotes} curated quotes")

    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate youtube_data in race profiles.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-race details")
    args = parser.parse_args()

    if not DATA_DIR.exists():
        print(f"ERROR: race-data directory not found: {DATA_DIR}", file=sys.stderr)
        return 1

    all_errors = []
    enriched_count = 0

    for json_file in sorted(DATA_DIR.glob("*.json")):
        try:
            data = json.loads(json_file.read_text())
            race = data.get("race", data)
        except (json.JSONDecodeError, IOError) as e:
            all_errors.append(f"{json_file.name}: failed to parse: {e}")
            continue

        if "youtube_data" not in race:
            continue

        enriched_count += 1
        errors = validate_race(json_file.name, race["youtube_data"], verbose=args.verbose)
        all_errors.extend(errors)

    if all_errors:
        print(f"\nYouTube validation FAILED ({len(all_errors)} errors in {enriched_count} enriched profiles):\n")
        for e in all_errors:
            print(f"  {e}")
        return 1

    print(f"YouTube validation passed: {enriched_count} enriched profiles, 0 errors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
