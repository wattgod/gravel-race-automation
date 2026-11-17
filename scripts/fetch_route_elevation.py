#!/usr/bin/env python3
"""Cache the elevation profile of each race's RideWithGPS route.

The race page's Course Dossier hero draws the course's elevation profile. This
reads the same RideWithGPS route the race profile lists
(race.course_description.ridewithgps_id, the route fetch_route_geometry.py
already maps), resamples its track points at even distance steps and writes
data/route-elevation/<slug>.json. Page generation reads only this cache.

Never fabricates: a race with no RideWithGPS id, a failed fetch, or a route
whose track points carry no elevation is skipped, and the page then shows no
profile.

Usage:
    python3 scripts/fetch_route_elevation.py                 # every race with an id
    python3 scripts/fetch_route_elevation.py --race unbound-200
    python3 scripts/fetch_route_elevation.py --force         # refetch cached ones
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_route_geometry as geo  # noqa: E402

ELEVATION_DIR = Path(__file__).resolve().parent.parent / "data" / "route-elevation"
SAMPLES = 400


def resample(points: list[dict], samples: int = SAMPLES) -> tuple[list[float], list[float]] | None:
    """(distance_km, elevation_m) at ``samples`` even distance steps, or None."""
    track = [(float(p["d"]), float(p["e"])) for p in points
             if isinstance(p.get("d"), (int, float)) and isinstance(p.get("e"), (int, float))]
    if len(track) < 2:
        return None
    track.sort(key=lambda t: t[0])
    total = track[-1][0] - track[0][0]
    if total <= 0:
        return None
    start = track[0][0]
    dist, ele = [], []
    j = 0
    for i in range(samples):
        target = start + total * i / (samples - 1)
        while j < len(track) - 2 and track[j + 1][0] < target:
            j += 1
        (d0, e0), (d1, e1) = track[j], track[j + 1]
        t = 0.0 if d1 == d0 else min(1.0, max(0.0, (target - d0) / (d1 - d0)))
        dist.append(round((target - start) / 1000, 3))
        ele.append(round(e0 + (e1 - e0) * t, 1))
    return dist, ele


def build_record(slug: str, route_id: str, route_json: dict,
                 privacy_code: str | None) -> dict | None:
    route = route_json.get("route", route_json)
    sampled = resample(route.get("track_points") or [])
    if not sampled:
        return None
    dist, ele = sampled
    raw = [float(p["e"]) for p in route.get("track_points") or []
           if isinstance(p.get("e"), (int, float))]
    return {
        "slug": slug,
        "ridewithgps_id": route_id,
        "route_name": (route.get("name") or "").strip(),
        "source_url": geo.official_route.rwgps_route_url(route_id, privacy_code),
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "distance_km": dist,
        "elevation_m": ele,
        "high_m": round(max(raw), 1),
        "low_m": round(min(raw), 1),
    }


def process(path: Path, force: bool) -> str:
    slug = path.stem
    race_json = json.loads(path.read_text(encoding="utf-8"))
    route_id = geo.get_rwgps_id(race_json)
    if not route_id:
        return "no_id"
    out = ELEVATION_DIR / f"{slug}.json"
    if out.exists() and not force:
        if json.loads(out.read_text(encoding="utf-8")).get("ridewithgps_id") == route_id:
            return "cached"
    privacy = geo.get_rwgps_privacy_code(race_json)
    route_json = geo.fetch_route_json(route_id, privacy)
    time.sleep(geo.RATE_LIMIT_SECONDS)
    if not route_json:
        return "fetch_failed"
    record = build_record(slug, route_id, route_json, privacy)
    if not record:
        return "no_elevation"
    ELEVATION_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, separators=(",", ":")) + "\n", encoding="utf-8")
    return "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--race")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    files = ([geo.RACE_DATA / f"{args.race}.json"] if args.race
             else geo.load_race_files())
    counts: dict[str, int] = {}
    for path in files:
        result = process(path, args.force)
        counts[result] = counts.get(result, 0) + 1
        if result not in ("no_id", "cached"):
            print(f"{path.stem}: {result}", flush=True)
    print(json.dumps(counts, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
