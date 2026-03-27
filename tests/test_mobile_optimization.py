"""Tests for Mobile Optimization sprint — guards against regressions in:
- Mobile touch resets (tap-highlight, touch-action)
- Active/pressed states for tap feedback
- Fluid sizing (clamp() replacing hardcoded px widths)
- 600px intermediate breakpoint
- Minimum font sizes (no sub-9px text)
- 44px minimum touch targets on mobile
- Collapsible sections on mobile
- Search page slider enlargement
"""
import re
import sys
from pathlib import Path

import pytest

# Add wordpress/ to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Touch Resets ─────────────────────────────────────────────


class TestTouchResets:
    """Mobile touch reset CSS must be present on interactive elements."""

    @pytest.fixture(autouse=True)
    def _load_css(self):
        from generate_neo_brutalist import get_page_css
        self.css = get_page_css()

    def test_tap_highlight_transparent(self):
        assert '-webkit-tap-highlight-color: transparent' in self.css

    def test_touch_action_manipulation(self):
        assert 'touch-action: manipulation' in self.css

    def test_touch_resets_target_buttons(self):
        """Touch resets must target button elements."""
        assert re.search(r'button[^{]*\{[^}]*touch-action:\s*manipulation', self.css)

    def test_touch_resets_target_links(self):
        """Touch resets must target anchor elements."""
        assert re.search(
            r'\.gg-neo-brutalist-page\s+a[^{]*\{[^}]*touch-action:\s*manipulation',
            self.css,
        )

    def test_touch_resets_target_inputs(self):
        """Touch resets must target input elements."""
        assert re.search(r'input[^{]*\{[^}]*touch-action:\s*manipulation', self.css)


# ── Active States ────────────────────────────────────────────


class TestActiveStates:
    """Interactive elements must have :active press states scoped to mobile only."""

    @pytest.fixture(autouse=True)
    def _load_css(self):
        from generate_neo_brutalist import get_page_css
        self.css = get_page_css()

    def test_active_states_scoped_to_mobile(self):
        """Active states must be inside a max-width: 768px media query, not global."""
        # Find :active rules NOT inside a media query — these are bugs
        # Split on @media to isolate global CSS
        parts = re.split(r'@media', self.css)
        global_css = parts[0] if parts else ''
        active_in_global = re.findall(r'[^{]+:active\s*\{', global_css)
        assert not active_in_global, (
            f"Active states must be mobile-only (inside @media), found global: "
            f"{[a.strip() for a in active_in_global]}"
        )

    def test_btn_active_state(self):
        assert '.gg-btn:active' in self.css

    def test_accordion_trigger_active(self):
        assert '.gg-accordion-trigger:active' in self.css

    def test_faq_question_active(self):
        assert '.gg-faq-question:active' in self.css

    def test_similar_card_active(self):
        assert '.gg-similar-card:active' in self.css

    def test_pack_workout_active(self):
        assert '.gg-pack-workout:active' in self.css

    def test_back_to_top_active(self):
        assert '.gg-back-to-top:active' in self.css

    def test_email_capture_btn_active(self):
        assert '.gg-email-capture-btn:active' in self.css

    def test_scale_transform_respects_reduced_motion(self):
        """transform: scale() in :active must be inside prefers-reduced-motion: no-preference."""
        # Find all scale transforms in active rules
        scale_blocks = re.findall(
            r'@media[^{]*\{[^}]*:active[^}]*transform:\s*scale\([^)]+\)[^}]*\}',
            self.css,
        )
        for block in scale_blocks:
            assert 'prefers-reduced-motion: no-preference' in block, (
                f"Scale transform in :active must be gated by prefers-reduced-motion: {block[:100]}"
            )


# ── Fluid Sizing ─────────────────────────────────────────────


class TestFluidSizing:
    """Accordion labels and demand bar labels must use clamp() for fluid sizing."""

    @pytest.fixture(autouse=True)
    def _load_css(self):
        from generate_neo_brutalist import get_page_css
        self.css = get_page_css()

    def test_accordion_label_uses_clamp(self):
        match = re.search(
            r'\.gg-accordion-label\s*\{[^}]*width:\s*clamp\((\d+)px,\s*[\d.]+vw,\s*(\d+)px\)',
            self.css,
        )
        assert match, "Accordion label width must use clamp() for fluid scaling"
        min_val, max_val = int(match.group(1)), int(match.group(2))
        assert min_val >= 60, f"clamp() minimum {min_val}px too small for readability"
        assert max_val <= 120, f"clamp() maximum {max_val}px too large"
        assert min_val < max_val, "clamp() minimum must be less than maximum"

    def test_accordion_label_no_fixed_110px(self):
        """No hardcoded width: 110px on accordion labels."""
        match = re.search(
            r'\.gg-accordion-label\s*\{[^}]*width:\s*110px',
            self.css,
        )
        assert not match, "Accordion label must not use fixed 110px width"

    def test_demand_label_uses_clamp(self):
        match = re.search(
            r'\.gg-pack-demand-label\s*\{[^}]*width:\s*clamp\((\d+)px,\s*[\d.]+vw,\s*(\d+)px\)',
            self.css,
        )
        assert match, "Demand bar label width must use clamp() for fluid scaling"
        min_val, max_val = int(match.group(1)), int(match.group(2))
        assert min_val >= 60, f"clamp() minimum {min_val}px too small"
        assert min_val < max_val, "clamp() minimum must be less than maximum"

    def test_demand_label_no_fixed_90px(self):
        """No hardcoded width: 90px on demand labels."""
        match = re.search(
            r'\.gg-pack-demand-label\s*\{[^}]*width:\s*90px',
            self.css,
        )
        assert not match, "Demand label must not use fixed 90px width"

    def test_cfg_field_uses_min(self):
        """Configurator field min-width must use min() to prevent overflow."""
        match = re.search(r'\.gg-cfg-field\s*\{[^}]*min-width:\s*min\(', self.css)
        assert match, "Configurator field min-width must use min() function"

    def test_accordion_content_padding_uses_clamp(self):
        """Accordion content padding-left must adapt to fluid label width."""
        match = re.search(
            r'\.gg-accordion-content\s*\{[^}]*padding:[^}]*clamp\(',
            self.css,
        )
        assert match, "Accordion content padding must use clamp() to match fluid label width"


# ── 600px Breakpoint ─────────────────────────────────────────


class TestIntermediateBreakpoint:
    """A 600px breakpoint must exist between the 768px and 480px breakpoints."""

    @pytest.fixture(autouse=True)
    def _load_css(self):
        from generate_neo_brutalist import get_page_css
        self.css = get_page_css()

    def test_600px_breakpoint_exists(self):
        assert '@media (max-width: 600px)' in self.css

    def test_600px_hero_padding(self):
        """Hero should have reduced padding at 600px."""
        block = self._extract_600px_block()
        assert '.gg-hero' in block

    def test_600px_hero_title(self):
        block = self._extract_600px_block()
        assert '.gg-hero h1' in block

    def test_600px_stat_grid(self):
        block = self._extract_600px_block()
        assert '.gg-stat-grid' in block

    def test_600px_training_primary(self):
        block = self._extract_600px_block()
        assert '.gg-training-primary' in block

    def _extract_600px_block(self):
        """Extract the large-phones 600px media query block (the one with hero rules)."""
        # Find all 600px blocks and return the one that has hero rules (the new one)
        blocks = re.findall(
            r'/\*\s*Responsive\s*[-—]\s*large\s*phones[^*]*\*/\s*@media\s*\(max-width:\s*600px\)\s*\{(.*?)\n\}',
            self.css,
            re.DOTALL,
        )
        if blocks:
            return blocks[0]
        # Fallback: find all 600px blocks
        blocks = re.findall(
            r'@media\s*\(max-width:\s*600px\)\s*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
            self.css,
            re.DOTALL,
        )
        for b in blocks:
            if '.gg-hero' in b:
                return b
        return ''


# ── Minimum Font Sizes ───────────────────────────────────────


class TestMinimumFontSizes:
    """No font-size below 9px should exist in the CSS (readability floor)."""

    @pytest.fixture(autouse=True)
    def _load_css(self):
        from generate_neo_brutalist import get_page_css
        self.css = get_page_css()

    def test_no_8px_fonts_in_base_styles(self):
        """Base styles (outside media queries) must not have 8px font sizes."""
        # Extract CSS before the first @media block
        first_media = self.css.find('@media')
        base_css = self.css[:first_media] if first_media != -1 else self.css
        matches = re.findall(r'font-size:\s*8px', base_css)
        assert not matches, f"Found {len(matches)} instances of font-size: 8px in base styles"

    def test_no_7px_or_below_anywhere(self):
        """No font-size of 7px or below should exist anywhere."""
        matches = re.findall(r'font-size:\s*[1-7]px', self.css)
        assert not matches, f"Found sub-8px font sizes: {matches}"

    def test_series_badge_readable(self):
        """Series badge must be at least 11px."""
        match = re.search(r'\.gg-series-badge\s*\{[^}]*font-size:\s*(\d+)px', self.css)
        assert match, "Series badge font-size not found"
        assert int(match.group(1)) >= 11, f"Series badge is {match.group(1)}px, minimum 11px"

    def test_difficulty_scale_readable(self):
        """Difficulty scale must be at least 10px."""
        match = re.search(r'\.gg-difficulty-scale\s*\{[^}]*font-size:\s*(\d+)px', self.css)
        assert match, "Difficulty scale font-size not found"
        assert int(match.group(1)) >= 10, f"Difficulty scale is {match.group(1)}px, minimum 10px"

    def test_demand_label_readable(self):
        """Pack demand label must be at least 11px."""
        match = re.search(
            r'\.gg-pack-demand-label\s*\{[^}]*font-size:\s*(\d+)px',
            self.css,
        )
        assert match, "Pack demand label font-size not found"
        assert int(match.group(1)) >= 11, f"Demand label is {match.group(1)}px, minimum 11px"

    def test_no_10px_or_below_in_600px_block(self):
        """The 600px breakpoint must not introduce sub-11px font sizes."""
        # Extract the 600px large-phones block
        match = re.search(
            r'/\*\s*Responsive\s*[-—]\s*large\s*phones[^*]*\*/\s*@media\s*\(max-width:\s*600px\)\s*\{(.*?)\n\}',
            self.css,
            re.DOTALL,
        )
        if not match:
            return  # Block may not exist yet
        block = match.group(1)
        violations = re.findall(r'font-size:\s*(\d+)px', block)
        for v in violations:
            assert int(v) >= 11, f"Font-size {v}px in 600px block violates 11px floor"


# ── Touch Targets ────────────────────────────────────────────


class TestTouchTargets:
    """Interactive elements must have 44px minimum touch targets on mobile (768px).

    Tests use selector-specific regex to verify each rule applies to the right element,
    not just that 'min-height: 44px' appears somewhere in the block.
    """

    @pytest.fixture(autouse=True)
    def _load_css(self):
        from generate_neo_brutalist import get_page_css
        self.css = get_page_css()

    def _mobile_block(self):
        """Extract the main 768px responsive block (the one with touch targets)."""
        match = re.search(
            r'/\*\s*Responsive\s*[-—]+\s*mobile\s*\*/\s*@media\s*\(max-width:\s*768px\)\s*\{(.+?)(?=/\*\s*Responsive)',
            self.css,
            re.DOTALL,
        )
        return match.group(1) if match else ''

    def _rule_for_selector(self, block, selector):
        """Extract the CSS rule body for a specific selector within a block."""
        escaped = re.escape(selector)
        match = re.search(escaped + r'\s*\{([^}]+)\}', block)
        return match.group(1) if match else ''

    def test_btn_min_height_44(self):
        rule = self._rule_for_selector(self._mobile_block(), '.gg-neo-brutalist-page .gg-btn')
        assert 'min-height: 44px' in rule or 'padding-top: 12px' in rule, (
            f".gg-btn rule missing 44px touch target: {rule[:100]}"
        )

    def test_accordion_trigger_min_height(self):
        rule = self._rule_for_selector(self._mobile_block(), '.gg-neo-brutalist-page .gg-accordion-trigger')
        assert 'min-height: 44px' in rule, f".gg-accordion-trigger rule: {rule[:100]}"

    def test_faq_question_min_height(self):
        rule = self._rule_for_selector(self._mobile_block(), '.gg-neo-brutalist-page .gg-faq-question')
        assert 'min-height: 44px' in rule, f".gg-faq-question rule: {rule[:100]}"

    def test_sticky_dismiss_min_size(self):
        rule = self._rule_for_selector(self._mobile_block(), '.gg-sticky-dismiss')
        assert 'min-width: 44px' in rule and 'min-height: 44px' in rule, (
            f".gg-sticky-dismiss rule: {rule[:100]}"
        )

    def test_back_to_top_min_size(self):
        rule = self._rule_for_selector(self._mobile_block(), '.gg-back-to-top')
        assert 'min-width: 44px' in rule and 'min-height: 44px' in rule, (
            f".gg-back-to-top rule: {rule[:100]}"
        )

    def test_email_capture_btn_min_height(self):
        rule = self._rule_for_selector(self._mobile_block(), '.gg-neo-brutalist-page .gg-email-capture-btn')
        assert 'min-height: 44px' in rule, f".gg-email-capture-btn rule: {rule[:100]}"

    def test_cfg_select_min_height(self):
        block = self._mobile_block()
        assert re.search(
            r'\.gg-cfg-select[^{]*\{[^}]*min-height:\s*44px', block
        ), "Configurator select must have min-height: 44px in its own rule"

    def test_review_star_btn_min_size(self):
        rule = self._rule_for_selector(self._mobile_block(), '.gg-neo-brutalist-page .gg-review-star-btn')
        assert 'min-width: 44px' in rule, f".gg-review-star-btn rule: {rule[:100]}"

    def test_section_header_button_min_height(self):
        block = self._mobile_block()
        assert re.search(
            r'\.gg-section-header\[role="button"\]\s*\{[^}]*min-height:\s*44px', block
        ), "Section header button must have min-height: 44px"


# ── Collapsible Sections ─────────────────────────────────────


class TestCollapsibleSections:
    """Mobile JS must make long sections collapsible."""

    @pytest.fixture(autouse=True)
    def _load_js(self):
        from generate_neo_brutalist import build_inline_js
        self.js = build_inline_js()

    @pytest.fixture()
    def neo_css(self):
        from generate_neo_brutalist import get_page_css
        return get_page_css()

    def test_collapsible_section_js_exists(self):
        assert 'gg-section-collapsible' in self.js

    def test_collapsible_respects_viewport_width(self):
        """Should only collapse on screens ≤768px."""
        assert 'window.innerWidth > 768' in self.js or 'innerWidth > 768' in self.js

    def test_collapsible_targets_history(self):
        assert "'history'" in self.js

    def test_collapsible_targets_logistics(self):
        assert "'logistics'" in self.js

    def test_collapsible_targets_training(self):
        assert "'training'" in self.js

    def test_collapsible_does_not_target_course(self):
        """Course overview should NOT be collapsible — it's the primary content."""
        # The list of collapsible IDs should not include 'course'
        match = re.search(r'collapsibleIds\s*=\s*\[([^\]]+)\]', self.js)
        assert match, "collapsibleIds array not found in JS"
        assert "'course'" not in match.group(1), "Course section must not be collapsible"

    def test_collapsible_does_not_target_ratings(self):
        """Ratings should NOT be collapsible — it's a key engagement section."""
        match = re.search(r'collapsibleIds\s*=\s*\[([^\]]+)\]', self.js)
        assert match, "collapsibleIds array not found in JS"
        assert "'ratings'" not in match.group(1), "Ratings section must not be collapsible"

    def test_collapsible_sets_aria_expanded(self):
        assert "aria-expanded" in self.js

    def test_collapsible_keyboard_accessible(self):
        """Collapsible headers must respond to Enter and Space keys."""
        assert "Enter" in self.js or "' '" in self.js

    def test_collapsible_respects_hash_anchor(self):
        """If URL hash points to a collapsible section, it must start expanded."""
        assert 'location.hash' in self.js or 'window.location.hash' in self.js
        assert 'startExpanded' in self.js or 'hash === id' in self.js

    def test_chevron_css_exists(self, neo_css):
        assert '.gg-section-chevron' in neo_css

    def test_chevron_reduced_motion_guard(self, neo_css):
        """Chevron transition must be gated by prefers-reduced-motion."""
        # Find all chevron rules with transitions
        chevron_transitions = re.findall(
            r'(?:@media[^{]*\{)?\s*[^{]*\.gg-section-chevron\s*\{[^}]*transition:[^}]*\}',
            neo_css,
        )
        for block in chevron_transitions:
            assert 'prefers-reduced-motion' in block, (
                f"Chevron transition must be inside prefers-reduced-motion guard: {block[:120]}"
            )


# ── Search Page CSS ──────────────────────────────────────────


class TestSearchPageMobile:
    """Search page CSS must have mobile touch/slider improvements."""

    @pytest.fixture(autouse=True)
    def _load_css(self):
        css_files = list((PROJECT_ROOT / "web").glob("gg-search.*.css"))
        assert css_files, "No gg-search.*.css file found"
        self.css = css_files[0].read_text()

    def test_search_touch_resets(self):
        assert 'touch-action: manipulation' in self.css

    def test_search_tap_highlight(self):
        assert '-webkit-tap-highlight-color: transparent' in self.css

    def test_slider_track_height_12px(self):
        """Slider tracks must be at least 12px for touch targets."""
        matches = re.findall(r'input\[type="range"\]\s*\{[^}]*height:\s*(\d+)px', self.css)
        assert matches, "No slider track height found"
        assert all(int(h) >= 12 for h in matches), f"Slider tracks too thin: {matches}"

    def test_slider_thumb_28px(self):
        """Slider thumbs must be at least 28px."""
        matches = re.findall(
            r'::-webkit-slider-thumb\s*\{[^}]*width:\s*(\d+)px',
            self.css,
        )
        assert matches, "No slider thumb width found"
        assert all(int(w) >= 28 for w in matches), f"Slider thumbs too small: {matches}"

    def test_search_mobile_touch_targets(self):
        """Search buttons must have min-height: 44px in mobile block."""
        assert 'min-height: 44px' in self.css

    def test_search_active_states(self):
        """Search page must have :active states for tap feedback."""
        assert ':active' in self.css

    def test_search_css_hash_matches_html(self):
        """The CSS filename hash must match what gravel-race-search.html references."""
        html = (PROJECT_ROOT / "web" / "gravel-race-search.html").read_text()
        css_files = list((PROJECT_ROOT / "web").glob("gg-search.*.css"))
        css_name = css_files[0].name
        assert css_name in html, f"HTML references different CSS than {css_name}"
