"""Tests for gg-cookie-consent.php mu-plugin — Python/PHP parity + correctness.

Enforces byte-level parity between cookie_consent.py (Python) and
gg-cookie-consent.php (PHP mu-plugin). Both render the same consent banner
with hardcoded hex values that must match tokens.css.

Also validates consent mode integration, priority ordering, and admin exclusion.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))
from cookie_consent import get_consent_banner_html

MU_PLUGIN = Path(__file__).parent.parent / "wordpress" / "mu-plugins" / "gg-cookie-consent.php"
TOKENS_CSS = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"


def _parse_tokens() -> dict[str, str]:
    """Parse token name → hex value from tokens.css."""
    result = {}
    text = TOKENS_CSS.read_text()
    for m in re.finditer(r"--(gg-color-[\w-]+):\s*(#[0-9a-fA-F]{3,8})", text):
        result[m.group(1)] = m.group(2)
    return result


@pytest.fixture
def php_source():
    return MU_PLUGIN.read_text()


@pytest.fixture
def python_banner():
    return get_consent_banner_html()


@pytest.fixture
def tokens():
    if not TOKENS_CSS.exists():
        pytest.skip("tokens.css not found")
    return _parse_tokens()


def _extract_php_banner(php_source: str) -> str:
    """Extract the banner HTML+CSS+JS from the PHP mu-plugin.

    The banner is in gg_cookie_consent_banner() between ?> and <?php.
    """
    # Find the banner function's output (second ?> ... <?php block)
    blocks = re.findall(r"\?>\n(.*?)\n\s*<\?php", php_source, re.DOTALL)
    if len(blocks) >= 2:
        return blocks[1].strip()
    return ""


def _extract_php_consent_defaults(php_source: str) -> str:
    """Extract the consent defaults script from the PHP mu-plugin."""
    blocks = re.findall(r"\?>\n(.*?)\n\s*<\?php", php_source, re.DOTALL)
    if blocks:
        return blocks[0].strip()
    return ""


# ── Parity Tests ──────────────────────────────────────────

class TestBannerParity:
    """Python and PHP consent banners must be identical."""

    def test_css_parity(self, php_source, python_banner):
        """CSS in PHP and Python must be byte-identical."""
        php_banner = _extract_php_banner(php_source)
        py_css = re.search(r"<style>(.*?)</style>", python_banner, re.DOTALL)
        php_css = re.search(r"<style>(.*?)</style>", php_banner, re.DOTALL)
        assert py_css and php_css, "Could not extract CSS from both sources"
        assert py_css.group(1) == php_css.group(1), (
            "CSS mismatch between cookie_consent.py and gg-cookie-consent.php"
        )

    def test_html_parity(self, php_source, python_banner):
        """Banner HTML structure in PHP and Python must match."""
        php_banner = _extract_php_banner(php_source)
        py_html = re.search(
            r"<div class=\"gg-consent-banner\".*?</div>",
            python_banner, re.DOTALL,
        )
        php_html = re.search(
            r"<div class=\"gg-consent-banner\".*?</div>",
            php_banner, re.DOTALL,
        )
        assert py_html and php_html, "Could not extract HTML from both sources"
        assert py_html.group(0) == php_html.group(0), (
            "HTML mismatch between cookie_consent.py and gg-cookie-consent.php"
        )

    def test_js_parity(self, php_source, python_banner):
        """Banner JS in PHP and Python must be byte-identical."""
        php_banner = _extract_php_banner(php_source)
        py_scripts = re.findall(r"<script>(.*?)</script>", python_banner, re.DOTALL)
        php_scripts = re.findall(r"<script>(.*?)</script>", php_banner, re.DOTALL)
        assert py_scripts and php_scripts, "Could not extract JS from both sources"
        assert py_scripts[-1] == php_scripts[-1], (
            "JS mismatch between cookie_consent.py and gg-cookie-consent.php"
        )


# ── Hex Parity with tokens.css ─────────────────────────────

class TestPhpHexParity:
    """PHP mu-plugin hex values must match tokens.css."""

    def test_all_hex_in_tokens(self, php_source, tokens):
        token_hex = {v.lower() for v in tokens.values()}
        php_hex = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}", php_source)}
        unknown = php_hex - token_hex
        assert not unknown, f"PHP hex not in tokens.css: {unknown}"

    def test_python_and_php_use_same_hex(self, php_source, python_banner):
        py_hex = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}", python_banner)}
        php_hex = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}", php_source)}
        # PHP may have additional hex from consent defaults section
        php_banner = _extract_php_banner(php_source)
        php_banner_hex = {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}", php_banner)}
        assert py_hex == php_banner_hex, (
            f"Hex set mismatch. Python: {py_hex}, PHP banner: {php_banner_hex}"
        )


# ── Consent Mode Integration ──────────────────────────────

class TestConsentMode:
    """Consent Mode v2 integration correctness."""

    def test_consent_defaults_before_ga4(self, php_source):
        """Consent defaults must fire at priority 0 (before GA4 at priority 1)."""
        assert "gg_consent_mode_defaults', 0" in php_source

    def test_banner_at_footer_priority_99(self, php_source):
        """Banner in footer at high priority to be last element."""
        assert "gg_cookie_consent_banner', 99" in php_source

    def test_consent_defaults_has_all_types(self, php_source):
        defaults = _extract_php_consent_defaults(php_source)
        assert "'analytics_storage'" in defaults
        assert "'ad_storage': 'denied'" in defaults
        assert "'ad_user_data': 'denied'" in defaults
        assert "'ad_personalization': 'denied'" in defaults

    def test_consent_defaults_wait_for_update(self, php_source):
        defaults = _extract_php_consent_defaults(php_source)
        assert "'wait_for_update': 500" in defaults

    def test_consent_defaults_checks_cookie(self, php_source):
        """Consent defaults must check existing gg_consent cookie."""
        defaults = _extract_php_consent_defaults(php_source)
        assert "gg_consent=accepted" in defaults

    def test_consent_defaults_uses_regex(self, php_source):
        """Consent defaults must use regex for cookie check, not indexOf."""
        defaults = _extract_php_consent_defaults(php_source)
        assert "/(^|; )gg_consent=accepted/.test" in defaults


# ── Admin Exclusion ────────────────────────────────────────

class TestAdminExclusion:
    """Mu-plugin must exclude admin users and admin pages."""

    def test_is_admin_check_in_defaults(self, php_source):
        # Find the consent defaults function
        defaults_fn = php_source[
            php_source.find("function gg_consent_mode_defaults"):
            php_source.find("function gg_cookie_consent_banner")
        ]
        assert "is_admin()" in defaults_fn

    def test_edit_posts_check_in_defaults(self, php_source):
        defaults_fn = php_source[
            php_source.find("function gg_consent_mode_defaults"):
            php_source.find("function gg_cookie_consent_banner")
        ]
        assert "current_user_can( 'edit_posts' )" in defaults_fn

    def test_is_admin_check_in_banner(self, php_source):
        banner_fn = php_source[php_source.find("function gg_cookie_consent_banner"):]
        assert "is_admin()" in banner_fn

    def test_edit_posts_check_in_banner(self, php_source):
        banner_fn = php_source[php_source.find("function gg_cookie_consent_banner"):]
        assert "current_user_can( 'edit_posts' )" in banner_fn


# ── Brand Compliance ──────────────────────────────────────

class TestPhpBrandCompliance:
    """PHP mu-plugin follows brand rules."""

    def test_no_border_radius(self, php_source):
        assert "border-radius" not in php_source

    def test_no_box_shadow(self, php_source):
        assert "box-shadow" not in php_source

    def test_sometype_mono_font(self, php_source):
        assert "'Sometype Mono'" in php_source

    def test_focus_visible_styles(self, php_source):
        assert "focus-visible" in php_source

    def test_prefers_reduced_motion(self, php_source):
        assert "prefers-reduced-motion" in php_source

    def test_secure_flag_on_cookies(self, php_source):
        banner = _extract_php_banner(php_source)
        cookie_sets = re.findall(r"document\.cookie='[^']*'", banner)
        for cs in cookie_sets:
            assert "Secure" in cs, f"Missing Secure: {cs}"
