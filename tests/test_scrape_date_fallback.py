"""Tests for batch_date_search.py --use-scraper fallback."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from batch_date_search import (
    scraper_fallback_date,
    extract_date_from_text,
    _month_num,
    _month_distance,
    _extract_month_from_date_specific,
)


# ---------------------------------------------------------------------------
# Cached extract fallback
# ---------------------------------------------------------------------------

class TestCachedExtractFallback:
    def test_reads_cached_iso_date(self, monkeypatch):
        """Falls back to cached extract with ISO date."""
        monkeypatch.setattr("batch_date_search.HAS_SCRAPER", True)
        extract = {"date_2026": "2026-07-12", "distance_mi": 200}

        with patch("batch_date_search.load_extract", return_value=extract):
            date_spec, month = scraper_fallback_date(
                {"logistics": {"official_site": "https://example.com"}},
                "test-race",
            )

        assert date_spec == "2026: July 12"
        assert month == "July"

    def test_reads_cached_text_date(self, monkeypatch):
        """Falls back to cached extract with text date like 'June 6, 2026'."""
        monkeypatch.setattr("batch_date_search.HAS_SCRAPER", True)
        extract = {"date_2026": "June 6, 2026"}

        with patch("batch_date_search.load_extract", return_value=extract):
            date_spec, month = scraper_fallback_date(
                {"logistics": {"official_site": "https://example.com"}},
                "test-race",
            )

        assert date_spec is not None
        assert "June" in date_spec
        assert month == "June"

    def test_no_extract_no_url_returns_none(self, monkeypatch):
        """Returns None when no extract and no URL."""
        monkeypatch.setattr("batch_date_search.HAS_SCRAPER", True)

        with patch("batch_date_search.load_extract", return_value=None):
            date_spec, month = scraper_fallback_date(
                {"logistics": {}},
                "test-race",
            )

        assert date_spec is None
        assert month is None

    def test_extract_without_date_tries_scrape(self, monkeypatch):
        """When extract has no date_2026, falls back to direct scraping."""
        monkeypatch.setattr("batch_date_search.HAS_SCRAPER", True)
        extract = {"distance_mi": 200}  # No date_2026

        html = '<html><body><p>Race date: July 12, 2026</p></body></html>'
        with patch("batch_date_search.load_extract", return_value=extract), \
             patch("batch_date_search.fetch_url", return_value=(html, 200, "fetcher")):
            date_spec, month = scraper_fallback_date(
                {"logistics": {"official_site": "https://example.com"}},
                "test-race",
            )

        assert date_spec == "2026: July 12"
        assert month == "July"


# ---------------------------------------------------------------------------
# Scraper not available
# ---------------------------------------------------------------------------

class TestScraperUnavailable:
    def test_no_scraper_returns_none(self, monkeypatch):
        """Returns None when scrapling is not installed."""
        monkeypatch.setattr("batch_date_search.HAS_SCRAPER", False)

        date_spec, month = scraper_fallback_date(
            {"logistics": {"official_site": "https://example.com"}},
            "test-race",
        )

        assert date_spec is None
        assert month is None


# ---------------------------------------------------------------------------
# Direct scraping fallback
# ---------------------------------------------------------------------------

class TestDirectScrapingFallback:
    def test_scrapes_url_extracts_date(self, monkeypatch):
        """Direct scraping finds date in HTML."""
        monkeypatch.setattr("batch_date_search.HAS_SCRAPER", True)

        html = """
        <html><body>
        <h1>Big Gravel Race 2026</h1>
        <p>Join us on September 14, 2026 for the ultimate gravel experience!</p>
        </body></html>
        """

        with patch("batch_date_search.load_extract", return_value=None), \
             patch("batch_date_search.fetch_url", return_value=(html, 200, "fetcher")):
            date_spec, month = scraper_fallback_date(
                {"logistics": {"official_site": "https://biggravel.com"}},
                "big-gravel-race",
            )

        assert date_spec == "2026: September 14"
        assert month == "September"

    def test_fetch_failure_returns_none(self, monkeypatch):
        """Returns None when fetch fails."""
        monkeypatch.setattr("batch_date_search.HAS_SCRAPER", True)

        with patch("batch_date_search.load_extract", return_value=None), \
             patch("batch_date_search.fetch_url", return_value=(None, 0, "error")):
            date_spec, month = scraper_fallback_date(
                {"logistics": {"official_site": "https://example.com"}},
                "test-race",
            )

        assert date_spec is None
        assert month is None

    def test_no_date_in_html_returns_none(self, monkeypatch):
        """Returns None when HTML has no 2026 date."""
        monkeypatch.setattr("batch_date_search.HAS_SCRAPER", True)

        html = "<html><body><h1>Race Coming Soon</h1></body></html>"

        with patch("batch_date_search.load_extract", return_value=None), \
             patch("batch_date_search.fetch_url", return_value=(html, 200, "fetcher")):
            date_spec, month = scraper_fallback_date(
                {"logistics": {"official_site": "https://example.com"}},
                "test-race",
            )

        assert date_spec is None
