#!/usr/bin/env python3
"""
A/B test reporting — queries GA4 Data API for experiment results.

Calculates conversion rates per variant, runs chi-squared significance
tests, and declares winners when p < 0.05 with minimum sample size.

Prerequisites:
  - GA4 custom dimensions registered: experiment_id, variant_id, variant_name
  - Google Analytics Data API credentials (service account JSON)
  - pip install google-analytics-data scipy

Usage:
    python scripts/ab_report.py                          # all experiments
    python scripts/ab_report.py --experiment homepage_hero_tagline
    python scripts/ab_report.py --json                   # machine-readable
    python scripts/ab_report.py --days 14                # last 14 days

Environment:
    GA4_PROPERTY_ID     — GA4 property ID (numeric)
    GA4_CREDENTIALS     — path to service account JSON (default: ga4-credentials.json)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

MIN_SAMPLE_SIZE = 100
SIGNIFICANCE_THRESHOLD = 0.05

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add wordpress/ to path for config import
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))


def get_ga4_data(property_id: str, credentials_path: str, days: int,
                 experiment_filter: str | None = None) -> dict:
    """Query GA4 Data API for ab_impression and ab_conversion events."""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.analytics.data_v1beta.types import (
            DateRange,
            Dimension,
            FilterExpression,
            Filter,
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

    results = {"impressions": defaultdict(lambda: defaultdict(int)),
               "conversions": defaultdict(lambda: defaultdict(int))}

    for event_name, bucket in [("ab_impression", "impressions"),
                                ("ab_conversion", "conversions")]:
        dimension_filter = FilterExpression(
            filter=Filter(
                field_name="eventName",
                string_filter=Filter.StringFilter(value=event_name),
            )
        )

        request = RunReportRequest(
            property=f"properties/{property_id}",
            dimensions=[
                Dimension(name="customEvent:experiment_id"),
                Dimension(name="customEvent:variant_id"),
            ],
            metrics=[Metric(name="eventCount")],
            date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
            dimension_filter=dimension_filter,
        )

        response = client.run_report(request)

        for row in response.rows:
            exp_id = row.dimension_values[0].value
            var_id = row.dimension_values[1].value
            count = int(row.metric_values[0].value)

            if experiment_filter and exp_id != experiment_filter:
                continue

            results[bucket][exp_id][var_id] = count

    return results


def chi_squared_test(control_impressions: int, control_conversions: int,
                     variant_impressions: int, variant_conversions: int) -> float:
    """Run chi-squared test comparing variant vs control. Returns p-value."""
    # Avoid division by zero
    if control_impressions == 0 or variant_impressions == 0:
        return 1.0
    if control_conversions < 0 or variant_conversions < 0:
        return 1.0

    try:
        import numpy as np
        from scipy.stats import chi2_contingency

        observed = np.array([
            [control_conversions, control_impressions - control_conversions],
            [variant_conversions, variant_impressions - variant_conversions],
        ])

        _, p_value, _, _ = chi2_contingency(observed)
        return p_value
    except ImportError:
        # Fallback: no scipy — return 1.0 (no significance claim)
        return 1.0
    except ValueError:
        return 1.0


def analyze(ga4_data: dict) -> list[dict]:
    """Analyze experiment results and determine winners."""
    from ab_experiments import EXPERIMENTS

    exp_lookup = {e["id"]: e for e in EXPERIMENTS}
    reports = []

    all_exp_ids = set(ga4_data["impressions"].keys()) | set(ga4_data["conversions"].keys())

    for exp_id in sorted(all_exp_ids):
        exp_config = exp_lookup.get(exp_id, {"description": "Unknown experiment"})
        impressions = ga4_data["impressions"].get(exp_id, {})
        conversions = ga4_data["conversions"].get(exp_id, {})

        variants = []
        control_imp = impressions.get("control", 0)
        control_conv = conversions.get("control", 0)
        control_rate = control_conv / control_imp if control_imp > 0 else 0

        for var_id in sorted(set(list(impressions.keys()) + list(conversions.keys()))):
            imp = impressions.get(var_id, 0)
            conv = conversions.get(var_id, 0)
            rate = conv / imp if imp > 0 else 0

            variant_report = {
                "variant_id": var_id,
                "impressions": imp,
                "conversions": conv,
                "conversion_rate": round(rate, 4),
            }

            if var_id != "control" and control_imp > 0 and imp > 0:
                p_value = chi_squared_test(control_imp, control_conv, imp, conv)
                variant_report["p_value"] = round(p_value, 6)
                variant_report["significant"] = (
                    p_value < SIGNIFICANCE_THRESHOLD
                    and imp >= MIN_SAMPLE_SIZE
                    and control_imp >= MIN_SAMPLE_SIZE
                )
                variant_report["lift"] = round(
                    (rate - control_rate) / control_rate, 4
                ) if control_rate > 0 else None

            variants.append(variant_report)

        # Determine winner
        winner = None
        significant_variants = [
            v for v in variants
            if v.get("significant") and v["conversion_rate"] > control_rate
        ]
        if significant_variants:
            winner = max(significant_variants, key=lambda v: v["conversion_rate"])

        total_impressions = sum(v["impressions"] for v in variants)
        reports.append({
            "experiment_id": exp_id,
            "description": exp_config.get("description", ""),
            "total_impressions": total_impressions,
            "variants": variants,
            "winner": winner["variant_id"] if winner else None,
            "status": "winner" if winner else (
                "running" if total_impressions >= MIN_SAMPLE_SIZE else "collecting"
            ),
        })

    return reports


def print_report(reports: list[dict]):
    """Print human-readable report to stdout."""
    print("=" * 65)
    print("A/B TEST REPORT")
    print("=" * 65)

    if not reports:
        print("\nNo experiment data found.")
        print("Ensure GA4 custom dimensions are registered and events are flowing.")
        return

    for r in reports:
        print(f"\n{'─' * 65}")
        print(f"Experiment: {r['experiment_id']}")
        print(f"  {r['description']}")
        print(f"  Status: {r['status'].upper()} | Total impressions: {r['total_impressions']}")
        print()

        for v in r["variants"]:
            rate_pct = f"{v['conversion_rate'] * 100:.1f}%"
            sig = ""
            if "p_value" in v:
                sig = f" | p={v['p_value']:.4f}"
                if v.get("significant"):
                    sig += " ***"
                lift = v.get("lift")
                if lift is not None:
                    sig += f" | lift={lift:+.1%}"
            print(f"  {v['variant_id']:>12}: {v['impressions']:>6} imp → "
                  f"{v['conversions']:>4} conv = {rate_pct:>6}{sig}")

        if r["winner"]:
            print(f"\n  WINNER: {r['winner']}")
        elif r["status"] == "collecting":
            needed = MIN_SAMPLE_SIZE - r["total_impressions"]
            print(f"\n  Need ~{max(0, needed)} more impressions for significance testing")

    print(f"\n{'=' * 65}")


def main():
    parser = argparse.ArgumentParser(description="A/B test reporting")
    parser.add_argument("--experiment", help="Filter to specific experiment ID")
    parser.add_argument("--days", type=int, default=30, help="Lookback days (default: 30)")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--mock", action="store_true",
                        help="Use mock data (for testing without GA4)")
    args = parser.parse_args()

    if args.mock:
        # Mock data for testing the report pipeline
        ga4_data = {
            "impressions": {
                "homepage_hero_tagline": {"control": 150, "variant_a": 148, "variant_b": 152},
                "training_price_frame": {"control": 80, "variant_a": 78, "variant_b": 82},
            },
            "conversions": {
                "homepage_hero_tagline": {"control": 12, "variant_a": 18, "variant_b": 14},
                "training_price_frame": {"control": 5, "variant_a": 7, "variant_b": 4},
            },
        }
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

        ga4_data = get_ga4_data(property_id, credentials_path, args.days, args.experiment)

    reports = analyze(ga4_data)

    if args.json:
        print(json.dumps(reports, indent=2))
    else:
        print_report(reports)


if __name__ == "__main__":
    main()
