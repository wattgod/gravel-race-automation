#!/usr/bin/env python3
"""Backfill missing category/label on race citations.

Newer scrape batches imported citations as {url, title, accessed} without
the category/label fields validate_citations.py requires. Both are
deterministically derivable, so this needs no API calls:

  - category/label from categorize_url() (extract_citations.py SOURCE_RULES)
  - official-site URLs get ('official', 'Official Website')
  - races over MAX_CITATIONS are trimmed with the same priority sort
    extract_citations.py uses

Usage:
  python scripts/backfill_citation_fields.py            # apply
  python scripts/backfill_citation_fields.py --dry-run  # preview counts
"""

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_citations import (
    MAX_CITATIONS,
    categorize_url,
    find_official_website,
)

RACE_DATA = Path(__file__).resolve().parent.parent / "race-data"

CATEGORY_PRIORITY = {'official': 0, 'route': 1, 'media': 2, 'community': 3,
                     'video': 4, 'registration': 5}


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def backfill_race(path: Path, dry_run: bool) -> dict | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    race = data.get("race", {})
    citations = race.get("citations")
    if not citations:
        return None

    official_domain = _domain(find_official_website(race) or "")
    filled = trimmed = 0

    for c in citations:
        needs_cat = not c.get("category")
        needs_label = not c.get("label")
        if not (needs_cat or needs_label):
            continue
        url = c.get("url", "")
        if official_domain and _domain(url) == official_domain:
            category, label = "official", "Official Website"
        else:
            category, label = categorize_url(url)
        if needs_cat:
            c["category"] = category
        if needs_label:
            c["label"] = "Official Website" if c["category"] == "official" else label
        filled += 1

    if len(citations) > MAX_CITATIONS:
        citations.sort(key=lambda c: CATEGORY_PRIORITY.get(c.get("category"), 99))
        trimmed = len(citations) - MAX_CITATIONS
        race["citations"] = citations[:MAX_CITATIONS]

    if not (filled or trimmed):
        return None
    if not dry_run:
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    return {"slug": path.stem, "filled": filled, "trimmed": trimmed}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = []
    for path in sorted(RACE_DATA.glob("*.json")):
        result = backfill_race(path, args.dry_run)
        if result:
            changed.append(result)

    total_filled = sum(r["filled"] for r in changed)
    total_trimmed = sum(r["trimmed"] for r in changed)
    mode = "DRY RUN — " if args.dry_run else ""
    print(f"{mode}{len(changed)} profiles: {total_filled} citations backfilled, "
          f"{total_trimmed} trimmed over cap")


if __name__ == "__main__":
    main()
