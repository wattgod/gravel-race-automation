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

    def test_no_old_pricing_in_meta(self, coaching_html):
        """No $15/week or $249 references in meta/OG tags."""
        assert "$15/week" not in coaching_html
        assert "$249" not in coaching_html


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
        hero = build_hero()
        assert "APPLY NOW" in hero
        assert "SEE HOW IT WORKS" in hero

    def test_stat_line(self):
        hero = build_hero()
        assert "Juniors" in hero
        assert "If you can pedal" in hero
        assert "gg-coach-stat-line" in hero

    def test_no_stat_bar(self):
        hero = build_hero()
        assert "gg-coach-stat-bar" not in hero
        assert "gg-coach-stat-item" not in hero

    def test_headline(self):
        hero = build_hero()
        assert "Algorithm" in hero


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

    def test_cadence_lines(self):
        tiers = build_service_tiers()
        assert "Weekly review" in tiers
        assert "Daily review" in tiers

    def test_section_title(self):
        tiers = build_service_tiers()
        assert "Same Coach. Same Standards. Different Involvement." in tiers

    def test_disclaimer(self):
        tiers = build_service_tiers()
        assert "skip workouts" in tiers
        assert "24 hours" in tiers

    def test_all_ctas_get_started(self):
        tiers = build_service_tiers()
        assert tiers.count("GET STARTED") == 3

    def test_no_old_tiers(self):
        tiers = build_service_tiers()
        assert "Race-Ready Plan" not in tiers
        assert "Ongoing Coaching" not in tiers
        assert "Race Consult" not in tiers


# ── Deliverables ─────────────────────────────────────────────


class TestDeliverables:
    def test_five_deliverables(self):
        d = build_deliverables()
        assert d.count("gg-coach-deliverable-num") == 5

    def test_no_sample_week(self):
        d = build_deliverables()
        assert "gg-coach-sample-grid" not in d
        assert "data-detail" not in d
        assert "gg-coach-sample-week" not in d

    def test_deliverable_titles(self):
        d = build_deliverables()
        assert "I Read Your File" in d
        assert "Your Plan Changes When Your Life Does" in d
        assert "Honest Feedback" in d
        assert "I Know What It Feels Like" in d
        assert "Race Strategy" in d


# ── How It Works ─────────────────────────────────────────────


class TestHowItWorks:
    def test_three_steps(self):
        h = build_how_it_works()
        assert h.count("gg-coach-step-num") == 3

    def test_step_titles(self):
        h = build_how_it_works()
        assert "Fill Out the Intake" in h
        assert "We Align on a Plan" in h
        assert "We Train Together" in h


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
    def test_coaching_for_you_lists(self):
        h = build_honest_check()
        assert "Coaching Is For You If:" in h
        assert "Coaching Isn&#39;t For You If:" in h

    def test_list_items_count(self):
        h = build_honest_check()
        li_count = h.count("<li>")
        assert li_count >= 8


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

    def test_kicker_number(self):
        f = build_faq()
        assert ">07<" in f


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

    def test_no_sample_week_css(self, coaching_css):
        """Sample week CSS should be removed."""
        assert "gg-coach-sample" not in coaching_css
        assert "gg-coach-block--" not in coaching_css
        assert "gg-coach-active" not in coaching_css

    def test_no_pricing_css(self, coaching_css):
        """Pricing CSS should be removed."""
        assert "gg-coach-pricing" not in coaching_css

    def test_no_stat_bar_css(self, coaching_css):
        """Stat bar CSS should be removed."""
        assert "gg-coach-stat-bar" not in coaching_css
        assert "gg-coach-stat-item" not in coaching_css


# ── GA4 Events ───────────────────────────────────────────────


class TestGA4Events:
    def test_all_events_present(self, coaching_js):
        events = [
            "coaching_page_view",
            "coaching_scroll_depth",
            "coaching_cta_click",
            "coaching_faq_open",
        ]
        for event in events:
            assert event in coaching_js, f"Missing GA4 event: {event}"

    def test_no_sample_week_event(self, coaching_js):
        assert "coaching_sample_week_click" not in coaching_js


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
