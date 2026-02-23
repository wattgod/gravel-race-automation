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
    get_ga4_head_snippet,
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


class TestGa4HeadSnippet:
    """Tests for get_ga4_head_snippet() — centralized GA4 consent + loading."""

    def test_returns_string(self):
        snippet = get_ga4_head_snippet()
        assert isinstance(snippet, str)
        assert len(snippet) > 100

    def test_consent_defaults_before_ga4(self):
        snippet = get_ga4_head_snippet()
        consent_pos = snippet.index("consent")
        ga4_pos = snippet.index("googletagmanager.com")
        assert consent_pos < ga4_pos, "Consent defaults must fire before GA4 loads"

    def test_has_all_consent_types(self):
        snippet = get_ga4_head_snippet()
        for ctype in ("analytics_storage", "ad_storage", "ad_user_data", "ad_personalization"):
            assert ctype in snippet, f"Missing consent type: {ctype}"

    def test_ad_types_denied_by_default(self):
        snippet = get_ga4_head_snippet()
        assert "'ad_storage':'denied'" in snippet
        assert "'ad_user_data':'denied'" in snippet
        assert "'ad_personalization':'denied'" in snippet

    def test_analytics_conditional_on_cookie(self):
        snippet = get_ga4_head_snippet()
        assert "gg_consent=accepted" in snippet
        assert "?'granted':'denied'" in snippet

    def test_uses_regex_not_indexof(self):
        snippet = get_ga4_head_snippet()
        assert "indexOf" not in snippet, "Must use regex, not indexOf"
        assert "/(^|; )gg_consent=accepted/.test" in snippet

    def test_has_wait_for_update(self):
        snippet = get_ga4_head_snippet()
        assert "wait_for_update" in snippet

    def test_has_ga4_measurement_id(self):
        snippet = get_ga4_head_snippet()
        assert GA_MEASUREMENT_ID in snippet

    def test_ga4_async_loading(self):
        snippet = get_ga4_head_snippet()
        assert f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_MEASUREMENT_ID}">' in snippet

    def test_ga4_config_call(self):
        snippet = get_ga4_head_snippet()
        assert f"gtag('config','{GA_MEASUREMENT_ID}')" in snippet

    def test_three_script_tags(self):
        snippet = get_ga4_head_snippet()
        assert snippet.count("<script") == 3
        assert snippet.count("</script>") == 3

    def test_no_generators_have_inline_ga4_block(self):
        """Ensure no generator has a copy-pasted GA4 block — all must use get_ga4_head_snippet()."""
        wp_dir = Path(__file__).parent.parent / "wordpress"
        violations = []
        for f in sorted(wp_dir.glob("generate_*.py")):
            content = f.read_text()
            if "googletagmanager.com/gtag/js" in content and f.name != "brand_tokens.py":
                violations.append(f.name)
        assert not violations, (
            f"Generators with inline GA4 block (must use get_ga4_head_snippet()): {violations}"
        )

    def test_no_generators_define_ga_measurement_id(self):
        """No generator should define GA_MEASUREMENT_ID locally — canonical definition is in brand_tokens."""
        wp_dir = Path(__file__).parent.parent / "wordpress"
        violations = []
        for f in sorted(wp_dir.glob("generate_*.py")):
            if f.name == "brand_tokens.py":
                continue
            for line in f.read_text().split("\n"):
                stripped = line.strip()
                if (stripped.startswith("GA_MEASUREMENT_ID") or
                    stripped.startswith("GA4_MEASUREMENT_ID")):
                    if "=" in stripped and "import" not in stripped:
                        violations.append(f"{f.name}: {stripped}")
        assert not violations, (
            f"Generators defining GA_MEASUREMENT_ID locally: {violations}"
        )
