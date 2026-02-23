"""Tests for the shared mega-footer module."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))
from shared_footer import get_mega_footer_css, get_mega_footer_html


class TestMegaFooterHTML:
    """Verify mega-footer HTML structure and content."""

    def setup_method(self):
        self.html = get_mega_footer_html()

    # ── Nav headings ─────────────────────────────────────────

    def test_has_races_heading(self):
        assert ">RACES</h4>" in self.html

    def test_has_products_heading(self):
        assert ">PRODUCTS</h4>" in self.html

    def test_has_services_heading(self):
        assert ">SERVICES</h4>" in self.html

    def test_has_articles_heading(self):
        assert ">ARTICLES</h4>" in self.html

    def test_has_newsletter_heading(self):
        assert ">NEWSLETTER</h4>" in self.html

    # ── Links ────────────────────────────────────────────────

    def test_races_links(self):
        assert "/gravel-races/" in self.html
        assert "/race/methodology/" in self.html

    def test_products_links(self):
        assert "/products/training-plans/" in self.html
        assert "/guide/" in self.html

    def test_services_links(self):
        assert "/coaching/" in self.html
        assert "/consulting/" in self.html

    def test_articles_links(self):
        assert "substack.com" in self.html
        assert "/articles/" in self.html

    # ── Brand ────────────────────────────────────────────────

    def test_brand_title(self):
        assert "GRAVEL GOD CYCLING" in self.html

    def test_brand_tagline(self):
        assert "Practical coaching and training" in self.html

    # ── Newsletter ───────────────────────────────────────────

    def test_subscribe_button(self):
        assert "SUBSCRIBE" in self.html

    def test_subscribe_ga4(self):
        assert 'data-ga="subscribe_click"' in self.html
        assert 'data-ga-label="mega_footer"' in self.html

    # ── Legal ────────────────────────────────────────────────

    def test_copyright(self):
        assert "Gravel God Cycling. All rights reserved." in self.html

    def test_copyright_year(self):
        from datetime import date
        assert str(date.today().year) in self.html

    def test_disclaimer(self):
        assert "produced independently" in self.html
        assert "not affiliated with" in self.html

    def test_has_legal_links_section(self):
        assert "gg-mega-footer-legal-links" in self.html

    def test_has_privacy_link(self):
        assert 'href="https://gravelgodcycling.com/privacy/"' in self.html

    def test_has_terms_link(self):
        assert 'href="https://gravelgodcycling.com/terms/"' in self.html

    def test_has_cookies_link(self):
        assert 'href="https://gravelgodcycling.com/cookies/"' in self.html

    def test_legal_links_in_nav(self):
        """Legal links must be inside a <nav> element for accessibility."""
        assert '<nav class="gg-mega-footer-legal-links">' in self.html

    def test_three_legal_links(self):
        """Exactly 3 legal links: Privacy, Terms, Cookies."""
        section = self.html.split("gg-mega-footer-legal-links")[1].split("</nav>")[0]
        link_count = section.count("<a ")
        assert link_count == 3, f"Expected 3 legal links, got {link_count}"

    def test_legal_link_labels(self):
        """Links must have visible text labels."""
        assert ">Privacy</a>" in self.html
        assert ">Terms</a>" in self.html
        assert ">Cookies</a>" in self.html

    # ── External links ───────────────────────────────────────

    def test_external_links_noopener(self):
        """All target=_blank links must have rel=noopener."""
        targets = re.findall(r'<a [^>]*target="_blank"[^>]*>', self.html)
        assert len(targets) >= 2, "Expected at least 2 external links"
        for tag in targets:
            assert 'rel="noopener"' in tag, f"Missing rel=noopener: {tag}"

    # ── Structure ────────────────────────────────────────────

    def test_footer_tag(self):
        assert '<footer class="gg-mega-footer">' in self.html
        assert "</footer>" in self.html

    def test_six_columns(self):
        cols = self.html.count("gg-mega-footer-col")
        assert cols == 6, f"Expected 6 columns, got {cols}"


class TestMegaFooterCSS:
    """Verify mega-footer CSS follows brand rules."""

    def setup_method(self):
        self.css = get_mega_footer_css()

    def test_no_raw_hex_colors(self):
        """All colors must use var(--gg-*) tokens, not raw hex."""
        lines = self.css.split("\n")
        for line in lines:
            if line.strip().startswith("/*") or line.strip().startswith("*"):
                continue
            # Find hex patterns that aren't inside var() or comment
            hexes = re.findall(r'#[0-9a-fA-F]{3,8}', line)
            for h in hexes:
                assert False, f"Raw hex {h} found in CSS: {line.strip()}"

    def test_no_border_radius(self):
        assert "border-radius" not in self.css

    def test_no_box_shadow(self):
        assert "box-shadow" not in self.css

    def test_uses_brand_fonts(self):
        assert "var(--gg-font-data)" in self.css
        assert "var(--gg-font-editorial)" in self.css

    def test_responsive_tablet(self):
        assert "max-width: 900px" in self.css

    def test_responsive_mobile(self):
        assert "max-width: 600px" in self.css

    def test_six_column_grid(self):
        assert "grid-template-columns:" in self.css
        # Desktop should have 6 columns
        assert "1.5fr 1fr 1fr 1fr 1fr 1fr" in self.css

    def test_tablet_three_columns(self):
        assert "1fr 1fr 1fr" in self.css

    def test_mobile_one_column(self):
        # After the 3-col breakpoint, mobile should collapse to 1
        mobile_match = re.search(r'600px.*?grid-template-columns:\s*1fr\s*;', self.css, re.DOTALL)
        assert mobile_match, "Mobile should collapse to 1 column"

    def test_css_prefix(self):
        """All classes must use gg-mega-footer- prefix."""
        classes = re.findall(r'\.(gg-[a-z][a-z0-9-]*)', self.css)
        for cls in classes:
            assert cls.startswith("gg-mega-footer"), f"Wrong prefix: .{cls}"

    def test_max_width_960(self):
        assert "max-width: 960px" in self.css
