"""Tests for gg-header.php mu-plugin — parity with shared_header.py and brand tokens.

Prevents:
  - Stale hardcoded hex values drifting from brand tokens
  - Nav structure divergence between PHP mu-plugin and Python shared_header
  - Missing CSS overrides (!important, :link/:visited) that let Astra theme bleed through
  - Missing body class injection that lets Code Snippet teal overrides apply
  - Missing Astra header hiding selectors
  - Missing entrance-animation opacity fix for WP-embedded pages
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ── File paths ──────────────────────────────────────────────

ROOT = Path(__file__).parent.parent
MU_PLUGIN_PATH = ROOT / "wordpress" / "mu-plugins" / "gg-header.php"
SHARED_HEADER_PATH = ROOT / "wordpress" / "shared_header.py"
BRAND_TOKENS_PATH = Path("/Users/mattirowe/Documents/GravelGod/gravel-god-brand/tokens/tokens.css")


# ── Fixtures ────────────────────────────────────────────────


@pytest.fixture(scope="module")
def mu_plugin_source():
    return MU_PLUGIN_PATH.read_text()


@pytest.fixture(scope="module")
def shared_header_html():
    """Get rendered HTML from shared_header.py."""
    import sys
    sys.path.insert(0, str(ROOT / "wordpress"))
    from shared_header import get_site_header_html
    return get_site_header_html()


@pytest.fixture(scope="module")
def shared_header_css():
    """Get CSS from shared_header.py."""
    import sys
    sys.path.insert(0, str(ROOT / "wordpress"))
    from shared_header import get_site_header_css
    return get_site_header_css()


@pytest.fixture(scope="module")
def brand_tokens():
    """Parse brand tokens.css into a dict of token_name → hex_value."""
    css = BRAND_TOKENS_PATH.read_text()
    tokens = {}
    for m in re.finditer(r'--(gg-color-[\w-]+):\s*(#[0-9a-fA-F]{3,8})', css):
        tokens[m.group(1)] = m.group(2).lower()
    return tokens


# ── Helper: extract token references from shared_header CSS ─


def _css_token_refs(css: str) -> dict[str, str]:
    """Map var(--gg-color-*) usage to property context.

    Returns dict like {"gg-color-dark-brown": "color", "gg-color-gold": "border"}.
    """
    refs = {}
    for m in re.finditer(r'var\(--(gg-color-[\w-]+)\)', css):
        refs[m.group(1)] = True
    return set(refs.keys())


def _php_hex_values(php: str) -> set[str]:
    """Extract all hex color values from the mu-plugin CSS section."""
    # Only look within the <style> block
    style_match = re.search(r'<style[^>]*>(.*?)</style>', php, re.DOTALL)
    if not style_match:
        return set()
    css = style_match.group(1)
    return {m.lower() for m in re.findall(r'#[0-9a-fA-F]{3,8}\b', css)}


# ── Token → Hex Parity ─────────────────────────────────────


class TestColorParity:
    """Every hardcoded hex in the mu-plugin must match a brand token value."""

    def _token_to_hex(self, brand_tokens: dict, shared_css: str) -> dict[str, str]:
        """Map token names used in shared_header CSS to their hex values."""
        refs = _css_token_refs(shared_css)
        return {name: brand_tokens[name] for name in refs if name in brand_tokens}

    def test_dark_brown_matches(self, mu_plugin_source, brand_tokens):
        """Nav link text color matches --gg-color-dark-brown."""
        expected = brand_tokens["gg-color-dark-brown"]
        assert expected in mu_plugin_source.lower(), (
            f"mu-plugin missing {expected} for --gg-color-dark-brown"
        )

    def test_gold_matches(self, mu_plugin_source, brand_tokens):
        """Hover/active color matches --gg-color-gold."""
        expected = brand_tokens["gg-color-gold"]
        assert expected in mu_plugin_source.lower(), (
            f"mu-plugin missing {expected} for --gg-color-gold"
        )

    def test_warm_paper_matches(self, mu_plugin_source, brand_tokens):
        """Background color matches --gg-color-warm-paper."""
        expected = brand_tokens["gg-color-warm-paper"]
        assert expected in mu_plugin_source.lower(), (
            f"mu-plugin missing {expected} for --gg-color-warm-paper"
        )

    def test_no_stale_hex_values(self, mu_plugin_source, brand_tokens):
        """Every hex in the mu-plugin CSS must be a known brand token value.

        Catches stale/wrong colors like #59473c when the token is #3a2e25.
        """
        php_hexes = _php_hex_values(mu_plugin_source)
        token_hexes = {v.lower() for v in brand_tokens.values()}
        stale = php_hexes - token_hexes
        assert stale == set(), (
            f"Mu-plugin contains hex values not in brand tokens: {stale}. "
            f"Read tokens.css for correct values."
        )


# ── Nav Structure Parity ───────────────────────────────────


class TestNavParity:
    """PHP mu-plugin nav must match Python shared_header nav."""

    def test_five_top_level_items(self, mu_plugin_source):
        assert ">RACES</a>" in mu_plugin_source
        assert ">PRODUCTS</a>" in mu_plugin_source
        assert ">SERVICES</a>" in mu_plugin_source
        assert ">ARTICLES</a>" in mu_plugin_source
        assert ">ABOUT</a>" in mu_plugin_source

    def test_dropdown_sub_links(self, mu_plugin_source):
        """All 8 sub-links present in PHP."""
        sub_links = [
            "All Gravel Races",
            "How We Rate",
            "Custom Training Plans",
            "Gravel Handbook",
            "Coaching",
            "Consulting",
            "Slow Mid 38s",
            "Hot Takes",
        ]
        for link in sub_links:
            assert link in mu_plugin_source, f"Missing sub-link: {link}"

    def test_url_parity(self, mu_plugin_source, shared_header_html):
        """All URLs in Python header must appear in PHP header."""
        url_pattern = re.compile(r'href="(https://[^"]+)"')
        py_urls = set(url_pattern.findall(shared_header_html))
        php_urls_raw = mu_plugin_source
        for url in py_urls:
            # PHP uses $base and $substack variables, so check the path part
            path = url.replace("https://gravelgodcycling.com", "").replace(
                "https://gravelgodcycling.substack.com", ""
            )
            if path:
                assert path in php_urls_raw, f"Missing URL path in PHP: {path}"

    def test_about_has_no_dropdown(self, mu_plugin_source):
        """ABOUT link is a plain <a>, not wrapped in gg-site-header-item."""
        # In PHP: the ABOUT link is directly in nav, not in a dropdown wrapper
        # Find the ABOUT link and verify it's NOT preceded by gg-site-header-item
        lines = mu_plugin_source.split("\n")
        for i, line in enumerate(lines):
            if ">ABOUT</a>" in line:
                # This line should be a plain <a>, not inside a .gg-site-header-item div
                assert "gg-site-header-item" not in line
                break

    def test_external_link_attributes(self, mu_plugin_source):
        """Substack link has target=_blank and rel=noopener."""
        assert 'target="_blank"' in mu_plugin_source
        assert 'rel="noopener"' in mu_plugin_source

    def test_aria_current_support(self, mu_plugin_source):
        """PHP generates aria-current='page' from URL detection."""
        assert 'aria-current="page"' in mu_plugin_source
        assert "aria('races')" in mu_plugin_source or "$aria('races')" in mu_plugin_source

    def test_logo_present(self, mu_plugin_source):
        assert "gg-site-header-logo" in mu_plugin_source
        assert "Gravel God" in mu_plugin_source


# ── CSS Override Quality ───────────────────────────────────


class TestCSSOverrides:
    """Mu-plugin CSS must use !important and pseudo-class selectors
    to override Astra theme defaults."""

    def test_all_color_properties_have_important(self, mu_plugin_source):
        """Every 'color:' declaration must have !important."""
        style_match = re.search(r'<style[^>]*>(.*?)</style>', mu_plugin_source, re.DOTALL)
        css = style_match.group(1)
        # Find color declarations that DON'T have !important
        color_no_important = re.findall(
            r'(?:^|;|\{)\s*color:\s*[^;!]+(?:;|\})', css
        )
        # Filter out ones that actually have !important
        missing = [c.strip() for c in color_no_important if "!important" not in c]
        assert missing == [], f"Color declarations missing !important: {missing}"

    def test_link_and_visited_selectors(self, mu_plugin_source):
        """Must include :link and :visited pseudo-class selectors."""
        assert ":link" in mu_plugin_source
        assert ":visited" in mu_plugin_source

    def test_font_family_has_important(self, mu_plugin_source):
        """Font-family must have !important to override Astra."""
        style_match = re.search(r'<style[^>]*>(.*?)</style>', mu_plugin_source, re.DOTALL)
        css = style_match.group(1)
        font_decls = re.findall(r'font-family:[^;]+', css)
        for decl in font_decls:
            assert "!important" in decl, f"font-family missing !important: {decl}"

    def test_font_import_present(self, mu_plugin_source):
        """Google Fonts import for Sometype Mono."""
        assert "fonts.googleapis.com" in mu_plugin_source
        assert "Sometype+Mono" in mu_plugin_source


# ── Astra Theme Hiding ─────────────────────────────────────


class TestAstraHiding:
    """Astra header elements must be hidden via display:none."""

    ASTRA_SELECTORS = [
        ".ast-above-header-wrap",
        ".ast-main-header-wrap",
        ".ast-below-header-wrap",
        "#ast-desktop-header",
        "#masthead",
        ".site-header",
        ".ast-mobile-header-wrap",
    ]

    def test_all_astra_selectors_hidden(self, mu_plugin_source):
        for sel in self.ASTRA_SELECTORS:
            assert sel in mu_plugin_source, f"Missing Astra hiding selector: {sel}"

    def test_display_none_important(self, mu_plugin_source):
        assert "display: none !important" in mu_plugin_source


# ── Body Class Injection ───────────────────────────────────


class TestBodyClass:
    """gg-neo-brutalist-page body class prevents Code Snippet teal overrides."""

    def test_body_class_filter_registered(self, mu_plugin_source):
        assert "body_class" in mu_plugin_source
        assert "gg_add_neo_brutalist_class" in mu_plugin_source

    def test_adds_neo_brutalist_class(self, mu_plugin_source):
        assert "gg-neo-brutalist-page" in mu_plugin_source

    def test_skips_admin_pages(self, mu_plugin_source):
        assert "is_admin()" in mu_plugin_source

    def test_skips_front_page(self, mu_plugin_source):
        assert "is_front_page()" in mu_plugin_source


# ── WP Animation Fix ──────────────────────────────────────


class TestAnimationFix:
    """Training Plans page entrance animations don't fire in WP context.
    The mu-plugin must force opacity:1 and transform:none."""

    def test_opacity_override(self, mu_plugin_source):
        assert "opacity: 1 !important" in mu_plugin_source

    def test_transform_override(self, mu_plugin_source):
        assert "transform: none !important" in mu_plugin_source

    def test_tp_hero_selectors(self, mu_plugin_source):
        assert ".tp-hero" in mu_plugin_source


# ── URI Active Detection ───────────────────────────────────


class TestURIDetection:
    """PHP URI detection must cover all known page paths."""

    URI_PATTERNS = [
        ("/gravel-races", "races"),
        ("/race/", "races"),
        ("/products/", "products"),
        ("/coaching", "services"),
        ("/consulting", "services"),
        ("/articles", "articles"),
        ("/blog", "articles"),
        ("/about", "about"),
    ]

    def test_all_uri_patterns_handled(self, mu_plugin_source):
        for path, _key in self.URI_PATTERNS:
            assert path in mu_plugin_source, (
                f"Missing URI pattern '{path}' in active nav detection"
            )
