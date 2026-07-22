#!/usr/bin/env python3
"""Deploy-parity detector — the anti-drift check (WS3, 2026-07-22).

tar+ssh deploys add-but-never-delete, so the live tree drifts from what the
generators would produce today. That class caused four incidents on
2026-07-22 alone (sitemap tires/VS, /blog/, /tire/, the retired Serbia hub).

Three-way model (converged Claude x GPT-5.6-sol design):
  1. EXPECTED manifest — computed from canonical data + the generators' own
     selection rules (imported, zero-render). Never from the long-lived
     wordpress/output/ tree, which is itself add-only and can carry the same
     staleness being detected.
  2. ACTUAL inventory — SSH `find` of index.html paths under the live webroot.
  3. Findings — ORPHAN (live but no longer generated: the drift class) and
     UNDEPLOYED (expected + advertised but absent live).

Static/WordPress-managed pages live in an explicit registry below; sections
not yet rule-covered are declared in UNCOVERED so the gap is visible instead
of silently passing.

Usage:
    python3 scripts/deploy_parity.py             # human summary (needs SSH)
    python3 scripts/deploy_parity.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
SSH_KEY = Path.home() / ".ssh" / "siteground_key"
REMOTE_ROOT = "~/www/gravelgodcycling.com/public_html"

sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
sys.path.insert(0, str(SCRIPT_DIR))

TOMBSTONES = frozenset(
    t["slug"] for t in json.loads(
        (PROJECT_ROOT / "config" / "tombstones.json").read_text())["tombstones"])

# Pages that exist by hand/WordPress/Elementor, not by generator rule.
STATIC_REGISTRY = {
    "/", "/gravel-races/", "/guide/", "/about/", "/coaching/", "/consulting/",
    "/questionnaire/", "/popular-training-plans/", "/insights/", "/cookies/",
    "/privacy/", "/terms/", "/fueling-methodology/", "/course/", "/courses/",
    "/articles/", "/blog/", "/race/methodology/", "/race/calendar/",
    "/products/training-plans/",
}

# Live sections we deliberately don't inventory (assets, WP internals, money
# path). Anything under these prefixes is ignored, never reported.
EXCLUDE_PREFIXES = (
    "/wp-", "/assets/", "/race/assets/", "/ab/", "/homepage/", "/feed/",
    "/.well-known/", "/img/", "/tp/", "/search/",
)

# Sections whose selection rule is not imported yet — declared, not silent.
UNCOVERED = ("/race/calendar/", "/race/tier-", "/series/", "/course/")


def _race_slugs() -> set[str]:
    return {p.stem for p in RACE_DATA_DIR.glob("*.json")
            if p.stem != "_schema" and p.stem not in TOMBSTONES}


def _tire_rec_slugs() -> set[str]:
    out = set()
    for p in RACE_DATA_DIR.glob("*.json"):
        if p.stem == "_schema" or p.stem in TOMBSTONES:
            continue
        try:
            r = json.loads(p.read_text()).get("race", {})
        except (OSError, json.JSONDecodeError):
            continue
        if (r.get("tire_recommendations") or {}).get("primary"):
            out.add(p.stem)
    return out


def _race_index() -> list[dict]:
    return json.loads((PROJECT_ROOT / "web" / "race-index.json").read_text())


def expected_pages() -> dict[str, set[str]]:
    """Section -> expected live paths (dir URLs, trailing slash), zero-render."""
    races = _race_slugs()
    idx = _race_index()

    exp: dict[str, set[str]] = {}
    exp["race"] = {f"/race/{s}/" for s in races}
    exp["race-tires"] = {f"/race/{s}/tires/" for s in _tire_rec_slugs()}
    exp["prep-kit"] = {f"/race/{s}/prep-kit/" for s in races}

    # Training-plan pages: races whose race-pack has demands.
    from generate_training_plan_pages import load_pack
    exp["training-plan"] = {
        f"/race/{s}/training-plan/" for s in races
        if load_pack(s).get("demands")}

    # State hubs: same grouping + floor the generator uses.
    from generate_state_hubs import MIN_RACES, group_races_by_state, _slugify
    grouped = group_races_by_state(idx)
    exp["state-hubs"] = {
        f"/race/best-gravel-races-{_slugify(state)}/"
        for state, rs in grouped.items() if len(rs) >= MIN_RACES}

    # Race VS pages: the generator's own pair selection.
    from generate_vs_pages import select_pairs
    exp["race-vs"] = {
        f"/race/{a}-vs-{b}/" for a, b in select_pairs(idx)}

    # Per-tire reviews + comparisons.
    tire_ids = sorted(p.stem for p in (PROJECT_ROOT / "data" / "tires").glob("*.json"))
    exp["tire-reviews"] = {f"/tire/{t}/" for t in tire_ids}
    from generate_tire_vs_pages import load_tire_database, select_tire_pairs
    exp["tire-vs"] = {
        f"/tire/{a}-vs-{b}/" for a, b in select_tire_pairs(load_tire_database())}

    # Blog: the generator's own pure enumeration (shared predicate).
    from generate_season_roundup import expected_roundup_slugs
    exp["blog"] = {f"/blog/{s}/" for s in expected_roundup_slugs(idx, 2026)}

    # Articles are hand-authored artifacts; their files are the only source.
    exp["articles"] = {
        f"/articles/{p.stem}/" for p in
        (PROJECT_ROOT / "wordpress" / "output" / "articles").glob("*.html")
        if p.stem != "index"}

    return exp


def parse_inventory(find_output: str) -> set[str]:
    """Normalize `find` output (index.html paths) to live dir URLs."""
    live = set()
    for line in find_output.splitlines():
        line = line.strip()
        if not line.endswith("/index.html"):
            continue
        m = re.search(r"public_html(/.*/)index\.html$", line)
        if not m:
            continue
        path = m.group(1)
        if any(path.startswith(p) for p in EXCLUDE_PREFIXES):
            continue
        live.add(path)
    return live


def ssh_inventory() -> set[str]:
    import os
    host = os.environ.get("SSH_HOST")
    user = os.environ.get("SSH_USER")
    port = os.environ.get("SSH_PORT", "18765")
    if not host or not user:
        raise RuntimeError("SSH_HOST/SSH_USER not set (source .env)")
    r = subprocess.run(
        ["ssh", "-i", str(SSH_KEY), "-p", port, f"{user}@{host}",
         f"find {REMOTE_ROOT} -maxdepth 5 -name index.html"],
        capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f"SSH inventory failed: {r.stderr.strip()[:200]}")
    inv = parse_inventory(r.stdout)
    if len(inv) < 100:
        raise RuntimeError(
            f"SSH inventory suspiciously small ({len(inv)} paths) — refusing "
            "to report mass-orphans from a bad listing")
    return inv


def compare(expected: dict[str, set[str]], live: set[str]) -> dict:
    """Per-section orphans/undeployed. A live path is an orphan only if it
    falls inside a covered section's namespace but isn't expected."""
    all_expected = set().union(*expected.values()) | STATIC_REGISTRY
    result = {"sections": {}, "orphans": [], "undeployed": []}

    def section_of(path: str) -> str | None:
        if any(path.startswith(u) for u in UNCOVERED):
            return None
        if path in STATIC_REGISTRY:
            return None
        if re.fullmatch(r"/race/[^/]+/tires/", path):
            return "race-tires"
        if re.fullmatch(r"/race/[^/]+/prep-kit/", path):
            return "prep-kit"
        if re.fullmatch(r"/race/[^/]+/training-plan/", path):
            return "training-plan"
        if re.fullmatch(r"/race/best-gravel-races-[^/]+/", path):
            return "state-hubs"
        if re.fullmatch(r"/race/[^/]+-vs-[^/]+/", path):
            return "race-vs"
        if re.fullmatch(r"/race/[^/]+/", path):
            return "race"
        if re.fullmatch(r"/tire/[^/]+-vs-[^/]+/", path):
            return "tire-vs"
        if re.fullmatch(r"/tire/[^/]+/", path):
            return "tire-reviews"
        if re.fullmatch(r"/blog/[^/]+/", path):
            return "blog"
        if re.fullmatch(r"/articles/[^/]+/", path):
            return "articles"
        return None

    for path in sorted(live):
        if path in all_expected:
            continue
        sec = section_of(path)
        if sec:
            result["orphans"].append({"section": sec, "path": path})

    for sec, paths in expected.items():
        missing = sorted(paths - live)
        present = len(paths) - len(missing)
        result["sections"][sec] = {"expected": len(paths), "live": present,
                                   "undeployed": len(missing)}
        result["undeployed"].extend({"section": sec, "path": p} for p in missing)

    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write full result JSON here")
    args = ap.parse_args()

    expected = expected_pages()
    live = ssh_inventory()
    result = compare(expected, live)

    print(f"live paths inventoried: {len(live)}")
    for sec, st in sorted(result["sections"].items()):
        print(f"  {sec:15s} expected {st['expected']:4d}  live {st['live']:4d}"
              f"  undeployed {st['undeployed']}")
    print(f"ORPHANS (live but not generated): {len(result['orphans'])}")
    for o in result["orphans"][:20]:
        print(f"   {o['section']:12s} {o['path']}")
    print(f"UNDEPLOYED (expected but absent): {len(result['undeployed'])}")
    for u in result["undeployed"][:20]:
        print(f"   {u['section']:12s} {u['path']}")

    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1))
    return 1 if (result["orphans"] or result["undeployed"]) else 0


if __name__ == "__main__":
    sys.exit(main())
