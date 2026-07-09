#!/usr/bin/env python3
"""
Cross-validate race vitals (distance, elevation gain, elevation ASL, date,
surface/terrain) across every source that carries them:

  1. race-data/<slug>.json          -- this repo, the pilot's source of truth
  2. known_races.py KNOWN_RACES      -- hand-curated ~14-race dict in the
                                         athlete-custom-training-plan-pipeline
                                         repo, used for questionnaire matching
  3. athletes/config/races.json      -- the 1,184-race snapshot in the same
                                         repo, BUILT FROM race-data and used
                                         as `known_races.py`'s fallback match

Race distances and courses change year to year (Big Sugar ran 104mi in 2023,
~100mi in 2025/2026). A hand-curated dict frozen at one year's numbers WILL
drift from the race-data files, which are meant to be refreshed. This is why
this is a periodic check, not a one-time script -- re-run it any time
race-data/*.json or known_races.py changes.

Checks:
  (a) CROSS-SOURCE CONFLICTS
      - known_races.py vs race-data: distance / elevation gain / date differ
      - races.json snapshot vs race-data: same fields differ (snapshot is
        stale relative to the file it was built from -- re-run
        build_race_snapshot.py)
  (b) INTERNAL IMPLAUSIBILITIES (within a single race-data file)
      - climbing gain > distance_mi * 300 ft/mi (implausible average grade
        outside dedicated hillclimbs)
      - a race the DB itself flags as mountainous
        (gravel_god_rating.altitude >= 4) but with no *_elevation_asl_ft
        field -- i.e. no real above-sea-level data backing that rating
      - date_specific citing a year in the past (stale, needs a refresh)
  (c) GAIN-VS-ASL CONFUSION (the Big Sugar / Unbound trap, specifically)
      - a *_elevation_asl_ft field that exactly equals the gain field
        (elevation_ft) on a race with meaningful gain -- almost certainly a
        copy-paste of the gain figure into the ASL field, not real ASL data

Severity: CONFLICT issues (a + the gain-vs-ASL confusion in c) cause a
nonzero exit so this is CI-able. WARNING issues (b) are reported but do not
fail the run by default -- pass --strict to fail on those too.

Usage:
    python3 scripts/validate_race_data.py            # full report
    python3 scripts/validate_race_data.py --strict    # warnings also fail
    python3 scripts/validate_race_data.py big-sugar leadville-100   # subset
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

# Sibling repo that owns known_races.py + the races.json snapshot. Mirrors
# the Path.home()/'Documents'/'GravelGod'/... convention already used by
# training_guide_builder.py::_resolve_race_data for cross-repo lookups.
PIPELINE_REPO = Path.home() / "Documents" / "GravelGod" / "athlete-custom-training-plan-pipeline"
KNOWN_RACES_SCRIPTS_DIR = PIPELINE_REPO / "athletes" / "scripts"
SNAPSHOT_PATH = PIPELINE_REPO / "athletes" / "config" / "races.json"

# known_races.py's KNOWN_RACES dict is a hand-curated ~14-entry map keyed by
# an internal race_id (e.g. 'big_sugar'), not by race-data slug. Names don't
# slugify cleanly onto race-data filenames (e.g. "Belgian Waffle Ride" has no
# unqualified race-data file -- only *-kansas and bwr-* variants exist), so
# this mapping is maintained by hand rather than fuzzy-matched. Add an entry
# here whenever a new race_id is added to KNOWN_RACES.
KNOWN_RACE_ID_TO_SLUG = {
    "unbound_gravel_200": "unbound-200",
    "unbound_gravel_100": "unbound-100",
    "unbound_xl": "unbound-xl",
    "sbt_grvl": "steamboat-gravel",
    "leadville_100": "leadville-100",
    "belgian_waffle_ride": None,  # ambiguous: race-data has no unqualified
                                  # "Belgian Waffle Ride" file, only
                                  # bwr-california / bwr-san-diego /
                                  # belgian-waffle-ride-kansas -- see report
    "dirty_kanza_200": "unbound-200",
    "gravel_worlds": "gravel-worlds",
    "mid_south": "mid-south",
    "big_sugar": "big-sugar",
    "boulder_roubaix": "boulder-roubaix",
    # No race-data file exists for these distance variants (short/mid course
    # editions aren't tracked as separate files):
    "unbound_gravel_50": None,
    "sbt_grvl_75": None,
    "sbt_grvl_37": None,
}

GAIN_PER_MILE_LIMIT = 300  # ft/mi -- above this, flag for a human look
ASL_TRIGGER_ALTITUDE_RATING = 4  # gravel_god_rating.altitude >= this = "mountainous"


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def _vitals_of(raw):
    """Return the flat `race.vitals` dict regardless of {"race": {...}} wrap."""
    r = raw.get("race", raw)
    return r, r.get("vitals", {})


def _norm(x):
    """None and 0/'' are the same 'no data' for comparison purposes."""
    return x or 0


def _year_of(date_specific):
    m = re.match(r"^(\d{4}):", date_specific or "")
    return int(m.group(1)) if m else None


_MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july",
                "august", "september", "october", "november", "december"]


def _month_num(word):
    word = word.lower().rstrip(".")
    for i, name in enumerate(_MONTH_NAMES, start=1):
        if len(word) >= 3 and name.startswith(word):
            return i
    return None


def _extract_dates(date_specific):
    """Parse a free-text date_specific ("2026: Aug 19-23 (Race Aug 22-23)")
    into (year, {(month, day), ...}) -- every day mentioned or covered by a
    range, so a specific race-day sub-phrase doesn't have to be the first
    date in the string. Returns (None, set()) if nothing parses (e.g.
    "Mid-October annually", "TBD")."""
    if not date_specific:
        return None, set()
    year_m = re.match(r"^(\d{4}):", date_specific)
    year = int(year_m.group(1)) if year_m else None
    days = set()
    for m in re.finditer(r"([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:-(\d{1,2}))?", date_specific):
        month = _month_num(m.group(1))
        if month is None:
            continue
        start_day = int(m.group(2))
        end_day = int(m.group(3)) if m.group(3) else start_day
        for d in range(start_day, end_day + 1):
            days.add((month, d))
    return year, days


class Report:
    def __init__(self):
        self.conflicts = []  # (race, message)
        self.warnings = []   # (race, message)

    def conflict(self, race, msg):
        self.conflicts.append((race, msg))

    def warning(self, race, msg):
        self.warnings.append((race, msg))


def load_known_races():
    sys.path.insert(0, str(KNOWN_RACES_SCRIPTS_DIR))
    try:
        import known_races  # noqa
        return dict(known_races.KNOWN_RACES)
    except Exception as e:
        print(f"WARNING: could not import known_races.py ({e}); "
              f"skipping known_races cross-checks.\n")
        return None


def load_snapshot():
    if not SNAPSHOT_PATH.exists():
        print(f"WARNING: snapshot not found at {SNAPSHOT_PATH}; "
              f"skipping snapshot cross-checks.\n")
        return None
    try:
        return _load_json(SNAPSHOT_PATH).get("races", {})
    except Exception as e:
        print(f"WARNING: could not load snapshot ({e}); skipping.\n")
        return None


def check_known_races(report, known_races, slugs=None, race_data_dir=None):
    """(a) known_races.py vs race-data/<slug>.json."""
    if known_races is None:
        return
    race_data_dir = race_data_dir or RACE_DATA_DIR
    for race_id, info in sorted(known_races.items()):
        slug = KNOWN_RACE_ID_TO_SLUG.get(race_id, "__unmapped__")
        if slugs and slug not in slugs and race_id not in slugs:
            continue
        if slug is None:
            report.warning(
                race_id,
                f"AMBIGUOUS_OR_UNTRACKED: known_races.py entry '{race_id}' "
                f"({info.get('name')}) has no unambiguous race-data file "
                f"mapping -- cannot cross-check (see KNOWN_RACE_ID_TO_SLUG "
                f"comment).",
            )
            continue
        if slug == "__unmapped__":
            report.warning(
                race_id,
                f"UNMAPPED: known_races.py entry '{race_id}' is not in "
                f"KNOWN_RACE_ID_TO_SLUG -- add a mapping (or None if "
                f"genuinely untrackable) so it gets cross-checked.",
            )
            continue

        path = race_data_dir / f"{slug}.json"
        if not path.exists():
            report.conflict(race_id, f"MISSING_RACE_DATA_FILE: mapped to "
                             f"{slug}.json which does not exist.")
            continue

        r, v = _vitals_of(_load_json(path))

        kr_dist = info.get("distance_miles")
        rd_dist = v.get("distance_mi")
        if _norm(kr_dist) != _norm(rd_dist):
            report.conflict(
                race_id,
                f"DISTANCE_MISMATCH: known_races.py={kr_dist}mi vs "
                f"race-data/{slug}.json={rd_dist}mi",
            )

        kr_elev = info.get("elevation_ft")
        rd_elev = v.get("elevation_ft")
        if _norm(kr_elev) != _norm(rd_elev):
            report.conflict(
                race_id,
                f"ELEVATION_GAIN_MISMATCH: known_races.py={kr_elev}ft vs "
                f"race-data/{slug}.json={rd_elev}ft",
            )

        kr_date = info.get("date")  # 'YYYY-MM-DD'
        rd_date = v.get("date_specific") or ""
        if kr_date:
            try:
                ky, km, kd = (int(x) for x in kr_date.split("-"))
            except (ValueError, AttributeError):
                ky = km = kd = None
            if ky is not None:
                rd_year, rd_days = _extract_dates(rd_date)
                year_conflicts = rd_year is not None and rd_year != ky
                # Only flag a day mismatch when date_specific actually parsed
                # to at least one concrete day -- "Mid-October annually" etc.
                # can't be cross-checked and isn't a conflict by default.
                day_conflicts = bool(rd_days) and (km, kd) not in rd_days
                if year_conflicts or day_conflicts:
                    report.conflict(
                        race_id,
                        f"DATE_MISMATCH: known_races.py={kr_date} vs "
                        f"race-data/{slug}.json date_specific='{rd_date}'",
                    )


def check_snapshot(report, snapshot, slugs=None, race_data_dir=None):
    """(a) races.json snapshot vs race-data/<slug>.json (build staleness)."""
    if snapshot is None:
        return
    race_data_dir = race_data_dir or RACE_DATA_DIR
    for key, entry in sorted(snapshot.items()):
        if not key.startswith("gravel:"):
            continue  # this repo only owns the gravel race-data
        slug = entry.get("slug")
        if slugs and slug not in slugs:
            continue
        path = race_data_dir / f"{slug}.json"
        if not path.exists():
            report.conflict(slug or key,
                             f"SNAPSHOT_ORPHAN: races.json references slug "
                             f"'{slug}' with no matching race-data file.")
            continue
        r, v = _vitals_of(_load_json(path))
        if _norm(entry.get("distance_mi")) != _norm(v.get("distance_mi")):
            report.conflict(
                slug,
                f"SNAPSHOT_STALE_DISTANCE: races.json={entry.get('distance_mi')}mi "
                f"vs race-data={v.get('distance_mi')}mi -- rebuild the snapshot",
            )
        if _norm(entry.get("elevation_ft")) != _norm(v.get("elevation_ft")):
            report.conflict(
                slug,
                f"SNAPSHOT_STALE_ELEVATION: races.json={entry.get('elevation_ft')}ft "
                f"vs race-data={v.get('elevation_ft')}ft -- rebuild the snapshot",
            )


def check_internal(report, slugs=None, race_data_dir=None):
    """(b) implausibilities + (c) gain-vs-ASL confusion, per race-data file."""
    race_data_dir = race_data_dir or RACE_DATA_DIR
    today_year = date.today().year
    files = sorted(race_data_dir.glob("*.json"))
    if slugs:
        files = [f for f in files if f.stem in slugs]

    missing_asl_mountain = []

    for path in files:
        slug = path.stem
        try:
            raw = _load_json(path)
        except Exception as e:
            report.conflict(slug, f"INVALID_JSON: {e}")
            continue
        r, v = _vitals_of(raw)
        dist = v.get("distance_mi")
        gain = v.get("elevation_ft")
        altitude_rating = r.get("gravel_god_rating", {}).get("altitude")

        # (b) gain implausible relative to distance
        if isinstance(dist, (int, float)) and dist > 0 and isinstance(gain, (int, float)):
            ratio = gain / dist
            if ratio > GAIN_PER_MILE_LIMIT:
                report.warning(
                    slug,
                    f"IMPLAUSIBLE_GAIN_RATIO: {gain}ft gain over {dist}mi "
                    f"= {ratio:.0f}ft/mi (limit {GAIN_PER_MILE_LIMIT}ft/mi) "
                    f"-- verify, or it's a legit hillclimb",
                )

        # (b) mountainous rating with no real ASL backing
        start_asl = v.get("start_elevation_asl_ft")
        avg_asl = v.get("avg_elevation_asl_ft")
        has_asl = bool(start_asl or avg_asl)
        if isinstance(altitude_rating, (int, float)) and altitude_rating >= ASL_TRIGGER_ALTITUDE_RATING and not has_asl:
            missing_asl_mountain.append(slug)

        # (c) gain-vs-ASL confusion: an ASL field that's suspiciously just a
        # copy of the gain figure
        if isinstance(gain, (int, float)) and gain > 3000:
            for field, val in (("start_elevation_asl_ft", start_asl), ("avg_elevation_asl_ft", avg_asl)):
                if val and val == gain:
                    report.conflict(
                        slug,
                        f"GAIN_AS_ASL_SUSPECTED: {field}={val} is IDENTICAL "
                        f"to elevation_ft (gain)={gain} -- almost certainly "
                        f"the climbing-gain figure copy-pasted into the ASL "
                        f"field instead of a real above-sea-level value.",
                    )

        # (b) stale date_specific year
        year = _year_of(v.get("date_specific"))
        if year is not None and year < today_year:
            report.warning(
                slug,
                f"STALE_DATE: date_specific year {year} is in the past "
                f"(current year {today_year}) -- needs a refresh for the "
                f"next running of the race",
            )

    if missing_asl_mountain:
        sample = ", ".join(missing_asl_mountain[:10])
        more = f" (+{len(missing_asl_mountain) - 10} more)" if len(missing_asl_mountain) > 10 else ""
        report.warning(
            "(aggregate)",
            f"MISSING_ASL_FOR_MOUNTAIN_RACE: {len(missing_asl_mountain)} races "
            f"rated altitude>={ASL_TRIGGER_ALTITUDE_RATING} have no "
            f"*_elevation_asl_ft data -- altitude guide section can't fire "
            f"for them yet. Examples: {sample}{more}",
        )


def print_section(title, items):
    print(f"--- {title} ({len(items)}) ---")
    for race, msg in items:
        print(f"  [{race}] {msg}")
    print()


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv[1:]
    slugs = set(argv) or None

    if not RACE_DATA_DIR.exists():
        print(f"ERROR: race-data directory not found: {RACE_DATA_DIR}")
        sys.exit(1)

    report = Report()
    known_races = load_known_races()
    snapshot = load_snapshot()

    check_known_races(report, known_races, slugs)
    check_snapshot(report, snapshot, slugs)
    check_internal(report, slugs)

    print("=" * 70)
    print("RACE DATA VALIDATION REPORT")
    print("=" * 70)
    print()
    print_section("CONFLICTS (cross-source mismatches, gain-vs-ASL confusion)",
                   report.conflicts)
    print_section("WARNINGS (implausibilities, staleness, missing ASL backlog)",
                   report.warnings)

    print("=" * 70)
    print(f"SUMMARY: {len(report.conflicts)} conflicts, "
          f"{len(report.warnings)} warnings")
    print("=" * 70)

    if report.conflicts or (strict and report.warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
