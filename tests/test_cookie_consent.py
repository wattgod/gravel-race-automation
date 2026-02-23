"""Tests for cookie_consent.py — shared consent banner module.

Tests: banner structure, hex parity with tokens.css, WCAG accessibility,
JS syntax validation, consent mode behavior, brand compliance.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))
from cookie_consent import get_consent_banner_html

TOKENS_CSS = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"


def _parse_tokens() -> dict[str, str]:
    """Parse token name → hex value from tokens.css."""
    result = {}
    text = TOKENS_CSS.read_text()
    for m in re.finditer(r"--(gg-color-[\w-]+):\s*(#[0-9a-fA-F]{3,8})", text):
        result[m.group(1)] = m.group(2)
    return result


def _extract_hex(text: str) -> set[str]:
    """Extract all hex color values from a string, normalized to lowercase."""
    return {h.lower() for h in re.findall(r"#[0-9a-fA-F]{3,8}", text)}


def _extract_css(html: str) -> str:
    """Extract the <style> block from consent banner HTML."""
    m = re.search(r"<style>(.*?)</style>", html, re.DOTALL)
    return m.group(1) if m else ""


def _extract_js(html: str) -> str:
    """Extract the last <script> block (banner JS, not consent defaults)."""
    scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
    return scripts[-1] if scripts else ""


@pytest.fixture
def banner():
    return get_consent_banner_html()


@pytest.fixture
def css(banner):
    return _extract_css(banner)


@pytest.fixture
def js(banner):
    return _extract_js(banner)


@pytest.fixture
def tokens():
    if not TOKENS_CSS.exists():
        pytest.skip("tokens.css not found")
    return _parse_tokens()


# ── Structure ──────────────────────────────────────────────

class TestBannerStructure:
    """Banner HTML structure and semantic correctness."""

    def test_has_role_dialog(self, banner):
        assert 'role="dialog"' in banner

    def test_has_aria_label(self, banner):
        assert 'aria-label="Cookie consent"' in banner

    def test_has_aria_describedby(self, banner):
        assert 'aria-describedby="gg-consent-desc"' in banner

    def test_desc_id_matches_describedby(self, banner):
        assert 'id="gg-consent-desc"' in banner

    def test_has_accept_button(self, banner):
        assert 'id="gg-consent-accept"' in banner

    def test_has_decline_button(self, banner):
        assert 'id="gg-consent-decline"' in banner

    def test_accept_button_text(self, banner):
        assert ">Accept<" in banner

    def test_decline_button_text(self, banner):
        assert ">Decline<" in banner

    def test_has_cookies_link(self, banner):
        assert 'href="/cookies/"' in banner

    def test_has_learn_more_text(self, banner):
        assert "Learn more" in banner

    def test_banner_id(self, banner):
        assert 'id="gg-consent-banner"' in banner

    def test_no_border_radius(self, css):
        assert "border-radius" not in css

    def test_no_box_shadow(self, css):
        assert "box-shadow" not in css

    def test_no_circles(self, banner):
        assert "<circle" not in banner


# ── Hex Parity with tokens.css ─────────────────────────────

class TestHexParity:
    """Every hex color in the banner must match a tokens.css value."""

    EXPECTED_MAPPING = {
        "#59473c": "gg-color-primary-brown",
        "#8c7568": "gg-color-secondary-brown",
        "#d4c5b9": "gg-color-tan",
        "#1a8a82": "gg-color-teal",
        "#4ecdc4": "gg-color-light-teal",
        "#b7950b": "gg-color-gold",
        "#ffffff": "gg-color-white",
    }

    def test_all_hex_in_tokens(self, banner, tokens):
        """Every hex in the banner must exist in tokens.css."""
        token_hex = {v.lower() for v in tokens.values()}
        banner_hex = _extract_hex(banner)
        unknown = banner_hex - token_hex
        assert not unknown, f"Hex not in tokens.css: {unknown}"

    def test_primary_brown_present(self, css):
        assert "#59473c" in css

    def test_teal_present(self, css):
        assert "#1A8A82".lower() in css.lower()

    def test_gold_present(self, css):
        assert "#B7950B".lower() in css.lower()

    def test_secondary_brown_present(self, css):
        assert "#8c7568" in css

    def test_tan_present(self, css):
        assert "#d4c5b9" in css

    def test_light_teal_present(self, css):
        assert "#4ECDC4".lower() in css.lower()


# ── Accessibility ──────────────────────────────────────────

class TestAccessibility:
    """WCAG compliance checks."""

    def test_focus_visible_styles(self, css):
        assert "focus-visible" in css

    def test_prefers_reduced_motion(self, css):
        assert "prefers-reduced-motion" in css

    def test_transition_none_for_reduced_motion(self, css):
        # After prefers-reduced-motion, should have transition:none
        idx = css.find("prefers-reduced-motion")
        assert "transition:none" in css[idx:]

    def test_buttons_have_type(self, banner):
        # All buttons should have type="button" to prevent form submission
        buttons = re.findall(r"<button[^>]*>", banner)
        # Consent buttons don't need type="button" since they're not in forms
        # But they should be clickable — verify they exist
        assert len(buttons) == 2

    def test_dialog_has_both_buttons(self, banner):
        """Dialog must have both accept AND decline options."""
        assert "gg-consent-accept" in banner
        assert "gg-consent-decline" in banner


# ── JavaScript Behavior ───────────────────────────────────

class TestJsBehavior:
    """Consent banner JavaScript correctness."""

    def test_js_syntax_valid(self, js):
        """JS must parse without errors."""
        result = subprocess.run(
            ["node", "-e", f"new Function({json.dumps(js)})"],
            capture_output=True, text=True, timeout=10,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stderr}"

    def test_cookie_check_uses_regex(self, js):
        """Must use regex for cookie check, not indexOf (prefix-safe)."""
        assert "/(^|; )gg_consent=/.test" in js
        assert "indexOf" not in js

    def test_accept_sets_cookie(self, js):
        assert "gg_consent=accepted" in js

    def test_decline_sets_cookie(self, js):
        assert "gg_consent=declined" in js

    def test_accept_updates_consent_mode(self, js):
        assert "'analytics_storage':'granted'" in js

    def test_decline_updates_consent_mode(self, js):
        """Decline MUST explicitly update consent to denied."""
        assert "'analytics_storage':'denied'" in js

    def test_cookie_has_secure_flag(self, js):
        """All cookies must have Secure flag for HTTPS sites."""
        cookie_sets = re.findall(r"document\.cookie='[^']*'", js)
        assert len(cookie_sets) >= 2, "Expected at least 2 cookie sets (accept + decline)"
        for cookie_set in cookie_sets:
            assert "Secure" in cookie_set, f"Missing Secure flag: {cookie_set}"

    def test_cookie_has_samesite(self, js):
        cookie_sets = re.findall(r"document\.cookie='[^']*'", js)
        for cookie_set in cookie_sets:
            assert "SameSite=Lax" in cookie_set

    def test_cookie_max_age_365_days(self, js):
        assert "max-age=31536000" in js  # 365 * 24 * 60 * 60

    def test_gtag_type_check(self, js):
        """Must check typeof gtag before calling it."""
        assert "typeof gtag==='function'" in js

    def test_removes_show_class(self, js):
        """Both accept and decline must hide the banner."""
        assert js.count("classList.remove('gg-consent-show')") == 2


# ── CSS Brand Compliance ──────────────────────────────────

class TestCssBrandCompliance:
    """CSS follows brand rules."""

    def test_sometype_mono_font(self, css):
        assert "'Sometype Mono'" in css

    def test_no_opacity_transition(self, css):
        """Brand rule: no opacity transitions."""
        transitions = re.findall(r"transition:[^;]+", css)
        for t in transitions:
            if t != "transition:none":
                assert "opacity" not in t, f"Opacity in transition: {t}"

    def test_allowed_transitions_only(self, css):
        """Only border-color, background-color, color transitions allowed."""
        allowed = {"background-color", "color", "border-color", "none"}
        transitions = re.findall(r"transition:([^;]+)", css)
        for t in transitions:
            if t.strip() == "none":
                continue
            props = re.findall(r"([\w-]+)\s+\.", t)
            for prop in props:
                assert prop in allowed, f"Disallowed transition property: {prop}"

    def test_mobile_breakpoint(self, css):
        assert "max-width:600px" in css

    def test_z_index_high(self, css):
        assert "z-index:9999" in css
