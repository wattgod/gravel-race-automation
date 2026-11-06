"""Every tire number on the site traces to a row in the BRR snapshot.

data/tires/lab/brr-cx-gravel.json is the snapshot; scripts/import_tire_lab_data.py
writes data/tires/{id}.json from it. These tests fail if a tire file drifts from
the snapshot, if a stored pick isn't lab-tested, or if a stored pick's watts
don't match the test it cites.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TIRE_DIR = ROOT / "data" / "tires"
LAB_DIR = TIRE_DIR / "lab"
RACE_DIR = ROOT / "race-data"

sys.path.insert(0, str(ROOT / "scripts"))
from import_tire_lab_data import brr_test_psi  # noqa: E402

SNAPSHOT = json.loads((LAB_DIR / "brr-cx-gravel.json").read_text(encoding="utf-8"))
ROWS = {r["brr_id"]: r for r in SNAPSHOT["rows"]}
CATALOG = {e["id"]: e for e in json.loads((LAB_DIR / "catalog.json").read_text(encoding="utf-8"))}
TIRES = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(TIRE_DIR.glob("*.json"))}

# brr_tests fields copied straight from the snapshot row
ROW_FIELDS = ("width_mm", "measured_width_mm", "year", "model", "rr_watts",
              "puncture_tread", "wet_grip", "knob_center_mm", "knob_edge_mm",
              "weight_g", "url")


def stored_picks():
    """(race slug, pick dict, tested width or None) for every stored pick."""
    out = []
    for path in sorted(RACE_DIR.glob("*.json")):
        race = json.loads(path.read_text(encoding="utf-8")).get("race", {})
        tr = race.get("tire_recommendations") or {}
        for p in tr.get("primary", []):
            out.append((path.stem, p, p.get("tested_width_mm")))
        split = tr.get("front_rear_split") or {}
        if split.get("applicable"):
            for side in ("front", "rear"):
                out.append((path.stem, split[side], None))
    return out


PICKS = stored_picks()


def test_import_check_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "import_tire_lab_data.py"), "--check"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_catalog_tire_has_a_file():
    assert set(CATALOG) <= set(TIRES), sorted(set(CATALOG) - set(TIRES))


def test_snapshot_names_its_source_and_protocol():
    assert SNAPSHOT["source"].startswith("https://www.bicyclerollingresistance.com/")
    assert SNAPSHOT["protocol"]
    assert SNAPSHOT["fetched"]


@pytest.mark.parametrize("tire_id", sorted(CATALOG))
def test_brr_tests_equal_their_snapshot_rows(tire_id):
    tire = TIRES[tire_id]
    rows = [ROWS[b] for b in CATALOG[tire_id]["brr"]]
    assert len(tire["brr_tests"]) == len(rows)
    by_model = {r["model"]: r for r in rows}
    for test in tire["brr_tests"]:
        row = by_model[test["model"]]
        for field in ROW_FIELDS:
            assert test[field] == row[field], (tire_id, test["width_mm"], field)
        assert test["test_psi"] == brr_test_psi(row["measured_width_mm"])


@pytest.mark.parametrize("tire_id", sorted(TIRES))
def test_no_number_without_a_test(tire_id):
    """crr and weight values exist only where a BRR test measured them."""
    tire = TIRES[tire_id]
    by_width = {str(t["width_mm"]): t for t in tire.get("brr_tests", [])}
    for width, watts in (tire.get("crr_watts_at_29kmh") or {}).items():
        assert width in by_width, (tire_id, "crr", width)
        assert watts == by_width[width]["rr_watts"], (tire_id, "crr", width)
    for width, grams in (tire.get("weight_grams") or {}).items():
        assert width in by_width, (tire_id, "weight", width)
        assert grams == round(by_width[width]["weight_g"]), (tire_id, "weight", width)
    if not tire.get("lab_tested"):
        assert not any(t["width_mm"] >= 38 for t in tire.get("brr_tests", []))


def test_there_are_stored_picks():
    assert len(PICKS) > 500


@pytest.mark.parametrize("slug,pick,_w", PICKS, ids=[f"{s}-{p['tire_id']}" for s, p, _ in PICKS])
def test_every_stored_pick_is_lab_tested(slug, pick, _w):
    tire = TIRES.get(pick["tire_id"])
    assert tire is not None, (slug, pick["tire_id"])
    assert tire["lab_tested"], (slug, pick["tire_id"])


@pytest.mark.parametrize("slug,pick,width", [x for x in PICKS if x[2] is not None],
                         ids=[f"{s}-{p['tire_id']}" for s, p, w in PICKS if w is not None])
def test_pick_crr_equals_its_tested_width(slug, pick, width):
    tire = TIRES[pick["tire_id"]]
    tests = [t for t in tire["brr_tests"] if t["width_mm"] == width]
    assert tests, (slug, pick["tire_id"], width)
    assert pick["crr_watts"] in {t["rr_watts"] for t in tests}, (slug, pick["tire_id"], width)


def test_every_primary_pick_names_its_tested_width():
    missing = [(s, p["tire_id"]) for s, p, w in PICKS if "rank" in p and w is None]
    assert not missing, missing[:5]
