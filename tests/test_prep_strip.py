"""Preparation Profile strip — northstar Phase 1 conversion engine.

The strip surfaces race demands + plan CTA above the fold (the full [08]
section converted 0.5% of visitors when it was the only entry point —
first funnel report, Jun 2026). These tests guard:
- render conditions (race-pack required, [08] must exist for the anchor)
- the gg-* contract the countdown/price JS depends on
- graceful degradation for missing/stale race dates (48 known stale profiles)
- no inline handlers / proper escaping
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wordpress"))

from generate_neo_brutalist import build_prep_strip, build_inline_js, get_page_css

RACE_PACKS = Path(__file__).resolve().parent.parent / "web" / "race-packs"


def _rd(slug="unbound-200", date_specific="2026: May 30"):
    return {
        "slug": slug,
        "name": "Unbound Gravel 200",
        "vitals": {"date_specific": date_specific},
    }


@pytest.fixture(scope="module")
def packed_slug():
    """A slug that actually has a race-pack preview on disk."""
    packs = sorted(RACE_PACKS.glob("*.json"))
    if not packs:
        pytest.skip("no race packs on disk")
    return packs[0].stem


class TestRenderConditions:
    def test_renders_for_race_with_pack(self, packed_slug):
        rd = _rd(slug=packed_slug)
        html = build_prep_strip(rd)
        assert 'id="prep-strip"' in html

    def test_empty_for_race_without_pack(self):
        html = build_prep_strip(_rd(slug="no-such-race-pack-xyz"))
        assert html == ""

    def test_at_most_three_chips(self, packed_slug):
        html = build_prep_strip(_rd(slug=packed_slug))
        assert html.count('class="gg-prep-chip"') <= 3


class TestJsContract:
    """IDs/attributes the countdown+price JS reads. Renaming any of these
    silently kills the dynamic pricing."""

    def test_contract_ids_present(self, packed_slug):
        html = build_prep_strip(_rd(slug=packed_slug))
        for needle in ('id="prep-strip"', 'id="gg-prep-countdown"',
                       'id="gg-prep-cta"'):
            assert needle in html, needle

    def test_inline_js_targets_contract(self):
        js = build_inline_js()
        assert "getElementById('prep-strip')" in js
        assert "data-race-date" in js
        assert "getElementById('gg-prep-countdown')" in js
        assert "getElementById('gg-prep-cta')" in js

    def test_js_pricing_matches_server(self):
        """$15/wk, min 4 weeks, $249 cap — must mirror webhook pricing."""
        js = build_inline_js()
        assert "weeks * 15" in js
        assert "Math.max(4," in js
        assert "249" in js

    def test_css_present(self):
        css = get_page_css()
        assert ".gg-prep-strip" in css
        assert ".gg-prep-chip" in css


class TestDateDegradation:
    def test_valid_date_emits_attr(self, packed_slug):
        html = build_prep_strip(_rd(slug=packed_slug,
                                    date_specific="2026: May 30"))
        assert 'data-race-date="2026-05-30"' in html

    def test_missing_date_omits_attr(self, packed_slug):
        html = build_prep_strip(_rd(slug=packed_slug, date_specific=""))
        assert 'id="prep-strip"' in html
        assert "data-race-date" not in html

    def test_generic_price_copy_without_js(self, packed_slug):
        """Server-rendered CTA must be safe even if JS never runs."""
        html = build_prep_strip(_rd(slug=packed_slug))
        assert "$15/WK" in html

    def test_past_date_guard_in_js(self):
        """JS must bail (keep generic copy) for past/imminent dates —
        48 profiles have known-stale dates."""
        js = build_inline_js()
        assert "days <= 7" in js


class TestSafety:
    def test_no_inline_handlers(self, packed_slug):
        html = build_prep_strip(_rd(slug=packed_slug))
        assert "onclick=" not in html
        assert "onsubmit=" not in html

    def test_cta_links(self, packed_slug):
        html = build_prep_strip(_rd(slug=packed_slug))
        assert 'href="#train-for-race"' in html
        assert f"questionnaire/?race={packed_slug}" in html

    def test_race_name_escaped(self, packed_slug):
        rd = _rd(slug=packed_slug)
        rd["name"] = 'Evil "Race" <script>'
        html = build_prep_strip(rd)
        assert "<script>" not in html.replace("</script>", "")
        assert "&lt;script&gt;" in html


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
