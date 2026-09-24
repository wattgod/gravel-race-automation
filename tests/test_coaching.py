"""Tests for the Gravel God coaching page generator.

Coaching page rewritten 2026-07-18 into "The Dossier" structure: hero →
terms → tiers → fit → faq → final-cta (replacing the old band sequence
hero → problem → deliverables → how-it-works → tiers → testimonials →
honest-check → faq → final-cta). This suite describes the page as it now
ships, not the old one — no lingering assertions about problem,
deliverables, how-it-works, or testimonials sections, none of which exist
anymore.

Modeled on road-race-automation/tests/test_coaching.py (the sibling-brand
rebuild's test suite), adapted for Gravel God: gg- class prefix, gravel
URLs, GA4 property G-EJJZ9T6M52, and gravel's slop_rules module for the
restraint guard.
"""
from __future__ import annotations

import html
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_coaching import (
    QUESTIONNAIRE_URL,
    TIERS,
    build_nav,
    build_hero,
    build_terms,
    build_tiers,
    build_fit_check,
    build_honest_check,
    build_faq,
    build_application_close,
    build_footer,
    build_mobile_sticky_cta,
    build_coaching_css,
    build_coaching_js,
    build_jsonld,
    generate_coaching_page,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def coaching_html():
    return generate_coaching_page()


@pytest.fixture(scope="module")
def coaching_css():
    return build_coaching_css()


@pytest.fixture(scope="module")
def coaching_js():
    return build_coaching_js()


# ── Page Generation ──────────────────────────────────────────


class TestPageGeneration:
    def test_returns_html(self, coaching_html):
        assert isinstance(coaching_html, str)
        assert "<!DOCTYPE html>" in coaching_html

    def test_has_canonical(self, coaching_html):
        assert 'rel="canonical"' in coaching_html
        assert "/coaching/" in coaching_html

    def test_has_ga4(self, coaching_html):
        assert "G-EJJZ9T6M52" in coaching_html
        assert "googletagmanager.com" in coaching_html

    def test_has_ab_snippet(self, coaching_html):
        assert "dataLayer" in coaching_html

    def test_has_jsonld(self, coaching_html):
        assert 'application/ld+json' in coaching_html
        assert '"@type":"WebPage"' in coaching_html
        assert '"@type":"Service"' in coaching_html

    def test_has_meta_robots(self, coaching_html):
        assert 'name="robots"' in coaching_html
        assert 'content="index, follow"' in coaching_html

    def test_has_meta_description(self, coaching_html):
        assert 'name="description"' in coaching_html

    def test_has_og_tags(self, coaching_html):
        assert 'og:title' in coaching_html
        assert 'og:description' in coaching_html

    def test_has_title(self, coaching_html):
        assert "<title>" in coaching_html
        assert "Coaching" in coaching_html


# ── Nav ──────────────────────────────────────────────────────


class TestNav:
    def test_nav_links(self, coaching_html):
        assert "/coaching/" in coaching_html
        assert "/about/" in coaching_html
        assert ">SERVICES</a>" in coaching_html
        assert ">ABOUT</a>" in coaching_html

    def test_breadcrumb(self, coaching_html):
        assert "gg-breadcrumb" in coaching_html
        assert "Coaching" in coaching_html

    def test_current_page_marker(self, coaching_html):
        assert 'aria-current="page"' in coaching_html
        assert 'aria-current="page">SERVICES</a>' in coaching_html


# ── Hero — "The Dossier" hero with corner CTA ───────────────


class TestHero:
    def test_hero_id(self):
        assert 'id="hero"' in build_hero()

    def test_hero_has_corner_cta(self):
        """Owner revision 2026-07-18: an obvious CTA on arrival, no scroll
        required. One link, the corner imperative."""
        hero = build_hero()
        assert 'class="gg-coach-hero-cta"' in hero
        assert 'data-cta="hero_apply"' in hero
        assert "GET ME IN YOUR CORNER" in hero

    def test_no_old_hero_artifacts(self):
        hero = build_hero()
        assert "gg-coach-file-strip" not in hero
        assert "TERMS OF WORK" not in hero
        assert "COURSES ON FILE" not in hero
        assert "Fitness is common" not in hero

    def test_headline(self):
        hero = build_hero()
        assert "You could be better than you think." in hero
        assert "That is not encouragement &mdash;" in hero
        assert "it&#39;s an observation about people who train alone." in hero

    def test_subhead(self):
        hero = build_hero()
        assert "The fix is a human in your corner." in hero
        assert "Not an AI, not a dashboard, not a coach who reads you like a spreadsheet." in hero
        assert "The terms are below." in hero


# ── Terms — five numbered clauses ───────────────────────────


class TestTerms:
    def test_terms_id(self):
        assert 'id="terms"' in build_terms()

    def test_five_clauses(self):
        t = build_terms()
        assert t.count('class="gg-coach-term"') == 5

    def test_clause_numbers(self):
        t = build_terms()
        for n in ("01", "02", "03", "04", "05"):
            assert f'<div class="gg-coach-term-num">{n}</div>' in t

    def test_clause_titles(self):
        t = build_terms()
        for title in (
            "Every file, read by a person",
            "The patterns you can&#39;t see",
            "The plan moves when your life does",
            "The truth, on schedule",
            "Involvement is the only variable",
        ):
            assert title in t

    def test_clause_bodies(self):
        t = build_terms()
        assert "I notice the interval you bailed on and ask why." in t
        assert "Knowledge isn&#39;t the limiter &mdash; application is." in t
        assert "the week adjusts that week" in t
        assert "&ldquo;You&#39;re sandbagging&rdquo; and &ldquo;take the rest week&rdquo;" in t
        assert "Same coach, same standards." in t

    def test_blindspot_sentence(self):
        """The blindspot clause is the load-bearing line of the Terms
        section — every athlete is their own worst blindspot."""
        t = build_terms()
        assert "their own worst blindspot" in t

    def test_last_clause_no_bottom_border(self, coaching_css):
        """Clause 05 has no border-bottom — tiers render immediately after
        with no visual gap, so the terms list must not double-close."""
        assert ".gg-coach-term:last-child" in coaching_css


# ── Full-Bleed Layout ────────────────────────────────────────


class TestFullBleedLayout:
    def test_container_override(self, coaching_css):
        assert "max-width: none" in coaching_css

    def test_inner_measure(self, coaching_css):
        assert "gg-coach-inner" in coaching_css
        assert "max-width: 1200px" in coaching_css

    def test_bands_present(self, coaching_html):
        assert 'class="gg-coach-band' in coaching_html
        assert "gg-coach-band--dark" in coaching_html

    def test_no_sand_band_anywhere(self, coaching_html, coaching_css):
        """gg-coach-band--sand is fully removed — tiers no longer sit on a
        sand background, they sit on the same paper as terms."""
        assert "gg-coach-band--sand" not in coaching_html
        assert "gg-coach-band--sand" not in coaching_css

    def test_all_sections_use_inner_wrapper(self, coaching_html):
        bands = coaching_html.count('<section class="gg-coach-band')
        inners = coaching_html.count('class="gg-coach-inner"')
        assert bands == inners == 6

    def test_terms_tiers_seamless(self, coaching_css):
        """Terms section has zero bottom padding, tiers section has zero
        top padding — the two must read as one continuous document, not
        two visually separated bands."""
        assert ".gg-coach-terms {\n  padding-bottom: 0;\n}" in coaching_css
        assert ".gg-coach-tiers-section {\n  padding-top: 0;\n}" in coaching_css

    def test_consent_banner_rendered(self, coaching_html):
        """Regression: an unescaped template tail would leave the literal
        placeholder string in the shipped HTML instead of the banner."""
        assert "{get_consent_banner_html()}" not in coaching_html


# ── Service Tiers ────────────────────────────────────────────


class TestServiceTiers:
    def test_tiers_id(self):
        assert 'id="tiers"' in build_tiers()

    def test_three_tier_columns(self):
        tiers = build_tiers()
        assert tiers.count('class="gg-coach-tier-col"') == 3
        assert "Min" in tiers
        assert "Mid" in tiers
        assert "Max" in tiers

    def test_prices(self):
        tiers = build_tiers()
        assert "$199" in tiers
        assert "$299" in tiers
        assert "$1,200" in tiers
        assert "/ 4 WEEKS" in tiers

    def test_get_started_links(self):
        tiers = build_tiers()
        assert tiers.count("GET STARTED") == 3
        assert 'data-cta="tier_min"' in tiers
        assert 'data-cta="tier_mid"' in tiers
        assert 'data-cta="tier_max"' in tiers
        assert f"{QUESTIONNAIRE_URL}?tier=min" in tiers
        assert f"{QUESTIONNAIRE_URL}?tier=mid" in tiers
        assert f"{QUESTIONNAIRE_URL}?tier=max" in tiers

    def test_setup_fee(self):
        tiers = build_tiers()
        assert "$99 setup fee" in tiers
        assert "TrainingPeaks Premium is included" in tiers
        assert "NOSETUP" not in tiers
        assert "privately, case by case" in tiers

    def test_disclaimer(self):
        tiers = build_tiers()
        assert "skipped workouts" in tiers
        assert "two business days" in tiers

    def test_feature_lists_verbatim(self):
        tiers = build_tiers()
        for item in (
            "Weekly training review", "File analysis", "Quarterly strategy calls",
            "Structured workouts for your trainer or head unit",
            "Race-day nutrition plan", "Custom training guide",
            "Everything in Min", "Detailed power-file analysis",
            "Every-4-week strategy calls", "Weekly plan adjustments",
            "Direct message access", "Blindspot detection",
            "Everything in Mid", "Daily file review", "On-demand calls",
            "Race-week strategy", "Multi-race season planning", "Priority response",
        ):
            assert item in tiers, f"Missing tier feature: {item}"

    def test_no_normie_jargon(self):
        """No raw jargon in tier feature lists (WKO, TSB, TSS, CTL)."""
        tiers = build_tiers()
        for term in ("WKO", "TSB", "TSS", "CTL"):
            assert term not in tiers, f"Raw jargon in tiers: {term}"

    def test_no_animation_on_tiers(self):
        """The Dossier is a still document — pricing must never depend on
        an observer firing."""
        assert 'data-animate' not in build_tiers()


# ── Fit check — three-question tier recommender ─────────────


def _fit_score_tier(q1: int, q2: int, q3) -> str:
    """Spec scoring, written independently of the page JS."""
    score = q1 + q2 + (1 if q3 == 2 else 0)
    if score <= 1:
        return "min"
    if score <= 3:
        return "mid"
    return "max"


def _fitcheck_js_iife(coaching_js: str) -> str:
    start = coaching_js.index("/* Fit check")
    end = coaching_js.index("/* Scroll depth tracking */")
    return coaching_js[start:end]


# Minimal DOM for the fit-check IIFE: just enough surface (hidden,
# attributes, classList, click listeners, the selectors the IIFE uses) to
# run the real script in Node and read back what it rendered.
_FITCHECK_DOM_HARNESS = r"""
const iife = process.argv[1];
const plan = JSON.parse(process.argv[2]);
function el(attrs, hidden) {
  const cls = new Set();
  return {
    hidden: !!hidden, attrs: Object.assign({}, attrs), listeners: [],
    getAttribute(n) { return n in this.attrs ? String(this.attrs[n]) : null; },
    setAttribute(n, v) { this.attrs[n] = String(v); },
    addEventListener(t, f) { if (t === 'click') this.listeners.push(f); },
    click() { this.listeners.forEach(function(f) { f(); }); },
    classList: {
      toggle(n, on) { if (on) cls.add(n); else cls.delete(n); },
      contains(n) { return cls.has(n); },
    },
  };
}
function run(clicks) {
  const events = [];
  global.gtag = function(kind, name, params) { events.push([name, params]); };
  const empty = el({}, false), answer = el({}, true), tight = el({}, true);
  const fits = [];
  ['min', 'mid', 'max'].forEach(function(t) { fits.push(el({'data-fit': t, kind: 'rec'}, true)); });
  ['min', 'mid', 'max'].forEach(function(t) { fits.push(el({'data-fit': t, kind: 'cta'}, true)); });
  const buttons = [];
  [1, 2, 3].forEach(function(q) {
    const group = [0, 1, 2].map(function(a) { return el({'data-q': q, 'data-a': a, 'aria-pressed': 'false'}); });
    const parent = { querySelectorAll: function() { return group; } };
    group.forEach(function(b) { b.parentNode = parent; buttons.push(b); });
  });
  const box = el({}, true);
  box.querySelector = function(sel) {
    return { '.gg-coach-fitcheck-empty': empty, '.gg-coach-fitcheck-answer': answer,
             '.gg-coach-fitcheck-tight': tight }[sel];
  };
  box.querySelectorAll = function(sel) {
    if (sel === '[data-fit]') return fits;
    if (sel === '.gg-coach-fitcheck-opt') return buttons;
    throw new Error('unexpected selector ' + sel);
  };
  const cols = ['min', 'mid', 'max'].map(function(t) {
    const c = el({'data-tier': t});
    const label = el({}, true);
    c.querySelector = function() { return label; };
    c.label = label;
    return c;
  });
  global.document = {
    getElementById: function(id) { return id === 'gg-coach-fitcheck' ? box : null; },
    querySelectorAll: function(sel) {
      if (sel === '.gg-coach-tier-col[data-tier]') return cols;
      throw new Error('unexpected selector ' + sel);
    },
  };
  new Function(iife)();
  const boxHiddenAfterInit = box.hidden;
  clicks.forEach(function(qa) {
    buttons.find(function(b) { return b.attrs['data-q'] == qa[0] && b.attrs['data-a'] == qa[1]; }).click();
  });
  return {
    boxHidden: boxHiddenAfterInit,
    emptyHidden: empty.hidden, answerHidden: answer.hidden, tightHidden: tight.hidden,
    recs: fits.filter(function(f) { return f.attrs.kind === 'rec' && !f.hidden; }).map(function(f) { return f.attrs['data-fit']; }),
    ctas: fits.filter(function(f) { return f.attrs.kind === 'cta' && !f.hidden; }).map(function(f) { return f.attrs['data-fit']; }),
    fitCols: cols.filter(function(c) { return c.classList.contains('gg-coach-is-fit'); }).map(function(c) { return c.attrs['data-tier']; }),
    fitLabels: cols.filter(function(c) { return !c.label.hidden; }).map(function(c) { return c.attrs['data-tier']; }),
    pressed: buttons.filter(function(b) { return b.attrs['aria-pressed'] === 'true'; }).map(function(b) { return [Number(b.attrs['data-q']), Number(b.attrs['data-a'])]; }),
    events: events,
  };
}
console.log(JSON.stringify(plan.map(run)));
"""


def _run_fitcheck(coaching_js: str, plans: list) -> list:
    import json
    result = subprocess.run(
        ["node", "-e", _FITCHECK_DOM_HARNESS, _fitcheck_js_iife(coaching_js), json.dumps(plans)],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"fit-check harness failed: {result.stderr}"
    return json.loads(result.stdout)


class TestFitCheck:
    """Tier recommender above the tier columns. Owner-voice copy is pinned
    verbatim; the whole block is JS-revealed so the no-JS page is
    unchanged."""

    @pytest.fixture(scope="class")
    def fit(self):
        return build_fit_check()

    def test_in_tiers_section_directly_above_columns(self):
        tiers = build_tiers()
        start = tiers.index('id="gg-coach-fitcheck"')
        assert tiers.index('id="tiers"') < start < tiers.index('class="gg-coach-tiers"')
        between = tiers[start:tiers.index('class="gg-coach-tiers"')]
        assert "gg-coach-tier-col" not in between

    def test_renders_hidden_for_no_js(self, fit, coaching_html):
        opening = '<div class="gg-coach-fitcheck" id="gg-coach-fitcheck" hidden>'
        assert fit.startswith(opening)
        assert coaching_html.count(opening) == 1

    def test_not_confused_with_fit_section(self, coaching_html):
        """The existing 'A fit, or not' section keeps id="fit"; the fit
        check must not collide with it or the scroll-depth label."""
        assert coaching_html.count('id="fit"') == 1
        assert 'id="gg-coach-fitcheck"' in coaching_html

    def test_three_labelled_groups(self, fit):
        groups = re.findall(r'<div class="gg-coach-fitcheck-opts" role="group" aria-labelledby="([\w-]+)">', fit)
        assert groups == ["gg-coach-fitcheck-q1", "gg-coach-fitcheck-q2", "gg-coach-fitcheck-q3"]
        for gid in groups:
            assert fit.count(f'id="{gid}"') == 1

    def test_nine_real_buttons_unpressed(self, fit):
        buttons = re.findall(r'<button\b[^>]*>', fit)
        assert len(buttons) == 9
        for b in buttons:
            assert 'type="button"' in b
            assert 'aria-pressed="false"' in b
        pairs = set(re.findall(r'data-q="(\d)" data-a="(\d)"', fit))
        assert pairs == {(str(q), str(a)) for q in (1, 2, 3) for a in (0, 1, 2)}

    def test_aria_live_result_region(self, fit):
        assert fit.count('aria-live="polite"') == 1
        assert '<div class="gg-coach-fitcheck-result" aria-live="polite">' in fit

    def test_data_tier_on_all_columns(self):
        tiers = build_tiers()
        for key in ("min", "mid", "max"):
            assert tiers.count(f'class="gg-coach-tier-col" data-tier="{key}"') == 1

    def test_your_fit_labels_prerendered_hidden(self):
        tiers = build_tiers()
        labels = re.findall(r'<span class="gg-coach-tier-fit-label"([^>]*)>YOUR FIT</span>', tiers)
        assert len(labels) == 3
        assert all(attrs.strip() == "hidden" for attrs in labels)

    def test_cta_href_and_tracking(self, fit):
        from urllib.parse import urlsplit, parse_qs
        ctas = re.findall(r'<a href="([^"]+)" class="gg-coach-fitcheck-cta" data-cta="([\w]+)" data-fit="(\w+)" hidden>([^<]+)</a>', fit)
        assert [c[2] for c in ctas] == ["min", "mid", "max"]
        for href, data_cta, key, label in ctas:
            assert href == f"{QUESTIONNAIRE_URL}?tier={key}&amp;src=fitcheck"
            assert data_cta == f"fitcheck_apply_{key}"
            assert label == f"APPLY FOR {key.upper()} &rarr;"
            # The apply page preselects via URLSearchParams.get("tier");
            # the extra src param must not disturb it.
            query = parse_qs(urlsplit(html.unescape(href)).query)
            assert query == {"tier": [key], "src": ["fitcheck"]}

    def test_result_states_all_start_hidden(self, fit):
        assert '<div class="gg-coach-fitcheck-answer" hidden>' in fit
        assert '<p class="gg-coach-fitcheck-tight" hidden>' in fit
        assert len(re.findall(r'data-fit="(?:min|mid|max)" hidden', fit)) == 6

    def test_name_and_price_match_tier_columns(self, fit):
        """Result name/price come from the same TIERS source as the
        columns, so they can't drift."""
        tiers = build_tiers()
        assert [(k, n, p) for k, n, p in TIERS] == [
            ("min", "Min", "$199"), ("mid", "Mid", "$299"), ("max", "Max", "$1,200"),
        ]
        for key, name, price in TIERS:
            assert f'<p class="gg-coach-fitcheck-tier">{name} <span class="gg-coach-fitcheck-price">{price} / 4 WEEKS</span></p>' in fit
            assert f'<div class="gg-coach-tier-name">{name} <span' in tiers
            assert f'<div class="gg-coach-tier-price">{price}<span class="gg-coach-tier-interval">/ 4 WEEKS</span></div>' in tiers

    @pytest.mark.parametrize("copy", [
        "Not sure which tier? Three questions, no email. I'll point you at the cheapest one that does the job.",
        "When a week goes sideways, you want…",
        "I'll adjust it myself. Check my work weekly.",
        "The plan moved that same week.",
        "Someone on it the same day.",
        "Your ride files should be…",
        "Skimmed. I know what I did.",
        "Read between sessions.",
        "Read every one, every day.",
        "Your A race is…",
        "16+ weeks out",
        "8–16 weeks out",
        "Under 8 weeks",
        "Answer the first two. The race date only changes what I tell you.",
        "YOU PROBABLY WANT",
        "You execute on your own and want the thinking done right. A weekly look is enough, and paying for attention you won't use is waste.",
        "You want the week to move when life does, not after. That's the whole gap between Min and Mid, and it's where most athletes land.",
        "You want every file read the day it lands. Worth it for one race that matters more than the rest. If this season isn't that, Mid covers it.",
        "Under 8 weeks is tight. I'll tell you straight if it's too late to change much.",
        "APPLY FOR MIN →",
        "APPLY FOR MID →",
        "APPLY FOR MAX →",
    ])
    def test_verbatim_copy(self, fit, copy):
        rendered = html.unescape(re.sub(r"<[^>]+>", "\n", fit))
        lines = {line.strip() for line in rendered.splitlines()}
        assert copy in lines, f"Fit-check copy missing or altered: {copy!r}"

    def test_css_hidden_beats_display_rules(self, coaching_css):
        """Toggled elements set their own display (grid, inline-flex,
        inline-block); without this override `hidden` would not hide them
        and the block would show with JS off."""
        assert ".gg-coach-tiers-section [hidden] {\n  display: none;\n}" in coaching_css

    def test_touch_targets(self, coaching_css):
        for selector in (".gg-coach-fitcheck-opt {", ".gg-coach-fitcheck-cta {"):
            block = coaching_css.split(selector, 1)[1].split("}", 1)[0]
            assert "min-height: 44px;" in block, selector

    def test_selected_state_is_solid_inverted(self, coaching_css):
        block = coaching_css.split('.gg-coach-fitcheck-opt[aria-pressed="true"] {', 1)[1].split("}", 1)[0]
        assert "background: var(--gg-color-dark-brown);" in block
        assert "color: var(--gg-color-warm-paper);" in block

    def test_fit_column_marked(self, coaching_css):
        assert ".gg-coach-tier-col.gg-coach-is-fit {" in coaching_css

    def test_focus_visible_not_suppressed(self, coaching_css):
        """Buttons and links get the shared focus ring
        (.gg-neo-brutalist-page button:focus-visible); nothing here may
        remove it."""
        from generate_neo_brutalist import get_page_css
        assert ".gg-neo-brutalist-page button:focus-visible" in get_page_css()
        assert ".gg-neo-brutalist-page a:focus-visible" in get_page_css()
        assert not re.search(r"outline:\s*(none|0)\b", coaching_css)

    def test_no_persistence(self, coaching_js):
        iife = _fitcheck_js_iife(coaching_js)
        assert "localStorage" not in iife
        assert "sessionStorage" not in iife
        assert "document.cookie" not in iife

    def test_analytics_events(self, coaching_js):
        iife = _fitcheck_js_iife(coaching_js)
        assert "gtag('event', 'coaching_fitcheck_answer', { question: q, answer: a })" in iife
        assert "gtag('event', 'coaching_fitcheck_result', { tier: tier })" in iife
        assert iife.count("typeof gtag === 'function'") == 2

    def test_js_selectors_exist_in_html(self, coaching_js, coaching_html):
        iife = _fitcheck_js_iife(coaching_js)
        for cls in set(re.findall(r"'\.(gg-coach-[\w-]+)", iife)):
            assert f'class="{cls}' in coaching_html or f' {cls}"' in coaching_html, cls

    def test_cta_listener_binds_fitcheck_ctas(self, coaching_js, fit):
        """cta_click binds once at load via querySelectorAll('[data-cta]').
        The fit-check CTAs are pre-rendered (hidden, never created later),
        so they are in the DOM when the listener binds."""
        assert "document.querySelectorAll('[data-cta]').forEach" in coaching_js
        assert "el.getAttribute('data-cta')" in coaching_js
        assert fit.count('data-cta="fitcheck_apply_') == 3
        assert "createElement" not in _fitcheck_js_iife(coaching_js)

    def test_scoring_every_combination(self, coaching_js):
        """Run the real IIFE against a DOM stub for every answer
        combination (Q3 unanswered or 0/1/2) and compare with the spec."""
        plans, expected = [], []
        for q1 in (0, 1, 2):
            for q2 in (0, 1, 2):
                for q3 in (None, 0, 1, 2):
                    clicks = [[1, q1], [2, q2]] + ([[3, q3]] if q3 is not None else [])
                    plans.append(clicks)
                    expected.append((_fit_score_tier(q1, q2, q3), q3 == 2))
        results = _run_fitcheck(coaching_js, plans)
        for clicks, (tier, tight), r in zip(plans, expected, results):
            assert r["boxHidden"] is False, clicks
            assert r["emptyHidden"] is True and r["answerHidden"] is False, clicks
            assert r["recs"] == [tier] and r["ctas"] == [tier], (clicks, r)
            assert r["fitCols"] == [tier] and r["fitLabels"] == [tier], (clicks, r)
            assert r["tightHidden"] is (not tight), clicks
            assert sorted(r["pressed"]) == sorted(clicks), clicks

    def test_named_combinations(self, coaching_js):
        cases = [
            ([[1, 0], [2, 0]], "min"),
            ([[1, 1], [2, 1]], "mid"),
            ([[1, 0], [2, 2]], "mid"),
            ([[1, 2], [2, 2]], "max"),
            ([[1, 1], [2, 2], [3, 2]], "max"),
            ([[1, 1], [2, 2]], "mid"),
        ]
        results = _run_fitcheck(coaching_js, [c for c, _ in cases])
        for (clicks, tier), r in zip(cases, results):
            assert r["recs"] == [tier], (clicks, r["recs"])

    def test_waits_for_first_two_answers(self, coaching_js):
        results = _run_fitcheck(coaching_js, [[], [[1, 2]], [[2, 2], [3, 2]]])
        for r in results:
            assert r["emptyHidden"] is False and r["answerHidden"] is True
            assert r["recs"] == [] and r["ctas"] == [] and r["fitCols"] == [] and r["fitLabels"] == []
            assert not [e for e in r["events"] if e[0] == "coaching_fitcheck_result"]
        # Q3 alone still surfaces its note, but no tier.
        assert results[2]["tightHidden"] is False

    def test_answers_change_live_and_result_fires_only_on_change(self, coaching_js):
        clicks = [[1, 0], [2, 0], [2, 0], [3, 0], [2, 2], [3, 2], [1, 2], [1, 0]]
        # min -> (same) -> (same) -> mid -> mid(3) -> max(5) -> mid(3)
        (r,) = _run_fitcheck(coaching_js, [clicks])
        answers = [e[1] for e in r["events"] if e[0] == "coaching_fitcheck_answer"]
        assert answers == [{"question": q, "answer": a} for q, a in clicks]
        tiers = [e[1]["tier"] for e in r["events"] if e[0] == "coaching_fitcheck_result"]
        assert tiers == ["min", "mid", "max", "mid"]
        assert r["recs"] == ["mid"] and r["fitCols"] == ["mid"]
        assert sorted(r["pressed"]) == [[1, 0], [2, 2], [3, 2]]


# ── A fit, or not ─────────────────────────────────────────────


class TestFit:
    def test_fit_id(self):
        assert 'id="fit"' in build_honest_check()

    def test_yes_no_columns(self):
        h = build_honest_check()
        assert "Coaching is for you if:" in h
        assert "It isn&#39;t:" in h

    def test_eight_list_items(self):
        h = build_honest_check()
        assert h.count("<li>") == 8

    def test_no_sand_bg(self):
        assert "gg-coach-band--sand" not in build_honest_check()


# ── FAQ ──────────────────────────────────────────────────────


class TestFAQ:
    def test_faq_id(self):
        assert 'id="faq"' in build_faq()

    def test_eight_questions(self):
        f = build_faq()
        assert f.count('class="gg-coach-faq-item"') == 8

    def test_accordion_toggle(self):
        f = build_faq()
        assert "gg-coach-faq-toggle" in f
        assert "gg-coach-faq-q" in f

    def test_setup_fee_faq(self):
        f = build_faq()
        assert "$99 setup fee" in f

    def test_has_aria(self):
        f = build_faq()
        assert 'aria-expanded' in f
        assert 'role="button"' in f


# ── Application close ────────────────────────────────────────


class TestApplicationClose:
    def test_final_cta_id(self):
        assert 'id="final-cta"' in build_application_close()

    def test_dark_band(self):
        assert "gg-coach-band--dark" in build_application_close()

    def test_kicker(self):
        assert "APPLICATION" in build_application_close()

    def test_line_copy(self):
        c = build_application_close()
        assert "Ten minutes of honest answers. I read every one myself." in c
        assert "usually hear from me within two business days" in c

    def test_cta_link(self):
        c = build_application_close()
        assert "GET ME IN YOUR CORNER &rarr;" in c
        assert f'href="{QUESTIONNAIRE_URL}"' in c
        assert 'data-cta="final_fill_intake"' in c

    def test_cta_border_is_paper_toned(self, coaching_css):
        assert "border: 1px solid var(--gg-color-warm-paper);" in coaching_css

    def test_contact_line(self):
        c = build_application_close()
        assert 'href="mailto:matt@gravelgodcycling.com"' in c
        assert "I answer myself, usually within a day." in c


# ── Mobile sticky CTA ────────────────────────────────────────


class TestMobileStickyCTA:
    def test_label_updated(self):
        sticky = build_mobile_sticky_cta()
        assert "GET ME IN YOUR CORNER &rarr;" in sticky
        assert "Apply for coaching" not in sticky

    def test_data_cta_and_href(self):
        sticky = build_mobile_sticky_cta()
        assert 'data-cta="sticky_cta"' in sticky
        assert f'href="{QUESTIONNAIRE_URL}"' in sticky


# ── Brand Compliance ─────────────────────────────────────────


class TestBrandCompliance:
    def test_no_hardcoded_hex_in_coaching_css(self, coaching_css):
        css = re.sub(r'/\*.*?\*/', '', coaching_css, flags=re.DOTALL)
        hex_colors = re.findall(r'#[0-9a-fA-F]{3,8}\b', css)
        assert len(hex_colors) == 0, f"Found hardcoded hex in coaching CSS: {hex_colors[:5]}"

    def test_no_border_radius(self, coaching_css):
        assert "border-radius" not in coaching_css

    def test_no_box_shadow(self, coaching_css):
        assert "box-shadow" not in coaching_css

    def test_uses_brand_tokens(self, coaching_css):
        assert "var(--gg-color-" in coaching_css
        assert "var(--gg-font-" in coaching_css

    def test_no_bounce_easing(self, coaching_css):
        assert "cubic-bezier(0.34, 1.56" not in coaching_css

    def test_no_gold_anywhere(self, coaching_css):
        """Prestige = restraint. Gold is not used anywhere in this page's
        own CSS — it stays reserved for header/footer chrome elsewhere."""
        assert "var(--gg-color-gold)" not in coaching_css

    def test_correct_class_prefix(self, coaching_css):
        allowed_roots = (
            'gg-coach-', 'gg-neo-brutalist', 'gg-site-header', 'gg-hero',
            'gg-section', 'gg-breadcrumb', 'gg-footer', 'gg-mega-footer',
            'gg-has-js', 'gg-in-view',
        )
        classes = set(re.findall(r'\.([a-zA-Z][\w-]*)', coaching_css))
        for cls in classes:
            assert cls.startswith(allowed_roots), (
                f"Non-prefixed class in coaching CSS: .{cls}"
            )


class TestTokenValidation:
    @pytest.fixture(scope="class")
    def defined_tokens(self):
        tokens_path = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("tokens.css not found")
        content = tokens_path.read_text()
        return set(re.findall(r'(--gg-[\w-]+)\s*:', content))

    def test_coaching_css_all_var_refs_defined(self, coaching_css, defined_tokens):
        used = set(re.findall(r'var\((--gg-[\w-]+)\)', coaching_css))
        undefined = used - defined_tokens
        assert not undefined, f"Undefined CSS tokens in coaching CSS: {undefined}"


# ── GA4 Events ───────────────────────────────────────────────


class TestGA4Events:
    def test_all_events_present(self, coaching_js):
        events = [
            "coaching_faq_open",
            "coaching_scroll_depth",
            "cta_click",
            "coaching_page_view",
        ]
        for event in events:
            assert event in coaching_js, f"Missing GA4 event: {event}"

    def test_no_carousel_events(self, coaching_js):
        assert "coaching_carousel" not in coaching_js

    def test_scroll_depth_section_ids_match_real_sections(self, coaching_js, coaching_html):
        """Every id referenced by the scroll-depth IIFE must exist in the
        shipped HTML, and the set must be exactly the six real content
        sections — no dead ids, no missing sections."""
        section_ids = re.findall(r"id:\s*'([\w-]+)'", coaching_js)
        assert set(section_ids) == {
            "hero", "terms", "tiers", "fit", "faq", "final-cta",
        }
        for sid in section_ids:
            assert f'id="{sid}"' in coaching_html, f"Dead section id in scroll-depth JS: {sid}"

    def test_old_section_labels_removed(self, coaching_js):
        for old_id in ("'problem'", "'deliverables'", "'how-it-works'", "'results'", "'honest-check'"):
            assert old_id not in coaching_js, f"Stale scroll-depth id still present: {old_id}"


# ── JS Syntax ────────────────────────────────────────────────


class TestJSSyntax:
    def test_js_parses_via_node(self, coaching_js):
        js_body = coaching_js.replace("<script>", "").replace("</script>", "")
        result = subprocess.run(
            [
                "node", "--input-type=module", "-e",
                "const src = process.argv[1];"
                "new Function(src);"
                "console.log('SYNTAX_OK');",
                js_body,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stdout} {result.stderr}"
        assert "SYNTAX_OK" in result.stdout


# ── JSON-LD ──────────────────────────────────────────────────


class TestJSONLD:
    def test_webpage_schema(self):
        ld = build_jsonld()
        assert '"@type":"WebPage"' in ld
        assert "/coaching/" in ld
        assert "Gravel God" in ld

    def test_service_schema(self):
        ld = build_jsonld()
        assert '"@type":"Service"' in ld
        assert "Gravel Race Coaching" in ld

    def test_uses_safe_json_for_script(self):
        """JSON-LD must go through _safe_json_for_script — a '</script>'
        payload should never be able to break out of the <script> tag."""
        from generate_neo_brutalist import _safe_json_for_script
        payload = {"a": "</script><script>alert(1)</script>"}
        safe = _safe_json_for_script(payload)
        assert "</script>" not in safe

    def test_no_raw_json_dumps_regression(self):
        """Regression guard: build_jsonld must not fall back to raw
        json.dumps — that would reopen the </script>-injection hole
        _safe_json_for_script exists to close."""
        import inspect
        from generate_coaching import build_jsonld as _build_jsonld
        source = inspect.getsource(_build_jsonld)
        assert "json.dumps(" not in source


# ── Accessibility ────────────────────────────────────────────


class TestAccessibility:
    def test_skip_to_content_link(self, coaching_html):
        assert 'class="gg-coach-skip-link"' in coaching_html
        assert 'Skip to content' in coaching_html

    def test_reduced_motion_css(self, coaching_css):
        assert "prefers-reduced-motion: reduce" in coaching_css

    def test_faq_aria_controls(self, coaching_html):
        assert 'aria-controls="gg-coach-faq-ans-' in coaching_html
        assert 'role="region"' in coaching_html


# ── Scroll Animations (shared guards) ───────────────────────
# The Dossier itself has no data-animate content — no fade-stagger,
# no entrance animations — but the shared scroll_animations module is
# still wired in for its .gg-has-js / .gg-in-view / IntersectionObserver
# guard contract used sitewide.


class TestScrollAnimationGuards:
    def test_no_data_animate_anywhere(self, coaching_html):
        """The Dossier is a still document — no entrance animations, no
        observer-gated content anywhere on the page. (The shared
        scroll_animations JS still references the bare `[data-animate]`
        selector as part of its generic observer wiring — that's fine;
        what matters is that no element actually carries the attribute.)"""
        assert 'data-animate="' not in coaching_html

    def test_reduced_motion_no_preference_guard(self, coaching_css):
        assert "prefers-reduced-motion: no-preference" in coaching_css

    def test_gg_has_js_in_js(self, coaching_js):
        assert "gg-has-js" in coaching_js

    def test_gg_in_view_in_js(self, coaching_js):
        assert "gg-in-view" in coaching_js

    def test_intersection_observer_in_js(self, coaching_js):
        assert "IntersectionObserver" in coaching_js


# ── Restraint Guard ──────────────────────────────────────────
# The page asserts; it doesn't perform. Banned substrings from the old
# loud template — and from the sibling-brand banned set — must never
# come back.


BANNED_SUBSTRINGS = [
    "$14.95",
    "/ride",
    "If you can pedal",
    "blown race",
    "costs you",
    "suffer smarter",
    "Not a Spreadsheet",
    "generated in 2 seconds",
    "Honest Check",
    "Can't Get From a Prompt",
]

# Checked against VISIBLE TEXT ONLY (script/style stripped, tags stripped) —
# these are generic words that can legitimately appear in class names,
# comments, or CSS without being loud marketing copy on the rendered page.
NEW_BANNED_VISIBLE_TEXT = [
    "unlock",
    "transform",
    "crush",
    "Fitness is common",
    "TERMS OF WORK",
    "COURSES ON FILE",
    "Not a Spreadsheet",
]

COURSE_COUNT_FLEX_PHRASES = [
    "757 courses",
    "757 races",
    "course profiles",
]


def _visible_text(html_doc: str) -> str:
    """Strip <script>...</script> and <style>...</style> blocks, then strip
    remaining HTML tags, leaving only what a reader actually sees."""
    no_script = re.sub(r'<script.*?</script>', '', html_doc, flags=re.DOTALL)
    no_style = re.sub(r'<style.*?</style>', '', no_script, flags=re.DOTALL)
    return re.sub(r'<[^>]+>', '', no_style)


class TestRestraintGuard:
    @pytest.mark.parametrize("phrase", BANNED_SUBSTRINGS)
    def test_banned_phrase_absent(self, coaching_html, phrase):
        assert phrase not in coaching_html, f"Banned phrase found in coaching page: {phrase!r}"

    @pytest.mark.parametrize("phrase", NEW_BANNED_VISIBLE_TEXT)
    def test_banned_visible_text_absent(self, coaching_html, phrase):
        visible = _visible_text(coaching_html)
        assert phrase not in visible, f"Banned word found in visible coaching page text: {phrase!r}"

    @pytest.mark.parametrize("phrase", COURSE_COUNT_FLEX_PHRASES)
    def test_no_course_count_flex_in_visible_text(self, coaching_html, phrase):
        visible = _visible_text(coaching_html)
        assert phrase not in visible, f"Course-count flex phrase in visible text: {phrase!r}"

    def test_no_exclamation_points_in_visible_text(self, coaching_html):
        visible = _visible_text(coaching_html)
        assert "!" not in visible, "Exclamation point found in visible coaching page text"

    def test_no_tire_comparison(self):
        tiers = build_tiers()
        assert "tires" not in tiers.lower()

    def test_no_coffee_cliche(self, coaching_html):
        lower = coaching_html.lower()
        assert "latte" not in lower
        assert "cup of" not in lower

    def test_no_slop_phrases(self, coaching_html):
        from slop_rules import check_text
        findings = check_text(coaching_html, is_html=True)
        assert not findings, f"Slop findings on coaching page: {findings}"

    def test_no_defensive_messaging(self, coaching_html):
        """Never 'no sponsors / not sponsored' framing — plants doubt."""
        lower = coaching_html.lower()
        assert "no sponsors" not in lower
        assert "not sponsored" not in lower
        assert "no affiliates" not in lower


# ── Required Content ─────────────────────────────────────────


class TestRequiredContent:
    def test_link_to_about(self, coaching_html):
        from generate_neo_brutalist import SITE_BASE_URL
        assert f"{SITE_BASE_URL}/about/" in coaching_html

    def test_apply_url_present(self, coaching_html):
        assert QUESTIONNAIRE_URL in coaching_html

    def test_questionnaire_url_shape(self):
        from generate_neo_brutalist import SITE_BASE_URL
        assert QUESTIONNAIRE_URL == f"{SITE_BASE_URL}/coaching/apply/"

    def test_disclaimer_and_setup_fee(self, coaching_html):
        assert "skipped workouts" in coaching_html
        assert "$99 setup fee" in coaching_html
        assert "TrainingPeaks Premium is included" in coaching_html
        assert "NOSETUP" not in coaching_html

    def test_hero_h1(self, coaching_html):
        assert "You could be better than you think." in coaching_html
        assert "it&#39;s an observation about people who train alone." in coaching_html

    def test_final_contact_line(self, coaching_html):
        assert "matt@gravelgodcycling.com" in coaching_html
        assert 'href="mailto:matt@gravelgodcycling.com"' in coaching_html
        assert "I answer myself, usually within a day." in coaching_html

    def test_removed_sections_absent(self, coaching_html):
        for old_id in ("how-it-works", "problem", "deliverables", "results", "honest-check"):
            assert f'id="{old_id}"' not in coaching_html
        assert "How it works" not in coaching_html

    def test_no_testimonials(self, coaching_html):
        assert coaching_html.count("<blockquote") == 0

    def test_all_section_ids_present(self, coaching_html):
        for sid in ("hero", "terms", "tiers", "fit", "faq", "final-cta"):
            assert f'id="{sid}"' in coaching_html
