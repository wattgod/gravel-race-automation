"""Nutrition API — duration-scaled fueling calculator for gravel races.

Exposes the deterministic fueling engine from pipeline/nutrition.py as a
public REST endpoint. No AI mediation — pure math from research-backed
duration brackets.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from pipeline.nutrition import compute_fueling, compute_fueling_for_guide

router = APIRouter()

# ---------------------------------------------------------------------------
# Rate limiting (same pattern as races_api.py)
# ---------------------------------------------------------------------------

_rate_buckets: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 60
_RATE_WINDOW = 60
_MAX_TRACKED_IPS = 10_000  # Prevent unbounded memory growth
_last_cleanup = 0.0


def _check_rate_limit(request: Request) -> None:
    """Raise 429 if IP exceeds rate limit."""
    global _last_cleanup
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()

    # Periodic cleanup of stale IPs to prevent memory leak
    if now - _last_cleanup > _RATE_WINDOW * 2:
        _last_cleanup = now
        cutoff = now - _RATE_WINDOW
        stale = [k for k, v in _rate_buckets.items() if not v or v[-1] < cutoff]
        for k in stale:
            del _rate_buckets[k]

    # Hard cap on tracked IPs (defense against IP-spray attacks)
    if ip not in _rate_buckets and len(_rate_buckets) >= _MAX_TRACKED_IPS:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    bucket = _rate_buckets[ip]
    cutoff = now - _RATE_WINDOW
    _rate_buckets[ip] = bucket = [t for t in bucket if t > cutoff]
    if len(bucket) >= _RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class FuelingRequest(BaseModel):
    """Input for the fueling calculator."""
    distance_mi: int = Field(
        ..., gt=0, le=1000,
        description="Race distance in miles (1-1000)",
    )
    duration_hours: float = Field(
        0, ge=0, le=168,
        description="Estimated duration in hours. If 0, estimated from distance. Max 168 (1 week).",
    )
    weight_lbs: Optional[float] = Field(
        None, gt=0, le=500,
        description="Athlete weight in pounds (enables daily carb targets). Max 500.",
    )
    duration_estimate: Optional[str] = Field(
        None,
        description="Duration range string, e.g. '6-10 hours' (alternative to duration_hours)",
    )


class FuelingResponse(BaseModel):
    """Fueling calculator output."""
    distance_mi: int
    hours: float
    carb_rate_lo: int
    carb_rate_hi: int
    carbs_total_lo: int
    carbs_total_hi: int
    gels_lo: int
    gels_hi: int
    label: str
    gut_training_weeks: int
    # Optional weight-derived fields
    weight_kg: Optional[float] = None
    weight_lbs: Optional[float] = None
    daily_carb_lo: Optional[int] = None
    daily_carb_hi: Optional[int] = None
    long_ride_carb_lo: Optional[int] = None
    long_ride_carb_hi: Optional[int] = None


# ---------------------------------------------------------------------------
# POST /api/v1/nutrition/fueling
# ---------------------------------------------------------------------------

@router.post(
    "/api/v1/nutrition/fueling",
    response_model=FuelingResponse,
    summary="Compute duration-scaled fueling targets",
    description=(
        "Returns carbohydrate targets for a gravel race based on distance and "
        "estimated duration. Uses research-backed duration brackets "
        "(Jeukendrup 2014, van Loon 2001, GSSI, Precision Fuel). "
        "Optionally include athlete weight for daily carb loading targets."
    ),
    tags=["Nutrition"],
)
async def compute_fueling_endpoint(request: Request, body: FuelingRequest):
    _check_rate_limit(request)

    # Build inputs for compute_fueling_for_guide (the richer variant)
    race_data = {}
    if body.duration_estimate:
        race_data["duration_estimate"] = body.duration_estimate

    profile = None
    if body.weight_lbs:
        profile = {"demographics": {"weight_lbs": body.weight_lbs}}

    # Use duration_hours directly if provided, otherwise let the engine estimate
    if body.duration_hours > 0:
        result = compute_fueling(body.distance_mi, body.duration_hours)
        # Add weight-derived targets manually if profile is available
        if profile:
            weight_kg = body.weight_lbs / 2.205
            result["weight_kg"] = round(weight_kg, 1)
            result["weight_lbs"] = body.weight_lbs
            result["daily_carb_lo"] = round(weight_kg * 6)
            result["daily_carb_hi"] = round(weight_kg * 7)
            result["long_ride_carb_lo"] = round(weight_kg * 8)
            result["long_ride_carb_hi"] = round(weight_kg * 10)
    else:
        result = compute_fueling_for_guide(
            race_distance=body.distance_mi,
            race_data=race_data,
            profile=profile,
        )

    return result
