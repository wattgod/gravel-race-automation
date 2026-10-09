"""Guards the non-winner fields a race recap renders.

generate_race_recap.py renders results.years[Y] winners and times, plus
conditions, field_size_actual, finisher_count, dnf_rate_pct and key_takeaways.
An extraction pass filled those with other years' facts, other distances'
numbers and generic advice (unbound-200 2024 credited 2025 winner Cameron
Jones; leadville-100 2024 had 200 starters; colorado-trail-race 2024 claimed
a 25-day record). The sourced fixes are in
data/corrections/2026-10-09-recaps.json; this test fails if a verified value
drifts or if the specific junk this audit removed comes back. Fields the audit
cleared are not frozen: a later sourced value for them must pass.
"""

import copy
import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent
RACE_DATA = ROOT / "race-data"
CORRECTIONS = ROOT / "data" / "corrections" / "2026-10-09-recaps.json"
COUNT_FIELDS = ("field_size_actual", "finisher_count")
WINNER_FIELDS = ("winner_male", "winner_female")

# Exact junk that was live on recap pages before 2026-10-09: (slug, year, field, value or substring).
KNOWN_JUNK = [
    ("unbound-200", "2024", "text", "Cameron Jones"),
    ("unbound-200", "2024", "text", "In 2022 it rained"),
    ("unbound-200", "2024", "field_size_actual", 5000),
    ("leadville-100", "2024", "field_size_actual", 200),
    ("leadville-100", "2024", "text", "1538 finishers out of 1561"),
    ("colorado-trail-race", "2024", "text", "Leveika - 25 days"),
    ("barry-roubaix", "2024", "text", "end of August"),
    ("the-traka", "2024", "field_size_actual", 800),
    ("rebeccas-private-idaho", "2024", "field_size_actual", 1500),
    ("seven", "2024", "text", "receives ~600mm rain annually"),
    ("turnhout-gravel", "2024", "text", "redesigned and renewed"),
]

# Other-year text this audit removed. Checked in every recap year, since the
# extraction pass could paste it anywhere. Deliberately specific: a recap may
# legitimately mention another year ("the 2023 course") or a past winner.
OTHER_YEAR_JUNK = [
    "men’s winner (Cameron Jones) obliterated the record",
    "Leveika - 25 days",
    "In 2022 it rained as riders arrived",
    "in its 2019 debut",
    "by 2022",
    "Introduced in 2024 (though that first edition got rained out)",
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


def _junk_problems(slug, year, yd):
    out = []
    for jslug, jyear, field, junk in KNOWN_JUNK:
        if (jslug, jyear) != (slug, year):
            continue
        if field == "text":
            out += [f"{slug} {year} text is back to {junk!r}" for t in _texts(yd) if junk in t]
        elif yd.get(field) == junk:
            out.append(f"{slug} {year} {field} is back to {junk!r}")
    out += [f"{slug} {year} text has removed other-year junk {j!r}"
            for t in _texts(yd) for j in OTHER_YEAR_JUNK if j in t]
    return out


def _verified_problems(entry, yd):
    """Kept/corrected/added/trimmed values must still be there; cleared ones are free."""
    out = []
    for field, c in entry["fields"].items():
        cur = yd.get(field)
        if "items" in c:
            have = cur if isinstance(cur, list) else []
            out += [f"{entry['slug']} {entry['year']} {field}: lost verified item {it['new']!r}"
                    for it in c["items"] if it["action"] != "clear" and it["new"] not in have]
        elif c["action"] != "clear" and cur != c["new"]:
            out.append(f"{entry['slug']} {entry['year']} {field}: {cur!r} != verified {c['new']!r}")
    return out


def _count_problems(slug, year, yd):
    out = []
    for f in COUNT_FIELDS:
        v = yd.get(f)
        if v is not None and not (isinstance(v, int) and not isinstance(v, bool) and v > 0):
            out.append(f"{slug} {year} {f}={v!r}")
    starters, finishers = yd.get("field_size_actual"), yd.get("finisher_count")
    if isinstance(starters, int) and isinstance(finishers, int) and finishers > starters:
        out.append(f"{slug} {year}: {finishers} finishers > {starters} starters")
    dnf = yd.get("dnf_rate_pct")
    if dnf is not None and not (isinstance(dnf, (int, float)) and 0 <= dnf <= 100):
        out.append(f"{slug} {year} dnf_rate_pct={dnf!r}")
    return out


def _all_problems(slug, year, yd, doc):
    out = _junk_problems(slug, year, yd) + _count_problems(slug, year, yd)
    for e in doc["entries"]:
        if (e["slug"], e["year"]) == (slug, year):
            out += _verified_problems(e, yd)
    return out


@pytest.fixture(scope="module")
def doc():
    return json.loads(CORRECTIONS.read_text())


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
    def test_no_removed_other_year_text(self):
        bad = [f"{slug} {year}: {j!r}" for slug, year, yd in _recap_years()
               for t in _texts(yd) for j in OTHER_YEAR_JUNK if j in t]
        assert not bad, "Recap text has other-year junk this audit removed:\n" + "\n".join(bad)

    def test_no_duplicate_takeaways(self):
        bad = [
            f"{slug} {year}"
            for slug, year, yd in _recap_years()
            if len(set(yd.get("key_takeaways") or [])) != len(yd.get("key_takeaways") or [])
        ]
        assert not bad, "Duplicate key_takeaways:\n" + "\n".join(bad)

    def test_counts_are_consistent(self):
        bad = [p for slug, year, yd in _recap_years() for p in _count_problems(slug, year, yd)]
        assert not bad, "\n".join(bad)


class TestCorrectionsFile:
    def test_race_data_keeps_verified_values(self, doc):
        """Every kept/corrected/added/trimmed value is still in race-data. Cleared fields may be refilled."""
        bad = []
        for e in doc["entries"]:
            bad += _verified_problems(e, _race(e["slug"])["results"]["years"].get(e["year"]) or {})
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
        """PUBLISH needs a verified winner plus one other verified field; a REDIRECT that meets it needs a reason."""
        bad = []
        rendered = set(doc["fields_rendered_by_recap"])
        for e in doc["entries"]:
            verified = {k for k, c in e["fields"].items() if k in rendered and c["new"] not in (None, "", [])}
            has_winner = bool(verified & set(WINNER_FIELDS))
            ok = has_winner and bool(verified - set(WINNER_FIELDS))
            if e["decision"] == "PUBLISH" and not ok:
                bad.append(f"{e['slug']} {e['year']}: PUBLISH but verified fields are {sorted(verified)}")
            if e["decision"] == "REDIRECT" and ok and not e.get("redirect_reason"):
                bad.append(f"{e['slug']} {e['year']}: meets the PUBLISH rule but REDIRECTs with no redirect_reason")
        assert not bad, "\n".join(bad)

    def test_publish_and_redirect_lists_match_entries(self, doc):
        want_pub = [{"slug": e["slug"], "year": e["year"]} for e in doc["entries"] if e["decision"] == "PUBLISH"]
        want_red = [{"slug": e["slug"], "year": e["year"]} for e in doc["entries"] if e["decision"] == "REDIRECT"]
        want_red += [{"slug": e["slug"], "year": None} for e in doc["no_results_data"]]
        assert doc["publish"] == want_pub
        assert doc["redirect"] == want_red
        assert not {(r["slug"], r["year"]) for r in doc["publish"]} & {(r["slug"], r["year"]) for r in doc["redirect"]}

    def test_uci_gravel_worlds_redirects(self, doc):
        """Recap location/distance come from vitals (the 2026 host), so past Worlds would be mislabelled."""
        years = {r["year"] for r in doc["redirect"] if r["slug"] == "uci-gravel-worlds"}
        assert years == {"2024", "2025"}
        worlds = _race("uci-gravel-worlds")["results"]["years"]
        assert worlds["2024"]["winner_male"] == "Mathieu van der Poel"
        assert worlds["2025"]["winner_female"] == "Lorena Wiebes"


class TestFutureData:
    def test_plausible_sourced_value_passes(self, doc):
        """A field this audit cleared can later take a real sourced value without tripping any guard."""
        yd = copy.deepcopy(_race("unbound-200")["results"]["years"]["2024"])
        # Hypothetical wording; the point is that a refilled cleared field and a new takeaway pass.
        yd["conditions"] = "Hot and humid, with highs near 90°F and strong south winds across the Flint Hills."
        yd["key_takeaways"] = list(yd.get("key_takeaways") or []) + [
            "Lachlan Morton beat Chad Haga by one second, the closest men's finish since 2019."
        ]
        assert _all_problems("unbound-200", "2024", yd, doc) == []

    def test_junk_still_caught(self, doc):
        yd = copy.deepcopy(_race("unbound-200")["results"]["years"]["2024"])
        yd["conditions"] = "In 2022 it rained as riders arrived, turning the next sectors to mud"
        assert _all_problems("unbound-200", "2024", yd, doc)
