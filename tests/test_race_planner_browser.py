"""The finish-time planner's replay in a real browser.

Serves one generated race page and its planner assets from a temporary
folder over local HTTP (the model runs in a Web Worker, which needs http),
blocks every other host, and drives the page: a result, Replay, keyboard
scrubbing, reduced motion and analytics calls. Skipped without Playwright.
"""
from __future__ import annotations

import functools
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
