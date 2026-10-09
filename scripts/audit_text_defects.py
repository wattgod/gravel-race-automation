#!/usr/bin/env python3
"""
Detect text defects in race profiles that leak onto live pages.

Defect classes:
  truncated    String cut off mid-word or mid-clause: unbalanced brackets or
               quotes, a dangling "(e" from a split "e.g.", or a results string
               that stops at the old extractor's length cap without terminal
               punctuation.
  broken       Scrape residue in results strings: markdown link/heading/table
               fragments, bare URL tails, leading bullet markers, trailing
               "[Source] (" stubs.
  unterminated A sentence field (one where >= 80% of the same field across all
               profiles ends in terminal punctuation) that does not.
  lowercase    A sentence field or results string that starts with a lowercase
               letter.
  allcaps_name race.name / race.display_name with an ALL-CAPS word that is not
               an acronym or the event's official stylization.

Usage:
  python scripts/audit_text_defects.py            # counts + every defect
  python scripts/audit_text_defects.py --summary  # counts only
  python scripts/audit_text_defects.py --json     # machine-readable
  python scripts/audit_text_defects.py --fail     # exit 1 if any defect
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"
RESEARCH_DIR = Path(__file__).resolve().parent.parent / "research-dumps"

TERMINAL = (".", "!", "?", "…", '"', "”", "’", "'", ")")
CITATION_TAIL = re.compile(r"(\s*\[\d+\])+\s*$")

# Field groups with at least this many non-empty values, and at least this
# share ending in terminal punctuation, are treated as sentence fields.
SENTENCE_MIN_COUNT = 20
SENTENCE_MIN_SHARE = 0.80

# Third-party or machine text: video titles/descriptions/transcripts, citation
# snippets, photo alt text, verbatim quotes, URLs, research notes. These are
# not house copy and are never "fixed" by this audit.
EXCLUDED_PATH = re.compile(
    r"youtube_data\.videos|citations|photos|unsplash|transcript|search_query"
    r"|url|research_metadata|\.quotes\[\]|additional_quotes"
)

RESULTS_PATH = re.compile(
    r"^race\.results\.years\.Y\.(conditions|key_takeaways\[\])$"
)

# scripts/extract_results.py capped takeaways at 150 chars and conditions
# at 200. A results string this long with no terminal punctuation was cut.
RESULTS_CAP_LEN = 140

# Tokens that are legitimately all caps inside race names: acronyms and
# official event stylizations (checked against each event's own branding).
NAME_CAPS_ALLOWED = {
    "UCI", "BWR", "USA", "US", "UK", "XL", "MTB", "NYC", "GFNY", "SBT", "GRVL",
    "RADL", "MAAP", "HYSK", "FNLD", "CIRREM", "BURGR", "GRUSK", "3RIDES",
    "JUST.GRAVEL", "KOM", "DK", "LTGP", "RPI", "GP", "TT", "OMG", "RVO", "TAR",
    "UEC", "WYO",
}

# (slug, field path) pairs reviewed and kept on purpose.
EXCEPTIONS: dict[tuple[str, str], str] = {
    # Lowercase usernames quoted as the subject of the sentence.
    ("eislek-gravel", "race.biased_opinion_ratings.community.explanation"):
        "starts with the forum handle eins4eins",
    ("cow-pie-classic", "race.biased_opinion_ratings.field_depth.explanation"):
        "starts with the forum handle aarondeutchman",
    ("cow-pie-classic", "race.biased_opinion_ratings.race_quality.explanation"):
        "starts with the forum handle aarono",
    ("gravel-unravel-why-not-chee",
     "race.biased_opinion_ratings.field_depth.explanation"):
        "starts with the forum handle broshaughnessy",
    ("gravel-unravel-why-not-chee",
     "race.biased_opinion_ratings.prestige.explanation"):
        "starts with the forum handle broshaughnessy",
    # Exact string pinned by tests/test_red_granite_grinder_2026.py.
    ("red-granite-grinder", "race.terrain.surface"):
        "value pinned verbatim by its own regression test",
    # Internal key=value scoring note, not rendered as prose.
    ("transcontinental-race", "race.gravel_god_rating.score_note"):
        "key=value scoring note",
}

# Placeholders that are not sentences and should not get a period.
PLACEHOLDERS = {"TBD", "TBA", "N/A"}

BROKEN_PATTERNS = [
    (re.compile(r"\]\(\s*$|\]\s*\(\s*$"), "markdown link stub"),
    (re.compile(r"\[[^\]]*$"), "unclosed markdown bracket"),
    (re.compile(r"^\s*#+\s"), "markdown heading"),
    (re.compile(r"^\s*\||\|\s*$"), "markdown table row"),
    (re.compile(r"^\s*(?:com|org|net)/"), "URL tail"),
    (re.compile(r"https?://"), "bare URL"),
    (re.compile(r"^\s*[-•*]\s|^\s*•"), "leading bullet marker"),
    (re.compile(r"^\s*(?:[)\]”,;:.]|\"\s)"),
     "starts mid-sentence on punctuation"),
]


@dataclass
class Defect:
    slug: str
    path: str
    kind: str
    detail: str
    value: str


def _walk(obj, path, gpath):
    """Yield (concrete path, group path, string) for every string leaf."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            gkey = "Y" if re.fullmatch(r"\d{4}", str(key)) else key
            yield from _walk(val, f"{path}.{key}", f"{gpath}.{gkey}")
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            yield from _walk(val, f"{path}[{i}]", f"{gpath}[]")
    elif isinstance(obj, str):
        yield path.lstrip("."), gpath.lstrip("."), obj


def _strip_tail(text: str) -> str:
    return CITATION_TAIL.sub("", text.strip())


def _ends_terminal(text: str) -> bool:
    return _strip_tail(text).endswith(TERMINAL)


def _starts_lowercase(text: str) -> bool:
    m = re.match(r"[\s\"“‘'(]*([A-Za-z])", text)
    return bool(m and m.group(1).islower())


INCH_MARK = re.compile(
    r"(?<=\d)[\"”](?=\s+(?:tires?|tyres?|wheel\w*|rider|rims?|travel)\b)")
ELLIPSIS_CUT = re.compile(r"\w(?:\.\.\.|…)[\"”]?$")


def _unbalanced(text: str) -> str | None:
    text = INCH_MARK.sub("in", text)  # 2.1" tyres, 5'9" rider
    if text.count("(") > text.count(")"):
        return "unclosed ("
    if text.count("[") > text.count("]"):
        return "unclosed ["
    if text.count("“") > text.count("”"):
        return "unclosed “"
    if text.count('"') % 2 == 1:
        return 'unclosed "'
    return None


_SOURCE_CACHE: dict[str, str] = {}


def _source_text(slug: str) -> str:
    """Whitespace-normalized research dumps for a slug (primary sources)."""
    if slug not in _SOURCE_CACHE:
        parts = [p.read_text(encoding="utf-8", errors="replace")
                 for p in sorted(RESEARCH_DIR.glob(f"{slug}-*.md"))]
        _SOURCE_CACHE[slug] = re.sub(r"\s+", " ", "\n".join(parts))
    return _SOURCE_CACHE[slug]


def _ellipsis_is_verbatim(slug: str, text: str) -> bool:
    """True when the ellipsis is the speaker's own, as written in the source.

    scripts/extract_quotes.py cut quotes at 200 chars and appended "...",
    often mid-word. A quote whose last words *including* the ellipsis appear
    verbatim in the research dump was elided by the speaker, not by us.
    """
    quote = re.split(r'["“]', text.rstrip('"”'))[-1]
    tail = re.sub(r"\s+", " ", quote)[-40:]
    return bool(tail) and tail in _source_text(slug)


def _truncation(text: str, results: bool, slug: str = "") -> str | None:
    core = _strip_tail(text)
    if re.search(r"\(e$|\be\.g$|\bi\.e$", core):
        return "split abbreviation"
    if ELLIPSIS_CUT.search(core) and not _ellipsis_is_verbatim(slug, core):
        return "quote cut with ellipsis"
    reason = _unbalanced(core)
    if reason:
        return reason
    if results and len(core) >= RESULTS_CAP_LEN and not core.endswith(TERMINAL):
        return f"cut at extractor cap ({len(core)} chars)"
    return None


def name_defect(name: str) -> str | None:
    """Return the offending ALL-CAPS words of a race name, if any."""
    bad = []
    for tok in name.split():
        word = tok.strip("-–—,:;()")
        letters = re.sub(r"[^A-Za-z]", "", word)
        if len(letters) < 3 or not letters.isupper():
            continue
        if word in NAME_CAPS_ALLOWED or word.rstrip(".") in NAME_CAPS_ALLOWED:
            continue
        bad.append(word)
    return " ".join(bad) if bad else None


def load_profiles(data_dir: Path = RACE_DATA_DIR) -> dict[str, dict]:
    profiles = {}
    for path in sorted(data_dir.glob("*.json")):
        profiles[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return profiles


def sentence_groups(profiles: dict[str, dict]) -> set[str]:
    counts = collections.Counter()
    terminal = collections.Counter()
    for data in profiles.values():
        for _, gpath, text in _walk(data, "", ""):
            if not text.strip() or EXCLUDED_PATH.search(gpath):
                continue
            counts[gpath] += 1
            terminal[gpath] += _ends_terminal(text)
    return {
        g for g, n in counts.items()
        if n >= SENTENCE_MIN_COUNT and terminal[g] / n >= SENTENCE_MIN_SHARE
    }


def audit(profiles: dict[str, dict]) -> list[Defect]:
    groups = sentence_groups(profiles)
    defects: list[Defect] = []

    def add(slug, path, kind, detail, value):
        if (slug, path) in EXCEPTIONS:
            return
        defects.append(Defect(slug, path, kind, detail, value))

    for slug, data in profiles.items():
        race = data.get("race", {})
        for key in ("name", "display_name"):
            val = race.get(key)
            if isinstance(val, str):
                bad = name_defect(val)
                if bad:
                    add(slug, f"race.{key}", "allcaps_name", bad, val)

        for path, gpath, text in _walk(data, "", ""):
            if not text.strip():
                continue
            is_results = bool(RESULTS_PATH.match(gpath))
            if not is_results and gpath not in groups:
                continue
            if is_results:
                for pattern, label in BROKEN_PATTERNS:
                    if pattern.search(text):
                        add(slug, path, "broken", label, text)
                        break
                else:
                    reason = _truncation(text, results=True, slug=slug)
                    if reason:
                        add(slug, path, "truncated", reason, text)
                    elif _starts_lowercase(text):
                        add(slug, path, "lowercase", "leading lowercase", text)
                continue
            reason = _truncation(text, results=False, slug=slug)
            if reason:
                add(slug, path, "truncated", reason, text)
            elif not _ends_terminal(text) and text.strip() not in PLACEHOLDERS:
                add(slug, path, "unterminated",
                    "no terminal punctuation; siblings have it", text)
            if _starts_lowercase(text):
                add(slug, path, "lowercase", "leading lowercase", text)
    return defects


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail", action="store_true",
                    help="exit 1 when any defect remains")
    args = ap.parse_args(argv)

    defects = audit(load_profiles())
    counts = collections.Counter(d.kind for d in defects)
    if args.json:
        print(json.dumps([asdict(d) for d in defects], indent=2,
                         ensure_ascii=False))
    else:
        if not args.summary:
            for d in defects:
                print(f"{d.kind:13s} {d.slug} {d.path} [{d.detail}] "
                      f"{d.value[:160]!r}")
        print("\nText defects by class:")
        for kind in ("truncated", "broken", "unterminated", "lowercase",
                     "allcaps_name"):
            print(f"  {kind:13s} {counts.get(kind, 0)}")
        print(f"  {'total':13s} {len(defects)}")
        print(f"  exceptions    {len(EXCEPTIONS)} (reviewed, kept on purpose)")
    return 1 if (args.fail and defects) else 0


if __name__ == "__main__":
    sys.exit(main())
