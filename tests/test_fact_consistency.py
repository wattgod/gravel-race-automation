"""Race pages must not contradict themselves (wordpress/fact_consistency.py).

Ratchet: every contradiction found today is listed in
config/fact-consistency-baseline.json. A new one fails the build; a fixed one
must be deleted from the baseline so the list only shrinks.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from fact_consistency import check_all, check_race  # noqa: E402

BASELINE = json.loads((ROOT / "config" / "fact-consistency-baseline.json").read_text())["known"]


@pytest.fixture(scope="module")
def current():
    return check_all()


def test_no_new_contradictions(current):
    new = {
        slug: [i for i in issues if i not in BASELINE.get(slug, [])]
        for slug, issues in current.items()
    }
    new = {slug: issues for slug, issues in new.items() if issues}
    assert not new, (
        "New contradictions on race pages (fix the data, or regenerate the "
        f"workout pack): {json.dumps(new, indent=2)}"
    )


def test_baseline_only_shrinks(current):
    stale = {
        slug: [i for i in issues if i not in current.get(slug, [])]
        for slug, issues in BASELINE.items()
    }
    stale = {slug: issues for slug, issues in stale.items() if issues}
    assert not stale, (
        "These contradictions are fixed; delete them from "
        f"config/fact-consistency-baseline.json: {json.dumps(stale, indent=2)}"
    )


def test_gravel_revival_is_clean(current):
    assert "gravel-revival" not in current


def test_distance_mismatch_detected(tmp_path):
    race = {"vitals": {"distance_mi": 68}, "guide_variables": {"race_distance": "75 miles"}}
    issues = check_race(race, "x", packs_dir=tmp_path)
    assert any("guide_variables" in i for i in issues)


def test_pack_distance_mismatch_detected(tmp_path):
    (tmp_path / "x.json").write_text(json.dumps({"distance_mi": 75.0}))
    issues = check_race({"vitals": {"distance_mi": 68}}, "x", packs_dir=tmp_path)
    assert any("workout pack" in i for i in issues)


def test_small_rounding_is_not_a_contradiction(tmp_path):
    race = {"vitals": {"distance_mi": 68}, "guide_variables": {"race_distance": "70 miles"}}
    assert check_race(race, "x", packs_dir=tmp_path) == []


def test_edition_mismatch_detected(tmp_path):
    race = {"biased_opinion_ratings": {
        "prestige": {"explanation": "The 6th annual event."},
        "community": {"explanation": "Back for the 5th annual edition."},
    }}
    issues = check_race(race, "x", packs_dir=tmp_path)
    assert any(i.startswith("edition") for i in issues)


def test_source_titles_do_not_count_as_editions(tmp_path):
    race = {
        "biased_opinion_ratings": {"prestige": {"explanation": "The 2026 edition is the 7th annual."}},
        "citations": [{"url": "https://example.com/the-5th-annual-race/", "label": "5th annual"}],
    }
    assert check_race(race, "x", packs_dir=tmp_path) == []
