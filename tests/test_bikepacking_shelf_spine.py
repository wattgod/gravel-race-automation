"""WS-G race-page checks for the Ultra & Bikepacking shelf."""

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))

from generate_neo_brutalist import (  # noqa: E402
    build_coaching_footnote,
    build_custom_plan_offer,
    build_prep_strip,
    generate_page,
    load_race_data,
)


def _bikepacking_profiles():
    profiles = []
    for path in sorted((ROOT / "race-data").glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        race = raw.get("race", raw)
        rating = race.get("gravel_god_rating", {})
        vitals = race.get("vitals", {})
        discipline = (
            rating.get("discipline")
            or vitals.get("discipline")
            or race.get("discipline")
            or "gravel"
        )
        if discipline == "bikepacking":
            profiles.append(path)
    return profiles


def test_every_bikepacking_profile_suppresses_custom_plan_but_keeps_coaching():
    profiles = _bikepacking_profiles()
    assert profiles, "The catalog must contain bikepacking profiles."

    for path in profiles:
        rd = load_race_data(path)
        assert rd["discipline"] == "bikepacking", path.name
        assert build_custom_plan_offer(rd) == "", path.name
        assert build_prep_strip(rd) == "", path.name
        assert 'data-cta="approved_coaching"' in build_coaching_footnote(rd)


def test_gravel_custom_plan_and_coaching_are_unchanged():
    rd = load_race_data(ROOT / "race-data" / "unbound-200.json")

    assert rd["discipline"] == "gravel"
    assert 'data-cta="approved_custom_plan"' in build_custom_plan_offer(rd)
    assert 'data-cta="approved_coaching"' in build_coaching_footnote(rd)


def test_tour_divide_page_has_spine_and_consent_without_custom_plan():
    rd = load_race_data(ROOT / "race-data" / "tour-divide.json")
    html = generate_page(rd)

    assert 'data-page-format="spine-v2-approved"' in html
    assert 'id="gg-consent-banner"' in html
    assert 'data-cta="approved_custom_plan"' not in html
    assert 'data-measure-section="custom-plan"' not in html
    assert 'data-cta="approved_coaching"' in html
    assert 'data-measure-section="coaching"' in html
