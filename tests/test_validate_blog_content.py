"""Tests for validate_blog_content.py quality gate.

Sprint 35: Tests that prove the Python repr detection patterns catch
real repr strings and don't false-positive on normal HTML content.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_blog_content import (
    PYTHON_REPR_PATTERNS,
    Validator,
    check_no_python_repr,
)

# Single source of truth — imported from the validator, not duplicated
REPR_PATTERNS = PYTHON_REPR_PATTERNS


def _any_pattern_matches(text):
    """Return True if any repr pattern matches the text."""
    for pattern, _ in REPR_PATTERNS:
        if pattern.search(text):
            return True
    return False


# ── True positives: these MUST be caught ──


class TestReprDetectionTruePositives:
    """Every one of these is real Python repr that leaked into HTML.
    If any test fails, the quality gate has a hole."""

    def test_catches_dict_single_quoted(self):
        text = "{'requirement': 'Heat adaptation', 'by_when': 'Week 6'}"
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_dict_html_escaped(self):
        text = "{&#x27;requirement&#x27;: &#x27;Heat adaptation&#x27;}"
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_list_single_quoted(self):
        text = "['Flint Hills gravel', 'rolling hills', 'sharp limestone']"
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_list_html_escaped(self):
        text = "[&#x27;Flint Hills gravel&#x27;, &#x27;rolling hills&#x27;]"
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_list_of_dicts_single_quoted(self):
        text = "[{'mile': 20, 'label': 'Early Mountains'}]"
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_list_of_dicts_double_quoted(self):
        text = '[{"mile": 20, "label": "Early Mountains"}]'
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_dict_double_quoted(self):
        text = '{"requirement": "Heat adaptation", "by_when": "Week 6"}'
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_list_double_quoted(self):
        text = '["2019: Renamed", "2021: Prize purse"]'
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_single_item_list_html_escaped(self):
        text = "[&#x27;single item&#x27;]"
        assert _any_pattern_matches(text), f"Should catch: {text}"

    def test_catches_list_of_dicts_html_escaped(self):
        text = "[{&#x27;mile&#x27;: 20}]"
        assert _any_pattern_matches(text), f"Should catch: {text}"


# ── True negatives: these MUST NOT be caught ──


class TestReprDetectionTrueNegatives:
    """Normal HTML content that should never trigger false positives.
    If any test fails, the quality gate is too aggressive."""

    def test_ignores_normal_html_text(self):
        text = "<p>This is a normal paragraph with some text.</p>"
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_html_links(self):
        text = '<a href="https://example.com/race/unbound-200/">Link</a>'
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_css_selectors(self):
        text = ".gg-blog-stat { text-align: center; }"
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_html_entities(self):
        text = "Flint Hills gravel &middot; rolling hills &middot; limestone"
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_html_escaped_apostrophes_in_text(self):
        text = "Renamed &#x27;Unbound Gravel&#x27; to reflect evolution"
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_parenthetical_text(self):
        text = "Prize purse equality ($100K split)"
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_year_colon_text(self):
        text = "<li>2019: Renamed to reflect evolution</li>"
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_bold_html(self):
        text = "<strong>Mile 60: First Meltdown Zone</strong>"
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_data_attributes(self):
        text = '<div data-tier="1" data-score="87">Race card</div>'
        assert not _any_pattern_matches(text), f"False positive on: {text}"

    def test_ignores_inline_style(self):
        text = '<div style="color: #59473c; font-weight: bold;">Text</div>'
        assert not _any_pattern_matches(text), f"False positive on: {text}"


# ── Integration: check_no_python_repr against real files ──


class TestCheckNoPythonReprIntegration:
    """Test the full check_no_python_repr function with temp files."""

    def test_clean_file_passes(self, tmp_path):
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "clean.html").write_text(
            "<!DOCTYPE html><html><head></head><body>"
            "<p>Normal content with <strong>bold</strong> text.</p>"
            "<ul><li>2019: Good moment</li></ul>"
            "</body></html>"
        )

        import validate_blog_content
        orig_dir = validate_blog_content.BLOG_DIR
        validate_blog_content.BLOG_DIR = blog_dir
        try:
            v = Validator()
            check_no_python_repr(v)
            assert v.failed == 0, "Clean file should pass"
            assert v.passed >= 1
        finally:
            validate_blog_content.BLOG_DIR = orig_dir

    def test_dirty_file_fails(self, tmp_path):
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "dirty.html").write_text(
            "<!DOCTYPE html><html><head></head><body>"
            "<p>{'requirement': 'Heat adaptation', 'by_when': 'Week 6'}</p>"
            "</body></html>"
        )

        import validate_blog_content
        orig_dir = validate_blog_content.BLOG_DIR
        validate_blog_content.BLOG_DIR = blog_dir
        try:
            v = Validator()
            check_no_python_repr(v)
            assert v.failed >= 1, "File with raw dict should fail"
        finally:
            validate_blog_content.BLOG_DIR = orig_dir

    def test_repr_in_script_tag_ignored(self, tmp_path):
        """Raw repr inside <script> tags should NOT trigger failure."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "script-ok.html").write_text(
            '<!DOCTYPE html><html><head></head><body>'
            '<script type="application/ld+json">{"name": "Test"}</script>'
            '<p>Normal content</p>'
            '</body></html>'
        )

        import validate_blog_content
        orig_dir = validate_blog_content.BLOG_DIR
        validate_blog_content.BLOG_DIR = blog_dir
        try:
            v = Validator()
            check_no_python_repr(v)
            assert v.failed == 0, "JSON-LD in script tag should be ignored"
        finally:
            validate_blog_content.BLOG_DIR = orig_dir

    def test_list_of_dicts_in_body_fails(self, tmp_path):
        """List-of-dicts repr (the most common bug) should fail."""
        blog_dir = tmp_path / "blog"
        blog_dir.mkdir()
        (blog_dir / "list-dicts.html").write_text(
            "<!DOCTYPE html><html><head></head><body>"
            "<p>[{'mile': 20, 'label': 'Early Mountains'}]</p>"
            "</body></html>"
        )

        import validate_blog_content
        orig_dir = validate_blog_content.BLOG_DIR
        validate_blog_content.BLOG_DIR = blog_dir
        try:
            v = Validator()
            check_no_python_repr(v)
            assert v.failed >= 1, "List-of-dicts repr should fail"
        finally:
            validate_blog_content.BLOG_DIR = orig_dir
