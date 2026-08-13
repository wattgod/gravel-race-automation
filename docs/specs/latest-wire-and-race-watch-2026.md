# /latest/ Wire Page + Watch-This-Race — 2026-08-13

Spec author: Claude (Fable). Implementer: Codex. Review/merge/deploy: Claude → Matt.
Global rules: `~/.codex/AGENTS.md`. Register law: `docs/email-voice-model.md` —
every new email template runs `scripts/friend_test.py --gate`. Gravel God only;
road/XC mirrors are follow-ups.

## Context (verified — build on, don't re-derive)

- `web/race-intel.json` exists (generate_race_intel.py, 287 races, events
  `{date, type, text}`, bulk-commit guard). Race pages render a LATEST
  ledger from it (generate_neo_brutalist.py).
- The intake worker (`workers/fueling-lead-intake/worker.js`) validates
  `source` against KNOWN_SOURCES (line ~35) and forwards to the MC webhook,
  which routes (trigger, brand) → sequences. Worker deploys via wrangler —
  a repo commit does NOT update the live worker; flag the deploy step.
- MC engine: enroll() dedups on (sequence_id, contact_email), has the
  contact-level unsubscribe guard, and sends via Resend with the standard
  unsubscribe footer. Scheduler runs daily jobs (race_countdown 14:00,
  race_debrief 14:30 UTC).
- Fetching anything from gravelgodcycling.com server-side MUST reuse the
  `_fetch_dates_sync`-style UA + gg_settings last-good pattern
  (`mission_control/services/race_countdown.py`) — hosts 403 default UAs
  and intermittently serve non-JSON.

## WS-A — `/latest/` wire page + RSS

1. `wordpress/generate_latest.py` → single page deployed at `/latest/`.
   Flatten all races' intel events, newest first, capped at 12 months.
   Month-grouped sections with stable anchors (`#2026-08`); within a month,
   rows grouped by day. Row: `date · RACE NAME (link to /race/{slug}/) ·
   event text`. Neo-brutalist, existing brand tokens and shared
   header/footer, monospace ledger styling consistent with the race-page
   LATEST section. No pagination — one long page IS the product; it must
   stay fast (text only, no per-row images).
2. Top of page: one honest line, no hype: "Every verified change to the
   race database, newest first." Nothing for sale on this page.
3. RSS: `web/feed/latest.xml` (RSS 2.0, follow generate_rss_feed.py
   conventions), 50 newest events, item link = race page + month anchor.
   Autodiscovery `<link rel="alternate">` on /latest/.
4. Race-page ledger header links here: "full wire →" (small, existing
   link styling) — added in generate_neo_brutalist.py.
5. Deploy plumbing: `--sync-latest` flag in scripts/push_wordpress.py
   (mirror --sync-insights: single page via SCP) + include /latest/ in the
   sitemap only if the deployed page exists (see the sitemap 404 lesson at
   push_wordpress.py:1730 — never sitemap an undeployed URL).
6. Tests: month grouping + anchors, 12-month cap, empty-intel renders a
   valid page with an honest "no changes yet" line, RSS validity (parse
   with stdlib xml), race links well-formed, `</script>`-safe if any JSON
   is inlined.

## WS-B — Watch this race

One-line affordance, not a second form fighting the prep-kit gate.

1. UI (generate_neo_brutalist.py): in the LATEST section footer — and for
   races with no events, a standalone one-liner where LATEST would sit —
   render: "WATCH THIS RACE — email me when this entry changes." Click
   expands an inline email field + honeypot (same pattern as the kit
   gate), posts to the worker with `source: race_watch`, `race_slug`,
   `race_name`. Success copy: "Watching. I'll email you when something
   changes." localStorage flag so a watcher sees "Watching ✓" on return.
2. Worker: add `race_watch` to KNOWN_SOURCES; forward unchanged. Note in
   the recap that the live worker needs `wrangler deploy` (do NOT deploy
   it yourself).
3. MC sequence `race_watch_v1` (new file, registered): trigger
   `race_watch`, single step at delay 0, template `race_watch_confirm`,
   subject `watching {race_name}`. Body (register, friend-gate it):
   "{greeting} you're watching {race_name} — when its entry changes
   (date confirmed, re-rated, course news), I'll send it over. Nothing
   else comes with this. — Matti". After the step the enrollment
   completes; watchers = enrollments with sequence_id race_watch_v1 and
   race_slug in source_data. No new tables.
4. Notifier — `mission_control/services/race_watch.py`, daily scheduler
   job at 15:00 UTC:
   - Fetch `https://gravelgodcycling.com/race-intel.json`… VERIFY the
     actual deployed URL of the intel JSON first; if it is not deployed
     anywhere yet, add it to `--sync-latest`'s uploads (it's needed live
     for this job) and fetch that. UA + gg_settings last-good fallback
     per the race-dates pattern; abort writes `race_watch_aborted` to
     gg_audit_log (never silent).
   - For each active-or-completed race_watch_v1 enrollment (not
     unsubscribed), compare the race's newest event date to
     `source_data.last_notified_event_date` (absent = enrollment date
     baseline: never replay history at signup). New events → ONE email
     listing them (template `race_watch_update`, subject
     `{race_name}: update`, body = the ledger lines verbatim + "— Matti",
     friend-gated), then update last_notified_event_date via db.update.
   - Rate cap: max one notification email per watcher per 7 days (fold
     newer events into the next send). Cap 50 sends/run, log
     race_watch_notified per send to gg_audit_log.
5. Tests: worker-payload contract test (field names), sequence
   registration + confirm step, notifier unit tests with fake enrollments
   and intel dicts (new-event detection, signup baseline, 7-day cap, cap
   per run, unsubscribed skipped), abort surfacing.

## Out of scope

Road/XC mirrors; digest emails beyond the 7-day fold; any chat surface;
watch management UI (unsubscribe link is the management UI).

## Verification (before claiming done)

- `$VENV -m pytest` touched files green; full-suite delta vs your starting
  commit = zero new failures.
- `python3 scripts/friend_test.py --brand gravelgod --sequence race_watch
  --gate` exit 0 (or --draft-file if the sequence flag doesn't resolve).
- Render /latest/ locally + regenerate unbound-200 race page; include
  output paths in the recap for visual review.
- Do NOT push, deploy pages, or deploy the worker. Commit to your branch;
  Claude reviews, merges, deploys; wrangler deploy is called out
  separately.
