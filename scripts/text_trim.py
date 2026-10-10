"""Sentence-aware splitting and trimming for extracted text.

The extractors used to cut text with raw slices (`text[:200]`) or split on
every period, which shipped strings like "...at 7,000+ f" and "(e" (a split
"e.g."). Everything that extracts or trims prose for race-data goes through
here instead:

  split_sentences(text)        sentences with their own terminal punctuation;
                               no split inside "e.g.", "St.", "2.5", URLs.
  trim_to_sentence(text, n)    the longest run of whole sentences that fits
                               in n chars; failing that, the first clause;
                               failing that, whole words. Never cuts a word,
                               never adds an ellipsis.

scripts/audit_text_defects.py is the downstream check over race-data.
"""

from __future__ import annotations

import re

# Words that end in a period without ending a sentence. Lowercased, without
# the trailing period. Unit abbreviations are included where they also lead
# proper nouns ("Ft. Collins", "Mt. Hood", "St. George").
_ABBREVIATIONS = {
    "e.g", "i.e", "etc", "vs", "approx", "est", "no", "nos", "ca", "cf",
    "mt", "mtn", "st", "ste", "ft", "fr", "dr", "mr", "mrs", "ms", "jr", "sr",
    "prof", "gen", "gov", "sen", "rep", "inc", "co", "corp", "ltd", "dept",
    "ave", "rd", "hwy", "blvd", "u.s", "u.k", "a.m", "p.m",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct",
    "nov", "dec",
}

# Terminal punctuation, plus any closing quotes/brackets glued to it, followed
# by whitespace or the end of the text. A period inside "2.5" or a URL has no
# whitespace after it, so it never matches.
_BOUNDARY = re.compile(r"(?:[.!?]+|…)[\"”’'\)\]]*(?=\s|$)")
# What may start the next sentence.
_SENTENCE_START = re.compile(r"[\"“‘'(\[]?[A-Z0-9$~£€]")
_CLAUSE_BREAK = re.compile(r"\s*(?:[,;:]|\s[—–-])(?=\s)")
_TRAILING_JOINERS = re.compile(r"[\s,;:—–-]+$")


def _sentence_ends(text: str) -> list[int]:
    """Offsets just past each sentence's terminal punctuation."""
    ends = []
    for m in _BOUNDARY.finditer(text):
        rest = text[m.end():].lstrip()
        if rest and not _SENTENCE_START.match(rest):
            continue  # "...at 5 a.m. riders" / "approx. three hours"
        if m.group().startswith(".") and not m.group().startswith(".."):
            word = re.search(r"(\S+)$", text[:m.start()])
            if word:
                w = word.group(1).lower().lstrip("\"“‘'([")
                if w in _ABBREVIATIONS or re.fullmatch(r"[a-z]", w):
                    continue  # abbreviation or a single initial ("J. Smith")
        ends.append(m.end())
    return ends


def split_sentences(text: str) -> list[str]:
    """Split prose into sentences, keeping each one's punctuation."""
    out, start = [], 0
    for end in _sentence_ends(text):
        sent = text[start:end].strip()
        if sent:
            out.append(sent)
        start = end
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def trim_to_sentence(text: str, max_chars: int) -> str:
    """Trim text to at most max_chars without cutting a sentence or word.

    Keeps the longest prefix of whole sentences that fits. When even the first
    sentence is too long, keeps its longest prefix ending at a clause break
    (comma, semicolon, colon, dash); when there is none, its longest prefix of
    whole words. Returns "" rather than cut a single over-long word. Never
    appends an ellipsis.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return text

    fitting = [e for e in _sentence_ends(text) if e <= max_chars]
    if fitting:
        return text[:fitting[-1]].strip()

    window = text[:max_chars + 1]
    breaks = [m.start() for m in _CLAUSE_BREAK.finditer(window[:max_chars])]
    breaks = [b for b in breaks if b > 0]
    if breaks:
        return _TRAILING_JOINERS.sub("", text[:breaks[-1]])

    if window[-1].isspace():
        return _TRAILING_JOINERS.sub("", window)
    head = window[:-1]
    if not re.search(r"\s", head):
        return ""
    return _TRAILING_JOINERS.sub("", head.rsplit(None, 1)[0])


_INCH_MARK = re.compile(
    r"(?<=\d)[\"”](?=\s+(?:tires?|tyres?|wheel\w*|rider|rims?|travel)\b)")


def unbalanced(text: str) -> bool:
    """True when brackets or quotes open and never close (a cut fragment)."""
    text = _INCH_MARK.sub("in", text)  # 2.1" tyres, 5'9" rider
    return (
        text.count("(") != text.count(")")
        or text.count("[") != text.count("]")
        or text.count("“") != text.count("”")
        or text.count('"') % 2 == 1
    )
