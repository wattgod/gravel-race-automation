"""The finish-time planner's replay in a real browser.

Serves one generated race page and its planner assets from a temporary
folder over local HTTP (the model runs in a Web Worker, which needs http),
blocks every other host, and drives the page: a result, Replay, keyboard
scrubbing, reduced motion and analytics calls. Skipped without Playwright.
"""
from __future__ import annotations

import base64
import functools
import hashlib
import http.server
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))


def _has_playwright() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(not _has_playwright(), reason="playwright not installed")

SLUG = "unbound-200"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    import race_planner
    from generate_neo_brutalist import generate_page, load_race_data
    if race_planner.planner_status(SLUG) not in race_planner.SHOWN:
        pytest.skip(f"{SLUG} has no planner in the imported status")
    root = tmp_path_factory.mktemp("site")
    race_dir = root / "race"
    (race_dir / SLUG).mkdir(parents=True)
    (race_dir / SLUG / "index.html").write_text(generate_page(load_race_data(ROOT / "race-data" / f"{SLUG}.json")))
    race_planner.write_planner_assets(race_dir, [SLUG])
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}/race/{SLUG}/"
    server.shutdown()


def _result(page):
    q = lambda s: "#finish-time " + s  # noqa: E731
    page.fill(q("input[name=ftp]"), "250")
    page.fill(q("input[name=kg]"), "165")
    page.click(q(".gg-planner-go"))
    page.check(q('input[name=hours][value="7-10"]'))
    page.check(q('input[name=group][value="some"]'))
    page.click(q(".gg-planner-go"))
    page.wait_for_selector(q(".gg-planner-readout"), timeout=120_000)
    return q


def _events(page):
    """Event names the page's own gtag queued (it pushes to dataLayer)."""
    return page.evaluate(
        "() => (window.dataLayer || []).map(e => Array.prototype.slice.call(e))"
        ".filter(e => e[0] === 'event').map(e => e[1])")


def test_replay_scrub_and_analytics(site):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith("http://127.0.0.1") else route.abort())
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(site)
        q = _result(page)
        assert _events(page).count("planner_result_shown") == 1

        readout = page.locator(q(".gg-planner-readout"))
        assert readout.get_attribute("aria-live") == "off"
        finish = readout.text_content()
        assert "riding time" in finish and "race day" in finish

        play = page.locator(q(".gg-planner-ride .gg-planner-edit"))
        play.click()
        assert play.get_attribute("aria-pressed") == "true"
        page.wait_for_timeout(2500)
        assert readout.text_content() != finish, "Replay moves the cursor"
        play.click()  # Stop
        assert play.get_attribute("aria-pressed") == "false"

        prof = page.locator(q(".gg-planner-profile"))
        prof.focus()
        page.keyboard.press("Home")
        assert float(prof.get_attribute("aria-valuenow")) == 0
        page.keyboard.press("ArrowRight")
        one = float(prof.get_attribute("aria-valuenow"))
        assert 1.5 < one < 1.7, "one mile per arrow press in miles"
        page.keyboard.press("End")
        assert float(prof.get_attribute("aria-valuenow")) == float(prof.get_attribute("aria-valuemax"))
        assert prof.get_attribute("aria-valuetext") == readout.text_content()

        # Other hosts are blocked here, so the map library cannot load: the
        # card says so and draws no map (no outline stand-in).
        note = page.locator(q(".gg-planner-mapnote"))
        note.wait_for(state="visible", timeout=10_000)
        assert "The map is not shown: the map library did not load." in note.text_content()
        assert page.locator(q(".gg-planner-basemap")).is_hidden()
        assert page.locator(q(".gg-planner-ride svg path.gg-planner-route")).count() == 0

        # Replay and scrubbing send no analytics: apart from the page's own
        # section-view events (fired when focus scrolls a section into view),
        # the only event is the one result.
        assert [e for e in _events(page) if e != "race_section_view"] == ["planner_result_shown"]
        assert errors == []
        browser.close()


def test_reduced_motion_replay_jumps_to_the_finish(site):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, reduced_motion="reduce")
        ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith("http://127.0.0.1") else route.abort())
        page = ctx.new_page()
        page.goto(site)
        q = _result(page)
        prof = page.locator(q(".gg-planner-profile"))
        prof.focus()
        page.keyboard.press("Home")
        page.locator(q(".gg-planner-ride .gg-planner-edit")).click()
        assert page.locator(q(".gg-planner-ride .gg-planner-edit")).get_attribute("aria-pressed") == "false"
        assert float(prof.get_attribute("aria-valuenow")) == float(prof.get_attribute("aria-valuemax"))
        browser.close()


# ---------- the map's loading rules, with a local stand-in for Leaflet ----------
# CI cannot reach the real library, so these serve a small script that records
# how the planner uses it. Each case gets its own SRI hash for that script, so
# the planner's integrity check still runs.
STUB_JS = """
window.__leaflet = { maps: [], opts: null, tileHandlers: {} };
(function () {
  function Ev() { this._h = {}; }
  Ev.prototype.on = function (n, f) { var self = this; n.split(" ").forEach(function (k) { (self._h[k] = self._h[k] || []).push(f); }); return this; };
  Ev.prototype.fire = function (n) { (this._h[n] || []).forEach(function (f) { f({}); }); };
  function Map(box, opts) { Ev.call(this); window.__leaflet.maps.push(this); window.__leaflet.opts = opts; this.box = box;
    this.attributionControl = { setPrefix: function () {} }; }
  Map.prototype = Object.create(Ev.prototype);
  Map.prototype.getSize = function () { return { x: this.box.clientWidth, y: this.box.clientHeight }; };
  Map.prototype.fitBounds = function () { return this; };
  Map.prototype.invalidateSize = function () { return this; };
  Map.prototype.panBy = function (o, opt) { window.__leaflet.lastPan = opt || null; return this; };
  Map.prototype.latLngToContainerPoint = function () { return { x: 0, y: 0 }; };
  Map.prototype.remove = function () { this.removed = true; };
  function Layer() { Ev.call(this); }
  Layer.prototype = Object.create(Ev.prototype);
  Layer.prototype.addTo = function () { return this; };
  Layer.prototype.setLatLng = function () { return this; };
  Layer.prototype.getBounds = function () { return {}; };
  window.L = {
    map: function (b, o) { return new Map(b, o); },
    tileLayer: function () { var t = new Layer(); window.__leaflet.tiles = t; return t; },
    TileLayer: { extend: function () { return function () { var t = new Layer(); window.__leaflet.tiles = t; return t; }; }, prototype: {} },
    polyline: function () { return new Layer(); },
    circleMarker: function () { return new Layer(); },
    extend: function (dest) { for (var i = 1; i < arguments.length; i++) { var src = arguments[i]; for (var k in src) dest[k] = src[k]; } return dest; },
    Browser: { mobile: false }
  };
})();
"""


def _sri(data: bytes) -> str:
    return "sha256-" + base64.b64encode(hashlib.sha256(data).digest()).decode()


@pytest.fixture()
def stub_site(tmp_path, monkeypatch):
    """A planner page whose map config points at local files: the stand-in
    script, a stylesheet, and a missing path for whichever one a test blocks."""
    import race_planner
    from generate_neo_brutalist import generate_page, load_race_data
    if race_planner.planner_status(SLUG) not in race_planner.SHOWN:
        pytest.skip(f"{SLUG} has no planner in the imported status")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(tmp_path))
    handler.log_message = lambda *a, **k: None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    (tmp_path / "stub").mkdir()
    js, css = STUB_JS.encode(), b".leaflet-container { overflow: hidden; }"
    (tmp_path / "stub" / "leaflet.js").write_bytes(js)
    (tmp_path / "stub" / "leaflet.css").write_bytes(css)

    def build(block=None):
        cfg = dict(race_planner.PLANNER_MAP)
        cfg.update(js=f"{base}/stub/{'missing' if block == 'js' else 'leaflet'}.js", js_sri=_sri(js),
                   css=f"{base}/stub/{'missing' if block == 'css' else 'leaflet'}.css", css_sri=_sri(css),
                   tiles=f"{base}/tiles/{{z}}/{{x}}/{{y}}.png")
        monkeypatch.setattr(race_planner, "PLANNER_MAP", cfg)
        race_dir = tmp_path / "race"
        (race_dir / SLUG).mkdir(parents=True, exist_ok=True)
        (race_dir / SLUG / "index.html").write_text(generate_page(load_race_data(ROOT / "race-data" / f"{SLUG}.json")))
        race_planner.write_planner_assets(race_dir, [SLUG])
        return f"{base}/race/{SLUG}/"
    yield build
    server.shutdown()


def _open(pw, url, reduced=False):
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, reduced_motion="reduce" if reduced else "no-preference")
    ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith("http://127.0.0.1") else route.abort())
    page = ctx.new_page()
    page.goto(url)
    return browser, page


@pytest.mark.parametrize("block", ["css", "js"])
def test_no_map_unless_both_the_script_and_the_stylesheet_load(stub_site, block):
    from playwright.sync_api import sync_playwright
    url = stub_site(block)
    with sync_playwright() as pw:
        browser, page = _open(pw, url)
        q = _result(page)
        note = page.locator(q(".gg-planner-mapnote"))
        note.wait_for(state="visible", timeout=10_000)
        assert "The map is not shown: the map library did not load." in note.text_content()
        assert page.locator(q(".gg-planner-basemap")).is_hidden()
        assert page.evaluate("() => window.__leaflet ? window.__leaflet.maps.length : 0") == 0, "no map is created"
        browser.close()


def test_a_tile_failing_in_the_first_view_removes_the_map(stub_site):
    from playwright.sync_api import sync_playwright
    url = stub_site()
    with sync_playwright() as pw:
        browser, page = _open(pw, url)
        q = _result(page)
        page.wait_for_function("() => window.__leaflet && window.__leaflet.tiles")
        assert page.locator(q(".gg-planner-basemap")).is_visible()
        page.evaluate("() => { window.__leaflet.tiles.fire('tileload'); window.__leaflet.tiles.fire('tileerror'); }")
        note = page.locator(q(".gg-planner-mapnote"))
        assert note.is_visible() and "some of the map tiles did not load" in note.text_content()
        assert page.locator(q(".gg-planner-basemap")).is_hidden()
        assert page.evaluate("() => window.__leaflet.maps[0].removed") is True
        browser.close()


def test_a_tile_failing_after_the_first_view_keeps_the_map(stub_site):
    from playwright.sync_api import sync_playwright
    url = stub_site()
    with sync_playwright() as pw:
        browser, page = _open(pw, url)
        q = _result(page)
        page.wait_for_function("() => window.__leaflet && window.__leaflet.tiles")
        page.evaluate("() => { window.__leaflet.tiles.fire('load'); window.__leaflet.tiles.fire('tileerror'); }")
        assert page.locator(q(".gg-planner-basemap")).is_visible()
        assert page.locator(q(".gg-planner-mapnote")).is_hidden()
        browser.close()


@pytest.mark.parametrize("reduced", [True, False])
def test_map_animations_follow_reduced_motion(stub_site, reduced):
    from playwright.sync_api import sync_playwright
    url = stub_site()
    with sync_playwright() as pw:
        browser, page = _open(pw, url, reduced=reduced)
        _result(page)
        page.wait_for_function("() => window.__leaflet && window.__leaflet.opts")
        opts = page.evaluate("() => window.__leaflet.opts")
        for k in ("zoomAnimation", "fadeAnimation", "markerZoomAnimation", "inertia"):
            assert opts[k] is (not reduced), k
        page.evaluate("() => window.__leaflet.maps[0].panBy([10, 0])")
        last = page.evaluate("() => window.__leaflet.lastPan")
        if reduced:
            assert last and last.get("animate") is False
        browser.close()

