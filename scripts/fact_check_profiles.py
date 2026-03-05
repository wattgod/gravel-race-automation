#!/usr/bin/env python3
"""
fact_check_profiles.py — Compare scraped extracts against race profile data.

Reads data/scrape-extracts/{slug}.json and compares against race-data/{slug}.json.
Reports mismatches, confirmations, enrichable fields, and stale dates.

Usage:
  python scripts/fact_check_profiles.py --dry-run                # Preview
  python scripts/fact_check_profiles.py --tier 1                  # By tier
  python scripts/fact_check_profiles.py --slug unbound-200        # Single race
  python scripts/fact_check_profiles.py --auto-fix                # Apply safe fixes only
  python scripts/fact_check_profiles.py --report                  # HTML report

Classifications:
  CONFIRM    — scraped value matches profile within tolerance
  MISMATCH   — scraped value differs beyond tolerance (manual review)
  ENRICHABLE — profile field is empty, scraped value available
  STALE_DATE — profile date is pre-2026, scraped date is 2026

Output: data/fact-check-report.json (and .html with --report)
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scrape_utils import (
    load_extract,
    load_official_sites,
    RACE_DATA_DIR,
    SCRAPE_EXTRACTS_DIR,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Months for parsing
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


# ---------------------------------------------------------------------------
# Comparison logic
# ---------------------------------------------------------------------------

def _safe_numeric(val) -> float | None:
    """Coerce a value to float, handling strings, commas, ranges."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    try:
        s = str(val).replace(",", "").strip()
        # Handle ranges like "4,500-9,116" — take first value
        parts = s.split("-")
        return float(parts[0].strip())
    except (ValueError, IndexError):
        return None


def compare_distance(profile_val, scraped_val) -> tuple:
    """Compare distance_mi values. Returns (classification, detail)."""
    p = _safe_numeric(profile_val)
    s = _safe_numeric(scraped_val)

    if s is None:
        return None, None  # No scraped data
    if p is None or p == 0:
        return "ENRICHABLE", f"scraped={s}"

    tolerance = max(p * 0.05, 2.0)  # 5% or 2mi, whichever is larger
    diff = abs(p - s)

    if diff <= tolerance:
        return "CONFIRM", f"profile={p}, scraped={s}, diff={diff:.1f}mi"
    return "MISMATCH", f"profile={p}, scraped={s}, diff={diff:.1f}mi (tolerance={tolerance:.1f})"


def compare_elevation(profile_val, scraped_val) -> tuple:
    """Compare elevation_ft values. Returns (classification, detail)."""
    p = _safe_numeric(profile_val)
    s = _safe_numeric(scraped_val)

    if s is None:
        return None, None
    if p is None or p == 0:
        return "ENRICHABLE", f"scraped={s}"

    tolerance = max(p * 0.15, 500.0)  # 15% or 500ft, whichever is larger
    diff = abs(p - s)

    if diff <= tolerance:
        return "CONFIRM", f"profile={p}, scraped={s}, diff={diff:.0f}ft"
    return "MISMATCH", f"profile={p}, scraped={s}, diff={diff:.0f}ft (tolerance={tolerance:.0f})"


def _extract_month_num(date_str: str) -> int | None:
    """Extract month number from a date string."""
    if not date_str:
        return None
    for i, m in enumerate(MONTHS):
        if m.lower() in str(date_str).lower():
            return i + 1
    # Try ISO format
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(date_str))
    if iso:
        return int(iso.group(2))
    return None


def _month_distance(m1: int | None, m2: int | None) -> int:
    """Minimum circular distance between two months (0-6)."""
    if m1 is None or m2 is None:
        return 0
    diff = abs(m1 - m2)
    return min(diff, 12 - diff)


def compare_date(profile_date_specific: str, scraped_date: str) -> tuple:
    """Compare date values. Returns (classification, detail)."""
    if not scraped_date:
        return None, None

    profile_ds = str(profile_date_specific) if profile_date_specific else ""

    # Check if profile date is stale (pre-2026)
    profile_year_match = re.match(r"(\d{4})", profile_ds)
    profile_year = int(profile_year_match.group(1)) if profile_year_match else None

    # Check if scraped date mentions 2026
    has_2026 = "2026" in str(scraped_date)

    if not profile_ds:
        if has_2026:
            return "ENRICHABLE", f"scraped={scraped_date}"
        return None, None

    if profile_year and profile_year < 2026 and has_2026:
        return "STALE_DATE", f"profile={profile_ds}, scraped={scraped_date}"

    if profile_year and profile_year >= 2026 and has_2026:
        # Both have 2026 dates — check if they match
        p_month = _extract_month_num(profile_ds)
        s_month = _extract_month_num(scraped_date)
        shift = _month_distance(p_month, s_month)
        if shift <= 1:
            return "CONFIRM", f"profile={profile_ds}, scraped={scraped_date}"
        return "MISMATCH", f"profile={profile_ds}, scraped={scraped_date}, month_shift={shift}"

    return None, None


def compare_race(slug: str) -> dict | None:
    """Compare a race's profile data against its scrape extract.

    Returns dict with field-level classifications, or None if no extract.
    """
    extract = load_extract(slug)
    if not extract or "error" in extract:
        return None

    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return None

    data = json.loads(path.read_text())
    race = data.get("race", data)
    vitals = race.get("vitals", {})

    result = {"slug": slug, "fields": {}, "summary": None}

    # Distance
    cls, detail = compare_distance(vitals.get("distance_mi"), extract.get("distance_mi"))
    if cls:
        result["fields"]["distance_mi"] = {"classification": cls, "detail": detail,
                                            "profile": vitals.get("distance_mi"),
                                            "scraped": extract.get("distance_mi")}

    # Elevation
    cls, detail = compare_elevation(vitals.get("elevation_ft"), extract.get("elevation_ft"))
    if cls:
        result["fields"]["elevation_ft"] = {"classification": cls, "detail": detail,
                                             "profile": vitals.get("elevation_ft"),
                                             "scraped": extract.get("elevation_ft")}

    # Date
    cls, detail = compare_date(vitals.get("date_specific"), extract.get("date_2026"))
    if cls:
        result["fields"]["date_specific"] = {"classification": cls, "detail": detail,
                                              "profile": vitals.get("date_specific"),
                                              "scraped": extract.get("date_2026")}

    # Enrichable fields (only if profile is empty and scraped has data)
    for field, extract_key in [
        ("registration", "registration_status"),
        ("field_size", "field_size"),
        ("start_time", "start_time"),
    ]:
        scraped_val = extract.get(extract_key)
        if scraped_val:
            profile_val = vitals.get(field, "") or vitals.get(extract_key, "")
            if not profile_val:
                result["fields"][field] = {
                    "classification": "ENRICHABLE",
                    "detail": f"scraped={scraped_val}",
                    "profile": None,
                    "scraped": scraped_val,
                }

    # Summary classification
    classifications = [f["classification"] for f in result["fields"].values()]
    if "MISMATCH" in classifications:
        result["summary"] = "MISMATCH"
    elif "STALE_DATE" in classifications:
        result["summary"] = "STALE_DATE"
    elif "ENRICHABLE" in classifications:
        result["summary"] = "ENRICHABLE"
    elif "CONFIRM" in classifications:
        result["summary"] = "CONFIRM"
    else:
        result["summary"] = "NO_DATA"

    return result


# ---------------------------------------------------------------------------
# Auto-fix (safe fixes only)
# ---------------------------------------------------------------------------

def auto_fix_race(slug: str, comparison: dict, dry_run: bool = False) -> list:
    """Apply safe auto-fixes based on comparison results.

    Only applies:
    - STALE_DATE: update date if month shift ≤ 2
    - ENRICHABLE: fill empty fields

    Never auto-fixes MISMATCH (lesson #33).

    Returns list of applied fix descriptions.
    """
    fixes = []
    path = RACE_DATA_DIR / f"{slug}.json"
    if not path.exists():
        return fixes

    data = json.loads(path.read_text())
    race = data.get("race", data)
    vitals = race.get("vitals", {})
    modified = False

    for field, info in comparison.get("fields", {}).items():
        cls = info["classification"]
        scraped = info["scraped"]

        if cls == "STALE_DATE" and field == "date_specific":
            # Guard: reject month shifts > 2
            old_month = _extract_month_num(info["profile"])
            new_month = _extract_month_num(str(scraped))
            shift = _month_distance(old_month, new_month)
            if shift > 2:
                fixes.append(f"SKIPPED {field}: month shift {shift} too large")
                continue

            fix_desc = f"date_specific: {info['profile']!r} -> {scraped!r}"
            if not dry_run:
                vitals["date_specific"] = str(scraped)
                modified = True
            fixes.append(fix_desc)

        elif cls == "ENRICHABLE" and scraped:
            # Map extract field names to profile field names
            profile_field = field
            fix_desc = f"{profile_field}: (empty) -> {scraped!r}"
            if not dry_run:
                vitals[profile_field] = scraped
                modified = True
            fixes.append(fix_desc)

    if modified and not dry_run:
        data["race"] = race
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

    return fixes


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_html_report(results: list) -> str:
    """Generate an HTML report from comparison results."""
    rows = []
    for r in sorted(results, key=lambda x: (
        {"MISMATCH": 0, "STALE_DATE": 1, "ENRICHABLE": 2, "CONFIRM": 3, "NO_DATA": 4}.get(x["summary"], 5),
        x["slug"],
    )):
        color = {
            "MISMATCH": "#ff4444",
            "STALE_DATE": "#ff8800",
            "ENRICHABLE": "#44aa44",
            "CONFIRM": "#888888",
            "NO_DATA": "#cccccc",
        }.get(r["summary"], "#cccccc")

        fields_html = ""
        for field, info in r["fields"].items():
            fields_html += f"<li><strong>{field}</strong>: {info['classification']} — {info['detail']}</li>"

        rows.append(f"""
        <tr>
          <td><span style="color:{color};font-weight:bold">{r['summary']}</span></td>
          <td>{r['slug']}</td>
          <td><ul style="margin:0;padding-left:1em">{fields_html}</ul></td>
        </tr>""")

    counts = {}
    for r in results:
        counts[r["summary"]] = counts.get(r["summary"], 0) + 1

    return f"""<!DOCTYPE html>
<html><head><title>Fact Check Report</title>
<style>
body {{ font-family: 'Sometype Mono', monospace; margin: 2em; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 2px solid black; padding: 8px; text-align: left; vertical-align: top; }}
th {{ background: #59473c; color: white; }}
ul {{ list-style: none; }}
</style></head>
<body>
<h1>Fact Check Report</h1>
<p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<p>Total: {len(results)} | MISMATCH: {counts.get('MISMATCH', 0)} |
STALE_DATE: {counts.get('STALE_DATE', 0)} | ENRICHABLE: {counts.get('ENRICHABLE', 0)} |
CONFIRM: {counts.get('CONFIRM', 0)} | NO_DATA: {counts.get('NO_DATA', 0)}</p>
<table>
<tr><th>Status</th><th>Race</th><th>Fields</th></tr>
{''.join(rows)}
</table>
</body></html>"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compare scraped extracts against race profile data"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview comparisons without writing")
    parser.add_argument("--tier", type=int, action="append", dest="tiers",
                        help="Only process races of this tier (repeatable)")
    parser.add_argument("--slug", help="Process single race by slug")
    parser.add_argument("--auto-fix", action="store_true",
                        help="Apply safe fixes (stale dates, enrichable fields)")
    parser.add_argument("--report", action="store_true",
                        help="Generate HTML report")
    args = parser.parse_args()

    tier_filters = set(args.tiers) if args.tiers else None
    sites = load_official_sites(tier_filters=tier_filters, slug_filter=args.slug)

    # Also check for extracts without matching sites (edge case)
    slugs_to_check = set(sites.keys())
    if args.slug:
        slugs_to_check.add(args.slug)

    results = []
    fixes_applied = 0

    for slug in sorted(slugs_to_check):
        comparison = compare_race(slug)
        if not comparison:
            continue

        results.append(comparison)

        tier = sites.get(slug, {}).get("tier", "?")
        print(f"T{tier} {slug}: {comparison['summary']}")
        for field, info in comparison["fields"].items():
            print(f"  {field}: {info['classification']} — {info['detail']}")

        if args.auto_fix and comparison["summary"] in ("STALE_DATE", "ENRICHABLE"):
            fixes = auto_fix_race(slug, comparison, dry_run=args.dry_run)
            for fix in fixes:
                prefix = "WOULD FIX" if args.dry_run else "FIXED"
                print(f"  {prefix}: {fix}")
                fixes_applied += 1

    print()
    print(f"Total: {len(results)} races checked")
    counts = {}
    for r in results:
        counts[r["summary"]] = counts.get(r["summary"], 0) + 1
    for cls in ["MISMATCH", "STALE_DATE", "ENRICHABLE", "CONFIRM", "NO_DATA"]:
        if counts.get(cls, 0) > 0:
            print(f"  {cls}: {counts[cls]}")
    if args.auto_fix:
        prefix = "Would apply" if args.dry_run else "Applied"
        print(f"  {prefix} {fixes_applied} fixes")

    # Save JSON report
    report_path = PROJECT_ROOT / "data" / "fact-check-report.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(f"\nReport saved: {report_path}")

    # Save HTML report
    if args.report:
        html_path = PROJECT_ROOT / "data" / "fact-check-report.html"
        html_path.write_text(generate_html_report(results))
        print(f"HTML report: {html_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
