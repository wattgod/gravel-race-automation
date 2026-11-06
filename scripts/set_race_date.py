#!/usr/bin/env python3
"""Set a race's next-edition date without losing the edition it replaces.

    python3 scripts/set_race_date.py graean-cymru "2027: June 5-6 (Saturday-Sunday, CONFIRMED — graeancymru.com)"

What the old ``date_specific`` recorded (a past confirmed date, "CANCELLED for
2026", "last held July 28, 2024") moves into ``race.editions`` first; the page's
Editions table shows it. Pass --correction when the old value was simply
wrong. Add the source citation separately, as usual.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "wordpress"))
from race_editions import problems, set_date_specific  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slug")
    parser.add_argument("date_specific")
    parser.add_argument("--correction", action="store_true",
                        help="the old value was wrong: don't keep it as a past edition")
    args = parser.parse_args(argv)

    path = ROOT / "race-data" / f"{args.slug}.json"
    if not path.exists():
        print(f"No profile at {path}", file=sys.stderr)
        return 1
    data = json.loads(path.read_text())
    race = data["race"]
    old = race.get("vitals", {}).get("date_specific")
    added = set_date_specific(race, args.date_specific, correction=args.correction)
    bad = problems(race)
    if bad:
        print("\n".join(bad), file=sys.stderr)
        return 1
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    print(f"{args.slug}: {old!r} -> {args.date_specific!r}")
    for entry in added:
        print(f"  kept in editions: {entry}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
