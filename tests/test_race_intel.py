"""Tests for deterministic race intel mining and rendering."""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_race_intel import (  # noqa: E402
    BULK_COMMIT_FILE_LIMIT,
    _history_rows,
    classify_changes,
    is_bulk_commit,
    mine_history,
)
from generate_neo_brutalist import build_latest_sidebar  # noqa: E402


def _profile(*, date="2026: June 6", tier=2, score=70, website="https://race.test"):
    return {
        "race": {
            "vitals": {"date_specific": date},
            "gravel_god_rating": {"tier": tier, "overall_score": score},
            "website": website,
        }
    }


def test_classifier_covers_only_v1_changes():
    old = _profile()
    new = _profile(date="2027: June 5; route pending", tier=1, score=74,
                   website="https://new.test")
    events = classify_changes(old, new)
    assert events == [
        {"type": "date_confirmed", "text": "2027 edition: June 5 — date confirmed"},
        {"type": "rerated", "text": "Re-rated: Tier 2 → Tier 1"},
        {"type": "rescored", "text": "Score updated: 70 → 74"},
        {"type": "site_updated", "text": "Official site link updated"},
    ]
    unchanged_v1 = _profile()
    unchanged_v1["race"]["tagline"] = "New editorial copy"
    assert classify_changes(old, unchanged_v1) == []


def test_classifier_added_and_score_threshold():
    assert classify_changes(None, _profile()) == [
        {"type": "added", "text": "Added to the database"}
    ]
    assert classify_changes(_profile(score=70), _profile(score=71)) == []


def test_bulk_guard_threshold():
    paths = [f"race-data/race-{i}.json" for i in range(BULK_COMMIT_FILE_LIMIT)]
    assert is_bulk_commit(paths) is False
    assert is_bulk_commit(paths + ["race-data/one-more.json"]) is True


def test_history_rows_accept_parentless_shallow_boundary(monkeypatch):
    monkeypatch.setattr(
        "generate_race_intel._git",
        lambda *args, **kwargs: (
            "\x1edeadbeef\t2026-08-12\t\n"
            "race-data/unbound-200.json\n"
        ),
    )
    assert _history_rows("6 months ago") == [
        ("deadbeef", "2026-08-12", None, ["race-data/unbound-200.json"])
    ]


def test_latest_sidebar_caps_formats_and_links_date_confirmation():
    rd = {"website": "https://race.test", "slug": "test-race", "name": "Test Race"}
    events = [
        {"date": "2026-08-10", "type": "date_confirmed", "text": "Date confirmed"},
        {"date": "2026-07-03", "type": "rerated", "text": "Re-rated"},
        {"date": "2026-06-02", "type": "rescored", "text": "Rescored"},
        {"date": "2026-05-01", "type": "added", "text": "Added"},
    ]
    html = build_latest_sidebar(rd, events)
    assert html.count('class="gg-latest-item"') == 3
    assert "Aug 2026" in html
    assert '<a href="https://race.test"' in html
    assert ">Re-rated</span>" in html
    assert "Added" not in html
    empty_html = build_latest_sidebar(rd, [])
    assert "WATCH THIS RACE" in empty_html
    assert 'name="race_slug" value="test-race"' in empty_html


def test_real_unbound_history_is_well_formed():
    events = mine_history(only_slug="unbound-200").get("unbound-200", [])
    assert len(events) <= 5
    for event in events:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", event["date"])
        assert event["type"] in {
            "date_confirmed", "rerated", "rescored", "site_updated", "added"
        }
        assert event["text"]
