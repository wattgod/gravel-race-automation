#!/usr/bin/env python3
"""Uptime check for the three brand sites, the checkout API and intake Workers.

Run every 10 minutes by .github/workflows/uptime.yml. Each target is tried up
to three times, 30 s apart, before it counts as down.

State lives in one open GitHub issue labelled "uptime":
  - something down, no open issue -> open one and email the Gmail
  - something down, issue open    -> update the issue body only (no repeat email)
  - all up, issue open            -> close it and email "recovered"
So an outage sends exactly two emails: when it starts and when it ends.

Needs GH_TOKEN + GITHUB_REPOSITORY (Actions provides both) for the issue, and
RESEND_API_KEY for the email. Without RESEND_API_KEY the email step fails the
run loudly; it is never skipped silently.

Usage:
    python3 scripts/uptime_check.py            # check, manage issue, email
    python3 scripts/uptime_check.py --dry-run  # check and print only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

ALERT_TO = "gravelgodcoaching@gmail.com"
ALERT_FROM = "Gravel God Uptime <noreply@gravelgodcycling.com>"
LABEL = "uptime"
UA = "GravelGodUptime/1.0 (+https://gravelgodcycling.com/)"  # SiteGround resets UAs that claim to be a browser or "compatible; bot"

# name, url, method, expected status, text the body must contain (or None).
# The three SiteGround homes are the only targets where a bot challenge can
# be read as "unknown" (see SITEGROUND_PAGES); for the APIs and Workers a
# 403/429 is an outage like any other.
SITEGROUND_PAGES = {"Gravel God home", "Roadie Labs home", "XC Ski Labs home"}
TARGETS = [
    ("Gravel God home", "https://gravelgodcycling.com/", "GET", 200, "Gravel God"),
    ("Roadie Labs home", "https://roadielabs.com/", "GET", 200, "Roadie Labs"),
    ("XC Ski Labs home", "https://xcskilabs.com/", "GET", 200, "XC Ski Labs"),
    ("Checkout API /health",
     "https://athlete-custom-training-plan-pipeline-production.up.railway.app/health",
     "GET", 200, '"status":"ok"'),
    ("Mission Control /health", "https://athlete-profiles-production.up.railway.app/health",
     "GET", 200, '"status":"ok"'),
    ("coaching-intake Worker", "https://coaching-intake.gravelgodcoaching.workers.dev/",
     "OPTIONS", 204, None),
    ("fueling-lead-intake Worker", "https://fueling-lead-intake.gravelgodcoaching.workers.dev/",
     "OPTIONS", 204, None),
    ("review-intake Worker", "https://review-intake.gravelgodcoaching.workers.dev/",
     "OPTIONS", 204, None),
]


# SiteGround sometimes answers a datacenter IP (like a GitHub runner) with a
# bot challenge. That says nothing about whether the site is up, so it
# counts as "unknown": never an alert, never a recovery.
CHALLENGE_STATUSES = {202, 403, 429}


def probe(url: str, method: str, expect: int, marker: str | None,
          challengeable: bool = False) -> tuple[str, str]:
    """('up' | 'down' | 'unknown', detail)."""
    headers = {"User-Agent": UA}
    if method == "OPTIONS":
        headers.update({"Origin": "https://gravelgodcycling.com",
                        "Access-Control-Request-Method": "POST"})
    req = urllib.request.Request(url, method=method, headers=headers)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.status
            body = resp.read(400_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, body = e.code, ""
    except Exception as e:  # timeouts, DNS, TLS, resets
        return "down", f"no response ({type(e).__name__})"
    took = time.monotonic() - started
    if status != expect and challengeable and status in CHALLENGE_STATUSES:
        return "unknown", f"HTTP {status} (bot challenge to this checker, not an outage)"
    if status != expect:
        return "down", f"HTTP {status}, expected {expect}"
    if marker and marker.replace(" ", "") not in body.replace(" ", ""):
        return "down", f"HTTP {status} but the page is missing {marker!r}"
    return "up", f"HTTP {status} in {took:.1f}s"


def check(target, tries: int = 3, gap: float = 30.0, sleep=time.sleep,
          probe_fn=None) -> tuple[str, str]:
    """Up as soon as one try is up; otherwise the last try's state."""
    name, url, method, expect, marker = target
    probe_fn = probe_fn or probe
    state, detail = "down", ""
    for attempt in range(tries):
        state, detail = probe_fn(url, method, expect, marker, name in SITEGROUND_PAGES)
        if state == "up":
            return state, detail
        if attempt < tries - 1:
            sleep(gap)
    return state, detail


def decide(states: list[str], issue_open: bool) -> str:
    """'alert' | 'update' | 'recover' | 'none'."""
    if "down" in states:
        return "update" if issue_open else "alert"
    if issue_open and all(st == "up" for st in states):
        return "recover"
    return "none"


def _gh(method: str, path: str, payload: dict | None = None):
    repo = os.environ["GITHUB_REPOSITORY"]
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}", method=method,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {os.environ['GH_TOKEN']}",
                 "Accept": "application/vnd.github+json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read() or b"null")


def email(subject: str, text: str) -> None:
    key = os.environ.get("RESEND_API_KEY", "")
    if not key:
        raise SystemExit("RESEND_API_KEY is not set; the uptime alert could not be emailed")
    req = urllib.request.Request(
        "https://api.resend.com/emails", method="POST",
        data=json.dumps({"from": ALERT_FROM, "to": [ALERT_TO],
                         "subject": subject, "text": text}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status >= 300:
            raise SystemExit(f"Resend answered {resp.status}")


def report(results: list[tuple[str, str, str, str]]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Checked {now}.", ""]
    for name, url, state, detail in results:
        lines.append(f"- {state.upper():7} {name}: {detail} ({url})")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # In parallel, so even if every target needs all three tries the run
    # takes about a minute, well inside the workflow timeout.
    with ThreadPoolExecutor(max_workers=len(TARGETS)) as pool:
        checked = list(pool.map(check, TARGETS))
    results = [(t[0], t[1], st, d) for t, (st, d) in zip(TARGETS, checked)]
    body = report(results)
    print(body)
    down = [r[0] for r in results if r[2] == "down"]
    if args.dry_run:
        return 1 if down else 0

    open_issues = _gh("GET", f"/issues?state=open&labels={LABEL}&per_page=5")
    issue = open_issues[0] if open_issues else None
    action = decide([r[2] for r in results], issue is not None)

    # Email first, then change the issue: if the email fails, the issue state
    # is unchanged and the next run tries the email again.
    if action == "alert":
        title = "Uptime: " + ", ".join(down) + " down"
        email(title, body + "\n\nThe uptime check emails again when everything is back.")
        _gh("POST", "/issues", {"title": title, "body": body, "labels": [LABEL]})
    elif action == "update":
        title = "Uptime: " + ", ".join(down) + " down"
        _gh("PATCH", f"/issues/{issue['number']}", {"title": title, "body": body})
    elif action == "recover":
        email("Uptime: everything is back up", body)
        _gh("POST", f"/issues/{issue['number']}/comments", {"body": "Recovered.\n\n" + body})
        _gh("PATCH", f"/issues/{issue['number']}", {"state": "closed"})
    # Exit 0 once the alert is handled: a failing run would also make GitHub
    # email its own failure notice every 10 minutes.
    return 0


if __name__ == "__main__":
    sys.exit(main())
