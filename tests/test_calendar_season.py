"""Season calendar: races sit in the month of their next edition.

/race/calendar/{season}/ places each race by its stored upcoming date or,
until one is announced, on the date projected from its last edition marked
"Est.". Only a race with nothing to project (not running, skipped a season,
no month) sits in the month it last ran marked "{season} date TBA".
Earlier seasons stay generated as archives that link to the season page.
"""

import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_calendar as gc  # noqa: E402

SEASON = gc.SEASON_YEAR
ON = date(SEASON - 1, 11, 5)  # autumn before the season: last year's editions have run


@pytest.fixture(autouse=True)
def autumn(monkeypatch):
    monkeypatch.setenv("GG_TODAY", ON.isoformat())


def _race(slug, month="June", status="active", tier=2, score=70):
    return {"slug": slug, "name": slug.title(), "month": month, "status": status,
            "tier": tier, "overall_score": score, "location": "Somewhere",
            "region": "West", "has_profile": True}


class TestPlaceRace:
    def test_confirmed_upcoming_date_sets_the_month(self):
        spot = gc.place_race(_race("a", month="June"), SEASON, f"{SEASON}: April 18")
        assert spot == ("April", "confirmed", "Apr 18", 18)

    def test_month_only_edition_is_confirmed_without_a_day(self):
        month, kind, label, _ = gc.place_race(_race("a"), SEASON, f"{SEASON}: July TBD")
        assert (month, kind) == ("July", "confirmed")
        assert "day TBA" in label

    def test_estimate_is_marked_as_an_estimate(self):
        month, kind, label, _ = gc.place_race(
            _race("a"), SEASON, f"{SEASON}: May 9 (estimated from pattern)")
        assert (month, kind) == ("May", "estimated")
        assert label.startswith("Est.")

    def test_past_edition_is_placed_on_its_estimate(self):
        last = date(SEASON - 1, 9, 20)
        month, kind, label, day = gc.place_race(
            _race("a", month="August"), SEASON, f"{SEASON - 1}: September 20")
        assert (month, kind) == ("September", "estimated")
        assert label == f"Est. Sep {day}"
        assert date(SEASON, 9, day).weekday() == last.weekday()

    def test_past_month_only_edition_is_estimated_without_a_day(self):
        spot = gc.place_race(_race("a"), SEASON, f"{SEASON - 1}: July TBD")
        assert spot == ("July", "estimated", "Est. Jul", 99)

    @pytest.mark.parametrize("race,ds,project", [
        (_race("a", month="August"), f"{SEASON - 1}: September 20", False),
        (_race("a", status="inactive"), f"{SEASON - 1}: September 20", True),
        (_race("a", month="August"), f"{SEASON - 2}: September 20", True),  # skipped
    ])
    def test_nothing_to_project_falls_back_to_the_month_it_last_ran(self, race, ds, project):
        month, kind, label, _ = gc.place_race(race, SEASON, ds, project=project)
        assert (month, kind, label) == ("September", "tba", f"{SEASON} date TBA")

    def test_undated_race_uses_the_index_month(self):
        month, kind, _, _ = gc.place_race(_race("a", month="March"), SEASON, None)
        assert (month, kind) == ("March", "tba")

    def test_edition_after_the_season_is_left_off(self):
        assert gc.place_race(_race("a"), SEASON, f"{SEASON + 1}: June 1") is None

    def test_archive_uses_that_years_edition_without_tba_marks(self):
        month, kind, label, _ = gc.place_race(
            _race("a", month="June"), SEASON - 1, f"{SEASON - 1}: October 4")
        assert (month, kind, label) == ("October", "archived", "Oct 4")
        _, kind, label, _ = gc.place_race(_race("b"), SEASON - 1, f"{SEASON}: May 2")
        assert (kind, label) == ("archived", "")


class TestCalendarPages:
    RACES = [
        _race("confirmed-race", month="June"),
        _race("estimated-race", month="June"),
        _race("tba-race", month="August"),
        _race("gone-race", status="inactive"),
    ]
    EDITIONS = {"confirmed-race": f"{SEASON}: April 18",
                "estimated-race": f"{SEASON - 1}: September 12",
                "tba-race": f"{SEASON - 1}: August 2"}
    FIXED = frozenset({"tba-race"})  # e.g. source blocked: never projected

    def test_season_page(self):
        html = gc.build_calendar_page(self.RACES, SEASON, self.EDITIONS, self.FIXED)
        assert f'<link rel="canonical" href="https://gravelgodcycling.com/race/calendar/{SEASON}/">' in html
        assert f"<h1>{SEASON} Gravel Race Calendar</h1>" in html
        assert "1 dates confirmed" in html
        april = html.split('id="month-april"')[1].split("</section>")[0]
        assert "/race/confirmed-race/" in april and "Apr 18" in april
        august = html.split('id="month-august"')[1].split("</section>")[0]
        assert "/race/tba-race/" in august and f"{SEASON} date TBA" in august
        september = html.split('id="month-september"')[1].split("</section>")[0]
        assert "/race/estimated-race/" in september and "Est. Sep " in september
        assert "/race/gone-race/" not in html  # not running stays off
        assert gc.get_ga4_head_snippet() in html

    def test_archive_links_to_the_season(self):
        html = gc.build_calendar_page(self.RACES, SEASON - 1, self.EDITIONS, self.FIXED)
        assert f'/race/calendar/{SEASON - 1}/">' in html  # canonical stays put
        assert f'<a href="/race/calendar/{SEASON}/">{SEASON} calendar' in html
        assert "date TBA" not in html and "Est. " not in html

    def test_generates_every_season_from_the_first(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["generate_calendar.py", "--output-dir", str(tmp_path)])
        gc.main()
        for year in range(gc.FIRST_CALENDAR_YEAR, SEASON + 1):
            assert (tmp_path / "calendar" / str(year) / "index.html").exists()
        assert not (tmp_path / "calendar" / "index.html").exists()


class TestEvergreenCalendarUrl:
    def test_bare_calendar_redirects_to_the_season(self):
        import push_wordpress as pw

        rule = f"RewriteRule ^race/calendar/?$ /race/calendar/{SEASON}/ [R=302,L]"
        assert pw.SEASON_CALENDAR_REDIRECT_RULE == rule
        assert rule in pw.REDIRECT_BLOCK

    def test_tombstones_point_at_the_evergreen_calendar(self):
        source = (ROOT / "scripts" / "push_wordpress.py").read_text()
        assert "/race/calendar/2026/ [R=301" not in source
        tombstones = (ROOT / "config" / "tombstones.json").read_text()
        assert "/race/calendar/20" not in tombstones

    def test_sitemap_lists_the_season_calendar(self, tmp_path):
        import generate_sitemap as gs

        assert f"calendar/{SEASON}" in gs.load_special_pages(tmp_path)
