#!/usr/bin/env python3
"""
Send touchpoint check-in emails to athletes.

Usage:
    # Send a specific touchpoint for a specific athlete:
    python3 scripts/send_touchpoint.py --athlete mike-wallace-20260214 --touchpoint week_1_welcome

    # Send all due touchpoints across all athletes:
    python3 scripts/send_touchpoint.py --send-due

    # Dry run (show what would be sent):
    python3 scripts/send_touchpoint.py --send-due --dry-run
"""

import argparse
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
ATHLETES_DIR = BASE_DIR / "athletes"
TEMPLATES_DIR = BASE_DIR / "templates" / "emails"


def send_touchpoint(athlete_id: str, touchpoint_id: str, dry_run: bool = False) -> bool:
    """Send a single touchpoint email for an athlete."""
    athlete_dir = ATHLETES_DIR / athlete_id
    tp_path = athlete_dir / "touchpoints.json"

    if not tp_path.exists():
        print(f"ERROR: No touchpoints.json for {athlete_id}")
        return False

    with open(tp_path) as f:
        tp_data = json.load(f)

    # Find the touchpoint
    touchpoint = None
    for tp in tp_data["touchpoints"]:
        if tp["id"] == touchpoint_id:
            touchpoint = tp
            break

    if touchpoint is None:
        print(f"ERROR: Touchpoint '{touchpoint_id}' not found for {athlete_id}")
        return False

    if touchpoint["sent"]:
        print(f"SKIP: {touchpoint_id} already sent at {touchpoint['sent_at']}")
        return True

    # Load template
    template_path = TEMPLATES_DIR / f"{touchpoint['template']}.html"
    if not template_path.exists():
        print(f"ERROR: Template not found: {template_path}")
        return False

    html_body = template_path.read_text()

    # Replace placeholders
    html_body = html_body.replace("{athlete_name}", tp_data["athlete"])
    html_body = html_body.replace("{race_name}", tp_data["race_name"])
    html_body = html_body.replace("{race_date}", tp_data["race_date"])
    html_body = html_body.replace("{plan_duration}", str(tp_data["plan_duration_weeks"]))

    if dry_run:
        print(f"DRY RUN: Would send '{touchpoint['subject']}' to {tp_data['email']}")
        return True

    # Send via Resend
    try:
        import resend
    except ImportError:
        print("ERROR: resend not installed. Run: pip install resend")
        return False

    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("ERROR: RESEND_API_KEY not set")
        return False

    resend.api_key = api_key

    result = resend.Emails.send({
        "from": "Gravel God <plans@gravelgodcycling.com>",
        "to": [tp_data["email"]],
        "subject": touchpoint["subject"],
        "html": html_body,
    })

    # Mark as sent
    touchpoint["sent"] = True
    touchpoint["sent_at"] = datetime.now().isoformat()

    with open(tp_path, "w") as f:
        json.dump(tp_data, f, indent=2)

    print(f"SENT: '{touchpoint['subject']}' to {tp_data['email']}")
    return True


def send_all_due(dry_run: bool = False):
    """Send all due touchpoints across all athletes."""
    today = date.today().isoformat()
    sent_count = 0

    if not ATHLETES_DIR.exists():
        print("No athletes directory found")
        return

    for athlete_dir in sorted(ATHLETES_DIR.iterdir()):
        if not athlete_dir.is_dir():
            continue
        tp_path = athlete_dir / "touchpoints.json"
        if not tp_path.exists():
            continue

        with open(tp_path) as f:
            tp_data = json.load(f)

        for tp in tp_data["touchpoints"]:
            if tp["sent"]:
                continue
            if tp["send_date"] <= today:
                success = send_touchpoint(athlete_dir.name, tp["id"], dry_run)
                if success:
                    sent_count += 1

    print(f"\n{'Would send' if dry_run else 'Sent'} {sent_count} touchpoint(s)")


def main():
    parser = argparse.ArgumentParser(description="Send touchpoint check-in emails")
    parser.add_argument("--athlete", help="Athlete directory ID (e.g., mike-wallace-20260214)")
    parser.add_argument("--touchpoint", help="Touchpoint ID (e.g., week_1_welcome)")
    parser.add_argument("--send-due", action="store_true", help="Send all due touchpoints")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without sending")
    args = parser.parse_args()

    if args.send_due:
        send_all_due(dry_run=args.dry_run)
    elif args.athlete and args.touchpoint:
        send_touchpoint(args.athlete, args.touchpoint, dry_run=args.dry_run)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
