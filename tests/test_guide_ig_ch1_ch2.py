"""Tests for the rebuilt Handbook charts, chapters 1-2 (wordpress/guide_ig/ch1_ch2.py)."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from guide_ig import ch1_ch2  # noqa: E402

BLOCK = {"caption": "A caption line.", "alt": "An alt summary"}

KEY_NUMBERS = {
    "ch1-gear-essentials": ["45mm+", "Bike Frame", "Hydration"],
    "ch1-rider-grid": ["100-160W", "280-400W", "12-20 hrs/wk", "Podium"],
    "ch1-hierarchy-of-speed": ["70%", "20%", "8%", "1.5%", "0.5%"],
    "ch1-gear-weight": ["14.1", "8.5<small>", "0.4<small>"],
    "ch2-scoring-dimensions": ["Unbound 200", "Mid South", "Leadville", "Field Depth"],
    "ch2-tier-distribution": ["328", "154", "47%", "25"],
    "ch2-course-profile": ["100 MI", "2,800", "14% grade"],
    "ch2-field-scatter": ["4,000", "Unbound 200", "80 at the smallest"],
    "ch2-race-table": ["Belgian Waffle Ride", "12,600 ft", "94"],
}


def test_all_assets_registered():
    assert set(ch1_ch2.RENDERERS) == set(KEY_NUMBERS)


@pytest.mark.parametrize("asset_id", sorted(KEY_NUMBERS))
def test_renders_key_numbers(asset_id):
    out = ch1_ch2.RENDERERS[asset_id](BLOCK)
    for needle in KEY_NUMBERS[asset_id]:
        assert needle in out, f"{asset_id} missing {needle}"
    assert "A caption line." in out
    assert out.count("A caption line.") == 1
    assert "gg-ig-a__head" in out


@pytest.mark.parametrize("asset_id", sorted(KEY_NUMBERS))
def test_no_inline_handlers_or_flip(asset_id):
    out = ch1_ch2.RENDERERS[asset_id](BLOCK)
    assert not re.search(r"\son[a-z]+\s*=", out)
    assert "Tap to flip" not in out


@pytest.mark.parametrize("asset_id", sorted(KEY_NUMBERS))
def test_hostile_strings_escaped(asset_id):
    hostile = '<script>alert(1)</script>"'
    out = ch1_ch2.RENDERERS[asset_id]({"caption": hostile, "alt": hostile})
    assert "<script>alert" not in out
    assert "&lt;script&gt;" in out


def test_esc_zero():
    assert ch1_ch2._e(0) == "0"


def test_hierarchy_data_matches_alt():
    assert [h[1] for h in ch1_ch2.HIERARCHY] == ["70%", "20%", "8%", "1.5%", "0.5%"]


def test_tier_counts_sum():
    assert sum(t[1] for t in ch1_ch2.TIERS) == 328


def test_gear_weight_buttons_work_statically():
    out = ch1_ch2.RENDERERS["ch1-gear-weight"](BLOCK)
    assert out.count("<button") == 8
    assert out.count('aria-pressed="true"') == 7
    assert out.count('aria-pressed="false"') == 1


def test_css_has_no_hex_and_is_prefixed():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", ch1_ch2.CSS)
    selectors = re.findall(r"(?:^|[},])\s*(\.[a-zA-Z][a-zA-Z0-9_-]*)", ch1_ch2.CSS, flags=re.M)
    assert selectors
    assert all(s.startswith(".gg-ig-a") for s in selectors), [s for s in selectors if not s.startswith(".gg-ig-a")]


def test_js_is_safe():
    js = ch1_ch2.JS
    assert "innerHTML" not in js
    assert "insertAdjacentHTML" not in js
    assert "gtag" not in js and "dataLayer" not in js
