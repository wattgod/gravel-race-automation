"""Tests for the rebuilt Chapter 3 handbook charts (wordpress/guide_ig/ch3.py)."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from guide_ig import ch3  # noqa: E402

IDS = {
    "ch3-supercompensation": ["REST = FASTER", "Training stress", "Supercompensation", "Detraining"],
    "ch3-zone-spectrum": ["Z2–Z4", "Active Recovery", "Neuromuscular", "106-120%", "121-150%"],
    "ch3-pmc-chart": ["+28", "+40", "-19", "RACE READY", "Chronic Training Load"],
    "ch3-training-phases": ["12 WEEKS", "PEAK / TAPER", "Reduce volume 40%", "VOLUME", "INTENSITY"],
    "ch3-power-duration": ["195 W", "380 W", "250 W", "138–188 W", "225–263 W", "78% of FTP"],
    "ch3-gantt-season": ["6 BLOCKS", "Off-Season", "Transition", "Mid Aug – Oct", "Base 2"],
    "ch3-before-after": ["+39%", "180W", "250W", "68 bpm", "Top 35%", "Bottom 25%"],
}


def render(asset_id, **extra):
    block = {"type": "image", "asset_id": asset_id, "caption": "A caption", "alt": "An alt"}
    block.update(extra)
    return ch3.RENDERERS[asset_id](block)


def test_registers_all_seven():
    assert set(ch3.RENDERERS) == set(IDS)


@pytest.mark.parametrize("asset_id", list(IDS))
def test_renders_key_numbers(asset_id):
    out = render(asset_id)
    for needle in IDS[asset_id]:
        assert needle in out, f"{asset_id} missing {needle!r}"
    assert "A caption" in out
    assert out.count("A caption") == 1


@pytest.mark.parametrize("asset_id", list(IDS))
def test_no_inline_handlers_or_innerhtml(asset_id):
    out = render(asset_id)
    assert not re.search(r"\son\w+\s*=", out)
    assert "innerHTML" not in ch3.JS and "insertAdjacentHTML" not in ch3.JS
    assert "innerHTML" not in out


@pytest.mark.parametrize("asset_id", list(IDS))
def test_escapes_hostile_strings(asset_id):
    evil = '<script>alert(1)</script>"x'
    out = render(asset_id, caption=evil, alt=evil)
    assert "<script>alert(1)" not in out
    assert "&lt;script&gt;" in out


@pytest.mark.parametrize("asset_id", list(IDS))
def test_charts_have_accessible_label(asset_id):
    out = render(asset_id)
    assert 'role="img"' in out or "aria-label=" in out


def test_escape_helper_prints_zero():
    assert ch3._e(0) == "0"
    assert ch3._e(None) == ""


def test_css_has_no_hex_and_is_prefixed():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", ch3.CSS)
    for sel in re.findall(r"(?m)^([^@{}\n]+)\{", ch3.CSS):
        for part in sel.split(","):
            assert part.strip().startswith(".gg-ig-b-"), part


def test_svg_attributes_use_no_var():
    for asset_id in IDS:
        out = render(asset_id)
        assert not re.search(r'(fill|stroke)="var\(', out)


def test_power_duration_curve_has_all_points():
    out = render("ch3-power-duration")
    # 13 data points -> 12 cubic segments, nothing stray
    path = re.search(r'class="gg-ig-b-pd-line" d="([^"]+)"', out).group(1)
    assert path.count("C") == 12
    assert len(ch3._PD) == 13
