"""Tests for wordpress/brand_tokens.py — CSS generation and color consistency."""

import re
import sys
from pathlib import Path

# Ensure wordpress/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from brand_tokens import (
    COLORS,
    FONT_FILES,
    GA_MEASUREMENT_ID,
    SITE_BASE_URL,
    get_font_face_css,
    get_preload_hints,
    get_tokens_css,
)


class TestTokensCSS:
    def test_returns_root_block(self):
        css = get_tokens_css()
        assert css.startswith(":root {")
        assert css.count(":root {") == 2  # primary + composite

    def test_contains_all_color_vars(self):
        css = get_tokens_css()
        for key, hex_val in COLORS.items():
            var_name = f"--gg-color-{key.replace('_', '-')}"
            assert var_name in css, f"Missing CSS var {var_name} for COLORS['{key}']"

    def test_color_values_match(self):
        """COLORS dict hex values must match the CSS custom properties."""
        css = get_tokens_css()
        for key, hex_val in COLORS.items():
            var_name = f"--gg-color-{key.replace('_', '-')}"
            # Find the value in CSS
            pattern = rf"{re.escape(var_name)}:\s*(#[0-9a-fA-F]{{3,8}})"
            match = re.search(pattern, css)
            assert match, f"Could not find {var_name} in CSS"
            assert match.group(1).lower() == hex_val.lower(), (
                f"{var_name}: CSS has {match.group(1)}, COLORS has {hex_val}"
            )

    def test_contains_font_tokens(self):
        css = get_tokens_css()
        assert "--gg-font-data:" in css
        assert "--gg-font-editorial:" in css
        assert "Sometype Mono" in css
        assert "Source Serif 4" in css

    def test_contains_spacing_tokens(self):
        css = get_tokens_css()
        assert "--gg-spacing-xs:" in css
        assert "--gg-spacing-xl:" in css

    def test_border_radius_is_zero(self):
        """Neo-brutalist: no rounded corners."""
        css = get_tokens_css()
        assert "--gg-border-radius: 0;" in css

    def test_composite_tokens(self):
        css = get_tokens_css()
        assert "--gg-border-standard:" in css
        assert "--gg-border-gold:" in css
        assert "--gg-transition-hover:" in css


class TestFontFaceCSS:
    def test_default_prefix(self):
        css = get_font_face_css()
        assert "/race/assets/fonts/" in css

    def test_custom_prefix(self):
        css = get_font_face_css("/custom/path")
        assert "/custom/path/" in css
        assert "/race/assets/fonts/" not in css

    def test_strips_trailing_slash(self):
        css = get_font_face_css("/fonts/")
        assert "/fonts//" not in css
        assert "/fonts/SometypeMono" in css

    def test_eight_font_faces(self):
        css = get_font_face_css()
        assert css.count("@font-face") == 8

    def test_font_display_swap(self):
        css = get_font_face_css()
        assert css.count("font-display: swap") == 8

    def test_all_font_files_referenced(self):
        css = get_font_face_css()
        for f in FONT_FILES:
            assert f in css, f"Font file {f} not referenced in @font-face CSS"


class TestPreloadHints:
    def test_preloads_latin_subsets(self):
        html = get_preload_hints()
        assert "SometypeMono-normal-latin.woff2" in html
        assert "SourceSerif4-normal-latin.woff2" in html

    def test_does_not_preload_extended(self):
        html = get_preload_hints()
        assert "latin-ext" not in html

    def test_crossorigin_attribute(self):
        html = get_preload_hints()
        assert html.count('crossorigin') == 2

    def test_custom_prefix(self):
        html = get_preload_hints("/cdn/fonts")
        assert "/cdn/fonts/" in html


class TestColorDict:
    def test_required_colors_present(self):
        required = [
            "dark_brown", "primary_brown", "secondary_brown", "tan",
            "warm_paper", "gold", "teal", "near_black", "white",
            "tier_1", "tier_2", "tier_3", "tier_4",
        ]
        for key in required:
            assert key in COLORS, f"Missing required color: {key}"

    def test_all_hex_format(self):
        for key, val in COLORS.items():
            assert re.match(r"^#[0-9a-fA-F]{6}$", val), (
                f"COLORS['{key}'] = '{val}' is not valid 6-digit hex"
            )

    def test_tier_colors_distinct(self):
        tier_vals = [COLORS[f"tier_{i}"] for i in range(1, 5)]
        assert len(set(v.lower() for v in tier_vals)) == 4, "Tier colors must be distinct"


class TestConstants:
    def test_ga_measurement_id_format(self):
        assert GA_MEASUREMENT_ID.startswith("G-")
        assert len(GA_MEASUREMENT_ID) > 5

    def test_site_base_url(self):
        assert SITE_BASE_URL.startswith("https://")
        assert not SITE_BASE_URL.endswith("/")

    def test_font_files_count(self):
        assert len(FONT_FILES) == 8

    def test_font_files_woff2(self):
        for f in FONT_FILES:
            assert f.endswith(".woff2"), f"{f} is not woff2"
