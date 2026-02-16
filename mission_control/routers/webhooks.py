"""Webhooks — receives intake from Cloudflare Worker."""

from fastapi import APIRouter, Header, HTTPException, Request

from mission_control.config import WEBHOOK_SECRET
from mission_control import supabase_client as db

router = APIRouter(prefix="/webhooks")


@router.post("/intake")
async def intake_webhook(
    request: Request,
    authorization: str = Header(""),
):
    # Verify webhook secret
    if WEBHOOK_SECRET:
        expected = f"Bearer {WEBHOOK_SECRET}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    request_id = body.get("request_id", "")

    if not request_id:
        raise HTTPException(status_code=400, detail="request_id required")

    # Look up the plan request
    plan_request = db.get_plan_request(request_id)
    if not plan_request:
        raise HTTPException(status_code=404, detail=f"Plan request {request_id} not found")

    payload = plan_request.get("payload", {})

    # Extract athlete info from payload
    name = payload.get("name", "Unknown")
    email = payload.get("email", "")

    # Generate slug
    slug_base = name.lower().replace(" ", "-")
    import re
    from datetime import date
    slug_base = re.sub(r"[^a-z0-9-]", "", slug_base)
    slug = f"{slug_base}-{date.today().strftime('%Y%m%d')}"

    # Check if athlete already exists
    existing = db.get_athlete(slug)
    if existing:
        return {"status": "already_exists", "slug": slug}

    # Create athlete record
    races = payload.get("races", [])
    race_name = races[0].get("name") if races else None
    race_date = races[0].get("date") if races else None

    db.upsert_athlete({
        "slug": slug,
        "plan_request_id": request_id,
        "name": name,
        "email": email,
        "race_name": race_name,
        "race_date": race_date,
        "ftp": payload.get("ftp"),
        "weekly_hours": str(payload.get("weekly_hours", "")),
        "plan_status": "intake_received",
        "intake_json": payload,
    })

    db.log_action("intake_received", "athlete", slug,
                  f"New intake from webhook: {name} ({email})")

    return {"status": "created", "slug": slug}
