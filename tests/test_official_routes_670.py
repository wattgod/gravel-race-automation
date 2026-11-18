"""Official course routes published off RideWithGPS, and unlisted RWGPS
organizer routes (issue #670).

The page shows a route only when the profile names the organizer page that
links it. A Strava route gets Strava's own embed; GPX/KMZ/Komoot routes get
an SVG drawn from the organizer's file; every official route gets a link.
"""

import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import official_route  # noqa: E402
import fetch_route_geometry as frg  # noqa: E402
import generate_neo_brutalist as v1  # noqa: E402
import generate_race_page_v2 as v2  # noqa: E402

STRAVA = {
    "provider": "strava",
    "url": "https://www.strava.com/routes/3412794902184532350",
    "provenance_url": "https://www.example-race.com/course/",
    "name": "2026 Example 100",
}
GPX = {
    "provider": "gpx",
    "url": "https://www.example-race.com/files/course.gpx",
    "provenance_url": "https://www.example-race.com/course/",
    "name": "Example Long Course",
}


CITATIONS = [
    {"url": "https://www.example-race.com/", "category": "official"},
    {"url": STRAVA["url"], "category": "route"},
    {"url": GPX["url"], "category": "route"},
    {"url": "https://www.example-race.com/course/", "category": "official"},
]


def _geometry(route: dict, **extra) -> str:
    return json.dumps({
        "official_route_url": route["url"],
        "geometry_inputs": official_route.geometry_inputs(route),
        "viewbox": "0 0 800 600",
        "path_d": "M10 10L20 20",
        **extra,
    })


def _rd(course_extra: dict, slug: str = "example-race", citations=None) -> dict:
    return {
        "slug": slug,
        "name": "Example Race",
        "citations": CITATIONS if citations is None else citations,
        "course": {
            "ridewithgps_id": None,
            "ridewithgps_name": "",
            "map_url": "",
            **course_extra,
        },
    }


# ── Profile field validation ────────────────────────────────────────────

class TestGetOfficialRoute:
    def test_complete_route_is_returned(self):
        assert official_route.get_official_route({"official_route": STRAVA}) is STRAVA

    @pytest.mark.parametrize("missing", ["provider", "url", "provenance_url"])
    def test_route_missing_a_required_field_is_dropped(self, missing):
        route = {k: v for k, v in STRAVA.items() if k != missing}
        assert official_route.get_official_route({"official_route": route}) is None

    def test_unknown_provider_is_dropped(self):
        route = {**STRAVA, "provider": "rider-upload"}
        assert official_route.get_official_route({"official_route": route}) is None

    def test_non_web_url_is_dropped(self):
        route = {**GPX, "url": "javascript:alert(1)"}
        assert official_route.get_official_route({"official_route": route}) is None

    def test_no_course_is_none(self):
        assert official_route.get_official_route(None) is None


class TestPrivacyCode:
    def test_embed_carries_privacy_code(self):
        url = official_route.rwgps_embed_url("54576515", "Unbound 100", "AbC123xyz")
        assert "id=54576515" in url and url.endswith("&privacyCode=AbC123xyz")

    def test_route_link_carries_privacy_code(self):
        assert (official_route.rwgps_route_url(54576515, "AbC123xyz")
                == "https://ridewithgps.com/routes/54576515?privacy_code=AbC123xyz")

    @pytest.mark.parametrize("bad", ["", None, "a&b=1", "x" * 80, "<script>"])
    def test_malformed_code_is_not_used(self, bad):
        assert "privacy" not in official_route.rwgps_embed_url("1", "", bad).lower()
        assert official_route.rwgps_route_url("1", bad) == "https://ridewithgps.com/routes/1"


# ── Race page rendering ─────────────────────────────────────────────────

class TestRouteEmbed:
    def test_rwgps_embed_unchanged_without_code(self):
        html = v1.build_route_embed(_rd({"ridewithgps_id": "123", "ridewithgps_name": "A B"}))
        assert "ridewithgps.com/embeds?type=route&amp;id=123&amp;sampleGraph=true&amp;title=A%20B" in html
        assert "privacyCode" not in html

    def test_rwgps_embed_with_privacy_code(self):
        html = v1.build_route_embed(_rd({"ridewithgps_id": "54576515",
                                         "ridewithgps_privacy_code": "AbC123xyz"}))
        assert "&amp;privacyCode=AbC123xyz" in html

    def test_rwgps_wins_over_official_route(self):
        html = v1.build_route_embed(_rd({"ridewithgps_id": "123", "official_route": STRAVA}))
        assert "ridewithgps.com/embeds" in html
        assert "strava" not in html

    def test_strava_route_gets_strava_embed_and_link(self):
        html = v1.build_route_embed(_rd({"official_route": STRAVA}))
        assert 'src="https://strava-embeds.com/route/3412794902184532350?' in html
        assert 'href="https://www.strava.com/routes/3412794902184532350"' in html
        assert 'href="https://www.example-race.com/course/"' in html
        assert "2026 Example 100 (Strava) &#x2197;</a>[2]" in html
        assert "example-race.com</a>[4]" in html

    def test_uncited_route_is_not_shown(self):
        cites = [c for c in CITATIONS if c["url"] != STRAVA["url"]]
        assert v1.build_route_embed(_rd({"official_route": STRAVA}, citations=cites)) == ""
        cites = [c for c in CITATIONS if c["url"] != STRAVA["provenance_url"]]
        assert v1.build_route_embed(_rd({"official_route": STRAVA}, citations=cites)) == ""

    def test_gpx_route_with_geometry_draws_svg(self, tmp_path, monkeypatch):
        (tmp_path / "example-race.json").write_text(_geometry(GPX))
        monkeypatch.setattr(official_route, "GEOMETRY_DIR", tmp_path)
        html = v1.build_route_embed(_rd({"official_route": GPX}))
        assert '<path d="M10 10L20 20" class="gg-official-route-map__line"/>' in html
        assert "Example Long Course (GPX file)" in html
        assert "<iframe" not in html

    def test_geometry_built_with_other_inputs_is_ignored(self, tmp_path, monkeypatch):
        (tmp_path / "example-race.json").write_text(_geometry(GPX))
        monkeypatch.setattr(official_route, "GEOMETRY_DIR", tmp_path)
        route = {**GPX, "exclude_placemarks": r"\bOption\b"}
        assert "<svg" not in v1.build_route_embed(_rd({"official_route": route}))

    def test_geometry_for_another_url_is_ignored(self, tmp_path, monkeypatch):
        (tmp_path / "example-race.json").write_text(json.dumps({
            "official_route_url": "https://www.example-race.com/files/2024.gpx",
            "viewbox": "0 0 800 600",
            "path_d": "M10 10L20 20",
        }))
        monkeypatch.setattr(official_route, "GEOMETRY_DIR", tmp_path)
        html = v1.build_route_embed(_rd({"official_route": GPX}))
        assert "<svg" not in html
        # The organizer's file is still linked.
        assert 'href="https://www.example-race.com/files/course.gpx"' in html

    def test_rwgps_geometry_is_not_drawn_as_official_route(self, tmp_path, monkeypatch):
        (tmp_path / "example-race.json").write_text(json.dumps({
            "ridewithgps_id": "999", "viewbox": "0 0 800 600", "path_d": "M1 1L2 2"}))
        monkeypatch.setattr(official_route, "GEOMETRY_DIR", tmp_path)
        assert "<svg" not in v1.build_route_embed(_rd({"official_route": GPX}))

    def test_nothing_without_a_route(self):
        assert v1.build_route_embed(_rd({})) == ""

    def test_text_is_escaped(self):
        route = {**GPX, "name": '<img src=x onerror=alert(1)>'}
        html = v1.build_route_embed(_rd({"official_route": route}))
        assert "<img" not in html and "&lt;img" in html

    def test_normalize_drops_unverified_route(self):
        data = {"race": {"name": "X", "slug": "x", "course_description": {
            "official_route": {"provider": "strava", "url": STRAVA["url"]}}}}
        rd = v1.normalize_race_data(data)
        assert rd["course"]["official_route"] is None

    def test_v2_has_no_placeholder_beside_an_official_route(self):
        assert v2.build_route_map_v2(_rd({"official_route": STRAVA})) == ""
        assert "NO VERIFIED ROUTE" in v2.build_route_map_v2(_rd({}))


# ── Geometry from organizer files ───────────────────────────────────────

GPX_DOC = b"""<?xml version="1.0"?>
<gpx xmlns="http://www.topografix.com/GPX/1/1" version="1.1">
 <trk><trkseg>
  <trkpt lat="45.0" lon="7.0"/><trkpt lat="45.01" lon="7.0"/>
 </trkseg><trkseg>
  <trkpt lat="45.1" lon="7.1"/><trkpt lat="45.11" lon="7.1"/>
 </trkseg></trk>
</gpx>"""

KML_DOC = b"""<?xml version="1.0"?>
<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>
 <LineString><coordinates>7.0,45.0,0 7.0,45.01,0</coordinates></LineString>
</Placemark></Document></kml>"""


class TestGeometryParsers:
    def test_gpx_track_segments(self):
        pts = frg.points_from_gpx(GPX_DOC)
        assert [(p["x"], p["y"], p["seg"]) for p in pts] == [
            (7.0, 45.0, 0), (7.0, 45.01, 0), (7.1, 45.1, 1), (7.1, 45.11, 1)]

    def test_gpx_route_points_when_no_track(self):
        doc = b'<gpx><rte><rtept lat="1" lon="2"/><rtept lat="3" lon="4"/></rte></gpx>'
        assert [(p["x"], p["y"]) for p in frg.points_from_gpx(doc)] == [(2.0, 1.0), (4.0, 3.0)]

    def test_kml_linestring(self):
        assert [(p["x"], p["y"]) for p in frg.points_from_kml(KML_DOC)] == [(7.0, 45.0), (7.0, 45.01)]

    def test_kmz_archive(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("doc.kml", KML_DOC)
        assert len(frg.points_from_archive(buf.getvalue())) == 2

    def test_archive_with_two_routes_is_refused(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("a.gpx", GPX_DOC)
            zf.writestr("b.gpx", GPX_DOC)
        assert frg.points_from_archive(buf.getvalue()) == []

    def test_dtd_is_refused(self):
        with pytest.raises(ValueError):
            frg.points_from_gpx(b'<!DOCTYPE gpx [<!ENTITY a "b">]><gpx/>')

    def test_utf16_dtd_is_refused(self):
        doc = '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE gpx [<!ENTITY a "b">]><gpx/>'
        with pytest.raises(ValueError):
            frg.points_from_gpx(doc.encode("utf-16"))

    def test_truncated_polyline_is_an_error_not_a_crash(self, tmp_path, monkeypatch):
        with pytest.raises(ValueError):
            frg.decode_polyline("_p~iF~ps|U_ulL")
        monkeypatch.setattr(frg, "GEOMETRY_DIR", tmp_path)
        monkeypatch.setattr(frg, "official_route_points",
                            lambda route: frg.decode_polyline("_p~iF~ps|U_ulL"))
        assert frg.process_official_route("x", STRAVA, dry_run=True, force=True) == "no_geometry"

    def test_cache_is_refetched_when_inputs_change(self, tmp_path, monkeypatch):
        monkeypatch.setattr(frg, "GEOMETRY_DIR", tmp_path)
        (tmp_path / "x.json").write_text(_geometry(GPX))
        assert frg.process_official_route("x", GPX, dry_run=True, force=False) == "cached"
        calls = []
        monkeypatch.setattr(frg, "official_route_points", lambda route: calls.append(route) or None)
        route = {**GPX, "download_url": "https://www.example-race.com/files/course-v2.gpx"}
        assert frg.process_official_route("x", route, dry_run=True, force=False) == "fetch_failed"
        assert calls == [route]

    def test_google_polyline(self):
        # Google's documented example polyline.
        pts = frg.decode_polyline("_p~iF~ps|U_ulLnnqC_mqNvxq`@")
        assert [(round(p["y"], 3), round(p["x"], 3)) for p in pts] == [
            (38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]

    def test_strava_embed_route_data(self):
        page = ('<script id="__ROUTE_DATA__" type="application/json">'
                '{"legs":[{"paths":[{"polyline":{"encoding":"Google",'
                '"data":"_p~iF~ps|U_ulLnnqC_mqNvxq`@"}}]}]}</script>')
        assert len(frg.points_from_strava_embed(page)) == 3

    def test_segments_do_not_join_and_distance_skips_gaps(self):
        pts = frg.points_from_gpx(GPX_DOC)
        record = frg.build_official_record("x", GPX, pts)
        assert record["path_d"].count("M") == 2
        assert record["official_route_url"] == GPX["url"]
        assert record["provenance_url"] == GPX["provenance_url"]
        # Two ~1.1 km segments, not the ~14 km jump between them.
        assert record["distance_mi_from_geometry"] < 2

    def test_rwgps_path_is_one_segment(self):
        proj = frg.project_to_viewbox([{"x": 0, "y": 0}, {"x": 1, "y": 1}, {"x": 2, "y": 0}])
        assert proj["path_d"].count("M") == 1 and proj["path_d"].count("L") == 2

    def test_unsupported_provider_is_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(frg, "GEOMETRY_DIR", tmp_path)
        route = {**STRAVA, "provider": "garmin"}
        assert frg.process_official_route("x", route, dry_run=True, force=False) == "no_id"


# ── Profiles verified against organizer pages, 17 Nov 2026 ──────────────

RACE_DATA = ROOT / "race-data"
GEOMETRY_DIR = ROOT / "data" / "route-geometry"

OFFICIAL_ROUTES = {
    "tour-divide": "gpx",
    "birkebeinerrittet-road": "racedaymap",
    "boulder-roubaix": "gpx",
    "grand-tour-3-cime-lavaredo": "gpx",
    "jackson-forest-grasshopper": "strava",
    "khomas100": "gpx",
    "pyrenees-catalanes-gravel-tour": "strava",
    "tartu-rattamaraton-gravel": "plotaroute",
    "tour-aotearoa": "kmz",
    "barry-roubaix": "strava",
    "coast-to-coast": "strava",
    "devils-cardigan": "gpx",
    "lone-wolf-gravel": "strava",
    "red-granite-grinder": "komoot",
    "the-equalizer": "strava",
    "wyscig-niepolomice": "gpx",
    "hart-hills": "gpx",
    "tour-de-gap": "strava",
    "wild-gravel": "strava",
    "gravel-of-marathon": "gpx",
}

# Rejected on review: a deleted file, a past edition at a venue that has
# moved, a copy of an older course, a one-off championship, a cancelled
# edition, a final edition, a 2027 course not yet out, a single lap of a
# lap race, and a file 15% short of its own label.
NO_OFFICIAL_ROUTE = (
    "seven", "uci-gravel-worlds", "vuelta-altas-cumbres", "houffa-gravel",
    "la-dromoise-gravel", "ghost-of-the-gravel", "unbound-100",
    "rad-am-ring-gravel", "safari-gravel-race",
)


def _profile(slug):
    return json.loads((RACE_DATA / f"{slug}.json").read_text(encoding="utf-8"))["race"]


class TestVerifiedProfiles:
    def test_official_routes_are_complete_and_cited(self):
        for slug, provider in OFFICIAL_ROUTES.items():
            race = _profile(slug)
            route = official_route.get_official_route(race["course_description"])
            assert route and route["provider"] == provider, slug
            assert not race["course_description"].get("ridewithgps_id"), slug
            cited = {c.get("url") for c in race["citations"] if isinstance(c, dict)}
            assert route["url"] in cited and route["provenance_url"] in cited, slug

    def test_drawable_routes_have_matching_geometry(self):
        for slug, provider in OFFICIAL_ROUTES.items():
            if provider not in official_route.GEOMETRY_PROVIDERS or provider == "strava":
                continue
            route = _profile(slug)["course_description"]["official_route"]
            assert official_route.load_official_geometry(slug, route), slug

    def test_drawn_route_matches_profile_distance(self):
        # The organizer's file and the profile must describe the same course.
        for slug, provider in OFFICIAL_ROUTES.items():
            if provider not in official_route.GEOMETRY_PROVIDERS or provider == "strava":
                continue
            race = _profile(slug)
            geometry = official_route.load_official_geometry(
                slug, race["course_description"]["official_route"])
            drawn = geometry["distance_mi_from_geometry"]
            stated = float(race["vitals"]["distance_mi"])
            assert abs(stated - drawn) / drawn <= 0.10, (slug, stated, drawn)

    def test_rejected_routes_stay_off(self):
        for slug in NO_OFFICIAL_ROUTE:
            course = _profile(slug).get("course_description") or {}
            assert not course.get("official_route"), slug
            assert not course.get("ridewithgps_privacy_code"), slug

    def test_edition_zero_uses_the_organizers_unlisted_route(self):
        race = _profile("edition-zero")
        course = race["course_description"]
        assert str(course["ridewithgps_id"]) == "53423216"
        code = official_route.valid_privacy_code(course["ridewithgps_privacy_code"])
        assert code
        cited = {c.get("url") for c in race["citations"] if isinstance(c, dict)}
        assert official_route.rwgps_route_url("53423216", code) in cited
        geometry = json.loads((GEOMETRY_DIR / "edition-zero.json").read_text())
        assert geometry["ridewithgps_id"] == "53423216"

    def test_tour_aotearoa_draws_the_main_route_only(self):
        geometry = json.loads((GEOMETRY_DIR / "tour-aotearoa.json").read_text())
        # Kennett Bros give 3,001 km with boat legs; the optional bypasses
        # in the same file would add ~670 km.
        assert 1800 < geometry["distance_mi_from_geometry"] < 1900


class TestKmlExclude:
    def test_option_placemarks_are_skipped(self):
        doc = b"""<kml><Document>
          <Placemark><name>1.1 Main</name><LineString><coordinates>1,1 2,2</coordinates></LineString></Placemark>
          <Placemark><name>1.1A Option bypass</name><LineString><coordinates>5,5 6,6</coordinates></LineString></Placemark>
        </Document></kml>"""
        assert len(frg.points_from_kml(doc)) == 4
        assert [(p["x"], p["y"]) for p in frg.points_from_kml(doc, r"\bOption\b")] == [(1.0, 1.0), (2.0, 2.0)]


def test_route_names_are_finished_labels_not_file_notes():
    """The name is printed on the page: no file names or research notes."""
    for slug in OFFICIAL_ROUTES:
        name = _profile(slug)["course_description"]["official_route"]["name"]
        lowered = name.lower()
        assert not any(bad in lowered for bad in (
            ".gpx", ".kmz", ".zip", "_", "internal name", "master", "copy", "v1", "v3)"
        )), (slug, name)
