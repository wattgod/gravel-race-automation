#!/usr/bin/env python3
"""Core Web Vitals Monitor — PageSpeed Insights snapshots, reports, and alerting.

Usage:
    python scripts/cwv_monitor.py --snapshot                  # Capture snapshot (both strategies)
    python scripts/cwv_monitor.py --snapshot --mobile         # Mobile only
    python scripts/cwv_monitor.py --snapshot --desktop        # Desktop only
    python scripts/cwv_monitor.py --report                    # Show latest snapshot with pass/fail
    python scripts/cwv_monitor.py --alert                     # Check alert thresholds
    python scripts/cwv_monitor.py --snapshot --report --alert # All at once

API key:
    - Works without a key (rate-limited to ~25 req/100s)
    - Optional: export PAGESPEED_API_KEY=your_key for higher quota
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "cwv-snapshots"

# Pages to monitor — one per page type
MONITORED_URLS = [
    {"url": "https://gravelgodcycling.com/", "label": "Homepage"},
    {"url": "https://gravelgodcycling.com/gravel-races/", "label": "Race Search"},
    {"url": "https://gravelgodcycling.com/race/unbound-200/", "label": "T1 Race"},
    {"url": "https://gravelgodcycling.com/race/barry-roubaix/", "label": "T2 Race"},
    {"url": "https://gravelgodcycling.com/race/big-sugar/", "label": "T3 Race"},
    {"url": "https://gravelgodcycling.com/race/3-state-3-mountain-challenge/", "label": "T4 Race"},
    {"url": "https://gravelgodcycling.com/coaching/", "label": "Coaching"},
]

PSI_API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Google's CWV thresholds — "good" upper bounds
THRESHOLDS = {
    "lcp_ms": 2500,       # Largest Contentful Paint
    "cls": 0.1,           # Cumulative Layout Shift
    "inp_ms": 200,        # Interaction to Next Paint
    "fid_ms": 100,        # First Input Delay (legacy)
    "fcp_ms": 1800,       # First Contentful Paint
    "ttfb_ms": 800,       # Time to First Byte
    "speed_index_ms": 3400,  # Speed Index
}

# Alert thresholds — stricter than "poor", tuned for catching regressions
ALERT_THRESHOLDS = {
    "lcp_ms": 2500,
    "cls": 0.1,
    "inp_ms": 200,
}


def get_api_key() -> str | None:
    """Return PAGESPEED_API_KEY from env, or None."""
    return os.environ.get("PAGESPEED_API_KEY")


def fetch_psi(url: str, strategy: str = "mobile", api_key: str | None = None) -> dict:
    """Call PageSpeed Insights API and return raw JSON response.

    Args:
        url: Page URL to analyze
        strategy: "mobile" or "desktop"
        api_key: Optional API key for higher quota

    Returns:
        Raw PSI API response dict
    """
    params = {
        "url": url,
        "strategy": strategy,
        "category": "PERFORMANCE",
    }
    if api_key:
        params["key"] = api_key

    request_url = f"{PSI_API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(request_url)
    req.add_header("User-Agent", "GravelGod-CWV-Monitor/1.0")

    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read().decode("utf-8"))


def extract_metrics(psi_response: dict) -> dict:
    """Extract CWV metrics from a PSI API response.

    Returns dict with keys: lcp_ms, cls, inp_ms, fid_ms, fcp_ms, ttfb_ms,
    speed_index_ms, performance_score. Values are None if not available.
    """
    metrics = {
        "lcp_ms": None,
        "cls": None,
        "inp_ms": None,
        "fid_ms": None,
        "fcp_ms": None,
        "ttfb_ms": None,
        "speed_index_ms": None,
        "performance_score": None,
    }

    # Lab data from Lighthouse
    lighthouse = psi_response.get("lighthouseResult", {})
    audits = lighthouse.get("audits", {})

    if "largest-contentful-paint" in audits:
        val = audits["largest-contentful-paint"].get("numericValue")
        if val is not None:
            metrics["lcp_ms"] = round(val, 1)

    if "cumulative-layout-shift" in audits:
        val = audits["cumulative-layout-shift"].get("numericValue")
        if val is not None:
            metrics["cls"] = round(val, 4)

    if "interactive" in audits:
        # INP is not directly in Lighthouse lab data; use field data if available
        pass

    if "first-contentful-paint" in audits:
        val = audits["first-contentful-paint"].get("numericValue")
        if val is not None:
            metrics["fcp_ms"] = round(val, 1)

    if "server-response-time" in audits:
        val = audits["server-response-time"].get("numericValue")
        if val is not None:
            metrics["ttfb_ms"] = round(val, 1)

    if "speed-index" in audits:
        val = audits["speed-index"].get("numericValue")
        if val is not None:
            metrics["speed_index_ms"] = round(val, 1)

    # Performance score (0-100)
    categories = lighthouse.get("categories", {})
    perf = categories.get("performance", {})
    if perf.get("score") is not None:
        metrics["performance_score"] = round(perf["score"] * 100)

    # Field data (CrUX) — preferred for INP/FID/CLS as these are real-user metrics
    loading_exp = psi_response.get("loadingExperience", {})
    crux_metrics = loading_exp.get("metrics", {})

    if "INTERACTION_TO_NEXT_PAINT" in crux_metrics:
        val = crux_metrics["INTERACTION_TO_NEXT_PAINT"].get("percentile")
        if val is not None:
            metrics["inp_ms"] = val

    if "FIRST_INPUT_DELAY_MS" in crux_metrics:
        val = crux_metrics["FIRST_INPUT_DELAY_MS"].get("percentile")
        if val is not None:
            metrics["fid_ms"] = val

    # Prefer CrUX CLS over lab CLS if available
    if "CUMULATIVE_LAYOUT_SHIFT_SCORE" in crux_metrics:
        val = crux_metrics["CUMULATIVE_LAYOUT_SHIFT_SCORE"].get("percentile")
        if val is not None:
            metrics["cls"] = round(val / 100, 4)

    # Prefer CrUX LCP over lab LCP if available
    if "LARGEST_CONTENTFUL_PAINT_MS" in crux_metrics:
        val = crux_metrics["LARGEST_CONTENTFUL_PAINT_MS"].get("percentile")
        if val is not None:
            metrics["lcp_ms"] = val

    return metrics


def grade_metric(key: str, value) -> str:
    """Return PASS / FAIL / N/A for a metric against thresholds."""
    if value is None:
        return "N/A"
    threshold = THRESHOLDS.get(key)
    if threshold is None:
        return "N/A"
    return "PASS" if value <= threshold else "FAIL"


def run_snapshot(strategies: list[str]) -> dict:
    """Run PSI checks for all monitored URLs and return snapshot dict.

    Args:
        strategies: list of "mobile" and/or "desktop"

    Returns:
        Snapshot dict with timestamp, results per URL/strategy, and summary
    """
    api_key = get_api_key()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    snapshot = {
        "timestamp": timestamp,
        "strategies": strategies,
        "results": [],
        "summary": {},
    }

    total_checks = len(MONITORED_URLS) * len(strategies)
    check_num = 0

    for entry in MONITORED_URLS:
        url = entry["url"]
        label = entry["label"]

        for strategy in strategies:
            check_num += 1
            print(f"  [{check_num}/{total_checks}] {label} ({strategy})...", end=" ", flush=True)

            try:
                raw = fetch_psi(url, strategy=strategy, api_key=api_key)
                metrics = extract_metrics(raw)

                result = {
                    "url": url,
                    "label": label,
                    "strategy": strategy,
                    "metrics": metrics,
                    "grades": {k: grade_metric(k, v) for k, v in metrics.items() if k != "performance_score"},
                }
                snapshot["results"].append(result)

                score = metrics.get("performance_score")
                lcp = metrics.get("lcp_ms")
                cls_val = metrics.get("cls")
                score_str = f"{score}" if score is not None else "?"
                lcp_str = f"{lcp:.0f}ms" if lcp is not None else "?"
                cls_str = f"{cls_val:.3f}" if cls_val is not None else "?"
                print(f"score={score_str}  LCP={lcp_str}  CLS={cls_str}")

                # Rate limit: PSI free tier allows ~25 req/100s
                if check_num < total_checks:
                    time.sleep(3)

            except urllib.error.HTTPError as e:
                print(f"HTTP {e.code}")
                snapshot["results"].append({
                    "url": url,
                    "label": label,
                    "strategy": strategy,
                    "error": f"HTTP {e.code}: {e.reason}",
                    "metrics": {},
                    "grades": {},
                })
            except Exception as e:
                print(f"ERROR: {e}")
                snapshot["results"].append({
                    "url": url,
                    "label": label,
                    "strategy": strategy,
                    "error": str(e),
                    "metrics": {},
                    "grades": {},
                })

    # Build summary
    _build_summary(snapshot)
    return snapshot


def _build_summary(snapshot: dict):
    """Compute summary stats across all results."""
    valid_results = [r for r in snapshot["results"] if "error" not in r]
    if not valid_results:
        snapshot["summary"] = {"total_checks": len(snapshot["results"]), "errors": len(snapshot["results"])}
        return

    scores = [r["metrics"]["performance_score"] for r in valid_results if r["metrics"].get("performance_score") is not None]
    fails = sum(1 for r in valid_results for g in r.get("grades", {}).values() if g == "FAIL")
    passes = sum(1 for r in valid_results for g in r.get("grades", {}).values() if g == "PASS")
    errors = len(snapshot["results"]) - len(valid_results)

    snapshot["summary"] = {
        "total_checks": len(snapshot["results"]),
        "errors": errors,
        "avg_performance_score": round(sum(scores) / len(scores), 1) if scores else None,
        "min_performance_score": min(scores) if scores else None,
        "max_performance_score": max(scores) if scores else None,
        "pass_count": passes,
        "fail_count": fails,
    }


def save_snapshot(snapshot: dict) -> Path:
    """Save snapshot to data/cwv-snapshots/{timestamp}.json."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = snapshot["timestamp"].replace(":", "-").replace("T", "_").rstrip("Z")
    path = SNAPSHOT_DIR / f"{ts}.json"
    path.write_text(json.dumps(snapshot, indent=2) + "\n")
    return path


def load_latest_snapshot() -> dict | None:
    """Load the most recent snapshot file, or None."""
    if not SNAPSHOT_DIR.exists():
        return None
    files = sorted(SNAPSHOT_DIR.glob("*.json"))
    if not files:
        return None
    return json.loads(files[-1].read_text())


def list_snapshots() -> list[Path]:
    """List all snapshot files sorted by date."""
    if not SNAPSHOT_DIR.exists():
        return []
    return sorted(SNAPSHOT_DIR.glob("*.json"))


def print_report(snapshot: dict | None = None):
    """Print pass/fail report for the latest snapshot."""
    if snapshot is None:
        snapshot = load_latest_snapshot()
    if snapshot is None:
        print("No snapshots found. Run --snapshot first.")
        return

    print(f"\n{'=' * 72}")
    print(f"  CWV REPORT -- {snapshot['timestamp']}")
    print(f"{'=' * 72}")

    summary = snapshot.get("summary", {})
    avg_score = summary.get("avg_performance_score")
    if avg_score is not None:
        print(f"  Avg performance score: {avg_score:.0f}/100")
        print(f"  Range: {summary.get('min_performance_score')}-{summary.get('max_performance_score')}")
    print(f"  Checks: {summary.get('total_checks', 0)}  Pass: {summary.get('pass_count', 0)}  Fail: {summary.get('fail_count', 0)}  Errors: {summary.get('errors', 0)}")

    for strategy in snapshot.get("strategies", ["mobile", "desktop"]):
        results = [r for r in snapshot["results"] if r.get("strategy") == strategy]
        if not results:
            continue

        print(f"\n{'─' * 72}")
        print(f"  {strategy.upper()}")
        print(f"{'─' * 72}")
        print(f"  {'Page':<20} {'Score':>5} {'LCP':>8} {'CLS':>7} {'INP':>7} {'FCP':>8} {'TTFB':>8} {'SI':>8}")

        for r in results:
            if "error" in r:
                print(f"  {r['label']:<20} ERROR: {r['error']}")
                continue

            m = r["metrics"]
            g = r["grades"]

            def _fmt(key, unit="ms", decimals=0):
                val = m.get(key)
                if val is None:
                    return "   --  "
                grade = g.get(key, "N/A")
                marker = "*" if grade == "FAIL" else " "
                if unit == "ms":
                    return f"{val:>6.0f}{marker}"
                else:
                    return f"{val:>6.3f}{marker}"

            score = m.get("performance_score")
            score_str = f"{score:>5}" if score is not None else "   --"

            print(f"  {r['label']:<20} {score_str} {_fmt('lcp_ms')} {_fmt('cls', unit='')} {_fmt('inp_ms')} {_fmt('fcp_ms')} {_fmt('ttfb_ms')} {_fmt('speed_index_ms')}")

    print(f"\n  * = exceeds Google threshold")
    print(f"  Thresholds: LCP <{THRESHOLDS['lcp_ms']}ms  CLS <{THRESHOLDS['cls']}  INP <{THRESHOLDS['inp_ms']}ms  FCP <{THRESHOLDS['fcp_ms']}ms  TTFB <{THRESHOLDS['ttfb_ms']}ms")
    print()


def check_alerts(snapshot: dict | None = None) -> int:
    """Check alert thresholds. Returns exit code (0=ok, 1=alerts fired)."""
    if snapshot is None:
        snapshot = load_latest_snapshot()
    if snapshot is None:
        print("No snapshots found. Run --snapshot first.")
        return 0

    alerts = []
    valid_results = [r for r in snapshot["results"] if "error" not in r]

    for r in valid_results:
        m = r["metrics"]
        label = f"{r['label']} ({r['strategy']})"

        lcp = m.get("lcp_ms")
        if lcp is not None and lcp > ALERT_THRESHOLDS["lcp_ms"]:
            alerts.append(f"LCP {lcp:.0f}ms > {ALERT_THRESHOLDS['lcp_ms']}ms -- {label}")

        cls_val = m.get("cls")
        if cls_val is not None and cls_val > ALERT_THRESHOLDS["cls"]:
            alerts.append(f"CLS {cls_val:.3f} > {ALERT_THRESHOLDS['cls']} -- {label}")

        inp = m.get("inp_ms")
        if inp is not None and inp > ALERT_THRESHOLDS["inp_ms"]:
            alerts.append(f"INP {inp}ms > {ALERT_THRESHOLDS['inp_ms']}ms -- {label}")

    if alerts:
        print(f"\n{'!' * 72}")
        print(f"  CWV ALERTS -- {snapshot['timestamp']}")
        print(f"{'!' * 72}")
        for a in alerts:
            print(f"  !!  {a}")
        print()
        return 1
    else:
        print(f"\n  CWV ALERTS -- {snapshot['timestamp']}: All clear")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Core Web Vitals Monitor — PageSpeed Insights")
    parser.add_argument("--snapshot", action="store_true", help="Run PSI checks and save snapshot")
    parser.add_argument("--report", action="store_true", help="Show latest snapshot with pass/fail")
    parser.add_argument("--alert", action="store_true", help="Check alert thresholds (LCP/CLS/INP)")
    parser.add_argument("--mobile", action="store_true", help="Mobile strategy only")
    parser.add_argument("--desktop", action="store_true", help="Desktop strategy only")
    args = parser.parse_args()

    if not any([args.snapshot, args.report, args.alert]):
        parser.print_help()
        return

    # Determine strategies
    if args.mobile and not args.desktop:
        strategies = ["mobile"]
    elif args.desktop and not args.mobile:
        strategies = ["desktop"]
    else:
        strategies = ["mobile", "desktop"]

    snapshot = None

    if args.snapshot:
        print(f"\n  Running CWV checks ({', '.join(strategies)})...")
        snapshot = run_snapshot(strategies)
        path = save_snapshot(snapshot)
        s = snapshot["summary"]
        print(f"\n  Snapshot saved: {path.name}")
        avg = s.get("avg_performance_score")
        avg_str = f"{avg:.0f}" if avg is not None else "--"
        print(f"  Avg score: {avg_str}/100  Pass: {s.get('pass_count', 0)}  Fail: {s.get('fail_count', 0)}  Errors: {s.get('errors', 0)}")

    if args.report:
        print_report(snapshot)

    if args.alert:
        exit_code = check_alerts(snapshot)
        if exit_code and not args.report:
            sys.exit(exit_code)


if __name__ == "__main__":
    main()
