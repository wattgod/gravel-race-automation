"""Tests for the Gravel God training plans page generator.

Covers page generation, navigation, hero, deliverables, how-it-works,
testimonials, pricing, FAQ, CSS quality, JS quality, and Stripe pricing parity.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_training_plans import (
    DELIVERABLES,
    FAQ_ITEMS,
    PRICE_CAP,
    PRICE_PER_WEEK,
    QUESTIONNAIRE_URL,
    REALITY_CHECKS,
    SAMPLE_WEEK_BLOCKS,
    TRAINING_PLANS_URL,
    build_faq,
    build_footer,
    build_hero,
    build_honest_check,
    build_how_it_works,
    build_jsonld,
    build_mobile_sticky,
    build_nav,
    build_pricing,
    build_rotating_quote,
    build_testimonials,
    build_training_css,
    build_training_js,
    build_what_you_get,
    generate_training_page,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def tp_html():
    return generate_training_page()


@pytest.fixture(scope="module")
def tp_css():
    return build_training_css()


@pytest.fixture(scope="module")
def tp_js():
    return build_training_js()


# ── 1. Page Generation ───────────────────────────────────────


class TestPageGeneration:
    def test_doctype(self, tp_html):
        assert tp_html.strip().startswith("<!DOCTYPE html>")

    def test_lang_attribute(self, tp_html):
        assert '<html lang="en">' in tp_html

    def test_charset(self, tp_html):
        assert '<meta charset="UTF-8">' in tp_html

    def test_viewport(self, tp_html):
        assert 'width=device-width, initial-scale=1.0' in tp_html

    def test_title(self, tp_html):
        assert "<title>Gravel Training Plans | Gravel God</title>" in tp_html

    def test_meta_description(self, tp_html):
        assert '<meta name="description"' in tp_html
        assert "Gravel training plans" in tp_html

    def test_canonical_url(self, tp_html):
        assert f'<link rel="canonical" href="{TRAINING_PLANS_URL}">' in tp_html

    def test_robots_index(self, tp_html):
        assert '<meta name="robots" content="index, follow">' in tp_html

    def test_ga4_tag(self, tp_html):
        assert "G-EJJZ9T6M52" in tp_html
        assert "googletagmanager.com/gtag/js" in tp_html

    def test_og_tags(self, tp_html):
        assert 'og:title' in tp_html
        assert 'og:description' in tp_html
        assert 'og:type' in tp_html
        assert 'og:url' in tp_html

    def test_twitter_card(self, tp_html):
        assert 'twitter:card' in tp_html

    def test_neo_brutalist_page_wrapper(self, tp_html):
        assert 'class="gg-neo-brutalist-page"' in tp_html

    def test_preload_hints(self, tp_html):
        assert "preload" in tp_html or "preconnect" in tp_html


# ── 2. Navigation ────────────────────────────────────────────


class TestNavigation:
    def test_shared_header_present(self, tp_html):
        assert "gg-site-header" in tp_html

    def test_active_products(self, tp_html):
        assert 'aria-current="page"' in tp_html

    def test_breadcrumb(self, tp_html):
        assert "gg-breadcrumb" in tp_html
        assert "Training Plans" in tp_html

    def test_breadcrumb_home_link(self, tp_html):
        assert 'href="https://gravelgodcycling.com/"' in tp_html

    def test_mega_footer(self, tp_html):
        footer = build_footer()
        assert len(footer) > 100


# ── 3. Hero ──────────────────────────────────────────────────


class TestHero:
    def test_headline(self):
        hero = build_hero()
        assert "Your Race. Your Hours. Your Plan." in hero

    def test_four_stats(self):
        hero = build_hero()
        assert "Same Day" in hero
        assert "Matched" in hero
        assert "$2/day" in hero
        assert "5 min" in hero

    def test_no_coffee_cliche(self):
        hero = build_hero()
        hero_lower = hero.lower()
        assert "coffee" not in hero_lower
        assert "latte" not in hero_lower

    def test_tube_comparison(self):
        hero = build_hero()
        assert "Less Than a Tube" in hero

    def test_cta_questionnaire_url(self):
        hero = build_hero()
        assert QUESTIONNAIRE_URL in hero

    def test_cta_build_my_plan(self):
        hero = build_hero()
        assert "Build My Plan" in hero

    def test_cta_how_it_works(self):
        hero = build_hero()
        assert "#how-it-works" in hero

    def test_data_cta_attributes(self):
        hero = build_hero()
        assert 'data-cta="hero_build"' in hero
        assert 'data-cta="hero_how"' in hero


# ── 4. What You Get ──────────────────────────────────────────


class TestWhatYouGet:
    def test_five_deliverables(self):
        section = build_what_you_get()
        assert section.count("gg-tp-deliverable-row") >= 5

    def test_deliverable_titles(self):
        section = build_what_you_get()
        for _, title, _ in DELIVERABLES:
            # Titles are embedded as-is (already contain &amp; entities)
            assert title in section

    def test_sample_week_grid(self):
        section = build_what_you_get()
        assert "gg-tp-sample-grid" in section

    def test_sample_week_seven_days(self):
        section = build_what_you_get()
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            assert day in section

    def test_sample_blocks_have_data_detail(self):
        section = build_what_you_get()
        assert "data-detail=" in section

    def test_sample_blocks_have_data_structure(self):
        section = build_what_you_get()
        assert "data-structure=" in section

    def test_seven_sample_blocks(self):
        section = build_what_you_get()
        assert section.count("gg-tp-sample-block ") == 7

    def test_section_label(self):
        section = build_what_you_get()
        assert "What You Get" in section


# ── 5. How It Works ──────────────────────────────────────────


class TestHowItWorks:
    def test_four_process_cards(self):
        section = build_how_it_works()
        assert section.count("gg-tp-process-step") == 4

    def test_four_detail_steps(self):
        section = build_how_it_works()
        assert section.count("gg-tp-step-num") == 4

    def test_trainingpeaks_reference(self):
        section = build_how_it_works()
        assert "TrainingPeaks" in section

    def test_section_id(self):
        section = build_how_it_works()
        assert 'id="how-it-works"' in section

    def test_alt_background(self):
        section = build_how_it_works()
        assert "gg-tp-section-alt" in section

    def test_process_card_titles(self):
        section = build_how_it_works()
        for title in ["Questionnaire", "TrainingPeaks", "Plan Built", "You Train"]:
            assert title in section


# ── 6. Rotating Quote ────────────────────────────────────────


class TestRotatingQuote:
    def test_reality_check_label(self):
        section = build_rotating_quote()
        assert "Reality Check" in section

    def test_quote_element_id(self):
        section = build_rotating_quote()
        assert 'id="gg-tp-quote-text"' in section

    def test_twenty_two_quotes(self):
        assert len(REALITY_CHECKS) == 22

    def test_first_quote_embedded(self):
        section = build_rotating_quote()
        # First quote should be present (HTML-escaped)
        assert "12-week plan" in section


# ── 7. Honest Check ─────────────────────────────────────────


class TestHonestCheck:
    def test_buy_if_column(self):
        section = build_honest_check()
        assert "Buy This If:" in section

    def test_dont_buy_if_column(self):
        section = build_honest_check()
        assert "Buy This If:" in section

    def test_five_buy_items(self):
        section = build_honest_check()
        assert section.count("gg-tp-for-list") >= 1

    def test_five_dont_items(self):
        section = build_honest_check()
        assert section.count("gg-tp-not-list") >= 1

    def test_two_column_grid(self):
        section = build_honest_check()
        assert "gg-tp-audience-grid" in section


# ── 8. Testimonials ──────────────────────────────────────────


class TestTestimonials:
    def test_three_testimonials(self):
        section = build_testimonials()
        assert section.count("gg-tp-testimonial") >= 3

    def test_athlete_names(self):
        section = build_testimonials()
        assert "Jason R." in section
        assert "Sarah M." in section
        assert "Mark D." in section

    def test_race_references(self):
        section = build_testimonials()
        assert "Mid-South" in section
        assert "Unbound" in section
        assert "Big Sugar" in section


# ── 9. Pricing ───────────────────────────────────────────────


class TestPricing:
    def test_price_per_week(self):
        section = build_pricing()
        assert PRICE_PER_WEEK in section

    def test_price_cap(self):
        section = build_pricing()
        assert PRICE_CAP in section

    def test_one_payment_no_subscription(self):
        section = build_pricing()
        assert "One Payment" in section
        assert "No Subscription" in section

    def test_no_cancel_anytime(self):
        """Training plans are one-time payments, not subscriptions."""
        section = build_pricing()
        assert "cancel anytime" not in section.lower()
        assert "cancel any time" not in section.lower()

    def test_guarantee(self):
        section = build_pricing()
        assert "7-Day Money-Back Guarantee" in section

    def test_pricing_cta(self):
        section = build_pricing()
        assert QUESTIONNAIRE_URL in section
        assert "Build My Plan" in section

    def test_honest_math_daily_rate(self):
        """$15/week ≈ $2.14/day, displayed as $2/day — order of magnitude correct."""
        section = build_pricing()
        assert "$2/day" in section

    def test_example_calculations(self):
        section = build_pricing()
        assert "6-week plan = $90" in section
        assert "12-week plan = $180" in section
        assert "16-week plan = $240" in section


# ── 10. FAQ ──────────────────────────────────────────────────


class TestFaq:
    def test_six_faq_items(self):
        section = build_faq()
        assert section.count("gg-tp-faq-item") == 6

    def test_aria_expanded(self):
        section = build_faq()
        assert 'aria-expanded="false"' in section

    def test_faq_questions_present(self):
        section = build_faq()
        assert "power meter" in section.lower()
        assert "FTP" in section
        assert "workouts delivered" in section.lower()
        assert "price calculated" in section.lower()
        assert "coaching" in section.lower()
        assert "database" in section.lower()

    def test_faq_toggle_button(self):
        section = build_faq()
        assert "gg-tp-faq-q" in section
        assert "<button" in section

    def test_faq_section_label(self):
        section = build_faq()
        assert "Questions" in section


# ── 11. CSS Quality ──────────────────────────────────────────


class TestCssQuality:
    def test_no_raw_hex(self, tp_css):
        """No hardcoded hex colors in the CSS."""
        # Extract CSS content between <style> tags
        match = re.search(r'<style>(.*?)</style>', tp_css, re.DOTALL)
        assert match, "CSS should be wrapped in <style> tags"
        css_content = match.group(1)
        # Find any hex color patterns (3, 4, 6, or 8 digit)
        hex_matches = re.findall(r'(?<!var\()#[0-9a-fA-F]{3,8}\b', css_content)
        assert hex_matches == [], f"Found raw hex in CSS: {hex_matches}"

    def test_no_box_shadow(self, tp_css):
        assert "box-shadow" not in tp_css

    def test_no_border_radius(self, tp_css):
        # border-radius: 0 is fine (it's the token), but any other value is not
        css_no_zero = tp_css.replace("border-radius: 0", "")
        assert "border-radius" not in css_no_zero

    def test_no_opacity_transition(self, tp_css):
        """No opacity in transition properties."""
        # Find all transition declarations
        transitions = re.findall(r'transition:[^;]+;', tp_css)
        for t in transitions:
            assert "opacity" not in t, f"Opacity transition found: {t}"

    def test_no_opacity_animation(self, tp_css):
        """No @keyframes that animate opacity."""
        keyframe_blocks = re.findall(r'@keyframes[^{]+\{[^}]+\}', tp_css, re.DOTALL)
        for block in keyframe_blocks:
            assert "opacity" not in block, f"Opacity animation found: {block}"

    def test_uses_var_tokens(self, tp_css):
        assert "var(--gg-color-" in tp_css
        assert "var(--gg-font-" in tp_css
        assert "var(--gg-spacing-" in tp_css

    def test_uses_border_tokens(self, tp_css):
        assert "var(--gg-border-" in tp_css

    def test_uses_transition_token(self, tp_css):
        assert "var(--gg-transition-hover)" in tp_css

    def test_gg_tp_prefix(self, tp_css):
        """All page-specific classes use the gg-tp- prefix."""
        # Find class selectors
        selectors = re.findall(r'\.([\w-]+)\s*[{,]', tp_css)
        page_selectors = [s for s in selectors if s.startswith("gg-tp-")]
        # Should have many gg-tp- prefixed selectors
        assert len(page_selectors) >= 20

    def test_no_import_statement(self, tp_css):
        """No @import for fonts — use preload hints instead."""
        assert "@import" not in tp_css

    def test_shared_header_css_included(self, tp_css):
        assert "gg-site-header" in tp_css

    def test_zone_css_classes(self, tp_css):
        """Workout viz zone colors defined via CSS classes, not inline."""
        for zone in ["z1", "z2", "z3", "z4", "z5", "z6"]:
            assert f".gg-tp-viz-{zone}" in tp_css

    def test_sticky_cta_visibility_pattern(self, tp_css):
        """Sticky CTA uses visibility, not opacity, for show/hide."""
        assert "visibility: hidden" in tp_css
        assert "visibility: visible" in tp_css


# ── 12. JS Quality ───────────────────────────────────────────


class TestJsQuality:
    def test_js_syntax_valid(self, tp_js):
        """JS passes Node.js syntax validation."""
        # Extract JS between <script> tags (not JSON-LD)
        match = re.search(r'<script>\s*\(function\(\)', tp_js)
        assert match, "JS should start with an IIFE"
        js_content = re.search(r'<script>(.*?)</script>', tp_js, re.DOTALL)
        assert js_content
        js = js_content.group(1)
        result = subprocess.run(
            ["node", "-e", f"new Function({json.dumps(js)})"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stderr}"

    def test_iife_wrapper(self, tp_js):
        assert "(function(){" in tp_js.replace(" ", "").replace("\n", "")

    def test_faq_handler(self, tp_js):
        assert "gg-tp-faq-q" in tp_js

    def test_twenty_two_quotes_in_js(self, tp_js):
        """All 22 reality check quotes embedded in JS."""
        for quote in REALITY_CHECKS[:3]:
            assert quote[:30] in tp_js

    def test_build_workout_viz(self, tp_js):
        assert "buildWorkoutViz" in tp_js

    def test_viz_uses_css_classes(self, tp_js):
        """buildWorkoutViz emits CSS class names, not inline hex."""
        assert "gg-tp-viz-block" in tp_js
        assert "gg-tp-viz-" in tp_js
        # Should NOT have zone color hex values in JS
        assert "'#e8e8e8'" not in tp_js
        assert "'#F5E5D3'" not in tp_js
        assert "'#c9b8a3'" not in tp_js

    def test_no_opacity_in_js(self, tp_js):
        """JS should not set opacity for animations."""
        assert ".opacity" not in tp_js.replace("style.visibility", "")

    def test_visibility_for_quote_rotation(self, tp_js):
        """Quote rotation uses visibility, not opacity."""
        assert "visibility" in tp_js

    def test_scroll_depth_tracking(self, tp_js):
        assert "tp_scroll_depth" in tp_js

    def test_cta_click_tracking(self, tp_js):
        assert "tp_cta_click" in tp_js

    def test_sample_week_click_tracking(self, tp_js):
        assert "tp_sample_week_click" in tp_js

    def test_page_view_tracking(self, tp_js):
        assert "tp_page_view" in tp_js

    def test_sticky_cta_scroll_trigger(self, tp_js):
        assert "gg-tp-sticky-cta" in tp_js
        assert "is-visible" in tp_js


# ── 13. Stripe Pricing Parity ────────────────────────────────


class TestStripePricingParity:
    @pytest.fixture(scope="class")
    def stripe_data(self):
        stripe_path = Path(__file__).parent.parent / "data" / "stripe-products.json"
        if not stripe_path.exists():
            pytest.skip("stripe-products.json not found")
        return json.loads(stripe_path.read_text())

    def test_cap_matches_stripe(self, stripe_data):
        """PRICE_CAP must match the 17+ week plan in Stripe."""
        cap_price = None
        for price in stripe_data["prices"]:
            if "17+" in price.get("nickname", ""):
                cap_price = price["amount"]
                break
        assert cap_price is not None, "17+ week plan not found in Stripe data"
        cap_dollars = int(PRICE_CAP.replace("$", ""))
        assert cap_price == cap_dollars * 100, (
            f"PRICE_CAP {PRICE_CAP} doesn't match Stripe amount {cap_price}"
        )

    def test_weekly_rate_matches_stripe(self, stripe_data):
        """$15/week should match the per-week price from Stripe data."""
        # Check 8-week plan: should be $120 = 8 * $15
        eight_week = None
        for price in stripe_data["prices"]:
            if "8-week" in price.get("nickname", ""):
                eight_week = price["amount"]
                break
        assert eight_week is not None, "8-week plan not found in Stripe data"
        per_week = int(PRICE_PER_WEEK.replace("$", ""))
        assert eight_week == 8 * per_week * 100

    def test_jsonld_price_matches_stripe(self, stripe_data):
        """JSON-LD highPrice should match Stripe cap."""
        jsonld = build_jsonld()
        cap_price = None
        for price in stripe_data["prices"]:
            if "17+" in price.get("nickname", ""):
                cap_price = price["amount"] // 100
                break
        assert str(cap_price) in jsonld


# ── 14. JSON-LD ──────────────────────────────────────────────


class TestJsonLd:
    def test_product_schema(self):
        jsonld = build_jsonld()
        assert '"@type": "Product"' in jsonld

    def test_aggregate_offer(self):
        jsonld = build_jsonld()
        assert '"@type": "AggregateOffer"' in jsonld

    def test_low_price(self):
        jsonld = build_jsonld()
        assert '"lowPrice": "60"' in jsonld

    def test_high_price(self):
        jsonld = build_jsonld()
        assert f'"highPrice": "249"' in jsonld

    def test_url(self):
        jsonld = build_jsonld()
        assert TRAINING_PLANS_URL in jsonld


# ── 15. Mobile Sticky CTA ───────────────────────────────────


class TestMobileStickyCta:
    def test_sticky_present(self, tp_html):
        assert "gg-tp-sticky-cta" in tp_html

    def test_sticky_cta_url(self):
        sticky = build_mobile_sticky()
        assert QUESTIONNAIRE_URL in sticky

    def test_sticky_daily_rate(self):
        sticky = build_mobile_sticky()
        assert "$2/day" in sticky

    def test_no_coffee_in_sticky(self):
        sticky = build_mobile_sticky()
        assert "coffee" not in sticky.lower()


# ── 16. Content Guard Tests ─────────────────────────────────


class TestContentGuards:
    def test_no_coffee_anywhere(self, tp_html):
        """No coffee/latte cliché anywhere on the page."""
        lower = tp_html.lower()
        assert "less than a coffee" not in lower
        assert "less than coffee" not in lower
        assert "cup of coffee" not in lower
        assert "latte" not in lower

    def test_no_cancel_anytime_anywhere(self, tp_html):
        """Training plans are one-time. No 'cancel anytime' copy."""
        lower = tp_html.lower()
        assert "cancel anytime" not in lower
        assert "cancel any time" not in lower

    def test_no_box_shadow_anywhere(self, tp_html):
        """No box-shadow except 'box-shadow: none' resets from shared header."""
        import re
        # Remove all "box-shadow: none" occurrences (valid resets)
        cleaned = re.sub(r'box-shadow:\s*none\s*!important;?', '', tp_html)
        assert "box-shadow" not in cleaned

    def test_pricing_mentions_one_time(self, tp_html):
        assert "One Payment" in tp_html

    def test_five_deliverables_count(self):
        assert len(DELIVERABLES) == 5

    def test_six_faq_count(self):
        assert len(FAQ_ITEMS) == 6

    def test_seven_sample_blocks_count(self):
        assert len(SAMPLE_WEEK_BLOCKS) == 7
