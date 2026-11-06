"""Race pages, titles and JSON-LD say what the data knows about an edition.

On 2026-11-05 "2026: August 30" has already run: the page shows the
estimated next date ("Aug 29, 2027 (estimate)"), the <title> prints the
estimate's year, and JSON-LD keeps the past startDate without calling it
EventScheduled and never carries the estimate. A race marked not running,
or one that skipped a season, says the next date is not announced.
"""

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

import generate_index as gi  # noqa: E402
import verify_race_rankings as vrr  # noqa: E402
from generate_neo_brutalist import (  # noqa: E402
    _location_tail,
    build_hero,
    generate_page,
    build_seo_title,
    build_sports_event_jsonld,
    normalize_race_data,
)
from race_facts import may_estimate, organizer_type  # noqa: E402

SCHEDULED = "https://schema.org/EventScheduled"


@pytest.fixture(autouse=True)
def nov_5(monkeypatch):
    monkeypatch.setenv("GG_TODAY", "2026-11-05")


@pytest.fixture
def traka():
    return json.loads((ROOT / "race-data" / "the-traka.json").read_text())


def _with(data, **vitals):
    data = copy.deepcopy(data)
    data["race"]["vitals"].update(vitals)
    return data


# ── <title> ───────────────────────────────────────────────────────────────

@pytest.mark.parametrize("location,tail", [
    ("Global (HQ: Girona, Spain)", "Global (HQ: Girona, Spain)"),
    ("Emporia, Kansas", "Kansas"),
    ("Girona, Spain (Catalonia, ES)", "Spain (Catalonia, ES)"),
    ("Kansas", "Kansas"),
])
def test_location_tail_ignores_commas_in_parentheses(location, tail):
    assert _location_tail(location) == tail


def test_title_never_splits_inside_parentheses():
    title = build_seo_title({"name": "Gravel Earth Series", "vitals": {
        "location": "Global (HQ: Girona, Spain)", "date_specific": "2027: May 1"}})
    assert "Spain)" not in title.replace("(HQ: Girona, Spain)", "")


@pytest.mark.parametrize("ds,expected", [
    ("2027: June 5", "Unbound Review 2027 | Kansas | Gravel God"),
    ("2026: August 30", "Unbound Review 2027 | Kansas | Gravel God"),  # estimate
    ("2025: August 3", "Unbound Review | Kansas | Gravel God"),        # skipped 2026
    ("Status: CANCELLED for 2026", "Unbound Review | Kansas | Gravel God"),
])
def test_title_year_is_next_edition_or_none(ds, expected):
    rd = {"name": "Unbound", "vitals": {"location": "Emporia, Kansas", "date_specific": ds}}
    assert build_seo_title(rd) == expected


def test_title_of_a_race_not_running_has_no_estimated_year():
    rd = {"name": "Unbound", "taking_a_break": {"label": "Not running in 2027"},
          "vitals": {"location": "Emporia, Kansas", "date_specific": "2026: August 30"}}
    assert build_seo_title(rd) == "Unbound Review | Kansas | Gravel God"


# ── Race page ─────────────────────────────────────────────────────────────

def test_past_edition_page_shows_the_estimated_next_date(traka):
    rd = normalize_race_data(_with(traka, date_specific="2026: September 19"))
    shown = "Sep 18, 2027 (estimate)"
    assert rd["vitals"]["date"] == shown
    assert shown in build_hero(rd)


def test_skipped_season_page_says_next_date_not_announced(traka):
    rd = normalize_race_data(_with(traka, date_specific="2025: August 3"))
    assert rd["vitals"]["date"] == "2027 date not announced · last ran Aug 3, 2025"


def test_race_not_running_gets_no_estimate(traka):
    data = _with(traka, date_specific="2026: September 19")
    data["race"]["taking_a_break"] = {"label": "Not running in 2027"}
    rd = normalize_race_data(data)
    assert rd["vitals"]["date"] == "2027 date not announced · last ran Sep 19, 2026"


def test_estimated_edition_is_labelled_estimate(traka):
    rd = normalize_race_data(_with(traka, date_specific="2027: June 5 (Saturday pattern)"))
    assert rd["vitals"]["date"] == "Jun 5, 2027 (estimate)"


def test_upcoming_confirmed_edition_shows_as_stored(traka):
    rd = normalize_race_data(_with(traka, date_specific="2027: May 1"))
    assert rd["vitals"]["date"] == "May 1, 2027"
    assert rd["vitals"]["edition_note"] == ""


@pytest.mark.parametrize("race,ok", [
    ({"vitals": {"date_specific": "2026: May 1"}}, True),
    ({"taking_a_break": {"label": "Cancelled for 2027"}, "vitals": {}}, False),
    ({"vitals": {"date_specific": "On hiatus; last held May 1, 2026"}}, False),
    ({"vitals": {"date_specific": "2026: May 1", "course_status": "source_blocked"}}, False),
])
def test_only_running_races_may_estimate(race, ok):
    assert may_estimate(race) is ok


# ── JSON-LD (race page and web/jsonld) ────────────────────────────────────

def _both(data):
    rd = normalize_race_data(data)
    entry = {"name": rd["name"], "tagline": "", "location": rd["vitals"]["location"]}
    return build_sports_event_jsonld(rd), gi.generate_jsonld(entry, data)


def test_upcoming_edition_is_scheduled_with_end_date(traka):
    data = _with(traka, date_specific="2027: April 30 (Fri) - May 2 (Sun)")
    for ld in _both(data):
        assert ld["eventStatus"] == SCHEDULED
        assert ld["startDate"] == "2027-04-30"
        assert ld["endDate"] == "2027-05-02"


def test_past_edition_keeps_start_date_but_not_scheduled(traka):
    for ld in _both(_with(traka, date_specific="2026: May 1")):
        assert ld["startDate"] == "2026-05-01"
        assert "eventStatus" not in ld


def test_jsonld_never_carries_an_estimate(traka):
    data = _with(traka, date_specific="2026: September 19 - September 20")
    for ld in _both(data):
        text = json.dumps(ld)
        assert ld["startDate"] == "2026-09-19"
        assert "2027-09" not in text and "estimate" not in text.lower()
        assert "eventStatus" not in ld


def test_estimate_reaches_the_date_label_only(traka):
    """No countdown, calendar export or structured date uses the estimate."""
    html = generate_page(normalize_race_data(_with(traka, date_specific="2026: September 19")), [])
    assert "Sep 18, 2027 (estimate)" in html
    for leak in ("2027-09-18", "20270918", "Sep 18, 2027<", "September 18, 2027"):
        assert leak not in html


def test_break_note_is_postponed_or_cancelled(traka):
    data = _with(traka, date_specific="2026: May 1")
    data["race"]["taking_a_break"] = {"label": "Cancelled for 2027"}
    for ld in _both(data):
        assert ld["eventStatus"] == "https://schema.org/EventCancelled"


def test_community_organizer_is_an_organization(traka):
    data = _with(traka, date_specific="2027: May 1")
    data["race"]["history"]["founder"] = "Local Girona cycling community"
    for ld in _both(data):
        assert ld["organizer"]["@type"] == "Organization"


@pytest.mark.parametrize("name,kind", [
    ("Jim Cummins", "Person"),
    ("Local Girona cycling community", "Organization"),
    ("Mike Ripley and Mudslinger Events", "Organization"),
    ("Rapha", "Organization"),
])
def test_organizer_type(name, kind):
    assert organizer_type(name) == kind


def test_jsonld_never_invents_offers(traka):
    data = _with(traka, date_specific="2027: May 1", registration="Opens in January")
    for ld in _both(data):
        assert "offers" not in ld


# ── Veracity commit subject ───────────────────────────────────────────────

def test_veracity_commit_counts_flagged_items():
    report = {"races": [
        {"changes": [{"field": "a", "flag_only": True}, {"field": "b", "flag_only": True}]},
        {"changes": [{"field": "c", "needs_review": True}]},
        {"changes": []},
    ]}
    assert vrr.commit_message(report, "2026-11-05") == (
        "veracity: 0 fixes applied, 2 races (3 fields) flagged for review (2026-11-05)")


def test_veracity_commit_counts_applied_fixes():
    report = {"races": [{"changes": [{"field": "x"}, {"field": "y"}]}]}
    assert vrr.commit_message(report, "2026-11-05") == (
        "veracity: 2 fixes applied, 0 flagged for review (2026-11-05)")


def test_veracity_workflow_uses_the_counted_subject():
    wf = (ROOT / ".github/workflows/rankings-veracity.yml").read_text()
    assert "no fixes needed" not in wf
    assert wf.count("--commit-message data/verification/last_run_report.json") == 2
