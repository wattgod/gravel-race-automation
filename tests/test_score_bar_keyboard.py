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


NODE_HARNESS = r"""
const src = process.argv[1];
function classList() { const s = new Set(); return {
  toggle(c) { if (s.has(c)) { s.delete(c); return false; } s.add(c); return true; },
  contains(c) { return s.has(c); } }; }
const panel = { classList: classList() };
const attrs = { 'aria-controls': 'gg-score-breakdown-x', 'aria-expanded': 'false' };
const btn = { getAttribute: k => attrs[k], setAttribute: (k, v) => { attrs[k] = v; } };
const document = { getElementById: id => (id === 'gg-score-breakdown-x' ? panel : null) };
const e = { target: { closest: sel => (sel === 'button.gg-score-bar' ? btn : null) } };
const run = new Function('e', 'document', src + '\nreturn "fell-through";');
const states = [];
for (let i = 0; i < 2; i++) {
  const r = run(e, document);
  states.push([r === undefined, attrs['aria-expanded'], panel.classList.contains('open')]);
}
console.log(JSON.stringify(states));
"""


def test_delegated_toggle_executes():
    """Run the real handler block: two clicks open then close the panel and
    keep aria-expanded in sync (Enter/Space reach it as native button clicks)."""
    import json
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("node not installed")
    start = JS.index("var scoreBtn = e.target.closest('button.gg-score-bar');")
    end = JS.index("return;\n    }", start) + len("return;\n    }")
    result = subprocess.run(["node", "-e", NODE_HARNESS, JS[start:end]],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout) == [[True, "true", True], [True, "false", False]]


def test_script_runs_once():
    """SiteGround bundles this file into its combined JS on top of the direct
    <script>, so it executes twice; without the guard the delegated score-bar
    toggle fires twice per click and never opens (live failure, #662)."""
    head = JS[:600]
    assert head.startswith("(function() {")
    assert "if (window.__ggRaceSearchLoaded) return;" in head
    assert "window.__ggRaceSearchLoaded = true;" in head


def test_double_load_registers_listeners_once():
    """Evaluate the real file twice against a stub DOM: only one click
    listener may be registered."""
    import shutil
    import subprocess
    if not shutil.which("node"):
        pytest.skip("node not installed")
    harness = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[1], 'utf8');
let clicks = 0;
const el = () => new Proxy(function () {}, { get: (t, k) => k === Symbol.toPrimitive ? () => '' : el(), apply: () => el() });
const document = new Proxy({}, { get: (t, k) => {
  if (k === 'addEventListener') return (type) => { if (type === 'click') clicks++; };
  if (k === 'readyState') return 'loading';
  return el(); } });
const window = {};
global.fetch = () => new Promise(() => {});
const localStorage = { getItem: () => null, setItem: () => {} };
for (let i = 0; i < 2; i++) new Function('window', 'document', 'localStorage', src)(window, document, localStorage);
console.log(clicks);
"""
    path = ROOT / "web" / "gravel-race-search.js"
    out = subprocess.run(["node", "-e", harness, str(path)],
                         capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "1"
