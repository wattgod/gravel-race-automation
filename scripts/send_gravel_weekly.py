#!/usr/bin/env python3
"""Send the latest approved Gravel Weekly issue through the existing audience."""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from brand_tokens import COLORS  # noqa: E402
from validate_gravel_weekly import load_public_issues  # noqa: E402

RESEND_API = "https://api.resend.com"
SEGMENT_NAMES = ("Gravel Weekly", "Gravel TV")
FROM_ADDR = "Gravel Weekly <weekly@gravelgodcycling.com>"
ISSUE_BASE_URL = "https://gravelgodcycling.com/gravel-weekly/"
SUBSCRIBER_SOURCES = ("gravel_weekly_subscribe", "gravel_tv_subscribe")
ACTIVE_BROADCAST_STATUSES = frozenset({"queued", "scheduled", "sent"})


def _req(url: str, method: str = "GET", body: dict | None = None,
         headers: dict | None = None) -> dict:
    request = urllib.request.Request(
        url,
        method=method,
        headers={"Content-Type": "application/json", **(headers or {})},
        data=json.dumps(body).encode() if body is not None else None,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read().decode()
        return json.loads(raw) if raw.strip() else {}


def resend(path: str, method: str = "GET", body: dict | None = None) -> dict:
    return _req(
        f"{RESEND_API}{path}", method, body,
        {"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
    )


def fetch_subscribers() -> list[str]:
    """Union the new source with the legacy publication audience."""
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    subscribers: set[str] = set()
    for source in SUBSCRIBER_SOURCES:
        query = urllib.parse.urlencode({"select": "contact_email", "source": f"eq.{source}"})
        rows = _req(
            f"{os.environ['SUPABASE_URL']}/rest/v1/gg_sequence_enrollments?{query}",
            headers=headers,
        )
        subscribers.update(
            row["contact_email"].strip().lower()
            for row in rows if row.get("contact_email")
        )
    return sorted(subscribers)


def find_or_create_segment() -> str | None:
    segments = resend("/segments").get("data", [])
    if not isinstance(segments, list):
        raise RuntimeError("Resend segment list returned an invalid response")
    for preferred_name in SEGMENT_NAMES:
        for segment in segments:
            if segment.get("name") == preferred_name:
                return segment["id"]
    return resend("/segments", "POST", {"name": SEGMENT_NAMES[0]}).get("id")


def ensure_segment_contact(segment_id: str, email_address: str) -> bool:
    """Ensure segment membership without changing an existing unsubscribe state."""
    encoded_email = urllib.parse.quote(email_address, safe="")
    try:
        existing = resend(f"/contacts/{encoded_email}")
        if not existing.get("id") and existing.get("email") != email_address:
            raise RuntimeError(f"Resend returned an invalid contact for {email_address}")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        created = resend(
            "/contacts",
            "POST",
            {"email": email_address, "segments": [{"id": segment_id}]},
        )
        if not created.get("id"):
            raise RuntimeError(f"Resend contact creation returned no id for {email_address}")
        return True

    memberships = resend(f"/contacts/{encoded_email}/segments").get("data", [])
    if not isinstance(memberships, list):
        raise RuntimeError(f"Resend returned invalid segment membership for {email_address}")
    if any(item.get("id") == segment_id for item in memberships if isinstance(item, dict)):
        return False
    added = resend(
        f"/contacts/{encoded_email}/segments/{segment_id}",
        "POST",
        {},
    )
    if added.get("id") != segment_id:
        raise RuntimeError(f"Resend did not confirm segment membership for {email_address}")
    return True


def broadcast_name(issue: dict) -> str:
    """Bind a Resend broadcast to one immutable published issue snapshot."""
    return (
        f"Gravel Weekly #{issue['issueNumber']:03d} · "
        f"{issue['publicationDate']} · {issue['contentHash']}"
    )


def find_existing_broadcast(name: str) -> dict | None:
    """Find a prior API broadcast by its content-hash-bound internal name."""
    summaries = resend("/broadcasts").get("data", [])
    if not isinstance(summaries, list):
        raise RuntimeError("Resend broadcast list returned an invalid response")
    for summary in summaries:
        broadcast_id = summary.get("id") if isinstance(summary, dict) else None
        if not broadcast_id:
            continue
        detail = resend(f"/broadcasts/{broadcast_id}")
        if detail.get("name") == name:
            return detail
    return None


def send_broadcast_once(issue: dict, segment_id: str, subject: str, email_html: str) -> dict:
    """Start exactly one broadcast for an immutable issue, safe across workflow reruns."""
    name = broadcast_name(issue)
    existing = find_existing_broadcast(name)
    if existing:
        status = existing.get("status")
        broadcast_id = existing.get("id")
        if not broadcast_id:
            raise RuntimeError("Existing Resend broadcast has no id")
        if status in ACTIVE_BROADCAST_STATUSES:
            return {"id": broadcast_id, "status": status, "reused": True}
        if status == "draft":
            resend(f"/broadcasts/{broadcast_id}/send", "POST", {})
            return {"id": broadcast_id, "status": "queued", "reused": True}
        raise RuntimeError(f"Existing Resend broadcast has unsafe status: {status!r}")

    created = resend("/broadcasts", "POST", {
        "segment_id": segment_id,
        "from": FROM_ADDR,
        "name": name,
        "subject": subject,
        "html": email_html,
        "send": True,
    })
    broadcast_id = created.get("id")
    if not broadcast_id:
        raise RuntimeError("Resend create-and-send returned no broadcast id")
    return {"id": broadcast_id, "status": "queued", "reused": False}


def _paragraphs(value: str) -> str:
    return "".join(
        f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;">{html.escape(paragraph.strip())}</p>'
        for paragraph in value.split("\n\n") if paragraph.strip()
    )


def build_email_html(issue: dict) -> str:
    current_id = issue.get("currentThingStoryId")
    current = next((story for story in issue["stories"] if story["candidateId"] == current_id), None)
    stories = [current] if current else []
    stories.extend(story for story in issue["stories"] if story is not current)
    story_html = ""
    for index, story in enumerate(stories):
        label = "THE CURRENT THING" if index == 0 and current else story["storyKind"].replace("_", " ").upper()
        story_html += f'''<div style="border-top:3px solid {COLORS['near_black']};padding:20px 0;">
      <div style="font:700 12px monospace;letter-spacing:2px;color:{COLORS['teal']};">{html.escape(label)}</div>
      <h2 style="font:700 30px Georgia,serif;line-height:1.05;margin:8px 0 12px;">{html.escape(story['headline'])}</h2>
      {_paragraphs(story['take'])}
    </div>'''
    quiet = issue.get("quietIssue")
    if quiet:
        story_html = f'''<div style="border-top:3px solid {COLORS['near_black']};background:{COLORS['gold']};padding:24px 18px;">
      <div style="font:700 12px monospace;letter-spacing:2px;">THE QUIET WEEK</div>
      <h2 style="font:700 30px Georgia,serif;line-height:1.05;margin:8px 0 12px;">{html.escape(quiet['headline'])}</h2>
      {_paragraphs(quiet['note'])}
    </div>'''
    issue_url = f"{ISSUE_BASE_URL}{issue['slug']}/"
    return f'''<div style="max-width:620px;margin:0 auto;color:{COLORS['near_black']};font-family:monospace;">
  <div style="background:{COLORS['white']};border:4px solid {COLORS['near_black']};padding:20px;">
    <div style="font-size:12px;font-weight:700;letter-spacing:2px;">ISSUE #{issue['issueNumber']:03d} · {html.escape(issue['publicationDate'])}</div>
    <div style="font-size:48px;font-weight:700;letter-spacing:-4px;line-height:.9;margin:14px 0;">GRAVEL <span style="color:{COLORS['teal']};">WEEKLY</span></div>
    <div style="display:inline-block;background:{COLORS['gold']};border:3px solid {COLORS['near_black']};padding:6px 10px;font-weight:700;">THE PEOPLE, RACES, MONEY &amp; BAD IDEAS MOVING GRAVEL</div>
    {story_html}
    <p style="margin:20px 0 0;"><a href="{issue_url}" style="display:inline-block;background:{COLORS['gold']};color:{COLORS['near_black']};border:3px solid {COLORS['near_black']};padding:12px 20px;font-weight:700;text-decoration:none;">READ THE FULL ISSUE &rarr;</a></p>
  </div>
  <p style="font-size:11px;color:{COLORS['secondary_brown']};margin-top:14px;">You subscribed to Gravel Weekly or its predecessor, Gravel TV, at gravelgodcycling.com. <a href="{{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}">Unsubscribe</a>.</p>
</div>'''


def select_issue(issues: list[dict], issue_date: str | None) -> dict:
    if not issues:
        raise RuntimeError("No sealed Gravel Weekly issue is available")
    if issue_date is None:
        return issues[0]
    selected = next(
        (issue for issue in issues if issue["publicationDate"] == issue_date),
        None,
    )
    if selected is None:
        raise RuntimeError(f"No sealed Gravel Weekly issue exists for {issue_date}")
    return selected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--issue-date",
        help="Exact sealed issue date to send (YYYY-MM-DD); defaults to latest",
    )
    args = parser.parse_args(argv)
    missing = [key for key in ("RESEND_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY") if not os.environ.get(key)]
    if missing:
        print(f"Missing {missing} — refusing to claim Gravel Weekly was sent", file=sys.stderr)
        return 1
    try:
        issue = select_issue(load_public_issues(), args.issue_date)
    except RuntimeError as exc:
        print(f"{exc} — refusing to send", file=sys.stderr)
        return 1
    try:
        subscribers = fetch_subscribers()
        if not subscribers:
            raise RuntimeError("No Gravel Weekly subscribers were found")
        segment_id = find_or_create_segment()
        if not segment_id:
            raise RuntimeError("Could not resolve the existing publication segment")
        added_memberships = sum(
            ensure_segment_contact(segment_id, email_address)
            for email_address in subscribers
        )
        current = next((story for story in issue["stories"] if story["candidateId"] == issue.get("currentThingStoryId")), None)
        subject = f"Gravel Weekly #{issue['issueNumber']:03d}"
        if current:
            subject += f": {current['headline']}"
        elif issue.get("quietIssue"):
            subject += f": {issue['quietIssue']['headline']}"
        receipt = send_broadcast_once(issue, segment_id, subject, build_email_html(issue))
        action = "Verified existing" if receipt["reused"] else "Started"
        print(
            f"{action} Gravel Weekly #{issue['issueNumber']:03d} broadcast "
            f"{receipt['id']} ({receipt['status']}) for {len(subscribers)} subscriber(s); "
            f"{added_memberships} new segment membership(s)"
        )
    except Exception as exc:
        print(f"Gravel Weekly send failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
