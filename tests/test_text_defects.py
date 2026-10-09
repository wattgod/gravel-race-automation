"""Guards against truncated/broken race text and ALL-CAPS race names.

The detector lives in scripts/audit_text_defects.py. The last test runs it
over every race-data profile so a regenerated or re-enriched profile that
brings back a cut-off string or a shouting name fails the build.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import audit_text_defects as atd  # noqa: E402


def _profile(slug, **race):
    return {slug: {"race": {"slug": slug, **race}}}


def _results(conditions=None, takeaways=None):
    year = {"winner_male": "A Rider"}
    if conditions is not None:
        year["conditions"] = conditions
    if takeaways is not None:
        year["key_takeaways"] = takeaways
    return {"years": {"2024": year}, "latest_year": "2024"}


def _kinds(profiles):
    return sorted((d.kind, d.path) for d in atd.audit(profiles))


class TestResultsStrings:
    def test_extractor_cap_cut_mid_word_is_truncated(self):
        cut = ("If you can't arrive early, just be prepared to dial back your "
               "pace especially on the first climb, as you will go into the "
               "red more quickly at 7,000+ f")
        assert len(cut) >= atd.RESULTS_CAP_LEN
        found = _kinds(_profile("x", results=_results(takeaways=[cut])))
        assert found == [("truncated",
                          "race.results.years.2024.key_takeaways[0]")]

    def test_split_abbreviation_is_truncated(self):
        found = _kinds(_profile("x", results=_results(
            takeaways=["Date shift in prior years (e"])))
        assert found[0][0] == "truncated"

    def test_unclosed_quote_is_truncated(self):
        found = _kinds(_profile("x", results=_results(
            conditions="noted “had no problems with the altitude")))
        assert ("truncated", "race.results.years.2024.conditions") in found

    @pytest.mark.parametrize("junk", [
        "[Cyclingnews: 2024 BWR Utah Results](",
        "#### From Cara Dixon (2024 First Female Finisher)",
        "| 2024 | Justinas Leveika | 13d 2h 16m |",
        "com/news/2024/oct/14/little-sugar-mtb-race-returns-to-bentonville/",
        "- 2024: Dry, dusty conditions",
        '" implying a new event around 2024',
    ])
    def test_scrape_residue_is_broken(self, junk):
        found = _kinds(_profile("x", results=_results(takeaways=[junk])))
        assert found and found[0][0] == "broken"

    def test_leading_lowercase_fragment(self):
        found = _kinds(_profile("x", results=_results(
            takeaways=["we started the first stage"])))
        assert found == [("lowercase",
                          "race.results.years.2024.key_takeaways[0]")]

    def test_clean_results_pass(self):
        found = _kinds(_profile("x", results=_results(
            conditions="2024: Dry, dusty conditions",
            takeaways=["~60% finish rate maintained",
                       "Robin Gemperle wins in 8d 23h 59m"])))
        assert found == []


class TestSentenceFields:
    def _many(self, odd_one):
        profiles = {}
        for i in range(atd.SENTENCE_MIN_COUNT):
            profiles.update(_profile(f"r{i}", tagline="A complete line."))
        profiles.update(_profile("odd", tagline=odd_one))
        return profiles

    def test_missing_period_where_siblings_have_it(self):
        found = _kinds(self._many("Where gravel meets the sky"))
        assert found == [("unterminated", "race.tagline")]

    def test_trailing_citation_marker_counts_as_terminated(self):
        assert _kinds(self._many("A sourced line.[1][3]")) == []

    def test_placeholder_is_not_a_sentence(self):
        assert _kinds(self._many("TBD")) == []

    def test_inch_marks_are_not_open_quotes(self):
        text = 'Riders on 2.1" tyres and a 5\'9" rider both coped.'
        assert _kinds(self._many(text)) == []

    def test_quote_cut_mid_word_with_ellipsis(self, monkeypatch):
        monkeypatch.setitem(atd._SOURCE_CACHE, "odd", "")
        found = _kinds(self._many('As Jo puts it: "and the red cheerle..."'))
        assert found == [("truncated", "race.tagline")]

    def test_speakers_own_ellipsis_is_kept(self, monkeypatch):
        monkeypatch.setitem(
            atd._SOURCE_CACHE, "odd",
            'Jo: "2 hours and 26 minutes... It has been a long time"')
        assert _kinds(self._many('As Jo puts it: "2 hours and 26 minutes..."')) == []


class TestNames:
    @pytest.mark.parametrize("name", [
        "TRANSCONTINENTAL RACE", "BADLANDS", "UNBOUND Gravel XL",
        "THE EQUALIZER - Missouri State Championship",
    ])
    def test_shouting_names_flagged(self, name):
        assert atd.name_defect(name)

    @pytest.mark.parametrize("name", [
        "Transcontinental Race", "SBT GRVL", "FNLD GRVL", "UCI Gravel Worlds",
        "USA Cycling Gravel National Championships", "BWR Arizona", "WYO 131",
        "JUST.GRAVEL", "Tour de Nebraska", "3RIDES Gravel Winterberg",
    ])
    def test_acronyms_and_stylizations_allowed(self, name):
        assert atd.name_defect(name) is None


def test_race_data_has_no_text_defects():
    defects = atd.audit(atd.load_profiles())
    listing = "\n".join(
        f"{d.kind} {d.slug} {d.path}: {d.value[:100]!r}" for d in defects[:25])
    assert not defects, (
        f"{len(defects)} text defects in race-data "
        f"(run scripts/audit_text_defects.py):\n{listing}")
