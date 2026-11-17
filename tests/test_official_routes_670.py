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


def _rd(course_extra: dict, slug: str = "example-race") -> dict:
    return {
        "slug": slug,
        "name": "Example Race",
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
        assert "2026 Example 100 (Strava)" in html
        assert "example-race.com" in html

    def test_gpx_route_with_geometry_draws_svg(self, tmp_path, monkeypatch):
        (tmp_path / "example-race.json").write_text(json.dumps({
            "official_route_url": GPX["url"],
            "viewbox": "0 0 800 600",
            "path_d": "M10 10L20 20",
        }))
        monkeypatch.setattr(official_route, "GEOMETRY_DIR", tmp_path)
        html = v1.build_route_embed(_rd({"official_route": GPX}))
        assert '<path d="M10 10L20 20" class="gg-official-route-map__line"/>' in html
        assert "Example Long Course (GPX file)" in html
        assert "<iframe" not in html

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
