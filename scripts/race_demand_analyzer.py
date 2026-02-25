"""Race demand analyzer — produces an 8-dimension demand vector from race JSON profiles.

Each dimension is scored 0-10 (integer, clamped).

Dimensions:
    durability       — fatigue resistance needed (distance-driven)
    climbing         — sustained climbing power (elevation-driven)
    vo2_power        — high-end aerobic power for competitive fields
    threshold        — sustained sub-max power
    technical        — bike handling + surges
    heat_resilience  — heat adaptation needed
    altitude         — high-altitude adaptation
    race_specificity — how much race-sim practice matters
"""

import argparse
import json
import os
import sys

DIMENSIONS = [
    "durability",
    "climbing",
    "vo2_power",
    "threshold",
    "technical",
    "heat_resilience",
    "altitude",
    "race_specificity",
]

HEAT_KEYWORDS = [
    "heat",
    "hot",
    "hydration",
    "sun exposure",
    "humidity",
    "heat adaptation",
    "overheating",
]


def _clamp(value: int) -> int:
    """Clamp an integer to 0-10."""
    return max(0, min(10, int(value)))


def _safe_get(d: dict, key: str, default=0):
    """Safely retrieve a value, returning default if missing or None."""
    val = d.get(key)
    if val is None:
        return default
    return val


def _safe_numeric(d: dict, key: str, default=0) -> float:
    """Safely retrieve a numeric value, coercing strings like '4,500-9,116'.

    For range strings, takes the first number. Strips commas.
    Returns default on any parse failure.
    """
    val = d.get(key)
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    # String coercion: take first number-like segment
    try:
        s = str(val).replace(",", "")
        # Handle ranges like '4500-9116' — take first number
        parts = s.split("-")
        return float(parts[0].strip())
    except (ValueError, IndexError):
        return default


# ── Individual scoring functions ──────────────────────────────────────


def _score_durability(vitals: dict, rating: dict) -> int:
    """Score fatigue resistance needed based on distance and discipline.

    Thresholds:
        >=200 mi: 10, >=150: 8, >=100: 6, >=75: 4, >=50: 2, else: 1
    Bikepacking discipline adds +2 (capped at 10).
    """
    distance = _safe_numeric(vitals, "distance_mi", 0)
    discipline = _safe_get(rating, "discipline", "gravel")

    if distance >= 200:
        score = 10
    elif distance >= 150:
        score = 8
    elif distance >= 100:
        score = 6
    elif distance >= 75:
        score = 4
    elif distance >= 50:
        score = 2
    else:
        score = 1

    if discipline == "bikepacking":
        score += 2

    return _clamp(score)


def _score_climbing(vitals: dict, rating: dict) -> int:
    """Score sustained climbing power.

    Formula: min(10, round(elevation_score * 1.5 + elevation_ft / 5000))
    """
    elevation_ft = _safe_numeric(vitals, "elevation_ft", 0)
    elevation_score = _safe_get(rating, "elevation", 0)
    raw = elevation_score * 1.5 + elevation_ft / 5000
    return _clamp(round(raw))


def _score_vo2_power(rating: dict) -> int:
    """Score high-end aerobic power for competitive fields.

    Formula: min(10, round((field_depth + prestige) * 1.0))
    """
    field_depth = _safe_get(rating, "field_depth", 0)
    prestige = _safe_get(rating, "prestige", 0)
    raw = (field_depth + prestige) * 1.0
    return _clamp(round(raw))


def _score_threshold(vitals: dict, rating: dict) -> int:
    """Score sustained sub-max power.

    Base: 75-150 mi: 7, 50-75 mi: 5, >150 mi: 4, else: 3
    Boost +1 if elevation_score >= 3 (sustained grinding).
    """
    distance = _safe_numeric(vitals, "distance_mi", 0)
    elevation_score = _safe_get(rating, "elevation", 0)

    if 75 <= distance <= 150:
        score = 7
    elif 50 <= distance < 75:
        score = 5
    elif distance > 150:
        score = 4
    else:
        score = 3

    if elevation_score >= 3:
        score += 1

    return _clamp(score)


def _score_technical(rating: dict) -> int:
    """Score bike handling + surges.

    Formula: min(10, technicality * 2)
    """
    technicality = _safe_get(rating, "technicality", 0)
    return _clamp(technicality * 2)


def _score_heat_resilience(race: dict) -> int:
    """Score heat adaptation needed.

    Base from climate score: if climate >= 4, start at climate * 2; else 0.
    Scan rider intel search_text for heat keywords: +2 if found (cap 10).
    Scan climate.challenges for heat keywords: +1 if found (cap 10).
    """
    rating = race.get("gravel_god_rating", {})
    climate_score = _safe_get(rating, "climate", 0)

    if climate_score >= 5:
        score = 10
    elif climate_score == 4:
        score = 6
    else:
        score = 0

    # Rider intel boost
    youtube_data = race.get("youtube_data", {})
    rider_intel = youtube_data.get("rider_intel", {})
    search_text = _safe_get(rider_intel, "search_text", "")
    if search_text:
        search_lower = search_text.lower()
        for keyword in HEAT_KEYWORDS:
            if keyword in search_lower:
                score += 2
                break

    # Climate challenges boost
    climate_block = race.get("climate", {})
    challenges = climate_block.get("challenges", [])
    challenges_text = " ".join(challenges).lower()
    for keyword in HEAT_KEYWORDS:
        if keyword in challenges_text:
            score += 1
            break

    return _clamp(score)


def _score_altitude(rating: dict) -> int:
    """Score high-altitude adaptation.

    Formula: min(10, altitude_score * 2)
    """
    altitude_score = _safe_get(rating, "altitude", 0)
    return _clamp(altitude_score * 2)


def _score_race_specificity(rating: dict) -> int:
    """Score how much race-sim practice matters.

    Formula: min(10, round((5 - tier) * 2 + prestige))
    """
    tier = _safe_get(rating, "tier", 4)
    prestige = _safe_get(rating, "prestige", 0)
    raw = (5 - tier) * 2 + prestige
    return _clamp(round(raw))


# ── Main analysis function ────────────────────────────────────────────


def analyze_race_demands(race_data: dict) -> dict:
    """Analyze a race JSON profile and return an 8-dimension demand vector.

    Args:
        race_data: Full JSON dict with 'race' key at top level.

    Returns:
        Dict mapping dimension name to integer score (0-10).
    """
    race = race_data.get("race", {})
    vitals = race.get("vitals", {})
    rating = race.get("gravel_god_rating", {})

    return {
        "durability": _score_durability(vitals, rating),
        "climbing": _score_climbing(vitals, rating),
        "vo2_power": _score_vo2_power(rating),
        "threshold": _score_threshold(vitals, rating),
        "technical": _score_technical(rating),
        "heat_resilience": _score_heat_resilience(race),
        "altitude": _score_altitude(rating),
        "race_specificity": _score_race_specificity(rating),
    }


def analyze_race_demands_from_file(path: str) -> dict:
    """Read a race JSON file and return the demand vector.

    Args:
        path: Path to a race JSON file.

    Returns:
        Dict mapping dimension name to integer score (0-10).
    """
    with open(path) as f:
        data = json.load(f)
    return analyze_race_demands(data)


# ── CLI ───────────────────────────────────────────────────────────────


def _race_data_dir() -> str:
    """Return the path to the race-data directory."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "race-data")


def _print_table(slug: str, demands: dict) -> None:
    """Print a demand vector as a formatted table."""
    print(f"\n{'=' * 50}")
    print(f"  {slug}")
    print(f"{'=' * 50}")
    print(f"  {'Dimension':<20} {'Score':>5}")
    print(f"  {'-' * 20} {'-' * 5}")
    for dim in DIMENSIONS:
        bar = "#" * demands[dim] + "." * (10 - demands[dim])
        print(f"  {dim:<20} {demands[dim]:>5}  [{bar}]")
    total = sum(demands.values())
    print(f"  {'-' * 20} {'-' * 5}")
    print(f"  {'TOTAL':<20} {total:>5}  / {len(DIMENSIONS) * 10}")
    print()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze race demand vectors from race JSON profiles."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slug", help="Race slug (e.g. unbound-200)")
    group.add_argument("--all", action="store_true", help="Analyze all races, output summary CSV")

    args = parser.parse_args()
    race_dir = _race_data_dir()

    if args.slug:
        path = os.path.join(race_dir, f"{args.slug}.json")
        if not os.path.exists(path):
            print(f"Error: {path} not found", file=sys.stderr)
            sys.exit(1)
        demands = analyze_race_demands_from_file(path)
        _print_table(args.slug, demands)

    elif args.all:
        # CSV header
        header = ["slug"] + DIMENSIONS + ["total"]
        print(",".join(header))

        json_files = sorted(f for f in os.listdir(race_dir) if f.endswith(".json"))
        for filename in json_files:
            slug = filename.replace(".json", "")
            path = os.path.join(race_dir, filename)
            try:
                demands = analyze_race_demands_from_file(path)
            except Exception as e:
                print(f"# ERROR: {slug}: {e}", file=sys.stderr)
                continue
            total = sum(demands.values())
            row = [slug] + [str(demands[d]) for d in DIMENSIONS] + [str(total)]
            print(",".join(row))


if __name__ == "__main__":
    main()
