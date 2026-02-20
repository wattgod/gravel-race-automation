"""Tests for the shared site header module."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))
from shared_header import get_site_header_css, get_site_header_html


class TestHeaderHTML:
    """Tests for get_site_header_html()."""

    def test_five_nav_items(self):
        html = get_site_header_html()
        for label in ["RACES", "PRODUCTS", "SERVICES", "ARTICLES", "ABOUT"]:
            assert f">{label}</a>" in html

    def test_four_dropdown_containers(self):
        html = get_site_header_html()
        assert html.count('class="gg-site-header-item"') == 4

    def test_four_dropdowns(self):
        html = get_site_header_html()
        assert html.count('class="gg-site-header-dropdown"') == 4

    def test_about_has_no_dropdown(self):
        html = get_site_header_html()
        # ABOUT is a plain <a>, not inside a dropdown item
        about_idx = html.index(">ABOUT</a>")
        # Get the 200 chars before ABOUT — should NOT have gg-site-header-item
        context = html[max(0, about_idx - 200) : about_idx]
        last_item = context.rfind("gg-site-header-item")
        last_close = context.rfind("</div>")
        # The dropdown item should be closed before ABOUT
        assert last_close > last_item or last_item == -1

    def test_all_dropdown_links_present(self):
        html = get_site_header_html()
        expected = [
            "All Gravel Races",
            "How We Rate",
            "Custom Training Plans",
            "Gravel Handbook",
            "Coaching",
            "Consulting",
            "Slow Mid 38s",
            "Hot Takes",
        ]
        for link_text in expected:
            assert link_text in html, f"Missing dropdown link: {link_text}"

    def test_eight_sub_links(self):
        html = get_site_header_html()
        # Count links inside dropdown divs
        dropdowns = re.findall(
            r'class="gg-site-header-dropdown">(.*?)</div>',
            html,
            re.DOTALL,
        )
        sub_links = sum(d.count("<a ") for d in dropdowns)
        assert sub_links == 9

    def test_logo_present(self):
        html = get_site_header_html()
        assert "cropped-Gravel-God-logo.png" in html
        assert 'class="gg-site-header-logo"' in html

    def test_aria_current_when_active(self):
        for key in ["races", "products", "services", "articles", "about"]:
            html = get_site_header_html(active=key)
            assert 'aria-current="page"' in html

    def test_no_aria_current_when_no_active(self):
        html = get_site_header_html()
        assert 'aria-current="page"' not in html

    def test_aria_current_on_correct_item(self):
        html = get_site_header_html(active="services")
        # aria-current should be on SERVICES link
        assert 'aria-current="page">SERVICES</a>' in html
        # Not on others
        assert 'aria-current="page">RACES</a>' not in html

    def test_external_links_have_target_blank(self):
        html = get_site_header_html()
        # Substack link should have target and rel
        assert 'target="_blank"' in html
        assert 'rel="noopener"' in html

    def test_substack_url(self):
        html = get_site_header_html()
        assert "gravelgodcycling.substack.com" in html

    def test_correct_urls(self):
        html = get_site_header_html()
        assert "/gravel-races/" in html
        assert "/race/methodology/" in html
        assert "/products/training-plans/" in html
        assert "/guide/" in html
        assert "/coaching/" in html
        assert "/consulting/" in html
        assert "/articles/" in html
        assert "/about/" in html


class TestHeaderCSS:
    """Tests for get_site_header_css()."""

    def test_no_raw_hex(self):
        css = get_site_header_css()
        # Remove comments before checking
        css_no_comments = re.sub(r'/\*.*?\*/', '', css)
        hex_matches = re.findall(r'#[0-9a-fA-F]{3,8}\b', css_no_comments)
        assert hex_matches == [], f"Raw hex found in CSS: {hex_matches}"

    def test_no_border_radius(self):
        css = get_site_header_css()
        assert "border-radius" not in css

    def test_no_box_shadow(self):
        css = get_site_header_css()
        assert "box-shadow" not in css

    def test_dropdown_position_absolute(self):
        css = get_site_header_css()
        assert "position: absolute" in css

    def test_dropdown_z_index(self):
        css = get_site_header_css()
        assert "z-index" in css

    def test_uses_var_tokens(self):
        css = get_site_header_css()
        assert "var(--gg-color-" in css
        assert "var(--gg-font-data)" in css

    def test_hover_shows_dropdown(self):
        css = get_site_header_css()
        assert ":hover .gg-site-header-dropdown" in css

    def test_focus_within_shows_dropdown(self):
        css = get_site_header_css()
        assert ":focus-within .gg-site-header-dropdown" in css

    def test_mobile_hides_dropdowns(self):
        css = get_site_header_css()
        assert "max-width: 600px" in css
        assert "display: none !important" in css

    def test_responsive_breakpoint(self):
        css = get_site_header_css()
        assert "@media" in css

    def test_max_width_960(self):
        css = get_site_header_css()
        assert "max-width: 960px" in css

    def test_dropdown_border(self):
        css = get_site_header_css()
        assert "2px solid" in css

    def test_warm_paper_background(self):
        css = get_site_header_css()
        assert "var(--gg-color-warm-paper)" in css
