# Mission Control hardening — spec

Status: ready for build (revised after adversarial review, 2026-11-10) · Branch: `fix/mission-control-hardening` · Written 2026-11-10
Source: evaluation at `endure-labs/notes/active/mission-control-evaluation.md` (section 6).

## Why

Mission Control (`mission_control/`, Railway service `athlete-profiles`) is the only
thing sending the three brands' lifecycle email: 211 sends / 96 people in the last
30 days, the last today. It can stop silently, a bad build can replace a good one,
two webhooks accept anything when their key is blank, the admin login is weak, and
about a third of the dashboard is dead code. This spec fixes those without changing
what any customer receives.

## Hard rules for the builder

- **No customer-visible change.** No email copy, subject, sequence step, delay,
  enrollment rule or template changes. No new email to customers.
- **No database changes.** No migrations, no table drops. Pruned pages leave their
  tables alone (they live in the Endure Prod database and are service-role only).
- **No deploys, no Railway/Cloudflare/GitHub setting changes, no secrets read or printed.**
  Merging to `main` auto-deploys to Railway, so do not merge and do not push to `main`.
  Commit on this branch only; the owner reviews before merge.
- Read only what you need. Do not touch files outside the scope list below.
- Keep URLs that sent emails point at: `/unsubscribe`, `/poster/{token}.png`,
  `/api/season-plan/prefill/{token}`. Their behaviour must not change.
- Run `pytest mission_control/tests -q` and `node --test tests/test_fueling_lead_intake.mjs`
  (plus `tests/test_pickem.py` if pickem is touched). All must pass before each commit.
- Keep a running `docs/specs/mission-control-hardening-notes.md`: any time the code
  forces you off this spec, take the conservative option, log it under **Deviations**
  with the reason, and continue.

## Decisions (most likely to be changed by the owner — listed first)

D1. **Prune the dead admin areas** (section 6 below). Keep sequences, deals, analytics,
    triage, lead replies + gmail-sync (owner may still mean to switch the Gmail bridge on),
    tp-store-sales (off by setting, not dead), reports' referral route if anything posts to it.
D2. **Alerting goes through GitHub, not a new service.** An hourly GitHub Actions job
    calls a new `/health/jobs` and fails if the email timer is stale; GitHub emails the
    owner on failure. No new account, no new key.
D3. **Lost-lead alert goes to the owner's inbox** from the Cloudflare worker, using the
    worker's existing Resend + `NOTIFICATION_EMAIL` path, so a lead the server dropped
    can be re-entered by hand.
D4. **Docker base image stays `python:3.12-slim`.** No Docker on the build machine to
    test a different tag; changing it blind is the exact failure we just had.
D5. **Daily jobs get three chances a day but run at most once a day** (a "done today"
    marker in `gg_audit_log`), so a restart at the wrong minute cannot skip a day and
    daily volume does not change.
D6. **Not in this change:** a separate limited database login for Mission Control
    (needs a new Supabase role and a Railway variable — owner-level), an external uptime
    service, and the shared-proxy rate-limit counting.

## Changes

### 1. Webhooks refuse requests when the key is missing  (`mission_control/routers/webhooks.py`)

- `/webhooks/intake` (around `:141`), `/webhooks/subscriber` (`:337`),
  `/webhooks/resend-inbound` (`:795`) currently skip the check when `WEBHOOK_SECRET`
  is empty. Make all three call the existing strict `_require_webhook_secret`
  (`:129-131`) — empty key ⇒ 401.
- `/webhooks/resend` (`:749+`): require `svix_ok or bearer_ok` always; with no
  `WEBHOOK_SECRET` the bearer path is simply unavailable.
- Check every other `/webhooks/*` route uses the strict helper; fix any that do not.
- Tests: for each route, empty key ⇒ 401; wrong key ⇒ 401; right key ⇒ unchanged.

### 2. Unsubscribe signing never falls back to a public string  (`services/sequence_engine.py:234-237`, `config.py:157-158`)

- **Context:** as of 2026-11-10 the owner's key rotation sets `UNSUBSCRIBE_SECRET` to the
  *old* `WEBHOOK_SECRET` value, so every link already sent keeps validating, and the
  webhook key then changes. From then on `UNSUBSCRIBE_SECRET` is the permanent signing key.
- Verification accepts a code made with any of: `UNSUBSCRIBE_SECRET`, then each value in an
  optional comma-separated `UNSUBSCRIBE_SECRET_PREVIOUS`. New links are signed with
  `UNSUBSCRIBE_SECRET` only (falling back to `WEBHOOK_SECRET` as today when unset). Test:
  a link signed with a "previous" key still unsubscribes; a link signed with an unknown
  key does not. Do **not** accept the current `WEBHOOK_SECRET` when `UNSUBSCRIBE_SECRET`
  is set (after rotation it never signed anything).
- Remove the `"fallback-dev-secret"` literal. If neither `UNSUBSCRIBE_SECRET` nor
  `WEBHOOK_SECRET` is set, `generate_unsubscribe_token` raises, and the health check
  (change 4) reports unhealthy. Existing links keep validating because the key value is
  unchanged.
- Tests run with a test key set in `conftest.py`; make sure that is still true.
- Keep the `UNSUBSCRIBE_SECRET → WEBHOOK_SECRET` fallback as is (removing it would break
  every sent link if the variable were ever deleted). Add a one-line comment saying why.

### 3. Admin login  (`routers/auth_routes.py`, `middleware/auth.py`, `app.py`)

- Compare the submitted password with `hmac.compare_digest` on **bytes**
  (`.encode()` both sides; string compare raises on non-ASCII) (`auth_routes.py:42`).
- Cookie `secure=True` when running on Railway (`RAILWAY_ENVIRONMENT` set), `False`
  otherwise so local dev still works (`auth_routes.py:57`).
- Bearer check in `require_admin`: `hmac.compare_digest` on bytes too.
- Failed-login limit: global (not per address — addresses behind Railway's proxy are
  the proxy's), in memory: after 10 failures in 10 minutes, `POST /login` answers 429
  until the window clears. Successful logins are not counted.
- Signed-out browser on an admin page: a `GET` whose `Accept` includes `text/html`
  and that fails `require_admin` gets a 303 to `/login`. Bearer/API callers and
  non-GETs keep the JSON 401. Implement as an exception handler or inside
  `require_admin`; do not change the public routes. Scope it to the admin routers only
  (`/webhooks/*`, `/api/*` keep JSON 401). Requests with an `HX-Request` header (htmx
  fragments) get a 401 with an `HX-Redirect: /login` header instead of a 303.
- `secure=True` check: `RAILWAY_ENVIRONMENT` is set in prod (verified by name); also
  accept `RAILWAY_PUBLIC_DOMAIN` as the signal.
- Note in the notes file: a global failure limit means anyone can lock the login form for
  10 minutes; Bearer access still works. Accepted trade-off.
- Tests for each.

### 4. Health checks that mean something  (`app.py`, `scheduler.py`, `railway.toml`)

- `/health` (used by Railway when deploying): 200 only if the job timer is running
  (`scheduler.running`) **and** the required settings are present by name:
  `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `RESEND_API_KEY`, `WEBHOOK_SECRET`,
  `MISSION_CONTROL_SECRET`. Otherwise 503 with a list of which check failed — names
  only, never values.
- `/health/jobs` (public, no personal data): records the last **good** `process_sequences`
  tick in memory. A tick is good when the run was not `skipped` (lock held) and it did not
  fail every send (`processed == 0` or `sent > 0`). Also keep the last run's counts.
  200 if the last good tick is < 45 minutes old, or the server started < 45 minutes ago
  **and** this is the first start in the last 2 hours (record first-start time in
  `gg_settings` or `gg_audit_log` so a crash loop cannot stay green — choose one, log it).
  503 otherwise. Body: `{"last_good_tick_utc", "started_utc", "last_run": {processed,
  sent, errors}, "ok"}` — counts only, never addresses.
- `app.py` lifespan: if `scheduler.start()` fails, log at ERROR (today it is a warning,
  `app.py:28-31`); `/health` then returns 503, so Railway refuses the deploy and keeps
  the previous one.
- `railway.toml` `[deploy]`: add `healthcheckPath = "/health"` and
  `healthcheckTimeout = 120`. This is the change that stops a broken build replacing a
  working one.
- Logging: configure the root logger at INFO in `mission_control.py` (before the app
  starts) so the app's own info lines ("Sequence processing: …") reach Railway logs.
  Keep the format plain. **Set `httpx`, `httpcore`, `hpack` and `postgrest` loggers to
  WARNING** — at INFO, httpx logs every database URL, and lookups put customer emails in
  the URL. Test: a database call under the configured logging emits no line containing
  an email address.
- Required-settings check: "present" means set and non-empty. Do not add
  `UNSUBSCRIBE_SECRET` or `RESEND_WEBHOOK_SECRET` to the required list.
- Existing tests that will need updating: `conftest.py:268-291` and `_make_client` in
  `test_admin_auth.py` stub the lifespan, so the scheduler never runs in tests, and
  `conftest.py:23` sets `RESEND_API_KEY=""`; `test_webhooks.py:215` asserts `/health`
  returns exactly `{"status":"ok"}`, `test_admin_auth.py:160` expects 200. Make the
  scheduler/settings check injectable for tests and update these.

### 5. Hourly heartbeat  (new `.github/workflows/mission-control-heartbeat.yml`)

- `schedule: cron "17 * * * *"` plus `workflow_dispatch`.
- One step: `curl -fsS --max-time 20 https://athlete-profiles-production.up.railway.app/health/jobs`
  with two retries 60 s apart. Failure ⇒ job fails ⇒ GitHub notifies the owner.
- No secrets, no checkout, `permissions: {}`, `timeout-minutes: 5`.

### 6. Prune dead areas  (D1)

Evidence (Endure Prod database, 2026-11-10): 0 plan pipeline runs ever; 0 touchpoints or
communications sent in 90 days; 5 athletes ever, none in 90 days; 0 NPS scores.

- **Never remove any function from `mission_control/supabase_client.py`**, and never touch
  the top-level `pipeline/` package (`nutrition_api.py` and other tests import it).
  `services/stats.dashboard_stats` (imported by `scripts/daily_report.py:300`) still uses
  touchpoint/NPS/pipeline-run helpers; race_countdown, win_back and `/webhooks/resend-inbound`
  still read `gg_athletes` (suppression) — keep all of that working.
- Nothing outside Mission Control calls `/webhooks/intake` or `/reports/referral`
  (checked: workers, `web/*.js`, workflows, `scripts/`, the Gmail bridge, sibling repos),
  so remove `reports` whole.
- Remove routers, templates and tests for: `mission_control/routers/pipeline.py` (also removes the ability to run
  `run_pipeline.py` from the web — good), `touchpoints`, `athletes`, the NPS part of
  `reports` (keep `/reports/referral` only if something posts to it — grep the repo and
  workers; if nothing does, remove `reports` whole), and `/webhooks/intake`.
- Remove the start-up filesystem sync in `mission_control.py` (`sync_all`, logs show
  "0 athletes synced") and `mission_control/sync.py` if nothing else imports it.
- **Triage**: `routers/triage.py` has `/triage/plans/{slug}/approve` and
  `/triage/touchpoints/{tp_id}/sent` and pulls athlete/touchpoint stats. Remove those
  two routes and the panels that only show pruned data; the triage page must still
  render. Update its tests.
- Remove dead nav links in `templates/base.html` / dashboard, and links to `/athletes/...`
  on pages that stay: `deals/detail.html:51`, `triage.html:121,163,174,207,452`,
  `dashboard.html:150,183` (render plain text instead of a link).
- Tests to update: `test_admin_auth.py:26-33` lists `/athletes/`, `/pipeline/`,
  `/reports/` as protected; `TestIntakeWebhook` in `test_webhooks.py`; `test_deliver_plan.py`.
  `test_triage.py` is in CI's explicit list and must keep passing.
- Services used only by the removed routes (`pipeline_runner.py`, `touchpoint_sender.py`,
  `file_storage.py`, etc.) go too — but only after `git grep` proves nothing else
  (including `road-race-automation`-style direct imports such as
  `scripts/daily_report.py` importing `mission_control.services.ga4/revenue/stats`, and
  anything under `scripts/`) imports them. `ga4`, `revenue`, `stats` stay.
- Update `.github/workflows/test.yml`'s explicit test list if it names removed tests.

### 7. Pin what can silently break  (`requirements.txt`)

Exact versions taken from the 2026-11-10 successful Railway build log:
`apscheduler==3.11.3`, `supabase==2.34.1`, `uvicorn==0.54.0`, `jinja2==3.1.6`,
`stripe==16.1.0`, `anthropic==2.8.0`, `resend==2.53.2`, `httpx==0.28.1`,
`python-multipart==0.0.33`, `google-analytics-data==0.23.3`, `requests==2.34.2`,
`google-genai==3.0.0`, `Pillow==13.0.0`, `fastmcp==4.1.7`,
plus the floating ones Mission Control imports directly: `pydantic==2.14.3`,
`python-dotenv==1.2.4`, `pyyaml==6.0.3`. (Checked: all install on CI's Python 3.11 and
3.13 and Docker's 3.12.)
Leave `fastapi`/`starlette`/`playwright` as already pinned. Add a comment: bump
deliberately, run the Mission Control tests.
**Check first** that nothing else in the repo (CI workflows, other Dockerfiles, scripts)
installs this same `requirements.txt` expecting newer versions; if a pin conflicts with
a test environment, log a deviation rather than loosening silently.

### 8. Rebuild only when Mission Control's inputs change  (`railway.toml`)

- Add `[build] watchPatterns = [...]` listing everything the container reads at run
  time. Derive the list from the code, not from this spec. Known so far:
  `mission_control/**`, `mission_control.py`, `requirements.txt`, `Dockerfile`,
  `railway.toml`, `pipeline/__init__.py`, `pipeline/nutrition.py` (nutrition API),
  `race-data/**` (email race facts, `sequence_engine.py:689`; races API),
  `web/race-index.json`, `data/pricing.json`, `guide/fonts/**`, `templates/emails/**`
  (`config.TEMPLATES_DIR`). Grep `REPO_ROOT`, `Path(`, `open(`, `read_text` across
  `mission_control/` and anything it imports to complete it.
- Write the derived list and the grep evidence into the notes file. Missing a path only
  makes a change wait for the next deploy; it never breaks the server — but be thorough.

### 9. Daily jobs survive a restart without running twice  (`scheduler.py`, D5)

- Today each daily job has one in-memory slot; a restart across 14:00–15:30 UTC loses that
  day's run, and `misfire_grace_time` does not help (the job list lives in memory).
- Enrollment is already deduplicated (`sequence_engine.enroll` `:146-152`, plus a
  `UNIQUE(sequence_id, contact_email)` rule), **but every cap is per run** (countdown
  `_max_per_run`, debrief `_MAX_ENROLLMENTS_PER_RUN`, `WIN_BACK_DAILY_CAP`, race_watch
  `_MAX_SENDS = 50`, which emails directly). So simply running three times would triple
  daily volume. Do not do that.
- Instead: give each of `race_countdown`, `race_debrief`, `race_watch`, `win_back` three
  slots (current time, +3 h, +6 h). Each run first looks in `gg_audit_log` for a
  `daily_job_done` row with `entity_id = '<job>:<UTC date>'`; if found it returns at once.
  Otherwise it runs and writes that row at the end, only if the run completed without
  raising. A run that aborts (e.g. race data fetch failed) writes nothing, so a later
  slot retries.
- This also guards the deploy overlap (old and new container both alive for a minute).
  The check-then-run is not atomic; accept that small window and note it.
- Tests: second same-day call does nothing even when a backlog remains; a raising run
  leaves no marker; next UTC day runs again.

### 10. Lost leads become loud  (`workers/fueling-lead-intake/worker.js`, D3)

- Today a Mission Control failure for an ordinary source (e.g. `prep_kit_gate`) is only
  logged and swallowed: `notifyMissionControl` (`:932-986`) returns `{}` either way.
- Make `notifyMissionControl` report `{ok, status}` (keep returning `poster_token` when
  present), and give its fetch `signal: AbortSignal.timeout(8000)`.
- On failure for a source **not** in `STORAGE_REQUIRED` and not `fueling_calculator`
  (which already emails the owner, `:221-229`), send one plain email to
  `env.NOTIFICATION_EMAIL`: subject `Lead not saved: <source>`, body with email, name,
  source, race slug, brand and status. Write a small shared `sendResendEmail` helper
  (the three existing senders each inline the Resend call). **From address must be
  `noreply@gravelgodcycling.com`** — other addresses on that domain are accepted by
  Resend but never delivered (`:797-800`); do not use `BRAND_SENDERS`' `leads@`.
- The handler is `fetch(request, env)` with no `ctx` (`:63`), so there is no `waitUntil`:
  chain the alert onto the Mission Control promise inside the existing
  `Promise.allSettled`. The visitor's response and status code must not change.
- Flood cap: module-level counter, at most 5 alerts per 10 minutes per worker instance;
  beyond that log one "N more not alerted" line. Skip quietly if `RESEND_API_KEY` or
  `NOTIFICATION_EMAIL` is unset (log once).
- `pickem-intake`: leave as is apart from a clearer log line. It stores every pick in KV
  and has a `/resync` route that replays what Mission Control missed
  (`pickem-intake/worker.js:10, :281`), so its leads are recoverable. Note in the notes file.
- Tests in `tests/test_fueling_lead_intake.mjs`: MC 500 ⇒ one alert and visitor still gets
  success; MC timeout ⇒ alert; MC ok ⇒ no alert; `fueling_calculator` failure ⇒ no extra
  alert; 6 failures in a row ⇒ 5 alerts.
- Workers deploy by hand (`wrangler deploy`), not by merge. Write the exact deploy
  command for the owner into the notes file; do not run it.

## Done looks like

- All ten changes committed on `fix/mission-control-hardening` in small commits
  (one per numbered change is fine), tests green, notes file with deviations,
  watch-pattern evidence and the owner's manual steps (worker deploys, merge order).
- No customer-visible change, no migrations, nothing pushed to `main`, nothing deployed.

## Owner steps after review (for the notes file)

1. Merge the PR (Railway deploys; the new health check guards the switch-over).
2. Confirm `/health` and `/health/jobs` return 200.
3. Deploy the fueling worker with `wrangler deploy` from its folder (pickem unchanged
   unless the log line was touched).
4. Run the heartbeat workflow once by hand from the Actions tab, and check the failure
   email reaches the owner (GitHub sends scheduled-run failures to whoever last edited the
   schedule — if that was a bot or agent account, the owner should push a trivial edit of
   that file themselves, or watch the repo's Actions notifications).
