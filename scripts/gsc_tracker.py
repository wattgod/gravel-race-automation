#!/usr/bin/env python3
"""GSC Monitoring Tracker — daily snapshots, trend analysis, and alerting.

Usage:
    python scripts/gsc_tracker.py --snapshot          # Capture daily snapshot
    python scripts/gsc_tracker.py --report            # Show 7d/30d trend report
    python scripts/gsc_tracker.py --alert             # Check alert thresholds
    python scripts/gsc_tracker.py --snapshot --report  # Capture + report

Requires:
    - GOOGLE_APPLICATION_CREDENTIALS env var → service account JSON
    - Service account needs GSC "Viewer" role on the property
    - pip install google-api-python-client google-auth
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

SITE_URL = "sc-domain:gravelgodcycling.com"
SNAPSHOT_DIR = Path(__file__).resolve().parent.parent / "data" / "gsc-snapshots"

# Alert thresholds
IMPRESSION_DROP_PCT = 20  # warn if impressions drop >20% vs 7d ago
CTR_FLOOR = 2.0           # warn if CTR drops below 2%
POSITION_REGRESSION = 5   # warn if avg position regresses >5 spots


def get_gsc_service():
    """Build GSC API service from GOOGLE_APPLICATION_CREDENTIALS."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path:
        return None

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    return build("searchconsole", "v1", credentials=creds)


def fetch_snapshot(service, target_date: date) -> dict:
    """Fetch a single day's GSC data and return structured snapshot."""
    end = target_date
    start = target_date - timedelta(days=6)  # 7-day window ending on target_date

    snapshot = {
        "date": target_date.isoformat(),
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "overall": {},
        "top_queries": [],
        "top_pages": [],
        "race_pages": [],
    }

    # Overall metrics
    resp = service.searchanalytics().query(
        siteUrl=SITE_URL,
        body={
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": [],
        }
    ).execute()
    if resp.get("rows"):
        r = resp["rows"][0]
        snapshot["overall"] = {
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 2),
            "position": round(r.get("position", 0), 1),
        }

    # Top queries (top 30)
    resp = service.searchanalytics().query(
        siteUrl=SITE_URL,
        body={
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["query"],
            "rowLimit": 30,
        }
    ).execute()
    snapshot["top_queries"] = [
        {
            "query": r["keys"][0],
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 1),
            "position": round(r.get("position", 0), 1),
        }
        for r in resp.get("rows", [])
    ]

    # Top pages (top 50)
    resp = service.searchanalytics().query(
        siteUrl=SITE_URL,
        body={
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
            "dimensions": ["page"],
            "rowLimit": 50,
        }
    ).execute()
    all_pages = [
        {
            "page": r["keys"][0].replace("https://gravelgodcycling.com", ""),
            "clicks": r.get("clicks", 0),
            "impressions": r.get("impressions", 0),
            "ctr": round(r.get("ctr", 0) * 100, 1),
            "position": round(r.get("position", 0), 1),
        }
        for r in resp.get("rows", [])
    ]
    snapshot["top_pages"] = all_pages

    # Filter race-specific pages
    snapshot["race_pages"] = [
        p for p in all_pages if p["page"].startswith("/race/")
    ]

    return snapshot


def save_snapshot(snapshot: dict) -> Path:
    """Save snapshot to data/gsc-snapshots/{date}.json."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    path = SNAPSHOT_DIR / f"{snapshot['date']}.json"
    path.write_text(json.dumps(snapshot, indent=2) + "\n")
    return path


def load_snapshot(target_date: date) -> dict | None:
    """Load a snapshot by date, or None if not found."""
    path = SNAPSHOT_DIR / f"{target_date.isoformat()}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def find_nearest_snapshot(target_date: date, max_days: int = 3) -> dict | None:
    """Find the nearest snapshot within max_days of target_date."""
    for offset in range(max_days + 1):
        snap = load_snapshot(target_date - timedelta(days=offset))
        if snap:
            return snap
        if offset > 0:
            snap = load_snapshot(target_date + timedelta(days=offset))
            if snap:
                return snap
    return None


def list_snapshots() -> list[Path]:
    """List all snapshot files sorted by date."""
    if not SNAPSHOT_DIR.exists():
        return []
    return sorted(SNAPSHOT_DIR.glob("*.json"))


def pct_change(current: float, previous: float) -> str:
    """Format percentage change with arrow."""
    if previous == 0:
        return "N/A"
    change = ((current - previous) / previous) * 100
    arrow = "\u2191" if change > 0 else "\u2193" if change < 0 else "\u2192"
    return f"{arrow} {abs(change):.1f}%"


def print_report(today: date):
    """Print trend report comparing latest vs 7d/30d ago."""
    latest = find_nearest_snapshot(today)
    week_ago = find_nearest_snapshot(today - timedelta(days=7))
    month_ago = find_nearest_snapshot(today - timedelta(days=30))

    if not latest:
        print("No snapshots found. Run --snapshot first.")
        return

    print(f"\n{'=' * 60}")
    print(f"  GSC TREND REPORT — {latest['date']}")
    print(f"{'=' * 60}\n")

    o = latest.get("overall", {})
    print(f"  Current 7d window: {latest['window']['start']} to {latest['window']['end']}")
    print(f"  Clicks:      {o.get('clicks', 0):,}")
    print(f"  Impressions: {o.get('impressions', 0):,}")
    print(f"  CTR:         {o.get('ctr', 0):.2f}%")
    print(f"  Avg Position:{o.get('position', 0):.1f}")

    # Comparisons
    for label, snap in [("7d ago", week_ago), ("30d ago", month_ago)]:
        if not snap:
            print(f"\n  vs {label}: No snapshot available")
            continue
        prev = snap.get("overall", {})
        print(f"\n  vs {label} ({snap['date']}):")
        print(f"    Clicks:      {pct_change(o.get('clicks', 0), prev.get('clicks', 0))}")
        print(f"    Impressions: {pct_change(o.get('impressions', 0), prev.get('impressions', 0))}")
        print(f"    CTR:         {o.get('ctr', 0):.2f}% (was {prev.get('ctr', 0):.2f}%)")
        print(f"    Position:    {o.get('position', 0):.1f} (was {prev.get('position', 0):.1f})")

    # Top queries
    queries = latest.get("top_queries", [])
    if queries:
        print(f"\n{'─' * 60}")
        print("  TOP QUERIES (7d)")
        print(f"{'─' * 60}")
        print(f"  {'Query':<40} {'Clicks':>6} {'Impr':>7} {'CTR':>6} {'Pos':>5}")
        for q in queries[:15]:
            print(f"  {q['query'][:40]:<40} {q['clicks']:>6} {q['impressions']:>7} {q['ctr']:>5.1f}% {q['position']:>5.1f}")

    # Race pages
    race_pages = latest.get("race_pages", [])
    if race_pages:
        print(f"\n{'─' * 60}")
        print("  RACE PAGES (indexed)")
        print(f"{'─' * 60}")
        print(f"  {'Page':<45} {'Clicks':>6} {'Impr':>7} {'Pos':>5}")
        for p in sorted(race_pages, key=lambda x: x["clicks"], reverse=True)[:20]:
            print(f"  {p['page'][:45]:<45} {p['clicks']:>6} {p['impressions']:>7} {p['position']:>5.1f}")

        # New indexing detection
        if week_ago:
            prev_pages = {p["page"] for p in week_ago.get("race_pages", [])}
            new_pages = [p for p in race_pages if p["page"] not in prev_pages]
            if new_pages:
                print(f"\n  NEW race pages (not in last week's snapshot):")
                for p in new_pages:
                    print(f"    {p['page']}")

    print()


def check_alerts(today: date) -> int:
    """Check alert thresholds. Returns exit code (0=ok, 1=alerts)."""
    latest = find_nearest_snapshot(today)
    week_ago = find_nearest_snapshot(today - timedelta(days=7))

    if not latest:
        print("No snapshots found. Run --snapshot first.")
        return 0

    alerts = []
    o = latest.get("overall", {})

    if week_ago:
        prev = week_ago.get("overall", {})

        # Impression drop
        if prev.get("impressions", 0) > 0:
            drop = ((prev["impressions"] - o.get("impressions", 0)) / prev["impressions"]) * 100
            if drop > IMPRESSION_DROP_PCT:
                alerts.append(
                    f"IMPRESSION DROP: {o.get('impressions', 0):,} vs {prev['impressions']:,} "
                    f"({drop:.1f}% drop, threshold {IMPRESSION_DROP_PCT}%)"
                )

        # Position regression
        pos_change = o.get("position", 0) - prev.get("position", 0)
        if pos_change > POSITION_REGRESSION:
            alerts.append(
                f"POSITION REGRESSION: {o.get('position', 0):.1f} vs {prev.get('position', 0):.1f} "
                f"(+{pos_change:.1f} spots, threshold {POSITION_REGRESSION})"
            )

    # CTR floor
    if o.get("ctr", 0) < CTR_FLOOR and o.get("impressions", 0) > 100:
        alerts.append(
            f"LOW CTR: {o.get('ctr', 0):.2f}% (threshold {CTR_FLOOR}%)"
        )

    if alerts:
        print(f"\n{'!' * 60}")
        print(f"  GSC ALERTS — {latest['date']}")
        print(f"{'!' * 60}")
        for a in alerts:
            print(f"  \u26a0  {a}")
        print()
        return 1
    else:
        print(f"\n  GSC ALERTS — {latest['date']}: All clear")
        return 0


def main():
    parser = argparse.ArgumentParser(description="GSC Monitoring Tracker")
    parser.add_argument("--snapshot", action="store_true", help="Capture daily snapshot")
    parser.add_argument("--report", action="store_true", help="Show trend report")
    parser.add_argument("--alert", action="store_true", help="Check alert thresholds")
    parser.add_argument("--date", help="Override date (YYYY-MM-DD), default=today")
    args = parser.parse_args()

    if not any([args.snapshot, args.report, args.alert]):
        parser.print_help()
        return

    today = date.fromisoformat(args.date) if args.date else date.today()

    if args.snapshot:
        service = get_gsc_service()
        if service is None:
            print("GOOGLE_APPLICATION_CREDENTIALS not set.")
            print("\nSetup steps:")
            print("  1. Create a GCP service account with Search Console API enabled")
            print("  2. Download the JSON key file")
            print("  3. Add the service account email as a Viewer in GSC")
            print("  4. export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
            if args.report or args.alert:
                print("\nSkipping snapshot, running from existing data...\n")
            else:
                sys.exit(1)
        else:
            try:
                snapshot = fetch_snapshot(service, today)
                path = save_snapshot(snapshot)
                o = snapshot.get("overall", {})
                print(f"  Snapshot saved: {path.name}")
                print(f"  Clicks: {o.get('clicks', 0):,}  Impressions: {o.get('impressions', 0):,}  "
                      f"CTR: {o.get('ctr', 0):.2f}%  Position: {o.get('position', 0):.1f}")
                print(f"  Race pages tracked: {len(snapshot.get('race_pages', []))}")
            except Exception as e:
                print(f"  ERROR capturing snapshot: {e}")
                if not (args.report or args.alert):
                    sys.exit(1)

    if args.report:
        print_report(today)

    if args.alert:
        exit_code = check_alerts(today)
        if exit_code and not args.report:
            sys.exit(exit_code)


if __name__ == "__main__":
    main()
