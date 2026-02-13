"""Tests for season roundup generator."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_season_roundup import (
    MONTH_NAMES,
    MONTH_NUMBERS,
    REGIONS,
    SEASONS,
    TIER_NAMES,
    build_race_card_html,
    build_roundup_stats,
    classify_blog_slug,
    filter_by_month,
    filter_by_region,
    filter_by_tier,
    generate_roundup_html,
    load_race_index,
)


@pytest.fixture
def race_index():
    """Load the real race-index.json for integration tests."""
    return load_race_index()


@pytest.fixture
def sample_races():
    """Minimal set of fake races for unit tests."""
    return [
        {"slug": "race-a", "name": "Race A", "month": "June", "region": "West",
         "tier": 1, "overall_score": 90, "location": "CO", "distance_mi": 200,
         "tagline": "The best race."},
        {"slug": "race-b", "name": "Race B", "month": "June", "region": "South",
         "tier": 2, "overall_score": 70, "location": "TX", "distance_mi": 100},
        {"slug": "race-c", "name": "Race C", "month": "March", "region": "South",
         "tier": 3, "overall_score": 55, "location": "GA", "distance_mi": 60},
        {"slug": "race-d", "name": "Race D", "month": "September", "region": "Europe",
         "tier": 1, "overall_score": 85, "location": "UK", "distance_mi": 150},
        {"slug": "race-e", "name": "Race E", "month": "March", "region": "West",
         "tier": 4, "overall_score": 40, "location": "CA", "distance_mi": 50},
    ]


# ── classify_blog_slug ──


def test_classify_roundup_slug():
    assert classify_blog_slug("roundup-march-2026") == "roundup"


def test_classify_recap_slug():
    assert classify_blog_slug("unbound-200-recap") == "recap"


def test_classify_preview_slug():
    assert classify_blog_slug("unbound-200") == "preview"


def test_classify_roundup_tier_slug():
    assert classify_blog_slug("roundup-tier-1-2026") == "roundup"


# ── filter_by_month ──


def test_filter_by_month_matches(sample_races):
    result = filter_by_month(sample_races, 2026, 6)
    assert len(result) == 2
    slugs = {r["slug"] for r in result}
    assert slugs == {"race-a", "race-b"}


def test_filter_by_month_no_matches(sample_races):
    result = filter_by_month(sample_races, 2026, 12)
    assert result == []


def test_filter_by_month_invalid():
    assert filter_by_month([], 2026, 0) == []
    assert filter_by_month([], 2026, 13) == []


def test_filter_by_month_case_insensitive(sample_races):
    """Month matching should be case-insensitive."""
    races = [{"slug": "x", "month": "JUNE"}]
    result = filter_by_month(races, 2026, 6)
    assert len(result) == 1


# ── filter_by_region ──


def test_filter_by_region_southeast(sample_races):
    result = filter_by_region(sample_races, "southeast")
    assert len(result) == 2
    slugs = {r["slug"] for r in result}
    assert slugs == {"race-b", "race-c"}


def test_filter_by_region_europe(sample_races):
    result = filter_by_region(sample_races, "europe")
    assert len(result) == 1
    assert result[0]["slug"] == "race-d"


def test_filter_by_region_invalid(sample_races):
    result = filter_by_region(sample_races, "nonexistent")
    assert result == []


def test_filter_by_region_west(sample_races):
    result = filter_by_region(sample_races, "west")
    assert len(result) == 2


# ── filter_by_tier ──


def test_filter_by_tier_1(sample_races):
    result = filter_by_tier(sample_races, 1)
    assert len(result) == 2
    slugs = {r["slug"] for r in result}
    assert slugs == {"race-a", "race-d"}


def test_filter_by_tier_4(sample_races):
    result = filter_by_tier(sample_races, 4)
    assert len(result) == 1
    assert result[0]["slug"] == "race-e"


def test_filter_by_tier_empty(sample_races):
    result = filter_by_tier(sample_races, 99)
    assert result == []


# ── build_roundup_stats ──


def test_stats_count(sample_races):
    stats = build_roundup_stats(sample_races)
    assert stats["count"] == 5


def test_stats_avg_score(sample_races):
    stats = build_roundup_stats(sample_races)
    expected = round((90 + 70 + 55 + 85 + 40) / 5)
    assert stats["avg_score"] == expected


def test_stats_tier_breakdown(sample_races):
    stats = build_roundup_stats(sample_races)
    assert stats["tier_breakdown"][1] == 2
    assert stats["tier_breakdown"][2] == 1
    assert stats["tier_breakdown"][3] == 1
    assert stats["tier_breakdown"][4] == 1


def test_stats_empty():
    stats = build_roundup_stats([])
    assert stats["count"] == 0
    assert stats["avg_score"] == 0
    assert stats["tier_breakdown"] == {}


# ── build_race_card_html ──


def test_card_contains_name(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "Race A" in html


def test_card_contains_tier(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "T1" in html
    assert "Elite" in html


def test_card_contains_score(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "90/100" in html


def test_card_contains_profile_link(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "/race/race-a/" in html


def test_card_contains_tagline(sample_races):
    html = build_race_card_html(sample_races[0])
    assert "The best race." in html


def test_card_without_tagline(sample_races):
    html = build_race_card_html(sample_races[1])
    assert "gg-roundup-tagline" not in html


# ── generate_roundup_html ──


def test_roundup_has_doctype(sample_races):
    html = generate_roundup_html(
        "Test Title", "Test Subtitle", "Intro text.",
        sample_races, "roundup-test", "Test Category"
    )
    assert "<!DOCTYPE html>" in html


def test_roundup_has_title(sample_races):
    html = generate_roundup_html(
        "March 2026 Calendar", "12 Races", "Intro.",
        sample_races, "roundup-march-2026", "Monthly Calendar"
    )
    assert "March 2026 Calendar" in html


def test_roundup_has_jsonld(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "application/ld+json" in html
    assert '"@type":"Article"' in html


def test_roundup_has_og_tags(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "og:title" in html
    assert "og:description" in html
    assert "og:url" in html


def test_roundup_has_canonical(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert 'rel="canonical"' in html
    assert "/blog/roundup-test/" in html


def test_roundup_has_stats_bar(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "gg-roundup-stats-bar" in html
    assert "5 Races" in html


def test_roundup_has_race_cards(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "gg-roundup-card" in html
    # All 5 races should have cards
    for r in sample_races:
        assert r["name"] in html


def test_roundup_has_cta(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Cat"
    )
    assert "Explore All 328 Races" in html
    assert "/gravel-races/" in html


def test_roundup_has_category_tag(sample_races):
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", sample_races, "roundup-test", "Monthly Calendar"
    )
    assert "Monthly Calendar" in html


def test_roundup_escapes_html():
    """Verify HTML special chars are escaped."""
    races = [{"slug": "x", "name": "Race <script>", "tier": 1, "overall_score": 50,
              "location": "CO", "month": "June"}]
    html = generate_roundup_html(
        "Test", "Sub", "Intro.", races, "roundup-test", "Cat"
    )
    assert "&lt;script&gt;" in html
    assert "<script>" not in html.split("</head>")[1]


# ── Integration: load_race_index ──


def test_load_race_index_returns_list(race_index):
    assert isinstance(race_index, list)
    assert len(race_index) > 300


def test_race_index_has_required_fields(race_index):
    r = race_index[0]
    assert "slug" in r
    assert "name" in r
    assert "tier" in r
    assert "month" in r
    assert "region" in r


# ── Integration: filter on real data ──


def test_filter_by_month_june_real(race_index):
    result = filter_by_month(race_index, 2026, 6)
    assert len(result) >= 3, "Expected at least 3 races in June"


def test_filter_by_tier_1_real(race_index):
    result = filter_by_tier(race_index, 1)
    assert len(result) >= 3, "Expected at least 3 T1 races"


def test_filter_by_region_west_real(race_index):
    result = filter_by_region(race_index, "west")
    assert len(result) >= 3, "Expected at least 3 West races"


# ── Slug format validation ──


def test_monthly_slug_format():
    """Monthly slugs should be roundup-{month}-{year}."""
    slug = f"roundup-{MONTH_NAMES[3].lower()}-2026"
    assert slug == "roundup-march-2026"
    assert classify_blog_slug(slug) == "roundup"


def test_regional_slug_format():
    slug = "roundup-southeast-spring-2026"
    assert classify_blog_slug(slug) == "roundup"


def test_tier_slug_format():
    slug = "roundup-tier-1-2026"
    assert classify_blog_slug(slug) == "roundup"
