"""Races API — read-only REST endpoints for the 328-race gravel database.

Provides queryable, filterable access to race data for AI agents,
coaching tools, and travel planners. Auto-generated OpenAPI docs
at /api/v1/docs enable agent discovery.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from mission_control.services.race_data import RaceDB, get_race_db

router = APIRouter()

# ---------------------------------------------------------------------------
# Rate limiting (sliding window, same pattern as webhooks.py)
# ---------------------------------------------------------------------------

_rate_buckets: dict[str, list[float]] = defaultdict(list)
_LIST_RATE_LIMIT = 60     # list/filter endpoints
_DETAIL_RATE_LIMIT = 120  # single-race lookups
_RATE_WINDOW = 60         # seconds


def _check_rate_limit(request: Request, limit: int = _LIST_RATE_LIMIT) -> None:
    """Raise 429 if IP exceeds rate limit."""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = _rate_buckets[ip]
    cutoff = now - _RATE_WINDOW
    _rate_buckets[ip] = bucket = [t for t in bucket if t > cutoff]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


# ---------------------------------------------------------------------------
# GET /api/v1/races — list / filter / search
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/races",
    summary="List and filter gravel races",
    description=(
        "Returns paginated, filterable results from the 328-race database. "
        "Supports filtering by tier, region, discipline, month, distance range, "
        "and free-text search across name, location, and tagline."
    ),
    tags=["Races"],
)
async def list_races(
    request: Request,
    tier: Optional[list[int]] = Query(None, description="Filter by tier (1-4), repeatable"),
    region: Optional[str] = Query(None, description="Filter by region name"),
    discipline: Optional[str] = Query(None, description="'gravel', 'mtb', or 'bikepacking'"),
    month: Optional[str] = Query(None, description="Filter by month name (e.g. 'June')"),
    distance_min: Optional[float] = Query(None, description="Min distance in miles"),
    distance_max: Optional[float] = Query(None, description="Max distance in miles"),
    q: Optional[str] = Query(None, description="Text search across name, location, tagline"),
    sort: str = Query("score", description="Sort by: 'score' (default), 'name', 'distance'"),
    limit: int = Query(20, ge=1, le=100, description="Results per page (max 100)"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    _check_rate_limit(request, _LIST_RATE_LIMIT)
    db = get_race_db()
    results = list(db.index)

    # Filters
    if tier:
        results = [r for r in results if r.get("tier") in tier]
    if region:
        results = [r for r in results if r.get("region", "").lower() == region.lower()]
    if discipline:
        results = [r for r in results if r.get("discipline", "gravel").lower() == discipline.lower()]
    if month:
        results = [r for r in results if r.get("month", "").lower() == month.lower()]
    if distance_min is not None:
        results = [r for r in results if (r.get("distance_mi") or 0) >= distance_min]
    if distance_max is not None:
        results = [r for r in results if (r.get("distance_mi") or 0) <= distance_max]
    if q:
        q_lower = q.lower()
        results = [
            r for r in results
            if q_lower in r.get("name", "").lower()
            or q_lower in r.get("location", "").lower()
            or q_lower in r.get("tagline", "").lower()
        ]

    # Sort
    if sort == "name":
        results.sort(key=lambda r: r.get("name", "").lower())
    elif sort == "distance":
        results.sort(key=lambda r: r.get("distance_mi") or 0, reverse=True)
    else:  # default: score descending
        results.sort(key=lambda r: r.get("overall_score") or 0, reverse=True)

    total = len(results)
    page = results[offset:offset + limit]

    # Build next link
    next_url = None
    if offset + limit < total:
        next_url = f"/api/v1/races?offset={offset + limit}&limit={limit}"

    return {
        "count": total,
        "limit": limit,
        "offset": offset,
        "next": next_url,
        "results": page,
    }


# ---------------------------------------------------------------------------
# GET /api/v1/races/recommend — recommendation engine
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/races/recommend",
    summary="Get race recommendations",
    description=(
        "Returns races matching your criteria, sorted by Gravel God score. "
        "Useful for coaching agents and travel planners."
    ),
    tags=["Races"],
)
async def recommend_races(
    request: Request,
    tier: Optional[list[int]] = Query(None, description="Filter by tier (1-4), repeatable"),
    region: Optional[str] = Query(None, description="Filter by region name"),
    discipline: Optional[str] = Query(None, description="'gravel', 'mtb', or 'bikepacking'"),
    month: Optional[str] = Query(None, description="Filter by month name"),
    distance_min: Optional[float] = Query(None, description="Min distance in miles"),
    distance_max: Optional[float] = Query(None, description="Max distance in miles"),
    limit: int = Query(10, ge=1, le=50, description="Max results (default 10)"),
):
    _check_rate_limit(request, _LIST_RATE_LIMIT)
    db = get_race_db()
    results = list(db.index)

    if tier:
        results = [r for r in results if r.get("tier") in tier]
    if region:
        results = [r for r in results if r.get("region", "").lower() == region.lower()]
    if discipline:
        results = [r for r in results if r.get("discipline", "gravel").lower() == discipline.lower()]
    if month:
        results = [r for r in results if r.get("month", "").lower() == month.lower()]
    if distance_min is not None:
        results = [r for r in results if (r.get("distance_mi") or 0) >= distance_min]
    if distance_max is not None:
        results = [r for r in results if (r.get("distance_mi") or 0) <= distance_max]

    # Always sort by score descending for recommendations
    results.sort(key=lambda r: r.get("overall_score") or 0, reverse=True)

    return {
        "count": len(results[:limit]),
        "results": results[:limit],
    }


# ---------------------------------------------------------------------------
# GET /api/v1/races/{slug} — full race profile
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/races/{slug}",
    summary="Get full race profile",
    description=(
        "Returns the complete race profile (50+ fields) including vitals, "
        "course description, 15-dimension Gravel God rating, terrain, "
        "non-negotiables, final verdict, citations, and training context. "
        "Supports fuzzy matching via aliases (e.g. 'dirty-kanza' → 'unbound-200')."
    ),
    tags=["Races"],
)
async def get_race(request: Request, slug: str):
    _check_rate_limit(request, _DETAIL_RATE_LIMIT)
    db = get_race_db()

    # Check for alias/fuzzy redirect
    canonical = db.resolve_slug(slug)
    if canonical is None:
        raise HTTPException(status_code=404, detail=f"Race '{slug}' not found")

    profile = db.get_profile(canonical)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Race '{slug}' not found")

    # If the slug was an alias, include the canonical slug in response
    result = dict(profile)
    if canonical != slug:
        result["_resolved_from"] = slug
        result["_canonical_slug"] = canonical

    return result


# ---------------------------------------------------------------------------
# GET /api/v1/races/{slug}/training — training context
# ---------------------------------------------------------------------------

@router.get(
    "/api/v1/races/{slug}/training",
    summary="Get training context for a race",
    description=(
        "Returns training-relevant data: distance, elevation, strength emphasis, "
        "fueling targets, and non-negotiables. Designed for coaching agents "
        "that need structured training parameters without parsing the full profile."
    ),
    tags=["Races"],
)
async def get_training_context(request: Request, slug: str):
    _check_rate_limit(request, _DETAIL_RATE_LIMIT)
    db = get_race_db()

    ctx = db.training_context(slug)
    if ctx is None:
        raise HTTPException(status_code=404, detail=f"Race '{slug}' not found")

    return ctx


# ---------------------------------------------------------------------------
# GET /.well-known/ai-plugin.json — agent discovery manifest
# ---------------------------------------------------------------------------

@router.get(
    "/.well-known/ai-plugin.json",
    summary="AI plugin manifest for agent discovery",
    description="OpenAI-standard plugin manifest pointing to the OpenAPI spec.",
    tags=["Discovery"],
    include_in_schema=False,
)
async def ai_plugin_manifest(request: Request):
    # Build base URL from request (force https — Railway proxies as http internally)
    base = str(request.base_url).rstrip("/").replace("http://", "https://", 1)
    return JSONResponse({
        "schema_version": "v1",
        "name_for_human": "Gravel God Race Database",
        "name_for_model": "gravel_god_races",
        "description_for_human": (
            "Search and explore 328 gravel and mountain bike races across North America "
            "and beyond. Get race profiles, ratings, training context, and recommendations."
        ),
        "description_for_model": (
            "Query the Gravel God database of 328 gravel and mountain bike races. "
            "Each race has a tier (1-4), overall score (0-100), 15-dimension rating, "
            "distance, elevation, location, terrain, and training context. "
            "Use /api/v1/races to list and filter, /api/v1/races/{slug} for full profiles, "
            "/api/v1/races/{slug}/training for coaching data, "
            "and /api/v1/races/recommend for recommendations."
        ),
        "auth": {"type": "none"},
        "api": {
            "type": "openapi",
            "url": f"{base}/api/v1/openapi.json",
        },
        "logo_url": f"{base}/static/favicon.ico",
        "contact_email": "matt@gravelgodcycling.com",
        "legal_info_url": "https://gravelgodcycling.com/about/",
    })
