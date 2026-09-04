"""Regression pins for the 2026-09-04 immune data fixes.

Issues: #68 (spring-valley-100 tier math), #59 (marly-grav score drift),
#114 (four races missing coordinates), plus baseline acceptance of the three
code-only fingerprints introduced by the fingerprint() fix (#151, #50).
Authority for score/tier math: docs/GRAVEL_GOD_SCORING_SYSTEM.md.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SCORE_FIELDS = [
    "logistics", "length", "technicality", "elevation", "climate",
    "altitude", "adventure", "prestige", "race_quality", "experience",
    "community", "field_depth", "value", "expenses",
]


def _race(slug: str) -> dict:
    return json.loads((ROOT / "race-data" / f"{slug}.json").read_text())["race"]


def _index() -> dict[str, dict]:
    return {row["slug"]: row for row in json.loads((ROOT / "web" / "race-index.json").read_text())}


# ── #59 marly-grav: criteria were re-rated (elevation 1→3, commit 8cfb0db6)
#    after the score was set in 79dc0753; the score never followed. ──────────
def test_marly_grav_score_follows_its_criteria():
    r = _race("marly-grav")["gravel_god_rating"]
    raw = sum(r[f] for f in SCORE_FIELDS) + r.get("cultural_impact", 0)
    assert raw == 34
    assert r["overall_score"] == round(raw / 70 * 100) == 49
    # 49 stays inside the T3 band (>= 45, < 60): no tier change.
    assert r["tier"] == r["display_tier"] == 3
    assert r["tier_label"] == "TIER 3"


# ── #68 spring-valley-100: score 47 (33/70) with prestige 1 → tier by score
#    alone → T3. There is no downward override in the scoring system. ────────
def test_spring_valley_100_is_tier_3_by_score():
    r = _race("spring-valley-100")["gravel_god_rating"]
    assert sum(r[f] for f in SCORE_FIELDS) == 33
    assert r["overall_score"] == 47
    assert r["prestige"] == 1
    assert (r["tier"], r["display_tier"], r["tier_label"]) == (3, 3, "TIER 3")
    assert "tier_override_reason" not in r
    # The rating note must not contradict the tier it sits next to.
    assert "Tier 4" not in r["score_note"]


# ── #114 geocoding: each result must sit where the location string says.
#    Nominatim's fallbacks put graean-cymru in Cumbria (UK centroid) and
#    khomas100 75 km south of Windhoek; both are pinned via MANUAL_COORDS. ──
@pytest.mark.parametrize("slug,lat_range,lng_range,place", [
    ("graean-cymru", (52.9, 53.3), (-3.8, -3.3), "Llyn Brenig, Denbighshire, Wales"),
    ("hysk-gravel-classic-yakurai", (38.4, 38.8), (140.6, 141.0), "Kami, Miyagi (not Kami in Hyogo/Kochi)"),
    ("khomas100", (-22.8, -22.3), (16.9, 17.3), "Windhoek, Namibia (race start)"),
    ("the-divide", (44.2, 44.6), (-85.6, -85.2), "Manton, Michigan"),
])
def test_geocoded_races_land_where_their_location_says(slug, lat_range, lng_range, place):
    v = _race(slug)["vitals"]
    assert v.get("lat") is not None and v.get("lng") is not None, f"{slug} still has no coords"
    assert lat_range[0] <= v["lat"] <= lat_range[1], f"{slug} lat {v['lat']} is not {place}"
    assert lng_range[0] <= v["lng"] <= lng_range[1], f"{slug} lng {v['lng']} is not {place}"


def test_manual_coords_pin_the_two_nominatim_traps():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import geocode_races
    assert geocode_races.MANUAL_COORDS["graean-cymru"] == (53.0922, -3.5288)
    assert geocode_races.MANUAL_COORDS["khomas100"] == (-22.5776, 17.0773)


# ── Generated artifacts carry the corrected values (index feeds search,
#    JSON-LD, embed widget; a stale index silently ships old tiers). ────────
def test_search_index_carries_the_corrected_values():
    idx = _index()
    assert idx["spring-valley-100"]["tier"] == 3
    assert idx["marly-grav"]["overall_score"] == 49
    for slug in ("graean-cymru", "hysk-gravel-classic-yakurai", "khomas100", "the-divide"):
        assert idx[slug].get("lat") is not None, f"{slug} coords missing from race-index.json"
    embed = {e["s"]: e for e in json.loads((ROOT / "web" / "embed" / "embed-data.json").read_text())}
    assert embed["spring-valley-100"]["t"] == 3
    assert embed["marly-grav"]["sc"] == 49
    jsonld = json.loads((ROOT / "web" / "jsonld" / "marly-grav.jsonld").read_text())
    assert jsonld["aggregateRating"]["ratingValue"] == "49"


# ── Baseline accepts the three code-only fingerprints (#50 known noise). ────
def test_baseline_accepts_code_only_volatile_fingerprints():
    data = json.loads((ROOT / "immune" / "baseline.json").read_text())
    fps = data["fingerprints"]
    for code in ("live-check-challenged", "prep-kit-check-blocked", "deploy-parity-skipped"):
        assert code in fps, f"{code} missing from immune/baseline.json"
    # --accept-baseline writes a sorted, de-duplicated list; hand edits must match.
    assert fps == sorted(set(fps))
