"""Tests for generate_legal_pages.py — Privacy, Terms, Cookies pages.

Tests: page generation, content accuracy, third-party disclosures,
cookie/localStorage tables, consent ordering, noindex, brand compliance.
"""
from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))
from generate_legal_pages import (
    CONTACT_EMAIL,
    CURRENT_YEAR,
    LEGAL_PAGES,
    SITE_NAME,
    build_page_css,
    get_cookies_content,
    get_privacy_content,
    get_terms_content,
)

TOKENS_CSS = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"


# ── Content Generation ─────────────────────────────────────

class TestPrivacyContent:
    """Privacy policy content accuracy."""

    @pytest.fixture
    def content(self):
        return get_privacy_content()

    def test_has_what_we_collect(self, content):
        assert "<h2>What We Collect</h2>" in content

    def test_has_analytics_section(self, content):
        assert "Google Analytics 4" in content

    def test_ga4_pii_claim_softened(self, content):
        """Must NOT claim 'No PII is sent' — use softer language."""
        assert "do not intentionally send personally identifiable" in content
        assert "IP anonymization" in content

    def test_has_form_submissions(self, content):
        assert "Form submissions" in content

    def test_has_stripe(self, content):
        assert "Stripe" in content

    def test_has_substack(self, content):
        assert "Substack" in content

    def test_has_third_party_services(self, content):
        assert "<h2>Third-Party Services</h2>" in content

    def test_third_party_includes_ga4(self, content):
        assert "Google Analytics 4" in content

    def test_third_party_includes_stripe(self, content):
        assert "<strong>Stripe</strong>" in content

    def test_third_party_includes_formsubmit(self, content):
        assert "Formsubmit.co" in content

    def test_third_party_includes_google_calendar(self, content):
        """Consulting uses Google Calendar for booking."""
        assert "Google Calendar" in content

    def test_third_party_includes_jetpack(self, content):
        """Jetpack is active for site security."""
        assert "Jetpack" in content

    def test_third_party_includes_siteground(self, content):
        assert "SiteGround" in content

    def test_has_data_retention(self, content):
        assert "<h2>Data Retention</h2>" in content

    def test_has_your_rights(self, content):
        assert "<h2>Your Rights</h2>" in content

    def test_has_contact_email(self, content):
        assert CONTACT_EMAIL in content

    def test_contact_email_is_mailto(self, content):
        assert f'href="mailto:{CONTACT_EMAIL}"' in content


class TestTermsContent:
    """Terms of service content accuracy."""

    @pytest.fixture
    def content(self):
        return get_terms_content()

    def test_has_services_section(self, content):
        assert "<h2>Services</h2>" in content

    def test_sole_proprietor(self, content):
        assert "Matti Rowe" in content
        assert "sole proprietor" in content

    def test_race_info_disclaimer(self, content):
        assert "not affiliated with" in content
        assert "verify with official race sources" in content

    def test_training_plans_one_time(self, content):
        assert "one-time purchases" in content

    def test_coaching_billing_every_4_weeks(self, content):
        """Coaching is every 4 weeks, NOT monthly."""
        assert "every 4 weeks" in content
        assert "13 billing cycles" in content

    def test_no_monthly_billing_claim(self, content):
        """Must not say 'monthly' for coaching billing."""
        lower = content.lower()
        # "monthly" should not appear in billing context
        assert "billed monthly" not in lower
        assert "per month" not in lower

    def test_setup_fee(self, content):
        assert "$99 setup fee" in content

    def test_consulting_price(self, content):
        assert "$150" in content

    def test_not_medical_advice(self, content):
        assert "not medical advice" in content

    def test_has_refund_policy(self, content):
        assert "Refund" in content or "refund" in content

    def test_has_ip_section(self, content):
        assert "Intellectual Property" in content

    def test_has_liability_section(self, content):
        assert "Limitation of Liability" in content


class TestCookiesContent:
    """Cookie policy content accuracy and completeness."""

    @pytest.fixture
    def content(self):
        return get_cookies_content()

    def test_has_what_are_cookies(self, content):
        assert "What Are Cookies" in content

    def test_has_essential_cookies(self, content):
        assert "Essential Cookies" in content

    def test_gg_consent_cookie(self, content):
        assert "<code>gg_consent</code>" in content

    def test_wordpress_cookies(self, content):
        assert "<code>wordpress_*</code>" in content

    def test_jetpack_cookie(self, content):
        """Jetpack sets tk_tc cookie."""
        assert "<code>tk_tc</code>" in content

    def test_analytics_cookies(self, content):
        assert "Analytics Cookies" in content

    def test_ga_cookie(self, content):
        assert "<code>_ga</code>" in content

    def test_ga_wildcard_cookie(self, content):
        assert "<code>_ga_*</code>" in content

    def test_consent_gated_analytics(self, content):
        """Analytics cookies must be described as consent-gated."""
        assert "after you accept" in content

    def test_has_localstorage_section(self, content):
        """localStorage must be in a separate section, not cookie table."""
        assert "Client-Side Storage" in content

    def test_localstorage_never_leaves_browser(self, content):
        """Must clarify localStorage doesn't leave the browser."""
        assert "never leaves your browser" in content

    def test_favorites_key(self, content):
        assert "<code>gg-favorites</code>" in content

    def test_saved_filters_key(self, content):
        assert "<code>gg-saved-filters</code>" in content

    def test_questionnaire_progress_key(self, content):
        assert "<code>athlete_questionnaire_progress</code>" in content

    def test_ab_assign_key(self, content):
        """A/B testing localStorage must be disclosed."""
        assert "<code>gg_ab_assign</code>" in content

    def test_ab_vid_key(self, content):
        assert "<code>gg_ab_vid</code>" in content

    def test_ab_cache_key(self, content):
        assert "<code>gg_ab_cache</code>" in content

    def test_ab_vid_not_linked_to_personal(self, content):
        """Visitor ID disclosure must clarify it's anonymous."""
        assert "not linked to personal data" in content

    def test_third_party_cookies_section(self, content):
        assert "Third-Party Cookies" in content

    def test_no_advertising_cookies(self, content):
        assert "do not use any advertising" in content

    def test_managing_cookies(self, content):
        assert "Managing Cookies" in content


# ── Page Structure ────────────────────────────────────────

class TestPageStructure:
    """Legal page configuration and metadata."""

    def test_three_pages_defined(self):
        assert len(LEGAL_PAGES) == 3

    def test_privacy_page_exists(self):
        assert "privacy" in LEGAL_PAGES

    def test_terms_page_exists(self):
        assert "terms" in LEGAL_PAGES

    def test_cookies_page_exists(self):
        assert "cookies" in LEGAL_PAGES

    @pytest.mark.parametrize("key", ["privacy", "terms", "cookies"])
    def test_page_has_title(self, key):
        assert "title" in LEGAL_PAGES[key]

    @pytest.mark.parametrize("key", ["privacy", "terms", "cookies"])
    def test_page_has_slug(self, key):
        assert LEGAL_PAGES[key]["slug"] == key

    @pytest.mark.parametrize("key", ["privacy", "terms", "cookies"])
    def test_page_has_description(self, key):
        assert "description" in LEGAL_PAGES[key]
        assert len(LEGAL_PAGES[key]["description"]) > 20

    @pytest.mark.parametrize("key", ["privacy", "terms", "cookies"])
    def test_page_has_content_fn(self, key):
        assert callable(LEGAL_PAGES[key]["content_fn"])

    def test_current_year_is_dynamic(self):
        """Year must not be hardcoded."""
        assert CURRENT_YEAR == date.today().year

    def test_site_name(self):
        assert SITE_NAME == "Gravel God Cycling"


# ── CSS Tests ─────────────────────────────────────────────

class TestLegalPageCss:
    """CSS brand compliance."""

    @pytest.fixture
    def css(self):
        return build_page_css()

    def test_no_hardcoded_hex(self, css):
        """Legal page CSS should use var() tokens, not hardcoded hex."""
        # Extract just the legal page CSS (not header/footer)
        legal_css = css.split("/* Legal")[0] if "/* Legal" in css else css
        # The CSS uses var() throughout — hex should only appear in
        # header/footer which are imported modules
        legal_rules = re.findall(r"\.gg-legal[^{]*\{[^}]+\}", css)
        for rule in legal_rules:
            hex_vals = re.findall(r"#[0-9a-fA-F]{3,8}", rule)
            assert not hex_vals, f"Hardcoded hex in legal CSS rule: {rule[:80]}"

    def test_uses_css_tokens(self, css):
        assert "var(--gg-color-" in css
        assert "var(--gg-font-" in css

    def test_no_border_radius(self, css):
        # Check only legal page rules
        legal_rules = re.findall(r"\.gg-legal[^{]*\{[^}]+\}", css)
        for rule in legal_rules:
            assert "border-radius" not in rule

    def test_mobile_breakpoint(self, css):
        assert "max-width: 600px" in css or "max-width:600px" in css

    def test_editorial_font_for_body(self, css):
        assert "var(--gg-font-editorial)" in css

    def test_data_font_for_headings(self, css):
        assert "var(--gg-font-data)" in css


# ── Generated Page Tests ──────────────────────────────────

class TestGeneratedPages:
    """Full page generation with all components."""

    @pytest.fixture
    def privacy_page(self, tmp_path):
        sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))
        from generate_legal_pages import generate_page
        generate_page("privacy", tmp_path)
        return (tmp_path / "privacy.html").read_text()

    @pytest.fixture
    def cookies_page(self, tmp_path):
        from generate_legal_pages import generate_page
        generate_page("cookies", tmp_path)
        return (tmp_path / "cookies.html").read_text()

    def test_privacy_has_noindex(self, privacy_page):
        assert 'name="robots" content="noindex, follow"' in privacy_page

    def test_privacy_has_canonical(self, privacy_page):
        assert 'rel="canonical"' in privacy_page

    def test_privacy_has_og_image(self, privacy_page):
        assert 'property="og:image"' in privacy_page

    def test_privacy_has_og_image_dimensions(self, privacy_page):
        assert 'og:image:width" content="1200"' in privacy_page
        assert 'og:image:height" content="630"' in privacy_page

    def test_privacy_has_og_site_name(self, privacy_page):
        assert 'og:site_name" content="Gravel God Cycling"' in privacy_page

    def test_privacy_has_consent_banner(self, privacy_page):
        assert "gg-consent-banner" in privacy_page

    def test_privacy_consent_before_body_close(self, privacy_page):
        """Consent banner must be after footer, before </body>."""
        banner_pos = privacy_page.find("gg-consent-banner")
        body_close = privacy_page.find("</body>")
        assert banner_pos < body_close

    def test_privacy_consent_defaults_in_head(self, privacy_page):
        """Consent defaults must be in <head> before GA4."""
        head = privacy_page[: privacy_page.find("</head>")]
        assert "gtag('consent','default'" in head

    def test_privacy_consent_defaults_uses_regex(self, privacy_page):
        """Consent defaults must use regex, not indexOf."""
        head = privacy_page[: privacy_page.find("</head>")]
        assert "/(^|; )gg_consent=accepted/.test" in head
        assert "indexOf" not in head

    def test_privacy_ga4_after_consent(self, privacy_page):
        head = privacy_page[: privacy_page.find("</head>")]
        consent_pos = head.find("gtag('consent','default'")
        ga4_pos = head.find("googletagmanager.com/gtag")
        assert consent_pos < ga4_pos, "Consent defaults must come before GA4 script"

    def test_privacy_has_header(self, privacy_page):
        assert "gg-site-header" in privacy_page or "gg-hdr" in privacy_page

    def test_privacy_has_footer(self, privacy_page):
        assert "gg-mega-footer" in privacy_page or "gg-mf" in privacy_page

    def test_privacy_has_breadcrumb(self, privacy_page):
        assert "gg-breadcrumb" in privacy_page

    def test_privacy_date_uses_current_year(self, privacy_page):
        assert f"{date.today().year}" in privacy_page

    def test_privacy_date_uses_current_month(self, privacy_page):
        """Month must be dynamic, not hardcoded."""
        current_month = date.today().strftime("%B")
        assert current_month in privacy_page

    def test_cookies_has_localstorage_section(self, cookies_page):
        assert "Client-Side Storage" in cookies_page

    def test_cookies_has_ab_keys(self, cookies_page):
        assert "gg_ab_assign" in cookies_page
        assert "gg_ab_vid" in cookies_page


# ── Consent Ordering Guard ────────────────────────────────

class TestConsentOrdering:
    """Consent defaults must appear before GA4 in all legal pages."""

    @pytest.fixture(params=["privacy", "terms", "cookies"])
    def page_html(self, request, tmp_path):
        from generate_legal_pages import generate_page
        generate_page(request.param, tmp_path)
        return (tmp_path / f"{request.param}.html").read_text()

    def test_consent_before_ga4(self, page_html):
        head = page_html[: page_html.find("</head>")]
        consent_pos = head.find("consent','default'")
        ga4_pos = head.find("googletagmanager.com/gtag")
        assert consent_pos > 0, "Missing consent defaults"
        assert ga4_pos > 0, "Missing GA4 script"
        assert consent_pos < ga4_pos
