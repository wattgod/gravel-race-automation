"""difficulty_composite — the quiz's highest-weighted input.

The race quiz asks "How hard do you want it?" and weights the answer at 20
points, more than terrain (12) or region (10). It reads difficulty_composite,
which nothing produced, so every race sat at the JS default of 2.5. Under the
scoring bands that meant "moderate" scored 20 for every race while "hard" and
"brutal" scored 0 for every race — the two hardest answers were discarded.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from generate_index import _DIFFICULTY_WEIGHTS, _difficulty_composite  # noqa: E402


class TestComposite:
    def test_weights_sum_to_one(self):
        assert round(sum(_DIFFICULTY_WEIGHTS.values()), 6) == 1.0

    def test_uses_physical_criteria_only(self):
        # prestige/value/logistics describe the event, not how much it hurts
        assert set(_DIFFICULTY_WEIGHTS) == {
            "length", "elevation", "technicality", "climate", "altitude"}

    def test_all_fives_is_five(self):
        assert _difficulty_composite({k: 5 for k in _DIFFICULTY_WEIGHTS}) == 5.0

    def test_all_ones_is_one(self):
        assert _difficulty_composite({k: 1 for k in _DIFFICULTY_WEIGHTS}) == 1.0

    def test_partial_scores_yield_none_not_a_confident_number(self):
        """length+elevation alone must not reach 5.0 and take full 'brutal'
        credit while three dimensions are unknown."""
        assert _difficulty_composite({"length": 5, "elevation": 5}) is None

    def test_none_when_nothing_physical_is_scored(self):
        # better a neutral default in the quiz than a fabricated number
        assert _difficulty_composite({"prestige": 5, "value": 4}) is None
        assert _difficulty_composite({}) is None

    def test_non_numeric_counts_as_missing(self):
        scores = {k: 4 for k in _DIFFICULTY_WEIGHTS}
        scores["length"] = "hard"
        assert _difficulty_composite(scores) is None


class TestIndexIsPopulated:
    @pytest.fixture(scope="class")
    def races(self):
        data = json.loads((ROOT / "web" / "race-index.json").read_text())
        return data if isinstance(data, list) else data.get("races", data)

    def test_profiled_races_have_a_difficulty(self, races):
        scored = [r for r in races if r.get("scores")]
        missing = [r["slug"] for r in scored
                   if not isinstance(r.get("difficulty_composite"), (int, float))]
        assert not missing, f"{len(missing)} scored races without difficulty: {missing[:5]}"

    def test_values_are_on_the_one_to_five_scale(self, races):
        vals = [r["difficulty_composite"] for r in races
                if isinstance(r.get("difficulty_composite"), (int, float))]
        assert vals
        assert min(vals) >= 1.0 and max(vals) <= 5.0

    def test_actually_discriminates(self, races):
        """A constant would make the quiz's biggest question meaningless."""
        vals = {r["difficulty_composite"] for r in races
                if isinstance(r.get("difficulty_composite"), (int, float))}
        assert len(vals) > 10, f"only {len(vals)} distinct difficulty values"

    def test_brutal_answer_can_match_something(self, races):
        """The old constant 2.5 meant 'brutal' scored zero against every race."""
        brutal = [r for r in races
                  if isinstance(r.get("difficulty_composite"), (int, float))
                  and r["difficulty_composite"] > 4]
        assert brutal, "no race qualifies as brutal — the answer matches nothing"


class TestPipelineEndToEnd:
    """The unit tests above and the checked-in index could both be right while
    the real entry builder never emits the field. Go through it."""

    def _profile(self, **score_overrides):
        scores = {"length": 4, "elevation": 4, "technicality": 3,
                  "climate": 3, "altitude": 2}
        scores.update(score_overrides)
        return {"race": {
            "name": "Test Race", "display_name": "Test Race",
            "vitals": {"location": "Emporia, Kansas", "date": "2026: June 1",
                       "distance_mi": 100, "elevation_ft": 6000},
            "gravel_god_rating": {"tier": 2, "overall_score": 70, **scores},
        }}

    def test_entry_builder_emits_difficulty(self):
        from generate_index import build_index_entry_from_profile
        entry = build_index_entry_from_profile("test-race", self._profile())
        assert entry["difficulty_composite"] == round(
            4 * 0.30 + 4 * 0.30 + 3 * 0.20 + 3 * 0.10 + 2 * 0.10, 2)

    def test_entry_builder_emits_none_on_partial(self):
        from generate_index import build_index_entry_from_profile
        p = self._profile()
        del p["race"]["gravel_god_rating"]["altitude"]
        entry = build_index_entry_from_profile("test-race", p)
        assert entry["difficulty_composite"] is None

    def test_quiz_carries_it_through_to_the_page(self):
        """End to end: profile -> index entry -> emitted RACES array."""
        import re
        sys.path.insert(0, str(ROOT / "wordpress"))
        from generate_index import build_index_entry_from_profile
        from generate_quiz import build_quiz_page

        entry = build_index_entry_from_profile("test-race", self._profile())
        html = build_quiz_page([entry])
        races = json.loads(re.search(r"var RACES=(\[.*?\]);", html, re.S).group(1))
        assert races[0]["df"] == entry["difficulty_composite"]
        assert races[0]["df"] > 0, "quiz emitted a zero difficulty"
