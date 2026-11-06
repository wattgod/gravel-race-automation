"""Publish Site builds and pushes every page its .htaccess redirects to.

The workflow pushes .htaccess (--sync-redirects), which sends /race/calendar/
to /race/calendar/{season}/ and past seasons' power rankings to this
season's page. Without the generators below, the September rollover
points those redirects at pages that were never built.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = (ROOT / ".github" / "workflows" / "publish-site.yml").read_text(encoding="utf-8")


def test_builds_season_pages_and_series_hubs():
    for gen in ("generate_calendar.py", "generate_power_rankings.py",
                "generate_series_hubs.py", "generate_homepage.py"):
        assert f"python3 wordpress/{gen}" in WF


def test_pushes_series_homepage_index_and_llms():
    for flag in ("--sync-series", "--sync-homepage", "--sync-index",
                 "--sync-widget", "--sync-llms-txt"):
        assert flag in WF


def test_pushes_the_tire_index_without_the_deleting_tire_sync():
    assert 'wordpress/output/tire/index.html "$R/tire/index.html"' in WF
    assert "--sync-tire-pages" not in WF


def test_season_pages_are_built_before_redirects_are_pushed():
    build = WF.index("python3 wordpress/generate_calendar.py")
    push = WF.index("--sync-redirects")
    assert build < push


def test_live_check_covers_this_seasons_pages():
    assert '"/race/calendar/$season/"' in WF
    assert '"/race/power-rankings-$season/"' in WF
