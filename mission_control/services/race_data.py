"""Race database service — singleton loader for the races API.

Wraps scripts.race_lookup.RaceLookup in a FastAPI-friendly singleton
that loads race-index.json (for list queries) and individual race-data/*.json
(for full profile lookups) once at import time.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from mission_control.config import REPO_ROOT

logger = logging.getLogger(__name__)

RACE_INDEX_PATH = REPO_ROOT / "web" / "race-index.json"
RACE_DATA_DIR = REPO_ROOT / "race-data"


class RaceDB:
    """Singleton race database loaded from static JSON files."""

    def __init__(self) -> None:
        self._index: list[dict] = []
        self._profiles: dict[str, dict] = {}  # slug → full profile
        self._aliases: dict[str, str] = {
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
        self._loaded = False

    def load(self, index_path: Path | None = None, data_dir: Path | None = None) -> None:
        """Load race data from disk. Safe to call multiple times (no-ops after first)."""
        if self._loaded:
            return

        idx = index_path or RACE_INDEX_PATH
        ddir = data_dir or RACE_DATA_DIR

        # Load index
        if idx.exists():
            self._index = json.loads(idx.read_text())
            logger.info("Loaded %d races from index", len(self._index))
        else:
            logger.warning("Race index not found at %s", idx)

        # Load individual profiles
        if ddir.is_dir():
            for f in sorted(ddir.glob("*.json")):
                try:
                    data = json.loads(f.read_text())
                    self._profiles[f.stem] = data
                except (json.JSONDecodeError, KeyError):
                    continue
            logger.info("Loaded %d race profiles", len(self._profiles))
        else:
            logger.warning("Race data dir not found at %s", ddir)

        self._loaded = True

    @property
    def index(self) -> list[dict]:
        self.load()
        return self._index

    def get_profile(self, slug: str) -> Optional[dict]:
        """Get full race profile by slug, with fuzzy/alias matching."""
        self.load()

        # Exact match
        if slug in self._profiles:
            return self._profiles[slug]

        # Normalize: lowercase, underscores to hyphens
        normalized = slug.lower().strip().replace("_", "-").replace(" ", "-")
        if normalized in self._profiles:
            return self._profiles[normalized]

        # Check aliases
        alias_key = slug.lower().strip().replace("-", "_").replace(" ", "_")
        if alias_key in self._aliases:
            target = self._aliases[alias_key]
            if target in self._profiles:
                return self._profiles[target]

        # Substring match
        for s in self._profiles:
            if normalized in s or s in normalized:
                return self._profiles[s]

        return None

    def resolve_slug(self, slug: str) -> Optional[str]:
        """Resolve a slug (including aliases) to the canonical slug."""
        self.load()

        if slug in self._profiles:
            return slug

        normalized = slug.lower().strip().replace("_", "-").replace(" ", "-")
        if normalized in self._profiles:
            return normalized

        alias_key = slug.lower().strip().replace("-", "_").replace(" ", "_")
        if alias_key in self._aliases:
            target = self._aliases[alias_key]
            if target in self._profiles:
                return target

        for s in self._profiles:
            if normalized in s or s in normalized:
                return s

        return None

    def training_context(self, slug: str) -> Optional[dict]:
        """Get training context for a race (reuses RaceLookup.Race logic)."""
        profile = self.get_profile(slug)
        if not profile:
            return None

        rd = profile.get("race", profile)
        vitals = rd.get("vitals", {})
        gravel_god = rd.get("gravel_god_rating", {})
        course = rd.get("course_description", {})
        scores = gravel_god.get("dimension_scores", gravel_god)

        distance_mi = vitals.get("distance_mi", 0) or 0
        elevation_ft = vitals.get("elevation_ft", 0) or 0

        # Strength emphasis from scores
        emphasis = []
        if scores.get("elevation", 0) >= 4:
            emphasis.append("climbing")
        if scores.get("technicality", 0) >= 4:
            emphasis.append("technical skills")
        if scores.get("length", 0) >= 4:
            emphasis.append("endurance")
        if scores.get("adventure", 0) >= 4:
            emphasis.append("self-sufficiency")
        if not emphasis:
            emphasis.append("general fitness")

        # Fueling targets
        if distance_mi >= 150:
            fuel_target = "300-400 cal/hr, 80-100g carbs/hr"
        elif distance_mi >= 100:
            fuel_target = "250-350 cal/hr, 60-90g carbs/hr"
        elif distance_mi >= 50:
            fuel_target = "200-300 cal/hr, 50-80g carbs/hr"
        else:
            fuel_target = "150-250 cal/hr, 40-60g carbs/hr"

        return {
            "race_slug": rd.get("slug", slug),
            "race_name": rd.get("name", slug),
            "tier": gravel_god.get("tier") or gravel_god.get("display_tier") or 4,
            "score": gravel_god.get("overall_score", 0),
            "distance_mi": distance_mi,
            "elevation_ft": elevation_ft,
            "discipline": gravel_god.get("discipline", "gravel"),
            "terrain_notes": course.get("character", ""),
            "strength_emphasis": emphasis,
            "fueling_target": fuel_target,
            "non_negotiables": rd.get("non_negotiables", []),
            "date": vitals.get("date_specific", "") or vitals.get("date", ""),
            "location": vitals.get("location", "") or vitals.get("location_badge", ""),
            "profile_url": f"https://gravelgodcycling.com/race/{rd.get('slug', slug)}/",
        }


# Module-level singleton
_db: RaceDB | None = None


def get_race_db() -> RaceDB:
    """FastAPI dependency — returns the singleton RaceDB instance."""
    global _db
    if _db is None:
        _db = RaceDB()
        _db.load()
    return _db
