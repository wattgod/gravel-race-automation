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
    PRICE_PER_WEEK,
    PRICE_CAP,
    QUESTIONNAIRE_URL,
    load_race_count,
    build_nav,
    build_hero,
    build_problem,
    build_service_tiers,
    build_deliverables,
    build_how_it_works,
    build_testimonials,
    build_honest_check,
    build_pricing,
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
def race_count():
    return load_race_count()


@pytest.fixture(scope="module")
def coaching_html():
    return generate_coaching_page()


@pytest.fixture(scope="module")
def coaching_css():
    return build_coaching_css()


@pytest.fixture(scope="module")
def coaching_js():
    return build_coaching_js()


# ── Data Loading ─────────────────────────────────────────────


class TestDataLoading:
    def test_race_count_loads(self, race_count):
        assert isinstance(race_count, int)
        assert race_count > 0

    def test_price_constants(self):
        assert PRICE_PER_WEEK == 15
        assert PRICE_CAP == 249


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
        # AB head snippet should be present (even if empty)
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


# ── Nav ──────────────────────────────────────────────────────


class TestNav:
    def test_nav_links(self, coaching_html):
        assert "/gravel-races/" in coaching_html
        assert "/coaching/" in coaching_html
        assert "/articles/" in coaching_html
        assert "/about/" in coaching_html

    def test_breadcrumb(self, coaching_html):
        assert "gg-breadcrumb" in coaching_html
        assert "Coaching" in coaching_html

    def test_current_page_marker(self, coaching_html):
        assert 'aria-current="page"' in coaching_html


# ── Hero ─────────────────────────────────────────────────────


class TestHero:
    def test_cta_present(self):
        hero = build_hero(328)
        assert "SEE OPTIONS" in hero
        assert "VIEW PRICING" in hero

    def test_stat_bar(self, race_count):
        hero = build_hero(race_count)
        assert str(race_count) in hero
        assert "$2/day" in hero
        assert "Same Day" in hero
        assert "1,000+" in hero

    def test_headline(self):
        hero = build_hero(328)
        assert "Stop Guessing" in hero


# ── Service Tiers ────────────────────────────────────────────


class TestServiceTiers:
    def test_three_tiers(self):
        tiers = build_service_tiers()
        assert "Race Prep Kit" in tiers
        assert "Custom Training Plan" in tiers
        assert "1:1 Coaching" in tiers

    def test_featured_tier(self):
        tiers = build_service_tiers()
        assert "gg-coach-tier-card--featured" in tiers
        assert "MOST POPULAR" in tiers

    def test_price_cap_mentioned(self):
        tiers = build_service_tiers()
        assert f"${PRICE_CAP}" in tiers

    def test_price_per_week(self):
        tiers = build_service_tiers()
        assert f"${PRICE_PER_WEEK}/week" in tiers


# ── Deliverables ─────────────────────────────────────────────


class TestDeliverables:
    def test_five_deliverables(self):
        d = build_deliverables()
        assert d.count("gg-coach-deliverable-num") == 5

    def test_sample_week_grid(self):
        d = build_deliverables()
        assert "gg-coach-sample-grid" in d
        assert "data-detail" in d

    def test_deliverable_titles(self):
        d = build_deliverables()
        assert "Structured Workouts" in d
        assert "Custom Training Guide" in d
        assert "Altitude" in d
        assert "Nutrition" in d
        assert "Strength" in d


# ── How It Works ─────────────────────────────────────────────


class TestHowItWorks:
    def test_three_steps(self):
        h = build_how_it_works()
        assert h.count("gg-coach-step-num") == 3

    def test_step_titles(self):
        h = build_how_it_works()
        assert "Tell Me About Your Race" in h
        assert "I Build Your Plan" in h
        assert "Open Your App" in h


# ── Testimonials ─────────────────────────────────────────────


class TestTestimonials:
    def test_carousel_present(self):
        t = build_testimonials()
        assert "gg-coach-carousel" in t
        assert "gg-coach-prev" in t
        assert "gg-coach-next" in t

    def test_fifty_plus_testimonials(self):
        t = build_testimonials()
        count = t.count("gg-coach-testimonial")
        # Each testimonial has multiple class references, but at least 50 blockquotes
        blockquotes = t.count("<blockquote")
        assert blockquotes >= 50


# ── Honest Check ─────────────────────────────────────────────


class TestHonestCheck:
    def test_buy_dont_buy_lists(self):
        h = build_honest_check()
        assert "Buy This If:" in h
        assert "Don&#39;t Buy This If:" in h

    def test_list_items_count(self):
        h = build_honest_check()
        li_count = h.count("<li>")
        assert li_count >= 8


# ── Pricing ──────────────────────────────────────────────────


class TestPricing:
    def test_price_displayed(self):
        p = build_pricing()
        assert f"${PRICE_PER_WEEK}" in p
        assert "/ week" in p

    def test_price_cap(self):
        p = build_pricing()
        assert f"${PRICE_CAP}" in p

    def test_anchoring_present(self):
        p = build_pricing()
        assert "$2/day" in p
        assert "entry fee" in p

    def test_guarantee(self):
        p = build_pricing()
        assert "refund" in p.lower()
        assert "7 day" in p.lower()

    def test_cta_present(self):
        p = build_pricing()
        assert "BUILD MY PLAN" in p


# ── FAQ ──────────────────────────────────────────────────────


class TestFAQ:
    def test_six_questions(self):
        f = build_faq()
        assert f.count("gg-coach-faq-item") == 6

    def test_accordion_toggle(self):
        f = build_faq()
        assert "gg-coach-faq-toggle" in f
        assert "gg-coach-faq-q" in f

    def test_has_aria(self):
        f = build_faq()
        assert 'aria-expanded' in f
        assert 'role="button"' in f


# ── Brand Compliance ─────────────────────────────────────────


class TestBrandCompliance:
    def test_no_hardcoded_hex_in_css(self, coaching_css):
        """CSS should use var(--gg-color-*) only — no raw hex codes."""
        # Extract just the CSS content (between <style> tags)
        css_match = re.search(r'<style>(.*?)</style>', coaching_css, re.DOTALL)
        if not css_match:
            pytest.skip("No CSS found")
        css = css_match.group(1)
        # Find all hex colors
        hex_colors = re.findall(r'#[0-9a-fA-F]{3,8}', css)
        assert len(hex_colors) == 0, f"Found hardcoded hex in CSS: {hex_colors[:5]}"

    def test_no_border_radius(self, coaching_css):
        assert "border-radius" not in coaching_css

    def test_no_box_shadow(self, coaching_css):
        assert "box-shadow" not in coaching_css

    def test_no_opacity_transition(self, coaching_css):
        """No opacity in transition declarations."""
        css_match = re.search(r'<style>(.*?)</style>', coaching_css, re.DOTALL)
        if not css_match:
            pytest.skip("No CSS found")
        css = css_match.group(1)
        # Check transition values don't include opacity
        transitions = re.findall(r'transition:\s*([^;]+);', css)
        for t in transitions:
            assert "opacity" not in t.lower(), f"Found opacity transition: {t}"

    def test_uses_brand_tokens(self, coaching_css):
        assert "var(--gg-color-" in coaching_css
        assert "var(--gg-font-" in coaching_css

    def test_no_entrance_animations(self, coaching_css):
        """No CSS keyframe entrance animations (opacity 0→1 or translateY on load)."""
        assert "@keyframes" not in coaching_css

    def test_correct_class_prefix(self, coaching_css):
        """All custom classes use gg-coach- prefix."""
        # Find all class selectors
        classes = re.findall(r'\.(gg-[a-z][a-z0-9-]*)', coaching_css)
        for cls in classes:
            # Allow shared gg-neo-brutalist-page, gg-site-header, gg-hero, gg-section, etc.
            if cls.startswith(('gg-neo-brutalist', 'gg-site-header', 'gg-hero',
                              'gg-section', 'gg-breadcrumb', 'gg-footer')):
                continue
            assert cls.startswith('gg-coach-'), f"Non-prefixed class in coaching CSS: .{cls}"

    def test_no_bounce_easing(self, coaching_css):
        """No cubic-bezier bounce/spring easing."""
        assert "cubic-bezier(0.34, 1.56" not in coaching_css


# ── GA4 Events ───────────────────────────────────────────────


class TestGA4Events:
    def test_all_events_present(self, coaching_js):
        events = [
            "coaching_page_view",
            "coaching_scroll_depth",
            "coaching_cta_click",
            "coaching_faq_open",
            "coaching_sample_week_click",
        ]
        for event in events:
            assert event in coaching_js, f"Missing GA4 event: {event}"


# ── JS Syntax ────────────────────────────────────────────────


class TestJSSyntax:
    def test_js_parses_via_node(self, coaching_js):
        """Validate JS syntax via Node.js subprocess."""
        # Strip <script> tags
        js = coaching_js.replace("<script>", "").replace("</script>", "")
        test_script = f"""
try {{
    new Function({json.dumps(js)});
    console.log('SYNTAX_OK');
}} catch(e) {{
    console.log('SYNTAX_ERROR: ' + e.message);
    process.exit(1);
}}
"""
        result = subprocess.run(
            ["node", "-e", test_script],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"JS syntax error: {result.stdout} {result.stderr}"
        assert "SYNTAX_OK" in result.stdout


# ── JSON-LD ──────────────────────────────────────────────────


class TestJSONLD:
    def test_webpage_schema(self):
        ld = build_jsonld(328)
        assert '"@type":"WebPage"' in ld
        assert "/coaching/" in ld

    def test_service_schema(self):
        ld = build_jsonld(328)
        assert '"@type":"Service"' in ld
        assert str(PRICE_PER_WEEK) in ld
