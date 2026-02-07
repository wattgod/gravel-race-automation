#!/usr/bin/env python3
"""
LTGP Claims Validation Script

Checks race-data/*.json files for incorrect Life Time Grand Prix claims.
Run this before committing to catch LTGP errors.

Usage: python3 tests/validate_ltgp_claims.py
"""

import json
import re
from pathlib import Path

# Official LTGP events for 2025/2026 (current seasons)
CURRENT_LTGP_SLUGS = {
    "sea-otter-gravel",
    "fuego-mtb",
    "unbound-200",
    "leadville-100",
    "chequamegon-mtb",
    "little-sugar-mtb",
    "big-sugar"
}

# Former LTGP events (should say "former" not current)
FORMER_LTGP_SLUGS = {
    "crusher-in-the-tushar",  # Was LTGP 2024 only
    "rad-dirt-fest"           # Was LTGP 2024 only
}

# Events that should NEVER claim LTGP (but comparisons are OK)
NEVER_LTGP_SLUGS = {
    "steamboat-gravel",  # SBT GRVL - Amy Charity independent
    "mid-south",         # Bobby Wintle independent
    "bwr-san-diego",     # Belgian Waffle Ride series
    "bwr-california",
    "bwr-north-carolina",
    "bwr-cedar-city",
    "bwr-arizona",
    "the-traka",         # Gravel Earth Series
    "grinduro",
    "rebeccas-private-idaho",
    "torino-nice-rally",
    "badlands",
    "tour-divide",
    "transcontinental-race"
}

# Events that legitimately compare themselves to LTGP (not claiming to BE LTGP)
# These files mention LTGP in comparison/contrast context, which is allowed
COMPARISON_OK_SLUGS = {
    "gravel-earth",         # Compares GES to LTGP as alternative series
    "colorado-trail-race",  # Mentions LTGP production quality for contrast
    "jeroboam",             # States no LTGP affiliation
    "pirinexus-360",        # States no LTGP field depth
}

def check_file(filepath: Path) -> list:
    """Check a race JSON file for incorrect LTGP claims."""
    errors = []
    slug = filepath.stem

    try:
        with open(filepath, 'r') as f:
            content = f.read()
            data = json.loads(content)
    except Exception as e:
        return [f"{slug}: Failed to parse JSON - {e}"]

    # Get race data (handle both formats)
    race = data.get("race", data)

    # Patterns that indicate LTGP claims
    ltgp_patterns = [
        r"Life Time Grand Prix",
        r"LTGP",
        r"seriesAffiliation.*Life Time"
    ]

    has_ltgp_claim = any(re.search(p, content, re.IGNORECASE) for p in ltgp_patterns)

    if slug in CURRENT_LTGP_SLUGS:
        # This IS an LTGP event - claims are OK
        pass
    elif slug in FORMER_LTGP_SLUGS:
        # Former LTGP - should say "former" or "was" not current
        if has_ltgp_claim:
            if not re.search(r"(former|was|2024 only|removed from)", content, re.IGNORECASE):
                errors.append(f"{slug}: Claims LTGP but was only LTGP in 2024 - should say 'former LTGP'")
    elif slug in NEVER_LTGP_SLUGS:
        # Should NEVER claim LTGP
        if has_ltgp_claim:
            # Allow comparisons like "not LTGP" or "unlike LTGP"
            if not re.search(r"(not|isn't|unlike|without|lacks|no|doesn't have).*LTGP", content, re.IGNORECASE):
                errors.append(f"{slug}: Incorrectly claims LTGP status - this is NOT an LTGP event")
    elif slug in COMPARISON_OK_SLUGS:
        # These events legitimately mention LTGP for comparison/contrast
        # No error needed - they're comparing, not claiming
        pass
    else:
        # Unknown event - flag if claiming LTGP (but check for comparison context)
        if has_ltgp_claim:
            # More comprehensive comparison patterns
            comparison_patterns = [
                r"(not|isn't|unlike|without|lacks|no|doesn't have).*LTGP",
                r"LTGP.*(affiliation|status|event)",  # Discussing LTGP affiliation
                r"Life Time Grand Prix.*(production|polish|money|purse)",  # Comparing features
                r"(alternative|versus|vs\.?|compared to).*Life Time",  # Explicit comparisons
            ]
            is_comparison = any(re.search(p, content, re.IGNORECASE) for p in comparison_patterns)
            if not is_comparison:
                errors.append(f"{slug}: Claims LTGP - verify if correct (not in known list)")

    return errors

def main():
    race_data_dir = Path(__file__).parent.parent / "race-data"

    if not race_data_dir.exists():
        print(f"Error: race-data directory not found at {race_data_dir}")
        return 1

    all_errors = []
    files_checked = 0

    for json_file in sorted(race_data_dir.glob("*.json")):
        files_checked += 1
        errors = check_file(json_file)
        all_errors.extend(errors)

    print(f"Checked {files_checked} race files for LTGP claim accuracy\n")

    if all_errors:
        print("ERRORS FOUND:")
        for error in all_errors:
            print(f"  - {error}")
        print(f"\nTotal errors: {len(all_errors)}")
        print("\nReference: https://www.lifetimegrandprix.com/events/")
        return 1
    else:
        print("All LTGP claims validated successfully!")
        return 0

if __name__ == "__main__":
    exit(main())
