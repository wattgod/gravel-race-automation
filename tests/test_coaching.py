"""Tests for the Gravel God coaching page generator."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_coaching import (
    QUESTIONNAIRE_URL,
    FEATURED_TESTIMONIAL_NAMES,
    build_nav,
    build_hero,
    build_problem,
    build_service_tiers,
    build_deliverables,
    build_how_it_works,
    build_testimonials,
    build_honest_check,
    build_faq,
    build_final_cta,
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
        assert "Coaching" in coaching_html or "Training" in coaching_html

    def test_no_old_pricing_in_meta(self, coaching_html):
        assert "$15/week" not in coaching_html
        assert "$249" not in coaching_html


# ── Nav ──────────────────────────────────────────────────────


class TestNav:
    def test_nav_links(self, coaching_html):
        assert "/gravel-races/" in coaching_html
        assert "/coaching/" in coaching_html
        assert "/articles/" in coaching_html
        assert "/about/" in coaching_html
        assert ">RACES</a>" in coaching_html
        assert ">PRODUCTS</a>" in coaching_html
        assert ">SERVICES</a>" in coaching_html
        assert ">ARTICLES</a>" in coaching_html
        assert ">ABOUT</a>" in coaching_html

    def test_nav_dropdowns(self, coaching_html):
        assert "gg-site-header-dropdown" in coaching_html
        assert "gg-site-header-item" in coaching_html

    def test_breadcrumb(self, coaching_html):
        assert "gg-breadcrumb" in coaching_html
        assert "Coaching" in coaching_html

    def test_current_page_marker(self, coaching_html):
        assert 'aria-current="page"' in coaching_html
        assert 'aria-current="page">SERVICES</a>' in coaching_html


# ── Hero ─────────────────────────────────────────────────────


class TestHero:
    def test_cta_present(self):
        hero = build_hero()
        assert ">Apply</a>" in hero
        assert "How it works" in hero

    def test_stat_line(self):
        hero = build_hero()
        assert "757 courses analyzed" in hero
        assert "One coach" in hero
        assert "gg-coach-stat-line" in hero

    def test_no_stat_bar(self):
        hero = build_hero()
        assert "gg-coach-stat-bar" not in hero
        assert "gg-coach-stat-item" not in hero

    def test_headline(self):
        hero = build_hero()
        assert "Preparation is rare" in hero

    def test_no_gold_chip(self):
        """The kicker is plain text — no inline gold background badge."""
        hero = build_hero()
        assert "style=" not in hero
        assert "gg-hero-tier" not in hero


# ── Full-Bleed Layout ────────────────────────────────────────


class TestFullBleedLayout:
    def test_container_override(self, coaching_css):
        """Coaching page unsets the shared 960px container."""
        assert "max-width: none" in coaching_css

    def test_inner_measure(self, coaching_css):
        assert "gg-coach-inner" in coaching_css
        assert "max-width: 1200px" in coaching_css

    def test_header_footer_aligned_to_measure(self, coaching_css):
        """Shared header/footer inner wrappers are widened to match."""
        assert ".gg-neo-brutalist-page .gg-site-header-inner" in coaching_css
        assert ".gg-neo-brutalist-page .gg-mega-footer-grid" in coaching_css

    def test_bands_present(self, coaching_html):
        assert 'class="gg-coach-band' in coaching_html
        assert "gg-coach-band--sand" in coaching_html
        assert "gg-coach-band--dark" in coaching_html

    def test_all_sections_use_inner_wrapper(self, coaching_html):
        bands = coaching_html.count('<section class="gg-coach-band')
        inners = coaching_html.count('class="gg-coach-inner"')
        assert bands == inners == 9

    def test_consent_banner_rendered(self, coaching_html):
        """Regression: the template tail was a non-f-string, leaving the
        literal '{get_consent_banner_html()}' in the shipped HTML."""
        assert "{get_consent_banner_html()}" not in coaching_html


# ── Service Tiers ────────────────────────────────────────────


class TestServiceTiers:
    def test_three_tiers(self):
        tiers = build_service_tiers()
        assert "Min" in tiers
        assert "Mid" in tiers
        assert "Max" in tiers

    def test_featured_tier(self):
        tiers = build_service_tiers()
        assert "gg-coach-tier-card--featured" in tiers

    def test_prices(self):
        tiers = build_service_tiers()
        assert "$199" in tiers
        assert "$299" in tiers
        assert "$1,200" in tiers

    def test_billing_interval(self):
        tiers = build_service_tiers()
        assert "/4 WK" in tiers
        assert tiers.count("/4 WK") == 3
        assert "/MO" not in tiers

    def test_tier_descriptors(self):
        tiers = build_service_tiers()
        assert "thinking done right" in tiers
        assert "Most athletes belong here" in tiers
        assert "nothing left to chance" in tiers

    def test_section_title(self):
        tiers = build_service_tiers()
        assert "Same coach. Three levels of involvement." in tiers

    def test_disclaimer(self):
        tiers = build_service_tiers()
        assert "skipped workouts" in tiers
        assert "24 hours" in tiers

    def test_all_ctas_get_started(self):
        tiers = build_service_tiers()
        assert tiers.count("Get started") == 3

    def test_no_old_tiers(self):
        tiers = build_service_tiers()
        assert "Race-Ready Plan" not in tiers
        assert "Ongoing Coaching" not in tiers
        assert "Race Consult" not in tiers

    def test_setup_fee_note(self):
        tiers = build_service_tiers()
        assert "gg-coach-tier-setup-fee" in tiers
        assert "$99 setup fee" in tiers

    def test_normie_safe_features(self):
        """No raw jargon in tier feature lists (WKO, TSB, FTP...)."""
        tiers = build_service_tiers()
        for term in ("WKO", "TSB", "FTP", "TSS", "CTL"):
            assert term not in tiers, f"Raw jargon in tiers: {term}"


# ── Deliverables ─────────────────────────────────────────────


class TestDeliverables:
    def test_four_deliverables(self):
        d = build_deliverables()
        assert d.count('<div class="gg-coach-deliverable">') == 4

    def test_no_sample_week(self):
        d = build_deliverables()
        assert "gg-coach-sample-grid" not in d
        assert "data-detail" not in d
        assert "gg-coach-sample-week" not in d

    def test_deliverable_titles(self):
        d = build_deliverables()
        assert "Every file, read by a person" in d
        assert "A plan that moves when your life does" in d
        assert "Honest feedback" in d
        assert "Race strategy from course data" in d

    def test_no_self_mythology(self):
        """The 'I've made every mistake' card was cut — it performs."""
        d = build_deliverables()
        assert "Every Mistake" not in d
        assert "blown up at mile 80" not in d


# ── How It Works ─────────────────────────────────────────────


class TestHowItWorks:
    def test_four_steps(self):
        h = build_how_it_works()
        assert h.count("gg-coach-step-num") == 4

    def test_step_titles(self):
        h = build_how_it_works()
        assert "Fill out the intake" in h
        assert "I build your first block" in h
        assert "We train" in h
        assert "We sharpen toward race day" in h

    def test_honest_selectivity_line(self):
        """The 48-hour reply promise includes the not-a-fit clause."""
        h = build_how_it_works()
        assert "48 hours" in h
        assert "if I don&#39;t think coaching is what you need" in h


# ── Testimonials ─────────────────────────────────────────────


class TestTestimonials:
    def test_static_grid_not_carousel(self):
        t = build_testimonials()
        assert "gg-coach-testimonials" in t
        assert "gg-coach-carousel" not in t
        assert "gg-coach-prev" not in t
        assert "gg-coach-next" not in t

    def test_three_curated(self):
        t = build_testimonials()
        assert t.count("<blockquote") == 3
        for name in FEATURED_TESTIMONIAL_NAMES:
            assert name in t, f"Missing featured testimonial: {name}"

    def test_link_to_full_set(self):
        t = build_testimonials()
        assert "/about/" in t
        assert "fifty athletes" in t


# ── Honest Check ─────────────────────────────────────────────


class TestHonestCheck:
    def test_coaching_for_you_lists(self):
        h = build_honest_check()
        assert "Coaching is for you if:" in h
        assert "It isn&#39;t:" in h

    def test_list_items_count(self):
        h = build_honest_check()
        li_count = h.count("<li>")
        assert li_count == 8


# ── FAQ ──────────────────────────────────────────────────────


class TestFAQ:
    def test_eight_questions(self):
        f = build_faq()
        assert f.count("gg-coach-faq-item") == 8

    def test_accordion_toggle(self):
        f = build_faq()
        assert "gg-coach-faq-toggle" in f
        assert "gg-coach-faq-q" in f

    def test_setup_fee_faq(self):
        f = build_faq()
        assert "$99 setup fee" in f
        assert "one-time charge" in f

    def test_has_aria(self):
        f = build_faq()
        assert 'aria-expanded' in f
        assert 'role="button"' in f

    def test_kicker_number(self):
        f = build_faq()
        assert ">07<" in f


# ── Brand Compliance ─────────────────────────────────────────


class TestBrandCompliance:
    def test_no_hardcoded_hex_in_css(self, coaching_css):
        css = re.sub(r'/\*.*?\*/', '', coaching_css, flags=re.DOTALL)
        hex_colors = re.findall(r'#[0-9a-fA-F]{3,8}\b', css)
        assert len(hex_colors) == 0, f"Found hardcoded hex in CSS: {hex_colors[:5]}"

    def test_no_border_radius(self, coaching_css):
        assert "border-radius" not in coaching_css

    def test_no_box_shadow(self, coaching_css):
        assert "box-shadow" not in coaching_css

    def test_no_opacity_on_hover_transitions(self, coaching_css):
        transitions = re.findall(
            r':hover[^\{]*\{[^\}]*transition:([^;]+);', coaching_css
        )
        for t in transitions:
            assert "opacity" not in t.lower(), f"Found opacity in hover transition: {t}"

    def test_uses_brand_tokens(self, coaching_css):
        assert "var(--gg-color-" in coaching_css
        assert "var(--gg-font-" in coaching_css

    def test_no_entrance_animations(self, coaching_css):
        css_before_scroll = coaching_css.split("gg-has-js")[0]
        assert "@keyframes" not in css_before_scroll

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

    def test_no_bounce_easing(self, coaching_css):
        assert "cubic-bezier(0.34, 1.56" not in coaching_css

    def test_no_sample_week_css(self, coaching_css):
        assert "gg-coach-sample" not in coaching_css
        assert "gg-coach-block--" not in coaching_css
        assert "gg-coach-active" not in coaching_css

    def test_no_pricing_css(self, coaching_css):
        assert "gg-coach-pricing" not in coaching_css

    def test_no_stat_bar_css(self, coaching_css):
        assert "gg-coach-stat-bar" not in coaching_css
        assert "gg-coach-stat-item" not in coaching_css

    def test_no_carousel_css(self, coaching_css):
        assert "gg-coach-carousel" not in coaching_css


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
        """Carousel removed — no auto-play or nav events remain."""
        assert "coaching_carousel" not in coaching_js

    def test_no_sample_week_event(self, coaching_js):
        assert "coaching_sample_week_click" not in coaching_js


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

    def test_service_schema(self):
        ld = build_jsonld()
        assert '"@type":"Service"' in ld
        assert "Gravel Race Coaching" in ld

    def test_no_offers_block(self):
        ld = build_jsonld()
        assert '"offers"' not in ld
        assert "$15" not in ld


# ── CSS Token Validation ─────────────────────────────────────


class TestCssTokenValidation:
    @pytest.fixture(scope="class")
    def defined_tokens(self):
        tokens_path = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("tokens.css not found")
        content = tokens_path.read_text()
        return set(re.findall(r'(--gg-[\w-]+)\s*:', content))

    def test_all_var_refs_defined(self, coaching_css, defined_tokens):
        used = set(re.findall(r'var\((--gg-[\w-]+)\)', coaching_css))
        undefined = used - defined_tokens
        assert not undefined, f"Undefined CSS tokens in coaching CSS: {undefined}"


# ── Accessibility ────────────────────────────────────────────


class TestAccessibility:
    def test_faq_aria_expanded_reset(self, coaching_js):
        assert "setAttribute('aria-expanded', 'false')" in coaching_js

    def test_faq_close_resets_all(self, coaching_js):
        js = coaching_js
        assert "classList.remove('gg-coach-faq-open')" in js
        foreach_match = re.search(
            r"items\.forEach\(function\(i\)\s*\{([^}]+)\}", js
        )
        assert foreach_match, "No forEach loop found for FAQ items"
        foreach_body = foreach_match.group(1)
        assert "aria-expanded" in foreach_body, (
            "FAQ close-all must also reset aria-expanded"
        )

    def test_no_month_in_billing_context(self, coaching_html):
        assert "/MO" not in coaching_html
        assert "$199/month" not in coaching_html.lower()
        assert "$299/month" not in coaching_html.lower()
        assert "per month" not in coaching_html.lower()

    def test_skip_to_content_link(self, coaching_html):
        assert 'class="gg-coach-skip-link"' in coaching_html
        assert 'Skip to content' in coaching_html

    def test_reduced_motion_css(self, coaching_css):
        assert "prefers-reduced-motion: reduce" in coaching_css

    def test_faq_aria_controls(self, coaching_html):
        assert 'aria-controls="gg-coach-faq-ans-' in coaching_html
        assert 'role="region"' in coaching_html

    def test_no_dead_btn_teal_css(self, coaching_css):
        assert "gg-coach-btn--teal" not in coaching_css

    def test_faq_uses_brand_easing(self, coaching_css):
        css = coaching_css
        assert "max-height 0.3s ease" not in css
        assert "max-height var(--gg-transition-hover)" in css

    def test_scroll_depth_covers_all_sections(self, coaching_js):
        section_ids = [
            "hero", "problem", "deliverables", "how-it-works", "tiers",
            "results", "honest-check", "faq", "final-cta",
        ]
        for section_id in section_ids:
            assert f"id: '{section_id}'" in coaching_js, f"Missing scroll depth for {section_id}"

    def test_no_monthly_calls_wording(self):
        tiers = build_service_tiers()
        assert "Monthly calls" not in tiers
        assert "Monthly strategy" not in tiers
        assert "Every-4-week" in tiers

    def test_tier_ctas_pass_tier_param(self):
        tiers = build_service_tiers()
        assert "?tier=min" in tiers
        assert "?tier=mid" in tiers
        assert "?tier=max" in tiers

    def test_cancellation_faq_exists(self):
        faq = build_faq()
        assert "cancel" in faq.lower()
        assert "No contracts" in faq or "no contracts" in faq

    def test_sticky_cta_scroll_based(self, coaching_css, coaching_js):
        assert "gg-coach-sticky-visible" in coaching_css
        assert "gg-coach-sticky-visible" in coaching_js
        assert "visibility: hidden" in coaching_css
        assert "pointer-events: none" in coaching_css


# ── Scroll Animations ────────────────────────────────────────


class TestScrollAnimations:
    def test_fade_stagger_on_tiers(self):
        html = build_service_tiers()
        assert 'data-animate="fade-stagger"' in html

    def test_fade_stagger_on_deliverables(self):
        html = build_deliverables()
        assert 'data-animate="fade-stagger"' in html

    def test_fade_stagger_on_steps(self):
        html = build_how_it_works()
        assert 'data-animate="fade-stagger"' in html

    def test_no_animation_on_hero(self):
        html = build_hero()
        assert 'data-animate' not in html

    def test_no_animation_on_problem_prose(self):
        html = build_problem()
        assert 'data-animate' not in html

    def test_no_animation_on_testimonials(self):
        html = build_testimonials()
        assert 'data-animate' not in html

    def test_no_animation_on_final_cta(self):
        html = build_final_cta()
        assert 'data-animate' not in html

    def test_css_has_reduced_motion_guard(self, coaching_css):
        assert "prefers-reduced-motion: no-preference" in coaching_css

    def test_css_has_gg_has_js_guard(self, coaching_css):
        assert ".gg-has-js" in coaching_css

    def test_css_has_gg_in_view(self, coaching_css):
        assert ".gg-in-view" in coaching_css

    def test_js_has_intersection_observer(self, coaching_js):
        assert "IntersectionObserver" in coaching_js

    def test_js_adds_gg_has_js(self, coaching_js):
        assert "gg-has-js" in coaching_js

    def test_js_unobserves_after_trigger(self, coaching_js):
        assert "unobserve" in coaching_js


# ── Restraint Guard ──────────────────────────────────────────
# The page asserts; it doesn't perform. These tests keep the
# gimmicks from creeping back in.


class TestRestraintGuard:
    def test_no_per_ride_math(self, coaching_html):
        """Price stands without a cost-per-ride defense."""
        assert "/ride" not in coaching_html
        assert "$14.95" not in coaching_html
        assert "rides a week" not in coaching_html

    def test_no_tire_comparison(self):
        tiers = build_service_tiers()
        assert "tires" not in tiers.lower()

    def test_no_coffee_cliche(self, coaching_html):
        lower = coaching_html.lower()
        assert "latte" not in lower
        assert "cup of" not in lower

    def test_no_pedal_zinger(self, coaching_html):
        assert "If you can pedal" not in coaching_html

    def test_no_cost_of_inaction_stack(self):
        """Final CTA closes quietly — no 'blown race costs months' punch."""
        cta = build_final_cta()
        assert "blown race" not in cta
        assert "costs you" not in cta
        assert "gg-coach-final-cost" not in cta

    def test_final_cta_honest_selectivity(self):
        cta = build_final_cta()
        assert "I read every one myself" in cta
        assert "48 hours" in cta

    def test_tiers_honest_fit_line(self):
        tiers = build_service_tiers()
        assert "I&#39;ll tell you within 24 hours" in tiers

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

    def test_no_uppercase_on_prose(self, coaching_css):
        """text-transform: uppercase only on structural labels, never prose."""
        uppercase_rules = re.findall(
            r'([^\{\}]+)\{[^\}]*text-transform:\s*uppercase[^\}]*\}',
            coaching_css, re.DOTALL
        )
        allowed_patterns = [
            'kicker', 'stat-line', 'sticky-cta', 'gg-coach-btn',
        ]
        for rule in uppercase_rules:
            selector = rule.strip().split('\n')[-1].strip()
            is_allowed = any(p in selector for p in allowed_patterns)
            assert is_allowed, (
                f"text-transform: uppercase on prose element: {selector}\n"
                f"Coaching copy is sentence case; the page doesn't shout."
            )

    def test_serif_section_titles(self, coaching_css):
        """Section titles are editorial serif, not shouted mono caps."""
        m = re.search(r'\.gg-coach-sec-title\s*\{([^}]+)\}', coaching_css)
        assert m, "Missing gg-coach-sec-title rule"
        body = m.group(1)
        assert "var(--gg-font-editorial)" in body
        assert "uppercase" not in body
