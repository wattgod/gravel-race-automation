#!/usr/bin/env python3
"""
Generate race photos using 3 layers: Street View, AI Landscapes, Route Maps.

Layer 1 — Google Street View: Real course photos from RWGPS route coordinates.
Layer 2 — AI Landscape: Atmospheric hero images (no cyclists) via Stability/Gemini.
Layer 3 — Route Maps: Satellite overview with route polyline overlay.

Usage:
    python3 scripts/generate_race_photos_v2.py --all
    python3 scripts/generate_race_photos_v2.py --slug unbound-200
    python3 scripts/generate_race_photos_v2.py --all --layer street
    python3 scripts/generate_race_photos_v2.py --all --layer landscape
    python3 scripts/generate_race_photos_v2.py --all --layer map
    python3 scripts/generate_race_photos_v2.py --all --engine gemini
    python3 scripts/generate_race_photos_v2.py --all --engine stability
    python3 scripts/generate_race_photos_v2.py --all --engine both
    python3 scripts/generate_race_photos_v2.py --all --dry-run
    python3 scripts/generate_race_photos_v2.py --status
    python3 scripts/generate_race_photos_v2.py --tier 1
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import shutil
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow required. Install with: pip install Pillow")
    sys.exit(1)

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ── Constants ──────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT_DIR = PROJECT_ROOT / "race-photos"
COMPARISON_DIR = OUTPUT_DIR / "_comparison"

# API endpoints
RWGPS_ROUTE_URL = "https://ridewithgps.com/routes/{route_id}.json"
STREET_VIEW_URL = "https://maps.googleapis.com/maps/api/streetview"
STREET_VIEW_META_URL = "https://maps.googleapis.com/maps/api/streetview/metadata"
MAPS_STATIC_URL = "https://maps.googleapis.com/maps/api/staticmap"
STABILITY_URL = "https://api.stability.ai/v2beta/stable-image/generate/sd3"

# Photo specs (16:9 for all types)
PHOTO_WIDTH = 1200
PHOTO_HEIGHT = 675

# Street View sampling
SAMPLE_POINTS = 10
MIN_POINT_SPACING_KM = 3
STREET_VIEW_SIZE = f"{PHOTO_WIDTH}x{PHOTO_HEIGHT}"
STREET_VIEW_FOV = 90
STREET_VIEW_PITCH = -5
MAX_STREET_VIEWS = 3

# Rate limiting
RWGPS_DELAY = 1.1  # seconds between RWGPS requests

# Cost estimates
COST_STREET_VIEW = 0.007
COST_STABILITY = 0.065
COST_GEMINI = 0.039
COST_MAP = 0.002

# Season/light from existing script
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


# ── Utility Functions ──────────────────────────────────────────

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


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in km between two points using haversine formula."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def bearing_between(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate compass bearing (0-360) from point 1 to point 2."""
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlng = math.radians(lng2 - lng1)
    x = math.sin(dlng) * math.cos(lat2_r)
    y = (math.cos(lat1_r) * math.sin(lat2_r) -
         math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlng))
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


# ── RWGPS Route Fetching ──────────────────────────────────────

def fetch_route_coordinates(rwgps_id: str) -> list[tuple[float, float]]:
    """Fetch (lat, lng) track points from RWGPS public API."""
    url = RWGPS_ROUTE_URL.format(route_id=rwgps_id)
    headers = {"User-Agent": "GravelGod/1.0 (race-photo-pipeline)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    # RWGPS returns route.track_points[].{x: lng, y: lat, e: elevation, d: distance}
    route = data.get("route", data)
    track_points = route.get("track_points", [])
    if not track_points:
        return []

    coords = []
    for pt in track_points:
        lat = pt.get("y")
        lng = pt.get("x")
        if lat is not None and lng is not None:
            coords.append((lat, lng))
    return coords


def sample_route_points(
    coords: list[tuple[float, float]],
    n: int = SAMPLE_POINTS,
    min_spacing_km: float = MIN_POINT_SPACING_KM,
) -> list[tuple[float, float, float]]:
    """Select n evenly-spaced points along route with heading.

    Skips first/last 5% (parking lots). Returns list of (lat, lng, heading).
    """
    if len(coords) < 3:
        return []

    # Skip first/last 5%
    skip = max(1, len(coords) // 20)
    trimmed = coords[skip:-skip] if skip < len(coords) // 2 else coords

    if len(trimmed) < 2:
        return []

    # Calculate cumulative distances
    distances = [0.0]
    for i in range(1, len(trimmed)):
        d = haversine_km(trimmed[i - 1][0], trimmed[i - 1][1],
                         trimmed[i][0], trimmed[i][1])
        distances.append(distances[-1] + d)

    total_dist = distances[-1]
    if total_dist < min_spacing_km:
        return []

    # Sample n evenly-spaced points
    step = total_dist / (n + 1)
    sampled = []
    target_dist = step

    for _ in range(n):
        if target_dist > total_dist:
            break
        # Find the segment containing target_dist
        for j in range(1, len(distances)):
            if distances[j] >= target_dist:
                # Interpolate between trimmed[j-1] and trimmed[j]
                frac = ((target_dist - distances[j - 1]) /
                        (distances[j] - distances[j - 1]))
                lat = trimmed[j - 1][0] + frac * (trimmed[j][0] - trimmed[j - 1][0])
                lng = trimmed[j - 1][1] + frac * (trimmed[j][1] - trimmed[j - 1][1])
                # Heading: look ahead to find a point far enough for bearing
                heading = 0
                for k in range(j, min(j + 50, len(trimmed))):
                    d = haversine_km(lat, lng, trimmed[k][0], trimmed[k][1])
                    if d > 0.05:  # at least 50m away
                        heading = bearing_between(lat, lng, trimmed[k][0], trimmed[k][1])
                        break
                sampled.append((lat, lng, heading))
                break
        target_dist += step

    # Enforce minimum spacing
    if len(sampled) < 2:
        return sampled

    filtered = [sampled[0]]
    for pt in sampled[1:]:
        prev = filtered[-1]
        if haversine_km(prev[0], prev[1], pt[0], pt[1]) >= min_spacing_km:
            filtered.append(pt)
    return filtered


# ── Street View Layer ──────────────────────────────────────────

def check_coverage(lat: float, lng: float, api_key: str) -> dict | None:
    """Check Street View metadata (FREE). Returns {pano_id, date} or None."""
    params = {
        "location": f"{lat},{lng}",
        "key": api_key,
    }
    resp = requests.get(STREET_VIEW_META_URL, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "OK":
        return {
            "pano_id": data.get("pano_id"),
            "date": data.get("date", ""),
            "lat": data.get("location", {}).get("lat", lat),
            "lng": data.get("location", {}).get("lng", lng),
        }
    return None


def fetch_street_view(lat: float, lng: float, heading: float, api_key: str) -> bytes:
    """Download Street View image. Returns JPEG bytes."""
    params = {
        "location": f"{lat},{lng}",
        "heading": str(int(heading)),
        "size": STREET_VIEW_SIZE,
        "fov": str(STREET_VIEW_FOV),
        "pitch": str(STREET_VIEW_PITCH),
        "key": api_key,
    }
    resp = requests.get(STREET_VIEW_URL, params=params, timeout=15)
    resp.raise_for_status()
    return resp.content


def generate_street_views(
    slug: str, rwgps_id: str, api_key: str, dry_run: bool = False,
) -> list[Path]:
    """Full pipeline: fetch route -> sample points -> check coverage -> fetch best."""
    output_slug_dir = OUTPUT_DIR / slug

    # Check for existing street view photos
    if output_slug_dir.is_dir():
        existing = sorted(output_slug_dir.glob(f"{slug}-street-*.jpg"))
        if existing:
            return existing

    print(f"    Fetching RWGPS route {rwgps_id}...")
    coords = fetch_route_coordinates(rwgps_id)
    if not coords:
        print(f"    No track points from RWGPS route {rwgps_id}")
        return []

    points = sample_route_points(coords)
    if not points:
        print(f"    Could not sample route points (route too short?)")
        return []

    print(f"    Sampled {len(points)} points, checking coverage...")

    if dry_run:
        for i, (lat, lng, heading) in enumerate(points):
            print(f"      Point {i+1}: ({lat:.4f}, {lng:.4f}) heading {heading:.0f}")
        return []

    # Check coverage at each point (metadata endpoint is FREE)
    covered_points = []
    for lat, lng, heading in points:
        meta = check_coverage(lat, lng, api_key)
        if meta:
            covered_points.append((lat, lng, heading, meta))

    print(f"    {len(covered_points)}/{len(points)} points have Street View coverage")

    if not covered_points:
        return []

    # Fetch up to MAX_STREET_VIEWS images, evenly spread across covered points
    if len(covered_points) > MAX_STREET_VIEWS:
        step = len(covered_points) / MAX_STREET_VIEWS
        selected = [covered_points[int(i * step)] for i in range(MAX_STREET_VIEWS)]
    else:
        selected = covered_points

    saved = []
    output_slug_dir.mkdir(parents=True, exist_ok=True)
    for i, (lat, lng, heading, meta) in enumerate(selected, 1):
        out_path = output_slug_dir / f"{slug}-street-{i}.jpg"
        print(f"    Downloading street view {i}/{len(selected)}...")
        img_bytes = fetch_street_view(lat, lng, heading, api_key)
        # Verify it's actually a JPEG image (not an error response)
        if len(img_bytes) < 5000:
            print(f"    SKIP: Street view at ({lat:.4f}, {lng:.4f}) returned small response")
            continue
        out_path.write_bytes(img_bytes)
        saved.append(out_path)

    print(f"    Saved {len(saved)} street view photos")
    return saved


# ── AI Landscape Layer ─────────────────────────────────────────

def build_landscape_prompt(race: dict) -> str:
    """Build a landscape-only prompt (no cyclists) from race data."""
    vitals = race.get("vitals", {})
    terrain_raw = race.get("terrain", {})
    if isinstance(terrain_raw, str):
        terrain = {"primary": terrain_raw, "surface": terrain_raw, "features": []}
    else:
        terrain = terrain_raw or {}
    climate_raw = race.get("climate", {})
    climate = climate_raw if isinstance(climate_raw, dict) else {"primary": str(climate_raw)}
    course = race.get("course_description", {}) if isinstance(race.get("course_description"), dict) else {}

    location = vitals.get("location", "a remote region")
    terrain_types = vitals.get("terrain_types", [])
    terrain_primary = terrain.get("primary", "gravel roads")
    # Handle terrain_primary being a dict
    if isinstance(terrain_primary, dict):
        terrain_primary = terrain_primary.get("type", "gravel roads")
    features = terrain.get("features", [])
    climate_desc = climate.get("description", "")
    character = course.get("character", "")

    # Derive season from race month
    month = _parse_month(vitals.get("date_specific", ""))
    season = MONTH_SEASONS.get(month, "summer") if month else "summer"
    light = MONTH_LIGHT.get(month, "natural daylight") if month else "natural daylight"

    # Terrain description
    terrain_joined = _join_natural(terrain_types[:3]) if terrain_types else terrain_primary
    features_joined = _join_natural(features[:3]) if features else ""

    # Extract region
    location_parts = [p.strip() for p in location.split(",")]
    region = location_parts[-1] if len(location_parts) > 1 else location

    # Climate snippet (first sentence, max 120 chars)
    climate_snippet = ""
    if climate_desc:
        first_sentence = climate_desc.split(".")[0] + "."
        climate_snippet = first_sentence if len(first_sentence) < 120 else climate_desc[:100] + "."

    prompt = (
        f"A photorealistic wide-angle photograph of an empty gravel road "
        f"winding through {terrain_joined} near {location}. "
        f"{season.capitalize()} landscape with {light}. "
    )
    if features_joined:
        prompt += f"Terrain features include {features_joined}. "
    if climate_snippet:
        prompt += f"{climate_snippet} "
    prompt += (
        f"The road stretches into the distance through {region}. "
        f"Shot on 24mm lens at f/11. Deep depth of field. "
        f"Editorial landscape photography. "
        f"No people, no cyclists, no riders, no text, no watermarks, no logos."
    )
    return prompt


def generate_landscape_stability(prompt: str, api_key: str) -> Image.Image | None:
    """Generate landscape via Stability AI SD3.5 API."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "image/*",
    }
    data = {
        "prompt": prompt,
        "negative_prompt": "people, cyclists, riders, humans, text, watermark, blurry, low quality, cartoon, illustration",
        "output_format": "jpeg",
        "aspect_ratio": "16:9",
        "model": "sd3.5-large",
    }
    try:
        resp = requests.post(STABILITY_URL, headers=headers, data=data, timeout=60)
        if resp.status_code == 200:
            return Image.open(io.BytesIO(resp.content))
        print(f"    Stability API error {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"    Stability API error: {e}")
        return None


def generate_landscape_gemini(prompt: str) -> Image.Image | None:
    """Generate landscape via Gemini 2.5 Flash Image API."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("    SKIP Gemini: google-genai not installed")
        return None

    api_key = (os.environ.get("GOOGLE_API_KEY")
               or os.environ.get("GEMINI_API_KEY")
               or os.environ.get("GOOGLE_AI_API_KEY"))
    if not api_key:
        print("    SKIP Gemini: No GOOGLE_API_KEY set")
        return None

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio="16:9"),
            ),
        )
        if response and response.parts:
            for part in response.parts:
                if part.inline_data:
                    img = part.as_image()
                    # Convert google.genai Image to PIL
                    if hasattr(img, '_pil_image'):
                        return img._pil_image
                    return img
        return None
    except Exception as e:
        print(f"    Gemini API error: {e}")
        return None


def save_landscape(img: Image.Image, output_path: Path):
    """Resize to target dimensions and save as optimized JPEG."""
    img = img.convert("RGB")
    img = img.resize((PHOTO_WIDTH, PHOTO_HEIGHT), Image.LANCZOS)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=85, optimize=True)


def generate_landscape(
    slug: str, race: dict, engine: str, dry_run: bool = False,
) -> list[Path]:
    """Generate AI landscape for a race.

    engine: 'stability', 'gemini', or 'both'
    """
    output_slug_dir = OUTPUT_DIR / slug

    # Check for existing landscape
    existing = output_slug_dir / f"{slug}-landscape.jpg"
    if existing.exists() and engine != "both":
        return [existing]

    prompt = build_landscape_prompt(race)

    if dry_run:
        print(f"    Landscape prompt ({len(prompt)} chars):")
        print(f"      {prompt[:200]}...")
        return []

    saved = []
    stability_key = os.environ.get("STABILITY_API_KEY")
    use_stability = engine in ("stability", "both") and stability_key
    use_gemini = engine in ("gemini", "both")

    if use_stability:
        print(f"    Generating landscape via Stability AI...")
        img = generate_landscape_stability(prompt, stability_key)
        if img:
            if engine == "both":
                COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
                out = COMPARISON_DIR / f"{slug}-landscape-sd.jpg"
            else:
                out = output_slug_dir / f"{slug}-landscape.jpg"
            save_landscape(img, out)
            saved.append(out)
            print(f"    Saved: {out.name}")
        else:
            print(f"    FAIL: Stability landscape for {slug}")

    if use_gemini:
        print(f"    Generating landscape via Gemini...")
        img = generate_landscape_gemini(prompt)
        if img:
            if engine == "both":
                COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
                out = COMPARISON_DIR / f"{slug}-landscape-gemini.jpg"
            else:
                out = output_slug_dir / f"{slug}-landscape.jpg"
            save_landscape(img, out)
            saved.append(out)
            print(f"    Saved: {out.name}")
        else:
            print(f"    FAIL: Gemini landscape for {slug}")

    # If engine is 'both' and we got at least one, copy the first as production
    if engine == "both" and saved:
        prod = output_slug_dir / f"{slug}-landscape.jpg"
        if not prod.exists():
            shutil.copy2(str(saved[0]), str(prod))
            saved.append(prod)

    return saved


# ── Route Map Layer ────────────────────────────────────────────

def encode_polyline(coords: list[tuple[float, float]]) -> str:
    """Encode coordinates to Google Encoded Polyline format.

    coords: list of (lat, lng) tuples
    Returns encoded polyline string.
    """
    encoded = []
    prev_lat = 0
    prev_lng = 0

    for lat, lng in coords:
        # Round to 5 decimal places and convert to integer
        lat_int = round(lat * 1e5)
        lng_int = round(lng * 1e5)

        # Delta encoding
        d_lat = lat_int - prev_lat
        d_lng = lng_int - prev_lng
        prev_lat = lat_int
        prev_lng = lng_int

        for val in (d_lat, d_lng):
            # Left-shift and invert if negative
            val = ~(val << 1) if val < 0 else val << 1
            # Break into 5-bit chunks
            while val >= 0x20:
                encoded.append(chr(((val & 0x1F) | 0x20) + 63))
                val >>= 5
            encoded.append(chr(val + 63))

    return "".join(encoded)


def downsample_coords(
    coords: list[tuple[float, float]], max_points: int = 100,
) -> list[tuple[float, float]]:
    """Downsample coordinate list to max_points, keeping first/last."""
    if len(coords) <= max_points:
        return coords
    step = (len(coords) - 1) / (max_points - 1)
    indices = [int(i * step) for i in range(max_points - 1)] + [len(coords) - 1]
    return [coords[i] for i in indices]


def generate_route_map(
    slug: str, rwgps_id: str, api_key: str, dry_run: bool = False,
) -> Path | None:
    """Generate satellite route overview via Maps Static API."""
    output_slug_dir = OUTPUT_DIR / slug
    out_path = output_slug_dir / f"{slug}-map.jpg"

    if out_path.exists():
        return out_path

    print(f"    Fetching route for map...")
    coords = fetch_route_coordinates(rwgps_id)
    if not coords:
        print(f"    No track points for map")
        return None

    # Downsample for URL length limit
    ds_coords = downsample_coords(coords, max_points=100)
    polyline = encode_polyline(ds_coords)

    if dry_run:
        print(f"    Map polyline: {len(polyline)} chars from {len(coords)} points "
              f"(downsampled to {len(ds_coords)})")
        return None

    output_slug_dir.mkdir(parents=True, exist_ok=True)

    # Build URL with brand color path overlay
    # Brand primary brown: #59473c → 0x59473cFF (with full opacity)
    path_param = f"color:0x59473cFF|weight:4|enc:{polyline}"

    params = {
        "size": STREET_VIEW_SIZE,
        "maptype": "hybrid",
        "path": path_param,
        "key": api_key,
        "format": "jpg",
    }

    print(f"    Fetching Maps Static API...")
    try:
        resp = requests.get(MAPS_STATIC_URL, params=params, timeout=15)
        resp.raise_for_status()
        if len(resp.content) < 5000:
            print(f"    SKIP: Map response too small ({len(resp.content)} bytes)")
            return None
        out_path.write_bytes(resp.content)
        print(f"    Saved: {out_path.name}")
        return out_path
    except Exception as e:
        print(f"    Map API error: {e}")
        return None


# ── Hero Selection ─────────────────────────────────────────────

def select_hero(slug: str, photos: list[dict]) -> list[dict]:
    """Auto-select hero image: best street view > landscape > map.

    Marks the chosen photo with primary=True and copies as {slug}-hero.jpg.
    """
    output_slug_dir = OUTPUT_DIR / slug

    # Priority: street-1 > street-2 > landscape > map
    priority = ["street-1", "street-2", "street-3", "landscape", "map"]

    hero_source = None
    for ptype in priority:
        for p in photos:
            if p["type"] == ptype:
                hero_source = p
                break
        if hero_source:
            break

    if not hero_source:
        return photos

    # Copy as hero
    src = output_slug_dir / hero_source["file"]
    dst = output_slug_dir / f"{slug}-hero.jpg"
    if src.exists() and not dst.exists():
        shutil.copy2(str(src), str(dst))

    # Mark primary
    hero_entry = {
        "type": "hero",
        "file": f"{slug}-hero.jpg",
        "url": f"/race-photos/{slug}/{slug}-hero.jpg",
        "alt": hero_source["alt"],
        "credit": hero_source["credit"],
        "primary": True,
    }
    # Clear primary from others
    for p in photos:
        p["primary"] = False
    photos.append(hero_entry)

    return photos


# ── JSON Update ────────────────────────────────────────────────

def update_race_json(slug: str, photos: list[dict]):
    """Write photos array to race JSON, matching generate_neo_brutalist.py schema.

    Schema expected:
      race.photos[] = [
        {"url": "/race-photos/{slug}/{file}", "alt": "...", "credit": "...", "primary": bool}
      ]
    """
    data_file = DATA_DIR / f"{slug}.json"
    if not data_file.exists():
        return

    with open(data_file) as f:
        data = json.load(f)

    data["race"]["photos"] = photos

    with open(data_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


# ── Orchestrator ───────────────────────────────────────────────

def process_race(
    slug: str,
    race: dict,
    layers: list[str],
    engine: str,
    google_key: str | None,
    dry_run: bool,
) -> dict:
    """Process one race through all requested layers."""
    results = {"slug": slug, "photos": [], "errors": 0}
    rwgps_id = None

    # ridewithgps_id is in course_description
    course = race.get("course_description", {})
    if isinstance(course, dict):
        rwgps_id = course.get("ridewithgps_id")

    name = race.get("name", slug)
    vitals = race.get("vitals", {})
    location = vitals.get("location", "")
    terrain_raw = race.get("terrain", {})
    terrain_primary = ""
    if isinstance(terrain_raw, dict):
        terrain_primary = terrain_raw.get("primary", "")
        if isinstance(terrain_primary, dict):
            terrain_primary = terrain_primary.get("type", "")

    # Credit strings
    credit_sv = "Google Street View"
    credit_ai = "AI Generated"
    credit_map = "Google Maps"

    # Layer 1: Street View
    if "street" in layers and rwgps_id and (google_key or dry_run):
        try:
            paths = generate_street_views(slug, rwgps_id, google_key or "", dry_run)
            for p in paths:
                n = p.stem.split("-")[-1]  # "1", "2", "3"
                results["photos"].append({
                    "type": f"street-{n}",
                    "file": p.name,
                    "url": f"/race-photos/{slug}/{p.name}",
                    "alt": f"Course view of {name} near {location}" if location else f"Course view of {name}",
                    "credit": credit_sv,
                    "primary": False,
                })
        except Exception as e:
            print(f"    Street View error: {e}")
            results["errors"] += 1
    elif "street" in layers and not rwgps_id:
        print(f"    SKIP street: No RWGPS route ID")

    # Layer 2: AI Landscape
    if "landscape" in layers:
        try:
            paths = generate_landscape(slug, race, engine, dry_run)
            for p in paths:
                # Only include production files (not _comparison)
                if "_comparison" not in str(p):
                    results["photos"].append({
                        "type": "landscape",
                        "file": p.name,
                        "url": f"/race-photos/{slug}/{p.name}",
                        "alt": f"Landscape of {terrain_primary} near {location}" if location else f"Landscape along the {name} course",
                        "credit": credit_ai,
                        "primary": False,
                    })
        except Exception as e:
            print(f"    Landscape error: {e}")
            results["errors"] += 1

    # Layer 3: Route Map
    if "map" in layers and rwgps_id and (google_key or dry_run):
        try:
            # Rate limit: reuse coords from street view if possible
            if not dry_run:
                time.sleep(RWGPS_DELAY)
            path = generate_route_map(slug, rwgps_id, google_key or "", dry_run)
            if path:
                results["photos"].append({
                    "type": "map",
                    "file": path.name,
                    "url": f"/race-photos/{slug}/{path.name}",
                    "alt": f"Satellite route overview of {name}",
                    "credit": credit_map,
                    "primary": False,
                })
        except Exception as e:
            print(f"    Map error: {e}")
            results["errors"] += 1
    elif "map" in layers and not rwgps_id:
        print(f"    SKIP map: No RWGPS route ID")

    # Hero selection (skip in dry-run)
    if not dry_run and results["photos"]:
        results["photos"] = select_hero(slug, results["photos"])
        update_race_json(slug, results["photos"])

    return results


# ── Status Report ──────────────────────────────────────────────

def print_status():
    """Print coverage report of generated photos."""
    all_slugs = [f.stem for f in sorted(DATA_DIR.glob("*.json"))]
    total_races = len(all_slugs)

    stats = {
        "hero": 0, "street": 0, "landscape": 0, "map": 0,
        "complete": 0, "partial": 0, "missing": 0, "total_files": 0,
    }

    for slug in all_slugs:
        slug_dir = OUTPUT_DIR / slug
        if not slug_dir.is_dir():
            stats["missing"] += 1
            continue

        files = list(slug_dir.glob("*.jpg"))
        if not files:
            stats["missing"] += 1
            continue

        stats["total_files"] += len(files)
        has_hero = any(f.name.endswith("-hero.jpg") for f in files)
        has_street = any("-street-" in f.name for f in files)
        has_landscape = any("-landscape.jpg" in f.name for f in files)
        has_map = any("-map.jpg" in f.name for f in files)

        if has_hero:
            stats["hero"] += 1
        if has_street:
            stats["street"] += 1
        if has_landscape:
            stats["landscape"] += 1
        if has_map:
            stats["map"] += 1

        # Complete = at least hero + one other
        if has_hero and (has_street or has_landscape or has_map):
            stats["complete"] += 1
        else:
            stats["partial"] += 1

    # Count RWGPS coverage
    rwgps_count = 0
    for slug in all_slugs:
        data_file = DATA_DIR / f"{slug}.json"
        with open(data_file) as f:
            data = json.load(f)
        race = data.get("race", data)
        course = race.get("course_description", {})
        if isinstance(course, dict) and course.get("ridewithgps_id"):
            rwgps_count += 1

    # Total file size
    total_size = 0
    if OUTPUT_DIR.exists():
        for f in OUTPUT_DIR.rglob("*.jpg"):
            if "_comparison" not in str(f):
                total_size += f.stat().st_size

    print(f"\nRace Photo Pipeline Status")
    print(f"{'='*40}")
    print(f"  Total races:        {total_races}")
    print(f"  RWGPS routes:       {rwgps_count} ({rwgps_count*100//total_races}%)")
    print(f"")
    print(f"  Hero images:        {stats['hero']}")
    print(f"  Street View:        {stats['street']}")
    print(f"  AI Landscapes:      {stats['landscape']}")
    print(f"  Route Maps:         {stats['map']}")
    print(f"")
    print(f"  Complete:           {stats['complete']}")
    print(f"  Partial:            {stats['partial']}")
    print(f"  Missing:            {stats['missing']}")
    print(f"  Total files:        {stats['total_files']}")
    if total_size > 0:
        print(f"  Total size:         {total_size / 1024 / 1024:.1f} MB")

    # Comparison dir
    if COMPARISON_DIR.exists():
        comp_files = list(COMPARISON_DIR.glob("*.jpg"))
        if comp_files:
            print(f"\n  Comparison images:  {len(comp_files)} (in _comparison/)")


# ── CLI ────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate race photos: Street View + AI Landscapes + Route Maps"
    )
    parser.add_argument("--slug", help="Generate for a single race slug")
    parser.add_argument("--all", action="store_true", help="Generate for all races")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4],
                        help="Filter to specific tier")
    parser.add_argument("--layer", nargs="+",
                        choices=["street", "landscape", "map"],
                        default=["street", "landscape", "map"],
                        help="Which layers to generate (default: all)")
    parser.add_argument("--engine",
                        choices=["stability", "gemini", "both"],
                        default="both",
                        help="AI engine for landscape layer (default: both)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be generated without calling APIs")
    parser.add_argument("--concurrency", type=int, default=3,
                        help="Max concurrent operations (default: 3)")
    parser.add_argument("--status", action="store_true",
                        help="Print coverage report")
    args = parser.parse_args()

    if args.status:
        print_status()
        return

    if not args.slug and not args.all:
        parser.error("Provide --slug, --all, or --status")

    # Collect slugs
    if args.all:
        slugs = [f.stem for f in sorted(DATA_DIR.glob("*.json"))]
    else:
        slugs = [args.slug]

    # Filter by tier if requested
    if args.tier:
        filtered = []
        for slug in slugs:
            data_file = DATA_DIR / f"{slug}.json"
            if not data_file.exists():
                continue
            with open(data_file) as f:
                data = json.load(f)
            race = data.get("race", data)
            rating = race.get("gravel_god_rating", {})
            if rating.get("display_tier") == args.tier:
                filtered.append(slug)
        slugs = filtered

    # Check API keys
    google_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    stability_key = os.environ.get("STABILITY_API_KEY")

    if not args.dry_run:
        if ("street" in args.layer or "map" in args.layer) and not google_key:
            print("WARNING: GOOGLE_MAPS_API_KEY not set. Street View and Map layers will be skipped.")
            print("  Set in .env: GOOGLE_MAPS_API_KEY=...")
        if "landscape" in args.layer:
            if args.engine in ("stability", "both") and not stability_key:
                print("WARNING: STABILITY_API_KEY not set. Stability AI will be skipped.")
                print("  Set in .env: STABILITY_API_KEY=...")
            gemini_key = (os.environ.get("GOOGLE_API_KEY")
                          or os.environ.get("GEMINI_API_KEY")
                          or os.environ.get("GOOGLE_AI_API_KEY"))
            if args.engine in ("gemini", "both") and not gemini_key:
                print("WARNING: GOOGLE_API_KEY not set. Gemini will be skipped.")
                print("  Set in .env: GOOGLE_API_KEY=...")

    print(f"Generating photos for {len(slugs)} race(s)")
    print(f"  Layers: {', '.join(args.layer)}")
    print(f"  Engine: {args.engine}")
    if args.dry_run:
        print(f"  (dry-run mode)")
    print()

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

        print(f"  [{i}/{len(slugs)}] {slug}")
        result = process_race(
            slug=slug,
            race=race,
            layers=args.layer,
            engine=args.engine,
            google_key=google_key,
            dry_run=args.dry_run,
        )
        total_generated += len(result["photos"])
        total_errors += result["errors"]

        # Rate limit between races (for RWGPS requests)
        if not args.dry_run and i < len(slugs):
            time.sleep(RWGPS_DELAY)

    elapsed = time.time() - start_time
    print(f"\nDone. {total_generated} photos for {len(slugs)} races in {elapsed:.0f}s")
    if total_errors:
        print(f"  {total_errors} errors")

    # Cost estimate
    if not args.dry_run and total_generated > 0:
        # Rough estimate based on what we generated
        est = 0
        for slug in slugs:
            slug_dir = OUTPUT_DIR / slug
            if not slug_dir.is_dir():
                continue
            for f in slug_dir.glob("*.jpg"):
                if "-street-" in f.name:
                    est += COST_STREET_VIEW
                elif "-landscape" in f.name:
                    est += COST_STABILITY if args.engine == "stability" else COST_GEMINI
                elif "-map" in f.name:
                    est += COST_MAP
        print(f"  Est. cost: ${est:.2f}")


if __name__ == "__main__":
    main()
