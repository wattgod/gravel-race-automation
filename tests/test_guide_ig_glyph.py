"""Tests for the shared Endure Glyph kit (wordpress/guide_ig/glyph.py)."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

import guide_ig  # noqa: E402
from guide_ig import glyph  # noqa: E402


def test_bundle_leads_with_glyph_kit():
    assert guide_ig.CSS.startswith(glyph.CSS.strip()[:40]) or glyph.CSS in guide_ig.CSS
    assert "window.GGEG" in guide_ig.JS


def test_hex_only_in_token_block():
    rest = glyph.CSS.replace(glyph.TOKENS_CSS, "")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", rest)
    assert "#2563EB" in glyph.TOKENS_CSS  # cobalt


def test_css_scoped_to_glyph_card():
    for sel in re.findall(r"(?m)^([^@{}\n]+)\{", glyph.CSS):
        for part in sel.split(","):
            assert part.strip().startswith(".gg-eg"), part


def test_js_has_no_innerhtml_or_inline_handlers():
    assert "innerHTML" not in glyph.JS and "insertAdjacentHTML" not in glyph.JS
    assert "ontouch" not in glyph.JS


def test_escape_prints_zero_and_escapes():
    assert glyph.esc(0) == "0"
    assert glyph.esc(None) == ""
    assert "&lt;" in glyph.esc("<b>")


def test_safe_json_cannot_close_script():
    out = glyph.safe_json({"a": "</script><!--x"})
    assert "</script" not in out and "<!--" not in out
    assert json.loads(out.replace("<\\/", "</").replace("<\\!--", "<!--"))["a"] == "</script><!--x"


def test_card_footer_link_and_data_island():
    card = glyph.glyph_card("Name", glyph.readout("1", "u"), "<p>plot</p>", data={"x": "</script>"})
    assert 'href="https://endurelabs.app/?utm_source=gravelgod&amp;utm_medium=handbook' not in card  # raw & in href, per repo style
    assert "utm_campaign=guide-charts" in card
    assert 'target="_blank" rel="noopener"' in card
    assert "Built on" in card and "Endure Labs" in card
    island = re.search(r'<script type="application/json" class="gg-eg-data">(.*?)</script>', card, re.S).group(1)
    assert "</" not in island
    assert not glyph.glyph_card("N", "", "", foot=False).count("Built on")


def test_scrub_wrap_is_a_slider():
    out = glyph.scrub_wrap("c", "", 12, 9, "Scrub", "Week 10", mode="band")
    for needle in ('role="slider"', 'tabindex="0"', 'aria-valuemin="0"', 'aria-valuemax="11"',
                   'aria-valuenow="9"', 'aria-valuetext="Week 10"', 'data-eg-scrub="c"'):
        assert needle in out


def test_readout_is_live_region():
    card = glyph.glyph_card("N", glyph.readout("78", "fitness", "+3", "Week 10"), "")
    assert 'aria-live="polite"' in card


def test_capsule_and_meter():
    c = glyph.capsule("+28", "Form", "teal", "dotted")
    assert "gg-eg-cap--teal" in c and "gg-eg-cap--dotted" in c and "+28" in c
    m = glyph.meter(50, 100, tick=75)
    assert "width:50.0%" in m and "left:75.0%" in m


def test_mono_curve_passes_points_and_never_overshoots():
    pts = [(0, 0), (1, 10), (2, 10), (3, 30)]
    f = glyph.mono_curve(pts)
    for x, y in pts:
        assert f(x) == pytest.approx(y)
    assert all(0 <= f(x / 10) <= 30 for x in range(31))
    assert max(f(1 + x / 100) for x in range(101)) <= 10 + 1e-9
    assert len(glyph.mono_sample(pts, 5)) == 3 * 5 + 1


def test_scales():
    assert glyph.linear(0, 10, 0, 100)(5) == 50
    assert glyph.log_scale(1, 100, 0, 100)(10) == pytest.approx(50)
    assert glyph.line_path([(0, 0), (1, 2)]) == "M0.0,0.0 L1.0,2.0"
