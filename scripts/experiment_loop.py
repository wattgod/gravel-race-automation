#!/usr/bin/env python3
"""
Automated experiment orchestration — Karpathy-style experiment loop.

Analyzes active A/B experiments, logs winners, and queues the next
hypothesis from the template library. Designed to run on a cadence
(weekly cron or manual) with --dry-run as the safe default.

Flow:
  1. Pull GA4 data for all active experiments
  2. Identify statistically significant winners (p < 0.05, >= 14 days)
  3. Log completed experiments to data/experiment-log.json
  4. Select next hypothesis from experiment_templates.py
  5. Optionally deploy via push_wordpress.py --sync-ab

Usage:
    python scripts/experiment_loop.py                          # dry-run report
    python scripts/experiment_loop.py --execute                # log winners, queue next
    python scripts/experiment_loop.py --execute --deploy       # also print deploy command
    python scripts/experiment_loop.py --days 21                # custom lookback
    python scripts/experiment_loop.py --json                   # machine-readable output

Environment:
    GA4_PROPERTY_ID     — GA4 property ID (numeric)
    GA4_CREDENTIALS     — path to service account JSON
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_LOG = PROJECT_ROOT / "data" / "experiment-log.json"
MIN_RUNTIME_DAYS = 14

# Add scripts/ and wordpress/ to path
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))


def load_experiment_log() -> list[dict]:
    """Load the experiment log, creating it if it doesn't exist."""
    if EXPERIMENT_LOG.exists():
        return json.loads(EXPERIMENT_LOG.read_text())
    return []


def save_experiment_log(log: list[dict]) -> None:
    """Write experiment log to disk."""
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    EXPERIMENT_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False) + "\n")


def get_experiment_start_date(experiment_id: str) -> date | None:
    """Look up experiment start date from ab_experiments.py."""
    from ab_experiments import EXPERIMENTS
    for exp in EXPERIMENTS:
        if exp["id"] == experiment_id:
            start = exp.get("start")
            if start:
                return date.fromisoformat(start)
    return None


def experiment_runtime_days(experiment_id: str) -> int:
    """Return number of days the experiment has been running."""
    start = get_experiment_start_date(experiment_id)
    if not start:
        return 0
    return (date.today() - start).days


def find_used_template_ids(log: list[dict]) -> list[str]:
    """Extract all template IDs that have been tested from the log."""
    used = []
    for entry in log:
        if entry.get("experiment_id"):
            used.append(entry["experiment_id"])
        if entry.get("next_hypothesis_id"):
            used.append(entry["next_hypothesis_id"])
    return used


def run_loop(days: int, execute: bool, deploy: bool, use_mock: bool,
             output_json: bool) -> dict:
    """Main experiment loop. Returns summary dict."""
    from ab_report import analyze, get_ga4_data
    from experiment_templates import TEMPLATES, get_next_template, list_categories
    import os

    # ── 1. Get GA4 data ─────────────────────────────────────────
    if use_mock:
        ga4_data = {
            "impressions": {
                "homepage_hero_tagline": {
                    "control": 520, "variant_a": 515, "variant_b": 510,
                },
                "training_price_frame": {
                    "control": 480, "variant_a": 475, "variant_b": 490,
                },
                "cta_button_text": {
                    "control": 350, "variant_a": 340, "variant_b": 345,
                },
                "coaching_scarcity": {
                    "control": 200, "variant_a": 195, "variant_b": 205,
                },
            },
            "conversions": {
                "homepage_hero_tagline": {
                    "control": 38, "variant_a": 62, "variant_b": 41,
                },
                "training_price_frame": {
                    "control": 28, "variant_a": 35, "variant_b": 30,
                },
                "cta_button_text": {
                    "control": 22, "variant_a": 20, "variant_b": 25,
                },
                "coaching_scarcity": {
                    "control": 10, "variant_a": 14, "variant_b": 11,
                },
            },
        }
    else:
        property_id = os.environ.get("GA4_PROPERTY_ID")
        if not property_id:
            print("ERROR: GA4_PROPERTY_ID not set. Use --mock for testing.")
            sys.exit(1)
        credentials_path = os.environ.get(
            "GA4_CREDENTIALS",
            str(PROJECT_ROOT / "ga4-credentials.json"),
        )
        if not Path(credentials_path).exists():
            print(f"ERROR: Credentials not found: {credentials_path}")
            sys.exit(1)
        ga4_data = get_ga4_data(property_id, credentials_path, days)

    # ── 2. Analyze experiments ──────────────────────────────────
    reports = analyze(ga4_data)
    log = load_experiment_log()
    logged_ids = {e["experiment_id"] for e in log}

    completed = []
    still_running = []

    for report in reports:
        exp_id = report["experiment_id"]
        runtime = experiment_runtime_days(exp_id)

        if report["winner"] and runtime >= MIN_RUNTIME_DAYS and exp_id not in logged_ids:
            # Find the winning variant details
            winner_variant = None
            control_variant = None
            for v in report["variants"]:
                if v["variant_id"] == report["winner"]:
                    winner_variant = v
                if v["variant_id"] == "control":
                    control_variant = v

            start_date = get_experiment_start_date(exp_id)
            entry = {
                "experiment_id": exp_id,
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": date.today().isoformat(),
                "winner_variant": report["winner"],
                "control_rate": control_variant["conversion_rate"] if control_variant else 0,
                "winner_rate": winner_variant["conversion_rate"] if winner_variant else 0,
                "lift_pct": round(
                    (winner_variant.get("lift", 0) or 0) * 100, 1
                ) if winner_variant else 0,
                "p_value": winner_variant.get("p_value", 1.0) if winner_variant else 1.0,
                "next_hypothesis_id": None,  # filled below
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            completed.append(entry)
        elif report["winner"] and runtime < MIN_RUNTIME_DAYS:
            still_running.append({
                "experiment_id": exp_id,
                "status": f"significant but only {runtime} days old (need {MIN_RUNTIME_DAYS})",
                "winner": report["winner"],
            })
        elif not report["winner"]:
            still_running.append({
                "experiment_id": exp_id,
                "status": report["status"],
                "total_impressions": report["total_impressions"],
            })

    # ── 3. Queue next hypotheses ────────────────────────────────
    used_ids = find_used_template_ids(log + completed)
    next_hypotheses = []

    for category in list_categories():
        template = get_next_template(category, used_ids)
        if template:
            next_hypotheses.append({
                "category": category,
                "template_id": template["id"],
                "description": template["description"],
            })

    # Assign next hypothesis to completed experiments
    hypothesis_idx = 0
    for entry in completed:
        if hypothesis_idx < len(next_hypotheses):
            entry["next_hypothesis_id"] = next_hypotheses[hypothesis_idx]["template_id"]
            hypothesis_idx += 1

    # ── 4. Execute or dry-run ───────────────────────────────────
    summary = {
        "mode": "execute" if execute else "dry-run",
        "lookback_days": days,
        "date": date.today().isoformat(),
        "completed_experiments": completed,
        "still_running": still_running,
        "next_hypotheses": next_hypotheses,
        "log_path": str(EXPERIMENT_LOG),
    }

    if execute and completed:
        log.extend(completed)
        save_experiment_log(log)
        summary["log_updated"] = True
        summary["log_entries_added"] = len(completed)
    else:
        summary["log_updated"] = False

    if deploy:
        deploy_cmd = f"python {PROJECT_ROOT}/wordpress/push_wordpress.py --sync-ab --purge-cache"
        summary["deploy_command"] = deploy_cmd

    return summary


def print_report(summary: dict) -> None:
    """Print human-readable report."""
    mode_label = "DRY RUN" if summary["mode"] == "dry-run" else "EXECUTE"
    print("=" * 65)
    print(f"EXPERIMENT LOOP — {mode_label}")
    print(f"Date: {summary['date']} | Lookback: {summary['lookback_days']} days")
    print("=" * 65)

    # Completed experiments with winners
    completed = summary["completed_experiments"]
    if completed:
        print(f"\n{'─' * 65}")
        print(f"COMPLETED ({len(completed)} experiment(s) with significant winner)")
        print(f"{'─' * 65}")
        for entry in completed:
            control_pct = f"{entry['control_rate'] * 100:.1f}%"
            winner_pct = f"{entry['winner_rate'] * 100:.1f}%"
            print(f"\n  {entry['experiment_id']}")
            print(f"    Winner: {entry['winner_variant']}")
            print(f"    Control: {control_pct} → Winner: {winner_pct} "
                  f"(+{entry['lift_pct']:.1f}%, p={entry['p_value']:.4f})")
            print(f"    Runtime: {entry['start_date']} → {entry['end_date']}")
            if entry.get("next_hypothesis_id"):
                print(f"    Next hypothesis: {entry['next_hypothesis_id']}")
    else:
        print("\nNo experiments completed this cycle.")

    # Still running
    running = summary["still_running"]
    if running:
        print(f"\n{'─' * 65}")
        print(f"STILL RUNNING ({len(running)} experiment(s))")
        print(f"{'─' * 65}")
        for exp in running:
            status = exp.get("status", "unknown")
            detail = ""
            if "total_impressions" in exp:
                detail = f" | {exp['total_impressions']} impressions"
            if "winner" in exp:
                detail = f" | tentative winner: {exp['winner']}"
            print(f"  {exp['experiment_id']}: {status}{detail}")

    # Next hypotheses
    hypotheses = summary["next_hypotheses"]
    if hypotheses:
        print(f"\n{'─' * 65}")
        print(f"NEXT HYPOTHESES ({len(hypotheses)} queued)")
        print(f"{'─' * 65}")
        for h in hypotheses:
            print(f"  [{h['category']}] {h['template_id']}")
            print(f"    {h['description']}")

    # Log status
    if summary.get("log_updated"):
        print(f"\nLog updated: {summary['log_entries_added']} entries → {summary['log_path']}")
    elif summary["mode"] == "dry-run" and completed:
        print(f"\nDry run — log NOT updated. Use --execute to write to {summary['log_path']}")

    # Deploy command
    if summary.get("deploy_command"):
        print(f"\nDeploy command (not executed):")
        print(f"  {summary['deploy_command']}")

    print(f"\n{'=' * 65}")


def main():
    parser = argparse.ArgumentParser(
        description="Automated experiment loop — analyze, log, and queue A/B tests",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Report only, don't modify anything (default)",
    )
    mode.add_argument(
        "--execute", action="store_true",
        help="Log winners and queue next hypotheses",
    )
    parser.add_argument(
        "--deploy", action="store_true",
        help="Print deploy command for syncing A/B config (does not execute)",
    )
    parser.add_argument(
        "--days", type=int, default=30,
        help="GA4 lookback window in days (default: 30)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output machine-readable JSON",
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Use mock GA4 data (for testing without credentials)",
    )
    args = parser.parse_args()

    summary = run_loop(
        days=args.days,
        execute=args.execute,
        deploy=args.deploy,
        use_mock=args.mock,
        output_json=args.json,
    )

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print_report(summary)


if __name__ == "__main__":
    main()
