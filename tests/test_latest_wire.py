from datetime import date
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wordpress"))
from generate_latest import flatten_events, render_page, render_rss


INDEX = [{"slug": "alpha", "name": "Alpha Race"}, {"slug": "beta", "name": "Beta & Race"}]


def test_month_grouping_anchors_and_day_rows():
    intel = {"alpha": [{"date": "2026-08-12", "text": "Date confirmed"}, {"date": "2026-07-01", "text": "Re-rated"}], "beta": [{"date": "2026-08-12", "text": "Course news"}]}
    html = render_page(intel, INDEX, date(2026, 8, 13))
    assert html.count('id="2026-08"') == 1
    assert html.count('id="2026-07"') == 1
    assert html.index('id="2026-08"') < html.index('id="2026-07"')
    assert html.count('aria-label="2026-08-12"') == 1


def test_twelve_month_cap():
    intel = {"alpha": [{"date": "2025-09-01", "text": "kept"}, {"date": "2025-08-31", "text": "dropped"}]}
    rows = flatten_events(intel, INDEX, date(2026, 8, 13))
    assert [row["text"] for row in rows] == ["kept"]


def test_empty_intel_is_valid_and_honest():
    html = render_page({}, INDEX, date(2026, 8, 13))
    assert "No verified changes yet." in html
    assert "Every verified change to the race database, newest first." in html
    assert "get_ga4_head_snippet" not in html


def test_rss_validity_limit_links_and_escaping():
    intel = {"beta": [{"date": "2026-08-13", "text": f"A < B & safe {n}"} for n in range(60)]}
    xml = render_rss(intel, INDEX, date(2026, 8, 13))
    root = ET.fromstring(xml)
    items = root.findall("./channel/item")
    assert len(items) == 50
    assert items[0].findtext("link") == "https://gravelgodcycling.com/race/beta/#2026-08"
    assert items[0].findtext("title").startswith("Beta & Race: A < B & safe")


def test_race_links_well_formed_and_data_escaped():
    html = render_page({"alpha": [{"date": "2026-08-13", "text": "</script><b>no</b>"}]}, INDEX, date(2026, 8, 13))
    assert 'href="/race/alpha/"' in html
    assert "</script><b>no</b>" not in html
    assert "&lt;/script&gt;&lt;b&gt;no&lt;/b&gt;" in html
