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
7. rider_intel: text fields have no HTML, source_video_ids reference valid videos,
   additional_quotes follow quote schema, search_text is 30-500 words

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

from youtube_enrich import QUOTE_CATEGORIES  # single source of truth

DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

VIDEO_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
HTML_RE = re.compile(r'<[a-z][^>]*>', re.IGNORECASE)


def validate_rider_intel(fname: str, intel: dict, video_ids: set) -> list[str]:
    """Validate rider_intel block. Returns list of error strings.

    Single source of truth — used by both youtube_validate.py (deploy check)
    and youtube_extract_intel.py (extraction-time validation).
    """
    errors = []

    # Validate key_challenges with max count
    challenges = intel.get("key_challenges", [])
    if len(challenges) > 6:
        errors.append(f"{fname}: too many key_challenges: {len(challenges)} (max 6)")
    for c in challenges:
        if not c.get("name"):
            errors.append(f"{fname}: rider_intel.key_challenges missing 'name'")
        if not c.get("description"):
            errors.append(f"{fname}: rider_intel.key_challenges '{c.get('name', '?')}' missing 'description'")
        for text_key in ("description", "name"):
            text = c.get(text_key, "")
            if text and HTML_RE.search(text):
                errors.append(f"{fname}: rider_intel.key_challenges {text_key} contains HTML: '{text[:60]}...'")
        vids = c.get("source_video_ids", [])
        if not isinstance(vids, list):
            errors.append(f"{fname}: rider_intel.key_challenges source_video_ids must be a list, got {type(vids).__name__}")
        else:
            for vid in vids:
                if vid not in video_ids:
                    errors.append(f"{fname}: rider_intel.key_challenges references unknown video_id '{vid}'")

    # Validate terrain_notes, gear_mentions, race_day_tips (text + source_video_ids)
    for field_name, items in [
        ("terrain_notes", intel.get("terrain_notes", [])),
        ("gear_mentions", intel.get("gear_mentions", [])),
        ("race_day_tips", intel.get("race_day_tips", [])),
    ]:
        for item in items:
            if not item.get("text"):
                errors.append(f"{fname}: rider_intel.{field_name} missing 'text'")
            text = item.get("text", "")
            if text and HTML_RE.search(text):
                errors.append(f"{fname}: rider_intel.{field_name} text contains HTML: '{text[:60]}...'")
            vids = item.get("source_video_ids", [])
            if not isinstance(vids, list):
                errors.append(f"{fname}: rider_intel.{field_name} source_video_ids must be a list, got {type(vids).__name__}")
            else:
                for vid in vids:
                    if vid not in video_ids:
                        errors.append(f"{fname}: rider_intel.{field_name} references unknown video_id '{vid}'")

    # Validate additional_quotes with max count + required attribution fields
    quotes = intel.get("additional_quotes", [])
    if len(quotes) > 5:
        errors.append(f"{fname}: too many additional_quotes: {len(quotes)} (max 5)")
    for q in quotes:
        text = q.get("text", "")
        if not text:
            errors.append(f"{fname}: rider_intel.additional_quote missing text")
        if HTML_RE.search(text):
            errors.append(f"{fname}: rider_intel.additional_quote contains HTML: '{text[:60]}...'")
        src = q.get("source_video_id", "")
        if src and src not in video_ids:
            errors.append(f"{fname}: rider_intel.additional_quote references unknown video_id '{src}'")
        cat = q.get("category", "")
        if cat and cat not in QUOTE_CATEGORIES:
            errors.append(f"{fname}: rider_intel.additional_quote has invalid category: '{cat}'")
        if not q.get("source_channel"):
            errors.append(f"{fname}: rider_intel.additional_quote missing 'source_channel'")
        if q.get("source_view_count") is None:
            errors.append(f"{fname}: rider_intel.additional_quote missing 'source_view_count'")

    # Validate search_text — must exist and be reasonable length
    search_text = intel.get("search_text", "")
    if not search_text:
        errors.append(f"{fname}: rider_intel.search_text is empty or missing")
    elif HTML_RE.search(search_text):
        errors.append(f"{fname}: rider_intel.search_text contains HTML")
    else:
        word_count = len(search_text.split())
        if word_count < 30:
            errors.append(f"{fname}: rider_intel.search_text too short: {word_count} words (min 30)")
        elif word_count > 500:
            errors.append(f"{fname}: rider_intel.search_text too long: {word_count} words (max 500)")

    # Validate extracted_at date
    ea = intel.get("extracted_at", "")
    if ea and not DATE_RE.match(ea):
        errors.append(f"{fname}: rider_intel.extracted_at invalid date '{ea}'")

    return errors


VALID_PHOTO_TYPES = {"video-1", "video-2", "video-3", "preview-gif",
                     "street-1", "street-2", "landscape", "map"}

PHOTOS_DIR = Path(__file__).resolve().parent.parent / "race-photos"
QUALITY_FLOOR = 30  # minimum quality_score before flagging


def validate_photos(fname: str, slug: str, photos: list) -> list[str]:
    """Validate race.photos array. Returns list of error strings."""
    if not photos:
        return []

    errors = []

    if not isinstance(photos, list):
        return [f"{fname}: photos must be a list, got {type(photos).__name__}"]

    primary_count = 0
    seen_types = set()

    for i, p in enumerate(photos):
        prefix = f"{fname}: photos[{i}]"

        # Required fields
        for field in ("type", "file", "url", "alt", "credit"):
            if not p.get(field):
                errors.append(f"{prefix} missing '{field}'")

        # Valid type
        ptype = p.get("type", "")
        if ptype and ptype not in VALID_PHOTO_TYPES:
            errors.append(f"{prefix} invalid type '{ptype}'")

        # Duplicate type check (preview-gif can appear multiple times for gallery)
        if ptype in seen_types and ptype != "preview-gif":
            errors.append(f"{prefix} duplicate type '{ptype}'")
        seen_types.add(ptype)

        # URL format
        url = p.get("url", "")
        if url and not url.startswith(f"/race-photos/{slug}/"):
            errors.append(f"{prefix} url must start with '/race-photos/{slug}/', got '{url}'")

        # Primary tracking
        if p.get("primary"):
            primary_count += 1

        # GIF flag consistency
        if ptype == "preview-gif" and not p.get("gif"):
            errors.append(f"{prefix} preview-gif entry missing gif=true")

        # No HTML in alt text
        alt = p.get("alt", "")
        if alt and HTML_RE.search(alt):
            errors.append(f"{prefix} alt text contains HTML")

        # File exists on disk (video-* and preview-gif types)
        if ptype and ptype.startswith("video-") or ptype == "preview-gif":
            photo_file = p.get("file", "")
            if photo_file:
                filepath = PHOTOS_DIR / slug / photo_file
                if not filepath.exists():
                    errors.append(f"{prefix} file not found on disk: {filepath.name}")

        # Quality floor check (if quality_score persisted)
        qs = p.get("quality_score")
        if qs is not None and isinstance(qs, (int, float)) and qs < QUALITY_FLOOR:
            errors.append(f"{prefix} quality_score {qs} below floor ({QUALITY_FLOOR})")

    # Exactly one primary (if any non-gif photos exist)
    non_gif = [p for p in photos if not p.get("gif")]
    if non_gif and primary_count != 1:
        errors.append(f"{fname}: expected exactly 1 primary photo, found {primary_count}")

    return errors


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

    # 7. rider_intel validation
    rider_intel = yt_data.get("rider_intel")
    if rider_intel:
        errors.extend(validate_rider_intel(fname, rider_intel, video_ids))

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

        # Validate photos (independent of youtube_data)
        photos = race.get("photos", [])
        if photos:
            slug = race.get("slug", json_file.stem)
            photo_errors = validate_photos(json_file.name, slug, photos)
            all_errors.extend(photo_errors)

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
