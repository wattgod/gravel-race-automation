#!/usr/bin/env python3
"""
Validate output quality - JSON structure, brief format, research completeness.
Prevents sloppy output from making it to production.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import requests
except ImportError:
    requests = None


def validate_json_structure(json_path: str) -> Tuple[bool, List[str]]:
    """Validate JSON matches required schema."""
    errors = []
    
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    
    # Check top-level structure
    if "race" not in data:
        errors.append("Missing 'race' key in JSON")
        return False, errors
    
    race = data["race"]
    
    # Required fields
    required_fields = {
        "name": str,
        "display_name": str,
        "vitals": dict,
        "tagline": str,
    }
    
    for field, field_type in required_fields.items():
        if field not in race:
            errors.append(f"Missing required field: race.{field}")
        elif not isinstance(race[field], field_type):
            errors.append(f"Invalid type for race.{field}: expected {field_type.__name__}")
    
    # Validate vitals
    if "vitals" in race:
        vitals = race["vitals"]
        required_vitals = ["location", "distance_mi", "elevation_ft"]
        for vital in required_vitals:
            if vital not in vitals:
                errors.append(f"Missing required vital: {vital}")
    
    # Validate radar scores
    if "gravel_god_rating" in race:
        rating = race["gravel_god_rating"]
        if "course_profile" in rating:
            profile = rating["course_profile"]
            radar_vars = ["logistics", "length", "technicality", "elevation", "climate", "altitude", "adventure"]
            for var in radar_vars:
                if var not in profile:
                    errors.append(f"Missing radar variable: {var}")
                elif not isinstance(profile[var], int) or not (1 <= profile[var] <= 5):
                    errors.append(f"Invalid radar score for {var}: must be 1-5")
    
    # Check for empty strings in critical fields
    critical_fields = ["name", "display_name", "tagline"]
    for field in critical_fields:
        if field in race and not race[field].strip():
            errors.append(f"Empty {field} field")
    
    return len(errors) == 0, errors


def validate_brief_format(brief_path: str) -> Tuple[bool, List[str]]:
    """Validate brief has required sections and format."""
    errors = []
    warnings = []
    
    content = Path(brief_path).read_text()
    
    # Required sections
    required_sections = [
        "RADAR SCORES",
        "TRAINING PLAN IMPLICATIONS",
        "THE BLACK PILL",
        "KEY QUOTES",
        "LOGISTICS SNAPSHOT"
    ]
    
    for section in required_sections:
        if section not in content:
            errors.append(f"Missing required section: {section}")
    
    # Check radar scores table
    if "RADAR SCORES" in content:
        radar_vars = ["Logistics", "Length", "Technicality", "Elevation", "Climate", "Altitude", "Adventure"]
        for var in radar_vars:
            if var not in content:
                warnings.append(f"Radar variable '{var}' not found in scores table")
    
    # Check for Matti voice indicators (should NOT have marketing speak)
    anti_patterns = [
        ("amazing opportunity", "Marketing language detected"),
        ("don't miss out", "Marketing language detected"),
        ("world-class experience", "Marketing language detected"),
        ("join us for", "Marketing language detected"),
    ]
    
    content_lower = content.lower()
    for pattern, message in anti_patterns:
        if pattern in content_lower:
            warnings.append(f"{message}: '{pattern}'")
    
    # Check for specific mile markers (research quality indicator)
    mile_marker_pattern = r'\bmile\s+\d+'
    if not re.search(mile_marker_pattern, content, re.IGNORECASE):
        warnings.append("No specific mile markers found - research may be too generic")
    
    # Check for quotes (should have forum quotes)
    if "KEY QUOTES" in content:
        quote_section = content.split("KEY QUOTES")[1].split("##")[0] if "##" in content.split("KEY QUOTES")[1] else content.split("KEY QUOTES")[1]
        if len(quote_section.strip()) < 100:
            warnings.append("KEY QUOTES section seems empty or too short")
    
    # Check Black Pill has substance
    if "THE BLACK PILL" in content:
        black_pill = content.split("THE BLACK PILL")[1].split("##")[0] if "##" in content.split("THE BLACK PILL")[1] else content.split("THE BLACK PILL")[1]
        if len(black_pill.strip()) < 200:
            warnings.append("THE BLACK PILL section seems too short - needs more depth")
    
    return len(errors) == 0, errors + warnings


def validate_research_quality(research_path: str) -> Tuple[bool, List[str]]:
    """Validate research dump has sufficient depth."""
    errors = []
    warnings = []
    
    content = Path(research_path).read_text()
    
    # Check minimum length (should be substantial)
    if len(content) < 2000:
        warnings.append(f"Research dump seems short ({len(content)} chars) - may lack depth")
    
    # Check for URLs (should have sources)
    url_pattern = r'https?://[^\s\)\]\"\'<>]+'
    urls = re.findall(url_pattern, content)
    if len(urls) < 3:
        warnings.append(f"Only {len(urls)} URLs found - research may lack sources")
    
    # Check for specific data points
    if not re.search(r'\d+\s*(mile|mi|km)', content, re.IGNORECASE):
        warnings.append("No specific distances/mile markers found")
    
    if not re.search(r'\d+°|temperature|weather|heat|cold', content, re.IGNORECASE):
        warnings.append("No weather/climate data found")
    
    # Check for forum indicators
    forum_indicators = ["reddit", "forum", "comment", "said", "posted"]
    has_forum_data = any(indicator in content.lower() for indicator in forum_indicators)
    if not has_forum_data:
        warnings.append("No forum/community data detected - may lack real rider insights")
    
    return len(errors) == 0, errors + warnings


def verify_ridewithgps(json_path: str) -> Tuple[bool, List[str]]:
    """Verify RideWithGPS route ID exists and is accessible.

    Returns (passed, issues). If no ridewithgps_id is set, returns (True, [warning]).
    If requests is not installed, returns (True, [warning]).
    """
    issues = []

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return False, [f"Cannot read JSON: {e}"]

    race = data.get("race", {})

    # Look for ridewithgps_id in multiple possible locations
    rwgps_id = None
    for path_fn in [
        lambda r: r.get("course_description", {}).get("ridewithgps_id"),
        lambda r: r.get("ridewithgps_id"),
        lambda r: r.get("vitals", {}).get("ridewithgps_id"),
    ]:
        val = path_fn(race)
        if val and val != 0:
            rwgps_id = val
            break

    if rwgps_id is None or rwgps_id == 0:
        return True, ["No ridewithgps_id set — not a failure, but route map won't render"]

    if requests is None:
        return True, ["requests library not installed — skipping HTTP verification"]

    url = f"https://ridewithgps.com/routes/{rwgps_id}"
    try:
        resp = requests.head(url, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return True, []
        else:
            return False, [f"RideWithGPS route {rwgps_id} returned HTTP {resp.status_code}: {url}"]
    except requests.RequestException as e:
        return False, [f"RideWithGPS verification failed for route {rwgps_id}: {e}"]


def validate_all_outputs(race_folder: str) -> Dict[str, Tuple[bool, List[str]]]:
    """Validate all outputs for a race."""
    results = {}
    
    # Validate research
    research_path = f"research-dumps/{race_folder}-raw.md"
    if Path(research_path).exists():
        results["research"] = validate_research_quality(research_path)
    else:
        results["research"] = (False, ["Research file not found"])
    
    # Validate brief
    brief_path = f"briefs/{race_folder}-brief.md"
    if Path(brief_path).exists():
        results["brief"] = validate_brief_format(brief_path)
    else:
        results["brief"] = (False, ["Brief file not found"])
    
    # Validate JSON
    json_path = f"landing-pages/{race_folder}.json"
    if Path(json_path).exists():
        results["json"] = validate_json_structure(json_path)
        # Also verify RideWithGPS route
        results["ridewithgps"] = verify_ridewithgps(json_path)
    else:
        results["json"] = (False, ["JSON file not found"])

    return results


def print_validation_report(results: Dict[str, Tuple[bool, List[str]]]):
    """Print formatted validation report."""
    print("\n" + "="*60)
    print("VALIDATION REPORT")
    print("="*60 + "\n")
    
    all_passed = True
    
    for output_type, (passed, issues) in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        icon = "✓" if passed else "✗"
        print(f"{icon} {output_type.upper()}: {status}")
        
        if issues:
            for issue in issues:
                if issue.startswith("Missing") or issue.startswith("Invalid"):
                    print(f"  ✗ ERROR: {issue}")
                    all_passed = False
                else:
                    print(f"  ⚠ WARNING: {issue}")
        print()
    
    print("="*60)
    if all_passed:
        print("✓ ALL VALIDATIONS PASSED")
    else:
        print("✗ VALIDATION FAILED - Fix errors before proceeding")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True, help="Race folder name")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings too")
    args = parser.parse_args()
    
    results = validate_all_outputs(args.folder)
    
    # Filter warnings if not strict
    if not args.strict:
        for key in results:
            passed, issues = results[key]
            errors_only = [i for i in issues if i.startswith("Missing") or i.startswith("Invalid")]
            results[key] = (passed and len(errors_only) == 0, errors_only)
    
    all_passed = print_validation_report(results)
    
    exit(0 if all_passed else 1)

