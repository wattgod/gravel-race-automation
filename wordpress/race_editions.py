"""Edition history for race profiles (``race.editions``).

A profile keeps the editions it has on record, newest first::

    "editions": [
      {"year": 2026, "date": "2026-09-12", "end_date": "2026-09-13",
       "edition": 5, "note": "Moved from June", "source": "https://..."},
      {"year": 2025, "status": "cancelled", "note": "Wildfire"}
    ]

Only ``year`` is required. ``status`` is absent for an edition that ran on
its date, and "cancelled" or "not_held" otherwise.

The next edition lives in ``vitals.date_specific``. Writing a new date with
``set_date_specific`` moves what the old value recorded into ``editions``
first, so a date update never drops the previous edition. Estimates are never
recorded: they are build-time only.
"""

from __future__ import annotations

import re
from datetime import date

from season import today, parse_edition

STATUSES = {"cancelled": "Cancelled", "not_held": "Not held"}
FIELDS = ("year", "date", "end_date", "status", "edition", "note", "source")
NOTE_MAX = 160

_SEGMENT = re.compile(r";\s*(?=20\d{2}\s*:)")
_CANCELLED = re.compile(r"\bcancel+ed\s+(?:for\s+(?:the\s+)?)?(20\d{2})\b", re.I)
_CANCELLED_EDITION = re.compile(r"\b(20\d{2})\s+(?:edition|event)\s+(?:was\s+)?cancel+ed\b", re.I)
_NOT_HELD = re.compile(
    r"\bno\s+20\d{2}(?:\s*(?:,|or|and|/)\s*20\d{2})*\s+(?:edition|race|event)\b", re.I)
# Words that make a date a guess rather than a record.
_UNSURE = re.compile(
    r"\b(?:pattern|estimated?|provisional|expected|projected|likely|tentative|"
    r"approx\w*|typically|usually|tbc|tbd|unconfirmed|anticipated|assumed|"
    r"probably|pending|unverified)\b|~|not yet confirmed", re.I)
_MONTH = (r"(January|February|March|April|May|June|July|August|September|"
          r"October|November|December)")
_LAST_HELD = re.compile(
    r"\blast\s+(?:held|ran|run|confirmed)\s+(?:on\s+)?" + _MONTH +
    r"\s+(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?,\s*(20\d{2})\b", re.I)
_EDITION_RAN = re.compile(
    r"\b(20\d{2})\s+edition\s+(?:ran|was\s+held|held)\s+(?:on\s+)?" + _MONTH +
    r"\s+(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?\b", re.I)
_MONTHS = {m.lower(): i for i, m in enumerate(_MONTH[1:-1].split("|"), 1)}


def _add_day(add, year: int, month: str, day: str, end_day: str | None) -> None:
    try:
        start = date(year, _MONTHS[month.lower()], int(day))
        end = date(year, start.month, int(end_day)) if end_day else None
    except ValueError:
        return
    add(_dated(year, start, end))


def _dated(year: int, start: date, end: date | None = None) -> dict:
    entry = {"year": year, "date": start.isoformat()}
    if end and end > start:
        entry["end_date"] = end.isoformat()
    return entry


def records(date_specific, on: date | None = None) -> list[dict]:
    """The editions a ``date_specific`` string states as fact, newest first.

    A confirmed date ("2027: June 5", or a second "; 2026: June 13" segment),
    "CANCELLED for 2026", "no 2026 edition" and "last held July 28, 2024".
    Estimates, TBDs and month-only dates record nothing.
    """
    raw = "" if date_specific is None else str(date_specific).strip()
    found: dict[int, dict] = {}

    def add(entry):
        found.setdefault(entry["year"], entry)

    for segment in _SEGMENT.split(raw):
        # A trailing "; 2027 pattern ~Aug 7" is about another year: only the
        # clause before the first ";" says whether this date is an estimate.
        head = segment.split(";", 1)[0]
        ed = parse_edition(segment)
        if ed.date and not ed.status_note and not _UNSURE.search(head):
            add(_dated(ed.year, ed.date, ed.end_date))
    for pattern in (_CANCELLED, _CANCELLED_EDITION):
        for m in pattern.finditer(raw):
            found[int(m.group(1))] = {"year": int(m.group(1)), "status": "cancelled"}
    for m in _NOT_HELD.finditer(raw):
        for year in re.findall(r"20\d{2}", m.group(0)):
            add({"year": int(year), "status": "not_held"})
    for m in _LAST_HELD.finditer(raw):
        _add_day(add, int(m.group(4)), m.group(1), m.group(2), m.group(3))
    for m in _EDITION_RAN.finditer(raw):
        _add_day(add, int(m.group(1)), m.group(2), m.group(3), m.group(4))
    return [found[y] for y in sorted(found, reverse=True)]


def merge(primary, secondary) -> list[dict]:
    """One entry per year, newest first. ``primary`` wins; ``secondary`` fills gaps."""
    by_year: dict[int, dict] = {}
    for entry in list(primary or []) + list(secondary or []):
        year = entry.get("year")
        if not isinstance(year, int):
            continue
        current = by_year.setdefault(year, {})
        for key in FIELDS:
            if key in entry and entry[key] not in (None, "") and key not in current:
                current[key] = entry[key]
    ordered = []
    for year in sorted(by_year, reverse=True):
        entry = by_year[year]
        if entry.get("status") and "date" not in entry:
            entry.pop("end_date", None)
        ordered.append({k: entry[k] for k in FIELDS if k in entry})
    return ordered


def _place_editions(race: dict, editions: list[dict]) -> None:
    """Store ``editions`` on ``race`` right after ``history`` (in place)."""
    if "editions" in race or "history" not in race:
        race["editions"] = editions
        return
    items = list(race.items())
    race.clear()
    for key, value in items:
        race[key] = value
        if key == "history":
            race["editions"] = editions


def set_date_specific(race: dict, value: str, on: date | None = None) -> list[dict]:
    """Write ``vitals.date_specific`` after moving the old value's editions into history.

    ``race`` is the profile's ``race`` dict. Old records for a year the new value
    also covers are corrections and are dropped. A dated record is kept only once
    its date has passed, so a moved-up future date never shows as a past edition.
    Returns the entries added to ``race["editions"]``.
    """
    on = on or today()
    vitals = race.setdefault("vitals", {})
    old = vitals.get("date_specific")
    new_years = {r["year"] for r in records(value, on)}
    if parse_edition(value).year:
        new_years.add(parse_edition(value).year)
    kept = [r for r in records(old, on)
            if r["year"] not in new_years
            and (r.get("status") or date.fromisoformat(r["date"]) < on)]
    existing = race.get("editions") or []
    known = {e.get("year") for e in existing}
    added = [r for r in kept if r["year"] not in known]
    if kept:
        _place_editions(race, merge(existing, kept))
    vitals["date_specific"] = value
    return added


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def rows(race: dict, on: date | None = None) -> list[dict]:
    """What the Editions table shows: the stored history plus the current date."""
    current = records((race.get("vitals") or {}).get("date_specific"), on)
    return merge(current, race.get("editions") or [])


def problems(race: dict) -> list[str]:
    """Schema problems in ``race.editions`` (empty when it is valid)."""
    editions = race.get("editions")
    if editions is None:
        return []
    if not isinstance(editions, list):
        return ["editions is not a list"]
    out = []
    years = []
    current = {r["year"]: r for r in
               records((race.get("vitals") or {}).get("date_specific"))}
    for i, e in enumerate(editions):
        where = f"editions[{i}]"
        if not isinstance(e, dict):
            out.append(f"{where} is not an object")
            continue
        extra = set(e) - set(FIELDS)
        if extra:
            out.append(f"{where} has unknown keys {sorted(extra)}")
        year = e.get("year")
        if not isinstance(year, int) or not 1980 <= year <= 2100:
            out.append(f"{where}.year must be an integer year")
            continue
        years.append(year)
        start = None
        for key in ("date", "end_date"):
            if key in e:
                try:
                    parsed = date.fromisoformat(str(e[key]))
                except ValueError:
                    out.append(f"{where}.{key} is not YYYY-MM-DD")
                    continue
                if key == "date":
                    start = parsed
                    if parsed.year != year:
                        out.append(f"{where}.date is not in {year}")
                elif start and parsed <= start:
                    out.append(f"{where}.end_date is not after date")
        if "end_date" in e and "date" not in e:
            out.append(f"{where}.end_date without date")
        if "status" in e and e["status"] not in STATUSES:
            out.append(f"{where}.status must be one of {sorted(STATUSES)}")
        if "edition" in e and (not isinstance(e["edition"], int) or e["edition"] < 1):
            out.append(f"{where}.edition must be a positive integer")
        note = e.get("note")
        if note is not None and (not isinstance(note, str) or not note.strip()
                                 or len(note) > NOTE_MAX or "\n" in note):
            out.append(f"{where}.note must be one line of {NOTE_MAX} characters or fewer")
        source = e.get("source")
        if source is not None and not str(source).startswith("https://"):
            out.append(f"{where}.source must be an https URL")
        if not any(k in e for k in ("date", "status", "edition", "note")):
            out.append(f"{where} records nothing beyond the year")
        now = current.get(year)
        if now and ("date" in e or "status" in e):
            if e.get("date") != now.get("date") or e.get("status") != now.get("status"):
                out.append(f"{where} disagrees with date_specific for {year}; "
                           "the current edition's date lives in date_specific")
    if len(set(years)) != len(years):
        out.append("editions has two entries for one year")
    if years != sorted(years, reverse=True):
        out.append("editions is not newest first")
    return out
