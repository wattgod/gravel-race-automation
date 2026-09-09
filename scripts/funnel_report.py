#!/usr/bin/env python3
"""
GA4 event-total report for journey-related events.

Rows are independently aggregated event counts in a useful reading order. They
do not identify a common user, session, product, race, or event sequence, so the
report deliberately does not calculate drop-off or conversion percentages.

Prerequisites:
  - Google Analytics Data API credentials (service account JSON)
  - pip install google-analytics-data

Usage:
    python scripts/funnel_report.py                   # both funnels, last 30 days
    python scripts/funnel_report.py --days 7           # last 7 days
    python scripts/funnel_report.py --json             # machine-readable output
    python scripts/funnel_report.py --mock             # sample data, no credentials

Environment:
    GA4_PROPERTY_ID     — GA4 property ID (numeric)
    GA4_CREDENTIALS     — path to service account JSON (default: ga4-credentials.json)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Observed event groups ───────────────────────────────────────────────

MEASUREMENT_METADATA = {
    "kind": "independent_event_totals",
    "joined": False,
    "denominator": None,
    "evidence_gap": (
        "The GA4 requests return aggregate eventCount values without a shared "
        "user, session, product, race, order identifier, or event sequence."
    ),
    "limitations": [
        "Each row is counted independently; rows are not a sequential cohort.",
        "Query scope can differ by row and is declared on every row.",
        "Purchase events are behavioral evidence until reconciled to provider transactions.",
    ],
    "joined_measurement_path": {
        "session_cohort": (
            "Use event-level GA4 export or a GA4 funnel report with ordered steps "
            "after the same race/product dimensions are present on every step."
        ),
        "order_cohort": (
            "Carry a common order and offer identifier through checkout and purchase, "
            "then reconcile purchase transaction_id to the provider ledger."
        ),
    },
}

RACE_SCOPE = "race pages (/race/*)"
QUESTIONNAIRE_SCOPE = "questionnaire (/questionnaire/*)"
COACHING_SCOPE = "coaching pages (/coaching/*)"
ARTICLE_SCOPE = "article pages (/articles/*)"
PROPERTY_SCOPE = "property-wide purchase events"

TRAINING_PLAN_FUNNEL = [
    {"stage": "page_view", "events": ["page_view"], "label": "Race page views",
     "filter_field": "pagePath", "filter_prefix": "/race/", "scope": RACE_SCOPE},
    {"stage": "cta_click", "events": ["cta_click"], "label": "Race-page CTA clicks",
     "filter_field": "pagePath", "filter_prefix": "/race/", "scope": RACE_SCOPE},
    {"stage": "tp_form_start", "events": ["form_start", "tp_form_start"],
     "label": "Form starts", "filter_field": "pagePath", "filter_prefix": "/questionnaire/",
     "scope": QUESTIONNAIRE_SCOPE},
    {"stage": "tp_form_submit", "events": ["form_submit", "tp_form_submit"],
     "label": "Form submissions", "filter_field": "pagePath", "filter_prefix": "/questionnaire/",
     "scope": QUESTIONNAIRE_SCOPE},
    {"stage": "begin_checkout", "events": ["begin_checkout"],
     "label": "Checkout starts", "filter_field": "pagePath", "filter_prefix": "/questionnaire/",
     "scope": QUESTIONNAIRE_SCOPE},
    {"stage": "purchase", "events": ["purchase"], "label": "Purchase events",
     "scope": PROPERTY_SCOPE},
]

COACHING_FUNNEL = [
    {"stage": "page_view", "events": ["page_view"], "label": "Coaching page views",
     "filter_field": "pagePath", "filter_prefix": "/coaching/", "scope": COACHING_SCOPE},
    {"stage": "coaching_cta_click", "events": ["cta_click", "coaching_cta_click"],
     "label": "CTA clicks", "filter_field": "pagePath", "filter_prefix": "/coaching/",
     "scope": COACHING_SCOPE},
    {"stage": "coaching_scroll_depth", "events": ["coaching_scroll_depth"],
     "label": "Deep scroll (FAQ/final CTA)", "filter_field": "pagePath",
     "filter_prefix": "/coaching/", "scope": COACHING_SCOPE},
]

ARTICLE_FUNNEL = [
    {"stage": "page_view", "events": ["page_view"], "label": "Article page views",
     "filter_field": "pagePath", "filter_prefix": "/articles/", "scope": ARTICLE_SCOPE},
    {"stage": "article_deep_read", "events": ["article_deep_read"],
     "label": "Deep reads (75%+ scroll)", "filter_field": "pagePath",
     "filter_prefix": "/articles/", "scope": ARTICLE_SCOPE},
    {"stage": "article_cta_click", "events": ["article_cta_click"],
     "label": "CTA clicks (coaching/plans/substack)", "filter_field": "pagePath",
     "filter_prefix": "/articles/", "scope": ARTICLE_SCOPE},
]


def get_funnel_data(property_id: str, credentials_path: str, days: int,
                    funnel: list[dict]) -> list[dict]:
    """Query GA4 Data API for independent event totals in display order."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            Filter,
            FilterExpression,
            FilterExpressionList,
            Metric,
            RunReportRequest,
        )
    except ImportError:
        print("ERROR: google-analytics-data package not installed.")
        print("  pip install google-analytics-data")
        sys.exit(1)

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    client = BetaAnalyticsDataClient()

    start_date = (date.today() - timedelta(days=days)).isoformat()
    end_date = date.today().isoformat()

    stages = []
    for stage_def in funnel:
        event_expressions = [
            FilterExpression(filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(value=event_name),
            ))
            for event_name in stage_def["events"]
        ]
        if len(event_expressions) == 1:
            event_expression = event_expressions[0]
        else:
            event_expression = FilterExpression(
                or_group=FilterExpressionList(expressions=event_expressions)
            )

        # If the stage has a page path filter, combine with AND
        if "filter_field" in stage_def:
            path_filter = Filter(
                field_name=stage_def["filter_field"],
                string_filter=Filter.StringFilter(
                    value=stage_def["filter_prefix"],
                    match_type=Filter.StringFilter.MatchType.BEGINS_WITH,
                ),
            )
            dimension_filter = FilterExpression(
                and_group=FilterExpressionList(
                    expressions=[
                        event_expression,
                        FilterExpression(filter=path_filter),
                    ]
                )
            )
        else:
            dimension_filter = event_expression

        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimension_filter=dimension_filter,
        )

        response = client.run_report(request)

        count = 0
        for row in response.rows:
            count += int(row.metric_values[0].value)

        stages.append({
            "stage": stage_def["stage"],
            "label": stage_def["label"],
            "count": count,
            "scope": stage_def["scope"],
            "event_names": list(stage_def["events"]),
        })

    return stages


def print_event_totals(title: str, stages: list[dict]):
    """Print independently aggregated events without cross-stage rates."""
    print(f"\n{'─' * 70}")
    print(f"  {title}")
    print(f"{'─' * 70}")

    print(f"  {'Observed event group':<38} {'Count':>8}  Scope")
    print(f"  {'─' * 38} {'─' * 8}  {'─' * 30}")

    for s in stages:
        print(f"  {s['label']:<38} {s['count']:>8,}  {s['scope']}")


def print_report(tp_stages: list[dict], coaching_stages: list[dict], days: int,
                 article_stages: list[dict] | None = None):
    """Print human-readable independent event totals to stdout."""
    print("=" * 70)
    print(f"INDEPENDENT GA4 EVENT TOTALS — last {days} days")
    print("=" * 70)
    print("No shared session, user, product, or event order is established.")
    print("Counts are observations, not conversion-rate denominators.")

    print_event_totals("TRAINING PLAN JOURNEY EVENTS", tp_stages)
    print_event_totals("COACHING JOURNEY EVENTS", coaching_stages)
    if article_stages:
        print_event_totals("ARTICLE JOURNEY EVENTS", article_stages)

    print(f"\n{'=' * 70}")


def build_report_payload(days: int, tp_stages: list[dict],
                         coaching_stages: list[dict],
                         article_stages: list[dict]) -> dict:
    """Build machine-readable output with an explicit measurement contract."""
    return {
        "schema": "ga4_event_totals/v2",
        "days": days,
        "measurement": MEASUREMENT_METADATA,
        "training_plan_totals": tp_stages,
        "coaching_totals": coaching_stages,
        "article_totals": article_stages,
    }


def get_mock_data() -> tuple[list[dict], list[dict], list[dict]]:
    """Return hardcoded sample data for testing without credentials."""
    def rows(definitions: list[dict], counts: list[int]) -> list[dict]:
        return [{
            "stage": definition["stage"],
            "label": definition["label"],
            "count": count,
            "scope": definition["scope"],
            "event_names": list(definition["events"]),
        } for definition, count in zip(definitions, counts)]

    # The purchase total intentionally exceeds checkout starts. Independent
    # aggregates can do this when event scope, attribution, or sources differ.
    tp_stages = rows(TRAINING_PLAN_FUNNEL, [12480, 1870, 624, 287, 143, 180])
    coaching_stages = rows(COACHING_FUNNEL, [3200, 480, 1120])
    article_stages = rows(ARTICLE_FUNNEL, [850, 340, 68])
    return tp_stages, coaching_stages, article_stages


def main():
    parser = argparse.ArgumentParser(
        description="GA4 journey-event totals with explicit scope and denominator limits"
    )
    parser.add_argument("--days", type=int, default=30,
                        help="Lookback days (default: 30)")
    parser.add_argument("--json", action="store_true",
                        help="JSON output")
    parser.add_argument("--mock", action="store_true",
                        help="Use mock data (for testing without GA4)")
    args = parser.parse_args()

    if args.mock:
        tp_stages, coaching_stages, article_stages = get_mock_data()
    else:
        property_id = os.environ.get("GA4_PROPERTY_ID")
        if not property_id:
            print("ERROR: GA4_PROPERTY_ID environment variable not set.")
            print("  export GA4_PROPERTY_ID=<your-ga4-property-id>")
            sys.exit(1)

        credentials_path = os.environ.get(
            "GA4_CREDENTIALS",
            str(PROJECT_ROOT / "ga4-credentials.json")
        )
        if not Path(credentials_path).exists():
            print(f"ERROR: Credentials file not found: {credentials_path}")
            print("  Set GA4_CREDENTIALS env var or place ga4-credentials.json in project root")
            sys.exit(1)

        tp_stages = get_funnel_data(
            property_id, credentials_path, args.days, TRAINING_PLAN_FUNNEL
        )
        coaching_stages = get_funnel_data(
            property_id, credentials_path, args.days, COACHING_FUNNEL
        )
        article_stages = get_funnel_data(
            property_id, credentials_path, args.days, ARTICLE_FUNNEL
        )

    if args.json:
        output = build_report_payload(
            args.days, tp_stages, coaching_stages, article_stages
        )
        print(json.dumps(output, indent=2))
    else:
        print_report(tp_stages, coaching_stages, args.days, article_stages)


if __name__ == "__main__":
    main()
