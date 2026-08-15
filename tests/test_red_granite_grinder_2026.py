"""Current-source contracts for the 2026 Red Granite Grinder."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLUG = "red-granite-grinder"


def load_race() -> dict:
    return json.loads(
        (ROOT / f"race-data/{SLUG}.json").read_text(encoding="utf-8")
    )["race"]


def test_red_granite_profile_uses_current_official_2026_facts() -> None:
    race = load_race()
    vitals = race["vitals"]

    assert vitals["date_specific"] == "2026: October 10"
    assert vitals["distance_mi"] == 150
    assert vitals["elevation_ft"] is None
    assert vitals["gain_display"] == "Not published"
    assert vitals["start_time"] == (
        "150 miles 7:00 AM; 100 miles 8:00 AM; 50 miles 8:30 AM; 20 miles 9:00 AM"
    )
    assert "$75 for 150 miles" in vitals["registration"]
    assert race["logistics"]["official_site"] == "https://www.redgranitegrinder.com/"
    assert race["gravel_god_rating"]["overall_score"] == 59
    assert race["gravel_god_rating"]["tier"] == 3
    assert race["source_review"]["reviewed_at"] == "2026-08-15"
    assert race["research_metadata"]["validation_status"] == "source-reviewed"


def test_red_granite_profile_preserves_current_course_uncertainty() -> None:
    race = load_race()
    serialized = json.dumps(race)

    assert race["terrain"]["surface"] == (
        "Red granite gravel and remote rural Wisconsin roads"
    )
    assert "final route and climbing still pending" in race[
        "course_description"
    ]["character"]
    assert race["youtube_data"] == {"videos": [], "quotes": []}
    assert race["photos"] == []
    for stale_or_wrong_claim in (
        "2,800",
        "2800",
        "90% gravel",
        "85% gravel",
        "Red Eagle Gravel Grinder",
        "Geneva, OH",
        "Rib Mountain",
    ):
        assert stale_or_wrong_claim not in serialized


def test_red_granite_current_sources_lead_the_citation_list() -> None:
    citations = load_race()["citations"]
    assert [item["url"] for item in citations[:2]] == [
        "https://www.redgranitegrinder.com/",
        "https://ironbull-signup.redpodium.com/2026-red-granite-grinder",
    ]
