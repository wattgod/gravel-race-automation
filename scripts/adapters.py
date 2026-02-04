#!/usr/bin/env python3
"""
Schema adapters — canonical JSON → consumer-specific formats.

Three adapters for four consumers:
  1. canonical_to_push_pages: Canonical → push_pages.py (V2, mostly passthrough)
  2. canonical_to_guide_v1:   Canonical → main guide_generator.py (V1, key renames + nesting)
  3. canonical_to_guide_v3:   Canonical → races/generation_modules guide_generator.py (V3/V4, restructure)

Usage:
    python adapters.py --file race.json --format push_pages
    python adapters.py --file race.json --format guide_v1
    python adapters.py --file race.json --format guide_v3
    python adapters.py --file race.json --format all --validate
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Optional


def _parse_location(location_str: str) -> dict:
    """Parse 'City, State' string into {city, state} object."""
    if not location_str or "," not in location_str:
        return {"city": location_str or "", "state": ""}
    parts = [p.strip() for p in location_str.split(",", 1)]
    return {"city": parts[0], "state": parts[1]}


def _get_score(race: dict, var_name: str, default: int = 3) -> int:
    """Extract a score variable from canonical format.

    Checks multiple locations:
    - race.gravel_god_rating.<var> (flat canonical)
    - race.course_profile.<var>.score (v1 nested)
    - race.biased_opinion_ratings.<var>.score (v1 nested editorial)
    """
    rating = race.get("gravel_god_rating", {})
    if var_name in rating and isinstance(rating[var_name], (int, float)):
        return int(rating[var_name])

    for section_key in ("course_profile", "biased_opinion_ratings"):
        section = race.get(section_key, {})
        entry = section.get(var_name, {})
        if isinstance(entry, dict) and "score" in entry:
            return int(entry["score"])

    return default


def canonical_to_push_pages(canonical: dict) -> dict:
    """Canonical JSON → push_pages.py format (V2).

    Mostly passthrough. push_pages reads:
      race.vitals.distance_mi, race.gravel_god_rating.overall_score,
      race.course_description.ridewithgps_id, etc.
    All of these exist in canonical format.
    """
    # Deep copy to avoid mutating input
    import copy
    output = copy.deepcopy(canonical)

    race = output.get("race", {})
    rating = race.get("gravel_god_rating", {})

    # Ensure tier_label exists (push_pages uses {{TIER_LABEL}})
    if "tier_label" not in rating and "editorial_tier_label" in rating:
        rating["tier_label"] = rating["editorial_tier_label"]
    elif "tier_label" not in rating and "display_tier_label" in rating:
        rating["tier_label"] = rating["display_tier_label"]
    elif "tier_label" not in rating:
        tier = rating.get("tier", rating.get("editorial_tier", rating.get("display_tier", 2)))
        rating["tier_label"] = f"TIER {tier}"

    return output


def canonical_to_guide_v1(canonical: dict) -> dict:
    """Canonical JSON → main guide_generator.py format (V1).

    Key transformations:
    - distance_mi → distance_miles
    - elevation_ft → elevation_gain_ft
    - vitals.location (string) → vitals.location.city/state (object)
    - gravel_god_rating flat scores → radar_scores.*.score (nested)
    - guide_variables.* → top-level race fields
    """
    race = canonical.get("race", {})
    vitals = race.get("vitals", {})
    guide_vars = race.get("guide_variables", {})
    location = _parse_location(vitals.get("location", ""))

    course_vars = ["logistics", "length", "technicality", "elevation", "climate", "altitude", "adventure"]

    v1_race = {
        "name": race.get("name", ""),
        "slug": race.get("slug", ""),
        "tagline": race.get("tagline", ""),
        "description": race.get("biased_opinion", {}).get("summary", race.get("tagline", "")),
        "vitals": {
            "distance_miles": vitals.get("distance_mi"),
            "elevation_gain_ft": vitals.get("elevation_ft"),
            "elevation_ft": vitals.get("elevation_ft"),  # altitude reference
            "location": location,
        },
        "radar_scores": {
            var: {"score": _get_score(race, var)}
            for var in course_vars
        },
        "support_url": race.get("logistics", {}).get("official_site", ""),
        "recommended_tire_width": guide_vars.get("recommended_tire_width",
                                                  race.get("race_specific", {}).get("mechanicals", {}).get("recommended_tire_width", "")),
        "aid_station_strategy": guide_vars.get("aid_station_strategy", ""),
        "weather_strategy": guide_vars.get("weather_strategy", ""),
        "tactics": guide_vars.get("tactics", race.get("race_specific", {}).get("tactics", "")),
        "equipment_checklist": guide_vars.get("equipment_checklist", []),
        "skill_notes": guide_vars.get("skill_notes", ""),
        "non_negotiables": guide_vars.get("non_negotiables", race.get("non_negotiables", [])),
    }

    return {"race": v1_race}


def canonical_to_guide_v3(canonical: dict) -> dict:
    """Canonical JSON → races/generation_modules format (V3/V4).

    Restructures from race.* hierarchy to top-level sections:
    - race_metadata, race_characteristics, race_hooks
    - guide_variables, non_negotiables, race_specific
    - workout_modifications, masterclass_topics, tier_overrides (V4 training blocks)
    - marketplace_variables
    """
    race = canonical.get("race", {})
    vitals = race.get("vitals", {})
    climate = race.get("climate", {})
    guide_vars = race.get("guide_variables", {})

    # Parse altitude from various locations
    altitude_ft = (
        guide_vars.get("altitude_feet")
        or vitals.get("start_elevation_ft")
        or 0
    )
    if isinstance(altitude_ft, str):
        try:
            altitude_ft = int(re.sub(r'[^\d]', '', altitude_ft))
        except ValueError:
            altitude_ft = 0

    # Determine altitude category
    if altitude_ft >= 8000:
        altitude_cat = "high"
    elif altitude_ft >= 5000:
        altitude_cat = "moderate"
    else:
        altitude_cat = "low"

    output = {
        "race_metadata": {
            "name": race.get("display_name", race.get("name", "")),
            "full_name": race.get("display_name", race.get("name", "")),
            "distance_miles": vitals.get("distance_mi"),
            "elevation_feet": vitals.get("elevation_ft"),
            "date": vitals.get("date", ""),
            "location": vitals.get("location", ""),
            "start_elevation_feet": altitude_ft,
            "max_elevation_feet": altitude_ft,  # Approximation, enrich in migration
            "avg_elevation_feet": altitude_ft,
        },
        "race_characteristics": {
            "climate": climate.get("primary", "").lower().split()[0] if climate.get("primary") else "",
            "altitude_feet": altitude_ft,
            "altitude_category": altitude_cat,
            "terrain": race.get("terrain", {}).get("primary", ""),
            "technical_difficulty": _map_tech_difficulty(_get_score(race, "technicality")),
            "typical_weather": climate.get("description", ""),
            "race_type": _classify_race_type(vitals.get("distance_mi", 0)),
        },
        "race_hooks": {
            "punchy": race.get("tagline", ""),
            "detail": race.get("biased_opinion", {}).get("summary", ""),
            "dark_mile": _extract_dark_mile(race),
        },
        "non_negotiables": race.get("non_negotiables", guide_vars.get("non_negotiables", [])),
        "guide_variables": guide_vars or {
            "race_name": race.get("display_name", race.get("name", "")),
            "race_distance": f"{vitals.get('distance_mi', '')} miles",
            "race_elevation": f"{vitals.get('elevation_ft', '')} feet",
            "race_date": vitals.get("date", ""),
            "race_location": vitals.get("location", ""),
            "race_terrain": race.get("terrain", {}).get("primary", ""),
            "race_weather": climate.get("description", ""),
            "race_challenges": climate.get("challenges", []),
            "altitude_section": altitude_ft >= 5000,
            "altitude_feet": altitude_ft if altitude_ft >= 5000 else None,
        },
        "race_specific": race.get("race_specific", {}),
    }

    # V4 training blocks — only include if they exist
    training_config = race.get("training_config", {})
    for key in ("workout_modifications", "masterclass_topics", "tier_overrides", "marketplace_variables"):
        val = training_config.get(key) or race.get(key)
        if val:
            output[key] = val

    return output


def _map_tech_difficulty(score: int) -> str:
    """Map technicality score (1-5) to difficulty label."""
    return {1: "easy", 2: "moderate", 3: "moderate", 4: "technical", 5: "extreme"}.get(score, "moderate")


def _classify_race_type(distance_mi) -> str:
    """Classify race by distance."""
    if distance_mi is None:
        return "unknown"
    if distance_mi >= 200:
        return "ultra_distance"
    if distance_mi >= 100:
        return "endurance"
    if distance_mi >= 50:
        return "standard"
    return "short"


def _extract_dark_mile(race: dict) -> Optional[int]:
    """Extract dark mile marker from race data."""
    # Check black_pill or course_description for suffering zones
    zones = race.get("course_description", {}).get("suffering_zones", [])
    if zones:
        # Pick the zone closest to 70-80% of race distance
        distance = race.get("vitals", {}).get("distance_mi", 100)
        target = distance * 0.75
        closest = min(zones, key=lambda z: abs(z.get("mile", 0) - target))
        return closest.get("mile")
    return None


def validate_adapter_output(output: dict, format_name: str) -> list:
    """Check adapter output for empty/missing critical fields."""
    issues = []

    if format_name == "push_pages":
        race = output.get("race", {})
        checks = [
            ("race.name", race.get("name")),
            ("race.vitals.distance_mi", race.get("vitals", {}).get("distance_mi")),
            ("race.vitals.location", race.get("vitals", {}).get("location")),
            ("race.gravel_god_rating.overall_score", race.get("gravel_god_rating", {}).get("overall_score")),
        ]
    elif format_name == "guide_v1":
        race = output.get("race", {})
        checks = [
            ("race.name", race.get("name")),
            ("race.vitals.distance_miles", race.get("vitals", {}).get("distance_miles")),
            ("race.vitals.location.city", race.get("vitals", {}).get("location", {}).get("city")),
            ("race.radar_scores.elevation.score", race.get("radar_scores", {}).get("elevation", {}).get("score")),
        ]
    elif format_name == "guide_v3":
        checks = [
            ("race_metadata.name", output.get("race_metadata", {}).get("name")),
            ("race_metadata.distance_miles", output.get("race_metadata", {}).get("distance_miles")),
            ("race_characteristics.terrain", output.get("race_characteristics", {}).get("terrain")),
            ("race_hooks.punchy", output.get("race_hooks", {}).get("punchy")),
        ]
    else:
        return [f"Unknown format: {format_name}"]

    for path, val in checks:
        if val is None or val == "" or val == 0:
            issues.append(f"Empty/missing: {path}")

    return issues


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert canonical race JSON to consumer formats")
    parser.add_argument("--file", required=True, help="Canonical race JSON file")
    parser.add_argument("--format", required=True, choices=["push_pages", "guide_v1", "guide_v3", "all"],
                        help="Output format")
    parser.add_argument("--output", help="Output file (default: stdout)")
    parser.add_argument("--validate", action="store_true", help="Validate output for missing fields")
    args = parser.parse_args()

    data = json.loads(Path(args.file).read_text())

    adapters = {
        "push_pages": canonical_to_push_pages,
        "guide_v1": canonical_to_guide_v1,
        "guide_v3": canonical_to_guide_v3,
    }

    if args.format == "all":
        results = {}
        all_valid = True
        for name, fn in adapters.items():
            output = fn(data)
            results[name] = output
            if args.validate:
                issues = validate_adapter_output(output, name)
                if issues:
                    all_valid = False
                    print(f"\n✗ {name}:", file=sys.stderr)
                    for issue in issues:
                        print(f"  - {issue}", file=sys.stderr)
                else:
                    print(f"✓ {name}: valid", file=sys.stderr)

        if args.output:
            Path(args.output).write_text(json.dumps(results, indent=2))
        else:
            print(json.dumps(results, indent=2))
        sys.exit(0 if all_valid else 1)
    else:
        fn = adapters[args.format]
        output = fn(data)

        if args.validate:
            issues = validate_adapter_output(output, args.format)
            if issues:
                print(f"✗ Validation issues:", file=sys.stderr)
                for issue in issues:
                    print(f"  - {issue}", file=sys.stderr)
                sys.exit(1)
            else:
                print(f"✓ {args.format}: valid", file=sys.stderr)

        if args.output:
            Path(args.output).write_text(json.dumps(output, indent=2))
        else:
            print(json.dumps(output, indent=2))
