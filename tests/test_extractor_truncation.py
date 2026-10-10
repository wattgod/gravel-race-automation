"""Extractors never cut rendered text mid-word or mid-sentence.

PR #448 restored 119 race-data strings that scripts/extract_results.py and
scripts/extract_quotes.py had cut with length caps ("...at 7,000+ f", rider
quotes cut at 200 chars with an invented "..."). These tests feed the
extractors long fixtures and fail if any output is a cut fragment, so the
next extraction run cannot re-truncate. scripts/audit_text_defects.py is the
same check over committed race-data (tests/test_text_defects.py and CI).
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import audit_text_defects as atd  # noqa: E402
import extract_quotes as eq  # noqa: E402
import extract_results as er  # noqa: E402
import text_trim  # noqa: E402
from community_parser import _truncate_at_sentence  # noqa: E402

TERMINAL = (".", "!", "?", '"', "”", ")")

LONG_TAKEAWAY = (
    "If you can't arrive early, just be prepared to dial back your pace "
    "especially on the first climb, as you will go into the red more quickly "
    "at 7,000+ ft and the 2024 field was the largest field ever at the start."
)
LONG_CONDITIONS = (
    "The 2024 race was run in brutal heat and strong crosswinds, with "
    "temperatures near 98F by midday, dust hanging over every sector of the "
    "course, and riders reporting that the wind on the exposed ridges made the "
    "final 40 miles slower than any edition before it."
)


def _assert_whole(text, source):
    """text is a complete sentence copied whole from source."""
    assert text, "empty output"
    assert text.endswith(TERMINAL), f"no terminal punctuation: {text!r}"
    assert "…" not in text and not text.endswith("..."), text
    norm = re.sub(r"\s+", " ", re.sub(r"\*+", "", source))
    idx = norm.find(text)
    assert idx >= 0, f"not verbatim from source: {text!r}"
    after = norm[idx + len(text):idx + len(text) + 1]
    assert after in ("", " "), f"cut mid-word before {after!r}: {text!r}"
    assert atd._truncation(text, results=True) is None, text


class TestTextTrim:
    def test_split_keeps_abbreviations_decimals_and_urls(self):
        text = ("Bring 2.5 in tires (e.g. Vittoria Terreno) for St. George. "
                "See https://example.com/a.b for the route. Done!")
        assert text_trim.split_sentences(text) == [
            "Bring 2.5 in tires (e.g. Vittoria Terreno) for St. George.",
            "See https://example.com/a.b for the route.",
            "Done!",
        ]

    def test_trim_keeps_whole_sentences(self):
        text = "First sentence here. Second one is here. Third runs long."
        assert text_trim.trim_to_sentence(text, 45) == (
            "First sentence here. Second one is here.")

    def test_trim_falls_back_to_clause(self):
        assert text_trim.trim_to_sentence(LONG_TAKEAWAY, 60) == (
            "If you can't arrive early")

    def test_trim_falls_back_to_whole_words(self):
        text = "one two three four five six seven eight nine ten"
        out = text_trim.trim_to_sentence(text, 22)
        assert out == "one two three four"

    def test_trim_never_cuts_a_single_word(self):
        assert text_trim.trim_to_sentence("x" * 50, 10) == ""

    @pytest.mark.parametrize("limit", range(5, len(LONG_CONDITIONS) + 5, 7))
    def test_trim_never_cuts_mid_word_at_any_limit(self, limit):
        out = text_trim.trim_to_sentence(LONG_CONDITIONS, limit)
        assert len(out) <= limit
        assert "..." not in out and "…" not in out
        if out and out != LONG_CONDITIONS:
            nxt = LONG_CONDITIONS[len(out):len(out) + 1]
            assert nxt in (" ", ",", ";", ":", ""), (limit, out)

    def test_community_hint_trim_never_adds_ellipsis(self):
        out = _truncate_at_sentence(LONG_CONDITIONS, 100)
        assert out == ("The 2024 race was run in brutal heat and strong "
                       "crosswinds, with temperatures near 98F by midday")


class TestExtractResults:
    def test_long_takeaway_kept_whole(self):
        dump = f"- **{LONG_TAKEAWAY}** Next sentence is unrelated."
        out = er.extract_key_takeaways(dump, "x", 2024)
        assert out == [LONG_TAKEAWAY]
        _assert_whole(out[0], dump)

    def test_long_conditions_kept_whole(self):
        dump = f"{LONG_CONDITIONS} Field size was 900 riders."
        out = er.extract_conditions(dump, "x", 2024)
        assert out == LONG_CONDITIONS
        _assert_whole(out, dump)

    def test_abbreviation_does_not_split_takeaway(self):
        dump = ("2024: Riders set a new course record despite mud "
                "(e.g. the Teterville climb was unrideable).")
        out = er.extract_key_takeaways(dump, "x", 2024)
        assert out == ["2024: Riders set a new course record despite mud "
                       "(e.g. the Teterville climb was unrideable)."]

    def test_markdown_and_urls_stripped_without_breaking_sentence(self):
        dump = ("- **2024:** Cameron Jones set a new course record in 8:34 "
                "([Cyclingnews](https://www.cyclingnews.com/a.b/c)) "
                "https://x.com/y.z [3]. Later riders struggled.")
        out = er.extract_key_takeaways(dump, "x", 2024)
        assert out == ["2024: Cameron Jones set a new course record in 8:34 "
                       "(Cyclingnews)."]
        assert not re.search(r"https?://|\]\(|\[\d+\]|\*", out[0])

    def test_fragments_are_dropped_not_cut(self):
        dump = "\n".join([
            "| 2024 | Justinas Leveika | new record 13d 2h |",
            "2024: " + "a new record " * 40 + "was set.",
        ])
        assert er.extract_key_takeaways(dump, "x", 2024) == []

    def test_long_unpunctuated_bullet_is_dropped(self):
        # Indistinguishable from a cut string; the audit would fail CI on it.
        line = ("- 2025 conditions: riders experienced pouring rain and "
                "temperatures near zero at Fort de l'Olive, requiring fleece "
                "blankets at the feed zone before the final climb of the day")
        assert er.extract_conditions(line, "x", 2025) == ""
        short = "- 2024: Dry, dusty conditions with a hot, windy finish"
        assert er.extract_conditions(short, "x", 2024) == (
            "2024: Dry, dusty conditions with a hot, windy finish")

    def test_generated_long_fixtures_never_truncate(self):
        words = ("gravel", "headwind", "record", "climb", "7,000+", "ft",
                 "riders", "dusty", "first", "Flint", "Hills", "mud")
        for n in range(10, 60, 3):
            body = " ".join(words[i % len(words)] for i in range(n))
            sent = f"The 2024 race set a new record in dry, dusty heat: {body}."
            dump = f"{sent} Another sentence follows."
            takeaways = er.extract_key_takeaways(dump, "x", 2024)
            cond = er.extract_conditions(dump, "x", 2024)
            for out in takeaways + ([cond] if cond else []):
                _assert_whole(out, dump)


class TestExtractQuotes:
    LONG_QUOTE = (
        "The second half of the course is where the race really starts, "
        "because the gravel turns to chunky limestone, the climbs stack up "
        "one after another, and if you went out too hard in the opening "
        "miles you will pay for it with interest on every single one of them "
        "until the finish line, and the last climb out of the river valley "
        "is the one that decides it"
    )
    SHORT_QUOTE = ("Brutal climbs and loose gravel on every steep descent, "
                   "with 9,000 ft of gain.")

    def _dump(self):
        return (f'**Jo Rider [ELITE]:** "{self.LONG_QUOTE}" (https://x.com)\n'
                f'**Sam Racer [COMPETITIVE]:** "{self.SHORT_QUOTE}" '
                "(https://y.com)\n")

    def test_long_quote_extracted_verbatim(self):
        assert len(self.LONG_QUOTE) > 300
        quotes = eq.extract_quotes_from_dump(self._dump())
        by_rider = {q["rider"]: q["quote"] for q in quotes}
        assert by_rider["Jo Rider"] == self.LONG_QUOTE
        assert by_rider["Sam Racer"] == self.SHORT_QUOTE

    def test_injection_skips_quotes_too_long_to_fit_whole(self):
        quotes = eq.extract_quotes_from_dump(self._dump())
        best = eq.pick_best_quote(quotes, "elevation", "")
        assert best["quote"] == self.SHORT_QUOTE
        only_long = [q for q in quotes if q["rider"] == "Jo Rider"]
        assert eq.pick_best_quote(only_long, "elevation", "") is None

    def test_no_quote_ever_gains_an_ellipsis(self):
        for q in eq.extract_quotes_from_dump(self._dump()):
            assert q["quote"] in self._dump()
            assert not q["quote"].endswith("...")
