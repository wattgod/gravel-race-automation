#!/usr/bin/env python3
"""
Preflight quality check — runs before deploy and should run before any PR.

This script catches the specific shortcuts and quality failures that have
bitten us before. It is NOT a replacement for pytest — it checks structural
quality issues that tests don't cover.

Usage:
    python scripts/preflight_quality.py          # all checks
    python scripts/preflight_quality.py --js     # JS-only checks
    python scripts/preflight_quality.py --quick  # skip slow checks

Exit code: 0 = all pass, 1 = failures found.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORDPRESS_DIR = PROJECT_ROOT / "wordpress"

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"

failures = []
warnings = []


def check(name, condition, msg=""):
    if condition:
        print(f"  {PASS}  {name}")
    else:
        print(f"  {FAIL}  {name}: {msg}")
        failures.append(f"{name}: {msg}")


def warn(name, msg):
    print(f"  {WARN}  {name}: {msg}")
    warnings.append(f"{name}: {msg}")


# ── Check 1: No inline imports ──────────────────────────────


def check_no_inline_imports():
    """Ensure all imports are at module top level, not inline in functions."""
    print("\n── Inline Import Check ──")
    gen = WORDPRESS_DIR / "generate_prep_kit.py"
    text = gen.read_text()
    lines = text.split("\n")
    in_function = False
    indent_level = 0
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("def ") or stripped.startswith("class "):
            in_function = True
            indent_level = len(line) - len(stripped)
        elif in_function and stripped and not line[0].isspace():
            in_function = False
        if in_function and stripped.startswith("import ") and len(line) - len(stripped) > indent_level:
            check(f"Line {i}", False, f"Inline import found: {stripped}")
            return
    check("No inline imports in generate_prep_kit.py", True)


# ── Check 2: JS/Python constant parity ─────────────────────


def check_js_python_constant_parity():
    """Verify that shared constants between Python and JS are identical."""
    print("\n── JS/Python Constant Parity ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_prep_kit as gpk

    js = gpk.build_prep_kit_js()

    # Heat multipliers
    for key, val in gpk.HEAT_MULTIPLIERS.items():
        check(f"HEAT_MULT.{key}={val}", f"{key}:{val}" in js,
              f"Python has {key}:{val} but not found in JS")

    # Sweat multipliers
    for key, val in gpk.SWEAT_MULTIPLIERS.items():
        check(f"SWEAT_MULT.{key}={val}", f"{key}:{val}" in js,
              f"Python has {key}:{val} but not found in JS")

    # Sodium boosts
    for key, val in gpk.SODIUM_HEAT_BOOST.items():
        check(f"SODIUM_HEAT_BOOST.{key}={val}", f"{key}:{val}" in js,
              f"Python has {key}:{val} but not found in JS")
    for key, val in gpk.SODIUM_CRAMP_BOOST.items():
        check(f"SODIUM_CRAMP_BOOST.{key}={val}", f"{key}:{val}" in js,
              f"Python has {key}:{val} but not found in JS")

    # Item constants
    check("GEL_CARBS=25", "/25" in js or "25)" in js, "GEL_CARBS=25 not in JS")
    check("DRINK_CARBS=40", "/40" in js, "DRINK_CARBS_500ML=40 not in JS")
    check("BAR_CARBS=35", "/35" in js, "BAR_CARBS=35 not in JS")


# ── Check 3: JS syntax validation via Node.js ──────────────


def check_js_syntax():
    """Parse the generated JS through Node.js to catch syntax errors."""
    print("\n── JS Syntax Validation ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_prep_kit as gpk

    js = gpk.build_prep_kit_js()
    # Wrap in IIFE to avoid DOM references crashing Node
    # We just want syntax parsing, not execution
    test_script = f"""
try {{
    new Function({json.dumps(js)});
    console.log('SYNTAX_OK');
}} catch(e) {{
    console.log('SYNTAX_ERROR: ' + e.message);
    process.exit(1);
}}
"""
    result = subprocess.run(
        ["node", "-e", test_script],
        capture_output=True, text=True, timeout=10
    )
    check("JS parses without syntax errors",
          result.returncode == 0 and "SYNTAX_OK" in result.stdout,
          result.stderr or result.stdout)


# ── Check 4: All 328 races classify climate without error ──


def check_climate_classification(quick=False):
    """Verify every race JSON classifies to a valid climate heat category."""
    print("\n── Climate Classification ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_prep_kit as gpk

    data_dir = PROJECT_ROOT / "race-data"
    jsons = sorted(data_dir.glob("*.json"))
    errors = []
    distribution = {"cool": 0, "mild": 0, "warm": 0, "hot": 0, "extreme": 0}

    for jf in jsons:
        data = json.loads(jf.read_text(encoding="utf-8"))
        race = data.get("race", data)
        climate = race.get("climate")
        score = (race.get("gravel_god_rating") or {}).get("climate")
        result = gpk.classify_climate_heat(climate, score)
        if result not in distribution:
            errors.append(f"{jf.stem}: invalid classification '{result}'")
        else:
            distribution[result] += 1

    total = sum(distribution.values())
    check(f"All {total} races classify", len(errors) == 0,
          f"{len(errors)} errors: {errors[:3]}")

    # Sanity check distribution — mild should be most common
    print(f"    Distribution: {distribution}")
    if distribution["extreme"] > 10:
        warn("Climate distribution", f"{distribution['extreme']} extreme races seems high")
    if distribution["mild"] < 50:
        warn("Climate distribution", f"Only {distribution['mild']} mild races — expected >50")


# ── Check 5: Worker JS has hydration fields ─────────────────


def check_worker_hydration_fields():
    """Verify the Cloudflare Worker captures all hydration fields."""
    print("\n── Worker Hydration Fields ──")
    worker_path = PROJECT_ROOT / "workers" / "fueling-lead-intake" / "worker.js"
    text = worker_path.read_text()

    required_fields = [
        "fluid_target_ml_hr",
        "sodium_mg_hr",
        "sweat_tendency",
        "fuel_format",
        "cramp_history",
        "climate_heat",
    ]
    for field in required_fields:
        check(f"Worker has {field}", field in text,
              f"{field} not found in worker.js")


# ── Check 6: CSS classes referenced in JS exist in CSS ──────


def check_css_js_class_sync():
    """Verify CSS classes referenced in JS rendering actually exist in CSS."""
    print("\n── CSS/JS Class Sync ──")
    sys.path.insert(0, str(WORDPRESS_DIR))
    import generate_prep_kit as gpk

    css = gpk.build_prep_kit_css()
    js = gpk.build_prep_kit_js()

    # Extract CSS class references from JS (patterns like 'gg-pk-calc-xxx')
    js_classes = set(re.findall(r'gg-pk-calc-[\w-]+', js))
    css_classes = set(re.findall(r'\.(gg-pk-calc-[\w-]+)', css))

    for cls in js_classes:
        # Skip dynamic class prefixes (e.g., 'gg-pk-calc-item--' + type)
        if cls.endswith("--"):
            # Verify at least one variant exists in CSS
            variants = [c for c in css_classes if c.startswith(cls)]
            check(f".{cls}* variants in CSS", len(variants) > 0,
                  f"JS builds dynamic .{cls}* but no variants in CSS")
            continue
        # Fully-qualified dynamic classes
        if cls.startswith("gg-pk-calc-item--"):
            check(f".{cls} in CSS", cls in css_classes, f"JS references .{cls} but not in CSS")
        elif cls in ("gg-pk-calc-aid-row", "gg-pk-calc-aid-badge",
                     "gg-pk-calc-hour-num", "gg-pk-calc-hourly-table",
                     "gg-pk-calc-hourly-scroll", "gg-pk-calc-panel-title",
                     "gg-pk-calc-shopping-grid", "gg-pk-calc-shopping-item",
                     "gg-pk-calc-shopping-qty", "gg-pk-calc-shopping-label",
                     "gg-pk-calc-shopping-note",
                     "gg-pk-calc-result", "gg-pk-calc-result-row",
                     "gg-pk-calc-result-label", "gg-pk-calc-result-value",
                     "gg-pk-calc-result-highlight", "gg-pk-calc-result-note",
                     "gg-pk-calc-substack"):
            check(f".{cls} in CSS", cls in css_classes, f"JS references .{cls} but not in CSS")


def main():
    parser = argparse.ArgumentParser(description="Preflight quality checks")
    parser.add_argument("--js", action="store_true", help="JS-only checks")
    parser.add_argument("--quick", action="store_true", help="Skip slow checks")
    args = parser.parse_args()

    print("=" * 60)
    print("PREFLIGHT QUALITY CHECK")
    print("=" * 60)

    if args.js:
        check_js_syntax()
        check_js_python_constant_parity()
        check_css_js_class_sync()
    else:
        check_no_inline_imports()
        check_js_python_constant_parity()
        check_js_syntax()
        check_css_js_class_sync()
        check_worker_hydration_fields()
        if not args.quick:
            check_climate_classification()

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED: {len(failures)} issue(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    else:
        total = "JS" if args.js else "all"
        print(f"ALL CHECKS PASSED ({total})")
        if warnings:
            print(f"  {len(warnings)} warning(s)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
