"""Race pages keep every edition on record, and a date update never drops one.

``race.editions`` holds past editions (date, cancelled, not held, edition
number, note, source). ``set_date_specific`` moves what the old date recorded
into it before writing the new one. The page's Editions table merges the two.
"""

import copy
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

from race_editions import merge, ordinal, problems, records, set_date_specific  # noqa: E402
from generate_neo_brutalist import (  # noqa: E402
    build_editions,
    build_toc,
    generate_page,
    normalize_race_data,
)

NOV_5 = date(2026, 11, 5)


@pytest.fixture(autouse=True)
def nov_5(monkeypatch):
    monkeypatch.setenv("GG_TODAY", "2026-11-05")


def _profile(slug="the-traka"):
    return json.loads((ROOT / "race-data" / f"{slug}.json").read_text())


# --- what a date_specific string records -------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("2026: September 12-13 (CONFIRMED — x.com)",
     [{"year": 2026, "date": "2026-09-12", "end_date": "2026-09-13"}]),
    ("2027: May 14-15 (CONFIRMED); 2026: June 13 (Saturday, completed)",
     [{"year": 2027, "date": "2027-05-14", "end_date": "2027-05-15"},
      {"year": 2026, "date": "2026-06-13"}]),
    ("2026: August 1 (Saturday, CONFIRMED — sableevents.com); 2027 pattern ~Aug 7",
     [{"year": 2026, "date": "2026-08-01"}]),
    ("2027: July 11 (Sunday, PATTERN ESTIMATE — second Sunday of July)", []),
    ("2027: TBD", []),
    ("2027: June", []),
    ('Status: CANCELLED for 2026 (cowboycrusher.com: "2026 Event Cancelled")',
     [{"year": 2026, "status": "cancelled"}]),
    ("Status: DROPPED — no 2026 or 2027 edition; last held October 14, 2023",
     [{"year": 2027, "status": "not_held"}, {"year": 2026, "status": "not_held"},
      {"year": 2023, "date": "2023-10-14"}]),
    ("Status: ON HIATUS — suspended for 2025 and 2026; last held July 28, 2024 (velocity.berlin)",
     [{"year": 2024, "date": "2024-07-28"}]),
    ("TBD — last confirmed July 3-5, 2026; next edition not announced",
     [{"year": 2026, "date": "2026-07-03", "end_date": "2026-07-05"}]),
    ("2027: June 12 (pattern — 2nd Saturday of June; 2026 edition ran June 13)",
     [{"year": 2026, "date": "2026-06-13"}]),
])
def test_records(text, expected):
    assert records(text) == expected


# --- set_date_specific keeps the old edition ---------------------------------

def test_new_year_moves_the_old_date_into_editions():
    race = {"vitals": {"date_specific": "2026: September 12 (CONFIRMED — x.com)"},
            "history": {}, "results": {}}
    added = set_date_specific(race, "2027: June 5 (CONFIRMED — x.com)", on=NOV_5)
    assert added == [{"year": 2026, "date": "2026-09-12"}]
    assert race["vitals"]["date_specific"].startswith("2027: June 5")
    assert race["editions"] == [{"year": 2026, "date": "2026-09-12"}]
    assert list(race) == ["vitals", "history", "editions", "results"]


def test_same_year_correction_is_not_kept():
    race = {"vitals": {"date_specific": "2027: June 5"}}
    assert set_date_specific(race, "2027: June 12", on=NOV_5) == []
    assert "editions" not in race


def test_future_date_that_moves_years_is_not_a_past_edition():
    race = {"vitals": {"date_specific": "2027: January 10 (CONFIRMED)"}}
    set_date_specific(race, "2026: December 20 (CONFIRMED)", on=NOV_5)
    assert "editions" not in race


def test_estimates_and_tbd_are_never_kept():
    race = {"vitals": {"date_specific": "2026: September 12 (pattern estimate)"}}
    set_date_specific(race, "2027: TBD", on=NOV_5)
    assert "editions" not in race


def test_cancellation_is_kept():
    race = {"vitals": {"date_specific": "Status: CANCELLED for 2026"}}
    set_date_specific(race, "2027: July 10 (CONFIRMED)", on=NOV_5)
    assert race["editions"] == [{"year": 2026, "status": "cancelled"}]


def test_existing_entry_keeps_its_note_and_source():
    race = {"vitals": {"date_specific": "2026: May 2 (CONFIRMED)"},
            "editions": [{"year": 2026, "edition": 5, "source": "https://x.com/"}]}
    set_date_specific(race, "2027: May 1", on=NOV_5)
    assert race["editions"] == [
        {"year": 2026, "date": "2026-05-02", "edition": 5, "source": "https://x.com/"}]


def test_merge_primary_wins_and_orders_newest_first():
    out = merge([{"year": 2025, "date": "2025-05-03"}],
                [{"year": 2025, "date": "2025-05-10", "note": "n"}, {"year": 2026, "status": "cancelled"}])
    assert out == [{"year": 2026, "status": "cancelled"},
                   {"year": 2025, "date": "2025-05-03", "note": "n"}]


@pytest.mark.parametrize("n,text", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"),
                                    (11, "11th"), (12, "12th"), (13, "13th"), (21, "21st"), (102, "102nd")])
def test_ordinal(n, text):
    assert ordinal(n) == text


# --- every profile -------------------------------------------------------------

def test_every_profiles_editions_are_valid():
    bad = {}
    for path in sorted((ROOT / "race-data").glob("*.json")):
        race = json.loads(path.read_text())["race"]
        found = problems(race)
        if found:
            bad[path.stem] = found
    assert not bad, bad


def test_problems_catches_drift_from_date_specific():
    race = {"vitals": {"date_specific": "2026: September 12 (CONFIRMED)"},
            "editions": [{"year": 2026, "date": "2026-09-19"}]}
    assert any("disagrees" in p for p in problems(race))


@pytest.mark.parametrize("entry,fragment", [
    ({"year": 2026, "date": "2026-13-01"}, "YYYY-MM-DD"),
    ({"year": 2026, "date": "2025-09-01"}, "not in 2026"),
    ({"year": 2026, "status": "postponed"}, "status"),
    ({"year": 2026, "date": "2026-09-01", "source": "http://x.com"}, "https"),
    ({"year": 2026}, "nothing beyond the year"),
    ({"year": 2026, "date": "2026-09-01", "winner": "x"}, "unknown keys"),
])
def test_problems_rejects(entry, fragment):
    assert any(fragment in p for p in problems({"vitals": {}, "editions": [entry]}))


def test_problems_accepts_editions_back_to_1950():
    """Nove Colli started in 1971; the floor is 1950, not the 1980 it once was."""
    ok = {"year": 1971, "date": "1971-05-16", "source": "https://www.novecolli.it/"}
    assert problems({"vitals": {}, "editions": [ok]}) == []
    too_old = {"year": 1949, "date": "1949-05-16", "source": "https://www.novecolli.it/"}
    assert problems({"vitals": {}, "editions": [too_old]})


def test_no_script_writes_date_specific_directly():
    """Date writers go through set_date_specific so the old edition is kept."""
    direct = re.compile(r"""\[\s*["']date_specific["']\s*\]\s*=(?!=)""")
    offenders = []
    for folder in ("scripts", "wordpress"):
        for path in (ROOT / folder).glob("*.py"):
            if path.name == "race_editions.py":
                continue
            for n, line in enumerate(path.read_text().splitlines(), 1):
                if direct.search(line) and 'result["fields"]' not in line:
                    offenders.append(f"{folder}/{path.name}:{n}")
    assert not offenders, offenders


# --- the page --------------------------------------------------------------------

def _rd(date_specific, editions):
    data = copy.deepcopy(_profile())
    data["race"]["vitals"]["date_specific"] = date_specific
    data["race"]["editions"] = editions
    return normalize_race_data(data)


def test_editions_table_lists_history_newest_first():
    html = build_editions(_rd("2027: June 5 (CONFIRMED — x.com)", [
        {"year": 2026, "date": "2026-09-12", "end_date": "2026-09-13", "edition": 5,
         "source": "https://x.com/2026"},
        {"year": 2025, "status": "cancelled", "note": "Wildfire closed the course"},
    ]))
    assert 'id="editions"' in html
    assert html.index(">2027<") < html.index(">2026<") < html.index(">2025<")
    assert "Jun 5" in html and "Sep 12–13" in html
    assert 'href="https://x.com/2026"' in html
    assert "Cancelled" in html and "Wildfire closed the course" in html
    assert "5th edition" in html


def test_no_table_for_a_single_edition():
    assert build_editions(_rd("2027: June 5 (CONFIRMED)", [])) == ""


def test_estimate_never_shows_in_the_table():
    html = build_editions(_rd("2027: June 12 (pattern estimate)", [
        {"year": 2026, "date": "2026-06-13"}, {"year": 2025, "date": "2025-06-14"}]))
    assert ">2027<" not in html and ">2026<" in html


def test_notes_column_only_when_a_row_has_one():
    html = build_editions(_rd("2027: June 5", [{"year": 2026, "date": "2026-06-06"}]))
    assert "Notes" not in html


def test_page_links_editions_in_the_toc():
    data = copy.deepcopy(_profile())
    data["race"]["vitals"]["date_specific"] = "2027: June 5 (CONFIRMED)"
    data["race"]["editions"] = [{"year": 2026, "date": "2026-06-06"}]
    html = generate_page(normalize_race_data(data))
    assert 'href="#editions"' in html and 'id="editions"' in html
    assert 'href="#editions"' not in build_toc({"course"})


@pytest.mark.parametrize("founded,shown", [
    (2016, "Founded in 2016."), ("2016 (UCI 1.2 status since 2018)", "Founded in 2016 (UCI"),
    ("DATA NOT FOUND", None), ("~2019", None), ("2010s", None), (None, None)])
def test_history_only_states_a_real_founding_year(founded, shown):
    from generate_neo_brutalist import build_history
    data = copy.deepcopy(_profile())
    data["race"]["history"]["founded"] = founded
    html = build_history(normalize_race_data(data))
    if shown:
        assert shown in html
    else:
        assert "Founded in" not in html


def test_correction_keeps_nothing_from_the_wrong_value():
    race = {"vitals": {"date_specific": "Status: DROPPED — last held October 11, 2025"}}
    assert set_date_specific(race, "Status: DROPPED — last held October 14, 2023",
                             on=NOV_5, correction=True) == []
    assert "editions" not in race


def test_long_history_keeps_the_newest_ten_rows_in_view():
    editions = [{"year": y, "date": f"{y}-06-01"} for y in range(2026, 2005, -1)]
    html = build_editions(_rd("2027: June 5 (CONFIRMED)", editions))
    table, earlier = html.split('<details class="gg-earlier-rows">')
    assert table.count("<tr><th scope=\"row\"") == 10
    assert ">2027<" in table and ">2018<" in table and ">2017<" not in table
    assert "Earlier editions: 2006&ndash;2017" in earlier
    assert earlier.count("<tr><th scope=\"row\"") == 12


def test_short_history_has_no_disclosure():
    html = build_editions(_rd("2027: June 5", [{"year": y, "date": f"{y}-06-01"} for y in range(2026, 2018, -1)]))
    assert "gg-earlier-rows" not in html


def test_results_older_than_ten_years_fold_away():
    from generate_neo_brutalist import build_results
    data = copy.deepcopy(_profile())
    data["race"]["results"] = {"years": {str(y): {"winner_male": f"M{y}", "winner_female": f"F{y}"}
                                         for y in range(2006, 2027)}}
    html = build_results(normalize_race_data(data))
    table, earlier = html.split('<details class="gg-earlier-rows">')
    assert "M2026" in table and "M2017" in table and "M2016" not in table
    assert "Earlier results: 2006&ndash;2016" in earlier and "M2006" in earlier


def test_unbound_200_carries_its_full_history():
    race = _profile("unbound-200")["race"]
    years = {e["year"] for e in race["editions"]}
    assert set(range(2006, 2027)) <= years
    assert next(e for e in race["editions"] if e["year"] == 2020)["status"] == "cancelled"
    winners = race["results"]["years"]
    assert winners["2006"]["winner_male"] == "Dan Hughes"
    assert all(str(y) in winners for y in range(2006, 2027) if y != 2020)
