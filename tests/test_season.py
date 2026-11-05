"""Season rollover and edition-date parsing (wordpress/season.py)."""

import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from season import (  # noqa: E402
    PAST,
    UNDATED,
    UPCOMING,
    edition_state,
    needs_date_refresh,
    parse_edition,
    season_year,
)

NOV_5 = date(2026, 11, 5)


@pytest.mark.parametrize("on,expected", [
    (date(2026, 1, 1), 2026),
    (date(2026, 8, 31), 2026),
    (date(2026, 9, 1), 2027),
    (date(2026, 11, 5), 2027),
    (date(2026, 12, 31), 2027),
])
def test_season_rolls_over_in_september(on, expected):
    assert season_year(on) == expected


@pytest.mark.parametrize("raw,ymd", [
    ("2027: June 5", (2027, 6, 5)),
    ("2026: July 2-5", (2026, 7, 2)),
    ("2027: June 12 (Saturday)", (2027, 6, 12)),
    ("2026: Saturday, September 19 (Gravel day, within the Fri Sep 18-Sun Sep 20)", (2026, 9, 19)),
    ("2026: October 17 (SATURDAY, CONFIRMED — bigsugarclassic.com/gravel/; 2", (2026, 10, 17)),
    ("May 17, 2026", (2026, 5, 17)),
    ("2026: Jan 25, Feb 28, Mar 28, Apr 25, May 24", (2026, 1, 25)),
    ("2026: October 30 - November 1", (2026, 10, 30)),
    ("TBD — 2027 event window: July 31-August 5; exact grand depart pending", (2027, 7, 31)),
    ("2027: April 30 (Fri) - May 2 (Sun) Traka week", (2027, 4, 30)),
])
def test_parses_first_concrete_date(raw, ymd):
    e = parse_edition(raw)
    assert (e.year, e.month, e.day) == ymd


@pytest.mark.parametrize("raw,state", [
    ("2026: August 30", PAST),            # same year, already happened
    ("2027: June 5", UPCOMING),
    ("2026: November 28", UPCOMING),
    ("2026: July TBD", PAST),             # month precision, month passed
    ("2026: December TBD", UPCOMING),
    ("2025: October 18", PAST),
    ("2026: TBD", UNDATED),               # year only, this year: unknown
    ("2027: Date not announced", UNDATED),
    ("2025: Spring/Fall TBD", PAST),
    ("Status: DROPPED — no 2026 or 2027 edition; last held October 11, 2025", UNDATED),
    ("Check USA Cycling for date", UNDATED),
    ("", UNDATED),
    (None, UNDATED),
])
def test_state_is_relative_to_today_not_the_year(raw, state):
    assert edition_state(raw, NOV_5) == state


def test_needs_refresh_flags_past_and_undated_only():
    assert needs_date_refresh("2026: August 30", NOV_5)
    assert needs_date_refresh("2026: TBD", NOV_5)
    assert not needs_date_refresh("2027: June 5", NOV_5)


def test_estimates_are_marked():
    assert parse_edition("2027: May 22 (Saturday, PATTERN ESTIMATE — same weekend)").estimated
    assert parse_edition("2027: April 24 (Saturday pattern; 2026 ran Apr 25)").estimated
    assert not parse_edition("2027: June 5").estimated


def test_lowercase_may_in_notes_is_not_a_month():
    e = parse_edition("2027: TBD (organizers may announce in spring)")
    assert (e.year, e.month) == (2027, None)
