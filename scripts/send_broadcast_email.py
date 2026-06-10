#!/usr/bin/env python3
"""
Send the weekly Gravel TV issue to subscribers via SendGrid.

Subscribers arrive through the lead-intake worker into the SendGrid
marketing list with custom field latest_source = 'gravel_tv_subscribe'.
This script find-or-creates a segment on that field and fires a Single
Send pointing readers at the live issue.

Fail-soft by design: any error logs and exits 0 — the broadcast page
deploy must never be hostage to the email leg.

Env: SENDGRID_API_KEY (skips politely if absent)
"""

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DESK_NOTE = PROJECT_ROOT / 'web' / 'gravel-tv-desk-note.md'

API = 'https://api.sendgrid.com/v3'
SEGMENT_NAME = 'Gravel TV Subscribers'
SOURCE_FIELD = 'w1_T'  # latest_source custom field (see worker wrangler.toml)
SOURCE_VALUE = 'gravel_tv_subscribe'
FROM_EMAIL = 'broadcast@gravelgodcycling.com'
FROM_NAME = 'Gravel TV'


def api(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(
        f'{API}{path}',
        method=method,
        headers={
            'Authorization': f'Bearer {os.environ["SENDGRID_API_KEY"]}',
            'Content-Type': 'application/json',
        },
        data=json.dumps(body).encode() if body else None,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw.strip() else {}


def find_or_create_segment() -> str | None:
    segments = api('GET', '/marketing/segments/2.0').get('results', [])
    for s in segments:
        if s.get('name') == SEGMENT_NAME:
            return s['id']
    created = api('POST', '/marketing/segments/2.0', {
        'name': SEGMENT_NAME,
        'query_dsl': f"{SOURCE_FIELD} = '{SOURCE_VALUE}'",
    })
    return created.get('id')


def build_email_html(note_text: str, issue_url: str) -> str:
    paras = ''.join(f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;">{p.strip()}</p>'
                    for p in note_text.split('\n\n') if p.strip() and not p.startswith('#'))
    return f'''<div style="max-width:560px;margin:0 auto;font-family:monospace;color:#000;">
  <div style="background:#178079;border:4px solid #000;padding:24px;text-align:center;">
    <span style="font-size:2rem;font-weight:700;color:#f5efe6;">GRAVEL<span style="background:#000;color:#B7950B;padding:0 6px;">TV</span></span>
  </div>
  <div style="border:3px solid #000;border-top:none;padding:20px;background:#fff;">
    {paras}
    <p style="margin:20px 0 0;">
      <a href="{issue_url}" style="display:inline-block;background:#B7950B;color:#000;border:3px solid #000;padding:12px 22px;font-weight:700;text-decoration:none;">WATCH THIS WEEK&rsquo;S BROADCAST &rarr;</a>
    </p>
  </div>
  <p style="font-size:11px;color:#777;margin-top:14px;">You tuned in at gravelgodcycling.com. <a href="{{{{unsubscribe}}}}">Change the channel</a>.</p>
</div>'''


def main() -> int:
    if not os.environ.get('SENDGRID_API_KEY'):
        print('SENDGRID_API_KEY not set — skipping list send (page still deploys)')
        return 0
    try:
        note = DESK_NOTE.read_text() if DESK_NOTE.exists() else ''
        issue_url = 'https://gravelgodcycling.com/gravel-tv/'
        seg_id = find_or_create_segment()
        if not seg_id:
            print('Could not resolve segment — skipping send')
            return 0
        today = date.today()
        single_send = api('POST', '/marketing/singlesends', {
            'name': f'Gravel TV — {today.isoformat()}',
            'send_to': {'segment_ids': [seg_id]},
            'email_config': {
                'subject': f'Gravel TV: this week in gravel ({today.strftime("%b %-d")})',
                'html_content': build_email_html(note, issue_url),
                'sender_id': None,
                'suppression_group_id': None,
            },
        })
        ss_id = single_send.get('id')
        if ss_id:
            api('PUT', f'/marketing/singlesends/{ss_id}/schedule', {'send_at': 'now'})
            print(f'Broadcast email scheduled (single send {ss_id})')
        else:
            print(f'Single send creation returned no id: {single_send}')
    except Exception as e:
        print(f'List send failed softly: {e}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
