"""Race database score bar opens its breakdown from the keyboard (#662).

The bar is a real <button type="button"> with aria-expanded/aria-controls,
toggled by the delegated click listener (no inline onclick). Races without a
breakdown get a plain, non-interactive bar.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = (ROOT / "web" / "gravel-race-search.js").read_text()


@pytest.fixture(scope="module")
def css():
    files = list((ROOT / "web").glob("gg-search.*.css"))
    assert len(files) == 1, files
    return files[0].read_text()


def _render_card_src():
    start = JS.index("function renderCard(race)")
    return JS[start:JS.index("// ── Tier grouping", start)]


def test_score_bar_is_a_button_with_state():
    src = _render_card_src()
    assert '<button type="button" class="gg-score-bar" aria-expanded="false" aria-controls="\' + breakdownId + \'"' in src
    assert "aria-label=" in src


def test_no_inline_handler_on_score_bar():
    assert not re.search(r'gg-score-bar"[^>]*onclick', JS)


def test_breakdown_has_matching_id():
    assert "renderScoreBreakdown(race.scores, breakdownId)" in JS
    assert '<div class="gg-score-breakdown" id="\' + id + \'">' in JS
    assert "var breakdownId = 'gg-score-breakdown-' + escHtml(race.slug);" in JS


def test_button_only_when_breakdown_exists():
    src = _render_card_src()
    assert "if (race.overall_score && breakdown)" in src
    assert "gg-score-bar gg-score-bar--static" in src


def test_delegated_toggle_updates_aria_expanded():
    start = JS.index("// Delegated event listeners")
    block = JS[start:start + 1500]
    assert "e.target.closest('button.gg-score-bar')" in block
    assert "getAttribute('aria-controls')" in block
    assert "setAttribute('aria-expanded', open ? 'true' : 'false')" in block


def test_button_reset_and_visible_focus(css):
    m = re.search(r"#gg-race-search button\.gg-score-bar \{([^}]*)\}", css)
    assert m
    body = m.group(1)
    for decl in ("background: transparent !important", "border: 0 !important",
                 "padding: 0 !important", "min-height: 24px"):
        assert decl in body
    assert re.search(r"button\.gg-score-bar:focus-visible \{[^}]*outline: 3px solid var\(--gg-color-teal\)", css)


def test_fill_is_block_inside_span_track(css):
    m = re.search(r"#gg-race-search \.gg-score-fill \{([^}]*)\}", css)
    assert "display: block" in m.group(1)
