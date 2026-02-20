"""Tests for post-checkout success page generator."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the generator
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_success_pages import (
    PAGES,
    build_success_css,
    build_success_js,
    build_training_plan_success,
    build_coaching_success,
    build_consulting_success,
    generate_success_page,
)


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture(scope="module")
def all_pages():
    """Generate all 3 success pages."""
    return {key: generate_success_page(key) for key in PAGES}


@pytest.fixture(scope="module")
def success_css():
    return build_success_css()


@pytest.fixture(scope="module")
def success_js():
    return build_success_js()


# ── Page Generation ──────────────────────────────────────────


class TestPageGeneration:
    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_generates_valid_html(self, all_pages, key):
        html = all_pages[key]
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "</html>" in html

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_title(self, all_pages, key):
        html = all_pages[key]
        expected_title = PAGES[key]["title"]
        assert expected_title in html

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_canonical(self, all_pages, key):
        html = all_pages[key]
        expected = PAGES[key]["canonical"]
        assert f'rel="canonical"' in html
        assert expected in html

    def test_all_three_pages_generated(self, all_pages):
        assert len(all_pages) == 3
        assert "training-plans-success" in all_pages
        assert "coaching-welcome" in all_pages
        assert "consulting-confirmed" in all_pages


# ── SEO & Indexing ───────────────────────────────────────────


class TestSEO:
    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_noindex(self, all_pages, key):
        """All success pages must be noindexed."""
        html = all_pages[key]
        assert 'noindex' in html, f"{key} missing noindex"

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_meta_description(self, all_pages, key):
        html = all_pages[key]
        assert 'name="description"' in html


# ── GA4 Tracking ─────────────────────────────────────────────


class TestGA4Tracking:
    def test_purchase_event(self, success_js):
        assert "purchase" in success_js

    def test_session_id_extraction(self, success_js):
        assert "session_id" in success_js

    def test_crosssell_click_tracking(self, success_js):
        assert "success_crosssell_click" in success_js

    def test_conversion_dedup(self, success_js):
        assert "gg_converted_" in success_js
        assert "sessionStorage" in success_js

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_page_has_product_type_attr(self, all_pages, key):
        html = all_pages[key]
        assert "data-product-type" in html

    def test_training_plan_product_type(self, all_pages):
        assert 'data-product-type="training_plan"' in all_pages["training-plans-success"]

    def test_coaching_product_type(self, all_pages):
        assert 'data-product-type="coaching"' in all_pages["coaching-welcome"]

    def test_consulting_product_type(self, all_pages):
        assert 'data-product-type="consulting"' in all_pages["consulting-confirmed"]


# ── Brand Compliance ─────────────────────────────────────────


class TestBrandCompliance:
    def test_no_hardcoded_hex_in_css(self, success_css):
        """CSS should use var(--gg-color-*) only — no raw hex codes."""
        css_match = re.search(r'<style>(.*?)</style>', success_css, re.DOTALL)
        if not css_match:
            pytest.skip("No CSS found")
        css = css_match.group(1)
        hex_colors = re.findall(r'#[0-9a-fA-F]{3,8}', css)
        assert len(hex_colors) == 0, f"Found hardcoded hex in CSS: {hex_colors[:5]}"

    def test_no_border_radius(self, success_css):
        assert "border-radius" not in success_css

    def test_no_box_shadow(self, success_css):
        assert "box-shadow" not in success_css

    def test_no_opacity_transition(self, success_css):
        css_match = re.search(r'<style>(.*?)</style>', success_css, re.DOTALL)
        if not css_match:
            pytest.skip("No CSS found")
        css = css_match.group(1)
        transitions = re.findall(r'transition:\s*([^;]+);', css)
        for t in transitions:
            assert "opacity" not in t.lower(), f"Found opacity transition: {t}"

    def test_uses_brand_tokens(self, success_css):
        assert "var(--gg-color-" in success_css
        assert "var(--gg-font-" in success_css

    def test_no_entrance_animations(self, success_css):
        assert "@keyframes" not in success_css

    def test_correct_class_prefix(self, success_css):
        """All custom classes use gg-success- prefix."""
        classes = re.findall(r'\.(gg-[a-z][a-z0-9-]*)', success_css)
        for cls in classes:
            if cls.startswith(('gg-neo-brutalist', 'gg-site-header', 'gg-hero',
                              'gg-section', 'gg-breadcrumb', 'gg-footer',
                              'gg-mega-footer')):
                continue
            assert cls.startswith('gg-success-'), f"Non-prefixed class: .{cls}"


# ── CSS Token Validation ─────────────────────────────────────


class TestCssTokenValidation:
    def test_all_var_refs_defined(self, success_css):
        """Every var(--gg-*) must be defined in brand tokens."""
        tokens_path = Path(__file__).parent.parent.parent / "gravel-god-brand" / "tokens" / "tokens.css"
        if not tokens_path.exists():
            pytest.skip("Brand tokens not found")
        tokens_css = tokens_path.read_text()
        var_refs = set(re.findall(r'var\((--gg-[a-z0-9-]+)\)', success_css))
        for var_name in var_refs:
            assert var_name in tokens_css, f"Undefined token: {var_name}"


# ── JS Syntax ────────────────────────────────────────────────


class TestJSSyntax:
    def test_js_parses_via_node(self, success_js):
        """Validate JS syntax via Node.js subprocess."""
        js = success_js.replace("<script>", "").replace("</script>", "")
        test_script = f"""
try {{
    new Function({json.dumps(js)});
    console.log('SYNTAX_OK');
}} catch (e) {{
    console.error('SYNTAX_ERROR:', e.message);
    process.exit(1);
}}"""
        result = subprocess.run(
            ["node", "-e", test_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"JS syntax error: {result.stderr}"
        assert "SYNTAX_OK" in result.stdout


# ── Content Sections ─────────────────────────────────────────


class TestTrainingPlanSuccess:
    def test_has_hero(self):
        html = build_training_plan_success()
        assert "gg-success-hero" in html
        assert "Training Plan Is on the Way" in html

    def test_has_next_steps(self):
        html = build_training_plan_success()
        assert "WHAT HAPPENS NEXT" in html
        assert "Check Your Email" in html
        assert "Import Your Workouts" in html
        assert "Read the Training Guide" in html

    def test_cross_sells_coaching(self):
        html = build_training_plan_success()
        assert "/coaching/" in html
        assert "gg-success-cta" in html

    def test_has_support_link(self):
        html = build_training_plan_success()
        assert "gravelgodcoaching@gmail.com" in html


class TestCoachingSuccess:
    def test_has_hero(self):
        html = build_coaching_success()
        assert "gg-success-hero" in html
        assert "Welcome to Coaching" in html

    def test_has_intake_link(self):
        html = build_coaching_success()
        assert "/coaching/apply/" in html

    def test_cross_sells_races(self):
        html = build_coaching_success()
        assert "/gravel-races/" in html
        assert "gg-success-cta" in html

    def test_has_next_steps(self):
        html = build_coaching_success()
        assert "Fill Out the Intake Form" in html
        assert "Expect an Email" in html
        assert "We Train Together" in html


class TestConsultingSuccess:
    def test_has_hero(self):
        html = build_consulting_success()
        assert "gg-success-hero" in html
        assert "Consulting Session Confirmed" in html

    def test_has_next_steps(self):
        html = build_consulting_success()
        assert "Check Your Email" in html
        assert "Prepare Your Questions" in html
        assert "We Talk" in html

    def test_cross_sells_coaching(self):
        html = build_consulting_success()
        assert "/coaching/" in html
        assert "gg-success-cta" in html


# ── Shared Structure ─────────────────────────────────────────


class TestSharedStructure:
    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_site_header(self, all_pages, key):
        assert "gg-site-header" in all_pages[key]

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_mega_footer(self, all_pages, key):
        assert "gg-mega-footer" in all_pages[key]

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_breadcrumb(self, all_pages, key):
        assert "gg-breadcrumb" in all_pages[key]

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_ga4_config(self, all_pages, key):
        assert "G-EJJZ9T6M52" in all_pages[key]

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_success_css(self, all_pages, key):
        assert "gg-success-hero" in all_pages[key]
        assert "gg-success-steps" in all_pages[key]

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_success_js(self, all_pages, key):
        assert "session_id" in all_pages[key]
        assert "purchase" in all_pages[key]


# ── PAGES Config ─────────────────────────────────────────────


class TestPagesConfig:
    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_has_required_fields(self, key):
        page = PAGES[key]
        required = ["title", "description", "canonical", "robots", "builder", "output_path"]
        for field in required:
            assert field in page, f"{key} missing field: {field}"

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_all_noindex(self, key):
        assert PAGES[key]["robots"] == "noindex, follow"

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_output_path_is_html(self, key):
        assert PAGES[key]["output_path"].endswith(".html")

    @pytest.mark.parametrize("key", list(PAGES.keys()))
    def test_canonical_starts_with_slash(self, key):
        assert PAGES[key]["canonical"].startswith("/")
        assert PAGES[key]["canonical"].endswith("/")
