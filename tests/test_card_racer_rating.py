"""
Tests for racer rating display on race cards across all generators.

Validates:
1. State hub cards show dual-score (GG + Racer) with correct classes
2. Homepage featured cards show GG + RACER columns
3. Series hub event cards show GG/RACER labels
4. Empty state shows "NO RATINGS" (not a fake CTA like "RATE IT")
5. Populated state shows percentage and rating count
6. Threshold uses shared RACER_RATING_THRESHOLD from brand_tokens
"""

import sys
from pathlib import Path

import pytest

# Ensure wordpress/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from brand_tokens import COLORS, RACER_RATING_THRESHOLD
from generate_state_hubs import build_race_cards
from generate_series_hubs import build_event_card


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture
def race_with_racer_rating():
    """Race index entry with racer rating above threshold."""
    return {
        "slug": "test-race",
        "name": "Test Gravel 100",
        "tier": 2,
        "overall_score": 72,
        "location": "Emporia, Kansas",
        "tagline": "A solid gravel race.",
        "distance_mi": 100,
        "elevation_ft": 5000,
        "month": "June",
        "racer_pct": 87,
        "racer_total": 25,
    }


@pytest.fixture
def race_without_racer_rating():
    """Race index entry with no racer rating data."""
    return {
        "slug": "no-rating-race",
        "name": "No Rating Race",
        "tier": 3,
        "overall_score": 55,
        "location": "Nowhere, Idaho",
        "tagline": "Nobody rated this yet.",
        "distance_mi": 60,
        "elevation_ft": 3000,
        "month": "August",
    }


@pytest.fixture
def race_below_threshold():
    """Race index entry with racer rating below threshold."""
    return {
        "slug": "low-rating-race",
        "name": "Low Rating Race",
        "tier": 3,
        "overall_score": 48,
        "location": "Smallville, Ohio",
        "tagline": "Barely rated.",
        "distance_mi": 40,
        "elevation_ft": 1500,
        "month": "July",
        "racer_pct": 90,
        "racer_total": 1,  # Below threshold
    }


# ── State Hub Card Tests ─────────────────────────────────────


class TestStateHubCards:
    """Tests for build_race_cards() in generate_state_hubs.py."""

    def test_card_has_dual_score_layout(self, race_with_racer_rating):
        html = build_race_cards([race_with_racer_rating])
        assert "gg-state-card-scores" in html
        assert "gg-state-card-gg" in html
        assert "gg-state-card-racer" in html

    def test_card_shows_gg_score_with_label(self, race_with_racer_rating):
        html = build_race_cards([race_with_racer_rating])
        assert ">72</div>" in html
        assert "gg-state-card-score-label" in html
        assert ">GG</div>" in html

    def test_card_shows_racer_rating_when_populated(self, race_with_racer_rating):
        html = build_race_cards([race_with_racer_rating])
        assert "87%" in html
        assert "25 RATINGS" in html
        assert "gg-state-card-racer--empty" not in html

    def test_card_shows_no_ratings_when_empty(self, race_without_racer_rating):
        html = build_race_cards([race_without_racer_rating])
        assert "gg-state-card-racer--empty" in html
        assert "NOT YET RATED" in html
        # Must NOT say "RATE IT" — that's a lie (no rating form exists)
        assert "RATE IT" not in html

    def test_card_shows_no_ratings_below_threshold(self, race_below_threshold):
        html = build_race_cards([race_below_threshold])
        assert "gg-state-card-racer--empty" in html
        assert "NOT YET RATED" in html
        # The 90% should NOT be shown since below threshold
        assert "90%" not in html

    def test_card_racer_color_is_teal(self, race_with_racer_rating):
        html = build_race_cards([race_with_racer_rating])
        assert COLORS["teal"] in html

    def test_card_links_to_race_profile(self, race_with_racer_rating):
        html = build_race_cards([race_with_racer_rating])
        assert 'href="/race/test-race/"' in html

    def test_threshold_matches_brand_tokens(self):
        """RACER_RATING_THRESHOLD must come from brand_tokens, not be hardcoded."""
        import generate_state_hubs
        source = Path(generate_state_hubs.__file__).read_text()
        assert "RACER_RATING_THRESHOLD" in source
        # Must NOT have hardcoded >= 5 for racer threshold
        assert "rr_total >= 5" not in source


# ── Homepage Card Tests ──────────────────────────────────────


class TestHomepageCards:
    """Tests for racer rating in homepage featured race cards."""

    def test_featured_card_has_score_columns(self):
        from generate_homepage import build_featured_races, load_race_index
        race_index = load_race_index()
        html = build_featured_races(race_index)
        assert "gg-hp-scores" in html
        assert "gg-hp-score-col" in html
        assert "gg-hp-score-label" in html

    def test_featured_card_has_gg_label(self):
        from generate_homepage import build_featured_races, load_race_index
        race_index = load_race_index()
        html = build_featured_races(race_index)
        assert ">GG</span>" in html

    def test_featured_card_has_racer_label(self):
        from generate_homepage import build_featured_races, load_race_index
        race_index = load_race_index()
        html = build_featured_races(race_index)
        assert ">RACER</span>" in html

    def test_featured_card_empty_racer_shows_dash(self):
        """When no racer rating data exists, show mdash not a fake CTA."""
        from generate_homepage import build_featured_races, load_race_index
        race_index = load_race_index()
        html = build_featured_races(race_index)
        # All races currently have no racer_pct in the index, so all show empty
        assert "gg-hp-racer-score--empty" in html
        assert "&mdash;" in html

    def test_homepage_threshold_matches_brand_tokens(self):
        """Homepage must use shared RACER_RATING_THRESHOLD, not hardcoded value."""
        from generate_homepage import RACER_RATING_THRESHOLD as hp_threshold
        assert hp_threshold == RACER_RATING_THRESHOLD
        import generate_homepage
        source = Path(generate_homepage.__file__).read_text()
        assert "rr_total >= 5" not in source


# ── Series Hub Card Tests ────────────────────────────────────


class TestSeriesHubCards:
    """Tests for racer rating in series hub event cards."""

    def test_event_card_shows_gg_label(self):
        event = {"name": "BWR California", "slug": "bwr-california",
                 "location": "San Marcos, CA", "month": "May",
                 "has_profile": True}
        race_lookup = {"bwr-california": {
            "tier": 2, "overall_score": 78,
            "racer_pct": 91, "racer_total": 40,
        }}
        html = build_event_card(event, race_lookup)
        assert ">GG</small>" in html
        assert "78" in html

    def test_event_card_shows_racer_when_populated(self):
        event = {"name": "BWR California", "slug": "bwr-california",
                 "location": "San Marcos, CA", "month": "May",
                 "has_profile": True}
        race_lookup = {"bwr-california": {
            "tier": 2, "overall_score": 78,
            "racer_pct": 91, "racer_total": 40,
        }}
        html = build_event_card(event, race_lookup)
        assert "91%" in html
        assert ">RACER</small>" in html
        assert "gg-series-event-racer--empty" not in html

    def test_event_card_shows_rate_label_when_empty(self):
        event = {"name": "BWR Kansas", "slug": "bwr-kansas",
                 "location": "Lawrence, KS", "month": "June",
                 "has_profile": True}
        race_lookup = {"bwr-kansas": {
            "tier": 3, "overall_score": 55,
        }}
        html = build_event_card(event, race_lookup)
        assert "gg-series-event-racer--empty" in html
        assert ">RACER</small>" in html  # Series uses "RACER" label

    def test_event_card_below_threshold(self):
        event = {"name": "BWR Utah", "slug": "bwr-utah",
                 "location": "Cedar City, UT", "month": "September",
                 "has_profile": True}
        race_lookup = {"bwr-utah": {
            "tier": 3, "overall_score": 60,
            "racer_pct": 95, "racer_total": 1,  # Below threshold
        }}
        html = build_event_card(event, race_lookup)
        assert "gg-series-event-racer--empty" in html
        # Must NOT show 95% since below threshold
        assert "95%" not in html

    def test_event_card_no_profile_no_scores(self):
        """Events without profiles should not show any scores."""
        event = {"name": "BWR Asheville", "slug": None,
                 "location": "Asheville, NC", "month": "October",
                 "has_profile": False}
        html = build_event_card(event, {})
        assert "gg-series-event-score" not in html
        assert "gg-series-event-racer" not in html

    def test_series_threshold_matches_brand_tokens(self):
        """Series hub must use shared RACER_RATING_THRESHOLD, not hardcoded value."""
        import generate_series_hubs
        source = Path(generate_series_hubs.__file__).read_text()
        assert "RACER_RATING_THRESHOLD" in source
        assert "rr_total >= 5" not in source


# ── Cross-Generator Consistency ──────────────────────────────


class TestCrossGeneratorConsistency:
    """Verify all generators use the same threshold and data fields."""

    def test_all_generators_import_shared_threshold(self):
        """Every generator with racer rating must import from brand_tokens."""
        for gen_name in ["generate_state_hubs", "generate_homepage", "generate_series_hubs"]:
            module = __import__(gen_name)
            source = Path(module.__file__).read_text()
            assert "from brand_tokens import" in source, f"{gen_name} doesn't import from brand_tokens"
            assert "RACER_RATING_THRESHOLD" in source, f"{gen_name} doesn't use RACER_RATING_THRESHOLD"

    def test_no_generator_hardcodes_threshold(self):
        """No generator should have 'rr_total >= 5' or similar hardcoded threshold."""
        for gen_name in ["generate_state_hubs", "generate_homepage", "generate_series_hubs",
                         "generate_neo_brutalist"]:
            module = __import__(gen_name)
            source = Path(module.__file__).read_text()
            assert "rr_total >= 5" not in source, f"{gen_name} has hardcoded threshold >= 5"
            assert "racer_total >= 5" not in source, f"{gen_name} has hardcoded threshold >= 5"

    def test_no_dishonest_rate_it_cta(self):
        """No generator should say 'RATE IT' — no rating form exists yet."""
        for gen_name in ["generate_state_hubs", "generate_homepage", "generate_series_hubs"]:
            module = __import__(gen_name)
            source = Path(module.__file__).read_text()
            assert "RATE IT" not in source, (
                f"{gen_name} still has 'RATE IT' CTA — no rating form exists"
            )

    def test_dead_code_removed(self):
        """generate_neo_brutalist must not have orphaned racer panel code."""
        import generate_neo_brutalist
        source = Path(generate_neo_brutalist.__file__).read_text()
        assert "RACER_RATING_FORM_BASE" not in source, "Dead RACER_RATING_FORM_BASE constant"
        assert "def _build_racer_panel" not in source, "Dead _build_racer_panel function"
        assert "gg-dual-score" not in source, "Dead .gg-dual-score CSS"
        assert "gg-dual-panel" not in source, "Dead .gg-dual-panel CSS"
