"""Tests for the Gravel God consulting page generator (Sultanic copy v2)."""
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
    ADDON_PRICE,
    ADDON_PRICE_INT,
    build_nav,
    build_hero,
    build_two_futures,
    build_how_it_works,
    build_what_i_look_at,
    build_what_we_cover,
    build_plan_addon,
    build_who,
    build_fit,
    build_faq,
    build_close,
    build_footer,
    build_consulting_css,
    build_consulting_js,
    build_jsonld,
    generate_consulting_page,
)

# Section builders whose output is human-readable copy — the Normie Test and
# other content guards should be checked against these, not the full page
# (which also embeds JS option names like IntersectionObserver's `threshold`).
COPY_SECTION_BUILDERS = [
    build_hero,
    build_two_futures,
    build_how_it_works,
    build_what_i_look_at,
    build_what_we_cover,
    build_plan_addon,
    build_who,
    build_fit,
    build_faq,
    build_close,
]


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


@pytest.fixture(scope="module")
def all_copy():
    return "\n".join(fn() for fn in COPY_SECTION_BUILDERS)


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

    def test_addon_price_in_page(self, consulting_html):
        assert ADDON_PRICE in consulting_html


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
        assert "read you can" in hero

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

    def test_checkout_form_has_addon_checkbox(self):
        hero = build_hero()
        assert 'name="plan_addon"' in hero
        assert 'type="checkbox"' in hero
        assert "custom 12-week plan" in hero
        assert ADDON_PRICE in hero

    def test_button_copy(self):
        hero = build_hero()
        assert "Book the consult" in hero


# ── Two Futures ───────────────────────────────────────────────


class TestTwoFutures:
    def test_section_present(self):
        section = build_two_futures()
        assert 'id="two-futures"' in section
        assert "Two futures" in section

    def test_comparison_ignition(self):
        section = build_two_futures()
        assert "forum" in section.lower()
        assert "Same bike. Same hours." in section


# ── How It Works ─────────────────────────────────────────────


class TestHowItWorks:
    def test_five_frames(self):
        section = build_how_it_works()
        assert section.count("gg-consult-strip-frame") >= 5

    def test_svg_present(self):
        section = build_how_it_works()
        assert "<svg" in section
        assert "gg-consult-strip-svg" in section

    def test_hairline_rail(self):
        section = build_how_it_works()
        assert "gg-consult-strip-rail" in section

    def test_frame_four_emphasised(self):
        section = build_how_it_works()
        assert "gg-consult-strip-frame--emphasis" in section

    def test_captions_present(self):
        section = build_how_it_works()
        assert "Book." in section
        assert "Connect your TrainingPeaks." in section
        assert "Answer twelve questions." in section
        assert "Your read arrives" in section
        assert "written plan of action within 48 hours" in section

    def test_no_var_in_svg_attrs(self):
        """SVG attributes can't resolve var() — must be styled via CSS classes only."""
        section = build_how_it_works()
        svg_match = re.search(r'<svg.*?</svg>', section, re.DOTALL)
        assert svg_match
        assert "var(--" not in svg_match.group(0)


# ── What I Actually Look At ──────────────────────────────────


class TestWhatILookAt:
    def test_section_present(self):
        section = build_what_i_look_at()
        assert 'id="look"' in section
        assert "What I actually look at" in section

    def test_five_bullets(self):
        section = build_what_i_look_at()
        assert section.count("<li>") == 5

    def test_key_points(self):
        section = build_what_i_look_at()
        assert "hard riding was actually hard" in section
        assert "climbing, flat, or quietly sliding" in section
        assert "easier deep in" in section
        assert "zones are built on are still true" in section


# ── What We Can Cover ────────────────────────────────────────


class TestWhatWeCover:
    def test_section_present(self):
        section = build_what_we_cover()
        assert 'id="cover"' in section
        assert "What we can cover" in section

    def test_topics(self):
        section = build_what_we_cover()
        for topic in ["Race selection", "Season planning", "Fuelling", "Race-day execution"]:
            assert topic in section

    def test_open_invite(self):
        section = build_what_we_cover()
        assert "It probably does" in section


# ── Plan Add-on ───────────────────────────────────────────────


class TestPlanAddon:
    def test_section_present(self):
        section = build_plan_addon()
        assert 'id="plan"' in section
        assert ADDON_PRICE in section

    def test_honest_limits(self):
        section = build_plan_addon()
        assert "one goal event" in section
        assert "twelve weeks" in section
        assert "seven days after the call" in section

    def test_no_jargon(self):
        section = build_plan_addon()
        for bad in ["TSS", "FTP", "CTL", "VO2", "periodization"]:
            assert bad not in section


# ── Who You'll Talk To ───────────────────────────────────────


class TestWho:
    def test_bio_section_present(self):
        bio = build_who()
        assert 'id="who"' in bio

    def test_bio_has_name(self):
        bio = build_who()
        assert "Matti" in bio

    def test_bio_has_credentials(self):
        bio = build_who()
        assert "TrainingPeaks" in bio
        assert "100+" in bio

    def test_bio_has_database_reference(self):
        bio = build_who()
        assert "750+" in bio

    def test_bio_section_title(self):
        bio = build_who()
        assert "Who you" in bio
        assert "talk to" in bio

    def test_bio_in_full_page(self, consulting_html):
        assert 'id="who"' in consulting_html
        assert "Matti" in consulting_html


# ── Is This For You ──────────────────────────────────────────


class TestFit:
    def test_section_present(self):
        section = build_fit()
        assert 'id="fit"' in section
        assert "Is this for you?" in section

    def test_for_and_not_for(self):
        section = build_fit()
        assert "For you if" in section
        assert "Not for you if" in section
        assert "goal event and real questions" in section
        assert "pep talk" in section


# ── FAQ ──────────────────────────────────────────────────────


class TestFAQ:
    def test_six_questions(self):
        faq = build_faq()
        assert faq.count("gg-consult-faq-item") == 6

    def test_accordion_buttons(self):
        faq = build_faq()
        assert faq.count('aria-expanded="false"') == 6

    def test_key_questions(self):
        faq = build_faq()
        assert "What happens after I pay?" in faq
        assert "I don" in faq and "TrainingPeaks" in faq
        assert "Do I have to share data?" in faq
        assert "Can I add the plan later?" in faq

    def test_privacy_sentence(self):
        faq = build_faq()
        assert "What happens to my data?" in faq
        assert "deleted on request" in faq
        assert "aren" in faq and "shared or sold" in faq


# ── Close ────────────────────────────────────────────────────


class TestClose:
    def test_cta_present(self):
        cta = build_close()
        assert "Less than a race entry" in cta
        assert 'data-cta="final_book"' in cta

    def test_final_cta_scrolls_to_form(self):
        cta = build_close()
        assert 'href="#checkout"' in cta

    def test_price_summary(self):
        cta = build_close()
        assert CONSULTING_PRICE in cta

    def test_no_dns_reference(self):
        """DNS reference excludes first-time prospects."""
        cta = build_close()
        assert "DNS" not in cta

    def test_no_coffee_cliche(self):
        cta = build_close()
        lower = cta.lower()
        assert "coffee" not in lower
        assert "latte" not in lower

    def test_quiet_clause(self):
        cta = build_close()
        assert "every week" in cta
        assert 'href="https://gravelgodcycling.com/coaching/"' in cta

    def test_quiet_clause_no_credit_claim(self):
        """No coaching-credit claim — that decision was explicitly deferred."""
        cta = build_close()
        assert "credit" not in cta.lower()


# ── Footer ───────────────────────────────────────────────────


class TestFooter:
    def test_mega_footer(self):
        footer = build_footer()
        assert "gg-mega-footer" in footer
        assert "GRAVEL GOD CYCLING" in footer


# ── No Testimonials (unverified — removed per copy v2) ───────


class TestNoTestimonials:
    def test_no_testimonial_section(self, consulting_html):
        assert "testimonial" not in consulting_html.lower()
        assert "What Athletes Say" not in consulting_html

    def test_no_removed_names(self, consulting_html):
        for name in ["Andrew T.", "Jen H.", "Katie B."]:
            assert name not in consulting_html


# ── CSS Quality ──────────────────────────────────────────────


class TestCSSQuality:
    def test_no_hardcoded_hex(self, consulting_css):
        """No raw hex colors — must use var(--gg-color-*)."""
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

    def test_no_bounce_easing(self, consulting_css):
        assert "bounce" not in consulting_css.lower()
        assert "spring" not in consulting_css.lower()

    def test_no_entrance_animations(self, consulting_css):
        assert "@keyframes" not in consulting_css


# ── Brand Tokens Are Real (mirrors coaching's pattern) ────────


class TestCssTokenValidation:
    def test_all_var_refs_defined(self, consulting_css):
        """Every var(--gg-*) used in the consulting CSS must exist in tokens.css."""
        tokens_path = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("Brand tokens not found")
        tokens_css = tokens_path.read_text()
        var_refs = set(re.findall(r'var\((--gg-[a-z0-9-]+)\)', consulting_css))
        assert var_refs, "No var(--gg-*) references found — did the generator change?"
        for var_name in var_refs:
            assert var_name in tokens_css, f"Undefined token: {var_name}"


# ── JS Quality ───────────────────────────────────────────────


class TestJSQuality:
    def test_faq_accordion(self, consulting_js):
        assert "gg-consult-faq-q" in consulting_js
        assert "classList" in consulting_js

    def test_cta_tracking(self, consulting_js):
        assert "'cta_click'" in consulting_js
        assert "source:'consulting'" in consulting_js
        assert "data-cta" in consulting_js

    def test_scroll_depth(self, consulting_js):
        assert "consulting_scroll_depth" in consulting_js
        assert "IntersectionObserver" in consulting_js
        assert "'who'" in consulting_js
        assert "'faq'" in consulting_js

    def test_page_view_event(self, consulting_js):
        assert "consulting_page_view" in consulting_js

    def test_checkout_js_has_api_url(self, consulting_js):
        assert "create-consulting-checkout" in consulting_js

    def test_checkout_js_sends_plan_addon(self, consulting_js):
        assert "plan_addon" in consulting_js
        assert "planAddon" in consulting_js

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

    def test_no_coaching_price_comparison(self, all_copy):
        """No coaching pricing mentioned in page content."""
        assert "$199" not in all_copy
        assert "$299" not in all_copy
        assert "$1,200" not in all_copy

    def test_no_training_plan_price_comparison(self, all_copy):
        """No training plan pricing mentioned."""
        assert "$15/w" not in all_copy


# ── Normie Test (banned jargon guard) ────────────────────────


class TestNormieTest:
    """No TSS/FTP/CTL/VO2max/threshold/periodization anywhere in the copy.
    Checked against section-builder output, not the full page — the full page
    also contains legitimate non-copy uses like the IntersectionObserver
    `threshold` option in inline JS."""

    BANNED_TERMS = ["TSS", "FTP", "CTL", "VO2max", "VO2", "periodization", "power curve"]

    def test_no_banned_jargon(self, all_copy):
        for term in self.BANNED_TERMS:
            assert term not in all_copy, f"Banned jargon '{term}' found in copy"

    def test_no_bare_threshold_word(self, all_copy):
        """'threshold' as training jargon is banned; this is copy-only text
        so there's no legitimate JS option name to collide with."""
        assert "threshold" not in all_copy.lower()
