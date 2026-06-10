#!/usr/bin/env python3
"""
Send the weekly Gravel TV issue to subscribers via Resend.

Why Resend: the SendGrid trial died 2026-04-10 and every other email leg
of the business already runs on Resend (Mission Control sequences,
Railway transactional). Subscribers are captured by the lead worker →
Mission Control webhook → Supabase gg_sequence_enrollments with
source = 'gravel_tv_subscribe'.

Flow: Supabase query → sync into the 'Gravel TV' Resend Audience
(Resend dedupes + manages unsubscribes) → create + send a Broadcast.

Fail-soft by design: any error logs and exits 0 — the page deploy must
never be hostage to the email leg.

Env: RESEND_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
     (each missing piece skips politely)
"""

import json
import os
import sys
import urllib.request
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DESK_NOTE = PROJECT_ROOT / 'web' / 'gravel-tv-desk-note.md'

RESEND_API = 'https://api.resend.com'
AUDIENCE_NAME = 'Gravel TV'
FROM_ADDR = 'Gravel TV <broadcast@gravelgodcycling.com>'
ISSUE_URL = 'https://gravelgodcycling.com/gravel-tv/'


def _req(url: str, method: str = 'GET', body: dict | None = None,
         headers: dict | None = None) -> dict:
    req = urllib.request.Request(
        url, method=method,
        headers={'Content-Type': 'application/json', **(headers or {})},
        data=json.dumps(body).encode() if body is not None else None,
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw.strip() else {}


def resend(path: str, method: str = 'GET', body: dict | None = None) -> dict:
    return _req(f'{RESEND_API}{path}', method, body,
                {'Authorization': f'Bearer {os.environ["RESEND_API_KEY"]}'})


def fetch_subscribers() -> list[str]:
    """Distinct gravel_tv_subscribe emails from Mission Control's Supabase."""
    url = (f"{os.environ['SUPABASE_URL']}/rest/v1/gg_sequence_enrollments"
           f"?select=contact_email&source=eq.gravel_tv_subscribe")
    key = os.environ['SUPABASE_SERVICE_ROLE_KEY']
    rows = _req(url, headers={'apikey': key, 'Authorization': f'Bearer {key}'})
    return sorted({r['contact_email'].strip().lower()
                   for r in rows if r.get('contact_email')})


def find_or_create_audience() -> str | None:
    audiences = resend('/audiences').get('data', [])
    for a in audiences:
        if a.get('name') == AUDIENCE_NAME:
            return a['id']
    created = resend('/audiences', 'POST', {'name': AUDIENCE_NAME})
    return created.get('id')


def build_email_html(note_text: str) -> str:
    paras = ''.join(
        f'<p style="margin:0 0 14px;font-size:16px;line-height:1.6;">{p.strip()}</p>'
        for p in note_text.split('\n\n') if p.strip() and not p.startswith('#'))
    return f'''<div style="max-width:560px;margin:0 auto;font-family:monospace;color:#000;">
  <div style="background:#178079;border:4px solid #000;padding:24px;text-align:center;">
    <span style="font-size:2rem;font-weight:700;color:#f5efe6;">GRAVEL<span style="background:#000;color:#B7950B;padding:0 6px;">TV</span></span>
  </div>
  <div style="border:3px solid #000;border-top:none;padding:20px;background:#fff;">
    {paras}
    <p style="margin:20px 0 0;">
      <a href="{ISSUE_URL}" style="display:inline-block;background:#B7950B;color:#000;border:3px solid #000;padding:12px 22px;font-weight:700;text-decoration:none;">WATCH THIS WEEK&rsquo;S BROADCAST &rarr;</a>
    </p>
  </div>
  <p style="font-size:11px;color:#777;margin-top:14px;">You tuned in at gravelgodcycling.com.
    <a href="{{{{{{RESEND_UNSUBSCRIBE_URL}}}}}}">Change the channel</a>.</p>
</div>'''


def main() -> int:
    missing = [k for k in ('RESEND_API_KEY', 'SUPABASE_URL',
                           'SUPABASE_SERVICE_ROLE_KEY') if not os.environ.get(k)]
    if missing:
        print(f'Missing {missing} — skipping list send (page still deploys)')
        return 0
    try:
        subs = fetch_subscribers()
        if not subs:
            print('No gravel_tv_subscribe contacts yet — nothing to send')
            return 0
        print(f'{len(subs)} subscriber(s)')

        audience_id = find_or_create_audience()
        if not audience_id:
            print('Could not resolve Resend audience — skipping')
            return 0

        # Sync (Resend dedupes by email; unsubscribed stay suppressed)
        for email in subs:
            try:
                resend(f'/audiences/{audience_id}/contacts', 'POST',
                       {'email': email})
            except Exception:
                pass  # already exists / malformed — move on

        note = DESK_NOTE.read_text() if DESK_NOTE.exists() else ''
        today = date.today()
        broadcast = resend('/broadcasts', 'POST', {
            'audience_id': audience_id,
            'from': FROM_ADDR,
            'subject': f'Gravel TV: this week in gravel ({today.strftime("%b %-d")})',
            'html': build_email_html(note),
        })
        b_id = broadcast.get('id')
        if b_id:
            resend(f'/broadcasts/{b_id}/send', 'POST', {})
            print(f'Broadcast sent (id {b_id}) to audience {audience_id}')
        else:
            print(f'Broadcast creation returned no id: {broadcast}')
    except Exception as e:
        print(f'List send failed softly: {e}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
