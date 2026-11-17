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

from __future__ import annotations

import argparse
import io
import json
import math
import re
import sys
import time
import zipfile
import xml.etree.ElementTree as ET
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))
import official_route  # noqa: E402

RACE_DATA = Path(__file__).resolve().parent.parent / "race-data"
GEOMETRY_DIR = Path(__file__).resolve().parent.parent / "data" / "route-geometry"
ROUTE_JSON_URL = "https://ridewithgps.com/routes/{id}.json"
STRAVA_EMBED_URL = "https://strava-embeds.com/route/{id}"
KOMOOT_COORDS_URL = "https://www.komoot.com/api/v007/tours/{id}/coordinates"
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
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


def get_rwgps_privacy_code(race_json: dict) -> str | None:
    course = race_json.get("race", {}).get("course_description", {})
    if isinstance(course, dict):
        return official_route.valid_privacy_code(course.get("ridewithgps_privacy_code"))
    return None


def fetch_route_json(route_id: str, privacy_code: str | None = None) -> dict | None:
    url = ROUTE_JSON_URL.format(id=route_id)
    if privacy_code:
        url += f"?privacy_code={privacy_code}"
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


def downsample_segments(points: list[dict], target: int) -> list[dict]:
    """Downsample each segment in proportion to its size, keeping its ends."""
    segments: list[list[dict]] = []
    for p in points:
        if not segments or segments[-1][-1].get("seg", 0) != p.get("seg", 0):
            segments.append([])
        segments[-1].append(p)
    out = []
    for seg in segments:
        if len(seg) < 2:
            continue
        share = max(2, round(target * len(seg) / len(points)))
        out.extend(downsample(seg, share))
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

    valid = [p for p in points if "x" in p and "y" in p]
    parts = []
    prev_seg = None
    for p, x, y in zip(valid, xs, ys):
        sx, sy = to_svg(x, y)
        seg = p.get("seg", 0)
        parts.append(f"{'M' if seg != prev_seg else 'L'}{sx} {sy}")
        prev_seg = seg
    path_d = "".join(parts)

    return {
        "viewbox": f"0 0 {vb_w} {vb_h}",
        "path_d": path_d,
    }


def build_geometry_record(slug: str, route_id: str, route_json: dict,
                          privacy_code: str | None = None) -> dict | None:
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
        "source_url": official_route.rwgps_route_url(route_id, privacy_code),
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
        route = official_route.get_official_route(
            race_json.get("race", {}).get("course_description"))
        if route:
            return process_official_route(slug, route, dry_run, force)
        return "no_id"
    privacy_code = get_rwgps_privacy_code(race_json)

    out_path = GEOMETRY_DIR / f"{slug}.json"
    if out_path.exists() and not force:
        existing = json.load(open(out_path, encoding="utf-8"))
        if existing.get("ridewithgps_id") == rwgps_id:
            return "cached"

    print(f"{slug}: fetching route {rwgps_id}...")
    route_json = fetch_route_json(rwgps_id, privacy_code)
    if not route_json:
        return "fetch_failed"

    record = build_geometry_record(slug, rwgps_id, route_json, privacy_code)
    if not record:
        return "no_geometry"
    return write_record(out_path, record, dry_run)


def write_record(out_path: Path, record: dict, dry_run: bool) -> str:
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


# ── Official routes published off RideWithGPS (issue #670) ──────────────

def _download(url: str) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT * 2) as resp:
            data = resp.read(MAX_DOWNLOAD_BYTES + 1)
    except (urllib.error.URLError, OSError) as e:
        print(f"  download failed for {url}: {e}")
        return None
    if len(data) > MAX_DOWNLOAD_BYTES:
        print(f"  {url} is larger than {MAX_DOWNLOAD_BYTES} bytes, skipping")
        return None
    return data


def _parse_xml(data: bytes):
    # Route files are untrusted: refuse DTDs/entities outright.
    if b"<!DOCTYPE" in data[:4096] or b"<!ENTITY" in data:
        raise ValueError("XML with a DTD is not accepted")
    return ET.fromstring(data)


def points_from_gpx(data: bytes) -> list[dict]:
    """Track points (else route points) from a GPX file, as {x: lon, y: lat}."""
    root = _parse_xml(data)
    pts = []
    for container, tag in (("trkseg", "trkpt"), ("rte", "rtept")):
        for seg, parent in enumerate(
                el for el in root.iter() if el.tag.rsplit("}", 1)[-1] == container):
            for el in parent:
                if el.tag.rsplit("}", 1)[-1] != tag:
                    continue
                try:
                    pts.append({"x": float(el.attrib["lon"]), "y": float(el.attrib["lat"]),
                                "seg": seg})
                except (KeyError, ValueError):
                    continue
        if pts:
            break
    return pts


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _skipped_line_strings(root, exclude: str | None) -> set:
    """LineStrings inside Placemarks whose name matches ``exclude`` — e.g. an
    organizer file that carries optional bypasses beside the main route."""
    if not exclude:
        return set()
    pattern = re.compile(exclude)
    skipped = set()
    for pm in root.iter():
        if _local(pm.tag) != "Placemark":
            continue
        name = next((c.text or "" for c in pm if _local(c.tag) == "name"), "")
        if pattern.search(name):
            skipped.update(el for el in pm.iter() if _local(el.tag) == "LineString")
    return skipped


def points_from_kml(data: bytes, exclude: str | None = None) -> list[dict]:
    """Coordinates of every LineString in a KML document, in order."""
    root = _parse_xml(data)
    skipped = _skipped_line_strings(root, exclude)
    pts = []
    seg = -1
    for el in root.iter():
        if _local(el.tag) == "LineString" and el not in skipped:
            seg += 1
            for child in el:
                if child.tag.rsplit("}", 1)[-1] == "coordinates" and child.text:
                    for triple in child.text.split():
                        parts = triple.split(",")
                        if len(parts) >= 2:
                            try:
                                pts.append({"x": float(parts[0]), "y": float(parts[1]), "seg": seg})
                            except ValueError:
                                continue
    return pts


def points_from_archive(data: bytes, exclude: str | None = None) -> list[dict]:
    """A KMZ/ZIP holding exactly one GPX or KML route file."""
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        names = [n for n in zf.namelist()
                 if not n.startswith("__MACOSX/") and n.lower().endswith((".gpx", ".kml"))]
        if len(names) != 1:
            print(f"  archive holds {len(names)} route files, expected exactly one")
            return []
        info = zf.getinfo(names[0])
        if info.file_size > MAX_DOWNLOAD_BYTES:
            return []
        inner = zf.read(names[0])
    return points_from_gpx(inner) if names[0].lower().endswith(".gpx") else points_from_kml(inner, exclude)


def decode_polyline(encoded: str) -> list[dict]:
    """Google encoded polyline -> [{x: lon, y: lat}]."""
    pts, index, lat, lng = [], 0, 0, 0
    while index < len(encoded):
        for which in (0, 1):
            shift = result = 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else result >> 1
            if which == 0:
                lat += delta
            else:
                lng += delta
        pts.append({"x": lng / 1e5, "y": lat / 1e5})
    return pts


_ROUTE_DATA = re.compile(
    r'<script id="__ROUTE_DATA__" type="application/json">(.*?)</script>', re.S)


def points_from_strava_embed(html_text: str) -> list[dict]:
    """The route line from Strava's public route embed for that route."""
    m = _ROUTE_DATA.search(html_text)
    if not m:
        return []
    data = json.loads(m.group(1))
    pts = []
    for leg in data.get("legs") or []:
        for path in leg.get("paths") or []:
            poly = path.get("polyline") or {}
            if poly.get("encoding") == "Google" and poly.get("data"):
                pts.extend(decode_polyline(poly["data"]))
    # Strava splits one continuous route into legs; consecutive legs share
    # their join point, so they stay a single segment.
    return pts


def official_route_points(route: dict) -> list[dict] | None:
    provider = route["provider"]
    url = route["url"]
    if provider == "strava":
        rid = official_route.strava_route_id(url)
        data = _download(STRAVA_EMBED_URL.format(id=rid)) if rid else None
        return points_from_strava_embed(data.decode("utf-8", "replace")) if data else None
    if provider == "komoot":
        tid = official_route.komoot_tour_id(url)
        data = _download(KOMOOT_COORDS_URL.format(id=tid)) if tid else None
        if not data:
            return None
        items = json.loads(data).get("items") or []
        return [{"x": p["lng"], "y": p["lat"]} for p in items if "lng" in p and "lat" in p]
    if provider in ("gpx", "kmz"):
        data = _download(route.get("download_url") or url)
        if not data:
            return None
        exclude = route.get("exclude_placemarks")
        if data[:2] == b"PK":
            return points_from_archive(data, exclude)
        head = data[:2048].lower()
        if b"<gpx" in head:
            return points_from_gpx(data)
        if b"<kml" in head:
            return points_from_kml(data, exclude)
        print(f"  {url} is neither GPX, KML nor an archive")
        return []
    return None


def track_distance_km(points: list[dict]) -> float:
    total = 0.0
    for a, b in zip(points, points[1:]):
        if a.get("seg", 0) != b.get("seg", 0):
            continue
        p1, p2 = math.radians(a["y"]), math.radians(b["y"])
        dphi = p2 - p1
        dl = math.radians(b["x"] - a["x"])
        h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        total += 2 * 6371.0088 * math.asin(math.sqrt(h))
    return total


def build_official_record(slug: str, route: dict, points: list[dict]) -> dict | None:
    if len(points) < 2:
        return None
    sampled = downsample_segments(points, TARGET_POINTS)
    projected = project_to_viewbox(sampled)
    if not projected:
        return None
    return {
        "slug": slug,
        "official_route_url": route["url"],
        "provider": route["provider"],
        "provenance_url": route["provenance_url"],
        "route_name": route.get("name", ""),
        "source_url": route["url"],
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "point_count": len(points),
        "sampled_count": len(sampled),
        "distance_mi_from_geometry": round(track_distance_km(points) / 1.609344, 1),
        "viewbox": projected["viewbox"],
        "path_d": projected["path_d"],
    }


def process_official_route(slug: str, route: dict, dry_run: bool, force: bool) -> str:
    if route["provider"] not in official_route.GEOMETRY_PROVIDERS:
        return "no_id"
    out_path = GEOMETRY_DIR / f"{slug}.json"
    if out_path.exists() and not force:
        existing = json.load(open(out_path, encoding="utf-8"))
        if existing.get("official_route_url") == route["url"]:
            return "cached"
    print(f"{slug}: fetching official {route['provider']} route {route['url']}...")
    try:
        points = official_route_points(route)
    except (ValueError, ET.ParseError, zipfile.BadZipFile, json.JSONDecodeError) as e:
        print(f"  {slug}: could not read route: {e}")
        return "no_geometry"
    if points is None:
        return "fetch_failed"
    record = build_official_record(slug, route, points)
    if not record:
        print(f"  {slug}: route has no usable geometry, skipping")
        return "no_geometry"
    return write_record(out_path, record, dry_run)


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
