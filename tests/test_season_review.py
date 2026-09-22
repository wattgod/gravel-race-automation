"""Tests for the season review page generator."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from generate_season_review import (  # noqa: E402
    FORMSUBMIT_URL,
    build_season_review_js,
    generate_season_review_page,
)


def page() -> str:
    return generate_season_review_page()


def test_has_ga4_and_header_js():
    html = page()
    assert "gtag" in html
    assert "gg-site-header" in html or "hamburger" in html.lower()


def test_noindex():
    assert 'name="robots" content="noindex, nofollow"' in page()


def test_honeypot_present():
    assert 'name="website" class="gg-apply-honeypot"' in page()


def test_submits_to_formsubmit_ajax():
    js = build_season_review_js()
    assert FORMSUBMIT_URL.startswith("https://formsubmit.co/ajax/")
    assert FORMSUBMIT_URL in js


def test_no_placeholders_left():
    assert not re.search(r"__[A-Z_]+__", build_season_review_js())


def test_no_innerhtml_in_js():
    assert "innerHTML" not in build_season_review_js()


def test_no_inline_handlers():
    assert not re.search(r"\son(click|submit|change|input)=", page())


def test_all_twelve_sections():
    html = page()
    for n in range(1, 13):
        assert f'gg-apply-section-title">{n}. ' in html


def test_sum_of_law_scores_never_shown_to_athlete():
    # Endure ruling: show the shape of the four scores, never the total.
    js = build_season_review_js()
    assert "/12" not in js.split("function formatSubmission")[0]
