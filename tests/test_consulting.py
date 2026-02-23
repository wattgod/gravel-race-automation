"""Tests for the Gravel God consulting page generator."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_consulting import (
    CONSULTING_PRICE,
    CONSULTING_PRICE_INT,
    CONSULTING_DURATION,
    build_nav,
    build_hero,
    build_what_you_get,
    build_bio,
    build_testimonials,
    build_how_it_works,
    build_topics,
    build_faq,
    build_final_cta,
    build_footer,
    build_consulting_css,
    build_consulting_js,
    build_jsonld,
    generate_consulting_page,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def consulting_html():
    return generate_consulting_page()


@pytest.fixture(scope="module")
def consulting_css():
    return build_consulting_css()


@pytest.fixture(scope="module")
def consulting_js():
    return build_consulting_js()


# ── Page Generation ──────────────────────────────────────────


class TestPageGeneration:
    def test_returns_html(self, consulting_html):
        assert isinstance(consulting_html, str)
        assert "<!DOCTYPE html>" in consulting_html

    def test_has_canonical(self, consulting_html):
        assert 'rel="canonical"' in consulting_html
        assert "/consulting/" in consulting_html

    def test_has_ga4(self, consulting_html):
        assert "G-EJJZ9T6M52" in consulting_html
        assert "googletagmanager.com" in consulting_html

    def test_has_jsonld(self, consulting_html):
        assert 'application/ld+json' in consulting_html
        assert '"@type":"Service"' in consulting_html or '"@type": "Service"' in consulting_html

    def test_has_meta_robots(self, consulting_html):
        assert 'name="robots"' in consulting_html
        assert 'content="index, follow"' in consulting_html

    def test_has_meta_description(self, consulting_html):
        assert 'name="description"' in consulting_html

    def test_has_og_tags(self, consulting_html):
        assert 'og:title' in consulting_html
        assert 'og:description' in consulting_html

    def test_has_title(self, consulting_html):
        assert "<title>" in consulting_html
        assert "Consulting" in consulting_html

    def test_price_in_page(self, consulting_html):
        assert CONSULTING_PRICE in consulting_html

    def test_duration_in_page(self, consulting_html):
        assert "60 minutes" in consulting_html


# ── Nav ──────────────────────────────────────────────────────


class TestNav:
    def test_nav_links(self, consulting_html):
        assert "/gravel-races/" in consulting_html
        assert "/coaching/" in consulting_html
        assert "/articles/" in consulting_html
        assert "/about/" in consulting_html
        assert ">RACES</a>" in consulting_html
        assert ">PRODUCTS</a>" in consulting_html
        assert ">SERVICES</a>" in consulting_html
        assert ">ARTICLES</a>" in consulting_html
        assert ">ABOUT</a>" in consulting_html

    def test_nav_dropdowns(self, consulting_html):
        assert "gg-site-header-dropdown" in consulting_html
        assert "gg-site-header-item" in consulting_html

    def test_breadcrumb(self, consulting_html):
        assert "gg-breadcrumb" in consulting_html
        assert "Consulting" in consulting_html

    def test_current_page_marker(self, consulting_html):
        assert 'aria-current="page"' in consulting_html
        assert 'aria-current="page">SERVICES</a>' in consulting_html


# ── Hero ─────────────────────────────────────────────────────


class TestHero:
    def test_headline(self):
        hero = build_hero()
        assert "One Call" in hero

    def test_price_displayed(self):
        hero = build_hero()
        assert CONSULTING_PRICE in hero

    def test_checkout_form_present(self):
        hero = build_hero()
        assert 'id="checkout"' in hero
        assert "<form" in hero

    def test_checkout_form_has_name_field(self):
        hero = build_hero()
        assert 'name="name"' in hero
        assert 'type="text"' in hero

    def test_checkout_form_has_email_field(self):
        hero = build_hero()
        assert 'type="email"' in hero
        assert 'name="email"' in hero

    def test_checkout_form_has_submit_button(self):
        hero = build_hero()
        assert "$150" in hero
        assert 'type="submit"' in hero
        assert 'data-cta="hero_book"' in hero

    def test_checkout_form_has_honeypot(self):
        hero = build_hero()
        assert 'name="_honeypot"' in hero
        assert 'display:none' in hero


# ── What You Get ─────────────────────────────────────────────


class TestWhatYouGet:
    def test_three_cards(self):
        section = build_what_you_get()
        assert section.count("gg-consult-card") >= 3

    def test_card_titles(self):
        section = build_what_you_get()
        assert "Pre-Call Prep" in section
        assert "60-Minute Deep Dive" in section
        assert "Written Action Plan" in section

    def test_mentions_48_hours(self):
        section = build_what_you_get()
        assert "48 hours" in section


# ── How It Works ─────────────────────────────────────────────


class TestHowItWorks:
    def test_three_steps(self):
        section = build_how_it_works()
        assert section.count("gg-consult-step") >= 3

    def test_step_titles(self):
        section = build_how_it_works()
        assert "Pay" in section
        assert "Schedule" in section
        assert "We Talk" in section
        assert "Get Your Plan" in section


# ── Topics ───────────────────────────────────────────────────


class TestTopics:
    def test_six_topics(self):
        section = build_topics()
        assert section.count("<li>") == 6

    def test_key_topics(self):
        section = build_topics()
        assert "Race selection" in section
        assert "Training structure" in section
        assert "Nutrition" in section


# ── Bio ─────────────────────────────────────────────────────


class TestBio:
    def test_bio_section_present(self):
        bio = build_bio()
        assert 'id="who"' in bio

    def test_bio_has_name(self):
        bio = build_bio()
        assert "Matti" in bio

    def test_bio_has_credentials(self):
        bio = build_bio()
        assert "TrainingPeaks" in bio
        assert "100+" in bio or "100" in bio

    def test_bio_has_database_reference(self):
        bio = build_bio()
        assert "328" in bio

    def test_bio_section_title(self):
        bio = build_bio()
        assert "Who You" in bio
        assert "Talk To" in bio

    def test_bio_in_full_page(self, consulting_html):
        assert 'id="who"' in consulting_html
        assert "Matti" in consulting_html


# ── Testimonials ────────────────────────────────────────────


class TestTestimonials:
    def test_three_testimonials(self):
        section = build_testimonials()
        assert section.count("gg-consult-testimonial") >= 3

    def test_section_id(self):
        section = build_testimonials()
        assert 'id="testimonials"' in section

    def test_section_title(self):
        section = build_testimonials()
        assert "What Athletes Say" in section

    def test_has_names(self):
        section = build_testimonials()
        assert "Andrew T." in section
        assert "Jen H." in section
        assert "Katie B." in section

    def test_has_meta_lines(self):
        section = build_testimonials()
        assert "gg-consult-testimonial-meta" in section

    def test_testimonials_in_full_page(self, consulting_html):
        assert 'id="testimonials"' in consulting_html
        assert "What Athletes Say" in consulting_html

    def test_no_coaching_language(self):
        """Testimonials should sound like single-session outcomes."""
        section = build_testimonials()
        assert "weekly" not in section.lower()
        assert "training plan" not in section.lower()
        assert "subscription" not in section.lower()


# ── FAQ ──────────────────────────────────────────────────────


class TestFAQ:
    def test_four_questions(self):
        faq = build_faq()
        assert faq.count("gg-consult-faq-item") == 4

    def test_accordion_buttons(self):
        faq = build_faq()
        assert faq.count('aria-expanded="false"') == 4

    def test_key_questions(self):
        faq = build_faq()
        assert "Who is this for?" in faq
        assert "What happens after I pay?" in faq


# ── Final CTA ────────────────────────────────────────────────


class TestFinalCTA:
    def test_cta_present(self):
        cta = build_final_cta()
        assert "Book Your Consult" in cta
        assert 'data-cta="final_book"' in cta

    def test_final_cta_scrolls_to_form(self):
        cta = build_final_cta()
        assert 'href="#checkout"' in cta

    def test_price_summary(self):
        cta = build_final_cta()
        assert CONSULTING_PRICE in cta


# ── Footer ───────────────────────────────────────────────────


class TestFooter:
    def test_mega_footer(self):
        footer = build_footer()
        assert "gg-mega-footer" in footer
        assert "GRAVEL GOD CYCLING" in footer


# ── CSS Quality ──────────────────────────────────────────────


class TestCSSQuality:
    def test_no_hardcoded_hex(self, consulting_css):
        """No raw hex colors — must use var(--gg-color-*)."""
        # Strip out the style tags and check CSS content
        css_content = consulting_css.replace("<style>", "").replace("</style>", "")
        hex_pattern = re.compile(r'(?<![\w-])#[0-9a-fA-F]{3,8}\b')
        matches = hex_pattern.findall(css_content)
        assert matches == [], f"Found hardcoded hex colors: {matches}"

    def test_no_border_radius(self, consulting_css):
        assert "border-radius" not in consulting_css

    def test_no_box_shadow(self, consulting_css):
        assert "box-shadow" not in consulting_css

    def test_uses_brand_tokens(self, consulting_css):
        assert "var(--gg-color-" in consulting_css
        assert "var(--gg-font-" in consulting_css

    def test_css_prefix(self, consulting_css):
        assert "gg-consult-" in consulting_css

    def test_responsive_breakpoint(self, consulting_css):
        assert "768px" in consulting_css

    def test_no_opacity_transition(self, consulting_css):
        assert "transition: opacity" not in consulting_css
        assert "transition:opacity" not in consulting_css


# ── JS Quality ───────────────────────────────────────────────


class TestJSQuality:
    def test_faq_accordion(self, consulting_js):
        assert "gg-consult-faq-q" in consulting_js
        assert "classList" in consulting_js

    def test_cta_tracking(self, consulting_js):
        assert "consulting_cta_click" in consulting_js
        assert "data-cta" in consulting_js

    def test_scroll_depth(self, consulting_js):
        assert "consulting_scroll_depth" in consulting_js
        assert "IntersectionObserver" in consulting_js
        assert "testimonials" in consulting_js
        assert "who" in consulting_js

    def test_page_view_event(self, consulting_js):
        assert "consulting_page_view" in consulting_js

    def test_checkout_js_has_api_url(self, consulting_js):
        assert "create-consulting-checkout" in consulting_js

    def test_checkout_js_has_begin_checkout_event(self, consulting_js):
        assert "begin_checkout" in consulting_js
        assert "Consulting Session" in consulting_js

    def test_checkout_js_has_error_handling(self, consulting_js):
        assert "consulting_checkout_error" in consulting_js
        assert "gg-consult-form-message" in consulting_js

    def test_checkout_js_has_smooth_scroll(self, consulting_js):
        assert 'href="#checkout"' in consulting_js
        assert "scrollIntoView" in consulting_js

    def test_js_syntax_valid(self, consulting_js):
        """Validate JS syntax via Node.js."""
        # Extract JS from script tags
        js = consulting_js.replace("<script>", "").replace("</script>", "")
        result = subprocess.run(
            ["node", "-e", f"new Function({repr(js)})"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stderr}"


# ── No Product Comparisons ───────────────────────────────────


class TestNoComparisons:
    """The consulting page body content should NOT compare itself to other products.
    Nav/footer links to other products are fine — we only check the page sections."""

    def test_no_coaching_price_comparison(self, consulting_html):
        """No coaching pricing mentioned in page content."""
        assert "$199" not in consulting_html
        assert "$299" not in consulting_html
        assert "$1,200" not in consulting_html

    def test_no_training_plan_price_comparison(self, consulting_html):
        """No training plan pricing mentioned."""
        assert "$15/w" not in consulting_html


# ── Sultanic Copy Guard ────────────────────────────────────────


class TestSultanicCopyGuard:
    """Verify psychological upgrade copy is present and brand-compliant."""

    def test_hero_comparison_ignition(self):
        """Hero should contrast the call vs. forum/YouTube research."""
        hero = build_hero()
        assert "forum threads" in hero or "YouTube" in hero, \
            "Missing comparison ignition in hero subtitle"

    def test_hero_no_dns_presumption(self):
        """Hero must NOT assume the prospect has DNS'd."""
        hero = build_hero()
        assert "DNS" not in hero, "DNS presumption in hero — not all prospects have DNS'd"

    def test_pre_call_efficiency_framing(self):
        """Pre-Call Prep should emphasize going deep immediately."""
        wyg = build_what_you_get()
        assert "go deep immediately" in wyg, "Missing efficiency framing in pre-call prep"

    def test_final_cta_functionally_free(self):
        """Final CTA should contain value comparison (race entry fee)."""
        cta = build_final_cta()
        assert "race entry fee" in cta, "Missing Functionally Free comparison"

    def test_final_cta_no_dns_reference(self):
        """Final CTA should NOT reference DNS (excludes first-timers)."""
        cta = build_final_cta()
        assert "DNS" not in cta, "DNS reference excludes first-time prospects"

    def test_cta_context_css_exists(self):
        """CTA context element must have CSS styling."""
        css = build_consulting_css()
        assert "gg-consult-cta-context" in css, "Missing CSS for CTA context"

    def test_cta_context_no_coffee_cliche(self):
        """CTA context must not use generic SaaS comparisons."""
        cta = build_final_cta()
        lower = cta.lower()
        assert "coffee" not in lower, "Coffee cliché violates brand voice"
        assert "latte" not in lower, "Latte cliché violates brand voice"
