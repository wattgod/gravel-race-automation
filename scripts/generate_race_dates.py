#!/usr/bin/env python3
"""Generate web/race-dates.json — {slug: "YYYY-MM-DD"} for the countdown trigger.

Parses race-data/*.json → race.vitals.date_specific. Handled formats
(verified against the full corpus, Jul 2026):

    "2026: May 30"        → 2026-05-30
    "2026: June 16-28"    → 2026-06-16   (multi-day: start line wins)
    "June 7, 2026"        → 2026-06-07
    "2026: October TBD"   → omitted      (never guess)

Mission Control fetches the deployed copy daily — see
docs/specs/race-countdown-trigger.md. Deploy alongside race-index.json.

Usage:
    python3 scripts/generate_race_dates.py [--check]
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "race-data"
OUTPUT = PROJECT_ROOT / "web" / "race-dates.json"

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}
_MONTHS.update({m[:3].lower(): i for m, i in list(_MONTHS.items())})
_MONTHS["sept"] = 9

# "2026: May 30" / "2026: June 16-28" / "2026: Sep 27" / "2026: August 1 (provisional)"
# Anchored at start; trailing text (parentheticals, ranges, notes) is ignored —
# for multi-day events the START day is what the countdown math needs.
_PREFIXED = re.compile(r"^(\d{4}):\s*([A-Za-z]+)\.?\s+(\d{1,2})(?:\s*[-–]\s*\d{1,2})?\b")
# "June 7, 2026" / "September 5, 2026 (main ride)" / "August 22, 2026 at 09:00"
_US_STYLE = re.compile(r"^([A-Za-z]+)\.?\s+(\d{1,2}),\s*(\d{4})\b")


def parse_date_specific(raw: str | None) -> str | None:
    """Parse a date_specific string to ISO YYYY-MM-DD, or None if unparseable."""
    if not raw:
        return None
    raw = raw.strip()
    m = _PREFIXED.match(raw)
    if m:
        year, month_name, day = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    else:
        m = _US_STYLE.match(raw)
        if not m:
            return None
        month_name, day, year = m.group(1).lower(), int(m.group(2)), int(m.group(3))
    month = _MONTHS.get(month_name)
    if not month:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def build() -> dict[str, str]:
    dates: dict[str, str] = {}
    skipped = 0
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            race = json.loads(path.read_text())["race"]
        except (json.JSONDecodeError, KeyError):
            skipped += 1
            continue
        iso = parse_date_specific((race.get("vitals") or {}).get("date_specific"))
        if iso:
            dates[path.stem] = iso
        else:
            skipped += 1
    print(f"Parsed {len(dates)} race dates, omitted {skipped} (TBD/unparseable)")
    return dates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="Exit 1 if the output file would change")
    args = parser.parse_args()

    dates = build()
    payload = json.dumps(dates, indent=0, sort_keys=True)
    if args.check:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        if current != payload:
            print("race-dates.json is stale — rerun scripts/generate_race_dates.py")
            return 1
        return 0
    OUTPUT.write_text(payload)
    print(f"Wrote {OUTPUT} ({len(payload):,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
