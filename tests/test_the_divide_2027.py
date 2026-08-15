import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "race-data" / "the-divide.json"


def load_race() -> dict:
    return json.loads(PROFILE.read_text(encoding="utf-8"))["race"]


def test_the_divide_2027_uses_the_organizers_recurrence_rule() -> None:
    race = load_race()
    vitals = race["vitals"]

    assert race["slug"] == vitals["slug"] == "the-divide"
    assert vitals["date_specific"] == "2027: July 25"
    assert vitals["distance_mi"] == 52
    assert vitals["elevation_ft"] == 4500
    assert "11:00 AM" in vitals["start_time"]
    assert race["logistics"]["official_site"] == (
        "https://hardracingevents.com/events/the-divide/events/the-divide/"
    )
    citation_text = " ".join(item["snippet"] for item in race["citations"])
    assert "last-Sunday-of-July" in citation_text
    assert "return for the 2027 season" in citation_text
    assert "final 2027 registration and rider documents remain pending" in (
        race["logistics"]["overview"]
    )


def test_the_divide_regrade_follows_the_scoring_bible() -> None:
    race = load_race()
    rating = race["gravel_god_rating"]
    dimensions = (
        "adventure",
        "altitude",
        "climate",
        "community",
        "elevation",
        "expenses",
        "experience",
        "field_depth",
        "length",
        "logistics",
        "prestige",
        "race_quality",
        "technicality",
        "value",
        "cultural_impact",
    )

    calculated = round(sum(rating[key] for key in dimensions) / 70 * 100)
    assert calculated == rating["overall_score"] == 51
    assert rating["tier"] == race["vitals"]["tier"] == 3
    assert rating["tier_label"] == "TIER 3"


def test_the_divide_generated_surfaces_match_the_profile() -> None:
    race = load_race()
    index = {
        row["slug"]: row
        for row in json.loads((ROOT / "web/race-index.json").read_text())
    }
    row = index["the-divide"]
    assert row["overall_score"] == 51
    assert row["tier"] == 3
    assert row["year"] == 2027
    assert row["distance_mi"] == 52
    assert row["elevation_ft"] == 4500

    jsonld = json.loads(
        (ROOT / "web/jsonld/the-divide.jsonld").read_text(encoding="utf-8")
    )
    assert jsonld["name"] == race["name"]
    assert jsonld["url"] == race["logistics"]["official_site"]
