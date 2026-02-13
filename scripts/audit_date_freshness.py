#!/usr/bin/env python3
"""
Data freshness audit for gravel race database.

Flags stale dates, missing data, content gaps, and generates an actionable report.

Usage:
    python scripts/audit_date_freshness.py
    python scripts/audit_date_freshness.py --json
    python scripts/audit_date_freshness.py --critical-only
    python scripts/audit_date_freshness.py --tier 1
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
CURRENT_YEAR = date.today().year


def load_race_data():
    """Load all race JSON files."""
    races = []
    for f in sorted(RACE_DATA_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            race = data.get("race", data)
            race["_file"] = f.name
            race["_slug"] = f.stem
            races.append(race)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  WARN  Could not load {f.name}: {e}", file=sys.stderr)
    return races


def parse_year_from_date(date_str):
    """Extract year from date_specific string like '2026: June 6'."""
    if not date_str:
        return None
    match = re.match(r"(\d{4})", str(date_str))
    return int(match.group(1)) if match else None


def check_stale_dates(race):
    """Check if race has stale or missing date."""
    issues = []
    date_str = race.get("vitals", {}).get("date_specific", "")
    if not date_str:
        date_str = race.get("vitals", {}).get("date", "")

    if not date_str:
        issues.append("No date field")
        return issues

    date_lower = str(date_str).lower()
    if "tbd" in date_lower or "check official" in date_lower:
        issues.append(f"TBD date: {date_str}")
        return issues

    year = parse_year_from_date(date_str)
    if year and year < CURRENT_YEAR:
        age = CURRENT_YEAR - year
        issues.append(f"Stale date ({age}yr old): {date_str}")

    return issues


def check_missing_fields(race):
    """Check for missing important fields."""
    issues = []
    vitals = race.get("vitals", {})
    gravel_god = race.get("gravel_god_rating", {})
    logistics = race.get("logistics", {})
    history = race.get("history", {})

    # Official website
    official = logistics.get("official_site", "") or vitals.get("website", "")
    if not official or not str(official).startswith("http"):
        organizer_site = race.get("organizer", {}).get("website", "")
        if not organizer_site or not str(organizer_site).startswith("http"):
            issues.append("No official website URL")

    # Founder/organizer
    if not history.get("founder"):
        if not race.get("organizer", {}).get("name"):
            issues.append("No founder or organizer")

    # Citations
    citations = race.get("citations", [])
    if len(citations) < 3:
        issues.append(f"Few citations ({len(citations)})")

    return issues


def check_content_gaps(race):
    """Check for content quality issues."""
    issues = []
    course_desc = race.get("course_description", {})
    final_verdict = race.get("final_verdict", {})

    if not course_desc.get("character"):
        issues.append("No course_description.character")

    if not race.get("non_negotiables"):
        issues.append("No non_negotiables")

    if not final_verdict.get("should_you_race"):
        issues.append("No final_verdict.should_you_race")

    if not race.get("tagline"):
        issues.append("No tagline")

    return issues


def check_research_age(race):
    """Check if research metadata is stale."""
    issues = []
    metadata = race.get("research_metadata", {})
    scored_at = metadata.get("scored_at", "")
    if scored_at:
        try:
            scored_date = datetime.strptime(scored_at[:10], "%Y-%m-%d").date()
            age_days = (date.today() - scored_date).days
            if age_days > 180:
                issues.append(f"Research {age_days} days old (scored {scored_at[:10]})")
        except ValueError:
            pass
    return issues


def check_price_freshness(race):
    """Check for stale price references."""
    issues = []
    reg = race.get("vitals", {}).get("registration", "")
    if reg:
        years_found = re.findall(r"\b(20\d{2})\b", str(reg))
        for yr in years_found:
            if int(yr) < CURRENT_YEAR:
                issues.append(f"Price references year {yr}: {str(reg)[:80]}")
                break
    return issues


def classify_severity(race, all_issues):
    """Classify overall severity for a race."""
    date_issues = all_issues.get("date", [])
    missing = all_issues.get("missing", [])
    content = all_issues.get("content", [])

    # Critical: TBD date + content gaps (stub profile)
    has_tbd = any("TBD" in i for i in date_issues)
    has_no_date = any("No date" in i for i in date_issues)
    has_content_gaps = len(content) >= 3

    if (has_tbd or has_no_date) and has_content_gaps:
        return "critical"

    # Stale: old dates
    if any("Stale date" in i for i in date_issues):
        return "stale"

    # Gap: missing content
    if content or missing:
        return "gap"

    return None


def audit_races(races, tier_filter=None):
    """Run all checks on all races, return categorized results."""
    results = {"critical": [], "stale": [], "gap": []}

    for race in races:
        gravel_god = race.get("gravel_god_rating", {})
        tier = gravel_god.get("tier") or gravel_god.get("display_tier")

        if tier_filter is not None and tier != tier_filter:
            continue

        all_issues = {
            "date": check_stale_dates(race),
            "missing": check_missing_fields(race),
            "content": check_content_gaps(race),
            "research": check_research_age(race),
            "price": check_price_freshness(race),
        }

        severity = classify_severity(race, all_issues)
        if severity is None:
            # Check if there are any issues at all
            flat = []
            for v in all_issues.values():
                flat.extend(v)
            if not flat:
                continue
            severity = "gap"

        flat_issues = []
        for v in all_issues.values():
            flat_issues.extend(v)

        results[severity].append({
            "slug": race["_slug"],
            "tier": tier,
            "issues": flat_issues,
        })

    return results


def print_report(results, total_count):
    """Print human-readable report."""
    print("DATA FRESHNESS REPORT")
    print("=" * 60)

    if results["critical"]:
        print(f"\nCRITICAL ({len(results['critical'])} races):")
        for r in sorted(results["critical"], key=lambda x: x["slug"]):
            issues = ", ".join(r["issues"])
            print(f"  {r['slug']:<40} {issues}")

    if results["stale"]:
        print(f"\nSTALE DATES ({len(results['stale'])} races):")
        for r in sorted(results["stale"], key=lambda x: x["slug"]):
            issues = ", ".join(r["issues"])
            print(f"  {r['slug']:<40} {issues}")

    if results["gap"]:
        print(f"\nMISSING CONTENT ({len(results['gap'])} races):")
        for r in sorted(results["gap"], key=lambda x: x["slug"]):
            issues = ", ".join(r["issues"])
            print(f"  {r['slug']:<40} {issues}")

    crit = len(results["critical"])
    stale = len(results["stale"])
    gaps = len(results["gap"])
    print(f"\nSUMMARY: {total_count} races | {crit} critical | {stale} stale | {gaps} gaps")


def main():
    parser = argparse.ArgumentParser(description="Audit race data freshness")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--critical-only", action="store_true", help="Only show critical issues")
    parser.add_argument("--tier", type=int, help="Filter to specific tier (1-4)")
    args = parser.parse_args()

    races = load_race_data()
    results = audit_races(races, tier_filter=args.tier)

    if args.critical_only:
        results["stale"] = []
        results["gap"] = []

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, len(races))

    # Exit code 1 if any critical issues
    if results["critical"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
