#!/usr/bin/env python3
"""Send XC Ski Labs Weekly: a review preview, or the approved broadcast.

    --next-issue-number            print the next issue number (counts sent broadcasts)
    --preview  STAGE_DIR           email the staged issue to the review inbox only
    --broadcast STAGE_DIR --approved-hash HASH
                                   send the staged issue to every XC subscriber, once

A broadcast needs the content hash Matti approved; a staged issue whose hash
differs is refused. Subscribers are Mission Control enrollments for brand
xcskilabs carrying newsletter_opt_in_at (set by the xcskilabs.com sign-up),
minus everyone who unsubscribed through Mission Control. Addresses are never
printed: this runs in a public repository's Actions log.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))

from send_gravel_weekly import (  # noqa: E402
    _req, ensure_segment_contact, fetch_opted_out, remove_segment_contact, resend,
)
from xc_weekly_issue import IssueError, render_email_html, validate_issue  # noqa: E402

SEGMENT_NAME = "XC Ski Labs Weekly"
FROM_ADDR = "XC Ski Labs Weekly <weekly@xcskilabs.com>"
REPLY_TO = "gravelgodcoaching@gmail.com"
REVIEW_TO = os.environ.get("XC_WEEKLY_REVIEW_EMAIL", "gravelgodcoaching@gmail.com")
BROADCAST_PREFIX = "XC Ski Labs Weekly No. "
ACTIVE_STATUSES = frozenset({"queued", "scheduled", "sent"})
PAGE_SIZE = 1000


def load_stage(stage_dir: Path) -> tuple[dict, dict]:
    issue = json.loads((stage_dir / "issue.json").read_text())
    evidence = json.loads((stage_dir / "evidence.json").read_text())
    return validate_issue(issue, evidence), evidence


def broadcast_name(issue: dict) -> str:
    return f"{BROADCAST_PREFIX}{issue['issueNumber']:03d} · {issue['issueDate']} · {issue['contentHash']}"


def list_broadcasts() -> list[dict]:
    summaries = resend("/broadcasts").get("data", [])
    if not isinstance(summaries, list):
        raise RuntimeError("Resend broadcast list returned an invalid response")
    return [s for s in summaries if isinstance(s, dict)]


def next_issue_number() -> int:
    """One more than the highest XC Weekly number already queued or sent."""
    highest = 0
    for summary in list_broadcasts():
        name = summary.get("name") or ""
        if not name.startswith(BROADCAST_PREFIX):
            continue
        if summary.get("status") not in ACTIVE_STATUSES:
            continue
        try:
            highest = max(highest, int(name[len(BROADCAST_PREFIX):].split(" ", 1)[0]))
        except ValueError:
            continue
    return highest + 1


def fetch_subscribers() -> list[str]:
    """Every address with an XC newsletter opt-in on record, all pages."""
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    emails: set[str] = set()
    offset = 0
    while True:
        query = urllib.parse.urlencode({
            "select": "contact_email",
            "source_data->>brand": "eq.xcskilabs",
            "source_data->>newsletter_opt_in_at": "not.is.null",
            "order": "id", "limit": PAGE_SIZE, "offset": offset,
        })
        rows = _req(f"{os.environ['SUPABASE_URL']}/rest/v1/gg_sequence_enrollments?{query}",
                    headers=headers)
        if not rows:
            return sorted(emails)
        emails.update(r["contact_email"].strip().lower() for r in rows if r.get("contact_email"))
        offset += len(rows)


def find_or_create_segment() -> str:
    segments = resend("/segments").get("data", [])
    if not isinstance(segments, list):
        raise RuntimeError("Resend segment list returned an invalid response")
    for segment in segments:
        if segment.get("name") == SEGMENT_NAME:
            return segment["id"]
    created = resend("/segments", "POST", {"name": SEGMENT_NAME}).get("id")
    if not created:
        raise RuntimeError("Resend did not create the XC Ski Labs Weekly segment")
    return created


def send_preview(issue: dict) -> str:
    banner = (f"PREVIEW FOR REVIEW · No. {issue['issueNumber']:03d} · hash {issue['contentHash']} · "
              "not sent to subscribers")
    result = resend("/emails", "POST", {
        "from": FROM_ADDR,
        "to": [REVIEW_TO],
        "reply_to": REPLY_TO,
        "subject": f"[Preview] {issue['subject']}",
        "html": render_email_html(issue, preview_banner=banner),
    })
    if not result.get("id"):
        raise RuntimeError("Resend returned no id for the preview email")
    return result["id"]


def send_broadcast_once(issue: dict, segment_id: str) -> dict:
    name = broadcast_name(issue)
    for summary in list_broadcasts():
        if summary.get("name") != name:
            continue
        status, broadcast_id = summary.get("status"), summary.get("id")
        if status in ACTIVE_STATUSES:
            return {"id": broadcast_id, "status": status, "reused": True}
        if status == "draft":
            resend(f"/broadcasts/{broadcast_id}/send", "POST", {})
            return {"id": broadcast_id, "status": "queued", "reused": True}
        raise RuntimeError(f"Existing broadcast has unsafe status {status!r}")
    created = resend("/broadcasts", "POST", {
        "segment_id": segment_id,
        "from": FROM_ADDR,
        "reply_to": REPLY_TO,
        "name": name,
        "subject": issue["subject"],
        "html": render_email_html(issue),
        "send": True,
    })
    if not created.get("id"):
        raise RuntimeError("Resend create-and-send returned no broadcast id")
    return {"id": created["id"], "status": "queued", "reused": False}


def broadcast(issue: dict, approved_hash: str) -> str:
    if issue["contentHash"] != approved_hash:
        raise RuntimeError(f"staged hash {issue['contentHash']} is not the approved hash {approved_hash}")
    opted_out = fetch_opted_out()
    subscribers = [e for e in fetch_subscribers() if e not in opted_out]
    if not subscribers:
        raise RuntimeError("No XC Ski Labs Weekly subscribers were found")
    segment_id = find_or_create_segment()
    removed = sum(remove_segment_contact(segment_id, e) for e in sorted(opted_out))
    added = sum(ensure_segment_contact(segment_id, e) for e in subscribers)
    receipt = send_broadcast_once(issue, segment_id)
    action = "Verified existing" if receipt["reused"] else "Started"
    return (f"{action} XC Ski Labs Weekly No. {issue['issueNumber']:03d} broadcast {receipt['id']} "
            f"({receipt['status']}) for {len(subscribers)} subscriber(s); {added} new segment "
            f"membership(s); {removed} opted-out contact(s) removed")


_ADDRESS = re.compile(r"[^\s\"'/?&=<>@]+(?:@|%40)[^\s\"'/?&=<>]+")


def _redact(text: str) -> str:
    """Strip anything address-shaped: this log is public."""
    return _ADDRESS.sub("[address]", text)


def _error_body(exc: urllib.error.HTTPError) -> str:
    """The API's own error reason (JSON from Resend or Supabase), addresses removed."""
    try:
        return _redact(exc.read().decode(errors="replace")[:300])
    except Exception:  # noqa: BLE001 - a body we cannot read is reported as such
        return "(no response body)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--next-issue-number", action="store_true")
    mode.add_argument("--preview", type=Path, metavar="STAGE_DIR")
    mode.add_argument("--broadcast", type=Path, metavar="STAGE_DIR")
    parser.add_argument("--approved-hash")
    args = parser.parse_args(argv)
    needed = ["RESEND_API_KEY"]
    if args.broadcast:
        needed += ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
        if not args.approved_hash:
            print("--broadcast needs --approved-hash; refusing to send", file=sys.stderr)
            return 1
    missing = [k for k in needed if not os.environ.get(k)]
    if missing:
        print(f"Missing {missing}; refusing to claim XC Weekly was sent", file=sys.stderr)
        return 1
    try:
        if args.next_issue_number:
            print(next_issue_number())
            return 0
        issue, _ = load_stage(args.preview or args.broadcast)
        if args.preview:
            print(f"Preview of No. {issue['issueNumber']:03d} sent to the review inbox (id {send_preview(issue)})")
        else:
            print(broadcast(issue, args.approved_hash))
    except urllib.error.HTTPError as exc:
        print(f"XC Weekly send failed: {exc} on {_redact(exc.url or '')}: {_error_body(exc)}",
              file=sys.stderr)
        return 1
    except (IssueError, RuntimeError, urllib.error.URLError, KeyError) as exc:
        print(f"XC Weekly send failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
