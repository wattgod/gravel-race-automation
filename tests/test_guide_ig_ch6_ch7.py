"""Tests for the rebuilt chapter 6 and 7 Handbook charts."""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "wordpress"))

from guide_ig import ch6_ch7  # noqa: E402

KEYS = {
    "ch6-three-acts": ["Restraint", "Resilience", "Resolve", "0–40%", "75–100%"],
    "ch6-psych-phases": ["Honeymoon", "Dark Patch", "Final Push", "40–60%", "110%"],
    "ch7-race-week-countdown": ["MON", "RACE DAY", "600-800 cal", "Bed by 9 PM"],
    "ch7-weather-matrix": ["60–75°F", "Hot + extreme wind: do not race", "Dangerous"],
}


def block(aid, **kw):
    return {"asset_id": aid, "alt": "alt text", "caption": "Cap line", **kw}


@pytest.mark.parametrize("aid", list(KEYS))
def test_renders_key_content(aid):
    out = ch6_ch7.RENDERERS[aid](block(aid))
    for k in KEYS[aid]:
        assert k in out
    assert "Cap line" in out
    assert out.count("Cap line") == 1


@pytest.mark.parametrize("aid", list(KEYS))
def test_hostile_strings_escaped(aid):
    evil = '<script>alert(1)</script>"'
    out = ch6_ch7.RENDERERS[aid](block(aid, caption=evil, alt=evil))
    assert "<script>alert" not in out


def test_esc_zero():
    assert ch6_ch7._e(0) == "0"


@pytest.mark.parametrize("aid", list(KEYS))
def test_no_inline_handlers(aid):
    out = ch6_ch7.RENDERERS[aid](block(aid))
    assert not re.search(r"\son\w+\s*=", out)


def test_js_safe():
    assert "innerHTML" not in ch6_ch7.JS
    assert "insertAdjacentHTML" not in ch6_ch7.JS


def test_css_no_hex_and_prefixed():
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", ch6_ch7.CSS)
    for sel in re.findall(r"(?m)^\.([\w-]+)", ch6_ch7.CSS):
        assert sel.startswith("gg-ig-d")


def test_matrix_complete():
    out = ch6_ch7.RENDERERS["ch7-weather-matrix"](block("ch7-weather-matrix"))
    assert out.count("gg-ig-d-mx-cell gg-ig-d-mx-cell--") == 25


def test_week_has_seven_days():
    out = ch6_ch7.RENDERERS["ch7-race-week-countdown"](block("ch7-race-week-countdown"))
    assert out.count('class="gg-ig-d-wk-panel"') == 7
