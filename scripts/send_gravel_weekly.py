#!/usr/bin/env python3
"""Send the latest approved Gravel Weekly issue through the existing audience."""

from __future__ import annotations

import html
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "wordpress"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from brand_tokens import COLORS  # noqa: E402
from validate_gravel_weekly import load_public_issues  # noqa: E402

RESEND_API = "https://api.resend.com"
AUDIENCE_NAMES = ("Gravel Weekly", "Gravel TV")
FROM_ADDR = "Gravel Weekly <weekly@gravelgodcycling.com>"
ISSUE_BASE_URL = "https://gravelgodcycling.com/gravel-weekly/"
SUBSCRIBER_SOURCES = ("gravel_weekly_subscribe", "gravel_tv_subscribe")


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


def find_or_create_audience() -> str | None:
    audiences = resend("/audiences").get("data", [])
    for preferred_name in AUDIENCE_NAMES:
        for audience in audiences:
            if audience.get("name") == preferred_name:
                return audience["id"]
    return resend("/audiences", "POST", {"name": AUDIENCE_NAMES[0]}).get("id")


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


def main() -> int:
    missing = [key for key in ("RESEND_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY") if not os.environ.get(key)]
    if missing:
        print(f"Missing {missing} — skipping Gravel Weekly send")
        return 0
    issues = load_public_issues()
    if not issues:
        print("No sealed Gravel Weekly issue — refusing to send")
        return 0
    issue = issues[0]
    try:
        subscribers = fetch_subscribers()
        if not subscribers:
            print("No Gravel Weekly subscribers — nothing to send")
            return 0
        audience_id = find_or_create_audience()
        if not audience_id:
            print("Could not resolve the existing publication audience — skipping")
            return 0
        for email_address in subscribers:
            try:
                resend(f"/audiences/{audience_id}/contacts", "POST", {"email": email_address})
            except Exception:
                pass
        current = next((story for story in issue["stories"] if story["candidateId"] == issue.get("currentThingStoryId")), None)
        subject = f"Gravel Weekly #{issue['issueNumber']:03d}"
        if current:
            subject += f": {current['headline']}"
        elif issue.get("quietIssue"):
            subject += f": {issue['quietIssue']['headline']}"
        broadcast = resend("/broadcasts", "POST", {
            "audience_id": audience_id,
            "from": FROM_ADDR,
            "subject": subject,
            "html": build_email_html(issue),
        })
        broadcast_id = broadcast.get("id")
        if not broadcast_id:
            raise RuntimeError("broadcast creation returned no id")
        resend(f"/broadcasts/{broadcast_id}/send", "POST", {})
        print(f"Sent Gravel Weekly #{issue['issueNumber']:03d} to {len(subscribers)} subscriber(s)")
    except Exception as exc:
        print(f"Gravel Weekly send failed softly: {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
