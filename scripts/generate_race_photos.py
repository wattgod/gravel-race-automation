#!/usr/bin/env python3
"""
Generate AI race photos using Gemini 2.5 Flash Image API.

Produces 3 photos per race (hero, terrain, action) using each profile's
rich JSON data to build targeted prompts. Output as JPEGs for self-hosting.

Usage:
    python scripts/generate_race_photos.py --all
    python scripts/generate_race_photos.py --slug unbound-200
    python scripts/generate_race_photos.py --slug mid-south --type hero
    python scripts/generate_race_photos.py --all --dry-run
    python scripts/generate_race_photos.py --all --concurrency 5
    python scripts/generate_race_photos.py --status
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("ERROR: google-genai required. Install with: pip install google-genai")
    sys.exit(1)

from dotenv import load_dotenv
import os

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Constants ──────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "wordpress" / "output" / "photos"

PHOTO_TYPES = {
    "hero": {"aspect_ratio": "16:9", "width": 1200, "height": 675},
    "terrain": {"aspect_ratio": "4:3", "width": 1200, "height": 900},
    "action": {"aspect_ratio": "16:9", "width": 1200, "height": 675},
}

# Cost per image at Gemini 2.5 Flash pricing
COST_PER_IMAGE = 0.039  # approximate

MONTH_SEASONS = {
    1: "winter", 2: "late winter", 3: "early spring", 4: "spring",
    5: "late spring", 6: "summer", 7: "mid-summer", 8: "late summer",
    9: "early autumn", 10: "autumn", 11: "late autumn", 12: "winter",
}

MONTH_LIGHT = {
    1: "low winter sun, long shadows",
    2: "soft late winter light",
    3: "crisp early spring light",
    4: "warm spring light filtering through new leaves",
    5: "bright late spring sunshine",
    6: "golden summer light, long days",
    7: "intense mid-summer sunlight",
    8: "warm late summer golden hour",
    9: "soft early autumn light with warm tones",
    10: "rich autumn golden light",
    11: "muted late autumn overcast light",
    12: "low winter sun, cold tones",
}


# ── Prompt Builder ─────────────────────────────────────────────

def _parse_month(date_specific: str) -> int | None:
    """Extract month number from date_specific field."""
    if not date_specific:
        return None
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for name, num in month_names.items():
        if name in date_specific.lower():
            return num
    return None


def _join_natural(items: list[str]) -> str:
    """Join list items into natural English."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]


def build_prompts(race: dict) -> dict[str, str]:
    """Build photo prompts from race JSON data."""
    vitals = race.get("vitals", {})
    terrain = race.get("terrain", {})
    climate = race.get("climate", {})
    course = race.get("course_description", {})
    rating = race.get("gravel_god_rating", {})

    location = vitals.get("location", "a remote gravel road")
    terrain_types = vitals.get("terrain_types", [])
    terrain_primary = terrain.get("primary", "gravel roads")
    surface_raw = terrain.get("surface", "gravel")
    # Truncate long surface descriptions to first clause for cleaner prompts
    surface = surface_raw.split(".")[0] if "." in surface_raw else surface_raw
    if len(surface) > 80:
        surface = surface[:77].rsplit(",", 1)[0]
    features = terrain.get("features", [])
    climate_desc = climate.get("description", "")
    climate_primary = climate.get("primary", "")
    character = course.get("character", "")
    discipline = rating.get("discipline", "gravel")

    # Derive season from race month
    month = _parse_month(vitals.get("date_specific", ""))
    season = MONTH_SEASONS.get(month, "summer") if month else "summer"
    light = MONTH_LIGHT.get(month, "natural daylight") if month else "natural daylight"

    # Cyclist description based on discipline
    if discipline == "mtb":
        cyclist_desc = "mountain biker"
        cyclist_plural = "mountain bikers"
        kit_desc = "mountain biking kit with full-finger gloves and helmet"
    else:
        cyclist_desc = "gravel cyclist"
        cyclist_plural = "gravel cyclists"
        kit_desc = "cycling kit with helmet and sunglasses"

    # Terrain description for hero
    terrain_joined = _join_natural(terrain_types) if terrain_types else terrain_primary
    features_joined = _join_natural(features[:3]) if features else ""

    # Extract region/landscape from location
    location_parts = [p.strip() for p in location.split(",")]
    region = location_parts[-1] if len(location_parts) > 1 else location

    # Climate snippet (first sentence or first 100 chars)
    climate_snippet = ""
    if climate_desc:
        first_sentence = climate_desc.split(".")[0] + "."
        climate_snippet = first_sentence if len(first_sentence) < 120 else climate_desc[:100] + "."

    # Hero prompt
    hero_prompt = (
        f"A photorealistic wide-angle landscape photograph of {terrain_primary} "
        f"near {location}. The landscape features {terrain_joined}. "
    )
    if climate_snippet:
        hero_prompt += f"{climate_snippet} "
    hero_prompt += (
        f"{light.capitalize()}. No people visible. The road stretches into "
        f"the distance. Shot on a 24mm lens at f/8, deep depth of field. "
        f"Rich natural colors, editorial landscape photography. "
        f"No text, no watermarks, no logos."
    )

    # Terrain prompt
    terrain_prompt = (
        f"A photorealistic close-up photograph of {surface} road surface "
        f"in {region}. "
    )
    if features_joined:
        terrain_prompt += f"The surrounding landscape shows {features_joined}. "
    terrain_prompt += (
        f"Shallow depth of field, road surface sharp in foreground, "
        f"landscape soft in background. Shot on 85mm lens at f/2.8. "
        f"Natural {season} light. Documentary style. "
        f"No text, no watermarks."
    )

    # Action prompt
    action_prompt = (
        f"A photorealistic photograph of 2 {cyclist_plural} riding on "
        f"{surface} road near {location}. "
    )
    if climate_primary:
        action_prompt += f"{climate_primary} conditions. "
    action_prompt += (
        f"Wearing {kit_desc}. "
    )
    if features_joined:
        action_prompt += f"{features_joined} visible in the landscape. "
    action_prompt += (
        f"Shot on 50mm lens at f/4, natural {light}. Slight motion blur "
        f"in wheels. Cyclists seen from behind, no visible faces. "
        f"Editorial cycling photography. No text, no watermarks."
    )

    return {
        "hero": hero_prompt,
        "terrain": terrain_prompt,
        "action": action_prompt,
    }


def build_alt_texts(race: dict) -> dict[str, str]:
    """Generate descriptive alt texts from race data."""
    vitals = race.get("vitals", {})
    terrain = race.get("terrain", {})
    rating = race.get("gravel_god_rating", {})

    location = vitals.get("location", "remote location")
    terrain_types = vitals.get("terrain_types", [])
    surface = terrain.get("surface", "gravel")
    terrain_primary = terrain.get("primary", "gravel road")
    discipline = rating.get("discipline", "gravel")

    # Short location (city + state/country)
    loc_short = location.split(",")[0].strip() if location else "the course"
    region = location.split(",")[-1].strip() if "," in location else location

    # Terrain type for alt text
    terrain_desc = terrain_types[0] if terrain_types else terrain_primary

    cyclist_word = "Mountain bikers" if discipline == "mtb" else "Gravel cyclists"

    return {
        "hero": f"{terrain_desc.capitalize()} road stretching through the landscape near {location}",
        "terrain": f"Close-up of {surface} near {loc_short}",
        "action": f"{cyclist_word} riding through {region}",
    }


# ── API Call ───────────────────────────────────────────────────

async def generate_photo(
    client: genai.Client,
    prompt: str,
    aspect_ratio: str,
) -> Image.Image | None:
    """Generate a single photo via Gemini 2.5 Flash Image API."""
    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
        if response and response.parts:
            for part in response.parts:
                if part.inline_data:
                    return part.as_image()
        return None
    except Exception as e:
        print(f"  API error: {e}")
        return None


# ── Post-Processing ────────────────────────────────────────────

def post_process(img, target_w: int, target_h: int, output_path: Path):
    """Resize and save as optimized JPEG. Accepts PIL Image or genai Image."""
    # Convert google.genai.types.Image to PIL if needed
    if hasattr(img, '_pil_image'):
        img = img._pil_image
    img = img.convert("RGB")
    img = img.resize((target_w, target_h), Image.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=85, optimize=True)


# ── JSON Update ────────────────────────────────────────────────

def update_race_json(data_file: Path, race_photos: list[dict]):
    """Write race_photos array into race JSON profile."""
    with open(data_file) as f:
        data = json.load(f)

    data["race"]["race_photos"] = race_photos

    with open(data_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ── Batch Processing ──────────────────────────────────────────

async def process_race(
    client: genai.Client,
    slug: str,
    race: dict,
    output_dir: Path,
    photo_type_filter: str | None,
    dry_run: bool,
    semaphore: asyncio.Semaphore,
) -> tuple[str, int, int]:
    """Process a single race. Returns (slug, generated_count, error_count)."""
    prompts = build_prompts(race)
    alt_texts = build_alt_texts(race)
    generated = 0
    errors = 0

    types_to_process = [photo_type_filter] if photo_type_filter else list(PHOTO_TYPES.keys())

    for ptype in types_to_process:
        spec = PHOTO_TYPES[ptype]
        output_path = output_dir / f"{slug}-{ptype}.jpg"

        # Skip if already exists (resume support)
        if output_path.exists() and not dry_run:
            generated += 1
            continue

        if dry_run:
            print(f"\n  [{slug}] {ptype} prompt:")
            print(f"    {prompts[ptype][:200]}...")
            generated += 1
            continue

        async with semaphore:
            img = await generate_photo(client, prompts[ptype], spec["aspect_ratio"])

        if img:
            post_process(img, spec["width"], spec["height"], output_path)
            generated += 1
        else:
            print(f"  FAIL: {slug}-{ptype}")
            errors += 1

    # Update race JSON with photo metadata (skip in dry-run)
    if not dry_run and generated > 0:
        data_file = DATA_DIR / f"{slug}.json"
        if data_file.exists():
            race_photos = []
            for ptype in PHOTO_TYPES:
                photo_path = output_dir / f"{slug}-{ptype}.jpg"
                if photo_path.exists():
                    race_photos.append({
                        "type": ptype,
                        "file": f"{slug}-{ptype}.jpg",
                        "alt": alt_texts[ptype],
                    })
            if race_photos:
                update_race_json(data_file, race_photos)

    return slug, generated, errors


async def run_batch(
    slugs: list[str],
    output_dir: Path,
    photo_type_filter: str | None,
    dry_run: bool,
    concurrency: int,
):
    """Run batch generation for multiple races."""
    api_key = (os.environ.get("GOOGLE_API_KEY")
               or os.environ.get("GEMINI_API_KEY")
               or os.environ.get("GOOGLE_AI_API_KEY"))
    if not api_key and not dry_run:
        print("ERROR: Set GOOGLE_API_KEY, GEMINI_API_KEY, or GOOGLE_AI_API_KEY environment variable")
        sys.exit(1)

    client = None
    if not dry_run:
        client = genai.Client(api_key=api_key)

    semaphore = asyncio.Semaphore(concurrency)
    total = len(slugs)
    total_generated = 0
    total_errors = 0
    start_time = time.time()

    for i, slug in enumerate(slugs, 1):
        data_file = DATA_DIR / f"{slug}.json"
        if not data_file.exists():
            print(f"  SKIP: {slug} (no data file)")
            total_errors += 1
            continue

        with open(data_file) as f:
            raw = json.load(f)
        race = raw.get("race", raw)

        slug_result, gen, err = await process_race(
            client, slug, race, output_dir, photo_type_filter, dry_run, semaphore
        )
        total_generated += gen
        total_errors += err

        if not dry_run and i % 10 == 0:
            elapsed = time.time() - start_time
            print(f"  [{i}/{total}] Generated {slug} ({elapsed:.0f}s elapsed)")

    elapsed = time.time() - start_time
    photos_per_race = 1 if photo_type_filter else 3
    expected = total * photos_per_race

    print(f"\nDone. {total_generated}/{expected} photos in {elapsed:.0f}s")
    if total_errors:
        print(f"  {total_errors} errors")
    if not dry_run:
        est_cost = total_generated * COST_PER_IMAGE
        print(f"  Est. cost: ${est_cost:.2f}")


# ── Status Report ──────────────────────────────────────────────

def print_status(output_dir: Path):
    """Print progress report of generated photos."""
    all_slugs = [f.stem for f in sorted(DATA_DIR.glob("*.json"))]
    total_races = len(all_slugs)

    complete = 0
    partial = 0
    missing = 0
    photo_count = 0

    for slug in all_slugs:
        types_found = 0
        for ptype in PHOTO_TYPES:
            if (output_dir / f"{slug}-{ptype}.jpg").exists():
                types_found += 1
                photo_count += 1
        if types_found == 3:
            complete += 1
        elif types_found > 0:
            partial += 1
        else:
            missing += 1

    total_expected = total_races * 3
    print(f"Race Photo Status:")
    print(f"  Total races: {total_races}")
    print(f"  Complete (3/3): {complete}")
    print(f"  Partial: {partial}")
    print(f"  Missing: {missing}")
    print(f"  Photos: {photo_count}/{total_expected}")

    if photo_count > 0:
        # Check total file size
        total_size = sum(
            f.stat().st_size
            for f in output_dir.glob("*.jpg")
            if f.is_file()
        )
        print(f"  Total size: {total_size / 1024 / 1024:.1f} MB")


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate AI race photos via Gemini 2.5 Flash Image"
    )
    parser.add_argument("--slug", help="Generate for a single race slug")
    parser.add_argument("--all", action="store_true", help="Generate for all races")
    parser.add_argument(
        "--type",
        choices=["hero", "terrain", "action"],
        help="Generate only one photo type",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prompts without calling API",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Max concurrent API calls (default: 3)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUTPUT_DIR,
        help=f"Output directory (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print progress report",
    )
    args = parser.parse_args()

    if args.status:
        print_status(args.output_dir)
        return

    if not args.slug and not args.all:
        parser.error("Provide --slug or --all (or --status)")

    if args.all:
        slugs = [f.stem for f in sorted(DATA_DIR.glob("*.json"))]
    else:
        slugs = [args.slug]

    print(f"Generating photos for {len(slugs)} race(s)...")
    if args.dry_run:
        print("  (dry-run mode — prompts only)")

    asyncio.run(
        run_batch(
            slugs=slugs,
            output_dir=args.output_dir,
            photo_type_filter=args.type,
            dry_run=args.dry_run,
            concurrency=args.concurrency,
        )
    )


if __name__ == "__main__":
    main()
