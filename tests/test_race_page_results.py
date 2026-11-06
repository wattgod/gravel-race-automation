"""Race pages show past results, and a past edition never counts down.

On 2026-11-05 the Traka has results for 2024-2026: the page lists them
newest first under id="results". "2026: September 19" has already run, so
nothing on the page counts down to it, offers a reminder for it or pre-fills
a plan with it. The date scripts look for the 2027 edition, not 2026.
"""

import copy
import importlib
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_neo_brutalist import (  # noqa: E402
    build_course_overview,
    build_date_reminder,
    build_email_capture,
    build_results,
    build_training,
    build_training_intelligence,
    generate_page,
    normalize_race_data,
    upcoming_race_start,
)

PAST = "2026: September 19"
UPCOMING = "2027: May 1"


@pytest.fixture(autouse=True)
def nov_5(monkeypatch):
    monkeypatch.setenv("GG_TODAY", "2026-11-05")


@pytest.fixture
def traka():
    return json.loads((ROOT / "race-data" / "the-traka.json").read_text())


def _with(data, results=..., **vitals):
    data = copy.deepcopy(data)
    data["race"]["vitals"].update(vitals)
    if results is not ...:
        if results is None:
            data["race"].pop("results", None)
        else:
            data["race"]["results"] = results
    return data


def _rd(data, **kw):
    return normalize_race_data(_with(data, **kw))


# ── Results ───────────────────────────────────────────────────────────────

def test_results_rows_newest_first_with_distance_and_times(traka):
    html = build_results(_rd(traka))
    assert 'id="results"' in html
    years = [html.index(f'gg-results-year">{y}') for y in (2026, 2025, 2024)]
    assert years == sorted(years)
    assert "The Traka 360" in html and "The Traka 200" in html
    assert "Rosa Klöser" in html and "11:27:58" in html
    assert "Mads Würtz Schmidt" in html and "9:57:38" in html
    assert ">Women<" in html and ">Men<" in html
    assert "gg-results-note" in html


def test_results_women_column_comes_before_men(traka):
    html = build_results(_rd(traka))
    row = html[html.index('gg-results-year">2026'):]
    assert row.index("Rosa Klöser") < row.index("Mads Würtz Schmidt")


def test_missing_time_shows_no_time_and_missing_winner_shows_dash(traka):
    results = {"years": {"2025": {"winner_male": "A Rider", "winning_time_male": "5:00:00"}}}
    html = build_results(_rd(traka, results=results))
    row = html[html.index('gg-results-year">2025'):]
    assert "<td>&mdash;</td>" in row
    assert row.count("gg-results-time") == 1
    assert "gg-results-race" not in html
    assert "gg-results-note" not in html


def test_results_values_are_escaped(traka):
    results = {"years": {"2026": {"winner_male": "<script>x</script>", "race": "<b>"}},
               "note": "<img src=x>"}
    html = build_results(_rd(traka, results=results))
    assert "<script>x" not in html and "<img" not in html and "<b>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("results", [None, {}, {"years": {}},
                                     {"years": {"2026": {"race": "No winners"}}}])
def test_no_results_renders_nothing(traka, results):
    assert build_results(_rd(traka, results=results)) == ""


def test_page_links_results_in_toc_only_when_rendered(traka):
    with_results = generate_page(_rd(traka), [])
    assert 'id="results"' in with_results
    assert 'data-toc-target="results"' in with_results

    without = generate_page(_rd(traka, results=None), [])
    assert 'id="results"' not in without
    assert 'data-toc-target="results"' not in without
    assert ">Results</h2>" not in without


# ── Past editions never count down ────────────────────────────────────────

@pytest.mark.parametrize("ds,expected", [
    (PAST, None),
    (UPCOMING, "2027-05-01"),
    ("TBD", None),
    ("", None),
    ("2027: TBD", None),
])
def test_upcoming_race_start(ds, expected):
    assert upcoming_race_start(ds) == expected


@pytest.mark.parametrize("build", [build_training, build_training_intelligence])
def test_past_edition_has_no_countdown(traka, build):
    assert "gg-countdown" not in build(_rd(traka, date_specific=PAST))
    assert 'data-date="2027-05-01"' in build(_rd(traka, date_specific=UPCOMING))


def test_past_edition_offers_no_reminder(traka):
    assert build_date_reminder(_rd(traka, date_specific=PAST)) == ""
    assert "data-race-date" not in build_email_capture(_rd(traka, date_specific=PAST))
    assert build_date_reminder(_rd(traka, date_specific=UPCOMING))
    assert 'data-race-date="2027-05-01"' in build_email_capture(
        _rd(traka, date_specific=UPCOMING))


def test_past_edition_has_no_calendar_export(traka):
    assert "calendar.google.com" not in build_course_overview(_rd(traka, date_specific=PAST))
    assert "calendar.google.com" in build_course_overview(_rd(traka, date_specific=UPCOMING))


def test_past_edition_page_never_prefills_a_plan_date(traka):
    html = generate_page(_rd(traka, date_specific=PAST), [])
    assert "gg-countdown\" data-date" not in html
    assert "data-race-date=" not in html
    assert f'"date_specific":"{PAST}"' not in html


# ── Date scripts look for the next edition ────────────────────────────────

@pytest.fixture
def bds(monkeypatch):
    fake = types.ModuleType("ddgs")
    fake.DDGS = object
    monkeypatch.setitem(sys.modules, "ddgs", fake)
    # delitem (not pop) so teardown restores the module other tests imported.
    monkeypatch.delitem(sys.modules, "batch_date_search", raising=False)
    return importlib.import_module("batch_date_search")


@pytest.mark.parametrize("text,expected", [
    ("Race day is June 5, 2027 in Girona", "2027: June 5"),
    ("5-6 June 2027", "2027: June 5-6"),
    ("start 2027-06-05", "2027: June 5"),
    ("May 29-31, 2027", "2027: May 29-31"),
    ("Last edition: June 6, 2026", None),
    ("June 6, 20271", None),
])
def test_batch_search_parses_next_edition_year(bds, text, expected):
    assert bds.extract_date_from_text(text)[0] == expected


def test_batch_search_queries_next_edition_year(bds):
    race = {"name": "The Traka", "vitals": {"location": "Girona, Spain"}}
    queries = bds.build_search_queries(race, "the-traka")
    assert all("2027" in q for q in queries)
    assert not any("2026" in q for q in queries)


@pytest.mark.parametrize("ds,year", [("TBD", 2027), ("2028: TBD", 2028)])
def test_reply_names_the_races_next_year(tmp_path, ds, year):
    import draft_race_reply as drr

    path = tmp_path / "x.json"
    path.write_text(json.dumps({"race": {"name": "X", "vitals": {"date_specific": ds}}}))
    reply = drr.draft(drr.race_facts(path, "https://gravelgodcycling.com"), "", "u")
    assert f"confirmed {year} date" in reply
