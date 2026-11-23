"""Station climate normals may back the climate rating only."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_neo_brutalist import _rating_citation_refs  # noqa: E402

RACE = {
    "citations": [
        {"url": "https://example.org/route", "category": "route", "label": "Route"},
        {"url": "https://example.org/", "category": "official", "label": "Official site"},
        {
            "url": "https://example.org/data/normals.csv",
            "category": "weather",
            "label": "Climate normals: August daily mean 17.2 C, field data",
        },
    ]
}


def test_weather_source_is_never_matched_to_another_rating():
    # "data", "mean" and "field" all overlap the weather label.
    text = "Field size data remain unknown; that could mean anything."
    for dimension in ("field_depth", "logistics", "expenses", "value", "altitude"):
        assert 3 not in _rating_citation_refs(RACE, dimension, text), dimension


def test_weather_source_still_backs_the_climate_rating():
    assert _rating_citation_refs(RACE, "climate", "August averages 17 C with rain.") == [3]


def test_explicit_refs_still_win():
    assert _rating_citation_refs(RACE, "field_depth", "anything", [3]) == [3]


def test_profiles_with_station_normals_link_them_from_climate_only():
    for slug in ("gravel-grit-n-grind", "gravel-tour-hlinsko", "the-wolf-dronninglund"):
        race = json.loads((ROOT / "race-data" / f"{slug}.json").read_text(encoding="utf-8"))["race"]
        weather = [i for i, c in enumerate(race["citations"], 1) if c["category"] == "weather"]
        assert len(weather) == 1, slug
        for dimension, rating in race["biased_opinion_ratings"].items():
            if not isinstance(rating, dict):
                continue
            refs = _rating_citation_refs(
                race, dimension, rating.get("explanation") or "", rating.get("citation_refs")
            )
            assert (weather[0] in refs) == (dimension == "climate"), (slug, dimension)
