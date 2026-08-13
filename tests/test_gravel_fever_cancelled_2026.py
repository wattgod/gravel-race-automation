import json
import sys
from pathlib import Path

from scripts.generate_index import generate_jsonld


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "wordpress"))
from generate_neo_brutalist import generate_page, normalize_race_data


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "race-data" / "gravel-fever.json"


def load_race():
    return json.loads(PROFILE.read_text(encoding="utf-8"))["race"]


def test_gravel_fever_is_not_presented_as_a_current_race():
    race = load_race()
    vitals = race["vitals"]

    assert vitals["date"] == "No current edition announced"
    assert vitals["date_specific"].startswith("Cancelled for 2026")
    assert "no replacement host" in vitals["date_specific"]
    assert "Closed" in vitals["registration"]
    assert race["research_metadata"]["validation_status"] == (
        "2026-cancelled-no-replacement-host-verified-2026-08-13"
    )
    assert race["eligibility"]["status"] == "cancelled"
    assert race["eligibility"]["race_plan_eligible"] is False


def test_historical_flagship_route_is_correctly_labeled():
    race = load_race()
    vitals = race["vitals"]

    assert vitals["distance_mi"] == 96.4
    assert vitals["elevation_ft"] == 4996
    assert "Historical" in race["course_description"]["character"]
    assert "future host" in race["course_description"]["signature_challenge"]


def test_cancellation_evidence_and_page_notice_are_present():
    race = load_race()
    urls = {citation["url"] for citation in race["citations"]}

    assert "https://structures.ffc.fr/epreuves-ffc-disciplines/gravel/coupe-france/" in urls
    assert "https://www.sporteco.com/gravel-fever-recherche-de-nouveaux-territoires-daccueil/" in urls
    assert race["taking_a_break"]["label"] == "2026 CANCELLED"
    assert "replacement host" in race["taking_a_break"]["line"]


def test_generated_surfaces_carry_cancellation_not_a_live_date():
    dates = json.loads((ROOT / "web" / "race-dates.json").read_text(encoding="utf-8"))
    index = json.loads((ROOT / "web" / "race-index.json").read_text(encoding="utf-8"))
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    html = generate_page(
        normalize_race_data(profile),
        index,
    )

    assert "gravel-fever" not in dates
    row = next(item for item in index if item["slug"] == "gravel-fever")
    assert row["distance_mi"] == 96.4
    assert "cancelled for 2026" in row["tagline"]
    assert "2026 CANCELLED" in html
    assert "replacement host" in html
    assert "20260926" not in html
    assert 'id="train-for-race"' not in html
    assert 'id="gg-pack-cta-default"' not in html

    jsonld = json.loads(
        (ROOT / "web" / "jsonld" / "gravel-fever.jsonld").read_text(
            encoding="utf-8"
        )
    )
    assert "startDate" not in jsonld
    assert jsonld["eventStatus"] == "https://schema.org/EventCancelled"


def test_jsonld_date_parser_does_not_invent_a_date_from_cancellation_prose():
    entry = {
        "name": "Cancelled Race",
        "slug": "cancelled-race",
        "tagline": "No current edition.",
        "discipline": "gravel",
    }
    profile = {
        "race": {
            "vitals": {
                "date_specific": (
                    "Cancelled for 2026 — funding ended; no replacement host or "
                    "2027 date announced"
                )
            },
            "taking_a_break": {"label": "2026 CANCELLED"},
        }
    }

    jsonld = generate_jsonld(entry, profile)

    assert "startDate" not in jsonld
    assert jsonld["eventStatus"] == "https://schema.org/EventCancelled"


def test_jsonld_date_parser_still_accepts_canonical_specific_dates():
    entry = {
        "name": "Scheduled Race",
        "slug": "scheduled-race",
        "tagline": "Current edition.",
        "discipline": "gravel",
    }
    profile = {"race": {"vitals": {"date_specific": "2027: May 15 (Saturday)"}}}

    jsonld = generate_jsonld(entry, profile)

    assert jsonld["startDate"] == "2027-05-15"


def test_jsonld_date_parser_accepts_weekday_and_month_abbreviation():
    entry = {
        "name": "Scheduled Race",
        "slug": "scheduled-race",
        "tagline": "Current edition.",
        "discipline": "gravel",
    }
    profile = {
        "race": {
            "vitals": {
                "date_specific": "2026: Saturday, Aug 22-23 (festival weekend)"
            }
        }
    }

    jsonld = generate_jsonld(entry, profile)

    assert jsonld["startDate"] == "2026-08-22"
