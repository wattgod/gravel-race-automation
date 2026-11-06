#!/usr/bin/env python3
"""Build the tire database from independent lab data.

Sources, all committed under data/tires/lab/:
- brr-cx-gravel.json: rows from bicyclerollingresistance.com's CX/Gravel
  table (free columns only), one per tested tire and width.
- catalog.json: which tires we carry, which BRR rows belong to each, the
  widths each comes in and where that list came from.

Every measured field in data/tires/{id}.json (rolling resistance, weight,
puncture, wet grip, knob height) is written from the BRR snapshot here, so a
number on the site always traces to one BRR test page. Fields BRR does not
measure (mud clearance, tread type) are our call and stay in the catalog.

Usage:
    python3 scripts/import_tire_lab_data.py                      # rebuild tire JSON
    python3 scripts/import_tire_lab_data.py --check              # exit 1 if stale
    python3 scripts/import_tire_lab_data.py --listing page.html  # refresh snapshot
        (save https://www.bicyclerollingresistance.com/cx-gravel-reviews first)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TIRE_DIR = ROOT / "data" / "tires"
LAB_DIR = TIRE_DIR / "lab"
CATALOG = LAB_DIR / "catalog.json"
SNAPSHOT = LAB_DIR / "brr-cx-gravel.json"
BRR_LISTING_URL = "https://www.bicyclerollingresistance.com/cx-gravel-reviews"
BRR_PROTOCOL = ("Single tire on BRR's drum at 28.8 km/h with a 42.5 kg load, "
                "at BRR's 'low' pressure for the tire's measured width.")

# BRR's "low" test pressure by measured casing width (from the table header).
BRR_LOW_PSI = ((32, 44), (35, 40), (38, 36), (42, 33), (46, 31), (99, 28))

# A tire is pickable once BRR has tested it at a gravel race width.
MIN_TESTED_WIDTH_MM = 38

# Labels from measured values. The site shows the number; the label is a
# reading aid. Cutoffs sit near the thirds of the gravel tires BRR has tested.
PUNCTURE_HIGH, PUNCTURE_MODERATE = 45, 35      # BRR total puncture score, tread
WET_GOOD, WET_FAIR = 75, 65                    # BRR wet grip (hard surface)
RR_FAST, RR_SLOW = 17.0, 22.0                  # watts, BRR low pressure

# Fields carried over from an existing tire file untouched.
KEEP = ("tagline", "tread_description", "best_conditions", "worst_conditions",
        "status", "race_appearances", "community_reviews", "comparable_tires",
        "versions", "last_enriched")
KEY_ORDER = ("id", "name", "brand", "casing", "widths_mm", "widths_source",
             "tread_type", "tread_description", "tagline", "best_conditions",
             "worst_conditions", "tubeless_ready", "msrp_usd", "msrp_source",
             "lab_tested", "brr_tests", "brr_urls_by_width",
             "crr_watts_at_29kmh", "weight_grams", "puncture_resistance",
             "wet_traction", "mud_clearance", "strengths", "weaknesses",
             "recommended_use", "avoid_use", "status", "race_appearances",
             "community_reviews", "comparable_tires", "versions",
             "last_enriched")


def brr_test_psi(measured_mm: float) -> int:
    for upper, psi in BRR_LOW_PSI:
        if measured_mm <= upper:
            return psi
    return BRR_LOW_PSI[-1][1]


def parse_listing(html: str) -> list:
    """Free columns of BRR's CX/Gravel table, one dict per row."""
    from bs4 import BeautifulSoup  # only needed to refresh the snapshot

    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.find("table", id="tableTirePagesData").find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 18:
            continue

        def num(cls):
            el = tr.find(class_=cls)
            try:
                return float(el.get_text(strip=True))
            except (AttributeError, ValueError):
                return None

        rows.append({
            "brr_id": tds[0].find("input")["id"],
            "model": f'{tds[1].get_text(strip=True)} {tds[2].get_text(" ", strip=True)}',
            "year": int(tds[3].get_text(strip=True)),
            "url": "https://www.bicyclerollingresistance.com" + tds[2].find("a")["href"],
            "width_mm": int(num("widths")),
            "measured_width_mm": num("widthm"),
            "weight_g": num("mweight"),
            "rr_watts": num("rrM"),
            "puncture_tread": num("pr"),
            "wet_grip": num("wga"),
            "knob_center_mm": num("knob"),
            "knob_edge_mm": num("knobedge"),
        })
    return rows


def refresh_snapshot(listing_path: Path, catalog: list) -> None:
    wanted = {b for c in catalog for b in c["brr"]}
    rows = {r["brr_id"]: r for r in parse_listing(listing_path.read_text(encoding="utf-8"))}
    missing = sorted(wanted - rows.keys())
    if missing:
        sys.exit(f"BRR listing no longer has: {missing}")
    snapshot = {
        "source": BRR_LISTING_URL,
        "fetched": date.today().isoformat(),
        "protocol": BRR_PROTOCOL,
        "rows": [rows[b] for b in sorted(wanted)],
    }
    SNAPSHOT.write_text(json.dumps(snapshot, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(wanted)} BRR rows to {SNAPSHOT.relative_to(ROOT)}")


def _fmt(v: float) -> str:
    return f"{v:g}"


def label_puncture(score):
    if score is None:
        return None
    return "high" if score >= PUNCTURE_HIGH else "moderate" if score >= PUNCTURE_MODERATE else "low"


def label_wet(score):
    if score is None:
        return None
    return "good" if score >= WET_GOOD else "fair" if score >= WET_FAIR else "poor"


def reference_test(tests: list) -> dict:
    """The test closest to 45mm stands for the tire in its labels."""
    return min(tests, key=lambda t: (abs(t["width_mm"] - 45), -t["year"]))


def describe(ref: dict, mud: str) -> dict:
    """Strengths, weaknesses and use tags, each stated from a measured value."""
    w = ref["width_mm"]
    strengths, weaknesses, use, avoid = [], [], [], []
    rr, pr, wet = ref["rr_watts"], ref["puncture_tread"], ref["wet_grip"]
    if rr <= RR_FAST:
        strengths.append(f"Rolls fast: {_fmt(rr)} W at {w}mm on BRR's drum")
        use.append("fast gravel")
    elif rr >= RR_SLOW:
        weaknesses.append(f"Slow rolling: {_fmt(rr)} W at {w}mm on BRR's drum")
        avoid.append("fast smooth courses")
    if pr >= PUNCTURE_HIGH:
        strengths.append(f"Tough tread: puncture score {_fmt(pr)}")
        use.append("sharp rock")
    elif pr < PUNCTURE_MODERATE:
        weaknesses.append(f"Thin tread: puncture score {_fmt(pr)}")
        avoid.append("sharp rock")
    if wet >= WET_GOOD:
        strengths.append(f"Wet grip {_fmt(wet)} on BRR's wet test")
        use.append("wet roads")
    elif wet < WET_FAIR:
        weaknesses.append(f"Wet grip {_fmt(wet)} on BRR's wet test")
        avoid.append("wet roads")
    if ref["knob_edge_mm"] >= 2.3:
        use.append("loose corners")
    if mud in ("moderate", "high"):
        use.append("mud")
    elif mud in ("none", "low"):
        avoid.append("mud")
    return {"strengths": strengths, "weaknesses": weaknesses,
            "recommended_use": use, "avoid_use": avoid}


def build_tire(entry: dict, existing: dict, rows: dict) -> dict:
    tests = []
    for brr_id in entry["brr"]:
        r = rows[brr_id]
        tests.append({
            "width_mm": r["width_mm"],
            "measured_width_mm": r["measured_width_mm"],
            "year": r["year"],
            "model": r["model"],
            "rr_watts": r["rr_watts"],
            "test_psi": brr_test_psi(r["measured_width_mm"]),
            "puncture_tread": r["puncture_tread"],
            "wet_grip": r["wet_grip"],
            "knob_center_mm": r["knob_center_mm"],
            "knob_edge_mm": r["knob_edge_mm"],
            "weight_g": r["weight_g"],
            "url": r["url"],
        })
    tests.sort(key=lambda t: t["width_mm"])

    tire = {"id": entry["id"]}
    tire["brand"] = entry.get("brand") or existing["brand"]
    tire["name"] = entry.get("name") or existing["name"]
    if entry.get("casing"):
        tire["casing"] = entry["casing"]
    widths = set(entry.get("widths_mm") or existing.get("widths_mm") or [])
    widths |= {t["width_mm"] for t in tests}
    tire["widths_mm"] = sorted(widths)
    tire["widths_source"] = entry.get("widths_source") or (
        "existing" if existing.get("widths_mm") else "brr")
    tire["tread_type"] = entry.get("tread_type") or existing["tread_type"]
    tire["mud_clearance"] = entry.get("mud_clearance") or existing["mud_clearance"]
    tire["tubeless_ready"] = existing.get("tubeless_ready", True)
    tire["msrp_usd"] = entry.get("msrp_usd", existing.get("msrp_usd"))
    if entry.get("msrp_source"):
        tire["msrp_source"] = entry["msrp_source"]

    tire["brr_tests"] = tests
    tire["lab_tested"] = any(t["width_mm"] >= MIN_TESTED_WIDTH_MM for t in tests)
    tire["brr_urls_by_width"] = {str(t["width_mm"]): t["url"] for t in tests}
    tire["crr_watts_at_29kmh"] = {str(t["width_mm"]): t["rr_watts"] for t in tests}
    tire["weight_grams"] = {str(t["width_mm"]): round(t["weight_g"]) for t in tests
                            if t["weight_g"]}
    if tests:
        ref = reference_test(tests)
        tire["puncture_resistance"] = label_puncture(ref["puncture_tread"])
        tire["wet_traction"] = label_wet(ref["wet_grip"])
        tire.update(describe(ref, tire["mud_clearance"]))
    else:
        # Not lab-tested: keep our earlier read, never a number we can't source.
        for key in ("puncture_resistance", "wet_traction", "strengths",
                    "weaknesses", "recommended_use", "avoid_use"):
            tire[key] = existing.get(key, [] if key[-1] == "s" or key.endswith("use") else None)

    for key in KEEP:
        if key in existing:
            tire[key] = existing[key]
    tire.setdefault("status", "active")
    tire.setdefault("race_appearances", [])
    tire.setdefault("community_reviews", [])
    tire.setdefault("comparable_tires", [])
    tire.setdefault("versions", [])
    order = [k for k in KEY_ORDER if k in tire]
    return {k: tire[k] for k in order + sorted(set(tire) - set(order))}


def build_all() -> dict:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    rows = {r["brr_id"]: r for r in snapshot["rows"]}
    out = {}
    for entry in catalog:
        path = TIRE_DIR / f"{entry['id']}.json"
        existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        out[path] = build_tire(entry, existing, rows)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if any tire file is stale")
    ap.add_argument("--listing", type=Path, help="saved BRR CX/Gravel page to refresh the snapshot")
    args = ap.parse_args()

    if args.listing:
        refresh_snapshot(args.listing, json.loads(CATALOG.read_text(encoding="utf-8")))

    stale = []
    for path, tire in build_all().items():
        text = json.dumps(tire, indent=2, ensure_ascii=False) + "\n"
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            stale.append(path.name)
            if not args.check:
                path.write_text(text, encoding="utf-8")
    if args.check:
        if stale:
            print(f"{len(stale)} tire files out of date: {stale[:5]}. "
                  "Run: python3 scripts/import_tire_lab_data.py")
            return 1
        return 0
    print(f"{len(stale)} tire files written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
