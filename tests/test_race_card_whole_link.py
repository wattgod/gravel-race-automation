"""Race database cards open the race from anywhere on the card (#655).

Pattern: the title <a class="gg-card-name"> stays the card's ONE link and its
::after stretches over the card; the compare checkbox, favourite heart,
series pill and score bar sit above it (position:relative; z-index:1) so they
keep their own clicks. The card is never wrapped in <a> (no nested interactive
elements). The title wraps above the badges instead of colliding with the
series pill.
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
    end = JS.index("// ── Tier grouping", start)
    return JS[start:end]


def _rule(css, selector):
    """Bodies of every rule whose selector list contains `selector`, joined."""
    bodies = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        head = re.sub(r"/\*.*?\*/", "", m.group(1), flags=re.S)
        sels = [s.strip() for s in head.split(",")]
        if selector in sels:
            bodies.append(m.group(2))
    assert bodies, f"no CSS rule for {selector}"
    return "\n".join(bodies)


class TestCardMarkup:
    def test_linked_card_gets_modifier_only_with_profile(self):
        src = _render_card_src()
        assert "(race.has_profile ? ' gg-card-linked' : '')" in src

    def test_title_is_the_only_race_link(self):
        src = _render_card_src()
        assert src.count("race.profile_url") == 1
        assert '<a class="gg-card-name" href="' in src

    def test_card_not_wrapped_in_anchor(self):
        src = _render_card_src()
        assert "return '<a" not in src
        assert "return '<div class=\"gg-card " in src

    def test_badges_use_class_not_inline_style(self):
        src = _render_card_src()
        assert '<div class="gg-card-badges">' in src
        assert "display:flex;gap:6px" not in src


class TestStretchedLinkCss:
    def test_card_is_positioning_context(self, css):
        assert "position: relative" in _rule(css, "#gg-race-search .gg-card")

    def test_title_after_covers_card(self, css):
        body = _rule(css, "#gg-race-search .gg-card-linked a.gg-card-name::after")
        assert 'content: ""' in body
        assert "position: absolute" in body
        assert "inset: 0" in body

    @pytest.mark.parametrize("control", [
        "gg-compare-check", "gg-fav-btn", "gg-series-badge",
        "gg-score-bar", "gg-score-breakdown",
    ])
    def test_secondary_controls_sit_above_link(self, css, control):
        body = _rule(css, f"#gg-race-search .gg-card-linked .{control}")
        assert "position: relative" in body
        assert "z-index: 1" in body

    def test_no_intermediate_positioning_context(self, css):
        """A positioned header would trap the ::after inside the header."""
        assert "position" not in _rule(css, "#gg-race-search .gg-card-header")

    def test_focus_and_hover_signifiers(self, css):
        focus = _rule(css, "#gg-race-search .gg-card-linked:focus-within")
        assert "outline: 3px solid var(--gg-color-teal)" in focus
        assert "underline" in _rule(css, "#gg-race-search .gg-card-linked:hover a.gg-card-name")

    def test_new_rules_stay_neo_brutalist(self, css):
        start = css.index("Whole-card link (stretched title anchor)")
        block = css[start:css.index("#gg-race-search .gg-tier-badge", start)]
        assert "border-radius" not in block
        assert "box-shadow" not in block
        assert not re.search(r"#[0-9a-fA-F]{3,6}\b", block), "use tokens, not hex"


class TestTitleDoesNotCollideWithPill:
    def test_header_wraps(self, css):
        body = _rule(css, "#gg-race-search .gg-card-header")
        assert "flex-wrap: wrap" in body
        assert "gap:" in body

    def test_title_can_shrink_and_wrap(self, css):
        body = _rule(css, "#gg-race-search a.gg-card-name")
        assert "min-width: 0" in body
        assert "overflow-wrap: anywhere" in body

    def test_badges_wrap(self, css):
        assert "flex-wrap: wrap" in _rule(css, "#gg-race-search .gg-card-badges")
