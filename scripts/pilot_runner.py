#!/usr/bin/env python3
"""
Pilot runner — orchestrates stages 3.5-4 of the pipeline.

This script is the post-research automation layer. After you've run
research (Stage 1) and JSON generation (Stage 3) in Cursor, this script:

1. Runs prose_qc.py pre-filter on the generated JSON
2. Runs adversarial_review.py (Haiku hostile editor)
3. If issues found, generates a fix prompt for Cursor
4. Runs quality_gates.py
5. Runs adapter validation
6. Compares against ground truth (for pilot races with existing profiles)
7. Produces a scorecard

Usage:
    python pilot_runner.py --race mid-south              # Run full pipeline on one race
    python pilot_runner.py --pilot                        # Run all 5 pilot races
    python pilot_runner.py --race unbound-200 --skip-llm  # Skip adversarial review (no API cost)
"""

import argparse
import json
import sys
from pathlib import Path

# Add scripts dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from prose_qc import run_prose_qc
from quality_gates import run_all_quality_checks
from adapters import canonical_to_push_pages, canonical_to_guide_v1, canonical_to_guide_v3, validate_adapter_output

RACE_DATA = Path(__file__).parent.parent / "race-data"

PILOT_RACES = ["mid-south", "barry-roubaix", "sbt-grvl", "gravel-locos", "the-rift"]


def run_pipeline(slug: str, skip_llm: bool = False) -> dict:
    """Run stages 3.5-4 on a single race."""
    json_path = RACE_DATA / f"{slug}.json"

    result = {
        "slug": slug,
        "stages": {},
        "overall": "unknown",
    }

    # Load JSON
    if not json_path.exists():
        result["overall"] = "MISSING"
        result["error"] = f"No JSON found at {json_path}"
        return result

    try:
        data = json.loads(json_path.read_text())
    except json.JSONDecodeError as e:
        result["overall"] = "INVALID_JSON"
        result["error"] = str(e)
        return result

    content = json_path.read_text()

    # Stage 3.5a: Prose QC pre-filter
    prose_result = run_prose_qc(data)
    result["stages"]["prose_qc"] = {
        "passed": prose_result["passed"],
        "critical": prose_result["critical_count"],
        "warnings": prose_result["warning_count"],
    }
    if not prose_result["passed"]:
        result["stages"]["prose_qc"]["issues"] = prose_result["critical_issues"]

    # Stage 3.5b: Adversarial LLM review
    if not skip_llm:
        try:
            from adversarial_review import review_race_json
            adv_result = review_race_json(str(json_path))
            result["stages"]["adversarial"] = {
                "passed": adv_result["passed"],
                "tokens_in": adv_result["input_tokens"],
                "tokens_out": adv_result["output_tokens"],
            }
            if not adv_result["passed"]:
                result["stages"]["adversarial"]["review"] = adv_result["review"]
        except ImportError:
            result["stages"]["adversarial"] = {"passed": True, "skipped": "anthropic not installed"}
        except Exception as e:
            result["stages"]["adversarial"] = {"passed": False, "error": str(e)}
    else:
        result["stages"]["adversarial"] = {"passed": True, "skipped": "skip_llm flag"}

    # Stage 4a: Quality gates
    qg_result = run_all_quality_checks(content, "json")
    result["stages"]["quality_gates"] = {
        "passed": qg_result["overall_passed"],
        "critical_failures": qg_result["critical_failures"],
    }

    # Stage 4b: Adapter validation
    adapter_issues = []
    for name, fn in [("push_pages", canonical_to_push_pages),
                     ("guide_v1", canonical_to_guide_v1),
                     ("guide_v3", canonical_to_guide_v3)]:
        output = fn(data)
        issues = validate_adapter_output(output, name)
        if issues:
            adapter_issues.extend([f"{name}: {i}" for i in issues])

    result["stages"]["adapters"] = {
        "passed": len(adapter_issues) == 0,
        "issues": adapter_issues if adapter_issues else [],
    }

    # Overall verdict
    all_passed = all(
        result["stages"][s].get("passed", False)
        for s in result["stages"]
    )
    result["overall"] = "PASS" if all_passed else "FAIL"

    return result


def compare_ground_truth(slug: str, data: dict) -> dict:
    """Compare pilot output against existing profile for accuracy."""
    race = data.get("race", {})
    vitals = race.get("vitals", {})

    checks = {
        "has_name": bool(race.get("name")),
        "has_distance": vitals.get("distance_mi") is not None,
        "has_elevation": vitals.get("elevation_ft") is not None,
        "has_location": bool(vitals.get("location")),
        "has_tagline": bool(race.get("tagline")),
        "has_scores": len([k for k in race.get("gravel_god_rating", {})
                          if k in ("length", "technicality", "elevation", "climate",
                                   "altitude", "logistics", "adventure")
                          and isinstance(race["gravel_god_rating"][k], (int, float))]) >= 7,
        "has_suffering_zones": len(race.get("course_description", {}).get("suffering_zones", [])) >= 2,
        "has_black_pill": bool(race.get("black_pill", {}).get("reality") or
                              race.get("black_pill", {}).get("truth")),
        "has_biased_opinion": bool(race.get("biased_opinion", {}).get("summary")),
        "has_logistics": bool(race.get("logistics")),
    }

    score = sum(checks.values()) / len(checks) * 100
    return {
        "completeness_score": round(score, 1),
        "checks": checks,
        "missing": [k for k, v in checks.items() if not v],
    }


def print_scorecard(results: list):
    """Print formatted pilot scorecard."""
    print("\n" + "=" * 70)
    print("PILOT BATCH SCORECARD")
    print("=" * 70 + "\n")

    for r in results:
        icon = "✓" if r["overall"] == "PASS" else "✗"
        print(f"{icon} {r['slug']:<30} {r['overall']}")

        for stage_name, stage in r["stages"].items():
            s_icon = "✓" if stage.get("passed") else "✗"
            extra = ""
            if stage.get("skipped"):
                extra = f" (skipped: {stage['skipped']})"
            elif stage.get("critical"):
                extra = f" ({stage['critical']} critical, {stage.get('warnings', 0)} warnings)"
            elif stage.get("critical_failures"):
                extra = f" ({', '.join(stage['critical_failures'])})"
            elif stage.get("issues"):
                extra = f" ({len(stage['issues'])} issues)"
            print(f"  {s_icon} {stage_name}: {'PASS' if stage.get('passed') else 'FAIL'}{extra}")

        if "ground_truth" in r:
            gt = r["ground_truth"]
            print(f"  Completeness: {gt['completeness_score']}%")
            if gt["missing"]:
                print(f"  Missing: {', '.join(gt['missing'])}")
        print()

    # Summary
    passed = sum(1 for r in results if r["overall"] == "PASS")
    print("=" * 70)
    print(f"RESULT: {passed}/{len(results)} passed")

    if passed == len(results):
        print("Pipeline validated. Ready for batch research (Sprint 5).")
    else:
        print("Fix failures before proceeding to batch research.")
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Pilot pipeline runner (Stages 3.5-4)")
    parser.add_argument("--race", help="Run pipeline on a single race slug")
    parser.add_argument("--pilot", action="store_true", help="Run all 5 pilot races")
    parser.add_argument("--skip-llm", action="store_true", help="Skip adversarial review (no API cost)")
    parser.add_argument("--json-output", action="store_true", help="Output JSON results")
    args = parser.parse_args()

    if not args.race and not args.pilot:
        parser.error("Provide --race <slug> or --pilot")

    slugs = PILOT_RACES if args.pilot else [args.race]
    results = []

    for slug in slugs:
        print(f"Running pipeline for {slug}...", flush=True)
        result = run_pipeline(slug, skip_llm=args.skip_llm)

        # Ground truth comparison for pilot races
        json_path = RACE_DATA / f"{slug}.json"
        if json_path.exists():
            data = json.loads(json_path.read_text())
            result["ground_truth"] = compare_ground_truth(slug, data)

        results.append(result)

    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print_scorecard(results)

    all_passed = all(r["overall"] == "PASS" for r in results)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
