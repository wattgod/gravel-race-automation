"""Guard: no unsourced social proof on the decision-point pages.

docs/specs/receipts-social-proof-2026.md §4.4. Until 2026-09-28 /about/,
/products/training-plans/ and the questionnaire carried placeholder
testimonials written by Claude sessions in Feb 2026, next to counts and
scarcity copy nobody could check. This file fails the build if any of that
comes back.

It fails on:
  - an element whose class starts with a legacy testimonial class;
  - `aggregateRating`, unless it is a race page's Racer Rating block whose
    ratingCount matches that race's real ratings (3+);
  - the scarcity/rating strings "Stars from", "athletes/month",
    "Next window", "Limited spots";
  - a person-attributed <cite> ("— Firstname L.", "&mdash; Name ·") outside
    an element carrying data-receipt-id;
  - a data-receipt-id that does not resolve in the receipts ledger. No
    ledger exists yet, so no page may emit one.

<blockquote> is deliberately NOT banned: race pages quote YouTube riders
with a channel attribution, and Gravel Weekly quotes sources.
"""
from __future__ import annotations

import functools
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

LEGACY_TESTIMONIAL_CLASSES = (
    "gg-about-testimonial",    # /about/ carousel (50 placeholders)
    "gg-tp-testimonial",       # /products/training-plans/ (3 placeholders)
    "gg-coach-testimonial",    # /coaching/ band sequence, pre-2026-07-18
    "gg-consult-testimonial",  # /consulting/, removed in copy v2
    "gg-hp-test-quote",        # homepage quote cards, pre-2026-07-18
    "gg-hp-test-card",
    "gg-trust-quote",          # questionnaire, above Submit & Pay
    "tp-testimonial",          # web/training-plans.html (legacy paste-in)
)

BANNED_STRINGS = ("Stars from", "athletes/month", "Next window")
BANNED_STRINGS_ANY_CASE = ("limited spots",)

# A dash, then one or two capitalised words (a name, maybe an initial), then
# a separator or the end: "— Jason R., Mid-South 2025", "— Sarah K.",
# "— Mark D. · Big Sugar 2025". A cite with no leading dash (race-page YouTube
# channel credits, publication titles) is not person-attributed.
PERSON_CITE_RE = re.compile(
    r"^[—–―-]{1,2}\s*"
    r"[A-Z][A-Za-z'’.-]*"
    r"(?:\s+[A-Z][A-Za-z'’-]*\.?)?"
    r"\s*(?:[,·|(]|$)"
)

# Receipts ledger (spec §4.4, §6.2). Empty until the receipts component
# lands; that change replaces this with a loader for the ledger.
KNOWN_RECEIPT_IDS: frozenset = frozenset()

_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
         "meta", "param", "source", "track", "wbr"}
_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


class _ProofScanner(HTMLParser):
    def __init__(self, known_receipt_ids: frozenset):
        super().__init__(convert_charrefs=True)
        self.known = known_receipt_ids
        self.findings: list[str] = []
        self._stack: list[tuple[str, bool]] = []  # (tag, inside a receipt)
        self._cite: list[str] | None = None
        self._cite_in_receipt = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        for cls in (a.get("class") or "").split():
            for banned in LEGACY_TESTIMONIAL_CLASSES:
                if cls.startswith(banned):
                    self.findings.append(f"legacy testimonial class .{cls} on <{tag}>")
        receipt_id = a.get("data-receipt-id")
        if "data-receipt-id" in a and receipt_id not in self.known:
            self.findings.append(
                f"data-receipt-id={receipt_id!r} does not resolve in the receipts ledger"
            )
        inside = "data-receipt-id" in a or any(r for _, r in self._stack)
        if tag in _VOID:
            return
        self._stack.append((tag, inside))
        if tag == "cite":
            self._cite = []
            self._cite_in_receipt = inside

    def handle_endtag(self, tag):
        if tag == "cite" and self._cite is not None:
            text = " ".join("".join(self._cite).split())
            if PERSON_CITE_RE.match(text) and not self._cite_in_receipt:
                self.findings.append(f"person-attributed <cite> outside a receipt: {text!r}")
            self._cite = None
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break

    def handle_data(self, data):
        if self._cite is not None:
            self._cite.append(data)


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
    sourced_rating_counts: frozenset = frozenset(),
    known_receipt_ids: frozenset = KNOWN_RECEIPT_IDS,
) -> list[str]:
    """Return every unsourced-proof finding in an HTML string (empty = clean).

    sourced_rating_counts: ratingCount values that trace to real Racer
    Ratings for this page (race pages only). Every other aggregateRating,
    and any that isn't in parseable JSON-LD, is a finding.
    """
    findings = []
    for s in BANNED_STRINGS:
        if s in html:
            findings.append(f"banned string {s!r}")
    lowered = html.lower()
    for s in BANNED_STRINGS_ANY_CASE:
        if s in lowered:
            findings.append(f"banned string {s!r} (any case)")

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

    scanner = _ProofScanner(known_receipt_ids)
    scanner.feed(html)
    scanner.close()
    return findings + scanner.findings


# ── The guard itself must catch planted regressions ─────────────────────


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
    ])
    def test_legacy_testimonial_classes(self, html):
        assert any("legacy testimonial class" in f for f in find_unsourced_proof(html))

    @pytest.mark.parametrize("copy", [
        "4.7 Stars from 100+ Reviews",
        "A human in your corner. 20 athletes/month.",
        "Next window: April.",
        "Limited spots &mdash; opens quarterly.",
        "1:1 COACHING &mdash; LIMITED SPOTS",
    ])
    def test_scarcity_and_rating_strings(self, copy):
        assert find_unsourced_proof(f"<p>{copy}</p>")

    def test_hard_coded_aggregate_rating(self):
        html = ('<script type="application/ld+json">{"@type":"SportsEvent",'
                '"aggregateRating":{"@type":"AggregateRating","ratingValue":"76",'
                '"ratingCount":"14"}}</script>')
        assert find_unsourced_proof(html)
        # Only a count that traces to real ratings passes.
        assert find_unsourced_proof(html, sourced_rating_counts=frozenset({"14"})) == []
        assert find_unsourced_proof(html, sourced_rating_counts=frozenset({"47"}))

    def test_aggregate_rating_outside_json_ld(self):
        html = '<div itemprop="aggregateRating"><span itemprop="ratingCount">14</span></div>'
        assert find_unsourced_proof(html, sourced_rating_counts=frozenset({"14"}))

    @pytest.mark.parametrize("cite", [
        "&mdash; Jason R., Mid-South 2025",
        "&mdash; Sarah K.",
        "— Mark D. &middot; Big Sugar 2025",
        "&ndash; Firstname Lastname, Unbound 200 finisher",
        "&mdash; Name &middot; Unbound 100 2025",
    ])
    def test_person_attributed_cite(self, cite):
        html = f"<blockquote><p>&ldquo;Best plan ever.&rdquo;</p><cite>{cite}</cite></blockquote>"
        assert any("person-attributed" in f for f in find_unsourced_proof(html))

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
        assert any("person-attributed" in f for f in findings)


class TestGuardAllowsLegitimateMarkup:
    def test_blockquote_without_person_attribution(self):
        html = "<blockquote><p>The mud at mile 80 decides it.</p></blockquote>"
        assert find_unsourced_proof(html) == []

    def test_youtube_channel_cite_on_race_pages(self):
        html = ('<blockquote class="gg-field-quote"><p class="gg-field-quote-text">'
                'Brutal climb.</p><cite class="gg-field-quote-cite">Some Channel '
                '&middot; 69K views</cite></blockquote>')
        assert find_unsourced_proof(html) == []

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


# ── The real pages ───────────────────────────────────────────────────────

SAMPLE_RACE = "unbound-200"


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


def _race_page() -> str:
    import generate_neo_brutalist
    rd = generate_neo_brutalist.load_race_data(ROOT / "race-data" / f"{SAMPLE_RACE}.json")
    return generate_neo_brutalist.generate_page(rd, _race_index())


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
    "/about/": _about,
    "/products/training-plans/": _training_plans,
    "/questionnaire/ (web/training-plans-questionnaire.html)":
        _source("web/training-plans-questionnaire.html"),
    "web/training-plans.html (legacy)": _source("web/training-plans.html"),
    "/consulting/": _consulting,
    "/coaching/": _coaching,
    "homepage": _homepage,
    f"/race/{SAMPLE_RACE}/": _race_page,
    f"/race/{SAMPLE_RACE}/training-plan/": _race_training_plan_page,
    "guide coaching CTA": _guide_coaching_cta,
}


@functools.lru_cache(maxsize=None)
def _render(name: str) -> str:
    return PAGES[name]()


def _sample_race_sourced_counts() -> frozenset:
    """Racer Rating counts that may appear in the race page's JSON-LD."""
    from brand_tokens import RACER_RATING_THRESHOLD
    d = json.loads((ROOT / "race-data" / f"{SAMPLE_RACE}.json").read_text(encoding="utf-8"))
    rr = d.get("race", d).get("racer_rating") or {}
    total = rr.get("total_ratings") or 0
    if total >= RACER_RATING_THRESHOLD and rr.get("star_average"):
        return frozenset({str(total)})
    return frozenset()


@pytest.mark.parametrize("name", list(PAGES))
def test_page_has_no_unsourced_proof(name):
    html = _render(name)
    assert len(html) > 200, f"{name} rendered almost nothing"
    sourced = _sample_race_sourced_counts() if name == f"/race/{SAMPLE_RACE}/" else frozenset()
    findings = find_unsourced_proof(html, sourced_rating_counts=sourced)
    assert not findings, f"{name}: " + "; ".join(findings)


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
