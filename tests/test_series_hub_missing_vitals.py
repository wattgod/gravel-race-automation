"""Series hubs render when a round publishes no distance or climbing figure.

BWR Mexico (Nov 2026) publishes 180 km but no elevation gain, so its
profile stores elevation_ft: null. The distance/elevation chart crashed on
max(None, int), which would stop Publish Site's build.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_series_hubs import build_distance_elevation_svg  # noqa: E402


def _series(*slugs):
    return {"name": "BWR", "events": [
        {"name": f"BWR {s}", "slug": s, "has_profile": True} for s in slugs]}


def _vitals(dist, elev):
    return {"vitals": {"distance_mi": dist, "elevation_ft": elev}}


def test_null_elevation_renders_not_published():
    svg = build_distance_elevation_svg(
        _series("a", "b"), {"a": _vitals(112, None), "b": _vitals(130, 11000)})
    assert "not published" in svg
    assert "11,000 ft" in svg and "112 mi" in svg


def test_null_distance_renders_not_published():
    svg = build_distance_elevation_svg(
        _series("a", "b"), {"a": _vitals(None, 5000), "b": _vitals(130, 11000)})
    assert "not published" in svg
    assert "5,000 ft" in svg


def test_real_bwr_hub_builds():
    import generate_series_hubs as gsh
    import json
    series = json.loads((ROOT / "series-data" / "belgian-waffle-ride.json").read_text())["series"]
    race_data = {}
    for e in series["events"]:
        p = ROOT / "race-data" / f"{e.get('slug')}.json"
        if e.get("slug") and p.exists():
            race_data[e["slug"]] = json.loads(p.read_text())["race"]
    assert gsh.build_distance_elevation_svg(series, race_data)
