"""Guards the non-winner fields a race recap renders.

generate_race_recap.py renders results.years[Y] winners and times, plus
conditions, field_size_actual, finisher_count, dnf_rate_pct and key_takeaways.
An extraction pass filled those with other years' facts, other distances'
numbers and generic advice (unbound-200 2024 credited 2025 winner Cameron
Jones; leadville-100 2024 had 200 starters; colorado-trail-race 2024 claimed
a 25-day record). The sourced fixes are in
data/corrections/2026-10-09-recaps.json; this test fails if race-data drifts
from them or if the same kinds of junk come back in any recap year.
"""

import json
import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = ROOT / "race-data"
CORRECTIONS = ROOT / "data" / "corrections" / "2026-10-09-recaps.json"
COUNT_FIELDS = ("field_size_actual", "finisher_count")
YEAR = re.compile(r"\b(19\d\d|20[0-3]\d)\b")

# Exact junk that was live on recap pages before 2026-10-09: (slug, year, field, value or substring).
KNOWN_JUNK = [
    ("unbound-200", "2024", "text", "Cameron Jones"),
    ("unbound-200", "2024", "text", "In 2022 it rained"),
    ("unbound-200", "2024", "field_size_actual", 5000),
    ("leadville-100", "2024", "field_size_actual", 200),
    ("leadville-100", "2024", "text", "1538 finishers out of 1561"),
    ("colorado-trail-race", "2024", "text", "Justinas Leveika"),
    ("colorado-trail-race", "2024", "text", "25 days"),
    ("barry-roubaix", "2024", "text", "end of August"),
    ("the-traka", "2024", "text", "360K"),
    ("the-traka", "2024", "field_size_actual", 800),
    ("rebeccas-private-idaho", "2024", "field_size_actual", 1500),
    ("seven", "2024", "text", "receives ~600mm rain annually"),
    ("turnhout-gravel", "2024", "text", "redesigned and renewed"),
]


def _race(slug):
    data = json.loads((RACE_DATA / f"{slug}.json").read_text())
    return data.get("race", data)


def _texts(yd):
    takeaways = yd.get("key_takeaways") or []
    return [yd.get("conditions") or ""] + [t for t in takeaways if isinstance(t, str)]


def _recap_years():
    """Every slug-year the recap generator would render (it needs a winner)."""
    rows = []
    for path in sorted(RACE_DATA.glob("*.json")):
        data = json.loads(path.read_text())
        race = data.get("race", data)
        years = (race.get("results") or {}).get("years") or {}
        for year, yd in years.items():
            if isinstance(yd, dict) and (yd.get("winner_male") or yd.get("winner_female")):
                rows.append((path.stem, str(year), yd))
    return rows


class TestKnownJunk:
    @pytest.mark.parametrize("slug,year,field,junk", KNOWN_JUNK)
    def test_junk_does_not_return(self, slug, year, field, junk):
        yd = _race(slug)["results"]["years"].get(year) or {}
        if field == "text":
            hits = [t for t in _texts(yd) if junk in t]
            assert not hits, f"{slug} {year} recap text is back to {junk!r}: {hits}"
        else:
            assert yd.get(field) != junk, f"{slug} {year} {field} is back to {junk!r}"


class TestRecapYears:
    def test_text_names_no_other_year(self):
        bad = [
            f"{slug} {year}: {t[:90]!r}"
            for slug, year, yd in _recap_years()
            for t in _texts(yd)
            if any(y != year for y in YEAR.findall(t))
        ]
        assert not bad, "Recap conditions/takeaways describe another year:\n" + "\n".join(bad)

    def test_no_duplicate_takeaways(self):
        bad = [
            f"{slug} {year}"
            for slug, year, yd in _recap_years()
            if len(set(yd.get("key_takeaways") or [])) != len(yd.get("key_takeaways") or [])
        ]
        assert not bad, "Duplicate key_takeaways:\n" + "\n".join(bad)

    def test_text_names_no_winner_of_another_year(self):
        bad = []
        for slug, year, yd in _recap_years():
            years = _race(slug)["results"]["years"]
            own = {yd.get("winner_male"), yd.get("winner_female")}
            others = {
                v for y, d in years.items() if str(y) != year and isinstance(d, dict)
                for k, v in d.items() if k in ("winner_male", "winner_female") and v and v not in own
            }
            bad += [f"{slug} {year}: names {w!r}" for w in others for t in _texts(yd) if w in t]
        assert not bad, "Recap text credits another year's winner:\n" + "\n".join(bad)

    def test_counts_are_consistent(self):
        bad = []
        for slug, year, yd in _recap_years():
            for f in COUNT_FIELDS:
                v = yd.get(f)
                if v is not None and not (isinstance(v, int) and not isinstance(v, bool) and v > 0):
                    bad.append(f"{slug} {year} {f}={v!r}")
            starters, finishers = yd.get("field_size_actual"), yd.get("finisher_count")
            if isinstance(starters, int) and isinstance(finishers, int) and finishers > starters:
                bad.append(f"{slug} {year}: {finishers} finishers > {starters} starters")
            dnf = yd.get("dnf_rate_pct")
            if dnf is not None and not (isinstance(dnf, (int, float)) and 0 <= dnf <= 100):
                bad.append(f"{slug} {year} dnf_rate_pct={dnf!r}")
        assert not bad, "\n".join(bad)


class TestCorrectionsFile:
    @pytest.fixture(scope="class")
    def doc(self):
        return json.loads(CORRECTIONS.read_text())

    def test_race_data_matches_verified_values(self, doc):
        """Every verified field still holds the sourced value (or stays cleared)."""
        bad = []
        for e in doc["entries"]:
            yd = _race(e["slug"])["results"]["years"].get(e["year"]) or {}
            for field, c in e["fields"].items():
                cur = yd.get(field)
                want = c["new"]
                if cur in ("", []):
                    cur = None
                if cur != want:
                    bad.append(f"{e['slug']} {e['year']} {field}: {cur!r} != verified {want!r}")
        assert not bad, "race-data drifted from the verified recap values:\n" + "\n".join(bad)

    def test_every_value_is_sourced(self, doc):
        bad = []
        for e in doc["entries"]:
            for field, c in e["fields"].items():
                for item in c.get("items", [c]):
                    for url in item.get("sources", []):
                        u = urlparse(url)
                        if u.scheme not in ("http", "https") or not u.netloc:
                            bad.append(f"{e['slug']} {e['year']} {field}: bad url {url!r}")
                    if item.get("new") not in (None, []) and item["action"] != "keep" and not item.get("sources"):
                        bad.append(f"{e['slug']} {e['year']} {field}: {item['action']} with no source")
                    if item.get("new") not in (None, []) and item["action"] == "keep" and not item.get("sources"):
                        bad.append(f"{e['slug']} {e['year']} {field}: kept with no source")
                    if item["action"] == "clear" and not item.get("note"):
                        bad.append(f"{e['slug']} {e['year']} {field}: cleared with no reason")
        assert not bad, "\n".join(bad)

    def test_publish_rule(self, doc):
        """PUBLISH needs a verified winner plus at least one other verified field."""
        bad = []
        for e in doc["entries"]:
            yd = _race(e["slug"])["results"]["years"].get(e["year"]) or {}
            has_winner = bool(yd.get("winner_male") or yd.get("winner_female"))
            others = [k for k, v in yd.items()
                      if k not in ("winner_male", "winner_female") and k in e["fields"] and v not in (None, "", [])]
            ok = has_winner and bool(others)
            if (e["decision"] == "PUBLISH") != ok:
                bad.append(f"{e['slug']} {e['year']}: decision {e['decision']} but winner={has_winner} others={others}")
        assert not bad, "\n".join(bad)
