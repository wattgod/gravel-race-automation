"""Dead TrainingPeaks listings get no buy button (sweep GG-02)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import check_tp_listings as ctl  # noqa: E402
import generate_training_plan_pages as gtpp  # noqa: E402


def test_classify_only_trusts_tp_own_pages():
    assert ctl.classify("Training Plan Not Found | TrainingPeaks") == "gone"
    assert ctl.classify("Unbound · Finisher · 12wk | cycling Training Plan | TrainingPeaks") == "live"
    assert ctl.classify("Just a moment...") == "unknown"
    assert ctl.classify(None) == "unknown"


def test_merge_keeps_state_on_unknown_and_clears_on_live():
    prev = {"plans": {"1": {"race_slug": "a", "first_seen": "2026-11-01", "last_checked": "2026-11-01"},
                      "2": {"race_slug": "a", "first_seen": "2026-11-01", "last_checked": "2026-11-01"}}}
    out = ctl.merge(prev, {1: ("unknown", "a"), 2: ("live", "a"), 3: ("gone", "b")}, "2026-11-15")
    assert set(out["plans"]) == {"1", "3"}
    assert out["plans"]["1"]["last_checked"] == "2026-11-01"
    assert out["plans"]["3"] == {"race_slug": "b", "first_seen": "2026-11-15", "last_checked": "2026-11-15"}


def _write(tmp_path, monkeypatch, gone):
    f = tmp_path / "unavailable.json"
    f.write_text(json.dumps({"plans": {str(i): {"race_slug": "x"} for i in gone}}))
    monkeypatch.setattr(gtpp, "TP_UNAVAILABLE", f)


def test_dead_listing_gets_no_button(tmp_path, monkeypatch):
    links = gtpp.load_sku_link("the-majestics-gravel")["links"]
    _write(tmp_path, monkeypatch, [links[0]["planId"]])
    after = gtpp.load_sku_link("the-majestics-gravel")["links"]
    assert [p["planId"] for p in after] == [p["planId"] for p in links[1:]]


def test_all_listings_dead_means_no_section_not_a_family_plan(tmp_path, monkeypatch):
    links = gtpp.load_sku_link("the-majestics-gravel")["links"]
    _write(tmp_path, monkeypatch, [p["planId"] for p in links])
    assert gtpp.load_sku_link("the-majestics-gravel") == {}


def test_malformed_unavailable_file_raises(tmp_path, monkeypatch):
    f = tmp_path / "unavailable.json"
    f.write_text("{")
    monkeypatch.setattr(gtpp, "TP_UNAVAILABLE", f)
    with pytest.raises(json.JSONDecodeError):
        gtpp.load_sku_link("the-majestics-gravel")


def test_committed_list_hides_the_audited_dead_listing():
    """tp-659969 (Gravel Grit 'n Grind Finisher 8wk) answered Not Found on
    14-15 Nov 2026."""
    gone = gtpp.load_unavailable_plan_ids()
    assert 659969 in gone
    ids = [p["planId"] for p in gtpp.load_sku_link("gravel-grit-n-grind").get("links", [])]
    assert 659969 not in ids
