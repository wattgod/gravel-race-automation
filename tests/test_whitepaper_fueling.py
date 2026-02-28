"""Tests for the fueling methodology white paper page generator.

Validates page structure, infographics, CSS, JS, nav integration,
accessibility, brand compliance, deploy function, and content accuracy.
"""
from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure wordpress/ is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "wordpress"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_whitepaper_fueling import (
    build_cta,
    build_duration_problem,
    build_hero,
    build_inline_cta,
    build_jensen,
    build_limitations,
    build_metabolic_testing,
    build_nav,
    build_phenotype,
    build_power_curve,
    build_practical,
    build_references,
    build_tldr,
    build_whitepaper_css,
    build_whitepaper_js,
    generate_whitepaper_page,
    main,
)


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def page_html():
    """Generate the full page HTML once for all tests."""
    return generate_whitepaper_page()


@pytest.fixture(scope="module")
def page_css():
    """Generate CSS once for all tests."""
    return build_whitepaper_css()


@pytest.fixture(scope="module")
def page_js():
    """Generate JS once for all tests."""
    return build_whitepaper_js()


# ── TestPageGeneration ────────────────────────────────────────


class TestPageGeneration:
    """Test that the page generates valid HTML with required structure."""

    def test_generates_html(self, page_html):
        assert "<!DOCTYPE html>" in page_html

    def test_has_html_lang(self, page_html):
        assert '<html lang="en">' in page_html

    def test_has_head_section(self, page_html):
        assert "<head>" in page_html
        assert "</head>" in page_html

    def test_has_body_section(self, page_html):
        assert "<body>" in page_html
        assert "</body>" in page_html

    def test_has_title(self, page_html):
        assert "How Many Carbs Do You Actually Need?" in page_html
        assert "<title>" in page_html

    def test_has_canonical_url(self, page_html):
        assert 'rel="canonical"' in page_html
        assert "/fueling-methodology/" in page_html

    def test_has_meta_description(self, page_html):
        assert 'name="description"' in page_html
        assert "60-90" in page_html

    def test_has_meta_robots(self, page_html):
        assert 'name="robots" content="index, follow"' in page_html

    def test_has_og_tags(self, page_html):
        assert 'property="og:title"' in page_html
        assert 'property="og:description"' in page_html
        assert 'property="og:type" content="article"' in page_html
        assert 'property="og:url"' in page_html

    def test_has_twitter_card(self, page_html):
        assert 'name="twitter:card"' in page_html

    def test_has_all_sections(self, page_html):
        """All 8 paper sections + TL;DR + CTA present."""
        section_ids = [
            "hero", "tldr", "duration-problem", "metabolic-testing",
            "power-curve", "jensen", "practical", "phenotype",
            "limitations", "references", "cta",
        ]
        for sid in section_ids:
            assert f'id="{sid}"' in page_html, f"Missing section: {sid}"

    def test_page_wrapper_class(self, page_html):
        assert "gg-wp-page" in page_html

    def test_has_json_ld(self, page_html):
        assert "application/ld+json" in page_html
        assert "ScholarlyArticle" in page_html

    def test_has_viewport_meta(self, page_html):
        assert 'name="viewport"' in page_html


# ── TestHero ──────────────────────────────────────────────────


class TestHero:
    """Test hero section with stat counters."""

    def test_has_title(self):
        html = build_hero()
        assert "How Many Carbs" in html

    def test_has_subtitle(self):
        html = build_hero()
        assert "yours" in html.lower()

    def test_has_counters(self):
        html = build_hero()
        assert "gg-wp-counter" in html

    def test_has_data_counter_attributes(self):
        html = build_hero()
        assert 'data-counter="27"' in html
        assert 'data-counter="83"' in html
        assert 'data-counter="8"' in html

    def test_counter_labels(self):
        html = build_hero()
        assert "overshoots" in html
        assert "fat burn" in html
        assert "gut training" in html


# ── TestInfographics ──────────────────────────────────────────


class TestInfographics:
    """Test infographic elements: SVG charts, bars, tables, accordions."""

    def test_murphy_comparison_bars(self):
        html = build_duration_problem()
        assert "gg-wp-compare-row" in html
        assert "80 g/hr" in html
        assert "63 g/hr" in html

    def test_murphy_bars_animate(self):
        html = build_duration_problem()
        assert 'data-animate="bars"' in html
        assert "data-target-w" in html

    def test_crossover_table(self):
        html = build_metabolic_testing()
        assert "Well-trained endurance" in html
        assert "Minimally trained" in html
        assert "~5.4" in html

    def test_calibration_scatter_svg(self):
        html = build_power_curve()
        assert "calibration" in html.lower() or "Calibration" in html
        assert "<svg" in html
        assert "polyline" in html

    def test_brackets_table(self):
        html = build_power_curve()
        assert "80&ndash;100" in html or "80-100" in html
        assert "30&ndash;50" in html or "30-50" in html

    def test_formula_block(self):
        html = build_power_curve()
        assert "gg-wp-formula" in html
        assert "intensity_factor" in html
        assert "1.4" in html

    def test_worked_examples_accordion(self):
        html = build_power_curve()
        assert "data-accordion" in html
        assert "Murphy" in html
        assert "95 kg" in html

    def test_jensen_comparison_bars(self):
        html = build_jensen()
        assert "100.8g" in html
        assert "55.0g" in html
        assert "83% overestimate" in html
        assert 'data-animate="bars"' in html

    def test_vlamax_table(self):
        html = build_phenotype()
        assert "VLaMax" in html
        assert "Diesel" in html
        assert "All-rounder" in html
        assert "gg-wp-heat-low" in html

    def test_depletion_timeline_bars(self):
        html = build_phenotype()
        assert "Glycogen Depletion" in html
        assert "12+ hrs" in html
        assert "5&ndash;6 hrs" in html or "5-6 hrs" in html

    def test_limitations_accordions(self):
        html = build_limitations()
        count = html.count("data-accordion")
        assert count == 10, f"Expected 10 limitation accordions, got {count}"

    def test_references_collapsible(self):
        html = build_references()
        assert "data-accordion" in html
        assert "Sources (38)" in html

    def test_practical_callout_cards(self):
        html = build_practical()
        assert "gg-wp-callout-card" in html
        count = html.count("gg-wp-callout-card")
        assert count == 5, f"Expected 5 callout cards, got {count}"

    def test_tldr_cards(self):
        html = build_tldr()
        assert "gg-wp-tldr-card" in html
        count = html.count('"gg-wp-tldr-card"')
        assert count == 3, f"Expected 3 TL;DR cards, got {count}"


# ── TestCSS ───────────────────────────────────────────────────


class TestCSS:
    """Test CSS structure and neo-brutalist compliance."""

    def test_has_wp_prefix_classes(self, page_css):
        assert ".gg-wp-page" in page_css
        assert ".gg-wp-hero" in page_css
        assert ".gg-wp-section" in page_css
        assert ".gg-wp-prose" in page_css

    def test_neo_brutalist_border_radius(self, page_css):
        assert "border-radius: 0 !important" in page_css

    def test_neo_brutalist_box_shadow(self, page_css):
        assert "box-shadow: none !important" in page_css

    def test_uses_font_variables(self, page_css):
        assert "var(--gg-font-data)" in page_css
        assert "var(--gg-font-editorial)" in page_css

    def test_uses_color_variables(self, page_css):
        assert "var(--gg-color-dark-brown)" in page_css
        assert "var(--gg-color-gold)" in page_css
        assert "var(--gg-color-teal)" in page_css

    def test_prose_max_width(self, page_css):
        """Prose sections use 720px for readability."""
        assert "max-width: 720px" in page_css

    def test_responsive_breakpoints(self, page_css):
        assert "@media" in page_css
        assert "max-width: 600px" in page_css

    def test_reduced_motion(self, page_css):
        assert "prefers-reduced-motion" in page_css

    def test_figure_title_gold_border(self, page_css):
        assert "gg-wp-figure-title" in page_css

    def test_takeaway_teal_border(self, page_css):
        assert "gg-wp-figure-takeaway" in page_css

    def test_accordion_styles(self, page_css):
        assert "gg-wp-accordion" in page_css

    def test_tldr_grid(self, page_css):
        assert "gg-wp-tldr-grid" in page_css

    def test_formula_block(self, page_css):
        assert "gg-wp-formula-block" in page_css

    def test_callout_card(self, page_css):
        assert "gg-wp-callout-card" in page_css

    def test_inline_cta_css(self, page_css):
        assert ".gg-wp-inline-cta" in page_css

    def test_header_css_included(self, page_css):
        assert "gg-site-header" in page_css


# ── TestJS ────────────────────────────────────────────────────


class TestJS:
    """Test JS functionality: animations, accordion, digit roller."""

    def test_has_script_tag(self, page_js):
        assert "<script>" in page_js

    def test_intersection_observer(self, page_js):
        assert "IntersectionObserver" in page_js

    def test_bar_animation(self, page_js):
        assert "data-animate" in page_js or "data-target-w" in page_js

    def test_accordion_handler(self, page_js):
        assert "data-accordion" in page_js
        assert "aria-expanded" in page_js

    def test_digit_roller(self, page_js):
        assert "data-counter" in page_js
        assert "animateCounter" in page_js

    def test_reduced_motion_check(self, page_js):
        assert "prefers-reduced-motion" in page_js

    def test_ga4_tracking(self, page_js):
        assert "gtag" in page_js
        assert "whitepaper_accordion" in page_js

    def test_strict_mode(self, page_js):
        assert "'use strict'" in page_js


# ── TestNavIntegration ────────────────────────────────────────


class TestNavIntegration:
    """Test header and footer nav integration."""

    def test_header_has_white_papers_link(self, page_html):
        assert "/fueling-methodology/" in page_html

    def test_header_active_articles(self, page_html):
        """Articles tab should be active."""
        nav_html = build_nav()
        assert 'aria-current="page"' in nav_html

    def test_footer_has_articles_section(self, page_html):
        assert "ARTICLES" in page_html

    def test_footer_has_state_of_gravel(self, page_html):
        assert "/insights/" in page_html

    def test_breadcrumb_present(self, page_html):
        assert "gg-wp-breadcrumb" in page_html
        assert "Articles" in page_html
        assert "Fueling Methodology" in page_html


# ── TestAccessibility ─────────────────────────────────────────


class TestAccessibility:
    """Test accessibility features."""

    def test_skip_link(self, page_html):
        assert "gg-skip-link" in page_html
        assert "#hero" in page_html

    def test_aria_labels_on_svgs(self):
        html = build_duration_problem()
        assert "aria-label" in html

    def test_aria_labels_on_tables(self):
        html = build_metabolic_testing()
        assert 'role="table"' in html
        assert "aria-label" in html

    def test_accordion_aria(self):
        html = build_limitations()
        assert 'aria-expanded="false"' in html
        assert 'aria-hidden="true"' in html

    def test_lang_attribute(self, page_html):
        assert 'lang="en"' in page_html


# ── TestBrandCompliance ───────────────────────────────────────


class TestBrandCompliance:
    """Test brand token usage and GA4 compliance."""

    def test_uses_ga4_head_snippet(self, page_html):
        """Must use get_ga4_head_snippet(), not inline GA4 blocks."""
        from brand_tokens import GA_MEASUREMENT_ID
        assert GA_MEASUREMENT_ID in page_html

    def test_uses_preload_hints(self, page_html):
        assert 'rel="preload"' in page_html

    def test_uses_brand_tokens_css(self, page_html):
        """Page CSS includes :root custom properties."""
        assert "--gg-color-dark-brown" in page_html

    def test_uses_cookie_consent(self, page_html):
        assert "gg-consent-banner" in page_html

    def test_uses_ab_head_snippet(self, page_html):
        assert "gg_ab_assign" in page_html

    def test_no_hardcoded_ga4_id(self, page_html):
        """GA4 ID should come from brand_tokens, not hardcoded inline."""
        # The ID should appear but only from the snippet function
        from brand_tokens import get_ga4_head_snippet
        snippet = get_ga4_head_snippet()
        # Verify it's in the page via the snippet
        assert snippet[:50] in page_html


# ── TestDeployFunction ────────────────────────────────────────


class TestDeployFunction:
    """Test that the deploy function exists and is wired up."""

    def test_sync_whitepaper_exists(self):
        push_mod = importlib.import_module("push_wordpress")
        assert hasattr(push_mod, "sync_whitepaper")

    def test_sync_whitepaper_is_callable(self):
        push_mod = importlib.import_module("push_wordpress")
        assert callable(push_mod.sync_whitepaper)

    def test_cli_has_sync_whitepaper_flag(self):
        """The argparse parser should have --sync-whitepaper."""
        source = (REPO_ROOT / "scripts" / "push_wordpress.py").read_text()
        assert "--sync-whitepaper" in source

    def test_deploy_all_includes_whitepaper(self):
        """deploy_all composite flag should include sync_whitepaper."""
        source = (REPO_ROOT / "scripts" / "push_wordpress.py").read_text()
        assert "args.sync_whitepaper = True" in source


# ── TestContentAccuracy ───────────────────────────────────────


class TestContentAccuracy:
    """Test that key numbers from the paper appear in the page."""

    def test_citation_count(self, page_html):
        assert "38" in page_html

    def test_duration_bracket_count(self, page_html):
        assert "5" in page_html  # 5 duration brackets

    def test_exponent_value(self, page_html):
        assert "1.4" in page_html

    def test_murphy_example_rate(self, page_html):
        assert "63" in page_html  # 63 g/hr

    def test_murphy_weight(self, page_html):
        assert "95" in page_html  # 95 kg

    def test_murphy_ftp(self, page_html):
        assert "220" in page_html  # 220W

    def test_wkg_floor(self, page_html):
        assert "1.5" in page_html

    def test_wkg_ceil(self, page_html):
        assert "4.5" in page_html

    def test_race_count(self, page_html):
        assert "328" in page_html

    def test_counter_in_page(self, page_html):
        """Hero counters are present in the page."""
        assert 'data-counter="27"' in page_html

    def test_overestimate_percentage(self, page_html):
        """83% fat oxidation overestimate from Jensen's inequality."""
        assert "83%" in page_html

    def test_calibration_max_error(self, page_html):
        """0.7 g/hr max calibration error."""
        assert "0.7" in page_html

    def test_old_formula_rate(self, page_html):
        """Old formula gave 80 g/hr for Murphy."""
        assert "80 g/hr" in page_html

    def test_phenotype_gap(self, page_html):
        """60-90 g/hr difference between phenotypes."""
        ph_html = build_phenotype()
        assert "60" in ph_html
        assert "90" in ph_html

    def test_references_have_dois(self):
        """References should contain DOI links."""
        html = build_references()
        assert "doi.org" in html

    def test_reference_count(self):
        """Should have 38 reference items."""
        html = build_references()
        count = html.count("gg-wp-ref-item")
        assert count == 38, f"Expected 38 references, got {count}"


# ── TestCSSBrandAudit ────────────────────────────────────────


class TestCSSBrandAudit:
    """Catch hardcoded colors that bypass brand tokens."""

    def test_no_hardcoded_hex(self, page_css):
        css_no_comments = re.sub(r'/\*.*?\*/', '', page_css, flags=re.DOTALL)
        hexes = re.findall(r'#[0-9a-fA-F]{3,8}\b', css_no_comments)
        assert hexes == [], f"Hardcoded hex in CSS: {hexes[:10]}"

    def test_no_hardcoded_rgba(self, page_css):
        css_no_comments = re.sub(r'/\*.*?\*/', '', page_css, flags=re.DOTALL)
        rgbas = re.findall(r'rgba?\([^)]+\)', css_no_comments)
        assert rgbas == [], f"Hardcoded rgba() in CSS: {rgbas[:5]}"


# ── TestProgressiveEnhancement ───────────────────────────────


class TestProgressiveEnhancement:
    """Test .gg-has-js progressive enhancement guard."""

    def test_has_js_guard_in_js(self, page_js):
        assert "gg-has-js" in page_js

    def test_has_js_guard_in_css(self, page_css):
        assert ".gg-has-js" in page_css

    def test_animated_bars_are_html_not_svg_rects(self, page_html):
        """Animated bars must use HTML divs, not SVG <rect>. SVG rect width
        animation doesn't work with CSS transitions (lesson learned)."""
        svg_rects_with_target = re.findall(r'<rect[^>]*data-target-w', page_html)
        assert svg_rects_with_target == [], (
            f"Found {len(svg_rects_with_target)} SVG <rect> elements with data-target-w. "
            "Animated bars must use HTML divs — SVG rect width can't be animated via CSS."
        )

    def test_bars_use_tw_custom_property_not_inline_width(self, page_html):
        """Animated bars must use style='--tw:X%', NOT style='width:X%'.
        Inline width beats .gg-has-js class selector, breaking animation.
        CSS custom properties don't set inline width, so .gg-has-js can zero it."""
        bar_fills = re.findall(r'<div[^>]*class="[^"]*gg-wp-bar-fill[^"]*"[^>]*>', page_html)
        for bar in bar_fills:
            if 'data-target-w' in bar:
                assert 'style="--tw:' in bar, (
                    f"Bar uses inline width instead of --tw custom property: {bar[:120]}. "
                    "This breaks .gg-has-js animation guard (inline wins over class selector)."
                )
                assert re.search(r'style="[^"]*width\s*:', bar) is None, (
                    f"Bar has inline 'width:' property: {bar[:120]}. "
                    "Must use --tw custom property only."
                )

    def test_reduced_motion_uses_tw_fallback(self, page_css):
        """prefers-reduced-motion must use var(--tw, 100%), NOT width: auto.
        Empty divs with width:auto compute to 0 — bars disappear."""
        # Extract the full media query block (nested braces)
        start = page_css.find('prefers-reduced-motion')
        assert start != -1, "Missing prefers-reduced-motion media query"
        # Find the opening { of the media query, then match to its closing }
        open_brace = page_css.index('{', start)
        depth = 1
        pos = open_brace + 1
        while depth > 0 and pos < len(page_css):
            if page_css[pos] == '{':
                depth += 1
            elif page_css[pos] == '}':
                depth -= 1
            pos += 1
        motion_block = page_css[open_brace:pos]
        assert 'width: auto' not in motion_block, (
            "prefers-reduced-motion uses 'width: auto' which computes to 0 for empty divs. "
            "Must use 'width: var(--tw, 100%)' instead."
        )
        assert 'var(--tw' in motion_block, (
            "prefers-reduced-motion must use var(--tw, 100%) to show bars at target width"
        )

    def test_bar_css_reads_tw_variable(self, page_css):
        """.gg-wp-bar-fill must use width: var(--tw, 100%) for no-JS fallback."""
        assert 'var(--tw, 100%)' in page_css, (
            "Bar fill CSS must use 'width: var(--tw, 100%)' — the 100% fallback "
            "ensures bars are visible when --tw is not set (shouldn't happen but safe)."
        )

    def test_gg_has_js_zeros_bar_width(self, page_css):
        """When JS loads, .gg-has-js must zero bar widths via class selector."""
        assert '.gg-has-js' in page_css
        # Find the rule that zeros bars
        zero_rule = re.search(
            r'\.gg-has-js\s+\[data-animate="bars"\]\s+\.gg-wp-bar-fill\s*\{[^}]*width:\s*0',
            page_css
        )
        assert zero_rule, (
            ".gg-has-js must zero .gg-wp-bar-fill width. Expected: "
            ".gg-has-js [data-animate='bars'] .gg-wp-bar-fill { width: 0; }"
        )

    def test_bar_ml_custom_property_for_offset(self, page_css):
        """Lab range bar uses --ml custom property for margin-left offset."""
        assert 'var(--ml, 0)' in page_css, (
            "Bar fill CSS must use 'margin-left: var(--ml, 0)' for offset bars "
            "(lab range bar needs 60% left offset)."
        )

    def test_lab_range_bar_uses_ml_not_inline_margin(self, page_html):
        """Lab range bar offset must use --ml custom property, not inline margin-left."""
        duration_html = build_duration_problem()
        gold_bars = re.findall(r'<div[^>]*gg-wp-bar-fill--gold[^>]*>', duration_html)
        for bar in gold_bars:
            if 'data-target-w' in bar:
                assert '--ml:' in bar, (
                    f"Lab range bar uses inline margin-left instead of --ml: {bar[:120]}"
                )
                assert 'margin-left:' not in bar, (
                    f"Lab range bar has inline margin-left: {bar[:120]}. "
                    "Must use --ml custom property."
                )


# ── TestBarProportionality ──────────────────────────────────


class TestBarProportionality:
    """Test that bar widths are proportional to their labeled values."""

    def test_murphy_bars_proportional(self):
        """Murphy comparison: 80g bar > 63g bar. Old formula > new formula."""
        html = build_duration_problem()
        bars = re.findall(r'--tw:(\d+)%', html)
        assert len(bars) >= 2, f"Expected at least 2 bars, got {len(bars)}"
        # First bar (old formula, 80g) should be wider than second (new, 63g)
        assert int(bars[0]) > int(bars[1]), (
            f"Old formula bar ({bars[0]}%) should be wider than W/kg bar ({bars[1]}%)"
        )

    def test_jensen_bars_proportional(self):
        """Jensen: average-power bar (100.8g) > second-by-second bar (55.0g)."""
        html = build_jensen()
        bars = re.findall(r'--tw:(\d+)%', html)
        assert len(bars) >= 2, f"Expected at least 2 bars, got {len(bars)}"
        assert int(bars[0]) > int(bars[1]), (
            f"Average power bar ({bars[0]}%) should be wider than per-second bar ({bars[1]}%)"
        )

    def test_phenotype_bars_proportional(self):
        """Phenotype: diesel (12+h) > average > glycolytic (5-6h)."""
        html = build_phenotype()
        bars = re.findall(r'--tw:(\d+)%', html)
        assert len(bars) >= 3, f"Expected 3 bars, got {len(bars)}"
        assert int(bars[0]) > int(bars[1]) > int(bars[2]), (
            f"Bars should descend: diesel ({bars[0]}%) > avg ({bars[1]}%) > glycolytic ({bars[2]}%)"
        )

    def test_metabolic_bars_descending(self):
        """Crossover table: well-trained has highest %, minimally trained lowest."""
        html = build_metabolic_testing()
        bars = re.findall(r'--tw:(\d+)%', html)
        assert len(bars) == 5, f"Expected 5 fitness category bars, got {len(bars)}"
        for i in range(len(bars) - 1):
            assert int(bars[i]) >= int(bars[i + 1]), (
                f"Bar {i} ({bars[i]}%) should be >= bar {i+1} ({bars[i+1]}%)"
            )

    def test_all_bar_widths_are_valid_percentages(self, page_html):
        """All --tw values must be valid percentages between 1-100."""
        tw_values = re.findall(r'--tw:(\d+)%', page_html)
        for tw in tw_values:
            pct = int(tw)
            assert 1 <= pct <= 100, f"Invalid bar width: {pct}%"


# ── TestContentLanguage ────────────────────────────────────


class TestContentLanguage:
    """Test content uses gravel-specific language, not road/crit references."""

    def test_no_crit_reference(self, page_html):
        """A gravel racing site should not reference crits (criteriums).
        'crit' is road racing terminology."""
        # Case insensitive search, but only for standalone 'crit' not 'critical' etc.
        crit_refs = re.findall(r'\bcrit\b', page_html, re.IGNORECASE)
        assert crit_refs == [], (
            f"Found {len(crit_refs)} references to 'crit' (criterium). "
            "This is a gravel racing site — use gravel-specific terms."
        )

    def test_no_peloton_reference(self, page_html):
        """Gravel racing doesn't have pelotons in the road-race sense."""
        assert 'peloton' not in page_html.lower(), (
            "Reference to 'peloton' found. Use gravel-specific terms."
        )

    def test_hero_speaks_to_rider(self):
        """Hero should address the reader directly (you/your)."""
        html = build_hero()
        subtitle = re.search(r'gg-wp-hero-subtitle">(.*?)</p>', html, re.DOTALL)
        assert subtitle, "Missing hero subtitle"
        text = subtitle.group(1).lower()
        assert 'your' in text or 'you' in text, (
            "Hero subtitle should address the reader directly (you/your)"
        )

    def test_no_criterium_reference(self, page_html):
        """A gravel site should not reference criteriums."""
        assert 'Criterium' not in page_html
        assert 'criterium' not in page_html

    def test_inline_ctas_present(self, page_html):
        """Page should have at least 2 inline CTAs."""
        count = page_html.count("gg-wp-inline-cta")
        assert count >= 2, f"Expected at least 2 inline CTAs, got {count}"

    def test_hero_has_eyebrow(self):
        """Hero should have eyebrow text."""
        html = build_hero()
        assert "gg-wp-hero-eyebrow" in html

    def test_real_race_names(self, page_html):
        """Page should reference real gravel races."""
        has_race = (
            "Unbound" in page_html
            or "SBT GRVL" in page_html
            or "Leadville" in page_html
            or "Mid South" in page_html
        )
        assert has_race, "Page should reference real gravel race names"


# ── TestFormulaAccessibility ─────────────────────────────────


class TestFormulaAccessibility:
    """Test formula block accessibility."""

    def test_formula_block_aria(self, page_html):
        assert 'role="region"' in page_html
        assert 'aria-label="Power curve formula"' in page_html


# ── TestFooterNavLinks ───────────────────────────────────────


class TestFooterNavLinks:
    """Test footer nav has key links."""

    def test_footer_has_white_papers_link(self, page_html):
        assert "/fueling-methodology/" in page_html

    def test_footer_has_insights_link(self, page_html):
        assert "/insights/" in page_html


# ── TestMainCLI ──────────────────────────────────────────────


class TestMainCLI:
    """Test main() CLI generates output file."""

    def test_main_generates_file(self, tmp_path):
        with patch('sys.argv', ['gen', '--output-dir', str(tmp_path)]):
            main()
        output = tmp_path / "whitepaper-fueling.html"
        assert output.exists()
        content = output.read_text()
        assert "<!DOCTYPE html>" in content
        assert len(content) > 10000
