"""Official course routes that live somewhere other than a public RideWithGPS id.

Some organizers publish their course only as a Strava route, a GPX/KMZ file,
or a Komoot/Garmin/OpenRunner/Plotaroute/Outdooractive page (issue #670).
Those go in ``race.course_description.official_route``::

    "official_route": {
        "provider": "strava",
        "url": "https://www.strava.com/routes/3412794902184532350",
        "provenance_url": "https://www.barry-roubaix.com/courses/",
        "name": "2026 Barry-Roubaix 100 mile race day route",
        "edition": "2026",
        "verified_at": "2026-11-17"
    }

``provenance_url`` is the organizer page that links ``url``. Only routes the
organizer links or owns belong here: never a rider upload, never a guessed
route. The route URL must also appear in the profile's citations.

Organizer routes that are unlisted on RideWithGPS keep using
``ridewithgps_id`` and add ``ridewithgps_privacy_code`` — the code the
organizer's own public embed carries.
"""

from __future__ import annotations

import html as _html
import json as _json
import re
from pathlib import Path as _Path
from urllib.parse import quote, urlparse

PROVIDER_LABELS = {
    "strava": "Strava",
    "gpx": "GPX file",
    "kmz": "KMZ file",
    "komoot": "Komoot",
    "garmin": "Garmin Connect",
    "openrunner": "OpenRunner",
    "plotaroute": "Plotaroute",
    "outdooractive": "Outdooractive",
    "racedaymap": "Raceday Map",
    "other": "the organizer's site",
}

# Providers whose geometry scripts/fetch_route_geometry.py can build from
# the organizer's own file or route data.
GEOMETRY_PROVIDERS = {"strava", "gpx", "kmz", "komoot"}

REQUIRED_FIELDS = ("provider", "url", "provenance_url")

_STRAVA_ROUTE = re.compile(r"^https://www\.strava\.com/routes/(\d+)/?$")
_KOMOOT_TOUR = re.compile(r"^https://www\.komoot\.com/(?:[a-z-]+/)?tour/(\d+)")
_PRIVACY_CODE = re.compile(r"^[A-Za-z0-9]{4,64}$")


def _is_web_url(value) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def get_official_route(course: dict | None) -> dict | None:
    """The profile's official_route when it is complete, else None.

    Incomplete entries render nothing: a route without the organizer page
    that links it isn't verified, and showing it anyway is a fallback.
    """
    route = (course or {}).get("official_route")
    if not isinstance(route, dict):
        return None
    if route.get("provider") not in PROVIDER_LABELS:
        return None
    if not all(_is_web_url(route.get(k)) for k in ("url", "provenance_url")):
        return None
    return route


def strava_route_id(url: str) -> str | None:
    m = _STRAVA_ROUTE.match((url or "").strip())
    return m.group(1) if m else None


def komoot_tour_id(url: str) -> str | None:
    m = _KOMOOT_TOUR.match((url or "").strip())
    return m.group(1) if m else None


def strava_embed_url(route: dict) -> str | None:
    """Strava's own route embed for an organizer's Strava route."""
    if route.get("provider") != "strava":
        return None
    rid = strava_route_id(route.get("url", ""))
    if not rid:
        return None
    return f"https://strava-embeds.com/route/{rid}?style=standard&fullWidth=true"


def valid_privacy_code(code) -> str | None:
    """A RideWithGPS privacy code, or None when absent or malformed."""
    if code is None:
        return None
    code = str(code).strip()
    return code if _PRIVACY_CODE.match(code) else None


def rwgps_route_url(route_id, privacy_code=None) -> str:
    url = f"https://ridewithgps.com/routes/{quote(str(route_id), safe='')}"
    code = valid_privacy_code(privacy_code)
    return f"{url}?privacy_code={code}" if code else url


def rwgps_embed_url(route_id, title: str = "", privacy_code=None) -> str:
    url = (
        "https://ridewithgps.com/embeds?type=route"
        f"&id={quote(str(route_id), safe='')}"
        "&sampleGraph=true"
        f"&title={quote(title or '', safe='')}"
    )
    code = valid_privacy_code(privacy_code)
    return f"{url}&privacyCode={code}" if code else url


def citation_number(citations, url: str) -> int | None:
    """1-based position of ``url`` in the page's numbered source list."""
    for index, citation in enumerate(citations or [], start=1):
        if isinstance(citation, dict) and citation.get("url") == url:
            return index
    return None


def geometry_inputs(route: dict) -> dict:
    """Everything that decides which line a cached geometry draws."""
    return {key: route.get(key) for key in ("url", "download_url", "exclude_placemarks")}


def provider_label(route: dict) -> str:
    return PROVIDER_LABELS.get(route.get("provider"), PROVIDER_LABELS["other"])


def provenance_host(route: dict) -> str:
    host = urlparse(route.get("provenance_url", "")).netloc.lower()
    return host[4:] if host.startswith("www.") else host


# ── Cached geometry (built by scripts/fetch_route_geometry.py) ───────────

GEOMETRY_DIR = _Path(__file__).resolve().parent.parent / "data" / "route-geometry"


def load_official_geometry(slug: str, route: dict | None,
                           geometry_dir: _Path | None = None) -> dict | None:
    """Cached geometry for this exact official route, else None.

    A cache built from another URL (an older edition's file, say) is ignored:
    the profile's route URL is the stale-map gate, as ridewithgps_id is for
    RideWithGPS geometry.
    """
    if not route:
        return None
    path = (geometry_dir or GEOMETRY_DIR) / f"{slug}.json"
    if not path.exists():
        return None
    try:
        geometry = _json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if geometry.get("official_route_url") != route.get("url"):
        return None
    if geometry.get("geometry_inputs") != geometry_inputs(route):
        return None
    if not (geometry.get("path_d") and geometry.get("viewbox")):
        return None
    return geometry


def route_svg_html(geometry: dict, race_name: str, provider: str) -> str:
    """Inline SVG of the organizer's route line. No caption; callers link it."""
    e = lambda s: _html.escape(str(s), quote=True)  # noqa: E731
    vb = str(geometry["viewbox"]).split()
    aspect = f"{vb[2]}/{vb[3]}" if len(vb) == 4 else "4/3"
    return (
        f'<figure class="gg-official-route-map" style="aspect-ratio:{e(aspect)}">'
        f'<svg viewBox="{e(geometry["viewbox"])}" class="gg-official-route-map__svg" role="img" '
        f'aria-label="Official course route for {e(race_name)}, from the organizer\'s {e(provider)}" '
        f'preserveAspectRatio="xMidYMid meet">'
        f'<path d="{e(geometry["path_d"])}" class="gg-official-route-map__glow"/>'
        f'<path d="{e(geometry["path_d"])}" class="gg-official-route-map__line"/>'
        f'</svg></figure>'
    )
