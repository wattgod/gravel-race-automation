"""Tire picks stay honest: right discipline, right course read, real tires.

Guards the Nov 2026 tire audit fixes:
- the surface classifier read "rain" inside "terrain" and "bog" inside "bog
  down", and treated "occasional sand/mud" as a mud course (Gravel Worlds got
  mud tires);
- MTB and bikepacking races got gravel-bike picks;
- stored picks drifted from what the matcher would produce;
- picks named widths the tire isn't made in;
- tire names didn't link to their /tire/ pages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
sys.path.insert(0, str(ROOT / "scripts"))

from generate_tire_guide import (  # noqa: E402
    SURFACE_MIXED,
    SURFACE_MUDDY,
    build_race_profile,
    build_tire_cards,
    load_tire_database,
)
from generate_neo_brutalist import build_tire_picks, normalize_race_data  # noqa: E402
from enrich_tire_recommendations import build_enrichment, gets_tire_picks  # noqa: E402
from push_wordpress import REDIRECT_BLOCK, TIRE_GUIDES_WITHDRAWN  # noqa: E402
from race_facts import race_discipline  # noqa: E402

TIRES = {t["id"]: t for t in load_tire_database()}


def _races():
    for path in sorted((ROOT / "race-data").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        yield path.stem, data, data.get("race", data)


RACES = list(_races())
WITH_PICKS = [(s, d, r) for s, d, r in RACES
              if (r.get("tire_recommendations") or {}).get("primary")]


def _profile(terrain: dict, distance_mi: int = 80) -> dict:
    raw = {"terrain": terrain, "vitals": {"distance_mi": distance_mi}}
    rd = {"slug": "t", "name": "T", "vitals": {"distance_mi": distance_mi}}
    return build_race_profile(rd, raw, {})


# ── Classifier ───────────────────────────────────────────────


class TestCourseRead:
    def test_terrain_is_not_rain(self):
        p = _profile({"surface": "Rolling terrain", "technical_rating": 2})
        assert not p["needs_wet"]

    def test_bog_down_is_not_a_bog(self):
        p = _profile({"surface": "Sandy sections bog down wheels", "technical_rating": 2})
        assert not p["needs_mud"] and not p["mud_risk"]

    def test_occasional_mud_is_a_risk_not_a_mud_course(self):
        p = _profile({"surface": "Loose gravel, occasional sand/mud.", "technical_rating": 2})
        assert p["surface_category"] == SURFACE_MIXED
        assert not p["needs_mud"] and p["mud_risk"]

    def test_mud_when_wet_is_a_risk(self):
        p = _profile({"surface": "Clay mud when wet becomes peanut butter", "technical_rating": 2})
        assert not p["needs_mud"] and p["mud_risk"]

    def test_mud_sectors_make_a_mud_course(self):
        p = _profile({"surface": "Rail trail, farm lanes and infamous mud sectors",
                      "technical_rating": 2})
        assert p["surface_category"] == SURFACE_MUDDY

    def test_negated_chunk_is_not_sharp(self):
        p = _profile({"surface": "Red clay. Not the chunky gravel of Unbound.",
                      "technical_rating": 2})
        assert not p["needs_puncture"]

    def test_rocky_mountains_are_not_rocky_ground(self):
        p = _profile({"surface": "Rocky Mountain forest roads", "technical_rating": 2})
        assert not p["needs_puncture"]

    def test_weather_never_sets_the_surface(self):
        raw = {"terrain": {"surface": "Smooth gravel", "technical_rating": 2},
               "vitals": {"distance_mi": 60}}
        rd = {"slug": "t", "name": "T", "vitals": {"distance_mi": 60}}
        p = build_race_profile(rd, raw, {"precip_chance_pct": 80})
        assert p["surface_category"] == SURFACE_MIXED
        assert p["needs_wet"]  # still weights wet grip


# ── Race data ────────────────────────────────────────────────


def test_only_gravel_races_have_picks():
    bad = [(s, race_discipline(r)) for s, _, r in RACES
           if "tire_recommendations" in r and not gets_tire_picks(r)]
    assert not bad, f"non-gravel races with gravel tire picks: {bad}"


def test_withdrawn_guide_redirects_never_hide_a_live_guide():
    by_slug = {s: r for s, _, r in RACES}
    for slug in TIRE_GUIDES_WITHDRAWN:
        assert slug in by_slug, f"{slug} not in race-data"
        assert "tire_recommendations" not in by_slug[slug], (
            f"{slug} has tire picks again; drop it from TIRE_GUIDES_WITHDRAWN "
            "or its guide will redirect away")
    assert "/tires/?$ /race/$1/ [R=301,L]" in REDIRECT_BLOCK
    assert "specialized-pathfinder-pro-47" in REDIRECT_BLOCK


@pytest.mark.parametrize("slug,data,race", WITH_PICKS, ids=[s for s, _, _ in WITH_PICKS])
def test_picks_are_real_offered_and_distinct(slug, data, race):
    tr = race["tire_recommendations"]
    ids = [p["tire_id"] for p in tr["primary"]]
    assert len(ids) == len(set(ids)), f"duplicate pick in {ids}"
    picks = list(tr["primary"])
    split = tr.get("front_rear_split") or {}
    if split.get("applicable"):
        picks += [{"tire_id": split[k]["tire_id"],
                   "recommended_width_mm": split[k]["width_mm"]} for k in ("front", "rear")]
    for p in picks:
        tire = TIRES.get(p["tire_id"])
        assert tire, f"unknown tire {p['tire_id']}"
        assert p["recommended_width_mm"] in tire["widths_mm"], (
            f"{tire['id']} isn't made in {p['recommended_width_mm']}mm")
    for p in tr["primary"]:
        why = p.get("why", "")
        assert why[:1].isupper() and why.rstrip().endswith("."), f"why line: {why!r}"


def test_stored_picks_match_the_matcher():
    """Picks are stored in race JSON; a matcher or tire-data change must be
    followed by a re-run or race pages show stale picks."""
    stale = []
    tire_db = list(TIRES.values())
    for slug, data, race in WITH_PICKS:
        rd = normalize_race_data(data)
        rd["slug"] = rd.get("slug") or slug
        now = build_enrichment(rd, race, tire_db, slug)
        if [p["tire_id"] for p in now["primary"]] != \
                [p["tire_id"] for p in race["tire_recommendations"]["primary"]]:
            stale.append(slug)
    assert not stale, (
        f"{len(stale)} races have stale picks, e.g. {stale[:5]}. Run: "
        "python3 scripts/enrich_tire_recommendations.py --force --existing-only")


def test_sourced_width_floor_survives_a_rerun():
    """West Coast Gravel's organizer says 45mm or wider. The floor lives in
    tire_recommendations.min_width_mm so the matcher can't drop it."""
    slug, data, race = next(x for x in WITH_PICKS if x[0] == "west-coast-gravel")
    rd = normalize_race_data(data)
    rd["slug"] = slug
    now = build_enrichment(rd, race, list(TIRES.values()), slug)
    assert now["min_width_mm"] == 45 and now["min_width_source"]
    assert now["recommended_width_mm"] >= 45
    widths = [p["recommended_width_mm"] for p in now["primary"]]
    split = now["front_rear_split"]
    if split.get("applicable"):
        widths += [split["front"]["width_mm"], split["rear"]["width_mm"]]
    assert min(widths) >= 45, widths


def test_every_width_floor_names_its_source():
    bad = [s for s, _, r in WITH_PICKS
           if r["tire_recommendations"].get("min_width_mm")
           and not r["tire_recommendations"].get("min_width_source")]
    assert not bad, f"min_width_mm without min_width_source: {bad}"


# ── Rendering ────────────────────────────────────────────────


def test_race_page_links_each_pick_to_its_tire_page():
    slug, data, _ = next(x for x in WITH_PICKS if x[0] == "unbound-200")
    rd = normalize_race_data(data)
    rd["slug"] = slug
    html = build_tire_picks(rd)
    for p in data["race"]["tire_recommendations"]["primary"]:
        assert f'href="/tire/{p["tire_id"]}/"' in html
    assert "W</div>" not in html and " · 32W" not in html


def test_tire_guide_links_each_pick_to_its_tire_page():
    picks = [{"tire": TIRES["vittoria-terreno-mix"], "width": 40}]
    html = build_tire_cards(picks, _profile({"technical_rating": 2}), "Test Race")
    assert 'href="/tire/vittoria-terreno-mix/"' in html
