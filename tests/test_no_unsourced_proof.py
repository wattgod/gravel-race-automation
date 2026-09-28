"""Guard: no unsourced social proof on the decision-point pages.

docs/specs/receipts-social-proof-2026.md §4.4. Until 2026-09-28 /about/,
/products/training-plans/ and the questionnaire carried placeholder
testimonials written by Claude sessions in Feb 2026, next to counts and
scarcity copy nobody could check. This file fails the build if any of that
comes back. The same rules run in wattgod/road-race-automation's copy of this
file; keep the two in step.

Pages come in two kinds:
  - commercial: about, coaching, consulting, training plans, questionnaire,
    homepage, guide CTA, race training-plan pages. Coach/product proof would
    live here.
  - editorial: race profiles and Gravel Weekly. They quote publications,
    organisers and riders as reporting, and race descriptions legitimately
    say things like "registration has limited spots" or "a 4.6/5 rating
    from 59 reviews".

Every page fails on:
  - a class token that starts with a legacy testimonial class, or contains
    "testimonial" at all (bar the coaching-band wrapper);
  - `aggregateRating` whose ratingCount doesn't trace to real Racer Ratings
    (3+) for that race; commercial pages have no rating source, so any;
  - a quote attribution that names a person, outside an element carrying
    data-receipt-id. Attributions are <cite>, a <footer> (the deleted
    /about/ card: <footer><strong>Firstname L.</strong>...), a <figcaption>,
    or a dash-led line ("<p>&mdash; Firstname L.</p>"). A publication or
    organisation ("— The Guardian", "Gravel Cyclist · 1.9K views") is not a
    person;
  - a data-receipt-id that does not resolve in the receipts ledger. No
    ledger exists yet, so no page may emit one.

Commercial pages also fail on:
  - any <cite> outside a receipt (a press quote is proof too);
  - scarcity ("Limited spots", "Next window", "athletes/month"), rating
    claims ("Rated 4.9/5", "4.8★", "★★★★★ (123 reviews)") and coach counts
    ("100+ athletes coached").
On editorial pages those claim checks run only inside commercial elements
(data-ab, data-cta, or a class token containing "coaching" or "cta"), so a
coaching CTA on a race page is still covered.

<blockquote> itself is not banned: race pages quote YouTube riders with a
channel <cite>, the homepage quotes race taglines, and Gravel Weekly quotes
sources.
"""
from __future__ import annotations

import functools
import html as html_lib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

COMMERCIAL = "commercial"
EDITORIAL = "editorial"

LEGACY_TESTIMONIAL_CLASSES = (
    "gg-about-testimonial",    # /about/ carousel (50 placeholders)
    "gg-tp-testimonial",       # /products/training-plans/ (3 placeholders)
    "gg-coach-testimonial",    # /coaching/ band sequence, pre-2026-07-18
    "gg-consult-testimonial",  # /consulting/, removed in copy v2
    "gg-hp-test-quote",        # homepage quote cards, pre-2026-07-18
    "gg-hp-test-card",
    "gg-trust-quote",          # questionnaire, above Submit & Pay
    "tp-testimonial",          # web/training-plans.html (legacy paste-in)
    "rl-about-testimonial",    # Roadie Labs' copies, in case of a copy-over
    "rl-tp-testimonial",
    "rl-coach-testimonial",
    "rl-about-carousel",
    "rl-hp-test-card",
    "rl-hp-test-quote",
    "rl-hp-test-grid",
    "rl-hp-test-name",
    "rl-hp-test-attr",
)

# The homepage coaching band wrapper. It renders a sentence and a CTA, no
# quotes (owner ruling 2026-07-18: no homepage testimonials).
ALLOWED_TESTIMONIAL_CLASS_TOKENS = frozenset({"gg-hp-testimonials", "rl-hp-testimonials"})

# ── Claims nobody can check (commercial copy only) ──────────────────────

SCARCITY_STRINGS = (
    "Stars from",
    "athletes/month",
    "Next window",
    "Limited spots",
    "same coach, same plan engine",  # borrowed Gravel God caption on Roadie
)

RATING_CLAIM_PATTERNS = (
    r"\brated\s+\d(?:\.\d+)?\s*(?:/|out\s+of)\s*\d+",       # Rated 4.9/5
    r"\b\d\.\d\s*/\s*5\b",                                   # 4.9/5
    r"\b\d(?:\.\d+)?\s+out\s+of\s+5\s+stars?\b",             # 4.9 out of 5 stars
    r"\b\d(?:\.\d+)?\s*[★⭐]",                                # 4.8★
    r"[★⭐]\s*\d\.\d",                                        # ★ 4.8
    r"[★⭐]{3,}",                                             # ★★★★★
    r"\(\s*\d[\d,]*\+?\s+(?:reviews?|ratings?)\s*\)",         # (123 reviews)
    r"\b\d[\d,]*\+?\s+(?:five|5)[-\s]?star\s+(?:reviews?|ratings?)\b",
)

COUNT_PATTERNS = (
    r"\b\d[\d,]*\+?\s+(?:athletes|riders|clients)\s+coached\b",
    r"\bcoached\s+(?:over\s+|more\s+than\s+)?\d[\d,]*\+?\s+(?:athletes|riders|clients)\b",
    r"\b\d[\d,]*\+?\s+(?:training\s+)?plans\s+sold\b",
    r"\bsold\s+(?:over\s+|more\s+than\s+)?\d[\d,]*\+?\s+(?:training\s+)?plans\b",
    r"\b(?:athletes|clients)\s+coached\s*:?\s*\d",
    r"\bplans\s+sold\s*:?\s*\d",
)

# ── Who counts as a person in an attribution ────────────────────────────

# A word in the name slot that marks a publication, organisation or
# platform, not a person: "— The Guardian", "— Cycling Weekly",
# "Life Time Grand Prix · 232K views".
ORG_WORDS = frozenset({
    "the", "weekly", "magazine", "mag", "news", "newspaper", "times",
    "guardian", "journal", "post", "daily", "tribune", "herald", "gazette",
    "review", "reviews", "press", "media", "radio", "podcast", "tv",
    "channel", "show", "cycling", "cyclist", "cyclists", "bicycling", "bike",
    "bikes", "biking", "velo", "velonews", "gravel", "outside", "club",
    "team", "racing", "race", "races", "events", "event", "series",
    "official", "organizers", "organisers", "organizer", "organiser",
    "promoter", "promoters", "staff", "editors", "editor", "editorial",
    "desk", "collective", "company", "co", "inc", "llc", "ltd",
    "foundation", "association", "federation", "committee", "council",
    "society", "productions", "studio", "studios", "online", "blog",
    "report", "wire", "network", "grand", "prix", "tour", "gp",
    "institute", "university", "group", "labs", "lab", "god", "strava",
    "reddit", "youtube", "instagram", "facebook", "twitter", "tiktok",
    "substack", "wikipedia", "uci", "usac",
})
NAME_PARTICLES = frozenset({"van", "von", "de", "del", "della", "da", "di", "du", "la", "le"})

_HARD, _SOFT = "\x1f", "\x1e"  # element boundaries inside collected text
_INLINE = frozenset({"a", "abbr", "b", "em", "i", "mark", "small", "span", "strong", "time", "u"})
_DASH_LINE_TAGS = frozenset({"p", "div", "span", "small", "li", "dd", "strong", "b", "em", "i"})
_VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                   "meta", "param", "source", "track", "wbr"})
# Python's \s matches the boundary characters, so spell whitespace out.
_WS = "[ \t\n\r\f\v\u00a0\u2009\u202f]"
# A dash, then the name with nothing but whitespace or an inline tag between.
_LEAD_DASH_RE = re.compile(
    rf"^(?:{_WS}|[\x1e\x1f])*(?:[—–―]|-(?={_WS}))(?:{_WS}|\x1e)*(?![\x1e\x1f]|{_WS}|$)"
)
_NAME_SPLIT_RE = re.compile(rf"[\x1e\x1f,·•|(/;:]|{_WS}[-–—―]{_WS}")
_INITIAL_RE = re.compile(r"(?:[A-Z]\.){1,3}")
_COMMERCIAL_CLASS_RE = re.compile(r"coaching|(?:^|[-_])cta(?:$|[-_])")
_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

# Receipts ledger (spec §4.4, §6.2). Empty until the receipts component
# lands; that change replaces this with a loader for the ledger.
KNOWN_RECEIPT_IDS: frozenset = frozenset()


def _plain(text: str) -> str:
    return " ".join(text.replace(_HARD, " ").replace(_SOFT, " ").split())


def _visible_text(markup: str) -> str:
    return " ".join(html_lib.unescape(re.sub(r"<[^>]+>", " ", markup)).split())


def find_unsupported_claims(text: str) -> list[str]:
    """Scarcity, rating and coach-count claims in copy (markup or text)."""
    findings = []
    lowered = text.lower()
    for s in SCARCITY_STRINGS:
        if s.lower() in lowered:
            findings.append(f"banned string {s!r}")
    for pattern in RATING_CLAIM_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            findings.append(f"rating claim {m.group(0)!r}")
    for pattern in COUNT_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            findings.append(f"unverified count {m.group(0)!r}")
    return findings


def _is_name_word(token: str) -> bool:
    core = re.sub(r"['’-]", "", token.rstrip("."))
    return (len(core) >= 2 and core.isalpha() and token[0].isupper()
            and any(c.islower() for c in core))


def person_in_attribution(text: str, *, structural: bool = False) -> str | None:
    """The person an attribution names, or None.

    `text` is the attribution's text; element boundaries inside it act as
    separators, so <footer><strong>Pat Q.</strong><span>Unbound</span>
    reads as "Pat Q." then "Unbound". A person is:
      - a name with an initial ("Pat Q.", "Test Rider A"), anywhere;
      - "First Last" after a leading dash, or in a structural slot
        (<footer>/<figcaption> of a quote);
      - a lone first name after a dash with context ("— Pat · Unbound 2025").
    Any publication/organisation word in the name slot means not a person.
    An undashed <cite> is a source title ("Drew Dillman · 35.8K views",
    a YouTube channel), not a testimonial byline.
    """
    m = _LEAD_DASH_RE.match(text)
    body = text[m.end():] if m else text
    pieces = [" ".join(p.split()) for p in _NAME_SPLIT_RE.split(body)]
    first = next((i for i, p in enumerate(pieces) if p), None)
    if first is None:
        return None
    name = pieces[first]
    has_context = any(pieces[first + 1:])
    tokens = name.split()
    if any(t.lower().strip(".'’") in ORG_WORDS for t in tokens):
        return None
    words = [t for t in tokens if t.lower() not in NAME_PARTICLES]
    if not words or len(words) > 3:
        return None
    initials = [
        t for i, t in enumerate(words)
        if _INITIAL_RE.fullmatch(t) or (len(t) == 1 and t.isupper() and i == len(words) - 1)
    ]
    full = [t for t in words if _is_name_word(t)]
    if not full or len(initials) + len(full) != len(words):
        return None
    if initials:
        return name
    if len(full) >= 2 and (m or structural):
        return name
    if len(full) == 1 and m and has_context:
        return name
    return None


class _Frame:
    __slots__ = ("tag", "in_receipt", "in_quote", "in_commercial", "commercial_root",
                 "parts", "has_quote", "captions")

    def __init__(self, tag, parent, *, receipt, commercial):
        self.tag = tag
        self.in_receipt = receipt or bool(parent and parent.in_receipt)
        self.in_quote = tag in ("blockquote", "q") or bool(parent and parent.in_quote)
        self.commercial_root = commercial and not (parent and parent.in_commercial)
        self.in_commercial = commercial or bool(parent and parent.in_commercial)
        self.parts: list[str] = []
        self.has_quote = False
        self.captions: list[str] = []


class _ProofScanner(HTMLParser):
    def __init__(self, page_kind: str, known_receipt_ids: frozenset):
        super().__init__(convert_charrefs=True)
        self.page_kind = page_kind
        self.known = known_receipt_ids
        self.findings: list[str] = []
        self._stack: list[_Frame] = []

    def _flag(self, finding: str) -> None:
        if finding not in self.findings:
            self.findings.append(finding)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        for cls in classes:
            if cls in ALLOWED_TESTIMONIAL_CLASS_TOKENS:
                continue
            if cls.startswith(LEGACY_TESTIMONIAL_CLASSES) or "testimonial" in cls:
                self._flag(f"testimonial class .{cls} on <{tag}>")
        if "data-receipt-id" in a and a["data-receipt-id"] not in self.known:
            self._flag(f"data-receipt-id={a['data-receipt-id']!r} does not resolve "
                       "in the receipts ledger")
        if tag in _VOID:
            if self._stack:  # <br> separates "Pat Q." from "Unbound 2025"
                self._stack[-1].parts.append(_HARD)
            return
        commercial = ("data-ab" in a or "data-cta" in a
                      or any(_COMMERCIAL_CLASS_RE.search(c) for c in classes))
        parent = self._stack[-1] if self._stack else None
        if tag in ("blockquote", "q"):
            for frame in self._stack:
                if frame.tag == "figure":
                    frame.has_quote = True
        self._stack.append(_Frame(tag, parent, receipt="data-receipt-id" in a,
                                  commercial=commercial))

    def handle_endtag(self, tag):
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                while len(self._stack) > i:
                    self._close(self._stack.pop())
                return

    def handle_data(self, data):
        if self._stack:
            self._stack[-1].parts.append(data)

    def finish(self) -> list[str]:
        self.close()
        while self._stack:
            self._close(self._stack.pop())
        return self.findings

    def _attribution(self, slot: str, text: str, *, structural: bool) -> bool:
        name = person_in_attribution(text, structural=structural)
        if name:
            self._flag(f"person-attributed {slot} outside a receipt: {name!r} "
                       f"(in {_plain(text)!r})")
        return bool(name)

    def _close(self, frame: _Frame) -> None:
        text = "".join(frame.parts)
        if self._stack:
            edge = _SOFT if frame.tag in _INLINE else _HARD
            self._stack[-1].parts.append(edge + text + edge)
        if frame.commercial_root and self.page_kind == EDITORIAL:
            for claim in find_unsupported_claims(_plain(text)):
                self._flag(f"{claim} in a commercial element")
        if frame.in_receipt:
            return
        if frame.tag == "cite":
            named = self._attribution("<cite>", text, structural=False)
            if not named and self.page_kind == COMMERCIAL:
                self._flag(f"<cite> outside a data-receipt-id element: {_plain(text)!r}")
        elif frame.tag == "footer":
            self._attribution("<footer>", text, structural=frame.in_quote)
        elif frame.tag == "figcaption":
            figure = next((f for f in reversed(self._stack) if f.tag == "figure"), None)
            if figure is not None:
                figure.captions.append(text)  # judged when the figure closes
            else:
                self._attribution("<figcaption>", text, structural=False)
        elif frame.tag == "figure":
            for caption in frame.captions:
                self._attribution("<figcaption>", caption, structural=frame.has_quote)
        if frame.tag in _DASH_LINE_TAGS and _LEAD_DASH_RE.match(text):
            self._attribution("dash line", text, structural=False)


def _aggregate_ratings(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "aggregateRating" and isinstance(value, dict):
                yield value
            yield from _aggregate_ratings(value)
    elif isinstance(node, list):
        for item in node:
            yield from _aggregate_ratings(item)


def find_unsourced_proof(
    html: str,
    *,
    page_kind: str = COMMERCIAL,
    sourced_rating_counts: frozenset = frozenset(),
    known_receipt_ids: frozenset = KNOWN_RECEIPT_IDS,
) -> list[str]:
    """Return every unsourced-proof finding in an HTML string (empty = clean).

    page_kind: COMMERCIAL (default, strictest) or EDITORIAL (race profiles,
    Gravel Weekly); see the module docstring.
    sourced_rating_counts: ratingCount values that trace to real Racer
    Ratings for this page (race pages only). Every other aggregateRating,
    and any that isn't in parseable JSON-LD, is a finding.
    """
    assert page_kind in (COMMERCIAL, EDITORIAL), page_kind
    findings = []
    if page_kind == COMMERCIAL:
        findings += find_unsupported_claims(html + "\n" + _visible_text(html))

    total = html.count("aggregateRating")
    if total:
        sourced = 0
        for block in _JSONLD_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            for agg in _aggregate_ratings(data):
                if str(agg.get("ratingCount")) in sourced_rating_counts:
                    sourced += 1
        if total > sourced:
            findings.append(
                f"aggregateRating without a real rating source ({total - sourced} of {total})"
            )

    scanner = _ProofScanner(page_kind, known_receipt_ids)
    scanner.feed(html)
    return findings + scanner.finish()


# ── The guard itself must catch planted regressions ─────────────────────

BOTH_KINDS = pytest.mark.parametrize("kind", [COMMERCIAL, EDITORIAL])


class TestGuardCatchesPlantedRegressions:
    """Fixture HTML only. If one of these stops failing, the guard is blind."""

    @pytest.mark.parametrize("html", [
        '<blockquote class="gg-about-testimonial"><p>Great plan.</p>'
        '<footer><strong>Pat Q.</strong></footer></blockquote>',
        '<div class="gg-tp-testimonials"><div class="gg-tp-testimonial"><p>x</p></div></div>',
        '<div class="gg-coach-testimonial">x</div>',
        '<div class="card gg-consult-testimonial--wide">x</div>',
        '<p class="gg-hp-test-quote">x</p>',
        '<div class="gg-trust-quote"><p>x</p></div>',
        '<div class="tp-testimonial"><p>x</p></div>',
        '<div class="gg-new-testimonial-card"><p>x</p></div>',
    ])
    def test_legacy_testimonial_classes(self, html):
        assert any("testimonial class" in f for f in find_unsourced_proof(html))

    @pytest.mark.parametrize("copy", [
        "4.7 Stars from 100+ Reviews",
        "A human in your corner. 20 athletes/month.",
        "Next window: April.",
        "Limited spots &mdash; opens quarterly.",
        "1:1 COACHING &mdash; LIMITED SPOTS",
    ])
    def test_scarcity_and_rating_strings(self, copy):
        assert find_unsourced_proof(f"<p>{copy}</p>")

    @pytest.mark.parametrize("copy", [
        "Rated 4.9/5 by our athletes",
        "rated 4.9 out of 5",
        "4.9/5 from riders",
        "4.9 out of 5 stars",
        "4.8★",
        "4.8 &#9733; on Google",
        "★ 4.8",
        "&#9733;&#9733;&#9733;&#9733;&#9733; (123 reviews)",
        "Plans (1,204 ratings)",
        "200+ five-star reviews",
    ])
    def test_rating_claims(self, copy):
        assert any("rating claim" in f for f in find_unsourced_proof(f"<p>{copy}</p>"))

    @pytest.mark.parametrize("copy", [
        "I&#39;ve coached 100+ athletes.",
        "100+ athletes coached, 1,000+ training plans sold.",
        "<dl><dt>Athletes coached</dt><dd>100+</dd></dl>",
    ])
    def test_coach_counts(self, copy):
        assert any("unverified count" in f for f in find_unsourced_proof(f"<div>{copy}</div>"))

    def test_hard_coded_aggregate_rating(self):
        html = ('<script type="application/ld+json">{"@type":"SportsEvent",'
                '"aggregateRating":{"@type":"AggregateRating","ratingValue":"76",'
                '"ratingCount":"14"}}</script>')
        assert find_unsourced_proof(html)
        # Only a count that traces to real ratings passes.
        assert find_unsourced_proof(html, page_kind=EDITORIAL,
                                    sourced_rating_counts=frozenset({"14"})) == []
        assert find_unsourced_proof(html, page_kind=EDITORIAL,
                                    sourced_rating_counts=frozenset({"47"}))

    def test_aggregate_rating_outside_json_ld(self):
        html = '<div itemprop="aggregateRating"><span itemprop="ratingCount">14</span></div>'
        assert find_unsourced_proof(html, page_kind=EDITORIAL,
                                    sourced_rating_counts=frozenset({"14"}))

    @BOTH_KINDS
    @pytest.mark.parametrize("cite", [
        "&mdash; Jason R., Mid-South 2025",
        "&mdash; Sarah K.",
        "— Mark D. &middot; Big Sugar 2025",
        "&ndash; Firstname Lastname, Unbound 200 finisher",
        "&mdash; Name &middot; Unbound 100 2025",
        "&mdash; <strong>Pat Q.</strong>, Unbound 2026",
        "Test Rider A",
    ])
    def test_person_attributed_cite(self, cite, kind):
        html = f"<blockquote><p>&ldquo;Best plan ever.&rdquo;</p><cite>{cite}</cite></blockquote>"
        findings = find_unsourced_proof(html, page_kind=kind)
        assert any("person-attributed <cite>" in f for f in findings), findings

    def test_any_cite_on_a_commercial_page(self):
        """A press quote on a sales page is proof too; it needs a receipt."""
        html = "<blockquote><p>The best plan.</p><cite>Cycling Weekly</cite></blockquote>"
        assert any("<cite> outside" in f for f in find_unsourced_proof(html))

    @BOTH_KINDS
    @pytest.mark.parametrize("footer", [
        # The exact shape of the deleted /about/ cards, under a new class name.
        "<footer><strong>Pat Q.</strong>"
        '<span class="gg-about-voice-meta">BWR Waffle · 10 hrs/week</span></footer>',
        "<footer><strong>Test Rider A</strong></footer>",
        "<footer><b>Pat Quinn</b><span>Unbound 200 finisher</span></footer>",
        "<footer>&mdash; Pat Q., Unbound 2025</footer>",
    ])
    def test_footer_strong_attribution(self, footer, kind):
        html = f'<blockquote class="gg-about-voice"><p>Great plan.</p>{footer}</blockquote>'
        findings = find_unsourced_proof(html, page_kind=kind)
        assert any("person-attributed <footer>" in f for f in findings), findings

    @BOTH_KINDS
    @pytest.mark.parametrize("caption", [
        "Test Rider B, Mid-South 2025",
        "&mdash; Pat Q.",
        "<strong>Pat Quinn</strong> &middot; Unbound 200",
    ])
    def test_figcaption_attribution(self, caption, kind):
        html = (f'<figure class="gg-proof-card"><blockquote><p>Best plan ever.</p></blockquote>'
                f"<figcaption>{caption}</figcaption></figure>")
        findings = find_unsourced_proof(html, page_kind=kind)
        assert any("person-attributed <figcaption>" in f for f in findings), findings

    @BOTH_KINDS
    @pytest.mark.parametrize("line", [
        "<p>&mdash; Test Rider C</p>",
        "<p>— Pat Q.</p>",
        "<p>&mdash; Pat Q., Unbound 2025</p>",
        "<p>&ndash; Firstname Lastname &middot; Big Sugar 2025</p>",
        "<p>&mdash; <strong>Pat Q.</strong></p>",
        '<span class="gg-card-by">— Pat Quinn</span>',
        "<p>&mdash; Pat Q.<br>Unbound 2025</p>",
    ])
    def test_dash_line_attribution(self, line, kind):
        html = f'<div class="gg-about-card"><p>&ldquo;Best plan ever.&rdquo;</p>{line}</div>'
        findings = find_unsourced_proof(html, page_kind=kind)
        assert any("person-attributed dash line" in f for f in findings), findings

    def test_cite_in_unknown_receipt_is_flagged(self):
        html = ('<figure data-receipt-id="made-up"><blockquote>x</blockquote>'
                '<cite>&mdash; Pat Q., Unbound 2026</cite></figure>')
        findings = find_unsourced_proof(html)
        assert any("does not resolve" in f for f in findings)

    def test_the_old_questionnaire_strip_is_caught(self):
        """The exact markup that sat above Submit & Pay until 2026-09-28."""
        html = (
            '<div class="gg-trust-strip"><div class="gg-trust-quotes">'
            '<div class="gg-trust-quote"><p>&ldquo;I finished Mid-South 45 minutes'
            ' faster than last year.&rdquo;</p><cite>&mdash; Jason R., Mid-South 2025'
            '</cite></div></div><div class="gg-trust-badges">'
            '<span class="gg-trust-badge">7-Day Full Refund</span></div></div>'
        )
        findings = find_unsourced_proof(html)
        assert any("gg-trust-quote" in f for f in findings)
        assert any("<cite> outside" in f for f in findings)
        assert any("person-attributed" in f for f in find_unsourced_proof(html, page_kind=EDITORIAL))

    def test_the_old_about_card_is_caught_under_a_new_class(self, monkeypatch):
        """The deleted /about/ carousel card, renamed, planted in the real page."""
        import generate_about
        original = generate_about.build_coaching
        card = ('<blockquote class="gg-about-voice"><p>Placeholder.</p>'
                '<footer><strong>Pat Q.</strong><span class="gg-about-voice-meta">'
                'Unbound 200 · 10 hrs/week</span></footer></blockquote>')
        monkeypatch.setattr(generate_about, "build_coaching", lambda: original() + card)
        findings = find_unsourced_proof(generate_about.generate_about_page())
        assert any("person-attributed <footer>" in f and "Pat Q." in f for f in findings), findings

    def test_scarcity_in_a_race_page_coaching_cta_is_caught(self):
        """Race pages are editorial, but the coaching footnote on every one
        of them is sales copy, so scarcity there still fails."""
        html = _render(f"/race/{SAMPLE_RACE}/")
        cta = 'data-cta="approved_coaching">GET ME IN YOUR CORNER'
        assert cta in html
        planted = html.replace(cta, 'data-cta="approved_coaching">1:1 COACHING &mdash; LIMITED SPOTS')
        findings = find_unsourced_proof(planted, page_kind=EDITORIAL,
                                        sourced_rating_counts=_sourced_rating_counts(SAMPLE_RACE))
        assert any("Limited spots" in f and "commercial element" in f for f in findings), findings


class TestGuardAllowsLegitimateMarkup:
    def test_blockquote_without_person_attribution(self):
        html = "<blockquote><p>The mud at mile 80 decides it.</p></blockquote>"
        assert find_unsourced_proof(html) == []

    def test_youtube_channel_cite_on_race_pages(self):
        html = ('<blockquote class="gg-field-quote"><p class="gg-field-quote-text">'
                'Brutal climb.</p><cite class="gg-field-quote-cite">Some Channel '
                '&middot; 69K views</cite></blockquote>')
        assert find_unsourced_proof(html, page_kind=EDITORIAL) == []

    def test_rider_named_youtube_channel_cite_on_race_pages(self):
        html = ('<blockquote class="gg-field-quote"><p class="gg-field-quote-text">'
                'Brutal climb.</p><cite class="gg-field-quote-cite">Test Channelname '
                '&middot; 35.8K views</cite></blockquote>')
        assert find_unsourced_proof(html, page_kind=EDITORIAL) == []

    @pytest.mark.parametrize("attribution", [
        "— The Guardian",
        "&mdash; The Guardian",
        "&mdash; Cycling Weekly, June 2025",
        "&mdash; Velo &middot; 2026",
        "— Outside Magazine",
        "&mdash; Unbound Gravel organizers",
        "&mdash; Life Time Grand Prix",
        "Gravel Cyclist &middot; 1.9K views",
        "&mdash; Strava, 2024",
    ])
    @pytest.mark.parametrize("slot", ["cite", "footer", "figcaption", "p"])
    def test_publication_and_organisation_attributions(self, attribution, slot):
        if slot == "figcaption":
            html = (f"<figure><blockquote><p>Brutal.</p></blockquote>"
                    f"<figcaption>{attribution}</figcaption></figure>")
        else:
            html = f"<blockquote><p>Brutal.</p><{slot}>{attribution}</{slot}></blockquote>"
        assert find_unsourced_proof(html, page_kind=EDITORIAL) == []

    def test_cite_inside_a_ledgered_receipt(self):
        html = ('<figure data-receipt-id="r-001"><blockquote>x</blockquote>'
                '<cite>&mdash; Pat Q., Unbound 2026</cite></figure>')
        assert find_unsourced_proof(html, known_receipt_ids=frozenset({"r-001"})) == []

    def test_coaching_band_class_is_not_a_quote_class(self):
        html = '<section class="gg-hp-testimonials"><div class="gg-hp-test-cta"><p>x</p></div></section>'
        assert find_unsourced_proof(html) == []

    def test_trust_badges_survive(self):
        html = ('<div class="gg-trust-strip"><div class="gg-trust-badges">'
                '<span class="gg-trust-badge">7-Day Full Refund</span></div></div>')
        assert find_unsourced_proof(html) == []

    @pytest.mark.parametrize("html", [
        '<div class="gg-hero-score"><div class="gg-hero-rider-empty">&mdash;</div>'
        '<a class="gg-hero-score-label" href="#r">RIDER SCORE &middot; RATE IT &rarr;</a></div>',
        '<div class="gg-stat"><div>&mdash;</div><div>Entry Cost</div></div>',
        "<p>&mdash; email me when this entry changes.</p>",
        "<p>Heat adaptation isn&#x27;t optional&mdash;it&#x27;s survival.</p>",
        '<figure><img src="x.jpg" alt=""><figcaption>Photo: Test Rider A</figcaption></figure>',
        '<figure><img src="x.jpg" alt=""><figcaption>Real course route &mdash; '
        '<a href="#">Test Route via RideWithGPS</a></figcaption></figure>',
        '<footer class="gg-mega-footer"><div><h3>Races</h3><a href="/">Race Search</a></div></footer>',
    ])
    def test_editorial_markup_that_looks_like_an_attribution(self, html):
        assert find_unsourced_proof(html, page_kind=EDITORIAL) == []

    @pytest.mark.parametrize("copy", [
        "Registration opens in January; limited spots sell out fast.",
        "The event maintains a 4.6/5 rating from 59 reviews.",
        "Next window for registration is March.",
    ])
    def test_race_editorial_claims_outside_commercial_elements(self, copy):
        html = f'<div class="gg-prose"><p>{copy}</p></div>'
        assert find_unsourced_proof(html, page_kind=EDITORIAL) == []
        assert find_unsourced_proof(html)  # the same copy on a sales page fails

    def test_gravel_weekly_receipts_and_culture_cards(self):
        """Weekly quotes publications (receipts) and people (culture desk)
        as sourced reporting: publisher link, then the excerpt."""
        from generate_gravel_weekly import render_receipts
        from gravel_weekly_culture import render_culture_artifacts
        receipts = render_receipts([{
            "canonicalUrl": "https://example.com/story/",
            "publisher": "Test Gazette",
            "publishedAt": "2026-08-27T12:00:00Z",
            "quoteExcerpt": "A bounded excerpt.",
        }])
        culture = render_culture_artifacts([{
            "artifactId": "culture-artifact_0123456789abcdef",
            "sourceKind": "bluesky",
            "publisher": "Test Rider A",
            "author": "Test Rider A",
            "canonicalUrl": "https://example.com/post/1",
            "publishedAt": "2026-08-27T18:30:00Z",
            "title": "The team bus became the meme",
            "excerpt": "Gravel has entered its team-bus era.",
            "timestampSeconds": None,
            "topicTags": ["teamification"],
        }])
        for html in (receipts, culture):
            assert "<blockquote>" in html
            assert find_unsourced_proof(html, page_kind=EDITORIAL) == []


# ── The real pages ───────────────────────────────────────────────────────

SAMPLE_RACE = "unbound-200"
# Race descriptions that legitimately say registration has limited spots.
LIMITED_SPOTS_RACES = ("whiskey-off-road", "wollombi-gravel-fest", "final-frontier-patagonia")


@functools.lru_cache(maxsize=None)
def _race_index() -> list:
    return json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))


def _about() -> str:
    from generate_about import generate_about_page
    return generate_about_page()


def _training_plans() -> str:
    from generate_training_plans import generate_training_page
    return generate_training_page()


def _consulting() -> str:
    from generate_consulting import generate_consulting_page
    return generate_consulting_page()


def _coaching() -> str:
    from generate_coaching import generate_coaching_page
    return generate_coaching_page()


def _homepage() -> str:
    import generate_homepage
    fake_posts = [{"title": "Test Post", "url": "https://example.com", "snippet": "x"}]
    with patch.object(generate_homepage, "fetch_substack_posts", return_value=fake_posts):
        return generate_homepage.generate_homepage(_race_index())


def _race_page(slug: str):
    def render() -> str:
        import generate_neo_brutalist
        rd = generate_neo_brutalist.load_race_data(ROOT / "race-data" / f"{slug}.json")
        return generate_neo_brutalist.generate_page(rd, _race_index())
    return render


def _race_training_plan_page() -> str:
    import generate_training_plan_pages as gtpp
    d = json.loads((ROOT / "race-data" / f"{SAMPLE_RACE}.json").read_text(encoding="utf-8"))
    race = d.get("race", d)
    race.setdefault("slug", SAMPLE_RACE)
    return gtpp.generate_page(race, gtpp.load_pack(SAMPLE_RACE))


def _guide_coaching_cta() -> str:
    from generate_guide import build_cta_coaching
    return build_cta_coaching()


def _source(rel: str):
    return lambda: (ROOT / rel).read_text(encoding="utf-8")


PAGES = {
    "/about/": (COMMERCIAL, _about),
    "/products/training-plans/": (COMMERCIAL, _training_plans),
    "/questionnaire/ (web/training-plans-questionnaire.html)":
        (COMMERCIAL, _source("web/training-plans-questionnaire.html")),
    "web/training-plans.html (legacy)": (COMMERCIAL, _source("web/training-plans.html")),
    "/consulting/": (COMMERCIAL, _consulting),
    "/coaching/": (COMMERCIAL, _coaching),
    "homepage": (COMMERCIAL, _homepage),
    f"/race/{SAMPLE_RACE}/training-plan/": (COMMERCIAL, _race_training_plan_page),
    "guide coaching CTA": (COMMERCIAL, _guide_coaching_cta),
    f"/race/{SAMPLE_RACE}/": (EDITORIAL, _race_page(SAMPLE_RACE)),
    **{f"/race/{slug}/": (EDITORIAL, _race_page(slug)) for slug in LIMITED_SPOTS_RACES},
}


@functools.lru_cache(maxsize=None)
def _render(name: str) -> str:
    return PAGES[name][1]()


def _sourced_rating_counts(slug: str) -> frozenset:
    """Racer Rating counts that may appear in a race page's JSON-LD."""
    from brand_tokens import RACER_RATING_THRESHOLD
    d = json.loads((ROOT / "race-data" / f"{slug}.json").read_text(encoding="utf-8"))
    rr = d.get("race", d).get("racer_rating") or {}
    total = rr.get("total_ratings") or 0
    if total >= RACER_RATING_THRESHOLD and rr.get("star_average"):
        return frozenset({str(total)})
    return frozenset()


@pytest.mark.parametrize("name", list(PAGES))
def test_page_has_no_unsourced_proof(name):
    kind = PAGES[name][0]
    html = _render(name)
    assert len(html) > 200, f"{name} rendered almost nothing"
    sourced = frozenset()
    if name.startswith("/race/") and kind == EDITORIAL:
        sourced = _sourced_rating_counts(name.split("/")[2])
    findings = find_unsourced_proof(html, page_kind=kind, sourced_rating_counts=sourced)
    assert not findings, f"{name}: " + "; ".join(findings)


@pytest.mark.parametrize("slug", LIMITED_SPOTS_RACES)
def test_race_description_with_limited_spots_passes(slug):
    """Race copy about the event's own registration isn't coaching scarcity."""
    html = _render(f"/race/{slug}/")
    assert "limited spots" in html.lower(), f"{slug} no longer says limited spots; pick another race"
    assert find_unsourced_proof(html, page_kind=EDITORIAL,
                                sourced_rating_counts=_sourced_rating_counts(slug)) == []


def test_race_jsonld_template_has_no_aggregate_rating():
    """scripts/generate_index.py wrote aggregateRating ratingCount "14" into
    every race's JSON-LD; nobody was counted."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from generate_index import generate_jsonld
    entry = next(e for e in _race_index() if e["slug"] == SAMPLE_RACE)
    assert "aggregateRating" not in generate_jsonld(entry, None)
    offenders = [p.name for p in (ROOT / "web" / "jsonld").glob("*.jsonld")
                 if "aggregateRating" in p.read_text(encoding="utf-8")]
    assert offenders == [], f"stale JSON-LD, rerun generate_index.py --with-jsonld: {offenders[:5]}"


def test_ab_payload_has_no_unsourced_proof():
    """A/B copy is injected client-side, so the page HTML can't show it."""
    from ab_experiments import EXPERIMENTS
    on_disk = json.loads((ROOT / "web" / "ab" / "experiments.json").read_text(encoding="utf-8"))
    for source, experiments in (("ab_experiments.py", EXPERIMENTS),
                                ("web/ab/experiments.json", on_disk["experiments"])):
        for exp in experiments:
            for v in exp["variants"]:
                findings = find_unsourced_proof(v["content"])
                assert not findings, f"{source} {exp['id']}/{v['id']}: {findings}"


def test_experiment_templates_have_no_unsourced_proof():
    """scripts/experiment_loop.py promotes these into live A/B tests, and
    data-ab="race_coaching_cta" is on every race page."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from experiment_templates import TEMPLATES
    for category, templates in TEMPLATES.items():
        for template in templates:
            for v in template["variants"]:
                findings = find_unsourced_proof(v["content"])
                assert not findings, f"{category}/{template['id']}/{v['id']}: {findings}"
    ids = {t["id"] for templates in TEMPLATES.values() for t in templates}
    assert "hero_tagline_proof" not in ids  # "Riders in 43 states trust these scores."


# ── Takedown specifics (receipts spec §4.1, 2026-09-28) ──────────────────


class TestAboutPageTakedown:
    def test_no_results_section_or_carousel(self):
        html = _render("/about/")
        assert 'id="results"' not in html
        assert "Athlete Results" not in html
        assert "gg-testimonial-carousel" not in html
        assert "about_carousel" not in html  # GA event tied to the carousel
        assert "athlete_results" not in html  # scroll-depth label for it

    def test_uncheckable_counts_removed(self):
        html = _render("/about/")
        for claim in ("100+", "1,000", "Athletes coached", "Plans sold"):
            assert claim not in html, claim

    def test_owner_bio_kept(self):
        html = _render("/about/")
        assert "12 years at TrainingPeaks" in html

    def test_no_scarcity_hook(self):
        html = _render("/about/")
        assert "coaching_scarcity" not in html
        assert "/coaching/apply/" in html  # the coaching CTA itself stays


def test_coaching_scarcity_experiment_retired():
    from ab_experiments import EXPERIMENTS
    assert "coaching_scarcity" not in {e["id"] for e in EXPERIMENTS}
    on_disk = json.loads((ROOT / "web" / "ab" / "experiments.json").read_text(encoding="utf-8"))
    assert "coaching_scarcity" not in {e["id"] for e in on_disk["experiments"]}
    assert "coaching_scarcity" not in _render("homepage")
