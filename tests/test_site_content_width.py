"""Regression checks for the ratified 1200px desktop content measure."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_coaching import build_coaching_css  # noqa: E402
from generate_homepage import build_homepage_css  # noqa: E402
from generate_neo_brutalist import get_page_css  # noqa: E402
from generate_training_plans import build_training_css  # noqa: E402
from shared_footer import get_mega_footer_css  # noqa: E402
from shared_header import get_site_header_css  # noqa: E402


def _rule(css: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", css)
    assert match, f"Missing CSS rule for {selector}"
    return match.group(1)


def test_shared_chrome_uses_ratified_desktop_measure():
    assert "max-width: 1200px" in _rule(get_site_header_css(), ".gg-site-header-inner")

    footer_css = get_mega_footer_css()
    for selector in (
        ".gg-mega-footer-grid",
        ".gg-mega-footer-legal",
        ".gg-mega-footer-disclaimer",
    ):
        assert "max-width: 1200px" in _rule(footer_css, selector)


def test_race_profile_uses_wide_frame_and_readable_prose():
    css = get_page_css()
    assert "max-width: 1200px" in _rule(css, ".gg-neo-brutalist-page")
    assert "max-width: 1200px" in _rule(css, ".gg-sticky-cta-inner")
    assert "max-width: 68ch" in _rule(css, ".gg-neo-brutalist-page .gg-prose")


def test_homepage_major_sections_share_1200px_measure():
    css = build_homepage_css()
    selectors = (
        ".gg-hp-hero-inner",
        ".gg-hp-ladder-grid",
        ".gg-hp-stats-inner",
        ".gg-hp-content-grid",
        ".gg-hp-how-it-works",
    )
    for selector in selectors:
        assert "max-width: 1200px" in _rule(css, selector)
    assert "max-width: 1080px" not in css


def test_training_plan_page_widens_frame_without_stretching_copy():
    css = build_training_css()
    for selector in (".gg-breadcrumb", ".gg-tp-section", ".gg-tp-hero"):
        assert "max-width: 1200px" in _rule(css, selector)
    assert "max-width: none" in _rule(css, ".gg-tp-hero-title")
    assert "max-width: 600px" in _rule(css, ".gg-tp-hero-sub")
    assert "max-width: 760px" in _rule(css, ".gg-tp-coaching-copy")


def test_coaching_reference_keeps_1200px_frame_and_68ch_prose():
    css = build_coaching_css()
    assert "max-width: 1200px" in _rule(css, ".gg-coach-inner")
    assert css.count("max-width: 68ch") >= 2


@pytest.mark.parametrize(
    ("source", "selector"),
    (
        ("generate_state_hubs.py", ".gg-state-page"),
        ("generate_tier_hubs.py", ".gg-hub-page"),
        ("generate_series_hubs.py", ".gg-series-page"),
        ("generate_vs_pages.py", ".gg-vs-page"),
        ("generate_power_rankings.py", ".gg-pr-page"),
        ("generate_insights.py", ".gg-insights-section"),
        ("generate_calendar.py", ".gg-cal-page"),
        ("generate_articles_index.py", ".gg-ai-page"),
        ("generate_courses.py", ".gg-course-index-inner"),
        ("generate_latest.py", ".gg-wire"),
        ("generate_blog_index_page.py", ".gg-blog-index"),
        ("generate_training_plan_pages.py", ".gg-tpp-page"),
        ("generate_whitepaper_fueling.py", ".gg-wp-scroll-section"),
        ("generate_consulting.py", ".gg-breadcrumb"),
    ),
)
def test_remaining_default_page_families_use_1200px(source: str, selector: str):
    text = (ROOT / "wordpress" / source).read_text()
    rule = _rule(text.replace("{{", "{").replace("}}", "}"), selector)
    assert re.search(r"max-width:\s*1200px", rule)


def test_release_overlay_is_width_only_and_preserves_prose_caps():
    css = (ROOT / "wordpress" / "desktop_width_override.css").read_text()
    declarations = re.findall(r"\b([a-z-]+)\s*:", re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL))
    assert set(declarations) == {"max-width"}

    assert "max-width: 1200px !important" in _rule(css, ".gg-site-header-inner")
    assert "max-width: none" in _rule(css, ".gg-tp-section.gg-tp-section-alt")
    assert "max-width: none" in _rule(css, ".gg-tp-hero-title")
    assert "max-width: 68ch" in _rule(css, ".gg-neo-brutalist-page .gg-prose")

    expected_caps = {
        ".gg-tp-hero-sub": "600px",
        ".gg-tp-hero-bar": "550px",
        ".gg-tp-delivery-terms": "700px",
        ".gg-tp-pullquote p": "750px",
        ".gg-tp-coaching-copy": "760px",
        ".gg-tp-pricing-wrap": "500px",
        ".gg-tp-deliverable-content p": "68ch",
        ".gg-tp-step p": "68ch",
    }
    for selector, width in expected_caps.items():
        assert f"max-width: {width}" in _rule(css, selector)
