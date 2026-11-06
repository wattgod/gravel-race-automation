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


# ── Ranges, ISO, stored form ─────────────────────────────────────────────

from season import canonical, edition_display, edition_year  # noqa: E402


@pytest.mark.parametrize("raw,end", [
    ("2026: August 19-23", date(2026, 8, 23)),
    ("2026: June 30 - July 2", date(2026, 7, 2)),
    ("2027: April 30 (Fri) - May 2 (Sun) Traka", date(2027, 5, 2)),
    ("2026: Dec 30 - Jan 2", date(2027, 1, 2)),
    ("May 17-18, 2027", date(2027, 5, 18)),
    ("2027: June 5", None),
])
def test_end_date_of_multi_day_edition(raw, end):
    assert parse_edition(raw).end_date == end


def test_iso_date_parses():
    assert parse_edition("2027-06-05").date == date(2027, 6, 5)


@pytest.mark.parametrize("raw,stored", [
    ("2027-06-05", "2027: June 5"),
    ("June 5, 2027", "2027: June 5"),
    ("2026: August 19-23", "2026: August 19-23"),
    ("2026: June 30 - July 2", "2026: June 30 - July 2"),
    ("2027: TBD", None),
])
def test_canonical_is_the_stored_form(raw, stored):
    assert canonical(parse_edition(raw)) == stored


# ── What a race page says about its edition ──────────────────────────────

@pytest.mark.parametrize("raw,shown", [
    ("2027: June 5", None),
    ("2027: June 5 (Saturday pattern; 2026 ran Jun 6)", "Jun 5, 2027 (estimate)"),
    ("2026: September 19", "Sep 18, 2027 (estimate)"),     # 3rd Saturday
    ("2026: Sept TBD", "Sep 2027 (estimate)"),
    ("2025: August 3", "2027 date not announced · last ran Aug 3, 2025"),  # skipped 2026
    ("2027: TBD", None),
    ("Status: DROPPED — last held October 11, 2025", None),
    ("", None),
])
def test_edition_display(raw, shown):
    assert edition_display(raw, NOV_5) == shown


def test_past_display_names_the_year_after_the_last_edition():
    """In May 2026 a March 2026 edition's next one is 2027, not 2026."""
    assert edition_display("2026: March 28", date(2026, 5, 1)) == "Mar 27, 2027 (estimate)"
    shown = edition_display("2026: March 28", date(2026, 5, 1), project=False)
    assert shown.startswith("2027 date not announced")


def test_not_running_race_is_never_projected():
    shown = edition_display("2026: September 19", NOV_5, project=False)
    assert shown == "2027 date not announced · last ran Sep 19, 2026"
    assert edition_year("2026: September 19", NOV_5, project=False) is None


@pytest.mark.parametrize("raw,year", [
    ("2027: June 5", 2027),
    ("2027: TBD", 2027),
    ("2026: August 30", 2027),            # estimated next edition
    ("2025: August 3", None),             # skipped 2026: no estimate
    ("2026: Spring TBD", None),
    ("Status: CANCELLED for 2026", None),
    ("", None),
])
def test_edition_year_never_stale(raw, year):
    assert edition_year(raw, NOV_5) == year


# ── Estimating the next edition of a race that has not announced it ──────

from season import estimate_next  # noqa: E402


@pytest.mark.parametrize("raw,start,end", [
    ("2026: September 19", date(2027, 9, 18), None),             # 3rd Saturday
    ("2026: March 29", date(2027, 3, 28), None),                 # 5th Sunday -> last
    ("2026: May 30", date(2027, 5, 29), None),                   # 5th Saturday -> last
    ("2026: August 29-30", date(2027, 8, 28), date(2027, 8, 29)),
    ("2026: June 30 - July 2", date(2027, 6, 29), date(2027, 7, 1)),
    ("2025: December 30 - January 2", date(2026, 12, 29), date(2027, 1, 1)),
    ("2025: November 22", date(2026, 11, 28), None),             # still upcoming
])
def test_estimate_keeps_the_weekday_and_length(raw, start, end):
    est = estimate_next(raw, NOV_5)
    assert est.estimated
    assert (est.date, est.end_date) == (start, end)
    assert est.date.weekday() == parse_edition(raw).date.weekday()
    assert est.state(NOV_5) == UPCOMING


def test_month_only_edition_estimates_the_month():
    est = estimate_next("2026: July TBD", NOV_5)
    assert (est.year, est.month, est.day, est.estimated) == (2027, 7, None, True)


@pytest.mark.parametrize("raw", [
    "2025: August 3",        # projection (Aug 2026) has passed: skipped a season
    "2027: June 5",          # not past
    "2026: December 12",     # not past
    "2025: TBD",             # no month
    "2026: Spring TBD",
    "Status: DROPPED — last held October 11, 2025",
    "",
    None,
])
def test_no_estimate(raw):
    assert estimate_next(raw, NOV_5) is None
