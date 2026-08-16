import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "race-data" / "bend-dirt-fest.json"


def _race():
    return json.loads(PROFILE.read_text())["race"]


def test_bend_dirt_fest_uses_verified_2027_course_and_schedule():
    race = _race()
    vitals = race["vitals"]

    assert race["slug"] == "bend-dirt-fest"
    assert vitals["date_specific"] == "2027: July 10"
    assert vitals["distance_mi"] == 54.7
    assert vitals["elevation_ft"] == 4016
    assert "8:15 AM" in vitals["start_time"]
    assert "62% unpaved" in vitals["route_options"][0]
    assert "mile 23 by 11:00 AM" in vitals["cutoff_time"]


def test_bend_dirt_fest_score_matches_the_official_rubric():
    race = _race()
    rating = race["gravel_god_rating"]
    dimensions = (
        "logistics",
        "length",
        "technicality",
        "elevation",
        "climate",
        "altitude",
        "adventure",
        "prestige",
        "race_quality",
        "experience",
        "community",
        "field_depth",
        "value",
        "expenses",
    )

    assert sum(rating[key] for key in dimensions) == 40
    assert rating["cultural_impact"] == 1
    assert round((40 + 1) / 70 * 100) == rating["overall_score"] == 59
    assert rating["tier"] == rating["display_tier"] == 3

    for key in dimensions:
        assert race["biased_opinion_ratings"][key]["score"] == rating[key]
    assert race["biased_opinion_ratings"]["cultural_impact"]["score"] == 1


def test_bend_dirt_fest_is_cleared_for_the_full_climber_ladder():
    race = _race()
    clearance = race["training_plan_clearance"]

    assert race["eligibility"]["race_plan_eligible"] is True
    assert clearance == {
        "status": "build_ready",
        "race_date": "2027-07-10",
        "event_window": "2027-07-10/2027-07-10",
        "ladder": "FULL-7",
        "variation": "Climber",
        "blockers": [],
        "guard": clearance["guard"],
    }
    assert "stale 49-mile" in clearance["guard"]
    assert race["course_description"]["ridewithgps_id"] == "54816842"
    assert "seven published TrainingPeaks plans (659261-659267)" in (
        race["source_review"]["discovery_note"]
    )
    assert "receipt-backed repair" in race["source_review"]["discovery_note"]


def test_bend_dirt_fest_citations_cover_the_controlling_sources():
    urls = {row["url"] for row in _race()["citations"]}

    assert "https://www.mudslingerevents.com/bend-dirt-fest" in urls
    assert "https://ridewithgps.com/routes/54816842" in urls
    assert "https://www.bikereg.com/bend-dirt-fest" in urls
    assert "https://obra.org/events/29106/results" in urls
    assert any(url.endswith("Bend-Dirt-Fest+Tech+Guide+20278426.pdf") for url in urls)
