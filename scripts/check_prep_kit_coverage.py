#!/usr/bin/env python3
"""Check that every published race profile's prep-kit gate has a live page."""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


USER_AGENT = "GG-MissionControl/1.0"
ROOT = Path(__file__).resolve().parent.parent
LEGACY_GATED_PATHS = (("gravelgod", "https://gravelgodcycling.com", "the-mid-south"),)


def load_indexes(include_road: bool = True) -> list[tuple[str, str, list[dict]]]:
    indexes = [("gravelgod", "https://gravelgodcycling.com", json.loads((ROOT / "web/race-index.json").read_text()))]
    if not include_road:
        return indexes
    road_local = ROOT.parent / "road-race-automation" / "web" / "race-index.json"
    try:
        if road_local.exists():
            data = json.loads(road_local.read_text())
        else:
            req = urllib.request.Request("https://roadielabs.com/race-index.json", headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.load(response)
        indexes.append(("roadielabs", "https://roadielabs.com", data))
    except (OSError, ValueError, urllib.error.URLError):
        # Road coverage is included when its index is reachable; an unavailable
        # sibling/index must not hide Gravel God failures.
        pass
    return indexes


def check_url(url: str) -> tuple[int | None, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return response.status, ""
    except urllib.error.HTTPError as exc:
        return exc.code, str(exc.reason)
    except urllib.error.URLError as exc:
        return None, str(exc.reason)


def check_coverage(indexes: list[tuple[str, str, list[dict]]]) -> tuple[list[dict], bool]:
    targets = []
    for brand, base_url, races in indexes:
        for race in races:
            # Every generated profile carries prep_kit_gate. Entries without a
            # profile have no gate and therefore cannot be a delivery failure.
            if race.get("has_profile"):
                slug = race["slug"]
                targets.append({"brand": brand, "slug": slug, "url": f"{base_url}/race/{slug}/prep-kit/"})
    present = {(row["brand"], row["slug"]) for row in targets}
    for brand, base_url, slug in LEGACY_GATED_PATHS:
        if (brand, slug) not in present:
            targets.append({"brand": brand, "slug": slug, "url": f"{base_url}/race/{slug}/prep-kit/"})
    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda row: check_url(row["url"]), targets))
    for row, (status, error) in zip(targets, results):
        row.update(status=status, error=error)
    failed = any(row["status"] != 200 for row in targets)
    return targets, failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gravel-only", action="store_true", help="skip the Roadie index")
    args = parser.parse_args()
    rows, failed = check_coverage(load_indexes(include_road=not args.gravel_only))
    print(f"{'BRAND':12} {'SLUG':42} {'STATUS':8} URL")
    for row in rows:
        status = row["status"] if row["status"] is not None else "ERROR"
        print(f"{row['brand']:12} {row['slug'][:42]:42} {str(status):8} {row['url']}")
    ok = sum(row["status"] == 200 for row in rows)
    print(f"\n{ok}/{len(rows)} gated race prep kits returned 200")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
