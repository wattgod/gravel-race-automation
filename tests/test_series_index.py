"""/race/series/ index and the optional series-data fields.

Optional fields: series.status ("active"|"ended"), ended_year, successor,
predecessor, season; per event date (ISO), date_text, round, note.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_series_hubs as gsh  # noqa: E402


def _series(slug, name, **extra):
    base = {"slug": slug, "name": name, "display_name": name, "tagline": f"{name} tagline",
            "events": [{"name": "Opener", "month": "March", "location": "A"},
                       {"name": "Finale", "month": "June", "location": "B"}],
            "key_stats": {"total_events": 2, "countries": 1}}
    base.update(extra)
    return base


OLD = _series("old-cup", "Old Cup", status="ended", ended_year=2025, successor="new-cup")
NEW = _series("new-cup", "New Cup", status="active", season=2027)


class TestSeriesIndex:
    def test_lists_every_series_with_count_and_status(self):
        html = gsh.build_series_index_page([OLD, NEW])
        assert '<link rel="canonical" href="https://gravelgodcycling.com/race/series/">' in html
        assert 'href="/race/series/new-cup/">New Cup</a>' in html
        assert 'href="/race/series/old-cup/">Old Cup</a>' in html
        assert html.count("2 events") == 2
        assert "Active" in html and "Ended 2025" in html
        assert html.index("New Cup") < html.index("Old Cup")  # active first
        assert gsh.get_ga4_head_snippet() in html
        assert "@font-face" in html
        assert "onclick=" not in html and "innerHTML" not in html

    def test_main_writes_the_index(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["generate_series_hubs.py", "--output-dir", str(tmp_path)])
        gsh.main()
        html = (tmp_path / "index.html").read_text()
        for path in sorted((ROOT / "series-data").glob("*.json")):
            import json
            slug = json.loads(path.read_text())["series"]["slug"]
            assert f'href="/race/series/{slug}/"' in html

    def test_sitemap_lists_the_index(self, tmp_path):
        import generate_sitemap as gs

        out = tmp_path / "web" / "sitemap.xml"
        out.parent.mkdir()
        gs.generate_sitemap([], out, series_slugs=["new-cup"])
        xml = out.read_text()
        assert "<loc>https://gravelgodcycling.com/race/series/</loc>" in xml


class TestSeriesLineage:
    NAMES = {"old-cup": "Old Cup", "new-cup": "New Cup"}

    def test_ended_series_is_a_history_page_linking_its_successor(self):
        html = gsh.build_hub_page(OLD, {}, {}, self.NAMES)
        assert "ENDED 2025" in html
        assert "Series History" in html.split("<title>")[1].split("</title>")[0]
        assert ('href="/race/series/new-cup/">Ended 2025. Continues as New Cup &rarr;</a>'
                in html)
        assert "Final Season: 2025" in html

    def test_successor_links_back(self):
        html = gsh.build_hub_page(dict(NEW, predecessor="old-cup"), {}, {}, self.NAMES)
        assert 'href="/race/series/old-cup/">&larr; Formerly Old Cup</a>' in html
        assert "2027 Event Calendar" in html

    def test_hub_breadcrumb_target_now_exists(self, tmp_path, monkeypatch):
        monkeypatch.setattr(sys, "argv", ["generate_series_hubs.py", "--output-dir", str(tmp_path)])
        gsh.main()
        assert (tmp_path / "index.html").exists()
        hub = next(tmp_path.glob("*/index.html")).read_text()
        assert '<a href="/race/series/">Series</a>' in hub


class TestEventDates:
    def test_events_sort_by_date_when_present(self):
        events = [
            {"name": "June event", "month": "June"},
            {"name": "Dated May", "month": "June", "date": "2027-05-02"},
            {"name": "March event", "month": "March"},
            {"name": "Dated April", "date": "2027-04-11"},
        ]
        order = [e["name"] for e in gsh.sort_events(events, 2027)]
        assert order == ["March event", "Dated April", "Dated May", "June event"]

    def test_round_breaks_ties(self):
        events = [{"name": "B", "month": "May", "round": 2}, {"name": "A", "month": "May", "round": 1}]
        assert [e["name"] for e in gsh.sort_events(events, 2027)] == ["A", "B"]

    def test_card_renders_date_round_and_note(self):
        card = gsh.build_event_card(
            {"name": "X", "month": "April", "date": "2027-04-11", "round": 3,
             "note": "Double points"}, {})
        assert '<time datetime="2027-04-11">Apr 11, 2027</time>' in card
        assert ">R3<" in card
        assert "Double points" in card

    def test_card_falls_back_to_date_text_then_month(self):
        assert "First half of April" in gsh.build_event_card(
            {"name": "X", "month": "April", "date_text": "First half of April"}, {})
        assert ">April<" in gsh.build_event_card({"name": "X", "month": "April"}, {})
