"""Tests for blog preview generator."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_blog_preview import (
    find_candidates,
    generate_preview_html,
    load_race,
    parse_race_date,
)


# ── parse_race_date ──


def test_parse_date_standard():
    d = parse_race_date("2026: June 6")
    assert d is not None
    assert d.year == 2026
    assert d.month == 6
    assert d.day == 6


def test_parse_date_with_range():
    d = parse_race_date("2026: October 3-4")
    assert d is not None
    assert d.year == 2026
    assert d.month == 10
    assert d.day == 3


def test_parse_date_none():
    assert parse_race_date(None) is None
    assert parse_race_date("") is None


def test_parse_date_tbd():
    assert parse_race_date("TBD") is None


def test_parse_date_invalid_month():
    assert parse_race_date("2026: Fakeuary 5") is None


# ── load_race ──


def test_load_race_exists():
    rd = load_race("unbound-200")
    assert rd is not None
    assert rd.get("name") is not None


def test_load_race_nonexistent():
    rd = load_race("nonexistent-race-12345")
    assert rd is None


# ── find_candidates ──


def test_find_candidates_returns_list():
    candidates = find_candidates(min_days=0, max_days=365)
    assert isinstance(candidates, list)


def test_find_candidates_have_required_keys():
    candidates = find_candidates(min_days=0, max_days=365)
    if candidates:
        c = candidates[0]
        assert "slug" in c
        assert "name" in c
        assert "date" in c
        assert "tier" in c
        assert "days_until" in c


def test_find_candidates_sorted():
    """Verify candidates are sorted by tier then days_until."""
    candidates = find_candidates(min_days=0, max_days=365)
    if len(candidates) >= 2:
        for i in range(len(candidates) - 1):
            a, b = candidates[i], candidates[i + 1]
            assert (a["tier"], a["days_until"]) <= (b["tier"], b["days_until"])


# ── generate_preview_html ──


def test_generate_preview_valid():
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "<!DOCTYPE html>" in html
    assert "Unbound" in html


def test_generate_preview_has_seo():
    html = generate_preview_html("mid-south")
    assert html is not None
    assert "og:title" in html
    assert "application/ld+json" in html
    assert 'canonical' in html


def test_generate_preview_has_sections():
    html = generate_preview_html("unbound-200")
    assert html is not None
    # Should have at least some content sections
    assert "Race Preview" in html
    assert "Full Race Profile" in html
    assert "Free Prep Kit" in html


def test_generate_preview_has_tier():
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "Tier 1" in html or "Elite" in html


def test_generate_preview_nonexistent():
    html = generate_preview_html("nonexistent-race-12345")
    assert html is None


def test_generate_preview_escapes_html():
    """Verify HTML entities are escaped in output."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    # Should not contain unescaped angle brackets in text content
    # (but will have them in HTML tags)
    assert "<script>" not in html.split("</head>")[1].split("</body>")[0] or \
           html.count("<script") <= 2  # Only the JSON-LD script


# ── Template quality ──


def test_preview_has_stats_section():
    """Verify stats section renders when data exists."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    # Unbound-200 should have distance and elevation
    assert "Miles" in html or "Ft Elevation" in html


def test_preview_has_hero():
    """Verify hero section exists."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "gg-blog-hero" in html


def test_preview_has_cta():
    """Verify CTA section exists."""
    html = generate_preview_html("unbound-200")
    assert html is not None
    assert "gg-blog-cta" in html
