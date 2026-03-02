#!/usr/bin/env python3
"""Gravel God MCP Server — 328-race gravel database for AI agents.

Standalone FastMCP server. Loads race-index.json at startup, lazy-loads
individual profiles from race-data/*.json. No dependency on mission_control.

Tools:
    search_races       — filter + free-text search
    get_race           — full profile with fuzzy slug matching
    compare_races      — side-by-side comparison (2-4 races)
    get_training_context — coaching-ready parameters
    find_similar_races — weighted similarity matching
    get_race_calendar  — races by time window and/or region

Resources:
    race://index       — full 328-entry index JSON
    race://{slug}      — full unabridged race profile

Usage:
    python mcp_server.py              # stdio transport (Claude Desktop)
    mcp dev mcp_server.py             # interactive dev inspector
"""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
RACE_INDEX_PATH = PROJECT_ROOT / "web" / "race-index.json"
RACE_DATA_DIR = PROJECT_ROOT / "race-data"
SITE_URL = "https://gravelgodcycling.com"

VALID_MONTHS = {
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
}

VALID_DISCIPLINES = {"gravel", "mtb", "bikepacking"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _num(val) -> float:
    """Coerce a value to float, returning 0 on failure.

    Handles None, strings like "11,000", and non-numeric garbage.
    """
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _safe_str(val) -> str:
    """Return val as string, or empty string for None. Preserves '0'."""
    if val is None:
        return ""
    return str(val)


def _validate_slug(slug: str) -> bool:
    """Reject slugs with path traversal or dangerous characters."""
    if not slug:
        return False
    if ".." in slug or "/" in slug or "\\" in slug or "\x00" in slug:
        return False
    return True


# ---------------------------------------------------------------------------
# Data layer — singleton loader
# ---------------------------------------------------------------------------

SLUG_ALIASES: dict[str, str] = {
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

# Internal fields to strip from get_race tool responses (denylist).
# The resource endpoint returns the full unabridged profile.
_STRIP_KEYS = frozenset({
    "biased_opinion_ratings",
    "training_config",
    "guide_variables",
    "research_metadata",
    "unsplash_photos",
})


class RaceDB:
    """Race database loaded from static JSON files."""

    def __init__(
        self,
        index_path: Path = RACE_INDEX_PATH,
        data_dir: Path = RACE_DATA_DIR,
    ) -> None:
        self._index_path = index_path
        self._data_dir = data_dir
        self._index: list[dict] = []
        self._slug_set: set[str] = set()
        self._profiles: dict[str, dict] = {}
        self._regions: set[str] = set()
        self._loaded_index = False

    def _ensure_index(self) -> None:
        if self._loaded_index:
            return
        if self._index_path.exists():
            try:
                self._index = json.loads(self._index_path.read_text())
                self._slug_set = {r["slug"] for r in self._index}
                self._regions = {r["region"] for r in self._index if r.get("region")}
                logger.info("Loaded %d races from index", len(self._index))
            except (json.JSONDecodeError, KeyError) as e:
                logger.error("Failed to load race index from %s: %s", self._index_path, e)
                self._index = []
                self._slug_set = set()
        else:
            logger.warning("Race index not found at %s", self._index_path)
        self._loaded_index = True

    def _load_profile(self, slug: str) -> Optional[dict]:
        """Lazy-load a single profile from disk.

        Only accepts canonical slugs already validated against the index.
        """
        if slug in self._profiles:
            return self._profiles[slug]

        # Defense in depth: only load slugs we know exist in the index
        if slug not in self._slug_set:
            return None

        if not _validate_slug(slug):
            logger.warning("Rejected unsafe slug: %r", slug)
            return None

        f = self._data_dir / f"{slug}.json"
        # Verify the resolved path is still inside the data dir
        try:
            f.resolve().relative_to(self._data_dir.resolve())
        except ValueError:
            logger.warning("Path traversal attempt blocked: %r", slug)
            return None

        if f.exists():
            try:
                data = json.loads(f.read_text())
                self._profiles[slug] = data
                return data
            except (json.JSONDecodeError, OSError) as e:
                logger.error("Failed to load profile %s: %s", slug, e)
                return None
        return None

    @property
    def index(self) -> list[dict]:
        self._ensure_index()
        return self._index

    @property
    def regions(self) -> set[str]:
        self._ensure_index()
        return self._regions

    def resolve_slug(self, slug: str) -> Optional[str]:
        """Resolve a user-provided slug to a canonical slug.

        Resolution order: exact -> normalized -> alias -> unique substring.
        Ambiguous substring matches return None (not a random pick).
        """
        self._ensure_index()

        if slug in self._slug_set:
            return slug

        normalized = slug.lower().strip().replace("_", "-").replace(" ", "-")
        if normalized in self._slug_set:
            return normalized

        alias_key = slug.lower().strip().replace("-", "_").replace(" ", "_")
        if alias_key in SLUG_ALIASES:
            target = SLUG_ALIASES[alias_key]
            if target in self._slug_set:
                return target

        # Substring match: only if exactly ONE slug matches (no ambiguity)
        matches = [s for s in self._slug_set if normalized in s or s in normalized]
        if len(matches) == 1:
            return matches[0]

        return None

    def get_profile(self, slug: str) -> Optional[dict]:
        """Get full race profile with fuzzy/alias matching."""
        canonical = self.resolve_slug(slug)
        if canonical is None:
            return None
        return self._load_profile(canonical)

    def get_trimmed_profile(self, slug: str) -> Optional[dict]:
        """Get profile with internal pipeline fields stripped.

        Returns a deep copy -- the cached profile is never mutated.
        """
        profile = self.get_profile(slug)
        if profile is None:
            return None

        result = copy.deepcopy(profile)
        race = result.get("race", result)
        if isinstance(race, dict):
            for key in _STRIP_KEYS:
                race.pop(key, None)
        return result

    def training_context(self, slug: str) -> Optional[dict]:
        """Get coaching-ready training parameters."""
        profile = self.get_profile(slug)
        if not profile:
            return None

        rd = profile.get("race", profile)
        vitals = rd.get("vitals", {})
        gravel_god = rd.get("gravel_god_rating", {})
        course = rd.get("course_description", {})

        distance_mi = _num(vitals.get("distance_mi"))
        elevation_ft = _num(vitals.get("elevation_ft"))

        emphasis = []
        if _num(gravel_god.get("elevation")) >= 4:
            emphasis.append("climbing")
        if _num(gravel_god.get("technicality")) >= 4:
            emphasis.append("technical skills")
        if _num(gravel_god.get("length")) >= 4:
            emphasis.append("endurance")
        if _num(gravel_god.get("adventure")) >= 4:
            emphasis.append("self-sufficiency")
        if not emphasis:
            emphasis.append("general fitness")

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
            "terrain_notes": _safe_str(course.get("character")),
            "strength_emphasis": emphasis,
            "fueling_target": fuel_target,
            "non_negotiables": rd.get("non_negotiables", []),
            "date": _safe_str(vitals.get("date_specific")) or _safe_str(vitals.get("date")),
            "location": _safe_str(vitals.get("location")) or _safe_str(vitals.get("location_badge")),
            "profile_url": f"{SITE_URL}/race/{rd.get('slug', slug)}/",
        }


# Module-level singleton
_db: RaceDB | None = None


def get_db() -> RaceDB:
    global _db
    if _db is None:
        _db = RaceDB()
    return _db


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "Gravel God Race Database",
    instructions=(
        "Query the Gravel God database of 328 gravel, MTB, and bikepacking races. "
        "Each race has a tier (1-4), overall score (0-100), 14-dimension rating, "
        "distance, elevation, location, terrain, and training context. "
        "Use search_races to filter, get_race for full profiles, "
        "compare_races for side-by-side, get_training_context for coaching data, "
        "find_similar_races for recommendations, and get_race_calendar for scheduling."
    ),
)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool
def search_races(
    query: Optional[str] = None,
    tier: Optional[int] = None,
    region: Optional[str] = None,
    month: Optional[str] = None,
    distance_min: Optional[float] = None,
    distance_max: Optional[float] = None,
    discipline: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Search and filter the 328-race gravel database.

    Free-text search matches name, location, tagline, and transcript text.
    All filters are optional and combine with AND logic.
    Returns compact index entries (~200 bytes each) sorted by score descending.

    Args:
        query: Free-text search across name, location, tagline, transcript text
        tier: Filter by tier (1=elite, 2=strong, 3=solid, 4=developing)
        region: Filter by region (e.g. "Pacific Northwest", "Southeast", "Midwest")
        month: Filter by month name (e.g. "June", "October")
        distance_min: Minimum distance in miles
        distance_max: Maximum distance in miles
        discipline: Filter by discipline: "gravel", "mtb", or "bikepacking"
        limit: Max results to return (default 20, max 100)
    """
    db = get_db()

    # Validate inputs and collect warnings
    warnings = []
    if tier is not None and tier not in (1, 2, 3, 4):
        warnings.append(f"Invalid tier {tier}. Valid tiers: 1 (elite), 2 (strong), 3 (solid), 4 (developing).")
    if month and month.lower() not in VALID_MONTHS:
        warnings.append(f"Invalid month '{month}'. Use full month name (e.g. 'June', 'October').")
    if discipline and discipline.lower() not in VALID_DISCIPLINES:
        warnings.append(f"Invalid discipline '{discipline}'. Valid: 'gravel', 'mtb', 'bikepacking'.")
    if region and region.lower() not in {r.lower() for r in db.regions}:
        valid_regions = sorted(db.regions)
        warnings.append(f"Unknown region '{region}'. Known regions: {', '.join(valid_regions)}.")

    results = list(db.index)

    if tier is not None:
        results = [r for r in results if r.get("tier") == tier]
    if region:
        region_lower = region.lower()
        results = [r for r in results if (r.get("region") or "").lower() == region_lower]
    if discipline:
        disc_lower = discipline.lower()
        results = [r for r in results if (r.get("discipline") or "gravel").lower() == disc_lower]
    if month:
        month_lower = month.lower()
        results = [r for r in results if (r.get("month") or "").lower() == month_lower]
    if distance_min is not None:
        results = [r for r in results if _num(r.get("distance_mi")) >= distance_min]
    if distance_max is not None:
        results = [r for r in results if _num(r.get("distance_mi")) <= distance_max]
    if query:
        q = query.lower()
        results = [
            r for r in results
            if q in (r.get("name") or "").lower()
            or q in (r.get("location") or "").lower()
            or q in (r.get("tagline") or "").lower()
            or q in (r.get("st") or "").lower()
        ]

    results.sort(key=lambda r: r.get("overall_score") or 0, reverse=True)
    limit = min(max(limit, 1), 100)
    page = results[:limit]

    response = {"count": len(results), "results": page}
    if warnings:
        response["warnings"] = warnings
    return response


@mcp.tool
def get_race(slug: str) -> dict:
    """Get a full race profile by slug with fuzzy matching and alias support.

    Supports common aliases (e.g. "dirty-kanza" -> "unbound-200",
    "sbt-grvl" -> "steamboat-gravel") and unique substring matching.
    Returns trimmed profile (~5-10KB) with vitals, course, rating,
    terrain, logistics, history, verdict, citations, and more.
    Internal pipeline fields are stripped.

    Args:
        slug: Race slug, alias, or partial name (e.g. "unbound-200", "dirty-kanza")
    """
    if not slug or not slug.strip():
        return {"error": "Slug cannot be empty", "suggestion": "Use search_races to find valid slugs"}

    db = get_db()
    canonical = db.resolve_slug(slug.strip())
    if canonical is None:
        return {"error": f"Race '{slug}' not found", "suggestion": "Use search_races to find valid slugs"}

    profile = db.get_trimmed_profile(canonical)
    if profile is None:
        return {"error": f"Profile for '{canonical}' could not be loaded"}

    if canonical != slug.strip():
        profile["_resolved_from"] = slug.strip()
        profile["_canonical_slug"] = canonical
    return profile


@mcp.tool
def compare_races(slugs: list[str]) -> dict:
    """Side-by-side comparison of 2-4 races on all 14 scoring dimensions plus vitals.

    Returns a structured comparison table with tier, score, distance, elevation,
    location, month, discipline, and all 14 dimension scores for each race.

    Args:
        slugs: List of 2-4 race slugs to compare
    """
    if len(slugs) < 2:
        return {"error": "Provide at least 2 slugs to compare"}
    if len(slugs) > 4:
        return {"error": "Maximum 4 races for comparison"}

    db = get_db()
    dimensions = [
        "logistics", "length", "technicality", "elevation", "climate",
        "altitude", "adventure", "prestige", "race_quality", "experience",
        "community", "field_depth", "value", "expenses",
    ]

    races = []
    for slug in slugs:
        canonical = db.resolve_slug(slug)
        if canonical is None:
            return {"error": f"Race '{slug}' not found"}

        entry = next((r for r in db.index if r["slug"] == canonical), None)
        if entry is None:
            return {"error": f"Race '{slug}' not in index"}

        row = {
            "slug": canonical,
            "name": entry.get("name", ""),
            "tier": entry.get("tier"),
            "overall_score": entry.get("overall_score"),
            "distance_mi": entry.get("distance_mi"),
            "elevation_ft": entry.get("elevation_ft"),
            "location": entry.get("location", ""),
            "month": entry.get("month", ""),
            "discipline": entry.get("discipline", "gravel"),
        }
        scores = entry.get("scores", {})
        for dim in dimensions:
            row[dim] = scores.get(dim)
        races.append(row)

    return {"dimensions": dimensions, "races": races}


@mcp.tool
def get_training_context(slug: str) -> dict:
    """Get coaching-ready training parameters for a race.

    Returns structured data for coaching agents: distance, elevation,
    strength emphasis, fueling targets, non-negotiables, and more.
    Designed so an AI coaching agent can build a training plan without
    parsing the full profile.

    Args:
        slug: Race slug (supports aliases and fuzzy matching)
    """
    if not slug or not slug.strip():
        return {"error": "Slug cannot be empty"}

    db = get_db()
    ctx = db.training_context(slug.strip())
    if ctx is None:
        return {"error": f"Race '{slug}' not found", "suggestion": "Use search_races to find valid slugs"}
    return ctx


@mcp.tool
def find_similar_races(slug: str, limit: int = 5) -> dict:
    """Find races similar to a given race using weighted scoring.

    Similarity is calculated from: same tier (+3), same region (+2),
    same discipline (+2), similar distance within 30% (+2),
    similar elevation within 30% (+1), same month (+1).
    Maximum match score: 11.

    Args:
        slug: Reference race slug
        limit: Number of similar races to return (default 5, max 20)
    """
    if not slug or not slug.strip():
        return {"error": "Slug cannot be empty"}

    db = get_db()
    canonical = db.resolve_slug(slug.strip())
    if canonical is None:
        return {"error": f"Race '{slug}' not found"}

    ref = next((r for r in db.index if r["slug"] == canonical), None)
    if ref is None:
        return {"error": f"Race '{slug}' not in index"}

    ref_dist = _num(ref.get("distance_mi"))
    ref_elev = _num(ref.get("elevation_ft"))
    ref_region = (ref.get("region") or "").lower()
    ref_disc = (ref.get("discipline") or "gravel").lower()
    ref_month = (ref.get("month") or "").lower()

    scored = []
    for r in db.index:
        if r["slug"] == canonical:
            continue
        score = 0
        reasons = []

        if r.get("tier") == ref.get("tier"):
            score += 3
            reasons.append("same tier")

        r_region = (r.get("region") or "").lower()
        if ref_region and r_region and r_region == ref_region:
            score += 2
            reasons.append("same region")

        r_disc = (r.get("discipline") or "gravel").lower()
        if r_disc == ref_disc:
            score += 2
            reasons.append("same discipline")

        r_dist = _num(r.get("distance_mi"))
        if ref_dist > 0 and r_dist > 0 and abs(r_dist - ref_dist) / ref_dist <= 0.3:
            score += 2
            reasons.append("similar distance")

        r_elev = _num(r.get("elevation_ft"))
        if ref_elev > 0 and r_elev > 0 and abs(r_elev - ref_elev) / ref_elev <= 0.3:
            score += 1
            reasons.append("similar elevation")

        r_month = (r.get("month") or "").lower()
        if ref_month and r_month and r_month == ref_month:
            score += 1
            reasons.append("same month")

        if score > 0:
            scored.append({
                "slug": r["slug"],
                "name": r.get("name", ""),
                "tier": r.get("tier"),
                "overall_score": r.get("overall_score"),
                "distance_mi": r.get("distance_mi"),
                "elevation_ft": r.get("elevation_ft"),
                "location": r.get("location", ""),
                "month": r.get("month", ""),
                "match_score": score,
                "match_reasons": reasons,
            })

    scored.sort(key=lambda x: (-x["match_score"], -(x.get("overall_score") or 0)))
    limit = min(max(limit, 1), 20)

    return {
        "reference": {
            "slug": canonical,
            "name": ref.get("name", ""),
            "tier": ref.get("tier"),
            "overall_score": ref.get("overall_score"),
        },
        "similar": scored[:limit],
    }


@mcp.tool
def get_race_calendar(
    month: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 20,
) -> dict:
    """Get races by time window and/or region, sorted by tier then score.

    Useful for planning a race calendar or finding events in a specific
    month and area.

    Args:
        month: Month name (e.g. "June", "October")
        region: Region name (e.g. "Pacific Northwest", "Southeast")
        limit: Max results (default 20, max 100)
    """
    db = get_db()

    warnings = []
    if month and month.lower() not in VALID_MONTHS:
        warnings.append(f"Invalid month '{month}'. Use full month name (e.g. 'June', 'October').")
    if region and region.lower() not in {r.lower() for r in db.regions}:
        valid_regions = sorted(db.regions)
        warnings.append(f"Unknown region '{region}'. Known regions: {', '.join(valid_regions)}.")

    results = list(db.index)

    if month:
        month_lower = month.lower()
        results = [r for r in results if (r.get("month") or "").lower() == month_lower]
    if region:
        region_lower = region.lower()
        results = [r for r in results if (r.get("region") or "").lower() == region_lower]

    results.sort(key=lambda r: (r.get("tier", 99), -(r.get("overall_score") or 0)))
    limit = min(max(limit, 1), 100)

    response = {"count": len(results), "results": results[:limit]}
    if warnings:
        response["warnings"] = warnings
    return response


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("race://index", mime_type="application/json")
def race_index() -> list[dict]:
    """Full 328-entry race index with slug, tier, score, vitals, and scores."""
    return get_db().index


@mcp.resource("race://{slug}", mime_type="application/json")
def race_profile(slug: str) -> dict:
    """Full unabridged race profile by slug (not trimmed -- includes all fields)."""
    db = get_db()
    profile = db.get_profile(slug)
    if profile is None:
        return {"error": f"Race '{slug}' not found"}
    # Return a deep copy so the caller cannot mutate our cache
    return copy.deepcopy(profile)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
