#!/usr/bin/env python3
"""Attach an XC goal-review reference to an already paid manual Stripe sale.

Use the goal_ref in the XC plan-intake email and the paid Checkout Session ID.
The script verifies the buyer's email against the saved XC review before it
updates Stripe metadata. It does not create a charge or send a message.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

_REF = re.compile(r"[0-9a-f]{64}\Z")
_SESSION = re.compile(r"cs_(?:live|test)_[A-Za-z0-9]+\Z")
_ENTRY_SRC = re.compile(r"[a-z_]{1,24}\Z")
_VARIANT = re.compile(r"[ABC]\Z")


def matching_review(rows: list[dict], email: str, goal_ref: str) -> dict | None:
    for row in rows:
        if row.get("source") != "goal_2027":
            continue
        if str(row.get("contact_email") or "").casefold() != email.casefold():
            continue
        data = row.get("source_data") or {}
        token = data.get("poster_token")
        if data.get("brand") != "xcskilabs" or not isinstance(token, str):
            continue
        if hashlib.sha256(token.encode()).hexdigest() == goal_ref:
            return row
    return None


def reconcile(session_id: str, goal_ref: str, *, stripe_api, db, api_key: str) -> str:
    if not _SESSION.fullmatch(session_id) or not _REF.fullmatch(goal_ref):
        raise ValueError("Invalid Checkout Session ID or goal reference")
    session = stripe_api.checkout.Session.retrieve(session_id, api_key=api_key)
    if session.payment_status != "paid":
        raise ValueError("Checkout Session is not paid")
    metadata = dict(session.metadata or {})
    if metadata.get("brand") not in (None, "", "xcskilabs"):
        raise ValueError("Checkout Session belongs to another brand")
    if metadata.get("goal_ref") not in (None, "", goal_ref):
        raise ValueError("Checkout Session already belongs to another review")
    details = session.customer_details or {}
    email = (details.get("email") or session.customer_email or "").strip().lower()
    if not email:
        raise ValueError("Checkout Session has no buyer email")
    review = None
    offset = 0
    while True:
        rows = (db._table("gg_sequence_enrollments")
                .select("source,contact_email,source_data")
                .eq("contact_email", email).eq("source", "goal_2027")
                .range(offset, offset + 999).execute().data or [])
        review = matching_review(rows, email, goal_ref)
        if review or len(rows) < 1000:
            break
        offset += 1000
    if not review:
        raise ValueError("No matching XC review for the paid buyer")
    source_data = review.get("source_data") or {}
    metadata_update = {"goal_ref": goal_ref, "brand": "xcskilabs"}
    for field, pattern in (("entry_src", _ENTRY_SRC), ("offer_variant", _VARIANT)):
        value = source_data.get(field)
        if isinstance(value, str) and pattern.fullmatch(value):
            metadata_update[field] = value
    stripe_api.checkout.Session.modify(session_id, api_key=api_key,
                                       metadata=metadata_update)
    return session_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--goal-ref", required=True)
    args = parser.parse_args()
    key = os.getenv("STRIPE_SECRET_KEY_XCSKILABS") or os.getenv("STRIPE_SECRET_KEY")
    if not key:
        parser.error("STRIPE_SECRET_KEY_XCSKILABS or STRIPE_SECRET_KEY is required")
    import stripe
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from mission_control import supabase_client as db
    done = reconcile(args.session_id, args.goal_ref, stripe_api=stripe,
                     db=db, api_key=key)
    print(f"Joined paid XC Checkout Session {done} to the saved review")


if __name__ == "__main__":
    main()
