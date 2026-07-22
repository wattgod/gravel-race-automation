"""Dead-tire-crosslink regressions (2026-07-22): prep kits and state hubs
linked /race/{slug}/tires/ unconditionally, 404ing for races with no
generated tire guide. Crosslinks now require tire_recommendations.primary
(prep kit) / has_tire_guide (hubs, via the race-index flag).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from generate_prep_kit import build_pk_equipment
from generate_index import build_index_entry_from_profile


GUIDE_SECTIONS = {
    "ch7-equipment": {
        "blocks": [
            {"type": "accordion", "items": [
                {"title": "Pack this", "content": "A pump."},
            ]},
        ],
    },
}


def _rd(with_tires: bool) -> dict:
    rd = {"slug": "test-race", "name": "Test Race"}
    if with_tires:
        rd["tire_recommendations"] = {
            "primary": [{"tire_id": "test-tire", "name": "Test Tire", "width_mm": 42}],
            "race_surface_profile": "mixed",
        }
    return rd


class TestPrepKitTireCrosslink:
    def test_crosslink_present_with_primary(self):
        html = build_pk_equipment(GUIDE_SECTIONS, {}, _rd(with_tires=True))
        assert "/race/test-race/tires/" in html

    def test_no_crosslink_without_primary(self):
        html = build_pk_equipment(GUIDE_SECTIONS, {}, _rd(with_tires=False))
        assert "/tires/" not in html

    def test_no_crosslink_with_empty_primary(self):
        rd = _rd(with_tires=True)
        rd["tire_recommendations"]["primary"] = []
        html = build_pk_equipment(GUIDE_SECTIONS, {}, rd)
        assert "/tires/" not in html


class TestIndexHasTireGuideFlag:
    def _profile(self, with_tires: bool) -> dict:
        race = {
            "slug": "test-race", "name": "Test Race",
            "vitals": {}, "gravel_god_rating": {"overall_score": 50, "tier": 3},
        }
        if with_tires:
            race["tire_recommendations"] = {"primary": [{"tire_id": "t"}]}
        return {"race": race}

    def test_flag_true_with_primary(self):
        entry = build_index_entry_from_profile("test-race", self._profile(True))
        assert entry["has_tire_guide"] is True

    def test_flag_false_without_primary(self):
        entry = build_index_entry_from_profile("test-race", self._profile(False))
        assert entry["has_tire_guide"] is False


class TestLiveIndexParity:
    def test_index_flag_matches_generated_tire_guides(self):
        """The set of has_tire_guide slugs must equal the generated tire pages."""
        idx = json.loads((PROJECT_ROOT / "web" / "race-index.json").read_text())
        flagged = {r["slug"] for r in idx if r.get("has_tire_guide")}
        generated = {p.stem for p in (PROJECT_ROOT / "wordpress" / "output" / "tires").glob("*.html")}
        if not generated:
            pytest.skip("no local tire-guide output")
        assert flagged == generated
