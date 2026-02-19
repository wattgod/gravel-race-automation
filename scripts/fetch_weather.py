#!/usr/bin/env python3
"""Fetch historical weather data from Open-Meteo and inject into climate explanations.

Uses the free Open-Meteo Historical Weather API to get actual temperature,
precipitation, and wind data for each race location + month. Injects concrete
weather stats into climate explanations.

Usage:
    python scripts/fetch_weather.py              # Fetch and inject
    python scripts/fetch_weather.py --dry-run    # Preview changes
    python scripts/fetch_weather.py --fetch-only # Just fetch, save to data/weather/
"""

import json
import pathlib
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

RACE_DATA = pathlib.Path(__file__).parent.parent / "race-data"
WEATHER_DIR = pathlib.Path(__file__).parent.parent / "data" / "weather"

# Open-Meteo historical weather API (free, no key needed)
# Docs: https://open-meteo.com/en/docs/historical-weather-api
BASE_URL = "https://archive-api.open-meteo.com/v1/archive"


def parse_month(date_str: str) -> int | None:
    """Extract month number from date string like 'Late March annually'."""
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    date_lower = date_str.lower()
    for name, num in months.items():
        if name in date_lower:
            return num
    return None


def fetch_weather(lat: float, lng: float, month: int) -> dict | None:
    """Fetch historical weather for a location + month (single API call, 2020-2024)."""
    from calendar import monthrange

    # Build date ranges for target month across 5 years
    # Open-Meteo supports multiple date ranges in one call — but to be safe,
    # we'll just grab the full 5-year span and filter to our month
    start = f"2020-{month:02d}-01"
    last_day = monthrange(2024, month)[1]
    end = f"2024-{month:02d}-{last_day}"

    params = {
        "latitude": lat,
        "longitude": lng,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,wind_speed_10m_max",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
    }

    url = BASE_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "GravelGod/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    daily = data.get("daily", {})
    dates = daily.get("time", [])

    # Filter to only our target month
    temps_max = []
    temps_min = []
    precip_vals = []
    wind_vals = []

    for i, date_str in enumerate(dates):
        date_month = int(date_str.split("-")[1])
        if date_month != month:
            continue
        t_max = (daily.get("temperature_2m_max") or [])[i] if i < len(daily.get("temperature_2m_max") or []) else None
        t_min = (daily.get("temperature_2m_min") or [])[i] if i < len(daily.get("temperature_2m_min") or []) else None
        p = (daily.get("precipitation_sum") or [])[i] if i < len(daily.get("precipitation_sum") or []) else None
        w = (daily.get("wind_speed_10m_max") or [])[i] if i < len(daily.get("wind_speed_10m_max") or []) else None

        if t_max is not None: temps_max.append(t_max)
        if t_min is not None: temps_min.append(t_min)
        if p is not None: precip_vals.append(p)
        if w is not None: wind_vals.append(w)

    if not temps_max:
        return None

    rain_days_pct = round(100 * sum(1 for p in precip_vals if p > 0.01) / len(precip_vals)) if precip_vals else None

    return {
        "avg_high_f": round(sum(temps_max) / len(temps_max)),
        "avg_low_f": round(sum(temps_min) / len(temps_min)),
        "precip_chance_pct": rain_days_pct,
        "max_wind_mph": round(max(wind_vals)) if wind_vals else None,
    }


def format_weather_prefix(weather: dict) -> str:
    """Format weather data as a natural prefix sentence."""
    high = weather["avg_high_f"]
    low = weather["avg_low_f"]
    precip = weather.get("precip_chance_pct")
    wind = weather.get("max_wind_mph")

    parts = [f"Historical weather data shows average highs of {high}°F and lows of {low}°F"]

    if precip is not None:
        parts.append(f"with a {precip}% chance of rain on any given day")

    if wind and wind > 25:
        parts.append(f"and gusts reaching {wind} mph")

    return ", ".join(parts) + "."


def has_temp_data(explanation: str) -> bool:
    """Check if explanation already has temperature data."""
    return bool(re.search(r'\d+°[FC]', explanation))


def main():
    dry_run = "--dry-run" in sys.argv
    fetch_only = "--fetch-only" in sys.argv

    WEATHER_DIR.mkdir(parents=True, exist_ok=True)

    races = sorted(RACE_DATA.glob("*.json"))
    total_fetched = 0
    total_injected = 0
    errors = 0

    for i, f in enumerate(races):
        d = json.loads(f.read_text())
        race = d.get("race", d)
        vitals = race.get("vitals", {})

        lat = vitals.get("lat")
        lng = vitals.get("lng")
        date_str = vitals.get("date", "")

        if not lat or not lng or not date_str:
            continue

        month = parse_month(date_str)
        if not month:
            continue

        # Check if we already fetched this
        weather_file = WEATHER_DIR / f"{f.stem}.json"
        if weather_file.exists():
            weather = json.loads(weather_file.read_text())
        else:
            # Rate limit: Open-Meteo allows ~600 req/min
            if total_fetched > 0 and total_fetched % 50 == 0:
                print(f"  [{total_fetched}/{len(races)}] Pausing 5s for rate limit...")
                time.sleep(5)

            weather = fetch_weather(float(lat), float(lng), month)
            if weather:
                weather["month"] = month
                weather["lat"] = float(lat)
                weather["lng"] = float(lng)
                weather_file.write_text(json.dumps(weather, indent=2) + "\n")
                total_fetched += 1
            else:
                errors += 1
                continue

        if fetch_only:
            continue

        # Inject into climate explanation
        bor = race.get("biased_opinion_ratings", {})
        climate_entry = bor.get("climate", {})
        if not isinstance(climate_entry, dict):
            continue
        explanation = climate_entry.get("explanation", "")
        if not explanation:
            continue

        # Skip if already has temperature data
        if has_temp_data(explanation):
            continue

        prefix = format_weather_prefix(weather)
        new_explanation = f"{prefix} {explanation}"

        # Don't exceed 700 chars
        if len(new_explanation) > 700:
            continue

        if dry_run:
            print(f"  {f.stem}:")
            print(f"    WEATHER: {prefix}")
            print(f"    OLD: {explanation[:100]}")
            print()
        else:
            climate_entry["explanation"] = new_explanation
            f.write_text(json.dumps(d, indent=2, ensure_ascii=False) + "\n")

        total_injected += 1

        if i % 50 == 0:
            print(f"  [{i}/{len(races)}] processed...")

    print(f"\nFetched weather for {total_fetched} new races ({errors} errors)")
    if not fetch_only:
        print(f"{'[DRY RUN] ' if dry_run else ''}Injected weather into {total_injected} climate explanations")


if __name__ == "__main__":
    main()
