import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLUGS = {
    "hysk-gravel-classic-yakurai": {
        "date": "2026: August 22",
        "distance_mi": 66.5,
        "elevation_ft": 8563,
        "score": 64,
        "official": "https://gravelclassic.com/course/",
    },
    "khomas100": {
        "date": "2026: August 22",
        "distance_mi": 88.9,
        "elevation_ft": 7546,
        "score": 71,
        "official": "https://khomas100.com.na/routes/",
    },
    "graean-cymru": {
        "date": "2026: September 5-6",
        "distance_mi": 70.2,
        "elevation_ft": 6795,
        "score": 76,
        "official": "https://gloriousgravel.com/product/gravel-race/graean-cymru/",
    },
}


def load_profile(slug: str) -> dict:
    return json.loads((ROOT / "race-data" / f"{slug}.json").read_text())["race"]


def test_new_uci_qualifiers_have_current_official_facts() -> None:
    for slug, expected in SLUGS.items():
        race = load_profile(slug)
        vitals = race["vitals"]
        assert race["slug"] == slug
        assert vitals["slug"] == slug
        assert vitals["date_specific"] == expected["date"]
        assert vitals["distance_mi"] == expected["distance_mi"]
        assert vitals["elevation_ft"] == expected["elevation_ft"]
        assert vitals["discipline"] == "gravel"
        assert expected["official"] in {item["url"] for item in race["citations"]}


def test_new_uci_qualifier_scores_follow_the_scoring_bible() -> None:
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
    )
    for slug, expected in SLUGS.items():
        race = load_profile(slug)
        rating = race["gravel_god_rating"]
        calculated = round(
            (sum(rating[key] for key in dimensions) + rating["cultural_impact"])
            / 70
            * 100
        )
        assert calculated == rating["overall_score"] == expected["score"]
        assert rating["tier"] == race["vitals"]["tier"] == 2


def test_new_uci_qualifiers_are_in_generated_index_and_jsonld() -> None:
    index = {
        item["slug"]: item
        for item in json.loads((ROOT / "web" / "race-index.json").read_text())
    }
    for slug, expected in SLUGS.items():
        assert index[slug]["overall_score"] == expected["score"]
        assert index[slug]["tier"] == 2
        jsonld = ROOT / "web" / "jsonld" / f"{slug}.jsonld"
        assert jsonld.exists()
        assert json.loads(jsonld.read_text())["name"] == load_profile(slug)["name"]
