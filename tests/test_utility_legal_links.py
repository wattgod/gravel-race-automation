"""Regression guards for legal links on custom utility-page footers."""

import sys
from pathlib import Path


WORDPRESS_DIR = Path(__file__).resolve().parents[1] / "wordpress"
sys.path.insert(0, str(WORDPRESS_DIR))

from generate_methodology import build_footer  # noqa: E402
from generate_tier_hubs import build_hub_page  # noqa: E402
from generate_vs_pages import build_vs_page  # noqa: E402


def _assert_legal_links(html: str) -> None:
    assert 'href="/privacy/"' in html
    assert 'href="/terms/"' in html


def test_methodology_footer_links_to_both_legal_pages() -> None:
    _assert_legal_links(build_footer())


def test_tier_hub_footer_links_to_both_legal_pages() -> None:
    race = {"slug": "test-race", "name": "Test Race", "score": 80, "tier": 1,
            "location": "Colorado", "month": "June", "tagline": "A real race."}
    _assert_legal_links(build_hub_page(1, [race], [race]))


def test_comparison_footer_links_to_both_legal_pages() -> None:
    race_a = {"slug": "race-a", "name": "Race A", "score": 80, "tier": 1,
              "location": "Colorado", "month": "June", "tagline": "Race A."}
    race_b = {"slug": "race-b", "name": "Race B", "score": 70, "tier": 2,
              "location": "Utah", "month": "July", "tagline": "Race B."}
    full = {"race": {"course": {}, "experience": {}, "logistics": {}}}
    _assert_legal_links(build_vs_page(race_a, race_b, full, full))
