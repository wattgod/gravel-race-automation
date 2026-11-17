"""Race-page trust fixes (2026-11-17): clean public dates, no plan totals,
no contradictory score history, no empty news shell, readable source names."""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from season import public_date  # noqa: E402
import generate_neo_brutalist as gnb  # noqa: E402

ON = date(2026, 11, 17)


def test_public_date_drops_research_notes():
    raw = "2027: June 5 (Saturday, CONFIRMED — unboundgravel.com; registration lottery)"
    shown = public_date(raw, ON)
    assert shown == "Sat, Jun 5, 2027"
    assert "CONFIRMED" not in shown and "unboundgravel" not in shown


def test_public_date_honest_when_unknown():
    assert public_date("", ON, status_label="Taking a break") == "Taking a break"
    assert public_date(None, ON) is None


def test_latest_rail_drops_stale_rescore():
    rd = {"slug": "x", "name": "X", "rating": {"overall_score": 96}}
    stale = [{"date": "2026-10-01", "type": "rescored", "text": "Rescored 93 → 95"}]
    current = [{"date": "2026-10-01", "type": "rescored", "text": "Rescored 95 → 96"}]
    stale_html = gnb.build_latest_sidebar(rd, stale)
    assert "93 → 95" not in stale_html and "WATCH THIS RACE" in stale_html
    assert "95 → 96" in gnb.build_latest_sidebar(rd, current)
    plain = [{"date": "2026-10-01", "type": "rescored", "text": "Rescored"}]
    assert ">Rescored</span>" in gnb.build_latest_sidebar(rd, plain)


def test_news_section_starts_hidden():
    html = gnb.build_news_section({"tier": 1, "name": "Unbound 200"})
    assert '<section id="news"' in html and " hidden>" in html


def test_citation_labels_are_readable():
    assert gnb._citation_label("Ircbike", "https://www.ircbike.com/en/x") == "ircbike.com"
    assert gnb._citation_label("Unbound%20200", "https://unboundgravel.com") == "Unbound 200"
    assert gnb._citation_label("Velo News", "https://velo.outsideonline.com") == "Velo News"


def test_generator_has_no_plan_totals():
    src = (ROOT / "wordpress" / "generate_neo_brutalist.py").read_text()
    assert "data-plan-quote" not in src
    assert "build_plan_quote" not in src
    assert " in all'" not in src and "pricing.summary" not in src


def test_news_never_in_toc_or_breakdown():
    src = (ROOT / "wordpress" / "generate_neo_brutalist.py").read_text()
    assert "active.add('news')" not in src


def test_no_raw_date_fallback():
    src = (ROOT / "wordpress" / "generate_neo_brutalist.py").read_text()
    assert "short_date or vitals.get('date'" not in src
    assert "short_date = vitals.get('date'" not in src
