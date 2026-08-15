"""Current-source contracts for the 2026 Hellhole stage race."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLUG = "hellhole-gravel-grind"
MARKETPLACE_URL = (
    "https://www.trainingpeaks.com/training-plans/cycling/tp-669713/p"
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_hellhole_profile_uses_current_official_stage_race_facts() -> None:
    race = load(ROOT / f"race-data/{SLUG}.json")["race"]

    assert race["vitals"]["date_specific"] == "2026: October 2-4"
    assert race["vitals"]["distance_mi"] == 150
    assert race["vitals"]["elevation_ft"] is None
    assert race["vitals"]["gain_display"] == "Not published"
    assert race["terrain"]["features"][:3] == [
        "Optional six-mile Friday night prologue",
        "Approximately 75 miles on Saturday",
        "Approximately 75 miles on Sunday",
    ]
    assert race["gravel_god_rating"]["overall_score"] == 50
    assert race["gravel_god_rating"]["tier"] == 3
    assert race["logistics"]["official_site"] == (
        "https://www.mtpleasantvelo.org/hellhole-gravel-grind-stage-race"
    )
    assert race["training_config"]["marketplace_variables"][
        "trainingpeaks_url"
    ] == MARKETPLACE_URL


def test_hellhole_generated_discovery_assets_match_the_profile() -> None:
    index = load(ROOT / "web/race-index.json")
    row = next(item for item in index if item["slug"] == SLUG)
    jsonld = load(ROOT / f"web/jsonld/{SLUG}.jsonld")
    pack = load(ROOT / f"web/race-packs/{SLUG}.json")

    assert row["elevation_ft"] is None
    assert row["overall_score"] == 50
    assert "optional night prologue" in row["tagline"]
    assert jsonld["startDate"] == "2026-10-02"
    assert jsonld["url"] == (
        "https://www.mtpleasantvelo.org/hellhole-gravel-grind-stage-race"
    )
    assert "6,000" not in json.dumps(pack)
    assert "6000" not in json.dumps(pack)
    assert "fast, flat forest gravel" in pack["pack_summary"]
