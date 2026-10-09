"""Guards race-data winner fields against values that are not people.

generate_race_recap.py puts results.years[Y].winner_male / winner_female into
the recap headline, meta description, JSON-LD and Winners block. An earlier
extraction pass filled those fields with place names and section headings
("Twin Lakes" won Leadville, "Prize Money" won Gravel Earth). The sourced
corrections are in data/corrections/2026-10-09-winners.json. This test fails
if any of those values, or anything shaped like them, comes back.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = ROOT / "race-data"
CORRECTIONS = ROOT / "data" / "corrections" / "2026-10-09-winners.json"
WINNER_FIELDS = ("winner_male", "winner_female")

# Exact values that were published as race winners before 2026-10-09.
KNOWN_JUNK = {
    "Accessibility Issues", "Altitude Impact", "Community Focus",
    "Distance Options", "El Diablito", "Elevation Gain",
    "Finisher Time Limits", "Founder Information", "Franklin County Cyclists",
    "Gravel Roll", "Historical Weather Incidents", "Homegrown Gravel Adventure",
    "Jay Peak Resort", "Key Course Features", "New Race",
    "Official Recognition", "Prize Money", "Punta Arenas", "Sierra Nevada",
    "Twin Lakes", "Weather Unpredictability", "Western Grey Kangaroos",
    "Wild Gravel Trail",
}

# Words that mark a value as a place, a feature or a heading, not a person.
NOT_A_PERSON_WORDS = {
    "accessibility", "adventure", "altitude", "community", "county", "course",
    "cyclists", "distance", "elevation", "features", "finisher", "focus",
    "founder", "gain", "gravel", "historical", "impact", "incidents",
    "information", "issues", "kangaroos", "lakes", "limits", "money",
    "nevada", "options", "prize", "race", "recognition", "resort", "trail",
    "unpredictability", "weather",
}


def not_a_person(value):
    """Return the reason a winner value is not a person's name, or None."""
    if value in KNOWN_JUNK:
        return "known junk value"
    if re.search(r"[\d():;/]", value):
        return "contains digits or punctuation (distance/time packed into name)"
    words = {w.lower() for w in re.findall(r"[^\W\d_]+", value)}
    hit = sorted(words & NOT_A_PERSON_WORDS)
    if hit:
        return f"contains non-person word(s) {hit}"
    return None


def _winner_rows():
    rows = []
    for path in sorted(RACE_DATA.glob("*.json")):
        data = json.loads(path.read_text())
        race = data.get("race", data)
        years = (race.get("results") or {}).get("years") or {}
        for year, yd in years.items():
            if not isinstance(yd, dict):
                continue
            for field in WINNER_FIELDS:
                value = yd.get(field)
                if value:
                    rows.append((path.stem, year, field, value))
    return rows


class TestHeuristic:
    @pytest.mark.parametrize("value", sorted(KNOWN_JUNK) + [
        "Aitor Azkarraga (150mi, 7:30:06)",
        "Some Lakes Loop",
    ])
    def test_flags_non_people(self, value):
        assert not_a_person(value)

    @pytest.mark.parametrize("value", [
        "Keegan Swenson", "Mathieu van der Poel", "Petr Vakoč",
        "Torbjørn Røed", "Michael Van Den Ham", "Lauren De Crescenzo",
        "Sofia Gomez Villafane",
    ])
    def test_passes_real_names(self, value):
        assert not_a_person(value) is None

    def test_known_junk_matches_corrections_file(self):
        entries = json.loads(CORRECTIONS.read_text())["entries"]
        flagged = {
            c["old"] for e in entries for c in e["fields"].values()
            if c.get("old_class") == "not a person"
        }
        assert flagged <= KNOWN_JUNK


class TestRaceData:
    def test_no_winner_is_a_non_person(self):
        bad = [
            f"{slug} {year} {field}={value!r}: {why}"
            for slug, year, field, value in _winner_rows()
            if (why := not_a_person(value))
        ]
        assert not bad, "Winner fields hold non-people:\n" + "\n".join(bad)

    def test_same_name_is_not_both_winners(self):
        rows = {}
        for slug, year, field, value in _winner_rows():
            rows.setdefault((slug, year), {})[field] = value
        bad = [
            f"{slug} {year}: {v['winner_male']!r}"
            for (slug, year), v in rows.items()
            if v.get("winner_male") and v.get("winner_male") == v.get("winner_female")
        ]
        assert not bad, "Same person listed as men's and women's winner:\n" + "\n".join(bad)
