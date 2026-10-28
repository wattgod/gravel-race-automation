"""Tests for the rebuilt Chapter 4-5 handbook charts (wordpress/guide_ig/ch4_ch5.py)."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from guide_ig import ch4_ch5  # noqa: E402

KEY_NUMBERS = {
    "ch4-execution-gap": ["95%", "55%", "85", "83-85%"],
    "ch4-traffic-light": ["GREEN", "YELLOW", "RED", "Slept 7+ hrs"],
    "ch4-recovery-dash": ["7.2", "65", "3", "rMSSD"],
    "ch4-sleep-debt": ["7", "8.5 h short", "1.5 h banked", "−1.5"],
    "ch5-fueling-timeline": ["75", "T-3 hrs", "600-800 cal", "500-750ml/hr"],
    "ch5-bonk-math": ["600g", "~2,000", "4,000+", "24 gels"],
    "ch5-hydration-calc": ["3,750", "4,500 mg", "~1.3", 'type="range"'],
    "ch5-glycogen-gauge": ["100%", "65%", "25%", "5%", "35%"],
    "ch5-macro-split": ["55-65%", "15-20%", "20-30%"],
    "ch5-calorie-burn": ["4,580", "700", "1,350", "2,530", "3,600"],
}


def render(asset, **kw):
    block = {"type": "image", "asset_id": asset, "caption": "Cap line", "alt": "x"}
    block.update(kw)
    return ch4_ch5.RENDERERS[asset](block)


def test_all_assets_registered():
    assert set(ch4_ch5.RENDERERS) == set(KEY_NUMBERS)


@pytest.mark.parametrize("asset", sorted(KEY_NUMBERS))
def test_renders_key_numbers(asset):
    out = render(asset)
    for needle in KEY_NUMBERS[asset]:
        assert needle in out, f"{asset} missing {needle}"
    assert "Cap line" in out
    assert out.count("Cap line") == 1


@pytest.mark.parametrize("asset", sorted(KEY_NUMBERS))
def test_no_inline_handlers(asset):
    assert not re.search(r"\son[a-z]+\s*=", render(asset), re.I)


@pytest.mark.parametrize("asset", sorted(KEY_NUMBERS))
def test_escapes_hostile_caption(asset):
    out = render(asset, caption='<script>alert(1)</script>')
    assert "<script>alert" not in out
    assert "&lt;script&gt;" in out


def test_escape_zero():
    assert ch4_ch5._e(0) == "0"
    assert ch4_ch5._e(None) == ""


def test_js_has_no_innerhtml():
    assert "innerHTML" not in ch4_ch5.JS
    assert "insertAdjacentHTML" not in ch4_ch5.JS


def test_css_scoped_and_no_hex():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", ch4_ch5.CSS)
    for sel in re.findall(r"(?m)^\.([a-z0-9_-]+)", ch4_ch5.CSS):
        assert sel.startswith("gg-ig-c"), sel


def test_no_hex_in_markup():
    for asset in KEY_NUMBERS:
        assert not re.search(r'style="[^"]*#[0-9a-fA-F]{3,6}', render(asset))
