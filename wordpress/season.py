"""Season year and race-edition dates, shared by generators and data scripts.

Two rules live here so no generator or audit re-derives them:

1. The racing season rolls over before the calendar year does. Riders plan,
   search and register for next year's races from autumn, so from
   ``ROLLOVER_MONTH`` (September by default) the current season is next year.
   Use ``season_year()`` for anything a rider reads as "this season" (page
   titles, calendar URLs, hub headings). Copyright lines and dates stamped on
   reports keep ``date.today().year``.

2. An edition is stale when its date has passed, not when its year is lower
   than this year. "2026: August 30" is stale on 2026-11-05.

``vitals.date_specific`` is free text ("2027: June 5", "May 17, 2026",
"2026: July TBD", "Status: HOLD — ..."). ``parse_edition()`` reads the first
concrete date out of it and records how precise it is.

Tests: tests/test_season.py. Override "today" with GG_TODAY=YYYY-MM-DD and the
rollover month with GG_SEASON_ROLLOVER_MONTH.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import date

ROLLOVER_MONTH = int(os.environ.get("GG_SEASON_ROLLOVER_MONTH", "9"))

_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
# Capitalised month names only: free-text notes use lower-case "may" as a verb.
_MONTH_RE = (
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?"
)
_PREFIX_YEAR = re.compile(r"^\s*(20\d{2})\s*:")
_MONTH_DAY = re.compile(_MONTH_RE + r"\s+(\d{1,2})(?!\d)")
_MONTH_ONLY = re.compile(_MONTH_RE + r"\b")
_US_STYLE = re.compile(_MONTH_RE + r"\s+(\d{1,2}),\s*(20\d{2})\b")
_ANY_YEAR = re.compile(r"\b(20\d{2})\b")
_STATUS = re.compile(
    r"^\s*(Status\s*:|Cancel+ed\b|Paused\b|Check\b|TBD\b.{0,20}\blast\b)",
    re.IGNORECASE,
)
_ESTIMATE = re.compile(r"\b(pattern|estimate|estimated|provisional|expected)\b",
                       re.IGNORECASE)

UPCOMING = "upcoming"
PAST = "past"
UNDATED = "undated"


def today() -> date:
    """Today, or GG_TODAY when set (tests, backfills)."""
    raw = os.environ.get("GG_TODAY")
    return date.fromisoformat(raw) if raw else date.today()


def season_year(on: date | None = None) -> int:
    """The season riders are planning for on ``on`` (default today)."""
    on = on or today()
    return on.year + 1 if on.month >= ROLLOVER_MONTH else on.year


@dataclass(frozen=True)
class Edition:
    """The first concrete date found in a ``date_specific`` string."""

    raw: str
    year: int | None = None
    month: int | None = None
    day: int | None = None
    estimated: bool = False
    status_note: bool = False

    @property
    def date(self) -> date | None:
        if self.year and self.month and self.day:
            try:
                return date(self.year, self.month, self.day)
            except ValueError:
                return None
        return None

    def state(self, on: date | None = None) -> str:
        """UPCOMING, PAST or UNDATED relative to ``on`` (default today)."""
        on = on or today()
        if not self.year:
            return UNDATED
        exact = self.date
        if exact:
            return PAST if exact < on else UPCOMING
        if self.month:
            return PAST if (self.year, self.month) < (on.year, on.month) else UPCOMING
        return PAST if self.year < on.year else UNDATED


def parse_edition(date_specific) -> Edition:
    raw = "" if date_specific is None else str(date_specific).strip()
    if not raw:
        return Edition(raw=raw)
    estimated = bool(_ESTIMATE.search(raw[:120]))
    status_note = bool(_STATUS.match(raw))

    prefix = _PREFIX_YEAR.match(raw)
    if prefix:
        year = int(prefix.group(1))
        rest = raw[prefix.end():]
        head = rest[:80]
        md = _MONTH_DAY.search(head)
        if md:
            return Edition(raw, year, _MONTHS[md.group(1).lower()], int(md.group(2)),
                           estimated, status_note)
        mo = _MONTH_ONLY.search(head)
        if mo:
            return Edition(raw, year, _MONTHS[mo.group(1).lower()], None,
                           estimated, status_note)
        return Edition(raw, year, None, None, estimated, status_note)

    if status_note:
        # "Status: DROPPED — ... last held October 11, 2025" describes a past
        # edition, not the next one.
        return Edition(raw, None, None, None, estimated, True)

    us = _US_STYLE.search(raw[:80])
    if us:
        return Edition(raw, int(us.group(3)), _MONTHS[us.group(1).lower()],
                       int(us.group(2)), estimated, status_note)

    year = _ANY_YEAR.search(raw)
    if not year:
        return Edition(raw, None, None, None, estimated, status_note)
    tail = raw[year.end():year.end() + 80]
    md = _MONTH_DAY.search(tail)
    if md:
        return Edition(raw, int(year.group(1)), _MONTHS[md.group(1).lower()],
                       int(md.group(2)), estimated, status_note)
    return Edition(raw, int(year.group(1)), None, None, estimated, status_note)


def edition_state(date_specific, on: date | None = None) -> str:
    return parse_edition(date_specific).state(on)


def needs_date_refresh(date_specific, on: date | None = None) -> bool:
    """True when the stored edition has passed or has no usable date."""
    return edition_state(date_specific, on) != UPCOMING
