"""Tests for scrape_utils.py — cache, Cloudflare detection, site loading, extraction."""

import json
import time
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from scrape_utils import (
    _cache_key,
    get_cached,
    set_cached,
    is_cloudflare_blocked,
    load_official_sites,
    _truncate_html,
    _build_extraction_prompt,
    load_extract,
    save_extract,
    CACHE_TTL_SECONDS,
    MAX_HTML_FOR_CLAUDE,
    CLOUDFLARE_MARKERS,
    SCRAPE_CACHE_DIR,
    SCRAPE_EXTRACTS_DIR,
    RACE_DATA_DIR,
)


# ---------------------------------------------------------------------------
# Cache key determinism
# ---------------------------------------------------------------------------

class TestCacheKey:
    def test_deterministic(self):
        """Same URL always produces same cache key."""
        url = "https://unboundgravel.com"
        assert _cache_key(url) == _cache_key(url)

    def test_different_urls_differ(self):
        """Different URLs produce different keys."""
        assert _cache_key("https://a.com") != _cache_key("https://b.com")

    def test_length(self):
        """Cache key is 16 hex chars."""
        key = _cache_key("https://example.com")
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_special_chars(self):
        """URLs with special chars produce valid keys."""
        key = _cache_key("https://example.com/path?q=hello world&x=1#frag")
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_unicode_url(self):
        """Unicode in URL doesn't crash."""
        key = _cache_key("https://example.com/räce/über")
        assert len(key) == 16


# ---------------------------------------------------------------------------
# Cache round-trip
# ---------------------------------------------------------------------------

class TestCacheRoundTrip:
    def test_set_and_get(self, tmp_path, monkeypatch):
        """Cached data can be retrieved."""
        monkeypatch.setattr("scrape_utils.SCRAPE_CACHE_DIR", tmp_path)
        url = "https://unboundgravel.com"
        set_cached(url, "<html>hello</html>", 200, "fetcher")
        result = get_cached(url)
        assert result is not None
        assert result["html"] == "<html>hello</html>"
        assert result["status"] == 200
        assert result["fetcher"] == "fetcher"
        assert result["url"] == url

    def test_miss_returns_none(self, tmp_path, monkeypatch):
        """Non-cached URL returns None."""
        monkeypatch.setattr("scrape_utils.SCRAPE_CACHE_DIR", tmp_path)
        assert get_cached("https://nonexistent.example.com") is None

    def test_expired_returns_none(self, tmp_path, monkeypatch):
        """Expired cache entry returns None."""
        monkeypatch.setattr("scrape_utils.SCRAPE_CACHE_DIR", tmp_path)
        url = "https://expired.example.com"
        set_cached(url, "<html>old</html>", 200, "fetcher")
        # Backdate the timestamp
        path = tmp_path / f"{_cache_key(url)}.json"
        data = json.loads(path.read_text())
        data["timestamp"] = time.time() - CACHE_TTL_SECONDS - 1
        path.write_text(json.dumps(data))
        assert get_cached(url) is None

    def test_fresh_cache_within_ttl(self, tmp_path, monkeypatch):
        """Cache entry just within TTL is returned."""
        monkeypatch.setattr("scrape_utils.SCRAPE_CACHE_DIR", tmp_path)
        url = "https://fresh.example.com"
        set_cached(url, "<html>fresh</html>", 200, "fetcher")
        # Backdate but still within TTL
        path = tmp_path / f"{_cache_key(url)}.json"
        data = json.loads(path.read_text())
        data["timestamp"] = time.time() - CACHE_TTL_SECONDS + 60
        path.write_text(json.dumps(data))
        result = get_cached(url)
        assert result is not None
        assert result["html"] == "<html>fresh</html>"

    def test_corrupt_cache_returns_none(self, tmp_path, monkeypatch):
        """Corrupt JSON in cache returns None."""
        monkeypatch.setattr("scrape_utils.SCRAPE_CACHE_DIR", tmp_path)
        url = "https://corrupt.example.com"
        path = tmp_path / f"{_cache_key(url)}.json"
        path.write_text("NOT VALID JSON {{{")
        assert get_cached(url) is None

    def test_null_html_cached(self, tmp_path, monkeypatch):
        """None html value round-trips correctly (failed fetch)."""
        monkeypatch.setattr("scrape_utils.SCRAPE_CACHE_DIR", tmp_path)
        url = "https://failed.example.com"
        set_cached(url, None, 403, "http_403")
        result = get_cached(url)
        assert result is not None
        assert result["html"] is None
        assert result["status"] == 403

    def test_creates_directory(self, tmp_path, monkeypatch):
        """set_cached creates cache directory if missing."""
        cache_dir = tmp_path / "deep" / "nested" / "cache"
        monkeypatch.setattr("scrape_utils.SCRAPE_CACHE_DIR", cache_dir)
        set_cached("https://example.com", "<html/>", 200, "fetcher")
        assert cache_dir.exists()


# ---------------------------------------------------------------------------
# Cloudflare detection
# ---------------------------------------------------------------------------

class TestCloudflareDetection:
    def test_detects_challenge_page(self):
        """Detects 'Just a moment' Cloudflare challenge."""
        html = """<!DOCTYPE html><html><head><title>Just a moment...</title>
        </head><body>Enable JavaScript and cookies to continue</body></html>"""
        assert is_cloudflare_blocked(html) is True

    def test_detects_cf_browser_verification(self):
        """Detects cf-browser-verification marker."""
        html = '<div id="cf-browser-verification">Verifying...</div>'
        assert is_cloudflare_blocked(html) is True

    def test_detects_cf_chl_opt(self):
        """Detects _cf_chl_opt script variable."""
        html = '<script>window._cf_chl_opt = {cType: "managed"};</script>'
        assert is_cloudflare_blocked(html) is True

    def test_normal_page_not_blocked(self):
        """Normal HTML is not flagged as Cloudflare blocked."""
        html = """<!DOCTYPE html><html><head><title>Unbound Gravel</title>
        </head><body><h1>Welcome to Unbound</h1><p>Register now!</p></body></html>"""
        assert is_cloudflare_blocked(html) is False

    def test_none_input(self):
        """None html returns False (not blocked)."""
        assert is_cloudflare_blocked(None) is False

    def test_empty_string(self):
        """Empty string returns False."""
        assert is_cloudflare_blocked("") is False

    def test_marker_deep_in_page_ignored(self):
        """Cloudflare markers past first 5000 chars are ignored (normal content)."""
        html = "x" * 5001 + "Just a moment"
        assert is_cloudflare_blocked(html) is False


# ---------------------------------------------------------------------------
# load_official_sites
# ---------------------------------------------------------------------------

class TestLoadOfficialSites:
    def test_loads_from_real_data(self):
        """Loads at least some races from actual race-data/."""
        sites = load_official_sites()
        assert len(sites) > 200  # we know ~289 have URLs

    def test_unbound_present(self):
        """Unbound 200 is in the results."""
        sites = load_official_sites(slug_filter="unbound-200")
        assert "unbound-200" in sites
        assert sites["unbound-200"]["url"] == "https://unboundgravel.com"
        assert sites["unbound-200"]["tier"] == 1

    def test_tier_filter(self):
        """Tier filter narrows results."""
        all_sites = load_official_sites()
        t1_only = load_official_sites(tier_filters={1})
        assert len(t1_only) < len(all_sites)
        for info in t1_only.values():
            assert info["tier"] == 1

    def test_slug_filter(self):
        """Slug filter returns at most one result."""
        sites = load_official_sites(slug_filter="unbound-200")
        assert len(sites) <= 1

    def test_structure(self):
        """Each entry has required keys."""
        sites = load_official_sites(slug_filter="unbound-200")
        if "unbound-200" in sites:
            info = sites["unbound-200"]
            assert "url" in info
            assert "name" in info
            assert "tier" in info
            assert "date_specific" in info

    def test_no_non_http_urls(self):
        """All returned URLs start with http."""
        sites = load_official_sites()
        for slug, info in sites.items():
            assert info["url"].startswith("http"), f"{slug} has non-HTTP URL: {info['url']}"


# ---------------------------------------------------------------------------
# HTML truncation
# ---------------------------------------------------------------------------

class TestTruncateHtml:
    def test_short_html_unchanged(self):
        """HTML under limit is returned as-is."""
        html = "<html><body>Hello</body></html>"
        assert _truncate_html(html) == html

    def test_long_html_truncated(self):
        """HTML over limit is truncated to MAX_HTML_FOR_CLAUDE chars."""
        html = "x" * (MAX_HTML_FOR_CLAUDE + 5000)
        result = _truncate_html(html)
        assert len(result) <= MAX_HTML_FOR_CLAUDE

    def test_extracts_main_tag(self):
        """Prefers <main> content when available."""
        main_content = "<p>" + "real content " * 100 + "</p>"
        html = "<html><head><style>" + "x" * 200000 + "</style></head>"
        html += f"<main>{main_content}</main></html>"
        result = _truncate_html(html)
        assert "real content" in result

    def test_strips_script_tags(self):
        """Strips <script> tags from truncated output."""
        html = "<script>var x = 1;</script>" * 1000 + "<p>content</p>" + "x" * MAX_HTML_FOR_CLAUDE
        result = _truncate_html(html)
        assert "var x = 1" not in result


# ---------------------------------------------------------------------------
# Extraction prompt
# ---------------------------------------------------------------------------

class TestBuildExtractionPrompt:
    def test_includes_race_name(self):
        """Prompt includes the race name."""
        prompt = _build_extraction_prompt("<html>test</html>", "Unbound 200", {})
        assert "Unbound 200" in prompt

    def test_includes_html(self):
        """Prompt includes the HTML content."""
        prompt = _build_extraction_prompt("<html><h1>Race Page</h1></html>", "Test Race", {})
        assert "Race Page" in prompt

    def test_includes_existing_data(self):
        """Prompt includes existing profile data for comparison."""
        existing = {"distance_mi": 200, "elevation_ft": 11000}
        prompt = _build_extraction_prompt("<html>test</html>", "Test Race", existing)
        assert "200" in prompt
        assert "11000" in prompt

    def test_requests_json_output(self):
        """Prompt asks for JSON output."""
        prompt = _build_extraction_prompt("<html>test</html>", "Test Race", {})
        assert "JSON" in prompt
        assert "date_2026" in prompt
        assert "distance_mi" in prompt


# ---------------------------------------------------------------------------
# Extract save/load
# ---------------------------------------------------------------------------

class TestExtractSaveLoad:
    def test_round_trip(self, tmp_path, monkeypatch):
        """Extract data round-trips through save/load."""
        monkeypatch.setattr("scrape_utils.SCRAPE_EXTRACTS_DIR", tmp_path)
        data = {"date_2026": "2026-06-06", "distance_mi": 200}
        save_extract("unbound-200", data)
        loaded = load_extract("unbound-200")
        assert loaded == data

    def test_load_missing_returns_none(self, tmp_path, monkeypatch):
        """Loading non-existent extract returns None."""
        monkeypatch.setattr("scrape_utils.SCRAPE_EXTRACTS_DIR", tmp_path)
        assert load_extract("nonexistent-race") is None

    def test_creates_directory(self, tmp_path, monkeypatch):
        """save_extract creates directory if missing."""
        extract_dir = tmp_path / "deep" / "extracts"
        monkeypatch.setattr("scrape_utils.SCRAPE_EXTRACTS_DIR", extract_dir)
        save_extract("test", {"x": 1})
        assert extract_dir.exists()
