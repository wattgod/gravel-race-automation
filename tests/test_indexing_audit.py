"""Tests for scripts/indexing_audit.py — sitemap indexing audit.

Covers:
- URL categorization (each page type pattern)
- Sitemap XML parsing with minimal samples
- Mock data output format
- Summary aggregation
"""
from __future__ import annotations

import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from indexing_audit import (
    BASE_URL,
    PAGE_TYPE_RULES,
    STATUS_CRAWLED_NOT_INDEXED,
    STATUS_ERROR,
    STATUS_INDEXED,
    STATUS_NOT_INDEXED,
    classify_url,
    generate_mock_data,
    parse_sitemap,
)


# ── URL categorization ─────────────────────────────────────


class TestClassifyUrl:
    """Each URL pattern should map to the correct page type."""

    def test_state_hubs(self):
        assert classify_url("/race/best-gravel-races-colorado/") == "state_hubs"
        assert classify_url("/race/best-gravel-races-california/") == "state_hubs"

    def test_tire_guides(self):
        assert classify_url("/race/unbound-200/tires/") == "tire_guides"
        assert classify_url("/race/mid-south/tires/") == "tire_guides"

    def test_vs_comparisons(self):
        assert classify_url("/race/unbound-200-vs-dirty-kanza/") == "vs_comparisons"
        assert classify_url("/race/leadville-vs-steamboat/") == "vs_comparisons"

    def test_tier_hubs(self):
        assert classify_url("/race/tier-1/") == "tier_hubs"
        assert classify_url("/race/tier-4/") == "tier_hubs"

    def test_series_hubs(self):
        assert classify_url("/race/series/lifetime-grand-prix/") == "series_hubs"

    def test_training_guides(self):
        assert classify_url("/guide/") == "training_guides"
        assert classify_url("/guide/gravel-training/") == "training_guides"

    def test_blog_posts(self):
        assert classify_url("/blog/tire-pressure-guide/") == "blog_posts"
        assert classify_url("/blog/2026/best-gravel-bikes/") == "blog_posts"

    def test_course_pages(self):
        assert classify_url("/course/gravel-101/") == "course_pages"

    def test_race_profiles_catch_all(self):
        assert classify_url("/race/unbound-200/") == "race_profiles"
        assert classify_url("/race/mid-south/") == "race_profiles"

    def test_other_urls(self):
        assert classify_url("/") == "other"
        assert classify_url("/coaching/") == "other"
        assert classify_url("/about/") == "other"

    def test_state_hubs_matched_before_race_profiles(self):
        """State hub pattern must match before the race profile catch-all."""
        result = classify_url("/race/best-gravel-races-texas/")
        assert result == "state_hubs"

    def test_tire_guides_matched_before_race_profiles(self):
        result = classify_url("/race/unbound-200/tires/")
        assert result == "tire_guides"

    def test_vs_matched_before_race_profiles(self):
        result = classify_url("/race/race-a-vs-race-b/")
        assert result == "vs_comparisons"


# ── Sitemap XML parsing ────────────────────────────────────


class TestParseSitemap:
    """Parse sitemap.xml and extract URL paths."""

    @pytest.fixture
    def minimal_sitemap(self, tmp_path):
        """Create a minimal valid sitemap.xml for testing."""
        sitemap_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{BASE_URL}/race/unbound-200/</loc></url>
  <url><loc>{BASE_URL}/race/mid-south/</loc></url>
  <url><loc>{BASE_URL}/race/unbound-200/tires/</loc></url>
  <url><loc>{BASE_URL}/race/best-gravel-races-colorado/</loc></url>
  <url><loc>{BASE_URL}/guide/</loc></url>
  <url><loc>{BASE_URL}/</loc></url>
</urlset>"""
        sitemap_path = tmp_path / "sitemap.xml"
        sitemap_path.write_text(sitemap_content)
        return sitemap_path

    def test_parses_correct_number_of_urls(self, minimal_sitemap):
        urls = parse_sitemap(minimal_sitemap)
        assert len(urls) == 6

    def test_strips_base_url(self, minimal_sitemap):
        urls = parse_sitemap(minimal_sitemap)
        for url in urls:
            assert not url.startswith("http")

    def test_returns_sorted_urls(self, minimal_sitemap):
        urls = parse_sitemap(minimal_sitemap)
        assert urls == sorted(urls)

    def test_root_url_becomes_slash(self, minimal_sitemap):
        urls = parse_sitemap(minimal_sitemap)
        assert "/" in urls

    def test_race_paths_preserved(self, minimal_sitemap):
        urls = parse_sitemap(minimal_sitemap)
        assert "/race/unbound-200/" in urls
        assert "/race/mid-south/" in urls

    def test_tire_guide_path_preserved(self, minimal_sitemap):
        urls = parse_sitemap(minimal_sitemap)
        assert "/race/unbound-200/tires/" in urls

    def test_state_hub_path_preserved(self, minimal_sitemap):
        urls = parse_sitemap(minimal_sitemap)
        assert "/race/best-gravel-races-colorado/" in urls

    def test_nonexistent_sitemap_exits(self, tmp_path):
        fake_path = tmp_path / "nonexistent.xml"
        with pytest.raises(SystemExit):
            parse_sitemap(fake_path)

    def test_empty_sitemap(self, tmp_path):
        """A sitemap with no <url> entries returns empty list."""
        sitemap_content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
</urlset>"""
        sitemap_path = tmp_path / "empty_sitemap.xml"
        sitemap_path.write_text(sitemap_content)
        urls = parse_sitemap(sitemap_path)
        assert urls == []


# ── Mock data output format ────────────────────────────────


class TestMockDataOutput:
    """Tests for generate_mock_data output structure."""

    @pytest.fixture
    def sample_urls(self):
        return [
            "/race/unbound-200/",
            "/race/mid-south/",
            "/race/unbound-200/tires/",
            "/race/best-gravel-races-colorado/",
            "/race/race-a-vs-race-b/",
            "/race/tier-1/",
            "/guide/",
            "/blog/test-post/",
            "/",
        ]

    def test_returns_list_of_dicts(self, sample_urls):
        results = generate_mock_data(sample_urls)
        assert isinstance(results, list)
        assert all(isinstance(r, dict) for r in results)

    def test_each_result_has_required_keys(self, sample_urls):
        results = generate_mock_data(sample_urls)
        for r in results:
            assert "url" in r
            assert "status" in r
            assert "page_type" in r

    def test_result_count_matches_input(self, sample_urls):
        results = generate_mock_data(sample_urls)
        assert len(results) == len(sample_urls)

    def test_statuses_are_valid(self, sample_urls):
        valid_statuses = {STATUS_INDEXED, STATUS_NOT_INDEXED,
                          STATUS_CRAWLED_NOT_INDEXED, STATUS_ERROR}
        results = generate_mock_data(sample_urls)
        for r in results:
            assert r["status"] in valid_statuses

    def test_page_types_are_classified(self, sample_urls):
        results = generate_mock_data(sample_urls)
        types = {r["page_type"] for r in results}
        # Should include at least race_profiles and other
        assert "race_profiles" in types or "tire_guides" in types

    def test_reproducible_with_fixed_seed(self, sample_urls):
        """generate_mock_data uses seed(42) so results are deterministic."""
        results1 = generate_mock_data(sample_urls)
        results2 = generate_mock_data(sample_urls)
        for r1, r2 in zip(results1, results2):
            assert r1["status"] == r2["status"]

    def test_urls_preserved_in_output(self, sample_urls):
        results = generate_mock_data(sample_urls)
        result_urls = [r["url"] for r in results]
        for url in sample_urls:
            assert url in result_urls

    def test_page_type_for_race_profile(self, sample_urls):
        results = generate_mock_data(sample_urls)
        unbound = next(r for r in results if r["url"] == "/race/unbound-200/")
        assert unbound["page_type"] == "race_profiles"

    def test_page_type_for_tire_guide(self, sample_urls):
        results = generate_mock_data(sample_urls)
        tire = next(r for r in results if r["url"] == "/race/unbound-200/tires/")
        assert tire["page_type"] == "tire_guides"

    def test_page_type_for_state_hub(self, sample_urls):
        results = generate_mock_data(sample_urls)
        state = next(r for r in results if r["url"] == "/race/best-gravel-races-colorado/")
        assert state["page_type"] == "state_hubs"

    def test_page_type_for_vs_comparison(self, sample_urls):
        results = generate_mock_data(sample_urls)
        vs = next(r for r in results if r["url"] == "/race/race-a-vs-race-b/")
        assert vs["page_type"] == "vs_comparisons"

    def test_page_type_for_tier_hub(self, sample_urls):
        results = generate_mock_data(sample_urls)
        tier = next(r for r in results if r["url"] == "/race/tier-1/")
        assert tier["page_type"] == "tier_hubs"

    def test_page_type_for_training_guide(self, sample_urls):
        results = generate_mock_data(sample_urls)
        guide = next(r for r in results if r["url"] == "/guide/")
        assert guide["page_type"] == "training_guides"

    def test_page_type_for_blog(self, sample_urls):
        results = generate_mock_data(sample_urls)
        blog = next(r for r in results if r["url"] == "/blog/test-post/")
        assert blog["page_type"] == "blog_posts"

    def test_page_type_for_other(self, sample_urls):
        results = generate_mock_data(sample_urls)
        root = next(r for r in results if r["url"] == "/")
        assert root["page_type"] == "other"
