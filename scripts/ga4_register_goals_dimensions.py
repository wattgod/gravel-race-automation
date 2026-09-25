#!/usr/bin/env python3
"""Dry-run: what registering the 2027-goals-funnel GA4 custom dimensions
would send to the Admin API.

See docs/ga4-key-events.md for why this defaults to a dry run and does not
mark anything a key event: the repo's existing GA4 governance
(docs/GA4_CONVERSION_AUTHORITY.md) requires a durable proven business outcome
before an event is promoted, and these events are brand new.

This script NEVER calls the network by default. It only builds and prints
the exact Admin API requests it would make (method, URL, JSON body) so a
human can read them before anything is registered. Real registration
(--execute) additionally requires a service account with the
`analytics.edit` OAuth scope granted Editor on the property — the same
authorization ga4_conversion_audit.py already uses for --mode
demote_cta_click. Nobody has run --execute as part of this change.

Usage:
    python scripts/ga4_register_goals_dimensions.py --property 123456789
    python scripts/ga4_register_goals_dimensions.py --property 123456789 --execute --credentials ga4-credentials.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ADMIN_ROOT = "https://analyticsadmin.googleapis.com/v1beta"
EDIT_SCOPE = "https://www.googleapis.com/auth/analytics.edit"
PROPERTY_RE = re.compile(r"^properties/(\d+)$")

# One row per custom dimension docs/ga4-key-events.md says the 2027 goals
# funnel needs. Kept here (not only in the doc) so the doc and the request
# this script would send cannot silently drift apart.
GOALS_FUNNEL_DIMENSIONS = [
    {
        "parameterName": "src",
        "displayName": "Goals entry surface",
        "description": "Which surface sent the visitor to /goals/ — 'home' "
                        "(poster wall) or 'race' (race-page goal strip). "
                        "Fires on goal_hero_click and every goal_* event.",
        "scope": "EVENT",
    },
    {
        "parameterName": "offer_variant",
        "displayName": "Offer variant",
        "description": "Which of the 3 /goals/ offer copy variants (A/B/C) — "
                        "goal_offer_view, goal_offer_click, and the tp_form_*/"
                        "begin_checkout events on a /goals/ referral.",
        "scope": "EVENT",
    },
    {
        "parameterName": "plan_type",
        "displayName": "Plan type",
        "description": "Race Plan vs Season Plan on goal_offer_click. Only "
                        "'race' exists until the Season Plan product ships.",
        "scope": "EVENT",
    },
    {
        "parameterName": "race_slug",
        "displayName": "Entry race slug",
        "description": "Which race page (if any) sent the visitor to /goals/ "
                        "(?race= param), on every goal_* event.",
        "scope": "EVENT",
    },
    {
        "parameterName": "entry_surface",
        "displayName": "Questionnaire entry surface",
        # GA4 caps descriptions at 150 characters (Admin API 400 otherwise).
        "description": "Which surface sent the visitor to the plan form (?src= param).",
        "scope": "EVENT",
    },
    {
        "parameterName": "number",
        "displayName": "Goal section number",
        "description": "Numbered question section (1-6) reached on /goals/, "
                        "from goal_section.",
        "scope": "EVENT",
    },
    {
        "parameterName": "variant",
        "displayName": "Season review variant",
        "description": "Which question-set variant rendered (goal_2027 on "
                        "the public page). Likely already registered from "
                        "the original season-review build; verify first.",
        "scope": "EVENT",
    },
    {
        "parameterName": "goal_type",
        "displayName": "Race page goal type",
        "description": "Goal tapped on the race-page goal card: finish, beat_time, race_it, same, or bigger.",
        "scope": "EVENT",
    },
]


def normalize_property(value: str) -> str:
    candidate = str(value or "").strip()
    if candidate.isdigit():
        candidate = f"properties/{candidate}"
    if not PROPERTY_RE.fullmatch(candidate):
        raise SystemExit("--property must be a numeric GA4 property ID or properties/ID")
    return candidate


def build_requests(property_name: str) -> list[dict]:
    """The exact Admin API calls registration would make, one per dimension."""
    return [
        {
            "method": "POST",
            "url": f"{ADMIN_ROOT}/{property_name}/customDimensions",
            "body": {
                "parameterName": dim["parameterName"],
                "displayName": dim["displayName"],
                "description": dim["description"],
                "scope": dim["scope"],
            },
        }
        for dim in GOALS_FUNNEL_DIMENSIONS
    ]


def execute(property_name: str, credentials_path: Path, requests: list[dict]) -> None:
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials

    credentials = Credentials.from_service_account_file(
        str(credentials_path), scopes=[EDIT_SCOPE])
    session = AuthorizedSession(credentials)
    for req in requests:
        response = session.post(req["url"], json=req["body"], timeout=30)
        status = response.status_code
        print(f"{req['body']['parameterName']}: HTTP {status}")
        if status >= 300:
            print(f"  {response.text[:500]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--property", required=True,
                        help="Numeric GA4 property ID, e.g. 123456789")
    parser.add_argument("--execute", action="store_true",
                        help="Actually call the Admin API. Default is dry-run "
                             "(print only, no network call). Not used to "
                             "produce this change's output.")
    parser.add_argument("--credentials", type=Path,
                        default=Path("ga4-credentials.json"),
                        help="Service account JSON with analytics.edit scope "
                             "granted Editor on the property (--execute only)")
    args = parser.parse_args()

    property_name = normalize_property(args.property)
    requests = build_requests(property_name)

    print(json.dumps({
        "mode": "execute" if args.execute else "dry_run",
        "property": property_name,
        "planned_requests": requests,
    }, indent=2))

    if not args.execute:
        print(
            "\nDry run only — nothing was sent. Pass --execute with a "
            "service account that has analytics.edit + Editor on the "
            "property to actually register these.",
            file=sys.stderr,
        )
        return 0

    execute(property_name, args.credentials, requests)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
