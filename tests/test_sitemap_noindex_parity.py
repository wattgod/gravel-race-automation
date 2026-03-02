"""Parity tests between Python sitemap logic and PHP noindex logic.

Cross-validates that the two independent systems (Python blog sitemap
generation and PHP noindex mu-plugin) agree on which blog pages are
indexable vs noindexed. Prevents silent drift between systems.
"""

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from generate_blog_index import classify_blog_slug
from generate_sitemap import INDEXABLE_BLOG_CATEGORIES


def php_blog_noindex(uri: str) -> bool:
    """Simulate the PHP blog noindex logic from gg-noindex.php."""
    if not re.match(r'^/blog/[a-z0-9-]+/?$', uri):
        return False
    if re.match(r'^/blog/roundup-', uri):
        return False
    if re.search(r'-recap/?$', uri):
        return False
    return True


@pytest.fixture
def blog_index():
    """Load real blog-index.json if available."""
    index_path = Path(__file__).parent.parent / "web" / "blog-index.json"
    if not index_path.exists():
        pytest.skip("blog-index.json not available")
    return json.loads(index_path.read_text())


class TestSitemapNoindexParity:
    def test_sitemap_urls_not_noindexed(self, blog_index):
        """Every URL that would appear in sitemap must NOT be noindexed by PHP."""
        for entry in blog_index:
            slug = entry.get("slug", "")
            category = entry.get("category", "preview")
            if category in INDEXABLE_BLOG_CATEGORIES:
                uri = f"/blog/{slug}/"
                assert not php_blog_noindex(uri), \
                    f"Sitemap-included URL {uri} (category={category}) is noindexed by PHP"

    def test_noindexed_urls_not_in_sitemap(self, blog_index):
        """Every URL noindexed by PHP must NOT be in the sitemap categories."""
        for entry in blog_index:
            slug = entry.get("slug", "")
            uri = f"/blog/{slug}/"
            if php_blog_noindex(uri):
                category = entry.get("category", "preview")
                assert category not in INDEXABLE_BLOG_CATEGORIES, \
                    f"PHP-noindexed URL {uri} has indexable category '{category}' — would appear in sitemap"

    def test_classify_agrees_with_php(self, blog_index):
        """classify_blog_slug() must agree with PHP regex for all entries."""
        for entry in blog_index:
            slug = entry.get("slug", "")
            category = classify_blog_slug(slug)
            uri = f"/blog/{slug}/"
            is_noindexed = php_blog_noindex(uri)

            if category in INDEXABLE_BLOG_CATEGORIES:
                assert not is_noindexed, \
                    f"classify_blog_slug('{slug}')='{category}' (indexable) but PHP noindexes it"
            else:
                assert is_noindexed, \
                    f"classify_blog_slug('{slug}')='{category}' (not indexable) but PHP allows it"

    def test_no_unknown_categories(self, blog_index):
        """All categories in blog-index.json must be known."""
        known = {"roundup", "recap", "preview"}
        for entry in blog_index:
            category = entry.get("category", "preview")
            assert category in known, \
                f"Unknown category '{category}' for slug '{entry.get('slug')}' — " \
                f"add to INDEXABLE_BLOG_CATEGORIES or known set"
