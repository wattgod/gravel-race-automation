"""Rider Score — RT audience-score mechanic in the hero (northstar P1.4).

Hard rule: a number only ever displays from real, threshold-gated submitted
ratings. Below threshold the cell is an honest ask that links to the review
form. No synthetic/sentiment-derived scores.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_neo_brutalist import (
    build_hero,
    build_racer_reviews,
    RACER_RATING_THRESHOLD,
)


def _rd(racer_rating=None):
    return {
        "slug": "test-race",
        "name": "Test Race",
        "overall_score": 88,
        "tier_label": "TIER 1",
        "vitals": {"location": "Emporia, KS", "month": "May"},
        "racer_rating": racer_rating or {},
    }


class TestEmptyState:
    def test_no_ratings_shows_ask_not_number(self):
        html = build_hero(_rd())
        assert "gg-hero-rider-empty" in html
        assert "RATE IT" in html
        assert 'href="#racer-reviews"' in html
        assert 'data-cta="hero_rate_race"' in html

    def test_below_threshold_still_ask(self):
        rr = {"total_ratings": max(RACER_RATING_THRESHOLD - 1, 0),
              "star_average": 4.8}
        html = build_hero(_rd(rr))
        assert "gg-hero-rider-empty" in html
        assert "96" not in html.split("gg-hero-score--rider")[1]

    def test_anchor_target_exists_in_reviews_section(self):
        html = build_racer_reviews(_rd())
        assert 'id="racer-reviews"' in html


class TestScoredState:
    def test_threshold_met_shows_score(self):
        rr = {"total_ratings": RACER_RATING_THRESHOLD, "star_average": 4.6,
              "total_reviews": 0, "reviews": []}
        html = build_hero(_rd(rr))
        assert "gg-hero-rider-empty" not in html
        assert f"{round(4.6 * 20)}" in html  # 92
        assert f"{RACER_RATING_THRESHOLD} RATINGS" in html

    def test_star_average_maps_to_100_scale(self):
        rr = {"total_ratings": RACER_RATING_THRESHOLD, "star_average": 5.0}
        html = build_hero(_rd(rr))
        assert ">100<" in html

    def test_missing_star_average_never_crashes(self):
        rr = {"total_ratings": RACER_RATING_THRESHOLD}
        html = build_hero(_rd(rr))
        assert "gg-hero-rider-empty" in html


class TestLayout:
    def test_both_scores_in_scores_wrapper(self):
        html = build_hero(_rd())
        assert "gg-hero-scores" in html
        assert "LAB SCORE" in html
        assert "RIDER SCORE" in html


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
