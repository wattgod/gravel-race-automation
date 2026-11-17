"""Organizer-verified course routes added in issue #661 (Nov 17 2026).

Every route here is either linked from the organizer's own page or owned by
the organizer's RideWithGPS account, and matches the profile's distance and
start. Each one must stay cited, and its cached geometry must describe the
same route id the profile carries.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = ROOT / "race-data"
GEOMETRY_DIR = ROOT / "data" / "route-geometry"

VERIFIED_ROUTES = {
    "big-sugar": "55885093",
    "bighorn-gravel": "52734716",
    "lauf-true-grit": "42244960",
    "gray-duck-grit": "56301537",
    "reliance-tennessee-gravel": "56181185",
    "the-grit-adventure": "55128073",
    "hibernator": "47924518",
    "real-west-gravel": "50097003",
    "bwr-california": "54026340",
    "glengarry-games-gravel-run": "51993288",
    "low-gap-grasshopper": "53729982",
    "okanagan-graveller": "55782704",
    "ukiah-mendo-gravel-epic": "45723133",
    "bend-dirt-fest": "54816842",
    "grusk": "47595782",
    "iron-cross": "31304897",
    "r3g3": "54058663",
    "santa-fe-century-gravelon": "56411897",
    "the-range": "55095902",
    "uwharrie-forest-gravel-grinder": "41743773",
    "falling-leaves-lahti": "53532865",
    "gravel-arteaga-mexico": "53501151",
    "usa-cycling-gravel-nationals": "56274042",
    "hazel-valley-rally": "41912593",
    "sasquatch-duro": "49314729",
    "dalby-grit": "55483772",
    "gravel-unravel-bon-jon-pass-out": "31776041",
    "mad-gravel": "53870735",
    "bwr-arizona": "54018255",
    "grinduro-california": "53291723",
    "the-rad": "51731077",
    "lost-and-found-gravel": "53119459",
    "atlas-mountain-race": "55605184",
    "nordsjorittet": "53719160",
    "race-around-rwanda": "53709689",
    "the-river": "56996252",
    "nanaimo-unpaved": "57411009",
    "wild-horse-gravel": "55845794",
}

# Rejected on purpose: a rider's deleted copy, a course that changes every
# year with the next one unpublished, or a route only a series account owns.
NO_ROUTE = (
    "tour-divide",
    "rule-of-three",
    "toppling-goliath-gravel-grinder",
    "leadville-100",  # 2026 route is private on RideWithGPS
)


def _race(slug):
    return json.loads((RACE_DATA / f"{slug}.json").read_text(encoding="utf-8"))["race"]


def test_verified_routes_are_on_the_profiles():
    for slug, route_id in VERIFIED_ROUTES.items():
        course = _race(slug)["course_description"]
        assert str(course["ridewithgps_id"]) == route_id, slug
        assert course.get("ridewithgps_name"), slug


def test_every_verified_route_is_cited():
    for slug, route_id in VERIFIED_ROUTES.items():
        urls = {c.get("url") for c in _race(slug)["citations"] if isinstance(c, dict)}
        assert f"https://ridewithgps.com/routes/{route_id}" in urls, slug


def test_every_verified_route_has_matching_geometry():
    for slug, route_id in VERIFIED_ROUTES.items():
        path = GEOMETRY_DIR / f"{slug}.json"
        assert path.exists(), slug
        geo = json.loads(path.read_text(encoding="utf-8"))
        assert str(geo["ridewithgps_id"]) == route_id, slug
        assert geo["path_d"].startswith("M"), slug


def test_rejected_routes_stay_off():
    for slug in NO_ROUTE:
        course = _race(slug)["course_description"]
        assert not course.get("ridewithgps_id"), slug
        assert "ridewithgps.com/routes/" not in (course.get("map_url") or ""), slug


def test_no_geometry_cache_describes_a_different_route():
    """A cache whose id differs from the profile's would show a stale course."""
    for path in sorted(GEOMETRY_DIR.glob("*.json")):
        race_file = RACE_DATA / path.name
        if not race_file.exists():
            continue
        route_id = _race(path.stem)["course_description"].get("ridewithgps_id")
        if not route_id:
            continue
        geo = json.loads(path.read_text(encoding="utf-8"))
        assert str(geo["ridewithgps_id"]) == str(route_id), path.stem
