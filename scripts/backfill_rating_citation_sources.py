#!/usr/bin/env python3
"""Ensure every scored Gravel God profile has a numbered source bibliography.

Existing citation arrays are never reordered because their positions are public
inline-reference IDs. Profiles with no citations are populated from the normal
extractor, with a small set of source-less legacy profiles pinned to verified
official URLs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from extract_citations import build_citations


ROOT = Path(__file__).resolve().parents[1]
RACE_DATA = ROOT / "race-data"

OFFICIAL_SOURCE_OVERRIDES = {
    "gran-fondo-argentina": [
        ("https://granfondoargentina.com/", "Gran Fondo Argentina — official event site"),
    ],
    "pan-celtic-ultra": [
        ("https://pancelticrace.com/", "Pan Celtic Race — official event site"),
        ("https://pancelticrace.com/the-ultra/faqs/", "Pan Celtic Race — official FAQ"),
        ("https://pancelticrace.com/the-ultra/rules/", "Pan Celtic Race — official rules"),
    ],
    "yangyang-gran-fondo": [
        ("https://ygranfondo.raceplan.co.kr/", "Yangyang Gran Fondo — official event site"),
        ("https://file.raceplan.co.kr/files/ygranfondo/images/ebook.pdf", "Yangyang Gran Fondo — official rider guide"),
    ],
    "tour-aotearoa": [
        ("https://www.touraotearoa.nz/p/home.html", "Tour Aotearoa — official route site"),
        ("https://www.touraotearoa.nz/p/map_22.html", "Tour Aotearoa — official route and GPS guidance"),
    ],
    "transiberica": [
        ("https://www.transiberica.club/", "Transibérica Ultracycling — official event site"),
        ("https://www.transiberica.club/24h/", "Transibérica Ultracycling — official event information"),
    ],
    "the-accursed-race": [
        ("https://www.lostdot.cc/race-brand/the-accursed-race", "Lost Dot — The Accursed Race official overview"),
        ("https://www.lostdot.cc/race/tarno1", "Lost Dot — inaugural Accursed Race edition"),
    ],
    "final-frontier-patagonia": [
        ("https://www.finalfrontierpatagonia.com/en/", "Final Frontier Patagonia — official event site"),
        ("https://finalfrontierpatagonia.com/en/route", "Final Frontier Patagonia — official route"),
        ("https://finalfrontierpatagonia.com/en/terms", "Final Frontier Patagonia — official terms and regulations"),
    ],
}


def override_citations(slug: str) -> list[dict]:
    return [
        {"url": url, "category": "official", "label": label}
        for url, label in OFFICIAL_SOURCE_OVERRIDES.get(slug, [])
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Report gaps without writing")
    args = parser.parse_args()

    changed = []
    missing = []
    for path in sorted(RACE_DATA.glob("*.json")):
        if path.name == "_schema.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        race = data.get("race", data)
        if not race.get("gravel_god_rating") or race.get("citations"):
            continue

        citations = build_citations(path.stem, race) or override_citations(path.stem)
        if not citations:
            missing.append(path.stem)
            continue
        changed.append((path.stem, len(citations)))
        if not args.check:
            race["citations"] = citations
            if "race" in data:
                data["race"] = race
            else:
                data = race
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for slug, count in changed:
        print(f"{'WOULD ADD' if args.check else 'ADDED'} {slug}: {count} source(s)")
    if missing:
        print("MISSING " + ", ".join(missing))
        return 1
    print(f"{'Would update' if args.check else 'Updated'} {len(changed)} profile(s); no source-less scored profiles remain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
