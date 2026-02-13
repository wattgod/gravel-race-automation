#!/usr/bin/env python3
"""
Audit all race JSON files for data quality issues.

Checks:
1. Invalid lat/lng coordinates (range checks + plausibility)
2. ridewithgps_id set to non-numeric values
3. Missing or empty tagline fields
4. overall_score that doesn't match round((sum_of_14_scores / 70) * 100)
5. tier that doesn't match tier thresholds (T1>=80, T2>=60, T3>=45, T4<45)
6. Geographically implausible coordinates (US race with wrong hemisphere, etc.)
"""

import json
import re
import sys
from pathlib import Path

RACE_DATA_DIR = Path(__file__).resolve().parent.parent / "race-data"

# The 14 scoring criteria
SCORE_FIELDS = [
    "logistics", "length", "technicality", "elevation", "climate",
    "altitude", "adventure", "prestige", "race_quality", "experience",
    "community", "field_depth", "value", "expenses"
]


def expected_tier(score):
    if score >= 80:
        return 1
    elif score >= 60:
        return 2
    elif score >= 45:
        return 3
    else:
        return 4


def expected_tier_with_prestige(score, prestige):
    base = expected_tier(score)
    if prestige == 5 and score >= 75:
        return 1
    elif prestige == 5 and score < 75:
        return min(base, 2)
    elif prestige == 4:
        promoted = base - 1
        if promoted < 2:
            promoted = 2
        return promoted
    return base


# --- Region detection ---
# Priority: check specific non-US regions first, then US last.
# This avoids false positives from 2-letter state abbreviations matching
# country names (e.g. ", CO" in "Colombia", ", NE" in "New South Wales").

def detect_region(location):
    """
    Returns one of: 'us', 'canada', 'europe', 'africa', 's_america',
    'australia_nz', 'asia', 'central_america', or None.
    Checks non-US regions first to avoid abbreviation false positives.
    """
    if not location:
        return None
    loc_upper = location.upper()

    # Australia / NZ (check before US -- "New South Wales" has ", NE")
    au_nz = ["AUSTRALIA", "NEW ZEALAND", "TASMANIA", "QUEENSLAND",
             "NEW SOUTH WALES", "WHANGANUI", "TAUPO", "WOLLOMBI",
             "NELLIGEN", "MUDGEE", "TENTERFIELD"]
    for kw in au_nz:
        if kw in loc_upper:
            return "australia_nz"

    # South America (check before US -- "Colombia" has ", CO")
    sa = ["BRAZIL", "ARGENTINA", "CHILE", "COLOMBIA", "COLOMBIAN",
          "PERU", "ECUADOR", "URUGUAY", "PATAGONIA", "SOUTH AMERICA",
          "BOGOTÁ", "BOGOTA", "MEDELLÍN", "MEDELLIN", "CÓRDOBA"]
    for kw in sa:
        if kw in loc_upper:
            return "s_america"

    # Europe (check before US -- "Denmark" has ", DE", "Catalonia" has ", CA",
    #  "Finland" has ", PA" in Paijanne, "Netherlands" has ", NE")
    europe = [
        "FRANCE", "SPAIN", "ITALY", "GERMANY", "PORTUGAL", "BELGIUM",
        "NETHERLANDS", "SWITZERLAND", "AUSTRIA", "ENGLAND",
        "SCOTLAND", "WALES", "IRELAND", "NORWAY", "SWEDEN", "FINLAND",
        "DENMARK", "CZECH", "POLAND", "GREECE", "CROATIA", "SLOVENIA",
        "ROMANIA", "HUNGARY", "ICELAND", "ANDORRA", "MONACO",
        "LIECHTENSTEIN", "LUXEMBOURG", "EUROPE", "GIRONA", "CATALONIA",
        "LAHTI", "COPENHAGEN", "OSLO", "HEERLEN", "RODEN", "DRENTHE",
        "MALLORCA", "SARDINIA", "TUSCANY", "FLANDERS"
    ]
    for kw in europe:
        if kw in loc_upper:
            return "europe"
    # "UK" as a word boundary check to avoid matching inside other words
    if re.search(r'\bUK\b', loc_upper):
        return "europe"

    # Africa
    africa = ["SOUTH AFRICA", "KENYA", "MOROCCO", "ETHIOPIA", "TANZANIA",
              "NAMIBIA", "BOTSWANA", "UGANDA", "RWANDA", "AFRICA",
              "LESOTHO", "CAPE TOWN", "JOHANNESBURG"]
    for kw in africa:
        if kw in loc_upper:
            return "africa"

    # Canada
    canada = ["CANADA", "ONTARIO", "BRITISH COLUMBIA", "ALBERTA", "QUEBEC",
              "MANITOBA", "SASKATCHEWAN", "NOVA SCOTIA", "NEW BRUNSWICK",
              "PRINCE EDWARD", "NEWFOUNDLAND"]
    for kw in canada:
        if kw in loc_upper:
            return "canada"

    # Central America / Caribbean
    # Note: "MEXICO" must be checked carefully -- "New Mexico" is a US state.
    central = ["COSTA RICA", "GUATEMALA", "BELIZE", "PANAMA",
               "HONDURAS", "NICARAGUA", "EL SALVADOR", "CARIBBEAN",
               "DOMINICAN", "PUERTO RICO", "CUBA"]
    for kw in central:
        if kw in loc_upper:
            return "central_america"
    # Mexico: only if NOT preceded by "NEW"
    if "MEXICO" in loc_upper and "NEW MEXICO" not in loc_upper:
        return "central_america"

    # Asia / Middle East
    # Note: "TURKEY" is excluded because Turkey, Texas is a US location.
    # Use "TÜRKIYE" or check that Turkey isn't followed by a US state/city indicator.
    asia = ["JAPAN", "CHINA", "TAIWAN", "KOREA", "VIETNAM",
            "THAILAND", "NEPAL", "INDIA", "MONGOLIA", "ASIA",
            "ISRAEL", "JORDAN", "OMAN", "UAE", "TÜRKIYE",
            "PHILIPPINES", "INDONESIA", "MALAYSIA", "KANCHANABURI"]
    for kw in asia:
        if kw in loc_upper:
            return "asia"
    # Special handling for Turkey: only if NOT followed by a comma+state pattern
    if "TURKEY" in loc_upper and not re.search(r'TURKEY,\s+\w', loc_upper):
        return "asia"

    # US -- check full state names (these are unambiguous)
    us_states = [
        "ALABAMA", "ALASKA", "ARIZONA", "ARKANSAS", "CALIFORNIA", "COLORADO",
        "CONNECTICUT", "DELAWARE", "FLORIDA", "GEORGIA", "HAWAII", "IDAHO",
        "ILLINOIS", "INDIANA", "IOWA", "KANSAS", "KENTUCKY", "LOUISIANA",
        "MAINE", "MARYLAND", "MASSACHUSETTS", "MICHIGAN", "MINNESOTA",
        "MISSISSIPPI", "MISSOURI", "MONTANA", "NEBRASKA", "NEVADA",
        "NEW HAMPSHIRE", "NEW JERSEY", "NEW MEXICO", "NEW YORK",
        "NORTH CAROLINA", "NORTH DAKOTA", "OHIO", "OKLAHOMA", "OREGON",
        "PENNSYLVANIA", "RHODE ISLAND", "SOUTH CAROLINA", "SOUTH DAKOTA",
        "TENNESSEE", "TEXAS", "UTAH", "VERMONT", "VIRGINIA", "WASHINGTON",
        "WEST VIRGINIA", "WISCONSIN", "WYOMING"
    ]
    for state in us_states:
        if state in loc_upper:
            return "us"

    # US abbreviation check -- only at end of string or before a paren
    # e.g. "Emporia, KS" or "Central Oregon (multiple towns)"
    us_abbrevs = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY"
    }
    # Match ", XX" at end of string or ", XX " followed by more text
    m = re.search(r',\s+([A-Z]{2})(?:\s|$|\()', location.strip())
    if m and m.group(1) in us_abbrevs:
        return "us"

    if "USA" in loc_upper or "UNITED STATES" in loc_upper:
        return "us"

    return None


# Coordinate bounding boxes by region
REGION_BOUNDS = {
    "us": {
        "lat": (18, 72),    # includes Alaska and Hawaii
        "lng": (-180, -66),  # includes Alaska
        "lng_positive_ok": False,
    },
    "canada": {
        "lat": (42, 84),
        "lng": (-141, -52),
        "lng_positive_ok": False,
    },
    "europe": {
        "lat": (35, 72),
        "lng": (-30, 45),
        "lng_positive_ok": True,
    },
    "africa": {
        "lat": (-35, 38),
        "lng": (-18, 52),
        "lng_positive_ok": True,
    },
    "s_america": {
        "lat": (-56, 13),
        "lng": (-82, -34),
        "lng_positive_ok": False,
    },
    "australia_nz": {
        "lat": (-48, -10),
        "lng": (110, 180),
        "lng_positive_ok": True,
    },
    "asia": {
        "lat": (-10, 55),
        "lng": (25, 150),
        "lng_positive_ok": True,
    },
    "central_america": {
        "lat": (7, 33),
        "lng": (-118, -60),
        "lng_positive_ok": False,
    },
}


def audit_race(filepath):
    """Audit a single race file. Returns list of issue strings."""
    issues = []

    try:
        with open(filepath) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        issues.append(f"PARSE ERROR: {e}")
        return issues

    race = data.get("race", {})

    # --- 1. Tagline ---
    tagline = race.get("tagline")
    if not tagline or (isinstance(tagline, str) and tagline.strip() == ""):
        issues.append("MISSING TAGLINE: tagline is empty or missing")

    # --- 2. Coordinates ---
    vitals = race.get("vitals", {})
    lat = vitals.get("lat")
    lng = vitals.get("lng")
    location = vitals.get("location", "")

    if lat is None or lng is None:
        issues.append(f"MISSING COORDS: lat={lat}, lng={lng}")
    else:
        if not isinstance(lat, (int, float)):
            issues.append(f"INVALID LAT TYPE: lat={lat} (type={type(lat).__name__})")
        elif not isinstance(lng, (int, float)):
            issues.append(f"INVALID LNG TYPE: lng={lng} (type={type(lng).__name__})")
        else:
            # Absolute range check
            if abs(lat) > 90:
                issues.append(f"LAT IMPOSSIBLE: lat={lat} (must be -90 to 90)")
            if abs(lng) > 180:
                issues.append(f"LNG IMPOSSIBLE: lng={lng} (must be -180 to 180)")

            # Habitable range (no race should be in Antarctica)
            if lat < -56 or lat > 72:
                issues.append(f"LAT OUT OF HABITABLE RANGE: lat={lat}")

            # Region-specific plausibility
            region = detect_region(location)
            if region and region in REGION_BOUNDS:
                bounds = REGION_BOUNDS[region]
                lat_min, lat_max = bounds["lat"]
                lng_min, lng_max = bounds["lng"]

                if lat < lat_min or lat > lat_max:
                    issues.append(
                        f"GEO MISMATCH ({region.upper()}): lat={lat} "
                        f"outside [{lat_min}, {lat_max}] for '{location}'"
                    )
                if lng < lng_min or lng > lng_max:
                    issues.append(
                        f"GEO MISMATCH ({region.upper()}): lng={lng} "
                        f"outside [{lng_min}, {lng_max}] for '{location}'"
                    )

            # Possible lat/lng swap: if lat is in lng range and vice versa
            if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
                if abs(lat) > 90 and abs(lng) <= 90:
                    issues.append(f"POSSIBLE LAT/LNG SWAP: lat={lat}, lng={lng}")

    # --- 3. RideWithGPS ID ---
    course_desc = race.get("course_description", {})
    rwgps_id = course_desc.get("ridewithgps_id")
    if rwgps_id is not None and rwgps_id != "":
        if isinstance(rwgps_id, str):
            stripped = rwgps_id.strip()
            if stripped.upper() in ("TBD", "N/A", "NONE", ""):
                issues.append(f"RWGPS PLACEHOLDER: ridewithgps_id='{rwgps_id}'")
            elif not stripped.isdigit():
                issues.append(f"RWGPS NON-NUMERIC: ridewithgps_id='{rwgps_id}'")

    # --- 4. Score calculation ---
    rating = race.get("gravel_god_rating", {})
    overall_score = rating.get("overall_score")

    if overall_score is not None:
        score_values = []
        missing_fields = []
        for field in SCORE_FIELDS:
            val = rating.get(field)
            if val is None or not isinstance(val, (int, float)):
                missing_fields.append(field)
            else:
                score_values.append(val)

        if missing_fields:
            issues.append(f"MISSING SCORE FIELDS: {', '.join(missing_fields)}")
        elif len(score_values) == 14:
            computed = round((sum(score_values) / 70) * 100)
            if computed != overall_score:
                issues.append(
                    f"SCORE MISMATCH: overall_score={overall_score}, "
                    f"computed=round(({sum(score_values)}/70)*100)={computed} "
                    f"(diff={overall_score - computed})"
                )

    # --- 5. Tier check ---
    tier = rating.get("tier")
    prestige = rating.get("prestige")

    if tier is not None and overall_score is not None:
        expected_t = expected_tier_with_prestige(overall_score, prestige)
        base_t = expected_tier(overall_score)

        if tier != expected_t and tier != base_t:
            tier_override = rating.get("tier_override_reason", "")
            editorial_tier = rating.get("editorial_tier")
            extra = ""
            if tier_override:
                extra = f" (override_reason: '{tier_override}')"
            if editorial_tier and editorial_tier != tier:
                extra += f" (editorial_tier={editorial_tier})"
            issues.append(
                f"TIER MISMATCH: tier={tier}, expected={expected_t} "
                f"(score={overall_score}, prestige={prestige}, "
                f"base_tier={base_t}){extra}"
            )

    # --- 6. display_tier vs tier ---
    display_tier = rating.get("display_tier")
    if display_tier is not None and tier is not None and display_tier != tier:
        issues.append(f"DISPLAY_TIER MISMATCH: display_tier={display_tier}, tier={tier}")

    # --- 7. Score values out of 1-5 range ---
    for field in SCORE_FIELDS:
        val = rating.get(field)
        if val is not None and isinstance(val, (int, float)):
            if val < 1 or val > 5:
                issues.append(f"SCORE OUT OF RANGE: {field}={val} (expected 1-5)")

    return issues


def main():
    if not RACE_DATA_DIR.exists():
        print(f"ERROR: Race data directory not found: {RACE_DATA_DIR}")
        sys.exit(1)

    json_files = sorted(RACE_DATA_DIR.glob("*.json"))
    print(f"Auditing {len(json_files)} race files in {RACE_DATA_DIR}\n")

    total_issues = 0
    issue_counts = {}
    races_with_issues = 0

    for filepath in json_files:
        issues = audit_race(filepath)
        if issues:
            races_with_issues += 1
            print(f"=== {filepath.stem} ===")
            for issue in issues:
                print(f"  - {issue}")
                category = issue.split(":")[0]
                issue_counts[category] = issue_counts.get(category, 0) + 1
                total_issues += 1
            print()

    # Summary
    print("=" * 60)
    print(f"SUMMARY: {total_issues} issues found across {races_with_issues} races "
          f"(out of {len(json_files)} total)")
    print()
    if issue_counts:
        print("Issues by category:")
        for category, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            print(f"  {category}: {count}")
    else:
        print("No issues found!")


if __name__ == "__main__":
    main()
