"""Single source of truth for facts every generator reads off a race profile.

Before this module existed, each generator re-derived these on its own and
they drifted apart:

- discipline: most generators read only ``gravel_god_rating.discipline``.
  49 road / MTB / bikepacking profiles keep it in ``vitals.discipline``, so
  the index, homepage and rankings called them gravel.
- status: ``taking_a_break`` marked cancelled races on their own page, but
  never reached the index, so rankings kept ranking them.
- country: the homepage counted the text after the last comma of every
  location as a "region", so "CO" and "Colorado" were two regions.

Import from here; do not re-implement.
"""

from __future__ import annotations

import re
from typing import Optional

DISCIPLINE_ALIASES = {
    "mountain_bike": "mtb",
    "mountain-bike": "mtb",
    "mountain bike": "mtb",
}


def race_discipline(race: dict) -> str:
    """Discipline of a race profile (the inner ``race`` dict).

    ``gravel_god_rating.discipline`` wins, then ``vitals.discipline``, then
    "gravel".
    """
    rating = race.get("gravel_god_rating") or {}
    vitals = race.get("vitals") or {}
    raw = rating.get("discipline") or vitals.get("discipline") or "gravel"
    raw = str(raw).strip().lower()
    return DISCIPLINE_ALIASES.get(raw, raw)


# ── Status ────────────────────────────────────────────────────────────────
#
# ``taking_a_break`` ({label, line}) is the one switch that says a race is
# not running. Its page shows the note, plan sales stop, and (via the index
# ``status`` field) rankings skip it. ``date_specific`` wording alone is
# never enough to flip a race; tests require the two to agree instead.

INACTIVE_DATE_RE = re.compile(
    r"^\s*(?:status:\s*)?(?:cancel+ed|dropped|on hiatus|not organizing|"
    r"no edition confirmed|postponed)\b",
    re.IGNORECASE,
)


def race_status(race: dict) -> dict:
    """Return ``{"status": "active"|"inactive", "label": str}``."""
    note = race.get("taking_a_break") or {}
    if note:
        label = str(note.get("label") or "Not running").strip()
        return {"status": "inactive", "label": label}
    return {"status": "active", "label": ""}


def is_ranked(entry: dict) -> bool:
    """True when an index entry may appear in rankings and top-N lists."""
    return (entry.get("status") or "active") == "active"


def date_says_inactive(race: dict) -> bool:
    """True when ``vitals.date_specific`` opens with a not-running status."""
    ds = str((race.get("vitals") or {}).get("date_specific") or "")
    return bool(INACTIVE_DATE_RE.match(ds))


# ── Country ───────────────────────────────────────────────────────────────

US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT",
    "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME",
    "maryland": "MD", "massachusetts": "MA", "michigan": "MI",
    "minnesota": "MN", "mississippi": "MS", "missouri": "MO",
    "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM",
    "new york": "NY", "north carolina": "NC", "north dakota": "ND",
    "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
    "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}
US_ABBREVS = set(US_STATES.values())

# alias (lower case) -> (country, continent)
COUNTRY_ALIASES = {
    "united states": ("USA", "North America"), "usa": ("USA", "North America"),
    "puerto rico": ("Puerto Rico", "North America"),
    "canada": ("Canada", "North America"), "ontario": ("Canada", "North America"),
    "quebec": ("Canada", "North America"), "british columbia": ("Canada", "North America"),
    "alberta": ("Canada", "North America"), "manitoba": ("Canada", "North America"),
    "nova scotia": ("Canada", "North America"),
    "mexico": ("Mexico", "North America"), "coahuila": ("Mexico", "North America"),
    "united kingdom": ("UK", "Europe"), "uk": ("UK", "Europe"),
    "england": ("UK", "Europe"), "scotland": ("UK", "Europe"),
    "wales": ("UK", "Europe"), "northern ireland": ("UK", "Europe"),
    "ireland": ("Ireland", "Europe"), "iceland": ("Iceland", "Europe"),
    "spain": ("Spain", "Europe"), "catalonia": ("Spain", "Europe"),
    "andalusia": ("Spain", "Europe"), "gran canaria": ("Spain", "Europe"),
    "italy": ("Italy", "Europe"), "sardinia": ("Italy", "Europe"),
    "tuscany": ("Italy", "Europe"), "veneto": ("Italy", "Europe"),
    "france": ("France", "Europe"), "corsica": ("France", "Europe"),
    "vosges": ("France", "Europe"), "belgium": ("Belgium", "Europe"),
    "belgian": ("Belgium", "Europe"), "flanders": ("Belgium", "Europe"),
    "germany": ("Germany", "Europe"), "eifel": ("Germany", "Europe"),
    "netherlands": ("Netherlands", "Europe"), "drenthe": ("Netherlands", "Europe"),
    "switzerland": ("Switzerland", "Europe"), "austria": ("Austria", "Europe"),
    "portugal": ("Portugal", "Europe"), "poland": ("Poland", "Europe"),
    "czech republic": ("Czechia", "Europe"), "czechia": ("Czechia", "Europe"),
    "slovakia": ("Slovakia", "Europe"), "hungary": ("Hungary", "Europe"),
    "romania": ("Romania", "Europe"), "slovenia": ("Slovenia", "Europe"),
    "croatia": ("Croatia", "Europe"), "montenegro": ("Montenegro", "Europe"),
    "albania": ("Albania", "Europe"), "kosovo": ("Kosovo", "Europe"),
    "bosnia": ("Bosnia and Herzegovina", "Europe"),
    "greece": ("Greece", "Europe"), "denmark": ("Denmark", "Europe"),
    "norway": ("Norway", "Europe"), "sweden": ("Sweden", "Europe"),
    "finland": ("Finland", "Europe"), "estonia": ("Estonia", "Europe"),
    "latvia": ("Latvia", "Europe"), "lithuania": ("Lithuania", "Europe"),
    "luxembourg": ("Luxembourg", "Europe"), "monaco": ("Monaco", "Europe"),
    "turkey": ("Turkey", "Europe"),
    "australia": ("Australia", "Oceania"), "queensland": ("Australia", "Oceania"),
    "victoria": ("Australia", "Oceania"), "tasmania": ("Australia", "Oceania"),
    "new south wales": ("Australia", "Oceania"),
    "western australia": ("Australia", "Oceania"),
    "south australia": ("Australia", "Oceania"),
    "new zealand": ("New Zealand", "Oceania"),
    "colombia": ("Colombia", "South America"), "argentina": ("Argentina", "South America"),
    "chile": ("Chile", "South America"), "brazil": ("Brazil", "South America"),
    "peru": ("Peru", "South America"), "ecuador": ("Ecuador", "South America"),
    "south africa": ("South Africa", "Africa"), "morocco": ("Morocco", "Africa"),
    "kenya": ("Kenya", "Africa"), "namibia": ("Namibia", "Africa"),
    "rwanda": ("Rwanda", "Africa"), "tanzania": ("Tanzania", "Africa"),
    "japan": ("Japan", "Asia"), "thailand": ("Thailand", "Asia"),
    "china": ("China", "Asia"), "hong kong": ("Hong Kong", "Asia"),
    "hong kong, china": ("Hong Kong", "Asia"),
    "south korea": ("South Korea", "Asia"), "korea": ("South Korea", "Asia"),
    "philippines": ("Philippines", "Asia"), "malaysia": ("Malaysia", "Asia"),
    "india": ("India", "Asia"), "oman": ("Oman", "Asia"),
    "vietnam": ("Vietnam", "Asia"), "taiwan": ("Taiwan", "Asia"),
}

US_REGION = {
    "West": {"CA", "OR", "WA", "CO", "UT", "MT", "WY", "ID", "NV", "AZ", "NM", "AK", "HI"},
    "Midwest": {"KS", "NE", "IA", "IL", "IN", "OH", "MI", "WI", "MN", "MO", "OK", "ND", "SD"},
    "South": {"TX", "AR", "LA", "MS", "AL", "GA", "FL", "TN", "KY", "NC", "SC", "VA", "WV"},
    "Northeast": {"NY", "PA", "CT", "MA", "VT", "NH", "ME", "MD", "NJ", "DE", "RI", "DC"},
}


_TAIL = r"(?=\s*(?:$|[,/()]|\s+to\s|\s+border))"


def _alias_hits(text: str) -> list:
    """(start, end, country, continent) for every alias found in text."""
    hits, taken = [], []
    for alias in sorted(COUNTRY_ALIASES, key=len, reverse=True):
        for m in re.finditer(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", text):
            if any(s <= m.start() < e for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            country, continent = COUNTRY_ALIASES[alias]
            hits.append((m.start(), m.end(), country, continent))
    return hits


def _us_states(location: str) -> list:
    """(start, end, abbrev) of every US state named as a place in location.

    A state name only counts when it ends a place ("Lincoln, Nebraska",
    "Nebraska (Sandhills)", "Oregon to Yorktown"), so "Mississippi Station,
    Ontario" stays in Canada.
    """
    low = location.lower()
    hits, taken = [], []
    for name in sorted(US_STATES, key=len, reverse=True):
        for m in re.finditer(rf"(?<![a-z]){re.escape(name)}(?![a-z]){_TAIL}", low):
            if any(s <= m.start() < e for s, e in taken):
                continue
            taken.append((m.start(), m.end()))
            hits.append((m.start(), m.end(), US_STATES[name]))
    for m in re.finditer(r"(?:^|[,/(]\s*)([A-Z]{2})" + _TAIL, location):
        if m.group(1) in US_ABBREVS:
            hits.append((m.start(1), m.end(1), m.group(1)))
    return hits


def location_places(location: str) -> list:
    """Ordered, de-duplicated ``(country, continent, us_state_or_None)``."""
    if not location:
        return []
    low = location.lower()
    foreign = _alias_hits(low)
    states = _us_states(location)
    if states:
        # "Turkey, Texas": a foreign word that is really a US town name.
        state_starts = [s for s, _, _ in states]
        foreign = [
            f for f in foreign
            if f[2] == "USA" or not any(
                re.fullmatch(r",\s*", low[f[1]:s]) for s in state_starts)
        ]
        # "New Mexico" is a state, not Mexico; a US state word inside a
        # foreign alias ("New South Wales") is that alias, not a state.
        foreign = [f for f in foreign
                   if not any(a <= f[0] < b for a, b, _ in states)]
        foreign_spans = [(f[0], f[1]) for f in foreign]
        states = [st for st in states
                  if not any(a <= st[0] < b for a, b in foreign_spans)]
    hits = [(f[0], f[2], f[3], None) for f in foreign]
    hits += [(st[0], "USA", "North America", st[2]) for st in states]
    hits.sort(key=lambda h: h[0])
    out, seen = [], set()
    for _, country, continent, state in hits:
        if (country, state) in seen:
            continue
        seen.add((country, state))
        out.append((country, continent, state))
    if any(c == "USA" and st for c, _, st in out):
        out = [p for p in out if not (p[0] == "USA" and p[2] is None)]
    return out


# Territories count toward their sovereign country in country totals.
COUNT_AS = {"Hong Kong": "China", "Puerto Rico": "USA"}


def location_countries(location: str) -> list:
    """Ordered list of countries a race location touches."""
    seen, out = set(), []
    for country, _, _ in location_places(location):
        country = COUNT_AS.get(country, country)
        if country not in seen:
            seen.add(country)
            out.append(country)
    return out


def location_region(location: str) -> Optional[str]:
    """Broad region for the search filter, or None when unknown.

    US races use the four US regions; everything else uses its continent.
    """
    places = location_places(location)
    if not places:
        return "Europe" if "europe" in (location or "").lower() else None
    country, continent, state = places[0]
    if country == "USA":
        if not state:
            return None
        for region, states in US_REGION.items():
            if state in states:
                return region
        return None
    return continent


# ── Catalog size ──────────────────────────────────────────────────────────

def catalog_race_count() -> int:
    """Number of live race profiles. Public copy reads this, never a literal.

    "328 races" and "757 races" both shipped long after they stopped being
    true.
    """
    from pathlib import Path
    return len(list((Path(__file__).resolve().parent.parent / "race-data").glob("*.json")))


# The scoring system: 14 base criteria scored 1-5 (/70), plus an optional
# cultural-impact bonus. Copy that counts criteria says 14, not 15.
BASE_CRITERIA_COUNT = 14
CRITERIA_PHRASE = "14 criteria plus a cultural-impact bonus"
