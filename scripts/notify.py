#!/usr/bin/env python3
"""
Send notification to Slack/Discord when race processing completes.
"""

import argparse
import os
import requests
import json


def notify_slack(race_name: str, status: str, webhook_url: str):
    """Send Slack notification."""
    message = {
        "text": f"Race Processing: {race_name}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Race Processing Complete*\n\n*Race:* {race_name}\n*Status:* {status}"
                }
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()
        print(f"✓ Notification sent to Slack")
    except Exception as e:
        print(f"⚠️  Failed to send Slack notification: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--race", required=True)
    parser.add_argument("--status", required=True)
    args = parser.parse_args()
    
    webhook = os.environ.get("SLACK_WEBHOOK")
    if webhook:
        notify_slack(args.race, args.status, webhook)
    else:
        print("⚠️  SLACK_WEBHOOK not set, skipping notification")

