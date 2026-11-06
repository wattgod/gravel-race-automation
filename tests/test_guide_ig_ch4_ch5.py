"""Tests for the rebuilt Chapter 4-5 handbook charts (wordpress/guide_ig/ch4_ch5.py)."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from guide_ig import ch4_ch5  # noqa: E402

KEY_NUMBERS = {
    "ch4-execution-gap": ["95→55", "% FTP", "Chased watts", "83-85%", "Built on"],
    "ch4-traffic-light": ["GREEN", "YELLOW", "RED", "Slept 7+ hrs", "Execute as planned"],
    "ch4-recovery-dash": ["7.2", "65", "rMSSD", "Target 7+ hours", "GO"],
    "ch4-sleep-debt": ["7", "8.5 h short", "1.5 h banked", "−1.5", "8 h need"],
    "ch5-fueling-timeline": ["75", "T-3 hrs", "600-800 cal", "500-750ml/hr", 'type="time"'],
    "ch5-bonk-math": ["600g", "~2,000", "4,000+", "24 gels", 'type="range"'],
    "ch5-hydration-calc": ["3,750", "750 mg", "4,500 mg total", "~1.3", 'type="range"'],
    "ch5-glycogen-gauge": ["35", "100%", "65%", "25%", "5%", "Built on"],
    "ch5-macro-split": ["55-65%", "15-20%", "20-30%", "420-700 g a day", "112-154 g a day"],
    "ch5-calorie-burn": ["4,580", "700", "1,350", "2,530", "3,600", "2,180"],
}

GLYPH = ["ch4-execution-gap", "ch4-traffic-light", "ch4-recovery-dash", "ch4-sleep-debt",
         "ch5-glycogen-gauge", "ch5-calorie-burn"]
SCRUB = {"ch4-execution-gap": 6, "ch4-sleep-debt": 7, "ch5-glycogen-gauge": 7, "ch5-calorie-burn": 8}


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


@pytest.mark.parametrize("asset", GLYPH)
def test_glyph_cards_have_endure_footer(asset):
    out = render(asset)
    assert "Built on" in out and "endurelabs.app" in out and "gg-eg" in out


@pytest.mark.parametrize("asset", sorted(SCRUB))
def test_scrub_plots_are_sliders(asset):
    out = render(asset)
    assert f'data-eg-n="{SCRUB[asset]}"' in out
    assert 'role="slider"' in out and "aria-valuetext" in out and 'tabindex="0"' in out
    assert 'aria-live="polite"' in out


@pytest.mark.parametrize("asset", sorted(SCRUB))
def test_data_island_is_valid_and_escaped(asset):
    import json
    out = render(asset)
    m = re.search(r'<script type="application/json" class="gg-eg-data">(.*?)</script>', out, re.S)
    assert m, asset
    assert "</" not in m.group(1)
    json.loads(m.group(1))


def test_execution_gap_default_numbers():
    import json
    out = render("ch4-execution-gap")
    data = json.loads(re.search(r'gg-eg-data">(.*?)</script>', out, re.S).group(1))
    assert data["plan"] == 85 and data["act"] == [95, 78, 55, 84, 83, 85]
    assert 'aria-pressed="true">Chased watts' in out


def test_sleep_debt_net_matches_round_one():
    assert ch4_ch5.render_sleep_debt({})  # renders
    hrs = [a for _d, a in ch4_ch5._SLEEP]
    need = ch4_ch5._SLEEP_NEED
    debt = sum(need - a for a in hrs if a < need)
    surplus = sum(a - need for a in hrs if a > need)
    assert (debt, surplus, debt - surplus) == (8.5, 1.5, 7.0)


def test_glycogen_model_reproduces_both_curves():
    out = render("ch5-glycogen-gauge")
    assert 'value="75"' in out  # default carbs per hour = the 75 g/hr curve
    assert ch4_ch5._GLY_FED[-1] == (6, 35) and ch4_ch5._GLY_UNFED[-1] == (6, 5)
    assert 'data-eg-def="6"' in out


def test_areas_split_at_target_crossing():
    parts = ch4_ch5._areas([0, 10, 20], [30, 10, 30], 20)
    assert [s for s, _ in parts] == [1, -1, 1]


def test_recovery_uses_guide_thresholds():
    assert ch4_ch5.JS.count("sleep < 5") >= 1 and "sore < 2" in ch4_ch5.JS and "sore < 3" in ch4_ch5.JS


def test_readiness_marks_by_shape():
    assert ".gg-ig-c-mk--go{border-radius:50%" in ch4_ch5.CSS
    assert ".gg-ig-c-mk--caution{border-radius:50%" in ch4_ch5.CSS and ".gg-ig-c-mk--rest{" in ch4_ch5.CSS


def test_hydration_heat_covers_full_slider_and_sodium_per_hour():
    out = render("ch5-hydration-calc")
    assert 'max="110"' in out and "Sodium / hr" in out
    js = ch4_ch5.JS
    assert "temp <= 90 ? Math.max(0, (temp - 60) * 5) : 150 + (temp - 90) * 2.5" in js
    assert "sodiumRate" in js and "sodiumtotal" in js

    def rate(temp, inten):
        heat = max(0, (temp - 60) * 5) if temp <= 90 else 150 + (temp - 90) * 2.5
        return 500 + heat + (inten - 1) * 12.5

    assert rate(80, 3) == 625  # round-1 default
    assert rate(90, 3) < rate(100, 3) < rate(110, 3)  # 90-110 F now changes the answer
    for t in range(50, 111, 5):
        for i in range(1, 6):
            assert 500 <= rate(t, i) <= 750  # inside the guide's 500-750 ml/hr
            assert 500 <= rate(t, i) * 1.2 <= 1000  # inside 500-1000 mg/hr


def test_bonk_gels_follow_total():
    out = render("ch5-bonk-math")
    assert out.count('class="gg-ig-c-gel"') == 24 and "data-gels" in out


def test_macro_grams_from_g_per_kg():
    assert ch4_ch5._grams((6, 10), 70) == "420-700 g a day"
    assert ch4_ch5._grams((1.6, 2.2), 70) == "112-154 g a day"
    assert "No g/kg range" in ch4_ch5._grams(None, 70)
