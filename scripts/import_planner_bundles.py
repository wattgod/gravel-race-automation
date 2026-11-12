#!/usr/bin/env python3
"""Import public finish-time planner data from the planner research workspace.

Reads (never writes) the research workspace's ``races_pub/`` folder:
  - ``eligibility.json``: per-race status from its eligibility check;
  - ``<slug>/bundle.json``: the course bundle (route bins, past race-day weather,
    frozen engine constants);
  - ``engine/engine7.js``: the planner engine.

Writes, in this repo:
  - ``data/planner/status.json``: for each race in ``data/planner/rollout.json``,
    its status (eligible / flagged / held / no bundle) and only the public flag
    text a page shows. Held races carry no reasons: the page is unchanged.
  - ``data/planner/courses/<slug>.json``: a trimmed public course for each
    eligible or flagged race (no profile notes, no build paths, no private
    checks).
  - ``wordpress/planner/engine7.js``: byte-identical copy of the engine; its
    sha256 is recorded in status.json and pinned by tests.

Re-run after the research side changes a race's status. A race that becomes
eligible upstream appears on its page after this import and a regenerate,
with no code change.

Usage:
    python3 scripts/import_planner_bundles.py --source <research workspace>/races_pub
    python3 scripts/import_planner_bundles.py --source <path> --check   # report only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLANNER_DATA = REPO / "data" / "planner"
ROLLOUT = PLANNER_DATA / "rollout.json"
STATUS = PLANNER_DATA / "status.json"
COURSES = PLANNER_DATA / "courses"
ENGINE_DST = REPO / "wordpress" / "planner" / "engine7.js"
GEAR = PLANNER_DATA / "gear.json"
BIKE_CLASSES = (("race_carbon", "Race carbon"), ("all_round_carbon", "All-round carbon"), ("alloy", "Alloy"))

SHOWN = ("eligible", "flagged")

# Flags the page knows how to show. Any other flag stops the import: a new
# kind of flag needs a reviewed page behaviour first.
FLAG_KINDS = {
    "edition not confirmed": "edition",
    "climbing-heavy": "climbing",
    "time outside 3-9 h": "visitor_sets_effort",
}
# Page text the launch decisions have since withdrawn (Amendment 2: a
# climbing-heavy course gets the same range, not a wider one). Dropped from
# the imported text; any other wording passes through unchanged.
WITHDRAWN_CLAUSES = (" (shown with a wider range)",)
# Flags that are for the route check only and never reach a visitor.
PRIVATE_FLAG_PAGE = "route check needed (not shown to visitors)"

COL_KEYS = ("g", "kap", "alt", "la", "lo", "h", "ok")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def public_flags(race: dict) -> list[dict]:
    out = []
    for flag in race.get("flags", []):
        if flag.get("page") == PRIVATE_FLAG_PAGE:
            continue
        kind = FLAG_KINDS.get(flag.get("flag"))
        if kind is None:
            raise SystemExit(f"unknown planner flag {flag.get('flag')!r}: add page behaviour before importing")
        text = flag["page"]
        for clause in WITHDRAWN_CLAUSES:
            text = text.replace(clause, "")
        out.append({"kind": kind, "text": text})
    return out


def trim_course(bundle: dict) -> dict:
    """Keep only what the page runs and shows."""
    route = bundle["route"]
    cols = bundle["bins"]["cols"]
    editions = []
    for ed in bundle["weather"]["editions"]:
        if not ed.get("start_iso"):
            continue  # no sourced start time: weather cannot be placed
        editions.append({
            "date": ed["date"],
            "start_iso": ed["start_iso"],
            "start_local": ed["start_local"],
            "timezone": ed["timezone"],
            "openmeteo": [{
                "latitude": w["latitude"],
                "longitude": w["longitude"],
                "utc_offset_seconds": w["utc_offset_seconds"],
                "hourly": {k: w["hourly"][k] for k in
                           ("time", "temperature_2m", "wind_speed_10m", "wind_direction_10m")},
            } for w in ed["openmeteo"]],
        })
    if not editions:
        raise SystemExit(f"{bundle['slug']}: no weather edition with a sourced start time")
    # Most recent past race day first: it is the one the page uses.
    editions.sort(key=lambda e: e["date"], reverse=True)
    engine = bundle["engine"]
    return {
        "schema": "ggc-planner-course/1",
        "slug": bundle["slug"],
        "built": bundle["built"][:10],
        "route": {
            "source": route["source"],
            "name": route["name"].strip(),
            "edition_year": route.get("edition_year_used"),
            "updated_year": route.get("updated_year"),
            "distance_m": route["distance_m"],
        },
        "target_edition": {"year": bundle["target_edition"].get("year"),
                           "date": bundle["target_edition"].get("date")},
        "bins": {"step_m": bundle["bins"]["step_m"], "n": bundle["bins"]["n"],
                 "cols": {k: cols[k] for k in COL_KEYS}},
        "weather": {"source": "Open-Meteo historical weather archive", "editions": editions},
        "engine": {k: engine[k] for k in ("crr", "wf", "cap", "phi", "solo_cda_default")},
    }


def public_gear(src: dict) -> dict:
    """Maker-listed bike and bottle weights only, each with its maker page."""
    bikes = []
    for key, label in BIKE_CLASSES:
        models = [{"model": b["model"], "kg": b["kg"], "url": b["url"]} for b in src["bikes"].get(key, [])]
        if len(models) < 3:
            continue  # a class mean needs at least three makers' figures
        bikes.append({"id": key, "label": label, "kg": round(sum(m["kg"] for m in models) / len(models), 3),
                      "models": models})
    bottles = [{"model": b["model"], "ml": b["ml"], "g": b["g"], "url": b["url"]}
               for b in src["bottles"] if b.get("ml") == 750]
    if not bikes or not bottles:
        raise SystemExit("gear sources are missing bike classes or a 750 ml bottle")
    return {"checked": src["checked"], "bikes": bikes, "bottle": bottles[0]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--source", required=True, help="path to the research workspace's races_pub/")
    ap.add_argument("--gear", default=None,
                    help="gear sources JSON (default: <source>/../research/gear_sources_v7.json)")
    ap.add_argument("--check", action="store_true", help="report what would change; write nothing")
    args = ap.parse_args(argv)
    src = Path(args.source).expanduser()
    elig = json.loads((src / "eligibility.json").read_text())
    rollout = json.loads(ROLLOUT.read_text())["races"]
    engine_src = src / "engine" / "engine7.js"
    gear_src = Path(args.gear).expanduser() if args.gear else src.parent / "research" / "gear_sources_v7.json"
    gear = public_gear(json.loads(gear_src.read_text()))

    status = {
        "generated_from_eligibility": elig["generated"],
        "engine_sha256": _sha256(engine_src),
        "races": {},
    }
    courses = {}
    for slug in rollout:
        race = elig["races"].get(slug)
        bundle_path = src / slug / "bundle.json"
        if race is None or not bundle_path.exists():
            status["races"][slug] = {"status": "no bundle"}
            continue
        if race["status"] not in SHOWN:
            status["races"][slug] = {"status": race["status"]}
            continue
        status["races"][slug] = {"status": race["status"], "flags": public_flags(race)}
        courses[slug] = trim_course(json.loads(bundle_path.read_text()))

    for slug, entry in status["races"].items():
        print(f"{slug:28s} {entry['status']:10s} " + "; ".join(f["text"] for f in entry.get("flags", [])))
    if args.check:
        return 0

    COURSES.mkdir(parents=True, exist_ok=True)
    for old in COURSES.glob("*.json"):
        if old.stem not in courses:
            old.unlink()
    for slug, course in courses.items():
        (COURSES / f"{slug}.json").write_text(json.dumps(course, separators=(",", ":")) + "\n")
    STATUS.write_text(json.dumps(status, indent=1) + "\n")
    GEAR.write_text(json.dumps(gear, indent=1, ensure_ascii=False) + "\n")
    ENGINE_DST.parent.mkdir(parents=True, exist_ok=True)
    ENGINE_DST.write_bytes(engine_src.read_bytes())
    if _sha256(ENGINE_DST) != status["engine_sha256"]:
        raise SystemExit("engine copy is not byte-identical")
    return 0


if __name__ == "__main__":
    sys.exit(main())
