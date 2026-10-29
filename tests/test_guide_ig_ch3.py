"""Tests for the rebuilt Chapter 3 handbook charts (wordpress/guide_ig/ch3.py)."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from guide_ig import ch3  # noqa: E402

IDS = {
    "ch3-supercompensation": ["REST = FASTER", "Training stress", "Supercompensation", "Detraining", "+70"],
    "ch3-zone-spectrum": ["Z2–Z4", "Active Recovery", "Neuromuscular", "106-120%", "121-150%", "138–263 W"],
    "ch3-pmc-chart": ["+28", "+40", "-19", "Race ready", "Chronic Training Load"],
    "ch3-training-phases": ["weeks", "PEAK / TAPER", "Reduce volume 40%", "Volume", "Intensity"],
    "ch3-power-duration": ["195 W", "380 W", "250 W", "138–188 W", "225–263 W", "78% of FTP"],
    "ch3-gantt-season": ["6 blocks", "Off-Season", "Transition", "Mid Aug – Oct", "Base 2"],
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
    # Glyph curve: 201 samples along the monotone cubic through the 13 data points
    path = re.search(r'class="gg-ig-b-eg-hero gg-ig-b-eg-hero--ride" d="([^"]+)"', out).group(1)
    assert path.count("L") == 200
    assert len(ch3._PD) == 13


import json  # noqa: E402

GLYPH_NEW = ["ch3-supercompensation", "ch3-zone-spectrum", "ch3-training-phases", "ch3-gantt-season", "ch3-before-after"]


@pytest.mark.parametrize("asset_id", GLYPH_NEW)
def test_new_cards_have_valid_escaped_data_island_and_footer(asset_id):
    out = render(asset_id, caption='</script><b>"')
    m = re.search(r'<script type="application/json" class="gg-eg-data">(.*?)</script>', out, re.S)
    assert m and json.loads(m.group(1))
    assert "Built on" in out and "endurelabs.app" in out
    assert 'aria-live="polite"' in out


def test_supercompensation_scrub_slider_and_default():
    out = render("ch3-supercompensation")
    assert 'role="slider"' in out and 'data-eg-n="21"' in out and 'aria-valuenow="11"' in out
    assert 'type="range"' in out and "Lands on the overshoot: +70 above baseline" in out


def test_supercompensation_verdict_reads_the_curve():
    assert ch3._sc_verdict(4) == "Lands in the fatigue hole: 120 below baseline"
    assert ch3._sc_verdict(11).startswith("Lands on the overshoot")
    assert ch3._sc_verdict(8) == "Lands at baseline: no boost yet"
    assert "faded" in ch3._sc_verdict(19)
    assert len(ch3._SC_LVL) == 21 and ch3._sc_stage(11) == "Supercompensation"


def test_zone_watts_follow_ftp():
    assert [ch3._zn_w(i, 250) for i in (0, 1, 2, 3, 6)] == ["≤ 138 W", "138–188 W", "190–225 W", "228–263 W", "Max"]
    assert ch3._zn_w(3, 300) == "273–315 W"
    out = render("ch3-zone-spectrum")
    assert 'data-eg-in="ftp"' in out


def test_season_labels_match_round_one_and_shift_with_race_month():
    s = ch3._gt_start(7)
    assert [ch3._gt_dates(s, a, b) for _, a, b, _, _ in ch3._GANTT] == [
        "Nov – mid Dec", "Mid Dec – Mar", "Apr – May", "Jun – mid Aug", "Mid Aug – Oct", "Nov",
    ]
    s5 = ch3._gt_start(4)  # A race in May
    assert ch3._MONTHS12[s5] == "Aug"
    assert ch3._gt_dates(s5, 7, 9.5) == "Mar – mid May"
    assert '<select' in render("ch3-gantt-season")


def test_phases_columns_and_scrub():
    out = render("ch3-training-phases")
    assert out.count("gg-ig-b-eg-col ") == 12
    assert 'data-eg-n="12"' in out and 'role="slider"' in out


def test_before_after_changes_in_capsules():
    out = render("ch3-before-after")
    for needle in ("+39%", "-27 bpm", "-7 pts", "+40 pts"):
        assert needle in out
    assert out.count('class="gg-eg-tick"') == 6
