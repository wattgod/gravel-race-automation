#!/usr/bin/env python3
"""Record which race-plan TrainingPeaks listings TP no longer serves.

data/tp-race-plan-links.json mirrors the canonical plan database, which can
say "published" for a plan TrainingPeaks answers with "Training Plan Not
Found". This probes every listing and writes data/tp-unavailable-listings.json;
generate_training_plan_pages.py leaves those buy buttons off the page.

A listing is marked unavailable only on TP's own "Training Plan Not Found"
page, and marked available again only on a real plan page. Anything else
(timeouts, WAF challenges, other errors) leaves that plan's recorded state
unchanged, so a bad network run never adds or removes buttons.

Usage:
    python3 scripts/check_tp_listings.py            # probe and write
    python3 scripts/check_tp_listings.py --dry-run  # probe and report only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINKS = PROJECT_ROOT / "data" / "tp-race-plan-links.json"
OUTPUT = PROJECT_ROOT / "data" / "tp-unavailable-listings.json"

NOT_FOUND = "Training Plan Not Found"
TITLE_RE = re.compile(r"<title>([^<]*)</title>", re.I)


def classify(title: str | None) -> str:
    """'gone', 'live' or 'unknown' from a TP page title."""
    if not title:
        return "unknown"
    if NOT_FOUND in title:
        return "gone"
    if "Training Plan | TrainingPeaks" in title:
        return "live"
    return "unknown"


def fetch_title(url: str) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (listing check)"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read(200_000).decode("utf-8", "replace")
    except Exception:
        return None
    m = TITLE_RE.search(body)
    return m.group(1).strip() if m else None


def merge(previous: dict, results: dict[int, tuple[str, str]], today: str) -> dict:
    """New unavailable map from the old one and this run's results.

    results: planId -> (state, race_slug).
    """
    plans = dict(previous.get("plans", {}))
    for plan_id, (state, slug) in results.items():
        key = str(plan_id)
        if state == "gone":
            entry = plans.get(key, {"race_slug": slug, "first_seen": today})
            entry["last_checked"] = today
            plans[key] = entry
        elif state == "live":
            plans.pop(key, None)
    return {
        "_note": ("Race-plan TrainingPeaks listings that answer 'Training Plan "
                  "Not Found'. Written by scripts/check_tp_listings.py; the "
                  "plan pages leave these buy buttons off."),
        "checked_at": today,
        "plans": dict(sorted(plans.items(), key=lambda kv: int(kv[0]))),
    }


def load_unavailable(path: Path = OUTPUT) -> set[int]:
    """Plan IDs to hide. Missing file means none; a malformed one raises."""
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(k) for k in data["plans"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    links = json.loads(LINKS.read_text(encoding="utf-8"))
    jobs = [(p["planId"], slug, p["url"]) for slug, plans in links.items() for p in plans]

    def probe(job):
        plan_id, slug, url = job
        return plan_id, slug, classify(fetch_title(url))

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        probed = list(pool.map(probe, jobs))

    results = {pid: (state, slug) for pid, slug, state in probed}
    counts = {s: sum(1 for _, _, st in probed if st == s) for s in ("live", "gone", "unknown")}
    print(f"probed {len(jobs)} listings: {counts['live']} live, "
          f"{counts['gone']} not found, {counts['unknown']} unknown (state kept)")

    previous = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    merged = merge(previous, results, date.today().isoformat())
    gone_by_race: dict[str, int] = {}
    for entry in merged["plans"].values():
        gone_by_race[entry["race_slug"]] = gone_by_race.get(entry["race_slug"], 0) + 1
    print(f"unavailable: {len(merged['plans'])} plans across {len(gone_by_race)} races")
    if not args.dry_run:
        OUTPUT.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUTPUT.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
