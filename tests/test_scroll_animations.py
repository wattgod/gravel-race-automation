"""Tests for the shared scroll animation module."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from scroll_animations import get_scroll_animation_css, get_scroll_animation_js, SUPPORTED_TYPES


class TestScrollAnimationCSS:
    def test_fade_stagger_has_reduced_motion_guard(self):
        css = get_scroll_animation_css(["fade-stagger"])
        assert "prefers-reduced-motion" in css

    def test_fade_stagger_has_gg_has_js_guard(self):
        css = get_scroll_animation_css(["fade-stagger"])
        assert ".gg-has-js" in css

    def test_fade_stagger_has_gg_in_view_trigger(self):
        css = get_scroll_animation_css(["fade-stagger"])
        assert ".gg-in-view" in css

    def test_fade_stagger_uses_translateY(self):
        css = get_scroll_animation_css(["fade-stagger"])
        assert "translateY" in css

    def test_fade_stagger_has_opacity(self):
        """Scroll-triggered fade-stagger uses opacity for perceptible reveal."""
        css = get_scroll_animation_css(["fade-stagger"])
        assert "opacity: 0" in css
        assert "opacity: 1" in css

    def test_fade_stagger_no_keyframes(self):
        """Scroll animations use transitions, never @keyframes."""
        css = get_scroll_animation_css(["fade-stagger"])
        assert "@keyframes" not in css

    def test_fade_stagger_has_stagger_delays(self):
        css = get_scroll_animation_css(["fade-stagger"])
        assert "nth-child(2)" in css
        assert "transition-delay" in css

    def test_bar_type(self):
        css = get_scroll_animation_css(["bar"])
        assert "gg-animated-bar__fill" in css
        assert "var(--w)" in css

    def test_multiple_types(self):
        css = get_scroll_animation_css(["fade-stagger", "bar"])
        assert "translateY" in css
        assert "gg-animated-bar__fill" in css

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="sparkle"):
            get_scroll_animation_css(["sparkle"])

    def test_supported_types_constant(self):
        assert "fade-stagger" in SUPPORTED_TYPES
        assert "bar" in SUPPORTED_TYPES


class TestScrollAnimationJS:
    def test_has_intersection_observer(self):
        js = get_scroll_animation_js()
        assert "IntersectionObserver" in js

    def test_has_unobserve(self):
        js = get_scroll_animation_js()
        assert "unobserve" in js

    def test_has_reduced_motion_guard(self):
        js = get_scroll_animation_js()
        assert "prefers-reduced-motion" in js

    def test_adds_gg_has_js(self):
        js = get_scroll_animation_js()
        assert "gg-has-js" in js

    def test_adds_gg_in_view(self):
        js = get_scroll_animation_js()
        assert "gg-in-view" in js

    def test_threshold_0_2(self):
        js = get_scroll_animation_js()
        assert "0.2" in js

    def test_handles_already_visible(self):
        """Elements in viewport on load should get gg-in-view immediately."""
        js = get_scroll_animation_js()
        assert "getBoundingClientRect" in js

    def test_queries_data_animate(self):
        js = get_scroll_animation_js()
        assert "data-animate" in js

    def test_reduced_motion_before_observer(self):
        """Reduced motion check must come before observer creation."""
        js = get_scroll_animation_js()
        motion_pos = js.find("prefers-reduced-motion")
        observer_pos = js.find("IntersectionObserver")
        assert motion_pos < observer_pos
