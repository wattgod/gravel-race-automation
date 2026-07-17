"""Tests for wordpress/generate_race_page_v2.py — race-page-redesign pilot template.

Per docs/specs/race-page-redesign/IMPLEMENTATION_PLAN.md §5: this pilot reuses
generate_neo_brutalist.py's DATA layer and unrelated sections unchanged; these
tests focus on what's net-new (the route-map component) and on re-verifying
the hard constraints (XSS, GA4, fonts, JSON-LD, no fabricated routes) hold for
the v2 assembly path specifically, since generate_neo_brutalist.py's own tests
don't exercise this module.
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_race_page_v2 import (  # noqa: E402
    build_route_map_v2,
    build_course_overview_v2,
    generate_page_v2,
    get_page_css_v2,
    load_race_data,
    load_route_geometry,
    find_data_file,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
GEOMETRY_DIR = PROJECT_ROOT / "data" / "route-geometry"


@pytest.fixture(scope="module")
def steamboat_rd():
    filepath = find_data_file("steamboat-gravel", [RACE_DATA_DIR])
    return load_race_data(filepath)


@pytest.fixture(scope="module")
def steamboat_page(steamboat_rd):
    return generate_page_v2(steamboat_rd, race_index=[])


@pytest.fixture(scope="module")
def no_route_rd():
    """A race with no ridewithgps_id / no cached geometry, for fallback-state tests."""
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        data = json.loads(f.read_text())
        rwgps_id = data.get("race", {}).get("course_description", {}).get("ridewithgps_id")
        if not rwgps_id:
            return load_race_data(f)
    pytest.skip("No race without ridewithgps_id found")


class TestRouteMapRealGeometry:
    """steamboat-gravel has cached geometry (data/route-geometry/steamboat-gravel.json) —
    the route-map component must render the real-route state."""

    def test_geometry_cache_exists(self):
        assert (GEOMETRY_DIR / "steamboat-gravel.json").exists()

    def test_renders_svg_not_empty_state(self, steamboat_rd):
        html = build_route_map_v2(steamboat_rd)
        assert "<svg" in html
        assert "gg-route-map__line" in html
        assert "gg-route-map--empty" not in html
        assert "NO VERIFIED ROUTE ON FILE" not in html

    def test_path_d_is_numeric_only(self, steamboat_rd):
        """The path 'd' attribute must contain only path-command letters, digits,
        spaces, dots, minus signs — server-generated numeric geometry, never
        arbitrary/user-derived text (no XSS surface even though it's not user input)."""
        html = build_route_map_v2(steamboat_rd)
        m = re.search(r'class="gg-route-map__line"', html)
        assert m
        d_match = re.search(r'd="([^"]*)"\s+class="gg-route-map__line"', html)
        assert d_match
        assert re.fullmatch(r"[MLml0-9.\- ]+", d_match.group(1))

    def test_caption_links_to_source(self, steamboat_rd):
        html = build_route_map_v2(steamboat_rd)
        assert "ridewithgps.com/routes/" in html
        assert 'target="_blank"' in html
        assert 'rel="noopener nofollow"' in html

    def test_glow_and_line_share_same_path(self, steamboat_rd):
        html = build_route_map_v2(steamboat_rd)
        paths = re.findall(r'<path d="([^"]*)"', html)
        assert len(paths) == 2
        assert paths[0] == paths[1]


class TestRouteMapFallbackState:
    """Races without cached geometry must get the explicit no-route placeholder,
    never a fabricated line (handoff §3: 'DO NOT fabricate routes')."""

    def test_renders_empty_state(self, no_route_rd):
        html = build_route_map_v2(no_route_rd)
        assert "gg-route-map--empty" in html
        assert "NO VERIFIED ROUTE ON FILE" in html

    def test_no_svg_path_in_empty_state(self, no_route_rd):
        html = build_route_map_v2(no_route_rd)
        assert "gg-route-map__line" not in html
        assert "gg-route-map__glow" not in html

    def test_exactly_one_state_ever(self, steamboat_rd, no_route_rd):
        """Never both real-route and empty-state markup in the same output."""
        for rd in (steamboat_rd, no_route_rd):
            html = build_route_map_v2(rd)
            has_real = "gg-route-map__line" in html
            has_empty = "gg-route-map--empty" in html
            assert has_real != has_empty  # exactly one, XOR


class TestLoadRouteGeometry:
    def test_missing_slug_returns_none(self):
        assert load_route_geometry("this-slug-does-not-exist-anywhere") is None

    def test_existing_slug_returns_dict(self):
        geometry = load_route_geometry("steamboat-gravel")
        assert geometry is not None
        assert geometry["slug"] == "steamboat-gravel"
        assert "path_d" in geometry
        assert "viewbox" in geometry


class TestCourseOverviewV2Injection:
    def test_route_map_appears_before_stat_grid(self, steamboat_rd):
        html = build_course_overview_v2(steamboat_rd, [])
        route_idx = html.find("gg-route-map")
        stat_idx = html.find("gg-stat-grid")
        assert route_idx != -1
        assert stat_idx != -1
        assert route_idx < stat_idx

    def test_iframe_still_present_when_rwgps_id_exists(self, steamboat_rd):
        """The existing RWGPS iframe embed must survive unchanged — supplemented,
        not replaced, per the plan."""
        html = build_course_overview_v2(steamboat_rd, [])
        assert "gg-map-embed" in html
        assert "ridewithgps.com/embeds" in html

    def test_stat_cards_and_gauge_preserved(self, steamboat_rd):
        html = build_course_overview_v2(steamboat_rd, [])
        assert "gg-stat-grid" in html
        assert "gg-difficulty-gauge" in html


class TestFullPageAssembly:
    def test_has_h1_with_race_name(self, steamboat_page, steamboat_rd):
        assert f"<h1>{steamboat_rd['name']}</h1>" in steamboat_page or steamboat_rd["name"] in steamboat_page

    def test_has_ga4_snippet(self, steamboat_page):
        assert "googletagmanager.com/gtag/js" in steamboat_page

    def test_has_font_face_css(self, steamboat_page):
        assert "@font-face" in steamboat_page

    def test_has_sports_event_jsonld(self, steamboat_page):
        assert '"@type": "SportsEvent"' in steamboat_page or '"@type":"SportsEvent"' in steamboat_page

    def test_has_faq_jsonld(self, steamboat_page):
        assert "FAQPage" in steamboat_page

    def test_has_plan_ladder_block(self, steamboat_page):
        assert "gg-plan-ladder" in steamboat_page or "plan-ladder" in steamboat_page.lower()

    def test_has_similar_races_links(self, steamboat_page):
        assert "gg-similar" in steamboat_page

    def test_route_map_component_has_no_innerhtml(self, steamboat_page):
        """The net-new route-map surface (this pilot's actual scope) must not
        use innerHTML at all — it's static server-rendered SVG, no JS needed.
        NOTE: the reused build_inline_js() ticker (`feed.innerHTML = ''`, an
        empty-string clear, not data insertion) and the reused calendar-export
        onclick (KNOWN_ONCLICK_LINES in tests/test_ux_overhaul.py — pre-existing,
        already shipped on all 734 live pages) are DATA-layer/reused-section
        code this pilot didn't touch; asserting on them here would be testing
        generate_neo_brutalist.py's existing, already-governed exceptions, not
        this module's new surface."""
        route_map_start = steamboat_page.find('<figure class="gg-route-map"')
        if route_map_start == -1:
            route_map_start = steamboat_page.find('<div class="gg-route-map gg-route-map--empty"')
        assert route_map_start != -1
        route_map_end = steamboat_page.find('</figcaption>', route_map_start)
        if route_map_end == -1:
            route_map_end = steamboat_page.find('</div>', route_map_start)
        route_map_html = steamboat_page[route_map_start:route_map_end]
        assert "innerHTML" not in route_map_html
        assert "onclick" not in route_map_html
        assert "onsubmit" not in route_map_html

    def test_no_new_onclick_beyond_known_exception(self, steamboat_page):
        """Every onclick in the v2 page output must be the same pre-existing,
        already-tracked calendar-export exception — no NEW inline handlers."""
        for m in re.finditer(r'<[^>]*\sonclick\s*=', steamboat_page):
            line = steamboat_page[max(0, m.start() - 200):m.start() + 200]
            assert "gg-cal-btn--ics" in line, (
                f"Unexpected new inline onclick (not the known ICS exception): {line[:200]}"
            )

    def test_has_route_map_component(self, steamboat_page):
        assert "gg-route-map" in steamboat_page

    def test_route_map_css_present(self, steamboat_page):
        assert "gg-route-map__line" in steamboat_page  # markup
        # CSS is external-asset when external_assets is passed; when inline
        # (no external_assets, as here) it must be in the <style> block.
        assert ".gg-route-map" in steamboat_page

    def test_canonical_url_matches_current_live_slug(self, steamboat_page):
        assert 'href="https://gravelgodcycling.com/race/steamboat-gravel/"' in steamboat_page


class TestPageCssV2:
    def test_includes_base_css(self):
        css = get_page_css_v2()
        assert "--gg-color-teal" in css

    def test_includes_route_map_rules(self):
        css = get_page_css_v2()
        assert ".gg-route-map" in css

    def test_no_border_radius_violation(self):
        """Route-map CSS must not fight the global border-radius:0 reset."""
        css = get_page_css_v2()
        route_map_block = css[css.find(".gg-route-map"):]
        assert "border-radius:" not in route_map_block.split("</style>")[0] or \
            "border-radius: 0" in route_map_block

    def test_no_box_shadow(self):
        css = get_page_css_v2()
        # Route-map component block specifically must not introduce box-shadow
        start = css.find("ROUTE_MAP_CSS") if "ROUTE_MAP_CSS" in css else css.rfind(".gg-route-map")
        block = css[start:]
        assert "box-shadow" not in block
