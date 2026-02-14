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
