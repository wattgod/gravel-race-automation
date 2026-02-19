#!/usr/bin/env python3
"""Inject vitals data into generic biased_opinion_ratings explanations.

Targets explanations that lack numbers/specifics by prepending concrete
data from the vitals dict (registration cost, distance, elevation, field size).

Zero API cost — pure data transformation.
"""

import json
import pathlib
import re
import sys

RACE_DATA = pathlib.Path(__file__).parent.parent / "race-data"

# Criteria → which vitals fields to inject
INJECTION_MAP = {
    "expenses": ["registration", "entry_fee"],
    "altitude": ["elevation_ft", "max_altitude_ft"],
    "length": ["distance_mi"],
    "field_depth": ["field_size", "participant_cap"],
}


def parse_cost(registration: str) -> str | None:
    """Extract cost string from registration field."""
    # Patterns: "Cost: ~$50-80", "Cost: $100-$150", "Cost: FREE", "Cost: ~€50-80"
    m = re.search(r'Cost:\s*~?\s*([A-Z]*\s*[\$€£][\d,]+(?:\s*[-–]\s*[\$€£]?\s*[\d,]+)?(?:\s*[A-Z]{2,4})?)', registration)
    if m:
        return m.group(1).strip()
    m = re.search(r'Cost:\s*(FREE)', registration, re.IGNORECASE)
    if m:
        return "free"
    return None


def has_dollar_amount(text: str) -> bool:
    """Check if text already contains a dollar/euro/pound amount."""
    return bool(re.search(r'[\$€£]\d+', text))


def has_number(text: str) -> bool:
    return bool(re.search(r'\d+', text))


def inject_expenses(explanation: str, vitals: dict) -> str | None:
    """Inject registration cost into expenses explanation if missing."""
    if has_dollar_amount(explanation):
        return None  # Already has cost info

    cost = None
    for key in INJECTION_MAP["expenses"]:
        val = vitals.get(key, "")
        if val:
            cost = parse_cost(str(val))
            if cost:
                break

    if not cost:
        return None

    # Skip if explanation already mentions "free entry" / "free registration"
    if cost.lower() == "free" and re.search(r'free\s+(entry|registration)', explanation, re.IGNORECASE):
        return None

    # Prepend cost context
    if cost.lower() == "free":
        prefix = "Registration is free."
    else:
        prefix = f"Registration runs {cost}."

    return f"{prefix} {explanation}"


def inject_altitude(explanation: str, vitals: dict) -> str | None:
    """Inject elevation gain into altitude explanation if missing."""
    if has_number(explanation):
        return None  # Already has numbers

    elev = vitals.get("elevation_ft", "")
    dist = vitals.get("distance_mi", "")

    if not elev:
        return None

    # Format elevation
    if isinstance(elev, (int, float)):
        elev_str = f"{int(elev):,}"
    else:
        elev_str = str(elev).replace(",", "").strip()
        # Try to format as number
        try:
            elev_str = f"{int(float(elev_str)):,}"
        except ValueError:
            pass

    # Format distance for context
    dist_str = ""
    if dist:
        dist_str = f" across {dist} miles" if isinstance(dist, (int, float)) else f" across {dist} miles"

    prefix = f"The route packs {elev_str}ft of elevation gain{dist_str}."
    return f"{prefix} {explanation}"


def inject_length(explanation: str, vitals: dict) -> str | None:
    """Inject distance into length explanation if missing."""
    if has_number(explanation):
        return None

    dist = vitals.get("distance_mi", "")
    if not dist:
        return None

    if isinstance(dist, (int, float)):
        prefix = f"At {dist} miles,"
    else:
        prefix = f"At {dist} miles,"

    return f"{prefix} {explanation[0].lower()}{explanation[1:]}"


def inject_field_depth(explanation: str, vitals: dict) -> str | None:
    """Inject field size into field_depth explanation if missing."""
    if has_number(explanation):
        return None

    field = vitals.get("field_size", "") or vitals.get("participant_cap", "")
    if not field:
        return None

    # Parse field size — could be "500", "~300", "150-200"
    field_str = str(field).strip()
    if not re.search(r'\d', field_str):
        return None

    # Avoid "riders riders" duplication
    prefix = f"With a field of {field_str},"
    return f"{prefix} {explanation[0].lower()}{explanation[1:]}"


def main():
    dry_run = "--dry-run" in sys.argv

    races = sorted(RACE_DATA.glob("*.json"))
    total_injected = 0
    changes_by_criterion = {}

    for f in races:
        d = json.loads(f.read_text())
        race = d.get("race", d)
        bor = race.get("biased_opinion_ratings", {})
        vitals = race.get("vitals", {})
        modified = False

        for criterion, inject_fn in [
            ("expenses", inject_expenses),
            # NOTE: altitude criterion is about thin-air effects, not climbing.
            # Injecting elevation_ft creates contradictions ("3500ft gain... no altitude effects")
            ("length", inject_length),
            ("field_depth", inject_field_depth),
        ]:
            entry = bor.get(criterion, {})
            if not isinstance(entry, dict):
                continue
            explanation = entry.get("explanation", "")
            if not explanation:
                continue

            new_explanation = inject_fn(explanation, vitals)
            if new_explanation and new_explanation != explanation:
                if dry_run:
                    print(f"  {f.stem}.{criterion}:")
                    print(f"    OLD: {explanation[:120]}")
                    print(f"    NEW: {new_explanation[:120]}")
                    print()
                else:
                    entry["explanation"] = new_explanation
                    modified = True
                total_injected += 1
                changes_by_criterion[criterion] = changes_by_criterion.get(criterion, 0) + 1

        if modified and not dry_run:
            f.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Injected vitals into {total_injected} explanations")
    for c, n in sorted(changes_by_criterion.items(), key=lambda x: -x[1]):
        print(f"  {c}: {n}")


if __name__ == "__main__":
    main()
