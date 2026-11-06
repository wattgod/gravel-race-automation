"""Date-refresh queues pick races by edition date, not year.

"2026: August 30" is stale on 2026-11-05; every queue (weekly scraper,
batch search, YouTube research, audits) must pick it up.
"""

import json
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import race_facts as rf  # noqa: E402
import scrape_utils  # noqa: E402
from extract_dates import is_stale  # noqa: E402

NOV_5 = date(2026, 11, 5)


def _race(ds, **extra):
    return {"vitals": {"date_specific": ds}, **extra}


@pytest.mark.parametrize("ds,expected", [
    ("2026: August 30", True),
    ("2027: June 5", False),
    ("2027: TBD", True),
    ("", True),
    ("Status: DROPPED — no 2027 edition", False),
])
def test_needs_date_check(ds, expected):
    assert rf.needs_date_check(_race(ds), NOV_5) is expected


def test_needs_date_check_skips_taking_a_break():
    race = _race("2025: August 3", taking_a_break={"label": "Not running"})
    assert rf.needs_date_check(race, NOV_5) is False


def test_extract_dates_is_stale_by_date():
    assert is_stale("2026: August 30", NOV_5)
    assert not is_stale("2027: June 5", NOV_5)


@pytest.fixture
def race_dir(tmp_path, monkeypatch):
    for slug, ds in [("ran", "2026: August 30"), ("next", "2027: June 5"),
                     ("old", "2025: May 1")]:
        (tmp_path / f"{slug}.json").write_text(json.dumps({"race": {
            "name": slug, "vitals": {"date_specific": ds},
            "logistics": {"official_site": f"https://{slug}.example"},
            "gravel_god_rating": {"tier": 2}}}))
    monkeypatch.setattr(scrape_utils, "RACE_DATA_DIR", tmp_path)
    monkeypatch.setenv("GG_TODAY", "2026-11-05")
    return tmp_path


def test_scraper_stale_only_includes_this_years_past_edition(race_dir):
    sites = scrape_utils.load_official_sites(stale_only=True)
    assert set(sites) == {"ran", "old"}


def test_weekly_refresh_caps_the_scrape():
    wf = (ROOT / ".github/workflows/weekly-fact-refresh.yml").read_text()
    assert "--stale-only --limit 50" in wf


def test_next_edition_date_reads_old_extracts():
    assert scrape_utils.next_edition_date({"date_2026": "2026-06-06"}) == "2026-06-06"
    assert scrape_utils.next_edition_date(
        {"next_edition_date": "2027-06-05", "date_2026": "x"}) == "2027-06-05"
    assert scrape_utils.next_edition_date(None) is None


def test_no_year_compare_staleness_left():
    """Year compares ('< 2026', '>= 2026') call August 30 fresh in November."""
    for name in ("scrape_utils.py", "batch_date_search.py", "extract_dates.py",
                 "audit_date_freshness.py", "youtube_research.py",
                 "fact_check_profiles.py"):
        text = (ROOT / "scripts" / name).read_text()
        assert "< 2026" not in text and ">= 2026" not in text, name
