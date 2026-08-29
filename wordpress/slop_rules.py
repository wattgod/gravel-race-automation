#!/usr/bin/env python3
"""Deterministic checks derived from petergyang/no-ai-slop.

The upstream skill is the editorial authority. This module turns the parts
that can be checked without guessing into a build guard. Qualitative checks
such as voice preservation, portability, and robotic rhythm still require the
upstream editorial review.

Pinned source:
    https://github.com/petergyang/no-ai-slop
    commit d30eddb9e04562234f2070b5ee63ca4649d9a05e

The upstream work is MIT licensed by Peter Yang. A vendored copy of the
license and editorial rules lives in ``vendor/no-ai-slop``.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser


RULESET_NAME = "petergyang/no-ai-slop"
RULESET_URL = "https://github.com/petergyang/no-ai-slop"
RULESET_COMMIT = "d30eddb9e04562234f2070b5ee63ca4649d9a05e"


# "Banned outright" in the upstream skill. Multiword spelling variants are
# included where a writer could otherwise bypass the same rule with a hyphen.
BANNED_PHRASES = [
    "delve",
    "foster",
    "leverage",
    "utilize",
    "facilitate",
    "empower",
    "streamline",
    "robust",
    "cutting-edge",
    "paradigm shift",
    "game changer",
    "game-changing",
    "this is huge",
    "this changes everything",
    "tapestry",
    "realm",
    "beacon",
    "multifaceted",
    "meticulous",
    "intricate",
    "paramount",
    "transformative",
    "elevate",
    "embark",
    "supercharge",
    "harness",
    "ever-evolving",
]


# Upstream says these are often empty, not always forbidden. Exact phrase
# matches are safe enough to make deterministic; context-sensitive adverbs
# ("just", "actually", etc.) remain in the human eval.
EMPTY_PHRASES = [
    "it's worth noting",
    "it is worth noting",
    "it's important to note",
    "it is important to note",
    "at the end of the day",
    "when it comes to",
    "at its core",
    "in today's world",
    "in the age of",
    "in the world of",
    "the reality is",
    "the truth is",
    "in terms of",
    "with regard to",
    "in order to",
    "going forward",
    "in this article",
    "let's dive in",
]


# Deterministic portions of the upstream "Patterns to cut" section. The label
# is kept verbatim so failures point back to a named, checkable editorial rule.
BANNED_STRUCTURES = [
    (
        r"\b(?:this|it|that|the (?:question|point|goal|answer))\s+(?:is|was)\s+not\s+[^.!?]{1,100}[.!?]\s+(?:it\s+is|it'?s|this\s+is|that\s+is|the\s+\w+\s+is)\b",
        "binary contrast",
    ),
    (r"\b(?:it'?s|this is) not just\s+[^.!?]{1,100}\bbut\b", "binary contrast"),
    (r"\bthe question isn'?t\s+[^,.!?]{1,100}[,.]\s*(?:it'?s|the answer is)", "binary contrast"),
    (
        r"(?:^|[.!?]\s+)(?:here(?:'?s| is) the thing|here(?:'?s| is) what i mean|here(?:'?s| is) what you need to know|let me be clear|i'?ll be honest|the uncomfortable truth is)\b",
        "throat-clearing opener",
    ),
    (
        r"\b(?:this is the part (?:most people|everyone) (?:skip|miss)|what (?:most people|everyone) (?:gets? wrong|miss(?:es)?)|here'?s what nobody tells you|the part everyone misses)\b",
        "faux-insight setup",
    ),
    (
        r"\b(?:the (?:detail|best part|worst part|reason|answer|secret|catch|point|problem|result)\b[^.!?\n:]{0,80}|plot twist):\s+[a-z]",
        "colon reveal",
    ),
    (r",\s*(?:highlighting|underscoring|reflecting|showcasing)\b", "superficial analysis"),
    (
        r"\b(?:stands? as a testament|marks? a pivotal moment|plays? a vital role|solidif(?:y|ies) (?:its|their) position|underscores? (?:its|the) significance)\b",
        "importance puffery",
    ),
    (
        r"\b(?:that last part matters more than it sounds|the key point is|as you can see|this distinction matters|in other words)\b",
        "interpretive metadiscourse",
    ),
    (r"\b(?:experts agree|industry reports suggest|many argue|widely regarded as|studies show)\b", "weasel attribution"),
    (r"\b(?:serves as|acts as|functions as)\s+(?:an?|the)\b", "fake-strong verb"),
    (
        r"(?:^|[.!?]\s+)not an?\s+[^.!?]{1,60}[.!?]\s+not an?\s+[^.!?]{1,60}[.!?]\s+(?:an?|the)\s+",
        "negative listing",
    ),
    (
        r"\bnot an?\s+[^,.!?]{1,50},\s*not an?\s+[^,.!?]{1,50},\s*(?:and\s+)?not an?\s+[^.!?]{1,50}",
        "negative listing",
    ),
    (r"\b(?:what if i told you|think about it:|plot twist:)\b", "rhetorical setup"),
    (r"(?:^|[.!?]\s+)(?:in conclusion|ultimately|overall),\s+", "summary-recap ending"),
]


# These upstream checks are intentionally not faked with brittle regexes.
# Reviewers and writing agents must run them from the vendored eval.
HUMAN_REVIEW_RULES = (
    "preserve the writer's point and voice",
    "portability test",
    "show rather than label importance",
    "synonym cycling",
    "dramatic fragmentation",
    "robotic rhythm",
    "fake-profound kicker",
    "formatting slop",
)


class _TextExtractor(HTMLParser):
    """Extract visible text while ignoring scripts, styles, and noscript."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self._parts.append(data)

    def get_text(self):
        return " ".join(self._parts)


def _extract_text(html: str) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    """Match a word/phrase without catching substrings such as elevation."""
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![\w-]){escaped}(?![\w-])", re.IGNORECASE)


def _finding(*, phrase: str, kind: str, match: re.Match[str] | None = None):
    finding = {"phrase": phrase, "type": kind, "ruleset": RULESET_NAME}
    if match:
        finding["match"] = match.group(0)
        finding["start"] = match.start()
    return finding


def check_text(text: str, is_html: bool = False):
    """Return deterministic no-ai-slop findings for plain text or HTML."""
    if is_html:
        text = _extract_text(text)

    findings = []
    for phrase in BANNED_PHRASES:
        match = _phrase_pattern(phrase).search(text)
        if match:
            findings.append(_finding(phrase=phrase, kind="banned_word", match=match))

    for phrase in EMPTY_PHRASES:
        match = _phrase_pattern(phrase).search(text)
        if match:
            findings.append(_finding(phrase=phrase, kind="empty_phrase", match=match))

    for pattern, label in BANNED_STRUCTURES:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            findings.append(_finding(phrase=label, kind="banned_structure", match=match))

    words = re.findall(r"\b\w+[’']?\w*\b", text)
    # A citation title such as "Gravel God Cycling — Unbound 200" uses the
    # dash as title punctuation, not prose rhythm. The upstream rule targets
    # decorative sentence cadence, so quoted spans are excluded here.
    prose_for_dash_check = re.sub(r'"[^"\n]*"|“[^”\n]*”', "", text)
    em_dash_count = prose_for_dash_check.count("—")
    max_em_dashes = 0 if len(words) <= 250 else 2
    if em_dash_count > max_em_dashes:
        findings.append({
            "phrase": "em-dash overuse",
            "type": "formatting_slop",
            "ruleset": RULESET_NAME,
            "match": "—",
            "count": em_dash_count,
            "allowed": max_em_dashes,
        })

    return findings


def clean_text(text: str):
    """Remove exact filler phrases; structural edits still need judgment.

    The old checker guessed bland replacements for hype words. The upstream
    rules require minimum effective edits that preserve voice, so this helper
    refuses to manufacture generic substitute copy.
    """
    result = text
    for phrase in sorted(EMPTY_PHRASES, key=len, reverse=True):
        result = _phrase_pattern(phrase).sub("", result)
    result = re.sub(r"[ \t]{2,}", " ", result)
    result = re.sub(r"^ +", "", result, flags=re.MULTILINE)
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)
    return result.strip()
