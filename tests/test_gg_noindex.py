"""Tests for WordPress mu-plugin gg-noindex.php blog classification logic.

Simulates the PHP regex in Python to validate noindex classification
matches the Python classify_blog_slug() logic.
"""

import re

import pytest


def php_blog_noindex(uri: str) -> bool:
    """Simulate the PHP blog noindex logic from gg-noindex.php.

    Returns True if the URI would be noindexed by the PHP plugin.
    """
    # Must be a blog slug page (not the /blog/ index itself)
    if not re.match(r'^/blog/[a-z0-9-]+/?$', uri):
        return False
    # Roundups start with "roundup-" — NOT noindexed
    if re.match(r'^/blog/roundup-', uri):
        return False
    # Recaps end with "-recap" — NOT noindexed
    if re.search(r'-recap/?$', uri):
        return False
    # Everything else is a preview — noindexed
    return True


class TestPhpNoindex:
    def test_preview_gets_noindexed(self):
        assert php_blog_noindex("/blog/unbound-200/") is True

    def test_roundup_not_noindexed(self):
        assert php_blog_noindex("/blog/roundup-march-2026/") is False

    def test_recap_not_noindexed(self):
        assert php_blog_noindex("/blog/unbound-200-recap/") is False

    def test_blog_index_not_matched(self):
        """The /blog/ index page itself must not be noindexed."""
        assert php_blog_noindex("/blog/") is False

    def test_no_false_positive_roundup_substring(self):
        """'roundup' inside slug but not at start → should be noindexed."""
        assert php_blog_noindex("/blog/my-roundup-race/") is True

    def test_no_false_positive_recap_substring(self):
        """'recap' inside slug but not at end → should be noindexed."""
        assert php_blog_noindex("/blog/recap-of-races/") is True

    def test_trailing_slash_optional(self):
        """Both /blog/slug and /blog/slug/ should behave the same."""
        assert php_blog_noindex("/blog/unbound-200") is True
        assert php_blog_noindex("/blog/unbound-200/") is True
        assert php_blog_noindex("/blog/roundup-march-2026") is False
        assert php_blog_noindex("/blog/roundup-march-2026/") is False

    def test_race_pages_not_affected(self):
        """Race pages (/race/{slug}/) must not match blog noindex logic."""
        assert php_blog_noindex("/race/unbound-200/") is False

    def test_nested_paths_not_matched(self):
        """Nested blog paths like /blog/category/slug/ must not match."""
        assert php_blog_noindex("/blog/category/unbound-200/") is False

    def test_recap_with_no_trailing_slash(self):
        assert php_blog_noindex("/blog/mid-south-recap") is False
