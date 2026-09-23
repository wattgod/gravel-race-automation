#!/usr/bin/env python3
"""
Funnel report for the 2027 goals questionnaire (docs/specs/goals-2027-funnel-spec.md).

Two independent sources, printed together, never merged into one number:

1. GA4 — how far visitors get through the page (hero click, start, each
   numbered section, submit, results view, poster download, offer view,
   offer click) plus begin_checkout/purchase, with breakdowns by offer
   variant (A/B/C), by entry src (home vs a race page), and by which race
   page. The breakdowns only return real rows once the `offer_variant`/
   `src`/`race_slug` custom dimensions are registered in GA4 admin
   (docs/ga4-key-events.md) — until then GA4's API rejects the dimension and
   this report says so rather than printing zeros that look like data.

2. Mission Control — its own record of the goal_2027 lead: how many people
   enrolled in the goal_2027 sequence, how many got a correction resend
   (services/sequence_engine.py resend_first_step), and open/click counts
   from gg_sequence_sends. This is a different denominator than GA4 (a
   server-side record of who Mission Control actually emailed, not a
   browser event), so its numbers are not expected to match GA4's.

Same independent-events discipline as scripts/funnel_report.py: no shared
session id joins GA4 rows to Mission Control rows, so this is not a single
drop-off table.

Prerequisites:
  - GA4 part: Google Analytics Data API credentials (service account JSON)
      pip install google-analytics-data
  - Mission Control part: Supabase REST access
      SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_SERVICE_KEY)
      (tip: `railway run python3 scripts/goals_funnel_report.py`, same as
      scripts/sequence_report.py)

Usage:
    python scripts/goals_funnel_report.py                  # last 30 days
    python scripts/goals_funnel_report.py --days 7
    python scripts/goals_funnel_report.py --json
    python scripts/goals_funnel_report.py --mock            # sample data, no credentials
    python scripts/goals_funnel_report.py --ga4-only        # skip Mission Control
    python scripts/goals_funnel_report.py --mission-control-only  # skip GA4

Environment:
    GA4_PROPERTY_ID           — GA4 property ID (accepts a bare number or a
                                "properties/123..." string; only digits are kept)
    GA4_CREDENTIALS           — path to service account JSON. If unset, this
                                script looks for ga4-credentials.json at the
                                MAIN checkout's root (found via `git
                                rev-parse --git-common-dir`, so running this
                                from a worktree still finds the real repo's
                                credentials file instead of looking for one
                                inside the worktree, which won't have it) —
                                see _default_ga4_credentials_path(). Falls
                                back to this file's own directory tree if
                                that lookup fails or finds nothing.
    SUPABASE_URL               — Mission Control's Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY  — service role key (or SUPABASE_SERVICE_KEY)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_ga4_credentials_path() -> Path:
    """Where ga4-credentials.json lives when GA4_CREDENTIALS isn't set.

    This script's own PROJECT_ROOT is wherever *this file* sits, which is
    wrong when it's running from a git worktree (e.g. .claude/worktrees/...):
    a worktree checks out the tracked files but not untracked, local-only
    ones like a credentials JSON — only the main checkout has that file.
    `git rev-parse --git-common-dir` finds the .git directory every worktree
    shares; its parent is the main checkout (standard, non-bare layout,
    which is what this repo uses). Falls back to PROJECT_ROOT if git isn't
    available or this isn't a worktree at all, which reproduces the old
    behaviour exactly.
    """
    try:
        import subprocess
        result = subprocess.run(
            ["git", "-C", str(Path(__file__).resolve().parent),
             "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, timeout=5, check=True,
        )
        common_dir = Path(Path(__file__).resolve().parent, result.stdout.strip())
        main_root = common_dir.resolve().parent
        if (main_root / "ga4-credentials.json").exists():
            return main_root / "ga4-credentials.json"
    except Exception:
        pass
    return PROJECT_ROOT / "ga4-credentials.json"


GOALS_SCOPE = "/goals/ page"
PROPERTY_SCOPE = "property-wide (not filtered to /goals/ referrals)"

# Order matches goals-2027-funnel-spec.md "Consent and analytics".
GOALS_FUNNEL = [
    {"stage": "goal_hero_click", "events": ["goal_hero_click"],
     "label": "Hero/CTA click into /goals/", "scope": PROPERTY_SCOPE,
     "note": "Homepage poster wall + race-page goal strip code merged to "
             "main (PR #381) but not deployed as of this audit (live "
             "homepage HTML has no poster wall) — expect 0 until deployed."},
    {"stage": "goal_start", "events": ["goal_start"], "label": "Started the questionnaire",
     "filter_field": "pagePath", "filter_prefix": "/goals/", "scope": GOALS_SCOPE},
    {"stage": "goal_section", "events": ["goal_section"], "label": "Reached a numbered section",
     "filter_field": "pagePath", "filter_prefix": "/goals/", "scope": GOALS_SCOPE},
    {"stage": "goal_submit", "events": ["goal_submit"], "label": "Submitted answers",
     "filter_field": "pagePath", "filter_prefix": "/goals/", "scope": GOALS_SCOPE},
    {"stage": "goal_results_view", "events": ["goal_results_view"], "label": "Saw results/poster",
     "filter_field": "pagePath", "filter_prefix": "/goals/", "scope": GOALS_SCOPE},
    {"stage": "goal_poster_download", "events": ["goal_poster_download"], "label": "Downloaded poster",
     "filter_field": "pagePath", "filter_prefix": "/goals/", "scope": GOALS_SCOPE},
    {"stage": "goal_offer_view", "events": ["goal_offer_view"], "label": "Saw step-two offer",
     "filter_field": "pagePath", "filter_prefix": "/goals/", "scope": GOALS_SCOPE},
    {"stage": "goal_offer_click", "events": ["goal_offer_click"], "label": "Clicked step-two offer",
     "filter_field": "pagePath", "filter_prefix": "/goals/", "scope": GOALS_SCOPE},
    {"stage": "begin_checkout", "events": ["begin_checkout"], "label": "Began checkout (any entry)",
     "filter_field": "pagePath", "filter_prefix": "/questionnaire/", "scope": PROPERTY_SCOPE},
    {"stage": "purchase", "events": ["purchase"], "label": "Purchase events (any entry)",
     "scope": PROPERTY_SCOPE},
]

BREAKDOWN_STAGES = ["goal_offer_view", "goal_offer_click"]
BREAKDOWN_DIMENSIONS = {
    "offer_variant": "customEvent:offer_variant",
    "src": "customEvent:src",          # entry surface: home / race
    "race_slug": "customEvent:race_slug",  # which race page, when src=race
}

MEASUREMENT_METADATA = {
    "kind": "independent_event_totals_plus_breakdowns",
    "joined": False,
    "evidence_gap": (
        "GA4 rows are independent aggregate eventCount values — no shared "
        "user/session id connects a goal_start to the goal_submit from the "
        "same visitor. The Mission Control section is a separate, "
        "server-side record (who actually got emailed) and is not "
        "reconciled to the GA4 rows above it."
    ),
    "breakdown_caveat": (
        "The offer_variant / race_slug breakdowns only return data once "
        "those are registered as GA4 custom dimensions (docs/ga4-key-events.md). "
        "Until then the GA4 Data API rejects the customEvent:<param> "
        "dimension and this report records that as 'not_registered' rather "
        "than printing zeros."
    ),
}


# ── GA4 ──────────────────────────────────────────────────────────────────


def _build_filter(stage_def: dict):
    from google.analytics.data_v1beta.types import Filter, FilterExpression, FilterExpressionList

    event_expressions = [
        FilterExpression(filter=Filter(
            field_name="eventName",
            string_filter=Filter.StringFilter(value=event_name),
        ))
        for event_name in stage_def["events"]
    ]
    event_expression = (event_expressions[0] if len(event_expressions) == 1
                        else FilterExpression(or_group=FilterExpressionList(expressions=event_expressions)))
    if "filter_field" not in stage_def:
        return event_expression
    path_filter = Filter(
        field_name=stage_def["filter_field"],
        string_filter=Filter.StringFilter(
            value=stage_def["filter_prefix"],
            match_type=Filter.StringFilter.MatchType.BEGINS_WITH,
        ),
    )
    return FilterExpression(and_group=FilterExpressionList(
        expressions=[event_expression, FilterExpression(filter=path_filter)]))


def get_goals_funnel(property_id: str, credentials_path: str, days: int) -> list[dict]:
    """Independent event totals for every stage in GOALS_FUNNEL."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    except ImportError:
        print("ERROR: google-analytics-data package not installed.")
        print("  pip install google-analytics-data")
        sys.exit(1)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    client = BetaAnalyticsDataClient()
    start_date = (date.today() - timedelta(days=days)).isoformat()
    end_date = date.today().isoformat()

    stages = []
    for stage_def in GOALS_FUNNEL:
        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimension_filter=_build_filter(stage_def),
        )
        response = client.run_report(request)
        count = sum(int(row.metric_values[0].value) for row in response.rows)
        stages.append({
            "stage": stage_def["stage"], "label": stage_def["label"], "count": count,
            "scope": stage_def["scope"], "event_names": list(stage_def["events"]),
            "note": stage_def.get("note", ""),
        })
    return stages


def get_breakdowns(property_id: str, credentials_path: str, days: int) -> dict:
    """Per-stage counts split by offer_variant and by race_slug (entry src)."""
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
    from google.api_core.exceptions import GoogleAPIError

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    client = BetaAnalyticsDataClient()
    start_date = (date.today() - timedelta(days=days)).isoformat()
    end_date = date.today().isoformat()

    out: dict = {}
    for stage in BREAKDOWN_STAGES:
        stage_def = next(s for s in GOALS_FUNNEL if s["stage"] == stage)
        out[stage] = {}
        for label, dim_name in BREAKDOWN_DIMENSIONS.items():
            try:
                request = RunReportRequest(
                    property=f"properties/{property_id}",
                    dimensions=[Dimension(name=dim_name)],
                    metrics=[Metric(name="eventCount")],
                    date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                    dimension_filter=_build_filter(stage_def),
                )
                response = client.run_report(request)
                rows = {row.dimension_values[0].value or "(not set)": int(row.metric_values[0].value)
                        for row in response.rows}
                out[stage][label] = {"status": "ok", "rows": rows}
            except GoogleAPIError as exc:
                out[stage][label] = {"status": "not_registered", "error": str(exc)[:200]}
    return out


def get_mock_ga4() -> tuple[list[dict], dict]:
    counts = [0, 210, 340, 96, 94, 41, 94, 22, 340, 118]
    stages = []
    for stage_def, c in zip(GOALS_FUNNEL, counts):
        stages.append({
            "stage": stage_def["stage"], "label": stage_def["label"], "count": c,
            "scope": stage_def["scope"], "event_names": list(stage_def["events"]),
            "note": stage_def.get("note", ""),
        })
    breakdowns = {
        "goal_offer_view": {
            "offer_variant": {"status": "ok", "rows": {"A": 31, "B": 30, "C": 33}},
            "src": {"status": "ok", "rows": {"home": 66, "race": 28}},
            "race_slug": {"status": "ok", "rows": {"(not set)": 80, "unbound-200": 14}},
        },
        "goal_offer_click": {
            "offer_variant": {"status": "ok", "rows": {"A": 9, "B": 6, "C": 7}},
            "src": {"status": "ok", "rows": {"home": 15, "race": 7}},
            "race_slug": {"status": "ok", "rows": {"(not set)": 19, "unbound-200": 3}},
        },
    }
    return stages, breakdowns


# ── Mission Control ──────────────────────────────────────────────────────


def _mc_req(path: str, params: str = "") -> list:
    base = os.environ["SUPABASE_URL"]
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_SERVICE_KEY", ""))
    url = f"{base}/rest/v1/{path}?{params}"
    req = urllib.request.Request(
        url, headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


MC_SENDS_BATCH_SIZE = 100  # enrollment_ids per "in.(...)" filter request


def _sends_for_enrollments(enrollment_ids: list[str]) -> list[dict]:
    """gg_sequence_sends rows for exactly these enrollments, fetched with a
    server-side enrollment_id filter rather than pulled unfiltered and
    matched client-side.

    Pulling the whole table client-side undercounts silently: Supabase's
    PostgREST caps a response at 1000 rows by default, and gg_sequence_sends
    already holds 1000+ across every sequence (not just goal_2027) — so a
    recent goal_2027 send can land past that cutoff and never reach the
    Python-side filter at all. Filtering with enrollment_id=in.(...) instead
    asks Postgres for only the rows this report cares about, which both
    fixes that and keeps the request small.
    """
    out: list[dict] = []
    for start in range(0, len(enrollment_ids), MC_SENDS_BATCH_SIZE):
        batch = enrollment_ids[start:start + MC_SENDS_BATCH_SIZE]
        ids = ",".join(urllib.parse.quote(str(i), safe="") for i in batch)
        out.extend(_mc_req(
            "gg_sequence_sends",
            f"select=enrollment_id,step_index,opened_at,clicked_at,status&enrollment_id=in.({ids})",
        ))
    return out


def get_mission_control_numbers(sequence_prefix: str = "goal_2027") -> dict:
    """Mission Control's own record: enrollments, resends, opens, clicks.

    A "resend" is an extra gg_sequence_sends row at step_index=0 for the
    same enrollment (services/sequence_engine.py resend_first_step — sent
    when someone corrects their goal_2027 answers). The first step-0 row per
    enrollment is the original send; anything after it is a resend.
    """
    enrollments = _mc_req(
        "gg_sequence_enrollments",
        "select=id,sequence_id,variant,status,contact_email,source_data"
        f"&sequence_id=like.{urllib.parse.quote(sequence_prefix)}*",
    )
    enrollment_ids = [e["id"] for e in enrollments]
    if not enrollment_ids:
        return {
            "sequence_prefix": sequence_prefix, "enrollments": 0, "unsubscribed": 0,
            "resends": 0, "sends": 0, "opens": 0, "clicks": 0, "by_offer_variant": {},
        }

    sends = _sends_for_enrollments(enrollment_ids)

    step0_per_enrollment: dict[str, int] = {}
    opens = clicks = 0
    for s in sends:
        if s.get("step_index") == 0:
            step0_per_enrollment[s["enrollment_id"]] = step0_per_enrollment.get(s["enrollment_id"], 0) + 1
        if s.get("opened_at"):
            opens += 1
        if s.get("clicked_at"):
            clicks += 1
    resends = sum(max(0, n - 1) for n in step0_per_enrollment.values())

    # The A/B/C offer copy variant a lead saw on /goals/ lives in
    # source_data.offer_variant (mission_control/routers/webhooks.py). The
    # enrollment's own top-level "variant" column is a different thing
    # entirely — sequence_engine.py's internal template-variant slot for
    # this sequence (e.g. which welcome-email copy) — and reading it here
    # silently reported the wrong variant under the right-looking label.
    by_offer_variant: dict[str, int] = {}
    for e in enrollments:
        v = (e.get("source_data") or {}).get("offer_variant") or "(none)"
        by_offer_variant[v] = by_offer_variant.get(v, 0) + 1

    return {
        "sequence_prefix": sequence_prefix,
        "enrollments": len(enrollments),
        "unsubscribed": sum(1 for e in enrollments if e.get("status") == "unsubscribed"),
        "resends": resends,
        "sends": len(sends),
        "opens": opens,
        "clicks": clicks,
        "by_offer_variant": by_offer_variant,
    }


def get_mock_mission_control() -> dict:
    return {
        "sequence_prefix": "goal_2027", "enrollments": 47, "unsubscribed": 2,
        "resends": 3, "sends": 61, "opens": 29, "clicks": 8,
        "by_offer_variant": {"A": 16, "B": 15, "C": 16},
    }


# ── Printing ──────────────────────────────────────────────────────────────


def print_report(stages: list[dict], breakdowns: dict, mc: dict | None, days: int):
    print("=" * 74)
    print(f"2027 GOALS FUNNEL — last {days} days")
    print("=" * 74)
    print("GA4 rows are independent event totals (no session join). Mission")
    print("Control rows are a separate, server-side sequence record.")

    print(f"\n{'─' * 74}\n  GA4 — FUNNEL STEPS\n{'─' * 74}")
    print(f"  {'Step':<26} {'Count':>8}  Scope")
    print(f"  {'─' * 26} {'─' * 8}  {'─' * 34}")
    for s in stages:
        note = f"  ({s['note']})" if s.get("note") else ""
        print(f"  {s['label']:<26} {s['count']:>8,}  {s['scope']}{note}")

    for stage in BREAKDOWN_STAGES:
        print(f"\n{'─' * 74}\n  GA4 — {stage} BY DIMENSION\n{'─' * 74}")
        for dim_label, result in breakdowns.get(stage, {}).items():
            if result.get("status") != "ok":
                print(f"  by {dim_label}: not available — {result.get('error') or 'dimension not registered'}")
                continue
            rows = result["rows"]
            total = sum(rows.values()) or 1
            for k, v in sorted(rows.items(), key=lambda kv: -kv[1]):
                print(f"  by {dim_label:<14} {k:<18} {v:>6,}  ({v / total * 100:4.1f}%)")

    if mc is not None:
        print(f"\n{'─' * 74}\n  MISSION CONTROL — goal_2027 sequence record\n{'─' * 74}")
        print(f"  Enrollments:        {mc['enrollments']:>6,}")
        print(f"  Unsubscribed:       {mc['unsubscribed']:>6,}")
        print(f"  Sends (all steps):  {mc['sends']:>6,}")
        print(f"  Resends (corrections, step 0 only): {mc['resends']:>6,}")
        print(f"  Opens:              {mc['opens']:>6,}")
        print(f"  Clicks:             {mc['clicks']:>6,}")
        if mc["by_offer_variant"]:
            print("  Enrollments by offer_variant (as stored at lead time):")
            for k, v in sorted(mc["by_offer_variant"].items()):
                print(f"    {k:<10} {v:>6,}")

    print(f"\n{'=' * 74}")


def build_payload(days: int, stages: list[dict], breakdowns: dict, mc: dict | None) -> dict:
    return {
        "schema": "goals_funnel_report/v1",
        "days": days,
        "measurement": MEASUREMENT_METADATA,
        "ga4_funnel": stages,
        "ga4_breakdowns": breakdowns,
        "mission_control": mc,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="2027 goals funnel report (GA4 + Mission Control)")
    parser.add_argument("--days", type=int, default=30, help="Lookback days (default: 30)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--mock", action="store_true", help="Use mock data (no credentials needed)")
    parser.add_argument("--ga4-only", action="store_true", help="Skip the Mission Control section")
    parser.add_argument("--mission-control-only", action="store_true", help="Skip the GA4 section")
    args = parser.parse_args()

    stages: list[dict] = []
    breakdowns: dict = {}
    mc: dict | None = None

    if args.mock:
        if not args.mission_control_only:
            stages, breakdowns = get_mock_ga4()
        if not args.ga4_only:
            mc = get_mock_mission_control()
    else:
        if not args.mission_control_only:
            # .env values can carry quotes, a stray \r or a "properties/" prefix;
            # the Data API wants the bare number.
            property_id = "".join(ch for ch in (os.environ.get("GA4_PROPERTY_ID") or "").split("/")[-1] if ch.isdigit())
            credentials_path = os.environ.get("GA4_CREDENTIALS", str(_default_ga4_credentials_path()))
            if not property_id:
                print("ERROR: GA4_PROPERTY_ID environment variable not set.", file=sys.stderr)
                print("  export GA4_PROPERTY_ID=<your-ga4-property-id>", file=sys.stderr)
                return 1
            if not Path(credentials_path).exists():
                print(f"ERROR: Credentials file not found: {credentials_path}", file=sys.stderr)
                return 1
            stages = get_goals_funnel(property_id, credentials_path, args.days)
            breakdowns = get_breakdowns(property_id, credentials_path, args.days)
        if not args.ga4_only:
            if not os.environ.get("SUPABASE_URL"):
                print("Mission Control section skipped: set SUPABASE_URL + "
                      "SUPABASE_SERVICE_ROLE_KEY (tip: `railway run python3 "
                      "scripts/goals_funnel_report.py`)", file=sys.stderr)
            else:
                mc = get_mission_control_numbers()

    if args.json:
        print(json.dumps(build_payload(args.days, stages, breakdowns, mc), indent=2))
    else:
        print_report(stages, breakdowns, mc, args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
