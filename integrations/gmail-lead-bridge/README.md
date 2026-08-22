# Gmail Lead Bridge

Account-local relay between `gravelgodcoaching@gmail.com` and Mission Control.
It runs every five minutes, reads only correspondents Mission Control identifies
as open leads, and syncs their Gmail threads. It can create a Gmail reply draft
only after a suggestion is explicitly marked `approved_for_gmail`. It never
sends, archives, trashes, labels, or marks messages read.

## Install

1. Apply `supabase/migrations/20260822000001_gmail_lead_reply_loop.sql` before
   deploying the matching Mission Control code.
2. Create a standalone Apps Script project while signed into
   `gravelgodcoaching@gmail.com`.
3. Copy `Code.gs` and `appsscript.json` into the project.
4. Set Script Properties:
   - `MISSION_CONTROL_URL`: production Mission Control origin, no trailing slash.
   - `WEBHOOK_SECRET`: the existing Mission Control webhook secret.
   - `ACCOUNT_EMAIL`: `gravelgodcoaching@gmail.com`.
5. Run `installLeadBridge()` once and approve the Gmail, external-request, and
   trigger scopes. This creates one five-minute installable trigger and performs
   the first sync.
6. Run `backfillLeadThreads()` once. It scans 180 days for known lead threads so
   Mission Control can surface older replies and active drafts. It remains
   read-only in Gmail and may be rerun safely.

## Safety invariants

- No call to `sendEmail`, `reply`, `send`, Trash, Archive, labels, or read-state APIs.
- The script refuses to run unless the effective Google account exactly matches
  the configured coaching account.
- Existing draft in a thread produces `draft_conflict`; it is never overwritten.
- Message IDs make overlapping 30-day scans and the 180-day backfill idempotent.
- Each message body is capped at 12,000 characters before transfer; Mission
  Control then strips quoted history and caps stored authored text again.
- The server ignores correspondents with no sequence enrollment or open deal,
  and stops lead sync after a deal is closed won so athlete communication moves
  to the coaching system.
- A real inbound reply pauses marketing enrollments; post-purchase service
  sequences remain active.
- Copy recommendations and Gmail draft creation are separate approval states.

Google supports `GmailMessage.createDraftReply()` and installable time-driven
triggers; see the official Gmail Service and Installable Triggers documentation.
