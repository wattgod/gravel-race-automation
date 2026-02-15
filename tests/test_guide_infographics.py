"""Tests for inline SVG/HTML infographic renderers."""
import re
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from guide_infographics import (
    INFOGRAPHIC_RENDERERS,
    _cubic_bezier_path,
    _figure_wrap,
)
import generate_guide


# ── All 16 asset_ids ────────────────────────────────────────

ALL_ASSET_IDS = [
    "ch1-gear-essentials",
    "ch1-rider-grid",
    "ch1-hierarchy-of-speed",
    "ch2-scoring-dimensions",
    "ch2-tier-distribution",
    "ch3-supercompensation",
    "ch3-zone-spectrum",
    "ch3-pmc-chart",
    "ch3-training-phases",
    "ch4-execution-gap",
    "ch4-traffic-light",
    "ch5-fueling-timeline",
    "ch5-bonk-math",
    "ch6-three-acts",
    "ch6-psych-phases",
    "ch7-race-week-countdown",
]


class TestDispatchMap:
    def test_all_16_asset_ids_have_renderers(self):
        for aid in ALL_ASSET_IDS:
            assert aid in INFOGRAPHIC_RENDERERS, f"Missing renderer for {aid}"

    def test_exactly_16_renderers(self):
        assert len(INFOGRAPHIC_RENDERERS) == 16

    def test_all_renderers_are_callable(self):
        for aid, fn in INFOGRAPHIC_RENDERERS.items():
            assert callable(fn), f"Renderer for {aid} is not callable"


# ── Parametrized tests across all 16 renderers ─────────────


@pytest.fixture(params=ALL_ASSET_IDS)
def rendered_html(request):
    """Render each infographic with a minimal block dict."""
    aid = request.param
    block = {
        "type": "image",
        "asset_id": aid,
        "alt": f"Test alt for {aid}",
        "caption": f"Test caption for {aid}",
    }
    renderer = INFOGRAPHIC_RENDERERS[aid]
    return renderer(block)


class TestRendererOutput:
    def test_returns_string(self, rendered_html):
        assert isinstance(rendered_html, str)
        assert len(rendered_html) > 50

    def test_wrapped_in_figure(self, rendered_html):
        assert "<figure" in rendered_html
        assert "</figure>" in rendered_html

    def test_has_figcaption(self, rendered_html):
        assert "<figcaption" in rendered_html
        assert "</figcaption>" in rendered_html

    def test_no_circle_elements(self, rendered_html):
        """Brand rule: no <circle> in SVG (use <rect> only)."""
        assert "<circle" not in rendered_html

    def test_no_border_radius(self, rendered_html):
        """Brand rule: no border-radius in inline styles."""
        assert "border-radius" not in rendered_html

    def test_no_img_tag(self, rendered_html):
        """Infographic renderers must not produce <img> tags."""
        assert "<img " not in rendered_html

    def test_uses_css_custom_properties(self, rendered_html):
        """SVG charts should use var(--gg-color-*) for colors."""
        # Card-based renderers use hex in their HTML classes (styled via CSS),
        # but SVG renderers should use CSS vars
        if "<svg" in rendered_html:
            assert "var(--gg-color-" in rendered_html

    def test_svg_has_viewbox(self, rendered_html):
        """If SVG present, it must have a viewBox for fluid scaling."""
        if "<svg" in rendered_html and 'xmlns="http://www.w3.org/2000/svg"' in rendered_html:
            assert "viewBox" in rendered_html

    def test_has_asset_id_data_attr(self, rendered_html):
        """Figure should have data-asset-id for identification."""
        assert "data-asset-id=" in rendered_html


class TestRendererWithoutCaption:
    def test_no_figcaption_when_no_caption(self):
        block = {"type": "image", "asset_id": "ch1-gear-essentials"}
        html = INFOGRAPHIC_RENDERERS["ch1-gear-essentials"](block)
        assert "<figcaption" not in html


# ── _cubic_bezier_path() unit tests ─────────────────────────


class TestCubicBezierPath:
    def test_empty_points(self):
        assert _cubic_bezier_path([]) == ""

    def test_single_point(self):
        assert _cubic_bezier_path([(10, 20)]) == ""

    def test_two_points_line(self):
        path = _cubic_bezier_path([(0, 0), (100, 100)])
        assert path.startswith("M ")
        assert "L " in path
        assert "100" in path

    def test_three_points_curve(self):
        path = _cubic_bezier_path([(0, 0), (50, 100), (100, 0)])
        assert path.startswith("M ")
        assert "C " in path

    def test_smooth_curve_many_points(self):
        points = [(i * 10, i * i) for i in range(10)]
        path = _cubic_bezier_path(points)
        assert path.startswith("M ")
        assert path.count("C ") == 9  # n-1 segments

    def test_output_is_string(self):
        path = _cubic_bezier_path([(0, 0), (50, 50), (100, 0)])
        assert isinstance(path, str)


# ── _figure_wrap() unit tests ───────────────────────────────


class TestFigureWrap:
    def test_basic_wrap(self):
        html = _figure_wrap("<p>content</p>", "A caption", asset_id="test-id")
        assert '<figure class="gg-infographic"' in html
        assert "<p>content</p>" in html
        assert "A caption" in html
        assert 'data-asset-id="test-id"' in html

    def test_no_caption(self):
        html = _figure_wrap("<p>content</p>", "")
        assert "<figcaption" not in html

    def test_full_width_layout(self):
        html = _figure_wrap("<p>content</p>", "", layout="full-width")
        assert "gg-infographic--full-width" in html

    def test_inline_layout_no_extra_class(self):
        html = _figure_wrap("<p>content</p>", "", layout="inline")
        assert 'class="gg-infographic"' in html
        assert "gg-infographic--" not in html


# ── Specific renderer spot checks ───────────────────────────


class TestSpecificRenderers:
    def test_gear_grid_has_5_cards(self):
        block = {"type": "image", "asset_id": "ch1-gear-essentials", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch1-gear-essentials"](block)
        assert html.count("gg-infographic-card") >= 5

    def test_rider_categories_has_4_cards(self):
        block = {"type": "image", "asset_id": "ch1-rider-grid", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch1-rider-grid"](block)
        assert html.count("gg-infographic-rider-card") == 4

    def test_race_week_has_7_days(self):
        block = {"type": "image", "asset_id": "ch7-race-week-countdown", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch7-race-week-countdown"](block)
        assert html.count("gg-infographic-day-abbr") == 7

    def test_race_week_has_race_day(self):
        block = {"type": "image", "asset_id": "ch7-race-week-countdown", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch7-race-week-countdown"](block)
        assert "gg-infographic-day-card--race" in html

    def test_traffic_light_has_3_signals(self):
        block = {"type": "image", "asset_id": "ch4-traffic-light", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch4-traffic-light"](block)
        assert html.count("gg-infographic-signal-row") == 3

    def test_three_acts_has_3_panels(self):
        block = {"type": "image", "asset_id": "ch6-three-acts", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch6-three-acts"](block)
        assert html.count("gg-infographic-act-panel") == 3

    def test_bonk_math_has_24_gels(self):
        block = {"type": "image", "asset_id": "ch5-bonk-math", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch5-bonk-math"](block)
        assert html.count("gg-infographic-bonk-gel") == 24

    def test_scoring_dimensions_has_14_bars(self):
        block = {"type": "image", "asset_id": "ch2-scoring-dimensions", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch2-scoring-dimensions"](block)
        # Each dimension produces a label + bar + score = 14 sets
        assert html.count("/5") == 14

    def test_tier_distribution_shows_328(self):
        block = {"type": "image", "asset_id": "ch2-tier-distribution", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch2-tier-distribution"](block)
        assert "328" in html

    def test_training_phases_has_legend(self):
        block = {"type": "image", "asset_id": "ch3-training-phases", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch3-training-phases"](block)
        assert "Volume" in html
        assert "Intensity" in html

    def test_pmc_chart_has_3_curves(self):
        block = {"type": "image", "asset_id": "ch3-pmc-chart", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch3-pmc-chart"](block)
        assert "CTL" in html
        assert "ATL" in html
        assert "TSB" in html

    def test_psych_phases_has_5_bands(self):
        block = {"type": "image", "asset_id": "ch6-psych-phases", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch6-psych-phases"](block)
        assert "Honeymoon" in html
        assert "Dark Patch" in html
        assert "Final Push" in html

    def test_execution_gap_has_two_sides(self):
        block = {"type": "image", "asset_id": "ch4-execution-gap", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch4-execution-gap"](block)
        assert "CHASING WATTS" in html
        assert "CONSISTENT EXECUTION" in html

    def test_fueling_timeline_has_markers(self):
        block = {"type": "image", "asset_id": "ch5-fueling-timeline", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch5-fueling-timeline"](block)
        assert "T-3 hrs" in html
        assert "Every 20 min" in html

    def test_supercompensation_has_insight_box(self):
        block = {"type": "image", "asset_id": "ch3-supercompensation", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch3-supercompensation"](block)
        assert "trigger adaptation" in html

    def test_hierarchy_pyramid_has_5_layers(self):
        block = {"type": "image", "asset_id": "ch1-hierarchy-of-speed", "caption": ""}
        html = INFOGRAPHIC_RENDERERS["ch1-hierarchy-of-speed"](block)
        assert "Equipment" in html
        assert "Fitness" in html
        assert "70%" in html


# ══════════════════════════════════════════════════════════════
# Enforcing Tests — these catch the exact shortcuts we shipped
# ══════════════════════════════════════════════════════════════


class TestAccessibility:
    """Every infographic MUST have an accessible name from alt text."""

    @pytest.fixture(params=ALL_ASSET_IDS)
    def rendered_with_alt(self, request):
        aid = request.param
        block = {
            "type": "image",
            "asset_id": aid,
            "alt": f"Descriptive alt text for {aid}",
            "caption": "caption",
        }
        return INFOGRAPHIC_RENDERERS[aid](block)

    def test_figure_has_aria_label(self, rendered_with_alt):
        """Figure must carry aria-label from block alt text."""
        assert 'aria-label="' in rendered_with_alt

    def test_figure_has_role(self, rendered_with_alt):
        """Figure with alt must have role=figure for assistive tech."""
        assert 'role="figure"' in rendered_with_alt

    def test_no_aria_label_without_alt(self):
        """No aria-label when alt is empty."""
        block = {"type": "image", "asset_id": "ch1-gear-essentials"}
        html = INFOGRAPHIC_RENDERERS["ch1-gear-essentials"](block)
        assert "aria-label" not in html


class TestNoOpacity:
    """Brand rule: no opacity attribute on SVG elements."""

    @pytest.fixture(params=ALL_ASSET_IDS)
    def rendered_svg(self, request):
        aid = request.param
        block = {"type": "image", "asset_id": aid, "alt": "test"}
        return INFOGRAPHIC_RENDERERS[aid](block)

    def test_no_opacity_attribute(self, rendered_svg):
        """SVG elements must not use opacity attribute (use color-mix instead)."""
        assert 'opacity="' not in rendered_svg


class TestInfographicCssTokenCompliance:
    """Infographic CSS MUST use var() for all colors, never raw hex."""

    def test_no_raw_hex_in_infographic_css(self):
        """CSS between infographic marker and end must have zero raw hex values."""
        css = generate_guide.build_guide_css()
        marker = "/* ── Inline Infographics ── */"
        assert marker in css, "Infographic CSS section marker missing"
        infographic_css = css[css.index(marker):]
        hex_matches = re.findall(r'#[0-9a-fA-F]{3,8}', infographic_css)
        assert not hex_matches, (
            f"Raw hex in infographic CSS (must use var()): {hex_matches}"
        )

    def test_infographic_css_uses_var_for_colors(self):
        """Infographic CSS must reference var(--gg-color-*) tokens."""
        css = generate_guide.build_guide_css()
        marker = "/* ── Inline Infographics ── */"
        infographic_css = css[css.index(marker):]
        assert "var(--gg-color-" in infographic_css
        assert "var(--gg-font-" in infographic_css


class TestRootDefinesAllVarReferences:
    """Every var(--gg-*) in infographic CSS must be defined in :root."""

    def test_all_var_references_have_definitions(self):
        """Extract all var(--gg-*) from infographic CSS, verify each in :root."""
        css = generate_guide.build_guide_css()
        marker = "/* ── Inline Infographics ── */"
        assert marker in css
        infographic_css = css[css.index(marker):]
        # All var(--gg-...) references
        refs = set(re.findall(r'var\((--gg-[\w-]+)\)', infographic_css))
        assert len(refs) > 0, "No var() references found in infographic CSS"
        # Parse :root definitions (both colors and fonts)
        root_match = re.search(r':root\s*\{([^}]+)\}', css)
        assert root_match, ":root block missing"
        root_block = root_match.group(1)
        defined = set(re.findall(r'(--gg-[\w-]+)\s*:', root_block))
        # Check every reference is defined
        undefined = refs - defined
        assert not undefined, (
            f"Infographic CSS uses var() for undefined properties: {sorted(undefined)}"
        )

    def test_font_vars_defined_in_root(self):
        """Specifically verify font custom properties exist in :root."""
        css = generate_guide.build_guide_css()
        root_match = re.search(r':root\s*\{([^}]+)\}', css)
        assert root_match, ":root block missing"
        root_block = root_match.group(1)
        assert "--gg-font-data" in root_block, "--gg-font-data not in :root"
        assert "--gg-font-editorial" in root_block, "--gg-font-editorial not in :root"


class TestRootTokenParity:
    """:root block must match brand tokens file exactly."""

    @pytest.fixture(scope="class")
    def token_colors(self):
        tokens_path = (
            Path(__file__).parent.parent.parent
            / "gravel-god-brand" / "tokens" / "tokens.css"
        )
        if not tokens_path.exists():
            pytest.skip("Brand tokens file not found")
        text = tokens_path.read_text(encoding="utf-8")
        return dict(re.findall(
            r'(--gg-color-[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})', text
        ))

    @pytest.fixture(scope="class")
    def guide_colors(self):
        css = generate_guide.build_guide_css()
        return dict(re.findall(
            r'(--gg-color-[\w-]+)\s*:\s*(#[0-9a-fA-F]{3,8})', css
        ))

    def test_guide_root_has_color_vars(self, guide_colors):
        """Guide :root block must define color custom properties."""
        assert len(guide_colors) >= 16

    def test_all_guide_colors_match_tokens(self, token_colors, guide_colors):
        """Every color in guide :root must match the brand tokens value."""
        mismatches = []
        for name, guide_val in guide_colors.items():
            if name in token_colors:
                if guide_val.lower() != token_colors[name].lower():
                    mismatches.append(
                        f"{name}: guide={guide_val} tokens={token_colors[name]}"
                    )
        assert not mismatches, (
            f":root colors don't match brand tokens:\n"
            + "\n".join(mismatches)
        )

    def test_no_invented_colors(self, token_colors, guide_colors):
        """Guide must not define color vars that don't exist in brand tokens."""
        invented = [
            name for name in guide_colors
            if name not in token_colors
        ]
        assert not invented, (
            f"Guide :root defines colors not in brand tokens: {invented}"
        )


class TestSvgFontViaCssNotPresentation:
    """SVG text must use style= for font-family, not presentation attribute.

    Presentation attributes (font-family="...") cannot resolve CSS custom
    properties. Only style="font-family:var(...)" works. This test catches
    any renderer that writes font-family as a presentation attribute.
    """

    @pytest.fixture(params=ALL_ASSET_IDS)
    def rendered_svg_text(self, request):
        aid = request.param
        block = {"type": "image", "asset_id": aid, "alt": "test"}
        return INFOGRAPHIC_RENDERERS[aid](block)

    def test_no_font_family_presentation_attribute(self, rendered_svg_text):
        """font-family must not appear as a presentation attribute on <text>."""
        # Match font-family="..." NOT preceded by style="
        # Presentation attr: <text font-family="...">
        # Style attr: <text style="font-family:...">  (this is fine)
        if "<text " not in rendered_svg_text:
            return  # HTML-only renderer, no SVG text
        matches = re.findall(r'<text[^>]* font-family="[^"]*"', rendered_svg_text)
        assert not matches, (
            f"SVG <text> uses font-family as presentation attribute "
            f"(must use style= for var() support): {matches[:3]}"
        )

    def test_svg_text_uses_var_for_fonts(self, rendered_svg_text):
        """SVG text with style font-family must use var(--gg-font-*)."""
        if "<text " not in rendered_svg_text:
            return
        font_styles = re.findall(
            r'style="font-family:([^"]*)"', rendered_svg_text
        )
        for val in font_styles:
            assert val.startswith("var(--gg-font-"), (
                f"SVG font-family style must use var(--gg-font-*), got: {val}"
            )


# ══════════════════════════════════════════════════════════════
# Editorial Framing Tests
# ══════════════════════════════════════════════════════════════


class TestEditorialFraming:
    """Every infographic MUST have a title bar and takeaway box."""

    @pytest.fixture(params=ALL_ASSET_IDS)
    def rendered_editorial(self, request):
        aid = request.param
        block = {"type": "image", "asset_id": aid, "alt": "test", "caption": "cap"}
        return INFOGRAPHIC_RENDERERS[aid](block)

    def test_has_title_div(self, rendered_editorial):
        """Every renderer output must contain .gg-infographic-title."""
        assert "gg-infographic-title" in rendered_editorial

    def test_has_takeaway_div(self, rendered_editorial):
        """Every renderer output must contain .gg-infographic-takeaway."""
        assert "gg-infographic-takeaway" in rendered_editorial

    def test_title_text_non_empty(self, rendered_editorial):
        """Title div must contain non-empty text."""
        match = re.search(
            r'class="gg-infographic-title">([^<]+)<', rendered_editorial
        )
        assert match, "Title div has no text content"
        assert len(match.group(1).strip()) > 3

    def test_takeaway_text_non_empty(self, rendered_editorial):
        """Takeaway div must contain non-empty text."""
        match = re.search(
            r'class="gg-infographic-takeaway">([^<]+)<', rendered_editorial
        )
        assert match, "Takeaway div has no text content"
        assert len(match.group(1).strip()) > 10


# ══════════════════════════════════════════════════════════════
# Animation Attribute Tests
# ══════════════════════════════════════════════════════════════

# SVG renderers that should have data-animate attributes
SVG_ASSET_IDS = [
    "ch1-hierarchy-of-speed",
    "ch2-scoring-dimensions",
    "ch2-tier-distribution",
    "ch3-supercompensation",
    "ch3-zone-spectrum",
    "ch3-pmc-chart",
    "ch3-training-phases",
    "ch4-execution-gap",
    "ch5-fueling-timeline",
    "ch6-psych-phases",
]

# Card renderers that should have .gg-infographic-card or similar
CARD_ASSET_IDS = [
    "ch1-gear-essentials",
    "ch1-rider-grid",
    "ch7-race-week-countdown",
    "ch4-traffic-light",
    "ch6-three-acts",
    "ch5-bonk-math",
]


class TestAnimationAttributes:
    """SVG renderers must have data-animate attrs; card renderers need card classes."""

    @pytest.fixture(params=SVG_ASSET_IDS)
    def rendered_svg_anim(self, request):
        aid = request.param
        block = {"type": "image", "asset_id": aid, "alt": "test"}
        return INFOGRAPHIC_RENDERERS[aid](block)

    def test_svg_has_data_animate(self, rendered_svg_anim):
        """SVG renderers must have at least one data-animate attribute."""
        assert ('data-animate="bar"' in rendered_svg_anim
                or 'data-animate="line"' in rendered_svg_anim), \
            "SVG renderer missing data-animate attribute"

    def test_no_keyframes_in_infographic_css(self):
        """Infographic CSS must use transitions, not @keyframes."""
        css = generate_guide.build_guide_css()
        marker = "/* ── Inline Infographics ── */"
        infographic_css = css[css.index(marker):]
        assert "@keyframes" not in infographic_css, \
            "Infographic CSS must use transitions only, not @keyframes"


class TestTooltipAttributes:
    """Renderers with tooltips must have data-tooltip + tabindex for a11y."""

    @pytest.fixture(params=ALL_ASSET_IDS)
    def rendered_tooltips(self, request):
        aid = request.param
        block = {"type": "image", "asset_id": aid, "alt": "test"}
        return INFOGRAPHIC_RENDERERS[aid](block)

    def test_has_data_tooltip(self, rendered_tooltips):
        """Every renderer should have at least one data-tooltip."""
        assert "data-tooltip=" in rendered_tooltips

    def test_tooltip_values_non_empty(self, rendered_tooltips):
        """All data-tooltip values must be non-empty strings."""
        tooltips = re.findall(r'data-tooltip="([^"]*)"', rendered_tooltips)
        for tip in tooltips:
            assert len(tip.strip()) > 5, f"Empty or too-short tooltip: '{tip}'"

    def test_tooltip_elements_have_tabindex(self, rendered_tooltips):
        """Elements with data-tooltip must have tabindex for keyboard access."""
        # Find all tags with data-tooltip
        elements = re.findall(r'<[^>]*data-tooltip="[^"]*"[^>]*>', rendered_tooltips)
        for el in elements:
            assert 'tabindex="0"' in el, (
                f"Element with data-tooltip missing tabindex: {el[:80]}"
            )


class TestAnimationCssReducedMotion:
    """Animation CSS must be wrapped in prefers-reduced-motion media query."""

    def test_animation_css_in_reduced_motion_block(self):
        """All animation CSS must be inside @media(prefers-reduced-motion:no-preference)."""
        css = generate_guide.build_guide_css()
        marker = "/* ── Inline Infographics ── */"
        infographic_css = css[css.index(marker):]

        # data-animate selectors should ONLY appear inside reduced-motion block
        # Find all data-animate rules outside the reduced-motion block
        # Split on the @media block
        parts = infographic_css.split("@media(prefers-reduced-motion:no-preference)")
        if len(parts) >= 2:
            before_rm = parts[0]
            assert 'data-animate' not in before_rm, \
                "data-animate CSS rules found outside @media(prefers-reduced-motion) block"
            assert 'gg-in-view' not in before_rm, \
                ".gg-in-view CSS rules found outside @media(prefers-reduced-motion) block"

    def test_content_renders_without_gg_in_view(self):
        """All content must be visible without .gg-in-view class (static fallback)."""
        # Card renderers should not require .gg-in-view for content to exist
        for aid in ALL_ASSET_IDS:
            block = {"type": "image", "asset_id": aid, "alt": "test"}
            html = INFOGRAPHIC_RENDERERS[aid](block)
            # Content should be present regardless of gg-in-view
            assert len(html) > 100, f"{aid} output too short"
            assert "gg-in-view" not in html, \
                f"{aid} renderer should not hardcode gg-in-view (JS adds it)"

    def test_no_js_fallback_guard(self):
        """Animation initial states (hidden cards) must require .gg-has-js class.

        Without JS, cards should render in their default position (no transform).
        The .gg-has-js class is added by JS, so without it, no hiding occurs.
        """
        css = generate_guide.build_guide_css()
        # Find the reduced-motion block
        rm_start = css.index("@media(prefers-reduced-motion:no-preference)")
        rm_block = css[rm_start:]

        # All initial-hidden selectors must be guarded by .gg-has-js
        hidden_selectors = [
            ".gg-infographic-card{transform:translateY",
            ".gg-infographic-rider-card{transform:translateY",
            ".gg-infographic-day-card{transform:translateY",
            ".gg-infographic-signal-row{transform:translateY",
            ".gg-infographic-act-panel{transform:translateY",
            ".gg-infographic-bonk-gel{transform:scale(0)",
        ]
        for sel in hidden_selectors:
            assert f".gg-has-js {sel}" in rm_block or f".gg-has-js{sel}" in rm_block, \
                f"Missing .gg-has-js guard on: {sel}"

    def test_js_adds_has_js_class(self):
        """JS must add .gg-has-js to <html> for animation CSS to activate."""
        js = generate_guide.build_guide_js()
        assert 'classList.add("gg-has-js")' in js, \
            "JS must add gg-has-js class to documentElement"


class TestFigureWrapEditorial:
    """Test _figure_wrap title and takeaway parameters."""

    def test_title_rendered(self):
        html = _figure_wrap("<p>inner</p>", "cap", title="My Title")
        assert "gg-infographic-title" in html
        assert "My Title" in html

    def test_takeaway_rendered(self):
        html = _figure_wrap("<p>inner</p>", "cap", takeaway="Key insight here")
        assert "gg-infographic-takeaway" in html
        assert "Key insight here" in html

    def test_no_title_no_div(self):
        html = _figure_wrap("<p>inner</p>", "cap")
        assert "gg-infographic-title" not in html

    def test_no_takeaway_no_div(self):
        html = _figure_wrap("<p>inner</p>", "cap")
        assert "gg-infographic-takeaway" not in html

    def test_title_before_inner(self):
        html = _figure_wrap("<p>inner</p>", "cap", title="My Title")
        title_pos = html.index("gg-infographic-title")
        inner_pos = html.index("<p>inner</p>")
        assert title_pos < inner_pos

    def test_takeaway_after_inner(self):
        html = _figure_wrap("<p>inner</p>", "cap", takeaway="Insight")
        inner_pos = html.index("<p>inner</p>")
        takeaway_pos = html.index("gg-infographic-takeaway")
        assert takeaway_pos > inner_pos

    def test_title_html_escaped(self):
        html = _figure_wrap("<p>x</p>", "", title='Test <script>"alert"</script>')
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
