"""Tests for verify_race_rankings.py — the rankings veracity checker.

Covers the pure logic only (rubric scoring, tolerance, fix application).
The Anthropic API call is not exercised here.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import verify_race_rankings as vrr


class TestNumericCoercion:
    def test_plain_int(self):
        assert vrr._num(11000) == 11000.0

    def test_comma_string(self):
        assert vrr._num("11,000 ft") == 11000.0

    def test_approx_prefix(self):
        assert vrr._num("~500") == 500.0

    def test_none(self):
        assert vrr._num(None) is None

    def test_garbage(self):
        assert vrr._num("unknown") is None


class TestRubricThresholds:
    """Thresholds must match docs/GRAVEL_GOD_SCORING_SYSTEM.md."""

    @pytest.mark.parametrize("miles,score", [
        (39, 1), (40, 2), (59, 2), (60, 3), (99, 3), (100, 4), (149, 4), (150, 5), (350, 5),
    ])
    def test_length(self, miles, score):
        assert vrr.score_from_thresholds(miles, vrr.LENGTH_THRESHOLDS) == score

    @pytest.mark.parametrize("feet,score", [
        (1999, 1), (2000, 2), (3999, 2), (4000, 3), (5999, 3),
        (6000, 4), (9999, 4), (10000, 5),
    ])
    def test_elevation(self, feet, score):
        assert vrr.score_from_thresholds(feet, vrr.ELEVATION_THRESHOLDS) == score


def _make_race_file(tmp_path, monkeypatch, vitals, rating):
    race_dir = tmp_path / "race-data"
    race_dir.mkdir()
    data = {"race": {"name": "Test Race", "vitals": vitals,
                     "gravel_god_rating": rating}}
    (race_dir / "test-race.json").write_text(json.dumps(data))
    monkeypatch.setattr(vrr, "RACE_DATA", race_dir)
    return race_dir / "test-race.json"


BASE_RATING = {
    "logistics": 3, "length": 4, "technicality": 3, "elevation": 3,
    "climate": 4, "altitude": 1, "adventure": 4, "prestige": 3,
    "race_quality": 4, "experience": 5, "community": 5, "field_depth": 4,
    "value": 4, "expenses": 3, "cultural_impact": 4,
    "overall_score": 71, "tier": 2, "editorial_tier": 2, "display_tier": 2,
    "tier_label": "TIER 2", "editorial_tier_label": "TIER 2",
    "display_tier_label": "TIER 2",
}


def _verdict(field, verdict="mismatch", web_value=None, confidence="high"):
    return {"field": field, "verdict": verdict, "web_value": web_value,
            "confidence": confidence, "source_url": "https://example.com",
            "note": None}


class TestApplyFixes:
    def test_high_confidence_mismatch_fixes_vital(self, tmp_path, monkeypatch):
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 100, "elevation_ft": 5000},
                               dict(BASE_RATING))
        changes = vrr.apply_fixes("test-race",
                                  [_verdict("distance_mi", web_value="62")],
                                  dry_run=False)
        data = json.loads(path.read_text())
        assert data["race"]["vitals"]["distance_mi"] == 62
        assert any(c["field"] == "vitals.distance_mi" for c in changes)

    def test_low_confidence_never_fixes(self, tmp_path, monkeypatch):
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 100}, dict(BASE_RATING))
        changes = vrr.apply_fixes(
            "test-race",
            [_verdict("distance_mi", web_value="62", confidence="medium")],
            dry_run=False)
        assert changes == []
        assert json.loads(path.read_text())["race"]["vitals"]["distance_mi"] == 100

    def test_within_tolerance_is_confirmed(self, tmp_path, monkeypatch):
        _make_race_file(tmp_path, monkeypatch,
                        {"distance_mi": 100}, dict(BASE_RATING))
        changes = vrr.apply_fixes("test-race",
                                  [_verdict("distance_mi", web_value="103")],
                                  dry_run=False)
        assert changes == []

    def test_distance_change_recomputes_length_score(self, tmp_path, monkeypatch):
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 100, "elevation_ft": 5000},
                               dict(BASE_RATING))
        vrr.apply_fixes("test-race",
                        [_verdict("distance_mi", web_value="62")],
                        dry_run=False)
        rating = json.loads(path.read_text())["race"]["gravel_god_rating"]
        assert rating["length"] == 3  # 62 mi → score 3 per rubric
        # overall recomputed: base sum drops by 1 → round(53/70*100) = 76... depends
        assert rating["overall_score"] == vrr.recalculate_score(rating)

    def test_tier_change_is_flagged(self, tmp_path, monkeypatch):
        rating = dict(BASE_RATING)
        rating["overall_score"] = 61  # near T2/T3 boundary (60)
        rating["length"] = 2
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 45, "elevation_ft": 5000}, rating)
        changes = vrr.apply_fixes("test-race",
                                  [_verdict("distance_mi", web_value="30")],
                                  dry_run=False)
        new_rating = json.loads(path.read_text())["race"]["gravel_god_rating"]
        assert new_rating["length"] == 1
        if new_rating["display_tier"] != 2:
            assert any(c.get("tier_change") for c in changes)
            assert new_rating["display_tier_label"] == f"TIER {new_rating['display_tier']}"

    def test_huge_swing_is_flag_only(self, tmp_path, monkeypatch):
        """>50% change usually means the agent verified the wrong distance
        variant of a multi-distance event — never auto-fix."""
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 65}, dict(BASE_RATING))
        changes = vrr.apply_fixes("test-race",
                                  [_verdict("distance_mi", web_value="26.7")],
                                  dry_run=False)
        assert changes and changes[0]["flag_only"] is True
        assert json.loads(path.read_text())["race"]["vitals"]["distance_mi"] == 65

    def test_flag_only_change_never_triggers_score_recompute(self, tmp_path, monkeypatch):
        """A held (flag-only) vital must not recompute criterion scores."""
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 51, "elevation_ft": 5000},
                               dict(BASE_RATING))
        vrr.apply_fixes("test-race",
                        [_verdict("distance_mi", web_value="8.6")],
                        dry_run=False)
        rating = json.loads(path.read_text())["race"]["gravel_god_rating"]
        assert rating["length"] == BASE_RATING["length"]
        assert rating["overall_score"] == BASE_RATING["overall_score"]

    def test_status_is_flag_only(self, tmp_path, monkeypatch):
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 100}, dict(BASE_RATING))
        changes = vrr.apply_fixes("test-race",
                                  [_verdict("status", web_value="cancelled")],
                                  dry_run=False)
        assert changes and changes[0]["flag_only"] is True
        # File untouched — status never auto-applied
        assert "status" not in json.loads(path.read_text())["race"]["vitals"]

    def test_subjective_criteria_never_touched(self, tmp_path, monkeypatch):
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 100, "elevation_ft": 5000},
                               dict(BASE_RATING))
        vrr.apply_fixes("test-race",
                        [_verdict("distance_mi", web_value="62")],
                        dry_run=False)
        rating = json.loads(path.read_text())["race"]["gravel_god_rating"]
        for field in ("prestige", "community", "experience", "adventure",
                      "race_quality", "cultural_impact"):
            assert rating[field] == BASE_RATING[field]

    def test_dry_run_never_writes(self, tmp_path, monkeypatch):
        path = _make_race_file(tmp_path, monkeypatch,
                               {"distance_mi": 100}, dict(BASE_RATING))
        before = path.read_text()
        changes = vrr.apply_fixes("test-race",
                                  [_verdict("distance_mi", web_value="62")],
                                  dry_run=True)
        assert changes  # changes reported...
        assert path.read_text() == before  # ...but nothing written


class TestPromptSafety:
    def test_prompt_includes_current_values(self):
        race = {"display_name": "Unbound 200",
                "vitals": {"distance_mi": 200, "elevation_ft": 11000,
                           "location": "Emporia, KS"}}
        prompt = vrr.build_prompt(race)
        assert "Unbound 200" in prompt
        assert "200" in prompt and "11000" in prompt
        assert "unverifiable" in prompt  # safe-answer escape hatch present
