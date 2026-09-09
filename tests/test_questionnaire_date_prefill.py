"""Source-confidence checks for questionnaire race-date prefill."""

import json
from pathlib import Path

from scripts.generate_index import (
    _questionnaire_date_from_vitals,
    build_index_entry_from_profile,
)


ROOT = Path(__file__).parent.parent


def test_big_sugar_explicitly_confirmed_single_date_is_published_for_prefill():
    profile = json.loads((ROOT / "race-data" / "big-sugar.json").read_text())

    entry = build_index_entry_from_profile("big-sugar", profile)

    assert entry["questionnaire_date"] == "2026-10-17"


def test_provisional_date_is_not_published_for_prefill():
    profile = json.loads(
        (ROOT / "race-data" / "worthersee-gravel-race.json").read_text()
    )

    entry = build_index_entry_from_profile("worthersee-gravel-race", profile)

    assert "questionnaire_date" not in entry


def test_multiday_date_is_not_published_for_prefill():
    profile = json.loads((ROOT / "race-data" / "gravel-burn.json").read_text())

    entry = build_index_entry_from_profile("gravel-burn", profile)

    assert "questionnaire_date" not in entry


def test_source_blocked_date_is_not_published_for_prefill():
    vitals = {
        "course_status": "source_blocked",
        "date_specific": "2027: June 5 (CONFIRMED)",
    }

    assert _questionnaire_date_from_vitals(vitals) is None


def test_exact_date_without_explicit_confirmation_is_not_promoted():
    vitals = {"date_specific": "2027: April 17 (Saturday)"}

    assert _questionnaire_date_from_vitals(vitals) is None
