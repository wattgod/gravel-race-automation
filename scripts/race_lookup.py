#!/usr/bin/env python3
"""
Race database lookup module for Athlete OS coaching pipeline integration.

Provides a clean API to query the gravel race database from the coaching pipeline.

Usage:
    from scripts.race_lookup import RaceLookup

    db = RaceLookup()
    race = db.lookup("unbound-200")
    print(race.tier, race.score, race.distance_mi)

    # Fuzzy matching
    race = db.lookup("unbound_gravel_200")  # → unbound-200

    # Recommendations
    matches = db.recommend(distance_range=(80, 150), tier=[1, 2], region="Midwest")

    # Training context for coaching pipeline
    ctx = race.training_context()
"""

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RACE_DATA_DIR = PROJECT_ROOT / "race-data"
DEFAULT_FLAT_DB = PROJECT_ROOT / "db" / "gravel_races_full_database.json"

# Common slug aliases for fuzzy matching
SLUG_ALIASES = {
    "unbound_gravel_200": "unbound-200",
    "unbound_gravel": "unbound-200",
    "unbound": "unbound-200",
    "sbt_grvl": "steamboat-gravel",
    "sbt-grvl": "steamboat-gravel",
    "belgian_waffle_ride": "bwr-california",
    "bwr": "bwr-california",
    "dirty_kanza": "unbound-200",
    "dirty-kanza": "unbound-200",
    "leadville_100_mtb": "leadville-100",
    "leadville": "leadville-100",
    "mid_south": "mid-south",
}


@dataclass
class Race:
    """Represents a single race with key attributes."""
    slug: str
    name: str
    tier: int = 4
    score: int = 0
    distance_mi: float = 0
    elevation_ft: float = 0
    discipline: str = "gravel"
    terrain: str = ""
    date: str = ""
    location: str = ""
    prestige: int = 0
    profile_url: str = ""
    region: str = ""
    month: str = ""
    non_negotiables: list = field(default_factory=list)
    _raw: dict = field(default_factory=dict, repr=False)

    def training_context(self) -> dict:
        """Extract training-relevant context for coaching pipeline."""
        vitals = self._raw.get("vitals", {})
        course = self._raw.get("course_description", {})
        gravel_god = self._raw.get("gravel_god_rating", {})
        scores = gravel_god.get("dimension_scores", gravel_god)

        # Determine strength emphasis from scores
        tech_score = scores.get("technicality", 0)
        elev_score = scores.get("elevation", 0)
        length_score = scores.get("length", 0)
        adventure_score = scores.get("adventure", 0)

        emphasis = []
        if elev_score >= 4:
            emphasis.append("climbing")
        if tech_score >= 4:
            emphasis.append("technical skills")
        if length_score >= 4:
            emphasis.append("endurance")
        if adventure_score >= 4:
            emphasis.append("self-sufficiency")
        if not emphasis:
            emphasis.append("general fitness")

        # Fueling targets based on distance
        if self.distance_mi >= 150:
            fuel_target = "300-400 cal/hr, 80-100g carbs/hr"
        elif self.distance_mi >= 100:
            fuel_target = "250-350 cal/hr, 60-90g carbs/hr"
        elif self.distance_mi >= 50:
            fuel_target = "200-300 cal/hr, 50-80g carbs/hr"
        else:
            fuel_target = "150-250 cal/hr, 40-60g carbs/hr"

        return {
            "race_slug": self.slug,
            "race_name": self.name,
            "tier": self.tier,
            "score": self.score,
            "distance_mi": self.distance_mi,
            "elevation_ft": self.elevation_ft,
            "discipline": self.discipline,
            "terrain_notes": self.terrain or course.get("character", ""),
            "strength_emphasis": emphasis,
            "fueling_target": fuel_target,
            "non_negotiables": self.non_negotiables,
            "date": self.date,
            "location": self.location,
            "profile_url": self.profile_url,
        }


class RaceLookup:
    """Race database connector for the coaching pipeline."""

    def __init__(self, data_path=None):
        """Initialize with race data.

        Args:
            data_path: Path to race-data/ directory or flat DB JSON.
                        Falls back to env var RACE_DATA_PATH, then default locations.
        """
        self._races = {}  # slug → Race
        self._load(data_path)

    def _load(self, data_path):
        """Load race data from JSON files."""
        if data_path is None:
            data_path = os.environ.get("RACE_DATA_PATH", "")

        path = Path(data_path) if data_path else None

        # Try race-data/ directory first (preferred — individual JSON files)
        if path and path.is_dir():
            self._load_from_dir(path)
        elif DEFAULT_RACE_DATA_DIR.exists():
            self._load_from_dir(DEFAULT_RACE_DATA_DIR)
        elif path and path.is_file():
            self._load_from_flat_db(path)
        elif DEFAULT_FLAT_DB.exists():
            self._load_from_flat_db(DEFAULT_FLAT_DB)
        else:
            raise FileNotFoundError(
                "No race data found. Set RACE_DATA_PATH or ensure "
                f"{DEFAULT_RACE_DATA_DIR} exists."
            )

    def _load_from_dir(self, dir_path):
        """Load from individual race JSON files."""
        for f in sorted(dir_path.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                rd = data.get("race", data)
                self._races[f.stem] = self._parse_race(f.stem, rd)
            except (json.JSONDecodeError, KeyError):
                continue

    def _load_from_flat_db(self, db_path):
        """Load from flat database JSON."""
        data = json.loads(db_path.read_text())
        if isinstance(data, list):
            for entry in data:
                rd = entry.get("race", entry)
                slug = rd.get("slug", "")
                if slug:
                    self._races[slug] = self._parse_race(slug, rd)
        elif isinstance(data, dict):
            for slug, rd in data.items():
                if isinstance(rd, dict):
                    self._races[slug] = self._parse_race(slug, rd)

    def _parse_race(self, slug, rd):
        """Parse a race dict into a Race dataclass."""
        vitals = rd.get("vitals", {})
        gravel_god = rd.get("gravel_god_rating", {})
        course = rd.get("course_description", {})

        terrain_parts = []
        terrain_data = rd.get("terrain", {})
        if isinstance(terrain_data, dict):
            if terrain_data.get("primary") and isinstance(terrain_data["primary"], str):
                terrain_parts.append(terrain_data["primary"])
            if terrain_data.get("surface") and isinstance(terrain_data["surface"], str):
                terrain_parts.append(terrain_data["surface"])
        terrain = ", ".join(terrain_parts)
        if not terrain:
            terrain = course.get("character", "")

        return Race(
            slug=slug,
            name=rd.get("name", slug),
            tier=gravel_god.get("tier") or gravel_god.get("display_tier") or 4,
            score=gravel_god.get("overall_score", 0),
            distance_mi=vitals.get("distance_mi", 0) or 0,
            elevation_ft=vitals.get("elevation_ft", 0) or 0,
            discipline=gravel_god.get("discipline", "gravel"),
            terrain=terrain,
            date=vitals.get("date_specific", "") or vitals.get("date", ""),
            location=vitals.get("location", "") or vitals.get("location_badge", ""),
            prestige=gravel_god.get("dimension_scores", gravel_god).get("prestige", 0),
            profile_url=f"https://gravelgodcycling.com/race/{slug}/",
            region=vitals.get("region", ""),
            month=vitals.get("month", ""),
            non_negotiables=rd.get("non_negotiables", []),
            _raw=rd,
        )

    def _normalize_slug(self, query):
        """Normalize a slug query for matching."""
        # Lowercase, replace underscores with hyphens
        normalized = query.lower().strip().replace("_", "-").replace(" ", "-")
        # Remove common suffixes
        normalized = re.sub(r"-gravel$", "", normalized)
        return normalized

    def lookup(self, query):
        """Look up a race by slug or alias.

        Args:
            query: Race slug, alias, or approximate name.

        Returns:
            Race object or None if not found.
        """
        # Exact match
        if query in self._races:
            return self._races[query]

        # Normalize
        normalized = self._normalize_slug(query)
        if normalized in self._races:
            return self._races[normalized]

        # Check aliases
        alias_key = query.lower().strip().replace("-", "_").replace(" ", "_")
        if alias_key in SLUG_ALIASES:
            target = SLUG_ALIASES[alias_key]
            if target in self._races:
                return self._races[target]

        # Fuzzy: try substring match
        for slug, race in self._races.items():
            if normalized in slug or slug in normalized:
                return race

        # Fuzzy: try name match
        query_lower = query.lower().replace("_", " ").replace("-", " ")
        for slug, race in self._races.items():
            if query_lower in race.name.lower():
                return race

        return None

    def recommend(self, distance_range=None, tier=None, region=None,
                  discipline=None, month=None, limit=20):
        """Find races matching criteria, sorted by score.

        Args:
            distance_range: Tuple of (min_mi, max_mi).
            tier: List of tier numbers, e.g. [1, 2].
            region: Region name string.
            discipline: "gravel" or "mtb".
            month: Month name string.
            limit: Max results to return.

        Returns:
            List of Race objects sorted by score descending.
        """
        matches = []
        for race in self._races.values():
            if distance_range:
                if race.distance_mi < distance_range[0] or race.distance_mi > distance_range[1]:
                    continue
            if tier and race.tier not in tier:
                continue
            if region and race.region != region:
                continue
            if discipline and race.discipline != discipline:
                continue
            if month and race.month != month:
                continue
            matches.append(race)

        matches.sort(key=lambda r: r.score, reverse=True)
        return matches[:limit]

    def all_races(self):
        """Return all races as a list."""
        return list(self._races.values())

    def __len__(self):
        return len(self._races)
