#!/usr/bin/env python3
"""
Prose QC pre-filter — fast mechanical checks before adversarial LLM review.

Catches obvious issues that don't need LLM intelligence:
- Run-on sentences (> 40 words)
- Empty filler phrases
- Generic suffering zone names (no real geographic reference)
- Missing required JSON fields
- Score math validation (14 scores → overall)

Runs instantly. Files that pass go to adversarial_review.py (LLM pass).
Files that fail get flagged for immediate fix before spending tokens.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple


# ============================================
# FILLER PHRASES — exact match, always wrong
# ============================================
FILLER_PHRASES = [
    "in order to",
    "due to the fact that",
    "it is important to note that",
    "it should be noted that",
    "it is worth mentioning that",
    "as a matter of fact",
    "for all intents and purposes",
    "at this point in time",
    "in the event that",
    "with regard to",
    "in regard to",
    "on a daily basis",
    "in a timely manner",
    "each and every",
    "first and foremost",
    "last but not least",
]

# Generic suffering zone names — these should be real places
GENERIC_ZONE_PATTERNS = [
    r"(?i)\bthe\s+(hard|tough|brutal|difficult)\s+(section|part|stretch|segment)\b",
    r"(?i)\b(major|big|main)\s+(climb|hill|ascent)\b",
    r"(?i)\bmidway\s+(point|section)\b",
    r"(?i)\b(early|mid|late)\s+(race|course)\s+(challenge|section|segment)\b",
    r"(?i)\bthe\s+final\s+(push|stretch|climb)\b",
]

# Required top-level fields in canonical race JSON
REQUIRED_RACE_FIELDS = [
    "name",
    "display_name",
    "tagline",
    "vitals",
    "gravel_god_rating",
    "course_description",
    "biased_opinion",
    "black_pill",
]

REQUIRED_VITALS = [
    "distance_mi",
    "elevation_ft",
    "location",
    "date",
]

# 14 scoring variables
COURSE_VARS = ["logistics", "length", "technicality", "elevation", "climate", "altitude", "adventure"]
EDITORIAL_VARS = ["prestige", "race_quality", "experience", "community", "field_depth", "value", "expenses"]


def extract_prose_fields(data: dict) -> List[Tuple[str, str]]:
    """Extract all string values from JSON that contain prose (not keys/IDs/URLs)."""
    prose = []

    def walk(obj, path=""):
        if isinstance(obj, str):
            # Skip URLs, slugs, short labels, dates
            if (
                obj.startswith("http")
                or len(obj) < 20
                or re.match(r"^\d{4}-\d{2}-\d{2}$", obj)
                or path.endswith(".slug")
                or path.endswith(".seo.slug")
                or path.endswith("_url")
                or path.endswith("_id")
                or path.endswith("_badge")
            ):
                return
            prose.append((path, obj))
        elif isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")

    walk(data)
    return prose


def check_run_on_sentences(prose_fields: List[Tuple[str, str]]) -> List[dict]:
    """Find sentences over 40 words."""
    issues = []
    for field_path, text in prose_fields:
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            word_count = len(sentence.split())
            if word_count > 40:
                issues.append({
                    "type": "run_on_sentence",
                    "field": field_path,
                    "word_count": word_count,
                    "text": sentence[:120] + ("..." if len(sentence) > 120 else ""),
                })
    return issues


def check_filler_phrases(prose_fields: List[Tuple[str, str]]) -> List[dict]:
    """Find empty filler phrases."""
    issues = []
    for field_path, text in prose_fields:
        text_lower = text.lower()
        for phrase in FILLER_PHRASES:
            if phrase in text_lower:
                idx = text_lower.find(phrase)
                context = text[max(0, idx - 20):idx + len(phrase) + 20]
                issues.append({
                    "type": "filler_phrase",
                    "field": field_path,
                    "phrase": phrase,
                    "context": context.strip(),
                })
    return issues


def check_generic_zones(data: dict) -> List[dict]:
    """Check suffering zones for real geographic names."""
    issues = []
    race = data.get("race", {})
    course = race.get("course_description", {})
    zones = course.get("suffering_zones", [])

    for i, zone in enumerate(zones):
        label = zone.get("label", "")
        desc = zone.get("desc", "")
        combined = f"{label} {desc}"

        for pattern in GENERIC_ZONE_PATTERNS:
            if re.search(pattern, combined):
                # Check if there's ALSO a proper noun (capitalized multi-word)
                has_proper_noun = bool(re.search(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', label))
                if not has_proper_noun:
                    issues.append({
                        "type": "generic_suffering_zone",
                        "zone_index": i,
                        "label": label,
                        "reason": "No real geographic name — should reference actual trail/road/landmark name",
                    })
    return issues


def check_required_fields(data: dict) -> List[dict]:
    """Check for missing required JSON fields."""
    issues = []
    race = data.get("race", {})

    for field in REQUIRED_RACE_FIELDS:
        if field not in race:
            issues.append({
                "type": "missing_field",
                "field": f"race.{field}",
            })
        elif isinstance(race[field], str):
            min_len = 5 if field in ("name", "display_name") else 10
            if len(race[field].strip()) < min_len:
                issues.append({
                    "type": "stub_field",
                    "field": f"race.{field}",
                    "value": race[field],
                })

    # Check vitals
    vitals = race.get("vitals", {})
    for field in REQUIRED_VITALS:
        if field not in vitals:
            issues.append({
                "type": "missing_field",
                "field": f"race.vitals.{field}",
            })

    # Check biased_opinion sub-fields
    opinion = race.get("biased_opinion", {})
    for sub in ["summary", "verdict", "strengths", "weaknesses", "bottom_line"]:
        if sub not in opinion:
            issues.append({
                "type": "missing_field",
                "field": f"race.biased_opinion.{sub}",
            })

    # Check black_pill sub-fields
    black_pill = race.get("black_pill", {})
    for sub in ["truth", "consequences", "expectation_reset"]:
        if sub not in black_pill:
            # Also accept alternate key names
            alt_keys = {"truth": ["reality"], "consequences": [], "expectation_reset": []}
            found = any(alt in black_pill for alt in alt_keys.get(sub, []))
            if not found:
                issues.append({
                    "type": "missing_field",
                    "field": f"race.black_pill.{sub}",
                })

    return issues


def check_score_math(data: dict) -> List[dict]:
    """Validate that overall_score = (sum of 14 / 70) * 100."""
    issues = []
    race = data.get("race", {})
    rating = race.get("gravel_god_rating", {})

    overall = rating.get("overall_score")
    if overall is None:
        issues.append({"type": "missing_score", "field": "race.gravel_god_rating.overall_score"})
        return issues

    # Try to find the 14 individual scores
    # Support both nested (course_profile/editorial) and flat formats
    scores = {}

    # Nested format (v1 style)
    course_profile = rating.get("course_profile", {})
    if isinstance(course_profile, dict):
        for var in COURSE_VARS:
            val = course_profile.get(var)
            if isinstance(val, (int, float)):
                scores[var] = val
            elif isinstance(val, dict) and "score" in val:
                scores[var] = val["score"]

    # Also check race.course_profile (Unbound style)
    race_course = race.get("course_profile", {})
    if isinstance(race_course, dict):
        for var in COURSE_VARS:
            if var not in scores:
                val = race_course.get(var)
                if isinstance(val, dict) and "score" in val:
                    scores[var] = val["score"]
                elif isinstance(val, (int, float)):
                    scores[var] = val

    editorial = rating.get("editorial", {})
    if isinstance(editorial, dict):
        for var in EDITORIAL_VARS:
            val = editorial.get(var)
            if isinstance(val, (int, float)):
                scores[var] = val
            elif isinstance(val, dict) and "score" in val:
                scores[var] = val["score"]

    # Also check race.biased_opinion_ratings (Unbound style)
    opinion_ratings = race.get("biased_opinion_ratings", {})
    if isinstance(opinion_ratings, dict):
        for var in EDITORIAL_VARS:
            if var not in scores:
                val = opinion_ratings.get(var)
                if isinstance(val, dict) and "score" in val:
                    scores[var] = val["score"]
                elif isinstance(val, (int, float)):
                    scores[var] = val

    # Flat format (canonical target)
    for var in COURSE_VARS + EDITORIAL_VARS:
        if var not in scores and var in rating:
            val = rating[var]
            if isinstance(val, (int, float)):
                scores[var] = val

    if len(scores) == 14:
        total = sum(scores.values())
        expected = round((total / 70) * 100)
        if abs(overall - expected) > 2:  # Allow ±2 rounding tolerance
            issues.append({
                "type": "score_math_mismatch",
                "overall_score": overall,
                "calculated": expected,
                "sum_of_14": total,
                "individual_scores": scores,
            })
    elif len(scores) > 0:
        missing_vars = [v for v in COURSE_VARS + EDITORIAL_VARS if v not in scores]
        if missing_vars:
            issues.append({
                "type": "incomplete_scores",
                "found": len(scores),
                "expected": 14,
                "missing": missing_vars,
            })

    return issues


def check_placeholder_content(prose_fields: List[Tuple[str, str]]) -> List[dict]:
    """Check for placeholder/stub content."""
    issues = []
    placeholder_patterns = [
        r"(?i)\bTBD\b",
        r"(?i)\bcoming soon\b",
        r"(?i)\bdata limited\b",
        r"(?i)\bmore research needed\b",
        r"(?i)\bplaceholder\b",
        r"(?i)\bTODO\b",
        r"(?i)\bFIXME\b",
        r"(?i)\b\[.*?\]\b",  # [bracketed placeholders]
    ]
    for field_path, text in prose_fields:
        for pattern in placeholder_patterns:
            match = re.search(pattern, text)
            if match:
                issues.append({
                    "type": "placeholder_content",
                    "field": field_path,
                    "match": match.group(),
                    "context": text[max(0, match.start() - 20):match.end() + 20].strip(),
                })
    return issues


def run_prose_qc(data: dict) -> dict:
    """Run all prose QC checks on a race JSON object."""
    prose_fields = extract_prose_fields(data)

    all_issues = []
    all_issues.extend(check_run_on_sentences(prose_fields))
    all_issues.extend(check_filler_phrases(prose_fields))
    all_issues.extend(check_generic_zones(data))
    all_issues.extend(check_required_fields(data))
    all_issues.extend(check_score_math(data))
    all_issues.extend(check_placeholder_content(prose_fields))

    # Classify severity
    critical_types = {"missing_field", "score_math_mismatch", "placeholder_content"}
    warning_types = {"run_on_sentence", "filler_phrase", "generic_suffering_zone", "stub_field", "incomplete_scores"}

    critical = [i for i in all_issues if i["type"] in critical_types]
    warnings = [i for i in all_issues if i["type"] in warning_types]

    return {
        "passed": len(critical) == 0,
        "critical_count": len(critical),
        "warning_count": len(warnings),
        "ready_for_adversarial_review": len(critical) == 0,
        "critical_issues": critical,
        "warnings": warnings,
    }


# ============================================
# CLI interface
# ============================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fast prose QC pre-filter for race JSON files"
    )
    parser.add_argument("--file", required=True, help="JSON file to check")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    parser.add_argument("--json-output", action="store_true", help="Output raw JSON instead of formatted report")
    args = parser.parse_args()

    try:
        data = json.loads(Path(args.file).read_text())
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"ERROR: {e}")
        exit(2)

    results = run_prose_qc(data)

    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print("\n" + "=" * 60)
        print("PROSE QC PRE-FILTER")
        print("=" * 60 + "\n")

        if results["critical_issues"]:
            print(f"CRITICAL ISSUES ({results['critical_count']}):")
            for issue in results["critical_issues"]:
                print(f"  ✗ [{issue['type']}] {issue.get('field', '')}")
                for k, v in issue.items():
                    if k not in ("type", "field"):
                        print(f"    {k}: {v}")
            print()

        if results["warnings"]:
            print(f"WARNINGS ({results['warning_count']}):")
            for issue in results["warnings"]:
                print(f"  ⚠ [{issue['type']}] {issue.get('field', '')}")
                detail = issue.get("text") or issue.get("context") or issue.get("label") or ""
                if detail:
                    print(f"    {detail[:100]}")
            print()

        print("=" * 60)
        if results["passed"]:
            if results["warning_count"] > 0:
                print(f"✓ PASSED (with {results['warning_count']} warnings) — ready for adversarial review")
            else:
                print("✓ PASSED — ready for adversarial review")
        else:
            print("✗ FAILED — fix critical issues before adversarial review")
        print("=" * 60 + "\n")

    if args.strict and results["warning_count"] > 0:
        exit(1)
    elif not results["passed"]:
        exit(1)
    else:
        exit(0)
