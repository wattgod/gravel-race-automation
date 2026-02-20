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

    def test_billing_interval(self):
        tiers = build_service_tiers()
        assert "/4 WK" in tiers
        assert tiers.count("/4 WK") == 3
        assert "/MO" not in tiers

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

    def test_setup_fee_note(self):
        tiers = build_service_tiers()
        assert "gg-coach-tier-setup-fee" in tiers
        assert "$99 setup fee" in tiers


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
                              'gg-section', 'gg-breadcrumb', 'gg-footer',
                              'gg-mega-footer')):
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


# ── CSS Token Validation ────────────────────────────────────


class TestCssTokenValidation:
    """Every var(--gg-*) reference in coaching CSS must be defined in tokens.css."""

    @pytest.fixture(scope="class")
    def defined_tokens(self):
        tokens_path = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("Brand tokens not available")
        text = tokens_path.read_text()
        return set(re.findall(r'--(gg-[a-z0-9-]+)', text))

    def test_all_var_refs_defined(self, coaching_css, defined_tokens):
        """No undefined var(--gg-*) references — prevents silent CSS failures."""
        css_match = re.search(r'<style>(.*?)</style>', coaching_css, re.DOTALL)
        if not css_match:
            pytest.skip("No CSS found")
        css = css_match.group(1)
        refs = set(re.findall(r'var\(--(gg-[a-z0-9-]+)\)', css))
        undefined = refs - defined_tokens
        assert not undefined, f"Undefined CSS tokens in coaching CSS: {undefined}"


# ── Accessibility ───────────────────────────────────────────


class TestAccessibility:
    def test_faq_aria_expanded_reset(self, coaching_js):
        """FAQ JS must reset aria-expanded on all siblings when opening a new item."""
        assert "setAttribute('aria-expanded', 'false')" in coaching_js
        # The reset must happen inside the forEach loop, not just on the clicked item
        js = coaching_js.replace("<script>", "").replace("</script>", "")
        # The forEach that removes gg-coach-faq-open should also reset aria-expanded
        assert "classList.remove('gg-coach-faq-open')" in js
        # Both operations must be in the same forEach
        foreach_match = re.search(r"items\.forEach\(function\(i\)\s*\{([^}]+)\}", js)
        assert foreach_match, "No forEach loop found for FAQ items"
        foreach_body = foreach_match.group(1)
        assert "aria-expanded" in foreach_body, (
            "aria-expanded reset must happen inside forEach loop, not just on clicked item"
        )

    def test_no_month_in_billing_context(self, coaching_html):
        """No 'monthly' or '/mo' in billing/pricing context. 'Monthly' for call cadence is OK."""
        assert "/MO" not in coaching_html
        assert "$199/month" not in coaching_html.lower()
        assert "$299/month" not in coaching_html.lower()
        assert "per month" not in coaching_html.lower()

    def test_skip_to_content_link(self, coaching_html):
        """Page has a skip-to-content link for keyboard navigation."""
        assert 'class="gg-coach-skip-link"' in coaching_html
        assert 'Skip to content' in coaching_html

    def test_carousel_aria_live(self, coaching_html):
        """Carousel counter has aria-live for screen reader notifications."""
        assert 'aria-live="polite"' in coaching_html

    def test_carousel_keyboard_pause(self, coaching_js):
        """Carousel pauses on keyboard focus (focusin), not just mouse hover."""
        assert "focusin" in coaching_js
        assert "focusout" in coaching_js

    def test_carousel_respects_reduced_motion(self, coaching_js):
        """Carousel auto-advance respects prefers-reduced-motion."""
        assert "prefers-reduced-motion" in coaching_js

    def test_reduced_motion_css(self, coaching_css):
        """CSS includes prefers-reduced-motion media query."""
        assert "prefers-reduced-motion: reduce" in coaching_css

    def test_faq_aria_controls(self, coaching_html):
        """FAQ questions have aria-controls linking to answer regions."""
        assert 'aria-controls="gg-coach-faq-ans-' in coaching_html
        assert 'role="region"' in coaching_html

    def test_no_dead_btn_teal_css(self, coaching_css):
        """Dead .gg-coach-btn--teal CSS has been removed."""
        assert "gg-coach-btn--teal" not in coaching_css

    def test_faq_uses_brand_easing(self, coaching_css):
        """FAQ transition uses brand token, not raw ease."""
        css_match = re.search(r'<style>(.*?)</style>', coaching_css, re.DOTALL)
        if not css_match:
            pytest.skip("No CSS found")
        css = css_match.group(1)
        # FAQ max-height transition should use brand token
        assert "max-height 0.3s ease" not in css
        assert "max-height var(--gg-transition-hover)" in css

    def test_scroll_depth_covers_all_sections(self, coaching_js):
        """Scroll depth tracking covers all 9 page sections."""
        for section_id in ["hero", "problem", "tiers", "deliverables",
                          "how-it-works", "honest-check", "faq", "final-cta"]:
            assert f"id: '{section_id}'" in coaching_js, f"Missing scroll depth for {section_id}"

    def test_no_monthly_calls_wording(self):
        """Mid tier should not say 'Monthly calls' — use 'Every-4-week' instead."""
        tiers = build_service_tiers()
        assert "Monthly calls" not in tiers
        assert "Monthly strategy" not in tiers
        assert "Every-4-week" in tiers

    def test_tier_ctas_pass_tier_param(self):
        """Each tier CTA links to apply page with ?tier= query param."""
        tiers = build_service_tiers()
        assert "?tier=min" in tiers
        assert "?tier=mid" in tiers
        assert "?tier=max" in tiers

    def test_cancellation_faq_exists(self):
        """FAQ must include a cancellation question for subscription transparency."""
        faq = build_faq()
        assert "cancel" in faq.lower()
        assert "No contracts" in faq or "no contracts" in faq

    def test_carousel_ga4_tracking(self, coaching_js):
        """Carousel prev/next/auto-advance should fire GA4 events."""
        assert "coaching_carousel" in coaching_js
        assert "direction: 'prev'" in coaching_js
        assert "direction: 'next'" in coaching_js
        assert "direction: 'auto'" in coaching_js

    def test_sticky_cta_scroll_based(self, coaching_css, coaching_js):
        """Mobile sticky CTA should be hidden by default and shown after scrolling past hero."""
        assert "gg-coach-sticky-visible" in coaching_css
        assert "gg-coach-sticky-visible" in coaching_js
        assert "visibility: hidden" in coaching_css
        assert "pointer-events: none" in coaching_css


# ── Sultanic Copy Guard ────────────────────────────────────────


class TestSultanicCopyGuard:
    """Verify psychological upgrade copy is present, accurate, and brand-compliant."""

    def test_problem_comparison_ignition(self):
        """Problem quotes should contain comparison-state language."""
        problem = build_problem()
        assert "rider who passed you" in problem, "Missing comparison ignition in quote 1"
        assert "paid for structure and got a spreadsheet" in problem, "Missing comparison ignition in quote 2"
        assert "hour you train without direction" in problem, "Missing cost-of-inaction in quote 3"

    def test_pricing_context_honest_math(self):
        """Cost-per-ride math must be truthful (based on 5 rides/week)."""
        tiers = build_service_tiers()
        assert "gg-coach-tier-context" in tiers, "Missing pricing context element"
        # Must NOT contain the false $10/ride claim
        assert "$10/ride" not in tiers, "False $10/ride math must be removed"
        # Must contain honest math
        assert "$14.95/ride" in tiers, "Missing honest per-ride cost"
        assert "5 rides a week" in tiers, "Missing ride frequency assumption"

    def test_pricing_no_coffee_cliche(self):
        """Pricing context must not use 'coffee' or 'latte' comparisons."""
        tiers = build_service_tiers()
        lower = tiers.lower()
        assert "coffee" not in lower, "Coffee cliché violates brand voice"
        assert "latte" not in lower, "Latte cliché violates brand voice"
        assert "cup of" not in lower, "Cup-of-X cliché violates brand voice"

    def test_deliverable_story_engineering(self):
        """Deliverables should contain transformation language."""
        deliverables = build_deliverables()
        assert "finish line" in deliverables, "Missing transformation outcome in deliverable 01"
        assert "adapt in real time" in deliverables, "Missing real-time adaptation in deliverable 02"

    def test_honest_check_investment_framing(self):
        """Honest check should contain bike/engine investment comparison."""
        check = build_honest_check()
        assert "invested in the bike" in check, "Missing investment framing in yes-column"
        assert "faster bike" in check, "Missing bike-vs-engine in no-column"

    def test_final_cta_cost_of_inaction(self):
        """Final CTA should quantify cost of NOT coaching."""
        cta = build_final_cta()
        assert "gg-coach-final-cost" in cta, "Missing cost-of-inaction element"
        assert "blown race costs you months" in cta, "Missing cost-of-inaction copy"
        assert "wasted training block" in cta, "Missing training block reference"

    def test_tier_context_css_exists(self):
        """Tier context element must have CSS styling."""
        css = build_coaching_css()
        assert "gg-coach-tier-context" in css, "Missing CSS for tier context"

    def test_final_cost_css_exists(self):
        """Final cost element must have CSS styling."""
        css = build_coaching_css()
        assert "gg-coach-final-cost" in css, "Missing CSS for final cost"

    def test_honest_check_yes_count(self):
        """Yes-column should have 6 items (original 5 + investment)."""
        check = build_honest_check()
        yes_items = re.findall(r'<li>.*?</li>', check[:check.find('--no')])
        assert len(yes_items) == 6, f"Expected 6 yes-items, got {len(yes_items)}"

    def test_honest_check_no_count(self):
        """No-column should have 5 items (original 4 + faster bike)."""
        check = build_honest_check()
        no_section = check[check.find('--no'):]
        no_items = re.findall(r'<li>.*?</li>', no_section)
        assert len(no_items) == 5, f"Expected 5 no-items, got {len(no_items)}"
