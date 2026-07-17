#!/usr/bin/env python3
"""
Fetch and cache real RideWithGPS route geometry for the race-page redesign's
"real map" card/hero treatment.

Separate from fetch_rwgps_routes.py, which only *resolves* a ridewithgps_id by
fuzzy name/distance/location matching. This script assumes ridewithgps_id is
already correct (race-data/<slug>.json -> race.course_description.ridewithgps_id)
and fetches the actual track geometry for that route, projects it into a
normalized SVG viewBox, and caches it to data/route-geometry/<slug>.json.

The generator (wordpress/generate_race_page_v2.py) reads only this cache at
page-build time — no live API calls happen during page generation, per the
handoff's "deterministic rebuilds, no live API calls at generate time" rule.

NEVER fabricates a route: races without a ridewithgps_id are simply skipped
(the template layer renders an explicit "no verified route on file" state for
them), and any race whose fetch fails (404, private route, malformed data) is
also skipped rather than filled in with a placeholder line.

Usage:
    python3 scripts/fetch_route_geometry.py                  # all races with rwgps id
    python3 scripts/fetch_route_geometry.py --race steamboat-gravel
    python3 scripts/fetch_route_geometry.py --dry-run
    python3 scripts/fetch_route_geometry.py --stats
"""

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

RACE_DATA = Path(__file__).resolve().parent.parent / "race-data"
GEOMETRY_DIR = Path(__file__).resolve().parent.parent / "data" / "route-geometry"
ROUTE_JSON_URL = "https://ridewithgps.com/routes/{id}.json"
RATE_LIMIT_SECONDS = 1.1  # matches fetch_rwgps_routes.py's courtesy rate limit
REQUEST_TIMEOUT = 15
USER_AGENT = "GravelGodRaceDB/1.0 (route geometry cache; contact gravelgodcoaching@gmail.com)"

TARGET_POINTS = 350  # downsample target for the cached path (visual fidelity is plenty at this count)
PADDING_FRAC = 0.04  # viewBox padding as a fraction of the larger bbox dimension


def load_race_files() -> list[Path]:
    return sorted(RACE_DATA.glob("*.json"))


def get_rwgps_id(race_json: dict) -> str | None:
    course = race_json.get("race", {}).get("course_description", {})
    if isinstance(course, dict):
        rid = course.get("ridewithgps_id")
        if rid:
            return str(rid)
    return None


def fetch_route_json(route_id: str) -> dict | None:
    url = ROUTE_JSON_URL.format(id=route_id)
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP error {e.code} fetching route {route_id}")
        return None
    except urllib.error.URLError as e:
        print(f"  Connection error fetching route {route_id}: {e.reason}")
        return None
    except json.JSONDecodeError as e:
        print(f"  Invalid JSON for route {route_id}: {e}")
        return None
    except Exception as e:
        print(f"  Unexpected error fetching route {route_id}: {e}")
        return None


def downsample(points: list[dict], target: int) -> list[dict]:
    """Stride-based downsample. Keeps first/last point, evenly spaced between."""
    n = len(points)
    if n <= target:
        return points
    stride = n / target
    out = []
    i = 0.0
    while int(i) < n:
        out.append(points[int(i)])
        i += stride
    if out[-1] is not points[-1]:
        out.append(points[-1])
    return out


def project_to_viewbox(points: list[dict]) -> dict | None:
    """Project lon/lat track points into a normalized, north-up SVG viewBox.

    Equirectangular projection with a cos(mean latitude) correction on
    longitude (flat-earth approximation, fine at race-course scale — this is
    a stylized wayfinding graphic, not a navigational map). Scaled to fit a
    bounding box with padding, aspect ratio preserved (no stretching).
    """
    lons = [p["x"] for p in points if "x" in p and "y" in p]
    lats = [p["y"] for p in points if "x" in p and "y" in p]
    if len(lons) < 2:
        return None

    lat_mean = sum(lats) / len(lats)
    cos_lat = math.cos(math.radians(lat_mean))

    xs = [lon * cos_lat for lon in lons]
    ys = [-lat for lat in lats]  # invert so increasing SVG y = south (north-up)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max_x - min_x or 1e-9
    span_y = max_y - min_y or 1e-9

    # Orientation: prefer a portrait viewBox (800x1000) for tall/narrow routes,
    # landscape (800x600) otherwise — matches the two viewBox shapes used in
    # the canonical prototype (preview-real-map-card-v5.html).
    aspect = span_x / span_y
    if aspect < 0.8:
        vb_w, vb_h = 800, 1000
    else:
        vb_w, vb_h = 800, 600

    pad = PADDING_FRAC * max(vb_w, vb_h)
    avail_w = vb_w - 2 * pad
    avail_h = vb_h - 2 * pad
    scale = min(avail_w / span_x, avail_h / span_y)

    draw_w = span_x * scale
    draw_h = span_y * scale
    offset_x = pad + (avail_w - draw_w) / 2
    offset_y = pad + (avail_h - draw_h) / 2

    def to_svg(x, y):
        sx = offset_x + (x - min_x) * scale
        sy = offset_y + (y - min_y) * scale
        return round(sx, 1), round(sy, 1)

    coords = [to_svg(x, y) for x, y in zip(xs, ys)]
    path_d = "M" + "L".join(f"{x} {y}" for x, y in coords)

    return {
        "viewbox": f"0 0 {vb_w} {vb_h}",
        "path_d": path_d,
    }


def build_geometry_record(slug: str, route_id: str, route_json: dict) -> dict | None:
    route = route_json.get("route", route_json)
    track_points = route.get("track_points") or []
    if len(track_points) < 2:
        print(f"  {slug}: route {route_id} has no usable track_points, skipping")
        return None

    sampled = downsample(track_points, TARGET_POINTS)
    projected = project_to_viewbox(sampled)
    if not projected:
        print(f"  {slug}: route {route_id} failed to project (degenerate geometry), skipping")
        return None

    distance_m = route.get("distance")
    distance_mi = round(distance_m / 1609.34, 1) if isinstance(distance_m, (int, float)) else None

    return {
        "slug": slug,
        "ridewithgps_id": route_id,
        "route_name": route.get("name", ""),
        "source_url": f"https://ridewithgps.com/routes/{route_id}",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "point_count": len(track_points),
        "sampled_count": len(sampled),
        "distance_mi_from_geometry": distance_mi,
        "viewbox": projected["viewbox"],
        "path_d": projected["path_d"],
    }


def process_race(filepath: Path, dry_run: bool, force: bool) -> str:
    slug = filepath.stem
    race_json = json.load(open(filepath, encoding="utf-8"))
    rwgps_id = get_rwgps_id(race_json)
    if not rwgps_id:
        return "no_id"

    out_path = GEOMETRY_DIR / f"{slug}.json"
    if out_path.exists() and not force:
        existing = json.load(open(out_path, encoding="utf-8"))
        if existing.get("ridewithgps_id") == rwgps_id:
            return "cached"

    print(f"{slug}: fetching route {rwgps_id}...")
    route_json = fetch_route_json(rwgps_id)
    if not route_json:
        return "fetch_failed"

    record = build_geometry_record(slug, rwgps_id, route_json)
    if not record:
        return "no_geometry"

    if dry_run:
        print(f"  [DRY RUN] Would write {out_path} "
              f"({record['sampled_count']} pts, viewBox {record['viewbox']})")
    else:
        GEOMETRY_DIR.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"  Wrote {out_path} ({record['sampled_count']} pts, viewBox {record['viewbox']})")
    return "ok"


def run_stats():
    files = load_race_files()
    with_id = 0
    cached = 0
    for f in files:
        race_json = json.load(open(f, encoding="utf-8"))
        if get_rwgps_id(race_json):
            with_id += 1
    if GEOMETRY_DIR.exists():
        cached = len(list(GEOMETRY_DIR.glob("*.json")))
    print(f"Races with ridewithgps_id: {with_id}/{len(files)}")
    print(f"Cached geometry files: {cached}")


def main():
    parser = argparse.ArgumentParser(description="Fetch + cache RWGPS route geometry for race pages.")
    parser.add_argument("--race", help="Single race slug")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fetched without writing")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if a cache entry already exists")
    parser.add_argument("--stats", action="store_true", help="Show coverage stats and exit")
    args = parser.parse_args()

    if args.stats:
        run_stats()
        return

    if args.race:
        files = [RACE_DATA / f"{args.race}.json"]
        if not files[0].exists():
            print(f"ERROR: no race-data file for slug '{args.race}'", file=sys.stderr)
            sys.exit(1)
    else:
        files = load_race_files()

    counts = {"ok": 0, "cached": 0, "no_id": 0, "fetch_failed": 0, "no_geometry": 0}
    for i, f in enumerate(files):
        result = process_race(f, args.dry_run, args.force)
        counts[result] = counts.get(result, 0) + 1
        if result == "ok" and not args.dry_run and i < len(files) - 1:
            time.sleep(RATE_LIMIT_SECONDS)

    print("\nDone.")
    print(f"  fetched:      {counts['ok']}")
    print(f"  already cached: {counts['cached']}")
    print(f"  no rwgps id:  {counts['no_id']}")
    print(f"  fetch failed: {counts['fetch_failed']}")
    print(f"  no geometry:  {counts['no_geometry']}")


if __name__ == "__main__":
    main()
