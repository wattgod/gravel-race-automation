#!/usr/bin/env python3
"""Validate meta-descriptions.json for deploy readiness.

Checks:
  - JSON structure and required fields
  - Description length (50-160 characters)
  - No duplicate descriptions
  - No Python repr leaks (\\n, \\t, list/dict literals)
  - WP ID uniqueness
  - Focus keyword presence in description (warning)
  - Full coverage of expected WP IDs

Usage:
    python scripts/validate_meta_descriptions.py
    python scripts/validate_meta_descriptions.py --verbose
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSON_FILE = PROJECT_ROOT / "seo" / "meta-descriptions.json"

MIN_LENGTH = 50
MAX_LENGTH = 160

# Expected WP IDs — all WordPress pages and posts minus skipped utility pages
SKIP_IDS = {3938, 3246, 3245, 3244}  # cart, instructor-reg, student-reg, dashboard

# All expected page IDs (58 pages minus 4 skipped = 54)
EXPECTED_PAGE_IDS = {
    448, 451, 470, 4993, 4994, 4995, 4996, 4997, 4998, 4999,
    5000, 5001, 5002, 5003, 5004, 5005, 5006, 5007, 5008, 5009,
    5010, 5011, 5012, 5013, 5014, 5016, 5017, 5018, 5019, 5020,
    5021, 5022, 5023, 5024, 5025, 5026, 5027, 5028, 5029, 5030,
    5031, 5032, 5033, 5034, 5035, 5036, 5037, 5038, 5039, 5040,
    5041, 5042, 5043, 5045,
}

# All expected post IDs (77 posts)
EXPECTED_POST_IDS = {
    901, 915, 922, 1078, 1186, 1230, 1269, 1431, 1496, 1499,
    1533, 1626, 1673, 1879, 1923, 1964, 2014, 2065, 2161, 2191,
    2209, 2298, 2324, 2345, 2394, 2414, 2445, 2469, 2521, 2552,
    2563, 2592, 2608, 2623, 2635, 2649, 2663, 2673, 2684, 2696,
    2716, 2790, 2830, 2844, 2904, 2916, 2927, 2942, 2956, 3203,
    3278, 3281, 3297, 3306, 3335, 3353, 3433, 3483, 3504, 3520,
    3537, 3581, 3594, 3617, 3631, 3641, 3653, 3662, 3673, 3694,
    3749, 3791, 3796, 3811, 3825, 3945, 4060,
}


def main():
    parser = argparse.ArgumentParser(description="Validate meta-descriptions.json")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    errors = []
    warnings = []

    # 1. File exists
    if not JSON_FILE.exists():
        print(f"FAIL: {JSON_FILE} not found")
        print("  Run: python scripts/generate_meta_descriptions.py")
        return 1

    # 2. Valid JSON
    try:
        data = json.loads(JSON_FILE.read_text())
    except json.JSONDecodeError as e:
        print(f"FAIL: Invalid JSON: {e}")
        return 1

    # 3. Structure check
    if "entries" not in data:
        errors.append("Missing 'entries' key in JSON")
    entries = data.get("entries", [])

    if not entries:
        errors.append("No entries in JSON")
        print(f"FAIL: {len(errors)} errors")
        for e in errors:
            print(f"  - {e}")
        return 1

    # 4. Required fields
    for i, e in enumerate(entries):
        for field in ("wp_id", "wp_type", "slug", "description"):
            if field not in e:
                errors.append(f"Entry {i}: missing required field '{field}'")

    # 5. Length checks
    for e in entries:
        desc = e.get("description", "")
        wp_id = e.get("wp_id", "?")
        slug = e.get("slug", "?")
        if len(desc) < MIN_LENGTH:
            errors.append(f"wp_id={wp_id} ({slug}): too short ({len(desc)} chars, min {MIN_LENGTH})")
        if len(desc) > MAX_LENGTH:
            errors.append(f"wp_id={wp_id} ({slug}): too long ({len(desc)} chars, max {MAX_LENGTH})")
        og = e.get("og_description", "")
        if og and len(og) > MAX_LENGTH:
            warnings.append(f"wp_id={wp_id}: og_description too long ({len(og)} chars)")

    # 6. No duplicates
    seen_descs = {}
    for e in entries:
        desc = e.get("description", "")
        wp_id = e.get("wp_id", "?")
        if desc in seen_descs:
            errors.append(f"Duplicate description: wp_id={wp_id} and wp_id={seen_descs[desc]}")
        seen_descs[desc] = wp_id

    # 7. No Python repr leaks
    for e in entries:
        for field in ("description", "og_description"):
            val = e.get(field) or ""
            if "\\n" in val or "\\t" in val:
                errors.append(f"wp_id={e.get('wp_id')}: repr leak in {field} (escaped newline/tab)")
            if val.startswith("[") or val.startswith("{"):
                errors.append(f"wp_id={e.get('wp_id')}: repr leak in {field} (starts with [{'{'})")

    # 8. WP ID uniqueness
    ids = [e.get("wp_id") for e in entries]
    if len(ids) != len(set(ids)):
        dupes = set(i for i in ids if ids.count(i) > 1)
        errors.append(f"Duplicate wp_ids: {dupes}")

    # 9. wp_type validation
    for e in entries:
        if e.get("wp_type") not in ("page", "post"):
            errors.append(f"wp_id={e.get('wp_id')}: invalid wp_type '{e.get('wp_type')}'")

    # 10. Coverage checks
    actual_ids = set(e.get("wp_id") for e in entries)
    all_expected = EXPECTED_PAGE_IDS | EXPECTED_POST_IDS

    missing = all_expected - actual_ids
    if missing:
        errors.append(f"Missing {len(missing)} expected WP IDs: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}")

    unexpected = actual_ids - all_expected
    if unexpected:
        warnings.append(f"Unexpected WP IDs (not in expected set): {sorted(unexpected)}")

    # 11. Focus keyword check (warning only)
    for e in entries:
        kw = e.get("focus_keyword")
        if kw and kw.lower() not in e.get("description", "").lower():
            if args.verbose:
                warnings.append(f"wp_id={e.get('wp_id')}: focus keyword '{kw}' not in description")

    # Report
    print(f"Validated {len(entries)} entries in {JSON_FILE.name}")
    print(f"  Pages: {sum(1 for e in entries if e.get('wp_type') == 'page')}")
    print(f"  Posts: {sum(1 for e in entries if e.get('wp_type') == 'post')}")

    if errors:
        print(f"\nFAILED: {len(errors)} error(s)")
        for e in errors:
            print(f"  ERROR: {e}")
    else:
        print("\nAll checks passed.")

    if warnings:
        print(f"\n{len(warnings)} warning(s)")
        for w in warnings:
            print(f"  WARN: {w}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
