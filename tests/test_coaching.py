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

import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_coaching import (
    QUESTIONNAIRE_URL,
    build_nav,
    build_hero,
    build_terms,
    build_tiers,
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

    def test_disclaimer(self):
        tiers = build_tiers()
        assert "skipped workouts" in tiers
        assert "24 hours" in tiers

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
        assert "You&#39;ll hear from me within 48 hours &mdash; including if I don&#39;t think coaching is what you need." in c

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
            "coaching_cta_click",
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
