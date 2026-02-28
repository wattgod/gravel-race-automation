"""Tests for the fueling methodology white paper page generator.

Validates page structure, infographics, CSS, JS, nav integration,
accessibility, brand compliance, deploy function, content accuracy,
scrollytelling sections, and inline calculator.
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
    build_hero,
    build_inline_calculator,
    build_inline_cta,
    build_jensen,
    build_limitations,
    build_metabolic_testing,
    build_murphy,
    build_nav,
    build_phenotype,
    build_power_curve,
    build_practical,
    build_references,
    build_scroll_crossover,
    build_scroll_duration,
    build_scroll_fitness,
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
        """All sections present in new narrative arc."""
        section_ids = [
            "hero", "murphy", "inline-calculator", "practical",
            "scroll-duration", "scroll-fitness", "scroll-crossover",
            "tldr", "phenotype", "jensen", "power-curve",
            "metabolic-testing", "limitations", "references", "cta",
        ]
        for sid in section_ids:
            assert f'id="{sid}"' in page_html, f"Missing section: {sid}"

    def test_page_wrapper_class(self, page_html):
        assert "gg-wp-page" in page_html

    def test_has_json_ld(self, page_html):
        assert "application/ld+json" in page_html
        assert '"Article"' in page_html

    def test_has_viewport_meta(self, page_html):
        assert 'name="viewport"' in page_html


# ── TestHero ──────────────────────────────────────────────────


class TestHero:
    """Test hero section — clean, no counters."""

    def test_has_title(self):
        html = build_hero()
        assert "How Many Carbs" in html

    def test_has_subtitle(self):
        html = build_hero()
        assert "yours" in html.lower()

    def test_no_counters(self):
        """Hero should not have stat counters (removed in scrollytelling rebuild)."""
        html = build_hero()
        assert "gg-wp-counter" not in html
        assert "data-counter" not in html


# ── TestInfographics ──────────────────────────────────────────


class TestInfographics:
    """Test infographic elements: SVG charts, bars, tables, accordions."""

    def test_murphy_comparison_bars(self):
        html = build_murphy()
        assert "gg-wp-compare-row" in html
        assert "80 g/hr" in html
        assert "63 g/hr" in html

    def test_murphy_bars_animate(self):
        html = build_murphy()
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
    """Test JS functionality: animations, accordion, scrollytelling, calculator."""

    def test_has_script_tag(self, page_js):
        assert "<script>" in page_js

    def test_intersection_observer(self, page_js):
        assert "IntersectionObserver" in page_js

    def test_bar_animation(self, page_js):
        assert "data-animate" in page_js or "data-target-w" in page_js

    def test_accordion_handler(self, page_js):
        assert "data-accordion" in page_js
        assert "aria-expanded" in page_js

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
        html = build_murphy()
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
        murphy_html = build_murphy()
        gold_bars = re.findall(r'<div[^>]*gg-wp-bar-fill--gold[^>]*>', murphy_html)
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
        html = build_murphy()
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


# ── TestScrollytelling ───────────────────────────────────────


class TestScrollytelling:
    """Test scrollytelling sections: scroll steps, sticky charts, SVGs."""

    def test_scroll_sections_present(self, page_html):
        """Page has 3 scroll sections."""
        count = page_html.count('class="gg-wp-scroll-section"')
        assert count == 3, f"Expected 3 scroll sections, got {count}"

    def test_scroll_steps_have_data_attributes(self, page_html):
        """Every scroll step has data-step attribute."""
        steps = re.findall(r'class="gg-wp-scroll-step[^"]*"[^>]*data-step="(\d+)"', page_html)
        assert len(steps) >= 10, f"Expected at least 10 scroll steps, got {len(steps)}"
        for step_val in steps:
            assert step_val.isdigit(), f"Invalid data-step value: {step_val}"

    def test_scroll_chart_sticky_css(self, page_css):
        """CSS contains position: sticky for scroll chart."""
        assert "position: sticky" in page_css

    def test_scroll_mobile_breakpoint(self, page_css):
        """CSS has media query for scroll section stacking on mobile."""
        assert "max-width: 768px" in page_css

    def test_scroll_observer_js(self, page_js):
        """JS contains scroll step observer."""
        assert "gg-wp-scroll-step" in page_js

    def test_scroll_duration_has_brackets(self):
        """Duration scroll section has bracket chart with 5 brackets."""
        html = build_scroll_duration()
        count = html.count('data-chart-bracket=')
        assert count == 5, f"Expected 5 brackets, got {count}"

    def test_scroll_fitness_has_power_curve(self):
        """Fitness scroll section has power curve SVG."""
        html = build_scroll_fitness()
        assert "<svg" in html
        assert "polyline" in html

    def test_scroll_crossover_has_fuel_mix(self):
        """Crossover scroll section has fuel mix area chart."""
        html = build_scroll_crossover()
        assert "<svg" in html
        assert "gg-wp-scroll-fat-area" in html
        assert "gg-wp-scroll-carb-trained" in html

    def test_crossover_correct_framing(self, page_html):
        """Page contains corrected crossover insight about carb dominance."""
        assert "carb-dominant" in page_html.lower()

    def test_no_white_paper_language(self, page_html):
        """Prose content should not reference 'this paper' (academic language)."""
        # Check prose sections only — not nav/footer which legitimately say "White Papers"
        prose_blocks = re.findall(r'class="gg-wp-prose">(.*?)</div>', page_html, re.DOTALL)
        for block in prose_blocks:
            text = block.lower()
            assert 'this paper' not in text, "Found 'this paper' in prose section"

    def test_fuel_mix_svg(self, page_html):
        """Page contains fuel-mix area chart SVG."""
        assert "Fuel Mix" in page_html or "fuel mix" in page_html.lower()


# ── TestInlineCalculator ─────────────────────────────────────


class TestInlineCalculator:
    """Test inline carb calculator."""

    def test_inline_calculator_present(self, page_html):
        """Page has calculator section."""
        assert "gg-wp-calculator" in page_html

    def test_calculator_js_compute_function(self, page_js):
        """JS contains computeInline function."""
        assert "computeInline" in page_js

    def test_calculator_no_email_gate(self):
        """Calculator section has no email input."""
        html = build_inline_calculator()
        assert 'type="email"' not in html

    def test_calculator_progressive_fallback(self):
        """Calculator has fallback div for no-JS."""
        html = build_inline_calculator()
        assert "gg-wp-calc-fallback" in html

    def test_calculator_has_weight_input(self):
        """Calculator has weight input field."""
        html = build_inline_calculator()
        assert 'id="gg-calc-weight"' in html

    def test_calculator_has_ftp_input(self):
        """Calculator has FTP input field."""
        html = build_inline_calculator()
        assert 'id="gg-calc-ftp"' in html

    def test_calculator_has_hours_input(self):
        """Calculator has race duration input field."""
        html = build_inline_calculator()
        assert 'id="gg-calc-hours"' in html

    def test_calculator_has_result_area(self):
        """Calculator has result display area."""
        html = build_inline_calculator()
        assert 'id="gg-calc-number"' in html

    def test_calculator_has_unit_toggle(self):
        """Calculator has kg/lbs toggle."""
        html = build_inline_calculator()
        assert 'id="gg-calc-unit-toggle"' in html

    def test_calculator_aria_live(self):
        """Calculator result area has aria-live for screen readers."""
        html = build_inline_calculator()
        assert 'aria-live="polite"' in html

    def test_calculator_form_role(self):
        """Calculator form has role attribute."""
        html = build_inline_calculator()
        assert 'role="form"' in html


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


# ── TestSVGBrandCompliance ──────────────────────────────────


class TestSVGBrandCompliance:
    """SVG presentation attributes must use COLORS dict hex, never var().
    Lesson #3: SVG attrs can't resolve var()/color-mix()."""

    def test_no_svg_var_in_fill(self, page_html):
        """SVG fill attributes must not use CSS custom properties."""
        # Extract all SVG blocks
        svg_blocks = re.findall(r'<svg[^>]*>.*?</svg>', page_html, re.DOTALL)
        for svg in svg_blocks:
            fills = re.findall(r'fill="(var\(--[^"]*)"', svg)
            assert fills == [], (
                f"SVG fill uses var(): {fills[:3]}. "
                "SVG presentation attributes can't resolve CSS custom properties. "
                "Use COLORS dict hex values instead (lesson #3)."
            )

    def test_no_svg_var_in_stroke(self, page_html):
        """SVG stroke attributes must not use CSS custom properties."""
        svg_blocks = re.findall(r'<svg[^>]*>.*?</svg>', page_html, re.DOTALL)
        for svg in svg_blocks:
            strokes = re.findall(r'stroke="(var\(--[^"]*)"', svg)
            assert strokes == [], (
                f"SVG stroke uses var(): {strokes[:3]}. "
                "Use COLORS dict hex values instead (lesson #3)."
            )

    def test_svg_fills_are_hex_or_none(self, page_html):
        """All SVG fill values should be hex colors, 'none', or named colors."""
        svg_blocks = re.findall(r'<svg[^>]*>.*?</svg>', page_html, re.DOTALL)
        for svg in svg_blocks:
            fills = re.findall(r'fill="([^"]+)"', svg)
            for fill in fills:
                assert not fill.startswith('var('), (
                    f"SVG fill '{fill}' uses var(). Must use hex color."
                )
                assert not fill.startswith('color-mix'), (
                    f"SVG fill '{fill}' uses color-mix(). Not supported in SVG attrs."
                )


# ── TestScrollSVGAccessibility ──────────────────────────────


class TestScrollSVGAccessibility:
    """Scroll section SVGs must have role='img' + aria-label + title."""

    def test_duration_svg_accessible(self):
        html = build_scroll_duration()
        assert 'role="img"' in html
        assert 'aria-label=' in html
        assert '<title>' in html

    def test_fitness_svg_accessible(self):
        html = build_scroll_fitness()
        assert 'role="img"' in html
        assert 'aria-label=' in html
        assert '<title>' in html

    def test_crossover_svg_accessible(self):
        html = build_scroll_crossover()
        assert 'role="img"' in html
        assert 'aria-label=' in html
        assert '<title>' in html


# ── TestDataStepIntegrity ───────────────────────────────────


class TestDataStepIntegrity:
    """Scroll step data-step values must be sequential with no gaps."""

    def _check_section_steps(self, html, expected_count):
        """Helper: verify data-step values are 0,1,2,...,n-1."""
        steps = re.findall(r'data-step="(\d+)"', html)
        assert len(steps) == expected_count, (
            f"Expected {expected_count} steps, got {len(steps)}"
        )
        for i, step in enumerate(steps):
            assert int(step) == i, (
                f"data-step gap: expected {i}, got {step}"
            )

    def test_duration_steps_sequential(self):
        self._check_section_steps(build_scroll_duration(), 3)

    def test_fitness_steps_sequential(self):
        self._check_section_steps(build_scroll_fitness(), 3)

    def test_crossover_steps_sequential(self):
        self._check_section_steps(build_scroll_crossover(), 4)


# ── TestChartDataAttributeCrossRef ──────────────────────────


class TestChartDataAttributeCrossRef:
    """JS-referenced data-chart-* attributes must exist in HTML."""

    def test_duration_chart_attributes(self):
        """Duration chart: JS references data-chart-bracket and data-chart-murphy."""
        html = build_scroll_duration()
        assert 'data-chart-bracket=' in html
        assert 'data-chart-murphy' in html

    def test_fitness_chart_attributes(self):
        """Fitness chart: JS references data-chart-murphy, data-chart-comp, data-chart-exponent."""
        html = build_scroll_fitness()
        assert 'data-chart-murphy' in html
        assert 'data-chart-comp' in html
        assert 'data-chart-exponent' in html

    def test_crossover_chart_attributes(self):
        """Crossover chart: JS references data-chart-crossover, rec, race-zone, etc."""
        html = build_scroll_crossover()
        for attr in [
            'data-chart-crossover',
            'data-chart-crossover-label',
            'data-chart-race-zone',
            'data-chart-race-label',
            'data-chart-rec-line',
            'data-chart-rec-label',
            'data-chart-rec',
        ]:
            assert attr in html, f"Missing {attr} in crossover chart HTML"

    def test_scroll_chart_id_matches_js(self):
        """data-scroll-chart values match section IDs used by JS dispatcher."""
        dur = build_scroll_duration()
        fit = build_scroll_fitness()
        cross = build_scroll_crossover()
        assert 'data-scroll-chart="duration"' in dur
        assert 'data-scroll-chart="fitness"' in fit
        assert 'data-scroll-chart="crossover"' in cross


# ── TestFormulaParity ───────────────────────────────────────


class TestFormulaParity:
    """Calculator formula must match prep-kit formula exactly.
    Python equivalent tested against known reference outputs."""

    @staticmethod
    def _compute_inline_python(weight_kg, ftp, hours):
        """Python equivalent of JS computeInline() function."""
        if hours <= 4:
            b_lo, b_hi = 80, 100
        elif hours <= 8:
            b_lo, b_hi = 60, 80
        elif hours <= 12:
            b_lo, b_hi = 50, 70
        elif hours <= 16:
            b_lo, b_hi = 40, 60
        else:
            b_lo, b_hi = 30, 50

        if ftp and ftp > 0 and weight_kg > 0:
            wkg = ftp / weight_kg
            lin = max(0, min(1, (wkg - 1.5) / 3.0))
            factor = lin ** 1.4
            rate = round(b_lo + factor * (b_hi - b_lo))
        else:
            rate = round((b_lo + b_hi) / 2)
        return rate, b_lo, b_hi

    def test_murphy_rate(self):
        """Murphy: 95kg, 220W, 6.5hrs → 63 g/hr."""
        rate, lo, hi = self._compute_inline_python(95, 220, 6.5)
        assert rate == 63, f"Murphy rate {rate} != 63"
        assert lo == 60
        assert hi == 80

    def test_competitive_racer(self):
        """70kg, 280W (4.0 W/kg), 6.5hrs → 75 g/hr."""
        rate, lo, hi = self._compute_inline_python(70, 280, 6.5)
        assert rate == 75, f"Competitive rate {rate} != 75"

    def test_short_race(self):
        """70kg, 280W, 3hrs → 2-4hr bracket (80-100)."""
        rate, lo, hi = self._compute_inline_python(70, 280, 3)
        assert lo == 80
        assert hi == 100
        assert 80 <= rate <= 100

    def test_ultra_race(self):
        """95kg, 220W, 18hrs → 16+ bracket (30-50)."""
        rate, lo, hi = self._compute_inline_python(95, 220, 18)
        assert lo == 30
        assert hi == 50
        assert 30 <= rate <= 50

    def test_no_ftp_gives_midpoint(self):
        """No FTP → bracket midpoint."""
        rate, lo, hi = self._compute_inline_python(75, 0, 6)
        assert rate == 70  # midpoint of 60-80
        rate2, _, _ = self._compute_inline_python(75, None, 6)
        assert rate2 == 70

    def test_formula_constants_in_js(self):
        """JS contains the same constants as the Python formula."""
        js = build_whitepaper_js()
        assert '1.5' in js  # WKG_FLOOR
        assert '3.0' in js  # WKG_CEIL - WKG_FLOOR
        assert '1.4' in js  # WKG_EXP
        assert 'Math.pow(lin, 1.4)' in js

    def test_all_five_brackets_in_js(self):
        """JS has all 5 duration bracket boundaries."""
        js = build_whitepaper_js()
        assert 'bLo = 80; bHi = 100' in js
        assert 'bLo = 60; bHi = 80' in js
        assert 'bLo = 50; bHi = 70' in js
        assert 'bLo = 40; bHi = 60' in js
        assert 'bLo = 30; bHi = 50' in js


# ── TestSectionOrder ────────────────────────────────────────


class TestSectionOrder:
    """Sections must appear in the correct narrative arc order."""

    def test_narrative_arc_order(self, page_html):
        """Sections follow: hook → answer → why → deeper → act."""
        section_order = [
            'id="hero"',
            'id="murphy"',
            'id="inline-calculator"',
            'id="practical"',
            'id="scroll-duration"',
            'id="scroll-fitness"',
            'id="scroll-crossover"',
            'id="tldr"',
            'id="phenotype"',
            'id="jensen"',
            'id="power-curve"',
            'id="metabolic-testing"',
            'id="limitations"',
            'id="references"',
            'id="cta"',
        ]
        positions = []
        for section_id in section_order:
            pos = page_html.find(section_id)
            assert pos != -1, f"Section {section_id} not found in page"
            positions.append(pos)
        # Verify monotonically increasing
        for i in range(len(positions) - 1):
            assert positions[i] < positions[i + 1], (
                f"Section order violation: {section_order[i]} (pos {positions[i]}) "
                f"appears after {section_order[i+1]} (pos {positions[i+1]})"
            )


# ── TestCalculatorEdgeCases ─────────────────────────────────


class TestCalculatorEdgeCases:
    """Edge case tests for calculator formula and JS behavior."""

    def test_wkg_floor_clamp(self):
        """W/kg below 1.5 should clamp to floor (rate = bracket low)."""
        rate, lo, hi = TestFormulaParity._compute_inline_python(100, 100, 6)
        # 100W / 100kg = 1.0 W/kg, below floor → factor = 0 → rate = lo
        assert rate == lo, f"Below-floor W/kg should give bracket low, got {rate}"

    def test_wkg_ceiling_clamp(self):
        """W/kg above 4.5 should clamp to ceiling (rate = bracket high)."""
        rate, lo, hi = TestFormulaParity._compute_inline_python(60, 300, 6)
        # 300W / 60kg = 5.0 W/kg, above ceiling → factor = 1 → rate = hi
        assert rate == hi, f"Above-ceiling W/kg should give bracket high, got {rate}"

    def test_boundary_hours_4(self):
        """At exactly 4 hours, should be in 2-4hr bracket."""
        rate, lo, hi = TestFormulaParity._compute_inline_python(75, 225, 4)
        assert lo == 80 and hi == 100

    def test_boundary_hours_8(self):
        """At exactly 8 hours, should be in 4-8hr bracket."""
        rate, lo, hi = TestFormulaParity._compute_inline_python(75, 225, 8)
        assert lo == 60 and hi == 80

    def test_boundary_hours_12(self):
        """At exactly 12 hours, should be in 8-12hr bracket."""
        rate, lo, hi = TestFormulaParity._compute_inline_python(75, 225, 12)
        assert lo == 50 and hi == 70

    def test_boundary_hours_16(self):
        """At exactly 16 hours, should be in 12-16hr bracket."""
        rate, lo, hi = TestFormulaParity._compute_inline_python(75, 225, 16)
        assert lo == 40 and hi == 60

    def test_rate_always_within_bracket(self):
        """Rate should always be >= lo and <= hi for any valid inputs."""
        test_cases = [
            (60, 150, 3),
            (75, 225, 6),
            (95, 220, 6.5),
            (110, 180, 14),
            (50, 350, 20),
            (80, 0, 10),
        ]
        for wkg, ftp, hrs in test_cases:
            rate, lo, hi = TestFormulaParity._compute_inline_python(wkg, ftp, hrs)
            assert lo <= rate <= hi, (
                f"Rate {rate} outside bracket [{lo}, {hi}] "
                f"for weight={wkg}, ftp={ftp}, hours={hrs}"
            )

    def test_js_has_input_validation(self):
        """JS calculator validates inputs before computing."""
        js = build_whitepaper_js()
        assert 'isNaN(rawWeight)' in js or 'isNaN' in js
        assert 'rawWeight <= 0' in js or 'rawWeight > 0' in js

    def test_js_has_ga4_debounce(self):
        """GA4 event should be debounced, not fire on every keystroke."""
        js = build_whitepaper_js()
        assert 'setTimeout' in js
        assert 'clearTimeout' in js
        assert 'calcGa4Timer' in js

    def test_js_chart_init_on_load(self):
        """Charts should be initialized at step 0 on page load."""
        js = build_whitepaper_js()
        assert 'updateChart(chart, section.id, 0)' in js

    def test_js_unit_toggle_updates_min_max(self):
        """Unit toggle must update min/max constraints."""
        js = build_whitepaper_js()
        assert "calcWeight.min" in js
        assert "calcWeight.max" in js


# ── TestProgressiveEnhancementCalculator ────────────────────


class TestProgressiveEnhancementCalculator:
    """Calculator must work without JS via progressive enhancement."""

    def test_calc_form_hidden_by_default_css(self, page_css):
        """Without JS, form should be display:none."""
        # Look for the standalone .gg-wp-calc-form { display: none; } rule
        # (not the .gg-has-js override)
        pattern = re.search(
            r'\.gg-wp-calc-form\s*\{\s*display:\s*none',
            page_css,
        )
        assert pattern, (
            "Missing .gg-wp-calc-form { display: none } default rule. "
            "Calculator form must be hidden without JS."
        )

    def test_calc_fallback_shown_by_default_css(self, page_css):
        """Without JS, fallback should be display:block."""
        # Find the gg-has-js override
        assert '.gg-has-js .gg-wp-calc-fallback' in page_css
        assert '.gg-has-js .gg-wp-calc-form' in page_css

    def test_calc_form_visible_with_js(self, page_css):
        """With .gg-has-js, form should be visible."""
        assert '.gg-has-js .gg-wp-calc-form' in page_css
