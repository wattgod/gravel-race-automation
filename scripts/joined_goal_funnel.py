#!/usr/bin/env python3
"""Join goal-review leads to Stripe Checkout Sessions by an opaque reference.

The browser sends SHA-256(poster_token) as goal_ref. The token itself is a
private prefill credential and must not be sent to Stripe or analytics. This
report prints aggregate counts only; it never prints contact data or refs.

Live: SUPABASE_URL, SUPABASE_SERVICE_KEY, and one or more Stripe secret keys.
Local: --enrollments and --sessions point to JSON arrays for verification.
XC payment links require a per-lead goal_ref in Checkout Session metadata;
until that manual handoff is used, XC purchases remain unjoined.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

GOAL_REF = re.compile(r"[0-9a-f]{64}\Z")
BRANDS = {"gravelgod", "roadielabs", "xcskilabs"}


def join_funnel(enrollments: list[dict], sessions: list[dict]) -> dict:
    """Return one row per brand/source/variant and a count of unmatched paid sessions."""
    leads: dict[str, dict] = {}
    for enrollment in enrollments:
        if enrollment.get("source") != "goal_2027":
            continue
        data = enrollment.get("source_data") or {}
        brand = data.get("brand") or "gravelgod"
        token = data.get("poster_token")
        if brand not in BRANDS or not isinstance(token, str):
            continue
        ref = hashlib.sha256(token.encode()).hexdigest()
        leads[ref] = {
            "brand": brand,
            "entry_src": data.get("entry_src") or "unknown",
            "offer_variant": data.get("offer_variant") or "unknown",
            "checkout": False,
            "paid": False,
        }

    unmatched_paid = 0
    for session in sessions:
        if str(session.get("id") or "").startswith("cs_test_"):
            continue
        metadata = session.get("metadata") or {}
        ref = metadata.get("goal_ref") or session.get("client_reference_id")
        if not isinstance(ref, str) or not GOAL_REF.fullmatch(ref):
            continue
        paid = session.get("payment_status") == "paid"
        lead = leads.get(ref)
        if not lead or metadata.get("brand") not in (None, "", lead["brand"]):
            if paid:
                unmatched_paid += 1
            continue
        lead["checkout"] = True
        lead["paid"] = lead["paid"] or paid

    buckets: dict[tuple, dict] = defaultdict(lambda: {"reviews": 0, "checkouts": 0, "buyers": 0})
    for lead in leads.values():
        key = lead["brand"], lead["entry_src"], lead["offer_variant"]
        row = buckets[key]
        row["reviews"] += 1
        row["checkouts"] += int(lead["checkout"])
        row["buyers"] += int(lead["paid"])
    rows = [
        {"brand": brand, "entry_src": src, "offer_variant": variant, **counts,
         "buyer_rate": round(counts["buyers"] / counts["reviews"], 4)}
        for (brand, src, variant), counts in sorted(buckets.items())
    ]
    return {"kind": "joined_goal_review_to_purchase", "rows": rows,
            "unmatched_paid_sessions": unmatched_paid,
            "limitations": [
                "Review entry and offer clicks remain GA4 event totals, not joined to this cohort.",
                "XC manual payments join only when their Checkout Session carries goal_ref.",
            ]}


def load_live(days: int) -> tuple[list[dict], list[dict]]:
    import stripe
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mission_control import supabase_client as db

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    leads = []
    offset = 0
    while True:
        batch = (db._table("gg_sequence_enrollments")
                 .select("source,source_data,enrolled_at")
                 .eq("source", "goal_2027")
                 .gte("enrolled_at", cutoff.isoformat())
                 .range(offset, offset + 999).execute().data or [])
        leads.extend(batch)
        if len(batch) < 1000:
            break
        offset += len(batch)

    keys = [os.environ.get(name, "") for name in (
        "STRIPE_SECRET_KEY", "STRIPE_SECRET_KEY_ROADIELABS", "STRIPE_SECRET_KEY_XCSKILABS")]
    sessions: dict[str, dict] = {}
    for key in set(filter(None, keys)):
        for session in stripe.checkout.Session.list(
                api_key=key, created={"gte": int(cutoff.timestamp())}, limit=100).auto_paging_iter():
            item = session.to_dict_recursive()
            sessions[item["id"]] = item
    if not any(keys):
        raise RuntimeError("A Stripe secret key is required for live purchase reconciliation")
    return leads, list(sessions.values())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--enrollments", type=Path)
    parser.add_argument("--sessions", type=Path)
    args = parser.parse_args()
    if bool(args.enrollments) != bool(args.sessions):
        parser.error("provide both --enrollments and --sessions, or neither for live mode")
    if args.days < 1:
        parser.error("--days must be positive")
    if args.enrollments:
        leads = json.loads(args.enrollments.read_text())
        sessions = json.loads(args.sessions.read_text())
    else:
        leads, sessions = load_live(args.days)
    print(json.dumps(join_funnel(leads, sessions), indent=2))


if __name__ == "__main__":
    main()
