"""Tests for youtube_thumbnail.py — thumbnail fetching, scoring, and caching.

Covers:
  - score_thumbnail dict shape and key presence
  - Black thumbnail detection
  - Nature/cycling thumbnail scoring
  - Text overlay detection
  - get_best_thumbnail_url maxres vs hqdefault selection
  - Cache hit behavior
  - Cache TTL expiration
"""

import io
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PIL = pytest.importorskip("PIL", reason="Pillow required for thumbnail tests")

# Ensure scripts/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from PIL import Image

from youtube_thumbnail import (
    score_thumbnail,
    get_best_thumbnail_url,
    fetch_thumbnail,
    _is_black_frame,
    _has_text_overlay,
    _score_brightness,
    _score_contrast,
    _score_nature_color,
    CACHE_DIR,
    CACHE_TTL_DAYS,
)


# ── Helpers ──────────────────────────────────────────────────

def _make_solid_image(color: tuple, size: tuple = (480, 360)) -> bytes:
    """Create a solid-color JPEG image as bytes."""
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


def _make_green_image() -> bytes:
    """Create a green (nature-like) image."""
    return _make_solid_image((60, 140, 50))


def _make_black_image() -> bytes:
    """Create a near-black image."""
    return _make_solid_image((5, 5, 5))


def _make_white_image() -> bytes:
    """Create a near-white image."""
    return _make_solid_image((250, 250, 250))


# ── Score Dict Shape ─────────────────────────────────────────

class TestScoreThumbnailShape:
    """Verify score_thumbnail returns all expected keys."""

    @patch("youtube_thumbnail.fetch_thumbnail")
    def test_score_thumbnail_dict_shape(self, mock_fetch):
        mock_fetch.return_value = (_make_green_image(), True)
        result = score_thumbnail("abcdefghijk")

        expected_keys = {"score", "has_text", "is_black", "has_maxres",
                         "brightness", "contrast", "nature_color"}
        assert set(result.keys()) == expected_keys
        assert isinstance(result["score"], float)
        assert isinstance(result["has_text"], bool)
        assert isinstance(result["is_black"], bool)
        assert isinstance(result["has_maxres"], bool)

    @patch("youtube_thumbnail.fetch_thumbnail")
    def test_empty_bytes_returns_zero_score(self, mock_fetch):
        mock_fetch.return_value = (b"", False)
        result = score_thumbnail("abcdefghijk")
        assert result["score"] == 0.0
        assert result["is_black"] is True


# ── Black Thumbnail Detection ────────────────────────────────

class TestBlackThumbnail:
    """Test black/dark frame detection."""

    def test_black_image_detected(self):
        img = Image.open(io.BytesIO(_make_black_image()))
        assert _is_black_frame(img) is True

    def test_normal_image_not_black(self):
        img = Image.open(io.BytesIO(_make_green_image()))
        assert _is_black_frame(img) is False

    @patch("youtube_thumbnail.fetch_thumbnail")
    def test_black_thumbnail_in_score(self, mock_fetch):
        mock_fetch.return_value = (_make_black_image(), False)
        result = score_thumbnail("abcdefghijk")
        assert result["is_black"] is True


# ── Nature Thumbnail Scoring ─────────────────────────────────

class TestNatureThumbnail:
    """Test nature/cycling color scoring."""

    def test_green_image_scores_high(self):
        img = Image.open(io.BytesIO(_make_green_image()))
        score = _score_nature_color(img)
        assert score > 0.4

    def test_white_image_scores_low(self):
        img = Image.open(io.BytesIO(_make_white_image()))
        score = _score_nature_color(img)
        assert score <= 0.3

    @patch("youtube_thumbnail.fetch_thumbnail")
    def test_nature_thumbnail_composite_score(self, mock_fetch):
        mock_fetch.return_value = (_make_green_image(), True)
        result = score_thumbnail("abcdefghijk")
        # Green image should have decent nature_color contribution
        assert result["score"] > 40


# ── Text Overlay Detection ───────────────────────────────────

class TestTextOverlay:
    """Test text overlay detection heuristics."""

    def test_solid_image_no_text(self):
        img = Image.open(io.BytesIO(_make_green_image()))
        assert _has_text_overlay(img) is False

    def test_high_edge_image_detected_as_text(self):
        """Image with sharp edges in top/bottom strips should be flagged."""
        # Create image with high contrast top strip (simulating text overlay)
        img = Image.new("RGB", (480, 360), (50, 50, 50))
        # Draw alternating black/white lines in top strip
        for x in range(0, 480, 2):
            for y in range(0, 90):
                img.putpixel((x, y), (255, 255, 255))
        assert _has_text_overlay(img) is True


# ── URL Selection ────────────────────────────────────────────

class TestBestThumbnailUrl:
    """Test get_best_thumbnail_url URL selection."""

    def test_best_url_maxres(self):
        url = get_best_thumbnail_url("abcdefghijk", has_maxres=True)
        assert "maxresdefault" in url
        assert "abcdefghijk" in url

    def test_best_url_fallback(self):
        url = get_best_thumbnail_url("abcdefghijk", has_maxres=False)
        assert "hqdefault" in url
        assert "maxresdefault" not in url
        assert "abcdefghijk" in url


# ── Cache Behavior ───────────────────────────────────────────

class TestCacheBehavior:
    """Test thumbnail cache hit and TTL expiration."""

    @patch("youtube_thumbnail._fetch_url")
    def test_cache_hit(self, mock_fetch_url, tmp_path):
        """Cached file should be returned without fetching."""
        with patch("youtube_thumbnail.CACHE_DIR", tmp_path):
            # Pre-populate cache
            cache_file = tmp_path / "abcdefghijk.jpg"
            img_bytes = _make_green_image()
            cache_file.write_bytes(img_bytes)

            result_bytes, has_maxres = fetch_thumbnail("abcdefghijk")
            assert result_bytes == img_bytes
            mock_fetch_url.assert_not_called()

    @patch("youtube_thumbnail._fetch_url")
    def test_cache_ttl_expired(self, mock_fetch_url, tmp_path):
        """Expired cache should trigger a new fetch."""
        with patch("youtube_thumbnail.CACHE_DIR", tmp_path):
            # Pre-populate cache with old timestamp
            cache_file = tmp_path / "abcdefghijk.jpg"
            img_bytes = _make_green_image()
            cache_file.write_bytes(img_bytes)
            # Set mtime to 31 days ago
            old_time = time.time() - (CACHE_TTL_DAYS + 1) * 86400
            import os
            os.utime(cache_file, (old_time, old_time))

            new_img_bytes = _make_solid_image((100, 100, 100))
            mock_fetch_url.return_value = new_img_bytes

            result_bytes, _ = fetch_thumbnail("abcdefghijk")
            # Should have fetched new data
            mock_fetch_url.assert_called()
